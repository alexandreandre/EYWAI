# Export Excel des titres de séjour — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter un bouton d'export Excel sur la page RH « Titres de séjour », produisant une fiche de suivi de 13 colonnes pour les salariés affichés à l'écran.

**Architecture:** Le serveur fabrique le fichier ; le navigateur envoie la liste des identifiants des lignes qu'il affiche, jamais les critères de filtrage. Une fonction de fabrication (`build_residence_permits_xlsx`) ignore tout de HTTP et de l'entreprise active, ce qui la rend réutilisable par un futur envoi planifié. Le serveur ne fait jamais confiance aux identifiants reçus : il borne la lecture à l'entreprise active.

**Tech Stack:** FastAPI, Pydantic, Supabase (PostgREST), `openpyxl` via `app.shared.utils.export.generate_xlsx`, React + TypeScript, axios, vitest.

**Spec :** `docs/superpowers/specs/2026-07-31-export-excel-titres-sejour-design.md`

## Global Constraints

- Tout le code, les commentaires et les messages d'erreur sont **en français**.
- Le module `residence_permits` respecte le découpage `domain / application / infrastructure / schemas / api`. Aucun accès DB hors `infrastructure`, aucune logique métier dans le router.
- Le contrôle d'accès passe par `_require_rh_company_context` déjà présent dans `api/router.py`. Ne pas le réécrire.
- Toute lecture d'employés pour l'export applique **les trois bornes** de la route liste : `company_id` de l'entreprise active, `is_subject_to_residence_permit = true`, `employment_status IN ('actif','en_sortie')`.
- Ne rien changer à `ResidencePermitListItem`, à la route `GET /api/residence-permits`, au tri, aux filtres ni au tableau affiché.
- Réutiliser `app.shared.utils.export.generate_xlsx` — ne pas réimplémenter la génération XLSX.
- Marqueurs pytest : `pytest.mark.unit` pour `tests/unit/**`, `pytest.mark.integration` pour `tests/integration/**`.
- Commandes depuis `backend/` : `.venv/bin/python -m pytest`. Depuis `frontend/` : `npm run test`.
- Le seuil applicatif d'anticipation (`ANTICIPATION_THRESHOLD_DAYS = 30`) n'est pas modifié par ce plan.

## Structure des fichiers

| Fichier | Responsabilité |
|---|---|
| `backend/app/modules/residence_permits/infrastructure/export_xlsx.py` *(créé)* | Mise en forme des valeurs et fabrication des octets XLSX. Ne connaît ni HTTP ni entreprise active. |
| `backend/app/modules/residence_permits/domain/interfaces.py` *(modifié)* | Nouveau port `IResidencePermitExportReader`, distinct du port de liste. |
| `backend/app/modules/residence_permits/infrastructure/queries.py` *(modifié)* | Requête de lecture bornée pour l'export. |
| `backend/app/modules/residence_permits/infrastructure/repository.py` *(modifié)* | Implémente le nouveau port. |
| `backend/app/modules/residence_permits/application/exports.py` *(créé)* | Garde-fous, restauration de l'ordre demandé, orchestration. |
| `backend/app/modules/residence_permits/schemas/requests.py` *(modifié)* | `ResidencePermitExportRequest`. |
| `backend/app/modules/residence_permits/api/router.py` *(modifié)* | Route `POST /api/residence-permits/export`. |
| `frontend/src/lib/downloadBlob.ts` *(modifié)* | `parseContentDispositionFilename`, extrait pour être testable. |
| `frontend/src/api/residencePermits.ts` *(modifié)* | Appel de l'export, lecture du nom de fichier, message d'erreur depuis un corps Blob. |
| `frontend/src/pages/rh/ResidencePermits.tsx` *(modifié)* | Bouton et état d'attente. |

**Note sur les tests frontend :** `frontend/vitest.config.ts` utilise `environment: "node"`. Il n'y a ni jsdom ni testing-library dans le dépôt : **aucun test de composant React n'est possible**. La spec prévoyait deux tests d'interface ; ils sont remplacés par un test de `parseContentDispositionFilename` (fonction pure) et par la couverture backend. Écart assumé, à ne pas contourner en ajoutant jsdom dans le cadre de ce plan.

---

### Task 1 : Fabrication du fichier XLSX

**Files:**
- Create: `backend/app/modules/residence_permits/infrastructure/export_xlsx.py`
- Test: `backend/tests/unit/residence_permits/test_export_xlsx.py`

**Interfaces:**
- Consumes: `app.shared.utils.export.generate_xlsx(data: List[Dict[str, Any]], headers: List[str], sheet_name: str) -> bytes`
- Produces:
  - `EXPORT_HEADERS: List[str]` (13 libellés, dans l'ordre)
  - `SHEET_NAME: str`
  - `build_residence_permits_xlsx(rows: List[Dict[str, Any]], company_name: str) -> bytes`
  - `build_export_filename(company_name: str, today: Optional[date] = None) -> str`

- [ ] **Step 1: Créer le dossier de tests**

```bash
mkdir -p backend/tests/unit/residence_permits
touch backend/tests/unit/residence_permits/__init__.py
```

- [ ] **Step 2: Écrire les tests qui échouent**

Créer `backend/tests/unit/residence_permits/test_export_xlsx.py` :

```python
"""
Fabrication du fichier XLSX des titres de séjour.

Les tests relisent le classeur produit : ils valident ce qu'Elsa ouvrira dans Excel,
pas la structure intermédiaire. Le champ `residence_permit_type` vaut NULL pour les
43 salariés soumis en production ; une cellule vide, jamais « None », est donc le cas
nominal et non un cas limite.
"""

from __future__ import annotations

import io
from datetime import date

import pytest
from openpyxl import load_workbook

from app.modules.residence_permits.infrastructure.export_xlsx import (
    EXPORT_HEADERS,
    build_export_filename,
    build_residence_permits_xlsx,
)

pytestmark = pytest.mark.unit


def _row(**kwargs):
    base = {
        "id": "emp-1",
        "first_name": "Dieu Merci",
        "last_name": "LANKOKO MVUKI",
        "matricule": "000123",
        "job_title": "Opérateur",
        "hire_date": "2023-04-03",
        "nationalite": "CONGOLAISE",
        "employment_status": "actif",
        "residence_permit_status": "expired",
        "residence_permit_type": None,
        "residence_permit_number": "9912345678",
        "residence_permit_expiry_date": "2026-01-28",
        "residence_permit_days_remaining": -184,
    }
    base.update(kwargs)
    return base


def _sheet(rows, company_name="Mont Blanc Composite"):
    content = build_residence_permits_xlsx(rows, company_name)
    return load_workbook(io.BytesIO(content)).active


def _values(ws, row_idx):
    return [c.value for c in ws[row_idx]]


def test_entetes_dans_l_ordre():
    ws = _sheet([_row()])
    assert _values(ws, 1) == EXPORT_HEADERS
    assert len(EXPORT_HEADERS) == 13


def test_ligne_complete():
    ws = _sheet([_row()])
    assert _values(ws, 2) == [
        "LANKOKO MVUKI",
        "Dieu Merci",
        "000123",
        "Mont Blanc Composite",
        "Opérateur",
        "03/04/2023",
        "CONGOLAISE",
        "Actif",
        "Expiré",
        "",
        "9912345678",
        "28/01/2026",
        -184,
    ]


def test_dates_au_format_francais():
    ws = _sheet([_row(hire_date=date(2024, 12, 1), residence_permit_expiry_date="2027-02-09")])
    ligne = _values(ws, 2)
    assert ligne[5] == "01/12/2024"
    assert ligne[11] == "09/02/2027"


@pytest.mark.parametrize(
    "statut,libelle",
    [
        ("expired", "Expiré"),
        ("to_renew", "À renouveler"),
        ("to_complete", "À compléter"),
        ("valid", "Valide"),
        (None, "À compléter"),
    ],
)
def test_libelles_de_statut(statut, libelle):
    ws = _sheet([_row(residence_permit_status=statut)])
    assert _values(ws, 2)[8] == libelle


def test_statut_emploi_en_toutes_lettres():
    ws = _sheet([_row(employment_status="en_sortie")])
    assert _values(ws, 2)[7] == "En sortie"


def test_valeurs_absentes_donnent_une_cellule_vide():
    """Ni « None », ni « — » : une cellule vide, qu'Excel sait filtrer et trier."""
    ws = _sheet(
        [
            _row(
                residence_permit_type=None,
                residence_permit_number=None,
                residence_permit_expiry_date=None,
                residence_permit_days_remaining=None,
                job_title=None,
                nationalite=None,
            )
        ]
    )
    ligne = _values(ws, 2)
    for index in (4, 6, 9, 10, 11, 12):
        assert ligne[index] in ("", None), f"colonne {index} = {ligne[index]!r}"


def test_jours_restants_negatif_pour_un_titre_expire():
    """Le nombre reste un nombre : Excel doit pouvoir trier par urgence."""
    ws = _sheet([_row(residence_permit_days_remaining=-184)])
    valeur = _values(ws, 2)[12]
    assert valeur == -184
    assert isinstance(valeur, int)


def test_ordre_des_lignes_preserve():
    ws = _sheet([_row(id="a", last_name="AAA"), _row(id="b", last_name="BBB")])
    assert _values(ws, 2)[0] == "AAA"
    assert _values(ws, 3)[0] == "BBB"


def test_aucune_ligne_produit_un_classeur_avec_entetes():
    ws = _sheet([])
    assert _values(ws, 1) == EXPORT_HEADERS
    assert ws.max_row == 1


def test_nom_de_fichier():
    assert (
        build_export_filename("Mont Blanc Composite", date(2026, 7, 31))
        == "titres-de-sejour_mont-blanc-composite_2026-07-31.xlsx"
    )


def test_nom_de_fichier_accents_et_ponctuation():
    assert (
        build_export_filename("Cartol Industrie (S.A.)", date(2026, 7, 31))
        == "titres-de-sejour_cartol-industrie-s-a_2026-07-31.xlsx"
    )


def test_nom_de_fichier_societe_vide():
    assert (
        build_export_filename("", date(2026, 7, 31))
        == "titres-de-sejour_entreprise_2026-07-31.xlsx"
    )
```

- [ ] **Step 3: Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/residence_permits/test_export_xlsx.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.modules.residence_permits.infrastructure.export_xlsx'`

- [ ] **Step 4: Écrire l'implémentation**

Créer `backend/app/modules/residence_permits/infrastructure/export_xlsx.py` :

```python
"""
Fabrication du fichier XLSX des titres de séjour.

Ce module ne connaît ni HTTP, ni entreprise active, ni provenance des lignes : il
reçoit des lignes déjà lues et enrichies du statut calculé. C'est ce qui le rend
réutilisable par un envoi planifié (cf. notifications/application/hr_deadline_reminders),
qui choisira ses propres lignes sans passer par un écran.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.shared.utils.export import generate_xlsx

SHEET_NAME = "Titres de séjour"

COL_NOM = "Nom"
COL_PRENOM = "Prénom"
COL_MATRICULE = "Matricule"
COL_SOCIETE = "Société"
COL_POSTE = "Poste"
COL_DATE_ENTREE = "Date d'entrée"
COL_NATIONALITE = "Nationalité"
COL_STATUT_EMPLOI = "Statut d'emploi"
COL_STATUT_TITRE = "Statut du titre"
COL_TYPE_TITRE = "Type de titre"
COL_NUMERO_TITRE = "Numéro de titre"
COL_DATE_EXPIRATION = "Date d'expiration"
COL_JOURS_RESTANTS = "Jours restants"

EXPORT_HEADERS: List[str] = [
    COL_NOM,
    COL_PRENOM,
    COL_MATRICULE,
    COL_SOCIETE,
    COL_POSTE,
    COL_DATE_ENTREE,
    COL_NATIONALITE,
    COL_STATUT_EMPLOI,
    COL_STATUT_TITRE,
    COL_TYPE_TITRE,
    COL_NUMERO_TITRE,
    COL_DATE_EXPIRATION,
    COL_JOURS_RESTANTS,
]

# Un statut absent signifie « données incomplètes » : c'est exactement ce que le
# calculateur renvoie pour un salarié soumis sans date d'expiration.
_STATUT_TITRE_LABELS = {
    "expired": "Expiré",
    "to_renew": "À renouveler",
    "to_complete": "À compléter",
    "valid": "Valide",
}
_STATUT_TITRE_DEFAUT = "À compléter"

_STATUT_EMPLOI_LABELS = {
    "actif": "Actif",
    "en_sortie": "En sortie",
}


def _texte(value: Any) -> str:
    """Cellule vide plutôt que « None » : Excel doit pouvoir filtrer sur le vide."""
    if value is None:
        return ""
    return str(value)


def _date_fr(value: Any) -> str:
    """Formate en JJ/MM/AAAA ; rend la valeur brute si elle n'est pas une date."""
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    try:
        return date.fromisoformat(str(value)[:10]).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(value)


def _statut_titre(value: Any) -> str:
    return _STATUT_TITRE_LABELS.get(str(value or ""), _STATUT_TITRE_DEFAUT)


def _statut_emploi(value: Any) -> str:
    brut = str(value or "")
    return _STATUT_EMPLOI_LABELS.get(brut, brut)


def _jours_restants(value: Any) -> Any:
    """Reste un entier — un titre expiré porte une valeur négative, triable dans Excel."""
    if value is None or value == "":
        return ""
    try:
        return int(value)
    except (TypeError, ValueError):
        return ""


def _ligne_export(row: Dict[str, Any], company_name: str) -> Dict[str, Any]:
    return {
        COL_NOM: _texte(row.get("last_name")),
        COL_PRENOM: _texte(row.get("first_name")),
        COL_MATRICULE: _texte(row.get("matricule")),
        COL_SOCIETE: _texte(company_name),
        COL_POSTE: _texte(row.get("job_title")),
        COL_DATE_ENTREE: _date_fr(row.get("hire_date")),
        COL_NATIONALITE: _texte(row.get("nationalite")),
        COL_STATUT_EMPLOI: _statut_emploi(row.get("employment_status")),
        COL_STATUT_TITRE: _statut_titre(row.get("residence_permit_status")),
        COL_TYPE_TITRE: _texte(row.get("residence_permit_type")),
        COL_NUMERO_TITRE: _texte(row.get("residence_permit_number")),
        COL_DATE_EXPIRATION: _date_fr(row.get("residence_permit_expiry_date")),
        COL_JOURS_RESTANTS: _jours_restants(row.get("residence_permit_days_remaining")),
    }


def build_residence_permits_xlsx(
    rows: List[Dict[str, Any]], company_name: str
) -> bytes:
    """
    Fabrique le classeur à partir de lignes déjà enrichies du statut calculé.

    L'ordre des lignes reçues est conservé tel quel : c'est l'appelant qui décide
    du tri (à l'écran, l'ordre d'urgence affiché).
    """
    data = [_ligne_export(row, company_name) for row in rows]
    return generate_xlsx(data, EXPORT_HEADERS, SHEET_NAME)


def _slug(value: str) -> str:
    """Réduit un nom de société aux caractères sûrs dans un nom de fichier."""
    normalise = unicodedata.normalize("NFKD", str(value or ""))
    ascii_only = normalise.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")


def build_export_filename(company_name: str, today: Optional[date] = None) -> str:
    """Nom du fichier proposé au téléchargement."""
    reference = today or date.today()
    return f"titres-de-sejour_{_slug(company_name) or 'entreprise'}_{reference.isoformat()}.xlsx"
```

- [ ] **Step 5: Lancer les tests pour vérifier qu'ils passent**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/residence_permits/test_export_xlsx.py -q`
Expected: PASS — 15 tests

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/residence_permits/infrastructure/export_xlsx.py backend/tests/unit/residence_permits/
git commit -m "feat(titres-sejour): fabrication du fichier XLSX de suivi"
```

---

### Task 2 : Lecture bornée à l'entreprise active

**Files:**
- Modify: `backend/app/modules/residence_permits/infrastructure/queries.py`
- Modify: `backend/app/modules/residence_permits/domain/interfaces.py`
- Modify: `backend/app/modules/residence_permits/infrastructure/repository.py`
- Test: `backend/tests/unit/residence_permits/test_export_queries.py`

**Interfaces:**
- Consumes: `app.core.database.get_supabase_client`
- Produces:
  - `fetch_employees_for_residence_permits_export(company_id: str, employee_ids: List[str]) -> List[dict]`
  - `IResidencePermitExportReader.get_employees_for_export(company_id: str, employee_ids: List[str]) -> List[Dict[str, Any]]`
  - `ResidencePermitListRepository.get_employees_for_export(...)` (même signature)

**Pourquoi un port distinct :** `IResidencePermitListReader` est déjà implémenté ailleurs ; ajouter une méthode abstraite à une ABC existante casse tout implémenteur. Un second port, implémenté par la même classe, évite ce couplage.

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `backend/tests/unit/residence_permits/test_export_queries.py` :

```python
"""
Lecture des salariés à exporter.

Le test central est celui du cloisonnement : le serveur ne fait jamais confiance
aux identifiants reçus du navigateur. Sans le filtre sur `company_id`, une requête
modifiée exporterait les salariés d'une autre société.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.residence_permits.infrastructure.queries import (
    fetch_employees_for_residence_permits_export,
)

pytestmark = pytest.mark.unit

COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture
def table():
    """Client Supabase simulé : chaque filtre renvoie le même objet chaînable."""
    with patch(
        "app.modules.residence_permits.infrastructure.queries._get_client"
    ) as get_client:
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.in_.return_value = chain
        chain.execute.return_value = MagicMock(data=[{"id": "emp-1"}])
        client = MagicMock()
        client.table.return_value = chain
        get_client.return_value = client
        yield chain


def test_borne_sur_l_entreprise_active(table):
    """Garde-fou central : le cloisonnement entre sociétés."""
    fetch_employees_for_residence_permits_export(COMPANY_ID, ["emp-1"])

    assert ("company_id", COMPANY_ID) in [c.args for c in table.eq.call_args_list]


def test_reprend_les_bornes_de_la_route_liste(table):
    """Mêmes filtres que la liste : soumis au titre, et en emploi."""
    fetch_employees_for_residence_permits_export(COMPANY_ID, ["emp-1"])

    assert ("is_subject_to_residence_permit", True) in [
        c.args for c in table.eq.call_args_list
    ]
    assert ("employment_status", ["actif", "en_sortie"]) in [
        c.args for c in table.in_.call_args_list
    ]


def test_filtre_sur_les_identifiants_demandes(table):
    fetch_employees_for_residence_permits_export(COMPANY_ID, ["emp-1", "emp-2"])

    assert ("id", ["emp-1", "emp-2"]) in [c.args for c in table.in_.call_args_list]


def test_liste_vide_ne_declenche_aucune_requete(table):
    """Sans identifiant, `IN ()` ramènerait toute l'entreprise : on ne requête pas."""
    assert fetch_employees_for_residence_permits_export(COMPANY_ID, []) == []
    table.execute.assert_not_called()


def test_colonnes_enrichies_demandees(table):
    fetch_employees_for_residence_permits_export(COMPANY_ID, ["emp-1"])

    colonnes = table.select.call_args.args[0]
    for attendue in ("matricule", "job_title", "hire_date", "nationalite"):
        assert attendue in colonnes


def test_retourne_une_liste_vide_si_aucune_donnee(table):
    table.execute.return_value = MagicMock(data=None)

    assert fetch_employees_for_residence_permits_export(COMPANY_ID, ["emp-1"]) == []
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/residence_permits/test_export_queries.py -q`
Expected: FAIL — `ImportError: cannot import name 'fetch_employees_for_residence_permits_export'`

- [ ] **Step 3: Ajouter la requête**

Dans `backend/app/modules/residence_permits/infrastructure/queries.py`, ajouter à la fin du fichier :

```python
EXPORT_COLUMNS = (
    "id, first_name, last_name, matricule, job_title, hire_date, nationalite, "
    "is_subject_to_residence_permit, residence_permit_expiry_date, "
    "residence_permit_type, residence_permit_number, employment_status"
)


def fetch_employees_for_residence_permits_export(
    company_id: str, employee_ids: List[str]
) -> List[dict]:
    """
    Employés désignés par le navigateur, bornés à l'entreprise active.

    Les identifiants viennent du client : ils désignent, ils n'autorisent pas. Les
    trois filtres de la route liste sont donc réappliqués ici, `company_id` en tête.
    Un identifiant hors périmètre disparaît simplement du résultat.
    """
    if not employee_ids:
        return []
    client = _get_client()
    response = (
        client.table("employees")
        .select(EXPORT_COLUMNS)
        .eq("company_id", company_id)
        .eq("is_subject_to_residence_permit", True)
        .in_("employment_status", ["actif", "en_sortie"])
        .in_("id", list(employee_ids))
        .execute()
    )
    return list(response.data or [])
```

- [ ] **Step 4: Ajouter le port**

Dans `backend/app/modules/residence_permits/domain/interfaces.py`, ajouter à la fin du fichier :

```python
class IResidencePermitExportReader(ABC):
    """
    Lit les employés désignés pour l'export, bornés à une entreprise.

    Port distinct de IResidencePermitListReader : la liste et l'export ne prennent
    pas les mêmes paramètres, et ajouter une méthode abstraite à un port existant
    casserait ses implémenteurs.
    """

    @abstractmethod
    def get_employees_for_export(
        self, company_id: str, employee_ids: List[str]
    ) -> List[Dict[str, Any]]:
        pass
```

- [ ] **Step 5: Implémenter le port dans le repository**

Remplacer intégralement `backend/app/modules/residence_permits/infrastructure/repository.py` par :

```python
"""
Repository residence_permits : implémentation des ports de lecture.

Délègue aux queries infrastructure. Aucune entité persistée dans ce module.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.modules.residence_permits.domain.interfaces import (
    IResidencePermitExportReader,
    IResidencePermitListReader,
)
from app.modules.residence_permits.infrastructure.queries import (
    fetch_employees_for_residence_permits_export,
    fetch_employees_for_residence_permits_list,
)


class ResidencePermitListRepository(
    IResidencePermitListReader, IResidencePermitExportReader
):
    """Lit les employés soumis au titre de séjour, en liste ou pour l'export."""

    def get_employees_subject_for_company(
        self, company_id: str
    ) -> List[Dict[str, Any]]:
        return fetch_employees_for_residence_permits_list(company_id)

    def get_employees_for_export(
        self, company_id: str, employee_ids: List[str]
    ) -> List[Dict[str, Any]]:
        return fetch_employees_for_residence_permits_export(company_id, employee_ids)
```

- [ ] **Step 6: Lancer les tests**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/residence_permits tests/integration/residence_permits -q`
Expected: PASS — les 6 nouveaux tests, plus les tests existants du module inchangés

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/residence_permits/ backend/tests/unit/residence_permits/
git commit -m "feat(titres-sejour): lecture des salariés à exporter, bornée à l'entreprise"
```

---

### Task 3 : Cas d'usage d'export

**Files:**
- Create: `backend/app/modules/residence_permits/application/exports.py`
- Test: `backend/tests/unit/residence_permits/test_export_command.py`

**Interfaces:**
- Consumes:
  - `IResidencePermitExportReader.get_employees_for_export` (Task 2)
  - `build_residence_permits_xlsx`, `build_export_filename` (Task 1)
  - `app.modules.residence_permits.application.service.enrich_row_with_residence_permit_status`
  - `app.modules.residence_permits.infrastructure.providers.get_residence_permit_status_calculator`
- Produces:
  - `MAX_EXPORT_EMPLOYEES: int = 1000`
  - `class ResidencePermitExportEmpty(Exception)`
  - `class ResidencePermitExportTooLarge(Exception)`
  - `export_residence_permits(company_id: str, company_name: str, employee_ids: List[str], *, reader=None, calculator=None, today=None) -> Tuple[bytes, str]`

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `backend/tests/unit/residence_permits/test_export_command.py` :

```python
"""
Cas d'usage d'export : garde-fous et restauration de l'ordre demandé.

Le navigateur envoie les identifiants dans l'ordre d'affichage (tri par urgence).
PostgREST ne garantit aucun ordre sur un `IN` : sans restauration explicite, le
fichier ne correspondrait plus à l'écran, ce qui est toute la promesse de l'export.
"""

from __future__ import annotations

import io
from datetime import date

import pytest
from openpyxl import load_workbook

from app.modules.residence_permits.application.exports import (
    MAX_EXPORT_EMPLOYEES,
    ResidencePermitExportEmpty,
    ResidencePermitExportTooLarge,
    export_residence_permits,
)

pytestmark = pytest.mark.unit

COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"


class FakeReader:
    """Simule la borne serveur : ne rend que ce qui appartient à l'entreprise."""

    def __init__(self, rows_par_entreprise):
        self.rows_par_entreprise = rows_par_entreprise
        self.appels = []

    def get_employees_for_export(self, company_id, employee_ids):
        self.appels.append((company_id, list(employee_ids)))
        connus = self.rows_par_entreprise.get(company_id, {})
        # Ordre volontairement inversé : PostgREST ne garantit rien.
        return [connus[i] for i in reversed(employee_ids) if i in connus]


def _row(emp_id, last_name):
    return {
        "id": emp_id,
        "first_name": "Test",
        "last_name": last_name,
        "matricule": "0001",
        "job_title": "Opérateur",
        "hire_date": "2023-01-02",
        "nationalite": "FRANCAISE",
        "employment_status": "actif",
        "is_subject_to_residence_permit": True,
        "residence_permit_expiry_date": "2027-01-01",
        "residence_permit_type": None,
        "residence_permit_number": "123",
    }


def _noms(content):
    ws = load_workbook(io.BytesIO(content)).active
    return [ws.cell(row=i, column=1).value for i in range(2, ws.max_row + 1)]


def test_ordre_demande_restaure():
    """Le fichier suit l'ordre du navigateur, pas celui de la base."""
    reader = FakeReader(
        {COMPANY_ID: {"a": _row("a", "AAA"), "b": _row("b", "BBB"), "c": _row("c", "CCC")}}
    )
    content, _ = export_residence_permits(
        COMPANY_ID, "Test Co", ["a", "b", "c"], reader=reader
    )

    assert _noms(content) == ["AAA", "BBB", "CCC"]


def test_identifiant_inconnu_ignore_sans_erreur():
    """Un salarié sorti entre l'affichage et le clic ne doit pas casser l'export."""
    reader = FakeReader({COMPANY_ID: {"a": _row("a", "AAA")}})
    content, _ = export_residence_permits(
        COMPANY_ID, "Test Co", ["a", "inexistant"], reader=reader
    )

    assert _noms(content) == ["AAA"]


def test_identifiant_d_une_autre_societe_exclu():
    """Cloisonnement : le lecteur n'est interrogé que sur l'entreprise active."""
    autre = "660e8400-e29b-41d4-a716-446655440099"
    reader = FakeReader(
        {COMPANY_ID: {"a": _row("a", "AAA")}, autre: {"z": _row("z", "ZZZ")}}
    )
    content, _ = export_residence_permits(
        COMPANY_ID, "Test Co", ["a", "z"], reader=reader
    )

    assert _noms(content) == ["AAA"]
    assert reader.appels == [(COMPANY_ID, ["a", "z"])]


def test_liste_vide_refusee():
    reader = FakeReader({COMPANY_ID: {}})
    with pytest.raises(ResidencePermitExportEmpty):
        export_residence_permits(COMPANY_ID, "Test Co", [], reader=reader)


def test_aucune_correspondance_refusee():
    reader = FakeReader({COMPANY_ID: {}})
    with pytest.raises(ResidencePermitExportEmpty):
        export_residence_permits(COMPANY_ID, "Test Co", ["inexistant"], reader=reader)


def test_trop_d_identifiants_refuse():
    reader = FakeReader({COMPANY_ID: {}})
    trop = [f"emp-{i}" for i in range(MAX_EXPORT_EMPLOYEES + 1)]
    with pytest.raises(ResidencePermitExportTooLarge):
        export_residence_permits(COMPANY_ID, "Test Co", trop, reader=reader)


def test_doublons_dedupliques():
    reader = FakeReader({COMPANY_ID: {"a": _row("a", "AAA")}})
    content, _ = export_residence_permits(
        COMPANY_ID, "Test Co", ["a", "a"], reader=reader
    )

    assert _noms(content) == ["AAA"]
    assert reader.appels == [(COMPANY_ID, ["a"])]


def test_statut_calcule_present_dans_le_fichier():
    """L'enrichissement est fait ici : le fichier porte un statut, pas un champ brut."""
    reader = FakeReader(
        {COMPANY_ID: {"a": _row("a", "AAA") | {"residence_permit_expiry_date": "2020-01-01"}}}
    )
    content, _ = export_residence_permits(
        COMPANY_ID, "Test Co", ["a"], reader=reader
    )
    ws = load_workbook(io.BytesIO(content)).active

    assert ws.cell(row=2, column=9).value == "Expiré"


def test_nom_de_fichier_retourne():
    reader = FakeReader({COMPANY_ID: {"a": _row("a", "AAA")}})
    _, filename = export_residence_permits(
        COMPANY_ID, "Mont Blanc Composite", ["a"], reader=reader, today=date(2026, 7, 31)
    )

    assert filename == "titres-de-sejour_mont-blanc-composite_2026-07-31.xlsx"
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/residence_permits/test_export_command.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.modules.residence_permits.application.exports'`

- [ ] **Step 3: Écrire l'implémentation**

Créer `backend/app/modules/residence_permits/application/exports.py` :

```python
"""
Cas d'usage : export XLSX des titres de séjour pour un ensemble de salariés désignés.

Le navigateur envoie les identifiants des lignes qu'il affiche, jamais les critères
de filtrage. Ce module ne refiltre donc pas : il borne (Task 2), restaure l'ordre
demandé, puis délègue la mise en forme. La règle de filtrage n'existe qu'à un seul
endroit, l'écran, et le fichier correspond à l'affichage par construction.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from app.modules.residence_permits.application.service import (
    enrich_row_with_residence_permit_status,
)
from app.modules.residence_permits.infrastructure.export_xlsx import (
    build_export_filename,
    build_residence_permits_xlsx,
)
from app.modules.residence_permits.infrastructure.providers import (
    get_residence_permit_status_calculator,
)
from app.modules.residence_permits.infrastructure.repository import (
    ResidencePermitListRepository,
)

# Garde-fou : la plus grosse société compte 34 salariés soumis. Cette borne protège
# d'une requête forgée, elle n'est pas une limite fonctionnelle.
MAX_EXPORT_EMPLOYEES = 1000

_repo = ResidencePermitListRepository()


class ResidencePermitExportEmpty(Exception):
    """Aucun salarié exportable parmi les identifiants reçus."""


class ResidencePermitExportTooLarge(Exception):
    """Plus d'identifiants demandés que la borne autorisée."""


def _identifiants_normalises(employee_ids: Optional[List[str]]) -> List[str]:
    """Nettoie et déduplique en conservant l'ordre d'affichage."""
    vus: Dict[str, None] = {}
    for brut in employee_ids or []:
        valeur = str(brut).strip()
        if valeur and valeur not in vus:
            vus[valeur] = None
    return list(vus)


def export_residence_permits(
    company_id: str,
    company_name: str,
    employee_ids: Optional[List[str]],
    *,
    reader: Any = None,
    calculator: Any = None,
    today: Optional[date] = None,
) -> Tuple[bytes, str]:
    """
    Produit le fichier XLSX et son nom pour les salariés désignés.

    Lève ResidencePermitExportEmpty si rien n'est exportable, et
    ResidencePermitExportTooLarge au-delà de MAX_EXPORT_EMPLOYEES.
    """
    identifiants = _identifiants_normalises(employee_ids)
    if not identifiants:
        raise ResidencePermitExportEmpty("Aucun salarié à exporter")
    if len(identifiants) > MAX_EXPORT_EMPLOYEES:
        raise ResidencePermitExportTooLarge(
            f"Export limité à {MAX_EXPORT_EMPLOYEES} salariés par fichier"
        )

    lecteur = reader if reader is not None else _repo
    rows: List[Dict[str, Any]] = lecteur.get_employees_for_export(
        company_id, identifiants
    )
    if not rows:
        raise ResidencePermitExportEmpty("Aucun salarié à exporter")

    calculateur = (
        calculator if calculator is not None else get_residence_permit_status_calculator()
    )
    enrichies = [
        enrich_row_with_residence_permit_status(row, calculateur) for row in rows
    ]

    # PostgREST ne garantit aucun ordre sur un `IN` : on rétablit celui du navigateur,
    # qui est l'ordre d'urgence affiché à l'écran.
    rang = {identifiant: index for index, identifiant in enumerate(identifiants)}
    enrichies.sort(key=lambda row: rang.get(str(row.get("id")), len(identifiants)))

    contenu = build_residence_permits_xlsx(enrichies, company_name)
    return contenu, build_export_filename(company_name, today)
```

- [ ] **Step 4: Lancer les tests**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/residence_permits -q`
Expected: PASS — 9 nouveaux tests, 30 au total sur le dossier

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/residence_permits/application/exports.py backend/tests/unit/residence_permits/test_export_command.py
git commit -m "feat(titres-sejour): cas d'usage d'export, ordre d'affichage restauré"
```

---

### Task 4 : Route HTTP

**Files:**
- Modify: `backend/app/modules/residence_permits/schemas/requests.py`
- Modify: `backend/app/modules/residence_permits/api/router.py`
- Test: `backend/tests/integration/residence_permits/test_export_api.py`

**Interfaces:**
- Consumes: `export_residence_permits`, `ResidencePermitExportEmpty`, `ResidencePermitExportTooLarge` (Task 3), `_require_rh_company_context` (existant)
- Produces: `POST /api/residence-permits/export`, `ResidencePermitExportRequest`

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `backend/tests/integration/residence_permits/test_export_api.py` :

```python
"""
Route POST /api/residence-permits/export.

POST et non GET : la liste d'identifiants est de longueur variable et passerait
dans l'URL, dont la longueur est bornée par les navigateurs et les proxys.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.residence_permits.application.exports import (
    ResidencePermitExportEmpty,
    ResidencePermitExportTooLarge,
)
from app.modules.users.schemas.responses import CompanyAccess, User

pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ROUTE = "/api/residence-permits/export"


def _rh_user(role: str = "rh"):
    return User(
        id=TEST_USER_ID,
        email="rh@test.com",
        accessible_companies=[
            CompanyAccess(
                company_id=TEST_COMPANY_ID,
                company_name="Mont Blanc Composite",
                role=role,
                is_primary=True,
            )
        ],
        active_company_id=TEST_COMPANY_ID,
    )


@pytest.fixture
def client_rh():
    app.dependency_overrides[get_current_user] = lambda: _rh_user()
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def client_collaborateur():
    app.dependency_overrides[get_current_user] = lambda: _rh_user(role="collaborateur")
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_cas_nominal(client_rh):
    with patch(
        "app.modules.residence_permits.api.router.export_residence_permits",
        return_value=(b"PK-faux-xlsx", "titres-de-sejour_test_2026-07-31.xlsx"),
    ) as export:
        response = client_rh.post(ROUTE, json={"employee_ids": ["emp-1", "emp-2"]})

    assert response.status_code == 200
    assert response.headers["content-type"] == XLSX_MIME
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="titres-de-sejour_test_2026-07-31.xlsx"'
    )
    assert response.content == b"PK-faux-xlsx"
    assert export.call_args.args[0] == TEST_COMPANY_ID
    assert export.call_args.args[1] == "Mont Blanc Composite"
    assert export.call_args.args[2] == ["emp-1", "emp-2"]


def test_sans_acces_rh(client_collaborateur):
    response = client_collaborateur.post(ROUTE, json={"employee_ids": ["emp-1"]})

    assert response.status_code == 403


def test_selection_vide(client_rh):
    with patch(
        "app.modules.residence_permits.api.router.export_residence_permits",
        side_effect=ResidencePermitExportEmpty("Aucun salarié à exporter"),
    ):
        response = client_rh.post(ROUTE, json={"employee_ids": []})

    assert response.status_code == 400
    assert response.json()["detail"] == "Aucun salarié à exporter"


def test_trop_d_identifiants(client_rh):
    with patch(
        "app.modules.residence_permits.api.router.export_residence_permits",
        side_effect=ResidencePermitExportTooLarge("Export limité à 1000 salariés par fichier"),
    ):
        response = client_rh.post(ROUTE, json={"employee_ids": ["emp-1"]})

    assert response.status_code == 400
    assert "1000" in response.json()["detail"]


def test_erreur_inattendue_donne_500(client_rh):
    with patch(
        "app.modules.residence_permits.api.router.export_residence_permits",
        side_effect=RuntimeError("boum"),
    ):
        response = client_rh.post(ROUTE, json={"employee_ids": ["emp-1"]})

    assert response.status_code == 500


def test_corps_absent_rejete(client_rh):
    response = client_rh.post(ROUTE, json={})

    assert response.status_code == 422
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/residence_permits/test_export_api.py -q`
Expected: FAIL — 404 sur la route (elle n'existe pas), et `ImportError` sur `ResidencePermitExportEmpty` si Task 3 n'est pas faite

- [ ] **Step 3: Ajouter le schéma de requête**

Remplacer intégralement `backend/app/modules/residence_permits/schemas/requests.py` par :

```python
"""
Schémas de requête du module residence_permits.
"""

from typing import List

from pydantic import BaseModel, Field


class ResidencePermitExportRequest(BaseModel):
    """
    Salariés à exporter, désignés par le navigateur.

    Ce sont les lignes affichées à l'écran, dans leur ordre d'affichage. Les
    identifiants désignent, ils n'autorisent pas : le serveur borne la lecture à
    l'entreprise active.
    """

    employee_ids: List[str] = Field(
        ..., description="Identifiants des salariés affichés, dans l'ordre de l'écran"
    )
```

- [ ] **Step 4: Ajouter la route**

Dans `backend/app/modules/residence_permits/api/router.py` :

Remplacer le bloc d'imports par :

```python
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response

from app.core.security import get_current_user
from app.modules.residence_permits.application.exports import (
    ResidencePermitExportEmpty,
    ResidencePermitExportTooLarge,
    export_residence_permits,
)
from app.modules.residence_permits.application.queries import get_residence_permits_list
from app.modules.residence_permits.schemas.requests import ResidencePermitExportRequest
from app.modules.residence_permits.schemas.responses import ResidencePermitListItem
from app.modules.users.schemas.responses import User

XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
```

Puis ajouter, après `_require_rh_company_context` :

```python
def _active_company_name(current_user: User, company_id: str) -> str:
    """Nom de l'entreprise active, pour la colonne Société et le nom du fichier."""
    for access in current_user.accessible_companies:
        if str(access.company_id) == str(company_id):
            return access.company_name or ""
    return ""
```

Puis ajouter, à la fin du fichier :

```python
@router.post("/export")
def export_residence_permits_route(
    payload: ResidencePermitExportRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Export XLSX des salariés désignés par le navigateur.

    POST et non GET : la liste d'identifiants est de longueur variable et passerait
    dans l'URL, dont la longueur est bornée par les navigateurs et les proxys.
    """
    company_id = _require_rh_company_context(current_user)
    company_name = _active_company_name(current_user, company_id)
    try:
        content, filename = export_residence_permits(
            company_id, company_name, payload.employee_ids
        )
    except ResidencePermitExportTooLarge as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ResidencePermitExportEmpty as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'export des titres de séjour: {str(e)}",
        )
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 5: Lancer les tests**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/residence_permits tests/integration/residence_permits -q`
Expected: PASS — 6 nouveaux tests d'intégration, aucun test existant cassé

- [ ] **Step 6: Vérifier les règles d'architecture**

Run: `cd backend && .venv/bin/python -m pytest tests/ -q -k "import_linter or architecture or wiring"`
Expected: PASS (ou aucun test collecté si ces tests n'existent pas sous ces noms)

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/residence_permits/ backend/tests/integration/residence_permits/test_export_api.py
git commit -m "feat(titres-sejour): route POST d'export XLSX"
```

---

### Task 5 : Appel côté navigateur

**Files:**
- Modify: `frontend/src/lib/downloadBlob.ts`
- Modify: `frontend/src/api/residencePermits.ts`
- Test: `frontend/src/lib/downloadBlob.test.ts`

**Interfaces:**
- Consumes: `POST /api/residence-permits/export` (Task 4), `downloadBlob` (existant)
- Produces:
  - `parseContentDispositionFilename(header: unknown, fallback: string): string`
  - `exportResidencePermits(employeeIds: string[]): Promise<void>`

- [ ] **Step 1: Écrire le test qui échoue**

Créer `frontend/src/lib/downloadBlob.test.ts` :

```ts
import { describe, expect, it } from "vitest";

import { parseContentDispositionFilename } from "./downloadBlob";

describe("parseContentDispositionFilename", () => {
  it("lit un nom entre guillemets", () => {
    expect(
      parseContentDispositionFilename(
        'attachment; filename="titres-de-sejour_mbc_2026-07-31.xlsx"',
        "repli.xlsx",
      ),
    ).toBe("titres-de-sejour_mbc_2026-07-31.xlsx");
  });

  it("lit un nom sans guillemets", () => {
    expect(
      parseContentDispositionFilename("attachment; filename=export.xlsx", "repli.xlsx"),
    ).toBe("export.xlsx");
  });

  it("décode la forme UTF-8 encodée", () => {
    expect(
      parseContentDispositionFilename(
        "attachment; filename*=UTF-8''titres-de-s%C3%A9jour.xlsx",
        "repli.xlsx",
      ),
    ).toBe("titres-de-séjour.xlsx");
  });

  it("rend le repli quand l'en-tête est absent", () => {
    expect(parseContentDispositionFilename(undefined, "repli.xlsx")).toBe("repli.xlsx");
  });

  it("rend le repli quand l'en-tête ne porte pas de nom", () => {
    expect(parseContentDispositionFilename("attachment", "repli.xlsx")).toBe("repli.xlsx");
  });
});
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `cd frontend && npx vitest run src/lib/downloadBlob.test.ts`
Expected: FAIL — `parseContentDispositionFilename is not exported`

- [ ] **Step 3: Ajouter le lecteur d'en-tête**

Ajouter à la fin de `frontend/src/lib/downloadBlob.ts` :

```ts
/**
 * Nom de fichier proposé par le serveur, ou repli.
 *
 * Gère `filename="..."` et la forme encodée `filename*=UTF-8''...`, que produisent
 * les serveurs dès que le nom porte un accent.
 */
export function parseContentDispositionFilename(header: unknown, fallback: string): string {
  if (typeof header !== 'string') return fallback;
  const match = header.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
  const value = match?.[1]?.trim();
  if (!value) return fallback;
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}
```

- [ ] **Step 4: Lancer le test**

Run: `cd frontend && npx vitest run src/lib/downloadBlob.test.ts`
Expected: PASS — 5 tests

- [ ] **Step 5: Ajouter l'appel d'export**

Ajouter à la fin de `frontend/src/api/residencePermits.ts` :

```ts
import { downloadBlob, parseContentDispositionFilename } from "@/lib/downloadBlob";

const EXPORT_FALLBACK_FILENAME = "titres-de-sejour.xlsx";

/**
 * Message d'erreur du serveur quand la réponse est un Blob.
 *
 * En `responseType: "blob"`, axios livre aussi le corps des erreurs sous forme de
 * Blob : sans cette lecture, un 400 « Aucun salarié à exporter » s'afficherait
 * comme un objet illisible.
 */
export async function residencePermitsExportErrorMessage(
  error: unknown,
  fallback = "L'export a échoué. Réessayez dans un instant.",
): Promise<string> {
  const data = (error as { response?: { data?: unknown } })?.response?.data;
  if (data instanceof Blob) {
    try {
      const detail = JSON.parse(await data.text())?.detail;
      if (typeof detail === "string") return detail;
    } catch {
      // Corps non JSON : on garde le repli.
    }
  }
  if (typeof (data as { detail?: unknown })?.detail === "string") {
    return (data as { detail: string }).detail;
  }
  return fallback;
}

/**
 * Télécharge l'export des salariés désignés.
 *
 * On envoie les identifiants des lignes affichées, dans leur ordre d'affichage,
 * et non les critères de filtrage : la règle de filtrage n'existe qu'ici, et le
 * fichier correspond à l'écran par construction.
 */
export async function exportResidencePermits(employeeIds: string[]): Promise<void> {
  const res = await apiClient.post<Blob>(
    "/api/residence-permits/export",
    { employee_ids: employeeIds },
    { responseType: "blob" },
  );
  const filename = parseContentDispositionFilename(
    res.headers["content-disposition"],
    EXPORT_FALLBACK_FILENAME,
  );
  downloadBlob(res.data as Blob, filename);
}
```

- [ ] **Step 6: Vérifier la compilation**

Run: `cd frontend && npx tsc --noEmit`
Expected: aucune erreur

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/downloadBlob.ts frontend/src/lib/downloadBlob.test.ts frontend/src/api/residencePermits.ts
git commit -m "feat(titres-sejour): appel d'export côté navigateur"
```

---

### Task 6 : Bouton sur la page

**Files:**
- Modify: `frontend/src/pages/rh/ResidencePermits.tsx`

**Interfaces:**
- Consumes: `exportResidencePermits`, `residencePermitsExportErrorMessage` (Task 5)
- Produces: rien (feuille de l'arbre)

- [ ] **Step 1: Ajouter les imports**

Dans `frontend/src/pages/rh/ResidencePermits.tsx` :

Remplacer la ligne d'import de `@/api/residencePermits` par :

```tsx
import {
  exportResidencePermits,
  getResidencePermits,
  residencePermitsExportErrorMessage,
} from "@/api/residencePermits";
```

Remplacer la ligne d'import de `lucide-react` par :

```tsx
import { Search, FileCheck, ChevronRight, RefreshCw, Download, Loader2 } from "lucide-react";
```

- [ ] **Step 2: Ajouter l'état et le gestionnaire**

Juste après la déclaration `const [searchTerm, setSearchTerm] = useState("");`, ajouter :

```tsx
  const [isExporting, setIsExporting] = useState(false);
```

Juste après le `useMemo` qui produit `filteredAndSorted`, ajouter :

```tsx
  // On envoie les identifiants des lignes affichées, dans l'ordre d'affichage :
  // le fichier reflète l'écran sans que le serveur ait à refaire le filtrage.
  const handleExport = async () => {
    setIsExporting(true);
    try {
      await exportResidencePermits(filteredAndSorted.map((item) => item.employee_id));
    } catch (exportError) {
      toast({
        title: "Export impossible",
        description: await residencePermitsExportErrorMessage(exportError),
        variant: "destructive",
      });
    } finally {
      setIsExporting(false);
    }
  };
```

- [ ] **Step 3: Ajouter le bouton**

Dans le `CardHeader`, remplacer le bloc `<Select>…</Select>` par :

```tsx
            <div className="flex items-center gap-3">
              <Select
                value={filterStatus}
                onValueChange={(v) => setFilterStatus(v as FilterStatus)}
              >
                <SelectTrigger className="w-[200px]">
                  <SelectValue placeholder="Filtrer par statut" />
                </SelectTrigger>
                <SelectContent>
                  {FILTER_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                type="button"
                variant="outline"
                className="gap-2"
                onClick={() => void handleExport()}
                disabled={isExporting || isLoading || filteredAndSorted.length === 0}
              >
                {isExporting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Download className="h-4 w-4" />
                )}
                Exporter en Excel
              </Button>
            </div>
```

- [ ] **Step 4: Vérifier la compilation et le lint**

Run: `cd frontend && npx tsc --noEmit && npx eslint src/pages/rh/ResidencePermits.tsx src/api/residencePermits.ts`
Expected: aucune erreur

- [ ] **Step 5: Lancer la suite frontend**

Run: `cd frontend && npm run test`
Expected: PASS — aucun test cassé

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/rh/ResidencePermits.tsx
git commit -m "feat(titres-sejour): bouton d'export Excel sur la page RH"
```

---

### Task 7 : Vérification d'ensemble

**Files:** aucun (vérification)

- [ ] **Step 1: Suite backend complète**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: PASS. Comparer au nombre de tests d'avant le chantier ; **le seul écart admis est l'ajout des nouveaux tests**.

- [ ] **Step 2: Suite frontend complète**

Run: `cd frontend && npm run test && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 3: Contrôle sur données réelles**

Créer un script jetable dans le répertoire scratchpad (hors dépôt) qui :
1. lit les salariés soumis de Mont Blanc Composite via `fetch_employees_for_residence_permits_export` ;
2. appelle `export_residence_permits` avec leurs identifiants ;
3. écrit le fichier et relit le classeur.

Vérifier sur le fichier produit :
- 34 lignes de données pour Mont Blanc Composite ;
- les 7 titres expirés portent « Expiré » et un nombre de jours négatif ;
- la colonne « Type de titre » est vide partout (attendu, cf. spec § 3.3) ;
- ASKARI n'a ni date d'expiration ni jours restants, et porte « À compléter ».

- [ ] **Step 4: Commit final éventuel**

Si l'étape 3 a révélé un correctif, l'appliquer avec son test puis committer.

---

## Auto-revue

**Couverture de la spec :**

| Section de la spec | Tâche |
|---|---|
| § 4.1 fabrication serveur | Task 1 |
| § 4.2 le navigateur désigne les lignes | Task 3 (ordre), Task 5 (envoi des identifiants) |
| § 4.3 découpage | Tasks 1-4 |
| § 4.4 contrat de l'endpoint, POST, codes d'erreur | Task 4 |
| § 4.5 sécurité, bornes serveur, ordre restauré | Task 2 (bornes), Task 3 (ordre) |
| § 4.6 13 colonnes, mise en forme, nom de fichier | Task 1 |
| § 4.7 bouton, état d'attente, toast | Task 6 |
| § 5 tests backend | Tasks 1-4 |
| § 5 tests frontend | Task 5, **avec écart documenté** (pas de jsdom dans le dépôt) |

**Écarts assumés :**
- Les deux tests d'interface prévus par la spec sont remplacés par un test de fonction pure. Motif : `environment: "node"` dans `vitest.config.ts`, aucune bibliothèque de test de composant installée. Ajouter jsdom dépasserait le cadre de #7.
- La spec ne mentionnait pas la lecture du message d'erreur depuis un corps `Blob` (Task 5). Ajout nécessaire : sans lui, un 400 s'afficherait comme un objet illisible.

**Cohérence des noms :** `build_residence_permits_xlsx`, `build_export_filename`, `fetch_employees_for_residence_permits_export`, `get_employees_for_export`, `export_residence_permits`, `ResidencePermitExportEmpty`, `ResidencePermitExportTooLarge`, `ResidencePermitExportRequest`, `parseContentDispositionFilename`, `exportResidencePermits`, `residencePermitsExportErrorMessage` — employés à l'identique entre les tâches qui les produisent et celles qui les consomment.
