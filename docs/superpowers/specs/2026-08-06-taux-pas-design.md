# Taux de prélèvement à la source : suivi RH et récupération par fichier

Point #31 de `docs/afaire.md` : « Taux PAS. Pouvoir voir facilement son taux.
Est-ce qu'il est bien récupéré ? Si on recrute un employé, comment récupérer son
taux ? C'est pas l'interfaçage net-entreprise justement ??? »

## Constat

Le taux PAS de chaque salarié vit dans `employees.specificites_paie.prelevement_a_la_source`
(`taux`, `type_taux`, `identifiant_taux`, `assiette_dsn`, `montant_dsn`). Le moteur
de paie lit `taux` et applique 0 % en son absence.

Sa seule source est l'import des DSN produites par Cegid. Vérifications faites en
production le 6 août 2026 :

- dernier import DSN : période **2026-05**, effectué le 29 juin, pour les 7 sociétés ;
- comparaison base ↔ DSN de mai : **39 écarts sur 241 salariés actifs**, dont
  **7 taux réellement faux** (ANDRE Elsa 10,5 % contre 13,3 % ; PERRIER Raphaël
  1,0 contre 8,1 ; BARAN Robin 9,9 contre 13,8 ; FERCHAUT Louise 3,5 contre 1,5 ;
  MIRZADA Mir Said Jan 1,4 contre 0,8 ; FILLINGER Mathys et DIGUET Pascal sans
  aucun taux contre 5,3 % et 4,2 %) ;
- le bloc JSON ne porte **aucune date de validité** : impossible de savoir de quel
  mois vient un taux, et certains salariés mélangent des champs de mois différents
  (NOBLE Eric : `type_taux` de janvier, `taux` de mai) ;
- `dsn_transmissions` est vide et `NetEntreprisesApiConnector` est un stub déclaré :
  EYWAI n'a jamais déposé de DSN et ne récupère donc **aucun compte rendu métier**.

Le mécanisme réel est confirmé par les DSN de LEWIS : NOBLE Eric déclaré à 3,50 %
en type 13 en janvier, puis 26,80 % en type 01 dès février ; HIRARD Yannick 2,90/13
puis 5,70/01. Le **type 13 est le taux barème** appliqué faute de mieux, le **type 01
le taux personnalisé** que la DGFiP renvoie dans le compte rendu métier après dépôt
de la DSN.

## Objet

Faire du taux PAS une donnée datée et traçable, alimentée par un fichier, et donner
aux RH un écran qui montre d'un coup d'œil qui est à jour et qui ne l'est pas.

Hors périmètre, documenté mais non traité :

- l'appel API automatique à net-entreprises (dépôt DSN, récupération du compte rendu
  métier), qui exige un certificat et une habilitation absents de la base ;
- le service TOPAze, qui donnerait le taux d'un embauché sans attendre la première DSN ;
- l'application du barème par le moteur de paie quand aucun taux n'est connu — un
  changement généraliste à instruire séparément.

## Architecture

### Table `employee_pas_rates`

Historique daté, une ligne par salarié et par période d'origine du taux.

```
id, company_id, employee_id,
periode            -- AAAA-MM, la période du fichier d'où vient le taux
taux               -- numeric(5,2)
type_taux          -- '01' DGFiP, '13' barème, autres valeurs DSN acceptées
identifiant_taux
source             -- 'dsn' | 'crm' | 'manuel'
source_fichier
applied_at, applied_by
```

Unicité sur `(employee_id, periode, source)` : redéposer le même fichier ne crée
pas de doublon. Le taux courant continue d'être écrit dans `specificites_paie`,
inchangé pour le moteur de paie.

### Module `backend/app/modules/pas_rates`

Découpage identique aux autres modules (`ijss_tracking` sert de référence) :

- `domain/model.py` — l'enregistrement de taux et le calcul du statut ;
- `application/ingest.py` — lit un fichier DSN ou un compte rendu métier avec le
  parser existant `dsn_import.domain.parser`, en extrait les taux, produit un aperçu
  des changements, puis les applique sur confirmation ;
- `application/service.py` — la vue RH : pour chaque salarié, taux courant, origine,
  période, statut, et les compteurs d'en-tête ;
- `infrastructure/repository.py` — accès à `employee_pas_rates` et à `employees` ;
- `api/router.py` — routes réservées aux profils RH.

### Statuts

Calculés dans le domaine, testés unitairement :

| Statut | Règle |
| --- | --- |
| `a_jour` | type 01 et période du taux dans les deux derniers mois |
| `bareme` | type 13 : la DGFiP n'a pas encore renvoyé de taux personnalisé |
| `a_rafraichir` | période du taux antérieure de plus de deux mois |
| `manquant` | aucun taux connu, donc 0 % appliqué sur le bulletin |
| `ecart` | le fichier déposé donne un taux différent de celui en base |

`ecart` n'est pas un statut stocké : il naît de la comparaison faite à l'aperçu.

### Routes

```
GET  /api/pas-rates                      liste + compteurs, société active
GET  /api/pas-rates/{employee_id}        historique d'un salarié
POST /api/pas-rates/preview              fichier -> diff, sans écriture
POST /api/pas-rates/apply                applique un diff confirmé
GET  /api/pas-rates/export               export Excel
```

### Page `/taux-pas`

Rejoint la famille des écrans `/suivi-…` que les RH connaissent.

- bandeau de compteurs cliquables qui filtrent le tableau ;
- tableau : salarié, société, taux, origine (DGFiP ou barème), période du taux, statut ;
- bouton « Mettre à jour les taux » : dépôt d'un fichier, aperçu ligne à ligne
  (`ANDRE Elsa 10,5 % → 13,3 %`), puis application ;
- export Excel sur le modèle du point #7.

## Flux de données

1. Elsa dépose un fichier — DSN mensuelle ou compte rendu métier téléchargé sur
   net-entreprises.
2. Le parser en extrait, par salarié, le dernier versement porteur d'un PAS.
3. L'aperçu compare au taux en base et classe chaque ligne : inchangé, nouveau,
   modifié, salarié non reconnu.
4. À la confirmation, chaque ligne modifiée écrit une entrée dans `employee_pas_rates`
   et met à jour `specificites_paie`.
5. La page reflète immédiatement les nouveaux statuts.

Le rapprochement salarié se fait sur le NIR quand il est présent (13 chiffres, même
règle que le module d'import DSN), sinon sur nom et prénom normalisés. Les salariés
non rapprochés sont listés, jamais créés.

## Traitement des erreurs

- Fichier illisible ou d'un autre SIREN que la société active : refus explicite,
  aucune écriture.
- Salarié du fichier absent de la base : signalé dans l'aperçu, ignoré à l'application.
- Taux absent du fichier pour un salarié connu : la ligne est laissée telle quelle,
  jamais remise à zéro.
- Application partiellement en échec : les lignes réussies sont conservées, les
  échecs listés. L'opération est rejouable sans effet de bord.

## Tests

- Domaine : calcul de statut sur chaque cas, y compris la frontière de deux mois.
- Ingestion : sur les DSN réelles présentes dans `data/*/dsn/` — sept sociétés,
  cinq mois — la transition de NOBLE Eric 3,50/13 → 26,80/01 sert de cas témoin.
- Idempotence : deux applications successives du même fichier ne produisent qu'une
  entrée d'historique.
- API : accès refusé hors profil RH, cloisonnement par société.

## Réserves

Le compte rendu métier partage le format à blocs de la DSN, mais aucun fichier réel
n'est disponible pour le vérifier. L'ingesteur est écrit tolérant et validé sur les
DSN ; un vrai compte rendu métier devra confirmer les dernières rubriques.

Un salarié recruté récupère son taux au prochain fichier déposé, pas immédiatement.
