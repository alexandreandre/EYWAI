"""
Constantes transverses de l'application.

Noms d'environnement, libellés, valeurs par défaut partagés.
Aucune logique métier.
"""
from __future__ import annotations

# Identité de l'app (aligné sur app/main.py si besoin)
APP_NAME = "API SIRH (modular)"
API_VERSION = "0.1.0"

# Variables d'environnement (noms uniquement ; les valeurs sont dans settings)
ENV_SUPABASE_URL = "SUPABASE_URL"
ENV_SUPABASE_KEY = "SUPABASE_KEY"
ENV_SUPABASE_SERVICE_KEY = "SUPABASE_SERVICE_KEY"
ENV_SUPABASE_SERVICE_ROLE_KEY = "SUPABASE_SERVICE_ROLE_KEY"

# Logging
ENV_LOG_LEVEL = "LOG_LEVEL"
