#!/usr/bin/env python
# coding: utf-8
"""
Fama-French 12-industry classification from SIC codes.

Note what this is and is not. The FF *factors* (SMB, HML, RMW, CMA) are built
from sorts on firm characteristics and are industry-agnostic: a stock lands in
the value decile because of its own book-to-market, not its sector. Ken French
separately publishes industry *portfolios* (5/10/12/17/30/38/48/49 industries),
which are a different product built by grouping on SIC.

The two get conflated a lot. This module exists to make the distinction testable
rather than rhetorical: with industry labels attached, a characteristic sort can
be run pooled (what the study does) or within-industry (industry-neutral), and
the difference measured.

Reference: Ken French Data Library, "Detail for 12 Industry Portfolios".
"""
import numpy as np
import pandas as pd

# (label, [(lo, hi), ...]) inclusive SIC ranges, in priority order.
FF12 = [
    ("NoDur", [(100, 999), (2000, 2399), (2700, 2749), (2770, 2799),
               (3100, 3199), (3940, 3989)]),
    ("Durbl", [(2500, 2519), (2590, 2599), (3630, 3659), (3710, 3711),
               (3714, 3714), (3716, 3716), (3750, 3751), (3792, 3792),
               (3900, 3939), (3990, 3999)]),
    ("Manuf", [(2520, 2589), (2600, 2699), (2750, 2769), (3000, 3099),
               (3200, 3569), (3580, 3629), (3700, 3709), (3712, 3713),
               (3715, 3715), (3717, 3749), (3752, 3791), (3793, 3799),
               (3830, 3839), (3860, 3899)]),
    ("Enrgy", [(1200, 1399), (2900, 2999)]),
    ("Chems", [(2800, 2829), (2840, 2899)]),
    ("BusEq", [(3570, 3579), (3660, 3692), (3694, 3699), (3810, 3829),
               (7370, 7379)]),
    ("Telcm", [(4800, 4899)]),
    ("Utils", [(4900, 4949)]),
    ("Shops", [(5000, 5999), (7200, 7299), (7600, 7699)]),
    ("Hlth",  [(2830, 2839), (3693, 3693), (3840, 3859), (8000, 8099)]),
    ("Money", [(6000, 6999)]),
]

FF12_LABELS = {
    "NoDur": "Consumer non-durables", "Durbl": "Consumer durables",
    "Manuf": "Manufacturing", "Enrgy": "Energy", "Chems": "Chemicals",
    "BusEq": "Business equipment / tech", "Telcm": "Telecoms",
    "Utils": "Utilities", "Shops": "Wholesale & retail",
    "Hlth": "Healthcare", "Money": "Finance", "Other": "Other",
}


def sic_to_ff12(siccd):
    """Map SIC codes to the FF 12-industry labels. Unmatched codes become Other."""
    s = pd.to_numeric(pd.Series(siccd), errors="coerce")
    out = pd.Series("Other", index=s.index, dtype=object)
    assigned = pd.Series(False, index=s.index)
    for label, ranges in FF12:
        mask = pd.Series(False, index=s.index)
        for lo, hi in ranges:
            mask |= (s >= lo) & (s <= hi)
        take = mask & ~assigned
        out[take] = label
        assigned |= take
    out[s.isna()] = np.nan
    return out


def industry_neutral(values, industries, min_per_group=5):
    """Demean and standardise a signal within each industry.

    This is what "industry-neutral" means operationally: a stock is judged
    cheap relative to its own sector rather than relative to the market. It
    strips out the persistent industry tilt that a pooled sort embeds, because
    high book-to-market is partly a statement about being a bank rather than
    about being cheap.

    Reference: Asness, Porter and Stevens (2000), "Predicting Stock Returns
    Using Industry-Relative Firm Characteristics".
    """
    df = pd.DataFrame({"v": pd.to_numeric(values, errors="coerce"),
                       "g": pd.Series(industries).values})
    g = df.groupby("g")["v"]
    mu, sd, n = g.transform("mean"), g.transform("std"), g.transform("count")
    out = (df["v"] - mu) / sd.where(sd > 0)
    return out.where(n >= min_per_group)
