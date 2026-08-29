"""Contrat statique du gate de sécurité Copilot avant déploiement."""

from pathlib import Path

import pytest
import yaml


pytestmark = pytest.mark.unit

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEPLOY_WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "deploy.yml"
DEPLOY_TEST_ENV_WORKFLOW = (
    REPOSITORY_ROOT / ".github" / "workflows" / "deploy-test-env.yml"
)


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

    assert "copilot-security-gate" in jobs["test-env"]["needs"]
    assert "copilot-security-gate" in jobs["production"]["needs"]


def test_production_ne_peut_pas_etre_deployee_avant_le_gate():
    """
    Aucun job hors `production` ne doit viser les services de production.

    Le job `staging` visait sirh-backend / sirh-frontend avec la base de prod :
    la production était déployée AVANT l'approbation, et le gate ne protégeait
    rien. Ce test empêche la situation de revenir.
    """
    brut = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    workflow = yaml.safe_load(brut)
    jobs = workflow["jobs"]

    assert "staging" not in jobs, (
        "Le job `staging` déployait en réalité la production : il a été remplacé "
        "par `test-env`. Ne pas le réintroduire sans services dédiés."
    )

    # Le déploiement de test doit viser des services suffixés -test et la base de test.
    test_env = jobs["test-env"]
    assert test_env["env"]["BACKEND_SERVICE_NAME"].endswith("-test")
    assert test_env["env"]["FRONTEND_SERVICE_NAME"].endswith("-test")

    etapes = "\n".join(str(e) for e in test_env["steps"])
    assert "SUPABASE_TEST_URL" in etapes, "Le test doit viser la base de test."
    assert "APP_ENV=test" in etapes, "Les garde-fous doivent être actifs."
    assert "secrets.SUPABASE_URL }}" not in etapes, (
        "Le déploiement de test ne doit jamais recevoir la base de production."
    )

    # La production reste derrière le déploiement de test.
    assert "test-env" in jobs["production"]["needs"]
    assert jobs["production"]["environment"] == "production"


def test_deploy_test_env_injects_openrouter_api_key():
    """Sans cette clé, calendrier IA (503) et copilote (500) cassent sur le test."""
    brut = DEPLOY_TEST_ENV_WORKFLOW.read_text(encoding="utf-8")
    assert "gcloud run deploy" in brut
    assert "OPENROUTER_API_KEY=${{ secrets.OPENROUTER_API_KEY }}" in brut
    assert "--set-env-vars" in brut or "--update-env-vars" in brut
