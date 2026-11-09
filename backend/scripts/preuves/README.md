# Outils de preuve

Filet de non-régression et rejeux au bac à sable. Aucun de ces scripts n'écrit en
base : `filet28.py` pose le piège à écritures de `scripts/verification_rgdu/piege.py`
avant d'importer l'application, et s'arrête si une écriture est tentée.

Rien ne vit ici qui viendrait d'un rejeu : les sorties (JSON, journaux) restent hors
du dépôt, car elles portent des bulletins réels.

| Fichier | Rôle |
|---|---|
| `lancer.sh` | Copie le backend d'un commit et relève les bulletins 2026 des sociétés demandées. |
| `filet28.py` | Recalcule les bulletins 2026 au bac à sable, avec la vue imprimée et l'enrichissement (saisies, avances, prêts) rejoué en mémoire. |
| `comparer5.py` | Compare deux relevés au centime : net, brut, lignes, pied, cumuls. |
| `classer_filet.py` | Classe les écarts d'une comparaison par chemin et par société. |
| `octobre.py` | Octobre 2026 au bac à sable, pour chaque salarié actif d'une société. |

Le rapport de `comparer5.py` n'affiche que 20 lignes par bulletin : qualifier un écart
sur les fichiers JSON ou avec `classer_filet.py`, jamais sur cet extrait.

Usage, depuis `backend/` :

    BACKEND_ENV=/chemin/.env VENV_PYTHON=/chemin/.venv/bin/python \
      scripts/preuves/lancer.sh /dossier/hors/depot/apres-X <commit>
    .venv/bin/python scripts/preuves/comparer5.py "/dossier/avant/apres_*.json" "/dossier/hors/depot/apres-X/apres_*.json"

Test du théorème (correction à la main) : `scripts/theoreme_correction_a_la_main.py`.
