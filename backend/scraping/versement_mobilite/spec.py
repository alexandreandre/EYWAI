"""Spec orchestrateur versement mobilité (VM.py)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from core.rate_spec import PersistenceMode, RateSpec
from core.validation import ValidationResult

_DIR = Path(__file__).resolve().parent
VM_SCRIPT = _DIR.parent / "VM.py"


def _run_vm() -> dict:
    proc = subprocess.run(
        [sys.executable, str(VM_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(_DIR.parent.parent),
        timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-500:])
    # VM.py prints logs, no JSON — use marker file approach: import function
    sys.path.insert(0, str(_DIR.parent))
    from VM import scrape_vmrr_from_urssaf  # noqa: WPS433

    data, links = scrape_vmrr_from_urssaf()
    if not data:
        raise RuntimeError("VMRR scrape failed")
    return {"rows": len(data), "sample_link": links[0] if links else ""}


def _extract(p: dict) -> dict:
    return {"rows": p.get("rows", 0)}


SPEC = RateSpec(
    scraper_name="VM",
    config_key="taux_vmrr",
    scripts=[],  # custom run below — placeholder
    extract_signature=lambda p: p,
    signatures_equal=lambda a, b: a == b,
    validate_signature=lambda s: ValidationResult(
        int(s.get("rows", 0)) > 100, "VMRR trop peu de lignes"
    ),
    build_config_data=lambda _s, _c: {},
    persistence_mode=PersistenceMode.FULL,
    warn_single_source=False,
    dual_source_consensus=False,
)

# Override: VM uses script directly in orchestrator wrapper
