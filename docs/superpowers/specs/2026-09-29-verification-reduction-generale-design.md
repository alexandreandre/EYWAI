# Vérification complète de la réduction générale (RGDU 2026) — conception du chantier

Date : 29/09/2026. Statut : conception validée par Alexandre, à planifier.

## 1. Pourquoi ce chantier

EYWAI calcule la réduction générale de cotisations patronales (RGDU 2026) :
- pour Colorplast et Comitech depuis septembre 2026, avec une bascule au 31/08 ;
- pour Mont-Blanc en parallèle de Quadra à partir d'octobre.

La réduction se régularise sur l'année civile. Chaque bulletin recalcule la réduction due depuis janvier, puis retire celle déjà appliquée. Toute différence de méthode sur les mois payés par Quadra ressort donc sur le premier bulletin EYWAI.

Constats de départ (29/09/2026) :
- **Colorplast, septembre à blanc.** Deux salariés reprennent 236 € et 216 € de réduction. En mars, Quadra a gardé dans le SMIC de référence environ 23 h d'absence payée par le maintien de salaire, sans les compter dans le « Cumul heures » imprimé. Notre ouverture reprend ce cumul imprimé.
- **Comitech, janvier.** Quadra n'a appliqué aucune RGDU en janvier : il a gardé les anciens taux réduits maladie et famille. Septembre rattraperait 6 927,35 € sur 13 salariés.
- **Forfait jours.** L'ouverture porte 0 h. Le moteur compte 7 h par jour travaillé, alors que Quadra compte 151,67 × 216 / 218 = 150,28 h par mois.
- **Code.** La lecture a relevé une vingtaine de zones à risque, présentées dans les questions ci-dessous. Exemples :
  - le brut cumulé n'est jamais remis à zéro en janvier, donc février 2027 sera faux ;
  - le SMIC figé n'existe qu'en base, sans version ni test ;
  - notre DSN recopie le SMIC retenu de Quadra au lieu de le calculer.

**Objectif.** Répondre à chaque question de la section 4, preuve à l'appui, et conclure pour chaque société : à partir de quand la réduction calculée par EYWAI est fiable, et quelles corrections il faut, chiffrées. Le chantier ne corrige rien lui-même : les corrections feront l'objet d'un plan séparé.

## 2. Règle de référence

Décidée par Alexandre le 29/09/2026.

- **Mois payés par Quadra** : Colorplast et Comitech de janvier à août 2026, Mont-Blanc jusqu'à sa bascule. Ce que Quadra a déclaré est définitif, et EYWAI s'y cale dans l'ouverture, même quand Quadra s'écarte de la loi. L'écart est documenté.
- **Mois payés par EYWAI** : la loi fait foi. Chaque divergence de méthode avec Quadra est documentée et présentée à Gaëlle.
- **Exception** : un écart de Quadra qui expose la société à un redressement est signalé à Alexandre, chiffré, et c'est lui qui décide. C'est le cas du cumul des taux réduits et de la RGDU en janvier chez Comitech.

## 3. Périmètre et données

| Société | Mois rejoués | Sources disponibles |
|---|---|---|
| Colorplast | 2026-01 à 2026-08 | Bulletins Quadra (PDF et extraits `md/`) ; DSN de janvier à juin (bloc S21.G00.79 « SMIC retenu », codes 018 et 106) ; pointages ; références de `colorplast_rejeu_test.py` ; filet |
| Comitech | 2026-01 à 2026-08 | Bulletins Quadra (août sans extrait `md/`) ; DSN de janvier à juin |
| Mont-Blanc | 2026-01 à 2026-07 | Bulletins Quadra et extraits ; DSN depuis 2025-09 |

Sont aussi utilisés :
- `docs/audit-maji-2026/donnees/rubriques.csv`, qui contient toutes les lignes Q802 ;
- `G-rgdu.csv` ;
- les lecteurs `backend/scripts/backtest/colorplast_lignes_quadra.py`, à étendre aux « Cumul jours » des forfaits.

Hors périmètre :
- la déduction forfaitaire patronale et la réduction salariale sur les heures supplémentaires, sauf quand elles se mêlent aux lignes de réduction ;
- les autres exonérations, sauf pour vérifier qu'elles ne coupent pas la réduction à tort (question A4).

## 4. Questions auxquelles le chantier répond

Pour chaque question, le rapport donne quatre éléments :
- la réponse : oui, non, ou un chiffre ;
- la preuve : le texte et les données ;
- le montant en jeu ;
- la correction proposée, avec le fichier visé et sa priorité.

### F — Formule et paramètres
- **F1.** Les paramètres 2026 sont-ils conformes au décret ? Tmin 0,02 ; Tdelta 0,3781 (moins de 50 salariés) ou 0,3821 ; P 1,75 ; sortie à 3 SMIC ; coefficient arrondi à 4 décimales. Il faut aussi réconcilier deux références : le décret 2025-887, cité par le code, et le décret 2025-1446, cité par le référentiel d'audit.
- **F2.** Le SMIC de référence reste-t-il figé à 12,02 € toute l'année 2026 (décret 2026-509 du 12/06/2026) ? Quelles tolérances pour les fins de contrat de juin ? En juin, Quadra a déclaré 12,31 € pour une partie des salariés : cet écart a-t-il été régularisé ensuite ?
- **F3.** Quel effectif fixe le Tdelta et le FNAL : l'effectif moyen annuel de l'année précédente (L130-1) ? Quelles valeurs retenir pour les trois sociétés ? La valeur fixe de `companies.effectif` suffit-elle ?
- **F4.** Quand deux contrats se suivent (CDD puis apprentissage), la réduction se calcule-t-elle par contrat ?

### H — Heures du SMIC de référence

Pour chaque cas : la loi, Quadra, EYWAI.

- **H1.** Mois complet : durée légale ou contractuelle, plus les heures supplémentaires et complémentaires au taux normal. D'après la DSN, Quadra retient le SMIC mensuel plus les heures supplémentaires × le SMIC horaire.
- **H2.** Congés payés pris.
- **H3.** Absence non payée (autorisée, injustifiée, sans solde) : quelle part des heures sort ? Quadra semble en garder environ 4 %. C'est la question Q3, restée ouverte auprès de Gaëlle.
- **H4.** Arrêt maladie ou accident du travail, selon le maintien : aucun, partiel ou total. Carence, subrogation, prévoyance.
- **H5.** Absences payées par l'employeur : événement familial, paternité avec maintien.
- **H6.** Jour férié chômé, payé ou non ; journée de solidarité.
- **H7.** Entrée ou sortie en cours de mois : comment le SMIC est-il proratisé ?
- **H8.** Temps partiel et heures complémentaires.
- **H9.** Forfait jours : faut-il retenir 151,67 × jours du forfait / 218 ? Cas du forfait réduit, et des jours d'absence du salarié au forfait.
- **H10.** Apprenti et contrat de professionnalisation ; stagiaire exclu.
- **H11.** Activité partielle.
- **H12.** Éléments du brut sans heures correspondantes : préavis non effectué, indemnité compensatrice de congés, pauses payées, heures de nuit.

### B — Brut retenu
- **B1.** Qu'est-ce qui entre dans le brut de la réduction ? Précarité, indemnité compensatrice de congés, indemnité de fin de mission, prime de partage de la valeur (exonérée ou soumise), participation, intéressement, avantages en nature, maintien, indemnités journalières, rappels.
- **B2.** Le cumul « Bruts » imprimé par Quadra est-il l'assiette de sa réduction ? Par exemple, la prime de partage de la valeur exonérée en fait-elle partie ?

### A — Calcul sur l'année
- **A1.** Le brut et les heures de la réduction sont-ils remis à zéro au 1er janvier ? Défaut connu : `brut_total` ne l'est jamais, donc février 2027 sera faux.
- **A2.** Que devient le cumul de réduction quand la ligne est absente (JEI, paramétrage inactif, brut nul) ? Le brut et les heures continuent de s'additionner, pas la réduction.
- **A3.** Régularisation progressive ou annuelle ; et à la sortie en cours d'année, régularisation au dernier bulletin.
- **A4.** Le JEI et les autres exonérations suppriment-ils la réduction à tort ?

### R — Reprise
- **R1.** Pour chaque salarié, l'ouverture au 31/08 redonne-t-elle la réduction cumulée de Quadra ? Le test : la formule appliquée au brut et aux heures repris doit égaler la somme des Q802 à 1 € près. Sinon, quelles heures faut-il reprendre ?
- **R2.** Janvier chez Comitech : faut-il suivre Quadra (réduction à partir du 01/02) ou régulariser ? Chiffrage final, et décision d'Alexandre.
- **R3.** Mont-Blanc : les mêmes contrôles avant sa bascule. Janvier y est sous-évalué, et 8 salariés n'ont pas eu de réduction en janvier.
- **R4.** Contrats successifs, et entrées après la bascule.

### D — DSN et comptabilité
- **D1.** Bloc S21.G00.79 (SMIC retenu) : EYWAI doit le calculer lui-même, alors qu'aujourd'hui il le recopie de Quadra.
- **D2.** Répartition entre les codes 018 et 106. Le code fige Tmax à 0,3980 et 0,4020, alors que le moteur retient 0,3981 et 0,4021. Quelle est la règle officielle de la part Agirc-Arrco ?
- **D3.** Écriture comptable : aujourd'hui, toute la réduction va à l'URSSAF.
- **D4.** Import DSN des cumuls de réduction : il stocke le montant du mois comme un cumul et lit de mauvais codes. À corriger ou à retirer.

### P — Paramètres et robustesse
- **P1.** `smic_reference_horaire` est-il versionné, daté et testé ?
- **P2.** `payroll_config` n'est pas daté : que donne un rejeu de 2026 lancé en 2027 ?
- **P3.** Collecte automatique des taux : risque d'écrire Tmax à la place de Tdelta ; bornes de contrôle.
- **P4.** Replis silencieux (année absente, SMIC de repli, effectif absent, maintien en échec) : lesquels doivent bloquer le calcul ?
- **P5.** Tests qui recopient la formule au lieu d'exécuter le code de production.

## 5. Méthode

### Étape 1 — Textes
- Récupérer en entier :
  - les fiches URSSAF sur la RGDU 2026 et la réduction générale (SMIC de référence, absences, forfait jours) ;
  - la rubrique du BOSS sur les allègements généraux ;
  - les articles L241-13 et D241-7 à D241-10 du Code de la sécurité sociale ;
  - le décret RGDU 2026 et le décret 2026-509 ;
  - les fiches net-entreprises sur le bloc 79 et la répartition 018 / 106.
- Le cahier technique DSN 2026.1 est déjà dans le dépôt.
- Rangement : `docs/reference/reduction-generale-2026/`, un fichier par texte, avec l'URL, la date de consultation et l'extrait intégral utile. Sources publiques uniquement.
- Sortie : un tableau « règle → texte → article », qui fonde toutes les réponses.

### Étape 2 — Calcul de référence
- Un script indépendant du moteur, écrit uniquement à partir des textes, dans `backend/scripts/verification_rgdu/` (hors de `app/`).
- Entrées : le brut du mois, les heures par nature (travail, heures supplémentaires, congés payés, chaque type d'absence, arrêt et part maintenue…) et les paramètres.
- Sorties : les heures de référence, le SMIC, le coefficient, la réduction cumulée et celle du mois, la répartition 018 / 106.
- Un cas de test par règle (H1 à H12, B1, A1 à A3), qui cite sa source. Ces tests tournent en CI avec les autres tests de scripts.

### Étape 3 — Rejeu à trois colonnes

Pour chaque salarié et chaque mois, trois colonnes :
- **Quadra** : la ligne Q802 du bulletin ; le SMIC retenu et les codes 018 / 106 de la DSN, de janvier à juin ; le cumul de brut et d'heures imprimé.
- **Loi** : le calcul de référence, appliqué aux éléments du bulletin Quadra (brut, heures, absences, maintien).
- **EYWAI** : le moteur en bac à sable, écritures piégées, sur les mêmes entrées. On passe par le rejeu existant (`colorplast_rejeu_test.py` et `colorplast_regulier_test.py`), étendu à Comitech et Mont-Blanc.

On compare, mois par mois :
- les heures de référence : celles de Quadra se déduisent du SMIC retenu en DSN, ou de sa réduction cumulée ;
- les montants.

Chaque écart de plus de 1 €, ou de plus de 0,5 h, reçoit un classement :
- `erreur_eywai` ;
- `erreur_quadra` ;
- `methode_legale_differente` ;
- `donnee_manquante` ;
- `arrondi`.

Chaque classement cite la règle de l'étape 1 et la ligne de données concernée.

Sortie : `data/_rapports/rgdu-2026/`, non versionné car il contient les vrais noms. Un tableau par société : salarié × mois × trois colonnes × classement.

### Étape 4 — Ouverture et septembre
- **Colorplast et Comitech :**
  - contrôle R1 sur chaque ouverture ;
  - septembre à blanc, deux fois : avec l'ouverture actuelle, puis avec une ouverture corrigée (heures de Quadra) ;
  - rattrapage chiffré par salarié.
- **Mont-Blanc :** les mêmes contrôles, sur une ouverture simulée au 31/07, sans aucune écriture.

### Étape 5 — Réponses et conclusion
- **Rapports.** Le rapport complet va dans `data/_rapports/rgdu-2026/rapport.md`, avec les vrais noms. Un résumé pseudonymisé va dans `docs/comptes-rendus/verification-reduction-generale-2026.md`.
- **Chaque question** reçoit :
  - sa réponse, sa preuve et le montant en jeu ;
  - la correction proposée ;
  - une priorité : avant la paie d'octobre, avant janvier 2027, ou plus tard.
- **Conclusion par société** : à partir de quel mois la réduction d'EYWAI est fiable, et à quelles conditions.
- **Questions à Gaëlle ou à Cegid** : seulement ce que les données et les textes ne tranchent pas. Une phrase chacune, avec l'exemple chiffré.
- **Suite** : un plan d'implémentation des corrections, puis tests et filet avant tout déploiement.

## 6. Données à demander dès le début

Le chantier avance sans elles ; en attendant, il note « donnée manquante ».
- Les DSN de juillet et d'août des trois sociétés : elles donnent le SMIC retenu pendant les arrêts et montrent si le SMIC de juin a été régularisé.
- Les réponses de Gaëlle :
  - Q3, absences non payées ;
  - Q7, SMIC de juin ;
  - la régularisation de janvier chez Comitech.
- Les conventions de forfait (216 jours) des cadres concernés.

## 7. Contraintes

- **Base de test en lecture seule** : Gaëlle y fait la vraie paie. Aucune écriture en base, calculs à blanc avec toutes les écritures piégées, jamais la production.
- **Pas de modification du moteur** pendant le chantier. Les scripts de vérification vivent hors de `app/`.
- **Aucun nom de salarié dans git** : les fichiers versionnés sont pseudonymisés (`data/_outils/pseudonymes.json`), les rapports nominatifs restent dans `data/_rapports/`, qui n'est pas versionné.
- **Textes officiels** : sources publiques, citées avec leur URL et leur date de consultation.
- **Coût** : au plus un agent par étape. Les étapes 1 et 3 peuvent tourner en parallèle, une société par agent. Pas de workflow multi-agents sans demande explicite.

## 8. Critères de fin

- Chaque question F, H, B, A, R, D et P a sa réponse, sa preuve et son montant.
- Tous les écarts de plus de 1 € du rejeu sont classés, sans aucun « inexpliqué ».
- Le calcul de référence passe tous ses cas de test, chacun rattaché à un texte.
- La conclusion est datée par société, et la liste des corrections est priorisée.
- Échéance : avant la paie d'octobre 2026.

## 9. Hors périmètre

- Coder les corrections : ce sera un plan séparé, après ce chantier.
- La déduction forfaitaire patronale et la réduction salariale sur les heures supplémentaires.
- La refonte de l'affichage du bulletin. Les défauts d'affichage sont seulement relevés : coefficient absent, remboursement masqué dans le bloc des allègements.
