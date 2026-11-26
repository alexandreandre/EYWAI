"""Lectures de l'activité partielle en masse : salariés de la société, bulletins figés."""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from app.core.database import supabase
from app.core.logging import get_logger

logger = get_logger(__name__)

_PAQUET = 40
_COLONNES_SALARIE = (
    "id, first_name, last_name, nom_usage, statut, is_forfait_jour, hire_date, "
    "contract_end_date, current_exit_id, employment_status, company_id"
)


def _paquets(ids: Sequence[str]) -> Iterable[list[str]]:
    uniques = list(dict.fromkeys(str(i) for i in ids if i))
    for i in range(0, len(uniques), _PAQUET):
        yield uniques[i : i + _PAQUET]


def salaries_de_la_societe(company_id: str, employee_ids: Sequence[str]) -> dict[str, dict[str, Any]]:
    """Les fiches demandées QUI appartiennent à la société ; les autres manquent."""
    out: dict[str, dict[str, Any]] = {}
    for paquet in _paquets(employee_ids):
        rows = (
            supabase.table("employees")
            .select(_COLONNES_SALARIE)
            .eq("company_id", company_id)
            .in_("id", paquet)
            .execute()
            .data
            or []
        )
        for row in rows:
            out[str(row["id"])] = row
    return out


def mois_figes(
    employee_ids: Sequence[str], mois: Sequence[tuple[int, int]]
) -> dict[str, set[tuple[int, int]]]:
    """Par salarié, les mois dont le bulletin (du contrat de la fiche) est validé
    ou repris de l'ancien logiciel : le calendrier n'y arriverait plus."""
    out: dict[str, set[tuple[int, int]]] = {}
    annees = sorted({a for a, _ in mois})
    voulus = set(mois)
    if not annees:
        return out
    for paquet in _paquets(employee_ids):
        rows = _bulletins(paquet, annees)
        for row in rows:
            cle = (int(row["year"]), int(row["month"]))
            if cle not in voulus:
                continue
            if str(row.get("status") or "") == "valide" or str(row.get("origine") or "") == "importe":
                out.setdefault(str(row["employee_id"]), set()).add(cle)
    return out


def _bulletins(employee_ids: list[str], annees: list[int]) -> list[dict[str, Any]]:
    # `origine` vient de la migration de reprise : sans elle, le statut seul
    # (même repli que `payslips.application.commands._fetch_payslip_status`).
    for colonnes in ("employee_id, year, month, status, origine", "employee_id, year, month, status"):
        try:
            return (
                supabase.table("payslips")
                .select(colonnes)
                .in_("employee_id", employee_ids)
                .in_("year", annees)
                .is_("contract_period_id", "null")
                .execute()
                .data
                or []
            )
        except Exception as exc:  # noqa: BLE001 — colonne absente : on réessaie sans
            if "origine" not in colonnes:
                raise
            logger.warning("Colonne payslips.origine illisible, statut seul : %s", exc)
    return []
