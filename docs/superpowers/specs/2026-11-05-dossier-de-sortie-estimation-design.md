# Dossier de sortie : une estimation qui suit la loi (05/11/2026)

Cas d'origine : fin de CDD d'un salarié de MAJI (contrat du 29/06/2026 au
30/09/2026, forfait 216 jours, 3 000 €), payée par Quadra en septembre, puis
dossier recréé dans Martine le 04/11 avec le motif « fin de période d'essai ».
Pas de brainstorming (consigne d'Alexandre) : les décisions ci-dessous sont
tranchées selon la recommandation, chaque règle a sa source ouverte le 05/11.

## Sources ouvertes le 05/11

- Code du travail, via code.travail.gouv.fr (curl, pages 200) :
  - L1243-8 : « Cette indemnité est égale à 10 % de la rémunération totale brute
    versée au salarié. Elle s'ajoute à la rémunération totale brute due au
    salarié. »
  - L1243-10 : l'indemnité n'est pas due 1° contrats saisonniers et d'usage,
    2° jeunes pendant les vacances, 3° refus d'un CDI équivalent, 4° rupture
    anticipée à l'initiative du salarié, pour faute grave ou force majeure.
  - L1242-16 : indemnité compensatrice de congés « au titre du travail
    effectivement accompli durant ce contrat […] ne peut être inférieur au
    dixième de la rémunération totale brute perçue par le salarié pendant la
    durée de son contrat ».
  - L3141-24 : I. dixième de la rémunération brute totale « perçue au cours de
    la période de référence » ; II. pas moins que le maintien.
  - L3141-28 : indemnité compensatrice pour la fraction de congé non prise à la
    rupture, déterminée d'après L3141-24 à L3141-27.
  - L3141-3 / L3141-4 : 2,5 jours ouvrables par mois de travail effectif ;
    4 semaines ou 24 jours valent un mois.
- service-public.gouv.fr F40 « Fin d'un contrat à durée déterminée » (curl,
  200) : « L'indemnité de fin de contrat est égale au minimum à 10 % de la
  rémunération brute totale versée durant votre contrat. »
- Fiche service-public « Indemnité compensatrice de congés payés » (mise à jour
  le 23/01/2026, lue sur code.travail.gouv.fr, onglet CDD) : « égale au 1/10e
  de la rémunération brute totale perçue au cours de la durée du contrat »,
  exemple : salaire 18 300 €, indemnité de fin de contrat 1 830 €, congés
  (18 300 + 1 830)/10 = 2 013 €. La prime entre donc dans la base des congés.
- Fiche service-public « Avez-vous le droit à des congés payés pendant votre
  CDD ? » (mise à jour le 10/04/2026) : un mois incomplet acquiert au prorata
  des jours travaillés.
- Bulletin Quadra de septembre (data/maji/bulletins/2026-09) : après le solde,
  compteur « CP N acquis 0,00 / solde 0,00 » ; prime 13 090,90 × 10 % =
  1 309,09 ; congés 1 058,18 ; repos forfait 3 j 415,32 ; brut 5 782,59.
- DSN de septembre de Quadra : nature 02, fin au 30/09, motif 031 (cahier
  technique 2026.1, S21.G00.62.002).

Legifrance n'a pas été ouvert : code.travail.gouv.fr reproduit le texte en
vigueur avec sa date de mise à jour.

## Ce qui était faux, et pourquoi

### Défaut 1 — le repli invente des mois

`lire_bruts_periode_reference` parcourt toute la période de congés (juin N à
mai N+1) sans s'arrêter à la sortie ni partir de l'entrée, et remplit chaque
mois sans bulletin avec le salaire du contrat. Au 30/06, on lisait donc onze
mois inventés (« Bulletin 10/2026 … 05/2027 absent — salaire contractuel
utilisé » aujourd'hui).

« Juin absent » : relu le 05/11, le bulletin de juin est trouvé (272,73 €). Le
seul chemin qui dit « absent » d'un bulletin existant est une lecture qui
échoue : l'exception était journalisée, puis le mois était rempli au salaire
du contrat avec le même texte que s'il manquait. On ne peut plus prouver
laquelle des deux a joué le jour du constat ; le texte distinguera désormais
les deux cas.

### Défaut 2 — 1,95 jour et 4 205,53 €

Quatre causes, mesurées en lecture seule :

1. **La reprise est lue après le solde.** La reprise de MAJI est datée du
   30/09 (bulletins de Quadra jusqu'en septembre). Son solde d'ouverture vient
   du bulletin de septembre, *après* le solde de tout compte : Quadra a payé
   les congés et son compteur affiche 0. Un départ daté au plus tard de la
   reprise ne peut donc pas lire ses droits dans ce compteur.
2. **Le prorata du mois d'entrée change entre l'écriture et la lecture.**
   `apply_cp_solde_import` calcule l'acquis théorique avec un ajustement vide,
   donc mois d'entrée au prorata (6,38 j). Le compteur relu porte une reprise
   datée après l'entrée, donc mois d'entrée entier (8,33 j). Ouverture
   0 − 6,38 = −6,38, relue 8,33 − 6,38 = 1,95 j au lieu de 0. Le recalage
   (`_recaler_sur_le_solde_affiche`) devait rattraper l'écart ; il n'a rien
   écrit pour ce salarié (`created_at` = `updated_at`), sans doute parce que la
   fiche, ce jour-là, situait la sortie avant la reprise (compteur vide, recalage
   sauté). Relevé des 276 reprises datées : 92 ont ce décalage, 91 recalées,
   seul ce salarié ne l'est pas.
3. **La base de la période en cours ignore juin-août.** Le dossier lit le
   « brut avant le mois » dans les cumuls d'août ; juillet et août, repris de
   Quadra, n'ont pas de cumuls : 0 €. 4 205,53 = 3 000 (septembre estimé) +
   1 205,53 (prime).
4. **La prime estimée est fausse.** 1 205,53 = 10 % de 12 055,32, total qui
   inclut le bulletin de septembre de Quadra, lequel porte déjà la prime, les
   congés et le repos du forfait.

**Le bulletin de sortie lit-il les mêmes compteurs ?** Oui :
`payslip_run_heures.cp_fin_de_contrat` (heures et forfait jours) appelle
`get_absence_balances_for_payslip` et `periodes_depuis_compteurs`. Les causes 1
et 3 ne le touchent pas : le bulletin ne se calcule qu'après la bascule, sur des
cumuls écrits chaque mois. La cause 2 ne touche que ce salarié, parti. En
cherchant, un défaut du bulletin est apparu :

5. **Départ dans le premier mois d'une période (juin).** Le run lit les cumuls
   du mois précédent (mai). Leur `brut_reference_n_1` est le total de la
   période *close* : il était ajouté à la période en cours, et la « période
   précédente » remontait d'un an. Reproduit en mémoire : départ en juin,
   période 2026-2027 de 1,04 j avec 36 000 € de base, période 2025-2026 avec le
   brut de 2024-2025. Une vraie paie au prochain départ de juin.

### Défaut 3 — le motif à choisir

Depuis la page Départs, le formulaire part sur « Démission » quel que soit le
contrat. Le bandeau de la Paie propose déjà « Fin de CDD » ; la page Départs non.

## Décisions

- **R1 — Le repli s'arrête au contrat.** Les mois lus vont de
  max(début de période, entrée) à min(fin de période, sortie). Rien après la
  sortie, rien avant l'entrée (L3141-24 I : rémunération *perçue* au cours de
  la période ; L1242-16 : *pendant la durée de son contrat*). Le mois de sortie
  sans bulletin est estimé au salaire au prorata des jours sous contrat. Une
  lecture qui échoue est dite « illisible », pas « absent ».
- **R2 — Base de la prime : la rémunération du contrat, mois de sortie
  estimé.** Les bulletins des mois du contrat avant le mois de sortie, plus le
  salaire estimé du mois de sortie ; jamais le bulletin du mois de sortie, qui
  porte déjà les indemnités de départ. Un mois sans bulletin vaut le salaire du
  contrat et le dossier le dit (L1243-8, F40 : « versée durant votre
  contrat »). Les mois d'un contrat antérieur ne comptent pas.
- **R3 — La prime n'entre dans la base des congés que si elle est versée** :
  fin de CDD ou de mission, prime non déclarée « non due » (L1242-16 :
  rémunération *perçue* ; fiche service-public : (18 300 + 1 830)/10).
- **R4 — Départ au premier mois de la période (bulletin et dossier).** Quand
  les cumuls du mois précédent appartiennent à la période close, la période en
  cours part de 0 et la période précédente prend ce cumul (L3141-24 I).
- **R5 — Brut avant le mois sans cumuls (dossier).** La somme des bulletins de
  la période en cours, depuis le début de la période ou l'entrée, jusqu'au mois
  d'avant la sortie.
- **R6 — Départ au plus tard à la date d'une reprise de congés (dossier).**
  Les droits se recomptent depuis l'entrée sans cette reprise, et le dossier
  le dit : « Départ payé par l'ancien logiciel : les soldes repris le JJ/MM sont
  ceux d'après son solde de tout compte ; Martine recompte les congés depuis
  l'entrée. » Les congés pris avant la reprise et absents du planning ne sont
  pas connus : la phrase le précise.
- **R7 — Reprise : un seul prorata.** `apply_cp_solde_import` calcule l'acquis
  théorique avec la règle de lecture (ajustement portant la date de
  référence). Le recalage reste pour les congés d'ancienneté et le
  fractionnement.
- **R8 — Fin de CDD proposée d'office.** Dans le formulaire de départ, un
  salarié en CDD avec une date de fin : motif « Fin de CDD » et dernier jour à
  la fin du contrat, avec la phrase « Proposé par Martine : CDD qui finit le
  JJ/MM/AAAA. » La RH peut tout changer ; rien ne bloque. Un choix de la RH
  n'est jamais écrasé. Le motif 031 d'une DSN importée devient déjà
  « fin_cdd » (`dsn_absence_exit_mapping`) et la date de fin vient du bloc 62.

Hors périmètre, noté :
- Le repos du forfait non pris (3 j, 415,32 € chez Quadra) n'est pas estimé par
  le dossier. S'il est dû, il fait partie de la rémunération versée et entre
  dans les deux bases.
- La fiche porte une durée de 35 h alors que le contrat et Quadra disent
  forfait 216 jours (valeur d'un jour : 3 000 / 21,67 = 138,46).

## Chiffres de ce cas (dossier au 30/09, « Fin de CDD »)

| | Avant (code du 05/11) | Après | Quadra |
|---|---|---|---|
| Prime de fin de contrat | 1 205,53 | 927,27 (10 % de 9 272,73) | 1 309,09 (10 % de 13 090,90) |
| Jours de congés | 1,95 | 6,38 | — |
| Base des congés | 4 205,53 | 10 200,00 (9 272,73 + 927,27) | 10 581,82 |
| Congés retenus | 420,55 (dixième) | 1 020,00 (dixième ; maintien 883,37) | 1 058,18 |

Écart avec Quadra, point d'audit (ne rien toucher à ses données) : sa base de
prime ajoute janvier-février (818,18 + 3 000), payés sur un contrat antérieur
clos le 28/02. L1243-8 et F40 limitent la base à la rémunération versée durant
*ce* contrat : +381,82 € de prime, +38,18 € de congés par contrecoup.

## Données

Aucun bulletin n'est régénéré. Deux écritures attendent « lance » :
1. Le dossier dee94ca9 : motif « fin_cdd », recalcul par Martine.
2. La reprise de ce salarié : ouverture N −6,38 → −8,33 (solde 0 au 30/09,
   comme Quadra).
