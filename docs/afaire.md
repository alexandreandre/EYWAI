# EYWAI, suivi des points

**Vérifié le 7 août 2026** dans la vraie base de production.


|     |                                     |
| --- | ----------------------------------- |
| 🟢  | **Terminé**, en ligne               |
| 🟠  | **On attend quelque chose de vous** |
| 🔴  | **À faire de notre côté**           |


## Vue d'ensemble


| #   | Sujet                         |       | #   | Sujet                     |       |
| --- | ----------------------------- | ----- | --- | ------------------------- | ----- |
| 1   | Accès de Vanessa              | 🟢    | 18  | Point paye avec Gaëlle    | 🟠    |
| 2   | Identifiants Gaëlle / Vanessa | 🔴    | 19  | Fractionnement des congés | 🟢    |
| 3   | Fichier BIC                   | 🟢 🔴 | 20  | NIR et sortie DSN         | 🟢 🟠 |
| 4   | **Adresses e-mail**           | 🟠    | 21  | Badgeuse Colorplast       | 🟢 🔴 |
| 5   | Robin, droits directeur      | 🟢    | 22  | Arrondi des congés        | 🟢    |
| 6   | Titres de séjour              | 🟢    | 23  | Provision congés payés    | 🟢 🟠 |
| 7   | Export titres de séjour       | 🟢    | 24  | Format du bulletin        | 🟢    |
| 8   | Compteur JTC                  | 🟢 🟠 | 25  | Entretiens annuels        | 🟢 🟠 |
| 9   | RTT Colorplast                | 🟢    | 26  | Interfaçage comptable     | 🟢 🟠 |
| 10  | Aménagement de poste          | 🟢    | 27  | Post-traitement pointages | 🟢 🔴 |
| 11  | Élus CSE                      | 🟢 🟠 | 28  | Périodes d'essai          | 🟢    |
| 12  | Exports CSE et BDES           | 🟢    | 29  | Alertes de paie           | 🟢    |
| 14  | Médailles du travail          | 🟢    | 30  | Assistant RH              | 🟢    |
| 15  | Prime de transport            | 🟢    | 31  | Taux prélèvement source   | 🟢 🟠 |
| 16  | Virement des acomptes         | 🟢    | 32  | Activité partielle        | 🟢    |
| 17  | Environnement de test         | 🟢    |     |                           |       |


> **Le plus urgent : le #4.** 148 salariés sur 246 n'ont pas d'adresse e-mail
> réelle. Ils ne peuvent ni se connecter, ni recevoir leur bulletin.

---



## #1. Accès de Vanessa 🟢

Vanessa voit ses 7 sociétés. Elle n'a qu'à se reconnecter.

Le jour de la réunion, elle s'était connectée entre deux mises à jour des
droits. D'où les 2 sur 7. C'était bon un quart d'heure après.

**Trouvé en vérifiant :** retirer un accès ne marchait pas vraiment. La
personne continuait à voir les sociétés qu'on lui avait enlevées. Corrigé et
nettoyé en production.

---



## #2. Identifiants Gaëlle et Vanessa 🔴

**Reste :** leur envoyer leurs identifiants par WhatsApp. De notre côté.

---



## #3. Fichier BIC 🟢 🔴

Le fichier n'était pas à attendre : vous l'aviez envoyé le 27 juillet.


| Société    | Lignes | BIC                          |
| ---------- | ------ | ---------------------------- |
| Cartol     | 91     | 91                           |
| MBC        | 76     | 76                           |
| Comitech   | 17     | 17                           |
| MAJI       | 10     | 10                           |
| Colorplast | 7      | 7                            |
| Zone 404   | 5      | 5                            |
| LEWIS      | 39     | 0 *(RIB seul, convertibles)* |


**206 BIC** sur six sociétés. Vos données sont bonnes : tous les IBAN sont
valides.

**Le BIC n'est plus obligatoire.** Depuis 2016, l'IBAN suffit. Nos exports
partent sans, avec un simple message.

**Reste :** le blocage est chez nous. Notre import lit une seule colonne et
ignore celle d'à côté, où est le BIC. À corriger avant de charger.

---



## #4. Adresses e-mail 🟠

**C'est notre plus gros blocage.**


| Sur 246 salariés en poste     |         |
| ----------------------------- | ------- |
| Adresse réelle                | 92      |
| **Adresse inventée par nous** | **148** |
| Aucune adresse                | 6       |


Les adresses inventées finissent par `dsn-import.local`. Elles viennent de
l'import des DSN, qui refuse de créer un salarié sans adresse.

**Elles ne marchent pas.** Ces 148 salariés ne peuvent ni se connecter, ni
recevoir leur bulletin.


| Société              | En poste | Inventées |
| -------------------- | -------- | --------- |
| LEWIS                | 39       | **39**    |
| Cartol               | 90       | **77**    |
| Mont Blanc Composite | 76       | 19        |
| Comitech             | 18       | 10        |
| Colorplast           | 7        | 2         |
| MAJI                 | 10       | 1         |
| Zone 404             | 6        | 0         |


**Il nous faut :** les vraies adresses. On ne les invente jamais à partir d'un
nom, on risquerait d'envoyer un bulletin à un inconnu.

---



## #5. Robin, droits de directeur 🟢

Robin est collaborateur RH sur Zone 404, avec les droits d'un directeur.

« Directeur » n'est pas un rôle chez nous, mais un ensemble de droits, celui
d'Eric Noble, Damien Faucher et Lucas Chambert.

Robin garde son espace salarié. Il gagne la vue RH et les validations : valider
un bulletin, approuver une note de frais ou une avance.

---



## #6. Titres de séjour 🟢

**41 salariés sur 43** ont leur date d'expiration. Avant, il en manquait 34.

33 chez Mont Blanc Composite, 3 Cartol, 2 LEWIS, 2 Zone 404, 1 Comitech.

Les alertes fonctionnent donc enfin pour de vrai.

---



## #7. Export Excel des titres de séjour 🟢

Un bouton « Exporter en Excel » sur la page RH.

Le fichier donne : nom, prénom, matricule, société, poste, date d'entrée,
nationalité, type et numéro de titre, date d'expiration.

Et surtout le **statut avec les jours restants**, vous voyez tout de suite qui
est expiré ou sur le point de l'être.

L'export reprend ce qui est à l'écran, limité à la société en cours.

---



## #8. Compteur JTC 🟢 🟠

Votre note du 28 juillet fixait tout. On l'a suivie à la lettre :

- Propre à **Mont Blanc Composite**. Personne d'autre.
- **3 jours par an** maximum, gagnés sur l'année précédente.
- Réduits si entrée en cours d'année, ou plus de 30 jours d'absence.
- Arrondis vers le bas : le solde vaut 0, 1, 2 ou 3.
- Un nouvel embauché n'a rien la première année.
- Journée de solidarité sur un JTC, sinon sur un congé payé.
- Le solde non posé est payé au départ.
- **Le JTC s'affiche à côté des congés payés, jamais dedans.**

Le compteur est en ligne, **éteint partout**. Tant qu'on ne l'allume pas sur
Mont Blanc Composite, rien ne change nulle part. Le barème se règle depuis
**Entreprise > Congés**, sans passer par nous.

**Il nous faut :**

1. **Les soldes de départ.** Le JTC 2026 se gagne sur 2025, or EYWAI ne
  contient rien avant janvier 2026. On ne peut pas recalculer pour vos 75
   salariés. À partir de 2027, EYWAI calculera seul.
2. **Une précision.** Un salarié absent 31 jours perd-il un JTC ? On a retenu
  la lecture stricte : il tombe à 2. Ça change le compte de tous ceux qui ont
   eu un arrêt d'un mois.
3. **L'onglet « détail absences »** de votre Excel, jamais reçu. C'est lui qui
  dit quelles absences comptent.

**Reste chez nous :** la journée de solidarité automatique et le paiement du
solde au départ. Laissés de côté exprès, ils touchent au calcul de la paie.

---



## #9. RTT chez Colorplast 🟢

Ce n'étaient pas des RTT posés, mais **un solde affiché à tort**.

Sans paramétrage, le système donnait 10 RTT par an à tout le monde. Ça touchait
4 sociétés sur 7.

Maintenant, sans paramétrage : 0. Les RTT se calculent depuis le forfait annuel
de chaque société (214 j chez Cartol, 216 ailleurs) et sont réservés aux 19
cadres au forfait-jours.

Colorplast est bien à 0.

---



## #10. Case « aménagement de poste » 🟢

En enregistrant une visite médicale comme réalisée, vous pouvez cocher
« aménagement de poste ».

La case remonte en tête de la fiche du salarié, en lecture seule. La visite
reste le seul endroit de saisie, et la corriger met bien la fiche à jour.

Volontairement une simple case, sans motif ni date de fin.

---



## #11. Élus CSE 🟢 🟠

Vous aviez envoyé votre liste le 2 août : **8 élus titulaires**, 2 Cartol,
2 LEWIS, 4 Mont Blanc Composite. On les a tous retrouvés, y compris celle qui
figure chez vous sous son nom d'usage.

L'outil de reprise est en ligne et testé. Il relit votre fichier, refuse
d'écrire si une ligne est douteuse, ne crée jamais deux fois le même mandat, et
refuse un mandat pour quelqu'un de parti. Répétition faite : les 8 mandats se
créent, la relance n'en crée aucun.

**Il nous faut le mandat lui-même.**

La colonne « date d'entrée » de votre fichier est la date d'embauche, pas la
date d'élection, les huit correspondent au jour près à ce qu'on a déjà. Sans
date de début et de fin, on ne peut rien enregistrer : ce sont elles qui
déclenchent les alertes et le calcul des heures de délégation.

Il nous faut aussi :

- Les **suppléants**, vous n'avez listé que des titulaires
- Le **collège** pour Cartol et LEWIS
- Le **secrétaire** de chaque CSE
- Le cas de **Colorplast, MAJI et Zone 404** : ni élu ni PV de carence. Celui
de Comitech est périmé depuis septembre 2023.

Aucun élu n'est enregistré à ce jour. L'outil attend vos dates.

---



## #12. Exports CSE et BDES 🟢

Vos erreurs sont trouvées et corrigées. Sans votre fichier : le défaut se
reproduisait tout seul.

**Trois problèmes :**

1. L'export des élus affichait **« Actif » pour tout le monde**, mandats
  terminés compris, avec « jours restants » vide. Le programme n'arrivait pas
   à lire ses propres dates et retombait sur « Actif ».
2. Les dates s'affichaient en écriture machine dans les trois exports.
3. **L'export des heures de délégation ne marchait pas du tout.** Il plantait à
  chaque tentative, depuis toujours. Personne ne l'avait signalé, il n'avait
   sans doute jamais servi.

Un mandat clos en janvier 2023 sort maintenant « Expiré », avec les jours de
dépassement. Un mandat proche du terme est signalé 3 mois avant.

**Plus grave, trouvé en relisant :** une société dont tous les mandats sont
expirés serait apparue « CSE en place, conforme ». Un faux feu vert sur une
obligation légale. Corrigé.

---



## #14. Médailles du travail 🟢

Le barème s'édite depuis **Entreprise > Paie** : paliers 20, 30, 35 et 40 ans
et leurs montants. Le montant reste ajustable au moment de valider.

Ajouté : un réglage **base d'ancienneté par société**, pour les reprises
d'ancienneté où la date d'entrée ne reflète pas les droits réels.

Surtout : la détection ne tournait qu'à l'ouverture d'une fiche. Elle passe en
**scan automatique quotidien**.

---



## #15. Prime de transport 🟢

Le montant se règle sur la fiche du salarié, avec une date d'effet. Il génère
chaque mois une ligne d'indemnité trajet dans les saisies.

Modifiable ou supprimable mois par mois. **Une correction manuelle n'est jamais
écrasée.**

Proratisée à l'entrée et à la sortie, retirée si absence tout le mois, avec
alerte au dépassement du plafond exonéré.

---



## #16. Virement des acomptes 🟢

Un export « Virement acomptes » séparé de celui des salaires : sa propre date
d'exécution, ses références bancaires, son historique.

Deux usages : sortir l'ordre de virement pour la banque (acomptes approuvés non
payés), ou la liste des acomptes déjà versés sur une période.

Les BIC manquants ne bloquent plus l'envoi.

---



## #17. Environnement de test 🟢

Un second EYWAI complet, avec sa propre base.

Il reçoit une copie des données réelles de la production, déclenchée à la main
depuis le bandeau orange. **Jamais dans l'autre sens.** Ce que vous y faites, 
démission, suppression, bulletin, reste dans le test et disparaît à la copie
suivante.

Les données étant réelles, trois sorties sont verrouillées : les e-mails
partent tous vers une seule boîte (le service refuse de démarrer sans), la
signature électronique et le dépôt de DSN sont refusés.

---



## #18. Point paye avec Gaëlle 🟠

**Il nous faut :** organiser la réunion.

---



## #19. Fractionnement des congés 🟢

Ce n'était pas propre. **Sept défauts** faussaient le calcul, dont un qui
rendait 0 jour pour les 221 salariés de MBC. Tout est corrigé.

Paramétrable par société dans **Entreprise > Congés** : méthode de calcul,
barème, exclusion des cadres au forfait-jours.

Le calcul est automatique, mais **rien n'est crédité sans votre validation**.

Aucune société n'était paramétrée : aucun salarié n'a été touché par ces
erreurs.

---



## #20. NIR et sortie DSN 🟢 🟠

**Les NIR sont bons.** 240 actifs, aucun vide, clé de contrôle correcte
partout. 274 des 275 personnes des DSN du cabinet correspondent au chiffre
près.

Trois anomalies viennent du cabinet, qu'on avait recopiées : 8 salariés
déclarés avec un sexe que leur NIR contredit, 2 dates de naissance
divergentes, 1 salarié déclaré chez Cartol qui n'existe pas dans EYWAI.

**Notre sortie DSN n'était pas déposable** : 100 à 120 rubriques manquantes
selon la société, dont le bloc total sans lequel net-entreprises rejette le
fichier. L'en-tête, l'identité et les contrats sont maintenant conformes,
vérifiés automatiquement sur cinq sociétés.

**Il nous faut :** la nomenclature officielle des codes de cotisation, à
demander au cabinet. Sans elle, on déclarerait des montants faux sur les
cotisations, les agrégés URSSAF et la prévoyance.

En attendant, l'export est marqué « non déposable » et le dit à l'écran.

---



## #21. Badgeuse Colorplast 🟢 🔴

**Surprise : Colorplast n'a pas de badgeuse.** On recevait des feuilles papier
remplies au stylo, puis scannées. La qualité se dégradait et les totaux avaient
disparu depuis le printemps.

Les salariés vont donc badger depuis leur téléphone. Le bouton n'existait pas,
il est en ligne.

Le système déduit la pause déjeuner comme eux : **30 minutes seulement au-delà
de 6 heures**, aucune sur une demi-journée. Vérifié sur leurs feuilles, les
trois semaines complètes tombent au centième.

**Rien ne part en paie tout de suite.** Pendant un mois, badgeuse et papier
tournent en parallèle, comparés chaque semaine. Le papier a le dernier mot.

**Reste :** le point d'attention n'est pas technique. **Aucun salarié de
Colorplast ne s'est jamais connecté à EYWAI.** Il faut les connecter.

*(On compte 7 salariés en poste ; le compte rendu en annonçait 9.)*

---



## #22. Arrondi des congés au 31 mai 🟢

Vérifié, rien à corriger. On arrondit toujours **au supérieur** dès qu'il y a
une fraction, à l'avantage du salarié, conforme à l'usage paie.


| Mois *(1er juin → 31 mai)* | Calcul | Résultat |
| -------------------------- | ------ | -------- |
| 1 *(bulletin de juin)*     | 2, 5    | **3**    |
| 7 *(au 31/12)*             | 17, 5   | **18**   |
| 8 *(au 31/01)*             | 20, 0   | **20**   |
| 12 *(période complète)*    | 30, 0   | **30**   |


Le mois n'est pas découpé en jours : tout mois commencé compte pour 1. Une
embauche le 15 juin fait compter juin en entier.

Taux paramétrable par société, par défaut 2, 5 jours ouvrables.

---



## #23. Provision congés payés 🟢 🟠

Le fichier exemple n'était pas à demander : vous l'aviez envoyé le 21, puis le
27 juillet. Un état du cabinet pour Cartol, 71 salariés, 394 121 €.

On l'a décortiqué plutôt que de vous relancer. **La méthode du cabinet est
entièrement retrouvée et tombe au centime sur les 71 lignes.** Le calcul :
solde de congés × journée de salaire + charges patronales.

L'export est dans **Exports > Exports RH**, sous « Provision congés payés ».
Vous choisissez un mois, vous obtenez un Excel avec une ligne par salarié et un
total.

On a ajouté trois colonnes que le cabinet n'a pas, date d'entrée, nombre de
mois de paie utilisés, colonne « anomalie », pour voir d'où sort chaque
chiffre au lieu de croire le fichier sur parole.

**Le premier essai sortait 31 % trop bas.** Pas le calcul : le solde de l'année
précédente n'avait jamais été repris. Chez nous il valait 25 jours pour tout le
monde, alors qu'en réalité il va de 3 à 88 jours.

Ces soldes étaient **dans votre fichier**, une colonne du même document. On les
a remis dans EYWAI. Vérifié nom par nom : BOISSINOT 88 jours, QUERAT 81,
BERTAUD 28. L'écart est passé de 6, 2 jours à un centième de jour, et de 31 % à
12 % en euros.

**Les 12 % restants ne peuvent pas être réglés.** Le salaire de référence se
calcule sur douze mois de paie, on n'en a que six. Ça se réglera seul en juin
2027. En attendant, l'export affiche un avertissement permanent, on préfère ça
à un montant faux présenté comme sûr.

Juste, en revanche : le solde de l'année en cours (4, 17 jours contre 4, 16 chez
le cabinet) et le taux de charges de chaque salarié.

Corrigé aussi : Zone 404 et MAJI n'ayant aucun bulletin, leur provision sortait
à zéro sans rien annoncer. On retombe sur le salaire du contrat (9 860 € et
22 602 €), et un fichier entièrement à zéro n'est plus produit.

**Il nous faut :**

1. **Le même état pour les six autres sociétés.** Ce n'est pas que pour la
  provision : c'est ce qui corrigera leurs compteurs de congés.
2. **Une réponse.** Votre fichier Cartol ne contient que 71 salariés, alors que
  86 ont été payés en juin. Les absents sont des embauches récentes. Nous, on
   les garde : ils ont des congés acquis, donc une dette.

---



## #24. Format du bulletin 🟢

Le bulletin sort au format du cabinet. Une page, sobre : compteurs de congés en
haut à gauche, adresse du salarié à droite, cumuls sur le côté, net à payer en
bas.

Les rubriques portent les codes Cegid (Q100 Santé, Q300 Retraite). Ce qu'on
affichait en plus, primes, notes de frais, cumuls annuels, soldes RTT, se
fond dans le gabarit.

L'aperçu à l'écran montre exactement le document qui sortira.

**Aucun montant ne change.** Les bulletins déjà émis restent tels quels.

Ajouté au passage : une mention obligatoire qui manquait depuis le début, 
l'évolution de la rémunération liée à la suppression des cotisations chômage et
maladie.

---



## #25. Entretiens annuels 🟢 🟠

Le fichier n'était pas à attendre : « Planif_entretiens.xlsx », envoyé le
27 juillet. 256 lignes, sept sociétés, et la règle de chacune :


| Société                     | Règle                      |
| --------------------------- | -------------------------- |
| Cartol                      | Novembre                   |
| Comitech, Colorplast, LEWIS | Octobre                    |
| MAJI                        | Décembre                   |
| Zone 404                    | À la date d'ancienneté     |
| Mont Blanc Composite        | Octobre, tous les deux ans |


Il fallait commencer par là. La page existait depuis longtemps, convocation
PDF, signature électronique, types légaux, **mais elle n'a jamais servi.** Pas
un seul entretien en production. Aucun compteur légal ne courait.

**Chaque société a maintenant sa campagne réglable** dans **Entreprise >
Paie** : le mois où l'on convoque tout le monde (ou « à la date
d'ancienneté »), et tous les combien.

C'est le point important : **l'an prochain, EYWAI proposera seul la campagne
suivante, et vous changerez le mois sans nous.** Tant qu'une société n'est pas
réglée, rien ne bouge chez elle.

La liste à planifier ne regardait que les cadres et forfaits jour, soit une
poignée de gens. Réglée, elle couvre tout l'effectif, avec la date attendue et
les retards en tête.

**La reprise est prête et vérifiée à blanc :** 211 entretiens à planifier, 43
passés. Le programme ne recopie pas votre colonne : il recalcule chaque
échéance avec la règle de la société, puis compare. **Sur 211 lignes, aucun
écart.** Il refuse d'écrire au moindre désaccord, ne crée jamais de doublon, et
ignore les salariés partis.

Deux choix volontaires : les 32 lignes de gens déjà sortis sont ignorées, et
pour les entretiens passés votre fichier ne donne qu'une **année**, on
l'enregistre sans inventer un jour. C'est suffisant pour faire courir le délai
de deux ans.

**Il nous faut :**

1. **Mont Blanc Composite ne colle pas.** Votre onglet compte 58 personnes, on
  en a 75 en poste. 13 de vos noms nous sont inconnus, 30 des nôtres n'y sont
   pas. À trancher avant de charger.
2. **Aucune date d'entretien professionnel ni de bilan à six ans**, ce sont
  pourtant les deux seuls obligatoires. Si elles existent, il nous les faut.
   Sinon tout le monde repart de zéro.
3. **Confirmer le cycle de deux ans** de Mont Blanc Composite.

Aucun entretien n'est écrit en base, aucune société n'est encore réglée.

---



## #26. Interfaçage comptable 🟢 🟠

L'écriture comptable de paie est juste et équilibrée. Elle sort aux comptes du
cabinet, **ventilée par organisme** (URSSAF, retraite, mutuelle, prévoyance) au
lieu d'un compte fourre-tout, et agrégée par compte comme le fait le cabinet :
une vingtaine de lignes au lieu de 137.

Colorplast, Comitech et Cartol tombent au centime. **Avant, aucune société ne
tombait juste**, il manquait jusqu'à 114 000 € d'un côté de la balance.

Un fichier qui ne s'équilibre pas n'est plus produit : l'écran dit quel compte
manque.

**Il nous faut :**

- Les comptes du cabinet pour les **paniers**, la **cantine** et les **IJSS**
- Les **identifiants Cegid**, pour envoyer les écritures automatiquement au
lieu de déposer un fichier

---



## #27. Post-traitement des pointages 🟢 🔴

Tout se règle par société dans **Entreprise > Paie > « Pointages & imports »** :
pause repas, durée en dessous de laquelle on ne déduit rien, tolérances
d'entrée et sortie, grilles horaires par équipe, validation des heures
supplémentaires.

Mais ce réglage n'était lu que pour les journées badgées. **Les heures venant
d'une feuille papier importée se voyaient appliquer une heure de pause écrite
en dur.**

Chez Colorplast, dont la règle est de 30 minutes au-delà de 6 heures, la même
journée valait 8 h par le papier et 8 h 30 par le badgeage. Une demi-heure
d'écart par jour et par personne, en plein mois de comparaison entre les deux.

Les deux chemins suivent maintenant le même réglage, et changer un paramètre
recalcule aussitôt les imports.

**Reste :** ⚠️ **seules Colorplast et Mont Blanc Composite sont paramétrées.**
Dans les cinq autres, une journée badgée serait comptée sans aucune pause. À
régler.

---



## #28. Périodes d'essai 🟢

**Pourquoi vous ne le trouviez pas :** aucun des 241 salariés actifs n'avait de
période d'essai renseignée, et la carte était masquée passé 90 jours
d'ancienneté, donc invisible pour 239 sur 241, sans moyen d'activer le suivi
après coup.

Ce qui a changé :

- La carte est visible sur **tout salarié actif**
- Une page **« Périodes d'essai »** dans le menu Effectifs, en trois sections :
à confirmer, en cours, à qualifier
- Le barème est éditable dans les réglages société : durées par type de contrat
et statut, délai d'alerte, règle CDD
- Le renouvellement s'enregistre et repousse l'alerte

**Découverte au passage :** le calcul de la date de fin était **faux d'un
jour**. Une période de deux mois ouverte le 1er mars finissait le 1er mai au
lieu du 30 avril. Sans données en base, le bug n'a jamais eu d'effet, mais une
rupture notifiée le dernier jour affiché aurait été prononcée hors période
d'essai, donc requalifiée. Corrigé, y compris pour les fins de mois
(31 janvier + 1 mois = 28 février).

**Pas de reprise automatique :** les 33 embauches LEWIS du même mois sont une
reprise de données, pas 33 recrutements. Le rattrapage passe par la section
« à qualifier », limitée aux embauches de moins de huit mois.

*À savoir : activer le suivi sur un salarié entré il y a des années crée une
période déjà terminée à sa date d'entrée. Juste en droit, peu utile. La date
reste modifiable.*

Aucune période n'est encore saisie : on doit vous montrer la page.

---



## #29. Alertes de paie 🟢

Il restait du bruit, c'est corrigé. Trois sources :

- « 100 % de bulletins non validés » s'affichait chez les sociétés qui
n'utilisent pas le circuit de validation
- « Taux de versement mobilité introuvable » venait d'un vrai bug de calcul,
réglé
- Les alertes de convention collective sur lesquelles on ne peut rien faire ne
remontent plus en critique

Les vraies anomalies sont toujours signalées.

---



## #30. Assistant RH 🟢

**Le modèle d'IA n'était pas la cause.** Le problème venait de ce qu'on lui
donnait à lire : la convention collective enregistrée chez nous ne contenait ni
la période d'essai ni le préavis. Il ne pouvait donc pas répondre.

Les avenants de catégorie ont été ajoutés.

Les questions nominatives sont maintenant limitées au périmètre RH de la
personne qui pose la question.

---



## #31. Taux de prélèvement à la source 🟢 🟠

Oui, c'est bien l'interfaçage net-entreprises : la DGFiP renvoie le taux dans
le compte rendu qui suit chaque dépôt de DSN.

**EYWAI n'en récupérait aucun.** Le taux ne venait que de l'import des DSN
Cegid, sans date. Et 6 taux étaient faux, dont le vôtre, figé depuis janvier.

Un écran RH « Prélèvement à la source » est livré : liste, fraîcheur du taux,
origine, dépôt de fichier avec aperçu, export. **182 salariés ont leur taux** en
production.

Un salarié sans taux connu reçoit la grille par défaut au lieu de 0 %. Ça ne
concerne personne aujourd'hui, mais protège les futurs embauchés.

**Erreur trouvée en chemin :** le « type de taux 13 » est le barème par défaut,
pas un taux personnel, il se déduit de la paie du mois. Or le moteur le figeait
d'un mois sur l'autre : un salarié à 0 % en juin, sous le seuil, restait à 0 %
en juillet même si sa paie remontait. Il recalcule maintenant à chaque bulletin.

Les DSN de juin des sept sociétés ont été appliquées : 12 taux mis à jour, sans
échec. Cinq personnes déclarées dans ces DSN n'existent pas dans EYWAI : elles
sont signalées et ignorées, jamais créées.

**Il nous faut :**

- **L'accès net-entreprises.** Sans lui, les taux dépendent de fichiers qu'on
doit vous réclamer, et un nouvel embauché reste au taux par défaut.
- **Les DSN de juillet**, pas encore déposées sur le Drive.

---



## #32. Indemnité d'activité partielle 🟢

Chez LEWIS, 33 salariés étaient en activité partielle en juin, pour 17 510 €
d'indemnité.

Le calcul était bon et le montant enregistré, mais **le bulletin ne l'affichait
nulle part.** Le salarié voyait ses heures chômées retirées de son salaire,
sans voir ce qu'il touchait en compensation.

La ligne « Indemnité activité partielle » apparaît maintenant, à côté des
paniers.

Seuls les bulletins LEWIS sont concernés : 35 sur les deux derniers mois.

---



# Questions pour Elsa

**21 questions.** Les 10 premières t'ont déjà été envoyées sur WhatsApp le
7 août. Ce sont les mêmes phrases, pour que tu t'y retrouves. Les 11 suivantes
sont nouvelles.

Tu peux répondre simplement par numéro.

> **Les trois plus bloquantes : 1, 5 et 11.** La 1 empêche 148 salariés
> d'utiliser EYWAI. La 5 bloque tout le CSE. La 11 fausse les compteurs de
> congés de six sociétés.

## Déjà demandé le 7 août, en attente

### Adresses e-mail *(WhatsApp 16 h 58)*, point #4

**1.** « Tu peux m'envoyer un fichier par société avec nom + mail ? Perso ou
pro peu importe, mais vraie : case vide si tu ne l'as pas. »

### Compteur JTC *(WhatsApp 17 h 07)*, point #8

**2.** « Les soldes JTC 2026 des 75 salariés MBC. Je n'ai pas 2025 dans EYWAI,
je ne peux pas les recalculer. À partir de 2027 EYWAI le fera seul. »

*Tu as répondu « je demande 2025 ».*

**3.** « L'onglet "détail absences" du fichier Excel que tu cites dans la note,
je ne l'ai pas reçu. »

**4.** « Prorata absences : quelqu'un absent 31 jours, il a 3 JTC ou 2 ?
Autrement dit, les 30 jours c'est un seuil de déclenchement (on proratise
ensuite sur toute l'absence) ou une franchise (on ne compte que ce qui
dépasse) ? »

### Élus CSE *(WhatsApp 17 h 31)*, point #11

**5.** « Les dates d'élection et de fin de mandat par société (Cartol, LEWIS,
MBC). La colonne "Date d'entrée" du fichier est la date d'embauche. Le PV des
élections suffit. »

*Avec ça seul, je peux déjà charger les 8 élus.*

**6.** « Les suppléants (le fichier ne liste que des titulaires). »

**7.** « Le collège pour Cartol et LEWIS (renseigné pour MBC seulement). »

**8.** « Qui est secrétaire (et trésorier) dans chaque société. »

**9.** « Pour Colorplast, MAJI et Zone 404 : CSE ou PV de carence ? Celui de
Comitech est expiré depuis septembre 2023. »

### Accès net-entreprises, point #31

**10.** Les codes net-entreprises.

*Tu as répondu « j'ai demandé à Marie la compta, j'attends son retour ».*

> *La question sur le **type de taux 13**, posée à 17 h 10, n'est plus utile :
> on a trouvé la réponse nous-mêmes. C'est le barème par défaut. Tu peux
> l'oublier.*

## Pas encore demandé

### Provision congés payés, point #23

**11.** Le même état de provision CP que celui de Cartol, pour les six autres
sociétés. Ce n'est pas que pour la provision : c'est ce qui corrigera leurs
compteurs de congés.

**12.** Ton fichier Cartol contient 71 salariés, alors que 86 ont été payés en
juin. Les absents sont tous des embauches récentes. C'est voulu ou c'est un
oubli ?

### Entretiens annuels, point #25

**13.** Mont Blanc Composite ne colle pas : ton onglet compte 58 personnes, on
en a 75 en poste. 13 de tes noms nous sont inconnus, 30 des nôtres n'y figurent
pas. Lesquels sont concernés ?

**14.** As-tu des dates d'entretien professionnel ou de bilan à six ans ? Ce
sont les deux seuls entretiens obligatoires. Si elles n'existent nulle part,
tout le monde repart de zéro.

**15.** Mont Blanc Composite est bien sur un cycle de deux ans, alors que les
six autres sont annuelles ?

### Pointages, point #27

**16.** Quelle règle de pause pour les cinq sociétés qu'on n'a pas encore
réglées ? Seules Colorplast et Mont Blanc Composite le sont. Ailleurs, une
journée badgée serait comptée sans aucune pause.

### À demander au cabinet, points #20 et #26

**17.** La nomenclature officielle des codes de cotisation. Sans elle, notre
DSN reste non déposable.

**18.** Les comptes comptables des paniers, de la cantine et des IJSS.

**19.** Les identifiants Cegid, pour envoyer les écritures automatiquement au
lieu de déposer un fichier.

### Divers

**20.** Les DSN de juillet, à déposer sur le Drive. *(point #31)*

**21.** Quand cale-t-on le point paye avec Gaëlle ? *(point #18)*

---

## Note de suivi

Le point **#13** était vide (« idem ») et le **#27** figurait deux fois. Les
deux ont été nettoyés.

Les statuts ont été vérifiés le 7 août 2026 dans la base de production et dans
le code déployé, pas déduits du texte précédent. Deux écarts corrigés :

- **#28** était donné comme non déployé, alors qu'il l'est.
- **#4** n'avait aucun chiffre, alors que 148 adresses sont fabriquées.

Les points **#11**, **#12** et **#24** ont été confirmés en production. Une
première lecture les avait crus en attente, à cause d'anciennes branches de
travail restées ouvertes : leur contenu était déjà intégré.

Aucun chantier n'est « prêt mais pas en ligne ».