# Helpers partagés pour l'orchestration bulletin heures et forfait (ex-generateur_fiche_paie*.py).
# Utilisés uniquement par payslip_run_heures et payslip_run_forfait.
from __future__ import annotations
from app.core.logging import get_logger, log_payroll_debug

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app.modules.payroll.engine.reference_remuneration import mettre_a_jour_brut_reference_cumul

import calendar

from app.modules.payroll.engine.contexte import ContextePaie


logger = get_logger("modules.payroll.documents.payslip_run_common")


# Réexport pour compatibilité (tests migration / imports historiques).
def _get_end_date_for_month(
    target_annee: int, target_mois: int, jour_cible: int, occurrence_cible: int
) -> date:
    from app.modules.payroll.engine.period_forfait import _get_end_date_for_month as _impl

    return _impl(target_annee, target_mois, jour_cible, occurrence_cible)


def _periode_calendaire(annee: int, mois: int) -> tuple[date, date]:
    from app.modules.payroll.engine.period_forfait import _periode_calendaire as _impl

    return _impl(annee, mois)


def heures_remunerees_mois_contrat(
    contexte: ContextePaie,
    calendrier_etendu: list,
) -> float:
    """Heures rémunérées du mois = contractuel mensuel − absences injustifiées."""
    from app.modules.payroll.engine import legal_constants as lc
    from app.modules.payroll.engine.salaire_contractuel import (
        heures_mensuelles_legales,
        heures_sup_structurelles_mensuelles,
    )

    duree_hebdo = contexte.duree_hebdo_contrat
    base = heures_mensuelles_legales()
    if duree_hebdo > lc.DUREE_LEGALE_HEBDO:
        base += heures_sup_structurelles_mensuelles(duree_hebdo)
    heures_absence = sum(
        float(j.get("heures") or 0)
        for j in calendrier_etendu
        if "absence_injustifiee" in str(j.get("type", ""))
    )
    return max(0.0, round(base - heures_absence, 2))


def mettre_a_jour_cumuls(
    contexte: ContextePaie,
    salaire_brut_mois: float,
    remuneration_hs_mois: float,
    resultats_nets_mois: dict,
    reduction_generale_mois: dict,
    mois: int,
    smic_mois: float,
    pss_mois: float,
    chemin_employe: Path,
    *,
    heures_supplementaires_mois: float | None = None,
    heures_remunerees_mois: float | None = None,
) -> None:
    """Écrit le fichier cumuls du mois avec les valeurs du bulletin."""
    nouveaux_cumuls_data = json.loads(json.dumps(contexte.cumuls))
    nouveau_fichier_path = chemin_employe / "cumuls" / f"{mois:02d}.json"
    nouveaux_cumuls_data.setdefault("periode", {})["dernier_mois_calcule"] = mois
    cumuls = nouveaux_cumuls_data.setdefault("cumuls", {})

    cumuls["brut_total"] = cumuls.get("brut_total", 0.0) + round(salaire_brut_mois, 2)
    cumuls["net_imposable"] = cumuls.get("net_imposable", 0.0) + round(
        resultats_nets_mois.get("net_imposable", 0.0), 2
    )
    cumuls["impot_preleve_a_la_source"] = cumuls.get(
        "impot_preleve_a_la_source", 0.0
    ) + round(resultats_nets_mois.get("montant_impot_pas", 0.0), 2)
    hs_heures = (
        heures_supplementaires_mois
        if heures_supplementaires_mois is not None
        else 0.0
    )
    cumuls["heures_supplementaires_remunerees"] = cumuls.get(
        "heures_supplementaires_remunerees", 0.0
    ) + round(hs_heures, 2)
    if heures_remunerees_mois is not None:
        cumuls["heures_remunerees"] = cumuls.get("heures_remunerees", 0.0) + round(
            heures_remunerees_mois, 2
        )
    else:
        cumuls.setdefault("heures_remunerees", 0.0)
    cumuls["montant_hs_remunerees"] = cumuls.get("montant_hs_remunerees", 0.0) + round(
        remuneration_hs_mois, 2
    )

    # Plafond ANNUEL d'exonération IR des HS/HC (art. 81 quater CGI, 7 500 €
    # net/an, cf. legal_constants.PLAFOND_EXONERATION_IR_HS_ANNUEL_NET).
    # Compteur DÉDIÉ, reset explicite au 1ᵉʳ janvier UNIQUEMENT pour cette clé
    # — ne touche à AUCUN autre cumul (`brut_total`, `net_imposable`, etc. ont
    # des règles de fenêtre différentes et volontaires, ne pas y toucher ici).
    base_hs_exonerees_ir = 0.0 if mois == 1 else cumuls.get("hs_exonerees_ir_cumul", 0.0)
    cumuls["hs_exonerees_ir_cumul"] = round(
        base_hs_exonerees_ir
        + round(resultats_nets_mois.get("hs_exonerees_ir_mois", 0.0), 2),
        2,
    )

    # Cumuls ANNÉE CIVILE dédiés à la régularisation progressive Agirc-Arrco
    # de la tranche 2 (cf. calcul_cotisations._cumul_agirc_arrco_debut_mois).
    # Reset explicite au 1ᵉʳ janvier UNIQUEMENT pour ces 3 clés — ne touche à
    # aucun autre cumul existant. Calculés et exposés en side-channel sur
    # `contexte` par calcul_cotisations.py (déjà incluent ce mois, prêts à
    # être stockés tels quels comme nouvelle base pour le mois suivant).
    agirc_arrco_cumuls = getattr(contexte, "agirc_arrco_cumuls_mois_courant", None)
    if isinstance(agirc_arrco_cumuls, dict):
        if mois == 1:
            cumuls["cumul_brut_agirc_arrco"] = round(
                agirc_arrco_cumuls.get("cumul_brut_agirc_arrco", 0.0), 2
            )
            cumuls["cumul_pss_agirc_arrco"] = round(
                agirc_arrco_cumuls.get("cumul_pss_agirc_arrco", 0.0), 2
            )
            cumuls["cumul_tranche_2_appliquee"] = round(
                agirc_arrco_cumuls.get("cumul_tranche_2_appliquee", 0.0), 2
            )
        else:
            cumuls["cumul_brut_agirc_arrco"] = round(
                agirc_arrco_cumuls.get(
                    "cumul_brut_agirc_arrco", cumuls.get("cumul_brut_agirc_arrco", 0.0)
                ),
                2,
            )
            cumuls["cumul_pss_agirc_arrco"] = round(
                agirc_arrco_cumuls.get(
                    "cumul_pss_agirc_arrco", cumuls.get("cumul_pss_agirc_arrco", 0.0)
                ),
                2,
            )
            cumuls["cumul_tranche_2_appliquee"] = round(
                agirc_arrco_cumuls.get(
                    "cumul_tranche_2_appliquee",
                    cumuls.get("cumul_tranche_2_appliquee", 0.0),
                ),
                2,
            )

    if reduction_generale_mois:
        nouveau_total = reduction_generale_mois.get(
            "valeur_cumulative_a_enregistrer", 0.0
        )
        cumuls["reduction_generale_patronale"] = -nouveau_total

    start_month = 6
    try:
        company_id = getattr(contexte, "company_id", None)
        if company_id:
            from app.modules.absences.infrastructure.leave_settings_repository import (
                get_leave_policy,
            )

            start_month = get_leave_policy(str(company_id)).cp_reference_period_start_month
    except Exception:
        pass

    annee = getattr(contexte, "year", None) or getattr(contexte, "annee_paie", None)
    if annee is None and isinstance(nouveaux_cumuls_data.get("periode"), dict):
        annee = nouveaux_cumuls_data["periode"].get("annee")
    ref_year = int(annee) if annee else date.today().year
    _, last_day = calendar.monthrange(ref_year, mois)
    mettre_a_jour_brut_reference_cumul(
        nouveaux_cumuls_data,
        round(salaire_brut_mois, 2),
        date(ref_year, mois, last_day),
        start_month=start_month,
    )

    nouveau_fichier_path.parent.mkdir(parents=True, exist_ok=True)
    with open(nouveau_fichier_path, "w", encoding="utf-8") as f:
        json.dump(nouveaux_cumuls_data, f, indent=2, ensure_ascii=False)
    log_payroll_debug(logger, f'INFO: Cumuls écrits dans {nouveau_fichier_path}')


def creer_calendrier_etendu(
    chemin_employe: Path, date_debut_periode: date, date_fin_periode: date
) -> list:
    """Charge les événements de paie des fichiers evenements_paie pour la période."""
    calendrier_final = []
    mois_a_charger = set()
    current_date = date_debut_periode
    while current_date <= date_fin_periode:
        mois_a_charger.add((current_date.year, current_date.month))
        current_date = (current_date.replace(day=28) + timedelta(days=4)).replace(day=1)

    for annee, mois in mois_a_charger:
        chemin_fichier = chemin_employe / "evenements_paie" / f"{mois:02d}.json"
        if chemin_fichier.exists():
            data = json.loads(chemin_fichier.read_text(encoding="utf-8"))
            for jour_data in data.get("calendrier_analyse", []):
                jour = jour_data.get("jour")
                if jour is None:
                    continue
                ev_annee = int(jour_data.get("annee") or annee)
                ev_mois = int(jour_data.get("mois") or mois)
                date_complete = date(ev_annee, ev_mois, int(jour))
                # Un événement de régularisation antérieure (cf.
                # `regularisation_events_from_calendar`) porte volontairement une
                # date d'origine ANTÉRIEURE au mois de paie en cours (l'événement
                # réel s'est produit un mois précédent mais son effet financier
                # est rattaché au bulletin du mois courant, cf. DSN
                # S21.G00.65 / pratique Cegid "rattachement"). Il ne doit PAS être
                # exclu par le filtre de période normal.
                if not (
                    date_debut_periode <= date_complete <= date_fin_periode
                ) and not jour_data.get("is_regularisation_anterieure"):
                    continue
                entry = dict(jour_data)
                entry["date_complete"] = date_complete.isoformat()
                calendrier_final.append(entry)
        else:
            logger.warning(f'AVERTISSEMENT: Fichier événements {mois:02d}.json non trouvé.')

    return sorted(calendrier_final, key=lambda j: j["date_complete"])


# Types d'événement acceptés pour une régularisation antérieure — mêmes types
# que ceux déjà interprétés par `calcul_brut.calculer_salaire_brut` pour un
# événement du mois courant (cf. boucle `for evenement in jours_dans_periode`).
# Volontairement restreint aux absences/arrêts (le cas d'usage identifié —
# OZEN/KIRMIZI mai 2026 MBC — est une absence dont la retenue n'a été
# rattachée qu'au bulletin du mois suivant) ; un futur besoin d'un autre type
# (ex. heures sup. oubliées) devra être évalué au cas par cas avant extension.
REGULARISATION_TYPES_ACCEPTES = frozenset(
    {
        "absence_non_remuneree",
        "absence_injustifiee_base",
        "absence_injustifiee_hs25",
        "arret_maladie",
        "ferie",
    }
)


def regularisation_events_from_calendar(
    planned_calendar: dict | None,
) -> list[dict]:
    """Convertit `planned_calendar.regularisations_anterieures` (saisie mensuelle,
    cf. `specificites_paie` — NON, volontairement PAS dans specificites_paie qui
    est une config permanente : ceci est ponctuel, scopé au mois de paie où la
    régularisation est rattachée) en événements de paie compatibles avec
    `calcul_brut.py` / `creer_calendrier_etendu`.

    Chaque entrée attendue :
        {"date_complete": "2026-04-27", "type": "absence_non_remuneree",
         "heures": 7.0}
    `date_complete` est la date RÉELLE (antérieure) de l'événement — elle est
    conservée telle quelle (affichée sur le bulletin, comme le fait Cegid :
    ex. "Absence maladie 040526-310526" ou "Rappel ... de 04/26 à 04/26") ;
    seul le drapeau `is_regularisation_anterieure` permet aux filtres de
    période de la laisser passer malgré une date hors du mois de paie.
    """
    if not isinstance(planned_calendar, dict):
        return []
    raw_entries = planned_calendar.get("regularisations_anterieures") or []
    if not isinstance(raw_entries, list):
        return []

    events: list[dict] = []
    for raw in raw_entries:
        if not isinstance(raw, dict):
            continue
        type_ev = raw.get("type")
        date_str = raw.get("date_complete")
        heures = raw.get("heures")
        if type_ev not in REGULARISATION_TYPES_ACCEPTES:
            logger.warning(
                "regularisation_events_from_calendar: type inconnu/non "
                f"supporté ignoré: {type_ev!r}"
            )
            continue
        if not date_str:
            logger.warning(
                "regularisation_events_from_calendar: entrée sans "
                f"date_complete ignorée: {raw!r}"
            )
            continue
        try:
            d = date.fromisoformat(str(date_str)[:10])
        except ValueError:
            logger.warning(
                "regularisation_events_from_calendar: date_complete invalide "
                f"ignorée: {date_str!r}"
            )
            continue
        try:
            heures_f = float(heures) if heures is not None else 0.0
        except (TypeError, ValueError):
            heures_f = 0.0
        events.append(
            {
                "jour": d.day,
                "mois": d.month,
                "annee": d.year,
                "type": type_ev,
                "heures": heures_f,
                "date_complete": d.isoformat(),
                "is_regularisation_anterieure": True,
            }
        )
    return events


def resolve_exit_state_for_payslip(
    employee_id: str,
    year: int,
    month: int,
    supabase_client: Any | None = None,
) -> tuple[dict | None, bool]:
    """
    Retourne (indemnités calculées, blocage ICCP auto).

    block_iccp_cdd=True si un départ tombe sur ce mois mais les indemnités
    n'ont pas encore été calculées (évite un ICCP 10e seul incorrect).
    """
    if not employee_id:
        return None, False

    try:
        from app.core.database import supabase as default_supabase

        sb = supabase_client or default_supabase
        resp = (
            sb.table("employee_exits")
            .select("id, last_working_day, status, calculated_indemnities")
            .eq("employee_id", employee_id)
            .not_.in_("status", ["cancelled", "canceled", "annule", "annulee"])
            .order("last_working_day", desc=True)
            .limit(5)
            .execute()
        )
        rows = resp.data or []
    except Exception as exc:
        log_payroll_debug(
            logger,
            f"Indemnités de sortie non résolues pour bulletin ({employee_id}): {exc}",
        )
        return None, False

    for row in rows:
        last_day_raw = row.get("last_working_day")
        if not last_day_raw:
            continue
        if isinstance(last_day_raw, str):
            last_day = date.fromisoformat(last_day_raw[:10])
        else:
            last_day = last_day_raw
        if last_day.year != year or last_day.month != month:
            continue

        indemnities = row.get("calculated_indemnities")
        if indemnities:
            return indemnities, False
        return None, True

    return None, False


def resolve_exit_indemnities_for_payslip(
    employee_id: str,
    year: int,
    month: int,
    supabase_client: Any | None = None,
) -> dict | None:
    """Retourne les indemnités de sortie calculées si un départ tombe sur ce mois de paie."""
    indemnities, _ = resolve_exit_state_for_payslip(
        employee_id, year, month, supabase_client
    )
    return indemnities


def prefetch_jours_maintien_prime(
    *,
    company_id: str | None,
    contexte: ContextePaie,
    arret_data: dict[str, Any] | None,
    date_debut_periode: date,
    date_fin_periode: date,
) -> set[int]:
    """Pré-calcule les jours du mois avec maintien (prorata prime d'ancienneté)."""
    if not company_id or not arret_data:
        return set()
    try:
        from app.modules.maintenance_settings.application.queries import (
            get_maintenance_settings,
        )
        from app.modules.payroll.engine.maintien_salaire_service import (
            compute_jours_avec_maintien_mois,
        )

        settings_maintien = get_maintenance_settings(company_id)
        settings_dict = settings_maintien.model_dump(mode="json")
        return compute_jours_avec_maintien_mois(
            arret_data,
            contexte,
            settings_dict,
            date_debut_periode,
            date_fin_periode,
        )
    except Exception as exc:
        logger.warning(
            "Jours maintien prime non calculés (company_id=%s): %s",
            company_id,
            exc,
        )
        return set()
