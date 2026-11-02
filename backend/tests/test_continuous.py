import json
from pathlib import Path

import numpy as np
import pytest

from mco import continuous as c
from mco.nsga2 import hypervolume_2d, non_dominated_fronts

EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'


def load(name):
    return c.from_dict(json.loads((EXAMPLES / f'{name}.json').read_text(encoding='utf-8')))


def test_production_payoff_matches_lab11():
    p = load('production')
    assert p.linear
    pay = p.to_original(p.payoff()['phi'])
    assert np.isclose(pay[0, 0], 1464 / 11)          # максимум прибутку з ЛР 11 (варіант 3)
    assert np.isclose(pay[1, 1], 3.0)                 # мінімум відходів: x1 = 0, x2 = 6


def test_eps_constraint_linear():
    p = load('production')
    s = p.eps_constraint(main=0, eps={1: 6.0})        # max прибутку при відходах ≤ 6
    assert np.isclose(s.f[1], 6.0, atol=1e-7)
    assert np.isclose(s.f[0], 108.0, atol=1e-6)


def test_methods_return_feasible_pareto_points():
    for name in ('production', 'binh_korn', 'portfolio'):
        p = load(name)
        sols = [p.weighted_sum(), p.ideal_point(p=2), p.ideal_point(p=np.inf), p.lexicographic(concession=0.1)]
        for s in sols:
            assert p.violation(s.x)[0] < 1e-5


def test_binh_korn_front_close_to_analytic():
    p = load('binh_korn')
    front = p.pareto_front('nsga2', pop_size=80, generations=80, seed=2)
    f1, f2 = front.F[:, 0], front.F[:, 1]
    # аналітичний фронт: x = y = t ∈ [0; 3] (f1 ≤ 72), далі y = 3, x ∈ [3; 5]
    t = np.sqrt(np.minimum(f1, 72) / 8)
    x = np.sqrt(np.maximum(f1 / 4 - 9, 9))
    exact = np.where(f1 <= 72, 2 * (t - 5) ** 2, (x - 5) ** 2 + 4)
    assert len(f1) > 40 and np.median(np.abs(f2 - exact)) / 50 < 0.01


def test_chebyshev_front_monotone():
    p = load('binh_korn')
    F = p.pareto_front('chebyshev', points=10).F
    assert len(F) >= 8 and (np.diff(F[:, 0]) > 0).all() and (np.diff(F[:, 1]) < 0).all()


def test_three_objective_front():
    p = load('portfolio')
    F = p.pareto_front('nsga2', pop_size=60, generations=40, seed=0).F
    assert F.shape[1] == 3 and len(F) > 20


def test_goal_programming_reaches_attainable_goals():
    p = load('production')
    s = p.goal_programming({0: 100.0, 1: 8.0})
    assert s.f[0] >= 100 - 1e-6 and s.f[1] <= 8 + 1e-6


def test_parse_errors_and_infeasible():
    V = [c.Variable('x', 0, 1)]
    O = [c.Objective('a', 'x', 'max'), c.Objective('b', 'x + z', 'min')]
    with pytest.raises(ValueError, match='невідомі змінні'):
        c.Problem(V, O)
    with pytest.raises(ValueError, match='двох цілей'):
        c.Problem(V, O[:1])
    p = c.Problem(V, [c.Objective('a', 'x', 'max'), c.Objective('b', 'x', 'min')], [c.Constraint('x', '≥', 2)])
    with pytest.raises(ValueError, match='допустимих'):
        p.payoff()


def test_nsga_utils():
    F = np.array([[1, 4], [2, 2], [4, 1], [3, 3]], float)
    fronts = non_dominated_fronts(F)
    assert sorted(fronts[0].tolist()) == [0, 1, 2] and fronts[1].tolist() == [3]
    assert np.isclose(hypervolume_2d(F[:3], (5, 5)), 1 * 1 + 3 * 2 + 1 * 4)
