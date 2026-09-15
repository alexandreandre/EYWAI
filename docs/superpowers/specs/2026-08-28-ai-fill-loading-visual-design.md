# Visuel de chargement du remplissage IA du calendrier

**Date** : 2026-08-28 · **Statut** : validé (approche A + touche de B, choisie par Alexandre)

## Problème

Pendant l'analyse d'une consigne par l'IA (dialogue « Remplissage par IA », route
`/api/schedules/assisted-fill/parse-text`), le seul retour visuel est le petit
spinner du bouton « Analyser ». L'attente (~10 à 30 s) paraît figée et ennuyante.

Le dialogue d'import de pointages a déjà sa progression (pages, file d'attente,
arrière-plan) : il est hors périmètre, mais le composant créé ici doit pouvoir
y être réutilisé plus tard.

## Décision

Un état d'attente **narratif** remplace la zone de saisie pendant l'analyse :

- icône Sparkles animée (pulsation + halo) ;
- 4 étapes affichées séquentiellement — « Lecture de la consigne… »,
  « Reconnaissance des collaborateurs… », « Construction des horaires… »,
  « Vérification des totaux… » — chacune passe de « en attente » à « en cours »
  puis « faite » selon la progression ;
- barre de progression **asymptotique** : montée rapide au début puis
  ralentissement, plafonnée sous 90 % — elle n'affiche jamais un faux 100 % ;
- touche de B : mini-grille calendrier en skeleton (7 colonnes × 3 lignes) avec
  shimmer décalé, qui suggère le résultat en train de se matérialiser ;
- ligne d'astuce : « Vous pourrez ajuster chaque jour avant d'enregistrer. » ;
- animations neutralisées sous `prefers-reduced-motion` (variantes
  `motion-reduce:` de Tailwind).

## Architecture

| Unité | Rôle |
|---|---|
| `aiFillProgressModel.ts` | Logique pure : `progressAt(elapsedMs, expectedMs)` (courbe asymptotique 0 → <90), `AI_FILL_STEPS` (labels + seuils), `stepStateAt(progress, index)` → `pending / active / done`. Testée par vitest. |
| `AssistedFillProgress.tsx` | Composant de présentation : tick de 200 ms, rend icône, étapes, barre (`ui/progress`), grille skeleton (`ui/skeleton`), astuce. Props : `expectedMs?` (défaut 18 000), `className?`. Aucun appel réseau. |
| `AssistedFillDialog.tsx` | Quand `isAnalyzing`, rend `AssistedFillProgress` à la place de la zone de saisie (le bandeau « Ciblé sur N collaborateurs » disparaît aussi). Arrête la dictée au lancement de l'analyse. |

Aucun changement backend. Échec → toast existant et retour au formulaire ;
succès → écran de revue comme aujourd'hui.

## Tests

- `aiFillProgressModel.test.ts` : progression nulle à t=0, strictement
  croissante, jamais ≥ 90 ; seuils des étapes strictement croissants et < 90 ;
  états `pending/active/done` corrects aux bornes.
- Vérification visuelle : lint + build + suite E2E existante (le dialogue reste
  fonctionnel de bout en bout).
