"""Консольне завантаження каталогу ноутбуків у CSV.

    python -m mco.shops brain --pages 3 --out data/brain_laptops.csv
    python -m mco.shops file збережена_сторінка_rozetka.html --out data/rozetka_laptops.csv
"""
import argparse
import sys
from pathlib import Path

from . import SHOPS, Fetcher, ShopError, load, parse_file


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m mco.shops', description='Завантаження ноутбуків з інтернет-магазину')
    ap.add_argument('source', help='brain | telemart | file')
    ap.add_argument('path', nargs='?', help='HTML-файл для source=file')
    ap.add_argument('--pages', type=int, default=2, help='кількість сторінок каталогу (1–20)')
    ap.add_argument('--delay', type=float, default=2.0, help='пауза між запитами, с')
    ap.add_argument('--no-cache', action='store_true', help='не використовувати збережені сторінки')
    ap.add_argument('--out', help='CSV-файл для збереження')
    a = ap.parse_args(argv)
    try:
        if a.source == 'file':
            if not a.path:
                ap.error('вкажіть HTML-файл')
            df = parse_file(Path(a.path).read_text(encoding='utf-8', errors='replace'))
        elif a.source in SHOPS:
            f = Fetcher(delay=a.delay)
            df = load(a.source, a.pages, fetcher=f, use_cache=not a.no_cache,
                      progress=lambda n, total, k: print(f'сторінка {n}/{total}: усього {k} товарів'))
        else:
            ap.error(f'невідоме джерело: {a.source}')
    except ShopError as e:
        print('Помилка:', e, file=sys.stderr)
        return 1
    print(f'Отримано {len(df)} ноутбуків, стовпці: {", ".join(df.columns)}')
    show = [c for c in ('Модель', 'Процесор', 'Ціна, грн', 'Продуктивність CPU, бали', 'ОЗП, ГБ', 'SSD, ГБ',
                        'Вага, кг', 'Акумулятор, Вт·год') if c in df.columns]
    print(df[show].head(10).to_string(index=False, max_colwidth=42))
    print('Пропуски:', ', '.join(f'{c} – {n}' for c, n in df.isna().sum().items() if n) or 'немає')
    if a.out:
        df.to_csv(a.out, index=False, encoding='utf-8-sig')
        print('Збережено:', a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
