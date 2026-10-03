# Nouveau contrat — réembauche, CDD successifs, CDD puis CDI

Date : 03/10/2026. Statut : conception, codée sur `feat/nouveau-contrat` (non poussée, non déployée).

## 1. Pourquoi

Une personne = une fiche = un contrat. Quand un salarié parti revient, ou enchaîne un nouveau contrat, rien à l'écran ne permet de le dire : la fiche reste « partie » et la paie refuse ses mois.

Cas réel : la salariée revenue de Comitech. CDD du 19/01/2026 au 31/05/2026 (départ archivé), revenue le 01/09/2026. EYWAI refuse son bulletin de septembre : « le collaborateur n'était plus présent dans l'entreprise (sortie le 31/05/2026) ». Quadra l'a payée en septembre, en CDD (contribution de 1 % des CDD sur son bulletin), entrée le 01/09/2026, brut 2 365,33, net 1 884,45.

Gaëlle a demandé le 02/10 : plusieurs CDD, successifs ou qui reprennent, une ancienneté calculée intelligemment, le suivi des contrats sur la fiche, le PDF de chaque contrat. Elle doit pouvoir tout faire seule.

## 2. Deux gestes, un bouton

Le bouton « Nouveau contrat » est dans la carte « Contrats » de la fiche. L'écran demande d'abord au serveur ce qui est possible (`GET /api/employees/{id}/new-contract`), puis propose l'un des deux gestes.

| Situation de la fiche | Geste proposé | Ce que c'est en droit |
|---|---|---|
| Départ clôturé (statut parti, sorti ou inactif) | **Nouveau contrat** : un contrat qui commence après la fin du précédent | Réembauche, CDD successifs, CDI après un CDD et une interruption |
| CDD en cours (actif), sans départ créé | **Suite en CDI** : le CDI commence le lendemain de la fin du CDD | Poursuite après l'échéance (L1243-11) |
| Départ créé mais pas clôturé (en sortie) | Rien : « Clôturez d'abord le départ du JJ/MM/AAAA (Départs), puis revenez ici. » | — |
| CDI en cours, ou CDD sans date de fin | Rien : « Le contrat en cours n'a pas de fin. Un nouveau contrat suit un départ clôturé ou la fin d'un CDD. » | — |

Renouveler un CDD (même contrat, nouvelle échéance, L1243-13) n'est pas un nouveau contrat : on change la date de fin dans « Modifier la fiche ». Le BOSS traite d'ailleurs le CDD renouvelé comme un seul calcul de réduction (§ 1080).

Un CDD suivi d'un autre CDD, ou d'un contrat d'apprentissage, sans interruption, passe par le départ : le premier CDD se termine (indemnité de fin de contrat, congés, certificat, attestation France Travail), puis « Nouveau contrat ».

## 3. Parcours à l'écran

**Nouveau contrat** (départ clôturé). Le dialogue rappelle le contrat précédent : « Contrat précédent : CDD du 19/01/2026 au 31/05/2026 ». Champs, préremplis depuis la fiche :

- Date de début : obligatoire, après la fin du précédent, et dans un mois postérieur (voir § 5) ;
- Type : CDI, CDD, Apprentissage, Contrat de professionnalisation ;
- Date de fin : obligatoire pour un CDD, facultative pour l'alternance, absente pour un CDI ;
- Durée hebdomadaire, salaire de base mensuel, poste ;
- Ancienneté : case « Reprendre l'ancienneté des contrats précédents » (décochée), avec la date d'ancienneté qui en résulte affichée avant validation ;
- Mois d'ancienneté antérieure (carrière ailleurs, `prior_service_months`) : affiché et modifiable, avec la phrase « Ne comptez pas ici les contrats précédents dans l'entreprise : cochez plutôt la case ci-dessus ».

**Suite en CDI** (CDD en cours). Date de début fixée au lendemain de la fin du CDD, non modifiable. Type CDI. Salaire, durée et poste préremplis. L'ancienneté n'est pas demandée : elle court depuis le début du CDD (L1243-11).

**Après validation.**
- Succès : « Nouveau contrat enregistré : CDD du 01/09/2026 au 18/12/2026. Le contrat précédent est rangé dans la carte Contrats. Le bulletin de 09/2026 peut être généré. » La fiche, la carte et la liste de paie sont relues.
- Refus : le message du serveur, dans le dialogue, qui dit quoi corriger et où. Rien n'est écrit (une seule transaction, § 4).
- Avertissement de la suite en CDI : si le bulletin du dernier mois du CDD existe déjà, « Le bulletin de MM/AAAA a été calculé en fin de CDD (indemnité de fin de contrat, congés) : régénérez-le. »

## 4. Ce qui est écrit

Une fonction Postgres, `public.nouveau_contrat`, écrit tout en une transaction, sous verrou de la fiche. Migration `supabase/migrations/20261003090000_nouveau_contrat.sql`, idempotente, non appliquée.

1. **Le contrat précédent est rangé** dans `employee_contract_periods` : type, début (`date_debut_execution`, à défaut `hire_date`), fin (dernier jour du départ archivé le plus récent, à défaut `contract_end_date`). Nouvelles colonnes, toutes facultatives : poste, durée hebdomadaire, salaire, départ lié (`exit_id`), origine (`nouveau_contrat` ou `suite_cdi`), et `fiche_avant` (la fiche telle qu'elle était, pour pouvoir annuler en phase 2).
2. **La fiche porte le nouveau contrat** :
   - nouveau contrat : `hire_date` = date de début, `date_debut_execution` et `date_conclusion_contrat` vidées, type, fin, durée, temps partiel, poste, statut `actif`, date d'ancienneté (§ 6), mois d'ancienneté antérieure ;
   - suite en CDI : type CDI, fin vidée, durée, temps partiel, poste. `hire_date` et la date d'ancienneté ne bougent pas : c'est le même contrat qui continue.
3. **Le salaire** : une ligne `salary_history` datée du début, si le montant change. Le serveur synchronise ensuite le salaire de la fiche, comme l'onglet Augmentations.
4. **Trace d'audit** `employee.contract.new`, avec le geste, les dates, le type et l'ancienneté retenue.

**Intacts** : le départ archivé et ses documents, les bulletins, les cumuls, les absences, le PDF du contrat déposé.

## 5. Mois payables

**Règle.** Un mois est payable s'il chevauche le contrat en cours, de la date de début de la fiche à sa date de fin. Un mois entre deux contrats ne l'est pas. Un mois couvert seulement par un contrat rangé ne l'est plus non plus : la fiche décrit désormais le nouveau contrat, et le recalculer donnerait un bulletin faux (nouveau salaire, nouvelle date d'entrée, pas d'indemnité de fin).

Deux contrats dans le même mois sont refusés en phase 1 : EYWAI ne fait qu'un bulletin par salarié et par mois. D'où la règle de la date de début : un mois après celui de la fin du contrat précédent. La suite en CDI n'est pas concernée, puisque c'est le même contrat.

**Garde-fou à la création.** Le dernier mois du contrat précédent doit avoir son bulletin (calculé ou importé), sauf s'il est antérieur à la bascule de reprise. Sinon : « Générez d'abord le bulletin de MM/AAAA, dernier mois du contrat précédent : il ne pourra plus l'être ensuite. »

**Messages** (serveur dans `salarie_generable`, écran dans `employmentPeriod.ts`, mêmes phrases) :
- entre deux contrats : « Aucun contrat ne couvre 07/2026 : le contrat précédent s'est terminé le 31/05/2026, le suivant commence le 01/09/2026. » ;
- contrat rangé : « 05/2026 relève du contrat précédent (CDD du 19/01/2026 au 31/05/2026), clos par le nouveau contrat du 01/09/2026 : son bulletin ne se recalcule plus. ».

Le générateur garde sa propre garde, sur la fiche seule : il ne calcule jamais un mois hors du contrat en cours.

## 6. Ancienneté

| Cas | Règle | Source |
|---|---|---|
| CDD poursuivi en CDI sans interruption | L'ancienneté court depuis le début du CDD. Suite en CDI : la fiche garde sa date. | C. trav. L1243-11 : « Le salarié conserve l'ancienneté qu'il avait acquise au terme du contrat de travail à durée déterminée. » |
| Réembauche après une interruption | L'ancienneté repart du nouveau contrat. La date d'ancienneté est posée au début du nouveau contrat, explicitement, pour que le trou ne se recolle pas tout seul. | Aucun texte ne cumule les contrats séparés. La CCN de la plasturgie, pour l'indemnité de licenciement : « la durée des contrats antérieurs avec la même entreprise n'est pas prise en compte, hormis : – la durée du contrat de travail à durée déterminée avec la même entreprise lorsque la relation de travail s'est poursuivie au terme de ce contrat » |
| La RH coche « Reprendre l'ancienneté des contrats précédents » | Date d'ancienneté = date de début − ancienneté acquise à la fin du contrat précédent, en jours (de l'ancienne date d'ancienneté à la dernière fin). L'écran montre la date avant validation. | Choix de la RH : accord, usage, contrat. EYWAI ne devine pas. |
| Saisonnier | Les contrats successifs ou non se cumulent pour les 3 mois des jours fériés. Non traité en phase 1 : la RH coche la case. | C. trav. L3133-3, al. 2 |

`prior_service_months` (carrière antérieure à l'entrée) reste un champ séparé, que le moteur ajoute à l'ancienneté des jours fériés. Il est faux sur 221 fiches (il porte l'ancienneté totale). C'est le cas de la salariée revenue : 4 mois, soit exactement son CDD. Le dialogue le montre et le laisse corriger. La réparation des 221 fiches reste une décision d'Alexandre.

La période d'essai n'est pas recalculée (L1243-11, al. 3 : la durée du CDD est déduite de l'essai du CDI).

## 7. Cumuls et congés

| Compteur | Ce que dit la loi | Ce que fait le moteur | Ce qu'on garde |
|---|---|---|---|
| Réduction générale (brut, heures, réduction appliquée) | Calcul « pour chaque contrat de travail » (CSS L241-13, III) ; CDD : « déterminé pour chaque contrat » (D241-7, V) ; BOSS § 1070. CDD renouvelé ou transformé en CDI : un seul calcul sur la période, dans l'année civile (BOSS § 1080). | Lit les cumuls du mois d'avant. | Nouveau contrat : on repart de zéro. Suite en CDI : on continue. |
| Indemnité de fin de contrat (`brut_total`) | 10 % de la rémunération totale brute du contrat ; pas due si un CDI suit (L1243-8). | Base = `brut_total` cumulé. | Zéro au nouveau contrat. La suite en CDI n'est plus un CDD : pas d'indemnité. |
| Congés payés et base du dixième | ICCP à la fin de chaque CDD, sauf si un CDI suit (L1242-16, dernier alinéa). | Acquisition depuis `hire_date` ; base `brut_reference_n_1`. | Nouveau contrat : compteurs à zéro (l'ancien contrat a payé ses congés). Suite en CDI : ils continuent. |
| Agirc-Arrco (tranches), plafond | Régularisation sur la période d'emploi. | Cumuls dédiés. | Zéro au nouveau contrat. Sans effet sous le plafond. |
| Net imposable, impôt, HS exonérées et plafond de 7 500 € | Année civile, par contribuable (CGI art. 81 quater). | Cumuls d'année civile. | Zéro au nouveau contrat en phase 1 (voir § 9). |

**Règle moteur** : au premier mois d'un contrat (date d'entrée de la fiche dans le mois), le bulletin ne reprend pas les cumuls du mois précédent. Ils appartiennent à un autre contrat ou n'existent pas. Le même patron que la garde de janvier, dans les deux générateurs (heures et forfait), en vraie génération comme en bac à sable. Pour une première embauche, rien ne change : le mois d'avant n'a pas de cumul.

**Vérifié sur le cas réel.** Quadra a recalculé la réduction de septembre sur le seul nouveau contrat, en continuant d'imprimer les cumuls de l'année : cumul brut 12 563,66, dont 10 198,33 du CDD. Sa réduction, 636,98 €, est exactement celle de la formule appliquée au mois seul : brut 2 365,33, SMIC figé 12,02 × 169 h. EYWAI, cumuls à zéro, trouve la même chose (§ 8 du compte rendu).

## 8. Hors périmètre, phase 2

- **PDF de chaque contrat.** Aujourd'hui un seul fichier par salarié (`contracts/{société}/{salarié}/contrat.pdf`) : déposer le nouveau remplace l'ancien. Il faut un fichier par contrat rangé, et un lien depuis la carte. Non trivial (stockage, droits, espace salarié), donc phase 2.
- **Deux contrats dans le même mois** (fin le 15, reprise le 20) : deux bulletins le même mois. Refusé en phase 1, avec la raison.
- **Annuler un nouveau contrat** tant qu'aucun bulletin n'a été calculé dessus : la fiche d'avant est gardée (`fiche_avant`), la fonction d'annulation reste à écrire. En attendant : « Modifier la fiche » et « Retirer » dans la carte.
- **DSN** : nouveau numéro de contrat (S21.G00.40.009), et bloc de changement (S21.G00.41) pour la suite en CDI. Non traité.
- **Délai de carence entre deux CDD** (L1244-3 et L1244-4) : non contrôlé.
- **Mois de la suite en CDI en cours de mois** : le bulletin est calculé en CDI sur tout le mois, donc sans la contribution de 1 % des CDD sur les jours de CDD. L'écran le dit.

## 9. Décisions pour Alexandre

1. Les cumuls d'année civile (net imposable, HS exonérées et plafond de 7 500 €) doivent-ils suivre la personne d'un contrat à l'autre dans la même année, comme les imprime Quadra ? Phase 1 : non. Le plafond n'est pas atteignable chez Colorplast et Comitech.
2. Les 221 fiches dont `prior_service_months` porte l'ancienneté totale (dont la salariée revenue, 4 mois).
3. Le type de son contrat de septembre (CDD d'après le bulletin Quadra, date de fin inconnue) et la prime de poste difficile : sa fiche n'est pas dans la règle automatique.
4. Son départ du 31/05 est enregistré « licenciement » alors que la DSN dit fin de CDD (motif 031).

## Sources

- Code du travail L1243-11 : https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006901222
- Code du travail L1243-8 : https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006901219
- Code du travail L1243-10 : https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006901221
- Code du travail L1242-16 : https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006901210
- Code du travail L3133-3 : https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000033020893
- Code de la sécurité sociale L241-13, III : https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000053280526
- Code de la sécurité sociale D241-7, V : https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000054252241/2026-03-01
- BOSS, Allègements généraux, §§ 710, 1070, 1080, 1090 : https://boss.gouv.fr/portail/accueil/exonerations/allegements-generaux.html. Copies datées dans `docs/reference/reduction-generale-2026/`.
- CCN de la plasturgie (IDCC 292), indemnité de licenciement, contrats antérieurs : https://www.legifrance.gouv.fr/conv_coll/id/KALITEXT000005682080/?idConteneur=KALICONT000005635856
- Code du travail L1243-13 (renouvellement) et L1244-3 (carence) : Légifrance, cités pour mémoire.
- CGI art. 81 quater (plafond annuel des heures supplémentaires exonérées) : Légifrance, cité pour mémoire.
