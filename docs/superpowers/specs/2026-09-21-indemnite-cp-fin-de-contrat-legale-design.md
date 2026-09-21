# Indemnité de congés payés de fin de contrat : la règle légale, par période — conception

Date : 21 septembre 2026. Décision d'Alexandre après l'Excel de Gaëlle : son
940,23 reposait sur des bruts faux ; la loi a raison. On retire l'option
« salaire rétabli, congés N-1 inclus » construite le matin même (sa
décomposition tombait au centime par coïncidence), et on remplace le dixième
« de tout » par le calcul légal : par période de référence, sur les seuls
jours restants, en comparant au maintien.

## Ce que la loi dit

À la fin d'un CDD (ou d'une mission d'intérim), les congés acquis et non pris
sont payés par une indemnité compensatrice. Pour chaque période de référence
(du 1er juin au 31 mai), l'indemnité vaut le plus favorable de :

- **le dixième** : 10 % de la rémunération brute de la période, précarité
  comprise, ramené aux jours restants — `dixième × restants / droits` ;
- **le maintien** : les jours restants × ce que vaut un jour de salaire.

Les jours déjà pris pendant le contrat ont été payés à leur date (retenue +
indemnité) : ils ne sont pas repayés, puisque seuls les jours restants comptent.
C'est la deuxième formule que Gaëlle a montrée (1 862,90 pour 25 jours →
74,52 par jour, 0,24 jour → 17,88), et celle du chantier noté le même jour.

## Recette : Aurélien Demory, juillet 2026

| Période | Brut de la période | Droits | Restants | Dixième | Maintien | Retenu |
|---|---|---|---|---|---|---|
| 2025-2026 (23/03 → 31/05) | 4 171,35 | 3,78 | 2,78 | 417,14 × 2,78/3,78 = 306,78 | 2,78 × 98,48 = 273,77 | 306,78 |
| 2026-2027 (01/06 → 24/07) | 2 026,41 + 1 772,64 + 797,04 = 4 596,09 | 4,16 | 4,16 | 459,61 | 4,16 × 98,48 = 409,68 | 459,61 |
| **Total** | | | | | | **766,39** |

Contre 876,74 aujourd'hui (dixième de tout, le jour pris le 13/07 repayé) et
940,23 chez Gaëlle (base fausse). Précarité inchangée : 797,04.

## Où viennent les nombres

- **Rémunération de la période en cours** : `cumuls.brut_reference_n_1` du
  mois précédent (la somme des bruts depuis `brut_reference_period_start`) +
  le brut du mois hors indemnité de congés + la prime de précarité (ou l'IFM).
- **Rémunération de la période précédente** : `brut_reference_n_1` des cumuls
  du dernier mois de cette période (mai : 4 171,35 pour Demory, période
  2025-06-01 → 2026-05-31) ; à défaut, la somme des `salaire_brut` des
  bulletins de la période ; à défaut, inconnue → la période se règle au
  maintien seul, et le bulletin le dit.
- **Jours** : les compteurs du pied de page
  (`get_absence_balances_for_payslip`) : `conges_payes` (période en cours) et
  `conges_payes_periode_precedente` — `solde` = restants, `pris + solde` =
  droits de la période. On n'utilise pas `acquis` tel quel (7,0 chez Demory
  pour un solde de 2,78 : il ne suit pas la reprise, cf.
  cp-double-compte-changement-de-periode).
- **Valeur d'un jour au maintien** : la règle de `calcul_conges` (à 39 h :
  7 h de base + 0,8 h structurelle majorée = 98,48 pour Demory).
- **Taux** : `cdd.indemnite_conges.taux` / `interim.indemnite_conges.taux`,
  défaut 0,10 ; `cdd_sans_iccp` et `block_iccp_cdd` inchangés.

## Repli

Sans compteurs (bac à sable sans base, tests unitaires sans `employee_id`), le
moteur garde le dixième de toute la rémunération, précarité comprise — le
comportement d'aujourd'hui — et le détail le dit (`methode: "dixieme_global"`).

## Ce qui est retiré

L'option `companies.settings.indemnite_cp_fin_cdd` et tout ce qui la portait :
`engine/iccp_fin_cdd.py` (méthode, salaire rétabli, assiette, mention), le
paramètre `parametres_paie.indemnite_cp_fin_cdd`, `contexte.solde_cp_n_1_fin_de_mois`,
le champ du PATCH, la carte front et son utilitaire, leurs tests, la spec et le
plan `2026-09-21-indemnite-cp-fin-cdd-methode`. Le réglage a été retiré de
Colorplast sur le test le 21/09.

## Où ça vit

- Pur : `engine/iccp_fin_contrat.py` — `PeriodeConges(libelle, brut, droits,
  restants)`, `indemnite_par_periode`, `indemnite_fin_de_contrat(periodes,
  taux, valeur_jour) -> IndemniteFinDeContrat(periodes détaillées, total,
  mention, resume())`, `valeur_jour_maintien`.
- `calcul_brut._calculer_iccp_cdd` : si `contexte.cp_fin_de_contrat` (dict
  posé par le run) porte des périodes, calcul légal ; sinon repli. Détail sur
  `contexte.detail_iccp_fin_contrat`.
- `payslip_run_heures.cp_fin_de_contrat(contexte, employee_id, year, month)` :
  seulement au dernier mois d'un CDD ou d'une mission ; lit les compteurs et
  la rémunération de la période précédente ; pure fonction de mise en forme
  `periodes_depuis_compteurs(...)` testée.
- `engine/bulletin` → `bulletin["indemnite_cp_fin_contrat"]` ; `bulletin_view` :
  note avant le brut.

## Hors périmètre

L'acquisition prorata du mois de sortie (nos compteurs donnent 4,16 j pour N,
Gaëlle 1,66 pour juillet) : question des compteurs, pas de l'indemnité.
