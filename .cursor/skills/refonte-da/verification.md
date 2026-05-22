# Vérification post-refonte DA

Cocher chaque point avant de considérer la refonte terminée. En cas d’échec, corriger dans l’ordre tokens → ui → sweep.

---

## A. Tokens & configuration

- [ ] `:root` et `.dark` dans `frontend/src/index.css` reflètent le brief (toutes les variables listées en phase 1 du skill).
- [ ] Couleurs en HSL nu dans les variables (pas de `hsl()` dans `--primary: …`).
- [ ] `--gradient-*`, `--shadow-*`, `--radius`, transitions alignés sur le brief.
- [ ] `tailwind.config.ts` : mapping cohérent ; nouveaux tokens éventuels exposés.
- [ ] Utilitaires `.hr-*`, `.kpi-card`, `.status-badge-*` n’utilisent plus de couleurs Tailwind fixes (`green-500`, etc.).

---

## B. Primitives UI

- [ ] Tous les fichiers `frontend/src/components/ui/*.tsx` passés (boutons, inputs, cards, tables, dialogs, sidebars, toast, chart, badges…).
- [ ] Variants `cva` / classes : tokens sémantiques, pas de palette nommée sauf exception documentée.
- [ ] APIs inchangées (mêmes `variant`, `size`, structure).

---

## C. Sweep codebase

Exécuter et traiter les résultats :

```bash
rg -n '(from-|to-|bg-|text-|border-|ring-|fill-|stroke-)(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-' frontend/src --glob '!**/node_modules/**'
rg -n '#[0-9a-fA-F]{3,8}|rgb\(|rgba\(' frontend/src --glob '!**/node_modules/**'
```

- [ ] Zéro occurrence non justifiée (lister exceptions dans la synthèse).
- [ ] Fichiers à volume élevé revus : Dashboard, Analytics, EmployeeDetail, super-admin, Employees, paie/simulation.

---

## D. Cohérence visuelle transversale (tokens)

- [ ] **Primary** identique sur CTA, liens actifs, ring focus, sidebar item actif.
- [ ] **Sémantiques** : success / warning / danger cohérents badges, alertes, toasts, statuts.
- [ ] **Muted** : textes secondaires, placeholders, descriptions harmonisés.
- [ ] **Cartes** : même fond/bordure/ombre que le reste (pas un style « îlot » daté).
- [ ] **Mode sombre** : pas de texte illisible ; bordures visibles ; primary pas trop saturé.
- [ ] **Graphiques** : couleurs de séries lisibles sur fond card ; grille discrète.

---

## D-bis. Cohérence inter-composants (uniformité fonctionnelle)

> Règle d’or : **deux éléments qui font la même chose doivent se ressembler partout.**

### Boutons

- [ ] Tous les CTA primaires utilisent `Button variant="default"` (ou équivalent unique) — même couleur, hauteur, radius, typo, hover, focus.
- [ ] Tous les boutons secondaires : un seul style (`secondary` ou `outline`, choisi une fois pour toutes).
- [ ] Tous les boutons destructifs : `variant="destructive"`, jamais une variante manuelle rouge.
- [ ] Tous les boutons icône : même taille (`size="icon"`), même hit area.
- [ ] **Aucun** `<button>` natif stylé à la main qui contourne `components/ui/button.tsx` (vérif `rg`).
- [ ] Ordre des actions dans les modales identique partout (annuler à gauche / valider à droite, ou convention inverse appliquée à 100%).

### Inputs / formulaires

- [ ] Tous les champs texte / select / textarea passent par les primitives `ui/input`, `ui/select`, `ui/textarea`.
- [ ] Même hauteur, padding, bordure, focus ring, état erreur.
- [ ] Labels, helper text, messages d’erreur stylés de la même façon partout.
- [ ] **Aucun** `<input>` ou `<select>` natif stylé hors primitive.

### Statuts / badges

- [ ] Un badge succès est **toujours** la même teinte, même radius, même typo (jamais `green-500` ici, `success` ailleurs).
- [ ] Mapping cohérent : statut métier → variant unique (ex. « validé » = success, « en attente » = warning, « refusé » = danger), sur **toutes** les pages où ce statut apparaît.
- [ ] `components/ui/status-badge.tsx`, `AnnualReviewBadge`, `PromotionBadge`, `CSEBadge`, `ResidencePermitBadge` partagent les mêmes paires couleur/sévérité.

### Cards / panneaux / tableaux

- [ ] Toutes les KPI cards : même hauteur, padding, ombre, radius.
- [ ] Toutes les cards de contenu : même fond/bordure/ombre.
- [ ] Tableaux : même header (typo, hauteur, couleur), même comportement hover row, même pagination/footer.
- [ ] Listes vides / loading / erreur : même structure et tonalité partout.

### Modales / dialogs / sheets / toasts

- [ ] Même padding, header, séparateur, footer d’actions.
- [ ] Tailles (`sm | default | lg`) cohérentes entre dialogs analogues.
- [ ] Toasts : même position, même icône par sévérité, même durée par défaut.

### Tabs et navigation interne

- [ ] Indicateur d’onglet actif identique sur toutes les pages à onglets (couleur, soulignement, fond).
- [ ] Sidebar admin / employé / super-admin : item actif, hover, focus identiques.
- [ ] Breadcrumb (si présent) avec même séparateur et même typo partout.

### Gabarits de page

- [ ] Pages liste (Employees, Recruitment, Promotions, Formations…) : même header (titre + actions), même barre de filtres, même pagination.
- [ ] Pages détail (employé, formation, annual review…) : même style d’onglets, mêmes paddings, même bandeau d’en-tête.
- [ ] Pages dashboard / analytics : même grille de cards, mêmes ratios.

### Sweep de cohérence (commandes)

```bash
rg -n '<button[^>]*className=' frontend/src --glob '!**/ui/**'
rg -n '<input[^>]*className=' frontend/src --glob '!**/ui/**'
rg -n 'rounded-full[^"]*(bg-|text-)' frontend/src --glob '!**/ui/**'
```

- [ ] Chaque résultat est justifié, sinon migré vers la primitive correspondante.

---

## E. UX & périmètre (non-régression)

- [ ] Aucun déplacement de section, suppression de champ, changement de libellé involontaire.
- [ ] Navigation et routes inchangées.
- [ ] Focus clavier toujours visible (`focus-visible` / `ring`).
- [ ] États hover/active/disabled toujours présents là où ils existaient.

---

## F. Qualité technique

- [ ] `npm run lint` OK dans `frontend/`.
- [ ] Build ou `npm run build` si demandé ou en fin de grosse session.
- [ ] Pas de fichier `.env` ou secret modifié.

---

## G. Parcours visuel rapide (manuel)

Ouvrir en local et valider **apparence uniquement** :

| Écran | OK |
|-------|-----|
| Login / auth | [ ] |
| Dashboard RH | [ ] |
| Liste employés | [ ] |
| Fiche employé (onglets) | [ ] |
| Sidebar + header | [ ] |
| Modal / dialog / sheet | [ ] |
| Toast succès & erreur | [ ] |
| Analytics ou graphique | [ ] |
| Mode sombre (si applicable) | [ ] |

### Test de cohérence côte à côte

Ouvrir **deux pages similaires** dans deux fenêtres et comparer :

| Comparaison | Boutons | Cards | Tableaux | Modales | Statuts |
|-------------|---------|-------|----------|---------|---------|
| `Employees` vs `Recruitment` | [ ] | [ ] | [ ] | [ ] | [ ] |
| `Promotions` vs `AnnualReviews` | [ ] | [ ] | [ ] | [ ] | [ ] |
| `Dashboard` (RH) vs `Dashboard` (employé) | [ ] | [ ] | — | [ ] | [ ] |
| Sidebar admin vs sidebar employé | [ ] | — | — | — | — |

Si une différence n’est **pas** justifiée par une différence de fonction, **uniformiser**.

---

## Synthèse à renvoyer à l’utilisateur

- Brief rappelé en une phrase.
- Tokens modifiés (fichier principal).
- Nombre de fichiers sweep + exceptions.
- Checklist : X/Y sections OK.
- Points restants éventuels.
