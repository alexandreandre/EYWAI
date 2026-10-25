"""Reprise Colorplast : écrit le solde d'ouverture au mois de bascule, lu chez Quadra.

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
Quadra comme les mois précédents. Le 24/10/2026, septembre aussi (bascule au 30/09,
`--bascule 9`) : octobre est le premier mois MARTINE.

La simulation montre aussi les congés qu'affichera MARTINE au mois de bascule une
fois la reprise faite : `apply_cp_solde_import` est rejoué avec ses écritures
gardées en mémoire (scripts/reprise_conges_en_memoire.py), et le solde affiché
comparé à celui que Quadra imprime.

Une embauche du mois de bascule que personne n'a encore créée dans MARTINE n'a pas
de fiche : `--sans-fiche N` accepte exactement N bulletins sans fiche, laissés de
côté (rien n'est écrit pour eux ; relancer une fois leur fiche créée).

Usage :
    python -m scripts.reprise_colorplast_solde_ouverture                    # simulation, bascule au 31/08
    python -m scripts.reprise_colorplast_solde_ouverture --apply            # écrit
    python -m scripts.reprise_colorplast_solde_ouverture --bascule 9 --sans-fiche 2          # 30/09, simulation
    python -m scripts.reprise_colorplast_solde_ouverture --bascule 9 --sans-fiche 2 --apply  # 30/09, écrit
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
#: Dernier mois payé par Quadra avant la bascule du 24/10/2026 (bascule au 31/08).
BASCULE_PAR_DEFAUT = 8
MOIS_REPRIS = tuple(range(1, BASCULE_PAR_DEFAUT + 1))
BASCULE = (ANNEE, BASCULE_PAR_DEFAUT)

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


def construire_le_solde(
    lus: dict[int, dict], mois_bascule: int = BASCULE_PAR_DEFAUT
) -> dict[str, dict[str, Any]]:
    """Un solde d'ouverture par salarié présent au mois de bascule."""
    soldes: dict[str, dict[str, Any]] = {}
    mois_repris = tuple(range(1, mois_bascule + 1))
    for nom, dernier in sorted(lus[mois_bascule].items()):
        mois_presents = [m for m in mois_repris if nom in lus.get(m, {})]
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


def _fiches_par_nom(admin) -> dict[str, dict]:
    lignes = (
        admin.table("employees").select("id, last_name, first_name")
        .eq("company_id", COMPANY_ID).execute().data
    )
    return {str(e["last_name"]).upper().replace(" ", "").replace("-", ""): e for e in lignes}


def fiches_des_matricules(par_nom: dict[str, dict], matricules) -> dict[str, dict]:
    """La fiche de chaque matricule Quadra, appariée comme à l'import des bulletins.

    Le matricule lu s'arrête au premier blanc (« MARTIN DUVAL » se lit « MARTIN ») et Quadra
    le coupe à dix caractères : un nom à deux mots ne retrouvait pas sa fiche, le
    solde le comptait sans fiche et refusait d'écrire, alors que l'import, qui
    tolère le préfixe, avait écrit son bulletin. Un préfixe qui désigne plusieurs
    fiches ne désigne personne.
    """
    from scripts.reprise_colorplast_import_litteral import _fiche_du_matricule

    return {nom: fiche for nom in matricules if (fiche := _fiche_du_matricule(par_nom, nom))}


def _simuler_les_conges(soldes: dict, fiches: dict, bascule: int) -> list[str]:
    """Les congés affichés après la reprise, simulée sans rien écrire, contre Quadra."""
    from scripts.reprise_colorplast_import_litteral import etiquette
    from scripts.reprise_conges_en_memoire import (
        ajustements_en_memoire,
        solde_affiche,
        solde_affiche_apres_reprise,
    )

    ecarts = []
    print(f"\nCongés au {bascule:02d}/{ANNEE} (N-1 / N) : Quadra, MARTINE avant, MARTINE après la reprise")
    for nom, solde in soldes.items():
        fiche = fiches.get(nom)
        if not fiche:
            continue
        quadra = (solde["conges"]["cp_n1"], solde["conges"]["cp_n"])
        with ajustements_en_memoire():
            avant = solde_affiche(fiche["id"], ANNEE, bascule)
            apres = solde_affiche_apres_reprise(COMPANY_ID, fiche["id"], ANNEE, bascule, *quadra)
        if apres is None:
            verdict = "plus de compteur au mois de bascule (sortie)"
        elif all(abs(a - q) < 0.005 for a, q in zip(apres, quadra)):
            verdict = "= Quadra"
        else:
            verdict = "ÉCART"
            ecarts.append(etiquette(fiche))
        print(f"  {etiquette(fiche):14s} Quadra {quadra[0]:6.2f} / {quadra[1]:5.2f}   avant {avant}   après {apres}   {verdict}")
    return ecarts


def main(appliquer: bool, bascule: int = BASCULE_PAR_DEFAUT, sans_fiche: int = 0) -> int:
    from scripts.reprise_colorplast_import_litteral import etiquette

    mois_repris = tuple(range(1, bascule + 1))
    lus = {m: lire_bulletins(ANNEE, m) for m in mois_repris}
    soldes = construire_le_solde(lus, bascule)
    admin = get_supabase_admin_client()
    fiches = fiches_des_matricules(_fiches_par_nom(admin), soldes)

    print(f"Reprise Colorplast au {bascule:02d}/{ANNEE} — "
          f"{len(soldes)} salariés présents au mois de bascule\n")

    anomalies = 0
    ignores = []
    for nom, solde in soldes.items():
        qui = etiquette(fiches.get(nom), lus[bascule][nom].infos.get("entree"))
        ecart = round(solde["controle_somme_des_bruts"] - solde["cumuls"]["brut_total"], 2)
        if abs(ecart) >= 0.01:
            print(f"!! {qui} : somme des bruts mensuels {solde['controle_somme_des_bruts']:.2f} "
                  f"contre brut cumulé imprimé {solde['cumuls']['brut_total']:.2f} "
                  f"(écart {ecart:+.2f}) — lecture à revoir avant écriture")
            anomalies += 1
        if nom not in fiches:
            ignores.append(qui)
    if len(ignores) != sans_fiche:
        print(f"!! {len(ignores)} bulletin(s) du mois de bascule sans fiche, {sans_fiche} attendu(s) "
              f"(--sans-fiche) : " + ", ".join(ignores))
        anomalies += 1
    elif ignores:
        print("Sans fiche, laissés de côté (relancer une fois la fiche créée) : " + ", ".join(ignores))
    soldes_ecrits = {nom: s for nom, s in soldes.items() if nom in fiches}

    cles = ["brut_total", "heures_remunerees", "net_imposable", "impot_preleve_a_la_source",
            "reduction_generale_patronale", "cumul_pss_agirc_arrco", "hs_exonerees_ir_cumul"]
    entetes = ["brut", "heures", "net imp.", "PAS", "réd. gén.", "plafond", "HS exo IR"]
    print(f"{'Salarié':14s} " + " ".join(f"{e:>11s}" for e in entetes))
    for nom, solde in soldes_ecrits.items():
        vals = [solde["cumuls"][c] for c in cles]
        print(f"{etiquette(fiches[nom]):14s} " + " ".join(f"{v:11.2f}" for v in vals))

    print("\nComparaison avec nos compteurs actuels du mois de bascule (nous − Quadra) :")
    for nom, solde in soldes_ecrits.items():
        eid = fiches[nom]["id"]
        ligne = (admin.table("employee_schedules").select("cumuls")
                 .eq("employee_id", eid).eq("year", ANNEE).eq("month", bascule)
                 .limit(1).execute().data)
        nos = ((ligne or [{}])[0].get("cumuls") or {}).get("cumuls") or {}
        diffs = []
        for c in cles:
            if c in nos and nos[c] is not None:
                d = round(float(nos[c]) - solde["cumuls"][c], 2)
                if abs(d) >= 0.01:
                    diffs.append(f"{c} {d:+.2f}")
        print(f"  {etiquette(fiches[nom]):14s} " + ("; ".join(diffs) if diffs else ("aligné" if nos else "aucun cumul")))

    if anomalies:
        print(f"\n{anomalies} anomalie(s) : rien n'est écrit.")
        return 1
    if not appliquer:
        ecarts = _simuler_les_conges(soldes_ecrits, fiches, bascule)
        if ecarts:
            print("!! Congés qui ne retomberaient pas sur Quadra : " + ", ".join(ecarts))
        print(f"\nSimulation. Relancer avec --apply pour écrire le solde, reprendre les "
              f"congés et poser la bascule au {bascule:02d}/{ANNEE}.")
        return 1 if ecarts else 0

    fin_du_mois = date(ANNEE, bascule, monthrange(ANNEE, bascule)[1])
    for nom, solde in soldes_ecrits.items():
        eid = fiches[nom]["id"]
        charge = {"cumuls": solde["cumuls"], "periode": solde["periode"],
                  "reprise": solde["reprise"]}
        existe = (admin.table("employee_schedules").select("id")
                  .eq("employee_id", eid).eq("year", ANNEE).eq("month", bascule)
                  .limit(1).execute().data)
        if existe:
            admin.table("employee_schedules").update({"cumuls": charge}) \
                .eq("id", existe[0]["id"]).execute()
        else:
            admin.table("employee_schedules").insert(
                {"employee_id": eid, "company_id": COMPANY_ID, "year": ANNEE, "month": bascule,
                 "cumuls": charge}
            ).execute()
        apply_cp_solde_import(
            COMPANY_ID, eid, ANNEE,
            cp_n1_solde=solde["conges"]["cp_n1"], cp_n_solde=solde["conges"]["cp_n"],
            rtt_solde=0.0, month=bascule,
            note=f"Reprise Quadra au {fin_du_mois:%d/%m/%Y} "
                 f"(bascule de la société) : soldes du bulletin de {bascule:02d}/{ANNEE}, "
                 f"N-1 {solde['conges']['cp_n1']:.2f} / N {solde['conges']['cp_n']:.2f}",
        )
        print(f"  {etiquette(fiches[nom]):14s} solde d'ouverture et congés écrits")

    ligne = {"company_id": COMPANY_ID, "cutoff_year": ANNEE, "cutoff_month": bascule,
             "source": "bulletins", "previous_software": "Quadra",
             "note": f"Reprise Colorplast : Gaëlle a payé janvier à {bascule:02d}/{ANNEE} dans "
                     f"Quadra. Bulletins et compteurs repris littéralement des PDF ; la paie MARTINE "
                     f"commence le mois suivant (bascule posée le {date.today():%d/%m/%Y})."}
    if admin.table("company_payroll_takeover").select("id").eq("company_id", COMPANY_ID).execute().data:
        admin.table("company_payroll_takeover").update(ligne).eq("company_id", COMPANY_ID).execute()
    else:
        admin.table("company_payroll_takeover").insert(ligne).execute()
    print(f"\nBascule de la société posée au {bascule:02d}/{ANNEE}.")
    return 0


if __name__ == "__main__":
    _bascule = BASCULE_PAR_DEFAUT
    if "--bascule" in sys.argv:
        _bascule = int(sys.argv[sys.argv.index("--bascule") + 1])
    _sans_fiche = 0
    if "--sans-fiche" in sys.argv:
        _sans_fiche = int(sys.argv[sys.argv.index("--sans-fiche") + 1])
    raise SystemExit(main("--apply" in sys.argv, _bascule, _sans_fiche))
