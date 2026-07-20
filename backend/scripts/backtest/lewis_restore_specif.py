"""Restaure specificites_paie (prévoyance + mutuelle) des salariés Lewis depuis
leur bulletin de MAI 2026, SANS toucher aux monthly_inputs.

Contexte : le reconciler réécrit `specificites_paie.prevoyance` et réassigne la
mutuelle depuis le bulletin du mois traité. En enchaînant jan→avr, la dernière
écriture (avril) peut diverger des valeurs correctes de mai pour certains
salariés (ex. prévoyance TU2 présente en mai mais pas en avril), régressant mai.
Ce script recale la prévoyance + la mutuelle sur les valeurs MAI (référence
protégée), sans re-générer les monthly_inputs (qui, eux, sont scopés par mois et
restent corrects).

Usage : .venv/bin/python -m scripts.backtest.lewis_restore_specif MATRICULE [...]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.bulletins_source import resolve_bulletin_pdf
from scripts.backtest import lewis_reconcile as LR

YEAR, MONTH = 2026, 5


def restore(admin, match, company_id) -> str:
    exp = LR.parse_reference(match.reference.raw_text or "")
    emp = (admin.table("employees").select("specificites_paie")
           .eq("id", match.employee_id).single().execute().data)
    sp = emp.get("specificites_paie") or {}
    actions = []

    # Prévoyance : recaler sur les lignes du bulletin de mai.
    if exp.prevoyance:
        prev = sp.setdefault("prevoyance", {})
        prev["adhesion"] = True
        lignes = []
        for i, (tu, sr, pr) in enumerate(exp.prevoyance):
            base_id = "brut_plafonne" if tu == "TU1" else "tranche_2"
            lignes.append({
                "id": f"prev_meta_{tu.lower()}_{i}", "base": base_id,
                "libelle": f"Prévoyance META {tu} (import bulletin mai)",
                "patronal": pr, "salarial": sr, "forfait_social": 0.08,
            })
        prev["lignes_specifiques"] = lignes
        actions.append("prév " + "+".join(f"{tu}:{sr*100:.2f}/{pr*100:.2f}"
                                           for tu, sr, pr in exp.prevoyance))

    # Mutuelle : réassigner vers le type existant portant les montants de mai
    # (jamais d'édition in-place ; barèmes créés lors du backtest de mai).
    if exp.mutuelle is not None:
        sal, pat = exp.mutuelle
        existing = (admin.table("company_mutuelle_types").select("id")
                    .eq("company_id", company_id).eq("montant_salarial", sal)
                    .eq("montant_patronal", pat).eq("is_active", True)
                    .limit(1).execute().data)
        if existing:
            tid = existing[0]["id"]
            if LR._mutuelle_type_ids(sp) != [tid]:
                sp.setdefault("mutuelle", {})["mutuelle_type_ids"] = [tid]
                actions.append(f"mut→{sal}/{pat}")

    admin.table("employees").update({"specificites_paie": sp}).eq(
        "id", match.employee_id).execute()

    # Arbitrage CP 1/10e : ré-injecter brut_reference_n_1 (back-calc depuis
    # l'arbitrage du bulletin de MAI) dans les cumuls d'AVRIL, lus par l'arbitrage
    # de mai. La régénération d'avril (reconcile) écrase ce cumul avec le brut YTD
    # réel → l'arbitrage de mai dérive. On le recale ici. (Ne PAS régénérer avril
    # après ce recalage, sinon il faudra le refaire.)
    if exp.arbitrage_cp and exp.cp_days:
        base_ref = round(exp.arbitrage_cp * 30.0 / (0.10 * len(exp.cp_days)), 2)
        prow = (admin.table("employee_schedules").select("id,cumuls")
                .match({"employee_id": match.employee_id, "year": 2026, "month": 4})
                .maybe_single().execute())
        if prow and prow.data:
            cum = prow.data.get("cumuls") or {}
            nested = cum.setdefault("cumuls", {}) if isinstance(cum, dict) else {}
            nested["brut_reference_n_1"] = base_ref
            admin.table("employee_schedules").update({"cumuls": cum}).eq(
                "id", prow.data["id"]).execute()
            actions.append(f"ref 1/10e→{base_ref}")
    return ", ".join(actions) or "rien"


def main():
    LR.YEAR, LR.MONTH = YEAR, MONTH  # pour parse_reference (filtrage CP)
    wanted = set(sys.argv[1:])
    admin = get_supabase_admin_client()
    pdf = resolve_bulletin_pdf("Lewis", YEAR, MONTH)
    refs = load_reference_bulletins("Lewis", YEAR, MONTH, pdf_path=pdf)
    cid = resolve_company_id("Lewis")
    matched = match_employees(cid, refs).matched
    if wanted:
        matched = [m for m in matched if m.matricule in wanted]
    for m in matched:
        try:
            act = restore(admin, m, cid)
            print(f"[{m.matricule:12s}] {act}", flush=True)
        except Exception as exc:
            print(f"[{m.matricule:12s}] ERREUR {exc}", flush=True)


if __name__ == "__main__":
    main()
