# Sélection en masse des calendriers — dissolution du popover « à saisir »

**Date** : 2026-08-29 · **Statut** : validé (carte blanche Alexandre après revue produit)

## Problème

Sur la page Calendriers RH, le popover « 6 à saisir » cumule trois métiers
(indicateur d'état, outil de sélection, lanceur d'actions) et crée un second
système de sélection parallèle au tableau. Deux entrées IA coexistent avec des
périmètres différents. La barre d'actions en masse — la bonne — n'est
accessible que par ce tunnel, et la vue Planning (par défaut) n'a aucune
sélection alors que la vue Liste en a déjà une.

## Principe

**La sélection vit dans le tableau, les actions suivent la sélection.**

## Décisions

1. **« À saisir (n) » devient un filtre d'état** : un bouton-chip dans la
   barre de filtres qui bascule le `saisieFilter` existant
   (`'a_saisir'` ⟷ `'all'`). Le Select « Statuts » partage le même état,
   donc reste synchronisé. Le popover `ASaisirActionsMenu` disparaît
   (suppression accordée — aucun usage caché confirmé).
2. **Checkboxes dans la vue Planning** (`TeamPlanningView`) : une par ligne
   dans la cellule collaborateur + tout-cocher dans l'en-tête de colonne,
   mêmes props que la vue Liste (`selectedIds`, `onToggleSelect`,
   `onToggleSelectAll`). Le clic sur le nom continue d'ouvrir le calendrier.
3. **La barre d'actions en masse absorbe l'IA** : nouveau bouton
   « Remplir par l'IA (n) » dans `CalendarBulkActionsBar`
   (prop `onFillWithAi(ids)`), aux côtés d'Appliquer modèle / Copier mois /
   Réel = prévu / Badgeuse / Export.
4. **Une seule entrée IA en haut** : le bouton « Remplissage par IA » cible
   la sélection courante s'il y en a une (dialogue en mode ciblé/broadcast),
   sinon comportement actuel (roster complet, consigne libre).

## Hors scope

Backend (aucun besoin), vue Liste (déjà correcte), stats Horaire/Forfait du
popover (disparaissent avec lui — l'info reste accessible via le filtre Mode).

## Validation

eslint + build + suite vitest verts ; vérification visuelle sur le serveur
local (les deux vues, sélection, barre d'actions, deux chemins IA).
