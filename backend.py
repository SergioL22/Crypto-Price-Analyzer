"""Local HTTP entry point: uvicorn backend:create_app --factory --host 127.0.0.1."""
from typing import Annotated, Literal
from pathlib import Path as FilePath
import os
import re
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, Path, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from backend_models import (BacktestRequest, RecommendationRequest, Evidence, AnalysisResponse, BacktestResponse,
                            RecommendationResponse, CatalogResponse, PricesResponse, HealthResponse, ErrorResponse)
from backend_service import BackendError, BackendService
from backend_models import PortfolioResponse
from backend_models import HoldingUpdate, HoldingRemoval, SavedHoldingsResponse
from backend_models import RestorePreviewRequest, RestoreRequest
from backend_models import AlertCreate, AlertChange
from stock_models import AssetCatalog, StockResearch
from profile_models import CompanyProfileResponse
from local_config import load_local_config


def create_app(service=None, *, allowed_origin=None):
    load_local_config()
    origin = allowed_origin if allowed_origin is not None else os.environ.get('CRYPTO_ORIGIN', 'http://127.0.0.1:8000')
    match = re.fullmatch(r'http://(127\.0\.0\.1|localhost):([0-9]{1,5})', origin)
    if not match or not 1 <= int(match[2]) <= 65535 or str(int(match[2])) != match[2]:
        raise ValueError('CRYPTO_ORIGIN must be a loopback HTTP origin with an explicit port.')
    authority = origin.removeprefix('http://')
    service = service or BackendService()
    app = FastAPI(title='Market Research Desk', version='0.1.0',
                  description='Local single-user prototype. No authentication; use one worker on loopback only.')
    app.state.service = service

    @app.middleware('http')
    async def hide_unexpected_errors(request, call_next):
        try:
            return await call_next(request)
        except Exception:
            # Do not expose or log arbitrary provider payloads, positions, or secrets.
            return JSONResponse(status_code=500, content={'error': {
                'code': 'internal_error', 'message': 'An unexpected server error occurred.'}})

    @app.exception_handler(BackendError)
    async def backend_error(request, error):
        body = {'error': {'code': error.code, 'message': error.message}}
        if error.coverage is not None:
            body['coverage'] = error.coverage
        headers = {'Retry-After': str(error.retry_after_seconds)} if error.retry_after_seconds else {'Retry-After':'1'} if error.status==429 else None
        return JSONResponse(status_code=error.status, content=body, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        # Pydantic's default body includes rejected input; don't echo private values.
        return JSONResponse(status_code=422, content={'error': {
            'code': 'invalid_request', 'message': 'Request fields do not match the documented schema.'}})

    @app.middleware('http')
    async def local_origin_only(request, call_next):
        hosts = request.headers.getlist('host')
        origins = request.headers.getlist('origin')
        if hosts != [authority] or (origins and origins != [origin]):
            return JSONResponse(status_code=403, content={'error': {
                'code': 'origin_forbidden', 'message': 'Request origin is not allowed.'}})
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Cache-Control'] = 'no-store'
        if request.url.path in ('/', '/crypto.html', '/stocks.html', '/watchlist.html', '/portfolio.html', '/backups.html', '/alerts.html') or request.url.path.startswith('/assets/'):
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        return response

    errors = {status: {'model': ErrorResponse} for status in (409, 422, 429, 500, 502, 503)}

    @app.get('/health', response_model=HealthResponse)
    async def health():
        return {'status': 'ok'}

    @app.get('/v1/alerts', responses=errors)
    def alerts():
        return service.alerts()

    @app.post('/v1/alerts', responses=errors)
    def create_alert(body: AlertCreate):
        return service.alerts(body)

    @app.patch('/v1/alerts/{alert_id}', responses=errors)
    def change_alert(alert_id: Annotated[int, Path(ge=1)], body: AlertChange):
        return service.alerts(alert_id=alert_id, active=body.active)

    @app.delete('/v1/alerts/{alert_id}', responses=errors)
    def remove_alert(alert_id: Annotated[int, Path(ge=1)]):
        return service.alerts(alert_id=alert_id)

    @app.post('/v1/alerts/check', responses=errors)
    def check_alerts():
        return service.check_alerts()

    @app.post('/v1/holdings/restore/preview', responses=errors)
    def preview_restore(body: RestorePreviewRequest):
        return service.restore_holdings(body, preview=True)

    @app.post('/v1/holdings/restore', response_model=SavedHoldingsResponse, responses=errors)
    def restore_holdings(body: RestoreRequest):
        return service.restore_holdings(body)

    @app.get('/v1/holdings/export', response_class=Response, responses=errors)
    def export_holdings():
        return Response(service.export_holdings(), media_type='application/json',
                        headers={'Content-Disposition': 'attachment; filename="portfolio-backup.json"'})

    @app.get('/v1/holdings', response_model=SavedHoldingsResponse, responses=errors)
    def saved_holdings():
        return service.saved_holdings()

    @app.put('/v1/holdings', response_model=SavedHoldingsResponse, responses=errors)
    def update_holding(body: HoldingUpdate):
        return service.saved_holdings(body)

    @app.delete('/v1/holdings', response_model=SavedHoldingsResponse, responses=errors)
    def remove_holding(body: HoldingRemoval):
        return service.saved_holdings(body, remove=True)

    @app.get('/v1/portfolio', response_model=PortfolioResponse, responses=errors)
    def portfolio():
        return service.portfolio()

    @app.get('/v1/coins', response_model=CatalogResponse, responses=errors)
    def coins():
        return service.coins()

    @app.get('/v1/assets', response_model=AssetCatalog, responses=errors)
    def asset_catalog(asset_class: Literal['crypto', 'stock', 'etf'] = 'stock'):
        return service.asset_catalog(asset_class)

    @app.get('/v1/company-profile',response_model=CompanyProfileResponse,responses=errors)
    def company_profile(asset_id:Annotated[str,Query(min_length=1,max_length=160)]):
        return service.company_profile(asset_id)

    @app.get('/v1/stock-analysis', response_model=StockResearch, responses=errors)
    def stock_research(asset_id: Annotated[str, Query(min_length=1, max_length=160)],
                       days: Annotated[int, Query(ge=1, le=3660)] = 3653,refresh:bool=False):
        return service.stock_research(asset_id, days,refresh=refresh)

    @app.get('/v1/prices', response_model=PricesResponse, responses=errors)
    def prices():
        return service.prices()

    @app.get('/v1/analysis/{coin_id}', response_model=AnalysisResponse, responses=errors)
    def evidence(coin_id: Annotated[str, Path(min_length=1, max_length=100, pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$')],
                 days: Annotated[int, Query(ge=35, le=365)] = 90, include_history: bool = False):
        return service.evidence(coin_id, days, include_history=include_history)

    @app.post('/v1/backtests', response_model=BacktestResponse, responses=errors)
    def backtest(body: BacktestRequest):
        return service.backtest(body.coin_id, body.days, body.strategy)

    @app.post('/v1/recommendations', response_model=RecommendationResponse, responses=errors)
    def recommendation(body: RecommendationRequest):
        position = None if body.selected_position is None else body.selected_position.model_dump()
        return service.recommend(body.coin_id, body.days, position)

    app.mount('/', StaticFiles(directory=FilePath(__file__).resolve().parent / 'static', html=True), name='dashboard')
    return app
