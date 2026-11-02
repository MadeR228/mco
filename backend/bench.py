"""Вимірювання швидкодії методів на випадкових задачах різного розміру.

Запуск:  python bench.py
"""
import time
import tracemalloc

import numpy as np

from mco import discrete
from mco.nsga2 import nsga2


def best_time(fn, repeat=5):
    times = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000)
    return min(times)


rng = np.random.default_rng(0)
methods = ['weighted_sum', 'ideal_point', 'topsis', 'vikor', 'germeier', 'weighted_product', 'lexicographic']
print('=== Дискретні методи: час, мс (найкращий з 5 запусків) ===')
print(f'{"m × n":>14s} | ' + ' | '.join(f'{discrete.METHODS[k].abbr[:12]:>12s}' for k in methods))
for m, n in ((100, 5), (1000, 10), (10000, 10), (100000, 10)):
    X = rng.random((m, n))
    s = np.where(rng.random(n) > 0.5, 1, -1)
    w = rng.random(n)
    row = []
    for k in methods:
        row.append(f'{best_time(lambda: discrete.run(k, X, s, w), 3 if m >= 10000 else 5):12.2f}')
    print(f'{f"{m} × {n}":>14s} | ' + ' | '.join(row))

print('\n=== NSGA-II на задачі ZDT1 (30 змінних, 2 цілі) ===')


def zdt1(P):
    f1 = P[:, 0]
    g = 1 + 9 * P[:, 1:].mean(axis=1)
    return np.column_stack([f1, g * (1 - np.sqrt(f1 / g))]), np.zeros(len(P))


for pop, gens in ((50, 100), (100, 200), (200, 250)):
    t0 = time.perf_counter()
    out = nsga2(zdt1, np.zeros(30), np.ones(30), pop_size=pop, generations=gens, seed=0, record_history=False)
    dt = (time.perf_counter() - t0) * 1000
    F = out['front_F']
    err = np.abs(F[:, 1] - (1 - np.sqrt(F[:, 0]))).mean()       # відстань до точного фронту f2 = 1 − √f1
    print(f'   популяція {pop:3d}, поколінь {gens:3d}: {dt:7.0f} мс, {len(F):3d} точок, '
          f'середнє відхилення від точного фронту {err:.4f}')

print('\n=== Пам’ять: пікове використання для 100000 × 10 (зважена сума, TOPSIS) ===')
X = rng.random((100000, 10))
s, w = np.ones(10), np.ones(10)
for k in ('weighted_sum', 'topsis'):
    tracemalloc.start()
    discrete.run(k, X, s, w)
    peak = tracemalloc.get_traced_memory()[1] / 2 ** 20
    tracemalloc.stop()
    print(f'   {discrete.METHODS[k].abbr:14s} {peak:7.1f} МБ (матриця даних – {X.nbytes / 2 ** 20:.1f} МБ)')
print('\n=== Виділення множини Парето: час, мс ===')
for m, n in ((1000, 3), (10000, 3), (100000, 3), (1000, 10), (10000, 10)):
    X = rng.random((m, n))
    t = best_time(lambda: discrete.pareto_mask(X, np.ones(n)), 3)
    print(f'{f"{m} × {n}":>14s} | {t:9.1f} мс | недомінованих: {discrete.pareto_mask(X, np.ones(n)).sum()}')

