#!/usr/bin/env python3
"""Backtest paie — participation Colorplast 2025 sur le bulletin de mai 2026 (M. BUGNY).

Ce script *réutilisable* injecte les trois opérations ponctuelles présentes sur le
bulletin Cegid de référence, puis régénère le bulletin EYWAI pour vérifier qu'il
coïncide :

  1. Participation 2025 — numéraire (BRUT) : le moteur applique le régime participation
     (exonération de cotisations sociales, CSG/CRDS 9,7 %, part numéraire imposable IR).
  2. Acompte participation déjà versé : déduit du net à payer (ligne non soumise négative).
  3. Remboursement de note de frais : ajouté au net (ligne non soumise, non imposable).

Les lignes sont écrites dans `monthly_inputs` via le **client admin** (service_role,
donc RLS contournée). L'opération est **idempotente** : les lignes gérées par ce
script sont supprimées puis recréées à chaque exécution (repérées par leur libellé).

⚠️  dev et prod partagent la même instance Supabase. Par sécurité, le script est en
    mode *aperçu* par défaut ; ajoutez `--apply` pour écrire réellement en base et
    régénérer le bulletin.

Exemples :
    python -m scripts.backtest_bugny_participation                 # aperçu (aucune écriture)
    python -m scripts.backtest_bugny_participation --apply         # injecte + régénère
    python -m scripts.backtest_bugny_participation --apply \
        --employee-folder BUGNY_Michel --year 2026 --month 5 \
        --participation-brut 3936.59 --acompte 1000 --note-de-frais 569.59
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Permet l'exécution directe (`python scripts/backtest_bugny_participation.py`)
# aussi bien qu'en module (`python -m scripts.backtest_bugny_participation`).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import get_supabase_admin_client, supabase  # noqa: E402

# --- Paramètres par défaut (référence Cegid — participation Colorplast 2025) --------
DEFAULT_EMPLOYEE_FOLDER = "BUGNY_Michel"
DEFAULT_YEAR = 2026
DEFAULT_MONTH = 5

# Participation brute après plafonnement (net = brut − CSG/CRDS 9,7 %).
DEFAULT_PARTICIPATION_BRUT = 3936.59
DEFAULT_ACOMPTE = 1000.0  # avance déjà versée, déduite ce mois-ci
DEFAULT_NOTE_DE_FRAIS = 569.59

# Libellés des lignes gérées par le script (servent aussi de clé d'idempotence).
LABEL_PARTICIPATION = "Participation 2025 — numéraire"
LABEL_ACOMPTE = "Acompte participation 2025 (déjà versé)"
LABEL_NOTE_DE_FRAIS = "Remboursement note de frais (participation)"


def _fmt(value) -> str:
    try:
        return f"{float(value):,.2f} €".replace(",", " ").replace(".", ",")
    except (TypeError, ValueError):
        return str(value)


def resolve_employee(folder: str) -> dict:
    """Retrouve le salarié par son dossier (employee_folder_name), repli sur le nom."""
    res = (
        supabase.table("employees")
        .select("id, company_id, first_name, last_name, employee_folder_name")
        .eq("employee_folder_name", folder)
        .execute()
    )
    rows = res.data or []
    if not rows:
        last_name = folder.split("_")[0]
        res = (
            supabase.table("employees")
            .select("id, company_id, first_name, last_name, employee_folder_name")
            .ilike("last_name", f"%{last_name}%")
            .execute()
        )
        rows = res.data or []
    if not rows:
        raise SystemExit(f"❌ Aucun salarié trouvé pour '{folder}'.")
    if len(rows) > 1:
        print("⚠️  Plusieurs salariés correspondent :")
        for r in rows:
            print(f"    - {r['first_name']} {r['last_name']} "
                  f"(dossier={r.get('employee_folder_name')}, id={r['id']})")
        raise SystemExit("Précisez --employee-folder pour lever l'ambiguïté.")
    return rows[0]


def build_managed_inputs(args) -> list[dict]:
    """Lignes monthly_inputs gérées par le script (brut pour la participation)."""
    inputs: list[dict] = []
    if args.participation_brut > 0:
        inputs.append(
            {
                "name": LABEL_PARTICIPATION,
                "description": "Participation aux bénéfices — exercice 2025 (part numéraire brute)",
                "amount": round(args.participation_brut, 2),
                # Régime participation : le moteur applique CSG/CRDS 9,7 % + IR.
                "is_socially_taxed": False,
                "is_taxable": True,
            }
        )
    if args.acompte > 0:
        inputs.append(
            {
                "name": LABEL_ACOMPTE,
                "description": "Avance sur participation déjà versée, déduite du net",
                "amount": round(-abs(args.acompte), 2),  # négatif = déduction du net
                "is_socially_taxed": False,
                "is_taxable": False,
            }
        )
    if args.note_de_frais > 0:
        inputs.append(
            {
                "name": LABEL_NOTE_DE_FRAIS,
                "description": "Remboursement de note de frais (non soumis)",
                "amount": round(args.note_de_frais, 2),
                "is_socially_taxed": False,
                "is_taxable": False,
            }
        )
    return inputs


def apply_inputs(
    admin, employee_id: str, company_id: str, year: int, month: int, inputs: list[dict]
) -> None:
    """Réécrit (idempotent) les lignes gérées pour ce salarié / mois."""
    labels = [i["name"] for i in inputs] + [
        LABEL_PARTICIPATION,
        LABEL_ACOMPTE,
        LABEL_NOTE_DE_FRAIS,
    ]
    admin.table("monthly_inputs").delete().eq("employee_id", employee_id).eq(
        "year", year
    ).eq("month", month).in_("name", list(set(labels))).execute()

    payload = [
        {
            **i,
            "employee_id": employee_id,
            "company_id": company_id,
            "year": year,
            "month": month,
        }
        for i in inputs
    ]
    if payload:
        admin.table("monthly_inputs").insert(payload).execute()


def print_bulletin_summary(employee_id: str, year: int, month: int) -> None:
    """Relit le bulletin régénéré (table payslips) et affiche la synthèse des nets."""
    res = (
        supabase.table("payslips")
        .select("payslip_data")
        .match({"employee_id": employee_id, "year": year, "month": month})
        .maybe_single()
        .execute()
    )
    data = (res.data or {}).get("payslip_data") if res else None
    if not data:
        print("⚠️  Bulletin introuvable après génération.")
        return
    synth = data.get("synthese_net", {}) or {}
    print("\n===== Bulletin régénéré — synthèse =====")
    print(f"  Salaire brut         : {_fmt(data.get('salaire_brut'))}")
    print(f"  Net social           : {_fmt(synth.get('montant_net_social'))}")
    print(f"  Net imposable        : {_fmt(synth.get('net_imposable'))}")
    pas = (synth.get("impot_prelevement_a_la_source") or {}).get("montant")
    print(f"  Prélèvement à la source: {_fmt(pas)}")
    print(f"  Acompte déduit       : {_fmt(synth.get('acompte_verse'))}")
    print(f"  NET À PAYER          : {_fmt(data.get('net_a_payer'))}")
    for p in data.get("participations", []) or []:
        print(
            f"  · Participation      : brut {_fmt(p.get('brut'))} "
            f"− CSG {_fmt(p.get('csg_total'))} = net {_fmt(p.get('brut', 0) - p.get('csg_total', 0))}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--employee-folder", default=DEFAULT_EMPLOYEE_FOLDER)
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    parser.add_argument("--month", type=int, default=DEFAULT_MONTH)
    parser.add_argument("--participation-brut", type=float, default=DEFAULT_PARTICIPATION_BRUT)
    parser.add_argument("--acompte", type=float, default=DEFAULT_ACOMPTE)
    parser.add_argument("--note-de-frais", type=float, default=DEFAULT_NOTE_DE_FRAIS)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Écrit réellement en base et régénère le bulletin (sinon simple aperçu).",
    )
    args = parser.parse_args()

    emp = resolve_employee(args.employee_folder)
    inputs = build_managed_inputs(args)

    print(f"Salarié : {emp['first_name']} {emp['last_name']} "
          f"(id={emp['id']}, société={emp['company_id']})")
    print(f"Période : {args.month:02d}/{args.year}")
    print("Lignes à injecter dans monthly_inputs :")
    for i in inputs:
        print(f"  - {i['name']:<45} {_fmt(i['amount'])} "
              f"(cotis={i['is_socially_taxed']}, imposable={i['is_taxable']})")

    if not args.apply:
        print("\n(aperçu — aucune écriture. Ajoutez --apply pour injecter + régénérer.)")
        return

    admin = get_supabase_admin_client()
    apply_inputs(admin, emp["id"], emp["company_id"], args.year, args.month, inputs)
    print("\n✅ Lignes injectées. Régénération du bulletin…")

    from app.modules.payroll.documents.payslip_generator import (
        process_payslip_generation,
    )

    result = process_payslip_generation(emp["id"], args.year, args.month)
    print(f"✅ {result.get('message')}")
    if result.get("warnings"):
        print("Alertes RH :")
        for w in result["warnings"]:
            print(f"  · {w}")

    print_bulletin_summary(emp["id"], args.year, args.month)


if __name__ == "__main__":
    main()
