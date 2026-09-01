# Arrêts maladie en jours calendaires

**Date** : 2026-09-01 · **Origine** : retour de Gaëlle (MAJI) — « serait-il possible de mettre aussi en arrêt le samedi et dimanche car nous devons compter les jours pour la prévoyance »

## Problème

Un arrêt de travail est légalement une période calendaire (Cerfa : date de début, date de fin, week-ends et fériés compris). Le SIRH ne permet pas de le saisir ainsi, et pire, ignore silencieusement les week-ends même saisis à la main :

1. **Saisie jour par jour** : `AbsenceRequestModal.tsx` n'offre qu'un `<Calendar mode="multiple">`. Un arrêt du 17/08 au 18/09 = ~33 clics.
2. **Verrou de projection** : à la validation, `CalendarUpdateProvider.update_calendar_from_days` (`backend/app/modules/absences/infrastructure/providers.py:330`) ne convertit en `arret_maladie` que les jours typés `travail`/`work` du `planned_calendar`. Un samedi/dimanche sélectionné reste `weekend` → **les week-ends ajoutés à la main par la RH sont perdus pour la paie**.
3. **Conséquence paie** : le bulletin reconstruit les dates de l'arrêt à partir des jours typés `arret_maladie` (`payslip_run_heures.py:145-163`, min/max). Un arrêt qui commence ou finit un week-end perd ces jours pour l'IJSS, le maintien employeur et la **prévoyance** — alors que le moteur (`maintien_salaire_service.py`) est, lui, déjà 100 % calendaire.

## Décision (validée par Alexandre le 01/09)

**Approche A** : saisie en période + expansion calendaire côté serveur + déverrouillage de la projection + réparation de l'existant. Le moteur de paie n'est pas modifié.

## Périmètre

### 1. Backend — schéma et commande de création

- Promouvoir `daterange_days` (`dsn_import/domain/dsn_absence_exit_mapping.py:65`) vers `app/shared/domain/` (module partagé) ; le module DSN l'importe depuis là.
- `AbsenceRequestCreate` (`absences/schemas/requests.py`) : ajouter `date_debut: Optional[date]` et `date_fin: Optional[date]` ; `selected_days` devient optionnel (défaut `[]`). Validation :
  - il faut soit `selected_days` non vide, soit le couple `date_debut`/`date_fin` complet avec `date_fin >= date_debut` ;
  - la saisie par période est **réservée aux types d'arrêt** (`IJSS_ELIGIBLE_TYPES` : `arret_maladie`, `arret_at`, `arret_maladie_pro`, `arret_maternite`, `arret_paternite`) ;
  - période + `arret_type == "mi_temps_therapeutique"` → erreur explicite (le mi-temps thérapeutique se saisit jour par jour, le salarié travaille partiellement).
- `create_absence_request` : ne consomme plus que `selected_days` (déjà expansés par le schéma, ou fournis tels quels par l'import DSN / la saisie jour par jour). Cap de 3 ans sur la période (`_PERIODE_ARRET_MAX_JOURS`) pour bloquer une faute de frappe sur l'année.

### 2. Backend — projection au calendrier de paie

**RÉVISÉ le 01/09 après revue de code** (l'approche initiale « retyper weekend/repos/ferie en `arret_maladie` » est invalidée : un jour `arret_maladie` à 0 h est déduit comme un jour plein par `calcul_brut` — repli durée contractuelle, cf. `TYPES_SIGNIFICATIFS_A_ZERO_HEURE` — et le retypage fausse fériés payés, jours ouvrables/HS conjoncturelles et proratas de primes).

Design retenu : **les jours non travaillés ne sont jamais retypés**. `update_calendar_from_days` :

- convertit comme avant les seuls jours `travail`/`work` ;
- pour un arrêt, **stampe les vraies bornes calendaires** (`date_debut_arret_reel` / `date_fin_arret_reel` = min/max des `selected_days`) sur les jours convertis **et** sur les week-end/repos/fériés de la période (type inchangé) ;
- pour un arrêt, **rafraîchit les métadonnées** (arret_type, subrogation, historique, bornes) des jours déjà typés `arret_maladie` sans toucher type/heures — re-projection idempotente (script de réparation, prolongations) ;
- branche « mois non planifié » : les jours de remplissage tombant un samedi/dimanche sont insérés en `weekend` (0 h), plus jamais en `travail` 7 h — un arrêt multi-mois par période rend cette branche courante.

`_extraire_arret_pour_maintien` (`payslip_run_heures.py`, partagé avec le forfait) :

- étend `date_fin` à `date_fin_arret_reel` si elle dépasse le dernier jour typé du mois ;
- accepte aussi un jour **non** typé `arret_maladie` dès qu'il porte `date_*_arret_reel` + `arret_type` (week-end/repos/férié tamponnés, type inchangé).

L'analyzer conserve les événements 0 h porteurs de ces bornes (`_conserver_evenement_a_zero_heure`) sans les retyper — un mois qui ne contient que le week-end de débordement d'un arrêt (ex. ven. 31/07 → dim. 02/08) reste visible pour la prévoyance/IJSS, sans retenue 7 h. Le moteur borne déjà ses calculs à l'intersection arrêt×période (`_intersection_dates`). `date_fin_arret_reel` est ajouté à `SERVER_OWNED_ABSENCE_KEYS` et aux clés transmises par l'analyzer.

Conséquence assumée : dans l'onglet calendrier, les week-ends d'un arrêt restent affichés en gris `weekend` (pas en ambre) — c'est le décompte (prévoyance, IJSS, exports, liste « du … au … ») qui devient calendaire, pas la couleur des cases.

### 3. Frontend — saisie en période

`AbsenceRequestModal.tsx`, mode `rh_arret` uniquement :

- quand le type est un arrêt et `arret_type ≠ mi_temps_therapeutique` → `<Calendar mode="range">` (« du … au … ») ; le bouton affiche « Du 17/08/2026 au 18/09/2026 (33 jours calendaires) » ;
- le payload envoie `date_debut`/`date_fin` (pas de `selected_days`) — l'expansion est serveur ;
- `arret_type == mi_temps_therapeutique` → multi-select conservé, payload `selected_days` comme aujourd'hui ;
- modes `employee` et `rh_leave` (CP, RTT, événements familiaux…) : strictement inchangés.
- `frontend/src/api/absences.ts` : `AbsenceCreationPayload` accepte `date_debut`/`date_fin` optionnels, `selected_days` optionnel.

### 4. Réparation de l'existant (script one-off)

`backend/scripts/reparer_arrets_calendaires.py` :

- cible : `absence_requests` de type arrêt (`IJSS_ELIGIBLE_TYPES`), `arret_type ≠ mi_temps_therapeutique`, statut `validated`, dont **TOUS les jours sont ≥ `--depuis`** (défaut 2026-08-01). Un arrêt à cheval sur la borne est **signalé et non traité** (ne pas réécrire les calendriers Colorplast 01→06/2026 convergés) ;
- action par arrêt : ① combler uniquement les **samedis/dimanches** manquants entre min et max — un trou en semaine (reprise réelle / deux épisodes en un enregistrement) n'est jamais comblé, seulement rapporté ; ② re-projeter via `update_calendar_from_days` (bornes `date_*_arret_reel`, subrogation calculée comme à la validation si absente) ;
- deux passes si `--apply` : d'abord tous les `selected_days`, puis chaque projection (historique calculé sur données déjà comblées) ; une erreur sur une ligne n'interrompt pas les suivantes ;
- sans `--apply` : simulation seulement ; idempotent.

### Hors périmètre

- L'opt-in `maintien_base_ouvree` (Cegid) dans `maintien_salaire_service.py` : déjà calendaire, à préserver.
- Les consommateurs qui filtrent déjà `weekday() < 5` (`calcul_absences.py`, `dashboard/application/service.py`, `transport_allowance.py`) : ils absorbent les week-ends sans régression.
- La requalification d'un jour déjà en congé vers un arrêt.

## Points de vigilance

- **Prime de présence** : `week_has_disqualifying_absence` lit les `selected_days` de la demande, pas le type calendrier — un dimanche désormais présent dans `selected_days` disqualifie la semaine. C'est le comportement *correct*. Test : `test_un_dimanche_d_arret_disqualifie_la_semaine_de_presence`.
- **Branche « mois non planifié »** : les samedis/dimanches de remplissage sont insérés en `weekend` 0 h (plus `travail` 7 h). Les fériés d'un mois encore non planifié restent `travail` (pas de calendrier des fériés dans cette branche).
- **Import DSN** : produit déjà des `selected_days` calendaires ; il bénéficie du tamponnage des bornes sur les jours convertis (ses week-ends n'étaient pas retypés, et ne le sont toujours pas).

## Tests

- **Schéma** : période valide → expansion en jours calendaires ; mi-temps thérapeutique + période → 422 ; ni jours ni période → 400 à la commande ; `date_fin < date_debut` → 422 ; période > 3 ans → 422.
- **Commande** : création par période (via schéma) → `selected_days` stockés = tous les jours calendaires ; création par `selected_days` → inchangé.
- **Projection** : week-end/repos/férié **gardent leur type** mais portent `date_*_arret_reel` ; CP inchangé ; re-projection rafraîchit les jours déjà `arret_maladie` ; mois non planifié : week-ends en `weekend` 0 h.
- **Bulletin** : arrêt finissant un dimanche → `date_fin` extraite = ce dimanche ; mois qui ne contient que le week-end de débordement → arrêt quand même visible via les bornes tamponnées.
- **Prime de présence** : semaine avec dimanche en arrêt → disqualifiée.
- **Script de réparation** : comblement des seuls week-ends, refus d'un trou en semaine, borne `--depuis` = min(jours) ≥ depuis, arrêts à cheval exclus.
- **Frontend** : utilitaire de formatage de période (`*.test.ts`) ; modal range pour un arrêt, y compris 1 jour (`to` absent) ; purge de sélection au bascule mi-temps.
