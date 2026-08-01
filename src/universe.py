#!/usr/bin/env python
# coding: utf-8
"""
P0: build the clean CRSP monthly universe.

The corrections applied here are the difference between a credible factor study
and one that quietly overstates every premium:

  1. Share-code and exchange filters, applied through the NAME HISTORY, so a
     stock that changed share class is treated correctly period by period.
  2. Delisting returns spliced into the return series, with the Shumway (1997)
     substitution where CRSP records a performance-related delisting but no
     return. Omitting this is the single largest upward bias in retail
     replications: the worst month of a failing stock is simply missing.
  3. Market equity aggregated at the COMPANY level across share classes, then
     assigned to the primary permno, which is the Fama-French convention.

References
----------
Shumway, T. (1997). "The Delisting Bias in CRSP Data." Journal of Finance 52(1).
Shumway, T. and Warther, V. (1999). "The Delisting Bias in CRSP's Nasdaq Data."
    Journal of Finance 54(6).
Fama, E. and French, K. (1993). Journal of Financial Economics 33(1).
"""
import os

import numpy as np
import pandas as pd

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
PROCESSED = os.path.join(os.path.dirname(__file__), "..", "data", "processed")

COMMON_SHARE_CODES = (10, 11)          # ordinary common shares
MAJOR_EXCHANGES = (1, 2, 3)            # NYSE, AMEX, NASDAQ

# CRSP delisting codes that indicate failure rather than merger or voluntary exit.
PERFORMANCE_DELIST = lambda c: (c == 500) | ((c >= 520) & (c <= 584))

# Shumway's estimates of the return actually realised in a performance delisting
# where CRSP records none. NASDAQ is worse than the listed exchanges.
SHUMWAY_LISTED = -0.30
SHUMWAY_NASDAQ = -0.55


def load_raw(name, raw_dir=None):
    path = os.path.join(raw_dir or RAW, f"{name}.parquet")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} missing. Run: python scripts/pull_crsp_universe.py")
    return pd.read_parquet(path)


def attach_name_info(msf, names):
    """Attach share code / exchange / SIC as of each observation's date.

    Uses the name-history intervals rather than a single current record. A
    permno's share code and exchange change over its life, and applying today's
    values to its whole history silently admits or excludes the wrong periods.
    """
    names = names.copy()
    # An open-ended name record has a null end date; treat it as still current.
    names["nameendt"] = names["nameendt"].fillna(pd.Timestamp("2100-12-31"))

    out = msf.merge(names, on="permno", how="left")
    in_window = (out["date"] >= out["namedt"]) & (out["date"] <= out["nameendt"])
    out = out[in_window].copy()

    # A handful of permno-months match two overlapping name records; keep the
    # one that started most recently.
    out = out.sort_values(["permno", "date", "namedt"])
    out = out.drop_duplicates(subset=["permno", "date"], keep="last")
    return out


def apply_delisting_returns(df, delist):
    """Splice delisting returns into the monthly return series.

    CRSP's `ret` is missing in the month a stock disappears. The delisting
    return records what a holder actually got. Where that is missing but the
    delisting code indicates failure, Shumway's substitution is applied.
    """
    d = delist.copy()
    d["dlmonth"] = d["dlstdt"].values.astype("datetime64[M]")

    df = df.copy()
    df["month"] = df["date"].values.astype("datetime64[M]")

    out = df.merge(
        d[["permno", "dlmonth", "dlret", "dlstcd"]].rename(columns={"dlmonth": "month"}),
        on=["permno", "month"], how="left",
    )

    perf = PERFORMANCE_DELIST(out["dlstcd"].fillna(0))
    missing_dlret = out["dlret"].isna() & out["dlstcd"].notna()
    substitute = perf & missing_dlret

    out["dlret_used"] = out["dlret"]
    out.loc[substitute & out["exchcd"].isin([1, 2]), "dlret_used"] = SHUMWAY_LISTED
    out.loc[substitute & (out["exchcd"] == 3), "dlret_used"] = SHUMWAY_NASDAQ
    out["dlret_substituted"] = substitute

    # Compound the partial-month return with the delisting return.
    r, dl = out["ret"], out["dlret_used"]
    out["ret_adj"] = np.where(
        r.notna() & dl.notna(), (1 + r) * (1 + dl) - 1,
        np.where(r.isna() & dl.notna(), dl, r),
    )
    return out.drop(columns=["month"])


def compute_market_equity(df):
    """Company-level market equity in $ millions, assigned to the primary permno.

    CRSP prices are negative when the print is a bid/ask midpoint rather than a
    trade, and `shrout` is in thousands. Fama-French sum market equity across a
    company's share classes (permnos sharing a permco) and attach the total to
    the permno with the largest individual market equity.
    """
    df = df.copy()
    df["me_permno"] = df["prc"].abs() * df["shrout"] / 1000.0  # $ millions

    df["me_permno"] = pd.to_numeric(df["me_permno"], errors="coerce").astype(float)

    # Aggregate once and merge back. A per-group Python lambda here runs over
    # roughly a million permco-date groups and dominates the whole build.
    agg = (df.groupby(["permco", "date"])["me_permno"]
             .agg(me_company="sum", me_max="max", n_valid="count")
             .reset_index())
    # A company whose share classes all lack prices should stay NaN rather than
    # collapsing to a market cap of zero, which `sum` would otherwise produce.
    agg.loc[agg["n_valid"] == 0, "me_company"] = np.nan

    df = df.merge(agg, on=["permco", "date"], how="left")

    # A NaN market equity can never be the company maximum. Comparing nullable
    # values propagates NA, so resolve to a plain bool before use.
    df["is_primary"] = (df["me_permno"] == df["me_max"]).fillna(False).astype(bool)

    # Market equity used for weighting and for size sorts is the company total,
    # carried only on the primary permno so a company is not counted twice.
    df["me"] = np.where(df["is_primary"], df["me_company"], np.nan)
    return df


def build_universe(raw_dir=None, start="1963-01-01", end="2024-12-31",
                   min_price=None, save=True):
    """Run P0 end to end and return the cleaned monthly panel."""
    msf = load_raw("msf", raw_dir)
    names = load_raw("msenames", raw_dir)
    delist = load_raw("msedelist", raw_dir)

    n0 = len(msf)
    df = attach_name_info(msf, names)
    n1 = len(df)

    df = df[df["shrcd"].isin(COMMON_SHARE_CODES)]
    n2 = len(df)
    df = df[df["exchcd"].isin(MAJOR_EXCHANGES)]
    n3 = len(df)

    df = apply_delisting_returns(df, delist)
    df = compute_market_equity(df)

    if min_price is not None:
        df = df[df["prc"].abs() >= min_price]

    df = df[(df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))]
    df = df.sort_values(["permno", "date"]).reset_index(drop=True)

    stats = {
        "raw_rows": n0,
        "after_name_merge": n1,
        "after_share_code_filter": n2,
        "after_exchange_filter": n3,
        "final_rows": len(df),
        "n_permnos": int(df["permno"].nunique()),
        "n_months": int(df["date"].nunique()),
        "delisting_returns_used": int(df["dlret_used"].notna().sum()),
        "shumway_substitutions": int(df["dlret_substituted"].sum()),
        "date_min": str(df["date"].min().date()),
        "date_max": str(df["date"].max().date()),
    }

    if save:
        os.makedirs(PROCESSED, exist_ok=True)
        keep = ["permno", "permco", "date", "ret", "ret_adj", "retx", "prc",
                "shrout", "vol", "shrcd", "exchcd", "siccd", "ticker",
                "me_permno", "me", "is_primary", "dlret_used", "dlstcd"]
        df[keep].to_parquet(os.path.join(PROCESSED, "universe.parquet"), index=False)

    return df, stats
