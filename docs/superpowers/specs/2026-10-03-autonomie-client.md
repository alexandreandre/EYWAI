# Autonomie du client : ce que le développeur fait encore à sa place

Date : 03/10/2026. Objectif : que les gestionnaires de paie fassent tout à l'écran,
et que le développeur ne fasse plus que de la maintenance.

Règle de partage :

| Donnée | Exemples | Qui la tient |
|---|---|---|
| Nationale | SMIC, plafond Sécu, taux URSSAF, grille d'impôt | EYWAI, par la synchro des taux (surveillée en maintenance) |
| Propre à la société, notifiée par un organisme | taux AT/MP, chômage bonus-malus, effectif | Le client, page société « Paramètres de paie » |
| Propre au salarié | contrats, réembauches, taux d'impôt personnalisé | Le client, fiche du salarié |
| Règles de calcul | moteur de paie | Le développeur |

Inventaire des interventions par script de septembre et octobre 2026, classées.

## A. Ponctuel : bascule depuis Quadra (normal)

- Reprise des bulletins et cumuls de janvier à août (deux sociétés), reprise d'août
  d'un CDD, ouverture d'un forfait jours (heures de la réduction générale, garde
  ajoutée dans le moteur le 03/10).
- À refaire pour chaque nouveau client (Mont-Blanc) : c'est le démarrage, il reste au
  développeur. À documenter comme une procédure.

## B. Récurrent, l'écran existe déjà : le client le fait seul

| Intervention faite par script | Écran |
|---|---|
| Annuler un congé validé en double | Congés & absences, « Annuler » |
| Retirer des heures saisies sur le mauvais salarié | Calendrier |
| Jours d'école d'un alternant | Calendrier, type « École » |
| Taux de prévoyance d'un salarié | Modifier la fiche, prévoyance |
| Salaire saisi pour 35 h | Modifier la fiche |
| Régénérer un bulletin | Paie |
| Départ, documents de sortie, retirer un document | Départs |
| Taux d'impôt personnalisé | Prélèvement à la source, « Modifier le taux » |
| Compensation des heures entre semaines | Société, carte dédiée |
| Carence conventionnelle | Société, carte maintien de salaire |

## C. Récurrent, écran manquant : en cours le 03/10

| Intervention | Fréquence | Écran |
|---|---|---|
| Taux d'assurance chômage bonus-malus | une fois par an | Paramètres de paie |
| Effectif retenu pour les seuils (11, 20, 50) | une fois par an | Paramètres de paie |
| Date de paiement des salaires | rare | Paramètres de paie |
| Journée de solidarité | une fois par an | Paramètres de paie |
| Réembauche, contrats successifs | chaque mois | Fiche, « Nouveau contrat » |
| Rattraper un relevé de pointage déjà importé | à chaque erreur d'import | Import, « Refaire l'import de ce fichier » |

## D. Récurrent, à décider

1. **Horaires d'été et d'hiver** (demande du 02/10) : deux plannings types et une date
   de bascule réglée par la RH. Proposé, en attente de validation.
2. **Congés validés en double** (deux fois en un mois) : refuser à la saisie un congé
   sur un jour déjà couvert par un congé validé. Recommandé.
3. **Arrêts qui se chevauchent** : l'alerte existe ; les refuser à la saisie.
   Recommandé.
4. **Rappels de maintien de salaire** : EYWAI ne les calcule pas ; aujourd'hui saisis
   en prime à la main. Selon la méthode de la gestionnaire.
5. **Taux d'impôt** : à terme, lus automatiquement dans le compte rendu de la DSN,
   quand EYWAI déposera les DSN.

## E. Maintenance du développeur

- Synchro mensuelle des barèmes nationaux (réservée à l'administrateur depuis le
  01/10) : surveiller qu'elle passe chaque mois.
- Règles de calcul et corrections du moteur, toujours au filet de paie.
- Démarrage des nouveaux clients (reprise).

## Ce qui serait de la sur-ingénierie

- Calculer l'effectif seul : la règle légale demande cinq ans d'historique. Un champ suffit.
- Aller chercher le taux bonus-malus automatiquement : aucun service ne le fournit.
