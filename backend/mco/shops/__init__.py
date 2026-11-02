"""Отримання таблиці альтернатив (ноутбуків) з каталогів інтернет-магазинів.

    >>> from mco import shops
    >>> df = shops.load('brain', pages=2)                 # завантаження з сайту
    >>> df = shops.parse_file(open('rozetka.html').read()) # збережена в браузері сторінка

Підтримувані джерела:
  brain     – brain.com.ua, завантаження з сайту або збереженої сторінки;
  telemart  – telemart.ua, завантаження з сайту або збереженої сторінки;
  rozetka   – rozetka.com.ua, лише збережена сторінка: сайт закритий перевіркою браузера
              для автоматичних запитів, і програма її не обходить.
"""
import re

import pandas as pd
from bs4 import BeautifulSoup

from .fetch import Fetcher, ShopError
from .specs import parse_price, parse_specs, pretty_cpu

COLUMNS = {   # внутрішній ключ → назва стовпця таблиці (як у data/laptops.csv)
    'price': 'Ціна, грн', 'cpu_score': 'Продуктивність CPU, бали', 'ram': 'ОЗП, ГБ', 'ssd': 'SSD, ГБ',
    'screen': 'Діагональ, дюйм', 'weight': 'Вага, кг', 'battery_wh': 'Акумулятор, Вт·год', 'hz': 'Частота екрана, Гц',
    'dgpu': 'Дискретна відеокарта', 'vram': 'Відеопам’ять, ГБ',
}


def _text(el):
    return ' '.join(el.get_text(' ').split()) if el is not None else ''


def _brand(b):
    """«MSI» і «ASUS» лишаються великими літерами, «LENOVO» → «Lenovo», «Acer» без змін."""
    b = (b or '').strip()
    if any(ch.islower() for ch in b):
        return b
    return b if len(b) <= 4 else b.title()


def _clean_name(name):
    name = re.sub(r'^\s*Ноутбук\s+', '', name)
    return name.split(' / ')[0].strip()


# ---------------------------------------------------------------------------
# Парсери сторінок каталогу: html -> список словників
# ---------------------------------------------------------------------------
def parse_brain(html):
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    for card in soup.select('div.br-pcg-product-wrapper'):
        name = card.get('data-name-ua') or card.get('data-name') or ''
        link = card.select_one('a[href]')
        specs = _text(card.select_one('.br-pp-i'))
        items.append({'name': name, 'brand': card.get('data-vendor', ''), 'price': parse_price(card.get('data-price')),
                      'specs': specs, 'url': link['href'] if link else ''})
    return items


def parse_telemart(html):
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    for card in soup.select('div.product-item__inner[data-prod-name]'):
        link = card.select_one('a[href*="/products/"]')
        # пари «Дисплей: … Процесор: …» – з блоку характеристик картки
        specs = ' '.join(_text(el) for el in card.select('[class*="product-short-char"], [class*="characteristic"]'))
        if not specs:
            specs = _text(card)
        items.append({'name': card['data-prod-name'], 'brand': card.get('data-prod-brand', ''),
                      'price': parse_price(card.get('data-prod-price') or card.get('data-price')),
                      'specs': specs, 'url': link['href'] if link else ''})
    return items


def parse_rozetka(html):
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    for tile in soup.select('rz-product-tile, rz-catalog-tile, .goods-tile'):
        a = tile.select_one('a.tile-title, a.goods-tile__heading, a[title]')
        price = tile.select_one('.price:not(.old-price), .goods-tile__price-value')
        if a is None or price is None:
            continue
        title = a.get('title') or _text(a)
        brand = re.sub(r'^\s*Ноутбук\s+', '', title).split()[0] if title else ''
        items.append({'name': title, 'brand': brand, 'price': parse_price(_text(price)), 'specs': title,
                      'url': a.get('href', '')})
    # один товар може бути в розмітці двічі (rz-catalog-tile містить rz-product-tile)
    seen, unique = set(), []
    for it in items:
        if it['url'] not in seen:
            seen.add(it['url'])
            unique.append(it)
    return unique


SHOPS = {
    'brain': {'title': 'Brain (brain.com.ua)', 'parse': parse_brain, 'marker': 'br-pcg-product-wrapper',
              'url': lambda n: 'https://brain.com.ua/ukr/category/Noutbuky-c1191/' + (f'page={n}/' if n > 1 else '')},
    'telemart': {'title': 'Telemart (telemart.ua)', 'parse': parse_telemart, 'marker': 'product-item__inner',
                 'url': lambda n: 'https://telemart.ua/ua/laptops/' + (f'?page={n}' if n > 1 else '')},
    'rozetka': {'title': 'Rozetka (rozetka.com.ua) – збережена сторінка', 'parse': parse_rozetka,
                'marker': 'rz-product-tile', 'url': None},
}


def detect_shop(html):
    for key, s in SHOPS.items():
        if s['marker'] in html:
            return key
    raise ShopError('Не вдалося визначити магазин: у файлі немає карток товарів Rozetka, Brain чи Telemart')


def to_frame(items, shop):
    """Список карток → таблиця альтернатив з числовими критеріями."""
    rows = []
    for it in items:
        if not it['price']:
            continue                                    # товар без ціни (немає в наявності)
        sp = parse_specs(it['name'] + ' / ' + it['specs'])
        row = {'Модель': _clean_name(it['name']), 'Бренд': _brand(it['brand']),
               'Магазин': shop, 'Процесор': pretty_cpu(sp.get('cpu')), 'Відеокарта': sp.get('gpu', '')}
        sp['price'] = it['price']
        if sp.get('dgpu') == 0:
            sp.setdefault('vram', 0.0)                  # інтегрована графіка – власної відеопам'яті немає
        for k, col in COLUMNS.items():
            row[col] = sp.get(k)
        row['Оцінка CPU'] = sp.get('cpu_source') or ''
        row['Посилання'] = it['url']
        rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        raise ShopError('На сторінці не знайдено карток товарів з ціною')
    df = df.drop_duplicates(subset=['Модель', 'Ціна, грн']).reset_index(drop=True)
    # стовпці, які магазин не надає зовсім, прибираємо
    return df[[c for c in df.columns if df[c].notna().any() and not (df[c] == '').all()]]


def parse_file(html, shop=None):
    shop = shop or detect_shop(html)
    return to_frame(SHOPS[shop]['parse'](html), shop)


def load(shop, pages=1, fetcher=None, use_cache=True, progress=None):
    """Завантажує pages сторінок каталогу магазину і повертає таблицю альтернатив."""
    if shop not in SHOPS:
        raise ShopError(f'Невідомий магазин: {shop}')
    if SHOPS[shop]['url'] is None:
        raise ShopError(f'{SHOPS[shop]["title"]}: автоматичне завантаження недоступне, імпортуйте збережену сторінку')
    pages = max(1, min(int(pages), 20))
    fetcher = fetcher or Fetcher()
    items = []
    for n in range(1, pages + 1):
        html = fetcher.get(SHOPS[shop]['url'](n), use_cache=use_cache)
        page_items = SHOPS[shop]['parse'](html)
        if not page_items:
            break
        items += page_items
        if progress:
            progress(n, pages, len(items))
    return to_frame(items, shop)


__all__ = ['SHOPS', 'Fetcher', 'ShopError', 'load', 'parse_file', 'detect_shop', 'to_frame']
