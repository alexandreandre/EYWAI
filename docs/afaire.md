PRIORITE  : 
#17. Créer un environnement de test avec les données réelles (il suit l'environnement de prod, avec les memes données, mais on peut faire des tests de demissions des gens etc... donc test suit prod mais prod suit pas test) MOI

On a mis en place un second EYWAI complet (sirh-frontend-test…, base Supabase dédiée), qui reçoit une copie des données réelles de la production via une resynchro déclenchée à la main depuis le bandeau orange — jamais l'inverse : tout ce qu'on fait dans le test (démission, suppression, bulletin) reste dans le test et disparaît à la prochaine resynchro. Comme les données sont réelles, trois sorties sont verrouillées techniquement : les e-mails sont tous redirigés vers une boîte unique (le service refuse même de démarrer sans cette redirection), la signature électronique et le dépôt de DSN sont refusés

#1. Accès Vanessa MOI
Vanessa voit bien ses 7 sociétés, elle n'a qu'à se reconnecter. Le jour de la réunion, elle s'était connectée pile entre deux mises à jour des droits, du coup elle n'en voyait que 2 sur 7 — ses accès étaient déjà corrects un quart d'heure plus tard. En vérifiant, on a trouvé un problème plus sérieux : quand on retirait un accès à quelqu'un, ça ne marchait pas vraiment — la personne continuait à voir les sociétés qu'on lui avait enlevées. On l'a corrigé et nettoyé en production.

#2. Envoyer identifiants de connexion à Gaëlle et Vanessa via Whatsapp MOI
#3. Fichier BIC — plus d'attente Elsa MOI

Le fichier n'était pas à attendre : Elsa l'a déjà envoyé le 27 juillet, sept
Excel Quadratus (une société chacun), toujours dans le fil WhatsApp et sous
`data/_inbox/whatsapp-elsa/` :

| Fichier | Lignes | BIC présents |
| --- | --- | --- |
| Zone 404 | 5 | 5 |
| Cartol | 91 | 91 |
| Colorplast | 7 | 7 |
| Comitech | 17 | 17 |
| MBC | 76 | 76 |
| MAJI | 10 | 10 |
| LEWIS | 39 | 0 (RIB français seul, 39/39 convertibles en IBAN) |

Total : **206 BIC explicites** sur six sociétés, plus 39 RIB LEWIS sans
colonne BIC. Rien de cassé dans les données source : en concaténant
`Bq iban` + `Bq rib` (ou le RIB seul), 100 % des IBAN passent la validation.

Ce qui bloquait côté nous, c'est le mapping d'import qui lit seulement
`Bq iban` (= le tronçon `FR76` / `FR88`) et ignore `Bq rib` : l'aperçu d'import
tombe en erreur alors que le BIC est bien dans la colonne à côté. À corriger
au moment de charger (joindre les deux colonnes, ou mapper le RIB sur
`Bq rib` + BIC sur `Bq bic`). LEWIS s'importe déjà tel quel pour l'IBAN ; le
BIC manquera tant qu'on ne le déduit pas (code banque) ou qu'Elsa ne renvoie
pas le format court des six autres.

Côté virement, le BIC n'est plus un bloqueur SEPA : depuis le règlement UE
2016 il est facultatif, l'export écrit sans BIC si besoin et affiche un simple
avertissement — l'IBAN suffit. Donc le point #3 « récupérer le fichier »
est clos : on l'a, il est complet pour six sociétés, importable après le
petit rattrapage de colonnes, et les virements ne sont plus pendants à ça.

#4. Adresses e-mail tous les employés attendre fichier ELSA


#5. Robin Collaborateur/RH - Directeur MOI

On a levé l'ambiguïté du compte rendu : Robin doit être collaborateur RH sur Zone 404, avec les droits d'un directeur. Chez nous, « directeur » n'est pas un rôle mais un paquet de droits — celui d'Eric Noble, Damien Faucher et Lucas Chambert. Concrètement Robin garde son espace salarié tout en ayant en plus la vue RH, et il obtient les validations (valider un bulletin, approuver une note de frais ou une avance). C'est écrit dans le fichier qui pilote les accès, la simulation est propre (2 changements, aucun conflit).

#6. Dates titres de séjour (Elsa m'a envoyé whatsapp) MOI

Les dates d'expiration des titres de séjour ont été saisies. Sur les 43 salariés en poste concernés, 41 ont maintenant leur date (33 chez Mont Blanc Composite, 3 chez Cartol, 2 chez LEWIS, 2 chez Zone 404, 1 chez Comitech). Avant, il en manquait 34. Les alertes du système fonctionnent donc enfin pour de vrai.

#7. Bouton d'export Excel titres de séjour MOI

Il y a maintenant un bouton « Exporter en Excel » sur la page RH des titres de séjour. Il génère un fichier avec, pour chaque salarié concerné : nom, prénom, matricule, société, poste, date d'entrée, nationalité, type et numéro de titre, date d'expiration, et surtout le statut du titre avec le nombre de jours restants — donc on voit tout de suite qui est expiré ou sur le point de l'être. L'export reprend exactement ce qui est affiché à l'écran et reste limité à la société sur laquelle on travaille.

#8. Compteur JTC attendre récap ELSA 

Le récap n'était pas à attendre : Elsa l'a envoyé le 28 juillet sur WhatsApp, une
note de deux pages qu'on n'avait pas ouverte. Elle fixe tout : le JTC est un accord
propre à Mont Blanc Composite, personne d'autre n'y a droit ; trois jours par an
au maximum, gagnés sur l'année précédente et à poser sur l'année en cours ; réduits
si le salarié est entré en cours d'année ou s'il a été absent plus de trente jours ;
toujours arrondis vers le bas, donc le solde est forcément 0, 1, 2 ou 3. Un nouvel
embauché n'a rien sa première année. La journée de solidarité se prend sur un JTC,
et sur un congé payé s'il n'en reste plus. Ce qui n'a pas été posé est payé au départ.
Et surtout, elle insiste : le JTC s'affiche à côté des congés payés, jamais dedans.

Le compteur est en ligne depuis aujourd'hui, en production comme sur le test. Il est
éteint partout : tant qu'on ne l'allume pas sur Mont Blanc Composite, aucune des sept
sociétés ne voit quoi que ce soit changer — ni sur les écrans, ni sur les bulletins.
Une fois allumé, le JTC devient un motif d'absence comme les congés payés, avec son
solde propre à l'écran et sa colonne à part sur le bulletin. Le barème (trois jours,
seuil de trente jours d'absence) se règle depuis Entreprise > Congés, sans passer par
nous.

Il manque encore trois choses avant de le montrer à Elsa. D'abord les soldes de
départ : le JTC de 2026 se gagne sur l'activité de 2025, or EYWAI ne contient rien
d'avant janvier 2026 — aucun pointage, aucun bulletin, quasiment aucune absence. On ne
peut donc pas recalculer ce que les 75 salariés de Mont Blanc Composite ont acquis :
il faut qu'elle nous donne leurs soldes une fois. À partir de janvier 2027, EYWAI
calculera seul, et un écran montrera le détail salarié par salarié avant que la RH ne
valide. Ensuite, un point de la note reste ambigu : quelqu'un absent trente et un jours
perd-il un JTC ou pas ? On a retenu la lecture stricte — il tombe à 2 — mais ça mérite
sa confirmation, car ça change le compte de tous ceux qui ont eu un arrêt d'un mois.
Enfin, la note renvoie à un onglet « détail absences » d'un fichier Excel qu'on n'a
jamais reçu : c'est lui qui dit exactement quelles absences comptent.

Deux morceaux ne sont pas encore faits, volontairement, parce qu'ils touchent au calcul
de la paie : l'imputation automatique de la journée de solidarité, et le paiement du
solde restant quand un salarié s'en va.

#9. Salarié colorplast en RTT (ou on des jours au compteur, je ne sais pas) alors que non. A checker MOI

Ce n'étaient pas des RTT posés mais un solde affiché à tort : sans paramétrage de congés, le système donnait 10 RTT/an à tout le monde — ça touchait 4 sociétés sur 7. Maintenant, sans paramétrage c'est 0, et les RTT sont calculés depuis le forfait annuel de chaque société (Cartol 214 j, les autres 216 j), réservés aux 19 cadres au forfait-jours. Vérifié : Colorplast est bien à 0.

#10. Case aménagement sur suivi médical MOI

Quand on enregistre une visite médicale comme réalisée, on peut cocher « aménagement de poste ». La case remonte ensuite en tête de la fiche du salarié, en lecture seule — la visite reste le seul endroit de saisie, et une correction de visite écrase bien l'ancienne valeur. C'est volontairement une simple case, sans motif ni date de fin.

#11. Elus CSE attendre fichier ELSA

Elsa avait bien envoyé sa liste par WhatsApp le 2 août : 8 élus titulaires, 2 chez
Cartol, 2 chez LEWIS, 4 chez Mont Blanc Composite. Les 8 ont été retrouvés parmi nos
salariés, y compris celle qui figure sur la liste sous son nom d'usage alors que nous
la connaissons sous son nom de naissance.

Ce qui manque, c'est le mandat lui-même. La colonne « date d'entrée » de son fichier
est la date d'embauche du salarié, pas la date d'élection — les huit dates
correspondent au jour près à ce que nous avons déjà en base. Or sans date de début et
de fin de mandat, on ne peut rien enregistrer : c'est ce qui déclenche les alertes de
fin de mandat et le calcul des heures de délégation.

L'outil de reprise est prêt et testé : il relit son fichier, retrouve les salariés,
refuse d'écrire tant qu'une seule ligne est douteuse, et ne crée jamais deux fois le
même mandat si on le relance. Il refuse aussi de créer un mandat pour quelqu'un qui a
quitté l'entreprise. Répétition faite sur l'environnement de test avec des dates
provisoires : les 8 mandats se créent, la relance n'en crée aucun.

Reste à obtenir d'Elsa : les dates d'élection et de fin de mandat par société, les
suppléants (elle n'a listé que des titulaires), le collège pour Cartol et LEWIS, le nom
du secrétaire de chaque CSE, et le cas de Colorplast, MAJI et Zone 404 qui n'ont ni élu
ni procès-verbal de carence — celui de Comitech est périmé depuis septembre 2023.

#12. Exports CSE et BDES attendre récap ELSA 

Les erreurs qu'Elsa constatait sur les exports CSE sont trouvées et corrigées, sans
avoir eu besoin de son fichier : le défaut se reproduisait sans aucune donnée.

L'export de la base des élus affichait « Actif » pour tout le monde, y compris les
mandats terminés depuis des années, avec la colonne « jours restants » vide. Le
programme n'arrivait pas à lire les dates qu'il recevait lui-même, l'erreur était
étouffée en silence, et il retombait sur la valeur par défaut — « Actif ». Vérifié sur
l'environnement de test avec de vrais mandats : des mandats clos en janvier 2023
sortaient « Actif » avant, ils sortent maintenant « Expiré » avec le nombre de jours de
dépassement. Un mandat qui approche de son terme est signalé trois mois à l'avance.

Deux autres choses corrigées au passage. Les dates s'affichaient en écriture machine
au lieu du format habituel dans les trois exports. Surtout, l'export des heures de
délégation ne fonctionnait pas du tout : il s'interrompait sur une erreur à chaque
tentative, depuis toujours. Personne ne l'avait signalé, ce qui laisse penser qu'il
n'avait jamais servi.

Un dernier point, plus sérieux, découvert en relisant l'ensemble : si on avait chargé
les élus tels quels, une société dont tous les mandats sont expirés serait apparue
« CSE en place, conforme » sur son tableau de bord. Un faux feu vert sur une obligation
légale. Corrigé des deux côtés — à l'enregistrement et au calcul de conformité.

Rien n'est encore en production : le travail attend d'être intégré, et les élus
attendent les dates d'Elsa.

#13. idem
#14. Vérifier si on peut bien paramétrer montant des primes médaille du travail depuis l'interface MOI

Le barème (paliers 20/30/35/40 ans et leurs montants) s'édite bien depuis Entreprise > Paie, et le montant peut aussi être ajusté au moment de valider une médaille. On a ajouté un réglage base d'ancienneté par société, pour les cas de reprise d'ancienneté où la date d'entrée ne reflète pas les droits réels. Et surtout, la détection ne tournait qu'à l'ouverture d'une fiche salarié : elle passe maintenant en scan automatique quotidien.

#15. Prime transport réglable dans les primes via l'interface (pas forcément tous les mois donc pouvoir paramétrer manuellement) MOI

Le montant se règle sur la fiche du salarié, avec une date d'effet, et génère chaque mois une ligne d'indemnité trajet dans les saisies mensuelles — modifiable ou supprimable mois par mois, la correction manuelle n'est jamais réécrasée. Proratisée à l'entrée/sortie, retirée si absence tout le mois, avec alerte au dépassement du plafond exonéré.


#16. Fichier de virement pour les acomptes aussi (idem pour salaire mais pas la meme campagne de paiement) MOI

Il y a maintenant un export « Virement acomptes », séparé de celui des salaires : sa propre date d'exécution, ses propres références bancaires, son propre historique. On peut soit sortir l'ordre de virement à envoyer à la banque (les acomptes approuvés pas encore payés), soit la liste des acomptes déjà versés sur une période. Les BIC manquants ne bloquent plus la remise SEPA (IBAN suffisant, avertissement non bloquant) ; les 7 fichiers d'Elsa du 27/07 sont disponibles pour compléter la base (point #3).

#18. Point paye avec Gaëlle ELSA
#19. Vérifier que fractionnement des congés c'est bien propre. Comment c'est activable ? paramétrable ? C'est automatiquement fait ? MOI

Ce n'était pas propre : sept défauts faussaient le calcul, dont un qui rendait 0 jour pour les 221 salariés de MBC. Tout est corrigé. C'est maintenant paramétrable par société dans Entreprise > Congés (méthode de calcul, barème, exclusion des cadres au forfait-jours), calculé automatiquement mais jamais crédité sans validation RH. Aucune société n'était paramétrée, donc aucun salarié n'a été touché par ces erreurs.

#20. Numéro NIR bons. Sortie DSN de chez nous à checker MOI

Les NIR sont bons : 240 actifs, aucun vide, clé de contrôle correcte partout, et 274 des 275 individus des DSN du cabinet correspondent au chiffre près. Trois choses viennent du cabinet et qu'on a recopiées : 8 salariés déclarés avec un sexe que leur propre NIR contredit, 2 dates de naissance divergentes, et un salarié déclaré chez Cartol depuis janvier qui n'existe pas dans EYWAI.

Notre sortie DSN, elle, n'était pas déposable : 100 à 120 rubriques manquantes selon la société, dont le bloc total sans lequel net-entreprises rejette le fichier. L'en-tête, l'identité et les contrats sont maintenant conformes au fichier du cabinet, vérifié automatiquement sur cinq sociétés. Restent les cotisations, les agrégés URSSAF et la prévoyance : ça demande la nomenclature officielle des codes de cotisation, sans quoi on déclarerait des montants faux. En attendant, l'export est marqué non déposable et le dit à l'écran.

#21. Badgeuse chez Colorplast. Stratégie d'intégration intelligente à gamberge MOI

D'abord une surprise : Colorplast n'a pas de badgeuse du tout. Ce qu'on recevait, ce sont des feuilles papier remplies au stylo, puis scannées ou photographiées — et la qualité se dégradait, les totaux ayant disparu depuis le printemps. Les salariés vont donc badger depuis leur téléphone : le bouton n'existait pas, il est maintenant en ligne. Le système sait aussi déduire la pause déjeuner comme eux le font vraiment, 30 minutes seulement quand la journée dépasse 6 heures — une demi-journée n'en subit aucune. Vérifié sur leurs propres feuilles : les trois semaines complètes retombent au centième. Rien ne part en paie tout de suite : pendant un mois, la badgeuse et le papier tournent en parallèle et on compare chaque semaine, le papier ayant le dernier mot. Le vrai point d'attention n'est pas technique : aucun des 9 salariés ne s'est jamais connecté à EYWAI.
#22. Arrondi des congés au 31 mai. Vérifier l'arrondi au supérieur comment c'est fait (mathématiquement) MOI

C'est bon, pas besoin d'attendre Elsa. Le calcul est dans
`_acquired_cp_from_months` (`absences/domain/rules.py`) :

```
acquis = ceil(nombre_de_mois × 2,5)
```

Donc `math.ceil` Python : on monte toujours à l'entier supérieur dès qu'il y a
une fraction (avantage salarié, conforme à l'usage paie L3141). Exemples couverts
par les tests unitaires :

| Mois sur la période (1er juin → 31 mai) | Produit | Après arrondi |
| --- | --- | --- |
| 1 (ex. bulletin de juin) | 2,5 | **3** |
| 7 (ex. au 31/12) | 17,5 | **18** |
| 8 (ex. au 31/01) | 20,0 | **20** (déjà entier) |
| 12 (période clôturée au 31 mai) | 30,0 | **30** |

Le « mois » n'est pas fractionné en jours : tout mois civil touché dans la
période de référence compte pour 1 (embauche le 15 juin → le mois de juin
entre déjà). Taux paramétrable par société (`cp_acquisition_days_per_month`, défaut
2,5 ouvrables) ; en affichage « ouvrés » le moteur garde 2,5 en interne et
affiche 25 j/an. Même `ceil` sur le prorata d'un crédit d'ancienneté CP. Rien à
corriger.

BONUS:
#23. Pouvoir faire un export de calcul de provision des congés payés. (En gros, c'est un fichier où on calcule ce qu'on devrait aux salariés de l'entreprise s'ils partaient tous en congés payés, et c'est converti en euros.) demander fichier exemple à ELSA 

Il n'y avait rien à demander : Elsa avait envoyé le fichier exemple le 21 juillet,
puis une deuxième fois le 27 avec la phrase « doc provision CP à mettre en export ».
C'est un état du cabinet pour Cartol, 71 salariés, 394 121 € au total. On l'a décortiqué
plutôt que de la relancer : la façon dont le cabinet calcule est entièrement retrouvée,
et elle tombe juste au centime sur les 71 lignes. Pour chaque salarié, on prend son
solde de congés, on le multiplie par sa journée de salaire, on ajoute ses charges
patronales.

L'export existe maintenant dans Exports > Exports RH, sous « Provision congés payés ».
On choisit un mois, on obtient un fichier Excel avec une ligne par salarié et un total
en bas : solde de l'année précédente, solde en cours, salaire de référence, taux de
charges, provision, total. On a ajouté trois colonnes que le cabinet n'a pas — la date
d'entrée, le nombre de mois de paie qui ont servi au calcul, et une colonne « anomalie »
— pour qu'on voie tout de suite d'où sort chaque chiffre au lieu de devoir croire le
fichier sur parole.

Au premier essai, nos chiffres sortaient 31 % en dessous de ceux du cabinet, et ce
n'était pas le calcul : le solde de l'année précédente n'avait jamais été repris. Chez
nous il valait 25 jours pour tout le monde — un droit théorique recalculé — alors que
dans la réalité il va de 3 à 88 jours selon les personnes. Même trou que pour le JTC :
EYWAI ne contient rien avant janvier 2026.

Sauf qu'on n'a pas eu à redemander ces soldes : ils sont **dans le fichier d'Elsa**, une
colonne du même document. On a donc écrit un outil qui les relit et les remet dans
EYWAI, et c'est fait : les 71 salariés de Cartol ont maintenant leur vrai report. On
vérifie nom par nom — BOISSINOT 88 jours, QUERAT 81, BERTAUD 28 — c'est exactement ce
qu'affiche le cabinet. L'écart sur les soldes est passé de 6,2 jours à un centième de
jour, et l'écart en euros de 31 % à 12 %.

Un piège au passage, qui aurait pu passer inaperçu : la première écriture n'a servi à
rien. Les valeurs étaient bien en base mais le calcul les ignorait, parce qu'une reprise
plus ancienne, faite à partir des bulletins de mai, prenait le dessus sans rien
signaler. On ne l'a vu qu'en remesurant l'écart au cabinet après coup. C'est corrigé, et
un test bloque le retour du problème.

Les 12 % restants viennent de la deuxième cause, qu'on ne peut pas régler : le salaire
de référence se calcule sur douze mois de paie et on n'en a que six. Ça se réglera tout
seul en juin 2027. En attendant, l'export affiche en permanence un avertissement qui dit
que le chiffre est indicatif — on préfère ça à un montant faux présenté comme sûr.

Ce qui est juste, en revanche : le solde de l'année en cours (4,17 jours contre 4,16
chez le cabinet, un simple arrondi) et le taux de charges de chaque salarié, à un
dixième de point près.

Deux choses trouvées en testant sur les vraies données. Zone 404 et MAJI n'ont aucun
bulletin dans EYWAI ; leur provision sortait à zéro euro sans que rien ne l'annonce.
C'est corrigé : on retombe sur le salaire du contrat (9 860 € et 22 602 €), et un
fichier entièrement à zéro n'est plus produit du tout — l'écran dit ce qui manque.

C'est en production depuis le 7 août : l'export répond bien sur le serveur de prod,
vérifié après le déploiement et pas seulement sur la foi d'un voyant vert.

Reste deux questions à Elsa : le même état de provision pour les six
autres sociétés (c'est ce qui corrigera leurs compteurs de congés, pas seulement la
provision), et pourquoi son fichier ne contient que 71 salariés alors que 86 ont été
payés en juin. Les absents sont tous des embauches récentes ; nous on les garde,
puisqu'ils ont des congés acquis donc une dette.

#24. Format bulletin de paie MOI

Le bulletin sort maintenant au format du cabinet : une page, sobre, avec le bloc des compteurs de congés en haut à gauche, l'adresse du salarié à droite, la colonne des cumuls sur le côté et le net à payer en bas. Les rubriques portent les mêmes codes que chez Cegid (Q100 Santé, Q300 Retraite…). Ce qu'on affichait en plus (primes, notes de frais, cumuls annuels, soldes RTT) se fond dans le gabarit au lieu d'occuper ses propres sections. À l'écran, l'aperçu d'un bulletin en cours de modification montre désormais exactement le document qui sortira. Aucun montant ne change, et les bulletins déjà émis restent tels quels. Au passage, on a ajouté une mention obligatoire qui manquait depuis le début : l'évolution de la rémunération liée à la suppression des cotisations chômage et maladie.

#25. Pouvoir importer dates des entretiens annuels attendre récap et fichier ELSA

Le fichier n'était pas à attendre : Elsa l'a envoyé le 27 juillet à 18 h 05 sur WhatsApp,
« Planif_entretiens.xlsx », qu'on n'avait jamais ouvert. 256 lignes, les sept sociétés, et
surtout la règle d'entretien de chacune : Cartol refait tout en novembre, Comitech,
Colorplast et LEWIS en octobre, MAJI en décembre, Zone 404 à la date d'ancienneté de
chaque salarié, et Mont Blanc Composite tous les deux ans en octobre.

Il fallait bien commencer par là, parce que la page des entretiens existait depuis
longtemps — avec la convocation en PDF, la signature électronique, les types
d'entretien légaux — mais qu'elle n'a jamais servi : il n'y avait pas un seul entretien
enregistré en production. Aucun compteur légal ne courait.

Ce qui a été fait. Chaque société a maintenant sa campagne d'entretiens réglable dans
Entreprise > Paie : le mois où l'on convoque tout le monde (ou bien « à la date
d'ancienneté »), et tous les combien. C'est le point important pour la suite : l'an
prochain, EYWAI proposera seul la campagne suivante, et Elsa pourra changer le mois
sans nous. Tant qu'une société n'est pas réglée, rien ne bouge chez elle — comme pour
le JTC.

Jusqu'ici, la liste des entretiens à planifier ne regardait que les cadres et les
salariés au forfait jour, soit une poignée de personnes. Une fois la campagne réglée,
elle couvre tout l'effectif de la société, avec la date attendue pour chacun et les
retards en tête de liste.

La reprise elle-même est prête et vérifiée à blanc sur les vraies données : 211
entretiens à planifier et 43 entretiens passés à reprendre. Le programme ne recopie pas
la colonne « à planifier » du fichier d'Elsa : il recalcule chaque échéance avec la
règle de la société, puis compare. Sur les 211 lignes, **aucun écart** — notre calcul
et son fichier tombent exactement pareil. Il refuse d'écrire au moindre désaccord, ne
crée jamais deux fois le même entretien si on le relance, et ignore les salariés partis.

Deux choses volontairement laissées de côté. Les 32 lignes du fichier qui correspondent
à des gens déjà sortis (21 chez Cartol, 5 Comitech, 4 LEWIS, 2 Colorplast) sont
ignorées. Et pour les entretiens passés, le fichier ne donne qu'une **année**, jamais
une date : on enregistre l'année, sans inventer un jour. C'est suffisant pour faire
courir le délai de deux ans.

Rien n'est encore écrit en base, et trois questions restent pour Elsa :

1. Mont Blanc Composite ne colle pas : son onglet compte 58 personnes alors qu'on en a
   75 en poste. 13 noms de sa liste nous sont inconnus, et 30 des nôtres n'y figurent
   pas. Il faut savoir lesquels sont concernés avant de charger cette société.
2. Le fichier ne porte aucune date d'entretien professionnel ni de bilan à six ans —
   ce sont pourtant les deux seuls entretiens obligatoires. Si ces dates existent
   quelque part, il les faut ; sinon, tout le monde repart de zéro.
3. Confirmer que Mont Blanc Composite est bien sur un cycle de deux ans alors que les
   six autres sociétés sont annuelles.

#26. Interfaçage compta MOI

L'écriture comptable de paie est maintenant juste et équilibrée : elle sort aux comptes du cabinet, ventilée par organisme (URSSAF, retraite, mutuelle, prévoyance) au lieu d'un compte fourre-tout, et agrégée par compte comme le fait le cabinet — une vingtaine de lignes au lieu de 137. Colorplast, Comitech et Cartol tombent au centime. Avant, aucune société ne tombait juste : il manquait jusqu'à 114 000 € d'un côté de la balance. Un fichier qui ne s'équilibre pas n'est plus produit du tout : l'écran dit quel compte manque. Il reste trois comptes à récupérer chez le cabinet — paniers, cantine, IJSS — et les identifiants Cegid pour envoyer les écritures automatiquement au lieu de déposer un fichier.

#27. Vérifier si le post traitemment automatique des pointages est paramétrable facilement (exemple, heures de pauses etc...)

Tout se règle par société dans Entreprise > Paie > « Pointages & imports » : pause repas déduite, durée de présence en dessous de laquelle on ne déduit rien, tolérance d'entrée et de sortie, grilles horaires par équipe, validation des heures supplémentaires détectées. Mais ce réglage n'était lu que pour les journées badgées : les heures venant d'une feuille papier importée se voyaient appliquer une heure de pause écrite en dur dans le programme. Chez Colorplast, dont la règle est de 30 minutes au-delà de 6 heures, la même journée valait 8 h par le papier et 8 h 30 par le badgeage — une demi-heure d'écart par jour et par personne, en plein mois de comparaison entre les deux. Les deux chemins suivent maintenant le même réglage, et changer un paramètre recalcule aussitôt les imports au lieu d'attendre le lendemain. Reste à savoir que seules Colorplast et Mont Blanc Composite sont paramétrées : ailleurs, une journée badgée serait comptée sans aucune pause.

#32. Indemnité d'activité partielle absente du bulletin MOI

Chez LEWIS, 33 salariés étaient en activité partielle en juin — 17 510 € d'indemnité. Le calcul était bon et le montant bien enregistré, mais le bulletin ne l'affichait nulle part : le salarié voyait ses heures chômées retirées de son salaire, sans voir ce qu'il touchait en compensation. C'est corrigé : la ligne « Indemnité activité partielle » apparaît maintenant avec son montant, à côté des paniers. Seuls les bulletins de LEWIS sont concernés, 35 sur les deux derniers mois ; aucune autre société n'avait ce cas.
#27. Vérifier si le post traitemment automatique des pointages est paramétrable facilement (exemple, heures de pauses etc...) MOI

Tout se règle par société dans Entreprise > Paie > « Pointages & imports » : pause repas déduite, durée de présence en dessous de laquelle on ne déduit rien, tolérance d'entrée et de sortie, grilles horaires par équipe, validation des heures supplémentaires détectées. Mais ce réglage n'était lu que pour les journées badgées : les heures venant d'une feuille papier importée se voyaient appliquer une heure de pause écrite en dur dans le programme. Chez Colorplast, dont la règle est de 30 minutes au-delà de 6 heures, la même journée valait 8 h par le papier et 8 h 30 par le badgeage — une demi-heure d'écart par jour et par personne, en plein mois de comparaison entre les deux. Les deux chemins suivent maintenant le même réglage, et changer un paramètre recalcule aussitôt les imports au lieu d'attendre le lendemain. Reste à savoir que seules Colorplast et Mont Blanc Composite sont paramétrées : ailleurs, une journée badgée serait comptée sans aucune pause.

#28. Suivi des périodes d'essais, pouvoir le cocher, quelque part, meme après la création. Bien paramétrable Pour l'instant, elsa ne l'a pas trouvé. MOI

Développé le 5 août 2026, pas encore déployé. Pourquoi Elsa ne trouvait pas :
aucun des 241 salariés actifs n'avait de période d'essai renseignée, et la carte
de la fiche était masquée passé 90 jours d'ancienneté — soit invisible pour 239
salariés sur 241, sans aucun moyen d'activer le suivi après la création.

Ce qui a été fait : une table `trial_periods` remplace le champ jsonb (vide) ; la
carte de la fiche est visible sur tout salarié actif ; une page « Périodes
d'essai » apparaît dans le menu Effectifs, en trois sections — à confirmer, en
cours, à qualifier avec application du barème en un clic ; le barème (durées par
type de contrat et statut, délai d'alerte, règle CDD) devient éditable dans les
réglages société ; le renouvellement effectif est enregistrable et repousse
l'alerte.

Découverte au passage : le calcul de la date de fin était faux d'un jour, back et
front. Une période de deux mois ouverte le 1er mars finissait le 1er mai au lieu
du 30 avril. Sans données en base le bug n'a jamais produit d'effet, mais une
rupture notifiée le dernier jour affiché aurait été prononcée hors période
d'essai, donc requalifiée. Corrigé et couvert par des tests, y compris les
embauches de fin de mois (31 janvier + 1 mois = 28 février, pas le 27).

Aucun backfill : les 33 embauches LEWIS du même mois sont une reprise de données,
pas 33 recrutements. Le rattrapage passe par la section « à qualifier », bornée
aux embauches de moins de huit mois — la durée maximale légale.

Recette passée sur l'environnement de test : barème cadre 4 mois / non-cadre
2 mois, activation sur un salarié ancien, renouvellement avant terme accepté et
après terme refusé, confirmation, réembauche possible une fois la période close,
apprenti sans période. Les quatre contraintes de la table mordent, RLS active,
aucune alerte de l'advisor de sécurité.

Reste à faire : déploiement en production (les deux migrations `20260806090000`
et `20260806100000` s'appliquent automatiquement au déploiement), puis montrer la
page à Elsa.

À noter : la carte étant désormais visible partout, activer le suivi sur un
salarié entré il y a des années crée une période déjà terminée à sa date d'entrée.
C'est juste en droit mais peu utile ; la date de début reste modifiable sur la
fiche.
#29. Alertes sur la paye moins énervé (normalement déjà fait mais à vérifier) MOI

Vérifié : il restait du bruit, c'est corrigé. Trois sources traitées : « 100 % de bulletins non validés » s'affichait chez les sociétés qui n'utilisent tout simplement pas le circuit de validation ; l'alerte « taux de versement mobilité introuvable » venait d'un vrai bug de calcul du taux, maintenant réglé ; et les alertes de convention collective non actionnables (règles absentes, prime d'ancienneté non éligible) ne remontent plus en critique. Les vraies anomalies, elles, sont toujours signalées.
#30. Changer le modèle d' IA d'assistant RH Car nul pour l'instant
#31. Taux PAS. Pouvoir voir facilement son taux. Est ce que il est bien récupéré ? Si on recrute un employé, comment récupérer son taux ? C'est pas l'interfaçage net-entreprise justement ???

Oui, c'est bien l'interfaçage : la DGFiP renvoie le taux dans le compte rendu métier qui suit chaque dépôt de DSN. EYWAI n'en récupérait aucun — le taux ne venait que de l'import des DSN Cegid, sans date, et 6 taux étaient faux, dont celui d'Elsa figé depuis janvier. Écran RH « Prélèvement à la source » livré (liste, fraîcheur, origine, dépôt de fichier avec aperçu, export), 238 taux repris sur la DSN de mai, et l'import DSN rafraîchit désormais le taux même quand il ignore la fiche. Un salarié sans taux connu se voit appliquer la grille par défaut au lieu de 0 % — ça ne concerne aucun actif aujourd'hui, ça protège les futurs embauchés. Reste à obtenir l'accès net-entreprises : sans lui les taux dépendent encore de fichiers réclamés à Elsa, et un embauché reste au taux par défaut au lieu de basculer sur le sien.

Le type de taux 13 est élucidé, et il cachait une erreur de calcul. C'est le barème mensuel métropole — la grille par défaut (23 et 33 outre-mer, 17/27/37 pour les variantes proratisées), d'après la note DGFiP publiée par net-entreprises et vérifié sur nos données : 233 des 236 lignes de type 13 des cinquante DSN tombent au centième sur la grille appliquée à l'assiette du versement. Un taux de barème n'appartient donc pas au salarié : il se déduit de sa paie du mois. Le moteur le figeait d'un mois sur l'autre — un salarié à 0 % en juin parce qu'il était sous le seuil restait à 0 % en juillet même si sa paie remontait. Il recalcule désormais la grille à chaque bulletin, et le bulletin affiche le taux réellement appliqué au lieu de celui de la fiche (il montrait 0 % quand la grille avait servi).

Les DSN de juin des sept sociétés ont été récupérées et appliquées : 12 taux mis à jour, dont DEPONGE Jordan 5,3 → 7,8 % et AGOUMBI Tristan 0 → 6,1 %, sans aucun échec. Cinq personnes déclarées dans ces DSN n'existent pas dans EYWAI (FROUIN Noa, LELIEVRE Cameron et SANTOS FERNANDES Paulo José chez Cartol, AMARKHILL Rafiullah chez MBC, VUILLERMET Sébastien chez Comitech) : elles sont signalées et ignorées, jamais créées. Les DSN de juillet n'ont pas encore été déposées sur le Drive. Le rafraîchissement d'un mois complet se rejoue avec `python scripts/pas_import_dsn.py --periode AAAA-MM --apply`.
