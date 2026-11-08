# Journal des versions de Martine

Chaque déploiement du site de paie porte une étiquette `paie-AAAA-MM-JJ.N`, affichée en bas du menu.
Pour chaque changement : trois lignes, en mots d'utilisatrice.

## Pas encore déployé

### Sorties et verrou
- Une heure faite en plus une semaine de congés est majorée quand le congé a été posé à l'écran ; une semaine d'arrêt maladie ne la majore pas (sociétés sans compensation entre semaines).
- Rupture, licenciement et préavis comptent depuis la date d'ancienneté de la fiche quand elle précède l'embauche ; le dossier le dit.
- Un bulletin encore en brouillon reste corrigeable après la date du verrou ; seul un bulletin validé se fige.

### Corrections à la main plus sûres
- Correction à la main : le net suit un avantage en nature corrigé, et l'OD porte l'avantage (compte à renseigner par société).
- DSN : une assiette de CSG par nature, plus de base 04 doublée après une correction.
- Une réduction générale corrigée au-delà du cumul est refusée avant d'écrire ; une saisie refusée par le recalcul est listée et se retire.
- Après une correction, Martine dit le mois suivant à recalculer. La carte dit que la réduction générale est reprise le mois suivant.
- Revue : impôt et net relus à la génération ; un écart critique non acquitté bloque la validation.
### Corriger une ligne dit ce qui suit vraiment, et où corriger le reste
- La carte ne promet plus que la DSN et les exports suivent toujours : une DSN déjà déposée ou un export déjà sorti sont à refaire. Sur la réduction générale, elle prévient que l'écart revient le mois suivant.
- Si Martine calcule autre chose après une correction (planning changé, par exemple), la ligne corrigée le dit, et la revue du mois aussi. La correction reste appliquée.
- Les montants hors de la carte (prêts, avances, saisies, indemnités de rupture, indemnités journalières) sont listés avec l'écran où les corriger.

### La DSN refuse un mois repris et une cotisation sans code
- Un mois payé avec l'ancien logiciel ne se déclare plus depuis Martine : l'aperçu l'explique et indique le premier mois à déclarer.
- Une cotisation qui porte un montant sans avoir de code DSN arrête le fichier au lieu d'être oubliée : l'aperçu nomme le salarié et la cotisation, et dit quoi faire.
### La DSN déclare l'activité partielle et le temps partiel thérapeutique
- Les heures chômées et l'indemnité d'activité partielle partent en DSN (motif 602, type 019) et le bulletin imprime les heures et le taux.
- Le temps partiel thérapeutique a son motif (15 à 18 selon l'origine) et la reprise en temps partiel son code 02, au lieu de la maladie. Il se saisit aussi sous accident du travail et maladie professionnelle.
### Le motif de fin de contrat se choisit sur le dossier de sortie
- Le dossier de sortie affiche le motif déclaré en DSN, proposé selon le type de sortie et le contrat. Un motif qui ne va pas avec le contrat est refusé et Martine dit lequel prendre.
- Une fin de CDD avant son terme ne part plus en « fin de CDD » sans qu'on le sache : Martine demande de choisir le motif.

### La date de l'accident se saisit sur l'arrêt
- Les arrêts pour accident ou maladie professionnelle ont un champ « date de l'accident ou de la première constatation », repris par le signalement DSN. Sans date, le signalement le dit avant le dépôt.

### Le mois de sortie va jusqu'au dernier jour du contrat
- Quand un salarié part après l'arrêté des variables, ses heures sup, paniers, absences et congés posés jusqu'à son dernier jour passent sur le bulletin de sortie. Ces jours sont à saisir avant de générer le bulletin.
- Un repos compensateur obligatoire non pris au départ est signalé sur le bulletin, à ajouter à la page Primes, et le reçu pour solde de tout compte indique les heures dues au lieu de « Néant ».

### Un import sur plusieurs mois garde ce que vous corrigez à la relecture
- Quand un fichier couvre plusieurs mois, une case corrigée avant d'enregistrer était perdue : c'était le fichier d'origine qui s'enregistrait. Vos corrections vont maintenant dans le bon mois.

### L'import du calendrier dit quels codes il ne comprend pas
- Un code inconnu (« CHOMAGE PARTIEL », « CP SS », « MODUL »…) devenait un congé sans rien dire. Martine les liste maintenant au moment de l'import, avec le nombre de jours, pour que vous les corrigiez à la relecture.
### Licenciement pour inaptitude et congés de fin de CDD sans compteurs
- Une case « Licenciement pour inaptitude » dit son origine. Si elle est professionnelle, Martine double l'indemnité légale et ajoute une indemnité compensatrice égale au préavis ; la DSN porte le bon motif.
- Quand les compteurs de congés manquent à la fin d'un CDD, le bulletin dit que l'indemnité vient du dixième du contrat et que les congés déjà payés ne sont pas déduits. À vérifier avant de valider.

### Le maintien légal cumule les arrêts des douze derniers mois
- Quand un salarié a déjà été indemnisé sur un autre arrêt dans l'année écoulée, les jours déjà pris sont déduits de ses droits, comme le prévoit le Code du travail. Le maintien ne repart plus à zéro à chaque arrêt.
- Le bulletin dit combien de jours ont été déduits. Les maintiens prévus par la convention ne changent pas.

### La revue d'avant-paie vérifie le minimum annuel de la métallurgie
- À partir d'octobre, chez Cartol et LEWIS, un salarié dont la rémunération de l'année reste sous le minimum de sa classe est signalé, avec le montant qui manque.
- Le contrôle suit la convention : prime d'ancienneté et heures supplémentaires écartées, forfait jours majoré de 30 %. Il ne bloque rien : les primes de fin d'année comptent, à vérifier à la clôture de décembre.

### Une avance sur salaire se retient au dixième du net
- La retenue d'une avance en espèces ne dépasse plus le dixième du net du mois, comme le prévoit le Code du travail. Le reste se retient sur les bulletins suivants, et le bulletin le dit.
- Les acomptes sur un travail en cours ne changent pas : ils restent retenus en entier.

### Martine connaît la convention Syntec
- La grille des salaires minima Syntec est prête, pour les sociétés qui passent sous cette convention.
- Un salarié au forfait jours sous Syntec est signalé si sa position ne l'autorise pas ou si son salaire est sous le plancher de la convention (122 % ou 120 % du minimum). Le bulletin ne change pas : la correction se fait par avenant.

### Une coupure de base n'ouvre plus la garde de reprise
- Si la base ne répond pas au moment du calcul, Martine arrête le bulletin et demande de réessayer. Avant, le mois repris pouvait se recalculer, ou le bulletin partir de cumuls à zéro.
- Le contrôle du taux horaire lit le Smic du mois, et un salarié sans date d'ancienneté n'a plus 26 ans de droits inventés au maintien.

### La revue d'avant-paie rappelle les primes habituelles à saisir
- Une prime versée en août et en septembre par l'ancien logiciel (présence, assiduité, poste…) et que rien ne reporte ce mois-ci est signalée, salarié par salarié.
- Rappel pendant les trois mois qui suivent la reprise, avec un lien vers la saisie. Il ne bloque pas : Martine ne calcule pas ces primes.

### Le titre de séjour est visible sur la fiche en mode paie
- Le badge d'expiration du titre de séjour revient sur la fiche du salarié. L'accueil les comptait déjà dans « Échéances ».
- Rien ne change dans le calcul de la paie.

### Les pièces de la société se déposent sur la page Entreprise
- Nouvel encart « Pièces de la société » dans l'onglet Fiche : Kbis, contrats de mutuelle et de prévoyance, adhésion à la fédération, justificatif JEI, accord sur le temps de travail.
- Martine dit ce qui reste à déposer pour la société et pourquoi. Le dépôt accepte PDF, JPG et PNG, 15 Mo au plus. Rien ne bloque la paie.

### La revue d'avant-paie rappelle les prêts et les saisies à poser
- Si l'ancien logiciel retenait un prêt ou une saisie en septembre et que rien n'est ouvert dans Martine, la revue le dit, salarié par salarié, avec le montant et le lien.
- Rappel pendant les trois mois qui suivent la reprise. Il ne bloque pas : la retenue ne part que si le prêt ou la saisie est posé.

### La liste de contrôle du mois dit ce qui manque encore
- Deux nouvelles lignes sur la page Paie : les taux d'impôt manquants ou périmés, et le compte bancaire de la société.
- Chaque ligne dit quoi faire et où. Un taux absent passait à la grille par défaut sans prévenir sur cette page.

### « Prévu » s'affiche pour tous les salariés au forfait jours
- Le planning d'un forfait est enregistré en heures par jour : l'écran n'affichait « Prévu » que pour la valeur 1, donc jamais.
- Un jour planifié et pas encore confirmé dit maintenant « Prévu », un jour confirmé « Travaillé ». Rien ne change sur les bulletins.

### Le contrat signé se dépose depuis la fiche en mode paie
- Sur la fiche d'un salarié, l'onglet Documents montre maintenant le contrat de travail à côté des bulletins et des attestations.
- Déposez le PDF signé, ou remplacez celui qui est là. Vous n'avez plus besoin de nous l'envoyer.

### Prime d'ancienneté de la métallurgie au forfait jours
- Elle sortait à zéro pour les salariés au forfait jours non cadres : les jours du forfait n'étaient pas comptés.
- Elle suit maintenant la convention (article 142) : valeur du point × taux de la classe × années, majorée de 30 % au forfait jours.
- Là où Quadra applique encore le point de 2025 ou oublie la majoration, Martine suit le texte : l'écart se voit au premier bulletin.

### L'import des DSN ne prend plus la prévoyance pour une mutuelle
- Chaque cotisation est rattachée à son contrat par les liens de la DSN, plus par l'ordre des lignes.
- Contrôlé sur les bulletins de septembre de 5 sociétés : mutuelle présente ou absente à juste titre pour 229 salariés sur 229.

### La part de l'employeur à la mutuelle santé entre toujours dans le net imposable
- La loi la rend imposable (Code général des impôts, article 83). 68 fiches de Cartol, Mont Blanc et Zone 404 l'en sortaient, comme Quadra.
- Le net imposable de ces salariés monte du montant de la part employeur ; l'impôt prélevé suit.
- L'import des DSN lit aussi le forfait jours dans la DSN, et rattache chaque salarié à sa formule de mutuelle même quand les montants varient.

### L'attestation d'emploi suit votre modèle
- Elle reprend votre modèle ligne à ligne : nom et prénom, n° de sécurité sociale, adresse, emploi occupé, reprise d'ancienneté, puis « est employé(e) au sein de notre entreprise depuis le… ». Elle s'appelle désormais « Attestation d'emploi » partout.
- Elle ne parle plus de la naissance, du contrat, du temps de travail ni du salaire : pour le salaire, c'est l'attestation de salaire.
- Si la fiche n'a pas le n° de sécurité sociale ou la date de reprise d'ancienneté, la lettre écrit « Non renseigné sur la fiche salarié » : complétez la fiche, puis générez-la de nouveau.

### Les heures de récupération sont suivies
- Un seul réglage par société (Entreprise > Paie > Organisation du temps) : heures sup payées, ou mises au compteur. Une heure à 25 % donne 1 h 15 de repos, à 50 % 1 h 30.
- Sur le bulletin : heures acquises, heures prises avec leur date, solde. Et sur chaque bulletin, un bouton pour payer les heures du mois au lieu de les mettre au compteur (ou l'inverse), payer le solde, ou revenir en arrière. La conséquence est écrite à côté : une heure mise en repos puis payée perd l'exonération d'impôt et les réductions.
- La récupération se pose comme une absence, à la journée ou en heures. Le solde entre dans la provision des congés. Tant que les soldes de Quadra ne sont pas repris, rien ne change pour personne.

## paie-2026-11-06.1 — 6 novembre 2026

### Le bulletin ne porte plus que ce qu'il doit porter
- « Heures compensées entre semaines (option société) » et « … plus favorable que la règle du 1/10ème » ne s'impriment plus : ces deux phrases restent à l'écran, dans « D'où viennent ces lignes ».
- « Réduction HS structurelles (jours d'absence) » devient « Heures sup. du contrat non faites (absence) » sur les nouveaux bulletins. Le calcul ne change pas.

### L'attestation de salaire maison disparaît, l'arrêt montre son signalement DSN
- Plus de PDF d'attestation pour la CPAM : le signalement d'arrêt en DSN le remplace, et ce document inventait le salaire de la fiche pour les mois sans bulletin.
- À la place, chaque arrêt validé dit où en est son signalement : à déposer avant telle date, en retard, ou fichier généré tel jour. Le dépôt se fait hors de Martine : elle ne le voit pas et ne le prétend pas.

### Plus de montant inventé sans le dire quand un bulletin manque
- Le reçu pour solde de tout compte se refuse sans le bulletin du mois de sortie. L'attestation employeur garde 0 € pour un bulletin sans salaire.
- Des IJ estimées disent combien de mois de référence n'ont pas de bulletin. Une avance sans bulletin dit que sa référence est le brut de la fiche.

### Forfait jours : un jour resté « Prévu » n'est plus une absence
- Dans un mois confirmé en partie, un jour prévu sans réel restait retenu en absence injustifiée. Seul un 0 posé à l'écran dit « non travaillé ».

### Deux messages qui ne demandent rien se taisent
- « Plasturgie : un an d'ancienneté requis… » : le motif se lit sous la ligne d'absence, à l'aperçu et au détail du maintien.
- Le net ne se compare plus à un mois d'entrée incomplet (« +508 % ») : ni orange, ni écart à acquitter avant de valider.

### Provision des congés
- « Mois retenus » s'écrit « 9 mois sur 12 » : Excel n'en fait plus une date.
## paie-2026-11-05.14 — 5 novembre 2026

### Les congés payés utilisent la rémunération de leur période d'acquisition
- Les congés pris, les indemnités de départ et la provision partagent le calcul légal du dixième, comparé au maintien de salaire.
- Les absences assimilées sont reconstituées et les primes exclues retirées, en distinguant les jours ouvrés des jours ouvrables.
- Une rémunération manquante ou une régularisation ambiguë est signalée ; les cumuls repris de l'ancien logiciel sont conservés.


## paie-2026-11-05.13 — 5 novembre 2026

### Les documents de départ n'inventent plus les heures d'un bulletin incomplet
- L'attestation France Travail indique « Non renseigné » si le bulletin repris ne porte pas son temps de travail ; une retenue d'entrée ou de sortie ne devient plus une absence.
- La phrase sur les organismes complémentaires reste lisible quand leur nom manque.
- La mention légale du certificat de travail reste en pied de page, sans créer une deuxième page presque vide.

## paie-2026-11-05.12 — 5 novembre 2026

### Le code PCS d'un collègue d'une autre société n'est plus posé sans l'accord de l'Insee
- Le code d'un collègue de la société reste sûr. Celui d'un collègue d'une autre société ne l'est plus que si l'Insee range ce poste dans ce code.
- Sinon la fiche le propose, avec la raison, sans le remplir ; un métier exact de l'Insee passe devant (« Responsable qualité » en 387d).

### Contribution OETH : le Smic du 31 décembre de l'année due
- Martine lit le Smic au 31 décembre de l'année, comme le demande le guide de l'Urssaf : 11,88 € pour 2025, inchangé, et 12,31 € pour 2026 au lieu de 11,88 €.

## paie-2026-11-05.11 — 5 novembre 2026

### Le dossier de départ d'un CDD estime la prime et les congés selon la loi
- La prime de fin de contrat se calcule sur les salaires de ce contrat seulement, le dernier mois estimé au salaire ; plus aucun mois inventé après le départ.
- Les congés d'un départ déjà payé par l'ancien logiciel se recomptent depuis l'entrée, et le dossier le dit ; un départ en juin ne mélange plus deux périodes de congés sur le bulletin.
- Au choix d'un salarié en CDD, le formulaire de départ propose « Fin de CDD » et la date de fin du contrat ; tout reste modifiable.

## paie-2026-11-05.10 — 5 novembre 2026

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
