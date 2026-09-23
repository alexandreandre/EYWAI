"""Critère de la spec 2026-09-23 : une prime ajoutée depuis le bulletin donne,
au centime, le même bulletin que la même prime saisie dans l'onglet Primes.

Le contrôle **régénère deux fois** un bulletin puis le remet en état
(`payslip_data` et variables du mois). L'historique des versions et le PDF, eux,
gardent la trace des deux passages. Il ne se lance donc que sur un bulletin
choisi exprès, jamais sur un brouillon en cours de travail, et avec l'accord
d'Alexandre (mémoire « jamais régénérer un bulletin sans accord »).

Garde-fous :
- `--je-confirme` obligatoire ;
- refus si le bulletin n'est pas un brouillon calculé ;
- refus s'il a été modifié dans les deux dernières heures.

Usage :
    python -m scripts.verif_prime_depuis_le_bulletin --societe ID --salarie NOM \
        --annee 2026 --mois 8 --je-confirme
"""

from __future__ import annotations

import copy
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PRIME = {
    "name": "Prime contrôle",
    "amount": 100.0,
    "is_socially_taxed": True,
    "is_taxable": True,
    "catalog_prime_id": None,
}


def _arg(nom: str) -> str | None:
    return sys.argv[sys.argv.index(nom) + 1] if nom in sys.argv else None


def _releve(payslip: dict) -> dict[str, float]:
    """Ce qui doit suivre une prime : brut, cotisations, net, cumuls."""
    d = payslip["payslip_data"]
    structure = d.get("structure_cotisations") or {}
    cumuls = (d.get("cumuls") or {}).get("cumuls") or {}
    return {
        "brut": round(float(d.get("salaire_brut") or 0), 2),
        "cotis_salariales": round(float(structure.get("total_salarial") or 0), 2),
        "cotis_patronales": round(float(structure.get("total_patronal") or 0), 2),
        "net_a_payer": round(float(d.get("net_a_payer") or 0), 2),
        "cumul_brut": round(float(cumuls.get("brut_total") or 0), 2),
        "cumul_net_imposable": round(float(cumuls.get("net_imposable") or 0), 2),
    }


def main() -> int:
    societe, nom = _arg("--societe"), (_arg("--salarie") or "").upper()
    annee, mois = int(_arg("--annee") or 0), int(_arg("--mois") or 0)
    if "--je-confirme" not in sys.argv or not (societe and nom and annee and mois):
        print(__doc__)
        return 2

    from app.core.database import supabase
    from app.modules.payslips.application.commands import edit_payslip, generate_payslip
    from app.modules.payslips.application.dto import EditPayslipInput, GeneratePayslipInput

    emp = next(
        (e for e in supabase.table("employees").select("id, last_name").eq("company_id", societe).execute().data
         if str(e["last_name"]).upper() == nom),
        None,
    )
    if emp is None:
        print(f"!! aucun salarié {nom} dans la société")
        return 1
    eid = str(emp["id"])

    def bulletin() -> dict:
        return (supabase.table("payslips").select("*").eq("employee_id", eid)
                .eq("year", annee).eq("month", mois).single().execute().data)

    def saisies() -> list[dict]:
        return (supabase.table("monthly_inputs").select("*").eq("employee_id", eid)
                .eq("year", annee).eq("month", mois).execute().data or [])

    origine = bulletin()
    if origine.get("status") != "brouillon" or origine.get("origine") == "importe":
        print("!! bulletin non brouillon ou importé — rien n'est fait")
        return 1
    modifie = datetime.fromisoformat(str(origine["updated_at"]).replace("Z", "+00:00"))
    if datetime.now(timezone.utc) - modifie < timedelta(hours=2):
        print(f"!! bulletin modifié à {modifie:%H:%M} UTC : peut-être en cours de travail — rien n'est fait")
        return 1
    ids_origine = {s["id"] for s in saisies()}

    def restaurer() -> None:
        for sid in {s["id"] for s in saisies()} - ids_origine:
            supabase.table("monthly_inputs").delete().eq("id", sid).execute()
        supabase.table("payslips").update({"payslip_data": origine["payslip_data"]}).eq(
            "id", origine["id"]).execute()

    regen = GeneratePayslipInput(employee_id=eid, year=annee, month=mois,
                                 force_calendrier_incomplet=True, regenerer_bulletin_valide=True)
    try:
        # Chemin A : la prime saisie comme variable du mois (onglet Primes).
        supabase.table("monthly_inputs").insert(
            {**PRIME, "employee_id": eid, "company_id": societe, "year": annee, "month": mois}).execute()
        generate_payslip(regen)
        a = _releve(bulletin())
        restaurer()

        # Chemin B : la même prime ajoutée depuis l'écran de modification.
        data = copy.deepcopy(origine["payslip_data"])
        data.setdefault("calcul_du_brut", []).append({
            "libelle": PRIME["name"], "quantite": None, "taux": None, "gain": PRIME["amount"],
            "perte": None, "is_sous_total": False, "nouvelle_saisie": dict(PRIME)})
        resultat = edit_payslip(EditPayslipInput(
            payslip_id=origine["id"], payslip_data=data, changes_summary="Contrôle prime depuis le bulletin",
            current_user_id="script", current_user_name="Contrôle automatique"))
        if resultat.get("recalcul_erreur"):
            print(f"!! recalcul impossible : {resultat['recalcul_erreur']}")
            return 1
        b = _releve(bulletin())
    finally:
        restaurer()

    if bulletin()["payslip_data"] != origine["payslip_data"]:
        print("!! la remise en état du bulletin a échoué")
        return 1
    ecarts = {k: (a[k], b[k]) for k in a if abs(a[k] - b[k]) > 0.01}
    print(f"{'':22s} {'onglet Primes':>14s} {'depuis le bulletin':>19s}")
    for k in a:
        print(f"  {k:20s} {a[k]:>14.2f} {b[k]:>19.2f}")
    print("IDENTIQUES au centime ; bulletin remis en état" if not ecarts else f"!! ÉCARTS : {ecarts}")
    return 1 if ecarts else 0


if __name__ == "__main__":
    sys.exit(main())
