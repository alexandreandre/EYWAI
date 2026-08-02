# Case « aménagement » sur le suivi médical — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permettre à la RH de cocher « aménagement de poste » en enregistrant une visite médicale réalisée, et afficher cet état en lecture seule sur la fiche du salarié.

**Architecture:** Une colonne booléenne `amenagement_poste` sur `medical_follow_up_obligations`, écrite uniquement par l'opération « marquer réalisée », propagée à travers les couches existantes du module (infrastructure → repository → application → schémas → API → client TS → écrans). La fiche salarié dérive l'état courant de la visite réalisée la plus récente, via une fonction pure testable.

**Tech Stack:** FastAPI / Pydantic / Supabase (PostgreSQL 17) côté backend ; React 18 / TypeScript / TanStack Query / shadcn-ui / Vitest côté frontend ; pytest côté backend.

**Spec:** `docs/superpowers/specs/2026-08-02-case-amenagement-suivi-medical-design.md`

## Global Constraints

- Nom de colonne et de champ, partout et sans variante : `amenagement_poste`.
- Type : `BOOLEAN NOT NULL DEFAULT FALSE` en base ; `bool = False` dans les schémas Pydantic ; `boolean` (non optionnel) dans les types TS de réponse.
- Libellé affiché à l'utilisateur, à l'identique dans les deux écrans : `Aménagement de poste`.
- La case n'est saisissable que dans le dialogue « Marquer comme réalisée ». Jamais cliquable ailleurs.
- `mark_planified` et `create_on_demand` ne sont pas modifiées.
- Aucun script de reprise de données : la colonne naît vide (aucune visite réalisée en production).
- Commandes de test backend : `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest <chemin> -q`
- Commande de test frontend : `cd frontend && npx vitest run <chemin>`
- Baseline avant travaux : `tests/unit/medical_follow_up` = **68 passed**. Ne pas juger le résultat sur la suite d'intégration complète : 51 échecs y sont pré-existants (`schedules`, `saisies_avances`).
- Branche partagée avec d'autres sessions : stager des chemins explicites, jamais `git add -A`.

---

### Task 1: Persistance de la case

**Files:**
- Create: `supabase/migrations/<horodatage>_medical_amenagement_poste.sql`
- Create: `backend/tests/unit/medical_follow_up/test_infra_queries.py`
- Modify: `backend/app/modules/medical_follow_up/infrastructure/queries.py:91-104`
- Modify: `backend/app/modules/medical_follow_up/infrastructure/repository.py:60-71`
- Modify: `backend/app/modules/medical_follow_up/domain/interfaces.py:40-49`

**Interfaces:**
- Consumes: rien (première tâche).
- Produces:
  - `update_obligation_completed(supabase, obligation_id: str, completed_date: str, justification: Optional[str], amenagement_poste: bool) -> None`
  - `MedicalObligationRepository.mark_completed(obligation_id: str, company_id: str, completed_date: str, justification: Optional[str], amenagement_poste: bool) -> None`

- [ ] **Step 1: Choisir l'horodatage de migration sans collision**

Run: `ls supabase/migrations/ | sort | tail -3`

Le dernier horodatage connu au 2026-08-02 est `20260722150000`. Utiliser `20260802120000` **s'il n'apparaît pas** dans la liste. S'il apparaît (une autre session l'a pris), incrémenter l'heure : `20260802130000`, etc. La CLI Supabase rejette les horodatages en doublon.

- [ ] **Step 2: Écrire la migration**

Créer `supabase/migrations/20260802120000_medical_amenagement_poste.sql` :

```sql
-- Case « aménagement de poste » saisie à l'enregistrement d'une visite médicale réalisée.
-- Voir docs/superpowers/specs/2026-08-02-case-amenagement-suivi-medical-design.md
ALTER TABLE medical_follow_up_obligations
  ADD COLUMN IF NOT EXISTS amenagement_poste BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN medical_follow_up_obligations.amenagement_poste IS
  'True si la visite réalisée a débouché sur un aménagement de poste. Saisi par la RH, jamais calculé.';
```

`DEFAULT FALSE` rend les lignes existantes explicitement « pas d'aménagement », ce qui est exact : aucune visite n'a jamais été enregistrée comme réalisée.

- [ ] **Step 3: Écrire le test d'infrastructure qui échoue**

Créer `backend/tests/unit/medical_follow_up/test_infra_queries.py` :

```python
"""
Tests unitaires des requêtes d'infrastructure medical_follow_up.

Client Supabase mocké ; pas de DB.
"""

from unittest.mock import MagicMock

from app.modules.medical_follow_up.infrastructure import queries as infra_queries


def _mock_supabase():
    """Client Supabase mock exposant la chaîne table().update().eq().execute()."""
    supabase = MagicMock()
    table = supabase.table.return_value
    table.update.return_value.eq.return_value.execute.return_value = None
    return supabase, table


class TestUpdateObligationCompleted:
    """Écriture d'une visite réalisée."""

    def test_writes_amenagement_poste_true(self):
        """La case cochée est persistée avec le reste de la visite."""
        supabase, table = _mock_supabase()
        infra_queries.update_obligation_completed(
            supabase, "obl-1", "2026-08-02", "Visite effectuée", True
        )
        supabase.table.assert_called_once_with("medical_follow_up_obligations")
        table.update.assert_called_once_with(
            {
                "status": "realisee",
                "completed_date": "2026-08-02",
                "justification": "Visite effectuée",
                "amenagement_poste": True,
            }
        )
        table.update.return_value.eq.assert_called_once_with("id", "obl-1")

    def test_writes_amenagement_poste_false(self):
        """Case décochée : la colonne est remise à False, jamais laissée telle quelle."""
        supabase, table = _mock_supabase()
        infra_queries.update_obligation_completed(
            supabase, "obl-1", "2026-08-02", None, False
        )
        table.update.assert_called_once_with(
            {
                "status": "realisee",
                "completed_date": "2026-08-02",
                "justification": None,
                "amenagement_poste": False,
            }
        )
```

Le second test est le plus important : il garantit qu'une correction (décocher) écrase bien la valeur précédente au lieu d'omettre la clé.

- [ ] **Step 4: Lancer le test pour vérifier qu'il échoue**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/medical_follow_up/test_infra_queries.py -q`

Expected: FAIL — `TypeError: update_obligation_completed() takes 4 positional arguments but 5 were given`

- [ ] **Step 5: Étendre la requête d'infrastructure**

Dans `backend/app/modules/medical_follow_up/infrastructure/queries.py`, remplacer `update_obligation_completed` :

```python
def update_obligation_completed(
    supabase: Any,
    obligation_id: str,
    completed_date: str,
    justification: Optional[str],
    amenagement_poste: bool,
) -> None:
    """Met à jour une obligation : status réalisée, completed_date, justification, aménagement de poste."""
    supabase.table("medical_follow_up_obligations").update(
        {
            "status": "realisee",
            "completed_date": completed_date,
            "justification": justification,
            "amenagement_poste": amenagement_poste,
        }
    ).eq("id", obligation_id).execute()
```

- [ ] **Step 6: Étendre le port du domaine**

Dans `backend/app/modules/medical_follow_up/domain/interfaces.py`, remplacer la méthode abstraite `mark_completed` :

```python
    @abstractmethod
    def mark_completed(
        self,
        obligation_id: str,
        company_id: str,
        completed_date: str,
        justification: Optional[str],
        amenagement_poste: bool,
    ) -> None:
        """Marque une obligation comme réalisée, avec ou sans aménagement de poste."""
        ...
```

- [ ] **Step 7: Étendre le repository**

Dans `backend/app/modules/medical_follow_up/infrastructure/repository.py`, remplacer `mark_completed` :

```python
    def mark_completed(
        self,
        obligation_id: str,
        company_id: str,
        completed_date: str,
        justification: Optional[str],
        amenagement_poste: bool,
    ) -> None:
        infra_queries.update_obligation_completed(
            self._supabase,
            obligation_id,
            completed_date,
            justification,
            amenagement_poste,
        )
```

- [ ] **Step 8: Lancer le test pour vérifier qu'il passe**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/medical_follow_up/test_infra_queries.py -q`

Expected: PASS — `2 passed`

- [ ] **Step 9: Vérifier la suite du module**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/medical_follow_up -q 2>&1 | tail -3`

Expected: PASS — `70 passed` (68 de baseline + 2 nouveaux).

Le changement de signature ne casse rien ici : `test_commands.py` mocke le repository avec `MagicMock`, qui accepte n'importe quelle signature, et `commands.mark_completed` appelle encore avec 4 arguments. C'est la tâche 2 qui alignera l'appel et ses assertions, dans le même commit.

- [ ] **Step 10: Commit**

```bash
git add supabase/migrations/20260802120000_medical_amenagement_poste.sql \
        backend/tests/unit/medical_follow_up/test_infra_queries.py \
        backend/app/modules/medical_follow_up/infrastructure/queries.py \
        backend/app/modules/medical_follow_up/infrastructure/repository.py \
        backend/app/modules/medical_follow_up/domain/interfaces.py
git commit -m "feat(medical): persister la case aménagement de poste

Colonne amenagement_poste sur medical_follow_up_obligations, écrite par
l'opération « marquer réalisée ». Le test couvre la remise à False, pour
qu'une correction écrase la valeur au lieu d'omettre la clé.

Refs afaire #10"
```

---

### Task 2: Écriture via l'API

**Files:**
- Modify: `backend/app/modules/medical_follow_up/schemas/requests.py:17-22`
- Modify: `backend/app/modules/medical_follow_up/application/commands.py:35-48`
- Modify: `backend/tests/unit/medical_follow_up/test_commands.py:76-105`

**Interfaces:**
- Consumes: `MedicalObligationRepository.mark_completed(obligation_id, company_id, completed_date, justification, amenagement_poste)` (Task 1).
- Produces: `MarkCompletedBody(completed_date: str, justification: Optional[str] = None, amenagement_poste: bool = False)` — corps accepté par `PATCH /api/medical-follow-up/obligations/{id}/completed`.

- [ ] **Step 1: Mettre à jour le test existant et ajouter les nouveaux cas**

Dans `backend/tests/unit/medical_follow_up/test_commands.py`, remplacer entièrement la classe `TestMarkCompleted` :

```python
@patch("app.modules.medical_follow_up.application.commands.get_obligation_repository")
class TestMarkCompleted:
    """Commande mark_completed."""

    def test_returns_ok_when_obligation_exists(self, mock_get_repo):
        """Obligation trouvée → appelle mark_completed et retourne {"ok": True}."""
        repo = _mock_repo()
        mock_get_repo.return_value = repo
        body = MarkCompletedBody(
            completed_date="2025-04-20", justification="Visite effectuée"
        )
        result = commands.mark_completed(
            "obl-1", body, "co-1", current_user=MagicMock()
        )
        assert result == {"ok": True}
        repo.obligation_exists.assert_called_once_with("obl-1", "co-1")
        repo.mark_completed.assert_called_once_with(
            "obl-1", "co-1", "2025-04-20", "Visite effectuée", False
        )

    def test_transmits_amenagement_poste(self, mock_get_repo):
        """Case cochée → transmise telle quelle au repository."""
        repo = _mock_repo()
        mock_get_repo.return_value = repo
        body = MarkCompletedBody(
            completed_date="2025-04-20",
            justification="Visite effectuée",
            amenagement_poste=True,
        )
        commands.mark_completed("obl-1", body, "co-1", current_user=MagicMock())
        repo.mark_completed.assert_called_once_with(
            "obl-1", "co-1", "2025-04-20", "Visite effectuée", True
        )

    def test_amenagement_poste_defaults_to_false(self, mock_get_repo):
        """Champ absent du corps → False. Garantit la compatibilité des appels existants."""
        repo = _mock_repo()
        mock_get_repo.return_value = repo
        body = MarkCompletedBody(completed_date="2025-04-20")
        assert body.amenagement_poste is False
        commands.mark_completed("obl-1", body, "co-1", current_user=MagicMock())
        repo.mark_completed.assert_called_once_with(
            "obl-1", "co-1", "2025-04-20", None, False
        )

    def test_raises_404_when_obligation_not_found(self, mock_get_repo):
        """Obligation inexistante → HTTPException 404."""
        repo = _mock_repo()
        repo.obligation_exists.return_value = False
        mock_get_repo.return_value = repo
        body = MarkCompletedBody(completed_date="2025-04-20")
        with pytest.raises(HTTPException) as exc_info:
            commands.mark_completed(
                "obl-unknown", body, "co-1", current_user=MagicMock()
            )
        assert exc_info.value.status_code == 404
        repo.mark_completed.assert_not_called()
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/medical_follow_up/test_commands.py -q`

Expected: FAIL — `ValidationError` ou `AttributeError` sur `amenagement_poste`, le champ n'existant pas encore dans `MarkCompletedBody`.

- [ ] **Step 3: Étendre le schéma de requête**

Dans `backend/app/modules/medical_follow_up/schemas/requests.py`, remplacer `MarkCompletedBody` :

```python
class MarkCompletedBody(BaseModel):
    """Corps pour PATCH .../obligations/{id}/completed."""

    completed_date: str
    justification: Optional[str] = None
    amenagement_poste: bool = False
```

Le défaut `False` préserve la compatibilité : un appel qui ignore le champ se comporte comme avant.

- [ ] **Step 4: Transmettre le champ dans la commande**

Dans `backend/app/modules/medical_follow_up/application/commands.py`, dans `mark_completed`, remplacer l'appel au repository :

```python
    repo.mark_completed(
        obligation_id,
        company_id,
        body.completed_date,
        body.justification,
        body.amenagement_poste,
    )
```

- [ ] **Step 5: Lancer la suite du module**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/medical_follow_up -q`

Expected: PASS — `72 passed` (68 de baseline, + 2 de la tâche 1, + 2 nouveaux ici).

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/medical_follow_up/schemas/requests.py \
        backend/app/modules/medical_follow_up/application/commands.py \
        backend/tests/unit/medical_follow_up/test_commands.py
git commit -m "feat(medical): accepter la case aménagement dans le corps de la visite réalisée

amenagement_poste, défaut False pour préserver les appels existants.

Refs afaire #10"
```

---

### Task 3: Lecture via l'API

**Files:**
- Modify: `backend/app/modules/medical_follow_up/schemas/responses.py:11-32`
- Modify: `backend/app/modules/medical_follow_up/application/dto.py:9-52`
- Modify: `backend/app/modules/medical_follow_up/api/router.py:248-270`
- Modify: `backend/app/modules/medical_follow_up/domain/entities.py:8-29`
- Modify: `backend/app/modules/medical_follow_up/infrastructure/mappers.py:9-27`
- Modify: `backend/tests/unit/medical_follow_up/test_queries.py`

**Interfaces:**
- Consumes: la colonne `amenagement_poste` présente dans les lignes DB (Task 1).
- Produces: `ObligationListItem.amenagement_poste: bool` et `ObligationListDTO.amenagement_poste: bool` — champ présent dans toutes les réponses de liste, y compris `GET /me`.

- [ ] **Step 1: Écrire le test de propagation qui échoue**

Dans `backend/tests/unit/medical_follow_up/test_queries.py`, ajouter à la fin du fichier :

```python
class TestObligationDtoAmenagementPoste:
    """Propagation de la case aménagement depuis la ligne DB."""

    def test_from_row_reads_amenagement_poste(self):
        """La colonne est reprise telle quelle dans le DTO."""
        from app.modules.medical_follow_up.application.dto import ObligationListDTO

        dto = ObligationListDTO.from_row(
            {
                "id": "obl-1",
                "company_id": "co-1",
                "employee_id": "emp-1",
                "visit_type": "vip",
                "trigger_type": "embauche",
                "due_date": "2026-09-01",
                "priority": 2,
                "status": "realisee",
                "amenagement_poste": True,
            }
        )
        assert dto.amenagement_poste is True

    def test_from_row_defaults_to_false_when_column_absent(self):
        """Ligne sans la colonne (sélection partielle) → False, jamais None."""
        from app.modules.medical_follow_up.application.dto import ObligationListDTO

        dto = ObligationListDTO.from_row(
            {
                "id": "obl-1",
                "company_id": "co-1",
                "employee_id": "emp-1",
                "visit_type": "vip",
                "trigger_type": "embauche",
                "due_date": "2026-09-01",
                "priority": 2,
                "status": "a_faire",
            }
        )
        assert dto.amenagement_poste is False
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/medical_follow_up/test_queries.py -q`

Expected: FAIL — `AttributeError: 'ObligationListDTO' object has no attribute 'amenagement_poste'`

- [ ] **Step 3: Étendre le DTO**

Dans `backend/app/modules/medical_follow_up/application/dto.py`, ajouter le champ à la fin de la liste des attributs de `ObligationListDTO` (après `employee_last_name`) :

```python
    amenagement_poste: bool = False
```

et, dans `from_row`, ajouter après `employee_last_name=emp.get("last_name"),` :

```python
            amenagement_poste=bool(r.get("amenagement_poste") or False),
```

Le `or False` protège du `None` que renverrait une ligne antérieure à la migration.

- [ ] **Step 4: Étendre le schéma de réponse**

Dans `backend/app/modules/medical_follow_up/schemas/responses.py`, ajouter à la fin des champs de `ObligationListItem` :

```python
    amenagement_poste: bool = False
```

- [ ] **Step 5: Étendre la conversion DTO → réponse**

Dans `backend/app/modules/medical_follow_up/api/router.py`, dans `_to_list_item`, ajouter le champ à la fin de la construction de `ObligationListItem` :

```python
        amenagement_poste=d.amenagement_poste,
```

- [ ] **Step 6: Étendre l'entité et le mapper**

Dans `backend/app/modules/medical_follow_up/domain/entities.py`, ajouter à la fin des attributs de `MedicalObligation` :

```python
    amenagement_poste: bool = False
```

Dans `backend/app/modules/medical_follow_up/infrastructure/mappers.py`, ajouter à la fin de la construction dans `row_to_obligation_entity` :

```python
        amenagement_poste=bool(row.get("amenagement_poste") or False),
```

- [ ] **Step 7: Lancer la suite du module**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/medical_follow_up -q`

Expected: PASS — `74 passed`

- [ ] **Step 8: Vérifier l'absence de régression sur les tests unitaires**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit -q 2>&1 | tail -3`

Expected: aucun échec nouveau par rapport à la baseline de la branche. Si un échec apparaît hors `medical_follow_up`, vérifier qu'il préexiste (`git stash` n'est pas fiable ici : d'autres sessions ont des fichiers modifiés non commités — comparer plutôt avec `git stash list` vide et un `pytest` sur `origin/main`).

- [ ] **Step 9: Commit**

```bash
git add backend/app/modules/medical_follow_up/schemas/responses.py \
        backend/app/modules/medical_follow_up/application/dto.py \
        backend/app/modules/medical_follow_up/api/router.py \
        backend/app/modules/medical_follow_up/domain/entities.py \
        backend/app/modules/medical_follow_up/infrastructure/mappers.py \
        backend/tests/unit/medical_follow_up/test_queries.py
git commit -m "feat(medical): exposer la case aménagement dans les réponses obligations

Champ présent dans toutes les listes, y compris GET /me où le salarié lit
sa propre donnée.

Refs afaire #10"
```

---

### Task 4: La case dans le dialogue de visite

**Files:**
- Modify: `frontend/src/api/medicalFollowUp.ts:7-24` et `:86-91`
- Modify: `frontend/src/pages/rh/MedicalFollowUp.tsx` (état, mutation, dialogue)
- Modify: `frontend/src/components/employee-detail/EmployeeDetailMedicalTab.tsx` (état, mutation, dialogue)

**Interfaces:**
- Consumes: `PATCH .../completed` acceptant `amenagement_poste` (Task 2) ; `ObligationListItem.amenagement_poste` en réponse (Task 3).
- Produces: état React `completedAmenagement: boolean` dans les deux écrans, envoyé à chaque `markCompleted`.

- [ ] **Step 1: Étendre le client API**

Dans `frontend/src/api/medicalFollowUp.ts`, ajouter à la fin de l'interface `ObligationListItem` (après `employee_last_name`) :

```ts
  amenagement_poste?: boolean;
```

et remplacer la signature de `markCompleted` :

```ts
export async function markCompleted(
  obligationId: string,
  body: { completed_date: string; justification?: string; amenagement_poste?: boolean }
): Promise<void> {
  await apiClient.patch(`/api/medical-follow-up/obligations/${obligationId}/completed`, body);
}
```

- [ ] **Step 2: Ajouter l'état dans la page de pilotage**

Dans `frontend/src/pages/rh/MedicalFollowUp.tsx`, après la ligne `const [completedComment, setCompletedComment] = useState("");` (≈ ligne 611) :

```tsx
  const [completedAmenagement, setCompletedAmenagement] = useState(false);
```

Importer le composant, à côté des autres imports `@/components/ui/` :

```tsx
import { Checkbox } from "@/components/ui/checkbox";
```

- [ ] **Step 3: Envoyer le champ et le préremplir**

Dans le même fichier, dans `handleMarkCompleted` (≈ ligne 923), remplacer l'appel :

```tsx
      await markCompleted(completedModal.id, {
        completed_date: completedDate,
        justification: completedComment || undefined,
        amenagement_poste: completedAmenagement,
      });
```

Dans l'entrée de menu « Marquer réalisée » (≈ ligne 1378), ajouter après `setCompletedComment(o.justification || "");` :

```tsx
                                              setCompletedAmenagement(o.amenagement_poste === true);
```

Le préremplissage depuis l'obligation est ce qui rendra la réédition de la tâche 5 correcte.

- [ ] **Step 4: Ajouter la case au dialogue**

Dans le même fichier, dans le `<Dialog>` « Marquer comme réalisée » (≈ ligne 1556), après le bloc du commentaire et avant la fermeture du `<div className="grid gap-4 py-4">` :

```tsx
              <div className="flex items-center gap-2">
                <Checkbox
                  id="completed-amenagement"
                  checked={completedAmenagement}
                  onCheckedChange={(checked) => setCompletedAmenagement(checked === true)}
                />
                <Label htmlFor="completed-amenagement" className="cursor-pointer font-normal">
                  Aménagement de poste
                </Label>
              </div>
```

- [ ] **Step 5: Répéter dans l'onglet de la fiche salarié**

Dans `frontend/src/components/employee-detail/EmployeeDetailMedicalTab.tsx` :

Ajouter l'import `import { Checkbox } from "@/components/ui/checkbox";`.

Après `const [completedComment, setCompletedComment] = useState("");` (≈ ligne 103) :

```tsx
  const [completedAmenagement, setCompletedAmenagement] = useState(false);
```

Dans `completedMutation.mutationFn` (≈ ligne 147), remplacer l'appel :

```tsx
      await markCompleted(completedModal.id, {
        completed_date: completedDate,
        justification: completedComment || undefined,
        amenagement_poste: completedAmenagement,
      });
```

Dans `openCompleted` (≈ ligne 207), ajouter :

```tsx
    setCompletedAmenagement(o.amenagement_poste === true);
```

Dans le dialogue « Marquer comme réalisée » de ce fichier, ajouter le même bloc de case qu'à l'étape 4, en changeant l'identifiant pour éviter une collision d'attribut `id` si les deux écrans coexistaient :

```tsx
              <div className="flex items-center gap-2">
                <Checkbox
                  id="employee-completed-amenagement"
                  checked={completedAmenagement}
                  onCheckedChange={(checked) => setCompletedAmenagement(checked === true)}
                />
                <Label htmlFor="employee-completed-amenagement" className="cursor-pointer font-normal">
                  Aménagement de poste
                </Label>
              </div>
```

- [ ] **Step 6: Vérifier la compilation**

Run: `cd frontend && npx tsc --noEmit`

Expected: aucune erreur sur les trois fichiers modifiés. (Des erreurs préexistantes ailleurs sont possibles sur cette branche partagée : ne juger que les fichiers touchés.)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/medicalFollowUp.ts \
        frontend/src/pages/rh/MedicalFollowUp.tsx \
        frontend/src/components/employee-detail/EmployeeDetailMedicalTab.tsx
git commit -m "feat(medical): cocher l'aménagement de poste en enregistrant une visite

La case est saisie dans la note de visite, sur les deux écrans qui portent
ce dialogue, et préremplie depuis l'obligation.

Refs afaire #10"
```

---

### Task 5: Rendre les visites réalisées modifiables

**Files:**
- Modify: `frontend/src/pages/rh/MedicalFollowUp.tsx:1353-1394`
- Modify: `frontend/src/components/employee-detail/EmployeeDetailMedicalTab.tsx:427-445`

**Interfaces:**
- Consumes: l'état `completedAmenagement` et le préremplissage (Task 4).
- Produces: rien de nouveau pour les tâches suivantes.

Sans cette tâche la case est en écriture unique : une erreur de saisie serait irrattrapable, et un aménagement notifié après coup impossible à enregistrer. Le backend accepte déjà de rejouer `PATCH .../completed` — seul l'affichage l'interdit.

- [ ] **Step 1: Rouvrir le menu sur la page de pilotage**

Dans `frontend/src/pages/rh/MedicalFollowUp.tsx`, remplacer la condition de la cellule d'actions (ligne 1353) et son contenu. Remplacer :

```tsx
                                    {o.status !== "realisee" && o.status !== "annulee" ? (
```

par :

```tsx
                                    {o.status !== "annulee" ? (
```

Puis, à l'intérieur du `<DropdownMenuContent align="end">`, rendre les deux entrées existantes conditionnelles et ajouter celle de modification :

```tsx
                                        <DropdownMenuContent align="end">
                                          {o.status !== "realisee" && (
                                            <>
                                              <DropdownMenuItem
                                                onClick={() => {
                                                  setPlanifiedModal(o);
                                                  setPlanifiedDate(
                                                    o.planned_date || new Date().toISOString().slice(0, 10)
                                                  );
                                                  setPlanifiedComment(o.justification || "");
                                                }}
                                              >
                                                Marquer planifiée
                                              </DropdownMenuItem>
                                              <DropdownMenuItem
                                                onClick={() => {
                                                  setCompletedModal(o);
                                                  setCompletedDate(
                                                    o.completed_date ||
                                                      new Date().toISOString().slice(0, 10)
                                                  );
                                                  setCompletedComment(o.justification || "");
                                                  setCompletedAmenagement(o.amenagement_poste === true);
                                                }}
                                              >
                                                Marquer réalisée
                                              </DropdownMenuItem>
                                            </>
                                          )}
                                          {o.status === "realisee" && (
                                            <DropdownMenuItem
                                              onClick={() => {
                                                setCompletedModal(o);
                                                setCompletedDate(
                                                  o.completed_date ||
                                                    new Date().toISOString().slice(0, 10)
                                                );
                                                setCompletedComment(o.justification || "");
                                                setCompletedAmenagement(o.amenagement_poste === true);
                                              }}
                                            >
                                              Modifier la visite
                                            </DropdownMenuItem>
                                          )}
                                        </DropdownMenuContent>
```

Les visites `annulee` restent figées : la condition de la cellule les exclut toujours.

- [ ] **Step 2: Ajouter le bouton dans l'onglet de la fiche salarié**

Dans `frontend/src/components/employee-detail/EmployeeDetailMedicalTab.tsx`, remplacer le contenu de la cellule d'actions (ligne 427) :

```tsx
                            <TableCell className="text-right">
                              {o.status !== "realisee" && o.status !== "annulee" && (
                                <div className="flex justify-end gap-1">
                                  <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => openPlanified(o)}
                                  >
                                    Planifier
                                  </Button>
                                  <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => openCompleted(o)}
                                  >
                                    Réalisée
                                  </Button>
                                </div>
                              )}
                              {o.status === "realisee" && (
                                <div className="flex justify-end">
                                  <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => openCompleted(o)}
                                  >
                                    Modifier
                                  </Button>
                                </div>
                              )}
                            </TableCell>
```

`openCompleted` préremplit déjà la case depuis la tâche 4 : rien d'autre à faire ici.

- [ ] **Step 3: Vérifier la compilation**

Run: `cd frontend && npx tsc --noEmit`

Expected: aucune erreur sur les deux fichiers modifiés.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/rh/MedicalFollowUp.tsx \
        frontend/src/components/employee-detail/EmployeeDetailMedicalTab.tsx
git commit -m "feat(medical): permettre de corriger une visite déjà réalisée

Sans cela la case aménagement serait en écriture unique. Le backend
acceptait déjà de rejouer l'opération ; seul l'affichage la masquait. Les
visites annulées restent figées.

Refs afaire #10"
```

---

### Task 6: Le badge sur la fiche salarié

**Files:**
- Create: `frontend/src/lib/medicalFollowUpLabels.test.ts`
- Modify: `frontend/src/lib/medicalFollowUpLabels.ts` (ajout en fin de fichier)
- Modify: `frontend/src/components/employee-detail/EmployeeDetailMedicalTab.tsx:297-306`

**Interfaces:**
- Consumes: `ObligationListItem.amenagement_poste` (Task 3, Task 4).
- Produces: `hasCurrentWorkplaceAccommodation(obligations: ObligationListItem[]): boolean`

- [ ] **Step 1: Écrire les tests de la règle de dérivation**

Créer `frontend/src/lib/medicalFollowUpLabels.test.ts` :

```ts
import { describe, expect, it } from "vitest";
import type { ObligationListItem } from "@/api/medicalFollowUp";
import { hasCurrentWorkplaceAccommodation } from "./medicalFollowUpLabels";

function obligation(over: Partial<ObligationListItem>): ObligationListItem {
  return {
    id: "obl",
    company_id: "co-1",
    employee_id: "emp-1",
    visit_type: "vip",
    trigger_type: "embauche",
    due_date: "2026-09-01",
    priority: 2,
    status: "realisee",
    rule_source: "legal",
    ...over,
  };
}

describe("hasCurrentWorkplaceAccommodation", () => {
  it("retourne false sans aucune obligation", () => {
    expect(hasCurrentWorkplaceAccommodation([])).toBe(false);
  });

  it("retourne false quand aucune visite n'est réalisée", () => {
    const obligations = [
      obligation({ id: "a", status: "a_faire", amenagement_poste: true }),
    ];
    expect(hasCurrentWorkplaceAccommodation(obligations)).toBe(false);
  });

  it("retourne true pour une visite réalisée avec aménagement", () => {
    const obligations = [
      obligation({ id: "a", completed_date: "2026-05-01", amenagement_poste: true }),
    ];
    expect(hasCurrentWorkplaceAccommodation(obligations)).toBe(true);
  });

  it("retourne false pour une visite réalisée sans aménagement", () => {
    const obligations = [
      obligation({ id: "a", completed_date: "2026-05-01", amenagement_poste: false }),
    ];
    expect(hasCurrentWorkplaceAccommodation(obligations)).toBe(false);
  });

  it("ne retient que la visite réalisée la plus récente", () => {
    const obligations = [
      obligation({ id: "vieille", completed_date: "2023-01-10", amenagement_poste: true }),
      obligation({ id: "recente", completed_date: "2026-05-01", amenagement_poste: false }),
    ];
    expect(hasCurrentWorkplaceAccommodation(obligations)).toBe(false);
  });

  it("affiche l'aménagement posé par la visite la plus récente", () => {
    const obligations = [
      obligation({ id: "vieille", completed_date: "2023-01-10", amenagement_poste: false }),
      obligation({ id: "recente", completed_date: "2026-05-01", amenagement_poste: true }),
    ];
    expect(hasCurrentWorkplaceAccommodation(obligations)).toBe(true);
  });

  it("en cas d'ex aequo de dates, l'aménagement l'emporte", () => {
    const obligations = [
      obligation({ id: "sans", completed_date: "2026-05-01", amenagement_poste: false }),
      obligation({ id: "avec", completed_date: "2026-05-01", amenagement_poste: true }),
    ];
    expect(hasCurrentWorkplaceAccommodation(obligations)).toBe(true);
  });

  it("ignore les visites réalisées sans date de réalisation", () => {
    const obligations = [
      obligation({ id: "sans-date", completed_date: null, amenagement_poste: true }),
    ];
    expect(hasCurrentWorkplaceAccommodation(obligations)).toBe(false);
  });
});
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `cd frontend && npx vitest run src/lib/medicalFollowUpLabels.test.ts`

Expected: FAIL — `hasCurrentWorkplaceAccommodation is not a function` (l'export n'existe pas).

- [ ] **Step 3: Implémenter la fonction**

Ajouter à la fin de `frontend/src/lib/medicalFollowUpLabels.ts` :

```ts
/**
 * True si le salarié a un aménagement de poste en cours.
 *
 * Seule la visite réalisée la plus récente fait foi : un aménagement se lève,
 * et cumuler l'historique afficherait à vie un aménagement terminé.
 * En cas d'ex aequo de dates, l'aménagement l'emporte — mieux vaut signaler
 * un aménagement levé que d'en masquer un actif.
 */
export function hasCurrentWorkplaceAccommodation(obligations: ObligationListItem[]): boolean {
  let latest = "";
  let accommodation = false;
  for (const o of obligations) {
    if (o.status !== "realisee" || !o.completed_date) continue;
    if (o.completed_date > latest) {
      latest = o.completed_date;
      accommodation = o.amenagement_poste === true;
    } else if (o.completed_date === latest && o.amenagement_poste === true) {
      accommodation = true;
    }
  }
  return accommodation;
}
```

Les `completed_date` sont des chaînes `YYYY-MM-DD` : la comparaison lexicographique est équivalente à la comparaison chronologique, sans construire de `Date`.

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `cd frontend && npx vitest run src/lib/medicalFollowUpLabels.test.ts`

Expected: PASS — `8 passed`

- [ ] **Step 5: Afficher le badge**

Dans `frontend/src/components/employee-detail/EmployeeDetailMedicalTab.tsx`, ajouter l'import :

```tsx
  hasCurrentWorkplaceAccommodation,
```

dans le bloc d'import existant depuis `@/lib/medicalFollowUpLabels`.

Après la ligne `const nextObligation = useMemo(() => getNextObligation(obligations), [obligations]);` (≈ ligne 95) :

```tsx
  const hasAccommodation = useMemo(
    () => hasCurrentWorkplaceAccommodation(obligations),
    [obligations]
  );
```

Dans la rangée de badges (ligne 297), après le badge `counts.completed` :

```tsx
                {hasAccommodation && (
                  <Badge variant="outline">Aménagement de poste</Badge>
                )}
```

Rien n'est affiché en l'absence d'aménagement : l'écran ne doit rien affirmer sur la santé d'un salarié dont on ne sait rien.

- [ ] **Step 6: Vérifier la compilation et la suite front**

Run: `cd frontend && npx tsc --noEmit && npx vitest run src/lib/medicalFollowUpLabels.test.ts`

Expected: compilation sans erreur sur les fichiers touchés, `8 passed`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/medicalFollowUpLabels.ts \
        frontend/src/lib/medicalFollowUpLabels.test.ts \
        frontend/src/components/employee-detail/EmployeeDetailMedicalTab.tsx
git commit -m "feat(medical): afficher l'aménagement de poste sur la fiche salarié

Badge en lecture seule, dérivé de la visite réalisée la plus récente. Rien
n'est affiché en l'absence d'aménagement.

Refs afaire #10"
```

---

### Task 7: Recette et mise en production

**Files:** aucun fichier de code. Cette tâche vérifie le comportement réel et prépare la bascule.

**Interfaces:**
- Consumes: l'ensemble des tâches précédentes.
- Produces: rien.

- [ ] **Step 1: Lancer la suite unitaire complète**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit -q 2>&1 | tail -3`

Expected: aucun échec nouveau. La CI ne bloque que sur `tests/unit`.

- [ ] **Step 2: Appliquer la migration sur l'environnement de test**

L'environnement de test n'applique **aucune** migration à son déploiement. La colonne doit y être créée à la main avant toute recette, sinon l'écran renverra une erreur 500 à l'enregistrement.

Se connecter au pooler du projet de test (`aws-0-…pooler.supabase.com:5432`, utilisateur `postgres.<project_ref>`, **pas** le port 6543) et exécuter le contenu de la migration de la tâche 1.

Voir `docs/guide-environnement-test.md`.

- [ ] **Step 3: Recette fonctionnelle sur le test**

Sur l'environnement de test, avec un compte RH :

1. Ouvrir une fiche salarié ayant une obligation, onglet « Suivi médical ».
2. « Marquer réalisée », cocher « Aménagement de poste », enregistrer.
3. Vérifier que le badge « Aménagement de poste » apparaît dans la rangée de badges en tête d'onglet.
4. « Modifier », décocher, enregistrer. Vérifier que le badge disparaît.
5. Sur `/medical-follow-up`, vérifier que le menu d'une visite réalisée propose « Modifier la visite » et que la case y est bien prérenseignée.
6. Vérifier qu'une visite `annulee` n'offre toujours aucune action.

- [ ] **Step 4: Prévenir Elsa avant la mise en production**

La case restera vide partout au lendemain de la bascule : en production, les 27 obligations sont toutes au statut « à faire » et aucune visite n'a jamais été enregistrée comme réalisée. C'est le comportement attendu, mais sans cet avertissement elle conclura à un défaut.

- [ ] **Step 5: Signaler l'écart de couverture**

Le suivi médical ne couvre que 23 salariés sur 240 actifs, avec uniquement des VIP (22) et des mi-carrière (5). C'est hors du périmètre de #10, mais cela limite la portée de la case. Proposer à Alexandre d'en faire une ligne distincte de `docs/afaire.md`.

- [ ] **Step 6: Cocher #10 dans le backlog**

Une fois la production vérifiée, mettre à jour `docs/afaire.md`. Ne stager que ce fichier : la branche est partagée avec d'autres sessions.
