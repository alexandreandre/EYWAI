# Élus CSE et exports — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corriger les exports CSE (points #12/#13 de `docs/afaire.md`) et livrer le script
d'import des élus, de sorte que la réponse d'Elsa ne déclenche plus qu'un chargement de données.

**Architecture:** Trois corrections indépendantes dans le module CSE backend
(`app/modules/cse/`), puis un script d'import autonome dans `backend/scripts/`. Le bug d'export
est reproductible **sans donnée** : c'est une exception silencieuse sur un type, pas un cas limite
de fuseau horaire. Aucune migration, aucun changement de contrat API — le frontend gère déjà les
valeurs corrigées.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, Supabase (postgrest-py), openpyxl, pytest.

## Constat vérifié (à ne pas re-débattre)

1. [cse_service_impl.py:128-130](backend/app/modules/cse/infrastructure/cse_service_impl.py#L128-L130)
   met `days_remaining = None` dès que le mandat est expiré (`end_date < today`).
2. [service.py:21-24](backend/app/modules/cse/application/service.py#L21-L24) — `_to_dict` appelle
   `model_dump()` : `start_date` et `end_date` arrivent dans l'export en objets `datetime.date`,
   **pas** en chaînes ISO.
3. [cse_export_impl.py:31-44](backend/app/modules/cse/infrastructure/cse_export_impl.py#L31-L44) —
   le repli `datetime.fromisoformat(member.get("end_date", ""))` lève `TypeError` sur un objet
   `date`, l'exception est avalée, `days_remaining` reste `None` et **le statut reste « Actif »**.
   → Conséquence : dans `base_elus_cse.xlsx`, **tout mandat expiré sort avec « Jours restants »
   vide et « Statut : Actif »**. C'est exactement l'erreur signalée par Elsa.
4. Même exception avalée sur le formatage des dates :
   [L48](backend/app/modules/cse/infrastructure/cse_export_impl.py#L48),
   [L54](backend/app/modules/cse/infrastructure/cse_export_impl.py#L54) (élus),
   [L159](backend/app/modules/cse/infrastructure/cse_export_impl.py#L159) (heures de délégation),
   [L208](backend/app/modules/cse/infrastructure/cse_export_impl.py#L208) (réunions) — les dates
   sortent en cellule date brute au lieu du `JJ/MM/AAAA` attendu.
5. Le frontend est déjà prêt : `CSEBadge.tsx:47` traite `daysRemaining < 0` (« Expiré depuis N
   jours ») et `ElectedMembersTab.tsx:67` a un repli local. Rendre `days_remaining` négatif ne
   casse rien et **répare l'affichage**.
6. Fichier d'Elsa `data/_inbox/whatsapp-elsa-2026-08-02/00005436-Membres_CSE.xlsx` : 8 titulaires
   (Cartol 2, LEWIS 2, MBC 4), tous rapprochés en base — dont Marie-Noëlle **ENOND**, `nom_usage`
   **DEPLANNE**. La colonne « Date d'entrée » du fichier est la date d'embauche, pas le mandat.
7. `ElectedMemberCreate` ([requests.py:28](backend/app/modules/cse/schemas/requests.py#L28)) exige
   `start_date` **et** `end_date` : sans dates de mandat, aucun élu ne peut être créé.

## Global Constraints

- **Aucune écriture en production** dans ce plan. Le script d'import est en `--dry-run` par
  défaut ; `--apply` ne sera lancé qu'après accord explicite d'Alexandre.
- **Aucune donnée nominative dans un fichier `.py`.** Noms, prénoms et e-mails restent dans
  `data/` (règle du dépôt public). Le script lit le classeur, il ne l'embarque pas.
- **Aucun changement de contrat API** : les champs de `ElectedMemberListItem` ne bougent pas, seule
  la valeur de `days_remaining` change (négative au lieu de `None` sur un mandat expiré).
- Tests lancés depuis `backend/` : `.venv/bin/python -m pytest`.
- Commits en français, sans `Co-Authored-By` ajouté par l'agent (convention du dépôt).

---

### Task 1 : `days_remaining` négatif sur les mandats expirés

**Files:**
- Modify: `backend/app/modules/cse/infrastructure/cse_service_impl.py:128-130`
- Test: `backend/tests/unit/cse/test_elected_members_days_remaining.py` (créer)

**Interfaces:**
- Consumes: rien.
- Produces: `get_elected_members(company_id, active_only)` renvoie des
  `ElectedMemberListItem` dont `days_remaining: int` est **toujours** renseigné —
  négatif si `end_date < aujourd'hui`, `0` le jour même de l'échéance.

- [ ] **Step 1 : écrire le test qui échoue**

Créer `backend/tests/unit/cse/test_elected_members_days_remaining.py` :

```python
"""Un mandat expiré doit sortir avec un nombre de jours négatif, pas avec None.

Sans cela, l'export Excel ne sait pas distinguer un mandat expiré d'un mandat en cours
et affiche tout le monde « Actif ».
"""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from app.modules.cse.infrastructure import cse_service_impl


def _ligne(end_date: date) -> dict:
    return {
        "id": "elu-1",
        "employee_id": "emp-1",
        "role": "titulaire",
        "college": "1er collège",
        "start_date": (end_date - timedelta(days=1461)).isoformat(),
        "end_date": end_date.isoformat(),
        "is_active": True,
        "employees": {
            "id": "emp-1",
            "first_name": "Prenom",
            "last_name": "NOM",
            "job_title": "Opérateur",
        },
    }


def _mock_supabase(lignes: list[dict]) -> MagicMock:
    reponse = MagicMock()
    reponse.data = lignes
    chaine = MagicMock()
    chaine.select.return_value = chaine
    chaine.eq.return_value = chaine
    chaine.gte.return_value = chaine
    chaine.order.return_value = chaine
    chaine.execute.return_value = reponse
    client = MagicMock()
    client.table.return_value = chaine
    return client


def test_mandat_expire_renvoie_un_nombre_de_jours_negatif():
    fin = date.today() - timedelta(days=45)
    with patch.object(cse_service_impl, "supabase", _mock_supabase([_ligne(fin)])):
        membres = cse_service_impl.get_elected_members("co-1", active_only=False)
    assert membres[0].days_remaining == -45


def test_mandat_en_cours_renvoie_un_nombre_de_jours_positif():
    fin = date.today() + timedelta(days=200)
    with patch.object(cse_service_impl, "supabase", _mock_supabase([_ligne(fin)])):
        membres = cse_service_impl.get_elected_members("co-1", active_only=False)
    assert membres[0].days_remaining == 200


def test_mandat_qui_finit_aujourdhui_renvoie_zero():
    with patch.object(cse_service_impl, "supabase", _mock_supabase([_ligne(date.today())])):
        membres = cse_service_impl.get_elected_members("co-1", active_only=False)
    assert membres[0].days_remaining == 0
```

- [ ] **Step 2 : lancer le test, vérifier qu'il échoue**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/cse/test_elected_members_days_remaining.py -v
```

Attendu : `test_mandat_expire_renvoie_un_nombre_de_jours_negatif` ÉCHOUE avec
`assert None == -45`. Les deux autres passent déjà.

- [ ] **Step 3 : corriger la source**

Dans `backend/app/modules/cse/infrastructure/cse_service_impl.py`, remplacer :

```python
        days_remaining = (
            (end_date - date.today()).days if end_date >= date.today() else None
        )
```

par :

```python
        # Négatif si le mandat est expiré : l'export et le badge frontend s'en servent
        # pour distinguer « Actif » d'« Expiré ». Renvoyer None les rendait indistinguables.
        days_remaining = (end_date - date.today()).days
```

- [ ] **Step 4 : lancer les tests, vérifier qu'ils passent**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/cse/ -v
```

Attendu : les 3 nouveaux tests PASSENT, et aucune régression dans `tests/unit/cse/`.

- [ ] **Step 5 : commit**

```bash
git add backend/app/modules/cse/infrastructure/cse_service_impl.py \
        backend/tests/unit/cse/test_elected_members_days_remaining.py
git commit -m "fix(cse): un mandat expiré ne renvoyait plus de nombre de jours"
```

---

### Task 2 : export des élus — statut « Actif » sur les mandats expirés

**Files:**
- Modify: `backend/app/modules/cse/infrastructure/cse_export_impl.py:16-70`
- Test: `backend/tests/unit/cse/test_export_impl_elus.py` (créer)

**Interfaces:**
- Consumes: Task 1 (`days_remaining` toujours renseigné) — mais l'export ne doit **pas**
  en dépendre : il recalcule à partir de `end_date`, qui reste la seule source fiable.
- Produces: `_vers_date(valeur) -> date | None` et `_formater_date(valeur) -> str`, deux
  helpers de module réutilisés par la Task 3.

- [ ] **Step 1 : écrire le test qui échoue**

Créer `backend/tests/unit/cse/test_export_impl_elus.py` :

```python
"""L'export des élus reçoit des objets date (model_dump), pas des chaînes ISO.

Avant correction, datetime.fromisoformat(objet_date) levait TypeError, l'exception
était avalée, et tout mandat expiré sortait « Actif » avec « Jours restants » vide.
"""

import io
from datetime import date, timedelta

import openpyxl

from app.modules.cse.infrastructure.cse_export_impl import export_elected_members


def _membre(fin: date, days_remaining=None) -> dict:
    return {
        "id": "elu-1",
        "employee_id": "emp-1",
        "first_name": "Prenom",
        "last_name": "NOM",
        "job_title": "Opérateur",
        "role": "titulaire",
        "college": "1er collège",
        "start_date": fin - timedelta(days=1461),
        "end_date": fin,
        "is_active": True,
        "days_remaining": days_remaining,
    }


def _lignes(contenu: bytes) -> list[dict]:
    ws = openpyxl.load_workbook(io.BytesIO(contenu)).active
    entetes = [c.value for c in ws[1]]
    return [dict(zip(entetes, [c.value for c in r])) for r in ws.iter_rows(min_row=2)]


def test_mandat_expire_sort_en_statut_expire():
    contenu = export_elected_members([_membre(date.today() - timedelta(days=45))])
    ligne = _lignes(contenu)[0]
    assert ligne["Statut"] == "Expiré"
    assert ligne["Jours restants"] == -45


def test_mandat_qui_expire_bientot():
    contenu = export_elected_members([_membre(date.today() + timedelta(days=30))])
    assert _lignes(contenu)[0]["Statut"] == "Expire bientôt"


def test_mandat_en_cours_reste_actif():
    contenu = export_elected_members([_membre(date.today() + timedelta(days=400))])
    assert _lignes(contenu)[0]["Statut"] == "Actif"


def test_les_dates_sortent_au_format_francais():
    contenu = export_elected_members([_membre(date(2027, 3, 9))])
    ligne = _lignes(contenu)[0]
    assert ligne["Date fin mandat"] == "09/03/2027"
    assert ligne["Date début mandat"] == "09/03/2023"


def test_accepte_aussi_des_chaines_iso():
    membre = _membre(date.today() - timedelta(days=45))
    membre["end_date"] = membre["end_date"].isoformat()
    membre["start_date"] = membre["start_date"].isoformat()
    ligne = _lignes(export_elected_members([membre]))[0]
    assert ligne["Statut"] == "Expiré"


def test_sans_date_de_fin_le_statut_est_inconnu():
    membre = _membre(date.today())
    membre["end_date"] = None
    ligne = _lignes(export_elected_members([membre]))[0]
    assert ligne["Statut"] == "Inconnu"
    assert ligne["Jours restants"] == ""
```

- [ ] **Step 2 : lancer le test, vérifier qu'il échoue**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/cse/test_export_impl_elus.py -v
```

Attendu : `test_mandat_expire_sort_en_statut_expire` ÉCHOUE avec
`assert 'Actif' == 'Expiré'`.

- [ ] **Step 3 : réécrire l'export**

Dans `backend/app/modules/cse/infrastructure/cse_export_impl.py`, remplacer l'import de
`datetime` et la fonction `export_elected_members` (lignes 10 et 16-70) par :

```python
from datetime import date, datetime


def _vers_date(valeur: Any) -> Optional[date]:
    """Normalise une valeur date/datetime/chaîne ISO vers une date. None si illisible.

    Les exports reçoivent des objets date (model_dump) ou des chaînes ISO (dicts bruts) :
    il faut accepter les deux plutôt que d'avaler une TypeError.
    """
    if valeur is None or valeur == "":
        return None
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    if isinstance(valeur, str):
        try:
            return datetime.fromisoformat(valeur).date()
        except ValueError:
            return None
    return None


def _formater_date(valeur: Any) -> str:
    """Rend une date au format JJ/MM/AAAA, ou la valeur telle quelle si illisible."""
    jour = _vers_date(valeur)
    if jour is None:
        return "" if valeur is None else str(valeur)
    return jour.strftime("%d/%m/%Y")


def export_elected_members(members: List[Dict[str, Any]]) -> bytes:
    """Export Excel de la base des élus CSE."""
    headers = [
        "Nom",
        "Prénom",
        "Poste",
        "Rôle CSE",
        "Collège",
        "Date début mandat",
        "Date fin mandat",
        "Jours restants",
        "Statut",
    ]
    aujourd_hui = date.today()
    data = []
    for member in members:
        fin = _vers_date(member.get("end_date"))
        days_remaining = (fin - aujourd_hui).days if fin is not None else None
        if days_remaining is None:
            status = "Inconnu"
        elif days_remaining < 0:
            status = "Expiré"
        elif days_remaining <= 90:
            status = "Expire bientôt"
        else:
            status = "Actif"
        data.append(
            {
                "Nom": member.get("last_name", ""),
                "Prénom": member.get("first_name", ""),
                "Poste": member.get("job_title", ""),
                "Rôle CSE": (member.get("role") or "").capitalize(),
                "Collège": member.get("college", ""),
                "Date début mandat": _formater_date(member.get("start_date")),
                "Date fin mandat": _formater_date(member.get("end_date")),
                "Jours restants": days_remaining if days_remaining is not None else "",
                "Statut": status,
            }
        )
    return generate_xlsx(data, headers, "Base élus CSE")
```

Ajouter `Optional` à l'import `typing` en tête de fichier :

```python
from typing import Any, Dict, List, Optional
```

Note : le statut est désormais calculé **depuis `end_date`**, plus depuis `days_remaining`.
L'export ne dépend donc plus de la Task 1 — les deux corrections se vérifient séparément.

- [ ] **Step 4 : lancer les tests, vérifier qu'ils passent**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/cse/ tests/integration/cse/ -v
```

Attendu : les 6 nouveaux tests PASSENT ; `tests/integration/legacy/test_cse_api_complet.py`
et `tests/integration/cse/` restent au vert.

- [ ] **Step 5 : commit**

```bash
git add backend/app/modules/cse/infrastructure/cse_export_impl.py \
        backend/tests/unit/cse/test_export_impl_elus.py
git commit -m "fix(cse): l'export des élus marquait « Actif » les mandats expirés"
```

---

### Task 3 : dates illisibles dans les exports heures de délégation et réunions

**Files:**
- Modify: `backend/app/modules/cse/infrastructure/cse_export_impl.py:155-161` (heures) et
  `:204-216` (réunions)
- Test: `backend/tests/unit/cse/test_export_impl_dates.py` (créer)

**Interfaces:**
- Consumes: `_formater_date(valeur) -> str` défini en Task 2.
- Produces: rien de nouveau.

- [ ] **Step 1 : écrire le test qui échoue**

Créer `backend/tests/unit/cse/test_export_impl_dates.py` :

```python
"""Les exports heures et réunions reçoivent eux aussi des objets date (model_dump)."""

import io
from datetime import date

import openpyxl

from app.modules.cse.infrastructure.cse_export_impl import (
    export_delegation_hours,
    export_meetings_history,
)


def _cellule(contenu: bytes, feuille: str, ligne: int, colonne: int):
    wb = openpyxl.load_workbook(io.BytesIO(contenu))
    return wb[feuille].cell(row=ligne, column=colonne).value


def test_detail_des_heures_date_au_format_francais():
    heures = [
        {
            "date": date(2026, 7, 9),
            "first_name": "Prenom",
            "last_name": "NOM",
            "duration_hours": 4,
            "source": "propre",
            "reason": "Réunion",
            "meeting_title": "CSE juillet",
        }
    ]
    contenu = export_delegation_hours(heures, [])
    assert _cellule(contenu, "Détail heures", 2, 1) == "09/07/2026"


def test_historique_des_reunions_date_au_format_francais():
    reunions = [
        {
            "title": "CSE juillet",
            "meeting_date": date(2026, 7, 9),
            "meeting_time": "14:00:00",
            "meeting_type": "ordinaire",
            "status": "terminee",
            "location": "Salle A",
            "participant_count": 4,
            "has_minutes": True,
        }
    ]
    contenu = export_meetings_history(reunions)
    wb = openpyxl.load_workbook(io.BytesIO(contenu))
    ws = wb.active
    entetes = [c.value for c in ws[1]]
    ligne = dict(zip(entetes, [c.value for c in ws[2]]))
    assert ligne["Date"] == "09/07/2026"
```

- [ ] **Step 2 : lancer le test, vérifier qu'il échoue**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/cse/test_export_impl_dates.py -v
```

Attendu : les 2 tests ÉCHOUENT — la cellule contient `datetime.date(2026, 7, 9)` au lieu de
la chaîne `"09/07/2026"`.

- [ ] **Step 3 : appliquer le helper aux deux exports**

Dans `export_delegation_hours`, remplacer :

```python
    for row_idx, hour in enumerate(hours, start=2):
        date_str = hour.get("date", "")
        if date_str:
            try:
                date_str = datetime.fromisoformat(date_str).strftime("%d/%m/%Y")
            except Exception:
                pass
        ws_detail.cell(row=row_idx, column=1, value=date_str)
```

par :

```python
    for row_idx, hour in enumerate(hours, start=2):
        ws_detail.cell(row=row_idx, column=1, value=_formater_date(hour.get("date")))
```

Dans la même fonction, remplacer le calcul de la colonne « Période » :

```python
        period_start = item.get("period_start", "")
        period_end = item.get("period_end", "")
        if period_start and period_end:
            try:
                start = datetime.fromisoformat(str(period_start)).strftime("%d/%m/%Y")
                end = datetime.fromisoformat(str(period_end)).strftime("%d/%m/%Y")
                ws_summary.cell(row=row_idx, column=11, value=f"{start} - {end}")
            except Exception:
                ws_summary.cell(
                    row=row_idx, column=11, value=f"{period_start} - {period_end}"
                )
```

par :

```python
        period_start = item.get("period_start")
        period_end = item.get("period_end")
        if period_start and period_end:
            ws_summary.cell(
                row=row_idx,
                column=11,
                value=f"{_formater_date(period_start)} - {_formater_date(period_end)}",
            )
```

Dans `export_meetings_history`, remplacer :

```python
        meeting_date = meeting.get("meeting_date", "")
        if meeting_date:
            try:
                meeting_date = datetime.fromisoformat(meeting_date).strftime("%d/%m/%Y")
            except Exception:
                pass
```

par :

```python
        meeting_date = _formater_date(meeting.get("meeting_date"))
```

- [ ] **Step 4 : lancer les tests, vérifier qu'ils passent**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/cse/ tests/integration/cse/ tests/integration/legacy/test_cse_api_complet.py -v
```

Attendu : tout au vert.

- [ ] **Step 5 : commit**

```bash
git add backend/app/modules/cse/infrastructure/cse_export_impl.py \
        backend/tests/unit/cse/test_export_impl_dates.py
git commit -m "fix(cse): dates illisibles dans les exports heures et réunions"
```

---

### Task 4 : script d'import des élus CSE

**Files:**
- Create: `backend/scripts/import_elus_cse.py`
- Test: `backend/tests/unit/scripts/test_import_elus_cse.py` (créer — les tests de scripts
  vivent sous `tests/unit/scripts/`, cf. `test_comitech_calendar_parser.py` qui importe
  déjà `from scripts.…`)

**Interfaces:**
- Consumes: rien des tâches précédentes.
- Produces:
  - `cle_nom(valeur: str) -> str` — normalise un nom (majuscules, sans accent, sans tiret
    ni espace) pour le rapprochement.
  - `lire_classeur(chemin: Path) -> list[LigneElu]` — lit le classeur d'Elsa.
  - `LigneElu` — dataclass `(societe, nom, prenom, qualite, college, debut_mandat, fin_mandat)`.
  - `ROLES` — correspondance libellé du classeur → rôle en base.

**Décision de conception** — le script lit **uniquement** le classeur d'Elsa. Les dates de mandat
sont attendues soit dans deux colonnes ajoutées au classeur (« Date début mandat », « Date fin
mandat »), soit passées en ligne de commande quand elles sont communes à toute une société
(`--mandat "MONT BLANC COMPOSITE (MBC)=2022-11-18:2026-11-17"`), ce qui est le cas normal :
un mandat CSE court d'une élection à l'autre, pour tous les élus de la société.

- [ ] **Step 1 : écrire le test qui échoue**

Créer `backend/tests/unit/scripts/test_import_elus_cse.py` :

```python
"""Rapprochement des élus du classeur d'Elsa avec les salariés en base.

Cas réel à couvrir : Marie-Noëlle figure au classeur sous « DEPLANNE », qui est son
nom d'usage ; en base son last_name est « ENOND ».
"""

from datetime import date

from scripts.import_elus_cse import (
    ROLES,
    LigneElu,
    cle_nom,
    dates_mandat_par_societe,
    rapprocher,
)


def test_cle_nom_ignore_accents_tirets_espaces_et_casse():
    assert cle_nom("De Barros") == cle_nom("DE BARROS")
    assert cle_nom("Hervé") == cle_nom("HERVE")
    assert cle_nom("Marie-Noelle") == cle_nom("MARIE NOELLE")


def test_roles_connus():
    assert ROLES["Membre titulaire"] == "titulaire"
    assert ROLES["Membre suppléant"] == "suppleant"


def test_rapprochement_sur_le_nom_de_naissance():
    salaries = [
        {"id": "emp-1", "last_name": "BREGEON", "nom_usage": None, "first_name": "EMILE"}
    ]
    ligne = LigneElu("CARTOL", "BREGEON", "Emile", "Membre titulaire", None, None, None)
    assert rapprocher(ligne, salaries) == salaries[0]


def test_rapprochement_sur_le_nom_dusage():
    salaries = [
        {
            "id": "emp-2",
            "last_name": "ENOND",
            "nom_usage": "DEPLANNE",
            "first_name": "MARIE-NOELLE",
        }
    ]
    ligne = LigneElu("CARTOL", "DEPLANNE", "Marie-Noelle", "Membre titulaire", None, None, None)
    assert rapprocher(ligne, salaries) == salaries[0]


def test_homonymes_departages_par_le_prenom():
    salaries = [
        {"id": "a", "last_name": "MARTIN", "nom_usage": None, "first_name": "PAUL"},
        {"id": "b", "last_name": "MARTIN", "nom_usage": None, "first_name": "JEANNE"},
    ]
    ligne = LigneElu("LEWIS", "MARTIN", "Jeanne", "Membre titulaire", None, None, None)
    assert rapprocher(ligne, salaries)["id"] == "b"


def test_aucun_rapprochement_renvoie_none():
    ligne = LigneElu("LEWIS", "INCONNU", "Zoe", "Membre titulaire", None, None, None)
    assert rapprocher(ligne, []) is None


def test_dates_de_mandat_en_ligne_de_commande():
    resultat = dates_mandat_par_societe(["CARTOL=2023-06-15:2027-06-14"])
    assert resultat["CARTOL"] == (date(2023, 6, 15), date(2027, 6, 14))
```

- [ ] **Step 2 : lancer le test, vérifier qu'il échoue**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/scripts/test_import_elus_cse.py -v
```

Attendu : ÉCHEC avec `ModuleNotFoundError: No module named 'scripts.import_elus_cse'`.

- [ ] **Step 3 : écrire le script**

Créer `backend/scripts/import_elus_cse.py` :

```python
"""Charge les élus CSE depuis le classeur transmis par Elsa.

Le classeur ne contient pas les dates de mandat : la colonne « Date d'entrée » est la
date d'embauche du salarié, pas le mandat. Les dates viennent donc soit de deux colonnes
ajoutées au classeur, soit de --mandat (cas normal : un mandat par société, commun à
tous ses élus).

Aucun nom n'est écrit dans ce fichier : le dépôt est public, les données nominatives
restent sous data/.

Usage :
    python scripts/import_elus_cse.py --fichier <classeur.xlsx> --dry-run
    python scripts/import_elus_cse.py --fichier <classeur.xlsx> \\
        --mandat "CARTOL=2023-06-15:2027-06-14" --apply
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROLES = {
    "Membre titulaire": "titulaire",
    "Membre suppléant": "suppleant",
    "Membre suppleant": "suppleant",
    "Secrétaire": "secretaire",
    "Secretaire": "secretaire",
    "Trésorier": "tresorier",
    "Tresorier": "tresorier",
}

# Le classeur nomme les sociétés autrement que la base.
SOCIETES = {
    "CARTOL": "Cartol Industrie",
    "LEWIS": "LEWIS",
    "MONT BLANC COMPOSITE (MBC)": "Mont Blanc Composite",
    "MBC": "Mont Blanc Composite",
    "COLORPLAST": "Colorplast",
    "COMITECH": "Comitech Composite",
    "MAJI": "MAJI",
    "ZONE 404": "Zone 404 Mars",
}


@dataclass
class LigneElu:
    societe: str
    nom: str
    prenom: str
    qualite: str
    college: Optional[str]
    debut_mandat: Optional[date]
    fin_mandat: Optional[date]


def cle_nom(valeur: Optional[str]) -> str:
    """Majuscules, sans accent, sans tiret ni espace — pour comparer deux noms."""
    sans_accent = unicodedata.normalize("NFD", (valeur or "").upper())
    sans_accent = sans_accent.encode("ascii", "ignore").decode()
    return sans_accent.replace("-", "").replace("'", "").replace(" ", "").strip()


def _vers_date(valeur: Any) -> Optional[date]:
    if valeur in (None, ""):
        return None
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    texte = str(valeur).strip()
    for motif in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texte, motif).date()
        except ValueError:
            continue
    return None


def lire_classeur(chemin: Path) -> List[LigneElu]:
    """Lit le classeur d'Elsa. Colonnes de mandat facultatives."""
    import openpyxl

    ws = openpyxl.load_workbook(chemin, data_only=True).active
    entetes = [str(c.value or "").strip() for c in ws[1]]
    lignes: List[LigneElu] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        valeurs = dict(zip(entetes, row))
        if not valeurs.get("Nom"):
            continue
        lignes.append(
            LigneElu(
                societe=str(valeurs.get("Société") or "").strip(),
                nom=str(valeurs.get("Nom") or "").strip(),
                prenom=str(valeurs.get("Prénom") or "").strip(),
                qualite=str(valeurs.get("Qualité") or "").strip(),
                college=(str(valeurs.get("Collège")).strip()
                         if valeurs.get("Collège") not in (None, "", "Non précisé")
                         else None),
                debut_mandat=_vers_date(valeurs.get("Date début mandat")),
                fin_mandat=_vers_date(valeurs.get("Date fin mandat")),
            )
        )
    return lignes


def dates_mandat_par_societe(
    arguments: List[str],
) -> Dict[str, Tuple[date, date]]:
    """Convertit --mandat "SOCIETE=AAAA-MM-JJ:AAAA-MM-JJ" en table de correspondance."""
    resultat: Dict[str, Tuple[date, date]] = {}
    for argument in arguments or []:
        societe, _, periode = argument.partition("=")
        debut_texte, _, fin_texte = periode.partition(":")
        debut = _vers_date(debut_texte)
        fin = _vers_date(fin_texte)
        if debut is None or fin is None:
            raise SystemExit(
                f"--mandat illisible : {argument!r} "
                '(attendu "SOCIETE=AAAA-MM-JJ:AAAA-MM-JJ")'
            )
        if fin < debut:
            raise SystemExit(f"--mandat : la fin précède le début ({argument!r})")
        resultat[societe.strip().upper()] = (debut, fin)
    return resultat


def rapprocher(
    ligne: LigneElu, salaries: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Retrouve le salarié correspondant, par nom de naissance ou nom d'usage."""
    cible = cle_nom(ligne.nom)
    candidats = [
        s
        for s in salaries
        if cle_nom(s.get("last_name")) == cible or cle_nom(s.get("nom_usage")) == cible
    ]
    if not candidats:
        return None
    if len(candidats) == 1:
        return candidats[0]
    prenom = cle_nom(ligne.prenom)
    exacts = [s for s in candidats if cle_nom(s.get("first_name")) == prenom]
    return exacts[0] if len(exacts) == 1 else None


def _charger_base() -> Tuple[Any, Dict[str, str]]:
    import os

    from dotenv import load_dotenv
    from supabase import create_client

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"],
    )
    societes = {
        s["company_name"]: s["id"]
        for s in client.table("companies").select("id,company_name").execute().data
    }
    return client, societes


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--fichier", required=True, type=Path)
    parseur.add_argument("--mandat", action="append", default=[])
    groupe = parseur.add_mutually_exclusive_group()
    groupe.add_argument("--dry-run", action="store_true", default=True)
    groupe.add_argument("--apply", action="store_true")
    options = parseur.parse_args()

    lignes = lire_classeur(options.fichier)
    mandats = dates_mandat_par_societe(options.mandat)
    client, societes = _charger_base()
    print(f"Base ciblée : {client.supabase_url}")

    salaries = (
        client.table("employees")
        .select("id,company_id,last_name,nom_usage,first_name,employment_status")
        .execute()
        .data
    )
    existants = {
        (e["employee_id"], e["start_date"])
        for e in client.table("cse_elected_members")
        .select("employee_id,start_date")
        .execute()
        .data
    }

    a_creer, bloques = [], []
    for ligne in lignes:
        nom_base = SOCIETES.get(ligne.societe.upper())
        company_id = societes.get(nom_base or "")
        debut, fin = ligne.debut_mandat, ligne.fin_mandat
        if debut is None or fin is None:
            depuis_option = mandats.get(ligne.societe.upper())
            if depuis_option:
                debut, fin = depuis_option
        role = ROLES.get(ligne.qualite)
        salarie = rapprocher(
            ligne, [s for s in salaries if s["company_id"] == company_id]
        )

        if company_id is None:
            bloques.append((ligne, "société inconnue en base"))
        elif salarie is None:
            bloques.append((ligne, "aucun salarié rapproché"))
        elif role is None:
            bloques.append((ligne, f"qualité inconnue : {ligne.qualite!r}"))
        elif debut is None or fin is None:
            bloques.append((ligne, "dates de mandat manquantes"))
        elif (salarie["id"], debut.isoformat()) in existants:
            print(f"  déjà en base  {ligne.nom} {ligne.prenom}")
        else:
            a_creer.append(
                {
                    "company_id": company_id,
                    "employee_id": salarie["id"],
                    "role": role,
                    "college": ligne.college,
                    "start_date": debut.isoformat(),
                    "end_date": fin.isoformat(),
                    "is_active": True,
                }
            )
            print(
                f"  à créer       {ligne.nom} {ligne.prenom} — {role} — "
                f"{debut:%d/%m/%Y} → {fin:%d/%m/%Y}"
            )

    for ligne, motif in bloques:
        print(f"  BLOQUÉ        {ligne.societe} {ligne.nom} {ligne.prenom} : {motif}")

    print(f"\n{len(a_creer)} mandat(s) à créer, {len(bloques)} bloqué(s).")

    if not options.apply:
        print("Mode simulation — rien n'a été écrit. Relancer avec --apply pour écrire.")
        return 1 if bloques else 0

    if bloques:
        print("Écriture refusée : résoudre d'abord les lignes bloquées.")
        return 1

    for mandat in a_creer:
        client.table("cse_elected_members").insert(mandat).execute()
    print(f"{len(a_creer)} mandat(s) créé(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4 : lancer les tests, vérifier qu'ils passent**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/scripts/test_import_elus_cse.py -v
```

Attendu : les 7 tests PASSENT.

- [ ] **Step 5 : simulation sur le classeur réel**

```bash
cd backend && .venv/bin/python scripts/import_elus_cse.py \
  --fichier ../data/_inbox/whatsapp-elsa-2026-08-02/00005436-Membres_CSE.xlsx --dry-run
```

Attendu, tant qu'Elsa n'a pas répondu : les 8 lignes ressortent **BLOQUÉ … dates de mandat
manquantes**, aucune en « société inconnue » ni « aucun salarié rapproché ». C'est le résultat
qui prouve que le rapprochement fonctionne sur les 8, ENOND/DEPLANNE comprise.

- [ ] **Step 6 : commit**

```bash
git add backend/scripts/import_elus_cse.py backend/tests/unit/scripts/test_import_elus_cse.py
git commit -m "feat(cse): script d'import des élus depuis le classeur d'Elsa"
```

---

### Task 5 : recette de bout en bout sur l'environnement de test

**Files:**
- Aucun fichier modifié. Recette manuelle sur l'environnement de test uniquement.

**Interfaces:**
- Consumes: Tasks 1 à 4.
- Produces: la preuve que l'export corrigé distingue bien un mandat expiré — ce que
  l'audit du 26/07 n'avait pas pu vérifier, la table étant vide.

- [ ] **Step 1 : charger les 8 élus dans l'environnement de test avec des dates provisoires**

Pointer explicitement sur la base de test — **`backend/.env` cible la production**
(`slleauhyjnmiawosvlcg`), un lancement sans surcharge écrirait donc en prod. Les variables
`SUPABASE_TEST_URL` / `SUPABASE_TEST_SERVICE_KEY` sont celles déjà utilisées par
`scripts/test_env/refresh_from_prod.sh`. Vérifier la ligne « Base ciblée : » affichée par le
script avant de laisser tourner.

```bash
cd backend && SUPABASE_URL="$SUPABASE_TEST_URL" \
  SUPABASE_SERVICE_ROLE_KEY="$SUPABASE_TEST_SERVICE_KEY" \
  .venv/bin/python scripts/import_elus_cse.py \
    --fichier ../data/_inbox/whatsapp-elsa-2026-08-02/00005436-Membres_CSE.xlsx \
    --mandat "CARTOL=2019-01-10:2023-01-09" \
    --mandat "LEWIS=2025-10-01:2029-09-30" \
    --mandat "MONT BLANC COMPOSITE (MBC)=2022-11-18:2026-11-17" \
    --apply
```

Les dates de Cartol sont volontairement dans le passé : c'est le cas qui reproduisait le bug.

- [ ] **Step 2 : télécharger l'export et vérifier les trois statuts**

Depuis l'environnement de test, page RH > CSE > Base des élus > Exporter. Vérifier dans
`base_elus_cse.xlsx` :

| Société | Attendu « Statut » | Attendu « Jours restants » |
|---|---|---|
| Cartol (2 lignes) | Expiré | nombre négatif |
| MBC (4 lignes) | Expire bientôt | entre 0 et 90 |
| LEWIS (2 lignes) | Actif | > 90 |

Et les colonnes de dates au format `JJ/MM/AAAA`, pas en cellule date brute.

- [ ] **Step 3 : vérifier le badge à l'écran**

Sur la fiche d'un élu Cartol : le badge CSE doit afficher « Expiré depuis N jours »
(`CSEBadge.tsx:84`), ce qu'il ne pouvait pas faire tant que `days_remaining` valait `None`.

- [ ] **Step 4 : nettoyer la base de test**

Les 8 mandats provisoires disparaîtront à la prochaine resynchro depuis la production. Si la
recette doit être rejouée avant, les supprimer explicitement plutôt que de les laisser fausser
un test ultérieur.

- [ ] **Step 5 : consigner le résultat**

Renseigner le compte rendu du point #12 dans [docs/afaire.md](docs/afaire.md), sous la ligne du
point, dans le style des points MOI.

---

## Ce qui reste suspendu à Elsa (hors de ce plan)

Rien de ce qui précède n'attend sa réponse. Ne dépendent d'elle que :

1. **Les dates d'élection et de fin de mandat** par société → sans elles, `--apply` en production
   est impossible (contrainte de `ElectedMemberCreate`).
2. **Les suppléants** — le classeur ne contient que des titulaires.
3. **Le collège** pour Cartol et LEWIS (« Non précisé » au classeur).
4. **Le secrétaire** (et le trésorier) de chaque CSE.
5. **Colorplast, MAJI, Zone 404** : CSE ou PV de carence ? Celui de Comitech est expiré depuis le
   06/09/2023 (`company_cse_settings.carence_valid_until`).
6. **L'export fautif qu'elle a constaté**, pour confirmer que la cause est bien celle corrigée ici
   et pas une seconde anomalie.

Le point #13 (génération de la BDES, 8-10 jours) reste entièrement bloqué sur son tableau : il
définit la cible et rien ne peut démarrer sans lui.
