# Compensation entre semaines : retenir le solde négatif — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** quand la fenêtre des variables se solde par un manque d'heures, retenir ce manque sur les derniers jours réellement manqués, au lieu d'effacer les retenues d'absence sans rien remettre.

**Architecture:** une fonction pure de plus dans le module de compensation décide quelles absences injustifiées survivent ; `appliquer_aux_mois` prend cette décision une seule fois pour toute la fenêtre (qui est à cheval sur deux mois) et la transmet à `appliquer`, qui cesse de supprimer les absences en bloc.

**Tech Stack:** Python 3.12, pytest. Module pur, sans base de données. Interpréteur : `backend/.venv/bin/python`. Linter : `backend/.venv/bin/ruff`.

## Global Constraints

- Spec de référence : `docs/superpowers/specs/2026-09-22-compensation-solde-negatif-retenu-design.md`.
- Convention de répartition, reprise de `_absences_injustifiees_de_la_semaine` : les heures supplémentaires absorbent les manques **dans l'ordre des jours** ; ce qui reste est retenu **sur les derniers jours manqués**.
- `Compensation.solde_negatif` vaut 0 ou est négatif — jamais positif. Ne jamais écrire de test qui suppose le contraire.
- À jour égal, l'absence `absence_injustifiee_base` est gardée avant `absence_injustifiee_hs25`.
- Le compteur de récupération entre mois de Gaëlle reste **hors périmètre**.
- Les régularisations antérieures (`is_regularisation_anterieure`) ne sont jamais touchées.
- Tous les commentaires, docstrings, libellés et messages sont en **français**.
- **Ne jamais commiter sans accord explicite d'Alexandre.** Les étapes « Commit » de ce plan sont des propositions : les préparer, les annoncer, attendre le feu vert.
- Lancer les tests depuis `backend/` avec `APP_ENV=test`.

---

### Task 1 : la fonction pure `absences_a_conserver`

**Files:**
- Modify: `backend/app/modules/payroll/application/compensation_semaines.py`
- Test: `backend/tests/unit/payroll/test_compensation_semaines.py`

**Interfaces:**
- Consumes: rien (fonction autonome, ajoutée au module existant).
- Produces: `absences_a_conserver(absences: list[dict[str, Any]], solde_negatif: float) -> tuple[list[dict[str, Any]], float]` — rend `(absences_gardées, reliquat_sans_jour)`. Les absences gardées portent les mêmes clés que celles reçues, avec `heures` éventuellement réduit, triées par date croissante. `reliquat_sans_jour` est un nombre positif ou nul.

- [ ] **Step 1 : écrire les tests qui échouent**

Ajouter à la fin de `backend/tests/unit/payroll/test_compensation_semaines.py` :

```python
class TestAbsencesAConserver:
    """Les heures sup absorbent les manques ; ce qui reste est retenu sur les
    derniers jours manqués (spec 2026-09-22)."""

    @staticmethod
    def _absence(jour: int, heures: float, *, type_: str = "absence_injustifiee_base", mois: int = 1):
        return {"annee": 2026, "mois": mois, "jour": jour, "type": type_, "heures": heures}

    def test_solde_nul_tout_est_absorbe(self):
        """Une semaine négative couverte par les heures sup d'une autre : c'est
        Bugny en mai, ce que l'option gagne et qu'il ne faut pas casser."""
        gardees, reliquat = absences_a_conserver([self._absence(12, 5.0)], 0.0)

        assert (gardees, reliquat) == ([], 0.0)

    def test_sans_absence_le_solde_devient_un_reliquat(self):
        gardees, reliquat = absences_a_conserver([], -4.0)

        assert (gardees, reliquat) == ([], 4.0)

    def test_un_seul_jour_est_reduit_au_solde(self):
        gardees, reliquat = absences_a_conserver([self._absence(21, 5.0)], -4.0)

        assert [(a["jour"], a["heures"]) for a in gardees] == [(21, 4.0)]
        assert reliquat == 0.0

    def test_les_jours_les_plus_tardifs_sont_retenus_les_premiers(self):
        absences = [self._absence(10, 2.0), self._absence(20, 3.0)]

        gardees, reliquat = absences_a_conserver(absences, -4.0)

        assert [(a["jour"], a["heures"]) for a in gardees] == [(10, 1.0), (20, 3.0)]
        assert reliquat == 0.0

    def test_le_manque_au_dela_des_absences_est_un_reliquat(self):
        gardees, reliquat = absences_a_conserver([self._absence(21, 5.0)], -10.0)

        assert [(a["jour"], a["heures"]) for a in gardees] == [(21, 5.0)]
        assert reliquat == 5.0

    def test_deux_evenements_du_meme_type_le_meme_jour_sont_additionnes(self):
        absences = [self._absence(21, 2.0), self._absence(21, 1.5)]

        gardees, reliquat = absences_a_conserver(absences, -3.0)

        assert [(a["jour"], a["heures"]) for a in gardees] == [(21, 3.0)]
        assert reliquat == 0.0

    def test_a_jour_egal_la_base_est_gardee_avant_les_hs(self):
        absences = [
            self._absence(21, 3.14),
            self._absence(21, 0.36, type_="absence_injustifiee_hs25"),
        ]

        gardees, reliquat = absences_a_conserver(absences, -3.14)

        assert [(a["type"], a["heures"]) for a in gardees] == [
            ("absence_injustifiee_base", 3.14)
        ]
        assert reliquat == 0.0
```

Compléter l'import en tête du fichier (`from app.modules.payroll.application.compensation_semaines import (...)`) en y ajoutant `absences_a_conserver`.

- [ ] **Step 2 : vérifier que les tests échouent**

```bash
cd backend && APP_ENV=test .venv/bin/python -m pytest tests/unit/payroll/test_compensation_semaines.py::TestAbsencesAConserver -v
```

Attendu : ÉCHEC à l'import — `ImportError: cannot import name 'absences_a_conserver'`.

- [ ] **Step 3 : écrire la fonction**

Dans `backend/app/modules/payroll/application/compensation_semaines.py`, juste après `compenser` :

```python
def _rang_de_retenue(cle: tuple[int, int, int, str]) -> tuple[int, str]:
    """Du jour le plus tardif au plus ancien ; à jour égal, la base avant les HS."""
    annee, mois, jour, type_ = cle
    return (-(annee * 10000 + mois * 100 + jour), type_)


def absences_a_conserver(
    absences: list[dict[str, Any]],
    solde_negatif: float,
) -> tuple[list[dict[str, Any]], float]:
    """Les absences injustifiées à garder, et ce qu'aucun jour ne porte.

    Les heures supplémentaires de la fenêtre ont absorbé les manques dans
    l'ordre des jours ; ce qui reste — `solde_negatif`, au signe près — est
    retenu sur les derniers jours manqués. C'est la convention que l'analyseur
    applique déjà à l'intérieur d'une semaine.

    Rend les absences gardées (triées par date, `heures` éventuellement réduit)
    et le reliquat qu'aucun jour ne porte, qui doit rester nul.
    """
    a_retenir = round(-float(solde_negatif or 0.0), 2)
    if a_retenir <= 0:
        return [], 0.0

    groupes: dict[tuple[int, int, int, str], dict[str, Any]] = {}
    for ev in absences:
        try:
            cle = (int(ev["annee"]), int(ev["mois"]), int(ev["jour"]), str(ev.get("type") or ""))
        except (KeyError, TypeError, ValueError):
            continue
        heures = round(float(ev.get("heures") or 0.0), 2)
        if cle in groupes:
            groupes[cle]["heures"] = round(groupes[cle]["heures"] + heures, 2)
        else:
            groupes[cle] = {**ev, "heures": heures}

    gardees: list[dict[str, Any]] = []
    restant = a_retenir
    for cle in sorted(groupes, key=_rang_de_retenue):
        if restant <= 0:
            break
        pris = min(groupes[cle]["heures"], restant)
        if pris > 0:
            gardees.append({**groupes[cle], "heures": round(pris, 2)})
            restant = round(restant - pris, 2)

    gardees.sort(key=lambda a: (int(a["annee"]), int(a["mois"]), int(a["jour"])))
    return gardees, round(max(restant, 0.0), 2)
```

Ajouter `"absences_a_conserver"` à `__all__` s'il existe dans ce module.

- [ ] **Step 4 : vérifier que les tests passent**

```bash
cd backend && APP_ENV=test .venv/bin/python -m pytest tests/unit/payroll/test_compensation_semaines.py -v
```

Attendu : les sept nouveaux tests passent, et les tests existants du fichier restent verts.

- [ ] **Step 5 : linter**

```bash
cd backend && .venv/bin/ruff check app/modules/payroll/application/compensation_semaines.py tests/unit/payroll/test_compensation_semaines.py
```

Attendu : `All checks passed!`

- [ ] **Step 6 : proposer le commit (ne pas commiter sans accord)**

```bash
git add backend/app/modules/payroll/application/compensation_semaines.py backend/tests/unit/payroll/test_compensation_semaines.py
git commit -m "feat(paie): la compensation sait quelles absences retenir"
```

---

### Task 2 : câbler la décision et la dire sur le bulletin

**Files:**
- Modify: `backend/app/modules/payroll/application/compensation_semaines.py`
- Test: `backend/tests/unit/payroll/test_compensation_semaines.py`

**Interfaces:**
- Consumes: `absences_a_conserver(absences, solde_negatif) -> (gardées, reliquat)` de la tâche 1.
- Produces:
  - `Compensation` gagne deux champs, `solde_retenu: float = 0.0` et `reliquat_sans_jour: float = 0.0`, tous deux positifs ou nuls.
  - `appliquer(evenements, fenetre, compensation, *, annee, mois, absences_gardees=())` — nouveau paramètre nommé, valeur par défaut `()` pour ne rien casser.
  - `appliquer_aux_mois(...)` garde sa signature et rend toujours `(dict, Compensation)`, la `Compensation` portant désormais `solde_retenu` et `reliquat_sans_jour`.

- [ ] **Step 1 : écrire les tests qui échouent**

Ajouter à `backend/tests/unit/payroll/test_compensation_semaines.py` :

```python
class TestRetenueDuSoldeNegatif:
    FENETRE = (date(2026, 6, 22), date(2026, 7, 26))

    @staticmethod
    def _planning(mois: int, jours: list[int], heures: float = 7.8):
        return [
            {"annee": 2026, "mois": mois, "jour": j, "type": "travail", "heures_prevues": heures}
            for j in jours
        ]

    def test_le_solde_negatif_garde_l_absence_a_sa_date(self):
        """Cotte, janvier : 3,5 h manquées le 21, aucune heure sup pour les absorber."""
        compensation = compenser({(2026, 27): -3.5}, 39.0)
        evenements = [
            {"annee": 2026, "mois": 7, "jour": 1, "type": "absence_injustifiee_base", "heures": 3.5},
        ]

        resultat = appliquer(
            evenements,
            self.FENETRE,
            compensation,
            annee=2026,
            mois=7,
            absences_gardees=[
                {"annee": 2026, "mois": 7, "jour": 1, "type": "absence_injustifiee_base", "heures": 3.5}
            ],
        )

        assert [(e["jour"], e["type"], e["heures"]) for e in resultat] == [
            (1, "absence_injustifiee_base", 3.5)
        ]

    def test_sans_absence_gardee_l_absence_disparait_comme_avant(self):
        compensation = compenser({(2026, 27): 2.0}, 39.0)
        evenements = [
            {"annee": 2026, "mois": 7, "jour": 1, "type": "absence_injustifiee_base", "heures": 3.5},
        ]

        resultat = appliquer(evenements, self.FENETRE, compensation, annee=2026, mois=7)

        assert [e["type"] for e in resultat] == ["travail_hs25"]

    def test_la_fenetre_a_cheval_decide_une_seule_fois(self):
        """Une absence en juin, une en juillet, un solde qui n'en couvre qu'une :
        c'est la plus tardive qui est retenue, dans son mois.

        Trois semaines : S26 (24/06) à −3, S27 (01/07) à −3, S28 (08/07) à +3.
        net25 = −3 − 3 + 3 = −3, donc 3 h à retenir sur 6 h d'absences.
        """
        planning = self._planning(6, [24]) + self._planning(7, [1, 8])
        reel = [
            {"annee": 2026, "mois": 6, "jour": 24, "heures_faites": 4.8},
            {"annee": 2026, "mois": 7, "jour": 1, "heures_faites": 4.8},
            {"annee": 2026, "mois": 7, "jour": 8, "heures_faites": 10.8},
        ]
        evenements = {
            (2026, 7): [
                {"annee": 2026, "mois": 7, "jour": 1, "type": "absence_injustifiee_base", "heures": 3.0}
            ],
            (2026, 6): [
                {"annee": 2026, "mois": 6, "jour": 24, "type": "absence_injustifiee_base", "heures": 3.0}
            ],
        }

        resultat, compensation = appliquer_aux_mois(
            evenements, planning, reel, 39.0, self.FENETRE
        )

        assert compensation.solde_retenu == 3.0
        assert [e["jour"] for e in resultat[(2026, 7)]] == [1]
        assert resultat[(2026, 6)] == []

    def test_le_reliquat_sans_jour_est_compte(self):
        """Un manque que rien ne porte : aucun événement d'absence n'existe.

        Attention : `mois_sans_pointage` neutralise un mois dont aucun jour n'a
        d'heures faites. Il faut donc une vraie journée travaillée à côté du
        jour manqué, sinon la semaine est ignorée et le solde vaut zéro.
        """
        planning = self._planning(7, [1, 2])
        reel = [
            {"annee": 2026, "mois": 7, "jour": 1, "heures_faites": 0.0},
            {"annee": 2026, "mois": 7, "jour": 2, "heures_faites": 7.8},
        ]

        _, compensation = appliquer_aux_mois({(2026, 7): []}, planning, reel, 39.0, self.FENETRE)

        assert compensation.reliquat_sans_jour == 7.8
        assert compensation.solde_retenu == 0.0

    def test_la_mention_dit_que_le_solde_est_retenu(self):
        compensation = compenser({(2026, 27): 1.5, (2026, 30): -4.0}, 39.0)
        retenue = replace(compensation, solde_retenu=2.5)

        assert mention(retenue).endswith("Solde retenu : −2,5 h.")

    def test_la_mention_signale_un_reliquat_sans_jour(self):
        compensation = compenser({(2026, 30): -5.0}, 39.0)
        retenue = replace(compensation, solde_retenu=2.0, reliquat_sans_jour=3.0)

        assert "dont 3 h sans jour identifié" in mention(retenue)
```

Compléter les imports en tête du fichier : `from dataclasses import replace` et, dans l'import du module, `appliquer_aux_mois`.

- [ ] **Step 2 : corriger le test existant devenu faux**

Dans `class TestApplicationAuCalendrier`, le test `test_sans_net_positif_aucune_ligne_ajoutee` suppose l'ancien comportement : `compenser({(2026, 30): -1.0}, 39.0)` donne un solde de −1 h, et l'absence du 24 juillet (0,9 + 0,1 h) doit désormais être retenue, plus effacée. Remplacer ce test par :

```python
    def test_sans_net_positif_aucune_ligne_ajoutee(self):
        """Aucune heure sup à poser ; l'absence de la fenêtre est retenue à sa date
        dès lors que l'appelant la passe en absence gardée (spec 2026-09-22)."""
        c = compenser({(2026, 30): -1.0}, 39.0)

        resultat = appliquer(
            self._evenements_juillet(),
            self.FENETRE,
            c,
            annee=2026,
            mois=7,
            absences_gardees=[
                {"annee": 2026, "mois": 7, "jour": 24,
                 "type": "absence_injustifiee_base", "heures": 0.9},
                {"annee": 2026, "mois": 7, "jour": 24,
                 "type": "absence_injustifiee_hs25", "heures": 0.1},
            ],
        )

        assert [(e["jour"], e["type"]) for e in resultat] == [
            (13, "conges_payes"),
            (24, "absence_injustifiee_base"),
            (24, "absence_injustifiee_hs25"),
            (30, "travail_hs25"),
        ]
```

- [ ] **Step 3 : vérifier que les tests échouent**

```bash
cd backend && APP_ENV=test .venv/bin/python -m pytest tests/unit/payroll/test_compensation_semaines.py -v
```

Attendu : ÉCHEC — `TypeError: appliquer() got an unexpected keyword argument 'absences_gardees'` et `Compensation` sans `solde_retenu`.

- [ ] **Step 4 : ajouter les deux champs au dataclass**

Dans `compensation_semaines.py`, dans `class Compensation`, après `solde_negatif` :

```python
    #: Heures effectivement retenues sur des jours identifiés (positif ou nul).
    solde_retenu: float = 0.0
    #: Manque qu'aucun jour d'absence ne porte (positif ou nul) — anomalie, dite au bulletin.
    reliquat_sans_jour: float = 0.0
```

et, dans `resume()`, ajouter au dictionnaire rendu, juste après `"solde_negatif": self.solde_negatif,` :

```python
            "solde_retenu": self.solde_retenu,
            "reliquat_sans_jour": self.reliquat_sans_jour,
```

- [ ] **Step 5 : faire conserver les absences gardées par `appliquer`**

Remplacer le corps de `appliquer` (la compréhension qui construit `conserves` et la boucle qui ajoute les nets) par :

```python
def appliquer(
    evenements: list[dict[str, Any]],
    fenetre: tuple[date, date],
    compensation: Compensation,
    *,
    annee: int,
    mois: int,
    absences_gardees: Sequence[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Les événements d'un mois : heures sup de la fenêtre remplacées par les nets,
    absences injustifiées réduites à celles que l'appelant a décidé de retenir.

    Les nets sont posés au dernier jour de la fenêtre, donc dans le mois qui le
    contient ; les autres mois ne font que perdre leurs événements de la fenêtre.
    """
    gardees = {
        (int(a["annee"]), int(a["mois"]), int(a["jour"]), str(a.get("type") or "")): round(
            float(a.get("heures") or 0.0), 2
        )
        for a in absences_gardees
    }
    conserves: list[dict[str, Any]] = []
    for ev in evenements:
        type_ev = str(ev.get("type") or "")
        if ev.get("is_regularisation_anterieure") or not (
            type_ev.startswith(_TYPES_REMPLACES) and _dans_la_fenetre(ev, fenetre, annee, mois)
        ):
            conserves.append(ev)
            continue
        if not type_ev.startswith("absence_injustifiee"):
            continue  # heures sup : remplacées par les nets
        cle = (
            int(ev.get("annee") or annee),
            int(ev.get("mois") or mois),
            int(ev["jour"]),
            type_ev,
        )
        heures = gardees.pop(cle, None)
        if heures is not None and heures > 0:
            conserves.append({**ev, "heures": heures})

    fin = fenetre[1]
    if (fin.year, fin.month) == (annee, mois):
        for type_ev, heures in (
            ("travail_hs25", compensation.net25),
            ("travail_hs50", compensation.net50),
        ):
            if heures > 0:
                conserves.append(
                    {
                        "annee": fin.year,
                        "mois": fin.month,
                        "jour": fin.day,
                        "type": type_ev,
                        "heures": heures,
                        "compensation_semaines": True,
                    }
                )
    return sorted(conserves, key=lambda ev: int(ev.get("jour", 0)))
```

Compléter l'import en tête du module : `from typing import Any, Mapping, Sequence`.

- [ ] **Step 6 : décider une seule fois dans `appliquer_aux_mois`**

Remplacer `appliquer_aux_mois` par :

```python
def appliquer_aux_mois(
    evenements_par_mois: Mapping[tuple[int, int], list[dict[str, Any]]],
    planned_all: list[dict[str, Any]],
    actual_all: list[dict[str, Any]],
    duree_hebdo: float,
    fenetre: tuple[date, date],
) -> tuple[dict[tuple[int, int], list[dict[str, Any]]], Compensation]:
    """L'orchestration que le générateur appelle : bilan, compensation, application.

    La fenêtre est à cheval sur deux mois : la décision de ce qui est retenu se
    prend **une seule fois**, sur toutes les absences de la fenêtre, avant
    d'appliquer mois par mois.
    """
    compensation = compenser(ecarts_par_semaine(planned_all, actual_all, fenetre), duree_hebdo)

    absences: list[dict[str, Any]] = []
    for (annee_m, mois_m), evts in evenements_par_mois.items():
        for ev in evts:
            if ev.get("is_regularisation_anterieure"):
                continue
            if not str(ev.get("type") or "").startswith("absence_injustifiee"):
                continue
            if not _dans_la_fenetre(ev, fenetre, annee_m, mois_m):
                continue
            absences.append(
                {
                    **ev,
                    "annee": int(ev.get("annee") or annee_m),
                    "mois": int(ev.get("mois") or mois_m),
                }
            )

    gardees, reliquat = absences_a_conserver(absences, compensation.solde_negatif)
    compensation = replace(
        compensation,
        solde_retenu=round(sum(float(a["heures"]) for a in gardees), 2),
        reliquat_sans_jour=reliquat,
    )
    return (
        {
            (annee, mois): appliquer(
                evts, fenetre, compensation, annee=annee, mois=mois, absences_gardees=gardees
            )
            for (annee, mois), evts in evenements_par_mois.items()
        },
        compensation,
    )
```

Compléter l'import en tête du module : `from dataclasses import dataclass, replace`.

- [ ] **Step 7 : dire la retenue dans la mention**

Dans `mention`, remplacer le bloc final :

```python
    if compensation.solde_negatif < 0:
        texte += f" Solde non payé : {_fr(compensation.solde_negatif)} h."
```

par :

```python
    if compensation.solde_retenu > 0:
        texte += f" Solde retenu : −{_fr(compensation.solde_retenu)} h."
    if compensation.reliquat_sans_jour > 0:
        texte += f" dont {_fr(compensation.reliquat_sans_jour)} h sans jour identifié."
    return texte
```

en gardant le `return texte` unique en fin de fonction.

- [ ] **Step 8 : vérifier que les tests passent**

```bash
cd backend && APP_ENV=test .venv/bin/python -m pytest tests/unit/payroll/test_compensation_semaines.py -v
```

Attendu : tout le fichier vert, tests existants compris.

- [ ] **Step 9 : vérifier que rien d'autre n'a bougé**

```bash
cd backend && APP_ENV=test .venv/bin/python -m pytest tests/unit/payroll -q
cd backend && .venv/bin/ruff check app/modules/payroll/application/compensation_semaines.py tests/unit/payroll/test_compensation_semaines.py
```

Attendu : suite verte, `All checks passed!`.

- [ ] **Step 10 : rafraîchir le commentaire de l'appelant**

Dans `backend/app/modules/payroll/documents/payslip_generator.py`, autour de la ligne 677, le commentaire dit « jamais de retenue ». Le remplacer par :

```python
        # Option société : les heures se compensent entre semaines sur la
        # fenêtre, comme Gaëlle le fait chez Colorplast — semaines négatives
        # comprises. Le manque que les heures sup ne couvrent pas est retenu
        # sur les derniers jours manqués (spec 2026-09-22, qui corrige celle
        # du 21/09 où rien n'était retenu).
```

- [ ] **Step 11 : proposer le commit (ne pas commiter sans accord)**

```bash
git add backend/app/modules/payroll/application/compensation_semaines.py backend/tests/unit/payroll/test_compensation_semaines.py backend/app/modules/payroll/documents/payslip_generator.py
git commit -m "fix(paie): la compensation retient le solde negatif au lieu d'effacer les absences"
```

---

### Task 3 : vérifier contre Quadra, puis décider du sort de l'option

**Files:**
- Create: `backend/scripts/verif_compensation_janvier.py`
- Modify: `docs/colorplast-2026-rejeu-regulier.md`
- Modify: `/Users/alex/.claude/projects/-Users-alex-Documents-Alexandre-01-Projets-EYWAI-EYWAI/memory/compensation-heures-entre-semaines-option.md`

**Interfaces:**
- Consumes: le moteur corrigé des tâches 1 et 2.
- Produces: un verdict chiffré — les six mois rejoués avec l'option corrigée, comparés aux 16/37 et 3 028,81 € sans option et aux 13/37 et 3 677,40 € avec l'option d'avant.

- [ ] **Step 1 : contrôler les deux bulletins de janvier en bac à sable**

Écrire `backend/scripts/verif_compensation_janvier.py` :

```python
"""Contrôle ciblé : Cotte et Gautheron, janvier 2026, doivent retrouver Quadra.

Lit les bulletins en bac à sable (aucune écriture) et compare le brut aux
valeurs imprimées par Quadra. Sert de garde avant le rejeu complet.

Usage : python -m scripts.verif_compensation_janvier
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SOCIETE = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"
ATTENDU = {"COTTE": 2351.89, "GAUTHERON": 2252.28}


def main() -> int:
    from app.core.database import supabase
    from app.modules.payslips.infrastructure.providers import payslip_generator_provider

    salaries = {
        str(r["last_name"]).upper(): str(r["id"])
        for r in (
            supabase.table("employees").select("id, last_name").eq("company_id", SOCIETE).execute()
        ).data
        or []
    }
    faux = 0
    for nom, brut_quadra in ATTENDU.items():
        resultat = payslip_generator_provider.generate_en_bac_a_sable(
            salaries[nom], 2026, 1, cumuls_precedents=None
        )
        brut = float((resultat.get("payslip_data") or {}).get("salaire_brut") or 0.0)
        ecart = round(brut - brut_quadra, 2)
        marque = "OK " if abs(ecart) < 0.02 else "!! "
        faux += abs(ecart) >= 0.02
        print(f"{marque}{nom:11s} EYWAI {brut:8.2f}  Quadra {brut_quadra:8.2f}  écart {ecart:+.2f}")
    return 1 if faux else 0


if __name__ == "__main__":
    sys.exit(main())
```

Lancer :

```bash
cd backend && APP_ENV=test .venv/bin/python -m scripts.verif_compensation_janvier
```

Attendu : deux lignes `OK`, écart `+0.00` pour Cotte et Gautheron.

Si l'écart n'est pas nul, ne pas continuer : reprendre la tâche 2.

- [ ] **Step 2 : rejouer les six mois avec l'option corrigée**

En arrière-plan, le script remet lui-même la base en état :

```bash
cd backend && APP_ENV=test .venv/bin/python -m scripts.colorplast_regulier_test --apply \
  --json-dir /tmp/rejeu_apres_correction
```

Attendu, en fin de sortie : `chaîne de paie intacte`. Puis comparer :

```bash
cd backend && .venv/bin/python -c "
import json
apres = json.load(open('/tmp/rejeu_apres_correction/regulier_resume.json', encoding='utf-8'))
n = tot = 0
for mois in apres.values():
    for nom, d in mois.items():
        if d.get('brut') is None or d.get('brut_quadra') is None: continue
        e = abs(round(d['brut'] - d['brut_quadra'], 2)); tot += e; n += e < 0.02
print(f'{n} bulletins au centime, {tot:.2f} EUR d écart cumulé')
print('références : 16 et 3028.81 sans option, 13 et 3677.40 avec option non corrigée')
# les trois bulletins à regagner, et celui qu il ne faut pas casser
for mois, nom, attendu in ((1,'COTTE',0.0), (1,'GAUTHERON',0.0), (6,'DEMORY',0.0), (5,'BUGNY',35.70)):
    d = apres[str(mois)][nom]
    e = round(d['brut'] - d['brut_quadra'], 2)
    etat = 'OK ' if abs(e - attendu) < 0.02 else '!! '
    print(f'{etat}{nom} {mois:02d} : écart {e:+.2f} (attendu {attendu:+.2f})')
"
```

Les quatre lignes de contrôle doivent toutes être `OK` : Cotte, Gautheron et Demory reviennent au centime, et Bugny de mai reste à **+35,70** — c'est ce que l'option gagne, la correction ne doit pas le défaire.

- [ ] **Step 3 : trancher le sort de l'option et le dire**

Critère de la spec : Cotte janvier, Gautheron janvier et Demory juin reviennent au centime ; aucun bulletin aujourd'hui exact ne se dégrade.

- Si l'option corrigée fait mieux que 3 028,81 € : elle reste allumée pour août.
- Sinon : l'éteindre pour les cinq sociétés du test le temps de traiter le compteur de récupération, et le dire à Alexandre avec les chiffres.

Dans les deux cas, ne rien changer en base sans son accord explicite.

- [ ] **Step 4 : consigner le résultat**

Ajouter à `docs/colorplast-2026-rejeu-regulier.md` une section « Rejeu après correction du solde négatif (22/09) » portant le tableau des trois mesures (sans option, avec option, avec option corrigée) et la décision prise.

Mettre à jour la mémoire `compensation-heures-entre-semaines-option.md` : remplacer la phrase « la partie absences est à rouvrir » par le résultat mesuré.

- [ ] **Step 5 : proposer le commit (ne pas commiter sans accord)**

```bash
git add backend/scripts/verif_compensation_janvier.py docs/colorplast-2026-rejeu-regulier.md
git commit -m "chore(backtest): mesure de la compensation corrigee sur six mois"
```
