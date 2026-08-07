---
name: questions-elsa
description: >-
  Cherche dans toutes nos sources (export WhatsApp d'Elsa, data/, docs/, Google Drive)
  les réponses aux questions en suspens — celles où l'on attend quelque chose d'Elsa,
  et celles qu'Elsa a posées sans réponse. Produit un rapport sourcé et ingère les
  fichiers trouvés. À utiliser lorsque l'utilisateur tape /questions-elsa, demande
  ce qui est en attente d'Elsa, ou si une réponse existe déjà quelque part.
---

# Questions Elsa (`/questions-elsa`)

## Pourquoi cette commande existe

Des questions restent bloquées alors que la réponse dort déjà dans nos fichiers.
Cas de référence, item #8 d'`afaire.md` : « Compteur JTC attendre récap ELSA » —
le récap était sur WhatsApp depuis le 28 juillet, une note de deux pages jamais
ouverte. Même schéma le 03/08 avec le barème de congés d'ancienneté (photo du
19/06) et les PDF « PROVISION CP », déjà dans `_inbox/`.

Le coût n'est pas le retard, c'est de relancer Elsa pour ce qu'elle a déjà
envoyé.

Argument optionnel : un numéro d'item (`/questions-elsa #11`) pour ne creuser
que celui-là. Sans argument, balayage complet.

---

## Étape 0 — Rafraîchir la conversation

Depuis `backend/` :

```bash
venv/bin/python -m scripts.data_organize.actualiser --appliquer
```

Extrait la conversation Elsa depuis la base WhatsApp locale, sans export manuel
du téléphone, et écrit `data/_inbox/whatsapp-elsa/nouveautes.md`. Si la commande
échoue, continuer avec l'export existant **en le signalant** dans le rapport —
un `_chat.txt` périmé fait manquer précisément les réponses récentes.

Les médias se limitent à ceux téléchargés sur le Mac : une pièce jointe
référencée mais absente du dossier est une **piste**, pas un manque de réponse.

---

## Étape 1 — Collecter les questions, dans les deux sens

### Sens A — nous attendons quelque chose d'Elsa

Lire `docs/afaire.md` **en entier** (~130 lignes). Relever les items portant un
marqueur d'attente ; les formulations varient (« attendre fichier ELSA »,
« attendre récap ELSA », « Attendre compte rendu ELSA », « en attente du fichier
d'Elsa »). Ne pas se fier à un seul motif : lire.

Pour chacun, formuler ce qui est attendu **concrètement** — pas « le fichier
BIC » mais « un BIC par salarié, 238 des 240 n'en ont pas ». C'est cette
formulation-là qu'on va chercher, pas l'intitulé de l'item.

Balayer aussi `docs/` pour les autres attentes marquées (`*-pending.md`, specs,
plans sous `docs/superpowers/`).

### Sens B — Elsa attend quelque chose de nous

Dans `data/_inbox/whatsapp-elsa/_chat.txt`, repérer ses questions directes
restées sans réponse dans les messages suivants. Se limiter aux questions
**actionnables** (une donnée, un arbitrage, un correctif) — pas aux échanges
personnels.

Prudence : une question peut avoir été traitée oralement ou par écran
interposé. En cas de doute, la classer comme telle plutôt que de la présenter
comme ignorée.

---

## Étape 2 — Chercher, quatre sources par question

### WhatsApp

```bash
grep -in "<terme>" data/_inbox/whatsapp-elsa/_chat.txt
```

Varier les termes : le vocabulaire d'Elsa n'est pas celui d'`afaire.md`
(« JTC » / « jours de temps choisi », « BIC » / « RIB » / « coordonnées
bancaires »). Lire le contexte autour du résultat, pas la seule ligne.

**Les pièces jointes portent souvent la réponse** : `< pièce jointe : NNNNNNNN-PHOTO-... >`
→ ouvrir le fichier correspondant dans `data/_inbox/whatsapp-elsa/` avec Read.
Les barèmes, grilles et récapitulatifs arrivent en photo.

### `data/`

Chemin déductible `data/<societe>/<rubrique>/[AAAA-MM]/`. Sociétés : `cartol`
`colorplast` `comitech` `lewis` `maji` `mbc` `zone`. Rubriques : `calendriers`
`dsn` `bulletins` `pointages` `variables` `compteurs` `referentiel`.
Transverses : `_inbox` `_archive` `_acces` `_modeles`.

Chercher par nom de fichier **et** par contenu.

### `docs/`

Une réponse peut déjà être documentée sans qu'`afaire.md` ait été mis à jour.

### Google Drive

MCP `claude_ai_Google_Drive` : `search_files` (`fullText contains '…'` ou
`title contains '…'`), puis `read_file_content` avec le `fileId` **exact**
retourné — ne jamais inventer un `fileId`. Le Drive du client contient des
documents RH réels (convocations CSE, résultats d'élections, procédures).

---

## Étape 3 — Trancher

**Règle centrale : une mention n'est pas une réponse.**

Le 07/08/2026, un `grep "net entreprise"` sur `_chat.txt` renvoyait huit
résultats — dont « je te les ai transféré » — sans qu'aucun identifiant ne
figure nulle part. Conclure « je les ai » était faux. Le fil contenait en
revanche les identifiants applicatifs EYWAI, d'où la confusion.

| Verdict | Condition |
|---|---|
| `RÉPONDU` | La donnée exploitable est là, **et** la source est citée exactement (`fichier:ligne` ou lien Drive) |
| `PISTE` | Le sujet est évoqué, la donnée manque |
| `RIEN` | Aucune trace |

Une occurrence de mot-clé sans valeur derrière tombe en `PISTE`. Si la source
ne peut pas être citée à la ligne près ou par lien, ce n'est pas un `RÉPONDU`.

---

## Étape 4 — Rapport

Écrire `docs/questions-elsa-<AAAA-MM-JJ>.md` :

```markdown
# Questions en suspens — <date>

## Réponses trouvées

### #<n> — <intitulé>
- **Attendu** : <ce qu'il fallait, concrètement>
- **Trouvé** : <la réponse, en clair>
- **Source** : `<fichier>:<ligne>` ou <lien Drive>
- **Suite** : <ce qu'il reste à faire pour clore l'item>

## Pistes (sujet évoqué, donnée manquante)

### #<n> — <intitulé>
- **Trouvé** : <ce qui existe> — **manque** : <ce qui manque>
- **À demander à Elsa** : <formulation prête à envoyer>

## Sans trace

- #<n> — <intitulé>

## Questions d'Elsa restées sans réponse

- [<date>] <question> — `_chat.txt:<ligne>`
```

À l'écran, **résumé court** : le compte par verdict, puis les `RÉPONDU`
seulement. Alexandre ne lit pas les textes longs — le détail est dans le
fichier.

---

## Étape 5 — Ingérer

Uniquement les fichiers rattachés à un `RÉPONDU`. Rien pour un `PISTE`.

1. Télécharger depuis Drive (`download_file_content`, base64) vers
   `data/_inbox/`, en gardant le nom d'origine.
2. Depuis `backend/`, simulation d'abord, **affichée** :

```bash
venv/bin/python -m scripts.data_organize.ingerer
```

3. Puis appliquer :

```bash
venv/bin/python -m scripts.data_organize.ingerer --appliquer
```

États possibles : `nouveau` / `identique` / `divergent` (à arbitrer, ne pas
trancher seul) / `inclassable` / `ignoré`. Un `divergent` remonte dans le
rapport, il ne s'écrase pas.

---

## Interdits

- **Ne pas toucher à `docs/afaire.md`** — Alexandre l'écrit à la main.
- **Ne rien recopier de `_chat.txt` ni de `data/` dans un fichier versionné** :
  le dépôt est **public**. Le rapport cite des chemins et des lignes, jamais le
  contenu nominatif. Les identifiants vont dans `data/_acces/`, gitignoré.
- **Ne pas inventer** une donnée manquante pour clore un item, ni un `fileId`
  Drive.
- **Ne pas conclure « il faut demander à Elsa »** avant d'avoir cherché dans les
  quatre sources — c'est l'erreur que cette commande existe pour éviter.
