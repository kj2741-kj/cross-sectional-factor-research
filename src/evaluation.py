#!/usr/bin/env python
# coding: utf-8
"""
P4: statistical evaluation of the long-short series.

The single most common failure in factor replication is declaring victory on a
t-stat of 2.1 from an OLS regression on autocorrelated monthly returns, chosen
from a menu of signals that were all tested. Three corrections apply here.

**Newey-West standard errors.** Monthly long-short returns are autocorrelated
and heteroskedastic. Plain OLS standard errors are too small, so plain t-stats
are too big. Lag length follows Newey-West's own automatic rule.

**Benchmark alpha, not raw mean.** A raw premium that is entirely explained by
market, size and value exposure is not a new finding. Alphas are reported
against FF3 and FF5, so a signal has to earn its place beyond the factors it
might just be re-expressing.

**A multiple-testing hurdle.** Six signals are tested at once. Harvey, Liu and
Zhu (2016) argue that with the volume of factor research already published, a
new factor needs t > 3.0 rather than 2.0. Benjamini-Hochberg FDR is reported
alongside, because the two answer different questions: the HLZ hurdle asks
whether this would survive as a new discovery, FDR asks what share of the
signals called significant here are likely false.

References
----------
Newey, W. and West, K. (1987). Econometrica 55(3).
Harvey, C., Liu, Y. and Zhu, H. (2016). Review of Financial Studies 29(1).
Benjamini, Y. and Hochberg, Y. (1995). JRSS-B 57(1).
Fama, E. and MacBeth, J. (1973). Journal of Political Economy 81(3).
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

HLZ_HURDLE = 3.0   # Harvey-Liu-Zhu t-statistic threshold for a new factor


def nw_lags(n):
    """Newey-West automatic lag selection, floor(4 * (n/100)^(2/9))."""
    return int(np.floor(4 * (n / 100.0) ** (2.0 / 9.0)))


def mean_with_nw(series):
    """Mean return and its Newey-West t-statistic.

    Implemented as a regression on a constant, which is what makes the
    autocorrelation correction apply to the mean itself.
    """
    y = pd.Series(series).dropna()
    n = len(y)
    if n < 12:
        return {"mean": np.nan, "t_nw": np.nan, "t_ols": np.nan, "n": n}
    X = np.ones((n, 1))
    res = sm.OLS(y.values, X).fit(cov_type="HAC",
                                  cov_kwds={"maxlags": nw_lags(n)})
    ols = sm.OLS(y.values, X).fit()
    return {"mean": float(res.params[0]), "t_nw": float(res.tvalues[0]),
            "t_ols": float(ols.tvalues[0]), "n": n}


def alpha_vs_benchmark(series, factors):
    """Newey-West alpha of a long-short series against a factor benchmark."""
    y = pd.Series(series).dropna()
    idx = y.index.intersection(factors.index)
    if len(idx) < 24:
        return {"alpha": np.nan, "t_alpha": np.nan, "n": len(idx)}
    yy = y.loc[idx]
    X = sm.add_constant(factors.loc[idx].astype(float))
    res = sm.OLS(yy.values, X.values).fit(
        cov_type="HAC", cov_kwds={"maxlags": nw_lags(len(idx))})
    out = {"alpha": float(res.params[0]), "t_alpha": float(res.tvalues[0]),
           "n": len(idx), "r2": float(res.rsquared)}
    for i, c in enumerate(factors.columns, start=1):
        out[f"beta_{c}"] = float(res.params[i])
    return out


def benjamini_hochberg(pvalues, q=0.05):
    """BH step-up procedure. Returns (rejected mask, critical p-value)."""
    p = np.asarray(pvalues, dtype=float)
    ok = np.isfinite(p)
    m = ok.sum()
    if m == 0:
        return np.zeros_like(p, dtype=bool), np.nan
    order = np.argsort(np.where(ok, p, np.inf))
    ranked = p[order][:m]
    thresholds = q * np.arange(1, m + 1) / m
    passing = ranked <= thresholds
    if not passing.any():
        return np.zeros_like(p, dtype=bool), 0.0
    k = np.max(np.where(passing)[0])
    crit = ranked[k]
    return (p <= crit) & ok, float(crit)


def evaluate_signals(long_short, factors_ff3, factors_ff5, weighting="vw",
                     label=""):
    """Full evaluation table across signals, with multiple-testing correction."""
    rows = {}
    for s, df in long_short.items():
        series = df[weighting]
        r = mean_with_nw(series)
        a3 = alpha_vs_benchmark(series, factors_ff3)
        a5 = alpha_vs_benchmark(series, factors_ff5)
        rows[s] = {
            "mean_pct": r["mean"] * 100,
            "t_ols": r["t_ols"],
            "t_nw": r["t_nw"],
            "ann_pct": r["mean"] * 12 * 100,
            "sharpe": (series.mean() / series.std() * np.sqrt(12)
                       if series.std() > 0 else np.nan),
            "alpha_ff3_pct": a3["alpha"] * 100,
            "t_alpha_ff3": a3["t_alpha"],
            "alpha_ff5_pct": a5["alpha"] * 100,
            "t_alpha_ff5": a5["t_alpha"],
            "n_months": r["n"],
        }
    out = pd.DataFrame(rows).T

    # Two-sided p-values from the Newey-West t-stats, then the corrections.
    out["p_nw"] = 2 * (1 - stats.norm.cdf(out["t_nw"].abs()))
    rejected, crit = benjamini_hochberg(out["p_nw"].values, q=0.05)
    out["survives_bh_fdr"] = rejected
    out["survives_hlz_t3"] = out["t_nw"].abs() > HLZ_HURDLE
    out["survives_naive_t2"] = out["t_nw"].abs() > 2.0
    out.attrs["bh_critical_p"] = crit
    out.attrs["label"] = label
    out.attrs["weighting"] = weighting
    return out


def fama_macbeth(panel, signals, ret_col="ret_adj", winsorize=0.01):
    """Fama-MacBeth cross-sectional regressions of returns on standardised signals.

    Signals are cross-sectionally standardised each month, so coefficients are
    comparable across signals and expressed per standard deviation of exposure.

    Winsorising is not cosmetic here. Compustat asset growth reaches 1e7 from
    near-zero denominators, and a single such observation would otherwise
    dominate an entire month's cross-sectional slope.
    """
    p = panel[["date", ret_col] + list(signals)].dropna(subset=[ret_col]).copy()

    def prep(g):
        for s in signals:
            v = g[s]
            if winsorize:
                lo, hi = v.quantile(winsorize), v.quantile(1 - winsorize)
                v = v.clip(lo, hi)
            sd = v.std()
            g[s] = (v - v.mean()) / sd if sd and np.isfinite(sd) and sd > 0 else np.nan
        return g

    p = p.groupby("date", group_keys=False).apply(prep)

    coefs = []
    for d, g in p.groupby("date"):
        g = g.dropna(subset=list(signals) + [ret_col])
        if len(g) < 30:
            continue
        X = sm.add_constant(g[list(signals)].values)
        res = sm.OLS(g[ret_col].values, X).fit()
        coefs.append([d] + list(res.params))

    cols = ["date", "intercept"] + list(signals)
    fm = pd.DataFrame(coefs, columns=cols).set_index("date")

    summary = {}
    for c in ["intercept"] + list(signals):
        r = mean_with_nw(fm[c])
        summary[c] = {"coef_pct": r["mean"] * 100, "t_nw": r["t_nw"],
                      "n_months": r["n"]}
    return fm, pd.DataFrame(summary).T
