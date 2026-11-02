"""Неперервні задачі: побудова mco.continuous.Problem з запиту і подання результатів."""
import math

import numpy as np

from mco import continuous as cont
from mco import discrete as disc
from mco.nsga2 import hypervolume_2d

from .convert import clean, parse_inf
from .schemas import ContinuousProblem, FrontRequest


def build(p: ContinuousProblem) -> cont.Problem:
    problem = cont.from_dict(p.model_dump(exclude={'starts'}))
    problem.starts = p.starts
    return problem


def analyze(problem: cont.Problem):
    P = problem.payoff()
    names = [o.name for o in problem.objectives]
    return clean({
        'linear': problem.linear,
        'solver': 'HiGHS (симплекс-метод)' if problem.linear else f'SLSQP, {problem.starts} стартових точок',
        'objectives': [{'name': o.name, 'sense': o.sense} for o in problem.objectives],
        'payoff': [{'optimum_of': n, 'values': dict(zip(names, row)),
                    'x': dict(zip([v.name for v in problem.variables], x))}
                   for n, row, x in zip(names, problem.to_original(P['phi']), P['X'])],
        'ideal': dict(zip(names, problem.to_original(P['ideal']))),
        'nadir': dict(zip(names, problem.to_original(P['nadir']))),
    })


def _objective(name_or_index, problem):
    names = [o.name for o in problem.objectives]
    if isinstance(name_or_index, int) and not isinstance(name_or_index, bool) and 0 <= name_or_index < len(names):
        return name_or_index
    if name_or_index in names:
        return names.index(name_or_index)
    raise ValueError(f'Невідома ціль «{name_or_index}»')


def _per_objective(values, problem):
    return {_objective(k, problem): (None if v is None else float(v)) for k, v in (values or {}).items()}


ALLOWED_PARAMS = {
    'weighted_sum': set(), 'ideal_point': {'p'}, 'eps_constraint': {'main', 'eps'},
    'lexicographic': {'order', 'concession'}, 'goal_programming': {'targets'},
}


def solve(problem: cont.Problem, method, params):
    if method not in cont.METHODS:
        raise ValueError(f'Невідомий метод «{method}»')
    unknown = set(params) - ALLOWED_PARAMS[method]
    if unknown:
        raise ValueError(f'Метод «{method}» не має параметрів: {", ".join(sorted(unknown))}')
    if method == 'weighted_sum':
        s = problem.weighted_sum()
    elif method == 'ideal_point':
        p = float(parse_inf(params.get('p', 2.0)))
        if p < 1:
            raise ValueError('Параметр p має бути ≥ 1')
        s = problem.ideal_point(p=p)
    elif method == 'eps_constraint':
        s = problem.eps_constraint(_objective(params.get('main', 0), problem), _per_objective(params.get('eps'), problem))
    elif method == 'lexicographic':
        order = [_objective(o, problem) for o in params.get('order') or range(problem.k)]
        order += [i for i in range(problem.k) if i not in order]
        concession = float(params.get('concession', 0.0))
        if not 0 <= concession <= 1:
            raise ValueError('Поступка δ має бути в межах [0; 1]')
        s = problem.lexicographic(order, concession)
    else:
        targets = params.get('targets')
        if targets is None:      # цілі за замовчуванням – ідеальна точка
            targets = dict(enumerate(problem.to_original(problem.payoff()['ideal'])))
        s = problem.goal_programming(_per_objective(targets, problem))
    names = [o.name for o in problem.objectives]
    info = {k: v for k, v in s.info.items() if k in ('p', 'distance', 'steps', 'deviations', 'main')}
    if 'p' in info and math.isinf(info['p']):
        info['p'] = 'inf'
    if 'main' in info:
        info['main'] = names[info['main']]
    return clean({
        'method': method, 'title': cont.METHODS[method], 'elapsed_ms': s.elapsed_ms,
        'x': dict(zip([v.name for v in problem.variables], s.x)), 'f': dict(zip(names, s.f)),
        'violation': float(problem.violation(s.x)[0]), 'info': info,
    })


def front(problem: cont.Problem, req: FrontRequest, progress=None):
    params = req.nsga.model_dump() if req.method == 'nsga2' else {}
    if req.method == 'nsga2' and progress:
        params['progress'] = progress
    fr = problem.pareto_front(req.method, points=req.points, **params)
    names = [o.name for o in problem.objectives]
    var_names = [v.name for v in problem.variables]
    out = {
        'method': req.method, 'title': cont.FRONT_METHODS[req.method], 'elapsed_ms': fr.elapsed_ms,
        'points': [{'x': dict(zip(var_names, x)), 'f': dict(zip(names, f))} for x, f in zip(fr.X, fr.F)],
        'compromise': None, 'convergence': None,
    }
    if len(fr.F) >= 2:     # рекомендований компроміс – TOPSIS на точках фронту з вагами цілей
        r = disc.topsis(fr.F, problem.senses, problem._weights(None))
        out['compromise'] = {'point': int(r.best), 'method': 'topsis'}
    if req.method == 'nsga2':
        out['evaluations'] = fr.info['evaluations']
        out['feasible_share'] = fr.info['feasible_share']
        hist = [h for h in fr.info.get('history', []) if len(h)]
        if problem.k == 2 and hist:
            phi = [-problem.senses * h for h in fr.info['history']]
            ref = np.max([np.max(h, axis=0) for h in phi if len(h)], axis=0)
            ref = ref + 0.05 * np.abs(ref) + 1e-9
            out['convergence'] = [hypervolume_2d(h, ref) if len(h) else 0.0 for h in phi]
    return clean(out)
