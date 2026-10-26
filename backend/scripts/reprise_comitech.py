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

Un salarié revenu en cours d'année sur sa fiche (même matricule Quadra, nouvelle
date d'entrée) ouvre avec les cumuls de son seul contrat en cours, comme MARTINE au
premier mois d'un contrat. Ses congés ne sont repris que si la fiche porte ce
contrat : sur une fiche encore sortie, le solde se calculerait sur l'ancien contrat
(rouvrir la fiche par « Nouveau contrat », puis relancer).

La simulation montre les congés qu'affichera MARTINE au mois de bascule après la
reprise (`apply_cp_solde_import` rejoué en mémoire, scripts/reprise_conges_en_memoire.py).

Usage (depuis backend/) :
    python -m scripts.reprise_comitech                   # simulation, jusqu'à juillet
    python -m scripts.reprise_comitech --jusqu-a 8       # simulation, jusqu'à août
    python -m scripts.reprise_comitech --jusqu-a 9 --mois 9           # septembre seul, simulation
    python -m scripts.reprise_comitech --jusqu-a 9 --mois 9 --apply   # écrit septembre, l'ouverture au 30/09
                                                                       # et la bascule
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
    base_du_dixieme,
)

SOCIETE = "comitech"
COMPANY_ID = "12cd8c71-da13-43f9-9151-475c4d5e8812"
ANNEE = 2026
SEAU = "payslips"
TOLERANCE = 0.011


def regler_pour(societe: str, company_id: str, tdelta: float) -> None:
    """Fait servir ce script à une autre société payée par Quadra (Mont Blanc).

    `societe` : dossier sous data/ ; `tdelta` : Tdelta de la réduction générale 2026
    (0,3781 sous 50 salariés, 0,3821 à partir de 50), qui sert à retrouver les heures
    de SMIC de Quadra (`smic_retrouve_de_la_reduction`)."""
    global SOCIETE, COMPANY_ID, _RGDU_TDELTA, _RGDU_TMAX
    SOCIETE, COMPANY_ID = societe, company_id
    _RGDU_TDELTA, _RGDU_TMAX = tdelta, round(_RGDU_TMIN + tdelta, 4)


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
        # Sans « SALAIRE BRUT » (brut nul), une ligne rangée sous une section de
        # cotisations (Q100…Q802) n'est jamais du brut : Mont Blanc, mai 2026, mois
        # d'arrêt complet où la participation versée porte de la CSG.
        if zone == "brut" and lg.section:
            zone = "cotisations"
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


_FORFAIT_JOURS = re.compile(r"FORFAIT\s+(\d{2,3})\s+JOURS", re.I)
#: Retenues d'absence imprimées par Quadra (« Abs. paternité … », « Absence
#: maladie … », « Absence pour entrée ou sortie ») ; les congés payés
#: (« Jours Absence Congés Payés ») sont payés et n'en font pas partie.
_ABSENCE_RETENUE = re.compile(r"^ABS|ABSENCE", re.I)
_CONGES_PAYES = re.compile(r"CONG", re.I)
_MAINTIEN = re.compile(r"MAINTIEN", re.I)


def heures_reduction_forfait_quadra(bulletin) -> float | None:
    """Heures de la réduction générale d'un mois Quadra au forfait jours, ou None.

    Quadra n'imprime pas de « Cumul heures » pour un forfait jours : sans ce
    compte, l'ouverture portait 0 h et le premier bulletin MARTINE remboursait
    toute la réduction de l'année. Quadra compte 151,67 × jours du forfait / 218
    par mois (150,28 h pour 216 jours), corrigé du rapport des salaires quand
    une absence ou un arrêt réduit le salaire (salaire de base − retenues
    d'absence + maintien, sur le salaire de base). Même règle que le moteur
    (`heures_reduction_forfait_jours`), vérifiée au centime sur les bulletins
    Quadra de Comitech et de Mont-Blanc (2026).
    """
    from app.modules.payroll.engine.calcul_reduction_generale import (
        heures_reduction_forfait_jours,
        rapport_salaires_forfait_jours,
    )

    jours = next(
        (int(m.group(1)) for lg in bulletin.lignes if (m := _FORFAIT_JOURS.search(lg.libelle or ""))),
        None,
    )
    if jours is None:
        return None
    salaire = sum(lg.gain or 0.0 for lg in bulletin.lignes
                  if _norme(lg.libelle) == "SALAIRE DE BASE")
    retenues = sum(lg.montant_sal or 0.0 for lg in bulletin.lignes
                   if _ABSENCE_RETENUE.search((lg.libelle or "").strip())
                   and not _CONGES_PAYES.search(lg.libelle or ""))
    maintien = sum(lg.gain or 0.0 for lg in bulletin.lignes if _MAINTIEN.search(lg.libelle or ""))
    return heures_reduction_forfait_jours(
        jours, rapport_salaires_forfait_jours(salaire, retenues, maintien)
    )


def _heures_de_la_reduction(lus: dict[int, dict], mois_presents: list[int], matricule: str,
                            dernier) -> float:
    """Le « Cumul heures » imprimé, plus les heures des mois au forfait jours."""
    forfait = [heures_reduction_forfait_quadra(lus[m][matricule]) for m in mois_presents]
    return round(float(dernier.droite.get("cumul_heures") or 0.0)
                 + sum(h for h in forfait if h is not None), 2)


def point_de_depart_de_la_reduction(lus: dict[int, dict], bascule: int, matricule: str) -> dict:
    """Les mois de tête où Quadra n'a appliqué de réduction générale à personne.

    Comitech, janvier 2026 : aucune ligne de réduction sur les 17 bulletins, et la
    régularisation de Quadra part de février sans jamais reprendre janvier. Martine
    suit Quadra (décision du 17/10/2026) : l'ouverture garde le brut et les heures
    imprimés depuis janvier, et dit à part ce que la réduction laisse hors de sa
    base (`calcul_reduction_generale.CLES_POINT_DE_DEPART_REDUCTION`). Rien si la
    réduction commence au premier mois repris, si Quadra n'en a appliqué aucune de
    l'année, ou si le salarié n'était pas là avant le point de départ. Les heures
    posées à la fin sont celles de `base_de_la_reduction`.
    """
    mois = [m for m in sorted(lus) if m <= bascule]
    avec_reduction = [
        m for m in mois
        if any(_somme_des_lignes(b, EST_REDUCTION_GENERALE) for b in lus[m].values())
    ]
    if not avec_reduction or avec_reduction[0] == mois[0]:
        return {}
    depart = avec_reduction[0]
    hors = [m for m in mois if m < depart and matricule in lus[m]]
    if not hors:
        return {}
    return {
        "reduction_generale_depuis_mois": depart,
        "brut_hors_reduction_generale": round(sum(_brut_du_mois(lus[m][matricule]) for m in hors), 2),
        "heures_hors_reduction_generale": _heures_de_la_reduction(lus, hors, matricule, lus[hors[-1]][matricule]),
    }


#: Réduction générale 2026, moins de 50 salariés (Comitech) : Tmin, Tdelta, P, plafond,
#: et SMIC horaire du 1er janvier 2026 que la RGDU retient toute l'année.
_RGDU_TMIN, _RGDU_TDELTA, _RGDU_P, _RGDU_TMAX = 0.02, 0.3781, 1.75, 0.3981
_SMIC_HORAIRE_RGDU = 12.02


def smic_retrouve_de_la_reduction(brut: float, deja: float) -> tuple[float | None, str | None]:
    """Le SMIC cumulé que suppose une réduction cumulée `deja` sur `brut`, ou (None, raison).

    Inversion de la formule de la réduction générale : coefficient = réduction ÷ brut,
    SMIC = brut/3 × (1 + 2 × ((coef − 0,02)/Tdelta)^(1/1,75)), Tdelta = 0,3781 sous 50
    salariés, 0,3821 au-delà (`regler_pour`). Le coefficient de Quadra a
    4 décimales et la réduction en centimes le redonne à l'arrondi près (21,17 € sur
    53,18 € = 0,39808 : c'est le plafond 0,3981) : seul un coefficient strictement entre
    0,02 et 0,3981 à 4 décimales dit combien d'heures Quadra a retenues.
    """
    if brut <= 0 or deja <= 0:
        return None, "aucune réduction"
    coef = deja / brut
    if not _RGDU_TMIN < round(coef, 4) < _RGDU_TMAX:
        etat = "plafonné" if round(coef, 4) >= _RGDU_TMAX else "au plancher ou nul"
        return None, f"coefficient {coef:.5f} {etat}, hors de ]0,02 ; {_RGDU_TMAX}["
    return brut / 3 * (1 + 2 * ((coef - _RGDU_TMIN) / _RGDU_TDELTA) ** (1 / _RGDU_P)), None


def base_de_la_reduction(lus: dict[int, dict], bascule: int, matricule: str, cumuls: dict) -> dict:
    """Les clés qui font repartir la réduction de Martine de la base de Quadra.

    `cumuls` : ceux de l'ouverture (brut et heures imprimés, réduction appliquée).
    Deux écarts entre ces cumuls et la base de Quadra (décision du 17/10/2026) :
    - les mois de tête sans réduction (`point_de_depart_de_la_reduction`) ;
    - les heures : le « Cumul heures » imprimé n'est pas la base de SMIC que Quadra a
      retenue (arrêt payé en maintien). Elles sont retrouvées en inversant la formule
      sur sa réduction cumulée, contrôlé au 17/10 à moins de 0,3 h du SMIC de ses DSN
      de février à juin.
    `heures_hors_reduction_generale` = heures imprimées − heures retrouvées, négatif quand
    Quadra en a retenu plus (voir `calcul_reduction_generale.CLES_POINT_DE_DEPART_REDUCTION`).
    Rend {"cles", "heures_imprimees", "heures_retrouvees", "raison"} : les clés à poser,
    et de quoi les relire.
    """
    depart = point_de_depart_de_la_reduction(lus, bascule, matricule)
    heures = float(cumuls.get("heures_remunerees") or 0.0)
    brut_base = round(float(cumuls.get("brut_total") or 0.0)
                      - float(depart.get("brut_hors_reduction_generale") or 0.0), 2)
    heures_imprimees = round(heures - float(depart.get("heures_hors_reduction_generale") or 0.0), 2)
    deja = abs(float(cumuls.get("reduction_generale_patronale") or 0.0))
    smic, raison = smic_retrouve_de_la_reduction(brut_base, deja)
    heures_retrouvees = round(smic / _SMIC_HORAIRE_RGDU, 2) if smic else None

    cles = {k: v for k, v in depart.items() if k != "heures_hors_reduction_generale"}
    if heures_retrouvees is not None:
        hors = round(heures - heures_retrouvees, 2)
        if cles or abs(hors) >= 0.005:
            cles["heures_hors_reduction_generale"] = hors
    elif "heures_hors_reduction_generale" in depart:
        cles["heures_hors_reduction_generale"] = depart["heures_hors_reduction_generale"]
    return {"cles": cles, "heures_imprimees": heures_imprimees,
            "heures_retrouvees": heures_retrouvees, "raison": raison}


def mois_du_contrat_en_cours(lus: dict[int, dict], bascule: int, matricule: str) -> list[int]:
    """Les mois repris du contrat en cours au mois de bascule, pour ce matricule.

    Quadra garde le même matricule quand un salarié parti revient (Comitech : CDD
    clos le 31/05, nouveau contrat le 01/09/2026) et imprime son « Entré(e) le » du
    nouveau contrat, mais continue ses cumuls sur l'année. Un mois antérieur à cette
    entrée appartient au contrat précédent.
    """
    presents = [m for m in sorted(lus) if m <= bascule and matricule in lus[m]]
    entree = lus[bascule][matricule].infos.get("entree")
    if not entree:
        return presents
    debut = _date_fr(entree)
    return [m for m in presents if f"{ANNEE:04d}-{m:02d}-31" >= debut]


def _somme_du_contrat(lus: dict[int, dict], mois: list[int], matricule: str) -> dict[str, float]:
    """Les cumuls du seul contrat en cours, additionnés mois par mois.

    Le cumul imprimé couvre l'année, contrat précédent compris : il ne sert pas.
    Chaque bulletin imprime ses valeurs du mois (brut, net imposable, impôt,
    heures de la période, heures sup des lignes, net des heures sup exonérées).
    """
    total = {"brut_total": 0.0, "net_imposable": 0.0, "impot_preleve_a_la_source": 0.0,
             "heures_remunerees": 0.0, "heures_supplementaires_remunerees": 0.0,
             "montant_net_hs_exonerees_cumul": 0.0}
    for m in mois:
        b = lus[m][matricule]
        total["brut_total"] += _brut_du_mois(b)
        total["net_imposable"] += float(b.net.get("net_imposable") or 0.0)
        total["impot_preleve_a_la_source"] += float(b.net.get("pas_montant") or 0.0)
        forfait = heures_reduction_forfait_quadra(b)
        total["heures_remunerees"] += forfait if forfait is not None else float(b.droite.get("heures_periode") or 0.0)
        total["heures_supplementaires_remunerees"] += sum(
            (lg.base or 0.0) * (1 if lg.gain is not None else -1)
            for lg in b.lignes
            if re.search(r"H\.?\s*SUPP|HEURES\s+SUPPL", lg.libelle or "", re.IGNORECASE)
            and (lg.gain is not None or lg.montant_sal is not None)
        )
        total["montant_net_hs_exonerees_cumul"] += float(b.net.get("net_hs_exo") or 0.0)
    return {k: round(v, 2) for k, v in total.items()}


def solde_d_ouverture(lus: dict[int, dict], bascule: int, matricule: str) -> dict:
    presents = [m for m in sorted(lus) if m <= bascule and matricule in lus[m]]
    mois_presents = mois_du_contrat_en_cours(lus, bascule, matricule)
    nouveau_contrat = mois_presents != presents
    # Un contrat qui reprend en cours d'année : les autres calculs ne voient que ses mois.
    lus_du_contrat = (
        {m: {matricule: lus[m][matricule]} for m in mois_presents} if nouveau_contrat else lus
    )
    dernier = lus[bascule][matricule]
    reduction_generale = deduction_hs = hs_brut = plafonds = bruts = 0.0
    for m in mois_presents:
        b = lus[m][matricule]
        reduction_generale += _somme_des_lignes(b, EST_REDUCTION_GENERALE)
        deduction_hs += _somme_des_lignes(b, EST_DEDUCTION_HS)
        hs_brut += _heures_sup_brut(b)
        plafonds += float(b.droite.get("plafond") or 0.0)
        bruts += _brut_du_mois(b)
    if nouveau_contrat:
        imprimes = _somme_du_contrat(lus, mois_presents, matricule)
    else:
        imprimes = {
            "brut_total": float(dernier.droite.get("cumul_bruts") or 0.0),
            "net_imposable": float(dernier.net.get("net_imposable_cumul") or 0.0),
            "impot_preleve_a_la_source": float(dernier.net.get("pas_cumul") or 0.0),
            "heures_remunerees": _heures_de_la_reduction(lus, mois_presents, matricule, dernier),
            "heures_supplementaires_remunerees": float(dernier.droite.get("cumul_hs") or 0.0),
            "montant_net_hs_exonerees_cumul": float(dernier.net.get("net_hs_exo_cumul") or 0.0),
        }
    brut = imprimes["brut_total"]
    net_hs_exo = imprimes["montant_net_hs_exonerees_cumul"]
    tranche_2 = round(max(0.0, brut - plafonds), 2)
    base_cp, debut_cp, fin_cp = base_du_dixieme(lus_du_contrat, ANNEE, bascule, matricule, _brut_du_mois)
    solde = {
        "controle_somme_des_bruts": round(bruts, 2),
        "cumuls": {
            "brut_total": brut,
            "net_imposable": imprimes["net_imposable"],
            "impot_preleve_a_la_source": imprimes["impot_preleve_a_la_source"],
            "heures_remunerees": imprimes["heures_remunerees"],
            "heures_supplementaires_remunerees": imprimes["heures_supplementaires_remunerees"],
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
        "periode": {"annee_en_cours": ANNEE, "dernier_mois_calcule": bascule},
        "reprise": {
            "logiciel_precedent": "Quadra",
            "source": "bulletins PDF lus ligne à ligne",
            "mois_de_bascule": f"{ANNEE:04d}-{bascule:02d}",
            "mois_repris": mois_presents,
            "fait_foi": True,
        },
    }
    if nouveau_contrat:
        # Même règle que MARTINE au premier mois d'un contrat (cumuls_precedents_du_contrat) :
        # la réduction générale, les tranches et le dixième repartent avec le contrat.
        solde["reprise"]["contrat_en_cours_depuis"] = dernier.infos.get("entree")
        solde["reprise"]["cumul_brut_imprime_sur_l_annee"] = float(dernier.droite.get("cumul_bruts") or 0.0)
    # Base de la réduction de Quadra (point de départ, heures de SMIC retenues) : les
    # clés vont dans les cumuls écrits ; le détail reste ici, pour être relu.
    base = base_de_la_reduction(lus_du_contrat, bascule, matricule, solde["cumuls"])
    solde["cumuls"].update(base["cles"])
    solde["base_de_la_reduction"] = base
    return solde


def solde_du_contrat_qui_continue(soldes: list[tuple[str, dict]]) -> dict:
    """Le solde d'ouverture d'une fiche qui a eu plusieurs matricules Quadra :
    celui du dernier contrat, `soldes` étant des paires (date d'entrée, solde).

    Fin de CDD le 30/08 puis contrat d'apprentissage le 31/08 : Quadra ouvre un
    second matricule dont les cumuls repartent de zéro, et la base n'a qu'une fiche
    par numéro de sécurité sociale. La réduction générale, les tranches et le
    plafond se calculent par contrat : additionner les deux faisait rattraper en
    septembre la réduction de toute l'année du CDD (−810,65 € au lieu d'environ
    −458,67 €, 29/09/2026). Le contrat terminé est clos, comme à une sortie.
    """
    return sorted(soldes, key=lambda x: _date_fr(x[0]))[-1][1]


def _date_fr(texte: Any) -> str:
    """« 31/08/2026 » → « 2026-08-31 », pour trier des dates d'entrée."""
    j, m, a = (str(texte or "01/01/1900").split("/") + ["", "", ""])[:3]
    return f"{a}-{m}-{j}"


# ---------------------------------------------------------------------------
# Programme
# ---------------------------------------------------------------------------


def fiche_hors_du_contrat(fiche: dict, bulletin) -> str | None:
    """Pourquoi la fiche ne porte pas le contrat du bulletin, ou None.

    Fiche sortie avant l'entrée imprimée (retour le 01/09 sur une fiche close au
    31/05) : ses congés se calculeraient sur l'ancien contrat, et ne s'afficheraient
    plus après la reprise.
    """
    entree = bulletin.infos.get("entree")
    fin = str(fiche.get("contract_end_date") or "")[:10]
    if entree and fin and fin < _date_fr(entree):
        return (f"fiche close le {fin[8:10]}/{fin[5:7]}/{fin[:4]}, contrat du bulletin "
                f"depuis le {entree} : rouvrir la fiche (« Nouveau contrat »), puis relancer")
    return None


def verdict_des_conges(quadra: tuple[float, float], apres: tuple[float, float] | None) -> str:
    """Les congés affichés après la reprise contre ceux de Quadra.

    Un solde négatif de Quadra (congés pris par anticipation) est enregistré tel quel,
    mais l'affichage garde son plancher à zéro (`apply_cp_solde_import`) : un 0 affiché
    face à un négatif est juste."""
    if apres is None:
        return "plus de compteur au mois de bascule (sortie)"

    def egal(affiche: float, repris: float) -> bool:
        return abs(affiche - repris) < 0.005 or (repris < 0 and abs(affiche) < 0.005)

    if egal(apres[0], quadra[0]) and egal(apres[1], quadra[1]):
        negatif = quadra[0] < 0 or quadra[1] < 0
        return "= Quadra (négatif enregistré, affiché à 0)" if negatif else "= Quadra"
    return "ÉCART"


def _simuler_les_conges(soldes: dict, bascule: int) -> list[str]:
    """Les congés affichés après la reprise, simulée sans rien écrire, contre Quadra."""
    from scripts.reprise_colorplast_import_litteral import etiquette
    from scripts.reprise_conges_en_memoire import (
        ajustements_en_memoire,
        solde_affiche,
        solde_affiche_apres_reprise,
    )

    ecarts = []
    print(f"\n=== Congés au {bascule:02d}/{ANNEE} (N-1 / N) : Quadra, MARTINE avant, MARTINE après la reprise")
    for v in soldes.values():
        fiche, b = v["fiche"], v["bulletin"]
        cp_n1, cp_n = b.cp.get("Solde", (0.0, 0.0))
        if v.get("conges_non_repris"):
            print(f"  {etiquette(fiche):14s} Quadra {cp_n1:6.2f} / {cp_n:5.2f}   non repris : {v['conges_non_repris']}")
            continue
        with ajustements_en_memoire():
            avant = solde_affiche(fiche["id"], ANNEE, bascule)
            apres = solde_affiche_apres_reprise(COMPANY_ID, fiche["id"], ANNEE, bascule, cp_n1, cp_n)
        verdict = verdict_des_conges((cp_n1, cp_n), apres)
        if verdict == "ÉCART":
            ecarts.append(etiquette(fiche))
        print(f"  {etiquette(fiche):14s} Quadra {cp_n1:6.2f} / {cp_n:5.2f}   avant {avant}   après {apres}   {verdict}")
    return ecarts


def main(appliquer: bool, jusqu_a: int, sans: tuple[str, ...] = (), mois_ecrits: tuple[int, ...] | None = None,
         complements: dict[int, dict[str, Any]] | None = None) -> int:
    """`complements` : {mois: {matricule: Bulletin}} pour des mois absents du PDF mais
    déclarés en DSN (Mont Blanc, mars : une page manquante). Ils entrent dans le solde
    d'ouverture seulement ; aucun bulletin n'est écrit pour eux."""
    from scripts.reprise_colorplast_import_litteral import etiquette

    admin = get_supabase_admin_client()
    fiches = admin.table("employees").select(
        "id, last_name, first_name, nir, statut, job_title, employee_folder_name, employment_status, "
        "is_forfait_jour, contract_end_date"
    ).eq("company_id", COMPANY_ID).execute().data
    par_nir = {_nir(f["nir"]): f for f in fiches if f.get("nir")}
    societe = admin.table("companies").select("company_name, siret").eq("id", COMPANY_ID).execute().data[0]

    mois_repris = tuple(range(1, jusqu_a + 1))
    # Les mois dont les bulletins sont (ré)écrits ; tous ceux repris par défaut. Le solde
    # d'ouverture, lui, se lit toujours sur tous les mois repris.
    mois_ecrits = tuple(mois_ecrits or mois_repris)
    if not set(mois_ecrits) <= set(mois_repris):
        raise SystemExit(f"Mois hors reprise : {sorted(set(mois_ecrits) - set(mois_repris))}")
    lus = {m: lire_bulletins(ANNEE, m, SOCIETE) for m in mois_repris}
    lus_ouverture = {m: {**(complements or {}).get(m, {}), **lus[m]} for m in mois_repris}
    for m, ajoutes in sorted((complements or {}).items()):
        absents = set(ajoutes) - set(lus.get(m, {}))
        if absents:
            print(f"  {m:02d} : {len(absents)} bulletin(s) absent(s) du PDF, mois complété(s) depuis la DSN "
                  "(ouverture seulement)")
    anomalies: list[str] = []
    a_ecrire: list[tuple[int, str, Any, dict]] = []

    for mois in mois_ecrits:
        print(f"\n=== {mois:02d}/{ANNEE} — {len(lus[mois])} bulletins")
        for mat, b in sorted(lus[mois].items()):
            fiche = par_nir.get(_nir(b.infos.get("nir")))
            qui = etiquette(fiche, b.infos.get("entree"))
            if mat in sans:
                print(f"  {qui:14s} écarté (--sans)")
                continue
            if not fiche:
                anomalies.append(f"{mois:02d} {qui} : aucune fiche pour ce numéro de sécurité sociale")
                print(f"  {qui:14s} !! aucune fiche (NIR)")
                continue
            donnees = donnees_du_bulletin(b, ANNEE, mois, fiche, societe)
            ecart_brut = lignes_du_brut(b)[1]["ecart_brut"]
            ecart_net = equilibre(b, donnees["structure_cotisations"], donnees["primes_non_soumises"],
                                  donnees["retenues_sur_net"])
            sans_effet = [r for r in donnees["retenues_sur_net"] if r.get("sans_effet_sur_le_net")]
            if sans_effet:
                print(f"  {qui:14s} .. retenue imprimée sans effet sur le net de Quadra : "
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
                anomalies.append(f"{mois:02d} {qui} : {etat}")
            cp = b.cp.get("Solde", (0.0, 0.0))
            cpt = donnees["pied_de_page"].get("compteurs_quadra") or {}
            print(f"  {qui:14s} brut {donnees['salaire_brut']:9.2f} net {donnees['net_a_payer']:9.2f} "
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
            print(f"  {mois:02d} {etiquette(principal[3]['fiche'])} : bulletin gardé, joint aux pages "
                  + ", ".join(f"de l'autre contrat ({a['brut']:.2f} brut, entrée {a['entree']})" for a in autres))
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
        solde = solde_d_ouverture(lus_ouverture, bascule, mat)
        ecart = round(solde["controle_somme_des_bruts"] - solde["cumuls"]["brut_total"], 2)
        if abs(ecart) > TOLERANCE:
            anomalies.append(f"{etiquette(fiche)} : somme des bruts {solde['controle_somme_des_bruts']:.2f} "
                             f"contre cumul imprimé {solde['cumuls']['brut_total']:.2f}")
        par_fiche.setdefault(fiche["id"], []).append((mat, b, solde, fiche))
    soldes: dict[str, dict] = {}
    for lignes in par_fiche.values():
        # Cumuls, congés et compteurs sont ceux du contrat qui continue : le dernier entré.
        lignes.sort(key=lambda x: _date_fr(x[1].infos.get("entree")))
        mat, b, _, fiche = lignes[-1]
        solde = solde_du_contrat_qui_continue([(x[1].infos.get("entree"), x[2]) for x in lignes])
        qui = etiquette(fiche)
        if len(lignes) > 1:
            print(f"  {qui:14s} contrat en cours depuis le {b.infos.get('entree')} : ses cumuls seuls "
                  f"({len(lignes) - 1} contrat(s) clos sous un autre matricule)")
        if solde["reprise"].get("contrat_en_cours_depuis"):
            print(f"  {qui:14s} revenu le {solde['reprise']['contrat_en_cours_depuis']} : cumuls du contrat en cours "
                  f"(Quadra imprime {solde['reprise']['cumul_brut_imprime_sur_l_annee']:.2f} de brut sur l'année)")
        soldes[mat] = {"fiche": fiche, "solde": solde, "bulletin": b,
                       "conges_non_repris": fiche_hors_du_contrat(fiche, b)}
        c = solde["cumuls"]
        print(f"  {qui:14s} brut {c['brut_total']:10.2f} heures {c['heures_remunerees']:8.2f} "
              f"HS {c['heures_supplementaires_remunerees']:7.2f} net imp. {c['net_imposable']:10.2f} "
              f"réd. gén. {c['reduction_generale_patronale']:9.2f} "
              f"(écart {round(solde['controle_somme_des_bruts'] - c['brut_total'], 2):+.2f})")

    presents = {_nir(v["fiche"]["nir"]) for v in soldes.values()}
    actifs_sans_bulletin = [f"{etiquette(f)} ({f['employment_status']})" for f in fiches
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
        ecarts = _simuler_les_conges(soldes, bascule)
        if ecarts:
            print("!! Congés qui ne retomberaient pas sur Quadra : " + ", ".join(ecarts))
        print(f"\nSimulation : {len(a_ecrire)} bulletins, {len(soldes)} soldes d'ouverture. "
              "Relancer avec --apply pour écrire.")
        return 1 if ecarts else 0

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
        if v.get("conges_non_repris"):
            print(f"  {etiquette(fiche):14s} solde d'ouverture écrit ; congés NON repris : {v['conges_non_repris']}")
            continue
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
        print(f"  {etiquette(fiche):14s} solde d'ouverture et congés écrits"
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
    # --mois 9 : n'écrit que les bulletins de ces mois (les autres sont déjà repris) ;
    # le solde d'ouverture se lit toujours sur tous les mois jusqu'à la bascule.
    mois_ecrits = None
    if "--mois" in sys.argv:
        mois_ecrits = tuple(int(m) for m in sys.argv[sys.argv.index("--mois") + 1].split(","))
    raise SystemExit(main("--apply" in sys.argv, jusqu_a, sans, mois_ecrits))
