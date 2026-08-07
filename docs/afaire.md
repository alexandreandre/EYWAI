# EYWAI — Suivi des points

**Vérifié le 7 août 2026.** Chaque statut a été recontrôlé dans la vraie base
de production. Ce n'est pas une simple relecture.

## Les couleurs

| | |
| :--: | --- |
| 🟢 | **Terminé.** C'est en ligne, vous pouvez vous en servir. |
| 🟠 | **On attend quelque chose de vous.** |
| 🔴 | **À faire de notre côté.** |

Un point peut avoir deux couleurs. Exemple : la fonction marche, mais il
manque encore une donnée.

## Vue d'ensemble

| # | Sujet | |
| :--: | --- | :--: |
| 1 | Accès de Vanessa | 🟢 |
| 2 | Identifiants de Gaëlle et Vanessa | 🔴 |
| 3 | Fichier BIC | 🟢 🔴 |
| 4 | Adresses e-mail des salariés | 🟠 |
| 5 | Robin — droits de directeur | 🟢 |
| 6 | Dates des titres de séjour | 🟢 |
| 7 | Export Excel des titres de séjour | 🟢 |
| 8 | Compteur JTC | 🟢 🟠 |
| 9 | RTT affichés à tort chez Colorplast | 🟢 |
| 10 | Case « aménagement de poste » | 🟢 |
| 11 | Élus CSE | 🟢 🟠 |
| 12 | Exports CSE et BDES | 🟢 |
| 14 | Barème des médailles du travail | 🟢 |
| 15 | Prime de transport | 🟢 |
| 16 | Virement des acomptes | 🟢 |
| 17 | Environnement de test | 🟢 |
| 18 | Point paye avec Gaëlle | 🟠 |
| 19 | Fractionnement des congés | 🟢 |
| 20 | NIR et sortie DSN | 🟢 🟠 |
| 21 | Badgeuse Colorplast | 🟢 🔴 |
| 22 | Arrondi des congés au 31 mai | 🟢 |
| 23 | Export provision congés payés | 🟢 🟠 |
| 24 | Format du bulletin de paie | 🟢 |
| 25 | Entretiens annuels | 🟢 🟠 |
| 26 | Interfaçage comptable | 🟢 🟠 |
| 27 | Post-traitement des pointages | 🟢 🔴 |
| 28 | Suivi des périodes d'essai | 🟢 |
| 29 | Alertes de paie | 🟢 |
| 30 | Assistant RH | 🟢 |
| 31 | Taux de prélèvement à la source | 🟢 🟠 |
| 32 | Indemnité d'activité partielle | 🟢 |

---

## #1 — Accès de Vanessa 🟢

**Ce qu'on a fait**

Vanessa voit bien ses 7 sociétés. Elle n'a qu'à se reconnecter.

Le jour de la réunion, elle s'était connectée pile entre deux mises à jour des
droits. D'où les 2 sociétés sur 7. Un quart d'heure plus tard, c'était bon.

En vérifiant, on a trouvé plus grave. **Retirer un accès à quelqu'un ne
marchait pas vraiment.** La personne continuait à voir les sociétés qu'on lui
avait enlevées. C'est corrigé et nettoyé en production.

**Ce qu'il reste** — Rien.

---

## #2 — Identifiants de Gaëlle et Vanessa 🔴

**Ce qu'il reste** — Leur envoyer leurs identifiants par WhatsApp. C'est de
notre côté.

---

## #3 — Fichier BIC 🟢 🔴

**Ce qu'on a fait**

Le fichier n'était pas à attendre. Vous l'aviez envoyé le 27 juillet. Sept
fichiers Excel, une société chacun.

| Société | Lignes | BIC présents |
| --- | --: | --- |
| Zone 404 | 5 | 5 |
| Cartol | 91 | 91 |
| Colorplast | 7 | 7 |
| Comitech | 17 | 17 |
| MBC | 76 | 76 |
| MAJI | 10 | 10 |
| LEWIS | 39 | 0 *(RIB seul, tous convertibles)* |

**206 BIC** au total sur six sociétés. Vos données sont bonnes : tous les IBAN
sont valides.

Bonne nouvelle sur les virements. **Le BIC n'est plus obligatoire.** Depuis
2016, l'IBAN suffit. Nos exports partent sans BIC, avec un simple message
d'information.

**Ce qu'il reste**

Le blocage est chez nous. Notre import lit une seule colonne du fichier et
ignore celle d'à côté, où se trouve le BIC. On doit corriger ça avant de
charger.

---

## #4 — Adresses e-mail des salariés 🟠

**C'est notre plus gros blocage aujourd'hui.**

Sur 246 salariés en poste :

| | |
| --- | --: |
| Adresse réelle | 92 |
| **Adresse inventée par nous** | **148** |
| Aucune adresse | 6 |

Les adresses inventées finissent par `dsn-import.local`. Elles viennent de
l'import des DSN, qui refuse de créer un salarié sans adresse.

**Elles ne marchent pas.** Ces 148 salariés ne peuvent pas se connecter. Ils ne
peuvent pas recevoir leur bulletin non plus.

| Société | En poste | Adresses inventées |
| --- | --: | --: |
| LEWIS | 39 | **39** |
| Cartol Industrie | 90 | **77** |
| Mont Blanc Composite | 76 | 19 |
| Comitech Composite | 18 | 10 |
| Colorplast | 7 | 2 |
| MAJI | 10 | 1 |
| Zone 404 Mars | 6 | 0 |

**Ce qu'on attend de vous**

Les vraies adresses. On ne les invente jamais à partir d'un nom : on risquerait
d'envoyer un bulletin à un inconnu.

---

## #5 — Robin, droits de directeur 🟢

**Ce qu'on a fait**

Robin est collaborateur RH sur Zone 404, avec les droits d'un directeur.

Chez nous, « directeur » n'est pas un rôle. C'est un ensemble de droits : celui
d'Eric Noble, Damien Faucher et Lucas Chambert.

Concrètement, Robin garde son espace salarié. Il gagne en plus la vue RH et les
validations : valider un bulletin, approuver une note de frais ou une avance.

**Ce qu'il reste** — Rien.

---

## #6 — Dates des titres de séjour 🟢

**Ce qu'on a fait**

Les dates sont saisies. Sur 43 salariés concernés, **41 ont leur date**.
Vérifié en production ce jour.

Avant, il en manquait 34.

Le détail : 33 chez Mont Blanc Composite, 3 chez Cartol, 2 chez LEWIS, 2 chez
Zone 404, 1 chez Comitech.

Les alertes fonctionnent donc enfin pour de vrai.

**Ce qu'il reste** — Rien.

---

## #7 — Export Excel des titres de séjour 🟢

**Ce qu'on a fait**

Un bouton « Exporter en Excel » sur la page RH des titres de séjour.

Le fichier donne, pour chaque salarié : nom, prénom, matricule, société, poste,
date d'entrée, nationalité, type et numéro de titre, date d'expiration.

Et surtout le statut, avec le nombre de jours restants. Vous voyez tout de
suite qui est expiré ou sur le point de l'être.

L'export reprend exactement ce qui est à l'écran. Il reste limité à la société
sur laquelle vous travaillez.

**Ce qu'il reste** — Rien.

---

## #8 — Compteur JTC 🟢 🟠

**Ce qu'on a fait**

Votre note du 28 juillet fixait tout. On l'a suivie à la lettre :

- Le JTC est propre à Mont Blanc Composite. Personne d'autre n'y a droit.
- Trois jours par an au maximum.
- Gagnés sur l'année précédente, posés sur l'année en cours.
- Réduits si le salarié est entré en cours d'année, ou s'il a été absent plus
  de trente jours.
- Toujours arrondis vers le bas. Le solde vaut donc 0, 1, 2 ou 3.
- Un nouvel embauché n'a rien la première année.
- La journée de solidarité se prend sur un JTC. Sinon sur un congé payé.
- Ce qui n'est pas posé est payé au départ.
- **Le JTC s'affiche à côté des congés payés, jamais dedans.**

Le compteur est en ligne, en production comme sur le test.

**Il est éteint partout.** Vérifié ce jour : aucune des sept sociétés n'est
activée. Tant qu'on ne l'allume pas sur Mont Blanc Composite, rien ne change
nulle part.

Une fois allumé, le JTC devient un motif d'absence comme les congés payés. Avec
son solde à l'écran et sa colonne sur le bulletin. Le barème se règle depuis
**Entreprise > Congés**, sans passer par nous.

**Ce qu'on attend de vous**

1. **Les soldes de départ.** Le JTC de 2026 se gagne sur 2025. Or EYWAI ne
   contient rien avant janvier 2026. On ne peut pas recalculer ce que vos 75
   salariés ont acquis. Il nous les faut une fois. À partir de janvier 2027,
   EYWAI calculera seul.
2. **Une précision.** Un salarié absent 31 jours perd-il un JTC ? On a retenu
   la lecture stricte : il tombe à 2. À confirmer. Ça change le compte de tous
   ceux qui ont eu un arrêt d'un mois.
3. **L'onglet « détail absences »** de votre fichier Excel. On ne l'a jamais
   reçu. C'est lui qui dit quelles absences comptent.

**Ce qu'il reste chez nous**

Deux morceaux, laissés de côté exprès parce qu'ils touchent au calcul de la
paie : l'imputation automatique de la journée de solidarité, et le paiement du
solde restant quand un salarié part.

---

## #9 — RTT affichés à tort chez Colorplast 🟢

**Ce qu'on a fait**

Ce n'étaient pas des RTT posés. C'était un solde affiché à tort.

Sans paramétrage, le système donnait 10 RTT par an à tout le monde. Ça touchait
4 sociétés sur 7.

Maintenant, sans paramétrage, c'est 0. Les RTT se calculent depuis le forfait
annuel de chaque société : 214 jours chez Cartol, 216 ailleurs. Ils sont
réservés aux 19 cadres au forfait-jours.

Colorplast est bien à 0.

**Ce qu'il reste** — Rien.

---

## #10 — Case « aménagement de poste » 🟢

**Ce qu'on a fait**

Quand vous enregistrez une visite médicale comme réalisée, vous pouvez cocher
« aménagement de poste ».

La case remonte ensuite en tête de la fiche du salarié, en lecture seule.

La visite reste le seul endroit où on saisit. Corriger la visite met bien à
jour la fiche. C'est volontairement une simple case, sans motif ni date de fin.

**Ce qu'il reste** — Rien.

---

## #11 — Élus CSE 🟢 🟠

**Ce qu'on a fait**

Vous aviez envoyé votre liste le 2 août : 8 élus titulaires. 2 chez Cartol,
2 chez LEWIS, 4 chez Mont Blanc Composite.

On a retrouvé les 8 parmi nos salariés. Y compris celle qui figure chez vous
sous son nom d'usage, alors qu'on la connaît sous son nom de naissance.

L'outil de reprise est prêt et testé. Il relit votre fichier, retrouve les
salariés, et refuse d'écrire si une seule ligne est douteuse. Il ne crée jamais
deux fois le même mandat. Il refuse aussi de créer un mandat pour quelqu'un qui
a quitté l'entreprise.

Répétition faite avec des dates provisoires : les 8 mandats se créent, et
relancer n'en crée aucun de plus.

**Ce qu'on attend de vous**

Il manque le mandat lui-même.

La colonne « date d'entrée » de votre fichier est la date d'embauche, pas la
date d'élection. Les huit dates correspondent au jour près à ce qu'on a déjà.

Sans date de début et de fin de mandat, on ne peut rien enregistrer. Ce sont
elles qui déclenchent les alertes de fin de mandat et le calcul des heures de
délégation.

Il nous faut aussi :

- Les **suppléants**. Vous n'avez listé que des titulaires.
- Le **collège** pour Cartol et LEWIS.
- Le nom du **secrétaire** de chaque CSE.
- Le cas de **Colorplast, MAJI et Zone 404**. Elles n'ont ni élu ni
  procès-verbal de carence. Celui de Comitech est périmé depuis septembre 2023.

**Ce qu'il reste chez nous** — Rien. L'outil est en ligne depuis le 7 août. Il
attend vos dates pour tourner. Aucun élu n'est enregistré à ce jour.

---

## #12 — Exports CSE et BDES 🟢

**Ce qu'on a fait**

Les erreurs que vous constatiez sont trouvées et corrigées. On n'a pas eu
besoin de votre fichier : le défaut se reproduisait tout seul.

**Trois problèmes :**

1. L'export des élus affichait « Actif » pour tout le monde. Même les mandats
   terminés depuis des années. Et la colonne « jours restants » était vide.
   Le programme n'arrivait pas à lire ses propres dates, l'erreur passait
   inaperçue, et il retombait sur « Actif ».
2. Les dates s'affichaient en écriture machine dans les trois exports.
3. **L'export des heures de délégation ne marchait pas du tout.** Il plantait à
   chaque tentative, depuis toujours. Personne ne l'avait signalé. On en déduit
   qu'il n'avait jamais servi.

Maintenant, un mandat clos en janvier 2023 sort « Expiré », avec le nombre de
jours de dépassement. Un mandat qui approche de son terme est signalé trois
mois avant.

**Un défaut plus grave, trouvé en relisant.** Une société dont tous les mandats
sont expirés serait apparue « CSE en place, conforme » sur son tableau de bord.
Un faux feu vert sur une obligation légale. Corrigé.

**Ce qu'il reste** — Rien. C'est en ligne depuis le 7 août.

---

## #14 — Barème des médailles du travail 🟢

**Ce qu'on a fait**

Le barème s'édite bien depuis **Entreprise > Paie** : les paliers 20, 30, 35 et
40 ans, et leurs montants. Vous pouvez aussi ajuster le montant au moment de
valider une médaille.

On a ajouté un réglage **base d'ancienneté par société**. C'est pour les cas de
reprise d'ancienneté, où la date d'entrée ne reflète pas les droits réels.

Et surtout : la détection ne tournait qu'à l'ouverture d'une fiche salarié.
Elle passe en **scan automatique tous les jours**.

**Ce qu'il reste** — Rien.

---

## #15 — Prime de transport 🟢

**Ce qu'on a fait**

Le montant se règle sur la fiche du salarié, avec une date d'effet.

Il génère chaque mois une ligne d'indemnité trajet dans les saisies mensuelles.
Vous pouvez la modifier ou la supprimer mois par mois. **Une correction
manuelle n'est jamais écrasée.**

Elle est proratisée à l'entrée et à la sortie. Elle est retirée si le salarié
est absent tout le mois. Une alerte prévient si on dépasse le plafond exonéré.

**Ce qu'il reste** — Rien.

---

## #16 — Virement des acomptes 🟢

**Ce qu'on a fait**

Un export « Virement acomptes », séparé de celui des salaires. Avec sa propre
date d'exécution, ses propres références bancaires et son propre historique.

Deux usages :

- Sortir l'ordre de virement à envoyer à la banque, avec les acomptes approuvés
  et pas encore payés.
- Sortir la liste des acomptes déjà versés sur une période.

Les BIC manquants ne bloquent plus l'envoi à la banque.

**Ce qu'il reste** — Rien.

---

## #17 — Environnement de test 🟢

**Ce qu'on a fait**

Il existe un second EYWAI complet, avec sa propre base.

Il reçoit une copie des données réelles de la production. La copie se
déclenche à la main, depuis le bandeau orange.

**Jamais dans l'autre sens.** Tout ce que vous faites dans le test — une
démission, une suppression, un bulletin — reste dans le test. Ça disparaît à la
copie suivante.

Comme les données sont réelles, trois sorties sont verrouillées :

- Les e-mails partent tous vers une seule boîte. Le service refuse même de
  démarrer sans cette redirection.
- La signature électronique est refusée.
- Le dépôt de DSN est refusé.

**Ce qu'il reste** — Rien.

---

## #18 — Point paye avec Gaëlle 🟠

**Ce qu'on attend de vous** — Organiser la réunion.

---

## #19 — Fractionnement des congés 🟢

**Ce qu'on a fait**

Ce n'était pas propre. **Sept défauts** faussaient le calcul. Dont un qui
rendait 0 jour pour les 221 salariés de MBC.

Tout est corrigé.

C'est maintenant paramétrable par société dans **Entreprise > Congés** :
méthode de calcul, barème, exclusion des cadres au forfait-jours.

Le calcul est automatique. Mais rien n'est jamais crédité sans votre
validation.

Bonne nouvelle : aucune société n'était paramétrée. Donc aucun salarié n'a été
touché par ces erreurs.

**Ce qu'il reste** — Rien. Vous pouvez paramétrer les sociétés quand vous
voulez.

---

## #20 — NIR et sortie DSN 🟢 🟠

**Ce qu'on a fait**

**Les NIR sont bons.** 240 actifs, aucun vide, clé de contrôle correcte
partout. 274 des 275 personnes des DSN du cabinet correspondent au chiffre
près.

Trois anomalies viennent du cabinet, et on les avait recopiées :

- 8 salariés déclarés avec un sexe que leur propre NIR contredit.
- 2 dates de naissance différentes.
- 1 salarié déclaré chez Cartol depuis janvier, qui n'existe pas dans EYWAI.

**Notre sortie DSN n'était pas déposable.** Il manquait 100 à 120 rubriques
selon la société. Dont le bloc total, sans lequel net-entreprises rejette le
fichier.

L'en-tête, l'identité et les contrats sont maintenant conformes au fichier du
cabinet. Vérifié automatiquement sur cinq sociétés.

**Ce qu'on attend de vous**

La nomenclature officielle des codes de cotisation, à demander au cabinet.

Il reste les cotisations, les agrégés URSSAF et la prévoyance. Sans cette
nomenclature, on déclarerait des montants faux.

En attendant, l'export est marqué « non déposable » et le dit à l'écran.

---

## #21 — Badgeuse Colorplast 🟢 🔴

**Ce qu'on a fait**

D'abord une surprise : **Colorplast n'a pas de badgeuse du tout.**

Ce qu'on recevait, c'étaient des feuilles papier remplies au stylo, puis
scannées ou photographiées. La qualité se dégradait. Les totaux avaient disparu
depuis le printemps.

Les salariés vont donc badger depuis leur téléphone. Le bouton n'existait pas.
Il est en ligne.

Le système déduit la pause déjeuner comme ils le font vraiment : 30 minutes
seulement quand la journée dépasse 6 heures. Une demi-journée n'en subit
aucune. Vérifié sur leurs propres feuilles : les trois semaines complètes
retombent au centième.

**Rien ne part en paie tout de suite.** Pendant un mois, la badgeuse et le
papier tournent en parallèle. On compare chaque semaine. Le papier a le dernier
mot.

**Ce qu'il reste**

Le vrai point d'attention n'est pas technique. **Aucun salarié de Colorplast ne
s'est jamais connecté à EYWAI.** Il faut les connecter.

*Petite différence à noter : on compte 7 salariés en poste chez Colorplast. Le
compte rendu de réunion en annonçait 9.*

---

## #22 — Arrondi des congés au 31 mai 🟢

**Ce qu'on a fait**

Vérifié, il n'y a rien à corriger.

On arrondit toujours **au supérieur**, dès qu'il y a une fraction. C'est à
l'avantage du salarié, et conforme à l'usage paie.

| Mois sur la période *(1er juin → 31 mai)* | Calcul | Résultat |
| --- | --: | --: |
| 1 *(bulletin de juin)* | 2,5 | **3** |
| 7 *(au 31/12)* | 17,5 | **18** |
| 8 *(au 31/01)* | 20,0 | **20** |
| 12 *(période complète)* | 30,0 | **30** |

Le mois n'est pas découpé en jours. Tout mois commencé compte pour 1. Une
embauche le 15 juin fait compter juin en entier.

Le taux est paramétrable par société. Par défaut 2,5 jours ouvrables par mois.

**Ce qu'il reste** — Rien.

---

## #23 — Export provision congés payés 🟢 🟠

**Ce qu'on a fait**

Le fichier exemple n'était pas à demander. Vous l'aviez envoyé le 21 juillet,
puis le 27.

C'est un état du cabinet pour Cartol : 71 salariés, 394 121 €.

On l'a décortiqué plutôt que de vous relancer. La méthode du cabinet est
entièrement retrouvée. Elle tombe juste au centime sur les 71 lignes.

Le calcul, par salarié : solde de congés × journée de salaire + charges
patronales.

L'export est dans **Exports > Exports RH**, sous « Provision congés payés ».
Vous choisissez un mois. Vous obtenez un Excel avec une ligne par salarié et un
total.

On a ajouté trois colonnes que le cabinet n'a pas : la date d'entrée, le nombre
de mois de paie utilisés, et une colonne « anomalie ». Vous voyez d'où sort
chaque chiffre, au lieu de croire le fichier sur parole.

**Le premier essai sortait 31 % en dessous du cabinet.** Ce n'était pas le
calcul. Le solde de l'année précédente n'avait jamais été repris : chez nous il
valait 25 jours pour tout le monde, alors qu'en réalité il va de 3 à 88 jours.

Sauf que ces soldes étaient **dans votre fichier**, une colonne du même
document. On les a relus et remis dans EYWAI. Les 71 salariés de Cartol ont
maintenant leur vrai report.

Vérifié nom par nom : BOISSINOT 88 jours, QUERAT 81, BERTAUD 28. L'écart sur
les soldes est passé de 6,2 jours à un centième de jour. L'écart en euros de
31 % à 12 %.

**Les 12 % restants ne peuvent pas être réglés.** Le salaire de référence se
calcule sur douze mois de paie, et on n'en a que six. Ça se réglera tout seul
en juin 2027. En attendant, l'export affiche en permanence un avertissement. On
préfère ça à un montant faux présenté comme sûr.

Ce qui est juste : le solde de l'année en cours (4,17 jours contre 4,16 chez le
cabinet, simple arrondi) et le taux de charges de chaque salarié.

Deux autres corrections. Zone 404 et MAJI n'ont aucun bulletin dans EYWAI :
leur provision sortait à zéro euro sans rien annoncer. On retombe maintenant
sur le salaire du contrat (9 860 € et 22 602 €). Et un fichier entièrement à
zéro n'est plus produit du tout.

En production depuis le 7 août.

**Ce qu'on attend de vous**

1. **Le même état pour les six autres sociétés.** Ce n'est pas que pour la
   provision : c'est ce qui corrigera leurs compteurs de congés.
2. **Une question.** Votre fichier Cartol ne contient que 71 salariés, alors
   que 86 ont été payés en juin. Les absents sont tous des embauches récentes.
   Nous, on les garde : ils ont des congés acquis, donc une dette.

---

## #24 — Format du bulletin de paie 🟢

**Ce qu'on a fait**

Le bulletin sort au format du cabinet. Une page, sobre.

- Les compteurs de congés en haut à gauche.
- L'adresse du salarié à droite.
- La colonne des cumuls sur le côté.
- Le net à payer en bas.

Les rubriques portent les mêmes codes que chez Cegid : Q100 Santé, Q300
Retraite, etc.

Ce qu'on affichait en plus — primes, notes de frais, cumuls annuels, soldes
RTT — se fond dans le gabarit au lieu d'occuper ses propres sections.

À l'écran, l'aperçu d'un bulletin en cours de modification montre exactement le
document qui sortira.

**Aucun montant ne change.** Les bulletins déjà émis restent tels quels.

Au passage, on a ajouté une mention obligatoire qui manquait depuis le début :
l'évolution de la rémunération liée à la suppression des cotisations chômage et
maladie.

**Ce qu'il reste** — Rien. C'est en ligne depuis le 7 août. Les bulletins
générés à partir de maintenant sortent au nouveau format.

---

## #25 — Entretiens annuels 🟢 🟠

**Ce qu'on a fait**

Le fichier n'était pas à attendre. Vous aviez envoyé « Planif_entretiens.xlsx »
le 27 juillet.

256 lignes, les sept sociétés. Et surtout la règle de chacune :

| Société | Règle |
| --- | --- |
| Cartol | Novembre |
| Comitech, Colorplast, LEWIS | Octobre |
| MAJI | Décembre |
| Zone 404 | À la date d'ancienneté |
| Mont Blanc Composite | Octobre, tous les deux ans |

Il fallait commencer par là. La page des entretiens existait depuis longtemps —
convocation en PDF, signature électronique, types d'entretien légaux. **Mais
elle n'a jamais servi.** Pas un seul entretien enregistré en production. Aucun
compteur légal ne courait.

**Ce qui est livré (7 août).** Chaque société a maintenant sa campagne
d'entretiens réglable dans **Entreprise > Paie** : le mois où l'on convoque
tout le monde (ou « à la date d'ancienneté »), et tous les combien.

C'est le point important pour la suite. **L'an prochain, EYWAI proposera seul
la campagne suivante, et vous pourrez changer le mois sans nous.** Tant qu'une
société n'est pas réglée, rien ne bouge chez elle. Comme pour le JTC.

Jusqu'ici, la liste des entretiens à planifier ne regardait que les cadres et
les forfaits jour, soit une poignée de gens. Une fois la campagne réglée, elle
couvre tout l'effectif, avec la date attendue pour chacun et les retards en
tête de liste.

**La reprise est prête et vérifiée à blanc :** 211 entretiens à planifier et 43
entretiens passés.

Le programme ne recopie pas votre colonne « à planifier ». Il recalcule chaque
échéance avec la règle de la société, puis compare. Sur les 211 lignes,
**aucun écart**. Notre calcul et votre fichier tombent exactement pareil.

Il refuse d'écrire au moindre désaccord. Il ne crée jamais deux fois le même
entretien. Il ignore les salariés partis.

Deux choix volontaires. Les 32 lignes qui correspondent à des gens déjà sortis
(21 Cartol, 5 Comitech, 4 LEWIS, 2 Colorplast) sont ignorées. Et pour les
entretiens passés, votre fichier ne donne qu'une **année**, jamais une date :
on enregistre l'année sans inventer un jour. C'est suffisant pour faire courir
le délai de deux ans.

**Ce qu'on attend de vous**

1. **Mont Blanc Composite ne colle pas.** Votre onglet compte 58 personnes, on
   en a 75 en poste. 13 noms de votre liste nous sont inconnus, et 30 des
   nôtres n'y figurent pas. Il faut trancher avant de charger cette société.
2. **Aucune date d'entretien professionnel ni de bilan à six ans** dans le
   fichier. Ce sont pourtant les deux seuls entretiens obligatoires. Si ces
   dates existent quelque part, il nous les faut. Sinon tout le monde repart de
   zéro.
3. **Confirmer le cycle de deux ans** de Mont Blanc Composite, alors que les
   six autres sont annuelles.

**Ce qu'il reste chez nous** — Lancer la reprise, une fois ces réponses
obtenues. Aujourd'hui, aucun entretien n'est écrit en base et aucune société
n'est encore réglée.

---

## #26 — Interfaçage comptable 🟢 🟠

**Ce qu'on a fait**

L'écriture comptable de paie est maintenant juste et équilibrée.

Elle sort aux comptes du cabinet, ventilée par organisme — URSSAF, retraite,
mutuelle, prévoyance — au lieu d'un compte fourre-tout. Et elle est agrégée par
compte, comme le fait le cabinet : une vingtaine de lignes au lieu de 137.

Colorplast, Comitech et Cartol tombent au centime.

**Avant, aucune société ne tombait juste.** Il manquait jusqu'à 114 000 € d'un
côté de la balance.

Un fichier qui ne s'équilibre pas n'est plus produit du tout. L'écran dit quel
compte manque.

**Ce qu'on attend de vous**

- Les comptes du cabinet pour les **paniers**, la **cantine** et les **IJSS**.
- Les **identifiants Cegid**, pour envoyer les écritures automatiquement au
  lieu de déposer un fichier à la main.

---

## #27 — Post-traitement des pointages 🟢 🔴

**Ce qu'on a fait**

Tout se règle par société dans **Entreprise > Paie > « Pointages & imports »** :
pause repas déduite, durée en dessous de laquelle on ne déduit rien, tolérance
d'entrée et de sortie, grilles horaires par équipe, validation des heures
supplémentaires.

Mais ce réglage n'était lu que pour les journées badgées. **Les heures venant
d'une feuille papier importée se voyaient appliquer une heure de pause écrite
en dur dans le programme.**

Chez Colorplast, dont la règle est de 30 minutes au-delà de 6 heures, la même
journée valait 8 h par le papier et 8 h 30 par le badgeage. Une demi-heure
d'écart par jour et par personne — en plein mois de comparaison entre les deux.

Les deux chemins suivent maintenant le même réglage. Et changer un paramètre
recalcule aussitôt les imports, au lieu d'attendre le lendemain.

**Ce qu'il reste**

⚠️ **Seules Colorplast et Mont Blanc Composite sont paramétrées.** Dans les
cinq autres sociétés, une journée badgée serait comptée sans aucune pause. Il
faut les régler.

---

## #28 — Suivi des périodes d'essai 🟢

**Ce qu'on a fait**

**Pourquoi vous ne le trouviez pas.** Aucun des 241 salariés actifs n'avait de
période d'essai renseignée. Et la carte de la fiche était masquée passé 90 jours
d'ancienneté — donc invisible pour 239 salariés sur 241. Il n'y avait aucun
moyen d'activer le suivi après la création.

Ce qui a été fait :

- La carte est visible sur **tout salarié actif**.
- Une page **« Périodes d'essai »** apparaît dans le menu Effectifs. En trois
  sections : à confirmer, en cours, à qualifier.
- Le barème devient éditable dans les réglages société : durées par type de
  contrat et statut, délai d'alerte, règle CDD.
- Le renouvellement s'enregistre et repousse l'alerte.

**Une découverte au passage.** Le calcul de la date de fin était faux d'un jour.
Une période de deux mois ouverte le 1er mars finissait le 1er mai au lieu du
30 avril.

Sans données en base, ce bug n'a jamais eu d'effet. Mais une rupture notifiée
le dernier jour affiché aurait été prononcée hors période d'essai — donc
requalifiée. C'est corrigé, y compris pour les embauches de fin de mois
(31 janvier + 1 mois = 28 février, pas le 27).

**Pas de reprise automatique.** Les 33 embauches LEWIS du même mois sont une
reprise de données, pas 33 recrutements. Le rattrapage passe par la section
« à qualifier », limitée aux embauches de moins de huit mois.

À savoir : la carte étant visible partout, activer le suivi sur un salarié
entré il y a des années crée une période déjà terminée à sa date d'entrée.
C'est juste en droit mais peu utile. La date de début reste modifiable.

**Ce qu'il reste** — Rien de technique. C'est en ligne depuis le 7 août. Aucune
période n'est encore saisie : on doit vous montrer la page.

---

## #29 — Alertes de paie 🟢

**Ce qu'on a fait**

Vérifié : il restait du bruit, c'est corrigé. Trois sources traitées :

- « 100 % de bulletins non validés » s'affichait chez les sociétés qui
  n'utilisent tout simplement pas le circuit de validation.
- « Taux de versement mobilité introuvable » venait d'un vrai bug de calcul du
  taux. Il est réglé.
- Les alertes de convention collective sur lesquelles on ne peut rien faire
  (règles absentes, prime d'ancienneté non éligible) ne remontent plus en
  critique.

Les vraies anomalies sont toujours signalées.

**Ce qu'il reste** — Rien.

---

## #30 — Assistant RH 🟢

**Ce qu'on a fait**

**Le modèle d'IA n'était pas la cause.** Le problème venait de ce qu'on lui
donnait à lire : la convention collective enregistrée chez nous ne contenait ni
la période d'essai ni le préavis. L'assistant ne pouvait donc pas répondre.

Les avenants de catégorie ont été ajoutés.

Et les questions nominatives sont maintenant limitées au périmètre RH de la
personne qui pose la question. Un rôle personnalisé ne voit que ce que ses
droits autorisent.

**Ce qu'il reste** — Rien.

---

## #31 — Taux de prélèvement à la source 🟢 🟠

**Ce qu'on a fait**

Oui, c'est bien l'interfaçage net-entreprises. La DGFiP renvoie le taux dans le
compte rendu qui suit chaque dépôt de DSN.

**EYWAI n'en récupérait aucun.** Le taux ne venait que de l'import des DSN
Cegid, sans date. Et 6 taux étaient faux, dont le vôtre, figé depuis janvier.

Un écran RH « Prélèvement à la source » est livré : la liste, la fraîcheur du
taux, son origine, le dépôt de fichier avec aperçu, l'export.

**182 salariés ont aujourd'hui leur taux** en production. L'import DSN
rafraîchit désormais le taux même quand il ignore la fiche.

Un salarié sans taux connu se voit appliquer la grille par défaut, au lieu de
0 %. Ça ne concerne aucun salarié actuel, mais ça protège les futurs embauchés.

**Une erreur trouvée en chemin.** Le « type de taux 13 » est le barème par
défaut, pas un taux personnel. Il se déduit de la paie du mois. Or le moteur le
figeait d'un mois sur l'autre : un salarié à 0 % en juin, parce qu'il était sous
le seuil, restait à 0 % en juillet même si sa paie remontait. Il recalcule
maintenant à chaque bulletin.

Les DSN de juin des sept sociétés ont été appliquées : 12 taux mis à jour, sans
aucun échec. Cinq personnes déclarées dans ces DSN n'existent pas dans EYWAI :
elles sont signalées et ignorées, jamais créées.

**Ce qu'on attend de vous**

- **L'accès à net-entreprises.** Sans lui, les taux dépendent encore de
  fichiers qu'on doit vous réclamer. Et un nouvel embauché reste au taux par
  défaut au lieu de basculer sur le sien.
- **Les DSN de juillet**, pas encore déposées sur le Drive.

---

## #32 — Indemnité d'activité partielle 🟢

**Ce qu'on a fait**

Chez LEWIS, 33 salariés étaient en activité partielle en juin. 17 510 €
d'indemnité.

Le calcul était bon et le montant bien enregistré. Mais **le bulletin ne
l'affichait nulle part.** Le salarié voyait ses heures chômées retirées de son
salaire, sans voir ce qu'il touchait en compensation.

C'est corrigé. La ligne « Indemnité activité partielle » apparaît maintenant
avec son montant, à côté des paniers.

Seuls les bulletins de LEWIS sont concernés : 35 sur les deux derniers mois.
Aucune autre société n'avait ce cas.

**Ce qu'il reste** — Rien.

---

## Note de suivi

Le point **#13** était vide dans le compte rendu d'origine (« idem »). Le point
**#27** y figurait deux fois à l'identique. Les deux ont été nettoyés.

Les statuts « en production » ont été vérifiés le 7 août 2026 dans la vraie base
de production et dans le code réellement déployé. Ils ne sont pas déduits du
texte précédent. Deux écarts corrigés :

- Le **#28** était présenté comme non déployé, alors qu'il l'est.
- Le **#4** n'avait aucun chiffre, alors que 148 adresses sont inventées.

Les points **#11**, **#12** et **#24** ont été confirmés en production le
7 août. Une première lecture les avait crus en attente, à cause d'anciennes
branches de travail restées ouvertes : leur contenu avait en réalité déjà été
intégré. Vérification refaite sur le code déployé, pas sur les branches.

Il ne reste donc aucun chantier « prêt mais pas en ligne ».
