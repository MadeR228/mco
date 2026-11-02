"""Вбудовані набори даних, приклади неперервних задач і документація."""
import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

DATASETS = {
    'laptops': {'file': 'laptops.csv', 'title': 'Ноутбуки (27 моделей)', 'kind': 'example',
                'note': 'Орієнтовні характеристики й ціни моделей 2025–2026 рр. для навчальних цілей'},
    'smartphones': {'file': 'smartphones.csv', 'title': 'Смартфони (21 модель)', 'kind': 'example',
                    'note': 'Орієнтовні характеристики й ціни моделей 2025–2026 рр. для навчальних цілей'},
    'brain': {'file': 'brain_laptops.csv', 'title': 'Ноутбуки Brain – знімок каталогу 27.10.2026', 'kind': 'snapshot',
              'note': 'Реальні ціни й характеристики, отримані парсером з каталогу магазину'},
    'telemart': {'file': 'telemart_laptops.csv', 'title': 'Ноутбуки Telemart – знімок каталогу 27.10.2026',
                 'kind': 'snapshot', 'note': 'Реальні ціни й характеристики, отримані парсером з каталогу магазину'},
}

DEFAULT_CRITERIA = {   # напрям і вага критеріїв, які пропонуються для набору
    'laptops': {'Ціна, грн': ('min', 0.30), 'Продуктивність CPU, бали': ('max', 0.20),
                'Автономність, год': ('max', 0.20), 'Вага, кг': ('min', 0.10),
                'ОЗП, ГБ': ('max', 0.10), 'SSD, ГБ': ('max', 0.10)},
    'smartphones': {'Ціна, грн': ('min', 0.30), 'Продуктивність AnTuTu, тис.': ('max', 0.20),
                    'Акумулятор, мА·год': ('max', 0.15), 'Вага, г': ('min', 0.10),
                    'Пам’ять, ГБ': ('max', 0.10), 'Оновлення ОС, років': ('max', 0.15)},
}
SHOP_CRITERIA = {'Ціна, грн': ('min', 0.30), 'Продуктивність CPU, бали': ('max', 0.25), 'ОЗП, ГБ': ('max', 0.15),
                 'SSD, ГБ': ('max', 0.10), 'Вага, кг': ('min', 0.10), 'Акумулятор, Вт·год': ('max', 0.10)}
DEFAULT_CONSTRAINTS = {
    'laptops': [{'column': 'Ціна, грн', 'op': '≤', 'value': '70000'},
                {'column': 'Тип', 'op': 'не у списку', 'value': 'Ігровий'}],
    'smartphones': [{'column': 'Ціна, грн', 'op': '≤', 'value': '45000'}],
}
MIN_HINTS = ('ціна', 'вартість', 'вага', 'price', 'cost', 'weight', 'ризик', 'витрат', 'час')

DOCS = {'user_guide': 'Інструкція користувача', 'methods': 'Опис методів'}


def guess_sense(column):
    return 'min' if any(h in column.lower() for h in MIN_HINTS) else 'max'


def suggested_criteria(numeric_columns, dataset_id=None, is_shop=False):
    """Критерії за замовчуванням: для відомих наборів – задані, інакше – всі числові стовпці."""
    preset = DEFAULT_CRITERIA.get(dataset_id) or (SHOP_CRITERIA if is_shop else None)
    out = []
    for c in numeric_columns:
        if preset is not None:
            sense, w = preset.get(c, (guess_sense(c), 0.0))
            out.append({'name': c, 'sense': sense, 'weight': w, 'use': c in preset})
        else:
            out.append({'name': c, 'sense': guess_sense(c), 'weight': 1.0, 'use': True})
    return out


@lru_cache(maxsize=8)
def load_dataset(dataset_id):
    return pd.read_csv(ROOT / 'data' / DATASETS[dataset_id]['file'])


@lru_cache(maxsize=1)
def examples():
    order = ['production', 'binh_korn', 'portfolio']
    out = {}
    for f in sorted((ROOT / 'examples').glob('*.json'),
                    key=lambda f: (order.index(f.stem) if f.stem in order else 99, f.stem)):
        out[f.stem] = json.loads(f.read_text(encoding='utf-8'))
    return out


def doc(name):
    return (ROOT / 'docs' / f'{name}.md').read_text(encoding='utf-8')
