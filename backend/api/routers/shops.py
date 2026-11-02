"""Інтернет-магазини: список джерел і фонове завантаження каталогу."""
from fastapi import APIRouter, HTTPException

from mco import shops

from .. import catalog
from ..convert import frame_to_table
from ..jobs import jobs
from ..schemas import ShopLoadRequest

router = APIRouter(prefix='/api', tags=['магазини'])

PAGE_SIZE = {'brain': 24, 'telemart': 48}


@router.get('/shops')
def shop_list():
    return [{'id': k, 'title': s['title'], 'live': s['url'] is not None, 'page_size': PAGE_SIZE.get(k),
             'note': None if s['url'] else 'Сайт закриває каталог перевіркою браузера – імпортуйте збережену '
                                           'сторінку (Ctrl+S → «Веб-сторінка, лише HTML») через /api/upload'}
            for k, s in shops.SHOPS.items()]


@router.post('/jobs/shops/{shop}', status_code=202)
def load_job(shop: str, req: ShopLoadRequest):
    if shop not in shops.SHOPS:
        raise HTTPException(404, f'Невідомий магазин «{shop}»')
    if shops.SHOPS[shop]['url'] is None:
        raise HTTPException(422, f'{shops.SHOPS[shop]["title"]}: автоматичне завантаження недоступне, '
                                 f'імпортуйте збережену сторінку через /api/upload')

    def run(report):
        fetcher = shops.Fetcher(delay=2.0)
        report(0.02, 'читаю robots.txt')
        df = shops.load(shop, req.pages, fetcher=fetcher, use_cache=req.use_cache,
                        progress=lambda n, total, k: report(n / total, f'сторінка {n} з {total}: {k} товарів'))
        table = frame_to_table(df)
        table['suggested_criteria'] = catalog.suggested_criteria(table['numeric_columns'], is_shop=True)
        table['suggested_constraints'] = []
        table['title'] = f'{shops.SHOPS[shop]["title"]}, {req.pages} стор.'
        table['log'] = fetcher.log
        return table

    return jobs.submit('shop', run)
