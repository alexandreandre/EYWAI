"""Préavis : exécuté, ou non exécuté avec ou sans indemnité compensatrice.

Code du travail, art. L1234-5 (Légifrance, version en vigueur depuis le
01/05/2008, ouvert le 11/10/2026) : « Lorsque le salarié n'exécute pas le
préavis, il a droit, sauf s'il a commis une faute grave, à une indemnité
compensatrice. L'inexécution du préavis, notamment en cas de dispense par
l'employeur, n'entraîne aucune diminution des salaires et avantages que le
salarié aurait perçus s'il avait accompli son travail jusqu'à l'expiration du
préavis, indemnité de congés payés comprise. »

service-public.gouv.fr F2883, « Démission d'un salarié » (vérifié le
08/07/2026, ouvert le 11/10/2026) : dispense « À sa demande et après
acceptation de l'employeur […] l'indemnité compensatrice de préavis n'est pas
due. Ou à la seule initiative de l'employeur. Celui-ci doit néanmoins verser
l'indemnité compensatrice de préavis. »

Une valeur par cas (colonne `employee_exits.notice_indemnity_type`), lue de la
même façon par l'écran, le calcul et les documents de sortie :
- « executed » : préavis exécuté, payé avec le salaire du mois ; aucune indemnité ;
- « paid » : dispense à l'initiative de l'employeur ; indemnité compensatrice
  (valeur historique, gardée : « payée » voulait dire « indemnité versée ») ;
- « waived » : dispense à la demande du salarié, acceptée ; rien n'est dû ;
- « not_applicable » : pas de préavis.

Congés du préavis non exécuté (dispense par l'employeur) : L1234-5 dit
« indemnité de congés payés comprise ». Les jours que le salarié aurait acquis
jusqu'à la fin théorique du préavis s'ajoutent à la période de référence où ils
tombent, et l'indemnité compensatrice de préavis entre dans la rémunération
brute de cette période, l'assiette du dixième (L3141-24, I : « la rémunération
brute totale perçue par le salarié au cours de la période de référence »).

Module pur : aucune lecture, aucune écriture.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any, Iterable, List, Optional, Sequence

PREAVIS_EXECUTE = "executed"
DISPENSE_PAR_L_EMPLOYEUR = "paid"
DISPENSE_A_LA_DEMANDE_DU_SALARIE = "waived"
SANS_PREAVIS = "not_applicable"

TYPES_DE_PREAVIS = (
    PREAVIS_EXECUTE,
    DISPENSE_PAR_L_EMPLOYEUR,
    DISPENSE_A_LA_DEMANDE_DU_SALARIE,
    SANS_PREAVIS,
)

#: Un mois de préavis compte 30 jours, comme la durée proposée à l'écran
#: (employee_exits.domain.notice_period.MONTH_CALENDAR_DAYS).
JOURS_PAR_MOIS = 30

_PHRASES = {
    PREAVIS_EXECUTE: "Préavis exécuté, payé avec le salaire.",
    DISPENSE_PAR_L_EMPLOYEUR: (
        "Préavis non exécuté, dispense à l'initiative de l'employeur : "
        "indemnité compensatrice de préavis versée."
    ),
    DISPENSE_A_LA_DEMANDE_DU_SALARIE: (
        "Préavis non exécuté à la demande du salarié, dispense acceptée : "
        "pas d'indemnité compensatrice."
    ),
}


def indemnite_compensatrice_due(type_preavis: Optional[str], *, faute_grave: bool = False) -> bool:
    """Seule la dispense à l'initiative de l'employeur ouvre l'indemnité (L1234-5)."""
    return type_preavis == DISPENSE_PAR_L_EMPLOYEUR and not faute_grave


def phrase_execution_preavis(type_preavis: Optional[str]) -> str:
    """La phrase que portent le reçu, le certificat et l'attestation France Travail."""
    return _PHRASES.get(str(type_preavis or ""), "Aucun préavis applicable.")


def jours_de_preavis_restants(
    *,
    jours_de_preavis: int,
    fin_du_preavis: Optional[date],
    dernier_jour_travaille: Optional[date],
) -> int:
    """Le temps de préavis que le salarié ne fait pas : du lendemain du dernier
    jour travaillé à la fin du préavis, jamais plus que la durée du préavis.
    Sans date de fin connue, toute la durée."""
    jours = max(0, int(jours_de_preavis or 0))
    if fin_du_preavis is None or dernier_jour_travaille is None:
        return jours
    return max(0, min(jours, (fin_du_preavis - dernier_jour_travaille).days))


@dataclass(frozen=True)
class CongesDuPreavis:
    """Les congés acquis pendant une part du préavis non exécuté.

    `libelle` : None pour la période de référence en cours au dernier jour
    travaillé, sinon la période suivante (« 2027-2028 »)."""

    libelle: Optional[str]
    jours: float
    brut: float

    def en_dict(self) -> dict:
        return asdict(self)


def _fin_de_la_periode(jour: date, mois_debut_periode: int) -> date:
    """Le dernier jour de la période de référence qui contient `jour`."""
    debut_suivante = date(
        jour.year + 1 if jour.month >= mois_debut_periode else jour.year, mois_debut_periode, 1
    )
    return debut_suivante - timedelta(days=1)


def conges_du_preavis_non_execute(
    *,
    dernier_jour_travaille: date,
    fin_du_preavis: date,
    indemnite: float,
    acquisition_par_mois: float,
    mois_debut_periode: int,
) -> List[CongesDuPreavis]:
    """Jours de congés acquis du lendemain du dernier jour travaillé à la fin
    théorique du préavis, au rythme de la société par mois de 30 jours (le mois
    du préavis, `JOURS_PAR_MOIS`), et la part de l'indemnité compensatrice de
    chaque période de référence."""
    total = (fin_du_preavis - dernier_jour_travaille).days
    if total <= 0 or acquisition_par_mois <= 0:
        return []
    fin_periode = _fin_de_la_periode(dernier_jour_travaille, mois_debut_periode)
    jours_en_cours = min(total, max(0, (fin_periode - dernier_jour_travaille).days))
    morceaux = [(None, jours_en_cours), (None, total - jours_en_cours)]
    debut_suivante = fin_periode + timedelta(days=1)
    fin_suivante = _fin_de_la_periode(debut_suivante, mois_debut_periode)
    libelle_suivante = (
        f"{debut_suivante.year}-{fin_suivante.year}"
        if fin_suivante.year != debut_suivante.year
        else str(debut_suivante.year)
    )
    parts: List[CongesDuPreavis] = []
    brut_restant = round(float(indemnite or 0.0), 2)
    for rang, (_libelle, jours) in enumerate(morceaux):
        if jours <= 0:
            continue
        dernier = rang == len(morceaux) - 1 or morceaux[rang + 1][1] <= 0
        brut = brut_restant if dernier else round(float(indemnite or 0.0) * jours / total, 2)
        brut_restant = round(brut_restant - brut, 2)
        parts.append(
            CongesDuPreavis(
                libelle=None if rang == 0 else libelle_suivante,
                jours=round(acquisition_par_mois * jours / JOURS_PAR_MOIS, 2),
                brut=brut,
            )
        )
    return parts


def _part(valeur: Any) -> Optional[CongesDuPreavis]:
    if isinstance(valeur, CongesDuPreavis):
        return valeur
    if isinstance(valeur, dict):
        try:
            return CongesDuPreavis(
                libelle=valeur.get("libelle"),
                jours=float(valeur.get("jours") or 0.0),
                brut=float(valeur.get("brut") or 0.0),
            )
        except (TypeError, ValueError):
            return None
    return None


def conges_du_preavis_du_dossier(dossier: Any) -> List[CongesDuPreavis]:
    """Les congés du préavis non exécuté que porte le dossier de départ
    (préavis dispensé par l'employeur, délai de prévenance non respecté)."""
    if not isinstance(dossier, dict):
        return []
    parts: List[CongesDuPreavis] = []
    for cle in ("indemnite_preavis", "indemnite_delai_prevenance"):
        bloc = dossier.get(cle)
        if not isinstance(bloc, dict) or float(bloc.get("montant") or 0) <= 0:
            continue
        for valeur in bloc.get("conges_du_preavis") or []:
            part = _part(valeur)
            if part is not None and part.jours > 0:
                parts.append(part)
    return parts


def ajouter_les_conges_du_preavis(periodes: Sequence[Any], parts: Iterable[Any]) -> list:
    """Les périodes de congés de la sortie, augmentées des congés du préavis :
    jours aux droits et aux restants, indemnité au brut de la période. La part
    de la période en cours va à la dernière période ; celle de la période
    suivante en crée une."""
    from app.modules.payroll.engine.iccp_fin_contrat import PeriodeConges

    resultat = list(periodes)
    for valeur in parts:
        part = _part(valeur)
        if part is None or part.jours <= 0:
            continue
        if part.libelle is None and resultat:
            p = resultat[-1]
            resultat[-1] = PeriodeConges(
                libelle=p.libelle,
                brut=None if p.brut is None else round(float(p.brut) + part.brut, 2),
                droits=round(float(p.droits or 0.0) + part.jours, 2),
                restants=round(float(p.restants or 0.0) + part.jours, 2),
            )
        else:
            resultat.append(
                PeriodeConges(
                    libelle=part.libelle or "période suivante",
                    brut=round(part.brut, 2),
                    droits=round(part.jours, 2),
                    restants=round(part.jours, 2),
                )
            )
    return resultat
