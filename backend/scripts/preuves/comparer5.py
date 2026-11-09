"""(Variante : ordre des lignes de mutuelle normalisé.) Compare deux relevés du filet (fichiers par société fusionnés) au centime :
payslip_data (net, brut, net imposable, chaque ligne, pied, mentions), vue imprimée, cumuls.

Usage : python comparer5.py "avant_*.json" "apres_*.json"
La clé de vue `pied.impot.exoneration_stagiaire` (nouvelle, rendu seulement) est
tolérée quand elle vaut False : rien ne s'imprime ; tout autre écart est listé.
"""
from __future__ import annotations

import glob
import json
import sys
from collections import Counter, defaultdict

VOLATILS = {"genere_le", "generated_at", "date_generation", "horodatage", "created_at", "updated_at",
            "empreinte_entrees", "calcule_le"}
TOLERE = ".vue.pied.impot.exoneration_stagiaire"


def diff(a, b, chemin="", sortie=None):
    sortie = [] if sortie is None else sortie
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k in VOLATILS:
                continue
            if k not in a or k not in b:
                sortie.append((f"{chemin}.{k}", a.get(k, "<absent>"), b.get(k, "<absent>")))
            else:
                diff(a[k], b[k], f"{chemin}.{k}", sortie)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            sortie.append((f"{chemin}[len]", len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f"{chemin}[{i}]", sortie)
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        if round(float(a), 2) != round(float(b), 2):
            sortie.append((chemin, a, b))
    elif a != b:
        sortie.append((chemin, a, b))
    return sortie


def _mutuelle(x):
    if not isinstance(x, dict):
        return False
    lib = str(x.get("libelle") or "")
    return x.get("coti_id") == "mutuelle" or lib.startswith("Mutuelle") or lib.startswith("GAN ")


def normaliser(o):
    """Trie par libellé chaque suite contiguë de lignes de mutuelle : leur ordre
    vient de la base (lecture sans ORDER BY), pas du code."""
    if isinstance(o, dict):
        return {k: normaliser(v) for k, v in o.items()}
    if isinstance(o, list):
        o = [normaliser(v) for v in o]
        out, i = [], 0
        while i < len(o):
            if _mutuelle(o[i]):
                j = i
                while j < len(o) and _mutuelle(o[j]):
                    j += 1
                out.extend(sorted(o[i:j], key=lambda x: str(x.get("libelle"))))
                i = j
            else:
                out.append(o[i]); i += 1
        return out
    return o


def charger(motif):
    tout = {}
    for f in sorted(glob.glob(motif)):
        tout.update(normaliser(json.load(open(f, encoding="utf-8"))))
    return tout


def main(m_avant, m_apres):
    avant, apres = charger(m_avant), charger(m_apres)
    par_soc = Counter()
    ecarts, ecarts_cumuls, erreurs = {}, {}, []
    toleres = 0
    for cle in sorted(set(avant) | set(apres)):
        soc, eid, mois = cle.split("|")
        a, b = avant.get(cle), apres.get(cle)
        if a is None or b is None:
            erreurs.append((cle, "absent d'un relevé"))
            continue
        if a["statut"] != "ok" or b["statut"] != "ok":
            erreurs.append((cle, a.get("erreur"), b.get("erreur")))
            continue
        par_soc[(soc, int(mois))] += 1
        d = (diff(a["payslip_data"], b["payslip_data"], ".data") + diff(a.get("vue"), b.get("vue"), ".vue")
             + diff(a.get("enrichissement"), b.get("enrichissement"), ".enrichissement"))
        reste = []
        for c, x, y in d:
            if c == TOLERE and x == "<absent>" and y is False:
                toleres += 1
                continue
            reste.append((c, x, y))
        if reste:
            ecarts[cle] = reste
        dc = diff(a.get("cumuls"), b.get("cumuls"))
        if dc:
            ecarts_cumuls[cle] = dc
    print("Bulletins comparés (société, mois) :")
    for (soc, mois), n in sorted(par_soc.items()):
        print(f"  {soc} m{mois} : {n}")
    print(f"Total comparés : {sum(par_soc.values())} ; clé de vue nouvelle à False tolérée sur {toleres}")
    print(f"Bulletins avec écart : {len(ecarts)}")
    chemins = Counter()
    for cle, d in ecarts.items():
        print(f"  {cle} : {len(d)} écarts")
        for c, x, y in d[:20]:
            print(f"     {c} : {x!r} -> {y!r}")
            chemins[c.split('[')[0]] += 1
    print(f"Cumuls avec écart : {len(ecarts_cumuls)}")
    for cle, d in ecarts_cumuls.items():
        print(f"  {cle} : " + "; ".join(f"{c} {x!r}->{y!r}" for c, x, y in d[:6]))
    print(f"Erreurs / absents : {len(erreurs)}")
    for e in erreurs:
        print("  ", e)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
