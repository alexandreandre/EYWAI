"""Ce qui, dans la génération, dépend du contrat du bulletin [D3].

Un mois où un contrat finit et un autre commence a deux bulletins. Celui du
contrat rangé (`contract_period_id` rempli) ne lit que ses variables et porte
un nom de PDF à lui ; il n'écrit rien dans le planning du mois, dont les cumuls
sont ceux du contrat qui continue.
"""

from __future__ import annotations

from typing import Any

from app.shared.cle_du_bulletin import du_contrat


def variables_du_bulletin(
    client: Any, employee_id: str, year: int, month: int, contract_period_id: str | None
) -> Any:
    """Les variables du mois qui appartiennent au bulletin de ce contrat (réponse Supabase)."""
    requete = (
        client.table("monthly_inputs")
        .select("*")
        .match({"employee_id": employee_id, "year": year, "month": month})
    )
    return du_contrat(requete, contract_period_id).execute()


def suffixe_du_pdf(contract_period_id: str | None) -> str:
    """Deux bulletins du même mois ne portent pas le même nom de fichier."""
    return "_contrat-precedent" if contract_period_id else ""
