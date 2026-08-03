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



#10. Case aménagement sur suivi médical MOI
#11. Elus CSE attendre fichier ELSA
#12. Exports CSE et BDES attendre récap ELSA 
#13. idem
#14. Vérifier si on peut bien paramétrer montant des primes médaille du travail depuis l'interface MOI
#15. Prime transport réglable dans les primes via l'interface (pas forcément tous les mois donc pouvoir paramétrer manuellement) MOI
#16. Fichier de virement pour les acomptes aussi (idem pour salaire mais pas la meme campagne de paiement) MOI

Il y a maintenant une carte « Virement acomptes » à côté de « Virement salaires », qui sort les deux mêmes fichiers : un récapitulatif lisible et la remise bancaire SEPA (ou un CSV bancaire). C'est bien une campagne séparée — historique, date d'exécution et libellé propres, et des identifiants bancaires distincts pour que la banque ne puisse pas confondre les deux remises d'un même mois. Deux modes : « à verser », les acomptes approuvés dont il reste quelque chose à payer, c'est l'ordre à donner à la banque ; et « déjà versés », un simple relevé, assorti d'un avertissement de ne pas le transmettre sous peine de payer une seconde fois. Le mode « à verser » ne filtre pas sur le mois par défaut : un acompte approuvé le 28 juin doit partir dans la remise de juillet. Le fichier ne change aucun statut — après passage de la banque, le versement reste à enregistrer sur la fiche de l'acompte.

Les contrôles reprennent ceux des salaires (IBAN manquant, montant nul, salarié sorti, règlement en chèque ou espèces écarté) et en ajoutent un propre aux acomptes : un acompte approuvé sans montant accordé est bloqué au lieu de partir à 0 €.

À signaler à Elsa : le seul acompte existant en base, chez LEWIS (90,90 €), est incohérent — marqué « versé » alors qu'aucun versement n'est enregistré, et sans montant accordé. C'est exactement le cas que le nouveau contrôle refuse.


#18. Point paye avec Gaëlle ELSA
#19. Vérifier que fractionnement des congés c'est bien propre. Comment c'est activable ? paramétrable ? C'est automatiquement fait ? MOI
#20. Numéro NIR bons ELSA. Sortie DSN de chez nous à checker MOI
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