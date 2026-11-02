"""Тести HTTP API (FastAPI TestClient): кожен ендпоінт, перевірка введення і фонові задачі."""
import io
import json
import time
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.main import app
from mco import discrete as disc
from mco import continuous as cont
from mco.shops.fetch import Fetcher

FIX = Path(__file__).resolve().parent / 'fixtures'
client = TestClient(app)


def ok(resp, status=200):
    assert resp.status_code == status, resp.text
    json.loads(resp.text, parse_constant=lambda c: pytest.fail(f'у JSON є {c}'))   # жодних NaN/Infinity
    return resp.json()


@pytest.fixture(scope='module')
def laptops():
    d = ok(client.get('/api/datasets/laptops'))
    return {'records': d['records'], 'criteria': [c for c in d['suggested_criteria'] if c['use']],
            'constraints': d['suggested_constraints']}


@pytest.fixture(scope='module')
def production():
    ex = ok(client.get('/api/continuous/examples/production'))
    return {k: ex[k] for k in ('variables', 'objectives', 'constraints')}


def wait(job, timeout=60):
    t0 = time.time()
    while job['status'] in ('queued', 'running'):
        assert time.time() - t0 < timeout, 'задача не завершилась'
        time.sleep(0.05)
        job = ok(client.get(f'/api/jobs/{job["id"]}'))
    return job


# --------------------------------------------------------------------- довідка й дані
def test_health_and_methods():
    assert ok(client.get('/api/health'))['status'] == 'ok'
    m = ok(client.get('/api/methods'))
    assert [x['key'] for x in m['discrete']] == list(disc.METHODS)
    ideal = next(x for x in m['discrete'] if x['key'] == 'ideal_point')
    assert ideal['params'][0]['options'] == [1.0, 2.0, 3.0, 'inf']
    assert {x['key'] for x in m['continuous']} == set(cont.METHODS)
    assert '≤' in m['operators'] and len(m['weights']) == 6


def test_datasets_and_examples():
    ids = {d['id'] for d in ok(client.get('/api/datasets'))}
    assert ids == {'laptops', 'smartphones', 'brain', 'telemart'}
    brain = ok(client.get('/api/datasets/brain'))
    assert brain['rows'] == 48 and brain['name_column'] == 'Модель'
    used = {c['name'] for c in brain['suggested_criteria'] if c['use']}
    assert 'Акумулятор, Вт·год' in used and 'Ціна, грн' in used
    assert client.get('/api/datasets/nope').status_code == 404
    assert len(ok(client.get('/api/continuous/examples'))) == 3
    assert 'MCO Studio' in ok(client.get('/api/docs/user_guide'))['markdown']
    assert client.get('/api/docs/secret').status_code == 404


def test_upload_csv_excel_html():
    csv = 'Модель;Ціна;Якість\nA;100,5;3\nB;200;5\n'.encode('utf-8')
    t = ok(client.post('/api/upload', files={'file': ('x.csv', csv, 'text/csv')}))
    assert t['rows'] == 2 and t['numeric_columns'] == ['Ціна', 'Якість'] and t['records'][0]['Ціна'] == 100.5
    buf = io.BytesIO()
    pd.DataFrame({'Назва': ['A', 'B'], 'x': [1, 2]}).to_excel(buf, index=False)
    t = ok(client.post('/api/upload', files={'file': ('x.xlsx', buf.getvalue(), 'application/octet-stream')}))
    assert t['rows'] == 2
    html = (FIX / 'rozetka_notebooks.html').read_bytes()
    t = ok(client.post('/api/upload', files={'file': ('rozetka.html', html, 'text/html')}))
    assert t['rows'] == 12 and t['name_column'] == 'Модель'
    assert any(c['use'] for c in t['suggested_criteria'])
    r = client.post('/api/upload', files={'file': ('x.pdf', b'%PDF', 'application/pdf')})
    assert r.status_code == 422 and 'CSV' in r.json()['detail']


# --------------------------------------------------------------------- дискретний вибір
@pytest.mark.parametrize('method', list(disc.METHODS))
def test_every_discrete_method(laptops, method):
    r = ok(client.post('/api/discrete/solve', json={'problem': laptops, 'method': method}))
    assert r['counts'] == {'total': 27, 'feasible': 18, 'pareto': 15}
    assert r['best'] is not None and len(r['alternatives']) == 18 and len(r['excluded']) == 9
    assert [a['rank'] for a in r['alternatives']] == sorted(a['rank'] for a in r['alternatives'])
    assert set(r['alternatives'][0]['normalized']) == {c['name'] for c in laptops['criteria']}


def test_known_results(laptops):
    ws = ok(client.post('/api/discrete/solve', json={'problem': laptops, 'method': 'weighted_sum'}))
    assert ws['best']['name'] == 'Lenovo Yoga Slim 7x 32/1TB' and abs(ws['best']['score'] - 0.738) < 1e-3
    tp = ok(client.post('/api/discrete/solve', json={'problem': laptops, 'method': 'topsis'}))
    assert tp['best']['name'] == 'Lenovo IdeaPad Slim 5 14 16/1TB'
    mc = ok(client.post('/api/discrete/solve', json={'problem': laptops, 'method': 'main_criterion', 'params': {
        'main': 'Продуктивність CPU, бали', 'thresholds': {'Ціна, грн': 50000, 'Автономність, год': 12}}}))
    assert mc['best']['name'] == 'Apple MacBook Air 13 M4 16/256' and mc['params']['main'] == 'Продуктивність CPU, бали'
    excluded = {e['name']: e['reasons'] for e in ws['excluded']}
    assert excluded['Apple MacBook Pro 14 M4 16/512'] == ['Ціна, грн ≤ 70000']


def test_param_validation(laptops):
    def err(method, params):
        r = client.post('/api/discrete/solve', json={'problem': laptops, 'method': method, 'params': params})
        assert r.status_code == 422, r.text
        return r.json()['detail']
    assert 'не має параметрів' in err('topsis', {'p': 2})
    assert 'допустимі значення' in err('ideal_point', {'p': 7})
    assert 'межах' in err('vikor', {'v': 3})
    assert 'Невідомий критерій' in err('main_criterion', {'main': 'Колір'})
    assert 'Невідомий метод' in err('magic', {})


def test_problem_validation(laptops):
    one = {**laptops, 'criteria': laptops['criteria'][:1]}
    assert client.post('/api/discrete/solve', json={'problem': one, 'method': 'topsis'}).status_code == 422
    zero = {**laptops, 'criteria': [{**c, 'weight': 0} for c in laptops['criteria']]}
    r = client.post('/api/discrete/solve', json={'problem': zero, 'method': 'topsis'})
    assert r.status_code == 422 and 'Сума ваг' in r.json()['detail']
    bad = {**laptops, 'constraints': [{'column': 'Ціна, грн', 'op': 'приблизно', 'value': 1}]}
    assert client.post('/api/discrete/solve', json={'problem': bad, 'method': 'topsis'}).status_code == 422
    none = {**laptops, 'constraints': [{'column': 'Ціна, грн', 'op': '≤', 'value': '1'}]}
    r = client.post('/api/discrete/solve', json={'problem': none, 'method': 'topsis'})
    assert r.status_code == 422 and 'Жодна' in r.json()['detail']
    text = {**laptops, 'criteria': [{'name': 'Модель', 'sense': 'max'}, *laptops['criteria']]}
    r = client.post('/api/discrete/solve', json={'problem': text, 'method': 'topsis'})
    assert r.status_code == 422 and 'нечислові' in r.json()['detail']


def test_missing_values_policy():
    brain = ok(client.get('/api/datasets/brain'))
    p = {'records': brain['records'], 'criteria': [c for c in brain['suggested_criteria'] if c['use']]}
    r = client.post('/api/discrete/solve', json={'problem': p, 'method': 'topsis'})
    assert r.status_code == 422 and 'missing' in r.json()['detail']
    drop = ok(client.post('/api/discrete/solve', json={'problem': {**p, 'missing': 'drop'}, 'method': 'topsis'}))
    assert drop['counts']['feasible'] == 42 and drop['best']['name'].startswith('Thunderobot Aibook14')
    assert all(e['reasons'][0].startswith('немає значень') for e in drop['excluded'])
    med = ok(client.post('/api/discrete/solve', json={'problem': {**p, 'missing': 'median'}, 'method': 'topsis'}))
    assert med['counts']['feasible'] == 48


def test_compare_sensitivity_montecarlo(laptops):
    c = ok(client.post('/api/discrete/compare', json={'problem': laptops}))
    assert c['consensus'] == {'index': 13, 'name': 'Lenovo IdeaPad Slim 5 14 16/1TB', 'borda': 125}
    assert len(c['spearman']) == len(c['methods']) == 8
    s = ok(client.post('/api/discrete/sensitivity', json={'problem': laptops, 'method': 'topsis',
                                                          'criterion': 'Ціна, грн', 'steps': 21}))
    assert s['winners'][0] == 'Lenovo Yoga Slim 7x 32/1TB' and len(s['weights']) == 21 and s['switches']
    m = ok(client.post('/api/discrete/montecarlo', json={'problem': laptops, 'method': 'topsis',
                                                         'samples': 300, 'seed': 1}))
    assert m['alternatives'][0]['name'] == 'Lenovo IdeaPad Slim 5 14 16/1TB'
    assert abs(sum(a['first'] for a in m['alternatives']) - 1) < 1e-9
    r = client.post('/api/discrete/sensitivity', json={'problem': laptops, 'method': 'pareto', 'criterion': 'Ціна, грн'})
    assert r.status_code == 422
    f = ok(client.post('/api/discrete/feasibility', json=laptops))
    assert f['feasible'] == 18 and len(f['excluded']) == 9


def test_weights(laptops):
    crit = laptops['criteria']
    names = [c['name'] for c in crit]
    eq = ok(client.post('/api/weights/equal', json={'criteria': crit}))['weights']
    assert all(abs(v - 1 / 6) < 1e-9 for v in eq.values())
    roc = ok(client.post('/api/weights/roc', json={'criteria': crit, 'order': [names[2], names[0]]}))['weights']
    assert roc[names[2]] > roc[names[0]] > roc[names[1]]
    true = [0.4, 0.2, 0.15, 0.1, 0.1, 0.05]
    A = [[a / b for b in true] for a in true]
    ahp = ok(client.post('/api/weights/ahp', json={'criteria': crit, 'matrix': A}))
    assert ahp['consistent'] and abs(ahp['weights'][names[0]] - 0.4) < 1e-9
    for m in ('entropy', 'critic'):
        w = ok(client.post(f'/api/weights/{m}', json={'criteria': crit, 'records': laptops['records']}))['weights']
        assert abs(sum(w.values()) - 1) < 1e-9
    assert client.post('/api/weights/entropy', json={'criteria': crit}).status_code == 422
    assert client.post('/api/weights/ahp', json={'criteria': crit, 'matrix': [[1]]}).status_code == 422


# --------------------------------------------------------------------- неперервні задачі
def test_continuous_analyze_and_methods(production):
    a = ok(client.post('/api/continuous/analyze', json=production))
    assert a['linear'] and abs(a['ideal']['Прибуток'] - 1464 / 11) < 1e-6 and a['nadir']['Відходи'] > 11
    cases = {'weighted_sum': {}, 'ideal_point': {'p': 'inf'}, 'eps_constraint': {'main': 'Прибуток', 'eps': {'Відходи': 6}},
             'lexicographic': {'order': ['Прибуток'], 'concession': 0.1}, 'goal_programming': {'targets': {'Прибуток': 100, 'Відходи': 8}}}
    for method, params in cases.items():
        s = ok(client.post('/api/continuous/solve', json={'problem': production, 'method': method, 'params': params}))
        assert s['violation'] < 1e-6 and set(s['x']) == {'x1', 'x2'}
    eps = ok(client.post('/api/continuous/solve', json={'problem': production, 'method': 'eps_constraint',
                                                        'params': {'main': 'Прибуток', 'eps': {'Відходи': 6}}}))
    assert abs(eps['f']['Прибуток'] - 108) < 1e-6
    r = client.post('/api/continuous/solve', json={'problem': production, 'method': 'ideal_point', 'params': {'q': 1}})
    assert r.status_code == 422


@pytest.mark.parametrize('expr', ['__import__("os").system("x")', 'x1.__class__', 'open("f")', 'eval("1")',
                                  'lambda: 1', 'x1; 1', 'x1 + z'])
def test_formula_injection_rejected(production, expr):
    bad = {**production, 'objectives': [{**production['objectives'][0], 'expr': expr}, production['objectives'][1]]}
    r = client.post('/api/continuous/analyze', json=bad)
    assert r.status_code == 422


def test_front_sync_methods(production):
    for method in ('chebyshev', 'eps', 'weighted'):
        f = ok(client.post('/api/continuous/front', json={'problem': production, 'method': method, 'points': 10}))
        assert len(f['points']) >= 3 and f['compromise'] is not None


def test_front_job_nsga(production):
    job = ok(client.post('/api/jobs/front', json={'problem': production, 'method': 'nsga2',
                                                  'nsga': {'pop_size': 40, 'generations': 30, 'seed': 1}}), 202)
    job = wait(job)
    assert job['status'] == 'done' and job['progress'] == 1.0
    res = job['result']
    assert len(res['points']) > 10 and len(res['convergence']) == 30 and res['evaluations'] == 40 + 30 * 40
    assert client.get('/api/jobs/unknown').status_code == 404
    bad = {**production, 'objectives': [{**production['objectives'][0], 'expr': 'x9'}, production['objectives'][1]]}
    assert client.post('/api/jobs/front', json={'problem': bad, 'method': 'nsga2'}).status_code == 422


# --------------------------------------------------------------------- магазини
def test_shop_list_and_rozetka():
    shops = {s['id']: s for s in ok(client.get('/api/shops'))}
    assert shops['brain']['live'] and not shops['rozetka']['live']
    assert client.post('/api/jobs/shops/rozetka', json={}).status_code == 422
    assert client.post('/api/jobs/shops/amazon', json={}).status_code == 404
    assert client.post('/api/jobs/shops/brain', json={'pages': 50}).status_code == 422


def test_shop_job_with_fake_site(monkeypatch, tmp_path):
    from mco import shops
    url = shops.SHOPS['brain']['url']
    pages = {'https://brain.com.ua/robots.txt': (200, 'User-agent: *\nDisallow: /api/'),
             url(1): (200, (FIX / 'brain_notebooks.html').read_text(encoding='utf-8')), url(2): (200, '<html></html>')}
    calls = []

    def fake_fetcher(delay=2.0):
        return Fetcher(delay=0, cache_dir=tmp_path, opener=lambda u: (calls.append(u), pages.get(u, (404, '')))[1])

    monkeypatch.setattr('api.routers.shops.shops.Fetcher', fake_fetcher)
    job = wait(ok(client.post('/api/jobs/shops/brain', json={'pages': 2, 'use_cache': False}), 202))
    assert job['status'] == 'done', job
    assert job['result']['rows'] == 4 and 'Модель' in job['result']['columns'] and job['result']['log']
    assert url(1) in calls


def test_shop_job_reports_block(monkeypatch, tmp_path):
    challenge = (403, '<html><title>Just a moment...</title></html>')
    monkeypatch.setattr('api.routers.shops.shops.Fetcher',
                        lambda delay=2.0: Fetcher(delay=0, cache_dir=tmp_path, opener=lambda u: challenge))
    job = wait(ok(client.post('/api/jobs/shops/telemart', json={'pages': 1, 'use_cache': False}), 202))
    assert job['status'] == 'error' and 'захист' in job['error']
