"""Reprise Mont Blanc Composite : les bulletins Quadra de 2026 copiés, l'ouverture posée.

Même doctrine et même programme que Comitech (`scripts/reprise_comitech.py`) : le passé
appartient à Quadra, il se copie ligne à ligne ; au mois de bascule, un solde d'ouverture
par salarié (cumuls, base de la réduction générale de Quadra, congés, repos des cadres),
puis la bascule de la société. Ce qui change pour Mont Blanc :

- plus de 50 salariés : Tdelta de la réduction 2026 à 0,3821 (coefficient implicite de
  0,40210 dans ses bulletins, `verification_rgdu/chemins.py`), pour retrouver les heures
  de SMIC que Quadra a retenues (`heures_hors_reduction_generale`, R3) ;
- un bulletin absent du PDF mais déclaré en DSN (mars 2026, un salarié entré le 02/03) :
  le mois entre dans l'ouverture depuis la DSN (brut, réduction 018 + 106, plafond au
  prorata), sans bulletin écrit (`complements_depuis_la_dsn`) ;
- l'ancienneté : Quadra imprime sa date d'ancienneté (« Ancienneté : 04/06/1986 »), qui
  paie la prime d'ancienneté ; la fiche porte dans `prior_service_months` l'ancienneté
  déjà écoulée, comptée deux fois par le moteur. Le plan pose la date de Quadra en
  `seniority_reference_date` et remet la reprise en mois à zéro (`plan_d_anciennete`).

Simulation par défaut. `--apply` écrit (bulletins, ouvertures, congés, bascule, puis
ancienneté) : à lancer par `~/dev/eywai-filet/reprise-mont-blanc/appliquer.sh`, qui
sauvegarde avant.

Usage (depuis backend/, `MARTINE_DATA` vers le data/ du dépôt principal) :
    python -m scripts.reprise_mont_blanc                  # simulation, bascule au 31/07
    python -m scripts.reprise_mont_blanc --bascule 9      # quand août et septembre seront là
    python -m scripts.reprise_mont_blanc --apply          # écrit
"""

from __future__ import annotations

import calendar
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SOCIETE = "mbc"
COMPANY_ID = "b541df31-e964-485e-ac36-cf580633fd1d"
ANNEE = 2026
#: 50 salariés et plus (R-F3, chemins.py) : Tdelta 0,3821, plafond 0,4021.
TDELTA = 0.3821
#: Plafond mensuel de la sécurité sociale 2026 (imprimé « Plafond Sécu : 4005.00 »).
PSS_MENSUEL = 4005.0
#: Dernier mois dont les bulletins Quadra sont arrivés (data/mbc/bulletins/2026-07).
BASCULE_PAR_DEFAUT = 7


def _date_fr(texte: Any) -> date | None:
    try:
        j, m, a = str(texte).split("/")
        return date(int(a), int(m), int(j))
    except (TypeError, ValueError):
        return None


def plafond_au_prorata(mois: int, entree: date | None, sortie: date | None = None) -> float:
    """Plafond du mois au prorata des jours calendaires de présence (R242-2 CSS)."""
    jours = calendar.monthrange(ANNEE, mois)[1]
    debut = max(entree, date(ANNEE, mois, 1)) if entree else date(ANNEE, mois, 1)
    fin = min(sortie, date(ANNEE, mois, jours)) if sortie else date(ANNEE, mois, jours)
    presents = max(0, (fin - debut).days + 1)
    return round(PSS_MENSUEL * presents / jours, 2)


def bulletin_depuis_la_dsn(matricule: str, mois: int, base, entree: date | None):
    """Un bulletin réduit à ce que l'ouverture lit : brut, réduction, plafond.

    `base` : la base 03 de la DSN du mois (`dsn_quadra.BaseReduction`) ; la réduction
    imprimée par Quadra est la somme des codes 018 et 106 (négative)."""
    from scripts.backtest.colorplast_lignes_quadra import Bulletin, Ligne

    b = Bulletin(matricule=matricule)
    b.lignes = [
        Ligne(None, "SALAIRE BRUT", gain=round(float(base.assiette or 0.0), 2)),
        Ligne(None, "EXO., ECRET. ET ALLEG. COTIS", montant_pat=-base.reduction,
              section="Q802 EXO., ECRET. ET ALLEG. COTIS"),
    ]
    b.droite = {"plafond": plafond_au_prorata(mois, entree)}
    b.infos = {"source": f"DSN {ANNEE:04d}-{mois:02d}"}
    b.pages = []
    return b


def complements_depuis_la_dsn(lus: dict[int, dict], bascule: int, bases_par_mois: dict[int, list]) -> dict:
    """{mois: {matricule: Bulletin}} : les mois où un salarié présent au mois de bascule est
    déclaré en DSN sans bulletin dans le PDF. Rapprochement par NIR (13 caractères)."""
    sortie: dict[int, dict] = {}
    presents = {str(b.infos.get("nir") or "")[:13]: (mat, b) for mat, b in lus.get(bascule, {}).items()}
    for mois, bases in sorted(bases_par_mois.items()):
        if mois > bascule:
            continue
        dans_le_pdf = {str(b.infos.get("nir") or "")[:13] for b in lus.get(mois, {}).values()}
        for base in bases:
            if base.debut.month != mois or base.nir in dans_le_pdf or base.nir not in presents:
                continue
            mat, dernier = presents[base.nir]
            entree = _date_fr(dernier.infos.get("entree"))
            if entree and entree > date(ANNEE, mois, calendar.monthrange(ANNEE, mois)[1]):
                continue
            sortie.setdefault(mois, {})[mat] = bulletin_depuis_la_dsn(mat, mois, base, entree)
    return sortie


def anciennete_de_quadra(bulletins: list, fin_de_bascule: date) -> date | None:
    """La date d'ancienneté du bulletin le plus récent qui n'est pas dans le futur.

    `bulletins` du plus ancien au plus récent. Quadra a imprimé une fois l'année de la
    date d'entrée à la place de l'année d'entrée (« 21/08/2026 » au bulletin de juillet
    2026, « 21/08/2023 » les mois d'avant) : une ancienneté postérieure au mois de bascule
    est une faute de frappe, la précédente fait foi."""
    for b in reversed(bulletins):
        d = _date_fr(b.infos.get("anciennete"))
        if d is not None and d <= fin_de_bascule:
            return d
    return None


def plan_d_anciennete(fiche: dict, bulletin, anciennete: date | None = None) -> dict | None:
    """Ce qu'il faut écrire sur la fiche pour que l'ancienneté soit celle de Quadra, ou None.

    Cible : `seniority_reference_date` = date d'ancienneté de Quadra quand elle diffère de
    l'embauche de la fiche (sinon aucune), `prior_service_months` = 0 (la date porte déjà la
    reprise ; la garder en plus la compterait deux fois, cf. prior-service-months).
    `anciennete` : la date retenue (`anciennete_de_quadra`), sinon celle du bulletin."""
    anciennete = anciennete or _date_fr(bulletin.infos.get("anciennete"))
    embauche = str(fiche.get("hire_date") or "")[:10]
    if anciennete is None:
        return None
    cible_ref = anciennete.isoformat() if anciennete.isoformat() != embauche else None
    actuel_ref = str(fiche.get("seniority_reference_date") or "")[:10] or None
    actuel_prior = int(fiche.get("prior_service_months") or 0)
    if actuel_ref == cible_ref and actuel_prior == 0:
        return None
    return {
        "seniority_reference_date": cible_ref,
        "prior_service_months": 0,
        "avant": {"seniority_reference_date": actuel_ref, "prior_service_months": actuel_prior},
        "quadra": {"anciennete": bulletin.infos.get("anciennete"), "entree": bulletin.infos.get("entree")},
        "embauche_fiche": str(fiche.get("hire_date") or "")[:10],
    }


def _bases_dsn(bascule: int) -> dict[int, list]:
    from scripts.verification_rgdu.dsn_quadra import dsn_du_mois

    return {m: dsn_du_mois(SOCIETE, m) for m in range(1, bascule + 1)}


def anciennete(appliquer: bool, bascule: int) -> int:
    """Le plan d'ancienneté au mois de bascule ; écrit avec `appliquer`."""
    from app.core.database import get_supabase_admin_client
    from scripts.backtest.colorplast_lignes_quadra import lire_bulletins
    from scripts.reprise_colorplast_import_litteral import etiquette
    from scripts.reprise_comitech import _nir

    admin = get_supabase_admin_client()
    fiches = admin.table("employees").select(
        "id, first_name, last_name, nir, hire_date, seniority_reference_date, prior_service_months"
    ).eq("company_id", COMPANY_ID).execute().data
    par_nir = {_nir(f["nir"]): f for f in fiches if f.get("nir")}
    plans = []
    print(f"\n=== Ancienneté au {bascule:02d}/{ANNEE} (date de Quadra, reprise en mois remise à zéro)")
    lus = [lire_bulletins(ANNEE, m, SOCIETE) for m in range(1, bascule + 1)]
    fin = date(ANNEE, bascule, calendar.monthrange(ANNEE, bascule)[1])
    for _mat, b in sorted(lus[-1].items()):
        fiche = par_nir.get(_nir(b.infos.get("nir")))
        if not fiche:
            continue
        historique = [m[_mat] for m in lus if _mat in m]
        plan = plan_d_anciennete(fiche, b, anciennete_de_quadra(historique, fin))
        if plan is None:
            continue
        ecart_embauche = plan["embauche_fiche"] != (
            _date_fr(b.infos.get("entree")).isoformat() if _date_fr(b.infos.get("entree")) else "")
        print(f"  {etiquette(fiche):14s} réf. {plan['avant']['seniority_reference_date']} → "
              f"{plan['seniority_reference_date']} ; reprise {plan['avant']['prior_service_months']} → 0 mois"
              + (f" ; embauche fiche {plan['embauche_fiche']} ≠ entrée Quadra {b.infos.get('entree')}"
                 if ecart_embauche else ""))
        plans.append((fiche, plan))
    print(f"{len(plans)} fiche(s) à mettre à l'ancienneté de Quadra.")
    if appliquer:
        for fiche, plan in plans:
            admin.table("employees").update({
                "seniority_reference_date": plan["seniority_reference_date"],
                "prior_service_months": 0,
            }).eq("id", fiche["id"]).eq("company_id", COMPANY_ID).execute()
        print(f"{len(plans)} fiche(s) écrites.")
    return 0


def main(appliquer: bool, bascule: int, sans: tuple[str, ...] = (), mois_ecrits: tuple[int, ...] | None = None,
         anciennete_seule: bool = False) -> int:
    import scripts.reprise_comitech as rc
    from scripts.backtest.colorplast_lignes_quadra import lire_bulletins

    rc.regler_pour(SOCIETE, COMPANY_ID, TDELTA)
    if not anciennete_seule:
        lus = {m: lire_bulletins(ANNEE, m, SOCIETE) for m in range(1, bascule + 1)}
        complements = complements_depuis_la_dsn(lus, bascule, _bases_dsn(min(bascule, 6)))
        code = rc.main(appliquer, bascule, sans, mois_ecrits, complements)
        if code:
            return code
    return anciennete(appliquer, bascule)


if __name__ == "__main__":
    bascule = BASCULE_PAR_DEFAUT
    if "--bascule" in sys.argv:
        bascule = int(sys.argv[sys.argv.index("--bascule") + 1])
    sans = ()
    if "--sans" in sys.argv:
        sans = tuple(m.strip().upper() for m in sys.argv[sys.argv.index("--sans") + 1].split(",") if m.strip())
    mois_ecrits = None
    if "--mois" in sys.argv:
        mois_ecrits = tuple(int(m) for m in sys.argv[sys.argv.index("--mois") + 1].split(","))
    raise SystemExit(main("--apply" in sys.argv, bascule, sans, mois_ecrits, "--anciennete-seule" in sys.argv))
