# Regime-Conditional Cross-Sectional Factor Research

Do standard cross-sectional equity factor premia survive a proper multiple-testing
hurdle on a full CRSP universe, and does conditioning on market regime improve them
beyond what a simple published rule already achieves?

Full scope, methodology decisions and phase status in [`PHASE_PLAN.md`](PHASE_PLAN.md).

## Status

**Complete, P0 through P8.** Full written results in [`docs/FINDINGS.md`](docs/FINDINGS.md).

Universe: 3,421,715 monthly observations, 26,200 stocks, 744 months (1963-01 to 2024-12).

### Headline results

1. **Value weighting decides which premia exist.** Short-term reversal is 0.30%/month
   value-weighted and 1.84% equal-weighted. Half these signals are equal-weight artifacts.
2. **Under multiple-testing correction, only momentum survives the full sample**
   value-weighted (Benjamini-Hochberg FDR and Harvey-Liu-Zhu t > 3.0). Value has a
   *negative* FF3 alpha: HML already captures it.
3. **Post-2003, nothing survives value-weighted.** Zero signals clear either hurdle.
   Momentum decays 84%; four of six flip sign. This is a direct confirmation of
   McLean-Pontiff (2016) post-publication decay, and was pre-registered as an
   acceptable outcome.
4. **Momentum crashes replicate exactly.** The bear-market flag alone is insignificant
   (-0.35%/mo, t = -0.33); the crash is the *interaction* with a rebounding market
   (-3.54%/mo, t = -2.42, worst month -45.6%). In a falling bear market momentum earns
   +4.78%/month.
5. **The HMM does not earn its complexity.** Daniel-Moskowitz's simple published rule
   lifts momentum's Sharpe 0.62 to 0.86 and cuts max drawdown from -76% to -35%; the
   expanding-window HMM *lowers* Sharpe to 0.29. It de-risks 59% of months versus the
   rule's 19%, flagging ordinary high-volatility periods rather than the specific
   bear-plus-rebound state that kills momentum.

Building the published benchmark first is what made result 5 visible. Without it, the
HMM's -35% drawdown would have looked like a success.

## Setup

```bash
pip install -r requirements.txt
python scripts/pull_crsp_universe.py   # requires a WRDS subscription; one Duo push
python tests/test_universe.py
```

CRSP and Compustat data are licensed and gitignored. The pull script regenerates
`data/` for anyone with their own WRDS access.

## Why this is not another factor-replication clone

Most public versions of this study run decile sorts on a few dozen names and skip the
corrections that actually move the numbers. This one applies them explicitly:

- **Delisting returns** spliced in, with Shumway (1997) substitution for
  performance-related delistings that CRSP records without a return. Omitting these is
  the largest single upward bias in retail factor replications.
- **NYSE breakpoints** for decile cutoffs rather than full-universe quantiles, so
  microcaps do not manufacture untradeable spreads.
- **Name history applied period by period**, so a stock that changed share class or
  exchange is filtered correctly in each month rather than by its final record.
- **Company-level market equity**, summed across share classes per Fama-French.
- **Multiple-testing correction** (Harvey-Liu-Zhu t > 3.0 and Benjamini-Hochberg FDR)
  across the six signals tested.
- **A published regime benchmark** (Daniel-Moskowitz 2016) that the HMM has to beat
  before its complexity is justified.

A null result is an acceptable outcome and the pre/post-2003 split is part of the
design, not a robustness afterthought. See `PHASE_PLAN.md`.
