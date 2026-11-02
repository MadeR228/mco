"""Тести парсерів інтернет-магазинів на збережених фрагментах реальних сторінок (без мережі)."""
from pathlib import Path

import numpy as np
import pytest

from mco import shops
from mco.shops.fetch import Fetcher, ShopError
from mco.shops.specs import cpu_score, find_cpu, parse_specs

FIX = Path(__file__).resolve().parent / 'fixtures'


def read(name):
    return (FIX / name).read_text(encoding='utf-8')


def test_rozetka_saved_page():
    html = read('rozetka_notebooks.html')
    assert shops.detect_shop(html) == 'rozetka'
    df = shops.parse_file(html)
    assert len(df) == 12
    first = df.iloc[0]
    assert first['Модель'] == 'ASUS Vivobook 15 M1502XA-BQ012 (90NB19L1-M00160) Quiet Blue'
    assert first['Ціна, грн'] == 29999 and first['ОЗП, ГБ'] == 8 and first['SSD, ГБ'] == 512
    assert first['Діагональ, дюйм'] == 15.6 and first['Процесор'] == 'Ryzen 7 7840HS'
    mac = df[df['Модель'].str.contains('MacBook')].iloc[0]       # формат «A18 Pro 8/256GB»
    assert mac['Процесор'] == 'Apple A18 Pro' and mac['ОЗП, ГБ'] == 8 and mac['SSD, ГБ'] == 256
    loq = df[df['Модель'].str.contains('LOQ')].iloc[0]
    assert loq['Дискретна відеокарта'] == 1 and loq['Відеопам’ять, ГБ'] == 6 and loq['Частота екрана, Гц'] == 144


def test_brain_saved_page():
    html = read('brain_notebooks.html')
    assert shops.detect_shop(html) == 'brain'
    df = shops.parse_file(html)
    assert len(df) == 4
    assert df['Ціна, грн'].gt(10000).all() and df['Вага, кг'].between(0.8, 4).all()
    assert df['Акумулятор, Вт·год'].notna().any()
    assert df['Продуктивність CPU, бали'].notna().all()


def test_telemart_saved_page():
    html = read('telemart_laptops.html')
    assert shops.detect_shop(html) == 'telemart'
    df = shops.parse_file(html)
    assert len(df) == 4
    row = df.iloc[0]
    assert row['Ціна, грн'] == 39999 and row['ОЗП, ГБ'] == 16 and row['Вага, кг'] == 1.7


@pytest.mark.parametrize('text, cpu', [
    ('Intel Core i5-13420H', 'core i5-13420h'), ('Intel Core i9 14900HX (2.2 ГГц)', 'core i9-14900hx'),
    ('AMD Ryzen AI 9 HX 370', 'ryzen ai 9 hx 370'), ('Intel Core Ultra 7 155H', 'core ultra 7 155h'),
    ('MacBook Air 13" M4 16/512GB', 'apple m4'), ('Intel Celeron N4020', 'celeron n4020'),
    ('Intel Core 5 210H', 'core 5 210h'), ('Snapdragon X Elite', 'snapdragon x elite'),
])
def test_cpu_detection(text, cpu):
    assert find_cpu(text) == cpu
    assert cpu_score(cpu)[0] > 0


def test_cpu_estimate_for_unknown_model():
    score, source = cpu_score('core i7-99999h')
    assert source == 'оцінка' and score > cpu_score('core i7-99999u')[0]
    assert cpu_score(None) == (None, None)


def test_specs_formats():
    s = parse_specs('16", 2560x1600, Intel Core 5 210H, DDR - 16 ГБ, SSD - 1 ТБ, NVIDIA GeForce RTX 3050, '
                    'GPU - 6 ГБ, 60 Втг, 2.49 кг')
    assert s['screen'] == 16 and s['ram'] == 16 and s['ssd'] == 1024 and s['vram'] == 6
    assert s['battery_wh'] == 60 and s['weight'] == 2.49 and s['dgpu'] == 1
    s = parse_specs("Дисплей: 15.6″ (1920x1080, IPS) Оперативна пам'ять: 32 ГБ (DDR5) "
                    "Внутрішній накопичувач: 1 ТБ (SSD) Вага: 1.7 кг")
    assert s['screen'] == 15.6 and s['ram'] == 32 and s['ssd'] == 1024 and s['weight'] == 1.7


class FakeSite:
    """Імітація сайту: словник url -> (код, текст) і журнал запитів."""
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def __call__(self, url):
        self.calls.append(url)
        return self.pages.get(url, (404, ''))


def test_fetcher_respects_robots_and_caches(tmp_path):
    site = FakeSite({'https://shop.test/robots.txt': (200, 'User-agent: *\nDisallow: /private/'),
                     'https://shop.test/catalog/': (200, '<html>ok</html>')})
    f = Fetcher(delay=0, cache_dir=tmp_path, opener=site)
    assert f.get('https://shop.test/catalog/') == '<html>ok</html>'
    assert f.get('https://shop.test/catalog/') == '<html>ok</html>'          # другий раз – з кешу
    assert site.calls.count('https://shop.test/catalog/') == 1
    with pytest.raises(ShopError, match='robots.txt'):
        f.get('https://shop.test/private/page')
    assert 'https://shop.test/private/page' not in site.calls


def test_fetcher_stops_on_bot_challenge(tmp_path):
    challenge = (403, '<html><head><title>Just a moment...</title></head></html>')
    site = FakeSite({'https://shop.test/robots.txt': (200, ''), 'https://shop.test/c/': challenge})
    with pytest.raises(ShopError, match='перевірки браузера'):
        Fetcher(delay=0, cache_dir=tmp_path, opener=site).get('https://shop.test/c/')
    site = FakeSite({'https://shop.test/robots.txt': challenge})
    with pytest.raises(ShopError, match='захист'):
        Fetcher(delay=0, cache_dir=tmp_path, opener=site).get('https://shop.test/c/')


def test_load_pages_with_fake_site(tmp_path):
    page1, page2 = read('brain_notebooks.html'), read('telemart_laptops.html').replace('product-item', 'x')
    url = shops.SHOPS['brain']['url']
    site = FakeSite({'https://brain.com.ua/robots.txt': (200, 'User-agent: *\nDisallow: /api/'),
                     url(1): (200, page1), url(2): (200, page2)})
    df = shops.load('brain', pages=3, fetcher=Fetcher(delay=0, cache_dir=tmp_path, opener=site))
    assert len(df) == 4 and url(3) not in site.calls          # порожня 2-га сторінка зупиняє обхід
    with pytest.raises(ShopError, match='збережену сторінку'):
        shops.load('rozetka')


def test_parsed_table_works_with_methods():
    from mco import discrete
    df = shops.parse_file(read('rozetka_notebooks.html'))
    cols = ['Ціна, грн', 'Продуктивність CPU, бали', 'ОЗП, ГБ', 'SSD, ГБ']
    data = df.dropna(subset=cols)
    r = discrete.topsis(data[cols].to_numpy(float), np.array([-1, 1, 1, 1]), [0.4, 0.3, 0.2, 0.1])
    assert r.best is not None
