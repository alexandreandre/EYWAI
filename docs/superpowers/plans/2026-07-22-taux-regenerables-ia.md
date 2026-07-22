# Taux régénérables via IA — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre régénérables depuis l'UI (bouton + « régénérer tout / une section ») les taux `payroll_config` qui n'avaient ni source ni bouton, via des orchestrateurs IA mono-source human-gated, sans toucher aux scrapers existants.

**Architecture:** On réutilise à l'identique le chemin ALTERNANCE (dossier `scraping/<X>/` auto-contenu : `orchestrator.py` → `main_entry(SPEC)`, `spec.py`, `_logic.py`, `<X>_AI.py`). Deux helpers `core/` factorisent le boilerplate (signature/validation/merge côté spec ; extraction web côté AI). `tier="critical"` impose un *pending change* validé manuellement (aucune écriture directe). Le bouton UI et l'intégration « régénérer tout/section » s'activent par simple ajout dans `RATE_KEY_TO_SOURCE_KEYS` + une ligne `scraping_sources`.

**Tech Stack:** Python 3 (scraping subprocess), FastAPI (module rates), React/TS (front rates), Supabase (`payroll_config`, `scraping_sources`), OpenRouter/Sonar (`MODEL_WEB_SEARCH_PRO`).

## Global Constraints

- **Ne JAMAIS modifier** les orchestrateurs / scripts de scrapers existants (`scraping/SMIC/…`, `scraping/CSG/…`, etc.). Chaque nouveau taux est un ajout strictement isolé.
- **Human-gating obligatoire** : tous les nouveaux orchestrateurs ont `tier="critical"` et `dual_source_consensus=False` → *pending change*, jamais d'écriture directe.
- **Intégration « régénérer tout/section » garantie par construction** : ajouter le `config_key` à `RATE_KEY_TO_SOURCE_KEYS` suffit (`all_page_source_keys()` et le sync par section itèrent dessus). Aucun code UI additionnel.
- **Unités = fractions décimales** (0,10 = 10 %). Les schémas cibles du §5 du spec sont la forme exacte lue par le moteur ; `build_config_data` **fusionne** dans la config existante, ne reconstruit jamais.
- **Valeurs par défaut inchangées** : aucune régression paie tant qu'aucun pending n'est validé. Garder verts : payroll (~448 tests), MBC/Colorplast/Lewis.
- Spec de référence : `docs/superpowers/specs/2026-07-22-taux-regenerables-ia-design.md`.
- **Commande de test (macOS)** : préfixer TOUT pytest par `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` (les libs système WeasyPrint/cairo/pango sont dans `/opt/homebrew/lib`), avec l'interpréteur `.venv-ci/bin/pytest` depuis `backend/`. Ex : `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/pytest <chemin> -q`.
- **Git discipline** : chaque commit fait `git add <chemins EXACTS>` uniquement — JAMAIS `git add -A`/`-u`/`.`. NE JAMAIS toucher `backend/app/modules/payroll/engine/baremes_loader.py` ni `backend/tests/unit/payroll/test_baremes_loader.py` (travail VM non committé d'un tiers, présent dans le working tree).

---

### Task 1: Helpers génériques `core/` (spec-side + AI-side)

**Files:**
- Create: `backend/scraping/core/ai_scalar_spec.py`
- Create: `backend/scraping/core/ai_scalar_source.py`
- Test: `backend/tests/scraping/test_ai_scalar_spec.py`

**Interfaces:**
- Produces:
  - `build_ai_scalar_spec(*, scraper_name: str, config_key: str, ai_script_path: str, keys: list[str], bounds: dict[str, tuple[float, float]] | None = None, setters: dict[str, list[str]], comment: str, source_key: str | None = None, require_current: bool = True, validate=None, build=None) -> RateSpec`
  - `make_signature(keys)`, `make_signatures_equal(keys)`, `make_range_validator(bounds)`, `make_merge_builder(setters, require_current)`, `signature_for_emit(sig)`
  - `run_ai_scalar_source(*, source_id: str, libelle: str, schema: dict, schema_name: str, task_prompt: str, keys: list[str], generator: str, include_domains: list[str] | None = None, label: str | None = None) -> None`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/scraping/test_ai_scalar_spec.py
import sys
from pathlib import Path

SCRAPING = Path(__file__).resolve().parents[2] / "scraping"
if str(SCRAPING) not in sys.path:
    sys.path.insert(0, str(SCRAPING))

from core.ai_scalar_spec import build_ai_scalar_spec  # noqa: E402


def _spec():
    return build_ai_scalar_spec(
        scraper_name="DEMO",
        config_key="demo",
        ai_script_path="/tmp/demo_AI.py",
        keys=["a", "b"],
        bounds={"a": (0.0, 1.0), "b": (0.0, 1.0)},
        setters={"a": ["a"], "b": ["nested", "b"]},
        comment="demo",
    )


def test_signature_reads_valeurs():
    spec = _spec()
    sig = spec.extract_signature({"valeurs": {"a": 0.1, "b": 0.2}})
    assert sig == {"a": 0.1, "b": 0.2}


def test_equal_true_and_false():
    spec = _spec()
    assert spec.signatures_equal({"a": 0.1, "b": 0.2}, {"a": 0.1, "b": 0.2})
    assert not spec.signatures_equal({"a": 0.1, "b": 0.2}, {"a": 0.9, "b": 0.2})


def test_validate_rejects_out_of_range():
    spec = _spec()
    assert spec.validate_signature({"a": 0.5, "b": 0.5}).ok
    assert not spec.validate_signature({"a": 5.0, "b": 0.5}).ok


def test_merge_preserves_existing_and_sets_nested():
    spec = _spec()
    current = {"config_data": {"a": 0.0, "nested": {"b": 0.0, "keep": True}, "other": 1}}
    out = spec.build_config_data({"a": 0.1, "b": 0.2}, current)
    assert out["a"] == 0.1
    assert out["nested"]["b"] == 0.2
    assert out["nested"]["keep"] is True   # jamais reconstruit
    assert out["other"] == 1               # clés voisines préservées


def test_merge_requires_current_when_flagged():
    spec = _spec()
    import pytest
    with pytest.raises(ValueError):
        spec.build_config_data({"a": 0.1, "b": 0.2}, None)


def test_spec_is_human_gated_mono_source():
    spec = _spec()
    assert spec.tier == "critical"
    assert spec.dual_source_consensus is False
    assert spec.source_key == "DEMO"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/pytest tests/scraping/test_ai_scalar_spec.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.ai_scalar_spec'`

- [ ] **Step 3: Write `core/ai_scalar_spec.py`**

```python
# backend/scraping/core/ai_scalar_spec.py
"""Fabrique générique de RateSpec IA mono-source (scalaires, merge sûr)."""

from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.rate_spec import PersistenceMode, RateSpec, ScraperScript
from core.validation import ValidationResult, require_float_range, validate_all


def _payload_valeurs(payload: Dict[str, Any]) -> Dict[str, Any]:
    return payload.get("valeurs") or payload.get("sections") or {}


def make_signature(keys: List[str]) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    def core_signature(payload: Dict[str, Any]) -> Dict[str, Any]:
        v = _payload_valeurs(payload)
        return {k: v.get(k) for k in keys}

    return core_signature


def make_signatures_equal(
    keys: List[str], tol: float = 1e-9
) -> Callable[[Dict[str, Any], Dict[str, Any]], bool]:
    def signatures_equal(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        for k in keys:
            va, vb = a.get(k), b.get(k)
            if va is None or vb is None:
                if va is not vb:
                    return False
                continue
            if not math.isclose(float(va), float(vb), abs_tol=tol):
                return False
        return True

    return signatures_equal


def make_range_validator(
    bounds: Dict[str, Tuple[float, float]]
) -> Callable[[Dict[str, Any]], ValidationResult]:
    def validate(sig: Dict[str, Any]) -> ValidationResult:
        return validate_all(
            [
                (lambda k=k, lo=lo, hi=hi: require_float_range(
                    sig.get(k), name=k, min_v=lo, max_v=hi
                ))
                for k, (lo, hi) in bounds.items()
            ]
        )

    return validate


def make_merge_builder(
    setters: Dict[str, List[str]], *, require_current: bool = True
) -> Callable[[Dict[str, Any], Optional[Dict[str, Any]]], Dict[str, Any]]:
    """Fusionne les valeurs vérifiées dans la config existante (jamais reconstruite)."""

    def build(sig: Dict[str, Any], current: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        cur = (current or {}).get("config_data") if current else None
        if require_current and not isinstance(cur, dict):
            raise ValueError("Config active requise pour un merge sûr")
        data = copy.deepcopy(cur) if isinstance(cur, dict) else {}
        for key, path in setters.items():
            val = sig.get(key)
            if val is None:
                continue
            node = data
            for p in path[:-1]:
                sub = node.get(p)
                if not isinstance(sub, dict):
                    sub = {}
                    node[p] = sub
                node = sub
            node[path[-1]] = val
        return data

    return build


def signature_for_emit(sig: Dict[str, Any]) -> Dict[str, Any]:
    return dict(sig)


def build_ai_scalar_spec(
    *,
    scraper_name: str,
    config_key: str,
    ai_script_path: str,
    keys: List[str],
    setters: Dict[str, List[str]],
    comment: str,
    bounds: Optional[Dict[str, Tuple[float, float]]] = None,
    source_key: Optional[str] = None,
    require_current: bool = True,
    validate: Optional[Callable[[Dict[str, Any]], ValidationResult]] = None,
    build: Optional[
        Callable[[Dict[str, Any], Optional[Dict[str, Any]]], Dict[str, Any]]
    ] = None,
) -> RateSpec:
    script_name = Path(ai_script_path).name
    return RateSpec(
        scraper_name=scraper_name,
        config_key=config_key,
        scripts=[ScraperScript(script_name, ai_script_path, blocking=True)],
        extract_signature=make_signature(keys),
        signatures_equal=make_signatures_equal(keys),
        validate_signature=validate or make_range_validator(bounds or {}),
        build_config_data=build or make_merge_builder(setters, require_current=require_current),
        persistence_mode=PersistenceMode.FULL,
        comment=comment,
        primary_label=script_name,
        dual_source_consensus=False,
        warn_single_source=True,
        signature_for_emit=signature_for_emit,
        source_key=source_key or scraper_name,
        tier="critical",
    )
```

- [ ] **Step 4: Write `core/ai_scalar_source.py`**

```python
# backend/scraping/core/ai_scalar_source.py
"""Runner générique pour un AI script mono-source (émet le payload JSON standard)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.ai_extractor import extract_with_web_search, last_citation
from openrouter_client import MODEL_WEB_SEARCH_PRO

OFFICIAL_DEFAULT = [
    "boss.gouv.fr",
    "urssaf.fr",
    "service-public.fr",
    "legifrance.gouv.fr",
    "impots.gouv.fr",
]


def run_ai_scalar_source(
    *,
    source_id: str,
    libelle: str,
    schema: Dict[str, Any],
    schema_name: str,
    task_prompt: str,
    keys: List[str],
    generator: str,
    include_domains: Optional[List[str]] = None,
    label: Optional[str] = None,
) -> None:
    data = extract_with_web_search(
        task_prompt=task_prompt,
        json_schema=schema,
        schema_name=schema_name,
        include_domains=include_domains or OFFICIAL_DEFAULT,
        model=MODEL_WEB_SEARCH_PRO,
    )
    if not data or all(data.get(k) is None for k in keys):
        print(f"ERREUR CRITIQUE: extraction IA {source_id} échouée.", file=sys.stderr)
        sys.exit(1)

    cit = last_citation()
    payload = {
        "id": source_id,
        "type": "bareme",
        "libelle": libelle,
        "valeurs": {k: data.get(k) for k in keys},
        "meta": {
            "source": [
                {
                    "url": cit.get("url", ""),
                    "label": label or libelle,
                    "date_doc": cit.get("date", ""),
                }
            ],
            "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "generator": generator,
            "method": "ai_web_search",
        },
    }
    print(json.dumps(payload, ensure_ascii=False))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/pytest tests/scraping/test_ai_scalar_spec.py -q`
Expected: PASS (6 tests)

> Note: si `require_float_range`/`validate_all`/`ValidationResult` n'exposent pas `.ok`, adapter l'assert au champ réel (`.is_valid`/`.valid`) après lecture de `core/validation.py`. Vérifier la vraie API avant Step 1.

- [ ] **Step 6: Commit**

```bash
git add backend/scraping/core/ai_scalar_spec.py backend/scraping/core/ai_scalar_source.py backend/tests/scraping/test_ai_scalar_spec.py
git commit -m "feat(scraping): fabrique générique de spec IA mono-source pour taux scalaires"
```

---

### Task 2: Pilote — orchestrateur IA `taux_interet_legal`

**Files:**
- Create: `backend/scraping/taux_interet_legal/orchestrator.py`
- Create: `backend/scraping/taux_interet_legal/spec.py`
- Create: `backend/scraping/taux_interet_legal/taux_interet_legal_AI.py`
- Test: `backend/tests/scraping/test_taux_interet_legal_spec.py`

**Interfaces:**
- Consumes: `build_ai_scalar_spec`, `run_ai_scalar_source` (Task 1).
- Produces: dossier scraper exécutable via `python orchestrator.py`, `config_key="taux_interet_legal"`, `source_key="TAUX_INTERET_LEGAL"`.

- [ ] **Step 1: Write the failing test**

> **⚠ Pattern de test partagé (OBLIGATOIRE — évite une collision `sys.modules["spec"]`).**
> Ne JAMAIS faire `from spec import SPEC` dans un test : avec `--import-mode=importlib`,
> deux `test_<x>_spec.py` qui importent chacun le `spec.py` de leur dossier reçoivent
> le MÊME module `spec` (le premier collecté) → tests silencieusement faux. Créer une
> fois un helper qui charge chaque `spec.py` sous un nom unique, et l'utiliser partout :
>
> ```python
> # backend/tests/scraping/_spec_loader.py
> """Charge le SPEC d'un dossier scraper sous un nom de module unique.
>
> Évite la collision sys.modules["spec"] quand plusieurs test_<x>_spec.py
> chargent chacun le spec.py de leur dossier dans le même run pytest.
> """
> import importlib.util
> import sys
> from pathlib import Path
>
> SCRAPING = Path(__file__).resolve().parents[2] / "scraping"
> if str(SCRAPING) not in sys.path:
>     sys.path.insert(0, str(SCRAPING))  # pour que spec.py résolve `from core...`
>
>
> def load_spec(folder_name: str):
>     spec_path = SCRAPING / folder_name / "spec.py"
>     mod_name = f"_scraper_spec_{folder_name}"
>     spec = importlib.util.spec_from_file_location(mod_name, spec_path)
>     module = importlib.util.module_from_spec(spec)
>     sys.modules[mod_name] = module
>     spec.loader.exec_module(module)
>     return module.SPEC
> ```
>
> Et un `conftest.py` pour rendre `_spec_loader` importable sous `--import-mode=importlib`
> (ce mode n'ajoute PAS le dossier du test au `sys.path`) :
>
> ```python
> # backend/tests/scraping/conftest.py
> import sys
> from pathlib import Path
>
> _HERE = Path(__file__).resolve().parent
> _SCRAPING = _HERE.parents[1] / "scraping"
> for _p in (_HERE, _SCRAPING):
>     if str(_p) not in sys.path:
>         sys.path.insert(0, str(_p))
> ```

```python
# backend/tests/scraping/test_taux_interet_legal_spec.py
from _spec_loader import load_spec

SPEC = load_spec("taux_interet_legal")


def test_spec_identity():
    assert SPEC.config_key == "taux_interet_legal"
    assert SPEC.source_key == "TAUX_INTERET_LEGAL"
    assert SPEC.tier == "critical"


def test_signature_and_validation():
    sig = SPEC.extract_signature({"valeurs": {"taux_annuel": 0.0526}})
    assert sig == {"taux_annuel": 0.0526}
    assert SPEC.validate_signature({"taux_annuel": 0.0526}).ok
    assert not SPEC.validate_signature({"taux_annuel": 0.5}).ok  # 50 % = aberrant


def test_build_creates_flat_config():
    out = SPEC.build_config_data({"taux_annuel": 0.0526}, None)
    assert out == {"taux_annuel": 0.0526}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/pytest tests/scraping/test_taux_interet_legal_spec.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'spec'`)

- [ ] **Step 3: Write the three folder files**

```python
# backend/scraping/taux_interet_legal/orchestrator.py
#!/usr/bin/env python3
"""Orchestrateur TAUX_INTERET_LEGAL (IA mono-source, human-gated)."""
import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.base_orchestrator import main_entry
from spec import SPEC

if __name__ == "__main__":
    main_entry(SPEC)
```

```python
# backend/scraping/taux_interet_legal/spec.py
"""Spec TAUX_INTERET_LEGAL : taux d'intérêt légal annuel en vigueur (fraction)."""

from __future__ import annotations

from pathlib import Path

from core.ai_scalar_spec import build_ai_scalar_spec

_DIR = Path(__file__).resolve().parent

SPEC = build_ai_scalar_spec(
    scraper_name="TAUX_INTERET_LEGAL",
    config_key="taux_interet_legal",
    source_key="TAUX_INTERET_LEGAL",
    ai_script_path=str(_DIR / "taux_interet_legal_AI.py"),
    keys=["taux_annuel"],
    bounds={"taux_annuel": (0.0, 0.20)},
    setters={"taux_annuel": ["taux_annuel"]},
    require_current=False,  # config plate simple : création sûre
    comment="Mise à jour automatique: taux d'intérêt légal (IA web)",
)
```

```python
# backend/scraping/taux_interet_legal/taux_interet_legal_AI.py
#!/usr/bin/env python3
"""Source IA — taux d'intérêt légal en vigueur (recherche web sourcée)."""
import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.ai_scalar_source import run_ai_scalar_source  # noqa: E402

SCHEMA = {
    "type": "object",
    "properties": {"taux_annuel": {"type": ["number", "null"]}},
    "required": ["taux_annuel"],
    "additionalProperties": False,
}

if __name__ == "__main__":
    run_ai_scalar_source(
        source_id="taux_interet_legal",
        libelle="Taux d'intérêt légal",
        schema=SCHEMA,
        schema_name="taux_interet_legal",
        keys=["taux_annuel"],
        generator="taux_interet_legal/taux_interet_legal_AI.py",
        task_prompt=(
            "Taux d'intérêt légal EN VIGUEUR en France pour le semestre courant, "
            "cas général (créances entre professionnels / taux légal de référence). "
            "Réponds en FRACTION décimale annuelle (ex : 0.0526 pour 5,26 %). "
            "Sources officielles uniquement (Banque de France, service-public, "
            "Légifrance)."
        ),
        include_domains=[
            "banque-france.fr",
            "service-public.fr",
            "legifrance.gouv.fr",
        ],
        label="Banque de France — taux d'intérêt légal (IA web)",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/pytest tests/scraping/test_taux_interet_legal_spec.py -q`
Expected: PASS (3 tests)

- [ ] **Step 5: Smoke-test the orchestrator import (no network)**

Run: `cd backend/scraping && python -c "import sys; sys.path.insert(0,'.'); sys.path.insert(0,'taux_interet_legal'); import importlib.util as u; s=u.spec_from_file_location('spec','taux_interet_legal/spec.py'); m=u.module_from_spec(s); s.loader.exec_module(m); print(m.SPEC.config_key, m.SPEC.tier)"`
Expected: `taux_interet_legal critical`

- [ ] **Step 6: Commit**

```bash
git add backend/scraping/taux_interet_legal/ backend/tests/scraping/test_taux_interet_legal_spec.py
git commit -m "feat(scraping): orchestrateur IA taux d'intérêt légal (pilote)"
```

---

### Tasks 3–9 : les 7 autres taux scalaires

> Chaque tâche = **même structure que Task 2** (3 fichiers dossier + 1 test),
> seuls changent : `keys`, `bounds`, `setters`, `require_current`, le `SCHEMA`,
> le `task_prompt`, et l'URL de domaines. Le code complet des artefacts variables
> est donné ci-dessous, tâche par tâche. Répéter le squelette de Task 2 (Steps
> 1→6) en substituant les blocs.

Pour **chaque** tâche : `orchestrator.py` est **identique** à Task 2 (seul le
docstring et rien d'autre) ; `spec.py` appelle `build_ai_scalar_spec` avec les
params listés ; `<x>_AI.py` appelle `run_ai_scalar_source` avec le `SCHEMA`, les
`keys`, le `task_prompt` et `generator` listés. Test = `test_<x>_spec.py` calqué
sur Task 2 (identité, signature/validation dans/hors bornes, merge), **chargeant le
spec via `from _spec_loader import load_spec` puis `SPEC = load_spec("<dossier>")`**
(JAMAIS `from spec import SPEC` — collision `sys.modules`). Le helper `_spec_loader.py`
et le `conftest.py` de `tests/scraping/` sont créés en Task 2, réutilisés ensuite.

---

#### Task 3: `cdd` — prime de précarité + ICCP

- Dossier `scraping/cdd/`, source_key `CDD`.
- `spec.py` params :
  - `keys=["precarite_taux", "indemnite_conges_taux"]`
  - `bounds={"precarite_taux": (0.0, 0.15), "indemnite_conges_taux": (0.08, 0.12)}`
  - `setters={"precarite_taux": ["precarite", "taux"], "indemnite_conges_taux": ["indemnite_conges", "taux"]}`
  - `require_current=True` (préserve `precarite.actif`)
  - `comment="Mise à jour automatique: taux CDD (précarité, ICCP) (IA web)"`
- `SCHEMA` : propriétés `precarite_taux`, `indemnite_conges_taux` (`["number","null"]`), toutes `required`.
- `task_prompt` : « Contrat à durée déterminée (CDD) en France : 1) taux de l'indemnité de fin de contrat (prime de précarité), en FRACTION (ex : 0.10 pour 10 %). 2) taux de l'indemnité compensatrice de congés payés, en FRACTION (ex : 0.10). Sources officielles (service-public, Légifrance, Code du travail L1243-8). »
- `generator="cdd/cdd_AI.py"`.
- Test merge : `current={"config_data":{"precarite":{"taux":0.06,"actif":True},"indemnite_conges":{"taux":0.10}}}` → `out["precarite"]["taux"]==0.10` (valeur IA simulée), `out["precarite"]["actif"] is True`.

#### Task 4: `interim` — IFM + ICCP

- Dossier `scraping/interim/`, source_key `INTERIM`.
- `keys=["ifm_taux", "indemnite_conges_taux"]`
- `bounds={"ifm_taux": (0.0, 0.15), "indemnite_conges_taux": (0.08, 0.12)}`
- `setters={"ifm_taux": ["ifm", "taux"], "indemnite_conges_taux": ["indemnite_conges", "taux"]}`
- `require_current=True`, `comment="Mise à jour automatique: taux intérim (IFM, ICCP) (IA web)"`.
- `SCHEMA` : `ifm_taux`, `indemnite_conges_taux`.
- `task_prompt` : « Intérim (travail temporaire) en France : 1) taux de l'indemnité de fin de mission (IFM), FRACTION (ex : 0.10). 2) taux de l'indemnité compensatrice de congés payés, FRACTION. Sources officielles (service-public, Code du travail L1251-32). »
- `generator="interim/interim_AI.py"`.

#### Task 5: `stage` — gratification minimale

- Dossier `scraping/stage/`, source_key `STAGE`.
- `keys=["pct_plafond_horaire_ss"]`
- `bounds={"pct_plafond_horaire_ss": (0.10, 0.20)}`
- `setters={"pct_plafond_horaire_ss": ["pct_plafond_horaire_ss"]}`
- `require_current=False`, `comment="Mise à jour automatique: gratification de stage (IA web)"`.
- `SCHEMA` : `pct_plafond_horaire_ss`.
- `task_prompt` : « Gratification minimale de stage en France : pourcentage du plafond horaire de la Sécurité sociale servant de base, en FRACTION (ex : 0.15 pour 15 %). Sources officielles (URSSAF, service-public). »
- `generator="stage/stage_AI.py"`.

#### Task 6: `maladie` — CSG/CRDS sur IJSS

- Dossier `scraping/maladie/`, source_key `MALADIE`.
- `keys=["csg_ijss_taux_deductible", "csg_ijss_taux_non_deductible"]`
- `bounds={"csg_ijss_taux_deductible": (0.0, 0.10), "csg_ijss_taux_non_deductible": (0.0, 0.10)}`
- `setters={"csg_ijss_taux_deductible": ["csg_ijss", "taux_deductible"], "csg_ijss_taux_non_deductible": ["csg_ijss", "taux_non_deductible"]}`
- `require_current=True`, `comment="Mise à jour automatique: CSG/CRDS sur IJSS (IA web)"`.
- `SCHEMA` : les deux clés.
- `task_prompt` : « CSG/CRDS applicables aux indemnités journalières de Sécurité sociale (IJSS) maladie en France : 1) taux de CSG déductible, FRACTION (ex : 0.038). 2) taux de CSG/CRDS non déductible, FRACTION (ex : 0.029). Sources officielles (BOSS, URSSAF). »
- `generator="maladie/maladie_AI.py"`.

#### Task 7: `jei` — plafond d'exonération

- Dossier `scraping/jei/`, source_key `JEI`.
- `keys=["facteur_smic_plafond"]`
- `bounds={"facteur_smic_plafond": (3.0, 6.0)}`
- `setters={"facteur_smic_plafond": ["facteur_smic_plafond"]}`
- `require_current=True` (préserve `actif`, `cotisations_exonerees_patronales`).
- `comment="Mise à jour automatique: plafond exonération JEI (IA web)"`.
- `SCHEMA` : `facteur_smic_plafond`.
- `task_prompt` : « Jeune Entreprise Innovante (JEI) en France, exonération de cotisations patronales : plafond de rémunération mensuelle exonérée exprimé en MULTIPLE du SMIC (ex : 4.5). Sources officielles (BOSS, URSSAF). »
- `generator="jei/jei_AI.py"`.

#### Task 8: `oeth` — taux d'obligation d'emploi

- Dossier `scraping/oeth/`, source_key `OETH`.
- `keys=["taux_obligation"]`
- `bounds={"taux_obligation": (0.0, 0.10)}`
- `setters={"taux_obligation": ["taux_obligation"]}`
- `require_current=True` (préserve `coefficients`, `boeth_50_plus_factor`, etc.).
- `comment="Mise à jour automatique: taux OETH (IA web)"`.
- `SCHEMA` : `taux_obligation`.
- `task_prompt` : « Obligation d'emploi des travailleurs handicapés (OETH/DOETH) en France : taux légal d'obligation d'emploi, en FRACTION (ex : 0.06 pour 6 %). Sources officielles (URSSAF, service-public). »
- `generator="oeth/oeth_AI.py"`.

#### Task 9: `reduction_generale` — paramètres RGDU

- Dossier `scraping/reduction_generale/`, source_key `REDUCTION_GENERALE`.
- `keys=["tmin", "p", "point_sortie_smic", "tdelta_fnal_moins_50", "tdelta_fnal_50_et_plus"]`
- `bounds={"tmin": (0.0, 0.5), "p": (1.0, 3.0), "point_sortie_smic": (1.6, 4.0), "tdelta_fnal_moins_50": (0.0, 0.5), "tdelta_fnal_50_et_plus": (0.0, 0.5)}`
- `setters={"tmin": ["tmin"], "p": ["p"], "point_sortie_smic": ["point_sortie_smic"], "tdelta_fnal_moins_50": ["tdelta", "fnal_moins_50"], "tdelta_fnal_50_et_plus": ["tdelta", "fnal_50_et_plus"]}`
- `require_current=True` (préserve `actif`).
- `comment="Mise à jour automatique: paramètres RGDU (IA web)"`.
- `SCHEMA` : les 5 clés.
- `task_prompt` : « Réduction générale dégressive des cotisations patronales (RGDU) en France, année courante : 1) coefficient maximal T pour employeurs de moins de 50 salariés (FNAL 0,10 %) et 2) pour 50 salariés et plus (FNAL 0,50 %), tous deux en FRACTION (ex : 0.3193 / 0.3233). 3) exposant de dégressivité P. 4) point de sortie en MULTIPLE du SMIC (ex : 3.0). 5) taux plancher Tmin. Sources officielles (BOSS, URSSAF). »
  - Mapping payload→setters : le AI script mappe `T_moins_50`→`tdelta_fnal_moins_50`, `T_50_plus`→`tdelta_fnal_50_et_plus` (adapter les noms de propriétés du SCHEMA en conséquence, mêmes clés que `keys`).
- `generator="reduction_generale/reduction_generale_AI.py"`.
- **Validation croisée** (note à l'implémenteur, non bloquant) : à la revue humaine, confirmer la cohérence de `tdelta.*` avec le taux FNAL scrapé par ailleurs.

**Commit** (chaque tâche 3–9) :
```bash
git add backend/scraping/<x>/ backend/tests/scraping/test_<x>_spec.py
git commit -m "feat(scraping): orchestrateur IA <x>"
```

---

### Task 10: taux non-scalaires — `mandataire` (liste) + `comptes_avances_acomptes` (PCG)

Ces deux-là n'ont pas de valeur scalaire : on passe `validate=` et `build=`
custom à `build_ai_scalar_spec` (surcharges prévues en Task 1).

**Files:**
- Create: `backend/scraping/mandataire/` (3 fichiers) + `backend/tests/scraping/test_mandataire_spec.py`
- Create: `backend/scraping/comptes_avances_acomptes/` (3 fichiers) + test
- Modify: aucun fichier existant.

**Interfaces:**
- Consomme `build_ai_scalar_spec(validate=..., build=...)`.

- [ ] **Step 1: Test mandataire (liste ⊆ ensemble connu)**

```python
# backend/tests/scraping/test_mandataire_spec.py  (extrait clé)
def test_validate_subset_and_merge():
    from spec import SPEC  # dossier mandataire
    ok = SPEC.validate_signature({"cotisations_exclues": ["assurance_chomage", "ags"]})
    assert ok.ok
    ko = SPEC.validate_signature({"cotisations_exclues": ["inconnue"]})
    assert not ko.ok
    out = SPEC.build_config_data(
        {"cotisations_exclues": ["assurance_chomage", "ags", "apec"]},
        {"config_data": {"cotisations_exclues": ["assurance_chomage"]}},
    )
    assert out["cotisations_exclues"] == ["assurance_chomage", "ags", "apec"]
```

- [ ] **Step 2: `mandataire/spec.py`** — `validate` = liste ⊆ `{"assurance_chomage","ags","chomage","apec"}`, sinon `ValidationResult` invalide ; `build` = remplace `config_data["cotisations_exclues"]` par la liste (require current). `keys=["cotisations_exclues"]`, `source_key="MANDATAIRE"`. AI `SCHEMA` = `{"cotisations_exclues": {"type":"array","items":{"type":"string"}}}`. `task_prompt` : « Dirigeant/mandataire social assimilé salarié en France : liste des cotisations dont il est EXCLU (identifiants attendus parmi : assurance_chomage, ags, chomage, apec). Sources officielles (URSSAF, BOSS). »

- [ ] **Step 3: Test comptes PCG (codes numériques)**

```python
# backend/tests/scraping/test_comptes_avances_acomptes_spec.py (extrait clé)
def test_validate_pcg_codes_and_merge():
    from spec import SPEC  # dossier comptes_avances_acomptes
    assert SPEC.validate_signature({"avance": "425", "banque": "512"}).ok
    assert not SPEC.validate_signature({"avance": "abc"}).ok
    out = SPEC.build_config_data(
        {"avance": "425", "banque": "512"},
        {"config_data": {"acompte": "425"}},
    )
    assert out["avance"] == "425" and out["acompte"] == "425"
```

- [ ] **Step 4: `comptes_avances_acomptes/spec.py`** — `validate` = chaque valeur `str` composée de chiffres ; `build` = merge shallow des paires (require current). `keys=["avance","acompte","banque"]`, `source_key="COMPTES_AVANCES_ACOMPTES"`. `SCHEMA` : trois `["string","null"]`. `task_prompt` : « Plan Comptable Général français : numéro de compte standard pour 1) avances au personnel, 2) acomptes au personnel, 3) banque. Réponds par les codes PCG (ex : "425", "425", "512"). »

- [ ] **Step 5: Run tests**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/pytest tests/scraping/test_mandataire_spec.py tests/scraping/test_comptes_avances_acomptes_spec.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/scraping/mandataire/ backend/scraping/comptes_avances_acomptes/ backend/tests/scraping/test_mandataire_spec.py backend/tests/scraping/test_comptes_avances_acomptes_spec.py
git commit -m "feat(scraping): orchestrateurs IA mandataire (liste) et comptes PCG"
```

---

### Task 11: Wiring backend (mapping + folder-map + manifest + migration `scraping_sources`)

**Files:**
- Modify: `backend/app/modules/rates/domain/rate_source_mapping.py` (dict `RATE_KEY_TO_SOURCE_KEYS`)
- Modify: `backend/app/modules/scraping/infrastructure/scraper_runner.py` (`SOURCE_KEY_TO_FOLDER_MAPPING`)
- Modify: `backend/scraping/scraper_manifest.py` (`SCRAPER_MANIFEST`)
- Create: `supabase/migrations/20260722120000_scraping_sources_taux_ia.sql`
- Test: `backend/tests/modules/rates/test_manifest_new_rates.py`

**Interfaces:**
- Consomme les 10 dossiers scrapers (Tasks 2–10).
- Produces: les 10 `config_key` présents dans le manifeste sync + `all_page_source_keys()`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/modules/rates/test_manifest_new_rates.py
from app.modules.rates.domain.rate_source_mapping import (
    RATE_KEY_TO_SOURCE_KEYS,
    all_page_source_keys,
)

NEW = {
    "taux_interet_legal": "TAUX_INTERET_LEGAL",
    "cdd": "CDD",
    "interim": "INTERIM",
    "stage": "STAGE",
    "maladie": "MALADIE",
    "jei": "JEI",
    "oeth": "OETH",
    "reduction_generale": "REDUCTION_GENERALE",
    "mandataire": "MANDATAIRE",
    "comptes_avances_acomptes": "COMPTES_AVANCES_ACOMPTES",
}


def test_all_new_rate_keys_mapped():
    for rate_key, source_key in NEW.items():
        assert RATE_KEY_TO_SOURCE_KEYS.get(rate_key) == [source_key]


def test_new_sources_in_full_page_update():
    page = set(all_page_source_keys())
    for source_key in NEW.values():
        assert source_key in page


def test_existing_mappings_untouched():
    # garde-fou anti-régression : les clés historiques restent inchangées
    assert RATE_KEY_TO_SOURCE_KEYS["smic"] == ["SMIC"]
    assert RATE_KEY_TO_SOURCE_KEYS["pss"] == ["PSS"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/pytest tests/modules/rates/test_manifest_new_rates.py -q`
Expected: FAIL (`assert None == ['TAUX_INTERET_LEGAL']`)

- [ ] **Step 3: Add the 10 entries to `RATE_KEY_TO_SOURCE_KEYS`**

Dans `rate_source_mapping.py`, ajouter (sans rien retirer) après la clé `"cotisations"` fermée, à l'intérieur du dict :

```python
    "taux_interet_legal": ["TAUX_INTERET_LEGAL"],
    "cdd": ["CDD"],
    "interim": ["INTERIM"],
    "stage": ["STAGE"],
    "maladie": ["MALADIE"],
    "jei": ["JEI"],
    "oeth": ["OETH"],
    "reduction_generale": ["REDUCTION_GENERALE"],
    "mandataire": ["MANDATAIRE"],
    "comptes_avances_acomptes": ["COMPTES_AVANCES_ACOMPTES"],
```

- [ ] **Step 4: Add folder mappings — les 10 explicitement (OBLIGATOIRE)**

`get_scraper_folder_name` a un fallback `source_key.replace("_","").replace("-","")`
qui **ne met PAS en minuscules** (vérifié : `"CDD"` → `"CDD"`, or le dossier est
`cdd`). Il faut donc mapper **les 10** explicitement dans
`SOURCE_KEY_TO_FOLDER_MAPPING` de `scraper_runner.py` :

```python
    "TAUX_INTERET_LEGAL": "taux_interet_legal",
    "CDD": "cdd",
    "INTERIM": "interim",
    "STAGE": "stage",
    "MALADIE": "maladie",
    "JEI": "jei",
    "OETH": "oeth",
    "REDUCTION_GENERALE": "reduction_generale",
    "MANDATAIRE": "mandataire",
    "COMPTES_AVANCES_ACOMPTES": "comptes_avances_acomptes",
```

- [ ] **Step 5: Add `ScraperEntry` × 10 to `SCRAPER_MANIFEST`**

Dans `scraper_manifest.py`, ajouter au tuple `SCRAPER_MANIFEST` (tier `standard`,
`network_flaky=True`, checks minimaux). Exemple pour deux, répliquer pour les 10 :

```python
    ScraperEntry(
        name="TAUX_INTERET_LEGAL", dir="taux_interet_legal",
        config_key="taux_interet_legal", tier="standard", network_flaky=True,
        checks=(ScraperCheck(path=["data", "taux_annuel"], min=0.0, max=0.20, not_null=True),),
    ),
    ScraperEntry(
        name="CDD", dir="cdd", config_key="cdd", tier="standard", network_flaky=True,
        checks=(ScraperCheck(path=["data", "precarite", "taux"], min=0.0, max=0.15),),
    ),
```

> Adapter `path`/bornes par taux (mêmes valeurs que les `bounds` des specs). Pour
> `mandataire`/`comptes_avances_acomptes` : `checks=()` (non numériques).

- [ ] **Step 6: Create the migration**

```sql
-- supabase/migrations/20260722120000_scraping_sources_taux_ia.sql
-- Sources scraping IA mono-source pour les taux jusque-là non régénérables.
INSERT INTO public.scraping_sources (
    source_key, source_name, source_type, description, target_table, target_field,
    primary_url, available_scrapers, orchestrator_path, requires_company_context,
    scraping_frequency, is_critical, is_active
)
VALUES
(
    'TAUX_INTERET_LEGAL', 'Taux d''intérêt légal', 'bareme',
    'Taux d''intérêt légal semestriel en vigueur',
    'payroll_config', 'taux_interet_legal',
    'https://www.service-public.fr/particuliers/vosdroits/F2100',
    '["taux_interet_legal_AI.py"]'::jsonb,
    'scraping/taux_interet_legal/orchestrator.py', false, 'manual', false, true
),
(
    'CDD', 'CDD — précarité & ICCP', 'bareme',
    'Taux prime de précarité et indemnité congés CDD',
    'payroll_config', 'cdd',
    'https://www.service-public.fr/particuliers/vosdroits/F40',
    '["cdd_AI.py"]'::jsonb,
    'scraping/cdd/orchestrator.py', false, 'manual', false, true
),
(
    'INTERIM', 'Intérim — IFM & ICCP', 'bareme',
    'Taux indemnité de fin de mission et congés intérim',
    'payroll_config', 'interim',
    'https://www.service-public.fr/particuliers/vosdroits/F13851',
    '["interim_AI.py"]'::jsonb,
    'scraping/interim/orchestrator.py', false, 'manual', false, true
),
(
    'STAGE', 'Gratification de stage', 'bareme',
    'Pourcentage du plafond horaire SS pour la gratification de stage',
    'payroll_config', 'stage',
    'https://www.urssaf.fr/accueil/employeur/embaucher-salarie/stagiaire.html',
    '["stage_AI.py"]'::jsonb,
    'scraping/stage/orchestrator.py', false, 'manual', false, true
),
(
    'MALADIE', 'CSG/CRDS sur IJSS', 'bareme',
    'Taux CSG déductible et non déductible sur les IJSS',
    'payroll_config', 'maladie',
    'https://boss.gouv.fr/portail/accueil/indemnisation-ijss.html',
    '["maladie_AI.py"]'::jsonb,
    'scraping/maladie/orchestrator.py', false, 'manual', false, true
),
(
    'JEI', 'Plafond exonération JEI', 'bareme',
    'Plafond de rémunération exonérée JEI (multiple du SMIC)',
    'payroll_config', 'jei',
    'https://boss.gouv.fr/portail/accueil/exonerations-zonees-et-ciblees/jei.html',
    '["jei_AI.py"]'::jsonb,
    'scraping/jei/orchestrator.py', false, 'manual', false, true
),
(
    'OETH', 'Taux OETH', 'bareme',
    'Taux légal d''obligation d''emploi des travailleurs handicapés',
    'payroll_config', 'oeth',
    'https://www.urssaf.fr/accueil/employeur/cotisations/liste-cotisations/oeth.html',
    '["oeth_AI.py"]'::jsonb,
    'scraping/oeth/orchestrator.py', false, 'manual', false, true
),
(
    'REDUCTION_GENERALE', 'Paramètres RGDU', 'bareme',
    'Coefficients T, P, Tmin, point de sortie de la réduction générale',
    'payroll_config', 'reduction_generale',
    'https://boss.gouv.fr/portail/accueil/allegements-et-exonerations/reduction-generale.html',
    '["reduction_generale_AI.py"]'::jsonb,
    'scraping/reduction_generale/orchestrator.py', false, 'manual', false, true
),
(
    'MANDATAIRE', 'Cotisations exclues mandataire', 'bareme',
    'Liste des cotisations dont le mandataire social est exclu',
    'payroll_config', 'mandataire',
    'https://www.urssaf.fr/accueil/employeur/dirigeants.html',
    '["mandataire_AI.py"]'::jsonb,
    'scraping/mandataire/orchestrator.py', false, 'manual', false, true
),
(
    'COMPTES_AVANCES_ACOMPTES', 'Comptes PCG avances/acomptes', 'bareme',
    'Comptes du Plan Comptable Général pour avances, acomptes, banque',
    'payroll_config', 'comptes_avances_acomptes',
    'https://www.plancomptable.com/titre-IV/titre-IV.htm',
    '["comptes_avances_acomptes_AI.py"]'::jsonb,
    'scraping/comptes_avances_acomptes/orchestrator.py', false, 'manual', false, true
)
ON CONFLICT (source_key) DO UPDATE SET
    source_name = EXCLUDED.source_name,
    description = EXCLUDED.description,
    primary_url = EXCLUDED.primary_url,
    available_scrapers = EXCLUDED.available_scrapers,
    orchestrator_path = EXCLUDED.orchestrator_path,
    is_active = EXCLUDED.is_active;
```

- [ ] **Step 7: Run mapping test to verify it passes**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/pytest tests/modules/rates/test_manifest_new_rates.py -q`
Expected: PASS

- [ ] **Step 8: Apply migration (DEV/staging d'abord ; prod après OK explicite utilisateur)**

Run (staging): `supabase db push` (ou l'outil de migration du projet).
Expected: `scraping_sources` contient 10 nouvelles lignes actives.
**⚠ Prod** : ne pousser qu'après validation explicite de l'utilisateur (voir §9 du spec ; clés `.env` Supabase potentiellement inversées).

- [ ] **Step 9: Commit**

```bash
git add backend/app/modules/rates/domain/rate_source_mapping.py backend/app/modules/scraping/infrastructure/scraper_runner.py backend/scraping/scraper_manifest.py supabase/migrations/20260722120000_scraping_sources_taux_ia.sql backend/tests/modules/rates/test_manifest_new_rates.py
git commit -m "feat(rates): brancher les 10 nouveaux taux IA (mapping, manifest, sources)"
```

---

### Task 12: UI — sortir `payslip_edit_lock` + page « Paramètres paie »

**Files:**
- Modify: `frontend/src/lib/ratesSyncManifest.ts` (`BAREMES_EXCLUDED_KEYS`)
- Modify: `frontend/src/components/rates/RatesAdminPanel.tsx` (retirer la carte)
- Modify: `frontend/src/pages/admin/eywai/navigation.ts` (entrée nav)
- Create: `frontend/src/pages/admin/eywai/PayrollSettings.tsx`
- Modify: routeur super-admin (là où sont déclarées les routes `/super-admin/*` ; localiser via `grep -rn "super-admin/rates" frontend/src`)
- Test: `frontend/src/lib/ratesSyncManifest.test.ts` (ajout d'un cas)

**Interfaces:**
- Consomme la carte existante `PayrollPayslipEditLockCard`.

- [ ] **Step 1: Write the failing test (exclusion)**

```ts
// ratesSyncManifest.test.ts — ajouter
import { listBaremesSectionKeys } from './ratesSyncManifest';

test('payslip_edit_lock never appears in barèmes section', () => {
  const data = {
    payslip_edit_lock: { config_data: { cutoff_day_of_next_month: 5 } },
    frais_pro: { config_data: { repas: 1 } },
  };
  const keys = listBaremesSectionKeys(data as any);
  expect(keys).not.toContain('payslip_edit_lock');
  expect(keys).toContain('frais_pro');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/ratesSyncManifest.test.ts`
Expected: FAIL (`payslip_edit_lock` présent)

- [ ] **Step 3: Exclude the key**

Dans `ratesSyncManifest.ts`, ajouter `'payslip_edit_lock'` à `BAREMES_EXCLUDED_KEYS`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/lib/ratesSyncManifest.test.ts`
Expected: PASS

- [ ] **Step 5: Remove card from RatesAdminPanel**

Dans `RatesAdminPanel.tsx` : retirer l'import ligne 16 et l'usage `<PayrollPayslipEditLockCard />` ligne 64.

- [ ] **Step 6: Create the Paramètres paie page**

```tsx
// frontend/src/pages/admin/eywai/PayrollSettings.tsx
import { PayrollPayslipEditLockCard } from '@/features/admin/components/PayrollPayslipEditLockCard';

export default function PayrollSettings() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Paramètres paie</h1>
        <p className="text-sm text-muted-foreground">
          Réglages globaux de la paie et des bulletins.
        </p>
      </div>
      <PayrollPayslipEditLockCard />
    </div>
  );
}
```

- [ ] **Step 7: Add nav entry + route**

Dans `navigation.ts`, section *Référentiels*, ajouter après « Suivi des taux » :
```ts
{ name: "Paramètres paie", href: "/super-admin/payroll-settings", icon: Percent },
```
(réutiliser une icône déjà importée, ex. `Percent`, ou importer `Settings`.)
Puis brancher la route `/super-admin/payroll-settings` → `PayrollSettings` dans le
routeur super-admin (fichier trouvé au grep du header).

- [ ] **Step 8: Verify build + tests**

Run: `cd frontend && npx tsc --noEmit && npx vitest run src/lib/ratesSyncManifest.test.ts`
Expected: PASS, pas d'erreur de type.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib/ratesSyncManifest.ts frontend/src/lib/ratesSyncManifest.test.ts frontend/src/components/rates/RatesAdminPanel.tsx frontend/src/pages/admin/eywai/PayrollSettings.tsx frontend/src/pages/admin/eywai/navigation.ts
git commit -m "feat(rates): sortir le verrou d'édition de Suivi des taux vers Paramètres paie"
```

---

### Task 13: Vérification finale (intégration + non-régression)

**Files:** aucun (vérification).

- [ ] **Step 1: Les nouveaux taux sont dans le manifeste sync**

```bash
cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -c "
from app.modules.rates.application.sync import get_rates_sync_sources_manifest
m = get_rates_sync_sources_manifest()
keys = {c['rate_key'] for c in m['rate_categories']}
for k in ['taux_interet_legal','cdd','interim','stage','maladie','jei','oeth','reduction_generale','mandataire','comptes_avances_acomptes']:
    print(k, k in keys, bool([c for c in m['rate_categories'] if c['rate_key']==k and c['sources']]))
"
```
Expected: chaque ligne `<key> True True` (présent + sources non vides après migration appliquée en staging).

- [ ] **Step 2: « Régénérer tout » inclut les nouveaux taux**

```bash
cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/python -c "
from app.modules.rates.domain.rate_source_mapping import all_page_source_keys
p=set(all_page_source_keys())
print(all(s in p for s in ['TAUX_INTERET_LEGAL','CDD','INTERIM','STAGE','MALADIE','JEI','OETH','REDUCTION_GENERALE','MANDATAIRE','COMPTES_AVANCES_ACOMPTES']))
"
```
Expected: `True`

- [ ] **Step 3: Aucun scraper existant modifié (garde-fou « ne rien casser »)**

```bash
git diff --name-only main...HEAD -- backend/scraping | grep -vE '^backend/scraping/(core/ai_scalar_(spec|source)\.py|scraper_manifest\.py|taux_interet_legal/|cdd/|interim/|stage/|maladie/|jei/|oeth/|reduction_generale/|mandataire/|comptes_avances_acomptes/)'
```
Expected: **aucune sortie** (aucun fichier d'un scraper existant touché).

- [ ] **Step 4: Non-régression paie**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/pytest tests/modules/payroll -q`
Expected: PASS (~381), aucun test cassé (les valeurs par défaut sont inchangées).

- [ ] **Step 5: Suite scraping**

Run: `cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv-ci/bin/pytest tests/scraping -q`
Expected: PASS.

- [ ] **Step 6: Revue humaine end-to-end (manuel, staging)**

Dans l'UI staging : ouvrir « Suivi des taux » → un taux (ex. Taux intérêt légal)
affiche désormais le bouton → « régénérer » → un *pending change* apparaît dans
« Validation & alertes » avec diff → valider → `payroll_config` mis à jour.
Vérifier aussi « Mise à jour complète » : les nouveaux taux sont lancés.
Vérifier que « Payslip Edit Lock » **n'apparaît plus** dans Suivi des taux et est
éditable dans « Paramètres paie ».

---

## Self-Review

- **Couverture spec :** §4 fabrique → Task 1 ; §5 catalogue (9 taux) → Tasks 2–9 ;
  non-scalaires → Task 10 ; §4.3 wiring + §9 migration → Task 11 ; §6
  payslip_edit_lock → Task 12 ; §3.1 intégration/non-régression → Task 13.
  `comptes_avances_acomptes` (§7) → Task 10. Human-gating (§4.2) → `tier="critical"`
  (Task 1). Aucun requirement sans tâche.
- **Placeholders :** aucun « TBD/TODO ». Les Tasks 3–9 donnent le code variable
  complet (pas « comme Task N » : le squelette est explicitement celui de Task 2,
  répété avec substitutions listées).
- **Cohérence des types :** `build_ai_scalar_spec(...)` mêmes params partout ;
  `run_ai_scalar_source(...)` mêmes clés ; `source_key`/`config_key`/dossiers
  cohérents entre specs, mapping, folder-map, manifest et migration.
- **Points à vérifier à l'implémentation (notés inline) :** API réelle de
  `ValidationResult` (`.ok` vs `.is_valid`) ; casse de `get_scraper_folder_name`
  (mapper les 10 explicitement par sécurité) ; fichier exact du routeur super-admin.
