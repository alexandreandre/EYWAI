"""Arrêts reportés : un arrêt arrivé après la paie de son mois passe sur le bulletin suivant.

Ce que fait Quadra chez LEWIS et Cartol, et le cabinet de Colorplast (retour
d'Elsa du 26/11/2026, bulletins de février à octobre 2026 relus) : l'arrêt est
compté sur le bulletin de la période qui le contient ; connu après que ce
bulletin est fait, il passe sur le bulletin suivant, avec ses vraies dates
(Cartol : « Absence maladie 230726-240726 » sur le bulletin d'août, rien en
juillet). Martine ne le faisait pas : un arrêt saisi après la validation du
bulletin de son mois n'était sur aucun bulletin.

Un jour d'arrêt est reporté sur le bulletin du mois M quand :
- le bulletin de la période précédente existe et est validé (il ne se
  régénère plus) ;
- ce bulletin ne l'a pas compté : sa trace (`arrets_du_bulletin`) ne le porte
  pas, aucune de ses retenues datées ne le couvre (« Absence maladie
  220926-230926 » d'un bulletin repris, « … du 01/10 au 30/10 » de Martine), et,
  sans trace, il a été calculé avant la saisie de l'arrêt ;
- la gestionnaire ne l'a pas déjà porté à la main : régularisation antérieure
  du même jour au planning du mois, ou heures normales de ce mois reprises
  depuis l'onglet « Corriger ».

Le report réutilise le mécanisme des régularisations antérieures
(`is_regularisation_anterieure`) : l'événement garde sa date d'origine, la
retenue et le maintien se calculent sur ses vraies dates, la DSN aussi.
Seule la période précédente est regardée : « le bulletin suivant ». Si le
bulletin suivant était déjà validé lui aussi, l'écran « Arrêts & IJ » dit de
le porter à la main.
"""

from __future__ import annotations

import calendar
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

#: Les arrêts indemnisés par la CPAM (mêmes types que le suivi des IJ).
TYPES_ARRET_REPORTABLES = frozenset(
    {
        "arret_maladie",
        "arret_at",
        "arret_paternite",
        "arret_maternite",
        "arret_maladie_pro",
    }
)

#: Clé de `payslip_data` : les jours d'arrêt que le bulletin compte, dont ceux
#: qu'il reporte d'un bulletin précédent.
CLE_TRACE = "arrets_du_bulletin"

#: Statut d'un bulletin qui ne se régénère plus sans forçage.
STATUT_VALIDE = "valide"


@dataclass(frozen=True)
class JourReporte:
    jour: date
    absence_id: str


# --- Ce qu'un bulletin a compté --------------------------------------------------

#: « 220926 » ou « 220926-230926 » (Quadra, Cegid).
_DATES_COMPACTES = re.compile(r"(?<!\d)(\d{2})(\d{2})(\d{2})(?:-(\d{2})(\d{2})(\d{2}))?(?!\d)")
#: « du 01/10 au 30/10 », « du 29/09/26 » (Martine).
_DATES_MARTINE = re.compile(
    r"du (\d{2})/(\d{2})(?:/(\d{2,4}))?(?: au (\d{2})/(\d{2})(?:/(\d{2,4}))?)?"
)


def _annee(texte: str | None, mois: int, annee_bulletin: int, mois_bulletin: int) -> int:
    if texte:
        valeur = int(texte)
        return valeur + 2000 if valeur < 100 else valeur
    # Sans année : celle du bulletin, ou la précédente pour un mois plus tardif
    # (décembre sur un bulletin de janvier).
    return annee_bulletin - 1 if mois > mois_bulletin else annee_bulletin


def _jours_entre(debut: date, fin: date) -> set[date]:
    if fin < debut or (fin - debut).days > 400:
        return {debut}
    return {debut + timedelta(days=k) for k in range((fin - debut).days + 1)}


def _date_sure(annee: int, mois: int, jour: int) -> date | None:
    try:
        return date(annee, mois, jour)
    except ValueError:
        return None


def jours_des_libelles(
    lignes: Iterable[Mapping[str, Any]] | None, annee: int, mois: int
) -> set[date]:
    """Les jours que couvrent les retenues datées d'un bulletin."""
    jours: set[date] = set()
    for ligne in lignes or []:
        if not isinstance(ligne, Mapping):
            continue
        try:
            perte = float(ligne.get("perte") or 0.0)
        except (TypeError, ValueError):
            perte = 0.0
        if perte <= 0:
            continue
        libelle = str(ligne.get("libelle") or "")
        for m in _DATES_COMPACTES.finditer(libelle):
            debut = _date_sure(2000 + int(m.group(3)), int(m.group(2)), int(m.group(1)))
            if debut is None:
                continue
            fin = (
                _date_sure(2000 + int(m.group(6)), int(m.group(5)), int(m.group(4)))
                if m.group(4)
                else debut
            )
            jours |= _jours_entre(debut, fin or debut)
        for m in _DATES_MARTINE.finditer(libelle):
            mois_debut = int(m.group(2))
            debut = _date_sure(
                _annee(m.group(3), mois_debut, annee, mois), mois_debut, int(m.group(1))
            )
            if debut is None:
                continue
            fin = debut
            if m.group(4):
                mois_fin = int(m.group(5))
                fin = _date_sure(
                    _annee(m.group(6), mois_fin, annee, mois), mois_fin, int(m.group(4))
                ) or debut
            jours |= _jours_entre(debut, fin)
    return jours


def trace_du_bulletin(payslip_data: Mapping[str, Any] | None) -> dict[str, Any] | None:
    trace = (payslip_data or {}).get(CLE_TRACE)
    return trace if isinstance(trace, Mapping) else None


def jours_reportes_par_le_bulletin(payslip_data: Mapping[str, Any] | None) -> set[date]:
    """Les jours d'une période précédente que ce bulletin a repris."""
    trace = trace_du_bulletin(payslip_data) or {}
    jours: set[date] = set()
    for entree in trace.get("reportes") or []:
        try:
            jours.add(date.fromisoformat(str(entree.get("date"))[:10]))
        except (AttributeError, ValueError):
            continue
    return jours


def jours_comptes_par_le_bulletin(
    bulletin: Mapping[str, Any], annee: int, mois: int
) -> set[date]:
    """Les jours d'absence qu'un bulletin a retenus : sa trace, ou ses libellés."""
    donnees = bulletin.get("payslip_data") or {}
    trace = trace_du_bulletin(donnees)
    if trace is not None:
        jours: set[date] = set()
        for iso in trace.get("jours_comptes") or []:
            try:
                jours.add(date.fromisoformat(str(iso)[:10]))
            except ValueError:
                continue
        return jours | jours_reportes_par_le_bulletin(donnees)
    lignes = list(donnees.get("calcul_du_brut") or []) + list(
        donnees.get("details_absences") or []
    )
    return jours_des_libelles(lignes, annee, mois)


def _instant(valeur: Any) -> datetime | None:
    if isinstance(valeur, datetime):
        moment = valeur
    elif isinstance(valeur, str) and valeur.strip():
        try:
            moment = datetime.fromisoformat(valeur.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _calcule_apres(bulletin: Mapping[str, Any], instant: Any) -> bool:
    """Le bulletin a été calculé après l'instant donné : il a lu l'arrêt."""
    calcule = _instant(bulletin.get("generated_at") or bulletin.get("updated_at"))
    reference = _instant(instant)
    return calcule is not None and reference is not None and calcule >= reference


def _est_une_reprise(bulletin: Mapping[str, Any]) -> bool:
    return isinstance((bulletin.get("payslip_data") or {}).get("reprise"), Mapping)


# --- Le choix des jours ------------------------------------------------------------


def mois_repris_a_la_main(
    regularisations_heures: Iterable[Mapping[str, Any]] | None, annee: int, mois: int
) -> bool:
    """Des heures normales de ce mois déjà reprises sur le bulletin (onglet « Corriger »)."""
    cle = f"{annee:04d}-{mois:02d}"
    for regul in regularisations_heures or []:
        if not isinstance(regul, Mapping) or regul.get("nature") != "normales":
            continue
        try:
            quantite = float(regul.get("quantite") or 0.0)
        except (TypeError, ValueError):
            continue
        debut = str(regul.get("mois_origine") or "")
        fin = str(regul.get("mois_fin") or debut)
        if quantite < 0 and debut <= cle <= fin:
            return True
    return False


def dates_des_regularisations_manuelles(planned_calendar: Mapping[str, Any] | None) -> set[date]:
    """Les jours d'arrêt déjà portés à la main au planning du mois."""
    jours: set[date] = set()
    for entree in (planned_calendar or {}).get("regularisations_anterieures") or []:
        if not isinstance(entree, Mapping) or not str(entree.get("type") or "").startswith("arret"):
            continue
        try:
            jours.add(date.fromisoformat(str(entree.get("date_complete"))[:10]))
        except ValueError:
            continue
    return jours


def jours_a_reporter(
    arrets: Iterable[Mapping[str, Any]],
    bulletins_origine: list[Mapping[str, Any]],
    periode_origine: tuple[date, date],
    *,
    annee_origine: int,
    mois_origine: int,
    deja_portes: set[date] | None = None,
    repris_a_la_main: bool = False,
) -> list[JourReporte]:
    """Les jours d'arrêt de la période précédente que son bulletin n'a pas comptés."""
    if not bulletins_origine or repris_a_la_main:
        return []
    if any(b.get("status") != STATUT_VALIDE for b in bulletins_origine):
        return []
    debut, fin = periode_origine
    comptes: set[date] = set()
    for b in bulletins_origine:
        comptes |= jours_comptes_par_le_bulletin(b, annee_origine, mois_origine)
    avec_trace = any(
        trace_du_bulletin(b.get("payslip_data")) is not None for b in bulletins_origine
    )
    reprise = all(_est_une_reprise(b) for b in bulletins_origine)
    choisis: dict[date, JourReporte] = {}
    for arret in arrets:
        jours_de_l_arret: list[date] = []
        if arret.get("type") not in TYPES_ARRET_REPORTABLES:
            continue
        if arret.get("status", "validated") != "validated":
            continue
        # Sans trace ni libellé, un bulletin de Martine calculé après la saisie
        # de l'arrêt l'a lu au planning : il l'a compté.
        if not avec_trace and not reprise and any(
            _calcule_apres(b, arret.get("created_at")) for b in bulletins_origine
        ):
            continue
        for brut in arret.get("selected_days") or []:
            try:
                jour = date.fromisoformat(str(brut)[:10])
            except ValueError:
                continue
            if not (debut <= jour <= fin) or jour in comptes:
                continue
            if deja_portes and jour in deja_portes:
                continue
            jours_de_l_arret.append(jour)
        # Seulement un week-end non compté (bord d'un arrêt que le bulletin a
        # retenu jusqu'au vendredi) : rien à reprendre, ni retenue ni IJ.
        if not any(j.weekday() < 5 for j in jours_de_l_arret):
            continue
        for jour in jours_de_l_arret:
            choisis.setdefault(jour, JourReporte(jour, str(arret.get("id") or "")))
    return [choisis[j] for j in sorted(choisis)]


def evenements_du_report(
    evenements_origine: Iterable[Mapping[str, Any]],
    jours: Iterable[JourReporte],
    annee: int,
    mois: int,
) -> list[dict[str, Any]]:
    """Les événements d'arrêt de la période précédente, rattachés au bulletin du mois.

    Ils gardent leur date d'origine (`is_regularisation_anterieure`) et disent
    de quel arrêt ils viennent (`arret_reporte`, `absence_id`). L'analyse d'un
    mois ne date ses jours que par leur numéro : `annee`, `mois` complètent."""
    par_date = {j.jour: j for j in jours}
    if not par_date:
        return []
    reportes: list[dict[str, Any]] = []
    for ev in evenements_origine:
        if not str(ev.get("type") or "").startswith("arret"):
            continue
        jour = _date_de_l_evenement(ev, annee, mois)
        if jour is None or jour not in par_date:
            continue
        reportes.append(
            {
                **ev,
                "annee": jour.year,
                "mois": jour.month,
                "jour": jour.day,
                "date_complete": jour.isoformat(),
                "is_regularisation_anterieure": True,
                "arret_reporte": True,
                "absence_id": par_date[jour].absence_id,
            }
        )
    return reportes


def _date_de_l_evenement(ev: Mapping[str, Any], annee: int, mois: int) -> date | None:
    if ev.get("date_complete"):
        try:
            return date.fromisoformat(str(ev["date_complete"])[:10])
        except ValueError:
            return None
    try:
        return date(int(ev.get("annee") or annee), int(ev.get("mois") or mois), int(ev["jour"]))
    except (KeyError, TypeError, ValueError):
        return None


def sans_les_jours_deja_reportes(
    evenements: list[dict[str, Any]], jours: set[date], annee: int, mois: int
) -> list[dict[str, Any]]:
    """Le bulletin d'origine régénéré ne recompte pas ce que le suivant a repris."""
    if not jours:
        return evenements
    return [
        ev
        for ev in evenements
        if not (
            str(ev.get("type") or "").startswith("arret")
            and not ev.get("is_regularisation_anterieure")
            and _date_de_l_evenement(ev, annee, mois) in jours
        )
    ]


def periode_precedente(
    annee: int,
    mois: int,
    *,
    forfait_jours: bool,
    jour_de_fin: Any = None,
    occurrence: Any = None,
) -> tuple[int, int, tuple[date, date]]:
    """(année, mois, bornes) de la période du bulletin précédent : le mois civil
    aux heures, la période de la société au forfait jours."""
    annee_o, mois_o = (annee, mois - 1) if mois > 1 else (annee - 1, 12)
    if forfait_jours:
        from app.modules.payroll.engine.period_forfait import bornes_periode_de_paie

        bornes = bornes_periode_de_paie(
            annee_o,
            mois_o,
            jour_de_fin if jour_de_fin is not None else 4,
            occurrence if occurrence is not None else -2,
        )
        return annee_o, mois_o, bornes
    from app.shared.domain.periode_variables import bornes_mois_civil

    return annee_o, mois_o, bornes_mois_civil(annee_o, mois_o)


# --- Lectures ------------------------------------------------------------------------

_COLONNES_BULLETIN = "id, year, month, status, generated_at, updated_at, payslip_data"


def lire_les_arrets(client: Any, employee_id: str) -> list[dict[str, Any]]:
    lignes = (
        client.table("absence_requests")
        .select("id, type, status, selected_days, created_at")
        .eq("employee_id", employee_id)
        .eq("status", "validated")
        .execute()
    ).data or []
    # Tri en Python : un filtre SQL sur l'enum échoue dès qu'un type manque.
    return [l for l in lignes if l.get("type") in TYPES_ARRET_REPORTABLES]


def lire_les_bulletins(client: Any, employee_id: str, annee: int, mois: int) -> list[dict[str, Any]]:
    return (
        client.table("payslips")
        .select(_COLONNES_BULLETIN)
        .eq("employee_id", employee_id)
        .eq("year", annee)
        .eq("month", mois)
        .execute()
    ).data or []


#: Clés des saisies du mois : le générateur du forfait jours passe le report
#: au moteur, qui analyse lui-même ses jours.
CLE_SAISIE_REPORT = "arrets_reportes"
CLE_SAISIE_REPRIS = "jours_repris_par_le_bulletin_suivant"


@dataclass(frozen=True)
class Report:
    """Ce que le bulletin du mois reprend du précédent, et ce que le suivant lui a pris."""

    jours: tuple[JourReporte, ...] = ()
    repris: frozenset[date] = frozenset()

    def vers_les_saisies(self) -> dict[str, Any]:
        return {
            CLE_SAISIE_REPORT: [
                {"date": j.jour.isoformat(), "absence_id": j.absence_id} for j in self.jours
            ],
            CLE_SAISIE_REPRIS: sorted(d.isoformat() for d in self.repris),
        }

    @classmethod
    def depuis_les_saisies(cls, saisie: Mapping[str, Any] | None) -> Report:
        saisie = saisie or {}
        jours = []
        for entree in saisie.get(CLE_SAISIE_REPORT) or []:
            try:
                jours.append(
                    JourReporte(date.fromisoformat(str(entree["date"])[:10]), str(entree.get("absence_id") or ""))
                )
            except (KeyError, TypeError, ValueError):
                continue
        repris = set()
        for iso in saisie.get(CLE_SAISIE_REPRIS) or []:
            try:
                repris.add(date.fromisoformat(str(iso)[:10]))
            except ValueError:
                continue
        return cls(tuple(jours), frozenset(repris))


def _touche(arrets: list[dict[str, Any]], debut: date, fin: date) -> bool:
    for a in arrets:
        for d in a.get("selected_days") or []:
            try:
                if debut <= date.fromisoformat(str(d)[:10]) <= fin:
                    return True
            except ValueError:
                continue
    return False


def preparer_le_report(
    client: Any,
    employee_id: str,
    annee: int,
    mois: int,
    *,
    forfait_jours: bool,
    company_data: Mapping[str, Any] | None,
    planned_calendar_du_mois: Mapping[str, Any] | None = None,
    saisies: Iterable[Mapping[str, Any]] | None = None,
) -> Report:
    """Les arrêts à reprendre du bulletin précédent, et les jours de ce mois que
    le bulletin suivant a déjà repris. Les bulletins ne se lisent que si le
    salarié a un arrêt sur l'une des deux périodes."""
    from app.modules.payroll.engine.corrections_manuelles import (
        est_regularisation_heures,
    )

    arrets = lire_les_arrets(client, employee_id)
    if not arrets:
        return Report()
    societe = company_data or {}
    annee_o, mois_o, bornes = periode_precedente(
        annee,
        mois,
        forfait_jours=forfait_jours,
        jour_de_fin=societe.get("paie_jour_de_fin"),
        occurrence=societe.get("paie_occurrence"),
    )
    jours: list[JourReporte] = []
    if _touche(arrets, *bornes):
        jours = jours_a_reporter(
            arrets,
            lire_les_bulletins(client, employee_id, annee_o, mois_o),
            bornes,
            annee_origine=annee_o,
            mois_origine=mois_o,
            deja_portes=dates_des_regularisations_manuelles(planned_calendar_du_mois),
            repris_a_la_main=mois_repris_a_la_main(
                [s["correction_ligne"] for s in saisies or [] if est_regularisation_heures(s)],
                annee_o,
                mois_o,
            ),
        )
    repris: set[date] = set()
    # Période du mois : le jour après la fin de la précédente, jusqu'à la veille de la suivante.
    debut_du_mois = bornes[1] + timedelta(days=1)
    fin_du_mois = date(annee, mois, calendar.monthrange(annee, mois)[1])
    if _touche(arrets, debut_du_mois, fin_du_mois):
        annee_s, mois_s = (annee, mois + 1) if mois < 12 else (annee + 1, 1)
        for b in lire_les_bulletins(client, employee_id, annee_s, mois_s):
            repris |= jours_reportes_par_le_bulletin(b.get("payslip_data"))
    return Report(tuple(jours), frozenset(repris))


def appliquer_le_report_aux_evenements(
    evenements_du_mois: list[dict[str, Any]],
    evenements_precedents: Iterable[Mapping[str, Any]],
    report: Report,
    annee: int,
    mois: int,
) -> list[dict[str, Any]]:
    """Les événements du mois sans les jours que le bulletin suivant a repris,
    plus les jours d'arrêt reportés du bulletin précédent (à leur date)."""
    annee_o, mois_o = (annee, mois - 1) if mois > 1 else (annee - 1, 12)
    evenements = sans_les_jours_deja_reportes(list(evenements_du_mois), set(report.repris), annee, mois)
    if not report.jours:
        return evenements
    return evenements + evenements_du_report(evenements_precedents, report.jours, annee_o, mois_o)


__all__ = [
    "CLE_SAISIE_REPORT",
    "CLE_SAISIE_REPRIS",
    "CLE_TRACE",
    "TYPES_ARRET_REPORTABLES",
    "JourReporte",
    "Report",
    "appliquer_le_report_aux_evenements",
    "dates_des_regularisations_manuelles",
    "evenements_du_report",
    "jours_a_reporter",
    "jours_comptes_par_le_bulletin",
    "jours_des_libelles",
    "jours_reportes_par_le_bulletin",
    "mois_repris_a_la_main",
    "periode_precedente",
    "preparer_le_report",
    "sans_les_jours_deja_reportes",
]
