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

Le prompt décrit les arguments d'`absence_summary` comme
`{"status": "<statut>", "type": "<type>"}` sans énumérer les valeurs valides. En
base, les valeurs réelles sont `type = arret_maladie | arret_at | sans_solde` et
`status = validated`.

Les modèles proposent donc `type: "maladie"`, `status: "validé"` — la requête
part, ne remonte rien, et la synthèse construit une réponse sur un ensemble vide.
C'est le pire des cas : pas une erreur, une **réponse fausse silencieuse**.
Le typage strict de `domain/tools.py` valide la *forme* des arguments, jamais leur
*domaine de valeurs*.

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

## 5. Plan proposé

### Lot 1 — Donner à l'assistant le texte des conventions *(impact maximal)*

Le texte de base complet est déjà rapatrié depuis KALI puis jeté. Le conserver
dans une colonne dédiée (`collective_agreement_texts.base_text`), sans toucher à
`full_text` dont le moteur de paie dépend, puis faire lire cette colonne au
copilot en repli sur `full_text`.

Zéro appel KALI supplémentaire, zéro régression paie possible puisque la colonne
existante n'est pas modifiée. Une resynchronisation des trois conventions
assignées suffit à couvrir les sept sociétés.

À prévoir dans la foulée : au-delà de ~200 k caractères, découper le texte et ne
retenir que les sections pertinentes à la question plutôt que tout envoyer — sinon
la précision se dégrade et la latence grimpe.

### Lot 2 — Réparer les deux défauts d'architecture

- Exécuter les outils **avant** de retourner la réponse convention, et permettre à
  une réponse de combiner données et convention (supprimer les `return`
  prématurés de `handle_agent_query`).
- Contraindre le domaine des valeurs de filtres dans `domain/tools.py` :
  énumérations validées côté serveur pour `type`, `status`, `employment_status`,
  `contract_type`, et rejet explicite d'une valeur inconnue — plutôt qu'une
  requête qui ne remonte rien. Les énumérer aussi dans le prompt.

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

### Lot 4 — Voir ce qui se passe

Journaliser chaque tour (entreprise, utilisateur, question, routage, outils
appelés, latence, modèle) dans une table dédiée, avec RLS et purge à échéance.
Sans cela, on continuera à améliorer l'assistant à l'aveugle. C'est aussi ce qui
permettra de remplacer le banc d'essai reconstitué par les vraies questions posées.

Et aligner la description de l'interface sur ce que l'assistant sait réellement
faire (retirer « notes de frais » tant qu'aucun outil ne les couvre).

---

## 6. Ordre suggéré

1. **Lot 1**, seul, avec vérification sur le banc d'essai : c'est lui qui décide
   si l'assistant sait répondre à une question de convention.
2. **Changement de modèle** — dépend du lot 1 pour la taille de contexte.
3. **Lot 2**, qui supprime deux catégories de réponses fausses.
4. **Lot 4** avant le **lot 3**, pour élargir le catalogue d'après l'usage réel
   plutôt que d'après nos suppositions.

Le banc d'essai se rejoue après chaque lot ; c'est la mesure, pas l'impression,
qui doit dire si ça s'améliore.
