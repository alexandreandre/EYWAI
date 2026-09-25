# Le bac à sable ne synchronise plus le salaire de la fiche

Décidé le 24/09/2026 avec Alexandre (approche A).

## Pourquoi

Le bac à sable de génération promet un calcul identique à une vraie génération,
sans aucune écriture (`app/modules/payroll/documents/bac_a_sable.py`). Le
24/09, le recalcul des six brouillons d'août de Colorplast a montré qu'il en
fait une : chaque calcul réécrit `employees.salaire_de_base`.

Toutes les écritures Supabase ont ensuite été piégées pendant un calcul en bac
à sable (Girerd, août) : il n'y en a qu'une, et sa pile est

```
generate_en_bac_a_sable
  → process_payslip_generation                 (payslip_generator.py)
    → prepare_salary_evolution_for_payslip     (salary_evolution_payroll.py)
      → sync_employee_salaire_actif            (employees/application/commands.py)
        → EmployeeRepository.sync_salaire_actif → update(employees)
```

La valeur écrite est le salaire actif du jour lu dans `salary_history`. Sur les
six salariés, c'était celle qui y était déjà : seul `updated_at` a bougé. Mais
un calcul d'audit ne doit rien écrire, et une fiche dont le salaire n'aurait
pas été synchronisé serait modifiée par un simple contrôle.

## Pourquoi on ne peut pas simplement sauter l'écriture

`prepare_salary_evolution_for_payslip` synchronise, **puis relit la fiche** :
le salaire relu sert de repli (`salaire_initial`) à
`construire_evolution_salaire_mois` quand aucune entrée de l'historique ne
couvre le mois. Sauter la synchronisation changerait ce repli dans ce cas, et
le bac à sable ne calculerait plus comme une vraie génération.

La synchronisation lit en outre la fiche avec sa propre règle
(`_valeur_salaire_row` : 0 si `salaire_de_base` n'est pas un dictionnaire avec
`valeur`), différente de celle du calcul (`_valeur_salaire`). Recopier la
formule dans le calcul ferait deux règles à tenir d'accord.

## Ce qu'on change

**1. `EmployeeRepository.salaire_de_base_a_date(employee_id, company_id, as_of)`
— nouvelle, n'écrit rien.** Le corps actuel de `sync_salaire_actif` jusqu'à
l'écriture : lit la fiche et l'historique, rend le `salaire_de_base` que la
synchronisation écrirait (le dictionnaire de la fiche, `valeur` remplacée par
`salaire_actif_a_date(timeline, as_of, _valeur_salaire_row(emp))`), ou `None`
si le salarié est introuvable.

**2. `sync_salaire_actif` — devient** `salaire_de_base_a_date` puis
`update(employee_id, {"salaire_de_base": ...})`. Même résultat qu'aujourd'hui,
par construction.

**3. `prepare_salary_evolution_for_payslip(..., persister: bool = True)`.**
- `persister=True` (défaut, vraie génération) : inchangé — synchronise, relit.
- `persister=False` (bac à sable) : ne synchronise pas ; relit la fiche, puis
  remplace son `salaire_de_base` par `repo.salaire_de_base_a_date(...,
  date.today())` quand il n'est pas `None`. Le calcul voit exactement la fiche
  qu'il aurait vue après la synchronisation.

**4. Les deux générateurs** (`payslip_generator.py`, `payslip_generator_forfait.py`)
passent `persister=bac_a_sable is None`, le nom et la règle déjà employés pour
le run heures et le hook de modulation.

## Ce qu'on ne change pas

- Une vraie génération synchronise toujours la fiche, comme aujourd'hui.
- L'autre appel à `sync_salaire_actif` (`EmployeeRepository`, hors paie) et
  `apply_salary_update` ne sont pas touchés.
- Pas de verrou général contre les écritures en bac à sable (approche B
  écartée : il faudrait toucher au client Supabase partagé par le serveur).

## Tests

Unitaires, dans `tests/unit/payroll/test_salary_evolution_payroll.py` :

1. `persister=False` : `sync_employee_salaire_actif` n'est pas appelé.
2. `persister=False`, historique vide, fiche à 2 000 € et
   `salaire_de_base_a_date` qui rend 3 000 € : le bulletin prend 3 000 € —
   c'est la valeur synchronisée qui sert de repli, pas celle de la fiche.
3. `persister=False` quand `salaire_de_base_a_date` rend `None` : la fiche
   relue sert telle quelle, sans erreur.
4. Les tests existants (défaut `persister=True`) passent sans modification :
   ils vérifient déjà l'appel à la synchronisation.

Unitaires, dans un nouveau `tests/unit/employees/test_salaire_de_base_a_date.py` :

5. `salaire_de_base_a_date` rend le dictionnaire de la fiche avec la valeur
   active à la date, et n'appelle jamais `update`.
6. `salaire_de_base_a_date` rend `None` pour un salarié introuvable.
7. `sync_salaire_actif` écrit exactement ce que `salaire_de_base_a_date` rend.

## Vérification sur le test

Aucune écriture autorisée : le script de vérification piège
`update/upsert/insert/delete` du client PostgREST (journal de la pile, puis
exception) et calcule en bac à sable :

- les six salariés de Colorplast en août — **zéro écriture**, et brut, net,
  cotisations et cumul brut identiques au relevé du 24/09 ;
- un salarié au forfait jours de Cartol Industrie, pour le second générateur,
  appelé directement (`process_payslip_generation_forfait(...,
  bac_a_sable=BacASable())`, voir le constat ci-dessous) — **zéro écriture**.
  Ces salariés n'ont encore aucun bulletin : si le calcul s'arrête faute de
  données avant la préparation du salaire, on le dit, et le câblage du forfait
  ne repose alors que sur la relecture du code.

## Constat hors périmètre

Sur la base de test, les salariés au forfait (Cartol Industrie) ne le sont que
par le booléen `is_forfait_jour` ; leur statut est « Cadre » ou « Non-Cadre ».
Or la génération réelle (`payslips/application/commands.py`, `generate_payslip`)
comme le bac à sable (`generate_en_bac_a_sable`) choisissent le générateur par
`is_forfait_jour(statut)`, **sans le booléen** : ces salariés partiraient dans
le générateur des heures. Seul le générateur forfait lit le booléen. À traiter
dans un chantier à part, avant la première paie de Cartol.

## Critère de réussite

Un calcul en bac à sable n'écrit plus rien, et ses montants ne bougent pas
d'un centime. La mémoire `bac-a-sable-generation` et la passation le disent.
