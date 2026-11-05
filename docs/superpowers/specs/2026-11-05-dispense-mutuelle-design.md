# Dispense de mutuelle sur la fiche du salarié

Date : 05/11/2026. Origine : retour d'Elsa du 04/11 sur la DSN d'août de MAJI.
Choix validés par Alexandre le 05/11 (« suis tes recommandations »).

## Le problème

À la DSN, Martine affiche « mutuelle absente alors que contrat actif » pour tout
CDI ou CDD dont la fiche n'a pas de formule de mutuelle
(`backend/app/modules/exports/infrastructure/export_dsn.py`, `check_dsn_data`).
Or des salariés ont le droit de ne pas adhérer, par exemple ceux qui sont couverts
par la mutuelle de leur conjoint. Elsa : « Il faut avoir la possibilité de dire OK
pas un problème. » Martine n'a aucune notion de dispense : la RH ne peut pas
faire taire l'alerte, et l'alerte ne lui dit pas quoi faire.

## Ce que dit la loi

Les textes ont été lus sur Légifrance le 05/11/2026 (en vigueur ce jour-là). La
copie mot pour mot est dans `data/_sources/legifrance/2026-11-05-dispenses-mutuelle.md`.

- **D911-2 CSS** : dispenses **de droit**, même si l'acte de l'entreprise n'en
  parle pas. Elles ne valent que pour la santé (« remboursement complémentaire de
  frais occasionnés par une maladie, une maternité ou un accident ») : 1°
  complémentaire santé solidaire (L861-3), jusqu'à la fin de l'aide ; 2° assurance
  individuelle déjà en cours à l'embauche, jusqu'à son échéance ; 3° couverture
  pour les mêmes risques au titre d'un autre emploi, « y compris en tant
  qu'ayants droit ». « Dans tous les cas, l'employeur doit être en mesure de
  produire la demande de dispense. »
- **R242-1-6 CSS** : dispenses « prévues dans l'acte juridique » de l'entreprise.
  Ce sont 1° les salariés embauchés avant une décision unilatérale qui les prévoit,
  et au 2° : a) CDD ou apprenti de 12 mois ou plus ayant une couverture
  individuelle, à justifier par écrit ; b) CDD ou apprenti de moins de 12 mois ;
  c) temps partiel ou apprenti dont la cotisation atteindrait au moins 10 % du
  brut ; d) et e) les mêmes cas que D911-2 1° et 2° ; f) couverture collective par
  ailleurs, y compris comme ayant droit, « à condition de le justifier chaque
  année ». La demande « comporte la mention selon laquelle le salarié a été
  préalablement informé par l'employeur des conséquences de son choix ».
- **D911-5 CSS** : la demande se fait à l'embauche, ou à la mise en place des
  garanties, ou à la date d'effet de l'autre couverture.
- **Prévoyance d'un cadre** : elle ne se dispense jamais (ANI du 17/11/2017,
  art. 1er ; `backend/app/shared/domain/prevoyance_obligatoire.py`). Ce chantier
  n'y touche pas.
- **DSN** (cahier technique 2026.1) : un salarié dispensé n'a pas de bloc
  d'affiliation S21.G00.70 pour la santé, et Martine le fait déjà
  (`dsn_export/application/builder.py`, bloc écrit seulement si `adhesion`).
  Le cahier ne prévoit aucune rubrique « dispense ». La fin d'une dispense en
  cours d'emploi se signale (S20.G00.05.011 = « 03 - Fin de dispense
  d'affiliation » et S21.G00.70.014), mais c'est hors de ce chantier (voir plus bas).

## Les décisions

1. **Les 7 motifs proposés**, chacun avec son article :

| Code | Libellé à l'écran | Source | Ce que Martine demande en plus |
|---|---|---|---|
| `couverture_collective` | Couvert ailleurs par une mutuelle collective (conjoint, parent des enfants, autre employeur) | D911-2 3° ; R242-1-6 2° f | date du dernier justificatif ; rappel au bout d'un an |
| `css` | Bénéficiaire de la complémentaire santé solidaire | D911-2 1° | date de fin de l'aide |
| `assurance_individuelle` | Assurance santé individuelle déjà en cours à l'embauche | D911-2 2° | date d'échéance du contrat |
| `cdd_moins_12_mois` | CDD ou apprenti de moins de 12 mois | R242-1-6 2° b | — |
| `cdd_12_mois_et_plus` | CDD ou apprenti de 12 mois ou plus, couvert à titre individuel | R242-1-6 2° a | — |
| `temps_partiel_10_pourcent` | Temps partiel ou apprenti : cotisation d'au moins 10 % du brut | R242-1-6 2° c | — |
| `anterieur_decision_unilaterale` | Embauché avant une mutuelle mise en place par décision unilatérale | R242-1-6 1° | — |

   Pour les quatre derniers motifs, l'écran rappelle : « valable seulement si
   l'acte de l'entreprise (décision unilatérale ou accord) prévoit ce cas ». Il ne
   pose pas de case à cocher en plus, pour garder l'outil léger.

2. **La demande signée** : une date obligatoire, « Demande signée reçue le ». Il
   n'y a pas de pièce jointe dans ce lot : la loi demande de pouvoir *produire*
   la demande, et la date atteste que la RH l'a. L'écran rappelle que la demande
   doit dire que le salarié a été informé des conséquences de son choix
   (R242-1-6).
3. **Pas de dispense de prévoyance** dans ce lot. L'alerte « prévoyance absente »
   et la règle de la prévoyance des cadres ne changent pas.
4. **Rien de plus à déclarer en DSN** : l'absence de bloc d'affiliation suffit,
   et elle existe déjà.
5. **C'est la RH qui pose la dispense** dans « Modifier la fiche ». Martine ne la
   pose jamais seule, ni à l'import.

## Le modèle

La dispense se range dans le bloc mutuelle de la fiche,
`specificites_paie.mutuelle.dispense` :

```json
{
  "motif": "couverture_collective",
  "demande_recue_le": "2026-09-01",
  "justificatif_recu_le": "2026-09-01",
  "fin_le": null
}
```

- `justificatif_recu_le` sert au seul motif `couverture_collective`. Il est
  obligatoire pour ce motif et vaut d'office la date de la demande.
- `fin_le` sert aux motifs `css` (fin de l'aide) et `assurance_individuelle`
  (échéance du contrat). Il est obligatoire pour ces deux motifs.
- Il n'y a pas de migration : `specificites_paie` est un JSON libre
  (`employees/schemas/requests.py`).
- Une formule de mutuelle choisie (`adhesion: true`) l'emporte : l'enregistrement
  écrit alors `dispense: null`. Le serveur fusionne le bloc mutuelle clé par clé
  (`employees/application/commands.py`, `_merge_json_dicts`) : `null` efface donc
  la dispense, et un import DSN, qui n'écrit que `adhesion`, la garde.

### Dispenses déjà posées le 25/10/2026

Quatre fiches de CDD (Colorplast, Comitech) portent déjà une `dispense`, posée
avant ce format : motif en toutes lettres (« CDD de moins de douze mois »),
`depuis`, `fondement`, `decidee_le`, `piece_a_conserver`, et pas de date de
demande. Martine lit ce libellé comme le motif `cdd_moins_12_mois` (même table
côté serveur et côté écran). L'alerte ne demande donc que la date de la demande
signée, et l'enregistrement de la fiche garde ces notes. Les données ne sont pas
réécrites.

## Le contrôle (une seule fonction)

Une fonction pure, `backend/app/shared/domain/dispense_mutuelle.py` :
`alerte_mutuelle(mutuelle, contract_type, annee, mois) -> str | None`. Elle
renvoie la phrase à afficher, ou `None`. Elle remplace le test en dur de
`check_dsn_data`. La copie de `payroll/exports/dsn.py` n'est plus appelée (le
paquet `payroll/exports` réexporte `exports/infrastructure/export_dsn.py`) : elle
reste telle quelle.

Pour un CDI ou un CDD sans adhésion (le périmètre actuel, inchangé) :

| Situation | Message (après « Salarié X : ») |
|---|---|
| ni formule ni dispense | mutuelle absente. Dans sa fiche (Modifier la fiche, Paie sociale), choisissez sa formule ou, s'il ne veut pas adhérer, posez sa dispense. |
| dispense sans motif connu | dispense de mutuelle incomplète : indiquez le motif et la date de la demande signée dans sa fiche. |
| motif connu, sans date de demande | dispense de mutuelle incomplète : indiquez la date de la demande signée par le salarié dans sa fiche. |
| motif `css` ou `assurance_individuelle` sans date de fin | dispense de mutuelle incomplète : indiquez la date de fin dans sa fiche. |
| `fin_le` antérieure au 1er jour du mois déclaré | dispense de mutuelle finie le JJ/MM/AAAA : choisissez sa formule ou mettez la dispense à jour dans sa fiche. |
| `couverture_collective` dont le justificatif a plus d'un an au dernier jour du mois | justificatif de sa mutuelle collective à redemander (le dernier date du JJ/MM/AAAA, il se renouvelle chaque année). Une fois reçu, mettez sa date dans la fiche. |
| motif `cdd_*` alors que le contrat est un CDI | dispense « CDD » sur un CDI : choisissez le bon motif ou sa formule dans sa fiche. |
| dispense valable | rien |

Chaque message dit où aller et quoi faire. C'est une alerte : elle ne bloque
pas la DSN, comme aujourd'hui.

## L'écran (fiche, « Modifier la fiche », section Paie sociale)

Sous la sélection de la formule de mutuelle, quand aucune formule n'est
choisie :

- la case « Le salarié ne veut pas adhérer (dispense) » ;
- si elle est cochée : la liste des 7 motifs, puis « Demande signée reçue le »
  (obligatoire) ;
- selon le motif : « Dernier justificatif reçu le » (pré-rempli avec la date de
  la demande), ou « Fin de la dispense le » ;
- deux lignes d'aide : la mention « informé des conséquences » (R242-1-6) et,
  pour les motifs de R242-1-6, « valable seulement si l'acte de l'entreprise le
  prévoit ».

Choisir une formule fait disparaître le bloc de la dispense. Un champ obligatoire
vide bloque l'enregistrement, avec un message sous le champ (le formulaire le
fait déjà pour les autres champs).

## Hors de ce lot

- La pièce jointe de la demande signée.
- La dispense de prévoyance d'un non-cadre.
- Le signalement DSN « fin de dispense d'affiliation », quand un salarié dispensé
  adhère en cours d'emploi.
- Le versement santé des CDD très courts (L911-7 III).
- À signaler seulement : sur une fiche de MAJI, le statut dit « Non-Cadre » mais
  la classification dit « Cadre ».

## Les tests

- Domaine (pytest) : chaque ligne du tableau du contrôle, plus « avec adhésion,
  rien » et « contrat autre que CDI ou CDD, rien ».
- `check_dsn_data` : une fiche dispensée et valable n'a plus l'alerte, et
  l'alerte « prévoyance absente » d'un cadre dispensé de mutuelle reste.
- Frontend (vitest) : `buildUpdatePayload` écrit la dispense, l'efface quand une
  formule est choisie, et le schéma refuse une dispense sans date de demande.
- Recette sur le site de test, en mode paie, sur une fiche de test remise en état
  ensuite : poser une dispense « conjoint », la voir disparaître de l'aperçu DSN,
  puis la retirer.
