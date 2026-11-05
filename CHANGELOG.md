# Journal des versions de Martine

Chaque déploiement du site de paie porte une étiquette `paie-AAAA-MM-JJ.N`, affichée en bas du menu.
Pour chaque changement : trois lignes, en mots d'utilisatrice.

## Pas encore déployé

### Le dossier de départ d'un CDD estime la prime et les congés selon la loi
- La prime de fin de contrat se calcule sur les salaires de ce contrat seulement, le dernier mois estimé au salaire ; plus aucun mois inventé après le départ.
- Les congés d'un départ déjà payé par l'ancien logiciel se recomptent depuis l'entrée, et le dossier le dit ; un départ en juin ne mélange plus deux périodes de congés sur le bulletin.
- Au choix d'un salarié en CDD, le formulaire de départ propose « Fin de CDD » et la date de fin du contrat ; tout reste modifiable.

### Une attestation pour un salarié, en PDF prêt à signer
- Fiche du salarié > Documents > « Générer une attestation » (aussi en mode paie), ou Exports > Déclarations > « Attestation pour un salarié ».
- Deux lettres : l'attestation de travail (poste, contrat, date d'entrée, ancienneté du bulletin, temps de travail, rémunération, période d'essai en cours) et l'attestation de salaire (brut et net avant impôt des derniers bulletins remis, 3 mois par défaut, jusqu'à 12).
- Une information absente de la fiche laisse des pointillés à remplir à la main. Martine refuse ce qu'elle ne peut pas attester, et le dit : un contrat fini (c'est le certificat de travail), un salaire sans bulletin validé et remis.

### « Attestations & annexes » devient « Récapitulatif des salaires du mois »
- Ce tableau n'a jamais été une attestation : il porte maintenant son vrai nom.
- La colonne « Matricule » donne le vrai matricule du salarié ; les colonnes « Type attestation » et « Statut » disparaissent.
- Les attestations de salaire pour la CPAM et France Travail partent toujours dans la DSN.

## paie-2026-11-05.9 — 5 novembre 2026

### Un arrêt maladie ordinaire acquiert 2 jours de congés par mois
- Depuis la loi du 22 avril 2024, un mois d'arrêt maladie ordinaire donne 2 jours ouvrables de congés, contre 2,5 pour un mois travaillé ; Martine comptait 2,5.
- Un accident du travail, une maladie professionnelle, une maternité ou une paternité gardent 2,5 jours ; les arrêts d'avant la reprise des soldes ne changent rien.
- En métallurgie, la convention (article 84) compte l'arrêt comme du travail, de 2 à 8 mois selon l'ancienneté : les compteurs de LEWIS et de Cartol ne bougent pas.

## paie-2026-11-05.8 — 5 novembre 2026

### Martine trouve le code PCS-ESE
- Sur la fiche et à la création, le code se choisit dans la liste officielle des 430 codes, en cherchant un code, un intitulé ou un métier (« soudeur »).
- Quand des collègues au même poste ont tous le même code, Martine le remplit et dit pourquoi ; sinon elle propose trois codes. Vous pouvez toujours le changer.
- Quand un code change, la DSN suivante déclare l'ancien code, comme le demande l'Urssaf ; un nouvel import de DSN ne remet plus « 9999 » sur un code trouvé.

## paie-2026-11-05.6 — 5 novembre 2026

### La provision des congés suit la règle légale
- Chaque période de congés vaut le plus élevé du maintien de salaire et du dixième, comme au départ d'un salarié : un mois d'absence ne fait plus baisser la valeur des jours.
- Dans le dixième, le salaire des absences est reconstitué : en entier pour un accident du travail, une maternité ou une paternité, à 80 % pour un arrêt maladie.
- Le maintien compte le salaire du contrat et les primes versées chaque mois ; de nouvelles colonnes montrent la valeur du jour, les bases du dixième et la méthode retenue.

## paie-2026-11-05.4 — 5 novembre 2026 (et .3)

### Un salarié peut être dispensé de mutuelle
- Modifier la fiche > Paie sociale, sans formule choisie : « Le salarié ne veut pas adhérer (dispense) », un motif parmi les cas de la loi, et la date de sa demande signée.
- Avec une dispense valable, l'aperçu de la DSN ne dit plus « mutuelle absente » ; sans formule ni dispense, il dit où aller et quoi faire.
- Pour un salarié couvert par la mutuelle de son conjoint ou d'un autre employeur, le justificatif se redemande chaque année : la DSN le rappelle au bout d'un an.

## paie-2026-11-05.2 — 5 novembre 2026

### Le repos compensateur entre dans la provision des congés
- L'état de provision a une colonne « Solde jrs repos compensateur », comptée dans le total des jours.
- Les heures de repos acquises et pas encore prises sont converties en jours (7 h par jour, ou le réglage de la société) et valorisées au même prix que les congés.
- Un repos pris sans crédit ne diminue pas la provision : la colonne « Anomalie » le signale.

## paie-2026-11-05.1 — 5 novembre 2026

### Le code PCS-ESE « 9999 » est accepté
- « 9999 » veut dire « profession inconnue » : c'est un code officiel de la DSN.
- La fiche d'un salarié qui a ce code peut de nouveau être enregistrée, et l'aperçu DSN ne le dit plus faux.
- Les salariés repris de Quadra avec ce code gardent un vrai code à trouver.

## paie-2026-11-04.7 — 4 novembre 2026

### Les prêts et les avances ne se perdent plus en silence
- Si une retenue de prêt ou d'avance ne s'enregistre pas, le bulletin le dit par une alerte.
- Une avance ne peut plus être retenue deux fois au recalcul.
- Un taux ou un barème illisible arrête le calcul au lieu de prendre une valeur par défaut.

### Plus rapide, sans rien changer aux montants
- Les barèmes ne sont plus relus en entier à chaque bulletin : seulement quand l'un d'eux a changé.
- Trois index accélèrent l'import DSN, les absences et l'import des pointages.
- Des appels à des tables qui n'existent pas sont retirés.

### La connexion dit pourquoi elle échoue
- Compte sans accès actif, trop de tentatives, service indisponible : chaque cas a son message.
- Un mot de passe faux et un compte inconnu gardent le même message, pour ne pas dire qu'un compte existe.
- Rien ne change pour une connexion qui réussit.

## paie-2026-11-04.6 — 4 novembre 2026

### L'aperçu d'un signalement DSN avant envoi
- Chaque signalement d'arrêt, de reprise ou de fin de contrat a un bouton « Aperçu ».
- La fenêtre montre le fichier en clair, rubrique par rubrique, avec ce que veut dire chaque code (« 01 = maladie »), et le fichier brut.
- L'aperçu n'envoie et n'enregistre rien ; le numéro de sécurité sociale y est masqué.

## paie-2026-11-04.5 — 4 novembre 2026

### Un cadre a toujours sa prévoyance
- Un cadre sans prévoyance n'a plus de bulletin : le message dit de cocher « Adhésion prévoyance » sur sa fiche et de choisir le contrat.
- Un bandeau le signale aussi sur la fiche.
- En plasturgie, même règle pour un non-cadre qui a atteint 3 mois d'ancienneté.

### Des calculs repris de l'audit de paie
- Un net imposable négatif ne donne plus d'impôt prélevé ; en DSN, l'assiette et le prélèvement ne sont plus jamais négatifs.
- La participation et l'intéressement sortent de la part saisissable du salaire.
- L'indemnité de fin de CDD se calcule sur toute la rémunération du contrat, renouvellements compris.

### Métallurgie
- La prime d'ancienneté suit la valeur du point 2026 de chaque territoire, à sa date.
- L'indemnité de licenciement ou de rupture conventionnelle ne descend plus sous le plancher de la convention.
- Rien ne change pour les autres conventions.

### Une erreur ne passe plus en silence
- Une action qui échoue le dit toujours ; trois messages peuvent s'afficher à la fois.
- Les boutons inactifs disent pourquoi, et la connexion dit pourquoi elle échoue.
- Le suivi IJSS, la badgeuse et l'import des taux d'impôt disent leurs erreurs.

### La paie du mois d'abord
- La page Paie s'ouvre sur la vue « Par mois ».
- Le mode groupé ne demande qu'une confirmation, qui nomme les calendriers incomplets.
- La DSN n'est cochée « faite » qu'une fois marquée déposée.

### Plus rapide au démarrage
- Le premier chargement du site passe d'environ 2,3 Mo à 0,9 Mo.
- La barre latérale ne relit plus tous ses compteurs à chaque écran.
- Sans logo de société, c'est le « M » de Martine qui s'affiche.

## paie-2026-11-04.4 — 4 novembre 2026

### Moins de code inutile
- Rien ne change à l'écran ni dans les bulletins.
- 36 fichiers et 101 fonctions qui ne servaient plus sont retirés, avec 19 bibliothèques.
- Moins de code à vérifier, et trois failles connues de bibliothèques disparaissent avec elles.

### La base de paie fermée aux accès directs
- Rien ne change à l'écran ni dans les bulletins.
- Les tables de la paie ne s'ouvrent plus qu'au serveur de Martine, plus à un accès public.
- Une fonction qui permettait d'exécuter n'importe quelle requête est supprimée.

## paie-2026-11-04.3 — 4 novembre 2026

### « Groupe C » ne s'invente plus
- La classification d'un salarié n'est plus remplie d'office, ni à la création ni à la modification de la fiche.
- Sous une convention à coefficient seul (plasturgie), la fiche affiche « Coeff. 700 », sans groupe ni classe.
- Sous une convention, la création demande de choisir la classification.

### Le même mois sur tous les écrans
- Calendrier, Primes, Paie et export s'ouvrent sur le même mois de paie, écrit dans l'adresse.
- Du 1er au 15 du mois, c'est le mois précédent : celui qu'on paie.
- Le mois choisi suit d'un écran à l'autre.

### Le forfait jours réduit
- La fiche d'un salarié au forfait jours accepte son propre nombre de jours (par exemple 43 pour un jour par semaine).
- La réduction générale se calcule sur ce forfait, et non plus sur celui de la société.
- Sans valeur sur la fiche, rien ne change.

### Un compte par prêt
- Un prêt peut porter son propre compte comptable, saisi à sa création.
- L'écriture de paie crédite ce compte de chaque remboursement.
- Sans compte, le prêt suit le compte « prêt » de la société, comme avant.

## paie-2026-11-04.2 — 4 novembre 2026

### Le montant net social de 2026
- Le « Montant net social » des bulletins ne compte plus les parts de l'employeur pour la mutuelle et la prévoyance.
- En 2026, la règle les exclut ; elles n'entreront que pour les salaires de 2027, si le décret paraît.
- Le brut, les cotisations, le net imposable et le net à payer ne changent pas.

### Le jour où le salarié voit son bulletin
- La fenêtre « Valider les bulletins prêts » dit le vrai jour où les salariés verront leurs bulletins.
- Une paie validée après ce jour (octobre validé en novembre, par exemple) est visible et figée dès la validation : la fenêtre le dit.
- Un bulletin de sortie est visible dès sa validation : la fenêtre le nomme.

### Pas de certificat pour la DSN
- La carte Net-entreprises ne propose plus « API — certificat » : il n'y a pas de certificat à demander.
- Elle ne demande plus de mot de passe et ne propose plus de « tester la connexion » : l'envoi direct n'est pas encore branché.
- La DSN se dépose à la main sur net-entreprises.fr, comme avant.

### Les chargements disent ce qui se passe
- Le requin disparaît : chaque chargement montre une barre fine et ce qui charge, en mots.
- La génération de la paie et l'écran de démarrage gardent leur compteur et leurs textes, sans requin.
- L'onglet du navigateur et l'aperçu des liens montrent le « M » de Martine.

## paie-2026-11-04.1 — 4 novembre 2026

Déployée depuis la branche `deploy/c1-2026-11-04` (import des pointages : case « absent », tableur de LEWIS, badges dans la revue). Entrée non rédigée au moment du déploiement.

## paie-2026-11-03.1 — 3 novembre 2026

### Des textes qui disent vrai
- La pastille orange en haut à droite dit « Données réelles · envois limités » au lieu de « Environnement de test ».
- En la survolant : vos données sont réelles et conservées, et ce qui ne part pas encore (e-mails des salariés, DSN, signature, comptable).
- Les e-mails automatiques arrivent de la part de « Martine ».

### Version visible
- La version du site s'affiche en bas du menu, par exemple « Version paie-2026-11-03.1 ».
- En signalant un écart, la donner au support : on saura quel code a calculé le bulletin.
- Le site ne peut plus être mis à jour si les vérifications automatiques ne sont pas vertes.

### Documents internes à l'abri
- Rien ne change à l'écran ni dans les bulletins.
- Les fichiers de travail tirés des bulletins et les documents commerciaux ne peuvent plus partir sur le dépôt public.
- Une protection supplémentaire de la base de paie est prête ; elle ne s'appliquera qu'après accord.

### Vérifications automatiques étanches
- Rien ne change à l'écran ni dans les bulletins.
- Les vérifications automatiques du code ne peuvent plus écrire dans la base où se fait la paie.
- Elles reprennent quelques minutes au lieu de vingt, donc les corrections arrivent plus vite.
