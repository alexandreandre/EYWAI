"""Le bulletin qui reprend un arrêt du bulletin précédent : maintien, IJ, trace.

Les jours reportés arrivent au calendrier du mois marqués `arret_reporte`
(`application/arrets_reportes.py`). La retenue se fait comme pour tout jour
d'arrêt (régularisation antérieure, à ses dates). Le maintien et les IJ se
calculent arrêt par arrêt, sur les seuls jours reportés, avec la même
préparation que l'arrêt du mois (arrêts connus pour la prolongation et les
jours légaux sur douze mois, carence payée, salaires de référence, IJ saisies,
maintien en jours ouvrés, sortie) : l'arrêt garde son vrai début, donc sa
carence et le rang de ses jours.

Chaque arrêt reporté a son bloc (`arrets_reportes` du bulletin) et ses lignes :
le bloc du mois (`bloc_maintien`, la synthèse des IJ) reste celui des arrêts du
mois, que le suivi des IJ rapproche.

Défaut A11 (jours de maintien relus par leur numéro dans le mois) : les jours
reportés n'entrent jamais dans `jours_maintien` (numéros du mois courant, tirés
du seul arrêt du mois). Le 29/09 reporté ne se confond pas avec le 29/10.

Pour les deux générateurs, heures et forfait jours.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from app.modules.payroll.application.arrets_reportes import CLE_TRACE, Report

logger = logging.getLogger(__name__)

#: Clé du bulletin : un bloc par arrêt reporté.
CLE_ARRETS_REPORTES = "arrets_reportes"


#: Bulletin d'origine régénéré dont l'arrêt a été repris en partie, au milieu,
#: par le bulletin suivant (`arrets_reportes.sans_les_jours_deja_reportes`).
MESSAGE_REPORT_PARTIEL = (
    "Arrêt de travail repris en partie par le bulletin suivant (jours au milieu de "
    "l'arrêt) : les jours repris ne sont plus retenus ici, mais le maintien et les "
    "IJ de cet arrêt sont à vérifier sur ce bulletin et à corriger à la main au besoin."
)


def _jour(ev: dict[str, Any]) -> date | None:
    try:
        return date.fromisoformat(str(ev.get("date_complete"))[:10])
    except ValueError:
        return None


def jours_reportes_du_calendrier(calendrier: list[dict[str, Any]]) -> list[tuple[date, dict[str, Any]]]:
    jours = []
    for ev in calendrier or []:
        if not ev.get("arret_reporte"):
            continue
        d = _jour(ev)
        if d is not None:
            jours.append((d, ev))
    return sorted(jours, key=lambda x: x[0])


def libelle_des_jours(jours: list[date]) -> str:
    """« du 29/09/26 » ou « du 28/09/26 au 30/09/26 »."""
    if not jours:
        return ""
    debut, fin = min(jours), max(jours)
    if debut == fin:
        return f"du {debut:%d/%m/%y}"
    return f"du {debut:%d/%m/%y} au {fin:%d/%m/%y}"


def _mois_civil(jour: date) -> tuple[date, date]:
    from app.shared.domain.periode_variables import bornes_mois_civil

    return bornes_mois_civil(jour.year, jour.month)


def _periodes_d_origine(jours: list[date], contexte: Any, year: int, month: int) -> list[tuple[date, date]]:
    """Le mois civil des jours reportés, et au forfait jours la période de paie
    du bulletin précédent (24/08 au 20/09 pour septembre)."""
    periodes = [_mois_civil(min(jours))]
    try:
        from app.modules.payroll.engine.maintien_salaire_service import (
            _contexte_is_forfait_jours,
        )

        if contexte is not None and _contexte_is_forfait_jours(contexte):
            from app.modules.payroll.engine.period_forfait import (
                definir_periode_de_paie,
            )

            annee_o, mois_o = (year, month - 1) if month > 1 else (year - 1, 12)
            periodes.append(tuple(definir_periode_de_paie(contexte, annee_o, mois_o)))
    except Exception:
        logger.warning("Période d'origine du forfait non lue : mois civil seul", exc_info=True)
    return periodes


def _bornes_du_report(
    jours: list[date], periodes: list[tuple[date, date]] | None = None
) -> tuple[tuple[date, date], bool]:
    """Les jours calendaires reportés (week-ends compris) ; toute la période
    d'origine s'ils en couvrent tous les jours ouvrés. Dit si elle est entière."""
    for debut, fin in periodes or [_mois_civil(min(jours))]:
        ouvres = {
            debut + timedelta(days=k)
            for k in range((fin - debut).days + 1)
            if (debut + timedelta(days=k)).weekday() < 5
        }
        if ouvres and ouvres <= set(jours):
            return (debut, fin), True
    return (min(jours), max(jours)), False


def _date_contrat(contexte: Any, cle: str) -> date | None:
    from app.modules.payroll.application.planning_apres_sortie import date_de_sortie

    return date_de_sortie(((contexte.contrat or {}).get("contrat") or {}).get(cle))


def jours_reportes_sous_contrat(
    calendrier: list[dict[str, Any]], contexte: Any
) -> list[tuple[date, dict[str, Any]]]:
    """Les jours reportés que le contrat de ce bulletin couvre.

    Un jour antérieur à l'entrée appartient au contrat d'avant (deux contrats
    le même mois, D3) : ni retenue, ni maintien, ni IJ sur celui-ci."""
    entree = _date_contrat(contexte, "date_entree")
    sortie = _date_contrat(contexte, "date_sortie")
    return [
        (d, ev)
        for d, ev in jours_reportes_du_calendrier(calendrier)
        if (entree is None or d >= entree) and (sortie is None or d <= sortie)
    ]


@dataclass
class BlocReporte:
    absence_id: str
    jours: list[date]
    resultat: dict[str, Any]


def maintien_des_arrets_reportes(
    calendrier: list[dict[str, Any]],
    contexte: Any,
    *,
    company_id: str | None,
    employee_id: str | None,
    year: int,
    month: int,
    saisie_du_mois: dict[str, Any] | None,
    avec_arret_du_mois: bool,
) -> list[BlocReporte]:
    """Maintien et IJ des jours reportés, arrêt par arrêt, sur leurs seules dates."""
    candidats = [(d, ev) for d, ev in jours_reportes_sous_contrat(calendrier, contexte) if ev.get("arret_type")]
    if not candidats or not company_id:
        return []
    from app.modules.maintenance_settings.application.queries import (
        get_maintenance_settings,
    )
    from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien
    from app.modules.payroll.infrastructure.salaires_de_reference import (
        poser_salaires_de_reference,
    )

    from .payslip_run_heures import (
        _arret_de_jours_candidats,
        _regrouper_par_arret,
        arrets_de_l_annee,
        noter_l_arret_apres_la_sortie,
        poser_les_arrets_connus,
    )

    saisie = saisie_du_mois or {}
    settings = get_maintenance_settings(company_id).model_dump(mode="json")
    sortie = _date_contrat(contexte, "date_sortie")
    groupes = _regrouper_par_arret(candidats)
    override = saisie.get("ijss_brut_override")
    blocs: list[BlocReporte] = []
    for groupe in groupes:
        arret = _arret_de_jours_candidats(groupe, contexte, sortie)
        jours = [d for d, _ in groupe]
        (debut, fin), entiere = _bornes_du_report(jours, _periodes_d_origine(jours, contexte, year, month))
        # La période du calcul est celle des jours reportés : le moteur la
        # verrait sinon « entièrement en arrêt » et maintiendrait le salaire
        # du mois pour un seul jour. La période d'origine entière (mois civil,
        # ou période du forfait) reste reconnue.
        arret["mois_entier_en_arret"] = entiere
        # Mêmes données que l'arrêt du mois : la chaîne des arrêts connus
        # (prolongation, jours légaux sur douze mois D1226-4, barème), la
        # carence payée, les salaires de référence, la saisie du mois.
        poser_les_arrets_connus(arret, company_id, employee_id, year, month)
        if settings.get("paid_waiting_days_per_year") and employee_id:
            arret["arrets_annee"] = arrets_de_l_annee(str(employee_id), year, month)
        if saisie.get("maintien_base_ouvree"):
            arret["maintien_base_ouvree"] = True
            arret["ijss_releve_du_bulletin"] = True
        # IJ saisies pour le mois : sans arrêt du mois, elles sont celles de
        # l'arrêt reporté ; avec un arrêt du mois, elles lui reviennent et
        # l'estimation de l'arrêt reporté ne s'y ajoute pas (dit plus bas).
        # Plusieurs arrêts reportés sans arrêt du mois : la saisie va au premier,
        # les autres ne reçoivent pas d'estimation en plus.
        ij_saisies_ailleurs = override is not None and (avec_arret_du_mois or bool(blocs))
        if override is not None and not ij_saisies_ailleurs:
            arret["ijss_brut_override"] = override
        poser_salaires_de_reference(arret, employee_id)
        resultat = calculer_maintien(arret, contexte, settings, debut, fin)
        noter_l_arret_apres_la_sortie(arret, resultat)
        if ij_saisies_ailleurs:
            resultat = _sans_ij_estimees(
                resultat,
                jours,
                "celui de l'arrêt du mois" if avec_arret_du_mois else f"celui de l'arrêt reporté {libelle_des_jours(blocs[0].jours)}",
            )
        absence_id = next((str(ev.get("absence_id") or "") for _, ev in groupe if ev.get("absence_id")), "")
        blocs.append(BlocReporte(absence_id, jours, resultat))
    return blocs


def _sans_ij_estimees(resultat: dict[str, Any], jours: list[date], attribue_a: str) -> dict[str, Any]:
    """IJ saisies pour le mois : l'estimation de l'arrêt reporté ne s'y ajoute jamais."""
    resultat = copy.deepcopy(resultat)
    ijss = resultat.setdefault("ijss", {})
    estimees = float(ijss.get("ijss_theorique") or 0.0)
    ijss["ijss_theorique"] = 0.0
    ijss["ijss_estimees_non_versees"] = round(estimees, 2)
    if estimees > 0:
        resultat.setdefault("alertes", []).append(
            f"IJ de l'arrêt reporté {libelle_des_jours(jours)} ({estimees:.2f} € estimés) non versées : "
            f"le montant d'IJ saisi pour le mois est {attribue_a}. "
            "Si la CPAM les a payées avec, ajoutez-les à la saisie."
        )
    return resultat


@dataclass
class EffetDuReport:
    lignes_csg_ijss: list[dict[str, Any]]
    ijss_imposables: list[dict[str, Any]]
    brut_modifie: bool = False
    maintien_verse: float = 0.0
    blocs: list[BlocReporte] = field(default_factory=list)


def appliquer_les_arrets_reportes(
    contexte: Any,
    calendrier: list[dict[str, Any]],
    details_brut: list[dict[str, Any]],
    lignes_csg_ijss: list[dict[str, Any]],
    ijss_imposables: list[dict[str, Any]],
    *,
    company_id: str | None,
    employee_id: str | None,
    year: int,
    month: int,
    saisie_du_mois: dict[str, Any] | None,
    avec_arret_du_mois: bool,
) -> EffetDuReport:
    """Les lignes des arrêts reportés : un maintien et des IJ subrogées par arrêt,
    la CSG des IJ recalculée sur le total, les alertes du report au bulletin."""
    rapport = Report.depuis_les_saisies(saisie_du_mois)
    alertes = getattr(contexte, "alertes_baremes", None)
    if isinstance(alertes, list):
        alertes.extend(a for a in rapport.alertes if a not in alertes)
        partiels = sorted(
            {d for ev in calendrier if ev.get("report_partiel") and (d := _jour(ev)) is not None}
        )
        if partiels and MESSAGE_REPORT_PARTIEL not in alertes:
            # Jours repris au milieu d'un arrêt par le bulletin suivant : les jours
            # gardés ici le sont, mais le maintien et les IJ de l'arrêt ne sont
            # pas recalculés seuls. Jamais en silence.
            alertes.append(MESSAGE_REPORT_PARTIEL)
    effet = EffetDuReport(list(lignes_csg_ijss), list(ijss_imposables))
    if not jours_reportes_du_calendrier(calendrier):
        return effet
    try:
        effet.blocs = maintien_des_arrets_reportes(
            calendrier,
            contexte,
            company_id=company_id,
            employee_id=employee_id,
            year=year,
            month=month,
            saisie_du_mois=saisie_du_mois,
            avec_arret_du_mois=avec_arret_du_mois,
        )
    except Exception:
        logger.exception("Maintien de l'arrêt reporté non calculé (company_id=%s)", company_id)
        from app.modules.payroll.engine.replis import (
            CODE_REPLI_MAINTIEN,
            signaler_repli,
        )

        signaler_repli(contexte, CODE_REPLI_MAINTIEN)
        return effet
    from app.modules.payroll.engine.ijss_bulletin import compute_ijss_csg_lines

    from .payslip_run_heures import _appliquer_maintien_arret_maladie

    ij_reportees = 0.0
    for bloc in effet.blocs:
        suffixe = f" (arrêt reporté {libelle_des_jours(bloc.jours)})"
        avant = len(details_brut)
        _, ij, modifie = _appliquer_maintien_arret_maladie(contexte, bloc.resultat, details_brut)
        for ligne in details_brut[avant:]:
            ligne["libelle"] = f"{ligne.get('libelle')}{suffixe}"
            ligne["arret_reporte"] = True
            ligne["absence_id"] = bloc.absence_id
        effet.brut_modifie = effet.brut_modifie or modifie
        effet.maintien_verse += float((bloc.resultat.get("maintien") or {}).get("maintien_verse") or 0.0)
        for ligne in ij:
            ij_reportees += float(ligne.get("montant") or 0.0)
            effet.ijss_imposables.append(
                {
                    **ligne,
                    "prime_id": "ijss_subrogees_arret_reporte",
                    "libelle": f"{ligne.get('libelle')}{suffixe}",
                }
            )
        if isinstance(alertes, list):
            alertes.extend(a for a in bloc.resultat.get("alertes") or [] if a not in alertes)
    if ij_reportees > 0:
        # Une seule CSG/CRDS sur les IJ du bulletin, celles du mois comprises.
        ij_du_mois = sum(
            float(l.get("montant") or 0.0)
            for l in ijss_imposables
            if l.get("prime_id") == "ijss_subrogees"
        )
        effet.lignes_csg_ijss = [
            l for l in lignes_csg_ijss if "IJSS" not in str(l.get("libelle") or "")
        ] + compute_ijss_csg_lines(
            round(ij_du_mois + ij_reportees, 2), (contexte.baremes.get("maladie") or {})
        )[0]
    effet.maintien_verse = round(effet.maintien_verse, 2)
    return effet


def resume_des_arrets_reportes(blocs: list[BlocReporte]) -> list[dict[str, Any]]:
    """Un bloc par arrêt reporté, lu par l'écran « Arrêts & IJ » et le suivi des IJ."""
    resume = []
    for bloc in blocs:
        maintien = bloc.resultat.get("maintien") or {}
        ijss = bloc.resultat.get("ijss") or {}
        resume.append(
            {
                "absence_id": bloc.absence_id,
                "du": min(bloc.jours).isoformat(),
                "au": max(bloc.jours).isoformat(),
                "maintien_verse": round(float(maintien.get("maintien_verse") or 0.0), 2),
                "ijss_theorique": round(float(ijss.get("ijss_theorique") or 0.0), 2),
                "nb_jours_indemnises": int(ijss.get("nb_jours_indemnises") or 0),
                "subrogation_active": bool(bloc.resultat.get("subrogation_active")),
                "bloc_maintien": bloc.resultat,
            }
        )
    return resume


#: Absences d'un autre type, retenues ou payées : la trace les note pour
#: qu'une requalification en arrêt ne les retienne pas deux fois.
_NATURES_DU_CALENDRIER = {
    "absence_non_remuneree": "sans_solde",
    "conges_payes": "conge",
    "activite_partielle": "activite_partielle",
    "rtt": "autre",
    "conge": "autre",
    "evenement_familial": "autre",
}


def _nature_du_jour(ev: dict[str, Any]) -> str | None:
    type_ev = str(ev.get("type") or "")
    if "absence_injustifiee" in type_ev:
        return "sans_solde"
    return _NATURES_DU_CALENDRIER.get(type_ev)


def trace_des_arrets(
    calendrier: list[dict[str, Any]],
    debut: date,
    fin: date,
    repris: set[date] | frozenset[date] = frozenset(),
    *,
    contexte: Any = None,
    bornes_variables: tuple[date, date] | None = None,
) -> dict[str, Any]:
    """Les jours d'absence que ce bulletin a traités, et les arrêts qu'il reprend.

    - `jours_comptes` : chaque jour calendaire d'un arrêt présent au calendrier
      dans la période, week-ends compris (de son vrai début à sa vraie fin,
      bornés à la période), hors jours repris par le bulletin suivant ;
    - `jours_retenus` : les autres absences du bulletin (sans solde, congé,
      activité partielle…), par nature, sur la période ou la fenêtre des
      variables qui les porte ;
    - `jours_repris_par_le_suivant` : jours d'arrêt écartés parce que le bulletin
      suivant les avait repris : il les garde même si ce bulletin-ci est en brouillon ;
    - `reportes` : jours d'arrêt du bulletin précédent repris ici, sous contrat.
    """
    comptes: set[date] = set()
    retenus: dict[date, str] = {}
    debut_var, fin_var = bornes_variables or (debut, fin)
    for ev in calendrier or []:
        d = _jour(ev)
        if d is None or ev.get("arret_reporte") or ev.get("is_regularisation_anterieure"):
            continue
        nature = _nature_du_jour(ev)
        if nature is not None:
            if debut_var <= d <= fin_var if nature == "sans_solde" else debut <= d <= fin:
                retenus.setdefault(d, nature)
            continue
        if not str(ev.get("type") or "").startswith("arret") and not ev.get("date_debut_arret_reel"):
            continue
        if not (debut <= d <= fin):
            continue
        comptes.add(d)
        try:
            vrai_debut = date.fromisoformat(str(ev.get("date_debut_arret_reel"))[:10])
            vraie_fin = date.fromisoformat(
                str(ev.get("date_fin_arret_reel") or ev.get("date_debut_arret_reel"))[:10]
            )
        except ValueError:
            continue
        jour = max(vrai_debut, debut)
        while jour <= min(vraie_fin, fin):
            comptes.add(jour)
            jour += timedelta(days=1)
    exclus = {j for j in repris if debut <= j <= fin}
    comptes -= exclus
    reportes = (
        jours_reportes_sous_contrat(calendrier, contexte)
        if contexte is not None
        else jours_reportes_du_calendrier(calendrier)
    )
    return {
        "jours_comptes": [j.isoformat() for j in sorted(comptes)],
        "jours_retenus": {j.isoformat(): retenus[j] for j in sorted(retenus) if j not in comptes},
        "jours_repris_par_le_suivant": [j.isoformat() for j in sorted(exclus)],
        "reportes": [
            {
                "date": d.isoformat(),
                "absence_id": str(ev.get("absence_id") or ""),
                # Repris sans seconde retenue (absence déjà retenue à l'origine).
                "sans_retenue": bool(ev.get("sans_retenue")),
            }
            for d, ev in reportes
        ],
    }


def poser_la_trace(
    bulletin: dict[str, Any],
    calendrier: list[dict[str, Any]],
    debut: date,
    fin: date,
    saisie_du_mois: dict[str, Any] | None = None,
    blocs: list[BlocReporte] | None = None,
    *,
    contexte: Any = None,
    bornes_variables: tuple[date, date] | None = None,
) -> None:
    """Sur tout bulletin calculé, même sans arrêt : une trace vide dit « rien
    compté ». Les blocs des arrêts reportés l'accompagnent."""
    repris = Report.depuis_les_saisies(saisie_du_mois).repris
    bulletin[CLE_TRACE] = trace_des_arrets(
        calendrier, debut, fin, repris, contexte=contexte, bornes_variables=bornes_variables
    )
    if blocs:
        bulletin[CLE_ARRETS_REPORTES] = resume_des_arrets_reportes(blocs)


__all__ = [
    "CLE_ARRETS_REPORTES",
    "BlocReporte",
    "EffetDuReport",
    "appliquer_les_arrets_reportes",
    "jours_reportes_du_calendrier",
    "jours_reportes_sous_contrat",
    "libelle_des_jours",
    "maintien_des_arrets_reportes",
    "poser_la_trace",
    "resume_des_arrets_reportes",
    "trace_des_arrets",
]
