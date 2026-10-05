"""Active le report des congés payés d'une société sans bouger les soldes repris.

Le report (`cp_carryover_enabled`) impute les congés pris sur le N-1 d'abord,
comme la règle et comme Quadra. Il passe ici par `update_leave_settings`, le
chemin de l'écran Congés & RTT : les écarts des reprises datées sont
réexprimés pour que le solde à la date de reprise ne bouge pas
(`rebaser_reprises_cp`). Seuls les congés posés ensuite sortent du N-1.

Depuis backend/ (code corrigé : branche lot1bis-back ou suivante) :

    PYTHONPATH=. python -m scripts.bascule_report_cp            # simulation, rien n'est écrit
    PYTHONPATH=. python -m scripts.bascule_report_cp --apply    # sauvegarde, bascule, contrôle
    PYTHONPATH=. python -m scripts.bascule_report_cp --restaurer FICHIER [--apply]

Société par défaut : Comitech. En simulation, toute écriture en base lève
(filet de paie). Avec --apply, la société et ses écarts de congés sont
sauvegardés dans data/_sauvegardes du dépôt principal avant toute écriture,
puis les soldes au 31/08/2026 sont relus et comparés à ceux d'avant.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import subprocess
import sys
from contextlib import ExitStack
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

COMITECH = "12cd8c71-da13-43f9-9151-475c4d5e8812"
REPRISE = date(2026, 8, 31)
STATUTS_SUIVIS = ("actif", "en_sortie")

Soldes = tuple[float, float] | None


def dossier_sauvegardes() -> Path:
    """data/_sauvegardes du dépôt principal (hors git), même depuis un worktree."""
    commun = subprocess.check_output(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=Path(__file__).resolve().parent,
        text=True,
    ).strip()
    return Path(commun).parent / "data" / "_sauvegardes"


def salaries_suivis(company_id: str) -> list[dict]:
    from app.core.database import supabase

    fiches = (
        supabase.table("employees")
        .select("id, first_name, last_name, employment_status")
        .eq("company_id", company_id)
        .in_("employment_status", list(STATUTS_SUIVIS))
        .execute()
        .data
        or []
    )
    return sorted(fiches, key=lambda f: (f.get("last_name") or "", f.get("first_name") or ""))


def soldes_quadra(company_id: str) -> dict[str, Soldes]:
    """N-1 et N imprimés par Quadra sur le bulletin repris du mois de reprise."""
    from app.core.database import supabase

    lignes = (
        supabase.table("payslips")
        .select("employee_id, payslip_data->pied_de_page->solde_conges")
        .eq("company_id", company_id)
        .eq("year", REPRISE.year)
        .eq("month", REPRISE.month)
        .eq("origine", "importe")
        .execute()
        .data
        or []
    )
    resultat: dict[str, Soldes] = {}
    for ligne in lignes:
        bloc = ligne.get("solde_conges") or {}
        n1 = (bloc.get("conges_payes_periode_precedente") or {}).get("solde")
        n = (bloc.get("conges_payes") or {}).get("solde")
        if n1 is not None and n is not None:
            resultat[str(ligne["employee_id"])] = (float(n1), float(n))
    return resultat


def reexpression_en_memoire(company_id: str, ancienne, nouvelle) -> dict[tuple[str, int], dict]:
    """Les écarts que la bascule réécrirait, calculés sans rien écrire."""
    from app.modules.absences.application import leave_settings_commands as cmd

    lignes = {
        (str(r["employee_id"]), int(r["year"])): r
        for r in cmd.list_company_adjustments_avec_reference(company_id)
    }
    reecrits: dict[tuple[str, int], dict] = {}

    def capter(_societe: str, employee_id: str, year: int, payload: dict) -> dict:
        cle = (str(employee_id), int(year))
        ligne = lignes[cle]
        reecrits[cle] = {
            **payload,
            "reference": date.fromisoformat(str(ligne["cp_opening_reference_date"])[:10]),
            "avant": (
                float(ligne.get("cp_n1_opening_balance") or 0),
                float(ligne.get("cp_n_opening_balance") or 0),
            ),
        }
        return {**payload, "employee_id": employee_id, "year": year}

    with patch.object(cmd, "upsert_employee_adjustment", capter):
        cmd.rebaser_reprises_cp(company_id, ancienne, nouvelle)
    return reecrits


def soldes_affiches(
    employee_id: str,
    au: date,
    *,
    policy=None,
    reecrits: dict[tuple[str, int], dict] | None = None,
) -> dict[str, Soldes]:
    """N-1 et N du bulletin du mois de reprise, et à la date `au`.

    `policy` et `reecrits` simulent un réglage et des écarts (sinon : la
    base). Le calcul du compteur d'ancienneté écrit en base : neutralisé, ces
    lectures n'écrivent jamais."""
    from app.modules.absences.application import queries as q
    from app.modules.absences.infrastructure.leave_settings_repository import (
        get_applicable_adjustment,
    )

    def ajustement(eid: str, year: int):
        adj = get_applicable_adjustment(eid, year)
        for (e, _annee), ligne in (reecrits or {}).items():
            if e == eid and adj.cp_opening_reference_date == ligne["reference"]:
                return dataclasses.replace(
                    adj,
                    cp_n1_opening_balance=ligne["cp_n1_opening_balance"],
                    cp_n_opening_balance=ligne["cp_n_opening_balance"],
                )
        return adj

    with ExitStack() as pile:
        pile.enter_context(patch.object(q, "compute_and_persist_grant", lambda *a, **k: None))
        if policy is not None:
            pile.enter_context(patch.object(q, "get_leave_policy", lambda _cid: policy))
        if reecrits:
            pile.enter_context(patch.object(q, "get_applicable_adjustment", ajustement))
        bulletin = q.get_absence_balances_for_payslip(employee_id, REPRISE.year, REPRISE.month)
        jour = q.get_absence_balances_at_date(employee_id, au)
    return {
        "reprise": None
        if not bulletin
        else (
            float(bulletin["conges_payes_periode_precedente"]["solde"]),
            float(bulletin["conges_payes"]["solde"]),
        ),
        "jour": None
        if not jour
        else (float(jour["conges_payes_n1"]["solde"]), float(jour["conges_payes_n"]["solde"])),
    }


def _f(soldes: Soldes) -> str:
    return "      —      " if soldes is None else f"{soldes[0]:6.2f}/{soldes[1]:6.2f}"


def _plancher(soldes: Soldes) -> Soldes:
    # L'affichage met un plancher à zéro (Quadra imprime −0,76, nous 0).
    return None if soldes is None else (max(0.0, soldes[0]), max(0.0, soldes[1]))


def imprimer(lignes: list[dict], au: date) -> list[str]:
    """Affiche le tableau et rend les anomalies dues à la bascule."""
    print(
        f"\n{'Salarié':28s} {'Quadra 31/08':>13s}   {'31/08 avant':>13s} {'31/08 après':>13s}"
        f"   {au:%d/%m} avant  {au:%d/%m} après"
    )
    print(f"{'':28s} {'N-1/N':>13s}   {'N-1/N':>13s} {'N-1/N':>13s}   {'N-1/N':>13s} {'N-1/N':>13s}")
    anomalies: list[str] = []
    for ligne in lignes:
        avant, apres, quadra = ligne["avant"], ligne["apres"], ligne["quadra"]
        marques = []
        if avant["reprise"] != apres["reprise"]:
            marques.append("BASCULE : 31/08 BOUGE")
            anomalies.append(f"{ligne['nom']} : 31/08 {_f(avant['reprise'])} → {_f(apres['reprise'])}")
        if quadra is not None and _plancher(quadra) != avant["reprise"]:
            marques.append("écart Quadra préexistant")
        if avant["jour"] != apres["jour"]:
            marques.append("aujourd'hui change")
        print(
            f"{ligne['nom'][:28]:28s} {_f(quadra)}   {_f(avant['reprise'])} {_f(apres['reprise'])}"
            f"   {_f(avant['jour'])} {_f(apres['jour'])}  {' ; '.join(marques)}"
        )
    return anomalies


def simuler(company_id: str, au: date) -> tuple[dict[tuple[str, int], dict], list[dict], list[str]]:
    from app.modules.absences.infrastructure.leave_settings_repository import (
        get_leave_policy,
    )

    ancienne = get_leave_policy(company_id)
    nouvelle = dataclasses.replace(ancienne, cp_carryover_enabled=True)
    reecrits = reexpression_en_memoire(company_id, ancienne, nouvelle)
    quadra = soldes_quadra(company_id)
    lignes = []
    for fiche in salaries_suivis(company_id):
        eid = str(fiche["id"])
        lignes.append(
            {
                "id": eid,
                "nom": f"{fiche.get('last_name') or ''} {fiche.get('first_name') or ''}".strip()
                + (" (en sortie)" if fiche.get("employment_status") == "en_sortie" else ""),
                "quadra": quadra.get(eid),
                "avant": soldes_affiches(eid, au),
                "apres": soldes_affiches(eid, au, policy=nouvelle, reecrits=reecrits),
            }
        )
    return reecrits, lignes, imprimer(lignes, au)


def imprimer_reecrits(reecrits: dict[tuple[str, int], dict], noms: dict[str, str]) -> None:
    if not reecrits:
        print("\nÉcarts de reprise réécrits : aucun (le report ne change aucun solde à sa date de reprise).")
        return
    print(f"\nÉcarts de reprise réécrits : {len(reecrits)}")
    for (eid, annee), ligne in sorted(reecrits.items()):
        a_n1, a_n = ligne["avant"]
        print(
            f"  {noms.get(eid, eid)[:28]:28s} {annee} réf {ligne['reference']:%d/%m/%Y} : "
            f"N-1 {a_n1:+.2f} → {ligne['cp_n1_opening_balance']:+.2f}, "
            f"N {a_n:+.2f} → {ligne['cp_n_opening_balance']:+.2f}"
        )


def sauvegarder(company_id: str) -> Path:
    from app.core.database import supabase

    reglage = (
        supabase.table("company_leave_settings").select("*").eq("company_id", company_id).execute().data
    )
    ecarts = (
        supabase.table("employee_leave_adjustments").select("*").eq("company_id", company_id).execute().data
    )
    dossier = dossier_sauvegardes()
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"report-cp-{company_id[:8]}-{datetime.now():%Y-%m-%d-%H%M%S}.json"
    chemin.write_text(
        json.dumps(
            {
                "company_id": company_id,
                "faite_le": datetime.now().isoformat(),
                "company_leave_settings": reglage,
                "employee_leave_adjustments": ecarts,
            },
            ensure_ascii=False,
            indent=1,
            default=str,
        )
    )
    return chemin


def restaurer(chemin: Path, ecrire: bool) -> int:
    """Remet le réglage du report et les écarts N-1/N de la sauvegarde."""
    from app.core.database import supabase

    sauvegarde = json.loads(chemin.read_text())
    company_id = sauvegarde["company_id"]
    a_faire: list[tuple[str, str, dict]] = []
    for reglage in sauvegarde["company_leave_settings"]:
        actuel = (
            supabase.table("company_leave_settings").select("cp_carryover_enabled")
            .eq("id", reglage["id"]).execute().data
        )
        if actuel and actuel[0]["cp_carryover_enabled"] != reglage["cp_carryover_enabled"]:
            a_faire.append(
                ("company_leave_settings", reglage["id"],
                 {"cp_carryover_enabled": reglage["cp_carryover_enabled"]})
            )
    for ligne in sauvegarde["employee_leave_adjustments"]:
        actuel = (
            supabase.table("employee_leave_adjustments")
            .select("cp_n1_opening_balance, cp_n_opening_balance").eq("id", ligne["id"]).execute().data
        )
        champs = {
            k: ligne[k]
            for k in ("cp_n1_opening_balance", "cp_n_opening_balance")
            if actuel and float(actuel[0][k] or 0) != float(ligne[k] or 0)
        }
        if champs:
            a_faire.append(("employee_leave_adjustments", ligne["id"], champs))
    print(f"Restauration de {chemin.name} (société {company_id[:8]}) : {len(a_faire)} ligne(s).")
    for table, ident, champs in a_faire:
        print(f"  {table} {ident[:8]} ← {champs}")
        if ecrire:
            supabase.table(table).update(champs).eq("id", ident).execute()
    if not ecrire:
        print("Rien n'est écrit. Relancer avec --apply pour restaurer.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--societe", default=COMITECH, help="company_id (défaut : Comitech)")
    parser.add_argument("--apply", action="store_true", help="écrire en base")
    parser.add_argument("--restaurer", type=Path, help="sauvegarde à remettre en place")
    args = parser.parse_args(argv)

    if args.restaurer:
        return restaurer(args.restaurer, args.apply)

    from app.modules.absences.infrastructure.leave_settings_repository import (
        get_leave_policy,
    )

    if get_leave_policy(args.societe).cp_carryover_enabled:
        print("Le report des CP est déjà actif pour cette société : rien à faire.")
        return 0
    au = date.today()

    if not args.apply:
        from scripts.filet_paie import Interception

        with Interception("photo") as filet:
            reecrits, lignes, anomalies = simuler(args.societe, au)
        imprimer_reecrits(reecrits, {l["id"]: l["nom"] for l in lignes})
        print(f"\nSimulation : {filet.nombre} lectures, aucune écriture (le filet les refuse).")
        if anomalies:
            print("ANOMALIE : la bascule déplacerait un solde au 31/08 :")
            for a in anomalies:
                print(f"  {a}")
            return 1
        print("Soldes au 31/08 inchangés. Relancer avec --apply pour basculer.")
        return 0

    from app.modules.absences.application.leave_settings_commands import (
        update_leave_settings,
    )
    from app.modules.absences.schemas.leave_settings import LeaveSettingsUpdate

    fiches = salaries_suivis(args.societe)
    avant = {str(f["id"]): soldes_affiches(str(f["id"]), au) for f in fiches}
    chemin = sauvegarder(args.societe)
    print(f"Sauvegarde : {chemin}")
    update_leave_settings(args.societe, LeaveSettingsUpdate(cp_carryover_enabled=True))
    print("Report des CP activé ; écarts de reprise réexprimés.")
    quadra = soldes_quadra(args.societe)
    lignes = [
        {
            "id": str(f["id"]),
            "nom": f"{f.get('last_name') or ''} {f.get('first_name') or ''}".strip(),
            "quadra": quadra.get(str(f["id"])),
            "avant": avant[str(f["id"])],
            "apres": soldes_affiches(str(f["id"]), au),
        }
        for f in fiches
    ]
    anomalies = imprimer(lignes, au)
    if anomalies:
        print("\nANOMALIE : un solde au 31/08 a bougé :")
        for a in anomalies:
            print(f"  {a}")
        print(
            "Pour revenir en arrière : PYTHONPATH=. python -m scripts.bascule_report_cp "
            f"--restaurer {chemin} --apply"
        )
        return 1
    print("\nContrôle : soldes au 31/08 inchangés.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
