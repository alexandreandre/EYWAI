# Suivi des périodes d'essai — design

Point #28 de `docs/afaire.md` : « Suivi des périodes d'essais, pouvoir le cocher,
quelque part, même après la création. Bien paramétrable. Pour l'instant, elsa ne
l'a pas trouvé. »

Date : 5 août 2026.

## Constat

La fonctionnalité existe déjà en grande partie : carte « Période d'essai » sur la
fiche salarié, badge dans l'en-tête, colonne « Essai J-x » dans la liste, relance
e-mail à J-15, filtre `?filter=trial_ending`. Elsa ne l'a pourtant pas trouvée,
et la production explique pourquoi.

**Aucun salarié n'a de période d'essai renseignée** : 0 sur 241 actifs, dans les
sept sociétés. Le champ `employees.periode_essai` (jsonb) est vide partout.

**La carte est masquée quand il n'y a rien à afficher.** Sa condition d'affichage
(`EmployeeDetailTrialPeriodCard.tsx`) exige une période d'essai déjà renseignée
ou une embauche de moins de 90 jours. Deux salariés sur 241 remplissent cette
condition. Pour les 239 autres, il n'existe aujourd'hui **aucun moyen d'activer
le suivi après la création** — ce que demande le point #28, mot pour mot.

**Le paramétrage est écrit dans le code** : « CDI 2 mois, CDD 1 mois,
stage et alternance exclus » dans `CreateEmployeeForm.tsx`, « alerte à 15 jours »
dans `trial_period_shared.py`.

### Le calcul de la date de fin est faux d'un jour

`compute_trial_period_end` fait `hire_date + N mois`. Une période d'essai de deux
mois débutant le 1er mars y finit le 1er mai, alors qu'elle expire le 30 avril à
minuit : le décompte va de quantième à quantième et la période s'achève la veille
du quantième correspondant. Le frontend (`computeTrialPeriodEndDate`) reproduit
le même décalage.

Sans données en base, ce bug n'a jamais produit d'effet. Il en produirait dès la
première saisie : une rupture notifiée le jour affiché comme dernier jour serait
prononcée hors période d'essai, donc requalifiée en licenciement sans cause
réelle et sérieuse.

La correction naïve — retirer un jour — est fausse pour les embauches de fin de
mois : `31 janvier + 1 mois - 1 jour` donne le 27 février, alors que la période
expire le 28. Quand le quantième n'existe pas dans le mois d'arrivée, la période
court jusqu'au dernier jour de ce mois.

### Contrainte de données : deux catégories, pas trois

Le barème légal distingue ouvriers/employés (2 mois), agents de maîtrise et
techniciens (3 mois) et cadres (4 mois). La base ne connaît que `statut` =
`Cadre` ou `Non-Cadre` : la maîtrise est noyée dans les non-cadres. Le barème
s'appuiera donc sur les deux catégories réellement disponibles, à charge pour
Elsa d'ajuster au cas par cas quand la convention l'impose. On ne fabrique pas
une catégorie que le SIRH ne porte pas.

Répartition en production : CDI Non-Cadre 187, CDD Non-Cadre 26, CDI Cadre 25,
Apprentissage 3.

## Décisions

| Sujet | Décision |
|---|---|
| Périmètre | Fiche salarié débloquée **et** page de suivi dédiée |
| Paramétrage | Barème par société, pré-rempli aux valeurs légales |
| Stock existant | Aucun backfill, rattrapage manuel assisté |
| Suivi | Confirmation **et** renouvellement effectif, tracés |
| Alertes | In-app et e-mail, destinataires RH réels |
| Stockage | Table dédiée `trial_periods`, le jsonb est abandonné |

Le stockage mérite une justification. Le jsonb étant vide à 100 %, la migration
de données coûte zéro aujourd'hui — il n'y a rien à migrer. Ce ne sera plus vrai
dans six mois avec cent périodes saisies. Une période d'essai est par ailleurs un
objet daté à cycle de vie (début, fin, renouvellement, issue) dont on veut
l'historique : le renouvellement doit être notifié avant le terme, et une rupture
contestée se défend avec des dates opposables. Un jsonb ne porte ni contrainte,
ni index, ni trace de qui a fait quoi.

**Le backfill est écarté** parce que les données ne s'y prêtent pas : LEWIS
compte 33 embauches au même mois (septembre 2025), qui sont une reprise de
données et non 33 recrutements. Un barème appliqué en masse y créerait 33
périodes d'essai fictives. Environ 17 salariés embauchés depuis avril 2026 ont
en revanche une période potentiellement encore en cours, non suivie : c'est eux
que le rattrapage vise.

## Architecture

### Table `trial_periods`

Source unique de vérité. Colonnes :

- `id`, `company_id`, `employee_id`
- `start_date` — date de début, initialisée à la date d'entrée, modifiable
  (un contrat peut débuter après l'embauche déclarée)
- `duration_value`, `duration_unit` (`jours` | `semaines` | `mois`)
- `renewal_allowed` — le renouvellement est-il ouvert par la convention
- `renewed_at`, `renewal_duration_value`, `renewal_duration_unit`,
  `renewed_by` — le renouvellement effectivement décidé
- `end_date` — date calculée, colonne réelle
- `status` — `en_cours` | `confirmee` | `rompue`
- `confirmed_at`, `confirmed_by`
- `created_at`, `updated_at`, `created_by`

Contraintes : `duration_value > 0`, unités dans la liste fermée, `end_date >=
start_date`, et un index unique partiel garantissant **une seule période active
par salarié** (`where status = 'en_cours'`) — ce qui laisse une réembauche créer
la sienne. RLS activée dès la création de la table, conformément au chantier de
sécurité du 4 août.

`end_date` est une colonne réelle et non générée : le calcul relève du droit du
travail (veille du quantième, dernier jour du mois quand le quantième n'existe
pas, prolongation par le renouvellement) et a sa place dans le domaine Python où
il se teste cas par cas. Une seule commande applicative l'écrit, ce qui borne le
risque de désynchronisation.

### Calcul de la date de fin

Fonction pure dans le domaine, remplaçant `compute_trial_period_end` :

- unité `jours` ou `semaines` : `start + N - 1 jour`
- unité `mois` : quantième du N-ième mois suivant, moins un jour ; si ce
  quantième n'existe pas, dernier jour du mois d'arrivée
- renouvellement : la durée de renouvellement s'ajoute à la fin initiale, selon
  les mêmes règles, en repartant du lendemain

Cas de test obligatoires : 1er mars + 2 mois → 30 avril ; 31 janvier + 1 mois →
28 février ; 31 janvier + 1 mois en année bissextile → 29 février ; 16 mars +
1 mois → 15 avril ; 2 mars + 8 jours → 9 mars ; 1er mars + 2 mois renouvelés
2 mois → 30 juin.

### Barème société

Dans `companies.settings.periode_essai`, comme le forfait RTT :

- lignes `type de contrat × statut → durée, unité, renouvellement autorisé`,
  pré-remplies aux valeurs légales (CDI Non-Cadre 2 mois, CDI Cadre 4 mois)
- `alerte_jours`, remplaçant la constante `TRIAL_REMINDER_DAYS`
- types de contrat exclus (apprentissage, professionnalisation, stage)
- une case « appliquer la règle légale CDD » : un jour par semaine de contrat,
  plafonné à deux semaines si le contrat fait six mois ou moins, un mois au-delà.
  Une durée fixe pour les CDD serait fausse dans la plupart des cas.

La résolution du barème est une fonction pure : contrat, statut et durée de
contrat en entrée, proposition de période d'essai en sortie. Elle propose, elle
n'impose pas — la valeur reste modifiable salarié par salarié.

### API

- `GET /trial-periods` — liste filtrable par statut, pour la page de suivi
- `POST /employees/{id}/trial-period` — créer, à partir du barème ou saisie
- `PATCH /trial-periods/{id}` — corriger durée, unité, date de début
- `POST /trial-periods/{id}/confirm` — confirmer l'embauche
- `POST /trial-periods/{id}/renew` — enregistrer un renouvellement

L'endpoint de confirmation existant (`PATCH /employees/{id}/trial-period/confirm`)
est rebranché sur la table.

### Frontend

**Page « Périodes d'essai »**, dans la navigation RH, en trois sections :

1. *En cours* — avec la date de fin et le J-x
2. *À confirmer* — échéance atteinte ou dépassée, action de confirmation directe
3. *À qualifier* — salariés actifs sans période d'essai dont l'embauche date de
   moins de huit mois, avec application du barème en un clic, unitaire ou par
   multi-sélection. Huit mois est la durée maximale légale d'une période d'essai
   (cadre, quatre mois, renouvelée une fois) : au-delà, il n'y a plus rien à
   suivre et la section resterait encombrée d'anciens salariés

C'est l'endroit qu'Elsa n'a pas trouvé.

**Carte de la fiche salarié** : visible pour tout salarié actif, quelle que soit
son ancienneté. L'interrupteur d'activation devient le point d'entrée réclamé par
le « pouvoir le cocher, même après la création ». S'y ajoutent l'enregistrement
d'un renouvellement (date et durée, qui repousse la fin et donc l'alerte) et
l'affichage de qui a confirmé, et quand.

**Badge d'en-tête, colonne de liste, filtre `trial_ending`** : rebranchés sur la
nouvelle source, comportement inchangé.

**Réglages société** : bloc d'édition du barème.

### Alertes

Le délai devient paramétrable. La relance e-mail groupée existante
(`hr_deadline_reminders`) est alimentée par la table et continue de partir aux
utilisateurs RH réels de la société — validé. Le compteur remonte dans les tâches
RH du tableau de bord.

### Contrats générés

`format_periode_essai` (`pdf/helpers.py`) alimente le libellé de la période
d'essai dans les contrats PDF et DOCX en lisant le jsonb. Il doit être rebranché
sur la table, en tenant compte du fait que la génération peut précéder la
création de la période. Le repli existant — « conformément aux dispositions
légales et conventionnelles applicables » — reste la sortie par défaut.

## Ce qui n'est pas fait

- Aucun backfill, aucune donnée fabriquée
- Pas de reprise d'historique des périodes d'essai passées
- La rupture reste gérée par le module des sorties, où le type
  `fin_periode_essai` existe déjà ; la table se contente d'enregistrer le statut
- Le décompte de la maîtrise à trois niveaux, faute de la donnée en base

## Vérification

Tests unitaires du domaine — calcul de fin (les six cas ci-dessus), résolution du
barème, règle CDD, statuts, éligibilité à la relance. La CI ne bloque que sur
`tests/unit` : les 51 échecs d'intégration préexistants ne jugent pas ce
changement.

Migration à horodatage unique, postérieur à `20260805100000`, appliquée d'abord
sur l'environnement de test.

## Hors périmètre, à traiter à part

En production, ni `PAYSLIP_EMAIL_REDIRECT` ni `EMAIL_FORCE_REDIRECT_TO` ne sont
définis sur le service `sirh-backend` — seul l'environnement de test porte le
garde-fou (`eywaitest@gmail.com`). Les e-mails destinés aux salariés partiraient
donc directement chez eux. Sur 241 salariés actifs, 240 ont une adresse en base,
dont 148 fabriquées et filtrées : environ 92 adresses potentiellement réelles.
La période d'essai n'envoie rien au salarié, donc ce chantier ne l'aggrave pas,
mais la variable reste à poser sur Cloud Run.
