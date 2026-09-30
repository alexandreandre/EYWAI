# Écrans de paie sans piège — conception

Date : 30/09/2026. Statut : proposé à Alexandre, pas encore implémenté.

## Pourquoi

Le 30/09, pendant la paie de septembre de Colorplast, la gestionnaire de paie a cru plusieurs fois qu'une action avait réussi alors qu'elle avait échoué, ou que le logiciel s'était trompé alors qu'il affichait un état périmé. Principe demandé par Alexandre : **aucune action ne doit pouvoir sembler réussie si elle a échoué, et aucun écran ne doit montrer un état périmé sans le dire.**

Tous les faits ci-dessous ont été vérifiés en base de test et dans les journaux du serveur de test.

## 1. Un salarié « enregistré » qui n'existe pas

**Fait.** Aucun salarié créé en base depuis trois jours. Aucune requête de création (`POST /api/employees`) n'a atteint le serveur de test ni la production depuis le 29/09 à 20 h UTC. Le formulaire s'est donc arrêté avant l'envoi, sans que la gestionnaire le comprenne.

**Causes possibles**, sans trancher ; les solutions couvrent les trois :
- Le formulaire laisse le navigateur valider les champs (pas de `noValidate`). Les champs numériques ont un pas imposé : taux personnalisé au pas de 0,1, montants au pas de 0,01. Une valeur hors pas bloque l'envoi, avec au mieux une petite bulle du navigateur.
- Une erreur de saisie est affichée en haut du formulaire, mais la fenêtre est fermée sans que la gestionnaire l'ait vue. La fenêtre se ferme sans avertir que rien n'est enregistré.
- La saisie est incomplète dans un autre onglet.

**Solutions**, dans `frontend/src/features/employees/components/CreateEmployeeForm.tsx` :
1. `noValidate` sur le formulaire, et pas de pas imposé sur les champs numériques. Toute erreur passe par la validation du formulaire, qui l'affiche.
2. **Parcours guidé** :
   - chaque onglet porte une pastille qui compte ses champs à corriger ;
   - en haut, un encadré « Il reste à remplir » liste les informations manquantes, avec un lien vers leur onglet ;
   - le bouton principal dit ce qu'il fera : « Enregistrer le salarié », ou « 2 informations à compléter (onglet Contrat) ».
3. **Pas de fermeture silencieuse** : fermer la fenêtre avec une saisie non enregistrée demande « Ce salarié n'est pas enregistré. Fermer sans enregistrer ? ».
4. **Succès visible** :
   - un écran de confirmation « Salarié X enregistré », qui existe déjà (`NouveauSalarieRecap`), avec ce qu'il reste à faire ;
   - le salarié apparaît en tête de la liste, avec un badge « Nouveau ».
5. **Échec visible** : si le serveur refuse, un bandeau rouge « Salarié NON enregistré » donne la raison. La saisie est conservée et le bouton reste disponible.
6. **Test de bout en bout**, dans le parcours de la gestionnaire (mode paie) :
   - une valeur piège (taux de 1,15 %, salaire au millième) produit une erreur visible et ne bloque pas en silence ;
   - fermer la fenêtre avec une saisie en cours demande confirmation ;
   - une création réussie affiche la confirmation.

## 2. Bulletins qui « ne se mettent pas à jour »

**Faits :**
- Le bouton « Régénérer » recalcule bien le bulletin. Un bulletin régénéré à 19 h 12 donnait exactement les heures sup de son calendrier.
- Deux bulletins avaient été générés AVANT les corrections de calendrier (15 h 58, puis correction à 18 h 42 ; 18 h 55, puis correction à 18 h 57) et n'ont pas été refaits. Rien ne le signalait.
- À 19 h 11, une suppression de bulletin a échoué (erreur 500 « 0 ligne ») : le bulletin avait déjà été supprimé. À 19 h 13, l'écran a tenté d'ouvrir un bulletin qui n'existait plus (404). **L'écran affichait des bulletins périmés.** Le cache des données de l'écran est conservé 24 h dans le navigateur (`eywai-rq-cache-v1`).
- Le PDF est réécrit au même chemin de stockage à chaque génération, ce qui expose à un cache du fichier. C'est une piste, non prouvée.

**Solutions :**
1. **Écran toujours à jour.**
   - Après une génération, une régénération ou une suppression, les listes et le bulletin affiché sont rechargés depuis le serveur, en invalidant les requêtes concernées.
   - Les bulletins ne sont plus conservés dans le cache persistant du navigateur.
   - Un bulletin introuvable affiche « Ce bulletin a été remplacé : rechargement », pas une erreur.
2. **Suppression idempotente** : supprimer un bulletin déjà supprimé répond « déjà supprimé » (204), pas 500.
3. **« Bulletin à recalculer »** : un bulletin est marqué périmé quand une donnée qu'il utilise change après sa génération. Sont concernés : le calendrier prévu ou réel des mois de la fenêtre, une absence qui touche ces dates, les saisies du mois et la fiche. On compare les dates de modification avec celle du bulletin.
   - La liste de paie et le bulletin affichent « À recalculer », avec un bouton « Recalculer ».
   - La page de paie du mois propose « Recalculer tout ce qui a changé ».
   - Un bulletin « à recalculer » ne peut pas être validé ; le message dit pourquoi.
4. **Ce qui a changé** : après un recalcul, un message résume les différences, par exemple « Heures sup : 28 h → 6 h ; net : 2 010,40 → 1 842,15 ». Plus besoin de supprimer puis générer pour être sûr.
5. **PDF toujours à jour** : chemin de stockage versionné, ou cache désactivé sur le PDF, pour que le PDF affiché soit celui du dernier calcul.

## 3. Heures pointées pendant un arrêt

**Fait.** Une salariée a un arrêt validé sur tout septembre. Son calendrier réel garde pourtant des heures pointées sur 12 jours (7 au 11, 14 au 17, 28 au 30).
- Le moteur les compare à un prévu de 0 h, puisque la salariée est en arrêt, et en fait des heures sup : 70,75 h à 50 % et 8 h à 25 %, soit 1 526 € de brut en trop.
- Régénérer redonne chaque fois le même résultat.
- Ces heures passent par deux calculs : le calcul normal et la compensation entre semaines. Neutraliser l'un ne suffit pas.

**Solutions :**
1. **Détection** d'un jour « en conflit » : arrêt ou absence non travaillée au prévu, avec des heures saisies au réel. Elle vit dans un module pur partagé par le calendrier, l'import des pointages et la génération.
2. **Correction proposée, en un clic.** Au moment de générer, et dans le calendrier dès la saisie ou l'import, l'écran affiche :
   > « Cette salariée est en arrêt, mais des heures sont saisies les 7, 8, 9… septembre. Que s'est-il passé ? »
   > [Elle était en arrêt : effacer ces heures] (conseillé) · [Elle a travaillé : modifier l'arrêt]
   - Rien ne se corrige sans ce clic. Une fois la correction faite, le bulletin concerné passe « à recalculer » (point 2).
3. **Filet dans le moteur** : même forcée, une heure saisie un jour d'arrêt ne crée jamais d'heure sup, ni dans le calcul normal ni dans la compensation. Elle est écartée, avec une alerte sur le bulletin.
4. **Import des pointages** : une ligne de pointage qui tombe sur un jour d'arrêt est signalée dans le récapitulatif de l'import au lieu d'être écrite en silence.

## 4. Sortie d'un salarié en cours de mois

**Fait.** Un CDD finit le 15/09 sans dossier de départ. La gestionnaire ne savait pas qu'il fallait « sortir » le salarié pour obtenir son bulletin de sortie.

**Solutions :**
1. Un bandeau sur la page de paie du mois : « X quitte l'entreprise le 15/09 : créez son départ avant de générer », avec le bouton « Créer le départ ».
2. Une fois le départ créé, le logiciel propose tout de suite de générer le bulletin de sortie.
3. Les documents de sortie (solde de tout compte, attestation France Travail, certificat) restent grisés tant que le bulletin du mois de sortie n'existe pas, avec la mention « générez d'abord le bulletin de sortie ». Constat de la revue du 29/09.

## 5. Heures sup comparées à son tableau

Après les points 2 et 3, les heures sup des bulletins sont celles des calendriers. S'il reste une différence avec le tableau de la gestionnaire, il faut son tableau de septembre pour la trouver, semaine par semaine.

Rappel : l'option « compensation entre semaines » est active chez Colorplast. Elle a été mesurée comme perdante sur six mois à cause des journées en récupération (voir la mémoire du projet).

## Ordre de réalisation

1. **Heures sur un jour d'arrêt** (point 3) : c'est ce qui bloque un bulletin de septembre.
2. **Écran à jour et « à recalculer »** (point 2).
3. **Création de salarié guidée** (point 1).
4. **Sortie guidée** (point 4).

Pour chaque point : tests unitaires, test de bout en bout du parcours de la gestionnaire (mode paie), filet de paie à zéro écart, puis déploiement sur le site de test avec l'accord d'Alexandre.

Aucune donnée de la base de test n'est modifiée par ces correctifs. Les corrections de données, comme effacer des heures ou raccourcir un arrêt, restent faites par la gestionnaire, avec le nouvel écran.

Ensuite : reprise du chantier de vérification de la réduction générale (tâche 9), puis des corrections de la revue du 29/09.
