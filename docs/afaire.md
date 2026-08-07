PRIORITE  : 
#17. Créer un environnement de test avec les données réelles (il suit l'environnement de prod, avec les memes données, mais on peut faire des tests de demissions des gens etc... donc test suit prod mais prod suit pas test) MOI

On a mis en place un second EYWAI complet (sirh-frontend-test…, base Supabase dédiée), qui reçoit une copie des données réelles de la production via une resynchro déclenchée à la main depuis le bandeau orange — jamais l'inverse : tout ce qu'on fait dans le test (démission, suppression, bulletin) reste dans le test et disparaît à la prochaine resynchro. Comme les données sont réelles, trois sorties sont verrouillées techniquement : les e-mails sont tous redirigés vers une boîte unique (le service refuse même de démarrer sans cette redirection), la signature électronique et le dépôt de DSN sont refusés

#1. Accès Vanessa MOI
Vanessa voit bien ses 7 sociétés, elle n'a qu'à se reconnecter. Le jour de la réunion, elle s'était connectée pile entre deux mises à jour des droits, du coup elle n'en voyait que 2 sur 7 — ses accès étaient déjà corrects un quart d'heure plus tard. En vérifiant, on a trouvé un problème plus sérieux : quand on retirait un accès à quelqu'un, ça ne marchait pas vraiment — la personne continuait à voir les sociétés qu'on lui avait enlevées. On l'a corrigé et nettoyé en production.

#2. Envoyer identifiants de connexion à Gaëlle et Vanessa via Whatsapp MOI
#3. Fichier BIC attendre fichier ELSA
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
#12. Exports CSE et BDES attendre récap ELSA 
#13. idem
#14. Vérifier si on peut bien paramétrer montant des primes médaille du travail depuis l'interface MOI

Le barème (paliers 20/30/35/40 ans et leurs montants) s'édite bien depuis Entreprise > Paie, et le montant peut aussi être ajusté au moment de valider une médaille. On a ajouté un réglage base d'ancienneté par société, pour les cas de reprise d'ancienneté où la date d'entrée ne reflète pas les droits réels. Et surtout, la détection ne tournait qu'à l'ouverture d'une fiche salarié : elle passe maintenant en scan automatique quotidien.

#15. Prime transport réglable dans les primes via l'interface (pas forcément tous les mois donc pouvoir paramétrer manuellement) MOI

Le montant se règle sur la fiche du salarié, avec une date d'effet, et génère chaque mois une ligne d'indemnité trajet dans les saisies mensuelles — modifiable ou supprimable mois par mois, la correction manuelle n'est jamais réécrasée. Proratisée à l'entrée/sortie, retirée si absence tout le mois, avec alerte au dépassement du plafond exonéré.


#16. Fichier de virement pour les acomptes aussi (idem pour salaire mais pas la meme campagne de paiement) MOI

Il y a maintenant un export « Virement acomptes », séparé de celui des salaires : sa propre date d'exécution, ses propres références bancaires, son propre historique. On peut soit sortir l'ordre de virement à envoyer à la banque (les acomptes approuvés pas encore payés), soit la liste des acomptes déjà versés sur une période.  Il ne sera pas utilisable tant que les BIC manquent : 238 salariés sur 240 n'en ont pas (c'est le point #3, en attente du fichier d'Elsa).

#18. Point paye avec Gaëlle ELSA
#19. Vérifier que fractionnement des congés c'est bien propre. Comment c'est activable ? paramétrable ? C'est automatiquement fait ? MOI

Ce n'était pas propre : sept défauts faussaient le calcul, dont un qui rendait 0 jour pour les 221 salariés de MBC. Tout est corrigé. C'est maintenant paramétrable par société dans Entreprise > Congés (méthode de calcul, barème, exclusion des cadres au forfait-jours), calculé automatiquement mais jamais crédité sans validation RH. Aucune société n'était paramétrée, donc aucun salarié n'a été touché par ces erreurs.

#20. Numéro NIR bons. Sortie DSN de chez nous à checker MOI

Les NIR sont bons : 240 actifs, aucun vide, clé de contrôle correcte partout, et 274 des 275 individus des DSN du cabinet correspondent au chiffre près. Trois choses viennent du cabinet et qu'on a recopiées : 8 salariés déclarés avec un sexe que leur propre NIR contredit, 2 dates de naissance divergentes, et un salarié déclaré chez Cartol depuis janvier qui n'existe pas dans EYWAI.

Notre sortie DSN, elle, n'était pas déposable : 100 à 120 rubriques manquantes selon la société, dont le bloc total sans lequel net-entreprises rejette le fichier. L'en-tête, l'identité et les contrats sont maintenant conformes au fichier du cabinet, vérifié automatiquement sur cinq sociétés. Restent les cotisations, les agrégés URSSAF et la prévoyance : ça demande la nomenclature officielle des codes de cotisation, sans quoi on déclarerait des montants faux. En attendant, l'export est marqué non déposable et le dit à l'écran.

#21. Badgeuse chez Colorplast. Stratégie d'intégration intelligente à gamberge MOI

D'abord une surprise : Colorplast n'a pas de badgeuse du tout. Ce qu'on recevait, ce sont des feuilles papier remplies au stylo, puis scannées ou photographiées — et la qualité se dégradait, les totaux ayant disparu depuis le printemps. Les salariés vont donc badger depuis leur téléphone : le bouton n'existait pas, il est maintenant en ligne. Le système sait aussi déduire la pause déjeuner comme eux le font vraiment, 30 minutes seulement quand la journée dépasse 6 heures — une demi-journée n'en subit aucune. Vérifié sur leurs propres feuilles : les trois semaines complètes retombent au centième. Rien ne part en paie tout de suite : pendant un mois, la badgeuse et le papier tournent en parallèle et on compare chaque semaine, le papier ayant le dernier mot. Le vrai point d'attention n'est pas technique : aucun des 9 salariés ne s'est jamais connecté à EYWAI.
#22. Arrondi des congés au 31 mai. Vérifier l'arrondi au supérieur comment c'est fait (mathématiquement)Normalement bon. Attendre compte rendu ELSA

BONUS:
#23. Pouvoir faire un export de calcul de provision des congés payés. (En gros, c'est un fichier où on calcule ce qu'on devrait aux salariés de l'entreprise s'ils partaient tous en congés payés, et c'est converti en euros.) demander fichier exemple à ELSA 
#24. Format bulletin de paie MOI

Le bulletin sort maintenant au format du cabinet : une page, sobre, avec le bloc des compteurs de congés en haut à gauche, l'adresse du salarié à droite, la colonne des cumuls sur le côté et le net à payer en bas. Les rubriques portent les mêmes codes que chez Cegid (Q100 Santé, Q300 Retraite…). Ce qu'on affichait en plus (primes, notes de frais, cumuls annuels, soldes RTT) se fond dans le gabarit au lieu d'occuper ses propres sections. À l'écran, l'aperçu d'un bulletin en cours de modification montre désormais exactement le document qui sortira. Aucun montant ne change, et les bulletins déjà émis restent tels quels. Au passage, on a ajouté une mention obligatoire qui manquait depuis le début : l'évolution de la rémunération liée à la suppression des cotisations chômage et maladie.

#25. Pouvoir importer dates des entretiens annuels attendre récap et fichier ELSA
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