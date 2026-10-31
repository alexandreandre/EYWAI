"""La clé d'un bulletin : (société, salarié, année, mois, contrat) [D3].

Un mois où un contrat finit et un autre commence a deux bulletins, un par
contrat. Le contrat est nul pour celui de la fiche, c'est-à-dire tous les
bulletins d'avant D3, et vaut le contrat rangé (`employee_contract_periods`)
pour le bulletin de l'ancien contrat dans ce mois partagé. Les variables du
mois portent la même clé.

Toute lecture « du bulletin du mois » passe par `du_contrat` : sans contrat,
elle rend le bulletin du contrat de la fiche, comme avant.
"""

from __future__ import annotations

from typing import Any

CONFLIT_BULLETIN = "company_id,employee_id,year,month,contract_period_id"


def du_contrat(requete: Any, contract_period_id: str | None) -> Any:
    """Restreint une lecture des bulletins ou des variables d'un mois au bulletin d'un contrat."""
    if contract_period_id:
        return requete.eq("contract_period_id", str(contract_period_id))
    return requete.is_("contract_period_id", "null")
