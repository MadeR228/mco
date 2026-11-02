"""Неперервні задачі: аналіз (лінійність, таблиця виграшів), розв’язок методом, фронт Парето."""
from fastapi import APIRouter

from .. import continuous_service as svc
from ..jobs import jobs
from ..schemas import ContinuousProblem, ContinuousSolveRequest, FrontRequest

router = APIRouter(prefix='/api', tags=['неперервні задачі'])


@router.post('/continuous/analyze')
def analyze(problem: ContinuousProblem):
    return svc.analyze(svc.build(problem))


@router.post('/continuous/solve')
def solve(req: ContinuousSolveRequest):
    return svc.solve(svc.build(req.problem), req.method, req.params)


@router.post('/continuous/front')
def front(req: FrontRequest):
    """Синхронна побудова фронту – для невеликих задач; для NSGA-II зручніше /api/jobs/front."""
    return svc.front(svc.build(req.problem), req)


@router.post('/jobs/front', status_code=202)
def front_job(req: FrontRequest):
    problem = svc.build(req.problem)        # помилки у формулах – одразу, до постановки в чергу

    def run(report):
        total = req.nsga.generations
        return svc.front(problem, req, progress=lambda g, n: report(g / max(n, 1), f'покоління {g} з {total}'))

    return jobs.submit('front', run)
