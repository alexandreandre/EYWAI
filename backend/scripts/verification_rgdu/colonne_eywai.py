"""Ce que calcule EYWAI : heures et SMIC de référence du mois, ligne de réduction.

Deux sources :
- `depuis_le_filet` : le filet de Colorplast (janvier à août), déjà calculé par le
  moteur et figé en JSON (`data/_filet/colorplast-janvier-aout/reference.json`) ;
- `depuis_le_bac_a_sable` : un appel direct au moteur, en bac à sable (rien n'est
  écrit en base), pour les mois qui n'ont pas de filet. Le piège à écritures
  (`scripts.verification_rgdu.piege.poser_le_piege`) est à poser par l'appelant,
  avant tout import de `app` — cette fonction ne le pose pas elle-même.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from scripts.verification_rgdu.oracle_smic import SMIC_H_2026


@dataclass
class MoisEywai:
    """Un mois retenu par EYWAI pour un salarié : heures de référence pour le SMIC
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
    """
    from app.modules.payslips.infrastructure.providers import payslip_generator_provider

    res = payslip_generator_provider.generate_en_bac_a_sable(employee_id, 2026, mois, cumuls_precedents)
    avant = float((cumuls_precedents.get("cumuls") or {}).get("heures_remunerees") or 0.0)
    apres = float(((res.get("cumuls") or {}).get("cumuls") or {}).get("heures_remunerees") or 0.0)
    h = round(apres - avant, 2)
    return MoisEywai(employee_id, mois, h, round(h * SMIC_H_2026, 2), _ligne_rg(res["payslip_data"]), "bac_a_sable")
