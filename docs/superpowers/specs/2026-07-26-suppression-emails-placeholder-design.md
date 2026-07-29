# Suppression des adresses e-mail fabriquées — conception

**Date :** 26 juillet 2026
**Décision fondatrice :** l'adresse e-mail d'un salarié est celle de la personne, ou rien.
Aucune adresse ne doit plus être inventée par la plateforme.

---

## 1. Constat

### 1.1 Ce que contient la production

| | Total | Adresse fabriquée |
|---|---|---|
| Fiches salarié (`employees.email`) | 289 | **183** |
| Comptes de connexion (`auth.users`) | 302 | **250** |

Quatre familles d'adresses fabriquées coexistent :

| Suffixe | Origine | Volume en fiche |
|---|---|---|
| `*.dsn-import.local` | import DSN | 153 |
| `@dsn-import.eywai.fr` | repli du provisionnement de compte | 27 |
| `@eywai.access.local` | comptes d'accès créés à la main (Gaëlle) | 3 |
| `@users.eywai` | repli des comptes techniques du manifeste | 0 (jamais déclenché) |

### 1.2 Les deux fabriques

Le placeholder n'a pas une source mais deux, et la seconde est la plus nocive.

**Fabrique 1 — import DSN.** `_placeholder_email`
(`dsn_import/application/mapping.py:512-517`) compose
`import.prenom.nom.123456@534386495.dsn-import.local` et l'écrit dans le payload salarié.
La DSN ne transporte aucune adresse e-mail : le champ était rempli uniquement pour ne pas
rester vide.

**Fabrique 2 — provisionnement de compte.** `provision_employee_account`
(`employees/application/account_provisioning.py:92-94` puis `:152-158`) prend l'adresse
technique de repli nécessaire à la création du compte Auth et la **recopie dans
`employees.email`**. Un identifiant technique interne devient ainsi une adresse de contact.

### 1.3 Conséquence conformité

La notification de dépôt de document — obligation « coffre-fort électronique » — teste
seulement `if email:` avant d'envoyer (`notifications/application/employee_document_alerts.py:198`).
Une adresse fabriquée passe ce test. L'envoi part, échoue côté SMTP, et la fonction est
`best effort` : elle ne lève jamais d'exception et ne journalise pas l'échec.

Résultat : on croit avoir notifié 183 salariés qui ne l'ont jamais été, sans moyen de savoir
lesquels.

### 1.4 Ce que les fichiers d'enrichissement contiennent déjà

Les 7 classeurs `Config/*/Enrichissement Salarié/*.xlsx` (format Quadratus) portent tous une
colonne `e-mail` en colonne Q. Le canal d'import la reconnaît déjà
(`admin_import/application/payroll_export_mapping.py:16`, alias `e-mail`/`email`/`mail`/`courriel`)
et écrase un placeholder par une vraie adresse sans jamais faire l'inverse
(`payroll_export_import.py:229-233`).

**Ce gisement est épuisé.** Sur 285 lignes salarié, 108 portent une adresse et **107 sont déjà
en base**. Il reste exactement un cas exploitable (Lucas CHAMBERT, fiche MBC en placeholder
alors que son adresse est connue sur sa fiche Comitech) et une adresse orpheline
(Rafiullah AMARKHILL, MBC, aucune fiche en base).

Pour les 183 autres, la case e-mail est vide chez Cegid aussi : Cartol a 108 lignes pour
11 adresses, LEWIS a 43 lignes et zéro adresse. **L'information n'existe dans aucun système.**
148 de ces salariés sont actifs — c'est le volume à collecter sur le terrain, hors périmètre
de ce chantier.

### 1.5 Le décalage fiche / compte

Croisement des 289 fiches avec les 302 comptes Auth :

| Situation | Nombre |
|---|---|
| Fiche fabriquée **et** login fabriqué | 183 |
| **Fiche réelle mais login encore fabriqué** | **85** |
| Fiche réelle et login réel | 21 |

Ces 85 personnes ont déjà leur adresse réelle en base et se connectent toujours avec
`import.…@…dsn-import.local`, parce **qu'aucun code du dépôt ne met à jour l'adresse d'un
compte Auth existant**. Vanessa Amate et Elsa André en font partie.

---

## 2. Principe directeur

Le code confond aujourd'hui deux objets. La conception les sépare.

| | Rôle | Règle |
|---|---|---|
| `employees.email` | **Adresse de contact** de la personne | Réelle ou vide. Jamais fabriquée, sous aucune condition. |
| `auth.users.email` | **Identifiant technique** du compte | Jamais affiché, jamais utilisé comme contact. Aligné sur l'adresse réelle dès qu'elle est connue, pour que la réinitialisation de mot de passe fonctionne. |

La connexion se fait par **identifiant `prenom.nom`**, pas par adresse. Le résolveur
(`auth/infrastructure/providers.py:88-104`) part de `employees.username`, passe par `user_id`,
puis lit l'adresse du compte Auth. **Vider `employees.email` ne casse donc aucune connexion** —
l'avertissement porté au §3.1 de `docs/etat-des-lieux-si-rh-2026-07.md` sur l'accès de Vanessa
est trop pessimiste : seules ses notifications sont en jeu, pas son accès.

**Comportement retenu à la création d'un salarié :** fiche créée complètement, sans adresse ;
l'adresse s'ajoute ensuite ; la connexion devient possible ensuite. L'absence d'adresse ne
bloque jamais la création d'une fiche, ni la paie, ni la DSN.

---

## 3. Conception

### 3.1 Import DSN — ne plus fabriquer

`_placeholder_email` est supprimée. La clé `email` disparaît du payload salarié quand la
source ne fournit rien ; le champ reste vide en base.

L'assistant d'import laisse déjà l'utilisateur saisir l'adresse par salarié (`FIELD_LABELS`
expose `email` → « Email ») : la saisie reste possible au moment de l'import, elle n'est
simplement plus pré-remplie d'une valeur inventée.

### 3.2 Provisionnement de compte — ne plus recopier

`provision_employee_account` continue d'utiliser une adresse technique quand aucune adresse
réelle n'existe : Supabase Auth en exige une. Mais cette adresse **n'est plus écrite dans
`employees.email`**. La fiche conserve son champ vide.

Le même verrou s'applique au chemin de création directe (`commands.py:398-455`), qui écrit
`db_insert_data["email"] = email` avec la même adresse de repli.

### 3.3 Garde-fou de notification

`notify_employee_document` refuse d'envoyer vers une adresse fabriquée et **journalise en
warning** au lieu de perdre l'échec. La notification in-app, elle, est conservée : elle reste
le seul canal disponible pour un salarié sans adresse.

Le garde-fou est utile même après les correctifs 3.1 et 3.2 : les 183 fiches existantes
conservent leur adresse fabriquée tant que la reprise n'a pas eu lieu, et une adresse
`@eywai.access.local` peut réapparaître par saisie manuelle.

### 3.4 Synchronisation fiche → compte

Nouveau comportement, aujourd'hui totalement absent : quand une adresse réelle est posée sur
une fiche rattachée à un compte dont l'adresse Auth est fabriquée, **le compte est réaligné**.

Déclenché depuis le point de passage unique de la mise à jour d'un salarié
(`employees/application/commands.py:update_employee`), donc valable quelle que soit l'origine
de la correction : import d'enrichissement, saisie RH, script de reprise.

Règles :
- réalignement uniquement si l'adresse Auth actuelle est fabriquée — une adresse réelle
  déjà en place n'est jamais écrasée ;
- si l'adresse cible est déjà prise par un autre compte, on ne force rien : l'échec est
  journalisé et la mise à jour de la fiche aboutit quand même ;
- l'opération ne lève jamais d'exception vers l'appelant : corriger une adresse de contact ne
  doit pas pouvoir faire échouer l'enregistrement d'une fiche.

### 3.5 Manifeste d'accès

`users/data/access_manifest.json:239` fige l'adresse fabriquée de Vanessa. Ce champ
`identity.email` est un **clé de recherche du compte Auth**
(`access_provisioning.py:663-668`), pas une adresse de contact — il doit donc suivre
l'adresse Auth réelle après réalignement, sinon la résolution échoue.

Ordre imposé : réaligner le compte, puis mettre le manifeste à jour. En cas d'inversion,
le provisioning signale un conflit `resolve_identity` sans rien créer — comportement
fail-closed acceptable.

Le repli `f"{username}@users.eywai"` (`access_provisioning.py:167`) est conservé : il ne
produit qu'un identifiant Auth pour un compte technique sans fiche, jamais une adresse de
contact. Il est ajouté à la liste des suffixes reconnus comme fabriqués.

### 3.6 Reprise de l'existant

Un script `backend/scripts/cleanup_placeholder_emails.py`, **en lecture seule par défaut**,
sur le modèle de `provision_access_matrix.py` (plan JSON, `--apply` explicite exigeant la
référence de projet et une confirmation production).

Deux opérations, activables séparément (`--clear-fiches`, `--realign-logins`) :

1. **Vider** les 183 `employees.email` fabriquées. Sans effet sur les connexions (§2).
2. **Réaligner** les 85 comptes dont la fiche porte déjà l'adresse réelle.

Le plan liste nommément chaque salarié touché et sauvegarde l'état avant modification. Les deux
opérations sont idempotentes : un second passage produit un plan vide.

L'unique adresse récupérable des fichiers d'enrichissement (Lucas CHAMBERT, fiche MBC —
`lucas.chambert@gmail.com`, déjà connue sur sa fiche Comitech) **n'est pas traitée par le
script** : un cas isolé ne justifie pas d'y brancher la lecture des classeurs `Config/`. À
saisir à la main ou à faire passer par l'import d'enrichissement, avant le vidage des fiches
— sinon l'adresse est simplement à ressaisir ensuite.

### 3.7 Cas particuliers documentés, non traités par le script

**Elsa André — identité dédoublée.** Elle utilise quotidiennement `eandre@maji-invest.fr`
(profil « Eandre André », admin sur Cartol/MBC/Comitech, dernière connexion 24/07), tandis que
sa fiche salarié MAJI pointe vers un compte jamais utilisé (collaborateur MAJI seul). Un
troisième compte orphelin occupe `andre.elsa@hotmail.com`.

L'objectif retenu est qu'elle puisse **basculer d'une société à l'autre comme un collaborateur
RH** — mécanisme qui existe déjà (Vanessa bascule entre 7 sociétés). Cela suppose une identité
unique portant plusieurs accès : rattacher `eandre@maji-invest.fr` à sa fiche salarié, y
ajouter l'accès MAJI, supprimer le compte inutilisé, corriger le prénom `Eandre` → `Elsa`.
Fusionner deux identités revient à décider quels droits survivent : opération exclue du
traitement de masse, à appliquer explicitement après validation.

**Vanessa Amate.** Son adresse réelle `amatevanessa@yahoo.fr` est déjà sur sa fiche. Elle se
connecte par son identifiant `vanessa.amate`. Un doublon jamais utilisé, sans fiche et à
l'accès MAJI révoqué, occupe l'adresse `vamate@maji-invest.fr` ; sa suppression n'est pas
nécessaire au réalignement et n'est pas incluse.

**Deux anomalies de données** relevées et non corrigées, faute de savoir laquelle des deux
valeurs est juste :
- `malopoulain@orange.fr` est porté à la fois par Quentin MATHIEU et Malo POULAIN (MBC) ;
- `athoumanimohamed@29gmail.com` (Athoumani MOHAMED, MBC) a un domaine invalide.

---

## 4. Hors périmètre

- **La collecte des 148 adresses manquantes** (salariés actifs sans adresse nulle part). Seul
  poste que le code ne peut pas résoudre ; relève du terrain, via le canal d'enrichissement
  existant.
- **Le nettoyage des comptes Auth orphelins** (comptes sans fiche ni profil).
- **La correction des deux anomalies de données** ci-dessus.

---

## 5. Tests

| Cible | Vérification |
|---|---|
| Import DSN | le payload d'un salarié sans adresse ne porte aucune clé `email` ; aucun suffixe fabriqué n'est produit |
| Provisionnement | l'adresse technique crée bien le compte Auth mais n'atterrit pas dans `employees.email` |
| Création directe | même garantie sur le chemin `commands.py` |
| Notification | une adresse fabriquée n'entraîne aucun envoi et produit un warning ; la notification in-app reste émise ; une adresse réelle envoie normalement |
| Synchronisation | adresse réelle posée sur une fiche à login fabriqué → compte réaligné ; login déjà réel → intact ; adresse cible déjà prise → fiche mise à jour, échec journalisé, aucune exception |
| Détection | les quatre suffixes fabriqués sont reconnus, une adresse réelle ne l'est jamais |

Non-régression attendue : suite complète du dépôt au vert.
