# D3.2 — La DSN d'un mois à deux contrats

Suite de [D3.1](2026-10-31-deux-contrats-meme-mois-design.md). Un CDD finit le
10/11, un nouveau contrat commence le 17/11 : novembre a deux bulletins, un par
contrat. Jusqu'ici, la DSN de ce mois était refusée en nommant le salarié. Elle
déclare désormais les deux.

## Ce que dit la norme

Sources : cahier technique DSN 2026.1 (`docs/audit-maji-2026/sources/dsn-cahier-technique-2026.1.txt`).

- **Arborescence** (§ 8, p. 117-118). Sous l'individu (30), on trouve d'abord
  les contrats (40), chacun suivi de ses arrêts (60), de sa fin (62), de ses
  suspensions (65), de ses affiliations (70) et de sa retraite complémentaire
  (71). Viennent ensuite les versements (50), chacun suivi de ses blocs 51 à 58
  et 78 à 81, puis les anciennetés (86). Un bloc se rattache au dernier bloc
  parent qui le précède (p. 76).
- **Numéro du contrat** : il doit être unique pour un individu dans la
  déclaration (40.009, CCH-12). Chaque contrat a au moins une rémunération qui
  le cite (40.009 CCH-13, 51.010 CCH-11).
- **Numéro de versement** : il est obligatoire et distinct dès qu'il y a deux
  versements (50.003, CCH-11 et CCH-12).
- **Base assujettie** : avec plusieurs contrats, elle porte le numéro de son
  contrat (78.006). Une base 31 cite une affiliation d'un contrat que le même
  versement rémunère (78.005, CCH-12).
- **Identifiant technique d'affiliation** : il est unique pour un salarié,
  tous contrats confondus (70.012, CCH-11). Il est interne au message.
- **Fin prévisionnelle** : elle doit être postérieure ou égale au début du
  contrat (40.010, CCH-11).
- **Pratique de Quadra**, lue sur 182 DSN de cabinet :
  - aucun salarié n'y a deux contrats dans le même mois ;
  - les contrats successifs d'un salarié portent les numéros 00000, 00001,
    00002…

## Décisions

1. **Un versement par bulletin.**
   - Le bulletin de l'ancien contrat est le versement 01, celui du nouveau le
     versement 02.
   - Chacun porte ses propres montants : net fiscal, prélèvement à la source,
     net versé, rémunérations (51.010 = son contrat), bases (78.006 = son
     contrat), net social (58).
   - Pourquoi : chaque bulletin a déjà son PAS et son net payé. Fusionner les
     deux obligerait à recalculer des montants que les bulletins portent déjà.
   - La date de versement reste la fin du mois pour les deux, comme
     aujourd'hui.
2. **Ordre d'écriture.** L'individu (30), puis chaque contrat (40) suivi de ses
   blocs, puis chaque versement (50) suivi de ses blocs, puis chaque ancienneté
   (86). Avec un seul contrat, le fichier ne change pas d'un octet.
3. **Numéro du nouveau contrat.**
   - « Nouveau contrat » pose le numéro suivant sur la fiche :
     `classification_conventionnelle.numero_contrat_dsn`, par exemple 00000
     devient 00001.
   - La fiche rangée garde l'ancienne classification, donc l'ancien numéro.
   - L'ancien contrat déclare ainsi son dernier mois sous son numéro, et le
     nouveau garde le sien les mois suivants.
   - Si deux numéros sont égaux (contrat rangé avant ce changement), la DSN
     refuse le mois en nommant le salarié.
4. **Reprise DSN propre au contrat.**
   - Ce qui est concerné : `dsn_reprise.date_fin_contrat`,
     `dsn_reprise.motif_recours` et `classification.motif_recours`. Ces champs
     décrivaient le contrat rangé.
   - « Nouveau contrat » efface la date de fin reprise : la nouvelle date est
     sur la fiche.
   - Il garde le motif de recours si l'ancien et le nouveau contrat sont deux
     CDD (des CDD successifs pour le même besoin, saisonnier par exemple), et
     l'efface sinon. Le motif se corrige sur la fiche (« Motif de recours du
     CDD »).
   - En défense, la DSN ignore une date de fin reprise antérieure au début du
     contrat (CCH-11).
5. **Événements.**
   - La sortie du mois (bloc 62) va au contrat dans les dates duquel elle
     tombe.
   - Chaque contrat déclare les arrêts qui touchent ses dates.
   - Le repli du SMIC de réduction générale vaut seulement pour le contrat de
     la fiche. Le bulletin de l'ancien contrat porte son SMIC, puisqu'il est
     calculé par le moteur actuel. S'il manque, c'est l'avertissement
     existant.
6. **Affiliations (70).**
   - Chaque contrat déclare les siennes.
   - Les identifiants techniques de l'ancien contrat sont décalés après ceux
     du nouveau, et les bases 31 de son versement citent les identifiants
     décalés.
7. **Contrôles avant génération.**
   - Le refus nommé de D3.1 est retiré.
   - Restent bloquants, toujours en nommant le salarié :
     - les deux contrats portent le même numéro ;
     - la fiche de l'ancien contrat n'a pas été rangée.
8. **Aperçu.** Une ligne par bulletin. `nombre_contrats` compte les deux et les
   totaux additionnent les deux.
9. **Ancien contrat seul.** Si le bulletin du nouveau contrat n'est pas encore
   généré, la DSN déclare l'ancien contrat seul, sur sa fiche rangée.

## Hors champ

- **Signalements d'arrêt ou de fin faits après « Nouveau contrat » pour
  l'ancien contrat.** Ils lisent la fiche, c'est-à-dire le nouveau contrat.
  C'est une limite de D4, inchangée.
- **Import d'une DSN à deux contrats.** Le lecteur range les versements sous le
  dernier contrat. C'est sans effet sur l'export et sur le contrôle relu après
  génération.
- **Date de versement réelle du solde de tout compte.** Elle n'est pas connue :
  c'est la fin de mois, comme pour toutes les sorties.

## Vérification

- Tests unitaires : l'écriture (ordre, un contrat inchangé), la fusion
  (numéros, 78.006, affiliations), la répartition des événements, la collecte
  des deux bulletins et le numéro suivant posé par « Nouveau contrat ».
- DSN-VAL sur un fichier fabriqué à deux contrats, à partir d'un jeu de
  conformité : aucun rejet propre aux deux contrats.

## Découpage

1. **Écriture.** `writer.write_individu` écrit les contrats, puis les
   versements, puis les anciennetés.
2. **Fusion.** `dsn_export/domain/deux_contrats.py` :
   - `fusionner(ancien, nouveau)` : versements 01 et 02, 78.006, affiliations
     décalées, refus si les numéros sont égaux ;
   - `evenements_du_contrat(evenements, debut, fin, fiche)`.
3. **Constructeur.** `build_parsed_dsn_from_payroll` construit le contrat
   précédent d'une ligne (`contrat_precedent`) et fusionne. `numero_du_contrat`
   est partagé avec les signalements. La date de fin reprise est ignorée si elle
   précède le début.
4. **Collecte et contrôles.**
   - `get_dsn_employees_data` : le bulletin à clé, sa fiche rangée, la
     répartition des événements et des totaux.
   - `check_dsn_data` : numéros égaux et fiche absente.
   - `preview_dsn` : une ligne par bulletin.
5. **Nouveau contrat.** Le numéro suivant, l'ancienne classification rangée, la
   reprise propre au contrat effacée.
6. **DSN-VAL** sur un cas fabriqué, puis mise à jour de la mémoire et de la
   feuille de route.
