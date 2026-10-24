# Maintien de salaire : les paliers de la convention de la plasturgie — conception

Date : 24/10/2026. Demande d'Alexandre : « Oui, parfait. Fais tout. » Branche `feat/maintien-paliers-convention`, partie de `feat/ijss-plafond-par-mois` (531773b8 : tout ce qui est déployé, plus le plafond des IJ par paie).

Matériel : l'analyse chiffrée de Comitech du 24/10, en lecture seule et au bac à sable (scratchpad de la session, dossier `comitech-maintien/` : `convention_calc.py`, `propose.json`, `cadre.json`, `actuel.json`, `releve_quadra.txt`), et la mémoire `comitech-maintien-plasturgie`. Les chiffres de ce document ont été refaits le 24/10 avec une maquette pure de la conception (scratchpad, `paliers-calc/`). Initiales seulement.

## 1. Le problème

Le maintien de Martine ne sait appliquer qu'**un seul taux** (`maintain_100_percent` ou `taux_maintien_conventionnel`) pendant **une seule durée** (`custom_duration_days`), comptée à partir de la fin de la carence (MSS:1041-1064, MSS:705-719). La convention de la plasturgie (IDCC 0292), celle de Comitech et de Colorplast, prévoit davantage :
- des **paliers** : 100 % pendant N jours, puis 75 % (non-cadres) ou 50 % (cadres) ;
- des **durées selon le statut** (cadre ou non) **et l'ancienneté** ;
- **pas de carence pour les cadres**, et pour les non-cadres une carence de 3 jours levée au premier arrêt de l'année ;
- une **limite par arrêt et par année civile**, qui cumule les arrêts.

Deux champs de la carte « Maintien de salaire » promettent une partie de cela, « Maintien par catégorie » (`maintain_by_category`) et « Prolongation selon ancienneté » (`seniority_extension_enabled`). Le moteur ne les lit pas (MSS:718 : « maintain_by_category : V1 ignoré » ; aucune lecture de l'autre).

Ce qui se passe chez Comitech (simulation du 24/10, au bac à sable) :
- **réglages d'aujourd'hui** : rien n'est maintenu, ni pour S.G. (non-cadre, 22 ans d'ancienneté, arrêt du 04/05 au 30/09), ni pour D.S. (cadre, 22 ans, arrêt du 27/04 au 26/07) ;
- **réglages proposés** (100 %, 57 jours plus la carence payée) : S.G. ne touche plus rien à partir du 61e jour, et D.S. reçoit 1 756,28 € de moins que dans Quadra sur juin et juillet.

## 2. Ce que disent les textes

Ouverts sur Légifrance le 24/10 (curl refusé, lus avec Firecrawl).

**Non-cadres — avenant du 15/05/1991, art. 13** ([KALIARTI000005856705](https://www.legifrance.gouv.fr/conv_coll/id/KALIARTI000005856705?idConteneur=KALICONT000005635856), en vigueur, étendu) :
- a) l'indemnisation prend effet à **un an d'ancienneté** ; pas de condition d'ancienneté pour un accident du travail ou une maladie professionnelle ;
- c) « Le nombre de jours indemnisables est limité à **105 jours calendaires** à la fois **par arrêt de travail et par année civile** », **135 jours** à 5 ans d'ancienneté ;
- d) les **3 premiers jours calendaires** de chaque arrêt de maladie (autre que professionnelle) ou d'accident (autre que du travail) ne sont pas indemnisés, sauf ALD. « Toutefois, il n'est pas fait application de ce délai de carence pour l'indemnisation du **premier de ces arrêts au cours d'une année civile**. » Si ce premier arrêt a duré moins de 3 jours, la carence de l'arrêt suivant est égale à sa durée ;
- e) l'indemnisation se calcule sur « la rémunération **nette** qu'aurait perçue l'intéressé s'il avait normalement travaillé pendant la période indemnisée » ;
- f) moins de 5 ans : **45 jours à 100 %, puis 60 jours à 75 %** ; à 5 ans : **60 jours à 100 %, puis 75 jours à 75 %** ;
- g) l'indemnisation est réduite des IJ de la Sécurité sociale, de la part employeur d'une prévoyance et des indemnités versées par un tiers responsable.

**Cadres — accord du 17/12/1992, art. 5** ([KALIARTI000005856723](https://www.legifrance.gouv.fr/conv_coll/id/KALIARTI000005856723?idConteneur=KALICONT000005635856) ; la version en vigueur est KALIARTI000005856724, étendue) :
- a) **un an d'ancienneté**, sans condition pour un accident du travail ou une maladie professionnelle. Pour un accident du travail (« à l'exclusion de l'accident de trajet ») ou une maladie professionnelle, les périodes sont **au moins celles de 2 ans d'ancienneté**. De 1 à 2 ans : **45 jours à 100 % et 45 jours à 50 %** ;
- b) à 2 ans : **60 et 60** ; à 3 ans : **90 et 90** ; à 5 ans : **120 et 120** ; à 10 ans : **150 et 150**. L'ancienneté s'apprécie **au début de l'arrêt** ;
- c) rémunération **nette** ; réduite des IJ et de la part employeur d'une prévoyance ;
- d) jours indemnisables « limité[s] à la fois par arrêt de travail et par année civile », comptés en **jours calendaires**.
- **Aucune carence** n'est prévue.

**Code du travail, L1226-1** (version du 27/06/2026, extrait lu le 24/10) : « Tout salarié ayant une année d'ancienneté dans l'entreprise bénéficie, en cas d'absence au travail justifiée par l'incapacité résultant de maladie ou d'accident [...] d'une indemnité complémentaire ». Ce maintien légal reste un plancher (§3.4).

## 3. Les choix

### 3.1 Le modèle : un barème en données, choisi par la société

**Recommandation : un barème écrit dans le code, versionné et testé, que la société choisit.** Pas de paliers saisis à l'écran.
- Un barème a deux **catégories**, non-cadres et cadres.
- Chaque catégorie a une liste de **tranches d'ancienneté** (« à partir de N mois complets »).
- Chaque tranche a une liste de **paliers** (taux, nombre de jours calendaires). La **limite** de la tranche est la somme de ses paliers : 105, 135, 90, 120, 180, 240 ou 300 jours.
- Chaque catégorie a sa **carence** : 3 jours pour les non-cadres, avec la levée du premier arrêt de l'année et le reliquat ; aucune pour les cadres.
- Deux règles d'accident : **sans condition d'ancienneté** en accident du travail, maladie professionnelle ou rechute ; pour les cadres, **au moins la tranche de 2 ans** en accident du travail (hors trajet) et maladie professionnelle.

Pourquoi : la convention fixe ces valeurs, l'utilisateur n'a rien à décider. Une saisie libre de 7 tranches et 14 paliers est une source d'erreurs pour une RH débutante, et Martine ne pourrait pas la vérifier. Un barème en code se teste au centime une fois pour toutes. Un deuxième barème, pour une autre convention, s'ajoutera de la même façon.

**Comment un jour est indemnisé.** Les arrêts connus du salarié (`arrets_connus` : ceux de l'année d'avant jusqu'au mois du bulletin, lus aux calendriers ; le bulletin, le forfait et l'aperçu les posent déjà) sont rejoués dans l'ordre. Pour chaque arrêt :
- **Un arrêt** est une chaîne de demandes de même nature séparées de 2 jours de reprise au plus (la règle des prolongations, `prolongation_arret.py`). Une prolongation n'est jamais un nouvel arrêt.
- **Ancienneté** : en **mois complets** (anniversaire du mois), au début de l'arrêt, depuis la date d'ancienneté de Martine (`_date_anciennete`). Le compte d'aujourd'hui (`_mois_anciennete`, « mois entamés ») donne 12 mois à D.J., entré le 28/05/2025, pour un arrêt du 05/05/2026 : il n'en a que 11. On garde ce compte hors du barème, pour ne rien changer sans barème.
- **Carence** (non-cadres, maladie ou accident non professionnel, hors ALD) : 3 jours calendaires. Elle est levée pour le premier arrêt de l'année civile qui ouvre droit à l'indemnisation. Si ce premier arrêt a duré moins de 3 jours, la carence du suivant vaut sa durée.
- **Rang** : chaque jour indemnisé de l'arrêt prend un rang (1, 2, 3…). Le rang fixe le palier : jours 1 à 60 à 100 %, jours 61 à 135 à 75 %, pour un non-cadre de 5 ans.
- **Limite** : un jour n'est indemnisé que si l'arrêt ET l'année civile du jour comptent moins de jours indemnisés que la limite de la tranche.

**Les paliers se comptent par arrêt, la limite par arrêt et par année (lecture A). Recommandé.** L'autre lecture (B) continue les paliers d'un arrêt à l'autre dans l'année : un deuxième arrêt reprendrait à 75 % là où le premier s'est arrêté. Le texte permet les deux.
- **Pour A** : l'article raisonne par arrêt (« chacun des arrêts », « par arrêt de travail »), et le f) fixe les taux des « premiers jours indemnisés » sans dire « de l'année ».
- **Surtout** : A n'est jamais moins favorable que B, jour par jour. Si B est la bonne lecture, A paie un peu trop, ce qui est permis. Si A est la bonne et qu'on applique B, Martine paierait moins que la convention.
- **Effet** : pour M.G. chez Colorplast, environ 2 891 € avec A, 2 208 € avec B (mémoire `comitech-maintien-plasturgie`).
- Le choix est une propriété du barème dans le code : en changer, c'est une ligne et ses tests. C'est la question n° 3 du §7.

**Accident de trajet : comme un accident du travail pour l'ancienneté et la carence, mais pas pour le minimum de 2 ans des cadres.** L'accord cadres exclut le trajet du seul minimum de 2 ans. L'avenant non-cadres parle d'« accident (autre qu'accident du travail) » sans dire où ranger le trajet. On prend la lecture qui ne peut pas sous-payer, et on pose la question (n° 5).

**Hors du barème** : les congés de maternité, de paternité et d'adoption gardent leur réglage (`maintain_parental_leave`). Le mi-temps thérapeutique et l'arrêt exceptionnel suivent le barème comme une maladie : aucun cas aujourd'hui chez Comitech ni chez Colorplast.

**Le statut cadre** se lit sur la fiche, comme aujourd'hui (`_statut_est_cadre`). Une fiche sans statut est lue non-cadre, et le bulletin le dit (§4).

### 3.2 Ce que voit l'utilisateur

**Recommandation : un choix « Barème de la convention » en tête de l'onglet Convention, avec deux valeurs.**
- « Aucun : les réglages ci-dessous » : aujourd'hui, au centime.
- « Plasturgie (IDCC 0292) ».

**Barème choisi** :
- **Le tableau du barème s'affiche, en lecture seule** : non-cadres, cadres, carence, limites, règles d'accident, avec les liens vers les deux textes. Le tableau vient de l'API (`GET /api/maintenance-settings/baremes`), construit depuis le barème du code : l'écran montre exactement ce que le moteur applique.
- **Les champs que le barème remplace disparaissent** de l'écran :
  - onglet Légal : ancienneté minimale maladie et AT/MP, carence employeur ;
  - onglet Convention : supprimer la carence employeur, carence annuelle unique, maintien à 100 %, différenciation selon pathologie, sans condition d'ancienneté, carence payée par an et son ancienneté, durée personnalisée.
  À leur place, une phrase : « Réglé par le barème Plasturgie (IDCC 0292) ».
- **« Appliquer le maintien légal »** devient une phrase fixe : « Avec le barème, Martine compare chaque mois avec le maintien légal et verse le plus favorable. »
- **Restent visibles et actifs** : maintien en jours ouvrés (la base, §3.3), congés de parentalité, mode de subrogation, arrêt sans subrogation, prévoyance.

**Les deux champs morts sont retirés de l'écran, barème ou non.**
- « Maintien par catégorie » et « Prolongation selon ancienneté » : le barème fait ce qu'ils promettaient.
- Les colonnes restent en base, sans migration destructive.
- Le front ne les envoie plus. Le back les accepte encore, sans les lire.

**Revenir à « Aucun »** rend le calcul d'avant, au centime. Les réglages manuels n'ont pas été effacés en choisissant le barème.

**Saisie libre des paliers : hors champ.** Aucune société d'aujourd'hui n'en a besoin, et elle ferait revenir le risque d'un barème faux.

### 3.3 La base du maintien

**Recommandation : un jour maintenu vaut ce que son absence a retiré du salaire.**
- **Mois entier en arrêt** (toute la période de paie est en arrêt, en un ou plusieurs arrêts qui se suivent) : le **salaire du mois**, réparti entre les paliers au prorata des jours ouvrés. Le salaire du mois, c'est le salaire de base et les heures sup structurelles, comme sur le bulletin.
- **Mois partiel** : la **journée** d'aujourd'hui en mode jours ouvrés (7 h et la quote-part d'heures sup structurelles), comptée par palier comme le cabinet : heures de base puis heures sup structurelles, chacune arrondie une fois (`_valeur_de_jours_ouvres`).
- **Sans le mode jours ouvrés**, même principe en jours calendaires. Mois entier : le salaire de base réparti au prorata des jours calendaires. Mois partiel : salaire / 30,42 par jour, comme aujourd'hui.
- **Temps partiel** : le salaire du mois du bulletin est déjà au temps partiel, la quotité ne s'y applique pas ; elle s'applique toujours à la journée.

Pourquoi : le texte garantit ce que le salarié « aurait perçu s'il avait normalement travaillé ». Un mois mensualisé entièrement travaillé paie le salaire du mois, qu'il compte 20 ou 23 jours ouvrés. Martine retient d'ailleurs exactement ce salaire quand tout le mois est en arrêt (« Retenue absence intégrale du mois limitée au salaire mensuel », `calcul_brut.py:1923-1966`). Avec la journée seule, un mois entier à 100 % verse plus que le salaire quand il a 22 jours ouvrés, et moins quand il en a 20 ou 21.

**Mesure sur Comitech** (maintien versé = garanti moins les IJ relevées sur Quadra : 41,19 €/jour pour S.G., 41,95 € pour D.S.) :

| Cas | Jours ouvrés × journée | Base recommandée | Quadra |
|---|---|---|---|
| S.G. mai (du 04 au 31/05, 20 j ouvrés) | 1 030,09 | 1 030,09 | 1 030,09 (308,97 au bulletin de mai, 721,12 de rappel en septembre) |
| S.G. juin (mois entier, 22 j ouvrés) | 1 030,13 | **995,78** | 995,78 (rappel de septembre) |
| D.S. avril (du 27 au 30/04) | 668,77 | 668,77 | 668,77 (533,04 au bulletin de mai, 135,73 dans le rappel de juin) |
| D.S. mai (mois entier, 21 j ouvrés) | 2 430,84 | **2 549,28** | 2 549,28 |
| D.S. du 18 au 26/07 (prolongation) | 510,85 | 510,85 | 510,85 (rappel d'août) |

Écart total à Quadra sur ces cinq cas : 152,79 € avec la journée seule (+34,35 et −118,44), **0,00 €** avec la base recommandée.

Ce n'est pas copier Quadra : c'est le texte, et Quadra le suit ici au centime.

### 3.4 Le plancher légal

**Recommandation : avec le barème, Martine calcule aussi le maintien légal, chaque mois, et verse le plus favorable des deux.**
- **On compare ce que l'employeur verse** (garanti moins les IJSS de ses jours), pas le garanti seul. Le moteur d'aujourd'hui compare les garantis (MSS:1072-1081) ; on ne change cela que sous le barème.
- **Le légal garde ses règles** :
  - un an d'ancienneté (L1226-1) ;
  - 7 jours de carence, 0 en accident du travail et maladie professionnelle (hors trajet), comme le moteur aujourd'hui (MSS:301-324) ;
  - durées du barème D1226-1 du moteur (`duree_maintien_par_taux`).
  Il ne lit aucun champ masqué.
- **Le légal et la convention valorisent les jours de la même façon** (§3.3), pour être comparables.

Pourquoi : la convention ne peut pas faire moins que la loi. Pour un non-cadre très ancien, le légal paie plus certains mois. S.G. a 22 ans d'ancienneté : 70 jours à 90 %, puis 70 jours à 66,67 %, après 7 jours de carence. Mois par mois, avec la base recommandée :

| S.G. | Convention : garanti / versé | Légal : garanti / versé | Martine verse |
|---|---|---|---|
| juillet (100 % jusqu'au 02/07, puis 75 %) | 1 722,12 / 445,23 | 1 781,95 / **505,06** | 505,06 (légal) |
| août (75 %) | 1 673,61 / **396,72** | 1 487,65 / 210,76 | 396,72 |
| septembre (75 % jusqu'au 15/09) | 836,81 / **218,96** | 1 284,79 / 172,66 | 218,96 |

En septembre, comparer les garantis aurait choisi le légal (1 284,79 €), qui verse moins (172,66 €) : il maintient plus de jours, donc déduit plus d'IJ. D'où la comparaison sur le versé.

### 3.5 Les IJSS déduites

**La règle du 23/10 s'applique par palier.** On déduit les IJSS des jours maintenus : les jours à 100 % et ceux à 75 % ou 50 %, en jours calendaires, à partir du premier jour indemnisé par la CPAM.
- Les IJSS des jours au-delà de la limite, ou des jours de carence, ne se déduisent pas : la CPAM les verse au salarié, ou l'employeur les reverse avec la subrogation.
- Avec un montant validé au « Suivi IJSS », chaque palier en prend sa part au prorata, comme le 23/10.
- La déduction totale est la somme des paliers. Le dernier palier prend l'arrondi, pour que l'écran tombe juste.
- **Le plancher à 0 vaut pour le mois** : le texte parle d'« indemnisation globale » réduite des IJ.
- **Sans subrogation, avec « Verser le salaire garanti en entier »**, rien n'est déduit, comme aujourd'hui.

**Garantie brute, pas nette.** Les deux textes garantissent le net. Martine, comme Quadra, garantit le brut et déduit les IJ brutes. C'est plus favorable au salarié : les IJ supportent moins de prélèvements que le salaire, le net dépasse donc le net garanti. Cinq cas de Comitech sont au centime ainsi. On garde le brut, et on pose la question (n° 4).

### 3.6 Compatibilité

- **Colonne `company_maintenance_settings.bareme_convention`**, `text`, nulle par défaut, contrôlée (`null` ou `'plasturgie_0292'`). Aucune ligne existante n'est touchée par la migration.
- **Sans barème** (colonne nulle, ou clé absente du dict) : le moteur suit le chemin d'aujourd'hui, octet pour octet. Le résultat est identique au centime et clé pour clé : aucune clé nouvelle, aucun texte nouveau. Les tests existants restent verts sans modification.
- **Empreinte** : la clé n'entre dans la partie « maintien » que si elle porte un barème. Sans barème, aucun bulletin ne passe « À recalculer ». Choisir le barème, ou revenir à « Aucun », fait passer « À recalculer » les bulletins du mois qui ont un arrêt, comme le 23/10.
- **Filet au centime** (`~/dev/eywai-filet`) : 0 bulletin et 0 cumul avec écart sur la branche, aucune société n'ayant de barème.
- **Ordre de déploiement** : la migration d'abord, sinon l'enregistrement de la carte échoue (colonne inconnue).

## 4. Ce qui se voit

- **Détail du maintien** (bulletin, `MaintenanceDetailModal`, et aperçu de l'absence, `MaintenancePreviewBlock`) : une section « Paliers de la convention ». Une ligne par palier du mois, par exemple « Du 01/07 au 02/07 : 2 jours ouvrés à 100 % — 194,04 € », et le barème appliqué (« Plasturgie (IDCC 0292), non-cadres, 5 ans et plus »). La carence employeur affichée est celle du barème.
- **« D'où viennent ces lignes »**, sur la ligne « Maintien de salaire employeur » : « Plasturgie (IDCC 0292) : 2 jours ouvrés à 100 % et 21 jours ouvrés à 75 %, salaire garanti 1 722,12 € », suivi s'il y a lieu de « moins 1 276,89 € d'IJSS versées par la CPAM au salarié (validées) ». Quand le légal l'emporte : « Maintien légal, plus favorable ce mois-ci que le barème ».
- **Alertes du maintien**, jamais d'état silencieux :
  - « Plasturgie : passage à 75 % le 03/07/2026 » ;
  - « Plasturgie : limite de 135 jours atteinte le 15/09/2026, plus de maintien ensuite. Vérifier la prévoyance. » ;
  - « Statut absent de la fiche : barème des non-cadres appliqué » ;
  - « Plasturgie : un an d'ancienneté requis pour une maladie (11 mois au début de l'arrêt) » ;
  - quand le légal l'emporte, l'alerte existante « Règle conventionnelle moins favorable que la règle légale — application de la règle légale ».
- **PDF** : la ligne de maintien ne change pas ; la mention « dont IJSS déduites » du 23/10 reste.
- **Carte des réglages** : le tableau du barème, la confirmation d'enregistrement comme les autres réglages, le rappel « Choix modifié, pas encore enregistré » comme le choix des IJSS.

## 5. Où vit le code

- **Barème** : `backend/app/modules/payroll/domain/baremes_maintien.py` (nouveau). Données, recherche de la tranche, description lisible pour l'écran.
- **Plan des jours** : `backend/app/modules/payroll/engine/paliers_convention.py` (nouveau), pur. Il rejoue les arrêts connus et rend, pour chaque jour, le taux du palier ; pour chaque arrêt, sa carence, sa tranche, la date de bascule et la date de la limite.
- **Moteur** (`maintien_salaire_service.py`) :
  - une branche quand `settings.get("bareme_convention")` porte un barème : valeur des jours (§3.3), plancher légal comparé sur le versé (§3.4), IJSS par palier (§3.5), clés `bareme` et `paliers` sur le maintien ;
  - la carence payée (crédit de Colorplast) et les champs remplacés ne sont pas lus sous le barème ;
  - les autres lecteurs suivent le barème : `compute_jours_avec_maintien_mois` (prime d'ancienneté), la prévoyance, plusieurs arrêts dans le mois.
- **Réglage** :
  - migration `supabase/migrations/20261024120000_bareme_convention_maintien.sql` ;
  - `maintenance_settings/schemas`, `application/commands.py` ;
  - route `GET /api/maintenance-settings/baremes`.
- **Empreinte** : `empreinte_entrees_service._maintien_pour_empreinte`.
- **Textes** : `backend/app/modules/payroll/domain/paliers_affiches.py` (nouveau) pour l'explication et les alertes ; `explications_lignes.py`.
- **Écran** :
  - `frontend/src/features/company/components/baremeConvention.ts` (nouveau : choix, champs remplacés, textes) ;
  - `MaintenanceSettingsCard.tsx`, `api/maintenanceSettings.ts` ;
  - `lib/paliersAffichage.ts` (nouveau), `MaintenanceDetailModal.tsx`, `MaintenancePreviewBlock.tsx`, `api/absences.ts`.

## 6. Tests et preuves

**Au centime, cas de Comitech que le texte explique** (contexte de test aux salaires de la fiche, IJ au montant validé relevé sur Quadra) :

| Cas | Attendu |
|---|---|
| S.G., non-cadre, 22 ans, premier arrêt de 2026 du 04/05 : mai | garanti 2 059,84, IJ 1 029,75, versé **1 030,09** |
| S.G., juin, prolongation, mois entier | garanti 2 231,48, IJ 1 235,70, versé **995,78** |
| D.S., cadre, 22 ans, du 27 au 30/04 | garanti 710,72, IJ 41,95, versé **668,77** |
| D.S., mai, mois entier | garanti 3 849,73, IJ 1 300,45, versé **2 549,28** |
| D.S., prolongation du 18 au 26/07 (83e à 91e jour) | garanti 888,40, IJ 377,55, versé **510,85** |

**Plan des jours** (pur) :
- S.G. 2026 : 100 % du 04/05 au 02/07 (60 jours), 75 % du 03/07 au 15/09 (75 jours). Rien pour l'arrêt du 02/10 au 12/10 : la limite de 135 jours de l'année est atteinte.
- Un deuxième arrêt de l'année a 3 jours de carence ; un premier arrêt de 2 jours donne 2 jours de carence au suivant, puis 3 au troisième.
- Accident du travail, maladie professionnelle, ALD : pas de carence. Prolongation à 2 jours de reprise : même arrêt, pas de carence, rang continu.
- Cadre : jamais de carence. Un arrêt de 6 mois d'ancienneté en accident du travail prend la tranche de 2 ans (60/60) ; en accident de trajet, la première tranche (45/45).
- Non-cadre de 11 mois complets en maladie : rien ; en accident du travail : 45 jours à 100 %, puis 60 à 75 %.
- Limite annuelle cumulée : après 80 jours indemnisés, un deuxième arrêt (moins de 5 ans) n'en reçoit plus que 25, à 100 % (lecture A).
- Arrêt à cheval sur deux années : la limite de l'arrêt tient, celle de l'année repart en janvier.
- Les 5 ans atteints pendant l'arrêt ne changent pas sa tranche.

**Moteur** :
- valeur des jours : mois entier = salaire du mois, réparti entre deux paliers au prorata des jours ouvrés ; mois partiel = journées par bloc ; mode calendaire ; temps partiel ;
- bascule de palier dans le mois (non-cadre de 6 ans, juillet), avec ses deux lignes de paliers et l'alerte ;
- plancher légal : S.G. juillet, le légal l'emporte (505,06 € versés) ; S.G. septembre, la convention l'emporte sur le versé (218,96 €) même si le garanti légal est plus haut ;
- avec subrogation : versé = garanti moins les IJSS des jours maintenus ; sans subrogation et « garanti en entier » : versé = garanti ;
- les champs remplacés (durée personnalisée, 100 %, carence payée, ancienneté minimale, maintien légal éteint) ne changent rien sous le barème ;
- **sans barème** : résultat identique clé pour clé avec ou sans la clé, et toute la suite existante verte sans modification ;
- plusieurs arrêts dans le mois, prime d'ancienneté, prévoyance.

**Réglage** : GET sans ligne ou avant migration → `null` ; PUT qui choisit le barème, puis revient à `null` ; valeur inconnue refusée ; `GET /baremes` rend le tableau.

**Empreinte** : sans barème, empreinte inchangée ; avec, « À recalculer » pour les seuls bulletins avec un arrêt.

**Écran** (vitest) : le choix, le tableau, les champs masqués, l'absence des deux champs morts, l'enregistrement.

**Filet au centime**, base 531773b8 contre la branche : 0 écart.

**Bac à sable Comitech**, lecture seule, écritures piégées (`simuler.py` avec `bareme_convention` en mémoire) : le tableau Quadra / Martine refait. Il n'est pas joint au commit.

## 7. Questions pour la personne qui fait la paie Comitech

À poser après le déploiement, avant de choisir le barème. Martine suit le texte en attendant.

1. **S.G., juillet.** Quadra verse 715,94 € pour juillet (rappel de septembre). C'est 15 jours ouvrés à 100 % (du 01 au 21/07), 1 jour à 75 % (le 22/07), moins 22 IJ (du 01 au 22/07). La convention donne 60 jours à 100 % du 04/05 au 02/07, puis 75 % dès le 03/07, jusqu'au 15/09 (135e jour). Pourquoi le passage à 75 % le 22/07 ? Et pourquoi rien en août et septembre, quand la convention donne 396,72 € et 218,96 € ?
2. **D.S., juin et juillet.** Quadra verse 1 919,99 € (du 01 au 22/06, conforme au texte), puis 1 652,41 € au bulletin de juillet, puis 510,85 € de rappel du 18 au 26/07 (conforme). Le 1 652,41 € ne se décompose en aucune combinaison simple de journées et d'IJ ; la convention donne 2 327,18 € du 23/06 au 17/07. Sur juin et juillet, la simulation du 24/10 mesurait +674,32 € pour Martine ; la base recommandée donne +615,53 €. Quelle période et quel taux couvre ce montant ?
3. **Les paliers d'un deuxième arrêt dans l'année** repartent-ils à 100 % (lecture A, celle de Martine), ou continuent-ils là où le premier s'est arrêté (lecture B) ?
4. **Net ou brut** : les textes garantissent la rémunération nette. Quadra garantit le brut. Est-ce un choix de la société ?
5. **Accident de trajet** : sans condition d'ancienneté et sans carence, comme un accident du travail ?
6. **D.J., accident du travail en mai, 11 mois d'ancienneté.** Quadra ne verse rien. Le texte supprime la condition d'ancienneté pour un accident du travail. Avec le barème, Martine verserait environ 431 € (simulation du 24/10, IJ estimées). Oubli dans Quadra ?

## 8. Hors champ

- **Colorplast ne change pas.** La pratique de Gaëlle (3 jours de carence payés par an, en jours ouvrés, sans maintien conventionnel) reste réglée à la main. La question lui est posée (M.G. : 310,78 € reçus en 2026, environ 2 891 € selon la convention ; mémoire `comitech-maintien-plasturgie`). Le barème ne s'appliquera chez elle que sur sa réponse.
- **Comitech** : le barème se choisira à l'écran après déploiement, avec Alexandre, après les questions du §7. Rien n'est écrit en base par ce chantier. Les rappels de mai à juillet de S.G. (2 432,84 €), dus en septembre, sont un geste à part (mémoire).
- **Les rappels du mois suivant**, à la manière de Quadra : Martine verse dans le mois de l'arrêt.
- **La garantie nette** (§3.5, question n° 4), et la déduction de la prévoyance et des indemnités d'un tiers responsable (art. 13 g).
- **Une saisie libre des paliers**, et d'autres conventions : un nouveau barème s'ajoutera dans le code.
- **Proposer le barème d'après l'IDCC de la société.**
- **L'empreinte des arrêts plus anciens** : modifier un arrêt de février ne fait pas passer « À recalculer » le bulletin d'octobre, même si la limite annuelle en dépend. C'est déjà vrai du crédit de carence payée.
- **Constat annexe, sans lien avec les paliers** : en mai, Martine retient tout le mois de S.G. (« Complément retenue absence intégrale du mois », 480,62 €), alors que son arrêt commence le 04/05 et que le 1er mai, férié chômé, le précède. Quadra laisse ce jour payé : 171,64 € d'écart sur le brut. La règle (`calcul_brut.py:1923`) se déclenche dès qu'aucun jour n'est planifié dans le mois. À vérifier à part.

## 9. Règles

- Moteur en Opus, tests d'abord, filet au centime avant tout déploiement. Déploiement seulement sur accord d'Alexandre, migration avant le code.
- Ne jamais régénérer un vrai bulletin ; bac à sable et lecture seule.
- Aucun nom de salarié dans le code, les tests, les commits ni les documents : initiales.
- Python 3.11 en CI.
- Textes en français, simples ; le produit s'appelle « Martine ».
