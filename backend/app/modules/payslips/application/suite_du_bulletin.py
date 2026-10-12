"""Le mois suivant qui part des cumuls d'un bulletin qu'on vient de recalculer.

Le bulletin de M+1 part des cumuls de M (brut et heures de l'année pour la
réduction générale, tranches Agirc-Arrco, plafond des heures sup, base du
dixième). Recalculer M en change les cumuls : M+1, calculé sur les anciens,
ne suit plus. Il ne passait « À recalculer » qu'une fois M recalculé, et
« Recalculer tout ce qui a changé » demandait un clic par mois (relevé J.1 du
12/10/2026).

Après un recalcul réussi, on lit donc l'état du bulletin de M+1 avec la même
règle que la pastille « À recalculer » (empreinte des cumuls du mois d'avant,
posée à sa génération) :

- un brouillon qui en part est rendu à l'écran, qui le recalcule dans le même
  geste (et le suivant de proche en proche) ;
- un bulletin validé n'est jamais recalculé sans la RH : il est signalé ;
- rien n'est dit d'un bulletin repris de l'ancien logiciel, du premier mois
  d'un contrat (il ne part pas du mois d'avant), ni d'un bulletin calculé avant
  l'empreinte (on ne sait pas).

Jamais bloquant : le bulletin de M est déjà enregistré.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.database import supabase
from app.modules.payslips.infrastructure.payslip_list_meta import montants_du_bulletin

logger = logging.getLogger(__name__)

CODE_MOIS_SUIVANT_VALIDE = "mois_suivant_valide"


@dataclass(frozen=True)
class MoisSuivant:
    year: int
    month: int
    #: Validé : signalé, jamais recalculé en groupe.
    valide: bool
    #: Heures sup, brut et net d'avant : le message de fin compare avant → après.
    montants: dict[str, Any] = field(default_factory=dict)

    def en_reponse(self) -> dict[str, Any]:
        return {"year": self.year, "month": self.month, **self.montants}


def _mois_suivant(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if int(month) == 12 else (int(year), int(month) + 1)


def phrase_mois_suivant_valide(year: int, month: int) -> str:
    return (
        f"Le bulletin validé de {month:02d}/{year} part des cumuls de ce bulletin, qui "
        "viennent de changer : il n'a pas été recalculé. Ouvrez-le pour décider s'il "
        "faut le régénérer."
    )


def _lire_bulletin_du_mois(employee_id: str, year: int, month: int) -> dict[str, Any] | None:
    """Statut, origine et données du bulletin de ce mois, ou None."""
    for colonnes in ("year, month, status, origine, payslip_data", "year, month, status, payslip_data"):
        try:
            r = (
                supabase.table("payslips")
                .select(colonnes)
                .match({"employee_id": str(employee_id), "year": year, "month": month})
                .maybe_single()
                .execute()
            )
        except Exception:  # noqa: BLE001 — colonne `origine` absente : on relit sans
            if "origine" not in colonnes:
                raise
            continue
        return r.data if r and r.data else None
    return None


def _etat_du_mois(employee_id: str, year: int, month: int):
    from app.modules.payroll.application.empreinte_entrees_service import etat_dans_la_chaine

    return etat_dans_la_chaine(str(employee_id), year, month)


def mois_suivant_a_recalculer(employee_id: str, year: int, month: int) -> MoisSuivant | None:
    """Le bulletin de M+1 s'il part des cumuls de M et qu'ils ont changé depuis son calcul."""
    annee, mois = _mois_suivant(year, month)
    try:
        bulletin = _lire_bulletin_du_mois(employee_id, annee, mois)
        if not bulletin or str(bulletin.get("origine") or "calcule") == "importe":
            return None
        etat = _etat_du_mois(employee_id, annee, mois)
    except Exception:  # noqa: BLE001 — une aide, jamais un échec de la génération
        logger.warning(
            "Mois suivant de %s (%02d/%s) illisible : la suite n'est pas proposée.",
            employee_id,
            month,
            year,
            exc_info=True,
        )
        return None
    if etat is None or getattr(etat, "cumuls_precedents_changes", None) is not True:
        return None
    return MoisSuivant(
        year=annee,
        month=mois,
        valide=str(bulletin.get("status") or "") == "valide",
        montants=montants_du_bulletin(bulletin.get("payslip_data")),
    )
