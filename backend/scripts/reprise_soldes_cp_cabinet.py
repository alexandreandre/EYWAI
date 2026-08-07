"""Reprise des soldes de congés reportés depuis l'état de provision du cabinet.

EYWAI ne contient aucun congé antérieur à janvier 2026 : il recalcule un droit
théorique d'année pleine au lieu du report réel. L'état « provision des congés payés »
du cabinet porte ce report, salarié par salarié, en jours ouvrés.

Le script écrit un ajustement dans `employee_leave_adjustments`. Le moteur ajoute cet
ajustement au solde qu'il calcule lui-même : on enregistre donc l'écart entre le report
réel et le théorique, jamais le report brut — sinon le solde serait compté deux fois.
L'écart étant recalculé à chaque exécution contre le théorique pur, relancer le script
ne cumule rien.

Simulation par défaut. Rien n'est écrit sans --apply.

Usage :
    ./venv/bin/python scripts/reprise_soldes_cp_cabinet.py \\
        --societe "Cartol Industrie" --annee 2026 \\
        --modele "../data/_inbox/whatsapp-elsa/00000595-PROVISION CP.pdf"
    # puis, après relecture du tableau :
    ... --apply
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unicodedata
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402
from app.modules.absences.application.queries import _leave_context, _parse_hire_date  # noqa: E402
from app.modules.absences.domain.fractionnement import ouvrables_to_ouvres  # noqa: E402
from app.modules.absences.domain.leave_policy import EmployeeLeaveAdjustment  # noqa: E402
from app.modules.absences.domain.rules import compute_cp_balances_for_bulletin  # noqa: E402
from app.modules.absences.infrastructure import (  # noqa: E402
    fractionnement_repository as frac_repo,
    leave_settings_repository as leave_repo,
)
from app.modules.absences.infrastructure.repository import absence_repository  # noqa: E402

# Position de la colonne « Nom de l'employé » dans l'état Cegid rendu par `pdftotext
# -layout`. Le numéro de collaborateur occupe les colonnes 0 à 17 et contient parfois
# une lettre de désambiguïsation (« COUTANT D », « LEMAIRE JN ») qu'il ne faut surtout
# pas confondre avec un prénom.
COLONNE_NOM = 18


def _cle(texte: str) -> str:
    sans_accent = (
        unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode()
    )
    return re.sub(r"[^A-Z]", "", sans_accent.upper())


def _jetons(*champs: str | None) -> set[str]:
    jetons = set()
    for champ in champs:
        for mot in re.split(r"[\s\-']+", champ or ""):
            if _cle(mot):
                jetons.add(_cle(mot))
    return jetons


def lire_reports_du_modele(chemin: str) -> list[dict]:
    """Numéro, nom et solde N-1 en jours ouvrés, une entrée par salarié de l'état."""
    texte = subprocess.run(
        ["pdftotext", "-layout", chemin, "-"], capture_output=True, text=True, check=True
    ).stdout
    return parser_reports(texte)


def parser_reports(texte: str) -> list[dict]:
    """Découpe le rendu `pdftotext -layout` de l'état Cegid.

    Séparé de la lecture du PDF pour être testable sans fichier.
    """
    reports = []
    for ligne in texte.splitlines():
        nombres = re.findall(r"-?[\d ]+\.\d\d", ligne)
        if len(nombres) != 8 or len(ligne) <= COLONNE_NOM:
            continue
        numero = ligne[:COLONNE_NOM].strip()
        if not numero or numero.lower().startswith("total"):
            continue
        reste = ligne[COLONNE_NOM:]
        debut_chiffres = reste.find(nombres[0].strip()[:4])
        nom = reste[:debut_chiffres].strip() if debut_chiffres > 0 else ""
        if not nom:
            continue
        reports.append(
            {
                "numero": numero,
                "nom": nom,
                "solde_n1_ouvres": float(nombres[0].replace(" ", "")),
            }
        )
    return reports


def solde_n1_theorique_ouvrables(
    employee_id: str, company_id: str, ref_date: date
) -> float | None:
    """Ce que le moteur calcule seul, ajustement neutralisé. Base de l'écart."""
    hire_date = _parse_hire_date(employee_id)
    if not hire_date:
        return None
    policy, _, _, cp_seniority = _leave_context(employee_id, ref_date.year, company_id)
    from app.modules.absences.application.fractionnement_prefill import (
        build_employee_cp_seniority_context_from_db,
    )

    soldes = compute_cp_balances_for_bulletin(
        hire_date,
        absence_repository.list_validated_for_employees([employee_id]),
        ref_date,
        policy=policy,
        adjustment=EmployeeLeaveAdjustment.empty(),
        cp_seniority=cp_seniority,
        employee_ctx=build_employee_cp_seniority_context_from_db(employee_id),
    )
    return float(soldes["periode_precedente"].get("solde") or 0)


def main() -> int:
    parseur = argparse.ArgumentParser()
    parseur.add_argument("--societe", required=True)
    parseur.add_argument("--annee", type=int, required=True)
    parseur.add_argument("--modele", required=True)
    parseur.add_argument(
        "--arrete",
        default=None,
        help="Date d'arrêté de l'état, format AAAA-MM-JJ (défaut : 31/07 de l'année)",
    )
    parseur.add_argument("--apply", action="store_true", help="Écrit réellement en base")
    args = parseur.parse_args()

    ref_date = (
        date.fromisoformat(args.arrete) if args.arrete else date(args.annee, 7, 31)
    )

    societes = supabase.table("companies").select("id, company_name").execute().data or []
    trouvees = [s for s in societes if _cle(args.societe) in _cle(s["company_name"])]
    if len(trouvees) != 1:
        print(f"Société introuvable ou ambiguë : {args.societe}")
        return 1
    company_id, societe = trouvees[0]["id"], trouvees[0]["company_name"]

    reglages = frac_repo.get_fractionnement_settings_row(company_id) or {}
    ratio = float(reglages.get("ouvres_to_ouvrables_ratio") or 1.2)

    salaries = (
        supabase.table("employees")
        .select("id, matricule, first_name, last_name, nom_usage, employment_status")
        .eq("company_id", company_id)
        .execute()
    ).data or []

    reports = lire_reports_du_modele(args.modele)
    print(f"{societe} — arrêté au {ref_date:%d/%m/%Y} — {len(reports)} lignes dans l'état")
    print(f"Conversion jours ouvrés → ouvrables : ×{ratio}\n")

    lignes, refus = [], []
    for report in reports:
        cibles = _jetons(report["nom"])
        candidats = [s for s in salaries if cibles and cibles <= _jetons(
            s.get("first_name"), s.get("last_name"), s.get("nom_usage")
        )]
        if len(candidats) != 1:
            refus.append(
                f"{report['numero']:14s} {report['nom']:32s} "
                f"→ {len(candidats)} correspondance(s)"
            )
            continue
        salarie = candidats[0]
        if salarie.get("employment_status") != "actif":
            refus.append(f"{report['numero']:14s} {report['nom']:32s} → salarié non actif")
            continue
        theorique = solde_n1_theorique_ouvrables(salarie["id"], company_id, ref_date)
        if theorique is None:
            refus.append(f"{report['numero']:14s} {report['nom']:32s} → sans date d'entrée")
            continue
        cible_ouvrables = round(report["solde_n1_ouvres"] * ratio, 2)
        ecart = round(cible_ouvrables - theorique, 2)
        lignes.append(
            {
                "employee_id": salarie["id"],
                "nom": report["nom"],
                "numero": report["numero"],
                "cible_ouvres": report["solde_n1_ouvres"],
                "theorique_ouvres": ouvrables_to_ouvres(theorique, ratio),
                "ecart_ouvrables": ecart,
            }
        )

    print(f"{'Numéro':14s} {'Nom':30s} {'cabinet':>9s} {'EYWAI':>9s} {'écart':>9s}")
    print("-" * 76)
    for l in sorted(lignes, key=lambda x: -abs(x["ecart_ouvrables"]))[:20]:
        print(
            f"{l['numero']:14s} {l['nom'][:30]:30s} {l['cible_ouvres']:9.2f} "
            f"{l['theorique_ouvres']:9.2f} {l['ecart_ouvrables']:+9.2f}"
        )
    if len(lignes) > 20:
        print(f"… et {len(lignes) - 20} autres")

    print(f"\nÀ reprendre : {len(lignes)} salarié(s)")
    if refus:
        print(f"Non repris  : {len(refus)}")
        for r in refus:
            print(f"   {r}")

    if not args.apply:
        print("\nSIMULATION — rien n'a été écrit. Relancer avec --apply pour appliquer.")
        return 0

    if refus:
        print(
            "\nREFUS : des lignes n'ont pas pu être rapprochées. On n'écrit rien tant "
            "que l'état n'est pas repris en totalité."
        )
        return 1

    for l in lignes:
        # Cartol porte déjà des ajustements issus d'un import de bulletins. On remplace
        # la valeur — l'état du cabinet fait foi et il est plus récent — mais on garde
        # la trace de ce qui était là, sinon on perd l'historique de la reprise.
        precedent = leave_repo.get_employee_adjustment(l["employee_id"], args.annee)
        note = (
            f"Reprise du report cabinet au {ref_date:%d/%m/%Y} : "
            f"{l['cible_ouvres']:.2f} j ouvrés"
        )
        if precedent and precedent.note:
            note = f"{note} — remplace : {precedent.note}"
        leave_repo.upsert_employee_adjustment(
            company_id,
            l["employee_id"],
            args.annee,
            {"cp_n1_opening_balance": l["ecart_ouvrables"], "note": note},
        )
    print(f"\n{len(lignes)} ajustement(s) écrit(s) pour {societe}, année {args.annee}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
