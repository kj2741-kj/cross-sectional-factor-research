#!/usr/bin/env python
# coding: utf-8
"""
Transaction costs: actual turnover, a time-varying cost schedule, and net returns.

Every result up to this point is gross. That matters more here than it usually
does, because the literature's central finding on dynamic factor strategies is
that predictability exists gross and disappears net (Dichtl et al. 2019), and
because the largest gross premium in this study is short-term reversal, which
has the highest turnover of any signal tested.

Three things have to be right for a net number to mean anything.

**Turnover must be measured, not assumed.** It is computed from the actual
month-to-month holdings, after drifting the previous month's weights by their
own returns. Without the drift step, a buy-and-hold portfolio appears to trade
every month simply because its weights moved.

**Costs must vary over time.** NYSE commissions were fixed and high until May
1975, decimalisation arrived in 2001, and effective spreads have fallen by more
than an order of magnitude across this sample. A single constant applied to
1963-2024 is wrong at both ends: far too low early, far too high late.

**Costs must vary with size.** An equal-weighted decile is mostly microcaps and
is drastically more expensive to trade than a value-weighted one holding the
same names in proportion to their market caps. Applying one cost to both is what
makes equal-weighted anomalies look investable.

References
----------
Novy-Marx, R. and Velikov, M. (2016). "A Taxonomy of Anomalies and Their
    Trading Costs." Review of Financial Studies 29(1).
Frazzini, A., Israel, R. and Moskowitz, T. (2012). "Trading Costs of Asset
    Pricing Anomalies." SSRN 1912807.
Hasbrouck, J. (2009). "Trading Costs and Returns for US Equities." JF 64(3).
"""
import numpy as np
import pandas as pd

# One-way effective cost in basis points for a LARGE-CAP, value-weighted trade.
# Anchored on the structural breaks in US equity market microstructure rather
# than fitted: fixed commissions to 1975, negotiated commissions and eighths to
# the 1990s, sixteenths in 1997, decimalisation in 2001, then electronic
# competition.
COST_SCHEDULE_BPS = [
    (1963, 1975, 125.0),   # fixed NYSE commissions, wide eighths
    (1975, 1990, 70.0),    # negotiated commissions from May 1975
    (1990, 1997, 40.0),
    (1997, 2001, 25.0),    # sixteenths
    (2001, 2010, 12.0),    # decimalisation
    (2010, 2100, 6.0),
]

# Multipliers on the large-cap schedule. Equal weighting pushes the portfolio
# into microcaps, where effective spreads are several times wider; Novy-Marx and
# Velikov find small-cap costs an order of magnitude above large-cap.
WEIGHTING_MULTIPLIER = {"vw": 1.0, "ew": 3.5}

# Sector exposure is available through futures and large ETFs, which is the
# entire practical argument for trading factors at the sector level.
SECTOR_ETF_BPS = 4.0


def cost_bps(dates, weighting="vw", multiplier=None):
    """One-way cost in bps for each date."""
    d = pd.DatetimeIndex(dates)
    out = pd.Series(np.nan, index=d)
    for lo, hi, bps in COST_SCHEDULE_BPS:
        mask = (d.year >= lo) & (d.year < hi)
        out[mask] = bps
    out = out.ffill().bfill()
    mult = multiplier if multiplier is not None else WEIGHTING_MULTIPLIER.get(weighting, 1.0)
    return out * mult


def leg_turnover(panel, decile_col, decile_value, weight_col="me_lag",
                 ret_col="ret_adj", equal_weight=False):
    """One-way turnover per month for a single decile leg.

    turnover_t = 0.5 * sum_i |w_i,t - w_i,t-1_drifted|

    The drift term is what separates rebalancing from passive weight movement.
    """
    d = panel[(panel[decile_col] == decile_value)
              & panel[ret_col].notna()
              & (panel[weight_col] > 0)][["date", "permno", weight_col, ret_col]]
    if d.empty:
        return pd.Series(dtype=float)

    prev_w, prev_r = None, None
    rows = []
    for date, g in d.groupby("date", sort=True):
        if equal_weight:
            w = pd.Series(1.0 / len(g), index=g["permno"].values)
        else:
            w = pd.Series(g[weight_col].values, index=g["permno"].values)
            w = w / w.sum()
        r = pd.Series(g[ret_col].values, index=g["permno"].values)

        if prev_w is not None:
            drifted = prev_w * (1.0 + prev_r)
            s = drifted.sum()
            drifted = drifted / s if s > 0 else drifted
            idx = w.index.union(drifted.index)
            to = 0.5 * (w.reindex(idx).fillna(0.0)
                        - drifted.reindex(idx).fillna(0.0)).abs().sum()
            rows.append((date, float(to)))
        prev_w, prev_r = w, r

    return pd.Series(dict(rows)).sort_index()


def strategy_turnover(panel, decile_col, weighting="vw", long_decile=10,
                      short_decile=1):
    """Combined one-way turnover of both legs of a long-short strategy."""
    ew = weighting == "ew"
    tl = leg_turnover(panel, decile_col, long_decile, equal_weight=ew)
    ts = leg_turnover(panel, decile_col, short_decile, equal_weight=ew)
    idx = tl.index.union(ts.index)
    return tl.reindex(idx).fillna(0.0) + ts.reindex(idx).fillna(0.0)


def rank_strategy_turnover(scores, ind_rets, n_side=3, direction=1):
    """Turnover for the sector rank strategy, both legs, equally weighted."""
    s = (scores * direction).reindex(ind_rets.index)
    prev = None
    rows = []
    for d in s.index:
        row = s.loc[d].dropna()
        if len(row) < 2 * n_side:
            continue
        order = row.sort_values(ascending=False)
        cur = {"long": set(order.index[:n_side]), "short": set(order.index[-n_side:])}
        if prev is not None:
            # Equal-weighted legs, so turnover is the share of names replaced.
            tl = len(cur["long"] - prev["long"]) / n_side
            ts = len(cur["short"] - prev["short"]) / n_side
            rows.append((d, float(tl + ts)))
        prev = cur
    return pd.Series(dict(rows)).sort_index()


def apply_costs(gross, turnover, weighting="vw", multiplier=None):
    """Net a gross return series for measured turnover at the scheduled cost."""
    g = pd.Series(gross).dropna()
    t = pd.Series(turnover).reindex(g.index).fillna(0.0)
    c = cost_bps(g.index, weighting=weighting, multiplier=multiplier) / 1e4
    cost = t * c
    return pd.DataFrame({"gross": g, "turnover": t,
                         "cost_bps": c * 1e4, "cost": cost,
                         "net": g - cost})


def breakeven_cost_bps(gross, turnover):
    """One-way cost in bps at which the strategy's mean return reaches zero.

    More informative than a single net number: it says how wrong the cost
    assumption would have to be to change the conclusion.
    """
    g = pd.Series(gross).dropna()
    t = pd.Series(turnover).reindex(g.index).fillna(0.0)
    mt = t.mean()
    return float(g.mean() / mt * 1e4) if mt > 0 else np.inf
