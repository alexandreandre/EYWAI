PRIORITE  : 
#17. Créer un environnement de test avec les données réelles (il suit l'environnement de prod, avec les memes données, mais on peut faire des tests de demissions des gens etc... donc test suit prod mais prod suit pas test) MOI

On a mis en place un second EYWAI complet (sirh-frontend-test…, base Supabase dédiée), qui reçoit une copie des données réelles de la production via une resynchro déclenchée à la main depuis le bandeau orange — jamais l'inverse : tout ce qu'on fait dans le test (démission, suppression, bulletin) reste dans le test et disparaît à la prochaine resynchro. Comme les données sont réelles, trois sorties sont verrouillées techniquement : les e-mails sont tous redirigés vers une boîte unique (le service refuse même de démarrer sans cette redirection), la signature électronique et le dépôt de DSN sont refusés

#1. Accès Vanessa MOI
Vanessa voit bien ses 7 sociétés, elle n'a qu'à se reconnecter. Le jour de la réunion, elle s'était connectée pile entre deux mises à jour des droits, du coup elle n'en voyait que 2 sur 7 — ses accès étaient déjà corrects un quart d'heure plus tard. En vérifiant, on a trouvé un problème plus sérieux : quand on retirait un accès à quelqu'un, ça ne marchait pas vraiment — la personne continuait à voir les sociétés qu'on lui avait enlevées. On l'a corrigé et nettoyé en production.

#2. Envoyer identifiants de connexion à Gaëlle et Vanessa via Whatsapp MOI
#3. Fichier BIC attendre fichier ELSA
#4. Adresses e-mail tous employés attendre fichier ELSA


#5. Robin Collaborateur/RH - Directeur MOI

On a levé l'ambiguïté du compte rendu : Robin doit être collaborateur RH sur Zone 404, avec les droits d'un directeur. Chez nous, « directeur » n'est pas un rôle mais un paquet de droits — celui d'Eric Noble, Damien Faucher et Lucas Chambert. Concrètement Robin garde son espace salarié tout en ayant en plus la vue RH, et il obtient les validations (valider un bulletin, approuver une note de frais ou une avance). C'est écrit dans le fichier qui pilote les accès, la simulation est propre (2 changements, aucun conflit).

#6. Dates titres de séjour (Elsa m'a envoyé whatsapp) MOI

Les dates d'expiration des titres de séjour ont été saisies. Sur les 43 salariés en poste concernés, 41 ont maintenant leur date (33 chez Mont Blanc Composite, 3 chez Cartol, 2 chez LEWIS, 2 chez Zone 404, 1 chez Comitech). Avant, il en manquait 34. Les alertes du système fonctionnent donc enfin pour de vrai.

#7. Bouton d'export Excel titres de séjour MOI

Il y a maintenant un bouton « Exporter en Excel » sur la page RH des titres de séjour. Il génère un fichier avec, pour chaque salarié concerné : nom, prénom, matricule, société, poste, date d'entrée, nationalité, type et numéro de titre, date d'expiration, et surtout le statut du titre avec le nombre de jours restants — donc on voit tout de suite qui est expiré ou sur le point de l'être. L'export reprend exactement ce qui est affiché à l'écran et reste limité à la société sur laquelle on travaille.

#8. Compteur JTC attendre récap ELSA 
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

#20. Numéro NIR bons ELSA. Sortie DSN de chez nous à checker MOI

Les NIR sont bons : 240 actifs, aucun vide, clé de contrôle correcte partout, et 274 des 275 individus des DSN du cabinet correspondent au chiffre près. Trois choses viennent du cabinet et qu'on a recopiées : 8 salariés déclarés avec un sexe que leur propre NIR contredit, 2 dates de naissance divergentes, et un salarié déclaré chez Cartol depuis janvier qui n'existe pas dans EYWAI.

Notre sortie DSN, elle, n'était pas déposable : 100 à 120 rubriques manquantes selon la société, dont le bloc total sans lequel net-entreprises rejette le fichier. L'en-tête, l'identité et les contrats sont maintenant conformes au fichier du cabinet, vérifié automatiquement sur cinq sociétés. Restent les cotisations, les agrégés URSSAF et la prévoyance : ça demande la nomenclature officielle des codes de cotisation, sans quoi on déclarerait des montants faux. En attendant, l'export est marqué non déposable et le dit à l'écran.

#21. Badgeuse chez Colorplast. Stratégie d'intégration intelligente à gamberge MOI
#22. Arrondi des congés au 31 mai. Vérifier l'arrondi au supérieur comment c'est fait (mathématiquement)Normalement bon. Attendre compte rendu ELSA

BONUS:
#23. Pouvoir faire un export de calcul de provision des congés payés. (En gros, c'est un fichier où on calcule ce qu'on devrait aux salariés de l'entreprise s'ils partaient tous en congés payés, et c'est converti en euros.) demander fichier exemple à ELSA 
#24. Format bulletin de paie MOI
#25. Pouvoir importer dates des entretiens annuels attendre récap et fichier ELSA
#26. Interfaçage compta MOI
#27. Vérifier si retraitemment pointages paramétrables (exemple, heures de pauses etc...) MOI
#28. Suivi des périodes d'essais, pouvoir le cocher, quelque part, meme après la création. Bien paramétrable Pour l'instant, elsa ne l'a pas trouvé. MOI
#29. Alertes sur la paye moins énervé (normalement déjà fait mais à vérifier) MOI
#30. Changer le modèle d'assistant RH Car nul pour l'instant
#31. Taux PAS. Pouvoir voir facilement son taux. Est ce que il est bien récupéré ? Si on recrute un employé, comment récupérer son taux ? C'est pas l'interfaçage net-entreprise justement ???