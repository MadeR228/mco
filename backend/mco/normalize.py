"""Нормалізація матриці рішень.

Усі функції приймають матрицю X (m альтернатив × n критеріїв) і вектор напрямів
senses (+1 – критерій максимізується, −1 – мінімізується) та повертають матрицю
тієї ж форми, у якій більше значення завжди краще (крім vector – див. нижче).
"""
import numpy as np


def as_senses(senses):
    """Перетворює ['max', 'min', ...] або [1, -1, ...] на масив ±1."""
    out = []
    for s in senses:
        if isinstance(s, str):
            s = s.strip().lower()
            if s not in ('max', 'min'):
                raise ValueError(f'Напрям критерію має бути max або min, отримано «{s}»')
            out.append(1 if s == 'max' else -1)
        else:
            out.append(1 if s > 0 else -1)
    return np.asarray(out, dtype=int)


def minmax(X, senses):
    """r = (x − min)/(max − min) для max-критеріїв і (max − x)/(max − min) для min-критеріїв.

    Якщо всі значення критерію однакові, він не розрізняє альтернативи: r = 1.
    """
    X = np.asarray(X, dtype=float)
    lo, hi = X.min(axis=0), X.max(axis=0)
    rng = hi - lo
    safe = np.where(rng > 0, rng, 1.0)
    R = np.where(np.asarray(senses) > 0, (X - lo) / safe, (hi - X) / safe)
    R[:, rng == 0] = 1.0
    return R


def linear_max(X, senses):
    """r = x/max для max-критеріїв і min/x для min-критеріїв (потрібні додатні значення)."""
    X = np.asarray(X, dtype=float)
    if (X <= 0).any():
        raise ValueError('Лінійна нормалізація x/max потребує додатних значень усіх критеріїв')
    return np.where(np.asarray(senses) > 0, X / X.max(axis=0), X.min(axis=0) / X)


def vector(X):
    """Векторна нормалізація x/‖x‖ (використовується в TOPSIS; напрям не змінюється)."""
    X = np.asarray(X, dtype=float)
    norm = np.linalg.norm(X, axis=0)
    return X / np.where(norm > 0, norm, 1.0)


NORMALIZATIONS = {
    'minmax': ('лінійна (min–max)', minmax),
    'linear_max': ('відносна (x/max, min/x)', linear_max),
}


def normalize(X, senses, kind='minmax'):
    if kind not in NORMALIZATIONS:
        raise ValueError(f'Невідомий тип нормалізації: {kind}')
    return NORMALIZATIONS[kind][1](X, senses)
