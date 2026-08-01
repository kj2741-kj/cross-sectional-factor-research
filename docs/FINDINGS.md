# Findings

Regime-conditional cross-sectional factor research, CRSP 1963-2024.
All results reproducible from `scripts/` and `src/`.

## Sample

3,421,715 monthly observations, 26,200 stocks, 744 months (1963-01 to 2024-12),
built from 4.79M raw CRSP rows. Delisting returns spliced in (2,698 used, 99
Shumway substitutions), NYSE breakpoints for all decile cutoffs, company-level
market equity, Fama-French timing on all annual fundamentals.

Six signals: size, value, momentum (12-2), profitability, investment,
short-term reversal.

---

## 1. Value weighting versus equal weighting changes the answer

Full sample, long-short decile spreads, monthly percent:

| Signal | VW mean | VW t(NW) | EW mean | EW t(NW) |
|---|---|---|---|---|
| Size | 0.146 | 0.69 | 0.521 | 2.36 |
| Value | 0.293 | 1.41 | 1.103 | 5.68 |
| **Momentum** | **1.182** | **4.35** | 0.737 | 2.92 |
| Profitability | 0.276 | 1.66 | 0.005 | 0.03 |
| Investment | 0.332 | 2.20 | 1.132 | 8.61 |
| Reversal | 0.297 | 1.72 | 1.839 | 9.46 |

Reversal is 0.30% value-weighted and 1.84% equal-weighted, a factor of six. Value
is 0.29% against 1.10%. These gaps are the microcap-dependence diagnostic: a
premium that exists only equal-weighted lives in stocks too small to hold at
size. Value-weighted results are the tradeable ones and are treated as primary
throughout.

## 2. Under a proper multiple-testing hurdle, only momentum survives

Six signals tested simultaneously, so the naive t > 2 threshold is not the right
bar.

| Criterion | Value-weighted survivors |
|---|---|
| Naive t > 2 | momentum, investment |
| Benjamini-Hochberg FDR 5% | **momentum** |
| Harvey-Liu-Zhu t > 3.0 | **momentum** |

Equal-weighted, five of six clear t > 2 and three clear the HLZ hurdle, which is
precisely why the weighting choice has to be stated before the hurdle is applied.

Against FF3, value has a **negative** alpha (-0.26%, t = -2.57): HML already
captures it, so the raw premium is not incremental information. Momentum's FF3
alpha is +1.67% (t = 5.93) and survives FF5 at +1.50% (t = 4.28).

## 3. Post-2003, nothing survives value-weighted

The McLean-Pontiff (2016) decay test, splitting at 2003:

| Signal | Pre-2003 mean | Pre t | Post-2003 mean | Post t | Decay |
|---|---|---|---|---|---|
| Size | 0.32 | 1.20 | -0.18 | -0.60 | 156% |
| Value | 0.56 | 2.31 | -0.19 | -0.53 | 134% |
| Momentum | 1.70 | 6.31 | 0.26 | 0.49 | 84% |
| Profitability | 0.23 | 1.11 | 0.36 | 1.30 | -54% |
| Investment | 0.55 | 3.18 | -0.07 | -0.28 | 113% |
| Reversal | 0.54 | 2.59 | -0.15 | -0.48 | 127% |

**Value-weighted, post-2003: zero signals survive HLZ t > 3.0 and zero survive
BH FDR.** Four of six flip sign outright. Momentum, the one signal that survives
in the full sample, decays 84% and becomes statistically indistinguishable from
zero (t = 0.49).

This was pre-registered in `PHASE_PLAN.md` as an acceptable outcome, and it is
the main result of the study. Profitability is the only signal that does not
decay, and it was never significant to begin with.

## 4. Momentum crashes replicate exactly

Daniel-Moskowitz (2016), value-weighted momentum:

| State | Months | Mean %/mo | t(NW) | Annualised | Worst month |
|---|---|---|---|---|---|
| Non-bear | 396 | +1.67 | 5.71 | +20.1% | -26.9% |
| Bear (all) | 115 | -0.35 | -0.33 | -4.3% | -45.6% |
| **Bear + market UP** | 71 | **-3.54** | **-2.42** | **-42.5%** | -45.6% |
| Bear + market DOWN | 44 | +4.78 | 5.43 | +57.4% | -18.8% |
| Panic + market UP | 59 | -4.48 | -2.64 | -53.8% | -45.6% |

The bear flag on its own is insignificant. The crash is specifically the
*interaction* of a bear market with a rebound: momentum's short leg is full of
beaten-down high-beta names that snap back hardest. Momentum in a **falling**
bear market earns +4.78%/month.

Regime conditioning also shows reversal is a crisis phenomenon: -0.16%/mo in
normal states, +3.55% (t = 4.14) in panic states, spread t = 4.36.

## 5. The HMM does not earn its complexity

The central test. Both regime signals used strictly ex ante, HMM labels from an
expanding-window refit so they are genuine forecasts.

Full sample, value-weighted momentum, de-risked to zero in the flagged state:

| | Ann. return | Ann. vol | Sharpe | Max DD | Months de-risked |
|---|---|---|---|---|---|
| Raw momentum | 14.9% | 24.1% | 0.62 | -76.2% | — |
| **+ DM panic rule** | **16.4%** | 19.0% | **0.86** | **-35.5%** | 19% |
| + HMM (expanding OOS) | 3.8% | 13.1% | 0.29 | -35.5% | 59% |

Post-2003, where raw momentum is dead (t = 0.47):

| | Ann. return | Sharpe | t(NW) |
|---|---|---|---|
| Raw momentum | 3.4% | 0.12 | 0.47 |
| **+ DM panic rule** | **10.0%** | **0.49** | **2.18** |
| + HMM (expanding OOS) | 4.0% | 0.25 | 0.99 |

**The simple published rule beats the latent-state model on every measure.** The
HMM's failure is diagnosable rather than mysterious: it de-risks 59% of months
against the rule's 19%, so it is identifying ordinary high-volatility periods
rather than the specific bear-plus-rebound state that actually kills momentum. A
two-state Gaussian HMM on market return and volatility has no way to represent
"down over two years but rising this month", because that is a conditional
interaction, not a level of volatility.

The one genuinely useful result: the DM rule restores post-2003 momentum from
t = 0.47 to t = 2.18 and cuts maximum drawdown from -71% to -35%. Even that
still fails an HLZ t > 3.0 hurdle, and it is a single rule selected with full
knowledge of the published literature, so it should be read as a replication of
Daniel-Moskowitz on an extended sample rather than a new discovery.

## 6. What this says overall

1. Weighting scheme decides which factor "premia" exist at all. Half of these
   signals are equal-weight artifacts.
2. On a value-weighted, multiple-testing-corrected basis, one of six canonical
   signals survives the full sample and **none survive post-2003**.
3. Momentum's crash risk is real, large, and forecastable by a rule from 2016
   that requires no machine learning.
4. The HMM added complexity and lost money. Building the published benchmark
   first is what made that visible; without it, the HMM's -35% max drawdown
   versus raw momentum's -76% would have looked like a success.

## Limitations

- No transaction costs. Momentum's turnover is high and reversal's is extreme,
  so the equal-weighted reversal premium in particular would not survive real
  trading costs. This alone could eliminate several of the surviving results.
- Long-short deciles assume costless shorting and full availability of borrow,
  which is unrealistic in the small-cap short legs.
- Six signals is a small menu. The HLZ hurdle is calibrated to the far larger
  universe of factors the literature has tested, so applying it here is
  conservative in one direction and lenient in another.
- The HMM is two-state Gaussian on two observables. A richer specification, more
  states, or different observables might do better; the finding is that this
  standard specification does not beat a simple rule, not that no latent-state
  model could.
- Delisting-return substitution uses the Shumway constants rather than
  firm-specific recovery estimates.

---

# Addendum: industry structure and transaction costs

## 7. Momentum is not industry momentum

Moskowitz and Grinblatt (1999) argued individual momentum is really industry
momentum in disguise. On this sample it is not.

| | Mean %/mo | t(NW) | Sharpe |
|---|---|---|---|
| Pooled momentum | 1.182 | 4.35 | 0.57 |
| Industry-neutral momentum | 1.072 | 4.67 | **0.65** |
| Pure industry momentum (top 3 - bottom 3) | 0.320 | 2.43 | 0.29 |

Neutralising within industry costs 9% of the premium and *raises* the Sharpe,
because it sheds industry-concentration risk without shedding signal. Pure
industry momentum is real but roughly a third the size. The Grundy-Martin (2001)
position holds here.

Value is the opposite case. The cheap decile is 19.3% financials against the
expensive decile's 4.3%, while the expensive decile is 23.0% tech and 17.1%
healthcare against 8.9% and 3.1%. A pooled value sort is substantially a
long-banks, short-tech-and-biotech position. Momentum's largest industry
imbalance is 3.5 percentage points.

## 8. Transaction costs decide which results survive

Turnover is measured from actual month-to-month holdings after drifting prior
weights by their own returns. Costs follow a schedule anchored on US market
structure (fixed commissions to 1975, decimalisation 2001), with equal-weighted
portfolios charged 3.5x for their microcap tilt.

| Signal | Wt | Turnover/mo | Gross % | Net % | Net t | Breakeven bps |
|---|---|---|---|---|---|---|
| Momentum | VW | 70.6% | 1.182 | **0.837** | **3.12** | 167 |
| Investment | EW | 23.0% | 1.132 | **0.756** | **5.46** | 491 |
| Value | EW | 17.7% | 1.103 | **0.823** | **4.21** | 623 |
| Value | VW | 7.0% | 0.293 | 0.262 | 1.26 | 418 |
| Momentum | EW | 60.8% | 0.737 | -0.318 | -1.25 | 121 |
| **Reversal** | EW | **167.5%** | **1.839** | **-1.147** | **-4.26** | 110 |
| **Reversal** | VW | **182.2%** | 0.297 | **-0.618** | **-3.48** | 16 |

**Short-term reversal, the largest gross premium in the study, is the largest
net loss.** At 167-182% monthly turnover it needs to be traded roughly twice
over every month. Its value-weighted version breaks even at a one-way cost of 16
basis points, which is above what the market actually charged for most of this
sample. This reproduces Novy-Marx and Velikov (2016) and retroactively justifies
treating the earlier gross reversal result as an artifact.

Value-weighted momentum survives net at t = 3.12, still clearing the
Harvey-Liu-Zhu hurdle, with a breakeven of 167bps against a modern cost of
roughly 6-12bps.

Post-2003 net, value-weighted, nothing survives. Equal-weighted, investment
(t = 3.24) and value (t = 2.39) do, because their turnover is low enough that
costs barely touch them.

## 9. The sector strategy is cost-robust but low-octane

Twelve FF industries ranked, long the top three and short the bottom three,
monthly, costed at 4bps one-way for ETF-level execution.

| Signal | Turnover/mo | Gross % | Net % | Net t | Sharpe | Breakeven bps |
|---|---|---|---|---|---|---|
| Combined composite | 28.2% | 0.325 | 0.314 | 2.72 | 0.35 | **115** |
| Sector investment | 16.9% | 0.254 | 0.247 | 2.31 | 0.31 | 150 |
| Sector momentum | 44.1% | 0.320 | 0.302 | 2.29 | 0.27 | 73 |
| Sector profitability | 15.0% | 0.212 | 0.206 | 1.76 | 0.25 | 142 |
| Sector value | 15.1% | 0.128 | 0.122 | 1.00 | 0.13 | 85 |

Costs are almost irrelevant here: the composite breaks even at 115bps against
an actual 4bps. That is the genuine advantage of trading factors at the sector
level, and it is exactly the objection Dichtl et al. (2019) raise against
dynamic factor strategies.

But the gross spread is small. Net of costs the composite earns 3.8%/year
against value-weighted momentum's 10.1%. Cost-robustness does not compensate for
having roughly one tenth the cross-sectional dispersion to work with. And
post-2003 the sector composite fails too (t = 0.90).

**Caveat on the comparison.** These are effective-spread costs and contain no
market-impact term, so they describe a modest book. At institutional scale
momentum's 70% monthly turnover across thousands of names generates impact that
the sector strategy structurally avoids. The comparison would narrow, possibly
reverse, and this model cannot say by how much.

## 10. The regime overlay is a momentum-crash hedge, not a regime timer

Applying the Daniel-Moskowitz panic rule to the sector composite makes it worse:

| | Ann. return | Sharpe |
|---|---|---|
| Sector composite, net | 4.6% | 0.43 |
| + DM panic overlay | 3.0% | 0.33 |

The same rule that lifts momentum's Sharpe from 0.62 to 0.86 costs the sector
composite 0.10 of Sharpe. This is the sharpest statement of what the regime
signal actually is: it identifies the state in which *momentum's short leg
violently rebounds*, not a general state of "bad for factor strategies". A
diversified composite has little momentum-crash exposure to hedge, so switching
it off in panic states only forgoes return.

Combined with the earlier finding that the HMM loses to this rule, the regime
conclusion for the whole study is narrow and specific: regime conditioning
worked in exactly one place, for exactly the reason the published paper said it
would, and generalised to nothing else tested.
