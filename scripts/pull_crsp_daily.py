#!/usr/bin/env python
# coding: utf-8
"""
One-shot WRDS pull of daily CRSP returns for the study's common-share universe.

Needed to build the actual Ang, Hodrick, Xing and Zhang (2006) idiosyncratic and
total volatility signals, which are defined on DAILY returns within each month.
The monthly-frequency proxy used earlier in this project was validated against
Chen-Zimmermann's reference series and found to measure a different, much
slower-moving quantity (correlation 0.32 against the real signal). This script
gets the real inputs.

Single wrds.Connection() (one Duo push), looped over 5-year blocks so no single
query or in-memory frame gets unmanageable. Only permno/date/ret is kept: the
month-level regressions this feeds need nothing else, and dsf's full row (bid,
ask, cfacpr, ...) would multiply the footprint for no benefit here.

The share-code/exchange filter mirrors scripts/pull_crsp_universe.py exactly
(SHRCD 10/11, EXCHCD 1/2/3), applied by joining to msenames rather than an IN
list of ~26,000 permnos, which most SQL engines handle poorly at that size.
"""
import io
import json
import os
from datetime import date

import pandas as pd

CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "dsf")
BLOCKS = [(y, min(y + 4, 2024)) for y in range(1963, 2025, 5)]


def read_credentials(path=None):
    path = path or os.path.expanduser("~/.wrds_credentials")
    creds = {}
    with io.open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and "=" in line:
                k, v = line.split("=", 1)
                creds[k.strip().lower()] = v.strip()
    return creds


def main():
    os.makedirs(CACHE, exist_ok=True)
    creds = read_credentials()
    os.environ.setdefault("PGUSER", creds["username"])
    if creds.get("password"):
        os.environ.setdefault("PGPASSWORD", creds["password"])

    import wrds

    print(f"connecting to WRDS as {creds['username']} (one Duo push for the whole pull)",
          flush=True)
    db = wrds.Connection(wrds_username=creds["username"])

    total_rows = 0
    try:
        for lo, hi in BLOCKS:
            out_path = os.path.join(CACHE, f"dsf_{lo}_{hi}.parquet")
            if os.path.exists(out_path):
                print(f"{lo}-{hi}: cached, skipping", flush=True)
                continue

            sql = f"""
                SELECT d.permno, d.date, d.ret
                FROM crsp.dsf d
                JOIN crsp.msenames n
                  ON d.permno = n.permno
                 AND d.date BETWEEN n.namedt AND COALESCE(n.nameendt, '2100-12-31')
                WHERE d.date BETWEEN '{lo}-01-01' AND '{hi}-12-31'
                  AND n.shrcd IN (10, 11)
                  AND n.exchcd IN (1, 2, 3)
            """
            df = db.raw_sql(sql, date_cols=["date"])
            df["ret"] = pd.to_numeric(df["ret"], errors="coerce").astype("float32")
            df["permno"] = df["permno"].astype("int32")
            df.to_parquet(out_path, index=False)
            total_rows += len(df)
            print(f"{lo}-{hi}: {len(df):,} rows -> {os.path.basename(out_path)}", flush=True)
    finally:
        db.close()
        print("connection closed", flush=True)

    meta = {"pulled_at": date.today().isoformat(), "blocks": BLOCKS,
            "total_rows_this_run": total_rows}
    with io.open(os.path.join(CACHE, "pull_meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    print("done", flush=True)


if __name__ == "__main__":
    main()
