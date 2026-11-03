# Le site de paie (projet « test ») — guide d'utilisation

Mis à jour : 2026-11-03 (la version du 29/07 décrivait une copie d'essai ; ce n'est plus vrai).

## En une phrase

Le site dit « de test » est **le site où se fait la paie réelle** depuis septembre 2026 :
les données y sont vraies et conservées. Il deviendra la production à la bascule ;
d'ici là, quatre envois y restent coupés.

## Les deux sites

| | Site de paie (projet « test ») | Ancienne production |
|---|---|---|
| Adresse | `sirh-frontend-test-505040845625.europe-west1.run.app` | `sirh-frontend-505040845625.europe-west1.run.app` |
| Données | **réelles**, saisies par la gestionnaire de paie | anciennes, plus mises à jour |
| Utilisé pour | la paie du mois | rien (image du 16/09, déploiement coupé) |
| Reconnaissable à | une pastille orange « Données réelles · envois limités » en haut à droite | pas de pastille |

La version en ligne s'affiche en bas du menu (« Version paie-AAAA-MM-JJ.N ») et dans
`/health` du backend. La donner quand on signale un écart.

## Ce qui ne part pas depuis ce site

Ces blocages sont des verrous du code (`APP_ENV=test`), pas des consignes :

- **E-mails** : ceux de l'équipe RH (accès admin, rh, collaborateur_rh, ou rôle avec
  une permission RH) partent aux vraies adresses ; ceux des salariés partent vers une
  boîte de contrôle unique, le destinataire prévu étant indiqué dans l'objet. Le
  service refuse de démarrer si cette redirection n'est pas configurée.
- **DSN** : aucun dépôt par l'API net-entreprises ; la DSN se dépose à la main.
- **Signature électronique** : refusée, aucun salarié ne reçoit de demande.
- **Cabinet comptable** : la transmission automatique retombe en mode manuel.

## Ce qu'il ne faut pas faire

- **Ne pas « essayer pour voir »** : une sortie, une suppression, un bulletin généré
  sont réels. Pour essayer un geste inconnu, demander d'abord à l'équipe.
- **Ne pas resynchroniser depuis l'ancienne production** : cela effacerait la paie
  réelle. C'est verrouillé trois fois (phrase `EFFACER LA BASE DE TEST` exigée ;
  refus si une société a une reprise de paie, table `company_payroll_takeover` ;
  route `POST /api/test-env/refresh` réservée aux super admins et sans jeton GitHub
  posé). Le workflow « Refresh test from prod » est désactivé depuis le 24/09/2026.
- **Ne pas faire tourner les tests contre cette base** : `backend/tests/conftest.py`
  impose une base factice avant tout import, et les tests unitaires coupent le réseau
  et refusent une vraie base. La dérogation `MARTINE_TESTS_BASE_REELLE=oui` (tests
  d'intégration et e2e seulement) est réservée à une base jetable créée pour ça.

## Sauvegardes

Sauvegarde quotidienne par Supabase, 7 jours, sans restauration à la minute : une
restauration peut perdre jusqu'à une journée de saisie. Le stockage des fichiers
n'est dans aucune sauvegarde (audit du 03/11/2026, R3). Vérifier :
`supabase backups list --project-ref <ref du projet test>`.

## Côté technique

**Déployer** (environ 6 minutes, puis l'E2E rejoue la suite) :

```bash
gh workflow run deploy-test-env.yml --ref <branche>
```

- Refusé si la CI n'est pas verte sur le commit (ou, pour un commit de documentation
  seule, sur le dernier commit de code avant lui) ; une CI en cours est attendue.
- Les jobs qui écrivent passent par l'environnement GitHub `paie-reelle` (relecteur,
  branches autorisées).
- Un déploiement réussi pose l'étiquette `paie-AAAA-MM-JJ.N` (date de Paris) sur le
  commit ; le résumé du run signale un commit qui ne contient pas la version en ligne.
- Trois lignes par changement dans `CHANGELOG.md`, en mots d'utilisatrice.

**Migrations** : jamais automatiques. Une migration s'applique en la nommant au
déploiement, dans une transaction qui l'inscrit aussi au registre :

```bash
gh workflow run deploy-test-env.yml --ref <branche> -f migration=AAAAMMJJHHMMSS_nom.sql
```

Les migrations du dépôt sont idempotentes ; toute nouvelle migration a un horodatage
unique. Le registre de la base de test ne correspond pas encore aux fichiers (audit
du 03/11/2026, R4) : ne pas lancer `supabase db push`.

**Variables du service backend** : le déploiement repose les siennes
(`--update-env-vars`) et garde les autres ; la liste de celles à poser une fois à la
main est en commentaire dans `.github/workflows/deploy-test-env.yml`.

**Conception d'origine** (copie d'essai, juillet 2026) :
`docs/superpowers/specs/2026-07-28-environnement-test-donnees-reelles-design.md`
