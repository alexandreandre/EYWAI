# Indemnité de congés payés de fin de CDD : méthode au choix — conception

Date : 21 septembre 2026. Décision d'Alexandre : régler côté moteur l'écart
de 63,49 € sur le bulletin de sortie d'Aurélien Demory (juillet 2026), par un
réglage société nommé, sans toucher à la règle par défaut.

## Le constat

Quadra : « Ind. de CP des CDD » 940,23. Nous : 876,74 (dixième légal de la
rémunération versée pendant le contrat, précarité comprise : 6 197,76 +
1 772,64 + 797,04 = 8 767,44). La base de Quadra, 9 402,30, se décompose au
centime, et c'est la seule décomposition qui tombe juste parmi dix variantes :

| Brique | Montant |
|---|---|
| cumul brut du contrat à fin juin | 6 197,76 |
| mois de sortie **rétabli** : 151,67 h × 12,31 + 17,33 h × 15,3875 | 2 133,73 |
| précarité | 797,04 |
| solde de congés N-1 restant, au maintien : 2,78 j × 98,48 | 273,77 |
| **assiette × 10 %** | **940,23** |

Un seul cas en 2026 chez Colorplast : la mention sur le bulletin fait voir la
formule à Gaëlle pour confirmation.

## Le réglage

`companies.settings.indemnite_cp_fin_cdd`, deux valeurs :

- `remuneration_versee` (défaut, rien ne change) : dixième du brut perçu
  pendant le contrat, précarité comprise.
- `salaire_retabli_solde_n1` : dixième calculé comme si le dernier mois avait
  été complet, précarité comprise, en ajoutant le solde de congés N-1 valorisé
  au maintien.

Libellé UI : « Indemnité de congés payés de fin de CDD », choix « Rémunération
réellement versée » / « Salaire rétabli du mois de sortie, congés N-1 inclus ».
Une valeur inconnue est refusée par le PATCH et lue comme le défaut par le
moteur.

## Ce que fait la méthode « salaire rétabli »

Sur le dernier mois d'un CDD (pas l'intérim, qui garde le dixième), l'assiette
du dixième devient :

1. **cumul brut du contrat** avant le mois : `cumuls.brut_total`, inchangé ;
2. **mois de sortie rétabli** : le salaire contractuel du mois plein
   (`heures mensuelles légales × taux horaire de base` + `HS structurelles
   mensuelles × taux majoré`), à la place du sous-total salaire contractuel
   réellement payé ; les autres éléments du mois (primes, indemnité et retenue
   de congés, absences) restent ce qu'ils sont ;
3. **précarité**, inchangée ;
4. **solde N-1** : les jours de congés N-1 restant à la fin du mois (après ceux
   pris dans le mois), valorisés à la valeur d'un jour au maintien, la même
   que celle qui paie un jour de congé (7 h de base + 0,8 h structurelle à
   39 h). Solde nul ou négatif : rien.

Montant = assiette × taux (barème `cdd.indemnite_conges.taux`, 0,10). La ligne
du bulletin garde son libellé ; une note sous le brut, du mécanisme de
l'arbitrage des congés, écrit les quatre briques et le résultat ;
`payslip_data.indemnite_cp_fin_cdd` garde le détail.

## Où ça vit

- Domaine pur : `app/modules/payroll/engine/iccp_fin_cdd.py` (méthode lue dans
  `entreprise.parametres_paie`, salaire rétabli, valeur du jour, assiette,
  mention).
- `calcul_brut._calculer_iccp_cdd` : choisit l'assiette selon la méthode et
  dépose le détail sur `contexte.detail_iccp_fin_cdd`.
- `payslip_run_heures` : quand la méthode est active et que c'est le dernier
  mois d'un CDD, lit le solde N-1 de fin de mois (la requête du pied de page)
  dans `contexte.solde_cp_n_1_fin_de_mois`.
- Générateur : `parametres_paie.indemnite_cp_fin_cdd` dans `entreprise.json`.
- `engine/bulletin` → `bulletin["indemnite_cp_fin_cdd"]` ; `bulletin_view` :
  note.
- Réglage : `CompanySettingsUpdate.indemnite_cp_fin_cdd` (Literal) ; carte
  front `IndemniteCpFinCddSettingsCard` dans la section « Jours fériés &
  congés ».

## Tests

- salaire rétabli à 39 h et 12,31 → 2 133,73 ; à 35 h → 151,67 × taux ;
- valeur du jour au maintien à 39 h et 12,31 → 98,48 ;
- assiette Demory → 9 402,30, montant 940,23 ; solde N-1 nul → pas de brique ;
- méthode inconnue ou absente → `remuneration_versee` ;
- mention ; note dans la vue ; schéma : valeur inconnue refusée ;
- recette en bac à sable : Demory juillet, méthode forcée → 940,23, brut
  3 509,91 (Quadra) ; méthode par défaut → 876,74 inchangé.

## Hors périmètre

La présentation des compteurs de congés à zéro sur le bulletin de sortie
(question 4 pour Gaëlle) ; l'intérim.
