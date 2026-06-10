---
name: is-fonctionnel
description: >-
  Vérifie de façon fiable, après implémentation, plan ou correction, que le
  périmètre annoncé fonctionne réellement (code branché, tests exécutés, preuves
  tracées) et produit un compte rendu avec verdict. À utiliser lorsque
  l'utilisateur tape /is-fonctionnel, demande si c'est bon, si tout est
  fonctionnel, une vérif complète post-implémentation, ou attache explicitement
  ce skill.
---

# Est-ce fonctionnel ? (`/is-fonctionnel`)

## Objectif

**Constater**, avec preuves, si le travail annoncé (feature, plan, correction) **fonctionne réellement** — pas seulement « du code existe ».

Livrable : **compte rendu structuré** + **verdict** (`FONCTIONNEL` | `PARTIEL` | `NON FONCTIONNEL`).

Ce skill **vérifie** ; il **ne complète pas** le périmètre (→ skill **check-feature**) ni n'explore tous les cas imaginables (→ skill **test-complet**). Il **corrige** uniquement un blocage évident qui empêche de conclure la vérif (build cassé, test rouge sur le périmètre) — puis relance la preuve.

---

## Quand utiliser

- **`/is-fonctionnel`** après une implémentation, l'exécution d'un plan, ou une correction.
- « C'est bon ? », « tout est fonctionnel ? », « vérifie que ça marche », « recette fiable ».
- Fin de session avant push/PR : gate de confiance sur le périmètre touché.

**Ne pas** utiliser pour : une question ponctuelle, un résumé en une phrase (→ **resume**), un audit exhaustif 25+ scénarios (→ **test-complet**), compléter une spec manquante (→ **check-feature**).

---

## Entrée et périmètre

1. **Priorité des sources** (du plus fiable au moins) :
   - demande explicite ou plan de la conversation ;
   - checklist d'acceptation citée par l'utilisateur ;
   - diff Git local (`git diff`, `git status`) + derniers commits non poussés ;
   - fichiers ouverts / contexte du fil.
2. Reformuler en **une phrase** : *quoi* doit fonctionner et *pour qui* (rôle, parcours).
3. Si le périmètre reste flou : **une seule** question courte ; sinon documenter les **hypothèses** dans le rapport et ne valider que ce qui est objectivable.

```bash
git fetch origin 2>/dev/null || true
git branch --show-current
git status -sb
git diff --stat
git log --oneline -8
```

---

## Workflow obligatoire

### 1. Checklist d'acceptation vérifiable

Dériver **5 à 15 points testables** du périmètre (pas de critères vagues).

| Bon | Mauvais |
|-----|---------|
| « Un manager peut créer une absence et la voir en liste » | « La feature absences est OK » |
| « PATCH salaire différé renvoie 400 si date passée » | « Le backend est branché » |

Chaque point reçoit un **ID** (`V01`, `V02`, …).

### 2. Cartographie minimale

Pour chaque point, noter **où** ça vit (indicatif EYWAI) :

| Zone | Où chercher |
|------|-------------|
| UI / routes | `frontend/src/`, routes, hooks, client API |
| API | `backend/app/modules/`, routers FastAPI |
| Domaine / règles | services, `domain/`, moteurs paie, etc. |
| Tests | `backend/tests/unit/`, `integration/` ; `e2e/` si UI critique |

Objectif : prouver **existence + câblage** (route enregistrée, menu, DI, appel API réel).

### 3. Preuves — règle d'or

**Aucun statut OK sans preuve.** Preuve = au moins une de :

- sortie de commande (pytest, lint, build) ;
- requête API / test d'intégration exécuté ;
- trace code citée (`fichier:ligne`) **+** enchaînement d'appel vérifié ;
- parcours navigateur observé (si agent ou dev server disponible).

Ordre d'exécution recommandé (adapter au périmètre) :

**Backend** — depuis `backend/` :

```bash
python -m pytest tests/ -m "not e2e" -v --tb=short -k "<mot-clé périmètre>"
python -m pytest tests/unit/<module>/ -v --tb=short
python -m pytest tests/integration/<module>/ -v --tb=short
```

**Frontend** — depuis `frontend/` :

```bash
npm run lint
npm run build
```

**E2E** — si le périmètre est un parcours UI critique et `e2e/` couvre le flux.

**Linter IDE** : `ReadLints` sur les fichiers modifiés du périmètre.

Ne pas abandonner au premier échec : analyser, corriger **uniquement** si ça bloque la conclusion sur le périmètre, **relancer** la preuve, documenter la correction dans le rapport.

### 4. Statuts par point

| Statut | Signification |
|--------|----------------|
| **OK** | Comportement confirmé avec preuve |
| **PARTIEL** | Fonctionne avec réserve (UX, cas limite, message) |
| **ÉCHEC** | Non conforme ou erreur reproductible |
| **NON VÉRIFIÉ** | Impossible sans env / secret / donnée — procédure manuelle fournie |

### 5. Verdict global

| Verdict | Condition |
|---------|-----------|
| **FONCTIONNEL** | Tous les points **critiques** en OK ; aucun ÉCHEC |
| **PARTIEL** | Parcours principal OK mais réserve(s) ou NON VÉRIFIÉ sur secondaire |
| **NON FONCTIONNEL** | Au moins un point **critique** en ÉCHEC ou MANQUANT non branché |

Marquer explicitement quels points sont **critiques** (sécurité, parcours principal, calcul métier, régression évidente).

---

## Compte rendu (obligatoire, en français)

Utiliser ce gabarit :

```markdown
# Compte rendu — /is-fonctionnel : [périmètre en une phrase]

## Verdict
**[FONCTIONNEL | PARTIEL | NON FONCTIONNEL]** — [justification en une phrase]

## Contexte
- Branche : …
- Périmètre vérifié : …
- Hypothèses (si any) : …
- Environnement : [pytest/lint/build lancés ; dev server ; navigateur]

## Synthèse chiffrée
- Points : X — OK : n | PARTIEL : n | ÉCHEC : n | NON VÉRIFIÉ : n

## Checklist
| ID | Critère | Critique ? | Statut | Preuve |
|----|---------|------------|--------|--------|
| V01 | … | oui | OK | `pytest …` / `path:ligne` / observation |

## Écarts détaillés
Pour chaque ÉCHEC / PARTIEL : symptôme, étapes, cause probable, fichier(s).

## Non vérifié / validation manuelle
Procédure pas à pas pour ce que l'agent n'a pas pu exécuter.

## Commandes exécutées
Liste des commandes + succès/échec (sans dump massif de logs).

## Suite recommandée
- Si NON FONCTIONNEL ou PARTIEL : actions prioritaires (→ **debug**, **check-feature**, **test**)
- Dette non bloquante éventuelle
```

---

## Priorisation

1. **Sûreté** — auth, permissions, données sensibles, calcul paie ;
2. **Parcours principal** annoncé dans le périmètre ;
3. **Câblage** — code mort, route absente, UI non reliée à l'API ;
4. **Régression** — tests existants du module ;
5. Finitions UX non bloquantes.

---

## Règles agent

- Répondre en **français** ; ton factuel, pas de « je pense que » sans preuve.
- **Transparence** : distinguer « code présent » et « comportement validé ».
- **Portée** : ne pas élargir la vérif au-delà du périmètre identifié.
- **Ne pas** remplacer une recette exhaustive produit (→ **test-complet**).
- **Ne pas** réécrire la feature pour la compléter (→ **check-feature**) sauf correctif minimal bloquant la preuve.

---

## Exemples

> `/is-fonctionnel` — on vient d'implémenter le salaire différé sur la fiche employé.

1. Périmètre : création/édition salaire différé + impact paie du mois.
2. Checklist V01–V08 (API, UI drawer, validation dates, bulletin).
3. pytest ciblé + lint + build ; lecture câblage router ↔ frontend.
4. Verdict **PARTIEL** si UI OK mais un cas limite non testé — preuves tabulées.

> `/is-fonctionnel`

Sans autre texte : inférer du diff Git + conversation, lister hypothèses, exécuter preuves, verdict.

---

## Skills voisins

| Besoin | Skill |
|--------|-------|
| Compléter / corriger vs prompt d'origine | **check-feature** |
| Matrice exhaustive 15–40+ scénarios | **test-complet** |
| Ajouter tests pytest CI | **test** |
| Corriger une erreur constatée | **debug** |
| Une phrase récap | **resume** |
