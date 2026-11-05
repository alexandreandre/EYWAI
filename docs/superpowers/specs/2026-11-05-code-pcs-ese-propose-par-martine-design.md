# Code PCS-ESE trouvé par Martine (05/11/2026)

**Objectif.** La RH n'a plus à chercher le code PCS-ESE d'un salarié : Martine le trouve seule.
Quand elle est sûre, elle pré-remplit le code et dit pourquoi. Sinon, elle propose 3 codes.
La RH peut toujours changer le code.

**Déjà fait.** Le code « 9999 » est accepté par la fiche et par l'aperçu DSN (7228039e, fusionné
dans feat/dsn-octobre par 38aa72ec, en ligne sur le test le 05/11).

---

## 1. État vérifié le 05/11 (base de test, qui porte la vraie paie)

- **Fiches** : 309 fiches, 7 sociétés, toutes dans le même groupe. 106 ont un vrai code, 198 ont
  « 9999 » (repris des DSN de Quadra), 5 n'ont rien.
- **Fiche salarié** : le code se tape dans une case libre
  (`frontend/src/features/employee-detail/components/EmployeeProfileEditForm.tsx`, l. 420-431).
- **Création d'un salarié** : `CreateEmployeeForm.tsx` ne demande pas le code (aucune occurrence
  de « pcs » dans le fichier).
- **DSN** : Martine écrit le code en S21.G00.40.004. Elle n'écrit **aucun** bloc S21.G00.41
  (« Changements Contrat ») : le module `dsn_export` n'en contient aucune rubrique, seul l'import
  le lit.
- **Import DSN** : l'import d'une DSN de Quadra passe par `update_employee` et réécrit la
  classification, code PCS compris (`dsn_import/application/commit.py`, l. 944-945). Un nouvel
  import remettrait donc « 9999 » sur une fiche corrigée.
- **OETH** : le calcul de Martine prend les postes ECAP saisis à la main dans la table
  `company_oeth_ecap_positions`. Cette table est vide : pour Martine, l'effectif ECAP vaut 0 dans
  toutes les sociétés.

## 2. Règles et sources

Pages ouvertes le 05/11 (curl). Sources déjà vérifiées le 03/11 :
`data/_sources/net-entreprises/pcs-ese-verifie-2026-11-03.md`.

**R1. La liste des codes.** Ce sont les 430 codes de la table DSN « PCSESE » P26V01
(net-entreprises, datée du 25/09/2025) : les 429 codes de la PCS-ESE 2017, plus « 9999 ».
Fichier : https://portail.net-entreprises.fr/nmcl/telechargeFichierCsv/NEODESP26-PCSESE-P26V01.csv
(430 lignes de codes, comptées le 05/11). Le cahier technique DSN 2026.1.2 (24/12/2025) n'accepte
que ces valeurs : « CRE-11 : valeurs autorisées » (p. 183). Minuscules et majuscules comptent (p. 88).

**R2. Les métiers de l'Insee.** Chaque code a une page Insee qui donne les « Professions les plus
typiques », les « Professions assimilées » et les « Professions exclues », avec le code à prendre à
la place (« voir 524b »). Les 429 pages
`https://www.insee.fr/fr/metadonnees/pcsese2017/rubriqueRegroupee/<code>` ont été téléchargées
le 05/11 (dernière mise à jour Insee : 19/12/2025).

**R3. Cadre ou non cadre.** C'est la convention collective qui fait le cadre, et un cadre ne prend
pas un code de non-cadre :
- Insee, catégorie 37 : « La qualification de cadre ou d'ingénieur est définie par les conventions
  collectives. » Elle exclut « les personnels non cadres exerçant des activités comparables à
  celles classées dans la catégorie (catégorie 46) ».
- Insee, catégorie 46 : « les cadres au sens des conventions collectives étant toutefois toujours
  exclus ».
- Insee, rubrique 543g : « Personnels classés "employés" dans les conventions collectives ».

Pages : https://www.insee.fr/fr/metadonnees/pcsese2017/categorieSocioprofessionnelle/37 et
`…/categorieSocioprofessionnelle/46` (mise à jour le 19/12/2025).

Martine applique donc ce filtre : un cadre ne reçoit que des codes du groupe 3, un non-cadre
que des codes des groupes 4, 5 et 6.

**R4. Codes jamais proposés d'office.**
- Les groupes 1 et 2 visent des dirigeants. Exemple, la rubrique 210x : « Artisans, employant 0 à 9
  salariés, salariés de leur propre entreprise ».
- Les 17 codes réservés aux employeurs publics : « Les codes ajoutés pour les employeurs publics
  sont suffixés par un astérisque » (Insee, page 2912545).
- Les métiers notés « (Etat) », « (coll. loc.) » ou « (fonction publique) ».

Tous ces codes restent dans la liste, la RH peut les choisir.

**R5. Un changement de code se déclare dans le bloc 41. C'est obligatoire.**
- Cahier technique 2026.1.2, p. 215 : « Les rubriques de ce bloc sont à renseigner en cas de
  modification d'une caractéristique du contrat […]. Les rubriques doivent être renseignées avec la
  valeur avant changement. » La rubrique S21.G00.41.019, « Ancien code profession et catégorie
  socioprofessionnelle (PCS-ESE) », existe (p. 222).
- **Guide OETH de l'Urssaf**, version 2.5 du 7 avril 2026, p. 46, « Comment corriger les codes
  PCS-ESE des salariés ? » : « Les corrections concernant l'effectif sont à apporter, salarié par
  salarié, au niveau du bloc « Changements Contrat – S21.G00.41 » avec : une date de modification
  […] ; un « Ancien code profession et catégorie socioprofessionnelle (PCS-ESE) - S21.G00.41.019 » ;
  une « Profondeur de recalcul de la paie - S21.G00.41.028 » renseignée au premier jour du mois où
  le changement de caractéristique du contrat est constaté. »
  https://www.urssaf.fr/files/live/sites/urssaffr/files/outils-documentation/guides/Guide-OETH.pdf
- Cahier technique : la date de la modification est obligatoire, « du changement ou de la
  correction » (p. 26). La profondeur de recalcul est obligatoire quand il n'y a qu'un bloc (p. 26).
  Un bloc ne porte qu'une modalité (p. 103). « Ce changement doit être déclaré dans la DSN du mois
  où le service prend connaissance de ces modifications, même si elles ont eu lieu antérieurement »
  (p. 25).

**Conséquence : le script des 198 attend le bloc 41** (lot 3 avant le lot 4).

**R6. ECAP (emplois exigeant des conditions d'aptitude particulières).** Guide OETH de l'Urssaf :
- p. 22 : « l'effectif moyen annuel des […] (Ecap) est calculé et notifié par l'Urssaf » ;
  « L'employeur valorise les Ecap par leur identification via le code PCS-ESE (S21.G00.40.004) ».
- p. 23 : la déduction est « égale à l'effectif annuel moyen des Ecap de l'année de référence
  multipliée par 17 fois le Smic horaire brut ». La liste compte 36 codes, par exemple 624d, 641a et
  643a.
- p. 13 : « Les entreprises de 20 salariés et plus […] sont assujetties à l'obligation d'emploi ».

## 3. Ce que fait Martine

### 3.1 Une liste à la place de la case libre (fiche et création)

- Le champ « Code PCS-ESE » devient une liste avec une recherche. On peut chercher par code, par
  libellé ou par métier Insee (« soudeur »). Chaque ligne affiche par exemple « 674a — Ouvriers de
  production non qualifiés : chimie, pharmacie, plasturgie ». « 9999 — Profession non connue » vient
  en dernier.
- **Création d'un salarié** : le même champ est ajouté après « Poste » et « Statut ».
- **Contrôle** : le code doit être l'un des 430 (R1). Ce contrôle remplace la règle de format, côté
  écran comme côté serveur (enregistrement de la fiche et aperçu DSN).
- La liste vient d'un seul fichier JSON du serveur, construit à partir des pages Insee et de la
  table P26V01 (source et date notées dedans). L'écran le charge une fois.

### 3.2 Comment Martine trouve le code

On lui donne : la société, l'intitulé du poste et le statut (cadre ou non cadre). Deux postes sont
« le même » s'ils sont égaux une fois mis en minuscules, sans accents ni ponctuation.

a) **Les collègues de la société** : même poste, même statut, avec un vrai code (ni « 9999 », ni
   vide), sans compter le salarié lui-même. Si tous ont le même code, Martine est sûre.
b) **Personne dans la société** : Martine cherche le même poste, au même statut, dans les autres
   sociétés du groupe, avec la même règle.
c) **Personne dans le groupe** : Martine cherche l'intitulé dans les métiers Insee (R2), en lisant
   les professions typiques, puis les assimilées, puis les exclues (pour une exclue, elle prend le
   code « voir »). Elle applique les filtres R3 et R4. **Elle n'est sûre que si l'intitulé est égal
   à un métier Insee sans secteur entre parenthèses, et s'il ne reste qu'un seul code.**

Quand les collègues ne sont pas d'accord, Martine ne passe pas à l'étape suivante : elle propose
leurs codes.

**Point à trancher, avec un seuil de collègues (voir § 4).**

**Ce qui s'affiche :**
- Sûre, et le code actuel est vide ou « 9999 » : Martine pré-remplit le code et écrit la raison
  dessous. Exemples : « Même poste et même statut que 3 collègues de Cartol Industrie, tous en
  674a » ; « Métier Insee : Contrôleur de gestion, non cadre (461d) ». Rien n'est enregistré tant
  que la RH n'a pas enregistré.
- Pas sûre : 3 codes probables, chacun avec sa raison, à choisir d'un clic. Ce sont d'abord les codes
  des collègues (le plus fréquent en premier), puis les métiers Insee les plus proches.
- Code ECAP (R6) : la mention « Code ECAP : il réduit la contribution OETH » s'affiche à côté.
- **Un vrai code déjà sur la fiche n'est jamais remplacé** par une proposition.

### 3.3 Le bloc « Changements Contrat » (S21.G00.41) pour le code PCS

- **Quand le code d'une fiche change** (par la RH ou par le script), d'un code A (non vide) vers un
  code B, Martine note A et la date du jour sur la fiche (dans la classification, à côté du code).
- **Plusieurs changements avant la DSN** : Martine garde le premier A, celui qui a été déclaré, et la
  dernière date. Si le code revient à A, il n'y a plus rien à déclarer.
- **Un code reçu par un import DSN** ne crée rien à déclarer : le cabinet l'a déjà déclaré. Et
  **un import ne remplace jamais un vrai code par « 9999 »**.
- **Dans la DSN d'un mois** : pour chaque contrat qui a un changement non encore déclaré, daté au
  plus tard du dernier jour du mois, Martine écrit un bloc S21.G00.41 après le bloc S21.G00.40 :
  - .001 = la date du changement (JJMMAAAA) ;
  - .019 = A ;
  - .028 = le 1er jour du mois de cette date.
- **« Déjà déclaré »** veut dire : une DSN mensuelle de la société, pour ce mois ou un mois
  suivant, a été envoyée, reçue ou déposée à la main (table `dsn_transmissions`). Jusque-là,
  chaque DSN générée porte le bloc, aperçu compris. Martine n'a encore déposé aucune DSN : le bloc
  partira dans la première.
- **Sur la fiche**, sous le code : « Ancien code 9999 jusqu'au 06/11/2026 : la prochaine DSN le
  déclarera. »
- **Hors de ce chantier** : les autres modalités du bloc 41 (statut, temps de travail…). Martine
  n'en déclare aucune aujourd'hui. À traiter à part.

### 3.4 Les 198 fiches à « 9999 »

- Le script `backend/scripts/pcs_ese/remplacer_9999.py` utilise la même fonction que l'écran
  (§ 3.2). Il ne retient que les codes sûrs et écrit par `update_employee` : le § 3.3 note donc
  chaque changement.
- On le lance par `~/dev/eywai-filet/pcs-ese/simuler.sh`, puis par `appliquer.sh`. Le script
  sauvegarde les fiches en JSON avant d'écrire, s'arrête à la première erreur et tient un journal
  par initiales.
- **La simulation produit la liste des changements** dans `data/_rapports/pcs-ese/`, hors git. Pour
  chaque fiche : initiales, société, poste, statut, actif ou parti, code, règle (a, b ou c), raison,
  nombre de collègues, ECAP oui ou non. Elle donne aussi les totaux et l'effet OETH par société
  (§ 3.5).
- **Écriture seulement après « lance … » d'Alexandre**, et seulement quand le lot du bloc 41 est en
  ligne sur le test.
- Sans code sûr, la fiche garde « 9999 », et elle proposera 3 codes.

### 3.5 OETH : effet mesuré

- **Calcul de Martine** : aucun effet, car la table des postes ECAP est vide.
- **Calcul de l'Urssaf**, fait à partir des codes déclarés en DSN (R6) : seul un code de la liste
  ECAP change quelque chose.
  - Cartol Industrie et Mont Blanc Composite paient une contribution (14 256 € et 19 008 € dans le
    bilan 2025 de Martine). Aucun code proposé pour elles n'est un code ECAP : effet 0 €.
  - LEWIS : 7 « opérateurs spécialisés » (6 actifs) prendraient 624d, un code ECAP, sur l'avis
    d'un seul collègue. L'effectif moyen 2025 de LEWIS est de 9,04, sous le seuil de 20 : pas de
    contribution en 2025. Si LEWIS dépasse 20 salariés en 2026 : 6 salariés × 2 mois sur 12 × 17 ×
    12,31 € ≈ 209 € de déduction pour 2026. Avec la recommandation du § 4, ce code n'est pas
    posé : effet 0 €.
  - Règle c) : aucun code sûr n'est un code ECAP.
- **Hors de ce chantier, signalé** : le calcul OETH de Martine devrait lire la liste ECAP officielle
  plutôt qu'une saisie à la main. Et il prend un Smic de 11,88 € : `load_smic_horaire` cherche
  `horaire` ou `smic_horaire`, alors que la base range 12,31 € sous `smic_horaire_brut`.

## 4. Mesures sur les 198 (base de test, 05/11) et point à trancher

| Règle | Sûrs | Collègues pas d'accord ou plusieurs codes | Rien |
|---|---|---|---|
| a) collègues de la société | 16 | 3 | — |
| b) collègues du groupe | 50 | 9 | — |
| c) métiers Insee (120 salariés restants) | 2 | 17 | 101 |
| **Total** | **68** | 29 | 101 |

**Constat.** 62 des 66 codes sûrs par a) et b) reposent sur **un seul collègue**. Exemples :
43 agents de production de Mont Blanc Composite prendraient 674a d'après un seul salarié de
Comitech Composite. 7 opérateurs spécialisés de LEWIS prendraient 624d, « Monteurs qualifiés en
structures métalliques », qui est un code ECAP.

**La règle c) seule est peu fiable.** Avec une recherche moins stricte, elle donnait des codes
« sûrs » faux : un agent de production classé 561d (employés de la restauration), un chef
d'atelier classé 486d d'après le métier « Chef d'atelier (transport et réparation automobile) ». D'où la règle stricte du § 3.2 c).

**Recommandation.** Garder la règle d'Alexandre : un seul collègue suffit. La raison affiche le
nombre de collègues, et la liste du script passe sous les yeux d'Alexandre avant « lance ».
**Une seule exception : un code ECAP n'est sûr qu'avec au moins 2 collègues d'accord.** Sinon il est
proposé, pas posé, parce qu'il baisse une contribution sans que personne ne le voie.
Résultat : **61 fiches changent seules**, 137 gardent « 9999 » avec 3 propositions.

## 5. Tests (TDD)

- **pytest, la proposition** :
  - comparaison des postes, ordre a → b → c, unanimité, même statut ;
  - le salarié ne compte pas parmi ses collègues ; « 9999 » et vide ne comptent pas ;
  - filtres R3 et R4 ; exclusion « voir » ; intitulé coupé à 30 caractères ;
  - seuil ECAP ; 3 propositions classées.
- **pytest, le bloc 41** :
  - rubriques, ordre et formats (.001, .019, .028) ; un bloc par contrat ;
  - premier ancien code gardé ; retour au code d'origine ; « déjà déclaré » ;
  - un import ne note rien et ne remet pas « 9999 ».
- **pytest, le contrôle** : un code hors des 430 est refusé (fiche et aperçu DSN).
- **vitest** :
  - recherche par code, libellé et métier ;
  - pré-remplissage seulement sur un code vide ou « 9999 », raison visible, 3 choix d'un clic ;
  - champ présent à la création.
- **e2e sur le site de test** : fiche puis création, un parcours chacun, joués de bout en bout avant
  de les montrer.
- **Script** : simulation avec les écritures piégées (bac à sable). La liste est relue avant
  « lance ».

## 6. Lots, dans l'ordre

1. Le fichier de référence (430 codes et métiers Insee), la proposition et l'API, côté serveur.
2. L'écran : la liste et la proposition, sur la fiche et à la création.
3. Le bloc 41 du code PCS, et la garde de l'import.
4. Le script des 198 : simulation, puis liste à Alexandre, puis « lance ».

Les lots 1 à 3 sont déployés sur le test quand ils sont verts, jamais sur `main`. Le lot 4 attend
le lot 3 en ligne.
