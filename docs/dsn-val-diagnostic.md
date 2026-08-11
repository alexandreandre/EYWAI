# DSN-VAL — ce que le validateur officiel reproche à notre export

**10/08/2026, dernière passe : les cinq sociétés passent à ZÉRO anomalie.**
Même verdict que les fichiers du cabinet — nos cinq DSN de mai 2026 sont
déposables au sens du validateur. Le détail du chemin 587 → 0 est en fin de
document (« La passe finale »). Les montants restent l'affaire du backtest :
zéro anomalie = déposable, pas juste.

**10/08/2026.** Première passe de nos DSN dans **DSN-VAL 2026.1.0.16**, l'outil
de contrôle de la CNAV distribué par net-entreprises. Il répond à la question du
point #20 : *qu'est-ce qui empêche notre DSN d'être déposable ?*

Jusqu'ici on ne savait que mesurer un **écart** avec le fichier du cabinet
(`dsn_conformance_report.py`). On sait maintenant mesurer une **conformité**.
Ce n'est pas la même chose : sur Colorplast, l'écart au cabinet tenait en
5 rubriques manquantes, quand le validateur en trouve 602 bloquantes.

## Le résultat

| Société | Première passe | Tri des rubriques | + 4 blocs | + prévoyance, net social, PAS | Passe finale | Cabinet |
|---|---|---|---|---|---|---|
| Cartol | 7 250 | 1 378 | 1 035 | 286 | **0** ✅ | 0 |
| Mont Blanc Composite | 6 027 | 1 196 | 904 | 114 | **0** ✅ | 0 |
| LEWIS | 3 355 | 632 | 469 | 105 | **0** ✅ | 0 |
| Comitech | 1 502 | 294 | 227 | 82 | **0** ✅ | 0 |
| Colorplast | 628 | 106 | 78 | **0** ✅ | **0** ✅ | 0 |
| **Total** | **18 762** | **3 606** | **2 713** | **587** | **0** | **0** |

**Colorplast passe le validateur officiel à zéro anomalie**, même verdict que le
fichier du cabinet. 97 % du chemin fait sur l'ensemble, 34 règles ramenées à 14.

## La cause racine : un ordre, pas un contenu

**15 156 anomalies sur 18 762 venaient d'une seule ligne de code.**

La norme NEODeS impose des rubriques **par numéro croissant** à l'intérieur d'un
bloc. Un lecteur qui rencontre un numéro inférieur au précédent tient le bloc
pour terminé, et déclare absentes toutes les rubriques qui suivent — même
écrites juste en dessous.

Or `_emit_rubriques_dict` émettait « dans l'ordre d'insertion » du dictionnaire.
Notre bloc contrat sortait `.019`, puis `.017`, `.018`, `.020`, `.039`… et
`.016` tout à la fin. D'où 10 575 « absences » de rubriques toutes présentes.

Le fichier du cabinet, lui, est strictement croissant partout.

Détail qui a levé une fausse piste : le cabinet écrit lui aussi
`S21.G00.40.009,'00000'` comme numéro de contrat, et passe à zéro. Les 675
« deux contrats portent le même numéro » ne venaient donc pas de cette valeur
mais du désordre, qui fabriquait des contrats fantômes.

Corrigé dans `domain/writer.py`, verrouillé par deux tests dans
`test_writer_structure.py`.

## Puis quatre manques, tous systématiques

**893 anomalies de plus, levées le 10/08.** Aucune ne demandait quoi que ce soit
au cabinet : les correspondances ont été **dérivées de ses DSN acceptées**, pas
supposées.

| Ajout | Ce que c'est | Règle retenue |
|---|---|---|
| `S21.G00.30.013` | Codification UE | France `01`, UE `02`, EEE et Suisse `03`, reste `04` — vérifié contre les nationalités réelles |
| `S21.G00.40.003` | Statut catégoriel Retraite Complémentaire | cadre → `01`, non-cadre → `04`, sans exception sur 219 contrats |
| `S21.G00.71` | Retraite complémentaire | `RUAA`, le régime unifié AGIRC-ARRCO, seul déclaré par le cabinet sur les sept sociétés |
| `S21.G00.86` | Ancienneté dans l'entreprise | type `07`, en mois révolus depuis l'entrée |

Le bloc 71 avait d'abord été rangé à tort avec la prévoyance : c'est **la
retraite complémentaire**, il ne dépendait donc d'aucune fiche de paramétrage.
Sans lui, le statut catégoriel `40.003` est refusé quelle que soit sa valeur.

Un second piège d'ordre au passage : le bloc ancienneté était émis **avant** le
versement, le cabinet le place après. Le validateur le réclame à cette place.

Les 5 151 tests unitaires passent.

**Le témoin est parfait.** Les cinq fichiers du cabinet, réellement déposés et
acceptés, passent à zéro anomalie. Le validateur ne bruite pas : nos anomalies
sont toutes les nôtres.

**Et elles se comptent en règles, pas en lignes** : 34 au départ, 25 après le
tri, les mêmes sur les cinq sociétés. Ce n'est jamais un chantier de plusieurs
milliers de corrections.

## Ce que la question #17 à Elsa devient

Le point #20 demandait au cabinet « la nomenclature officielle des codes de
cotisation, sans elle notre DSN reste non déposable ». **Le validateur donne le
diagnostic sans elle.** Il nomme chaque rubrique manquante et chaque règle
violée, avec le libellé officiel.

C'est le même schéma que le fichier BIC et la provision CP : la réponse était de
notre côté. La question peut être retirée, ou réduite à ce qui restera après
correction.

## La passe du 10/08 au soir — Colorplast à zéro

Tout ce qui suit est codé et vérifié (5 151 tests) :

- **Blocs 70 par salarié** : repris des DSN du cabinet
  (`dsn_deriver_psc.py --ecrire-salaries`), émis entre le contrat et la
  retraite complémentaire, dans l'ordre du cabinet.
- **Bases 31 refondues** : une par cotisation 059, montant 0,00, identifiant
  d'affiliation en `78.005`, assiette dans un composant `79` type 18, sans
  identifiant OPS. Chaque affiliation déclarée reçoit sa base (CCH-13) — au
  besoin à 0,00 quand le moteur ne calcule pas encore la cotisation (retraite
  supplémentaire) : le manque reste visible, pas masqué.
- **SMIC de la réduction générale** : composant `79` type 01 sous la base 03.
  La clé pérenne est `synthese_net.montant_smic_reduction_generale`, **que le
  moteur ne renseigne pas encore** (`smic_calcule_mois` existe dans les runs,
  il n'est juste pas rangé) ; d'ici là, valeur reprise du cabinet.
- **Montant net social** : bloc `58` type 03 — la paie le calculait déjà.
- **PAS** : `50.007` honnête (01 si identifiant DGFiP connu, 13 sinon),
  `50.008` repris du cabinet en attendant les CRM via Cegid.
- **Bloc 53** rattaché à la rémunération 001, **virgules** proscrites des
  adresses, **CDD** avec date de fin (40.010, la donnée existait) et motif de
  recours (40.021, repris).
- Deux bugs d'ordre en plus du premier : l'ancienneté avant le versement, et le
  bloc 50 émis dans l'ordre d'insertion (un `50.008` après `50.013` ouvrait un
  versement fantôme).

Le cliquet de conformité cotisations passe de 616 à 617 montants divergents :
**un transfert, pas un recul** — la 059 retraite sup était une ligne absente,
elle est devenue une ligne à 0,00 (99 + 617 = 100 + 616).

## La passe finale (10/08 au soir) : 587 → 0

Les quatre sujets du résiduel sont tombés en quatre temps, chacun vérifié
contre les DSN du cabinet, jamais deviné :

**1. « Multi-contrats » : deux bugs distincts, aucun n'était du multi-contrats
(587 → 175).** Les 144 anomalies 51.010/40.009 venaient d'un `contrat_ref`
codé en dur `'00000'` dans le builder, quand le 40.009 du contrat portait
`'00001'` : chaque rémunération pointait un contrat inexistant. Les 281
anomalies 78.005 venaient du **quatrième piège d'ordre du chantier**, côté
lecture cette fois : le parseur de `dsn_deriver_psc.py` n'ouvrait une
affiliation que sur `70.004`, or un bloc 70 peut commencer à `70.005` — deux
affiliations consécutives étaient fusionnées en une, et la reprise perdait la
moitié des affiliations.

**2. Nés hors de France et DOM (175 → 63).** Le cabinet déclare `30.014='99'`
+ `30.015` pour l'étranger — et le pays est souvent **'FR'** (nés à l'étranger
de nationalité française) ; pour les DOM, Mayotte comprise, il déclare
`30.014='97'` + `'FR'`. Aucune règle à déduire : le couple département/pays
est repris tel quel dans `dsn_reprise` par salarié.

**3. Une base 31 par affiliation, jamais plus (63 → ~37).** Quand le bulletin
porte plus de lignes 059 que le salarié n'a d'affiliations, les identifiants
78.005 excédentaires (3, 4…) ne correspondent à aucun bloc 70. Le surplus se
replie sur la dernière affiliation, montants additionnés — la structure suit
les affiliations, le rattachement fin ligne à ligne reste au moteur.

**4. Les petits cas.** Embauchés du mois : périodes 51.001/78.002/58.001
bornées au premier jour du contrat, et ancienneté déclarée **en jours**
(86.002='01', du premier jour inclus : entré le 04/05, 28 jours fin mai) —
zéro mois est refusé. Apprentis : `30.025` (niveau de diplôme préparé) et
`40.010` repris du cabinet. Caractères : la localité (30.010) n'admet ni
apostrophe ni tiret (« L ABSIE », « LE BOURGET DU LAC »), les textes CSL-11
(30.007, 30.016) perdent virgule, barre oblique et tiret entre espaces.

Onze tests verrouillent l'ensemble (`test_builder_individu_contrat.py`,
`test_cotisation_mapping.py`). Les 5 162 tests passent, le cliquet
`test_conformance_reelle.py` est vert sans toucher aux plafonds.

Reste connu, hors validateur : le loader de la reprise vers la base réelle,
l'enrichissement moteur `montant_smic_reduction_generale`, et la validation
d'un second mois — les jeux sont calibrés sur 2026-05 uniquement.

### Notes de chantier (résolu le 10/08 au soir)

Conservé pour l'historique : le bloc 15 vient du paramétrage
(`organismes_complementaires`, dérivé des DSN du cabinet par
`dsn_deriver_psc.py --ecrire`, ordre `15.005` figé). La règle « le statut
détermine l'affiliation » a été **réfutée** en route — trois profils cadres
distincts chez Colorplast — d'où la reprise par salarié. La liste « corrigeable
sans rien attendre » de la passe précédente (SMIC, OPS, 30.013, bloc 53, PAS,
net social, ancienneté, 40.003) est **intégralement traitée**.

Reste transverse, hors validateur : le loader qui portera la reprise
(affiliations, identifiants PAS) vers `specificites_paie` en base — aujourd'hui
elle vit dans les jeux de conformité. Et `write_affiliation` garde un mapping
hérité trompeur (`nb_enfants` → `70.012`) sur son chemin sans `rubriques`,
inutilisé par le builder actuel.

## Rejouer le diagnostic

```bash
cd backend
venv/bin/python scripts/dsn_generer_pour_validation.py   # écrit les 5 sociétés
venv/bin/python scripts/dsn_valider.py --tout            # valide et dépouille
venv/bin/python scripts/dsn_valider.py --rapports-seuls  # redépouille seulement
```

L'installation de DSN-VAL et le contournement macOS sont documentés en tête de
`backend/scripts/dsn_valider.py`. L'outil pèse 110 Mo, il vit dans
`data/_outils/dsnval/` et n'est pas versionné.

**Aucune donnée n'est sortie du poste** : DSN-VAL est une application locale, la
validation ne fait aucun appel réseau.

## Ce que ça vaut comme jalon

Un compteur d'anomalies par société, qui doit tomber à zéro. C'est la première
mesure de conformité DSN qu'on ait qui ne dépende ni du cabinet, ni d'un dépôt
réel.
