# Patterns de promptage — copilot RH EYWAI

Référence pour Phase 3 (`providers.py`). Ne pas dupliquer ces blocs entiers dans le code — appliquer les principes.

## 1. Architecture multi-prompts (déjà en place)

```
Question utilisateur
  → analyze_intent_and_plan (JSON structuré)
    → branche app_help | CC | data_retrieval
      → answer_app_usage_question | answer_CC | generate_sql_for_step × N
        → synthesize_final_answer (data uniquement)
```

**Pourquoi JSON intent** : force le routage explicite, évite le SQL sur « comment faire ».

## 2. Paramètres LLM par étape

| Étape | temperature | max_tokens | Raison |
|-------|-------------|------------|--------|
| generate_sql_* | 0 | — | Déterminisme SQL |
| analyze_intent | 0.3 | — | Routage stable avec légère flexibilité |
| answer_app_usage | 0.3 | 1200 | Réponses structurées, pas trop longues |
| answer_CC | 0.2 | 2000 | Fidélité au texte juridique |
| synthesize_final | 0.7 | — | Ton naturel RH |
| format_answer_from_data | 0 | — | Faits stricts |

## 3. Règles intent JSON — à préserver

```json
{
  "requires_app_help": true  // PRIORITAIRE — désactive SQL et CC
}
```

Déclencheurs app_help (non exhaustif — ajouter few-shot si nouveau) :
- « comment », « où », « où trouver », « à quoi sert », « comment faire »
- navigation, module, écran, bouton, onglet, menu
- identifiants de connexion, mot de passe collaborateur

## 4. Few-shot : quand en ajouter

Ajouter **1 exemple** dans `analyze_intent_and_plan` quand :
- Une nouvelle feature crée une ambiguïté intent (ex. « prêt » = employee_loans data vs aide navigation)
- Les tests matrice montrent un mauvais routage récurrent

Format :
```
- "[question exacte utilisateur]" → [champ JSON]: true, [autres]: false
```

Ne pas dépasser **~15 exemples** dans le prompt intent (token budget).

## 5. Schéma SQL — techniques efficaces

### Placeholder date
```python
DATABASE_SCHEMA_TEXT_TO_SQL = """... La date actuelle est {today}. ..."""
```

### Exemple JSONB inline (1 seul par champ)
```
-- Salaire Brut: (payslip_data->>'salaire_brut')::numeric
```

### Valeurs enum explicites
```
status (text): 'pending', 'validated', 'rejected', 'cancelled'
```

### Rappel filtre entreprise (critique RLS)
```
IMPORTANT: Toute requête sur employees ou table liée DOIT filtrer
via employees.company_id ou jointure employees WHERE company_id = ...
```

## 6. Prompt aide logiciel — contraintes UX

- Français, concis, orienté action
- Chemins : « Menu latéral → [Section] → [Page] »
- Gras markdown `**Titre :**` autorisé ; pas de `#`, pas de routes `/url`
- Distinguer RH vs collaborateur
- Si absent du guide → honnêteté + Support

## 7. Prompt synthèse data — anti-patterns

**Interdit dans la réponse utilisateur** :
- Mention de SQL, tables, colonnes, JSONB
- « Selon la requête… »
- Données brutes non interprétées

**Encouragé** :
- Contexte RH (« ce qui représente X % de l'effectif »)
- Suggestion CC si sujet réglementaire (« consultez votre convention pour le détail legal »)
- Structure claire si multi-employés

## 8. Gestion du contexte conversation

Historique : **5 derniers messages** (`conversation_history[-5:]`) — ne pas augmenter sans test token.

Pour questions de suivi (« et pour elle ? »), l'intent doit s'appuyer sur l'historique — vérifier que le prompt intent inclut bien `conversation_context`.

## 9. Troncature CC

Texte CC > 150 000 chars → troncature (déjà implémentée). Documenter dans le rapport si une CC fréquente est tronquée.

## 10. Checklist qualité prompt (avant merge)

- [ ] Intent app_help prioritaire sur data/CC
- [ ] Schéma agent ≤ ~4000 tokens (estimation)
- [ ] Schéma text-to-sql : tous les JSONB fréquents documentés
- [ ] Few-shots couvrent les 3 familles
- [ ] Aucune route `/path` dans app_knowledge
- [ ] Tests unitaires copilot passent
