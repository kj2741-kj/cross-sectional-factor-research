#!/usr/bin/env python
# coding: utf-8
"""
P0 validation: universe filters, delisting returns, market equity.

Synthetic fixtures with known answers, so this runs without the licensed CRSP
data present.

    python tests/test_universe.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from universe import (  # noqa: E402
    attach_name_info,
    apply_delisting_returns,
    compute_market_equity,
    PERFORMANCE_DELIST,
    SHUMWAY_LISTED,
    SHUMWAY_NASDAQ,
)

PASSED, FAILED = [], []


def check(name, cond, detail=""):
    (PASSED if cond else FAILED).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


print("\n[1] Name history is applied period by period")
msf = pd.DataFrame({
    "permno": [1, 1, 1],
    "permco": [10, 10, 10],
    "date": pd.to_datetime(["2000-01-31", "2005-01-31", "2010-01-31"]),
    "ret": [0.01, 0.02, 0.03], "retx": [0.01, 0.02, 0.03],
    "prc": [10.0, 20.0, 30.0], "shrout": [1000.0] * 3, "vol": [1e5] * 3,
})
# The stock is an ordinary common share until 2007, then converts to a class
# that should be excluded. A current-record-only merge would get this wrong.
names = pd.DataFrame({
    "permno": [1, 1],
    "namedt": pd.to_datetime(["1990-01-01", "2007-01-01"]),
    "nameendt": pd.to_datetime(["2006-12-31", None]),
    "shrcd": [11, 73], "exchcd": [1, 1], "siccd": [3570, 3570],
    "ticker": ["AAA", "AAA"], "comnam": ["A Corp", "A Corp"],
})
merged = attach_name_info(msf, names)
check("every observation gets a name record", len(merged) == 3)
check("share code reflects the date, not the latest record",
      list(merged.sort_values("date")["shrcd"]) == [11, 11, 73],
      str(list(merged.sort_values("date")["shrcd"])))
check("open-ended name records are treated as current",
      merged["nameendt"].max() > pd.Timestamp("2090-01-01"))

print("\n[2] Delisting returns")
base = pd.DataFrame({
    "permno": [1, 2, 3, 4],
    "date": pd.to_datetime(["2000-03-31"] * 4),
    "ret": [-0.10, -0.20, np.nan, 0.05],
    "exchcd": [1, 3, 1, 1],
})
delist = pd.DataFrame({
    "permno": [1, 2, 3],
    "dlstdt": pd.to_datetime(["2000-03-15", "2000-03-20", "2000-03-10"]),
    # permno 1 has a recorded delisting return; 2 and 3 are performance
    # delistings with none, so Shumway substitution applies.
    "dlret": [-0.50, np.nan, np.nan],
    "dlstcd": [500, 552, 574],
})
out = apply_delisting_returns(base, delist).set_index("permno")
check("recorded delisting return is compounded with the partial month",
      np.isclose(out.loc[1, "ret_adj"], (1 - 0.10) * (1 - 0.50) - 1),
      f"{out.loc[1, 'ret_adj']:.4f}")
check("NASDAQ performance delisting without a return uses -55%",
      np.isclose(out.loc[2, "dlret_used"], SHUMWAY_NASDAQ))
check("listed-exchange performance delisting uses -30%",
      np.isclose(out.loc[3, "dlret_used"], SHUMWAY_LISTED))
check("a missing monthly return falls back to the delisting return alone",
      np.isclose(out.loc[3, "ret_adj"], SHUMWAY_LISTED))
check("a surviving stock is untouched",
      np.isclose(out.loc[4, "ret_adj"], 0.05) and pd.isna(out.loc[4, "dlret_used"]))
check("substitutions are flagged for audit",
      bool(out.loc[2, "dlret_substituted"]) and not bool(out.loc[1, "dlret_substituted"]))

check("performance codes classified correctly",
      bool(PERFORMANCE_DELIST(pd.Series([500])).iloc[0])
      and bool(PERFORMANCE_DELIST(pd.Series([552])).iloc[0])
      and not bool(PERFORMANCE_DELIST(pd.Series([200])).iloc[0]),
      "500 and 552 are failures, 200 (merger) is not")

print("\n[3] Market equity")
me_in = pd.DataFrame({
    "permno": [1, 2, 3, 4],
    "permco": [10, 10, 20, 30],       # permnos 1 and 2 are share classes of one company
    "date": pd.to_datetime(["2000-01-31"] * 4),
    "prc": [10.0, 5.0, -20.0, np.nan],  # negative price = bid/ask midpoint
    "shrout": [1000.0, 400.0, 500.0, 100.0],
})
me = compute_market_equity(me_in).set_index("permno")
check("negative prices are treated as valid quotes in absolute value",
      np.isclose(me.loc[3, "me_permno"], 10.0), f"{me.loc[3, 'me_permno']}")
check("share classes are summed to a company total",
      np.isclose(me.loc[1, "me_company"], 12.0), f"{me.loc[1, 'me_company']}")
check("company total is carried only on the largest share class",
      np.isclose(me.loc[1, "me"], 12.0) and pd.isna(me.loc[2, "me"]))
check("exactly one primary permno per company",
      me.loc[[1, 2], "is_primary"].sum() == 1)
check("a company with no usable price stays NaN rather than zero",
      pd.isna(me.loc[4, "me_company"]), f"{me.loc[4, 'me_company']}")
check("shrout is scaled from thousands to $ millions",
      np.isclose(me.loc[3, "me_permno"], 20.0 * 500.0 / 1000.0))

print("\n" + "=" * 62)
print(f"  {len(PASSED)} passed, {len(FAILED)} failed")
for f in FAILED:
    print(f"    FAILED: {f}")
print("=" * 62)
sys.exit(1 if FAILED else 0)
