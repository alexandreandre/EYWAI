"""Rejeu d'une société : Quadra (DSN ou implicite), loi, MARTINE → data/_rapports/rgdu-2026/.

Trois colonnes par salarié et par mois (spec, étape 3) :
- **Quadra** : le SMIC retenu de la DSN (janvier à juin), sinon le SMIC implicite retrouvé
  depuis la réduction cumulée imprimée (`implicite.smic_quadra_par_mois`) ;
- **loi** : `regle_du_mois.smic_loi_du_mois`, appliqué aux lignes du bulletin Quadra, avec la
  seconde lecture des points non tranchés quand elle existe ;
- **MARTINE** : le moteur en bac à sable, cumuls de Quadra au mois précédent, lu dans le cache
  `eywai_<societe>.json` écrit par `eywai_bac_a_sable` (aucun appel au moteur ici).

Rien n'est lu en base et rien n'y est écrit : le piège est posé avant tout import, parce que
`quadra_mois` importe l'application. Sorties nominatives (clé NIR/matricule), hors git :
`<societe>.csv` et `<societe>.md` (comptes, couverture, détail à juger, clé tronquée).

Usage (depuis backend/) :
    MARTINE_DATA=… PYTHONPATH=. .venv/bin/python -m scripts.verification_rgdu.rejouer colorplast comitech mbc
"""
from __future__ import annotations

import sys

from scripts.verification_rgdu import piege

if __name__ == "__main__":
    piege.poser_le_piege()

import json  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from pathlib import Path  # noqa: E402

from scripts.verification_rgdu.chemins import (  # noqa: E402
    ANNEE,
    RAPPORT,
    SOCIETES,
    parametres_de,
)
from scripts.verification_rgdu.comparaison import (  # noqa: E402
    TOLERANCE_SMIC,
    LigneComparee,
    preclasser,
)
from scripts.verification_rgdu.oracle import Parametres  # noqa: E402

#: Les DSN de Quadra couvrent janvier à juin (`demande-donnees.md`).
MOIS_DSN = tuple(range(1, 7))


@dataclass
class MoisRejoue:
    """Ce qu'il faut d'un mois Quadra pour la ligne comparée."""
    mq: object        # quadra_mois.MoisQuadra
    loi: object       # regle_du_mois.SmicLoi


def smic_quadra_du_mois(mois: int, smic_dsn: dict[int, float], implicite: dict) -> tuple[float | None, str]:
    """(SMIC du mois retenu par Quadra, source) : la DSN d'abord, l'implicite ensuite."""
    if mois in smic_dsn:
        return smic_dsn[mois], "dsn"
    si = implicite.get(mois)
    if si is not None and si.calculable and si.smic_mois is not None:
        return si.smic_mois, "implicite"
    return None, "implicite" if si is not None else "absent"


def smic_eywai(cache: dict, cle: str, mois: int) -> float | None:
    v = cache.get(f"{cle}|{mois}") or {}
    return float(v["smic"]) if v.get("statut") == "ok" and v.get("smic") is not None else None


def exces_de_juin(mois: list[MoisRejoue], smic_dsn: dict[int, float], implicite: dict) -> float | None:
    """Le SMIC de juin que Quadra a compté à 12,31 € au lieu de 12,02 € (R-F2), pour un salarié.

    Deux traces : la DSN de juin elle-même (SMIC déclaré au-dessus de la loi d'environ 2,4 %), ou,
    quand la DSN déclare 12,02 €, son SMIC cumulé implicite de juin (inversion de la réduction
    cumulée) au-dessus du cumul de ses DSN de janvier à juin. La plus grande des deux, si elle
    dépasse une demi-heure de SMIC ; None sinon."""
    from scripts.verification_rgdu.classement import HAUSSE_DE_JUIN

    candidats = []
    juin = next((x for x in mois if x.mq.mois == 6), None)
    if juin is not None and 6 in smic_dsn and juin.loi.smic:
        d = smic_dsn[6] - juin.loi.smic
        if abs(d - juin.loi.smic * HAUSSE_DE_JUIN) <= TOLERANCE_SMIC:
            candidats.append(d)
    presents = [x.mq.mois for x in mois if x.mq.mois <= 6]
    si = implicite.get(6)
    if presents and all(m in smic_dsn for m in presents) and si is not None and si.smic_cumule is not None:
        candidats.append(si.smic_cumule - sum(smic_dsn[m] for m in presents))
    candidats = [c for c in candidats if c > TOLERANCE_SMIC]
    return round(max(candidats), 2) if candidats else None


def comparer_un_salarie(societe: str, cle: str, mois: list[MoisRejoue], smic_dsn: dict[int, float],
                        cache: dict, prm: Parametres) -> list[tuple[LigneComparee, str]]:
    """Les lignes comparées d'un salarié (une clé Quadra), mois par mois, avec la règle de la loi."""
    from scripts.verification_rgdu.implicite import smic_quadra_par_mois

    mois = sorted(mois, key=lambda x: x.mq.mois)
    implicite = smic_quadra_par_mois([x.mq for x in mois], prm)
    sortie: list[tuple[LigneComparee, str]] = []
    smic_cumule = 0.0
    for x in mois:
        mq, loi = x.mq, x.loi
        smic_q, source = smic_quadra_du_mois(mq.mois, smic_dsn, implicite)
        l = LigneComparee(societe, cle, mq.mois, smic_q, source, loi.smic, smic_eywai(cache, cle, mq.mois),
                          mq.cumul_bruts, round(smic_cumule, 2), smic_loi_variante=loi.smic_variante,
                          variante=loi.variante)
        l.preclassement = preclasser(l, prm)
        notes = [n for n in (l.note, loi.note) if n]
        if smic_q is None and mq.mois in implicite:
            notes.append(f"Quadra : {implicite[mq.mois].raison}")
        l.note = " ; ".join(notes)
        sortie.append((l, loi.regle))
        smic_cumule += smic_q or 0.0
    EXCES_DE_JUIN.setdefault(societe, {})[cle] = exces_de_juin(mois, smic_dsn, implicite)
    return sortie


def lignes_de_la_societe(societe: str) -> list[tuple[LigneComparee, str]]:
    from scripts.backtest.colorplast_lignes_quadra import lire_bulletins
    from scripts.verification_rgdu.dsn_quadra import dsn_du_mois
    from scripts.verification_rgdu.eywai_bac_a_sable import (
        chemin_cache,
        lire_cache,
        smic_dsn_du_salarie,
    )
    from scripts.verification_rgdu.quadra_mois import elements_du_mois
    from scripts.verification_rgdu.regle_du_mois import (
        choisir_reference,
        elements_loi,
        smic_loi_du_mois,
    )

    prm = parametres_de(societe)
    mois_soc = SOCIETES[societe]["mois"]
    lus = {m: lire_bulletins(ANNEE, m, SOCIETES[societe]["dossier"]) for m in mois_soc}
    par_cle: dict[str, dict[int, tuple]] = {}
    for m in mois_soc:
        for mq in elements_du_mois(lus[m], lus.get(m - 1), societe, m):
            cle = f"{mq.nir}/{mq.matricule}" if mq.nir else mq.matricule
            par_cle.setdefault(cle, {})[m] = (mq, elements_loi(lus[m][mq.matricule]))
    bases = {m: dsn_du_mois(societe, m) for m in MOIS_DSN}
    cache = lire_cache(chemin_cache(societe))
    sortie: list[tuple[LigneComparee, str]] = []
    for cle, mois in sorted(par_cle.items()):
        rejoues = [MoisRejoue(mq, smic_loi_du_mois(mq, el, choisir_reference(mois, m)))
                   for m, (mq, el) in sorted(mois.items())]
        nir = next(iter(mois.values()))[0].nir
        smic_dsn = smic_dsn_du_salarie(bases, nir) if nir else {}
        sortie += comparer_un_salarie(societe, cle, rejoues, smic_dsn, cache, prm)
    return sortie


def classer_les_lignes(societe: str, lignes: list[tuple[LigneComparee, str]]) -> list[tuple[str, str, str]]:
    """Le classement final de chaque ligne (`classement.classer`), le contexte du salarié compris."""
    from scripts.verification_rgdu.classement import Contexte, classer

    contextes = {cle: Contexte(exces_juin=e, societe_sans_reduction_en_janvier=societe == "comitech")
                 for cle, e in EXCES_DE_JUIN.get(societe, {}).items()}
    defaut = Contexte(societe_sans_reduction_en_janvier=societe == "comitech")
    return [classer(l, r, contextes.get(l.cle, defaut)) for l, r in lignes]


#: Excès de juin par société et par clé, posé par `comparer_un_salarie` pour le classement.
EXCES_DE_JUIN: dict[str, dict[str, float | None]] = {}


def ecrire(societe: str, lignes: list[tuple[LigneComparee, str]], dossier: Path = RAPPORT) -> str:
    from scripts.verification_rgdu.rapport import (
        couverture,
        detail_a_juger,
        ecrire_csv,
        resume_agrege,
    )

    from scripts.verification_rgdu.rapport import resume_classement

    ls = [l for l, _ in lignes]
    classements = classer_les_lignes(societe, lignes)
    ecrire_csv(ls, dossier / f"{societe}.csv", [r for _, r in lignes], classements)
    texte = (f"# Rejeu {societe}\n\n## Comptes\n\n{resume_agrege(ls)}\n## Classement final\n\n"
             f"{resume_classement(ls, classements)}\n## Couverture\n\n{couverture(ls)}\n"
             f"## À juger\n\n{detail_a_juger(ls)}")
    (dossier / f"{societe}.md").write_text(texte, encoding="utf-8")
    return resume_agrege(ls)


def main(societes: list[str]) -> int:
    piege.poser_le_piege()
    for societe in societes:
        print(ecrire(societe, lignes_de_la_societe(societe)))
    print("écritures tentées :", json.dumps(piege.ECRITURES, ensure_ascii=False))
    return 1 if piege.ECRITURES else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["colorplast", "comitech", "mbc"]))
