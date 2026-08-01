# Regime-Conditional Cross-Sectional Factor Research

Phase plan, locked 2026-08-01.

## Research question

Do standard cross-sectional equity factor premia survive a proper multiple-testing
hurdle on a full CRSP universe, and does conditioning on market regime improve
them beyond what a simple published rule already achieves?

Two things distinguish this from the very large number of near-identical factor
studies:

1. **A real universe with the unglamorous corrections applied.** Delisting
   returns, NYSE breakpoints, correct CCM linking, Fama-French timing. These are
   where most retail replications silently break.
2. **The regime layer is tested against a published benchmark**, not presented
   on its own. Daniel-Moskowitz (2016) already established that momentum crashes
   in high-volatility bear-market rebounds using a simple ex-ante rule. An HMM
   only earns its complexity if it beats that.

## Committed in advance

A null result is an acceptable outcome. McLean and Pontiff (2016) document ~58%
post-publication decay in anomaly returns, so several of these six signals may
fail a t > 3.0 hurdle in the post-2003 sample. Building this to guarantee a
positive result is exactly how it becomes another clone. The pre/post-2003 split
is therefore part of the design, not a robustness afterthought.

## Sample

- **1963-2024**, monthly, matching the standard Fama-French sample start.
- Explicit **pre/post-2003 split** to test post-publication decay directly.
- Universe: CRSP common shares (`SHRCD` 10, 11) on NYSE/AMEX/NASDAQ
  (`EXCHCD` 1, 2, 3).

## Phases

| Phase | Content | Model | Status |
|---|---|---|---|
| P0 | CRSP universe: `msf`, `msenames`, `msedelist`. Filters, delisting-return splicing, market equity. | Sonnet | |
| P1 | Compustat `funda` merge via CCM `ccmxpf_lnkhist`, Fama-French timing conventions. | Sonnet | |
| P2 | Six signals: value, momentum, size, profitability, investment, idiosyncratic volatility. | Sonnet | |
| P3 | Portfolio formation: NYSE-breakpoint deciles, value- and equal-weighted, long-short series. | Opus | |
| P4 | Evaluation: Newey-West t-stats, FF3/FF5 alpha attribution, Fama-MacBeth, multiple-testing hurdle. | Opus | |
| P5 | Regime detection: HMM on market return and volatility; validate states are economically meaningful. | Fable 5 | |
| P6 | Regime-conditional premia + Daniel-Moskowitz momentum-crash replication. | Fable 5 | |
| P7 | Regime-conditional strategy with honest out-of-sample test. | Opus | |
| P8 | Report and dashboard. | Sonnet | |

## Methodology decisions locked up front

**Delisting returns.** CRSP `ret` is missing in the delisting month. The delisting
return from `msedelist` must be spliced in, and where `dlret` is itself missing
for a performance-related delisting code (500, 520-584), the standard treatment
is to substitute -30% (Shumway 1997). Omitting this is the largest single source
of upward bias in retail factor replications.

**NYSE breakpoints.** Decile cutoffs are computed on NYSE stocks only, then
applied to the whole universe. Using full-universe quantiles instead puts the
thousands of AMEX/NASDAQ microcaps into the extreme buckets and manufactures
spreads that are not tradeable.

**Value-weighted as primary.** Equal-weighted results are reported alongside,
because the gap between them is itself the microcap-dependence diagnostic.

**Fama-French timing.** Accounting data for fiscal year ending in calendar year
t-1 is matched to returns from July of year t through June of year t+1, with
market equity from December of t-1 for book-to-market. This lag exists to
guarantee the fundamentals were public; shortening it is look-ahead bias.

**Multiple testing.** Six signals tested simultaneously. Report raw Newey-West
t-stats, then apply the Harvey-Liu-Zhu (2016) t > 3.0 hurdle and a
Benjamini-Hochberg FDR correction. Both, because they answer slightly different
questions.

## Data sources

| Table | Use |
|---|---|
| `crsp.msf` | monthly returns, price, shares outstanding |
| `crsp.msenames` | share code, exchange code, SIC, ticker |
| `crsp.msedelist` | delisting returns and codes |
| `comp.funda` | book equity, profitability, asset growth |
| `crsp.ccmxpf_lnkhist` | Compustat to CRSP permno link |
| Ken French library | FF3/FF5 factors for attribution benchmarks |

CRSP and Compustat are licensed and gitignored. Ken French data is public.

## References

- Fama, E. and French, K. (1993, 2015). Three- and five-factor models.
- Jegadeesh, N. and Titman, J. (1993). Momentum.
- Daniel, K. and Moskowitz, T. (2016). "Momentum Crashes." JFE 122(2).
- Harvey, C., Liu, Y. and Zhu, H. (2016). "...and the Cross-Section of Expected
  Returns." Review of Financial Studies 29(1).
- McLean, R. and Pontiff, J. (2016). "Does Academic Research Destroy Return
  Predictability?" Journal of Finance 71(1).
- Shumway, T. (1997). "The Delisting Bias in CRSP Data." Journal of Finance 52(1).
- Novy-Marx, R. (2013). Gross profitability.
