#!/usr/bin/env python
# coding: utf-8
"""
Monthly Fama-French benchmark factors from the Ken French Data Library.

Public, free, no credentials, and fresher than the CRSP subscription. Monthly
files key rows on YYYYMM rather than the daily files' YYYYMMDD, and several
append an annual block below the monthly one, so rows are selected by key length
rather than by line offset.
"""
import io
import os
import zipfile
import urllib.request

import numpy as np
import pandas as pd

BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "factors")

FILES = {
    "ff3": "F-F_Research_Data_Factors_CSV.zip",
    "ff5": "F-F_Research_Data_5_Factors_2x3_CSV.zip",
    "mom": "F-F_Momentum_Factor_CSV.zip",
}

DAILY_FILES = {
    "ff3": "F-F_Research_Data_Factors_daily_CSV.zip",
    "ff5": "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip",
}


def _find_header(lines):
    """Locate the real column-header row in a Ken French CSV.

    Cannot search for a factor name: the prose preamble describes the factors by
    name, so "Mom" appears on line 4 of the momentum file long before the actual
    ",Mom" header on line 14. Matching on the name silently parsed the
    description as the header and returned an empty frame.

    The header is the first row whose leading field is blank (the unnamed date
    column) and which is immediately followed by a row starting with digits.
    """
    for i, l in enumerate(lines[:-1]):
        parts = l.split(",")
        if len(parts) < 2 or parts[0].strip() != "":
            continue
        nxt = lines[i + 1].split(",")[0].strip()
        if nxt[:4].isdigit():
            return i
    raise ValueError("Could not locate a header row in the Ken French file.")


def load_ff(dataset="ff3", cache_dir=None, refresh=False):
    cache_dir = cache_dir or CACHE
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{dataset}_monthly.csv")
    if os.path.exists(path) and not refresh:
        return pd.read_csv(path, index_col=0, parse_dates=True)

    req = urllib.request.Request(BASE + FILES[dataset],
                                 headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=60).read()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        text = z.read(z.namelist()[0]).decode("latin-1")

    lines = text.splitlines()
    hdr = _find_header(lines)
    cols = [c.strip() for c in lines[hdr].split(",")[1:]]

    dates, rows = [], []
    for line in lines[hdr + 1:]:
        parts = line.split(",")
        key = parts[0].strip()
        # 6 digits is a monthly row; 4 digits is the annual block underneath.
        if len(key) != 6 or not key.isdigit() or len(parts) - 1 != len(cols):
            continue
        dates.append(pd.to_datetime(key, format="%Y%m"))
        rows.append([float(p) for p in parts[1:]])

    df = pd.DataFrame(rows, index=pd.DatetimeIndex(dates, name="date"), columns=cols)
    df = df.mask(df <= -99.0) / 100.0          # published in percent
    df.index = df.index + pd.offsets.MonthEnd(0)  # align to CRSP month-end
    df.to_csv(path)
    return df


def load_ff_daily(dataset="ff3", cache_dir=None, refresh=False):
    """Daily Fama-French factors, needed for the Ang et al. (2006) volatility
    signals: idiosyncratic and total volatility are both defined on daily
    returns within a single month, and cannot be built from the monthly series.

    Same header-detection and percent-to-decimal handling as `load_ff`; the
    only structural difference is an 8-digit YYYYMMDD date key instead of
    6-digit YYYYMM.
    """
    cache_dir = cache_dir or CACHE
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{dataset}_daily.csv")
    if os.path.exists(path) and not refresh:
        return pd.read_csv(path, index_col=0, parse_dates=True)

    req = urllib.request.Request(BASE + DAILY_FILES[dataset],
                                 headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=60).read()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        text = z.read(z.namelist()[0]).decode("latin-1")

    lines = text.splitlines()
    hdr = _find_header(lines)
    cols = [c.strip() for c in lines[hdr].split(",")[1:]]

    dates, rows = [], []
    for line in lines[hdr + 1:]:
        parts = line.split(",")
        key = parts[0].strip()
        if len(key) != 8 or not key.isdigit() or len(parts) - 1 != len(cols):
            continue
        dates.append(pd.to_datetime(key, format="%Y%m%d"))
        rows.append([float(p) for p in parts[1:]])

    df = pd.DataFrame(rows, index=pd.DatetimeIndex(dates, name="date"), columns=cols)
    df = df.mask(df <= -99.0) / 100.0
    df.to_csv(path)
    return df


def benchmark_set(name="ff3", cache_dir=None):
    """Return the factor matrix plus RF, with momentum appended for ff3+mom."""
    if name in ("ff3", "ff5"):
        f = load_ff(name, cache_dir)
        rf = f.pop("RF")
        return f, rf
    if name == "ff4":
        f = load_ff("ff3", cache_dir)
        rf = f.pop("RF")
        mom = load_ff("mom", cache_dir)
        mom.columns = [c.strip() for c in mom.columns]
        f = f.join(mom[["Mom"]], how="inner")
        return f, rf.reindex(f.index)
    raise ValueError(f"unknown benchmark {name!r}")
