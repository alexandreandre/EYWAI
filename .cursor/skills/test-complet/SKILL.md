---
name: test-complet
description: Élabore une matrice exhaustive de scénarios pour une page ou une fonctionnalité, les exécute un par un (code, API, pytest, navigateur si disponible), puis produit un compte rendu structuré en français. À utiliser lorsque l'utilisateur tape /test-complet, demande un test exhaustif, une recette complète, ou une couverture de tous les cas possibles d'un écran ou d'un flux.
---

# Test complet (`/test-complet`)

## Objectif

Pour une **page** ou une **fonctionnalité** nommée par l'utilisateur :

1. **Inventorier** tous les scénarios possibles et imaginables (pas seulement le happy path).
2. Les **tester un par un**, dans l'ordre, sans sauter d'étape.
3. Produire un **compte rendu** final avec statuts, preuves et actions restantes.

Ce skill **ne remplace pas** `/test` (écriture de tests pytest) ni `/check-feature` (conformité à un prompt d'origine) : il **explore et valide** de façon exhaustive ; en cas de trou, mentionner l'ajout de tests automatisés via le skill **test**.

---

## Entrée utilisateur

Invocation typique :

> `/test-complet` Badgeuse — page employé  
> ou  
> `/test-complet` Création d'une absence (tous rôles)

Si le périmètre est flou : **une seule** question courte (page exacte, rôles, environnement dev déjà lancé ou non). Sinon, déduire du contexte (fichiers ouverts, branche, conversation) et documenter les hypothèses dans le rapport.

---

## Workflow obligatoire

### 1. Cadrer le périmètre

- Reformuler en une phrase : **quoi** (page / feature / flux) et **pour qui** (rôles).
- Lister les **comportements attendus** visibles (actions, données affichées, messages).
- Noter les **dépendances** : auth, company, API, migrations, feature flags.

### 2. Cartographier le code

| Zone | Où chercher (EYWAI) |
|------|---------------------|
| Page / UI | `frontend/src/pages/`, composants, routes dans `App.tsx` / `lazyPages.ts` |
| API client | `frontend/src/api/`, hooks `frontend/src/hooks/` |
| Backend | `backend/app/modules/<module>/` — router, service, domain |
| Tests existants | `backend/tests/unit/<module>/`, `integration/<module>/` |
| Auth / rôles | `AuthContext`, guards, constantes rôles |

Produire une **carte courte** (routes, endpoints, fichiers clés) — base pour les scénarios.

### 3. Générer la matrice de scénarios (exhaustive)

Construire une liste **numérotée** `S01`, `S02`, … en croisant au minimum les dimensions ci-dessous. Pour chaque scénario : **titre court**, **préconditions**, **actions**, **résultat attendu**, **méthode de test** prévue (`code` | `pytest` | `api` | `navigateur` | `manuel`).

**Dimensions à couvrir** (adapter au périmètre ; omettre seulement si manifestement hors scope) :

| Dimension | Exemples de scénarios |
|-----------|------------------------|
| Rôles & permissions | admin, manager, employé, non connecté, mauvais company |
| Happy path | parcours nominal complet de bout en bout |
| Chemins alternatifs | annulation, retour arrière, brouillon, édition après création |
| Validation & erreurs | champs vides, formats invalides, doublons, conflits métier |
| États UI | vide, chargement, erreur réseau, timeout, retry |
| Données limites | 0, 1, max, null, fuseaux dates, mois chevauchants |
| Liste / filtres | tri, recherche, pagination, filtre actif vide |
| CRUD | create → read → update → delete (ou équivalent métier) |
| Idempotence / double action | double clic, double soumission, refresh pendant requête |
| Navigation | URL directe, refresh F5, lien sidebar, historique navigateur |
| Cohérence données | affichage = réponse API ; invalidation cache React Query si utilisé |
| Messages produit | textes en **français**, toasts, erreurs 4xx/5xx compréhensibles |
| Sécurité | accès sans token, ID d'une autre company, élévation de rôle |
| Régression adjacente | écrans liés (menu, dashboard) après action principale |
| Accessibilité | focus clavier, labels, boutons désactivés cohérents |
| Responsive | viewport étroit si la page est critique mobile |
| Backend isolé | règles domain/service via pytest ciblé si logique critique |

Viser **au moins 15 scénarios** pour une page simple, **25+** pour un flux métier riche. Ajouter des scénarios **spécifiques au domaine** découverts à l'étape 2 (edge cases métier RH : paie, absences, badgeuse, etc.).

Afficher la matrice complète à l'utilisateur **avant** l'exécution (tableau ou liste numérotée).

### 4. Exécuter scénario par scénario

Règles :

- Traiter **un scénario à la fois** ; mettre à jour son statut avant de passer au suivant.
- **Ne pas abandonner** au premier échec : noter, continuer, corriger seulement si bloquant pour la suite ou si l'utilisateur l'a demandé implicitement (bug évident).
- Prioriser les méthodes **automatisées** quand elles existent ; compléter par inspection code ou parcours navigateur.

**Ordre de tentative par scénario :**

1. **pytest** — depuis `backend/` :
   ```bash
   python -m pytest tests/unit/<module>/ -v --tb=short -k "<mot-clé>"
   python -m pytest tests/integration/<module>/ -v --tb=short
   ```
   Alignement CI : `python -m pytest tests/ -m "not e2e" -v --tb=short` si besoin global.

2. **API** — `TestClient` mental ou requête documentée ; vérifier status, corps, headers auth.

3. **Frontend build/lint** — depuis `frontend/` si le scénario touche compilation ou types :
   ```bash
   npm run lint
   npm run build
   ```

4. **Navigateur** — si un agent navigateur ou dev server (`npm run dev`) est disponible : parcourir le flux ; sinon marquer **MANUEL** avec étapes précises.

5. **Code seul** — si aucune exécution possible : tracer le chemin dans le code ; statut **VÉRIFIÉ (code)** avec fichiers cités.

**Statuts par scénario :**

| Statut | Signification |
|--------|----------------|
| **OK** | Comportement conforme au attendu |
| **ÉCHEC** | Non conforme ou erreur reproductible |
| **PARTIEL** | Fonctionne avec réserves (UX, message, cas limite) |
| **NON TESTÉ** | Impossible sans env / secret / donnée — étapes manuelles fournies |
| **VÉRIFIÉ (code)** | Logique présente en lecture seule, pas exécutée |

### 5. Compte rendu final (en français)

Utiliser ce gabarit :

```markdown
# Compte rendu — Test complet : [nom du périmètre]

## Synthèse
- Scénarios : X total — OK : n | ÉCHEC : n | PARTIEL : n | NON TESTÉ : n | VÉRIFIÉ (code) : n
- Verdict : [Prêt / Prêt avec réserves / Non prêt]
- Environnement : [dev local, branche, serveurs lancés ou non]

## Matrice exécutée
| ID | Scénario | Statut | Preuve / note |
|----|----------|--------|---------------|
| S01 | … | OK | pytest … / capture / fichier:ligne |

## Échecs et écarts (détail)
Pour chaque ÉCHEC / PARTIEL : symptôme, étapes, cause probable, fichier(s).

## Scénarios non testés / manuels
Liste avec procédure pas à pas pour validation humaine.

## Recommandations
- Correctifs prioritaires (sécurité, blocant métier)
- Tests automatisés à ajouter (skill **test**)
- Dette UX / accessibilité non bloquante
```

---

## Règles pour l'agent

- Répondre et rédiger le rapport en **français**.
- **Transparence** : chaque statut OK doit avoir une **preuve** (commande, sortie, fichier, observation).
- **Portée** : ne pas refactorer hors périmètre ; corriger uniquement un bug **bloquant** découvert en cours de test (le mentionner dans le rapport).
- **Concurrence** : ne pas paralléliser les scénarios utilisateur-facing dans le rapport — l'utilisateur doit voir la progression **un par un**.
- Si la matrice dépasse ~40 scénarios : regrouper par **lot** (ex. Auth, CRUD, Erreurs) mais garder des IDs uniques et traiter chaque scénario individuellement à l'intérieur du lot.

---

## Exemple

> `/test-complet` Page Dashboard — rôle manager

1. Carte : `Dashboard.tsx`, hooks `useDashboardQueries`, routes API payroll/absences.
2. Matrice S01–S28 (rôles, widgets vides, erreur API, refresh, etc.).
3. Exécution S01 → S28 avec statuts mis à jour.
4. Compte rendu : 24 OK, 2 PARTIEL, 2 MANUEL (seed data manquant).

---

## Ressources

- Conventions pytest : [backend/tests/README.md](../../../backend/tests/README.md)
- Ajout de tests CI : skill **test** (`.cursor/skills/test/SKILL.md`)
- Complétude fonctionnelle vs prompt : skill **check-feature**
