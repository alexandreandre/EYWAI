# Extraction autonome de la conversation WhatsApp Elsa

**Date** : 2026-08-07
**Statut** : design validé

## Le problème

La conversation WhatsApp avec Elsa est le canal principal d'arrivée des données de
paie : tableaux de pointage, DSN, listes de salariés, provisions, consignes. La
chaîne de classement existe déjà — `whatsapp.lire()` parse un export, `ingerer`
en déduit société / rubrique / période et range sous `data/` — mais elle part d'un
**export manuel** déclenché depuis le téléphone d'Alexandre.

Conséquence : l'export le plus récent date du 2026-08-02 alors que la conversation
vit tous les jours. Tout ce qu'Elsa envoie entre deux exports est invisible, et
personne ne sait ce qui manque.

## Ce qui rend l'automatisation possible

WhatsApp Desktop (macOS) tient une base SQLite **en clair**, à jour en continu :

    ~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite

Vérifié le 2026-08-07 :

| Élément | Constat |
|---|---|
| Conversation Elsa | `ZWACHATSESSION.Z_PK = 109`, JID `33XXXXXXXXX@s.whatsapp.net` |
| Messages | 5 515, dernier horodaté du jour même |
| Texte | `ZWAMESSAGE.ZTEXT`, lisible |
| Médias téléchargés localement | 611 fichiers, présents sur disque sous `Message/Media/<JID>/` |
| Nom d'origine d'un document | `ZWAMESSAGE.ZTEXT` (ex. `Membres_CSE.xlsx`) |
| Légende du document | `ZWAMEDIAITEM.ZTITLE` (ex. « voici les membres du CSE… ») |

Le couple **nom d'origine + légende** est exactement ce dont `ingerer.classer_piece()`
a besoin : le nom porte souvent la société et la période, la légende comble le reste.

### Limite connue

La base référence 6 272 médias pour cette conversation, mais seuls **611 sont
téléchargés sur le Mac** (l'essentiel de 2026 : 347 en juin, 79 en juillet). Les
autres ne vivent que sur le téléphone. L'export manuel du 2026-08-02 reste donc
en place comme socle historique : on ne le remplace pas, on le complète.

## Architecture

Un seul module nouveau, qui se branche en amont de la chaîne existante.

```
ChatStorage.sqlite  ──▶  extraire_whatsapp  ──▶  dossier d'export  ──▶  ingerer  ──▶  data/<societe>/…
   (lecture seule)                              (_chat.txt + pièces)   (existant)
```

### `backend/scripts/data_organize/extraire_whatsapp.py`

Responsabilité unique : **produire un dossier d'export depuis la base locale**, au
format que `whatsapp.lire()` sait déjà lire. Il ne classe rien, ne range rien.

1. Copie `ChatStorage.sqlite` et ses `-wal` / `-shm` vers un répertoire temporaire,
   puis ouvre la copie en lecture seule (`file:…?mode=ro`). WhatsApp peut tourner
   pendant l'opération ; on n'écrit jamais dans la base d'origine.
2. Résout la conversation par nom de contact (`--contact Elsa` par défaut).
3. Écrit `_chat.txt` **intégral**, régénéré à chaque exécution, au format attendu :

       [07/08/2026 15:48:54] Alexandre: Un certificat cachet serveur…
       [31/07/2026 14:50:12] Elsa: Membres_CSE.xlsx ‎<pièce jointe : 00004421-Membres_CSE.xlsx>

   Intégral et non incrémental, pour deux raisons : `ingerer` a besoin des messages
   voisins pour lever les ambiguïtés de nommage, et un fil complet reste lisible
   sans avoir à recoller des morceaux.
4. Copie les pièces jointes **manquantes seulement**, préfixées du compteur
   attendu. Une pièce déjà présente n'est pas recopiée.
5. Écrit `nouveautes.md` : les messages postérieurs à la dernière extraction,
   pièces jointes et texte simple confondus.

### État

`data/_inbox/.whatsapp-elsa.json` retient l'horodatage du dernier message extrait
et le nombre de pièces copiées. C'est ce qui délimite `nouveautes.md` et alimente
le rapport. Fichier absent = première extraction, tout est neuf.

### Sortie

`data/_inbox/whatsapp-elsa/` — dossier canonique, régénéré. Distinct de
`whatsapp-elsa-2026-08-02/`, l'export manuel, qui n'est jamais touché.
`whatsapp.trouver_exports()` remonte les deux ; le dédoublonnage par empreinte de
`ingerer` fait que traiter les deux ne crée pas de doublon.

### `backend/scripts/data_organize/actualiser.py`

Une commande pour la chaîne complète :

    python -m scripts.data_organize.actualiser              # simulation
    python -m scripts.data_organize.actualiser --appliquer  # extrait, range, rapporte

Elle enchaîne `extraire_whatsapp` puis `ingerer`, et produit un rapport unique.

## Ne rien perdre

Le classement automatique ne voit que les fichiers de paie. Or une part de
l'information passe en texte : « je te renvoie les codes net-entreprise »,
« pas de CSE sur Comitech/Colorplast/Zone 404 ». Le rapport comporte donc trois
volets, du plus actionnable au plus brut :

1. **Rangé** — fichiers copiés, avec leur destination sous `data/`.
2. **À trancher** — pièces jointes utiles dont la société ou la rubrique reste
   indéterminée, et conflits (même emplacement, contenu différent). Elles restent
   dans le dossier d'export, jamais supprimées.
3. **Nouveautés du fil** — `nouveautes.md`, le texte des messages depuis la
   dernière extraction. C'est là que se lisent les engagements, les décisions et
   les documents promis mais pas encore envoyés.

Le volet 3 est destiné à être lu par Claude, qui en tire ce qui doit remonter dans
`docs/afaire.md` ou dans une mémoire. Aucun tri automatique n'est tenté sur le
texte : la valeur est dans la lecture, pas dans une heuristique.

## Confidentialité

Le dépôt est public ; `data/` est gitignoré. `_chat.txt` et `nouveautes.md` y
restent, comme l'export manuel aujourd'hui. Aucun contenu de conversation n'entre
dans le code, dans un test ou dans un document versionné — la règle déjà établie
pour les données nominatives s'applique telle quelle.

## Pour que Claude s'en serve seul

Une mémoire `whatsapp-elsa-extraction.md` (type `project`) décrit la commande, ce
qu'elle produit et quand la lancer : dès qu'Alexandre évoque un échange avec Elsa,
un document qu'elle aurait envoyé, ou une donnée manquante susceptible d'être
arrivée par WhatsApp. Ligne correspondante dans `MEMORY.md`.

## Tests

- Extraction sur la base réelle copiée : `_chat.txt` reparsé par `whatsapp.lire()`
  redonne le bon nombre de messages et les bonnes pièces jointes.
- Rejouabilité : deux exécutions consécutives ne copient rien la seconde fois et
  laissent `nouveautes.md` vide.
- Format : une ligne d'export générée est acceptée par `_RE_ENTETE` et
  `_RE_PIECE_JOINTE` de `whatsapp.py`.
- Média absent du disque : la pièce est mentionnée dans `_chat.txt` mais le
  fichier manque ; `ingerer.analyser()` doit l'ignorer sans lever d'erreur.
- Base verrouillée par WhatsApp en cours d'écriture : l'extraction aboutit.

## Hors périmètre

- Récupérer les médias qui ne sont pas sur le Mac (ils sont sur le téléphone).
- Écrire dans WhatsApp, répondre, ou déclencher quoi que ce soit côté application.
- Toute autre conversation que celle d'Elsa (le paramètre `--contact` existe, mais
  rien d'autre n'est visé aujourd'hui).
