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
- `create_absence_request` (`absences/application/commands.py`) : si `date_debut`/`date_fin` fournis, `selected_days = daterange_days(date_debut, date_fin)` — **tous les jours calendaires**. Le stockage en base reste `selected_days` (aucune migration de schéma).

### 2. Backend — projection au calendrier de paie

`update_calendar_from_days` (`providers.py:330`) : pour les types d'arrêt (`is_arret`, déjà calculé l.248), la conversion accepte aussi les jours typés `weekend`, `repos` et `ferie` (en plus de `travail`/`work`), avec `heures_prevues = 0` (les jours non travaillés en avaient déjà 0 → pas de sur-déduction : la retenue passe par les `heures_prevues`). Les types non-arrêt (CP, RTT…) gardent le comportement actuel (`travail`/`work` uniquement). Les jours `conge`/`conges_payes`/`rtt` ne sont **pas** écrasés (la requalification absence→absence est un sujet séparé, cf. `dev-lot1-preservation-planning`).

### 3. Frontend — saisie en période

`AbsenceRequestModal.tsx`, mode `rh_arret` uniquement :

- quand le type est un arrêt et `arret_type ≠ mi_temps_therapeutique` → `<Calendar mode="range">` (« du … au … ») ; le bouton affiche « Du 17/08/2026 au 18/09/2026 (33 jours calendaires) » ;
- le payload envoie `date_debut`/`date_fin` (pas de `selected_days`) — l'expansion est serveur ;
- `arret_type == mi_temps_therapeutique` → multi-select conservé, payload `selected_days` comme aujourd'hui ;
- modes `employee` et `rh_leave` (CP, RTT, événements familiaux…) : strictement inchangés.
- `frontend/src/api/absences.ts` : `AbsenceCreationPayload` accepte `date_debut`/`date_fin` optionnels, `selected_days` optionnel.

### 4. Réparation de l'existant (script one-off)

`backend/scripts/reparation/reparer_arrets_calendaires.py` :

- cible : `absence_requests` de type arrêt (`IJSS_ELIGIBLE_TYPES`), `arret_type ≠ mi_temps_therapeutique`, statut `validated`, dont **au moins un jour ≥ 2026-08-01** (borne paramétrable `--depuis`). La borne protège les calendriers qui sous-tendent les bulletins Colorplast janvier→juin déjà convergés au centime (régénération du 27/08) ;
- action par arrêt : ① combler `selected_days` en calendaire continu min→max (un enregistrement = une période, par construction du modèle) ; ② re-projeter le calendrier via le même chemin que la validation (`update_calendar_from_days` avec `arret_type`, subrogation, `nombre_enfants`, historique recalculés comme dans `update_absence_request_status`) ;
- `--dry-run` par défaut (liste ce qui serait modifié), `--apply` pour exécuter ; idempotent (un arrêt déjà calendaire et déjà projeté ne change rien) ;
- déroulé : env de **test** d'abord, vérification sur l'arrêt de Marion GAUTHERON (17/08→18/09), puis prod.

### Hors périmètre

- Le moteur maintien/IJSS/prévoyance (`maintien_salaire_service.py`) : déjà calendaire, y compris l'opt-in `maintien_base_ouvree` (Cegid) à préserver.
- Les consommateurs qui filtrent déjà `weekday() < 5` (`calcul_absences.py`, `dashboard/application/service.py`, `transport_allowance.py`) : ils absorbent les week-ends sans régression.
- L'« extension de robustesse » des dates dans `payslip_run_heures.py` : inutile une fois les données saines à la source et l'historique réparé.
- La requalification d'un jour déjà en congé vers un arrêt.

## Points de vigilance

- **Prime de présence** : `week_has_disqualifying_absence` (`payroll_variables/domain/presence_week.py:73`) — un dimanche désormais typé `arret_maladie` peut disqualifier une semaine. C'est le comportement *correct* (l'arrêt couvre réellement ce jour), mais un test doit figer cette décision.
- **Branche « mois non planifié »** de `update_calendar_from_days` (insert) : comportement conservé tel quel (les jours de remplissage restent `travail`, test existant `test_les_jours_de_remplissage_ne_sont_pas_marques`).
- **Import DSN** : produit déjà des `selected_days` calendaires ; il bénéficie du déverrouillage de la projection (ses week-ends étaient ignorés aussi).

## Tests

- **Schéma** : période valide → expansion refusée/acceptée selon type ; mi-temps thérapeutique + période → 422 ; ni jours ni période → 422 ; `date_fin < date_debut` → 422.
- **Commande** : création par période → `selected_days` stockés = tous les jours calendaires ; création par `selected_days` → inchangé.
- **Projection** (harnais existant `test_planned_calendar_preservation.py`, faux Supabase) : week-end/repos/férié → `arret_maladie` avec `heures_prevues=0` pour un arrêt ; restent intacts pour un CP ; jours `conge` non écrasés par un arrêt.
- **Bulletin** : arrêt finissant un dimanche en fin de mois → `date_fin` de l'arrêt extraite = ce dimanche (jours IJSS/prévoyance non tronqués).
- **Prime de présence** : semaine avec dimanche en arrêt → disqualifiée (décision figée).
- **Script de réparation** : comblement min→max, respect de la borne `--depuis`, idempotence, dry-run sans écriture.
- **Frontend** : utilitaire d'expansion/formatage de période testé (`*.test.ts`) ; le modal passe en range pour un arrêt et repasse en multiple pour mi-temps thérapeutique.
