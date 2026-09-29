"""Reprise Comitech : les bulletins Quadra de 2026, copiés dans notre format.

Même doctrine que Colorplast (cf. reprise_colorplast_import_litteral.py et
reprise_colorplast_solde_ouverture.py) : le passé appartient à Quadra, il se
copie, il ne se recalcule pas. Différence : Comitech n'a aucun bulletin en base,
il n'y a donc pas de rejeu à compléter. Chaque bulletin est entièrement bâti
depuis le PDF de Gaëlle :

- lignes du brut, cotisations rangées dans nos blocs (principales, allègements,
  CSG/CRDS non déductible, autres contributions), sommes versées après le net,
  acomptes, retenues, nets, impôt à la source, cumuls imprimés, compteurs de
  congés, coût employeur et allègement du mois ;
- les compteurs que Quadra imprime en mention (« Solde heures récup »,
  « Solde repos cadre », « Repos cadre pris ») sont gardés au bulletin ;
- le PDF du salarié, découpé dans celui du mois, est servi tel quel.

Chaque bulletin est contrôlé avant écriture : la somme des lignes du brut doit
redonner le brut imprimé, et brut − retenues + sommes versées après cotisations
le net payé. Un bulletin qui ne s'équilibre pas n'est pas écrit.

Au mois de bascule, pour chaque salarié présent :
- solde d'ouverture des cumuls de paie (employee_schedules.cumuls), contrôlé
  contre le cumul brut imprimé ;
- soldes de congés CP N-1 / N et repos des cadres (jours de temps choisi) en
  soldes d'ouverture datés (apply_cp_solde_import) ;
puis la bascule de la société (company_payroll_takeover) verrouille les mois
repris.

Les salariés sont appariés par numéro de sécurité sociale : Quadra les inscrit
parfois sous leur nom de naissance.

Usage (depuis backend/) :
    python -m scripts.reprise_comitech                   # simulation, jusqu'à juillet
    python -m scripts.reprise_comitech --jusqu-a 8       # simulation, jusqu'à août
    python -m scripts.reprise_comitech --apply           # écrit
"""

from __future__ import annotations

import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import get_supabase_admin_client, supabase  # noqa: E402
from scripts.backtest.colorplast_lignes_quadra import (  # noqa: E402
    lire_bulletins,
    pdf_du_mois,
)
from scripts.reprise_colorplast_import_litteral import (  # noqa: E402
    _brut_du_mois,
    _compteurs_affiches,
    _cumuls_affiches,
    _LIBELLES_GAIN,
    _LIBELLES_PERTE,
    _pages_du_salarie,
    _pied_de_page_du_pdf,
    _synthese_du_pdf,
)
from scripts.reprise_colorplast_solde_ouverture import (  # noqa: E402
    EST_DEDUCTION_HS,
    EST_REDUCTION_GENERALE,
    RATIO_HS_DEFISCALISEES,
    _heures_sup_brut,
    _somme_des_lignes,
)

SOCIETE = "comitech"
COMPANY_ID = "12cd8c71-da13-43f9-9151-475c4d5e8812"
ANNEE = 2026
SEAU = "payslips"
TOLERANCE = 0.011


def _norme(libelle: Any) -> str:
    return " ".join(str(libelle or "").split()).upper()


def _nir(valeur: Any) -> str:
    """Les 13 caractères du numéro : le bulletin imprime aussi la clé, la fiche et la DSN non."""
    return re.sub(r"\s", "", str(valeur or "")).upper()[:13]


def _arrondi(valeur: Any) -> float:
    return round(float(valeur or 0.0), 2)


# ---------------------------------------------------------------------------
# Zones du bulletin
# ---------------------------------------------------------------------------


def zones(bulletin) -> dict[str, list]:
    """Les lignes par zone : brut, cotisations, avant le net imposable, après."""
    rangees: dict[str, list] = {"brut": [], "cotisations": [], "avant_net": [], "apres_net": []}
    # Un bulletin sans salaire (participation versée à un ancien salarié) n'a pas
    # de ligne « SALAIRE BRUT » : tout y est cotisation ou somme versée.
    # Un mois entièrement absent a un brut nul : Quadra n'imprime alors pas de
    # « SALAIRE BRUT », mais ses lignes de salaire et d'absence sont bien du brut.
    a_un_brut = any(_norme(lg.libelle) in ("SALAIRE BRUT", "SALAIRE DE BASE") for lg in bulletin.lignes)
    zone = "brut" if a_un_brut else "cotisations"
    for lg in bulletin.lignes:
        lib = _norme(lg.libelle)
        # Le net négatif d'un mois précédent, reporté : une retenue sur le net.
        if lib.startswith("REPORT NAP"):
            rangees["apres_net"].append(lg)
            continue
        if lib == "SALAIRE BRUT":
            zone = "cotisations"
            continue
        if lib.startswith("TOTAL DES RETENUES"):
            zone = "avant_net"
            continue
        if lib == "NET IMPOSABLE":
            zone = "apres_net"
            continue
        rangees[zone].append(lg)
    return rangees


def _ligne_totale(bulletin, debut: str):
    return next((lg for lg in bulletin.lignes if _norme(lg.libelle).startswith(debut)), None)


# ---------------------------------------------------------------------------
# Brut
# ---------------------------------------------------------------------------


def lignes_du_brut(bulletin) -> tuple[list[dict], dict[str, Any]]:
    """Les lignes du brut dans la forme de `calcul_du_brut`, et les mentions.

    Les lignes « CONGÉS PAYÉS : jjmmaa » sont gardées ou non selon qu'elles
    équilibrent le brut : chez Colorplast elles doublaient une autre ligne.
    """
    brut = _brut_du_mois(bulletin)
    lignes: list[dict] = []
    conges: list[dict] = []
    mentions: dict[str, Any] = {}
    for lg in zones(bulletin)["brut"]:
        lib = _norme(lg.libelle)
        compteur = re.match(r"(SOLDE HEURES RECUP|SOLDE REPOS CADRE|REPOS CADRE PRIS)\s*=\s*(-?[\d.,]+)\s*([HJ])", lib)
        if compteur:
            valeur = float(compteur.group(2).replace(",", "."))
            cle = {"SOLDE HEURES RECUP": "solde_heures_recup", "SOLDE REPOS CADRE": "solde_repos_cadre",
                   "REPOS CADRE PRIS": "repos_cadre_pris"}[compteur.group(1)]
            mentions[cle] = valeur
            continue
        if lg.gain is None and lg.montant_sal is None:
            if lib.startswith("FORFAIT") and "JOURS" in lib:
                mentions["forfait"] = lg.libelle.strip()
            continue
        if lg.gain is not None:
            ligne = {
                "libelle": _LIBELLES_GAIN.get(lib, lg.libelle.strip()),
                "quantite": lg.base,
                "taux": lg.taux,
                "gain": _arrondi(lg.gain),
                "perte": None,
                **({"code": lg.code} if lg.code else {}),
            }
        else:
            ligne = {
                "libelle": _LIBELLES_PERTE.get(lib, lg.libelle.strip()),
                "quantite": lg.base,
                "taux": lg.taux,
                "gain": None,
                "perte": _arrondi(lg.montant_sal),
                **({"code": lg.code} if lg.code else {}),
            }
        (conges if lib.startswith(("CONGÉS PAYÉS :", "CONGES PAYES :")) else lignes).append(ligne)

    def somme(ls):
        return round(sum((l["gain"] or 0.0) - (l["perte"] or 0.0) for l in ls), 2)

    if conges and abs(somme(lignes + conges) - brut) < abs(somme(lignes) - brut):
        lignes = lignes + conges
    mentions["ecart_brut"] = round(brut - somme(lignes), 2)
    return lignes, mentions


# ---------------------------------------------------------------------------
# Cotisations
# ---------------------------------------------------------------------------

_RUBRIQUES = (
    ("SÉCU.SOC-MAL", "sante", "securite_sociale_maladie"),
    ("ACC. DU TRAV", "at_mp", "at_mp"),
    ("SÉCU.SOC PLAFONNÉE", "retraite", "vieillesse_plafonnee"),
    ("SÉCU.SOC DÉPLAFONNÉE", "retraite", "vieillesse_deplafonnee"),
    ("COMPLÉMENTAIRE TRANCHE 1", "retraite", "retraite_comp_t1"),
    ("COMPLÉMENTAIRE TRANCHE 2", "retraite", "retraite_comp_t2"),
    ("SUPPLÉMENTAIRE", "retraite", "retraite_supplementaire"),
    ("APEC", "retraite", "apec"),
    ("FAMILLE", "famille", "allocations_familiales"),
    ("CHÔMAGE", "chomage", "assurance_chomage"),
    ("AGS", "chomage", "ags"),
    ("CSG DÉDUCTIBLE", "csg_deductible", "csg_deductible"),
    ("AUTRES CONTRIB", "autres_contributions_employeur", "autres_contributions"),
)
_ALLEGEMENTS = (
    (EST_REDUCTION_GENERALE, "reduction_generale"),
    (re.compile(r"REDUCTION SALARIALE HS", re.I), "reduction_hs_salariale"),
    (EST_DEDUCTION_HS, "deduction_hs_patronale"),
)


def _ligne_de_cotisation(lg, rubrique: str, coti_id: str) -> dict:
    taux = lg.taux / 100 if lg.taux is not None else None
    salarial = lg.montant_sal if lg.montant_sal is not None else 0.0
    return {
        "libelle": " ".join(lg.libelle.split()),
        "coti_id": coti_id,
        "rubrique": rubrique,
        "base": _arrondi(lg.base) if lg.base is not None else None,
        "taux_salarial": taux if lg.montant_sal is not None else None,
        "taux_patronal": None,
        "montant_salarial": _arrondi(salarial),
        "montant_patronal": _arrondi(lg.montant_pat),
        **({"code": lg.code} if lg.code else {}),
    }


def structure_des_cotisations(bulletin) -> dict:
    principales: list[dict] = []
    allegements: list[dict] = []
    autres: list[dict] = []
    csg_nd: list[dict] = []
    for lg in zones(bulletin)["cotisations"]:
        lib = _norme(lg.libelle)
        allegement = next((cid for motif, cid in _ALLEGEMENTS if motif.search(lg.libelle)), None)
        if allegement:
            ligne = _ligne_de_cotisation(lg, "exonerations", allegement)
            allegements.append(ligne)
            continue
        if (lg.code or "").startswith(("EMU", "SMU")):
            principales.append(_ligne_de_cotisation(lg, "sante", "mutuelle"))
            continue
        if (lg.code or "").startswith("EPR"):
            principales.append(_ligne_de_cotisation(lg, "prevoyance", "prevoyance"))
            continue
        rubrique, coti_id = next(
            ((r, c) for debut, r, c in _RUBRIQUES if lib.startswith(debut)), ("autres", "autre")
        )
        cible = autres if rubrique == "autres_contributions_employeur" else principales
        cible.append(_ligne_de_cotisation(lg, rubrique, coti_id))
    # Après le net imposable : CSG/CRDS non déductible et mutuelle facultative.
    for lg in zones(bulletin)["apres_net"]:
        lib = _norme(lg.libelle)
        if lib.startswith("CSG/CRDS NON DÉDUCTIBLE"):
            ligne = _ligne_de_cotisation(lg, "csg_non_deductible", "csg_non_deductible")
            if lg.montant_sal is None and lg.gain is not None:
                # Régularisation imprimée en gain : une CSG rendue.
                ligne["montant_salarial"] = -_arrondi(lg.gain)
            csg_nd.append(ligne)
        elif (lg.code or "").startswith("SMU"):
            ligne = _ligne_de_cotisation(lg, "sante", "mutuelle")
            montant = lg.montant_sal if lg.montant_sal is not None else -(lg.gain or 0.0)
            ligne["montant_salarial"] = _arrondi(montant)
            principales.append(ligne)
    blocs = (principales, allegements, csg_nd, autres)
    total_sal = round(sum(l["montant_salarial"] for b in blocs for l in b), 2)
    total_pat = round(sum(l["montant_patronal"] for b in blocs for l in b), 2)
    avant = round(sum(l["montant_salarial"] for b in (principales, allegements) for l in b
                      if not str(l.get("code") or "").startswith("SMU")), 2)
    return {
        "bloc_principales": principales,
        "bloc_allegements": allegements,
        "bloc_csg_non_deductible": csg_nd,
        "bloc_autres_contributions": {"lignes": autres, "total": round(sum(l["montant_patronal"] for l in autres), 2)},
        "total_salarial": total_sal,
        "total_patronal": total_pat,
        "total_avant_csg_crds": {
            "libelle": "Total des retenues (avant CSG/CRDS non déductible)",
            "montant_salarial": avant,
            "montant_patronal": round(total_pat, 2),
        },
    }


# ---------------------------------------------------------------------------
# Après le net
# ---------------------------------------------------------------------------

_REINTEGRATION = "COTIS. RETRAITE/PRÉV./F.SANTÉ"


def apres_le_net(bulletin) -> tuple[list[dict], list[dict]]:
    """(sommes versées après cotisations, retenues sur le net) hors CSG et mutuelle."""
    versees: list[dict] = []
    retenues: list[dict] = []
    for zone in ("avant_net", "apres_net"):
        for lg in zones(bulletin)[zone]:
            lib = _norme(lg.libelle)
            if lib.startswith((_REINTEGRATION, "CSG/CRDS NON DÉDUCTIBLE")) or (lg.code or "").startswith("SMU"):
                continue
            if lg.gain is not None:
                versees.append({"libelle": lg.libelle.strip(), "montant": _arrondi(lg.gain),
                                **({"code": lg.code} if lg.code else {}), "zone": zone})
            elif lg.montant_sal is not None:
                retenues.append({"libelle": lg.libelle.strip(), "montant": _arrondi(lg.montant_sal),
                                 **({"code": lg.code} if lg.code else {}), "zone": zone})
    return versees, retenues


def equilibre(bulletin, structure: dict, versees: list[dict], retenues: list[dict]) -> float:
    """Écart entre le net imprimé et brut − cotisations + versé − retenu − impôt.

    Une retenue imprimée que le net de Quadra ne déduit pas (saisie d'avril) est
    marquée comme telle au lieu de fausser l'équilibre : on copie, on ne corrige pas.
    """
    brut = _brut_du_mois(bulletin)
    impot = float(bulletin.net.get("pas_montant") or 0.0)
    imprime = float(bulletin.net.get("net_a_payer") or 0.0)

    def ecart() -> float:
        calcule = (brut - structure["total_salarial"] + sum(v["montant"] for v in versees)
                   - sum(r["montant"] for r in retenues if not r.get("sans_effet_sur_le_net")) - impot)
        return round(imprime - calcule, 2)

    e = ecart()
    if abs(e) > TOLERANCE:
        for r in retenues:
            if abs(r["montant"] - e) <= TOLERANCE:
                r["sans_effet_sur_le_net"] = True
                return ecart()
    return e


# ---------------------------------------------------------------------------
# Bulletin complet
# ---------------------------------------------------------------------------


def donnees_du_bulletin(bulletin, annee: int, mois: int, fiche: dict, societe: dict) -> dict:
    lignes, mentions = lignes_du_brut(bulletin)
    structure = structure_des_cotisations(bulletin)
    versees, retenues = apres_le_net(bulletin)
    synthese = _synthese_du_pdf({}, bulletin)
    pied = _pied_de_page_du_pdf({}, bulletin)
    pied["solde_conges"] = _compteurs_affiches(bulletin, annee, mois)
    compteurs = {k: v for k, v in mentions.items() if k in ("solde_heures_recup", "solde_repos_cadre",
                                                             "repos_cadre_pris", "forfait")}
    if compteurs:
        pied["compteurs_quadra"] = compteurs
    fin = date(annee, mois, 28)
    while True:
        try:
            fin = fin.replace(day=fin.day + 1)
        except ValueError:
            break
    return {
        "en_tete": {
            "mois": mois,
            "annee": annee,
            "periode": f"{mois:02d}/{annee}",
            "date_debut_periode": f"{annee:04d}-{mois:02d}-01",
            "date_fin_periode": fin.isoformat(),
            "salarie": {
                "nom": fiche.get("last_name"),
                "prenom": fiche.get("first_name"),
                "emploi": bulletin.infos.get("emploi") or fiche.get("job_title"),
                "statut": fiche.get("statut"),
                "coefficient": bulletin.infos.get("coefficient"),
                "date_entree": bulletin.infos.get("entree"),
                "date_sortie": bulletin.infos.get("sortie"),
            },
            "entreprise": {"raison_sociale": societe.get("company_name"), "siret": societe.get("siret")},
        },
        "salaire_brut": _brut_du_mois(bulletin),
        "calcul_du_brut": lignes,
        "details_absences": [],
        "details_conges": [],
        "structure_cotisations": structure,
        "primes_non_soumises": [
            {"libelle": v["libelle"], "montant": v["montant"], **({"code": v["code"]} if "code" in v else {})}
            for v in versees
        ],
        "retenues_sur_net": retenues,
        "synthese_net": synthese,
        "net_a_payer": float(bulletin.net.get("net_a_payer") or 0.0),
        "cumuls": _cumuls_affiches(bulletin, annee, mois),
        "pied_de_page": pied,
        "is_bulletin_sortie": bool(bulletin.infos.get("sortie")),
        "reprise": {
            "logiciel_precedent": "Quadra",
            "document": "PDF d'origine, pages " + ",".join(str(p) for p in bulletin.pages),
            "source": f"data/{SOCIETE}/bulletins/{annee:04d}-{mois:02d}",
            "avertissement": "Bulletin repris de Quadra : le document affiché est l'original, "
                             "les données ci-dessus en sont la copie ligne à ligne.",
        },
    }


# ---------------------------------------------------------------------------
# Solde d'ouverture au mois de bascule
# ---------------------------------------------------------------------------


def solde_d_ouverture(lus: dict[int, dict], bascule: int, matricule: str) -> dict:
    mois_presents = [m for m in sorted(lus) if m <= bascule and matricule in lus[m]]
    dernier = lus[bascule][matricule]
    reduction_generale = deduction_hs = hs_brut = plafonds = bruts = 0.0
    for m in mois_presents:
        b = lus[m][matricule]
        reduction_generale += _somme_des_lignes(b, EST_REDUCTION_GENERALE)
        deduction_hs += _somme_des_lignes(b, EST_DEDUCTION_HS)
        hs_brut += _heures_sup_brut(b)
        plafonds += float(b.droite.get("plafond") or 0.0)
        bruts += _brut_du_mois(b)
    brut = float(dernier.droite.get("cumul_bruts") or 0.0)
    net_hs_exo = float(dernier.net.get("net_hs_exo_cumul") or 0.0)
    tranche_2 = round(max(0.0, brut - plafonds), 2)
    return {
        "controle_somme_des_bruts": round(bruts, 2),
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
            "brut_reference_n_1": _brut_du_mois(dernier),
            "brut_reference_period_start": f"{ANNEE:04d}-06-01",
            "brut_reference_period_end": f"{ANNEE + 1:04d}-05-31",
        },
        "periode": {"annee_en_cours": ANNEE, "dernier_mois_calcule": bascule},
        "reprise": {
            "logiciel_precedent": "Quadra",
            "source": "bulletins PDF lus ligne à ligne",
            "mois_de_bascule": f"{ANNEE:04d}-{bascule:02d}",
            "mois_repris": mois_presents,
            "fait_foi": True,
        },
    }


def fusionner_les_soldes(soldes: list[dict]) -> dict:
    """Un solde d'ouverture pour une fiche qui a eu plusieurs matricules Quadra.

    Fin de CDD le 30/08 puis contrat d'apprentissage le 31/08 : Quadra ouvre un
    second matricule, chacun avec ses cumuls ; la base n'a qu'une fiche par numéro
    de sécurité sociale. Les montants s'additionnent, les dates restent.
    """
    if len(soldes) == 1:
        return soldes[0]
    fusion = {
        "controle_somme_des_bruts": round(sum(x["controle_somme_des_bruts"] for x in soldes), 2),
        "cumuls": {},
        "periode": dict(soldes[0]["periode"]),
        "reprise": dict(soldes[0].get("reprise") or {}),
    }
    for cle, valeur in soldes[0]["cumuls"].items():
        if isinstance(valeur, (int, float)):
            fusion["cumuls"][cle] = round(sum(float(x["cumuls"].get(cle) or 0.0) for x in soldes), 2)
        else:
            fusion["cumuls"][cle] = valeur
    fusion["reprise"]["mois_repris"] = sorted(
        {m for x in soldes for m in (x.get("reprise") or {}).get("mois_repris") or []}
    )
    return fusion


def _date_fr(texte: Any) -> str:
    """« 31/08/2026 » → « 2026-08-31 », pour trier des dates d'entrée."""
    j, m, a = (str(texte or "01/01/1900").split("/") + ["", "", ""])[:3]
    return f"{a}-{m}-{j}"


# ---------------------------------------------------------------------------
# Programme
# ---------------------------------------------------------------------------


def main(appliquer: bool, jusqu_a: int, sans: tuple[str, ...] = ()) -> int:
    admin = get_supabase_admin_client()
    fiches = admin.table("employees").select(
        "id, last_name, first_name, nir, statut, job_title, employee_folder_name, employment_status, is_forfait_jour"
    ).eq("company_id", COMPANY_ID).execute().data
    par_nir = {_nir(f["nir"]): f for f in fiches if f.get("nir")}
    societe = admin.table("companies").select("company_name, siret").eq("id", COMPANY_ID).execute().data[0]

    mois_repris = tuple(range(1, jusqu_a + 1))
    lus = {m: lire_bulletins(ANNEE, m, SOCIETE) for m in mois_repris}
    anomalies: list[str] = []
    a_ecrire: list[tuple[int, str, Any, dict]] = []

    for mois in mois_repris:
        print(f"\n=== {mois:02d}/{ANNEE} — {len(lus[mois])} bulletins")
        for mat, b in sorted(lus[mois].items()):
            if mat in sans:
                print(f"  {mat:11s} écarté (--sans)")
                continue
            fiche = par_nir.get(_nir(b.infos.get("nir")))
            if not fiche:
                anomalies.append(f"{mois:02d} {mat} : aucune fiche pour ce numéro de sécurité sociale")
                print(f"  {mat:11s} !! aucune fiche (NIR)")
                continue
            donnees = donnees_du_bulletin(b, ANNEE, mois, fiche, societe)
            ecart_brut = lignes_du_brut(b)[1]["ecart_brut"]
            ecart_net = equilibre(b, donnees["structure_cotisations"], donnees["primes_non_soumises"],
                                  donnees["retenues_sur_net"])
            sans_effet = [r for r in donnees["retenues_sur_net"] if r.get("sans_effet_sur_le_net")]
            if sans_effet:
                print(f"  {mat:11s} .. retenue imprimée sans effet sur le net de Quadra : "
                      + ", ".join(f"{r['libelle']} {r['montant']:.2f}" for r in sans_effet))
            total = _ligne_totale(b, "TOTAL DES RETENUES")
            ecart_total = None
            if total is not None and total.montant_sal is not None:
                sal_avant = sum(l["montant_salarial"] for l in donnees["structure_cotisations"]["bloc_principales"]
                                + donnees["structure_cotisations"]["bloc_allegements"]
                                if not (l.get("code") or "").startswith("SMU"))
                ecart_total = round(float(total.montant_sal) - sal_avant, 2)
            etat = "ok"
            if abs(ecart_brut) > TOLERANCE or abs(ecart_net) > TOLERANCE or (ecart_total is not None and abs(ecart_total) > TOLERANCE):
                etat = f"ÉCART brut {ecart_brut:+.2f} net {ecart_net:+.2f} retenues {ecart_total if ecart_total is not None else 0:+.2f}"
                anomalies.append(f"{mois:02d} {mat} : {etat}")
            cp = b.cp.get("Solde", (0.0, 0.0))
            cpt = donnees["pied_de_page"].get("compteurs_quadra") or {}
            print(f"  {mat:11s} brut {donnees['salaire_brut']:9.2f} net {donnees['net_a_payer']:9.2f} "
                  f"CP {cp[0]:5.2f}/{cp[1]:5.2f} {cpt if cpt else ''} [{etat}]")
            a_ecrire.append((mois, mat, b, {"fiche": fiche, "donnees": donnees}))

    # Plusieurs bulletins du même mois pour une même fiche (fin de CDD puis
    # apprentissage) : un seul bulletin en base, celui au brut le plus élevé, avec les pages des
    # autres jointes à son PDF et leur résumé dans la reprise.
    groupes: dict[tuple[int, str], list] = {}
    for ligne in a_ecrire:
        groupes.setdefault((ligne[0], ligne[3]["fiche"]["id"]), []).append(ligne)
    a_ecrire = []
    for (mois, _), lignes in sorted(groupes.items()):
        lignes.sort(key=lambda x: -x[3]["donnees"]["salaire_brut"])
        principal = lignes[0]
        principal[3]["pages"] = list(principal[2].pages)
        if len(lignes) > 1:
            autres = [{"matricule": m, "pages": list(b.pages), "brut": v["donnees"]["salaire_brut"],
                       "net_a_payer": v["donnees"]["net_a_payer"], "entree": b.infos.get("entree"),
                       "sortie": b.infos.get("sortie"), "emploi": b.infos.get("emploi")}
                      for _, m, b, v in lignes[1:]]
            principal[3]["donnees"]["reprise"]["autres_bulletins_du_mois"] = autres
            principal[3]["donnees"]["reprise"]["document"] = (
                "PDF d'origine : " + " puis ".join(f"{m} pages {','.join(str(p) for p in b.pages)}" for _, m, b, _ in lignes)
            )
            for _, m, b, _ in lignes[1:]:
                principal[3]["pages"] += list(b.pages)
            print(f"  {mois:02d} {principal[1]} : bulletin gardé, joint à ses pages "
                  + ", ".join(f"{a['matricule']} ({a['brut']:.2f} brut, entrée {a['entree']})" for a in autres))
        a_ecrire.append(principal)

    bascule = mois_repris[-1]
    print(f"\n=== Solde d'ouverture au {bascule:02d}/{ANNEE}")
    par_fiche: dict[str, list] = {}
    for mat, b in sorted(lus[bascule].items()):
        if mat in sans:
            continue
        fiche = par_nir.get(_nir(b.infos.get("nir")))
        if not fiche:
            continue
        solde = solde_d_ouverture(lus, bascule, mat)
        ecart = round(solde["controle_somme_des_bruts"] - solde["cumuls"]["brut_total"], 2)
        if abs(ecart) > TOLERANCE:
            anomalies.append(f"{mat} : somme des bruts {solde['controle_somme_des_bruts']:.2f} contre cumul imprimé "
                             f"{solde['cumuls']['brut_total']:.2f}")
        par_fiche.setdefault(fiche["id"], []).append((mat, b, solde, fiche))
    soldes: dict[str, dict] = {}
    for lignes in par_fiche.values():
        # Les congés et compteurs sont ceux du contrat qui continue : le dernier entré.
        lignes.sort(key=lambda x: _date_fr(x[1].infos.get("entree")))
        mat, b, _, fiche = lignes[-1]
        solde = fusionner_les_soldes([x[2] for x in lignes])
        if len(lignes) > 1:
            print(f"  {mat:11s} solde fusionné de " + " + ".join(x[0] for x in lignes)
                  + f" ; congés et compteurs du dernier contrat ({b.infos.get('entree')})")
        soldes[mat] = {"fiche": fiche, "solde": solde, "bulletin": b}
        c = solde["cumuls"]
        print(f"  {mat:11s} brut {c['brut_total']:10.2f} heures {c['heures_remunerees']:8.2f} "
              f"HS {c['heures_supplementaires_remunerees']:7.2f} net imp. {c['net_imposable']:10.2f} "
              f"réd. gén. {c['reduction_generale_patronale']:9.2f} "
              f"(écart {round(solde['controle_somme_des_bruts'] - c['brut_total'], 2):+.2f})")

    presents = {_nir(v["fiche"]["nir"]) for v in soldes.values()}
    actifs_sans_bulletin = [f"{f['last_name']} ({f['employment_status']})" for f in fiches
                            if (f.get("employment_status") or "actif") in ("actif", "active")
                            and _nir(f.get("nir")) not in presents]
    if actifs_sans_bulletin:
        print("\nFiches actives sans bulletin au mois de bascule : " + ", ".join(actifs_sans_bulletin))

    if anomalies:
        print(f"\n{len(anomalies)} anomalie(s) :")
        for a in anomalies:
            print("  - " + a)
        print("Rien n'est écrit tant qu'une anomalie subsiste.")
        return 1
    if not appliquer:
        print(f"\nSimulation : {len(a_ecrire)} bulletins, {len(soldes)} soldes d'ouverture. "
              "Relancer avec --apply pour écrire.")
        return 0

    # --- Écriture ------------------------------------------------------------
    from app.modules.absences.application.leave_settings_commands import apply_cp_solde_import

    for mois, mat, b, v in a_ecrire:
        fiche, donnees = v["fiche"], v["donnees"]
        dossier = fiche.get("employee_folder_name") or f"{fiche['last_name']}_{fiche['first_name']}"
        nom_pdf = f"Bulletin_{dossier}_{mois:02d}-{ANNEE}.pdf"
        chemin = f"{COMPANY_ID}/{fiche['id']}/bulletins/{nom_pdf}"
        supabase.storage.from_(SEAU).upload(
            path=chemin,
            file=_pages_du_salarie(pdf_du_mois(ANNEE, mois, SOCIETE), v.get("pages") or b.pages),
            file_options={"x-upsert": "true", "content-type": "application/pdf"},
        )
        url = supabase.storage.from_(SEAU).create_signed_url(chemin, 3600, options={"download": True})["signedURL"]
        admin.table("payslips").upsert(
            {
                "employee_id": fiche["id"],
                "company_id": COMPANY_ID,
                "year": ANNEE,
                "month": mois,
                "name": nom_pdf,
                "payslip_data": donnees,
                "pdf_storage_path": chemin,
                "url": url,
                "origine": "importe",
            },
            on_conflict="company_id,employee_id,year,month",
        ).execute()
    print(f"\n{len(a_ecrire)} bulletins écrits.")

    for mat, v in soldes.items():
        fiche, solde, b = v["fiche"], v["solde"], v["bulletin"]
        charge = {"cumuls": solde["cumuls"], "periode": solde["periode"], "reprise": solde["reprise"]}
        existe = admin.table("employee_schedules").select("id").eq("employee_id", fiche["id"]) \
            .eq("year", ANNEE).eq("month", bascule).limit(1).execute().data
        if existe:
            admin.table("employee_schedules").update({"cumuls": charge}).eq("id", existe[0]["id"]).execute()
        else:
            admin.table("employee_schedules").insert(
                {"employee_id": fiche["id"], "company_id": COMPANY_ID, "year": ANNEE, "month": bascule, "cumuls": charge}
            ).execute()
        cp_n1, cp_n = b.cp.get("Solde", (0.0, 0.0))
        compteurs = lignes_du_brut(b)[1]
        repos_cadre = compteurs.get("solde_repos_cadre")
        apply_cp_solde_import(
            COMPANY_ID, fiche["id"], ANNEE,
            cp_n1_solde=float(cp_n1), cp_n_solde=float(cp_n), rtt_solde=0.0, month=bascule,
            note=f"Reprise Quadra : bulletin de {bascule:02d}/{ANNEE}",
        )
        if repos_cadre is not None:
            admin.table("employee_leave_adjustments").update(
                {"jtc_opening_balance": float(repos_cadre)}
            ).eq("employee_id", fiche["id"]).eq("year", ANNEE).execute()
        print(f"  {mat:11s} solde d'ouverture et congés écrits"
              + (f", repos cadre {repos_cadre} j" if repos_cadre is not None else ""))

    existante = admin.table("company_payroll_takeover").select("company_id").eq("company_id", COMPANY_ID).execute().data
    ligne = {"company_id": COMPANY_ID, "cutoff_year": ANNEE, "cutoff_month": bascule, "source": "bulletins",
             "previous_software": "Quadra",
             "note": f"Reprise Quadra de janvier à {bascule:02d}/{ANNEE}, le {datetime.now():%d/%m/%Y}"}
    if existante:
        admin.table("company_payroll_takeover").update(ligne).eq("company_id", COMPANY_ID).execute()
    else:
        admin.table("company_payroll_takeover").insert(ligne).execute()
    print(f"\nBascule de la société posée au {bascule:02d}/{ANNEE}.")
    return 0


if __name__ == "__main__":
    jusqu_a = 7
    if "--jusqu-a" in sys.argv:
        jusqu_a = int(sys.argv[sys.argv.index("--jusqu-a") + 1])
    # --sans MAT1,MAT2 : écarte des bulletins sans fiche en base (embauche à créer
    # d'abord), repris plus tard par une nouvelle exécution.
    sans = ()
    if "--sans" in sys.argv:
        sans = tuple(m.strip().upper() for m in sys.argv[sys.argv.index("--sans") + 1].split(",") if m.strip())
    raise SystemExit(main("--apply" in sys.argv, jusqu_a, sans))
