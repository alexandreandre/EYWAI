# État des lieux SI RH — audit technique des retours de réunion

**Date :** 26 juillet 2026
**Objectif fixé :** plateforme totalement opérationnelle en septembre 2026
**Périmètre :** 22 actions issues de la réunion de présentation + les points de contexte associés
**Méthode :** chaque action a été confrontée au code réel du dépôt. Ce document distingue
explicitement ce qui est **vérifié dans le code**, ce qui est **inféré**, et ce qui **reste à
confirmer** par une requête en base ou une information terrain.

---

## 1. Résumé exécutif

Sur les 22 actions listées :

| Catégorie | Nombre | Commentaire |
|---|---|---|
| Saisie / config / organisation — **zéro ligne de code** | 9 | Peut démarrer immédiatement, en parallèle |
| Fonctionnalité **déjà présente**, mal identifiée ou non paramétrée | 4 | Risque de développer du doublon si on ne vérifie pas |
| **Bugs** à corriger | 4 | 3 causes racines identifiées, 1 à instrumenter |
| **Développements** neufs | 5 | Dont 1 gros (BDES) et 1 sujet RGPD (env. de test) |

**La charge de dev nette est d'environ 25 à 35 jours.** Il reste ~5 semaines avant septembre.
C'est tenable, à trois conditions :

1. **La BDES démarre maintenant.** C'est le seul poste à 8-10 jours ; tout le reste est du
   court terme. Si elle démarre en août, elle ne sera pas prête.
2. **L'environnement de test est redimensionné** en copie pseudonymisée plutôt qu'en copie
   des données réelles (cf. §4.1).
3. **Les 9 actions de saisie ne m'attendent pas.** Elles ne dépendent d'aucun développement
   et constituent le chemin critique réel de plusieurs chantiers (les e-mails bloquent la
   conformité RGPD, les BIC bloquent les virements).

> **Le point le plus important de ce document n'est pas dans la liste de la réunion.**
> Trois problèmes structurels ont été trouvés pendant l'audit et n'ont été détectés par
> personne en séance, parce qu'ils sont silencieux : ils ne produisent ni erreur, ni alerte.
> Voir §2.

---

## 2. Les découvertes qui changent le plan

Ces quatre points n'étaient pas dans la liste des actions. Ils sont classés par gravité.

### 2.1 ✅ La notification RGPD de dépôt de document partait dans le vide — corrigé le 26/07

> **Traité.** Cause racine supprimée, garde-fou posé, reprise de l'existant outillée.
> Conception : `docs/superpowers/specs/2026-07-26-suppression-emails-placeholder-design.md`.
> Ce qui reste est une collecte de terrain : **148 salariés actifs sans adresse connue
> nulle part** — ni en base, ni chez Cegid. Détail en fin de section.

**Vérifié.** Tout salarié créé par import DSN recevait une adresse e-mail technique fabriquée :

```
import.prenom.nom.123456@534386495.dsn-import.local
```

*(`mapping.py:512-517`)*

Le domaine `.dsn-import.local` n'existe pas et n'est pas routable. Or la fonction qui notifie
le salarié du dépôt d'un document — l'obligation « coffre-fort électronique » évoquée en
réunion — teste seulement `if email:` avant d'envoyer
*(`employee_document_alerts.py:198`)*. Une adresse placeholder est « vraie » au sens de ce
test. L'envoi part, échoue côté SMTP, et la fonction est explicitement `best effort` :
elle **ne lève jamais d'exception**.

Conséquence : aujourd'hui, déposer un bulletin pour un salarié importé par DSN produit une
notification in-app, un envoi e-mail silencieusement perdu, et **aucune trace d'échec**.
Rien dans l'interface ne distingue « notifié » de « jamais notifié ».

Ce qui rend ce point notable : le suffixe `.dsn-import.local` est **déjà reconnu dans cinq
endroits du code** (détection des salariés orphelins, règles métier `employees`, requêtes
d'import, assistant DSN côté front). Il est connu partout — sauf à l'unique endroit où il
engage la conformité.

**Donc l'action « collecter les adresses e-mail » ne suffit pas.** Il faut aussi un
garde-fou, sinon on croira avoir notifié des salariés qui ne l'ont jamais été, et on n'aura
aucun moyen de savoir lesquels. C'est un demi-jour de dev, et c'est la chose la plus rentable
de toute la liste.

#### Ce qui a été fait le 26/07

L'audit a révélé **deux fabriques d'adresses, pas une** — la seconde étant la plus nocive :
le provisionnement de compte recopiait dans `employees.email` l'adresse technique nécessaire à
Supabase Auth, transformant un identifiant interne en adresse de contact.

Principe retenu, appliqué dans le code : `employees.email` est **l'adresse de contact** de la
personne — réelle ou vide, jamais fabriquée ; l'adresse du compte Auth est un **identifiant
technique**, jamais affiché, aligné sur l'adresse réelle dès qu'elle est connue. Une fiche se
crée complètement sans adresse ; l'adresse s'ajoute ensuite ; la connexion suit.

Cinq correctifs : suppression du placeholder à l'import DSN, arrêt de la recopie au
provisionnement (deux chemins), garde-fou de notification qui refuse une adresse fabriquée et
**journalise l'échec** au lieu de le perdre, synchronisation fiche → compte Auth (inexistante
jusqu'ici), et manifeste d'accès identifiant les personnes par leur fiche salarié plutôt que
par une adresse. 32 tests neufs, suite unitaire à 4056 au vert, aucune régression.

Reprise de l'existant outillée mais **non appliquée** :
`backend/scripts/cleanup_placeholder_emails.py`, lecture seule par défaut, plan JSON nominatif,
`--apply` sous double garde-fou avec sauvegarde préalable. Le plan sorti en production porte
**183 fiches à vider et 85 comptes à réaligner**.

État réel de la donnée, mesuré en production :

| | Total | Adresse fabriquée |
|---|---|---|
| Fiches salarié | 289 | 183 |
| Comptes de connexion | 302 | 250 |

Les 7 fichiers `Config/*/Enrichissement Salarié/*.xlsx` portent bien une colonne `e-mail`,
**mais le gisement est épuisé** : 108 adresses y figurent, 107 sont déjà en base. Une seule
reste à reporter (Lucas CHAMBERT, fiche MBC). Pour les 183 autres, la case est vide chez Cegid
aussi — Cartol a 108 lignes pour 11 adresses, LEWIS 43 lignes et zéro adresse.
**148 salariés actifs sont concernés : c'est une collecte de terrain, pas un sujet technique.**

Deux anomalies relevées, non corrigées faute de savoir quelle valeur est juste :
`malopoulain@orange.fr` est porté par **deux** salariés (Quentin MATHIEU et Malo POULAIN, MBC),
et `athoumanimohamed@29gmail.com` (Athoumani MOHAMED, MBC) a un domaine invalide.

### 2.2 🔴 Les RTT à 10 jours par an sont un défaut, pas un paramétrage Colorplast

**Vérifié.** L'action « vérifier pourquoi certains salariés de Colorplast apparaissent en RTT
alors qu'ils n'en ont pas » a une cause générique :

```python
def resolve_rtt_annual_base(year, policy, ...):
    if policy.rtt_annual_days is not None:
        return float(policy.rtt_annual_days)
    if policy.rtt_use_forfait_jours_formula:  # ...
    if policy.rtt_use_calendar_formula:       # ...
    return RTT_ANNUAL_DAYS_DEFAULT            # ← 10.0
```

*(`absences/domain/rules.py:136-164`, constante `leave_policy.py:16`)*

Une entreprise qui n'a **jamais configuré** ses RTT — `rtt_annual_days` à `None`, aucune
formule activée — retombe sur **10 jours de RTT par an**. Et l'éligibilité individuelle ne
filtre rien : `_rtt_eligible_for_employee` renvoie `True` pour tout le monde dès que la
formule forfait-jours n'est pas activée *(`rules.py:167-175`)*. Il n'existe aucun indicateur
« ce salarié n'a pas de RTT ».

Ce n'est donc pas un problème Colorplast : **c'est le comportement par défaut des 7 structures**.
Colorplast est simplement celle où quelqu'un l'a remarqué.

Le correctif est simple sur le principe (traiter `None` comme « RTT désactivés » et exiger un
paramétrage explicite) mais **il change le comportement de toutes les entreprises** : il faut
d'abord relever la configuration RTT réelle des 7 sociétés, puis corriger, puis vérifier
qu'aucun solde légitime ne disparaît. Compter la vérification, pas seulement le patch.

### 2.3 🟠 Les arrêts de travail de la DSN sont probablement importés en « congé sans solde »

**Partiellement vérifié — à confirmer contre le cahier technique DSN.**

Bonne nouvelle d'abord, qui corrige ma première analyse : la chaîne d'import des arrêts
**existe et est complète**. `build_absence_payload_from_arret` → item d'import de type
`absence` → `_commit_absence` → `create_reconciliation_absence`, qui écrit dans
`absence_requests` avec `status: "validated"` *(`absences/application/commands.py:494-500`)*.
C'est exactement ce que le tableau de bord attend.

Le problème est dans le **mapping des codes**. Le code déclare :

```python
# Motif suspension G00.60 → type absence
SUSPENSION_ABSENCE_MAP = {"01": "sans_solde", "02": "sans_solde", "03": "arret_maladie"}
```

*(`dsn_absence_exit_mapping.py:34-38`, bloc décrit comme « Suspension » dans `rubriques.py:181`)*

Or dans la DSN Cartol de janvier, le bloc `S21.G00.60` contient **16 occurrences, dont 14 avec
le motif `'01'`**, et la forme des données ne ressemble pas à une suspension de contrat :

```
S21.G00.60.001,'01'          ← motif
S21.G00.60.002,'21012026'    ← dernier jour travaillé
S21.G00.60.003,'23012026'    ← fin prévisionnelle
S21.G00.60.004,'01'          ← lu comme « motif » par le code
S21.G00.60.005,'22012026'    ← date de subrogation
```

Les rubriques `.005` à `.008` (présentes 10 fois) portent des dates et des coordonnées
bancaires de subrogation, et `.010` une date de reprise. **Un bloc de suspension de contrat ne
transporte pas de subrogation.** Tout indique le bloc « arrêt de travail », dans lequel `.004`
est l'indicateur de subrogation (01/02) et non un motif.

Si c'est confirmé, alors `map_suspension_to_absence('01')` renvoie `sans_solde`, et **14 arrêts
maladie de janvier deviennent des congés sans solde** — faux pour l'absentéisme, faux pour le
maintien de salaire, faux pour les attestations de salaire.

À noter : le bloc `S21.G00.41`, que le code désigne comme le bloc « arrêt travail »
*(`rubriques.py:175-179`)*, ne contient dans ce fichier que `.001` (une date) et `.012` (un
SIRET) — **ni motif, ni date de fin**. La voie « arrêt » du code ne peut donc rien produire ici.

**Action : confirmer les deux blocs contre le cahier technique DSN avant de toucher au
mapping.** C'est le prérequis de l'action « double-checker les données DSN avant la mise en
production », et c'est plus important que la vérification des NIR.

### 2.4 🟠 La masse salariale du tableau de bord ne sera jamais juste en l'état

**Vérifié.** Le chiffre affiché est la somme des salaires **contractuels** des salariés actifs,
pas la masse salariale réelle :

```python
salary_by_service[sk] += _salaire_brut_valeur(e.get("salaire_de_base"))
# ...
masse_salariale_source="contractual_base"
```

*(`dashboard/application/service.py:534` et `:600`)*

Le code l'assume : il expose littéralement `masse_salariale_source = "contractual_base"`. Sont
donc exclus les primes, les heures supplémentaires, les absences, les entrées et sorties en
cours de mois, les régularisations. Second effet : `_salaire_brut_valeur` renvoie `0.0` si
`salaire_de_base` n'est pas un dictionnaire `{valeur: …}` *(`service.py:280-288`)* — tout
salarié au format non conforme **pèse zéro** dans le total, sans avertissement.

Les bulletins de janvier à juin sont pourtant en base et exploitables
(`fetch_payslips_by_company` les charge déjà pour un autre graphique).

**Point de vigilance organisationnel :** la réunion précise que *« les directeurs auront le
même niveau d'accès aux données »*. Un indicateur de masse salariale faux, exposé à des
directeurs qui le compareront à leur propre suivi budgétaire, coûtera plus cher en crédibilité
que le développement lui-même. C'est à corriger **avant** d'ouvrir les accès directeurs, pas après.

---

## 3. Les 22 actions, chantier par chantier

### 3.1 Accès et utilisateurs

> **✅ Section traitée le 26/07/2026.** Résultats ci-dessous, vérifiés en base de production.

| # | Action | État | Charge |
|---|---|---|---|
| 1 | Accès de Vanessa sur toutes les filiales | ✅ **Déjà corrigé le 22/07** — reconnexion suffit | — |
| 2 | Identifiants à Gaëlle et Vanessa via WhatsApp | ✅ **Débloqué** — identifiants prêts | — |
| 5 | Ajouter Robin sur Zone 404 | ⏸️ En attente d'infos | 15 min |
| — | 🔴 **Accès révoqués toujours effectifs** (découvert) | ✅ Corrigé + 5 tests + prod nettoyée | fait |

**Vanessa — le problème s'était résolu tout seul, quinze minutes trop tard.** Le préflight du
26/07 sort **50 no-op, 0 create, 0 conflit** : manifeste et production sont alignés. La
chronologie relevée en base explique le signalement en réunion :

| Heure (22/07) | Événement |
|---|---|
| 12:28 | Provisioning passe 1 → MAJI réactivé, Zone 404 créé |
| **13:11** | **Connexion de Vanessa** → elle ne voit que **2 filiales sur 7** |
| 13:26 | Provisioning passe 2 → MBC, Cartol, LEWIS, Colorplast, Comitech créés |
| depuis | aucune reconnexion |

Ses 7 accès sont actifs en `role: admin`. **Aucune action nécessaire, seulement une reconnexion.**

Elle possède deux profils : le compte actif (`d225b179`) et un doublon
`vamate@maji-invest.fr` jamais utilisé, dont l'accès MAJI est révoqué — à ne pas utiliser
pour se connecter.

Le script `backend/scripts/provision_access_matrix.py` est en lecture seule par défaut et
produit un plan JSON ; `--apply` exige la référence de projet exacte et une confirmation
production.

### 🔴 Découverte — la révocation d'accès n'avait aucun effet

**Vérifié, corrigé.** Le provisioning écrivait bien `user_company_accesses.is_active = false`,
mais `get_current_user` chargeait les accès **sans jamais filtrer cette colonne**
*(`core/security.py:156`)*. La révocation était donc purement cosmétique : elle changeait le
plan de provisioning et le classeur Excel, pas les droits réels.

En reproduisant la requête de session, Gaëlle Bouali obtenait **les 7 entreprises** alors que
5 étaient révoquées depuis le 22/07. Et ce n'était pas qu'un menu trop garni : en passant
l'en-tête `X-Active-Company`, la session basculait réellement sur Cartol avec `role = rh` —
soit un accès effectif aux bulletins et données personnelles de MBC, Cartol, LEWIS, Colorplast
et Comitech.

L'indice de l'oubli : la migration du 22/07 crée un index
`idx_uca_user_active ON (user_id, is_active)` — l'index existe pour ce filtre exact, qui
n'avait jamais été écrit.

**Correctif** (TDD, 5 tests écrits d'abord dont 4 en échec) : filtre `.eq("is_active", True)`
avec repli défensif si la migration n'est pas appliquée, dans le style déjà utilisé pour
`must_change_password`. Vérifications préalables : colonne `NOT NULL DEFAULT true` et
**0 ligne NULL sur 319** (313 actives / 6 révoquées), donc le filtre ne retire que les accès
censés l'être. **Suite complète : 4250 passés, 0 échec.**

**Mitigation immédiate appliquée en production** (avant déploiement du correctif) : suppression
des 5 lignes révoquées de Gaëlle après sauvegarde. Table passée de 319 à 314 lignes ; il ne
reste qu'un accès révoqué, celui du doublon inutilisé de Vanessa. Gaëlle a désormais exactement
MAJI + Zone 404 en production — périmètre depuis révisé dans le manifeste, voir plus bas.

**Détail structurant à connaître :** les permissions sont **strictement par entreprise**. Il
n'existe aucun périmètre « toutes sociétés » : l'évaluation refuse l'accès dès que
`employee.company_id != grant.company_id` *(`access_control/domain/scopes.py:63-64`)*, avec une
logique *fail-closed*. Un administrateur multi-filiales est donc N accès distincts, à
re-provisionner à chaque nouvelle société. C'est sain pour la sécurité, mais cela signifie que
toute nouvelle filiale demandera un passage par le manifeste.

**Gaëlle — le périmètre cible a changé, et la production ne le reflète pas encore.** Le
manifeste la déclare désormais **`rh` sur MBC, Cartol, LEWIS, Colorplast et Comitech**, et non
plus sur MAJI et Zone 404. C'est un choix assumé, postérieur à la réunion.

En production elle a aujourd'hui l'inverse : MAJI + Zone 404, après la suppression des 5 lignes
révoquées. Son entrée portant `sync_accesses: true`, le prochain `--apply` du provisioning
**créera les 5 accès opérationnels et désactivera MAJI et Zone 404**. C'est le comportement
attendu — mais il faut le savoir avant de lancer la commande, car le préflight affichera 5
créations et 2 désactivations là où les sections précédentes de ce document annonçaient
« 50 no-op, 0 create ».

Distinguer les deux sujets : la découverte 🔴 ci-dessus portait sur des accès **révoqués et
pourtant effectifs** (bug de filtrage) ; ici il s'agit d'accès **volontairement accordés**.

**Robin** n'est **pas** dans le manifeste. À ajouter avec la même mécanique (une entrée
`people`, société `zone_404`). Informations manquantes : nom complet, rôle voulu
(`admin` / `rh` / `custom` avec permissions précises), et existence éventuelle d'un compte.

### Identifiants de connexion (action 2) — débloqué

Le login par identifiant `prenom.nom` **fonctionne déjà en production**. La résolution passe
d'abord par `employees.username` *(`auth/infrastructure/providers.py:80-105`)*, et les deux
comptes ont une fiche salarié avec un `username` unique. Exécution du résolveur de production
en lecture seule :

| Identifiant | Résout vers |
|---|---|
| `vanessa.amate` | `import.vanessa.amate.383122@…dsn-import.local` |
| `gaelle.bouali` | `gaelle.bouali@eywai.access.local` |

Les mots de passe provisoires sont dans `backend/reports/EYWAI_acces_provisoires.xlsx`
(permissions `600`, dossier `backend/reports/` ignoré par git). Les deux comptes ont
`must_change_password = true` : le mot de passe sera imposé au premier accès.

**Migration en attente, non bloquante.** `20260722150000_profiles_username.sql` n'est **pas**
appliquée en production (`profiles.username` absent) ; toutes les autres migrations récentes le
sont. Cette colonne n'est que le **repli** pour les comptes techniques *sans* fiche salarié —
ni Vanessa ni Gaëlle ne sont dans ce cas. À appliquer avec le prochain déploiement, en même
temps que le correctif `is_active`, sans urgence.

**Lien avec le chantier RGPD (§2.1) — alerte levée le 26/07.** L'e-mail d'authentification de
Vanessa est bien un placeholder DSN, mais **son accès n'est pas en danger** : le résolveur de
connexion part de l'identifiant `vanessa.amate`, passe par `user_id`, et ne lit jamais l'adresse
de la fiche (`auth/infrastructure/providers.py:88-104`). Vider `employees.email` ne casse aucune
connexion. Seules ses notifications étaient en jeu.

Elle se connecte de toute façon par son identifiant. Son adresse réelle
`amatevanessa@yahoo.fr` figure déjà sur sa fiche : le réalignement de son compte est inclus dans
le plan de reprise, sans rien à collecter. Son doublon inutilisé occupe `vamate@maji-invest.fr`
et n'est pas touché.

**Elsa André — cas distinct, à arbitrer.** Elle travaille quotidiennement sur
`eandre@maji-invest.fr` (profil « Eandre André », admin sur Cartol, MBC et Comitech, dernière
connexion le 24/07), alors que sa fiche salarié MAJI pointe vers un compte jamais utilisé, en
`collaborateur` sur MAJI seul. Un troisième compte orphelin occupe `andre.elsa@hotmail.com`.
Pour qu'elle bascule d'une société à l'autre comme un collaborateur RH, il faut une identité
unique portant plusieurs accès : rattacher `eandre@maji-invest.fr` à sa fiche, y ajouter l'accès
MAJI, supprimer le compte inutilisé, corriger le prénom. Fusionner deux identités revient à
décider quels droits survivent : **exclu du traitement de masse, à appliquer sur validation.**

---

### 3.2 Module Collaborateurs

| # | Action | État | Charge |
|---|---|---|---|
| 3 | Fichier importable IBAN + BIC | ✅ L'import existe | 1 h (produire le fichier) |
| 4 | Collecter les e-mails (RGPD) | ✅ **Dev fait le 26/07** — reste la collecte de 148 adresses | voir §2.1 |
| 6 | Dates d'expiration des titres de séjour | 📋 Saisie | — |
| 7 | Bouton d'export Excel des titres de séjour | 🟡 À développer | 0,5 j |

**IBAN/BIC — ne rien développer.** L'import Excel gère déjà la colonne BIC, avec reconnaissance
souple des en-têtes (`bic`, `swift`, `code bic`) *(`admin_import/application/rib_excel.py:25`)*,
validation d'IBAN et parsing de cellule RIB combinée. Il suffit de produire le fichier au bon
format. Je peux générer le gabarit pré-rempli des salariés dont le BIC manque, prêt à compléter.

**Titres de séjour — la moitié du travail est déjà là.** Le moteur d'alertes existe et couvre
même le cas « salarié soumis à titre de séjour mais **date d'expiration non renseignée** »
*(`residence_permits/domain/rules.py:58-66`)*, avec calcul du nombre de jours restants et
statuts d'échéance. Le tableau de bord charge déjà `residence_permit_expiry_date`. Il ne manque
donc réellement que **l'export Excel** : le module n'a aucune génération de fichier (aucune
occurrence de `xlsx`/`openpyxl`). C'est un petit développement, calqué sur les exports existants.

**Distinction date d'entrée / date d'ancienneté :** rien à faire. Les deux colonnes coexistent
légitimement, et la reprise d'ancienneté à la date de rachat pour Cartol est déjà la logique
utilisée pour la prime d'ancienneté. C'est conforme.

---

### 3.3 Module Congés

| # | Action | État | Charge |
|---|---|---|---|
| 8 | Compteur JTC séparé (3/an, dont 1 solidarité) | 🔴 Rien n'existe | 3-5 j |
| 9 | RTT fantômes Colorplast | 🔴 Voir §2.2 | 1 j + vérif 7 sociétés |
| 19 | Vérifier le fractionnement | ✅ Existe | 30 min |
| 22 | Arrondi des congés au 31 mai | 🟡 Partiellement là | 1 j |

**Fractionnement — rien à développer.** Module complet : domaine dédié
(`fractionnement.py`, `fractionnement_legal.py`), requêtes, prévisualisation, validation,
réglages activables par entreprise. C'est une vérification de paramétrage, pas un chantier.

**Arrondi au 31 mai — nuance importante.** L'arrondi à l'entier supérieur **existe déjà**, mais
sur l'**acquisition** :

```python
return float(math.ceil(months_worked * days_per_month))
```

*(`absences/domain/rules.py:82`, également appliqué au prorata d'ancienneté `cp_seniority.py:389`)*

Et la période de référence est bien calée sur une clôture au 31 mai
(`cp_reference_period_start_month` = 6 par défaut → juin→mai).

Ce qui est demandé — *« si le solde est de 7,5 jours, arrondi à 8 »* — porte sur le **solde**
(acquis moins pris), pas sur l'acquis. Ce n'est pas couvert. Avant de coder, **il faut trancher
la règle exacte** : arrondir le solde à la clôture, ou arrondir le droit acquis annuel ? Les
deux donnent des résultats différents dès qu'un salarié a posé des congés, et l'un des deux
crée du droit à congé supplémentaire. C'est une question pour Gaëlle avant d'être une question
de code.

**JTC — le chantier le plus sous-estimé de la liste.** Le terme « JTC » n'apparaît **nulle part**
dans le dépôt. Et surtout, les types d'absence sont un **type énuméré PostgreSQL**
(`absence_type`, migrations 50 et 55) *(`absences/domain/enums.py:9-21`)* : ajouter un type
implique une **migration de schéma**, pas seulement du code applicatif.

Deux approches :

- **Nouveau type d'absence** — migration d'enum, propagation dans le moteur de paie, les
  exports, la DSN, le front. Le plus intrusif.
- **Compteur séparé, sur le modèle de `repos_compensateur` ou `cet`** — deux modules complets
  qui font déjà exactement ça : un compteur distinct des CP/RTT, avec ses propres règles
  d'acquisition, de consommation et de péremption. **C'est le bon modèle**, et c'est ce que
  demande la réunion (« compteur séparé »).

La règle « 1 JTC réservé à la journée de solidarité » a un point d'accroche existant :
la journée de solidarité est déjà paramétrée par entreprise
(`parametres_paie.jour_solidarite`) et traitée par le moteur de paie
*(`payroll/engine/calcul_brut.py:120-123`)*. Il faudra relier les deux, ce qui n'est pas
trivial : c'est le seul point du chantier JTC qui touche la paie.

---

### 3.4 Tableau de bord, CSE et BDES

| # | Action | État | Charge |
|---|---|---|---|
| — | Absentéisme à zéro sur Cartol | 🔴 Voir §2.3 | 1-2 j |
| — | Masse salariale incorrecte | 🔴 Voir §2.4 | 2 j |
| 11 | Ajouter les élus CSE | 📋 Saisie | — |
| 12 | Erreurs sur les exports CSE | 🟠 Piste identifiée | à instrumenter |
| 13 | BDES auto-alimentée | 🔴 Seul l'upload existe | 8-10 j |

**Absentéisme.** Le calcul lui-même est correct : il compte les jours ouvrés d'absences
validées, rapportés à l'effectif actif multiplié par les jours ouvrés de la fenêtre
*(`dashboard/application/service.py:332-365`)*. Il lit `absence_requests` avec
`status = 'validated'` — exactement ce que l'import DSN produit.

Donc **si l'indicateur affiche zéro alors que la DSN de janvier contient 16 arrêts**, c'est que
les lignes d'absence n'ont pas atterri en base. Deux hypothèses, à départager par une requête :

1. Les éléments de type `absence` **n'ont pas été sélectionnés** lors de l'import (l'assistant
   permet de choisir ce qu'on valide) ;
2. Ils ont été importés mais **mal typés** (cf. §2.3), et se retrouvent en `sans_solde`.

Un simple comptage de `absence_requests` pour Cartol par type tranche immédiatement. **C'est la
première chose à faire sur ce chantier** — le correctif dépend entièrement de la réponse.

**Exports CSE — une piste, pas un diagnostic.** Trois exports existent : base des élus, heures
de délégation, historique des réunions *(`cse/infrastructure/cse_export_impl.py`)*. Dans
l'export des élus, le calcul des jours restants est enveloppé dans un `try/except Exception`
qui, en cas d'échec, met la valeur à `None` et laisse le statut à `"Actif"`
*(`cse_export_impl.py:31-44`)*. Si les dates de fin de mandat remontent avec un fuseau horaire,
la soustraction avec `datetime.now()` lève une `TypeError`, avalée par le `except` : l'export
sort alors avec une colonne « Jours restants » vide et **tous les mandats marqués « Actif »**,
y compris les expirés. C'est cohérent avec « des erreurs sur les exports ».

Mais je ne veux pas corriger sur une hypothèse. **Il me faut l'export fautif ou la description
précise de l'erreur constatée en réunion** — c'est le seul des quatre bugs où je n'ai pas de
cause racine solide.

**BDES — le seul vrai gros morceau.** Aujourd'hui, seul le **dépôt** d'un fichier BDES existe
(`POST /bdes`, `uploads/api/router.py:105`). Il n'y a **aucune génération**. L'objectif annoncé
— alimentation automatique des effectifs, du turnover, de la pyramide des âges, des salaires,
et export PDF ou Word pour septembre — représente 8 à 10 jours.

Le point positif : les indicateurs nécessaires existent déjà et sont calculés
(`build_analytics_avances` produit turnover, pyramide des âges, effectifs par service et par
contrat, ancienneté moyenne). L'essentiel du travail est la **structure réglementaire de la
BDES** et le rendu documentaire, pas le calcul. D'où l'importance de récupérer vite le tableau
BDES d'Elsa : **c'est lui qui définit la cible**, et sans lui le chantier ne peut pas démarrer.

---

### 3.5 Module Paye

| # | Action | État | Charge |
|---|---|---|---|
| 14 | Montants des primes médaille du travail | ✅ Configurable | 30 min |
| 15 | Prime de transport dans le module primes | ⚠️ **Ne pas faire** | — |
| 16 | Fichier de virement des acomptes | 🟡 Briques présentes | 2 j |
| — | Augmentations collectives : export Excel + vue annuelle | 🟡 À développer | 2-3 j |
| 20 | Double-check NIR et données DSN | 📋 + voir §2.3 | — |

**Médaille du travail — simple config.** Les paliers par défaut sont 400 € (argent, 20 ans),
600 € (vermeil, 30 ans), 800 € (or, 35 ans) et 1 000 € (grand or, 40 ans)
*(`work_medals/domain/rules.py:26-55`)*, mais une table `company_work_medal_settings` permet de
les redéfinir par entreprise. Les montants confirmés par Mickaël se paramètrent sans
développement. À signaler : le module gère déjà l'exonération sociale 2026 (exonéré si le
montant n'excède pas le salaire mensuel de base brut) — utile à mentionner à Mickaël, car cela
peut orienter le montant retenu.

**Prime de transport — attention, l'action telle que formulée conduirait à une erreur de paie.**
Le catalogue de primes ne connaît que deux modes de calcul, `montant_fixe` et `selon_heures`
*(`bonus_types/domain/enums.py`)*, **sans aucune notion d'exonération**. Une « prime de
transport » créée dans ce catalogue serait donc **intégralement soumise à cotisations**.

Or le transport **existe déjà**, ailleurs et correctement : dans les spécificités de paie du
contrat, avec le remboursement d'abonnement à 50 % (obligatoire, exonéré) et l'indemnité
mensuelle nette *(`payroll/engine/calcul_net.py:448-469`)*.

**La bonne réponse à cette action est donc : « elle existe, mais pas dans le module primes —
dans la fiche du salarié, onglet spécificités de paie ».** Il faut le montrer à Gaëlle plutôt
que de créer une prime au mauvais endroit. Le seul développement éventuel serait de rendre ce
réglage plus visible ou de permettre une saisie en masse.

**Fichier de virement des acomptes — les briques existent, le branchement non.** L'export
« acomptes » actuel est **comptable** : liste détaillée et écritures OD (comptes 425x/512000),
sans coordonnées bancaires *(`exports/infrastructure/export_acomptes.py`)*. Ce n'est pas un
fichier de virement.

En revanche, la plateforme sait déjà générer des virements : `export_sepa.py` produit du
**SEPA pain.001** (`generate_sepa_pain001`, `generate_sepa_or_csv_bank_file`) et le type
d'export `virement_salaires` est déclaré et fonctionnel
*(`exports/domain/value_objects.py`)*. Le travail consiste à alimenter la génération SEPA avec
les acomptes de la période au lieu des nets à payer. **Dépendance directe : les BIC manquants**
(§3.2) — sans eux, le fichier ne passera pas en banque.

**Augmentations collectives.** Le module `promotions` ne contient **aucune génération Excel ni
vue annuelle** (aucune occurrence de `xlsx`/`excel`). Les deux demandes de la réunion sont donc
à développer intégralement.

**Anomalies de paie — conforme.** Le système rouge/orange décrit en réunion existe bien :
`PreflightAnomalySeverity = Literal["bloquant", "a_verifier"]`
*(`payroll/schemas/preflight_responses.py:19`)*. Rien à faire.

**OD comptables.** La réunion indique qu'elles « ne sont pas encore interfacées ». Le module
`accounting_integration` contient pourtant déjà trois connecteurs : manuel, API générique et
**Cegid Quadra**. C'est donc potentiellement de la configuration plutôt qu'un développement —
à qualifier avec le cabinet avant de chiffrer.

**Prélèvement à la source.** Conforme à ce qui a été présenté : taux récupéré via la DSN
d'amorçage, non modifiable manuellement. Attention toutefois — un défaut d'import du taux à
0,00 a déjà été rencontré et corrigé par le passé ; **cela fait partie des points à revérifier
avant la mise en production**, au même titre que les NIR.

---

### 3.6 Suivi médical, départs, pointage

| # | Action | État | Charge |
|---|---|---|---|
| 10 | Coche « aménagement » sur le suivi médical | 🟡 À développer | 0,5-1 j |
| 21 | Badgeuse chez Colorplast | ✅ Prête | déploiement |
| 17 | Environnement de test | 🔴 Voir §4.1 | 3-5 j |
| 18 | Session paye avec Gaëlle | 📋 Organisation | — |

**Coche « aménagement de poste ».** Le terme n'existe nulle part. Le module gère les
obligations et les visites (`VisitType`, `MedicalObligation`, moteur d'obligations), mais il
n'y a pas d'entité « avis d'aptitude » portant des restrictions. Deux points d'attention :

1. Il faut **décider où la coche se pose** — sur la visite ou sur le salarié. Un aménagement de
   poste survit à la visite qui l'a prescrit : le poser sur la visite le rendrait invisible dès
   la visite suivante. Il devrait être porté par le salarié, avec la visite d'origine en référence.
2. Un aménagement de poste a des **conséquences juridiques** (obligation de reclassement,
   inaptitude). Une simple case à cocher est le bon point de départ, mais il faut savoir qu'elle
   appellera ensuite un motif et une date de fin.

**Badgeuse — rien à développer.** Le module est complet : service QR, authentification des
terminaux, routeur terminal dédié, gestion des pointages, export, type d'événement `QR_SCAN`.
Le déploiement chez Colorplast d'abord est la bonne approche et ne dépend pas de moi.

**Départs — conforme.** Les trois documents obligatoires sont bien générés : certificat de
travail (article L1234-19), attestation Pôle Emploi et solde de tout compte
*(`employee_exits/domain/interfaces.py:130-155`)*. Détail cosmétique : l'organisme s'appelle
France Travail depuis 2024 ; l'attestation reste nommée « Pôle Emploi » dans le code et
probablement dans l'interface.

---

## 4. Risques transverses

### 4.1 🔴 L'environnement de test avec données réelles

La demande est légitime : personne ne doit s'entraîner à faire une sortie de salarié en
production. Mais **« avec les données réelles »** signifie dupliquer, hors production, des
bulletins de paie, des NIR, des IBAN, des coordonnées et des données de santé (arrêts de
travail) de plusieurs centaines de personnes. C'est un traitement de données personnelles à
part entière, sans base légale évidente, et un environnement de test est par construction moins
protégé que la production.

**Une base pseudonymisée remplit exactement le même objectif de formation** — s'entraîner sur
les sorties, la génération de paie, les opérations à risque — pour un coût de développement
comparable et sans exposition. Les volumes, les structures et les cas particuliers sont
conservés ; seules les identités changent.

Je recommande de trancher pour la pseudonymisation. Si la copie réelle est malgré tout retenue,
c'est une décision à documenter et à porter avec le DPO, pas une décision technique.

### 4.2 🟠 Ce qui bloque quoi

Deux dépendances ne sont pas visibles dans une liste à plat et peuvent faire dérailler le
planning si elles sont découvertes tard :

- **BIC manquants → fichier de virement des acomptes.** Développer le virement avant d'avoir les
  BIC produit un fichier rejeté par la banque. La collecte doit démarrer maintenant.
- **Tableau BDES d'Elsa → chantier BDES.** Sans la cible, le développement ne peut pas commencer.
  C'est le poste le plus long : c'est aussi celui dont la dépendance externe doit être levée en premier.

### 4.3 🟡 Points de contrôle avant la mise en production

- **Sécurité base de données.** Une migration d'activation des politiques RLS couvrant 14 tables
  sensibles (permissions, `payroll_config`, modèles de documents, objectifs) a été écrite le
  22/07 *(`supabase/migrations/20260722120000_security_rls_advisor_fixes.sql`)*. **À confirmer
  qu'elle est bien appliquée en production**, en particulier avant d'ouvrir les accès aux directeurs.
- **SMIC non daté.** La table de configuration de paie ne porte pas de dimension temporelle : une
  seule valeur de SMIC est active à la fois. Les calculs sur les mois passés utilisent donc le
  SMIC courant. L'impact est limité (réduction générale de cotisations patronales) mais réel, et
  c'est un chantier transverse à toutes les entreprises. À connaître avant de conclure sur des
  écarts de paie.
- **Travail non commité.** Deux fichiers sont modifiés et non validés dans le dépôt
  (`dsn_import/application/mapping.py` et son test). À finaliser ou à ranger avant d'enchaîner.

---

## 5. Plan proposé jusqu'à septembre

**Vague 0 — à lancer aujourd'hui, sans dépendance** *(non technique, en parallèle de tout)*
Collecte des e-mails (passage papier via Corinne et Catherine) · collecte des BIC · saisie des
dates d'expiration des titres de séjour · ajout des élus CSE · confirmation des montants médaille
avec Mickaël · demande du tableau BDES à Elsa.

**Vague 1 — semaine 1 : crédibilité de l'outil** *(~5 j)*
Provisionnement des accès Vanessa et Robin · ~~garde-fou e-mails placeholder (§2.1)~~ **fait le
26/07, reste à déployer et à appliquer la reprise** · diagnostic puis correction de
l'absentéisme Cartol (§2.3) · masse salariale depuis les bulletins (§2.4) · RTT par défaut,
avec relevé des 7 sociétés (§2.2).
→ *Objectif : plus aucun chiffre faux affiché avant l'ouverture aux directeurs.*

**Vague 2 — semaine 2 : les petits manques visibles** *(~4 j)*
Export Excel des titres de séjour · coche aménagement de poste · arrondi des congés au 31 mai
(après arbitrage de la règle) · gabarit d'import IBAN/BIC · démonstration à Gaëlle de la prime
de transport existante · exports CSE (dès que j'ai l'erreur exacte).

**Vague 3 — semaines 2 à 5, en fil rouge : la BDES** *(~8-10 j)*
Démarre dès réception du tableau d'Elsa. C'est le poste long ; il doit tourner en parallèle des
autres vagues, pas après.

**Vague 4 — semaines 3 et 4 : la paye et les compteurs** *(~8 j)*
Fichier de virement des acomptes (après les BIC) · compteur JTC · augmentations collectives
(export Excel et vue annuelle).

**Vague 5 — semaine 5 : la recette**
Environnement de test pseudonymisé · session paye dédiée avec Gaëlle · double-vérification des
NIR et du mapping DSN · déploiement de la badgeuse chez Colorplast.

---

## 6. Ce dont j'ai besoin pour avancer

1. **L'erreur exacte sur les exports CSE** — quel export, quel symptôme. C'est le seul bug sans
   cause racine identifiée.
2. **L'arbitrage sur l'arrondi des congés au 31 mai** : arrondir le solde, ou le droit acquis ?
   Question pour Gaëlle.
3. **La décision sur l'environnement de test** : pseudonymisé (recommandé) ou données réelles.
4. **Le tableau BDES d'Elsa** — bloquant sur le chantier le plus long.
5. **Confirmation que la migration RLS est appliquée en production.**

---

*Document produit par audit du code au 26/07/2026. Les références de fichiers pointent vers
l'état du dépôt à cette date, branche `main`.*
