# Prime transport paramétrable — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permettre à la RH de définir une fois la prime de transport d'un salarié et de la retrouver chaque mois dans les primes, déjà proratisée et modifiable, puis rétablir les plafonds d'exonération de frais professionnels que le moteur n'applique plus.

**Architecture:** Le montant contractuel reste sur la fiche salarié (`specificites_paie.transport`), là où vit l'avenant. Une règle du moteur `payroll_variables` existant génère chaque mois une ligne visible dans Saisies > Primes, calculée par des fonctions de domaine pures. L'ajout silencieux actuel du moteur de paie est retiré pour éviter le double comptage. Les plafonds sont réparés après assainissement de la sémantique des quantités, ordre imposé par le § 3.5 de la spec.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pytest, Supabase (PostgreSQL 17), React 18 + TypeScript + Vite, shadcn/ui, TanStack Query.

**Spec :** `docs/superpowers/specs/2026-08-02-prime-transport-parametrable-design.md`

## Global Constraints

- Toutes les commandes Python se lancent depuis `backend/` avec le préfixe `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` et l'interpréteur `.venv-ci/bin/python`. Sans ce préfixe, l'import de `psycopg`/`pydantic-core` échoue sur macOS.
- La CI ne juge que `tests/unit`. Les 51 échecs de `tests/integration` (`schedules`, `saisies_avances`) sont pré-existants et ne doivent pas être considérés comme des régressions.
- Le moteur de paie est **généraliste** : jamais de règle spécifique à un salarié dans le code. Les données par salarié sont en base, la paramétrisation lisible par un RH est encouragée.
- Aucune migration ne doit réutiliser un horodatage existant dans `supabase/migrations/` — l'horodatage est la clé primaire de la CLI Supabase. Les migrations s'appliquent automatiquement en production depuis le 31/07/2026 ; le déploiement de l'environnement de test n'en applique aucune.
- Ne jamais fabriquer d'adresse e-mail de salarié.
- L'arbre de travail et la branche Git sont partagés avec d'autres sessions. Stager des chemins explicites, jamais `git add -A` ni `git add .`.
- Blocs 1 à 3 : **aucun euro ne doit bouger** sur les bulletins existants. Bloc 4 : backtest complet avant merge.
- Le barème de frais professionnels actif est stocké sous la forme `config_data["FRAIS_PRO"][0]["sections"]` dans `payroll_config`, `config_key = 'frais_pro'`, `is_active = true`. Valeurs repas actives : `sur_lieu_travail` 7,50 € / `hors_locaux_sans_restaurant` 10,40 € / `hors_locaux_avec_restaurant` 21,40 €. Plafonds `mobilite_durable.employeurs_prives` : `limite_base` 600 €/an, `limite_cumul_transport_public` 900 €/an, `limite_cumul_carburant_total` 600 €/an, `limite_cumul_carburant_part_carburant` 300 €/an.

---

## Structure des fichiers

**Créés :**

| Fichier | Responsabilité |
|---|---|
| `backend/app/modules/payroll_variables/domain/transport_allowance.py` | Calcul pur du montant mensuel de transport : prorata entrée/sortie, date d'effet, absence totale |
| `backend/tests/unit/payroll_variables/test_transport_allowance.py` | Tests du calcul pur |
| `backend/app/modules/payroll/engine/plafond_transport.py` | Lecture du plafond annuel et calcul du dépassement (pur) |
| `backend/tests/unit/payroll/test_plafond_transport.py` | Tests du plafond annuel |
| `backend/tests/unit/payroll/test_frais_pro_sections.py` | Fige la forme réellement stockée du barème frais pro |
| `backend/scripts/normalize_panier_quantities.py` | Reprise des 62 lignes MBC à sémantique inversée |
| `supabase/migrations/20260803090000_monthly_inputs_quantity_kind.sql` | Colonnes `quantity_kind` et `manual_override` sur `monthly_inputs` |

**Modifiés :**

| Fichier | Nature du changement |
|---|---|
| `backend/app/modules/payroll_variables/domain/rules.py` | Ciblage par salarié + nouveau `rule_type` |
| `backend/app/modules/payroll_variables/schemas/requests.py` | Nouveau `rule_type` dans le `Literal` |
| `backend/app/modules/payroll_variables/application/generate_monthly.py` | Branche de génération transport |
| `backend/app/modules/payroll_variables/infrastructure/repository.py` | `upsert_monthly_input` respecte `manual_override` |
| `backend/app/modules/monthly_inputs/schemas/requests.py` | Schéma de mise à jour |
| `backend/app/modules/monthly_inputs/application/commands.py` | Commande de mise à jour |
| `backend/app/modules/monthly_inputs/api/router.py` | `PATCH /api/monthly-inputs/{id}` |
| `backend/app/modules/payroll/engine/calcul_net.py:460-469` | Retrait de l'ajout silencieux |
| `backend/app/modules/payroll/engine/calcul_frais.py` | Lecture réelle des sections + plafond situationnel |
| `backend/app/modules/payroll/engine/controles_convention.py` | Contrôle de dépassement transport |
| `backend/app/modules/payroll/documents/payslip_generator.py` | Appel du contrôle transport |
| `frontend/src/features/employee-detail/components/EmployeeProfileEditForm.tsx` | Libellé + date d'effet |
| `frontend/src/features/employee-detail/components/employeeProfileFormUtils.ts` | Mapping de la date d'effet |
| `frontend/src/features/employee-detail/types.ts` | Type du bloc transport |
| `frontend/src/api/saisies.ts` | Appel `PATCH` |
| `frontend/src/components/saisies/PrimesTab.tsx` | Édition d'une ligne |

---

## Bloc 1 — Le montant contractuel

### Task 1: Date d'effet sur l'indemnité transport (fiche salarié)

**Files:**
- Modify: `frontend/src/features/employee-detail/types.ts:89`
- Modify: `frontend/src/features/employee-detail/components/employeeProfileFormUtils.ts:70-71,129-131`
- Modify: `frontend/src/features/employee-detail/components/EmployeeProfileEditForm.tsx:588-600`

**Interfaces:**
- Consomme : rien.
- Produit : le chemin `specificites_paie.transport.indemnite_date_effet` (chaîne ISO `YYYY-MM-DD` ou `null`), lu par la Task 4.

Le champ `indemnite_mensuelle_nette` existe déjà et est éditable. On ajoute la date d'effet de l'avenant et on corrige le libellé, qui dit « transport » là où il s'agit de trajet domicile-travail. Aucune migration : `specificites_paie` est une colonne JSON.

- [ ] **Step 1: Étendre le type du bloc transport**

Dans `frontend/src/features/employee-detail/types.ts`, remplacer la ligne 89 :

```ts
    transport?: {
      abonnement_mensuel_total?: number;
      indemnite_mensuelle_nette?: number;
      indemnite_date_effet?: string | null;
    };
```

- [ ] **Step 2: Mapper la date d'effet dans le formulaire**

Dans `employeeProfileFormUtils.ts`, le bloc `const transport = spec.transport as {...}` (ligne 70) devient :

```ts
  const transport = spec.transport as {
    abonnement_mensuel_total?: number;
    indemnite_mensuelle_nette?: number;
    indemnite_date_effet?: string | null;
  } | undefined;
```

Puis, dans l'objet de valeurs par défaut (ligne 129) :

```ts
      transport: {
        abonnement_mensuel_total: transport?.abonnement_mensuel_total ?? 0,
        indemnite_mensuelle_nette: transport?.indemnite_mensuelle_nette ?? 0,
        indemnite_date_effet: transport?.indemnite_date_effet ?? null,
      },
```

- [ ] **Step 3: Ajouter le champ à l'écran et corriger le libellé**

Dans `EmployeeProfileEditForm.tsx`, remplacer le `FormLabel` de la ligne 593 par `Indemnité trajet domicile-travail (€ net/mois)`, puis ajouter juste après ce `FormField` :

```tsx
            <FormField
              control={form.control}
              name="specificites_paie.transport.indemnite_date_effet"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Date d'effet de l'avenant</FormLabel>
                  <FormControl>
                    <Input
                      type="date"
                      value={field.value ?? ""}
                      onChange={(e) => field.onChange(e.target.value || null)}
                    />
                  </FormControl>
                  <FormDescription>
                    L'indemnité n'est générée qu'à partir de ce mois. Laisser vide
                    pour l'appliquer sans limite de date.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
```

Si `FormDescription` n'est pas déjà importé dans ce fichier, l'ajouter à l'import existant depuis `@/components/ui/form`.

- [ ] **Step 4: Vérifier la compilation**

Run: `cd frontend && npx tsc --noEmit`
Expected: aucune erreur sur les trois fichiers modifiés.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/employee-detail/types.ts \
        frontend/src/features/employee-detail/components/employeeProfileFormUtils.ts \
        frontend/src/features/employee-detail/components/EmployeeProfileEditForm.tsx
git commit -m "feat(paie): dater l'indemnité trajet domicile-travail sur la fiche salarié"
```

---

## Bloc 2 — La ligne mensuelle générée

### Task 2: Ciblage d'une règle par salarié

**Files:**
- Modify: `backend/app/modules/payroll_variables/domain/rules.py:49-68`
- Test: `backend/tests/unit/payroll_variables/test_payroll_variables_rules.py`

**Interfaces:**
- Consomme : rien.
- Produit : `employee_matches_conditions(employee: dict, conditions: dict | None) -> bool` accepte désormais la condition `employee_ids: list[str]`. Utilisée par la Task 4.

Aujourd'hui la fonction ne filtre que sur `statuts` / `exclude_statuts`, c'est-à-dire Cadre / Non-Cadre. C'est la raison pour laquelle zéro règle existe en production : impossible de viser deux salariés nommés avec deux montants différents.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `backend/tests/unit/payroll_variables/test_payroll_variables_rules.py` :

```python
def test_employee_ids_filter_matches():
    emp = {"id": "abc-123", "statut": "Non-Cadre"}
    assert employee_matches_conditions(emp, {"employee_ids": ["abc-123"]})


def test_employee_ids_filter_excludes():
    emp = {"id": "abc-123", "statut": "Non-Cadre"}
    assert not employee_matches_conditions(emp, {"employee_ids": ["zzz-999"]})


def test_employee_ids_empty_list_does_not_filter():
    """Une liste vide ne doit cibler personne plutôt que tout le monde."""
    emp = {"id": "abc-123"}
    assert not employee_matches_conditions(emp, {"employee_ids": []})


def test_employee_ids_combines_with_statut():
    emp = {"id": "abc-123", "statut": "Cadre"}
    conditions = {"employee_ids": ["abc-123"], "exclude_statuts": ["Cadre"]}
    assert not employee_matches_conditions(emp, conditions)
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/payroll_variables/test_payroll_variables_rules.py -q`
Expected: FAIL — `test_employee_ids_filter_excludes` et `test_employee_ids_empty_list_does_not_filter` échouent (la fonction renvoie `True` en ignorant la condition inconnue).

- [ ] **Step 3: Implémenter le filtre**

Dans `backend/app/modules/payroll_variables/domain/rules.py`, insérer dans `employee_matches_conditions`, juste après `if not conditions: return True` :

```python
    employee_ids = conditions.get("employee_ids")
    if isinstance(employee_ids, list):
        # Liste vide = règle ciblée mais sans destinataire : ne cible personne.
        cibles = {str(x) for x in employee_ids}
        if str(employee.get("id") or "") not in cibles:
            return False
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/payroll_variables -q`
Expected: PASS — 46 tests passés (42 existants + 4 nouveaux).

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/payroll_variables/domain/rules.py \
        backend/tests/unit/payroll_variables/test_payroll_variables_rules.py
git commit -m "feat(paie): cibler une règle de variables sur des salariés nommés"
```

---

### Task 3: Calcul pur du montant mensuel de transport

**Files:**
- Create: `backend/app/modules/payroll_variables/domain/transport_allowance.py`
- Create: `backend/tests/unit/payroll_variables/test_transport_allowance.py`

**Interfaces:**
- Consomme : rien.
- Produit :
  - `jours_ouvres(debut: date, fin: date) -> int`
  - `est_absent_tout_le_mois(jours_absence: set[date], debut_mois: date, fin_mois: date) -> bool`
  - `montant_transport_mensuel(montant_contractuel: float, *, debut_mois: date, fin_mois: date, date_entree: date | None = None, date_sortie: date | None = None, date_effet: date | None = None, absent_tout_le_mois: bool = False) -> float`

  Toutes utilisées par la Task 4.

La convention de prorata reprend celle de `backend/app/modules/payroll/engine/calcul_brut.py:54-88` : jours ouvrés sous contrat sur jours ouvrés du mois, un jour ouvré étant un jour de `weekday() < 5`. Ne pas inventer une autre base — le moteur en a déjà une et elle fait autorité.

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `backend/tests/unit/payroll_variables/test_transport_allowance.py` :

```python
"""Indemnité trajet domicile-travail — calcul mensuel (domaine pur)."""

from datetime import date

from app.modules.payroll_variables.domain.transport_allowance import (
    est_absent_tout_le_mois,
    jours_ouvres,
    montant_transport_mensuel,
)

JUIN_DEBUT = date(2026, 6, 1)
JUIN_FIN = date(2026, 6, 30)


def test_juin_2026_compte_22_jours_ouvres():
    assert jours_ouvres(JUIN_DEBUT, JUIN_FIN) == 22


def test_fin_avant_debut_donne_zero():
    assert jours_ouvres(JUIN_FIN, JUIN_DEBUT) == 0


def test_mois_complet_verse_le_montant_contractuel():
    montant = montant_transport_mensuel(
        250.0, debut_mois=JUIN_DEBUT, fin_mois=JUIN_FIN
    )
    assert montant == 250.0


def test_absence_totale_ne_verse_rien():
    """Règle d'Elsa : « si absent tous les mois on enlève »."""
    montant = montant_transport_mensuel(
        250.0,
        debut_mois=JUIN_DEBUT,
        fin_mois=JUIN_FIN,
        absent_tout_le_mois=True,
    )
    assert montant == 0.0


def test_entree_en_cours_de_mois_proratise():
    """Entrée le 15/06/2026 : 12 jours ouvrés sur 22."""
    montant = montant_transport_mensuel(
        250.0,
        debut_mois=JUIN_DEBUT,
        fin_mois=JUIN_FIN,
        date_entree=date(2026, 6, 15),
    )
    assert montant == 136.36


def test_sortie_en_cours_de_mois_proratise():
    """Sortie le 15/06/2026 : 11 jours ouvrés sur 22."""
    montant = montant_transport_mensuel(
        250.0,
        debut_mois=JUIN_DEBUT,
        fin_mois=JUIN_FIN,
        date_sortie=date(2026, 6, 15),
    )
    assert montant == 125.0


def test_date_effet_posterieure_au_mois_ne_verse_rien():
    montant = montant_transport_mensuel(
        250.0,
        debut_mois=JUIN_DEBUT,
        fin_mois=JUIN_FIN,
        date_effet=date(2026, 7, 1),
    )
    assert montant == 0.0


def test_date_effet_anterieure_verse_le_montant_plein():
    montant = montant_transport_mensuel(
        250.0,
        debut_mois=JUIN_DEBUT,
        fin_mois=JUIN_FIN,
        date_effet=date(2026, 1, 1),
    )
    assert montant == 250.0


def test_date_effet_en_cours_de_mois_proratise():
    montant = montant_transport_mensuel(
        250.0,
        debut_mois=JUIN_DEBUT,
        fin_mois=JUIN_FIN,
        date_effet=date(2026, 6, 15),
    )
    assert montant == 136.36


def test_montant_contractuel_nul_ne_verse_rien():
    assert montant_transport_mensuel(0.0, debut_mois=JUIN_DEBUT, fin_mois=JUIN_FIN) == 0.0


def test_sortie_avant_le_mois_ne_verse_rien():
    montant = montant_transport_mensuel(
        250.0,
        debut_mois=JUIN_DEBUT,
        fin_mois=JUIN_FIN,
        date_sortie=date(2026, 5, 20),
    )
    assert montant == 0.0


def test_absence_couvrant_tous_les_jours_ouvres():
    jours = {date(2026, 6, d) for d in range(1, 31)}
    assert est_absent_tout_le_mois(jours, JUIN_DEBUT, JUIN_FIN)


def test_absence_partielle_nest_pas_totale():
    jours = {date(2026, 6, d) for d in range(1, 16)}
    assert not est_absent_tout_le_mois(jours, JUIN_DEBUT, JUIN_FIN)


def test_absence_ignorant_les_week_ends_reste_totale():
    """Un salarié absent tous les jours ouvrés l'est totalement,
    même si les samedis et dimanches ne sont pas déclarés."""
    jours = {
        date(2026, 6, d)
        for d in range(1, 31)
        if date(2026, 6, d).weekday() < 5
    }
    assert est_absent_tout_le_mois(jours, JUIN_DEBUT, JUIN_FIN)
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/payroll_variables/test_transport_allowance.py -q`
Expected: FAIL au collect — `ModuleNotFoundError: No module named 'app.modules.payroll_variables.domain.transport_allowance'`.

- [ ] **Step 3: Implémenter le module**

Créer `backend/app/modules/payroll_variables/domain/transport_allowance.py` :

```python
"""Indemnité trajet domicile-travail — calcul mensuel (domaine pur).

Le montant est contractuel (avenant signé) et stable. Il est retiré si le
salarié est absent sur tout le mois, et proratisé à l'entrée comme à la sortie.

La base de prorata reprend celle du moteur de paie
(app/modules/payroll/engine/calcul_brut.py::_facteur_prorata_entree_sortie) :
jours ouvrés sous contrat rapportés aux jours ouvrés du mois.
"""

from __future__ import annotations

from datetime import date, timedelta


def jours_ouvres(debut: date, fin: date) -> int:
    """Nombre de jours du lundi au vendredi entre deux dates incluses."""
    if fin < debut:
        return 0
    return sum(
        1
        for offset in range((fin - debut).days + 1)
        if (debut + timedelta(days=offset)).weekday() < 5
    )


def est_absent_tout_le_mois(
    jours_absence: set[date],
    debut_mois: date,
    fin_mois: date,
) -> bool:
    """True si tous les jours ouvrés du mois sont couverts par une absence."""
    ouvres = [
        debut_mois + timedelta(days=offset)
        for offset in range((fin_mois - debut_mois).days + 1)
        if (debut_mois + timedelta(days=offset)).weekday() < 5
    ]
    if not ouvres:
        return False
    return all(jour in jours_absence for jour in ouvres)


def montant_transport_mensuel(
    montant_contractuel: float,
    *,
    debut_mois: date,
    fin_mois: date,
    date_entree: date | None = None,
    date_sortie: date | None = None,
    date_effet: date | None = None,
    absent_tout_le_mois: bool = False,
) -> float:
    """Montant à verser pour le mois, arrondi au centime.

    Renvoie 0 si le montant contractuel est nul, si le salarié est absent sur
    tout le mois, ou si le droit ne couvre aucun jour ouvré du mois.
    """
    if montant_contractuel <= 0 or absent_tout_le_mois:
        return 0.0

    debuts = [d for d in (date_entree, date_effet) if d is not None]
    debut_droit = max([debut_mois, *debuts])
    fin_droit = min(fin_mois, date_sortie) if date_sortie else fin_mois

    total_mois = jours_ouvres(debut_mois, fin_mois)
    if total_mois <= 0:
        return 0.0

    jours_droit = jours_ouvres(debut_droit, fin_droit)
    if jours_droit <= 0:
        return 0.0
    if jours_droit >= total_mois:
        return round(montant_contractuel, 2)
    return round(montant_contractuel * jours_droit / total_mois, 2)
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/payroll_variables/test_transport_allowance.py -q`
Expected: PASS — 14 tests passés.

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/payroll_variables/domain/transport_allowance.py \
        backend/tests/unit/payroll_variables/test_transport_allowance.py
git commit -m "feat(paie): calculer l'indemnité trajet domicile-travail au prorata"
```

---

### Task 4: Générer la ligne mensuelle

**Files:**
- Modify: `backend/app/modules/payroll_variables/domain/rules.py:7-17`
- Modify: `backend/app/modules/payroll_variables/schemas/requests.py:15-25`
- Modify: `backend/app/modules/payroll_variables/application/generate_monthly.py`
- Test: `backend/tests/unit/payroll_variables/test_payroll_variables_rules.py`

**Interfaces:**
- Consomme : `employee_matches_conditions` (Task 2), `montant_transport_mensuel` et `est_absent_tout_le_mois` (Task 3), `specificites_paie.transport.indemnite_date_effet` (Task 1).
- Produit : le `rule_type` `"transport_domicile_travail"`, reconnu par `compute_rule_amount` et par `generate_monthly_variables`.

Le montant ne vient pas de `rule.amount` mais de la fiche de chaque salarié : une seule règle par entreprise sert tous les bénéficiaires, chacun avec son propre montant.

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter à `backend/tests/unit/payroll_variables/test_payroll_variables_rules.py` :

```python
def test_transport_rule_type_ignore_le_montant_de_la_regle():
    """Le montant vient de la fiche salarié, pas de la règle : la règle
    n'impose rien et compute_rule_amount ne doit pas inventer de valeur."""
    assert compute_rule_amount("transport_domicile_travail", 250.0, None, 1.0) == 0.0
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/payroll_variables/test_payroll_variables_rules.py::test_transport_rule_type_ignore_le_montant_de_la_regle -q`
Expected: PASS immédiat — `compute_rule_amount` renvoie déjà `0.0` pour un type inconnu. Ce test verrouille ce comportement pour empêcher une future branche `transport_domicile_travail` d'y être ajoutée par erreur.

- [ ] **Step 3: Déclarer le nouveau type de règle**

Dans `backend/app/modules/payroll_variables/domain/rules.py`, ajouter `"transport_domicile_travail",` à la fin du `Literal` `RuleType` (après `"per_week_without_absence"`).

Dans `backend/app/modules/payroll_variables/schemas/requests.py`, ajouter la même chaîne à la fin du `Literal` de `PayrollVariableRuleSchema.rule_type`.

Ne rien ajouter à `compute_rule_amount` : le montant est calculé par salarié dans le générateur.

- [ ] **Step 4: Ajouter la branche de génération**

Dans `backend/app/modules/payroll_variables/application/generate_monthly.py`, ajouter en tête de fichier, aux imports existants :

```python
from app.modules.payroll_variables.domain.transport_allowance import (
    est_absent_tout_le_mois,
    montant_transport_mensuel,
)
```

Puis ajouter ces deux helpers au niveau module, à côté de `_load_calendrier_reel` :

```python
def _parse_date_iso(valeur: Any) -> date | None:
    """Parse une date ISO issue de la base ; None si absente ou invalide."""
    if not valeur:
        return None
    if isinstance(valeur, date):
        return valeur
    try:
        return date.fromisoformat(str(valeur)[:10])
    except ValueError:
        return None


def _jours_absence(rows: list[dict[str, Any]], start: date, end: date) -> set[date]:
    """Jours couverts par les absences validées, bornés au mois."""
    jours: set[date] = set()
    for row in rows:
        debut = _parse_date_iso(row.get("date_debut") or row.get("start_date"))
        fin = _parse_date_iso(row.get("date_fin") or row.get("end_date")) or debut
        if not debut or not fin:
            continue
        curseur = max(debut, start)
        borne = min(fin, end)
        while curseur <= borne:
            jours.add(curseur)
            curseur += timedelta(days=1)
    return jours
```

Vérifier que `date` et `timedelta` sont importés depuis `datetime` en tête de fichier ; les ajouter sinon.

Enfin, dans la boucle `for emp in employees:` de `generate_monthly_variables`, juste après `eid = str(emp["id"])`, insérer la branche :

```python
            if rule_type == "transport_domicile_travail":
                spec = emp.get("specificites_paie") or {}
                transport = (spec.get("transport") or {}) if isinstance(spec, dict) else {}
                try:
                    contractuel = float(transport.get("indemnite_mensuelle_nette") or 0)
                except (TypeError, ValueError):
                    contractuel = 0.0
                if contractuel <= 0:
                    continue
                amount = montant_transport_mensuel(
                    contractuel,
                    debut_mois=start,
                    fin_mois=end,
                    date_entree=_parse_date_iso(emp.get("date_entree")),
                    date_sortie=_parse_date_iso(emp.get("date_sortie")),
                    date_effet=_parse_date_iso(transport.get("indemnite_date_effet")),
                    absent_tout_le_mois=est_absent_tout_le_mois(
                        _jours_absence(absences_by_employee.get(eid, []), start, end),
                        start,
                        end,
                    ),
                )
                written = _append_generated_input(
                    preview=preview,
                    written=written,
                    dry_run=dry_run,
                    rule=rule,
                    emp=emp,
                    eid=eid,
                    year=year,
                    month=month,
                    amount=amount,
                    quantity=1.0,
                    name_suffix="",
                )
                continue
```

Élargir enfin le `select` de `generate_monthly_variables` pour rapatrier les dates de contrat, en remplaçant la chaîne de sélection existante par :

```python
            "id, first_name, last_name, statut, specificites_paie, "
            "salaire_de_base, duree_hebdomadaire, date_entree, date_sortie"
```

- [ ] **Step 5: Vérifier que la suite reste verte**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/payroll_variables -q`
Expected: PASS — 47 tests passés.

- [ ] **Step 6: Vérifier que la colonne `date_sortie` existe**

Run:
```bash
cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib PYTHONPATH=. .venv-ci/bin/python -c "
from app.core.database import supabase
r = supabase.table('employees').select('id,date_entree,date_sortie').limit(1).execute()
print(r.data)
"
```
Expected: une ligne s'affiche sans erreur. Si l'API renvoie `column employees.date_sortie does not exist`, remplacer par le nom réel indiqué dans le `hint` de l'erreur, dans le `select` **et** dans la branche de génération.

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/payroll_variables/domain/rules.py \
        backend/app/modules/payroll_variables/schemas/requests.py \
        backend/app/modules/payroll_variables/application/generate_monthly.py \
        backend/tests/unit/payroll_variables/test_payroll_variables_rules.py
git commit -m "feat(paie): générer la ligne mensuelle d'indemnité trajet domicile-travail"
```

---

### Task 5: Préserver les ajustements manuels

**Files:**
- Create: `supabase/migrations/20260803090000_monthly_inputs_quantity_kind.sql`
- Modify: `backend/app/modules/payroll_variables/infrastructure/repository.py:71-83`
- Modify: `backend/app/modules/monthly_inputs/schemas/requests.py`
- Modify: `backend/app/modules/monthly_inputs/application/commands.py`
- Modify: `backend/app/modules/monthly_inputs/api/router.py:47`

**Interfaces:**
- Consomme : `upsert_monthly_input(row: dict) -> None` (existant).
- Produit : colonnes `monthly_inputs.manual_override` (booléen, défaut `false`) et `monthly_inputs.quantity_kind` (texte, nullable) ; endpoint `PATCH /api/monthly-inputs/{input_id}` ; commande `update_monthly_input(input_id: str, payload: MonthlyInputUpdate) -> dict`.

Deux problèmes à régler ensemble. D'une part `upsert_monthly_input` écrase sans condition la ligne existante : relancer « Préparer variables du mois » effacerait une correction d'Elsa. D'autre part il n'existe **aucun** endpoint de modification — seulement création et suppression — donc « modifier la ligne » est aujourd'hui impossible.

La colonne `quantity_kind` est créée ici pour n'avoir qu'une seule migration sur cette table ; elle n'est exploitée qu'à la Task 8.

- [ ] **Step 1: Écrire la migration**

Créer `supabase/migrations/20260803090000_monthly_inputs_quantity_kind.sql` :

```sql
-- Saisies mensuelles : distinguer une ligne ajustée à la main d'une ligne
-- générée, et lever l'ambiguïté de payroll_quantity (nombre vs valeur unitaire).
alter table public.monthly_inputs
  add column if not exists manual_override boolean not null default false,
  add column if not exists quantity_kind text;

comment on column public.monthly_inputs.manual_override is
  'True si la ligne a été créée ou corrigée à la main : la génération mensuelle ne doit plus l''écraser.';

comment on column public.monthly_inputs.quantity_kind is
  'Sémantique de payroll_quantity : ''count'' = nombre d''unités, ''unit_value'' = valeur unitaire en euros. NULL = indéterminé.';

alter table public.monthly_inputs
  drop constraint if exists monthly_inputs_quantity_kind_check;

alter table public.monthly_inputs
  add constraint monthly_inputs_quantity_kind_check
  check (quantity_kind is null or quantity_kind in ('count', 'unit_value'));
```

Avant de créer le fichier, vérifier qu'aucune migration ne porte déjà cet horodatage :

Run: `ls supabase/migrations/ | grep 20260803`
Expected: aucune sortie. Si un fichier existe, incrémenter l'horodatage d'une minute.

- [ ] **Step 2: Faire respecter `manual_override` par la génération**

Dans `backend/app/modules/payroll_variables/infrastructure/repository.py`, remplacer le corps de `upsert_monthly_input` :

```python
def upsert_monthly_input(row: dict[str, Any]) -> None:
    existing = find_existing_monthly_input(
        str(row["employee_id"]),
        int(row["year"]),
        int(row["month"]),
        str(row["name"]),
    )
    if existing:
        # Une ligne corrigée à la main fait autorité sur la génération :
        # Elsa a tranché pour ce mois, on ne repasse pas derrière elle.
        if existing.get("manual_override"):
            return
        supabase.table("monthly_inputs").update(row).eq(
            "id", existing["id"]
        ).execute()
    else:
        supabase.table("monthly_inputs").insert(row).execute()
```

- [ ] **Step 3: Ajouter le schéma de mise à jour**

Dans `backend/app/modules/monthly_inputs/schemas/requests.py`, ajouter après `MonthlyInputCreate` :

```python
class MonthlyInputUpdate(BaseModel):
    """Correction manuelle d'une saisie (PATCH). Champs omis = inchangés."""

    amount: Optional[float] = None
    name: Optional[str] = None
    description: Optional[str] = None
    is_socially_taxed: Optional[bool] = None
    is_taxable: Optional[bool] = None
    payroll_quantity: Optional[float] = None
```

- [ ] **Step 4: Ajouter la commande**

Dans `backend/app/modules/monthly_inputs/application/commands.py`, ajouter :

```python
def update_monthly_input(input_id: str, payload: "MonthlyInputUpdate") -> dict:
    """Applique une correction manuelle et marque la ligne comme telle."""
    from app.core.database import supabase

    changes = payload.model_dump(exclude_none=True)
    if not changes:
        raise ValueError("Aucun champ à mettre à jour.")
    changes["manual_override"] = True
    resp = (
        supabase.table("monthly_inputs")
        .update(changes)
        .eq("id", input_id)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        raise ValueError(f"Saisie {input_id} introuvable.")
    return rows[0]
```

Adapter l'import de `supabase` au style déjà présent en tête de `commands.py` si celui-ci l'importe déjà au niveau module.

- [ ] **Step 5: Exposer l'endpoint**

Dans `backend/app/modules/monthly_inputs/api/router.py`, ajouter `MonthlyInputUpdate` à l'import depuis `schemas.requests`, puis insérer juste avant `@router.delete("/api/monthly-inputs/{input_id}")` :

```python
@router.patch("/api/monthly-inputs/{input_id}")
def update_monthly_input(input_id: str, payload: MonthlyInputUpdate):
    """Corrige une saisie mensuelle. La ligne devient prioritaire sur la génération."""
    try:
        return commands.update_monthly_input(input_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("update_monthly_input")
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 6: Vérifier que l'application démarre et que la route est enregistrée**

Run:
```bash
cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib PYTHONPATH=. .venv-ci/bin/python -c "
from app.main import app
routes = [(r.path, sorted(r.methods)) for r in app.routes if 'monthly-inputs' in getattr(r, 'path', '')]
for p, m in sorted(routes): print(m, p)
"
```
Expected: la liste contient `['PATCH'] /api/monthly-inputs/{input_id}`.

- [ ] **Step 7: Vérifier la non-régression**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit -q`
Expected: PASS, sans échec nouveau par rapport à la référence relevée avant de commencer.

- [ ] **Step 8: Commit**

```bash
git add supabase/migrations/20260803090000_monthly_inputs_quantity_kind.sql \
        backend/app/modules/payroll_variables/infrastructure/repository.py \
        backend/app/modules/monthly_inputs/schemas/requests.py \
        backend/app/modules/monthly_inputs/application/commands.py \
        backend/app/modules/monthly_inputs/api/router.py
git commit -m "feat(paie): rendre les saisies mensuelles corrigeables sans être écrasées"
```

---

### Task 6: Retirer l'ajout silencieux du moteur

**Files:**
- Modify: `backend/app/modules/payroll/engine/calcul_net.py:460-469`
- Test: `backend/tests/unit/payroll/` (fichier existant couvrant `calcul_net`, à identifier au Step 1)

**Interfaces:**
- Consomme : rien.
- Produit : `_calculer_net_a_payer` continue de renvoyer un triplet `(net, remboursement_transport, indemnite_transport_fixe)`, mais `indemnite_transport_fixe` vaut désormais toujours `0.0`. La clé `indemnite_transport_fixe` du bulletin est conservée pour ne pas casser `bulletin.py:357` ni les gabarits PDF.

Sans ce retrait, la prime serait comptée deux fois : une fois par la ligne générée à la Task 4, une fois par le moteur. Le retrait est sans risque : aucun salarié n'a `indemnite_mensuelle_nette` renseigné aujourd'hui.

- [ ] **Step 1: Localiser la couverture existante**

Run: `cd backend && grep -rln "indemnite_transport_fixe\|_calculer_net_a_payer" tests/`
Expected: la liste des fichiers de test concernés. S'il n'y en a aucun, créer `backend/tests/unit/payroll/test_calcul_net_transport.py`.

- [ ] **Step 2: Écrire le test qui échoue**

Dans le fichier identifié (ou créé) :

```python
from types import SimpleNamespace

from app.modules.payroll.engine.calcul_net import _calculer_net_a_payer


def _contexte_transport(indemnite: float, abonnement: float = 0.0):
    """Double minimal de ContextePaie : seul `contrat` est lu par la fonction."""
    return SimpleNamespace(
        contrat={
            "specificites_paie": {
                "transport": {
                    "indemnite_mensuelle_nette": indemnite,
                    "abonnement_mensuel_total": abonnement,
                }
            }
        }
    )


def test_indemnite_transport_contractuelle_nest_plus_ajoutee_au_net():
    """L'indemnité trajet domicile-travail passe désormais par une saisie
    mensuelle générée (payroll_variables), plus par le moteur : la conserver
    ici la compterait deux fois."""
    net, remboursement, indemnite = _calculer_net_a_payer(
        net_social=2000.0,
        montant_pas=0.0,
        contexte=_contexte_transport(250.0),
        primes_non_soumises=[],
    )
    assert indemnite == 0.0
    assert net == 2000.0


def test_remboursement_abonnement_public_reste_intact():
    """L'obligation légale des 50 % d'abonnement n'est pas concernée."""
    net, remboursement, indemnite = _calculer_net_a_payer(
        net_social=2000.0,
        montant_pas=0.0,
        contexte=_contexte_transport(0.0, abonnement=36.0),
        primes_non_soumises=[],
    )
    assert remboursement == 18.0
    assert net == 2018.0
```

Signature réelle, à respecter exactement : `_calculer_net_a_payer(net_social, montant_pas, contexte, primes_non_soumises, montant_acompte=0.0, primes_soumises_impot=None, participations=None) -> tuple[float, float, float]` (`calcul_net.py:413-421`).

- [ ] **Step 3: Lancer le test pour vérifier qu'il échoue**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/payroll -k transport -q`
Expected: FAIL — `assert 250.0 == 0.0`.

- [ ] **Step 4: Retirer l'ajout**

Dans `backend/app/modules/payroll/engine/calcul_net.py`, remplacer le bloc des lignes 460 à 469 par :

```python
    # L'indemnité trajet domicile-travail est désormais produite comme saisie
    # mensuelle par payroll_variables (règle transport_domicile_travail), afin
    # d'être visible et corrigeable dans Saisies > Primes, proratisée à
    # l'entrée/sortie et retirée en cas d'absence sur tout le mois.
    # La conserver ici la compterait deux fois. La variable reste renvoyée à 0
    # pour ne pas modifier le contrat de retour ni le gabarit du bulletin.
    indemnite_transport_fixe = 0.0
```

- [ ] **Step 5: Lancer les tests pour vérifier qu'ils passent**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/payroll -q`
Expected: PASS, sans échec nouveau.

- [ ] **Step 6: Vérifier qu'aucun euro n'a bougé**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib PYTHONPATH=. .venv-ci/bin/python scripts/backtest/colorplast_verify_all.py`
Expected: 7/7 convergés, identique à la référence avant modification. Le champ retiré n'étant renseigné pour aucun salarié, tout écart signale une erreur d'implémentation.

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/payroll/engine/calcul_net.py backend/tests/unit/payroll/
git commit -m "refactor(paie): sortir l'indemnité transport du moteur vers les saisies"
```

---

### Task 7: Éditer une ligne depuis l'écran Primes

**Files:**
- Modify: `frontend/src/api/saisies.ts:50`
- Modify: `frontend/src/components/saisies/PrimesTab.tsx:16-33,96-105,230-235`

**Interfaces:**
- Consomme : `PATCH /api/monthly-inputs/{id}` (Task 5).
- Produit : `updateMonthlyInput(id: string, data: Partial<MonthlyInput>)`.

Aujourd'hui la table n'offre que la suppression. Elsa doit pouvoir corriger un montant sans supprimer puis recréer.

- [ ] **Step 1: Ajouter l'appel API**

Dans `frontend/src/api/saisies.ts`, ajouter après `deleteMonthlyInput` :

```ts
export const updateMonthlyInput = (
  id: string,
  data: Partial<Pick<MonthlyInput, 'amount' | 'name' | 'description' | 'is_socially_taxed' | 'is_taxable'>>,
) => {
  return apiClient.patch<MonthlyInput>(`/api/monthly-inputs/${id}`, data);
};
```

- [ ] **Step 2: Ajouter l'édition du montant dans la table**

Dans `PrimesTab.tsx`, ajouter l'état et le gestionnaire au corps du composant, après `handleDelete` :

```tsx
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingAmount, setEditingAmount] = useState<string>("");

  const handleSaveAmount = async (id: string) => {
    const parsed = Number(editingAmount.replace(",", "."));
    if (Number.isNaN(parsed)) {
      toast({ title: "Montant invalide", variant: "destructive" });
      return;
    }
    try {
      await saisiesApi.updateMonthlyInput(id, { amount: parsed });
      toast({ title: "Saisie corrigée", description: "Elle ne sera plus écrasée par la génération du mois." });
      setEditingId(null);
      fetchData();
    } catch (error) {
      log.error(error);
      toast({ title: "Erreur", description: "Impossible de corriger la saisie.", variant: "destructive" });
    }
  };
```

Remplacer la `TableCell` du montant (ligne 219) par :

```tsx
                        <TableCell>
                          {editingId === input.id ? (
                            <div className="flex items-center gap-2">
                              <Input
                                className="h-8 w-28"
                                value={editingAmount}
                                autoFocus
                                onChange={(e) => setEditingAmount(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") handleSaveAmount(input.id);
                                  if (e.key === "Escape") setEditingId(null);
                                }}
                              />
                              <Button size="sm" onClick={() => handleSaveAmount(input.id)}>OK</Button>
                            </div>
                          ) : (
                            <button
                              type="button"
                              className="underline decoration-dotted underline-offset-4"
                              onClick={() => {
                                setEditingId(input.id);
                                setEditingAmount(String(input.amount));
                              }}
                            >
                              {new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(input.amount)}
                            </button>
                          )}
                        </TableCell>
```

Ajouter `import { Input } from "@/components/ui/input";` aux imports du fichier.

- [ ] **Step 3: Vérifier la compilation**

Run: `cd frontend && npx tsc --noEmit`
Expected: aucune erreur.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/saisies.ts frontend/src/components/saisies/PrimesTab.tsx
git commit -m "feat(saisies): corriger le montant d'une prime directement dans la table"
```

---

## Bloc 3 — Assainir la sémantique des quantités

### Task 8: Résolution explicite de la valeur unitaire

**Files:**
- Modify: `backend/app/modules/payroll/engine/calcul_frais.py`
- Test: `backend/tests/unit/payroll/test_frais_pro_sections.py` (créé ici)

**Interfaces:**
- Consomme : colonne `quantity_kind` (Task 5).
- Produit : `valeur_unitaire(montant: float, quantity: float | None, quantity_kind: str | None) -> float`.

`payroll_quantity` porte deux sémantiques opposées selon le libellé : 62 lignes Mont Blanc Composite y stockent la **valeur unitaire** (7,5), 52 autres lignes y stockent le **nombre** d'unités. Le moteur divise sans distinction, ce qui produit 22 € le panier au lieu de 7,50 €. C'est le prérequis de la Task 10 : réparer le plafond avant cette correction réintégrerait à tort sur 62 lignes.

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `backend/tests/unit/payroll/test_frais_pro_sections.py` :

```python
"""Sémantique des quantités de saisie et forme du barème frais professionnels."""

from app.modules.payroll.engine.calcul_frais import valeur_unitaire


def test_quantite_en_nombre_divise_le_montant():
    """« Paniers jours non soumis » : 207,20 € pour 28 paniers -> 7,40 €."""
    assert valeur_unitaire(207.20, 28.0, "count") == 7.4


def test_quantite_en_valeur_unitaire_est_retournee_telle_quelle():
    """« Paniers Jours non soumis » (MBC) : quantity porte déjà 7,50 €."""
    assert valeur_unitaire(165.0, 7.5, "unit_value") == 7.5


def test_sans_kind_on_divise_comme_avant():
    """Rétrocompatibilité : le comportement historique est conservé."""
    assert valeur_unitaire(195.0, 13.0, None) == 15.0


def test_quantite_absente_renvoie_le_montant():
    assert valeur_unitaire(100.0, None, None) == 100.0


def test_quantite_nulle_renvoie_le_montant():
    assert valeur_unitaire(100.0, 0.0, "count") == 100.0
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/payroll/test_frais_pro_sections.py -q`
Expected: FAIL au collect — `ImportError: cannot import name 'valeur_unitaire'`.

- [ ] **Step 3: Implémenter la résolution**

Ajouter à `backend/app/modules/payroll/engine/calcul_frais.py`, après `reintegration_exces` :

```python
def valeur_unitaire(
    montant: float,
    quantity: Optional[float],
    quantity_kind: Optional[str],
) -> float:
    """Valeur unitaire d'une saisie, quelle que soit la sémantique de sa quantité.

    `payroll_quantity` a porté deux conventions inverses selon le libellé :
      - 'count'      : nombre d'unités  -> valeur unitaire = montant / quantité
      - 'unit_value' : valeur unitaire  -> la quantité EST la valeur unitaire
      - None         : indéterminé      -> division, comportement historique
    """
    try:
        qte = float(quantity) if quantity is not None else 0.0
    except (TypeError, ValueError):
        qte = 0.0
    if qte <= 0:
        return float(montant)
    if quantity_kind == "unit_value":
        return round(qte, 2)
    return round(float(montant) / qte, 2)
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/payroll/test_frais_pro_sections.py -q`
Expected: PASS — 5 tests passés.

- [ ] **Step 5: Faire remonter `quantity_kind` jusqu'au moteur**

Sans cette étape, `valeur_unitaire` serait du code mort — exactement le défaut qu'on répare au bloc 4.

Dans `backend/app/modules/payroll/documents/payslip_generator.py`, après la ligne 657 (`prime_entry["quantity"] = float(row["payroll_quantity"])`), ajouter :

```python
            if row.get("quantity_kind"):
                prime_entry["quantity_kind"] = row["quantity_kind"]
```

Appliquer le même ajout dans `backend/app/modules/payroll/documents/payslip_generator_forfait.py`, après la ligne 273.

- [ ] **Step 6: Utiliser la sémantique dans la branche panier**

Dans `backend/app/modules/payroll/documents/payslip_run_heures.py`, remplacer les deux lignes qui calculent `qty` et `unit` (lignes 408-409) par :

```python
                qty_brute = saisie.get("quantity")
                unit = valeur_unitaire(montant, qty_brute, saisie.get("quantity_kind"))
                # Nombre d'unités : déduit du montant quand la quantité porte
                # la valeur unitaire (convention Mont Blanc Composite).
                qty = max(1.0, round(montant / unit)) if unit > 0 else 1.0
```

Ajouter `valeur_unitaire` à l'import existant depuis `app.modules.payroll.engine.calcul_frais` en tête de ce fichier.

- [ ] **Step 7: Vérifier que la valeur unitaire est désormais juste**

Run:
```bash
cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -c "
from app.modules.payroll.engine.calcul_frais import valeur_unitaire
# Ligne MBC réelle : 165 € avec quantity=7.5 portant la valeur unitaire.
u = valeur_unitaire(165.0, 7.5, 'unit_value')
print('unitaire =', u, '| nombre =', round(165.0 / u))
"
```
Expected: `unitaire = 7.5 | nombre = 22`. Avant correction, le moteur lisait 22 € l'unité pour 7 unités.

- [ ] **Step 8: Vérifier qu'aucun euro n'a bougé**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit -q`
Expected: PASS, sans échec nouveau. Le plafond étant encore inactif à ce stade (Task 10 non faite), `exoneration_repas` renvoie toujours `None` et aucune réintégration ne peut se produire : le changement est neutre par construction.

- [ ] **Step 9: Commit**

```bash
git add backend/app/modules/payroll/engine/calcul_frais.py \
        backend/tests/unit/payroll/test_frais_pro_sections.py \
        backend/app/modules/payroll/documents/payslip_generator.py \
        backend/app/modules/payroll/documents/payslip_generator_forfait.py \
        backend/app/modules/payroll/documents/payslip_run_heures.py
git commit -m "feat(paie): lever l'ambiguïté de la quantité des saisies de frais"
```

---

### Task 9: Reprise des lignes à sémantique inversée

**Files:**
- Create: `backend/scripts/normalize_panier_quantities.py`

**Interfaces:**
- Consomme : colonne `quantity_kind` (Task 5).
- Produit : un script idempotent, `--dry-run` par défaut, qui renseigne `quantity_kind` sur les saisies existantes.

La convention est déduite du libellé, seule information disponible. Le script ne modifie **aucun montant** : il annote seulement la sémantique. C'est vérifiable, et c'est ce qui garantit que la reprise ne déplace aucun euro.

- [ ] **Step 1: Écrire le script**

Créer `backend/scripts/normalize_panier_quantities.py` :

```python
"""Annote la sémantique de payroll_quantity sur les saisies existantes.

payroll_quantity a porté deux conventions inverses selon le libellé :
  - « Paniers Jours non soumis » (J majuscule, Mont Blanc Composite) stocke la
    VALEUR unitaire (7,5) ;
  - tous les autres libellés panier/repas stockent le NOMBRE d'unités.

Ce script ne touche à aucun montant : il renseigne uniquement quantity_kind.

Usage :
    python scripts/normalize_panier_quantities.py            # simulation
    python scripts/normalize_panier_quantities.py --apply    # écriture
"""

from __future__ import annotations

import argparse
import sys

from app.core.database import supabase

# Libellés dont payroll_quantity porte la valeur unitaire et non un nombre.
LIBELLES_VALEUR_UNITAIRE = {"Paniers Jours non soumis"}


def classer(name: str) -> str | None:
    """Renvoie 'unit_value', 'count', ou None si la ligne n'est pas concernée."""
    if name in LIBELLES_VALEUR_UNITAIRE:
        return "unit_value"
    low = (name or "").lower()
    if "panier" in low or "repas" in low:
        return "count"
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="écrit en base")
    args = parser.parse_args()

    rows = supabase.table("monthly_inputs").select(
        "id, name, payroll_quantity, amount, quantity_kind"
    ).execute().data or []

    a_traiter = []
    for row in rows:
        attendu = classer(row.get("name") or "")
        if attendu is None:
            continue
        if row.get("quantity_kind") == attendu:
            continue
        a_traiter.append((row, attendu))

    print(f"{len(rows)} saisies lues, {len(a_traiter)} à annoter.")
    par_kind: dict[str, int] = {}
    for row, attendu in a_traiter:
        par_kind[attendu] = par_kind.get(attendu, 0) + 1
    for kind, n in sorted(par_kind.items()):
        print(f"  {kind}: {n}")

    if not args.apply:
        print("\nSimulation — relancer avec --apply pour écrire.")
        for row, attendu in a_traiter[:10]:
            print(f'  "{row["name"]}" qty={row.get("payroll_quantity")} -> {attendu}')
        return 0

    for row, attendu in a_traiter:
        supabase.table("monthly_inputs").update(
            {"quantity_kind": attendu}
        ).eq("id", row["id"]).execute()
    print(f"{len(a_traiter)} saisies annotées.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Simuler sur l'environnement de test**

Vérifier d'abord que l'environnement de test est resynchronisé (ses données dataient du 29 juillet), puis, avec les variables d'environnement pointant sur le test :

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib PYTHONPATH=. .venv-ci/bin/python scripts/normalize_panier_quantities.py`
Expected: `114 à annoter`, réparties en `count: 52` et `unit_value: 62`.

- [ ] **Step 3: Appliquer sur le test et vérifier qu'aucun euro n'a bougé**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib PYTHONPATH=. .venv-ci/bin/python scripts/normalize_panier_quantities.py --apply`
Expected: `114 saisies annotées.`

Puis relancer le script sans `--apply` : Expected: `0 à annoter` (idempotence).

- [ ] **Step 4: Vérifier la non-régression des bulletins**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib PYTHONPATH=. .venv-ci/bin/python scripts/backtest/colorplast_verify_all.py`
Expected: 7/7, inchangé. Le script n'écrit que `quantity_kind`, aucun montant ne doit varier.

- [ ] **Step 5: Normaliser les libellés divergents**

**À faire impérativement après le Step 3.** Le libellé est la seule information
qui permet de deviner la sémantique : normaliser avant d'annoter détruirait le
signal et rendrait la reprise impossible.

Ajouter au script, avant `main()` :

```python
# Libellés divergents constatés en base, fusionnés vers une forme unique.
# Appliqué APRÈS l'annotation de quantity_kind : le libellé est le seul
# discriminant de la sémantique, le normaliser d'abord la détruirait.
RENOMMAGES = {
    "Indemnite de transport": "Indemnité de transport",
    "Paniers Jours non soumis": "Paniers jours non soumis",
}


def normaliser_libelles(apply: bool) -> int:
    rows = supabase.table("monthly_inputs").select("id, name, quantity_kind").execute().data or []
    cibles = [r for r in rows if r.get("name") in RENOMMAGES]
    non_annotees = [r for r in cibles if not r.get("quantity_kind")]
    if non_annotees:
        print(
            f"ABANDON : {len(non_annotees)} ligne(s) à renommer n'ont pas encore "
            "de quantity_kind. Annoter d'abord (voir plus haut)."
        )
        return -1
    print(f"{len(cibles)} libellé(s) à normaliser.")
    if not apply:
        return 0
    for row in cibles:
        supabase.table("monthly_inputs").update(
            {"name": RENOMMAGES[row["name"]]}
        ).eq("id", row["id"]).execute()
    print(f"{len(cibles)} libellé(s) normalisé(s).")
    return 0
```

Puis, dans `main()`, juste avant `return 0` de la branche `--apply` :

```python
    code = normaliser_libelles(args.apply)
    if code < 0:
        return 1
```

et, dans la branche simulation, remplacer `return 0` par :

```python
    normaliser_libelles(False)
    return 0
```

- [ ] **Step 6: Vérifier le garde-fou d'ordre**

Sur une base où `quantity_kind` n'est pas encore posé, le script doit refuser de
renommer.

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib PYTHONPATH=. .venv-ci/bin/python scripts/normalize_panier_quantities.py`
Expected: après annotation complète, `72 libellé(s) à normaliser.` (62 `Paniers Jours non soumis` + 10 `Indemnite de transport`). Si l'annotation n'a pas été faite, le message `ABANDON` doit apparaître.

Attention : `Indemnite de transport` n'est pas un libellé panier, donc le Step 3
ne lui pose aucun `quantity_kind`. Le garde-fou ne doit s'appliquer qu'aux
libellés panier. Restreindre le contrôle en conséquence :

```python
    non_annotees = [
        r for r in cibles
        if not r.get("quantity_kind") and "panier" in (r.get("name") or "").lower()
    ]
```

- [ ] **Step 7: Commit**

```bash
git add backend/scripts/normalize_panier_quantities.py
git commit -m "chore(paie): annoter la sémantique des quantités et normaliser les libellés"
```

- [ ] **Step 8: Demander l'accord avant la production**

L'exécution `--apply` en production est une opération sur données réelles. Ne pas la lancer sans accord explicite d'Alexandre, conformément à la règle sur les actions globales.

---

## Bloc 4 — Les plafonds

### Task 10: Réparer la lecture du barème de frais professionnels

**Files:**
- Modify: `backend/app/modules/payroll/engine/calcul_frais.py:10-36`
- Test: `backend/tests/unit/payroll/test_frais_pro_sections.py`

**Interfaces:**
- Consomme : rien.
- Produit : `sections_frais_pro(frais_pro: dict | None) -> dict` ; `exoneration_repas(frais_pro, type_repas="repas", *, situation: str | None = None) -> float | None`.

`exoneration_repas` lit `frais_pro["sections"]`. Aucune version stockée de `payroll_config` n'a jamais eu cette clé au premier niveau : v1 mettait les sections à la racine, v2 à v4 les rangent sous `config_data["FRAIS_PRO"][0]["sections"]`. La fonction renvoie donc toujours `None`, aucun plafond n'est appliqué, et la branche « Réintégration NDF » de `payslip_run_heures.py:392-403` est du code mort.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `backend/tests/unit/payroll/test_frais_pro_sections.py` :

```python
from app.modules.payroll.engine.calcul_frais import (
    exoneration_repas,
    sections_frais_pro,
)

BAREME_REPAS = {
    "sur_lieu_travail": 7.5,
    "hors_locaux_avec_restaurant": 21.4,
    "hors_locaux_sans_restaurant": 10.4,
}

# Forme réellement stockée dans payroll_config (versions 2 à 4).
FORME_STOCKEE = {"FRAIS_PRO": [{"id": 1, "libelle": "Frais pro", "sections": {"repas": BAREME_REPAS}}]}
# Forme de la version 1 : sections à la racine.
FORME_V1 = {"repas": BAREME_REPAS}
# Forme attendue par le code d'origine, jamais rencontrée en base.
FORME_HISTORIQUE = {"sections": {"repas": BAREME_REPAS}}


def test_sections_lues_depuis_la_forme_reellement_stockee():
    assert sections_frais_pro(FORME_STOCKEE) == {"repas": BAREME_REPAS}


def test_sections_lues_depuis_la_forme_v1():
    assert sections_frais_pro(FORME_V1) == FORME_V1


def test_sections_lues_depuis_la_forme_historique():
    assert sections_frais_pro(FORME_HISTORIQUE) == {"repas": BAREME_REPAS}


def test_sections_absentes_donnent_un_dict_vide():
    assert sections_frais_pro(None) == {}
    assert sections_frais_pro({"autre": 1}) == {}


def test_plafond_repas_par_defaut_reste_le_plus_eleve():
    """Repli délibéré : durcir sans connaître la situation réintégrerait à tort
    les paniers chauffeur à 15 €, qui sont des repas hors locaux légitimes."""
    assert exoneration_repas(FORME_STOCKEE) == 21.4


def test_plafond_repas_selon_la_situation_declaree():
    assert exoneration_repas(FORME_STOCKEE, situation="sur_lieu_travail") == 7.5
    assert exoneration_repas(FORME_STOCKEE, situation="hors_locaux_sans_restaurant") == 10.4
    assert exoneration_repas(FORME_STOCKEE, situation="hors_locaux_avec_restaurant") == 21.4


def test_situation_inconnue_retombe_sur_le_repli():
    assert exoneration_repas(FORME_STOCKEE, situation="inexistante") == 21.4
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/payroll/test_frais_pro_sections.py -q`
Expected: FAIL au collect — `ImportError: cannot import name 'sections_frais_pro'`.

- [ ] **Step 3: Implémenter la lecture tolérante**

Dans `backend/app/modules/payroll/engine/calcul_frais.py`, remplacer intégralement `exoneration_repas` (lignes 10 à 36) par :

```python
def sections_frais_pro(frais_pro: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Sections du barème frais pro, quelle que soit la forme stockée.

    Trois formes ont coexisté dans payroll_config.config_data :
      - v1        : sections à la racine        -> {"repas": {...}, ...}
      - v2 à v4   : {"FRAIS_PRO": [{"sections": {...}}]}  (forme active)
      - historique: {"sections": {...}}         -- jamais rencontrée en base,
        mais seule forme que lisait le code d'origine, d'où l'absence totale
        de plafond appliqué jusqu'ici.
    """
    if not isinstance(frais_pro, dict):
        return {}
    sections = frais_pro.get("sections")
    if isinstance(sections, dict):
        return sections
    bloc = frais_pro.get("FRAIS_PRO")
    if isinstance(bloc, list) and bloc and isinstance(bloc[0], dict):
        imbriquees = bloc[0].get("sections")
        if isinstance(imbriquees, dict):
            return imbriquees
    if isinstance(bloc, dict) and isinstance(bloc.get("sections"), dict):
        return bloc["sections"]
    if isinstance(frais_pro.get("repas"), dict):
        return frais_pro
    return {}


def exoneration_repas(
    frais_pro: Optional[Dict[str, Any]],
    type_repas: str = "repas",
    *,
    situation: Optional[str] = None,
) -> Optional[float]:
    """Plafond d'exonération repas (€), None si le barème est absent.

    `situation` sélectionne le plafond applicable : sur_lieu_travail,
    hors_locaux_sans_restaurant, hors_locaux_avec_restaurant. Tant qu'elle
    n'est pas déclarée, on retient le plafond le plus élevé : durcir sans
    l'information réintégrerait à tort des repas hors locaux légitimes.
    """
    sections = sections_frais_pro(frais_pro)
    repas = sections.get(type_repas) or sections.get("repas") or {}
    if not isinstance(repas, dict):
        return None
    if situation:
        val = repas.get(situation)
        if isinstance(val, (int, float)) and val > 0:
            return float(val)
    for key in (
        "repas",
        "montant",
        "forfait",
        "valeur",
        "indemnite_repas",
        "repas_valeur",
    ):
        val = repas.get(key)
        if isinstance(val, (int, float)) and val > 0:
            return float(val)
    vals = [float(v) for v in repas.values() if isinstance(v, (int, float)) and v > 0]
    return max(vals) if vals else None
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/payroll/test_frais_pro_sections.py -q`
Expected: PASS — 12 tests passés.

- [ ] **Step 5: Vérifier le plafond réellement obtenu sur la configuration active**

Run:
```bash
cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib PYTHONPATH=. .venv-ci/bin/python -c "
from app.core.database import supabase
from app.modules.payroll.engine.baremes_loader import charger_db_baremes, assembler_baremes
from app.modules.payroll.engine.calcul_frais import exoneration_repas
b = assembler_baremes(charger_db_baremes(supabase))
print('plafond par défaut :', exoneration_repas(b['frais_pro']))
print('sur lieu de travail :', exoneration_repas(b['frais_pro'], situation='sur_lieu_travail'))
"
```
Expected: `plafond par défaut : 21.4` puis `sur lieu de travail : 7.5`. Avant ce correctif, les deux lignes affichaient `None`.

- [ ] **Step 6: Vérifier qu'aucun euro n'a bougé**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib PYTHONPATH=. .venv-ci/bin/python scripts/backtest/colorplast_verify_all.py`
Expected: 7/7 inchangé. Les valeurs unitaires réelles en base sont 5,00 / 7,40 / 7,50 / 15,00 €, toutes sous le repli de 21,40 €.

Lancer également les autres backtests disponibles (`comitech_verify_all.py`, `cartol_compare_fast.py`) et comparer au relevé pris avant le bloc 4. Tout écart doit être élucidé avant de continuer.

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/payroll/engine/calcul_frais.py \
        backend/tests/unit/payroll/test_frais_pro_sections.py
git commit -m "fix(paie): lire la forme réelle du barème de frais professionnels"
```

---

### Task 11: Rendre la situation repas déclarable

**Files:**
- Create: `supabase/migrations/20260803091000_bonus_types_situation_repas.sql`
- Modify: `backend/app/modules/bonus_types/domain/entities.py`
- Modify: `backend/app/modules/payroll/documents/payslip_generator.py`
- Modify: `backend/app/modules/payroll/documents/payslip_run_heures.py`
- Test: `backend/tests/unit/payroll/test_frais_pro_sections.py`

**Interfaces:**
- Consomme : `exoneration_repas(..., situation=...)` (Task 10), `quantity_kind` (Task 8).
- Produit : colonne `company_bonus_types.situation_repas` ; clé `situation_repas` portée par la saisie jusqu'à `appliquer_exoneration_note_frais`.

Sans cette tâche, le paramètre `situation` de la Task 10 resterait inutilisé et le repli à 21,40 € serait définitif — c'est-à-dire le même défaut que celui qu'on répare : une fonction correcte que personne n'appelle.

- [ ] **Step 1: Écrire la migration**

Vérifier d'abord l'absence de collision : Run `ls supabase/migrations/ | grep 20260803091000` — Expected: aucune sortie.

Créer `supabase/migrations/20260803091000_bonus_types_situation_repas.sql` :

```sql
-- Situation de restauration d'une prime de type panier/repas, qui détermine
-- le plafond d'exonération URSSAF applicable. NULL = non déclaré : le moteur
-- retient alors le plafond le plus élevé plutôt que de réintégrer à tort.
alter table public.company_bonus_types
  add column if not exists situation_repas text;

alter table public.company_bonus_types
  drop constraint if exists company_bonus_types_situation_repas_check;

alter table public.company_bonus_types
  add constraint company_bonus_types_situation_repas_check
  check (
    situation_repas is null
    or situation_repas in (
      'sur_lieu_travail',
      'hors_locaux_sans_restaurant',
      'hors_locaux_avec_restaurant'
    )
  );

comment on column public.company_bonus_types.situation_repas is
  'Situation de restauration : sur_lieu_travail (7,50 €), hors_locaux_sans_restaurant (10,40 €), hors_locaux_avec_restaurant (21,40 €). NULL = non déclaré.';
```

- [ ] **Step 2: Écrire le test qui échoue**

Ajouter à `backend/tests/unit/payroll/test_frais_pro_sections.py` :

```python
from app.modules.payroll.engine.calcul_frais import appliquer_exoneration_note_frais


def test_panier_sans_situation_declaree_reste_exonere():
    """Repli : 15 € le repas passe sous le plafond le plus élevé (21,40 €)."""
    exo, reint, plafond = appliquer_exoneration_note_frais(
        {"montant": 15.0, "prime_id": "panier", "type": "panier"},
        FORME_STOCKEE,
    )
    assert plafond == 21.4
    assert exo == 15.0
    assert reint == 0.0


def test_panier_declare_sur_lieu_de_travail_est_plafonne():
    exo, reint, plafond = appliquer_exoneration_note_frais(
        {
            "montant": 15.0,
            "prime_id": "panier",
            "type": "panier",
            "situation_repas": "sur_lieu_travail",
        },
        FORME_STOCKEE,
    )
    assert plafond == 7.5
    assert exo == 7.5
    assert reint == 7.5
```

- [ ] **Step 3: Lancer le test pour vérifier qu'il échoue**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/payroll/test_frais_pro_sections.py -k situation -q`
Expected: FAIL — `test_panier_declare_sur_lieu_de_travail_est_plafonne` obtient `plafond == 21.4`, la situation n'étant pas transmise.

- [ ] **Step 4: Transmettre la situation dans le calcul**

Dans `backend/app/modules/payroll/engine/calcul_frais.py`, dans `appliquer_exoneration_note_frais`, remplacer :

```python
    if "repas" in type_ndf or "panier" in type_ndf:
        plafond = exoneration_repas(frais_pro, "repas")
```

par :

```python
    if "repas" in type_ndf or "panier" in type_ndf:
        plafond = exoneration_repas(
            frais_pro, "repas", situation=saisie.get("situation_repas")
        )
```

- [ ] **Step 5: Lancer les tests pour vérifier qu'ils passent**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/payroll/test_frais_pro_sections.py -q`
Expected: PASS — 14 tests passés.

- [ ] **Step 6: Faire remonter la situation depuis le catalogue**

Dans `backend/app/modules/bonus_types/domain/entities.py`, ajouter au dataclass `BonusType`, après `export_code` :

```python
    situation_repas: Optional[str] = None
```

Dans `backend/app/modules/payroll/documents/payslip_generator.py`, au même endroit que l'ajout du Step 5 de la Task 8, ajouter :

```python
            if row.get("situation_repas"):
                prime_entry["situation_repas"] = row["situation_repas"]
```

La colonne vivant sur `company_bonus_types` et non sur `monthly_inputs`, la requête qui charge les saisies doit joindre le type de prime. Repérer la requête qui alimente `row` dans ce fichier et étendre son `select` avec `company_bonus_types(situation_repas)`, puis aplatir la valeur avant usage. Si la jointure s'avère coûteuse ou fragile, l'alternative acceptable est de dupliquer `situation_repas` sur `monthly_inputs` au moment de la génération, comme le fait déjà `export_code`.

Dans `backend/app/modules/payroll/documents/payslip_run_heures.py`, propager la clé dans le dictionnaire passé à `appliquer_exoneration_note_frais` de la branche panier :

```python
                    exo, reint, plafond = appliquer_exoneration_note_frais(
                        {
                            "montant": unit,
                            "prime_id": prime_id,
                            "type": "panier",
                            "situation_repas": saisie.get("situation_repas"),
                        },
                        contexte.baremes.get("frais_pro"),
                    )
```

- [ ] **Step 7: Vérifier qu'aucun euro n'a bougé**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit -q`
Expected: PASS, sans échec nouveau.

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib PYTHONPATH=. .venv-ci/bin/python scripts/backtest/colorplast_verify_all.py`
Expected: 7/7 inchangé. Aucune prime n'ayant de `situation_repas` déclarée, le repli s'applique partout et rien ne change. Le durcissement viendra entreprise par entreprise, sous le contrôle d'Elsa.

- [ ] **Step 8: Commit**

```bash
git add supabase/migrations/20260803091000_bonus_types_situation_repas.sql \
        backend/app/modules/bonus_types/domain/entities.py \
        backend/app/modules/payroll/engine/calcul_frais.py \
        backend/app/modules/payroll/documents/payslip_generator.py \
        backend/app/modules/payroll/documents/payslip_run_heures.py \
        backend/tests/unit/payroll/test_frais_pro_sections.py
git commit -m "feat(paie): déclarer la situation de restauration d'une prime panier"
```

---

### Task 12: Plafond annuel de transport et dépassement

**Files:**
- Create: `backend/app/modules/payroll/engine/plafond_transport.py`
- Create: `backend/tests/unit/payroll/test_plafond_transport.py`

**Interfaces:**
- Consomme : `sections_frais_pro` (Task 10).
- Produit :
  - `plafond_annuel_transport(frais_pro: dict | None, *, avec_abonnement_public: bool = False) -> float | None`
  - `depassement_annuel(cumul_verse: float, plafond: float | None) -> float`

  Utilisées par la Task 12.

Le plafond de transport est **annuel et cumulatif**, alors que toute la mécanique d'exonération existante raisonne ligne par ligne et mois par mois. C'est la pièce neuve du lot.

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `backend/tests/unit/payroll/test_plafond_transport.py` :

```python
"""Plafond annuel d'exonération de la prise en charge des trajets."""

from app.modules.payroll.engine.plafond_transport import (
    depassement_annuel,
    plafond_annuel_transport,
)

BAREME = {
    "FRAIS_PRO": [
        {
            "sections": {
                "mobilite_durable": {
                    "employeurs_prives": {
                        "limite_base": 600.0,
                        "limite_cumul_transport_public": 900.0,
                        "limite_cumul_carburant_total": 600.0,
                        "limite_cumul_carburant_part_carburant": 300.0,
                    }
                }
            }
        }
    ]
}


def test_plafond_de_base():
    assert plafond_annuel_transport(BAREME) == 600.0


def test_plafond_releve_en_cas_de_cumul_avec_abonnement_public():
    assert plafond_annuel_transport(BAREME, avec_abonnement_public=True) == 900.0


def test_bareme_absent_donne_none():
    assert plafond_annuel_transport(None) is None
    assert plafond_annuel_transport({"FRAIS_PRO": []}) is None


def test_depassement_girerd_3000_euros_par_an():
    """GIRERD Fabrice, Colorplast : 250 €/mois soit 3 000 €/an."""
    assert depassement_annuel(3000.0, 600.0) == 2400.0


def test_depassement_espinosa_1200_euros_par_an():
    """ESPINOSA Anthony, Colorplast : 100 €/mois soit 1 200 €/an."""
    assert depassement_annuel(1200.0, 600.0) == 600.0


def test_pas_de_depassement_sous_le_plafond():
    assert depassement_annuel(500.0, 600.0) == 0.0


def test_pas_de_depassement_au_plafond_exact():
    assert depassement_annuel(600.0, 600.0) == 0.0


def test_plafond_inconnu_ne_signale_aucun_depassement():
    """Sans barème, on ne peut rien affirmer : ne pas alerter à tort."""
    assert depassement_annuel(3000.0, None) == 0.0
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/payroll/test_plafond_transport.py -q`
Expected: FAIL au collect — `ModuleNotFoundError: No module named 'app.modules.payroll.engine.plafond_transport'`.

- [ ] **Step 3: Implémenter le module**

Créer `backend/app/modules/payroll/engine/plafond_transport.py` :

```python
"""Plafond annuel d'exonération de la prise en charge des trajets domicile-travail.

Contrairement aux plafonds repas, unitaires, celui-ci est annuel et cumulatif
par salarié. Les valeurs proviennent du barème URSSAF scrapé
(section mobilite_durable, employeurs_prives).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.modules.payroll.engine.calcul_frais import sections_frais_pro


def plafond_annuel_transport(
    frais_pro: Optional[Dict[str, Any]],
    *,
    avec_abonnement_public: bool = False,
) -> Optional[float]:
    """Plafond annuel applicable (€), None si le barème est absent.

    Le plafond est relevé lorsque le salarié bénéficie aussi de la prise en
    charge obligatoire de 50 % d'un abonnement de transport public.
    """
    sections = sections_frais_pro(frais_pro)
    mobilite = sections.get("mobilite_durable") or {}
    if not isinstance(mobilite, dict):
        return None
    prives = mobilite.get("employeurs_prives") or {}
    if not isinstance(prives, dict):
        return None
    cle = "limite_cumul_transport_public" if avec_abonnement_public else "limite_base"
    valeur = prives.get(cle)
    if isinstance(valeur, (int, float)) and valeur > 0:
        return float(valeur)
    return None


def depassement_annuel(cumul_verse: float, plafond: Optional[float]) -> float:
    """Part du cumul annuel excédant le plafond, 0 si plafond inconnu."""
    if plafond is None:
        return 0.0
    return round(max(0.0, float(cumul_verse) - float(plafond)), 2)
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/payroll/test_plafond_transport.py -q`
Expected: PASS — 8 tests passés.

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/payroll/engine/plafond_transport.py \
        backend/tests/unit/payroll/test_plafond_transport.py
git commit -m "feat(paie): calculer le plafond annuel d'exonération des trajets"
```

---

### Task 13: Alerter au dépassement, sans modifier le bulletin

**Files:**
- Modify: `backend/app/modules/payroll/engine/controles_convention.py`
- Modify: `backend/app/modules/payroll/documents/payslip_generator.py:1102-1106`
- Test: `backend/tests/unit/payroll/test_plafond_transport.py`

**Interfaces:**
- Consomme : `plafond_annuel_transport`, `depassement_annuel` (Task 12), `_alert` (existant, `controles_convention.py:35`).
- Produit : `controle_plafond_transport(cumul_annuel: float, frais_pro: dict | None, *, avec_abonnement_public: bool = False, annee: int) -> list[dict]`.

Au dépassement, EYWAI **prévient** — il ne réintègre pas. Une réintégration automatique modifierait des bulletins qui convergent aujourd'hui avec ceux du cabinet, sans qu'Elsa l'ait décidé. Le dépassement constaté porte sur la paie produite par le cabinet, pas sur une erreur d'EYWAI.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `backend/tests/unit/payroll/test_plafond_transport.py` :

```python
from app.modules.payroll.engine.controles_convention import controle_plafond_transport


def test_aucune_alerte_sous_le_plafond():
    assert controle_plafond_transport(500.0, BAREME, annee=2026) == []


def test_alerte_au_dessus_du_plafond():
    alertes = controle_plafond_transport(3000.0, BAREME, annee=2026)
    assert len(alertes) == 1
    alerte = alertes[0]
    assert alerte["code"] == "transport_plafond_annuel_depasse"
    assert alerte["critique"] is True
    assert "2 400,00" in alerte["message"].replace(" ", " ").replace("\xa0", " ")
    assert "600" in alerte["message"]


def test_aucune_alerte_sans_bareme():
    assert controle_plafond_transport(3000.0, None, annee=2026) == []


def test_plafond_releve_evite_l_alerte():
    """Avec abonnement public, le plafond passe à 900 € : 800 € ne dépasse plus."""
    alertes = controle_plafond_transport(
        800.0, BAREME, avec_abonnement_public=True, annee=2026
    )
    assert alertes == []
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/payroll/test_plafond_transport.py -q`
Expected: FAIL au collect — `ImportError: cannot import name 'controle_plafond_transport'`.

- [ ] **Step 3: Implémenter le contrôle**

Ajouter à `backend/app/modules/payroll/engine/controles_convention.py`, après `controle_prime_anciennete` :

```python
def controle_plafond_transport(
    cumul_annuel: float,
    frais_pro: Dict[str, Any] | None,
    *,
    avec_abonnement_public: bool = False,
    annee: int,
) -> List[Dict[str, Any]]:
    """Signale un dépassement du plafond annuel d'exonération des trajets.

    Contrôle non bloquant : le bulletin n'est pas modifié. La décision de
    régulariser appartient à la RH et au cabinet.
    """
    from app.modules.payroll.engine.plafond_transport import (
        depassement_annuel,
        plafond_annuel_transport,
    )

    plafond = plafond_annuel_transport(
        frais_pro, avec_abonnement_public=avec_abonnement_public
    )
    exces = depassement_annuel(cumul_annuel, plafond)
    if exces <= 0:
        return []

    def _eur(v: float) -> str:
        return f"{v:,.2f}".replace(",", " ").replace(".", ",")

    return [
        _alert(
            code="transport_plafond_annuel_depasse",
            critique=True,
            message=(
                f"Indemnité trajet domicile-travail : {_eur(cumul_annuel)} € versés "
                f"en {annee} pour un plafond d'exonération de {_eur(plafond)} € — "
                f"dépassement de {_eur(exces)} €. La part excédentaire est "
                "normalement soumise à cotisations et imposable. Le bulletin n'a "
                "pas été modifié : à arbitrer avec le cabinet."
            ),
        )
    ]
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit/payroll/test_plafond_transport.py -q`
Expected: PASS — 12 tests passés.

- [ ] **Step 5: Brancher le contrôle sur la génération du bulletin**

Dans `backend/app/modules/payroll/documents/payslip_generator.py`, juste avant l'appel à `extraire_messages_alertes_rh` (ligne 1102), insérer :

```python
        try:
            from app.core.database import supabase as _sb
            from app.modules.payroll.engine.baremes_loader import (
                assembler_baremes,
                charger_db_baremes,
            )
            from app.modules.payroll.engine.controles_convention import (
                controle_plafond_transport,
            )

            _saisies_annee = (
                _sb.table("monthly_inputs")
                .select("amount, name")
                .eq("employee_id", employee_id)
                .eq("year", year)
                .execute()
                .data
                or []
            )
            _cumul = sum(
                float(s.get("amount") or 0)
                for s in _saisies_annee
                if "transport" in (s.get("name") or "").lower()
            )
            _spec = employee_data.get("specificites_paie") or {}
            _abo = float(
                ((_spec.get("transport") or {}).get("abonnement_mensuel_total")) or 0
            )
            _frais_pro = assembler_baremes(charger_db_baremes(_sb)).get("frais_pro")
            for _a in controle_plafond_transport(
                _cumul,
                _frais_pro,
                avec_abonnement_public=_abo > 0,
                annee=year,
            ):
                final_payslip_data.setdefault("alertes", []).append(_a)
        except Exception as _e:
            logger.warning(f"[WARNING] contrôle plafond transport: {_e}")
```

Les identifiants `employee_id`, `year`, `employee_data` et `final_payslip_data`
sont bien en portée à cet endroit (`payslip_generator.py:347`, `362`, `994`,
`1064`). Le barème est rechargé localement plutôt que réutilisé depuis une
variable de la fonction, dont le nom n'est pas garanti à cette profondeur. Le
contrôle est enveloppé dans un `try` afin qu'une alerte ne puisse jamais faire
échouer une génération de bulletin.

- [ ] **Step 6: Vérifier la non-régression complète**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit -q`
Expected: PASS, sans échec nouveau.

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib PYTHONPATH=. .venv-ci/bin/python scripts/backtest/colorplast_verify_all.py`
Expected: 7/7, montants inchangés. L'alerte s'ajoute aux métadonnées du bulletin, elle ne touche aucun euro.

- [ ] **Step 7: Vérifier que l'alerte se déclenche sur le cas réel**

Run:
```bash
cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib PYTHONPATH=. .venv-ci/bin/python -c "
from app.core.database import supabase
from app.modules.payroll.engine.baremes_loader import charger_db_baremes, assembler_baremes
from app.modules.payroll.engine.controles_convention import controle_plafond_transport
b = assembler_baremes(charger_db_baremes(supabase))
for alerte in controle_plafond_transport(3000.0, b['frais_pro'], annee=2026):
    print(alerte['code'], '|', alerte['message'])
"
```
Expected: une alerte `transport_plafond_annuel_depasse` mentionnant 3 000,00 €, 600,00 € et un dépassement de 2 400,00 €.

- [ ] **Step 8: Commit**

```bash
git add backend/app/modules/payroll/engine/controles_convention.py \
        backend/app/modules/payroll/documents/payslip_generator.py \
        backend/tests/unit/payroll/test_plafond_transport.py
git commit -m "feat(paie): alerter au dépassement du plafond annuel de transport"
```

---

## Recette finale

- [ ] **Suite unitaire complète**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -m pytest tests/unit -q`
Expected: PASS. Les 51 échecs d'intégration pré-existants ne sont pas concernés.

- [ ] **Backtests de non-régression**

Lancer chaque backtest disponible et comparer au relevé pris avant le début du plan :

```bash
cd backend
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib PYTHONPATH=. .venv-ci/bin/python scripts/backtest/colorplast_verify_all.py
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib PYTHONPATH=. .venv-ci/bin/python scripts/backtest/comitech_verify_all.py
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib PYTHONPATH=. .venv-ci/bin/python scripts/backtest/cartol_compare_fast.py
```

Expected: nombres de convergés identiques à la référence. Tout écart doit être élucidé, jamais accepté au motif que « ça converge encore à peu près ».

- [ ] **Recette fonctionnelle sur l'environnement de test**

Après resynchronisation du test (ses données dataient du 29 juillet) :

1. Sur la fiche d'un salarié de Colorplast, renseigner une indemnité trajet domicile-travail de 250 € avec une date d'effet au 1er du mois courant.
2. Dans Entreprise > Paie > Règles variables paie, créer une règle de type `transport_domicile_travail` ciblant ce salarié.
3. Dans Saisies > Primes, cliquer « Préparer variables du mois ». Vérifier qu'une ligne « Indemnité de transport » à 250 € apparaît.
4. Corriger le montant à 200 €, relancer « Préparer variables du mois », vérifier que la ligne **reste** à 200 €.
5. Générer le bulletin, vérifier que la prime apparaît une seule fois au net à payer.

- [ ] **Points à reposer à Elsa**

Ces réponses n'ont pas bloqué l'implémentation, mais elles restent ouvertes :

- La liste des bénéficiaires chez Colorplast (elle n'a confirmé la complétude que pour Mont Blanc Composite).
- Le code de rubrique comptable des saisies (`export_code` est vide sur les 1 000 saisies) — alimente #26.
- La confirmation du régime d'exonération applicable à une indemnité forfaitaire de trajet prévue par avenant, qui conditionne le libellé de l'alerte de la Task 12.
