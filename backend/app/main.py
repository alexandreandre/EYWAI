"""
Point d’entrée de l’application cible (modular monolith).
"""

import logging
import os
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import router as api_router

logger = logging.getLogger(__name__)

app = FastAPI(title="API SIRH (modular)", version="0.1.0")

ALLOWED_ORIGINS = [
    "http://localhost:8080",
    "http://localhost:5173",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:5173",
    "https://sirh-frontend-app-505040845625.europe-west1.run.app",
    "https://sirh-frontend-505040845625.europe-west1.run.app",
]

# localhost / 127.0.0.1 avec n’importe quel port (Vite, preview, etc.) — ne matche pas les domaines de prod.
_DEV_LOCAL_ORIGIN_REGEX = r"https?://(localhost|127\.0\.0\.1)(:\d+)?$"
_cors_origin_regex = os.getenv("CORS_ALLOW_ORIGIN_REGEX", _DEV_LOCAL_ORIGIN_REGEX)
if _cors_origin_regex.strip() == "":
    _cors_origin_regex = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=_cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all : garantit une réponse JSON propre (avec headers CORS) même sur erreur 500."""
    logger.error(
        "Unhandled exception on %s %s: %s", request.method, request.url.path, exc
    )
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )


# ---------------------------------------------------------------------------
# Lifecycle (startup / shutdown, à brancher plus tard)
# ---------------------------------------------------------------------------
# @app.on_event("startup")
# async def startup(): ...
# @app.on_event("shutdown")
# async def shutdown(): ...

# ---------------------------------------------------------------------------
# Error handlers (à brancher plus tard)
# ---------------------------------------------------------------------------
# @app.exception_handler(HTTPException)
# async def http_exception_handler(request, exc): ...
# @app.exception_handler(RequestValidationError)
# async def validation_exception_handler(request, exc): ...

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
app.include_router(api_router)


@app.get("/health")
def healthcheck():
    """Healthcheck pour vérifier que l'API est en ligne."""
    return {"status": "ok"}
