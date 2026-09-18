"""Reprise Colorplast : écrit le solde d'ouverture au 30 juin 2026 lu chez Quadra.

Le passé appartient à Quadra. Ce script ne recalcule rien : il lit les bulletins
PDF de Gaëlle ligne à ligne, agrège les six mois, contrôle l'agrégat contre le
bloc de cumuls imprimé, puis écrit le résultat dans
`employee_schedules.cumuls` du mois de bascule. Le bloc imprimé sert de somme de
contrôle : une erreur de lecture se voit avant d'entrer en base.

Le script n'écrit que le solde d'ouverture. Le verrou de janvier à juin vient de
la bascule de la société (cf. app/shared/reprise_paie.py) et non d'une marque sur
les bulletins : cette marque dira « contenu repris de Quadra », ce qui ne sera
vrai qu'après l'import littéral.

Usage :
    python -m scripts.reprise_colorplast_solde_ouverture            # simulation
    python -m scripts.reprise_colorplast_solde_ouverture --apply    # écrit
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import get_supabase_admin_client  # noqa: E402
from scripts.backtest.colorplast_lignes_quadra import lire_bulletins  # noqa: E402

COMPANY_ID = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"
ANNEE = 2026
MOIS_REPRIS = (1, 2, 3, 4, 5, 6)
BASCULE = (2026, 6)

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
                "brut_reference_n_1": _salaire_brut(dernier),
                "brut_reference_period_start": f"{ANNEE:04d}-06-01",
                "brut_reference_period_end": f"{ANNEE + 1:04d}-05-31",
            },
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
        print("\nSimulation. Relancer avec --apply pour écrire le solde et verrouiller "
              "janvier à juin.")
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
        print(f"  {nom:11s} solde d'ouverture écrit")

    print("\nSolde d'ouverture en place. Janvier à juin sont déjà verrouillés par la "
          "bascule de la société ; leur marque `origine = importe` sera posée par "
          "l'import littéral des bulletins, quand leur contenu viendra bien de Quadra.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--apply" in sys.argv))
