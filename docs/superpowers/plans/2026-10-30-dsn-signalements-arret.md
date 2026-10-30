# Signalements DSN d'arrêt et de reprise — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Martine liste les arrêts à signaler (nature 04) et les reprises anticipées (nature 05), avec la date limite, et génère le fichier `.dsn` à déposer à la main sur net-entreprises.

**Architecture:** Deux modules purs dans `dsn_export/domain` (rubriques permises par nature ; arrêts à signaler et dates limites), un constructeur de fichier dans `dsn_export/application`, une couche `exports/application/signalements.py` qui lit la base, génère, range le fichier et l'historique, deux routes, et une carte dans l'onglet Déclarations.

**Tech Stack:** Python 3.11 / FastAPI / Supabase (backend), React + TypeScript + react-query (frontend), pytest, vitest, DSN-VAL 2026.1 (local).

Spec : `docs/superpowers/specs/2026-10-30-dsn-signalements-arret-design.md`.

## Global Constraints

- Délai 04 : connu le + 5 jours calendaires ; en subrogation, l'échéance de la DSN mensuelle du mois de connaissance (le 15 du mois suivant sous 50 salariés, le 5 à partir de 50).
- Délai 05 : reprise + 5 jours ouvrables (dimanches sautés).
- Connu le = max(date de saisie de la première demande de la période, premier jour d'arrêt).
- Point de départ : arrêts commencés après le dernier mois de bulletins `origine = importe` de la société.
- Un essai ne vaut pas signalement fait.
- Fichier réel derrière `SIGNALEMENTS_DEPOSABLES = False` ; l'essai se génère toujours.
- Aucune valeur inventée : un champ manquant arrête la génération et le nomme.
- Dépôt public : aucun nom de salarié dans le code, les tests, les commits.
- Interpréteur backend : `backend/.venv/bin/python` ; tests depuis `backend/`.

---

### Task 1: Rubriques permises par nature

**Files:**
- Create: `backend/app/modules/dsn_export/domain/usages_signalement.py`
- Test: `backend/tests/unit/dsn_export/test_usages_signalement.py`

**Interfaces:**
- Produces: `NATURE_ARRET = "04"`, `NATURE_REPRISE = "05"`, `PERMISES: Dict[str, FrozenSet[str]]`, `filtrer(rubriques: Mapping[str, str], nature: str) -> Dict[str, str]` (lève `ValueError` sur une nature inconnue).

- [ ] **Step 1: Write the failing test**

```python
import pytest

from app.modules.dsn_export.domain.usages_signalement import (
    NATURE_ARRET,
    NATURE_REPRISE,
    filtrer,
)


def test_le_contrat_ne_garde_que_debut_numero_et_lieu():
    contrat = {
        "S21.G00.40.001": "01092026", "S21.G00.40.002": "04", "S21.G00.40.004": "674a",
        "S21.G00.40.007": "02", "S21.G00.40.009": "00001", "S21.G00.40.019": "80248516900011",
    }
    assert filtrer(contrat, NATURE_ARRET) == {
        "S21.G00.40.001": "01092026", "S21.G00.40.009": "00001",
        "S21.G00.40.019": "80248516900011",
    }


def test_la_subrogation_est_interdite_dans_une_reprise():
    arret = {"S21.G00.60.001": "01", "S21.G00.60.004": "01", "S21.G00.60.007": "FR76",
             "S21.G00.60.010": "13102026"}
    assert filtrer(arret, NATURE_REPRISE) == {"S21.G00.60.001": "01", "S21.G00.60.010": "13102026"}
    assert filtrer(arret, NATURE_ARRET)["S21.G00.60.004"] == "01"


def test_le_mois_principal_et_l_ape_sont_interdits():
    assert filtrer({"S20.G00.05.005": "01102026", "S21.G00.06.003": "2229A"}, NATURE_ARRET) == {}


def test_une_nature_inconnue_est_refusee():
    with pytest.raises(ValueError):
        filtrer({}, "07")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/dsn_export/test_usages_signalement.py -q`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Write minimal implementation**

```python
"""Rubriques permises dans un signalement d'arrêt (04) ou de reprise (05).

Tableau des usages du cahier technique DSN 2026.1 (fin du cahier,
`docs/audit-maji-2026/sources/dsn-cahier-technique-2026.1.txt`) : seules les
rubriques obligatoires ou conditionnelles de la nature s'écrivent ; les autres
y sont interdites, et DSN-VAL refuse le fichier qui les porte.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Mapping

NATURE_ARRET = "04"
NATURE_REPRISE = "05"

_COMMUNES = frozenset(
    """
    S10.G00.00.001 S10.G00.00.002 S10.G00.00.003 S10.G00.00.004 S10.G00.00.005
    S10.G00.00.006 S10.G00.00.007 S10.G00.00.008
    S10.G00.01.001 S10.G00.01.002 S10.G00.01.003 S10.G00.01.004 S10.G00.01.005
    S10.G00.01.006 S10.G00.01.007 S10.G00.01.008 S10.G00.01.009 S10.G00.01.010
    S10.G00.02.001 S10.G00.02.002 S10.G00.02.004 S10.G00.02.005 S10.G00.02.006
    S20.G00.05.001 S20.G00.05.002 S20.G00.05.003 S20.G00.05.004 S20.G00.05.006
    S20.G00.05.007 S20.G00.05.009
    S20.G00.07.001 S20.G00.07.002 S20.G00.07.003 S20.G00.07.004
    S21.G00.06.001 S21.G00.06.002
    S21.G00.11.001 S21.G00.11.003 S21.G00.11.004 S21.G00.11.005 S21.G00.11.006
    S21.G00.11.007
    S21.G00.15.001 S21.G00.15.002 S21.G00.15.003 S21.G00.15.005
    S21.G00.30.001 S21.G00.30.002 S21.G00.30.003 S21.G00.30.004 S21.G00.30.006
    S21.G00.30.019 S21.G00.30.020
    S21.G00.40.001 S21.G00.40.009 S21.G00.40.019
    S21.G00.60.001 S21.G00.60.002 S21.G00.60.003 S21.G00.60.010 S21.G00.60.011
    S21.G00.60.012 S21.G00.60.600
    """.split()
)
#: La subrogation se déclare à l'arrêt, jamais à la reprise.
_SUBROGATION = frozenset(
    {"S21.G00.60.004", "S21.G00.60.005", "S21.G00.60.006", "S21.G00.60.007", "S21.G00.60.008"}
)

PERMISES: Dict[str, FrozenSet[str]] = {
    NATURE_ARRET: _COMMUNES | _SUBROGATION,
    NATURE_REPRISE: _COMMUNES,
}


def filtrer(rubriques: Mapping[str, str], nature: str) -> Dict[str, str]:
    """Les rubriques du bloc permises dans un signalement de cette nature."""
    if nature not in PERMISES:
        raise ValueError(f"Nature de signalement inconnue : {nature}")
    permises = PERMISES[nature]
    return {code: valeur for code, valeur in rubriques.items() if code in permises}
```

- [ ] **Step 4: Run test to verify it passes** — same command, Expected: 4 passed.

- [ ] **Step 5: Commit** — `git commit -m "feat(dsn): rubriques permises dans un signalement d'arrêt ou de reprise"`

### Task 2: Arrêts à signaler et dates limites

**Files:**
- Modify: `backend/app/modules/dsn_export/domain/evenements.py` (extraire `dernier_jour_travaille`, utilisé par `blocs_arret`)
- Create: `backend/app/modules/dsn_export/domain/signalements.py`
- Test: `backend/tests/unit/dsn_export/test_signalements.py`

**Interfaces:**
- Consumes: `periodes_d_arret`, `MOTIFS_ACCIDENT` (evenements.py).
- Produces:
  - `dernier_jour_travaille(motif: str, debut: date, debut_contrat: Optional[date]) -> date` (evenements.py)
  - `@dataclass(frozen=True) SignalementEnvoye(employee_id: str, nature: str, motif: str, debut: date, fin_prevue: date, essai: bool, genere_le: date)`
  - `@dataclass(frozen=True) SignalementAFaire(employee_id: str, nature: str, motif: str, debut: date, fin_prevue: date, subrogation: bool, connu_le: date, a_deposer_avant: date, date_reprise: Optional[date] = None)`
  - `echeance_mensuelle(jour: date, effectif: int) -> date`
  - `ajouter_jours_ouvrables(jour: date, n: int) -> date`
  - `signalements_a_faire(arrets: Mapping[str, List[Dict[str, Any]]], envoyes: Iterable[SignalementEnvoye], *, depuis: Optional[date], effectif: int) -> List[SignalementAFaire]` — `arrets` : demandes validées par salarié, avec `type`, `selected_days`, `subrogation_active`, `arret_type`, `created_at`.

- [ ] **Step 1: Write the failing test**

```python
from datetime import date

from app.modules.dsn_export.domain.evenements import dernier_jour_travaille
from app.modules.dsn_export.domain.signalements import (
    SignalementEnvoye,
    ajouter_jours_ouvrables,
    echeance_mensuelle,
    signalements_a_faire,
)


def _arret(du, au, saisi, *, type_="arret_maladie", subrogation=False):
    jours = [date.fromordinal(o).isoformat() for o in range(du.toordinal(), au.toordinal() + 1)]
    return {"type": type_, "selected_days": jours, "subrogation_active": subrogation,
            "arret_type": None, "created_at": f"{saisi.isoformat()}T09:00:00+00:00"}


def _envoye(nature, debut, fin, *, essai=False, le=date(2026, 10, 6)):
    return SignalementEnvoye("e1", nature, "01", debut, fin, essai, le)


def test_un_arret_sans_subrogation_se_signale_sous_cinq_jours():
    (s,) = signalements_a_faire({"e1": [_arret(date(2026, 10, 5), date(2026, 10, 9), date(2026, 10, 6))]},
                                [], depuis=date(2026, 10, 1), effectif=20)
    assert (s.nature, s.debut, s.fin_prevue, s.connu_le) == ("04", date(2026, 10, 5), date(2026, 10, 9), date(2026, 10, 6))
    assert s.a_deposer_avant == date(2026, 10, 11)


def test_saisi_avant_l_arret_le_delai_part_du_premier_jour():
    (s,) = signalements_a_faire({"e1": [_arret(date(2026, 11, 2), date(2026, 11, 20), date(2026, 10, 20))]},
                                [], depuis=None, effectif=20)
    assert s.connu_le == date(2026, 11, 2)


def test_en_subrogation_le_signalement_suit_la_dsn_mensuelle():
    (s,) = signalements_a_faire({"e1": [_arret(date(2026, 10, 5), date(2026, 10, 9), date(2026, 10, 6), subrogation=True)]},
                                [], depuis=None, effectif=20)
    assert s.a_deposer_avant == date(2026, 11, 15)
    assert echeance_mensuelle(date(2026, 12, 3), 60) == date(2027, 1, 5)


def test_une_prolongation_ne_se_signale_pas():
    arrets = [_arret(date(2026, 10, 5), date(2026, 10, 9), date(2026, 10, 6)),
              _arret(date(2026, 10, 10), date(2026, 10, 20), date(2026, 10, 9))]
    assert len(signalements_a_faire({"e1": arrets}, [], depuis=None, effectif=20)) == 1


def test_un_arret_signale_ne_revient_pas_mais_un_essai_ne_compte_pas():
    arrets = {"e1": [_arret(date(2026, 10, 5), date(2026, 10, 9), date(2026, 10, 6))]}
    assert signalements_a_faire(arrets, [_envoye("04", date(2026, 10, 5), date(2026, 10, 9))], depuis=None, effectif=20) == []
    assert len(signalements_a_faire(arrets, [_envoye("04", date(2026, 10, 5), date(2026, 10, 9), essai=True)], depuis=None, effectif=20)) == 1


def test_une_reprise_avant_la_fin_declaree_demande_un_signalement_de_reprise():
    arrets = {"e1": [_arret(date(2026, 10, 5), date(2026, 10, 9), date(2026, 10, 6))]}
    (s,) = signalements_a_faire(arrets, [_envoye("04", date(2026, 10, 5), date(2026, 10, 16))], depuis=None, effectif=20)
    assert (s.nature, s.date_reprise, s.fin_prevue) == ("05", date(2026, 10, 10), date(2026, 10, 16))
    # Reprise le samedi 10/10 : dimanche 11 sauté, cinq jours ouvrables jusqu'au vendredi 16.
    assert s.a_deposer_avant == date(2026, 10, 16)
    assert signalements_a_faire(arrets, [_envoye("04", date(2026, 10, 5), date(2026, 10, 16)),
                                         _envoye("05", date(2026, 10, 5), date(2026, 10, 16))],
                                depuis=None, effectif=20) == []


def test_un_arret_d_avant_le_point_de_depart_appartient_a_l_ancien_logiciel():
    arrets = {"e1": [_arret(date(2026, 9, 1), date(2026, 10, 4), date(2026, 10, 1))]}
    assert signalements_a_faire(arrets, [], depuis=date(2026, 10, 1), effectif=20) == []


def test_le_jour_de_l_accident_est_travaille():
    assert dernier_jour_travaille("06", date(2026, 10, 5), None) == date(2026, 10, 5)
    assert dernier_jour_travaille("01", date(2026, 10, 5), None) == date(2026, 10, 4)
    assert dernier_jour_travaille("01", date(2026, 10, 5), date(2026, 10, 5)) == date(2026, 10, 5)


def test_jours_ouvrables():
    assert ajouter_jours_ouvrables(date(2026, 10, 10), 5) == date(2026, 10, 16)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/dsn_export/test_signalements.py -q`
Expected: FAIL (ImportError on `dernier_jour_travaille`)

- [ ] **Step 3: Write minimal implementation**

In `evenements.py`, add after `periodes_d_arret`:

```python
def dernier_jour_travaille(motif: str, debut: date, debut_contrat: Optional[date]) -> date:
    """La veille de l'arrêt, sauf accident ou maladie professionnelle : le jour
    de l'accident est travaillé (CT, 60.002) ; jamais avant le contrat (CCH-13)."""
    jour = debut if motif in MOTIFS_ACCIDENT else debut - timedelta(days=1)
    if debut_contrat and jour < debut_contrat:
        return debut_contrat
    return jour
```

and in `blocs_arret`, replace the computation of `dernier_jour` (the comment and the `if debut_contrat…` lines) by:

```python
        dernier_jour = dernier_jour_travaille(periode.motif, periode.debut, debut_contrat)
```

Create `signalements.py`:

```python
"""Arrêts à signaler (DSN 04) et reprises anticipées (DSN 05), avec leur date limite.

Cahier technique DSN 2026.1 : § 5.3 (arrêt : « dans les 5 jours après la prise
de connaissance », ou avec la DSN mensuelle en subrogation) ; § 5.4 (reprise :
« qu'en cas de reprise anticipée », « dans les cinq jours ouvrables qui suivent
la reprise »). Guide net-entreprises des arrêts : une prolongation ne se signale
pas, elle passe dans la DSN mensuelle. Fonctions pures.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Mapping, Optional

from app.modules.dsn_export.domain.evenements import _jours, periodes_d_arret
from app.modules.dsn_export.domain.usages_signalement import NATURE_ARRET, NATURE_REPRISE

#: À partir de 50 salariés, la DSN du mois M est due le 5 de M+1, sinon le 15.
SEUIL_ECHEANCE = 50


@dataclass(frozen=True)
class SignalementEnvoye:
    employee_id: str
    nature: str
    motif: str
    debut: date
    fin_prevue: date
    essai: bool
    genere_le: date


@dataclass(frozen=True)
class SignalementAFaire:
    employee_id: str
    nature: str
    motif: str
    debut: date
    fin_prevue: date
    subrogation: bool
    connu_le: date
    a_deposer_avant: date
    date_reprise: Optional[date] = None


def echeance_mensuelle(jour: date, effectif: int) -> date:
    annee, mois = (jour.year + 1, 1) if jour.month == 12 else (jour.year, jour.month + 1)
    return date(annee, mois, 5 if effectif >= SEUIL_ECHEANCE else 15)


def ajouter_jours_ouvrables(jour: date, n: int) -> date:
    """n jours ouvrables après ``jour`` : les dimanches ne comptent pas (les
    fériés comptent : c'est la lecture la plus stricte)."""
    while n > 0:
        jour += timedelta(days=1)
        if jour.weekday() != 6:
            n -= 1
    return jour


def _saisie(absence: Dict[str, Any]) -> Optional[date]:
    texte = str(absence.get("created_at") or "")[:10]
    try:
        return date.fromisoformat(texte)
    except ValueError:
        return None


def _connu_le(absences: List[Dict[str, Any]], debut: date, fin: date) -> date:
    saisies = [
        _saisie(a)
        for a in absences
        if (jours := _jours(a)) and debut <= jours[0] <= fin and _saisie(a)
    ]
    return max(min(saisies), debut) if saisies else debut


def signalements_a_faire(
    arrets: Mapping[str, List[Dict[str, Any]]],
    envoyes: Iterable[SignalementEnvoye],
    *,
    depuis: Optional[date],
    effectif: int,
) -> List[SignalementAFaire]:
    reels = [e for e in envoyes if not e.essai]
    resultat: List[SignalementAFaire] = []
    for employee_id, absences in arrets.items():
        for periode in periodes_d_arret(absences):
            if depuis and periode.debut < depuis:
                continue
            les_siens = [
                e for e in reels
                if e.employee_id == employee_id and e.motif == periode.motif and e.debut == periode.debut
            ]
            arrets_envoyes = [e for e in les_siens if e.nature == NATURE_ARRET]
            connu = _connu_le(absences, periode.debut, periode.fin)
            if not arrets_envoyes:
                limite = (
                    echeance_mensuelle(connu, effectif)
                    if periode.subrogation
                    else connu + timedelta(days=5)
                )
                resultat.append(SignalementAFaire(
                    employee_id, NATURE_ARRET, periode.motif, periode.debut, periode.fin,
                    periode.subrogation, connu, limite,
                ))
                continue
            declaree = max(arrets_envoyes, key=lambda e: e.genere_le).fin_prevue
            reprise_envoyee = any(e.nature == NATURE_REPRISE for e in les_siens)
            if periode.fin < declaree and not reprise_envoyee:
                reprise = periode.fin + timedelta(days=1)
                resultat.append(SignalementAFaire(
                    employee_id, NATURE_REPRISE, periode.motif, periode.debut, declaree,
                    periode.subrogation, connu, ajouter_jours_ouvrables(reprise, 5), reprise,
                ))
    return sorted(resultat, key=lambda s: (s.a_deposer_avant, s.employee_id))
```

- [ ] **Step 4: Run tests** — `.venv/bin/python -m pytest tests/unit/dsn_export/test_signalements.py tests/unit/dsn_export -q` ; Expected: all pass (the existing `blocs_arret` tests guard the extraction).

- [ ] **Step 5: Commit** — `git commit -m "feat(dsn): arrêts à signaler et reprises anticipées, avec leur date limite"`

### Task 3: Le fichier d'un signalement

**Files:**
- Modify: `backend/app/modules/dsn_export/domain/writer.py` (ajouter `ecrire_blocs`)
- Create: `backend/app/modules/dsn_export/application/signalement_builder.py`
- Test: `backend/tests/unit/dsn_export/test_signalement_builder.py`

**Interfaces:**
- Consumes: `build_envoi`, `build_entreprise`, `build_etablissement`, `DsnBuildError`, `_classification` (builder.py) ; `dsn`, `MOTIFS_ACCIDENT`, `dernier_jour_travaille` (evenements.py) ; `filtrer` (Task 1) ; `SignalementAFaire` (Task 2).
- Produces:
  - `ecrire_blocs(blocs: Sequence[Mapping[str, str]]) -> str` (writer.py) : chaque bloc par numéro croissant, puis le total S90.
  - `construire_signalement(company: Dict[str, Any], employee: Dict[str, Any], signalement: SignalementAFaire, *, settings: DsnSettings, essai: bool, constitue_le: date) -> str`

- [ ] **Step 1: Write the failing test**

```python
from datetime import date

import pytest

from app.modules.dsn_export.application.builder import DsnBuildError
from app.modules.dsn_export.application.signalement_builder import construire_signalement
from app.modules.dsn_export.domain.settings import DsnSettings
from app.modules.dsn_export.domain.signalements import SignalementAFaire

SOCIETE = {"siret": "80248516900011", "name": "Société test", "code_naf": "2229A",
           "address": {"rue": "1 rue du Test", "code_postal": "01100", "ville": "OYONNAX"}}
SALARIE = {"nir": "1900101234567", "last_name": "Testeur", "first_name": "Alix",
           "date_naissance": "1990-01-15", "hire_date": "2026-09-01", "matricule": "42",
           "classification_conventionnelle": {"numero_contrat_dsn": "00042"}}
REGLAGES = DsnSettings(versements=[{"organisme": "URSSAF", "iban": "FR7612345678901234567890123", "bic": "TESTFRPP"}])


def _signalement(nature="04", motif="01", subrogation=False, reprise=None):
    return SignalementAFaire("e1", nature, motif, date(2026, 10, 5), date(2026, 10, 16), subrogation,
                             date(2026, 10, 6), date(2026, 10, 11), reprise)


def _lignes(texte):
    return dict(l.split(",", 1) for l in texte.strip().splitlines())


def test_un_signalement_d_arret_maladie():
    r = _lignes(construire_signalement(SOCIETE, SALARIE, _signalement(), settings=REGLAGES,
                                       essai=True, constitue_le=date(2026, 10, 7)))
    assert r["S10.G00.00.005"] == "'01'"
    assert r["S20.G00.05.001"] == "'04'"
    assert r["S20.G00.05.007"] == "'07102026'"
    assert "S20.G00.05.005" not in r and "S21.G00.06.003" not in r
    assert r["S21.G00.30.001"] == "'1900101234567'" and r["S21.G00.30.002"] == "'TESTEUR'"
    assert r["S21.G00.40.009"] == "'00042'" and "S21.G00.40.007" not in r
    assert (r["S21.G00.60.001"], r["S21.G00.60.002"], r["S21.G00.60.003"], r["S21.G00.60.004"]) == (
        "'01'", "'04102026'", "'16102026'", "'02'")
    assert "S21.G00.60.012" not in r
    assert r["S90.G00.90.002"] == "'1'"


def test_un_accident_du_travail_porte_la_date_de_l_accident():
    r = _lignes(construire_signalement(SOCIETE, SALARIE, _signalement(motif="06"), settings=REGLAGES,
                                       essai=True, constitue_le=date(2026, 10, 7)))
    assert r["S21.G00.60.002"] == "'05102026'" and r["S21.G00.60.012"] == "'05102026'"


def test_la_subrogation_porte_les_dates_et_le_compte_de_l_employeur():
    r = _lignes(construire_signalement(SOCIETE, SALARIE, _signalement(subrogation=True), settings=REGLAGES,
                                       essai=True, constitue_le=date(2026, 10, 7)))
    assert (r["S21.G00.60.004"], r["S21.G00.60.005"], r["S21.G00.60.006"]) == ("'01'", "'05102026'", "'16102026'")
    assert r["S21.G00.60.007"] == "'FR7612345678901234567890123'" and r["S21.G00.60.008"] == "'TESTFRPP'"


def test_une_subrogation_sans_iban_ne_se_genere_pas():
    with pytest.raises(DsnBuildError, match="IBAN"):
        construire_signalement(SOCIETE, SALARIE, _signalement(subrogation=True), settings=DsnSettings(),
                               essai=True, constitue_le=date(2026, 10, 7))


def test_une_reprise_porte_sa_date_sans_subrogation():
    r = _lignes(construire_signalement(SOCIETE, SALARIE, _signalement(nature="05", subrogation=True, reprise=date(2026, 10, 10)),
                                       settings=REGLAGES, essai=False, constitue_le=date(2026, 10, 12)))
    assert r["S20.G00.05.001"] == "'05'" and r["S10.G00.00.005"] == "'02'"
    assert (r["S21.G00.60.010"], r["S21.G00.60.011"]) == ("'10102026'", "'01'")
    assert "S21.G00.60.004" not in r


@pytest.mark.parametrize("champ", ["nir", "date_naissance", "hire_date", "first_name"])
def test_un_champ_d_identite_manquant_arrete_tout(champ):
    with pytest.raises(DsnBuildError):
        construire_signalement(SOCIETE, {**SALARIE, champ: None}, _signalement(), settings=REGLAGES,
                               essai=True, constitue_le=date(2026, 10, 7))
```

- [ ] **Step 2: Run test to verify it fails** — `.venv/bin/python -m pytest tests/unit/dsn_export/test_signalement_builder.py -q` ; Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Write minimal implementation**

In `writer.py`, after `write_total_fichier`:

```python
def ecrire_blocs(blocs: Sequence[Mapping[str, str]]) -> str:
    """Un fichier fait de blocs déjà construits (signalements) : chaque bloc par
    numéro croissant, dans l'ordre donné, puis le bloc total."""
    out: List[str] = []
    for bloc in blocs:
        _emit_rubriques_dict(dict(bloc), out)
    write_total_fichier(out)
    return FIN_DE_LIGNE.join(out) + FIN_DE_LIGNE
```

(ajouter `Mapping` à l'import `typing` du fichier.)

Create `signalement_builder.py`:

```python
"""Le fichier d'un signalement d'arrêt (04) ou de reprise anticipée (05).

Les données identifiantes sont celles de la DSN mensuelle (cahier technique
2026.1, § 2.5.1 : sinon le signalement n'aboutit pas) : mêmes lectures de la
fiche, puis filtrage par les rubriques permises de la nature.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from app.modules.dsn_export.application.builder import (
    DsnBuildError,
    _classification,
    build_envoi,
    build_entreprise,
    build_etablissement,
)
from app.modules.dsn_export.domain.contract_map import iso_to_dsn_date
from app.modules.dsn_export.domain.evenements import MOTIFS_ACCIDENT, dernier_jour_travaille, dsn
from app.modules.dsn_export.domain.settings import DsnSettings
from app.modules.dsn_export.domain.signalements import SignalementAFaire
from app.modules.dsn_export.domain.usages_signalement import NATURE_ARRET, filtrer
from app.modules.dsn_export.domain.writer import ecrire_blocs


def _manque(champ: str) -> DsnBuildError:
    return DsnBuildError(f"Signalement impossible : {champ} manquant sur la fiche du salarié.")


def _individu(employee: Dict[str, Any]) -> Dict[str, str]:
    nir = str(employee.get("nir") or "").replace(" ", "")[:13]
    ntt = str(employee.get("ntt") or "")
    if not nir and not ntt:
        raise _manque("numéro de sécurité sociale")
    naissance = iso_to_dsn_date(employee.get("date_naissance") or employee.get("birth_date"))
    nom = str(employee.get("last_name") or "").upper()
    prenom = str(employee.get("first_name") or "").strip()
    for champ, valeur in (("nom", nom), ("prénom", prenom), ("date de naissance", naissance)):
        if not valeur:
            raise _manque(champ)
    rubriques = {
        "S21.G00.30.001": nir,
        "S21.G00.30.002": nom,
        "S21.G00.30.004": prenom,
        "S21.G00.30.006": naissance,
        "S21.G00.30.019": str(employee.get("matricule") or employee.get("time_tracking_id") or ""),
        "S21.G00.30.020": ntt,
    }
    if employee.get("nom_usage"):
        rubriques["S21.G00.30.003"] = str(employee["nom_usage"]).upper()
    return rubriques


def _contrat(employee: Dict[str, Any], siret: str) -> Dict[str, str]:
    debut = iso_to_dsn_date(employee.get("hire_date") or employee.get("date_entree"))
    if not debut:
        raise _manque("date d'embauche")
    classification = _classification(employee)
    numero = str(
        classification.get("numero_contrat_dsn")
        or employee.get("numero_contrat")
        or employee.get("contract_number")
        or "00000"
    )
    return {"S21.G00.40.001": debut, "S21.G00.40.009": numero, "S21.G00.40.019": siret[:14]}


def _arret(s: SignalementAFaire, debut_contrat: date | None, settings: DsnSettings) -> Dict[str, str]:
    rubriques = {
        "S21.G00.60.001": s.motif,
        "S21.G00.60.002": dsn(dernier_jour_travaille(s.motif, s.debut, debut_contrat)),
        "S21.G00.60.003": dsn(s.fin_prevue),
    }
    if s.motif in MOTIFS_ACCIDENT:
        # Martine n'a pas de champ « date de l'accident » : le premier jour de
        # l'arrêt, que la DSN mensuelle tient déjà pour le jour de l'accident.
        rubriques["S21.G00.60.012"] = dsn(max(s.debut, debut_contrat) if debut_contrat else s.debut)
    if s.nature == NATURE_ARRET:
        rubriques["S21.G00.60.004"] = "01" if s.subrogation else "02"
        if s.subrogation:
            compte = next((v for v in settings.versements if v.get("iban")), None)
            if not compte:
                raise DsnBuildError(
                    "Signalement impossible : subrogation sans IBAN de l'employeur "
                    "(réglages DSN, versements)."
                )
            rubriques.update({
                "S21.G00.60.005": dsn(s.debut),
                "S21.G00.60.006": dsn(s.fin_prevue),
                "S21.G00.60.007": str(compte.get("iban") or ""),
                "S21.G00.60.008": str(compte.get("bic") or ""),
            })
    else:
        rubriques["S21.G00.60.010"] = dsn(s.date_reprise)
        rubriques["S21.G00.60.011"] = "01"
    return rubriques


def construire_signalement(
    company: Dict[str, Any],
    employee: Dict[str, Any],
    signalement: SignalementAFaire,
    *,
    settings: DsnSettings,
    essai: bool,
    constitue_le: date,
) -> str:
    nature = signalement.nature
    individu = _individu(employee)
    entreprise = build_entreprise(company, settings=settings)
    etablissement = build_etablissement(company, entreprise, settings=settings)
    contrat = _contrat(employee, etablissement.siret)
    debut_contrat = date.fromisoformat(str(employee.get("hire_date") or employee.get("date_entree"))[:10])
    declaration = {
        "S20.G00.05.001": nature,
        "S20.G00.05.002": "01",
        "S20.G00.05.003": "11",
        "S20.G00.05.004": "1",
        "S20.G00.05.007": dsn(constitue_le),
    }
    contacts = [
        {
            "S20.G00.07.001": c.nom,
            "S20.G00.07.002": c.telephone,
            "S20.G00.07.003": c.email,
            "S20.G00.07.004": c.code_destinataire,
        }
        for c in settings.contacts_declaration
    ]
    blocs: List[Dict[str, str]] = [
        build_envoi(essai=essai, settings=settings).rubriques,
        declaration,
        *contacts,
        entreprise.rubriques,
        etablissement.rubriques,
        *(org.rubriques for org in etablissement.organismes_psc),
        individu,
        contrat,
        _arret(signalement, debut_contrat, settings),
    ]
    return ecrire_blocs([filtrer(bloc, nature) for bloc in blocs])
```

- [ ] **Step 4: Run tests** — `.venv/bin/python -m pytest tests/unit/dsn_export -q` ; Expected: all pass.

- [ ] **Step 5: Commit** — `git commit -m "feat(dsn): fichier de signalement d'arrêt et de reprise"`

### Task 4: Preuve DSN-VAL sur un vrai arrêt (lecture seule)

**Files:**
- Create (hors git) : `data/_outils/dsn-octobre/signalement.py`

- [ ] **Step 1: Write the script**

```python
"""Un signalement d'arrêt d'essai tiré d'un arrêt du test, passé à DSN-VAL. Lecture seule."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, "/Users/alex/dev/EYWAI/backend")
from scripts.verification_rgdu import piege  # noqa: E402

piege.poser_le_piege()
from app.core.database import supabase  # noqa: E402
from app.modules.dsn_export.application.signalement_builder import construire_signalement  # noqa: E402
from app.modules.dsn_export.domain.signalements import signalements_a_faire  # noqa: E402
from app.modules.dsn_export.infrastructure import settings_repository  # noqa: E402
from app.modules.exports.infrastructure.export_dsn import get_company_data  # noqa: E402
from scripts.dsn_valider import valider  # noqa: E402

COMITECH = "12cd8c71-da13-43f9-9151-475c4d5e8812"
arrets = supabase.table("absence_requests").select("employee_id,type,selected_days,subrogation_active,arret_type,created_at") \
    .eq("company_id", COMITECH).eq("status", "validated").like("type", "arret_%").execute().data
par = {}
for a in arrets:
    par.setdefault(str(a["employee_id"]), []).append(a)
s = signalements_a_faire(par, [], depuis=date(2026, 9, 1), effectif=20)[0]
employee = supabase.table("employees").select("*").eq("id", s.employee_id).single().execute().data
texte = construire_signalement(get_company_data(COMITECH), employee, s,
                               settings=settings_repository.charger(COMITECH), essai=True, constitue_le=date.today())
chemin = Path(sys.argv[1]) / "signalement-essai.dsn"
chemin.write_bytes(texte.encode("iso-8859-15"))
print(chemin, valider(chemin))
```

- [ ] **Step 2: Run it** — `cd backend && DSNVAL_HOME=~/dev/dsn-val/2026.1/app PYTHONPATH=. .venv/bin/python ../data/_outils/dsn-octobre/signalement.py <scratchpad>` ; Expected: 0 anomalie bloquante. Each refusal → corriger la Task 1 ou 3 (test d'abord), relancer.

### Task 5: Migration, verrou, couche exports et routes

**Files:**
- Create: `supabase/migrations/20261030120000_exports_history_dsn_signalement.sql`
- Modify: `backend/app/modules/dsn_export/domain/etat_conformite.py` (verrou)
- Create: `backend/app/modules/exports/application/signalements.py`
- Modify: `backend/app/modules/exports/api/router.py` (2 routes)
- Test: `backend/tests/unit/exports/test_signalements_service.py`

**Interfaces:**
- Consumes: Tasks 2 and 3 ; `get_company_data` (export_dsn.py) ; `settings_repository.charger` ; `effectif_retenu` ; `upload_export_file`, `create_signed_url`, `commands.record_export_history`, `BUCKET` (service.py imports).
- Produces:
  - `SIGNALEMENTS_DEPOSABLES: bool = False`, `RAISON_SIGNALEMENTS: str` (etat_conformite.py)
  - `EXPORT_TYPE = "dsn_signalement_arret"`
  - `lister(company_id: str, *, aujourd_hui: date | None = None) -> Dict[str, Any]` → `{"a_faire": [ligne], "faits": [ligne]}`, `ligne = {employee_id, salarie, nature, motif, debut, fin_prevue, subrogation, connu_le, a_deposer_avant, date_reprise, en_retard}` (dates ISO).
  - `generer(company_id: str, user_id: str, *, employee_id: str, nature: str, debut: str, essai: bool) -> Dict[str, Any]` → `{export_id, filename, download_url, message}` ; `ValueError` quand le signalement n'est plus à faire ou que le réel est verrouillé.
  - Routes : `GET /api/exports/dsn-signalements`, `POST /api/exports/dsn-signalements` (body `{employee_id, nature, debut, essai}`).

- [ ] **Step 1: Migration** — same content as `20261013010000_exports_history_dsn_hors_martine.sql`, with `'dsn_signalement_arret'` appended to the array and a header comment: « Signalements DSN d'arrêt et de reprise (30/10/2026) : chaque fichier généré est une ligne de l'historique des exports, ses paramètres disent le salarié, la nature, le motif, le début et la fin déclarée. »

- [ ] **Step 2: Write the failing test**

```python
from datetime import date
from unittest.mock import patch

import pytest

from app.modules.exports.application import signalements as service

MODULE = "app.modules.exports.application.signalements"


def _arret(du, au, saisi):
    jours = [date.fromordinal(o).isoformat() for o in range(du.toordinal(), au.toordinal() + 1)]
    return {"employee_id": "e1", "type": "arret_maladie", "selected_days": jours,
            "subrogation_active": False, "arret_type": None, "created_at": f"{saisi}T09:00:00+00:00"}


@pytest.fixture
def base():
    with patch(f"{MODULE}._arrets", return_value=[_arret(date(2026, 10, 5), date(2026, 10, 9), "2026-10-06")]), \
         patch(f"{MODULE}._envoyes", return_value=[]), \
         patch(f"{MODULE}._depuis", return_value=date(2026, 10, 1)), \
         patch(f"{MODULE}._effectif", return_value=20), \
         patch(f"{MODULE}._noms", return_value={"e1": "A. T."}):
        yield


def test_la_liste_dit_la_date_limite_et_le_retard(base):
    resultat = service.lister("c1", aujourd_hui=date(2026, 10, 12))
    (ligne,) = resultat["a_faire"]
    assert ligne["nature"] == "04" and ligne["a_deposer_avant"] == "2026-10-11"
    assert ligne["en_retard"] is True and ligne["salarie"] == "A. T."


def test_le_fichier_reel_reste_verrouille(base):
    with pytest.raises(ValueError, match="essai"):
        service.generer("c1", "u1", employee_id="e1", nature="04", debut="2026-10-05", essai=False)


def test_un_signalement_qui_n_est_plus_a_faire_est_refuse(base):
    with pytest.raises(ValueError, match="plus à faire"):
        service.generer("c1", "u1", employee_id="e1", nature="04", debut="2026-10-04", essai=True)


def test_l_essai_se_range_dans_l_historique(base):
    with patch(f"{MODULE}._fichier", return_value="S10.G00.00.001,'Martine Paie'\n"), \
         patch(f"{MODULE}.upload_export_file", return_value="exports/c1/x.dsn"), \
         patch(f"{MODULE}.create_signed_url", return_value="https://lien"), \
         patch(f"{MODULE}.commands.record_export_history", return_value="x1") as historique:
        resultat = service.generer("c1", "u1", employee_id="e1", nature="04", debut="2026-10-05", essai=True)
    enregistre = historique.call_args.args[0]
    assert enregistre["export_type"] == "dsn_signalement_arret" and enregistre["period"] == "2026-10"
    assert enregistre["parameters"] == {"employee_id": "e1", "nature": "04", "motif": "01",
                                        "debut": "2026-10-05", "fin_prevue": "2026-10-09",
                                        "subrogation": False, "date_reprise": None, "essai": True}
    assert resultat["download_url"] == "https://lien" and "mode test" in resultat["message"]
```

- [ ] **Step 3: Run it** — `.venv/bin/python -m pytest tests/unit/exports/test_signalements_service.py -q` ; Expected: FAIL (ImportError).

- [ ] **Step 4: Implement**

In `etat_conformite.py`, next to `DEPOSABLE`:

```python
#: Signalements d'arrêt et de reprise : verrou à part, un arrêt n'attend pas le
#: 15. Il s'ouvre sur décision d'Alexandre, après un essai passé à DSN-VAL sans
#: erreur bloquante et accepté en mode test sur net-entreprises.
SIGNALEMENTS_DEPOSABLES = False
RAISON_SIGNALEMENTS = (
    "Le fichier réel du signalement n'est pas encore ouvert : générez le fichier "
    "d'essai et déposez-le en mode test sur net-entreprises.fr."
)
```

Create `exports/application/signalements.py`:

```python
"""Signalements DSN d'arrêt et de reprise : la liste à faire, et la génération.

Les règles sont dans `dsn_export/domain/signalements.py` ; ici, la lecture de la
base, le rangement du fichier et l'historique des exports.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.core.database import supabase
from app.modules.dsn_export.application.signalement_builder import construire_signalement
from app.modules.dsn_export.domain import etat_conformite
from app.modules.dsn_export.domain.evenements import MOTIF_ARRET
from app.modules.dsn_export.domain.signalements import (
    SignalementAFaire,
    SignalementEnvoye,
    signalements_a_faire,
)
from app.modules.dsn_export.infrastructure import settings_repository
from app.modules.exports.application import commands
from app.modules.exports.infrastructure.export_dsn import get_company_data
from app.modules.exports.infrastructure.storage import create_signed_url, upload_export_file
from app.shared.domain.effectif_seuils import effectif_retenu

EXPORT_TYPE = "dsn_signalement_arret"
BUCKET = "exports"


def _arrets(company_id: str) -> List[Dict[str, Any]]:
    return (
        supabase.table("absence_requests")
        .select("employee_id,type,selected_days,subrogation_active,arret_type,created_at")
        .eq("company_id", company_id)
        .eq("status", "validated")
        .in_("type", sorted(MOTIF_ARRET))
        .execute()
    ).data or []


def _envoyes(company_id: str) -> List[SignalementEnvoye]:
    lignes = (
        supabase.table("exports_history")
        .select("parameters,created_at")
        .eq("company_id", company_id)
        .eq("export_type", EXPORT_TYPE)
        .execute()
    ).data or []
    envoyes = []
    for ligne in lignes:
        p = ligne.get("parameters") or {}
        envoyes.append(SignalementEnvoye(
            str(p.get("employee_id")), str(p.get("nature")), str(p.get("motif")),
            date.fromisoformat(p["debut"]), date.fromisoformat(p["fin_prevue"]),
            bool(p.get("essai")), date.fromisoformat(str(ligne["created_at"])[:10]),
        ))
    return envoyes


def _depuis(company_id: str) -> Optional[date]:
    """Le 1er du mois qui suit le dernier mois de bulletins repris d'un autre logiciel."""
    lignes = (
        supabase.table("payslips")
        .select("year,month")
        .eq("company_id", company_id)
        .eq("origine", "importe")
        .order("year", desc=True)
        .order("month", desc=True)
        .limit(1)
        .execute()
    ).data or []
    if not lignes:
        return None
    annee, mois = int(lignes[0]["year"]), int(lignes[0]["month"])
    return date(annee + 1, 1, 1) if mois == 12 else date(annee, mois + 1, 1)


def _effectif(company_id: str, annee: int) -> int:
    societe = supabase.table("companies").select("*").eq("id", company_id).single().execute().data
    return effectif_retenu(societe, annee).valeur or 0


def _noms(company_id: str) -> Dict[str, str]:
    lignes = (
        supabase.table("employees").select("id,first_name,last_name").eq("company_id", company_id).execute()
    ).data or []
    return {str(l["id"]): f"{l.get('first_name') or ''} {l.get('last_name') or ''}".strip() for l in lignes}


def _a_faire(company_id: str, aujourd_hui: date) -> List[SignalementAFaire]:
    par_salarie: Dict[str, List[Dict[str, Any]]] = {}
    for arret in _arrets(company_id):
        par_salarie.setdefault(str(arret["employee_id"]), []).append(arret)
    return signalements_a_faire(
        par_salarie, _envoyes(company_id),
        depuis=_depuis(company_id), effectif=_effectif(company_id, aujourd_hui.year),
    )


def _ligne(s: Any, noms: Dict[str, str], aujourd_hui: date) -> Dict[str, Any]:
    iso = lambda d: d.isoformat() if d else None  # noqa: E731
    return {
        "employee_id": s.employee_id, "salarie": noms.get(s.employee_id, ""),
        "nature": s.nature, "motif": s.motif, "debut": iso(s.debut), "fin_prevue": iso(s.fin_prevue),
        "subrogation": s.subrogation, "connu_le": iso(s.connu_le),
        "a_deposer_avant": iso(s.a_deposer_avant), "date_reprise": iso(s.date_reprise),
        "en_retard": s.a_deposer_avant < aujourd_hui,
    }


def lister(company_id: str, *, aujourd_hui: Optional[date] = None) -> Dict[str, Any]:
    jour = aujourd_hui or date.today()
    noms = _noms(company_id)
    faits = [
        {"employee_id": e.employee_id, "salarie": noms.get(e.employee_id, ""), "nature": e.nature,
         "motif": e.motif, "debut": e.debut.isoformat(), "fin_prevue": e.fin_prevue.isoformat(),
         "essai": e.essai, "genere_le": e.genere_le.isoformat()}
        for e in sorted(_envoyes(company_id), key=lambda e: e.genere_le, reverse=True)
    ]
    return {"a_faire": [_ligne(s, noms, jour) for s in _a_faire(company_id, jour)], "faits": faits}


def _fichier(company_id: str, s: SignalementAFaire, essai: bool) -> str:
    employee = supabase.table("employees").select("*").eq("id", s.employee_id).single().execute().data
    return construire_signalement(
        get_company_data(company_id), employee, s,
        settings=settings_repository.charger(company_id), essai=essai, constitue_le=date.today(),
    )


def generer(company_id: str, user_id: str, *, employee_id: str, nature: str, debut: str, essai: bool) -> Dict[str, Any]:
    if not essai and not etat_conformite.SIGNALEMENTS_DEPOSABLES:
        raise ValueError(etat_conformite.RAISON_SIGNALEMENTS)
    jour = date.today()
    s = next(
        (x for x in _a_faire(company_id, jour)
         if x.employee_id == employee_id and x.nature == nature and x.debut.isoformat() == debut),
        None,
    )
    if s is None:
        raise ValueError("Ce signalement n'est plus à faire : rechargez la liste.")
    contenu = _fichier(company_id, s, essai).encode("iso-8859-15")
    prefixe = "dsn_essai_signalement" if essai else "dsn_signalement"
    filename = f"{prefixe}_{nature}_{s.debut.isoformat()}_{datetime.now():%Y%m%d%H%M%S}.dsn"
    chemin = upload_export_file(
        BUCKET, f"exports/{company_id}/{EXPORT_TYPE}/{filename}", contenu, "text/plain; charset=iso-8859-15"
    )
    export_id = commands.record_export_history({
        "company_id": company_id,
        "export_type": EXPORT_TYPE,
        "period": s.debut.strftime("%Y-%m"),
        "parameters": {
            "employee_id": s.employee_id, "nature": s.nature, "motif": s.motif,
            "debut": s.debut.isoformat(), "fin_prevue": s.fin_prevue.isoformat(),
            "subrogation": s.subrogation,
            "date_reprise": s.date_reprise.isoformat() if s.date_reprise else None,
            "essai": essai,
        },
        "file_paths": [chemin],
        "report": {},
        "status": "generated",
        "generated_by": user_id,
    })
    limite = s.a_deposer_avant.strftime("%d/%m/%Y")
    message = (
        "Fichier d'essai : déposez-le en mode test sur net-entreprises.fr. Il ne vaut pas signalement."
        if essai
        else f"Déposez-le sur net-entreprises.fr avant le {limite}."
    )
    return {"export_id": export_id, "filename": filename,
            "download_url": create_signed_url(chemin, 3600), "message": message}
```

(Vérifier à l'implémentation le chemin réel de `upload_export_file` / `create_signed_url` / `BUCKET` dans les imports de `exports/application/service.py`, et le reprendre tel quel.)

In `router.py`, after `marquer_dsn_hors_martine`:

```python
class SignalementRequest(BaseModel):
    employee_id: str
    nature: str
    debut: str
    essai: bool = True


@router.get("/dsn-signalements")
def lister_signalements(
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    """Arrêts à signaler et reprises anticipées, avec la date limite ; signalements générés."""
    _require_exports_company_access(current_user, company_id)
    return signalements_service.lister(company_id)


@router.post("/dsn-signalements")
def generer_signalement(
    request: SignalementRequest,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    try:
        _require_exports_company_access(current_user, company_id)
        return signalements_service.generer(
            company_id, current_user.id, employee_id=request.employee_id,
            nature=request.nature, debut=request.debut, essai=request.essai,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise _value_error_to_http(e)
    except Exception:
        logger.exception("Échec de generer_signalement")
        raise HTTPException(status_code=500, detail="Le signalement n'a pas été généré : réessayez.")
```

with `from app.modules.exports.application import signalements as signalements_service` among the imports.

- [ ] **Step 5: Run tests** — `.venv/bin/python -m pytest tests/unit/exports tests/unit/dsn_export -q` ; Expected: all pass.

- [ ] **Step 6: Commit** — two commits: `feat(exports): signalements DSN d'arrêt à faire et générés, fichier réel verrouillé` (code + tests) and `feat(db): l'historique des exports accepte les signalements DSN` (migration).

### Task 6: La carte « Signalements d'arrêt »

**Files:**
- Modify: `frontend/src/api/exports.ts` (types et deux appels)
- Create: `frontend/src/components/exports/signalementsArret.ts` (+ `signalementsArret.test.ts`)
- Create: `frontend/src/components/exports/SignalementsArretCard.tsx`
- Modify: `frontend/src/components/exports/DeclarationsTab.tsx` (rendre la carte sous la grille)

**Interfaces:**
- Produces: `listerSignalements(): Promise<SignalementsResponse>`, `genererSignalement(body): Promise<SignalementGenere>` ; `libelleSignalement(ligne): string`, `echeance(ligne): { texte: string; urgent: boolean }`.

- [ ] **Step 1: Write the failing test** (`signalementsArret.test.ts`)

```ts
import { describe, expect, it } from 'vitest';
import { echeance, libelleSignalement } from './signalementsArret';

const ligne = {
  employee_id: 'e1', salarie: 'A. T.', nature: '04', motif: '01', debut: '2026-10-05',
  fin_prevue: '2026-10-09', subrogation: false, connu_le: '2026-10-06',
  a_deposer_avant: '2026-10-11', date_reprise: null, en_retard: false,
} as const;

describe('signalements d’arrêt', () => {
  it('dit l’arrêt en mots simples', () => {
    expect(libelleSignalement(ligne)).toBe('Arrêt maladie du 05/10/2026 au 09/10/2026');
    expect(libelleSignalement({ ...ligne, nature: '05', date_reprise: '2026-10-08' })).toBe(
      'Reprise anticipée le 08/10/2026 (arrêt maladie du 05/10/2026)',
    );
  });
  it('dit la date limite, en urgence une fois dépassée', () => {
    expect(echeance(ligne)).toEqual({ texte: 'À déposer avant le 11/10/2026', urgent: false });
    expect(echeance({ ...ligne, en_retard: true })).toEqual({ texte: 'En retard : à déposer avant le 11/10/2026', urgent: true });
  });
});
```

- [ ] **Step 2: Run** — `npx vitest run src/components/exports/signalementsArret.test.ts` (depuis `frontend/`) ; Expected: FAIL.

- [ ] **Step 3: Implement**

`signalementsArret.ts`:

```ts
import type { SignalementLigne } from '@/api/exports';

const MOTIFS: Record<string, string> = {
  '01': 'maladie', '02': 'maternité', '03': 'paternité', '04': 'accident de trajet',
  '05': 'maladie professionnelle', '06': 'accident du travail', '09': 'adoption',
};

const jour = (iso: string) => iso.split('-').reverse().join('/');

export function libelleSignalement(l: SignalementLigne): string {
  const arret = `arrêt ${MOTIFS[l.motif] ?? l.motif} du ${jour(l.debut)}`;
  if (l.nature === '05' && l.date_reprise) return `Reprise anticipée le ${jour(l.date_reprise)} (${arret})`;
  return `A${arret.slice(1)} au ${jour(l.fin_prevue)}`;
}

export function echeance(l: SignalementLigne): { texte: string; urgent: boolean } {
  const texte = `À déposer avant le ${jour(l.a_deposer_avant)}`;
  return l.en_retard ? { texte: `En retard : ${texte.charAt(0).toLowerCase()}${texte.slice(1)}`, urgent: true } : { texte, urgent: false };
}
```

`api/exports.ts` (ajouts) :

```ts
export interface SignalementLigne {
  employee_id: string; salarie?: string; nature: '04' | '05' | string; motif: string;
  debut: string; fin_prevue: string; subrogation: boolean; connu_le: string;
  a_deposer_avant: string; date_reprise: string | null; en_retard: boolean;
}
export interface SignalementFait {
  employee_id: string; salarie: string; nature: string; motif: string; debut: string;
  fin_prevue: string; essai: boolean; genere_le: string;
}
export interface SignalementsResponse { a_faire: SignalementLigne[]; faits: SignalementFait[] }
export interface SignalementGenere { export_id: string; filename: string; download_url: string; message: string }

export async function listerSignalements(): Promise<SignalementsResponse> {
  const response = await apiClient.get('/api/exports/dsn-signalements');
  return response.data;
}

export async function genererSignalement(body: {
  employee_id: string; nature: string; debut: string; essai: boolean;
}): Promise<SignalementGenere> {
  const response = await apiClient.post('/api/exports/dsn-signalements', body);
  return response.data;
}
```

`SignalementsArretCard.tsx` : une `Card` « Signalements d'arrêt » ; `useQuery(['dsn-signalements'], listerSignalements)` ; pendant le chargement « Chargement… », en erreur « La liste des signalements n'a pas pu être lue : réessayez. » avec un bouton « Réessayer » ; liste vide « Aucun arrêt à signaler. » ; chaque ligne : `salarie`, `libelleSignalement`, `echeance` (classe `text-destructive` si urgent), boutons « Fichier d'essai » (essai = true) et « Fichier réel » (essai = false). `useMutation(genererSignalement)` : au succès, ouvrir `download_url` (`window.open`), afficher `message` (toast existant du projet), invalider `['dsn-signalements']` ; en échec, afficher le `detail` de l'erreur (il dit le champ à compléter ou le verrou). Sous la liste, les 5 derniers `faits` : « Essai » ou « Déposé » + libellé + date de génération.

`DeclarationsTab.tsx` : `<SignalementsArretCard />` après la grille des exports.

- [ ] **Step 4: Run** — `npx vitest run src/components/exports && npx tsc --noEmit -p tsconfig.app.json && npx eslint src/components/exports src/api/exports.ts` ; Expected: pass, 0 erreur.

- [ ] **Step 5: Commit** — `feat(exports): carte « Signalements d'arrêt » dans les déclarations`

### Task 7: Vérification, push, notes

- [ ] Suites ciblées : `cd backend && .venv/bin/python -m pytest tests/unit/dsn_export tests/unit/exports tests/unit/net_entreprises -q` ; `cd frontend && npx vitest run src/components/exports`.
- [ ] Relancer la preuve DSN-VAL (Task 4) sur le code final.
- [ ] `git push origin feat/dsn-octobre` ; CI verte.
- [ ] Feuille de route (chantier 2) et mémoire : fait, preuve DSN-VAL, déploiement avec migration en attente de « déploie ».
