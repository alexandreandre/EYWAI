# Période des variables de paie — design

Date : 2026-09-08 · Source : échanges WhatsApp Gaëlle Bouali / Vanessa du 08/09/2026

## Le besoin

Gaëlle arrête les paies quand elle peut, société par société. Le bulletin porte
toujours le mois civil, mais les **variables** — heures supplémentaires et
paniers — couvrent des **semaines complètes décalées**, dont elle décide la fin
à chaque paie. Ses fenêtres réelles :

| | juillet 2026 | août 2026 |
|---|---|---|
| Colorplast, Comitech, MBC | 22/06 → 25/07 (S26→S30) | 27/07 → 22/08 (S31→S34) |
| Cartol, Lewis | 22/06 → 18/07 (S26→S29) | 20/07 → 22/08 (S30→S34) |

En juillet elle a arrêté Cartol et Lewis le 19, les trois autres le 25 ; août
rattrape mécaniquement la semaine que juillet n'avait pas prise. Ses bornes
commencent un lundi et finissent un samedi, et chaque mois reprend au lundi
suivant : **aucun trou, aucun doublon**.

Le logiciel raisonne en **semaines complètes** : une fenêtre se termine le
dimanche de la semaine qui contient la date choisie. Le 25/07 de Gaëlle est donc
stocké 26/07, son 18/07 devient 19/07 — le dimanche est vide, l'écart est
d'affichage. C'est déjà la règle du moteur (`decalage_vers_dimanche`), et c'est
elle qui garantit la continuité.

Ce qui reste sur le **mois civil** (1er → dernier jour), sur sa demande
explicite : congés, RTT, primes, notes de frais, avances, acomptes, saisies sur
salaire. Le bulletin affiche « du 1er au 31 juillet, paiement le 31 ».

MAJI et ZONE 404 ne sont pas concernées (Vanessa) : mois civil de bout en bout.

## L'existant

La fenêtre glissante existe déjà et tourne en production :

- `companies.paie_jour_de_fin` / `paie_occurrence`, lues par
  `backend/app/shared/domain/periode_de_paie.py` ; valeurs par défaut `4` et
  `-2` = **avant-dernier vendredi**, étendu au dimanche de sa semaine
  (`bornes_periode_de_paie`, `backend/app/modules/payroll/engine/period_forfait.py`).
- Pour Colorplast, la règle produit 22/06 → 26/07 en juillet et 27/07 → 23/08 en
  août : **les dates de Gaëlle, au dimanche près**.
- `est_mode_mois_calendaire` gère déjà le repli mois civil quand `jour_de_fin`
  sort de `[0, 6]`.

Deux manques :

1. **Elle ne peut pas corriger la fenêtre** quand elle décale (Cartol/Lewis en
   juillet). La règle est figée dans deux colonnes société.
2. **Le périmètre est trop large.** `creer_calendrier_etendu`
   (`payslip_run_common.py:197`) charge *tous* les événements de paie sur cette
   fenêtre — donc congés, arrêts et absences décalent aussi. Un congé pris le
   30/07 atterrit aujourd'hui sur le bulletin d'août. C'est l'inverse de ce que
   Gaëlle demande.

## Ce qu'on construit

### 1. Une surcharge mensuelle par société

Table `company_variable_periods` :

| colonne | type | note |
|---|---|---|
| `id` | uuid PK | |
| `company_id` | uuid FK companies | |
| `year`, `month` | int | |
| `start_date`, `end_date` | date | bornes incluses |
| `origin` | text | `regle` (pré-rempli accepté tel quel) ou `manuel` |
| `created_by` | uuid | utilisateur qui a validé |
| `created_at`, `updated_at` | timestamptz | |

`UNIQUE (company_id, year, month)`. RLS activée, aucune policy publique, accès
par `app.core.database` comme les autres tables société.

**Résolution de la fenêtre** pour un couple (société, mois), dans l'ordre :

1. la ligne stockée si elle existe ;
2. sinon `bornes_periode_de_paie(paie_jour_de_fin, paie_occurrence)` — le
   comportement actuel, inchangé ;
3. si `est_mode_mois_calendaire`, la fenêtre **est** le mois civil.

La résolution vit dans `backend/app/shared/domain/periode_de_paie.py`, aux côtés
de la lecture des colonnes société : un seul endroit lit la période de paie, la
règle du fichier est conservée.

**Continuité.** Le début proposé est toujours le lendemain de la fin du mois
précédent (stockée, ou calculée par la règle si rien n'est stocké). Il est
verrouillé en saisie ; le déverrouiller demande une confirmation explicite et
affiche ce qu'on perd ou double.

### 2. La saisie au lancement de la paie

Dans `frontend/src/features/dashboard/widgets/GeneratePayrollModal.tsx`, sous le
sélecteur de mois, un bloc **« Variables (heures sup et paniers) »** :

- `Du 27/07 au 22/08 — semaines 31 à 34`, le début en lecture seule avec la
  mention « suite du mois précédent » ;
- la fin se choisit par date ou par numéro de semaine ; quelle que soit la date
  saisie, la fenêtre s'arrête au **dimanche de la semaine qui la contient**, et
  la borne retenue est affichée avant validation (« 25/07 → semaine 30, jusqu'au
  dimanche 26/07 ») ;
- un décompte de ce que la fenêtre contient : *n* heures supplémentaires,
  *n* paniers ;
- le report : « la semaine 35 (24/08 → 30/08) partira sur septembre » ;
- des avertissements sur trou, chevauchement, ou fenêtre inférieure à 2 semaines
  / supérieure à 6.

Pour une société en mois civil, le bloc affiche « mois civil » sans champ.

La fenêtre est enregistrée à la validation, avant génération. Toute régénération
ultérieure du même mois relit la ligne stockée : un bulletin régénéré en octobre
donne le même résultat qu'en août.

### 3. La séparation du rattachement

`run_payslip_generation_heures` (`payslip_run_heures.py:298`) calcule
aujourd'hui **une** paire `(date_debut_periode, date_fin_periode)` qui sert à
tout. Cible : deux fenêtres explicites.

- `periode_mois` = 1er → dernier jour du mois.
- `periode_variables` = la fenêtre résolue ci-dessus.
- `creer_calendrier_etendu` charge l'**union** des deux et marque chaque jour de
  son rattachement (`rattachement: "mois" | "variables"`).
- `calculer_salaire_brut` reçoit les deux bornes : heures travaillées, heures
  supplémentaires (structurelles et conjoncturelles), majorations attachées aux
  heures et paniers issus des jours travaillés sont filtrés sur
  `periode_variables` ; tout le reste sur `periode_mois`.

Décisions de rattachement, à figer dans le code et vérifiées par les tests :

| | fenêtre |
|---|---|
| salaire de base, congés, RTT, arrêts, primes fixes, NDF, avances, acomptes, saisies sur salaire | mois civil |
| HS structurelles et conjoncturelles, majorations horaires, paniers / repas des jours travaillés | variables |
| solde de tout compte (`resolve_exit_state_for_payslip`) | **mois civil** — le bulletin couvre 1→31, un dernier jour travaillé le 30/07 appartient à juillet. Change le comportement actuel : à valider par backtest. |
| forfait-jours (`payslip_run_forfait.py:178`) | **inchangé** — la période glissante a été introduite pour lui ; on n'y touche pas dans ce lot. |

### 4. L'en-tête du bulletin

`bulletin_view.py:120-134` imprime aujourd'hui les bornes de la fenêtre
glissante — d'où le « Du 22/06/2026 Au 26/07/2026 » du bulletin de GIRERD.
Cible : `Du 01/07/2026 Au 31/07/2026`, plus une ligne
`Variables du 22/06/2026 au 25/07/2026` quand la fenêtre diffère du mois. C'est
exactement ce que Quadra imprime, donc ce que Gaëlle lit déjà.

## Hors périmètre

- **Primes de présence et d'assiduité MBC**, que Gaëlle veut calées sur les
  variables décalées. C'est une règle de calcul en plus, pas une fenêtre ; elle a
  dit « on en reparlera ».
- Fenêtre par salarié : personne ne l'a demandée.
- Modification de la règle par défaut (`paie_jour_de_fin` / `paie_occurrence`) :
  elle reste le pré-remplissage.

## Reprise de l'existant

Juillet 2026 a été généré avec la règle par défaut, donc **faux pour Cartol et
Lewis** (22/06 → 26/07 au lieu de 22/06 → 19/07). Décision : on rejoue juillet
une fois la fonctionnalité livrée — saisie des cinq fenêtres puis régénération,
pour que la recette de Gaëlle porte sur des bulletins justes.

Sauvegarde des bulletins concernés avant régénération : un mois rejoué applique
les données du jour, pas celles d'origine.

## Vérification

Rien n'est livré sans ces quatre preuves :

1. **Unitaires** — résolution de la fenêtre (stockée / règle / mois calendaire),
   continuité entre mois, normalisation d'une date de fin en semaine complète,
   refus d'un chevauchement.
2. **Intégration** — un congé posé le 30/07 apparaît sur le bulletin de juillet ;
   une heure supplémentaire du 28/07 apparaît sur celui d'août.
3. **Backtest Colorplast mai 2026** — 7/7 au centime, avant et après. C'est le
   garde-fou contre une régression du changement de rattachement : le mois
   convergeait déjà avec l'ancien découpage.
4. **Cartol juillet 2026** — heures supplémentaires et paniers effectivement
   bornés au 19/07 après saisie de la fenêtre.
