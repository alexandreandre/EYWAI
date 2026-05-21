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

## D. Cohérence visuelle transversale

- [ ] **Primary** identique sur CTA, liens actifs, ring focus, sidebar item actif.
- [ ] **Sémantiques** : success / warning / danger cohérents badges, alertes, toasts, statuts.
- [ ] **Muted** : textes secondaires, placeholders, descriptions harmonisés.
- [ ] **Cartes** : même fond/bordure/ombre que le reste (pas un style « îlot » daté).
- [ ] **Mode sombre** : pas de texte illisible ; bordures visibles ; primary pas trop saturé.
- [ ] **Graphiques** : couleurs de séries lisibles sur fond card ; grille discrète.

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

---

## Synthèse à renvoyer à l’utilisateur

- Brief rappelé en une phrase.
- Tokens modifiés (fichier principal).
- Nombre de fichiers sweep + exceptions.
- Checklist : X/Y sections OK.
- Points restants éventuels.
