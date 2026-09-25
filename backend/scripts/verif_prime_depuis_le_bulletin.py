"""Critère de la spec 2026-09-23 : une prime ajoutée depuis le bulletin donne,
au centime, le même bulletin que la même prime saisie dans l'onglet Primes.

Le contrôle **régénère deux fois** un bulletin. Tout ce qu'une régénération
touche est donc photographié avant, écrit sur disque, puis remis à l'identique
et vérifié champ par champ :

- la ligne `payslips` entière (contenu, historique des versions, compteur
  d'éditions, statut, URL, chemin du PDF) ;
- le PDF lui-même, dans le stockage ;
- la ligne `employee_schedules` du mois (les cumuls y sont réécrits) ;
- les variables du mois (`monthly_inputs`) ;
- les crédits de repos compensateur de l'année (recalculés à chaque génération) ;
- les retenues de saisie et remboursements d'avance rattachés au bulletin
  (contrôlés : le salarié choisi ne doit en avoir aucun).

Si le processus est interrompu, `--remettre-depuis FICHIER` rejoue la remise en
état depuis l'instantané.

Garde-fous : `--je-confirme` obligatoire ; bulletin brouillon calculé ; pas
modifié depuis deux heures ; jamais sur un brouillon en cours de travail
(mémoire « jamais régénérer un bulletin sans accord »).

Usage :
    python -m scripts.verif_prime_depuis_le_bulletin --societe ID --salarie NOM \
        --annee 2026 --mois 6 --utilisateur UUID --je-confirme
    python -m scripts.verif_prime_depuis_le_bulletin --remettre-depuis FICHIER
"""

from __future__ import annotations

import base64
import copy
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PRIME = {
    "name": "Prime contrôle",
    "amount": 100.0,
    "is_socially_taxed": True,
    "is_taxable": True,
    "catalog_prime_id": None,
}
# Colonnes posées par la base elle-même : non restaurables, non comparées.
_AUTO = {"updated_at"}


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


# ---------------------------------------------------------------- instantané


def _photographier(supabase: Any, eid: str, annee: int, mois: int) -> dict:
    payslip = (supabase.table("payslips").select("*").eq("employee_id", eid)
               .eq("year", annee).eq("month", mois).single().execute().data)
    schedule = (supabase.table("employee_schedules").select("*").eq("employee_id", eid)
                .eq("year", annee).eq("month", mois).maybe_single().execute())
    pdf = b""
    if payslip.get("pdf_storage_path"):
        pdf = supabase.storage.from_("payslips").download(payslip["pdf_storage_path"])
    return {
        "employee_id": eid,
        "annee": annee,
        "mois": mois,
        "payslip": payslip,
        "schedule": schedule.data if schedule and schedule.data else None,
        "monthly_inputs": supabase.table("monthly_inputs").select("*").eq("employee_id", eid)
        .eq("year", annee).eq("month", mois).execute().data or [],
        "repos_credits": supabase.table("repos_compensateur_credits").select("*")
        .eq("employee_id", eid).eq("year", annee).execute().data or [],
        "retenues": _retenues(supabase, payslip["id"]),
        "pdf_base64": base64.b64encode(pdf).decode() if pdf else "",
    }


def _retenues(supabase: Any, payslip_id: str) -> dict[str, int]:
    return {
        table: len(supabase.table(table).select("id").eq("payslip_id", payslip_id).execute().data or [])
        for table in ("salary_seizure_deductions", "salary_advance_repayments")
    }


def _sans_auto(ligne: dict) -> dict:
    return {k: v for k, v in ligne.items() if k not in _AUTO}


def _remettre(supabase: Any, photo: dict) -> list[str]:
    """Remet tout à l'identique ; rend la liste des écarts restants (vide = réussi)."""
    eid, annee, mois = photo["employee_id"], photo["annee"], photo["mois"]
    payslip = photo["payslip"]

    # Variables du mois : retirer les ajoutées, réinsérer les disparues.
    ids = {r["id"] for r in photo["monthly_inputs"]}
    actuelles = supabase.table("monthly_inputs").select("id").eq("employee_id", eid) \
        .eq("year", annee).eq("month", mois).execute().data or []
    for r in actuelles:
        if r["id"] not in ids:
            supabase.table("monthly_inputs").delete().eq("id", r["id"]).execute()
    presentes = {r["id"] for r in actuelles}
    for r in photo["monthly_inputs"]:
        if r["id"] not in presentes:
            supabase.table("monthly_inputs").insert(_sans_auto(r)).execute()

    # Crédits de repos de l'année.
    ids_credits = {r["id"] for r in photo["repos_credits"]}
    for r in supabase.table("repos_compensateur_credits").select("id").eq("employee_id", eid) \
            .eq("year", annee).execute().data or []:
        if r["id"] not in ids_credits:
            supabase.table("repos_compensateur_credits").delete().eq("id", r["id"]).execute()
    for r in photo["repos_credits"]:
        supabase.table("repos_compensateur_credits").upsert(_sans_auto(r)).execute()

    # Cumuls du mois.
    if photo["schedule"]:
        supabase.table("employee_schedules").update(
            {k: v for k, v in _sans_auto(photo["schedule"]).items() if k != "id"}
        ).eq("id", photo["schedule"]["id"]).execute()

    # Bulletin : toute la ligne, puis le PDF.
    supabase.table("payslips").update(
        {k: v for k, v in _sans_auto(payslip).items() if k != "id"}
    ).eq("id", payslip["id"]).execute()
    if photo["pdf_base64"] and payslip.get("pdf_storage_path"):
        supabase.storage.from_("payslips").upload(
            path=payslip["pdf_storage_path"],
            file=base64.b64decode(photo["pdf_base64"]),
            file_options={"x-upsert": "true", "content-type": "application/pdf"},
        )

    return _verifier(supabase, photo)


def _verifier(supabase: Any, photo: dict) -> list[str]:
    actuel = _photographier(supabase, photo["employee_id"], photo["annee"], photo["mois"])
    ecarts: list[str] = []
    for cle in ("payslip", "schedule"):
        avant, apres = photo[cle] or {}, actuel[cle] or {}
        for champ in set(avant) | set(apres):
            if champ in _AUTO:
                continue
            if avant.get(champ) != apres.get(champ):
                ecarts.append(f"{cle}.{champ}")
    for cle in ("monthly_inputs", "repos_credits"):
        if sorted(r["id"] for r in photo[cle]) != sorted(r["id"] for r in actuel[cle]):
            ecarts.append(cle)
    if photo["retenues"] != actuel["retenues"]:
        ecarts.append("retenues")
    if photo["pdf_base64"] != actuel["pdf_base64"]:
        ecarts.append("pdf")
    return ecarts


# --------------------------------------------------------------------- main


def main() -> int:
    from app.core.database import supabase

    if _arg("--remettre-depuis"):
        photo = json.loads(Path(_arg("--remettre-depuis")).read_text(encoding="utf-8"))
        ecarts = _remettre(supabase, photo)
        print("remis à l'identique" if not ecarts else f"!! écarts restants : {ecarts}")
        return 1 if ecarts else 0

    societe, nom = _arg("--societe"), (_arg("--salarie") or "").upper()
    annee, mois = int(_arg("--annee") or 0), int(_arg("--mois") or 0)
    # `edit_payslip` trace l'auteur dans une colonne UUID : il faut un vrai compte.
    utilisateur = _arg("--utilisateur")
    if "--je-confirme" not in sys.argv or not (societe and nom and annee and mois and utilisateur):
        print(__doc__)
        return 2

    from app.modules.payslips.application.commands import edit_payslip, generate_payslip
    from app.modules.payslips.application.dto import (
        EditPayslipInput,
        GeneratePayslipInput,
    )

    emp = next(
        (e for e in supabase.table("employees").select("id, last_name").eq("company_id", societe).execute().data
         if str(e["last_name"]).upper() == nom),
        None,
    )
    if emp is None:
        print(f"!! aucun salarié {nom} dans la société")
        return 1
    eid = str(emp["id"])

    photo = _photographier(supabase, eid, annee, mois)
    payslip = photo["payslip"]
    if payslip.get("status") != "brouillon" or payslip.get("origine") == "importe":
        print("!! bulletin non brouillon ou importé — rien n'est fait")
        return 1
    modifie = datetime.fromisoformat(str(payslip["updated_at"]))
    # `--recence-due-au-controle` : seulement quand la dernière modification est la
    # remise en état d'un passage précédent de ce même contrôle.
    if "--recence-due-au-controle" not in sys.argv and datetime.now(UTC) - modifie < timedelta(hours=2):
        print(f"!! bulletin modifié à {modifie:%H:%M} UTC : peut-être en cours de travail — rien n'est fait")
        return 1
    if any(photo["retenues"].values()):
        print(f"!! retenues rattachées au bulletin {photo['retenues']} — choisir un autre salarié")
        return 1

    fichier = Path(_arg("--instantane") or f"/tmp/instantane_{nom}_{annee}_{mois:02d}.json")
    fichier.write_text(json.dumps(photo, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"instantané écrit : {fichier}  (en cas d'arrêt : --remettre-depuis {fichier})")

    def bulletin() -> dict:
        return (supabase.table("payslips").select("*").eq("employee_id", eid)
                .eq("year", annee).eq("month", mois).single().execute().data)

    regen = GeneratePayslipInput(employee_id=eid, year=annee, month=mois,
                                 force_calendrier_incomplet=True, regenerer_bulletin_valide=True)
    a = b = None
    try:
        # Chemin A : la prime saisie comme variable du mois (onglet Primes).
        supabase.table("monthly_inputs").insert(
            {**PRIME, "employee_id": eid, "company_id": societe, "year": annee, "month": mois}).execute()
        generate_payslip(regen)
        a = _releve(bulletin())
        ecarts = _remettre(supabase, photo)
        if ecarts:
            print(f"!! remise en état intermédiaire incomplète : {ecarts}")
            return 1

        # Chemin B : la même prime ajoutée depuis l'écran de modification.
        data = copy.deepcopy(payslip["payslip_data"])
        data.setdefault("calcul_du_brut", []).append({
            "libelle": PRIME["name"], "quantite": None, "taux": None, "gain": PRIME["amount"],
            "perte": None, "is_sous_total": False, "nouvelle_saisie": dict(PRIME)})
        resultat = edit_payslip(EditPayslipInput(
            payslip_id=payslip["id"], payslip_data=data, changes_summary="Contrôle prime depuis le bulletin",
            current_user_id=utilisateur, current_user_name="Contrôle automatique"))
        if resultat.get("recalcul_erreur"):
            print(f"!! recalcul impossible : {resultat['recalcul_erreur']}")
        else:
            b = _releve(bulletin())
    finally:
        ecarts_finaux = _remettre(supabase, photo)

    print("remise en état :", "complète, vérifiée champ par champ" if not ecarts_finaux
          else f"!! ÉCARTS RESTANTS {ecarts_finaux} — relancer --remettre-depuis {fichier}")
    if a is None or b is None:
        return 1
    ecarts = {k: (a[k], b[k]) for k in a if abs(a[k] - b[k]) > 0.01}
    print(f"{'':22s} {'onglet Primes':>14s} {'depuis le bulletin':>19s}")
    for k in a:
        print(f"  {k:20s} {a[k]:>14.2f} {b[k]:>19.2f}")
    print("IDENTIQUES au centime" if not ecarts else f"!! ÉCARTS : {ecarts}")
    return 1 if (ecarts or ecarts_finaux) else 0


if __name__ == "__main__":
    sys.exit(main())
