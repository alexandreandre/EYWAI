# Journal des versions de Martine

Chaque déploiement du site de paie porte une étiquette `paie-AAAA-MM-JJ.N`, affichée en bas du menu.
Pour chaque changement : trois lignes, en mots d'utilisatrice.

## Pas encore déployé

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
