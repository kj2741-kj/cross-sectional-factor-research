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
| lowvol | VolSD | 502 | **0.32** | -0.285 | +0.410 | -0.79 | 2.95 |

## What passed

Six of eight signals correlate 0.75-0.92 with the reference. Profitability
matches almost exactly (0.297 vs 0.314). Reversal and momentum correlate 0.90+.
The core implementation, including NYSE breakpoints, delisting returns,
value weighting and Fama-French timing, is sound.

## What failed, and it matters

**The volatility signals are not the published factors.** `lowvol` correlates
only 0.32 with CZ's VolSD, and `ivol` correlates 0.81 but with the opposite
sign of mean return (-0.362 vs +1.063).

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
