#!/usr/bin/env python3
"""
Configuration initiale complète de l'entreprise « Comitech Composite » dans EYWAI.

Société cible : Comitech Composite (SIRET 49861035100013, Belley, CCN plasturgie IDCC 0292).
Ce script ne concerne pas d'autres filiales du groupe MAJI.

Usage (depuis backend/, venv activé) :
  python scripts/setup_comitech_composite.py [--dry-run] [--skip-scan]
  python scripts/setup_comitech_composite.py --skip-medical --skip-formation  # config seule
  python scripts/setup_comitech_composite.py --skip-benefits  # sans protection sociale
  python scripts/setup_comitech_composite.py --benefits-year 2025  # barèmes 2025
  python scripts/setup_comitech_composite.py --skip-participation  # sans participation 2025
  python scripts/setup_comitech_composite.py --skip-contingent     # sans contingent HS

Options :
  --skip-scan           Ne pas scanner les médailles du travail sur l'effectif
  --skip-medical        Ne pas importer le registre SPST visites médicales
  --skip-formation      Ne pas importer habilitations / formations / budget
  --skip-benefits       Ne pas configurer mutuelle / prévoyance / retraite sup
  --skip-participation  Ne pas importer simulation / campagne participation 2025
  --skip-contingent     Ne pas configurer contingent HS / contrat 39 h / RCR 2025
  --benefits-year       Année de référence protection sociale (2025 ou 2026, défaut 2026)

Étapes (idempotentes) :
  1. Crée Comitech Composite si absente, synchronise les champs identité
  2. Rattache au groupe MAJI si besoin
  3. CC plasturgie IDCC 0292, preset CP ancienneté, CET groupe, DSN external
  4. CSE carence + cycle électoral 2019
  5. Médailles du travail (barème 150/300/450/600 €) + scan effectif
  6. Catalogue primes (prime annuelle médaille 30 €)
  7. Stubs salariés absents du DSN (BOUALI, GENAND)
  8. Formations / habilitations / budget 2026 (registre Excel RH Comitech Composite)
  9. Suivi médical : activation module + registre SPST du 24/06/2026
 10. Protection sociale : catalogue mutuelle Quadra + réconciliation DSN + prévoyance / retraite sup
 11. Participation 2025 : simulation Quadra + campagne bulletin d'option (avances incluses)
 12. Contingent HS : plafond 360 h, pauses, contrat 39 h/semaine, RCR 2025 (reprise Excel)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import calendar as cal_mod
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

env_file = BACKEND_ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))

# ---------------------------------------------------------------------------
# Comitech Composite — identité légale
# ---------------------------------------------------------------------------
COMPANY_SIRET = "49861035100013"
COMPANY_NAME = "Comitech Composite"
COMPOSITE_CC_ID = "39e86454-778b-4913-ac4a-2b01735f89ef"  # plasturgie IDCC 0292
DRY_RUN_COMPANY_ID = "dry-run-comitech-composite-id"

COMPANY_IDENTITY: dict[str, Any] = {
    "company_name": COMPANY_NAME,
    "siret": COMPANY_SIRET,
    "email": "nvicendet@comitech01.com",
    "phone": "04.79.87.14.12",
    "adresse_rue": "ZA La Pélissière",
    "adresse_code_postal": "01300",
    "adresse_ville": "BELLEY",
    "naf_ape": "2229A",
    "idcc": "0292",
    "dsn_sync_mode": "external",
}

COMITECH_WORK_MEDAL_TIERS: list[dict[str, Any]] = [
    {
        "level": "argent",
        "years": 20,
        "label": "Médaille d'argent (20 ans)",
        "amount_mode": "fixed",
        "amount_value": 150,
    },
    {
        "level": "vermeil",
        "years": 30,
        "label": "Médaille de vermeil (30 ans)",
        "amount_mode": "fixed",
        "amount_value": 300,
    },
    {
        "level": "or",
        "years": 35,
        "label": "Médaille d'or (35 ans)",
        "amount_mode": "fixed",
        "amount_value": 450,
    },
    {
        "level": "grand_or",
        "years": 40,
        "label": "Grande médaille d'or (40 ans)",
        "amount_mode": "fixed",
        "amount_value": 600,
    },
]

COMITECH_BONUS_TYPES: list[dict[str, Any]] = [
    {
        "libelle": "Prime médaille du travail annuelle",
        "type": "montant_fixe",
        "montant": 30,
        "soumise_a_cotisations": True,
        "soumise_a_impot": True,
        "export_code": "PRIME_MEDAILLE_ANNUELLE",
    },
    {
        "libelle": "Prime médaille du travail — palier",
        "type": "montant_fixe",
        "montant": 0,
        "soumise_a_cotisations": True,
        "soumise_a_impot": True,
        "export_code": "PRIME_MEDAILLE_PALIER",
    },
]

CET_GROUP_PAYLOAD: dict[str, Any] = {
    "cet_enabled": True,
    "allow_deposit_hs": True,
    "allow_deposit_cp": True,
    "max_cp_days_per_year": 10,
    "validation_mode": "manager",
    "cp_unit": "ouvres",
    "cp_debit_timing": "on_validation",
    "hs_debit_timing": "on_payroll",
}

CET_GROUP_PAYLOAD_V1: dict[str, Any] = {
    "cet_enabled": True,
    "validation_mode": "manager",
}

# ---------------------------------------------------------------------------
# Comitech Composite — registre SPST (24/06/2026)
# ---------------------------------------------------------------------------
MEDICAL_REGISTRY_SOURCE = "Registre SPST Comitech Composite — 24/06/2026"

TRIGGER_BY_VISIT: dict[str, str] = {
    "vip": "periodicite_vip",
    "sir": "periodicite_sir",
}


@dataclass(frozen=True)
class MedicalRegistryRow:
    last_name: str
    first_hint: str | None
    visit_type: str  # "sir" | "vip"
    visit_date: date
    renew_before: date | None
    doctor_comment: str | None = None
    last_name_aliases: tuple[str, ...] = ()


COMITECH_MEDICAL_REGISTRY: tuple[MedicalRegistryRow, ...] = (
    MedicalRegistryRow("BOUFRIDA", "SAMIR", "sir", date(2023, 2, 3), date(2028, 3, 7)),
    MedicalRegistryRow("BOUVEYRON", "MICHEL", "sir", date(2025, 6, 10), date(2027, 6, 10)),
    MedicalRegistryRow("CORDEAU", "Olivier", "vip", date(2023, 8, 24), date(2028, 8, 24)),
    MedicalRegistryRow(
        "DA SILVA",
        "VITOR",
        "sir",
        date(2025, 4, 9),
        date(2027, 2, 9),
        last_name_aliases=("DA SILVA CARDOSO", "CASANOVA DA SILVA"),
    ),
    MedicalRegistryRow(
        "EL IDRISSI",
        "HAFIDA",
        "sir",
        date(2026, 1, 21),
        date(2028, 1, 21),
        "Eviter les manutentions manuelles seules de charges lourdes.",
        ("MARCHICH",),
    ),
    MedicalRegistryRow("GARCIA", "MICKAEL", "sir", date(2023, 5, 11), date(2028, 5, 11)),
    MedicalRegistryRow(
        "GOYAT",
        "Stephane",
        "sir",
        date(2025, 4, 11),
        date(2027, 4, 11),
        "PAS DE CONDUITE DE CHARIOT",
    ),
    MedicalRegistryRow(
        "GROS",
        "NADINE",
        "sir",
        date(2025, 4, 11),
        date(2027, 2, 11),
        last_name_aliases=("PRONIER",),
    ),
    MedicalRegistryRow("GENAND", "CATHERINE", "sir", date(2025, 4, 23), date(2027, 4, 23)),
    MedicalRegistryRow("JEAN", "DAVID", "sir", date(2025, 9, 25), date(2027, 9, 25)),
    MedicalRegistryRow(
        "OUASSIF",
        "Yamena",
        "sir",
        date(2025, 11, 6),
        date(2027, 4, 6),
        last_name_aliases=("MARCHICH",),
    ),
    MedicalRegistryRow(
        "POINSIGNON",
        "Thibault",
        "sir",
        date(2026, 4, 28),
        date(2028, 3, 28),
    ),
    MedicalRegistryRow("SARDA", "DOMINIQUE", "sir", date(2025, 6, 24), date(2027, 6, 24)),
    MedicalRegistryRow("SOW", "MAMADOU", "sir", date(2025, 10, 2), date(2027, 10, 2)),
    MedicalRegistryRow("TROUILLOUD", "FLORIAN", "sir", date(2025, 2, 15), date(2027, 2, 15)),
    MedicalRegistryRow(
        "VALLAT",
        "ROMAIN",
        "sir",
        date(2023, 1, 9),
        date(2025, 1, 9),
        "rdv demandé le 17/03",
    ),
    MedicalRegistryRow(
        "VADOT",
        "Virginie",
        "sir",
        date(2026, 2, 12),
        date(2028, 2, 12),
        last_name_aliases=("LACAQUE",),
    ),
)

# ---------------------------------------------------------------------------
# Comitech Composite — formations / habilitations (registre Excel RH)
# ---------------------------------------------------------------------------
FORMATION_REGISTRY_SOURCE = "Registre formations Comitech Composite — Excel RH"
TRAINING_BUDGET_YEAR = 2026

COMITECH_CERT_REFS: list[dict[str, Any]] = [
    {
        "name": "Autorisation de conduite",
        "category": "securite",
        "validity_months": 36,
        "certifying_body": "AFTRAL",
        "description": "Autorisation de conduite véhicules entreprise",
    },
    {
        "name": "SST",
        "category": "securite",
        "validity_months": 24,
        "description": "Sauveteur secouriste du travail",
    },
    {
        "name": "Formation incendie / évacuation",
        "category": "securite",
        "validity_months": 36,
        "description": "Recyclage tous les 3 ans — session collective Belley",
    },
]


@dataclass(frozen=True)
class EmployeeCertSeed:
    last_name: str
    first_hint: str | None
    obtained: date
    expiry: date
    cert_ref_name: str
    notes: str | None = None
    last_name_aliases: tuple[str, ...] = ()


COMITECH_EMPLOYEE_CERTS: tuple[EmployeeCertSeed, ...] = (
    EmployeeCertSeed(
        "BOUVEYRON", None, date(2024, 2, 21), date(2027, 2, 1),
        "Autorisation de conduite", "formation AFTRAL",
    ),
    EmployeeCertSeed(
        "VALLAT", None, date(2024, 2, 21), date(2027, 2, 1),
        "Autorisation de conduite", "formation AFTRAL",
    ),
    EmployeeCertSeed(
        "DA SILVA CARDOSO", None, date(2024, 2, 21), date(2027, 2, 1),
        "Autorisation de conduite", "formation AFTRAL",
        last_name_aliases=("DA SILVA", "CASANOVA DA SILVA"),
    ),
    EmployeeCertSeed(
        "POINSIGNON", None, date(2024, 2, 21), date(2027, 2, 1),
        "Autorisation de conduite", "formation AFTRAL",
    ),
    EmployeeCertSeed(
        "SARDA", None, date(2024, 2, 21), date(2027, 2, 1),
        "Autorisation de conduite", "formation AFTRAL",
    ),
    EmployeeCertSeed(
        "TROUILLOUD", None, date(2024, 2, 21), date(2027, 2, 1),
        "Autorisation de conduite", "formation AFTRAL",
    ),
    EmployeeCertSeed("SARDA", None, date(2024, 4, 9), date(2026, 4, 9), "SST"),
    EmployeeCertSeed("GENAND", "Catherine", date(2024, 4, 9), date(2026, 4, 9), "SST"),
    EmployeeCertSeed("BOUVEYRON", None, date(2024, 11, 6), date(2026, 11, 6), "SST"),
    EmployeeCertSeed("POINSIGNON", None, date(2024, 11, 6), date(2026, 11, 6), "SST"),
)

COMITECH_INCENDIE_SESSION = {
    "obtained": date(2023, 11, 17),
    "expiry": date(2026, 11, 17),
    "notes": "Session collective 17/11/2023 — prochaine session 21/04/2026",
}

COMITECH_SOLIDWORKS_NOTES = (
    "Dossier OPCO 26FOR07761,01 — Financement ENTREPRISE — Coût interne 275,26 € — "
    "Impact plan OPCO OUI — Remboursement OPCO OUI — Facture payée OUI — Lieu Belley — Certif OUI"
)
COMITECH_ACC_RH_NOTES = (
    "Dossier OPCO 24DIA04176.01 — Financement OPCO — Coût total 10 000 € HT — "
    "Formateur HESNAUX Fabienne — STADRH 06.29.57.73.08 — Lieu Belley — Certif NON"
)

COMITECH_SOLIDWORKS_EMPLOYEES: tuple[str, ...] = ("SARDA", "BOUVEYRON", "GARCIA", "CHAMBERT")

COMITECH_TRAINING_BUDGET: dict[str, Any] = {
    "global_envelope": 12880.0,
    "alert_threshold_1": 70.0,
    "alert_threshold_2": 90.0,
    "service_breakdown": {
        "SOLIDWORKS": 2880.0,
        "ACC_RH": 10000.0,
        "PDC": 0.0,
        "opco_budget_alloue": 4800.0,
        "opco_disponibilites": 2195.26,
    },
}

# Salariés absents de l'import DSN mais présents dans les registres RH Comitech Composite
COMITECH_STUB_EMPLOYEES: tuple[tuple[str, str, str, int], ...] = (
    ("Gaëlle", "BOUALI", "RH", 901),
    ("Catherine", "GENAND", "Mouleuse formatrice", 902),
)


@dataclass
class SetupOptions:
    dry_run: bool = False
    scan_medals: bool = True
    seed_medical: bool = True
    seed_formation: bool = True
    seed_benefits: bool = True
    seed_participation: bool = True
    seed_contingent: bool = True
    seed_planned_calendar: bool = True
    calendar_xlsx: Path | None = None
    benefits_year: int = 2026


def _get_supabase():
    from app.core.database import supabase

    return supabase


# ---------------------------------------------------------------------------
# Entreprise Comitech Composite
# ---------------------------------------------------------------------------
def find_company(supabase) -> dict | None:
    r = (
        supabase.table("companies")
        .select("*")
        .eq("siret", COMPANY_SIRET)
        .maybe_single()
        .execute()
    )
    if r and r.data:
        return r.data
    r2 = (
        supabase.table("companies")
        .select("*")
        .ilike("company_name", COMPANY_NAME)
        .limit(1)
        .execute()
    )
    rows = r2.data or []
    return rows[0] if rows else None


def ensure_group_attachment(supabase, company_id: str, *, dry_run: bool) -> None:
    row = (
        supabase.table("companies")
        .select("group_id")
        .eq("id", company_id)
        .maybe_single()
        .execute()
    )
    if row and row.data and row.data.get("group_id"):
        return
    if dry_run:
        print(f"[dry-run] rattachement groupe MAJI pour Comitech Composite ({company_id})")
        return
    from app.modules.super_admin.infrastructure.commands import _attach_company_to_default_group

    group_id = _attach_company_to_default_group(supabase, company_id)
    if group_id:
        print(f"Comitech Composite rattachée au groupe MAJI ({group_id})")


def sync_company_identity(
    supabase, company_id: str, fields: dict[str, Any], *, dry_run: bool
) -> None:
    payload = {k: v for k, v in fields.items() if k != "company_name"}
    if dry_run:
        print(f"[dry-run] sync Comitech Composite {company_id}", payload)
        return
    supabase.table("companies").update(payload).eq("id", company_id).execute()


def create_company(supabase, *, dry_run: bool) -> dict:
    from app.modules.super_admin.infrastructure.commands import create_company_with_admin

    if dry_run:
        print("[dry-run] create Comitech Composite", COMPANY_IDENTITY)
        return {"id": DRY_RUN_COMPANY_ID, **COMPANY_IDENTITY}

    row = create_company_with_admin(COMPANY_IDENTITY, {"id": "setup-script"})
    cid = row["company"]["id"]
    sync_company_identity(supabase, cid, COMPANY_IDENTITY, dry_run=False)
    return supabase.table("companies").select("*").eq("id", cid).single().execute().data


def assign_collective_agreement(supabase, company_id: str, *, dry_run: bool) -> None:
    existing = (
        supabase.table("company_collective_agreements")
        .select("id")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        return
    if dry_run:
        print(f"[dry-run] assign CC plasturgie -> Comitech Composite ({company_id})")
        return
    supabase.table("company_collective_agreements").insert(
        {"company_id": company_id, "collective_agreement_id": COMPOSITE_CC_ID}
    ).execute()


def apply_cp_seniority_preset(company_id: str, *, dry_run: bool) -> None:
    if dry_run:
        print("[dry-run] CP seniority preset plasturgie_idcc_0292 -> Comitech Composite")
        return
    from app.modules.absences.application.cp_seniority_commands import (
        apply_cp_seniority_preset as apply_preset,
        update_cp_seniority_settings,
    )

    apply_preset(company_id, "plasturgie_idcc_0292")
    update_cp_seniority_settings(company_id, {"enabled": True})


def seed_cet_settings(supabase, company_id: str, *, dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] CET Comitech Composite -> {company_id}", CET_GROUP_PAYLOAD)
        return
    for label, payload in (
        ("v2", {**CET_GROUP_PAYLOAD, "company_id": company_id}),
        ("v1", {**CET_GROUP_PAYLOAD_V1, "company_id": company_id}),
    ):
        try:
            supabase.table("company_cet_settings").upsert(
                payload, on_conflict="company_id"
            ).execute()
            print(f"CET Comitech Composite configuré ({label})")
            return
        except Exception as exc:
            if label == "v1":
                print(
                    "CET seed ignoré pour Comitech Composite (schéma BDD à migrer): "
                    f"{exc}"
                )
                return


def configure_work_medals(company_id: str, *, dry_run: bool, scan: bool) -> None:
    settings_payload = {
        "enabled": True,
        "seniority_basis": "company_only",
        "reminder_months_before": 6,
        "tiers": COMITECH_WORK_MEDAL_TIERS,
        "default_is_taxable": True,
        "default_is_socially_taxed": False,
    }
    if dry_run:
        print(f"[dry-run] médailles du travail Comitech Composite -> {company_id}")
        if scan:
            print(f"[dry-run] scan médailles Comitech Composite -> {company_id}")
        return
    from app.modules.work_medals.application.commands import save_work_medal_settings
    from app.modules.work_medals.schemas.requests import WorkMedalSettingsUpdate

    save_work_medal_settings(company_id, WorkMedalSettingsUpdate(**settings_payload))
    if scan:
        from app.modules.work_medals.application.detection import scan_company_work_medals

        result = scan_company_work_medals(company_id)
        print(
            f"Médailles Comitech Composite : "
            f"{result.created} créé(s), {result.updated} mis à jour"
        )


def seed_bonus_catalog(supabase, company_id: str, *, dry_run: bool) -> None:
    existing = (
        supabase.table("company_bonus_types")
        .select("libelle")
        .eq("company_id", company_id)
        .execute()
    )
    known = {str(r["libelle"]) for r in (existing.data or [])}
    for spec in COMITECH_BONUS_TYPES:
        if spec["libelle"] in known:
            continue
        row = {**spec, "company_id": company_id}
        if dry_run:
            print(f"[dry-run] prime Comitech Composite -> {company_id}", row)
            continue
        supabase.table("company_bonus_types").insert(row).execute()


def configure_cse(supabase, company_id: str, *, dry_run: bool) -> None:
    from app.modules.cse.application.cse_settings import save_company_cse_settings
    from app.modules.cse.infrastructure.cse_service_impl import create_election_cycle
    from app.modules.cse.schemas.requests import ElectionCycleCreate

    if dry_run:
        print("[dry-run] CSE carence Comitech Composite until 2023-09-06")
        return

    try:
        supabase.table("company_cse_settings").select("company_id").limit(1).execute()
    except Exception:
        print(
            "Table company_cse_settings absente — appliquer la migration "
            "supabase/migrations/20260623120000_company_cse_settings.sql puis relancer."
        )
        return

    save_company_cse_settings(
        company_id,
        {
            "cse_status": "carence",
            "carence_valid_until": "2023-09-06",
            "notes": "PV carence CSE Cerfa 15248*03 — 06/09/2019 — Belley (Comitech Composite)",
        },
    )

    existing_cycles = (
        supabase.table("cse_election_cycles")
        .select("id")
        .eq("company_id", company_id)
        .ilike("cycle_name", "%2019%")
        .limit(1)
        .execute()
    )
    if not existing_cycles.data:
        create_election_cycle(
            company_id,
            ElectionCycleCreate(
                cycle_name="Carence CSE 2019",
                mandate_end_date=__import__("datetime").date(2023, 9, 6),
                election_date=__import__("datetime").date(2019, 9, 2),
                outcome="carence",
                notes={
                    "info_salaries": "2019-07-04",
                    "premier_tour": "2019-08-19",
                    "second_tour": "2019-09-02",
                    "cerfa": "15248*03",
                },
            ),
        )


# ---------------------------------------------------------------------------
# Effectif Comitech Composite (partagé medical + formation)
# ---------------------------------------------------------------------------
def load_employees(supabase, company_id: str) -> list[dict]:
    r = (
        supabase.table("employees")
        .select("id, first_name, last_name, employment_status, job_title")
        .eq("company_id", company_id)
        .execute()
    )
    return list(r.data or [])


def _normalize_name(value: str | None) -> str:
    """Uppercase sans accents — matching registres Excel vs fiches DSN."""
    folded = unicodedata.normalize("NFD", value or "")
    stripped = "".join(c for c in folded if unicodedata.category(c) != "Mn")
    return stripped.upper().strip()


def _first_name_matches(first_hint: str | None, first_name: str | None) -> bool:
    if not first_hint:
        return True
    hint = _normalize_name(first_hint)
    actual = _normalize_name(first_name)
    if not hint or not actual:
        return False
    if hint in actual or actual in hint:
        return True
    prefix_len = min(len(hint), len(actual), 6)
    return prefix_len >= 3 and hint[:prefix_len] == actual[:prefix_len]


def _resolve_by_last(
    employees: list[dict], last_name: str, first_hint: str | None
) -> dict | None:
    ln = _normalize_name(last_name)
    matches = [
        e for e in employees if ln in _normalize_name(e.get("last_name"))
    ]
    if first_hint:
        matches = [
            e
            for e in matches
            if _first_name_matches(first_hint, e.get("first_name"))
        ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1 and not first_hint:
        return matches[0]
    return None


def resolve_employee(
    employees: list[dict],
    last_name: str,
    first_hint: str | None = None,
    last_name_aliases: tuple[str, ...] = (),
) -> dict | None:
    for candidate in (last_name, *last_name_aliases):
        emp = _resolve_by_last(employees, candidate, first_hint)
        if emp:
            return emp
    return None


def ensure_stub_employees(
    supabase, company_id: str, employees: list[dict], *, dry_run: bool
) -> list[dict]:
    """Crée les fiches BOUALI / GENAND si absentes (registres RH Comitech Composite)."""
    template = (
        supabase.table("employees")
        .select("*")
        .eq("company_id", company_id)
        .eq("last_name", "SARDA")
        .limit(1)
        .execute()
    )
    if not template.data and not dry_run:
        print("WARN stubs Comitech Composite : aucun modèle salarié pour création")
        return employees

    tpl = template.data[0] if template.data else {}
    skip_keys = {
        "id", "created_at", "updated_at", "email", "username",
        "employee_folder_name", "user_id", "first_name", "last_name", "job_title", "nir",
    }
    created_count = 0

    for first_name, last_name, job_title, suffix in COMITECH_STUB_EMPLOYEES:
        if resolve_employee(employees, last_name, first_name):
            continue
        if dry_run:
            print(f"[dry-run] stub Comitech Composite : {last_name} {first_name}")
            continue

        from app.modules.employees.application.commands import create_employee_imported

        payload = {k: v for k, v in tpl.items() if k not in skip_keys and v is not None}
        payload.update(
            {
                "first_name": first_name,
                "last_name": last_name,
                "job_title": job_title or tpl.get("job_title") or "",
                "nir": f"2999999999{suffix:03d}",
                "email": (
                    f"import.{first_name.lower()}.{last_name.lower()}.{suffix}"
                    f"@498610351.dsn-import.local"
                ),
            }
        )
        row = create_employee_imported(payload, company_id)
        employees.append(
            {
                "id": row["id"],
                "first_name": first_name,
                "last_name": last_name,
                "job_title": job_title,
                "employment_status": "actif",
            }
        )
        created_count += 1
        print(f"Stub Comitech Composite créé : {last_name} {first_name} ({row['id']})")

    if created_count:
        print(f"Stubs Comitech Composite : {created_count} fiche(s) créée(s)")
    return employees


# ---------------------------------------------------------------------------
# Formations / habilitations Comitech Composite
# ---------------------------------------------------------------------------
def _get_or_create_cert_ref(
    supabase, company_id: str, spec: dict[str, Any], *, dry_run: bool
) -> str | None:
    existing = (
        supabase.table("certification_referential")
        .select("id")
        .eq("company_id", company_id)
        .eq("name", spec["name"])
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    if existing.data:
        return str(existing.data[0]["id"])
    if dry_run:
        print(f"[dry-run] cert ref Comitech Composite : {spec['name']}")
        return str(uuid.uuid4())
    from app.modules.certifications.application.commands import create_certification_ref
    from app.modules.certifications.schemas.requests import CertificationRefCreate

    row = create_certification_ref(company_id, CertificationRefCreate(**spec))
    return str(row.id)


def _cert_exists(
    supabase, company_id: str, employee_id: str, certification_id: str, obtained: date
) -> bool:
    r = (
        supabase.table("employee_certifications")
        .select("id")
        .eq("company_id", company_id)
        .eq("employee_id", employee_id)
        .eq("certification_id", certification_id)
        .eq("obtained_date", obtained.isoformat())
        .eq("is_archived", False)
        .limit(1)
        .execute()
    )
    return bool(r.data)


def _get_or_create_training(
    supabase, company_id: str, title: str, body: dict[str, Any], *, dry_run: bool
) -> str | None:
    existing = (
        supabase.table("training_catalog")
        .select("id")
        .eq("company_id", company_id)
        .eq("title", title)
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    if existing.data:
        return str(existing.data[0]["id"])
    if dry_run:
        print(f"[dry-run] formation Comitech Composite : {title}")
        return str(uuid.uuid4())
    from app.modules.training.application.commands import create_training
    from app.modules.training.schemas.requests import TrainingCatalogCreate

    row = create_training(company_id, TrainingCatalogCreate(**body))
    return str(row.id)


def _enrollment_exists(
    supabase, company_id: str, training_id: str, employee_id: str
) -> bool:
    r = (
        supabase.table("training_enrollments")
        .select("id")
        .eq("company_id", company_id)
        .eq("training_id", training_id)
        .eq("employee_id", employee_id)
        .neq("status", "cancelled")
        .limit(1)
        .execute()
    )
    return bool(r.data)


def seed_formation_registry(
    supabase,
    company_id: str,
    employees: list[dict],
    *,
    dry_run: bool,
) -> dict[str, Any]:
    """Importe habilitations, formations et budget Comitech Composite."""
    ref_ids: dict[str, str] = {}
    for spec in COMITECH_CERT_REFS:
        rid = _get_or_create_cert_ref(supabase, company_id, spec, dry_run=dry_run)
        if rid:
            ref_ids[spec["name"]] = rid

    certs_created = 0
    certs_skipped = 0
    cert_missing: list[str] = []

    for row in COMITECH_EMPLOYEE_CERTS:
        emp = resolve_employee(
            employees, row.last_name, row.first_hint, row.last_name_aliases
        )
        label = f"{row.last_name} {row.first_hint or ''}".strip()
        if not emp:
            cert_missing.append(label)
            certs_skipped += 1
            continue
        ref_id = ref_ids.get(row.cert_ref_name)
        if not ref_id:
            certs_skipped += 1
            continue
        if _cert_exists(supabase, company_id, str(emp["id"]), ref_id, row.obtained):
            certs_skipped += 1
            continue
        if dry_run:
            print(f"[dry-run] cert {row.cert_ref_name} -> {label}")
            certs_created += 1
            continue
        from app.modules.certifications.application.commands import create_employee_certification
        from app.modules.certifications.schemas.requests import EmployeeCertificationCreate

        create_employee_certification(
            company_id,
            EmployeeCertificationCreate(
                employee_id=str(emp["id"]),
                certification_id=ref_id,
                obtained_date=row.obtained,
                expiry_date=row.expiry,
                certifying_body=(
                    "AFTRAL" if row.cert_ref_name == "Autorisation de conduite" else None
                ),
                notes=row.notes,
            ),
        )
        certs_created += 1

    incendie_id = ref_ids.get("Formation incendie / évacuation")
    incendie_created = 0
    if incendie_id:
        for emp in employees:
            if (emp.get("employment_status") or "actif") != "actif":
                continue
            if _cert_exists(
                supabase,
                company_id,
                str(emp["id"]),
                incendie_id,
                COMITECH_INCENDIE_SESSION["obtained"],
            ):
                certs_skipped += 1
                continue
            if dry_run:
                print(
                    f"[dry-run] incendie Comitech Composite -> "
                    f"{emp.get('last_name')} {emp.get('first_name')}"
                )
                incendie_created += 1
                continue
            from app.modules.certifications.application.commands import create_employee_certification
            from app.modules.certifications.schemas.requests import EmployeeCertificationCreate

            create_employee_certification(
                company_id,
                EmployeeCertificationCreate(
                    employee_id=str(emp["id"]),
                    certification_id=incendie_id,
                    obtained_date=COMITECH_INCENDIE_SESSION["obtained"],
                    expiry_date=COMITECH_INCENDIE_SESSION["expiry"],
                    notes=COMITECH_INCENDIE_SESSION["notes"],
                ),
            )
            incendie_created += 1

    solidworks_id = _get_or_create_training(
        supabase,
        company_id,
        "Formation adaptée SolidWorks",
        {
            "title": "Formation adaptée SolidWorks",
            "training_type": "presentiel",
            "duration_hours": 14.0,
            "unit_cost_ht": 720.0,
            "pedagogical_objective": "Formation SolidWorks — équipe Bureau Belley",
            "categories": ["metier", "cao"],
        },
        dry_run=dry_run,
    )
    acc_rh_id = _get_or_create_training(
        supabase,
        company_id,
        "ACC RH",
        {
            "title": "ACC RH",
            "training_type": "blended",
            "provider": "STADRH — 06.29.57.73.08 — contactstadrh@gmail.com",
            "duration_hours": 35.0,
            "unit_cost_ht": 10000.0,
            "pedagogical_objective": (
                "GRH : fiche de poste, EAE, EP, grille de compétences — "
                "Formateur HESNAUX Fabienne"
            ),
            "categories": ["rh", "management"],
        },
        dry_run=dry_run,
    )

    enrollments_created = 0
    enrollments_missing: list[str] = []

    if solidworks_id:
        for ln in COMITECH_SOLIDWORKS_EMPLOYEES:
            emp = resolve_employee(employees, ln)
            if not emp:
                enrollments_missing.append(f"{ln} (SolidWorks)")
                continue
            if _enrollment_exists(supabase, company_id, solidworks_id, str(emp["id"])):
                continue
            if dry_run:
                print(f"[dry-run] inscription SolidWorks Comitech Composite -> {ln}")
                enrollments_created += 1
                continue
            from app.modules.training.application.commands import create_enrollment
            from app.modules.training.schemas.requests import TrainingEnrollmentCreate

            create_enrollment(
                company_id,
                TrainingEnrollmentCreate(
                    training_id=solidworks_id,
                    employee_id=str(emp["id"]),
                    status="completed",
                    notes=COMITECH_SOLIDWORKS_NOTES,
                ),
            )
            enrollments_created += 1

    if acc_rh_id:
        emp = resolve_employee(employees, "BOUALI", "Gaëlle")
        if not emp:
            enrollments_missing.append("BOUALI Gaëlle (ACC RH)")
        elif not _enrollment_exists(supabase, company_id, acc_rh_id, str(emp["id"])):
            if dry_run:
                print("[dry-run] inscription ACC RH Comitech Composite -> BOUALI Gaëlle")
                enrollments_created += 1
            else:
                from app.modules.training.application.commands import create_enrollment
                from app.modules.training.schemas.requests import TrainingEnrollmentCreate

                create_enrollment(
                    company_id,
                    TrainingEnrollmentCreate(
                        training_id=acc_rh_id,
                        employee_id=str(emp["id"]),
                        status="completed",
                        notes=COMITECH_ACC_RH_NOTES,
                    ),
                )
                enrollments_created += 1

    budget_action = "skipped"
    if not dry_run:
        from app.modules.training_budget.application.commands import save_budget
        from app.modules.training_budget.schemas.requests import TrainingBudgetPutBody

        save_budget(
            company_id,
            TRAINING_BUDGET_YEAR,
            TrainingBudgetPutBody(**COMITECH_TRAINING_BUDGET),
        )
        budget_action = "saved"
        print(
            f"Budget formation Comitech Composite {TRAINING_BUDGET_YEAR} : "
            f"{COMITECH_TRAINING_BUDGET['global_envelope']} €"
        )
    else:
        print(
            f"[dry-run] budget formation Comitech Composite {TRAINING_BUDGET_YEAR} = "
            f"{COMITECH_TRAINING_BUDGET['global_envelope']} €"
        )
        budget_action = "dry_run"

    print(
        f"Formations Comitech Composite : {certs_created + incendie_created} habilitation(s), "
        f"{enrollments_created} inscription(s), budget {budget_action}"
    )
    if cert_missing:
        print("Habilitations — salariés introuvables :")
        for name in cert_missing:
            print(f"  - {name}")

    return {
        "certifications_created": certs_created + incendie_created,
        "certifications_skipped": certs_skipped,
        "enrollments_created": enrollments_created,
        "budget_year": TRAINING_BUDGET_YEAR,
        "budget_action": budget_action,
        "missing_cert_employees": cert_missing,
        "missing_enrollment_employees": enrollments_missing,
    }


# ---------------------------------------------------------------------------
# Suivi médical Comitech Composite
# ---------------------------------------------------------------------------
def configure_medical_module(supabase, company_id: str, *, dry_run: bool) -> None:
    if dry_run:
        print("[dry-run] medical_follow_up_enabled=true pour Comitech Composite")
        return
    from app.modules.companies.infrastructure.repository import company_repository

    current = company_repository.get_settings(company_id) or {}
    if current.get("medical_follow_up_enabled") is True:
        return
    current["medical_follow_up_enabled"] = True
    company_repository.update_settings(company_id, current)
    print("Module suivi médical activé pour Comitech Composite")


def _set_poste_sir(
    supabase, employee_id: str, is_sir: bool, *, dry_run: bool
) -> None:
    if dry_run:
        return
    try:
        supabase.table("employees").update({"is_poste_sir": is_sir}).eq("id", employee_id).execute()
    except Exception as exc:
        print(
            f"  WARN is_poste_sir non mis à jour ({employee_id}) — "
            f"colonne absente ou schéma à migrer : {exc}"
        )


def _visit_already_imported(
    supabase,
    company_id: str,
    employee_id: str,
    visit_type: str,
    visit_date: date,
) -> bool:
    r = (
        supabase.table("medical_follow_up_obligations")
        .select("id")
        .eq("company_id", company_id)
        .eq("employee_id", employee_id)
        .eq("visit_type", visit_type)
        .eq("status", "realisee")
        .eq("completed_date", visit_date.isoformat())
        .limit(1)
        .execute()
    )
    return bool(r.data)


def _insert_completed_visit(
    supabase,
    company_id: str,
    employee_id: str,
    row: MedicalRegistryRow,
    *,
    dry_run: bool,
) -> bool:
    if _visit_already_imported(
        supabase, company_id, employee_id, row.visit_type, row.visit_date
    ):
        return False

    justification_parts = [MEDICAL_REGISTRY_SOURCE]
    if row.doctor_comment:
        justification_parts.append(row.doctor_comment)
    justification = " — ".join(justification_parts)

    payload = {
        "company_id": company_id,
        "employee_id": employee_id,
        "visit_type": row.visit_type,
        "trigger_type": TRIGGER_BY_VISIT.get(row.visit_type, "periodicite_vip"),
        "due_date": row.visit_date.isoformat(),
        "priority": 2,
        "status": "realisee",
        "completed_date": row.visit_date.isoformat(),
        "rule_source": "legal",
        "justification": justification,
    }
    if dry_run:
        print(
            f"[dry-run] visite {row.visit_type} Comitech Composite {row.last_name} "
            f"({row.visit_date.isoformat()})"
        )
        return True

    supabase.table("medical_follow_up_obligations").insert(payload).execute()
    return True


def _sync_next_due_from_registry(
    supabase,
    company_id: str,
    employee_id: str,
    row: MedicalRegistryRow,
    *,
    dry_run: bool,
) -> None:
    if not row.renew_before:
        return

    r = (
        supabase.table("medical_follow_up_obligations")
        .select("id, due_date")
        .eq("company_id", company_id)
        .eq("employee_id", employee_id)
        .eq("visit_type", row.visit_type)
        .in_("status", ["a_faire", "planifiee"])
        .order("due_date")
        .limit(1)
        .execute()
    )
    if not r.data:
        return

    ob = r.data[0]
    target = row.renew_before.isoformat()
    if ob.get("due_date") == target:
        return

    if dry_run:
        print(
            f"[dry-run] échéance SPST Comitech Composite {row.last_name} "
            f"{row.visit_type} → {target}"
        )
        return

    supabase.table("medical_follow_up_obligations").update({"due_date": target}).eq(
        "id", ob["id"]
    ).execute()


def seed_medical_registry(
    supabase,
    company_id: str,
    employees: list[dict],
    *,
    dry_run: bool,
) -> dict[str, Any]:
    from app.modules.medical_follow_up.application.service import (
        compute_obligations_for_employee,
    )

    created = 0
    skipped = 0
    missing: list[str] = []
    touched: set[str] = set()

    for row in COMITECH_MEDICAL_REGISTRY:
        emp = resolve_employee(
            employees, row.last_name, row.first_hint, row.last_name_aliases
        )
        label = f"{row.last_name} {row.first_hint or ''}".strip()
        if not emp:
            missing.append(label)
            skipped += 1
            continue

        employee_id = str(emp["id"])
        _set_poste_sir(supabase, employee_id, row.visit_type == "sir", dry_run=dry_run)

        inserted = _insert_completed_visit(
            supabase, company_id, employee_id, row, dry_run=dry_run
        )
        if inserted:
            created += 1
            touched.add(employee_id)
        else:
            skipped += 1

        if not dry_run:
            compute_obligations_for_employee(company_id, employee_id)
            _sync_next_due_from_registry(
                supabase, company_id, employee_id, row, dry_run=False
            )
            compute_obligations_for_employee(company_id, employee_id)
        elif row.renew_before:
            print(
                f"[dry-run] recalc SPST Comitech Composite {label} "
                f"→ {row.renew_before.isoformat()}"
            )

    print(
        f"Suivi médical Comitech Composite : {created} visite(s) importée(s), "
        f"{skipped} ignorée(s), {len(touched)} salarié(s) recalculé(s)"
    )
    if missing:
        print("Suivi médical — salariés introuvables :")
        for name in missing:
            print(f"  - {name}")

    return {
        "created": created,
        "skipped": skipped,
        "missing": missing,
        "touched_employee_count": len(touched),
    }


def cleanup_comitech_medical_phantoms(
    supabase,
    company_id: str,
    employees: list[dict],
    *,
    dry_run: bool,
) -> dict[str, Any]:
    """
    Recalcule le suivi médical pour tout l'effectif actif Comitech Composite
    afin d'annuler les obligations obsolètes (aptitude SIR, mi-carrière, VIP SIR).
    """
    from app.modules.medical_follow_up.application.service import (
        compute_obligations_for_employee,
    )

    active_statuses = {"actif", "active", "en_onboarding", "en_sortie"}
    active_employees = [
        e
        for e in employees
        if (e.get("employment_status") or "actif").lower() in active_statuses
    ]

    if dry_run:
        print(
            f"[dry-run] reconcile suivi médical pour {len(active_employees)} salarié(s)"
        )
        return {"reconciled_employees": len(active_employees), "dry_run": True}

    overdue_before = (
        supabase.table("medical_follow_up_obligations")
        .select("id", count="exact")
        .eq("company_id", company_id)
        .in_("status", ["a_faire", "planifiee"])
        .lt("due_date", date.today().isoformat())
        .execute()
        .count
        or 0
    )

    for emp in active_employees:
        compute_obligations_for_employee(company_id, str(emp["id"]))

    overdue_after = (
        supabase.table("medical_follow_up_obligations")
        .select("id", count="exact")
        .eq("company_id", company_id)
        .in_("status", ["a_faire", "planifiee"])
        .lt("due_date", date.today().isoformat())
        .execute()
        .count
        or 0
    )

    print(
        "Suivi médical Comitech Composite — réconciliation effectif : "
        f"{len(active_employees)} salarié(s), "
        f"retards {overdue_before} → {overdue_after}"
    )
    return {
        "reconciled_employees": len(active_employees),
        "overdue_before": overdue_before,
        "overdue_after": overdue_after,
    }


# ---------------------------------------------------------------------------
# Comitech Composite — protection sociale (mutuelle / prévoyance / retraite sup)
# ---------------------------------------------------------------------------
def _import_benefits_data():
    scripts_root = Path(__file__).resolve().parent
    if str(scripts_root) not in sys.path:
        sys.path.insert(0, str(scripts_root))
    from comitech_benefits_data import (
        COMITECH_MUTUELLE_CATALOG,
        MUTUELLE_AMOUNT_TOLERANCE,
        PREVOYANCE_TEMPLATES,
        RETRAITE_SUP_TEMPLATES,
    )

    return (
        COMITECH_MUTUELLE_CATALOG,
        MUTUELLE_AMOUNT_TOLERANCE,
        PREVOYANCE_TEMPLATES,
        RETRAITE_SUP_TEMPLATES,
    )


def _normalize_employee_statut(statut: str | None) -> str:
    return "Cadre" if (statut or "").strip().lower() == "cadre" else "Non-Cadre"


def load_employees_pay(supabase, company_id: str) -> list[dict]:
    r = (
        supabase.table("employees")
        .select("id, first_name, last_name, statut, specificites_paie, employment_status")
        .eq("company_id", company_id)
        .execute()
    )
    return list(r.data or [])


def seed_mutuelle_catalog(
    supabase,
    company_id: str,
    *,
    benefits_year: int,
    dry_run: bool,
) -> dict[str, str]:
    """Crée ou met à jour le catalogue mutuelle Comitech ; retourne libellé → id."""
    catalog, _, _, _ = _import_benefits_data()
    libelle_to_id: dict[str, str] = {}
    upserted = 0

    for spec in catalog:
        libelle = spec["libelle"]
        is_active = spec["benefits_year"] == benefits_year
        payload = {
            "montant_salarial": spec["montant_salarial"],
            "montant_patronal": spec["montant_patronal"],
            "pack_couverture": spec["pack_couverture"],
            "statut_categoriel": "tous",
            "part_patronale_soumise_a_csg": True,
            "is_active": is_active,
            "source": "manual",
        }

        existing = (
            supabase.table("company_mutuelle_types")
            .select("id")
            .eq("company_id", company_id)
            .eq("libelle", libelle)
            .limit(1)
            .execute()
        )
        if existing.data:
            type_id = str(existing.data[0]["id"])
            if dry_run:
                print(f"[dry-run] mutuelle catalog update {libelle} active={is_active}")
            else:
                supabase.table("company_mutuelle_types").update(payload).eq(
                    "id", type_id
                ).execute()
        else:
            if dry_run:
                print(f"[dry-run] mutuelle catalog insert {libelle}")
                type_id = str(uuid.uuid4())
            else:
                row = {**payload, "company_id": company_id, "libelle": libelle}
                resp = (
                    supabase.table("company_mutuelle_types")
                    .insert(row)
                    .execute()
                )
                type_id = str(resp.data[0]["id"])
            upserted += 1

        libelle_to_id[libelle] = type_id

    print(
        f"Catalogue mutuelle Comitech : {len(catalog)} formule(s), "
        f"{upserted} création(s), année active {benefits_year}"
    )
    return libelle_to_id


def _amounts_close(a: float, b: float, tolerance: float) -> bool:
    return abs(a - b) <= tolerance


def _find_mutuelle_match(
    montant_sal: float,
    montant_pat: float,
    catalog_rows: list[dict],
    *,
    tolerance: float,
) -> dict | None:
    for row in catalog_rows:
        if _amounts_close(montant_sal, float(row["montant_salarial"]), tolerance) and _amounts_close(
            montant_pat, float(row["montant_patronal"]), tolerance
        ):
            return row
    return None


def _resolve_mutuelle_amounts(
    supabase,
    mutuelle_spec: dict,
    catalog_rows: list[dict],
) -> tuple[float, float] | None:
    type_ids = mutuelle_spec.get("mutuelle_type_ids") or []
    if type_ids:
        resp = (
            supabase.table("company_mutuelle_types")
            .select("montant_salarial, montant_patronal")
            .in_("id", type_ids)
            .limit(1)
            .execute()
        )
        if resp.data:
            row = resp.data[0]
            return float(row["montant_salarial"]), float(row["montant_patronal"])

    lignes = mutuelle_spec.get("lignes_specifiques") or []
    if lignes:
        ligne = lignes[0]
        return float(ligne.get("montant_salarial") or 0), float(
            ligne.get("montant_patronal") or 0
        )

    if mutuelle_spec.get("montant_salarial") is not None:
        return float(mutuelle_spec.get("montant_salarial") or 0), float(
            mutuelle_spec.get("montant_patronal") or 0
        )
    return None


def _default_mutuelle_libelle(benefits_year: int, pack: str = "isole") -> str:
    if benefits_year >= 2026:
        return (
            "GAN Famille 2026 (EMU4+SMU2)"
            if pack == "famille"
            else "GAN Isolé 2026 (EMU3)"
        )
    return (
        "AG2R Famille 2025 (EMU1+SMU1)"
        if pack == "famille"
        else "AG2R Isolé 2025 (EMU0)"
    )


def _assign_mutuelle_to_employee(
    supabase,
    company_id: str,
    employee_id: str,
    mutuelle_type_id: str,
    pack: str,
    specificites: dict,
    *,
    dry_run: bool,
) -> None:
    mutuelle = dict(specificites.get("mutuelle") or {})
    mutuelle.update(
        {
            "adhesion": True,
            "mutuelle_type_ids": [mutuelle_type_id],
            "pack_couverture": pack,
            "lignes_specifiques": [],
        }
    )
    specificites_updated = {**specificites, "mutuelle": mutuelle}
    if dry_run:
        return
    supabase.table("employee_mutuelle_types").delete().eq(
        "employee_id", employee_id
    ).execute()
    supabase.table("employee_mutuelle_types").upsert(
        {"employee_id": employee_id, "mutuelle_type_id": mutuelle_type_id},
        on_conflict="employee_id,mutuelle_type_id",
    ).execute()
    supabase.table("employees").update(
        {"specificites_paie": specificites_updated}
    ).eq("id", employee_id).execute()


def reconcile_employee_mutuelle(
    supabase,
    company_id: str,
    employees: list[dict],
    catalog_by_libelle: dict[str, str],
    *,
    benefits_year: int,
    dry_run: bool,
) -> tuple[int, list[str]]:
    catalog, tolerance, _, _ = _import_benefits_data()
    catalog_rows = []
    for spec in catalog:
        type_id = catalog_by_libelle.get(spec["libelle"])
        if type_id:
            catalog_rows.append({**spec, "id": type_id})

    reconciled = 0
    warnings: list[str] = []

    for emp in employees:
        if (emp.get("employment_status") or "actif") != "actif":
            continue
        emp_id = str(emp["id"])
        label = f"{emp.get('last_name')} {emp.get('first_name')}"
        specificites = emp.get("specificites_paie") or {}
        if not isinstance(specificites, dict):
            specificites = {}
        mutuelle = specificites.get("mutuelle") or {}
        if not isinstance(mutuelle, dict):
            mutuelle = {}

        amounts = _resolve_mutuelle_amounts(supabase, mutuelle, catalog_rows)
        matched: dict | None = None
        if amounts:
            matched = _find_mutuelle_match(
                amounts[0], amounts[1], catalog_rows, tolerance=tolerance
            )

        if matched:
            type_id = str(matched["id"])
            pack = matched["pack_couverture"]
            current_ids = mutuelle.get("mutuelle_type_ids") or []
            if current_ids == [type_id] and mutuelle.get("pack_couverture") == pack:
                continue
            _assign_mutuelle_to_employee(
                supabase,
                company_id,
                emp_id,
                type_id,
                pack,
                specificites,
                dry_run=dry_run,
            )
            reconciled += 1
            continue

        if mutuelle.get("mutuelle_type_ids") or mutuelle.get("adhesion"):
            warnings.append(f"{label}: mutuelle non réconciliable avec le catalogue")
            continue

        fallback_libelle = _default_mutuelle_libelle(benefits_year, "isole")
        fallback_id = catalog_by_libelle.get(fallback_libelle)
        if not fallback_id:
            warnings.append(f"{label}: formule mutuelle fallback introuvable")
            continue
        warnings.append(f"{label}: mutuelle absente DSN → isolé {benefits_year} par défaut")
        _assign_mutuelle_to_employee(
            supabase,
            company_id,
            emp_id,
            fallback_id,
            "isole",
            specificites,
            dry_run=dry_run,
        )
        reconciled += 1

    return reconciled, warnings


def _clone_template_lines(template: list[dict]) -> list[dict]:
    return [dict(line) for line in template]


def _should_expand_gan_single_line(ligne: dict) -> bool:
    patronal = float(ligne.get("patronal") or 0)
    return abs(patronal - 0.01825) < 0.0005


def _is_alptis_like(lignes: list[dict]) -> bool:
    if len(lignes) >= 3:
        return True
    total_pat = sum(float(ligne.get("patronal") or 0) for ligne in lignes)
    return total_pat > 0.025


def sync_employee_prevoyance(
    employees: list[dict],
    supabase,
    *,
    benefits_year: int,
    dry_run: bool,
) -> tuple[int, list[str]]:
    _, _, templates, _ = _import_benefits_data()
    filled = 0
    warnings: list[str] = []

    cadre_key = "gan_cadre_2026" if benefits_year >= 2026 else "gan_cadre_2025"
    nc_key = "gan_non_cadre_2026" if benefits_year >= 2026 else "mutex_non_cadre_2025"

    for emp in employees:
        if (emp.get("employment_status") or "actif") != "actif":
            continue
        emp_id = str(emp["id"])
        label = f"{emp.get('last_name')} {emp.get('first_name')}"
        statut = _normalize_employee_statut(emp.get("statut"))
        specificites = emp.get("specificites_paie") or {}
        if not isinstance(specificites, dict):
            specificites = {}
        prevoyance = specificites.get("prevoyance") or {}
        if not isinstance(prevoyance, dict):
            prevoyance = {}
        lignes = list(prevoyance.get("lignes_specifiques") or [])

        if lignes:
            if statut == "Cadre" and len(lignes) == 1:
                if _should_expand_gan_single_line(lignes[0]):
                    new_lignes = _clone_template_lines(templates[cadre_key])
                    if dry_run:
                        print(f"[dry-run] expand prévoyance GAN -> {label}")
                    else:
                        prevoyance = {
                            **prevoyance,
                            "adhesion": True,
                            "lignes_specifiques": new_lignes,
                        }
                        supabase.table("employees").update(
                            {"specificites_paie": {**specificites, "prevoyance": prevoyance}}
                        ).eq("id", emp_id).execute()
                    filled += 1
                elif _is_alptis_like(lignes):
                    warnings.append(f"{label}: prévoyance ALPTIS détectée, non modifiée")
            continue

        template_key = cadre_key if statut == "Cadre" else nc_key
        new_lignes = _clone_template_lines(templates[template_key])
        if dry_run:
            print(f"[dry-run] prévoyance {template_key} -> {label}")
        else:
            prevoyance = {
                **prevoyance,
                "adhesion": True,
                "lignes_specifiques": new_lignes,
            }
            supabase.table("employees").update(
                {"specificites_paie": {**specificites, "prevoyance": prevoyance}}
            ).eq("id", emp_id).execute()
        filled += 1
        if statut == "Cadre":
            warnings.append(f"{label}: prévoyance cadre GAN par défaut (vérifier ALPTIS si besoin)")

    return filled, warnings


def sync_employee_retraite_sup(
    employees: list[dict],
    supabase,
    *,
    benefits_year: int,
    dry_run: bool,
) -> tuple[int, list[str]]:
    if benefits_year < 2026:
        return 0, []

    _, _, _, retraite_templates = _import_benefits_data()
    filled = 0
    warnings: list[str] = []

    for emp in employees:
        if (emp.get("employment_status") or "actif") != "actif":
            continue
        if _normalize_employee_statut(emp.get("statut")) != "Cadre":
            continue
        emp_id = str(emp["id"])
        label = f"{emp.get('last_name')} {emp.get('first_name')}"
        specificites = emp.get("specificites_paie") or {}
        if not isinstance(specificites, dict):
            specificites = {}
        retraite = specificites.get("retraite_sup") or {}
        if not isinstance(retraite, dict):
            retraite = {}
        if retraite.get("lignes_specifiques"):
            continue

        new_lignes = _clone_template_lines(retraite_templates["ag2r_eres_2026"])
        if dry_run:
            print(f"[dry-run] retraite sup ERES -> {label}")
        else:
            retraite = {"adhesion": True, "lignes_specifiques": new_lignes}
            supabase.table("employees").update(
                {"specificites_paie": {**specificites, "retraite_sup": retraite}}
            ).eq("id", emp_id).execute()
        filled += 1

    return filled, warnings


def seed_protection_sociale(
    supabase,
    company_id: str,
    employees: list[dict],
    *,
    benefits_year: int,
    dry_run: bool,
) -> dict[str, Any]:
    """Catalogue mutuelle + réconciliation effectif (DSN-first)."""
    if not employees and not dry_run:
        employees = load_employees_pay(supabase, company_id)

    catalog_ids = seed_mutuelle_catalog(
        supabase, company_id, benefits_year=benefits_year, dry_run=dry_run
    )
    mutuelle_reconciled, mutuelle_warnings = reconcile_employee_mutuelle(
        supabase,
        company_id,
        employees,
        catalog_ids,
        benefits_year=benefits_year,
        dry_run=dry_run,
    )
    prevoyance_filled, prevoyance_warnings = sync_employee_prevoyance(
        employees, supabase, benefits_year=benefits_year, dry_run=dry_run
    )
    retraite_filled, retraite_warnings = sync_employee_retraite_sup(
        employees, supabase, benefits_year=benefits_year, dry_run=dry_run
    )

    all_warnings = mutuelle_warnings + prevoyance_warnings + retraite_warnings
    summary = {
        "benefits_year": benefits_year,
        "mutuelle_catalog_count": len(catalog_ids),
        "employees_mutuelle_reconciled": mutuelle_reconciled,
        "employees_prevoyance_filled": prevoyance_filled,
        "employees_retraite_sup_filled": retraite_filled,
        "warnings": all_warnings,
    }
    print(
        f"Protection sociale Comitech : mutuelle {mutuelle_reconciled}, "
        f"prévoyance {prevoyance_filled}, retraite sup {retraite_filled}, "
        f"{len(all_warnings)} avertissement(s)"
    )
    return summary


# ---------------------------------------------------------------------------
# Comitech Composite — participation 2025 (registre Quadra)
# ---------------------------------------------------------------------------
def _import_participation_data():
    scripts_root = Path(__file__).resolve().parent
    if str(scripts_root) not in sys.path:
        sys.path.insert(0, str(scripts_root))
    from comitech_participation_data import (
        COMITECH_PARTICIPATION_2025,
        PARTICIPATION_EXERCISE_LABEL,
        PARTICIPATION_EXERCISE_YEAR,
        PARTICIPATION_PAYROLL_MONTH,
        PARTICIPATION_PAYROLL_YEAR,
        PARTICIPATION_SIMULATION_NAME,
        PARTICIPATION_SOURCE,
        participation_simulation_payload,
    )

    return (
        COMITECH_PARTICIPATION_2025,
        PARTICIPATION_EXERCISE_LABEL,
        PARTICIPATION_EXERCISE_YEAR,
        PARTICIPATION_PAYROLL_MONTH,
        PARTICIPATION_PAYROLL_YEAR,
        PARTICIPATION_SIMULATION_NAME,
        PARTICIPATION_SOURCE,
        participation_simulation_payload,
    )


def _merge_participation_amounts(
    by_employee: dict[str, dict[str, Any]],
    employee_id: str,
    *,
    employee_name: str,
    gross_amount: float,
    advance_amount: float,
    advance_label: str,
) -> None:
    """Fusionne les montants si plusieurs lignes Quadra pointent vers le même salarié."""
    existing = by_employee.get(employee_id)
    if not existing:
        by_employee[employee_id] = {
            "employeeName": employee_name,
            "participationAmount": round(gross_amount, 2),
            "interessementAmount": 0.0,
            "totalAmount": round(gross_amount, 2),
            "advance_amount": round(advance_amount, 2),
            "advance_label": advance_label if advance_amount > 0 else "",
        }
        return

    existing["participationAmount"] = round(
        float(existing["participationAmount"]) + gross_amount, 2
    )
    existing["totalAmount"] = round(
        float(existing["participationAmount"]) + float(existing["interessementAmount"]), 2
    )
    if advance_amount > 0:
        existing["advance_amount"] = round(
            float(existing.get("advance_amount") or 0) + advance_amount, 2
        )
        existing["advance_label"] = advance_label


def _resolve_participation_rows(
    employees: list[dict],
    rows: tuple[Any, ...],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    by_employee: dict[str, dict[str, Any]] = {}
    missing: list[str] = []

    for row in rows:
        emp = resolve_employee(
            employees, row.last_name, row.first_hint, row.last_name_aliases
        )
        label = f"{row.last_name} {row.first_hint or ''}".strip()
        if not emp:
            missing.append(label)
            continue
        employee_id = str(emp["id"])
        employee_name = f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip()
        _merge_participation_amounts(
            by_employee,
            employee_id,
            employee_name=employee_name,
            gross_amount=float(row.gross_amount),
            advance_amount=float(row.advance_amount),
            advance_label=row.advance_label,
        )

    return by_employee, missing


def _find_participation_simulation(
    supabase, company_id: str, simulation_name: str, year: int
) -> dict | None:
    result = (
        supabase.table("participation_simulations")
        .select("id, simulation_name, year")
        .eq("company_id", company_id)
        .eq("year", year)
        .eq("simulation_name", simulation_name)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


def _find_participation_campaign(
    supabase, company_id: str, year: int, exercise_label: str
) -> dict | None:
    result = (
        supabase.table("participation_campaigns")
        .select("id, exercise_label, year, simulation_id")
        .eq("company_id", company_id)
        .eq("year", year)
        .eq("exercise_label", exercise_label)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


def _sync_missing_participation_bulletins(
    supabase,
    company_id: str,
    campaign_id: str,
    by_employee: dict[str, dict[str, Any]],
) -> int:
    """Ajoute les bulletins manquants si la campagne existe déjà."""
    from app.modules.participation.domain.bulletin_rules import compute_net_after_advances
    from app.modules.participation.infrastructure.campaign_repository import (
        campaign_repository,
    )

    existing = campaign_repository.list_bulletins(campaign_id)
    known = {
        (str(row["employee_id"]), str(row["dispositif_type"]))
        for row in existing
    }
    rows: list[dict[str, Any]] = []
    for emp_id, data in by_employee.items():
        part_amt = float(data.get("participationAmount") or 0)
        if part_amt <= 0.005:
            continue
        key = (emp_id, "participation")
        if key in known:
            continue
        advance_amount = float(data.get("advance_amount") or 0)
        non_ded, ded, _, net_final = compute_net_after_advances(
            part_amt, advance_amount
        )
        rows.append(
            {
                "campaign_id": campaign_id,
                "company_id": company_id,
                "employee_id": emp_id,
                "dispositif_type": "participation",
                "gross_amount": round(part_amt, 2),
                "csg_non_deductible": float(non_ded),
                "csg_deductible": float(ded),
                "advance_amount": round(advance_amount, 2),
                "advance_label": str(data.get("advance_label") or ""),
                "net_amount": float(net_final),
                "status": "pending",
            }
        )
    if not rows:
        return 0
    campaign_repository.insert_bulletins(rows)
    print(f"Participation Comitech Composite : {len(rows)} bulletin(s) complété(s)")
    return len(rows)


def seed_participation_2025(
    supabase,
    company_id: str,
    employees: list[dict],
    *,
    dry_run: bool,
) -> dict[str, Any]:
    """Importe simulation + campagne participation 2025 (registre Quadra)."""
    (
        rows,
        exercise_label,
        exercise_year,
        payroll_month,
        payroll_year,
        simulation_name,
        source_label,
        build_simulation_payload,
    ) = _import_participation_data()

    by_employee, missing = _resolve_participation_rows(employees, rows)
    if not by_employee:
        print(f"Participation Comitech : aucun salarié résolu ({source_label})")
        return {
            "skipped": True,
            "reason": "no_employees_resolved",
            "missing": missing,
        }

    results_data = {
        emp_id: {
            "employeeName": data["employeeName"],
            "participationAmount": data["participationAmount"],
            "interessementAmount": data["interessementAmount"],
            "totalAmount": data["totalAmount"],
        }
        for emp_id, data in by_employee.items()
    }

    simulation_action = "exists"
    simulation_id: str | None = None
    existing_sim = _find_participation_simulation(
        supabase, company_id, simulation_name, exercise_year
    )
    if existing_sim:
        simulation_id = str(existing_sim["id"])
    elif dry_run:
        simulation_action = "dry_run"
        simulation_id = "dry-run-simulation-id"
        print(
            f"[dry-run] simulation participation {exercise_year} "
            f"({len(results_data)} salarié(s))"
        )
    else:
        payload = build_simulation_payload(company_id, results_data)
        inserted = (
            supabase.table("participation_simulations")
            .insert(payload)
            .execute()
        )
        simulation_id = str(inserted.data[0]["id"])
        simulation_action = "created"

    campaign_action = "exists"
    bulletin_count = 0
    existing_campaign = _find_participation_campaign(
        supabase, company_id, exercise_year, exercise_label
    )
    if existing_campaign:
        campaign_id = str(existing_campaign["id"])
        if not dry_run:
            bulletin_count = _sync_missing_participation_bulletins(
                supabase,
                company_id,
                campaign_id,
                by_employee,
            )
    elif dry_run:
        campaign_action = "dry_run"
        campaign_id = "dry-run-campaign-id"
        bulletin_count = len(by_employee)
        print(
            f"[dry-run] campagne {exercise_label} — "
            f"{bulletin_count} bulletin(s), paie {payroll_month}/{payroll_year}"
        )
    else:
        from app.modules.participation.application import campaign_service as campaign_svc
        from app.modules.participation.schemas.campaign_requests import (
            CampaignAdvanceInput,
            CampaignAmountInput,
            ParticipationCampaignCreate,
        )

        advances = [
            CampaignAdvanceInput(
                employee_id=emp_id,
                amount=float(data.get("advance_amount") or 0),
                label=str(data.get("advance_label") or ""),
            )
            for emp_id, data in by_employee.items()
            if float(data.get("advance_amount") or 0) > 0
        ]
        amounts = [
            CampaignAmountInput(
                employee_id=emp_id,
                participation_amount=float(data["participationAmount"]),
                interessement_amount=0.0,
            )
            for emp_id, data in by_employee.items()
        ]
        detail, bulletin_count = campaign_svc.create_campaign(
            company_id,
            None,
            ParticipationCampaignCreate(
                simulation_id=simulation_id,
                year=exercise_year,
                exercise_label=exercise_label,
                payroll_year=payroll_year,
                payroll_month=payroll_month,
                advances=advances,
                amounts=amounts,
            ),
        )
        campaign_id = detail.id
        campaign_action = "created"

    print(
        f"Participation Comitech {exercise_year} : simulation {simulation_action}, "
        f"campagne {campaign_action}, {len(by_employee)} salarié(s), "
        f"{bulletin_count} bulletin(s)"
    )
    if missing:
        print("Participation — salariés introuvables :")
        for name in missing:
            print(f"  - {name}")

    return {
        "exercise_year": exercise_year,
        "simulation_id": simulation_id,
        "simulation_action": simulation_action,
        "campaign_id": campaign_id,
        "campaign_action": campaign_action,
        "employees_seeded": len(by_employee),
        "bulletins": bulletin_count,
        "missing": missing,
    }


# ---------------------------------------------------------------------------
# Comitech Composite — contingent HS (registre Excel Quadra 2025)
# ---------------------------------------------------------------------------
def _import_contingent_data():
    scripts_root = Path(__file__).resolve().parent
    if str(scripts_root) not in sys.path:
        sys.path.insert(0, str(scripts_root))
    from comitech_contingent_data import (
        COMITECH_PAID_HS_2025,
        COMITECH_RCR_ABSENCES_2025,
        COMITECH_WEEKLY_HOURS,
        CONTINGENT_HS_PAYROLL_MONTH,
        CONTINGENT_HS_SOURCE,
        CONTINGENT_RCR_SOURCE,
        CONTINGENT_SETTINGS,
        CONTINGENT_VERIFY_REFERENCE,
        CONTINGENT_VERIFY_YEAR,
    )

    return (
        COMITECH_RCR_ABSENCES_2025,
        COMITECH_WEEKLY_HOURS,
        CONTINGENT_RCR_SOURCE,
        CONTINGENT_SETTINGS,
        CONTINGENT_VERIFY_REFERENCE,
        CONTINGENT_VERIFY_YEAR,
        COMITECH_PAID_HS_2025,
        CONTINGENT_HS_SOURCE,
        CONTINGENT_HS_PAYROLL_MONTH,
    )


def seed_contingent_settings(company_id: str, *, dry_run: bool) -> dict[str, Any]:
    """Paramètres plafond HS entreprise (360 h, pauses, HS structurelles)."""
    settings = _import_contingent_data()[3]
    if dry_run:
        print(f"[dry-run] contingent Comitech Composite -> {company_id}", settings)
        return {"action": "dry_run", **settings}

    from app.modules.repos_compensateur.infrastructure.settings_repository import (
        upsert_contingent_settings,
    )

    row = upsert_contingent_settings(company_id, settings)
    print(
        "Contingent Comitech Composite : plafond "
        f"{row.get('management_contingent_hours')} h, pauses activées"
    )
    return {"action": "saved", **settings}


def sync_employee_weekly_hours(
    supabase,
    company_id: str,
    employees: list[dict],
    *,
    dry_run: bool,
) -> dict[str, Any]:
    """Force duree_hebdomadaire = 39 h pour l'effectif actif (contrat Comitech)."""
    weekly_hours = _import_contingent_data()[1]
    updated = 0
    skipped = 0

    roster = employees
    if company_id != DRY_RUN_COMPANY_ID:
        resp = (
            supabase.table("employees")
            .select("id, first_name, last_name, employment_status, duree_hebdomadaire")
            .eq("company_id", company_id)
            .execute()
        )
        roster = list(resp.data or [])

    for emp in roster:
        if (emp.get("employment_status") or "actif") not in (
            "actif",
            "active",
            "en_onboarding",
        ):
            skipped += 1
            continue
        current = emp.get("duree_hebdomadaire")
        if current is not None and abs(float(current) - weekly_hours) < 0.01:
            skipped += 1
            continue
        label = f"{emp.get('last_name')} {emp.get('first_name')}"
        if dry_run:
            print(
                f"[dry-run] duree_hebdomadaire {weekly_hours} h -> {label} "
                f"(actuel: {current})"
            )
            updated += 1
            continue
        supabase.table("employees").update({"duree_hebdomadaire": weekly_hours}).eq(
            "id", str(emp["id"])
        ).execute()
        updated += 1

    print(
        f"Contrat hebdo Comitech Composite : {updated} salarié(s) à {weekly_hours} h, "
        f"{skipped} déjà conforme(s)"
    )
    return {"weekly_hours": weekly_hours, "updated": updated, "skipped": skipped}


def _rcr_absence_exists(
    supabase,
    company_id: str,
    employee_id: str,
    source_comment: str,
) -> bool:
    resp = (
        supabase.table("absence_requests")
        .select("id")
        .eq("company_id", company_id)
        .eq("employee_id", employee_id)
        .eq("type", "repos_compensateur")
        .eq("status", "validated")
        .eq("comment", source_comment)
        .limit(1)
        .execute()
    )
    return bool(resp.data)


def seed_contingent_rcr_absences(
    supabase,
    company_id: str,
    employees: list[dict],
    *,
    dry_run: bool,
) -> dict[str, Any]:
    """Reprise des RCR 2025 depuis le registre Excel (GENAND)."""
    rows, source = _import_contingent_data()[0], _import_contingent_data()[2]
    created = 0
    skipped = 0
    missing: list[str] = []

    for row in rows:
        emp = resolve_employee(
            employees, row.last_name, row.first_hint, row.last_name_aliases
        )
        label = f"{row.last_name} {row.first_hint or ''}".strip()
        if not emp:
            missing.append(label)
            skipped += 1
            continue

        employee_id = str(emp["id"])
        comment = f"{source} — {label}"
        if _rcr_absence_exists(supabase, company_id, employee_id, comment):
            skipped += 1
            continue

        payload = {
            "company_id": company_id,
            "employee_id": employee_id,
            "type": "repos_compensateur",
            "status": "validated",
            "selected_days": [d.isoformat() for d in row.selected_days],
            "comment": comment,
        }
        if dry_run:
            print(
                f"[dry-run] RCR {len(row.selected_days)} j -> {label} "
                f"({row.selected_days[0].isoformat()}…)"
            )
            created += 1
            continue

        supabase.table("absence_requests").insert(payload).execute()
        created += 1

    print(
        f"RCR contingent Comitech Composite : {created} reprise(s), "
        f"{skipped} ignorée(s)"
    )
    if missing:
        print("RCR contingent — salariés introuvables :")
        for name in missing:
            print(f"  - {name}")

    return {"created": created, "skipped": skipped, "missing": missing}


def _paid_hs_already_seeded(
    supabase,
    employee_id: str,
    year: int,
    month: int,
    source: str,
) -> bool:
    resp = (
        supabase.table("employee_schedules")
        .select("payroll_events")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .eq("month", month)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return False
    events = rows[0].get("payroll_events") or {}
    if not isinstance(events, dict):
        return False
    return events.get("source") == source


def seed_contingent_paid_hs_2025(
    supabase,
    company_id: str,
    employees: list[dict],
    *,
    dry_run: bool,
) -> dict[str, Any]:
    """Reprise HS payées 2025 (registre Excel) via employee_schedules.payroll_events."""
    (
        _rcr,
        _wh,
        _rcr_src,
        _settings,
        _ref,
        year,
        paid_rows,
        source,
        month,
    ) = _import_contingent_data()
    created = 0
    skipped = 0
    missing: list[str] = []

    for row in paid_rows:
        emp = resolve_employee(
            employees, row.last_name, row.first_hint, row.last_name_aliases
        )
        label = f"{row.last_name} {row.first_hint or ''}".strip()
        if not emp:
            missing.append(label)
            skipped += 1
            continue

        employee_id = str(emp["id"])
        if _paid_hs_already_seeded(supabase, employee_id, year, month, source):
            skipped += 1
            continue

        payroll_events = {
            "source": source,
            "hs_realisees_mois": round(float(row.hours), 2),
        }
        if dry_run:
            print(f"[dry-run] HS payées {year}-{month:02d} {label} : {row.hours} h")
            created += 1
            continue

        supabase.table("employee_schedules").upsert(
            {
                "employee_id": employee_id,
                "company_id": company_id,
                "year": year,
                "month": month,
                "payroll_events": payroll_events,
            },
            on_conflict="employee_id,year,month",
        ).execute()
        created += 1

    print(
        f"HS payées contingent {year} Comitech Composite : {created} reprise(s), "
        f"{skipped} ignorée(s)"
    )
    if missing:
        print("HS payées — salariés introuvables :")
        for name in missing:
            print(f"  - {name}")

    return {"created": created, "skipped": skipped, "missing": missing}


def _merge_month_with_defaults(
    excel_entries: list[dict[str, Any]],
    year: int,
    month: int,
    *,
    holiday_days: set[int],
    daily_hours: float,
) -> list[dict[str, Any]]:
    """Complète le mois Excel avec jours manquants (sem. type + fériés)."""
    from scripts.comitech_calendar_parser import build_default_month_calendar

    by_jour = {
        e["jour"]: e
        for e in build_default_month_calendar(
            year, month, daily_hours=daily_hours, holiday_days=holiday_days
        )
    }
    for entry in excel_entries:
        by_jour[entry["jour"]] = entry
    _, n_days = cal_mod.monthrange(year, month)
    return [by_jour[j] for j in range(1, n_days + 1)]


def seed_planned_calendar_2026(
    supabase,
    company_id: str,
    employees: list[dict],
    *,
    dry_run: bool,
    xlsx_path: Path | None = None,
) -> dict[str, Any]:
    """Importe les heures prévues 2026 depuis le calendrier Excel Quadra."""
    from app.modules.schedules.infrastructure.repository import schedule_repository
    from app.shared.public_holidays import day_numbers_observed_holidays
    from scripts.comitech_calendar_data import (
        CALENDAR_DAILY_HOURS,
        CALENDAR_YEAR,
    )
    from scripts.comitech_calendar_parser import (
        build_default_month_calendar,
        build_planned_calendar_payload,
        load_workbook_sheets,
        parse_employee_sheet,
        sheet_mapping_by_key,
    )

    try:
        sheets = load_workbook_sheets(xlsx_path)
    except FileNotFoundError as exc:
        print(f"WARN calendrier prévu Comitech Composite : {exc}")
        return {"skipped": True, "reason": str(exc)}

    mappings = sheet_mapping_by_key()
    sheet_to_employee: dict[str, str] = {}
    unresolved_sheets: list[str] = []

    for key, mapping in mappings.items():
        if key not in sheets:
            continue
        emp = resolve_employee(
            employees,
            mapping.last_name,
            mapping.first_hint,
            mapping.last_name_aliases,
        )
        label = f"{mapping.last_name} {mapping.first_hint or ''}".strip()
        if not emp:
            unresolved_sheets.append(label)
            continue
        sheet_to_employee[key] = str(emp["id"])

    covered_ids = set(sheet_to_employee.values())
    created = 0
    skipped = 0
    months_written = 0

    def _upsert_month(employee_id: str, month: int, entries: list[dict[str, Any]]) -> None:
        nonlocal created, skipped, months_written
        payload = build_planned_calendar_payload(
            entries, year=CALENDAR_YEAR, month=month
        )
        if dry_run:
            created += 1
            months_written += 1
            return
        schedule_repository.upsert_schedule(
            employee_id,
            company_id,
            CALENDAR_YEAR,
            month,
            planned_calendar=payload,
        )
        created += 1
        months_written += 1

    for key, employee_id in sheet_to_employee.items():
        parsed = parse_employee_sheet(sheets[key], year=CALENDAR_YEAR)
        for month in range(1, 13):
            holidays = day_numbers_observed_holidays(
                CALENDAR_YEAR, month, company_id
            )
            excel_entries = parsed.get(month, [])
            entries = _merge_month_with_defaults(
                excel_entries,
                CALENDAR_YEAR,
                month,
                holiday_days=holidays,
                daily_hours=CALENDAR_DAILY_HOURS,
            )
            _upsert_month(employee_id, month, entries)

    default_employees = [
        e for e in employees if str(e["id"]) not in covered_ids
    ]
    for emp in default_employees:
        employee_id = str(emp["id"])
        for month in range(1, 13):
            holidays = day_numbers_observed_holidays(
                CALENDAR_YEAR, month, company_id
            )
            entries = build_default_month_calendar(
                CALENDAR_YEAR,
                month,
                daily_hours=CALENDAR_DAILY_HOURS,
                holiday_days=holidays,
            )
            _upsert_month(employee_id, month, entries)

    print(
        f"Calendrier prévu 2026 Comitech Composite : {months_written} mois écrit(s), "
        f"{skipped} ignoré(s) (déjà importés), "
        f"{len(sheet_to_employee)} feuille(s) Excel, "
        f"{len(default_employees)} salarié(s) en semaine type"
    )
    if unresolved_sheets:
        print("Calendrier prévu — feuilles Excel sans salarié :")
        for name in unresolved_sheets:
            print(f"  - {name}")

    return {
        "year": CALENDAR_YEAR,
        "months_written": months_written,
        "created": created,
        "skipped": skipped,
        "excel_sheets": len(sheet_to_employee),
        "default_employees": len(default_employees),
        "unresolved_sheets": unresolved_sheets,
    }


def verify_contingent_snapshot(
    company_id: str,
    *,
    dry_run: bool,
) -> dict[str, Any]:
    """Contrôle rapide du contingent au 31/12/2025 (si bulletins présents)."""
    ref_date, year = _import_contingent_data()[4], _import_contingent_data()[5]
    if dry_run:
        print(
            f"[dry-run] vérif contingent Comitech Composite au {ref_date.isoformat()}"
        )
        return {"skipped": True, "reason": "dry_run"}

    from app.modules.repos_compensateur.application.contingent_queries import (
        get_contingent_overview,
    )

    overview = get_contingent_overview(company_id, year, ref_date)
    kpis = overview.get("kpis") or {}
    exceeded = [
        row
        for row in overview.get("employees") or []
        if row.get("status") in ("management_exceeded", "cor_exceeded")
    ]
    print(
        f"Vérif contingent {year} ({ref_date.isoformat()}) : "
        f"{kpis.get('total_employees', 0)} salarié(s), "
        f"{len(exceeded)} dépassement(s)"
    )
    if exceeded:
        for row in exceeded:
            print(
                f"  - {row.get('last_name')} {row.get('first_name')} : "
                f"{row.get('total_for_ceiling')} h / "
                f"{row.get('management_contingent')} h"
            )
    return {
        "year": year,
        "reference_date": ref_date.isoformat(),
        "kpis": kpis,
        "exceeded_count": len(exceeded),
    }


def seed_contingent_hs(
    supabase,
    company_id: str,
    employees: list[dict],
    *,
    dry_run: bool,
) -> dict[str, Any]:
    """Configuration complète contingent HS Comitech Composite."""
    settings_summary = seed_contingent_settings(company_id, dry_run=dry_run)
    contract_summary = sync_employee_weekly_hours(
        supabase, company_id, employees, dry_run=dry_run
    )
    rcr_summary = seed_contingent_rcr_absences(
        supabase, company_id, employees, dry_run=dry_run
    )
    paid_hs_summary = seed_contingent_paid_hs_2025(
        supabase, company_id, employees, dry_run=dry_run
    )
    verify_summary = verify_contingent_snapshot(company_id, dry_run=dry_run)
    return {
        "settings": settings_summary,
        "weekly_hours": contract_summary,
        "rcr_2025": rcr_summary,
        "paid_hs_2025": paid_hs_summary,
        "verify_2025": verify_summary,
    }


# ---------------------------------------------------------------------------
# Orchestration Comitech Composite
# ---------------------------------------------------------------------------
def setup_company_core(
    supabase,
    company_id: str,
    *,
    dry_run: bool,
    scan_medals: bool,
) -> None:
    """Paramètres entreprise Comitech Composite (hors effectif)."""
    ensure_group_attachment(supabase, company_id, dry_run=dry_run)
    sync_company_identity(supabase, company_id, COMPANY_IDENTITY, dry_run=dry_run)
    assign_collective_agreement(supabase, company_id, dry_run=dry_run)
    apply_cp_seniority_preset(company_id, dry_run=dry_run)
    seed_cet_settings(supabase, company_id, dry_run=dry_run)
    if not dry_run:
        supabase.table("companies").update({"dsn_sync_mode": "external"}).eq(
            "id", company_id
        ).execute()
    configure_work_medals(company_id, dry_run=dry_run, scan=scan_medals)
    seed_bonus_catalog(supabase, company_id, dry_run=dry_run)
    try:
        configure_cse(supabase, company_id, dry_run=dry_run)
    except Exception as exc:
        print("CSE Comitech Composite :", exc)


def load_comitech_employees(
    supabase, company_id: str, *, dry_run: bool, ensure_stubs: bool
) -> list[dict]:
    if company_id == DRY_RUN_COMPANY_ID:
        return []
    employees = load_employees(supabase, company_id)
    if ensure_stubs:
        employees = ensure_stub_employees(
            supabase, company_id, employees, dry_run=dry_run
        )
    return employees


def run_comitech_composite_setup(options: SetupOptions) -> dict[str, Any]:
    """Point d'entrée programmatique — configuration complète Comitech Composite."""
    supabase = _get_supabase()

    company = find_company(supabase)
    if company:
        print(
            f"Comitech Composite existante : {company['id']} "
            f"({company.get('company_name')})"
        )
    else:
        print("Création Comitech Composite…")
        company = create_company(supabase, dry_run=options.dry_run)

    company_id = str(company["id"])
    print(f"\n--- Comitech Composite ({company.get('company_name')}, {company_id}) ---")

    setup_company_core(
        supabase,
        company_id,
        dry_run=options.dry_run,
        scan_medals=options.scan_medals and not options.dry_run,
    )

    need_employees = (
        options.seed_formation
        or options.seed_medical
        or options.seed_benefits
        or options.seed_participation
        or options.seed_contingent
    )
    employees: list[dict] = []
    if need_employees:
        employees = load_comitech_employees(
            supabase,
            company_id,
            dry_run=options.dry_run,
            ensure_stubs=(
                options.seed_formation
                or options.seed_medical
                or options.seed_benefits
                or options.seed_participation
                or options.seed_contingent
                or options.seed_planned_calendar
            ),
        )
        if employees:
            print(f"Effectif Comitech Composite : {len(employees)} salarié(s)")

    benefits_summary: dict[str, Any] = {"skipped": True}
    if options.seed_benefits:
        print(
            f"\n>> Protection sociale Comitech Composite (année {options.benefits_year})"
        )
        pay_employees = (
            load_employees_pay(supabase, company_id)
            if company_id != DRY_RUN_COMPANY_ID
            else employees
        )
        benefits_summary = seed_protection_sociale(
            supabase,
            company_id,
            pay_employees,
            benefits_year=options.benefits_year,
            dry_run=options.dry_run,
        )

    formation_summary: dict[str, Any] = {"skipped": True}
    if options.seed_formation:
        print(f"\n>> Formations / habilitations Comitech Composite ({FORMATION_REGISTRY_SOURCE})")
        formation_summary = seed_formation_registry(
            supabase, company_id, employees, dry_run=options.dry_run
        )

    medical_summary: dict[str, Any] = {"skipped": True}
    if options.seed_medical:
        print(f"\n>> Suivi médical Comitech Composite ({MEDICAL_REGISTRY_SOURCE})")
        configure_medical_module(supabase, company_id, dry_run=options.dry_run)
        medical_summary = seed_medical_registry(
            supabase, company_id, employees, dry_run=options.dry_run
        )
        cleanup_summary = cleanup_comitech_medical_phantoms(
            supabase, company_id, employees, dry_run=options.dry_run
        )
        medical_summary = {**medical_summary, **cleanup_summary}

    participation_summary: dict[str, Any] = {"skipped": True}
    if options.seed_participation:
        print("\n>> Participation Comitech Composite (exercice 2025 — Quadra)")
        participation_summary = seed_participation_2025(
            supabase, company_id, employees, dry_run=options.dry_run
        )

    contingent_summary: dict[str, Any] = {"skipped": True}
    if options.seed_contingent:
        print("\n>> Contingent HS Comitech Composite (registre Excel Quadra 2025)")
        if not employees and company_id != DRY_RUN_COMPANY_ID:
            employees = load_comitech_employees(
                supabase,
                company_id,
                dry_run=options.dry_run,
                ensure_stubs=True,
            )
        contingent_summary = seed_contingent_hs(
            supabase, company_id, employees, dry_run=options.dry_run
        )

    planned_calendar_summary: dict[str, Any] = {"skipped": True}
    if options.seed_planned_calendar:
        print("\n>> Calendrier prévu 2026 Comitech Composite (Excel Quadra)")
        if not employees and company_id != DRY_RUN_COMPANY_ID:
            employees = load_comitech_employees(
                supabase,
                company_id,
                dry_run=options.dry_run,
                ensure_stubs=True,
            )
        planned_calendar_summary = seed_planned_calendar_2026(
            supabase,
            company_id,
            employees,
            dry_run=options.dry_run,
            xlsx_path=options.calendar_xlsx,
        )

    return {
        "company": {
            "company_id": company_id,
            "company_name": company.get("company_name"),
            "siret": COMPANY_SIRET,
            "label": COMPANY_NAME,
        },
        "employees_count": len(employees),
        "benefits": benefits_summary,
        "formation": formation_summary,
        "medical": medical_summary,
        "participation": participation_summary,
        "contingent": contingent_summary,
        "planned_calendar": planned_calendar_summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configuration initiale complète Comitech Composite dans EYWAI"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--skip-scan",
        action="store_true",
        help="Ne pas lancer le scan médailles sur l'effectif Comitech Composite",
    )
    parser.add_argument(
        "--skip-medical",
        action="store_true",
        help="Ne pas importer le registre SPST visites médicales Comitech Composite",
    )
    parser.add_argument(
        "--skip-formation",
        action="store_true",
        help="Ne pas importer habilitations / formations / budget Comitech Composite",
    )
    parser.add_argument(
        "--skip-benefits",
        action="store_true",
        help="Ne pas configurer mutuelle / prévoyance / retraite sup Comitech Composite",
    )
    parser.add_argument(
        "--skip-participation",
        action="store_true",
        help="Ne pas importer simulation / campagne participation 2025 Comitech Composite",
    )
    parser.add_argument(
        "--skip-contingent",
        action="store_true",
        help="Ne pas configurer contingent HS / contrat 39 h / RCR 2025 Comitech Composite",
    )
    parser.add_argument(
        "--skip-planned-calendar",
        action="store_true",
        help="Ne pas importer le calendrier prévu 2026 (Excel Quadra)",
    )
    parser.add_argument(
        "--calendar-xlsx",
        type=Path,
        default=None,
        help="Chemin vers le fichier Excel calendrier 2026 (défaut : scripts/data/)",
    )
    parser.add_argument(
        "--benefits-year",
        type=int,
        choices=(2025, 2026),
        default=2026,
        help="Année de référence protection sociale (défaut 2026)",
    )
    args = parser.parse_args()

    summary = run_comitech_composite_setup(
        SetupOptions(
            dry_run=args.dry_run,
            scan_medals=not args.skip_scan,
            seed_medical=not args.skip_medical,
            seed_formation=not args.skip_formation,
            seed_benefits=not args.skip_benefits,
            seed_participation=not args.skip_participation,
            seed_contingent=not args.skip_contingent,
            seed_planned_calendar=not args.skip_planned_calendar,
            calendar_xlsx=args.calendar_xlsx,
            benefits_year=args.benefits_year,
        )
    )

    print("\nRésumé Comitech Composite :")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
