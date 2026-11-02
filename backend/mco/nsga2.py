"""Власна векторизована реалізація генетичного алгоритму NSGA-II (Deb et al., 2002).

Особливості: недоміноване сортування через матрицю домінування NumPy,
обмеження враховуються правилом constraint-domination (допустимий розв’язок
завжди кращий за недопустимий, серед недопустимих кращий той, що менше
порушує обмеження), оператори SBX-схрещування та поліноміальної мутації.
"""
import numpy as np


def dominance_matrix(F, CV=None):
    """D[i, j] = True, якщо розв’язок i домінує j (усі цілі мінімізуються)."""
    le = np.all(F[:, None, :] <= F[None, :, :], axis=2)
    lt = np.any(F[:, None, :] < F[None, :, :], axis=2)
    D = le & lt
    if CV is not None:
        feas = CV <= 0
        both = feas[:, None] & feas[None, :]
        D = np.where(both, D, False)
        D |= feas[:, None] & ~feas[None, :]
        D |= (~feas[:, None]) & (~feas[None, :]) & (CV[:, None] < CV[None, :])
    return D


def non_dominated_fronts(F, CV=None):
    """Розбиття на фронти: список масивів індексів (фронт 0 – недоміновані)."""
    D = dominance_matrix(F, CV)
    count = D.sum(axis=0).astype(int)        # скільки розв’язків домінує j
    fronts = []
    current = np.where(count == 0)[0]
    done = np.zeros(len(F), dtype=bool)
    while current.size:
        fronts.append(current)
        done[current] = True
        count = count - D[current].sum(axis=0)
        current = np.where((count == 0) & ~done)[0]
    return fronts


def crowding_distance(F):
    """Відстань скупченості для точок одного фронту."""
    n, k = F.shape
    if n <= 2:
        return np.full(n, np.inf)
    d = np.zeros(n)
    for j in range(k):
        order = np.argsort(F[:, j])
        f = F[order, j]
        rng = f[-1] - f[0]
        d[order[0]] = d[order[-1]] = np.inf
        if rng > 0:
            d[order[1:-1]] += (f[2:] - f[:-2]) / rng
    return d


def _sbx(P1, P2, lo, hi, eta, pc, rng):
    """SBX-схрещування з урахуванням меж змінних (Deb, Agrawal, 1995)."""
    y1, y2 = np.minimum(P1, P2), np.maximum(P1, P2)
    diff = np.maximum(y2 - y1, 1e-14)
    u = rng.random(P1.shape)

    def betaq(beta):
        alpha = 2.0 - beta ** -(eta + 1)
        return np.where(u <= 1.0 / alpha, (u * alpha) ** (1 / (eta + 1)),
                        (1.0 / np.maximum(2.0 - u * alpha, 1e-14)) ** (1 / (eta + 1)))

    c1 = 0.5 * (y1 + y2 - betaq(1 + 2 * (y1 - lo) / diff) * diff)
    c2 = 0.5 * (y1 + y2 + betaq(1 + 2 * (hi - y2) / diff) * diff)
    c1, c2 = np.clip(c1, lo, hi), np.clip(c2, lo, hi)
    swap = rng.random(P1.shape) < 0.5
    c1, c2 = np.where(swap, c2, c1), np.where(swap, c1, c2)
    # кожна змінна схрещується з імовірністю 0,5, пара – з імовірністю pc
    mask = (rng.random(P1.shape) < 0.5) & (rng.random(len(P1)) < pc)[:, None] & (y2 - y1 > 1e-14)
    return np.where(mask, c1, P1), np.where(mask, c2, P2)


def _mutate(X, lo, hi, eta, pm, rng):
    """Поліноміальна мутація з урахуванням меж змінних."""
    span = np.where(hi > lo, hi - lo, 1.0)
    d1, d2 = (X - lo) / span, (hi - X) / span
    u = rng.random(X.shape)
    p = 1.0 / (eta + 1)
    left = (2 * u + (1 - 2 * u) * (1 - d1) ** (eta + 1)) ** p - 1
    right = 1 - (2 * (1 - u) + 2 * (u - 0.5) * (1 - d2) ** (eta + 1)) ** p
    delta = np.where(u < 0.5, left, right)
    mask = rng.random(X.shape) < pm
    return np.clip(X + np.where(mask, delta * span, 0.0), lo, hi)


def _rank_and_crowding(F, CV):
    rank = np.empty(len(F), dtype=int)
    crowd = np.empty(len(F))
    fronts = non_dominated_fronts(F, CV)
    for r, fr in enumerate(fronts):
        rank[fr] = r
        crowd[fr] = crowding_distance(F[fr])
    return rank, crowd, fronts


def nsga2(evaluate, lo, hi, pop_size=100, generations=100, pc=0.9, eta_c=15.0,
          pm=None, eta_m=20.0, seed=0, record_history=True, progress=None):
    """Запуск NSGA-II.

    evaluate(X) -> (F, CV): F – матриця N×k цілей (мінімізуються), CV – сумарне
    порушення обмежень (0 – допустимий). Повертає словник з фінальною популяцією,
    недомінованими розв’язками та історією фронтів по поколіннях.
    progress(покоління, усього) викликається після кожного покоління.
    """
    lo, hi = np.asarray(lo, dtype=float), np.asarray(hi, dtype=float)
    if not (np.isfinite(lo).all() and np.isfinite(hi).all()):
        raise ValueError('Для NSGA-II всі змінні повинні мати скінченні межі')
    if (hi < lo).any():
        raise ValueError('Нижня межа змінної більша за верхню')
    pop_size = int(pop_size) + int(pop_size) % 2      # парний розмір популяції
    if pop_size < 4:
        raise ValueError('Розмір популяції має бути не меншим за 4')
    n = len(lo)
    pm = 1.0 / n if pm is None else float(pm)
    rng = np.random.default_rng(seed)

    X = lo + rng.random((pop_size, n)) * (hi - lo)
    F, CV = evaluate(X)
    rank, crowd, _ = _rank_and_crowding(F, CV)
    history = []
    evaluations = pop_size

    for gen in range(int(generations)):
        if progress:
            progress(gen, int(generations))
        # бінарний турнір: менший ранг, за рівності – більша скупченість
        a, b = rng.integers(0, pop_size, (2, pop_size))
        better_a = (rank[a] < rank[b]) | ((rank[a] == rank[b]) & (crowd[a] > crowd[b]))
        parents = np.where(better_a, a, b)
        P1, P2 = X[parents[0::2]], X[parents[1::2]]
        C1, C2 = _sbx(P1, P2, lo, hi, eta_c, pc, rng)
        Q = _mutate(np.vstack([C1, C2]), lo, hi, eta_m, pm, rng)
        FQ, CVQ = evaluate(Q)
        evaluations += len(Q)

        # елітарний відбір із об’єднаної популяції батьків і нащадків
        XR, FR, CVR = np.vstack([X, Q]), np.vstack([F, FQ]), np.concatenate([CV, CVQ])
        fronts = non_dominated_fronts(FR, CVR)
        chosen = []
        for fr in fronts:
            if len(chosen) + len(fr) <= pop_size:
                chosen.extend(fr)
            else:
                cd = crowding_distance(FR[fr])
                chosen.extend(fr[np.argsort(-cd)[:pop_size - len(chosen)]])
                break
        chosen = np.asarray(chosen)
        X, F, CV = XR[chosen], FR[chosen], CVR[chosen]
        rank, crowd, fr_now = _rank_and_crowding(F, CV)
        if record_history:
            first = fr_now[0]
            history.append(F[first][CV[first] <= 0].copy())

    feasible = CV <= 0
    first = non_dominated_fronts(F, CV)[0]
    first = first[feasible[first]]
    return {'X': X, 'F': F, 'CV': CV, 'front_X': X[first], 'front_F': F[first],
            'history': history, 'evaluations': evaluations, 'feasible_share': float(feasible.mean())}


def hypervolume_2d(F, ref):
    """Гіперобʼєм (площа, домінована фронтом) для двох мінімізованих цілей."""
    F = np.asarray(F, dtype=float)
    F = F[(F[:, 0] < ref[0]) & (F[:, 1] < ref[1])]
    if not len(F):
        return 0.0
    F = F[np.argsort(F[:, 0])]
    hv, best_f2 = 0.0, ref[1]
    for f1, f2 in F:
        if f2 < best_f2:
            hv += (ref[0] - f1) * (best_f2 - f2)
            best_f2 = f2
    return hv
