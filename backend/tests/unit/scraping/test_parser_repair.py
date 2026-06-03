"""Tests de l'auto-réparation supervisée du parser (cas B)."""

from core.parser_repair import (
    ENV_REPAIR_DISABLED,
    RepairProposal,
    apply_proposal,
    passes_invariants,
    repair_parser,
    reproduces_validated,
)

HTML = """
<html><body>
  <table><tr><td class="smic">SMIC horaire : 11,88 €</td></tr></table>
  <div class="autre">Autre valeur 999</div>
</body></html>
"""


def test_apply_proposal_extracts_french_number():
    proposal = RepairProposal(css_selector="td.smic", value_regex=r"\d[\d\s.,]*", transform="eur")
    assert apply_proposal(HTML, proposal) == 11.88


def test_apply_proposal_no_match_returns_none():
    proposal = RepairProposal(css_selector="td.inexistant")
    assert apply_proposal(HTML, proposal) is None


def test_passes_invariants_bounds():
    assert passes_invariants(11.88, invariant_min=10.0, invariant_max=15.0)
    assert not passes_invariants(99.0, invariant_min=10.0, invariant_max=15.0)


def test_reproduces_validated_tolerance():
    assert reproduces_validated(11.88, 11.88)
    assert reproduces_validated(11.885, 11.88, abs_tol=0.01)
    assert not reproduces_validated(12.5, 11.88, abs_tol=0.01)


def test_repair_succeeds_when_oracle_satisfied():
    # Le modèle (mocké) propose un bon sélecteur ; il NE connaît pas la valeur cible.
    def fake_propose(html, intent, attempt, feedback):
        return RepairProposal(css_selector="td.smic", value_regex=r"\d[\d\s.,]*", transform="eur")

    result = repair_parser(
        html=HTML,
        intent="Extraire le SMIC horaire (€)",
        validated_value=11.88,
        invariant_min=10.0,
        invariant_max=15.0,
        propose_fn=fake_propose,
    )
    assert result.success
    assert result.extracted_value == 11.88
    assert not result.escalate


def test_repair_escalates_when_value_not_reproduced():
    # Le sélecteur lit une valeur hors invariants -> jamais accepté, escalade.
    def fake_propose(html, intent, attempt, feedback):
        return RepairProposal(css_selector="div.autre", value_regex=r"\d+", transform="float")

    result = repair_parser(
        html=HTML,
        intent="Extraire le SMIC horaire (€)",
        validated_value=11.88,
        invariant_min=10.0,
        invariant_max=15.0,
        max_attempts=2,
        propose_fn=fake_propose,
    )
    assert not result.success
    assert result.escalate
    assert result.attempts == 2


def test_repair_kill_switch(monkeypatch):
    monkeypatch.setenv(ENV_REPAIR_DISABLED, "1")
    result = repair_parser(
        html=HTML,
        intent="x",
        validated_value=11.88,
        propose_fn=lambda *a, **k: RepairProposal(css_selector="td.smic"),
    )
    assert not result.success
    assert result.escalate
    assert result.attempts == 0
