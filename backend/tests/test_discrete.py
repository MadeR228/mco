import numpy as np
import pytest

from mco import discrete as d

# Класичний приклад TOPSIS (вибір телефону): ціна (min), пам'ять, камера, вигляд (max), рівні ваги
PHONES = np.array([[250, 16, 12, 5], [200, 16, 8, 3], [300, 32, 16, 4], [275, 32, 8, 4], [225, 16, 16, 2]], float)
PHONE_SENSES = np.array([-1, 1, 1, 1])


def test_topsis_reference_example():
    r = d.topsis(PHONES, PHONE_SENSES, [0.25] * 4)
    assert np.allclose(r.score, [0.5342, 0.3083, 0.6916, 0.5348, 0.4011], atol=1e-3)
    assert r.best == 2


def test_pareto_mask_and_fronts():
    X = np.array([[1, 5], [2, 4], [3, 3], [2, 2], [1, 1], [3, 3]], float)   # обидва критерії max
    mask = d.pareto_mask(X, [1, 1])
    assert mask.tolist() == [True, True, True, False, False, True]          # дублікати не домінують одне одного
    assert d.pareto_fronts(X, [1, 1]).tolist() == [0, 0, 0, 1, 2, 0]


def test_pareto_respects_min_direction():
    X = np.array([[10, 1], [8, 1], [12, 3]], float)       # ціна min, якість max
    assert d.pareto_mask(X, [-1, 1]).tolist() == [False, True, True]


def test_weighted_sum_by_hand():
    X = np.array([[100, 1.0], [200, 3.0], [150, 2.0]])
    r = d.weighted_sum(X, [-1, 1], [0.5, 0.5])
    # нормалізація: ціна (1, 0, 0.5), якість (0, 1, 0.5)
    assert np.allclose(r.score, [0.5, 0.5, 0.5])
    r = d.weighted_sum(X, [-1, 1], [0.8, 0.2])
    assert r.best == 0 and np.isclose(r.score[0], 0.8)


def test_ideal_point_chebyshev_is_max_deviation():
    X = np.array([[0, 10], [10, 0], [6, 6]], float)
    r = d.ideal_point(X, [1, 1], [0.5, 0.5], p=np.inf)
    assert np.allclose(r.score, [0.5, 0.5, 0.2]) and r.best == 2


def test_germeier_prefers_balanced():
    X = np.array([[10, 0], [0, 10], [5, 5]], float)
    assert d.germeier(X, [1, 1], [0.5, 0.5]).best == 2


def test_main_criterion_thresholds():
    X = np.array([[100, 5], [80, 9], [120, 7]], float)    # якість max, ціна min (в другому стовпці)
    r = d.main_criterion(X, [1, -1], [1, 1], main=0, thresholds={1: 8})
    assert r.best == 2 and r.info['feasible'] == 2
    r = d.main_criterion(X, [1, -1], [1, 1], main=0, thresholds={1: 1})
    assert r.best is None


def test_lexicographic_with_concession():
    X = np.array([[100, 1], [99, 9], [80, 10]], float)
    assert d.lexicographic(X, [1, 1], [1, 1], order=[0, 1], concession=0).best == 0
    assert d.lexicographic(X, [1, 1], [1, 1], order=[0, 1], concession=0.1).best == 1
    assert d.lexicographic(X, [1, 1], [1, 1], order=[1, 0], concession=0).best == 2


def test_vikor_conditions():
    r = d.vikor(PHONES, PHONE_SENSES, [0.25] * 4, v=0.5)
    assert {'C1', 'C2', 'compromise'} <= set(r.info)
    with pytest.raises(ValueError):
        d.vikor(PHONES, PHONE_SENSES, [0.25] * 4, v=2)


def test_goal_programming_zero_when_goals_met():
    X = np.array([[100, 5], [80, 9]], float)
    r = d.goal_programming(X, [-1, 1], [0.5, 0.5], targets={0: 90, 1: 8})
    assert r.score[1] == 0 and r.best == 1 and r.info['achieved'][1] == 2


def test_dominated_alternative_never_wins():
    rng = np.random.default_rng(3)
    X = rng.random((40, 4))
    X = np.vstack([X, X[0] - 0.01])          # явно домінована копія першої альтернативи
    s = np.ones(4)
    for key in ('weighted_sum', 'ideal_point', 'topsis', 'weighted_product', 'vikor'):
        for _ in range(20):
            w = rng.random(4)
            assert d.run(key, X, s, w).best != 40


def test_invalid_input_messages():
    with pytest.raises(ValueError, match='Сума ваг'):
        d.weighted_sum(PHONES, PHONE_SENSES, [0, 0, 0, 0])
    with pytest.raises(ValueError, match='невід’ємними'):
        d.weighted_sum(PHONES, PHONE_SENSES, [1, -1, 0, 0])
    with pytest.raises(ValueError, match='нечислові'):
        d.weighted_sum(np.array([[1, np.nan], [2, 3]]), [1, 1], [1, 1])
    with pytest.raises(ValueError):
        d.run('unknown', PHONES, PHONE_SENSES, [1] * 4)


def test_constant_criterion_does_not_break_normalization():
    X = np.array([[1, 5], [2, 5], [3, 5]], float)
    for key in d.METHODS:
        if key in ('main_criterion', 'goal_programming'):
            continue
        r = d.run(key, X, [1, 1], [0.5, 0.5])
        assert np.isfinite(r.score).all()


def test_rank_ties_and_nan():
    assert d.rank_scores([3, 1, 3, np.nan]).tolist() == [1, 3, 1, 4]
    assert d.rank_scores([0.2, 0.1], higher_is_better=False).tolist() == [2, 1]


def test_compare_and_spearman():
    ranks, times, borda = d.compare(PHONES, PHONE_SENSES, [0.25] * 4)
    assert len(ranks) == 8 and len(borda) == 5
    C = d.spearman_matrix(list(ranks.values()))
    assert np.allclose(np.diag(C), 1)


def test_large_problem_is_fast():
    rng = np.random.default_rng(0)
    X = rng.random((20000, 10))
    s = np.where(rng.random(10) > 0.5, 1, -1)
    for key in ('weighted_sum', 'topsis', 'ideal_point', 'vikor'):
        r = d.run(key, X, s, np.ones(10))
        assert r.elapsed_ms < 500
