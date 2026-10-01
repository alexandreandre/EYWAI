# Recette du mode paie — écrans sans piège

Document pour Alexandre, à coller tel quel à Claude dans Chrome **après** le déploiement de la branche `fix/payslip-edit-state` sur le site de test.

Rédigé le 1er octobre 2026. **Cette interface n’est pas encore en ligne** au moment où ce texte est écrit. Ne lancez la recette que lorsque le site de test a reçu ce déploiement. Si la page Paie n’affiche pas le bloc « Liste de contrôle » ni le lien « Manuel de la paie », arrêtez-vous : le déploiement n’est pas fait.

## Pré-requis

1. Ouvrir uniquement le **site de test** : `https://sirh-frontend-test-505040845625.europe-west1.run.app`
2. Vérifier le **bandeau orange** en haut de page. S’il n’y en a pas, vous êtes en production : fermez l’onglet, ne cliquez rien.
3. Vous connecter avec le **compte QA**.
4. Dans le sélecteur d’entreprise (haut de la barre latérale), choisir **MAJI** (société de démonstration). Le nom exact peut porter une forme juridique ; il doit contenir MAJI.
5. Rester en **mode paie** (navigation réduite d’une gestionnaire, pas le menu plateforme admin).

## Interdits

- Ne jamais ouvrir **Colorplast** ni **Comitech**.
- Ne jamais recopier un nom réel de salarié, un NIR, un RIB, un bulletin ou un montant de paie réelle dans une capture, un commentaire ou ce document.
- Ne pas écrire en base par un autre moyen que les écrans (pas de SQL, pas d’outil d’admin).
- Ne pas inventer de procédure de contournement si un parcours échoue : noter **KO**, capturer l’écran, passer au parcours suivant quand il est indépendant.
- Ne pas valider ni exporter la paie d’un salarié qui n’est pas celui créé pour cette recette.
- Ne pas déployer, ne pas lancer de workflow GitHub.

## Salarié et mois de la recette

Toutes les saisies portent sur un **salarié inventé**, créé pendant la recette :

| Champ | Valeur |
| --- | --- |
| Prénom | Octavie |
| Nom | Recette |
| Poste | Opératrice recette |
| Date d’entrée | le 1er du **mois M** |
| Type de contrat | CDD |
| Date de fin de contrat | le 15 du **mois M** |
| Salaire de base | 1990,001 € |
| Taux PAS personnalisé | 1,15 % |
| RIB à la création | vide |
| Case « Création de contrat pdf » | **décochée** |

**Mois M** = le mois nommé dans le titre « Liste de contrôle — … » sur `/payroll` (exemple : « Octobre 2026 »). Toutes les dates ci-dessous (7 et 8, le 15, le 21) s’entendent dans ce mois M. Si 7 ou 8 tombent un week-end, prenez les deux premiers jours ouvrés du mois.

Ne nommez jamais un autre salarié de MAJI dans les captures. Si un parcours demande « un bulletin déjà là avant ce déploiement », décrivez-le par son mois et son badge (`Importé`), pas par un nom.

## Comment jouer

Pour chaque parcours : suivez les clics, saisissez exactement les données indiquées, comparez à « Résultat attendu », prenez la capture demandée, puis remplissez la grille en fin de document (`OK`, `KO`, ou `non joué` + une remarque).

Le **2.6** rétablit des jours travaillés après un 2.5 qui a vidé le calendrier. Sans ça, les 3.1, 3.3 et 3.6 n’ont plus de jour à 7 h à passer à 8 h. Si le 2.5 n’a pas touché au calendrier, sautez le 2.6.

---

## 1. Création de salarié

Menu : **Bulletins de paie** (`/payroll`). Bouton en haut à droite : **Nouveau Collaborateur**. Fenêtre : titre « Nouveau Collaborateur ». Onglets : Collaborateur, Contrat, Rémunération, Avantages, Spécificités.

### 1.1 Valeur piège — le formulaire dit l’erreur, il n’échoue pas en silence

1. Ouvrir **Nouveau Collaborateur**.
2. Onglet **Collaborateur** : Prénom `Octavie`, Nom `X` (une lettre).
3. Onglet **Contrat** : Date d’entrée = 1er du mois M ; Intitulé du poste = `Opératrice recette`.
4. Onglet **Rémunération** : Salaire de base mensuel = `1990.001` (millième).
5. Onglet **Spécificités** : cocher « Appliquer un taux personnalisé », Taux personnalisé (%) = `1.15`.
6. Laisser l’IBAN vide. Décocher « Création de contrat pdf ».
7. Cliquer le bouton du bas (il peut dire « Enregistrer le salarié » ou « N informations à compléter (onglet …) »).

**Résultat attendu**

- Une requête de création **ne part pas** tant que le nom a une lettre.
- Encadré ambre « **Il reste à remplir** » (`creation-salarie-reste`), avec un lien vers le nom (onglet Collaborateur). Pastille chiffrée sur l’onglet Collaborateur.
- Le bouton dit combien d’informations manquent, par exemple « 1 information à compléter (onglet Collaborateur) ».
- **Aucun** bandeau seul du type « Une erreur est survenue ».
- Le millième et le 1,15 % **ne bloquent plus** l’envoi : une fois le nom corrigé au parcours 1.3, l’enregistrement part.

**Capture** : fenêtre entière, encadré « Il reste à remplir », pastille, texte du bouton. Pas le toast générique seul.

### 1.2 Fermeture avec une saisie non enregistrée

Toujours dans la même fenêtre, saisie commencée (parcours 1.1).

1. Appuyer sur **Échap**, ou cliquer hors de la fenêtre / sur la croix.

**Résultat attendu**

- Dialogue « **Salarié non enregistré** ».
- Texte exact : « Ce salarié n'est pas enregistré. Fermer sans enregistrer ? »
- Deux actions : **Continuer la saisie** et **Fermer sans enregistrer**.
- Cliquer **Continuer la saisie** : la fenêtre de création reste ouverte, les champs déjà saisis sont encore là.

**Capture** : le dialogue de confirmation, puis la fenêtre encore ouverte.

### 1.3 Création sans RIB — succès visible

Toujours dans la même fenêtre.

1. Onglet **Collaborateur** : Nom = `Recette` (au moins deux lettres). IBAN toujours vide.
2. Onglet **Contrat** : type **CDD** ; Date de fin de contrat (CDD / stage) = le **15** du mois M.
3. Vérifier que « Création de contrat pdf » est décochée.
4. Cliquer **Enregistrer le salarié**.

**Résultat attendu**

- Une requête part (plus d’échec silencieux).
- Écran de confirmation « **Fiche créée : Octavie Recette** » (`recap-nouveau-salarie`).
- Dans « À compléter avant sa première paie », la liste contient les **coordonnées bancaires (RIB)** (libellé du récap, pas encore le badge).
- Fermer le récap. Sur la page Paie, **Par collaborateur**, Octavie Recette est **en tête** de liste.
- Badge vert **Nouveau** (session courante, 24 h).
- Mention ambre **RIB à compléter** (c’est le texte réel de la liste).
- La ligne de paie du mois peut afficher « Fiche à compléter : … Coordonnées bancaires (RIB) » : la génération reste bloquée tant que le RIB manque. C’est voulu.

**Capture** : récap nommé ; liste Paie avec badge **Nouveau** et **RIB à compléter**.

### 1.4 Entrée après la clôture des variables

Seulement si la fenêtre des variables du mois M se termine **le 20 ou avant**. Sinon : `non joué`, remarque « fenêtre plus tardive que le 20 ».

1. **Nouveau Collaborateur** une deuxième fois.
2. Prénom `Nestor`, Nom `Recette`, poste `Opérateur recette`, entrée le **21** du mois M, CDI, salaire `2000`, sans RIB, sans contrat PDF.
3. Enregistrer, puis **Compléter la fiche** avec une identité inventée (NIR, naissance, adresse, IBAN fictif accepté par le formulaire). Ne copiez aucun RIB réel.
4. Poser un calendrier à partir du 21 (jours travaillés après l’entrée seulement).
5. Générer le bulletin du mois M.

**Résultat attendu**

- La fiche s’enregistre.
- La génération **n’exige pas** de pointage pour les jours **avant** l’entrée.
- Le bulletin paie le salaire au prorata du 21 à la fin du mois, sans variables de la période close. Pas de refus « calendrier incomplet » pour les jours hors contrat.

**Capture** : bulletin (onglet Bulletin) avec la période d’emploi ; pas de refus pour les jours 1 à 20.

---

## 2. Heures saisies un jour d’arrêt

Préparer Octavie Recette pour la génération :

1. Ouvrir sa fiche (**Ouvrir la fiche** au récap, ou Collaborateurs).
2. **Compléter la fiche** : NIR, date et lieu de naissance, adresse, **IBAN inventé** que le formulaire accepte. Le badge **RIB à compléter** doit disparaître. Ne copiez aucun RIB réel.
3. Onglet **Calendrier** de la fiche (`/employees/…?tab=calendrier`). Aller sur le **mois M**.
4. Pour le **7** et le **8** du mois M (ou les deux premiers jours ouvrés) :
   - type prévu = **Arrêt maladie** (0 h) ;
   - heures réelles = **7**.
5. Ces arrêts sont saisis **au planning**, pas par une demande dans Congés & absences.
6. Cliquer **Enregistrer**.

Les jours en conflit ont un fond rose, un anneau, et l’info-bulle « **Heures saisies pendant l’arrêt** ».

**Capture** : calendrier du mois M, jours 7 et 8 roses.

### 2.1 Refus à la génération — pas de « Générer quand même »

1. **Bulletins de paie** → onglet **Par mois** → mois M.
2. Sur la ligne Octavie Recette, **Générer** (ou « Générer le bulletin de sortie » si le bandeau de départ est déjà là : d’abord faire 2.1–2.3 **avant** de créer le départ, ou générer depuis **Par collaborateur**).

**Résultat attendu**

- Dialogue titre **« Heures saisies un jour d’arrêt »**.
- Phrase du serveur du type : « Octavie est en arrêt, mais des heures sont saisies les 7 et 8 … » (dates du mois M).
- Liste des jours avec les heures, par exemple « 7 … : 7 h ».
- Deux boutons, du type :
  - « Octavie était en arrêt : **effacer ces heures** »
  - « Octavie a travaillé : **modifier l’arrêt** »
- **Pas** de bouton « Générer quand même ». Le forçage du calendrier incomplet n’apparaît pas ici.
- Rien n’est calculé tant qu’on n’a pas choisi.

**Capture** : dialogue de refus entier, sans bouton de forçage.

### 2.2 Effacer ces heures

1. Dans le même dialogue, cliquer « Octavie était en arrêt : **effacer ces heures** ».

**Résultat attendu**

- Toast « **Heures effacées : 7 et 8 …** » (dates du mois M).
- La génération **repart toute seule**.
- Le bulletin apparaît dans la liste (badge **Généré** ou **Alerte**, pas **Échec**).
- Sur le calendrier, après rechargement (changer de mois puis revenir, ou rouvrir l’onglet Calendrier), le rose a disparu ; réel à 0 h sur ces jours.
- Le bulletin **ne paie pas** d’heures sup nées de ces jours d’arrêt. S’il reste une alerte « Heures saisies pendant l’arrêt, écartées du calcul… », la noter : le filet du moteur a écarté des heures encore présentes ; ce n’est pas un succès silencieux.

**Capture** : toast d’effacement ; ligne de paie après génération ; calendrier sans rose.

### 2.3 Corriger un arrêt saisi au planning — pas d’impasse « modifier l’arrêt »

Remettre le conflit (mêmes 7 et 8, prévu Arrêt maladie, réel 7 h, **Enregistrer**). Générer à nouveau jusqu’au dialogue de refus.

1. Cliquer « Octavie a travaillé : **modifier l’arrêt** ».
2. L’écran **Congés & Absences** (`/leaves?employee=…`) s’ouvre, filtré sur Octavie, onglet Historique, bouton **Afficher tous les salariés**.
3. Lire le bandeau (`bandeau-absences-salarie`). Comme l’arrêt a été saisi au planning, le texte attendu est :

   « Aucune demande d’absence enregistrée pour ce salarié : l’arrêt a été saisi au planning. Corrigez-le dans le calendrier du salarié. »

   (S’il y a d’autres demandes : « Demandes d’absence de ce salarié. Si l’arrêt à corriger n’apparaît pas ici, il a été saisi au planning : corrigez-le dans le calendrier du salarié. »)

4. Le bandeau **ne promet pas** que l’arrêt est dans la liste.
5. Cliquer **Ouvrir le calendrier du salarié** (pas rester bloqué sur Absences).
6. Fiche, onglet **Calendrier**, mois M (reculer d’un mois si le calendrier ouvre le mois civil courant).
7. Remettre les 7 et 8 en **Travail** avec les heures voulues, **ou** laisser l’arrêt et passer le réel à 0. **Enregistrer**.
8. Retour Paie, générer : plus de refus pour ces jours.

**Résultat attendu** : le bouton « modifier l’arrêt » n’est pas une impasse. Le bandeau envoie au calendrier. Après correction au calendrier, la génération passe.

**Capture** : bandeau Absences + lien calendrier ; calendrier après correction ; génération sans ce refus.

### 2.4 Import de pointages (seulement s’il existe un fichier MAJI)

Menu **Calendrier** (`/schedules`) → **Importer des pointages**. Uniquement un fichier de **démonstration MAJI**. Pas de fichier Colorplast ni Comitech. S’il n’y en a pas : `non joué`.

1. Importer un relevé qui pose des heures un jour d’arrêt d’Octavie (ou d’un autre salarié **inventé** de cette recette).
2. Enregistrer l’import.

**Résultat attendu**

- L’import n’est **pas** bloqué.
- Récapitulatif rose « **Heures sur un jour d’arrêt ou d’absence** » (`recap-conflits-arret`), jours listés, lien **Ouvrir le calendrier** vers la fiche, onglet Calendrier (pas `/schedules?employee=` qui ne cible personne).

**Capture** : récapitulatif d’import.

### 2.5 Mois entier d’arrêt, net négatif

**Avant d’écraser le calendrier.** Ouvrir le bulletin déjà généré (après 2.2). S’il n’y a **aucune** ligne de mutuelle ni de forfait santé, le net d’un mois d’arrêt ne sera pas négatif : marquer **2.5 `non joué`**, **ne pas modifier le calendrier**, passer au 2.6 (qui se saute) puis au lot 3. Ne pas aller chercher un bulletin ailleurs.

Seulement si cette ligne existe, qu’Octavie (entrée le 1er) peut être en arrêt **tous les jours ouvrés** du mois M, sans maintien, et que la génération n’est plus refusée (heures de conflit à 0) :

1. Calendrier : tous les jours ouvrés du mois M en **Arrêt maladie**, réel 0. Enregistrer.
2. Générer le bulletin du mois M.
3. Lire le net sur la ligne et dans l’onglet Bulletin / PDF.

**Résultat attendu**

- Le net **peut être négatif**. Il n’est pas ramené à 0. Badge **Alerte** (pas un vert « Généré » qui cacherait le problème).
- Message du type : « Net à payer négatif : … €. Rien ne sera viré en … Reprenez cette somme en … »
- Bouton du type « **Reporter … € sur** {mois suivant} ». Après clic : « Reporté sur … » (saisie « Report NAP négatif MM/AAAA »).
- Ne copiez pas un montant d’une autre société. Notez seulement le signe et le libellé.

Si, **après** génération, le net n’est pas négatif : **2.5 `non joué`** (pas `OK`). Enchaîner **quand même** le 2.6 : le calendrier ne doit pas rester vidé.

**Capture** : ligne de paie (badge Alerte, net, bouton de report si présent). Si `non joué` sans avoir touché au calendrier : pas de capture de calendrier vidé.

### 2.6 Rétablir des jours travaillés avant le lot 3

Les 3.1, 3.3 et 3.6 ont besoin d’un jour **travaillé** à 7 h, à passer à 8 h. Un mois entier d’arrêt (2.5) ne laisse plus ce jour. Remettre des heures sur un arrêt relancerait le refus du 2.1, pas le toast « Bulletin recalculé ».

**Si le 2.5 n’a pas modifié le calendrier** (`non joué` avant écrasement) : ne rien faire ici, passer au 3.1.

**Si le 2.5 a mis les jours ouvrés en arrêt** (net négatif ou non) :

1. Fiche → **Calendrier** → mois M.
2. Chaque jour ouvré du 1er au 15 du mois M (bornes du CDD) : type prévu **Travail**, réel **7 h**. Enregistrer.
3. Retour **Bulletins de paie**, mois M : **Recalculer** (ou **Générer** s’il n’y a plus de bulletin). Le bulletin doit correspondre à ces jours travaillés avant d’enchaîner le 3.1.

**Résultat attendu** : au moins un jour ouvré en Travail à 7 h ; plus de refus « heures saisies un jour d’arrêt » ; un bulletin du mois M à jour.

**Capture** : calendrier du mois M avec des jours travaillés à 7 h.

---

## 3. Bulletin à jour, suppression, PDF

### 3.1 « À recalculer » — seul `a_recalculer` vrai bloque

1. Avoir un bulletin **généré** pour Octavie, mois M, avec des jours **travaillés** (après 2.6, ou après 2.2 si le 2.5 n’a pas touché au calendrier).
2. Fiche → **Calendrier** → mois M : changer les heures réelles d’**un jour travaillé** (par exemple 7 h → 8 h). **Enregistrer**. Ne pas régénérer tout de suite.
3. Retour **Bulletins de paie**, mois M (recharger la page si besoin).

**Résultat attendu**

- Badge **À recalculer** sur la ligne (`badge-a-recalculer`).
- Bouton **Recalculer** sur la ligne.
- En tête de l’onglet **Par mois** (et/ou **Par collaborateur** si d’autres bulletins du même salarié sont périmés) : **Recalculer tout ce qui a changé (n)**.
- Ouvrir **Modifier** : bandeau « **À recalculer** » avec le texte exact  
  « Le calendrier ou les absences ont changé depuis le calcul : recalculez avant de valider ».
- **Valider le bulletin** est inactif ; le survol reprend ce message.

**Capture** : liste avec badge et boutons ; écran de correction, bouton Valider grisé.

### 3.2 Un bulletin ancien sans empreinte n’est pas périmé

1. Sur MAJI seulement, trouver un bulletin déjà présent **avant** ce déploiement : badge **Importé**, ou bulletin d’un mois antérieur jamais recalculé depuis l’empreinte.
2. Ne pas le nommer. S’il n’y en a pas sur MAJI : `non joué`.

**Résultat attendu**

- **Pas** de badge « À recalculer » pour ce seul motif.
- La validation **n’est pas** bloquée par le message du 3.1 (`a_recalculer` vide ou `null` n’est pas « périmé »).
- Un badge **Importé** peut griser Modifier / Supprimer pour une autre raison : le noter, ce n’est pas le filet « à recalculer ».

**Capture** : ligne sans badge « À recalculer ».

### 3.3 Recalculer — l’écran dit ce qui a changé

1. Sur Octavie, mois M, cliquer **Recalculer** (ou **Recalculer tout ce qui a changé (n)**).

**Résultat attendu**

- Toast « **Bulletin recalculé** » avec  
  `Heures sup. … → … · Brut … → … · Net … → …`  
  **ou** « recalculé, comparaison indisponible » si un montant manque.
- Le badge **À recalculer** disparaît.
- Ne pas inventer les chiffres du toast : recopier uniquement ce que l’écran affiche, sur Octavie.

**Capture** : toast + ligne sans badge périmé.

### 3.4 Suppression puis relance — déjà supprimé n’est pas une erreur

1. Sur la ligne du bulletin d’Octavie, mois M : icône poubelle → « **Supprimer ce bulletin ?** » → **Supprimer**.
2. Toast « **Bulletin supprimé** ». La liste se recharge ; la ligne repasse à **À générer**.
3. **Deux onglets** du navigateur, même ligne. Dans le premier, supprimer. Dans le second, supprimer à nouveau le même bulletin.

**Résultat attendu**

- Premier onglet : « Bulletin supprimé ».
- Second : « **Bulletin déjà supprimé** » — « Il avait été supprimé depuis un autre écran ou un autre onglet. Rien à refaire : la liste est rechargée. »
- **Pas** d’erreur 500, **pas** « Une erreur est survenue ».
- **Générer** à nouveau : un bulletin réapparaît.

**Capture** : toast « déjà supprimé » ; liste après relance.

### 3.5 Bulletin remplacé

1. Générer le bulletin d’Octavie, mois M. Ouvrir **Modifier** (URL `/payslips/{id}/edit`).
2. Noter l’URL.
3. Revenir à la liste, **supprimer**, **générer** à nouveau (nouvel identifiant).
4. Coller l’**ancienne** URL dans la barre d’adresse.

**Résultat attendu**

- Message « **Ce bulletin a été remplacé : rechargement…** »
- Retour à la liste Paie du salarié et du mois (`/payroll?employee=…&month=AAAA-MM`), liste à jour.
- Une coupure réseau à l’ouverture doit dire « **Bulletin non chargé** » + Réessayer, **pas** « remplacé ».

**Capture** : message « remplacé », puis la liste.

### 3.6 PDF à jour

1. Ouvrir le bulletin d’Octavie, onglet **Bulletin** (aperçu) et **Visualiser le bulletin** / **Télécharger**.
2. Noter un chiffre visible (net, ou une ligne d’heures).
3. Changer encore une heure au calendrier, **Recalculer** (ou **Régénérer** sur l’écran de correction).
4. Rouvrir tout de suite Visualiser / Télécharger, sans attendre.

**Résultat attendu**

- Le PDF montre le **dernier** calcul, pas l’ancien.
- Le fichier téléchargé s’appelle du type `Bulletin_…_MM-AAAA.pdf`, **sans** horodatage dans le nom.
- L’aperçu de l’onglet Bulletin change après le recalcul (il se refait au rechargement du bulletin).

**Capture** : aperçu ou PDF après recalcul, à côté du net affiché à l’écran.

### 3.7 Listes toujours à jour

1. Générer ou supprimer un bulletin d’Octavie.
2. Recharger la page Paie (F5).

**Résultat attendu** : la liste correspond au serveur, pas à un bulletin disparu rejoué depuis un cache de 24 h. Le premier chargement après déploiement peut être un peu plus lent (nouveau cache navigateur).

**Capture** : liste après F5, cohérente avec l’action.

---

## 4. Sortie d’un salarié

Octavie Recette : CDD qui finit le 15 du mois M, **sans** contrat PDF généré par EYWAI.

### 4.1 Départ possible sans contrat généré par EYWAI

1. **Bulletins de paie** → **Par mois** → mois M.
2. Bandeau ambre : « **Octavie Recette quitte l'entreprise le 15/MM : créez son départ.** » Bouton **Créer le départ**.
3. Sinon : menu **Départs** → **Nouveau départ de collaborateur**.
4. Dans la liste **Employé**, Octavie **apparaît** (plus de liste vide « Aucun collaborateur éligible » pour ce seul motif).
5. La sélectionner.

**Résultat attendu**

- Texte : « **Contrat non présent dans EYWAI (repris de l'ancien logiciel) : le départ se crée quand même** »
- Aide si la liste est vide pour d’**autres** raisons : « Seuls les collaborateurs actifs peuvent faire l'objet d'un départ. Un collaborateur déjà parti, ou dont un départ est déjà en cours, n'apparaît pas ici. »
- Remplir le type (**Fin de CDD**), dernier jour travaillé = 15 du mois M, **Créer le départ**.
- Le départ se crée. Le toast du dialogue peut encore dire « Succès » ; la confirmation métier est le bandeau suivant.

**Capture** : liste avec Octavie ; mention contrat absent ; bandeau après création.

### 4.2 Bulletin de sortie, puis documents grisés

Après 4.1, toujours **Par mois**, mois M.

1. Bandeau : « **Départ de Octavie Recette créé : générez son bulletin de sortie.** » Bouton **Générer le bulletin de sortie**.
2. Si la fiche bloque encore : le bouton est **remplacé** par la raison (« Fiche à compléter : … »), **sans** clic silencieux.
3. Générer (régler d’abord un refus d’heures sur arrêt, parcours 2, s’il revient).
4. Menu **Départs**, dossier d’Octavie, onglet **Documents**.

**Résultat attendu — avant le bulletin de sortie**

- Bouton **Générer un document** **grisé**.
- Mention exacte : « **Générez d'abord le bulletin de sortie** ».

**Résultat attendu — après le bulletin**

- Le bouton se dégrise. Certificat de travail, attestation employeur, solde de tout compte sont proposés.
- Les montants de rupture affichés viennent de ce bulletin (indemnité de congés, précarité s’il y a lieu). Ne comparez qu’à **ce** bulletin d’Octavie, pas à un autre dossier.

**Capture** : bandeau « générez le bulletin » ; Documents grisés + mention ; Documents après génération.

---

## 5. Aide sur le bulletin

Sur le bulletin **généré** d’Octavie (mois M ou mois suivant si le mois M est un bulletin de sortie trop court : alors générer aussi un mois travaillé).

1. **Modifier** le bulletin → onglet **Bulletin**.

### 5.1 Astérisque seulement s’il y a une explication

**Résultat attendu**

- Section « **D’où viennent ces lignes** » : un `*` uniquement à côté d’une ligne qui a une explication.
- Survol du `*` : le texte (heures sup semaine par semaine, absence avec ses dates, ou « Réduction générale : régularisation depuis janvier »).
- **Pas** d’astérisque vide. Un bulletin jamais recalculé depuis l’ajout des explications peut n’avoir aucun `*` : d’abord **Régénérer**, puis revérifier.
- L’astérisque est sur cet écran, **pas** sur le PDF imprimé.

**Capture** : section avec `*` et info-bulle ouverte.

### 5.2 « Ce qui a changé » — pas de chiffre inventé

Même onglet Bulletin, encadré « **Ce qui a changé par rapport au mois dernier** ».

**Résultat attendu**

- S’il existe un bulletin du mois civil précédent : le texte du serveur (brut, net, heures sup, absences). Recopier uniquement ce texte.
- S’il n’y en a pas (premier mois d’Octavie) : **exactement** « Pas de bulletin le mois dernier », **sans aucun montant**.

**Capture** : l’encadré entier.

---

## 6. Liste de contrôle du mois

Page **Bulletins de paie** (`/payroll`), au-dessus des onglets.

### 6.1 Contenu et coches

**Résultat attendu**

- Titre « **Liste de contrôle — {Mois Année}** » (Mois avec une majuscule, ex. « Octobre 2026 »).
- Lien à droite **Manuel de la paie**.
- Six étapes, dans cet ordre :
  1. Calendriers complets
  2. Aucun conflit arrêt / heures
  3. Absences saisies
  4. Bulletins générés et à jour
  5. Sorties créées
  6. RIB renseignés
- Une **coche verte** seulement si une donnée le prouve. Chargement = spinner, pas vert. Erreur de lecture = à confirmer, pas vert.
- **Absences saisies** reste **à confirmer**, avec :  
  « Le logiciel ne peut pas vérifier que toutes les absences du mois sont saisies. Confirmez-le vous-même dans Congés & absences. »
- Tant qu’Octavie a eu « RIB à compléter », l’étape **RIB renseignés** est à faire, détail du type « 1 salarié a la mention « RIB à compléter ». »
- **Actions en attente** : une ligne = quoi, où cliquer, ce qu’on doit voir ensuite. **Pas de nom de salarié** dans ces textes.

**Capture** : bloc entier, y compris Absences à confirmer et les actions.

### 6.2 Un clic « Par mois » ouvre cet onglet

1. Onglet **Par collaborateur** (défaut).
2. Dans **Actions en attente**, cliquer le lien **Bulletins de paie, onglet Par mois** (étape bulletins ou sorties).

**Résultat attendu**

- L’URL contient `view=month` (et `month=AAAA-MM`).
- L’onglet **Par mois** est vraiment sélectionné (pas seulement l’URL). On voit la liste du mois, les bandeaux de sortie s’il y en a.
- Cliquer l’onglet **Par mois** dans les onglets fait la même chose.

**Capture** : URL + onglet Par mois actif.

---

## 7. Manuel opérateur

1. Depuis la liste de contrôle, **Manuel de la paie**, ou ouvrir `/payroll/manuel`.

**Résultat attendu**

- Titre « **Manuel de la paie du mois** ». Lien **Retour à la paie** vers `/payroll`.
- Section « **La paie du mois, étape par étape** » : huit étapes (pointages, calendrier, absences, générer, vérifier, recalculer, valider, sorties).
- Section « **Pièges déjà vus, et quoi faire** » : heures un jour d’arrêt, écran périmé, bulletin à recalculer, net négatif, départ sans bulletin de sortie, RIB à compléter.
- Aucun nom de salarié, aucune société réelle (pas Colorplast, pas Comitech).
- La page est joignable en mode paie.

**Capture** : haut de page + liste des huit étapes ; un piège en entier.

---

## 8. Heures sup du bulletin et calendrier

Après les parcours 2 et 3, sur Octavie uniquement.

1. Calendrier du mois M : noter les heures réelles des jours **travaillés**.
2. Bulletin, onglet Bulletin : lignes d’heures sup.

**Résultat attendu** : plus d’heures sup nées d’un jour d’arrêt. S’il reste une différence, elle doit se lire sur des jours **travaillés** du calendrier, pas sur de l’arrêt. Il n’y a pas de « tableau gestionnaire » de MAJI dans cette recette : ne pas aller chercher un tableau d’une autre société.

**Capture** : calendrier (extrait) + lignes d’heures sup du bulletin.

---

## Prompt à coller dans Claude dans Chrome

Coller **tout ce fichier**, puis le bloc ci-dessous.

```
Tu fais la recette du mode paie EYWAI, uniquement sur le site de test, après le déploiement de la branche fix/payslip-edit-state.

Adresse : https://sirh-frontend-test-505040845625.europe-west1.run.app
Compte : le compte QA déjà ouvert dans Chrome (ne demande pas le mot de passe, ne l’écris pas).
Société : MAJI seulement. N’ouvre jamais Colorplast ni Comitech.

Si le bandeau orange du site de test est absent : arrête-toi, c’est la production.
Si la page /payroll n’a ni « Liste de contrôle » ni le lien « Manuel de la paie » : arrête-toi, le déploiement n’est pas fait. Dis-le clairement.

Suis chaque parcours numéroté de ce document, dans l’ordre (y compris le 2.6, qui rétablit des jours travaillés avant le lot 3). Saisis uniquement le salarié inventé « Octavie Recette » (et « Nestor Recette » seulement pour le parcours 1.4). Ne recopie aucun nom réel, NIR, RIB ou montant d’un autre salarié.

Si le bulletin déjà généré n’a ni mutuelle ni forfait santé : 2.5 = non joué, n’écrase pas le calendrier. Si tu as quand même mis tous les jours en arrêt, fais le 2.6 avant 3.1, 3.3 et 3.6 : sans jour travaillé à 7 h, Recalculer relance le refus d’heures sur arrêt au lieu du toast « Bulletin recalculé ».

Pour chaque parcours : fais les clics, compare au résultat attendu, prends la capture demandée. Remplis ensuite la grille (OK / KO / non joué + une remarque courte).

Si un parcours échoue : KO, capture, passe au suivant quand il est indépendant. N’invente pas de contournement. N’écris pas en base hors des écrans. Ne valide pas la paie d’un autre salarié. Ne déploie rien.

À la fin, rends la grille complète et un résumé de 10 lignes : ce qui est bon, ce qui est KO, ce qui n’a pas pu être joué.
```

---

## Grille de résultats

À remplir pendant la recette. Société : MAJI. Date : ________  Site : test  Branche déployée : oui / non

| N° | Parcours | OK | KO | Non joué | Remarque |
| --- | --- | --- | --- | --- | --- |
| 1.1 | Création : valeur piège (nom trop court, millième, PAS 1,15 %) |  |  |  |  |
| 1.2 | Création : fermeture, confirmation |  |  |  |  |
| 1.3 | Création sans RIB : récap, badge Nouveau, « RIB à compléter » |  |  |  |  |
| 1.4 | Entrée le 21, après clôture des variables |  |  |  |  |
| 2.0 | Calendrier : jours d’arrêt avec heures, marquage rose |  |  |  |  |
| 2.1 | Génération refusée, pas de « Générer quand même » |  |  |  |  |
| 2.2 | Effacer les heures, génération relancée, plus d’HS d’arrêt |  |  |  |  |
| 2.3 | « Modifier l’arrêt » → bandeau planning → calendrier |  |  |  |  |
| 2.4 | Import de pointages, récap conflits |  |  |  |  |
| 2.5 | Mois d’arrêt, net négatif, bouton de report |  |  |  |  |
| 2.6 | Rétablir des jours travaillés avant le lot 3 |  |  |  |  |
| 3.1 | Badge « À recalculer », validation bloquée |  |  |  |  |
| 3.2 | Ancien bulletin sans empreinte : pas périmé |  |  |  |  |
| 3.3 | Recalculer : toast avant → après, badge disparu |  |  |  |  |
| 3.4 | Supprimer, puis déjà supprimé, puis régénérer |  |  |  |  |
| 3.5 | Ancienne URL : « bulletin remplacé » |  |  |  |  |
| 3.6 | PDF du dernier calcul, nom sans horodatage |  |  |  |  |
| 3.7 | F5 : liste à jour, pas de cache périmé |  |  |  |  |
| 4.1 | Départ sans contrat EYWAI, mention, bandeau |  |  |  |  |
| 4.2 | Bulletin de sortie ; documents grisés puis dégrisés |  |  |  |  |
| 5.1 | Aide bulletin : astérisque seulement s’il y a une explication |  |  |  |  |
| 5.2 | « Ce qui a changé » / « Pas de bulletin le mois dernier » |  |  |  |  |
| 6.1 | Liste de contrôle : pas de coche verte sans preuve ; absences à confirmer |  |  |  |  |
| 6.2 | Lien « Par mois » ouvre l’onglet Par mois |  |  |  |  |
| 7 | Manuel `/payroll/manuel` |  |  |  |  |
| 8 | Heures sup du bulletin = jours travaillés du calendrier |  |  |  |  |
