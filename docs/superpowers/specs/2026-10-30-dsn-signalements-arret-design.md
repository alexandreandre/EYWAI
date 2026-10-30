# Signalements DSN d'arrêt et de reprise (chantier 2, lot A)

Date : 30/10/2026. Feuille de route du 30/10, chantier 2 (décision D2) : sans Quadra, plus personne ne signale un arrêt ni une fin de contrat. Ce lot couvre l'arrêt (nature 04) et la reprise anticipée (nature 05). La fin de contrat (FCTU, nature 07) est le lot B, conçu à part : il porte le solde de tout compte (blocs 50, 51, 62, 63…), bien plus lourd.

## Ce que disent les textes

Cahier technique DSN 2026.1 (`docs/audit-maji-2026/sources/dsn-cahier-technique-2026.1.txt`) :
- § 5.3, nature 04 : « Le signalement d'évènement doit être transmis dans les 5 jours après la prise de connaissance de l'évènement par l'employeur, sauf dans un cas de subrogation ou de décalage sur le mois suivant de la prise en compte en paie où l'émission du message peut être concomitante à l'envoi de la DSN mensuelle. »
- § 5.4, nature 05 : « n'est à émettre qu'en cas de reprise anticipée par rapport à la date prévisionnelle de l'arrêt et doit alors être transmis au plus tard dans les cinq jours ouvrables qui suivent la reprise du travail. »
- § 2.5.1 : les données identifiantes du signalement (NIR, nom, prénoms, naissance, numéro et date de début du contrat) doivent être celles de la dernière DSN mensuelle déposée, sinon le signalement n'aboutit pas.
- Tableau des usages : un signalement 04 ou 05 ne porte que les blocs 10, 20.05, 20.07, 21.06, 21.11, 21.15, 21.30, 21.40, 21.60 et 90, et dans chacun une petite partie des rubriques (par exemple 40.001, 40.009, 40.019 seulement ; 20.05.005, 20.05.008 et 20.05.010 sont interdites).
- 60.012 (date de l'accident) : obligatoire pour les motifs 04, 05, 06, interdite sinon (CCH-11) ; égale ou postérieure au début du contrat (SIG-14).

Guide net-entreprises « Pour une bonne gestion des arrêts de travail dans la DSN » (fiches 01/2019) : un signalement pour chaque arrêt initial d'au moins un jour ; « les prolongations ne doivent pas faire l'objet d'un signalement mais alimentent vos DSN mensuelles ».

## Ce que fait Martine

1. **Liste « Signalements d'arrêt à faire »**, sur la page des exports, carte DSN. Une ligne par arrêt à signaler : salarié, motif, du / au prévu, connu le, **« à déposer avant le … »** (en rouge une fois dépassé), et deux boutons : « Fichier d'essai » et « Fichier réel ». Les signalements déjà générés restent listés, avec leur date.
2. **Génération** d'un fichier `.dsn` de nature 04 (ou 05), téléchargé puis déposé à la main sur net-entreprises (l'API n'est qu'une coquille, décision 2 du 30/10). Après génération : « Déposez-le sur net-entreprises.fr avant le … ».
3. **Rien à faire pour une prolongation** : elle part dans la DSN mensuelle, comme aujourd'hui.

### Quels arrêts, et pour quand

- Un arrêt = une période de `periodes_d_arret` (arrêts validés de type maladie, maternité, paternité, AT, maladie professionnelle, accident de trajet ; une prolongation sans reprise prolonge la période). Le signalement 04 porte le début de la période ; il est fait quand un export 04 existe pour ce salarié, ce motif et ce début.
- Connu le : la date de saisie de la première demande de la période (`created_at`).
- À déposer avant :
  - sans subrogation : connu le + 5 jours (jours calendaires : plus strict que les 5 jours ouvrés de net-entreprises, et simple à suivre) ;
  - en subrogation : l'échéance de la DSN mensuelle du mois de connaissance (le 5 ou le 15 du mois suivant selon l'effectif, règle déjà suivie pour les paiements d'organismes).
- Reprise anticipée (05) : quand la fin réelle de la période est avant la fin prévue déclarée dans le dernier signalement 04 (gardée dans les paramètres de l'export), et qu'aucun 05 n'existe. À déposer avant : reprise + 5 jours ouvrables (dimanches sautés, jours fériés comptés : le plus strict).
- Point de départ : seuls les arrêts commencés après le dernier mois de paie repris d'un autre logiciel (bulletins `origine = importe`). Avant, le signalement était l'affaire de l'ancien logiciel. Chez Colorplast et Comitech, cela donne les arrêts commencés depuis le 01/10/2026.

### Le fichier

- En-tête : `build_envoi` (essai ou réel, comme la mensuelle), `build_entreprise`, `build_etablissement`, contacts ; S20.G00.05.001 = 04 ou 05, 05.002 = 01, 05.003 = 11, 05.004 = 1.
- Individu et contrat : les mêmes valeurs que la DSN mensuelle (mêmes fonctions de lecture de la fiche et de la reprise, notamment le numéro de contrat repris de l'ancien logiciel), filtrées par la liste des rubriques permises pour la nature (tableau des usages, rangé dans le code).
- Bloc 60 : les règles de `blocs_arret` (dernier jour travaillé, fin prévisionnelle, subrogation et IBAN de l'employeur) ; en 04, la date de l'accident (60.012) pour les motifs 04, 05, 06 ; en 05, la date et le motif de la reprise (60.010, 60.011), sans subrogation (interdite en 05).
- Date de l'accident : Martine n'a pas de champ. On prend le premier jour de l'arrêt, que la DSN mensuelle traite déjà comme le jour de l'accident, travaillé. Juste pour un accident du travail ou de trajet ; pour une maladie professionnelle, la première constatation médicale peut être plus ancienne : limite connue, un champ sera ajouté au premier cas.

### Verrou

Le fichier d'essai se génère toujours. Le fichier réel suit un verrou à lui, `SIGNALEMENTS_DEPOSABLES` (dans `etat_conformite.py`), fermé au départ : il s'ouvre sur la décision d'Alexandre, une fois un fichier d'essai passé à DSN-VAL sans erreur bloquante et accepté en mode test sur net-entreprises. Il ne dépend pas du verrou de la mensuelle : un arrêt n'attend pas le 15.

### Ce qui bloque la génération

Une fiche sans NIR (ni numéro technique temporaire), sans nom, prénoms ou date de naissance, un contrat sans date de début ni numéro, une subrogation sans IBAN de l'employeur : la génération s'arrête et dit le champ à compléter, sur la fiche ou dans les réglages DSN. Aucune valeur inventée.

## Découpage

- `dsn_export/domain/usages_signalement.py` : rubriques permises par nature (04, 05), et le filtre d'un bloc.
- `dsn_export/domain/signalements.py` (fonctions pures) : arrêts à signaler, reprises anticipées, dates limites.
- `dsn_export/application/signalement_builder.py` : le fichier d'un signalement.
- `exports` : type d'export `dsn_signalement_arret` (génération, historique avec paramètres, essai, verrou) et la liste des signalements à faire.
- Frontend : la carte « Signalements d'arrêt » et son appel d'API.

## Tests

- Domaine : prolongation sans signalement ; deux arrêts séparés par un jour travaillé ; date limite avec et sans subrogation ; arrêt déjà signalé ; reprise anticipée et reprise à la date prévue ; arrêt d'avant le point de départ ignoré.
- Fichier : nature 04 et 05 ; aucune rubrique interdite (bloc 50, 51, 78, 81, rubriques 40.007, 30.005…) ; 60.012 pour un accident du travail, absente pour une maladie ; subrogation et IBAN.
- DSN-VAL : un fichier d'essai tiré d'un vrai arrêt du test (lecture seule), 0 erreur bloquante.
- Frontend : la date limite et sa couleur ; les boutons d'essai et réel.

## Lot B : fin de contrat (FCTU, nature 07)

Cahier technique 2026.1, § 5.2 : le signalement « doit être transmis dans les cinq jours ouvrés qui suivent la survenance de la fin du contrat de travail » ; il porte « l'ensemble des informations relatives à la fin d'un contrat de travail, y compris les données du mois en cours calculées dans le cadre du solde de tout compte » ; ses données se reportent ensuite dans la DSN mensuelle. Rubriques propres : S21.G00.62.020 (mois du solde de tout compte, au 1er du mois) et S21.G00.50.020 (01 : éléments de ce mois).

- **Contenu** : la DSN du mois de sortie limitée au salarié (`generate_dsn_file` avec son seul identifiant, les mêmes règles que la mensuelle), passée en nature 07, filtrée par les rubriques permises en fin de contrat (tableau des usages : 227 rubriques ; les blocs d'établissement 20, 22, 23 en sortent), avec 62.020 et 50.020 = 01. Pas de 62 dans le mois (sortie non saisie) : la génération s'arrête et le dit.
- **Quelles fins** : les sorties saisies (hors annulées) et les CDD à leur terme, terminés après le dernier mois repris de l'ancien logiciel ; celles des 31 jours à venir s'affichent aussi, pour prévenir. À déposer avant : fin + 5 jours ouvrés (samedis et dimanches sautés, fériés comptés : le plus strict).
- **Prêt** quand le bulletin du mois de sortie existe ; sinon la ligne dit « bulletin de sortie à calculer d'abord » et ne se génère pas.
- **Historique** : même type d'export que les arrêts (`dsn_signalement_arret`, nature 07 dans les paramètres) : pas de nouvelle migration.
- **Verrou** : le contenu vient du constructeur de la mensuelle ; le fichier réel s'ouvre après un essai tiré d'une vraie sortie passé à DSN-VAL sans anomalie bloquante.
- **Hors lot B** : un FCTU qui porte aussi M-1 (50.020 = 02), quand la DSN de M-1 n'est pas encore déposée : la règle net-entreprises est alors de déposer la DSN de M-1 dans le même délai ; « annule et remplace » après un rappel.

## Hors du lot

- FCTU (lot B), puis signalement « annule et remplace » d'un 04 déjà déposé (une erreur se corrige aujourd'hui sur net-entreprises).
- Temps partiel thérapeutique : il se saisit sur net-entreprises (guide net-entreprises).
- Plafond des IJ d'accident du travail pour les arrêts dès le 01/11/2026 (décret 2026-909) : moteur de paie, fait à part avec le filet au centime.
