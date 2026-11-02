"""Приклад роботи з MCO API без браузера: вибір ноутбука та неперервна задача.

Запуск (бекенд має працювати на :8000):  python examples/api_demo.py
"""
import json
import sys
import time
import urllib.request

API = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8000'


def call(path, body=None):
    req = urllib.request.Request(API + path, method='POST' if body is not None else 'GET',
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


print('=== 1. GET /api/methods: реєстр методів ===')
meta = call('/api/methods')
print('Дискретні:', ', '.join(m['abbr'] for m in meta['discrete']))
print('Неперервні:', ', '.join(m['title'] for m in meta['continuous']))

print('\n=== 2. POST /api/discrete/solve: ноутбуки, ціна ≤ 70 000 грн, не ігрові ===')
ds = call('/api/datasets/laptops')
problem = {'records': ds['records'], 'criteria': [c for c in ds['suggested_criteria'] if c['use']],
           'constraints': ds['suggested_constraints']}
for method, params in (('weighted_sum', {}), ('topsis', {}), ('ideal_point', {'p': 'inf'}), ('vikor', {'v': 0.5})):
    r = call('/api/discrete/solve', {'problem': problem, 'method': method, 'params': params})
    print(f"{r['title'][:42]:42s} → {r['best']['name']:34s} {r['best']['score']:8.4f}  "
          f"({r['counts']['feasible']} з {r['counts']['total']}, Парето {r['counts']['pareto']}, {r['elapsed_ms']:.2f} мс)")
c = call('/api/discrete/compare', {'problem': problem})
print(f"Консенсус Борда: {c['consensus']['name']} ({c['consensus']['borda']} балів)")

print('\n=== 3. POST /api/weights/ahp: узгодженість суджень ===')
w = [0.3, 0.2, 0.2, 0.1, 0.1, 0.1]
ahp = call('/api/weights/ahp', {'criteria': problem['criteria'], 'matrix': [[a / b for b in w] for a in w]})
print('Ваги:', ', '.join(f'{k} {v:.2f}' for k, v in ahp['weights'].items()), f"| CR = {ahp['cr']:.4f}")

print('\n=== 4. Неперервна задача (ЛР 11) і фонова задача NSGA-II ===')
ex = call('/api/continuous/examples/production')
cp = {k: ex[k] for k in ('variables', 'objectives', 'constraints')}
a = call('/api/continuous/analyze', cp)
print('Лінійна:', a['linear'], '| ідеал:', {k: round(v, 3) for k, v in a['ideal'].items()})
s = call('/api/continuous/solve', {'problem': cp, 'method': 'ideal_point', 'params': {'p': 'inf'}})
print('Тихонова, p = ∞: x =', {k: round(v, 3) for k, v in s['x'].items()}, 'f =', {k: round(v, 3) for k, v in s['f'].items()})
job = call('/api/jobs/front', {'problem': cp, 'method': 'nsga2', 'nsga': {'pop_size': 80, 'generations': 60, 'seed': 1}})
while job['status'] in ('queued', 'running'):
    time.sleep(0.2)
    job = call(f"/api/jobs/{job['id']}")
res = job['result']
print(f"NSGA-II: {job['status']}, {len(res['points'])} точок фронту, {res['evaluations']} обчислень, {res['elapsed_ms']:.0f} мс")

print('\n=== 5. Перевірка введення: формула з __import__ ===')
bad = {**cp, 'objectives': [{**cp['objectives'][0], 'expr': '__import__("os").system("dir")'}, cp['objectives'][1]]}
try:
    call('/api/continuous/analyze', bad)
except urllib.error.HTTPError as e:
    print(e.code, json.loads(e.read())['detail'])
