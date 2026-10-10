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

# Logging (voir app/core/logging.py)
ENV_LOG_LEVEL = "LOG_LEVEL"
ENV_APP_DEBUG = "APP_DEBUG"
ENV_PAYROLL_DEBUG = "PAYROLL_DEBUG"

# En-têtes de réponse lus par le frontend : exposés par le CORS (app/main.py),
# sans quoi le navigateur les masque à un écran servi depuis une autre origine.
#: Suppression sans objet (la ressource n'existait plus) : une 204 n'a pas de corps.
HEADER_DEJA_SUPPRIME = "X-Deja-Supprime"
EXPOSED_HEADERS = [HEADER_DEJA_SUPPRIME]

# Journal d'audit : action posée à la suppression d'un bulletin (année et mois
# dans `details`). Relue par l'écran des exports : un export dont un bulletin
# du mois a été supprimé depuis est « à refaire ».
AUDIT_BULLETIN_SUPPRIME = "payslip.delete"

#: Ce que voit la gestionnaire quand la génération d'un bulletin échoue sur une
#: erreur interne : le détail technique reste dans les journaux du serveur.
MESSAGE_ERREUR_GENERATION = (
    "Le bulletin n'a pas pu être généré à cause d'une erreur interne de Martine. "
    "Réessayez dans un instant ; si l'erreur revient, signalez-la au support en "
    "indiquant le salarié et le mois."
)

#: Même principe pour toute autre route (suppression, validation, historique,
#: édition, catalogue de primes…) : jamais le texte de l'exception à l'écran.
MESSAGE_ERREUR_INTERNE = (
    "L'opération n'a pas abouti à cause d'une erreur interne de Martine. "
    "Réessayez dans un instant ; si l'erreur revient, signalez-la au support en "
    "indiquant ce que vous faisiez (salarié, mois)."
)
