# Deux contrats le même mois : un bulletin par contrat (D3)

Date : 31/10/2026. Branche `feat/dsn-octobre`. Retour d'Elsa sur la vidéo H.

## Besoin

Elsa, le 28/10 : « si un salarié [part] et revient le même mois, Martine bloque sur l'obligation de générer le contrat le mois suivant (parfois on a des peintres, ressource rare, on doit les reprendre de suite et pas attendre le mois d'après). […] Gaëlle confirme que l'on ne peut pas attendre le mois d'après, on doit pouvoir faire son bulletin et son bulletin le même mois. »

Exemple : un CDD finit le 10/11, un nouveau contrat commence le 17/11. Aujourd'hui « Nouveau contrat » refuse : « Martine ne fait qu'un bulletin par mois. Il peut commencer le 01/12/2026 au plus tôt. »

Décision : deux bulletins en novembre, un par contrat. Pas un bulletin à deux périodes. La réduction générale se calcule « pour chaque contrat de travail » (CSS L241-13, III ; D241-7, V). La prime de précarité vaut 10 % du brut du seul contrat (C. trav. L1243-8). Le contrat qui finit paie ses congés à sa fin (L1242-16). Chaque contrat a donc son propre calcul, ce que le moteur sait déjà faire bulletin par bulletin.

## Ce qui existe déjà

- Le moteur borne un bulletin à son contrat : aucun événement du planning ne produit de paie avant l'entrée ni après la sortie (`calcul_brut.py`, « Aucun événement ne peut produire de paie hors contrat »). Le prorata d'entrée et de sortie compte les jours sous contrat. Un planning commun aux deux contrats donne donc deux bulletins justes, chacun sur ses jours.
- « Nouveau contrat » range le contrat précédent dans `employee_contract_periods`, avec la fiche qu'il avait (`fiche`). Un mois de ce contrat se recalcule sur cette fiche (`contrat_du_mois.fiche_du_mois`).
- Le premier mois d'un contrat part de cumuls vides (`cumuls_precedents_du_contrat`). Le bulletin du nouveau contrat ne reprend donc rien du bulletin de l'ancien, même dans le mois partagé.
- Le verrou de génération porte sur (salarié, année, mois). Il sérialise les deux bulletins du mois, ce qui suffit : on ne les génère pas en même temps.

## La clé du bulletin

Nouvelle colonne `payslips.contract_period_id` (uuid, nulle, `references employee_contract_periods(id) on delete restrict`).

- **Nulle** : le bulletin du contrat de la fiche pour ce mois. C'est le cas de tous les bulletins existants et de presque tous les bulletins à venir.
- **Remplie** : le bulletin d'un contrat rangé qui s'est terminé dans un mois où un autre contrat a commencé. Elle n'est remplie que dans ce mois partagé.

L'index unique `idx_payslips_company_unique` devient (company_id, employee_id, year, month, contract_period_id) `nulls not distinct`. Les écritures passent à `on_conflict="company_id,employee_id,year,month,contract_period_id"`. Vérifié sur PostgreSQL 17 en local le 31/10 : une écriture à clé nulle remplace le bulletin à clé nulle du mois, une écriture à clé remplie crée ou remplace le sien, sans toucher l'autre. La base de test tourne en PostgreSQL 17.6.

Même colonne sur `monthly_inputs` : une variable du mois partagé appartient au bulletin de son contrat.

`on delete restrict` : on ne peut pas retirer un contrat rangé qui a un bulletin dans un mois partagé. Sinon ce bulletin retomberait sur la clé nulle, déjà prise par le nouveau contrat.

Le planning (`employee_schedules`) reste unique par mois : il est commun aux deux contrats.

Un mois est **partagé** quand un contrat rangé avec sa fiche y finit et que le contrat de la fiche y commence. Cela se lit sur la fiche et dans `employee_contract_periods`, pas sur les bulletins. L'écran peut donc proposer le bulletin du contrat rangé même après sa suppression.

## Parcours

1. Le CDD finit le 10/11. Gaëlle clôture le départ et génère le bulletin de novembre, qui est le bulletin de sortie. Rien ne change ici.
2. « Nouveau contrat », début le 17/11. Le refus « dans le même mois » est levé. Restent ces refus :
   - le début doit tomber après la fin du contrat précédent ;
   - le bulletin du dernier mois doit déjà être généré, comme aujourd'hui. Dans un mois partagé, c'est le bulletin de novembre de l'ancien contrat.
3. À l'enregistrement, en plus des trois écritures existantes, le mois partagé est **rangé avec le contrat précédent**. Le bulletin de novembre à clé nulle et les variables de novembre à clé nulle reçoivent l'id du contrat rangé. Le rangement et le marquage passent en une seule transaction (fonction SQL `ranger_mois_partage`). Si le marquage échoue, on retire le contrat rangé et la fiche revient à son état d'avant, comme pour un échec de rangement aujourd'hui. Sans ce marquage, le premier bulletin du nouveau contrat remplacerait celui de l'ancien.
4. Le message de succès le dit : « Novembre 2026 aura deux bulletins : celui du contrat précédent (jusqu'au 10/11), déjà généré, et celui du nouveau contrat (depuis le 17/11), à générer. »
5. Gaëlle génère le bulletin de novembre du nouveau contrat, comme pour toute entrée en cours de mois.

## Génération

`process_payslip_generation` (et le générateur au forfait) reçoit `contract_period_id` (nul par défaut).

- **Clé nulle** : rien ne change, sauf l'écriture de la clé. Une garde refuse d'écrire si le bulletin à clé nulle du mois appartient à un autre contrat. On le voit à sa date d'entrée enregistrée (`payslip_data.en_tete.salarie.date_entree`), qui n'est pas le début du contrat de la fiche. Cela ne peut arriver que si le marquage a manqué. Le message : « Le bulletin de novembre du contrat précédent n'est pas rangé : régénérez-le depuis sa ligne, avant celui du nouveau contrat. » Jamais de remplacement silencieux.
- **Suppression** : supprimer un bulletin vide aujourd'hui les cumuls du mois (`payslips/infrastructure/repository.py`). Ce n'est fait que pour un bulletin à clé nulle : ces cumuls sont ceux du contrat qui continue.
- **Clé remplie** : c'est le bulletin du contrat rangé dans le mois partagé.
  - La fiche est celle du contrat rangé : `fiche_du_mois` reçoit l'id et prend la fiche rangée, même si le mois est celui du début du contrat en cours.
  - Il ne lit que les variables de sa clé.
  - Il ne lance pas la génération automatique des variables : celles de ce contrat ont été écrites quand il était en cours, et elles sont rangées.
  - Il n'écrit rien dans `employee_schedules`, ni cumuls ni `payroll_events`. Ceux du mois sont ceux du contrat qui continue, et le mois suivant les relit. Ses cumuls restent dans `payslip_data`.
  - Le PDF est recherché et remplacé par sa clé, et son nom porte « contrat-precedent ».
- **Variables automatiques** (`generate_monthly_variables`) : ne comptent que les jours du contrat de la fiche. Aujourd'hui, les règles qui comptent les postes du planning (paniers, astreintes, types de poste) lisent toute la fenêtre des variables. Dans un mois partagé, elles paieraient au nouveau contrat les postes de l'ancien. Elles n'écrivent et ne suppriment que des variables à clé nulle.
- **Effets défaits par mois** : le CET (`defaire_application_en_paie`) et la modulation (`defaire_credits_de_paie`) se défont par (salarié, mois). Régénérer un bulletin du mois partagé déferait ceux de l'autre. « Nouveau contrat » dans le même mois est donc refusé si le bulletin de l'ancien contrat porte du CET ou de la modulation : « Le bulletin de novembre porte un usage du CET : le nouveau contrat commence le 01/12 au plus tôt, ou corrigez d'abord ce bulletin. » Ce cas ne s'est jamais présenté pour un CDD court.

## Lecture : « le bulletin du mois »

Règle unique : une lecture par (salarié, année, mois) rend **le bulletin du contrat de la fiche**, c'est-à-dire la clé nulle, sauf si elle passe une clé. Une seule fonction, `bulletin_du_mois(employee_id, year, month, contract_period_id=None)`, sert toutes ces lectures. Les données existantes ont toutes une clé nulle : le comportement d'aujourd'hui ne change pas.

Passent la clé du contrat rangé :
- la génération et la correction de son bulletin ;
- son PDF ;
- ses documents de sortie (bulletin de sortie, solde de tout compte), quand on les refait après le nouveau contrat.

Lisent les deux bulletins du mois, parce que de l'argent ou un document du mois en dépend :
- le paiement des salaires : deux nets à payer. La garde « Doublon détecté » porte sur le bulletin, plus sur le salarié ;
- le PDF de tous les bulletins du mois ;
- le journal de paie et les écritures comptables. Ils somment déjà bulletin par bulletin. Les variables s'y rattachent au bulletin de leur clé, et non plus au salarié, qui les compterait deux fois ;
- la provision de congés : somme des deux ;
- les effectifs des exports et des indicateurs : nombre de salariés distincts, et non de bulletins.

## DSN du mois partagé

Elle déclare deux contrats pour l'individu, avec leurs rémunérations. Sa forme exacte (blocs 40, 50, 51 et 78) se lit dans le cahier technique avant d'être codée : c'est **D3.2**, une spécification à part. D'ici là, l'export DSN refuse le mois, nommément : « Novembre 2026 : [salarié] a deux contrats dans le mois. La DSN de ce cas n'est pas encore faite par Martine. » C'est un manque du verrou, comme les fiches incomplètes, et non une DSN qui perdrait un bulletin. Le signalement de fin de contrat (FCTU) de l'ancien contrat existe déjà.

## Écrans

- **Liste de paie** : la ligne du salarié montre le bulletin du contrat de la fiche, comme aujourd'hui. En dessous, une ligne « Contrat précédent, jusqu'au 10/11 » porte le bulletin rangé, avec son statut et ses actions (voir, régénérer, valider). Les contrôles du mois (à générer, à recalculer, validé) lisent les deux bulletins : le mois est complet quand les deux sont validés. Aujourd'hui `Payroll.tsx` et `listeControleMois.ts` prennent le premier bulletin trouvé pour le mois. Ils prendront celui de la clé nulle, et l'autre par sa clé.
- **Fiche du salarié, bulletins** : les deux bulletins de novembre, chacun avec les dates de son contrat.
- **Saisie des variables** : le mois montre les variables du contrat de la fiche. Une variable du contrat rangé s'ajoute par « Corriger le bulletin » sur son bulletin, qui écrit sa clé.

## Hors périmètre

- La DSN du mois partagé (D3.2, ci-dessus).
- Plus de deux contrats dans le même mois.
- Les salaires de référence (maintien, attestations, PPV) lisent, pour le mois partagé, le bulletin du contrat de la fiche. Ils ne voient donc pas la part de l'ancien contrat. C'est un écart de niche, corrigeable à la main, et on le dit dans la vidéo H.5.
- Le délai de carence entre deux CDD sur le même poste (C. trav. L1244-3) : c'est à l'employeur de le respecter, Martine ne le contrôle pas.
- Une génération groupée « tout le mois » ne régénère que le bulletin du contrat de la fiche. Le bulletin rangé se régénère depuis sa ligne.

## Mise en ligne

La migration et le code partent ensemble. L'ancien `on_conflict` n'a plus d'index, et le nouveau n'existe pas avant la migration. La migration ne modifie aucune donnée existante : elle ajoute deux colonnes nulles, remplace l'index et crée `ranger_mois_partage`.

## Tests

- Domaine : « Nouveau contrat » accepte un début le même mois après la fin. Il refuse un début avant la fin, un dernier bulletin non généré, et un bulletin portant du CET ou de la modulation.
- `fiche_du_mois` avec une clé : la fiche rangée, y compris pour le mois de début du contrat en cours.
- Génération avec une clé : elle ne lit que les variables de sa clé, n'écrit pas `employee_schedules`, remplace son seul PDF et écrit sa clé. Avec la clé nulle : la garde refuse si le bulletin du mois porte un autre contrat.
- Variables automatiques bornées au contrat : un panier du 5/11 n'est pas compté au contrat qui commence le 17/11.
- Exports : paiement (deux nets, pas de doublon), journal et OD (variables comptées une fois), effectif distinct, et refus nommé de la DSN.
- Cas complet en bac à sable sur un salarié de Recette chez MAJI, supprimé ensuite : sortie le 10/11, retour le 17/11, deux bulletins. La somme des deux bruts égale le brut d'un mois entier au prorata des jours, à la réduction générale près, calculée par contrat.

## Sources

- Retour d'Elsa : `~/dev/eywai-videos/chantiers-elsa/H.md`, ligne 12 (28/10/2026).
- C. trav. L1243-8 et L1242-16 ; CSS L241-13 et D241-7 : adresses et lecture dans `docs/superpowers/specs/2026-10-03-nouveau-contrat-design.md`.
- PostgreSQL, index unique `NULLS NOT DISTINCT` et `ON CONFLICT` : essai local sur PostgreSQL 17.10, le 31/10/2026 (deux écritures à clé nulle donnent une ligne, deux écritures à clé remplie en donnent une autre).
