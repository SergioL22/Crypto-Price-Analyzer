"""Local HTTP entry point: uvicorn backend:create_app --factory --host 127.0.0.1."""
from typing import Annotated
from fastapi import FastAPI, Path, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend_models import (BacktestRequest, RecommendationRequest, Evidence, BacktestResponse,
                            RecommendationResponse, PricesResponse, HealthResponse, ErrorResponse)
from backend_service import BackendError, BackendService


def create_app(service=None):
    service = service or BackendService()
    app = FastAPI(title='Crypto Price Analyzer', version='0.1.0',
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
        headers = {'Retry-After': '1'} if error.status == 429 else None
        return JSONResponse(status_code=error.status, content=body, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        # Pydantic's default body includes rejected input; don't echo private values.
        return JSONResponse(status_code=422, content={'error': {
            'code': 'invalid_request', 'message': 'Request fields do not match the documented schema.'}})

    errors = {status: {'model': ErrorResponse} for status in (422, 429, 500, 502, 503)}

    @app.get('/health', response_model=HealthResponse)
    async def health():
        return {'status': 'ok'}

    @app.get('/v1/prices', response_model=PricesResponse, responses=errors)
    def prices():
        return service.prices()

    @app.get('/v1/analysis/{coin_id}', response_model=Evidence, responses=errors)
    def evidence(coin_id: Annotated[str, Path(min_length=1, max_length=100, pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$')],
                 days: Annotated[int, Query(ge=35, le=365)] = 90):
        return service.evidence(coin_id, days)

    @app.post('/v1/backtests', response_model=BacktestResponse, responses=errors)
    def backtest(body: BacktestRequest):
        return service.backtest(body.coin_id, body.days, body.strategy)

    @app.post('/v1/recommendations', response_model=RecommendationResponse, responses=errors)
    def recommendation(body: RecommendationRequest):
        position = None if body.selected_position is None else body.selected_position.model_dump()
        return service.recommend(body.coin_id, body.days, position)

    return app
