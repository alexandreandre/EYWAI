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

from app.modules.absences.domain.date_accident import date_accident_de
from app.modules.dsn_export.domain.motif_rupture import motif_propose, motif_refuse

#: Type de demande d'absence → motif d'arrêt (S21.G00.60.001).
MOTIF_ARRET = {
    "arret_maladie": "01",
    "arret_maternite": "02",
    "arret_paternite": "03",
    "arret_maladie_pro": "05",
    "arret_at": "06",
}
MOTIF_ACCIDENT_TRAJET = "04"
#: Adoption, saisie sous la nature maternité ou paternité (cahier technique 2026.1).
MOTIF_ADOPTION = "09"
#: Accident et maladie professionnelle : le jour de l'accident est
#: travaillé (60.002). Leur date (60.012) relève du signalement d'arrêt.
MOTIFS_ACCIDENT = {"04", "05", "06"}

#: Temps partiel thérapeutique selon le risque d'origine (60.001, cahier
#: technique 2026.1.2). Le trajet n'a pas de nature propre : voir `_motif_tpt`.
TYPE_ARRET_TPT = "mi_temps_therapeutique"
MOTIF_TPT = {"arret_maladie": "15", "arret_at": "16", "arret_maladie_pro": "18"}
MOTIF_TPT_TRAJET = "17"
MOTIFS_TPT = {"15", "16", "17", "18"}
#: Motif de la reprise (60.011) : modalité du travail après l'arrêt.
REPRISE_NORMALE = "01"
REPRISE_TPT = "02"

MOTIF_CONGE_NON_REMUNERE = "501"
#: Activité partielle : chômage sans rupture du contrat (65.001).
MOTIF_CHOMAGE_PARTIEL = "602"
MOTIF_EVENEMENT_FAMILIAL = "637"

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
    # Rupture de période d'essai, délai de prévenance non respecté (cahier
    # technique 2026.1 : « 017 - Dommages et intérêts dus [...] à une rupture de
    # période d'essai (délai de prévenance) »).
    (("délai de prévenance", "delai de prevenance"), "017"),
    (("précarité", "precarite"), "011"),
    (("compensatrice de congés", "compensatrice de conges", "ind.de cp des cdd", "indemnité de cp des cdd"), "020"),
    (("compensatrice de préavis", "compensatrice de preavis"), "023"),
    (("rupture conventionnelle",), "001"),
    (("légale de licenciement", "legale de licenciement"), "007"),
    # Inaptitude d'origine professionnelle (L1226-14 ; cahier technique 2026.1).
    (("spéciale de licenciement", "speciale de licenciement"), "009"),
    (("compensatrice d'inaptitude", "compensatrice d’inaptitude"), "032"),
    # Licenciement conventionnel (« conv » → 021) et part soumise d'une
    # indemnité de licenciement.
    (
        (
            "conventionnelle de licenciement",
            "indemnité de licenciement",
            "indemnite de licenciement",
        ),
        "007",
    ),
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
    date_accident: Optional[date] = None
    absence_id: Optional[str] = None


def _jours(absence: Dict[str, Any]) -> List[date]:
    jours = [_date(j) for j in absence.get("selected_days") or []]
    return sorted(j for j in jours if j)


def _motif_tpt(absence: Dict[str, Any], absences: List[Dict[str, Any]]) -> Optional[str]:
    """15, 16 ou 18 selon la nature ; 17 si l'arrêt d'accident qui précède est
    un accident de trajet, seule trace de cette origine dans la demande."""
    motif = MOTIF_TPT.get(str(absence.get("type") or ""))
    if motif != "16":
        return motif
    debut = _jours(absence)[0]
    precedents = [
        a
        for a in absences
        if isinstance(a, dict)
        and a.get("type") == "arret_at"
        and a.get("arret_type") != TYPE_ARRET_TPT
        and _jours(a)
        and _jours(a)[-1] < debut
    ]
    if precedents and "trajet" in str(
        max(precedents, key=lambda a: _jours(a)[-1]).get("arret_type") or ""
    ):
        return MOTIF_TPT_TRAJET
    return motif


def _motif_arret(absence: Dict[str, Any], absences: List[Dict[str, Any]]) -> Optional[str]:
    if str(absence.get("arret_type") or "") == TYPE_ARRET_TPT and _jours(absence):
        return _motif_tpt(absence, absences)
    motif = MOTIF_ARRET.get(str(absence.get("type") or ""))
    if motif == "06" and "trajet" in str(absence.get("arret_type") or ""):
        return MOTIF_ACCIDENT_TRAJET
    if motif in ("02", "03") and str(absence.get("arret_type") or "") == "adoption":
        return MOTIF_ADOPTION
    return motif


def periodes_d_arret(absences: Iterable[Dict[str, Any]]) -> List[Periode]:
    """Arrêts continus : une prolongation sans reprise prolonge l'arrêt."""
    brutes: List[Periode] = []
    toutes = list(absences or [])
    for absence in toutes:
        if not isinstance(absence, dict):
            continue
        motif = _motif_arret(absence, toutes)
        jours = _jours(absence)
        if not motif or not jours:
            continue
        brutes.append(
            Periode(
                motif,
                jours[0],
                jours[-1],
                bool(absence.get("subrogation_active")),
                date_accident_de(absence),
                str(absence["id"]) if absence.get("id") else None,
            )
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
            precedente.date_accident = precedente.date_accident or periode.date_accident
            continue
        fusionnees.append(periode)
    return sorted(fusionnees, key=lambda p: p.debut)


def dernier_jour_travaille(
    motif: str,
    debut: date,
    debut_contrat: Optional[date],
    date_accident: Optional[date] = None,
) -> date:
    """La veille de l'arrêt, sauf accident ou maladie professionnelle : le jour
    de l'accident est travaillé (CT, 60.002) ; jamais avant le contrat (CCH-13)."""
    jour_de_l_accident = motif in MOTIFS_ACCIDENT and not (date_accident and date_accident < debut)
    jour = debut if jour_de_l_accident else debut - timedelta(days=1)
    if debut_contrat and jour < debut_contrat:
        return debut_contrat
    return jour


def _reprend_en_tpt(periode: Periode, periodes: List[Periode]) -> bool:
    """Un temps partiel thérapeutique commence au jour ouvré qui suit l'arrêt."""
    if periode.motif in MOTIFS_TPT:
        return False
    for suivante in periodes:
        if suivante.motif not in MOTIFS_TPT or suivante.debut <= periode.fin:
            continue
        ecart = (suivante.debut - periode.fin).days
        if all((periode.fin + timedelta(days=k)).weekday() >= 5 for k in range(1, ecart)):
            return True
    return False


def blocs_arret(
    absences: Iterable[Dict[str, Any]],
    debut_mois: date,
    fin_mois: date,
    debut_contrat: Optional[date] = None,
    *,
    compte_employeur: Optional[Tuple[str, str]] = None,
    subrogation_paie: Optional[bool] = None,
) -> List[Dict[str, str]]:
    """Blocs 60 des arrêts qui touchent le mois (« supra-mensuel » compris).

    ``compte_employeur`` : (IBAN, BIC) de l'employeur, obligatoires en
    subrogation (60.007 / 60.008). ``subrogation_paie`` : ce que la paie du
    mois a appliqué, qui prime sur la case cochée dans la demande d'arrêt.
    """
    blocs: List[Dict[str, str]] = []
    periodes = periodes_d_arret(absences)
    for periode in periodes:
        if periode.fin < debut_mois or periode.debut > fin_mois:
            continue
        if subrogation_paie is not None:
            periode.subrogation = subrogation_paie
        dernier_jour = dernier_jour_travaille(
            periode.motif, periode.debut, debut_contrat, periode.date_accident
        )
        rubriques = {
            "S21.G00.60.001": periode.motif,
            "S21.G00.60.002": dsn(dernier_jour),
            "S21.G00.60.003": dsn(periode.fin),
            "S21.G00.60.004": "01" if periode.subrogation else "02",
        }
        if periode.subrogation:
            rubriques["S21.G00.60.005"] = dsn(periode.debut)
            rubriques["S21.G00.60.006"] = dsn(periode.fin)
            if compte_employeur and compte_employeur[0]:
                rubriques["S21.G00.60.007"] = compte_employeur[0]
                rubriques["S21.G00.60.008"] = compte_employeur[1]
        if periode.fin < fin_mois:
            rubriques["S21.G00.60.010"] = dsn(periode.fin + timedelta(days=1))
            rubriques["S21.G00.60.011"] = (
                REPRISE_TPT if _reprend_en_tpt(periode, periodes) else REPRISE_NORMALE
            )
        # La date de l'accident (60.012) ne se déclare qu'au signalement
        # d'arrêt : en DSN mensuelle, DSN-VAL la refuse (CST-04).
        blocs.append(rubriques)
    return blocs


# --------------------------------------------------------------------------
# Temps partiel thérapeutique (66), obligatoire sous les motifs 15 à 18
# --------------------------------------------------------------------------

_LIGNE_ARRET_MARTINE = re.compile(r" du (\d{2})/(\d{2})(?: au (\d{2})/(\d{2}))?")


def _bornes_ligne_d_arret(ligne: Dict[str, Any], annee: int) -> Optional[Tuple[date, date]]:
    """Les dates d'une ligne d'arrêt : reprise (« 070926-300926 ») ou calculée."""
    libelle = str(ligne.get("libelle") or "")
    trouve = _LIGNE_REPRISE.search(libelle)
    if trouve:
        debut = _jour_reprise(trouve.group(1))
        fin = _jour_reprise(trouve.group(2)) if trouve.group(2) else debut
        return (debut, fin) if debut and fin else None
    trouve = _LIGNE_ARRET_MARTINE.search(libelle)
    if not trouve:
        return None
    jour, mois, jour_fin, mois_fin = trouve.groups()
    debut = date(annee, int(mois), int(jour))
    fin = date(annee, int(mois_fin), int(jour_fin)) if jour_fin else debut
    return debut, fin


def _est_ligne_de_tpt(ligne: Dict[str, Any]) -> bool:
    libelle = str(ligne.get("libelle") or "").lower()
    return "tps.part" in libelle or "thérap" in libelle or "therap" in libelle or bool(
        ligne.get("is_arret_maladie")
    )


def _perte_du_tpt(payslip_data: Dict[str, Any], debut: date, fin: date) -> Optional[float]:
    """Perte de salaire des lignes d'arrêt du bulletin dans la période (66.003)."""
    total: Optional[float] = None
    for ligne in payslip_data.get("calcul_du_brut") or []:
        if not isinstance(ligne, dict) or not _est_ligne_de_tpt(ligne):
            continue
        bornes = _bornes_ligne_d_arret(ligne, debut.year)
        if bornes and bornes[0] <= fin and bornes[1] >= debut:
            total = (total or 0.0) + float(ligne.get("perte") or 0)
    return None if total is None else round(total, 2)


def blocs_temps_partiel_therapeutique(
    absences: Iterable[Dict[str, Any]],
    payslip_data: Dict[str, Any],
    debut_mois: date,
    fin_mois: date,
) -> Tuple[List[Dict[str, str]], bool]:
    """Blocs 66, bornés au mois déclaré, et « une perte n'a pas été trouvée »."""
    blocs: List[Dict[str, str]] = []
    perte_introuvable = False
    for periode in periodes_d_arret(absences):
        if periode.motif not in MOTIFS_TPT or periode.fin < debut_mois or periode.debut > fin_mois:
            continue
        debut, fin = max(periode.debut, debut_mois), min(periode.fin, fin_mois)
        perte = _perte_du_tpt(payslip_data, debut, fin)
        perte_introuvable = perte_introuvable or perte is None
        blocs.append(
            {
                "S21.G00.66.001": dsn(debut),
                "S21.G00.66.002": dsn(fin),
                "S21.G00.66.003": f"{perte or 0.0:.2f}",
            }
        )
    return blocs, perte_introuvable


# --------------------------------------------------------------------------
# Autres suspensions (65), lues sur les lignes d'absence du bulletin
# --------------------------------------------------------------------------

#: Bulletin calculé : « Absence injustifiée du 14/09/26 (base) ».
_LIGNE_MARTINE = re.compile(
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
        trouve = _LIGNE_MARTINE.search(libelle)
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


# --------------------------------------------------------------------------
# Activité partielle (65 motif 602, 51 type 019)
# --------------------------------------------------------------------------

#: Au-delà, la colonne « taux » d'une ligne reprise est un taux journalier et
#: sa quantité des jours : 1 à 140,91 € pour une journée de 7 h (bulletins
#: LEWIS de juin 2026). La DSN veut des heures (51.012).
_TAUX_HORAIRE_MAXIMUM = 100.0


@dataclass
class ActivitePartielle:
    heures: float
    indemnite: float
    periodes: List[Tuple[date, date]]
    en_heures: bool


def _est_chomage_partiel(libelle: str) -> bool:
    texte = libelle.lower()
    if "indemn" in texte:
        return False
    return "act. partiel" in texte or (
        ("chôm" in texte or "chom" in texte) and "act" in texte and "part" in texte
    )


def activite_partielle_du_bulletin(payslip_data: Dict[str, Any]) -> Optional[ActivitePartielle]:
    """Heures chômées et indemnité : la saisie du mois ou les lignes reprises."""
    heures = 0.0
    en_heures = True
    periodes: List[Tuple[date, date]] = []
    trouve_ligne = False
    for ligne in payslip_data.get("calcul_du_brut") or []:
        if not isinstance(ligne, dict) or ligne.get("is_sous_total"):
            continue
        libelle = str(ligne.get("libelle") or "")
        if not _est_chomage_partiel(libelle):
            continue
        trouve_ligne = True
        heures += abs(float(ligne.get("quantite") or 0))
        if float(ligne.get("taux") or 0) > _TAUX_HORAIRE_MAXIMUM:
            en_heures = False
        trouve = _LIGNE_REPRISE.search(libelle)
        if trouve:
            debut = _jour_reprise(trouve.group(1))
            fin = _jour_reprise(trouve.group(2)) if trouve.group(2) else debut
            if debut and fin:
                periodes.append((debut, fin))
    indemnite = sum(
        float(p.get("montant") or 0)
        for cle in ("primes_non_soumises", "revenus_hors_brut_imposables")
        for p in payslip_data.get(cle) or []
        if isinstance(p, dict)
        and "indemn" in str(p.get("libelle") or "").lower()
        and "partiel" in str(p.get("libelle") or "").lower()
    )
    if not trouve_ligne:
        return None
    return ActivitePartielle(round(heures, 2), round(indemnite, 2), sorted(periodes), en_heures)


def declaration_activite_partielle(
    payslip_data: Dict[str, Any], debut_periode: date, fin_periode: date
) -> Tuple[List[Dict[str, str]], Optional[Tuple[float, float]], List[str]]:
    """Blocs 65 (602), (heures, indemnité) du 019 et avertissements.

    Les deux vont ensemble (65.001 SIG-11). Une saisie du mois ne porte pas de
    dates : le bloc couvre alors la période, et un avertissement le dit.
    """
    activite = activite_partielle_du_bulletin(payslip_data)
    if activite is None:
        return [], None, []
    if not activite.en_heures or activite.heures <= 0:
        return [], None, [
            "Activité partielle non déclarée (blocs 65 et 51 type 019) : "
            "heures chômées absentes ou exprimées en jours"
        ]
    avertissements: List[str] = []
    periodes = activite.periodes
    if not periodes:
        periodes = [(debut_periode, fin_periode)]
        avertissements.append(
            "Activité partielle sans dates de chômage : bloc 602 déclaré sur "
            "toute la période, à corriger avec les jours réels"
        )
    blocs = [
        {
            "S21.G00.65.001": MOTIF_CHOMAGE_PARTIEL,
            "S21.G00.65.002": dsn(debut),
            "S21.G00.65.003": dsn(fin),
        }
        for debut, fin in periodes
    ]
    return blocs, (activite.heures, activite.indemnite), avertissements


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
    notes = (sortie or {}).get("exit_notes")
    motif_dsn = notes.get("motif_dsn") if isinstance(notes, dict) else None
    if motif_dsn:
        # Choisi au dossier : une sortie reprise ne le porte pas, sinon il prime.
        refus = motif_refuse(str(motif_dsn), sortie, employee)
        if refus:
            avertissements.append(f"{refus} Bloc 62 non émis tant que le motif n'est pas corrigé.")
            return None, avertissements
        motif = str(motif_dsn)
    elif repris:
        motif = repris.group(1)
    elif type_sortie:
        motif, raison = motif_propose(sortie, employee, apprentissage=apprentissage)
        if raison:
            avertissements.append(f"{raison} Bloc 62 non émis tant que le motif n'est pas choisi.")
            return None, avertissements
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
    lignes = list(calcul) if isinstance(calcul, list) else []
    # Le moteur range l'indemnité compensatrice de congés avec les congés
    # (`details_conges`) : c'est elle qui a été versée, pas l'estimation du
    # dossier que garde le récapitulatif `indemnites_sortie`.
    conges = payslip_data.get("details_conges")
    lignes += [
        ligne
        for ligne in (conges if isinstance(conges, list) else [])
        if isinstance(ligne, dict) and "compensatrice" in str(ligne.get("libelle") or "").lower()
    ]
    for ligne in lignes:
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
            montant = round(float(ligne.get("montant") or 0), 2)
            if not (code and montant):
                continue
            # Indemnité conventionnelle de licenciement : la part légale en 007,
            # le supplément conventionnel en 021 (cahier technique 2026.1).
            part_legale = float(ligne.get("part_legale") or 0)
            if code == CODE_CONVENTIONNEL["007"] and part_legale > 0:
                legale = round(min(part_legale, montant), 2)
                resultat.setdefault("007", []).append(legale)
                dans_le_brut.setdefault("007", False)
                montant = round(montant - legale, 2)
                if montant <= 0:
                    continue
            resultat.setdefault(code, []).append(montant)
            dans_le_brut.setdefault(code, False)
    return [
        (code, round(sum(montants), 2), dans_le_brut.get(code, False))
        for code, montants in sorted(resultat.items())
    ]


# --------------------------------------------------------------------------
# Prime de partage de la valeur (52, codes 904 à 906)
# --------------------------------------------------------------------------


def _est_ppv(ligne: Dict[str, Any]) -> bool:
    # Même reconnaissance que le bulletin : par la nature, catalogue ou libellé.
    from app.modules.payroll.engine.ppv import est_une_ppv

    return est_une_ppv(ligne.get("prime_id"), ligne.get("libelle"))


def primes_partage_valeur(payslip_data: Dict[str, Any]) -> List[Tuple[str, float]]:
    """(code 52, montant) des primes de partage de la valeur du mois.

    La paie range la PPV exonérée et non imposable (moins de 50 salariés)
    dans les éléments non soumis : 904 ; exonérée mais imposable (50 et
    plus), dans les revenus imposables hors brut : 905. Soumise à
    cotisations, elle est dans le brut et n'a pas de bloc 52.
    """
    resultat: Dict[str, float] = {}
    for cle, code in (("primes_non_soumises", "904"), ("revenus_hors_brut_imposables", "905")):
        for ligne in payslip_data.get(cle) or []:
            if isinstance(ligne, dict) and _est_ppv(ligne) and float(ligne.get("montant") or 0):
                resultat[code] = resultat.get(code, 0.0) + float(ligne["montant"])
    return [(code, round(montant, 2)) for code, montant in sorted(resultat.items())]
