import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .models import Instance, OptimizationResult, OptimizeRequest
from .solver_bridge import SolverRequestError, get_solver

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data' / 'results'
logger = logging.getLogger('uvicorn.error')
solver_lock = Lock()


def load_saved(instance: str) -> OptimizationResult:
    # instance is constrained by API model/enums, never a user-supplied file path.
    return OptimizationResult.model_validate_json((DATA / f'result_{instance}.json').read_text())


@asynccontextmanager
async def lifespan(_app):
    # Fail fast on corrupt assets or invalid integration configuration.
    for instance in ('sector_8', 'sector_12', 'sector_16'):
        load_saved(instance)
    get_solver()
    yield


app = FastAPI(title='Quantum Camera Placement API', version='1.0.0', lifespan=lifespan)
origins = [o.strip() for o in os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])


@app.get('/health')
def health():
    configured = get_solver() is not None
    return {'status': 'ok', 'solver_configured': configured, 'mode': 'live' if configured else 'saved-results'}


@app.get('/instances')
def instances():
    return {'instances': [{'id': f'sector_{n}', 'qubits': n, 'name': 'Midtown Manhattan (Bryant Park)'} for n in (8, 12, 16)]}


@app.get('/results/{instance}', response_model=OptimizationResult, response_model_exclude_unset=True)
def saved_result(instance: Instance):
    return load_saved(instance)


@app.post('/optimize', response_model=OptimizationResult, response_model_exclude_unset=True)
def optimize(request: OptimizeRequest):
    solver = get_solver()
    if solver is None:
        raise HTTPException(503, 'Live solver is not connected. Set SOLVER_CALLABLE in backend/.env; saved results remain available.')
    if not solver_lock.acquire(blocking=False):
        raise HTTPException(429, 'An optimization is already running. Please retry after it finishes.')
    try:
        bbox = request.bbox if request.bbox is not None else load_saved(request.instance).sector.bbox
        result = solver(instance=request.instance, bbox=list(bbox), p=request.p, lambda_=request.lambda_)
        if inspect_awaitable(result):
            raise TypeError('Solver returned an awaitable; use a synchronous adapter')
        # Preserve optional fields but reject invalid core results before the UI receives them.
        return OptimizationResult.model_validate(result)
    except SolverRequestError as exc:
        logger.warning('Solver rejected request: %s', exc)
        raise HTTPException(422, str(exc)) from None
    except (ValidationError, TypeError, ValueError):
        logger.exception('Solver returned an invalid result')
        raise HTTPException(502, 'Solver failed or returned an invalid result. See server logs.') from None
    except Exception:
        logger.exception('Optimization pipeline failed')
        raise HTTPException(500, 'Optimization pipeline failed. See server logs.') from None
    finally:
        solver_lock.release()


def inspect_awaitable(result):
    import inspect
    if inspect.isawaitable(result):
        if inspect.iscoroutine(result):
            result.close()
        return True
    return False


# Optional single-origin production/demo serving. Routes above take precedence.
# Set SERVE_FRONTEND=1 after `npm run build` in frontend/.
if os.getenv('SERVE_FRONTEND') == '1':
    dist = ROOT / 'frontend' / 'dist'
    if not dist.is_dir():
        raise RuntimeError('Build frontend/dist before setting SERVE_FRONTEND=1')
    app.mount('/', StaticFiles(directory=dist, html=True), name='frontend')
