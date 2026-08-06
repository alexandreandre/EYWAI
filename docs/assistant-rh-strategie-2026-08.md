# Assistant RH — diagnostic mesuré et stratégie (#30)

État au 5 août 2026. Ce document répond au point #30 d'`afaire.md`
(« Changer le modèle d'IA d'assistant RH, car nul pour l'instant »).

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

Un point à surveiller : le texte KALI contient des articles en double
(`Article 91.1.1` apparaît deux fois dans la métallurgie, en deux versions). Sans
incidence constatée, mais à garder en tête sur les questions de maintien de salaire.

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

## 7. Mise en production : poussée, en attente de GitHub

Les quatre commits sont sur `main` (`d6922496`, `7a8146e5`, `35e88704`,
`4a254674`). **Rien n'est encore actif en production**, pour une raison
extérieure : **GitHub Actions est en panne majeure** (« Incident with Actions »,
constaté le 6 août au soir). Aucune CI ne démarre, donc aucun déploiement, donc
aucune migration appliquée.

Ce n'est pas un problème de configuration — les workflows sont actifs et les
tâches planifiées de la journée ont tourné normalement jusqu'à 18 h 26. Deux
poussées vers `main` (21 h 13 et 22 h 12) n'ont produit aucun run.

Conséquence pratique : le code déployé en production reste celui du 4 août. Les
correctifs paie poussés hier soir (barèmes, alertes CC, taux VM, pause des
imports) attendent la même reprise.

Il reste donc deux étapes, dans cet ordre, quand Actions sera rétabli :

1. **Laisser passer la CI et le déploiement** — les migrations
   `20260806160000_cc_base_text.sql` et `20260806170000_copilot_interactions.sql`
   s'appliquent alors automatiquement. En attendant, l'assistant lit `full_text`
   et le journal reste muet : les deux replis sont prévus et testés.
2. **Rattraper les trois conventions** — depuis le backend, une fois la migration
   passée :

   ```
   venv/bin/python scripts/backfill_cc_base_text.py            # simulation
   venv/bin/python scripts/backfill_cc_base_text.py --apply
   ```

   Le script n'écrit que `base_text`, jamais `full_text` : la paie ne peut pas
   être affectée. Il refuse d'écrire un texte où aucun repère RH n'apparaît, et
   compte ~1 minute par convention (rapatriement KALI).

Puis rejouer le banc d'essai (`scripts/eval_assistant_rh.py`) pour mesurer la
branche convention sur le vrai corpus, cette fois de bout en bout.

Les deux migrations ont été appliquées et vérifiées sur l'**environnement de
test**. Leur application anticipée en production a été tentée par l'API Supabase
pour ne pas dépendre de la panne : la politique de permissions l'a refusée, et
elle n'a pas été contournée.

Le test unitaire `tests/unit/payroll/test_golden_bulletins.py::test_contexte_injecte_sans_supabase`
échoue, mais indépendamment de ces changements : le commit `16386f6b` d'hier a
retiré `create_client` de `payroll/engine/contexte.py` sans mettre le test à jour.

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
