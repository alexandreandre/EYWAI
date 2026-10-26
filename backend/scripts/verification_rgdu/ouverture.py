"""Tâche 10, recalée au 25/10 : ouvertures de la réduction au 30/09, puis octobre à blanc.

Depuis le 25/10, septembre est repris de Quadra chez Colorplast et Comitech : la bascule est au
30/09 et octobre est le premier mois payé par MARTINE.

1. **Ouvertures (R1).** Pour chaque salarié présent en septembre, les cumuls du mois 9 en base
   doivent porter le brut, les heures et la réduction cumulée imprimés par Quadra, et la formule
   appliquée à la base de la réduction (celle que lit le moteur, `base_de_la_reduction`) doit
   redonner la réduction cumulée de Quadra (`ecart_d_ouverture`, à 1 € près, palier compris).
2. **Octobre à blanc.** Chaque salarié en contrat en octobre est calculé en bac à sable : planning
   prévu et saisies d'octobre en base, cumuls de septembre en base. Pour chaque bulletin : refus
   éventuel, réduction du mois décomposée (`decomposer`), SMIC du mois contre la loi
   (`smic_loi_martine`), maintien et paliers, rappels et report du net négatif, net à payer.

Aucune écriture : le piège est posé avant tout import de l'application, puis le filet
(`scripts.filet_paie.Interception`) refuse toute requête qui n'est pas une lecture. Sorties en
initiales dans `data/_rapports/rgdu-2026/octobre.md` et `octobre.json` (hors git).

Usage (depuis backend/, `.env` chargé, `MARTINE_DATA` vers le data/ du dépôt principal) :
    PYTHONPATH=. .venv/bin/python -m scripts.verification_rgdu.ouverture
"""
from __future__ import annotations

import re
import sys
from dataclasses import asdict, dataclass, field

from scripts.verification_rgdu import piege

if __name__ == "__main__":
    piege.poser_le_piege()

from scripts.verification_rgdu.oracle import (  # noqa: E402
    Parametres,
    reduction_cumulee,
    smic_pour_reduction,
)
from scripts.verification_rgdu.oracle_smic import (  # noqa: E402
    SMIC_H_2026,
    smic_au_rapport_des_salaires,
    smic_forfait_jours,
)

MOIS_BASCULE = 9
MOIS_BLANC = 10
TOLERANCE = 1.0
#: Clés de la base de la réduction posées par une reprise (calcul_reduction_generale).
CLE_BRUT_HORS = "brut_hors_reduction_generale"
CLE_HEURES_HORS = "heures_hors_reduction_generale"


def ecart_d_ouverture(brut_total: float, heures: float, reduction_quadra: float, prm: Parametres) -> float:
    """La formule sur `heures` × 12,02, moins la réduction cumulée de Quadra. Positif : MARTINE
    rattraperait de la réduction au premier mois ; négatif : il en reprendrait."""
    return round(reduction_cumulee(brut_total, round(heures * SMIC_H_2026, 2), prm) - reduction_quadra, 2)


def heures_qui_redonnent_quadra(brut_total: float, reduction_quadra: float, prm: Parametres) -> float:
    return round(smic_pour_reduction(brut_total, reduction_quadra, prm) / SMIC_H_2026, 2)


def base_de_la_reduction(cumuls: dict) -> tuple[float, float, float]:
    """(brut, heures, réduction déjà appliquée) que lit le moteur au mois suivant : même lecture
    que `calcul_reduction_generale._lire_cumuls_precedents` (brut de l'année civile, sinon brut
    total ; base posée par une reprise retirée, jamais sous zéro)."""
    c = (cumuls or {}).get("cumuls") or {}
    brut = float(c.get("brut_annee_civile", c.get("brut_total", 0.0)) or 0.0)
    heures = float(c.get("heures_remunerees", 0.0) or 0.0)
    deja = abs(float(c.get("reduction_generale_patronale", 0.0) or 0.0))
    brut_hors, heures_hors = c.get(CLE_BRUT_HORS), c.get(CLE_HEURES_HORS)
    if brut_hors or heures_hors:
        brut = max(0.0, brut - float(brut_hors or 0.0))
        heures = max(0.0, heures - float(heures_hors or 0.0))
    return round(brut, 2), round(heures, 2), round(deja, 2)


def decomposer(brut_prec: float, heures_prec: float, deja: float, brut_mois: float, heures_mois: float,
               prm: Parametres) -> dict[str, float]:
    """La réduction du mois en trois parts, au centime :
    - `mois_isole` : la formule sur le seul mois ;
    - `effet_du_cumul` : ce que la régularisation progressive ajoute ou retire, légalement, parce
      que le coefficient de l'année change avec ce mois ;
    - `ecart_d_ouverture` : la réduction due au 30/09 selon la formule, moins celle déjà appliquée
      (non nul : l'ouverture ne redonne pas Quadra, la régularisation est anormale).
    Leur somme est la réduction du mois (`total`), comme le moteur la calcule (SMIC cumulé arrondi
    au centime sur les heures cumulées)."""
    smic_prec = round(heures_prec * SMIC_H_2026, 2)
    smic_total = round((heures_prec + heures_mois) * SMIC_H_2026, 2)
    due_prec = reduction_cumulee(brut_prec, smic_prec, prm)
    due_total = reduction_cumulee(round(brut_prec + brut_mois, 2), smic_total, prm)
    isole = reduction_cumulee(brut_mois, round(heures_mois * SMIC_H_2026, 2), prm)
    return {
        "mois_isole": isole,
        "effet_du_cumul": round(due_total - due_prec - isole, 2),
        "ecart_d_ouverture": round(due_prec - deja, 2),
        "total": round(due_total - deja, 2),
    }


EST_BASE = re.compile(r"^SALAIRE\s+DE\s+BASE", re.I)
EST_HS_STRUCTURELLE = re.compile(r"HEURES?\s+SUPP\S*\s+STRUCTUREL", re.I)
EST_HS = re.compile(r"HEURES?\s+SUPP", re.I)
EST_MAINTIEN = re.compile(r"MAINTIEN", re.I)
EST_RAPPEL = re.compile(r"RAPPEL", re.I)
EST_CONGE = re.compile(r"CONG[EÉ]S?\s+PAY|\bCP\b", re.I)


@dataclass
class ElementsMartine:
    """Ce que la loi lit sur un bulletin calculé par MARTINE (lignes du brut et absences)."""
    salaire_base: float = 0.0
    heures_base: float = 0.0
    heures_structurelles: float = 0.0
    montant_structurelles: float = 0.0
    heures_occasionnelles: float = 0.0
    retenues: float = 0.0
    retenues_arret: float = 0.0
    maintien: float = 0.0
    rappels: list[tuple[str, float]] = field(default_factory=list)
    forfait_jours: float | None = None


def elements_martine(payslip_data: dict, forfait_jours: float | None = None) -> ElementsMartine:
    """Lit `calcul_du_brut` et `details_absences`. Les congés payés pris ne réduisent rien (R-H2) :
    leur retenue et la réduction d'heures structurelles qui la suit sortent du calcul. Les rappels
    (de maintien ou autres) restent hors du rapport du mois (R-B1, rattachement non tranché)."""
    el = ElementsMartine(forfait_jours=forfait_jours)
    for l in payslip_data.get("calcul_du_brut") or []:
        lib, gain = str(l.get("libelle") or ""), l.get("gain")
        if gain is None:
            continue
        if EST_BASE.search(lib):
            el.salaire_base = round(el.salaire_base + float(gain), 2)
            el.heures_base = round(el.heures_base + float(l.get("quantite") or 0.0), 2)
        elif EST_RAPPEL.search(lib):
            el.rappels.append((lib, float(gain)))
        elif EST_HS_STRUCTURELLE.search(lib):
            el.heures_structurelles = round(el.heures_structurelles + float(l.get("quantite") or 0.0), 2)
            el.montant_structurelles = round(el.montant_structurelles + float(gain), 2)
        elif EST_HS.search(lib):
            el.heures_occasionnelles = round(el.heures_occasionnelles + float(l.get("quantite") or 0.0), 2)
        elif EST_MAINTIEN.search(lib):
            el.maintien = round(el.maintien + float(gain), 2)
    precedent_conge = False
    for a in payslip_data.get("details_absences") or []:
        perte = float(a.get("perte") or 0.0)
        lib = str(a.get("libelle") or "")
        if a.get("is_reduction_hs"):
            if not precedent_conge:
                el.retenues = round(el.retenues + perte, 2)
            continue
        precedent_conge = bool(EST_CONGE.search(lib)) or bool(a.get("is_conges_payes"))
        if precedent_conge:
            continue
        el.retenues = round(el.retenues + perte, 2)
        if a.get("is_arret_maladie"):
            el.retenues_arret = round(el.retenues_arret + perte, 2)
    return el


def smic_loi_martine(el: ElementsMartine) -> float | None:
    """SMIC légal du mois (R-H1 à R-H9) sur les éléments d'un bulletin MARTINE : rapport des
    salaires sur le mois complet (salaire de base et heures structurelles), heures occasionnelles
    ajoutées entières. None sans salaire de base."""
    complet = round(el.salaire_base + el.montant_structurelles, 2)
    if complet <= 0:
        return None
    due = complet - el.retenues + el.maintien
    if el.forfait_jours:
        return smic_au_rapport_des_salaires(None, due, complet, jours_forfait=el.forfait_jours)
    return smic_au_rapport_des_salaires(min(el.heures_base, 1820 / 12) if el.heures_base else 1820 / 12,
                                        due, complet, heures_structurelles=el.heures_structurelles,
                                        heures_sup_occasionnelles=el.heures_occasionnelles)


def ligne_reduction(payslip_data: dict) -> dict | None:
    for l in (payslip_data.get("structure_cotisations") or {}).get("bloc_allegements") or []:
        if l.get("coti_id") == "reduction_generale":
            return l
    return None


def initiales(e: dict) -> str:
    return f"{(e.get('first_name') or '?')[:1]}.{(e.get('last_name') or '?')[:1]}."


def smic_mois_complet(el: ElementsMartine) -> float | None:
    """SMIC d'un mois payé en entier pour ce contrat (R-H1, R-H8, R-H9), heures occasionnelles à part."""
    complet = round(el.salaire_base + el.montant_structurelles, 2)
    if complet <= 0:
        return None
    if el.forfait_jours:
        return smic_forfait_jours(el.forfait_jours)
    base = min(el.heures_base, 1820 / 12) if el.heures_base else 1820 / 12
    return smic_au_rapport_des_salaires(base, complet, complet, heures_structurelles=el.heures_structurelles)


def smic_des_rappels_de_maintien(el: ElementsMartine) -> float:
    """BOSS § 800 et CSS D241-7, IV, 5e al. : un rappel de maintien rétablit une part de la
    rémunération due des mois d'arrêt ; le SMIC qu'il rétablit (SMIC du mois complet × rappel ÷
    salaire du mois complet) se corrige le mois où la paie en tient compte, celui du rappel.
    C'est aussi ce que fait Quadra (septembre de S.G. chez Comitech). 0 sans rappel de maintien."""
    complet = round(el.salaire_base + el.montant_structurelles, 2)
    rappels = round(sum(m for lib, m in el.rappels if EST_MAINTIEN.search(lib)), 2)
    plein = smic_mois_complet(el)
    if not rappels or complet <= 0 or plein is None:
        return 0.0
    return round(plein * rappels / complet, 2)


# ---------------------------------------------------------------------------------------------
# Exécution (lecture seule)
# ---------------------------------------------------------------------------------------------

def _ouvertures(societe: str, employes: list[dict], cumuls_9: dict[str, dict],
                prm: Parametres) -> tuple[list[dict], dict[str, int]]:
    """(contrôle R1 par salarié présent en septembre, forfait jours de Quadra par employee_id)."""
    from scripts.verification_rgdu.eywai_bac_a_sable import joindre_employes
    from scripts.verification_rgdu.quadra_mois import lire_societe

    quadra = lire_societe(societe)
    par_cle: dict[str, list] = {}
    for (cle, _m), mq in quadra.items():
        par_cle.setdefault(cle, []).append(mq)
    # Jointure sur les seules clés de septembre : un CDD clos puis un contrat d'apprentissage
    # gardent le même NIR sous deux matricules, et le NIR seul ne désigne alors personne.
    jointure = joindre_employes(employes, {c for c, mqs in par_cle.items() if any(m.mois == MOIS_BASCULE for m in mqs)})
    par_id = {e["id"]: e for e in employes}
    lignes, forfaits = [], {}
    for cle, mqs in sorted(par_cle.items()):
        sept = next((m for m in mqs if m.mois == MOIS_BASCULE), None)
        if sept is None:
            continue
        eid = jointure.get(cle, (None, ""))[0]
        if eid and sept.forfait_jours:
            forfaits[eid] = sept.forfait_jours
        e = par_id.get(eid, {})
        c = (cumuls_9.get(eid) or {}).get("cumuls") or {}
        rq = round(sum(m.reduction_mois for m in mqs), 2)
        brut_b, h_b, deja = base_de_la_reduction(cumuls_9.get(eid) or {})
        ligne = {
            "societe": societe, "ini": initiales(e) if e else "?", "employee_id": eid,
            "quadra_brut": sept.cumul_bruts, "quadra_heures": sept.cumul_heures, "quadra_reduction": rq,
            "base_brut": float(c.get("brut_total", 0.0) or 0.0), "base_heures": float(c.get("heures_remunerees", 0.0) or 0.0),
            "base_reduction": abs(float(c.get("reduction_generale_patronale", 0.0) or 0.0)),
            "hors_brut": c.get(CLE_BRUT_HORS), "hors_heures": c.get(CLE_HEURES_HORS),
            "depuis": c.get("reduction_generale_depuis_mois"),
            "formule_brut": brut_b, "formule_heures": h_b, "deja": deja,
        }
        ligne["ecart_ouverture"] = ecart_d_ouverture(brut_b, h_b, deja, prm) if eid else None
        try:
            ligne["heures_quadra"] = heures_qui_redonnent_quadra(brut_b, deja, prm) if deja > 0 else None
        except ValueError:
            ligne["heures_quadra"] = None
        lignes.append(ligne)
    return lignes, forfaits


def _octobre(societe: str, employes: list[dict], cumuls_9: dict[str, dict], saisies: dict[str, list],
             prm: Parametres, filet, forfaits: dict[str, int], ouvertures: dict[str, dict]) -> list[dict]:
    from app.modules.payslips.application.commands import salarie_generable

    sortie = []
    for e in employes:
        debut, fin = str(e.get("hire_date") or ""), str(e.get("contract_end_date") or "")
        if e.get("employment_status") == "parti" or debut > "2026-10-31" or (fin and fin < "2026-10-01"):
            continue
        ligne = {"societe": societe, "ini": initiales(e), "employee_id": e["id"],
                 "saisies": saisies.get(e["id"], [])}
        try:
            salarie_generable(e["id"], 2026, MOIS_BLANC)
            ligne["generable"] = None
        except Exception as exc:  # noqa: BLE001 — le refus de l'écran fait partie du résultat
            ligne["generable"] = f"{type(exc).__name__}: {exc}"
        avant = len(piege.ECRITURES)
        r = filet._calculer([{"employee_id": e["id"], "year": 2026, "month": MOIS_BLANC}])
        v = r.get(f"{e['id']}/2026-{MOIS_BLANC:02d}") or {}
        ligne["ecritures_piegees"] = piege.ECRITURES[avant:]
        if v.get("erreur"):
            ligne["erreur"] = v["erreur"][:400]
            sortie.append(ligne)
            continue
        pd = v.get("payslip_data") or {}
        brut_prec, h_prec, deja = base_de_la_reduction(cumuls_9.get(e["id"]) or {})
        h_oct = round(float(((v.get("cumuls") or {}).get("cumuls") or {}).get("heures_remunerees") or 0.0)
                      - float((((cumuls_9.get(e["id"]) or {}).get("cumuls")) or {}).get("heures_remunerees") or 0.0), 2)
        rg = ligne_reduction(pd) or {}
        brut = float(pd.get("salaire_brut") or 0.0)
        el = elements_martine(pd, forfaits.get(e["id"]))
        smic_loi = smic_loi_martine(el)
        rappels = smic_des_rappels_de_maintien(el)
        # La loi pour octobre : la base de Quadra au 30/09 (heures retrouvées par inversion, R1),
        # le SMIC légal du mois, et le SMIC rétabli par les rappels de maintien (§ 800).
        o = ouvertures.get(e["id"]) or {}
        h_quadra = o.get("heures_quadra") if o.get("heures_quadra") is not None else h_prec
        loi = None
        if smic_loi is not None:
            loi = round(reduction_cumulee(round(brut_prec + brut, 2),
                                          round(round(h_quadra * SMIC_H_2026, 2) + smic_loi + rappels, 2), prm) - deja, 2)
        maintien = ((pd.get("bloc_maintien") or {}).get("maintien") or {})
        ligne.update({
            "brut": brut, "net_a_payer": pd.get("net_a_payer"),
            "heures_reduction": h_oct, "smic_martine": rg.get("smic_reference_mois"), "smic_loi": smic_loi,
            "smic_rappels_maintien": rappels,
            "reduction_mois": round(-float(rg.get("montant_patronal") or 0.0), 2) if rg else None,
            "coefficient": rg.get("taux_patronal"), "reduction_cumulee": rg.get("valeur_cumulative_a_enregistrer"),
            "decomposition": decomposer(brut_prec, h_prec, deja, brut, h_oct, prm),
            "reduction_mois_loi": loi, "heures_ouverture_quadra": h_quadra,
            "elements": asdict(el),
            "maintien": {k: maintien.get(k) for k in ("maintien_verse", "maintien_cible", "regle_retenue",
                                                       "bareme_detail", "taux_maintien", "nb_jours_maintien")},
            "paliers": maintien.get("paliers"),
            "carence": (pd.get("bloc_maintien") or {}).get("carence"),
            "alertes_maintien": (pd.get("bloc_maintien") or {}).get("alertes"),
            "absences": [(a.get("libelle"), a.get("quantite"), a.get("perte")) for a in pd.get("details_absences") or []],
            "lignes_brut": [(l.get("libelle"), l.get("quantite"), l.get("gain"), l.get("perte"))
                            for l in pd.get("calcul_du_brut") or []],
            "alertes": [a.get("code") or a.get("message") for a in pd.get("alertes_baremes") or []
                        if isinstance(a, dict)],
            "report_net_negatif": _reports(pd),
            "warnings": [str(w)[:200] for w in (v.get("warnings") or [])][:10],
        })
        sortie.append(ligne)
    return sortie


def _reports(pd: dict) -> list:
    """Toute ligne du bulletin qui porte un report de net négatif, où qu'elle soit rangée."""
    trouves = []

    def chercher(x, chemin=""):
        if isinstance(x, dict):
            lib = str(x.get("libelle") or x.get("name") or x.get("label") or "")
            if re.search(r"REPORT|N[EÉ]GATIF", lib, re.I):
                trouves.append((chemin, lib, x.get("montant", x.get("amount", x.get("gain", x.get("perte"))))))
            for k, v in x.items():
                chercher(v, f"{chemin}.{k}")
        elif isinstance(x, list):
            for i, v in enumerate(x):
                chercher(v, f"{chemin}[{i}]")

    chercher(pd)
    return trouves


#: Où se lisent les défauts et les données d'octobre (worktree feat/integration-24-10, 25/10/2026).
OU_RAPPEL = ("app/modules/payroll/documents/payslip_run_heures.py:1308-1315 (heures de la réduction "
             "sans les heures rétablies par un rappel de maintien)")
OU_OUVERTURE = ("employee_schedules, mois 9 : clé heures_hors_reduction_generale absente ; cause "
                "scripts/reprise_colorplast_solde_ouverture.py, construire_le_solde")
OU_FICHE = ("app/modules/onboarding/domain/profile.py:16-22 et 98-123, appelé par "
            "app/modules/payslips/application/commands.py:518 ; virement : "
            "app/modules/payroll/exports/paiement_salaires.py:152 ; DSN : "
            "app/modules/dsn_export/application/builder.py:1462 (S21.G00.30.006 vide, non émise)")


def anomalies_d_un_bulletin(o: dict, ouverture: dict | None) -> list[tuple[str, str]]:
    """(classement, phrase) des anomalies d'un bulletin d'octobre à blanc. Classements : « défaut
    de Martine », « donnée à corriger », « attendu »."""
    sortie: list[tuple[str, str]] = []
    if o.get("generable"):
        sortie.append(("donnée à corriger", f"génération refusée : {o['generable'].split(': ', 1)[-1]} ({OU_FICHE})"))
    if o.get("erreur"):
        sortie.append(("défaut de Martine", f"calcul refusé : {o['erreur']}"))
        return sortie
    dec = o["decomposition"]
    # Un palier du coefficient (4 décimales) vaut brut cumulé × 0,0001 : sous lui, c'est l'arrondi.
    palier = max(TOLERANCE, float((ouverture or {}).get("formule_brut") or 0.0) * 0.0001)
    if abs(dec["ecart_d_ouverture"]) >= palier:
        sortie.append(("donnée à corriger",
                       f"ouverture au 30/09 : la formule sur les heures imprimées ne redonne pas la réduction de "
                       f"Quadra, octobre régularise {dec['ecart_d_ouverture']:+.2f} € ; heures de Quadra "
                       f"{(ouverture or {}).get('heures_quadra')} contre {(ouverture or {}).get('base_heures')} "
                       f"imprimées ({OU_OUVERTURE})"))
    if o.get("smic_rappels_maintien"):
        sortie.append(("défaut de Martine",
                       f"rappels de maintien sans SMIC : {o['smic_rappels_maintien']:.2f} € de SMIC des mois d'arrêt "
                       f"non rétabli (BOSS § 800 ; Quadra le rétablit), réduction trop basse ; {OU_RAPPEL}"))
    if o.get("smic_loi") is not None and o.get("smic_martine") is not None \
            and abs(float(o["smic_martine"]) - o["smic_loi"]) > 0.1:
        sortie.append(("défaut de Martine", f"SMIC du mois {o['smic_martine']} contre {o['smic_loi']} selon la loi"))
    if o.get("reduction_mois") is not None and o["reduction_mois"] < 0 and not o.get("smic_rappels_maintien"):
        sortie.append(("défaut de Martine", f"réduction négative ({o['reduction_mois']:+.2f} €) sans cause connue"))
    if "repli_soldes_conges" in (o.get("alertes") or []):
        sortie.append(("attendu", "soldes de congés non imprimés : écriture des droits d'ancienneté bloquée par le "
                                  "piège du bac à sable (calcul réel : écrite)"))
    return sortie


def rapport_octobre(resultat: dict) -> str:
    """Le compte rendu d'octobre à blanc en initiales (data/_rapports, hors git)."""
    ouv = {o["employee_id"]: o for o in resultat["ouvertures"] if o.get("employee_id")}
    lignes = ["# Octobre 2026 à blanc, Colorplast et Comitech", "",
              "Bac à sable, piège posé, filet en lecture seule. Écritures tentées et bloquées : "
              f"{len(resultat.get('ecritures_piegees') or [])} (toutes `{', '.join(sorted(set(resultat.get('ecritures_piegees') or [])))}`).",
              "", "## Ouvertures au 30/09 (R1)", "",
              "| Société | Salarié | Brut | Heures imprimées | Clé posée | Heures de Quadra | Réduction de Quadra | Écart d'ouverture (€) |",
              "|---|---|---|---|---|---|---|---|"]
    for o in resultat["ouvertures"]:
        eo = "" if o["ecart_ouverture"] is None else f"{o['ecart_ouverture']:+.2f}"
        cle = "—" if o["hors_heures"] is None else o["hors_heures"]
        lignes.append(f"| {o['societe']} | {o['ini']} | {o['quadra_brut']:.2f} | {o['quadra_heures']:.2f} | "
                      f"{cle} | {o['heures_quadra']} | {o['quadra_reduction']:.2f} | {eo} |")
    lignes += ["", "## Bulletins d'octobre", "",
               "| Société | Salarié | Générable | Brut | Net à payer | SMIC Martine / loi | Réduction Martine | dont mois isolé / cumul / ouverture | Réduction selon la loi | Écart (€) |",
               "|---|---|---|---|---|---|---|---|---|---|"]
    for o in resultat["octobre"]:
        if o.get("erreur"):
            lignes.append(f"| {o['societe']} | {o['ini']} | — | erreur : {o['erreur'][:80]} | | | | | | |")
            continue
        d = o["decomposition"]
        ecart = round((o["reduction_mois_loi"] or 0.0) - (o["reduction_mois"] or 0.0), 2)
        lignes.append(
            f"| {o['societe']} | {o['ini']} | {'oui' if not o.get('generable') else 'non'} | {o['brut']:.2f} | "
            f"{o['net_a_payer']:.2f} | {o['smic_martine']} / {o['smic_loi']} | {o['reduction_mois']:+.2f} | "
            f"{d['mois_isole']:.2f} / {d['effet_du_cumul']:+.2f} / {d['ecart_d_ouverture']:+.2f} | "
            f"{o['reduction_mois_loi']:+.2f} | {ecart:+.2f} |")
    lignes += ["", "## Anomalies classées", ""]
    for o in resultat["octobre"]:
        for classe, phrase in anomalies_d_un_bulletin(o, ouv.get(o["employee_id"])):
            lignes.append(f"- **{o['societe']} {o['ini']}** — {classe} : {phrase}")
    lignes += ["", "## Arrêts, rappels et report", ""]
    for o in resultat["octobre"]:
        if o.get("erreur"):
            continue
        arrets = [a for a in o.get("absences") or [] if "arrêt" in str(a[0]).lower()]
        if arrets or o.get("saisies"):
            m = o.get("maintien") or {}
            lignes.append(
                f"- **{o['societe']} {o['ini']}** : arrêts {[(a[0], a[1]) for a in arrets] or 'aucun'} ; maintien versé "
                f"{m.get('maintien_verse')} ({m.get('bareme_detail') or m.get('regle_retenue')}), paliers {o.get('paliers') or 'aucun'} ; "
                f"alertes {o.get('alertes_maintien') or 'aucune'} ; saisies {o.get('saisies')} ; "
                f"report de net négatif {[r[1:] for r in o.get('report_net_negatif') or []] or 'aucun'} ; net {o['net_a_payer']}")
    return "\n".join(lignes) + "\n"


def main() -> int:
    import json

    from scripts import filet_paie as filet
    from scripts.verification_rgdu.chemins import RAPPORT, SOCIETES, parametres_de

    resultat: dict = {"ouvertures": [], "octobre": []}
    with filet.Interception("photo"):
        from app.core.database import supabase

        for societe in ("colorplast", "comitech"):
            cid = SOCIETES[societe]["company_id"]
            prm = parametres_de(societe)
            employes = (supabase.table("employees").select(
                "id, first_name, last_name, nir, matricule, hire_date, contract_end_date, employment_status")
                .eq("company_id", cid).execute().data) or []
            ids = [e["id"] for e in employes]
            cumuls_9 = {r["employee_id"]: r.get("cumuls") or {} for r in (
                supabase.table("employee_schedules").select("employee_id, cumuls").in_("employee_id", ids)
                .eq("year", 2026).eq("month", MOIS_BASCULE).execute().data or [])}
            saisies: dict[str, list] = {}
            for s in supabase.table("monthly_inputs").select("employee_id, name, amount").in_("employee_id", ids).eq(
                    "year", 2026).eq("month", MOIS_BLANC).execute().data or []:
                saisies.setdefault(s["employee_id"], []).append((s["name"], float(s["amount"])))
            ouvertures, forfaits = _ouvertures(societe, employes, cumuls_9, prm)
            resultat["ouvertures"] += ouvertures
            resultat["octobre"] += _octobre(societe, employes, cumuls_9, saisies, prm, filet, forfaits,
                                            {o["employee_id"]: o for o in ouvertures if o["employee_id"]})
    resultat["ecritures_piegees"] = piege.ECRITURES
    RAPPORT.mkdir(parents=True, exist_ok=True)
    (RAPPORT / "octobre.json").write_text(json.dumps(resultat, ensure_ascii=False, indent=1, default=str),
                                          encoding="utf-8")
    (RAPPORT / "octobre.md").write_text(rapport_octobre(resultat), encoding="utf-8")
    print("écritures piégées :", sorted(set(piege.ECRITURES)), len(piege.ECRITURES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
