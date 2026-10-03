# Nouveau contrat d'un salarié parti

Date : 03/10/2026. Version minimale, demandée par Alexandre : le moteur est bon, la gestionnaire paramètre. Branche `feat/nouveau-contrat`, non poussée.

## Besoin

Un salarié parti qui revient (réembauche, nouveau CDD, CDI après un CDD) n'a aujourd'hui qu'une fiche « partie ». La paie refuse alors ses mois. Exemple : la salariée revenue de Comitech, en CDD du 19/01/2026 au 31/05/2026, revenue le 01/09/2026. Son bulletin de septembre est refusé : « sortie le 31/05/2026 ».

## Parcours

Le bouton **Nouveau contrat** est dans la carte « Contrats » de la fiche d'un salarié parti, sorti ou inactif.

Le dialogue rappelle le contrat précédent : « Contrat précédent : CDD du 19/01/2026 au 31/05/2026. Il reste dans les contrats passés, avec son départ et ses bulletins. »

Champs :
- date de début, avec « Au plus tôt le 01/06/2026 » ;
- type : CDI, CDD, Apprentissage ou Contrat de professionnalisation ;
- date de fin : obligatoire pour un CDD, absente pour un CDI ;
- durée hebdomadaire, salaire de base mensuel et poste, préremplis depuis la fiche ;
- case « Reprendre l'ancienneté des contrats précédents ». Sous la case, la date d'ancienneté qui sera retenue.

Au succès, un message nommé : « Nouveau contrat enregistré : CDD du 01/09/2026 au 18/12/2026. Le contrat précédent (CDD du 19/01/2026 au 31/05/2026) est dans les contrats passés. Le bulletin de 09/2026 peut être généré. » La fiche, la carte et la liste de paie sont ensuite relues. Un refus s'affiche dans le dialogue, avec ce qu'il faut corriger.

Refus :
- départ pas clôturé ;
- début avant la fin du précédent, ou dans le même mois (EYWAI ne fait qu'un bulletin par mois) ;
- CDD sans date de fin ;
- dernier bulletin du contrat précédent pas généré : « Générez d'abord le bulletin de MM/AAAA ». Ce refus ne joue pas si ce mois a été payé par l'ancien logiciel, avant la bascule.

## Ce qui est écrit, sans migration

1. **La fiche** reçoit le nouveau contrat : date d'entrée, type, fin, durée, temps partiel, poste, statut `actif`, date d'ancienneté. Le début d'exécution et la date de conclusion, qui étaient ceux de l'ancien contrat, sont vidés. L'écriture n'a lieu que si la fiche n'a pas changé depuis sa lecture (double clic, autre onglet).
2. **Le contrat précédent** (type, début, fin) est rangé dans `employee_contract_periods`. Si ce rangement échoue, la fiche revient à son état d'avant.
3. **Le salaire** est historisé à la date de début, par le même chemin que l'onglet Augmentations. Si cette écriture échoue, la réponse dit où saisir le salaire.
4. **Une trace d'audit** est posée : `employee.contract.new`.

Le départ archivé, les bulletins, les cumuls et les absences restent intacts.

## Mois payables

Ils suivent la fiche : un mois est payable s'il chevauche le nouveau contrat. Les mois entre deux contrats ne le sont pas. Les mois de l'ancien contrat ne se recalculent plus, puisque la fiche décrit désormais le nouveau. Aucune règle de paie n'est ajoutée pour cela : la date d'entrée suffit.

## Ancienneté

La RH décide avec la case, sans calcul :
- case cochée : la date d'ancienneté du contrat précédent est gardée, ou à défaut son début ;
- case décochée : l'ancienneté part du début du nouveau contrat.

La date est toujours écrite, parce que la date d'entrée change. Un champ vide retomberait sur la nouvelle date d'entrée sans que personne l'ait décidé.

## Cumuls du premier mois

Au premier mois d'un contrat, le bulletin part de cumuls vides, ceux du mois précédent n'appartenant pas à ce contrat. La règle est la même que la garde de janvier, dans les deux générateurs.

Pourquoi :
- la réduction générale se calcule « pour chaque contrat de travail » (CSS L241-13, III ; D241-7, V ; BOSS § 1070) ;
- l'indemnité de fin de CDD vaut 10 % du brut du seul contrat (C. trav. L1243-8) ;
- l'ancien contrat a payé ses congés à sa fin (L1242-16).

Sans cette règle, un CDD repris le 1er du mois suivant paierait sa prime de précarité sur les deux contrats.

Pour une première embauche, ou pour la salariée revenue, rien ne change : le mois d'avant n'a pas de cumul.

La règle est vérifiée sur le cas réel : Quadra recalcule la réduction de septembre sur le seul nouveau contrat, 636,98 € (formule sur 2 365,33 € et 169 h × 12,02 €). Il continue pourtant d'imprimer les cumuls de l'année.

## Hors périmètre

- PDF de chaque contrat ;
- suite d'un CDD en CDI sans départ (L1243-11) : se fait aujourd'hui dans « Modifier la fiche » ;
- deux contrats dans le même mois ;
- calcul de la période d'essai ;
- DSN du nouveau contrat ;
- annulation d'un nouveau contrat : se fait par « Modifier la fiche » et « Retirer ».

## Sources

- C. trav. L1243-8, L1242-16 : https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006901219 et https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006901210
- CSS L241-13 : https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000053280526
- CSS D241-7 : https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000054252241/2026-03-01
- BOSS, Allègements généraux, § 1070 et § 1080 : https://boss.gouv.fr/portail/accueil/exonerations/allegements-generaux.html. Copie datée dans `docs/reference/reduction-generale-2026/boss-rgdu.md`.
