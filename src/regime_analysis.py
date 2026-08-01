#!/usr/bin/env python
# coding: utf-8
"""
P6/P7: regime-conditional factor premia, momentum crashes, and a timing strategy.

P6 asks whether factor premia differ across market regimes, and replicates the
Daniel-Moskowitz momentum-crash result as the benchmark the HMM must beat.

P7 asks the harder question: can a regime signal be used *ex ante* to improve a
factor strategy. In-sample regime labels make this trivially easy and completely
meaningless, so the strategy is evaluated only on out-of-sample labels from an
expanding-window fit.
"""
import numpy as np
import pandas as pd

from evaluation import mean_with_nw


def conditional_premia(long_short, regime, weighting="vw", regime_name="regime"):
    """Mean long-short return within each regime state, with Newey-West t-stats."""
    r = pd.Series(regime).dropna()
    rows = []
    for signal, df in long_short.items():
        s = df[weighting].dropna()
        idx = s.index.intersection(r.index)
        if len(idx) < 24:
            continue
        ss, rr = s.loc[idx], r.loc[idx]
        rec = {"signal": signal}
        for state in sorted(rr.unique()):
            sub = ss[rr == state]
            st = mean_with_nw(sub)
            rec[f"state{int(state)}_mean%"] = st["mean"] * 100
            rec[f"state{int(state)}_t"] = st["t_nw"]
            rec[f"state{int(state)}_n"] = st["n"]
        states = sorted(rr.unique())
        if len(states) == 2:
            hi, lo = ss[rr == states[1]], ss[rr == states[0]]
            rec["spread%"] = (hi.mean() - lo.mean()) * 100
            # Welch t-test: the two regimes have very different variances, so
            # the equal-variance version would overstate significance.
            n1, n2 = len(hi), len(lo)
            if n1 > 1 and n2 > 1:
                se = np.sqrt(hi.var(ddof=1) / n1 + lo.var(ddof=1) / n2)
                rec["spread_t"] = (hi.mean() - lo.mean()) / se if se > 0 else np.nan
        rows.append(rec)
    return pd.DataFrame(rows).set_index("signal")


def momentum_crash_analysis(mom_series, dm, mkt):
    """Replicate the Daniel-Moskowitz crash decomposition.

    Their result is not that momentum does badly in bear markets generally. It
    is specifically that momentum collapses when a bear market *rebounds*: the
    short leg is full of beaten-down high-beta names that snap back hardest.
    The interaction of the bear flag with a contemporaneous up-market is
    therefore the state that matters, not the bear flag alone.
    """
    idx = mom_series.dropna().index.intersection(dm.index).intersection(mkt.index)
    m = mom_series.loc[idx]
    bear = dm.loc[idx, "bear"].astype(bool)
    panic = dm.loc[idx, "panic"].astype(bool)
    up = mkt.loc[idx] > 0

    def block(mask, label):
        sub = m[mask]
        st = mean_with_nw(sub)
        return {"state": label, "n": int(mask.sum()), "mean%": st["mean"] * 100,
                "t_nw": st["t_nw"],
                "ann%": st["mean"] * 12 * 100 if np.isfinite(st["mean"]) else np.nan,
                "worst%": sub.min() * 100 if len(sub) else np.nan}

    rows = [
        block(~bear, "Non-bear"),
        block(bear, "Bear (all)"),
        block(bear & up, "Bear + market UP (rebound)"),
        block(bear & ~up, "Bear + market DOWN"),
        block(panic & up, "Panic + market UP"),
    ]
    return pd.DataFrame(rows).set_index("state")


def regime_timed_strategy(signal_series, regime_oos, bad_state=0, mode="off"):
    """Switch a factor strategy off (or short) in the flagged bad regime.

    Only out-of-sample regime labels are accepted. Months before the label is
    available are held flat rather than being filled with a full position, so
    the comparison against buy-and-hold is on a common sample.

    Regime labels are lagged one month: a label derived from data through t-1
    can only be acted on at t.
    """
    s = pd.Series(signal_series).dropna()
    r = pd.Series(regime_oos).reindex(s.index).shift(1)

    exposure = pd.Series(np.where(r.isna(), np.nan,
                                  np.where(r == bad_state,
                                           0.0 if mode == "off" else -1.0, 1.0)),
                         index=s.index)
    valid = exposure.notna()
    out = pd.DataFrame({
        "raw": s[valid],
        "exposure": exposure[valid],
    })
    out["timed"] = out["raw"] * out["exposure"]
    return out


def strategy_stats(df, cols=("raw", "timed")):
    rows = {}
    for c in cols:
        x = df[c].dropna()
        st = mean_with_nw(x)
        cum = (1 + x).cumprod()
        dd = (cum / cum.cummax() - 1).min()
        rows[c] = {
            "mean%": st["mean"] * 100, "t_nw": st["t_nw"],
            "ann%": st["mean"] * 12 * 100,
            "ann_vol%": x.std() * np.sqrt(12) * 100,
            "sharpe": (x.mean() / x.std() * np.sqrt(12)) if x.std() > 0 else np.nan,
            "max_dd%": dd * 100,
            "worst_month%": x.min() * 100,
            "n": len(x),
        }
    return pd.DataFrame(rows).T
