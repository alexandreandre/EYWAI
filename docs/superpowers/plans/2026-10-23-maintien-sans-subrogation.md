# Arrêt sans subrogation : IJSS déduites ou non — plan d'exécution

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> Sur ce chantier : exécution par `superpowers:executing-plans`, sans sous-agent (brief du 23/10).

**Goal :** un réglage société « sans subrogation : IJSS déduites ou non ». À `true`, un arrêt non subrogé ne verse que le complément : salaire garanti moins les IJSS des seuls jours maintenus et indemnisés par la CPAM. À `false`, ou sans arrêt non subrogé, rien ne bouge au centime ni à la clé.

**Architecture :** la colonne `company_maintenance_settings.deduire_ijss_sans_subrogation` (migration rejouable) passe par `get_maintenance_settings`, qui pose toujours la clé, jusqu'au moteur `maintien_salaire_service`. Le moteur relève les IJSS jour par jour (`_calculer_ijss`), garde les jours calendaires de la période de maintien, déduit leurs IJSS (estimées, ou part au prorata du montant validé) et pose `ijss_deduites` / `ijss_deduites_source` sur le maintien, seulement quand une déduction joue. Les textes (alerte, explication, mention PDF) vivent dans un module de domaine. L'empreinte ne voit la clé qu'à `true`.

**Tech Stack :** Python 3.11 (FastAPI, Pydantic v2, pytest), SQL Supabase, React + TypeScript (vitest, environnement node).

**Conception :** `docs/superpowers/specs/2026-10-23-maintien-sans-subrogation-design.md` (6c53297b). Elle fait foi.

## Global Constraints

- Réglage `false`, réglage absent du dict, ou bulletin sans arrêt non subrogé : bulletin identique au centime et clé pour clé ; aucune clé nouvelle sans déduction.
- L'empreinte ne change que si la ligne de réglages porte `true`.
- `test_sans_subrogation_pas_deduction_ijss` (tests/integration/legacy) reste vert, sans modification.
- Moteur : `settings.get("deduire_ijss_sans_subrogation", False)`. `get_maintenance_settings` : valeur de la ligne ; `false` si la colonne manque (avant migration) ; `true` sans ligne.
- Avec subrogation : rien ne change (le chemin avec subrogation est hors champ : un test de caractérisation, pas de code).
- Écran sans piège : succès confirmé, échec qui dit où corriger, aucun état silencieux. Textes en français simples ; le produit s'appelle « Martine ».
- Aucun nom de salarié dans le code, les tests ni les commits.
- Python 3.11 : aucune syntaxe propre à 3.12.
- Rien n'est poussé, déployé ni appliqué en base ; aucun bulletin régénéré.
- Commits : `feat(paie): …` / `fix(paie): …`, ligne vide, `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Tests backend, depuis `backend/` : `APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest …` (noté `PYTEST` ci-dessous).

## Fichiers

| Fichier | Rôle |
|---|---|
| `supabase/migrations/20261023120000_deduire_ijss_sans_subrogation.sql` | créer : colonne, `false` aux lignes existantes, défaut `true` |
| `backend/app/modules/maintenance_settings/schemas/{responses,requests}.py` | champ du réglage |
| `backend/app/modules/maintenance_settings/application/{queries,commands}.py` | défaut sans ligne, lecture avant migration, écriture |
| `backend/app/modules/payroll/domain/ijss_deduites.py` | créer : clés et textes (alerte, explication, mention PDF) |
| `backend/app/modules/payroll/engine/maintien_salaire_service.py` | IJSS par jour, jours maintenus, déduction, relevé du mois |
| `backend/app/modules/payroll/engine/controles_convention.py` | l'alerte enrichie reste non actionnable |
| `backend/app/modules/payroll/application/empreinte_entrees_service.py` | la clé n'entre qu'à `true` |
| `backend/app/modules/payroll/domain/explications_lignes.py` | explication de la ligne de maintien |
| `backend/app/modules/payroll/documents/bulletin_view.py` | mention sous la ligne de maintien |
| `backend/app/modules/ijss_tracking/application/service.py` | la règle de synchronisation, nommée |
| `frontend/src/api/maintenanceSettings.ts` | type |
| `frontend/src/features/company/components/ijssSansSubrogation.ts` | créer : choix et texte d'aide |
| `frontend/src/features/company/components/MaintenanceSettingsCard.tsx` | les deux boutons radio |

---

### Task 1 : le réglage, de la base à l'API

**Files :**
- Create : `supabase/migrations/20261023120000_deduire_ijss_sans_subrogation.sql`
- Modify : `backend/app/modules/maintenance_settings/schemas/responses.py`, `schemas/requests.py`, `application/queries.py`, `application/commands.py`
- Test : `backend/tests/unit/maintenance_settings/test_deduire_ijss.py`

**Interfaces :**
- Produces : `MaintenanceSettings.deduire_ijss_sans_subrogation: bool` (défaut `True`) ; `get_maintenance_settings(company_id)` pose toujours la clé ; `"deduire_ijss_sans_subrogation"` dans `commands._DB_WRITABLE_KEYS`.

- [ ] **Step 1 : tests qui échouent**

```python
"""Le réglage « sans subrogation : IJSS déduites ou non », de la ligne à l'écran.

Sans ligne de réglages, la règle légale (true). Une ligne existante garde le
calcul d'avant ce réglage : la migration la pose à false, et une ligne lue
avant la migration (sans la colonne) se lit false aussi.
"""

from __future__ import annotations

import pytest

from app.modules.maintenance_settings.application import commands, queries
from app.modules.maintenance_settings.schemas.requests import MaintenanceSettingsUpdate

pytestmark = pytest.mark.unit

SOCIETE = "aaaaaaaa-1111-1111-1111-111111111111"
CLE = "deduire_ijss_sans_subrogation"
LIGNE = {
    "id": "bbbbbbbb-2222-2222-2222-222222222222",
    "company_id": SOCIETE,
    "subrogation_mode": "never",
    "maintain_working_days": True,
}


def _lire(monkeypatch, ligne):
    monkeypatch.setattr(
        queries.maintenance_settings_repository, "get_by_company", lambda _cid: ligne
    )


def test_sans_ligne_la_regle_legale(monkeypatch):
    _lire(monkeypatch, None)
    assert queries.get_maintenance_settings(SOCIETE).deduire_ijss_sans_subrogation is True


def test_une_ligne_lue_avant_la_migration_garde_le_calcul_d_aujourd_hui(monkeypatch):
    _lire(monkeypatch, dict(LIGNE))
    reglages = queries.get_maintenance_settings(SOCIETE)
    assert reglages.deduire_ijss_sans_subrogation is False
    assert reglages.model_dump(mode="json")[CLE] is False


@pytest.mark.parametrize("valeur", [True, False])
def test_la_valeur_de_la_ligne_fait_foi(monkeypatch, valeur):
    _lire(monkeypatch, {**LIGNE, CLE: valeur})
    assert queries.get_maintenance_settings(SOCIETE).deduire_ijss_sans_subrogation is valeur


def _ecrire(monkeypatch, ligne):
    _lire(monkeypatch, ligne)
    ecrit: dict = {}

    def upsert(cid, data):
        ecrit.update(data)
        return {**data, "company_id": cid}

    monkeypatch.setattr(commands.maintenance_settings_repository, "upsert", upsert)
    return ecrit


def test_le_put_enregistre_le_choix(monkeypatch):
    ecrit = _ecrire(monkeypatch, {**LIGNE, CLE: False})
    sauve = commands.save_maintenance_settings(
        SOCIETE, MaintenanceSettingsUpdate(deduire_ijss_sans_subrogation=True)
    )
    assert ecrit[CLE] is True
    assert sauve.deduire_ijss_sans_subrogation is True


def test_un_autre_reglage_enregistre_ne_touche_pas_au_choix(monkeypatch):
    ecrit = _ecrire(monkeypatch, {**LIGNE, CLE: False})
    commands.save_maintenance_settings(SOCIETE, MaintenanceSettingsUpdate(employer_waiting_days=3))
    assert ecrit[CLE] is False


def test_une_premiere_ligne_prend_la_regle_legale(monkeypatch):
    ecrit = _ecrire(monkeypatch, None)
    commands.save_maintenance_settings(SOCIETE, MaintenanceSettingsUpdate(employer_waiting_days=3))
    assert ecrit[CLE] is True
```

- [ ] **Step 2 : les voir échouer** — `PYTEST tests/unit/maintenance_settings/test_deduire_ijss.py -q` → FAIL (`AttributeError` / champ inconnu `extra_forbidden`).

- [ ] **Step 3 : implémentation**

`schemas/responses.py`, après `maintain_parental_leave` :

```python
    #: Arrêt sans subrogation : la CPAM verse les IJSS au salarié. True : Martine
    #: ne verse que le complément, IJSS des jours maintenus déduites (règle
    #: légale, D1226-5). False : le salaire garanti en entier.
    deduire_ijss_sans_subrogation: bool = True
```

`schemas/requests.py`, après `maintain_parental_leave` : `deduire_ijss_sans_subrogation: Optional[bool] = None`.

`application/queries.py` : `deduire_ijss_sans_subrogation=True,` dans `_defaults` ; puis

```python
#: Colonne ajoutée le 23/10/2026. Une ligne lue avant la migration ne la porte
#: pas : c'est une société qui existait, elle garde le calcul d'avant (false),
#: comme la migration le pose.
_CLE_DEDUIRE_IJSS = "deduire_ijss_sans_subrogation"


def get_maintenance_settings(company_id: str) -> MaintenanceSettings:
    """Retourne la config ou les valeurs par défaut si aucune ligne."""
    raw = maintenance_settings_repository.get_by_company(company_id)
    if not raw:
        return _defaults(company_id)
    if _CLE_DEDUIRE_IJSS not in raw:
        raw = {**raw, _CLE_DEDUIRE_IJSS: False}
    return MaintenanceSettings.model_validate(raw)
```

`application/commands.py` : ajouter `"deduire_ijss_sans_subrogation",` à `_DB_WRITABLE_KEYS`.

Migration :

```sql
-- Arrêt sans subrogation : déduire ou non du maintien les IJSS des jours
-- maintenus, par société (conception du 23/10/2026).
--
-- Sans subrogation, la CPAM verse les IJSS directement au salarié.
--   true  : Martine ne verse que le complément, IJSS des jours maintenus et
--           indemnisés déduites (règle légale, Code du travail D1226-5) ;
--   false : le salaire garanti en entier, le calcul d'avant ce réglage.
-- Les sociétés qui ont déjà une ligne gardent leur calcul (false) ; une ligne
-- créée ensuite prend la règle légale (true).
--
-- Rejouable sans erreur et sans écraser un choix : la colonne naît sans
-- défaut, les lignes existantes (alors à null) passent à false, puis le défaut
-- true et le not null sont posés. Un second passage ne trouve plus de null.
-- À appliquer AVANT de déployer le code qui l'écrit : sans elle,
-- l'enregistrement des réglages de maintien échoue (colonne inconnue).

alter table public.company_maintenance_settings
  add column if not exists deduire_ijss_sans_subrogation boolean;

update public.company_maintenance_settings
  set deduire_ijss_sans_subrogation = false
  where deduire_ijss_sans_subrogation is null;

alter table public.company_maintenance_settings
  alter column deduire_ijss_sans_subrogation set default true;

alter table public.company_maintenance_settings
  alter column deduire_ijss_sans_subrogation set not null;

comment on column public.company_maintenance_settings.deduire_ijss_sans_subrogation is
  'Arrêt sans subrogation : true, le maintien ne verse que le complément (IJSS des jours maintenus déduites) ; false, le salaire garanti en entier.';
```

- [ ] **Step 4 : verts** — même commande, plus `PYTEST tests/unit/maintenance_settings tests/unit/payroll/test_conges_parentalite.py -q` → PASS.

- [ ] **Step 5 : commit** — `feat(paie): réglage « sans subrogation : IJSS déduites ou non », false pour les sociétés existantes`.

---

### Task 2 : le moteur, un arrêt

**Files :**
- Create : `backend/app/modules/payroll/domain/ijss_deduites.py`
- Modify : `backend/app/modules/payroll/engine/maintien_salaire_service.py` (`_calculer_ijss`, `_calculer_maintien_employeur`, `calculer_maintien`), `backend/app/modules/payroll/engine/controles_convention.py:29-32, 671, 745`
- Test : `backend/tests/unit/payroll/test_maintien_sans_subrogation.py`, `backend/tests/unit/payroll/test_controles_convention.py`

**Interfaces :**
- Consumes : la clé de Task 1 dans le dict `settings`.
- Produces :
  - `ijss_deduites.CLE_IJSS_DEDUITES = "ijss_deduites"`, `CLE_SOURCE = "ijss_deduites_source"`, `ALERTE_IJSS_AU_SALARIE = "IJSS versées directement au salarié"` ;
  - `alerte_ijss_au_salarie(maintien: Mapping | None) -> str`, `est_alerte_ijss_au_salarie(message: str) -> bool`, `explication_ijss_deduites(maintien) -> str | None`, `mention_ijss_deduites(maintien) -> str | None` ;
  - MSS : `CLE_DEDUIRE_IJSS`, `deduire_ijss_sans_subrogation(settings) -> bool`, `calculer_maintien(..., *, releve_ijss_du_mois: tuple[float, float, int] | None = None)` ; `maintien["ijss_deduites"]: float` et `maintien["ijss_deduites_source"]: "estimees" | "validees"`, posés seulement si la déduction est > 0.

**Règle :** un jour est maintenu s'il est un jour de carence payé, ou si son rang après la carence employeur porte un taux (légal ou conventionnel, selon la règle retenue pour la cible) — en jours calendaires, week-ends compris en jours ouvrés. Congé parental maintenu : tous les jours de l'arrêt dans la période. IJSS retenues = Σ IJSS estimées des jours maintenus et indemnisés ; montant validé V : V × (IJSS estimées des jours maintenus ÷ IJSS estimées de l'arrêt), ou au prorata des jours indemnisés si rien n'a pu être estimé. Versé = max(0, cible − IJSS retenues).

- [ ] **Step 1 : tests qui échouent** (`test_maintien_sans_subrogation.py`)

Chiffres de référence (mesurés sur le moteur) : arrêt du 05 au 20/06/2025, salaire 2 500 €, entrée 2021 → cible 665,68 €, IJSS 13 jours (08→20/06) 534,25 €, jours maintenus 12→20/06 → 9 × 41,0959 = 369,86 €.

```python
"""Arrêt sans subrogation : déduire du maintien les IJSS des jours maintenus, ou non.

Sans subrogation, la CPAM verse les IJSS au salarié. Réglage à true : Martine
ne verse que le complément « sous déduction des IJSS » (D1226-5), et seulement
celles des jours que l'employeur maintient et que la CPAM indemnise. Les IJSS
de la carence employeur (J4 à J7) restent au salarié ; sur des jours de carence
payés, la CPAM ne verse rien. Réglage à false ou absent : le salaire garanti en
entier, le calcul d'avant (conception du 23/10/2026).
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.payroll.documents.payslip_run_heures import _extraire_arret_pour_maintien
from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

CLE = "deduire_ijss_sans_subrogation"
JUIN = (date(2025, 6, 1), date(2025, 6, 30))
SEPTEMBRE = (date(2026, 9, 1), date(2026, 9, 30))
ALERTE = "IJSS versées directement au salarié"


def _ctx():
    return SimpleNamespace(
        salaire_base_mensuel=2500.0,
        baremes={"pss": {"annuel": 48000.0}},
        contrat={"contrat": {"date_entree": "2021-01-15"}},
    )


def _legal(**extra):
    return {
        "apply_legal_maintenance": True,
        "min_seniority_months": 12,
        "employer_waiting_days": 7,
        "seniority_extension_enabled": False,
        "remove_employer_waiting": False,
        "annual_unique_waiting": False,
        "maintain_100_percent": False,
        "differentiated_at_illness": False,
        "maintain_by_category": False,
        "no_seniority_condition": False,
        "custom_duration_days": None,
        "provident_relay_days": None,
        **extra,
    }


def _arret(**extra):
    return {
        "arret_type": "maladie_simple",
        "date_debut": "2025-06-05",
        "date_fin": "2025-06-20",
        "subrogation_active": False,
        "nombre_enfants": 0,
        "salaire_periode_reelle": 0.0,
        **extra,
    }


def _juin(arret=None, **reglages):
    return calculer_maintien(arret or _arret(), _ctx(), _legal(**reglages), *JUIN)


# --- Réglage éteint ou absent : rien ne change ------------------------------


def test_reglage_eteint_ou_absent_le_garanti_est_verse_en_entier():
    for reglages in ({}, {CLE: False}):
        r = _juin(**reglages)
        assert r["maintien"]["maintien_cible"] == 665.68
        assert r["maintien"]["maintien_verse"] == 665.68
        assert "ijss_deduites" not in r["maintien"]
        assert ALERTE in r["alertes"]


def test_reglage_eteint_le_resultat_est_identique_cle_pour_cle():
    assert _juin() == _juin(**{CLE: False})


def test_avec_subrogation_le_reglage_ne_change_rien():
    subroge = _arret(subrogation_active=True)
    assert _juin(subroge, **{CLE: True}) == _juin(subroge)


# --- Réglage allumé : les IJSS des seuls jours maintenus --------------------


def test_maintien_legal_seules_les_ijss_des_jours_maintenus_sont_deduites():
    r = _juin(**{CLE: True})
    m = r["maintien"]
    assert r["ijss"]["ijss_theorique"] == 534.25  # 13 jours, du 08 au 20/06
    assert m["maintien_cible"] == 665.68
    assert m["ijss_deduites"] == 369.86  # 9 jours maintenus, du 12 au 20/06
    assert m["ijss_deduites_source"] == "estimees"
    assert m["maintien_verse"] == 295.82  # et non 131,43
    assert m["complement_employeur"] == 295.82
    assert (
        "IJSS versées directement au salarié : 369,86 € déduites du maintien "
        "(estimées par Martine)"
    ) in r["alertes"]
    assert ALERTE not in r["alertes"]


def test_montant_valide_sa_part_des_jours_maintenus_au_prorata():
    r = _juin(_arret(ijss_brut_override=480.0), **{CLE: True})
    m = r["maintien"]
    assert r["ijss"]["ijss_theorique"] == 480.0
    assert m["ijss_deduites"] == 332.31  # 480 × 9/13
    assert m["ijss_deduites_source"] == "validees"
    assert m["maintien_verse"] == 333.37
    assert any("(montant validé dans le suivi IJSS)" in a for a in r["alertes"])


def test_plancher_a_zero_quand_les_ijss_depassent_le_garanti():
    m = _juin(_arret(ijss_brut_override=5000.0), **{CLE: True})["maintien"]
    assert m["maintien_verse"] == 0
    assert m["ijss_deduites"] == 665.68
    assert m["complement_employeur"] == 0


def test_un_arret_tout_dans_la_carence_employeur_n_a_rien_a_deduire():
    r = _juin(_arret(date_fin="2025-06-10"), **{CLE: True})
    assert r["ijss"]["ijss_theorique"] > 0  # du 08 au 10/06, au salarié
    assert r["maintien"]["maintien_verse"] == 0
    assert "ijss_deduites" not in r["maintien"]


# --- Plasturgie : jours ouvrés, « Jamais », carence payée (cas Colorplast) ---

PLASTURGIE = {
    "apply_legal_maintenance": False,
    "min_seniority_months": 10,
    "employer_waiting_days": 3,
    "subrogation_mode": "never",
    "paid_waiting_days_per_year": 3,
    "paid_waiting_min_seniority_months": 12,
    "maintain_working_days": True,
}


def _septembre(reglages, debut="2026-09-07", fin="2026-09-18"):
    contexte = build_test_contexte(
        salaire_base=1963.99, duree_hebdo=39.0, date_entree="2021-09-13",
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )
    jours = []
    d = date.fromisoformat(debut)
    while d <= date.fromisoformat(fin):
        jours.append({
            "date_complete": d.isoformat(),
            "type": "weekend" if d.weekday() >= 5 else "arret_maladie",
            "arret_type": "maladie_simple",
            "date_debut_arret_reel": debut,
            "date_fin_arret_reel": fin,
        })
        d = date.fromordinal(d.toordinal() + 1)
    arret = _extraire_arret_pour_maintien(jours, contexte, *SEPTEMBRE)
    arret["arrets_annee"] = [{"debut": debut, "fin": fin, "type": "maladie_simple"}]
    arret["arrets_connus"] = list(arret["arrets_annee"])
    return calculer_maintien(arret, contexte, dict(reglages), *SEPTEMBRE)


def test_carence_payee_seule_rien_n_est_deduit():
    for debut, fin in (("2026-09-07", "2026-09-18"), ("2026-09-01", "2026-09-30")):
        r = _septembre({**PLASTURGIE, CLE: True}, debut, fin)
        assert r["ijss"]["ijss_theorique"] > 0
        assert r["maintien"]["maintien_verse"] == pytest.approx(310.78, abs=0.01)
        assert "ijss_deduites" not in r["maintien"]
        assert r == _septembre(PLASTURGIE, debut, fin)


def test_jours_ouvres_jamais_avec_maintien_legal_les_week_ends_comptent():
    """Maintien légal dès J4 : du 10 au 18/09, week-end des 12 et 13 compris."""
    r = _septembre({**PLASTURGIE, "apply_legal_maintenance": True, CLE: True})
    m = r["maintien"]
    assert r["subrogation_active"] is False
    assert r["ijss"]["nb_jours_indemnises"] == 9
    assert m["ijss_deduites"] == r["ijss"]["ijss_theorique"]
    eteint = _septembre({**PLASTURGIE, "apply_legal_maintenance": True})["maintien"]
    assert m["maintien_cible"] == eteint["maintien_cible"]
    assert m["maintien_verse"] == pytest.approx(
        eteint["maintien_verse"] - r["ijss"]["ijss_theorique"], abs=0.01
    )


def test_caracterisation_avec_subrogation_carence_payee_seule():
    """Hors champ (conception § 6) : ce que fait AUJOURD'HUI le chemin subrogé.

    La subrogation retire toutes les IJSS de l'arrêt du maintien, sans plancher :
    sur la seule carence payée, le versé devient négatif, la ligne de maintien
    n'est pas posée et les 310,78 € de carence ne sont pas payés. Le réglage n'y
    change rien. Test de caractérisation : à revoir avec Alexandre, pas un
    comportement voulu.
    """
    subroge = {**PLASTURGIE, "subrogation_mode": "when_maintien"}
    for reglages in (subroge, {**subroge, CLE: True}):
        r = _septembre(reglages, "2026-09-01", "2026-09-30")
        assert r["subrogation_active"] is True
        assert r["maintien"]["maintien_cible"] == pytest.approx(310.78, abs=0.01)
        assert r["ijss"]["ijss_theorique"] == pytest.approx(871.69, abs=0.01)
        assert r["maintien"]["maintien_verse"] == pytest.approx(-560.91, abs=0.01)


# --- Congés de parentalité maintenus ----------------------------------------


def _ctx_parental():
    return SimpleNamespace(
        salaire_base_mensuel=4000.0,
        statut_salarie="Non-Cadre",
        baremes={
            "pss": {"annuel": 48060.0},
            "ij_plafonds": {"maladie": 42.97, "maternite_paternite": 104.02,
                            "at_mp": 240.49, "at_mp_majoree": 320.66},
        },
        contrat={"contrat": {"date_entree": "2021-08-01", "statut": "Non-Cadre"}},
    )


def test_conge_parental_maintenu_les_ij_de_tout_le_conge_sont_deduites():
    arret = {
        "arret_type": "maternite", "date_debut": "2026-09-07", "date_fin": "2026-09-30",
        "subrogation_active": False, "nombre_enfants": 0, "salaire_periode_reelle": 0.0,
    }
    reglages = _legal(maintain_parental_leave=True)
    allume = calculer_maintien(arret, _ctx_parental(), {**reglages, CLE: True}, *SEPTEMBRE)
    eteint = calculer_maintien(arret, _ctx_parental(), reglages, *SEPTEMBRE)
    ij = allume["ijss"]["ijss_theorique"]
    assert 0 < ij < eteint["maintien"]["maintien_verse"]
    assert allume["maintien"]["ijss_deduites"] == ij
    assert allume["maintien"]["maintien_verse"] == pytest.approx(
        eteint["maintien"]["maintien_verse"] - ij, abs=0.01
    )
```

Dans `test_controles_convention.py`, à côté du test existant de la ligne 221 : l'alerte enrichie (`"IJSS versées directement au salarié : 369,86 € déduites du maintien (estimées par Martine)"`) reste hors des alertes actionnables, comme la courte. Écrire le test sur le modèle du test existant (même appel, message remplacé).

- [ ] **Step 2 : les voir échouer** — `PYTEST tests/unit/payroll/test_maintien_sans_subrogation.py -q` : les tests « réglage allumé » échouent (pas de clé `ijss_deduites`), les autres passent déjà.

- [ ] **Step 3 : implémentation**

`domain/ijss_deduites.py` :

```python
"""IJSS déduites du maintien sans subrogation : clés et textes du bulletin.

Sans subrogation, la CPAM verse les IJSS au salarié. Quand la société les
déduit du maintien (réglage « Verser le complément, IJSS déduites »), le moteur
pose sur le maintien le montant déduit et sa source : estimées par Martine, ou
part du montant validé dans le suivi IJSS. Ces clés n'existent que si une
déduction a joué : les autres bulletins gardent leur forme.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

CLE_IJSS_DEDUITES = "ijss_deduites"
CLE_SOURCE = "ijss_deduites_source"
SOURCE_ESTIMEES = "estimees"
SOURCE_VALIDEES = "validees"

ALERTE_IJSS_AU_SALARIE = "IJSS versées directement au salarié"

_SOURCE_LONGUE = {
    SOURCE_ESTIMEES: "estimées par Martine",
    SOURCE_VALIDEES: "montant validé dans le suivi IJSS",
}
_SOURCE_COURTE = {SOURCE_ESTIMEES: "estimées", SOURCE_VALIDEES: "validées"}


def _euros(valeur: float) -> str:
    return f"{valeur:,.2f}".replace(",", " ").replace(".", ",") + " €"


def _nombre(valeur: Any) -> float:
    try:
        return float(valeur or 0.0)
    except (TypeError, ValueError):
        return 0.0


def montant_deduit(maintien: Optional[Mapping[str, Any]]) -> float:
    """Les IJSS déduites du maintien, 0 s'il n'y en a pas."""
    if not isinstance(maintien, Mapping):
        return 0.0
    return round(_nombre(maintien.get(CLE_IJSS_DEDUITES)), 2)


def _source(maintien: Mapping[str, Any]) -> str:
    source = maintien.get(CLE_SOURCE)
    return source if source in _SOURCE_LONGUE else SOURCE_ESTIMEES


def alerte_ijss_au_salarie(maintien: Optional[Mapping[str, Any]]) -> str:
    """L'alerte d'un arrêt sans subrogation ; elle dit la déduction quand elle joue."""
    deduites = montant_deduit(maintien)
    if deduites <= 0:
        return ALERTE_IJSS_AU_SALARIE
    return (
        f"{ALERTE_IJSS_AU_SALARIE} : {_euros(deduites)} déduites du maintien "
        f"({_SOURCE_LONGUE[_source(maintien)]})"
    )


def est_alerte_ijss_au_salarie(message: str) -> bool:
    texte = str(message or "").strip()
    return texte == ALERTE_IJSS_AU_SALARIE or texte.startswith(f"{ALERTE_IJSS_AU_SALARIE} :")


def explication_ijss_deduites(maintien: Optional[Mapping[str, Any]]) -> Optional[str]:
    """« D'où viennent ces lignes » : le garanti, moins les IJSS déduites."""
    deduites = montant_deduit(maintien)
    if deduites <= 0:
        return None
    garanti = round(_nombre(maintien.get("maintien_cible")), 2)
    return (
        f"Complément employeur : salaire garanti {_euros(garanti)} moins "
        f"{_euros(deduites)} d'IJSS versées par la CPAM au salarié "
        f"({_SOURCE_LONGUE[_source(maintien)]})"
    )


def mention_ijss_deduites(maintien: Optional[Mapping[str, Any]]) -> Optional[str]:
    """La note du PDF sous la ligne de maintien."""
    deduites = montant_deduit(maintien)
    if deduites <= 0:
        return None
    return f"dont IJSS déduites : {_euros(deduites)} ({_SOURCE_COURTE[_source(maintien)]})"
```

MSS — en tête, après les imports :

```python
from app.modules.payroll.domain.ijss_deduites import (
    CLE_IJSS_DEDUITES,
    CLE_SOURCE,
    SOURCE_ESTIMEES,
    SOURCE_VALIDEES,
    alerte_ijss_au_salarie,
)

#: Réglage société (23/10/2026) : sans subrogation, déduire du maintien les
#: IJSS des jours maintenus. Absent du dict : le calcul d'avant ce réglage ;
#: `get_maintenance_settings` pose toujours la clé.
CLE_DEDUIRE_IJSS = "deduire_ijss_sans_subrogation"

#: Relevé du mois pour plusieurs arrêts : (montant validé, IJSS estimées, jours indemnisés).
ReleveIjss = Tuple[float, float, int]


def deduire_ijss_sans_subrogation(settings: Dict[str, Any]) -> bool:
    return bool(settings.get(CLE_DEDUIRE_IJSS, False))
```

(`Tuple` ajouté à l'import `typing`.)

`_calculer_ijss` : paramètre `par_jour: Optional[Dict[date, float]] = None` ; dans la boucle, après `if is_tp: ijss_j *= quotite` :

```python
                if par_jour is not None:
                    par_jour[d] = ijss_j
```

Deux fonctions, avant `_calculer_maintien_employeur` :

```python
def _ijss_des_jours_maintenus(
    jours_maintenus: set,
    ijss: Dict[str, Any],
    ijss_par_jour: Dict[date, float],
    releve_du_mois: Optional[ReleveIjss],
) -> tuple[float, str]:
    """IJSS que la CPAM verse pour les jours que l'employeur maintient.

    Estimées : la somme des IJSS de ces jours. Montant validé au suivi IJSS :
    sa part pour ces jours, au prorata des IJSS estimées de l'arrêt (du mois
    pour plusieurs arrêts), ou des jours indemnisés si rien n'a pu être estimé.
    """
    jours = [d for d in ijss_par_jour if d in jours_maintenus]
    estimees = sum(ijss_par_jour[d] for d in jours)
    if releve_du_mois is None and not ijss.get("ijss_brut_override"):
        return estimees, SOURCE_ESTIMEES
    if releve_du_mois is not None:
        valide, estime_total, nb_total = releve_du_mois
    else:
        valide = float(ijss.get("ijss_theorique") or 0.0)
        estime_total = sum(ijss_par_jour.values())
        nb_total = len(ijss_par_jour)
    if estime_total > 0:
        part = estimees / estime_total
    elif nb_total > 0:
        part = len(jours) / nb_total
    else:
        part = 0.0
    return valide * part, SOURCE_VALIDEES


def _verse_sans_subrogation(
    maintien_cible: float,
    settings: Dict[str, Any],
    jours_maintenus: set,
    ijss: Dict[str, Any],
    ijss_par_jour: Optional[Dict[date, float]],
    releve_du_mois: Optional[ReleveIjss],
) -> tuple[float, Dict[str, Any]]:
    """Le maintien versé sans subrogation, et la déduction quand elle joue.

    Réglage éteint : le garanti en entier. Allumé : le garanti moins les IJSS
    des jours maintenus, plancher à 0 (D1226-5).
    """
    if ijss_par_jour is None or not deduire_ijss_sans_subrogation(settings):
        return maintien_cible, {}
    retenues, source = _ijss_des_jours_maintenus(
        jours_maintenus, ijss, ijss_par_jour, releve_du_mois
    )
    retenues = round(retenues, 2)
    if retenues <= 0 or maintien_cible <= 0:
        return maintien_cible, {}
    verse = max(0.0, maintien_cible - retenues)
    deduites = round(round(maintien_cible, 2) - round(verse, 2), 2)
    if deduites <= 0:
        return maintien_cible, {}
    return verse, {CLE_IJSS_DEDUITES: deduites, CLE_SOURCE: source}
```

`_calculer_maintien_employeur` : deux paramètres mot-clé `ijss_par_jour: Optional[Dict[date, float]] = None`, `releve_du_mois: Optional[ReleveIjss] = None`.
- Branche maternité : après le prorata temps partiel,

```python
        if bool(arret.get("subrogation_active")):
            maintien_verse_mat, deduction_mat = maintien_cible_mat, {}
        else:
            jours_mat = {inter_d + timedelta(days=k) for k in range(jours_intersection)}
            maintien_verse_mat, deduction_mat = _verse_sans_subrogation(
                maintien_cible_mat, settings, jours_mat, ijss, ijss_par_jour, releve_du_mois
            )
```
  puis `"maintien_verse": round(maintien_verse_mat, 2)`, `"complement_employeur": round(maintien_verse_mat - salaire_reel_mat, 2)`, et `**deduction_mat` en fin de dict.
- Boucle des jours : `jours_payes`, `jours_leg`, `jours_conv` (ensembles de dates). Le jour de carence payé va dans `jours_payes`. Avant le saut des week-ends :

```python
        jour = inter_d + timedelta(days=k)
        rang_maintien = jours_deja + offset + k + 1 - carence_emp_arret
        if rang_maintien >= 1:
            if apply_legal and _taux_legal_pour_jour_maintien(rang_maintien, duree_par_taux) > 0:
                jours_leg.add(jour)
            if taux_conv is not None and rang_maintien <= cap_conv and float(taux_conv) > 0:
                jours_conv.add(jour)
```
- Après le choix de la cible :

```python
    # Les jours maintenus, en jours calendaires, ceux de la règle retenue.
    if taux_conv is not None and (
        not apply_legal or maintien_total_conv >= maintien_total_legal - 1e-6
    ):
        jours_maintenus = jours_conv | jours_payes
    else:
        jours_maintenus = jours_leg | jours_payes
```
- Branche sans subrogation : `maintien_verse, deduction = _verse_sans_subrogation(maintien_cible, settings, jours_maintenus, ijss, ijss_par_jour, releve_du_mois)` ; `deduction = {}` dans la branche subrogée ; `**deduction` en fin du dict retourné.

`calculer_maintien(..., *, releve_ijss_du_mois: Optional[ReleveIjss] = None)` : `ijss_par_jour: Dict[date, float] = {}` passé à `_calculer_ijss(..., par_jour=ijss_par_jour)` ; les deux appels à `_calculer_maintien_employeur` reçoivent `ijss_par_jour=ijss_par_jour, releve_du_mois=releve_ijss_du_mois` ; l'alerte devient `alertes.append(alerte_ijss_au_salarie(maintien))`.

`controles_convention.py` : les deux tests `msg in _MAINTIEN_MESSAGES_NON_ACTIONNABLES_LISTE` deviennent `_maintien_non_actionnable(msg)` :

```python
def _maintien_non_actionnable(message: str) -> bool:
    """Les alertes du maintien qui informent sans rien demander."""
    return message in _MAINTIEN_MESSAGES_NON_ACTIONNABLES_LISTE or est_alerte_ijss_au_salarie(message)
```

- [ ] **Step 4 : verts** — `PYTEST tests/unit/payroll/test_maintien_sans_subrogation.py tests/unit/payroll/test_controles_convention.py tests/integration/legacy/test_maintien_salaire_service.py tests/unit/payroll -q -k "maintien or subrogation or parental or prolongation or carence or ijss or controles"` → PASS, legacy inchangé.

- [ ] **Step 5 : commit** — `feat(paie): sans subrogation, déduire du maintien les IJSS des seuls jours maintenus quand la société le choisit`.

---

### Task 3 : le moteur, plusieurs arrêts dans le mois

**Files :**
- Modify : `maintien_salaire_service._calculer_maintien_des_arrets_du_mois`
- Test : `backend/tests/unit/payroll/test_maintien_sans_subrogation.py`

**Interfaces :** Consumes `calculer_maintien(..., releve_ijss_du_mois=…)`, `CLE_IJSS_DEDUITES`, `CLE_SOURCE`, `alerte_ijss_au_salarie`, `est_alerte_ijss_au_salarie`.

Le relevé validé vaut pour le mois et reste porté par le premier arrêt (les autres à 0) : le chemin subrogé et l'affichage ne bougent pas. Pour la déduction, chaque arrêt reçoit le relevé du mois `(V, IJSS estimées de tous les arrêts, jours indemnisés de tous les arrêts)`, calculé par un premier passage sans relevé, seulement si le réglage est allumé et qu'un relevé existe. La fusion additionne les `ijss_deduites`, pose la source (`validees` si l'un l'est) et remplace les alertes « IJSS versées… » des arrêts par une seule, du mois.

- [ ] **Step 1 : tests qui échouent**

```python
# --- Deux arrêts dans le mois -----------------------------------------------


def _deux_arrets(reglages, override=None):
    contexte = build_test_contexte(
        salaire_base=1963.99, duree_hebdo=39.0, date_entree="2021-09-13",
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )
    jours = []
    for debut, fin in (("2026-09-01", "2026-09-11"), ("2026-09-21", "2026-09-30")):
        d = date.fromisoformat(debut)
        while d <= date.fromisoformat(fin):
            jours.append({
                "date_complete": d.isoformat(),
                "type": "weekend" if d.weekday() >= 5 else "arret_maladie",
                "arret_type": "maladie_simple",
                "date_debut_arret_reel": debut,
                "date_fin_arret_reel": fin,
            })
            d = date.fromordinal(d.toordinal() + 1)
    arret = _extraire_arret_pour_maintien(jours, contexte, *SEPTEMBRE)
    if override is not None:
        arret["ijss_brut_override"] = override
    return calculer_maintien(arret, contexte, dict(reglages), *SEPTEMBRE)


LEGAL_OUVRES = {**PLASTURGIE, "apply_legal_maintenance": True, "paid_waiting_days_per_year": None}


def test_deux_arrets_les_deductions_s_additionnent():
    r = _deux_arrets({**LEGAL_OUVRES, CLE: True})
    m = r["maintien"]
    par_arret = [a["maintien_verse"] for a in r["arrets_du_mois"]]
    assert len(par_arret) == 2
    assert m["ijss_deduites"] > 0
    assert m["ijss_deduites_source"] == "estimees"
    eteint = _deux_arrets(LEGAL_OUVRES)["maintien"]
    assert m["maintien_verse"] == pytest.approx(eteint["maintien_verse"] - m["ijss_deduites"], abs=0.01)
    assert len([a for a in r["alertes"] if a.startswith("IJSS versées")]) == 1


def test_deux_arrets_le_releve_valide_se_repartit_sur_le_mois():
    estime = _deux_arrets({**LEGAL_OUVRES, CLE: True})
    part = estime["maintien"]["ijss_deduites"] / estime["ijss"]["ijss_theorique"]
    r = _deux_arrets({**LEGAL_OUVRES, CLE: True}, override=600.0)
    assert r["ijss"]["ijss_theorique"] == 600.0
    assert r["maintien"]["ijss_deduites_source"] == "validees"
    assert r["maintien"]["ijss_deduites"] == pytest.approx(600.0 * part, abs=0.02)


def test_deux_arrets_reglage_eteint_identique_au_calcul_d_aujourd_hui():
    assert _deux_arrets({**LEGAL_OUVRES, CLE: False}, override=600.0) == _deux_arrets(
        LEGAL_OUVRES, override=600.0
    )
    assert "ijss_deduites" not in _deux_arrets(LEGAL_OUVRES)["maintien"]
```

- [ ] **Step 2 : les voir échouer** — `PYTEST tests/unit/payroll/test_maintien_sans_subrogation.py -q -k deux_arrets` → FAIL (alerte en double, relevé porté par le premier arrêt seul).

- [ ] **Step 3 : implémentation**

```python
def _releve_ijss_du_mois(
    arret: Dict[str, Any],
    segments: List[Dict[str, Any]],
    contexte: ContextePaie,
    settings: Dict[str, Any],
    date_debut_periode: date,
    date_fin_periode: date,
) -> Optional[ReleveIjss]:
    """Le relevé validé du mois et ce que Martine estime pour tous les arrêts.

    Seulement quand la déduction sans subrogation est allumée : sinon le relevé
    reste porté par le premier arrêt, comme avant.
    """
    override = arret.get("ijss_brut_override")
    if override is None or not deduire_ijss_sans_subrogation(settings):
        return None
    try:
        valide = float(override)
    except (TypeError, ValueError):
        return None
    if valide < 0:
        return None
    estimes = [
        calculer_maintien(
            {k: v for k, v in _arret_du_segment(arret, s).items() if k != "ijss_brut_override"},
            contexte, settings, date_debut_periode, date_fin_periode,
        )
        for s in segments
    ]
    return (
        valide,
        sum(float((r.get("ijss") or {}).get("ijss_theorique") or 0.0) for r in estimes),
        sum(int((r.get("ijss") or {}).get("nb_jours_indemnises") or 0) for r in estimes),
    )
```

Dans `_calculer_maintien_des_arrets_du_mois` : `releve = _releve_ijss_du_mois(arret, segments, contexte, settings, date_debut_periode, date_fin_periode)` avant la boucle ; `calculer_maintien(sous, ..., releve_ijss_du_mois=releve)`. Après la somme des montants du maintien :

```python
    deduites = round(sum(
        float((r.get("maintien") or {}).get(CLE_IJSS_DEDUITES) or 0.0) for r in resultats
    ), 2)
    maintien.pop(CLE_IJSS_DEDUITES, None)
    maintien.pop(CLE_SOURCE, None)
    if deduites > 0:
        maintien[CLE_IJSS_DEDUITES] = deduites
        maintien[CLE_SOURCE] = (
            SOURCE_VALIDEES
            if any((r.get("maintien") or {}).get(CLE_SOURCE) == SOURCE_VALIDEES for r in resultats)
            else SOURCE_ESTIMEES
        )
```

et, une fois `alertes` dédoublonnées, si `deduites > 0` : remplacer les alertes `est_alerte_ijss_au_salarie` par une seule `alerte_ijss_au_salarie(maintien)`, à la place de la première.

- [ ] **Step 4 : verts** — `PYTEST tests/unit/payroll/test_maintien_sans_subrogation.py tests/unit/payroll/test_prolongation_arret.py -q` → PASS.

- [ ] **Step 5 : commit** — `feat(paie): plusieurs arrêts sans subrogation dans le mois, le relevé IJSS validé se répartit sur le mois`.

---

### Task 4 : l'empreinte ne voit le réglage qu'allumé

**Files :** Modify `backend/app/modules/payroll/application/empreinte_entrees_service.py:512-513` ; Test `backend/tests/unit/payroll/test_empreinte_complementaire_service.py`.

- [ ] **Step 1 : tests qui échouent**

```python
def _arret_en_mai():
    return {
        **CALENDRIERS,
        (2026, 5): {
            "planned_calendar": {"calendrier_prevu": [
                {"jour": 12, "type": "arret_maladie", "heures": 0, "arret_type": "maladie"}]},
            "actual_hours": {"calendrier_reel": []},
        },
    }


def test_le_reglage_ijss_eteint_ne_change_pas_l_empreinte():
    avant = _du_mois(calendriers=_arret_en_mai())["reglages_societe"]
    eteint = {**COMPLEMENTS.maintien, "deduire_ijss_sans_subrogation": False}
    apres = _du_mois(replace(COMPLEMENTS, maintien=eteint), calendriers=_arret_en_mai())
    assert empreinte_partie(apres["reglages_societe"]) == empreinte_partie(avant)


def test_le_reglage_ijss_allume_ou_eteint_de_nouveau_un_mois_avec_arret_est_a_recalculer():
    eteint = {**COMPLEMENTS.maintien, "deduire_ijss_sans_subrogation": False}
    allume = {**COMPLEMENTS.maintien, "deduire_ijss_sans_subrogation": True}
    e = _du_mois(replace(COMPLEMENTS, maintien=eteint), calendriers=_arret_en_mai())
    a = _du_mois(replace(COMPLEMENTS, maintien=allume), calendriers=_arret_en_mai())
    assert empreinte_partie(e["reglages_societe"]) != empreinte_partie(a["reglages_societe"])


def test_le_reglage_ijss_allume_ne_touche_pas_un_mois_sans_arret():
    allume = {**COMPLEMENTS.maintien, "deduire_ijss_sans_subrogation": True}
    assert not _change("reglages_societe", maintien=allume)
```

- [ ] **Step 2 : échec** — `PYTEST tests/unit/payroll/test_empreinte_complementaire_service.py -q -k reglage_ijss` → le premier échoue (la clé `false` change l'empreinte).

- [ ] **Step 3 : implémentation**

```python
#: Réglage du 23/10/2026 : il n'entre dans l'empreinte qu'allumé. La migration
#: le pose à false partout ; sans ce filtre, tous les bulletins avec un arrêt
#: passeraient « À recalculer ».
_CLE_DEDUIRE_IJSS = "deduire_ijss_sans_subrogation"


def _maintien_pour_empreinte(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    reglage = _sans(row, _COLONNES_HORS_CALCUL | {_CLE_DEDUIRE_IJSS})
    if reglage is not None and row.get(_CLE_DEDUIRE_IJSS) is True:
        reglage[_CLE_DEDUIRE_IJSS] = True
    return reglage
```

et `parties["maintien"] = _maintien_pour_empreinte(complements.maintien)`.

- [ ] **Step 4 : verts** — `PYTEST tests/unit/payroll -q -k empreinte` → PASS.
- [ ] **Step 5 : commit** — `feat(paie): l'empreinte ne voit le réglage des IJSS sans subrogation qu'allumé`.

---

### Task 5 : l'explication à l'écran et la mention du PDF

**Files :** Modify `backend/app/modules/payroll/domain/explications_lignes.py` (`poser_explications`), `backend/app/modules/payroll/documents/bulletin_view.py` (`construire_lignes`) ; Test `backend/tests/unit/payroll/test_ijss_deduites_au_bulletin.py`.

- [ ] **Step 1 : tests qui échouent**

```python
"""Une déduction d'IJSS sans subrogation se lit au bulletin, à l'écran et au PDF."""

from __future__ import annotations

import pytest

from app.modules.payroll.documents import bulletin_view
from app.modules.payroll.domain.explications_lignes import poser_explications

pytestmark = pytest.mark.unit

LIGNE = {"libelle": "Maintien de salaire employeur", "quantite": None, "taux": None,
         "gain": 295.82, "perte": None, "is_maintien_employeur": True}


def _bulletin(maintien, ligne=None):
    return {
        "en_tete": {"annee": 2025, "mois": 6},
        "calcul_du_brut": [dict(ligne or LIGNE)],
        "bloc_maintien": {"maintien": maintien},
    }


DEDUIT = {"maintien_cible": 665.68, "maintien_verse": 295.82,
          "ijss_deduites": 369.86, "ijss_deduites_source": "estimees"}


def test_l_explication_dit_le_garanti_moins_les_ijss():
    b = poser_explications(_bulletin(DEDUIT))
    assert b["calcul_du_brut"][0]["explication"] == (
        "Complément employeur : salaire garanti 665,68 € moins 369,86 € d'IJSS "
        "versées par la CPAM au salarié (estimées par Martine)"
    )


def test_montant_valide_l_explication_le_dit():
    b = poser_explications(_bulletin({**DEDUIT, "ijss_deduites_source": "validees"}))
    assert b["calcul_du_brut"][0]["explication"].endswith("(montant validé dans le suivi IJSS)")


def test_sans_deduction_aucune_cle_nouvelle():
    b = poser_explications(_bulletin({"maintien_cible": 665.68, "maintien_verse": 665.68}))
    assert "explication" not in b["calcul_du_brut"][0]
    lignes = bulletin_view.construire_lignes(_bulletin({"maintien_verse": 665.68}))
    assert [l for l in lignes if l["type"] == "note"] == []


def test_le_pdf_porte_la_mention_sous_la_ligne_de_maintien():
    lignes = bulletin_view.construire_lignes(_bulletin(DEDUIT))
    i = next(i for i, l in enumerate(lignes) if l["libelle"] == "Maintien de salaire employeur")
    assert lignes[i + 1] == bulletin_view._ligne("note", "dont IJSS déduites : 369,86 € (estimées)")


def test_le_pdf_d_une_ligne_corrigee_a_la_main_ne_porte_pas_la_mention():
    corrigee = {**LIGNE, "correction": {"motif": "Relevé CPAM", "valeur_calculee": 295.82}}
    lignes = bulletin_view.construire_lignes(_bulletin(DEDUIT, corrigee))
    assert not any(l["libelle"].startswith("dont IJSS") for l in lignes)
```

- [ ] **Step 2 : échec** — `PYTEST tests/unit/payroll/test_ijss_deduites_au_bulletin.py -q` → FAIL.

- [ ] **Step 3 : implémentation**

`explications_lignes.py`, dans `poser_explications`, avant `_expliquer_corrections(bulletin)` : `_expliquer_ijss_deduites(bulletin)` ;

```python
def _expliquer_ijss_deduites(bulletin: dict[str, Any]) -> None:
    """Sans subrogation, IJSS déduites : la ligne de maintien dit le calcul."""
    from app.modules.payroll.domain.ijss_deduites import explication_ijss_deduites

    bloc = bulletin.get("bloc_maintien")
    texte = explication_ijss_deduites(bloc.get("maintien") if isinstance(bloc, Mapping) else None)
    if not texte:
        return
    for ligne in _lignes_de(bulletin, "calcul_du_brut"):
        if ligne.get("is_maintien_employeur"):
            _poser(ligne, texte)
```

`bulletin_view.py` : import `from app.modules.payroll.domain.ijss_deduites import mention_ijss_deduites` ; dans la boucle des lignes de brut de `construire_lignes` :

```python
            if isinstance(detail, dict):
                lignes.append(_ligne_brut(detail))
                mention = _mention_sous_la_ligne(bulletin, detail)
                if mention:
                    lignes.append(_ligne("note", mention))
```

```python
def _mention_sous_la_ligne(bulletin: Dict[str, Any], detail: Dict[str, Any]) -> Optional[str]:
    """Sous la ligne de maintien : les IJSS déduites sans subrogation.

    Une ligne corrigée à la main a sa propre note, après les cotisations.
    """
    if not detail.get("is_maintien_employeur") or isinstance(detail.get("correction"), dict):
        return None
    bloc = bulletin.get("bloc_maintien")
    return mention_ijss_deduites(bloc.get("maintien") if isinstance(bloc, dict) else None)
```

- [ ] **Step 4 : verts** — `PYTEST tests/unit/payroll -q -k "bulletin_view or explication or ijss_deduites or pdf"` → PASS.
- [ ] **Step 5 : commit** — `feat(paie): le bulletin et le PDF disent les IJSS déduites du maintien sans subrogation`.

---

### Task 6 : la règle du suivi IJSS, nommée et testée

Constat (relecture du 23/10) : `creer_bulletin_final` pose `synthese_net["ijss_subrogees"] = ijss_theorique` même sans subrogation (`engine/bulletin.py:653`). La synchronisation garde donc déjà ces bulletins dès que des IJSS sont estimées ; une déduction implique des IJSS > 0. Pas de changement de comportement : la règle devient une fonction nommée, avec la déduction écrite en clair.

**Files :** Modify `backend/app/modules/ijss_tracking/application/service.py:244-247` ; Test `backend/tests/unit/ijss_tracking/test_bulletins_suivis.py`.

- [ ] **Step 1 : test qui échoue**

```python
"""Quels bulletins ont leur ligne attendue au suivi IJSS."""

from __future__ import annotations

import pytest

from app.modules.ijss_tracking.application.service import bulletin_attend_des_ijss

pytestmark = pytest.mark.unit


def test_un_bulletin_subroge_a_sa_ligne():
    assert bulletin_attend_des_ijss({"synthese_net": {"subrogation_active": True}})


def test_un_bulletin_non_subroge_avec_ijss_deduites_a_sa_ligne():
    # Forme posée par le moteur : ijss_subrogees reprend les IJSS estimées.
    pdata = {
        "synthese_net": {"subrogation_active": False, "ijss_subrogees": 534.25},
        "bloc_maintien": {"maintien": {"ijss_deduites": 369.86, "ijss_deduites_source": "estimees"}},
    }
    assert bulletin_attend_des_ijss(pdata)
    pdata["synthese_net"].pop("ijss_subrogees")
    assert bulletin_attend_des_ijss(pdata)


def test_un_bulletin_sans_ijss_n_a_pas_de_ligne():
    assert not bulletin_attend_des_ijss({"synthese_net": {"subrogation_active": False}})
    assert not bulletin_attend_des_ijss({})
```

- [ ] **Step 2 : échec** — `PYTEST tests/unit/ijss_tracking/test_bulletins_suivis.py -q` → ImportError.

- [ ] **Step 3 : implémentation**

```python
def bulletin_attend_des_ijss(payslip_data: Dict[str, Any]) -> bool:
    """Le bulletin a sa ligne attendue au suivi IJSS.

    Subrogé, ou des IJSS sur le bulletin. Sans subrogation, `ijss_subrogees`
    reprend les IJSS estimées par Martine (engine/bulletin.py) : un arrêt
    indemnisé y figure déjà. Une déduction d'IJSS du maintien suffit aussi, pour
    que le vrai montant puisse y être saisi puis appliqué au bulletin.
    """
    pdata = payslip_data if isinstance(payslip_data, dict) else {}
    sn = pdata.get("synthese_net") or {}
    if float(sn.get("ijss_subrogees") or 0) > 0 or sn.get("subrogation_active"):
        return True
    maintien = (pdata.get("bloc_maintien") or {}).get("maintien") or {}
    return float(maintien.get("ijss_deduites") or 0) > 0
```

et dans `sync_expected_lines` : `if not bulletin_attend_des_ijss(pdata): continue` à la place du test inline (la variable `ijss` reste lue pour `ijss_subrogees_bulletin`).

- [ ] **Step 4 : verts** — `PYTEST tests/unit/ijss_tracking -q` → PASS.
- [ ] **Step 5 : commit** — `fix(paie): la règle du suivi IJSS dit qu'un arrêt sans subrogation avec IJSS déduites a sa ligne attendue`.

---

### Task 7 : l'écran

**Files :** Modify `frontend/src/api/maintenanceSettings.ts`, `frontend/src/features/company/components/MaintenanceSettingsCard.tsx` ; Create `frontend/src/features/company/components/ijssSansSubrogation.ts` ; Test `frontend/src/test/ijssSansSubrogation.test.ts`.

Préalable : `frontend/node_modules` absent du worktree → lien symbolique vers `/Users/alex/dev/EYWAI/frontend/node_modules` (lecture seule ; `node_modules` est ignoré par `frontend/.gitignore`).

- [ ] **Step 1 : test qui échoue**

```ts
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import {
  AIDE_IJSS_SANS_SUBROGATION,
  CHOIX_IJSS_SANS_SUBROGATION,
  choixIjssDepuisReglage,
  reglageDepuisChoixIjss,
} from "@/features/company/components/ijssSansSubrogation";

const SRC = path.resolve(__dirname, "..");
const lire = (rel: string) => readFileSync(path.join(SRC, rel), "utf8").replace(/\s+/g, " ");

describe("Réglage « sans subrogation : IJSS déduites ou non »", () => {
  it("propose les deux choix, dans les mots de la conception", () => {
    expect(CHOIX_IJSS_SANS_SUBROGATION.map((c) => [c.libelle, c.deduire])).toEqual([
      ["Verser le salaire garanti en entier", false],
      ["Verser le complément, IJSS déduites (règle légale)", true],
    ]);
  });

  it("le texte d'aide explique le choix", () => {
    expect(AIDE_IJSS_SANS_SUBROGATION).toBe(
      "Sans subrogation, la CPAM paie les IJSS directement au salarié. Martine peut les déduire du maintien, comme le prévoit la loi, ou verser le salaire garanti en entier."
    );
  });

  it("le bouton coché suit le réglage, et l'inverse", () => {
    expect(choixIjssDepuisReglage(true)).toBe("complement");
    expect(choixIjssDepuisReglage(false)).toBe("garanti");
    expect(reglageDepuisChoixIjss("complement")).toBe(true);
    expect(reglageDepuisChoixIjss("garanti")).toBe(false);
    expect(reglageDepuisChoixIjss("autre")).toBeNull();
  });

  it("la carte pose les deux boutons et l'aide sous le mode de subrogation, et enregistre le choix", () => {
    const t = lire("features/company/components/MaintenanceSettingsCard.tsx");
    expect(t).toContain("deduire_ijss_sans_subrogation: form.deduire_ijss_sans_subrogation");
    expect(t).toContain("CHOIX_IJSS_SANS_SUBROGATION.map");
    expect(t).toContain("{AIDE_IJSS_SANS_SUBROGATION}");
    expect(t.indexOf("Mode de subrogation")).toBeLessThan(t.indexOf("CHOIX_IJSS_SANS_SUBROGATION.map"));
    expect(t).toContain("Paramètres de maintien de salaire mis à jour.");
    expect(lire("api/maintenanceSettings.ts")).toContain("deduire_ijss_sans_subrogation: boolean;");
  });
});
```

- [ ] **Step 2 : échec** — `cd frontend && npx vitest run src/test/ijssSansSubrogation.test.ts` → FAIL (module introuvable).

- [ ] **Step 3 : implémentation**

`ijssSansSubrogation.ts` :

```ts
/** Réglage « sans subrogation : IJSS déduites ou non » (conception du 23/10/2026). */

export type ChoixIjssSansSubrogation = 'garanti' | 'complement';

export const CHOIX_IJSS_SANS_SUBROGATION: ReadonlyArray<{
  valeur: ChoixIjssSansSubrogation;
  libelle: string;
  deduire: boolean;
}> = [
  { valeur: 'garanti', libelle: 'Verser le salaire garanti en entier', deduire: false },
  { valeur: 'complement', libelle: 'Verser le complément, IJSS déduites (règle légale)', deduire: true },
];

export const AIDE_IJSS_SANS_SUBROGATION =
  'Sans subrogation, la CPAM paie les IJSS directement au salarié. Martine peut les déduire du maintien, comme le prévoit la loi, ou verser le salaire garanti en entier.';

export function choixIjssDepuisReglage(deduire: boolean): ChoixIjssSansSubrogation {
  return deduire ? 'complement' : 'garanti';
}

export function reglageDepuisChoixIjss(valeur: string): boolean | null {
  const choix = CHOIX_IJSS_SANS_SUBROGATION.find((c) => c.valeur === valeur);
  return choix ? choix.deduire : null;
}
```

`maintenanceSettings.ts` : `deduire_ijss_sans_subrogation: boolean;` (avec un commentaire) après `maintain_parental_leave`.

`MaintenanceSettingsCard.tsx` : import `RadioGroup, RadioGroupItem` et du module ; `deduire_ijss_sans_subrogation: form.deduire_ijss_sans_subrogation,` dans `toUpdatePayload` ; sous le bloc « Mode de subrogation » :

```tsx
            <div className="grid gap-2 max-w-md">
              <Label id="deduire_ijss_sans_subrogation">Arrêt sans subrogation</Label>
              <RadioGroup
                aria-labelledby="deduire_ijss_sans_subrogation"
                value={choixIjssDepuisReglage(form.deduire_ijss_sans_subrogation)}
                onValueChange={(v) => {
                  const deduire = reglageDepuisChoixIjss(v);
                  if (deduire === null) return;
                  setForm((p) => (p ? { ...p, deduire_ijss_sans_subrogation: deduire } : p));
                }}
                disabled={readOnly}
              >
                {CHOIX_IJSS_SANS_SUBROGATION.map((choix) => (
                  <div key={choix.valeur} className="flex items-center gap-2">
                    <RadioGroupItem value={choix.valeur} id={`deduire_ijss_${choix.valeur}`} />
                    <Label htmlFor={`deduire_ijss_${choix.valeur}`} className="font-normal cursor-pointer">
                      {choix.libelle}
                    </Label>
                  </div>
                ))}
              </RadioGroup>
              <p className="text-sm text-muted-foreground">{AIDE_IJSS_SANS_SUBROGATION}</p>
            </div>
```

L'enregistrement passe par le bouton « Enregistrer » de la carte : succès confirmé par le toast existant (« Enregistré — Paramètres de maintien de salaire mis à jour. »), échec par le toast d'erreur existant (détail du serveur).

- [ ] **Step 4 : verts** — `npx vitest run src/test/ijssSansSubrogation.test.ts src/test/lot37Ecrans.test.ts` → PASS.
- [ ] **Step 5 : commit** — `feat(paie): la carte « Maintien de salaire » propose de déduire ou non les IJSS sans subrogation`.

---

### Task 8 : suites complètes

- [ ] `PYTEST tests/unit -q` (une fois) et `PYTEST tests/integration/legacy/test_maintien_salaire_service.py -q`.
- [ ] `cd frontend && npm run typecheck && npm run lint && npx vitest run`.
- [ ] Rouges dus à l'environnement local (deux connus, APP_ENV) : les noter, ne pas les « corriger ».
- [ ] Compte rendu : commits, tests ajoutés, suites, migration, écarts, ce qui reste à jouer sur le site (migration sur la base de test avant déploiement, filet au centime, jeu de bout en bout chez MAJI).
