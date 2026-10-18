# Théorème de la correction à la main — étape 1 : plan d'exécution

> **Pour les agents :** sous-compétence requise : superpowers:subagent-driven-development (recommandée) ou superpowers:executing-plans, tâche par tâche. Les étapes se cochent (`- [ ]`).

**But :** rendre vrai le théorème « toute ligne d'un bulletin se corrige toujours à la main, et la correction passe partout ». Pour cela, on ajoute la régularisation de cotisation : une ligne saisie depuis l'onglet « Corriger », rejouée par le moteur, qui passe dans le net, les cumuls, la DSN, la comptabilité et le PDF.

**Architecture :**
- **Stockage.** Une régularisation est une saisie du mois (`monthly_inputs`) dont la nouvelle colonne `correction_ligne` porte la charge utile.
- **Calcul.** Les deux générateurs la rangent à part des primes. Les deux pipelines (`payslip_run_heures`, `payslip_run_forfait`) la posent dans le bloc des cotisations, après la réduction générale et avant le net, par une seule fonction du module `engine/corrections_manuelles.py`.
- **Ce qui suit de soi.** Le total salarial, le net, l'impôt, les cumuls (réduction générale comprise), la DSN, la comptabilité et le PDF suivent, parce qu'ils lisent les lignes du bulletin.
- **Gains et retenues.** Ils existent déjà (« primes ajoutées », montant signé, soumis ou non) : rien à créer.

**Technologies :** Python 3.11 (FastAPI, Pydantic, client Supabase), pytest ; React + TypeScript, Vitest ; Postgres (migration Supabase).

**Spécification :** `docs/superpowers/specs/2026-10-18-theoreme-correction-a-la-main-design.md`.

## Contraintes globales

- Un bulletin sans régularisation reste identique au centime (filet avant/après sur Colorplast, Comitech Composite, MAJI, Zone 404 Mars).
- Les totaux ne se tapent jamais. Une régularisation de cotisation porte une base et le taux de la ligne qu'elle régularise, ou un montant seulement pour une cotisation sans taux (forfait, réduction générale). Le serveur calcule les montants : `round(base × taux, 2)`.
- Le motif est obligatoire : au moins 3 caractères, au plus 300.
- Le libellé imprimé est `Régularisation – <libellé de la ligne d'origine>`, et la ligne garde le `coti_id` de l'organisme.
- Rien n'est écrit en base par les tests. Le test du théorème tourne au bac à sable, sous le piège à écritures (`backend/scripts/verification_rgdu/piege.py`).
- Rien n'est déployé ni migré sur le site de test sans l'accord explicite d'Alexandre. Ne jamais pousser sur `main`.
- Aucun nom de salarié dans le code, les tests, les commits ni les messages (dépôt public).
- Interpréteur : `backend/.venv/bin/python`, lancé depuis `backend/`. Deux tests unitaires sont rouges à cause de l'environnement local (`APP_ENV=test`), pas du code : ne pas les « corriger ».

## Fichiers

| Fichier | Rôle |
|---|---|
| `supabase/migrations/20261018120000_monthly_inputs_correction_ligne.sql` (créé) | colonne `correction_ligne jsonb` |
| `backend/app/modules/payroll/domain/empreinte_entrees.py` | `saisie_pour_empreinte` : une colonne vide ne change pas l'empreinte |
| `backend/app/modules/payroll/infrastructure/empreinte_entrees_queries.py` | lit `correction_ligne`, passe par `saisie_pour_empreinte` |
| `backend/app/modules/monthly_inputs/application/queries.py` | l'écran « Saisies du mois » ne liste pas les régularisations |
| `backend/app/modules/payroll/engine/corrections_manuelles.py` (créé) | le domaine : régularisation, saisie, ligne, rangement, pose, lecture sur un bulletin, mentions |
| `backend/app/modules/payroll/documents/payslip_generator.py`, `payslip_generator_forfait.py` | rangent la saisie à part des primes |
| `backend/app/modules/payroll/documents/payslip_run_heures.py`, `payslip_run_forfait.py` | posent les régularisations avant le net, passent la réduction générale aux cumuls |
| `backend/app/modules/payroll/documents/payslip_run_common.py` | cumul de la réduction générale |
| `backend/app/modules/payroll/engine/calcul_net.py` | part patronale de mutuelle régularisée réintégrée |
| `backend/app/modules/payslips/schemas/requests.py`, `domain/corrections.py`, `application/corrections.py` | la route de correction : ajout, retrait, restauration, résumé |
| `backend/app/modules/dsn_export/domain/cotisation_mapping.py` | la fusion n'additionne pas le taux d'une régularisation |
| `backend/app/modules/payroll/documents/bulletin_view.py` | mention sur le PDF |
| `backend/app/modules/payslips/infrastructure/payslip_list_meta.py` | `regularisations` dans les listes |
| `frontend/src/api/payslips.ts`, `features/payroll/utils/correctionsBulletin.ts`, `components/payslip-edit/RegularisationsCotisationCard.tsx` (créé), `components/payslip-edit/CorrectionsBulletinPanel.tsx` | l'écran |
| `frontend/src/features/payroll/utils/bulletinARecalculer.ts`, `listeControleMois.ts` | liste de contrôle et capteur |
| `backend/scripts/theoreme_correction_a_la_main.py` (créé) | le test du théorème, au bac à sable |

---

### Tâche 0 : branche et filet « avant »

**Fichiers :** aucun dans le dépôt.

- [ ] **Étape 1 : créer la branche depuis la branche courante**

```bash
cd /Users/alex/dev/EYWAI && git switch -c feat/theoreme-correction-etape-1
```

- [ ] **Étape 2 : relever le filet « avant », au bac à sable et sous le piège à écritures (environ 20 min, en arrière-plan)**

```bash
caffeinate -i /Users/alex/dev/eywai-filet/lancer.sh /Users/alex/dev/eywai-filet/theoreme-avant HEAD
```

Attendu : le fichier `theoreme-avant/fini.txt` existe, et les 4 fichiers `apres_*.json` sont non vides.

---

### Tâche 1 : la colonne `correction_ligne`, sans réveiller les bulletins

**Fichiers :**
- Créer : `supabase/migrations/20261018120000_monthly_inputs_correction_ligne.sql`
- Modifier : `backend/app/modules/payroll/domain/empreinte_entrees.py`, `backend/app/modules/payroll/infrastructure/empreinte_entrees_queries.py:32-36` et `:391`, `backend/app/modules/monthly_inputs/application/queries.py`
- Tester : `backend/tests/unit/payroll/test_empreinte_entrees.py`, `backend/tests/unit/monthly_inputs/test_saisies_sans_corrections.py` (créé)

**Interfaces :**
- Produit : `saisie_pour_empreinte(row: Mapping[str, Any]) -> dict[str, Any]` dans `app.modules.payroll.domain.empreinte_entrees`.

- [ ] **Étape 1 : écrire la migration**

```sql
-- Théorème de la correction à la main, étape 1 (spec 2026-10-18) : une saisie
-- du mois peut porter une correction faite depuis le bulletin. Aujourd'hui, une
-- régularisation de cotisation. NULL pour toute saisie ordinaire.
ALTER TABLE public.monthly_inputs
  ADD COLUMN IF NOT EXISTS correction_ligne jsonb;

COMMENT ON COLUMN public.monthly_inputs.correction_ligne IS
  'Correction saisie à la main depuis le bulletin (type, organisme, base et taux ou montant, motif). NULL pour une saisie ordinaire.';
```

- [ ] **Étape 2 : écrire les tests qui échouent**

Dans `backend/tests/unit/payroll/test_empreinte_entrees.py`, ajouter :

```python
from app.modules.payroll.domain.empreinte_entrees import (
    construire_entrees,
    empreinte,
    saisie_pour_empreinte,
)


def test_une_colonne_correction_vide_ne_change_pas_l_empreinte():
    """Ajouter `correction_ligne` aux colonnes lues ne doit périmer aucun bulletin."""
    ancienne = {"year": 2026, "month": 9, "name": "Prime", "amount": 100}
    nouvelle = {**ancienne, "correction_ligne": None}
    assert empreinte(construire_entrees({"saisies": [ancienne]})) == empreinte(
        construire_entrees({"saisies": [saisie_pour_empreinte(nouvelle)]})
    )


def test_une_regularisation_change_l_empreinte():
    ordinaire = {"year": 2026, "month": 9, "name": "Régularisation – X", "amount": 0}
    regularisee = {**ordinaire, "correction_ligne": {"type": "regularisation_cotisation", "base": 10}}
    assert empreinte(construire_entrees({"saisies": [saisie_pour_empreinte(ordinaire)]})) != empreinte(
        construire_entrees({"saisies": [saisie_pour_empreinte(regularisee)]})
    )
```

Créer `backend/tests/unit/monthly_inputs/test_saisies_sans_corrections.py` :

```python
"""L'écran « Saisies du mois » ne montre pas les régularisations : elles se gèrent depuis le bulletin."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.monthly_inputs.application import queries

pytestmark = pytest.mark.unit

ORDINAIRE = {"id": "s1", "name": "Prime", "amount": 50, "correction_ligne": None}
REGUL = {"id": "s2", "name": "Régularisation – Mutuelle", "amount": 0,
         "correction_ligne": {"type": "regularisation_cotisation"}}


def test_la_liste_d_un_salarie_ecarte_les_regularisations():
    with patch.object(queries.monthly_inputs_repository, "list_by_employee_period", return_value=[ORDINAIRE, REGUL]):
        resultat = queries.list_monthly_inputs_by_employee_period("e", 2026, 10, "c")
    assert [s["id"] for s in resultat.items] == ["s1"]


def test_la_liste_de_la_societe_ecarte_les_regularisations():
    with patch.object(queries.monthly_inputs_repository, "list_by_period", return_value=[ORDINAIRE, REGUL]):
        resultat = queries.list_monthly_inputs_by_period(2026, 10, "c")
    assert [s["id"] for s in resultat.items] == ["s1"]
```

- [ ] **Étape 3 : lancer les tests, ils échouent**

Commande : `cd backend && .venv/bin/python -m pytest tests/unit/payroll/test_empreinte_entrees.py tests/unit/monthly_inputs/test_saisies_sans_corrections.py -q`
Attendu : échec, `ImportError: cannot import name 'saisie_pour_empreinte'`, et la régularisation encore présente dans les listes.

- [ ] **Étape 4 : implémenter**

Dans `backend/app/modules/payroll/domain/empreinte_entrees.py`, sous `_liste_stable` :

```python
def saisie_pour_empreinte(row: Mapping[str, Any]) -> dict[str, Any]:
    """Une saisie telle que l'empreinte la lit : une correction vide n'y figure pas.

    `correction_ligne` est NULL sur toutes les saisies d'avant le 18/10/2026. La
    garder vide changerait l'empreinte de tous les bulletins, qui passeraient
    « À recalculer » sans que rien n'ait changé.
    """
    propre = dict(row)
    if propre.get("correction_ligne") is None:
        propre.pop("correction_ligne", None)
    return propre
```

Dans `backend/app/modules/payroll/infrastructure/empreinte_entrees_queries.py`, ajouter `correction_ligne` à la fin de `SAISIE_COLONNES` :

```python
SAISIE_COLONNES = (
    "year, month, name, amount, catalog_prime_id, is_socially_taxed, is_taxable, "
    "payroll_quantity, sur_le_net, export_code, quantity_kind, situation_repas, "
    "description, participation_campaign_id, participation_bulletin_id, correction_ligne"
)
```

Puis, ligne 391, remplacer `saisies_par_mois.setdefault(cle, []).append(row)` par :

```python
        saisies_par_mois.setdefault(cle, []).append(saisie_pour_empreinte(row))
```

Ajouter l'import `saisie_pour_empreinte` depuis `app.modules.payroll.domain.empreinte_entrees` en tête du fichier.

Dans `backend/app/modules/monthly_inputs/application/queries.py` :

```python
def _sans_corrections(items: list) -> list:
    """Les régularisations saisies depuis le bulletin se gèrent depuis le bulletin."""
    return [i for i in items if not (isinstance(i, dict) and i.get("correction_ligne"))]
```

Appliquer `_sans_corrections(...)` au résultat du dépôt dans `list_monthly_inputs_by_period` et `list_monthly_inputs_by_employee_period` :

```python
    items = _sans_corrections(monthly_inputs_repository.list_by_period(year, month, company_id))
```

```python
    items = _sans_corrections(
        monthly_inputs_repository.list_by_employee_period(employee_id, year, month, company_id)
    )
```

- [ ] **Étape 5 : lancer les tests, ils passent**

Commande : la même qu'à l'étape 3. Attendu : tout passe.

- [ ] **Étape 6 : commiter**

```bash
git add supabase/migrations/20261018120000_monthly_inputs_correction_ligne.sql backend/app/modules/payroll/domain/empreinte_entrees.py backend/app/modules/payroll/infrastructure/empreinte_entrees_queries.py backend/app/modules/monthly_inputs/application/queries.py backend/tests/unit/payroll/test_empreinte_entrees.py backend/tests/unit/monthly_inputs/test_saisies_sans_corrections.py
git commit -m "feat(paie): une saisie du mois peut porter une correction faite depuis le bulletin (colonne correction_ligne) ; une colonne vide ne change pas l'empreinte des bulletins, et l'écran « Saisies du mois » ne liste pas les régularisations"
```

---

### Tâche 2 : le domaine de la régularisation

**Fichiers :**
- Créer : `backend/app/modules/payroll/engine/corrections_manuelles.py`
- Tester : `backend/tests/unit/payroll/test_corrections_manuelles.py` (créé)

**Interfaces :**
- Produit, dans `app.modules.payroll.engine.corrections_manuelles` :
  - `TYPE_REGULARISATION_COTISATION = "regularisation_cotisation"`, `CLE_REGULARISATIONS_COTISATION = "regularisations_cotisation"`, `PREFIXE_LIBELLE = "Régularisation – "`, `COTI_ID_REDUCTION_GENERALE = "reduction_generale"` ;
  - `class RegularisationInvalide(ValueError)` ;
  - `@dataclass(frozen=True) class RegularisationCotisation`, avec les champs `coti_id, libelle, motif, base, taux_salarial, taux_patronal, montant_salarial, montant_patronal, saisie_id` et les méthodes `montants() -> tuple[float, float]`, `charge_utile() -> dict`, `depuis(donnees, saisie_id=None)` (classmethod), `saisie_du_mois(periode) -> dict`, `ligne_de_cotisation() -> dict` ;
  - `est_regularisation_cotisation(saisie) -> bool` ;
  - `ranger_regularisation(saisie, saisies_data) -> bool` ;
  - `lignes_de_regularisation(entrees) -> list[dict]` ;
  - `@dataclass(frozen=True) class EffetDesRegularisations(total_salarial: float, reduction_generale: float)` ;
  - `ajouter_regularisations(lignes_cotisations, total_salarial, saisie_du_mois) -> EffetDesRegularisations` ;
  - `regularisations_du_bulletin(payslip_data) -> dict[str, RegularisationCotisation]` ;
  - `mentions_des_regularisations(payslip_data) -> list[str]`.

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
"""La régularisation de cotisation (spec 2026-10-18, étape 1).

Une ligne saisie à la main depuis le bulletin, rattachée à l'organisme de la
ligne qu'elle régularise, calculée comme le moteur (base × taux, au centime),
rejouée à chaque calcul.
"""
from __future__ import annotations

import pytest

from app.modules.payroll.engine.corrections_manuelles import (
    CLE_REGULARISATIONS_COTISATION,
    RegularisationCotisation,
    RegularisationInvalide,
    ajouter_regularisations,
    est_regularisation_cotisation,
    mentions_des_regularisations,
    ranger_regularisation,
    regularisations_du_bulletin,
)

pytestmark = pytest.mark.unit

PERIODE = {"employee_id": "e", "company_id": "c", "year": 2026, "month": 10}


def _par_base(**k):
    donnees = dict(coti_id="securite_sociale_maladie", libelle="Sécurité sociale - Maladie",
                   motif="Base de septembre oubliée", base=100.0, taux_patronal=0.07)
    donnees.update(k)
    return RegularisationCotisation(**donnees)


def test_les_montants_suivent_la_base_et_le_taux_au_centime():
    r = _par_base(base=33.33, taux_salarial=0.069, taux_patronal=0.0855)
    assert r.montants() == (2.30, 2.85)


def test_une_cotisation_au_forfait_se_regularise_par_son_montant():
    r = RegularisationCotisation(coti_id="mutuelle", libelle="Mutuelle", motif="Tarif 2026",
                                 montant_salarial=-4.1, montant_patronal=8.3)
    assert r.montants() == (-4.10, 8.30)


@pytest.mark.parametrize("champs", [
    {"motif": "  "},
    {"coti_id": ""},
    {"base": None},
    {"montant_patronal": 3.0},
    {"taux_patronal": None, "taux_salarial": None},
])
def test_une_regularisation_incomplete_ou_ambigue_est_refusee(champs):
    with pytest.raises(RegularisationInvalide):
        _par_base(**champs)


def test_la_ligne_garde_l_organisme_et_reprend_le_libelle():
    ligne = _par_base(saisie_id="s1").ligne_de_cotisation()
    assert ligne["coti_id"] == "securite_sociale_maladie"
    assert ligne["libelle"] == "Régularisation – Sécurité sociale - Maladie"
    assert ligne["montant_patronal"] == 7.0 and ligne["montant_salarial"] == 0.0
    assert ligne["explication"] == "Régularisation saisie à la main : Base de septembre oubliée"
    assert ligne["regularisation"]["saisie_id"] == "s1"
    assert ligne["rubrique"]


def test_la_saisie_du_mois_porte_la_charge_et_aucun_montant():
    saisie = _par_base().saisie_du_mois(PERIODE)
    assert saisie["amount"] == 0
    assert saisie["name"] == "Régularisation – Sécurité sociale - Maladie"
    assert saisie["correction_ligne"]["type"] == "regularisation_cotisation"
    assert saisie["correction_ligne"]["base"] == 100.0
    assert est_regularisation_cotisation(saisie)
    assert not est_regularisation_cotisation({"name": "Prime", "correction_ligne": None})


def test_le_generateur_range_la_regularisation_a_part_des_primes():
    saisies_data = {"primes": []}
    saisie = {**_par_base().saisie_du_mois(PERIODE), "id": "s1"}
    assert ranger_regularisation(saisie, saisies_data) is True
    assert saisies_data["primes"] == []
    assert saisies_data[CLE_REGULARISATIONS_COTISATION][0]["saisie_id"] == "s1"
    assert ranger_regularisation({"name": "Prime", "amount": 10}, saisies_data) is False


def test_poser_les_regularisations_ajoute_les_lignes_et_le_salarial():
    lignes = [{"coti_id": "x", "montant_salarial": 10.0, "montant_patronal": 0.0}]
    saisie_du_mois = {CLE_REGULARISATIONS_COTISATION: [
        {**_par_base(taux_salarial=0.1).charge_utile(), "saisie_id": "s1"},
        {**RegularisationCotisation(coti_id="reduction_generale", libelle="Réduction générale de cotisations patronales",
                                    motif="Écart de juillet", montant_patronal=-12.5).charge_utile(), "saisie_id": "s2"},
    ]}
    effet = ajouter_regularisations(lignes, 10.0, saisie_du_mois)
    assert len(lignes) == 3
    assert effet.total_salarial == 20.0
    assert effet.reduction_generale == -12.5


def test_sans_regularisation_rien_ne_bouge():
    lignes = [{"coti_id": "x", "montant_salarial": 10.0}]
    effet = ajouter_regularisations(lignes, 10.0, {})
    assert lignes == [{"coti_id": "x", "montant_salarial": 10.0}]
    assert effet.total_salarial == 10.0 and effet.reduction_generale == 0.0


def test_un_bulletin_dit_ses_regularisations_et_ses_mentions():
    ligne = _par_base(saisie_id="s1").ligne_de_cotisation()
    payslip_data = {"cotisations_officielles": [{"code": "sante", "lignes": [{"coti_id": "y"}, ligne]}]}
    trouvees = regularisations_du_bulletin(payslip_data)
    assert list(trouvees) == ["s1"]
    assert trouvees["s1"].base == 100.0
    assert mentions_des_regularisations(payslip_data) == [
        "Régularisation saisie à la main — Sécurité sociale - Maladie : Base de septembre oubliée"
    ]
```

- [ ] **Étape 2 : lancer les tests, ils échouent**

Commande : `cd backend && .venv/bin/python -m pytest tests/unit/payroll/test_corrections_manuelles.py -q`
Attendu : `ModuleNotFoundError: app.modules.payroll.engine.corrections_manuelles`.

- [ ] **Étape 3 : écrire le module**

```python
"""Les corrections faites à la main sur un bulletin (spec 2026-10-18,
« théorème de la correction à la main »).

Étape 1 : la régularisation de cotisation. Elle ne retouche pas une ligne
calculée. Elle s'ajoute au bloc des cotisations, rattachée à l'organisme de la
ligne qu'elle régularise (son `coti_id`), avec sa base et son taux, au centime
comme le moteur (`_calculer_une_ligne`). Une cotisation sans taux (forfait,
réduction générale) se régularise par son montant. Elle vit comme une saisie du
mois (`monthly_inputs.correction_ligne`) : le moteur la rejoue à chaque calcul,
et elle passe dans le net, les cumuls, la DSN et les exports comme toute ligne.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from app.modules.payroll.engine.cotisations_rubriques import enrichir_ligne_cotisation

TYPE_REGULARISATION_COTISATION = "regularisation_cotisation"
CLE_REGULARISATIONS_COTISATION = "regularisations_cotisation"
PREFIXE_LIBELLE = "Régularisation – "
COTI_ID_REDUCTION_GENERALE = "reduction_generale"


class RegularisationInvalide(ValueError):
    """Une régularisation qu'on ne peut pas appliquer telle quelle."""


def _nombre(valeur: Any) -> float | None:
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class RegularisationCotisation:
    coti_id: str
    libelle: str
    motif: str
    base: float | None = None
    taux_salarial: float | None = None
    taux_patronal: float | None = None
    montant_salarial: float | None = None
    montant_patronal: float | None = None
    saisie_id: str | None = None

    def __post_init__(self) -> None:
        if not self.coti_id.strip():
            raise RegularisationInvalide("Choisissez la cotisation à régulariser.")
        if not self.libelle.strip():
            raise RegularisationInvalide("La cotisation à régulariser n'a pas de libellé.")
        if len(self.motif.strip()) < 3:
            raise RegularisationInvalide("Écrivez le motif de la régularisation.")
        par_taux = self.base is not None
        au_montant = self.montant_salarial is not None or self.montant_patronal is not None
        if par_taux == au_montant:
            raise RegularisationInvalide(
                "Une régularisation porte soit une base avec le taux de la cotisation, "
                "soit un montant pour une cotisation sans taux, jamais les deux."
            )
        if par_taux and not (self.taux_salarial or self.taux_patronal):
            raise RegularisationInvalide(
                "Une régularisation par la base porte le taux de la cotisation."
            )

    @property
    def par_taux(self) -> bool:
        return self.base is not None

    def montants(self) -> tuple[float, float]:
        """(salarial, patronal), arrondis au centime comme `_calculer_une_ligne`."""
        if self.par_taux:
            base = float(self.base or 0.0)
            return (
                round(base * float(self.taux_salarial or 0.0), 2),
                round(base * float(self.taux_patronal or 0.0), 2),
            )
        return (
            round(float(self.montant_salarial or 0.0), 2),
            round(float(self.montant_patronal or 0.0), 2),
        )

    def charge_utile(self) -> dict[str, Any]:
        """Ce qui s'enregistre dans `monthly_inputs.correction_ligne`."""
        return {
            "type": TYPE_REGULARISATION_COTISATION,
            "coti_id": self.coti_id,
            "libelle": self.libelle,
            "motif": self.motif.strip(),
            "base": self.base,
            "taux_salarial": self.taux_salarial,
            "taux_patronal": self.taux_patronal,
            "montant_salarial": self.montant_salarial,
            "montant_patronal": self.montant_patronal,
        }

    @classmethod
    def depuis(
        cls, donnees: Mapping[str, Any], saisie_id: str | None = None
    ) -> "RegularisationCotisation":
        identifiant = saisie_id or donnees.get("saisie_id")
        return cls(
            coti_id=str(donnees.get("coti_id") or ""),
            libelle=str(donnees.get("libelle") or ""),
            motif=str(donnees.get("motif") or ""),
            base=_nombre(donnees.get("base")),
            taux_salarial=_nombre(donnees.get("taux_salarial")),
            taux_patronal=_nombre(donnees.get("taux_patronal")),
            montant_salarial=_nombre(donnees.get("montant_salarial")),
            montant_patronal=_nombre(donnees.get("montant_patronal")),
            saisie_id=str(identifiant) if identifiant else None,
        )

    def saisie_du_mois(self, periode: Mapping[str, Any]) -> dict[str, Any]:
        """La ligne `monthly_inputs` qui porte la régularisation : aucun montant
        de prime (elle n'en est pas une), la charge dans `correction_ligne`."""
        return {
            **periode,
            "name": f"{PREFIXE_LIBELLE}{self.libelle}"[:120],
            "description": self.motif.strip(),
            "amount": 0,
            "is_socially_taxed": False,
            "is_taxable": False,
            "correction_ligne": self.charge_utile(),
        }

    def ligne_de_cotisation(self) -> dict[str, Any]:
        salarial, patronal = self.montants()
        ligne = {
            "libelle": f"{PREFIXE_LIBELLE}{self.libelle}",
            "base": self.base,
            "taux_salarial": self.taux_salarial if self.par_taux else None,
            "montant_salarial": salarial,
            "taux_patronal": self.taux_patronal if self.par_taux else None,
            "montant_patronal": patronal,
            "explication": f"Régularisation saisie à la main : {self.motif.strip()}",
            "regularisation": {**self.charge_utile(), "saisie_id": self.saisie_id},
        }
        return enrichir_ligne_cotisation(ligne, coti_id=self.coti_id)


def est_regularisation_cotisation(saisie: Mapping[str, Any]) -> bool:
    correction = saisie.get("correction_ligne")
    return (
        isinstance(correction, Mapping)
        and correction.get("type") == TYPE_REGULARISATION_COTISATION
    )


def ranger_regularisation(saisie: Mapping[str, Any], saisies_data: dict[str, Any]) -> bool:
    """Dans la boucle des saisies d'un générateur : range une régularisation à
    part (ce n'est pas une prime). Dit si la saisie en était une."""
    if not est_regularisation_cotisation(saisie):
        return False
    entree = dict(saisie["correction_ligne"])
    if saisie.get("id"):
        entree["saisie_id"] = str(saisie["id"])
    saisies_data.setdefault(CLE_REGULARISATIONS_COTISATION, []).append(entree)
    return True


def lignes_de_regularisation(entrees: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    return [RegularisationCotisation.depuis(e).ligne_de_cotisation() for e in entrees or []]


@dataclass(frozen=True)
class EffetDesRegularisations:
    total_salarial: float
    #: Montant patronal (signé) des régularisations de la réduction générale :
    #: il entre dans le cumul de la réduction appliquée.
    reduction_generale: float


def ajouter_regularisations(
    lignes_cotisations: list[dict[str, Any]],
    total_salarial: float,
    saisie_du_mois: Mapping[str, Any],
) -> EffetDesRegularisations:
    """Pose les régularisations du mois dans le bloc des cotisations (en place).

    Appelée dans les deux pipelines au même endroit : après la réduction
    générale (qui ne doit pas les lire), avant le net (qui lit le total
    salarial, pas les lignes).
    """
    lignes = lignes_de_regularisation(saisie_du_mois.get(CLE_REGULARISATIONS_COTISATION))
    lignes_cotisations.extend(lignes)
    return EffetDesRegularisations(
        total_salarial=round(
            float(total_salarial or 0.0) + sum(l["montant_salarial"] for l in lignes), 2
        ),
        reduction_generale=round(
            sum(
                l["montant_patronal"]
                for l in lignes
                if l.get("coti_id") == COTI_ID_REDUCTION_GENERALE
            ),
            2,
        ),
    )


def regularisations_du_bulletin(
    payslip_data: Mapping[str, Any] | None,
) -> dict[str, RegularisationCotisation]:
    """Les régularisations imprimées sur un bulletin, par identifiant de saisie."""
    trouvees: dict[str, RegularisationCotisation] = {}
    for rubrique in (payslip_data or {}).get("cotisations_officielles") or []:
        if not isinstance(rubrique, Mapping):
            continue
        for ligne in rubrique.get("lignes") or []:
            regul = ligne.get("regularisation") if isinstance(ligne, Mapping) else None
            if isinstance(regul, Mapping) and regul.get("saisie_id"):
                trouvees[str(regul["saisie_id"])] = RegularisationCotisation.depuis(regul)
    return trouvees


def mentions_des_regularisations(payslip_data: Mapping[str, Any] | None) -> list[str]:
    return [
        f"Régularisation saisie à la main — {r.libelle} : {r.motif}"
        for r in regularisations_du_bulletin(payslip_data).values()
    ]
```

- [ ] **Étape 4 : lancer les tests, ils passent**

Commande : la même qu'à l'étape 2. Attendu : tout passe.

- [ ] **Étape 5 : commiter**

```bash
git add backend/app/modules/payroll/engine/corrections_manuelles.py backend/tests/unit/payroll/test_corrections_manuelles.py
git commit -m "feat(paie): la régularisation de cotisation, saisie à la main depuis le bulletin : rattachée à l'organisme de la ligne régularisée, calculée par sa base et son taux au centime (ou son montant pour une cotisation sans taux), motif obligatoire, libellé « Régularisation – » ; rangée à part des primes, posée dans le bloc des cotisations, relue sur un bulletin"
```

---

### Tâche 3 : le moteur pose les régularisations, et le cumul de la réduction générale suit

**Fichiers :**
- Modifier : `backend/app/modules/payroll/documents/payslip_generator.py:917-921`, `payslip_generator_forfait.py:288-291`, `payslip_run_heures.py:1316-1333` et l'appel de `mettre_a_jour_cumuls`, `payslip_run_forfait.py` (mêmes points), `payslip_run_common.py:43-56` et `:198-203`
- Tester : `backend/tests/unit/payroll/test_regularisations_dans_les_pipelines.py` (créé), `backend/tests/unit/payroll/test_cumul_reduction_regularisee.py` (créé), `backend/tests/migration/test_regularisation_heures.py` (créé)

**Interfaces :**
- Consomme : `ranger_regularisation`, `ajouter_regularisations`, `EffetDesRegularisations`, `RegularisationInvalide` (tâche 2).
- Produit : `mettre_a_jour_cumuls(..., regularisation_reduction_generale: float = 0.0)`.

- [ ] **Étape 1 : écrire les tests qui échouent**

`backend/tests/unit/payroll/test_regularisations_dans_les_pipelines.py`, le test de contrat :

```python
"""Les deux générateurs et les deux pipelines traitent la régularisation au même endroit."""
from __future__ import annotations

import inspect

import pytest

from app.modules.payroll.documents import (
    payslip_generator,
    payslip_generator_forfait,
    payslip_run_forfait,
    payslip_run_heures,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("module", [payslip_generator, payslip_generator_forfait])
def test_chaque_generateur_range_la_regularisation_avant_les_primes(module):
    source = inspect.getsource(module)
    assert "ranger_regularisation(row, saisies_data)" in source
    assert source.index("ranger_regularisation(row, saisies_data)") < source.index("est_saisie_ijss_validees(row)")


@pytest.mark.parametrize("module", [payslip_run_heures, payslip_run_forfait])
def test_chaque_pipeline_pose_les_regularisations_entre_la_reduction_et_le_net(module):
    source = inspect.getsource(module)
    pose = source.index("ajouter_regularisations(")
    assert source.index("calculer_reduction_generale(") < pose < source.index("resultats_nets = calculer_net_et_impot(")
    assert "regularisation_reduction_generale=effet_regul.reduction_generale" in source
```

`backend/tests/unit/payroll/test_cumul_reduction_regularisee.py` :

```python
"""Le cumul de la réduction générale enregistre ce qui a été réellement appliqué."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.modules.payroll.documents.payslip_run_common import mettre_a_jour_cumuls
from app.modules.payroll.engine.corrections_manuelles import RegularisationInvalide

pytestmark = pytest.mark.unit


def _contexte(cumul_rg: float) -> SimpleNamespace:
    return SimpleNamespace(
        cumuls={"cumuls": {"reduction_generale_patronale": cumul_rg, "brut_total": 1000.0}, "periode": {}},
        company_id=None,
        year=2026,
    )


def _cumuls(tmp_path, contexte, ligne_rg, regul, mois=10):
    mettre_a_jour_cumuls(contexte, 2000.0, 0.0, {"net_imposable": 1500.0}, ligne_rg, mois, 0.0, 0.0,
                         tmp_path, regularisation_reduction_generale=regul)
    return json.loads((tmp_path / "cumuls" / f"{mois:02d}.json").read_text(encoding="utf-8"))["cumuls"]


def test_la_regularisation_entre_dans_le_cumul_de_la_reduction(tmp_path):
    cumuls = _cumuls(tmp_path, _contexte(-900.0), {"valeur_cumulative_a_enregistrer": 1000.0}, -12.5)
    assert cumuls["reduction_generale_patronale"] == -1012.5


def test_sans_ligne_de_reduction_ce_mois_le_cumul_precedent_est_regularise(tmp_path):
    cumuls = _cumuls(tmp_path, _contexte(-900.0), None, 20.0)
    assert cumuls["reduction_generale_patronale"] == -880.0


def test_sans_regularisation_le_cumul_est_celui_d_avant(tmp_path):
    cumuls = _cumuls(tmp_path, _contexte(-900.0), {"valeur_cumulative_a_enregistrer": 1000.0}, 0.0)
    assert cumuls["reduction_generale_patronale"] == -1000.0


def test_une_reduction_annuelle_negative_est_refusee(tmp_path):
    with pytest.raises(RegularisationInvalide):
        _cumuls(tmp_path, _contexte(-10.0), None, 25.0)
```

`mettre_a_jour_cumuls` écrit son fichier dans `chemin_employe / "cumuls" / f"{mois:02d}.json"` (`payslip_run_common.py:59`). Si la fonction lit d'autres attributs du contexte que `cumuls` et `company_id`, les ajouter au `SimpleNamespace` de `_contexte` avec une valeur neutre (`None` ou `{}`).

`backend/tests/migration/test_regularisation_heures.py`, de bout en bout dans le pipeline (même harnais et mêmes doublures que `tests/migration/test_bac_a_sable_heures.py`) :

```python
"""Une régularisation posée dans les saisies du mois traverse tout le pipeline heures."""
from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest

from tests.migration.fixtures import build_employee_fixture_dir

EMPLOYEE_APP = "TEST_MIG_REGUL"
YEAR, MONTH = 2026, 4
EMPLOYEE_ID = "11111111-1111-4111-8111-111111111111"
COMPANY_ID = "22222222-2222-4222-8222-222222222222"
_HOOK_CET = "app.modules.cet.application.payroll_hook"
_HOOK_MOD = "app.modules.modulation.application.payroll_hook"


def _needs_supabase():
    return not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"))


def _generer(regularisations: list[dict] | None):
    from app.core.paths import payroll_engine_employee_folder, payroll_engine_root
    from app.modules.modulation.application.payroll_hook import ModulationPayrollResult
    from app.modules.payroll.documents.payslip_run_heures import run_payslip_generation_heures
    from app.modules.payroll.engine.corrections_manuelles import CLE_REGULARISATIONS_COTISATION

    racine = payroll_engine_root()
    build_employee_fixture_dir(racine, EMPLOYEE_APP, YEAR, MONTH, mode="heures")
    dossier = payroll_engine_employee_folder(EMPLOYEE_APP)
    if regularisations:
        chemin = dossier / "saisies" / f"{MONTH:02d}.json"
        saisie = json.loads(chemin.read_text(encoding="utf-8"))
        saisie[CLE_REGULARISATIONS_COTISATION] = regularisations
        chemin.write_text(json.dumps(saisie), encoding="utf-8")

    def _inchange(*args, **kwargs):
        calendrier = args[3] if len(args) > 3 else kwargs["calendrier_etendu"]
        return calendrier, []

    def _modulation(*args, **kwargs):
        calendrier = args[4] if len(args) > 4 else kwargs["calendrier_etendu"]
        return calendrier, [], ModulationPayrollResult()

    with patch(f"{_HOOK_MOD}.apply_modulation_hour_account_to_calendar", side_effect=_modulation), \
         patch(f"{_HOOK_CET}.apply_cet_deposits_to_calendar", side_effect=_inchange), \
         patch(f"{_HOOK_CET}.apply_cet_withdrawals_to_calendar", side_effect=_inchange), \
         patch("app.modules.cet.infrastructure.repository.get_cet_settings_row", return_value={}), \
         patch(f"{_HOOK_MOD}.finalize_modulation_payroll_application"), \
         patch(f"{_HOOK_CET}.finalize_cet_payroll_application"), \
         patch(f"{_HOOK_CET}.apply_cet_cp_debits_for_payroll"):
        bulletin = run_payslip_generation_heures(
            dossier, YEAR, MONTH, racine, company_id=COMPANY_ID, employee_id=EMPLOYEE_ID, persister=False
        )
    cumuls = json.loads((dossier / "cumuls" / f"{MONTH:02d}.json").read_text(encoding="utf-8"))["cumuls"]
    return bulletin, cumuls


def _premiere_ligne_a_taux_salarial(bulletin):
    for rubrique in bulletin["cotisations_officielles"]:
        for ligne in rubrique["lignes"]:
            if ligne.get("coti_id") and (ligne.get("taux_salarial") or 0) > 0 and not ligne.get("regularisation"):
                return ligne
    raise AssertionError("aucune cotisation salariale à taux")


@pytest.mark.skipif(_needs_supabase(), reason="SUPABASE_URL et SUPABASE_SERVICE_KEY requis")
def test_une_regularisation_salariale_change_les_cotisations_et_le_net_social_d_autant():
    avant, cumuls_avant = _generer(None)
    cible = _premiere_ligne_a_taux_salarial(avant)
    regul = {"type": "regularisation_cotisation", "coti_id": cible["coti_id"], "libelle": cible["libelle"],
             "motif": "Essai de régularisation", "base": 100.0, "taux_salarial": cible["taux_salarial"],
             "taux_patronal": cible.get("taux_patronal") or 0.0, "saisie_id": "s-essai"}
    apres, cumuls_apres = _generer([regul])

    delta = round(100.0 * cible["taux_salarial"], 2)
    assert apres["structure_cotisations"]["total_salarial"] == pytest.approx(
        avant["structure_cotisations"]["total_salarial"] + delta, abs=0.005)
    assert apres["synthese_net"]["net_social_avant_impot"] == pytest.approx(
        avant["synthese_net"]["net_social_avant_impot"] - delta, abs=0.005)
    assert apres["salaire_brut"] == avant["salaire_brut"]
    assert cumuls_apres["net_imposable"] <= cumuls_avant["net_imposable"]
    regularisees = [l for r in apres["cotisations_officielles"] for l in r["lignes"] if l.get("regularisation")]
    assert [l["libelle"] for l in regularisees] == [f"Régularisation – {cible['libelle']}"]
```

- [ ] **Étape 2 : lancer les tests, ils échouent**

Commande : `cd backend && .venv/bin/python -m pytest tests/unit/payroll/test_regularisations_dans_les_pipelines.py tests/unit/payroll/test_cumul_reduction_regularisee.py tests/migration/test_regularisation_heures.py -q`
Attendu : échec sur l'absence des appels, sur l'argument inconnu `regularisation_reduction_generale`, et sur l'absence de ligne régularisée.

- [ ] **Étape 3 : ranger la saisie dans les deux générateurs**

Dans `payslip_generator.py`, boucle `for row in saisies_res.data:` (ligne 917), et à l'identique dans `payslip_generator_forfait.py` (ligne 288), juste après le bloc `if est_saisie_retiree(row): ... continue` :

```python
            if ranger_regularisation(row, saisies_data):
                # Régularisation de cotisation saisie depuis le bulletin : elle
                # n'est pas une prime, le pipeline la pose dans les cotisations.
                continue
```

Avec l'import, dans chaque fichier :

```python
from app.modules.payroll.engine.corrections_manuelles import ranger_regularisation
```

- [ ] **Étape 4 : poser les régularisations dans les deux pipelines**

Dans `payslip_run_heures.py`, entre le bloc `if not jei_applicable(...): ... lignes_cotisations.append(ligne_reduction_generale)` et `resultats_nets = calculer_net_et_impot(`, puis à l'identique dans `payslip_run_forfait.py` :

```python
    # Régularisations de cotisation saisies à la main (spec 2026-10-18) : après
    # la réduction générale, qui ne doit pas les lire ; avant le net, qui lit le
    # total salarial et non les lignes.
    effet_regul = ajouter_regularisations(lignes_cotisations, total_salarial, saisie_du_mois)
    total_salarial = effet_regul.total_salarial
```

Ajouter `regularisation_reduction_generale=effet_regul.reduction_generale,` aux arguments nommés de l'appel `mettre_a_jour_cumuls(` du même fichier. Importer :

```python
from app.modules.payroll.engine.corrections_manuelles import ajouter_regularisations
```

- [ ] **Étape 5 : le cumul de la réduction générale**

Dans `payslip_run_common.py`, signature de `mettre_a_jour_cumuls` :

```python
    heures_supplementaires_mois: float | None = None,
    heures_remunerees_mois: float | None = None,
    regularisation_reduction_generale: float = 0.0,
) -> None:
```

Puis, juste après le bloc `if reduction_generale_mois: ... cumuls["reduction_generale_patronale"] = -nouveau_total` :

```python
    if regularisation_reduction_generale:
        # Le cumul enregistre la réduction réellement appliquée, régularisation
        # comprise (stockée en négatif, relue en valeur absolue par
        # `calcul_reduction_generale._lire_cumuls_precedents`). Le mois suivant
        # régularise depuis cette valeur, comme le veut la loi.
        cumul = round(
            float(cumuls.get("reduction_generale_patronale", 0.0) or 0.0)
            + float(regularisation_reduction_generale),
            2,
        )
        if cumul > 0:
            raise RegularisationInvalide(
                "La régularisation de la réduction générale dépasse la réduction "
                "appliquée depuis janvier : la réduction de l'année deviendrait "
                "négative. Corrigez son montant."
            )
        cumuls["reduction_generale_patronale"] = cumul
```

Importer `RegularisationInvalide` depuis `app.modules.payroll.engine.corrections_manuelles`.

- [ ] **Étape 6 : lancer les tests, ils passent**

Commande : la même qu'à l'étape 2. Attendu : tout passe. Le test de migration peut être sauté sans `SUPABASE_URL` : le lancer avec `backend/.env` chargé (lecture seule des barèmes).

- [ ] **Étape 7 : lancer les tests voisins du moteur**

Commande : `cd backend && .venv/bin/python -m pytest tests/unit/payroll tests/migration -q -x`
Attendu : seuls échouent les deux tests connus pour l'environnement local.

- [ ] **Étape 8 : commiter**

```bash
git add backend/app/modules/payroll/documents/payslip_generator.py backend/app/modules/payroll/documents/payslip_generator_forfait.py backend/app/modules/payroll/documents/payslip_run_heures.py backend/app/modules/payroll/documents/payslip_run_forfait.py backend/app/modules/payroll/documents/payslip_run_common.py backend/tests/unit/payroll/test_regularisations_dans_les_pipelines.py backend/tests/unit/payroll/test_cumul_reduction_regularisee.py backend/tests/migration/test_regularisation_heures.py
git commit -m "feat(paie): le moteur rejoue les régularisations de cotisation : les deux générateurs les rangent à part des primes, les deux pipelines les posent après la réduction générale et avant le net (total salarial, net, impôt suivent), le cumul de la réduction générale enregistre la réduction réellement appliquée et refuse une réduction annuelle négative"
```

---

### Tâche 4 : le net imposable suit une régularisation de mutuelle ou de CSG non déductible

**Fichiers :**
- Modifier : `backend/app/modules/payroll/engine/calcul_net.py:115-137`
- Tester : `backend/tests/unit/payroll/test_net_imposable_regularisations.py` (créé)

**Interfaces :**
- Consomme : `RegularisationCotisation.ligne_de_cotisation()` (tâche 2).

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
"""Le net imposable classe une régularisation comme la ligne qu'elle régularise."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.payroll.engine import calcul_net
from app.modules.payroll.engine.corrections_manuelles import RegularisationCotisation

pytestmark = pytest.mark.unit


def _mutuelle(patronal):
    return {"coti_id": "mutuelle", "libelle": "Mutuelle", "montant_salarial": 20.0, "montant_patronal": patronal}


def test_sans_regularisation_la_part_reintegree_est_inchangee():
    with patch.object(calcul_net, "_get_part_patronale_mutuelle", return_value=30.0):
        assert calcul_net._part_patronale_mutuelle_du_bulletin(None, [_mutuelle(30.0)]) == 30.0
        assert calcul_net._part_patronale_mutuelle_du_bulletin(None, []) == 0.0


def test_une_regularisation_de_la_part_patronale_est_reintegree():
    regul = RegularisationCotisation(coti_id="mutuelle", libelle="Mutuelle", motif="Tarif 2026",
                                     montant_patronal=5.0).ligne_de_cotisation()
    with patch.object(calcul_net, "_get_part_patronale_mutuelle", return_value=30.0):
        assert calcul_net._part_patronale_mutuelle_du_bulletin(None, [_mutuelle(30.0), regul]) == 35.0


def test_une_regularisation_de_csg_non_deductible_est_lue_comme_elle():
    regul = RegularisationCotisation(coti_id="csg_non_deductible", libelle="CSG/CRDS non déductible",
                                     motif="Base oubliée", base=100.0, taux_salarial=0.029).ligne_de_cotisation()
    libelle = regul["libelle"].lower()
    assert "csg/crds" in libelle and "non déductible" in libelle and "sur hs" not in libelle
```

- [ ] **Étape 2 : lancer les tests**

Commande : `cd backend && .venv/bin/python -m pytest tests/unit/payroll/test_net_imposable_regularisations.py -q`
Attendu : `test_une_regularisation_de_la_part_patronale_est_reintegree` échoue (30.0 au lieu de 35.0) ; les deux autres passent.

- [ ] **Étape 3 : implémenter**

Remplacer le corps de `_part_patronale_mutuelle_du_bulletin` (en gardant la docstring), puis ajouter cette phrase à la docstring : « Une régularisation saisie à la main s'ajoute à ce plafond : elle corrige ce que le bulletin a vraiment versé. »

```python
    mutuelle = [l for l in lignes_cotisations if l.get("coti_id") == "mutuelle"]
    calculee = round(
        sum(_get_safe_float(l.get("montant_patronal")) for l in mutuelle if not l.get("regularisation")),
        2,
    )
    regularisee = round(
        sum(_get_safe_float(l.get("montant_patronal")) for l in mutuelle if l.get("regularisation")),
        2,
    )
    fiche = _get_part_patronale_mutuelle(contexte)
    reintegree = min(fiche, calculee) if calculee > 0 else 0.0
    if regularisee and fiche > 0:
        reintegree += regularisee
    return round(max(0.0, reintegree), 2)
```

- [ ] **Étape 4 : lancer les tests, ils passent**

Commande : la même qu'à l'étape 2. Attendu : tout passe.

- [ ] **Étape 5 : commiter**

```bash
git add backend/app/modules/payroll/engine/calcul_net.py backend/tests/unit/payroll/test_net_imposable_regularisations.py
git commit -m "fix(paie): une régularisation de la part patronale de mutuelle est réintégrée au net imposable au-delà du plafond de la fiche ; une régularisation de CSG non déductible est lue comme elle (libellé d'origine)"
```

---

### Tâche 5 : la route de correction ajoute, retire et restaure les régularisations

**Fichiers :**
- Modifier : `backend/app/modules/payslips/schemas/requests.py`, `backend/app/modules/payslips/domain/corrections.py`, `backend/app/modules/payslips/application/corrections.py:157-166`
- Tester : `backend/tests/unit/payslips/test_corrections.py` (étendu), `backend/tests/unit/payslips/test_corrections_restauration_regularisations.py` (créé)

**Interfaces :**
- Consomme : `RegularisationCotisation`, `RegularisationInvalide`, `regularisations_du_bulletin` (tâche 2).
- Produit : `CorrectionsBulletin.regularisations_ajoutees: tuple[RegularisationCotisation, ...] = ()`, `CorrectionsBulletin.regularisations_retirees: tuple[str, ...] = ()`. Requête : `RegularisationAjoutee` (Pydantic), `CorrectionsBulletinRequest.regularisations_ajoutees: list[RegularisationAjoutee]`, `CorrectionsBulletinRequest.regularisations_retirees: list[str]`.

- [ ] **Étape 1 : écrire les tests qui échouent**

Ajouter à `backend/tests/unit/payslips/test_corrections.py` :

```python
from app.modules.payroll.engine.corrections_manuelles import RegularisationCotisation

REGUL = {"coti_id": "mutuelle", "libelle": "Mutuelle", "motif": "Tarif 2026", "montant_patronal": 8.3}


def test_une_regularisation_sans_motif_est_refusee_par_la_requete():
    with pytest.raises(ValidationError):
        PayslipEditRequest(corrections={"regularisations_ajoutees": [{**REGUL, "motif": ""}]})


def test_une_regularisation_ambigue_est_refusee_par_la_requete():
    with pytest.raises(ValidationError):
        PayslipEditRequest(corrections={"regularisations_ajoutees": [{**REGUL, "base": 10, "taux_patronal": 0.01}]})


def test_la_requete_donne_des_regularisations_au_domaine():
    requete = PayslipEditRequest(corrections={"regularisations_ajoutees": [REGUL], "regularisations_retirees": ["s9"]})
    domaine = requete.corrections.vers_domaine()
    assert domaine.regularisations_ajoutees[0].montants() == (0.0, 8.3)
    assert domaine.regularisations_retirees == ("s9",)
    assert domaine.change_des_variables


def test_ajouter_une_regularisation_ecrit_une_saisie_du_mois_puis_recalcule(base):
    regul = RegularisationCotisation(**REGUL)
    _corriger(CorrectionsBulletin(regularisations_ajoutees=(regul,)))
    inserts = base.de("monthly_inputs", "insert")
    assert len(inserts) == 1
    saisie = inserts[0][2][0]
    assert saisie["employee_id"] == "emp-1" and saisie["company_id"] == "comp-1"
    assert saisie["year"] == 2026 and saisie["month"] == 8
    assert saisie["correction_ligne"]["type"] == "regularisation_cotisation"
    assert base.generer.called


def test_retirer_une_regularisation_supprime_la_seule_saisie_du_bulletin(base):
    _corriger(CorrectionsBulletin(regularisations_retirees=("s9",)))
    suppressions = base.de("monthly_inputs", "delete")
    assert len(suppressions) == 1
    filtres = dict(suppressions[0][3])
    assert filtres["employee_id"] == "emp-1" and filtres["year"] == 2026 and filtres["month"] == 8
    assert filtres["id"] == ("s9",)
```

Créer `backend/tests/unit/payslips/test_corrections_restauration_regularisations.py` :

```python
"""Restaurer une version revient aussi à ses régularisations."""
from __future__ import annotations

import pytest

from app.modules.payroll.engine.corrections_manuelles import RegularisationCotisation
from app.modules.payslips.domain.corrections import corrections_pour_revenir, resume_des_corrections

pytestmark = pytest.mark.unit


def _bulletin(*regs):
    return {"cotisations_officielles": [{"code": "sante", "lignes": [r.ligne_de_cotisation() for r in regs]}]}


A = RegularisationCotisation(coti_id="mutuelle", libelle="Mutuelle", motif="Tarif", montant_patronal=8.3, saisie_id="s1")
B = RegularisationCotisation(coti_id="mutuelle", libelle="Mutuelle", motif="Autre", montant_patronal=2.0, saisie_id="s2")


def test_une_regularisation_ajoutee_depuis_la_version_est_retiree():
    c = corrections_pour_revenir(_bulletin(A, B), _bulletin(A))
    assert c.regularisations_retirees == ("s2",)
    assert c.regularisations_ajoutees == ()


def test_une_regularisation_disparue_depuis_la_version_est_recreee():
    c = corrections_pour_revenir(_bulletin(), _bulletin(A))
    assert [r.motif for r in c.regularisations_ajoutees] == ["Tarif"]
    assert c.regularisations_ajoutees[0].saisie_id is None


def test_le_resume_nomme_la_regularisation():
    from app.modules.payslips.domain.corrections import CorrectionsBulletin
    texte = resume_des_corrections(CorrectionsBulletin(regularisations_ajoutees=(A,), regularisations_retirees=("s2",)))
    assert "régularisation « mutuelle » : tarif" in texte.lower()
    assert "1 régularisation retirée" in texte
```

- [ ] **Étape 2 : lancer les tests, ils échouent**

Commande : `cd backend && .venv/bin/python -m pytest tests/unit/payslips/test_corrections.py tests/unit/payslips/test_corrections_restauration_regularisations.py -q`
Attendu : échecs sur les champs inconnus `regularisations_ajoutees` et `regularisations_retirees`.

- [ ] **Étape 3 : le domaine**

Dans `backend/app/modules/payslips/domain/corrections.py`, ajouter les champs à `CorrectionsBulletin` :

```python
from app.modules.payroll.engine.corrections_manuelles import (
    RegularisationCotisation,
    regularisations_du_bulletin,
)
```

```python
    primes: DiffPrimes = DiffPrimes()
    #: Régularisations de cotisation à ajouter, puis identifiants de saisie à retirer.
    regularisations_ajoutees: tuple[RegularisationCotisation, ...] = ()
    regularisations_retirees: tuple[str, ...] = ()

    @property
    def change_des_variables(self) -> bool:
        return (
            self.heures_sup is not None
            or self.revenir_au_planning
            or not self.primes.vide
            or bool(self.regularisations_ajoutees)
            or bool(self.regularisations_retirees)
        )
```

Dans `resume_des_corrections`, avant `if not parties:` :

```python
    for regul in corrections.regularisations_ajoutees:
        parties.append(f"régularisation « {regul.libelle} » : {regul.motif}")
    if corrections.regularisations_retirees:
        n = len(corrections.regularisations_retirees)
        parties.append(f"{n} régularisation{'s' if n > 1 else ''} retirée{'s' if n > 1 else ''}")
```

Dans `corrections_pour_revenir`, avant le `return`, puis passer les deux tuples au constructeur :

```python
    regul_courant = regularisations_du_bulletin(courant)
    regul_cible = regularisations_du_bulletin(cible)
    regularisations_retirees = tuple(sid for sid in regul_courant if sid not in regul_cible)
    regularisations_ajoutees = tuple(
        RegularisationCotisation.depuis({**regul.charge_utile()})
        for sid, regul in regul_cible.items()
        if sid not in regul_courant and sid not in saisies_existantes
    )
```

```python
    return CorrectionsBulletin(
        heures_sup=_heures_pour_revenir(courant, cible),
        primes=DiffPrimes(tuple(ajoutees), tuple(modifiees), retirees),
        regularisations_ajoutees=regularisations_ajoutees,
        regularisations_retirees=regularisations_retirees,
    )
```

Mettre à jour la docstring du module : « Ce qui se corrige sur un bulletin : ses heures sup, ses primes du mois et ses régularisations de cotisation. »

- [ ] **Étape 4 : la requête**

Dans `backend/app/modules/payslips/schemas/requests.py` :

```python
from app.modules.payroll.engine.corrections_manuelles import (
    RegularisationCotisation,
    RegularisationInvalide,
)


class RegularisationAjoutee(BaseModel):
    """Une régularisation de cotisation saisie depuis le bulletin. Le serveur
    calcule les montants d'une régularisation par la base ; il ne reçoit un
    montant que pour une cotisation sans taux."""

    model_config = ConfigDict(extra="forbid")

    coti_id: str = Field(..., min_length=1, max_length=80)
    libelle: str = Field(..., min_length=1, max_length=160)
    motif: str = Field(..., min_length=3, max_length=300)
    base: float | None = Field(None, ge=-1_000_000, le=1_000_000)
    taux_salarial: float | None = Field(None, ge=-1, le=1)
    taux_patronal: float | None = Field(None, ge=-1, le=1)
    montant_salarial: float | None = Field(None, ge=-100_000, le=100_000)
    montant_patronal: float | None = Field(None, ge=-100_000, le=100_000)

    @model_validator(mode="after")
    def _regularisation_coherente(self) -> "RegularisationAjoutee":
        try:
            self.vers_domaine()
        except RegularisationInvalide as exc:
            raise ValueError(str(exc)) from exc
        return self

    def vers_domaine(self) -> RegularisationCotisation:
        return RegularisationCotisation(**self.model_dump())
```

Dans `CorrectionsBulletinRequest` :

```python
    regularisations_ajoutees: list[RegularisationAjoutee] = Field(default_factory=list, max_length=20)
    regularisations_retirees: list[str] = Field(default_factory=list, max_length=50)
```

et dans `vers_domaine()`, ajouter au constructeur :

```python
            regularisations_ajoutees=tuple(r.vers_domaine() for r in self.regularisations_ajoutees),
            regularisations_retirees=tuple(dict.fromkeys(self.regularisations_retirees)),
```

Mettre à jour la docstring de `CorrectionsBulletinRequest` : « heures sup, primes et régularisations de cotisation du mois ».

- [ ] **Étape 5 : l'écriture**

Dans `backend/app/modules/payslips/application/corrections.py` :

```python
def _ecrire_regularisations(corrections: CorrectionsBulletin, periode: dict[str, Any]) -> None:
    """Ajoute et retire les régularisations du mois. Le retrait ne vise que les
    saisies de ce salarié et de ce mois : un identifiant d'un autre bulletin
    ne supprime rien."""
    if corrections.regularisations_retirees:
        (
            supabase.table("monthly_inputs")
            .delete()
            .match(periode)
            .in_("id", list(corrections.regularisations_retirees))
            .execute()
        )
    if corrections.regularisations_ajoutees:
        supabase.table("monthly_inputs").insert(
            [r.saisie_du_mois(periode) for r in corrections.regularisations_ajoutees]
        ).execute()
```

et l'appeler à la fin de `_ecrire_variables` :

```python
    _ecrire_regularisations(corrections, periode)
```

- [ ] **Étape 6 : lancer les tests, ils passent**

Commande : `cd backend && .venv/bin/python -m pytest tests/unit/payslips -q`
Attendu : tout passe.

- [ ] **Étape 7 : commiter**

```bash
git add backend/app/modules/payslips backend/tests/unit/payslips/test_corrections.py backend/tests/unit/payslips/test_corrections_restauration_regularisations.py
git commit -m "feat(paie): l'onglet « Corriger » ajoute et retire des régularisations de cotisation (motif obligatoire, montants calculés par le serveur, retrait limité au bulletin), les restaure avec leur version et les nomme dans l'historique"
```

---

### Tâche 6 : la DSN additionne le montant d'une régularisation, jamais son taux

**Fichiers :**
- Modifier : `backend/app/modules/dsn_export/domain/cotisation_mapping.py` (`LigneDsn` vers la ligne 202, `_cumuler` vers la ligne 720, la boucle de `build_bases_and_cotisations` vers la ligne 777)
- Tester : `backend/tests/unit/dsn_export/test_regularisations_dsn.py` (créé)

**Interfaces :**
- Consomme : `RegularisationCotisation.ligne_de_cotisation()` (tâche 2).
- Produit : `LigneDsn.regularisation: bool = False`.

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
"""Une régularisation de cotisation se déclare avec sa ligne d'origine : le
montant et l'assiette s'additionnent, le taux reste celui de la cotisation."""
from __future__ import annotations

import pytest

from app.modules.dsn_export.domain.cotisation_mapping import build_bases_and_cotisations
from app.modules.payroll.engine.corrections_manuelles import RegularisationCotisation

pytestmark = pytest.mark.unit


def _maladie(base):
    return {"coti_id": "securite_sociale_maladie", "libelle": "Sécurité sociale - Maladie", "base": base,
            "taux_salarial": None, "taux_patronal": 0.07, "montant_salarial": 0.0,
            "montant_patronal": round(base * 0.07, 2)}


def _cotisations(lignes):
    _, cotisations, _ = build_bases_and_cotisations(lignes, brut=2000.0, period_start="2026-10-01",
                                                    period_end="2026-10-31")
    return cotisations


def _par_code(cotisations, code):
    trouvees = [c for c in cotisations if c.code == code]
    assert len(trouvees) == 1, trouvees
    return trouvees[0]


def test_la_regularisation_ajoute_son_montant_et_son_assiette_et_garde_le_taux():
    regul = RegularisationCotisation(coti_id="securite_sociale_maladie", libelle="Sécurité sociale - Maladie",
                                     motif="Base oubliée", base=100.0, taux_patronal=0.07).ligne_de_cotisation()
    sans = _par_code(_cotisations([_maladie(2000.0)]), "075")
    avec = _par_code(_cotisations([_maladie(2000.0), regul]), "075")
    assert avec.montant_patronal == pytest.approx(sans.montant_patronal + 7.0, abs=0.001)
    assert avec.montant_assiette == pytest.approx(sans.montant_assiette + 100.0, abs=0.001)
    assert avec.rubriques.get("S21.G00.81.007") == sans.rubriques.get("S21.G00.81.007")


def test_sans_regularisation_la_dsn_ne_change_pas():
    assert _cotisations([_maladie(2000.0)]) == _cotisations([_maladie(2000.0)])
```

`CotisationIndividuelleBlock` (`app.modules.dsn_import.domain.model`) porte `code`, `montant_assiette`, `montant_salarial` (toujours 0), `montant_patronal` (le montant déclaré) et `rubriques` (le taux en `S21.G00.81.007`).

- [ ] **Étape 2 : lancer les tests, ils échouent**

Commande : `cd backend && .venv/bin/python -m pytest tests/unit/dsn_export/test_regularisations_dsn.py -q`
Attendu : `test_la_regularisation_ajoute_son_montant_et_son_assiette_et_garde_le_taux` échoue, car le taux déclaré vaut 14 % et l'assiette reste celle d'origine.

- [ ] **Étape 3 : implémenter**

Ajouter le champ à `LigneDsn`, après `par_taux` :

```python
    # Régularisation saisie à la main : se fond dans la ligne de même code en
    # ajoutant son montant et son assiette (elle est une base), jamais son taux.
    regularisation: bool = False
```

Dans `_cumuler`, juste après `existante = cumulees.get(cle)` et le bloc `if existante is None: ...` :

```python
        if ligne.regularisation:
            existante.montant = round(existante.montant + ligne.montant, 2)
            existante.assiette = round(existante.assiette + ligne.assiette, 2)
            continue
```

Dans la boucle de `build_bases_and_cotisations`, remplacer `traduites = _traduire(ligne, tmax, assiette_hs, brut)` par :

```python
        est_regularisation = bool(ligne.get("regularisation"))
        # Une régularisation de la réduction générale ne redéclare pas le brut
        # en assiette : elle n'ajoute que son montant.
        traduites = _traduire(ligne, tmax, assiette_hs, 0.0 if est_regularisation else brut)
        if est_regularisation:
            for traduite in traduites:
                traduite.regularisation = True
```

Une régularisation de la réduction générale n'a pas de base (`base: None`) : `_parts` la lit à 0 par `_flottant`, donc `_reduction_generale` reçoit une assiette nulle et la fusion n'ajoute que le montant.

- [ ] **Étape 4 : lancer les tests DSN, ils passent**

Commande : `cd backend && .venv/bin/python -m pytest tests/unit/dsn_export -q`
Attendu : tout passe, et aucun test DSN existant ne change.

- [ ] **Étape 5 : commiter**

```bash
git add backend/app/modules/dsn_export/domain/cotisation_mapping.py backend/tests/unit/dsn_export/test_regularisations_dsn.py
git commit -m "fix(dsn): une régularisation de cotisation se fond dans la ligne de même code en ajoutant son montant et son assiette, jamais son taux (la fusion déclarait 14 % de maladie) ; une régularisation de la réduction générale ne redéclare pas le brut"
```

---

### Tâche 7 : le PDF le dit, et les listes de bulletins le savent

**Fichiers :**
- Modifier : `backend/app/modules/payroll/documents/bulletin_view.py` (fonction qui assemble `lignes`, autour des lignes 527-560), `backend/app/modules/payslips/infrastructure/payslip_list_meta.py`
- Tester : `backend/tests/unit/payroll/test_bulletin_view_regularisations.py` (créé), `backend/tests/unit/payslips/test_payslip_list_meta_regularisations.py` (créé)

**Interfaces :**
- Consomme : `mentions_des_regularisations`, `regularisations_du_bulletin` (tâche 2).
- Produit : `payslip_list_meta(...)["regularisations"]: list[str]` (libellés des cotisations régularisées).

- [ ] **Étape 1 : écrire les tests qui échouent**

La boucle `for rubrique in rubriques_principales: lignes.extend(_lignes_rubrique(rubrique))` est dans `construire_lignes(bulletin)` (`bulletin_view.py:508`). Écrire `test_bulletin_view_regularisations.py` :

```python
from __future__ import annotations

import pytest

from app.modules.payroll.documents import bulletin_view
from app.modules.payroll.engine.corrections_manuelles import RegularisationCotisation

pytestmark = pytest.mark.unit


def test_le_pdf_porte_une_note_par_regularisation():
    ligne = RegularisationCotisation(coti_id="mutuelle", libelle="Mutuelle", motif="Tarif 2026",
                                     montant_patronal=8.3, saisie_id="s1").ligne_de_cotisation()
    bulletin = {"cotisations_officielles": [{"code": "sante", "libelle": "Santé", "lignes": [ligne]}]}
    lignes = bulletin_view.construire_lignes(bulletin)
    notes = [l["libelle"] for l in lignes if l["type"] == "note"]
    assert "Régularisation saisie à la main — Mutuelle : Tarif 2026" in notes
```

Puis `test_payslip_list_meta_regularisations.py` :

```python
from __future__ import annotations

import pytest

from app.modules.payroll.engine.corrections_manuelles import RegularisationCotisation
from app.modules.payslips.infrastructure.payslip_list_meta import payslip_list_meta

pytestmark = pytest.mark.unit


def test_la_liste_dit_les_cotisations_regularisees():
    ligne = RegularisationCotisation(coti_id="mutuelle", libelle="Mutuelle", motif="Tarif",
                                     montant_patronal=8.3, saisie_id="s1").ligne_de_cotisation()
    meta = payslip_list_meta({"cotisations_officielles": [{"code": "sante", "lignes": [ligne]}]})
    assert meta["regularisations"] == ["Mutuelle"]


def test_un_bulletin_sans_regularisation_n_en_dit_aucune():
    assert payslip_list_meta({})["regularisations"] == []
    assert payslip_list_meta(None)["regularisations"] == []
```

- [ ] **Étape 2 : lancer les tests, ils échouent**

Commande : `cd backend && .venv/bin/python -m pytest tests/unit/payroll/test_bulletin_view_regularisations.py tests/unit/payslips/test_payslip_list_meta_regularisations.py -q`
Attendu : la note est absente, et `KeyError: 'regularisations'`.

- [ ] **Étape 3 : implémenter**

Dans `bulletin_view.py`, juste après la boucle `for rubrique in rubriques_principales: lignes.extend(_lignes_rubrique(rubrique))` :

```python
    for mention in mentions_des_regularisations(bulletin):
        lignes.append(_ligne("note", mention))
```

avec l'import `from app.modules.payroll.engine.corrections_manuelles import mentions_des_regularisations`.

Dans `payslip_list_meta.py`, ajouter `"regularisations": [],` au dictionnaire `vide`, puis, dans le dictionnaire retourné pour un bulletin lisible :

```python
        "regularisations": sorted({r.libelle for r in regularisations_du_bulletin(payslip_data).values()}),
```

avec l'import `from app.modules.payroll.engine.corrections_manuelles import regularisations_du_bulletin`.

La liste des bulletins d'un salarié recopie les métadonnées champ par champ (`backend/app/modules/payslips/infrastructure/queries.py`, `get_employee_payslips`, autour de la ligne 266) : ajouter, après `"empreinte_complementaire": meta.get("empreinte_complementaire"),` :

```python
                "regularisations": meta.get("regularisations", []),
```

(L'autre appelant, ligne 193, ne sert que le nom, l'URL, le net et les alertes : rien à y ajouter.)

- [ ] **Étape 4 : lancer les tests, ils passent**

Commande : la même qu'à l'étape 2. Attendu : tout passe.

- [ ] **Étape 5 : commiter**

```bash
git add backend/app/modules/payroll/documents/bulletin_view.py backend/app/modules/payslips/infrastructure/payslip_list_meta.py backend/app/modules/payslips/infrastructure/queries.py backend/tests/unit/payroll/test_bulletin_view_regularisations.py backend/tests/unit/payslips/test_payslip_list_meta_regularisations.py
git commit -m "feat(paie): le PDF porte une note par régularisation saisie à la main (cotisation et motif), et les listes de bulletins disent les cotisations régularisées"
```

---

### Tâche 8 : l'écran « Corriger » ajoute et retire une régularisation

**Fichiers :**
- Modifier : `frontend/src/api/payslips.ts:305-311`, `frontend/src/features/payroll/utils/correctionsBulletin.ts`, `frontend/src/components/payslip-edit/CorrectionsBulletinPanel.tsx`
- Créer : `frontend/src/components/payslip-edit/RegularisationsCotisationCard.tsx`
- Tester : `frontend/src/features/payroll/utils/correctionsBulletin.test.ts` (étendu)

**Interfaces :**
- Consomme : la requête `regularisations_ajoutees` et `regularisations_retirees` (tâche 5) ; la clé `regularisation` des lignes (tâche 2).
- Produit, dans `correctionsBulletin.ts` : `CotisationRegularisable`, `RegularisationDuBulletin`, `cotisationsRegularisables(data)`, `regularisationsDuBulletin(data)`, `regularisationDepuisEcart(cotisation, ecart, part, motif)`, et dans `EtatCorrections` les champs `regularisations`, `regularisationsAjoutees`, `regularisationsRetirees`.

- [ ] **Étape 1 : les types de l'API**

Dans `frontend/src/api/payslips.ts`, avant `CorrectionsBulletin` :

```ts
/** Une régularisation de cotisation saisie depuis le bulletin (spec 2026-10-18). */
export interface RegularisationAjoutee {
  coti_id: string;
  libelle: string;
  motif: string;
  /** Par la base : le serveur calcule base × taux. Sinon, montant d'une cotisation sans taux. */
  base?: number | null;
  taux_salarial?: number | null;
  taux_patronal?: number | null;
  montant_salarial?: number | null;
  montant_patronal?: number | null;
}
```

Dans `CorrectionsBulletin` :

```ts
  regularisations_ajoutees?: RegularisationAjoutee[];
  regularisations_retirees?: string[];
```

- [ ] **Étape 2 : écrire les tests qui échouent**

Ajouter à `correctionsBulletin.test.ts` :

```ts
import {
  cotisationsRegularisables,
  etatInitial,
  regularisationDepuisEcart,
  regularisationsDuBulletin,
  requeteDeCorrection,
} from './correctionsBulletin';

const BULLETIN = {
  cotisations_officielles: [
    {
      code: 'sante',
      lignes: [
        { coti_id: 'securite_sociale_maladie', libelle: 'Sécurité sociale - Maladie', base: 2000, taux_patronal: 0.07, montant_patronal: 140 },
        { coti_id: 'mutuelle', libelle: 'Mutuelle', base: null, taux_salarial: null, taux_patronal: null, montant_salarial: 20, montant_patronal: 30 },
        { libelle: 'CSG déductible — Participation', base: 100, taux_salarial: 0.068, montant_salarial: 6.8, is_participation: true },
        {
          coti_id: 'mutuelle', libelle: 'Régularisation – Mutuelle', montant_patronal: 5,
          regularisation: { saisie_id: 's1', coti_id: 'mutuelle', libelle: 'Mutuelle', motif: 'Tarif', montant_patronal: 5 },
        },
      ],
    },
  ],
};

describe('régularisations de cotisation', () => {
  it('propose les cotisations du bulletin, sans la participation ni les régularisations', () => {
    expect(cotisationsRegularisables(BULLETIN).map((c) => c.cotiId)).toEqual(['securite_sociale_maladie', 'mutuelle']);
  });

  it('lit les régularisations déjà posées', () => {
    expect(regularisationsDuBulletin(BULLETIN)).toEqual([
      { saisieId: 's1', libelle: 'Mutuelle', motif: 'Tarif', montantSalarial: 0, montantPatronal: 5 },
    ]);
  });

  it('convertit un écart en euros en base au taux de la cotisation', () => {
    const [maladie] = cotisationsRegularisables(BULLETIN);
    const r = regularisationDepuisEcart(maladie, 7, 'patronale', 'Base oubliée');
    expect(r).toEqual({
      coti_id: 'securite_sociale_maladie', libelle: 'Sécurité sociale - Maladie', motif: 'Base oubliée',
      base: 100, taux_salarial: null, taux_patronal: 0.07,
    });
  });

  it('une cotisation sans taux se régularise par son montant', () => {
    const mutuelle = cotisationsRegularisables(BULLETIN)[1];
    expect(regularisationDepuisEcart(mutuelle, -4.1, 'salariale', 'Tarif')).toEqual({
      coti_id: 'mutuelle', libelle: 'Mutuelle', motif: 'Tarif', montant_salarial: -4.1, montant_patronal: null,
    });
  });

  it('la requête porte les régularisations ajoutées et retirées', () => {
    const initial = etatInitial(BULLETIN, '');
    const courant = {
      ...initial,
      regularisationsRetirees: ['s1'],
      regularisationsAjoutees: [{ coti_id: 'mutuelle', libelle: 'Mutuelle', motif: 'Tarif', montant_patronal: 2 }],
    };
    const requete = requeteDeCorrection(initial, courant, null);
    expect(requete.corrections.regularisations_retirees).toEqual(['s1']);
    expect(requete.corrections.regularisations_ajoutees).toHaveLength(1);
  });
});
```

- [ ] **Étape 3 : lancer les tests, ils échouent**

Commande : `cd frontend && npx vitest run src/features/payroll/utils/correctionsBulletin.test.ts`
Attendu : les fonctions n'existent pas.

- [ ] **Étape 4 : implémenter les fonctions**

Dans `correctionsBulletin.ts`, ajouter l'import `RegularisationAjoutee` depuis `@/api/payslips`, puis :

```ts
/** Une cotisation du bulletin qu'on peut régulariser (elle porte un organisme). */
export interface CotisationRegularisable {
  cotiId: string;
  libelle: string;
  tauxSalarial: number | null;
  tauxPatronal: number | null;
}

/** Une régularisation imprimée sur le bulletin. */
export interface RegularisationDuBulletin {
  saisieId: string;
  libelle: string;
  motif: string;
  montantSalarial: number;
  montantPatronal: number;
}

function lignesDeCotisation(data: unknown): Ligne[] {
  const d = (data ?? {}) as { cotisations_officielles?: unknown };
  const rubriques = Array.isArray(d.cotisations_officielles) ? (d.cotisations_officielles as Ligne[]) : [];
  return rubriques.flatMap((r) => (Array.isArray(r.lignes) ? (r.lignes as Ligne[]) : []));
}

export function cotisationsRegularisables(data: unknown): CotisationRegularisable[] {
  const vues = new Set<string>();
  const sortie: CotisationRegularisable[] = [];
  for (const l of lignesDeCotisation(data)) {
    if (!l.coti_id || l.regularisation || l.is_participation || l.is_ppv) continue;
    const libelle = typeof l.libelle === 'string' ? l.libelle : String(l.coti_id);
    const cle = `${l.coti_id}|${libelle}`;
    if (vues.has(cle)) continue;
    vues.add(cle);
    sortie.push({
      cotiId: String(l.coti_id),
      libelle,
      tauxSalarial: nombre(l.taux_salarial) || null,
      tauxPatronal: nombre(l.taux_patronal) || null,
    });
  }
  return sortie;
}

export function regularisationsDuBulletin(data: unknown): RegularisationDuBulletin[] {
  return lignesDeCotisation(data)
    .map((l) => l.regularisation as Ligne | undefined)
    .filter((r): r is Ligne => !!r && typeof r === 'object' && !!r.saisie_id)
    .map((r) => ({
      saisieId: String(r.saisie_id),
      libelle: String(r.libelle ?? ''),
      motif: String(r.motif ?? ''),
      montantSalarial: arrondi(nombre(r.montant_salarial) ?? 0),
      montantPatronal: arrondi(nombre(r.montant_patronal) ?? 0),
    }));
}

export type PartRegularisee = 'salariale' | 'patronale' | 'les_deux';

/**
 * Un écart en euros devient une base au taux de la cotisation (règle 3 de la
 * spec : un montant différent de base × taux est rejeté par la DSN). Le serveur
 * recalcule le montant arrondi. Sans taux, l'écart est le montant.
 */
export function regularisationDepuisEcart(
  cotisation: CotisationRegularisable,
  ecart: number,
  part: PartRegularisee,
  motif: string
): RegularisationAjoutee {
  const tauxSal = part === 'patronale' ? null : cotisation.tauxSalarial;
  const tauxPat = part === 'salariale' ? null : cotisation.tauxPatronal;
  const taux = (tauxSal ?? 0) + (tauxPat ?? 0);
  const commun = { coti_id: cotisation.cotiId, libelle: cotisation.libelle, motif: motif.trim() };
  if (taux) {
    return { ...commun, base: arrondi(ecart / taux), taux_salarial: tauxSal, taux_patronal: tauxPat };
  }
  return {
    ...commun,
    montant_salarial: part === 'patronale' ? null : arrondi(ecart),
    montant_patronal: part === 'patronale' ? arrondi(ecart) : null,
  };
}
```

Ajouter à `EtatCorrections` :

```ts
  regularisations: RegularisationDuBulletin[];
  regularisationsAjoutees: RegularisationAjoutee[];
  regularisationsRetirees: string[];
```

Dans `etatInitial`, ajouter :

```ts
    regularisations: regularisationsDuBulletin(data),
    regularisationsAjoutees: [],
    regularisationsRetirees: [],
```

Dans `requeteDeCorrection`, avant `const requete` :

```ts
  if (courant.regularisationsAjoutees.length) corrections.regularisations_ajoutees = courant.regularisationsAjoutees;
  if (courant.regularisationsRetirees.length) corrections.regularisations_retirees = courant.regularisationsRetirees;
```

- [ ] **Étape 5 : lancer les tests, ils passent**

Commande : la même qu'à l'étape 3. Attendu : tout passe, y compris les tests existants du fichier.

- [ ] **Étape 6 : la carte**

Créer `frontend/src/components/payslip-edit/RegularisationsCotisationCard.tsx` :

```tsx
/**
 * Régularisations de cotisation (spec 2026-10-18, théorème de la correction à la main).
 *
 * Une cotisation fausse se corrige ici : on choisit l'organisme, on tape l'écart
 * en euros et un motif. Il devient une base au taux de la cotisation, le serveur
 * recalcule le bulletin en entier, et la régularisation passe dans le net, les
 * cumuls, la DSN et les exports.
 */
import { useState } from 'react';
import { Scale, Trash2, Undo2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  cotisationsRegularisables,
  type EtatCorrections,
  type PartRegularisee,
  regularisationDepuisEcart,
} from '@/features/payroll/utils/correctionsBulletin';

function euros(valeur: number): string {
  return valeur.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' });
}

interface Props {
  payslipData: unknown;
  etat: EtatCorrections;
  onChange: (etat: EtatCorrections) => void;
  disabled?: boolean;
}

export default function RegularisationsCotisationCard({ payslipData, etat, onChange, disabled }: Props) {
  const cotisations = cotisationsRegularisables(payslipData);
  const [choix, setChoix] = useState(0);
  const [ecart, setEcart] = useState('');
  const [part, setPart] = useState<PartRegularisee>('les_deux');
  const [motif, setMotif] = useState('');
  const retirees = new Set(etat.regularisationsRetirees);
  const cotisation = cotisations[choix];
  const valeur = Number.parseFloat(ecart.replace(',', '.'));
  const pret = !!cotisation && Number.isFinite(valeur) && valeur !== 0 && motif.trim().length >= 3;

  const ajouter = () => {
    if (!pret || !cotisation) return;
    onChange({
      ...etat,
      regularisationsAjoutees: [...etat.regularisationsAjoutees, regularisationDepuisEcart(cotisation, valeur, part, motif)],
    });
    setEcart('');
    setMotif('');
  };

  return (
    <Card data-testid="regularisations-cotisation">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Scale className="h-5 w-5" />
          Régularisations de cotisation
        </CardTitle>
        <CardDescription>
          Une cotisation fausse ? Choisissez-la, tapez l’écart en euros et le motif. À l’enregistrement, le
          bulletin est recalculé en entier : net, cumuls, DSN et exports suivent.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {etat.regularisations.map((r) => (
          <div key={r.saisieId} className="flex items-center justify-between rounded-md border p-3 text-sm">
            <div className={retirees.has(r.saisieId) ? 'line-through text-muted-foreground' : ''}>
              <div className="font-medium">{r.libelle}</div>
              <div className="text-xs text-muted-foreground">
                {r.motif} — salarial {euros(r.montantSalarial)}, patronal {euros(r.montantPatronal)}
              </div>
            </div>
            {retirees.has(r.saisieId) ? (
              <Button variant="ghost" size="sm" disabled={disabled}
                onClick={() => onChange({ ...etat, regularisationsRetirees: etat.regularisationsRetirees.filter((id) => id !== r.saisieId) })}>
                <Undo2 className="h-4 w-4 mr-1" /> Garder
              </Button>
            ) : (
              <Button variant="ghost" size="sm" disabled={disabled}
                onClick={() => onChange({ ...etat, regularisationsRetirees: [...etat.regularisationsRetirees, r.saisieId] })}>
                <Trash2 className="h-4 w-4 mr-1" /> Retirer
              </Button>
            )}
          </div>
        ))}
        {etat.regularisationsAjoutees.map((r, index) => (
          <div key={`nouvelle-${index}`} className="flex items-center justify-between rounded-md border border-dashed p-3 text-sm">
            <div>
              <div className="font-medium">{r.libelle} (à enregistrer)</div>
              <div className="text-xs text-muted-foreground">{r.motif}</div>
            </div>
            <Button variant="ghost" size="sm" disabled={disabled}
              onClick={() => onChange({ ...etat, regularisationsAjoutees: etat.regularisationsAjoutees.filter((_, i) => i !== index) })}>
              <Trash2 className="h-4 w-4 mr-1" /> Annuler
            </Button>
          </div>
        ))}
        {!disabled && cotisations.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="regul-cotisation">Cotisation</Label>
              <select id="regul-cotisation" className="w-full rounded-md border px-2 py-2 text-sm"
                value={choix} onChange={(e) => setChoix(Number(e.target.value))}>
                {cotisations.map((c, i) => <option key={`${c.cotiId}-${i}`} value={i}>{c.libelle}</option>)}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="regul-part">Part à régulariser</Label>
              <select id="regul-part" className="w-full rounded-md border px-2 py-2 text-sm"
                value={part} onChange={(e) => setPart(e.target.value as PartRegularisee)}>
                <option value="les_deux">Les deux parts</option>
                <option value="salariale">La part salariale</option>
                <option value="patronale">La part patronale</option>
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="regul-ecart">Écart en euros (négatif pour baisser)</Label>
              <Input id="regul-ecart" inputMode="decimal" value={ecart} onChange={(e) => setEcart(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="regul-motif">Motif (obligatoire)</Label>
              <Input id="regul-motif" maxLength={300} value={motif} onChange={(e) => setMotif(e.target.value)} />
            </div>
            <div className="sm:col-span-2">
              <Button variant="outline" disabled={!pret} onClick={ajouter} data-testid="ajouter-regularisation">
                Ajouter la régularisation
              </Button>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
```

Dans `CorrectionsBulletinPanel.tsx`, importer la carte et l'insérer entre la carte « Primes du mois » et la carte « Ce qui se corrige ailleurs » :

```tsx
      <RegularisationsCotisationCard payslipData={payslipData} etat={etat} onChange={onChange} disabled={disabled} />
```

Mettre à jour la docstring du panneau : « ses heures sup, ses primes du mois et ses régularisations de cotisation ».

- [ ] **Étape 7 : vérifier les types et le lint**

Commande : `cd frontend && npx tsc --noEmit -p . && npx eslint src/components/payslip-edit src/features/payroll/utils/correctionsBulletin.ts`
Attendu : aucune erreur. Si `tsc` signale un `EtatCorrections` écrit en dur (dans un test ou un écran) sans les nouveaux champs, y ajouter `regularisations: [], regularisationsAjoutees: [], regularisationsRetirees: []`.

- [ ] **Étape 8 : commiter**

```bash
git add frontend/src/api/payslips.ts frontend/src/features/payroll/utils/correctionsBulletin.ts frontend/src/features/payroll/utils/correctionsBulletin.test.ts frontend/src/components/payslip-edit/RegularisationsCotisationCard.tsx frontend/src/components/payslip-edit/CorrectionsBulletinPanel.tsx
git commit -m "feat(paie): carte « Régularisations de cotisation » dans l'onglet « Corriger » : choisir la cotisation, la part, l'écart en euros (converti en base au taux de la cotisation) et le motif ; retirer une régularisation posée"
```

---

### Tâche 9 : la liste de contrôle compte les régularisations et signale celles qui reviennent

**Fichiers :**
- Modifier : `frontend/src/features/payroll/utils/bulletinARecalculer.ts:27-36`, `frontend/src/features/payroll/utils/listeControleMois.ts`
- Tester : `frontend/src/features/payroll/utils/listeControleMois.test.ts` (étendu)

**Interfaces :**
- Consomme : `regularisations: string[]` dans les lignes de bulletin de la liste (tâche 7).
- Produit : l'étape `ETAPE_REGULARISATIONS = 'regularisations'`, dont l'état vaut toujours `'fait'` (information, non bloquante).

- [ ] **Étape 1 : écrire les tests qui échouent**

Dans `listeControleMois.test.ts`, avec le constructeur du fichier `entree(overrides)` (ligne 57) :

```ts
it('compte les régularisations du mois et signale une cotisation régularisée deux mois de suite', () => {
  const e = entree({
    year: 2026,
    month: 10,
    bulletinsParSalarie: {
      statut: 'ok',
      valeur: {
        s1: [
          { year: 2026, month: 10, regularisations: ['Mutuelle'] },
          { year: 2026, month: 9, regularisations: ['Mutuelle'] },
        ],
        s2: [{ year: 2026, month: 10, regularisations: [] }],
      },
    },
  });
  const etape = listeControleDuMois(e).etapes.find((x) => x.id === 'regularisations');
  expect(etape?.etat).toBe('fait');
  expect(etape?.detail).toBe(
    '1 régularisation saisie à la main ce mois. « Mutuelle » est régularisée deux mois de suite : signalez-le, Martine se trompe peut-être.'
  );
});

it('sans régularisation, l’étape le dit simplement', () => {
  const etape = listeControleDuMois(entree({ bulletinsParSalarie: { statut: 'ok', valeur: {} } })).etapes.find(
    (x) => x.id === 'regularisations'
  );
  expect(etape?.detail).toBe('Aucune régularisation saisie à la main ce mois.');
});
```

- [ ] **Étape 2 : lancer les tests, ils échouent**

Commande : `cd frontend && npx vitest run src/features/payroll/utils/listeControleMois.test.ts`
Attendu : l'étape `regularisations` est absente.

- [ ] **Étape 3 : implémenter**

Dans `bulletinARecalculer.ts`, ajouter à `LigneBulletinPaie` :

```ts
  /** Cotisations régularisées à la main sur ce bulletin (libellés). */
  regularisations?: string[] | null;
```

Dans `listeControleMois.ts` :

```ts
export const ETAPE_REGULARISATIONS = 'regularisations';

function etapeRegularisations(
  lecture: Lecture<Record<string, LigneBulletinPaie[]>>,
  year: number,
  month: number
): { etat: EtatEtape; detail: string } {
  return etatDepuisLecture(lecture, (parSalarie) => {
    const precedent = month === 1 ? { year: year - 1, month: 12 } : { year, month: month - 1 };
    let total = 0;
    const repetees = new Set<string>();
    for (const bulletins of Object.values(parSalarie)) {
      const duMois = bulletins.find((b) => b.year === year && b.month === month)?.regularisations ?? [];
      const avant = new Set(
        bulletins.find((b) => b.year === precedent.year && b.month === precedent.month)?.regularisations ?? []
      );
      total += duMois.length;
      duMois.filter((l) => avant.has(l)).forEach((l) => repetees.add(l));
    }
    if (total === 0) return { etat: 'fait', detail: 'Aucune régularisation saisie à la main ce mois.' };
    const phrases = [`${total} régularisation${total > 1 ? 's' : ''} saisie${total > 1 ? 's' : ''} à la main ce mois.`];
    for (const libelle of [...repetees].sort()) {
      phrases.push(`« ${libelle} » est régularisée deux mois de suite : signalez-le, Martine se trompe peut-être.`);
    }
    return { etat: 'fait', detail: phrases.join(' ') };
  });
}
```

Dans `listeControleDuMois`, avant `const etapes = [...]` :

```ts
  const regularisations: EtapeControle = {
    id: ETAPE_REGULARISATIONS,
    libelle: 'Régularisations à la main',
    ...etapeRegularisations(entree.bulletinsParSalarie, year, month),
  };
```

puis insérer `regularisations` après `valides` dans `etapes`. Importer `LigneBulletinPaie` depuis `./bulletinARecalculer` si le fichier ne l'importe pas déjà. L'étape est toujours `'fait'` : elle n'entre ni dans le compte « N points à traiter » ni dans les actions en attente.

- [ ] **Étape 4 : lancer les tests, ils passent**

Commande : la même qu'à l'étape 2. Attendu : tout passe, et les tests existants de la liste ne changent pas (sinon, ajouter l'étape attendue aux listes d'étapes des tests existants).

- [ ] **Étape 5 : commiter**

```bash
git add frontend/src/features/payroll/utils/bulletinARecalculer.ts frontend/src/features/payroll/utils/listeControleMois.ts frontend/src/features/payroll/utils/listeControleMois.test.ts
git commit -m "feat(paie): la liste de contrôle du mois compte les régularisations saisies à la main et signale une cotisation régularisée deux mois de suite (défaut probable du moteur)"
```

---

### Tâche 10 : le test du théorème, au bac à sable

**Fichiers :**
- Créer : `backend/scripts/theoreme_correction_a_la_main.py`

**Interfaces :**
- Consomme : `payslip_generator_provider.generate_en_bac_a_sable(employee_id, year, month, cumuls_precedents, saisies_en_plus)` (`app.modules.payslips.infrastructure.providers`), `RegularisationCotisation` (tâche 2), `build_bases_and_cotisations` (tâche 6), `ligne_od_du_bulletin` et `residu_du_bulletin` (comptabilité), `poser_le_piege` (`backend/scripts/verification_rgdu/piege.py`).

- [ ] **Étape 1 : écrire le script**

```python
"""Test du théorème de la correction à la main (spec 2026-10-18, § 9), au bac à sable.

Pour chaque bulletin d'une société et d'un mois, et pour chaque cotisation
régularisable qu'il porte, injecte en mémoire une régularisation (base de 10 €
au taux de la ligne, ou 1 € pour une cotisation sans taux), recalcule sans rien
écrire, et vérifie :
  1. la ligne « Régularisation – » porte le montant attendu ;
  2. le total salarial a bougé du montant salarial attendu ;
  3. le net se reconstruit (résidu comptable nul, comme sans régularisation) ;
  4. le cumul de la réduction générale suit une régularisation de la réduction ;
  5. la DSN de la cotisation a bougé du montant attendu (à 0,01 € près par ligne scindée).
Puis, pour chaque bulletin, un gain soumis de 10 € et une retenue de 10 € sur le net
(saisies ordinaires) : le brut et son cumul, ou le net, bougent d'autant, et le net
se reconstruit. Écrit un rapport JSON hors du dépôt. Usage, depuis backend/ :
    PYTHONPATH=. .venv/bin/python scripts/theoreme_correction_a_la_main.py "<Société>" 2026 9 <sortie.json>
"""
from __future__ import annotations

import json
import sys

sys.path.insert(0, "scripts/verification_rgdu")
from piege import poser_le_piege  # noqa: E402

poser_le_piege()

from app.core.database import supabase  # noqa: E402
from app.modules.dsn_export.domain.cotisation_mapping import build_bases_and_cotisations  # noqa: E402
from app.modules.exports.domain.controle_comptable import residu_du_bulletin  # noqa: E402
from app.modules.exports.infrastructure.export_ecritures_comptables import ligne_od_du_bulletin  # noqa: E402
from app.modules.payroll.engine.corrections_manuelles import RegularisationCotisation  # noqa: E402
from app.modules.payslips.infrastructure.providers import payslip_generator_provider  # noqa: E402


def _cumuls_precedents(employee_id: str, year: int, month: int) -> dict | None:
    py, pm = (year, month - 1) if month > 1 else (year - 1, 12)
    res = (supabase.table("employee_schedules").select("cumuls")
           .match({"employee_id": employee_id, "year": py, "month": pm}).maybe_single().execute())
    return (res.data or {}).get("cumuls") if res else None


def _lignes(payslip_data: dict) -> list[dict]:
    return [l for r in payslip_data.get("cotisations_officielles") or [] for l in r.get("lignes") or []]


def _montants_dsn(payslip_data: dict) -> dict[str, float]:
    _, cotisations, _ = build_bases_and_cotisations(
        _lignes(payslip_data), brut=float(payslip_data.get("salaire_brut") or 0),
        period_start="2026-01-01", period_end="2026-01-31")
    sortie: dict[str, float] = {}
    for c in cotisations:
        sortie[c.code] = round(sortie.get(c.code, 0.0) + float(c.montant_patronal or 0), 2)
    return sortie


def _residu(payslip_data: dict, employee: dict) -> float:
    ligne = ligne_od_du_bulletin(payslip_id="theoreme", employee=employee, payslip_data=payslip_data,
                                 saisies_du_salarie=[], compte_de_saisie=lambda _t: "421000")
    return residu_du_bulletin(ligne)


def _regularisation(ligne: dict) -> RegularisationCotisation:
    taux_s, taux_p = ligne.get("taux_salarial") or None, ligne.get("taux_patronal") or None
    commun = dict(coti_id=ligne["coti_id"], libelle=ligne["libelle"], motif="Test du théorème")
    if taux_s or taux_p:
        return RegularisationCotisation(**commun, base=10.0, taux_salarial=taux_s, taux_patronal=taux_p)
    return RegularisationCotisation(**commun, montant_patronal=-1.0 if ligne["coti_id"] == "reduction_generale" else 1.0)


def main(societe: str, year: int, month: int, sortie: str) -> int:
    company = supabase.table("companies").select("id").eq("company_name", societe).single().execute().data
    bulletins = (supabase.table("payslips").select("employee_id")
                 .match({"company_id": company["id"], "year": year, "month": month}).execute().data)
    rapport, echecs = [], 0
    for b in bulletins:
        emp = b["employee_id"]
        employee = supabase.table("employees").select("*").eq("id", emp).single().execute().data
        cumuls = _cumuls_precedents(emp, year, month)
        base = payslip_generator_provider.generate_en_bac_a_sable(emp, year, month, cumuls_precedents=cumuls)
        data0 = base["payslip_data"]
        dsn0, residu0 = _montants_dsn(data0), _residu(data0, employee)
        vus = set()
        for ligne in _lignes(data0):
            if not ligne.get("coti_id") or ligne.get("is_participation") or ligne.get("is_ppv"):
                continue
            if ligne["coti_id"] in vus:
                continue
            vus.add(ligne["coti_id"])
            regul = _regularisation(ligne)
            saisie = {**regul.saisie_du_mois({"employee_id": emp, "company_id": company["id"],
                                              "year": year, "month": month}), "id": "theoreme"}
            res = payslip_generator_provider.generate_en_bac_a_sable(
                emp, year, month, cumuls_precedents=cumuls, saisies_en_plus=(saisie,))
            data1 = res["payslip_data"]
            sal, pat = regul.montants()
            constats = {
                "ligne": any(l.get("regularisation") for l in _lignes(data1)),
                "total_salarial": abs(data1["structure_cotisations"]["total_salarial"]
                                      - data0["structure_cotisations"]["total_salarial"] - sal) < 0.005,
                "residu": abs(_residu(data1, employee) - residu0) < 0.005,
            }
            if ligne["coti_id"] == "reduction_generale":
                c0 = (base.get("cumuls") or {}).get("cumuls", {}).get("reduction_generale_patronale", 0)
                c1 = (res.get("cumuls") or {}).get("cumuls", {}).get("reduction_generale_patronale", 0)
                constats["cumul_reduction"] = abs(c1 - c0 - pat) < 0.005
            dsn1 = _montants_dsn(data1)
            ecart_dsn = round(sum(dsn1.values()) - sum(dsn0.values()), 2)
            constats["dsn"] = abs(ecart_dsn - round(sal + pat, 2)) <= 0.02
            ok = all(constats.values())
            echecs += 0 if ok else 1
            rapport.append({"salarie": emp, "coti_id": ligne["coti_id"], "ok": ok, **constats})
            print(("OK  " if ok else "ÉCHEC"), emp[:8], ligne["coti_id"], constats if not ok else "")
        # Gain et retenue de régularisation : des saisies ordinaires (primes ajoutées depuis le bulletin).
        periode = {"employee_id": emp, "company_id": company["id"], "year": year, "month": month}
        cas = {
            "gain soumis": ({**periode, "id": "theoreme-gain", "name": "Régularisation – gain", "amount": 10.0,
                             "is_socially_taxed": True, "is_taxable": True}, "brut", 10.0),
            "retenue sur le net": ({**periode, "id": "theoreme-retenue", "name": "Régularisation – retenue",
                                    "amount": -10.0, "sur_le_net": True, "is_socially_taxed": False,
                                    "is_taxable": False}, "net", -10.0),
        }
        for nom, (saisie, cle, attendu) in cas.items():
            res = payslip_generator_provider.generate_en_bac_a_sable(
                emp, year, month, cumuls_precedents=cumuls, saisies_en_plus=(saisie,))
            data1 = res["payslip_data"]
            champ = "salaire_brut" if cle == "brut" else "net_a_payer"
            constats = {
                cle: abs(float(data1[champ]) - float(data0[champ]) - attendu) < 0.005,
                "residu": abs(_residu(data1, employee) - residu0) < 0.005,
            }
            if cle == "brut":
                b0 = (base.get("cumuls") or {}).get("cumuls", {}).get("brut_total", 0)
                b1 = (res.get("cumuls") or {}).get("cumuls", {}).get("brut_total", 0)
                constats["cumul_brut"] = abs(b1 - b0 - attendu) < 0.005
            ok = all(constats.values())
            echecs += 0 if ok else 1
            rapport.append({"salarie": emp, "cas": nom, "ok": ok, **constats})
            print(("OK  " if ok else "ÉCHEC"), emp[:8], nom, constats if not ok else "")
    with open(sortie, "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=1)
    print(f"{len(rapport)} cas, {echecs} échec(s)")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]))
```

Le résultat du bac à sable porte `payslip_data` et `cumuls` (le fichier de cumuls du mois, avec sa clé `cumuls`), comme l'écrit `payslip_generator.py:1499`. La société se lit par `companies.company_name`.

- [ ] **Étape 2 : lancer le test du théorème sur les trois sociétés (en arrière-plan, sous `caffeinate -i`)**

```bash
cd backend && for s in "Colorplast" "Comitech Composite" "MAJI"; do PYTHONPATH=. caffeinate -i .venv/bin/python scripts/theoreme_correction_a_la_main.py "$s" 2026 9 "/Users/alex/dev/eywai-filet/theoreme-${s// /_}.json"; done
```

Attendu : `N cas, 0 échec(s)` pour chaque société, et aucune `EcritureInterdite`. Pour chaque échec, ouvrir le cas, trouver la cause et la corriger dans la tâche concernée (avec un test unitaire qui la reproduit), puis relancer. Ne jamais assouplir un contrôle pour le faire passer.

- [ ] **Étape 3 : commiter le script (sans les rapports, qui restent hors du dépôt)**

```bash
git add backend/scripts/theoreme_correction_a_la_main.py
git commit -m "test(paie): test du théorème de la correction à la main, au bac à sable sous piège à écritures : pour chaque bulletin et chaque cotisation, une régularisation injectée en mémoire change la ligne, le total salarial, le cumul de la réduction générale et la DSN d'autant, et le net se reconstruit"
```

---

### Tâche 11 : filet « après », suite complète, demande de déploiement

**Fichiers :** aucun nouveau.

- [ ] **Étape 1 : filet « après » (environ 20 min, en arrière-plan)**

```bash
caffeinate -i /Users/alex/dev/eywai-filet/lancer.sh /Users/alex/dev/eywai-filet/theoreme-apres HEAD
cd /Users/alex/dev/eywai-filet && /Users/alex/dev/EYWAI/backend/.venv/bin/python comparer5.py "theoreme-avant/apres_*.json" "theoreme-apres/apres_*.json"
```

Attendu : aucun écart, au centime, sur les quatre sociétés (garantie 1). Tout écart bloque la suite : il faut l'expliquer et le corriger.

- [ ] **Étape 2 : suite complète, une seule fois**

```bash
cd backend && .venv/bin/python -m pytest -q -x --ignore=tests/e2e
cd ../frontend && npx vitest run && npx tsc --noEmit -p .
```

Attendu : tout passe, sauf les deux tests unitaires connus pour l'environnement local.

- [ ] **Étape 3 : pousser la branche et vérifier la CI**

```bash
cd /Users/alex/dev/EYWAI && git push -u origin feat/theoreme-correction-etape-1 && gh run list --branch feat/theoreme-correction-etape-1 --limit 3
```

Attendu : la CI est verte.

- [ ] **Étape 4 : demander l'accord d'Alexandre pour le déploiement sur le site de test**

Ne rien lancer avant son accord. Avec son accord :
- appliquer la migration `20261018120000_monthly_inputs_correction_ligne.sql` sur la base de test (connecteur Supabase, `apply_migration`) ;
- déployer avec `gh workflow run deploy-test-env.yml --ref feat/theoreme-correction-etape-1` ;
- rejouer le parcours de bout en bout sur un salarié de MAJI créé pour l'occasion, puis le ranger : ajouter une régularisation, enregistrer, vérifier le bulletin (ligne, note PDF, net) et la liste de contrôle, retirer la régularisation, enregistrer.
