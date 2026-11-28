"""Récapitulatif des congés et absences d'une société sur une période (lot L21).

Demande de la gestionnaire (27/11/2026) : voir les congés pris de tous les
salariés sans ouvrir la fiche de chacun. Domaine pur : les jours sont comptés
sur le calendrier de paie (`employee_schedules.planned_calendar`), là où sont
posés congés payés, RTT, absences et arrêts ; les demandes validées disent la
nature d'un arrêt, un congé sans solde, une récupération de modulation, et
donnent les congés qui n'écrivent pas le calendrier (JTC, repos seniors).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, Mapping, Optional

from app.modules.absences.domain.nature_arret import LIBELLES_NATURE, NATURE_DU_TYPE_D_ARRET
from app.shared.domain.conge_parental import est_jour_de_conge_parental

#: Colonnes de jours, dans l'ordre de l'écran et du fichier : (clé, libellé, source).
COLONNES: tuple[tuple[str, str, str], ...] = (
    ("cp", "Congés payés", "Calendrier : jours « Congés payés » (demi-journée = 0,5), hors récupération de modulation"),
    ("rtt", "RTT", "Calendrier : jours « RTT » (demi-journée = 0,5)"),
    (
        "jtc_repos_seniors",
        "JTC / repos seniors",
        "Demandes validées JTC et repos seniors (elles n'écrivent pas le calendrier)",
    ),
    (
        "repos_recup",
        "Repos compensateur / récup.",
        "Calendrier : jours « Congé » (repos compensateur, anciens congés hors paie) et jours "
        "d'une récupération de modulation validée",
    ),
    (
        "absence_non_payee",
        "Absences non payées",
        "Calendrier : jours « Absence non rémunérée » hors congé sans solde et congé parental "
        "(quelques heures = part de la journée habituelle du mois)",
    ),
    (
        "parental_sans_solde",
        "Congé parental / sans solde",
        "Calendrier : jours « Absence non rémunérée » d'un congé sans solde validé ou d'un congé parental",
    ),
    (
        "arret_maladie",
        "Arrêt maladie",
        "Calendrier : jours « Arrêt » de nature maladie (ALD, mi-temps thérapeutique compris)",
    ),
    (
        "arret_at",
        "Accident du travail / trajet",
        "Calendrier : jours d'arrêt de nature accident du travail, de trajet ou rechute",
    ),
    ("arret_maladie_pro", "Maladie professionnelle", "Calendrier : jours d'arrêt de nature maladie professionnelle"),
    ("arret_maternite", "Congé maternité", "Calendrier : jours d'arrêt de nature maternité (adoption comprise)"),
    ("arret_paternite", "Congé paternité", "Calendrier : jours d'arrêt de nature paternité (adoption comprise)"),
    (
        "arret_non_precise",
        "Arrêt (nature non précisée)",
        "Calendrier : jours d'arrêt sans demande validée ni type d'arrêt qui en dise la nature",
    ),
    ("evenement_familial", "Événement familial", "Calendrier : jours « Événement familial »"),
    (
        "absence_justifiee",
        "Absence justifiée",
        "Calendrier : jours « Absence justifiée » (quelques heures = part de la journée habituelle)",
    ),
    ("activite_partielle", "Activité partielle", "Calendrier : jours « Activité partielle »"),
)

CLES_COLONNES: tuple[str, ...] = tuple(c[0] for c in COLONNES)

SOURCE_SOLDES_CP = (
    "Soldes CP N-1 et N au jour du calcul, calculés comme les soldes de la fiche salarié "
    "(congés validés et congés payés du calendrier, ajustements et reprise de solde, congés "
    "parentaux pour l'ancienneté) ; les jours de CP placés au CET n'en sont pas retirés"
)

NOTE_ARRETS = (
    "Arrêts : jours que le calendrier porte en arrêt (le salarié aurait travaillé) ; "
    "les week-ends et repos couverts par l'arrêt ne sont pas comptés. La nature vient de "
    "la demande validée du jour, à défaut du type d'arrêt du calendrier. Dates et IJ : « Arrêts & IJ »."
)

NOTE_REPRISE = (
    "Reprise dans Martine : pour un salarié repris en cours de période (date sur sa ligne), "
    "le calendrier avant cette date peut être incomplet ; ses congés d'avant sont dans le solde repris."
)

#: Statuts présents : leur ligne apparaît même sans jour, et leurs soldes sont calculés.
STATUTS_PRESENTS = frozenset({"actif", "active", "en_onboarding", "en_sortie"})

#: Type de jour du calendrier -> colonne (arrêts et absence non rémunérée à part).
_TYPE_VERS_COLONNE: dict[str, str] = {
    "conges_payes": "cp",
    "rtt": "rtt",
    "conge": "repos_recup",
    "evenement_familial": "evenement_familial",
    "absence_justifiee": "absence_justifiee",
    "activite_partielle": "activite_partielle",
}

_TYPES_JOUR_ARRET = frozenset({"arret_maladie", "arret_at"})

#: Absences comptées en part de journée quand elles ne durent que quelques heures.
_TYPES_EN_HEURES = frozenset({"absence_non_remuneree", "absence_justifiee"})

_TYPES_JOUR_TRAVAILLE = frozenset({"travail", "work"})

#: Demandes validées comptées hors calendrier (elles ne l'écrivent jamais).
TYPES_DEMANDE_HORS_CALENDRIER = {"jtc": "jtc_repos_seniors", "repos_senior": "jtc_repos_seniors"}

#: Journée habituelle quand le mois n'a aucun jour travaillé avec ses heures.
JOURNEE_PAR_DEFAUT_H = 7.0

#: Plus longue période acceptée (une année et un jour).
DUREE_MAX_JOURS = 366


@dataclass(frozen=True)
class JoursDesDemandes:
    """Ce que les demandes validées d'un salarié disent de ses jours de calendrier."""

    sans_solde: frozenset[str] = frozenset()
    recup_modulation: frozenset[str] = frozenset()
    #: date ISO -> nature (clé de colonne) de l'arrêt validé ce jour-là.
    nature_arret: Mapping[str, str] = field(default_factory=dict)


def _jours_iso(demande: Mapping[str, Any]) -> list[str]:
    return [str(j)[:10] for j in demande.get("selected_days") or [] if j]


def jours_des_demandes(demandes: Iterable[Mapping[str, Any]]) -> JoursDesDemandes:
    sans_solde: set[str] = set()
    recup: set[str] = set()
    nature: dict[str, str] = {}
    for demande in demandes:
        type_demande = str(demande.get("type") or "")
        if type_demande == "sans_solde":
            sans_solde.update(_jours_iso(demande))
        elif type_demande == "recuperation_modulation":
            recup.update(_jours_iso(demande))
        elif type_demande in LIBELLES_NATURE:
            for jour in _jours_iso(demande):
                nature[jour] = type_demande
    return JoursDesDemandes(frozenset(sans_solde), frozenset(recup), nature)


def jours_a_zero() -> dict[str, float]:
    return {cle: 0.0 for cle in CLES_COLONNES}


def lire_periode(debut: Optional[str], fin: Optional[str]) -> tuple[date, date]:
    """Les bornes AAAA-MM-JJ ; ValueError si absentes, illisibles, inversées ou trop longues."""
    if not debut or not fin:
        raise ValueError("Indiquez le début et la fin de la période (AAAA-MM-JJ).")
    try:
        d0 = date.fromisoformat(str(debut)[:10])
        d1 = date.fromisoformat(str(fin)[:10])
    except ValueError as exc:
        raise ValueError("Dates illisibles : utilisez le format AAAA-MM-JJ.") from exc
    if d1 < d0:
        raise ValueError("La fin de la période précède son début.")
    if (d1 - d0).days >= DUREE_MAX_JOURS:
        raise ValueError("La période ne peut pas dépasser un an.")
    return d0, d1


def mois_de_la_periode(debut: date, fin: date) -> list[tuple[int, int]]:
    """Les (année, mois) touchés par la période, dans l'ordre."""
    mois: list[tuple[int, int]] = []
    annee, m = debut.year, debut.month
    while (annee, m) <= (fin.year, fin.month):
        mois.append((annee, m))
        annee, m = (annee + 1, 1) if m == 12 else (annee, m + 1)
    return mois


def _nombre(valeur: Any) -> Optional[float]:
    try:
        return float(valeur) if valeur is not None else None
    except (TypeError, ValueError):
        return None


def journee_habituelle(jours: Iterable[Any]) -> float:
    """Les heures d'une journée travaillée du mois (la plus fréquente), 7 h à défaut."""
    heures = Counter(
        h
        for j in jours
        if isinstance(j, dict) and str(j.get("type") or "") in _TYPES_JOUR_TRAVAILLE
        for h in [_nombre(j.get("heures_prevues"))]
        if h and h > 0
    )
    return heures.most_common(1)[0][0] if heures else JOURNEE_PAR_DEFAUT_H


def _part_de_journee(jour: Mapping[str, Any], journee: float, *, en_heures: bool) -> float:
    """Quotité posée par le serveur ; à défaut, pour une absence de quelques heures,
    ses heures sur la journée habituelle ; une journée entière sinon."""
    quotite = _nombre(jour.get("quotite_absence"))
    if quotite is not None and 0 < quotite <= 1:
        return quotite
    if en_heures:
        heures = _nombre(jour.get("heures"))
        if heures is None:
            heures = _nombre(jour.get("heures_prevues"))
        if heures and 0 < heures < journee:
            return round(heures / journee, 4)
    return 1.0


def colonne_de_l_arret(jour: Mapping[str, Any], iso: str, demandes: JoursDesDemandes) -> Optional[str]:
    """La colonne d'un jour porté en arrêt, ou None si le jour n'en est pas un.

    Seuls les jours que le calendrier porte en arrêt comptent : un week-end, un
    repos ou un férié marqué de l'arrêt n'est pas un jour d'absence, et tous
    les arrêts ne le marquent pas (comptage sinon inégal d'un arrêt à l'autre).
    """
    type_jour = str(jour.get("type") or "")
    if type_jour not in _TYPES_JOUR_ARRET:
        return None
    nature = demandes.nature_arret.get(iso)
    if nature:
        return nature
    arret_type = str(jour.get("arret_type") or "")
    if arret_type in NATURE_DU_TYPE_D_ARRET:
        return NATURE_DU_TYPE_D_ARRET[arret_type]
    if type_jour == "arret_at":
        return "arret_at"
    return "arret_non_precise"


def compter_jours_du_calendrier(
    planned_calendar: Any,
    debut: date,
    fin: date,
    *,
    annee: Optional[int] = None,
    mois: Optional[int] = None,
    demandes: Optional[JoursDesDemandes] = None,
) -> dict[str, float]:
    """Jours de congé et d'absence d'un mois de calendrier, bornés à la période.

    L'année et le mois sont ceux de la ligne (`employee_schedules.year/month`) ;
    `periode` du calendrier n'est qu'un repli : des mois écrits à la validation
    d'une absence n'en ont pas.
    """
    totaux = jours_a_zero()
    if not isinstance(planned_calendar, dict):
        return totaux
    jours = planned_calendar.get("calendrier_prevu")
    periode = planned_calendar.get("periode") or {}
    annee = annee if isinstance(annee, int) else periode.get("annee")
    mois = mois if isinstance(mois, int) else periode.get("mois")
    if not isinstance(jours, list) or not isinstance(annee, int) or not isinstance(mois, int):
        return totaux
    demandes = demandes or JoursDesDemandes()
    journee = journee_habituelle(jours)
    for jour in jours:
        if not isinstance(jour, dict) or not isinstance(jour.get("jour"), int):
            continue
        try:
            le_jour = date(annee, mois, jour["jour"])
        except ValueError:
            continue
        if not debut <= le_jour <= fin:
            continue
        iso = le_jour.isoformat()
        arret = colonne_de_l_arret(jour, iso, demandes)
        if arret:
            totaux[arret] += 1.0
            continue
        type_jour = str(jour.get("type") or "")
        if type_jour == "absence_non_remuneree":
            cle = (
                "parental_sans_solde"
                if est_jour_de_conge_parental(jour) or iso in demandes.sans_solde
                else "absence_non_payee"
            )
        elif type_jour == "conges_payes" and iso in demandes.recup_modulation:
            cle = "repos_recup"
        else:
            cle = _TYPE_VERS_COLONNE.get(type_jour)
        if cle:
            totaux[cle] += _part_de_journee(jour, journee, en_heures=type_jour in _TYPES_EN_HEURES)
    return totaux


def compter_jours_des_demandes(
    demandes: Iterable[Mapping[str, Any]], debut: date, fin: date
) -> dict[str, float]:
    """Jours des demandes validées qui n'écrivent pas le calendrier (JTC, repos seniors)."""
    totaux = jours_a_zero()
    for demande in demandes:
        cle = TYPES_DEMANDE_HORS_CALENDRIER.get(str(demande.get("type") or ""))
        if not cle:
            continue
        demi = demande.get("demi_journees") or {}
        for iso in _jours_iso(demande):
            try:
                le_jour = date.fromisoformat(iso)
            except ValueError:
                continue
            if debut <= le_jour <= fin:
                totaux[cle] += 0.5 if iso in demi else 1.0
    return totaux


def _arrondi(valeur: float) -> float:
    return round(valeur + 0.0, 2)


def est_present(employe: Mapping[str, Any]) -> bool:
    return str(employe.get("employment_status") or "") in STATUTS_PRESENTS


def construire_recap(
    *,
    debut: date,
    fin: date,
    employes: list[Mapping[str, Any]],
    calendriers: list[Mapping[str, Any]],
    demandes_validees: list[Mapping[str, Any]],
    soldes: Mapping[str, Mapping[str, float]],
    date_des_soldes: date,
    reprises: Optional[Mapping[str, Optional[date]]] = None,
) -> dict[str, Any]:
    """Une ligne par salarié : jours de la période par colonne et soldes CP.

    `employes` est déjà réduit au périmètre de l'utilisateur. Un salarié parti
    n'apparaît que s'il a au moins un jour sur la période.
    """
    reprises = reprises or {}
    demandes_par_salarie: dict[str, list[Mapping[str, Any]]] = {}
    for demande in demandes_validees:
        demandes_par_salarie.setdefault(str(demande.get("employee_id")), []).append(demande)
    calendriers_par_salarie: dict[str, list[Mapping[str, Any]]] = {}
    for ligne in calendriers:
        calendriers_par_salarie.setdefault(str(ligne.get("employee_id")), []).append(ligne)

    lignes: list[dict[str, Any]] = []
    totaux = jours_a_zero()
    for employe in employes:
        eid = str(employe.get("id"))
        demandes = demandes_par_salarie.get(eid, [])
        contexte = jours_des_demandes(demandes)
        jours = compter_jours_des_demandes(demandes, debut, fin)
        for ligne in calendriers_par_salarie.get(eid, []):
            mois = compter_jours_du_calendrier(
                ligne.get("planned_calendar"),
                debut,
                fin,
                annee=ligne.get("year"),
                mois=ligne.get("month"),
                demandes=contexte,
            )
            for cle, valeur in mois.items():
                jours[cle] += valeur
        total = sum(jours.values())
        if total <= 0 and not est_present(employe):
            continue
        solde = soldes.get(eid)
        reprise = reprises.get(eid)
        for cle, valeur in jours.items():
            totaux[cle] += valeur
        lignes.append(
            {
                "employee_id": eid,
                "matricule": employe.get("matricule"),
                "prenom": str(employe.get("first_name") or "").strip(),
                "nom": str(employe.get("nom_usage") or "").strip()
                or str(employe.get("last_name") or "").strip(),
                "jours": {cle: _arrondi(v) for cle, v in jours.items()},
                "total_jours": _arrondi(total),
                "solde_cp_n1": None if solde is None else _arrondi(float(solde["cp_n1"])),
                "solde_cp_n": None if solde is None else _arrondi(float(solde["cp_n"])),
                "reprise_au": reprise.isoformat() if reprise and reprise >= debut else None,
            }
        )
    lignes.sort(key=lambda l: (l["nom"].upper(), l["prenom"].upper()))
    return {
        "debut": debut.isoformat(),
        "fin": fin.isoformat(),
        "colonnes": [{"cle": c, "libelle": l, "source": s} for c, l, s in COLONNES],
        "source_soldes": SOURCE_SOLDES_CP,
        "note_arrets": NOTE_ARRETS,
        "note_reprise": NOTE_REPRISE,
        "date_des_soldes": date_des_soldes.isoformat(),
        "salaries": lignes,
        "totaux": {cle: _arrondi(v) for cle, v in totaux.items()},
        "aucun_jour": sum(totaux.values()) <= 0,
    }


def lignes_du_fichier(recap: Mapping[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    """En-têtes et lignes de la feuille Excel, avec une ligne de total."""
    colonnes = recap["colonnes"]
    entetes = ["Matricule", "Nom", "Prénom"]
    entetes += [f"{c['libelle']} (j)" for c in colonnes]
    entetes += ["Total des jours", "Solde CP N-1 (j)", "Solde CP N (j)", "Reprise dans Martine"]
    lignes: list[dict[str, Any]] = []
    for salarie in recap["salaries"]:
        ligne: dict[str, Any] = {
            "Matricule": salarie.get("matricule") or "",
            "Nom": salarie["nom"].upper(),
            "Prénom": salarie["prenom"],
            "Total des jours": salarie["total_jours"],
            "Solde CP N-1 (j)": "non calculé" if salarie["solde_cp_n1"] is None else salarie["solde_cp_n1"],
            "Solde CP N (j)": "non calculé" if salarie["solde_cp_n"] is None else salarie["solde_cp_n"],
            "Reprise dans Martine": salarie.get("reprise_au") or "",
        }
        for c in colonnes:
            ligne[f"{c['libelle']} (j)"] = salarie["jours"].get(c["cle"], 0.0)
        lignes.append(ligne)
    total: dict[str, Any] = {"Nom": "TOTAL"}
    for c in colonnes:
        total[f"{c['libelle']} (j)"] = recap["totaux"].get(c["cle"], 0.0)
    total["Total des jours"] = _arrondi(sum(recap["totaux"].values()))
    lignes.append(total)
    return entetes, lignes


__all__ = [
    "CLES_COLONNES",
    "COLONNES",
    "JoursDesDemandes",
    "NOTE_ARRETS",
    "NOTE_REPRISE",
    "SOURCE_SOLDES_CP",
    "STATUTS_PRESENTS",
    "colonne_de_l_arret",
    "compter_jours_des_demandes",
    "compter_jours_du_calendrier",
    "construire_recap",
    "est_present",
    "jours_des_demandes",
    "journee_habituelle",
    "lignes_du_fichier",
    "lire_periode",
    "mois_de_la_periode",
]
