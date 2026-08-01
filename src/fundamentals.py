#!/usr/bin/env python
# coding: utf-8
"""
P1: Compustat fundamentals, linked to CRSP and aligned to Fama-French timing.

Two things here are load-bearing and easy to get quietly wrong.

**The CCM link is an interval, not a key.** A gvkey maps to different permnos
over time. Merging on gvkey alone attaches fundamentals to the wrong company
after any reorganisation. The link is valid only for `linkdt <= datadate <=
linkenddt`, and the pull already restricted to linktype LU/LC and linkprim P/C
(the primary, researched links).

**The lag is not conservatism, it is the absence of look-ahead.** Fama-French
match a fiscal year ending in calendar year t-1 to returns from July of year t
through June of t+1. Annual reports are filed months after the fiscal year ends,
so anything shorter uses numbers the market could not have seen. The December
t-1 market equity used for book-to-market is a separate choice: it puts the
value ratio on a common measurement date across firms with different fiscal
year ends.

References
----------
Fama, E. and French, K. (1993, 2015).
Novy-Marx, R. (2013). "The Other Side of Value." JFE 108(1).
"""
import os

import numpy as np
import pandas as pd

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
PROCESSED = os.path.join(os.path.dirname(__file__), "..", "data", "processed")


def compute_book_equity(f):
    """Fama-French book equity, using the documented fallback hierarchy.

    BE = shareholders' equity + deferred taxes - preferred stock

    Each component has a preferred source and fallbacks, because Compustat
    coverage of the preferred item is patchy in the early sample. Collapsing the
    hierarchy to a single field loses a large share of pre-1980 firms.
    """
    f = f.copy()

    # Compustat columns arrive as nullable dtypes, where any comparison
    # involving a missing value yields pd.NA and blows up the moment it reaches
    # a boolean context. Coerce to plain float once, here, rather than guarding
    # every downstream expression.
    numeric = ["at", "lt", "seq", "ceq", "pstkl", "pstkrv", "pstk", "txditc",
               "txdb", "itcb", "revt", "cogs", "xsga", "xint", "ib", "ni"]
    for c in numeric:
        if c in f.columns:
            f[c] = pd.to_numeric(f[c], errors="coerce").astype(float)

    # Shareholders' equity: SEQ, else CEQ + PSTK, else AT - LT.
    she = f["seq"]
    she = she.fillna(f["ceq"] + f["pstk"].fillna(0.0))
    she = she.fillna(f["at"] - f["lt"])

    # Deferred taxes and investment tax credit.
    dt = f["txditc"].fillna(f["txdb"].fillna(0.0) + f["itcb"].fillna(0.0))

    # Preferred stock: redemption value, else liquidating, else par.
    ps = f["pstkrv"].fillna(f["pstkl"]).fillna(f["pstk"])

    f["be"] = she + dt.fillna(0.0) - ps.fillna(0.0)
    # Negative book equity makes book-to-market uninterpretable, so it is
    # excluded rather than winsorised.
    f.loc[f["be"] <= 0, "be"] = np.nan
    return f


def compute_fundamental_signals(f):
    """Operating profitability and asset growth, per FF5 definitions."""
    f = f.sort_values(["gvkey", "datadate"]).copy()

    # Operating profitability: revenues less COGS, SG&A and interest, over book
    # equity. Missing expense items are treated as zero only when revenue and
    # COGS are present, which is the FF construction.
    opinc = (f["revt"] - f["cogs"].fillna(0.0)
             - f["xsga"].fillna(0.0) - f["xint"].fillna(0.0))
    f["op"] = np.where(f["revt"].notna() & f["cogs"].notna(), opinc / f["be"], np.nan)

    # Asset growth. Only meaningful against the same firm's prior fiscal year,
    # so the lag is taken within gvkey and rejected if the years are not
    # consecutive (gaps mean a restatement or a coverage break).
    f["at_lag"] = f.groupby("gvkey")["at"].shift(1)
    f["fyear_lag"] = f.groupby("gvkey")["fyear"].shift(1)
    consecutive = ((f["fyear"] - f["fyear_lag"]) == 1).fillna(False).astype(bool)
    positive_base = (f["at_lag"] > 0).fillna(False).astype(bool)
    f["inv"] = np.where(consecutive & positive_base,
                        (f["at"] - f["at_lag"]) / f["at_lag"], np.nan)
    return f


def link_to_permno(funda, link):
    """Attach CRSP permno using the CCM link validity window."""
    link = link.copy()
    link["linkenddt"] = link["linkenddt"].fillna(pd.Timestamp("2100-12-31"))

    m = funda.merge(link, on="gvkey", how="inner")
    valid = (m["datadate"] >= m["linkdt"]) & (m["datadate"] <= m["linkenddt"])
    m = m[valid].copy()
    m = m.rename(columns={"lpermno": "permno"})

    # A gvkey can briefly map to two permnos; keep the primary link.
    m["linkprim_rank"] = (m["linkprim"] == "P").astype(int)
    m = m.sort_values(["gvkey", "datadate", "linkprim_rank"])
    m = m.drop_duplicates(subset=["gvkey", "datadate"], keep="last")
    return m


def build_fundamentals(raw_dir=None, save=True):
    """Run P1 and return one row per permno per formation year."""
    raw_dir = raw_dir or RAW
    funda = pd.read_parquet(os.path.join(raw_dir, "funda.parquet"))
    link = pd.read_parquet(os.path.join(raw_dir, "ccmlink.parquet"))

    f = compute_book_equity(funda)
    f = compute_fundamental_signals(f)
    n_funda = len(f)

    f = link_to_permno(f, link)
    n_linked = len(f)

    # Fiscal year ending in calendar year Y is used to form portfolios in June
    # of Y+1, and held July Y+1 through June Y+2.
    f["fy_end_year"] = f["datadate"].dt.year
    f["formation_june"] = pd.to_datetime(
        (f["fy_end_year"] + 1).astype(str) + "-06-30")

    # Where a firm reports twice in one calendar year (fiscal year change), keep
    # the later report.
    f = f.sort_values(["permno", "fy_end_year", "datadate"])
    f = f.drop_duplicates(subset=["permno", "fy_end_year"], keep="last")

    keep = ["permno", "gvkey", "datadate", "fyear", "fy_end_year",
            "formation_june", "be", "op", "inv", "at"]
    out = f[keep].reset_index(drop=True)

    stats = {
        "funda_rows": n_funda,
        "linked_rows": n_linked,
        "final_rows": len(out),
        "n_permnos": int(out["permno"].nunique()),
        "with_book_equity": int(out["be"].notna().sum()),
        "with_profitability": int(out["op"].notna().sum()),
        "with_investment": int(out["inv"].notna().sum()),
        "year_min": int(out["fy_end_year"].min()),
        "year_max": int(out["fy_end_year"].max()),
    }

    if save:
        os.makedirs(PROCESSED, exist_ok=True)
        out.to_parquet(os.path.join(PROCESSED, "fundamentals.parquet"), index=False)
    return out, stats


def assign_formation_june(dates):
    """Map each month to the June portfolio-formation date governing it.

    July of year Y through June of Y+1 are all governed by the June Y sort.
    """
    dates = pd.DatetimeIndex(dates)
    year = np.where(dates.month >= 7, dates.year, dates.year - 1)
    return pd.to_datetime(pd.Series(year, index=range(len(dates))).astype(str) + "-06-30").values
