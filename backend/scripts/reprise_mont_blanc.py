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
  `seniority_reference_date` et remet la reprise en mois à zéro (`plan_d_anciennete`) ;
- le salaire : la fiche reprend le salaire de base que Quadra paie au mois de bascule (SMIC
  passé à 12,31 €, heures structurelles hors du salaire), par un changement daté
  (`plan_de_salaire`).

`--anciennete-seule` : seulement l'étape des fiches (ancienneté et salaire), pour la relecture.

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

    Cible : `seniority_reference_date` = date d'ancienneté de Quadra, toujours écrite, même
    égale à l'embauche : sans elle le moteur reprend la date « d'ancienneté » de l'ancien
    import DSN, lue sur une suspension (prime d'ancienneté perdue chez quatre salariés en
    juillet) ; `prior_service_months` = 0 (la date porte déjà la reprise ; la garder en plus
    la compterait deux fois, cf. prior-service-months).
    `anciennete` : la date retenue (`anciennete_de_quadra`), sinon celle du bulletin."""
    anciennete = anciennete or _date_fr(bulletin.infos.get("anciennete"))
    if anciennete is None:
        return None
    cible_ref = anciennete.isoformat()
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


def taux_de_chomage_de_quadra(bulletins) -> float | None:
    """Le taux patronal d'assurance chômage que Quadra applique au plus grand nombre (en %).

    Taux modulé (bonus-malus) notifié à la société : 2,95 % chez Mont Blanc en juillet 2026, les
    apprentis restant au taux de droit commun (4 %). Réglage de société `taux_assurance_chomage`,
    comme chez Comitech."""
    from collections import Counter

    taux = Counter()
    for b in bulletins:
        for lg in b.lignes:
            lib = " ".join(str(lg.libelle or "").split()).upper()
            if lib.startswith(("CHÔMAGE", "CHOMAGE")) and lg.base and lg.montant_pat and lg.base > 0:
                taux[round(lg.montant_pat / lg.base * 100, 2)] += 1
    return taux.most_common(1)[0][0] if taux else None


def plan_prime_anciennete(fiche: dict, bulletin) -> bool:
    """Vrai si la fiche dit la prime d'ancienneté fondue dans le salaire de base alors que Quadra
    la paie sur une ligne à part (« Prime ancienneté ») : le réglage est à retirer."""
    spec = ((fiche.get("specificites_paie") or {}).get("prime_anciennete") or {})
    incluse = isinstance(spec, dict) and bool(spec.get("incluse_dans_salaire_base"))
    a_part = any("ANCIENNET" in " ".join(str(lg.libelle or "").split()).upper() and lg.gain
                 for lg in bulletin.lignes)
    return incluse and a_part


def _maj(libelle) -> str:
    return " ".join(str(libelle or "").split()).upper()


def _montants_quadra_de_mutuelle(bulletin) -> list[tuple[float, float, str]]:
    """(salarial, patronal, libellé) de chaque ligne de mutuelle du bulletin : obligatoire
    (« EMU… », dans les cotisations) et facultative (« SMU… », après le net, salariale)."""
    lignes = []
    for lg in bulletin.lignes:
        code = lg.code or ""
        if code.startswith("EMU"):
            lignes.append((round(lg.montant_sal or 0.0, 2), round(lg.montant_pat or 0.0, 2), lg.libelle))
        elif code.startswith("SMU"):
            montant = lg.montant_sal if lg.montant_sal is not None else -(lg.gain or 0.0)
            lignes.append((round(montant, 2), 0.0, lg.libelle))
    return lignes


def _formule_de_quadra(sal: float, pat: float, libelle: str, types: list[dict]) -> dict | None:
    """La formule de la société aux mêmes montants ; à égalité, celle dont le libellé partage
    un mot clé avec Quadra (isolé, enfant, conjoint), puis la plus utilisée."""
    egales = [t for t in types if abs(float(t.get("montant_salarial") or 0) - sal) < 0.005
              and abs(float(t.get("montant_patronal") or 0) - pat) < 0.005]
    mots = {m for m in ("ISOL", "ENFANT", "CONJOINT") if m in _maj(libelle)}
    egales.sort(key=lambda t: (-len(mots & {m for m in ("ISOL", "ENFANT", "CONJOINT") if m in _maj(t.get("libelle"))}),
                               -int(t.get("n") or 0), str(t.get("libelle"))))
    return egales[0] if egales else None


def plan_de_mutuelle(fiche: dict, bulletin, types: list[dict]) -> dict | None:
    """Les formules de mutuelle de la fiche telles que Quadra les prélève au mois de bascule, ou None.

    Le moteur lit `specificites_paie.mutuelle` (adhésion, formules). Une ligne de Quadra sans
    formule aux mêmes montants dans la société n'est pas devinée : `introuvables`."""
    quadra = _montants_quadra_de_mutuelle(bulletin)
    mutuelle = ((fiche.get("specificites_paie") or {}).get("mutuelle") or {})
    actuels = [str(i) for i in (mutuelle.get("mutuelle_type_ids") or []) if i] if mutuelle.get("adhesion") else []
    par_id = {str(t["id"]): t for t in types}
    montants = sorted((round(float(par_id[i].get("montant_salarial") or 0), 2),
                       round(float(par_id[i].get("montant_patronal") or 0), 2)) for i in actuels if i in par_id)
    if sorted((sal, pat) for sal, pat, _ in quadra) == montants and len(montants) == len(actuels):
        return None
    cibles, introuvables = [], []
    for sal, pat, libelle in quadra:
        t = _formule_de_quadra(sal, pat, libelle, types)
        (cibles.append(str(t["id"])) if t else introuvables.append(f"{libelle} {sal:.2f} / {pat:.2f}"))
    return {"adhesion": bool(cibles), "mutuelle_type_ids": cibles, "introuvables": introuvables,
            "avant": {"adhesion": bool(mutuelle.get("adhesion")), "mutuelle_type_ids": actuels},
            "quadra": [f"{lib} {sal:.2f} / {pat:.2f}" for sal, pat, lib in quadra]}


def plan_de_prevoyance(fiche: dict, bulletin) -> dict | None:
    """La prévoyance de la fiche aux taux que Quadra prélève (lignes « EPR… », tranche A), ou None.

    Posée seulement quand Quadra prélève une prévoyance que la fiche n'applique pas ou à
    d'autres taux ; les lignes reprennent la forme de l'import DSN (`prevoyance_dsn`)."""
    lignes, quadra = [], []
    for lg in bulletin.lignes:
        if (lg.code or "").startswith("EPR") and lg.base:
            quadra.append((lg.base, round(lg.montant_sal or 0.0, 2), round(lg.montant_pat or 0.0, 2)))
            lignes.append({
                "id": "prevoyance_dsn" if not lignes else f"prevoyance_dsn_{len(lignes) + 1}",
                "base": "brut_plafonne",
                "libelle": " ".join(lg.libelle.split()),
                # Le taux salarial imprimé par Quadra ; le patronal, montant ÷ base à cinq
                # décimales (0,50 %, 1,58 %, 0,904 %) : au-delà, c'est l'arrondi au centime.
                "salarial": round((lg.taux / 100) if lg.taux and lg.montant_sal else
                                  (lg.montant_sal or 0.0) / lg.base, 5),
                "patronal": round((lg.montant_pat or 0.0) / lg.base, 5),
                "forfait_social": 0.08,
            })
    if not lignes:
        return None
    prev = ((fiche.get("specificites_paie") or {}).get("prevoyance") or {})
    actuelles = prev.get("lignes_specifiques") or []
    # Mêmes taux : ceux de la fiche redonnent, sur les bases de Quadra, ses montants au centime.
    memes_taux = len(actuelles) == len(quadra) and all(
        abs(round(base * float(l.get("salarial") or 0), 2) - sal) < 0.005
        and abs(round(base * float(l.get("patronal") or 0), 2) - pat) < 0.005
        for l, (base, sal, pat) in zip(actuelles, quadra))
    if prev.get("adhesion") and (memes_taux or not actuelles):
        return None
    return {"adhesion": True, "lignes_specifiques": lignes,
            "avant": {"adhesion": bool(prev.get("adhesion")),
                      "taux": [(l.get("salarial"), l.get("patronal")) for l in actuelles]}}


def sorties_de_quadra(mois: list[dict], fin_de_bascule: date) -> list[tuple[str, object, date]]:
    """(matricule, dernier bulletin, date de sortie) des sorties imprimées par Quadra
    (« Sorti(e) le ») jusqu'au mois de bascule ; `mois` : les bulletins par mois, dans l'ordre."""
    vues: dict[str, tuple] = {}
    for bulletins in mois:
        for mat, b in bulletins.items():
            d = _date_fr(b.infos.get("sortie"))
            if d is not None and d <= fin_de_bascule:
                vues[mat] = (mat, b, d)
    return sorted(vues.values(), key=lambda x: x[0])


def motif_de_sortie(bulletin, motif_dsn: str | None) -> tuple[str, str]:
    """(type de départ, d'où il vient). La DSN du mois de sortie d'abord (S21.G00.62.002) ;
    sinon ce que le bulletin prouve : indemnité de précarité (fin de CDD), de licenciement, de
    rupture conventionnelle ; sinon « autre motif », Quadra n'imprimant pas le motif."""
    from app.modules.dsn_import.domain.dsn_absence_exit_mapping import map_exit_motif

    if motif_dsn:
        return map_exit_motif(motif_dsn), f"motif DSN {motif_dsn}"
    libelles = [_maj(lg.libelle) for lg in bulletin.lignes if lg.gain]
    if any("PRÉCARITÉ" in l or "PRECARITE" in l for l in libelles):
        return "fin_cdd", "indemnité de précarité au bulletin de Quadra"
    if any("LICENCIEMENT" in l for l in libelles):
        return "licenciement", "indemnité de licenciement au bulletin de Quadra"
    if any("RUPTURE" in l and "CONV" in l for l in libelles):
        return "rupture_conventionnelle", "indemnité de rupture conventionnelle au bulletin de Quadra"
    return "autre_motif", "motif non imprimé par Quadra ; à reprendre de la DSN du mois de sortie"


def motif_dsn_de_sortie(nir: str, mois: int) -> str | None:
    """Le motif de rupture (S21.G00.62.002) déclaré pour ce NIR dans la DSN du mois, s'il y est."""
    import re

    from scripts.verification_rgdu.chemins import DATA

    chemin = DATA / SOCIETE / "dsn" / f"{ANNEE:04d}-{mois:02d}.dsn"
    if not chemin.exists():
        return None
    courant, motif = None, None
    for ligne in chemin.read_bytes().decode("latin-1").splitlines():
        m = re.match(r"(S21\.G00\.\d\d\.\d{3}),'(.*)'", ligne.strip())
        if not m:
            continue
        rub, val = m.groups()
        if rub == "S21.G00.30.001":
            courant = val[:13]
        elif rub == "S21.G00.62.002" and courant == str(nir)[:13]:
            motif = val
    return motif


#: Heures mensuelles d'un temps plein (35 h × 52 / 12), base du « SALAIRE DE BASE » de Quadra.
HEURES_TEMPS_PLEIN = 151.67


def plan_de_salaire(fiche: dict, bulletin) -> dict | None:
    """Le salaire de base de la fiche tel que Quadra le paie au mois de bascule, ou None.

    Quadra imprime « SALAIRE DE BASE heures × taux » (ou le seul montant, au forfait jours) et,
    au-delà de 35 h, les heures structurelles à part (« H. supp majorées à 25 % »). La fiche doit
    porter ce salaire du mois complet, et le réglage « salaire hors heures structurelles » quand
    l'horaire dépasse 35 h (sinon le moteur prend le salaire pour l'horaire entier). Un mois
    incomplet (entrée, sortie, temps partiel en cours de mois) ne dit pas le salaire du mois
    complet : aucun plan."""
    ligne = next((lg for lg in bulletin.lignes
                  if " ".join(str(lg.libelle or "").split()).upper().startswith("SALAIRE DE BASE") and lg.gain), None)
    if ligne is None:
        return None
    duree = float(fiche.get("duree_hebdomadaire") or 35.0)
    heures_contrat = round(min(duree, 35.0) * 52 / 12, 2)
    if ligne.base is not None and abs(ligne.base - heures_contrat) > 0.02 and abs(ligne.base - HEURES_TEMPS_PLEIN) > 0.02:
        return None
    cible = round(float(ligne.gain), 2)
    hors_hs = True if duree > 35.0 and ligne.base is not None else None
    actuel = fiche.get("salaire_de_base") or {}
    actuel_hors = bool((fiche.get("specificites_paie") or {}).get("salaire_hors_hs_structurelles"))
    if abs(float(actuel.get("valeur") or 0.0) - cible) < 0.005 and (hors_hs is None or actuel_hors):
        return None
    return {
        "salaire_de_base": {"valeur": cible, "type": actuel.get("type") or "mensuel"},
        "salaire_hors_hs_structurelles": hors_hs,
        "avant": {"salaire_de_base": actuel, "salaire_hors_hs_structurelles": actuel_hors},
        "quadra": {"base": ligne.base, "taux": ligne.taux, "gain": ligne.gain},
    }


def _bases_dsn(bascule: int) -> dict[int, list]:
    from scripts.verification_rgdu.dsn_quadra import dsn_du_mois

    return {m: dsn_du_mois(SOCIETE, m) for m in range(1, bascule + 1)}


#: Compte qui signe les écritures de reprise (Alexandre), comme scripts/dsn_arrets_a_reclasser.py.
AUTEUR = "8300cc71-87a7-4d3f-8aef-8393de0ebc4f"


def fiches(appliquer: bool, bascule: int) -> int:
    """Les fiches au mois de bascule : ancienneté de Quadra, salaire de base de Quadra.

    Écrit avec `appliquer` : la date d'ancienneté et la reprise en mois sur la fiche ; le
    salaire par un changement daté du 1er du mois de bascule (`apply_salary_update`, qui
    met la fiche à jour), et le réglage « salaire hors heures structurelles »."""
    from app.core.database import get_supabase_admin_client
    from scripts.backtest.colorplast_lignes_quadra import lire_bulletins
    from scripts.reprise_colorplast_import_litteral import etiquette
    from scripts.reprise_comitech import _nir

    admin = get_supabase_admin_client()
    lignes = admin.table("employees").select(
        "id, first_name, last_name, nir, hire_date, seniority_reference_date, prior_service_months, "
        "salaire_de_base, duree_hebdomadaire, specificites_paie, employment_status, contract_end_date"
    ).eq("company_id", COMPANY_ID).execute().data
    types = admin.table("company_mutuelle_types").select(
        "id, libelle, montant_salarial, montant_patronal").eq("company_id", COMPANY_ID).eq("is_active", True).execute().data
    usages = admin.table("employee_mutuelle_types").select("mutuelle_type_id").in_(
        "mutuelle_type_id", [t["id"] for t in types] or ["-"]).execute().data
    for t in types:
        t["n"] = sum(1 for u in usages if u["mutuelle_type_id"] == t["id"])
    par_nir = {_nir(f["nir"]): f for f in lignes if f.get("nir")}
    plans, salaires, primes, mutuelles, prevoyances = [], [], [], [], []
    print(f"\n=== Ancienneté au {bascule:02d}/{ANNEE} (date de Quadra, reprise en mois remise à zéro)")
    lus = [lire_bulletins(ANNEE, m, SOCIETE) for m in range(1, bascule + 1)]
    fin = date(ANNEE, bascule, calendar.monthrange(ANNEE, bascule)[1])
    for _mat, b in sorted(lus[-1].items()):
        fiche = par_nir.get(_nir(b.infos.get("nir")))
        if not fiche:
            continue
        historique = [m[_mat] for m in lus if _mat in m]
        plan = plan_d_anciennete(fiche, b, anciennete_de_quadra(historique, fin))
        salaire = plan_de_salaire(fiche, b)
        if salaire is not None:
            salaires.append((fiche, salaire))
        if plan_prime_anciennete(fiche, b):
            primes.append(fiche)
        # Mutuelle et prévoyance : seulement pour qui reste payé après la bascule.
        fin_contrat = str(fiche.get("contract_end_date") or "")[:10]
        encore_la = not b.infos.get("sortie") and not (fin_contrat and fin_contrat <= fin.isoformat())
        if encore_la:
            mut = plan_de_mutuelle(fiche, b, types)
            if mut is not None:
                mutuelles.append((fiche, mut))
            prev = plan_de_prevoyance(fiche, b)
            if prev is not None:
                prevoyances.append((fiche, prev))
        if plan is None:
            continue
        entree = _date_fr(b.infos.get("entree"))
        ecart_embauche = plan["embauche_fiche"] != (entree.isoformat() if entree else "")
        print(f"  {etiquette(fiche):14s} réf. {plan['avant']['seniority_reference_date']} → "
              f"{plan['seniority_reference_date']} ; reprise {plan['avant']['prior_service_months']} → 0 mois"
              + (f" ; embauche fiche {plan['embauche_fiche']} ≠ entrée Quadra {b.infos.get('entree')}"
                 if ecart_embauche else ""))
        plans.append((fiche, plan))
    print(f"{len(plans)} fiche(s) à mettre à l'ancienneté de Quadra.")
    print(f"\n=== Salaire de base au {bascule:02d}/{ANNEE} (celui que Quadra paie)")
    for fiche, sal in salaires:
        print(f"  {etiquette(fiche):14s} {sal['avant']['salaire_de_base'].get('valeur')} → {sal['salaire_de_base']['valeur']}"
              f" (Quadra {sal['quadra']['base']} × {sal['quadra']['taux']})"
              + (" ; réglage « hors heures structurelles » posé"
                 if sal["salaire_hors_hs_structurelles"] and not sal["avant"]["salaire_hors_hs_structurelles"] else ""))
    print(f"{len(salaires)} salaire(s) à aligner sur Quadra.")
    for fiche in primes:
        print(f"  {etiquette(fiche):14s} prime d'ancienneté payée à part par Quadra : réglage « incluse dans le salaire » retiré")
    print(f"{len(primes)} prime(s) d'ancienneté à remettre à part.")
    libelles = {str(t["id"]): t["libelle"] for t in types}
    print(f"\n=== Mutuelle et prévoyance au {bascule:02d}/{ANNEE} (celles que Quadra prélève)")
    for fiche, mut in mutuelles:
        print(f"  {etiquette(fiche):14s} mutuelle {[libelles.get(i, i) for i in mut['avant']['mutuelle_type_ids']] or 'aucune'}"
              f" → {[libelles.get(i, i) for i in mut['mutuelle_type_ids']] or 'aucune'} (Quadra : {mut['quadra'] or 'aucune'})"
              + (f" ; !! sans formule aux montants de Quadra : {mut['introuvables']}" if mut["introuvables"] else ""))
    for fiche, prev in prevoyances:
        print(f"  {etiquette(fiche):14s} prévoyance {'adhérente' if prev['avant']['adhesion'] else 'non adhérente'} "
              f"{prev['avant']['taux']} → {[(l['salarial'], l['patronal']) for l in prev['lignes_specifiques']]}")
    print(f"{len(mutuelles)} mutuelle(s) à aligner sur Quadra.")
    print(f"{len(prevoyances)} prévoyance(s) à aligner sur Quadra.")
    societe = admin.table("companies").select("settings").eq("id", COMPANY_ID).execute().data[0]
    reglages = dict(societe.get("settings") or {})
    taux = taux_de_chomage_de_quadra(lus[-1].values())
    a_poser = taux is not None and reglages.get("taux_assurance_chomage") != taux
    print(f"\n=== Société : taux d'assurance chômage {reglages.get('taux_assurance_chomage')} → {taux} "
          f"(Quadra, {bascule:02d}/{ANNEE})")
    print(f"{int(a_poser)} réglage(s) de société à poser.")
    if appliquer and a_poser:
        reglages["taux_assurance_chomage"] = taux
        admin.table("companies").update({"settings": reglages}).eq("id", COMPANY_ID).execute()
        print("taux d'assurance chômage écrit.")
    if appliquer:
        from app.modules.employees.application.commands import apply_salary_update

        for fiche, plan in plans:
            admin.table("employees").update({
                "seniority_reference_date": plan["seniority_reference_date"],
                "prior_service_months": 0,
            }).eq("id", fiche["id"]).eq("company_id", COMPANY_ID).execute()
        for fiche, sal in salaires:
            if abs(float(sal["avant"]["salaire_de_base"].get("valeur") or 0.0) - sal["salaire_de_base"]["valeur"]) >= 0.005:
                apply_salary_update(fiche["id"], COMPANY_ID, sal["avant"]["salaire_de_base"], sal["salaire_de_base"],
                                    f"Reprise Quadra : salaire de base du bulletin de {bascule:02d}/{ANNEE}",
                                    f"{ANNEE:04d}-{bascule:02d}-01", AUTEUR)
        from app.modules.mutuelle_types.infrastructure.repository import MutuelleTypesRepository

        depot = MutuelleTypesRepository(admin)
        for fiche, mut in mutuelles:
            if mut["introuvables"]:
                print(f"  {etiquette(fiche):14s} mutuelle NON écrite : formule introuvable")
                continue
            if len(mut["mutuelle_type_ids"]) == 1:
                depot.replace_employee_mutuelle(fiche["id"], mut["mutuelle_type_ids"][0], AUTEUR)
            else:
                admin.table("employee_mutuelle_types").delete().eq("employee_id", fiche["id"]).execute()
                for i in mut["mutuelle_type_ids"]:
                    admin.table("employee_mutuelle_types").insert(
                        {"employee_id": fiche["id"], "mutuelle_type_id": i, "created_by": AUTEUR}).execute()
        # Une seule écriture de specificites_paie par fiche, avec tous ses changements, relue
        # après la mutuelle (replace_employee_mutuelle l'a mise à jour).
        relues = {f["id"]: f.get("specificites_paie") or {} for f in admin.table("employees").select(
            "id, specificites_paie").eq("company_id", COMPANY_ID).execute().data}
        for fiche in [f for f, _ in salaires] + primes + [f for f, _ in mutuelles] + [f for f, _ in prevoyances]:
            fiche["specificites_paie"] = relues.get(fiche["id"], fiche.get("specificites_paie"))
        specs: dict[str, dict] = {}
        for fiche, mut in mutuelles:
            if len(mut["mutuelle_type_ids"]) != 1 and not mut["introuvables"]:
                spec = specs.setdefault(fiche["id"], dict(fiche.get("specificites_paie") or {}))
                spec["mutuelle"] = {**(spec.get("mutuelle") or {}), "adhesion": bool(mut["mutuelle_type_ids"]),
                                    "mutuelle_type_ids": mut["mutuelle_type_ids"], "lignes_specifiques": []}
        for fiche, prev in prevoyances:
            spec = specs.setdefault(fiche["id"], dict(fiche.get("specificites_paie") or {}))
            spec["prevoyance"] = {**(spec.get("prevoyance") or {}), "adhesion": True,
                                  "lignes_specifiques": prev["lignes_specifiques"]}
        for fiche, sal in salaires:
            if sal["salaire_hors_hs_structurelles"] and not sal["avant"]["salaire_hors_hs_structurelles"]:
                spec = specs.setdefault(fiche["id"], dict(fiche.get("specificites_paie") or {}))
                spec["salaire_hors_hs_structurelles"] = True
        for fiche in primes:
            spec = specs.setdefault(fiche["id"], dict(fiche.get("specificites_paie") or {}))
            spec["prime_anciennete"] = {**(spec.get("prime_anciennete") or {}), "incluse_dans_salaire_base": False}
        for fid, spec in specs.items():
            admin.table("employees").update({"specificites_paie": spec}).eq("id", fid).eq(
                "company_id", COMPANY_ID).execute()
        print(f"{len(plans)} ancienneté(s), {len(salaires)} salaire(s), {len(primes)} prime(s), "
              f"{len(mutuelles)} mutuelle(s) et {len(prevoyances)} prévoyance(s) écrites.")
    return 0


def sorties(appliquer: bool, bascule: int) -> int:
    """Les sorties imprimées par Quadra jusqu'à la bascule, posées sur les fiches encore actives.

    Par le chemin de l'application pour une sortie reprise (`create_reconciliation_exit`) :
    départ créé, clos et archivé (fiche « partie »), sans document de sortie (Quadra les a
    faits). Motif : DSN du mois de sortie si elle est là, sinon ce que prouve le bulletin."""
    from app.core.database import get_supabase_admin_client
    from scripts.backtest.colorplast_lignes_quadra import lire_bulletins
    from scripts.reprise_colorplast_import_litteral import etiquette
    from scripts.reprise_comitech import _nir

    admin = get_supabase_admin_client()
    par_nir = {_nir(f["nir"]): f for f in admin.table("employees").select(
        "id, first_name, last_name, nir, employment_status").eq("company_id", COMPANY_ID).execute().data if f.get("nir")}
    fin = date(ANNEE, bascule, calendar.monthrange(ANNEE, bascule)[1])
    a_poser = []
    print(f"\n=== Sorties imprimées par Quadra jusqu'au {fin:%d/%m/%Y}")
    for _mat, b, jour in sorties_de_quadra([lire_bulletins(ANNEE, m, SOCIETE) for m in range(1, bascule + 1)], fin):
        fiche = par_nir.get(_nir(b.infos.get("nir")))
        if not fiche:
            continue
        statut = str(fiche.get("employment_status") or "actif")
        if statut not in ("actif", "active"):
            print(f"  {etiquette(fiche):14s} sortie le {jour:%d/%m/%Y} : fiche déjà {statut}")
            continue
        type_depart, raison = motif_de_sortie(b, motif_dsn_de_sortie(_nir(b.infos.get("nir")), jour.month))
        print(f"  {etiquette(fiche):14s} sortie le {jour:%d/%m/%Y} à poser : {type_depart} ({raison})")
        a_poser.append((fiche, jour, type_depart, raison))
    print(f"{len(a_poser)} sortie(s) à poser.")
    if appliquer:
        from app.modules.employee_exits.application.commands import create_reconciliation_exit

        for fiche, jour, type_depart, raison in a_poser:
            create_reconciliation_exit(
                fiche["id"], COMPANY_ID, AUTEUR, exit_type=type_depart, last_working_day=jour,
                exit_reason=f"Reprise Quadra : sortie du {jour:%d/%m/%Y} ({raison})",
                fast_archive=True, source="dsn_reconciliation",
            )
            print(f"  {etiquette(fiche):14s} sortie posée et archivée")
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
    code = fiches(appliquer, bascule)
    return code or sorties(appliquer, bascule)


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
