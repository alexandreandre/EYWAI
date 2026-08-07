# `/questions-elsa` — design

**Date** : 2026-08-07
**Statut** : validé

## Problème

Des questions restent en suspens des deux côtés alors que la réponse existe
déjà quelque part. Le cas de référence est l'item #8 d'`afaire.md` : « Compteur
JTC attendre récap ELSA » — le récap était sur WhatsApp depuis le 28 juillet,
une note de deux pages jamais ouverte. Même schéma le 03/08 avec le barème de
congés d'ancienneté (photo du 19/06) et les PDF « PROVISION CP ».

Le coût n'est pas seulement le retard : on relance Elsa pour quelque chose
qu'elle a déjà envoyé.

## Portée

Les deux sens :

- **Nous → Elsa** : items d'`afaire.md` portant un marqueur d'attente
  (« attendre fichier / récap / compte rendu ELSA »). Au 07/08 : #3 BIC,
  #4 adresses e-mail, #11 élus CSE, #12 exports CSE et BDES, #22 arrondi des
  congés, #25 dates des entretiens annuels.
- **Elsa → nous** : ses questions directes dans `_chat.txt` restées sans
  réponse dans les messages suivants.

Balayage complet à chaque lancement — pas d'état incrémental. Une question
ajoutée aujourd'hui doit pouvoir trouver une réponse vieille de six mois, ce
que l'incrémental raterait par construction (c'est exactement le cas #8).

## Sources

| Source | Accès |
|---|---|
| Conversation WhatsApp | `data/_inbox/whatsapp-elsa/_chat.txt` + pièces jointes lues avec Read |
| Données locales | `data/` (gitignoré, convention `<societe>/<rubrique>/[AAAA-MM]/`) |
| Documentation | `docs/` |
| Google Drive | MCP `claude_ai_Google_Drive` (`search_files` → `read_file_content`) |

## Discipline de verdict

Règle centrale, tirée de l'incident net-entreprises du 07/08/2026 : **une
mention n'est pas une réponse.** Un `grep "net entreprise"` renvoyait huit
résultats sans qu'aucun identifiant ne figure dans l'export ; conclure « je les
ai » était faux.

| Verdict | Condition |
|---|---|
| `RÉPONDU` | La donnée exploitable est là, et la source est citée exactement (`fichier:ligne` ou lien Drive) |
| `PISTE` | Le sujet est évoqué, la donnée manque |
| `RIEN` | Aucune trace |

Une occurrence de mot-clé sans valeur derrière tombe en `PISTE`, jamais en
`RÉPONDU`.

## Sorties

1. **Rapport** `docs/questions-elsa-<AAAA-MM-JJ>.md`, plus un résumé court à
   l'écran (Alexandre ne lit pas les textes longs).
2. **Ingestion** des fichiers Drive rattachés à un `RÉPONDU` uniquement :
   téléchargement dans `data/_inbox/`, puis
   `python -m scripts.data_organize.ingerer` en simulation affichée, puis
   `--appliquer`. Rien n'est ingéré pour un `PISTE`.
3. **Aucune écriture dans `afaire.md`** — Alexandre l'écrit à la main.

## Forme

Skill markdown pur (`.claude/skills/questions-elsa/SKILL.md`), comme `/elsa`.
Pas de script Python : les marqueurs d'attente d'`afaire.md` sont de la prose
libre aux formulations variables, qu'une lecture directe des ~130 lignes traite
mieux qu'un regex. Pas de fan-out de sous-agents non plus — le coût des faux
positifs augmente avec le nombre de lecteurs indépendants, et la valeur du
résultat tient à la rigueur du verdict, pas au débit.

## Hors périmètre

- Mise à jour automatique d'`afaire.md`.
- Rédaction des relances à envoyer à Elsa.
- Recherche dans les e-mails (connecteur Gmail non autorisé).
