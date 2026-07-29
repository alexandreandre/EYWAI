# Environnement de test — guide d'utilisation

Date : 2026-07-29

## En une phrase

Il existe désormais **deux EYWAI** : celui de tous les jours, et une copie sur
laquelle on peut tout essayer sans rien casser.

## Les deux environnements

| | Production | Test |
|---|---|---|
| Adresse | `sirh-frontend-505040845625.europe-west1.run.app` | `sirh-frontend-test-505040845625.europe-west1.run.app` |
| Données | les vraies | une **copie** des vraies |
| Conséquences | réelles | aucune |
| Reconnaissable à | rien de particulier | un **bandeau orange** en haut de chaque page |

Les identifiants sont les mêmes des deux côtés. Chacun retrouve ses droits
habituels dans le test.

## La règle à retenir

**Le test copie la production. La production n'a jamais connaissance du test.**

Ce qui est fait dans le test — une démission, une suppression, un bulletin
généré — n'existe que là. Ce qui est fait en production ne descend dans le test
qu'au moment d'une resynchro, décidée à la main.

## Ce qui ne peut pas partir depuis le test

Les données étant réelles, trois sorties sont bloquées pour éviter d'atteindre
de vraies personnes :

- **Les e-mails** partent tous vers une boîte unique, jamais aux salariés. Le
  destinataire prévu est indiqué dans l'objet du message.
- **La signature électronique** est refusée : aucun salarié ne reçoit de
  demande de signature.
- **Le dépôt de DSN** est refusé : rien n'est transmis à l'URSSAF.

Ces blocages ne sont pas une consigne mais un verrou technique : le service de
test **refuse de démarrer** si la redirection des e-mails n'est pas configurée.

## La resynchro

Le bouton « Resynchroniser depuis la prod », dans le bandeau orange, remet le
test à l'état exact de la production.

**Elle efface tout ce qui a été fait dans le test.** Une démission d'essai, un
bulletin généré pour voir, une fiche modifiée : tout disparaît et est remplacé
par les données réelles du moment.

À lancer quand une nouveauté vient d'être livrée en production, ou quand le test
a trop dérivé. Prévenir les personnes qui testent avant de le faire. La date de
la dernière resynchro est affichée en permanence dans le bandeau.

## Bonnes pratiques

**Pour les personnes qui testent**

- Tout essayer dans le test, y compris ce qu'on n'oserait jamais faire en
  production : sortir un salarié, supprimer une fiche, lancer une paie.
- Vérifier le bandeau orange avant toute manipulation destructrice. Pas de
  bandeau = production.
- Ne pas compter sur la durée : le test peut être remis à zéro à tout moment.
  Ce qui doit être conservé se note ailleurs, avec une capture d'écran.
- Signaler un problème en précisant l'environnement, la date et l'heure.

**Pour l'administration**

- Prévenir avant chaque resynchro.
- Faire valider une nouveauté dans le test avant de la livrer en production.
- La production ne se déploie plus sans approbation explicite (règle de
  révision obligatoire sur l'environnement GitHub `production`).

## Côté technique

**Déployer une branche sur le test**, pour faire valider une nouveauté avant
livraison :

```bash
gh workflow run deploy-test-env.yml --ref <branche>
```

Ne touche jamais la production : services, base et variables sont ceux du test.

**Lancer une resynchro** depuis le bandeau, ou à la main :

```bash
gh workflow run refresh-test-from-prod.yml
```

**Ce que la resynchro copie** : le schéma `public` (schéma et données), les
comptes de connexion (`auth.users` et `auth.identities`), et les fichiers
Storage. Elle rétablit ensuite les droits d'API, supprime la configuration SMTP
héritée de la production et vide les notifications en attente.

**Garantie de non-écriture** : la lecture de la production passe par un rôle
PostgreSQL dédié, `eywai_replica_reader`, dont toutes les sessions sont forcées
en lecture seule. Un `UPDATE`, un `INSERT` ou un `DELETE` y est refusé par le
serveur lui-même — pas par une consigne.

**Conception détaillée** :
`docs/superpowers/specs/2026-07-28-environnement-test-donnees-reelles-design.md`

## Points ouverts

- Les e-mails du test partent tous vers `eywaitest@gmail.com`.
- Le bouton de resynchro nécessite un jeton GitHub à portée restreinte
  (`GITHUB_DISPATCH_TOKEN`) sur le service de test. Sans lui, la resynchro
  reste lançable depuis GitHub.
- **Ne pas créer le secret `SUPABASE_DB_URL`** en l'état. Le job de migrations
  de `deploy.yml` est sauté faute de ce secret, mais le créer ferait échouer
  tout déploiement : les 159 migrations ne sont pas idempotentes
  (`CREATE POLICY` n'accepte pas `IF NOT EXISTS`), et la production n'a aucune
  table de suivi `supabase_migrations.schema_migrations` — la CLI les
  considère donc toutes comme à appliquer. Vérifié sur la base de test le
  2026-07-29. À traiter par un rattrapage d'historique
  (`supabase migration repair`), testé sur le test au préalable.
