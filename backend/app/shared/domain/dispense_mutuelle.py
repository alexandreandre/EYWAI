"""Mutuelle absente ou dispensée : ce que la DSN en dit à la RH.

Un salarié peut refuser la mutuelle de l'entreprise dans les seuls cas de la loi.
Textes lus sur Légifrance le 05/11/2026, en vigueur ce jour-là (copie mot pour
mot : data/_sources/legifrance/2026-11-05-dispenses-mutuelle.md) :

- CSS D911-2 (LEGIARTI000038682723) : dispenses de droit, pour la santé
  seulement. 1° complémentaire santé solidaire (L861-3), « jusqu'à la date à
  laquelle les salariés cessent de bénéficier de cette couverture » ; 2°
  assurance individuelle en cours à l'embauche, « jusqu'à échéance du contrat
  individuel » ; 3° couverture « au titre d'un autre emploi », « y compris en
  tant qu'ayants droit ».
- CSS R242-1-6 (LEGIARTI000038701542) : dispenses « prévues dans l'acte
  juridique » de l'entreprise. 1° embauchés avant une décision unilatérale ; 2° a)
  CDD ou apprenti de 12 mois ou plus avec couverture individuelle ; b) CDD ou
  apprenti de moins de 12 mois ; c) temps partiel ou apprenti dont la cotisation
  atteindrait 10 % du brut ; f) couverture collective par ailleurs, « à condition
  de le justifier chaque année ».
- Les deux : « l'employeur doit être en mesure de produire la demande de
  dispense ». D'où la date de la demande signée, exigée sur la fiche.

C'est la RH qui pose la dispense (Modifier la fiche). Martine ne fait que dire ce
qui manque. La prévoyance d'un cadre ne se dispense jamais
(prevoyance_obligatoire.py) : ce module ne la regarde pas.
"""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any

#: Code -> libellé de l'écran (le même que frontend dispenseMutuelle.ts).
MOTIFS_DISPENSE: dict[str, str] = {
    "couverture_collective": "Couvert ailleurs par une mutuelle collective",
    "css": "Bénéficiaire de la complémentaire santé solidaire",
    "assurance_individuelle": "Assurance santé individuelle déjà en cours à l'embauche",
    "cdd_moins_12_mois": "CDD ou apprenti de moins de 12 mois",
    "cdd_12_mois_et_plus": "CDD ou apprenti de 12 mois ou plus, couvert à titre individuel",
    "temps_partiel_10_pourcent": "Temps partiel ou apprenti : cotisation d'au moins 10 % du brut",
    "anterieur_decision_unilaterale": "Embauché avant une mutuelle mise en place par décision unilatérale",
}

#: D911-2 1° et 2° : la dispense ne joue que jusqu'à une date.
MOTIFS_A_ECHEANCE = frozenset({"css", "assurance_individuelle"})
#: R242-1-6 2° f : « à condition de le justifier chaque année ».
MOTIF_JUSTIFIE_CHAQUE_ANNEE = "couverture_collective"
MOTIFS_CDD = frozenset({"cdd_moins_12_mois", "cdd_12_mois_et_plus"})

#: Le contrôle d'avant le 05/11/2026 ne regardait que ces contrats ; inchangé.
CONTRATS_CONTROLES = frozenset({"CDI", "CDD"})

_OU = "dans sa fiche (Modifier la fiche, Paie sociale)"


def _date(valeur: Any) -> date | None:
    if not isinstance(valeur, str):
        return None
    try:
        return date.fromisoformat(valeur[:10])
    except ValueError:
        return None


def _fr(jour: date) -> str:
    return jour.strftime("%d/%m/%Y")


def _un_an_apres(jour: date) -> date:
    try:
        return jour.replace(year=jour.year + 1)
    except ValueError:  # 29 février : un an après, c'est le 28
        return date(jour.year + 1, 2, 28)


def alerte_mutuelle(
    mutuelle: Any, contract_type: str | None, annee: int, mois: int
) -> str | None:
    """La phrase à montrer pour la mutuelle du mois, ou None s'il n'y a rien à faire.

    ``mutuelle`` est le bloc ``specificites_paie.mutuelle`` de la fiche du mois.
    La phrase dit toujours où aller et quoi faire.
    """
    if contract_type not in CONTRATS_CONTROLES:
        return None
    bloc = mutuelle if isinstance(mutuelle, dict) else {}
    if bloc.get("adhesion"):
        return None

    dispense = bloc.get("dispense")
    if not isinstance(dispense, dict):
        return (
            f"mutuelle absente. {_OU[0].upper()}{_OU[1:]}, choisissez sa formule ou, "
            "s'il ne veut pas adhérer, posez sa dispense."
        )

    motif = dispense.get("motif")
    demande = _date(dispense.get("demande_recue_le"))
    if motif not in MOTIFS_DISPENSE or demande is None:
        return (
            "dispense de mutuelle incomplète : indiquez le motif et la date de la "
            f"demande signée {_OU}."
        )

    if motif in MOTIFS_A_ECHEANCE:
        fin = _date(dispense.get("fin_le"))
        if fin is None:
            return f"dispense de mutuelle incomplète : indiquez la date de fin {_OU}."
        if fin < date(annee, mois, 1):
            return (
                f"dispense de mutuelle finie le {_fr(fin)} : choisissez sa formule "
                f"ou mettez la dispense à jour {_OU}."
            )

    if motif in MOTIFS_CDD and contract_type == "CDI":
        return f"dispense « CDD » sur un CDI : choisissez le bon motif ou sa formule {_OU}."

    if motif == MOTIF_JUSTIFIE_CHAQUE_ANNEE:
        justificatif = _date(dispense.get("justificatif_recu_le")) or demande
        dernier_jour = date(annee, mois, calendar.monthrange(annee, mois)[1])
        if _un_an_apres(justificatif) <= dernier_jour:
            return (
                "justificatif de sa mutuelle collective à redemander (le dernier date "
                f"du {_fr(justificatif)}, il se renouvelle chaque année). Une fois "
                f"reçu, mettez sa date {_OU}."
            )

    return None


__all__ = ["MOTIFS_DISPENSE", "alerte_mutuelle"]
