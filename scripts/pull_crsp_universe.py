#!/usr/bin/env python
# coding: utf-8
"""
One-shot WRDS pull for the factor study: CRSP universe + Compustat + CCM link.

Every wrds.Connection() costs a Duo push, so P0 (CRSP) and P1 (Compustat)
data are both fetched inside a single connection and cached to parquet.

    python scripts/pull_crsp_universe.py

Tables
------
crsp.msf           monthly returns, price, shares outstanding
crsp.msenames      share code, exchange code, SIC, ticker
crsp.msedelist     delisting returns and codes
comp.funda         annual fundamentals for value / profitability / investment
crsp.ccmxpf_lnkhist  Compustat gvkey to CRSP permno link
"""
import io
import json
import os
import sys
from datetime import date

import pandas as pd

CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

# One extra year at the front: momentum needs a 12-month lookback before the
# 1963 sample start, and book-to-market needs the prior fiscal year.
START = "1961-01-01"
END = "2024-12-31"


def read_credentials(path=None):
    path = path or os.path.expanduser("~/.wrds_credentials")
    creds = {}
    with io.open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and "=" in line:
                k, v = line.split("=", 1)
                creds[k.strip().lower()] = v.strip()
    if "username" not in creds:
        raise ValueError(f"No 'username=' line in {path}")
    return creds


def main():
    os.makedirs(CACHE, exist_ok=True)
    log_lines = []

    def log(m):
        print(m, flush=True)
        log_lines.append(m)

    creds = read_credentials()
    # wrds.Connection() drops to an interactive prompt if its first attempt
    # fails, which deadlocks a non-interactive run. Seed libpq's own env vars
    # before importing wrds so the first attempt succeeds.
    os.environ.setdefault("PGUSER", creds["username"])
    if creds.get("password"):
        os.environ.setdefault("PGPASSWORD", creds["password"])

    import wrds

    log(f"connecting to WRDS as {creds['username']} (expect ONE Duo push)")
    db = wrds.Connection(wrds_username=creds["username"])

    try:
        # --- CRSP monthly stock file -----------------------------------------
        log("pulling crsp.msf ...")
        msf = db.raw_sql(
            f"""SELECT permno, permco, date, ret, retx, prc, shrout, vol
                FROM crsp.msf
                WHERE date BETWEEN '{START}' AND '{END}'""",
            date_cols=["date"],
        )
        log(f"  msf: {len(msf):,} rows, {msf.permno.nunique():,} permnos")

        # --- Name history (share code / exchange / SIC) ----------------------
        log("pulling crsp.msenames ...")
        names = db.raw_sql(
            """SELECT permno, namedt, nameendt, shrcd, exchcd, siccd, ticker, comnam
               FROM crsp.msenames""",
            date_cols=["namedt", "nameendt"],
        )
        log(f"  msenames: {len(names):,} rows")

        # --- Delisting returns ------------------------------------------------
        log("pulling crsp.msedelist ...")
        delist = db.raw_sql(
            """SELECT permno, dlstdt, dlret, dlstcd
               FROM crsp.msedelist""",
            date_cols=["dlstdt"],
        )
        log(f"  msedelist: {len(delist):,} rows")

        # --- Compustat annual fundamentals ------------------------------------
        # The four filters are the standard Compustat screen: industrial format,
        # standardised data, domestic population, consolidated.
        log("pulling comp.funda ...")
        funda = db.raw_sql(
            f"""SELECT gvkey, datadate, fyear, at, lt, seq, ceq, pstkl, pstkrv,
                       pstk, txditc, txdb, itcb, revt, cogs, xsga, xint, ib, ni
                FROM comp.funda
                WHERE indfmt='INDL' AND datafmt='STD' AND popsrc='D' AND consol='C'
                  AND datadate BETWEEN '{START}' AND '{END}'""",
            date_cols=["datadate"],
        )
        log(f"  funda: {len(funda):,} rows, {funda.gvkey.nunique():,} gvkeys")

        # --- CCM link table ---------------------------------------------------
        log("pulling crsp.ccmxpf_lnkhist ...")
        link = db.raw_sql(
            """SELECT gvkey, lpermno, lpermco, linktype, linkprim, linkdt, linkenddt
               FROM crsp.ccmxpf_lnkhist
               WHERE linktype IN ('LU','LC') AND linkprim IN ('P','C')""",
            date_cols=["linkdt", "linkenddt"],
        )
        log(f"  ccm link: {len(link):,} rows")
    finally:
        db.close()
        log("connection closed")

    for name, df in [("msf", msf), ("msenames", names), ("msedelist", delist),
                     ("funda", funda), ("ccmlink", link)]:
        path = os.path.join(CACHE, f"{name}.parquet")
        df.to_parquet(path, index=False)
        log(f"cached {name}: {len(df):,} rows -> {os.path.basename(path)}")

    meta = {
        "pulled_at": date.today().isoformat(),
        "start": START, "end": END,
        "rows": {"msf": len(msf), "msenames": len(names), "msedelist": len(delist),
                 "funda": len(funda), "ccmlink": len(link)},
        "msf_date_range": [str(msf.date.min().date()), str(msf.date.max().date())],
        "n_permnos": int(msf.permno.nunique()),
    }
    with io.open(os.path.join(CACHE, "pull_meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    with io.open(os.path.join(CACHE, "pull_log.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log_lines))
    log("done")


if __name__ == "__main__":
    main()
