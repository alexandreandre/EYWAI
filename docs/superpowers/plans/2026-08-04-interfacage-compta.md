# Interfaçage comptable — plan d'implémentation

> **Pour les agents :** SOUS-COMPÉTENCE REQUISE — utiliser `superpowers:subagent-driven-development` (recommandé) ou `superpowers:executing-plans` pour exécuter ce plan tâche par tâche. Les étapes utilisent des cases à cocher (`- [ ]`).

**Conception :** `docs/superpowers/specs/2026-08-04-interfacage-compta-design.md`
**Point afaire :** #26. Interfaçage compta

**Objectif :** produire pour chaque société une OD de paie mensuelle équilibrée, aux comptes de son cabinet, exportable en CSV / Excel / FEC et transmissible par l'API Cegid Loop.

**Architecture :** un référentiel comptable pur (`coti_id` → organisme → couple de comptes charge/tiers) alimente un moteur d'écritures unique (`payroll_ledger`) qui pose chaque montant du bulletin des deux côtés au moment où il le lit, agrège par compte, et refuse de produire un fichier déséquilibré.

**Stack :** Python 3.14 / FastAPI / Supabase (PostgreSQL 17) côté backend, React + TanStack Query + shadcn/ui côté frontend, pytest pour les tests.

## Contraintes globales

- **Le rattachement d'une cotisation se fait sur `coti_id`, jamais sur le libellé.** Les libellés varient d'une société à l'autre pour la même cotisation (« GAN Isolé 2026 (EMU3) » / « AG2R Mutuelle »).
- **Tolérance d'équilibre : 0,01 €.** Au-delà, l'export est refusé, pas produit avec un avertissement.
- **Cascade de résolution :** mapping société → mapping plateforme (`company_id IS NULL`) → défaut codé. Jamais de compte inventé silencieusement.
- **Aucune donnée nominative dans le dépôt.** Le dépôt est public. Les OD de référence vivent dans `data/<societe>/comptabilite/` (gitignoré).
- **Migrations :** horodatage unique `AAAAMMJJHHMMSS_nom.sql` dans `supabase/migrations/`. Elles s'appliquent automatiquement en production depuis le 31/07.
- **Tests :** `cd backend && ./venv/bin/pytest tests/unit/exports/ -v`. La CI ne bloque que sur `tests/unit`.
- **Le moteur reste généraliste.** Aucune règle spécifique à un salarié ou à une société dans le code ; toute particularité passe par le paramétrage en base.

---

## État d'avancement au 5 août 2026

Tâches 1 à 12 faites, sauf le paramétrage effectif d'une société (tâche 12,
étape 4) qui attend d'appliquer la migration. Tâche 13 : le garde-fou
d'environnement est posé, la configuration Cegid attend les identifiants du
cabinet.

**Écarts d'équilibre mesurés sur la production :**

| Société | Mai 2026 | Juin 2026 | Reste à paramétrer |
|---|---|---|---|
| Colorplast | 0,00 | 0,00 | — |
| Comitech | 0,00 | 0,00 | — |
| Cartol | 0,00 | 20,00 | panier |
| LEWIS | 1 734,86 | 1 073,00 | panier, IJSS |
| Mont Blanc | 2 563,58 | 616,50 | cantine, panier, IJSS |

Plus aucune cause inconnue : tous les écarts restants portent sur des familles
sans compte comptable, remontées en anomalie nommée.

**Trois pièges de données découverts en cours de route**, absents du plan initial :
1. La participation a deux représentations — tableau `participations`, ou ligne
   `is_informative` dans `calcul_du_brut`.
2. `part_pee` est brut de CSG.
3. Les revenus non soumis mais imposables sont dans
   `revenus_hors_brut_imposables`, clé absente des bulletins anciens — d'où un
   repli sur `monthly_inputs`.

**La tâche 6 n'a pas eu besoin d'être écrite** : l'agrégation par compte est
acquise par construction dans la tâche 5 (16 lignes, 16 comptes distincts,
aucun doublon).

**Sources de double comptage à connaître :** `synthese_net.acompte_verse`
agrège acomptes et saisies sur salaire ; les notes de frais ont leur propre
extraction. D'où `FAMILLES_DEJA_COUVERTES` dans `accounting_plan.py`.

---

## Structure des fichiers

**Créés :**

| Fichier | Responsabilité |
|---|---|
| `backend/app/modules/exports/domain/accounting_plan.py` | référentiel pur : `coti_id` → organisme → comptes par défaut. Aucune dépendance infra. |
| `backend/app/modules/exports/domain/ledger_entries.py` | construction des écritures hors cotisations (éléments non soumis), logique pure |
| `backend/tests/unit/exports/test_accounting_plan.py` | tests du référentiel |
| `backend/tests/unit/exports/test_ledger_entries.py` | tests des écritures hors brut |
| `backend/tests/unit/exports/test_ledger_balance.py` | tests d'équilibre bout en bout |
| `supabase/migrations/20260805090000_accounting_mappings_organismes.sql` | colonnes `coti_id`, `compte_charge`, `compte_tiers`, `organisme` + seed |
| `backend/scripts/import_plan_comptable.py` | paramétrage d'une société depuis son plan de comptes |

**Modifiés :**

| Fichier | Nature du changement |
|---|---|
| `backend/app/modules/exports/domain/charges_organisme.py` | `resolve_organisme` délègue à `accounting_plan`, la détection par libellé devient un repli |
| `backend/app/modules/exports/infrastructure/payslip_accounting_extract.py` | extraction des éléments hors brut |
| `backend/app/modules/exports/infrastructure/payroll_ledger.py` | ventilation par organisme, écritures hors brut, agrégation par compte |
| `backend/app/modules/exports/infrastructure/export_ecritures_comptables.py` | défauts corrigés, refus sur déséquilibre |
| `backend/app/modules/exports/application/accounting_mappings.py` | CRUD des nouveaux champs |
| `backend/app/modules/exports/schemas/accounting_mappings.py` | schémas Pydantic |
| `backend/app/modules/exports/api/router.py` | inchangé sauf typage des réponses |
| `frontend/src/api/exports.ts` | type `AccountingMapping` étendu |
| `frontend/src/components/exports/AccountingMappingsPanel.tsx` | deux colonnes de comptes, organisme, clés non mappées |

**Supprimé :**

| Fichier | Raison |
|---|---|
| `backend/app/modules/payroll/exports/ecritures_comptables.py` | copie obsolète (lit `structure_cotisations.cotisations`, clé disparue) |

---

## Tâche 1 : Référentiel comptable

Le socle. Logique pure, aucune base de données, entièrement testable.

**Fichiers :**
- Créer : `backend/app/modules/exports/domain/accounting_plan.py`
- Test : `backend/tests/unit/exports/test_accounting_plan.py`

**Interfaces :**
- Consomme : rien.
- Produit :
  - `ORGANISMES: dict[str, str]` — clé organisme → libellé affiché
  - `COTI_TO_ORGANISME: dict[str, str]` — `coti_id` → clé organisme
  - `DEFAULT_ACCOUNTS: dict[str, AccountPair]` — clé organisme → comptes par défaut
  - `@dataclass(frozen=True) AccountPair(compte_charge: str, compte_tiers: str)`
  - `resolve_organisme_from_coti_id(coti_id: str | None, libelle: str = "") -> str`
  - `default_accounts_for(organisme: str) -> AccountPair | None`
  - `ELEMENT_ACCOUNTS: dict[str, AccountPair]` — éléments hors cotisations (`net_a_payer`, `salaire_brut`, `pas`…)

- [ ] **Étape 1 : Écrire le test qui échoue**

```python
# backend/tests/unit/exports/test_accounting_plan.py
"""Référentiel comptable : rattachement des cotisations aux organismes."""

import pytest

from app.modules.exports.domain.accounting_plan import (
    COTI_TO_ORGANISME,
    ORGANISME_URSSAF,
    ORGANISME_RETRAITE,
    ORGANISME_MUTUELLE,
    ORGANISME_PREVOYANCE,
    ORGANISME_RETRAITE_SUP,
    default_accounts_for,
    resolve_organisme_from_coti_id,
)

pytestmark = pytest.mark.unit


class TestResolutionParCotiId:
    def test_cotisations_urssaf_reconnues(self):
        """Les cotisations recouvrées par l'URSSAF ne portent pas 'URSSAF' dans
        leur libellé — c'est le défaut que ce référentiel corrige."""
        for coti_id in (
            "securite_sociale_maladie",
            "allocations_familiales",
            "assurance_chomage",
            "ags",
            "at_mp",
            "retraite_secu_plafond",
            "retraite_secu_deplafond",
            "csg_deductible",
            "csg_non_deductible",
            "csa",
            "fnal",
            "dialogue_social",
            "versement_mobilite",
            "CFP",
            "taxe_apprentissage",
            "taxe_apprentissage_solde",
            "forfait_social",
            "reduction_generale",
            "deduction_hs_patronale",
            "reduction_hs_salariale",
            "exoneration_apprenti_salariale",
        ):
            assert resolve_organisme_from_coti_id(coti_id) == ORGANISME_URSSAF, coti_id

    def test_cotisations_retraite_complementaire(self):
        for coti_id in ("retraite_comp_t1", "retraite_comp_t2", "ceg_t1", "ceg_t2", "cet", "apec"):
            assert resolve_organisme_from_coti_id(coti_id) == ORGANISME_RETRAITE, coti_id

    def test_mutuelle_prevoyance_et_retraite_sup_distinguees(self):
        assert resolve_organisme_from_coti_id("mutuelle") == ORGANISME_MUTUELLE
        assert resolve_organisme_from_coti_id("prevoyance_cadre") == ORGANISME_PREVOYANCE
        assert resolve_organisme_from_coti_id("prevoyance_non_cadre") == ORGANISME_PREVOYANCE
        assert resolve_organisme_from_coti_id("retraite_sup") == ORGANISME_RETRAITE_SUP

    def test_libelle_ignore_quand_coti_id_present(self):
        """Le libellé varie par société ; il ne doit jamais primer."""
        assert (
            resolve_organisme_from_coti_id("mutuelle", "GAN Isolé 2026 (EMU3)")
            == ORGANISME_MUTUELLE
        )
        assert (
            resolve_organisme_from_coti_id("mutuelle", "AG2R MUTUELLE")
            == ORGANISME_MUTUELLE
        )

    def test_csg_participation_sans_coti_id_rattachee_a_urssaf(self):
        """Cas observé en production : la CSG sur participation n'a pas de coti_id."""
        assert (
            resolve_organisme_from_coti_id(None, "CSG déductible — Participation 2025")
            == ORGANISME_URSSAF
        )

    def test_coti_id_inconnu_leve_une_cle_explicite(self):
        assert resolve_organisme_from_coti_id("cotisation_martienne") == "INCONNU"

    def test_tous_les_coti_id_de_production_sont_couverts(self):
        """31 identifiants relevés sur les bulletins de juin 2026."""
        attendus = {
            "ags", "allocations_familiales", "apec", "assurance_chomage", "at_mp",
            "ceg_t1", "ceg_t2", "cet", "csg_deductible", "csg_non_deductible",
            "deduction_hs_patronale", "exoneration_apprenti_salariale", "forfait_social",
            "mutuelle", "prevoyance_cadre", "prevoyance_non_cadre", "reduction_generale",
            "reduction_hs_salariale", "retraite_comp_t1", "retraite_comp_t2",
            "retraite_secu_deplafond", "retraite_secu_plafond", "retraite_sup",
            "securite_sociale_maladie", "CFP", "csa", "dialogue_social", "fnal",
            "taxe_apprentissage", "taxe_apprentissage_solde", "versement_mobilite",
        }
        assert attendus <= set(COTI_TO_ORGANISME)


class TestComptesParDefaut:
    def test_chaque_organisme_a_un_couple_de_comptes(self):
        for organisme in set(COTI_TO_ORGANISME.values()):
            pair = default_accounts_for(organisme)
            assert pair is not None, organisme
            assert pair.compte_charge.startswith("6"), organisme
            assert pair.compte_tiers.startswith("4"), organisme

    def test_organismes_ont_des_comptes_de_tiers_distincts(self):
        """Le défaut d'aujourd'hui écrase tout sur 431000 ; chaque organisme
        doit avoir sa propre dette."""
        tiers = {
            default_accounts_for(o).compte_tiers
            for o in (
                ORGANISME_URSSAF,
                ORGANISME_RETRAITE,
                ORGANISME_MUTUELLE,
                ORGANISME_PREVOYANCE,
                ORGANISME_RETRAITE_SUP,
            )
        }
        assert len(tiers) == 5

    def test_organisme_inconnu_sans_comptes(self):
        assert default_accounts_for("INCONNU") is None
```

- [ ] **Étape 2 : Vérifier que le test échoue**

```bash
cd backend && ./venv/bin/pytest tests/unit/exports/test_accounting_plan.py -v
```

Attendu : `ModuleNotFoundError: No module named 'app.modules.exports.domain.accounting_plan'`

- [ ] **Étape 3 : Écrire le référentiel**

```python
# backend/app/modules/exports/domain/accounting_plan.py
"""Référentiel comptable paie — rattachement des cotisations aux organismes.

Le rattachement se fait sur `coti_id`, identifiant stable porté par chaque ligne
de cotisation du bulletin. Le libellé n'est utilisé qu'en dernier recours, pour
les rares lignes qui n'ont pas d'identifiant (CSG sur participation).

Les comptes définis ici sont des défauts au plan comptable général. Chaque
société les surcharge en base (`accounting_mappings`) avec les comptes de son
cabinet — souvent à 8 chiffres et ventilés par organisme nommé.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

ORGANISME_URSSAF = "URSSAF"
ORGANISME_RETRAITE = "RETRAITE"
ORGANISME_RETRAITE_SUP = "RETRAITE_SUP"
ORGANISME_MUTUELLE = "MUTUELLE"
ORGANISME_PREVOYANCE = "PREVOYANCE"
ORGANISME_INCONNU = "INCONNU"

ORGANISMES: Dict[str, str] = {
    ORGANISME_URSSAF: "URSSAF",
    ORGANISME_RETRAITE: "Retraite complémentaire",
    ORGANISME_RETRAITE_SUP: "Retraite supplémentaire",
    ORGANISME_MUTUELLE: "Mutuelle",
    ORGANISME_PREVOYANCE: "Prévoyance",
    ORGANISME_INCONNU: "Organisme non rattaché",
}


@dataclass(frozen=True)
class AccountPair:
    """Couple de comptes d'un organisme : charge patronale et dette."""

    compte_charge: str
    compte_tiers: str


# coti_id → organisme. Recensé sur les bulletins de production de juin 2026.
COTI_TO_ORGANISME: Dict[str, str] = {
    # --- Recouvré par l'URSSAF ---
    "securite_sociale_maladie": ORGANISME_URSSAF,
    "allocations_familiales": ORGANISME_URSSAF,
    "assurance_chomage": ORGANISME_URSSAF,
    "ags": ORGANISME_URSSAF,
    "at_mp": ORGANISME_URSSAF,
    "retraite_secu_plafond": ORGANISME_URSSAF,
    "retraite_secu_deplafond": ORGANISME_URSSAF,
    "csg_deductible": ORGANISME_URSSAF,
    "csg_non_deductible": ORGANISME_URSSAF,
    "csa": ORGANISME_URSSAF,
    "fnal": ORGANISME_URSSAF,
    "dialogue_social": ORGANISME_URSSAF,
    "versement_mobilite": ORGANISME_URSSAF,
    "CFP": ORGANISME_URSSAF,
    "taxe_apprentissage": ORGANISME_URSSAF,
    "taxe_apprentissage_solde": ORGANISME_URSSAF,
    "forfait_social": ORGANISME_URSSAF,
    # Allègements et exonérations : même organisme, montant négatif
    "reduction_generale": ORGANISME_URSSAF,
    "deduction_hs_patronale": ORGANISME_URSSAF,
    "reduction_hs_salariale": ORGANISME_URSSAF,
    "exoneration_apprenti_salariale": ORGANISME_URSSAF,
    # --- Retraite complémentaire (AGIRC-ARRCO) ---
    "retraite_comp_t1": ORGANISME_RETRAITE,
    "retraite_comp_t2": ORGANISME_RETRAITE,
    "ceg_t1": ORGANISME_RETRAITE,
    "ceg_t2": ORGANISME_RETRAITE,
    "cet": ORGANISME_RETRAITE,
    "apec": ORGANISME_RETRAITE,
    # --- Retraite supplémentaire ---
    "retraite_sup": ORGANISME_RETRAITE_SUP,
    # --- Santé et prévoyance ---
    "mutuelle": ORGANISME_MUTUELLE,
    "prevoyance_cadre": ORGANISME_PREVOYANCE,
    "prevoyance_non_cadre": ORGANISME_PREVOYANCE,
}

# Comptes par défaut au PCG. Surchargés par société en base.
DEFAULT_ACCOUNTS: Dict[str, AccountPair] = {
    ORGANISME_URSSAF: AccountPair(compte_charge="645100", compte_tiers="431000"),
    ORGANISME_RETRAITE: AccountPair(compte_charge="645300", compte_tiers="437200"),
    ORGANISME_RETRAITE_SUP: AccountPair(compte_charge="645301", compte_tiers="437800"),
    ORGANISME_MUTUELLE: AccountPair(compte_charge="645242", compte_tiers="437020"),
    ORGANISME_PREVOYANCE: AccountPair(compte_charge="645241", compte_tiers="437400"),
}

# Éléments du bulletin qui ne sont pas des cotisations.
# `compte_tiers` vide signifie que l'élément n'a qu'un seul compte.
ELEMENT_ACCOUNTS: Dict[str, AccountPair] = {
    "salaire_brut": AccountPair(compte_charge="641000", compte_tiers=""),
    "prime_soumise": AccountPair(compte_charge="641100", compte_tiers=""),
    # 421 « Personnel — rémunérations dues », et non 425 « avances et acomptes »
    "net_a_payer": AccountPair(compte_charge="", compte_tiers="421000"),
    "pas": AccountPair(compte_charge="", compte_tiers="442000"),
    "saisie_opposition": AccountPair(compte_charge="", compte_tiers="427000"),
    "acompte": AccountPair(compte_charge="", compte_tiers="425000"),
    "avance": AccountPair(compte_charge="", compte_tiers="425200"),
    "pret_employeur": AccountPair(compte_charge="", compte_tiers="274000"),
    "note_de_frais": AccountPair(compte_charge="", compte_tiers="428625"),
    "indemnite_transport": AccountPair(compte_charge="648000", compte_tiers=""),
}

# Repli par libellé, pour les lignes sans coti_id.
_LIBELLE_FALLBACK = (
    ("CSG", ORGANISME_URSSAF),
    ("CRDS", ORGANISME_URSSAF),
    ("URSSAF", ORGANISME_URSSAF),
    ("AGIRC", ORGANISME_RETRAITE),
    ("ARRCO", ORGANISME_RETRAITE),
    ("RETRAITE SUPP", ORGANISME_RETRAITE_SUP),
    ("RETRAITE", ORGANISME_RETRAITE),
    ("PREVOYANCE", ORGANISME_PREVOYANCE),
    ("PRÉVOYANCE", ORGANISME_PREVOYANCE),
    ("MUTUELLE", ORGANISME_MUTUELLE),
)


def resolve_organisme_from_coti_id(
    coti_id: Optional[str], libelle: str = ""
) -> str:
    """Rattache une ligne de cotisation à son organisme.

    `coti_id` prime toujours. Le libellé n'est consulté que si l'identifiant est
    absent — cas de la CSG sur participation, observé en production.
    Retourne `INCONNU` si rien ne correspond : l'appelant doit le signaler, pas
    l'absorber.
    """
    if coti_id:
        organisme = COTI_TO_ORGANISME.get(coti_id)
        if organisme:
            return organisme
        return ORGANISME_INCONNU

    upper = (libelle or "").upper()
    for marqueur, organisme in _LIBELLE_FALLBACK:
        if marqueur in upper:
            return organisme
    return ORGANISME_INCONNU


def default_accounts_for(organisme: str) -> Optional[AccountPair]:
    """Comptes par défaut d'un organisme, ou None s'il n'est pas rattaché."""
    return DEFAULT_ACCOUNTS.get(organisme)
```

- [ ] **Étape 4 : Vérifier que le test passe**

```bash
cd backend && ./venv/bin/pytest tests/unit/exports/test_accounting_plan.py -v
```

Attendu : 9 tests PASS.

- [ ] **Étape 5 : Commit**

```bash
git add backend/app/modules/exports/domain/accounting_plan.py backend/tests/unit/exports/test_accounting_plan.py
git commit -m "feat(compta): référentiel de rattachement des cotisations aux organismes

Le rattachement se fait sur coti_id, identifiant stable du bulletin, et non
plus sur le libellé — qui varie d'une société à l'autre pour la même
cotisation et renvoyait AUTRE pour la quasi-totalité des lignes URSSAF.

Les 31 identifiants relevés sur les bulletins de juin 2026 sont couverts."
```

---

## Tâche 2 : Migration de `accounting_mappings`

**Fichiers :**
- Créer : `supabase/migrations/20260805090000_accounting_mappings_organismes.sql`

**Interfaces :**
- Consomme : les clés d'organisme de la tâche 1.
- Produit : colonnes `coti_id`, `compte_charge`, `compte_tiers`, `organisme` sur `accounting_mappings` ; lignes de défaut plateforme pour les 5 organismes.

**Note importante :** la ligne de défaut `net_a_payer` pointe aujourd'hui sur `425000` (« Personnel — avances et acomptes »). Le compte correct au PCG est `421000` (« Personnel — rémunérations dues »), et c'est bien ce qu'utilise le cabinet (`42100000`). La migration corrige ce défaut plateforme. Les surcharges société éventuelles ne sont pas touchées.

- [ ] **Étape 1 : Écrire la migration**

```sql
-- supabase/migrations/20260805090000_accounting_mappings_organismes.sql
-- Interfaçage comptable (#26) : ventilation des cotisations par organisme.
--
-- Une cotisation demande deux comptes : la charge patronale (classe 6) et la
-- dette envers l'organisme (classe 4). La table n'en portait qu'un.

alter table public.accounting_mappings
  add column if not exists coti_id text,
  add column if not exists compte_charge text,
  add column if not exists compte_tiers text,
  add column if not exists organisme text;

comment on column public.accounting_mappings.coti_id is
  'Identifiant stable de la cotisation dans le bulletin (structure_cotisations). Clé de rattachement — ne jamais se fier au libellé.';
comment on column public.accounting_mappings.compte_charge is
  'Compte de classe 6 débité pour la part patronale.';
comment on column public.accounting_mappings.compte_tiers is
  'Compte de classe 4 crédité (dette organisme ou salarié).';
comment on column public.accounting_mappings.organisme is
  'Clé d''organisme : URSSAF, RETRAITE, RETRAITE_SUP, MUTUELLE, PREVOYANCE.';

-- Unicité du couple (société, rubrique). company_id NULL = défaut plateforme.
create unique index if not exists accounting_mappings_company_rubrique_uidx
  on public.accounting_mappings (company_id, rubrique_code)
  where company_id is not null;

create unique index if not exists accounting_mappings_global_rubrique_uidx
  on public.accounting_mappings (rubrique_code)
  where company_id is null;

-- Correction : le net à payer est une rémunération due (421), pas un acompte (425).
update public.accounting_mappings
   set compte_comptable = '421000',
       compte_tiers = '421000',
       updated_at = now()
 where company_id is null
   and rubrique_code = 'net_a_payer'
   and compte_comptable = '425000';

-- Défauts plateforme par organisme.
insert into public.accounting_mappings
  (company_id, rubrique_code, rubrique_libelle, compte_comptable,
   compte_charge, compte_tiers, organisme, sens, type_rubrique, journal, is_active)
values
  (null, 'organisme_urssaf',       'URSSAF',                  '645100', '645100', '431000', 'URSSAF',       'debit', 'charge_patronale', 'OD', true),
  (null, 'organisme_retraite',     'Retraite complémentaire', '645300', '645300', '437200', 'RETRAITE',     'debit', 'charge_patronale', 'OD', true),
  (null, 'organisme_retraite_sup', 'Retraite supplémentaire', '645301', '645301', '437800', 'RETRAITE_SUP', 'debit', 'charge_patronale', 'OD', true),
  (null, 'organisme_mutuelle',     'Mutuelle',                '645242', '645242', '437020', 'MUTUELLE',     'debit', 'charge_patronale', 'OD', true),
  (null, 'organisme_prevoyance',   'Prévoyance',              '645241', '645241', '437400', 'PREVOYANCE',   'debit', 'charge_patronale', 'OD', true)
on conflict do nothing;

-- Éléments hors cotisations absents du jeu initial.
insert into public.accounting_mappings
  (company_id, rubrique_code, rubrique_libelle, compte_comptable,
   compte_charge, compte_tiers, organisme, sens, type_rubrique, journal, is_active)
values
  (null, 'prime_soumise',        'Primes soumises',        '641100', '641100', '',       null, 'debit',  'salaire',       'OD', true),
  (null, 'indemnite_transport',  'Indemnité de transport', '648000', '648000', '',       null, 'debit',  'non_soumis',    'OD', true),
  (null, 'note_de_frais',        'Notes de frais',         '428625', '',       '428625', null, 'credit', 'dette_salarie', 'OD', true)
on conflict do nothing;

-- Alignement des lignes existantes sur les nouvelles colonnes.
update public.accounting_mappings
   set compte_charge = case when sens = 'debit'  then compte_comptable else compte_charge end,
       compte_tiers  = case when sens = 'credit' then compte_comptable else compte_tiers  end
 where compte_charge is null and compte_tiers is null;
```

- [ ] **Étape 2 : Répéter sur l'environnement de test**

Vérifier d'abord que `backend/.env` ne pointe pas sur la production (il pointe sur la prod par défaut). Puis appliquer sur le projet de test via le workflow dispatchable :

```bash
gh workflow run deploy-test-env.yml -f migration=20260805090000_accounting_mappings_organismes.sql
gh run watch
```

Attendu : workflow vert.

- [ ] **Étape 3 : Vérifier le résultat sur le test**

```sql
select rubrique_code, compte_charge, compte_tiers, organisme
  from accounting_mappings
 where company_id is null
 order by rubrique_code;
```

Attendu : 19 lignes, dont les 5 `organisme_*` et un `net_a_payer` à `421000`.

- [ ] **Étape 4 : Commit**

```bash
git add supabase/migrations/20260805090000_accounting_mappings_organismes.sql
git commit -m "feat(compta): comptes de charge et de tiers par organisme

Une cotisation demande deux comptes : la charge patronale et la dette envers
l'organisme. Corrige au passage le défaut du net à payer, qui pointait sur
425 (avances et acomptes) au lieu de 421 (rémunérations dues)."
```

---

## Tâche 3 : Extraction des éléments hors brut

C'est la cause racine du déséquilibre : ces montants arrivent au net à payer sans contrepartie de charge.

**Fichiers :**
- Modifier : `backend/app/modules/exports/infrastructure/payslip_accounting_extract.py`
- Test : `backend/tests/unit/exports/test_payslip_accounting_extract.py` (fichier existant, ajouter une classe)

**Interfaces :**
- Consomme : rien de la tâche 1.
- Produit : `extract_elements_hors_brut(payslip_data: dict) -> list[dict]`, chaque élément portant `{"element_key": str, "libelle": str, "montant": float}`.

- [ ] **Étape 1 : Écrire le test qui échoue**

```python
# À ajouter à la fin de backend/tests/unit/exports/test_payslip_accounting_extract.py

from app.modules.exports.infrastructure.payslip_accounting_extract import (
    extract_elements_hors_brut,
)


class TestElementsHorsBrut:
    """Ces montants s'ajoutent au net sans passer par le brut. Sans contrepartie
    au débit, l'OD est déséquilibrée d'exactement leur total."""

    def test_prime_non_soumise_extraite_avec_son_identifiant(self):
        payslip = {
            "primes_non_soumises": [
                {
                    "libelle": "Indemnite de transport",
                    "montant": 250.0,
                    "prime_id": "indemnite_de_transport",
                }
            ]
        }
        elements = extract_elements_hors_brut(payslip)
        assert elements == [
            {
                "element_key": "indemnite_de_transport",
                "libelle": "Indemnite de transport",
                "montant": 250.0,
            }
        ]

    def test_participation_extraite(self):
        payslip = {"participations": {"montant_verse": 4436.0, "libelle": "Participation 2025"}}
        elements = extract_elements_hors_brut(payslip)
        assert elements == [
            {
                "element_key": "participation",
                "libelle": "Participation 2025",
                "montant": 4436.0,
            }
        ]

    def test_participation_nulle_ignoree(self):
        assert extract_elements_hors_brut({"participations": None}) == []

    def test_montant_zero_ignore(self):
        payslip = {
            "primes_non_soumises": [
                {"libelle": "Prime vide", "montant": 0.0, "prime_id": "prime_vide"}
            ]
        }
        assert extract_elements_hors_brut(payslip) == []

    def test_prime_sans_identifiant_utilise_une_cle_generique(self):
        payslip = {"primes_non_soumises": [{"libelle": "Prime exceptionnelle", "montant": 100.0}]}
        elements = extract_elements_hors_brut(payslip)
        assert elements[0]["element_key"] == "prime_non_soumise"

    def test_bulletin_sans_element_hors_brut(self):
        assert extract_elements_hors_brut({"salaire_brut": 3000.0}) == []

    def test_ecart_colorplast_juin_2026_reproduit(self):
        """Cas réel : l'écart d'équilibre de 437,53 € correspond exactement
        aux indemnités de transport de la société sur le mois."""
        bulletins = [
            {"primes_non_soumises": [{"libelle": "Indemnite de transport", "montant": 250.0, "prime_id": "indemnite_de_transport"}]},
            {"primes_non_soumises": [{"libelle": "Indemnite de transport", "montant": 187.53, "prime_id": "indemnite_de_transport"}]},
        ]
        total = sum(
            e["montant"] for b in bulletins for e in extract_elements_hors_brut(b)
        )
        assert round(total, 2) == 437.53
```

- [ ] **Étape 2 : Vérifier que le test échoue**

```bash
cd backend && ./venv/bin/pytest tests/unit/exports/test_payslip_accounting_extract.py::TestElementsHorsBrut -v
```

Attendu : `ImportError: cannot import name 'extract_elements_hors_brut'`

- [ ] **Étape 3 : Implémenter**

```python
# À ajouter à backend/app/modules/exports/infrastructure/payslip_accounting_extract.py

def extract_elements_hors_brut(payslip_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Éléments qui s'ajoutent au net à payer sans transiter par le brut.

    Primes non soumises (indemnité de transport…) et participation. Sans
    contrepartie au débit, l'OD est déséquilibrée d'exactement leur total.
    """
    elements: List[Dict[str, Any]] = []

    for prime in payslip_data.get("primes_non_soumises") or []:
        if not isinstance(prime, dict):
            continue
        montant = float(prime.get("montant", 0) or 0)
        if montant == 0:
            continue
        elements.append(
            {
                "element_key": str(prime.get("prime_id") or "prime_non_soumise"),
                "libelle": str(prime.get("libelle") or "Prime non soumise"),
                "montant": montant,
            }
        )

    participation = payslip_data.get("participations")
    if isinstance(participation, dict):
        montant = float(participation.get("montant_verse", 0) or 0)
        if montant != 0:
            elements.append(
                {
                    "element_key": "participation",
                    "libelle": str(participation.get("libelle") or "Participation"),
                    "montant": montant,
                }
            )

    return elements
```

- [ ] **Étape 4 : Vérifier que le test passe**

```bash
cd backend && ./venv/bin/pytest tests/unit/exports/test_payslip_accounting_extract.py -v
```

Attendu : tous PASS, dont les 7 nouveaux.

- [ ] **Étape 5 : Vérifier la structure réelle de `participations`**

Le test suppose `participations.montant_verse`. Deux bulletins de production en portent une ; confirmer la clé avant de considérer la tâche finie :

```sql
select jsonb_pretty(payslip_data->'participations')
  from payslips
 where payslip_data->'participations' is not null
   and payslip_data->'participations' <> 'null'::jsonb
 limit 1;
```

Si la clé diffère, corriger l'implémentation **et** le test.

- [ ] **Étape 6 : Commit**

```bash
git add backend/app/modules/exports/infrastructure/payslip_accounting_extract.py backend/tests/unit/exports/test_payslip_accounting_extract.py
git commit -m "feat(compta): extraction des éléments hors brut du bulletin

Indemnité de transport et participation s'ajoutent au net à payer sans passer
par le brut. Ils n'étaient extraits nulle part, d'où l'absence de contrepartie
au débit et le déséquilibre de l'OD."
```

---

## Tâche 4 : Ventilation des cotisations par organisme

**Fichiers :**
- Modifier : `backend/app/modules/exports/domain/charges_organisme.py`
- Modifier : `backend/app/modules/exports/infrastructure/payroll_ledger.py:572-628`
- Test : `backend/tests/unit/exports/test_payroll_ledger.py` (ajouter une classe)

**Interfaces :**
- Consomme : `resolve_organisme_from_coti_id`, `default_accounts_for`, `AccountPair` (tâche 1).
- Produit : `_accounts_for_cotisation(coti: dict, mappings: dict) -> tuple[str, str, str]` retournant `(organisme, compte_charge, compte_tiers)`.

- [ ] **Étape 1 : Écrire le test qui échoue**

```python
# À ajouter à backend/tests/unit/exports/test_payroll_ledger.py

from app.modules.exports.domain.accounting_plan import (
    ORGANISME_MUTUELLE,
    ORGANISME_URSSAF,
)


class TestVentilationParOrganisme:
    def test_cotisation_urssaf_rattachee_meme_sans_le_mot_dans_le_libelle(self):
        coti = {
            "coti_id": "securite_sociale_maladie",
            "libelle": "Sécurité sociale - Maladie, Maternité, Invalidité, Décès",
            "montant_patronal": 501.28,
        }
        organisme, charge, tiers = ledger_module._accounts_for_cotisation(coti, {})
        assert organisme == ORGANISME_URSSAF
        assert charge == "645100"
        assert tiers == "431000"

    def test_mutuelle_rattachee_quel_que_soit_le_libelle_societe(self):
        coti = {"coti_id": "mutuelle", "libelle": "GAN Isolé 2026 (EMU3)", "montant_patronal": 29.23}
        organisme, charge, tiers = ledger_module._accounts_for_cotisation(coti, {})
        assert organisme == ORGANISME_MUTUELLE
        assert tiers == "437020"

    def test_mapping_societe_surcharge_le_defaut(self):
        mappings = {
            "organisme_mutuelle": {
                "compte_charge": "64524200",
                "compte_tiers": "43702000",
                "organisme": "MUTUELLE",
            }
        }
        coti = {"coti_id": "mutuelle", "libelle": "AG2R MUTUELLE", "montant_patronal": 126.28}
        organisme, charge, tiers = ledger_module._accounts_for_cotisation(coti, mappings)
        assert organisme == ORGANISME_MUTUELLE
        assert charge == "64524200"
        assert tiers == "43702000"

    def test_cotisation_inconnue_retourne_des_comptes_vides(self):
        coti = {"coti_id": "cotisation_martienne", "libelle": "Inconnue", "montant_patronal": 10.0}
        organisme, charge, tiers = ledger_module._accounts_for_cotisation(coti, {})
        assert organisme == "INCONNU"
        assert charge == ""
        assert tiers == ""
```

- [ ] **Étape 2 : Vérifier que le test échoue**

```bash
cd backend && ./venv/bin/pytest tests/unit/exports/test_payroll_ledger.py::TestVentilationParOrganisme -v
```

Attendu : `AttributeError: module ... has no attribute '_accounts_for_cotisation'`

- [ ] **Étape 3 : Implémenter la résolution**

Ajouter dans `payroll_ledger.py`, après `_resolve_mapping` (ligne 272) :

```python
from app.modules.exports.domain.accounting_plan import (
    ORGANISME_INCONNU,
    default_accounts_for,
    resolve_organisme_from_coti_id,
)

_ORGANISME_TO_RUBRIQUE = {
    "URSSAF": "organisme_urssaf",
    "RETRAITE": "organisme_retraite",
    "RETRAITE_SUP": "organisme_retraite_sup",
    "MUTUELLE": "organisme_mutuelle",
    "PREVOYANCE": "organisme_prevoyance",
}


def _accounts_for_cotisation(
    coti: Dict[str, Any], mappings: Dict[str, Dict[str, Any]]
) -> Tuple[str, str, str]:
    """Retourne (organisme, compte de charge, compte de tiers) d'une cotisation.

    Cascade : mapping société → défaut plateforme. Un organisme non rattaché
    retourne des comptes vides ; l'appelant doit le signaler.
    """
    organisme = resolve_organisme_from_coti_id(
        coti.get("coti_id"), str(coti.get("libelle") or "")
    )
    if organisme == ORGANISME_INCONNU:
        return organisme, "", ""

    rubrique = _ORGANISME_TO_RUBRIQUE.get(organisme, "")
    mapping = mappings.get(rubrique) or {}
    pair = default_accounts_for(organisme)

    compte_charge = str(
        mapping.get("compte_charge") or (pair.compte_charge if pair else "")
    )
    compte_tiers = str(
        mapping.get("compte_tiers") or (pair.compte_tiers if pair else "")
    )
    return organisme, compte_charge, compte_tiers
```

- [ ] **Étape 4 : Vérifier que le test passe**

```bash
cd backend && ./venv/bin/pytest tests/unit/exports/test_payroll_ledger.py -v
```

Attendu : tous PASS.

- [ ] **Étape 5 : Commit**

```bash
git add backend/app/modules/exports/infrastructure/payroll_ledger.py backend/tests/unit/exports/test_payroll_ledger.py
git commit -m "feat(compta): résolution des comptes d'une cotisation par organisme

Cascade mapping société → défaut plateforme, rattachement sur coti_id."
```

---

## Tâche 5 : Écritures équilibrées par construction

Le cœur du chantier. Chaque montant est posé des deux côtés au moment où il est lu.

**Fichiers :**
- Modifier : `backend/app/modules/exports/infrastructure/payroll_ledger.py:572-678`
- Test : `backend/tests/unit/exports/test_ledger_balance.py` (créer)

**Interfaces :**
- Consomme : `_accounts_for_cotisation` (tâche 4), `extract_elements_hors_brut` (tâche 3).
- Produit : `build_payroll_ledger` renvoie des écritures dont la somme des débits égale celle des crédits à 0,01 € près, et `od_totals["anomalies"]: list[dict]` listant les montants sans compte.

- [ ] **Étape 1 : Écrire le test qui échoue**

```python
# backend/tests/unit/exports/test_ledger_balance.py
"""Équilibre de l'OD — le fichier est refusé plutôt que faux."""

from unittest.mock import patch

import pytest

from app.modules.exports.infrastructure import payroll_ledger as ledger_module

pytestmark = pytest.mark.unit


def _payslip(
    brut: float,
    net: float,
    cot_sal: float,
    cot_pat: float,
    pas: float,
    detail=None,
    hors_brut=None,
):
    return {
        "employee_id": "emp-1",
        "employee_name": "Salarié Test",
        "brut": brut,
        "net_a_payer": net,
        "cotisations_salariales": cot_sal,
        "cotisations_patronales": cot_pat,
        "pas": pas,
        "cotisations_detail": detail or [],
        "elements_hors_brut": hors_brut or [],
    }


def _build(payslips, totals=None, mappings=None):
    """Construit le registre en neutralisant les accès base annexes."""
    computed = totals or {
        "total_brut": sum(p["brut"] for p in payslips),
        "total_net_a_payer": sum(p["net_a_payer"] for p in payslips),
        "total_cotisations_salariales": sum(p["cotisations_salariales"] for p in payslips),
        "total_cotisations_patronales": sum(p["cotisations_patronales"] for p in payslips),
        "total_pas": sum(p["pas"] for p in payslips),
        "employees_count": len(payslips),
    }
    with patch.object(
        ledger_module, "get_payslip_data_for_od", return_value=(payslips, computed)
    ), patch.object(
        ledger_module, "get_accounting_mappings", return_value=mappings or {}
    ), patch.object(
        ledger_module, "list_loan_repayments_by_period", return_value=[]
    ), patch(
        "app.modules.exports.infrastructure.export_acomptes.get_acomptes_data",
        return_value=([], [], {}, {}),
    ), patch(
        "app.modules.exports.infrastructure.export_saisies.get_saisies_data",
        return_value=([], {}, {}),
    ), patch(
        "app.modules.exports.infrastructure.export_notes_frais.get_notes_frais_ecritures",
        return_value=[],
    ):
        return ledger_module.build_payroll_ledger("co-1", "2026-06")


class TestEquilibre:
    def test_bulletin_simple_equilibre(self):
        """brut = net + cotisations salariales + PAS"""
        payslips = [
            _payslip(
                brut=3000.0,
                net=2500.0,
                cot_sal=400.0,
                cot_pat=600.0,
                pas=100.0,
                detail=[
                    {
                        "coti_id": "securite_sociale_maladie",
                        "libelle": "Sécurité sociale - Maladie",
                        "montant_salarial": 400.0,
                        "montant_patronal": 600.0,
                    }
                ],
            )
        ]
        _, totals, _ = _build(payslips)
        assert totals["ecart"] <= 0.01
        assert totals["equilibre"] is True

    def test_element_hors_brut_equilibre_par_sa_charge(self):
        """Le cas Colorplast juin 2026 : 437,53 € d'indemnité de transport.
        Avant correction, l'écart valait exactement ce montant."""
        payslips = [
            _payslip(
                brut=3000.0,
                net=2937.53,
                cot_sal=400.0,
                cot_pat=600.0,
                pas=100.0,
                detail=[
                    {
                        "coti_id": "securite_sociale_maladie",
                        "libelle": "Sécurité sociale - Maladie",
                        "montant_salarial": 400.0,
                        "montant_patronal": 600.0,
                    }
                ],
                hors_brut=[
                    {
                        "element_key": "indemnite_de_transport",
                        "libelle": "Indemnite de transport",
                        "montant": 437.53,
                    }
                ],
            )
        ]
        ecritures, totals, _ = _build(payslips)
        assert totals["ecart"] <= 0.01, totals
        comptes = {e["compte_comptable"] for e in ecritures}
        assert "648000" in comptes

    def test_participation_equilibree(self):
        """Le cas Colorplast mai 2026 : le net dépasse le brut de 4 436 €."""
        payslips = [
            _payslip(
                brut=3000.0,
                net=6936.0,
                cot_sal=400.0,
                cot_pat=600.0,
                pas=100.0,
                detail=[
                    {
                        "coti_id": "securite_sociale_maladie",
                        "libelle": "Sécurité sociale - Maladie",
                        "montant_salarial": 400.0,
                        "montant_patronal": 600.0,
                    }
                ],
                hors_brut=[
                    {"element_key": "participation", "libelle": "Participation 2025", "montant": 4436.0}
                ],
            )
        ]
        _, totals, _ = _build(payslips)
        assert totals["ecart"] <= 0.01, totals

    def test_allegement_patronal_pose_des_deux_cotes(self):
        payslips = [
            _payslip(
                brut=3000.0,
                net=2500.0,
                cot_sal=400.0,
                cot_pat=200.0,
                pas=100.0,
                detail=[
                    {
                        "coti_id": "securite_sociale_maladie",
                        "libelle": "Sécurité sociale - Maladie",
                        "montant_salarial": 400.0,
                        "montant_patronal": 600.0,
                    },
                    {
                        "coti_id": "reduction_generale",
                        "libelle": "Réduction générale de cotisations patronales",
                        "montant_salarial": 0.0,
                        "montant_patronal": -400.0,
                    },
                ],
            )
        ]
        _, totals, _ = _build(payslips)
        assert totals["ecart"] <= 0.01, totals

    def test_cotisation_sans_compte_remonte_une_anomalie_et_nest_pas_postee(self):
        payslips = [
            _payslip(
                brut=3000.0,
                net=2500.0,
                cot_sal=400.0,
                cot_pat=600.0,
                pas=100.0,
                detail=[
                    {
                        "coti_id": "cotisation_martienne",
                        "libelle": "Cotisation inconnue",
                        "montant_salarial": 0.0,
                        "montant_patronal": 50.0,
                    }
                ],
            )
        ]
        _, totals, _ = _build(payslips)
        anomalies = totals.get("anomalies") or []
        assert any(a["code"] == "organisme_non_rattache" for a in anomalies), anomalies
        assert any("cotisation_martienne" in str(a.get("detail", "")) for a in anomalies)
```

- [ ] **Étape 2 : Vérifier que le test échoue**

```bash
cd backend && ./venv/bin/pytest tests/unit/exports/test_ledger_balance.py -v
```

Attendu : échecs sur `test_element_hors_brut_equilibre_par_sa_charge`, `test_participation_equilibree` et `test_cotisation_sans_compte_remonte_une_anomalie_et_nest_pas_postee`.

- [ ] **Étape 3 : Alimenter `elements_hors_brut` dans les données de bulletin**

Dans `export_ecritures_comptables.py`, fonction `get_payslip_data_for_od`, ajouter l'appel à l'extracteur et le champ dans chaque entrée de `payslip_list` :

```python
from app.modules.exports.infrastructure.payslip_accounting_extract import (
    extract_cotisations_from_payslip,
    extract_elements_hors_brut,
    extract_pas_amount,
)

# ... dans la boucle de construction de payslip_list, ajouter la clé :
        "elements_hors_brut": extract_elements_hors_brut(payslip_data),
```

- [ ] **Étape 4 : Remplacer la boucle de cotisations du moteur**

Dans `payroll_ledger.py`, remplacer le bloc `for payslip in payslip_list:` des lignes 572 à 628 par :

```python
    charges_par_compte: Dict[Tuple[str, str, str], float] = defaultdict(float)
    dettes_par_compte: Dict[Tuple[str, str, str], float] = defaultdict(float)
    anomalies: List[Dict[str, Any]] = []

    for payslip in payslip_list:
        entry_group = (
            payslip.get("establishment_label") or "Principal"
            if regroupement == "par_etablissement"
            else group_key
        )
        for coti in payslip.get("cotisations_detail", []):
            if not isinstance(coti, dict):
                continue
            montant_pat = float(coti.get("montant_patronal", 0) or 0)
            montant_sal = float(coti.get("montant_salarial", 0) or 0)
            if montant_pat == 0 and montant_sal == 0:
                continue

            organisme, compte_charge, compte_tiers = _accounts_for_cotisation(
                coti, mappings
            )
            if not compte_charge or not compte_tiers:
                anomalies.append(
                    {
                        "code": "organisme_non_rattache",
                        "label": "Cotisation sans compte comptable",
                        "detail": f"{coti.get('coti_id') or '?'} — {coti.get('libelle') or ''}",
                        "montant": _round2(abs(montant_pat) + abs(montant_sal)),
                    }
                )
                tracker.skip(
                    f"cotisation non postée ({_round2(abs(montant_pat))}€) : "
                    f"organisme non rattaché pour {coti.get('coti_id') or coti.get('libelle')}"
                )
                continue

            # Part patronale : charge au débit, dette au crédit.
            if montant_pat != 0:
                charges_par_compte[(entry_group, organisme, compte_charge)] += montant_pat
                dettes_par_compte[(entry_group, organisme, compte_tiers)] += montant_pat
            # Part salariale : dette au crédit, la contrepartie est le brut déjà débité.
            if montant_sal != 0:
                dettes_par_compte[(entry_group, organisme, compte_tiers)] += montant_sal

    for (grp, organisme, compte), montant in sorted(charges_par_compte.items()):
        if abs(montant) < 0.005:
            continue
        libelle_organisme = ORGANISMES.get(organisme, organisme)
        if montant > 0:
            ecritures.append(
                _make_entry(
                    date_ecriture=date_ecriture,
                    journal="OD",
                    compte=compte,
                    libelle=f"Charges sociales {libelle_organisme} {period_label}",
                    debit=montant,
                    credit=0.0,
                    reference=reference,
                    period=period,
                    group_key=grp,
                )
            )
            tracker.add_debit("charges_patronales", montant)
        else:
            ecritures.append(
                _make_entry(
                    date_ecriture=date_ecriture,
                    journal="OD",
                    compte=compte,
                    libelle=f"Allègements {libelle_organisme} {period_label}",
                    debit=0.0,
                    credit=abs(montant),
                    reference=reference,
                    period=period,
                    group_key=grp,
                )
            )
            tracker.add_credit("charges_patronales_allegements", abs(montant))

    for (grp, organisme, compte), montant in sorted(dettes_par_compte.items()):
        if abs(montant) < 0.005:
            continue
        libelle_organisme = ORGANISMES.get(organisme, organisme)
        if montant > 0:
            ecritures.append(
                _make_entry(
                    date_ecriture=date_ecriture,
                    journal="OD",
                    compte=compte,
                    libelle=f"Dette {libelle_organisme} {period_label}",
                    debit=0.0,
                    credit=montant,
                    reference=reference,
                    period=period,
                    group_key=grp,
                )
            )
            tracker.add_credit("dettes_organismes", montant)
        else:
            ecritures.append(
                _make_entry(
                    date_ecriture=date_ecriture,
                    journal="OD",
                    compte=compte,
                    libelle=f"Dette {libelle_organisme} (allègements) {period_label}",
                    debit=abs(montant),
                    credit=0.0,
                    reference=reference,
                    period=period,
                    group_key=grp,
                )
            )
            tracker.add_debit("dettes_organismes_allegements", abs(montant))
```

Ajouter l'import en tête de fichier :

```python
from app.modules.exports.domain.accounting_plan import ELEMENT_ACCOUNTS, ORGANISMES
```

**Supprimer** le bloc des lignes 630-678 (l'ancienne écriture globale « Dettes organismes sociaux »), désormais produit par la boucle ci-dessus. Supprimer aussi `dettes_par_groupe` et `charges_par_caisse`, devenus inutiles.

- [ ] **Étape 4 bis : Retirer le crédit global des cotisations salariales**

**Sans cette étape, la part salariale est comptée deux fois** : une fois par l'ancien crédit global de `_append_core_salary_entries`, une fois par la nouvelle dette par organisme. Le test `test_bulletin_simple_equilibre` échouerait avec un écart égal au total des cotisations salariales.

Dans `_append_core_salary_entries` (lignes 435-456), supprimer entièrement le bloc `cot_sal`, ainsi que la ligne `m_cot_sal = _resolve_mapping(mappings, "cotisation_salariale")` (ligne 390). La part salariale est désormais créditée sur le compte de tiers de son organisme, au même titre que la part patronale.

Vérifier qu'aucune autre écriture ne subsiste pour cette rubrique :

```bash
cd backend && grep -n "cotisation_salariale\|cotisations_salariales" app/modules/exports/infrastructure/payroll_ledger.py
```

Attendu : plus aucune écriture postée pour cette rubrique. Les occurrences restantes ne doivent servir qu'au diagnostic (`_BalanceTracker`, `_build_gap_analysis`), qui compare l'OD aux bulletins et doit continuer de fonctionner.

- [ ] **Étape 5 : Poster les éléments hors brut**

Ajouter, juste avant le bloc `if include_notes_frais:` (ligne 771) :

```python
    elements_par_cle: Dict[Tuple[str, str], float] = defaultdict(float)
    for payslip in payslip_list:
        for element in payslip.get("elements_hors_brut", []) or []:
            if not isinstance(element, dict):
                continue
            montant = float(element.get("montant", 0) or 0)
            if montant == 0:
                continue
            cle = str(element.get("element_key") or "prime_non_soumise")
            elements_par_cle[(cle, str(element.get("libelle") or cle))] += montant

    for (cle, libelle), montant in sorted(elements_par_cle.items()):
        mapping_element = _resolve_mapping(mappings, cle)
        compte = str(
            mapping_element.get("compte_charge")
            or mapping_element.get("compte_comptable")
            or ""
        )
        if not compte:
            pair = ELEMENT_ACCOUNTS.get(cle)
            compte = pair.compte_charge if pair else ""
        if not compte:
            anomalies.append(
                {
                    "code": "element_hors_brut_non_mappe",
                    "label": "Élément hors brut sans compte de charge",
                    "detail": f"{cle} — {libelle}",
                    "montant": _round2(montant),
                }
            )
            tracker.skip(
                f"élément hors brut non posté ({_round2(montant)}€) : "
                f"aucun compte pour {cle}"
            )
            continue
        ecritures.append(
            _make_entry(
                date_ecriture=date_ecriture,
                journal="OD",
                compte=compte,
                libelle=f"{libelle} {period_label}",
                debit=montant,
                credit=0.0,
                reference=reference,
                period=period,
                group_key=group_key,
            )
        )
        tracker.add_debit("elements_hors_brut", montant)
```

- [ ] **Étape 6 : Exposer les anomalies dans les totaux**

Modifier le dictionnaire `od_totals` (ligne 806) :

```python
    od_totals = {
        "total_debit": _round2(total_debit),
        "total_credit": _round2(total_credit),
        "equilibre": abs(total_debit - total_credit) < 0.01,
        "ecart": _round2(abs(total_debit - total_credit)),
        "anomalies": anomalies,
        "balance_debug": balance_debug,
    }
```

- [ ] **Étape 7 : Vérifier que les tests passent**

```bash
cd backend && ./venv/bin/pytest tests/unit/exports/ -v
```

Attendu : tous PASS. Les tests existants `test_payroll_ledger.py` et `test_balance_tracker.py` doivent continuer de passer ; s'ils reposaient sur l'ancien libellé « Charges … — AUTRE », les mettre à jour.

- [ ] **Étape 8 : Vérifier sur les données réelles**

```bash
cd backend && ./venv/bin/python -c "
from app.modules.exports.infrastructure.payroll_ledger import build_payroll_ledger
for period in ['2026-05', '2026-06']:
    ec, tot, _ = build_payroll_ledger('dbe2b9f5-44dd-41bc-a625-36ed33d160f7', period, None, None, scope='full')
    print(period, '| lignes', len(ec), '| ecart', tot['ecart'], '| anomalies', len(tot['anomalies']))
    for a in tot['anomalies']:
        print('   ', a['code'], a['detail'], a['montant'])
"
```

Attendu : écart de 0.0 sur les deux périodes. Toute anomalie restante doit être expliquée avant de continuer.

- [ ] **Étape 9 : Commit**

```bash
git add backend/app/modules/exports/infrastructure/payroll_ledger.py backend/app/modules/exports/infrastructure/export_ecritures_comptables.py backend/tests/unit/exports/test_ledger_balance.py
git commit -m "fix(compta): OD équilibrée par construction

Chaque montant du bulletin est posé des deux côtés au moment où il est lu :
part patronale en charge et en dette, part salariale en dette, éléments hors
brut en charge. Les montants sans compte remontent en anomalie au lieu d'être
absorbés.

Corrige l'écart de 437,53 € sur Colorplast juin 2026 et de 10 571,53 € en mai."
```

---

## Tâche 6 : Agrégation par compte

Le cabinet sort 19 lignes agrégées ; nous en produisons 137.

**Fichiers :**
- Modifier : `backend/app/modules/exports/infrastructure/payroll_ledger.py` (fonction `ledger_to_od_export_rows`)
- Test : `backend/tests/unit/exports/test_ledger_balance.py` (ajouter une classe)

**Interfaces :**
- Consomme : les écritures produites en tâche 5.
- Produit : `aggregate_ledger_by_account(ecritures: list[dict]) -> list[dict]` — une ligne par `(journal, compte, sens)`.

- [ ] **Étape 1 : Écrire le test qui échoue**

```python
# À ajouter à backend/tests/unit/exports/test_ledger_balance.py

class TestAgregationParCompte:
    def test_lignes_du_meme_compte_fusionnees(self):
        ecritures = [
            {"date_ecriture": "2026-06-30", "journal": "OD", "compte_comptable": "645100",
             "libelle": "Charges sociales URSSAF Juin 2026", "debit": 100.0, "credit": 0.0,
             "analytique": None, "reference_export": "OD_PAIE_2026-06", "periode_paie": "2026-06"},
            {"date_ecriture": "2026-06-30", "journal": "OD", "compte_comptable": "645100",
             "libelle": "Charges sociales URSSAF Juin 2026", "debit": 50.0, "credit": 0.0,
             "analytique": None, "reference_export": "OD_PAIE_2026-06", "periode_paie": "2026-06"},
        ]
        rows = ledger_module.aggregate_ledger_by_account(ecritures)
        assert len(rows) == 1
        assert rows[0]["debit"] == 150.0

    def test_debit_et_credit_du_meme_compte_restent_separes(self):
        """Le cabinet présente les deux sens sur des lignes distinctes."""
        ecritures = [
            {"date_ecriture": "2026-06-30", "journal": "OD", "compte_comptable": "645100",
             "libelle": "Charges sociales URSSAF Juin 2026", "debit": 100.0, "credit": 0.0,
             "analytique": None, "reference_export": "OD_PAIE_2026-06", "periode_paie": "2026-06"},
            {"date_ecriture": "2026-06-30", "journal": "OD", "compte_comptable": "645100",
             "libelle": "Allègements URSSAF Juin 2026", "debit": 0.0, "credit": 30.0,
             "analytique": None, "reference_export": "OD_PAIE_2026-06", "periode_paie": "2026-06"},
        ]
        rows = ledger_module.aggregate_ledger_by_account(ecritures)
        assert len(rows) == 2

    def test_agregation_preserve_lequilibre(self):
        ecritures = [
            {"date_ecriture": "2026-06-30", "journal": "OD", "compte_comptable": "641000",
             "libelle": "Salaires", "debit": 3000.0, "credit": 0.0, "analytique": None,
             "reference_export": "OD_PAIE_2026-06", "periode_paie": "2026-06"},
            {"date_ecriture": "2026-06-30", "journal": "OD", "compte_comptable": "421000",
             "libelle": "Net à payer", "debit": 0.0, "credit": 2500.0, "analytique": None,
             "reference_export": "OD_PAIE_2026-06", "periode_paie": "2026-06"},
            {"date_ecriture": "2026-06-30", "journal": "OD", "compte_comptable": "431000",
             "libelle": "Dette URSSAF", "debit": 0.0, "credit": 500.0, "analytique": None,
             "reference_export": "OD_PAIE_2026-06", "periode_paie": "2026-06"},
        ]
        rows = ledger_module.aggregate_ledger_by_account(ecritures)
        assert round(sum(r["debit"] for r in rows), 2) == round(sum(r["credit"] for r in rows), 2)
```

- [ ] **Étape 2 : Vérifier que le test échoue**

```bash
cd backend && ./venv/bin/pytest tests/unit/exports/test_ledger_balance.py::TestAgregationParCompte -v
```

Attendu : `AttributeError: module ... has no attribute 'aggregate_ledger_by_account'`

- [ ] **Étape 3 : Implémenter**

Ajouter à la fin de `payroll_ledger.py` :

```python
def aggregate_ledger_by_account(
    ecritures: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Regroupe les écritures par compte et par sens.

    Le cabinet présente une ligne par compte pour la société entière. Débit et
    crédit d'un même compte restent sur deux lignes distinctes, comme sur l'OD
    de référence.
    """
    grouped: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
    for e in ecritures:
        sens = "debit" if float(e.get("debit", 0) or 0) > 0 else "credit"
        cle = (
            str(e.get("journal", "OD")),
            str(e.get("compte_comptable", "")),
            sens,
            str(e.get("group_key", "global")),
        )
        if cle not in grouped:
            grouped[cle] = {
                "date_ecriture": e["date_ecriture"],
                "journal": e.get("journal", "OD"),
                "compte_comptable": e.get("compte_comptable", ""),
                "libelle": e.get("libelle", ""),
                "debit": 0.0,
                "credit": 0.0,
                "analytique": e.get("analytique"),
                "reference_export": e.get("reference_export", ""),
                "periode_paie": e["periode_paie"],
            }
        grouped[cle]["debit"] = _round2(
            grouped[cle]["debit"] + float(e.get("debit", 0) or 0)
        )
        grouped[cle]["credit"] = _round2(
            grouped[cle]["credit"] + float(e.get("credit", 0) or 0)
        )

    return [
        row
        for row in grouped.values()
        if abs(row["debit"]) > 0.005 or abs(row["credit"]) > 0.005
    ]
```

Puis brancher l'agrégation dans `ledger_to_od_export_rows` :

```python
def ledger_to_od_export_rows(
    ecritures: List[Dict[str, Any]], aggregate: bool = True
) -> List[Dict[str, Any]]:
    """Convertit les écritures registre vers le format export OD standard.

    `aggregate=True` (défaut) produit une ligne par compte, comme le cabinet.
    `aggregate=False` conserve le détail, pour les contrôles.
    """
    source = aggregate_ledger_by_account(ecritures) if aggregate else ecritures
    return [
        {
            "date_ecriture": e["date_ecriture"],
            "journal": e["journal"],
            "compte_comptable": e["compte_comptable"],
            "libelle": e["libelle"],
            "debit": e["debit"],
            "credit": e["credit"],
            "analytique": e.get("analytique"),
            "reference_export": e.get("reference_export", ""),
            "periode_paie": e["periode_paie"],
        }
        for e in source
    ]
```

- [ ] **Étape 4 : Vérifier que le test passe**

```bash
cd backend && ./venv/bin/pytest tests/unit/exports/ -v
```

Attendu : tous PASS.

- [ ] **Étape 5 : Vérifier le nombre de lignes sur les données réelles**

```bash
cd backend && ./venv/bin/python -c "
from app.modules.exports.infrastructure.payroll_ledger import build_payroll_ledger, ledger_to_od_export_rows
ec, tot, _ = build_payroll_ledger('dbe2b9f5-44dd-41bc-a625-36ed33d160f7', '2026-06', None, None, scope='full')
rows = ledger_to_od_export_rows(ec)
for r in sorted(rows, key=lambda x: x['compte_comptable']):
    print(f\"{r['compte_comptable']:<10} {r['libelle'][:45]:<47} D {r['debit']:>10.2f}  C {r['credit']:>10.2f}\")
print('lignes', len(rows), '| debit', round(sum(r['debit'] for r in rows),2), '| credit', round(sum(r['credit'] for r in rows),2))
"
```

Attendu : une vingtaine de lignes, débit égal au crédit.

- [ ] **Étape 6 : Commit**

```bash
git add backend/app/modules/exports/infrastructure/payroll_ledger.py backend/tests/unit/exports/test_ledger_balance.py
git commit -m "feat(compta): agrégation de l'OD par compte

Une ligne par compte et par sens pour la société entière, comme le fait le
cabinet — 137 lignes ramenées à une vingtaine."
```

---

## Tâche 7 : Refus d'export si déséquilibre

Changement de comportement volontaire : un fichier faux ne doit plus sortir.

**Fichiers :**
- Modifier : `backend/app/modules/exports/infrastructure/export_ecritures_comptables.py`
- Modifier : `backend/app/modules/exports/infrastructure/export_fec.py`
- Test : `backend/tests/unit/exports/test_ledger_balance.py` (ajouter une classe)

**Interfaces :**
- Consomme : `od_totals["equilibre"]` et `od_totals["anomalies"]` (tâche 5).
- Produit : `class LedgerImbalanceError(ValueError)` levée par `assert_ledger_balanced(od_totals)`.

- [ ] **Étape 1 : Écrire le test qui échoue**

```python
# À ajouter à backend/tests/unit/exports/test_ledger_balance.py

from app.modules.exports.infrastructure.payroll_ledger import (
    LedgerImbalanceError,
    assert_ledger_balanced,
)


class TestRefusExportDesequilibre:
    def test_od_equilibree_passe(self):
        assert_ledger_balanced({"equilibre": True, "ecart": 0.0, "anomalies": []})

    def test_od_desequilibree_leve_une_erreur_explicite(self):
        with pytest.raises(LedgerImbalanceError) as exc:
            assert_ledger_balanced(
                {
                    "equilibre": False,
                    "ecart": 437.53,
                    "anomalies": [
                        {
                            "code": "element_hors_brut_non_mappe",
                            "label": "Élément hors brut sans compte de charge",
                            "detail": "indemnite_de_transport — Indemnite de transport",
                            "montant": 437.53,
                        }
                    ],
                }
            )
        message = str(exc.value)
        assert "437.53" in message
        assert "indemnite_de_transport" in message

    def test_message_sans_anomalie_reste_actionnable(self):
        with pytest.raises(LedgerImbalanceError) as exc:
            assert_ledger_balanced({"equilibre": False, "ecart": 12.0, "anomalies": []})
        assert "12.0" in str(exc.value)
```

- [ ] **Étape 2 : Vérifier que le test échoue**

```bash
cd backend && ./venv/bin/pytest tests/unit/exports/test_ledger_balance.py::TestRefusExportDesequilibre -v
```

Attendu : `ImportError: cannot import name 'LedgerImbalanceError'`

- [ ] **Étape 3 : Implémenter**

Ajouter à `payroll_ledger.py` :

```python
class LedgerImbalanceError(ValueError):
    """L'OD ne s'équilibre pas — le fichier n'est pas produit."""


def assert_ledger_balanced(od_totals: Dict[str, Any]) -> None:
    """Refuse un registre déséquilibré, avec le détail de ce qui manque.

    Un fichier d'écritures déséquilibré est rejeté par tout logiciel comptable.
    Mieux vaut un message actionnable qu'un export silencieusement faux.
    """
    if od_totals.get("equilibre"):
        return

    ecart = od_totals.get("ecart", 0)
    lignes = [
        f"L'écriture ne s'équilibre pas : écart de {ecart} €.",
    ]
    anomalies = od_totals.get("anomalies") or []
    if anomalies:
        lignes.append("Éléments sans compte comptable :")
        for a in anomalies:
            lignes.append(f"  — {a.get('detail', '')} ({a.get('montant', 0)} €)")
        lignes.append(
            "Renseignez les comptes manquants dans Exports > Comptes comptables."
        )
    else:
        lignes.append(
            "Aucun élément non mappé détecté : vérifiez le détail de l'équilibre "
            "dans le panneau de diagnostic de l'OD."
        )
    raise LedgerImbalanceError("\n".join(lignes))
```

- [ ] **Étape 4 : Brancher le refus sur les générateurs**

Dans `export_ecritures_comptables.py`, dans chacune des quatre fonctions qui appellent `build_payroll_ledger` (lignes 196, 219, 242, 266), ajouter juste après l'appel :

```python
    assert_ledger_balanced(od_totals)
```

Avec l'import :

```python
from app.modules.exports.infrastructure.payroll_ledger import assert_ledger_balanced
```

Faire de même dans `export_fec.py`, après l'appel ligne 51.

- [ ] **Étape 5 : Traduire l'erreur en réponse HTTP**

Dans `backend/app/modules/exports/api/router.py`, ajouter un gestionnaire pour que le message remonte tel quel à l'écran plutôt qu'en erreur 500. Repérer le bloc `except` du point d'entrée de génération d'export et ajouter avant les autres :

```python
    except LedgerImbalanceError as e:
        raise HTTPException(status_code=422, detail=str(e))
```

Avec l'import :

```python
from app.modules.exports.infrastructure.payroll_ledger import LedgerImbalanceError
```

- [ ] **Étape 6 : Vérifier que les tests passent**

```bash
cd backend && ./venv/bin/pytest tests/unit/exports/ -v
```

Attendu : tous PASS.

- [ ] **Étape 7 : Commit**

```bash
git add backend/app/modules/exports/infrastructure/payroll_ledger.py backend/app/modules/exports/infrastructure/export_ecritures_comptables.py backend/app/modules/exports/infrastructure/export_fec.py backend/app/modules/exports/api/router.py backend/tests/unit/exports/test_ledger_balance.py
git commit -m "feat(compta): refuser un export d'écritures déséquilibré

Le fichier n'est plus produit si l'écart dépasse 0,01 €. Le message liste les
éléments sans compte et renvoie vers l'écran de paramétrage."
```

---

## Tâche 8 : Suppression du module dupliqué

**Fichiers :**
- Supprimer : `backend/app/modules/payroll/exports/ecritures_comptables.py`
- Modifier : `backend/app/modules/exports/infrastructure/providers.py:17,233`
- Modifier : `backend/app/modules/exports/application/service.py:781,797`

- [ ] **Étape 1 : Recenser les appelants**

```bash
cd backend && grep -rn "payroll.exports.ecritures_comptables\|generate_od_salaires" app/ tests/ --include="*.py"
```

Noter chaque emplacement avant de modifier.

- [ ] **Étape 2 : Rediriger `providers.py`**

Remplacer l'import ligne 17 :

```python
from app.modules.exports.infrastructure.export_ecritures_comptables import (
    generate_od_salaires as _generate_od_salaires,
)
```

- [ ] **Étape 3 : Supprimer le module obsolète**

```bash
git rm backend/app/modules/payroll/exports/ecritures_comptables.py
```

- [ ] **Étape 4 : Vérifier qu'aucune référence ne subsiste**

```bash
cd backend && grep -rn "payroll.exports.ecritures_comptables" app/ tests/ --include="*.py"
```

Attendu : aucun résultat.

- [ ] **Étape 5 : Lancer toute la suite unitaire**

```bash
cd backend && ./venv/bin/pytest tests/unit/ -q
```

Attendu : aucun échec nouveau. Les 51 échecs d'intégration pré-existants (`schedules`, `saisies_avances`) ne concernent pas `tests/unit`.

- [ ] **Étape 6 : Commit**

```bash
git add -A backend/app/modules/payroll/exports backend/app/modules/exports/infrastructure/providers.py backend/app/modules/exports/application/service.py
git commit -m "refactor(compta): supprimer la copie obsolète du module d'écritures

payroll/exports/ecritures_comptables.py lisait structure_cotisations.cotisations,
une clé disparue des bulletins, et retournait donc zéro cotisation. Le moteur
unique est payroll_ledger."
```

---

## Tâche 9 : API des mappings

**Fichiers :**
- Modifier : `backend/app/modules/exports/schemas/accounting_mappings.py`
- Modifier : `backend/app/modules/exports/application/accounting_mappings.py`
- Test : `backend/tests/unit/exports/test_accounting_mappings.py` (fichier existant)

**Interfaces :**
- Consomme : les colonnes de la tâche 2.
- Produit : `AccountingMappingOut` et `AccountingMappingUpsert` portant `coti_id`, `compte_charge`, `compte_tiers`, `organisme`.

- [ ] **Étape 1 : Écrire le test qui échoue**

```python
# À ajouter à backend/tests/unit/exports/test_accounting_mappings.py

from app.modules.exports.application.accounting_mappings import _row_to_out


class TestChampsOrganisme:
    def test_row_to_out_expose_les_deux_comptes(self):
        row = {
            "id": "map-1",
            "company_id": "co-1",
            "rubrique_code": "organisme_mutuelle",
            "rubrique_libelle": "Mutuelle",
            "compte_comptable": "64524200",
            "compte_charge": "64524200",
            "compte_tiers": "43702000",
            "organisme": "MUTUELLE",
            "coti_id": None,
            "journal": "PAI",
            "sens": "debit",
            "type_rubrique": "charge_patronale",
            "analytique": None,
            "is_active": True,
        }
        out = _row_to_out(row)
        assert out.compte_charge == "64524200"
        assert out.compte_tiers == "43702000"
        assert out.organisme == "MUTUELLE"
        assert out.is_global_default is False

    def test_champs_absents_tolerés(self):
        """Les lignes créées avant la migration n'ont pas les nouvelles colonnes."""
        row = {
            "id": "map-2",
            "company_id": None,
            "rubrique_code": "salaire_brut",
            "rubrique_libelle": "Salaire brut",
            "compte_comptable": "641000",
            "journal": "OD",
            "sens": "debit",
            "type_rubrique": "salaire",
            "is_active": True,
        }
        out = _row_to_out(row)
        assert out.compte_charge is None
        assert out.compte_tiers is None
        assert out.organisme is None
```

- [ ] **Étape 2 : Vérifier que le test échoue**

```bash
cd backend && ./venv/bin/pytest tests/unit/exports/test_accounting_mappings.py::TestChampsOrganisme -v
```

Attendu : `AttributeError: 'AccountingMappingOut' object has no attribute 'compte_charge'`

- [ ] **Étape 3 : Étendre les schémas**

Dans `schemas/accounting_mappings.py`, ajouter aux deux modèles :

```python
class AccountingMappingOut(BaseModel):
    id: str
    company_id: Optional[str] = None
    rubrique_code: str
    rubrique_libelle: str
    compte_comptable: str
    coti_id: Optional[str] = None
    compte_charge: Optional[str] = None
    compte_tiers: Optional[str] = None
    organisme: Optional[str] = None
    journal: str = "OD"
    sens: Literal["debit", "credit"] = "debit"
    type_rubrique: str = "salaire"
    analytique: Optional[str] = None
    is_active: bool = True
    is_global_default: bool = False


class AccountingMappingUpsert(BaseModel):
    rubrique_code: str = Field(..., min_length=1)
    rubrique_libelle: str = Field(..., min_length=1)
    compte_comptable: str = Field(..., min_length=3)
    coti_id: Optional[str] = None
    compte_charge: Optional[str] = None
    compte_tiers: Optional[str] = None
    organisme: Optional[str] = None
    journal: str = "OD"
    sens: Literal["debit", "credit"] = "debit"
    type_rubrique: str = "salaire"
    analytique: Optional[str] = None
    is_active: bool = True
```

- [ ] **Étape 4 : Étendre le service**

Dans `application/accounting_mappings.py`, compléter `_row_to_out` :

```python
        coti_id=row.get("coti_id"),
        compte_charge=row.get("compte_charge"),
        compte_tiers=row.get("compte_tiers"),
        organisme=row.get("organisme"),
```

et `upsert_company_mapping`, dans `payload` :

```python
        "coti_id": body.coti_id,
        "compte_charge": body.compte_charge,
        "compte_tiers": body.compte_tiers,
        "organisme": body.organisme,
```

- [ ] **Étape 5 : Vérifier que le test passe**

```bash
cd backend && ./venv/bin/pytest tests/unit/exports/test_accounting_mappings.py -v
```

Attendu : tous PASS.

- [ ] **Étape 6 : Commit**

```bash
git add backend/app/modules/exports/schemas/accounting_mappings.py backend/app/modules/exports/application/accounting_mappings.py backend/tests/unit/exports/test_accounting_mappings.py
git commit -m "feat(compta): exposer les comptes de charge et de tiers dans l'API des mappings"
```

---

## Tâche 10 : Écran de paramétrage

**Fichiers :**
- Modifier : `frontend/src/api/exports.ts` (type `AccountingMapping`)
- Modifier : `frontend/src/components/exports/AccountingMappingsPanel.tsx`

**Interfaces :**
- Consomme : la réponse de `GET /exports/accounting-mappings` (tâche 9).
- Produit : rien pour les tâches suivantes.

- [ ] **Étape 1 : Étendre le type**

Dans `frontend/src/api/exports.ts`, repérer `export type AccountingMapping` et ajouter :

```ts
  coti_id?: string | null;
  compte_charge?: string | null;
  compte_tiers?: string | null;
  organisme?: string | null;
```

- [ ] **Étape 2 : Ajouter les colonnes au tableau**

Dans `AccountingMappingsPanel.tsx`, remplacer l'en-tête (lignes 87-94) :

```tsx
                <TableRow>
                  <TableHead>Rubrique</TableHead>
                  <TableHead>Organisme</TableHead>
                  <TableHead>Compte de charge</TableHead>
                  <TableHead>Compte de tiers</TableHead>
                  <TableHead>Journal</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
```

et le corps de ligne (lignes 98-119) :

```tsx
                  <TableRow key={m.rubrique_code}>
                    <TableCell>
                      <div className="font-medium">{m.rubrique_libelle}</div>
                      <div className="text-muted-foreground text-xs">
                        {m.coti_id ?? m.rubrique_code}
                      </div>
                    </TableCell>
                    <TableCell>{m.organisme ?? "—"}</TableCell>
                    <TableCell>
                      {m.compte_charge ? (
                        m.compte_charge
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {m.compte_tiers ? (
                        m.compte_tiers
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell>{m.journal}</TableCell>
                    <TableCell>
                      {m.is_global_default && !m.company_id ? "Défaut global" : "Société"}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button type="button" size="sm" variant="outline" onClick={() => setEditing(m)}>
                        Modifier
                      </Button>
                    </TableCell>
                  </TableRow>
```

- [ ] **Étape 3 : Ajouter les deux champs au formulaire**

Remplacer le champ « Compte comptable » (lignes 130-137) par :

```tsx
              <div className="space-y-1">
                <Label>Compte de charge (classe 6)</Label>
                <Input
                  value={editing.compte_charge ?? ""}
                  placeholder="ex. 64524200"
                  onChange={(e) => setEditing({ ...editing, compte_charge: e.target.value })}
                />
              </div>
              <div className="space-y-1">
                <Label>Compte de tiers (classe 4)</Label>
                <Input
                  value={editing.compte_tiers ?? ""}
                  placeholder="ex. 43702000"
                  onChange={(e) => setEditing({ ...editing, compte_tiers: e.target.value })}
                />
              </div>
```

et compléter l'appel de sauvegarde (lignes 170-179) :

```tsx
                  saveMutation.mutate({
                    rubrique_code: editing.rubrique_code,
                    rubrique_libelle: editing.rubrique_libelle,
                    compte_comptable:
                      editing.compte_charge || editing.compte_tiers || editing.compte_comptable,
                    coti_id: editing.coti_id ?? undefined,
                    compte_charge: editing.compte_charge ?? undefined,
                    compte_tiers: editing.compte_tiers ?? undefined,
                    organisme: editing.organisme ?? undefined,
                    journal: editing.journal,
                    sens: editing.sens,
                    type_rubrique: editing.type_rubrique,
                    analytique: editing.analytique ?? undefined,
                    is_active: true,
                  })
```

- [ ] **Étape 4 : Vérifier la compilation**

```bash
cd frontend && npm run build
```

Attendu : build réussi, aucune erreur de typage.

- [ ] **Étape 5 : Commit**

```bash
git add frontend/src/api/exports.ts frontend/src/components/exports/AccountingMappingsPanel.tsx
git commit -m "feat(compta): saisie des comptes de charge et de tiers par organisme"
```

---

## Tâche 11 : Format du cabinet

**Fichiers :**
- Modifier : `backend/app/modules/exports/infrastructure/export_formats_cabinet.py`
- Test : `backend/tests/unit/exports/test_fec_sepa.py` (ajouter une classe)

**Interfaces :**
- Consomme : les écritures agrégées (tâche 6).
- Produit : rien pour les tâches suivantes.

Éléments relevés sur l'OD de référence : journal `PAI`, référence de pièce `PAIE<MMAA>`, date au dernier jour du mois, libellé « Salaire de MM/AAAA ».

- [ ] **Étape 1 : Écrire le test qui échoue**

```python
# À ajouter à backend/tests/unit/exports/test_fec_sepa.py

from app.modules.exports.infrastructure.export_formats_cabinet import (
    format_piece_reference,
    format_libelle_ecriture,
)


class TestFormatCabinet:
    def test_reference_de_piece_au_format_du_cabinet(self):
        """Relevé sur l'OD de référence : PAIE1025 pour la période 10/2025."""
        assert format_piece_reference("2025-10") == "PAIE1025"
        assert format_piece_reference("2026-06") == "PAIE0626"

    def test_libelle_ecriture(self):
        assert format_libelle_ecriture("2025-10") == "Salaire de 10/2025"
        assert format_libelle_ecriture("2026-06") == "Salaire de 06/2026"
```

- [ ] **Étape 2 : Vérifier que le test échoue**

```bash
cd backend && ./venv/bin/pytest tests/unit/exports/test_fec_sepa.py::TestFormatCabinet -v
```

Attendu : `ImportError: cannot import name 'format_piece_reference'`

- [ ] **Étape 3 : Implémenter**

Ajouter à `export_formats_cabinet.py` :

```python
def format_piece_reference(period: str) -> str:
    """Référence de pièce au format du cabinet : PAIE + MMAA.

    Relevé sur l'OD de référence : période 10/2025 → PAIE1025.
    """
    year, month = period.split("-")
    return f"PAIE{month}{year[2:]}"


def format_libelle_ecriture(period: str) -> str:
    """Libellé d'écriture au format du cabinet : « Salaire de MM/AAAA »."""
    year, month = period.split("-")
    return f"Salaire de {month}/{year}"
```

- [ ] **Étape 4 : Vérifier que le test passe**

```bash
cd backend && ./venv/bin/pytest tests/unit/exports/test_fec_sepa.py -v
```

Attendu : tous PASS.

- [ ] **Étape 5 : Commit**

```bash
git add backend/app/modules/exports/infrastructure/export_formats_cabinet.py backend/tests/unit/exports/test_fec_sepa.py
git commit -m "feat(compta): référence de pièce et libellé au format du cabinet"
```

---

## Tâche 12 : Paramétrage d'une société et comparaison à son OD réelle

**Fichiers :**
- Créer : `backend/scripts/import_plan_comptable.py`
- Créer : `data/colorplast/comptabilite/plan_comptable.json` (hors dépôt, gitignoré)

**Interfaces :**
- Consomme : l'API de mappings (tâche 9).
- Produit : les lignes `accounting_mappings` d'une société.

- [ ] **Étape 1 : Écrire le fichier de plan comptable de Colorplast**

Relevé sur l'OD du cabinet. À placer dans `data/colorplast/comptabilite/plan_comptable.json` — **jamais dans le dépôt** :

```json
{
  "company_name": "Colorplast",
  "code_dossier_cegid": "000005",
  "journal": "PAI",
  "organismes": {
    "URSSAF":       {"compte_charge": "64510000", "compte_tiers": "43100000", "libelle": "URSSAF"},
    "RETRAITE":     {"compte_charge": "64530000", "compte_tiers": "43720000", "libelle": "Caisse de retraite"},
    "RETRAITE_SUP": {"compte_charge": "64530100", "compte_tiers": "43780000", "libelle": "Retraite supplémentaire"},
    "MUTUELLE":     {"compte_charge": "64524200", "compte_tiers": "43702000", "libelle": "Mutuelle"},
    "PREVOYANCE":   {"compte_charge": "64524100", "compte_tiers": "43740000", "libelle": "Prévoyance"}
  },
  "elements": {
    "salaire_brut":        {"compte_charge": "64110000", "compte_tiers": ""},
    "prime_soumise":       {"compte_charge": "64111300", "compte_tiers": ""},
    "net_a_payer":         {"compte_charge": "",         "compte_tiers": "42100000"},
    "pas":                 {"compte_charge": "",         "compte_tiers": "44210000"},
    "saisie_opposition":   {"compte_charge": "",         "compte_tiers": "42700000"},
    "note_de_frais":       {"compte_charge": "",         "compte_tiers": "42862500"},
    "indemnite_transport": {"compte_charge": "67181500", "compte_tiers": ""}
  }
}
```

**Note :** l'OD de référence porte deux comptes de prévoyance distincts (`43740000` / `64524100` et `43741000` / `64524300`), correspondant à deux organismes. Notre modèle n'en distingue qu'un. Tant qu'Elsa n'a pas confirmé quelle cotisation va chez lequel, ne câbler que le premier et laisser le second en anomalie visible plutôt que de répartir au hasard.

- [ ] **Étape 2 : Écrire le script d'import**

```python
# backend/scripts/import_plan_comptable.py
"""Paramètre les comptes comptables d'une société depuis son plan de comptes.

Le fichier source vit dans data/<societe>/comptabilite/plan_comptable.json et
n'est jamais versionné : il contient le paramétrage comptable du client.

Usage :
    python -m scripts.import_plan_comptable --company-id <uuid> \\
        --file data/colorplast/comptabilite/plan_comptable.json [--apply]

Sans --apply, le script affiche ce qu'il ferait sans rien écrire.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from app.core.database import supabase

ORGANISME_RUBRIQUES = {
    "URSSAF": "organisme_urssaf",
    "RETRAITE": "organisme_retraite",
    "RETRAITE_SUP": "organisme_retraite_sup",
    "MUTUELLE": "organisme_mutuelle",
    "PREVOYANCE": "organisme_prevoyance",
}


def _rows_from_plan(company_id: str, plan: Dict[str, Any]) -> list[Dict[str, Any]]:
    journal = str(plan.get("journal") or "OD")
    rows: list[Dict[str, Any]] = []

    for organisme, comptes in (plan.get("organismes") or {}).items():
        rubrique = ORGANISME_RUBRIQUES.get(organisme)
        if not rubrique:
            print(f"  ! organisme inconnu ignoré : {organisme}", file=sys.stderr)
            continue
        rows.append(
            {
                "company_id": company_id,
                "rubrique_code": rubrique,
                "rubrique_libelle": comptes.get("libelle") or organisme,
                "compte_comptable": comptes.get("compte_charge") or comptes.get("compte_tiers"),
                "compte_charge": comptes.get("compte_charge") or None,
                "compte_tiers": comptes.get("compte_tiers") or None,
                "organisme": organisme,
                "sens": "debit",
                "type_rubrique": "charge_patronale",
                "journal": journal,
                "is_active": True,
            }
        )

    for element, comptes in (plan.get("elements") or {}).items():
        charge = comptes.get("compte_charge") or ""
        tiers = comptes.get("compte_tiers") or ""
        rows.append(
            {
                "company_id": company_id,
                "rubrique_code": element,
                "rubrique_libelle": element.replace("_", " ").capitalize(),
                "compte_comptable": charge or tiers,
                "compte_charge": charge or None,
                "compte_tiers": tiers or None,
                "organisme": None,
                "sens": "debit" if charge else "credit",
                "type_rubrique": "salaire" if charge else "dette_salarie",
                "journal": journal,
                "is_active": True,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company-id", required=True)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    plan = json.loads(args.file.read_text(encoding="utf-8"))
    rows = _rows_from_plan(args.company_id, plan)

    print(f"{plan.get('company_name', '?')} — {len(rows)} rubriques")
    for row in rows:
        print(
            f"  {row['rubrique_code']:<24} charge {row['compte_charge'] or '—':<10} "
            f"tiers {row['compte_tiers'] or '—':<10} journal {row['journal']}"
        )

    if not args.apply:
        print("\nSimulation — relancer avec --apply pour écrire.")
        return 0

    for row in rows:
        existing = (
            supabase.table("accounting_mappings")
            .select("id")
            .eq("company_id", args.company_id)
            .eq("rubrique_code", row["rubrique_code"])
            .maybe_single()
            .execute()
        )
        if existing and existing.data:
            supabase.table("accounting_mappings").update(row).eq(
                "id", existing.data["id"]
            ).execute()
        else:
            supabase.table("accounting_mappings").insert(row).execute()
    print(f"\n{len(rows)} rubriques écrites.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Étape 3 : Simuler sur l'environnement de test**

Vérifier d'abord vers quel projet pointe la configuration — `backend/.env` pointe sur la **production** par défaut :

```bash
cd backend && ./venv/bin/python -c "
from app.core import settings
print(settings.SUPABASE_URL)
"
```

Puis simuler :

```bash
cd backend && ./venv/bin/python -m scripts.import_plan_comptable \
  --company-id dbe2b9f5-44dd-41bc-a625-36ed33d160f7 \
  --file ../data/colorplast/comptabilite/plan_comptable.json
```

Attendu : 12 rubriques listées, aucune écriture.

- [ ] **Étape 4 : Appliquer sur le test puis comparer**

```bash
cd backend && ./venv/bin/python -m scripts.import_plan_comptable \
  --company-id dbe2b9f5-44dd-41bc-a625-36ed33d160f7 \
  --file ../data/colorplast/comptabilite/plan_comptable.json --apply

./venv/bin/python -c "
from app.modules.exports.infrastructure.payroll_ledger import build_payroll_ledger, ledger_to_od_export_rows
ec, tot, _ = build_payroll_ledger('dbe2b9f5-44dd-41bc-a625-36ed33d160f7', '2026-06', None, None, scope='full')
rows = ledger_to_od_export_rows(ec)
for r in sorted(rows, key=lambda x: x['compte_comptable']):
    print(f\"{r['compte_comptable']:<10} {r['libelle'][:40]:<42} D {r['debit']:>10.2f}  C {r['credit']:>10.2f}\")
print('ecart', tot['ecart'], '| anomalies', tot['anomalies'])
"
```

Attendu : les comptes sont ceux du cabinet (`64110000`, `42100000`, `43100000`…), écart nul.

- [ ] **Étape 5 : Commit**

```bash
git add backend/scripts/import_plan_comptable.py
git commit -m "feat(compta): paramétrage d'une société depuis son plan de comptes

Le fichier source reste dans data/, hors dépôt. Simulation par défaut,
écriture sur --apply."
```

---

## Tâche 13 : Transmission Cegid Loop

**Dépend d'Elsa.** Ne pas démarrer avant d'avoir reçu la clé API, la clé d'abonnement et le code dossier de chaque société. Le connecteur existe et suit la documentation officielle ; il n'a jamais été exercé contre le service réel.

**Fichiers :**
- Modifier : `backend/app/modules/accounting_integration/application/service.py`
- Test : `backend/tests/unit/accounting_integration/test_cegid_connector.py` (fichier existant)

- [ ] **Étape 1 : Créer la configuration d'une société**

Depuis l'écran d'administration EYWAI (`AccountingIntegrations`), renseigner pour Colorplast : fournisseur `cegid_quadra`, code dossier `000005`, clés d'authentification.

Vérifier :

```sql
select company_id, provider, mode, code_dossier_cegid, enabled, force_manual
  from company_accounting_config;
```

Attendu : 1 ligne.

- [ ] **Étape 2 : Tester la connexion sans rien envoyer**

Utiliser le bouton « Tester la connexion » de l'écran, puis :

```sql
select last_test_at, last_test_status, last_test_message
  from company_accounting_config
 where company_id = 'dbe2b9f5-44dd-41bc-a625-36ed33d160f7';
```

Attendu : `last_test_status = 'success'`. En cas d'échec, le message porte le code HTTP de Cegid — ne pas passer à l'étape suivante avant qu'il soit vert.

- [ ] **Étape 3 : Vérifier le garde-fou de l'environnement de test**

La transmission comptable doit être refusée hors production, comme le dépôt de DSN. Vérifier que le service applique cette règle, et l'ajouter si elle manque :

```bash
cd backend && grep -rn "IS_TEST_ENV\|force_manual\|ENVIRONMENT" app/modules/accounting_integration/application/service.py
```

Attendu : un garde-fou explicite. S'il est absent, l'ajouter avant tout envoi réel — une transmission depuis le test irait polluer la comptabilité du client.

- [ ] **Étape 4 : Première transmission réelle**

À faire sur un mois clos, en présence d'Elsa, et après accord explicite du cabinet. Vérifier ensuite :

```sql
select period, status, external_ref, submitted_at, error_message
  from accounting_transmissions
 order by created_at desc limit 1;
```

- [ ] **Étape 5 : Commit**

```bash
git add backend/app/modules/accounting_integration/
git commit -m "feat(compta): garde-fou de transmission et configuration Cegid par société"
```

---

## Vérification finale

- [ ] **Suite unitaire complète**

```bash
cd backend && ./venv/bin/pytest tests/unit/ -q
```

Attendu : aucun échec.

- [ ] **Build frontend**

```bash
cd frontend && npm run build
```

- [ ] **Équilibre sur les 7 sociétés**

```bash
cd backend && ./venv/bin/python -c "
from app.core.database import supabase
from app.modules.exports.infrastructure.payroll_ledger import build_payroll_ledger
companies = supabase.table('companies').select('id, company_name').execute().data
for c in sorted(companies, key=lambda x: x['company_name']):
    for period in ['2026-05', '2026-06']:
        try:
            ec, tot, _ = build_payroll_ledger(c['id'], period, None, None, scope='full')
            flag = 'OK ' if tot['ecart'] <= 0.01 else 'ECART'
            print(f\"{flag} {c['company_name']:<24} {period}  lignes {len(ec):>3}  ecart {tot['ecart']:>10.2f}  anomalies {len(tot['anomalies'])}\")
        except Exception as e:
            print(f\"ERR {c['company_name']:<24} {period}  {e}\")
"
```

Attendu : `OK` partout, écart nul. Les sociétés dont le plan comptable n'est pas encore paramétré remonteront des anomalies `organisme_non_rattache` — c'est attendu tant qu'Elsa n'a pas fourni leur OD, et cela ne doit pas être masqué.

---

## Couverture de la conception

| Section de la conception | Tâches |
|---|---|
| A — Plan comptable par société | 1, 2, 9, 10, 12 |
| B — Moteur d'OD équilibré | 3, 4, 5, 6, 7, 8 |
| C — Formats de sortie | 7, 11 |
| D — Transmission | 13 |
| E — Validation | 12, vérification finale |
