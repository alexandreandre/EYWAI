"""
Centralisation des variables d'environnement.
Utilisé par app.core.config ; le legacy continue d'utiliser backend_api/core/config.py.
"""

import base64
import json
import os

from dotenv import load_dotenv

load_dotenv()

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# Clé service_role (optionnelle ; pour admin / opérations bypass RLS)
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# OpenRouter (clé API ; les modèles sont définis dans app.shared.infrastructure.ai.models)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


def _env_bool(name: str, default: bool = False) -> bool:
    """Lit une variable d'environnement booléenne (1/true/yes/on)."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# Net-entreprises / télétransmission DSN.
# Flag global d'activation de la couche API (envoi automatique). Désactivé par défaut :
# tant qu'il est à false, seul le mode « manuel » (dépôt manuel) est possible, quelle
# que soit la config par entreprise. Empêche tout appel réseau tant que rien n'est branché.
NET_ENTREPRISES_ENABLED = _env_bool("NET_ENTREPRISES_ENABLED", False)

# Intégration comptable API (Cegid Loop, etc.). Désactivé par défaut.
ACCOUNTING_API_ENABLED = _env_bool("ACCOUNTING_API_ENABLED", False)

# Cegid Loop API (Quadra) — host public documenté ; surchargeable par entreprise.
# https://developers.cegid.com/docreference/BusinessUnits/Loop-Api-Management-Docs/
CEGID_LOOP_API_BASE_URL = os.getenv(
    "CEGID_LOOP_API_BASE_URL",
    "https://loop-publicapi.cegid.com",
).rstrip("/")
CEGID_LOOP_API_BASE_URL_TEST = os.getenv(
    "CEGID_LOOP_API_BASE_URL_TEST",
    "https://loop-publicapi.cegid.com",
).rstrip("/")

# SMTP / e-mails transactionnels (repli si config plateforme inactive ou absente).
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_SECURITY = os.getenv("SMTP_SECURITY", "starttls").strip().lower()
FROM_EMAIL = os.getenv("FROM_EMAIL")
FROM_NAME = os.getenv("FROM_NAME", "SIRH - Système de Gestion RH")
REPLY_TO = os.getenv("REPLY_TO")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8080")

_support_raw = os.getenv("SUPPORT_RECIPIENTS", "contact@eywai.fr")
SUPPORT_RECIPIENTS = tuple(
    e.strip() for e in _support_raw.split(",") if e.strip()
) or ("contact@eywai.fr",)

# Redirection temporaire des e-mails « nouveau bulletin » (vide = envoi au salarié).
PAYSLIP_EMAIL_REDIRECT = os.getenv("PAYSLIP_EMAIL_REDIRECT", "").strip() or None

# --- Environnement d'exécution -------------------------------------------------
# "prod" (défaut) ou "test". Pilote les garde-fous de l'environnement de test :
# redirection e-mail, blocage signature électronique et dépôt DSN.
APP_ENV = os.getenv("APP_ENV", "prod").strip().lower() or "prod"

# Redirection forcée de TOUS les e-mails sortants, quel que soit leur type.
# Distincte de PAYSLIP_EMAIL_REDIRECT, qui ne couvre que les bulletins et reste
# un filet de production pendant la collecte des adresses manquantes.
EMAIL_FORCE_REDIRECT_TO = os.getenv("EMAIL_FORCE_REDIRECT_TO", "").strip() or None


def is_test_environment() -> bool:
    """True si le service tourne dans l'environnement de test."""
    return APP_ENV == "test"


def check_environment_consistency() -> None:
    """
    Refuse de démarrer un environnement de test sans redirection e-mail.

    Sans cette garde, une variable oubliée suffirait à faire partir de vrais
    e-mails vers de vrais salariés depuis un environnement contenant les
    données réelles. Ici, soit la redirection est active, soit le service ne
    démarre pas.
    """
    if is_test_environment() and not EMAIL_FORCE_REDIRECT_TO:
        raise RuntimeError(
            "APP_ENV=test sans EMAIL_FORCE_REDIRECT_TO : refus de démarrer. "
            "Configurez l'adresse de redirection des e-mails de test."
        )


def parse_extra_origins(raw: str | None) -> list[str]:
    """Découpe une liste d'origines CORS séparées par des virgules."""
    if not raw:
        return []
    return [o.strip() for o in raw.split(",") if o.strip()]


# Origines CORS supplémentaires (frontend de test, etc.). Vide en production.
ALLOWED_ORIGINS_EXTRA = parse_extra_origins(os.getenv("ALLOWED_ORIGINS_EXTRA"))


def require_supabase_env() -> tuple[str, str]:
    """Retourne (SUPABASE_URL, SUPABASE_KEY) ou lève RuntimeError si manquants."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Variables d'environnement SUPABASE manquantes.")
    return SUPABASE_URL, SUPABASE_KEY


def _jwt_role(supabase_jwt: str) -> str | None:
    """Lit le champ 'role' du JWT Supabase (sans vérification cryptographique)."""
    try:
        parts = supabase_jwt.split(".")
        if len(parts) < 2:
            return None
        payload_b64 = parts[1]
        pad = "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + pad))
        r = payload.get("role")
        return str(r) if r is not None else None
    except Exception:
        return None


def get_supabase_admin_env() -> tuple[str, str]:
    """
    Retourne (url, key) pour un client Supabase admin (service_role).

    Choix de la clé : préfère une JWT dont le rôle est ``service_role`` parmi
    SUPABASE_SERVICE_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_KEY (certains .env
    utilisent SUPABASE_KEY pour la service_role et une autre variable pour anon).
    """
    url = SUPABASE_URL
    if not url:
        raise RuntimeError("Variable d'environnement SUPABASE_URL manquante.")

    candidates = [
        k for k in (SUPABASE_SERVICE_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_KEY) if k
    ]
    for key in candidates:
        if _jwt_role(key) == "service_role":
            return url, key

    key = SUPABASE_SERVICE_KEY or SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY
    if not key:
        raise RuntimeError(
            "Variables d'environnement Supabase manquantes pour le client admin "
            "(SUPABASE_SERVICE_KEY / SUPABASE_SERVICE_ROLE_KEY / SUPABASE_KEY)."
        )
    return url, key


def get_supabase_anon_env() -> tuple[str, str]:
    """
    Retourne (url, key) pour un client Supabase anonyme (auth publique :
    sign_in, refresh). Préfère la JWT dont le rôle est ``anon`` parmi
    SUPABASE_KEY, SUPABASE_SERVICE_KEY, SUPABASE_SERVICE_ROLE_KEY — les
    noms de variables ont été historiquement inversés, seul le claim fait foi.
    """
    if not SUPABASE_URL:
        raise RuntimeError("Variable d'environnement SUPABASE_URL manquante.")
    candidates = [
        k for k in (SUPABASE_KEY, SUPABASE_SERVICE_KEY, SUPABASE_SERVICE_ROLE_KEY) if k
    ]
    for key in candidates:
        if _jwt_role(key) == "anon":
            return SUPABASE_URL, key
    if not SUPABASE_KEY:
        raise RuntimeError("Variable d'environnement SUPABASE_KEY manquante.")
    return SUPABASE_URL, SUPABASE_KEY
