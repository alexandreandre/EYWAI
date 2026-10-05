"""Contrôle des exports comptables d'une société pour un mois, au centime (lecture seule).

Pour chaque mois : l'OD globale et ses trois parts, les fichiers réellement
produits (OD CSV, Quadra, Sage, générique, FEC) relus compte par compte, le
journal de paie, et les exports de détail (prêts, acomptes, saisies) — contre
la somme des bulletins, nature par nature.

Rien n'est écrit : toute requête d'écriture vers Supabase est refusée avant de
partir (`Interception` du filet de paie). Lit la base désignée par le `.env`.

Usage, depuis backend/ :
  .venv/bin/python -m scripts.controle_exports_comptables --company-id <uuid> \\
      --periode 2026-08 --periode 2026-09 [--plan ../data/<societe>/comptabilite/plan_comptable.json]

`--plan` applique en mémoire le plan comptable relevé sur l'OD de l'ancien
logiciel (jamais écrit en base), pour comparer comptes et sens.

La sortie peut nommer des salariés : la garder hors git.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TOLERANCE = 0.005

Soldes = dict[str, tuple[float, float]]


# ---------------------------------------------------------------------------
# Relecture des fichiers produits (sans I/O)
# ---------------------------------------------------------------------------


def _ajouter(soldes: dict[str, list[float]], compte: str, debit: float, credit: float) -> None:
    soldes[compte][0] += debit
    soldes[compte][1] += credit


def _arrondir(soldes: dict[str, list[float]]) -> Soldes:
    return {c: (round(d, 2), round(cr, 2)) for c, (d, cr) in soldes.items()}


def relire_csv(contenu: bytes, col_compte: str, col_debit: str, col_credit: str) -> Soldes:
    """OD globale ou format générique (CSV UTF-8, virgule séparatrice)."""
    soldes: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for ligne in csv.DictReader(io.StringIO(contenu.decode("utf-8-sig"))):
        _ajouter(soldes, ligne[col_compte], float(ligne[col_debit] or 0), float(ligne[col_credit] or 0))
    return _arrondir(soldes)


def relire_quadra(contenu: bytes) -> Soldes:
    """Fichier ASCII QuadraCOMPTA : compte en 2 (8), sens en 42, centimes signés en 43."""
    soldes: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for ligne in contenu.decode("latin-1").split("\r\n"):
        if not ligne:
            continue
        if len(ligne) != 146 or ligne[0] != "M":
            raise ValueError(f"Enregistrement Quadra invalide : {ligne!r}")
        montant = int(ligne[42:55]) / 100
        if ligne[41] == "D":
            _ajouter(soldes, ligne[1:9].strip(), montant, 0.0)
        else:
            _ajouter(soldes, ligne[1:9].strip(), 0.0, montant)
    return _arrondir(soldes)


def relire_sage(contenu: bytes) -> Soldes:
    soldes: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    lignes = contenu.decode("utf-8-sig").split("\r\n")
    for ligne in lignes[1:]:
        if ligne:
            champs = ligne.split("|")
            _ajouter(soldes, champs[2], float(champs[4]), float(champs[5]))
    return _arrondir(soldes)


def relire_fec(contenu: bytes) -> Soldes:
    soldes: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    lecteur = csv.DictReader(io.StringIO(contenu.decode("utf-8")), delimiter="\t")
    for ligne in lecteur:
        _ajouter(
            soldes,
            ligne["CompteNum"],
            float(ligne["Debit"].replace(",", ".")),
            float(ligne["Credit"].replace(",", ".")),
        )
    return _arrondir(soldes)


def soldes_du_registre(ecritures: list[dict[str, Any]], compte: Callable[[str], str] = str) -> Soldes:
    soldes: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for e in ecritures:
        _ajouter(soldes, compte(str(e["compte_comptable"])), float(e["debit"]), float(e["credit"]))
    return _arrondir(soldes)


def ecart_de_soldes(fichier: Soldes, registre: Soldes) -> float:
    """Plus grand écart, au centime, entre deux relevés compte par compte."""
    comptes = set(fichier) | set(registre)
    return round(
        max(
            (
                max(
                    abs(fichier.get(c, (0.0, 0.0))[0] - registre.get(c, (0.0, 0.0))[0]),
                    abs(fichier.get(c, (0.0, 0.0))[1] - registre.get(c, (0.0, 0.0))[1]),
                )
                for c in comptes
            ),
            default=0.0,
        ),
        2,
    )


def lignes_du_plan(company_id: str, plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Plan comptable relevé sur l'OD d'un cabinet, en lignes de mapping société."""
    lignes: dict[str, dict[str, Any]] = {}
    journal = str(plan.get("journal") or "OD")
    rubriques = {
        "URSSAF": "organisme_urssaf",
        "RETRAITE": "organisme_retraite",
        "RETRAITE_SUP": "organisme_retraite_sup",
        "MUTUELLE": "organisme_mutuelle",
        "PREVOYANCE": "organisme_prevoyance",
    }
    for organisme, comptes in (plan.get("organismes") or {}).items():
        if organisme in rubriques:
            lignes[rubriques[organisme]] = {"company_id": company_id, **comptes}
    for element, comptes in (plan.get("elements") or {}).items():
        charge, tiers = comptes.get("compte_charge") or "", comptes.get("compte_tiers") or ""
        lignes[element] = {
            "company_id": company_id,
            "compte_charge": charge or None,
            "compte_tiers": tiers or None,
            "compte_comptable": charge or tiers,
            "journal": journal,
        }
    return lignes


# ---------------------------------------------------------------------------
# Contrôle d'un mois (lit la base)
# ---------------------------------------------------------------------------


def _identite_brute(payslip_data: dict[str, Any]) -> float:
    """Net reconstruit à partir des seuls champs du bulletin, sans l'extraction de l'export."""

    def f(x: Any) -> float:
        try:
            return float(x or 0)
        except (TypeError, ValueError):
            return 0.0

    sn = payslip_data.get("synthese_net") or {}
    sc = payslip_data.get("structure_cotisations") or {}
    pas_obj = sn.get("impot_prelevement_a_la_source")
    pas = f(pas_obj.get("montant")) if isinstance(pas_obj, dict) else f(sn.get("impot_preleve_a_la_source"))
    participation = 0.0
    for p in payslip_data.get("participations") or []:
        brut = f(p.get("brut"))
        numeraire = max(0.0, brut - f(p.get("part_pee")))
        participation += numeraire - (f(p.get("csg_total")) * numeraire / brut if brut else 0.0) - f(p.get("acompte"))
    retenues_reprises = payslip_data.get("retenues_sur_net")
    if retenues_reprises is not None:
        retenues = sum(f(r.get("montant")) for r in retenues_reprises if not r.get("sans_effet_sur_le_net"))
    else:
        retenues = f(sn.get("acompte_verse"))
    sortie = payslip_data.get("indemnites_sortie") or {}
    reconstruit = (
        f(payslip_data.get("salaire_brut"))
        - f(sc.get("total_salarial"))
        - pas
        + sum(f(p.get("montant")) for p in payslip_data.get("primes_non_soumises") or [])
        + sum(f(p.get("montant")) for p in payslip_data.get("revenus_hors_brut_imposables") or [])
        + participation
        + f(sn.get("remboursement_transport"))
        + f(sortie.get("total_exonerees"))
        - retenues
        - f((payslip_data.get("retenues_saisies") or {}).get("total_preleve"))
        - f((payslip_data.get("remboursements_avances") or {}).get("total_rembourse"))
        - f((payslip_data.get("remboursements_prets") or {}).get("total_rembourse"))
    )
    return round(reconstruit - f(payslip_data.get("net_a_payer")), 2)


def controler_mois(company_id: str, periode: str) -> list[dict[str, Any]]:
    """Une ligne par export : équilibré ? complet ? écart au centime, et pourquoi."""
    from app.core.database import supabase
    from app.modules.exports.domain.accounting_plan import (
        resolve_organisme_from_coti_id,
    )
    from app.modules.exports.domain.controle_comptable import controler
    from app.modules.exports.infrastructure import export_formats_cabinet as cabinet
    from app.modules.exports.infrastructure.export_acomptes import get_acomptes_data
    from app.modules.exports.infrastructure.export_ecritures_comptables import (
        generate_od_export_file,
        get_payslip_data_for_od,
    )
    from app.modules.exports.infrastructure.export_fec import generate_fec_export
    from app.modules.exports.infrastructure.export_journal_paie import (
        get_journal_paie_data,
    )
    from app.modules.exports.infrastructure.export_prets_employeur import (
        generate_prets_ecritures,
    )
    from app.modules.exports.infrastructure.export_saisies import get_saisies_data
    from app.modules.exports.infrastructure.payroll_ledger import (
        LedgerImbalanceError,
        build_payroll_ledger,
        ledger_to_od_export_rows,
    )

    def organisme_de(coti: dict[str, Any]) -> str:
        return resolve_organisme_from_coti_id(coti.get("coti_id"), str(coti.get("libelle") or ""))

    lignes, _ = get_payslip_data_for_od(company_id, periode)
    ecritures, od_totals, _ = build_payroll_ledger(company_id, periode, scope="full")
    rapport = controler(lignes, ecritures, organisme_de)
    registre = soldes_du_registre(ecritures)
    resultats: list[dict[str, Any]] = []

    def ajouter(export: str, equilibre: bool | None, complet: bool | None, ecart: float, note: str = "") -> None:
        resultats.append(
            {"export": export, "equilibre": equilibre, "complet": complet, "ecart": ecart, "note": note}
        )

    causes = [f"{a['label']} : {a['detail']}" for a in od_totals["anomalies"]]
    ecart_natures = max((abs(n["ecart"]) for n in rapport["natures"]), default=0.0)
    ajouter(
        "OD globale (registre)",
        rapport["equilibre"],
        rapport["complet"],
        max(abs(rapport["ecart"]), ecart_natures, *(abs(b["residu"]) for b in rapport["bulletins_incoherents"])),
        " ; ".join(causes[:3]) + (" …" if len(causes) > 3 else ""),
    )

    # Les trois parts : chacune équilibrée, leur somme égale l'OD globale.
    somme_parts: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for scope, nom in (("salaires", "OD salaires"), ("charges_sociales", "OD charges sociales"), ("pas", "OD PAS")):
        partielle, _, _ = build_payroll_ledger(company_id, periode, scope=scope)  # type: ignore[arg-type]
        d = round(sum(e["debit"] for e in partielle), 2)
        c = round(sum(e["credit"] for e in partielle), 2)
        for e in partielle:
            somme_parts[e["compte_comptable"]][0] += e["debit"] - e["credit"]
        ajouter(nom, abs(d - c) < TOLERANCE, rapport["complet"], round(abs(d - c), 2))
    soldes_parts = {k: round(v[0], 2) for k, v in somme_parts.items()}
    soldes_globale = {k: round(d - c, 2) for k, (d, c) in registre.items()}
    ecart_parts = max(
        (abs(soldes_parts.get(k, 0.0) - soldes_globale.get(k, 0.0)) for k in set(soldes_parts) | set(soldes_globale)),
        default=0.0,
    )
    ajouter("Parts = OD globale", None, ecart_parts < TOLERANCE, round(ecart_parts, 2))

    # Fichiers réellement produits, relus compte par compte.
    fichiers: list[tuple[str, Callable[[], bytes], Callable[[bytes], Soldes], Callable[[str], str]]] = [
        (
            "Fichier OD globale (CSV)",
            lambda: generate_od_export_file(ledger_to_od_export_rows(ecritures), "od_globale", periode, "csv"),
            lambda b: relire_csv(b, "Compte comptable", "Débit", "Crédit"),
            str,
        ),
        (
            "Format générique",
            lambda: cabinet.generate_cabinet_generic_export(company_id, periode),
            lambda b: relire_csv(b, "Compte", "Débit", "Crédit"),
            str,
        ),
        (
            "Format Quadra",
            lambda: cabinet.generate_cabinet_quadra_export(company_id, periode),
            relire_quadra,
            lambda c: c.ljust(8, "0") if c.isdigit() else c,
        ),
        ("Format Sage", lambda: cabinet.generate_cabinet_sage_export(company_id, periode), relire_sage, str),
        ("FEC", lambda: generate_fec_export(company_id, periode), relire_fec, str),
    ]
    for nom, produire, relire, compte in fichiers:
        try:
            soldes = relire(produire())
        except LedgerImbalanceError as refus:
            ajouter(nom, False, False, abs(rapport["ecart"]), "refusé : " + str(refus).split("\n")[0])
            continue
        attendu = soldes_du_registre(ecritures, compte)
        d = round(sum(v[0] for v in soldes.values()), 2)
        c = round(sum(v[1] for v in soldes.values()), 2)
        ecart = ecart_de_soldes(soldes, attendu)
        ajouter(nom, abs(d - c) < TOLERANCE, ecart < TOLERANCE and rapport["complet"], ecart)

    # Journal de paie : un registre, pas une écriture ; ses totaux contre les bulletins.
    journal, _ = get_journal_paie_data(company_id, periode)
    attendus = {
        "Brut": sum(ligne["brut"] for ligne in lignes),
        "Charges salariales": sum(ligne["cotisations_salariales"] for ligne in lignes),
        "Charges patronales": sum(ligne["cotisations_patronales"] for ligne in lignes),
        "PAS": sum(ligne["pas"] for ligne in lignes),
        "Net à payer": sum(ligne["net_a_payer"] for ligne in lignes),
    }
    ecart_journal = max(
        abs(round(sum(float(r.get(col) or 0) for r in journal) - v, 2)) for col, v in attendus.items()
    )
    ajouter("Journal de paie", None, ecart_journal < TOLERANCE and len(journal) == len(lignes), ecart_journal)

    # Exports de détail.
    natures = {n["nature"]: n["bulletins"] for n in rapport["natures"]}
    prets_bulletins = round(
        -(natures.get("hors_brut:pret_employeur", 0.0) + natures.get("hors_brut:interets_pret_employeur", 0.0)), 2
    ) + 0.0
    prets_export = round(sum(e["credit"] - e["debit"] for e in generate_prets_ecritures(company_id, periode)), 2)
    ajouter("Prêts employeur (écritures)", None, abs(prets_export - prets_bulletins) < TOLERANCE,
            round(abs(prets_export - prets_bulletins), 2), f"bulletins {prets_bulletins:.2f}")

    _, remboursements, _, _ = get_acomptes_data(company_id, periode)
    acomptes_table = round(sum(float(r.get("amount_repaid") or 0) for r in remboursements), 2)
    avances_bulletins = round(-natures.get("hors_brut:avance_salaire", 0.0), 2) + 0.0
    ajouter("Acomptes & avances (remboursements)", None, abs(acomptes_table - avances_bulletins) < TOLERANCE,
            round(abs(acomptes_table - avances_bulletins), 2),
            f"table {acomptes_table:.2f} / bulletins {avances_bulletins:.2f}")

    prelevements, _, _ = get_saisies_data(company_id, periode)
    saisies_table = round(sum(float(d.get("deducted_amount") or 0) for d in prelevements), 2)
    saisies_bulletins_module = 0.0
    year, month = map(int, periode.split("-"))
    bruts = (
        supabase.table("payslips").select("payslip_data")
        .eq("company_id", company_id).eq("year", year).eq("month", month).execute()
    ).data or []
    for b in bruts:
        saisies_bulletins_module += float(((b.get("payslip_data") or {}).get("retenues_saisies") or {}).get("total_preleve") or 0)
    ajouter("Saisies (prélèvements)", None, abs(saisies_table - saisies_bulletins_module) < TOLERANCE,
            round(abs(saisies_table - saisies_bulletins_module), 2),
            f"table {saisies_table:.2f} / bulletins {saisies_bulletins_module:.2f}")

    # Caisses et remise de paiement : la dette de chaque organisme, celle de l'OD.
    from app.modules.exports.infrastructure.export_charges_sociales import (
        get_charges_sociales_data,
    )
    from app.modules.exports.infrastructure.export_paiement_organismes import (
        _build_payment_rows,
    )

    detail_caisses, resume_caisses, _ = get_charges_sociales_data(company_id, periode)
    dettes_od = {
        n["nature"].split(":", 1)[1]: round(-n["export"], 2)
        for n in rapport["natures"]
        if n["nature"].startswith("dettes:")
    }
    par_caisse = {r["Organisme"]: round(r["Total cotisations"], 2) for r in resume_caisses}
    a_payer: dict[str, float] = defaultdict(float)
    for r in _build_payment_rows(detail_caisses, periode):
        a_payer[r["Organisme"]] += r["Total à payer"]
    for nom, releve in (("Charges sociales par caisse", par_caisse), ("Paiement organismes", a_payer)):
        ecart = max(
            (abs(round(releve.get(o, 0.0) - dettes_od.get(o, 0.0), 2)) for o in set(releve) | set(dettes_od)),
            default=0.0,
        )
        ajouter(nom, None, ecart < TOLERANCE, ecart, "contre les dettes par organisme de l'OD")

    # Contre-épreuve indépendante de l'extraction de l'export.
    brutes = [r for r in (_identite_brute(b.get("payslip_data") or {}) for b in bruts) if abs(r) >= TOLERANCE]
    ajouter("Bulletins (identité du net, lecture brute)", None, not brutes,
            max((abs(r) for r in brutes), default=0.0), f"{len(brutes)} bulletin(s) en écart" if brutes else "")
    return resultats + [{"rapport": rapport, "registre": registre}]


def _oui_non(valeur: bool | None) -> str:
    return "—" if valeur is None else ("oui" if valeur else "NON")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--company-id", required=True)
    parser.add_argument("--periode", action="append", required=True)
    parser.add_argument("--plan", type=Path, help="plan comptable JSON appliqué en mémoire")
    parser.add_argument("--env", type=Path, help="fichier .env à charger (défaut : celui du dossier courant)")
    parser.add_argument("--detail", action="store_true", help="natures et comptes du registre")
    args = parser.parse_args()

    from dotenv import load_dotenv

    load_dotenv(args.env or Path.cwd() / ".env")
    from scripts.filet_paie import Interception

    with Interception("photo"):
        if args.plan:
            from app.modules.exports.infrastructure import payroll_ledger

            plan = lignes_du_plan(args.company_id, json.loads(args.plan.read_text(encoding="utf-8")))
            lire = payroll_ledger.get_accounting_mappings
            payroll_ledger.get_accounting_mappings = lambda cid: {**lire(cid), **plan}  # type: ignore[assignment]

        for periode in args.periode:
            resultats = controler_mois(args.company_id, periode)
            details = resultats.pop()
            print(f"\n## {periode}\n")
            print("| Export | Équilibré | Complet | Écart (€) | Note |")
            print("|---|---|---|---|---|")
            for r in resultats:
                print(f"| {r['export']} | {_oui_non(r['equilibre'])} | {_oui_non(r['complet'])} | {r['ecart']:.2f} | {r['note']} |")
            if args.detail:
                print("\nNatures (débit − crédit) : bulletins / export / écart")
                for n in details["rapport"]["natures"]:
                    print(f"  {n['nature']:<40} {n['bulletins']:>12.2f} {n['export']:>12.2f} {n['ecart']:>8.2f}")
                print("\nComptes du registre : débit / crédit")
                for compte, (d, c) in sorted(details["registre"].items()):
                    print(f"  {compte:<10} {d:>12.2f} {c:>12.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
