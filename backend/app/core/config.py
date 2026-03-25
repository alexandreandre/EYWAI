"""
Configuration de l'app cible (app/) : Supabase, chemins.
Comportement aligné sur l'ancien core.config ; les imports legacy restent sur backend_api/core/config.py.
Clients Supabase et chemins moteur de paie sont centralisés dans app.core.database et app.core.paths.
"""

from pathlib import Path


# Réexport pour les usages qui font "from app.core.config import ..."
# (et pour le wrapper backend_api/core/config.py)

# --- Chemins (config garde CORE_DIR / API_DIR pour compat) ---
_CURRENT_FILE = Path(__file__).resolve()
CORE_DIR = _CURRENT_FILE.parent
API_DIR = _CURRENT_FILE.parent.parent.parent
