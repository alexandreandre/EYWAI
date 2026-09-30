# Vérification de la réduction générale (RGDU 2026) — plan d'exécution

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**But :** répondre, preuve et montant à l'appui, à chaque question de la spec, et conclure pour chaque société à partir de quand la réduction générale calculée par EYWAI est fiable.

**Architecture :**
- Un paquet de scripts de vérification, `backend/scripts/verification_rgdu/`, hors du moteur. Il ne l'importe qu'en lecture ou en bac à sable, avec toutes les écritures piégées.
- Il lit trois sources par salarié et par mois :
  - les bulletins Quadra (PDF) ;
  - les DSN Quadra (SMIC retenu, codes 018 et 106) ;
  - le calcul d'EYWAI.
- Il les compare à un calcul de référence écrit depuis les textes officiels, puis classe chaque écart.
- Les rapports nominatifs restent dans `data/_rapports/rgdu-2026/`, que git ignore. Seul un résumé agrégé, sans nom, est versionné.

**Stack :** Python 3.11 (CI) / 3.12 (poste), pytest, les lecteurs existants `scripts/backtest/colorplast_lignes_quadra.py`, le bac à sable `payslip_generator_provider.generate_en_bac_a_sable`.

**Spec :** `docs/superpowers/specs/2026-09-29-verification-reduction-generale-design.md` (fa726c8a).

## Contraintes globales

- **Base de test :** lecture seule, car Gaëlle y fait la vraie paie. Aucune écriture en base. Jamais la production (`slleauhyjnmiawosvlcg`).
- **Calculs à blanc :** toujours avec `verification_rgdu.piege.poser_le_piege()` appelé avant tout import applicatif.
- **Moteur :** aucune modification de `backend/app/` pendant ce chantier.
- **Noms de salariés :**
  - jamais dans git : ni code, ni tests, ni messages de commit ;
  - les tests utilisent des valeurs réelles anonymisées (« salarié A ») ;
  - avant chaque commit, `python -m scripts.verification_rgdu.sans_nom <fichiers>` doit répondre « aucun nom ».
- **Rapports nominatifs :** uniquement dans `data/_rapports/rgdu-2026/` (dossier `/data/` ignoré par git).
- **Textes officiels :** sources publiques, citées avec l'URL et la date de consultation.
- **Règle de référence :**
  - mois payés par Quadra : Quadra fait foi ;
  - mois payés par EYWAI : la loi fait foi ;
  - une divergence qui expose à un redressement est signalée à Alexandre.
- **Seuils d'écart :** 1 € de réduction ou 0,5 h de SMIC (6,01 € de SMIC de référence).
- **Réponses :** en français, sans jargon inutile.
- **Commits :** sur la branche `fix/payslip-edit-state`, jamais sur `main`. Message terminé par `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **Commandes :** depuis `backend/`, avec `.venv/bin/python` et `PYTHONPATH=.`. Pour les tests : `env -u APP_ENV .venv/bin/python -m pytest -q -p no:faulthandler`.

## Carte des fichiers

| Fichier | Rôle |
|---|---|
| `backend/scripts/verification_rgdu/__init__.py` | Paquet, docstring du chantier |
| `backend/scripts/verification_rgdu/chemins.py` | Chemins, sociétés, mois rejoués |
| `backend/scripts/verification_rgdu/piege.py` | Piège à écritures postgrest et storage, posé et retiré |
| `backend/scripts/verification_rgdu/sans_nom.py` | Refuse un fichier qui contient un nom de salarié |
| `backend/scripts/verification_rgdu/oracle.py` | Formule RGDU : coefficient, réduction cumulée, réduction du mois |
| `backend/scripts/verification_rgdu/oracle_smic.py` | SMIC de référence du mois selon les règles légales, avec leurs variantes |
| `backend/scripts/verification_rgdu/dsn_quadra.py` | Lecture des DSN Quadra : SMIC retenu, 018, 106 par NIR et période |
| `backend/scripts/verification_rgdu/quadra_mois.py` | Éléments du mois tirés des bulletins Quadra |
| `backend/scripts/verification_rgdu/regle_du_mois.py` | SMIC légal du mois à partir des éléments Quadra |
| `backend/scripts/verification_rgdu/implicite.py` | SMIC cumulé implicite de Quadra, reconstitué depuis sa réduction cumulée |
| `backend/scripts/verification_rgdu/colonne_eywai.py` | SMIC et réduction d'EYWAI : filet Colorplast et bac à sable |
| `backend/scripts/verification_rgdu/comparaison.py` | Lignes salarié × mois à trois colonnes, pré-classement, impact en euros |
| `backend/scripts/verification_rgdu/rapport.py` | CSV et Markdown nominatifs, résumé agrégé versionnable |
| `backend/scripts/verification_rgdu/ouverture.py` | Contrôle R1 des ouvertures, septembre à blanc avant et après |
| `backend/scripts/verification_rgdu/rejouer.py` | Point d'entrée : une société → tableaux complets |
| `backend/tests/unit/scripts/verification_rgdu/test_*.py` | Tests unitaires de chaque module |
| `docs/reference/reduction-generale-2026/*.md` | Textes officiels et tableau des règles |
| `data/_rapports/rgdu-2026/*` | Sorties nominatives, non versionnées |
| `docs/comptes-rendus/verification-reduction-generale-2026.md` | Résumé final agrégé, sans nom |

---

### Tâche 0 : squelette, piège, garde anti-noms, demande des données

**Fichiers :**
- Créer : `backend/scripts/verification_rgdu/__init__.py`, `chemins.py`, `piege.py`, `sans_nom.py`
- Créer : `backend/tests/unit/scripts/verification_rgdu/__init__.py` (vide), `test_piege.py`, `test_sans_nom.py`

**Interfaces :**
- Produit :
  - `chemins.DATA: Path`, `chemins.RAPPORT: Path`, `chemins.TEXTES: Path` ;
  - `chemins.SOCIETES: dict[str, dict]`, avec les clés `company_id: str | None`, `mois: tuple[int, ...]` et `dossier: str` ;
  - `piege.poser_le_piege() -> None`, `piege.retirer_le_piege() -> None`, `piege.ECRITURES: list[str]`, `piege.EcritureInterdite` ;
  - `sans_nom.noms_trouves(texte: str) -> list[str]`, et `python -m scripts.verification_rgdu.sans_nom f1 f2…` (code retour 1 si un nom est trouvé).

- [ ] **Étape 1 : écrire les tests qui échouent**

`backend/tests/unit/scripts/verification_rgdu/test_piege.py` :
```python
"""Le piège bloque toute écriture Supabase et se retire proprement."""
from unittest.mock import MagicMock

import pytest

from scripts.verification_rgdu import piege

pytestmark = pytest.mark.unit


def test_une_ecriture_est_bloquee_puis_le_piege_se_retire():
    import postgrest._sync.request_builder as rb

    original = rb.SyncRequestBuilder.insert
    piege.poser_le_piege()
    try:
        with pytest.raises(piege.EcritureInterdite):
            rb.SyncRequestBuilder.insert(MagicMock(path="employee_schedules"), {})
        assert piege.ECRITURES[-1].endswith("insert employee_schedules")
    finally:
        piege.retirer_le_piege()
    assert rb.SyncRequestBuilder.insert is original


def test_poser_deux_fois_ne_double_pas_le_piege():
    piege.poser_le_piege()
    piege.poser_le_piege()
    piege.retirer_le_piege()
    import postgrest._sync.request_builder as rb

    assert not getattr(rb.SyncRequestBuilder.insert, "_piege", False)
```

`backend/tests/unit/scripts/verification_rgdu/test_sans_nom.py` :
```python
"""Aucun nom de salarié ne doit sortir dans un fichier versionné."""
import pytest

from scripts.verification_rgdu import sans_nom

pytestmark = pytest.mark.unit


def test_un_nom_de_la_table_est_trouve(monkeypatch):
    monkeypatch.setattr(sans_nom, "_mots_interdits", lambda: {"DUPONTEL"})
    assert sans_nom.noms_trouves("Écart pour Dupontel en mars") == ["DUPONTEL"]


def test_un_texte_sans_nom_passe(monkeypatch):
    monkeypatch.setattr(sans_nom, "_mots_interdits", lambda: {"DUPONTEL"})
    assert sans_nom.noms_trouves("Écart pour le salarié A en mars") == []
```

- [ ] **Étape 2 : lancer les tests, ils doivent échouer**

Lancer : `env -u APP_ENV .venv/bin/python -m pytest -q -p no:faulthandler tests/unit/scripts/verification_rgdu`
Attendu : ÉCHEC (`ModuleNotFoundError: scripts.verification_rgdu`).

- [ ] **Étape 3 : écrire les modules**

`backend/scripts/verification_rgdu/__init__.py` :
```python
"""Vérification de la réduction générale (RGDU 2026) : Quadra, loi, EYWAI.

Voir docs/superpowers/specs/2026-09-29-verification-reduction-generale-design.md.
Aucune écriture en base : tout calcul du moteur passe par le bac à sable, piège posé.
"""
```

`backend/scripts/verification_rgdu/chemins.py` :
```python
"""Où sont les données, où vont les rapports, quelles sociétés et quels mois."""
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
DATA = RACINE / "data"
RAPPORT = DATA / "_rapports" / "rgdu-2026"
TEXTES = RACINE / "docs" / "reference" / "reduction-generale-2026"
ANNEE = 2026

SOCIETES: dict[str, dict] = {
    "colorplast": {"company_id": "dbe2b9f5-44dd-41bc-a625-36ed33d160f7", "mois": tuple(range(1, 9)), "dossier": "colorplast"},
    "comitech": {"company_id": "12cd8c71-da13-43f9-9151-475c4d5e8812", "mois": tuple(range(1, 9)), "dossier": "comitech"},
    # company_id de Mont-Blanc : lu en base à la tâche 8 (lecture seule), laissé à None ici.
    "mbc": {"company_id": None, "mois": tuple(range(1, 8)), "dossier": "mbc"},
}
```

`backend/scripts/verification_rgdu/piege.py` :
```python
"""Piège à écritures : toute écriture postgrest ou storage lève EcritureInterdite.

À poser AVANT d'importer l'application. Réversible, pour que les tests ne fuient pas.
"""
from __future__ import annotations

ECRITURES: list[str] = []
_ORIGINAUX: dict[tuple[type, str], object] = {}


class EcritureInterdite(RuntimeError):
    """Une vérification a tenté d'écrire : rien n'est parti."""


def _cibles():
    import postgrest._sync.request_builder as rb
    import storage3._sync.file_api as fa

    return [(rb.SyncRequestBuilder, n) for n in ("insert", "update", "upsert", "delete")] + [
        (fa.SyncBucketActionsMixin, n) for n in ("upload", "update", "remove", "move", "copy")
    ]


def poser_le_piege() -> None:
    for cls, nom in _cibles():
        if (cls, nom) in _ORIGINAUX:
            continue
        _ORIGINAUX[(cls, nom)] = getattr(cls, nom)

        def piege(self, *a, _nom=nom, _cls=cls, **k):
            cible = str(getattr(self, "path", None) or getattr(self, "id", None) or "")
            ECRITURES.append(f"{_cls.__name__}.{_nom} {cible.split('/')[-1]}".replace(f"{_cls.__name__}.", ""))
            raise EcritureInterdite(f"écriture interdite : {_cls.__name__}.{_nom} ({cible})")

        piege._piege = True
        setattr(cls, nom, piege)


def retirer_le_piege() -> None:
    for (cls, nom), original in list(_ORIGINAUX.items()):
        setattr(cls, nom, original)
        del _ORIGINAUX[(cls, nom)]
```

`backend/scripts/verification_rgdu/sans_nom.py` :
```python
"""Garde : un fichier destiné à git ne contient aucun nom de salarié (table des pseudonymes)."""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from functools import lru_cache

from scripts.verification_rgdu.chemins import DATA


def _norme(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()


@lru_cache(maxsize=1)
def _mots_interdits() -> frozenset[str]:
    table = json.loads((DATA / "_outils" / "pseudonymes.json").read_text(encoding="utf-8"))
    return frozenset(m for cle in table for m in _norme(cle).split() if len(m) >= 4)


def noms_trouves(texte: str) -> list[str]:
    t = _norme(texte)
    return sorted(m for m in _mots_interdits() if re.search(rf"\b{re.escape(m)}\b", t))


if __name__ == "__main__":
    fautes = {f: noms_trouves(open(f, encoding="utf-8").read()) for f in sys.argv[1:]}
    fautes = {f: n for f, n in fautes.items() if n}
    print(fautes or "aucun nom")
    sys.exit(1 if fautes else 0)
```

- [ ] **Étape 4 : lancer les tests, ils doivent passer**

Lancer : `env -u APP_ENV .venv/bin/python -m pytest -q -p no:faulthandler tests/unit/scripts/verification_rgdu`
Attendu : 4 réussis.

- [ ] **Étape 5 : préparer la demande de données (texte pour Alexandre, sans rien envoyer)**

Écrire `data/_rapports/rgdu-2026/demande-donnees.md` :
```markdown
Pour Gaëlle (à envoyer par Alexandre) :
1. Les DSN de juillet et d'août 2026 de Colorplast, Comitech et Mont-Blanc (fichiers .dsn déposés chez net-entreprises).
2. Quand un salarié a une absence non payée, sur quelles heures Quadra calcule-t-il la réduction ? (exemple : janvier, 3,14 h d'absence, Quadra retient 165,64 h au lieu de 165,50)
3. En juin, Quadra a pris le SMIC à 12,02 pour certains salariés et 12,31 pour d'autres : y a-t-il eu une régularisation en juillet ou août ?
4. Les conventions de forfait jours (216 jours) des cadres de Comitech.
```

- [ ] **Étape 6 : commit**

```bash
cd /Users/alex/dev/EYWAI/backend && PYTHONPATH=. .venv/bin/python -m scripts.verification_rgdu.sans_nom scripts/verification_rgdu/*.py tests/unit/scripts/verification_rgdu/*.py
git add scripts/verification_rgdu tests/unit/scripts/verification_rgdu
git commit -m "chore(verification-rgdu): squelette, piège à écritures et garde anti-noms"
```
Attendu de `sans_nom` : « aucun nom ». La même commande précède chaque commit des tâches suivantes.

---

### Tâche 1 : textes officiels et tableau des règles

**Fichiers :**
- Créer : `docs/reference/reduction-generale-2026/README.md` (index), un fichier par texte, et `regles.md`.

**Interfaces :**
- Produit : `regles.md`, un tableau `| ID | Règle | Texte | Article | URL | Consulté le |`. Les ID utilisés plus loin sont R-F1 (paramètres et arrondi), R-F2 (SMIC figé), R-F3 (effectif), R-F4 (par contrat), R-H1 à R-H12, R-B1, R-A1 à R-A3 et R-D2 (part Agirc-Arrco).

- [ ] **Étape 1 : récupérer les textes en entier.** Utiliser l'outil de lecture web (WebFetch ou Firecrawl) et copier l'extrait intégral utile, pas un résumé :
  - URSSAF : « Réduction générale des cotisations patronales » (fiche RGDU 2026, calcul du coefficient, SMIC de référence, cas des absences, forfait jours, entrée ou sortie) ;
  - BOSS (boss.gouv.fr), rubrique « Allègements généraux », sections formule, rémunération prise en compte, SMIC de référence, cas particuliers, régularisation ;
  - Légifrance : CSS L241-13 ; D241-7, D241-8, D241-9, D241-10 dans leur version 2026 ; décret fixant les paramètres RGDU 2026 (le code cite 2025-887, le référentiel d'audit 2025-1446 : lire les deux et noter lequel fixe quoi) ; décret 2026-509 du 12/06/2026 (SMIC de référence figé) ;
  - net-entreprises : fiches DSN sur le bloc S21.G00.79 (composant 01 « SMIC retenu ») et la répartition 018 / 106.

  Chaque fichier commence ainsi :
  ```markdown
  # <titre officiel>
  Source : <URL> — consulté le <JJ/MM/AAAA>
  ```

- [ ] **Étape 2 : écrire `regles.md`.** Une ligne par règle et par ID, avec la citation courte de l'article. Pour chaque règle H, répondre explicitement à « heures ou SMIC retenus, et comment ».
- [ ] **Étape 3 : lister les contradictions.** Ajouter une section « Points non tranchés par les textes » dans `regles.md`, où chaque point indique le montant qui en dépend.
- [ ] **Étape 4 : commit.**
```bash
git add docs/reference/reduction-generale-2026
git commit -m "docs(reference): textes officiels de la réduction générale 2026 et tableau des règles"
```

---

### Tâche 2 : calcul de référence — la formule

**Fichiers :**
- Créer : `backend/scripts/verification_rgdu/oracle.py`
- Test : `backend/tests/unit/scripts/verification_rgdu/test_oracle.py`

**Interfaces :**
- Consomme : `regles.md` (R-F1). Si le texte contredit une valeur ci-dessous, corriger la valeur ET le test avant de passer à la suite.
- Produit :
  - `Parametres(tmin=0.02, tdelta=0.3781, p=1.75, point_sortie=3.0)`, avec `Parametres.tmax -> float` ;
  - `coefficient(brut_cumule: float, smic_cumule: float, prm: Parametres) -> float` ;
  - `reduction_cumulee(brut_cumule, smic_cumule, prm) -> float` ;
  - `reduction_du_mois(brut_prec, smic_prec, deja_appliquee, brut_mois, smic_mois, prm) -> float` ;
  - `smic_pour_reduction(brut_cumule, reduction_voulue, prm) -> float`, qui retrouve par dichotomie le SMIC cumulé redonnant une réduction.

- [ ] **Étape 1 : tests qui échouent**
```python
"""Formule RGDU 2026 écrite depuis les textes (R-F1), vérifiée sur une DSN réelle anonymisée."""
import pytest

from scripts.verification_rgdu.oracle import (
    Parametres, coefficient, reduction_cumulee, reduction_du_mois, smic_pour_reduction,
)

pytestmark = pytest.mark.unit
P = Parametres()


def test_au_smic_le_coefficient_vaut_tmax():
    assert coefficient(1823.03, 1823.03, P) == 0.3981


def test_a_trois_smic_et_au_dela_rien():
    assert coefficient(3 * 1823.03, 1823.03, P) == 0.0
    assert coefficient(6000.0, 1823.03, P) == 0.0


def test_une_dsn_quadra_de_janvier_est_retrouvee_au_centime():
    """Salarié A, Colorplast, janvier 2026 : assiette 3 023,40, SMIC retenu 2 277,75,
    réduction déclarée 483,87 (018) + 86,04 (106) = 569,91."""
    assert coefficient(3023.40, 2277.75, P) == 0.1885
    assert reduction_cumulee(3023.40, 2277.75, P) == 569.91


def test_la_reduction_du_mois_est_la_regularisation_de_l_annee():
    jan = reduction_cumulee(3000.0, 2300.0, P)
    fev = reduction_du_mois(3000.0, 2300.0, jan, 3100.0, 2250.0, P)
    assert round(jan + fev, 2) == reduction_cumulee(6100.0, 4550.0, P)


def test_le_smic_implicite_redonne_la_reduction():
    smic = smic_pour_reduction(3023.40, 569.91, P)
    assert abs(smic - 2277.75) < 0.5
```

- [ ] **Étape 2 : lancer, échec attendu**

Lancer : `env -u APP_ENV .venv/bin/python -m pytest -q -p no:faulthandler tests/unit/scripts/verification_rgdu/test_oracle.py`
Attendu : ÉCHEC (module absent).

- [ ] **Étape 3 : écrire `oracle.py`**
```python
"""Formule de la réduction générale 2026 (RGDU), écrite depuis les textes (regles.md, R-F1).

Indépendante du moteur : ne rien importer de app/.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Parametres:
    tmin: float = 0.02
    tdelta: float = 0.3781        # moins de 50 salariés ; 0.3821 à partir de 50
    p: float = 1.75
    point_sortie: float = 3.0     # en SMIC

    @property
    def tmax(self) -> float:
        return round(self.tmin + self.tdelta, 4)


def coefficient(brut_cumule: float, smic_cumule: float, prm: Parametres) -> float:
    if brut_cumule <= 0 or smic_cumule <= 0:
        return 0.0
    if round(brut_cumule, 2) >= round(prm.point_sortie * smic_cumule, 2):
        return 0.0
    crochet = 0.5 * (prm.point_sortie * smic_cumule / brut_cumule - 1)
    return round(min(prm.tmin + prm.tdelta * crochet ** prm.p, prm.tmax), 4)


def reduction_cumulee(brut_cumule: float, smic_cumule: float, prm: Parametres) -> float:
    return round(brut_cumule * coefficient(brut_cumule, smic_cumule, prm), 2)


def reduction_du_mois(brut_prec: float, smic_prec: float, deja_appliquee: float,
                      brut_mois: float, smic_mois: float, prm: Parametres) -> float:
    return round(reduction_cumulee(brut_prec + brut_mois, smic_prec + smic_mois, prm) - deja_appliquee, 2)


def smic_pour_reduction(brut_cumule: float, reduction_voulue: float, prm: Parametres) -> float:
    """Le SMIC cumulé qui redonne `reduction_voulue` (positive) sur ce brut : dichotomie."""
    lo, hi = 0.0, brut_cumule * 2
    for _ in range(100):
        mid = (lo + hi) / 2
        if brut_cumule * coefficient(brut_cumule, mid, prm) < reduction_voulue:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 2)
```

- [ ] **Étape 4 : lancer, succès attendu.** 5 réussis.
- [ ] **Étape 5 : commit.** `git add` les deux fichiers ; message « feat(verification-rgdu): formule RGDU de référence, retrouvée sur une DSN Quadra ».

---

### Tâche 3 : calcul de référence — SMIC de référence du mois, règle par règle

**Fichiers :**
- Créer : `backend/scripts/verification_rgdu/oracle_smic.py`
- Test : `backend/tests/unit/scripts/verification_rgdu/test_oracle_smic.py`

**Interfaces :**
- Consomme : `regles.md` (R-H1 à R-H12). Chaque fonction cite son ID. Si le texte tranche autrement, corriger la fonction et son test.
- Produit (SMIC en euros ; `smic_h = 12.02` par défaut) :
  - `smic_mensuel(smic_h=12.02) -> float` : `round(smic_h * 1820 / 12, 2)`, soit 1823,03 ;
  - `smic_mois_complet(duree_mensuelle_contrat, heures_sup, heures_comp, smic_h=12.02) -> float` (R-H1, R-H8) ;
  - `smic_absence_non_payee(smic_complet, heures_absence, heures_prevues, variante: str, smic_h=12.02) -> float` (R-H3), avec deux variantes, `"soustraction"` et `"proportion"` ;
  - `smic_suspension_avec_paiement(smic_complet, remuneration_versee, remuneration_sans_suspension) -> float` (R-H4, R-H5) ;
  - `smic_forfait_jours(jours_forfait, jours_absence_non_payes=0.0, smic_h=12.02) -> float` (R-H9) ;
  - `smic_entree_sortie(smic_complet, heures_dues, heures_du_mois) -> float` (R-H7).

- [ ] **Étape 1 : tests qui échouent**
```python
"""SMIC de référence du mois : une règle, un cas, une source (regles.md)."""
import pytest

from scripts.verification_rgdu.oracle_smic import (
    smic_absence_non_payee, smic_entree_sortie, smic_forfait_jours, smic_mensuel,
    smic_mois_complet, smic_suspension_avec_paiement,
)

pytestmark = pytest.mark.unit


def test_r_h1_mois_complet_avec_heures_sup_comme_quadra_en_dsn():
    """Salarié A, janvier 2026 : 1 823,03 + 37,83 h × 12,02 = 2 277,75 (DSN S21.G00.79 type 01)."""
    assert smic_mensuel() == 1823.03
    assert smic_mois_complet(151.67, 37.83, 0.0) == 2277.75


def test_r_h8_temps_partiel_au_prorata_de_la_duree_du_contrat():
    assert smic_mois_complet(121.33, 0.0, 4.0) == round(12.02 * 121.33 + 12.02 * 4.0, 2)


def test_r_h3_absence_non_payee_deux_variantes():
    complet = smic_mois_complet(151.67, 17.33, 0.0)
    assert smic_absence_non_payee(complet, 7.0, 169.0, "soustraction") == round(complet - 7.0 * 12.02, 2)
    assert smic_absence_non_payee(complet, 7.0, 169.0, "proportion") == round(complet * (1 - 7.0 / 169.0), 2)


def test_r_h4_suspension_au_rapport_de_la_remuneration_versee():
    assert smic_suspension_avec_paiement(1823.03, 1200.0, 2400.0) == round(1823.03 * 0.5, 2)
    assert smic_suspension_avec_paiement(1823.03, 2400.0, 2400.0) == 1823.03


def test_r_h9_forfait_216_jours():
    """151,67 × 216 / 218 = 150,28 h par mois, soit 1 806,31 € de SMIC."""
    assert smic_forfait_jours(216) == round(1823.03 * 216 / 218, 2)


def test_r_h7_entree_en_cours_de_mois_au_prorata():
    assert smic_entree_sortie(1823.03, 47.5, 151.67) == round(1823.03 * 47.5 / 151.67, 2)
```

- [ ] **Étape 2 : lancer, échec attendu.**
- [ ] **Étape 3 : écrire `oracle_smic.py`**
```python
"""SMIC de référence du mois, règle par règle (docs/reference/reduction-generale-2026/regles.md).

Les variantes existent là où les textes ou Quadra laissent un doute ; le rejeu (tâche 7)
dit laquelle reproduit la DSN de Quadra, et regles.md dit laquelle est légale.
"""
from __future__ import annotations

SMIC_H_2026 = 12.02   # R-F2 : SMIC de référence figé (décret 2026-509)


def smic_mensuel(smic_h: float = SMIC_H_2026) -> float:
    return round(smic_h * 1820 / 12, 2)


def smic_mois_complet(duree_mensuelle_contrat: float, heures_sup: float, heures_comp: float,
                      smic_h: float = SMIC_H_2026) -> float:
    """R-H1 / R-H8 : SMIC mensuel (au prorata du contrat s'il est inférieur à la durée légale),
    plus les heures sup et complémentaires au taux normal."""
    legal = 1820 / 12
    base = smic_mensuel(smic_h) if duree_mensuelle_contrat >= legal - 0.01 else smic_h * duree_mensuelle_contrat
    return round(base + smic_h * (heures_sup + heures_comp), 2)


def smic_absence_non_payee(smic_complet: float, heures_absence: float, heures_prevues: float,
                           variante: str, smic_h: float = SMIC_H_2026) -> float:
    """R-H3. « soustraction » : on retire les heures au SMIC horaire ; « proportion » : on réduit
    le SMIC du mois au prorata des heures prévues."""
    if variante == "soustraction":
        return round(smic_complet - heures_absence * smic_h, 2)
    if variante == "proportion":
        return round(smic_complet * (1 - heures_absence / heures_prevues), 2)
    raise ValueError(variante)


def smic_suspension_avec_paiement(smic_complet: float, remuneration_versee: float,
                                  remuneration_sans_suspension: float) -> float:
    """R-H4 / R-H5 : suspension du contrat avec paiement total ou partiel : SMIC au rapport de
    la rémunération versée sur celle qui aurait été versée sans suspension."""
    if remuneration_sans_suspension <= 0:
        return 0.0
    return round(smic_complet * min(1.0, remuneration_versee / remuneration_sans_suspension), 2)


def smic_forfait_jours(jours_forfait: float, jours_absence_non_payes: float = 0.0,
                       smic_h: float = SMIC_H_2026) -> float:
    """R-H9 : SMIC mensuel × jours du forfait / 218, réduit des jours non payés."""
    mensuel = smic_mensuel(smic_h) * jours_forfait / 218
    if jours_absence_non_payes:
        mensuel *= 1 - jours_absence_non_payes / (jours_forfait / 12)
    return round(mensuel, 2)


def smic_entree_sortie(smic_complet: float, heures_dues: float, heures_du_mois: float) -> float:
    """R-H7 : mois incomplet, SMIC au prorata des heures dues sur la période de contrat."""
    return round(smic_complet * heures_dues / heures_du_mois, 2)
```

- [ ] **Étape 4 : lancer, succès attendu.** 6 réussis.
- [ ] **Étape 5 : commit.** Message « feat(verification-rgdu): SMIC de référence du mois, règle par règle ».

---

### Tâche 4 : lecture des DSN Quadra

**Fichiers :**
- Créer : `backend/scripts/verification_rgdu/dsn_quadra.py`
- Test : `backend/tests/unit/scripts/verification_rgdu/test_dsn_quadra.py`

**Interfaces :**
- Produit :
  - `@dataclass BaseReduction(nir: str, nom: str, prenom: str, debut: date, fin: date, assiette: float | None, smic_retenu: float | None, montant_018: float, montant_106: float)`, avec `reduction -> float` qui vaut `-(montant_018 + montant_106)`, positive pour un allègement ;
  - `lire_dsn(chemin: Path) -> list[BaseReduction]` : un élément par bloc S21.G00.78 de type `03` (assiette brute), dans l'ordre du fichier ;
  - `dsn_du_mois(societe: str, mois: int) -> list[BaseReduction]`, qui lit `data/<dossier>/dsn/2026-MM.dsn` et renvoie `[]` si le fichier est absent.

- [ ] **Étape 1 : test qui échoue** (DSN synthétique, avec les vraies valeurs d'une ligne anonymisée)
```python
"""Lecture du SMIC retenu et des codes 018 / 106 d'une DSN Quadra (latin-1, CRLF)."""
from datetime import date

import pytest

from scripts.verification_rgdu.dsn_quadra import lire_dsn

pytestmark = pytest.mark.unit

DSN = (
    "S20.G00.05.005,'01012026'\r\n"
    "S21.G00.30.001,'1999999999999'\r\nS21.G00.30.002,'ESSAI'\r\nS21.G00.30.004,'Léa'\r\n"
    "S21.G00.78.001,'02'\r\nS21.G00.78.002,'01012026'\r\nS21.G00.78.003,'31012026'\r\nS21.G00.78.004,'3023.40'\r\n"
    "S21.G00.81.001,'076'\r\nS21.G00.81.004,'400.00'\r\n"
    "S21.G00.78.001,'03'\r\nS21.G00.78.002,'01012026'\r\nS21.G00.78.003,'31012026'\r\nS21.G00.78.004,'3023.40'\r\n"
    "S21.G00.79.001,'01'\r\nS21.G00.79.004,'2277.75'\r\nS21.G00.79.001,'04'\r\nS21.G00.79.004,'29.23'\r\n"
    "S21.G00.81.001,'018'\r\nS21.G00.81.003,'3023.40'\r\nS21.G00.81.004,'-483.87'\r\n"
    "S21.G00.81.001,'106'\r\nS21.G00.81.003,'3023.40'\r\nS21.G00.81.004,'-86.04'\r\n"
    "S21.G00.81.001,'114'\r\nS21.G00.81.004,'-10.00'\r\n"
)


def test_une_base_03_donne_le_smic_retenu_et_la_reduction(tmp_path):
    f = tmp_path / "2026-01.dsn"
    f.write_bytes(DSN.encode("latin-1"))
    [b] = lire_dsn(f)
    assert (b.nir, b.nom, b.prenom) == ("1999999999999", "ESSAI", "Léa")
    assert (b.debut, b.fin) == (date(2026, 1, 1), date(2026, 1, 31))
    assert b.smic_retenu == 2277.75 and b.assiette == 3023.40
    assert b.reduction == 569.91
```

- [ ] **Étape 2 : lancer, échec attendu.**
- [ ] **Étape 3 : écrire `dsn_quadra.py`**
```python
"""DSN Quadra : SMIC retenu (S21.G00.79 type 01) et réduction (codes 018 + 106) par base brute."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from scripts.verification_rgdu.chemins import ANNEE, DATA, SOCIETES

LIGNE = re.compile(r"^(S\d\d\.G\d\d\.\d\d\.\d{3}),'(.*)'\s*$")


@dataclass
class BaseReduction:
    nir: str
    nom: str
    prenom: str
    debut: date
    fin: date
    assiette: float | None = None
    smic_retenu: float | None = None
    montant_018: float = 0.0
    montant_106: float = 0.0

    @property
    def reduction(self) -> float:
        return round(-(self.montant_018 + self.montant_106), 2)


def _date(s: str) -> date:
    return datetime.strptime(s, "%d%m%Y").date()


def lire_dsn(chemin: Path) -> list[BaseReduction]:
    bases: list[BaseReduction] = []
    individu = {"nir": "", "nom": "", "prenom": ""}
    type_base = composant = code = None
    periode: list[str] = []
    courante: BaseReduction | None = None
    for brute in chemin.read_bytes().decode("latin-1").splitlines():
        m = LIGNE.match(brute.strip())
        if not m:
            continue
        rub, val = m.groups()
        if rub == "S21.G00.30.001":
            individu = {"nir": val[:13], "nom": "", "prenom": ""}
            courante = None
        elif rub == "S21.G00.30.002":
            individu["nom"] = val
        elif rub == "S21.G00.30.004":
            individu["prenom"] = val
        elif rub == "S21.G00.78.001":
            type_base, periode, courante = val, [], None
        elif rub in ("S21.G00.78.002", "S21.G00.78.003"):
            periode.append(val)
            if type_base == "03" and len(periode) == 2:
                courante = BaseReduction(debut=_date(periode[0]), fin=_date(periode[1]), **individu)
                bases.append(courante)
        elif rub == "S21.G00.78.004" and courante is not None:
            courante.assiette = float(val)
        elif rub == "S21.G00.79.001":
            composant = val
        elif rub == "S21.G00.79.004" and courante is not None and composant == "01":
            courante.smic_retenu = float(val)
        elif rub == "S21.G00.81.001":
            code = val
        elif rub == "S21.G00.81.004" and courante is not None and code in ("018", "106"):
            if code == "018":
                courante.montant_018 += float(val)
            else:
                courante.montant_106 += float(val)
    return bases


def dsn_du_mois(societe: str, mois: int) -> list[BaseReduction]:
    chemin = DATA / SOCIETES[societe]["dossier"] / "dsn" / f"{ANNEE:04d}-{mois:02d}.dsn"
    return lire_dsn(chemin) if chemin.exists() else []
```

- [ ] **Étape 4 : lancer, succès attendu.**
- [ ] **Étape 5 : contrôle sur les vraies DSN (sans commit de sortie).** Lancer :
```bash
PYTHONPATH=. .venv/bin/python -c "
from scripts.verification_rgdu.dsn_quadra import dsn_du_mois
for s in ('colorplast','comitech','mbc'):
    for m in range(1,7):
        b = dsn_du_mois(s, m); print(s, m, len(b), sum(x.smic_retenu is not None for x in b), round(sum(x.reduction for x in b),2))"
```
Attendu : des bases à chaque mois de janvier à juin pour les trois sociétés. Comitech en janvier : SMIC retenu présent, réduction à 0.
- [ ] **Étape 6 : commit.** Message « feat(verification-rgdu): lecture du SMIC retenu et des codes 018/106 des DSN Quadra ».

---

### Tâche 5 : éléments du mois tirés des bulletins Quadra

**Fichiers :**
- Créer : `backend/scripts/verification_rgdu/quadra_mois.py`
- Test : `backend/tests/unit/scripts/verification_rgdu/test_quadra_mois.py`

**Interfaces :**
- Consomme : `scripts.backtest.colorplast_lignes_quadra.lire_bulletins(annee, mois, societe) -> dict[str, Bulletin]`, avec `Bulletin.lignes: list[Ligne(code, libelle, base, taux, montant_sal, gain, montant_pat)]`, `Bulletin.droite["cumul_heures"|"cumul_bruts"]` et `Bulletin.infos["nir"]`. Consomme aussi `scripts.reprise_colorplast_solde_ouverture.EST_REDUCTION_GENERALE` et `_somme_des_lignes`.
- Produit :
  - `@dataclass MoisQuadra(societe, mois, matricule, nir, brut_mois, cumul_bruts, cumul_heures, heures_mois, reduction_mois, absences: list[Absence], maintien: float, forfait_jours: int | None, entree: str | None, sortie: str | None)` ;
  - `@dataclass Absence(nature: str, libelle: str, heures: float | None, montant: float | None)`, avec pour `nature` l'une des valeurs `"maladie"`, `"non_payee"`, `"injustifiee"`, `"sans_solde"`, `"evenement_familial"`, `"paternite"`, `"conges_payes"`, `"autre"` ;
  - `elements_du_mois(bulletins_du_mois: dict, bulletins_mois_prec: dict | None, societe: str, mois: int) -> list[MoisQuadra]` ;
  - `lire_societe(societe: str) -> dict[tuple[str, int], MoisQuadra]`, indexé par `(nir, mois)`.

- [ ] **Étape 1 : test qui échoue** (bulletin synthétique, avec des libellés Quadra réels)
```python
"""Les éléments du mois utiles à la réduction, lus sur un bulletin Quadra."""
import pytest

from scripts.backtest.colorplast_lignes_quadra import Bulletin, Ligne
from scripts.verification_rgdu.quadra_mois import elements_du_mois

pytestmark = pytest.mark.unit


def _b(lignes, cumul_h, cumul_b, **infos):
    b = Bulletin(matricule="ESSAI")
    b.lignes, b.droite, b.infos = lignes, {"cumul_heures": cumul_h, "cumul_bruts": cumul_b}, {"nir": "1999999999999", **infos}
    return b


def test_un_mois_d_arret_avec_maintien():
    fev = _b([Ligne(None, "SALAIRE BRUT", gain=2400.0)], 169.0, 2400.0)
    mars = _b([
        Ligne(None, "SALAIRE DE BASE", base=151.67, gain=1900.0),
        Ligne(None, "Absence maladie 160326-280326", base=70.0, montant_sal=877.0),
        Ligne(None, "Maintien de salaire", gain=310.78),
        Ligne(None, "SALAIRE BRUT", gain=1609.96),
        Ligne(None, "EXO., ECRET. ET ALLEG. COTIS", base=-419.16, montant_pat=-419.16),
    ], 259.0, 4009.96)
    [m] = elements_du_mois({"ESSAI": mars}, {"ESSAI": fev}, "colorplast", 3)
    assert (m.brut_mois, m.heures_mois, m.reduction_mois, m.maintien) == (1609.96, 90.0, 419.16, 310.78)
    assert [(a.nature, a.heures) for a in m.absences] == [("maladie", 70.0)]


def test_forfait_jours_et_absence_non_payee():
    b = _b([
        Ligne(None, "Forfait 216 jours"),
        Ligne(None, "Abs. Abs aut nonpayé 130126", base=2.24, montant_sal=30.0),
        Ligne(None, "SALAIRE BRUT", gain=3750.0),
    ], 0.0, 3750.0)
    [m] = elements_du_mois({"ESSAI": b}, None, "comitech", 1)
    assert m.forfait_jours == 216
    assert [(a.nature, a.heures) for a in m.absences] == [("non_payee", 2.24)]
```

- [ ] **Étape 2 : lancer, échec attendu.**
- [ ] **Étape 3 : écrire `quadra_mois.py`**
```python
"""Éléments du mois utiles à la réduction, tirés des bulletins Quadra (PDF)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from scripts.backtest.colorplast_lignes_quadra import lire_bulletins
from scripts.reprise_colorplast_solde_ouverture import EST_REDUCTION_GENERALE, _somme_des_lignes
from scripts.verification_rgdu.chemins import ANNEE, SOCIETES

NATURES = [
    ("maladie", re.compile(r"ABSENCE\s+MALADIE|ACCIDENT|ARR[EÊ]T", re.I)),
    ("paternite", re.compile(r"PATERNIT|MATERNIT", re.I)),
    ("evenement_familial", re.compile(r"EVT\s+FAMIL", re.I)),
    ("injustifiee", re.compile(r"INJUSTIFI", re.I)),
    ("sans_solde", re.compile(r"S\.?\s*SOL", re.I)),
    ("non_payee", re.compile(r"NON\s*PAY", re.I)),
    ("conges_payes", re.compile(r"H\.?\s*ABSENCE\s+CONG", re.I)),
]
EST_ABSENCE = re.compile(r"^ABS|ABSENCE|MALADIE|PATERNIT", re.I)
EST_MAINTIEN = re.compile(r"MAINTIEN", re.I)
FORFAIT = re.compile(r"FORFAIT\s+(\d{2,3})\s+JOURS", re.I)
ENTREE = re.compile(r"ENTREE\s+LE\s+([\d/.-]+)", re.I)
SORTIE = re.compile(r"SORTIE\s+LE\s+([\d/.-]+)", re.I)


@dataclass
class Absence:
    nature: str
    libelle: str
    heures: float | None
    montant: float | None


@dataclass
class MoisQuadra:
    societe: str
    mois: int
    matricule: str
    nir: str
    brut_mois: float
    cumul_bruts: float
    cumul_heures: float
    heures_mois: float
    reduction_mois: float
    absences: list[Absence] = field(default_factory=list)
    maintien: float = 0.0
    forfait_jours: int | None = None
    entree: str | None = None
    sortie: str | None = None


def _nature(libelle: str) -> str:
    return next((n for n, motif in NATURES if motif.search(libelle)), "autre")


def _brut(b) -> float:
    return next((round(l.gain, 2) for l in b.lignes if l.libelle.strip().upper() == "SALAIRE BRUT" and l.gain is not None), 0.0)


def elements_du_mois(bulletins: dict, precedents: dict | None, societe: str, mois: int) -> list[MoisQuadra]:
    sortie: list[MoisQuadra] = []
    for mat, b in sorted(bulletins.items()):
        prec = (precedents or {}).get(mat)
        cumul_h = float(b.droite.get("cumul_heures") or 0.0)
        h_prec = float(prec.droite.get("cumul_heures") or 0.0) if prec else 0.0
        m = MoisQuadra(
            societe=societe, mois=mois, matricule=mat, nir=str(b.infos.get("nir") or "")[:13],
            brut_mois=_brut(b), cumul_bruts=float(b.droite.get("cumul_bruts") or 0.0),
            cumul_heures=cumul_h, heures_mois=round(cumul_h - h_prec, 2),
            reduction_mois=round(-_somme_des_lignes(b, EST_REDUCTION_GENERALE), 2),
        )
        for l in b.lignes:
            lib = l.libelle.strip()
            if f := FORFAIT.search(lib):
                m.forfait_jours = int(f.group(1))
            if e := ENTREE.search(lib):
                m.entree = e.group(1)
            if s := SORTIE.search(lib):
                m.sortie = s.group(1)
            if EST_MAINTIEN.search(lib) and l.gain:
                m.maintien = round(m.maintien + l.gain, 2)
            elif EST_ABSENCE.search(lib) or _nature(lib) != "autre":
                m.absences.append(Absence(_nature(lib), lib, l.base, l.montant_sal))
        sortie.append(m)
    return sortie


def lire_societe(societe: str) -> dict[tuple[str, int], MoisQuadra]:
    lus = {m: lire_bulletins(ANNEE, m, SOCIETES[societe]["dossier"]) for m in SOCIETES[societe]["mois"]}
    index: dict[tuple[str, int], MoisQuadra] = {}
    for m in SOCIETES[societe]["mois"]:
        for mq in elements_du_mois(lus[m], lus.get(m - 1), societe, m):
            index[(mq.nir or mq.matricule, m)] = mq
    return index
```

- [ ] **Étape 4 : lancer, succès attendu.**
- [ ] **Étape 5 : contrôle sur les vrais PDF.** Lancer `PYTHONPATH=. .venv/bin/python -c "from scripts.verification_rgdu.quadra_mois import lire_societe; d=lire_societe('colorplast'); print(len(d)); print(sorted({a.libelle for m in d.values() for a in m.absences if a.nature=='autre'}))"`. Attendu : 52 lignes. Chaque libellé classé « autre » est ajouté à `NATURES`, avec un test, puis relancé jusqu'à ce que la liste ne contienne plus que des libellés réellement sans effet sur la réduction. Même chose pour `comitech` et `mbc`.
- [ ] **Étape 6 : commit.** Message « feat(verification-rgdu): éléments du mois lus sur les bulletins Quadra ».

---

### Tâche 6 : SMIC implicite de Quadra (juillet et août, sans DSN)

**Fichiers :**
- Créer : `backend/scripts/verification_rgdu/implicite.py`
- Test : `backend/tests/unit/scripts/verification_rgdu/test_implicite.py`

**Interfaces :**
- Consomme : `oracle.smic_pour_reduction`, `oracle.Parametres`, `quadra_mois.MoisQuadra`.
- Produit :
  - `smic_quadra_par_mois(mois_quadra: list[MoisQuadra], prm) -> dict[int, float]`, le SMIC du mois que Quadra a implicitement retenu. Il vaut la différence des SMIC cumulés qui redonnent sa réduction cumulée. Les mois où la réduction cumulée est nulle ne sont pas calculables.

- [ ] **Étape 1 : test qui échoue**
```python
import pytest

from scripts.verification_rgdu.implicite import smic_quadra_par_mois
from scripts.verification_rgdu.oracle import Parametres, reduction_cumulee
from scripts.verification_rgdu.quadra_mois import MoisQuadra

pytestmark = pytest.mark.unit
P = Parametres()


def _m(mois, brut_mois, cumul_bruts, reduction_mois):
    return MoisQuadra("colorplast", mois, "ESSAI", "1999999999999", brut_mois, cumul_bruts, 0.0, 0.0, reduction_mois)


def test_deux_mois_redonnent_les_smic_du_mois():
    r1 = reduction_cumulee(3000.0, 2300.0, P)
    r2 = reduction_cumulee(6100.0, 4550.0, P) - r1
    smic = smic_quadra_par_mois([_m(1, 3000.0, 3000.0, r1), _m(2, 3100.0, 6100.0, r2)], P)
    # Le coefficient arrondi à 4 décimales laisse un palier d'environ 0,4 € de SMIC par mois.
    assert abs(smic[1] - 2300.0) < 1.0 and abs(smic[2] - 2250.0) < 1.5
```

- [ ] **Étape 2 : lancer, échec attendu.**
- [ ] **Étape 3 : écrire `implicite.py`**
```python
"""SMIC que Quadra a implicitement retenu, reconstitué depuis sa réduction cumulée."""
from __future__ import annotations

from scripts.verification_rgdu.oracle import Parametres, smic_pour_reduction
from scripts.verification_rgdu.quadra_mois import MoisQuadra


def smic_quadra_par_mois(mois_quadra: list[MoisQuadra], prm: Parametres) -> dict[int, float]:
    resultat: dict[int, float] = {}
    reduction_cumulee = 0.0
    smic_prec: float | None = 0.0
    for m in sorted(mois_quadra, key=lambda x: x.mois):
        reduction_cumulee += m.reduction_mois
        if reduction_cumulee <= 0:
            smic_prec = None
            continue
        smic_cumule = smic_pour_reduction(m.cumul_bruts, reduction_cumulee, prm)
        if smic_prec is not None:
            resultat[m.mois] = round(smic_cumule - smic_prec, 2)
        smic_prec = smic_cumule
    return resultat
```

- [ ] **Étape 4 : lancer, succès attendu.**
- [ ] **Étape 5 : commit.** Message « feat(verification-rgdu): SMIC implicite de Quadra depuis sa réduction cumulée ».

---

### Tâche 7 : colonne EYWAI

**Fichiers :**
- Créer : `backend/scripts/verification_rgdu/colonne_eywai.py`
- Test : `backend/tests/unit/scripts/verification_rgdu/test_colonne_eywai.py`

**Interfaces :**
- Consomme : `data/_filet/colorplast-janvier-aout/reference.json`, un dictionnaire `"<employee_id>/<AAAA-MM>" -> {payslip_data, cumuls}`, dont `cumuls["cumuls"]["heures_remunerees"]` est cumulé. Pour le bac à sable : `payslip_generator_provider.generate_en_bac_a_sable(employee_id, annee, mois, cumuls_precedents) -> {"payslip_data", "cumuls", "warnings"}`.
- Produit :
  - `@dataclass MoisEywai(employee_id: str, mois: int, heures_reduction: float, smic: float, reduction_ligne: float | None, source: str)` ;
  - `depuis_le_filet(chemin: Path) -> dict[tuple[str, int], MoisEywai]` : heures du mois = différence de `heures_remunerees` cumulées, et SMIC = heures × 12,02 ;
  - `depuis_le_bac_a_sable(employee_id: str, mois: int, cumuls_precedents: dict) -> MoisEywai`, où `source="bac_a_sable"` et où le piège est posé par l'appelant.

- [ ] **Étape 1 : test qui échoue** (filet synthétique)
```python
import json

import pytest

from scripts.verification_rgdu.colonne_eywai import depuis_le_filet

pytestmark = pytest.mark.unit


def test_les_heures_du_mois_sont_la_difference_des_cumuls(tmp_path):
    def entree(h, rg):
        return {"payslip_data": {"structure_cotisations": {"bloc_allegements": [
            {"coti_id": "reduction_generale", "montant_patronal": rg}]}}, "cumuls": {"cumuls": {"heures_remunerees": h}}}
    f = tmp_path / "reference.json"
    f.write_text(json.dumps({"e1/2026-01": entree(159.13, -582.24), "e1/2026-02": entree(331.63, -600.0)}))
    d = depuis_le_filet(f)
    assert d[("e1", 1)].heures_reduction == 159.13
    assert d[("e1", 2)].heures_reduction == 172.5 and d[("e1", 2)].smic == round(172.5 * 12.02, 2)
    assert d[("e1", 2)].reduction_ligne == 600.0
```

- [ ] **Étape 2 : lancer, échec attendu.**
- [ ] **Étape 3 : écrire `colonne_eywai.py`**
```python
"""Ce que calcule EYWAI : heures et SMIC de référence du mois, ligne de réduction."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from scripts.verification_rgdu.oracle_smic import SMIC_H_2026


@dataclass
class MoisEywai:
    employee_id: str
    mois: int
    heures_reduction: float
    smic: float
    reduction_ligne: float | None
    source: str


def _ligne_rg(payslip_data: dict) -> float | None:
    for l in (payslip_data.get("structure_cotisations") or {}).get("bloc_allegements") or []:
        if l.get("coti_id") == "reduction_generale":
            return round(-float(l.get("montant_patronal") or 0.0), 2)
    return None


def depuis_le_filet(chemin: Path) -> dict[tuple[str, int], MoisEywai]:
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
    from app.modules.payslips.infrastructure.providers import payslip_generator_provider

    res = payslip_generator_provider.generate_en_bac_a_sable(employee_id, 2026, mois, cumuls_precedents)
    avant = float((cumuls_precedents.get("cumuls") or {}).get("heures_remunerees") or 0.0)
    apres = float(((res.get("cumuls") or {}).get("cumuls") or {}).get("heures_remunerees") or 0.0)
    h = round(apres - avant, 2)
    return MoisEywai(employee_id, mois, h, round(h * SMIC_H_2026, 2), _ligne_rg(res["payslip_data"]), "bac_a_sable")
```

- [ ] **Étape 4 : lancer, succès attendu.**
- [ ] **Étape 5 : essai du bac à sable sur un mois passé (décision de faisabilité, rien à commiter).**

  Script `data/_rapports/rgdu-2026/essai_bac_a_sable.py`, lancé depuis `backend/` avec `PYTHONPATH=.`. Il pose le piège d'abord, puis lit en base :
  - l'`employee_id` d'un salarié de Comitech ;
  - le `company_id` de Mont-Blanc (`companies.company_name ilike '%mont%blanc%'`) ;
  - les cumuls du mois 2 de Comitech en base.

  Il appelle ensuite `depuis_le_bac_a_sable(eid, 3, cumuls_mois_2)`.

  Décision, à écrire dans `data/_rapports/rgdu-2026/faisabilite.md` :
  - **Le calcul aboutit et les heures sont plausibles** : la colonne EYWAI de Comitech (et de Mont-Blanc si ses fiches et plannings existent en base) se fait mois par mois en bac à sable, avec les cumuls du mois précédent reconstruits depuis Quadra, soit `brut_total = cumul_bruts`, `heures_remunerees = SMIC implicite / 12,02` et `reduction_generale_patronale = −réduction cumulée`.
  - **Le calcul échoue** (fiche absente, planning absent, garde) : la colonne EYWAI de cette société vaut « non rejouable ». La règle d'EYWAI est alors jugée sur les cas de Colorplast et sur le septembre à blanc de la tâche 10. La cause exacte est notée.
- [ ] **Étape 6 : commit** du module et du test. Message « feat(verification-rgdu): colonne EYWAI depuis le filet et le bac à sable ».

---

### Tâche 8 : comparaison à trois colonnes et pré-classement

**Fichiers :**
- Créer : `backend/scripts/verification_rgdu/comparaison.py`
- Test : `backend/tests/unit/scripts/verification_rgdu/test_comparaison.py`

**Interfaces :**
- Consomme : `oracle.reduction_cumulee`, `oracle.Parametres`.
- Produit :
  - `@dataclass LigneComparee(societe, cle, mois, smic_quadra: float | None, source_quadra: str, smic_loi: float | None, smic_eywai: float | None, brut_cumule: float, smic_cumule_prec: float, preclassement: str = "", impact_quadra: float = 0.0, impact_eywai: float = 0.0)` ;
  - `impact_en_euros(brut_cumule, smic_cumule_prec, smic_mois_ref, smic_mois_autre, prm) -> float` : l'écart de réduction cumulée dû au seul SMIC du mois ;
  - `preclasser(l: LigneComparee, prm) -> str`, qui renvoie l'une des valeurs `"identique"`, `"arrondi"`, `"erreur_eywai"`, `"a_juger_quadra"`, `"a_juger_les_deux"`, `"donnee_manquante"`.

  Le classement final (`erreur_eywai`, `erreur_quadra`, `methode_legale_differente`, `donnee_manquante`, `arrondi`) se fait à la tâche 9, par relecture humaine.

- [ ] **Étape 1 : tests qui échouent**
```python
import pytest

from scripts.verification_rgdu.comparaison import LigneComparee, impact_en_euros, preclasser
from scripts.verification_rgdu.oracle import Parametres

pytestmark = pytest.mark.unit
P = Parametres()


def _l(q, loi, e):
    return LigneComparee("colorplast", "A", 3, q, "dsn", loi, e, 12000.0, 7000.0)


def test_trois_colonnes_egales():
    assert preclasser(_l(2000.0, 2000.0, 2000.0), P) == "identique"


def test_quadra_s_ecarte_de_la_loi_et_eywai_la_suit():
    assert preclasser(_l(2283.0, 2000.0, 2000.0), P) == "a_juger_quadra"


def test_eywai_s_ecarte_de_la_loi_et_quadra_la_suit():
    assert preclasser(_l(2000.0, 2000.0, 1700.0), P) == "erreur_eywai"


def test_sans_la_loi_on_ne_juge_pas():
    assert preclasser(_l(2000.0, None, 2000.0), P) == "donnee_manquante"


def test_l_impact_est_celui_du_seul_smic_du_mois():
    assert impact_en_euros(12000.0, 7000.0, 2000.0, 2000.0, P) == 0.0
    assert impact_en_euros(12000.0, 7000.0, 2000.0, 2283.0, P) > 0
```

- [ ] **Étape 2 : lancer, échec attendu.**
- [ ] **Étape 3 : écrire `comparaison.py`**
```python
"""Salarié × mois : SMIC de référence selon Quadra, la loi et EYWAI ; impact et pré-classement."""
from __future__ import annotations

from dataclasses import dataclass

from scripts.verification_rgdu.oracle import Parametres, reduction_cumulee

TOLERANCE_SMIC = round(0.5 * 12.02, 2)   # 0,5 h
TOLERANCE_EUROS = 1.0


@dataclass
class LigneComparee:
    societe: str
    cle: str
    mois: int
    smic_quadra: float | None
    source_quadra: str
    smic_loi: float | None
    smic_eywai: float | None
    brut_cumule: float
    smic_cumule_prec: float
    preclassement: str = ""
    impact_quadra: float = 0.0
    impact_eywai: float = 0.0


def impact_en_euros(brut_cumule: float, smic_cumule_prec: float, smic_mois_ref: float,
                    smic_mois_autre: float, prm: Parametres) -> float:
    ref = reduction_cumulee(brut_cumule, smic_cumule_prec + smic_mois_ref, prm)
    autre = reduction_cumulee(brut_cumule, smic_cumule_prec + smic_mois_autre, prm)
    return round(autre - ref, 2)


def _ecart(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else abs(a - b)


def preclasser(l: LigneComparee, prm: Parametres) -> str:
    if l.smic_loi is None or l.smic_quadra is None:
        return "donnee_manquante"
    l.impact_quadra = impact_en_euros(l.brut_cumule, l.smic_cumule_prec, l.smic_loi, l.smic_quadra, prm)
    if l.smic_eywai is not None:
        l.impact_eywai = impact_en_euros(l.brut_cumule, l.smic_cumule_prec, l.smic_loi, l.smic_eywai, prm)
    q_ok = _ecart(l.smic_quadra, l.smic_loi) <= TOLERANCE_SMIC and abs(l.impact_quadra) <= TOLERANCE_EUROS
    e = _ecart(l.smic_eywai, l.smic_loi)
    e_ok = e is None or (e <= TOLERANCE_SMIC and abs(l.impact_eywai) <= TOLERANCE_EUROS)
    if q_ok and e_ok:
        exact = _ecart(l.smic_quadra, l.smic_loi) < 0.01 and (e is None or e < 0.01)
        return "identique" if exact else "arrondi"
    if not q_ok and e_ok:
        return "a_juger_quadra"
    if q_ok and not e_ok:
        return "erreur_eywai"
    return "a_juger_les_deux"
```

- [ ] **Étape 4 : lancer, succès attendu.**
- [ ] **Étape 5 : commit.** Message « feat(verification-rgdu): comparaison à trois colonnes et pré-classement ».

---

### Tâche 9 : rejeu des trois sociétés, rapport et classement final

**Fichiers :**
- Créer : `backend/scripts/verification_rgdu/rejouer.py`, `backend/scripts/verification_rgdu/rapport.py`
- Test : `backend/tests/unit/scripts/verification_rgdu/test_rapport.py`

**Interfaces :**
- Consomme : tout ce qui précède.
- Produit :
  - `rapport.ecrire_csv(lignes: list[LigneComparee], chemin: Path) -> None` ;
  - `rapport.resume_agrege(lignes) -> str`, un tableau en Markdown des comptes et des montants par société, pré-classement et mois, **sans aucune clé de salarié** ;
  - `rejouer.main(societe: str) -> int`, qui écrit `data/_rapports/rgdu-2026/<societe>.csv` et `<societe>.md`.

- [ ] **Étape 1 : test qui échoue**
```python
import pytest

from scripts.verification_rgdu.comparaison import LigneComparee
from scripts.verification_rgdu.rapport import resume_agrege

pytestmark = pytest.mark.unit


def test_le_resume_agrege_ne_contient_aucune_cle_de_salarie():
    l = LigneComparee("colorplast", "1999999999999", 3, 2283.0, "dsn", 2000.0, 2000.0, 12000.0, 7000.0, "a_juger_quadra", 45.0, 0.0)
    texte = resume_agrege([l])
    assert "1999999999999" not in texte
    assert "a_juger_quadra" in texte and "45.00" in texte
```

- [ ] **Étape 2 : lancer, échec attendu.**
- [ ] **Étape 3 : écrire `rapport.py`**
```python
"""Sorties du rejeu : CSV nominatif (data/_rapports, hors git) et résumé agrégé sans nom."""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from scripts.verification_rgdu.comparaison import LigneComparee


def ecrire_csv(lignes: list[LigneComparee], chemin: Path) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(lignes[0])) + ["classement_final", "regle", "note"])
        w.writeheader()
        for l in lignes:
            w.writerow({**asdict(l), "classement_final": "", "regle": "", "note": ""})


def resume_agrege(lignes: list[LigneComparee]) -> str:
    comptes: dict[tuple[str, str], list[float]] = defaultdict(list)
    for l in lignes:
        comptes[(l.societe, l.preclassement)].append(l.impact_quadra + l.impact_eywai)
    sortie = ["| Société | Pré-classement | Lignes | Impact cumulé (€) |", "|---|---|---|---|"]
    for (s, c), impacts in sorted(comptes.items()):
        sortie.append(f"| {s} | {c} | {len(impacts)} | {sum(impacts):.2f} |")
    return "\n".join(sortie) + "\n"
```

- [ ] **Étape 4 : écrire `regle_du_mois.py` et son test.** Ce module traduit un `MoisQuadra` en SMIC légal du mois, avec `oracle_smic` et les règles retenues dans `regles.md`. Interface : `smic_loi_du_mois(mq: MoisQuadra) -> float | None`, qui renvoie None quand un élément nécessaire manque, par exemple le salaire sans absence pour un arrêt maintenu. Code :
```python
"""SMIC légal du mois à partir des éléments Quadra (règles de regles.md)."""
from __future__ import annotations

from scripts.verification_rgdu.oracle_smic import (
    smic_absence_non_payee, smic_forfait_jours, smic_mois_complet, smic_suspension_avec_paiement,
)
from scripts.verification_rgdu.quadra_mois import MoisQuadra

VARIANTE_ABSENCE = "soustraction"   # à fixer d'après regles.md, R-H3
NON_PAYEES = {"non_payee", "injustifiee", "sans_solde"}
SUSPENSIONS = {"maladie", "paternite"}


def smic_loi_du_mois(mq: MoisQuadra) -> float | None:
    if mq.forfait_jours:
        return smic_forfait_jours(mq.forfait_jours)
    non_payees = sum(a.heures or 0.0 for a in mq.absences if a.nature in NON_PAYEES)
    suspensions = [a for a in mq.absences if a.nature in SUSPENSIONS]
    heures_sup = round(max(0.0, mq.heures_mois + non_payees + sum(a.heures or 0.0 for a in suspensions) - 151.67), 2)
    complet = smic_mois_complet(151.67, heures_sup, 0.0)
    smic = smic_absence_non_payee(complet, non_payees, 151.67 + heures_sup, VARIANTE_ABSENCE) if non_payees else complet
    if suspensions:
        retenue = sum(a.montant or 0.0 for a in suspensions)
        sans_absence = mq.brut_mois + retenue - mq.maintien
        if sans_absence <= 0:
            return None
        smic = smic_suspension_avec_paiement(smic, mq.brut_mois, sans_absence)
    return smic
```
  Test `backend/tests/unit/scripts/verification_rgdu/test_regle_du_mois.py` :
```python
import pytest

from scripts.verification_rgdu.oracle_smic import smic_forfait_jours, smic_mois_complet
from scripts.verification_rgdu.quadra_mois import Absence, MoisQuadra
from scripts.verification_rgdu.regle_du_mois import smic_loi_du_mois

pytestmark = pytest.mark.unit


def _mq(heures, absences=(), brut=2400.0, maintien=0.0, forfait=None):
    m = MoisQuadra("colorplast", 3, "ESSAI", "1999999999999", brut, brut, heures, heures, 0.0)
    m.absences, m.maintien, m.forfait_jours = list(absences), maintien, forfait
    return m


def test_mois_complet_39_heures():
    assert smic_loi_du_mois(_mq(169.0)) == smic_mois_complet(151.67, 17.33, 0.0)


def test_forfait_216_jours():
    assert smic_loi_du_mois(_mq(0.0, forfait=216)) == smic_forfait_jours(216)


def test_arret_maintenu_en_entier_garde_tout_le_smic():
    arret = Absence("maladie", "Absence maladie 160326-280326", 70.0, 877.0)
    assert smic_loi_du_mois(_mq(99.0, [arret], maintien=877.0)) == smic_mois_complet(151.67, 17.33, 0.0)


def test_arret_sans_maintien_au_rapport_de_la_remuneration():
    arret = Absence("maladie", "Absence maladie 160326-280326", 70.0, 1000.0)
    attendu = round(smic_mois_complet(151.67, 17.33, 0.0) * 1400.0 / 2400.0, 2)
    assert smic_loi_du_mois(_mq(99.0, [arret], brut=1400.0)) == attendu
```
  Lancer : `env -u APP_ENV .venv/bin/python -m pytest -q -p no:faulthandler tests/unit/scripts/verification_rgdu/test_regle_du_mois.py`. Attendu : 4 réussis.

  Dès que `regles.md` tranche la valeur de `VARIANTE_ABSENCE` et les cas d'entrée ou de sortie (`mq.entree`, `mq.sortie` → `smic_entree_sortie`), les ajouter ici avec leur test.

- [ ] **Étape 5 : écrire `rejouer.py`**
```python
"""Rejeu d'une société : Quadra (DSN ou implicite), loi, EYWAI → data/_rapports/rgdu-2026/.

Usage (depuis backend/) : PYTHONPATH=. .venv/bin/python -m scripts.verification_rgdu.rejouer colorplast
"""
from __future__ import annotations

import sys

from scripts.verification_rgdu import piege

piege.poser_le_piege()

from scripts.verification_rgdu.chemins import DATA, RAPPORT, SOCIETES  # noqa: E402
from scripts.verification_rgdu.colonne_eywai import depuis_le_filet  # noqa: E402
from scripts.verification_rgdu.comparaison import LigneComparee, preclasser  # noqa: E402
from scripts.verification_rgdu.dsn_quadra import dsn_du_mois  # noqa: E402
from scripts.verification_rgdu.implicite import smic_quadra_par_mois  # noqa: E402
from scripts.verification_rgdu.oracle import Parametres  # noqa: E402
from scripts.verification_rgdu.quadra_mois import lire_societe  # noqa: E402
from scripts.verification_rgdu.rapport import ecrire_csv, resume_agrege  # noqa: E402
from scripts.verification_rgdu.regle_du_mois import smic_loi_du_mois  # noqa: E402


def main(societe: str) -> int:
    prm = Parametres()
    quadra = lire_societe(societe)
    dsn = {m: {b.nir: b for b in dsn_du_mois(societe, m) if b.debut.month == m} for m in SOCIETES[societe]["mois"]}
    par_nir: dict[str, list] = {}
    for (cle, m), mq in quadra.items():
        par_nir.setdefault(cle, []).append(mq)
    eywai = depuis_le_filet(DATA / "_filet" / "colorplast-janvier-aout" / "reference.json") if societe == "colorplast" else {}
    eid_par_nir = _employee_ids(societe) if eywai else {}
    lignes: list[LigneComparee] = []
    for cle, mois in par_nir.items():
        implicite = smic_quadra_par_mois(mois, prm)
        smic_cumule = 0.0
        for mq in sorted(mois, key=lambda x: x.mois):
            b = dsn.get(mq.mois, {}).get(cle)
            smic_q = b.smic_retenu if b and b.smic_retenu is not None else implicite.get(mq.mois)
            source = "dsn" if b and b.smic_retenu is not None else "implicite"
            ey = eywai.get((eid_par_nir.get(cle, ""), mq.mois))
            l = LigneComparee(societe, cle, mq.mois, smic_q, source, smic_loi_du_mois(mq),
                              ey.smic if ey else None, mq.cumul_bruts, smic_cumule)
            l.preclassement = preclasser(l, prm)
            lignes.append(l)
            smic_cumule += smic_q or 0.0
    ecrire_csv(lignes, RAPPORT / f"{societe}.csv")
    (RAPPORT / f"{societe}.md").write_text(resume_agrege(lignes), encoding="utf-8")
    print(resume_agrege(lignes))
    return 0


def _employee_ids(societe: str) -> dict[str, str]:
    from app.core.database import get_supabase_admin_client

    rows = get_supabase_admin_client().table("employees").select("id, nir").eq(
        "company_id", SOCIETES[societe]["company_id"]).execute().data
    return {str(r["nir"] or "").replace(" ", "")[:13]: r["id"] for r in rows}


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
```

- [ ] **Étape 6 : lancer le rejeu des trois sociétés.**
```bash
for s in colorplast comitech mbc; do PYTHONPATH=. .venv/bin/python -m scripts.verification_rgdu.rejouer $s; done
```
  Attendu : trois CSV et trois résumés dans `data/_rapports/rgdu-2026/`, et `piege.ECRITURES` vide. Chaque ligne `a_juger_*` ou `erreur_eywai` a un impact chiffré.
- [ ] **Étape 7 : classement final (relecture).** Pour chaque ligne dont le pré-classement n'est ni `identique` ni `arrondi`, remplir dans le CSV :
  - `classement_final`, parmi `erreur_eywai`, `erreur_quadra`, `methode_legale_differente`, `donnee_manquante` et `arrondi` ;
  - `regle`, l'ID de `regles.md` ;
  - `note`, en une phrase avec la ligne du bulletin.

  Critère : aucune ligne ne reste vide. Les écarts qui se répètent, comme le SMIC de juin, peuvent être classés en bloc avec une note commune.
- [ ] **Étape 8 : commit** des modules et tests seulement (`sans_nom` d'abord). Les CSV restent dans `data/`. Message « feat(verification-rgdu): rejeu des trois sociétés et classement des écarts ».

---

### Tâche 10 : ouvertures au 31/08 et septembre à blanc

**Fichiers :**
- Créer : `backend/scripts/verification_rgdu/ouverture.py`
- Test : `backend/tests/unit/scripts/verification_rgdu/test_ouverture.py`

**Interfaces :**
- Consomme : `oracle.reduction_cumulee`, `oracle.smic_pour_reduction`, les cumuls du mois 8 en base (lecture), `colonne_eywai.depuis_le_bac_a_sable`.
- Produit :
  - `ecart_d_ouverture(brut_total: float, heures: float, reduction_quadra: float, prm) -> float`, soit la formule sur heures × 12,02 moins la réduction de Quadra ;
  - `heures_qui_redonnent_quadra(brut_total, reduction_quadra, prm) -> float` ;
  - `main()`, qui écrit `data/_rapports/rgdu-2026/ouvertures.md`.

- [ ] **Étape 1 : test qui échoue**
```python
import pytest

from scripts.verification_rgdu.oracle import Parametres, reduction_cumulee
from scripts.verification_rgdu.ouverture import ecart_d_ouverture, heures_qui_redonnent_quadra

pytestmark = pytest.mark.unit
P = Parametres()


def test_une_ouverture_coherente_n_a_pas_d_ecart():
    r = reduction_cumulee(14349.67, round(998.6 * 12.02, 2), P)
    assert abs(ecart_d_ouverture(14349.67, 998.6, r, P)) < 1.0
    # Palier d'arrondi du coefficient : environ 0,15 h sur ce brut.
    assert abs(heures_qui_redonnent_quadra(14349.67, r, P) - 998.6) < 0.2


def test_des_heures_imprimees_trop_basses_donnent_un_ecart_negatif():
    r = reduction_cumulee(14349.67, round(998.6 * 12.02, 2), P)
    assert ecart_d_ouverture(14349.67, 973.8, r, P) < -200
```

- [ ] **Étape 2 : lancer, échec attendu.**
- [ ] **Étape 3 : écrire `ouverture.py`**
```python
"""R1 : l'ouverture au 31/08 redonne-t-elle la réduction de Quadra ? Et septembre à blanc avant / après."""
from __future__ import annotations

import copy

from scripts.verification_rgdu import piege
from scripts.verification_rgdu.chemins import RAPPORT, SOCIETES
from scripts.verification_rgdu.oracle import Parametres, reduction_cumulee, smic_pour_reduction
from scripts.verification_rgdu.oracle_smic import SMIC_H_2026


def ecart_d_ouverture(brut_total: float, heures: float, reduction_quadra: float, prm: Parametres) -> float:
    return round(reduction_cumulee(brut_total, round(heures * SMIC_H_2026, 2), prm) - reduction_quadra, 2)


def heures_qui_redonnent_quadra(brut_total: float, reduction_quadra: float, prm: Parametres) -> float:
    return round(smic_pour_reduction(brut_total, reduction_quadra, prm) / SMIC_H_2026, 2)


def main() -> int:
    piege.poser_le_piege()
    from app.core.database import get_supabase_admin_client
    from scripts.verification_rgdu.colonne_eywai import depuis_le_bac_a_sable

    prm, admin, lignes = Parametres(), get_supabase_admin_client(), ["| Société | Salarié | Écart d'ouverture (€) | Heures imprimées | Heures Quadra | Sept. actuel | Sept. corrigé |", "|---|---|---|---|---|---|---|"]
    for societe in ("colorplast", "comitech"):
        emps = admin.table("employees").select("id, last_name").eq("company_id", SOCIETES[societe]["company_id"]).execute().data
        for e in emps:
            rows = admin.table("employee_schedules").select("cumuls").eq("employee_id", e["id"]).eq("year", 2026).eq("month", 8).execute().data
            c = (rows[0]["cumuls"] or {}).get("cumuls") if rows else None
            if not c or "reduction_generale_patronale" not in c:
                continue
            brut, h, rq = float(c["brut_total"]), float(c["heures_remunerees"]), abs(float(c["reduction_generale_patronale"]))
            ecart = ecart_d_ouverture(brut, h, rq, prm)
            hq = heures_qui_redonnent_quadra(brut, rq, prm) if rq > 0 else h
            actuel = corrige = None
            try:
                actuel = depuis_le_bac_a_sable(e["id"], 9, rows[0]["cumuls"]).reduction_ligne
                cumuls = copy.deepcopy(rows[0]["cumuls"])
                cumuls["cumuls"]["heures_remunerees"] = hq
                corrige = depuis_le_bac_a_sable(e["id"], 9, cumuls).reduction_ligne
            except Exception as exc:  # noqa: BLE001 — noté dans le rapport, jamais masqué
                actuel = f"échec : {type(exc).__name__}"
            lignes.append(f"| {societe} | {e['last_name']} | {ecart:+.2f} | {h:.2f} | {hq:.2f} | {actuel} | {corrige} |")
    RAPPORT.mkdir(parents=True, exist_ok=True)
    (RAPPORT / "ouvertures.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print("\n".join(lignes))
    print("écritures tentées :", piege.ECRITURES)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Étape 4 : lancer les tests, succès attendu.**
- [ ] **Étape 5 : lancer le contrôle.** `PYTHONPATH=. .venv/bin/python -m scripts.verification_rgdu.ouverture`. Attendu :
  - un tableau pour Colorplast et Comitech ;
  - chez Colorplast, les écarts déjà connus (−235,87 et −216,04 pour deux salariés) ;
  - aucune écriture tentée, hors `employee_cp_seniority_grants`, limite connue du bac à sable, dont l'écriture est bloquée.
- [ ] **Étape 6 : Mont-Blanc, ouverture simulée au 31/07.** Depuis `lire_societe('mbc')`, pour chaque salarié présent en juillet, calculer `ecart_d_ouverture(cumul_bruts, cumul_heures, somme des reduction_mois, prm)` et l'ajouter en fin de `ouvertures.md`.
- [ ] **Étape 7 : commit** du module et du test (`sans_nom` d'abord). Message « feat(verification-rgdu): contrôle des ouvertures et septembre à blanc ».

---

### Tâche 11 : réponses aux questions de la spec

**Fichiers :**
- Créer : `data/_rapports/rgdu-2026/reponses.md`, nominatif et non versionné.

- [ ] **Étape 1 : créer le fichier** avec une section par question de la spec, dans cet ordre : F1 à F4, H1 à H12, B1, B2, A1 à A4, R1 à R4, D1 à D4, P1 à P5. Chaque section a exactement ces lignes :
```markdown
### <ID> — <question>
- Réponse : oui / non / <chiffre>
- Preuve : <texte (fichier de docs/reference, article)> ; <données (CSV, ligne) ou code (fichier:ligne)>
- Montant en jeu : <€, par société>
- Correction proposée : <fichier visé, ce qui change> ou « aucune »
- Priorité : avant la paie d'octobre / avant janvier 2027 / plus tard
```
- [ ] **Étape 2 : questions de données.** Répondre à H1 à H12, B1, B2, R1 à R4 et F2 à partir des CSV de la tâche 9 et de `ouvertures.md` : compter les lignes par classement final et citer un cas chiffré par règle.
- [ ] **Étape 3 : questions de code**, preuve par `fichier:ligne` et démonstration chiffrée :
  - **A1** : appeler `oracle.coefficient` avec un brut cumulé qui contient toute l'année 2026 plus janvier 2027, face aux heures de janvier seules. Le coefficient vaut 0. Citer `payslip_run_common.py:71-88` et `calcul_reduction_generale.py:213-225`.
  - **A2** : citer `payslip_run_common.py:182-186` (JEI, paramétrage inactif).
  - **D1** : `builder.py:605-623`, `synthese_net.montant_smic_reduction_generale` n'est jamais produit.
  - **D2** : `cotisation_mapping.py:76-83, 344-380`, 0,3980 et 0,4020 contre `Parametres().tmax`. Donner la règle officielle d'après `regles.md` (R-D2).
  - **D3** : `accounting_plan.py:63`.
  - **D4** : `dsn_import/application/cumuls.py:394-396`, `rubriques.py:318-321`.
  - **P1 à P5** : `calcul_reduction_generale.py:104-109`, `baremes_loader.py:59-74, 370-401`, `scraping/reduction_generale/spec.py`, les tests qui recopient la formule (`test_heures_arret_smic_reference.py:23` et suivants).
- [ ] **Étape 4 : critère.** Aucune section n'a de champ vide. Toute réponse « on ne sait pas » a sa donnée manquante listée dans `demande-donnees.md`.

---

### Tâche 12 : conclusion, résumé versionné, mémoire

**Fichiers :**
- Créer : `data/_rapports/rgdu-2026/conclusion.md`, nominatif.
- Créer : `docs/comptes-rendus/verification-reduction-generale-2026.md`, agrégé et sans nom.

- [ ] **Étape 1 : conclusion par société**, dans `conclusion.md` :
  - à partir de quel mois la réduction d'EYWAI est fiable, et à quelles conditions ;
  - la liste des corrections, triées par priorité, chacune avec le fichier visé, le montant et le test qui la prouvera.
- [ ] **Étape 2 : questions à Gaëlle ou à Cegid.** Seulement celles que les textes et les données ne tranchent pas, une phrase chacune, avec l'exemple chiffré.
- [ ] **Étape 3 : résumé versionné.** Écrire `docs/comptes-rendus/verification-reduction-generale-2026.md` avec :
  - les tableaux `resume_agrege` des trois sociétés ;
  - les réponses aux questions, sans noms, les salariés étant désignés par leur pseudonyme de `data/_outils/pseudonymes.json` s'il le faut ;
  - la conclusion et la liste des corrections.

  Lancer `sans_nom` : il doit répondre « aucun nom ».
- [ ] **Étape 4 : commit** du résumé. Message « docs(comptes-rendus): vérification de la réduction générale 2026, réponses et conclusion ».
- [ ] **Étape 5 : mémoire.** Mettre à jour `chantier-verification-reduction-generale.md` : conclusion, corrections décidées, questions ouvertes.
- [ ] **Étape 6 : présenter à Alexandre** la conclusion, en dix lignes au plus, et proposer le plan de corrections (writing-plans) pour les corrections « avant la paie d'octobre ».
