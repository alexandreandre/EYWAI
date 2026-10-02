# Demandes Gaëlle — 1er octobre 2026

Quatre ajouts, dans cet ordre. Chacun est utilisable seul. Les dates d’été Comitech ne sont pas dans ce lot.

## 1. Congé sans solde

La RH le choisit dans « Nouveau congé ». À la validation, le jour du calendrier devient `absence_non_remuneree` (déjà une absence non payée). Le salarié ne le demande pas lui-même. Le JTC continue de ne pas écrire le calendrier.

Un jour d’absence est enregistré à 0 h. Le moteur doit quand même retenir une journée contractuelle : `_heures_evenement_absence` le fait déjà si l’événement arrive jusqu’au bulletin. Aujourd’hui un événement à 0 h est jeté, sauf arrêt et férié. `absence_non_remuneree` rejoint cette liste, parce que c’est le sens du type. Conséquence : un jour déjà typé ainsi à 0 h sera retenu à la prochaine paie.

## 2. Jour École

Type de jour du calendrier, pas une demande de congé. L’alternant n’est pas dans l’entreprise. La journée est payée : ce n’est pas une absence, le salaire mensualisé ne baisse pas. Les heures supplémentaires restent celles saisies comme pour les autres, ou pointées un autre jour. On ne compte pas les heures d’école comme des heures travaillées.

Un mois sans aucun jour « travail » ni congé payé déclenche une retenue du mois entier. Un jour École compte comme un jour couvert, pour ne pas effacer ces journées.

La copie du mois précédent ne recopie pas un jour École.

## 3. Brut pour la durée du contrat

À côté de « Salaire de base mensuel », si la durée hebdomadaire dépasse 35 h. Pour 39 h, le libellé parle de 169 h (39 × 52 / 12).

Le montant saisi est le salaire de base à 35 h. Le chiffre affiché ajoute les heures entre 35 h et la durée du contrat, majorées de 25 %. C’est le même calcul que `salaire_contractuel_total_hors_hs_mode`. Aucun nom de société. Le bulletin n’est pas modifié.

## 4. Contrats précédents

La fiche ne garde qu’un contrat. Un CDD terminé puis une réembauche fait disparaître le premier, et l’ancienneté ne doit pas recoller le trou toute seule.

Table `employee_contract_periods` : début, fin, type. La RH ajoute le contrat passé. Le contrat affiché en tête reste celui de la fiche (`hire_date`, `contract_end_date`). `seniority_reference_date` n’est pas recalculée. On n’invente pas les dates d’un salarié déjà en base.
