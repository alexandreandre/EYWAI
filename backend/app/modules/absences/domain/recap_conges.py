"""Récapitulatif des congés et absences d'une société sur une période (lot L21).

Demande de la gestionnaire (27/11/2026) : voir les congés pris de tous les
salariés sans ouvrir la fiche de chacun. Domaine pur : les jours sont comptés
sur le calendrier de paie (`employee_schedules.planned_calendar`), là où sont
posés congés payés, RTT, absences et arrêts, et sur les demandes validées pour
les seuls congés qui n'écrivent pas le calendrier (JTC, repos seniors). Rien
n'est recalculé d'une autre façon que ce que le bulletin lit.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Mapping, Optional

from app.modules.absences.domain.nature_arret import NATURE_DU_TYPE_D_ARRET
from app.shared.domain.conge_parental import est_jour_de_conge_parental

#: Colonnes de jours, dans l'ordre de l'écran et du fichier : (clé, libellé, source).
COLONNES: tuple[tuple[str, str, str], ...] = (
    ("cp", "Congés payés", "Calendrier : jours « Congés payés » (demi-journée = 0,5)"),
    ("rtt", "RTT", "Calendrier : jours « RTT » (demi-journée = 0,5)"),
    (
        "jtc_repos_seniors",
        "JTC / repos seniors",
        "Demandes validées JTC et repos seniors (elles n'écrivent pas le calendrier)",
    ),
    (
        "repos_recup",
        "Repos compensateur / récup.",
        "Calendrier : jours « Congé » (repos compensateur, anciens congés hors paie)",
    ),
    (
        "absence_non_payee",
        "Absences non payées",
        "Calendrier : jours « Absence non rémunérée » hors congé sans solde et congé parental",
    ),
    (
        "parental_sans_solde",
        "Congé parental / sans solde",
        "Calendrier : jours « Absence non rémunérée » d'un congé sans solde validé ou d'un congé parental",
    ),
    (
        "arret_maladie",
        "Arrêt maladie",
        "Calendrier : jours « Arrêt maladie » de nature maladie (ALD, mi-temps thérapeutique compris)",
    ),
    (
        "arret_at",
        "Accident du travail / trajet",
        "Calendrier : jours d'arrêt de nature accident du travail, de trajet ou rechute",
    ),
    (
        "arret_maladie_pro",
        "Maladie professionnelle",
        "Calendrier : jours d'arrêt de nature maladie professionnelle",
    ),
    (
        "arret_maternite",
        "Congé maternité",
        "Calendrier : jours d'arrêt de nature maternité",
    ),
    (
        "arret_paternite",
        "Congé paternité",
        "Calendrier : jours d'arrêt de nature paternité",
    ),
    ("evenement_familial", "Événement familial", "Calendrier : jours « Événement familial »"),
    ("absence_justifiee", "Absence justifiée", "Calendrier : jours « Absence justifiée »"),
    ("activite_partielle", "Activité partielle", "Calendrier : jours « Activité partielle »"),
)

CLES_COLONNES: tuple[str, ...] = tuple(c[0] for c in COLONNES)

SOURCE_SOLDES_CP = (
    "Soldes CP N-1 et N à la date du jour : même calcul que « Entreprise, onglet Paie, "
    "Congés & RTT » et l'onglet Soldes de la fiche salarié"
)

#: Ce que la colonne d'arrêt compte, dit à l'écran et dans le fichier.
NOTE_ARRETS = (
    "Arrêts : jours que le calendrier porte en arrêt (le salarié aurait travaillé) ; "
    "les week-ends et repos couverts par l'arrêt ne sont pas comptés. Dates et IJ : « Arrêts & IJ »."
)

#: Type de jour du calendrier -> colonne (les arrêts et l'absence non rémunérée à part).
_TYPE_VERS_COLONNE: dict[str, str] = {
    "conges_payes": "cp",
    "rtt": "rtt",
    "conge": "repos_recup",
    "evenement_familial": "evenement_familial",
    "absence_justifiee": "absence_justifiee",
    "activite_partielle": "activite_partielle",
}

_TYPES_JOUR_ARRET = {"arret_maladie": "arret_maladie", "arret_at": "arret_at"}

#: Demandes validées comptées hors calendrier (elles ne l'écrivent jamais).
TYPES_DEMANDE_HORS_CALENDRIER = {"jtc": "jtc_repos_seniors", "repos_senior": "jtc_repos_seniors"}

#: Plus longue période acceptée (une année et un jour).
DUREE_MAX_JOURS = 366


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


def _quotite(jour: Mapping[str, Any]) -> float:
    """Part de journée d'absence : 0,5 pour une demi-journée, 1 sinon."""
    brut = jour.get("quotite_absence")
    try:
        valeur = float(brut) if brut is not None else 1.0
    except (TypeError, ValueError):
        return 1.0
    return valeur if 0 < valeur <= 1 else 1.0


def colonne_de_l_arret(jour: Mapping[str, Any]) -> Optional[str]:
    """La colonne d'un jour d'arrêt (par sa nature), ou None si le jour n'en porte pas."""
    type_jour = str(jour.get("type") or "")
    arret_type = jour.get("arret_type")
    # Seuls les jours que le calendrier porte en arrêt comptent : un week-end,
    # un repos ou un férié marqué de l'arrêt n'est pas un jour d'absence, et
    # tous les arrêts ne le marquent pas (comptage sinon inégal d'un arrêt à l'autre).
    if type_jour not in _TYPES_JOUR_ARRET:
        return None
    if arret_type and str(arret_type) in NATURE_DU_TYPE_D_ARRET:
        return NATURE_DU_TYPE_D_ARRET[str(arret_type)]
    return _TYPES_JOUR_ARRET.get(type_jour, "arret_maladie")


def compter_jours_du_calendrier(
    planned_calendar: Any,
    debut: date,
    fin: date,
    jours_sans_solde: Iterable[str] = (),
) -> dict[str, float]:
    """Jours de congé et d'absence d'un mois de calendrier, bornés à la période."""
    totaux = jours_a_zero()
    if not isinstance(planned_calendar, dict):
        return totaux
    jours = planned_calendar.get("calendrier_prevu")
    periode = planned_calendar.get("periode") or {}
    annee, mois = periode.get("annee"), periode.get("mois")
    if not isinstance(jours, list) or not isinstance(annee, int) or not isinstance(mois, int):
        return totaux
    sans_solde = {str(j)[:10] for j in jours_sans_solde}
    for jour in jours:
        if not isinstance(jour, dict) or not isinstance(jour.get("jour"), int):
            continue
        try:
            le_jour = date(annee, mois, jour["jour"])
        except ValueError:
            continue
        if not debut <= le_jour <= fin:
            continue
        arret = colonne_de_l_arret(jour)
        if arret:
            totaux[arret] += 1.0
            continue
        type_jour = str(jour.get("type") or "")
        if type_jour == "absence_non_remuneree":
            cle = (
                "parental_sans_solde"
                if est_jour_de_conge_parental(jour) or le_jour.isoformat() in sans_solde
                else "absence_non_payee"
            )
            totaux[cle] += _quotite(jour)
            continue
        cle = _TYPE_VERS_COLONNE.get(type_jour)
        if cle:
            totaux[cle] += _quotite(jour)
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
        for jour in demande.get("selected_days") or []:
            iso = str(jour)[:10]
            try:
                le_jour = date.fromisoformat(iso)
            except ValueError:
                continue
            if debut <= le_jour <= fin:
                totaux[cle] += 0.5 if iso in demi else 1.0
    return totaux


def jours_sans_solde_valides(demandes: Iterable[Mapping[str, Any]]) -> set[str]:
    """Les dates des congés sans solde validés (congé parental compris)."""
    dates: set[str] = set()
    for demande in demandes:
        if demande.get("type") == "sans_solde":
            dates.update(str(j)[:10] for j in demande.get("selected_days") or [])
    return dates


def _arrondi(valeur: float) -> float:
    return round(valeur + 0.0, 2)


def construire_recap(
    *,
    debut: date,
    fin: date,
    employes: list[Mapping[str, Any]],
    calendriers: list[Mapping[str, Any]],
    demandes_validees: list[Mapping[str, Any]],
    soldes: Mapping[str, Mapping[str, float]],
    date_des_soldes: date,
) -> dict[str, Any]:
    """Une ligne par salarié : jours de la période par colonne et soldes CP.

    `employes` est déjà réduit au périmètre de l'utilisateur. Un salarié sorti
    n'apparaît que s'il a au moins un jour sur la période.
    """
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
        sans_solde = jours_sans_solde_valides(demandes)
        jours = compter_jours_des_demandes(demandes, debut, fin)
        for ligne in calendriers_par_salarie.get(eid, []):
            mois = compter_jours_du_calendrier(ligne.get("planned_calendar"), debut, fin, sans_solde)
            for cle, valeur in mois.items():
                jours[cle] += valeur
        total = sum(jours.values())
        actif = str(employe.get("employment_status") or "") in ("actif", "active", "en_onboarding")
        if total <= 0 and not actif:
            continue
        solde = soldes.get(eid)
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
            }
        )
    lignes.sort(key=lambda l: (l["nom"].upper(), l["prenom"].upper()))
    return {
        "debut": debut.isoformat(),
        "fin": fin.isoformat(),
        "colonnes": [{"cle": c, "libelle": l, "source": s} for c, l, s in COLONNES],
        "source_soldes": SOURCE_SOLDES_CP,
        "note_arrets": NOTE_ARRETS,
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
    entetes += ["Total des jours", "Solde CP N-1 (j)", "Solde CP N (j)"]
    lignes: list[dict[str, Any]] = []
    for salarie in recap["salaries"]:
        ligne: dict[str, Any] = {
            "Matricule": salarie.get("matricule") or "",
            "Nom": salarie["nom"].upper(),
            "Prénom": salarie["prenom"],
            "Total des jours": salarie["total_jours"],
            "Solde CP N-1 (j)": "" if salarie["solde_cp_n1"] is None else salarie["solde_cp_n1"],
            "Solde CP N (j)": "" if salarie["solde_cp_n"] is None else salarie["solde_cp_n"],
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
    "NOTE_ARRETS",
    "SOURCE_SOLDES_CP",
    "colonne_de_l_arret",
    "compter_jours_des_demandes",
    "compter_jours_du_calendrier",
    "construire_recap",
    "jours_sans_solde_valides",
    "lignes_du_fichier",
    "lire_periode",
    "mois_de_la_periode",
]
