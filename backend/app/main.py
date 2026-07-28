"""
Point d’entrée de l’application cible (modular monolith).
"""

import os
import traceback

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from postgrest.exceptions import APIError

from app.api.router import router as api_router
from app.core.supabase_resilience import is_transient_supabase_error
from app.core.lifecycle import lifespan
from app.core.logging import configure_logging, get_logger
from app.core.settings import ALLOWED_ORIGINS_EXTRA, check_environment_consistency
from app.modules.planning.api.router import router as planning_router
from app.modules.signatures.api.router import router as signatures_router
from app.modules.teams.api.router import router as teams_router

configure_logging()
logger = get_logger(__name__)

# Refuse de démarrer un environnement de test sans redirection e-mail : sans
# elle, de vrais salariés recevraient les envois d'un environnement contenant
# les données réelles.
# Cf. docs/superpowers/specs/2026-07-28-environnement-test-donnees-reelles-design.md §7.3
check_environment_consistency()

app = FastAPI(
    lifespan=lifespan,
    title="EYWAI SIRH API",
    description="""
## API REST EYWAI

API complète pour l'intégration du SIRH EYWAI
dans votre Système d'Information.

### Authentification
Toutes les routes nécessitent un token JWT Bearer :
`Authorization: Bearer {token}`

### Multi-entreprises
Spécifier l'entreprise active :
`X-Active-Company: {company_id}`

### Connecteurs BI
Pour Power BI, Tableau et Metabase :
- Endpoint analytics : `GET /api/dashboard/analytics`
- Endpoint exports : `POST /api/exports/generate`
- Données temps réel : `GET /api/dashboard/all`

### Webhooks
Abonnez-vous aux événements métier via
`POST /api/webhooks`

Événements disponibles :
- employee.hired, employee.left, employee.salary_updated
- payslip.validated, absence.approved
- document.signed, recruitment.hired
    """,
    version="1.0.0",
    contact={
        "name": "EYWAI Support",
        "email": "support@eywai.fr",
    },
)

ALLOWED_ORIGINS = [
    "http://localhost:8080",
    "http://localhost:5173",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:5173",
    "https://sirh-frontend-app-505040845625.europe-west1.run.app",
    "https://sirh-frontend-505040845625.europe-west1.run.app",
    # Origines supplémentaires (frontend de test) — vide en production.
    *ALLOWED_ORIGINS_EXTRA,
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


@app.exception_handler(APIError)
async def postgrest_exception_handler(request: Request, exc: APIError):
    """Erreurs Supabase/PostgREST : message lisible + réponse JSON (headers CORS conservés)."""
    code = exc.code
    message = str(exc.message or exc)

    if code == "PGRST205" and any(
        t in message
        for t in (
            "employee_time_entries",
            "employee_time_entries_validations",
            "employee_badge_credentials",
        )
    ):
        detail = (
            "Tables badgeuse absentes sur Supabase. "
            "Appliquez la migration supabase/migrations/20260525120000_badgeuse_qr.sql "
            "(SQL Editor ou script backend/scripts/check_badgeuse_schema.py)."
        )
        return JSONResponse(
            status_code=503,
            content={"detail": detail},
        )

    if code == "PGRST204" and any(
        c in message
        for c in ("nom_signataire_rh", "qualite_signataire_rh")
    ):
        detail = (
            "Colonnes signataire RH absentes sur Supabase. "
            "Appliquez la migration supabase/migrations/20260604120000_company_signatory.sql "
            "(SQL Editor ou script backend/scripts/check_companies_schema.py)."
        )
        return JSONResponse(
            status_code=503,
            content={"detail": detail},
        )

    logger.error(
        "PostgREST error on %s %s: %s",
        request.method,
        request.url.path,
        exc.json() if hasattr(exc, "json") else exc,
    )
    return JSONResponse(
        status_code=502,
        content={"detail": "Erreur base de données"},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None) or {},
    )


@app.exception_handler(httpx.HTTPError)
async def httpx_exception_handler(request: Request, exc: httpx.HTTPError):
    if is_transient_supabase_error(exc):
        logger.warning(
            "Erreur réseau transitoire Supabase on %s %s: %s",
            request.method,
            request.url.path,
            exc,
        )
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "Connexion à la base temporairement indisponible. "
                    "Réessayez dans quelques secondes."
                )
            },
        )
    logger.error(
        "HTTP error on %s %s: %s", request.method, request.url.path, exc
    )
    return JSONResponse(
        status_code=502,
        content={"detail": "Erreur de communication avec la base de données"},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all : garantit une réponse JSON propre (avec headers CORS) même sur erreur 500."""
    if is_transient_supabase_error(exc):
        logger.warning(
            "Erreur réseau transitoire on %s %s: %s",
            request.method,
            request.url.path,
            exc,
        )
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "Connexion à la base temporairement indisponible. "
                    "Réessayez dans quelques secondes."
                )
            },
        )

    logger.error(
        "Unhandled exception on %s %s: %s", request.method, request.url.path, exc
    )

    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )


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
app.include_router(planning_router)
app.include_router(signatures_router)
app.include_router(teams_router)


@app.get("/health")
def healthcheck():
    """Healthcheck pour vérifier que l'API est en ligne."""
    return {"status": "ok"}
