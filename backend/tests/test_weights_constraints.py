import numpy as np
import pandas as pd
import pytest

from mco import constraints as c
from mco import sensitivity as s
from mco import weights as w


def test_ahp_consistent_matrix_recovers_weights():
    true = np.array([0.5, 0.3, 0.2])
    A = true[:, None] / true[None, :]
    weights, lam, ci, cr = w.ahp(A)
    assert np.allclose(weights, true) and np.isclose(lam, 3) and abs(cr) < 1e-9


def test_ahp_inconsistency_detected():
    A = w.ahp_matrix_from_upper({(0, 1): 9, (0, 2): 1 / 9, (1, 2): 9}, 3)
    assert w.ahp(A)[3] > 0.1


def test_ahp_rejects_non_reciprocal():
    with pytest.raises(ValueError):
        w.ahp(np.array([[1, 3], [3, 1]]))


def test_roc_and_entropy():
    roc = w.rank_order_centroid([2, 0, 1])
    assert np.isclose(roc.sum(), 1) and roc[2] > roc[0] > roc[1]
    X = np.array([[1, 5], [2, 5.1], [3, 4.9]])
    e = w.entropy(X, [1, 1])
    assert np.isclose(e.sum(), 1)
    cr = w.critic(X, [1, 1])
    assert np.isclose(cr.sum(), 1)


DF = pd.DataFrame({'Модель': ['A', 'B', 'C'], 'Ціна': [100, 200, 300], 'Тип': ['офісний', 'ігровий', 'офісний']})


def test_numeric_and_text_constraints():
    ok, reasons = c.apply(DF, [c.Constraint('Ціна', '≤', '250'), c.Constraint('Тип', 'у списку', 'офісний')])
    assert ok.tolist() == [True, False, False]
    assert reasons[1] == ['Тип у списку офісний'] and reasons[2] == ['Ціна ≤ 250']
    ok, _ = c.apply(DF, [c.Constraint('Модель', 'містить', 'b')])
    assert ok.tolist() == [False, True, False]
    ok, _ = c.apply(DF, [c.Constraint('Ціна', '≥', '150,5')])           # десяткова кома
    assert ok.tolist() == [False, True, True]


def test_constraint_errors():
    with pytest.raises(ValueError, match='відсутній'):
        c.apply(DF, [c.Constraint('Вага', '≤', 1)])
    with pytest.raises(ValueError, match='числом'):
        c.apply(DF, [c.Constraint('Ціна', '≤', 'дешево')])


def test_weight_sweep_and_acceptability():
    X = np.array([[0, 10], [10, 0], [6, 6]], float)
    ts, S, winners, hib = s.weight_sweep('weighted_sum', X, [1, 1], [0.5, 0.5], 0, steps=11)
    assert winners[0] == 0 and winners[-1] == 1 and hib
    P = s.rank_acceptability('topsis', X, [1, 1], [0.5, 0.5], samples=300, seed=1)
    assert np.allclose(P.sum(axis=1), 1) and np.allclose(P.sum(axis=0), 1)
