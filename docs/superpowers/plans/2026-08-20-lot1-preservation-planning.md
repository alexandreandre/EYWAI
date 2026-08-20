# Lot 1 — Le planning ne détruit plus les absences validées

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enregistrer ou régénérer un planning ne doit plus effacer
silencieusement les jours d'absence validés ni leurs métadonnées (nature
d'arrêt, subrogation, historique) — aujourd'hui un arrêt maladie
correctement saisi redevient une déduction sèche dès qu'une RH touche au
planning du mois.

**Architecture:** Trois défauts cumulés, corrigés en trois temps.
(1) `PlannedCalendarEntry` ne connaît que `{jour, type, heures_prevues}` et
sert de `response_model` au GET **et** de payload au POST : la lecture
ampute les métadonnées, l'écriture réécrit le mois entier avec ce qui reste.
(2) `update_planned_calendar` remplace au lieu de fusionner.
(3) Les jours écrits par la validation d'absence ne portent pas le drapeau
`manuel`, donc même le mode `preserve_manual` de la régénération ne les
protège pas — et le mode par défaut est `overwrite_all`.

La défense est posée **côté serveur** (fusion), pas côté client : un
frontend ancien ou un payload partiel ne doit jamais pouvoir détruire des
données. Le schéma est ouvert en complément, pour que le GET cesse de mentir.

**Tech Stack:** Python/FastAPI, Pydantic v2, Supabase, pytest.

## Global Constraints

- Tests avec `cwd=backend`, `venv/bin/python -m pytest`. Aucun test ne
  touche une vraie base (`backend/.env` pointe sur la PROD).
- Fixes **généralistes** : jamais de cas particulier lié à un salarié ou à
  une société (règle backtest du projet).
- Commits par chemins explicites, branche `dev-lot1-preservation-planning`
  depuis `main` à jour et **CI verte**.
- Aucune modification de `docs/afaire.md`, `landing/`, `AGENTS.md`.
- Vocabulaire : ce lot **ne touche pas** au débat `conge` /
  `conges_payes` (c'est le lot 2). Il préserve ce qui existe, quel que soit
  le libellé.

---

### Task 1: Le schéma cesse d'amputer les jours

**Files:**
- Modify: `backend/app/modules/schedules/schemas/requests.py` (classe `PlannedCalendarEntry`, ~ligne 14)
- Test: `backend/tests/unit/schedules/test_planned_calendar_preservation.py` (nouveau)

**Interfaces:**
- Produces: `PlannedCalendarEntry` accepte et restitue les clés
  supplémentaires (`arret_type`, `subrogation_active`, `nombre_enfants`,
  `historique_arrets_annee`, `date_debut_arret_reel`, `manuel`, …) au lieu
  de les jeter. `model_dump()` les inclut.

- [ ] **Step 1: Écrire le test qui échoue**

```python
"""Le planning ne doit jamais amputer ni écraser les métadonnées d'absence."""


def test_entree_calendrier_conserve_les_cles_supplementaires():
    from app.modules.schedules.schemas.requests import PlannedCalendarEntry

    entry = PlannedCalendarEntry(
        jour=3,
        type="arret_maladie",
        heures_prevues=0,
        arret_type="maladie_simple",
        subrogation_active=True,
        nombre_enfants=2,
        date_debut_arret_reel="2026-07-14",
    )
    dumped = entry.model_dump()
    assert dumped["arret_type"] == "maladie_simple"
    assert dumped["subrogation_active"] is True
    assert dumped["nombre_enfants"] == 2
    assert dumped["date_debut_arret_reel"] == "2026-07-14"
```

- [ ] **Step 2: Vérifier l'échec**

Run: `cd backend && venv/bin/python -m pytest tests/unit/schedules/test_planned_calendar_preservation.py -v`
Expected: FAIL — `KeyError: 'arret_type'` (Pydantic v2 ignore les extras par défaut).

- [ ] **Step 3: Implémenter**

Dans `requests.py`, ajouter l'import `ConfigDict` à la ligne d'import Pydantic existante, puis dans `PlannedCalendarEntry`, juste avant `jour: int` :

```python
    # Les jours portent des métadonnées d'absence (arret_type,
    # subrogation_active, nombre_enfants, historique_arrets_annee,
    # date_debut_arret_reel…). Sans extra="allow", le GET les amputait et le
    # POST suivant réécrivait le mois sans elles.
    model_config = ConfigDict(extra="allow")
```

- [ ] **Step 4: Vérifier le vert**

Run: `cd backend && venv/bin/python -m pytest tests/unit/schedules/ -v`
Expected: tous verts (dont les tests de planning existants).

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/schedules/schemas/requests.py backend/tests/unit/schedules/test_planned_calendar_preservation.py
git commit -m "fix(schedules): le schéma de calendrier conserve les métadonnées d'absence"
```

---

### Task 2: L'écriture fusionne au lieu de remplacer

**Files:**
- Modify: `backend/app/modules/schedules/application/commands.py` (`update_planned_calendar`, ~lignes 54-60)
- Test: `backend/tests/unit/schedules/test_planned_calendar_preservation.py` (ajout)

**Interfaces:**
- Consumes: `schedule_repository.get_schedule(employee_id, year, month)` —
  vérifier le nom exact dans `schedules/infrastructure/repository.py` et
  l'utiliser tel quel ; si aucune lecture unitaire n'existe, passer par la
  query déjà utilisée par `queries.get_planned_calendar`.
- Produces: `merge_planned_entries(existing, incoming) -> list[dict]` dans
  `schedules/domain/rules.py` — fonction pure, testable seule : pour chaque
  jour entrant, part de l'entrée stockée et superpose les champs fournis.

- [ ] **Step 1: Écrire le test de la fonction pure (échoue)**

```python
def test_fusion_conserve_les_metadonnees_absentes_du_payload():
    from app.modules.schedules.domain.rules import merge_planned_entries

    existing = [
        {
            "jour": 3,
            "type": "arret_maladie",
            "heures_prevues": 0,
            "arret_type": "maladie_simple",
            "subrogation_active": True,
            "nombre_enfants": 2,
        },
        {"jour": 4, "type": "travail", "heures_prevues": 7.0},
    ]
    # Le client renvoie le mois « appauvri » (cas réel du GET actuel)
    incoming = [
        {"jour": 3, "type": "arret_maladie", "heures_prevues": 0},
        {"jour": 4, "type": "travail", "heures_prevues": 7.0},
    ]

    merged = merge_planned_entries(existing, incoming)
    jour3 = next(e for e in merged if e["jour"] == 3)
    assert jour3["arret_type"] == "maladie_simple"
    assert jour3["subrogation_active"] is True
    assert jour3["nombre_enfants"] == 2


def test_fusion_applique_bien_les_changements_demandes():
    from app.modules.schedules.domain.rules import merge_planned_entries

    existing = [{"jour": 5, "type": "travail", "heures_prevues": 7.0}]
    incoming = [{"jour": 5, "type": "conge", "heures_prevues": 0}]

    merged = merge_planned_entries(existing, incoming)
    assert merged[0]["type"] == "conge"
    assert merged[0]["heures_prevues"] == 0


def test_fusion_accepte_un_mois_vierge_et_des_jours_nouveaux():
    from app.modules.schedules.domain.rules import merge_planned_entries

    merged = merge_planned_entries([], [{"jour": 1, "type": "travail", "heures_prevues": 7.0}])
    assert merged == [{"jour": 1, "type": "travail", "heures_prevues": 7.0}]
```

- [ ] **Step 2: Vérifier l'échec**

Run: `cd backend && venv/bin/python -m pytest tests/unit/schedules/test_planned_calendar_preservation.py -v`
Expected: FAIL — `ImportError: cannot import name 'merge_planned_entries'`.

- [ ] **Step 3: Implémenter la fonction pure**

Dans `backend/app/modules/schedules/domain/rules.py` :

```python
def merge_planned_entries(
    existing: list[dict] | None,
    incoming: list[dict],
) -> list[dict]:
    """
    Fusionne le calendrier entrant sur le calendrier stocké, jour par jour.

    Le payload d'un client ne porte souvent que ``jour``/``type``/
    ``heures_prevues`` : remplacer le mois effacerait les métadonnées
    d'absence (nature d'arrêt, subrogation, historique) posées par la
    validation d'absence. On part donc de l'entrée stockée et on superpose
    uniquement les champs fournis.
    """
    par_jour = {
        e["jour"]: dict(e) for e in (existing or []) if e.get("jour") is not None
    }
    fusionnes: list[dict] = []
    for entree in incoming:
        jour = entree.get("jour")
        base = dict(par_jour.get(jour, {}))
        base.update({k: v for k, v in entree.items() if v is not None or k in base})
        fusionnes.append(base)
    return fusionnes
```

- [ ] **Step 4: Vérifier le vert de la fonction pure**

Run: `cd backend && venv/bin/python -m pytest tests/unit/schedules/test_planned_calendar_preservation.py -v`
Expected: 4 passed.

- [ ] **Step 5: Brancher dans la commande**

Dans `update_planned_calendar` (`commands.py`), remplacer le bloc qui
construit `calendrier_prevu_raw` par une lecture de l'existant puis la
fusion — en conservant la normalisation forfait-jour qui suit :

```python
        calendrier_prevu_raw = [
            entry.model_dump() for entry in payload.calendrier_prevu
        ]
        # Fusion sur l'existant : le payload client n'embarque pas toujours
        # les métadonnées d'absence, et un remplacement les effacerait.
        existant = queries.get_planned_calendar(
            employee_id, payload.year, payload.month
        ).get("calendrier_prevu", [])
        calendrier_prevu_raw = domain_rules.merge_planned_entries(
            existant, calendrier_prevu_raw
        )
```

(vérifier le nom exact d'accès aux queries dans ce module — s'il n'est pas
déjà importé, importer `from app.modules.schedules.application import queries` ;
si `get_planned_calendar` lève quand le mois n'existe pas, envelopper dans
un `try/except` qui retombe sur `[]`.)

- [ ] **Step 6: Test d'intégration de la commande**

```python
def test_update_planned_calendar_ne_detruit_pas_les_metadonnees(monkeypatch):
    from app.modules.schedules.application import commands
    from app.modules.schedules.schemas.requests import (
        PlannedCalendarEntry,
        PlannedCalendarRequest,
    )

    stocke = {
        "calendrier_prevu": [
            {
                "jour": 3,
                "type": "arret_maladie",
                "heures_prevues": 0,
                "arret_type": "maladie_simple",
                "subrogation_active": True,
            }
        ]
    }
    monkeypatch.setattr(
        commands, "get_employee_company_and_statut", lambda _id: ("comp-1", "Employé")
    )
    monkeypatch.setattr(
        commands.queries, "get_planned_calendar", lambda *a, **k: stocke
    )
    capture = {}

    def fake_upsert(employee_id, company_id, year, month, planned_calendar=None, **kw):
        capture["planned"] = planned_calendar

    monkeypatch.setattr(commands.schedule_repository, "upsert_schedule", fake_upsert)

    payload = PlannedCalendarRequest(
        year=2026,
        month=7,
        calendrier_prevu=[
            PlannedCalendarEntry(jour=3, type="arret_maladie", heures_prevues=0)
        ],
    )
    commands.update_planned_calendar("emp-1", payload)

    jour3 = capture["planned"]["calendrier_prevu"][0]
    assert jour3["arret_type"] == "maladie_simple"
    assert jour3["subrogation_active"] is True
```

- [ ] **Step 7: Vérifier le vert + non-régression du module**

Run: `cd backend && venv/bin/python -m pytest tests/unit/schedules/ -v`
Expected: tous verts.

- [ ] **Step 8: Commit**

```bash
git add backend/app/modules/schedules/domain/rules.py backend/app/modules/schedules/application/commands.py backend/tests/unit/schedules/test_planned_calendar_preservation.py
git commit -m "fix(schedules): fusionner le calendrier au lieu de remplacer le mois"
```

---

### Task 3: La régénération ne balaie plus les absences validées

**Files:**
- Modify: `backend/app/modules/absences/infrastructure/providers.py` (`_day_entry`, ~ligne 209)
- Modify: `backend/app/modules/schedules/domain/calendar_generation_rules.py` (~ligne 178)
- Test: `backend/tests/unit/schedules/test_planned_calendar_preservation.py` (ajout)

**Interfaces:**
- Consumes: `OVERWRITE_ALL` / `PRESERVE_MANUAL` / `FILL_EMPTY` de
  `calendar_generation_rules`.
- Produces: les jours écrits par une validation d'absence portent
  `"origine": "absence"` ; `build_month_calendrier_prevu` les conserve
  **dans tous les modes**, y compris `overwrite_all`.

Choix de conception : on n'utilise pas `manuel` (qui signifie « retouché à
la main ») mais un marqueur d'origine distinct — une absence validée n'est
pas une retouche manuelle, et la distinction restera lisible.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
def test_jour_d_absence_porte_son_origine():
    from app.modules.absences.infrastructure.providers import CalendarUpdateProvider

    entry = CalendarUpdateProvider()._day_entry(
        3, "arret_maladie", 0, arret_type="maladie_simple"
    )
    assert entry["origine"] == "absence"


def test_regeneration_conserve_un_jour_d_absence_meme_en_overwrite_all():
    from app.modules.schedules.domain import calendar_generation_rules as gen

    existant = [
        {
            "jour": 3,
            "type": "arret_maladie",
            "heures_prevues": 0,
            "arret_type": "maladie_simple",
            "origine": "absence",
        }
    ]
    resultat = gen.build_month_calendrier_prevu(
        year=2026,
        month=7,
        week_config={str(d): {"heures": 7.0} for d in range(1, 6)},
        existing=existant,
        overwrite_mode=gen.OVERWRITE_ALL,
    )
    jour3 = next(e for e in resultat if e["jour"] == 3)
    assert jour3["type"] == "arret_maladie"
    assert jour3["arret_type"] == "maladie_simple"
```

**Avant d'écrire ce second test**, lire la vraie signature de
`build_month_calendrier_prevu` (`calendar_generation_rules.py:132-200`) et
aligner les noms/valeurs des paramètres (`week_config`, `holidays`, …) :
le test doit appeler la fonction telle qu'elle existe, sans la modifier.

- [ ] **Step 2: Vérifier l'échec**

Run: `cd backend && venv/bin/python -m pytest tests/unit/schedules/test_planned_calendar_preservation.py -v`
Expected: FAIL sur les deux (`KeyError: 'origine'`, puis le jour 3 revenu à `travail`).

- [ ] **Step 3: Marquer l'origine dans `_day_entry`**

Dans `providers.py`, dans le dict `entry` construit par `_day_entry` :

```python
        entry: Dict[str, Any] = {
            "jour": day,
            "type": calendar_type,
            "heures_prevues": heures if calendar_type == "travail" else 0,
            # Marque la provenance : une régénération de planning ne doit pas
            # effacer un jour issu d'une absence validée.
            "origine": "absence",
        }
```

- [ ] **Step 4: Protéger à la régénération**

Dans `calendar_generation_rules.py`, à la boucle de construction
(~ligne 178), avant le test `preserve_manual` existant :

```python
        # Un jour issu d'une absence validée n'est jamais balayé par une
        # régénération : l'écraser annulerait un arrêt ou un congé en silence.
        if existing and existing.get("origine") == "absence":
            entry = dict(existing)
            resultat.append(entry)
            continue
```

(adapter les noms de variables locales — `existing`, la liste de sortie —
à ceux réellement employés dans la fonction.)

- [ ] **Step 5: Vérifier le vert**

Run: `cd backend && venv/bin/python -m pytest tests/unit/schedules/ tests/unit/absences/ -v`
Expected: tous verts.

- [ ] **Step 6: Suite complète**

Run: `cd backend && venv/bin/python -m pytest tests/unit -q`
Expected: 0 échec (baseline actuelle : 5181 passed, 3 skipped).

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/absences/infrastructure/providers.py backend/app/modules/schedules/domain/calendar_generation_rules.py backend/tests/unit/schedules/test_planned_calendar_preservation.py
git commit -m "fix(schedules): la régénération de planning préserve les jours d'absence validés"
```

---

### Task 4: Reprise — marquer les jours d'absence déjà en base

**Files:**
- Create: `backend/scripts/backfill_origine_absence.py`
- Test: exécution en simulation d'abord, sur l'environnement de **test**

Les absences déjà validées n'ont pas le marqueur `origine` : sans reprise,
la protection de la Task 3 ne les couvre pas. Le script rapproche
`absence_requests` (validées) et `employee_schedules` pour poser le
marqueur sur les jours correspondants.

**Interfaces:**
- Produces: script idempotent avec `--apply` (sans lui : simulation
  affichée, rien n'est écrit) et `--company` optionnel pour cibler.

- [ ] **Step 1: Écrire le script**

Suivre le patron des scripts de reprise existants du dépôt (lire d'abord
`backend/scripts/` pour reprendre leurs conventions : chargement de
l'environnement, argparse, mode simulation par défaut, compte rendu final).
Logique : pour chaque `absence_request` en statut validé, pour chaque jour
de `selected_days`, si l'entrée correspondante de `planned_calendar` a un
type d'absence (`arret_maladie`, `conge`, `rtt`) et pas de clé `origine`,
poser `origine="absence"`. Ne jamais modifier `type` ni `heures_prevues`.

- [ ] **Step 2: Simulation, affichée**

Run: `cd backend && venv/bin/python -m scripts.backfill_origine_absence`
Expected: un compte rendu « N jours seraient marqués sur M salariés », aucune écriture.

- [ ] **Step 3: Appliquer sur l'environnement de test d'abord**

Pointer explicitement les variables Supabase de test (⚠ `backend/.env`
pointe sur la PROD), puis relancer avec `--apply`. Vérifier ensuite qu'un
enregistrement de planning sur un mois d'arrêt ne détruit plus rien.

- [ ] **Step 4: Appliquer en production** *(supervisé)*

Même commande contre la prod, après validation du résultat de test.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/backfill_origine_absence.py
git commit -m "chore(schedules): reprise du marqueur d'origine sur les absences validées"
```

---

## Vérification de bout en bout (avant de clore le lot)

Le scénario qui a motivé ce lot, à rejouer sur l'environnement de test :

1. Valider un arrêt maladie de 3 jours sur un salarié.
2. Vérifier en base que les jours portent `arret_type` et `origine`.
3. Ouvrir la page planning du mois, enregistrer sans rien changer.
4. Vérifier que `arret_type` et `subrogation_active` sont **toujours là**.
5. Régénérer le planning du mois depuis le plan horaire société.
6. Vérifier que les 3 jours d'arrêt sont **toujours** des arrêts.
7. Générer le bulletin : maintien et IJSS doivent apparaître.

Ce scénario devient le premier des « scénarios de vie » de l'étape 2.
