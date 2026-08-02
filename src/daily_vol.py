#!/usr/bin/env python
# coding: utf-8
"""
Total and idiosyncratic volatility, built exactly as Ang, Hodrick, Xing and
Zhang (2006, JF) specify: from daily returns within a single calendar month.

This replaces the monthly-window proxy used earlier in the project
(src/signals.py's original `lowvol`/`ivol`), which was validated against
Chen-Zimmermann's reference series and found to correlate only 0.32-0.81 with
the real signal, with the wrong sign of mean return on `ivol`. See
docs/VALIDATION.md.

The construction is one OLS per (permno, month): regress that stock's daily
returns on the daily factors, take the residual standard deviation. Run
naively that is ~3.4 million small regressions. It is instead vectorized per
month, which is the one place a closed form is available: every stock trading
in a given month shares the same daily factor observations, so the design
matrix X is identical across stocks that month and only y (returns) varies.

    beta   = (X'X)^-1 X'Y          one (k x k) solve per month, not per stock
    resid  = Y - X @ beta
    idio   = std(resid, axis=0)

X'X is a k x k matrix (k = 1 for CAPM, 3 for FF3) computed once per month.
X'Y is computed for all stocks at once via a single matrix multiplication.
This turns 3.4 million regressions into roughly 750 small linear solves plus
750 matrix multiplications, which is the difference between a computation that
finishes in seconds and one that does not finish at all.

Stocks with any missing daily return within the month are dropped for that
month rather than estimated on a ragged subset, which would break the shared-X
assumption. Ang et al. require at least 15 valid daily observations; the same
floor is applied here before a stock enters the shared-X block.

Reference
---------
Ang, A., Hodrick, R., Xing, Y. and Zhang, X. (2006). "The Cross-Section of
    Volatility and Expected Returns." Journal of Finance 61(1), 259-299.
"""
import glob
import os

import numpy as np
import pandas as pd

MIN_DAYS = 15


def load_daily_returns(raw_dir):
    """Concatenate the year-block parquet files from pull_crsp_daily.py."""
    files = sorted(glob.glob(os.path.join(raw_dir, "dsf_*.parquet")))
    if not files:
        raise FileNotFoundError(
            f"No daily CRSP files in {raw_dir}. Run: python scripts/pull_crsp_daily.py")
    parts = [pd.read_parquet(f) for f in files]
    df = pd.concat(parts, ignore_index=True)
    df["ret"] = pd.to_numeric(df["ret"], errors="coerce")
    return df.dropna(subset=["ret"])


def _month_key(dates):
    return dates.values.astype("datetime64[M]")


def compute_monthly_volatility(daily, daily_factors, min_days=MIN_DAYS):
    """Total and factor-residual volatility per permno per month.

    Parameters
    ----------
    daily : DataFrame with columns permno, date, ret
    daily_factors : DataFrame indexed by date, containing at minimum 'Mkt-RF'
        and optionally 'SMB', 'HML' for the three-factor version. RF should
        already be removed (pass an excess-return factor frame).

    Returns
    -------
    DataFrame indexed by (permno, month-end date) with columns:
        total_vol, idio_vol_capm, idio_vol_ff3, n_days
    All are monthly (not annualised) standard deviations of daily residuals.
    """
    d = daily.merge(daily_factors, left_on="date", right_index=True, how="inner")
    d["month"] = _month_key(d["date"])

    factor_cols_1f = ["Mkt-RF"]
    factor_cols_3f = ["Mkt-RF", "SMB", "HML"] if "SMB" in d.columns else None

    results = []
    for month, g in d.groupby("month", sort=True):
        # Total volatility needs no factor alignment at all.
        piv_ret = g.pivot_table(index="date", columns="permno", values="ret")
        n_days = piv_ret.notna().sum()
        eligible = n_days[n_days >= min_days].index
        if len(eligible) == 0:
            continue

        # Stocks with a full, gap-free month share one design matrix and are
        # handled by the closed-form block. A stock missing even one day
        # inside an otherwise-eligible month is dropped from that month rather
        # than patched, so the shared-X assumption is never silently violated.
        full = piv_ret[eligible].dropna(axis=1, how="any")
        Y = full.values
        dates = full.index
        stocks = full.columns

        fac = g[["date"] + factor_cols_1f + (factor_cols_3f or [])].drop_duplicates("date")
        fac = fac.set_index("date").reindex(dates)
        if fac.isna().any().any():
            continue  # a factor missing on a day this stock traded; skip the month

        total_vol = pd.Series(Y.std(axis=0, ddof=1), index=stocks)

        def resid_std(cols):
            X = np.column_stack([np.ones(len(dates)), fac[cols].values])
            XtX_inv = np.linalg.pinv(X.T @ X)
            beta = XtX_inv @ (X.T @ Y)          # (k+1) x n_stocks
            fitted = X @ beta
            resid = Y - fitted
            return pd.Series(resid.std(axis=0, ddof=X.shape[1]), index=stocks)

        idio_capm = resid_std(factor_cols_1f)
        idio_ff3 = resid_std(factor_cols_3f) if factor_cols_3f else pd.Series(np.nan, index=stocks)

        results.append(pd.DataFrame({
            "permno": stocks, "month": month,
            "total_vol": total_vol.values,
            "idio_vol_capm": idio_capm.values,
            "idio_vol_ff3": idio_ff3.values,
            "n_days": n_days.reindex(stocks).values,
        }))

    out = pd.concat(results, ignore_index=True)
    out["month_end"] = pd.to_datetime(out["month"]) + pd.offsets.MonthEnd(0)
    return out.drop(columns=["month"])


def attach_lagged_volatility(panel, vol_monthly):
    """Merge the volatility estimate ending in month t onto returns of month t+1.

    Ang et al. sort at the start of month t+1 on volatility measured over
    month t, so the signal is shifted forward one month before merging. This
    is the same "no look-ahead" discipline as every other signal in the study.
    """
    v = vol_monthly.copy()
    v["signal_month_end"] = (v["month_end"] + pd.offsets.MonthEnd(1))
    v = v.rename(columns={
        "total_vol": "lowvol_daily", "idio_vol_capm": "ivol_capm_daily",
        "idio_vol_ff3": "ivol_ff3_daily",
    })
    p = panel.copy()
    p["month_end"] = pd.to_datetime(p["date"]) + pd.offsets.MonthEnd(0)
    out = p.merge(
        v[["permno", "signal_month_end", "lowvol_daily", "ivol_capm_daily", "ivol_ff3_daily"]],
        left_on=["permno", "month_end"], right_on=["permno", "signal_month_end"], how="left",
    )
    return out.drop(columns=["month_end", "signal_month_end"])
