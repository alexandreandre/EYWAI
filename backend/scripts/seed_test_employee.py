#!/usr/bin/env python3
"""
Seed Supabase : employé de test « Test Maintien » (Colorplast) pour le module Maintien de Salaire.

Exécution : depuis le dossier backend/
  python scripts/seed_test_employee.py

Variables d'environnement (via .env à la racine backend ou export) :
  - SUPABASE_URL, SUPABASE_KEY (toujours chargés par app.core.settings)
  - SUPABASE_SERVICE_KEY ou SUPABASE_SERVICE_ROLE_KEY : recommandé pour bypass RLS
    (get_supabase_admin_client choisit une JWT service_role si présente).

Optionnel :
  - SEED_MAINTIEN_USER_ID : UUID d'un utilisateur Auth existant ; renseigne employees.user_id
    et crée une ligne user_company_accesses (collaborateur) s'il n'en a pas déjà pour cette entreprise.

Chaîne paie (payslip_generator.py → analyser_horaires_du_mois → evenements_paie → payslip_run_heures) :
  - L'analyseur ne lit pas absence_requests ; il fusionne planned_calendar vs actual_hours.
  - Les jours prévus en type « travail » sans heures réelles suffisantes → événements « absence_injustifiee_* »
    (même logique que _preparer_calendrier_enrichi dans payslip_run_heures pour les fichiers).
  - Les jours d'arrêt maladie qualifiés doivent apparaître dans calendrier_prevu avec type « arret_maladie »
    et « arret_type » (copiés tels quels vers calendrier_analyse) pour calcul_brut et _extraire_arret_pour_maintien.

Comportement du script :
  - Si l'employé existe déjà : suppression des absence_requests « Seed script » et de la ligne
    employee_schedules du mois courant, puis recréation du planning + absences (sans toucher à l'employé).
  - Si l'employé n'existe pas : création complète comme avant.
"""

from __future__ import annotations

import calendar
import os
import sys
import traceback
import unicodedata
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Racine du package backend (parent de scripts/)
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.database import get_supabase_admin_client  # noqa: E402


COMPANY_ID = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"
TEST_EMAIL = "test.maintien@colorplast.fr"
TEST_FIRST = "Test"
TEST_LAST = "Maintien"
HIRE_DATE = "2022-01-01"
DUREE_HEBDO = 35.0
HEURES_JOUR = 7.0  # 35h / 5 jours
SALAIRE_VALEUR = 2500.0

# Plages calendaires (jours du mois) alignées sur les absence_requests seedées
SICK_LEAVE_DAY_RANGE: Tuple[int, int] = (1, 5)
AT_LEAVE_DAY_RANGE: Tuple[int, int] = (10, 12)

SEED_COMMENT_MALADIE = "Seed script — arrêt maladie qualifié (test maintien)"
SEED_COMMENT_AT = "Seed script — arrêt AT (test maintien)"

MOIS_FR = (
    "",
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def _remove_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _fmt_error(exc: BaseException) -> str:
    parts = [f"{type(exc).__name__}: {exc}"]
    details = getattr(exc, "details", None) or getattr(exc, "message", None)
    if details:
        parts.append(f"Détails: {details}")
    parts.append(traceback.format_exc())
    return "\n".join(parts)


def _in_day_range(day: int, range_pair: Tuple[int, int]) -> bool:
    lo, hi = range_pair
    return lo <= day <= hi


def _is_weekday(year: int, month: int, day: int) -> bool:
    return date(year, month, day).weekday() < 5


def _build_planned_and_actual_calendars(year: int, month: int) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Prévisionnel + réel pour employee_schedules.

    - Jours ouvrés hors arrêts : travail / pointage 7h (évite absence_injustifiee dans analyser_horaires_du_mois).
    - Arrêt maladie (plage SICK) en semaine : arret_maladie + arret_type maladie_simple (+ subrogation).
    - Arrêt AT (plage AT) en semaine : absence_non_remuneree (le moteur brut ne gère pas « arret_at » ;
      évite de fusionner deux blocs arret_maladie pour _extraire_arret_pour_maintien). Les absence_requests
      restent type arret_at pour l'UI / APIs absences.
    - Week-ends : weekend.
    """
    _, n_days = calendar.monthrange(year, month)
    planned_entries: List[Dict[str, Any]] = []
    actual_entries: List[Dict[str, Any]] = []

    for jour in range(1, n_days + 1):
        if not _is_weekday(year, month, jour):
            planned_entries.append({"jour": jour, "type": "weekend", "heures_prevues": 0.0})
            continue

        if _in_day_range(jour, SICK_LEAVE_DAY_RANGE):
            planned_entries.append(
                {
                    "jour": jour,
                    "type": "arret_maladie",
                    "heures_prevues": HEURES_JOUR,
                    "arret_type": "maladie_simple",
                    "subrogation_active": True,
                }
            )
            continue

        if _in_day_range(jour, AT_LEAVE_DAY_RANGE):
            planned_entries.append(
                {
                    "jour": jour,
                    "type": "absence_non_remuneree",
                    "heures_prevues": HEURES_JOUR,
                }
            )
            continue

        planned_entries.append(
            {"jour": jour, "type": "travail", "heures_prevues": HEURES_JOUR}
        )
        actual_entries.append(
            {"jour": jour, "type": "travail", "heures_faites": HEURES_JOUR}
        )

    planned = {
        "periode": {"mois": month, "annee": year},
        "calendrier_prevu": planned_entries,
    }
    actual = {
        "periode": {"mois": month, "annee": year},
        "calendrier_reel": actual_entries,
    }
    return planned, actual


def _count_jours_ouvres(year: int, month: int) -> int:
    _, n_days = calendar.monthrange(year, month)
    return sum(1 for j in range(1, n_days + 1) if date(year, month, j).weekday() < 5)


def _employee_insert_payload(employee_id: str, link_user_id: Optional[str]) -> Dict[str, Any]:
    norm_last = _remove_accents(TEST_LAST).upper()
    norm_first = _remove_accents(TEST_FIRST).capitalize()
    folder = f"{norm_last}_{norm_first}"
    fn_slug = _remove_accents(TEST_FIRST).lower().replace(" ", "_")
    ln_slug = _remove_accents(TEST_LAST).lower().replace(" ", "_")
    username = f"{fn_slug}.{ln_slug}"

    payload: Dict[str, Any] = {
        "id": employee_id,
        "company_id": COMPANY_ID,
        "first_name": TEST_FIRST,
        "last_name": TEST_LAST,
        "email": TEST_EMAIL,
        "username": username,
        "employee_folder_name": folder,
        "hire_date": HIRE_DATE,
        "date_naissance": "1990-06-15",
        "lieu_naissance": "Paris",
        "nationalite": "Française",
        "nir": "1900699999999",
        "adresse": {
            "rue": "1 rue du Test",
            "ville": "Lyon",
            "code_postal": "69001",
        },
        "coordonnees_bancaires": {"iban": "FR1420041010050500013M02606", "bic": "PSSTFRPPXXX"},
        "contract_type": "CDI",
        "statut": "Non-Cadre",
        "job_title": "Employé de test — Maintien de salaire",
        "is_temps_partiel": False,
        "duree_hebdomadaire": DUREE_HEBDO,
        "salaire_de_base": {"valeur": SALAIRE_VALEUR},
        "classification_conventionnelle": {
            "coefficient": 100,
            "classe_emploi": 1,
            "groupe_emploi": "A",
        },
        "periode_essai": None,
        "elements_variables": {},
        "avantages_en_nature": {"repas": {"nombre_par_mois": 0}, "logement": {"beneficie": False}},
        "specificites_paie": {
            "mutuelle": {"adhesion": False},
            "prevoyance": {"adhesion": False},
            "prelevement_a_la_source": {"taux": 0},
        },
        "is_subject_to_residence_permit": False,
        "employment_status": "actif",
        "collective_agreement_id": None,
    }
    if link_user_id:
        payload["user_id"] = link_user_id
    return payload


def _purge_seed_month(
    client: Any,
    employee_id: str,
    year: int,
    month: int,
) -> None:
    """Supprime les absences seed et la ligne employee_schedules du mois (re-seed)."""
    ar = (
        client.table("absence_requests")
        .select("id,comment")
        .eq("employee_id", employee_id)
        .execute()
    )
    for row in ar.data or []:
        c = str(row.get("comment") or "")
        if c == SEED_COMMENT_MALADIE or c == SEED_COMMENT_AT:
            try:
                client.table("absence_requests").delete().eq("id", row["id"]).execute()
            except Exception:
                pass
    try:
        client.table("employee_schedules").delete().match(
            {"employee_id": employee_id, "year": year, "month": month}
        ).execute()
    except Exception:
        pass


def _cleanup(
    client: Any,
    *,
    employee_id: Optional[str],
    absence_ids: List[str],
    year: int,
    month: int,
    user_access_row_id: Optional[str],
    delete_employee: bool,
) -> None:
    """Suppression best-effort après échec partiel."""
    for aid in absence_ids:
        try:
            client.table("absence_requests").delete().eq("id", aid).execute()
        except Exception:
            pass
    if employee_id:
        try:
            client.table("employee_schedules").delete().match(
                {"employee_id": employee_id, "year": year, "month": month}
            ).execute()
        except Exception:
            pass
        if delete_employee:
            try:
                client.table("employees").delete().eq("id", employee_id).execute()
            except Exception:
                pass
    if user_access_row_id:
        try:
            client.table("user_company_accesses").delete().eq("id", user_access_row_id).execute()
        except Exception:
            pass


def _days_iso_in_month(year: int, month: int, d1: int, d2: int) -> List[str]:
    last = calendar.monthrange(year, month)[1]
    return [
        date(year, month, d).isoformat()
        for d in range(d1, d2 + 1)
        if 1 <= d <= last
    ]


def _insert_absences(
    client: Any, employee_id: str, year: int, month: int, absence_ids_out: List[str]
) -> Tuple[Any, Any]:
    days_maladie = _days_iso_in_month(year, month, *SICK_LEAVE_DAY_RANGE)
    days_at = _days_iso_in_month(year, month, *AT_LEAVE_DAY_RANGE)

    abs1_base = {
        "employee_id": employee_id,
        "company_id": COMPANY_ID,
        "type": "arret_maladie",
        "arret_type": "maladie_simple",
        "selected_days": days_maladie,
        "status": "validated",
        "comment": SEED_COMMENT_MALADIE,
    }
    try:
        r1 = (
            client.table("absence_requests")
            .insert({**abs1_base, "subrogation_active": True})
            .execute()
        )
    except Exception as exc_sub:
        err_txt = str(exc_sub).lower()
        if "subrogation_active" in err_txt:
            r1 = client.table("absence_requests").insert(abs1_base).execute()
        else:
            raise
    if not r1.data:
        raise RuntimeError("Insertion absence 1 : échec.")
    absence_ids_out.append(str(r1.data[0]["id"]))

    r2 = (
        client.table("absence_requests")
        .insert(
            {
                "employee_id": employee_id,
                "company_id": COMPANY_ID,
                "type": "arret_at",
                "arret_type": "accident_travail",
                "selected_days": days_at,
                "status": "validated",
                "comment": SEED_COMMENT_AT,
            }
        )
        .execute()
    )
    if not r2.data:
        raise RuntimeError("Insertion absence 2 : échec.")
    absence_ids_out.append(str(r2.data[0]["id"]))
    return r1, r2


def _upsert_schedule(
    client: Any,
    employee_id: str,
    year: int,
    month: int,
    planned: Dict[str, Any],
    actual: Dict[str, Any],
) -> None:
    client.table("employee_schedules").upsert(
        {
            "employee_id": employee_id,
            "company_id": COMPANY_ID,
            "year": year,
            "month": month,
            "planned_calendar": planned,
            "actual_hours": actual,
            "payroll_events": {},
            "cumuls": {},
        },
        on_conflict="employee_id,year,month",
    ).execute()


def _print_verification(client: Any, employee_id: str, year: int, month: int) -> None:
    """Équivalent contrôle post-seed (lecture Supabase)."""
    print("\n--- Vérification employee_schedules (mois courant) ---")
    sch = (
        client.table("employee_schedules")
        .select("year,month,planned_calendar,actual_hours")
        .match({"employee_id": employee_id, "year": year, "month": month})
        .maybe_single()
        .execute()
    )
    row = sch.data if sch else None
    if not row:
        print("(aucune ligne employee_schedules pour ce mois)")
    else:
        prev = (row.get("planned_calendar") or {}).get("calendrier_prevu") or []
        reel = (row.get("actual_hours") or {}).get("calendrier_reel") or []
        print(f"year={row.get('year')} month={row.get('month')}")
        print("calendrier_prevu : jour | type | heures_prevues | arret_type (si présent)")
        for e in sorted(prev, key=lambda x: x.get("jour", 0)):
            print(
                f"  {e.get('jour'):>2} | {str(e.get('type')):<22} | "
                f"{e.get('heures_prevues')} | {e.get('arret_type', '')}"
            )
        print("calendrier_reel : jour | type | heures_faites")
        for e in sorted(reel, key=lambda x: x.get("jour", 0)):
            print(f"  {e.get('jour'):>2} | {str(e.get('type')):<22} | {e.get('heures_faites')}")

    print("\n--- Vérification absence_requests (employé test) ---")
    ab = (
        client.table("absence_requests")
        .select("id,type,arret_type,status,selected_days,comment")
        .eq("employee_id", employee_id)
        .order("id", desc=True)
        .execute()
    )
    if not ab.data:
        print("(aucune demande)")
    else:
        for a in ab.data:
            print(
                f"  id={a.get('id')} type={a.get('type')} arret_type={a.get('arret_type')} "
                f"status={a.get('status')} jours={a.get('selected_days')}"
            )
    print()


def main() -> int:
    today = date.today()
    year, month = today.year, today.month

    client = get_supabase_admin_client()

    existing = (
        client.table("employees")
        .select("id")
        .eq("company_id", COMPANY_ID)
        .eq("email", TEST_EMAIL)
        .limit(1)
        .execute()
    )

    link_uid = os.environ.get("SEED_MAINTIEN_USER_ID")
    link_uid = str(link_uid).strip() if link_uid else None
    if link_uid == "":
        link_uid = None

    employee_id: Optional[str] = None
    created_employee = False
    absence_ids: List[str] = []
    user_access_row_id: Optional[str] = None

    if existing.data:
        employee_id = str(existing.data[0]["id"])
        print(f"Employé de test déjà présent (ID: {employee_id}) — nettoyage et re-seed du mois.")
        _purge_seed_month(client, employee_id, year, month)
    else:
        employee_id = str(uuid.uuid4())

    assert employee_id is not None

    try:
        if not existing.data:
            emp_payload = _employee_insert_payload(employee_id, link_uid)
            emp_res = client.table("employees").insert(emp_payload).execute()
            if not emp_res.data:
                raise RuntimeError("Insertion employees : aucune ligne retournée.")
            created_employee = True

            if link_uid:
                acc_chk = (
                    client.table("user_company_accesses")
                    .select("id")
                    .eq("user_id", link_uid)
                    .eq("company_id", COMPANY_ID)
                    .limit(1)
                    .execute()
                )
                if not acc_chk.data:
                    access_payload: Dict[str, Any] = {
                        "user_id": link_uid,
                        "company_id": COMPANY_ID,
                        "role": "collaborateur",
                        "base_role": "collaborateur",
                        "is_primary": True,
                        "contract_type": emp_payload.get("contract_type"),
                        "statut": emp_payload.get("statut"),
                    }
                    acc_ins = client.table("user_company_accesses").insert(access_payload).execute()
                    if acc_ins.data:
                        user_access_row_id = acc_ins.data[0].get("id")
                print(
                    f"ℹ️  Accès entreprise : utilisateur {link_uid} "
                    f"({'ligne créée' if user_access_row_id else 'déjà présent'})."
                )
            else:
                print(
                    "ℹ️  Pas de SEED_MAINTIEN_USER_ID : employees.user_id non défini, "
                    "pas de user_company_accesses (voir docstring du script)."
                )
        else:
            if link_uid:
                print(
                    f"ℹ️  Employé existant : accès Auth inchangé "
                    f"(SEED_MAINTIEN_USER_ID={link_uid} ignoré pour user_company_accesses)."
                )

        planned, actual = _build_planned_and_actual_calendars(year, month)
        _upsert_schedule(client, employee_id, year, month, planned, actual)

        absence_ids.clear()
        r1, r2 = _insert_absences(client, employee_id, year, month, absence_ids)

        n_ouvres = _count_jours_ouvres(year, month)
        mois_lib = f"{MOIS_FR[month]} {year}"

        print()
        if created_employee:
            print(f"✅ Employé créé : {TEST_FIRST} {TEST_LAST} (ID: {employee_id})")
        else:
            print(f"✅ Employé conservé : {TEST_FIRST} {TEST_LAST} (ID: {employee_id})")
        print(
            f"✅ Calendrier (re)créé : {n_ouvres} jours ouvrés pour {mois_lib} — "
            f"arrêt maladie en « arret_maladie » (maladie_simple), jours travaillés pointés en actual_hours."
        )
        print(
            f"✅ Absence 1 : arrêt maladie jours {SICK_LEAVE_DAY_RANGE[0]}–{SICK_LEAVE_DAY_RANGE[1]} "
            f"(ID: {r1.data[0]['id']}, status=validated, arret_type=maladie_simple)."
        )
        print(
            f"✅ Absence 2 : arrêt AT jours {AT_LEAVE_DAY_RANGE[0]}–{AT_LEAVE_DAY_RANGE[1]} "
            f"(ID: {r2.data[0]['id']}, status=validated, arret_type=accident_travail)."
        )
        print("→ Vous pouvez maintenant régénérer le bulletin (paie) pour ce mois.")
        _print_verification(client, employee_id, year, month)
        return 0

    except Exception as exc:
        sys.stderr.write(_fmt_error(exc))
        sys.stderr.write("\n--- Nettoyage des données partiellement insérées ---\n")
        _cleanup(
            client,
            employee_id=employee_id,
            absence_ids=absence_ids,
            year=year,
            month=month,
            user_access_row_id=user_access_row_id,
            delete_employee=created_employee,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
