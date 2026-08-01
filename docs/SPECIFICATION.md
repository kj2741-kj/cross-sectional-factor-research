# Study specification

Exact construction of every universe, signal, portfolio and strategy in this
repo. Numbers here are measured from the built data, not intended values.

---

## 1. Universe

**Source:** CRSP monthly stock file (`crsp.msf`), 1961-2024 pulled, 1963-2024 used.

**Filters, in order applied:**

| Step | Rule | Rows remaining |
|---|---|---|
| Raw pull | `date` 1961-2024 | 4,789,942 |
| Name-history merge | valid `namedt <= date <= nameendt` | 4,728,936 |
| Share code | `SHRCD` in (10, 11) = ordinary common shares | 3,514,699 |
| Exchange | `EXCHCD` in (1, 2, 3) = NYSE, AMEX, NASDAQ | 3,453,430 |
| Sample window | 1963-01 to 2024-12 | **3,421,715** |

**Result:** 26,200 unique stocks, 744 months, ~4,100 stocks per month with a
usable signal.

**What is excluded and why.** The share-code filter removes ETFs, closed-end
funds, ADRs, REITs, units, SBIs and trusts. Those are not operating companies,
their book equity is not comparable, and including them contaminates value and
profitability sorts. The exchange filter removes OTC and non-major listings.

Filters are applied through the **name history**, period by period, so a stock
that changed share class or exchange is treated correctly in each month rather
than by its final record.

**Delisting returns.** Spliced from `crsp.msedelist` (2,698 used). Where CRSP
records a performance-related delisting code (500, 520-584) but no return,
Shumway's substitution applies: -30% listed, -55% NASDAQ (99 cases).

**Market equity.** `|prc| * shrout / 1000`, in $ millions, summed across share
classes within a `permco` and assigned to the largest permno (Fama-French
convention). Negative prices are bid/ask midpoints, not errors.

---

## 2. The six factors

| Signal | Definition | Source | Direction |
|---|---|---|---|
| **size** | Market equity at June of formation year | CRSP | Long **small** |
| **value** | Book equity (FY t-1) / market equity (Dec t-1) | Compustat + CRSP | Long **high** B/M |
| **mom** | Cumulative return months t-12 to t-2 | CRSP | Long **winners** |
| **prof** | (REVT - COGS - XSGA - XINT) / book equity | Compustat | Long **robust** |
| **inv** | (AT_t - AT_t-1) / AT_t-1, asset growth | Compustat | Long **conservative** |
| **rev** | Return in month t-1 | CRSP | Long **losers** |

**Book equity** uses the FF fallback hierarchy: shareholders' equity (`SEQ`, else
`CEQ + PSTK`, else `AT - LT`) plus deferred taxes (`TXDITC`, else `TXDB + ITCB`)
minus preferred stock (`PSTKRV`, else `PSTKL`, else `PSTK`). Negative book equity
is excluded, not winsorised.

**Momentum skips month t-1** deliberately. Including it blends momentum with
short-term reversal, which is a distinct and opposite-signed effect, weakening
both.

**Idiosyncratic volatility was dropped** in favour of short-term reversal. Idio
vol is normally estimated from daily returns within the month (Ang et al. 2006);
a monthly-data proxy measures a different quantity and would not be comparable
to the published factor.

**Coverage:**

| Signal | First usable | Observations | Stocks |
|---|---|---|---|
| size | 1963-07 | 3,191,309 | 25,480 |
| value | 1964-07 | 2,679,219 | 21,294 |
| mom | 1964-01 | 3,025,545 | 24,622 |
| prof | 1963-01 | 2,692,773 | 21,272 |
| inv | 1963-07 | 2,740,168 | 21,244 |
| rev | 1963-02 | 3,319,095 | 25,965 |

The Compustat-based signals cover ~21,000 stocks against CRSP's 26,000: the gap
is firms CRSP carries that Compustat does not, mostly small and early-sample.

---

## 3. Trading frequency

**Two rebalancing schedules, chosen by what drives the signal.**

| Signal | Rebalance | Rationale |
|---|---|---|
| size, value, prof, inv | **Annual, end of June** | Inputs are annual fundamentals. Re-sorting monthly would re-rank stale numbers. |
| mom, rev | **Monthly** | Inputs change every month. |

Annual signals are sorted once in June on the June cross-section, then **held
July through the following June**.

**Measured turnover by calendar month confirms this holds in the built data**
(one-way, both legs, value-weighted):

| Month | value | inv | mom | rev |
|---|---|---|---|---|
| Jan-Jun | 0.6-1.3% | 0.6-1.9% | 67-74% | 180-184% |
| **Jul** | **76.1%** | **158.4%** | 62.5% | 182.0% |
| Aug-Dec | 0.5-1.0% | 0.7-1.1% | 69-76% | 182-183% |

Value and investment trade essentially only in July. Momentum replaces roughly
70% of both legs every month. Reversal replaces ~182%, meaning the book turns
over nearly twice monthly, which is why costs destroy it.

**Fama-French timing.** Fiscal year ending in calendar year t-1 maps to returns
July of year t through June of t+1. Market equity for book-to-market comes from
December of t-1. The lag exists so the fundamentals were actually public;
shortening it is look-ahead bias.

---

## 4. Portfolio construction

**Deciles on NYSE breakpoints.** Cutoffs are computed on NYSE-listed stocks only
(`EXCHCD == 1`), then applied to the whole universe. Full-universe quantiles
would put thousands of AMEX/NASDAQ microcaps into the extreme deciles and
manufacture untradeable spreads.

**Long-short = decile 10 minus decile 1**, oriented so a positive number is the
documented bet. Size and investment are inverted (long the bottom decile), since
small firms and conservative investors are the documented winners.

**Weighting.** Both value-weighted (by **lagged** market equity, so the month's
own return does not set its own weight) and equal-weighted are produced. The gap
between them is the microcap-dependence diagnostic.

**Actual holdings per month:**

| Signal | Long leg (names) | Short leg (names) | Long leg $bn | Short leg $bn |
|---|---|---|---|---|
| size | 1,967 | 152 | 98 | 6,542 |
| value | 443 | 503 | 264 | 2,725 |
| mom | 554 | 757 | 1,214 | 322 |
| prof | 274 | 875 | 1,437 | 409 |
| inv | 540 | 583 | 456 | 1,051 |
| rev | 743 | 638 | 532 | 791 |

The size row shows the structural asymmetry NYSE breakpoints create: 1,967 small
names worth $98bn against 152 large names worth $6,542bn, a 67x market-cap gap
between legs. This is inherent to the size factor, not a construction error.

---

## 5. Industries

**Fama-French 12-industry classification** from CRSP `SICCD`.

BusEq (tech), Money (finance), Manuf, Shops (retail), Hlth, NoDur, Enrgy, Utils,
Telcm, Chems, Durbl, Other.

**Universe composition** (share of market cap, 2015+): tech 30.5%, finance
14.3%, Other 14.3%, healthcare 8.6%, retail 8.4%, manufacturing 6.0%, consumer
non-durables 4.2%, energy 3.5%, telecoms 3.2%, utilities 3.1%, chemicals 2.8%,
durables 0.9%.

**Industry concentration of the extreme deciles:**

| | Value: cheap decile | Value: expensive decile | Gap |
|---|---|---|---|
| Finance | 19.3% | 4.3% | +15.0pp |
| Tech | 8.9% | 23.0% | -14.1pp |
| Healthcare | 3.1% | 17.1% | -13.9pp |

Momentum's largest industry gap is 3.5pp. A pooled value sort is substantially a
long-banks, short-tech-and-biotech position; momentum is close to industry
neutral already.

---

## 6. Complete inventory of strategies tested

**Stock-level long-short (6 signals x 2 weightings = 12):** every signal in
section 2, value- and equal-weighted, full sample and split at 2003, gross and
net of costs.

**Industry-neutral variant (1):** momentum standardised within industry each
month, then sorted. Tests Moskowitz-Grinblatt.

**Sector-level long-short (5):** 12 FF industries ranked, long top 3 / short
bottom 3, monthly rebalance. Signals: sector momentum (12-2 on industry
portfolios), sector value, sector profitability, sector investment, and an
equal-weighted composite of all four. Sector fundamentals are **time-series
z-scored against each industry's own 10-year history**, not cross-sectionally,
because cross-sectional sector book-to-market is a permanent structural tilt
(banks are always cheap on book) rather than a signal.

**Regime overlays (2 methods x 2 applications):** Daniel-Moskowitz ex-ante
bear/high-vol rule, and a 2-state Gaussian HMM on market return and trailing
volatility. Applied to stock-level momentum and to the sector composite. HMM
labels come from an **expanding-window refit** (20-year minimum training,
refit annually) so they are genuine forecasts, not in-sample fits.

**Benchmarks:** FF3 and FF5 monthly factors from the Ken French Data Library for
alpha attribution.

---

## 7. Costs

One-way effective-spread schedule, anchored on US market structure:

| Period | bps | Reason |
|---|---|---|
| 1963-1975 | 125 | Fixed NYSE commissions, eighths |
| 1975-1990 | 70 | Negotiated commissions from May 1975 |
| 1990-1997 | 40 | |
| 1997-2001 | 25 | Sixteenths |
| 2001-2010 | 12 | Decimalisation |
| 2010+ | 6 | Electronic competition |

Equal-weighted portfolios pay **3.5x** for their microcap tilt. Sector ETF
execution is **4bps**.

Turnover is measured from actual month-to-month holdings after drifting prior
weights by their own returns, so passive weight movement is not counted as
trading.

**Not modelled:** market impact. These are effective-spread costs only and
describe a modest book. At institutional scale, momentum's 70% monthly turnover
across ~1,300 names would incur impact the sector strategy structurally avoids.
Also not modelled: shorting costs and borrow availability, which are most
binding in exactly the small-cap short legs the equal-weighted results depend on.
