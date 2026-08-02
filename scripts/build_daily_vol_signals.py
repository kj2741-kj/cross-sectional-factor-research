#!/usr/bin/env python
# coding: utf-8
"""
Build the correct Ang, Hodrick, Xing and Zhang (2006) volatility signals from
daily CRSP data, and evaluate them under the study's standard NYSE-breakpoint,
cost-adjusted methodology.

Requires scripts/pull_crsp_daily.py to have been run first.

    python scripts/build_daily_vol_signals.py
"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from daily_vol import load_daily_returns, compute_monthly_volatility, attach_lagged_volatility  # noqa: E402
from factors import load_ff_daily, benchmark_set  # noqa: E402
from portfolios import add_lagged_weights, assign_deciles, decile_returns, long_short_series  # noqa: E402
from costs import strategy_turnover, apply_costs  # noqa: E402
from evaluation import mean_with_nw, alpha_vs_benchmark, benjamini_hochberg, HLZ_HURDLE  # noqa: E402

PROC = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
RAW_DSF = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "dsf")

VOL_SIGNALS = {
    "lowvol_daily": "RealizedVol",     # CZ acronym for the matching reference series
    "ivol_capm_daily": "IdioVolCAPM",
    "ivol_ff3_daily": "IdioVol3F",
}


def main():
    print("loading daily CRSP returns ...")
    daily = load_daily_returns(RAW_DSF)
    daily.to_parquet(os.path.join(PROC, "daily_returns_combined.parquet"), index=False)
    print(f"  {len(daily):,} rows, {daily.permno.nunique():,} permnos")

    print("computing monthly volatility (vectorized per-month regression) ...")
    ff3_daily = load_ff_daily("ff3")[["Mkt-RF", "SMB", "HML"]]
    vol = compute_monthly_volatility(daily, ff3_daily)
    vol.to_parquet(os.path.join(PROC, "daily_volatility.parquet"), index=False)
    print(f"  {len(vol):,} permno-months")

    print("merging into signal panel ...")
    panel = pd.read_parquet(os.path.join(PROC, "signals.parquet"))
    panel = attach_lagged_volatility(panel, vol)
    panel = add_lagged_weights(panel)
    panel.to_parquet(os.path.join(PROC, "signals_with_daily_vol.parquet"), index=False)

    print("forming NYSE-breakpoint decile portfolios, monthly rebalance ...")
    net = {}
    for s in VOL_SIGNALS:
        col = f"d_{s}"
        panel[col] = assign_deciles(panel, s)
        dr = decile_returns(panel, col)
        ls = long_short_series(dr, -1)  # long low vol, short high vol
        for wt in ("vw", "ew"):
            turn = strategy_turnover(panel, col, weighting=wt, long_decile=1, short_decile=10)
            net[(s, wt)] = apply_costs(ls[wt], turn, weighting=wt)
    with open(os.path.join(PROC, "dailyvol_net.pkl"), "wb") as fh:
        pickle.dump(net, fh)

    print("\nvalidating against Chen-Zimmermann reference series ...")
    cz = pd.read_parquet(os.path.join(os.path.dirname(__file__), "..", "data", "cz",
                                      "deciles_vw.parquet"))
    ls_cz = cz[cz.port == "LS"].copy()
    ls_cz["date"] = pd.to_datetime(ls_cz["date"]) + pd.offsets.MonthEnd(0)
    CZ = ls_cz.pivot(index="date", columns="signalname", values="ret") / 100.0

    ff3, _ = benchmark_set("ff3")
    for s, cz_name in VOL_SIGNALS.items():
        if cz_name not in CZ.columns:
            continue
        a = net[(s, "vw")].gross.dropna()
        b = CZ[cz_name].dropna()
        idx = a.index.intersection(b.index)
        corr = a.loc[idx].corr(b.loc[idx])
        print(f"  {s:<18} vs {cz_name:<12} corr(gross, NYSE) = {corr:.2f}")

    print("\nfinal panel, NET, VW, NYSE breakpoints, value-weighted:")
    for tag, lo in [("full sample", "1963-01-01"), ("post-2003", "2003-01-01")]:
        print(f"  --- {tag} ---")
        for s in VOL_SIGNALS:
            r = net[(s, "vw")].net.dropna()
            r = r[r.index >= pd.Timestamp(lo)]
            st = mean_with_nw(r)
            a3 = alpha_vs_benchmark(r, ff3)
            print(f"    {s:<18} ann={st['mean']*1200:6.2f}%  t={st['t_nw']:5.2f}  "
                  f"alpha={a3['alpha']*1200:6.2f}%  t_alpha={a3['t_alpha']:5.2f}  "
                  f"beta={a3['beta_Mkt-RF']:5.2f}")


if __name__ == "__main__":
    main()
