"""
DTOs applicatifs du module promotions.

Pour l’instant les schémas Pydantic (PromotionCreate, PromotionUpdate, PromotionRead, etc.)
servent de DTOs entre API et application. Aucun objet de transfert interne supplémentaire
n’est requis ; la logique applicative utilise directement ces schémas.
Si besoin futur : créer des classes dédiées (ex. CreatePromotionInput) pour découpler
les contrats API des modèles internes.
"""

from __future__ import annotations

# Pas de DTO dédié pour l’instant ; les schemas du module font office de DTOs.

__all__: list[str] = []
