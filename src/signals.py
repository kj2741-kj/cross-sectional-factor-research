#!/usr/bin/env python
# coding: utf-8
"""
P2: build the monthly cross-sectional signal panel.

Six signals, all standard and all computable from monthly data:

  size     market equity at June of the formation year
  value    book equity / December market equity
  mom      cumulative return months t-12 to t-2
  prof     operating profitability
  inv      asset growth
  rev      prior-month return (short-term reversal)

Idiosyncratic volatility was in the original scope but is normally estimated
from daily returns within the month (Ang et al. 2006). Estimating it from
monthly data over a multi-year window measures something materially different
and would not be comparable to the published factor. Short-term reversal
(Jegadeesh 1990) is substituted: equally canonical, and honestly computable from
the data actually in hand.

The momentum gap matters. Skipping month t-1 avoids contaminating the momentum
signal with short-term reversal, which is a distinct and opposite-signed effect.
Measuring t-12 to t-1 blends the two and weakens both.
"""
import os

import numpy as np
import pandas as pd

PROCESSED = os.path.join(os.path.dirname(__file__), "..", "data", "processed")

SIGNALS = ["size", "value", "mom", "prof", "inv", "rev"]

# Sign convention: +1 means a high signal value is the expected-high-return leg.
# Size and investment are inverted because small firms and low-investment firms
# are the documented winners, so the long leg is the BOTTOM decile.
SIGNAL_DIRECTION = {"size": -1, "value": +1, "mom": +1,
                    "prof": +1, "inv": -1, "rev": -1}

SIGNAL_LABELS = {
    "size": "Size (small minus big)",
    "value": "Value (high minus low B/M)",
    "mom": "Momentum (12-2)",
    "prof": "Profitability (robust minus weak)",
    "inv": "Investment (conservative minus aggressive)",
    "rev": "Short-term reversal",
}


def compute_past_return_signals(panel):
    """Momentum (t-12 to t-2) and short-term reversal (t-1).

    Computed in log space so the 11-month compounding is a rolling sum, then
    converted back. `min_periods=11` refuses to produce a momentum score from a
    partial history rather than quietly ranking a six-month-old listing against
    a full-history one.
    """
    p = panel.sort_values(["permno", "date"]).copy()
    p["logret"] = np.log1p(p["ret_adj"])

    g = p.groupby("permno")["logret"]
    # Sum of log returns over the 11 months ending at t-2.
    roll11 = g.transform(lambda s: s.rolling(11, min_periods=11).sum())
    p["mom"] = np.expm1(roll11.groupby(p["permno"]).shift(2))

    p["rev"] = p.groupby("permno")["ret_adj"].shift(1)
    return p.drop(columns=["logret"])


def attach_formation_data(panel, fundamentals):
    """Merge June-formation fundamentals and the two market-equity snapshots.

    Every month from July of year Y to June of Y+1 uses the same June Y sort.
    Rebalancing more often than annually on annual fundamentals would only be
    re-sorting on stale numbers.
    """
    p = panel.copy()
    year = np.where(p["date"].dt.month >= 7, p["date"].dt.year, p["date"].dt.year - 1)
    p["formation_year"] = year
    p["formation_june"] = pd.to_datetime(pd.Series(year, index=p.index).astype(str) + "-06-30")

    # June market equity, the size signal and the value-weighting base.
    june = p[p["date"].dt.month == 6][["permno", "date", "me"]].copy()
    june["formation_year"] = june["date"].dt.year
    june = june.rename(columns={"me": "me_june"}).drop(columns=["date"])
    p = p.merge(june, on=["permno", "formation_year"], how="left")

    # December market equity of the prior calendar year, the book-to-market
    # denominator. A common date across firms with different fiscal year ends.
    dec = p[p["date"].dt.month == 12][["permno", "date", "me"]].copy()
    dec["formation_year"] = dec["date"].dt.year + 1
    dec = dec.rename(columns={"me": "me_dec"}).drop(columns=["date"])
    p = p.merge(dec, on=["permno", "formation_year"], how="left")

    f = fundamentals[["permno", "formation_june", "be", "op", "inv"]].rename(
        columns={"op": "prof"})
    p = p.merge(f, on=["permno", "formation_june"], how="left")
    return p


def build_signal_panel(processed_dir=None, save=True):
    """Run P2 and return the monthly panel with all six signals."""
    processed_dir = processed_dir or PROCESSED
    uni = pd.read_parquet(os.path.join(processed_dir, "universe.parquet"))
    fund = pd.read_parquet(os.path.join(processed_dir, "fundamentals.parquet"))

    # Signals and weights are defined at company level, so only primary permnos
    # carry market equity and only they are ranked.
    uni = uni[uni["is_primary"]].copy()

    p = compute_past_return_signals(uni)
    p = attach_formation_data(p, fund)

    p["size"] = p["me_june"]
    p["value"] = p["be"] / p["me_dec"]
    # Book-to-market is undefined without a positive denominator.
    p.loc[~(p["me_dec"] > 0), "value"] = np.nan

    keep = ["permno", "date", "ret_adj", "me", "me_june", "exchcd", "siccd",
            "formation_year"] + SIGNALS
    out = p[keep].sort_values(["date", "permno"]).reset_index(drop=True)

    stats = {"rows": len(out), "n_permnos": int(out["permno"].nunique())}
    for s in SIGNALS:
        stats[f"coverage_{s}"] = float(out[s].notna().mean())

    if save:
        os.makedirs(processed_dir, exist_ok=True)
        out.to_parquet(os.path.join(processed_dir, "signals.parquet"), index=False)
    return out, stats
