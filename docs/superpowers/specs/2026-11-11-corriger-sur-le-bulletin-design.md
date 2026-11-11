# Corriger sur le bulletin : design

Date : 11/11/2026. Branche : `feat/corriger-sur-le-bulletin` (depuis `feat/elsa-10-11`).
Maquettes validées par Alexandre : disposition A3, ajout et retrait de lignes (compagnon visuel du 11/11).

## 1. Problème

À la réunion de Lyon (10/11), l'équipe RH a trouvé la correction à la main « pas évidente, et chiante ». Phrases relevées : « régulariser des heures, je n'arrive pas à trouver », « je veux modifier l'ensemble des lignes du bulletin, il y a un espace dédié ? », « je ne veux pas qu'elle ait le maintien », « ça me saoule ce truc ».

L'onglet « Corriger » de `PayslipEdit.tsx` empile six cartes (heures sup, primes, régularisations d'heures, régularisations de cotisation, « Corriger une ligne », « Ce qui se corrige ailleurs »). Il faut savoir laquelle choisir. Corriger une ligne demande six gestes (liste, champ base, taux ou montant, valeur, motif libre, « Ajouter la correction », puis « Enregistrer et recalculer » en haut de page). Le vocabulaire est celui du moteur (variable, base, taux). Le bulletin se lit dans un autre onglet.

## 2. Objectif et critères de réussite

L'équipe corrige un bulletin en regardant le bulletin, guidée à chaque pas, sans réfléchir au mécanisme.

- Corriger le montant d'une ligne : 3 gestes (crayon, valeur, Appliquer), le motif proposé en un clic.
- Ajouter une ligne : un bouton, une tuile, deux champs au plus, Appliquer.
- Retirer une ligne : la poubelle, un motif en un clic, Appliquer ; la ligne reste visible, barrée, avec « Remettre ».
- Aucun terme de moteur à l'écran : pas de « variable », « base », « mode ».
- **Aucun calcul ne change** : les corrections restent des variables du mois, le bulletin est recalculé en entier comme aujourd'hui (théorème de la correction à la main). Le filet avant/après doit rester à 0 écart.

## 3. Ce qui est décidé

### 3.1 Disposition (A3)

L'onglet « Corriger » devient le bulletin lui-même, ligne par ligne, groupé par blocs (Rémunération, Sur le net, Cotisations repliées, Impôt, Net à payer).

- En haut, un **bandeau d'étapes** : « 1. Cliquez la ligne fausse, ou Ajouter une ligne », « 2. Remplissez », « 3. Appliquez ». L'étape en cours est en bleu, les étapes faites en vert.
- Au bout de chaque ligne : **✎** (corriger) et, si la ligne est retirable, **🗑**.
- En bas, collée à l'écran, une **barre de correction** : nombre de changements en attente et bouton unique **Appliquer**.
- Les cartes actuelles disparaissent de l'onglet. « Ce qui se corrige ailleurs » devient un lien sous chaque ligne concernée.

### 3.2 Corriger une ligne

Clic sur ✎ : la ligne s'ouvre en place.

- « Martine : 58,20 € · le bon montant : [ ] ». Pour une ligne en heures, on demande le nombre d'heures ; pour une ligne avec un taux, le champ proposé est celui que la règle 3 du théorème autorise, avec son unité. Si la base et le taux sont tous deux permis, la base est proposée et un lien discret « corriger le taux plutôt » bascule.
- Le nouveau montant de la ligne s'affiche aussitôt (« 58,20 € → 63,00 € »), calculé comme aujourd'hui par `apercuDuMontant`.
- **Motif en puces** : « Correction d’une erreur de calcul », « Correction d’une erreur de saisie », « Rappel d’un mois précédent », « Ligne non due ce mois-ci », « Autre… » (champ libre). Le motif reste obligatoire pour le serveur ; une puce le remplit. Le motif est imprimé sur le bulletin du salarié : aucune puce ne parle de Quadra.
- ✕ annule la correction en attente.
- Une ligne déjà corrigée l'affiche (« corrigée : motif ») avec « Remettre la valeur de Martine ».
- Une ligne non corrigeable (raison donnée par le serveur) n'a pas de ✎ : à la place, sa raison et le lien vers sa source.

### 3.3 Retirer une ligne

- 🗑 sur : une prime saisie du mois, une ligne ajoutée, une ligne calculée dont la règle 3 permet le montant (ex. maintien de salaire, retiré par une correction à 0 €).
- La ligne reste affichée, barrée sur fond rouge pâle, étiquette « Retirée », motif, bouton « Remettre ».
- Pas de 🗑 sur une ligne qui vient de la fiche ou du planning (salaire de base, absence) : un lien « Vient du planning · ouvrir le 14/10 » ou « Vient de la fiche · ouvrir la fiche ».

### 3.4 Ajouter une ligne

Un gros bouton « ＋ Ajouter une ligne » ouvre quatre tuiles, dans les mots de la RH :

| Tuile | Champs | Ce que Martine fait (existant réutilisé) |
|---|---|---|
| ⏱ Des heures | Quel mois (ce mois-ci, les deux mois passés, autre) ; combien d'heures, en plus ou en moins | Ce mois-ci : heures sup ou complémentaires du mois (logique de la carte actuelle). Mois passé : régularisation d'heures (`RegularisationsHeuresCard`). Martine dit en clair : heures normales ou majorées, taux, montant |
| € Une prime | Liste du catalogue avec recherche, ou prime libre ; montant | `SaisieModal` / `AjouterPrimeBouton`. Prime libre : deux questions en clair (« Soumise aux cotisations ? », « Imposable ? ») avec la valeur par défaut du catalogue |
| ↔ Sur le net | Remboursement ou retenue ; montant ; libellé | Saisie sur le net existante (versement ou retenue) |
| % Une cotisation | Mois, cotisation, montant | `RegularisationsCotisationCard` |

Forfait jours : la tuile « Des heures » est remplacée par la phrase existante `PHRASE_FORFAIT_JOURS_SANS_HEURES_SUP`. Temps partiel : « heures complémentaires » au lieu de « heures sup ».

La nouvelle ligne apparaît dans le bulletin, sur fond vert pâle, étiquette « Nouvelle ».

### 3.5 Appliquer et voir le résultat

Le serveur n'a pas de calcul du bulletin sans écriture, et le moteur écrit en cours de génération (`payslip_generator_provider`, `writer.py`). Un piège à écritures global n'est pas sûr dans un serveur multi-requêtes. Décision :

- Avant Appliquer : chaque ligne touchée montre son montant avant et après ; la barre montre le nombre de changements.
- **Appliquer** = la route actuelle `POST /api/payslips/{id}/edit` (variables du mois puis recalcul complet), environ 6 s, avec un état « Martine recalcule le bulletin… ».
- Après : la barre devient « Net : 2 084,51 € → 2 088,24 € » avec **Annuler**, qui restaure la version d'avant par la route existante `POST /api/payslips/{id}/restore`.
- Refus du recalcul (`recalcul_refus`) : même traitement qu'aujourd'hui (`RegeneratePayslipButton`, refus initial), dit dans la barre.
- Un calcul sans écriture (aperçu du net pendant la saisie) reste une idée pour plus tard, pas dans ce lot.

### 3.6 Notes, verrous, bulletin validé

- Notes du PDF et note interne : section repliée sous le bulletin, inchangée.
- Verrou d'édition et bulletin remis : mêmes règles qu'aujourd'hui (`isEditLocked`) ; ✎, 🗑 et « Ajouter » disparaissent, un bandeau dit pourquoi.
- Corrections en attente non placées (`en_attente`) : bandeau rouge en haut avec « Retirer » ou « Reporter sur une autre ligne », comme aujourd'hui.

## 4. Composants

Nouveau dossier `frontend/src/components/payslip-edit/bulletin-a-corriger/` :

- `BulletinACorriger.tsx` : l'onglet ; lit les lignes, tient l'état, place les blocs, le bandeau et la barre.
- `LigneDuBulletin.tsx` : une ligne, ses états (normale, en édition, corrigée, retirée, nouvelle, à la source).
- `ChampDeLaLigne.tsx` : la valeur voulue, son unité, l'aperçu du montant.
- `MotifEnPuces.tsx` : les puces et « Autre… ».
- `AjouterUneLigne.tsx` : le bouton, les quatre tuiles et leurs formulaires (réutilisent la logique des cartes actuelles).
- `BandeauEtapes.tsx`, `BarreDeCorrection.tsx`.
- Logique pure dans `features/payroll/utils/correctionsBulletin.ts` (existant) : choix du champ proposé, état d'une ligne, texte du motif. Testée en unitaire.

L'état reste `EtatCorrections` ; l'enregistrement reste celui de `PayslipEdit.tsx` (`demanderEnregistrement`). Les anciennes cartes ne sont plus montées dans l'onglet ; elles sont retirées une fois les e2e passés.

Aucun changement serveur. L'origine d'une ligne (fiche, planning, prime, régularisation, calcul) et son retrait se déduisent de son `code` (`codes_des_lignes.py`), dans `bulletinACorriger.ts`.

## 5. Tests et preuves

- Unitaire (vitest) : choix du champ proposé, états de ligne, retrait d'une prime contre correction à 0, motifs.
- Composants (vitest) : corriger une ligne en 3 gestes ; retirer puis remettre ; chaque tuile d'ajout ; forfait jours ; verrou.
- Serveur : test de la réponse enrichie de `lignes-corrigeables` ; test du théorème inchangé.
- e2e sur le site de test : nouveau parcours « corriger, ajouter, retirer, appliquer, annuler » sur un bulletin de test créé puis supprimé ; e2e 06 et 08-mode-paie adaptés.
- Filet avant/après : 0 écart attendu (aucun calcul changé).

## 6. Après l'implémentation : un PDF pour Elsa

Demande d'Alexandre (11/11) : un PDF simple et visuel qui explique la nouveauté à Elsa.

- 2 à 4 pages : le principe en une phrase (« on corrige sur le bulletin »), le schéma des 3 étapes, une capture par geste (corriger, retirer, ajouter avec les 4 tuiles, Appliquer et Annuler).
- Captures prises sur le site de test, sur un bulletin de test supprimé ensuite ; aucun vrai nom ni NIR.
- Hors dépôt, envoi par Alexandre.

## 7. Hors champ

- Tout changement de calcul du moteur.
- L'aperçu du net sans écriture (idée pour plus tard).
- Les autres onglets du bulletin (Bulletin, Historique, Comparaison, Tendance).
