# Reprise des dates d'entretiens annuels

**Date** : 2026-08-07
**Point** : `docs/afaire.md` #25
**Statut** : validé

## Constat

Elsa a demandé la « reprise des dates entretiens annuels et des 6 ans » (WhatsApp du
22/07/2026, répondu « Non » à l'époque). Le fichier n'était pas à attendre : elle l'a
envoyé le **27/07/2026 à 18h05** — `Planif_entretiens.xlsx`, sous
`data/_inbox/whatsapp-elsa/` et `data/_inbox/whatsapp-elsa-2026-08-02/` (même fichier au
bit près, md5 `896247ac…`), avec le message « pour la planif entretein annuel ».

Le module `backend/app/modules/annual_reviews/` est complet (13 routes, huit types
d'entretien dont les obligations L6315-1, convocation PDF, signature Yousign, écran
Formation > Pilotage, onglet fiche salarié). **La table `annual_reviews` est vide en
production : 0 ligne.** Rien n'a jamais été saisi, donc aucun compteur légal ne court.

## Le classeur

256 lignes, 7 colonnes : `Société`, `Nom`, `Prénom`, `Date d'entrée`,
`Dernier entretien`, `Entretien à planifier`, `Règle appliquée`.

La colonne `Règle appliquée` est la vraie information : elle donne **la politique
d'entretien de chaque société**.

| Société | Lignes | Règle |
|---|---|---|
| CARTOL | 108 | tous les entretiens à refaire en novembre 2026 |
| MBC | 58 | dernier entretien + 2 ans, en octobre |
| LEWIS | 43 | reprise, tous à refaire en octobre |
| COMITECH | 22 | entretien annuel chaque année en octobre |
| MAJI | 10 | tous les entretiens en décembre |
| COLORPLAST | 9 | entretien annuel chaque année en octobre |
| ZONE 404 | 6 | à la date d'ancienneté (entrée + 1 an) |

`Dernier entretien` ne contient qu'une **année** (2024 ou 2025), et uniquement pour les
58 lignes MBC (34 en 2024, 20 en 2025, 4 « Aucun »). Les 198 autres lignes sont vides :
aucune date d'entretien passé n'existe pour les six autres sociétés. Rien non plus sur
les bilans de compétences à 6 ans.

## Appariement avec la base (lecture seule, prod)

Normalisation identique à `scripts/import_elus_cse.py` (majuscules, accents et
séparateurs retirés), sur `last_name` **et** `nom_usage`.

- **243 lignes sur 256 appariées**, 0 ambiguïté, 0 homonyme.
- **32 lignes correspondent à des salariés partis** (21 CARTOL, 5 COMITECH, 4 LEWIS,
  2 COLORPLAST) : le classeur a été constitué avant ces sorties.
- **MBC ne colle pas** : 58 lignes pour 75 actifs. 13 noms du classeur sont introuvables
  chez nous, et 30 de nos actifs MBC ne figurent pas au classeur.
- Les six autres sociétés couvrent la totalité de leurs actifs.
- Restent donc **211 entretiens à planifier** et **43 entretiens passés** à reprendre.

## Décisions

### 1. Le type d'entretien se déduit du statut

Le classeur ne dit pas de quel type d'entretien il s'agit. Les huit types existent déjà
(`domain/interview_types.py`) et Elsa les avait listés le 17/06. On déduit :

| Statut du salarié | Type créé |
|---|---|
| forfait jour | `annual_forfait_jour` |
| cadre | `annual_cadres` |
| autre | `annual_performance` |

C'est la même règle que celle déjà appliquée par `compute_planning_suggestions`, donc
l'import et les suggestions ne se contrediront pas.

### 2. Aucune date n'est inventée

`annual_reviews` porte à la fois `year` (entier) et `completed_date` (date, nullable).
Un « dernier entretien 2024 » est repris en `year = 2024`, `status = realise`,
**`completed_date = NULL`**, provenance écrite dans `rh_notes`.

C'est suffisant : `_has_covered_review` raisonne sur `year`, pas sur la date. Et ça
respecte la règle maison — on ne fabrique pas une donnée qu'on n'a pas (cf. les adresses
e-mail, point #4).

### 3. Les salariés partis sont ignorés

Même comportement que l'import des élus CSE : signalés dans le compte rendu du script,
jamais écrits.

### 4. La règle de campagne devient un réglage société, pas une ligne de script

C'est le point qui décide de la valeur à cinq ans. Si les mois de campagne restent dans
le script d'import, il faut nous rappeler chaque automne. En réglage société, EYWAI
propose seul la campagne suivante, et la RH change le mois sans nous.

Nouvelle table `company_interview_settings`, une ligne par société, suivant le patron
`company_<domaine>_settings` déjà utilisé quinze fois (`company_leave_settings`,
`company_work_medal_settings`, `company_punch_accounting_settings`…) :

| Colonne | Rôle |
|---|---|
| `campaign_mode` | `mois_fixe` ou `anniversaire_embauche` |
| `campaign_month` | 1..12, obligatoire en `mois_fixe`, nul sinon |
| `periodicity_years` | 1 par défaut ; 2 pour MBC |
| `enabled` | faux par défaut : aucune société ne change tant qu'on n'a pas réglé |

Défaut volontairement inerte, comme pour le JTC : tant qu'une société n'est pas réglée,
elle ne voit rien de nouveau.

### 5. Les suggestions couvrent enfin tout le monde

`compute_planning_suggestions` ne regarde aujourd'hui que les cadres et les forfaits
jour — soit une petite minorité de l'effectif. Une fois le réglage société posé, la
même fonction propose la campagne à tous les salariés actifs de la société, avec la
date calculée depuis le réglage et le dernier entretien connu.

## Vérification croisée

Le script de reprise ne reprend pas la colonne « Entretien à planifier » : il recalcule
chaque échéance avec `next_campaign_date`, puis la compare à la colonne du classeur et
refuse d'écrire au moindre écart. Simulation du 07/08/2026 sur la base de production
(lecture seule) : **0 divergence sur 211 échéances**. Le moteur et le classeur d'Elsa
disent exactement la même chose, société par société.

## Ce qui reste à demander à Elsa

1. L'écart MBC : 58 lignes au classeur pour 75 salariés actifs — 13 noms qu'on ne
   connaît pas, 30 des nôtres absents.
2. Les dates réelles des entretiens professionnels et des bilans à 6 ans : le classeur
   n'en porte aucune, alors que ce sont les deux obligations légales du L6315-1.
3. Confirmation que MBC est bien en cycle de deux ans quand les six autres sont
   annuelles.
