#!/usr/bin/env python
# coding: utf-8
"""
Industry-level factor portfolios, and the Moskowitz-Grinblatt decomposition.

Two distinct questions live here.

**Does individual-stock momentum survive industry neutralisation?**
Moskowitz and Grinblatt (1999) argued that individual momentum is really
industry momentum: winners cluster in sectors that have been rising, so buying
past winners is largely buying hot sectors. Grundy and Martin (2001) disputed
it. The decisive comparison is pooled momentum against within-industry momentum
against pure industry momentum, on the same sample.

**Can industries themselves be ranked and traded?**
A sector strategy is far more tradeable than a 3,000-name long-short: sector
exposure is available in size at low cost, which is exactly the transaction-cost
objection that weighs against the stock-level results. The cost is statistical
power. Twelve industries ranked into thirds is three bets, not a thousand, and
they are all long equity, so the cross-sectional dispersion available is a
fraction of what the stock-level sorts have.

A note on sector value. Cross-sectional book-to-market across industries is
mostly a structural constant: banks are always cheap on book, software is always
expensive, and neither fact is a signal. A cross-sectional sector value sort is
therefore a permanent long-banks position wearing a factor's clothing. Sector
value has to be measured against each industry's OWN history, which is what
`time_series_zscore` does.

References
----------
Moskowitz, T. and Grinblatt, M. (1999). "Do Industries Explain Momentum?"
    Journal of Finance 54(4).
Grundy, B. and Martin, J. (2001). Review of Financial Studies 14(1).
Asness, C., Porter, R. and Stevens, R. (2000). SSRN 213872.
"""
import numpy as np
import pandas as pd

from industry import sic_to_ff12


def industry_portfolios(panel, ind_col="ind", ret_col="ret_adj",
                        weight_col="me_lag"):
    """Value-weighted monthly return for each industry."""
    d = panel[panel[ret_col].notna() & (panel[weight_col] > 0)].copy()
    d = d[d[ind_col].notna()]
    d["wr"] = d[ret_col] * d[weight_col]
    g = d.groupby(["date", ind_col])
    out = g.agg(num=("wr", "sum"), den=(weight_col, "sum"), n=(ret_col, "size"))
    out["ret"] = out["num"] / out["den"]
    return out["ret"].unstack(ind_col)


def industry_characteristic(panel, char, ind_col="ind", weight_col="me_lag"):
    """Value-weighted average of a firm characteristic within each industry."""
    d = panel[panel[char].notna() & (panel[weight_col] > 0)].copy()
    d = d[d[ind_col].notna()]
    d["wc"] = d[char] * d[weight_col]
    g = d.groupby(["date", ind_col])
    out = g.agg(num=("wc", "sum"), den=(weight_col, "sum"))
    return (out["num"] / out["den"]).unstack(ind_col)


def industry_momentum(ind_rets, lookback=12, skip=1):
    """Past 12-2 cumulative return per industry, strictly backward-looking."""
    lr = np.log1p(ind_rets)
    roll = lr.rolling(lookback - skip, min_periods=lookback - skip).sum()
    return np.expm1(roll.shift(1 + skip))


def time_series_zscore(df, window=120, min_periods=60):
    """Standardise each column against its own trailing history.

    The point of contrast with a cross-sectional z-score: this asks "is this
    industry cheap *for itself*", which is a signal, rather than "is this
    industry cheap relative to other industries", which is mostly a statement
    about what business it is in.
    """
    mu = df.rolling(window, min_periods=min_periods).mean().shift(1)
    sd = df.rolling(window, min_periods=min_periods).std().shift(1)
    return (df.shift(1) - mu) / sd.where(sd > 0)


def rank_long_short(scores, ind_rets, n_side=3, direction=1):
    """Rank industries on a score each month and go long the top, short the bottom.

    Scores must already be lagged. Returns the spread plus each leg, so a
    strategy that only works because of its short leg is visible as such.
    """
    s = (scores * direction).reindex(ind_rets.index)
    rows = []
    for d in s.index:
        row = s.loc[d].dropna()
        if len(row) < 2 * n_side:
            continue
        order = row.sort_values(ascending=False)
        longs, shorts = order.index[:n_side], order.index[-n_side:]
        r = ind_rets.loc[d]
        if r[longs].isna().any() or r[shorts].isna().any():
            continue
        rows.append({"date": d, "long": r[longs].mean(),
                     "short": r[shorts].mean(),
                     "ls": r[longs].mean() - r[shorts].mean()})
    return pd.DataFrame(rows).set_index("date")


def prepare_panel(signals_path, add_industry=True):
    """Load the signal panel with industry labels and lagged weights attached."""
    from portfolios import add_lagged_weights
    p = pd.read_parquet(signals_path)
    if add_industry:
        p["ind"] = sic_to_ff12(p["siccd"])
    return add_lagged_weights(p)
