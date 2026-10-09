"""Ce que calcule MARTINE : heures et SMIC de référence du mois, ligne de réduction.

Deux sources :
- `depuis_le_filet` : le filet de Colorplast (janvier à août), déjà calculé par le
  moteur et figé en JSON (`data/_filet/colorplast-janvier-aout/reference.json`) ;
- `depuis_le_bac_a_sable` : un appel direct au moteur, en bac à sable (rien n'est
  écrit en base), pour les mois qui n'ont pas de filet. Le piège à écritures
  (`scripts.verification_rgdu.piege.poser_le_piege`) est à poser par l'appelant,
  avant tout import de `app` — cette fonction ne le pose pas elle-même.

Quand le bac à sable démarre au milieu de l'année (pas de filet MARTINE avant),
`cumuls_quadra_avant` reconstruit les cumuls à injecter depuis les seules
données Quadra (bulletins + DSN), pour un salarié.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from scripts.verification_rgdu.implicite import SmicImplicite
from scripts.verification_rgdu.oracle_smic import SMIC_H_2026
from scripts.verification_rgdu.quadra_mois import MoisQuadra


@dataclass
class MoisEywai:
    """Un mois retenu par MARTINE pour un salarié : heures de référence pour le SMIC
    (`heures_reduction`), SMIC de référence qui en découle (`smic`, heures × 12,02),
    et la ligne de réduction générale imprimée par le moteur (`reduction_ligne`,
    `None` si absente du bulletin). `source` vaut « filet » ou « bac_a_sable »."""
    employee_id: str
    mois: int
    heures_reduction: float
    smic: float
    reduction_ligne: float | None
    source: str


def _ligne_rg(payslip_data: dict) -> float | None:
    """La réduction générale patronale imprimée par le moteur, positive (le bulletin
    la porte en négatif, montant qui vient en déduction des cotisations patronales)."""
    for l in (payslip_data.get("structure_cotisations") or {}).get("bloc_allegements") or []:
        if l.get("coti_id") == "reduction_generale":
            return round(-float(l.get("montant_patronal") or 0.0), 2)
    return None


def depuis_le_filet(chemin: Path) -> dict[tuple[str, int], MoisEywai]:
    """Lit le filet Colorplast (janvier à août) : `chemin` pointe vers son
    `reference.json`, `"<employee_id>/<AAAA-MM>" -> {payslip_data, cumuls, warnings}`.

    Les heures du mois sont la différence des `heures_remunerees` cumulées d'un
    mois à l'autre (cumul du mois précédent soustrait, janvier pris tel quel) ; le
    SMIC de référence en découle (heures × 12,02, R-F2). La ligne de réduction est
    lue sur `payslip_data` de ce même mois (`_ligne_rg`). `source="filet"`.
    """
    ref = json.loads(Path(chemin).read_text(encoding="utf-8"))
    par_salarie: dict[str, list[tuple[int, dict]]] = {}
    for cle, v in ref.items():
        eid, periode = cle.split("/")
        par_salarie.setdefault(eid, []).append((int(periode[-2:]), v))
    sortie: dict[tuple[str, int], MoisEywai] = {}
    for eid, mois in par_salarie.items():
        prec = 0.0
        for m, v in sorted(mois):
            cumul = float(((v.get("cumuls") or {}).get("cumuls") or {}).get("heures_remunerees") or 0.0)
            h = round(cumul - (prec if m > 1 else 0.0), 2)
            sortie[(eid, m)] = MoisEywai(eid, m, h, round(h * SMIC_H_2026, 2), _ligne_rg(v["payslip_data"]), "filet")
            prec = cumul
    return sortie


def depuis_le_bac_a_sable(employee_id: str, mois: int, cumuls_precedents: dict) -> MoisEywai:
    """Appelle le moteur en bac à sable pour un salarié et un mois, à partir des
    cumuls du mois précédent (`cumuls_precedents`, même forme que `cumuls` dans le
    filet). Rien n'est écrit en base : `payslip_generator_provider.generate_en_bac_a_sable`
    passe par `BacASable`. Le piège à écritures doit déjà être posé par l'appelant
    (`piege.poser_le_piege()`, avant tout import de `app`) ; cette fonction ne le
    pose pas elle-même, pour ne pas masquer un import d'`app` fait trop tôt ailleurs.

    Les heures du mois sont la différence entre `heures_remunerees` cumulées après
    et avant l'appel. `source="bac_a_sable"`.

    Janvier (`mois == 1`) est un cas à part : le moteur remet `heures_remunerees`
    à zéro AVANT d'ajouter le mois (`payslip_run_common.mettre_a_jour_cumuls`,
    reset des compteurs d'année civile, `if mois == 1: cumuls[...] = 0.0` avant
    l'incrément du mois) — la valeur en sortie (`apres`) est donc déjà les seules
    heures de janvier, quels que soient les cumuls injectés. Les soustraire
    (comme pour un mois ordinaire) donnerait un résultat faux dès que
    `cumuls_precedents` porte des heures non nulles (cumuls reconstruits depuis
    Quadra, étape 5) : `avant` vaut donc `0.0` par construction pour janvier,
    jamais la valeur de `cumuls_precedents`.
    """
    from app.modules.payslips.infrastructure.providers import payslip_generator_provider

    res = payslip_generator_provider.generate_en_bac_a_sable(employee_id, 2026, mois, cumuls_precedents)
    avant = 0.0 if mois == 1 else float((cumuls_precedents.get("cumuls") or {}).get("heures_remunerees") or 0.0)
    apres = float(((res.get("cumuls") or {}).get("cumuls") or {}).get("heures_remunerees") or 0.0)
    h = round(apres - avant, 2)
    return MoisEywai(employee_id, mois, h, round(h * SMIC_H_2026, 2), _ligne_rg(res["payslip_data"]), "bac_a_sable")


def cumuls_quadra_avant(
    mois: int,
    mois_quadra: list[MoisQuadra],
    smic_dsn: dict[int, float],
    implicite: dict[int, SmicImplicite],
) -> dict | None:
    """Cumuls à injecter dans `depuis_le_bac_a_sable` pour calculer `mois` : l'état
    cumulé de Quadra à la fin du mois `mois - 1`, pour UN salarié (une année,
    2026 — mêmes données que le reste du chantier).

    Ne couvre que `brut_total`, `heures_remunerees` et
    `reduction_generale_patronale` : les trois seuls cumuls que lit la réduction
    générale (`calcul_reduction_generale._lire_cumuls_precedents`, lignes
    198-225 — `contexte.cumuls["cumuls"].get("brut_total"/"heures_remunerees"
    /"reduction_generale_patronale")`, rien d'autre). `net_imposable`,
    `impot_preleve_a_la_source` et `heures_supplementaires_remunerees` sont
    volontairement absents du résultat (aucune source Quadra fiable pour les
    reconstruire ici) : le reste du moteur les traite comme `0.0` par défaut
    (`cumuls.get(cle, 0.0)`, `payslip_run_common.mettre_a_jour_cumuls`), et la
    réduction générale elle-même ne les lit jamais — sans effet sur
    `heures_reduction` ni sur `reduction_ligne`.

    `brut_total` = `cumul_bruts` de Quadra au mois `mois - 1` (déjà cumulé sur
    le bulletin lui-même, `quadra_mois.MoisQuadra.cumul_bruts`).

    `heures_remunerees` = SMIC cumulé ÷ 12,02 (`oracle_smic.SMIC_H_2026`), où le
    SMIC cumulé vient, dans cet ordre de préférence :
    1. la DSN (`smic_dsn`, SMIC retenu de la base 03 — `dsn_quadra.py`) : somme
       des mois 1 à `mois - 1`, mais SEULEMENT si chacun de ces mois y est
       connu (une somme partielle mélangerait silencieusement DSN et
       implicite — la DSN Quadra ne couvre que janvier à juin) ;
    2. à défaut, le SMIC cumulé implicite du seul mois `mois - 1`
       (`implicite[mois - 1].smic_cumule`) : déjà cumulé depuis janvier par
       construction (`implicite.smic_quadra_par_mois`), pas la peine de sommer.

    `reduction_generale_patronale` = -(somme des `reduction_mois` de Quadra du
    mois 1 à `mois - 1`, présents dans `mois_quadra`), signe négatif comme sur
    le bulletin (voir `_ligne_rg`).

    `None` (rien à injecter) dans trois cas :
    - `mois <= 1` : rien n'existe avant janvier, et `depuis_le_bac_a_sable`
      ignore de toute façon les cumuls injectés pour janvier (voir sa
      docstring) — l'appelant n'a rien à reconstruire pour ce mois ;
    - le mois `mois - 1` est absent de `mois_quadra` (aucun `cumul_bruts` de
      départ) ;
    - ni la DSN complète, ni l'implicite de `mois - 1` (absent du dict, ou
      `smic_cumule=None`) ne donnent de SMIC cumulé. `smic_cumule` est utilisé
      même quand `calculable=False` (cascade, `implicite.py` cas 3 et 4) : ce
      champ reste alors publié et fiable, seule sa décomposition en SMIC du
      mois ne l'est pas — voir la docstring d'`implicite.smic_quadra_par_mois`.
    """
    if mois <= 1:
        return None
    mois_prec = mois - 1
    mq_prec = next((m for m in mois_quadra if m.mois == mois_prec), None)
    if mq_prec is None:
        return None

    if all(m in smic_dsn for m in range(1, mois)):
        smic_cumule = round(sum(smic_dsn[m] for m in range(1, mois)), 2)
    else:
        si_prec = implicite.get(mois_prec)
        if si_prec is None or si_prec.smic_cumule is None:
            return None
        smic_cumule = si_prec.smic_cumule

    reduction_cumulee = round(sum(m.reduction_mois for m in mois_quadra if m.mois <= mois_prec), 2)
    return {
        "cumuls": {
            "brut_total": mq_prec.cumul_bruts,
            "heures_remunerees": round(smic_cumule / SMIC_H_2026, 2),
            "reduction_generale_patronale": -reduction_cumulee,
        }
    }
