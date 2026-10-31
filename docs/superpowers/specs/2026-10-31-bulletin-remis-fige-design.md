# Bulletin remis : mis à disposition à date, puis figé (D4 et D5)

Date : 31/10/2026. Feuille de route du 30/10, chantier 4. D4 : « bulletin remis figé, correction le mois suivant ». D5 : « date de mise à disposition réglable par société (1er du mois suivant par défaut), anciens bulletins toujours visibles ». Les deux tiennent ensemble : un bulletin est remis le jour où le salarié peut le voir.

## Ce que disent les sources

service-public.fr, fiche F559 (ouverte le 31/10) :
- « Tout salarié doit recevoir une fiche de paie lors du paiement du salaire. »
- « Pour la remise de la fiche de paie électronique, l'employeur doit indiquer au salarié les conditions dans lesquelles la fiche de paie est disponible. »
- Disponibilité garantie « pendant une durée de 50 ans à compter de son émission » ou 6 ans après la retraite : les anciens bulletins restent visibles.

Elsa (vidéo J, 29/10) : on régularise toujours sur M+1, on ne reprend jamais un bulletin édité.

## Ce qui existe

- Le salarié voit un bulletin dès sa validation (`payslips/infrastructure/queries.py`, `get_my_payslips`), et il en est notifié à ce moment.
- Un verrou de période bloque la correction et la restauration à partir du 15 du mois suivant (`payslips/domain/period_edit_lock.py`, réglage global), quel que soit le statut. Mais « Régénérer » rouvre un bulletin validé à toute date, et l'application des IJSS aussi : le verrou se contourne.

## La règle

- **Réglage par société** `settings.bulletins_mise_a_disposition_jour` : 0 = dès la validation, 1 à 28 = ce jour du mois suivant. Sans réglage : le 1er du mois suivant.
- **Remis le** : un bulletin validé est remis le plus tard des deux jours, sa validation et la date de mise à disposition de son mois. Le bulletin du mois de sortie est remis dès sa validation : il est payé avec le solde de tout compte, le jour du départ. Un brouillon n'est jamais remis.
- **Le salarié** voit ses bulletins remis, et ceux-là seulement (liste, détail, courbe des nets). Il est notifié le jour de la remise : à la validation si elle est déjà passée, sinon par la tâche quotidienne `scripts/notifier_bulletins_remis.py` (son cron reste coupé avant la production, comme les autres envois).
- **Un bulletin remis est figé** : ni correction, ni restauration, ni « Régénérer », ni IJSS appliquées. Message : « Ce bulletin a été remis au salarié le 01/11/2026 : il ne se modifie plus. Une erreur se corrige sur le bulletin de novembre 2026, par une régularisation. » L'administrateur de la plateforme garde la main, comme pour le verrou de période (correction sur accord d'Alexandre).
- **L'écran RH** dit, sur un bulletin validé pas encore remis : « Visible par le salarié le … Jusque-là, il se corrige encore ». « Correction autorisée jusqu'au … » s'arrête la veille de la remise. Une fois remis, le verrou le dit (« Ce bulletin a été remis au salarié le … »).
- **Le réglage** se choisit dans « Paramètres de paie » : « Bulletins visibles par les salariés », de « Dès la validation » à « Le 28 du mois suivant ».
- Le verrou de période du 15 reste tel quel, pour les brouillons.

## Effet sur la base de test

Lu le 31/10 : aucun bulletin d'octobre ; septembre est repris de Quadra (brouillons importés, déjà intouchables). La règle s'applique à partir d'octobre. Le réglage n'entre pas dans l'empreinte des bulletins (`parametres_societe_pour_empreinte` ne prend que des clés nommées) : rien ne passe « À recalculer ».

## Découpage

- `payslips/domain/mise_a_disposition.py` (pur) : jour réglé, date de remise, messages.
- Moteur : la marque `bulletin_de_sortie` écrite dans le bulletin (déjà calculée pour les alertes de congés), sans effet sur les montants.
- `payslips/application/remise.py` : la date de remise d'un bulletin lu en base (réglage de la société).
- Branchements : liste et détail du salarié, notification, verrou (`period_edit_lock`), garde de régénération (`_check_validated_guard`, champ `modifier_bulletin_remis`), IJSS.
- Société : validation et enregistrement du réglage (`companies/domain/parametres_paie.py`).
- Frontend : le réglage dans « Paramètres de paie », la ligne de remise sur l'écran du bulletin.

## Tests

- Domaine : défaut au 1er, 0 = validation, validation après la date, décembre vers janvier, sortie, brouillon, borne 1-28.
- Branchements : le salarié ne voit pas un bulletin validé avant la date ; correction, restauration et régénération refusées sur un bulletin remis, permises avant ; l'administrateur passe ; pas de notification avant la remise.
- Frontend : le réglage envoyé seulement s'il change, la ligne de remise.
