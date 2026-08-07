# EYWAI — Suivi des points

**Vérifié le 7 août 2026** dans la vraie base de production.

| | |
| :--: | --- |
| 🟢 | **Terminé et en ligne.** Rien à faire. |
| 🟠 | **On attend quelque chose de toi.** |
| 🔴 | **À faire de notre côté.** |

## Vue d'ensemble

| # | Sujet | | # | Sujet | |
| :--: | --- | :--: | :--: | --- | :--: |
| 1 | Accès de Vanessa | 🟢 | 19 | Fractionnement des congés | 🟢 |
| 2 | Identifiants Gaëlle / Vanessa | 🔴 | 20 | NIR et sortie DSN | 🟢 🟠 |
| 3 | Fichier BIC | 🟢 🔴 | 21 | Badgeuse Colorplast | 🟢 🔴 |
| 4 | **Adresses e-mail** | 🟠 | 22 | Arrondi des congés | 🟢 |
| 5 | Robin — droits directeur | 🟢 | 23 | Provision congés payés | 🟢 🟠 |
| 6 | Titres de séjour | 🟢 | 24 | Format du bulletin | 🟢 |
| 7 | Export titres de séjour | 🟢 | 25 | Entretiens annuels | 🟢 🟠 |
| 8 | Compteur JTC | 🟢 🟠 | 26 | Interfaçage comptable | 🟢 🟠 |
| 9 | RTT Colorplast | 🟢 | 27 | Pointages | 🟢 🔴 |
| 10 | Aménagement de poste | 🟢 | 28 | Périodes d'essai | 🟢 |
| 11 | Élus CSE | 🟢 🟠 | 29 | Alertes de paie | 🟢 |
| 12 | Exports CSE et BDES | 🟢 | 30 | Assistant RH | 🟢 |
| 14 | Médailles du travail | 🟢 | 31 | Prélèvement à la source | 🟢 🟠 |
| 15 | Prime de transport | 🟢 | 32 | Activité partielle | 🟢 |
| 16 | Virement des acomptes | 🟢 | | | |
| 17 | Environnement de test | 🟢 | | | |
| 18 | Point paye avec Gaëlle | 🟠 | | | |

**9 sujets attendent une réponse de toi :** 4, 8, 11, 18, 20, 23, 25, 26, 31.
**Aucun chantier n'est en attente de mise en ligne.**

---

# 🟠 Ce qu'on attend de toi

## #4 — Les vraies adresses e-mail

> **C'est notre plus gros blocage.**

Sur 246 salariés : **92 adresses réelles, 148 inventées par nous, 6 vides.**

Les inventées finissent par `dsn-import.local` — l'import des DSN refuse de créer
un salarié sans adresse. **Elles ne marchent pas :** ces 148 salariés ne peuvent
ni se connecter, ni recevoir leur bulletin.

| Société | En poste | Inventées |
| --- | --: | --: |
| Cartol | 90 | **77** |
| LEWIS | 39 | **39** |
| Mont Blanc Composite | 76 | 19 |
| Comitech | 18 | 10 |
| Colorplast | 7 | 2 |
| MAJI | 10 | 1 |
| Zone 404 | 6 | 0 |

On ne les invente jamais à partir d'un nom : on risquerait d'envoyer un bulletin
à un inconnu.

## #8 — Les soldes JTC de départ

- **Les soldes de tes 75 salariés de MBC.** Le JTC 2026 se gagne sur 2025, or
  EYWAI ne contient rien avant janvier 2026. Une seule fois suffit : ensuite
  EYWAI calcule seul.
- **Un salarié absent 31 jours perd-il un JTC ?** On a retenu la lecture stricte
  (il tombe à 2). À confirmer — ça change le compte de tous ceux qui ont eu un
  arrêt d'un mois.
- **L'onglet « détail absences »** de ton Excel, jamais reçu. C'est lui qui dit
  quelles absences comptent.

## #11 — Les mandats des élus CSE

Tes 8 titulaires sont retrouvés. Il manque le mandat lui-même :

- **Les dates d'élection et de fin de mandat.** Ta colonne « date d'entrée » est
  la date d'embauche. Sans ces dates, rien ne s'enregistre — ce sont elles qui
  déclenchent les alertes et les heures de délégation.
- **Les suppléants** (tu n'as listé que des titulaires).
- **Le collège** pour Cartol et LEWIS.
- **Le secrétaire** de chaque CSE.
- **Colorplast, MAJI, Zone 404 :** ni élu ni PV de carence. Celui de Comitech est
  périmé depuis septembre 2023.

## #18 — Point paye avec Gaëlle

Réunion à organiser.

## #20 — La nomenclature des codes de cotisation

À demander au cabinet. Sans elle, on déclarerait des montants faux sur les
cotisations, les agrégés URSSAF et la prévoyance.

## #23 — La provision CP des six autres sociétés

- **Le même état que pour Cartol.** Ce n'est pas que pour la provision : c'est ce
  qui corrigera leurs compteurs de congés.
- **Pourquoi 71 salariés** dans ton fichier Cartol, alors que 86 ont été payés en
  juin ? Les absents sont des embauches récentes. Nous, on les garde : ils ont
  des congés acquis, donc une dette.

## #25 — Trois questions sur les entretiens

- **Mont Blanc Composite ne colle pas.** Ton onglet compte 58 personnes, on en a
  75. 13 noms inconnus chez nous, 30 des nôtres absents de ta liste. À trancher
  avant de charger cette société.
- **Aucune date d'entretien professionnel ni de bilan à six ans** — ce sont
  pourtant les deux seuls obligatoires. Si elles existent, il nous les faut.
- **Confirmer le cycle de deux ans** de MBC, alors que les six autres sont
  annuelles.

## #26 — Trois comptes comptables

Les comptes du cabinet pour les **paniers**, la **cantine** et les **IJSS**. Plus
les **identifiants Cegid**, pour envoyer les écritures automatiquement.

## #31 — L'accès à net-entreprises

Sans lui, les taux dépendent de fichiers qu'on doit te réclamer, et un nouvel
embauché reste au taux par défaut. **Les DSN de juillet** ne sont pas encore sur
le Drive.

---

# 🔴 Ce qu'on doit faire

| # | Action |
| :--: | --- |
| 2 | Envoyer leurs identifiants à Gaëlle et Vanessa. |
| 3 | Corriger notre import de BIC : il lit une colonne et ignore celle d'à côté. |
| 8 | Journée de solidarité et paiement du solde au départ *(touche au calcul de la paie)*. |
| 21 | Connecter les salariés de Colorplast — **aucun ne s'est jamais connecté**. |
| 27 | Paramétrer les pointages des 5 sociétés restantes. |

---

# 🟢 Ce qui est fait

## #1 — Accès de Vanessa

Elle voit ses 7 sociétés. Le jour de la réunion, elle s'était connectée entre
deux mises à jour des droits ; c'était bon un quart d'heure après.

> **Trouvé au passage :** retirer un accès ne marchait pas vraiment. La personne
> continuait à voir les sociétés qu'on lui avait enlevées. Corrigé.

## #3 — Fichier BIC

Tu l'avais envoyé le 27 juillet. **206 BIC**, tes données sont bonnes, tous les
IBAN sont valides.

| Société | Lignes | BIC |
| --- | --: | --- |
| Cartol | 91 | 91 |
| MBC | 76 | 76 |
| LEWIS | 39 | 0 *(RIB seul, tous convertibles)* |
| Comitech | 17 | 17 |
| MAJI | 10 | 10 |
| Colorplast | 7 | 7 |
| Zone 404 | 5 | 5 |

**Le BIC n'est plus obligatoire** pour les virements : depuis 2016, l'IBAN
suffit.

## #5 — Robin, droits de directeur

Collaborateur RH sur Zone 404 avec les droits d'un directeur — soit ceux d'Eric
Noble, Damien Faucher et Lucas Chambert. Il garde son espace salarié, et gagne la
vue RH plus les validations : bulletin, note de frais, avance.

## #6 — Dates des titres de séjour

**41 salariés sur 43 ont leur date**, contre 9 avant. 33 chez MBC, 3 Cartol,
2 LEWIS, 2 Zone 404, 1 Comitech. Les alertes fonctionnent enfin pour de vrai.

## #7 — Export Excel des titres de séjour

Bouton sur la page RH. Contient l'identité, la société, le poste, la nationalité,
le type et le numéro de titre, la date d'expiration — **et le statut avec les
jours restants**, pour voir tout de suite qui est expiré.

## #8 — Compteur JTC

Ta note du 28 juillet, suivie à la lettre :

- Propre à Mont Blanc Composite, 3 jours par an maximum.
- Gagnés sur l'année précédente, posés sur l'année en cours.
- Réduits si entrée en cours d'année ou absence de plus de 30 jours.
- Arrondis vers le bas : le solde vaut 0, 1, 2 ou 3.
- Rien la première année. Journée de solidarité prise dessus, sinon sur un CP.
- Non posé = payé au départ.
- **Affiché à côté des congés payés, jamais dedans.**

**Il est éteint sur les 7 sociétés.** Tant qu'on ne l'allume pas sur MBC, rien ne
change nulle part. Barème réglable dans **Entreprise > Congés**.

## #9 — RTT affichés à tort chez Colorplast

Pas des RTT posés, mais un solde affiché à tort : sans paramétrage, le système
donnait 10 RTT par an à tout le monde — **4 sociétés sur 7 touchées**.

Maintenant 0 par défaut. Les RTT se calculent depuis le forfait annuel (214 j
chez Cartol, 216 ailleurs) et sont réservés aux 19 cadres au forfait-jours.

## #10 — Case « aménagement de poste »

Cochable en enregistrant une visite médicale comme réalisée. Elle remonte en tête
de la fiche du salarié, en lecture seule. La visite reste le seul endroit de
saisie.

## #11 — Élus CSE *(outil en ligne, attend tes dates)*

Tes 8 titulaires retrouvés, y compris celle qui figure sous son nom d'usage.

L'outil relit ton fichier, refuse d'écrire si une ligne est douteuse, ne crée
jamais deux fois le même mandat, et refuse un mandat pour quelqu'un qui a quitté
l'entreprise. Testé : les 8 mandats se créent, relancer n'en crée aucun de plus.

## #12 — Exports CSE et BDES

Trois défauts corrigés :

- **L'export des élus affichait « Actif » pour tout le monde**, mandats terminés
  compris. Un mandat clos en 2023 sort maintenant « Expiré » avec ses jours de
  dépassement, et un mandat proche du terme est signalé 3 mois avant.
- Les dates s'affichaient en écriture machine.
- **L'export des heures de délégation ne marchait pas du tout**, depuis toujours.
  Personne ne l'avait signalé : il n'avait sans doute jamais servi.

> **Plus grave :** une société dont tous les mandats sont expirés serait apparue
> « CSE en place, conforme ». Un faux feu vert sur une obligation légale. Corrigé.

## #14 — Médailles du travail

Barème éditable dans **Entreprise > Paie** (paliers 20/30/35/40 ans), ajustable
aussi au moment de valider. Ajout d'une **base d'ancienneté par société**, pour
les reprises d'ancienneté.

**La détection ne tournait qu'à l'ouverture d'une fiche.** Elle passe en scan
quotidien.

## #15 — Prime de transport

Réglable sur la fiche du salarié avec une date d'effet. Génère chaque mois une
ligne d'indemnité trajet, modifiable mois par mois — **une correction manuelle
n'est jamais écrasée**. Proratisée à l'entrée et à la sortie, retirée si absence
tout le mois, avec alerte au dépassement du plafond exonéré.

## #16 — Virement des acomptes

Export séparé de celui des salaires, avec sa propre date et son propre
historique. Deux usages : l'ordre de virement pour la banque, ou la liste des
acomptes déjà versés sur une période.

## #17 — Environnement de test

Un second EYWAI complet, qui reçoit une copie des données réelles sur demande.
**Jamais dans l'autre sens :** ce que tu y fais disparaît à la copie suivante.

Trois sorties verrouillées, puisque les données sont réelles : les e-mails
partent tous vers une seule boîte, la signature électronique et le dépôt de DSN
sont refusés.

## #19 — Fractionnement des congés

**7 défauts** faussaient le calcul, dont un qui rendait 0 jour pour les 221
salariés de MBC. Tout est corrigé.

Paramétrable dans **Entreprise > Congés**. Calcul automatique, mais **rien n'est
crédité sans ta validation**. Aucune société n'était paramétrée : personne n'a été
touché par ces erreurs.

## #20 — NIR et sortie DSN

**Les NIR sont bons :** 240 actifs, aucun vide, clé de contrôle correcte partout.
274 des 275 personnes des DSN du cabinet correspondent au chiffre près.

Trois anomalies viennent du cabinet, qu'on avait recopiées : 8 salariés dont le
sexe déclaré contredit leur NIR, 2 dates de naissance divergentes, 1 salarié
déclaré chez Cartol qui n'existe pas chez nous.

**Notre sortie DSN** n'était pas déposable : 100 à 120 rubriques manquantes.
L'en-tête, l'identité et les contrats sont maintenant conformes, vérifiés sur
5 sociétés. En attendant la suite, l'export est marqué « non déposable ».

## #21 — Badgeuse Colorplast

Surprise : **Colorplast n'a pas de badgeuse du tout.** On recevait des feuilles
papier scannées, dont la qualité se dégradait.

Les salariés badgeront depuis leur téléphone. La pause déjeuner se déduit comme
ils le font vraiment : 30 minutes au-delà de 6 heures, aucune sur une
demi-journée. Vérifié sur leurs feuilles, les trois semaines tombent au centième.

**Rien ne part en paie tout de suite :** un mois de badgeuse et papier en
parallèle, le papier a le dernier mot.

## #22 — Arrondi des congés au 31 mai

Vérifié, rien à corriger. On arrondit **au supérieur** dès qu'il y a une
fraction — à l'avantage du salarié.

| Mois *(1er juin → 31 mai)* | Calcul | Résultat |
| --- | --: | --: |
| 1 | 2,5 | **3** |
| 7 | 17,5 | **18** |
| 8 | 20,0 | **20** |
| 12 | 30,0 | **30** |

Tout mois commencé compte pour 1 : une embauche le 15 juin fait compter juin en
entier.

## #23 — Provision congés payés

Ton fichier exemple : Cartol, 71 salariés, 394 121 €. On l'a décortiqué plutôt
que de te relancer — **la méthode du cabinet est retrouvée et tombe juste au
centime** sur les 71 lignes.

L'export est dans **Exports > Exports RH > « Provision congés payés »**. On a
ajouté 3 colonnes que le cabinet n'a pas — date d'entrée, mois de paie utilisés,
et « anomalie » — pour voir d'où sort chaque chiffre.

**Le premier essai sortait 31 % trop bas.** Le solde de l'année précédente
n'avait jamais été repris : chez nous 25 jours pour tout le monde, alors qu'en
vrai il va de 3 à 88 jours. Ces soldes étaient **dans ton fichier**. On les a
remis : **l'écart est passé de 6,2 jours à un centième, et de 31 % à 12 %**.

- **Les 12 % restants ne peuvent pas être réglés :** le salaire de référence se
  calcule sur 12 mois de paie et on n'en a que 6. Ça se règlera seul en juin
  2027. L'export affiche un avertissement permanent.
- Zone 404 et MAJI n'ont aucun bulletin : leur provision sortait à zéro sans rien
  annoncer. On retombe maintenant sur le salaire du contrat.

## #24 — Format du bulletin de paie

Le bulletin sort au format du cabinet : une page, compteurs de congés en haut à
gauche, adresse à droite, cumuls sur le côté, net à payer en bas. Les rubriques
portent les codes Cegid (Q100 Santé, Q300 Retraite…).

Primes, notes de frais, cumuls annuels et soldes RTT se fondent dans le gabarit.
L'aperçu montre exactement le document qui sortira.

**Aucun montant ne change**, et les bulletins déjà émis restent tels quels. Ajout
d'une mention obligatoire qui manquait : l'évolution de la rémunération liée à la
suppression des cotisations chômage et maladie.

## #25 — Entretiens annuels

Ton fichier du 27 juillet donnait la règle de chaque société :

| Société | Règle |
| --- | --- |
| Cartol | Novembre |
| Comitech, Colorplast, LEWIS | Octobre |
| MAJI | Décembre |
| Zone 404 | À la date d'ancienneté |
| Mont Blanc Composite | Octobre, tous les deux ans |

La page existait depuis longtemps — convocation PDF, signature, types légaux —
**mais elle n'a jamais servi** : aucun entretien enregistré, aucun compteur légal
en cours.

- Chaque société a sa campagne réglable dans **Entreprise > Paie**.
- **L'an prochain, EYWAI proposera seul la campagne suivante, et tu pourras
  changer le mois sans nous.**
- La liste ne regardait que les cadres et forfaits jour. Campagne réglée, elle
  couvre tout l'effectif, retards en tête.
- **Reprise vérifiée à blanc :** 211 entretiens à planifier, 43 passés. On
  recalcule chaque échéance puis on compare à ton fichier — **aucun écart sur les
  211 lignes.**
- Les 32 lignes de gens déjà sortis sont ignorées. Les entretiens passés n'ont
  qu'une année : on l'enregistre sans inventer un jour.

*Rien n'est encore écrit : la reprise attend tes trois réponses.*

## #26 — Interfaçage comptable

L'écriture de paie est juste et équilibrée. Elle sort aux comptes du cabinet,
**ventilée par organisme** (URSSAF, retraite, mutuelle, prévoyance) et agrégée
par compte : une vingtaine de lignes au lieu de 137.

Colorplast, Comitech et Cartol tombent au centime. **Avant, aucune société ne
tombait juste** — il manquait jusqu'à 114 000 € d'un côté de la balance.

Un fichier qui ne s'équilibre pas n'est plus produit : l'écran dit quel compte
manque.

## #27 — Post-traitement des pointages

Tout se règle dans **Entreprise > Paie > « Pointages & imports »** : pause repas,
seuil de déduction, tolérances, grilles par équipe, validation des heures
supplémentaires.

**Mais ce réglage n'était lu que pour les journées badgées.** Les feuilles papier
se voyaient appliquer une heure de pause en dur. Chez Colorplast (30 min au-delà
de 6 h), la même journée valait 8 h par le papier et 8 h 30 par le badgeage —
**une demi-heure d'écart par jour et par personne**, en plein mois de comparaison.

Les deux chemins suivent maintenant le même réglage.

## #28 — Périodes d'essai

**Pourquoi tu ne le trouvais pas :** aucun des 241 salariés n'avait de période
renseignée, et la carte était masquée passé 90 jours d'ancienneté — invisible
pour 239 salariés sur 241.

- Carte visible sur **tout salarié actif**.
- Page **« Périodes d'essai »** dans Effectifs : à confirmer, en cours, à
  qualifier.
- Barème éditable par société. Renouvellement enregistrable.

> **Découverte :** la date de fin était fausse d'un jour. Deux mois ouverts le
> 1er mars finissaient le 1er mai au lieu du 30 avril. Sans données, aucun effet
> — mais une rupture notifiée le dernier jour affiché aurait été requalifiée.
> Corrigé.

Pas de reprise automatique : les 33 embauches LEWIS du même mois sont une reprise
de données, pas 33 recrutements. Le rattrapage passe par « à qualifier ».

*Aucune période saisie : on doit te montrer la page.*

## #29 — Alertes de paie

Il restait du bruit, corrigé sur trois sources : « 100 % de bulletins non
validés » chez les sociétés qui n'utilisent pas la validation, « taux de
versement mobilité introuvable » (vrai bug de calcul), et les alertes de
convention collective sur lesquelles on ne peut rien faire.

**Les vraies anomalies sont toujours signalées.**

## #30 — Assistant RH

**Le modèle d'IA n'était pas la cause.** La convention collective enregistrée ne
contenait ni la période d'essai ni le préavis : il ne pouvait pas répondre. Les
avenants de catégorie ont été ajoutés.

Les questions nominatives sont limitées au périmètre RH de celui qui pose la
question.

## #31 — Prélèvement à la source

C'est bien l'interfaçage net-entreprises : la DGFiP renvoie le taux après chaque
dépôt de DSN. **EYWAI n'en récupérait aucun** — le taux venait des DSN Cegid,
sans date, et 6 étaient faux dont le tien, figé depuis janvier.

Écran RH livré (liste, fraîcheur, origine, dépôt de fichier, export). **182
salariés ont leur taux.** Un salarié sans taux connu passe à la grille par défaut
au lieu de 0 %.

DSN de juin appliquées : 12 taux mis à jour, sans échec. Cinq personnes déclarées
n'existent pas chez nous : signalées et ignorées, jamais créées.

> **Erreur trouvée en chemin :** le « type de taux 13 » est le barème par défaut,
> pas un taux personnel — il se déduit de la paie du mois. Le moteur le figeait
> d'un mois sur l'autre : un salarié à 0 % en juin restait à 0 % en juillet même
> si sa paie remontait. Il recalcule maintenant à chaque bulletin.

## #32 — Indemnité d'activité partielle

Chez LEWIS, 33 salariés en activité partielle en juin, 17 510 € d'indemnité. Le
calcul était bon, mais **le bulletin ne l'affichait nulle part** : le salarié
voyait ses heures chômées retirées sans voir la compensation.

La ligne apparaît maintenant à côté des paniers. 35 bulletins LEWIS concernés,
aucune autre société.

---

## Note de suivi

- Le **#13** était vide (« idem ») et le **#27** figurait deux fois. Nettoyés.
- Statuts vérifiés le 7 août dans la base de production et le code déployé, pas
  déduits du texte précédent.
- **#28** était donné comme non déployé alors qu'il l'est. **#4** n'avait aucun
  chiffre, alors que 148 adresses sont inventées.
- **#11, #12 et #24** ont été confirmés en production : d'anciennes branches de
  travail restées ouvertes les avaient fait croire en attente.
