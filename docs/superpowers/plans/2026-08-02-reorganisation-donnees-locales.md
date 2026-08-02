# Réorganisation des données de paie locales

**Date** : 2026-08-02
**Objectif** : une racine unique, une convention de nommage déterministe, un flux
d'entrée WhatsApp, une mémoire persistante — sans qu'aucune donnée personnelle ne
puisse atteindre GitHub et sans casser un seul script.

---

## 1. Constat (vérifié le 02/08/2026)

### 1.1 Cinq racines pour un même type de document

| Racine | Volume | Contenu |
| --- | --- | --- |
| `Bulletins/` | 377 Mo | bulletins Cegid PDF, pointages, calendriers |
| `Config/` | 88 Mo | DSN, calendriers, enrichissement salarié, bulletins `.md` |
| `CARTOL/` | 4 Mo | RTT, CP, IJSS, variables, indemnités, CET |
| `~/Desktop/MBC/` | hors dépôt | calendriers, variables, CET, CSE, charges |
| `backend/scripts/data/` | — | 1 calendrier Comitech |

998 fichiers : 779 `.md`, 128 `.pdf`, 47 `.xlsx`, 44 `.dsn`.

### 1.2 Le vrai problème n'est pas la duplication, c'est la divergence

Seuls deux fichiers sont identiques au hash près. Les calendriers, eux, existent
en plusieurs versions **de contenu différent** :

```
CALENDRIER 2026.xlsx   Config/MBC/          1,38 Mo   25/06
                       Bulletins/…/06/      1,39 Mo   06/07
                       ~/Desktop/MBC/       9,34 Mo   01/07
```

Trois fichiers, trois contenus, trois dates, aucun moyen de savoir lequel fait
foi. C'est ce qui conduit à redemander au client un document déjà présent.

### 1.3 Incohérences structurelles

- `Config/Lewis/LEWIS/` duplique un niveau et reproduit exactement les rubriques
  de `CARTOL/` à la racine (RTT, IJSS, Variables, CP ancienneté, Prime ancienneté).
- `Config/*/Compteur CP (bulletins de mai)/` contient en réalité
  `bulletins_md_2026-01` à `-06` : le nom ment.
- Nommage des sociétés flottant : `Cartol` / `CARTOL`, `Comitech Composite`,
  `MBC`, `Zone` (fichier `ZONE 404`).
- Artefacts macOS dans les noms :
  `calendrier 2026 CARTOL(Récupération automatique)(Récupération automatique).xlsx`.
- Un `.dsn` Cartol traîne à la racine du dépôt.
- Redondance `Config/*/Pointages/` ↔ `Bulletins/BULLETIN */NN/` (mêmes semaines).

### 1.4 Hygiène git : bonne, sauf deux fuites déjà publiées

`git check-ignore` confirme que `Config/`, `Bulletins/`, `CARTOL/`, `/*.dsn` et
`backend/reports/` sont couverts. **Acquis à préserver.**

Deux fichiers échappent aux règles parce qu'ils sont rangés dans le code, et sont
présents sur `origin/main` :

| Fichier | Donnée exposée |
| --- | --- |
| `backend/scripts/data/calendrier_2026_comitech.xlsx` | 20 onglets nommés = 20 salariés Comitech identifiés |
| `backend/tests/fixtures/timesheets/lewis_june2026_sample.csv` | 5 salariés Lewis : nom, matricule, heures d'entrée/sortie |

L'export WhatsApp (`WhatsApp Chat - Elsa (1)/`, 611 fichiers, 549 Mo) était posé à
la racine du dépôt **sans être ignoré**. Protection posée en préalable.

---

## 2. Décisions de conception

| Question | Décision | Raison |
| --- | --- | --- |
| Où vivent les données | `data/` **dans** le dépôt, gitignoré | Choix utilisateur : accès direct pour Claude Code, jamais en distant |
| Axe d'arborescence | **Société d'abord** | Les sessions sont mono-société (backtest MBC, Cartol RTT…) |
| Période | Dans le nom de fichier, ou niveau `AAAA-MM` là où il y a plusieurs occurrences par an | Évite un niveau vide pour les documents non datés |
| Anciens chemins | **Symlinks de compatibilité**, pas réécriture des 17 fichiers de code | Zéro casse silencieuse, zéro modification du code applicatif (hors-scope) |
| Suppression | **Aucune** | Contrainte utilisateur ; les écartés vont dans `data/_archive/` |
| Réversibilité | Manifeste JSON + script de rollback | Toute la migration est annulable |

### 2.1 Pourquoi des symlinks plutôt que réécrire le code

17 fichiers de code et 6 documents référencent les anciens chemins, dont
`backend/app/modules/admin_import/application/mbc_mod_moi_teams.py` — du code
applicatif, explicitement hors-scope. Réécrire 17 fichiers, c'est 17 occasions de
casser un outil de backtest historique sans s'en apercevoir.

Un symlink à l'ancien chemin garantit que **tout continue de fonctionner à
l'identique**, tout en rendant la nouvelle arborescence canonique. C'est la
lecture fidèle de la contrainte « tout déplacement doit s'accompagner de la mise à
jour des références, sinon des scripts casseront en silence » : l'objectif est
l'absence de casse, et le symlink l'atteint mieux que l'édition de masse.

---

## 3. Arborescence cible

```
data/                                  ← racine unique, gitignorée
├── <societe>/                         cartol colorplast comitech lewis maji mbc zone
│   ├── calendriers/                   calendrier-2026.xlsx, jours-repos-forfait-2026.xlsx
│   ├── dsn/                           2026-01.dsn … 2026-05.dsn
│   ├── bulletins/<AAAA-MM>/           bulletins Cegid PDF + extraits .md par salarié
│   ├── pointages/<AAAA-MM>/           relevés hebdomadaires
│   ├── variables/<AAAA-MM>/           prépa paie, heures sup, primes du mois
│   ├── compteurs/                     CP ancienneté, 10e CP, IJSS, RTT, fractionnement, CET
│   └── referentiel/                   enrichissement salarié, accords, modèles de contrat
├── _inbox/                            zone d'atterrissage des exports WhatsApp
├── _archive/                          versions écartées et doublons — jamais supprimés
├── _modeles/                          ex-`Config/Exemple/`
└── _manifeste.json                    journal des mouvements (réversibilité)
```

### 3.1 Slugs de société (stables, définitifs)

| Sources actuelles | Slug |
| --- | --- |
| `Config/Cartol`, `CARTOL/`, `BULLETIN CARTOL` | `cartol` |
| `Config/Colorplast`, `BULLETIN COLORPLAST` | `colorplast` |
| `Config/Comitech Composite`, `BULLETIN COMITECH` | `comitech` |
| `Config/Lewis`, `Config/Lewis/LEWIS`, `BULLETIN LEWIS` | `lewis` |
| `Config/Maji` | `maji` |
| `Config/MBC`, `BULLETIN MBC`, `~/Desktop/MBC` | `mbc` |
| `Config/Zone` | `zone` |
| `Config/Exemple` | `_modeles` |

### 3.2 Règles de nommage

1. Minuscules, tirets, **sans accent, sans espace, sans parenthèse**.
2. Période toujours `AAAA-MM` (mensuel) ou `AAAA` (annuel), jamais `05-26`.
3. Forme : `<type>-<periode>.<ext>`.
4. Les artefacts (`(1)`, `(Récupération automatique)`, `ok GB`) disparaissent.
5. En cas de collision, le fichier le plus récent garde le nom canonique ; les
   autres partent dans `_archive/` suffixés de leur date de modification.

Exemples — chemin déductible sans chercher :

| Document | Chemin |
| --- | --- |
| Calendrier 2026 de Cartol | `data/cartol/calendriers/calendrier-2026.xlsx` |
| DSN de mai 2026 de MBC | `data/mbc/dsn/2026-05.dsn` |
| Bulletins de juin 2026 de Comitech | `data/comitech/bulletins/2026-06/` |
| Jours de repos forfait 2026 de Cartol | `data/cartol/calendriers/jours-repos-forfait-2026.xlsx` |
| Enrichissement salarié de Lewis | `data/lewis/referentiel/enrichissement-salaries.xlsx` |
| Pointages de mai 2026 de MBC | `data/mbc/pointages/2026-05/` |

---

## 4. Plan d'exécution

### Phase 0 — Sécurisation *(fait avant tout le reste)*

1. Ajouter au `.gitignore` : `WhatsApp Chat*/`, `WhatsApp Chat*.zip`, `_chat.txt`,
   `/data/inbox/`.
   **Vérifiable** : `git status --porcelain | grep -i whatsapp` ne renvoie rien.

### Phase 1 — Cartographie

2. Script `backend/scripts/data_organize/inventory.py` : parcourt `Config/`,
   `Bulletins/`, `CARTOL/`, le `.dsn` racine et `~/Desktop/MBC/`, calcule le hash
   SHA-256 de chaque fichier, en déduit société / type / période, et propose le
   chemin cible.
   **Vérifiable** : un rapport listant 100 % des fichiers, aucun en catégorie
   « inconnu » non justifié.
3. Détecter doublons exacts (même hash) et versions divergentes (même cible,
   hash différent).
   **Vérifiable** : le rapport nomme chaque conflit et le gagnant retenu.

### Phase 2 — Migration réversible

4. Créer l'arborescence `data/`.
5. Déplacer (`mv`, jamais `rm`) chaque fichier vers sa cible ; les perdants d'un
   conflit vont dans `data/_archive/` avec leur date.
   **Vérifiable** : `data/_manifeste.json` contient une entrée source → cible par
   fichier, et le total égale le nombre de fichiers de départ.
6. Écrire `rollback.py` qui rejoue le manifeste à l'envers.
   **Vérifiable** : exécution à blanc listant les mouvements inverses.

### Phase 3 — Compatibilité

7. Poser un symlink à chaque ancien chemin référencé par le code, pointant vers
   la nouvelle cible.
   **Vérifiable** : pour chacun des chemins littéraux extraits des 17 fichiers de
   code, `test -e` renvoie vrai.

### Phase 4 — Vérification d'hygiène git

8. `git check-ignore -v` sur `data/` et sur chaque sous-dossier créé.
   **Vérifiable** : chaque chemin renvoie une règle d'ignore.
9. `git status --porcelain` ne montre aucun fichier de données.
10. Lancer les tests unitaires touchant les chemins de données, sans les modifier.
    **Vérifiable** : même résultat qu'avant migration.

### Phase 5 — Ingestion WhatsApp

11. `backend/scripts/data_organize/whatsapp_ingest.py` :
    - parse `_chat.txt` — grammaire confirmée :
      `[JJ/MM/AAAA HH:MM:SS] Auteur: <nom> ‎< pièce jointe : NNNNNNNN-<nom> >` ;
    - classe chaque pièce jointe par nom d'origine, puis par contexte
      conversationnel (± 5 messages) quand le nom est ambigu ;
    - compare par hash à l'existant : `NOUVEAU` / `IDENTIQUE` / `VERSION DIVERGENTE` ;
    - **dry-run par défaut**, `--apply` pour copier (jamais déplacer, jamais
      supprimer) ;
    - ne recopie **jamais** le texte de la conversation dans le dépôt.
    **Vérifiable** : dry-run sur l'export d'Elsa produisant un rapport chiffré.

### Phase 6 — Documentation et mémoire

12. `docs/donnees-locales.md` — versionné, aucune donnée personnelle : la
    convention, la carte, le mode d'emploi de l'ingestion.
13. Entrée de mémoire « où trouver quoi » + pointeur dans `MEMORY.md`.

### Phase 7 — Restitution

14. Rapport final, et décision demandée à l'utilisateur sur les deux fuites
    GitHub (hors-scope : elles touchent au code applicatif et aux tests).

---

## 5. Hors-scope assumé

- Aucune modification du code applicatif (`backend/app/`) ni des tests : les
  symlinks rendent l'édition inutile.
- Aucune modification de la base de données.
- Aucun commit, aucun push sans accord explicite.
- Aucune suppression de fichier.
- `~/Desktop/MBC/` : rapatrié en copie seulement si l'utilisateur confirme que ce
  n'est pas un dossier synchronisé ; par défaut, inventorié et référencé, pas
  déplacé.
