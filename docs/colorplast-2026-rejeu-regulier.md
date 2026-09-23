# Colorplast, janvier à juin 2026 : la paie rejouée à la régulière

Rejeu du 17/09/2026, `backend/scripts/colorplast_regulier_test.py`, comparé aux
bulletins Quadra ligne à ligne (`scripts.backtest.colorplast_lignes`).
Convention : **écart = EYWAI − Quadra**.

> **Il n'y a pas de cabinet** : Gaëlle fait la paie elle-même dans Quadra (Cegid). Quand ce document et les
> précédents disent « le cabinet », il faut lire « Gaëlle, dans Quadra » (précision d'Alexandre, 17/09/2026).

## Pourquoi un second rejeu

Le rejeu de référence (`colorplast_rejeu_test.py`) juge le moteur sur les
entrées du cabinet : les heures supplémentaires y sont une saisie mensuelle lue
sur le bulletin Quadra, les absences sont datées et quantifiées comme Quadra
les imprime, et deux mois d'entrée (Demory en mars, Fuckar en avril) sont
donnés au moteur par une surcharge. Il répond à la question « à entrées
égales, calculons-nous comme le cabinet ? » — et la réponse est oui, au
centime, de janvier à juin.

Il ne répond pas à l'autre question, celle du processus réel : **avec les
seules sources régulières, sans rien ajuster pour coller au bulletin, que
produit le moteur, et où s'écarte-t-il de ce que le cabinet a payé ?** C'est
ce que fait ce second rejeu.

## Les sources, et rien d'autre

| Source | Ce qu'elle apporte | Où |
|---|---|---|
| Feuilles de pointage (S02 à S25) | les heures de chaque jour, donc les heures sup et les journées courtes ou manquées | `data/colorplast/pointages/2026-0M/`, transcrites dans `colorplast_feuilles_janvier.py`, `colorplast_feuilles.py` (février à mai), `colorplast_feuilles_juin.py` |
| Calendrier d'absences du cabinet (classeur de Gaëlle) | congés payés, fériés non payés, journées « en récup », événement familial, heures du mois d'entrée de Demory | `data/colorplast/variables/2026-08/calendrier-2026-colorplast.xlsx`, lu par `colorplast_calendrier_cabinet.py` |
| DSN | arrêts de travail, datés | déjà au calendrier de la base de test (chargeur DSN) |
| Variables du mois | primes, acomptes, notes de frais, indemnités de transport, participation, augmentations | `colorplast_setup.py` (MONTH_DATA), inchangé |

Règle de lecture des feuilles, annotée par Gaëlle sur la feuille S03 :
heures = fin − début − 0,5 h de pause quand la journée dépasse 6 h. Une case
vide est un jour **sans pointage** (neutre : ni travail, ni absence) ; une case
barrée ou un « absente » est un jour **pointé absent** (0 h). Les lectures
douteuses sont listées dans `colorplast_feuilles.INCERTITUDES`, avec ce qui a
été retenu.

## Ce que le script fait, mois après mois

1. Le setup pose le mois (salaires, variables, absences telles que le cabinet
   les imprime) ; le cumul d'un entrant est remis à zéro.
2. Le planning de la fenêtre est **régularisé** : les congés, absences et
   événements familiaux recopiés des bulletins sont remis à l'horaire du jour ;
   les fériés restent des fériés ; les arrêts de la DSN ne sont pas touchés.
   Puis sont posés les congés du classeur et des feuilles (« C P » écrit dans
   la case), et l'événement familial de Cotte (25 au 27/02 : le classeur ne
   marque que le 25, le décès d'un parent ouvre trois jours, L3142-4, et la
   feuille le laisse sans pointage les trois jours). Les absences non
   justifiées ne se posent pas : elles viennent du pointage.
3. Les feuilles sont écrites au calendrier réel des deux mois que la fenêtre
   couvre ; les saisies d'heures sup du setup sont effacées pour tout le
   monde ; les surcharges de mois d'entrée sont retirées.
4. Les bulletins sont générés, puis comparés ligne à ligne aux PDF Quadra.
5. Tout est remis comme relevé : fiches, historiques de salaire, plannings,
   pointages, saisies, bulletins.

Ce qui n'est **pas** régulier et reste du setup : les variables du mois
(primes, acomptes, notes de frais) — ce sont des saisies de l'entreprise, pas
des lectures de bulletin — et les arrêts de la DSN, que le rejeu de référence
qualifie déjà (nature, bornes).

## Ce que les feuilles disent, semaine par semaine

Total pointé de chaque semaine, ce qu'en fait la règle hebdomadaire (39 h,
40ᵉ à 43ᵉ heure à 25 %, au-delà à 50 %, fériés et congés non assimilés parce
qu'à 0 h prévue), et ce que le cabinet a payé.

| Mois | Salarié | Semaines (heures pointées) | Feuilles, 25 % / 50 % | Fériés comptés | Cabinet | Brut EYWAI | Brut Quadra | Écart |
|---|---|---|---|---|---|---|---|---|
| Janvier | Bugny | S2=45.5 S3=43 S4=49 | 12 / 8,5 | 12 / 8,5 | 12 / 8,5 | 3023,40 | 3023,40 | 0,00 |
| Janvier | Cotte | S2=39 S3=39 S4=35.5 | 0 / 0 | 0 / 0 | 0 / 0 | 2351,89 | 2351,89 | 0,00 |
| Janvier | Espinosa | S2=45 S3=44 S4=44 | 12 / 3 | 12 / 3 | 12 / 4 | 3023,66 | 3046,68 | **−23,02** |
| Janvier | Gautheron | S2=39 S3=28 S4=30.5 | 0 / 0 | 0 / 0 | 0 / 0 | 2252,28 | 2252,28 | 0,00 |
| Janvier | Girerd | — | 0 / 0 | 0 / 0 | 0 / 0 | 3799,07 | 3799,06 | +0,01 |
| Février | Bugny | S5=45.5 S6=49 S7=52 S8=47.5 | 16 / 22 | 16 / 22 | 0 / 0 | 3376,90 | 2634,90 | **+742,00** |
| Février | Cotte | S5=39 S6=39 S7=39 S8=25.5 | 0 / 0 | 0 / 0 | 0 / 0 | 2398,38 | 2398,38 | 0,00 |
| Février | Espinosa | S5=42 S6=43 S7=45 S8=45 | 15 / 4 | 15 / 4 | 15 / 4 | 3104,24 | 3104,24 | 0,00 |
| Février | Gautheron | S6=40 S7=40.5 S8=40 | 3,5 / 0 | 3,5 / 0 | 3,5 / 0 | 2455,03 | 2455,03 | 0,00 |
| Février | Girerd | — | 0 / 0 | 0 / 0 | 0 / 0 | 3799,07 | 3799,06 | +0,01 |
| Mars | Bugny | S9=43 S10=50.75 S11=49.75 S12=49 | 16 / 20,5 | 16 / 20,5 | 16 / 10 | 3345,40 | 3124,90 | **+220,50** |
| Mars | Cotte | S9=17 S10=39 S11=39 S12=39 | 0 / 0 | 0 / 0 | 0 / 0 | 2398,38 | 2398,38 | 0,00 |
| Mars | Demory | — | 0 / 0 | 0 / 0 | 0 / 0 | 683,20 | 625,25 | **+57,95** |
| Mars | Espinosa | S9=45 S10=43 S11=46.75 S12=41.5 | 14,5 / 5,75 | 14,5 / 5,75 | 14,75 / 5,75 | 3134,94 | 3139,74 | **−4,80** |
| Mars | Gautheron | S9=27 S10=41 S11=38.5 | 2 / 0 | 2 / 0 | 0 / 0 | 1944,35 | 1609,96 | **+334,39** |
| Mars | Girerd | — | 0 / 0 | 0 / 0 | 0 / 0 | 3799,07 | 3799,06 | +0,01 |
| Avril | Bugny | S13=49.5 S14=56.5 S15=33.5 S16=43 | 12 / 20 | 15 / 20 | 18 / 0 | 3264,90 | 2949,90 | **+315,00** |
| Avril | Cotte | S13=39 S14=39.5 S15=30.5 S16=39 | 0,5 / 0 | 0,5 / 0 | 2 / 0 | 2406,47 | 2430,75 | **−24,28** |
| Avril | Demory | S13=33.5 S14=17 S16=39 | 0 / 0 | 0 / 0 | 0 / 0 | 1948,24 | 2017,05 | **−68,81** |
| Avril | Espinosa | S13=44 S14=45.25 S15=33.5 S16=40.25 | 9,25 / 3,25 | 12,25 / 3,25 | 18 / 3,75 | 2976,65 | 3156,05 | **−179,40** |
| Avril | Fuckar | S15=30.5 S16=39 | 0 / 0 | 0 / 0 | 5 / 0 | 1756,80 | 1818,80 | **−62,00** |
| Avril | Gautheron | — | 0 / 0 | 0 / 0 | 0 / 0 | 1915,13 | 20,20 | **+1 894,93** |
| Avril | Girerd | — | 0 / 0 | 0 / 0 | 0 / 0 | 3799,07 | 3799,06 | +0,01 |
| Mai | Bugny | S17=27.5 S18=38 S19=38 S20=33.5 S21=43 | 4 / 0 | 15 / 0 | 15 / 0 | 2755,99 | 2952,34 | **−196,35** |
| Mai | Cotte | S17=41 S18=34 S19=34 S20=30.5 S21=39 | 2 / 0 | 2 / 0 | 0 / 0 | 2477,35 | 2444,33 | **+33,02** |
| Mai | Demory | S17=39 S18=34 S19=26 S20=25.5 S21=39 | 0 / 0 | 0 / 0 | 0 / 0 | 1529,05 | 1529,05 | 0,00 |
| Mai | Espinosa | S17=42 S18=41 S19=40 S20=28.5 S21=44 | 10 / 1 | 15 / 6 | 3 / 6,5 | 2998,01 | 2990,19 | **+7,82** |
| Mai | Fuckar | S17=43 S18=34 S19=8.5 S20=32.5 S21=39 | 4 / 0 | 6 / 0 | 2,5 / 0 | 1687,65 | 1664,78 | **+22,87** |
| Mai | Gautheron | S18=17 S19=34 S20=25.5 S21=39 | 0 / 0 | 0 / 0 | 0 / 0 | 2432,78 | 2432,78 | 0,00 |
| Mai | Girerd | — | 0 / 0 | 0 / 0 | 0 / 0 | 3855,98 | 3855,98 | 0,00 |
| Juin | Bugny | S22=39 S23=43 S24=46.5 S25=46.5 | 12 / 7 | 12 / 7 | 14 / 7 | 3048,73 | 3084,43 | **−35,70** |
| Juin | Cotte | S22=37.5 S23=41.5 S24=41.5 S25=42.5 | 8,5 / 0 | 8,5 / 0 | 0 / 0 | 2584,67 | 2444,33 | **+140,34** |
| Juin | Demory | S24=8.5 S25=39 | 0 / 0 | 0 / 0 | 0 / 0 | 2026,41 | 2026,41 | 0,00 |
| Juin | Espinosa | S22=34.5 S23=44 S24=45.08 S25=47 | 12 / 7,08 | 16 / 7,08 | 16 / 7 | 3179,94 | 3256,34 | **−76,40** |
| Juin | Fuckar | S22=32 S23=46 S24=40 S25=43 | 9 / 3 | 10,5 / 3 | 4 / 3 | 2527,62 | 2450,68 | **+76,94** |
| Juin | Gautheron | S22=31.5 S23=39.5 S24=31 S25=39 | 0,5 / 0 | 1,5 / 0 | 0 / 0 | 2440,99 | 2327,64 | **+113,35** |
| Juin | Girerd | — | 0 / 0 | 0 / 0 | 0 / 0 | 3855,98 | 3855,98 | 0,00 |

## Ce que le moteur produit, et les écarts avec le cabinet

Seize bulletins sur trente-sept sortent au centime (Girerd ×6, Cotte janvier-mars, Gautheron janvier, février et mai, Demory mai et juin, Bugny janvier, Espinosa février). Écart de brut par bulletin dans le tableau ci-dessus ; ci-dessous, mois par mois, ce qui l'explique.

### Janvier

Cinq bulletins, quatre au centime. Anthony : sa feuille de la semaine du 5 janvier donne 44 h, le cabinet en a payé 45 — une heure à 50 % de moins chez nous, 23,02 €.

- **Une heure de plus dans la saisie du cabinet** (à trancher) — Feuille S02 d'Anthony : 6h–16h les quatre premiers jours, 6h–12h le vendredi, 44 h. Quadra paie 4 h à 50 %, ce qui suppose 45 h. Le rapprochement plus bas avait aligné la feuille sur la saisie ; ici la feuille est prise telle quelle. Question 5.


**Vérifié (17/09)** : janvier rejoué avec le décompte de Gaëlle, `--ajuster ESPINOSA:01-05=10.5`
(45 h la semaine du 5 janvier). Le bulletin d'Espinosa tombe au centime : brut 3 046,68, 12/4 h sup,
96 champs identiques ; il ne reste que la présentation de la prime d'ancienneté et le total des retenues
sans la mutuelle famille, déjà connus. L'écart tient à cette seule heure.

### Février

Cinq bulletins, quatre au centime. Michel : 38 h au-delà de 39 h sur ses feuilles, 16 à 25 % et 22 à 50 %, rien de payé — 742,00 € de brut.

- **Les heures de Michel** (à trancher) — Trois de ses quatre semaines portent le total écrit de la main de Gaëlle : 45,5, 49 et 52 h. Le moteur les paie ; le cabinet non. Anthony et Marion, sur les mêmes semaines, sont payés ce que disent leurs feuilles. Constat 5, question 5.

### Mars

Six bulletins, deux au centime (Léo, Fabrice). Michel : 10,5 h à 50 % de plus que le cabinet, 220,50 €. Anthony : un quart d'heure de moins, 4,80 €. Aurélien, entré le 23 : 7 jours ouvrés à 7,8 h chez nous, ses 50,5 h réelles chez le cabinet. Marion : le congé du 23 février et 2 h sup retrouvés sur la feuille, 3,5 h manquantes la semaine du 23 là où le cabinet n'en retient qu'une, et le maintien de salaire toujours en attente.

- **Les heures de Michel, encore** (à trancher) — Ses semaines 10, 11 et 12 font 50,75, 49,75 et 49 h : 20,5 h au-delà de 43 h, 10 payées. Question 5.
- **Le mois d'entrée d'Aurélien** (sans conséquence) — Le cabinet paie les heures réellement faites du 23 au 31 mars, 47,5 h et 3 h structurelles. Le moteur proratise le mois aux jours ouvrés sous contrat, 7 sur 22, soit 49 h et 5,6 h : 57,95 € de plus. Sa demi-journée du 25 mars (3 h) tombe ensuite dans la fenêtre d'avril, où le moteur la retient : 68,81 € de moins. Sur les deux mois, 10,86 € d'écart. Deux méthodes admises ; la leur colle aux heures faites, la nôtre au calendrier.
- **La semaine du 23 février de Marion** (à trancher) — Feuille S09 : congé le lundi, 8h30–15h30 le mardi, 6h–15h le mercredi, 6h–12h le jeudi et le vendredi — 27 h pointées et 8,5 h de congé, 3,5 h sous les 39 h. Le moteur retient ces 3,5 h (40,66 €), le cabinet 1 h (11,65 €). Question 10.

### Avril

Sept bulletins, un au centime (Fabrice) ; Marion en arrêt, toujours en attente pour le maintien. Michel : 12 h à 25 % et 20 h à 50 % sur les feuilles, 18 h à 25 % et rien à 50 % payées, +315,00 €. Anthony : 9,25 et 3,25 contre 18 et 3,75, −179,40 €. Léo : 0,5 h contre 2, −24,28 €. Hugo, entré le 7 : aucune heure sup sur ses feuilles, 5 payées, et un mois d'entrée proratisé autrement, −62,00 € en tout. Aurélien : la demi-journée du 25 mars, −68,81 €.

- **Le lundi de Pâques dans le seuil des 39 h** (à trancher) — Le cabinet compte le férié chômé comme une journée travaillée : la semaine du 6 avril rapporte 3 h à 25 % à Michel et à Anthony. Chez nous le férié est à 0 h prévue et ne compte pas. La Cour de cassation exclut les fériés chômés du seuil (1ᵉʳ décembre 2004, 4 avril 2012) ; l'administration et beaucoup de conventions les comptent. À trancher — question 13.
- **Ce que les feuilles ne donnent pas** (à trancher) — Le férié compté, il reste 3 h chez Michel (18 payées contre 15), 5,75 h à 25 % et 0,5 h à 50 % chez Anthony, 1,5 h chez Léo et 5 h chez Hugo dont aucune feuille ne rend compte — et 20 h à 50 % de Michel qui n'ont pas été payées. Le classeur de détail d'avril n'est pas dans nos données. Question 5.
- **Le mois d'entrée de Hugo** (sans conséquence) — Le cabinet retire 30,5 h, les journées du 1ᵉʳ au 6 avril à l'horaire, et garde les 17,33 h structurelles entières. Le moteur paie 18 jours ouvrés sous contrat à 7,8 h : 14,25 € de plus. Deux méthodes admises.

### Mai

Sept bulletins, trois au centime (Aurélien, Marion, Fabrice). Michel : 4 h contre 15 payées, −196,35 € — les 11 h manquantes sont exactement les fériés de la période comptés comme travaillés. Anthony : 10 h à 25 % et 1 à 50 % chez nous, 3 et 6,5 chez le cabinet, +7,82 € seulement. Léo +2 h, Hugo +1,5 h. Aurélien : un congé le 15 mai sur son bulletin, rien au calendrier ni sur sa feuille.

- **Trois fériés dans la même fenêtre** (à trancher) — 1ᵉʳ mai, 8 mai, Ascension. Comptés à l'horaire du jour, les feuilles de Michel donnent exactement les 15 h payées ; sans eux, 4. Même mécanique chez Anthony (15 h au lieu de 10) et chez Hugo (6 au lieu de 4). C'est le seul point de méthode qui pèse sur plusieurs bulletins. Question 13.
- **Les journées « en récup » d'Anthony** (à trancher) — Le calendrier de Gaëlle marque Anthony « en récup » le 15 mai, le 25 mai et le 3 juin. Le cabinet retire ces journées de ses heures sup à 25 % : 15 h fériés compris, moins 12 h de récup (5 + 7), 3 h payées. C'est un repos compensateur de remplacement : il suppose un accord, et il n'apparaît sur aucun bulletin. Question 11.
- **Le congé d'Aurélien du 15 mai** (à trancher) — Bulletin de mai : un jour de congé payé le 15. Calendrier de Gaëlle : rien. Feuille S20 : case vide. À la régulière, pas de congé — le brut est le même, le compteur non. Question 12.

### Juin

Sept bulletins, deux au centime (Aurélien, Fabrice). Anthony : 16 h à 25 % chez le cabinet, 12 chez nous — les 4 h sont le lundi de Pentecôte, pris « en récup » et compté comme travaillé, −76,40 €. Michel −2 h, Hugo +5 h, Léo +8,5 h : les compensations entre semaines du constat 8. Marion : case vide le 10 juin, rien au calendrier, 7,8 h retenues par le cabinet et rien chez nous, +113,35 € avec sa demi-heure sup de la semaine 23.

- **Le lundi de Pentecôte** (à trancher) — Journée de solidarité chez Colorplast. Michel et Léo l'ont travaillée. Anthony et Marion non, et le cabinet la compte quand même dans leur seuil de 39 h. Question 13.
- **Les compensations entre semaines** (nous avons raison) — Hugo −5 h, Léo +8,5 h, Michel −2 h : le classeur du cabinet additionne les semaines, négatives comprises. Les heures sup se décomptent par semaine civile. Constat 8, questions 8 et 9.
- **Le 10 juin de Marion, le 8 juin d'Aurélien** (à trancher) — La feuille S24 de Marion est vide ce mercredi-là, entre deux journées pointées ; le calendrier ne dit rien ; le cabinet retient 7,8 h. Pour Aurélien le 8 juin, la case est barrée : le moteur retient 8,5 h, comme le cabinet. Une case vide n'est pas une absence tant que personne ne l'a dite. Question 12.

## Les écarts par nature

| Nature | Où | Combien | Ce qu'on en fait |
|---|---|---|---|
| Heures sup : les feuilles contre la saisie du cabinet | Bugny février (+742,00), mars (+220,50), avril (+315,00) ; Espinosa janvier (−23,02), mars (−4,80), avril (−179,40 dont 3 h de férié) ; Cotte avril (−24,28), mai (+33,02) ; Fuckar avril (−76,25 sur −62,00), mai (+22,87) ; Gautheron mars (+32,37) | ≈ +1 060 € nets d'écart sur six mois, presque tout chez Bugny | Question 5 (Bugny), incertitudes de lecture listées dans `INCERTITUDES` |
| Fériés chômés comptés par le cabinet dans le seuil des 39 h, pas par nous | Bugny avril (3 h), mai (11 h, −196,35) ; Espinosa avril (3 h), mai (5 h à 25 %, 5 h à 50 %), juin (4 h, −76,40) ; Fuckar mai (2 h), juin (1,5 h) ; Gautheron juin (1 h) | ≈ 26 h à 25 % et 5 h à 50 % d'avril à juin | À trancher chez nous (Cass. contre usage) ; question 13 |
| Journées « en récup » retirées par le cabinet | Espinosa mai : 12 h (15/05 et 25/05) retirées de ses heures sup à 25 % | 12 h à 25 % | Question 11 (accord de repos compensateur ?) |
| Compensations entre semaines (constat 8) | Juin : Bugny −2 h, Cotte +8,5 h, Fuckar +5 h, Gautheron +0,5 h | comme au rejeu de juin | Nous avons raison ; questions 8 et 9 |
| Mois d'entrée : jours ouvrés à 7,8 h chez nous, heures réelles chez le cabinet | Demory mars (+57,95) puis sa demi-journée du 25/03 retenue en avril (−68,81) ; Fuckar avril (+14,25 sur le prorata) | < 15 € par salarié sur deux mois | Sans conséquence, deux méthodes admises |
| Journées lues sur la feuille | Gautheron 24 et 26/02 : 3,5 h retenues contre 1 h (−29,01) ; Gautheron 10/06 : case vide, rien retenu contre 7,8 h (+105,14) ; Demory 08/06 : case barrée, 8,5 h comme le cabinet ; Demory 25/03 : 3 h du calendrier du cabinet, 5,5 h retenues | | Questions 10 et 12 |
| Congés : bulletin contre calendrier | Demory 15/05 (bulletin seul) ; Espinosa et Girerd 25/05 (bulletin de mai seul, « en récup » au calendrier pour Espinosa) | brut identique, compteurs différents | Question 12 |
| Maintien de salaire de Gautheron | mars, avril, juin | inchangé | En attente, question 4 |
| Suites mécaniques | cotisations, CSG, allègement, nets, cumuls, à la suite de chaque ligne ci-dessus | | — |

## Ce que cela dit du moteur

- **La chaîne pointage → heures sup est juste** : sur vingt-neuf couples salarié-mois, le moteur donne exactement ce que la règle hebdomadaire donne sur les feuilles, au centième.
- **Les fériés et les congés à 0 h prévue n'entrent pas dans le seuil** (`heures_assimilees`, `analyzer.py`). C'est le seul point de méthode qui pèse sur plusieurs bulletins : 26 h à 25 % d'avril à juin. Les congés posés par `regulariser_le_planning` gardent l'horaire du jour et sont assimilés (Gautheron 23/02) ; ceux posés par l'interface sont à 0 h. À trancher, puis à corriger pour de bon ; voir [[defauts-moteur-paie-revus]] et la question 13.
- **Le mois d'entrée est payé aux jours ouvrés sous contrat × 7,8 h** (`_facteur_prorata_entree_sortie`) : Demory 7 × 7,8 = 54,6 h, Fuckar 18 × 7,8 = 140,4 h. Le cabinet paie les heures réelles (Demory) ou retire les heures d'avant l'embauche à l'horaire en gardant les 17,33 h structurelles entières (Fuckar). Les deux méthodes sont admises ; la nôtre s'écarte de moins de 15 € par salarié.
- **Le férié non payé d'un salarié de moins de trois mois est déduit seul** (`_jour_ferie_est_paye`) : Demory 06/04, 08/05, 14/05, Fuckar 14/05, au centime du cabinet. Il n'y a plus besoin de le poser en absence.
- **Le bilan hebdomadaire des absences fonctionne** : Gautheron S09 (2 + 2,5 − 1 = 3,5 h), S11 (0,5 h) ; Demory 25/03 (5,5 h) ; Cotte 21/01 ; Gautheron 13 et 14/01. Une case vide reste neutre (Gautheron 10/06, Bugny 21 et 24/04, Demory 7 et 15/05) — c'est voulu, et c'est ce qui fait la question 12.
- **Ce qui reste du setup dans le rejeu régulier** : les variables du mois et les arrêts de la DSN, qualifiés par le rejeu de référence. Les surcharges de mois d'entrée et les absences recopiées des bulletins sont retirées.

## À demander à Gaëlle

- Q10 — Marion, semaine du 23/02 : 3,5 h sous les 39 h sur la feuille, 1 h retenue.
- Q11 — Anthony « en récup » les 15/05, 25/05 et 3/06 : quel accord, quel compteur ?
- Q12 — Trois journées où bulletin, calendrier et feuille divergent : Aurélien 15/05, Marion 10/06, Anthony et Fabrice 25/05.
- Q13 — Les fériés chômés comptent-ils dans le seuil des 39 h chez Colorplast, et au titre de quoi (usage, convention de la plasturgie) ?
- Q5, reformulée — Michel : 1 277,50 € d'heures sup sur ses feuilles de février à avril, non payées.

---

# Rejeu du 22/09/2026 : ce que l'option de compensation a changé

Même script, mêmes sources, avec les réglages d'aujourd'hui — option
« compensation des heures entre semaines » **active** depuis le 21/09,
règle légale de l'indemnité de fin de contrat, pointages de juillet corrigés.
Base remise en état et chaîne de paie vérifiée intacte (44 bulletins,
84 cumuls identiques).

## Le solde : l'option éloigne de Quadra

Les six mois ont été rejoués deux fois, avec et sans l'option, tout le reste
égal (le réglage société est remis dans les deux cas).

| | Bulletins au centime | Écart absolu cumulé |
|---|---|---|
| Sans l'option | **16 / 37** | 3 028,81 € |
| Avec l'option | 13 / 37 | 3 677,40 € |

**L'option éloigne de 648,59 € sur six mois et coûte trois bulletins exacts.**

Elle rapproche là où Gaëlle compense vraiment : Bugny mai (−196,35 → +35,70),
Espinosa juin (−76,40 → +1,88), Demory avril (−68,81 → 0,00), Espinosa avril
(−179,40 → −121,84). Elle éloigne ailleurs, et plus fort : Espinosa mai
(+7,82 → +281,80), Gautheron janvier (0,00 → +146,10), Cotte juin
(+140,34 → +265,82), Demory juin (0,00 → +107,32), Cotte janvier
(0,00 → +46,49).

## Pourquoi : l'option fait deux choses, pas une

`_TYPES_REMPLACES = ("travail_hs25", "travail_hs50", "absence_injustifiee")`.
La compensation ne se contente pas de solder les heures supplémentaires entre
semaines : elle **supprime aussi les absences injustifiées** de la fenêtre, et
ne les remplace par rien quand le solde est négatif — « jamais de retenue ».

C'est conforme à la règle décidée le 21/09, mais la mesure montre que Gaëlle,
elle, retient. Janvier rejoué sans l'option le prouve, toutes choses égales :

| Janvier | Quadra | avec l'option | sans l'option |
|---|---|---|---|
| Cotte | 2 351,89 | 2 398,38 (+46,49) | **2 351,89 (0,00)** |
| Gautheron | 2 252,28 | 2 398,38 (+146,10) | **2 252,28 (0,00)** |

Les retenues de Cotte le 21/01 et de Gautheron les 13 et 14/01 sont celles que
Quadra applique ; l'option les efface. La partie « heures supplémentaires » de
l'option tient ; la partie « absences » est à rouvrir.

## Les écarts qui restent, classés

**Vrais chantiers**

1. **L'option de compensation** — 648,59 € et trois bulletins exacts perdus.
   Décision à prendre avant août, puisque août sera calculé avec elle.
2. **Les fériés chômés dans le seuil des 39 h** — Gaëlle les compte, pas nous.
   ≈ 26 h à 25 % d'avril à juin, sur Bugny, Espinosa, Fuckar et Gautheron.
   Cassation contre usage : à trancher, pas à corriger d'office. Question 13.
3. **L'arrêt maladie long** — Gautheron avril : Quadra déduit 1 816,38 €,
   nous 1 540,88 € (275,50 € de moins, environ trois jours), et le plafond
   Sécu tombe à 267,00 € chez nous contre 4 005,00 € chez Quadra. Un seul
   salarié-mois, mais le mécanisme de proratisation est à vérifier.

**Le plus gros montant, qui n'est pas un défaut moteur**

4. **Les heures supplémentaires de Bugny** — environ 1 600 € sur février à
   juin (+742,00 en février seul, où Gaëlle n'a payé aucune heure sup alors que
   ses feuilles portent 16 h à 25 % et 22 h à 50 %). Question 5, toujours sans
   réponse.

**Futilités récurrentes, à traiter pour le confort de lecture**

5. La mutuelle famille (98,13 €) que Quadra place hors du total des retenues :
   présente sur presque tous les bulletins.
6. La prime d'ancienneté : 60 champs en écart pour **0,00 €** — base et taux
   présentés autrement, montant identique.
7. Girerd : +0,01 € tous les mois, arrondi.
8. Le mois d'entrée proratisé aux jours ouvrés : moins de 15 € par salarié,
   deux méthodes également admises.
9. Les absences longues impriment **une ligne par jour** (17 lignes identiques
   chez Gautheron en avril, 15 en août). Le calcul est juste, l'affichage est
   illisible.

**Questions de saisie pour Gaëlle** : inchangées — questions 10 à 13 ci-dessus.

## Rejeu après correction du solde négatif (22/09, même journée)

Correction appliquée : les heures supplémentaires de la fenêtre absorbent les
absences injustifiées dans l'ordre des jours ; le manque qu'elles ne couvrent
pas est retenu sur les derniers jours manqués, à leur vraie date
(spec `2026-09-22-compensation-solde-negatif-retenu-design.md`).

| | Bulletins au centime | Écart absolu cumulé |
|---|---|---|
| Sans l'option | **16 / 37** | **3 028,81 €** |
| Avec l'option, non corrigée | 13 / 37 | 3 677,40 € |
| Avec l'option, corrigée | 15 / 37 | 3 472,85 € |

Les quatre bulletins de contrôle passent : Cotte janvier, Gautheron janvier et
Demory juin reviennent **exactement** sur Quadra ; Bugny mai reste à +35,70,
donc ce que l'option gagne n'a pas été défait.

Deux bulletins se dégradent, et aucun des deux ne met en cause la correction :

- **Demory, avril : 0,00 → −68,81.** L'option non corrigée effaçait ici une
  retenue **erronée** — sa demi-journée du 25 mars, qui tombe dans la fenêtre
  d'avril et que le moteur retient à tort. L'exactitude d'avant tenait à deux
  fautes qui s'annulaient. Le défaut est celui du mois d'entrée, déjà décrit
  plus haut, pas celui de la compensation.
- **Gautheron, mars : −297,47 → −324,02.** Une retenue de plus chez quelqu'un
  où nous retenons déjà trop ; son mois est dominé par le maintien de salaire
  en arrêt, question 4, toujours en attente.

**Conclusion.** La correction fait ce qu'elle promettait — deux bulletins
exacts regagnés, 204,55 € d'écart en moins — mais **l'option reste moins bonne
que son absence** : 3 472,85 € contre 3 028,81 €, 15 bulletins au centime
contre 16. Le critère posé dans la spec est donc atteint dans le mauvais sens.

Ce qui manque est identifié : le **compteur de récupération entre mois** de
Gaëlle, hors périmètre depuis le 21/09. Sans lui, l'option reproduit la moitié
de sa méthode — elle additionne les semaines comme son classeur, mais ignore
les journées « en récup » qu'elle retire ensuite (Espinosa, mai : +281,80 €,
12 h retirées les 15 et 25/05). C'est là que se loge l'essentiel de l'écart
qui subsiste.
