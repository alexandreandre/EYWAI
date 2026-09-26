# Données de paie locales — où trouver quoi

Les données de paie réelles (bulletins, DSN, calendriers, pointages, compteurs)
vivent sous **`data/`**, à la racine du dépôt. Ce dossier est gitignoré : rien de
ce qu'il contient ne part sur GitHub.

Ce document ne contient aucune donnée personnelle. Il décrit uniquement *où* les
choses sont rangées.

---

## Règle de déduction

À partir du **type de document**, de la **société** et de la **période**, le
chemin se déduit sans chercher :

```
data/<societe>/<rubrique>/[<AAAA-MM>/]<nom>
```

| Ce que je cherche | Où c'est |
| --- | --- |
| Le calendrier 2026 de Cartol | `data/cartol/calendriers/calendrier-2026.xlsx` |
| La DSN de mai 2026 de MBC | `data/mbc/dsn/2026-05.dsn` |
| Les bulletins de juin 2026 de Comitech | `data/comitech/bulletins/2026-06/` |
| Un bulletin Cegid salarié par salarié | `data/<societe>/bulletins/<AAAA-MM>/md/<MATRICULE>.md` |
| Les pointages de mai 2026 de MBC | `data/mbc/pointages/2026-05/` |
| L'enrichissement salarié de Lewis | `data/lewis/referentiel/` |
| Les jours de repos forfait de Cartol | `data/cartol/calendriers/jour-repos-forfait-2026.xlsx` |
| Les variables de juin 2026 de Colorplast | `data/colorplast/variables/2026-06/` |

### Sociétés

`cartol` · `colorplast` · `comitech` · `lewis` · `maji` · `mbc` · `zone`

Toujours en minuscules, jamais `CARTOL`, `Comitech Composite` ou `MBC`.

### Rubriques

| Rubrique | Contenu | Découpage mensuel |
| --- | --- | --- |
| `calendriers` | calendrier annuel, jours de repos forfait | non |
| `dsn` | déclarations sociales nominatives, une par mois | non (le nom porte le mois) |
| `bulletins` | bulletins Cegid PDF + extraits `.md` par salarié | oui |
| `pointages` | relevés hebdomadaires | oui |
| `variables` | prépa paie, heures sup, primes du mois | oui |
| `compteurs` | CP, ancienneté, IJSS, fractionnement, CET | non |
| `referentiel` | enrichissement salarié, accords, modèles de contrat | non |

### Nommage

- minuscules, tirets, **sans accent, sans espace, sans parenthèse** ;
- période toujours `AAAA-MM` ou `AAAA`, jamais `05-26` ;
- les semaines s'écrivent `semaine-18` ou `semaines-22-a-25`, jamais `S18` ;
- les DSN sont renommées d'après leur mois : `2026-05.dsn`.

### Dossiers transverses

| Dossier | Rôle |
| --- | --- |
| `data/_inbox/` | dépôt des exports WhatsApp à traiter |
| `data/_archive/` | doublons et versions écartées — **rien n'est jamais supprimé** |
| `data/_modeles/` | fichiers d'exemple, sans donnée réelle |
| `data/_manifeste.json` | journal de la migration, permet de tout annuler |

---

## Compatibilité avec les scripts existants

Les anciens emplacements (`Config/`, `Bulletins/`, `CARTOL/`) existent toujours,
sous forme de **liens symboliques** vers `data/`. Les 17 fichiers de code qui
référencent des chemins en dur — dont
`backend/app/modules/admin_import/application/mbc_mod_moi_teams.py` et les outils
de backtest — continuent donc de fonctionner sans modification.

Pour du code neuf, utiliser directement `data/`. Les liens pourront être retirés
quand plus personne n'en dépendra :

```bash
python -m scripts.data_organize.migrer --sans-compat
```

---

## Recevoir des documents par WhatsApp

Elsa envoie les documents de paie par WhatsApp. Le flux :

1. Exporter la conversation depuis WhatsApp (« Exporter la discussion », avec
   les médias) ;
2. déposer le dossier obtenu dans `data/_inbox/` ;
3. lancer l'ingestion.

```bash
cd backend
python -m scripts.data_organize.ingerer              # simulation, ne copie rien
python -m scripts.data_organize.ingerer --appliquer  # range les nouveautés
```

Le script lit `_chat.txt`, identifie les pièces jointes utiles, en déduit
société / rubrique / période — d'abord depuis le nom du fichier, puis depuis le
fil de la conversation quand le nom est muet — et range celles qui manquent.

Chaque pièce est classée en :

| État | Signification |
| --- | --- |
| `nouveau` | absent de `data/`, sera rangé |
| `identique` | déjà présent au bit près, ignoré |
| `divergent` | même emplacement, contenu différent — **à arbitrer à la main** |
| `inclassable` | société ou rubrique indéterminée, listé pour tri manuel |
| `ignoré` | photo, audio, vidéo, ou document personnel hors paie |

**Un export WhatsApp n'est jamais versionné.** Le `.gitignore` couvre
`WhatsApp Chat*/`, `*.zip` et `_chat.txt`. Le contenu de la conversation n'est
jamais recopié : seuls les noms de fichiers et la classification sortent du
script.

---

## Outils

Tous sous `backend/scripts/data_organize/`, à lancer depuis `backend/`.

| Commande | Rôle |
| --- | --- |
| `python -m scripts.data_organize.inventaire` | inventorie et classe, sans rien déplacer |
| `python -m scripts.data_organize.migrer` | simule la migration |
| `python -m scripts.data_organize.migrer --appliquer` | exécute la migration |
| `python -m scripts.data_organize.rollback --appliquer` | annule la migration |
| `python -m scripts.data_organize.ingerer` | simule l'ingestion WhatsApp |
| `python -m scripts.data_organize.ingerer --appliquer` | range les nouveautés |

`convention.py` est la seule source de vérité sur « quel document va où ». Pour
faire évoluer le rangement, modifier ce fichier, puis rejouer
`rollback --appliquer` suivi de `migrer --appliquer`.

---

## Hors de `data/`

- **`~/Desktop/MBC/`** — dossier de travail MBC (calendriers, variables, CET,
  CSE, charges). Non rapatrié : `backend/scripts/fix_rtt_settings.py` y pointe
  en dur, et son mode de mise à jour (téléchargement manuel ou synchronisation)
  n'est pas établi.
- **`backend/scraping/versement_mobilite/fichiers_urssaf/`** — barèmes URSSAF
  publics, sans donnée personnelle : restent versionnés.
