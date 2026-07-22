"""Contrat statique du gate de sécurité Copilot avant déploiement."""

from pathlib import Path

import pytest
import yaml


pytestmark = pytest.mark.unit

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEPLOY_WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "deploy.yml"


def test_deployments_require_blocking_copilot_security_gate():
    workflow = yaml.safe_load(DEPLOY_WORKFLOW.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]

    gate = jobs["copilot-security-gate"]
    assert gate.get("continue-on-error") is not True
    assert "if" not in gate, "Le gate doit s'exécuter pour chaque mode de déclenchement."

    uses = [step.get("uses", "") for step in gate["steps"]]
    assert "actions/checkout@v4" in uses
    assert "actions/setup-python@v5" in uses

    checkout = next(
        step for step in gate["steps"] if step.get("uses") == "actions/checkout@v4"
    )
    checkout_ref = checkout["with"]["ref"]
    assert "github.event.workflow_run.head_sha" in checkout_ref
    assert "github.sha" in checkout_ref

    setup_python = next(
        step for step in gate["steps"] if step.get("uses") == "actions/setup-python@v5"
    )
    assert setup_python["with"]["python-version"] == "3.11"

    commands = "\n".join(
        str(step.get("run", "")) for step in gate["steps"] if "run" in step
    )
    assert "requirements.txt" in commands
    assert "requirements-dev.txt" in commands
    assert "tests/unit/copilot" in commands
    assert "tests/integration/copilot" in commands
    assert "tests/unit/access_control" in commands

    assert "copilot-security-gate" in jobs["staging"]["needs"]
    assert "copilot-security-gate" in jobs["production"]["needs"]
