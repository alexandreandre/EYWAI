"""Ce qu'un bulletin écrit hors de lui-même, et comment le défaire.

Générer un bulletin ne fait pas que l'enregistrer : il retient l'échéance d'un
prêt, rembourse une avance ou un acompte, applique les dépôts et retraits CET
du mois, crédite au compte de modulation les heures sup qu'il ne paie pas.
Recalculer le bulletin sans défaire tout cela perdait l'échéance et l'avance,
payait de nouveau les heures déposées au CET et comptait deux fois les heures
créditées ; le supprimer ne rendait rien (audit du 04/10/2026).

Avant de recalculer, et quand on supprime, ces effets sont défaits ; le
recalcul les refait une seule fois. Recalculer deux fois de suite laisse les
compteurs au même point.

Les prêts et avances se retrouvent par le bulletin (leurs lignes de retenue
portent son identifiant) ; le CET et la modulation par le salarié et le mois,
puisque seule la paie du mois les applique. Ce qui ne se défait pas proprement
— une retenue sur un prêt annulé ou suspendu depuis — est refusé avant toute
écriture, avec une phrase qui dit quoi faire.

Jamais en bac à sable : ces fonctions ne sont appelées que par la génération,
la correction et la suppression réelles.
"""

from __future__ import annotations

import logging

from app.core.database import supabase
from app.modules.payslips.application.dto import PayslipBadRequestError

logger = logging.getLogger(__name__)


class EffetsNonDefaisables(PayslipBadRequestError, ValueError):
    """Le bulletin a écrit quelque chose qu'on ne saurait pas défaire proprement.

    `ValueError` aussi : le chemin IJSS rend ses refus en 400 par ce biais.
    """


def _bulletin_du_mois(employee_id: str, year: int, month: int) -> str | None:
    lignes = (
        supabase.table("payslips")
        .select("id")
        .match({"employee_id": employee_id, "year": year, "month": month})
        .limit(1)
        .execute()
        .data
        or []
    )
    return str(lignes[0]["id"]) if lignes else None


def refuser_si_effets_non_defaisables(
    employee_id: str,
    year: int,
    month: int,
    *,
    payslip_id: str | None = None,
    verbe: str = "recalculer",
) -> None:
    """Lève `EffetsNonDefaisables` si le bulletin du mois ne peut pas être défait.

    À appeler avant toute écriture (variables d'une correction, archive,
    suppression). Sans bulletin, rien à refuser.
    """
    from app.modules.employee_loans.application.annulation import refus_de_defaire

    payslip_id = payslip_id or _bulletin_du_mois(employee_id, year, month)
    if not payslip_id:
        return
    refus = refus_de_defaire(payslip_id, verbe)
    if refus:
        raise EffetsNonDefaisables(refus)


def defaire_effets_du_bulletin(
    employee_id: str, year: int, month: int, *, payslip_id: str | None
) -> None:
    """Défait ce que le bulletin du mois a écrit hors de lui.

    `payslip_id` : le bulletin enregistré, ou None s'il n'y en a pas — le CET et
    la modulation du mois sont défaits quand même : appliqués par une génération
    interrompue, ils ne doivent pas être perdus au calcul suivant.
    """
    from app.modules.cet.application.payroll_hook import defaire_application_en_paie
    from app.modules.employee_loans.application.annulation import (
        defaire_retenues_du_bulletin,
    )
    from app.modules.modulation.application.payroll_hook import defaire_credits_de_paie
    from app.modules.saisies_avances.application.annulation import (
        defaire_remboursements_du_bulletin,
    )

    prets = avances = 0
    if payslip_id:
        prets = defaire_retenues_du_bulletin(payslip_id)
        avances = defaire_remboursements_du_bulletin(payslip_id)
    cet = defaire_application_en_paie(employee_id, year, month)
    modulation = defaire_credits_de_paie(employee_id, year, month)
    if prets or avances or cet or modulation:
        logger.info(
            "[effets] %s %02d/%d défait : %d retenue(s) de prêt, %d avance(s), "
            "%d mouvement(s) CET, %d crédit(s) de modulation.",
            employee_id,
            month,
            year,
            prets,
            avances,
            cet,
            modulation,
        )


def _periode_du_bulletin(payslip_id: str) -> tuple[str, int, int] | None:
    """(salarié, année, mois) du bulletin, None s'il n'existe plus."""
    r = (
        supabase.table("payslips")
        .select("employee_id, year, month")
        .eq("id", payslip_id)
        .maybe_single()
        .execute()
    )
    ligne = r.data if r and r.data else None
    if not ligne or not ligne.get("employee_id"):
        return None
    return str(ligne["employee_id"]), int(ligne["year"]), int(ligne["month"])


def defaire_avant_suppression(payslip_id: str) -> None:
    """Refuse ou défait, avant que le bulletin ne soit supprimé."""
    periode = _periode_du_bulletin(payslip_id)
    if not periode:
        return
    refuser_si_effets_non_defaisables(*periode, payslip_id=payslip_id, verbe="supprimer")
    defaire_effets_du_bulletin(*periode, payslip_id=payslip_id)
