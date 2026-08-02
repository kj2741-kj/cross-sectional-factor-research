# Implementation validation against Chen-Zimmermann

Our value-weighted decile long-short series compared against the reference
implementations in Chen and Zimmermann's Open Source Asset Pricing project
(`deciles_vw`, 179 signals, 1926-2024). Overlapping months, 1963-2024.

| Our signal | CZ signal | Months | Corr | Our mean %/mo | CZ mean %/mo | Our t | CZ t |
|---|---|---|---|---|---|---|---|
| rev | STreversal | 518 | **0.92** | 0.528 | 0.654 | 2.47 | 2.18 |
| mom | Mom12m | 511 | **0.90** | 1.218 | 1.794 | 3.65 | 4.86 |
| size | Size | 511 | 0.85 | 0.110 | -0.197 | 0.44 | -0.59 |
| value | BMdec | 503 | 0.81 | 0.247 | 0.125 | 1.09 | 0.62 |
| ivol | IdioVol3F | 460 | 0.81 | **-0.362** | **+1.063** | -1.03 | 2.78 |
| prof | OperProf | 511 | 0.77 | 0.297 | 0.314 | 1.64 | 1.52 |
| inv | AssetGrowth | 511 | 0.75 | 0.162 | 0.394 | 0.90 | 2.02 |
| ~~lowvol~~ | ~~VolSD~~ | ~~502~~ | ~~0.32~~ | ~~-0.285~~ | ~~+0.410~~ | ~~-0.79~~ | ~~2.95~~ |

## What passed

Six of eight signals correlate 0.75-0.92 with the reference. Profitability
matches almost exactly (0.297 vs 0.314). Reversal and momentum correlate 0.90+.
The core implementation, including NYSE breakpoints, delisting returns,
value weighting and Fama-French timing, is sound.

## Correction (superseded row above, struck through)

The `lowvol` vs `VolSD` row above is **not a valid comparison** and should not
have been reported. `VolSD` (Chordia, Subrahmanyam and Anshuman 2001) is the
rolling standard deviation of monthly **trading volume** — a liquidity signal —
not a return-volatility signal at all. `lowvol` (our trailing return std) and
`VolSD` measure entirely different things; a low correlation between them is
expected and uninformative. This was a mapping error in the original
validation script, caught only when pulling Chen-Zimmermann's signal
documentation to answer a follow-up question. Left visible here rather than
deleted, per the standing practice on this project of surfacing every mistake
found rather than quietly fixing it.

No Chen-Zimmermann acronym corresponds cleanly to "trailing monthly-return
volatility" at all; the closest published constructs (`IdioVol3F`,
`IdioVolCAPM`, `RealizedVol`) are all defined on **daily** returns within the
month, per Ang, Hodrick, Xing and Zhang (2006). See
`scripts/pull_crsp_daily.py` and `src/daily_vol.py` for the correct
construction, built from real CRSP daily data.

## What failed, and it matters

**The idiosyncratic volatility signal is not the published factor.** `ivol`
correlates 0.81 with CZ's `IdioVol3F` but with the opposite sign of mean return
(-0.362 vs +1.063).

The cause is the estimation window. Ang et al. (2006) and CZ estimate
idiosyncratic volatility from **daily returns within a month**, regressed on
FF3. We estimated it from a **trailing 36-month window of monthly returns**
because daily CRSP was not pulled. Those are different quantities, and the
validation proves it rather than leaving it as a caveat.

**The consequence for the study's conclusions.** An earlier draft concluded
"the low-volatility anomaly does not replicate." That statement is withdrawn.
It does replicate in CZ's data (IdioVol3F t = 2.78, VolSD t = 2.95). What our
monthly proxy shows is only that *the proxy* does not work. Testing the real
signal requires a daily CRSP pull.

**Momentum runs 0.58%/month below the reference** despite a 0.90 correlation.
CZ follow each original paper's exact construction while we apply a uniform
Fama-French decile approach across all signals, so some gap is expected, but
the size of it is unexplained and worth tracing before the momentum result is
quoted as a precise number.

## Why this was worth doing

Four bugs were already found and fixed during this project by running things
against reality rather than reading the code. This validation found a fifth
problem that no amount of code review would have surfaced: a signal that was
correctly implemented as specified, where the specification itself was wrong
for the question being asked.


---

## Correction, part 2: the volatility signal, rebuilt from real daily data

The `ivol` failure above (correlation 0.81 with `IdioVol3F`, wrong sign of mean
return) was diagnosed and fixed by pulling actual daily CRSP data
(`scripts/pull_crsp_daily.py`, 71.8M rows, 1963-2024) and building the Ang,
Hodrick, Xing and Zhang (2006) construction exactly as specified: regress each
stock's **daily** returns within a month on daily FF3, take the residual
standard deviation. `src/daily_vol.py` does this as one vectorized regression
per calendar month across all stocks trading that month, rather than 3.36
million individual per-stock regressions, since every stock shares the same
daily factor observations within a month.

**Validated first on synthetic data** with known betas and known idiosyncratic
vol (2 stocks, 3 months): recovered the true values within sampling noise
before touching real data.

### Result 1: matches Chen-Zimmermann almost exactly, once the breakpoint
convention matches theirs

CZ's default `deciles_vw` file uses full-universe quantile breakpoints (NYSE
restriction is offered as a *separate* download option in their menu, implying
it is not the default). Reproducing that convention:

| Our signal | CZ signal | Corr | Our mean %/mo | CZ mean %/mo | Our t | CZ t |
|---|---|---|---|---|---|---|
| ivol_ff3_daily | IdioVol3F | **0.95** | 1.204 | 1.153 | 3.41 | 3.23 |
| lowvol_daily | RealizedVol | **0.94** | 1.192 | 0.956 | 3.07 | 2.32 |

Both correlation and magnitude now line up closely. The construction is
correct.

### Result 2: under this study's own NYSE-breakpoint, cost-adjusted
convention, the picture changes

Everywhere else in this study, deciles are cut on **NYSE breakpoints**, not
full-universe quantiles, because full-universe cutoffs let thousands of
AMEX/NASDAQ microcaps dominate the extreme deciles and manufacture spreads
that cannot actually be traded. Applying that same standard, and the study's
cost model:

| Signal | Beta | Net ann. (NYSE, VW) | Net t | FF3 alpha | t(alpha) |
|---|---|---|---|---|---|
| ivol_ff3_daily, full sample | -0.47 | -1.21% | -0.36 | +3.20% | 1.40 |
| ivol_ff3_daily, post-2003 | -0.64 | -2.38% | -0.41 | +5.25% | 1.30 |
| lowvol_daily, post-2003 | -0.97 | -0.73% | -0.11 | **+11.18%** | **2.70** |
| ivol_capm_daily, post-2003 | -0.65 | +0.94% | 0.16 | **+9.16%** | **2.25** |

Raw net returns are near zero, but this is **not** the anomaly disappearing —
it is the portfolio's large negative market beta (-0.47 to -0.97) eating the
raw return in a market that rose most of the sample. This is exactly the same
shape of result found for the monthly-window proxy earlier in the project and
for Frazzini-Pedersen's BAB construction: a long-low-vol/short-high-vol book
is a short-beta position first and a stock-picking signal second. The FF3
alpha is where the actual signal lives, and post-2003 it is the largest alpha
of any signal in the study.

It falls short of the strict Harvey-Liu-Zhu t > 3 hurdle on alpha
(t = 2.25-2.70), so this is reported as **suggestive, not established** — see
the alpha-based multiple-testing panel in `docs/FINDINGS.md` for the full
picture across all nine signals.

Reproduce with `python scripts/build_daily_vol_signals.py` (requires
`scripts/pull_crsp_daily.py` to have been run first; both need a WRDS
subscription and cost one Duo push each).