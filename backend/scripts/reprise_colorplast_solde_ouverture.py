"""Reprise Colorplast : écrit le solde d'ouverture au 31 août 2026 lu chez Quadra.

Le passé appartient à Quadra. Ce script ne recalcule rien : il lit les bulletins
PDF de Gaëlle ligne à ligne, agrège les mois repris, contrôle l'agrégat contre le
bloc de cumuls imprimé, puis écrit le résultat dans
`employee_schedules.cumuls` du mois de bascule. Le bloc imprimé sert de somme de
contrôle : une erreur de lecture se voit avant d'entrer en base.

Le même `--apply` reprend les compteurs de congés imprimés sur le bulletin du mois
de bascule (`apply_cp_solde_import`, reprise datée du dernier jour du mois) et
pose la bascule de la société (`company_payroll_takeover`), qui verrouille les
mois repris (cf. app/shared/reprise_paie.py). L'écart de congés figé à la reprise
absorbe les absences validées jusqu'à cette date : ranger des doublons d'avant
la bascule se fait donc avant ce script, jamais après.

Bascule au 31/07 le 21/09/2026, puis au 31/08 le 29/09/2026 : août est payé par
Quadra comme les mois précédents, septembre est le premier mois MARTINE.

Usage :
    python -m scripts.reprise_colorplast_solde_ouverture            # simulation
    python -m scripts.reprise_colorplast_solde_ouverture --apply    # écrit
"""

from __future__ import annotations

import re
import sys
from calendar import monthrange
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import get_supabase_admin_client  # noqa: E402
from app.modules.absences.application.leave_settings_commands import (  # noqa: E402
    apply_cp_solde_import,
)
from app.modules.payroll.engine.reference_remuneration import (  # noqa: E402
    get_cp_reference_period_bounds,
)
from scripts.backtest.colorplast_lignes_quadra import lire_bulletins  # noqa: E402

COMPANY_ID = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"
ANNEE = 2026
MOIS_REPRIS = (1, 2, 3, 4, 5, 6, 7, 8)
BASCULE = (2026, 8)

#: Deux libellés chez Quadra pour les heures sup : les structurelles et les réelles.
EST_HEURE_SUP = re.compile(r"H\.?\s*SUPP|HEURES\s+SUPPL", re.I)
#: La réduction générale de cotisations patronales, hors déduction forfaitaire HS.
EST_REDUCTION_GENERALE = re.compile(r"EXO\.|ALLEG", re.I)
#: La déduction forfaitaire patronale sur heures sup, portée à part.
EST_DEDUCTION_HS = re.compile(r"REDUCT\s+HEURES\s+SUPPL", re.I)
#: Abattement d'assiette de la CSG (1,75 % non soumis).
ABATTEMENT_CSG = 0.9825
#: CSG déductible de l'impôt.
TAUX_CSG_DEDUCTIBLE = 0.068
#: CSG + CRDS non déductibles, taux plein qui pèse sur les heures sup exonérées.
TAUX_CSG_CRDS_PLEIN = 0.097

#: Passage du compteur imprimé par Quadra à celui dont notre moteur a besoin.
#:
#: Quadra n'imprime qu'un seul cumul d'heures sup exonérées : le brut des HS
#: moins la seule CSG déductible, celui qui entre dans le revenu fiscal de
#: référence. Notre moteur en tient un second, le montant réellement défiscalisé,
#: qui retire aussi la CSG/CRDS non déductible et qui sert à écrêter au plafond
#: annuel de 7 500 € (art. 81 quater CGI). Les deux se déduisent du même brut G :
#:     imprimé   = G × (1 − 0,068 × 0,9825)
#:     défiscalisé = G × (1 − 0,097 × 0,9825)
#: donc le second vaut le premier multiplié par le rapport des deux facteurs.
#: Vérifié sur GIRERD juin 2026 : 449,54 € de HS, 419,51 € imprimés, 406,70 €
#: défiscalisés, et sur les six mois l'écart avec notre cumul reste sous 1 €.
RATIO_HS_DEFISCALISEES = (1 - TAUX_CSG_CRDS_PLEIN * ABATTEMENT_CSG) / (
    1 - TAUX_CSG_DEDUCTIBLE * ABATTEMENT_CSG
)


def _somme_des_lignes(bulletin, motif: re.Pattern) -> float:
    """Somme patronale des lignes qui correspondent, signe conservé."""
    return round(
        sum(lg.montant_pat for lg in bulletin.lignes
            if lg.montant_pat is not None and motif.search(lg.libelle)),
        2,
    )


def _heures_sup_brut(bulletin) -> float:
    """Rémunération brute des heures sup du mois : les gains moins les retenues."""
    total = 0.0
    for lg in bulletin.lignes:
        if not EST_HEURE_SUP.search(lg.libelle):
            continue
        total += (lg.gain or 0.0) - (lg.montant_sal or 0.0)
    return round(total, 2)


def _salaire_brut(bulletin) -> float:
    for lg in bulletin.lignes:
        if lg.libelle.strip().upper() == "SALAIRE BRUT" and lg.gain is not None:
            return round(lg.gain, 2)
    return 0.0


def base_du_dixieme(lus: dict[int, dict], annee: int, bascule: int, cle: str, brut_du_mois,
                    *, start_month: int = 6) -> tuple[float, date, date]:
    """La rémunération de la période de congés en cours au dernier jour de la bascule :
    la somme des bruts repris depuis son début, pour ce matricule (donc ce contrat).
    Le moteur la prolonge ensuite mois après mois (`mettre_a_jour_brut_reference_cumul`) ;
    le seul brut du dernier mois n'était juste qu'avec une bascule au 30 juin."""
    debut, fin = get_cp_reference_period_bounds(
        date(annee, bascule, monthrange(annee, bascule)[1]), start_month=start_month)
    if debut.year < annee:
        raise SystemExit(f"Période de congés {debut} → {fin} : il faut aussi les bulletins de {debut.year}.")
    mois = [m for m in sorted(lus) if m <= bascule and cle in lus[m] and date(annee, m, 1) >= debut]
    return round(sum(brut_du_mois(lus[m][cle]) for m in mois), 2), debut, fin


def construire_le_solde(lus: dict[int, dict]) -> dict[str, dict[str, Any]]:
    """Un solde d'ouverture par salarié présent au mois de bascule."""
    soldes: dict[str, dict[str, Any]] = {}
    mois_bascule = BASCULE[1]
    for nom, dernier in sorted(lus[mois_bascule].items()):
        mois_presents = [m for m in MOIS_REPRIS if nom in lus.get(m, {})]
        reduction_generale = deduction_hs = hs_brut = plafonds = 0.0
        bruts_mensuels = 0.0
        for m in mois_presents:
            b = lus[m][nom]
            reduction_generale += _somme_des_lignes(b, EST_REDUCTION_GENERALE)
            deduction_hs += _somme_des_lignes(b, EST_DEDUCTION_HS)
            hs_brut += _heures_sup_brut(b)
            plafonds += float(b.droite.get("plafond") or 0.0)
            bruts_mensuels += _salaire_brut(b)

        brut = float(dernier.droite.get("cumul_bruts") or 0.0)
        net_hs_exo = float(dernier.net.get("net_hs_exo_cumul") or 0.0)
        tranche_2 = round(max(0.0, brut - plafonds), 2)
        base_cp, debut_cp, fin_cp = base_du_dixieme(lus, ANNEE, mois_bascule, nom, _salaire_brut)
        soldes[nom] = {
            "mois_presents": mois_presents,
            "controle_somme_des_bruts": round(bruts_mensuels, 2),
            "cumuls": {
                "brut_total": brut,
                "net_imposable": float(dernier.net.get("net_imposable_cumul") or 0.0),
                "impot_preleve_a_la_source": float(dernier.net.get("pas_cumul") or 0.0),
                "heures_remunerees": float(dernier.droite.get("cumul_heures") or 0.0),
                "heures_supplementaires_remunerees": float(dernier.droite.get("cumul_hs") or 0.0),
                "montant_hs_remunerees": round(hs_brut, 2),
                "montant_net_hs_exonerees_cumul": net_hs_exo,
                "hs_exonerees_ir_cumul": round(net_hs_exo * RATIO_HS_DEFISCALISEES, 2),
                "reduction_generale_patronale": round(reduction_generale, 2),
                "deduction_forfaitaire_hs_patronale": round(deduction_hs, 2),
                "cumul_brut_agirc_arrco": brut,
                "cumul_pss_agirc_arrco": round(plafonds, 2),
                "cumul_tranche_2_appliquee": tranche_2,
                "cumul_tranche_1_appliquee": round(brut - tranche_2, 2),
                "brut_reference_n_1": base_cp,
                "brut_reference_period_start": debut_cp.isoformat(),
                "brut_reference_period_end": fin_cp.isoformat(),
            },
            "conges": dict(zip(("cp_n1", "cp_n"), (float(v) for v in dernier.cp.get("Solde", (0.0, 0.0))))),
            "periode": {"annee_en_cours": ANNEE, "dernier_mois_calcule": mois_bascule},
            "reprise": {
                "logiciel_precedent": "Quadra",
                "source": "bulletins PDF lus ligne à ligne",
                "mois_de_bascule": f"{ANNEE:04d}-{mois_bascule:02d}",
                "fait_foi": True,
            },
        }
    return soldes


def _fiches_par_nom(admin) -> dict[str, str]:
    lignes = (
        admin.table("employees").select("id, last_name").eq("company_id", COMPANY_ID).execute().data
    )
    return {str(e["last_name"]).upper().replace(" ", "").replace("-", ""): e["id"] for e in lignes}


def main(appliquer: bool) -> int:
    lus = {m: lire_bulletins(ANNEE, m) for m in MOIS_REPRIS}
    soldes = construire_le_solde(lus)
    admin = get_supabase_admin_client()
    fiches = _fiches_par_nom(admin)

    print(f"Reprise Colorplast au {BASCULE[1]:02d}/{BASCULE[0]} — "
          f"{len(soldes)} salariés présents au mois de bascule\n")

    anomalies = 0
    for nom, solde in soldes.items():
        ecart = round(solde["controle_somme_des_bruts"] - solde["cumuls"]["brut_total"], 2)
        if abs(ecart) >= 0.01:
            print(f"!! {nom} : somme des bruts mensuels {solde['controle_somme_des_bruts']:.2f} "
                  f"contre brut cumulé imprimé {solde['cumuls']['brut_total']:.2f} "
                  f"(écart {ecart:+.2f}) — lecture à revoir avant écriture")
            anomalies += 1
        if nom not in fiches:
            print(f"!! {nom} : aucune fiche dans la base")
            anomalies += 1

    cles = ["brut_total", "heures_remunerees", "net_imposable", "impot_preleve_a_la_source",
            "reduction_generale_patronale", "cumul_pss_agirc_arrco", "hs_exonerees_ir_cumul"]
    entetes = ["brut", "heures", "net imp.", "PAS", "réd. gén.", "plafond", "HS exo IR"]
    print(f"{'Salarié':11s} " + " ".join(f"{e:>11s}" for e in entetes))
    for nom, solde in soldes.items():
        vals = [solde["cumuls"][c] for c in cles]
        print(f"{nom:11s} " + " ".join(f"{v:11.2f}" for v in vals))

    print("\nComparaison avec nos compteurs actuels (nous − Quadra) :")
    for nom, solde in soldes.items():
        eid = fiches.get(nom)
        if not eid:
            continue
        ligne = (admin.table("employee_schedules").select("cumuls")
                 .eq("employee_id", eid).eq("year", BASCULE[0]).eq("month", BASCULE[1])
                 .limit(1).execute().data)
        nos = ((ligne or [{}])[0].get("cumuls") or {}).get("cumuls") or {}
        diffs = []
        for c in cles:
            if c in nos and nos[c] is not None:
                d = round(float(nos[c]) - solde["cumuls"][c], 2)
                if abs(d) >= 0.01:
                    diffs.append(f"{c} {d:+.2f}")
        print(f"  {nom:11s} " + ("; ".join(diffs) if diffs else "aligné"))

    if anomalies:
        print(f"\n{anomalies} anomalie(s) : rien n'est écrit.")
        return 1
    if not appliquer:
        print("\nCongés imprimés au mois de bascule (N-1 / N) :")
        for nom, solde in soldes.items():
            print(f"  {nom:11s} {solde['conges']['cp_n1']:6.2f} / {solde['conges']['cp_n']:6.2f}")
        print(f"\nSimulation. Relancer avec --apply pour écrire le solde, reprendre les "
              f"congés et poser la bascule au {BASCULE[1]:02d}/{BASCULE[0]}.")
        return 0

    for nom, solde in soldes.items():
        eid = fiches[nom]
        charge = {"cumuls": solde["cumuls"], "periode": solde["periode"],
                  "reprise": solde["reprise"]}
        existe = (admin.table("employee_schedules").select("id")
                  .eq("employee_id", eid).eq("year", BASCULE[0]).eq("month", BASCULE[1])
                  .limit(1).execute().data)
        if existe:
            admin.table("employee_schedules").update({"cumuls": charge}) \
                .eq("id", existe[0]["id"]).execute()
        else:
            admin.table("employee_schedules").insert(
                {"employee_id": eid, "year": BASCULE[0], "month": BASCULE[1], "cumuls": charge}
            ).execute()
        apply_cp_solde_import(
            COMPANY_ID, eid, BASCULE[0],
            cp_n1_solde=solde["conges"]["cp_n1"], cp_n_solde=solde["conges"]["cp_n"],
            rtt_solde=0.0, month=BASCULE[1],
            note=f"Reprise Quadra au {date(BASCULE[0], BASCULE[1], monthrange(*BASCULE)[1]):%d/%m/%Y} "
                 f"(bascule de la société) : soldes du bulletin de {BASCULE[1]:02d}/{BASCULE[0]}, "
                 f"N-1 {solde['conges']['cp_n1']:.2f} / N {solde['conges']['cp_n']:.2f}",
        )
        print(f"  {nom:11s} solde d'ouverture et congés écrits")

    ligne = {"company_id": COMPANY_ID, "cutoff_year": BASCULE[0], "cutoff_month": BASCULE[1],
             "source": "bulletins", "previous_software": "Quadra",
             "note": f"Reprise Colorplast : Gaëlle a payé janvier à {BASCULE[1]:02d}/{BASCULE[0]} dans "
                     f"Quadra. Bulletins et compteurs repris littéralement des PDF ; la paie MARTINE "
                     f"commence le mois suivant (bascule posée le {date.today():%d/%m/%Y})."}
    if admin.table("company_payroll_takeover").select("id").eq("company_id", COMPANY_ID).execute().data:
        admin.table("company_payroll_takeover").update(ligne).eq("company_id", COMPANY_ID).execute()
    else:
        admin.table("company_payroll_takeover").insert(ligne).execute()
    print(f"\nBascule de la société posée au {BASCULE[1]:02d}/{BASCULE[0]}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--apply" in sys.argv))
