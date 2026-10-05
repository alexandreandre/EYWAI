"""Événements du contrat dans la DSN mensuelle.

Arrêts de travail (S21.G00.60), fin du contrat (S21.G00.62), autres
suspensions (S21.G00.65) et indemnités de rupture (S21.G00.52, codes 001 à
025). Fonctions pures : elles lisent ce que le chargeur de la DSN joint au
salarié (`absences_dsn`, `sortie_dsn`) et le bulletin du mois.

Sources, et pourquoi :
- les arrêts viennent des demandes d'absence validées — elles seules
  donnent l'étendue de l'arrêt (dernier jour travaillé, fin prévisionnelle,
  reprise) et la subrogation ; le bulletin n'en voit que la part du mois ;
- les absences non rémunérées (501) et les congés pour événement familial
  (637) viennent des lignes du bulletin, qui sont ce qui a été retenu — y
  compris les absences injustifiées venues du planning, qui ne sont pas des
  demandes ;
- la fin du contrat vient de la sortie, à défaut du terme du CDD.

Règles lues dans le cahier technique NEODeS 2026 (CT2026.1.2) et vérifiées
sur les DSN de l'ancien logiciel de 2026.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

#: Type de demande d'absence → motif d'arrêt (S21.G00.60.001).
MOTIF_ARRET = {
    "arret_maladie": "01",
    "arret_maternite": "02",
    "arret_paternite": "03",
    "arret_maladie_pro": "05",
    "arret_at": "06",
}
MOTIF_ACCIDENT_TRAJET = "04"
#: Accident et maladie professionnelle : date de l'accident obligatoire
#: (60.012, CCH-11) ; le jour de l'accident est travaillé (60.002).
MOTIFS_ACCIDENT = {"04", "05", "06"}

MOTIF_CONGE_NON_REMUNERE = "501"
MOTIF_EVENEMENT_FAMILIAL = "637"

#: Type de sortie EYWAI → motif de rupture (S21.G00.62.002).
MOTIF_RUPTURE = {
    "fin_cdd": "031",
    "demission": "059",
    "rupture_conventionnelle": "043",
    "licenciement": "020",
    "depart_retraite": "039",
    "mise_retraite": "038",
    "fin_periode_essai": "034",
    "deces": "066",
}
#: Date de notification obligatoire (62.003, CCH-12).
MOTIFS_AVEC_NOTIFICATION = {
    "011", "012", "014", "015", "020", "025", "034", "035", "036", "037",
    "058", "059", "082", "083", "087", "088", "089", "095", "096", "097",
}
#: Date de signature de la convention obligatoire (62.004, CCH-11).
MOTIFS_AVEC_SIGNATURE = {"043", "110", "111"}
#: Date d'engagement de la procédure de licenciement (62.005, CCH-12).
MOTIFS_AVEC_ENGAGEMENT = {"011", "012", "014", "015", "020", "025", "087", "088", "089", "091", "092"}

#: Indemnités de rupture (S21.G00.52, codes 001 à 025) : elles ne
#: s'ajoutent pas au salaire brut chômage (002).
INDEMNITES_RUPTURE: List[Tuple[Tuple[str, ...], str]] = [
    (("précarité", "precarite"), "011"),
    (("compensatrice de congés", "compensatrice de conges", "ind.de cp des cdd", "indemnité de cp des cdd"), "020"),
    (("compensatrice de préavis", "compensatrice de preavis"), "023"),
    (("rupture conventionnelle",), "001"),
    (("légale de licenciement", "legale de licenciement"), "007"),
    (("départ à la retraite", "depart a la retraite", "départ en retraite", "depart en retraite"), "005"),
    (("mise à la retraite", "mise a la retraite"), "003"),
]
#: Une indemnité « conventionnelle » a son propre code, voisin du légal.
CODE_CONVENTIONNEL = {"005": "006", "003": "004", "007": "021"}
#: « Indemnité CP » seule, au départ : l'indemnité compensatrice (020). Hors
#: départ, ce libellé est le paiement de congés pris — « Indemnités de CP ».
_ICCP_AU_DEPART = re.compile(r"^\s*indemnit[ée] (de )?c\.?p\.?\s*$", re.IGNORECASE)


def _date(valeur: Any) -> Optional[date]:
    if isinstance(valeur, date):
        return valeur
    texte = str(valeur or "").strip()[:10]
    try:
        return date.fromisoformat(texte)
    except ValueError:
        return None


def dsn(jour: date) -> str:
    return jour.strftime("%d%m%Y")


def date_dsn(texte: str) -> Optional[date]:
    try:
        return datetime.strptime(texte, "%d%m%Y").date()
    except (TypeError, ValueError):
        return None


@dataclass
class Periode:
    motif: str
    debut: date
    fin: date
    subrogation: bool = False


def _jours(absence: Dict[str, Any]) -> List[date]:
    jours = [_date(j) for j in absence.get("selected_days") or []]
    return sorted(j for j in jours if j)


def _motif_arret(absence: Dict[str, Any]) -> Optional[str]:
    motif = MOTIF_ARRET.get(str(absence.get("type") or ""))
    if motif == "06" and "trajet" in str(absence.get("arret_type") or ""):
        return MOTIF_ACCIDENT_TRAJET
    return motif


def periodes_d_arret(absences: Iterable[Dict[str, Any]]) -> List[Periode]:
    """Arrêts continus : une prolongation sans reprise prolonge l'arrêt."""
    brutes: List[Periode] = []
    for absence in absences or []:
        if not isinstance(absence, dict):
            continue
        motif = _motif_arret(absence)
        jours = _jours(absence)
        if not motif or not jours:
            continue
        brutes.append(
            Periode(motif, jours[0], jours[-1], bool(absence.get("subrogation_active")))
        )
    fusionnees: List[Periode] = []
    for periode in sorted(brutes, key=lambda p: (p.motif, p.debut)):
        precedente = fusionnees[-1] if fusionnees else None
        if (
            precedente
            and precedente.motif == periode.motif
            and periode.debut <= precedente.fin + timedelta(days=1)
        ):
            precedente.fin = max(precedente.fin, periode.fin)
            precedente.subrogation = precedente.subrogation or periode.subrogation
            continue
        fusionnees.append(periode)
    return sorted(fusionnees, key=lambda p: p.debut)


def blocs_arret(
    absences: Iterable[Dict[str, Any]],
    debut_mois: date,
    fin_mois: date,
    debut_contrat: Optional[date] = None,
) -> List[Dict[str, str]]:
    """Blocs 60 des arrêts qui touchent le mois (« supra-mensuel » compris)."""
    blocs: List[Dict[str, str]] = []
    for periode in periodes_d_arret(absences):
        if periode.fin < debut_mois or periode.debut > fin_mois:
            continue
        # La veille de la prescription, sauf arrêt prescrit un jour travaillé :
        # le jour de l'accident est travaillé (CT, 60.002).
        dernier_jour = (
            periode.debut
            if periode.motif in MOTIFS_ACCIDENT
            else periode.debut - timedelta(days=1)
        )
        if debut_contrat and dernier_jour < debut_contrat:
            dernier_jour = debut_contrat  # CCH-13
        rubriques = {
            "S21.G00.60.001": periode.motif,
            "S21.G00.60.002": dsn(dernier_jour),
            "S21.G00.60.003": dsn(periode.fin),
            "S21.G00.60.004": "01" if periode.subrogation else "02",
        }
        if periode.subrogation:
            rubriques["S21.G00.60.005"] = dsn(periode.debut)
            rubriques["S21.G00.60.006"] = dsn(periode.fin)
        if periode.fin < fin_mois:
            rubriques["S21.G00.60.010"] = dsn(periode.fin + timedelta(days=1))
            rubriques["S21.G00.60.011"] = "01"
        if periode.motif in MOTIFS_ACCIDENT:
            rubriques["S21.G00.60.012"] = dsn(periode.debut)
        blocs.append(rubriques)
    return blocs


# --------------------------------------------------------------------------
# Autres suspensions (65), lues sur les lignes d'absence du bulletin
# --------------------------------------------------------------------------

#: Bulletin calculé : « Absence injustifiée du 14/09/26 (base) ».
_LIGNE_EYWAI = re.compile(
    r"absence (injustifiée|injustifiee|non rémunérée|non remuneree|événement familial|evenement familial)"
    r" du (\d{2}/\d{2}/\d{2,4})(?: au (\d{2}/\d{2}/\d{2,4}))?",
    re.IGNORECASE,
)
#: Bulletin repris : « Abs. Abs aut nonpayé 080626 », « Abs. Congés s.so 170826-180826 ».
_LIGNE_REPRISE = re.compile(r"(\d{6})(?:\s*-\s*(\d{6}))?\s*$")


def _jour_eywai(texte: str) -> Optional[date]:
    for format_date in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(texte, format_date).date()
        except ValueError:
            continue
    return None


def _jour_reprise(texte: str) -> Optional[date]:
    try:
        return datetime.strptime(texte, "%d%m%y").date()
    except (TypeError, ValueError):
        return None


def _motif_suspension(libelle: str) -> Optional[str]:
    texte = libelle.lower()
    if "famil" in texte:
        return MOTIF_EVENEMENT_FAMILIAL
    if any(
        mot in texte
        for mot in ("injustifi", "non rémunér", "non remuner", "nonpay", "non pay", "s.so", "sans solde")
    ):
        return MOTIF_CONGE_NON_REMUNERE
    return None


def suspensions_du_bulletin(payslip_data: Dict[str, Any]) -> List[Tuple[str, date, date]]:
    """(motif, début, fin) des absences non rémunérées et événements familiaux."""
    lignes: List[Dict[str, Any]] = []
    calcul = payslip_data.get("calcul_du_brut")
    if isinstance(calcul, list):
        lignes.extend(l for l in calcul if isinstance(l, dict))
    lignes.extend(
        l for l in (payslip_data.get("details_absences") or []) if isinstance(l, dict)
    )
    vues = set()
    resultat: List[Tuple[str, date, date]] = []
    for ligne in lignes:
        if not float(ligne.get("perte") or 0) > 0:
            continue
        libelle = str(ligne.get("libelle") or "")
        if "structurell" in libelle.lower():
            continue
        motif = _motif_suspension(libelle)
        if not motif:
            continue
        trouve = _LIGNE_EYWAI.search(libelle)
        if trouve:
            debut = _jour_eywai(trouve.group(2))
            fin = _jour_eywai(trouve.group(3)) if trouve.group(3) else debut
        else:
            trouve = _LIGNE_REPRISE.search(libelle)
            if not trouve:
                continue
            debut = _jour_reprise(trouve.group(1))
            fin = _jour_reprise(trouve.group(2)) if trouve.group(2) else debut
        if not debut or not fin:
            continue
        cle = (motif, debut, fin)
        if cle in vues:
            continue
        vues.add(cle)
        resultat.append(cle)
    return sorted(resultat, key=lambda s: (s[1], s[0]))


def blocs_suspension(payslip_data: Dict[str, Any]) -> List[Dict[str, str]]:
    return [
        {
            "S21.G00.65.001": motif,
            "S21.G00.65.002": dsn(debut),
            "S21.G00.65.003": dsn(fin),
        }
        for motif, debut, fin in suspensions_du_bulletin(payslip_data)
    ]


def _chevauchement(debut: date, fin: date, debut_mois: date, fin_mois: date) -> int:
    a, b = max(debut, debut_mois), min(fin, fin_mois)
    return max(0, (b - a).days + 1)


def jours_hors_plafond(
    absences: Iterable[Dict[str, Any]],
    payslip_data: Dict[str, Any],
    debut_periode: date,
    fin_periode: date,
) -> int:
    """Jours calendaires d'arrêt et de congé non rémunéré de la période.

    Ils sortent des jours du plafond (53 unité 40) : 31 jours en mai, moins
    deux jours non payés et sept jours d'accident du travail, font les 22
    déclarés par l'ancien logiciel. Les événements familiaux, payés, restent.
    """
    jours = set()
    for periode in periodes_d_arret(absences):
        for decalage in range(_chevauchement(periode.debut, periode.fin, debut_periode, fin_periode)):
            jours.add(max(periode.debut, debut_periode) + timedelta(days=decalage))
    for motif, debut, fin in suspensions_du_bulletin(payslip_data):
        if motif != MOTIF_CONGE_NON_REMUNERE:
            continue
        for decalage in range(_chevauchement(debut, fin, debut_periode, fin_periode)):
            jours.add(max(debut, debut_periode) + timedelta(days=decalage))
    return len(jours)


# --------------------------------------------------------------------------
# Fin du contrat (62)
# --------------------------------------------------------------------------

_MOTIF_REPRIS = re.compile(r"\((\d{3})\)")


def date_de_fin(
    employee: Dict[str, Any], debut_mois: date, fin_mois: date
) -> Optional[date]:
    """Dernier jour du contrat s'il tombe dans le mois, sinon None."""
    sortie = employee.get("sortie_dsn") if isinstance(employee.get("sortie_dsn"), dict) else {}
    candidates = [
        _date(sortie.get("last_working_day")) if sortie else None,
        _date(employee.get("contract_end_date")),
    ]
    for candidate in candidates:
        if candidate and debut_mois <= candidate <= fin_mois:
            return candidate
    return None


def bloc_fin_contrat(
    employee: Dict[str, Any],
    debut_mois: date,
    fin_mois: date,
    *,
    apprentissage: bool = False,
) -> Tuple[Optional[Dict[str, str]], List[str]]:
    """Bloc 62 si le contrat finit dans le mois, et ses avertissements."""
    avertissements: List[str] = []
    fin = date_de_fin(employee, debut_mois, fin_mois)
    if not fin:
        return None, avertissements
    sortie = employee.get("sortie_dsn") if isinstance(employee.get("sortie_dsn"), dict) else {}
    # Une sortie reprise d'une DSN porte son motif d'origine : « Import DSN (039) ».
    repris = _MOTIF_REPRIS.search(str((sortie or {}).get("exit_reason") or ""))
    type_sortie = str((sortie or {}).get("exit_type") or "")
    if repris:
        motif = repris.group(1)
    elif type_sortie:
        motif = MOTIF_RUPTURE.get(type_sortie, "")
        if type_sortie == "licenciement" and (sortie or {}).get("is_gross_misconduct"):
            motif = "087"
        if type_sortie == "fin_cdd" and apprentissage:
            motif = "081"
    else:
        # Terme d'un CDD sans dossier de sortie.
        motif = "081" if apprentissage else "031"
    if not motif:
        avertissements.append(
            f"Motif de fin de contrat inconnu pour la sortie « {type_sortie} » : bloc 62 non émis"
        )
        return None, avertissements
    rubriques = {
        "S21.G00.62.001": dsn(fin),
        "S21.G00.62.002": motif,
        "S21.G00.62.006": dsn(fin),
    }
    notification = _date((sortie or {}).get("exit_request_date"))
    if motif in MOTIFS_AVEC_NOTIFICATION | MOTIFS_AVEC_SIGNATURE | MOTIFS_AVEC_ENGAGEMENT:
        if notification and notification <= fin:
            if motif in MOTIFS_AVEC_NOTIFICATION:
                rubriques["S21.G00.62.003"] = dsn(notification)
            if motif in MOTIFS_AVEC_SIGNATURE:
                rubriques["S21.G00.62.004"] = dsn(notification)
            if motif in MOTIFS_AVEC_ENGAGEMENT:
                rubriques["S21.G00.62.005"] = dsn(notification)
        else:
            avertissements.append(
                f"Date de notification / signature de la rupture inconnue (motif {motif}) : "
                "rubrique 62.003 / 62.004 / 62.005 à compléter"
            )
    return rubriques, avertissements


# --------------------------------------------------------------------------
# Indemnités de rupture (52)
# --------------------------------------------------------------------------


def _code_indemnite(libelle: str, sortie: bool = False) -> Optional[str]:
    texte = libelle.lower()
    for mots, code in INDEMNITES_RUPTURE:
        if any(mot in texte for mot in mots):
            if "conv" in texte and code in CODE_CONVENTIONNEL:
                return CODE_CONVENTIONNEL[code]
            return code
    if sortie and _ICCP_AU_DEPART.match(libelle):
        return "020"
    return None


def indemnites_de_rupture(
    payslip_data: Dict[str, Any], sortie: bool = False
) -> List[Tuple[str, float, bool]]:
    """(code 52, montant, comprise dans le brut) des indemnités de fin de contrat.

    ``sortie`` : le contrat finit dans le mois — seule une sortie fait d'une
    « Indemnité CP » l'indemnité compensatrice de congés payés.
    """
    resultat: Dict[str, List[float]] = {}
    dans_le_brut: Dict[str, bool] = {}
    calcul = payslip_data.get("calcul_du_brut")
    for ligne in calcul if isinstance(calcul, list) else []:
        if not isinstance(ligne, dict) or not float(ligne.get("gain") or 0):
            continue
        code = _code_indemnite(str(ligne.get("libelle") or ""), sortie)
        if code:
            resultat.setdefault(code, []).append(float(ligne["gain"]))
            dans_le_brut[code] = True
    indemnites_sortie = payslip_data.get("indemnites_sortie")
    if isinstance(indemnites_sortie, dict):
        for ligne in indemnites_sortie.get("lignes_soumises") or []:
            code = _code_indemnite(str(ligne.get("libelle") or ""), True)
            if code and code not in resultat and float(ligne.get("gain") or 0):
                resultat.setdefault(code, []).append(float(ligne["gain"]))
                dans_le_brut[code] = True
        for ligne in indemnites_sortie.get("lignes_exonerees") or []:
            code = _code_indemnite(str(ligne.get("libelle") or ""), True)
            if code and float(ligne.get("montant") or 0):
                resultat.setdefault(code, []).append(float(ligne["montant"]))
                dans_le_brut.setdefault(code, False)
    return [
        (code, round(sum(montants), 2), dans_le_brut.get(code, False))
        for code, montants in sorted(resultat.items())
    ]
