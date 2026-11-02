"""Методи багатокритеріального вибору зі скінченної множини альтернатив.

Кожен метод має сигнатуру method(X, senses, w, **params) -> Result, де
  X      – матриця рішень m×n (рядки – альтернативи, стовпці – критерії);
  senses – масив ±1 (max / min);
  w      – ваги критеріїв (нормуються до суми 1).
Методи векторизовані засобами NumPy: один прохід по матриці без циклів Python
за альтернативами, тому працюють і для десятків тисяч альтернатив.
"""
import time
from dataclasses import dataclass, field

import numpy as np

from .normalize import minmax, normalize, vector


@dataclass
class Param:
    """Опис параметра методу – за ним інтерфейс сам будує віджет."""
    name: str
    label: str
    kind: str                 # 'float' | 'int' | 'choice' | 'criterion' | 'order' | 'per_criterion'
    default: object = None
    min: float | None = None
    max: float | None = None
    step: float | None = None
    options: tuple = ()
    help: str = ''


@dataclass
class Result:
    method: str
    score: np.ndarray                 # значення узагальненого критерію (NaN – альтернатива відкинута)
    higher_is_better: bool
    info: dict = field(default_factory=dict)
    elapsed_ms: float = 0.0
    rank: np.ndarray = None           # 1 – найкраща альтернатива

    def __post_init__(self):
        if self.rank is None:
            self.rank = rank_scores(self.score, self.higher_is_better)

    @property
    def best(self):
        """Індекс найкращої альтернативи (None, якщо допустимих немає)."""
        ok = ~np.isnan(self.score)
        return int(np.argmin(np.where(ok, self.rank, np.inf))) if ok.any() else None


def rank_scores(score, higher_is_better=True):
    """Ранги 1..m (однакові значення отримують однаковий найкращий ранг, NaN – останні)."""
    s = np.asarray(score, dtype=float)
    key = np.where(np.isnan(s), np.inf, -s if higher_is_better else s)
    order = np.argsort(key, kind='stable')
    rank = np.empty(len(s), dtype=int)
    rank[order] = np.arange(1, len(s) + 1)
    # однакові значення – однаковий ранг
    sorted_key = key[order]
    for i in range(1, len(s)):
        if sorted_key[i] == sorted_key[i - 1]:
            rank[order[i]] = rank[order[i - 1]]
    return rank


def normalize_weights(w, n=None):
    w = np.asarray(w, dtype=float)
    if n is not None and len(w) != n:
        raise ValueError(f'Кількість ваг ({len(w)}) не дорівнює кількості критеріїв ({n})')
    if np.isnan(w).any() or (w < 0).any():
        raise ValueError('Ваги критеріїв мають бути невід’ємними числами')
    if w.sum() <= 0:
        raise ValueError('Сума ваг має бути більшою за нуль')
    return w / w.sum()


def _check(X, senses, w):
    X = np.asarray(X, dtype=float)
    if X.ndim != 2 or X.shape[0] == 0 or X.shape[1] == 0:
        raise ValueError('Матриця рішень порожня: потрібна хоча б одна альтернатива і один критерій')
    if not np.isfinite(X).all():
        raise ValueError('Матриця рішень містить порожні або нечислові значення')
    senses = np.asarray(senses)
    if len(senses) != X.shape[1]:
        raise ValueError('Кількість напрямів не дорівнює кількості критеріїв')
    return X, senses, normalize_weights(w, X.shape[1])


# ---------------------------------------------------------------------------
# Множина Парето
# ---------------------------------------------------------------------------
def pareto_mask(X, senses):
    """Маска недомінованих (Парето-оптимальних) альтернатив.

    Альтернатива a домінує b, якщо a не гірша за всіма критеріями і краща хоча б
    за одним. Алгоритм послідовно відкидає точки, домінувані поточною
    недомінованою, тому на практиці працює значно швидше за O(m²·n).
    """
    Y = np.asarray(X, dtype=float) * np.asarray(senses)     # усі критерії → max
    m = len(Y)
    # домінуюча точка має більшу суму критеріїв, тому перевірка в порядку спадання суми
    # відкидає більшість домінованих точок на перших ітераціях
    idx = np.argsort(-Y.sum(axis=1), kind='stable')
    cand = Y[idx]
    i = 0
    while i < len(cand):
        dominated = np.all(cand <= cand[i], axis=1) & np.any(cand < cand[i], axis=1)
        keep = ~dominated
        idx, cand = idx[keep], cand[keep]
        i = int(keep[:i].sum()) + 1
    mask = np.zeros(m, dtype=bool)
    mask[idx] = True
    return mask


def pareto_fronts(X, senses):
    """Номер фронту для кожної альтернативи (0 – множина Парето, 1 – наступний шар тощо)."""
    X = np.asarray(X, dtype=float)
    front = np.full(len(X), -1)
    rest = np.arange(len(X))
    k = 0
    while len(rest):
        mask = pareto_mask(X[rest], senses)
        front[rest[mask]] = k
        rest = rest[~mask]
        k += 1
    return front


def pareto(X, senses, w):
    """Метод Парето: альтернативи впорядковуються за номером фронту недомінованості."""
    X, senses, _ = _check(X, senses, w)
    front = pareto_fronts(X, senses)
    return Result('pareto', front.astype(float), False,
                  info={'pareto_count': int((front == 0).sum()), 'fronts': int(front.max()) + 1})


# ---------------------------------------------------------------------------
# Згортки
# ---------------------------------------------------------------------------
def weighted_sum(X, senses, w, normalization='minmax'):
    """Метод зваженої суми (адитивна згортка): F = Σ wⱼ·rⱼ → max."""
    X, senses, w = _check(X, senses, w)
    R = normalize(X, senses, normalization)
    return Result('weighted_sum', R @ w, True, info={'normalized': R})


def weighted_product(X, senses, w):
    """Мультиплікативна згортка: F = Π rⱼ^wⱼ → max (r – min–max, зсунуті в [0,01; 1])."""
    X, senses, w = _check(X, senses, w)
    R = 0.01 + 0.99 * minmax(X, senses)
    return Result('weighted_product', np.exp(np.log(R) @ w), True)


def ideal_point(X, senses, w, p=2.0):
    """Метод ідеальної точки (компромісний метод Тихонова).

    Найкраща альтернатива – найближча до утопічної точки (усі rⱼ = 1) у
    зваженій метриці Lp: d = (Σ (wⱼ(1 − rⱼ))^p)^(1/p) → min. p = 1 дає зважену
    суму відхилень, p = 2 – евклідову відстань, p = ∞ – метрику Чебишова.
    """
    X, senses, w = _check(X, senses, w)
    D = w * (1.0 - minmax(X, senses))
    p = float(p)
    if np.isinf(p):
        d = D.max(axis=1)
    else:
        if p < 1:
            raise ValueError('Параметр p метрики має бути ≥ 1')
        d = (D ** p).sum(axis=1) ** (1.0 / p)
    return Result('ideal_point', d, False, info={'p': p})


def germeier(X, senses, w):
    """Максимінна згортка Гермейєра: F = minⱼ rⱼ / wⱼ → max (критерії з нульовою вагою не враховуються).

    Оцінка альтернативи визначається її найслабшим (з урахуванням ваг) критерієм,
    тому метод вибирає збалансовані варіанти без провалів за окремими критеріями.
    """
    X, senses, w = _check(X, senses, w)
    R = minmax(X, senses)
    used = w > 0
    F = (R[:, used] / w[used]).min(axis=1)
    weakest = np.where(used)[0][(R[:, used] / w[used]).argmin(axis=1)]
    return Result('germeier', F, True, info={'weakest': weakest})


# ---------------------------------------------------------------------------
# Методи з порогами та пріоритетами
# ---------------------------------------------------------------------------
def main_criterion(X, senses, w, main=0, thresholds=None):
    """Метод головного критерію (ε-обмежень).

    Оптимізується один головний критерій, а решта переводяться в обмеження:
    xⱼ ≥ εⱼ для max-критеріїв і xⱼ ≤ εⱼ для min-критеріїв (εⱼ – у вихідних одиницях).
    """
    X, senses, w = _check(X, senses, w)
    n = X.shape[1]
    if not 0 <= int(main) < n:
        raise ValueError('Головний критерій не вибрано')
    main = int(main)
    feasible = np.ones(len(X), dtype=bool)
    for j, eps in (thresholds or {}).items():
        j = int(j)
        if j == main or eps is None or (isinstance(eps, float) and np.isnan(eps)):
            continue
        feasible &= X[:, j] >= eps if senses[j] > 0 else X[:, j] <= eps
    score = np.where(feasible, X[:, main], np.nan)          # значення головного критерію у вихідних одиницях
    return Result('main_criterion', score, bool(senses[main] > 0),
                  info={'feasible': int(feasible.sum()), 'main': main})


def lexicographic(X, senses, w, order=None, concession=0.0):
    """Лексикографічний метод і метод послідовних поступок.

    Критерії розглядаються в порядку важливості. На кожному кроці залишаються
    альтернативи, гірші за найкращу не більше ніж на поступку δ·(розмах критерію).
    δ = 0 – строгий лексикографічний метод.
    """
    X, senses, w = _check(X, senses, w)
    m, n = X.shape
    order = list(range(n)) if order is None else [int(j) for j in order]
    if sorted(order) != sorted(set(order)) or any(not 0 <= j < n for j in order):
        raise ValueError('Порядок критеріїв задано некоректно')
    Y = X * senses
    rng = np.ptp(Y, axis=0)
    stage = np.zeros(m, dtype=int)          # на якому кроці альтернативу відкинуто
    alive = np.ones(m, dtype=bool)
    steps = []
    for k, j in enumerate(order, start=1):
        best = Y[alive, j].max()
        keep = alive & (Y[:, j] >= best - float(concession) * rng[j] - 1e-12)
        stage[alive & ~keep] = k
        alive = keep
        steps.append(int(alive.sum()))
    stage[alive] = len(order) + 1
    # ранжування: пізніше відкинута – краща; далі – лексикографічно за значеннями
    keys = [Y[:, j] for j in reversed(order)] + [stage]
    order_idx = np.lexsort(keys)[::-1]
    score = np.empty(m)
    score[order_idx] = np.arange(m, 0, -1)
    return Result('lexicographic', score, True,
                  info={'remaining_after_step': steps, 'order': order})


def topsis(X, senses, w):
    """TOPSIS: близькість до позитивного і віддаленість від негативного ідеалу.

    V = w·X/‖X‖; A⁺, A⁻ – найкращі та найгірші значення; C = D⁻/(D⁺ + D⁻) → max.
    """
    X, senses, w = _check(X, senses, w)
    V = vector(X) * w
    pos = np.where(senses > 0, V.max(axis=0), V.min(axis=0))
    neg = np.where(senses > 0, V.min(axis=0), V.max(axis=0))
    d_pos = np.linalg.norm(V - pos, axis=1)
    d_neg = np.linalg.norm(V - neg, axis=1)
    denom = d_pos + d_neg
    C = np.where(denom > 0, d_neg / np.where(denom > 0, denom, 1), 1.0)
    return Result('topsis', C, True, info={'d_pos': d_pos, 'd_neg': d_neg})


def vikor(X, senses, w, v=0.5):
    """VIKOR: компроміс між «корисністю групи» S і «максимальним жалем» R.

    Q = v·(S − S*)/(S⁻ − S*) + (1 − v)·(R − R*)/(R⁻ − R*) → min.
    Додатково перевіряються умови прийнятної переваги (C1) і стабільності (C2).
    """
    X, senses, w = _check(X, senses, w)
    if not 0 <= float(v) <= 1:
        raise ValueError('Параметр v методу VIKOR має бути в межах [0; 1]')
    v = float(v)
    D = w * (1.0 - minmax(X, senses))
    S, R = D.sum(axis=1), D.max(axis=1)

    def scale(a):
        r = a.max() - a.min()
        return (a - a.min()) / r if r > 0 else np.zeros_like(a)

    Q = v * scale(S) + (1 - v) * scale(R)
    m = len(X)
    order = np.argsort(Q, kind='stable')
    info = {'S': S, 'R': R}
    if m >= 2:
        a1, a2 = order[0], order[1]
        dq = 1.0 / (m - 1)
        info['C1'] = bool(Q[a2] - Q[a1] >= dq)
        info['C2'] = bool(S[a1] == S.min() or R[a1] == R.min())
        if info['C1'] and info['C2']:
            info['compromise'] = [int(a1)]
        elif not info['C1']:
            info['compromise'] = [int(a) for a in order if Q[a] - Q[a1] < dq]
        else:
            info['compromise'] = [int(a1), int(a2)]
    return Result('vikor', Q, False, info=info)


def goal_programming(X, senses, w, targets=None, p=1.0):
    """Цільове програмування: мінімізація зважених недосягнень цілей.

    dⱼ = max(0, gⱼ − xⱼ)/розмах для max-критеріїв і max(0, xⱼ − gⱼ)/розмах для
    min-критеріїв; F = (Σ (wⱼdⱼ)^p)^(1/p) → min. Критерій без цілі не враховується.
    """
    X, senses, w = _check(X, senses, w)
    targets = targets or {}
    rng = np.ptp(X, axis=0)
    rng = np.where(rng > 0, rng, 1.0)
    D = np.zeros_like(X)
    used = np.zeros(X.shape[1], dtype=bool)
    for j, g in targets.items():
        j = int(j)
        if g is None or (isinstance(g, float) and np.isnan(g)):
            continue
        used[j] = True
        gap = (g - X[:, j]) if senses[j] > 0 else (X[:, j] - g)
        D[:, j] = np.maximum(gap, 0) / rng[j]
    if not used.any():
        raise ValueError('Для цільового програмування задайте ціль хоча б для одного критерію')
    WD = w * D
    p = float(p)
    F = WD.max(axis=1) if np.isinf(p) else (WD ** p).sum(axis=1) ** (1 / p)
    achieved = ((D == 0) | ~used).sum(axis=1) - (~used).sum()
    return Result('goal_programming', F, False,
                  info={'goals': int(used.sum()), 'achieved': achieved})


# ---------------------------------------------------------------------------
# Реєстр методів (за ним будується інтерфейс)
# ---------------------------------------------------------------------------
@dataclass
class MethodSpec:
    title: str
    func: object
    short: str
    params: list = field(default_factory=list)
    uses_weights: bool = True
    abbr: str = ''           # коротка назва для таблиць і графіків


METHODS = {
    'weighted_sum': MethodSpec(
        'Метод зваженої суми (адитивна згортка)', weighted_sum,
        'F = Σ wⱼ·rⱼ → max; найпростіша й найпоширеніша згортка, допускає компенсацію '
        'поганого значення одного критерію добрим значенням іншого.',
        [Param('normalization', 'Нормалізація', 'choice', 'minmax', options=('minmax', 'linear_max'),
               help='minmax – (x−min)/(max−min); linear_max – x/max для max-критеріїв і min/x для min')], abbr='Зважена сума'),
    'ideal_point': MethodSpec(
        'Метод ідеальної точки (Тихонова)', ideal_point,
        'Мінімізація зваженої відстані Lp до утопічної точки; p = ∞ – метрика Чебишова.',
        [Param('p', 'Параметр метрики p', 'choice', 2.0, options=(1.0, 2.0, 3.0, float('inf')),
               help='1 – манхеттенська, 2 – евклідова, ∞ – Чебишова (мінімізація найбільшого відхилення)')], abbr='Ідеальна точка'),
    'topsis': MethodSpec(
        'TOPSIS', topsis,
        'Відносна близькість до позитивного ідеалу та віддаленість від негативного.', abbr='TOPSIS'),
    'pareto': MethodSpec(
        'Метод Парето (недомінованість)', pareto,
        'Виділення множини Парето і шарів недомінованості; ваги не потрібні.', uses_weights=False, abbr='Парето'),
    'germeier': MethodSpec(
        'Максимінна згортка Гермейєра', germeier,
        'Оцінка за найслабшим зваженим критерієм; вибирає збалансовані альтернативи.', abbr='Гермейєр'),
    'main_criterion': MethodSpec(
        'Метод головного критерію (ε-обмежень)', main_criterion,
        'Оптимізація одного критерію за умови, що інші не гірші за задані пороги.',
        [Param('main', 'Головний критерій', 'criterion', 0),
         Param('thresholds', 'Пороги ε для інших критеріїв', 'per_criterion', None,
               help='Для max-критерію: значення ≥ ε, для min-критерію: значення ≤ ε. Порожньо – без обмеження.')],
        uses_weights=False, abbr='Головний критерій'),
    'lexicographic': MethodSpec(
        'Лексикографічний метод / послідовних поступок', lexicographic,
        'Критерії оптимізуються по черзі за важливістю з допустимою поступкою δ.',
        [Param('order', 'Порядок важливості критеріїв', 'order', None),
         Param('concession', 'Поступка δ (частка розмаху критерію)', 'float', 0.05, 0.0, 1.0, 0.01,
               help='0 – строгий лексикографічний метод')],
        uses_weights=False, abbr='Лексикографічний'),
    'vikor': MethodSpec(
        'VIKOR (компромісне ранжування)', vikor,
        'Компроміс між сумарним і максимальним зваженим відхиленням від ідеалу.',
        [Param('v', 'Вага стратегії «більшості» v', 'float', 0.5, 0.0, 1.0, 0.05,
               help='v > 0,5 – перевага сумарної корисності, v < 0,5 – мінімізація найбільшого жалю')], abbr='VIKOR'),
    'weighted_product': MethodSpec(
        'Мультиплікативна згортка', weighted_product,
        'F = Π rⱼ^wⱼ; сильніше за адитивну карає дуже погані значення.', abbr='Мультиплікативна'),
    'goal_programming': MethodSpec(
        'Цільове програмування', goal_programming,
        'Мінімізація зважених недосягнень цільових значень критеріїв.',
        [Param('targets', 'Цільові значення', 'per_criterion', None,
               help='Для max-критерію – бажаний мінімум, для min-критерію – бажаний максимум'),
         Param('p', 'Параметр метрики p', 'choice', 1.0, options=(1.0, 2.0, float('inf')))], abbr='Цільове'),
}


def run(method, X, senses, w, **params):
    """Запускає метод за ключем реєстру і вимірює час виконання."""
    if method not in METHODS:
        raise ValueError(f'Невідомий метод: {method}')
    t0 = time.perf_counter()
    res = METHODS[method].func(X, senses, w, **params)
    res.elapsed_ms = (time.perf_counter() - t0) * 1000
    return res


def compare(X, senses, w, methods=None, params=None):
    """Ранги альтернатив за кількома методами + консенсус за правилом Борда."""
    methods = methods or [k for k in METHODS if k not in ('main_criterion', 'goal_programming')]
    params = params or {}
    ranks, times = {}, {}
    for k in methods:
        r = run(k, X, senses, w, **params.get(k, {}))
        ranks[k], times[k] = r.rank, r.elapsed_ms
    R = np.column_stack([ranks[k] for k in methods])
    m = R.shape[0]
    borda = (m - R).sum(axis=1)
    return ranks, times, borda


def spearman_matrix(rank_cols):
    """Матриця коефіцієнтів рангової кореляції Спірмена між методами."""
    R = np.column_stack(rank_cols).astype(float)
    sd = R.std(axis=0)
    R = (R - R.mean(axis=0)) / np.where(sd > 0, sd, 1)
    C = (R.T @ R) / len(R)
    const = sd == 0                  # метод не розрізняє альтернатив – кореляція не визначена
    C[const, :] = np.nan
    C[:, const] = np.nan
    np.fill_diagonal(C, 1.0)
    return C
