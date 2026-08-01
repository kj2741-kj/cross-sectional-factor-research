#!/usr/bin/env python
# coding: utf-8
"""
P5: market regime detection, two ways.

The point of building both is that the HMM has to earn its complexity. Daniel
and Moskowitz (2016) already showed momentum crashes can be anticipated with a
rule anyone can compute in a spreadsheet: is the market down over two years, and
is volatility high. If a latent-state model cannot beat that, the honest
conclusion is to use the rule.

Everything here is **ex ante**. Every indicator at month t uses information
through month t-1 only. This is the single easiest place in the whole study to
accidentally produce a spectacular result: a regime label fitted with knowledge
of the returns it is used to predict will "forecast" crashes perfectly and mean
nothing.

References
----------
Daniel, K. and Moskowitz, T. (2016). "Momentum Crashes." JFE 122(2), 221-247.
Hamilton, J. (1989). "A New Approach to the Economic Analysis of Nonstationary
    Time Series and the Business Cycle." Econometrica 57(2).
"""
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Daniel-Moskowitz style ex-ante indicators
# ---------------------------------------------------------------------------

def dm_indicators(mkt_excess, bear_window=24, vol_window=12,
                  vol_median_window=120):
    """Bear-market and high-volatility flags, both strictly ex ante.

    bear      cumulative market return over the prior `bear_window` months < 0
    high_vol  trailing volatility above its own trailing median
    panic     both at once, which is Daniel-Moskowitz's crash state

    The volatility threshold is a trailing median rather than a full-sample one.
    Using the full-sample median would leak the future distribution of
    volatility into a 1960s observation.
    """
    m = pd.Series(mkt_excess).astype(float).sort_index()

    # Shift by one so month t sees only data through t-1.
    cum = (1 + m).rolling(bear_window).apply(np.prod, raw=True) - 1
    bear = (cum.shift(1) < 0)

    vol = m.rolling(vol_window).std().shift(1)
    vol_med = vol.rolling(vol_median_window, min_periods=36).median()
    high_vol = vol > vol_med

    out = pd.DataFrame({
        "cum_2y": cum.shift(1),
        "vol": vol,
        "vol_median": vol_med,
        "bear": bear.fillna(False),
        "high_vol": high_vol.fillna(False),
    })
    out["panic"] = out["bear"] & out["high_vol"]
    # Undefined until all the trailing windows are available.
    warm = out["vol_median"].isna() | out["cum_2y"].isna()
    out.loc[warm, ["bear", "high_vol", "panic"]] = False
    out["valid"] = ~warm
    return out


# ---------------------------------------------------------------------------
# Hidden Markov model
# ---------------------------------------------------------------------------

def fit_hmm(observations, n_states=2, seed=0, n_iter=200):
    """Fit a Gaussian HMM and return (model, state sequence, ordered mapping).

    States are relabelled by mean return, ascending, so state 0 is always the
    worst. Raw HMM state indices are arbitrary and change between fits, which
    makes any hard-coded interpretation of "state 1" unreliable.
    """
    from hmmlearn.hmm import GaussianHMM

    X = np.asarray(observations, dtype=float)
    if X.ndim == 1:
        X = X.reshape(-1, 1)

    model = GaussianHMM(n_components=n_states, covariance_type="full",
                        n_iter=n_iter, random_state=seed)
    model.fit(X)
    states = model.predict(X)

    order = np.argsort(model.means_[:, 0])
    remap = {old: new for new, old in enumerate(order)}
    return model, np.array([remap[s] for s in states]), remap


def hmm_regimes(mkt_excess, n_states=2, vol_window=12, seed=0):
    """Full-sample HMM regimes on market return and trailing volatility.

    In-sample and descriptive only. Use `hmm_regimes_expanding` for anything
    that feeds a strategy, because this version has seen the whole series.
    """
    m = pd.Series(mkt_excess).astype(float).sort_index()
    vol = m.rolling(vol_window).std().shift(1)
    df = pd.DataFrame({"ret": m, "vol": vol}).dropna()

    _, states, _ = fit_hmm(df.values, n_states=n_states, seed=seed)
    return pd.Series(states, index=df.index, name="hmm_state")


def hmm_regimes_expanding(mkt_excess, n_states=2, vol_window=12,
                          min_train=240, refit_every=12, seed=0):
    """Out-of-sample HMM state labels from an expanding window.

    At each refit the model sees only data up to that point, and the labels it
    assigns to subsequent months are genuine forecasts. This is materially
    harder than the in-sample version and usually looks worse, which is the
    point of computing it.

    `min_train=240` (20 years) because a two-state Gaussian HMM fitted on a
    short sample tends to latch onto one volatile episode.
    """
    m = pd.Series(mkt_excess).astype(float).sort_index()
    vol = m.rolling(vol_window).std().shift(1)
    df = pd.DataFrame({"ret": m, "vol": vol}).dropna()

    labels = pd.Series(np.nan, index=df.index, name="hmm_state_oos")
    n = len(df)
    if n <= min_train:
        return labels

    for start in range(min_train, n, refit_every):
        train = df.iloc[:start]
        try:
            model, _, remap = fit_hmm(train.values, n_states=n_states, seed=seed)
        except Exception:
            continue
        stop = min(start + refit_every, n)
        # Decode the full history then keep only the out-of-sample tail, so the
        # Viterbi path respects the transition structure rather than treating
        # each new month as independent.
        block = df.iloc[:stop]
        raw = model.predict(block.values)[start:stop]
        labels.iloc[start:stop] = [remap[s] for s in raw]
    return labels


def describe_regimes(mkt_excess, labels, name="regime"):
    """Economic characterisation of each regime: are the states meaningful?"""
    m = pd.Series(mkt_excess).astype(float)
    lab = pd.Series(labels).dropna()
    idx = m.index.intersection(lab.index)
    df = pd.DataFrame({"ret": m.loc[idx], name: lab.loc[idx]})

    g = df.groupby(name)["ret"]
    out = pd.DataFrame({
        "months": g.size(),
        "share": g.size() / len(df),
        "mean_pct": g.mean() * 100,
        "vol_pct": g.std() * 100,
        "ann_ret_pct": g.mean() * 12 * 100,
        "ann_vol_pct": g.std() * np.sqrt(12) * 100,
    })
    out["sharpe"] = out["ann_ret_pct"] / out["ann_vol_pct"]

    # Persistence: a regime label that flips every month is describing noise,
    # not a regime.
    s = df[name]
    out["persistence"] = [float((s.shift(1) == k)[s == k].mean()) for k in out.index]
    return out
