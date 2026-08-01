#!/usr/bin/env python
# coding: utf-8
"""
P3: decile portfolio formation and long-short return series.

Three construction choices here decide whether the resulting spreads are real.

**NYSE breakpoints.** Decile cutoffs are computed on NYSE-listed stocks only,
then applied to the whole universe. Full-universe quantiles put the thousands of
AMEX/NASDAQ microcaps into the extreme deciles and manufacture spreads that no
one could trade. With NYSE breakpoints the extreme deciles hold far fewer, far
larger names, which is the honest picture.

**Rebalancing frequency follows the signal.** Annual fundamentals (size, value,
profitability, investment) are sorted once in June and held twelve months, per
Fama-French. Re-sorting those monthly would just be re-ranking stale numbers.
Momentum and reversal are re-sorted every month because their inputs change
every month.

**Value weights use lagged market equity.** Weighting by contemporaneous market
equity uses the month's own return to set the weight it is being applied to,
which is look-ahead and inflates measured performance.

Both value- and equal-weighted results are produced, because the gap between
them is the microcap-dependence diagnostic: a premium that exists only
equal-weighted is a premium concentrated in stocks too small to hold.
"""
import numpy as np
import pandas as pd

from signals import SIGNALS, SIGNAL_DIRECTION

N_DECILES = 10
ANNUAL_SIGNALS = ("size", "value", "prof", "inv")   # June sort, held 12 months
MONTHLY_SIGNALS = ("mom", "rev")                     # re-sorted every month

NYSE = 1


def _decile_from_nyse_breakpoints(values, is_nyse, n=N_DECILES):
    """Assign deciles using cutoffs computed on NYSE stocks only."""
    v = np.asarray(values, dtype=float)
    ref = v[is_nyse & np.isfinite(v)]
    out = np.full(v.shape, np.nan)
    if ref.size < n:
        return out  # too few NYSE names to define cutoffs
    edges = np.quantile(ref, np.linspace(0, 1, n + 1)[1:-1])
    finite = np.isfinite(v)
    out[finite] = np.searchsorted(edges, v[finite], side="right") + 1
    return out


def assign_deciles(panel, signal):
    """Return a Series of decile assignments aligned to `panel`."""
    annual = signal in ANNUAL_SIGNALS
    df = panel[["permno", "date", "formation_year", "exchcd", signal]].copy()

    if annual:
        # Rank once, in June, on the June cross-section.
        june = df[df["date"].dt.month == 6].copy()
        parts = []
        for d, grp in june.groupby("date", sort=False):
            dec = _decile_from_nyse_breakpoints(
                grp[signal].values, (grp["exchcd"] == NYSE).values)
            parts.append(pd.DataFrame({
                "permno": grp["permno"].values,
                "formation_year": grp["formation_year"].values,
                "decile": dec}))
        if not parts:
            return pd.Series(np.nan, index=panel.index)
        assign = pd.concat(parts, ignore_index=True).dropna(subset=["decile"])
        merged = df.merge(assign, on=["permno", "formation_year"], how="left")
        return pd.Series(merged["decile"].values, index=panel.index)

    parts = np.full(len(df), np.nan)
    pos = 0
    for d, grp in df.groupby("date", sort=False):
        dec = _decile_from_nyse_breakpoints(
            grp[signal].values, (grp["exchcd"] == NYSE).values)
        parts[pos:pos + len(grp)] = dec
        pos += len(grp)
    # groupby preserves order within groups only if the frame is date-sorted.
    df = df.assign(decile=parts)
    return pd.Series(df["decile"].values, index=panel.index)


def add_lagged_weights(panel):
    """Market equity at the end of the prior month, for value weighting."""
    p = panel.sort_values(["permno", "date"]).copy()
    p["me_lag"] = p.groupby("permno")["me"].shift(1)
    return p.sort_values(["date", "permno"])


def decile_returns(panel, decile_col, ret_col="ret_adj"):
    """Value- and equal-weighted returns for each decile, by month."""
    d = panel[panel[decile_col].notna() & panel[ret_col].notna()].copy()
    d = d[d["me_lag"] > 0]

    d["wr"] = d[ret_col] * d["me_lag"]
    g = d.groupby(["date", decile_col])
    out = g.agg(vw_num=("wr", "sum"), vw_den=("me_lag", "sum"),
                ew=(ret_col, "mean"), n=(ret_col, "size")).reset_index()
    out["vw"] = out["vw_num"] / out["vw_den"]
    return out.drop(columns=["vw_num", "vw_den"]).rename(
        columns={decile_col: "decile"})


def long_short_series(dec_ret, direction):
    """High-minus-low spread, oriented so a positive number is the documented bet.

    `direction = -1` flips the legs, because for size and investment the
    documented winners are the BOTTOM decile (small firms, conservative
    investors), so the long leg is decile 1.
    """
    piv_vw = dec_ret.pivot(index="date", columns="decile", values="vw")
    piv_ew = dec_ret.pivot(index="date", columns="decile", values="ew")
    piv_n = dec_ret.pivot(index="date", columns="decile", values="n")

    hi, lo = (N_DECILES, 1) if direction > 0 else (1, N_DECILES)
    return pd.DataFrame({
        "vw": piv_vw[hi] - piv_vw[lo],
        "ew": piv_ew[hi] - piv_ew[lo],
        "long_vw": piv_vw[hi], "short_vw": piv_vw[lo],
        "n_long": piv_n[hi], "n_short": piv_n[lo],
    })


def build_all_portfolios(panel, signals=SIGNALS):
    """Run P3 for every signal.

    Returns (long_short dict, decile_returns dict).
    """
    panel = add_lagged_weights(panel)
    ls, decs = {}, {}
    for s in signals:
        dcol = f"decile_{s}"
        panel[dcol] = assign_deciles(panel, s)
        dr = decile_returns(panel, dcol)
        decs[s] = dr
        ls[s] = long_short_series(dr, SIGNAL_DIRECTION[s])
    return ls, decs
