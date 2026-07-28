# Environnement de test avec les données réelles

Date : 2026-07-28
Sujet : `docs/afaire.md` #17
Statut : conception validée, implémentation à planifier

## 1. Objectif

Offrir un second environnement complet, en ligne, contenant une copie des données
de production, sur lequel Elsa, Gaëlle et Vanessa peuvent effectuer des
manipulations réelles — démissions, ruptures, générations de bulletins,
suppressions — sans aucun effet sur la production.

La relation entre les deux environnements est à sens unique :

- le test se recale sur la prod à la demande (« resynchro ») ;
- rien ne remonte jamais du test vers la prod.

Cette garantie est structurelle et non conventionnelle : le pipeline de copie se
connecte à la production avec un rôle PostgreSQL **en lecture seule**. Un script
bogué ou une erreur de manipulation ne peut pas écrire en production.

## 2. Hors périmètre

- Environnement par pull request ou URL de prévisualisation.
- Anonymisation des données. Le test contient les données réelles, ce qui est le
  besoin exprimé ; l'accès est limité aux mêmes personnes qu'en production, qui
  y ont déjà un accès légitime.
- Bascule test → prod, sous quelque forme que ce soit.
- Remplacement de l'environnement Supabase local (`docs/LOCAL_SUPABASE.md`), qui
  reste l'outil de développement quotidien.

## 3. État des lieux

### 3.1 Il n'existe pas de véritable pré-production

Dans `.github/workflows/deploy.yml`, les jobs `staging` et `production`
injectent tous deux `secrets.SUPABASE_URL` et `secrets.SUPABASE_KEY` : **la même
base**. Même lorsque les noms de services Cloud Run diffèrent (`*_PROD`), les
deux environnements écrivent dans la base de production, et les tests de fumée
du job `staging` s'exécutent sur les données réelles avant le gate production.
Le job `staging` est donc un faux filet de sécurité. Il devient le déploiement
de test décrit ici.

### 3.2 Le dépôt n'a pas de migration initiale

`docs/LOCAL_SUPABASE.md` le documente déjà : les tables historiques
(`companies`, `profiles`, `employees`, `user_company_accesses`) n'ont pas de
migration de création. Les 159 migrations du dépôt ne peuvent donc pas
reconstruire une base vide. La création initiale de la base de test passe
obligatoirement par un dump complet du schéma de production, comme le fait déjà
`make supabase-dump-prod-schema`. Les migrations ultérieures s'appliquent
ensuite normalement via `supabase db push`.

### 3.3 Sorties vers le monde réel

Trois chemins peuvent atteindre de vraies personnes depuis un environnement
contenant des données réelles :

| Sortie | Code | Risque |
|---|---|---|
| SMTP | `app/shared/infrastructure/email/smtp_sender.py` | bulletins et alertes envoyés à de vrais salariés |
| Dépôt DSN | `app/modules/net_entreprises/infrastructure/api_connector.py` | déclaration réelle transmise à l'URSSAF |
| Signature électronique | `app/services/yousign_service.py` | demandes de signature à de vraies personnes |

Point critique : **la configuration SMTP est lue en base**, pas seulement dans
l'environnement. `SmtpMailSender._load_config()` appelle
`get_resolved_email_config()` qui interroge `platform_settings`, avec repli sur
les variables d'environnement. Copier les données de production copie donc ses
réglages SMTP dans le test. Une neutralisation par variables d'environnement
seule serait insuffisante.

`PAYSLIP_EMAIL_REDIRECT` existe déjà mais ne couvre qu'un seul type d'envoi
(`employee_document_alerts.py`, notifications de bulletins). Il ne protège ni
les réinitialisations de mot de passe, ni les alertes d'échéances, ni les
exports.

`YousignService` lève déjà une erreur si `YOUSIGN_API_KEY` est absente ; le
blocage sera néanmoins explicite, pour que l'interface affiche « action
indisponible en environnement de test » plutôt qu'une erreur de configuration.

## 4. Architecture

```
GitHub main ──CI verte──┬──► Cloud Run  sirh-backend       ──► Supabase PROD
                        │    Cloud Run  sirh-frontend
                        │
                        └──► Cloud Run  sirh-backend-test  ──► Supabase TEST
                             Cloud Run  sirh-frontend-test

        Workflow « Refresh test from prod » (manuel ou bouton)
        Supabase PROD ──(rôle lecture seule)──► Supabase TEST
```

### 4.1 Choix d'hébergement : Cloud Run, pas Vercel

Le backend ne peut pas être hébergé sur Vercel : WeasyPrint exige les
bibliothèques système cairo et pango (installées explicitement dans la CI) et le
service tourne avec `--memory=2Gi --timeout=900`, 512 Mio provoquant des OOM.
Vercel n'hébergerait donc que le frontend de test, ce qui ferait coexister deux
chaînes de livraison pour le même code : nginx dans Docker en production, Vercel
en test. Tout ce qui dépend de nginx — fallback SPA, en-têtes, cache — ne serait
plus couvert par le test. Un environnement de test qui ne reproduit pas la
chaîne de production perd son intérêt.

Deux services Cloud Run supplémentaires réutilisent les Dockerfile et le
workflow existants.

### 4.2 Choix de base : un second projet Supabase

Alternatives écartées :

- **Schéma `test` dans la base de production** : même instance, `auth.users` et
  Storage partagés — donc pas d'identifiants distincts — et une charge de test
  dégrade la production.
- **Sociétés « (TEST) » dans la base de production** : les écritures de test
  atterrissent physiquement en production. La garantie demandée disparaît.
- **Branching Supabase** : conçu pour des bases éphémères créées par pull
  request à partir des migrations. Or le dépôt n'a pas de migration initiale
  (§3.2), une branche naîtrait vide ; il faudrait y restaurer un dump, soit le
  même travail que pour un projet mais sur un support prévu pour être jeté, et
  facturé à l'heure.

Le second projet est le seul montage où l'isolation est une propriété physique.

Coût : un projet Supabase supplémentaire. Le palier gratuit plafonne à 500 Mio
et met le projet en pause après 7 jours d'inactivité, ce qui ne convient pas
avec le Storage des bulletins ; prévoir un projet payant (~25 $/mois).

### 4.3 Identification de l'environnement

- Backend : `APP_ENV` (`prod` par défaut, `test` sur les services de test).
- Frontend : `VITE_APP_ENV`, injecté **au build**. Le bandeau et le bouton de
  resynchro n'existent donc pas dans le bundle de production, plutôt que d'être
  masqués par une condition à l'exécution.

## 5. Périmètre de la copie

Copié :

- schéma `public` — l'intégralité des données métier ;
- schéma `auth` — les comptes de connexion, afin que chacune se connecte au test
  avec ses identifiants habituels et retrouve ses droits, sans recréation
  manuelle après chaque resynchro ;
- Storage — bulletins, documents et pièces jointes, sans quoi le test affiche
  des liens morts sur l'historique.

## 6. Flux de resynchro

Déclenché par le bouton de l'interface de test ou manuellement depuis GitHub
Actions. Le backend de test ne détient **aucun** accès à la base de production :
il déclenche le workflow via un jeton GitHub à portée restreinte, limité à ce
seul workflow. Les accès aux bases restent côté GitHub Actions.

1. **Verrou** — refus si une resynchro est déjà en cours (`concurrency` GitHub).
2. **Garde de destination** — échec immédiat si la référence du projet cible est
   celle de la production.
3. **Dump** — `pg_dump` des schémas `public` et `auth`, données seules, via le
   rôle lecture seule de production.
4. **Storage** — copie des objets via l'API Storage.
5. **Restauration** — purge puis chargement dans le test, en transaction.
6. **Neutralisation en base** (§7.2).
7. **Contrôles** — tests de fumée et cohérence (§8).
8. **Horodatage** — date de dernière resynchro exposée par le backend et
   affichée dans le bandeau.

Toute resynchro écrase le bac à sable : les manipulations en cours côté test
sont perdues. C'est assumé et signalé par une confirmation explicite dans
l'interface, indiquant la date de la dernière resynchro.

## 7. Garde-fous

### 7.1 Applicatifs

Sous `APP_ENV=test` :

- **SMTP** — redirection de tout envoi vers l'adresse de `EMAIL_FORCE_REDIRECT_TO`,
  appliquée dans `SmtpMailSender` après résolution de la configuration, donc
  quelle que soit son origine (base ou environnement). Le destinataire réel est
  reporté dans l'objet du message. `PAYSLIP_EMAIL_REDIRECT` est généralisé en un
  mécanisme unique couvrant tous les types d'envoi.
- **Dépôt DSN** — `NetEntreprisesApiConnector.submit_dsn` refuse et renvoie un
  message explicite d'indisponibilité en environnement de test.
- **Signature électronique** — `YousignService` refuse toute création de demande
  de signature, avec le même type de message.

### 7.2 En base, après chaque copie

- Configuration SMTP de `platform_settings` remplacée par celle de la boîte de
  test (sans quoi le test hériterait des réglages de production, §3.3).
- Secrets d'intégration copiés purgés.
- Files d'envoi et notifications en attente vidées.

Les adresses e-mail des salariés sont en revanche **conservées telles quelles**.
Les réécrire reviendrait à fabriquer des adresses, ce que la règle du projet
interdit et ce que la branche `fix/emails-reels-suppression-placeholders`
supprime précisément ; cela rendrait de surcroît le test infidèle à la
production. La protection ne repose donc pas sur l'altération des données mais
sur le point d'envoi unique, garanti par §7.3.

### 7.3 Impossibilité de démarrer sans redirection

La redirection SMTP est pilotée par une variable dédiée,
`EMAIL_FORCE_REDIRECT_TO`, et non déduite de `APP_ENV`. Le backend **refuse de
démarrer** sous `APP_ENV=test` si cette variable est vide.

Une erreur de configuration ne peut donc pas produire un environnement de test
qui envoie du courrier réel : soit la redirection est active, soit le service ne
démarre pas. C'est ce qui remplace, avantageusement, la réécriture des adresses
en base.

### 7.4 Infrastructure

- Rôle PostgreSQL de production en lecture seule dédié au pipeline.
- Jeton GitHub du backend de test restreint au déclenchement d'un seul workflow.
- Vérification que les workflows planifiés — `hr-deadline-reminders-dispatch`,
  `scheduled-exports-dispatch`, `collective-agreements-kali-sync` — ne visent
  que la production.

## 8. Tests

Chaque garde-fou est couvert par un test qui échoue s'il saute.

Tests automatisés (suite backend) :

- sous `APP_ENV=test`, `submit_dsn` de l'API net-entreprises refuse ;
- sous `APP_ENV=test`, la création de demande de signature Yousign refuse ;
- la redirection SMTP s'applique à **tous** les types d'envoi, y compris lorsque
  la configuration provient de la base — test de non-régression contre le
  comportement partiel actuel de `PAYSLIP_EMAIL_REDIRECT` ;
- sous `APP_ENV=prod`, aucun de ces blocages ne s'active (non-régression) ;
- le backend refuse de démarrer sous `APP_ENV=test` sans
  `EMAIL_FORCE_REDIRECT_TO` (§7.3) ;
- le garde de destination du script de resynchro refuse une cible de production ;
- `ALLOWED_ORIGINS_EXTRA` étend bien les origines CORS sans altérer celles de
  production ni la regex de développement local (§12.1).

Contrôles exécutés à la fin de chaque resynchro :

- effectifs de la base de test identiques à ceux de la production ;
- connexion réussie avec un compte réel ;
- configuration SMTP de `platform_settings` bien remplacée par celle de la boîte
  de test, et non héritée de la production ;
- tests de fumée HTTP sur le backend et le frontend de test, sur le modèle de
  ceux déjà présents dans `deploy.yml`.

## 9. Découpage de la livraison

Quatre lots, chacun utilisable indépendamment.

1. **Garde-fous applicatifs et tests** — `APP_ENV`, redirection SMTP
   généralisée, refus de démarrage sans redirection, blocages DSN et Yousign.
   Ne dépend d'aucune infrastructure et peut être livré immédiatement.
2. **Projet Supabase de test et script de copie** — création du projet, rôle
   lecture seule en production, dump, restauration, Storage, neutralisation en
   base, garde de destination.
3. **Services Cloud Run de test et intégration CI** — remplacement du job
   `staging`, déploiement automatique de `main` et déploiement d'une branche au
   choix par `workflow_dispatch`.
4. **Interface** — bandeau permanent, bouton de resynchro avec confirmation,
   affichage de la date de dernière resynchro.

## 10. Prérequis à la charge de l'utilisateur

Tout le reste est automatisé en CLI (`gcloud` et `gh` sont déjà authentifiés,
`pg_dump` 15.15 est aligné sur la version de la base). Restent deux points
d'authentification qu'aucune commande ne contourne :

1. **Jeton d'accès Supabase** — `supabase login` (validation navigateur, une
   fois) ou jeton personnel. La CLI est installée mais non authentifiée.
2. **Identifiants SMTP de la boîte de test** à créer.

Aléa à lever une fois le jeton disponible : si l'organisation Supabase est au
palier gratuit, le passage au palier payant relève de la facturation, donc du
tableau de bord.

## 11. Risques

| Risque | Traitement |
|---|---|
| Une resynchro efface un test en cours | Déclenchement manuel uniquement, confirmation explicite, date de dernière resynchro affichée |
| Dérive de schéma entre test et prod | Résolue par construction : la resynchro restaure le schéma **et** les données (§12.3) |
| Croissance du coût Storage | Mesure de la volumétrie au premier lot 2 ; copie sélective des buckets si nécessaire |
| Données réelles dupliquées dans un second système | Accès restreint aux mêmes personnes qu'en production ; neutralisation systématique des sorties |

## 12. Robustesse — pièges identifiés et traitement

Les défauts de ce type de montage sont dans la plomberie. Les points suivants
ont été vérifiés dans le code et doivent être traités explicitement, faute de
quoi l'environnement ne fonctionnera pas.

### 12.1 Les origines CORS sont écrites en dur — bloquant

`app/main.py` définit `ALLOWED_ORIGINS` comme une liste littérale contenant les
deux URL Cloud Run de production. Le frontend de test aurait une URL nouvelle,
absente de cette liste : **tous les appels API seraient rejetés par le
navigateur** et l'environnement serait inutilisable.

`CORS_ALLOW_ORIGIN_REGEX` existe déjà mais le surcharger écraserait la regex de
développement local, cassant le travail quotidien.

Traitement : ajouter une variable `ALLOWED_ORIGINS_EXTRA` (liste séparée par des
virgules) concaténée à `ALLOWED_ORIGINS`, vide par défaut. Le service de test y
déclare l'origine de son frontend. Aucun comportement de production ni de
développement local n'est modifié. Couvert par un test.

### 12.2 `VITE_API_URL` est figé au build — ordre de création imposé

`frontend/Dockerfile` reçoit `VITE_API_URL` en `ARG` : l'URL du backend est
compilée dans le bundle. Il faut donc connaître l'URL du backend de test avant
de construire son frontend, alors que cette URL n'existe qu'après création du
service Cloud Run.

Traitement, en deux temps :

1. **Amorçage, une seule fois** : créer le service backend de test, lire son URL
   via `gcloud run services describe`, l'enregistrer comme variable de dépôt
   `VITE_API_URL_TEST`, puis créer le frontend de test.
2. **Ensuite** : `deploy.yml` construit **deux** images frontend, l'une avec
   `vars.VITE_API_URL`, l'autre avec `vars.VITE_API_URL_TEST`. Les images
   backend sont identiques pour les deux environnements — seules les variables
   d'environnement diffèrent.

### 12.3 Restauration : dump complet pour `public`, données seules pour `auth`

Une restauration en données seules sur une base préexistante achoppe sur l'ordre
des clés étrangères et sur les déclencheurs. Traitement :

- **`public`** : dump **schéma et données** de la production, restauré dans une
  base de test vidée au préalable. L'ordre des dépendances est alors géré par
  `pg_dump` lui-même, et la dérive de schéma entre test et production disparaît
  par construction — le test reçoit à chaque fois le schéma exact de la prod.
- **`auth`** : **données seules**. Le schéma `auth` est géré par Supabase et
  existe déjà dans un projet neuf ; le recréer casserait le service
  d'authentification. Les sessions et jetons de rafraîchissement sont **exclus**
  de la copie : ils sont propres au projet d'origine et invalides ailleurs. Les
  mots de passe, eux, sont des empreintes portables et se copient.
- Restauration avec `--no-owner --no-privileges` : le dump référence des rôles
  Supabase propres au projet source, qui provoqueraient sinon des erreurs de
  rôle inexistant.

### 12.4 Storage : fichiers et métadonnées doivent rester cohérents

Les objets ont deux faces : les fichiers stockés et les lignes `storage.objects`
en base. Copier l'une sans l'autre produit soit des liens morts, soit des
fichiers orphelins. Les deux sont copiés dans la même resynchro, et le contrôle
final compare les décomptes de part et d'autre.

### 12.5 Reprise après échec

Une resynchro interrompue en cours laisse le test dans un état partiel. Le
traitement retenu est la **rejouabilité** plutôt que la transaction géante :
relancer le workflow repart d'une base vidée et refait la copie complète. Le
backend expose l'état et la date de la dernière resynchro réussie, affichés dans
le bandeau, afin qu'un état partiel soit visible plutôt que silencieux.

### 12.6 Suivi côté interface

La copie dure plusieurs minutes. Le bouton ne se contente pas de déclencher : il
suit l'exécution du workflow et affiche son avancement, puis son issue. Un
déclenchement pendant qu'une resynchro tourne est refusé par le verrou de
concurrence, avec un message explicite.
