"""
Point d'entrée de l'application cible (modular monolith).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router as api_router

app = FastAPI(title="API SIRH (modular)", version="0.1.0")

ALLOWED_ORIGINS = [
    "http://localhost:8080",
    "http://localhost:5173",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:5173",
    "https://sirh-frontend-app-505040845625.europe-west1.run.app",
    "https://sirh-frontend-505040845625.europe-west1.run.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
