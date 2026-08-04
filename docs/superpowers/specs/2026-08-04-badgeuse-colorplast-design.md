# Badgeuse QR chez Colorplast

Date : 2026-08-04
Sujet : `docs/afaire.md` #21 — « Badgeuse chez Colorplast. Stratégie d'intégration
intelligente à gamberge »
Statut : conception validée ; bouton livré, paramétrage vérifié sur
l'environnement de test et en attente d'application en production

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
- Le bug `companies.name` du kiosque (§ 3.5) est sans effet ici puisque la
  borne n'est pas utilisée. Corrigé au passage, une ligne, plutôt que laissé
  derrière nous.
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

Une correction ponctuelle écrite lors d'une session précédente
(`backend/scripts/colorplast_unpaid_break_one_shot.py`) applique la même
déduction, formulée autrement : 30 minutes du lundi au jeudi, en excluant deux
salariés. Cette exclusion tenait à l'état des données de l'époque, pas à une
règle différente — les neuf salariés suivent aujourd'hui le même rythme de
8,5 h du lundi au jeudi et 5 h le vendredi.

⚠ Ce script retranche 30 minutes des heures **déjà enregistrées**. Une fois la
badgeuse en place, la déduction se fait en amont : le rejouer déduirait la
pause une seconde fois.

Déduite, pas confirmée. À faire valider par Elsa (§ 7).

### 3.7 Le système de créneaux ne leur convient pas

`company_punch_shift_slots` suppose des équipes à horaires fixes. Chez
Colorplast les horaires varient chaque jour : embauche à 6 h ou 7 h, sortie à
15 h, 16 h, 16 h 30 ou 17 h 30.

Sans créneau, `compute_punch_day` retient `théorique = pointé` et applique la
pause résolue pour la journée. C'est exactement ce qu'il faut ici.

### 3.8 La pause planifiée prime sur la pause par défaut

Piste explorée puis écartée au § 4.2, mais le mécanisme reste vrai et il faut
le connaître pour comprendre l'ordre de priorité des pauses.

`resolve_break_minutes` regarde d'abord la pause non payée **planifiée** : si
la journée du calendrier en porte une, elle l'emporte sur la pause par défaut
de la société. Cette pause remonte de bout en bout —
`calendar_generation_rules` la pose sur chaque jour généré,
`_unpaid_break_from_planned` la relit, `compute_accounted_hours_for_badgeuse_day`
la transmet.

Colorplast a déjà un gabarit de semaine « Colorplast — Standard (39 h) » qui
porte une pause par jour, aujourd'hui à zéro partout, et dont les heures
correspondent exactement aux feuilles papier : 8,5 h du lundi au jeudi, 5 h le
vendredi.

Quand la pause planifiée vaut zéro, aucune clé n'est écrite sur la journée et
le moteur retombe sur la pause par défaut de la société. Il suffit donc de
laisser cette valeur par défaut à zéro pour que le vendredi ne subisse aucune
déduction.

### 3.9 Aucun des neuf salariés ne s'est jamais connecté

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

### 4.2 Le seuil de pause

Le chemin a hésité, et le détour vaut d'être écrit.

Le mécanisme de pause planifiée du § 3.8 permet de poser 30 minutes du lundi au
jeudi et rien le vendredi, sans une ligne de code. Vérification faite sur leurs
feuilles, il se trompe : une demi-journée du lundi au jeudi subirait la pause
alors qu'elle n'en subit aucune en réalité. Sur la seule semaine 03, le cas se
produit une fois — un mardi de 6 h compté 6 h.

La règle n'est donc pas « pause du lundi au jeudi » mais bien « pause au-delà
d'une certaine présence », telle que décodée au § 3.6. Elle demande un réglage
qui n'existait pas :

**`break_threshold_minutes`** — présence brute en deçà ou égale à laquelle
aucune pause n'est déduite.

- Valeur par défaut **0** : aucune journée exemptée, comportement identique à
  aujourd'hui pour toutes les sociétés déjà paramétrées.
- Le seuil s'applique **après** la résolution de pause existante, jamais à sa
  place : créneaux, pause planifiée et pause payée gardent leur priorité. Il ne
  fait qu'annuler le résultat sur une journée trop courte.
- Comparé au brut pointé, pauses comprises.
- Éditable depuis Entreprise > Paie, à côté des réglages de comptabilisation.

Paramétrage Colorplast : comptabilisation activée, pause par défaut 30 minutes,
seuil 360 minutes, aucun créneau.

Le seuil rend inutile toute autre manipulation : ni gabarit de semaine à
modifier, ni calendrier à régénérer, ni heure réelle à retoucher. C'est ce qui
l'a emporté sur la piste précédente, autant que sa justesse.

Vérification : les trois semaines complètes relevées sur la feuille papier de la
semaine 03 (28 h, 43 h, 39 h) sont reproduites au centième par le moteur, jour
par jour, demi-journée comprise.

### 4.3 La réconciliation hebdomadaire — à la main

Première version de cette spec : un script de comparaison. Disproportionné.

Neuf salariés sur cinq jours, c'est quarante-cinq cellules par semaine. La
comparaison se fait dans un tableur, à partir de l'export badgeuse existant
d'un côté et de la feuille papier de l'autre. Un script apporterait du confort,
pas de la fiabilité — et il faudrait de toute façon saisir les heures papier à
la main, les feuilles étant des images sans couche texte.

Ce qui compte n'est pas l'outil mais la discipline : chaque écart est expliqué
avant de passer à la semaine suivante.

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
Le bouton et le seuil sont livrés. Le paramétrage est rejoué d'abord sur
l'environnement de test — fait le 2026-08-04, migration comprise, sans effet sur
les autres sociétés — puis appliqué en production par
`backend/scripts/setup_badgeuse_colorplast.py --apply`.

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
- Aucun changement de comportement pour les six autres sociétés : le
  paramétrage du § 4.2 ne touche que le gabarit et les réglages de Colorplast.
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
