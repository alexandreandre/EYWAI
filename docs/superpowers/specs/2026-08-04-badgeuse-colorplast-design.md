# Badgeuse QR chez Colorplast

Date : 2026-08-04
Sujet : `docs/afaire.md` #21 — « Badgeuse chez Colorplast. Stratégie d'intégration
intelligente à gamberge »
Statut : conception validée, implémentation à planifier

## 1. Objectif

Remplacer les feuilles de pointage papier de Colorplast par la badgeuse EYWAI,
sans qu'un seul bulletin de paie soit faussé pendant la transition.

Le badgeage se fait depuis le téléphone du salarié, avec son compte EYWAI. Pas
de borne, pas de carte, pas de contrôle de lieu : neuf personnes qui se
connaissent, l'écart se voit tout de suite.

La bascule se fait après un mois de double run — badgeuse et papier en
parallèle, réconciliés chaque semaine, le papier arbitre.

## 2. Hors périmètre

- Borne tablette en kiosque, cartes QR plastifiées, badges RFID.
- Géolocalisation, contrôle du réseau Wi-Fi, ou toute preuve de présence
  physique. Décision assumée (§ 4.5).
- Déploiement chez les six autres sociétés. Colorplast d'abord, seul.
- Reprise de l'historique des pointages papier des mois passés.
- Le bug `companies.name` du kiosque (§ 3.5) : réel, mais sans effet ici
  puisque la borne n'est pas utilisée. À porter ailleurs.
- Les badgeuses tierces déjà en place chez deux autres sociétés (§ 3.2).

## 3. État des lieux

Constats établis le 2026-08-04 par lecture de la base de production, du dépôt
et des fichiers de `data/`.

### 3.1 Colorplast n'a pas de badgeuse

Les documents de `data/colorplast/pointages/` ne sortent d'aucune machine. Ce
sont des grilles papier pré-imprimées (semaine, LUNDI→VENDREDI, DÉBUT/FIN),
remplies à la main au stylo, puis scannées ou photographiées au téléphone. Ni
couche texte, ni matricule, ni horodatage à la minute.

La qualité se dégrade : en janvier, scan à plat avec totaux journaliers annotés
et total hebdomadaire entouré en rouge ; en juin, photo de travers sans aucun
total.

Effectif concerné : 9 salariés actifs, dont 1 cadre.

### 3.2 Deux vraies badgeuses existent ailleurs dans le groupe

Elles ne changent rien au périmètre, mais elles disent que le sujet est mûr :

- une société sort un PDF « Pointages "retenu" + commentaires, semaine à
  semaine » produit par un logiciel WinDev, avec matricules et pointages à la
  minute ;
- une autre sort un Excel `Matricule / Jour / Nom / Section / Entrée 1-3 /
  Sortie 1-3 / Tot H Point / Hr Théorique / Code Horaire`.

Le dépôt sait déjà lire ce genre de formats (`parsers/kelio_weekly.py`,
`cegid_weekly.py`, `banque_heures.py`, plus un import tabulaire générique).

### 3.3 La badgeuse EYWAI existe, mais n'est déployée nulle part

Le module est là : QR signé HMAC, terminaux authentifiés, pointages,
comptabilisation, export. En production, tout est à zéro : 3 terminaux créés en
essai (2 chez Colorplast le 09/06, 1 ailleurs le 01/07), **2 pointages au
total**, aucun paramétrage de comptabilisation chez Colorplast.

Le QR est **statique** — `eywai:badge:v1:<société>:<salarié>:<version>:<signature>`,
sans horodatage ni expiration, valable jusqu'à régénération. Il pourrait donc
être imprimé sur une carte. On ne s'en sert pas ici, mais c'est bon à savoir.

### 3.4 Le bouton de badgeage n'existe pas

C'est le point que le compte rendu « module complet, rien à développer » a
manqué.

- Back : `POST /api/me/badgeuse/toggle` fonctionne, réglage `allow_self_toggle`
  à `true` par défaut.
- Front : `toggleMyBadge` est écrit dans `frontend/src/api/badgeuse.ts` et
  **appelé nulle part**.
- L'écran « Ma badgeuse » n'affiche qu'un QR, une frise et, si le réglage est à
  faux, la phrase « Le badgeage se fait uniquement via scan QR à l'accueil ».

Un salarié ne peut donc pas pointer depuis son téléphone aujourd'hui.

### 3.5 Deux défauts moteur constatés

**Aucune pause n'est déduite si la comptabilisation est désactivée.** Une
journée badgée vaut alors le brut sortie − entrée. Chez Colorplast : environ
30 min de trop par jour et par personne, soit de l'ordre de **90 h par mois
payées en trop** pour neuf salariés. Et comme leurs semaines tournent entre 39 h
et 44 h, l'erreur tombe directement dans les heures supplémentaires.

**Le seuil de pause n'existe pas.** La pause est déduite à plat, tous les jours
travaillés, quelle que soit la durée de présence.

Bug annexe, hors périmètre : l'endpoint de statut du kiosque lit
`companies.name`, colonne qui n'existe pas — c'est `company_name` — et l'erreur
est avalée par un `except Exception: pass`. L'écran de la borne n'affiche donc
jamais le nom ni le logo de la société.

### 3.6 La règle de pause réelle de Colorplast

Décodée de leurs feuilles, semaine 03, quatre salariés : **30 minutes déduites
seulement au-delà de 6 h de présence**. Une journée de 6 h pile ne subit aucune
déduction, un vendredi de 5 h non plus. Les totaux hebdomadaires entourés en
rouge (28, 43, 44, 39) retombent au quart d'heure près avec cette règle.

Déduite, pas confirmée. À faire valider par Elsa (§ 7).

### 3.7 Le système de créneaux ne leur convient pas

`company_punch_shift_slots` suppose des équipes à horaires fixes. Chez
Colorplast les horaires varient chaque jour : embauche à 6 h ou 7 h, sortie à
15 h, 16 h, 16 h 30 ou 17 h 30.

Sans créneau, `compute_punch_day` retient `théorique = pointé` et applique la
pause par défaut de la société. C'est exactement ce qu'il faut ici — à condition
que le seuil du § 3.6 existe.

### 3.8 Aucun des neuf salariés ne s'est jamais connecté

Comptes créés fin juin 2026, tous confirmés, tous avec un e-mail réel,
`last_sign_in_at` vide pour les neuf.

C'est le vrai risque du projet. Le blocage n'est pas technique.

## 4. Conception

### 4.1 Chantier 1 — le bouton badger

Dans `EmployeeBadgeusePanel`, un bouton principal, lisible sur un téléphone
tenu d'une main sale en atelier : *Je pointe mon entrée* / *Je pointe ma
sortie* selon l'état courant, l'heure du dernier pointage, et l'état en
présence déjà affiché.

- Il appelle `toggleMyBadge`, qui existe.
- Il n'apparaît pas si `allow_self_toggle` est à faux — le message qui le
  remplace est déjà écrit.
- Il n'apparaît que sur la journée du jour, jamais sur une date passée.
- Garde-fou anti double-pointage : bouton désactivé pendant l'appel, et refus
  d'un second pointage dans la minute qui suit le précédent.
- Après pointage, la frise se rafraîchit et affiche la nouvelle ligne.

Aucun changement back n'est nécessaire.

### 4.2 Chantier 2 — le seuil de pause

Nouveau réglage société dans `company_punch_accounting_settings` :
`break_threshold_minutes`, la présence brute en deçà de laquelle aucune pause
n'est déduite.

- Valeur par défaut **0** : aucune déduction supprimée, comportement identique
  à aujourd'hui. Aucune régression possible pour les sociétés déjà
  paramétrées.
- Règle : si `sortie − entrée` ≤ seuil, pause déduite = 0 ; sinon, la pause
  résolue par les règles existantes s'applique inchangée.
- Le seuil s'applique après la résolution de pause actuelle, pas à sa place :
  créneaux, pause planifiée et pause payée gardent leur priorité.
- Éditable depuis Entreprise > Paie, à côté des réglages de comptabilisation
  existants.

Paramétrage Colorplast : comptabilisation activée, seuil 360 minutes, pause par
défaut 30 minutes, aucun créneau.

C'est un réglage de société, pas une règle codée pour Colorplast : le moteur
reste généraliste.

### 4.3 Chantier 3 — la réconciliation hebdomadaire

Un script, pas un écran : neuf salariés sur quatre semaines, c'est un outil
jetable, et un écran coûterait plus cher que le service rendu.

Entrée : une semaine, la société. Sortie : un tableau par salarié et par jour —
heures comptabilisées depuis la badgeuse, heures lues sur la feuille papier,
écart — plus un total hebdomadaire par salarié.

Les heures papier sont saisies à la main dans un fichier de la semaine : les
feuilles sont des images sans couche texte, et neuf lignes par semaine se
recopient plus vite qu'on ne fiabilise une lecture automatique. Le fichier vit
sous `data/colorplast/pointages/`, jamais dans le dépôt.

Le script est en lecture seule. Il ne corrige rien, il ne touche à aucun
calendrier, à aucune paie.

### 4.4 Ce qui alimente la paie, et quand

Rien pendant le double run. Les pointages s'accumulent, la comptabilisation
tourne, mais le calendrier réel et la paie continuent de venir des feuilles
papier par le circuit actuel.

La bascule est une décision explicite prise avec Elsa en fin de mois, sur la
base des écarts constatés. Elle n'est pas dans le périmètre de cette spec.

### 4.5 Absence de contrôle de lieu

Assumée. Rien n'empêche un salarié de pointer depuis chez lui.

Le garde-fou est humain et suffisant à cette échelle : neuf personnes dans une
petite usine, un écart d'horaire se remarque le jour même. Les anomalies
détectées par le moteur — pointage manquant, journée hors normes — restent
visibles côté RH, et la RH peut corriger un pointage via l'outil existant.

Si le besoin apparaît plus tard, le QR affiché au mur de l'atelier est la piste
la moins intrusive. Pas maintenant.

## 5. Déroulé

**Semaine 0 — préparation.**
Paramétrage rejoué d'abord sur l'environnement de test, puis appliqué en
production. Le seuil de pause est livré avant, sans quoi le paramétrage n'a pas
de sens.

**Semaine 0 — les comptes.**
Les neuf salariés se connectent une première fois. C'est le point qui décide du
succès du reste. Mots de passe distribués sur place, une démonstration du
bouton en atelier, pas un e-mail.

**Semaines 1 à 4 — le double run.**
Badgeage au téléphone *et* feuille papier comme d'habitude. Réconciliation
chaque lundi sur la semaine écoulée. Chaque écart est expliqué avant de passer
à la semaine suivante : un écart non expliqué est un écart qui reviendra sur un
bulletin.

**Fin de mois — la décision.**
Bilan des écarts avec Elsa, et décision de basculer ou de prolonger.

## 6. Critères de réussite

- Les neuf salariés se sont connectés au moins une fois.
- Sur la dernière semaine du double run, l'écart badgeuse/papier est nul ou
  expliqué pour chaque salarié.
- Aucun changement de comportement pour les six autres sociétés : le seuil de
  pause à 0 par défaut le garantit, et un test doit le démontrer.
- Le taux de pointages oubliés est connu et jugé acceptable par Elsa.

## 7. Questions ouvertes

À poser à Elsa, aucune ne bloque le démarrage du développement :

1. La règle « 30 min déduites au-delà de 6 h » est déduite des feuilles. Est-ce
   la règle écrite chez Colorplast ?
2. Que fait-on d'un oubli de pointage — sortie non badgée, journée entière
   oubliée ? Proposition : anomalie visible côté RH et correction manuelle par
   la RH, jamais par le salarié.
3. Qui valide les heures supplémentaires chez Colorplast ? Le réglage
   `require_manager_validation_for_overtime` attend un nom.
4. Les feuilles papier s'arrêtent-elles à la bascule, ou reste-t-elle une trace
   de secours ?
