# Journal des versions de Martine

Chaque déploiement du site de paie porte une étiquette `paie-AAAA-MM-JJ.N`, affichée en bas du menu.
Pour chaque changement : trois lignes, en mots d'utilisatrice.

## Pas encore déployé

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
