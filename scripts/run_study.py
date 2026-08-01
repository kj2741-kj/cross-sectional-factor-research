#!/usr/bin/env python
# coding: utf-8
"""End-to-end reproduction of the study, P0 through P7.

    python scripts/run_study.py

Requires the WRDS pull to have been run once (scripts/pull_crsp_universe.py).
"""
import os
import pickle
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from universe import build_universe                      # noqa: E402
from fundamentals import build_fundamentals              # noqa: E402
from signals import build_signal_panel                   # noqa: E402
from portfolios import build_all_portfolios              # noqa: E402
from factors import benchmark_set                        # noqa: E402
from evaluation import evaluate_signals, fama_macbeth    # noqa: E402
from regimes import dm_indicators, hmm_regimes, hmm_regimes_expanding  # noqa: E402
from regime_analysis import (momentum_crash_analysis, conditional_premia,  # noqa: E402
                             regime_timed_strategy, strategy_stats)

PROC = os.path.join(os.path.dirname(__file__), "..", "data", "processed")


def main():
    print("P0 universe ...");      _, s0 = build_universe();      print("   ", s0["final_rows"], "rows")
    print("P1 fundamentals ...");  _, s1 = build_fundamentals();  print("   ", s1["final_rows"], "rows")
    print("P2 signals ...");       panel, s2 = build_signal_panel(); print("   ", s2["rows"], "rows")

    print("P3 portfolios ...")
    ls, decs = build_all_portfolios(panel)
    pickle.dump({"ls": ls, "decs": decs}, open(os.path.join(PROC, "portfolios.pkl"), "wb"))

    print("P4 evaluation ...")
    ff3, _ = benchmark_set("ff3")
    ff5, _ = benchmark_set("ff5")
    cut = pd.Timestamp("2003-01-01")
    for wt in ("vw", "ew"):
        print(f"\n--- full sample, {wt} ---")
        print(evaluate_signals(ls, ff3, ff5, weighting=wt).round(3).to_string())
        for name, sel in (("pre-2003", lambda d: d[d.index < cut]),
                          ("post-2003", lambda d: d[d.index >= cut])):
            sub = {k: sel(v) for k, v in ls.items()}
            r = evaluate_signals(sub, ff3, ff5, weighting=wt)
            print(f"  {name} survives HLZ t>3:", list(r.index[r.survives_hlz_t3.astype(bool)]))

    print("\nP5 regimes ...")
    mkt = ff3["Mkt-RF"].loc["1963":"2024"]
    dm = dm_indicators(mkt)
    hm = hmm_regimes(mkt, n_states=2)
    ho = hmm_regimes_expanding(mkt, n_states=2)
    pickle.dump({"dm": dm, "hmm": hm, "hmm_oos": ho, "mkt": mkt},
                open(os.path.join(PROC, "regimes.pkl"), "wb"))

    print("\nP6 momentum crashes ...")
    print(momentum_crash_analysis(ls["mom"]["vw"], dm, mkt).round(2).to_string())
    print("\nP6 premia by DM panic state ...")
    print(conditional_premia(ls, dm.panic.astype(int), "vw").round(2).to_string())

    print("\nP7 regime timing (out-of-sample labels only) ...")
    for name, lab, bad in (("DM panic rule", dm.panic.astype(int), 1),
                           ("HMM expanding OOS", ho, 0)):
        st = strategy_stats(regime_timed_strategy(ls["mom"]["vw"], lab, bad_state=bad))
        print(f"\n--- {name} ---")
        print(st.round(2).to_string())

    print("\nSee docs/FINDINGS.md for the written results.")


if __name__ == "__main__":
    main()
