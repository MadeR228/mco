"""Способи визначення ваг критеріїв."""
import numpy as np

from .normalize import minmax

# Випадковий індекс узгодженості Сааті для n = 1..15
RANDOM_INDEX = (0, 0, 0.58, 0.90, 1.12, 1.24, 1.32, 1.41, 1.45, 1.49, 1.51, 1.48, 1.56, 1.57, 1.59)

SAATY_SCALE = {1: 'однаково важливі', 3: 'помірна перевага', 5: 'суттєва перевага',
               7: 'значна перевага', 9: 'абсолютна перевага'}


def equal(n):
    return np.full(n, 1.0 / n)


def rank_order_centroid(order):
    """Ваги за рангом важливості (ROC): wₖ = (1/n)·Σᵢ₌ₖⁿ 1/i, order – індекси від найважливішого."""
    n = len(order)
    roc = np.array([sum(1.0 / i for i in range(k, n + 1)) / n for k in range(1, n + 1)])
    w = np.empty(n)
    w[list(order)] = roc
    return w


def ahp(A):
    """Метод аналізу ієрархій Сааті.

    A – обернено-симетрична матриця парних порівнянь (aᵢⱼ = 1/aⱼᵢ). Ваги – головний
    власний вектор; узгодженість: CI = (λmax − n)/(n − 1), CR = CI/RI (прийнятно CR ≤ 0,1).
    Повертає (ваги, λmax, CI, CR).
    """
    A = np.asarray(A, dtype=float)
    n = A.shape[0]
    if A.shape != (n, n) or (A <= 0).any():
        raise ValueError('Матриця парних порівнянь має бути квадратною з додатними елементами')
    if not np.allclose(A * A.T, 1.0, atol=1e-6):
        raise ValueError('Матриця парних порівнянь має бути обернено-симетричною: aᵢⱼ·aⱼᵢ = 1')
    vals, vecs = np.linalg.eig(A)
    k = int(np.argmax(vals.real))
    w = np.abs(vecs[:, k].real)
    w /= w.sum()
    lam = float(vals[k].real)
    ci = (lam - n) / (n - 1) if n > 2 else 0.0
    ri = RANDOM_INDEX[n - 1] if n <= len(RANDOM_INDEX) else RANDOM_INDEX[-1]
    cr = ci / ri if ri > 0 else 0.0
    return w, lam, ci, cr


def ahp_matrix_from_upper(upper, n):
    """Будує повну матрицю з елементів над діагоналлю {(i, j): aᵢⱼ}."""
    A = np.ones((n, n))
    for (i, j), a in upper.items():
        A[i, j] = a
        A[j, i] = 1.0 / a
    return A


def entropy(X, senses):
    """Об’єктивні ваги за ентропією Шеннона: більша розкиданість критерію – більша вага."""
    R = minmax(X, senses) + 1e-9
    P = R / R.sum(axis=0)
    m = len(R)
    if m < 2:
        return equal(R.shape[1])
    E = -(P * np.log(P)).sum(axis=0) / np.log(m)
    d = 1 - E
    return d / d.sum() if d.sum() > 0 else equal(R.shape[1])


def critic(X, senses):
    """Метод CRITIC: вага ~ σⱼ·Σ(1 − rⱼₖ) (контрастність і незалежність критерію)."""
    R = minmax(X, senses)
    sd = R.std(axis=0)
    with np.errstate(invalid='ignore', divide='ignore'):
        C = np.corrcoef(R, rowvar=False)
    C = np.nan_to_num(np.atleast_2d(C), nan=0.0)
    info = sd * (1 - C).sum(axis=0)
    return info / info.sum() if info.sum() > 0 else equal(R.shape[1])
