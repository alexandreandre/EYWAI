# La période à saisir pour la paie d'un mois — conception

Date : 20 septembre 2026. Décidé avec Alexandre le 20/09 au matin, à partir du
cas Michel BUGNY, juillet 2026, sur le test.

## Le constat

Colorplast compte ses variables (heures supplémentaires, paniers) sur des
semaines complètes arrêtées à l'avant-dernier vendredi du mois
(`paie_jour_de_fin=4`, `paie_occurrence=-2`). La fenêtre de **juillet 2026 va
du 22/06 au 26/07** (S26 à S30), celle d'**août du 27/07 au 23/08** (S31 à
S34). Les dossiers de pointage de Gaëlle sont rangés exactement ainsi.

Le moteur respecte cette fenêtre : `payslip_run_heures.py` construit le
calendrier sur l'**union** du mois civil et de la fenêtre des variables
(`creer_calendrier_etendu`, 22/06 → 31/07 pour juillet) et
`calcul_brut.evenements_de_la_periode` rattache les heures à la fenêtre, le
reste au mois civil. La fenêtre est résolue à un seul endroit,
`periode_variables_service.resoudre_fenetre_variables` (règle société,
surcharge mensuelle de la fin, continuité : un mois commence le lendemain de la
fin retenue du précédent).

Le contrôle amont, lui, ne connaît que le mois civil. `_check_calendar_guard`
(`payslips/application/commands.py`), la revue pré-paie
(`payroll/application/preflight_anomalies.py`) et le tableau de bord
(`dashboard/application/analytics_gestion.py`) appellent tous
`ecart_rules.compute_row_status(planned, actual, year, month)` sur la ligne
`employee_schedules` du mois. Deux erreurs à la fois, constatées sur Michel :

- **fausse alerte** : « calendrier incomplet » pour les 27–31/07, que le moteur
  ne lit pas pour les heures (c'est la paie d'août) ;
- **silence** : rien sur les 22–30/06 (S26 et le début de S27), que le moteur
  lit et qui étaient vides dans le réel de juin. Forcer aurait produit un
  juillet avec deux semaines d'heures sup manquantes, sans avertissement.

## Le principe

**Une seule notion de « période à saisir pour la paie de M »**, calculée par
une fonction pure à partir de la fenêtre du moteur, et consommée par tout le
monde : le garde-fou de génération, la revue pré-paie, le tableau de bord,
l'écran d'import. Le moteur ne change pas : il fait déjà juste, c'est le
contrôle qui est en retard sur lui.

Rigide là où la paie l'exige — la continuité des fenêtres, un seul chemin de
code — et souple là où la pratique varie : la règle est une donnée société,
l'exception est mensuelle (la fin, semaine entamée comptée entière), le
forçage reste possible et tracé. **Pas de fenêtre par salarié ni par
génération** : ça casserait l'invariant « un jour n'appartient qu'à une
paie », et déplacerait sur la personne qui génère une décision qui relève de la
clôture de paie.

## Conception

### 1. Le domaine : `jours_a_saisir` (pur)

Nouveau module `app/modules/schedules/domain/periode_a_saisir.py`, sans I/O.

```python
@dataclass(frozen=True)
class JourASaisir:
    jour: date
    bloquant: bool      # dans la fenêtre des variables (heures) : True ; hors fenêtre, dans le mois civil : False
    motif: str          # "prevu_sans_reel" | "prevu_sans_heures" | "reel_a_zero" | "planning_absent"

@dataclass(frozen=True)
class PeriodeASaisir:
    debut: date         # min(1er du mois civil, début de la fenêtre)
    fin: date           # max(dernier du mois civil, fin de la fenêtre)
    fenetre: tuple[date, date]
    mois_civil: tuple[date, date]
    manquants: tuple[JourASaisir, ...]

    @property
    def bloquants(self) -> tuple[JourASaisir, ...]: ...
    @property
    def informatifs(self) -> tuple[JourASaisir, ...]: ...
    @property
    def statut(self) -> "a_saisir" | "saisi": ...   # a_saisir ssi un bloquant existe

def periode_a_saisir(
    *,
    annee: int, mois: int,
    fenetre: tuple[date, date],
    calendriers: Mapping[tuple[int, int], tuple[list[dict], list[dict]]],  # (année, mois) → (prévu, réel), M-1 et M
    date_entree: date | None,
    date_sortie: date | None,
    forfait: bool,
) -> PeriodeASaisir
```

Règles, dans l'ordre :

1. **Bornes** : union du mois civil et de la fenêtre. Un forfait jour est jugé
   sur le mois civil seul (présence en jours, pas d'heures : la fenêtre des
   variables ne le concerne pas).
2. **Contrat** : aucun jour avant `date_entree` ni après `date_sortie` n'est à
   saisir — comme le moteur, qui écarte tout événement hors contrat.
3. **Jour prêt** : la règle actuelle `is_day_ready_for_payroll` est conservée
   telle quelle (travail prévu ⇒ réel présent, heures non nulles quand du
   prévu existe ; les autres types sont prêts). Elle est appliquée jour par
   jour sur la période, en allant chercher chaque jour dans le calendrier du
   bon mois. Un mois sans ligne de planning dans la période du contrat : tous
   ses jours ouvrés attendus sont « planning_absent », bloquants.
4. **Bloquant / informatif** : un manquant dans la fenêtre des variables est
   bloquant ; un manquant du mois civil hors fenêtre (les 27–31/07 de Michel)
   est informatif — il n'apparaît que dans le détail d'un refus (422) et dans
   la revue pré-paie, jamais comme alerte d'une génération réussie : la fin du
   mois civil dépasse la fenêtre tous les mois, une alerte permanente n'en est
   pas une (retour d'Alexandre, 21/09).

`compute_row_status` garde sa signature pour les écarts d'heures
(`saisi_avec_ecart`), mais sa décision `a_saisir` vient désormais de
`periode_a_saisir` — un seul juge.

### 2. Le chargement : `charger_periode_a_saisir` (application)

`app/modules/schedules/application/periode_a_saisir_service.py` :

```python
def charger_periode_a_saisir(company_id, employee, annee, mois) -> PeriodeASaisir
def charger_periodes_a_saisir(company_id, employees, annee, mois) -> dict[employee_id, PeriodeASaisir]
```

Résout la fenêtre (`resoudre_fenetre_variables`), lit les lignes
`employee_schedules` des mois couverts par l'union en une requête
(`list_schedules_for_employees` par mois), lit les dates de contrat
(`hire_date` ; sortie = `exit_last_working_day` sinon `contract_end_date`,
la résolution qu'utilise déjà `commands.py` pour le STC), et appelle la
fonction pure. La version « pluriel » sert la revue pré-paie et le tableau de bord sans
N requêtes.

### 3. Les consommateurs

- **Garde-fou de génération** (`_check_calendar_guard`) : `a_saisir` ⇔ des
  bloquants existent. Le 422 garde `{code: "calendrier_incomplet", message}` et
  ajoute :

  ```json
  {
    "code": "calendrier_incomplet",
    "message": "Juillet 2026 — 7 jours à saisir dans la fenêtre des variables (22/06 → 26/07) : 22/06–26/06, 29/06–30/06.",
    "fenetre": {"debut": "2026-06-22", "fin": "2026-07-26", "semaines": [26, 27, 28, 29, 30], "origine": "regle"},
    "jours_manquants": ["2026-06-22", "2026-06-23", "2026-06-24", "2026-06-25", "2026-06-26", "2026-06-29", "2026-06-30"],
    "jours_informatifs": ["2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30", "2026-07-31"]
  }
  ```

  Le message nomme les dates, groupées en plages. Le forçage
  (`force_calendrier_incomplet`) reste, tracé comme aujourd'hui ; son
  avertissement de réponse liste aussi les dates forcées.
- **Revue pré-paie** (`preflight_anomalies`) : l'anomalie `heures_non_saisies`
  porte les mêmes dates et la fenêtre ; son message devient « 7 jours à saisir
  dans la fenêtre 22/06 → 26/07 ». Un salarié qui n'a que des informatifs n'est
  pas en anomalie.
- **Tableau de bord** (`analytics_gestion`) : compte `a_saisir` sur la même
  base — les chiffres du tableau de bord et les refus de génération ne peuvent
  plus se contredire.

### 4. Bulletins calculés sur une autre fenêtre

Chaque bulletin stocke déjà la fenêtre sur laquelle il a été calculé
(`payslip_data.en_tete.date_debut_variables` / `date_fin_variables`). Quand la
fenêtre d'un mois change (surcharge de la fin), les bulletins de ce mois
calculés sur l'ancienne fenêtre deviennent **« à régénérer »** :

- `enregistrer_fenetre_variables` renvoie, en plus de la fenêtre, le nombre de
  bulletins du mois calculés sur une autre fenêtre ;
- la revue pré-paie signale ces bulletins (anomalie `fenetre_modifiee`,
  informative, avec l'ancienne et la nouvelle fenêtre).

C'est ce qui empêche la dérive silencieuse — plus utile que n'importe quel
blocage.

### 5. Le front

- **Dialogue de refus** (`PayrollGenerationRefusalDialog`, `RegeneratePayslipButton`) :
  affiche la fenêtre, la liste des dates manquantes groupées par semaine, et
  un lien « Compléter le planning » vers le bon mois du bon salarié ; les
  informatifs apparaissent sous « Seront saisis pour août : 27/07–31/07 ».
  « Générer quand même » reste, et l'on sait ce qu'on force.
- **Bloc fenêtre partout où l'on génère** : `BlocPeriodeVariables` (déjà dans
  la modale groupée du tableau de bord) apparaît aussi dans le dialogue de
  régénération unitaire (`RegeneratePayslipButton`), en lecture : « Variables
  de juillet : 22/06 → 26/07, S26–S30 ». « Modifier la fenêtre de juillet »
  ouvre le réglage société-mois existant, qui annonce « s'applique à toute la
  société pour juillet ; N bulletins déjà générés seront à régénérer ».
- **Import des pointages** (`PointageImportDialog`, `monthIsoWeekOptions`) :
  chaque option du sélecteur « Semaine » porte le mois de paie auquel elle
  appartient (« S31 · 27 juil. – 2 août → paie d'août »), calculé depuis
  `GET /period` du mois cible et du suivant ; une semaine choisie hors de la
  fenêtre du mois cible déclenche une note, pas un blocage — le commit range
  de toute façon chaque jour dans son mois réel.

## Robustesse : les cas qui doivent être dans les tests

1. Embauché en cours de fenêtre (entrée le 06/07) : rien à saisir avant le 6.
2. Sorti en cours de mois (sortie le 15/07) : rien après le 15.
3. Pas de ligne M-1 : premier mois du salarié → rien (contrat) ; contrat en
   cours et ligne absente → jours ouvrés attendus manquants, bloquants,
   `planning_absent`.
4. Forfait jour : mois civil seul, règle 0/1 conservée.
5. Société en mode mois calendaire : fenêtre = mois civil, aucun informatif.
6. Fenêtre surchargée (fin avancée au 19/07) : les 20–26/07 deviennent
   informatifs pour juillet et bloquants pour août.
7. Michel, juillet 2026, état du test au 20/09 : bloquants 22/06–26/06 et
   29/06–30/06 ; informatifs 27/07–31/07 ; `a_saisir`.
8. Même état une fois S26 et S27 saisis en juin : `saisi`, cinq informatifs.
9. Un bulletin de juillet calculé sur 22/06 → 26/07, fenêtre modifiée à
   → 19/07 : signalé « à régénérer ».
10. `compute_row_status` : `saisi_avec_ecart` inchangé sur les heures du mois.

## Hors périmètre

- Le moteur de bulletin : aucune modification.
- Une fenêtre par établissement, équipe ou salarié : le jour où un vrai cas se
  présente, ce sera une donnée de plus dans la résolution de la fenêtre ; la
  fonction pure reçoit des bornes et n'a pas à changer.
- Le déplacement automatique de jours d'un mois à l'autre : le commit d'import
  range déjà chaque jour dans son mois réel (correctif du 19/09).

## Ordre de livraison

Chaque pas est livrable et utile seul.

1. **Socle backend** : domaine pur + service de chargement + garde-fou + revue
   pré-paie + tableau de bord, avec les dix cas ci-dessus. Michel n'est plus
   bloqué pour les 27–31/07 et l'est, avec les dates, pour juin.
2. **Front** : dialogue de refus avec dates et lien ; bloc fenêtre dans la
   régénération unitaire ; « à régénérer » quand la fenêtre change.
3. **Import** : mois de paie affiché par semaine, note hors fenêtre.
