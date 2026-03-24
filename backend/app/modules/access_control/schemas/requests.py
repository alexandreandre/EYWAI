"""
Schémas d'entrée pour les endpoints du module access_control.

Les endpoints check-hierarchy et check-permission sont en GET avec query params
(target_role, company_id ; user_id, company_id, permission_code). Aucun body requis,
donc pas de schémas request à migrer. Ce fichier reste un placeholder pour d'éventuels
futurs endpoints (ex. bulk check).
"""
from __future__ import annotations
