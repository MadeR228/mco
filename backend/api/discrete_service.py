"""Підготовка дискретної задачі з запиту API та перетворення результатів методів."""
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from mco import constraints as cons
from mco import discrete as disc
from mco import sensitivity as sens
from mco.normalize import minmax

from .convert import clean, parse_inf
from .schemas import DiscreteProblem


@dataclass
class Prepared:
    criteria: list           # назви критеріїв
    senses: np.ndarray       # ±1
    weights: np.ndarray      # нормовані ваги
    X: np.ndarray            # матриця рішень допустимих альтернатив
    index: np.ndarray        # номери цих альтернатив у вхідній таблиці
    names: list              # їхні назви
    excluded: list           # [{index, name, reasons}]
    total: int


def prepare(p: DiscreteProblem) -> Prepared:
    df = pd.DataFrame.from_records(p.records)
    criteria = [c.name for c in p.criteria]
    if len(set(criteria)) != len(criteria):
        raise ValueError('Назви критеріїв повторюються')
    for c in criteria:
        if c not in df.columns:
            raise ValueError(f'У таблиці немає стовпця «{c}»')
        numeric = pd.to_numeric(df[c], errors='coerce')
        if (numeric.isna() & df[c].notna()).any():
            raise ValueError(f'Стовпець «{c}» містить нечислові значення')
        df[c] = numeric
    if p.name_column:
        if p.name_column not in df.columns:
            raise ValueError(f'У таблиці немає стовпця «{p.name_column}»')
        names_all = df[p.name_column].astype(str).tolist()
    else:
        text = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
        names_all = df[text[0]].astype(str).tolist() if text else [f'A{i + 1}' for i in range(len(df))]

    limits = [cons.Constraint(c.column, c.op, c.value) for c in p.constraints]
    ok, reasons = cons.apply(df, limits)
    gaps = df[criteria].isna().any(axis=1).to_numpy()
    if gaps[ok].any():
        missing_cols = [c for c in criteria if df.loc[ok, c].isna().any()]
        if p.missing == 'error':
            raise ValueError(f'У {int(gaps[ok].sum())} альтернатив немає значень критеріїв '
                             f'{", ".join(missing_cols)}: виключіть їх (missing="drop") або замініть медіаною '
                             f'(missing="median")')
        if p.missing == 'median':
            df[criteria] = df[criteria].fillna(df[criteria].median())
        else:
            for i in np.where(ok & gaps)[0]:
                reasons[i].append('немає значень: ' + ', '.join(c for c in criteria if pd.isna(df.at[i, c])))
            ok = ok & ~gaps
    if not ok.any():
        raise ValueError('Жодна альтернатива не задовольняє обмеження')
    X = df.loc[ok, criteria].to_numpy(dtype=float)
    if np.isnan(X).any():
        raise ValueError('Після заміни медіаною лишилися пропуски: у критерію немає жодного значення')
    idx = np.where(ok)[0]
    return Prepared(
        criteria=criteria,
        senses=np.array([1 if c.sense == 'max' else -1 for c in p.criteria]),
        weights=disc.normalize_weights([c.weight for c in p.criteria]),
        X=X, index=idx, names=[names_all[i] for i in idx],
        excluded=[{'index': int(i), 'name': names_all[i], 'reasons': reasons[i]} for i in np.where(~ok)[0]],
        total=len(df),
    )


def _find_criterion(value, criteria):
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < len(criteria):
        return value
    if value in criteria:
        return criteria.index(value)
    raise ValueError(f'Невідомий критерій «{value}»')


def method_params(method, params, pr: Prepared):
    """Перевіряє параметри методу за реєстром і перетворює назви критеріїв на індекси."""
    if method not in disc.METHODS:
        raise ValueError(f'Невідомий метод «{method}»')
    spec = {p.name: p for p in disc.METHODS[method].params}
    unknown = set(params) - set(spec)
    if unknown:
        raise ValueError(f'Метод «{method}» не має параметрів: {", ".join(sorted(unknown))}')
    out = {}
    for name, p in spec.items():
        v = params.get(name, p.default)
        if p.kind == 'choice':
            v = parse_inf(v)
            try:
                v = float(v) if isinstance(p.default, float) else v
            except (TypeError, ValueError):
                raise ValueError(f'{p.label}: некоректне значення «{v}»') from None
            if v not in p.options:
                raise ValueError(f'{p.label}: допустимі значення {", ".join(map(str, p.options))}')
        elif p.kind == 'float':
            v = float(v)
            if not p.min <= v <= p.max:
                raise ValueError(f'{p.label}: значення має бути в межах [{p.min}; {p.max}]')
        elif p.kind == 'criterion':
            v = _find_criterion(int(np.argmax(pr.weights)) if v is None else v, pr.criteria)
        elif p.kind == 'order':
            order = [_find_criterion(c, pr.criteria) for c in (v or [])]
            if len(set(order)) != len(order):
                raise ValueError(f'{p.label}: критерії повторюються')
            rest = [j for j in np.argsort(-pr.weights, kind='stable') if j not in order]
            v = order + [int(j) for j in rest]
        elif p.kind == 'per_criterion':
            if v is None and name == 'targets':      # цілі за замовчуванням – «добрий» квартиль
                v = {pr.criteria[j]: float(np.quantile(pr.X[:, j], 0.75 if s > 0 else 0.25))
                     for j, s in enumerate(pr.senses)}
            v = {_find_criterion(k, pr.criteria): (None if x is None else float(x)) for k, x in (v or {}).items()}
        out[name] = v
    return out


def public_params(params, pr: Prepared):
    """Параметри у відповіді: індекси критеріїв назад у назви, ∞ – рядком."""
    out = {}
    for k, v in params.items():
        if k == 'main':
            v = pr.criteria[v]
        elif k == 'order':
            v = [pr.criteria[j] for j in v]
        elif isinstance(v, dict):
            v = {pr.criteria[j]: x for j, x in v.items()}
        elif isinstance(v, float) and math.isinf(v):
            v = 'inf'
        out[k] = v
    return out


def solve(pr: Prepared, method, params):
    res = disc.run(method, pr.X, pr.senses, pr.weights, **params)
    pareto = disc.pareto_mask(pr.X, pr.senses)
    fronts = disc.pareto_fronts(pr.X, pr.senses)
    R = minmax(pr.X, pr.senses)
    alts = []
    for k in np.argsort(res.rank, kind='stable'):
        a = {'index': int(pr.index[k]), 'name': pr.names[k], 'rank': int(res.rank[k]), 'score': res.score[k],
             'pareto': bool(pareto[k]), 'front': int(fronts[k]),
             'values': dict(zip(pr.criteria, pr.X[k])), 'normalized': dict(zip(pr.criteria, R[k]))}
        if method == 'germeier':
            a['weakest'] = pr.criteria[int(res.info['weakest'][k])]
        if method == 'goal_programming':
            a['goals_achieved'] = int(res.info['achieved'][k])
        alts.append(a)
    info = {}
    if method == 'vikor' and 'compromise' in res.info:
        info = {'C1': res.info['C1'], 'C2': res.info['C2'], 'compromise': [pr.names[i] for i in res.info['compromise']]}
    elif method == 'main_criterion':
        info = {'feasible': res.info['feasible'], 'main': pr.criteria[res.info['main']]}
    elif method == 'lexicographic':
        info = {'remaining_after_step': res.info['remaining_after_step'],
                'order': [pr.criteria[j] for j in res.info['order']]}
    elif method == 'goal_programming':
        info = {'goals': res.info['goals']}
    elif method == 'pareto':
        info = {'pareto_count': res.info['pareto_count'], 'fronts': res.info['fronts']}
    elif method == 'ideal_point':
        info = {'p': 'inf' if math.isinf(res.info['p']) else res.info['p']}
    best = res.best
    return clean({
        'method': method, 'title': disc.METHODS[method].title, 'higher_is_better': res.higher_is_better,
        'elapsed_ms': res.elapsed_ms, 'params': public_params(params, pr),
        'weights': dict(zip(pr.criteria, pr.weights)),
        'best': None if best is None else {'index': int(pr.index[best]), 'name': pr.names[best], 'score': res.score[best]},
        'counts': {'total': pr.total, 'feasible': len(pr.X), 'pareto': int(pareto.sum())},
        'alternatives': alts, 'excluded': pr.excluded, 'info': info,
    })


def compare(pr: Prepared, methods=None):
    methods = methods or [k for k in disc.METHODS if k not in ('main_criterion', 'goal_programming')]
    for m in methods:
        if m not in disc.METHODS:
            raise ValueError(f'Невідомий метод «{m}»')
    ranks, times, borda = disc.compare(pr.X, pr.senses, pr.weights, methods)
    corr = disc.spearman_matrix([ranks[m] for m in methods])
    order = np.argsort(-borda, kind='stable')
    return clean({
        'methods': [{'key': m, 'title': disc.METHODS[m].title, 'abbr': disc.METHODS[m].abbr, 'elapsed_ms': times[m]}
                    for m in methods],
        'alternatives': [{'index': int(pr.index[k]), 'name': pr.names[k], 'borda': int(borda[k]),
                          'ranks': {m: int(ranks[m][k]) for m in methods}} for k in order],
        'spearman': corr,
        'consensus': {'index': int(pr.index[order[0]]), 'name': pr.names[order[0]], 'borda': int(borda[order[0]])},
    })


def sensitivity(pr: Prepared, method, params, criterion, steps):
    if not disc.METHODS[method].uses_weights:
        raise ValueError('Цей метод не використовує ваги – аналіз чутливості до ваг для нього не має сенсу')
    k = _find_criterion(criterion, pr.criteria)
    ts, S, winners, hib = sens.weight_sweep(method, pr.X, pr.senses, pr.weights, k, steps, **params)
    base = disc.run(method, pr.X, pr.senses, pr.weights, **params)
    show = list(dict.fromkeys([int(i) for i in winners if i is not None] +
                              [int(i) for i in np.argsort(base.rank, kind='stable')[:3]]))[:8]
    switches = [{'weight': ts[i], 'from': pr.names[winners[i - 1]], 'to': pr.names[winners[i]]}
                for i in range(1, len(ts)) if winners[i] != winners[i - 1]
                and winners[i] is not None and winners[i - 1] is not None]
    return clean({
        'criterion': pr.criteria[k], 'current_weight': pr.weights[k], 'higher_is_better': hib, 'weights': ts,
        'winners': [None if w is None else pr.names[w] for w in winners],
        'series': [{'index': int(pr.index[i]), 'name': pr.names[i], 'scores': S[:, i]} for i in show],
        'switches': switches,
    })


def montecarlo(pr: Prepared, method, params, samples, concentration, seed):
    if not disc.METHODS[method].uses_weights:
        raise ValueError('Цей метод не використовує ваги – стохастичний аналіз ваг для нього не має сенсу')
    P = sens.rank_acceptability(method, pr.X, pr.senses, pr.weights, samples, concentration, seed, **params)
    order = np.lexsort([-P[:, j] for j in reversed(range(min(3, P.shape[1])))])
    return clean({
        'samples': samples, 'concentration': concentration,
        'alternatives': [{'index': int(pr.index[i]), 'name': pr.names[i], 'first': P[i, 0],
                          'places': P[i, :min(5, P.shape[1])]} for i in order],
    })
