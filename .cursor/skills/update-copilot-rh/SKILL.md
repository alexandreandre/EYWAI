---
name: update-copilot-rh
description: >-
  Actualise exhaustivement l'assistant « Demander à l'IA » du tableau de bord RH
  EYWAI : guide produit (navigation, parcours, actions), schéma Supabase
  (tables/colonnes/valeurs JSONB), exemples few-shot et règles de promptage.
  À utiliser lorsque l'utilisateur tape /update-copilot-rh, demande de mettre à
  jour l'agent IA du dashboard, enrichir le copilot RH, ou synchroniser les
  connaissances après une nouvelle feature ou migration Supabase.
---

# Actualiser l'assistant RH IA (`/update-copilot-rh`)

## Objectif

Maintenir l'agent **« Demander à l'IA »** (`CopilotModalAgent` → `POST /query-agent`) capable de répondre à **toute question RH** en trois familles :

| Famille | Mécanisme | Fichier source |
|---------|-----------|----------------|
| Données entreprise (effectifs, paie, absences…) | Text-to-SQL + synthèse | `schema_context.py` |
| Conventions collectives | Texte PDF en cache | tables CC (déjà branchées) |
| Aide à l'utilisation du logiciel | Guide navigation | `app_knowledge.py` |

Livrable : fichiers Python mis à jour + tests verts + matrice de questions RH validée.

---

## Architecture (ne pas dupliquer ailleurs)

```
frontend/src/components/CopilotModalAgent.tsx
  → backend/app/modules/copilot/api/router.py (handle_agent_query)
    → application/commands.py (handle_agent_query)
      → providers.py (prompts LLM)
      → app_knowledge.py (APP_FEATURE_GUIDE)
      → schema_context.py (DATABASE_SCHEMA_*)
```

**Ne jamais** mettre de routes, chemins `/url` ou noms de tables dans `APP_FEATURE_GUIDE` (règle produit).
**Toujours** documenter tables/colonnes/valeurs enum dans `schema_context.py`.

---

## Workflow obligatoire

Copier cette checklist et cocher au fur et à mesure :

```
Progression :
- [ ] Phase 0 — État des lieux (git diff migrations + sidebar)
- [ ] Phase 1 — Guide produit (app_knowledge.py)
- [ ] Phase 2 — Schéma BDD (schema_context.py)
- [ ] Phase 3 — Prompts & few-shots (providers.py si nécessaire)
- [ ] Phase 4 — Tests unitaires copilot
- [ ] Phase 5 — Matrice RH (20+ questions)
- [ ] Phase 6 — Rapport de synthèse
```

### Phase 0 — État des lieux

```bash
git log --oneline -15 -- supabase/migrations/ frontend/src/components/ui/app-sidebar.tsx frontend/src/components/ui/employee-sidebar.tsx
git diff origin/main -- supabase/migrations/ 2>/dev/null | head -200
```

Lire les fichiers actuels :
- `backend/app/modules/copilot/infrastructure/app_knowledge.py`
- `backend/app/modules/copilot/infrastructure/schema_context.py`
- `backend/app/modules/copilot/infrastructure/providers.py` (bloc `analyze_intent_and_plan`)

Sources de vérité : voir [sources-of-truth.md](sources-of-truth.md).

### Phase 1 — Guide produit (`APP_FEATURE_GUIDE`)

**Principe** : le guide = ce que voit un RH dans la barre latérale + parcours clés. Pas de code.

1. Extraire la navigation depuis :
   - `frontend/src/components/ui/app-sidebar.tsx` (RH : `RH_HOME`, `RH_TEAM_GROUPS`, `RH_GESTION_GROUPS`, `RH_PAIE_GROUPS`)
   - `frontend/src/components/ui/employee-sidebar.tsx` (collaborateur : `coreNavItems`)
2. Pour chaque entrée de menu, documenter :
   - **Libellé exact** (copier depuis le code, pas de paraphrase)
   - **À quoi ça sert** (1–2 phrases métier RH)
   - **Actions principales** (créer, valider, exporter…)
   - **Onglets / sous-écrans** si la page en a (fiche collaborateur, Paie, Mon Entreprise…)
   - **Profil concerné** : RH / collaborateur / élu CSE / admin plateforme
3. Conserver la structure existante (sections `====`, espaces RH vs collaborateur).
4. Mettre à jour les parcours paie numérotés si le workflow sidebar a changé.
5. Ajouter une section **FAQ RH transverses** (identifiants, lancer la paie, convention collective, multi-entreprises).

**Format d'une entrée** (concis, orienté action) :
```
— [Libellé menu] (« [Libellé exact] ») :
  [Usage métier]. [Actions clés]. [Onglets si pertinent].
```

**Interdits dans le guide** : routes React, noms de tables, détails API, fonctionnalités absentes du code.

### Phase 2 — Schéma BDD (`schema_context.py`)

Deux constantes, rôles distincts :

| Constante | Audience LLM | Niveau de détail |
|-----------|--------------|------------------|
| `DATABASE_SCHEMA_TEXT_TO_SQL` | Génération SQL directe | **Maximal** : colonnes, types, JSONB, exemples SQL, valeurs enum |
| `DATABASE_SCHEMA_AGENT` | Planification agent + SQL par étapes | **Condensé** : colonnes clés + jointures + enums |

**Checklist tables RH** : [schema-tables-rh.md](schema-tables-rh.md) — couvrir **toutes** les tables marquées « obligatoire ».

Pour chaque table documentée :
```markdown
Table 'nom_table': [Rôle métier en une phrase].
  - col (type): description. Valeurs: 'a', 'b', 'c' si enum.
  - champ_jsonb (jsonb): structure {"cle": type}. Usage SQL: (champ->>'cle')::type
  - Jointures: employee_id → employees.id, company_id → companies.id
```

**Règles SQL critiques à inclure dans le schéma** :
- Filtrer par entreprise : `employees.company_id = '<company_id>'` (ou jointure via employees)
- JSONB : toujours montrer la syntaxe `->>` et le cast `::numeric` / `::boolean` / `::date`
- Dates : `hire_date`, `selected_days` (array), `month`/`year` sur payslips
- Statuts employé : inclure `parti`, `en_onboarding` si présents en migration
- Ne pas documenter les tables scraping / super_admin / audit (hors périmètre RH)

**Extraction depuis migrations** :
```bash
rg "CREATE TABLE" supabase/migrations/ --no-heading
rg "ALTER TABLE.*ADD COLUMN" supabase/migrations/ --no-heading | tail -40
```

Croiser avec les `.table("...")` du backend pour les colonnes réellement lues.

### Phase 3 — Prompts (`providers.py`)

Modifier **uniquement si** un gap persiste après Phase 1–2.

Techniques à appliquer (détails : [prompt-patterns.md](prompt-patterns.md)) :

1. **Intent JSON** (`analyze_intent_and_plan`) : enrichir les exemples few-shot quand une nouvelle famille de questions apparaît (ex. prêts employeur, évolution salaire).
2. **Priorité aide logiciel** : conserver `requires_app_help` prioritaire sur SQL/CC.
3. **Températures** : SQL = 0 ; intent = 0.3 ; aide app = 0.3 ; CC = 0.2 ; synthèse = 0.7.
4. **Clarification** : demander précision si question data vague (« combien d'employés ? » → CDI ? cadres ?).
5. **Synthèse** : jamais mentionner SQL/tables ; ton collègue RH expert.

### Phase 4 — Tests

```bash
cd backend && pytest tests/unit/copilot/ -q
```

Mettre à jour `tests/unit/copilot/test_app_knowledge.py` si de nouvelles sections obligatoires (ex. prêts employeur, avances & acomptes).

Ajouter un test si une feature critique manquait :
```python
def test_guide_covers_employee_loans():
    assert "Prêts employeur" in APP_FEATURE_GUIDE
```

### Phase 5 — Matrice de validation RH

Exécuter mentalement ou via appels API (si env LLM dispo) les catégories de [rh-question-taxonomy.md](rh-question-taxonomy.md).

Minimum **20 questions** couvrant les 3 familles. Pour chaque question noter :
- Intent attendu (data / CC / app_help)
- Réponse satisfaisante ? (oui / partiel / non + cause)

**Verdict matrice** :
- ≥ 90 % oui → OK
- 70–89 % → compléter guide ou schéma, relancer Phase 1–2
- < 70 % → revue architecture intent + schéma incomplet

### Phase 6 — Rapport

```markdown
## Actualisation copilot RH — [date]

### Fichiers modifiés
- app_knowledge.py : [+N lignes, sections ajoutées]
- schema_context.py : [+N tables/colonnes]
- providers.py : [oui/non, quoi]

### Écarts corrigés
- [liste]

### Matrice RH : X/20 OK

### Limites connues
- [ce que l'agent ne peut pas faire — ex. données temps réel badgeuse sans table X]
```

---

## Principes d'optimisation token

Le contexte LLM est partagé — chaque token compte.

1. **Guide produit** : phrases courtes, pas de doublons entre sections ; FAQ pour les questions récurrentes plutôt que répéter dans chaque module.
2. **Schéma agent** : 1 ligne par colonne secondaire, détail JSONB seulement sur les champs requêtés souvent (salaire, payslip_data, cumuls).
3. **Schéma text-to-sql** : exemples SQL inline uniquement sur JSONB et arrays.
4. **Few-shots** : 1 exemple par intent nouveau, pas de liste exhaustive dans le prompt (liste dans taxonomy, pas dans le prompt).

---

## Quand relancer ce skill

- Nouvelle entrée sidebar RH ou collaborateur
- Migration Supabase ajoutant une table/colonne métier RH
- Nouveau parcours paie ou module (CSE, formation, badgeuse…)
- Retours utilisateurs : « l'IA ne sait pas répondre à… »
- Avant merge d'une grosse feature RH sur `main`

---

## Ressources

- [sources-of-truth.md](sources-of-truth.md) — fichiers à lire dans le dépôt
- [schema-tables-rh.md](schema-tables-rh.md) — inventaire tables Supabase RH
- [rh-question-taxonomy.md](rh-question-taxonomy.md) — questions que l'agent doit couvrir
- [prompt-patterns.md](prompt-patterns.md) — techniques de promptage copilot
