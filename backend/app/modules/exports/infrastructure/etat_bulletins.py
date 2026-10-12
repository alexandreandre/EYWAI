"""Lecture de l'état des bulletins d'un mois, pour l'aperçu d'un export (lecture seule)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
from typing import Any, List, Optional, Tuple

from app.core.database import supabase
from app.core.logging import get_logger

logger = get_logger(__name__)

#: Temps laissé à la vérification « à recalculer » : l'aperçu ne doit pas attendre
#: des dizaines de secondes sur une grosse société. Le reste est annoncé non vérifié.
BUDGET_SECONDES = 15.0

#: Lectures simultanées de l'état des bulletins.
NB_LECTURES_PARALLELES = 8


def _bulletins_du_mois(
    company_id: str, year: int, month: int, employee_ids: Optional[List[str]]
) -> List[dict[str, Any]]:
    for colonnes in ("employee_id, status, origine", "employee_id, status"):
        try:
            requete = (
                supabase.table("payslips")
                .select(colonnes)
                .eq("company_id", company_id)
                .eq("year", year)
                .eq("month", month)
            )
            if employee_ids:
                requete = requete.in_("employee_id", employee_ids)
            return list(requete.execute().data or [])
        except Exception:  # noqa: BLE001 — colonne `origine` absente : on relit sans elle
            if "origine" not in colonnes:
                raise
    return []


def lire_etat_bulletins(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    budget_secondes: float = BUDGET_SECONDES,
) -> Tuple[int, int, int]:
    """(non validés, à recalculer, non vérifiés) parmi les bulletins du mois.

    « À recalculer » suit la règle de l'écran des bulletins (empreinte des
    entrées, cascade des mois d'avant). Un bulletin repris n'est jamais à
    recalculer. Passé le budget de temps, les bulletins restants sont comptés
    « non vérifiés » plutôt que supposés à jour.
    """
    from app.modules.payroll.application import empreinte_entrees_service

    year, month = map(int, period.split("-"))
    bulletins = _bulletins_du_mois(company_id, year, month, employee_ids)
    non_valides = sum(1 for b in bulletins if b.get("status") != "valide")
    a_calculer = [
        str(b["employee_id"])
        for b in bulletins
        if str(b.get("origine") or "calcule") != "importe"
    ]

    def etat_de(employee_id: str) -> bool | None:
        etat = empreinte_entrees_service.etat_dans_la_chaine(employee_id, year, month)
        return None if etat is None else etat.a_recalculer

    # Chaque salarié coûte une dizaine de lectures : en parallèle, et sous un
    # plafond de temps, le reste est annoncé « non vérifié » plutôt que supposé à jour.
    a_recalculer = 0
    non_verifies = 0
    pool = ThreadPoolExecutor(max_workers=NB_LECTURES_PARALLELES)
    try:
        futures = [pool.submit(etat_de, employee_id) for employee_id in a_calculer]
        faits, _ = wait(futures, timeout=budget_secondes)
        for future in futures:
            if future not in faits:
                non_verifies += 1
                continue
            try:
                if future.result() is True:
                    a_recalculer += 1
            except Exception:  # noqa: BLE001 — un salarié illisible n'empêche pas l'aperçu
                logger.warning("État « à recalculer » illisible pour un bulletin", exc_info=True)
                non_verifies += 1
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return non_valides, a_recalculer, non_verifies
