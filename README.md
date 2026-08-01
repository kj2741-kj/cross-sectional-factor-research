# Regime-Conditional Cross-Sectional Factor Research

Do standard cross-sectional equity factor premia survive a proper multiple-testing
hurdle on a full CRSP universe, and does conditioning on market regime improve them
beyond what a simple published rule already achieves?

Full scope, methodology decisions and phase status in [`PHASE_PLAN.md`](PHASE_PLAN.md).

## Status

- **P0 complete** — CRSP universe built: 3,421,715 monthly observations, 26,200 stocks,
  744 months (1963-01 to 2024-12). 16 tests passing.
- P1-P8 pending.

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
