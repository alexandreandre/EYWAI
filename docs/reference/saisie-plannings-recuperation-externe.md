# Saisir les plannings et les récupérations suivies hors Martine

Guide pour les salariés à temps plein dont le temps est décompté en heures.
Les temps partiels et les forfaits jours suivent leur propre circuit. Le type
« Repos / récupération externe » et la période des saisies sont en ligne depuis
la version paie-2026-11-13.1.

**La compensation et le solde de récupération restent calculés dans votre
suivi externe. Martine reçoit les jours qualifiés et les heures
supplémentaires restant à payer.** Le choix « Repos » ne débite aucun compteur.

## 1. Préparer le mois

1. Sélectionnez la société et le salarié, puis le mois dans **Calendrier** ou
   dans l'onglet **Calendrier** de sa fiche.
2. Vérifiez la période des variables de paie : elle peut commencer le mois
   précédent. Complétez également les pointages de cette partie de période.
3. Posez l'horaire prévu avec le modèle de semaine applicable. Le prévu est
   l'horaire de référence ; le réel contient les heures effectivement faites.
4. Importez les pointages, puis examinez les jours à zéro et les absences.
   Un zéro ne permet pas de reconnaître un congé, une récupération ou un arrêt.

## 2. Choisir le type de chaque jour

| Situation confirmée | Type dans le calendrier | Saisie et contrôle |
| --- | --- | --- |
| Travail effectué | Travail | Horaire prévu et heures réellement faites |
| Récupération autorisée, suivie dans un compteur externe | Repos / récupération externe | Prévu 0 h, réel 0 h ; mouvement à enregistrer dans le suivi externe |
| Jour normalement non travaillé | Week-end ou Repos | Prévu 0 h ; conserver les éventuelles heures réellement travaillées |
| Congé payé | Congés payés | La saisie RH synchronise une demande validée ; contrôler le solde CP |
| RTT | RTT | Contrôler la demande et le solde RTT |
| Arrêt de travail | Arrêt maladie et demande d'arrêt qualifiée | Renseigner les dates et le motif exact dans Absences |
| Absence réellement sans rémunération | Absence non rémunérée | Contrôler la retenue au bulletin |
| Zéro dont le motif n'est pas connu | Faire confirmer le motif | Ne pas décider d'une récupération à partir du zéro seul |

Pour une récupération demandée sur un **compteur géré dans Martine**, passez
par **Absences** avec le type de récupération approprié : le repos saisi au
calendrier ne remplace pas la demande ni son débit.

## 3. Saisir une journée de récupération externe

1. Faites confirmer la récupération par le responsable et vérifiez le solde
   du suivi externe. Notez dans ce suivi la date, la durée autorisée et
   l'horaire initial avant de le remplacer par zéro dans Martine.
2. Cliquez sur le jour concerné. Dans le choix du type, sélectionnez
   **Repos / récupération externe**. La cellule affiche ensuite **Repos**.
3. Le prévu passe à **0 h**. Conservez le réel importé à **0 h**.
4. Enregistrez le calendrier.
5. Déduisez dans le suivi externe la durée de récupération autorisée, selon
   l'horaire initial conservé. Gardez la validation et le solde après débit.

Le salaire mensualisé est conservé pour ce repos, sans retenue d'absence ni
consommation de CP provoquée par cette saisie. Le compteur externe, lui, ne
change que lorsque vous le mettez à jour. Les autres absences du mois
continuent d'avoir leur effet habituel.

Ne requalifiez pas en repos un arrêt ou un congé déjà validé pour faire
disparaître une alerte. Corrigez le motif à sa source si la demande est erronée.
Si le réel contient des heures, le choix Repos les conserve : faites vérifier
le pointage et la récupération avant la paie. Appliquez les modèles et les
copies de mois avant de qualifier les récupérations ; une copie reprend un
rythme et ne constitue pas une nouvelle autorisation de récupération.

## 4. Reporter les heures restant à payer

1. Terminez le calcul dans le suivi externe : heures à récupérer, récupérations
   prises, solde conservé et heures supplémentaires restant à payer, par taux.
2. Dans **Mon Entreprise → Paie**, vérifiez que **Compensation des heures
   entre semaines** est désactivée pour le circuit traité à l'extérieur.
   Vérifiez aussi qu'aucun routage automatique vers un compte d'heures ou CET
   ne refait le même traitement. La règle société « Tout payer au bulletin »
   peut être modifiée par un choix individuel de mise au compteur sur le mois :
   contrôlez aussi ce choix. Vérifiez les mouvements CET déjà validés pour
   le salarié et le mois, même si vous n'autorisez plus de nouvelles demandes.
3. Générez un bulletin brouillon, ouvrez-le, puis l'onglet **Corriger**.
4. Cliquez sur **Ajouter une ligne**, puis la tuile **Des heures** et
   **Ce mois-ci**. Déclarez les quantités définitives dans **Majorées à 25 %**
   et **Majorées à 50 %**, puis **Appliquer** : le bulletin est recalculé et le
   net avant/après s'affiche.
5. Si rien ne doit être payé, déclarez explicitement **0 aux deux taux** depuis
   cet écran. Une saisie ordinaire à zéro dans les variables ne suffit pas à
   effacer les heures calculées depuis le planning. **Reprendre les heures du
   planning** annule la déclaration.
6. Contrôlez les quantités et les montants au bulletin, puis les cotisations,
   le net et les cumuls après le recalcul.

Si un compteur Martine reste ouvert pour des droits antérieurs, son solde
reste dû. Ne le supprimez pas pour traiter le mois à l'extérieur. Lorsque
la carte **Heures de récupération** indique que les heures du mois sont mises
au compteur, le choix RH **Payer ces heures ce mois-ci** permet de les payer
sur ce bulletin. Contrôlez le résultat et l'absence d'un nouveau crédit après
recalcul. Ne recopiez pas le solde externe dans ce compteur.

Pour un **temps partiel**, la même tuile **Des heures → Ce mois-ci** propose
les heures complémentaires, avec les paliers affichés pour son contrat.
Les quantités déclarées remplacent celles du planning, y compris zéro ; elles
ne doivent pas être saisies dans les heures supplémentaires du temps plein.
Un **forfait jours** reste décompté en jours et n'utilise pas ces cartes d'heures.

**Exemple de saisie, une fois les droits calculés et validés à l'extérieur :**
le responsable autorise un repos de 7 h et confirme 3 h à payer à 25 %, 0 h
à 50 %. Le jour est saisi en Repos, prévu 0 h et réel 0 h. Le suivi externe
porte le débit de 7 h ; le bulletin reçoit la déclaration de 3 h à 25 % et
0 h à 50 %. Cet exemple ne définit aucune règle de conversion entre heures
supplémentaires et repos.

## 5. Comprendre les alertes

- **Travail prévu avec réel à 0 h** : un travail prévu n'est pas réalisé.
  Confirmez le motif, puis qualifiez le jour. Ne recopiez pas le prévu dans
  le réel pour faire disparaître l'alerte.
- **Absent — type à donner** : l'import a repéré une absence dont le motif
  manque. Donnez le motif réel avant la paie.
- **Heures pendant un arrêt ou une absence** : vérifiez les pointages et la
  demande ; ne supprimez pas une absence justifiée pour passer le contrôle.
- **Aucune heure pointée sur tout le mois** : Martine peut reprendre le prévu.
  Vérifiez l'import ; un mois vide ne prouve pas un mois entièrement absent.

## 6. Pauses, paniers et astreintes

Dans les modèles de semaine, ouvrez **Détail des pauses**. Séparez les pauses
payées des pauses non payées. Les heures de travail doivent être nettes des
pauses non payées ; si les pointages les excluent déjà, ne les retranchez pas
à nouveau du réel.

Pour une organisation qui conserve les paniers et astreintes en saisie
manuelle, ajoutez les montants validés dans les saisies du mois. Vérifiez les
règles automatiques déjà actives pour éviter un doublon. Le droit, le montant
et le traitement social d'un panier se vérifient selon la société et la situation.

## 7. Ajouter la période d'un maintien saisi à la main

Dans **Ajouter une saisie du mois** ou **Ajouter une prime** depuis le bulletin,
choisissez la rubrique du catalogue applicable, puis renseignez **Période à
afficher sur le bulletin → Du / Au**. L'aperçu montre le libellé imprimé,
par exemple : « Rappel de maintien de salaire du 01/10/2026 au 05/10/2026 ».

Le montant reste payé sur le mois sélectionné. Les dates sont conservées
dans le libellé de cette saisie : elles ne déplacent pas le versement et ne
modifient pas les dates de l'arrêt, les droits au maintien ou les IJSS.
Contrôlez d'abord le maintien déjà calculé pour saisir seulement le complément dû.
Pour une régularisation qui doit être rattachée à un autre mois dans la DSN,
utilisez la régularisation d'un mois passé depuis le bulletin : la période
descriptive d'une saisie ne fait pas ce rattachement.

## Contrôle avant validation

- Les jours à zéro ont tous un motif confirmé et les pointages sont complets.
- Les récupérations sont débitées une seule fois dans le compteur retenu.
- Les quantités d'heures sup du bulletin correspondent au calcul externe.
- Ni retenue non rémunérée ni débit de CP n'apparaît pour le repos externe.
- Aucun panier ou astreinte n'est doublé par une règle automatique.
- Les bulletins ont été recalculés après les corrections des variables.

Le choix d'un type dans le logiciel ne constitue pas un accord de récupération.
Le remplacement du paiement des heures supplémentaires par du repos, y compris
les majorations, dépend du dispositif applicable : voir les
[articles L3121-28 à L3121-37 du Code du travail](https://www.legifrance.gouv.fr/codes/id/LEGISCTA000033020522).
