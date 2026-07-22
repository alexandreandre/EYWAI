# Import des participations depuis des saisies existantes — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter une capacité réutilisable (service + endpoint + UI) qui reconstruit une campagne de participation clôturée à partir des saisies de paie (`monthly_inputs`) déjà présentes en base, puis l'exécuter pour les 5 sociétés ayant une participation 2025 déjà versée (MBC, Cartol, Lewis, Comitech, Colorplast).

**Architecture:** Une fonction pure de reconstruction (domaine) classe les saisies par salarié et calcule les champs du bulletin d'option ; un service applicatif orchestre la lecture/écriture Supabase (idempotent, réversible) ; un endpoint FastAPI + un bouton dans `ParticipationCampaignPanel` exposent la capacité ; un script one-shot exécute l'import réel pour les 5 sociétés.

**Tech Stack:** Python 3.12 / FastAPI / Supabase (postgrest client) côté backend ; React / TypeScript / TanStack Query / shadcn (Dialog) côté frontend ; pytest pour les tests.

## Global Constraints

- Ne jamais modifier `monthly_inputs.amount` / `is_socially_taxed` / `is_taxable` — seules les colonnes `participation_campaign_id` / `participation_bulletin_id` sont écrites. Les bulletins de mai 2026 doivent rester visuellement identiques après l'import.
- Campagnes reconstruites : `status="closed"`, bulletins `status="responded"` avec `choice_type` déduit. Aucun envoi (`publish_campaign`), aucune notification, aucun PDF généré.
- Réutiliser `compute_participation_csg` de `app/modules/participation/domain/bulletin_rules.py` (ne pas dupliquer les taux CSG).
- Tests backend : `DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib" .venv-ci/bin/pytest <path> -v` depuis `backend/`.
- Spec de référence : `docs/superpowers/specs/2026-07-22-import-participations-saisies-existantes-design.md`.

---

## Task 1: Reconstruction — fonction pure (domaine)

**Files:**
- Create: `backend/app/modules/participation/domain/import_reconstruction.py`
- Test: `backend/tests/unit/participation/test_import_reconstruction.py`

**Interfaces:**
- Consumes: `compute_participation_csg(gross: float | Decimal) -> Tuple[Decimal, Decimal, Decimal]`, `CSG_DEDUCTIBLE_RATE`, `CSG_NON_DEDUCTIBLE_RATE` depuis `app.modules.participation.domain.bulletin_rules` (existant).
- Produces: `ReconstructedBulletin` (dataclass frozen) et `reconstruct_bulletins_from_inputs(monthly_inputs: List[Dict[str, Any]]) -> List[ReconstructedBulletin]` dans `app.modules.participation.domain.import_reconstruction`. Champs de `ReconstructedBulletin` : `employee_id: str`, `dispositif_type: str`, `gross_amount: Decimal`, `csg_non_deductible: Decimal`, `csg_deductible: Decimal`, `advance_amount: Decimal`, `advance_label: str`, `net_amount: Decimal`, `choice_type: str`, `cash_amount: Decimal`, `pee_amount: Decimal`, `source_input_ids: List[str]`.

- [ ] **Step 1: Écrire le fichier de test complet (échouera : le module n'existe pas encore)**

Créer `backend/tests/unit/participation/test_import_reconstruction.py` :

```python
"""Tests unitaires — reconstruction des bulletins participation depuis les saisies.

Fixtures calées sur des cas réels de la base (backtest 2025/2026) : GIRERD
(MBC, 100 % PEE), un cas numéraire+avance, un cas mixte numéraire+PEE+avance.
"""

from __future__ import annotations

from decimal import Decimal

from app.modules.participation.domain.import_reconstruction import (
    reconstruct_bulletins_from_inputs,
)


def _row(employee_id: str, name: str, amount: float, row_id: str) -> dict:
    return {"id": row_id, "employee_id": employee_id, "name": name, "amount": amount}


class TestFullCash:
    def test_numeraire_seul(self):
        rows = [_row("e1", "Participation 2025 — numéraire", 3535.86, "r1")]

        result = reconstruct_bulletins_from_inputs(rows)

        assert len(result) == 1
        b = result[0]
        assert b.employee_id == "e1"
        assert b.choice_type == "full_cash"
        assert b.cash_amount == Decimal("3192.88")
        assert b.pee_amount == Decimal("0.00")
        assert b.net_amount == Decimal("3192.88")
        assert b.advance_amount == Decimal("0")
        assert b.source_input_ids == ["r1"]

    def test_numeraire_avec_avance(self):
        """Cas réel : société MBC, numéraire 3535,86 € + avance -1000 €."""
        rows = [
            _row("e1", "Participation 2025 — numéraire", 3535.86, "r1"),
            _row("e1", "Avance participation 2025 (déjà versée)", -1000.0, "r2"),
        ]

        result = reconstruct_bulletins_from_inputs(rows)

        b = result[0]
        assert b.choice_type == "full_cash"
        assert b.cash_amount == Decimal("2192.88")
        assert b.advance_amount == Decimal("1000")
        assert b.advance_label == "Avance participation 2025 (déjà versée)"
        assert set(b.source_input_ids) == {"r1", "r2"}

    def test_libelle_simple_traite_comme_numeraire(self):
        """Cartol/Lewis : libellé 'Participation 2025' sans suffixe '— numéraire'."""
        rows = [_row("e1", "Participation 2025", 1000.0, "r1")]

        result = reconstruct_bulletins_from_inputs(rows)

        assert result[0].choice_type == "full_cash"


class TestFullPee:
    def test_pee_seul_girerd(self):
        """Cas réel : Fabrice GIRERD, MBC mai 2026, participation 100 % PEE."""
        rows = [_row("e2", "Participation 2025 — PEE", 5331.56, "r1")]

        result = reconstruct_bulletins_from_inputs(rows)

        b = result[0]
        assert b.choice_type == "full_pee"
        assert b.cash_amount == Decimal("0.00")
        assert b.pee_amount == Decimal("4814.40")
        assert b.net_amount == Decimal("4814.40")
        assert b.csg_non_deductible == Decimal("154.62")
        assert b.csg_deductible == Decimal("362.55")


class TestPartialCash:
    def test_numeraire_et_pee_avec_avance(self):
        """Cas réel : numéraire 4429,40 + PEE 559,40 + avance -1000."""
        rows = [
            _row("e3", "Participation 2025 — numéraire", 4429.40, "r1"),
            _row("e3", "Participation 2025 PEE", 559.40, "r2"),
            _row("e3", "Avance participation 2025 (déjà versée)", -1000.0, "r3"),
        ]

        result = reconstruct_bulletins_from_inputs(rows)

        b = result[0]
        assert b.choice_type == "partial_cash"
        assert b.cash_amount == Decimal("2999.75")
        assert b.pee_amount == Decimal("505.14")
        assert b.net_amount == Decimal("3504.89")


class TestExclusions:
    def test_note_de_frais_exclue(self):
        rows = [
            _row("e1", "Participation 2025 — numéraire", 1000.0, "r1"),
            _row("e1", "Remboursement note de frais (participation)", 50.0, "r2"),
        ]

        result = reconstruct_bulletins_from_inputs(rows)

        assert len(result) == 1
        assert result[0].source_input_ids == ["r1"]

    def test_avance_orpheline_ignoree(self):
        """Défensif : aucun cas réel actuel, mais une avance sans numéraire/PEE
        associé ne doit pas créer de bénéficiaire fantôme."""
        rows = [_row("e1", "Avance participation 2025 (déjà versée)", -500.0, "r1")]

        result = reconstruct_bulletins_from_inputs(rows)

        assert result == []

    def test_ligne_non_participation_ignoree(self):
        rows = [_row("e1", "Prime de vacances", 200.0, "r1")]

        result = reconstruct_bulletins_from_inputs(rows)

        assert result == []


class TestMultiEmployees:
    def test_regroupe_par_salarie(self):
        rows = [
            _row("e1", "Participation 2025 — numéraire", 1000.0, "r1"),
            _row("e2", "Participation 2025 — PEE", 500.0, "r2"),
        ]

        result = reconstruct_bulletins_from_inputs(rows)

        assert {b.employee_id for b in result} == {"e1", "e2"}
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent (module manquant)**

Run (depuis `backend/`) :
```bash
DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib" .venv-ci/bin/pytest tests/unit/participation/test_import_reconstruction.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.modules.participation.domain.import_reconstruction'`

- [ ] **Step 3: Créer `backend/app/modules/participation/domain/import_reconstruction.py`**

```python
"""Reconstruction de bulletins d'option participation depuis des saisies existantes.

Fonction pure : classe les `monthly_inputs` déjà en base (issues d'un backtest
ou d'une saisie antérieure au module participation) et reconstitue, par
salarié, le bulletin d'option qu'aurait produit le workflow normal
(create_campaign → réponse salarié), sans jamais modifier les saisies.

Voir docs/superpowers/specs/2026-07-22-import-participations-saisies-existantes-design.md
pour la dérivation complète de la formule (en particulier : le montant d'une
ligne PEE est déjà un brut, pas un net à regonfler — vérifié sur le moteur
réel et sur le cas GIRERD/MBC).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List

from app.modules.participation.domain.bulletin_rules import (
    CSG_DEDUCTIBLE_RATE,
    CSG_NON_DEDUCTIBLE_RATE,
    compute_participation_csg,
)

# Facteur net-de-CSG : ce que le salarié perçoit réellement (numéraire) ou ce
# qui est effectivement placé (PEE) une fois la CSG/CRDS 9,7 % déduite à la
# source du montant brut de la saisie.
_NET_FACTOR = Decimal("1") - CSG_DEDUCTIBLE_RATE - CSG_NON_DEDUCTIBLE_RATE


def _round2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ReconstructedBulletin:
    """Bulletin d'option reconstitué pour un salarié à partir de ses saisies."""

    employee_id: str
    dispositif_type: str
    gross_amount: Decimal
    csg_non_deductible: Decimal
    csg_deductible: Decimal
    advance_amount: Decimal
    advance_label: str
    net_amount: Decimal
    choice_type: str
    cash_amount: Decimal
    pee_amount: Decimal
    source_input_ids: List[str] = field(default_factory=list)


def _classify_input(row: Dict[str, Any]) -> str:
    """Retourne 'numeraire' | 'pee' | 'avance' | 'exclu' selon le libellé et le montant.

    Ordre de détection important : les remboursements de frais/notes de frais
    sont exclus en premier (même si leur libellé contient « participation »),
    puis le PEE, puis l'avance/acompte (dont le libellé contient aussi
    « participation »), puis la ligne numéraire générique.
    """
    name = str(row.get("name") or "").lower()
    amount = float(row.get("amount") or 0)

    if "note de frais" in name or "remboursement" in name:
        return "exclu"
    if "pee" in name or "épargne" in name or "epargne" in name:
        return "pee" if amount > 0 else "exclu"
    if "avance" in name or "acompte" in name:
        return "avance" if amount < 0 else "exclu"
    if "participation" in name or "intéressement" in name or "interessement" in name:
        return "numeraire" if amount > 0 else "exclu"
    return "exclu"


def reconstruct_bulletins_from_inputs(
    monthly_inputs: List[Dict[str, Any]],
) -> List[ReconstructedBulletin]:
    """Reconstitue un bulletin d'option participation par salarié bénéficiaire.

    `monthly_inputs` : lignes brutes de la table `monthly_inputs` (au minimum
    `id`, `employee_id`, `name`, `amount`), pour une société et une période de
    paie données. Les lignes non liées à la participation (autres primes,
    frais, etc.) sont ignorées : cette fonction peut recevoir l'intégralité
    des saisies du mois sans pré-filtrage SQL.

    Un salarié sans ligne numéraire ni PEE positive (ex. avance orpheline) ne
    devient pas bénéficiaire.
    """
    grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(
        lambda: {"numeraire": [], "pee": [], "avance": []}
    )
    for row in monthly_inputs:
        kind = _classify_input(row)
        if kind == "exclu":
            continue
        employee_id = str(row.get("employee_id"))
        grouped[employee_id][kind].append(row)

    results: List[ReconstructedBulletin] = []
    for employee_id, buckets in grouped.items():
        numeraire_rows = buckets["numeraire"]
        pee_rows = buckets["pee"]
        avance_rows = buckets["avance"]
        if not numeraire_rows and not pee_rows:
            continue

        gross_numeraire = sum(
            (Decimal(str(r["amount"])) for r in numeraire_rows), Decimal("0")
        )
        gross_pee = sum((Decimal(str(r["amount"])) for r in pee_rows), Decimal("0"))
        advance_amount = sum(
            (abs(Decimal(str(r["amount"]))) for r in avance_rows), Decimal("0")
        )
        advance_label = str(avance_rows[0]["name"]) if avance_rows else ""

        gross = gross_numeraire + gross_pee
        csg_non_deductible, csg_deductible, _csg_total = compute_participation_csg(
            gross
        )

        cash_amount = _round2(gross_numeraire * _NET_FACTOR) - advance_amount
        pee_amount = _round2(gross_pee * _NET_FACTOR)
        net_amount = cash_amount + pee_amount

        if gross_pee == 0:
            choice_type = "full_cash"
        elif gross_numeraire == 0:
            choice_type = "full_pee"
        else:
            choice_type = "partial_cash"

        source_input_ids = [
            str(r["id"]) for r in (*numeraire_rows, *pee_rows, *avance_rows)
        ]

        results.append(
            ReconstructedBulletin(
                employee_id=employee_id,
                dispositif_type="participation",
                gross_amount=gross,
                csg_non_deductible=csg_non_deductible,
                csg_deductible=csg_deductible,
                advance_amount=advance_amount,
                advance_label=advance_label,
                net_amount=net_amount,
                choice_type=choice_type,
                cash_amount=cash_amount,
                pee_amount=pee_amount,
                source_input_ids=source_input_ids,
            )
        )
    return results
```

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run:
```bash
DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib" .venv-ci/bin/pytest tests/unit/participation/test_import_reconstruction.py -v
```
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/participation/domain/import_reconstruction.py backend/tests/unit/participation/test_import_reconstruction.py
git commit -m "feat(participation): reconstruction pure des bulletins depuis les saisies

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Repository — suppression d'une campagne

**Files:**
- Modify: `backend/app/modules/participation/infrastructure/campaign_repository.py`
- Test: `backend/tests/integration/participation/test_campaign_repository.py`

**Interfaces:**
- Consumes: rien de nouveau (méthode ajoutée à la classe existante `ParticipationCampaignRepository`).
- Produces: `ParticipationCampaignRepository.delete_campaign(campaign_id: str, company_id: str) -> None`. Utilisée par Task 3. Note : la table `participation_campaigns` a des FK `ON DELETE CASCADE` vers `participation_bulletins`/`participation_campaign_advances`, donc supprimer la campagne suffit à nettoyer ses bulletins/avances (pas besoin de méthodes séparées).

- [ ] **Step 1: Écrire le test (échouera : la méthode n'existe pas)**

Créer `backend/tests/integration/participation/test_campaign_repository.py` :

```python
"""Tests d'intégration — ParticipationCampaignRepository.delete_campaign.

Sans DB réelle : mock Supabase pour valider les appels. Note : la suppression
d'une campagne cascade en base (FK ON DELETE CASCADE) vers ses bulletins et
avances — pas de méthode dédiée nécessaire pour ces sous-tables.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.participation.infrastructure.campaign_repository import (
    ParticipationCampaignRepository,
)

pytestmark = pytest.mark.integration

COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
CAMPAIGN_ID = "880e8400-e29b-41d4-a716-446655440003"


class TestDeleteCampaign:
    def test_delete_campaign_scopes_by_company(self):
        with patch(
            "app.modules.participation.infrastructure.campaign_repository.supabase"
        ) as supabase:
            table = MagicMock()
            delete_chain = MagicMock()
            eq_chain_1 = MagicMock()
            eq_chain_2 = MagicMock()
            table.delete.return_value = delete_chain
            delete_chain.eq.return_value = eq_chain_1
            eq_chain_1.eq.return_value = eq_chain_2
            eq_chain_2.execute.return_value = MagicMock(data=[{"id": CAMPAIGN_ID}])
            supabase.table.return_value = table

            repo = ParticipationCampaignRepository()
            repo.delete_campaign(CAMPAIGN_ID, COMPANY_ID)

            supabase.table.assert_any_call("participation_campaigns")
            table.delete.assert_called_once()
            delete_chain.eq.assert_called_once_with("id", CAMPAIGN_ID)
            eq_chain_1.eq.assert_called_once_with("company_id", COMPANY_ID)
            eq_chain_2.execute.assert_called_once()
```

- [ ] **Step 2: Lancer le test, vérifier qu'il échoue**

Run:
```bash
DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib" .venv-ci/bin/pytest tests/integration/participation/test_campaign_repository.py -v
```
Expected: `AttributeError: 'ParticipationCampaignRepository' object has no attribute 'delete_campaign'`

- [ ] **Step 3: Ajouter la méthode dans `campaign_repository.py`**

Dans `backend/app/modules/participation/infrastructure/campaign_repository.py`, insérer juste après la méthode `update_campaign` (après la ligne `return dict(result.data[0])` qui la termine, avant `def upsert_advances`) :

```python
    def delete_campaign(self, campaign_id: str, company_id: str) -> None:
        """Supprime une campagne. Cascade en base (FK ON DELETE CASCADE) vers
        ses bulletins et ses avances — rien d'autre à supprimer explicitement."""
        supabase.table("participation_campaigns").delete().eq(
            "id", campaign_id
        ).eq("company_id", company_id).execute()
```

- [ ] **Step 4: Lancer le test, vérifier qu'il passe**

Run:
```bash
DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib" .venv-ci/bin/pytest tests/integration/participation/test_campaign_repository.py -v
```
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/participation/infrastructure/campaign_repository.py backend/tests/integration/participation/test_campaign_repository.py
git commit -m "feat(participation): ajoute delete_campaign au repository

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Service d'import (application)

**Files:**
- Create: `backend/app/modules/participation/application/campaign_import_service.py`
- Test: `backend/tests/unit/participation/test_campaign_import_service.py`

**Interfaces:**
- Consumes: `reconstruct_bulletins_from_inputs` (Task 1) ; `campaign_repository.delete_campaign` (Task 2) ; méthodes existantes `campaign_repository.list_campaigns`, `count_bulletins_by_status`, `create_campaign`, `upsert_advances`, `insert_bulletins` ; `app.core.database.supabase`.
- Produces: `ImportResult` (dataclass frozen : `campaign_id: Optional[str]`, `bulletins: int`, `full_cash: int`, `partial_cash: int`, `full_pee: int`, `linked_inputs: int`, `skipped: bool`, `dry_run: bool`, `detail: str`) ; `import_campaign_from_inputs(company_id: str, year: int, payroll_year: int, payroll_month: int, *, created_by: Optional[str] = None, dry_run: bool = False, force: bool = False) -> ImportResult` ; `delete_imported_campaign(campaign_id: str, company_id: str) -> None`. Utilisés par Task 4 (endpoint) et Task 6 (script).

- [ ] **Step 1: Écrire le test complet (échouera : le module n'existe pas)**

Créer `backend/tests/unit/participation/test_campaign_import_service.py` :

```python
"""Tests unitaires — service d'import des participations depuis les saisies.

Repository et Supabase mockés ; pas de DB réelle.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.participation.application.campaign_import_service import (
    delete_imported_campaign,
    import_campaign_from_inputs,
)

COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
CAMPAIGN_ID = "880e8400-e29b-41d4-a716-446655440003"


def _rows_two_employees():
    return [
        {
            "id": "r1",
            "employee_id": "e1",
            "name": "Participation 2025 — numéraire",
            "amount": 3535.86,
        },
        {
            "id": "r2",
            "employee_id": "e1",
            "name": "Avance participation 2025 (déjà versée)",
            "amount": -1000.0,
        },
        {
            "id": "r3",
            "employee_id": "e2",
            "name": "Participation 2025 — PEE",
            "amount": 5331.56,
        },
    ]


def _mock_fetch(mock_supabase, rows):
    chain = (
        mock_supabase.table.return_value.select.return_value.eq.return_value
        .eq.return_value.eq.return_value
    )
    chain.execute.return_value = MagicMock(data=rows)


def _mock_update(mock_supabase):
    update_return = mock_supabase.table.return_value.update.return_value
    update_return.in_.return_value.execute.return_value = MagicMock(data=[])
    update_return.eq.return_value.execute.return_value = MagicMock(data=[])


@pytest.fixture
def mock_supabase():
    with patch(
        "app.modules.participation.application.campaign_import_service.supabase"
    ) as supabase:
        yield supabase


@pytest.fixture
def mock_repo():
    with patch(
        "app.modules.participation.application.campaign_import_service.campaign_repository"
    ) as repo:
        repo.list_campaigns.return_value = []
        yield repo


class TestDryRun:
    def test_returns_preview_without_writing(self, mock_supabase, mock_repo):
        _mock_fetch(mock_supabase, _rows_two_employees())

        result = import_campaign_from_inputs(COMPANY_ID, 2025, 2026, 5, dry_run=True)

        assert result.dry_run is True
        assert result.bulletins == 2
        assert result.full_cash == 1
        assert result.full_pee == 1
        mock_repo.create_campaign.assert_not_called()
        mock_repo.insert_bulletins.assert_not_called()


class TestNoData:
    def test_no_participation_inputs_returns_empty_result(
        self, mock_supabase, mock_repo
    ):
        _mock_fetch(mock_supabase, [])

        result = import_campaign_from_inputs(COMPANY_ID, 2025, 2026, 5)

        assert result.bulletins == 0
        assert result.campaign_id is None
        mock_repo.create_campaign.assert_not_called()


class TestFullImport:
    def test_creates_campaign_bulletins_and_links_inputs(
        self, mock_supabase, mock_repo
    ):
        _mock_fetch(mock_supabase, _rows_two_employees())
        _mock_update(mock_supabase)
        mock_repo.create_campaign.return_value = {"id": CAMPAIGN_ID}
        mock_repo.insert_bulletins.return_value = [
            {"id": "b1", "employee_id": "e1"},
            {"id": "b2", "employee_id": "e2"},
        ]

        result = import_campaign_from_inputs(
            COMPANY_ID, 2025, 2026, 5, created_by="user-1"
        )

        assert result.campaign_id == CAMPAIGN_ID
        assert result.bulletins == 2
        assert result.linked_inputs == 3  # r1+r2 (e1) + r3 (e2)

        created_payload = mock_repo.create_campaign.call_args[0][0]
        assert created_payload["status"] == "closed"
        assert created_payload["year"] == 2025
        assert created_payload["created_by"] == "user-1"

        bulletin_rows = mock_repo.insert_bulletins.call_args[0][0]
        assert {r["employee_id"] for r in bulletin_rows} == {"e1", "e2"}
        assert all(r["status"] == "responded" for r in bulletin_rows)

        # Invariant de sécurité : le rattachement des saisies ne touche QUE les
        # colonnes de liaison — jamais amount/is_socially_taxed/is_taxable.
        update_calls = mock_supabase.table.return_value.update.call_args_list
        assert len(update_calls) == 2  # un appel par bulletin créé (e1, e2)
        for call in update_calls:
            payload = call.args[0]
            assert set(payload.keys()) == {
                "participation_campaign_id",
                "participation_bulletin_id",
            }


class TestIdempotence:
    def test_skips_when_campaign_already_imported_without_force(
        self, mock_supabase, mock_repo
    ):
        mock_repo.list_campaigns.return_value = [{"id": CAMPAIGN_ID, "year": 2025}]
        mock_repo.count_bulletins_by_status.return_value = {"responded": 5}

        result = import_campaign_from_inputs(COMPANY_ID, 2025, 2026, 5)

        assert result.skipped is True
        assert result.bulletins == 5
        mock_repo.delete_campaign.assert_not_called()
        mock_repo.create_campaign.assert_not_called()

    def test_replaces_empty_draft_without_force(self, mock_supabase, mock_repo):
        mock_repo.list_campaigns.return_value = [{"id": CAMPAIGN_ID, "year": 2025}]
        mock_repo.count_bulletins_by_status.return_value = {}
        _mock_fetch(mock_supabase, _rows_two_employees())
        _mock_update(mock_supabase)
        mock_repo.create_campaign.return_value = {"id": "new-campaign"}
        mock_repo.insert_bulletins.return_value = [
            {"id": "b1", "employee_id": "e1"},
            {"id": "b2", "employee_id": "e2"},
        ]

        result = import_campaign_from_inputs(COMPANY_ID, 2025, 2026, 5)

        mock_repo.delete_campaign.assert_called_once_with(CAMPAIGN_ID, COMPANY_ID)
        assert "brouillon" in result.detail
        assert result.campaign_id == "new-campaign"

    def test_force_replaces_existing_campaign(self, mock_supabase, mock_repo):
        mock_repo.list_campaigns.return_value = [{"id": CAMPAIGN_ID, "year": 2025}]
        mock_repo.count_bulletins_by_status.return_value = {"responded": 5}
        _mock_fetch(mock_supabase, _rows_two_employees())
        _mock_update(mock_supabase)
        mock_repo.create_campaign.return_value = {"id": "new-campaign"}
        mock_repo.insert_bulletins.return_value = [
            {"id": "b1", "employee_id": "e1"},
            {"id": "b2", "employee_id": "e2"},
        ]

        result = import_campaign_from_inputs(COMPANY_ID, 2025, 2026, 5, force=True)

        mock_repo.delete_campaign.assert_called_once_with(CAMPAIGN_ID, COMPANY_ID)
        assert result.campaign_id == "new-campaign"


class TestDeleteImportedCampaign:
    def test_unlinks_inputs_then_deletes_campaign(self, mock_supabase, mock_repo):
        _mock_update(mock_supabase)

        delete_imported_campaign(CAMPAIGN_ID, COMPANY_ID)

        update_return = mock_supabase.table.return_value.update.return_value
        update_return.eq.assert_called_once_with(
            "participation_campaign_id", CAMPAIGN_ID
        )
        mock_repo.delete_campaign.assert_called_once_with(CAMPAIGN_ID, COMPANY_ID)
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run:
```bash
DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib" .venv-ci/bin/pytest tests/unit/participation/test_campaign_import_service.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.modules.participation.application.campaign_import_service'`

- [ ] **Step 3: Créer `backend/app/modules/participation/application/campaign_import_service.py`**

```python
"""Import des participations depuis des saisies mensuelles existantes.

Reconstruit rétroactivement une campagne bulletin d'option clôturée (choix
déjà fait, participation déjà versée) à partir des `monthly_inputs`
existantes — pour les sociétés dont la participation a été saisie directement
en paie, hors du workflow normal `create_campaign` → publication → réponse
salarié.

Voir docs/superpowers/specs/2026-07-22-import-participations-saisies-existantes-design.md.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import supabase
from app.modules.participation.domain.import_reconstruction import (
    reconstruct_bulletins_from_inputs,
)
from app.modules.participation.infrastructure.campaign_repository import (
    campaign_repository,
)


@dataclass(frozen=True)
class ImportResult:
    campaign_id: Optional[str]
    bulletins: int
    full_cash: int
    partial_cash: int
    full_pee: int
    linked_inputs: int
    skipped: bool
    dry_run: bool
    detail: str


def _fetch_company_monthly_inputs(
    company_id: str, payroll_year: int, payroll_month: int
) -> List[Dict[str, Any]]:
    result = (
        supabase.table("monthly_inputs")
        .select("id, employee_id, name, amount")
        .eq("company_id", company_id)
        .eq("year", payroll_year)
        .eq("month", payroll_month)
        .execute()
    )
    return list(result.data or [])


def _unlink_monthly_inputs(campaign_id: str) -> None:
    supabase.table("monthly_inputs").update(
        {"participation_campaign_id": None, "participation_bulletin_id": None}
    ).eq("participation_campaign_id", campaign_id).execute()


def delete_imported_campaign(campaign_id: str, company_id: str) -> None:
    """Supprime une campagne (cascade DB vers bulletins/avances) et délie les
    saisies mensuelles qui y étaient rattachées."""
    _unlink_monthly_inputs(campaign_id)
    campaign_repository.delete_campaign(campaign_id, company_id)


def import_campaign_from_inputs(
    company_id: str,
    year: int,
    payroll_year: int,
    payroll_month: int,
    *,
    created_by: Optional[str] = None,
    dry_run: bool = False,
    force: bool = False,
) -> ImportResult:
    """Reconstruit une campagne participation clôturée pour `year` depuis les
    saisies de paie `(payroll_year, payroll_month)` de `company_id`.

    Idempotent : si une campagne `(company_id, year)` avec bulletins existe
    déjà, elle est conservée (résultat `skipped=True`) sauf `force=True`. Un
    brouillon vide (sans bulletin) est toujours remplacé silencieusement.
    `dry_run=True` calcule et retourne le résultat sans rien écrire.
    """
    replaced_empty_draft = False
    for campaign in campaign_repository.list_campaigns(company_id, year):
        campaign_id = str(campaign["id"])
        counts = campaign_repository.count_bulletins_by_status(campaign_id)
        total_existing = sum(counts.values())
        if total_existing == 0:
            replaced_empty_draft = True
            if not dry_run:
                campaign_repository.delete_campaign(campaign_id, company_id)
            continue
        if not force:
            return ImportResult(
                campaign_id=campaign_id,
                bulletins=total_existing,
                full_cash=0,
                partial_cash=0,
                full_pee=0,
                linked_inputs=0,
                skipped=True,
                dry_run=dry_run,
                detail=(
                    f"Campagne {year} déjà importée ({total_existing} "
                    "bulletin(s)) — utilisez force=true pour la remplacer."
                ),
            )
        if not dry_run:
            delete_imported_campaign(campaign_id, company_id)

    rows = _fetch_company_monthly_inputs(company_id, payroll_year, payroll_month)
    bulletins = reconstruct_bulletins_from_inputs(rows)
    if not bulletins:
        return ImportResult(
            campaign_id=None,
            bulletins=0,
            full_cash=0,
            partial_cash=0,
            full_pee=0,
            linked_inputs=0,
            skipped=False,
            dry_run=dry_run,
            detail="Aucune saisie participation trouvée pour cette période.",
        )

    counts_by_choice = Counter(b.choice_type for b in bulletins)
    suffix = " (remplace un brouillon vide existant)" if replaced_empty_draft else ""

    if dry_run:
        return ImportResult(
            campaign_id=None,
            bulletins=len(bulletins),
            full_cash=counts_by_choice.get("full_cash", 0),
            partial_cash=counts_by_choice.get("partial_cash", 0),
            full_pee=counts_by_choice.get("full_pee", 0),
            linked_inputs=sum(len(b.source_input_ids) for b in bulletins),
            skipped=False,
            dry_run=True,
            detail=f"Aperçu : {len(bulletins)} bulletin(s) seraient créés{suffix}.",
        )

    campaign = campaign_repository.create_campaign(
        {
            "company_id": company_id,
            "simulation_id": None,
            "year": year,
            "exercise_label": f"PARTICIPATION {year}",
            "status": "closed",
            "payroll_year": payroll_year,
            "payroll_month": payroll_month,
            "created_by": created_by,
        }
    )
    campaign_id = str(campaign["id"])

    advances = [
        {
            "employee_id": b.employee_id,
            "amount": float(b.advance_amount),
            "label": b.advance_label,
        }
        for b in bulletins
        if b.advance_amount > 0
    ]
    campaign_repository.upsert_advances(campaign_id, advances)

    now = datetime.now(timezone.utc).isoformat()
    bulletin_rows = [
        {
            "campaign_id": campaign_id,
            "company_id": company_id,
            "employee_id": b.employee_id,
            "dispositif_type": b.dispositif_type,
            "gross_amount": float(b.gross_amount),
            "csg_non_deductible": float(b.csg_non_deductible),
            "csg_deductible": float(b.csg_deductible),
            "advance_amount": float(b.advance_amount),
            "advance_label": b.advance_label,
            "net_amount": float(b.net_amount),
            "status": "responded",
            "choice_type": b.choice_type,
            "choice_cash_amount": float(b.cash_amount)
            if b.choice_type == "partial_cash"
            else None,
            "pee_amount": float(b.pee_amount),
            "cash_amount": float(b.cash_amount),
            "responded_at": now,
        }
        for b in bulletins
    ]
    created_rows = campaign_repository.insert_bulletins(bulletin_rows)
    bulletin_id_by_employee = {
        str(row["employee_id"]): str(row["id"]) for row in created_rows
    }

    linked = 0
    for b in bulletins:
        bulletin_id = bulletin_id_by_employee.get(b.employee_id)
        if not bulletin_id or not b.source_input_ids:
            continue
        supabase.table("monthly_inputs").update(
            {
                "participation_campaign_id": campaign_id,
                "participation_bulletin_id": bulletin_id,
            }
        ).in_("id", b.source_input_ids).execute()
        linked += len(b.source_input_ids)

    return ImportResult(
        campaign_id=campaign_id,
        bulletins=len(bulletins),
        full_cash=counts_by_choice.get("full_cash", 0),
        partial_cash=counts_by_choice.get("partial_cash", 0),
        full_pee=counts_by_choice.get("full_pee", 0),
        linked_inputs=linked,
        skipped=False,
        dry_run=False,
        detail=(
            f"{len(bulletins)} bulletin(s) importé(s), {linked} saisie(s) "
            f"rattachée(s){suffix}."
        ),
    )
```

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run:
```bash
DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib" .venv-ci/bin/pytest tests/unit/participation/test_campaign_import_service.py -v
```
Expected: `7 passed`

- [ ] **Step 5: Lancer toute la suite participation pour vérifier l'absence de régression**

Run:
```bash
DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib" .venv-ci/bin/pytest tests/unit/participation tests/integration/participation -v
```
Expected: tous les tests passent (nouveaux + existants).

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/participation/application/campaign_import_service.py backend/tests/unit/participation/test_campaign_import_service.py
git commit -m "feat(participation): service d'import des campagnes depuis les saisies

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Endpoint API

**Files:**
- Modify: `backend/app/modules/participation/schemas/campaign_requests.py`
- Modify: `backend/app/modules/participation/schemas/campaign_responses.py`
- Modify: `backend/app/modules/participation/api/router.py`
- Modify: `backend/tests/integration/participation/test_campaign_api.py`

**Interfaces:**
- Consumes: `import_campaign_from_inputs`, `ImportResult` (Task 3).
- Produces: `POST /api/participation/campaigns/import-from-inputs` — body `ImportFromInputsRequest {year, payroll_year, payroll_month, dry_run?, force?}`, réponse `ImportResultResponse`. Consommé par Task 5 (frontend).

- [ ] **Step 1: Écrire les tests d'intégration (échoueront : route inexistante)**

Dans `backend/tests/integration/participation/test_campaign_api.py`, ajouter une méthode dans `class TestParticipationCampaignRhRoutes` (après `test_generate_payroll_lines_returns_200`, avant la fin de la classe) :

```python
    @patch(
        "app.modules.participation.api.router.campaign_import_service.import_campaign_from_inputs"
    )
    def test_import_from_inputs_returns_200(self, mock_import, rh_client: TestClient):
        from app.modules.participation.application.campaign_import_service import (
            ImportResult,
        )

        mock_import.return_value = ImportResult(
            campaign_id=TEST_CAMPAIGN_ID,
            bulletins=2,
            full_cash=1,
            partial_cash=0,
            full_pee=1,
            linked_inputs=3,
            skipped=False,
            dry_run=False,
            detail="2 bulletin(s) importé(s), 3 saisie(s) rattachée(s).",
        )

        response = rh_client.post(
            "/api/participation/campaigns/import-from-inputs",
            json={"year": 2025, "payroll_year": 2026, "payroll_month": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["campaign_id"] == TEST_CAMPAIGN_ID
        assert data["bulletins"] == 2
        assert data["full_pee"] == 1
        mock_import.assert_called_once()
        _, kwargs = mock_import.call_args
        assert kwargs["dry_run"] is False
        assert kwargs["force"] is False
```

Et dans `class TestParticipationCampaignEmployeeRoutes` (après `test_respond_partial_cash_returns_400_on_invalid`) :

```python
    def test_import_from_inputs_requires_rh(self, employee_client: TestClient):
        response = employee_client.post(
            "/api/participation/campaigns/import-from-inputs",
            json={"year": 2025, "payroll_year": 2026, "payroll_month": 5},
        )
        assert response.status_code == 403
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run:
```bash
DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib" .venv-ci/bin/pytest tests/integration/participation/test_campaign_api.py -v -k import_from_inputs
```
Expected: `404 Not Found` (route inexistante) sur les deux tests.

- [ ] **Step 3: Ajouter les schémas**

Dans `backend/app/modules/participation/schemas/campaign_requests.py`, ajouter à la fin du fichier :

```python
class ImportFromInputsRequest(BaseModel):
    year: int = Field(..., ge=2020, le=2100)
    payroll_year: int = Field(..., ge=2020, le=2100)
    payroll_month: int = Field(..., ge=1, le=12)
    dry_run: bool = False
    force: bool = False
```

Dans `backend/app/modules/participation/schemas/campaign_responses.py`, ajouter à la fin du fichier :

```python
class ImportResultResponse(BaseModel):
    campaign_id: Optional[str] = None
    bulletins: int = 0
    full_cash: int = 0
    partial_cash: int = 0
    full_pee: int = 0
    linked_inputs: int = 0
    skipped: bool = False
    dry_run: bool = False
    detail: str = ""
```

- [ ] **Step 4: Brancher l'endpoint dans `router.py`**

Ajouter l'import du module service (pas seulement les fonctions, pour patcher `campaign_import_service.xxx` comme `campaign_svc.xxx`), juste après la ligne existante `from app.modules.participation.application import campaign_service as campaign_svc` :

```python
from app.modules.participation.application import campaign_import_service
```

Ajouter `asdict` aux imports en tête de fichier (après `import traceback`) :

```python
from dataclasses import asdict
```

Dans le bloc d'import de `app.modules.participation.schemas.campaign_requests`, ajouter `ImportFromInputsRequest` à la liste existante. Dans le bloc d'import de `app.modules.participation.schemas.campaign_responses`, ajouter `ImportResultResponse` à la liste existante.

Ajouter la route juste après `create_campaign_route` (avant `@router.get("/campaigns", ...)`) :

```python
@router.post(
    "/campaigns/import-from-inputs",
    response_model=ImportResultResponse,
)
def import_campaign_from_inputs_route(
    body: ImportFromInputsRequest,
    user: ParticipationUserContext = Depends(get_current_user),
) -> ImportResultResponse:
    """Reconstruit une campagne clôturée à partir des saisies participation
    déjà en paie (`monthly_inputs`), sans relancer le workflow d'envoi/réponse
    salarié — pour les données saisies directement en paie hors du module.
    """
    try:
        _require_rh_or_admin(user)
        company_id = _require_company_id(user)
        _require_participation_permission(
            user, company_id, "participation.allocation.manage"
        )
        result = campaign_import_service.import_campaign_from_inputs(
            company_id,
            body.year,
            body.payroll_year,
            body.payroll_month,
            created_by=str(user.id),
            dry_run=body.dry_run,
            force=body.force,
        )
        return ImportResultResponse(**asdict(result))
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 5: Lancer les tests, vérifier qu'ils passent**

Run:
```bash
DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib" .venv-ci/bin/pytest tests/integration/participation/test_campaign_api.py -v
```
Expected: tous les tests du fichier passent, y compris les 2 nouveaux.

- [ ] **Step 6: Lancer toute la suite participation (non-régression)**

Run:
```bash
DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib" .venv-ci/bin/pytest tests/unit/participation tests/integration/participation -v
```
Expected: tous passent.

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/participation/schemas/campaign_requests.py backend/app/modules/participation/schemas/campaign_responses.py backend/app/modules/participation/api/router.py backend/tests/integration/participation/test_campaign_api.py
git commit -m "feat(participation): endpoint POST /campaigns/import-from-inputs

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Frontend — client API + UI

**Files:**
- Modify: `frontend/src/api/participation.ts`
- Modify: `frontend/src/components/saisies/ParticipationCampaignPanel.tsx`

**Interfaces:**
- Consumes: `POST /api/participation/campaigns/import-from-inputs` (Task 4), contrat JSON `{year, payroll_year, payroll_month, dry_run?, force?}` → `{campaign_id, bulletins, full_cash, partial_cash, full_pee, linked_inputs, skipped, dry_run, detail}`.
- Produces: `importParticipationFromInputs()` (client API), bouton + Dialog dans `ParticipationCampaignPanel`.

- [ ] **Step 1: Ajouter le client API**

Dans `frontend/src/api/participation.ts`, ajouter à la fin du fichier :

```typescript
export interface ImportParticipationResult {
  campaign_id: string | null;
  bulletins: number;
  full_cash: number;
  partial_cash: number;
  full_pee: number;
  linked_inputs: number;
  skipped: boolean;
  dry_run: boolean;
  detail: string;
}

export async function importParticipationFromInputs(payload: {
  year: number;
  payroll_year: number;
  payroll_month: number;
  dry_run?: boolean;
  force?: boolean;
}): Promise<ImportParticipationResult> {
  const { data } = await apiClient.post<ImportParticipationResult>(
    '/api/participation/campaigns/import-from-inputs',
    payload,
  );
  return data;
}
```

- [ ] **Step 2: Ajouter les imports dans `ParticipationCampaignPanel.tsx`**

Remplacer la ligne d'import lucide-react :
```typescript
import { Download, FileText, Megaphone, RefreshCw, Send } from 'lucide-react';
```
par :
```typescript
import { Download, FileText, Megaphone, RefreshCw, Send, Upload } from 'lucide-react';
```

Ajouter `importParticipationFromInputs` et le type `ImportParticipationResult` au bloc d'import `@/api/participation` (ordre alphabétique conservé) :
```typescript
import {
  bulletinStatusLabel,
  choiceLabel,
  closeCampaignDefaults,
  createCampaign,
  generateCampaignPayrollLines,
  generateRegularisationPayslip,
  importParticipationFromInputs,
  listCampaignBulletins,
  listCampaigns,
  publishCampaign,
  remindCampaign,
  type CampaignAdvanceInput,
  type ImportParticipationResult,
  type ParticipationBulletin,
  type ParticipationCampaign,
} from '@/api/participation';
```

Ajouter l'import des composants Dialog, juste après l'import de `Card*` :
```typescript
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
```

- [ ] **Step 3: Ajouter l'état et les mutations**

Après le bloc `const [advances, setAdvances] = useState(...)` (juste avant `const { data: campaigns = [], ... }`), ajouter :

```typescript
  const [importOpen, setImportOpen] = useState(false);
  const [importPayrollYear, setImportPayrollYear] = useState(
    defaultPayrollYear ?? year + 1,
  );
  const [importPayrollMonth, setImportPayrollMonth] = useState(
    defaultPayrollMonth ?? 5,
  );
  const [importPreview, setImportPreview] = useState<ImportParticipationResult | null>(
    null,
  );
```

Après le bloc `const payrollMut = useMutation({...});` (juste avant `const [regulPendingId, ...]`), ajouter :

```typescript
  const importPreviewMut = useMutation({
    mutationFn: () =>
      importParticipationFromInputs({
        year,
        payroll_year: importPayrollYear,
        payroll_month: importPayrollMonth,
        dry_run: true,
      }),
    onSuccess: (data) => setImportPreview(data),
    onError: (e: unknown) => {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Aperçu impossible.';
      toast({ title: 'Erreur', description: String(detail), variant: 'destructive' });
    },
  });

  const importConfirmMut = useMutation({
    mutationFn: () =>
      importParticipationFromInputs({
        year,
        payroll_year: importPayrollYear,
        payroll_month: importPayrollMonth,
        dry_run: false,
      }),
    onSuccess: (data) => {
      setImportOpen(false);
      setImportPreview(null);
      void queryClient.invalidateQueries({ queryKey: ['participation-campaigns', year] });
      toast({ title: 'Import terminé', description: data.detail });
    },
    onError: (e: unknown) => {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Import impossible.';
      toast({ title: 'Erreur', description: String(detail), variant: 'destructive' });
    },
  });
```

- [ ] **Step 4: Ajouter le bouton et le Dialog dans le JSX**

Juste après la fermeture `</CardDescription>` et `</CardHeader>` (avant `<CardContent className="space-y-6">`), le composant garde `<CardContent>` inchangé. À l'intérieur de `<CardContent className="space-y-6">`, juste avant le premier `<div className="grid grid-cols-1 gap-4 md:grid-cols-3">`, insérer :

```tsx
        <div className="flex justify-end">
          <Button variant="outline" onClick={() => setImportOpen(true)}>
            <Upload className="mr-2 h-4 w-4" />
            Importer depuis les saisies existantes
          </Button>
        </div>

        <Dialog open={importOpen} onOpenChange={setImportOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                Importer les participations {year} depuis les saisies existantes
              </DialogTitle>
              <DialogDescription>
                Reconstruit une campagne clôturée à partir des saisies de paie déjà
                enregistrées (numéraire, PEE, avances). Aucun bulletin d&apos;option
                n&apos;est envoyé aux salariés : le choix est déduit des saisies.
              </DialogDescription>
            </DialogHeader>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Année de paie</Label>
                <Input
                  type="number"
                  value={importPayrollYear}
                  onChange={(e) => {
                    setImportPayrollYear(parseInt(e.target.value, 10) || importPayrollYear);
                    setImportPreview(null);
                  }}
                />
              </div>
              <div className="space-y-2">
                <Label>Mois de paie</Label>
                <Select
                  value={String(importPayrollMonth)}
                  onValueChange={(v) => {
                    setImportPayrollMonth(parseInt(v, 10));
                    setImportPreview(null);
                  }}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {MONTH_OPTIONS.map((m) => (
                      <SelectItem key={m.value} value={String(m.value)}>
                        {m.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            {importPreview && (
              <div className="rounded-lg border bg-muted/30 p-4 text-sm space-y-1">
                <div>{importPreview.detail}</div>
                {importPreview.bulletins > 0 && (
                  <div>
                    {importPreview.full_cash} numéraire · {importPreview.partial_cash} mixte
                    · {importPreview.full_pee} PEE — {importPreview.linked_inputs} saisie(s)
                    à rattacher
                  </div>
                )}
              </div>
            )}
            <DialogFooter>
              <Button
                variant="outline"
                disabled={importPreviewMut.isPending}
                onClick={() => importPreviewMut.mutate()}
              >
                Aperçu
              </Button>
              <Button
                disabled={
                  !importPreview ||
                  importPreview.skipped ||
                  importPreview.bulletins === 0 ||
                  importConfirmMut.isPending
                }
                onClick={() => importConfirmMut.mutate()}
              >
                Confirmer l&apos;import
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

```

- [ ] **Step 5: Vérifier le typage TypeScript**

Run (depuis `frontend/`) :
```bash
npx tsc --noEmit -p .
```
Expected: aucune erreur liée à `ParticipationCampaignPanel.tsx` ou `api/participation.ts` (le projet peut avoir des erreurs préexistantes ailleurs — vérifier qu'aucune nouvelle erreur n'apparaît sur ces deux fichiers).

- [ ] **Step 6: Vérifier le lint**

Run:
```bash
npx eslint src/components/saisies/ParticipationCampaignPanel.tsx src/api/participation.ts
```
Expected: aucune erreur.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/participation.ts frontend/src/components/saisies/ParticipationCampaignPanel.tsx
git commit -m "feat(participation): UI d'import des campagnes depuis les saisies

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Exécution de l'import 2025 pour les 5 sociétés

**Files:**
- Create: `backend/scripts/import_participation_2025.py`
- Create: `backend/scripts/verify_participation_import_2025.py`

**Interfaces:**
- Consumes: `import_campaign_from_inputs` (Task 3), base Supabase réelle (cloud).
- Produces: 5 campagnes `closed` + ~188 bulletins `responded` + 291 saisies rattachées, en base réelle. Aucune interface consommée par du code ultérieur (opération terminale).

- [ ] **Step 1: Créer le script d'import**

Créer `backend/scripts/import_participation_2025.py` :

```python
"""Importe les participations 2025 depuis les saisies existantes, pour les 5
sociétés de backtest concernées.

Usage (depuis backend/) :
    DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib" .venv-ci/bin/python \
        scripts/import_participation_2025.py --dry-run
    DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib" .venv-ci/bin/python \
        scripts/import_participation_2025.py

Idempotent : relancer sans --force ne duplique rien (skip les campagnes déjà
importées). Voir docs/superpowers/specs/2026-07-22-import-participations-saisies-existantes-design.md.
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, ".")

from app.core.database import supabase  # noqa: E402
from app.modules.participation.application.campaign_import_service import (  # noqa: E402
    import_campaign_from_inputs,
)

YEAR = 2025
PAYROLL_YEAR = 2026
PAYROLL_MONTH = 5

COMPANY_NAMES = [
    "Mont Blanc Composite",
    "Cartol Industrie",
    "LEWIS",
    "Comitech Composite",
    "Colorplast",
]


def _resolve_company_ids() -> dict[str, str]:
    rows = (
        supabase.table("companies")
        .select("id, company_name")
        .in_("company_name", COMPANY_NAMES)
        .execute()
        .data
        or []
    )
    found = {r["company_name"]: r["id"] for r in rows}
    missing = set(COMPANY_NAMES) - set(found)
    if missing:
        raise SystemExit(f"Sociétés introuvables : {missing}")
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    companies = _resolve_company_ids()
    total_bulletins = 0
    for name in COMPANY_NAMES:
        company_id = companies[name]
        result = import_campaign_from_inputs(
            company_id,
            YEAR,
            PAYROLL_YEAR,
            PAYROLL_MONTH,
            dry_run=args.dry_run,
            force=args.force,
        )
        total_bulletins += result.bulletins
        print(
            f"{name:22s} campaign={result.campaign_id} bulletins={result.bulletins:3d} "
            f"(cash={result.full_cash} mixte={result.partial_cash} pee={result.full_pee}) "
            f"linked={result.linked_inputs} skipped={result.skipped} — {result.detail}"
        )
    print(f"\nTOTAL bulletins: {total_bulletins}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Lancer en dry-run et vérifier l'aperçu contre les chiffres attendus**

Run (depuis `backend/`) :
```bash
DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib" .venv-ci/bin/python scripts/import_participation_2025.py --dry-run
```
Expected : 5 lignes, `TOTAL bulletins: 188`, réparti `Mont Blanc Composite` 72, `Cartol Industrie` 65, `LEWIS` 28, `Comitech Composite` 18, `Colorplast` 5 (chiffres établis lors du brainstorming — s'il y a un écart, **s'arrêter et investiguer avant de continuer**, ne pas lancer l'import réel sur des chiffres inattendus).

- [ ] **Step 3: Lancer l'import réel**

Run:
```bash
DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib" .venv-ci/bin/python scripts/import_participation_2025.py
```
Expected : mêmes chiffres que le dry-run, `skipped=False` pour les 5 sociétés (sauf Comitech qui remplace son brouillon vide — `detail` doit mentionner « remplace un brouillon vide existant »).

- [ ] **Step 4: Créer le script de vérification en lecture seule**

Créer `backend/scripts/verify_participation_import_2025.py` :

```python
"""Vérifie l'état de l'import participation 2025 (lecture seule).

Usage (depuis backend/) :
    DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib" .venv-ci/bin/python \
        scripts/verify_participation_import_2025.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".")

from app.core.database import supabase  # noqa: E402

COMPANY_NAMES = [
    "Mont Blanc Composite",
    "Cartol Industrie",
    "LEWIS",
    "Comitech Composite",
    "Colorplast",
]


def main() -> None:
    companies = (
        supabase.table("companies")
        .select("id, company_name")
        .in_("company_name", COMPANY_NAMES)
        .execute()
        .data
        or []
    )
    company_ids = [c["id"] for c in companies]
    cmap = {c["id"]: c["company_name"] for c in companies}

    campaigns = (
        supabase.table("participation_campaigns")
        .select("id, company_id, year, status")
        .in_("company_id", company_ids)
        .eq("year", 2025)
        .execute()
        .data
        or []
    )
    print(f"Campagnes 2025 : {len(campaigns)} (attendu 5, toutes status=closed)")
    for c in campaigns:
        print(f"  {cmap.get(c['company_id'])}: status={c['status']}")

    total_bulletins = 0
    for c in campaigns:
        bulletins = (
            supabase.table("participation_bulletins")
            .select("id, choice_type, status")
            .eq("campaign_id", c["id"])
            .execute()
            .data
            or []
        )
        total_bulletins += len(bulletins)
        non_responded = [b for b in bulletins if b["status"] != "responded"]
        if non_responded:
            print(f"  ANOMALIE {cmap.get(c['company_id'])}: {len(non_responded)} bulletin(s) non 'responded'")
    print(f"Total bulletins : {total_bulletins} (attendu 188)")

    linked = (
        supabase.table("monthly_inputs")
        .select("id", count="exact")
        .in_("company_id", company_ids)
        .not_.is_("participation_campaign_id", "null")
        .execute()
    )
    print(f"Saisies rattachées : {linked.count} (attendu 291)")

    # Vérification ciblée : le montant GIRERD (PEE) doit être strictement
    # inchangé après l'import (aucune régénération de paie).
    girerd = (
        supabase.table("monthly_inputs")
        .select("amount, name")
        .in_("company_id", company_ids)
        .ilike("name", "%PEE%")
        .eq("amount", 5331.56)
        .execute()
        .data
        or []
    )
    print(f"Ligne GIRERD PEE 5331.56 toujours intacte : {'OUI' if girerd else 'NON — ALERTE'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Lancer la vérification**

Run:
```bash
DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib" .venv-ci/bin/python scripts/verify_participation_import_2025.py
```
Expected : `Campagnes 2025 : 5`, toutes `status=closed`, `Total bulletins : 188`, `Saisies rattachées : 291`, `Ligne GIRERD PEE 5331.56 toujours intacte : OUI`, aucune ligne `ANOMALIE`.

- [ ] **Step 6: Relancer le dry-run pour confirmer l'idempotence**

Run:
```bash
DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib" .venv-ci/bin/python scripts/import_participation_2025.py --dry-run
```
Expected : les 5 sociétés affichent `skipped=True` avec le message « déjà importée » (aucune duplication en re-exécutant sans `--force`).

- [ ] **Step 7: Commit des scripts**

```bash
git add backend/scripts/import_participation_2025.py backend/scripts/verify_participation_import_2025.py
git commit -m "chore(participation): scripts d'import et de vérification participation 2025

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review (à la fin de l'exécution)

Une fois les 6 tâches terminées :
- Relire la spec (`docs/superpowers/specs/2026-07-22-import-participations-saisies-existantes-design.md`) section par section et vérifier que chaque point a une tâche correspondante (couvert : reconstruction §1→Task1, service §2→Task3, endpoint §3→Task4, frontend §4→Task5, exécution §5→Task6).
- Lancer l'intégralité de la suite backend pour non-régression globale (pas seulement le module participation) :
  ```bash
  DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib" .venv-ci/bin/pytest -q
  ```
- Confirmer visuellement (capture ou lecture directe) qu'un bulletin de mai 2026 déjà généré (ex. GIRERD, MBC) affiche toujours le même montant de participation qu'avant l'import.
