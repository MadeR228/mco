"""Довідкові дані: методи з параметрами, набори даних, приклади, документація, завантаження файлів."""
import io

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile

from mco import continuous as cont
from mco import discrete as disc
from mco import shops
from mco.constraints import OPERATORS
from mco.normalize import NORMALIZATIONS

from .. import catalog
from ..convert import clean, frame_to_table

router = APIRouter(prefix='/api', tags=['довідка'])

MAX_UPLOAD = 20 * 1024 * 1024

WEIGHT_METHODS = [
    {'key': 'manual', 'title': 'Вручну', 'needs': []},
    {'key': 'equal', 'title': 'Рівні', 'needs': []},
    {'key': 'ahp', 'title': 'AHP – парні порівняння', 'needs': ['matrix']},
    {'key': 'entropy', 'title': 'Ентропія', 'needs': ['records']},
    {'key': 'critic', 'title': 'CRITIC', 'needs': ['records']},
    {'key': 'roc', 'title': 'ROC – за рангом важливості', 'needs': ['order']},
]


@router.get('/methods')
def methods():
    """Реєстр методів: за описом параметрів фронтенд будує форми автоматично."""
    def param(p):
        return {'name': p.name, 'label': p.label, 'kind': p.kind, 'default': p.default, 'min': p.min, 'max': p.max,
                'step': p.step, 'options': ['inf' if o == float('inf') else o for o in p.options],
                'help': p.help or None}
    return clean({
        'discrete': [{'key': k, 'title': s.title, 'abbr': s.abbr, 'description': s.short,
                      'uses_weights': s.uses_weights, 'params': [param(p) for p in s.params]}
                     for k, s in disc.METHODS.items()],
        'continuous': [{'key': k, 'title': t} for k, t in cont.METHODS.items()],
        'fronts': [{'key': k, 'title': t} for k, t in cont.FRONT_METHODS.items()],
        'weights': WEIGHT_METHODS,
        'operators': list(OPERATORS),
        'normalizations': [{'key': k, 'title': t} for k, (t, _) in NORMALIZATIONS.items()],
    })


@router.get('/datasets')
def datasets():
    out = []
    for key, d in catalog.DATASETS.items():
        df = catalog.load_dataset(key)
        out.append({'id': key, 'title': d['title'], 'kind': d['kind'], 'note': d['note'], 'rows': len(df)})
    return out


def _table_response(df, dataset_id=None, **extra):
    table = frame_to_table(df)
    table['suggested_criteria'] = catalog.suggested_criteria(
        table['numeric_columns'], dataset_id, is_shop='Магазин' in table['columns'])
    table['suggested_constraints'] = catalog.DEFAULT_CONSTRAINTS.get(dataset_id, [])
    table.update(extra)
    return table


@router.get('/datasets/{dataset_id}')
def dataset(dataset_id: str):
    if dataset_id not in catalog.DATASETS:
        raise HTTPException(404, f'Немає набору даних «{dataset_id}»')
    d = catalog.DATASETS[dataset_id]
    return _table_response(catalog.load_dataset(dataset_id), dataset_id, id=dataset_id, title=d['title'],
                           note=d['note'])


@router.post('/upload')
async def upload(file: UploadFile = File(...)):
    """CSV (роздільник «,» або «;»), Excel або збережена сторінка каталогу магазину (HTML)."""
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, 'Файл більший за 20 МБ')
    name = (file.filename or '').lower()
    try:
        if name.endswith(('.html', '.htm')):
            df = shops.parse_file(data.decode('utf-8', errors='replace'))
        elif name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(io.BytesIO(data))
        elif name.endswith(('.csv', '.txt')) or not name:
            raw = data.decode('utf-8-sig', errors='replace')
            sep = ';' if raw.count(';') > raw.count(',') else ','
            df = pd.read_csv(io.StringIO(raw), sep=sep, decimal=',' if sep == ';' else '.')
        else:
            raise ValueError('Підтримуються файли CSV, Excel (.xlsx) і HTML')
    except (shops.ShopError, ValueError) as e:
        raise HTTPException(422, str(e)) from None
    except Exception as e:       # пошкоджений файл
        raise HTTPException(422, f'Не вдалося прочитати файл: {type(e).__name__}') from None
    if df.empty:
        raise HTTPException(422, 'У файлі немає рядків')
    return _table_response(df, title=file.filename)


@router.get('/continuous/examples')
def continuous_examples():
    return [{'id': k, 'title': e['title'], 'description': e['description'],
             'objectives': len(e['objectives']), 'variables': len(e['variables'])} for k, e in catalog.examples().items()]


@router.get('/continuous/examples/{example_id}')
def continuous_example(example_id: str):
    ex = catalog.examples()
    if example_id not in ex:
        raise HTTPException(404, f'Немає прикладу «{example_id}»')
    return {'id': example_id, **ex[example_id]}


@router.get('/docs')
def docs():
    return [{'id': k, 'title': t} for k, t in catalog.DOCS.items()]


@router.get('/docs/{name}')
def doc(name: str):
    if name not in catalog.DOCS:
        raise HTTPException(404, f'Немає документа «{name}»')
    return {'id': name, 'title': catalog.DOCS[name], 'markdown': catalog.doc(name)}
