"""MCO Studio API – FastAPI-бекенд над бібліотекою mco.

Запуск для розробки:  uvicorn api.main:app --reload   (з теки backend)
Документація API:     http://localhost:8000/docs
"""
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from mco import __version__
from mco.shops import ShopError

from .jobs import jobs
from .routers import catalog, continuous, discrete, shops

app = FastAPI(title='MCO Studio API', version=__version__,
              description='Методи багатокритеріальної оптимізації (Multi-Criteria Optimization): дискретний '
                          'вибір, неперервні задачі, дані з інтернет-магазинів.')

origins = os.environ.get('MCO_CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173')
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in origins.split(',') if o.strip()],
                   allow_methods=['GET', 'POST'], allow_headers=['*'])


@app.exception_handler(ValueError)
async def value_error(_: Request, exc: ValueError):
    """Помилки введення з бібліотеки mco – зрозумілі повідомлення українською."""
    return JSONResponse(status_code=422, content={'detail': str(exc)})


@app.exception_handler(ShopError)
async def shop_error(_: Request, exc: ShopError):
    return JSONResponse(status_code=422, content={'detail': str(exc)})


@app.get('/api/health', tags=['службові'])
def health():
    return {'status': 'ok', 'version': __version__}


@app.get('/api/jobs/{job_id}', tags=['службові'])
def job(job_id: str):
    j = jobs.get(job_id)
    if j is None:
        raise HTTPException(404, 'Задачу не знайдено або вона застаріла')
    return j


for r in (catalog.router, discrete.router, continuous.router, shops.router):
    app.include_router(r)

# Зібраний фронтенд (npm run build → ../dist) віддається тим самим сервером: одна команда для запуску
DIST = Path(os.environ.get('MCO_FRONTEND_DIST', Path(__file__).resolve().parents[2] / 'dist'))
if DIST.is_dir():
    app.mount('/assets', StaticFiles(directory=DIST / 'assets'), name='assets')

    @app.get('/{path:path}', include_in_schema=False)
    def spa(path: str):
        if path == 'api' or path.startswith('api/'):
            raise HTTPException(404, 'Немає такого ендпоінта API')
        target = (DIST / path).resolve()
        if path and target.is_file() and DIST.resolve() in target.parents:
            return FileResponse(target)
        return FileResponse(DIST / 'index.html')      # маршрути React обробляє на клієнті
