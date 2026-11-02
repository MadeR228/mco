"""Аналіз чутливості результату до ваг критеріїв."""
import numpy as np

from .discrete import METHODS, normalize_weights


def sweep_weights(w, k, t):
    """Вага критерію k дорівнює t, решта пропорційно ділять 1 − t."""
    w = normalize_weights(w)
    rest = np.delete(w, k)
    rest = rest / rest.sum() if rest.sum() > 0 else np.full(len(rest), 1 / len(rest))
    return np.insert(rest * (1 - t), k, t)


def weight_sweep(method, X, senses, w, k, steps=21, **params):
    """Значення узагальненого критерію і переможець при зміні ваги критерію k від 0 до 1."""
    ts = np.linspace(0, 1, int(steps))
    func = METHODS[method].func
    scores, winners = [], []
    for t in ts:
        r = func(X, senses, sweep_weights(w, k, t), **params)
        scores.append(r.score)
        winners.append(r.best)
    return ts, np.array(scores), np.array(winners), func(X, senses, w, **params).higher_is_better


def rank_acceptability(method, X, senses, w, samples=1000, concentration=30.0, seed=0, **params):
    """Стохастичний аналіз: ваги ~ Діріхле(concentration·w).

    Повертає матрицю P[a, r] – частку випробувань, у яких альтернатива a посіла
    місце r + 1. Що більше concentration, то ближче випадкові ваги до заданих.
    """
    rng = np.random.default_rng(seed)
    w = normalize_weights(w)
    alpha = np.maximum(w * float(concentration), 1e-3)
    W = rng.dirichlet(alpha, size=int(samples))
    m = len(X)
    P = np.zeros((m, m))
    func = METHODS[method].func
    for wi in W:
        r = func(X, senses, wi, **params).rank
        P[np.arange(m), np.clip(r - 1, 0, m - 1)] += 1
    return P / len(W)
