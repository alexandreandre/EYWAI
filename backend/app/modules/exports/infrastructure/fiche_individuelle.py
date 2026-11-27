"""Fiche individuelle d'un salarié : ses cumuls mois par mois (lot L18, 27/11/2026).

Utile pour l'indemnité de départ : les rubriques du bulletin en lignes, les mois
en colonnes, un total. Tout est lu sur les bulletins enregistrés
(`payslips.payslip_data`), regroupé par rubrique comme le journal de paie
(`journal_recapitulatif.lignes_du_bulletin`) ; rien n'est recalculé.

Un mois sans bulletin Martine reste vide et le dit (« mois non payé dans
Martine »), jamais en silence. Un bulletin non validé le dit (« brouillon, non
validé ») ; un bulletin repris de l'ancien logiciel à la bascule aussi.

Le salaire de référence de l'indemnité de départ (R1234-4 : moyenne des 12
derniers mois ou tiers des 3 derniers) applique la règle du calcul de sortie
(`payroll.engine.salaire_reference_sortie`, lu sans être modifié) aux bulletins
jusqu'au dernier mois de la période, ce mois compris. Le calcul de sortie, lui,
s'arrête avant le mois de la notification : les deux peuvent différer.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.modules.exports.infrastructure.journal_recapitulatif import (
    REMUNERATION,
    lignes_du_bulletin,
)
from app.modules.exports.infrastructure.payslip_accounting_extract import (
    extract_cotisations_from_payslip,
    extract_pas_amount,
)
from app.modules.payroll.engine.salaire_reference_sortie import (
    MoisDeSalaire,
    SalaireDeReference,
    calculer_salaire_de_reference,
    mois_de_salaire_du_bulletin,
)
from app.modules.payslips.infrastructure.payslip_list_meta import heures_sup_du_bulletin

Mois = Tuple[int, int]

MOIS_NON_PAYE = "mois non payé dans Martine"
MOIS_AVANT_ENTREE = "avant l'entrée"
MOIS_A_VENIR = "mois à venir"
MOIS_BROUILLON = "brouillon, non validé"
MOIS_REPRIS = "repris de l'ancien logiciel"
MOIS_PAYE = "payé"
#: Au-delà, le tableau devient illisible : trois ans au plus.
MOIS_MAXIMUM = 36

MOIS_COURTS = (
    "janv.", "févr.", "mars", "avr.", "mai", "juin",
    "juil.", "août", "sept.", "oct.", "nov.", "déc.",
)
MOIS_LONGS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)


def libelle_court(mois: Mois) -> str:
    return f"{MOIS_COURTS[mois[1] - 1]} {mois[0]}"


def libelle_long(mois: Mois) -> str:
    return f"{MOIS_LONGS[mois[1] - 1]} {mois[0]}"


def libelle_chiffre(mois: Mois) -> str:
    return f"{mois[1]:02d}/{mois[0]}"


def est_repris(bulletin: Dict[str, Any]) -> bool:
    """Repris de l'ancien logiciel à la bascule (`origine = importe`)."""
    donnees = bulletin.get("payslip_data") or {}
    return bulletin.get("origine") == "importe" or bool(isinstance(donnees, dict) and donnees.get("reprise"))


def est_brouillon(bulletin: Dict[str, Any]) -> bool:
    """Calculé par Martine et pas encore validé : ses montants peuvent changer."""
    return not est_repris(bulletin) and bulletin.get("status") != "valide"


def _nombre(valeur: Any) -> float:
    try:
        return float(valeur or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _date(valeur: Any) -> Optional[date]:
    if isinstance(valeur, date):
        return valeur
    try:
        return date.fromisoformat(str(valeur)[:10])
    except (TypeError, ValueError):
        return None


def _suivant(mois: Mois) -> Mois:
    return (mois[0], mois[1] + 1) if mois[1] < 12 else (mois[0] + 1, 1)


def mois_de_la_periode(debut: Mois, fin: Mois) -> List[Mois]:
    mois, courant = [], debut
    while courant <= fin:
        mois.append(courant)
        courant = _suivant(courant)
    return mois


def periode_par_defaut(aujourd_hui: date) -> Tuple[Mois, Mois]:
    """L'année civile en cours."""
    return (aujourd_hui.year, 1), (aujourd_hui.year, 12)


def _lire_mois(valeur: str) -> Mois:
    try:
        annee, numero = (int(x) for x in str(valeur).split("-"))
    except ValueError:
        raise ValueError(f"Mois illisible : « {valeur} » (attendu AAAA-MM).") from None
    if not 1 <= numero <= 12:
        raise ValueError(f"Mois illisible : « {valeur} » (attendu AAAA-MM).")
    return annee, numero


def lire_periode(debut: Optional[str], fin: Optional[str], aujourd_hui: date) -> Tuple[Mois, Mois]:
    """La période demandée (AAAA-MM), l'année civile en cours sinon."""
    defaut_debut, defaut_fin = periode_par_defaut(aujourd_hui)
    premier = _lire_mois(debut) if debut else defaut_debut
    dernier = _lire_mois(fin) if fin else (defaut_fin if not debut else (premier[0], 12))
    if premier > dernier:
        raise ValueError("Le premier mois de la période est après le dernier.")
    if len(mois_de_la_periode(premier, dernier)) > MOIS_MAXIMUM:
        raise ValueError(f"Période trop longue : {MOIS_MAXIMUM} mois au plus.")
    return premier, dernier


# --- Lecture d'un bulletin ---------------------------------------------------


def _reduction_generale(payslip_data: Dict[str, Any]) -> float:
    _, _, lignes, _ = extract_cotisations_from_payslip(payslip_data)
    total = 0.0
    for ligne in lignes:
        coti = str(ligne.get("coti_id") or "").lower()
        libelle = str(ligne.get("libelle") or "").lower()
        if coti.startswith("reduction_generale") or "réduction générale" in libelle:
            total += _nombre(ligne.get("montant_patronal"))
    return total


def _heures(valeur: float) -> str:
    return f"{valeur:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " h"


def _heures_de_base(payslip_data: Dict[str, Any]) -> Optional[float | str]:
    """Les heures de la ligne « Salaire de base » ; « forfait jours » au forfait ;
    les deux quand le mois mêle les deux."""
    heures, vu, forfait = 0.0, False, False
    for ligne in payslip_data.get("calcul_du_brut") or []:
        if not isinstance(ligne, dict):
            continue
        libelle = str(ligne.get("libelle") or "").strip().lower()
        if not libelle.startswith("salaire de base"):
            continue
        if "forfait" in libelle:
            forfait = True
        elif ligne.get("quantite") is not None:
            heures += _nombre(ligne.get("quantite"))
            vu = True
    if forfait:
        return f"{_heures(heures)} + forfait jours" if vu else "forfait jours"
    return round(heures, 2) if vu else None


#: Bulletins repris d'un autre logiciel : « Act. partiel. 250926 »,
#: « Absence maladie 220926-230926 ». La rubrique, sans la date collée.
_DATES_COLLEES = re.compile(r"\s+\d{6}(\s*-\s*\d{6})?$")


def _rubriques_du_brut(payslip_data: Dict[str, Any]) -> Iterable[Tuple[str, float]]:
    for section, libelle, _base, salarial, _patronal in lignes_du_bulletin(payslip_data):
        if section != REMUNERATION or not salarial:
            continue
        # Le sous-total du bulletin répète des lignes déjà comptées.
        if libelle.upper().startswith("SOUS-TOTAL"):
            continue
        yield _DATES_COLLEES.sub("", libelle).strip() or libelle, salarial


# --- La fiche ------------------------------------------------------------------

#: Lignes de synthèse, sous les rubriques du brut, dans l'ordre de la fiche.
SYNTHESE = (
    "SALAIRE BRUT",
    "Heures du salaire de base",
    "Heures supplémentaires",
    "Cotisations salariales",
    "Cotisations patronales",
    "dont réduction générale",
    "NET IMPOSABLE",
    "Prélèvement à la source",
    "NET A PAYER",
)


def _synthese(payslip_data: Dict[str, Any]) -> Dict[str, Any]:
    salariales, patronales, _, _ = extract_cotisations_from_payslip(payslip_data)
    synthese_net = payslip_data.get("synthese_net") or {}
    return {
        "SALAIRE BRUT": _nombre(payslip_data.get("salaire_brut")),
        "Heures du salaire de base": _heures_de_base(payslip_data),
        "Heures supplémentaires": heures_sup_du_bulletin(payslip_data),
        "Cotisations salariales": salariales,
        "Cotisations patronales": patronales,
        "dont réduction générale": _reduction_generale(payslip_data),
        "NET IMPOSABLE": _nombre(synthese_net.get("net_imposable") if isinstance(synthese_net, dict) else 0),
        "Prélèvement à la source": extract_pas_amount(synthese_net),
        "NET A PAYER": _nombre(payslip_data.get("net_a_payer")),
    }


def _parties(valeur: Any) -> Tuple[float, bool, bool]:
    """(heures, heures lues, forfait) d'une valeur de la ligne des heures."""
    if isinstance(valeur, (int, float)):
        return float(valeur), True, False
    texte = str(valeur)
    forfait = "forfait" in texte
    m = re.match(r"^([\d,]+) h", texte)
    return (float(m.group(1).replace(",", ".")), True, forfait) if m else (0.0, False, forfait)


def _ajouter(cumul: Dict[str, Any], libelle: str, valeur: Any) -> None:
    if valeur is None:
        return
    precedent = cumul.get(libelle)
    if isinstance(valeur, str) or isinstance(precedent, str):
        # Heures et forfait jours le même mois (deux bulletins) : les deux.
        h1, vu1, f1 = _parties(precedent) if precedent is not None else (0.0, False, False)
        h2, vu2, f2 = _parties(valeur)
        heures, vu, forfait = h1 + h2, vu1 or vu2, f1 or f2
        if forfait:
            cumul[libelle] = f"{_heures(heures)} + forfait jours" if vu else "forfait jours"
        else:
            cumul[libelle] = round(heures, 2)
        return
    cumul[libelle] = (precedent if isinstance(precedent, (int, float)) else 0.0) + float(valeur)


def _arrondi(valeur: Any) -> Any:
    return round(valeur, 2) if isinstance(valeur, float) else valeur


def _total(valeurs: Iterable[Any]) -> Optional[float]:
    nombres = [v for v in valeurs if isinstance(v, (int, float))]
    return round(sum(nombres), 2) if nombres else None


def _etat_du_mois(
    mois: Mois, bulletins: Sequence[Dict[str, Any]], entree: Optional[Mois], courant: Mois
) -> str:
    nombre = len(bulletins)
    if nombre:
        if any(est_brouillon(b) for b in bulletins):
            etat = MOIS_BROUILLON
        elif all(est_repris(b) for b in bulletins):
            etat = MOIS_REPRIS
        else:
            etat = MOIS_PAYE
        return f"{etat} ({nombre} bulletins)" if nombre > 1 else etat
    if entree and mois < entree:
        return MOIS_AVANT_ENTREE
    if mois > courant:
        return MOIS_A_VENIR
    return MOIS_NON_PAYE


def _salaire_habituel(employe: Dict[str, Any]) -> float:
    """Le salaire habituel du contrat, comme le calcul de sortie (sans bulletin)."""
    from app.modules.payroll.engine.calcul_indemnites_sortie import (
        _parse_salaire_base,
        _salaire_habituel_et_taux_horaire,
    )

    try:
        return _salaire_habituel_et_taux_horaire(employe, _parse_salaire_base(employe))[0]
    except (TypeError, ValueError):
        return 0.0


def _mois_de_salaire(bulletins: Sequence[Dict[str, Any]], fin: Mois) -> List[MoisDeSalaire]:
    """Un mois de salaire par mois civil (deux bulletins le même mois : additionnés)."""
    par_mois: Dict[Mois, List[MoisDeSalaire]] = defaultdict(list)
    for bulletin in bulletins:
        mois = (int(bulletin["year"]), int(bulletin["month"]))
        if mois <= fin:
            par_mois[mois].append(mois_de_salaire_du_bulletin(mois[0], mois[1], bulletin["payslip_data"]))
    return sorted(
        MoisDeSalaire(
            annee=mois[0],
            mois=mois[1],
            brut=round(sum(m.brut for m in liste), 2),
            primes_annuelles=round(sum(m.primes_annuelles for m in liste), 2),
            arret_maladie=any(m.arret_maladie for m in liste),
        )
        for mois, liste in par_mois.items()
    )


def _mois_retenus(mois: Sequence[MoisDeSalaire], reference: SalaireDeReference) -> List[Mois]:
    """Les mois sur lesquels la règle a calculé : les derniers, ou ceux d'avant l'arrêt."""
    from app.modules.payroll.engine.salaire_reference_sortie import _arret_le_plus_recent

    if reference.formule == "contrat" or not reference.mois_lus:
        return []
    tries = list(mois)
    if reference.arret:
        arret = _arret_le_plus_recent(tries[-12:])
        if arret is not None:
            debut = (arret[0].annee, arret[0].mois)
            tries = [m for m in tries if (m.annee, m.mois) < debut]
    return [(m.annee, m.mois) for m in tries[-reference.mois_lus:]]


def _reference(
    employe: Dict[str, Any], bulletins: Sequence[Dict[str, Any]], fin: Mois
) -> Tuple[SalaireDeReference, List[Mois]]:
    mois_de_salaire = _mois_de_salaire(bulletins, fin)
    entree = _date(employe.get("hire_date"))
    anciennete = None
    if entree:
        anciennete = max((fin[0] - entree.year) * 12 + fin[1] - entree.month + 1, 0)
    reference = calculer_salaire_de_reference(
        mois_de_salaire, repli_contrat=_salaire_habituel(employe), mois_d_anciennete=anciennete
    )
    return reference, _mois_retenus(mois_de_salaire, reference)


def phrase_mois_retenus(mois: Sequence[Mois]) -> Optional[str]:
    if not mois:
        return None
    return (
        f"bulletins de {libelle_chiffre(mois[0])} à {libelle_chiffre(mois[-1])} inclus "
        f"({len(mois)} mois)"
    )


def construire_fiche(
    employe: Dict[str, Any],
    bulletins: Sequence[Dict[str, Any]],
    debut: Mois,
    fin: Mois,
    *,
    aujourd_hui: date,
) -> Dict[str, Any]:
    """La fiche : identité, mois, lignes (rubrique, valeur de chaque mois, total),
    notes et salaire de référence.

    `bulletins` : lignes de `payslips` (year, month, payslip_data), y compris
    celles d'avant la période, qui servent au salaire de référence."""
    mois = mois_de_la_periode(debut, fin)
    valides = [
        b for b in bulletins if isinstance(b.get("payslip_data"), dict) and b.get("year") and b.get("month")
    ]
    rubriques: Dict[Mois, Dict[str, Any]] = {m: {} for m in mois}
    synthese: Dict[Mois, Dict[str, Any]] = {m: {} for m in mois}
    du_mois: Dict[Mois, List[Dict[str, Any]]] = defaultdict(list)
    ordre_rubriques: List[str] = []
    for bulletin in sorted(valides, key=lambda b: (int(b["year"]), int(b["month"]))):
        cle = (int(bulletin["year"]), int(bulletin["month"]))
        if cle not in rubriques:
            continue
        du_mois[cle].append(bulletin)
        donnees = bulletin["payslip_data"]
        for libelle, montant in _rubriques_du_brut(donnees):
            if libelle not in ordre_rubriques:
                ordre_rubriques.append(libelle)
            _ajouter(rubriques[cle], libelle, montant)
        for libelle, valeur in _synthese(donnees).items():
            _ajouter(synthese[cle], libelle, valeur)

    entree_date = _date(employe.get("hire_date"))
    entree = (entree_date.year, entree_date.month) if entree_date else None
    courant = (aujourd_hui.year, aujourd_hui.month)
    etats = {m: _etat_du_mois(m, du_mois[m], entree, courant) for m in mois}
    avec_bulletin = sum(1 for m in mois if du_mois[m])

    def ligne(libelle: str, section: str, source: Dict[Mois, Dict[str, Any]]) -> Dict[str, Any]:
        valeurs = {m: _arrondi(source[m].get(libelle)) for m in mois}
        return {"libelle": libelle, "section": section, "valeurs": valeurs, "total": _total(valeurs.values())}

    lignes: List[Dict[str, Any]] = [
        {
            "libelle": "Bulletin Martine",
            "section": "etat",
            "valeurs": etats,
            "total": f"{avec_bulletin} mois avec bulletin sur {len(mois)}",
        }
    ]
    lignes += [ligne(libelle, "brut", rubriques) for libelle in ordre_rubriques]
    lignes += [ligne(libelle, "synthese", synthese) for libelle in SYNTHESE]

    notes: List[str] = []
    non_payes = [m for m in mois if etats[m] == MOIS_NON_PAYE]
    if non_payes:
        notes.append(
            f"Mois non payé dans Martine ({len(non_payes)}) : "
            + ", ".join(libelle_long(m) for m in non_payes)
            + ". Leurs montants ne sont pas dans la fiche (paie faite dans un autre logiciel ou pas encore faite)."
        )
    brouillons = [m for m in mois if etats[m].startswith(MOIS_BROUILLON)]
    if brouillons:
        notes.append(
            f"Brouillon, non validé ({len(brouillons)}) : "
            + ", ".join(libelle_long(m) for m in brouillons)
            + ". Leurs montants peuvent encore changer jusqu'à la validation du bulletin."
        )
    repris = [m for m in mois if etats[m].startswith(MOIS_REPRIS)]
    if repris:
        notes.append(
            f"Repris de l'ancien logiciel ({len(repris)}) : "
            + ", ".join(libelle_long(m) for m in repris)
            + ". Montants tels que l'ancien logiciel les a calculés, repris à la bascule vers Martine."
        )
    notes.append(
        "Montants lus sur les bulletins enregistrés (calculés par Martine, ou repris de l'ancien "
        "logiciel) ; rien n'est recalculé."
    )

    reference, retenus = _reference(employe, valides, fin)
    notes_reference: List[str] = [
        "Même règle que le calcul de sortie de Martine (C. trav. R1234-4), appliquée aux bulletins "
        "jusqu'au dernier mois de la fiche compris. Pour un départ, le calcul de sortie s'arrête "
        "avant le mois de la notification : le montant peut différer."
    ]
    retenus_set = set(retenus)
    brouillons_reference = sorted(
        {
            (int(b["year"]), int(b["month"]))
            for b in valides
            if est_brouillon(b) and (int(b["year"]), int(b["month"])) in retenus_set
        }
    )
    if brouillons_reference:
        notes_reference.append(
            "Le salaire de référence compte des bulletins en brouillon, non validés : "
            + ", ".join(libelle_long(m) for m in brouillons_reference)
            + ". Il peut changer à leur validation."
        )

    return {
        "employe": employe,
        "debut": debut,
        "fin": fin,
        "mois": mois,
        "lignes": lignes,
        "notes": notes,
        "reference": reference,
        "mois_reference": phrase_mois_retenus(retenus),
        "notes_reference": notes_reference,
    }
