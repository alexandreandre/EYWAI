# Format du bulletin de paie — alignement sur le gabarit Cegid

*afaire.md #24 — 4 août 2026*

## Problème

Notre bulletin PDF ([template_bulletin.html](../../../backend/app/runtime/payroll/templates/template_bulletin.html), 824 lignes) est un document « web » : titres colorés, sections empilées, cartes de cumuls, bandeaux d'avertissement, deux à trois pages. Le bulletin que les salariés reçoivent depuis toujours, celui du cabinet (Cegid), est une page A4 dense, sobre, à colonne latérale.

L'écart est purement formel — les montants sont les mêmes — mais il suffit à désorienter le lecteur, et c'est précisément la population la moins à l'aise avec un changement de document qui est concernée. Objectif : que personne ne remarque le changement d'outil.

## Décisions de cadrage

| Question | Décision |
|---|---|
| Ambition | Coller au format Cegid, pas une refonte à notre identité |
| Blocs EYWAI absents chez Cegid | Les fondre dans le gabarit, sans détailler |
| Périmètre | Le PDF **et** l'aperçu de la page RH d'édition |
| Bulletins déjà émis | Inchangés (les PDF sont figés dans le bucket `payslips`) ; la bascule vaut pour les bulletins générés ensuite |
| Moteur de calcul | Aucune modification. Chantier de présentation uniquement |

## Le gabarit cible

Référence : `data/cartol/bulletins/2026-06/06-2026-cartol-bulletin-de-salaire.pdf`, lisible avec `pdftotext -layout`.

### 1. Bandeau

Gauche : raison sociale, rue, code postal + ville, `Siret : … Code NAF : …`
Droite : `BULLETIN DE SALAIRE`, `Période : Juin 2026`, `Paiement le : 30/06/26`, `Du : 01/06/2026  Au : 30/06/2026`.

Le `<h1>` bleu pleine largeur disparaît.

### 2. Bloc compteurs (haut gauche)

Tableau `Acquis / Total pris / Solde` en lignes, une colonne par compteur :

| | CP N-1 | CP N | RTT | Repos comp. |
|---|---|---|---|---|

Les colonnes RTT et Repos compensateur ne s'affichent que si le compteur existe (acquis ou pris non nuls) — c'est ainsi que la section `#solde-conges` actuelle disparaît en se fondant ici.

Source : `pied_de_page.solde_conges` (`conges_payes_periode_precedente`, `conges_payes`, `rtt`, `repos_compensateur`).

Les mentions annexes du bloc actuel (fractionnement, CP ancienneté conventionnels, note forfait) passent en une ligne de note sous le tableau, en petit, uniquement si renseignées.

### 3. Bloc salarié (haut droite)

`MR ALVES Lucas` puis l'adresse postale sur deux lignes.

- Civilité : `employees.sexe` → `MR` / `MME`. Absente : rien, on démarre au nom.
- Nom : `NOM Prénom`, nom en majuscules (Cegid met le nom en premier).
- Adresse : `contrat.salarie.adresse` (rue, code postal, ville).

### 4. Ligne d'identité et bloc contrat

```
Matricule : ALVES              NoSécu. : 1 02 09 85 191 239 74
Entré(e) le : 08/04/2026
Emploi : Opérateur polyvalent          Ancienneté : 08/04/2026
Qualif :               Classif :              Coeff : A
```

- Matricule : `employees.matricule` (241/241 renseignés en production).
- NIR groupé par blocs comme Cegid : `1 02 09 85 191 239 74`.
- Ancienneté : `contrat.seniority_reference_date`, **repli sur `date_entree`** quand elle est absente (81 actifs sur 241).
- Qualif / Classif / Coeff : éclatés depuis `classification_conventionnelle`, là où le template actuel affichait une chaîne unique via `_formater_classification`.

### 5. Corps — tableau des rubriques

Cinq colonnes : `Rubriques | Base | Taux salarial | Montant salarial | Mt patronal`.

Ordre des lignes :

1. `SALAIRE DE BASE`, puis les lignes de brut (`calcul_du_brut`), les congés (`details_conges`), les absences (`details_absences`), le maintien (`details_maintien`)
2. `SALAIRE BRUT` — ligne de total, en gras
3. Les rubriques de cotisations dans l'ordre réglementaire, préfixées du code Cegid :

   | Code | Rubrique EYWAI (`RUBRIQUES_ORDRE`) |
   |---|---|
   | Q100 | Santé |
   | Q200 | AT-MP |
   | Q300 | Retraite |
   | Q400 | Famille |
   | Q500 | Assurance chômage |
   | Q600 | Autres contributions dues par l'employeur |
   | Q800 | CSG déductible |
   | Q801 | CSG/CRDS non déductible |
   | Q802 | Exonérations, allègements et réductions |

   Ces neuf codes sont les seuls que Cegid utilise — vérifié sur les bulletins de juin 2026 des sept sociétés (226 à 229 occurrences chacun, aucun autre `Q…`).

   Le regroupement lui-même ne bouge pas : `construire_cotisations_officielles` produit déjà cet ordre, hérité de l'arrêté du 25/02/2016. Seuls les codes et la mise en forme sont nouveaux. Les sous-totaux par rubrique du template actuel disparaissent (Cegid n'en a pas).

   **Divergence assumée sur la mutuelle et la prévoyance.** Cegid ne les range sous aucun code `Q` : il les imprime en lignes isolées avec ses propres références de contrat (`EP1 PREV GROUPAMA NC TA`, `EMU1 MUTUELLE ISOLE`, `EPR3`, `EMU4`…), juste avant `TOTAL DES RETENUES`. Ces références sont internes à son paramétrage et nous n'avons pas d'équivalent. Nous conservons donc notre rattachement, qui est celui de l'arrêté : mutuelle et complémentaire santé sous `Q100 Santé`, prévoyance sous sa rubrique. Les lignes portent leur libellé, sans code. C'est le seul écart visuel volontaire avec le bulletin du cabinet.

4. `TOTAL DES RETENUES` — montant salarial et patronal
5. `NET IMPOSABLE`
6. Les lignes hors brut, après le net imposable, comme Cegid place son `SPEQ INDEMNITE DE PANIER` :
   - primes non soumises (`primes_non_soumises`), une ligne chacune
   - **notes de frais : une seule ligne agrégée** `Remboursement de frais professionnels`, jamais le détail
   - acomptes et avances (`remboursements_avances`), retenues sur salaire, remboursement de prêt employeur, indemnités de transport
   - CSG/CRDS non déductible (rubrique Q801, qui chez Cegid figure après le net imposable)

### 6. Colonne latérale droite

Encadré étroit, une valeur par bloc :

| Bloc | Valeur | Source |
|---|---|---|
| SMIC Horaire | `contexte.smic_horaire` | à exposer dans le bulletin |
| Plafond Sécu | `baremes["pss"]["mensuel"]` | à exposer dans le bulletin |
| HEURES | heures période, cumul heures, cumul h. sup | `cumuls.cumuls.heures_remunerees`, `heures_supplementaires_remunerees` |
| Solde rep. remp. / rep. récup. | soldes de repos | `pied_de_page.solde_conges.repos_compensateur` |
| CUMULS | bases, bruts, heures majorées | `cumuls.cumuls.brut_total` |
| Allègement cotis. employeur | total des exonérations | `pied_de_page.total_exonerations` |
| Total versé employeur | coût total employeur | `pied_de_page.cout_total_employeur` |
| Paiement | `par Virement` / `par Chèque` / … | `employees.salary_payment_method` (241/241) |

C'est ici que se fondent les cartes `#cumuls-annuels` du template actuel : plus de grille de cartes ambrées.

### 7. Pied

```
MONTANT NET SOCIAL                                        1105.80
NET A PAYER AVANT IMPOT SUR LE REVENU                     1105.80
dont évolution de la rémunération liée à la suppression
des cotisations salariales chômage et maladie               20.46

   Impôt sur le revenu       Base      Taux    Montant   Cumul annuel
   Montant net imposable                       1128.07        3621.64
   Impôt prélevé à la source 1128.07   17.30    195.16         420.57
   Montant net des heures compl/suppl exo.        0.00         170.36

                              Net à payer au salarié (En Euros)
                                                            910.64

Convention collective nationale de la métallurgie
À défaut de convention collective : Code du travail — …
Pour plus d'informations sur le bulletin de paie clarifié : www.service-public.fr
Dans votre intérêt et pour vous aider à faire valoir vos droits, conservez ce
bulletin de paie sans limitation de durée.
```

Le net à payer est la seule valeur mise en avant typographiquement — plus de bandeau vert.

## Mention légale manquante

Le bulletin Cegid porte la mention *« dont évolution de la rémunération liée à la suppression des cotisations salariales chômage et maladie »* (art. R3243-1 du Code du travail). **Notre bulletin ne l'a jamais affichée.**

Formule retrouvée par recoupement sur le bulletin CARTOL de juin 2026 :

```
montant = brut × 3,15 %  −  base CSG × 1,7 %
```

Vérification : `1436,21 × 3,15 % − 1457,66 × 1,7 % = 45,24 − 24,78 = 20,46 €`, au centime près la valeur imprimée par Cegid.

Les 3,15 % correspondent aux cotisations salariales supprimées en 2018 (maladie 0,75 % + chômage 2,40 %) et les 1,7 % à la hausse de CSG qui les a compensées. La ligne s'affiche dès que le montant est non nul.

## Architecture

### `bulletin_view.py` — la vue

Nouveau module `backend/app/modules/payroll/documents/bulletin_view.py`, une fonction pure :

```python
def construire_vue_bulletin(bulletin: dict) -> dict
```

Elle prend le `bulletin_final` existant et rend les boîtes du gabarit : `bandeau`, `compteurs`, `salarie`, `identite`, `lignes` (le corps, à plat, avec un type par ligne), `lateral`, `pied`. C'est là que vivent :

- les replis (ancienneté absente, civilité absente, compteur vide)
- l'agrégation des notes de frais en une ligne
- l'éclatement qualif/classif/coeff
- le calcul de la mention « évolution de la rémunération »
- le formatage du NIR par blocs

Elle est testable sans rendu PDF, ce qui est l'essentiel de la couverture.

### Template

`template_bulletin.html` réécrit, sans logique : il parcourt les boîtes de la vue. Mise en page A4 portrait via `@page`, corps en table, colonne latérale en cellule de droite à largeur fixe. `thead` répété si le tableau déborde sur une deuxième page ; aucun bloc coupé en son milieu (`page-break-inside: avoid` sur les boîtes).

Les quatre appelants (`payslip_run_heures`, `payslip_run_forfait`, `payslip_editor`, `simulated_payslip_generator`) passent par la vue avant le rendu ; aucun autre changement chez eux.

### Données à faire remonter

Additif uniquement, aucune valeur calculée ne change :

- `payslip_generator.py` et `payslip_generator_forfait.py` : ajouter `matricule`, `sexe`, `salary_payment_method` au bloc `salarie` du contrat, et `adresse` côté forfait (elle n'y est pas, contrairement au générateur heures) ; `classification_conventionnelle` brute en plus de la chaîne formatée.
- `creer_bulletin_final` : exposer `smic_horaire` et `pss_mensuel` dans le bulletin (aujourd'hui connus du contexte mais absents du document).

### Aperçu RH

Nouvel endpoint `POST /payslips/{payslip_id}/preview` : reçoit les données de bulletin éditées, renvoie le rendu du même template. La page [PayslipEdit.tsx](../../../frontend/src/pages/rh/PayslipEdit.tsx) affiche ce rendu dans une iframe isolée, rafraîchie à la demande (bouton) plutôt qu'à chaque frappe.

[PreviewPanel.tsx](../../../frontend/src/components/payslip-edit/PreviewPanel.tsx) (460 lignes qui réimplémentent la mise en page en React) est supprimé : c'est une duplication qui divergerait dès la première retouche du gabarit.

L'endpoint ne persiste rien et rend uniquement à partir des données reçues, sous le même contrôle d'accès que l'édition du bulletin.

## Tests

- Unitaires sur `construire_vue_bulletin` : mapping des rubriques vers les codes Q, repli d'ancienneté, agrégation des notes de frais, compteurs absents, mention « évolution de la rémunération » (le cas CARTOL de juin comme valeur attendue).
- Rendu : le HTML produit contient les zones attendues, dans l'ordre attendu.
- `test_bulletin_officiel.py` existant : les assertions de rendu (montant net social, solde de congés) sont réécrites sur le nouveau gabarit — le contenu reste présent, sa forme change.
- Endpoint d'aperçu : test d'intégration sur le contrôle d'accès et le rendu.

## Hors périmètre

- Aucune modification du moteur de calcul, donc aucun impact sur les backtests, qui comparent des données et non nos PDF.
- Aucune régénération des bulletins déjà émis : les PDF du bucket `payslips` restent tels quels. Un bulletin ancien réédité ressortira au nouveau format, ce qui est acceptable.
- Le solde de tout compte, l'attestation employeur et les autres documents gardent leur mise en page.
