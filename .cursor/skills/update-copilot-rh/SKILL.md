---
name: update-copilot-rh
description: >-
  Actualise exhaustivement l'assistant « Demander à l'IA » du tableau de bord RH
  EYWAI : guide produit (navigation, parcours, actions), catalogue d'outils RH
  fermés (domain/tools + secure_queries), exemples few-shot et règles de
  promptage. À utiliser lorsque l'utilisateur tape /update-copilot-rh, demande
  de mettre à jour l'agent IA du dashboard, enrichir le copilot RH, ou
  synchroniser les connaissances après une nouvelle feature.
---

# Actualiser l'assistant RH IA (`/update-copilot-rh`)

## Objectif

Maintenir l'agent **« Demander à l'IA »** (`CopilotModalAgent` → `POST /query-agent`) capable de répondre à **toute question RH** en trois familles :

| Famille | Mécanisme | Fichier source |
|---------|-----------|----------------|
| Données entreprise (effectifs, paie, absences…) | Catalogue fermé d'outils scopés + synthèse | `domain/tools.py`, `secure_queries.py` |
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
      → domain/tools.py + application/tool_service.py + secure_queries.py
```

**Ne jamais** mettre de routes, chemins `/url` ou noms de tables dans `APP_FEATURE_GUIDE` (règle produit).

**Ne jamais** réintroduire `schema_context.py` ni le text-to-SQL libre (supprimés volontairement, commit `8596ee7a`) : toute donnée RH passe par le catalogue fermé d'outils, avec `company_id` imposé serveur.

---

## Workflow obligatoire

Copier cette checklist et cocher au fur et à mesure :

```
Progression :
- [ ] Phase 0 — État des lieux (git diff migrations + sidebar)
- [ ] Phase 1 — Guide produit (app_knowledge.py)
- [ ] Phase 2 — Catalogue d'outils (tools.py + secure_queries.py)
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
- `backend/app/modules/copilot/domain/tools.py`
- `backend/app/modules/copilot/infrastructure/secure_queries.py`
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

### Phase 2 — Catalogue d'outils fermés

Fichiers :
- `domain/tools.py` — `ToolName`, schémas d'arguments, `parse_tool_calls` (fail-closed)
- `infrastructure/secure_queries.py` — requêtes scopées `company_id` serveur
- `application/tool_service.py` — mapping outil → handler

Pour chaque outil :
1. Documenter les arguments dans le prompt `analyze_intent_and_plan` (valeurs enum exactes).
2. Si un filtre métier manque (ex. `contract_type`, borne de dates absences) : l'ajouter au schéma + à `secure_queries` + tests.
3. Si une famille de questions data revient souvent et n'est pas couverte : **ajouter un outil typé** (jamais de SQL libre).
4. Interdits LLM : `company_id`, `group_id`, `sql`, `query`, `table`, `employee_ids`.

Inventaire tables utiles pour de futurs outils : [schema-tables-rh.md](schema-tables-rh.md) (référence, pas de doc SQL dans le prompt).

### Phase 3 — Prompts (`providers.py`)

Modifier **uniquement si** un gap persiste après Phase 1–2.

Techniques à appliquer (détails : [prompt-patterns.md](prompt-patterns.md)) :

1. **Intent JSON** (`analyze_intent_and_plan`) : enrichir les few-shots quand une nouvelle famille apparaît.
2. **Priorité aide logiciel** : conserver `requires_app_help` prioritaire sur data/CC.
3. **Températures** : intent = 0.3 ; aide app = 0.3 ; CC = 0.2 ; synthèse = 0.7.
4. **Clarification** : question data vague → préciser ; hors catalogue → clarification honnête (pas d'outil inventé).
5. **Synthèse** : jamais mentionner outils/SQL/tables ; ton collègue RH expert ; avouer les trous.

### Phase 4 — Tests

```bash
cd backend && pytest tests/unit/copilot/ -q
```

Mettre à jour `tests/unit/copilot/test_app_knowledge.py` si de nouvelles sections obligatoires.

Mettre à jour `test_tools.py` / `test_secure_queries.py` si le catalogue ou les filtres évoluent.

### Phase 5 — Matrice de validation RH

Exécuter mentalement ou via appels API (si env LLM dispo) les catégories de [rh-question-taxonomy.md](rh-question-taxonomy.md).

Minimum **20 questions** couvrant les 3 familles. Pour chaque question noter :
- Intent attendu (data / CC / app_help)
- Réponse satisfaisante ? (oui / partiel / non + cause)

**Verdict matrice** :
- ≥ 90 % oui → OK
- 70–89 % → compléter guide ou outils, relancer Phase 1–2
- < 70 % → revue architecture intent + catalogue incomplet

### Phase 6 — Rapport

```markdown
## Actualisation copilot RH — [date]

### Fichiers modifiés
- app_knowledge.py : [sections ajoutées]
- tools.py / secure_queries.py : [filtres / outils]
- providers.py : [oui/non, quoi]

### Écarts corrigés
- [liste]

### Matrice RH : X/20 OK

### Limites connues
- [ce que l'agent ne peut pas faire — ex. salaire individuel hors catalogue]
```

---

## Principes d'optimisation token

Le contexte LLM est partagé — chaque token compte.

1. **Guide produit** : phrases courtes, pas de doublons entre sections ; FAQ pour les questions récurrentes.
2. **Catalogue outils** : documenter enums et filtres dans le prompt intent, pas le schéma SQL complet.
3. **Few-shots** : 1 exemple par intent nouveau, pas de liste exhaustive dans le prompt.

---

## Quand relancer ce skill

- Nouvelle entrée sidebar RH ou collaborateur
- Nouveau parcours paie ou module (CSE, formation, badgeuse…)
- Nouveau besoin data non couvert par un outil existant
- Retours utilisateurs : « l'IA ne sait pas répondre à… »
- Avant merge d'une grosse feature RH sur `main`

---

## Ressources

- [sources-of-truth.md](sources-of-truth.md) — fichiers à lire dans le dépôt
- [schema-tables-rh.md](schema-tables-rh.md) — inventaire tables Supabase RH (référence outils futurs)
- [rh-question-taxonomy.md](rh-question-taxonomy.md) — questions que l'agent doit couvrir
- [prompt-patterns.md](prompt-patterns.md) — techniques de promptage copilot
