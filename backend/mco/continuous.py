"""Багатокритеріальна оптимізація з неперервними змінними.

Задача задається формулами:  fᵢ(x) → max/min,  gⱼ(x) {≤, ≥, =} bⱼ,  lo ≤ x ≤ hi.
Формули розбираються SymPy і компілюються в векторизовані функції NumPy.
Якщо всі формули лінійні, скалярні підзадачі розв’язуються точно симплекс-методом
(scipy.optimize.linprog, HiGHS), інакше – SLSQP з кількох стартових точок.

Усі скаляризації зводяться до однієї форми над вектором орієнтованих цілей
φ(x) (φᵢ = −fᵢ для max, fᵢ для min) і допоміжними змінними u:
    a·φ(x) + b·u → min,   A_φ·φ(x) + A_u·u ≤ rhs,
що дозволяє однаково розв’язувати їх і для лінійних, і для нелінійних задач.
"""
import itertools
import re
import time
from dataclasses import dataclass, field

import numpy as np
import sympy as sp
from scipy.optimize import linprog, minimize

from .discrete import pareto_mask
from .nsga2 import nsga2

ALLOWED = {name: getattr(sp, name) for name in
           ('sin', 'cos', 'tan', 'exp', 'log', 'sqrt', 'Abs', 'pi', 'E', 'Min', 'Max', 'atan', 'sinh', 'cosh')}
ALLOWED['abs'] = sp.Abs
ALLOWED['ln'] = sp.log

TOL = 1e-6


@dataclass
class Variable:
    name: str
    lo: float = 0.0
    hi: float = 10.0


@dataclass
class Objective:
    name: str
    expr: str
    sense: str = 'max'
    weight: float = 1.0


@dataclass
class Constraint:
    expr: str
    op: str = '≤'
    rhs: float = 0.0


@dataclass
class Solution:
    method: str
    x: np.ndarray
    f: np.ndarray
    status: str = 'optimal'
    message: str = ''
    info: dict = field(default_factory=dict)
    elapsed_ms: float = 0.0


@dataclass
class Front:
    method: str
    X: np.ndarray
    F: np.ndarray
    elapsed_ms: float = 0.0
    info: dict = field(default_factory=dict)


FORMULA_CHARS = re.compile(r'^[0-9A-Za-z_\s+\-*/^().,]*$')
MAX_FORMULA = 500


def _check_formula(text, symbols, what):
    """Допускає лише числа, оператори, дужки, змінні задачі й дозволені функції.

    Формули приходять від користувача по мережі, а SymPy розбирає їх через eval, тому
    будь-які інші символи та імена (атрибути, «__», виклики модулів) відхиляються до розбору.
    """
    if len(text) > MAX_FORMULA:
        raise ValueError(f'{what}: формула довша за {MAX_FORMULA} символів')
    if not FORMULA_CHARS.match(text) or '__' in text:
        raise ValueError(f'{what}: недопустимі символи у формулі «{text}»')
    for name in re.findall(r'[A-Za-z_][A-Za-z0-9_]*', text):
        if name not in symbols and name not in ALLOWED:
            raise ValueError(f'{what}: невідомі змінні {name}')


def _parse(text, symbols, what):
    if not str(text).strip():
        raise ValueError(f'{what}: порожня формула')
    _check_formula(str(text), symbols, what)
    try:
        expr = sp.sympify(str(text).replace('^', '**'), locals={**ALLOWED, **symbols})
    except (sp.SympifyError, SyntaxError, TypeError) as e:
        raise ValueError(f'{what}: не вдалося розібрати формулу «{text}»') from e
    if not isinstance(expr, sp.Expr):
        raise ValueError(f'{what}: формула «{text}» не є виразом')
    unknown = expr.free_symbols - set(symbols.values())
    if unknown:
        raise ValueError(f'{what}: невідомі змінні {", ".join(sorted(map(str, unknown)))}')
    return expr


class Problem:
    def __init__(self, variables, objectives, constraints=()):
        if not variables:
            raise ValueError('Задайте хоча б одну змінну')
        if len(objectives) < 2:
            raise ValueError('Багатокритеріальна задача потребує щонайменше двох цілей')
        names = [v.name.strip() for v in variables]
        if len(set(names)) != len(names) or not all(n.isidentifier() for n in names):
            raise ValueError('Імена змінних мають бути унікальними ідентифікаторами (x1, y, price …)')
        self.variables, self.objectives, self.constraints = list(variables), list(objectives), list(constraints)
        self.lo = np.array([float(v.lo) for v in variables])
        self.hi = np.array([float(v.hi) for v in variables])
        if (self.lo > self.hi).any():
            raise ValueError('Нижня межа змінної більша за верхню')
        self.n, self.k = len(variables), len(objectives)
        syms = {n: sp.Symbol(n, real=True) for n in names}
        self.symbols = [syms[n] for n in names]
        self.senses = np.array([1 if o.sense == 'max' else -1 for o in objectives])
        f_exprs = [_parse(o.expr, syms, f'Ціль «{o.name}»') for o in objectives]
        ineq, eq = [], []
        for i, c in enumerate(constraints, start=1):
            e = _parse(c.expr, syms, f'Обмеження {i}') - float(c.rhs)
            if c.op in ('≤', '<='):
                ineq.append(e)
            elif c.op in ('≥', '>='):
                ineq.append(-e)
            elif c.op == '=':
                eq.append(e)
            else:
                raise ValueError(f'Обмеження {i}: невідомий оператор «{c.op}»')
        self.f_exprs, self.g_exprs, self.h_exprs = f_exprs, ineq, eq
        self._f = sp.lambdify(self.symbols, f_exprs, 'numpy')
        self._g = sp.lambdify(self.symbols, ineq, 'numpy') if ineq else None
        self._h = sp.lambdify(self.symbols, eq, 'numpy') if eq else None
        self.linear = all(self._is_linear(e) for e in f_exprs + ineq + eq)
        if self.linear:
            self.C, self.c0 = self._coeffs(f_exprs)
            self.Ag, self.ag0 = self._coeffs(ineq)
            self.Ah, self.ah0 = self._coeffs(eq)
        self._payoff = None
        self.starts = 8           # кількість стартових точок SLSQP для нелінійних задач

    # ------------------------------------------------------------------ обчислення
    def _is_linear(self, e):
        try:
            return sp.Poly(e, *self.symbols).total_degree() <= 1
        except sp.PolynomialError:
            return False

    def _coeffs(self, exprs):
        if not exprs:
            return np.zeros((0, self.n)), np.zeros(0)
        A, b = sp.linear_eq_to_matrix(exprs, self.symbols)
        return np.array(A.tolist(), dtype=float), -np.array(b.tolist(), dtype=float).ravel()

    @staticmethod
    def _stack(fun, X, count):
        X = np.atleast_2d(X)
        vals = fun(*X.T)
        return np.column_stack([np.broadcast_to(np.asarray(v, dtype=float), (len(X),)) for v in vals]) \
            if count else np.zeros((len(X), 0))

    def objectives_at(self, X):
        """Значення цілей у вихідних одиницях для рядків X (N×n)."""
        return self._stack(self._f, X, self.k)

    def phi(self, X):
        """Орієнтовані на мінімізацію цілі."""
        return -self.senses * self.objectives_at(X)

    def violation(self, X):
        X = np.atleast_2d(X)
        cv = np.zeros(len(X))
        if self._g:
            cv += np.maximum(self._stack(self._g, X, len(self.g_exprs)), 0).sum(axis=1)
        if self._h:
            cv += np.maximum(np.abs(self._stack(self._h, X, len(self.h_exprs))) - 1e-4, 0).sum(axis=1)
        cv += np.maximum(self.lo - X, 0).sum(axis=1) + np.maximum(X - self.hi, 0).sum(axis=1)
        return cv

    # ------------------------------------------------------------------ скалярний розв'язувач
    def _solve_form(self, a, b=None, A_phi=None, A_u=None, rhs=None, u_bounds=None, starts=None, seed=0):
        """a·φ(x) + b·u → min при A_φ·φ(x) + A_u·u ≤ rhs. Повертає (x, u) або кидає ValueError."""
        a = np.asarray(a, dtype=float)
        nu = 0 if b is None else len(b)
        b = np.zeros(0) if b is None else np.asarray(b, dtype=float)
        A_phi = np.zeros((0, self.k)) if A_phi is None else np.atleast_2d(np.asarray(A_phi, dtype=float))
        A_u = np.zeros((len(A_phi), nu)) if A_u is None else np.atleast_2d(np.asarray(A_u, dtype=float))
        rhs = np.zeros(0) if rhs is None else np.asarray(rhs, dtype=float)
        u_bounds = u_bounds or [(None, None)] * nu
        if self.linear:
            Cphi = -self.senses[:, None] * self.C          # φ(x) = Cphi·x + cphi
            cphi = -self.senses * self.c0
            c = np.concatenate([a @ Cphi, b])
            A_ub = [np.hstack([self.Ag, np.zeros((len(self.Ag), nu))]), np.hstack([A_phi @ Cphi, A_u])]
            b_ub = [-self.ag0, rhs - A_phi @ cphi]
            A_eq = np.hstack([self.Ah, np.zeros((len(self.Ah), nu))]) if len(self.Ah) else None
            b_eq = -self.ah0 if len(self.Ah) else None
            bounds = [(None if np.isinf(l) else l, None if np.isinf(h) else h) for l, h in zip(self.lo, self.hi)]
            res = linprog(c, A_ub=np.vstack(A_ub), b_ub=np.concatenate(b_ub), A_eq=A_eq, b_eq=b_eq,
                          bounds=bounds + list(u_bounds), method='highs')
            if res.status == 2:
                raise ValueError('Задача не має допустимих розв’язків (обмеження несумісні)')
            if res.status == 3:
                raise ValueError('Цільова функція необмежена: додайте обмеження або межі змінних')
            if res.status != 0:
                raise ValueError(f'Симплекс-метод не знайшов розв’язку: {res.message}')
            return res.x[:self.n], res.x[self.n:]

        def fun(z):
            return float(a @ self.phi(z[:self.n])[0] + b @ z[self.n:])

        cons = [{'type': 'ineq', 'fun': lambda z: -self._stack(self._g, z[:self.n], 1)[0]}] if self._g else []
        if self._h:
            cons.append({'type': 'eq', 'fun': lambda z: self._stack(self._h, z[:self.n], 1)[0]})
        if len(A_phi):
            cons.append({'type': 'ineq',
                         'fun': lambda z: rhs - A_phi @ self.phi(z[:self.n])[0] - A_u @ z[self.n:]})
        return self._multistart(fun, cons, nu, u_bounds, starts or self.starts, seed)

    def _multistart(self, fun, cons, nu, u_bounds, starts, seed):
        rng = np.random.default_rng(seed)
        lo = np.where(np.isfinite(self.lo), self.lo, np.minimum(self.hi, 0) - 10)
        hi = np.where(np.isfinite(self.hi), self.hi, lo + 20)
        bounds = [(None if np.isinf(l) else l, None if np.isinf(h) else h) for l, h in zip(self.lo, self.hi)]
        best = None
        for s in range(max(1, int(starts))):
            x0 = (lo + hi) / 2 if s == 0 else lo + rng.random(self.n) * (hi - lo)
            u0 = np.zeros(nu)
            if nu:      # стартові u – щоб допоміжні обмеження виконувались
                u0 = np.full(nu, np.abs(self.phi(x0)).max() + 1.0)
            res = minimize(fun, np.concatenate([x0, u0]), method='SLSQP', constraints=cons,
                           bounds=bounds + list(u_bounds), options={'maxiter': 300, 'ftol': 1e-10})
            viol = max([0.0] + [float(np.max(-c['fun'](res.x))) if c['type'] == 'ineq'
                                else float(np.max(np.abs(c['fun'](res.x)))) for c in cons])
            cand = (viol > 1e-5, res.fun, res.x)
            if best is None or cand[:2] < best[:2]:
                best = cand
        if best[0]:
            raise ValueError('Не знайдено допустимого розв’язку (спробуйте більше стартових точок або '
                             'перевірте обмеження)')
        return best[2][:self.n], best[2][self.n:]

    # ------------------------------------------------------------------ таблиця виграшів
    def payoff(self):
        """Оптимізація кожної цілі окремо: таблиця виграшів, ідеальна точка та оцінка надира (у φ)."""
        if self._payoff is None:
            rows, xs = [], []
            for i in range(self.k):
                a = np.zeros(self.k)
                a[i] = 1
                x, _ = self._solve_form(a)
                # уточнення: серед оптимумів i-ї цілі – найкращий за сумою інших (усуває слабку оптимальність)
                phi_i = self.phi(x)[0, i]
                a2 = np.ones(self.k) * 1e-3
                a2[i] = 1
                try:
                    row = np.zeros(self.k)
                    row[i] = 1
                    x, _ = self._solve_form(a2, A_phi=row[None, :], rhs=[phi_i + 1e-7 * (1 + abs(phi_i))])
                except ValueError:
                    pass
                xs.append(x)
                rows.append(self.phi(x)[0])
            P = np.array(rows)
            ideal, nadir = np.diag(P).copy(), P.max(axis=0)
            rng = np.where(nadir - ideal > 1e-12, nadir - ideal, 1.0)
            self._payoff = {'X': np.array(xs), 'phi': P, 'ideal': ideal, 'nadir': nadir, 'range': rng}
        return self._payoff

    def _weights(self, w):
        w = np.asarray([o.weight for o in self.objectives] if w is None else w, dtype=float)
        if len(w) != self.k or (w < 0).any() or w.sum() <= 0:
            raise ValueError('Ваги цілей мають бути невід’ємними, хоча б одна – додатна')
        return w / w.sum()

    def _solution(self, method, x, t0, **info):
        x = np.asarray(x, dtype=float)
        return Solution(method, x, self.objectives_at(x)[0], info=info,
                        elapsed_ms=(time.perf_counter() - t0) * 1000)

    def to_original(self, phi):
        return -self.senses * np.asarray(phi)

    # ------------------------------------------------------------------ методи
    def weighted_sum(self, w=None):
        """min Σ wᵢ(φᵢ − φᵢ*)/(φᵢⁿ − φᵢ*) – зважена сума нормованих цілей."""
        t0 = time.perf_counter()
        P, w = self.payoff(), self._weights(w)
        x, _ = self._solve_form(w / P['range'])
        return self._solution('weighted_sum', x, t0, weights=w)

    def eps_constraint(self, main=0, eps=None):
        """Метод головного критерію: оптимізується ціль main, решта – обмеження fᵢ ≥ εᵢ (max) / fᵢ ≤ εᵢ (min)."""
        t0 = time.perf_counter()
        a = np.zeros(self.k)
        a[int(main)] = 1
        rows, rhs = [], []
        for i, e in (eps or {}).items():
            i = int(i)
            if i == int(main) or e is None or np.isnan(e):
                continue
            r = np.zeros(self.k)
            r[i] = 1
            rows.append(r)
            rhs.append(-self.senses[i] * float(e))     # φᵢ ≤ −εᵢ для max, φᵢ ≤ εᵢ для min
        x, _ = self._solve_form(a, A_phi=np.array(rows) if rows else None, rhs=rhs)
        return self._solution('eps_constraint', x, t0, main=int(main))

    def ideal_point(self, w=None, p=2.0, rho=1e-4):
        """Метод ідеальної точки (Тихонова): min ‖w·(φ − φ*)/Δ‖ₚ; p = ∞ – зважена метрика Чебишова."""
        t0 = time.perf_counter()
        P, w = self.payoff(), self._weights(w)
        p = float(p)
        if p == 1:
            return self.weighted_sum(w)
        scale = w / P['range']
        if np.isinf(p):
            # min t + ρΣ wᵢφ̃ᵢ  при  wᵢ(φᵢ − φᵢ*)/Δᵢ ≤ t  (доданок ρ відсікає слабко оптимальні точки)
            x, u = self._solve_form(rho * scale, b=[1.0], A_phi=np.diag(scale), A_u=-np.ones((self.k, 1)),
                                    rhs=scale * P['ideal'], u_bounds=[(None, None)])
            return self._solution('ideal_point', x, t0, p=p, distance=float(u[0]))
        if p < 1:
            raise ValueError('Параметр p має бути ≥ 1')

        def fun(z):
            d = np.abs(scale * (self.phi(z[:self.n])[0] - P['ideal']))
            return float((d ** p).sum() ** (1 / p))

        cons = [{'type': 'ineq', 'fun': lambda z: -self._stack(self._g, z[:self.n], 1)[0]}] if self._g else []
        if self._h:
            cons.append({'type': 'eq', 'fun': lambda z: self._stack(self._h, z[:self.n], 1)[0]})
        x, _ = self._multistart(fun, cons, 0, [], self.starts, 0)
        return self._solution('ideal_point', x, t0, p=p, distance=fun(x))

    def goal_programming(self, targets, w=None):
        """Цільове програмування: min Σ wᵢdᵢ, dᵢ ≥ (φᵢ − φᵢ^ціль)/Δᵢ, dᵢ ≥ 0."""
        t0 = time.perf_counter()
        P, w = self.payoff(), self._weights(w)
        goals = [(int(i), float(g)) for i, g in (targets or {}).items() if g is not None and not np.isnan(g)]
        if not goals:
            raise ValueError('Задайте цільове значення хоча б для однієї цілі')
        m = len(goals)
        A_phi, A_u, rhs = np.zeros((m, self.k)), -np.eye(m), np.zeros(m)
        for r, (i, g) in enumerate(goals):
            A_phi[r, i] = 1 / P['range'][i]
            rhs[r] = -self.senses[i] * g / P['range'][i]
        b = np.array([w[i] for i, _ in goals])
        x, d = self._solve_form(np.zeros(self.k), b=b, A_phi=A_phi, A_u=A_u, rhs=rhs, u_bounds=[(0, None)] * m)
        return self._solution('goal_programming', x, t0, deviations=d)

    def lexicographic(self, order=None, concession=0.0):
        """Метод послідовних поступок: оптимізація за важливістю з поступкою δ·Δᵢ на кожному кроці."""
        t0 = time.perf_counter()
        P = self.payoff()
        order = list(range(self.k)) if order is None else [int(i) for i in order]
        rows, rhs, steps = [], [], []
        x = None
        for i in order:
            a = np.zeros(self.k)
            a[i] = 1
            x, _ = self._solve_form(a, A_phi=np.array(rows) if rows else None, rhs=rhs)
            best = self.phi(x)[0, i]
            steps.append(float(self.to_original(np.eye(self.k)[i] * best)[i]))
            r = np.zeros(self.k)
            r[i] = 1
            rows.append(r)
            rhs.append(best + float(concession) * P['range'][i] + 1e-9)
        return self._solution('lexicographic', x, t0, steps=steps)

    # ------------------------------------------------------------------ фронт Парето
    def _simplex_weights(self, points):
        if self.k == 2:
            t = np.linspace(0, 1, max(2, int(points)))
            return np.column_stack([t, 1 - t])
        H = 1
        while len(list(itertools.combinations(range(H + self.k - 1), self.k - 1))) < points:
            H += 1
        W = []
        for c in itertools.combinations(range(H + self.k - 1), self.k - 1):
            parts = np.diff([-1, *c, H + self.k - 1]) - 1
            W.append(parts / H)
        return np.array(W)

    def pareto_front(self, method='chebyshev', points=30, **params):
        """Апроксимація фронту Парето: перебір ваг, ε-обмежень, Чебишова або NSGA-II."""
        t0 = time.perf_counter()
        info = {}
        if method == 'nsga2':
            out = nsga2(lambda X: (self.phi(X), self.violation(X)), self.lo, self.hi, **params)
            X = out['front_X']
            info = {'history': [self.to_original(h) for h in out['history']],
                    'evaluations': out['evaluations'], 'feasible_share': out['feasible_share']}
        else:
            P = self.payoff()
            xs = []
            if method in ('weighted', 'chebyshev'):
                for w in self._simplex_weights(points):
                    w = np.maximum(w, 1e-6)
                    try:
                        s = self.weighted_sum(w) if method == 'weighted' else self.ideal_point(w, p=np.inf)
                        xs.append(s.x)
                    except ValueError:
                        continue
            elif method == 'eps':
                per = max(2, int(round(points ** (1 / (self.k - 1)))))
                grids = [np.linspace(P['ideal'][i], P['nadir'][i], per) for i in range(1, self.k)]
                for eps_phi in itertools.product(*grids):
                    eps = {i: float(self.to_original(np.eye(self.k)[i] * e)[i])
                           for i, e in zip(range(1, self.k), eps_phi)}
                    try:
                        xs.append(self.eps_constraint(0, eps).x)
                    except ValueError:
                        continue
            else:
                raise ValueError(f'Невідомий спосіб побудови фронту: {method}')
            X = np.array(xs).reshape(-1, self.n)
        F = self.objectives_at(X) if len(X) else np.zeros((0, self.k))
        if len(F):
            keep = pareto_mask(np.round(F, 9), self.senses)
            X, F = X[keep], F[keep]
            _, uniq = np.unique(np.round(F, 6), axis=0, return_index=True)
            X, F = X[np.sort(uniq)], F[np.sort(uniq)]
            order = np.argsort(F[:, 0])
            X, F = X[order], F[order]
        return Front(method, X, F, (time.perf_counter() - t0) * 1000, info)


METHODS = {
    'weighted_sum': 'Метод зваженої суми',
    'ideal_point': 'Метод ідеальної точки (Тихонова)',
    'eps_constraint': 'Метод головного критерію (ε-обмежень)',
    'lexicographic': 'Метод послідовних поступок (лексикографічний)',
    'goal_programming': 'Цільове програмування',
}

FRONT_METHODS = {
    'chebyshev': 'Зважена метрика Чебишова (перебір ваг)',
    'eps': 'Метод ε-обмежень (перебір порогів)',
    'weighted': 'Зважена сума (перебір ваг)',
    'nsga2': 'Генетичний алгоритм NSGA-II',
}


def from_dict(d):
    """Створює задачу з JSON-словника (формат файлів у examples/)."""
    return Problem([Variable(**v) for v in d['variables']],
                   [Objective(**o) for o in d['objectives']],
                   [Constraint(**c) for c in d.get('constraints', [])])
