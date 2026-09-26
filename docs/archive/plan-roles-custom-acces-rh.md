# Rôles `custom` : plan de remise en état du contrôle d'accès RH

État au 7 août 2026. Découvert en traitant #30 : l'assistant RH refuse les
comptes à rôle `custom`. Le défaut n'est pas dans l'assistant — il est dans la
méthode que 123 appels utilisent pour décider « cet utilisateur est-il RH ici ? ».

> **RÉALISÉ le 7 août 2026** (`ca32ccd8`, `1964accd`). Le § 4 décrit le plan tel
> qu'il avait été conçu ; la mise en œuvre a pris un chemin plus court et plus
> sûr, expliqué au § 6. Les cinq comptes fonctionnent, l'assistant leur est
> ouvert, et leur périmètre est respecté — vérifié sur les comptes réels.

---

## 1. Le défaut

`User.has_rh_access_in_company()` renvoie **`False` pour un rôle `custom`**, quel
que soit son paramétrage réel. Son propre commentaire l'annonce :

```python
if role == "custom":
    # Note: Cette vérification nécessite une requête à la base de données
    # Elle sera implémentée dans user_management.py avec has_any_rh_permission()
    # Pour l'instant, on retourne False et la vérification sera faite côté router
    return False
```

Le contrôle est donc **volontairement incomplet**, à charge pour chaque appelant
de le compléter. C'est un contrat qu'aucun nom de méthode ne rappelle, et qui est
oublié presque partout — y compris dans `AccessControlService.require_rh_access`,
c'est-à-dire dans le service dont c'est précisément le métier.

Le contrôle complet existe pourtant : `can_access_company_as_rh()`, qui traite
`custom` via `has_any_rh_permission()`.

**4 appels** au contrôle complet, **123** à l'incomplet.

## 2. Ce que ça coûte aujourd'hui — mesuré en production

| Fait | Valeur |
|---|---|
| Accès `custom` | 8, répartis sur 5 sociétés |
| Utilisateurs distincts concernés | 5 |
| Comptes avec permissions réellement configurées | **8 sur 8** (15 à 30 grants chacun) |
| Comptes s'étant déjà connectés | **0** |

Leurs permissions sont bien de niveau RH : `payslips.validate`,
`advances.process`, `analytics.view_all`, `contracts.view_all`,
`expenses.approve`, `schedules.validate`…

**Conclusion : le bug est réel mais latent.** Quelqu'un a configuré ces huit
accès avec soin ; personne ne s'en est encore servi. Le jour où on les
distribue, ces utilisateurs se heurtent à « Accès RH requis » sur l'essentiel de
l'application, avec des droits pourtant renseignés. Ce n'est pas un incident en
cours, c'est une mine posée.

Répartition des 123 appels : payslips (14), collective_agreements (10),
access_control (7), absences (7), payroll (6), users (5), recruitment (5), puis
une longue traîne. **64 d'entre eux gardent directement un accès** (levée d'un
403).

## 3. La question à poser à Elsa avant de coder

**Qui sont ces 5 utilisateurs, et doivent-ils exister ?**

- S'ils sont **abandonnés** (paramétrage d'essai jamais distribué) : les
  supprimer règle le sujet utilisateur immédiatement. Le défaut de conception
  reste, mais il redevient une dette tranquille, à traiter sans urgence.
- S'ils sont **prévus** (directeurs, managers à droits sur mesure) : le chantier
  devient bloquant, car ces comptes ne fonctionneront pas le jour de leur remise.

Cette réponse change le calendrier, pas le contenu du plan. Ne pas commencer
sans elle.

## 4. Le plan

### Lot A — Rendre le défaut impossible à reproduire *(le cœur)*

Renommer `has_rh_access_in_company` en **`has_rh_role_only`**. Le nom dit alors
ce que la méthode fait vraiment : elle regarde le rôle, rien d'autre.

Le renommage est l'outil de recherche : il fait échouer les 123 appels d'un
coup. On ne cherche pas les sites à la main, on les fait remonter.

Puis, sur chacun :

- appel qui **garde un accès** (64 cas) → le remplacer par
  `can_access_company_as_rh()`, contrôle complet ;
- appel qui **filtre un affichage** ou choisit une variante → `has_rh_role_only`
  convient, mais doit être commenté sur place pour expliquer pourquoi le cas
  `custom` n'a pas d'importance ici.

Le tri se fait appel par appel. C'est long, mais chaque décision est locale et
lisible. Ne pas automatiser le remplacement : les deux cas ne se distinguent pas
syntaxiquement.

### Lot B — Un test qui verrouille

Deux cas, en test d'intégration, sur un module représentatif puis sur le copilot :

- un compte `custom` **avec** permission RH doit passer ;
- un compte `custom` **sans** permission RH doit être refusé.

Sans ce test, le défaut revient à la première méthode d'accès ajoutée.

Ajouter aussi un test de garde sur le modèle : `has_rh_role_only` renvoie `False`
pour `custom`, **et c'est voulu** — le test documente l'intention pour que
personne ne « corrige » la méthode en y ajoutant un accès base.

### Lot C — Rouvrir l'assistant aux rôles `custom`

Une fois le lot A passé, `require_copilot_rh_user` utilise le contrôle complet et
les comptes `custom` accèdent à l'assistant. Rejouer le banc d'essai
(`scripts/eval_assistant_rh.py`) sous un compte `custom` restreint à une équipe :
c'est le seul cas qui éprouve réellement le périmètre des outils nominatifs,
puisque aucun autre utilisateur n'a de grant scopé aujourd'hui.

### Lot D — Empêcher le retour du contrat implicite

Le vrai problème est qu'une méthode de sécurité pouvait mentir sans que rien ne
le signale. Deux garde-fous, au choix :

- faire lever `has_rh_role_only` si on l'appelle sur un rôle `custom` sans avoir
  déclaré qu'on assume le cas — bruyant, mais définitif ;
- ou, plus simple : n'exposer que `can_access_company_as_rh` hors du modèle, et
  rendre `has_rh_role_only` privé au module `users`.

La seconde est préférable : elle supprime le choix au lieu de le documenter.

## 5. Ordre et précautions

1. Poser la question du § 3. Selon la réponse, le chantier est urgent ou non.
2. **Lot B avant lot A** : écrire les tests d'abord, sur le comportement
   souhaité. Ils échouent, puis le lot A les fait passer — c'est ce qui prouve
   que le renommage a réellement corrigé quelque chose.
3. Lot A par modules, en commençant par `access_control` lui-même (7 appels, dont
   `require_rh_access` qui est le plus symbolique), puis `payslips` (14).
4. Lot C et D ensuite.

**Précaution** : ce chantier touche 64 gardes d'accès. Une erreur ouvre un accès
au lieu de le fermer. Chaque lot passe sur l'environnement de test avant la
production, et le gate sécurité Copilot (`tests/unit/access_control`) est déjà
bloquant dans le déploiement — il faut l'étendre aux tests du lot B.

**Ce chantier n'est pas un point d'`afaire.md`** : c'est de la dette de sécurité
transverse. À arbitrer avec Alexandre avant d'y engager du temps.

---

## 6. Ce qui a réellement été fait, et pourquoi le plan a changé

Le § 4 prévoyait de renommer `has_rh_access_in_company` en `has_rh_role_only`,
puis de trier 123 appels vers `can_access_company_as_rh`. La cartographie a
montré que ce détour était inutile, et même plus risqué.

**Les deux contrôles sont équivalents.** Une fois le cas `custom` traité :

| | méthode du modèle | `can_access_company_as_rh` |
|---|---|---|
| admin plateforme | vrai | vrai |
| admin / rh / collaborateur_rh | vrai | vrai (`role_has_rh_level`) |
| custom | ses permissions RH | ses permissions RH |
| autre | faux | faux |

Router les 123 appels aurait donc produit **exactement les mêmes verdicts**, au
prix de 123 modifications sur des gardes d'accès — soit 123 occasions d'ouvrir
un accès en croyant le fermer. Corriger la méthode fait le même travail en un
seul endroit. L'équivalence est démontrée par un test paramétré : si l'une des
deux dérive, il tombe.

**Comment le cas `custom` est résolu.** Ses droits se lisent en base ; la méthode
du modèle n'y a pas accès. L'accès RH est donc résolu une fois, à la
construction de l'utilisateur (`app/core/security.py`, seul point de
construction), et porté par `CompanyAccess.has_rh_permissions`. Une seule
lecture couvre toutes les entreprises de l'utilisateur — la fonction tourne à
chaque requête authentifiée. Un drapeau non résolu vaut refus, et le refus est
**tracé** : c'est le silence qui avait rendu ce défaut indétectable.

**Un défaut trouvé en rouvrant l'assistant.** Le lot 3 de #30 appliquait la règle
« aucun grant → périmètre entreprise ». Juste pour un admin, faux pour un
`custom`, dont les droits ne viennent QUE de ses grants. DROZ-VINCENT, quinze
permissions en périmètre « équipes » mais pas `employees.view_all`, se voyait
ouvrir les 89 salariés de Mont Blanc Composite. Corrigé : 0 sur cette
permission, 58 sur `schedules.view_all` qu'il détient.

**Un défaut de véracité, du même genre que celui de #30.** Le compte restreint
s'entendait répondre « aucun salarié ne possède de titre de séjour arrivant à
expiration » — alors que sept sont expirés, simplement hors de son périmètre.
Un résultat vide et un refus d'accès sont deux réponses opposées ; ils sont
désormais distingués dans les données transmises à la synthèse.

**Vérifications.** 4 930 tests unitaires, banc d'essai de l'assistant à 20 sur
21, et contrôle sur les comptes de production : admin 89 salariés, custom
restreint 0 ou 58 selon la permission.

## 7. Ce qui reste ouvert

- **Les adresses e-mail.** Quatre des cinq comptes ont une adresse non routable
  (`@…dsn-import.local`, `@eywai.access.local`). Ils ne peuvent recevoir ni
  identifiants ni notification : le correctif les rend fonctionnels, il ne les
  rend pas joignables. À traiter avec Elsa.
- **La granularité du contrôle grossier.** `has_rh_access_in_company` reste un
  portail « cet utilisateur est-il RH ici ? ». Une permission RH suffit à le
  franchir ; c'est le contrôle fin (`require_employee_access`,
  `check_user_has_permission`) qui décide ensuite du détail. Ce fonctionnement
  est antérieur à ce chantier et vaut pour tous les rôles. Le resserrer serait
  un chantier distinct, à arbitrer séparément.
