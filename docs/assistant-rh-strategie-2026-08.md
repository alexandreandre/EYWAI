# Assistant RH — diagnostic mesuré et stratégie (#30)

État au 7 août 2026. Ce document répond au point #30 d'`afaire.md`
(« Changer le modèle d'IA d'assistant RH, car nul pour l'instant »).

> **Où on en est (07/08).** Les lots 1, 2 et 4 sont en production, le corpus des
> conventions est rempli. Résultat mesurable : à « quelle est la durée de la
> période d'essai d'un ouvrier ? », l'assistant répondait « la convention n'en
> parle pas » ; il répond aujourd'hui « 1 mois pour les coefficients 700-710,
> 2 mois pour 720-750, 3 mois pour 800-830 », en citant l'article 3.2 de
> l'avenant — vérifié mot pour mot contre le texte stocké. Routage 15/19 → 17/19.
> Détail des lots livrés au § 5, mise en production au § 7.

Conclusion en une phrase : **le modèle n'est pas la première cause.** Cinq modèles
différents produisent le même routage à un scénario près ; ce qui rend l'assistant
mauvais est en amont — la base documentaire des conventions ne contient pas les
articles qu'on lui demande, deux branches du pipeline s'excluent mutuellement, et
les filtres passés aux outils utilisent un vocabulaire qui n'existe pas en base.

---

## 1. Ce qui a été mesuré

Banc d'essai versionné : `backend/scripts/eval_assistant_rh.py`.

19 situations RH réelles (aide logiciel, convention collective, données du
catalogue, questions hors catalogue, question mixte, tentatives de contournement),
rejouées à travers le pipeline applicatif complet — plan LLM, outils scopés par
entreprise, synthèse — sur la base de **production**, en lecture seule, pour
5 modèles. 95 tours au total.

```
venv/bin/python scripts/eval_assistant_rh.py
venv/bin/python scripts/eval_assistant_rh.py --modeles google/gemini-3.1-flash-lite
```

---

## 2. Les causes, par ordre d'impact

### A. La base documentaire des conventions est une base de *paie*, pas une base RH

C'est de loin le premier problème. Le copilot lit
`collective_agreement_texts.full_text`, alimenté par la synchronisation KALI
(`collective-agreements-kali-sync.yml`), qui a été construite pour le moteur de
paie. `KaliClient.fetch_convention` ne collecte que trois choses :

- les **textes salaires** (avenants « valeur du point » département par département) ;
- les **annexes paie** ;
- un **extrait rémunération** du texte de base, via
  `_extract_remuneration_excerpt()` — articles 7.1 / 7.2, prime d'ancienneté, titre V.

Le texte de base complet est bel et bien récupéré depuis KALI, puis jeté : seul
l'extrait rémunération est conservé.

Vérification sur la production :

| Convention | Sociétés | Taille en cache | « essai » | « préavis » | « congé » |
|---|---|---|---|---|---|
| Métallurgie 3248 | Cartol, LEWIS | 77 298 car. | **0** | **0** | **0** |
| Plasturgie 0292 | Colorplast, Comitech, Mont Blanc | 85 204 car. | 12 | **0** | **0** |
| Bâtiment (non affectée) | — | 105 467 car. | 19 | 2 | 2 |

Le sommaire du texte métallurgie est explicite : « Texte salarial : Ain », « … :
Alpes-Maritimes », « … : Auvergne », « … : Bas-Rhin »… puis « Rémunération (texte
de base) ». Aucun article de la convention elle-même.

Conséquence directe, mesurée : à « quelle est la durée de la période d'essai ? »,
les cinq modèles répondent — correctement, vu ce qu'on leur donne — que la
convention n'en parle pas. À « il y a une prime d'ancienneté ? », tous confirment
son existence mais aucun ne peut donner le barème : l'accord du 16 décembre 2004
qui le porte n'est pas dans le cache.

**Aucun changement de modèle ne corrige cela.** Un modèle plus fort répondra
simplement « je ne trouve pas » avec plus d'élégance.

Un second plafond, découvert en corrigeant le premier : le parcours des sections
KALI s'arrête à `MAX_TEXT_CHARS = 400 000` caractères. Sur la métallurgie 3248,
il tombait **au milieu de la convention** et perdait les titres IV à X — contrat
de travail, durée du travail, congés, rupture. Avec un plafond propre au texte de
base, la convention passe de 406 000 à **838 990 caractères**, et les repères
suivent : « essai » 28 → 96, « préavis » 4 → 43, « congé » 22 → 161,
« licenciement » 4 → 54.

À noter au passage : MAJI n'a **aucune** convention assignée en production ; toute
question conventionnelle y est refusée par construction.

### B. Les branches du pipeline s'excluent, et la branche convention court-circuite les outils

`handle_agent_query` teste dans l'ordre : aide logiciel → convention → données,
chaque branche faisant un `return`. Une question qui relève de deux familles perd
la seconde.

Cas mesuré (`mix1`), « Combien j'ai de CDI, et que dit la convention sur leur
période d'essai ? » : le plan est pourtant *bon* — il demande l'outil
`employee_count{contract_type: CDI}` **et** la convention. Mais le `return` de la
branche convention intervient avant `execute_tool_calls`. Résultat, sur les cinq
modèles : « aucune information ne permet de déterminer le nombre de salariés en
CDI dans votre entreprise » — alors que la réponse était à un appel d'outil.

### C. Les valeurs de filtres sont inventées par le modèle, et ne correspondent pas à la base

Le prompt décrit les arguments comme `{"status": "<statut>", "type": "<type>"}`
sans énumérer les valeurs valides. Le typage strict de `domain/tools.py` valide la
*forme* des arguments, jamais leur *domaine de valeurs*. Deux conséquences
différentes selon la colonne :

- **`absence_requests.type` et `.status` sont des énumérations Postgres.** Le
  modèle propose `type: "maladie"` ; la base attend `arret_maladie`. Postgres
  rejette la valeur (`invalid input value for enum absence_type`), l'outil entier
  échoue et l'assistant répond qu'il n'a pas accès aux données. Panne visible,
  mais systématique.
- **`employees.contract_type` est du texte libre** (`CDI`, `CDD`,
  `Apprentissage`). Le modèle propose `Apprenti` : la requête part, ne remonte
  rien, et l'assistant répond **« aucun apprenti »**. Vérifié en production sur
  Mont Blanc Composite, qui en a deux. Pas une erreur, une **réponse fausse
  silencieuse** — le pire des cas.

### D. Le catalogue d'outils ne recouvre pas les questions du quotidien

Six outils, tous des agrégats : effectifs, recherche par nom, synthèse paie,
synthèse absences, synthèse planning, indicateurs RH. Les questions que pose
réellement une gestionnaire RH — « qui est en arrêt en ce moment ? », « quels
titres de séjour expirent dans trois mois ? », « quel est le salaire de X ? »,
« qui n'a pas signé son contrat ? » — sont toutes hors catalogue.

Sur `hors3` (« Qui est en arrêt maladie ? »), les cinq modèles déclenchent
`absence_summary`, qui ne renvoie que des comptes, puis expliquent qu'ils n'ont
pas accès à l'information. L'utilisateur a attendu quatre secondes pour un refus.

En face, l'interface promet dans sa description que l'assistant « interroge vos
données RH (effectifs, paie, absences, **notes de frais**) » : il n'existe aucun
outil notes de frais. L'écart entre la promesse et le catalogue est lui-même une
partie du « c'est nul ».

### E. La clarification est demandée là où elle n'apporte rien

La règle 4 du prompt de planification impose de demander une précision quand la
question de données est « vague ». Les cinq modèles renvoient donc une question à
« Combien de personnes travaillent chez nous ? » — au lieu de répondre avec
l'effectif actif et de proposer le détail. Trois des cinq font de même sur les
questions hors catalogue, ce qui ressemble à une esquive.

### F. Aucune observabilité

Aucune table ne trace les échanges avec l'assistant, aucun log applicatif ne
conserve le couple question / routage / réponse. On ne sait donc pas ce qu'Elsa
demande réellement, ni ce qui échoue en vrai. Tout ce document repose sur un
banc d'essai reconstitué, faute de données d'usage.

---

## 3. Comparatif des modèles

Toutes valeurs mesurées sur les 19 situations (latence moyenne bout en bout, coût
réel calculé sur les tokens consommés).

| Modèle | Latence moy. | Coût / question | Routage | Rédaction |
|---|---|---|---|---|
| `openai/gpt-4o-mini` *(en place)* | 4,9 s | 0,16 c | 15/19 | la plus faible — signe ses réponses « [Votre Nom], Service RH » |
| `google/gemini-3.1-flash-lite` | **3,1 s** | 0,28 c | 15/19 | claire, explicite sur ce qui manque dans le texte |
| `google/gemini-3-flash-preview` | 5,7 s | 0,64 c | **16/19** | la meilleure structure ; seul, avec Haiku, à traiter correctement l'absence de convention (MAJI) |
| `anthropic/claude-haiku-4.5` | 6,6 s | 1,38 c | **16/19** | bonne, mais tutoie l'utilisateur (registre incohérent) |
| `openai/gpt-5-mini` | **21,2 s** | 0,46 c | 14/19 | réponses **tronquées** : les tokens de raisonnement consomment le `max_tokens=1200` |

Trois enseignements :

1. **Le routage est quasi identique partout** (14 à 16 sur 19), et surtout
   **trois échecs sont communs aux cinq modèles** : `data5` (clarification
   inutile), `hors3` (outil déclenché pour rien) et `mix1` (moitié de la question
   perdue). Ce sont exactement les points B, D et E ci-dessus : le prompt et
   l'architecture, pas le modèle.
2. **Le coût n'est pas un sujet.** Entre le modèle le moins cher et le plus cher
   testés, l'écart est de 1,2 centime par question. À 500 questions par mois sur
   les sept sociétés, on parle de 1 € contre 7 €. Optimiser là-dessus n'a aucun sens.
3. **gpt-5-mini est disqualifié** pour un usage interactif : 21 s de moyenne, et
   le code actuel devrait de toute façon être adapté (budget `max_tokens` séparé
   pour le raisonnement).

---

## 4. Recommandation de modèles

Un modèle par rôle plutôt qu'un modèle unique — la structure de `ai/models.py` le
permet déjà.

| Rôle | Aujourd'hui | Recommandé | Pourquoi |
|---|---|---|---|
| Planification / routage | gpt-4o-mini | `google/gemini-3.1-flash-lite` | le plus rapide (le plan est sur le chemin critique de *chaque* question), routage équivalent |
| Aide logiciel | gpt-4o-mini | `google/gemini-3-flash-preview` | meilleure structure de réponse sur un guide de 25 k caractères |
| Convention collective | gpt-4o-mini | `google/gemini-3-flash-preview` | **et surtout** : contexte 1 M. Une fois le texte de base complet en cache (lot 1), le prompt passera de 25 k à plusieurs centaines de milliers de tokens — gpt-4o-mini plafonne à 128 k et casserait |
| Synthèse finale | gpt-4o-mini | `google/gemini-3-flash-preview` | supprime les signatures fictives et les formules creuses |

Gain attendu du seul changement de modèle : une rédaction nettement meilleure et
plus honnête, environ 1,5 s de latence en moins sur les questions de données. **Cela
ne rendra pas juste une seule réponse aujourd'hui fausse.** D'où les lots qui suivent.

---

## 5. Ce qui a été fait (6 août 2026)

Le lot 1 est écrit et validé, ainsi que les deux correctifs du lot 2 dont
l'absence produisait des réponses fausses. **Rien n'est encore en production :
deux étapes attendent un feu vert, au § 7.**

| Changement | Fichier |
|---|---|
| Colonne `base_text` (+ compteur, date) | `supabase/migrations/20260806160000_cc_base_text.sql` |
| Texte de base rapatrié une fois, conservé au lieu d'être jeté ; plafond propre (1,2 M car.) | `collective_agreements/infrastructure/kali_client.py` |
| Persistance du texte de base | `collective_agreements/{domain/interfaces,infrastructure/providers,application/kali_import}.py` |
| Rattrapage sans re-synchro complète | `backend/scripts/backfill_cc_base_text.py` |
| Lecture de `base_text`, repli sur `full_text` si la colonne n'existe pas encore | `copilot/infrastructure/queries.py` |
| Sélection des sections utiles + sommaire complet joint | `copilot/domain/agreement_context.py` |
| Choix des sections par le modèle à la lecture du sommaire | `copilot/infrastructure/providers.py` |
| Un modèle par rôle | `shared/infrastructure/ai/models.py` |
| Rapprochement des valeurs de filtre | `copilot/domain/filter_values.py`, `infrastructure/secure_queries.py` |
| Deux règles de clarification inutiles supprimées | `copilot/infrastructure/providers.py` |
| Questions mixtes : sources collectées puis synthétisées | `copilot/application/commands.py`, `application/service.py` |
| Période et salariés concernés dans la synthèse d'absences | `copilot/infrastructure/secure_queries.py` |
| Journal des échanges (question, routage, outils, latence) | `copilot/infrastructure/journal.py`, `supabase/migrations/20260806170000_copilot_interactions.sql` |
| Versions d'article remplacées écartées du texte de l'assistant | `collective_agreements/infrastructure/kali_client.py` |
| Garde-fou Supabase du contexte paie recalé (bloquait la CI) | `tests/unit/payroll/test_golden_bulletins.py` |
| Description de l'interface alignée sur le catalogue réel | `frontend/src/components/CopilotModalAgent.tsx` |

Résultats mesurés :

- **Routage : 15/19 → 17/19**, latence moyenne 4,9 s → 4,8 s. Les deux cas
  restants ne sont plus des échecs mais un critère mal posé de ma part :
  `hors3` (« qui est en arrêt ? ») répond correctement « personne aujourd'hui »
  au lieu de décliner, et `mix1` affiche le routage « cc » tout en exécutant ses
  outils. Les deux attentes du banc ont été corrigées, avec le motif écrit.
- **Questions mixtes** : « Combien j'ai de CDI, et que dit la convention ? »
  répond désormais aux deux volets (6 CDI **et** la règle conventionnelle) au
  lieu d'affirmer qu'aucune information ne permet de compter les CDI.
- **Absences** : « Qui est en arrêt maladie en ce moment ? » répondait
  « 4 collaborateurs » — 4 demandes sur tout l'historique, alors que **personne**
  n'était en arrêt ce jour-là. La réponse est maintenant « aucun salarié
  actuellement », vérifiée en base.
- **Convention** (validé hors base, sur le texte réel) : « combien de jours pour
  un mariage ou un décès ? » passait de « l'information ne figure pas dans le
  texte » à la table complète de l'**article 90**, vérifiée ligne à ligne contre
  la source. Idem pour la période d'essai, le préavis et la prime d'ancienneté en
  plasturgie, qui citent maintenant les articles 8, 9, 11, 21 et 28.
- **Apprentis** : « aucun apprenti » → « 2 apprentis », vérifié en base.
- **Absences** : le filtre `type: "maladie"` ne fait plus échouer l'outil ;
  « 3 absences maladie validées, 3 jours » correspond exactement à la base.

Réserve honnête : sur la métallurgie, la sélection retient 120 000 caractères sur
839 000. Le modèle cite désormais les bons articles, mais sur une question très
transverse il peut encore signaler qu'une section n'a pas été reproduite — il le
dit explicitement plutôt que de conclure à tort, ce qui était l'objectif.

Les articles en double repérés dans le texte KALI n'étaient pas un artefact
bénin. KALI renvoie **plusieurs versions du même article** — celle qui s'applique
et celles qu'elle remplace — distinguées par `etat` (`VIGUEUR`, `VIGUEUR_ETEN`,
`REMPLACE`, `ABROGE`) et par `dateDebut` / `dateFin`. Les *sections* étaient
filtrées sur cet état, les *articles* jamais : l'assistant pouvait donc citer un
article périmé comme s'il était en vigueur. Sur la métallurgie, 67 numéros
apparaissaient plusieurs fois avec des contenus différents — trois « Article 19 »
sous le même chapitre « garanties conventionnelles », deux « Article 166 » sur la
cotisation garantie de branche dont un remplacé depuis janvier 2023.

Après filtrage : 839 000 → 688 000 caractères, 570 → 498 articles, 67 → 20
doublons, tous légitimes (mêmes numéros dans des chapitres différents). Les
repères RH sont intacts (« préavis » 43, « congé » 156) : c'est du bruit qui
part, pas du signal.

**Le corpus paie n'est volontairement pas filtré.** Le même défaut l'affecte
probablement — des grilles salariales remplacées y côtoient les actuelles — mais
le corriger changerait le contenu de `full_text`, donc les barèmes extraits. À
traiter séparément, avec un backtest paie.

## 6. Plan proposé

### Lot 1 — Donner à l'assistant le texte des conventions *(fait)*

Le texte de base est conservé dans `collective_agreement_texts.base_text`, sans
toucher à `full_text` dont le moteur de paie dépend. Zéro appel KALI
supplémentaire — le texte était déjà rapatrié, puis jeté. Le copilot lit
`base_text` et retombe sur `full_text` tant qu'une convention n'a pas été
rattrapée.

La sélection de sections (`copilot/domain/agreement_context.py`) évite d'envoyer
800 000 caractères à chaque question. Deux garde-fous : sous 60 000 caractères le
texte part **intégralement**, et le **sommaire complet** est toujours joint, pour
que le modèle puisse dire qu'une section existe mais n'a pas été reproduite —
plutôt que de conclure que la convention est muette.

Deux pièges rencontrés, tous deux corrigés et couverts par des tests :

- un classement lexical par *présence* de mots favorise les sections géantes
  (une section de 56 000 caractères contient tous les mots) : c'est la densité
  qui compte ;
- la barrière de vocabulaire — « combien de jours pour un mariage » ne partage
  aucun mot avec « Congés payés. Congés exceptionnels ». Le modèle désigne donc
  lui-même les sections à lire à partir du sommaire, en un appel court ; en cas
  d'échec, le classement lexical reprend la main.

### Lot 2 — Réparer les défauts d'architecture *(partiellement fait)*

**Fait** — le domaine des valeurs de filtres est contraint côté serveur
(`copilot/domain/filter_values.py`) : rapprochement insensible à la casse et aux
accents, synonymes courants, correspondance par préfixe (`Apprenti` →
`Apprentissage`), et échec **explicite** listant les valeurs acceptées plutôt
qu'un résultat vide. Les valeurs d'énumération sont aussi listées dans le prompt.
Cas limite couvert : une entreprise sans salarié répond « zéro », pas « valeur
inconnue ».

**Fait** — les deux règles de clarification qui renvoyaient une question là où une
réponse existait (`data5`, `cc5`).

**Reste à faire** — exécuter les outils **avant** de retourner la réponse
convention, et permettre à une réponse de combiner données et convention
(supprimer les `return` prématurés de `handle_agent_query`). C'est l'échec `mix1`,
toujours présent.

### Lot 3 — Élargir le catalogue aux vraies questions

Par ordre de fréquence probable côté Elsa : qui est absent / en arrêt à une date,
échéances RH (titres de séjour, visites médicales, périodes d'essai), situation
individuelle d'un salarié (contrat, ancienneté, rémunération) sous contrôle de
permission, état d'avancement de la paie du mois.

Deux garde-fous à conserver : le `company_id` reste imposé par le serveur, et les
outils nominatifs doivent respecter le périmètre RH de l'utilisateur (un RH
restreint à une équipe ne doit pas lire toute l'entreprise). Le point B du
comportement actuel — refuser proprement plutôt qu'inventer — est bon et doit
survivre à l'élargissement.

### Lot 4 — Voir ce qui se passe *(fait)*

`copilot_interactions` enregistre chaque tour : entreprise, utilisateur,
question, routage, outils exécutés, latence, longueur de la réponse. **La
réponse elle-même n'est pas conservée** — seule sa longueur l'est. RLS activée
et droits retirés à `anon`/`authenticated`, comme le reste du schéma ; le backend
passe par `service_role`. Table à purger périodiquement.

L'écriture part dans un fil détaché : le journal ne doit ni empêcher ni ralentir
une réponse. Écrit d'abord de façon bloquante, il faisait passer la suite de
tests de 18 s à 81 s — un bon indicateur de ce qu'il aurait coûté à l'utilisateur.

La description de l'interface a été alignée sur le catalogue réel : elle
promettait d'interroger les notes de frais, qu'aucun outil ne couvre.

---

## 7. Mise en production — et la panne qu'elle a révélée

La panne GitHub Actions du 6 août avait masqué un blocage bien plus ancien :
**aucun déploiement ne passait depuis le 4 août 16 h 52**, et personne ne le
voyait.

`supabase db push` échouait sur :

```
Remote migration versions not found in local migrations directory.
supabase migration repair --status reverted 20260804202547
```

La migration RLS avait été appliquée en production **via l'API Supabase**, qui
génère son propre horodatage (`20260804202547`), puis versionnée dans le dépôt
sous un numéro choisi à la main (`20260804160000`). Deux numéros pour la même
migration : la CLI refusait de continuer. Comme les jobs `test-env` et
`production` dépendent du job migrations, ils étaient *skipped* — et un run
affichait même « success » avec tous les vrais jobs sautés.

Étaient donc coincés : les correctifs paie du 5 août, l'interfaçage compta, les
périodes d'essai, le suivi PAS, et l'assistant RH.

Deux correctifs, poussés le 7 août :

- **`013b14b9`** — le fichier RLS est renommé sur l'horodatage réellement
  enregistré en base, après vérification que le SQL exécutable est identique au
  distant (comparé hors commentaires) ; la migration n'est donc pas rejouée.
- **`7c7724b5`** — `supabase db push --include-all` dans le workflow. Une
  migration écrite ici peut porter un numéro antérieur à la dernière appliquée
  par l'API ; sans ce drapeau, la CLI refuse de l'appliquer. Le cas se
  reproduira tant que des migrations passeront par l'API.

**Règle à retenir : une migration appliquée via l'API Supabase doit être
versionnée dans le dépôt sous son horodatage d'origine, jamais sous un numéro
reconstitué.**

Un troisième obstacle a été levé au passage : le test
`test_golden_bulletins.py::test_contexte_injecte_sans_supabase` échouait sur
`main` et **aurait fait échouer la CI dès sa reprise** (`tests/unit` est
bloquant). Il piégeait `contexte.create_client`, que le module n'importe plus
depuis `16386f6b` ; le piège porte désormais sur `get_supabase_admin_client`,
le point d'entrée réellement utilisé.

**Résultat** : les 7 migrations en attente sont appliquées en production
(vérifié en base), dont `cc_base_text` et `copilot_interactions`. Aucune n'était
destructive — vérifié avant application.

Le corpus des trois conventions est rempli :

| IDCC | Sociétés | `base_text` | « essai » | « préavis » | « congé » |
|---|---|---|---|---|---|
| 3248 métallurgie | Cartol, LEWIS | 707 349 car. | 95 | 43 | 177 |
| 0292 plasturgie | Colorplast, Comitech, MBC | 338 148 car. | 87 | 49 | 151 |
| 1597 bâtiment | *(non assignée)* | 166 846 car. | 16 | 16 | 74 |

Avant : 0, 0 et 0 pour la métallurgie.

Deux pièges rencontrés en appliquant le backfill, tous deux corrigés :

- `set_base_text` avalait l'échec d'écriture et le script annonçait « écrit » :
  une coupure SSL a laissé l'IDCC 0292 **vide** sans que rien ne le signale. La
  méthode renvoie maintenant un booléen, et le script **relit ce qu'il a écrit**
  avant d'annoncer un succès. Le second incident (IDCC 1597) a été détecté
  immédiatement par ce garde-fou.
- le texte de base ne suffisait pas pour la plasturgie : son article 8 renvoie
  aux « avenants particuliers » pour la période d'essai. Ces avenants vivent
  dans les « Textes Attachés » et sont désormais joints au corpus RH
  (`_is_hr_annex`, `198020ce`).

## 8. Suite

Il reste le **lot 3**, délibérément laissé de côté : élargir le catalogue
d'outils. Le faire maintenant reviendrait à deviner ce qu'Elsa demande. Le
journal du lot 4 donnera la réponse en quelques semaines d'usage — c'est
précisément pour cela qu'il a été fait d'abord.

Les candidats pressentis, à confirmer par le journal : qui est absent à une date
donnée (nominatif), échéances RH (titres de séjour, visites médicales, périodes
d'essai), situation individuelle d'un salarié sous contrôle de permission.

Deux garde-fous à conserver le jour où le catalogue s'élargit : le `company_id`
reste imposé par le serveur, et les outils nominatifs doivent respecter le
périmètre RH de l'utilisateur — un RH restreint à une équipe ne doit pas lire
toute l'entreprise.

Le banc d'essai se rejoue après chaque lot ; c'est la mesure, pas l'impression,
qui doit dire si ça s'améliore.
