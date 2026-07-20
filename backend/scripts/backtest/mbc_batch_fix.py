"""Corrections automatiques par lot pour le backtest MBC mai 2026.

Applique les patterns déjà catalogués (prévoyance 0,5%/0,5%, mutuelle,
participation + acompte, primes/paniers/prêts taggés) détectés dans le texte
brut du bulletin de référence, pour accélérer le traitement salarié par
salarié (cf. .claude/skills/backtest-paie-auto).

Usage (depuis backend/):
    .venv/bin/python -m scripts.backtest.mbc_batch_fix MATRICULE1 MATRICULE2 ...
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins

COMPANY = "Mont Blanc Composite"
YEAR, MONTH = 2026, 5

_PREVOYANCE_RE = re.compile(r"PREVOYANCE.*?([\d.]+\.\d+)\s+0\.5000\s+", re.IGNORECASE)
_MUTUELLE_RE = re.compile(
    r"^\s*EMU\d\s+(GAN Mut[^\n]*?)\s+[\d.]+\.\d{2}(?:\s+[\d.]+\.\d{4})?\s+([\d.]+\.\d{2})(?:\s+([\d.]+\.\d{2}))?(?=\s{2,}|\s*$)",
    re.MULTILINE,
)
_PARTICIPATION_RE = re.compile(
    r"^\s*Participation(?:\s*2025)?\s+([\d]+\.\d{2})\s+([\d]+\.\d{2})(?=\s{2,}|\s*$)",
    re.MULTILINE,
)
_ACOMPTE_RE = re.compile(
    r"Avance participation\s*(\d{4})?\s+(-[\d]+\.\d{2})\s+(-[\d]+\.\d{2})", re.IGNORECASE
)
_PRET_RE = re.compile(
    r"^\s*(?:SAVV|SAVU|SAVP|SAWZ|SAWY|SBUS)\s+(Contrat de pr[êe]t[^\n]*?)\s+-([\d]+\.\d{2})\s+-([\d]+\.\d{2})(?=\s{2,}|\s*$)",
    re.MULTILINE,
)
_CANTINE_RE = re.compile(
    r"^\s*SCAN\s+(Cantine)\s+-[\d.]+\s+[\d.]+\s+-([\d]+\.\d{2})(?=\s{2,}|\s*$)", re.MULTILINE
)
_TAGGED_PRIME_RE = re.compile(
    r"^\s*(BAA|BPAN|BSIC|SPAN|SND\w?)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'.() ]*?)\s+"
    r"([\d.]+\.\d{2})(?:\s+([\d.]+\.\d{4}))?\s+([\d.]+\.\d{2})(?=\s{2,}|\s*$)",
    re.MULTILINE,
)

NON_TAXED_LABELS = ("panier", "indemnité forfaitaire", "indemnite forfaitaire", "déplacement", "deplacement")


def _normalize(s: str) -> str:
    return "".join(c for c in s.upper() if c.isalnum())


def diagnose(employee_id: str, matricule: str, ref, admin) -> dict:
    """Retourne les corrections détectées (sans les appliquer)."""
    text = ref.raw_text or ""
    findings: dict = {}

    m = _PREVOYANCE_RE.search(text)
    if m:
        findings["prevoyance_0_5"] = True

    mutuelle_matches = _MUTUELLE_RE.findall(text)
    if mutuelle_matches:
        label, m1, _m2 = mutuelle_matches[0]
        # m1 (le premier montant après le taux, ou le seul montant s'il n'y en
        # a qu'un) est la valeur fiable ; un 2e nombre peut être un artefact
        # de mise en page (ex. SMIC horaire 12.02 qui déborde sur la ligne).
        findings["mutuelle"] = (label.strip(), float(m1))

    part_matches = _PARTICIPATION_RE.findall(text)
    if part_matches:
        base, montant = part_matches[0]
        findings["participation_amount"] = float(base)

    acompte_m = _ACOMPTE_RE.search(text)
    if acompte_m:
        findings["acompte"] = float(acompte_m.group(2))

    for label, montant_s, montant_p in _PRET_RE.findall(text):
        findings.setdefault("prets", []).append((label.strip(), -float(montant_s)))

    cantine_m = _CANTINE_RE.search(text)
    if cantine_m:
        findings["cantine"] = -float(cantine_m.group(2))

    primes = []
    for code, label, base_or_amount, taux, montant in _TAGGED_PRIME_RE.findall(text):
        label = label.strip()
        amount = float(montant)
        qty = float(base_or_amount) if taux else None
        primes.append((code, label, amount, qty))
    if primes:
        findings["primes"] = primes

    return findings


def apply_fixes(employee_id: str, company_id: str, findings: dict, admin, *, dry_run: bool = False) -> list[str]:
    actions: list[str] = []

    emp = admin.table("employees").select("specificites_paie,classification_conventionnelle").eq("id", employee_id).single().execute().data
    sp = emp.get("specificites_paie") or {}
    changed_sp = False

    if findings.get("prevoyance_0_5") and sp.get("prevoyance", {}).get("adhesion"):
        lignes = sp["prevoyance"].get("lignes_specifiques")
        if not lignes:
            sp["prevoyance"]["lignes_specifiques"] = [
                {
                    "id": "prevoyance_dsn",
                    "base": "brut_plafonne",
                    "libelle": "Prévoyance (import DSN)",
                    "patronal": 0.005,
                    "salarial": 0.005,
                    "forfait_social": 0.08,
                }
            ]
            changed_sp = True
            actions.append("prevoyance: lignes_specifiques créées 0.5%/0.5%")
        elif lignes[0].get("patronal") != 0.005 or lignes[0].get("salarial") != 0.005:
            lignes[0]["patronal"] = 0.005
            lignes[0]["salarial"] = 0.005
            changed_sp = True
            actions.append("prevoyance: taux corrigé -> 0.5%/0.5%")

    if "mutuelle" in findings and sp.get("mutuelle", {}).get("adhesion"):
        label, montant = findings["mutuelle"]
        statut = (
            (emp.get("classification_conventionnelle") or {}).get("statut_categoriel") or "non_cadre"
        ).lower().replace("-", "_")
        if not dry_run:
            existing = (
                admin.table("company_mutuelle_types")
                .select("id,montant_salarial,montant_patronal")
                .eq("company_id", company_id)
                .eq("montant_salarial", montant)
                .eq("montant_patronal", montant)
                .execute()
                .data
            )
            if existing:
                new_id = existing[0]["id"]
            else:
                created = (
                    admin.table("company_mutuelle_types")
                    .insert(
                        {
                            "company_id": company_id,
                            "libelle": f"Mutuelle Autre {montant:.2f}€ / {montant:.2f}€",
                            "montant_salarial": montant,
                            "montant_patronal": montant,
                            "part_patronale_soumise_a_csg": True,
                            "is_active": True,
                            "pack_couverture": "autre",
                            "statut_categoriel": statut,
                            "source": "manual",
                        }
                    )
                    .execute()
                    .data
                )
                new_id = created[0]["id"]
            current_ids = sp.get("mutuelle", {}).get("mutuelle_type_ids") or []
            if current_ids != [new_id]:
                sp["mutuelle"]["mutuelle_type_ids"] = [new_id]
                changed_sp = True
                actions.append(f"mutuelle: repointé sur {montant:.2f}€/{montant:.2f}€ ({new_id})")

    if changed_sp and not dry_run:
        admin.table("employees").update({"specificites_paie": sp}).eq("id", employee_id).execute()

    existing_inputs = (
        admin.table("monthly_inputs")
        .select("id,name,amount")
        .eq("employee_id", employee_id)
        .eq("year", YEAR)
        .eq("month", MONTH)
        .execute()
        .data
    )
    existing_by_norm = {_normalize(r["name"]): r for r in existing_inputs}

    def ensure_input(name: str, amount: float, *, taxed: bool, qty: float | None = None):
        norm = _normalize(name)
        row = existing_by_norm.get(norm)
        if row:
            if abs((row.get("amount") or 0) - amount) > 0.01:
                if not dry_run:
                    admin.table("monthly_inputs").update({"amount": amount}).eq("id", row["id"]).execute()
                actions.append(f"input '{name}': montant corrigé {row.get('amount')} -> {amount}")
            return
        if not dry_run:
            payload = {
                "employee_id": employee_id,
                "company_id": company_id,
                "year": YEAR,
                "month": MONTH,
                "name": name,
                "amount": amount,
                "is_socially_taxed": taxed,
                "is_taxable": taxed,
            }
            if qty is not None:
                payload["payroll_quantity"] = qty
            admin.table("monthly_inputs").insert(payload).execute()
        actions.append(f"input '{name}' ajouté: {amount}" + (f" (qty={qty})" if qty else ""))

    if "participation_amount" in findings:
        # Cherche une entrée participation existante (nom contenant "participation"
        # + "numéraire"/"2025"), sinon en crée une.
        part_row = next(
            (
                r
                for r in existing_inputs
                if "PARTICIPATION" in _normalize(r["name"]) and "AVANCE" not in _normalize(r["name"])
            ),
            None,
        )
        amount = findings["participation_amount"]
        if part_row:
            if abs((part_row.get("amount") or 0) - amount) > 0.01:
                if not dry_run:
                    admin.table("monthly_inputs").update({"amount": amount}).eq("id", part_row["id"]).execute()
                actions.append(f"participation: montant corrigé {part_row.get('amount')} -> {amount}")
        else:
            ensure_input("Participation 2025 — numéraire", amount, taxed=False)
            # is_taxable doit rester True pour la participation (imposable IR) ;
            # ensure_input met taxed=False pour les deux, on corrige is_taxable.
            if not dry_run:
                row = (
                    admin.table("monthly_inputs")
                    .select("id")
                    .eq("employee_id", employee_id)
                    .eq("year", YEAR)
                    .eq("month", MONTH)
                    .eq("name", "Participation 2025 — numéraire")
                    .execute()
                    .data
                )
                if row:
                    admin.table("monthly_inputs").update({"is_taxable": True}).eq("id", row[0]["id"]).execute()

    if "acompte" in findings:
        ensure_input("Avance participation 2025 (déjà versée)", findings["acompte"], taxed=False)

    if "cantine" in findings:
        ensure_input("Cantine", findings["cantine"], taxed=True)

    for label, amount in findings.get("prets", []):
        ensure_input(label, amount, taxed=False)

    for code, label, amount, qty in findings.get("primes", []):
        is_non_taxed = (
            "soumises" not in label.lower()
            and (any(term in label.lower() for term in NON_TAXED_LABELS) or code == "SPAN")
        )
        ensure_input(label, amount, taxed=not is_non_taxed, qty=qty)

    return actions


def main():
    matricules = sys.argv[1:]
    admin = get_supabase_admin_client()
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH)
    cid = resolve_company_id(COMPANY)
    matches = {m.matricule: m for m in match_employees(cid, refs).matched}

    for matricule in matricules:
        m = matches.get(matricule)
        if not m:
            print(f"[{matricule}] introuvable dans l'appariement")
            continue
        findings = diagnose(m.employee_id, matricule, m.reference, admin)
        actions = apply_fixes(m.employee_id, cid, findings, admin)
        print(f"[{matricule}] {len(actions)} action(s):")
        for a in actions:
            print(f"    {a}")


if __name__ == "__main__":
    main()
