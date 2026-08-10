# Questions en suspens — 8 août 2026

Balayage des 21 questions de `docs/afaire.md` contre quatre sources : export
WhatsApp Elsa (rafraîchi ce matin, 6 681 messages), `data/`, `docs/`, Google
Drive.

**10 réponses trouvées, 5 pistes, 6 sans trace.** Aucune question d'Elsa ne reste
sans réponse de notre côté.

> **Mise à jour de fin de journée.** Deux dossiers déposés dans `data/` le 08/08
> — « MBC 2 » et « Avenants MAJI » — ont réglé les questions **#2** et **#3**, et
> confirmé la **#4** par la formule elle-même. Voir la dernière section.

Ce fichier est versionné dans un dépôt public : il cite des chemins, des lignes
et des liens, jamais de contenu nominatif. Les données extraites sont écrites
sous `data/`, gitignoré.

---

## Réponses trouvées

### #10 — Codes net-entreprises *(point #31)*

- **Attendu** : identifiant et mot de passe net-entreprises pour les 7 SIREN.
- **Trouvé** : identifiant + mot de passe + titulaire du compte pour **MBC,
  Comitech et Colorplast**. Elsa les a envoyés en photo le 07/08 à 19:30, une
  capture d'une page « SIRH — MAJI », avec le commentaire « J'ai déjà ceux là ».
  Les 4 autres sociétés restent à obtenir.
- **Source** : `data/_inbox/whatsapp-elsa/00000612-PHOTO-2026-08-07-19-30-42.jpg`,
  annoncée `_chat.txt:9164`.
- **Suite** : recopiés dans `data/_acces/net-entreprises.md`. Non testés :
  personne ne s'est encore connecté. Relancer pour Cartol, LEWIS, MAJI, Zone 404.

> La note d'accès affirmait le 07/08 qu'aucun identifiant n'existait dans
> l'export. C'était vrai à 17:51, plus à 19:30. Corrigé.

### #1 — Adresses e-mail, pour Colorplast *(point #4)*

- **Attendu** : un fichier par société, nom + adresse réelle.
- **Trouvé** : un export Quadratus « Liste des employés » pour Colorplast, avec
  une colonne e-mail renseignée. 7 salariés, **5 adresses réelles**, 2 vides à
  la source. Déposé sur le Drive le 09/06/2026, jamais ouvert.
- **Source** : Drive, dossier `COLORPLAST /`, `Coordonnées salariés + RIB.xlsx`
  <https://drive.google.com/file/d/1ST9ZPwC7SVKTRNuMDXaw9Qlx5vn2zoci/view>
- **Suite** : extrait dans `data/colorplast/referentiel/coordonnees-emails.csv`.
  Vérifier si les 2 adresses inventées de Colorplast sont justement les 2 vides
  — auquel cas rien n'est débloqué. Aucun fichier équivalent sur le Drive pour
  les six autres sociétés : c'est **ce même export** qu'il faut demander.

### #5, #6, #7 — CSE Mont Blanc Composite *(point #11)*

- **Attendu** : date d'élection, suppléants, collège.
- **Trouvé** : l'affichage des résultats. **1er tour le 20 novembre 2023**,
  4 titulaires et **4 suppléants**, répartis en deux collèges nommés. Les
  4 titulaires correspondent aux 4 lignes MBC de `Membres_CSE.xlsx`.
- **Source** : Drive, `MBC / CSE / election /`
  <https://drive.google.com/file/d/1wIrS4vTOqeaEwfjZ39b0_JLnQYJkBvN2/view>
- **Suite** : extrait dans `data/mbc/referentiel/cse-elections-2023.md`. La date
  de fin de mandat n'y figure pas : 4 ans par défaut donne le 19/11/2027, à
  confirmer par le protocole préélectoral, introuvable. Avec ça, les 4 mandats
  MBC sont chargeables. Cartol et LEWIS restent bloqués.

### #4 — Prorata des absences JTC *(point #8)*

- **Attendu** : les 30 jours sont-ils un seuil de déclenchement ou une franchise ?
- **Trouvé** : la note d'Elsa tranche. § 3 : « Absences supérieures à 30 jours
  sur N-1 : le droit est réduit **au prorata des absences**. […] Les absences
  ≤ 30 jours n'ont pas d'impact. » Au prorata des absences, pas de ce qui les
  dépasse : c'est bien un seuil, la lecture stricte déjà retenue.
- **Source** : `data/_inbox/whatsapp-elsa/00000607-Note JTC.docx`, § 3.
- **Suite** : rien à changer dans le paramétrage. Question à retirer de la liste.

### #14 — Entretiens professionnels et bilans à 6 ans *(point #25)*

- **Attendu** : les dates d'entretien professionnel et de bilan à 6 ans, les
  deux seuls entretiens obligatoires.
- **Trouvé** : deux fichiers de suivi, un par société, envoyés le 16/07 puis
  renvoyés le 27/07, jamais ouverts. **Colorplast : 6 salariés. Comitech :
  16 salariés.** Chaque ligne porte la date d'entrée, les échéances d'entretien
  professionnel (tous les 2 ans, trois périodes) et la date de bilan à 6 ans.
- **Source** : `data/_inbox/whatsapp-elsa/00000578-2024 Suivi bilan à 6 ans EP COLORPLAST.xlsx`
  et `00000579-2024 Suivi bilan à 6 ans EP comitech.xlsx`, onglet
  « Dates EAE-EP et OBLIGATIONS ».
- **Nuance importante** : ce sont des **dates à prévoir**, calculées depuis la
  date d'entrée. Les colonnes « date de réalisation » sont vides, sauf une
  poignée de lignes Colorplast dans l'onglet « Suivi EP ». Ça donne les
  échéances, pas l'historique.
- **Suite** : chargeable pour ces deux sociétés. Reste à demander pour les cinq
  autres.

### #15 — Cycle de 2 ans chez MBC *(point #25)*

- **Attendu** : confirmation que MBC est à 2 ans quand les six autres sont
  annuelles.
- **Trouvé** : le fichier d'Elsa l'écrit lui-même. Colonne « Règle appliquée »,
  toutes les lignes MBC : « Dernier entretien &lt;année&gt; -&gt; +2 ans ».
- **Source** : `data/_inbox/whatsapp-elsa/00000606-Planif_entretiens.xlsx`,
  colonne G.
- **Suite** : paramétrer MBC sur 2 ans. Confirmation orale de confort, pas
  bloquante.

### #16 — Règles de pause, 3 sociétés sur 5 *(point #27)*

- **Attendu** : la règle de pause des cinq sociétés non paramétrées.
- **Trouvé**, dans le fil des 4 et 6 juillet :
  - **MBC** : 10 min le matin et 10 min l'après-midi, **pauses payées**,
    comprises dans les 7,50 h/jour — `_chat.txt:8235` et `:8311`
  - **Cartol** : les pauses sont pointées, elles figurent déjà dans les
    pointages — `_chat.txt:8291`
  - **Comitech et LEWIS** : les salariés **dépointent à leur pause**, donc rien
    à déduire, la pause est déjà hors pointage — `_chat.txt:8295`
- **Suite** : paramétrable dès maintenant pour MBC, Cartol, Comitech et LEWIS.
  Manquent **MAJI et Zone 404**, jamais évoquées.

### #9 — PV de carence Comitech *(point #11)*

- **Attendu** : pour Colorplast, MAJI et Zone 404, CSE ou PV de carence ?
- **Trouvé** : le PV de carence de **Comitech**, daté du 16/11/2022. Il confirme
  ce qu'on supposait : c'est bien celui qui est périmé.
- **Source** : Drive, `COMITECH / CSE / PV de carence.pdf`
  <https://drive.google.com/file/d/15no7KYmuP5tMjoXSrEUjJ4_pH9FIvtET/view>
- **Suite** : la question reste entière pour Colorplast, MAJI et Zone 404 —
  aucun document pour ces trois-là.

### #2 et #3 — Soldes JTC et onglet « détail absences » *(point #8)*

Réglés en fin de journée par le dossier « MBC 2 » déposé dans `data/` :
**voir la dernière section**, qui donne les chiffres et la réserve à lever.

---

## Pistes (sujet évoqué, donnée manquante)

### #1 — Adresses e-mail, six autres sociétés *(point #4)*

- **Trouvé** : « pour les adresses email la demande est partie te tiens au
  jus », 27/07 (`_chat.txt:8967`) — **manque** : les fichiers.
- **À demander** : « Le même export Quadratus que le "Coordonnées salariés +
  RIB" de Colorplast, mais pour les six autres sociétés : la colonne e-mail y
  est déjà. »

### #18, #19 — Comptes comptables et accès Cegid *(point #26)*

- **Trouvé** : « Pour la Clé API cegid faudra attendre mi août »
  (`_chat.txt:9101`, Vanessa en vacances), et pour les OD de paie « je vais
  essayer de les demander à une autre personne » (`_chat.txt:9155`). La seule OD
  en notre possession reste celle de Colorplast, octobre 2025
  (`data/_inbox/whatsapp-elsa/00000003-od paies COLORPLAST 10-25.pdf`) —
  **manque** : une OD pour Cartol, Comitech, LEWIS, MAJI, MBC, Zone 404, d'où
  se lisent les comptes paniers, cantine et IJSS.
- **À demander** : on est mi-août, relancer sur les deux à la fois.

### #13 — Périmètre MBC des entretiens *(point #25)*

- **Trouvé** : trois noms éclaircis le 06/08 — AMARKHILL est bien une arrivée de
  juin 2026, fiche à créer ; deux autres salariés sont sortis le 3 juillet
  (`_chat.txt:9103-9106`) — **manque** : l'arbitrage sur les 13 noms inconnus et
  les 30 manquants.
- **À demander** : « Ton onglet MBC des entretiens date d'avant les mouvements
  de juillet ? Si oui je repars de mon effectif et j'ignore ta colonne. »

### #8 — Secrétaire du CSE MBC *(point #11)*

- **Trouvé** : le Drive porte deux sous-dossiers **vides**, `BOUSSANOUNE
  secretaire` et `PFISTER secretaire`, plus `GOISSAUD référent securité +
  delegue syndical` — **manque** : lequel des deux est secrétaire aujourd'hui.
- **À demander** : « Sur le Drive MBC, deux personnes sont notées "secrétaire".
  L'un est secrétaire adjoint, ou c'est un changement en cours de mandat ? »

### #17 — Nomenclature des codes de cotisation *(point #20)*

- **Trouvé** : trois accusés de réception le 07/08 en fin d'après-midi — « Ok
  demandé », « Ok demande », « Ça j'ai relancé » (`_chat.txt:9136-9138`) — mais
  ils suivent une rafale de six messages et **on ne peut pas dire lequel répond
  à quoi**. Elsa clôt par « tout le reste j'ai demandé à Gaelle, ça devrait
  arriver » (`_chat.txt:9156`).
- **À demander** : reposer la question nommément, sans la noyer dans une liste.

---

## Sans trace

- **#11** — l'état de provision CP des six autres sociétés. Les **trois** PDF
  « PROVISION CP » reçus (21/07 et deux fois le 27/07) sont tous **Cartol** ;
  les deux du 27/07 sont bit à bit identiques.
- **#12** — pourquoi l'état Cartol ne liste que 71 salariés sur 86 payés.
- **#20** — les DSN de juillet. Vérifié sur le Drive ce matin : le dossier `DSN`
  contient `06-2026` et rien de plus récent. Les dossiers « JUILLET &lt;société&gt; »
  créés le 03/08 portent des bulletins, des calendriers et des pointages, pas de
  DSN. Le « c'est tout sur le drive SIRH » du 07/08 visait juin, déjà en notre
  possession.
- **#5, #6, #7** — dates d'élection, suppléants et collège pour **Cartol et
  LEWIS**. Aucun PV, aucun affichage, aucun protocole sur le Drive.
- **#9** — CSE ou carence pour **Colorplast, MAJI et Zone 404**.
- **#21** — la date du point paye avec Gaëlle.

---

## Questions d'Elsa restées sans réponse

Aucune. Ses quatre questions du 07/08 — « Quel certificat ? » (17:41), « Tu veux
2025 ? » (17:45), « Tu as déjà les identifiants net entreprise ou tu les re veux
quand même ? » (17:51) — ont toutes reçu une réponse dans l'heure.

Elle a accusé réception du récapitulatif le 08/08 à 04:41 : « Je regarde tout je
te fais un retour asap ».

---

## À trier, hors questions

- Un conflit d'ingestion non résolu : `semaine 21 (1).pdf` du 22/06 diverge du
  fichier déjà rangé en `data/comitech/pointages/2026-05/semaine-21.pdf`.
  Même emplacement, contenu différent — arbitrage manuel.
- 33 pièces jointes restent inclassables faute de société ou de rubrique
  déductible du nom, dont `Paie_Mai2026.xlsx`,
  `Tableau_codes_horaires_entreprise.xlsx` et `repartition prévoyance &
  mutuelle.xlsx`.
- Elsa renvoie plusieurs fois à des **e-mails** qu'elle nous a adressés (« le
  tableau recap des cp et rtt pour tous les forfait jours », 05/08,
  `_chat.txt:9095` et `:9100` ; « Tu avais vu tous les tableaux recap email »,
  07/08, `_chat.txt:9151`). **Le connecteur Gmail n'est pas autorisé dans cette
  session** : ces pièces n'ont pas pu être vérifiées, et elles portent peut-être
  déjà une partie des réponses ci-dessus.

---

## Deux dossiers déposés dans `data/` le 08/08

53 fichiers, rangés selon `backend/scripts/data_organize/convention.py`. Le
détail par fichier n'a pas sa place ici : tout est sous `data/`, gitignoré.

### « MBC 2 » — 46 fichiers, le classeur de paie de Gaëlle

Rangés en `data/mbc/` : compteurs (JTC, contingent, journée de solidarité,
fractionnement, CET, reporting CP), comptabilité (tableaux de charges, journal
de paie, paiements, mutuelle), référentiel (CSE, NAO, solde de tout compte,
saisie sur salaire, tableaux de suivi CDD / titre de séjour / visite médicale),
variables, calendriers.

**#2 — Soldes JTC : réglé.** `data/mbc/compteurs/suivi-jtc-2026-acquisition.xlsx`,
onglet « Acquisition JTC » : **59 salariés**, soldes au 01/01/2026 — 46 à 3 JTC,
7 à 2, 3 à 1, 3 à 0. Le solde se décompose en une part « Direction
(positionnés) » et une part « Salarié », ce que la note de cadrage ne disait
pas ; le code de rubrique Quadratus est `.JT2`. Extrait en
`data/mbc/compteurs/jtc-2026-soldes.csv`.
**Réserve** : 59 lignes pour 75 salariés en poste, écart non expliqué. À
confirmer avant de charger, sous peine de mettre à 0 des gens qui ont des droits.

**#3 — Onglet « détail absences » : réglé.** C'est le second onglet du même
classeur. 61 lignes, colonnes Maladie, A.T., Maternité/Paternité, Congés P.,
Autres absences, ½ temps thérapeutique, total 2025 en heures puis en jours.
Il répond à « quelles absences comptent » : toutes, hors heures normales,
complémentaires et supplémentaires.

**#4 — Prorata : confirmé par la formule, plus seulement par le texte.** La
colonne G du classeur calcule `(3 / 365) × (365 − jours d'absence)`, arrondie
par `ROUNDDOWN`. Le prorata porte sur **toute** l'absence, les 30 jours ne sont
qu'un seuil de déclenchement. Vérifié sur les trois salariés concernés en 2025 :
124,09 j → 1 JTC, 55,49 j → 2, 57,01 j → 2 ; la lecture « franchise » aurait
donné 2, 2 et 2. La lecture stricte retenue dans EYWAI est la bonne.

**Un conflit laissé en l'état** : deux calendriers MBC 2026 différents, 9,3 Mo
daté du 01/07 contre 1,4 Mo du 06/07 déjà rangé. Aucun n'écrase l'autre, le
nouveau est parqué en `calendrier-2026-version-01-07.xlsx`.

### « Avenants MAJI » — 7 trames de contrat

Rangées en `data/_modeles/contrats/` : un modèle n'est la donnée d'aucune
société. Trois CDI (non cadre, non cadre au forfait, cadre au forfait), un CDD,
deux avenants de renouvellement de CDD, un avenant de passage en CDI.

**Le dossier dit MAJI, les sept documents portent l'en-tête COMITECH** — RCS,
SIRET, siège de Belley, et la convention collective de la **Plasturgie** à
l'article 1. Soit ce sont les modèles Comitech et le dossier est mal nommé, soit
ce sont des trames de groupe à re-siglaliser société par société. **Question
ouverte** : tant qu'elle n'est pas tranchée, ne pas les proposer comme trame par
défaut, un CDI Cartol sorti sur une base Plasturgie serait faux.

Ils donnent en revanche une source écrite à trois règles que le moteur applique
déjà sans pouvoir les justifier : pas de période d'essai au passage en CDI,
reprise intégrale des droits et de l'ancienneté du CDD, et deux renouvellements
de CDD au maximum.

### Ce que le rangement a changé dans le code (suite en fin de document)

`convention.py` ne savait classer que 28 de ces 46 fichiers. Trois ajouts, dans
le seul module qui décide « quel document va où » :

- une rubrique **`comptabilite`**, qui existait déjà sur le disque pour
  Colorplast sans être déclarée ;
- des **dossiers décisifs** (`CSE`, `Charges`, `Solde de tout compte`…) qui
  l'emportent sur le nom du fichier — sans quoi `CSE/feuille de présence.xlsx`
  part en pointages sur le mot « présence » ;
- une poignée de mots-clés : journal de paie, mutuelle, certificat de travail,
  saisie-arrêt, convocation, carence, heures par jour.

Résultat : 46 fichiers sur 46 classés, zéro inclassable.

---

## Première connexion à net-entreprises, 08/08

Les identifiants reçus en photo le 07/08 ont été testés sur **MBC**. Trois
constats, dont deux qui changent des décisions prises la veille. Détail et
identifiants dans `data/_acces/net-entreprises.md`, gitignoré.

### Le compte n'est pas mono-société : il en couvre quatre

C'est un compte **tiers-déclarant** qui dépose déjà les DSN de **MBC, Comitech,
MAJI et Colorplast**. La question posée à Elsa le 07/08 à 14:48 — « a-t-on déjà
un compte MAJI habilité sur les 7 SIREN ? » — trouve donc sa réponse : **4 sur
7**.

Il ne reste que **Cartol, LEWIS et Zone 404**, et la bonne demande n'est plus
« quatre comptes de plus » mais « étendre les habilitations de celui-ci ».
Les identifiants Comitech et Colorplast reçus séparément font sans doute double
emploi.

**À éclaircir** : un profil **MECELEC INDUSTRIES** figure dans la liste des
utilisateurs du compte. Cette entité n'est aucune des sept sociétés.

### Le portail ne donne pas les taux de prélèvement à la source

C'est la correction importante, et elle est solide : vérifiée deux fois, sur
deux échéances (juin et juillet), par deux chemins, en lisant la structure des
pages et pas seulement leur rendu.

Sur l'écran de détail d'une déclaration, tous les retours — CRM identité,
contrôles, URSSAF, AGIRC-ARRCO, prévoyance et surtout **DGFiP « Données
nominatives »** — ne sont que du **texte statique**. Aucun lien. La ligne qui
porte les taux PAS ne s'ouvre pas.

Trois fausses pistes fermées au passage : le bouton « Télécharger au format
PDF » du certificat de conformité n'ouvre qu'une pop-up de texte brut ; la page
« Gestion des retours TPT » concerne le **Temps Partiel Thérapeutique**, pas un
routage des retours ; et « BIS Régime général » renvoie au même tableau de bord.
Aucune gestion d'API ni de certificat n'existe dans ce compte.

Le point **#31** supposait que l'accès au portail suffirait. Il ne suffit pas,
et scripter une connexion n'y changerait rien : le fichier n'est nulle part.

**Restent deux voies, et une seule est courte :**

1. **Cegid.** Les CRM y arrivent déjà — c'est précisément pour ça que le portail
   ne les expose pas. Elsa nous apporte les clés API Cegid mi-août, et
   `pas_rates/application/ingest.py:21` sait déjà lire un CRM.
2. **L'API DSN de net-entreprises**, souscription hors portail plus certificat
   cachet serveur. Des semaines. Plan B.

### Deux choses à faire remonter à Elsa

- **Ajouter Cartol, LEWIS et Zone 404 ne se fait pas depuis ce compte.** Aucun
  écran de rattachement d'un nouveau SIREN côté tiers-déclarant ; la démarche
  part de l'entreprise cliente. C'est elle qui doit la lancer.
- **Une entité nommée MECELEC INDUSTRIES est administrateur du SIRET de Mont
  Blanc Composite** et voit le même tableau de bord que Gaëlle. Elle n'est
  aucune des sept sociétés. À confirmer comme voulu — c'est un droit
  d'administration sur les déclarations sociales de MBC.

### Ce qui a été vérifié au passage

- **Taux AT/MP 2026 de MBC : 3,14 %** (code risque 252HK, décision du
  12/12/2025). EYWAI porte exactement la même valeur, `companies.taux_at_mp`.
  Rien à corriger.
- **Les DSN de juin et juillet sont déposées et conformes.** Le point #20 visait
  leur absence *sur le Drive*, pas leur dépôt : la demande à Elsa reste valable,
  mais elle porte bien sur le partage, pas sur une déclaration manquante.
- La DSN de juin a été **rejetée non conforme au premier dépôt** le 07/07 à
  13:14, puis acceptée huit minutes plus tard. Sans conséquence, mais c'est le
  genre d'aller-retour qu'un dépôt automatisé éviterait.
- 76 salariés déclarés chez MBC en juin, contre 75 en poste dans EYWAI et 59
  lignes dans le fichier JTC. Trois chiffres, trois périmètres.

Restent non testés : les accès Comitech et Colorplast.
