"""Дискретний вибір: розв’язок, порівняння методів, чутливість, Монте-Карло, ваги."""
import numpy as np
import pandas as pd
from fastapi import APIRouter

from mco import discrete as disc
from mco import weights as wts

from .. import discrete_service as svc
from ..convert import clean
from ..schemas import (CompareRequest, DiscreteProblem, MonteCarloRequest, SensitivityRequest, SolveRequest,
                       WeightsRequest)

router = APIRouter(prefix='/api', tags=['дискретний вибір'])


@router.post('/discrete/solve')
def solve(req: SolveRequest):
    pr = svc.prepare(req.problem)
    return svc.solve(pr, req.method, svc.method_params(req.method, req.params, pr))


@router.post('/discrete/compare')
def compare(req: CompareRequest):
    return svc.compare(svc.prepare(req.problem), req.methods)


@router.post('/discrete/sensitivity')
def sensitivity(req: SensitivityRequest):
    pr = svc.prepare(req.problem)
    return svc.sensitivity(pr, req.method, svc.method_params(req.method, req.params, pr), req.criterion, req.steps)


@router.post('/discrete/montecarlo')
def montecarlo(req: MonteCarloRequest):
    pr = svc.prepare(req.problem)
    return svc.montecarlo(pr, req.method, svc.method_params(req.method, req.params, pr),
                          req.samples, req.concentration, req.seed)


@router.post('/discrete/feasibility')
def feasibility(problem: DiscreteProblem):
    """Лише обмеження і пропуски: скільки альтернатив допустимі та чому решту виключено."""
    pr = svc.prepare(problem)
    return clean({'total': pr.total, 'feasible': len(pr.X), 'pareto': int(disc.pareto_mask(pr.X, pr.senses).sum()),
                  'excluded': pr.excluded})


@router.post('/weights/{method}')
def weights(method: str, req: WeightsRequest):
    names = [c.name for c in req.criteria]
    n = len(names)
    extra = {}
    if method == 'equal':
        w = wts.equal(n)
    elif method == 'manual':
        w = disc.normalize_weights([c.weight for c in req.criteria])
    elif method == 'roc':
        order = req.order or names
        unknown = [c for c in order if c not in names]
        if unknown:
            raise ValueError(f'Невідомі критерії в порядку: {", ".join(unknown)}')
        order = list(dict.fromkeys(order)) + [c for c in names if c not in order]
        w = wts.rank_order_centroid([names.index(c) for c in order])
    elif method == 'ahp':
        if req.matrix is None or len(req.matrix) != n or any(len(r) != n for r in req.matrix):
            raise ValueError(f'Для AHP потрібна матриця парних порівнянь {n}×{n}')
        w, lam, ci, cr = wts.ahp(np.array(req.matrix, dtype=float))
        ci, cr = max(ci, 0.0), max(cr, 0.0)      # узгоджена матриця дає ±1e-16 через округлення
        extra = {'lambda_max': lam, 'ci': ci, 'cr': cr, 'consistent': cr <= 0.1}
    elif method in ('entropy', 'critic'):
        if not req.records:
            raise ValueError('Для цього способу потрібні дані альтернатив (records)')
        df = pd.DataFrame.from_records(req.records)
        missing = [c for c in names if c not in df.columns]
        if missing:
            raise ValueError(f'У таблиці немає стовпців: {", ".join(missing)}')
        X = df[names].apply(pd.to_numeric, errors='coerce').dropna().to_numpy(dtype=float)
        if len(X) < 2:
            raise ValueError('Потрібно щонайменше дві альтернативи без пропусків')
        senses = [1 if c.sense == 'max' else -1 for c in req.criteria]
        w = (wts.entropy if method == 'entropy' else wts.critic)(X, senses)
    else:
        raise ValueError(f'Невідомий спосіб визначення ваг «{method}»')
    return clean({'method': method, 'weights': dict(zip(names, w)), **extra})
