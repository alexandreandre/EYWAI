"""L'appel au modèle, avec un faux client : aucune requête ne part."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from app.modules.relecture_ia.domain.consignes import CONSIGNES, blocs_systeme
from app.modules.relecture_ia.infrastructure import client_claude
from app.modules.relecture_ia.infrastructure.client_claude import (
    RelecteurClaude,
    RelectureImpossible,
    creer_client,
)

pytestmark = pytest.mark.unit

SYSTEME = blocs_systeme(None)
FICHE = {"salarie": "SAL-ABC", "mois": {"salaire_brut": 100.0}}


def _reponse(texte: str, stop_reason: str = "end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text=texte)],
        usage=SimpleNamespace(
            input_tokens=10,
            output_tokens=20,
            cache_read_input_tokens=30,
            cache_creation_input_tokens=0,
        ),
    )


class FauxClient:
    def __init__(self, *reponses):
        self.reponses = list(reponses)
        self.appels: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.appels.append(kwargs)
        reponse = self.reponses.pop(0)
        if isinstance(reponse, Exception):
            raise reponse
        return reponse


_VIDE = json.dumps({"signalements": []})


def test_le_module_n_importe_pas_anthropic_au_chargement():
    source = Path(client_claude.__file__).read_text(encoding="utf-8")
    for noeud in ast.parse(source).body:
        if isinstance(noeud, ast.Import):
            assert all(a.name.split(".")[0] != "anthropic" for a in noeud.names)
        if isinstance(noeud, ast.ImportFrom):
            assert (noeud.module or "").split(".")[0] != "anthropic"


def test_parametres_de_l_appel():
    client = FauxClient(_reponse(_VIDE))
    RelecteurClaude(client=client).relire(SYSTEME, FICHE)
    appel = client.appels[0]
    assert appel["model"] == "claude-opus-5-5"
    assert appel["betas"] == ["server-side-fallback-2026-07-01"]
    assert appel["fallbacks"] == "default"
    assert appel["thinking"] == {"type": "adaptive"}
    assert appel["output_config"]["effort"] == "medium"
    assert appel["output_config"]["format"]["type"] == "json_schema"
    assert appel["system"] == SYSTEME
    assert appel["system"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert "SAL-ABC" in appel["messages"][0]["content"]


def test_reponse_lue_et_consommation_rendue():
    contenu = {
        "signalements": [
            {"gravite": "important", "ligne": "Brut", "raison": "x", "chiffres_cites": ["100"]}
        ]
    }
    reponse = RelecteurClaude(client=FauxClient(_reponse(json.dumps(contenu)))).relire(SYSTEME, FICHE)
    assert reponse.signalements == contenu["signalements"]
    assert reponse.usage["output_tokens"] == 20
    assert reponse.usage["cache_read_input_tokens"] == 30


def test_refus_dit_pourquoi_et_n_arrete_pas_le_lot():
    with pytest.raises(RelectureImpossible) as exc:
        RelecteurClaude(client=FauxClient(_reponse("", "refusal"))).relire(SYSTEME, FICHE)
    assert "refusé" in exc.value.message
    assert not exc.value.fatale


def test_max_tokens_relance_une_fois_avec_plus_de_place_et_cumule():
    client = FauxClient(_reponse("{", "max_tokens"), _reponse(_VIDE))
    reponse = RelecteurClaude(client=client).relire(SYSTEME, FICHE)
    assert client.appels[1]["max_tokens"] > client.appels[0]["max_tokens"]
    assert reponse.signalements == []
    assert reponse.usage["output_tokens"] == 40


def test_max_tokens_deux_fois_abandonne_ce_bulletin():
    client = FauxClient(_reponse("{", "max_tokens"), _reponse("{", "max_tokens"))
    with pytest.raises(RelectureImpossible) as exc:
        RelecteurClaude(client=client).relire(SYSTEME, FICHE)
    assert not exc.value.fatale


def test_json_illisible():
    with pytest.raises(RelectureImpossible):
        RelecteurClaude(client=FauxClient(_reponse("pas du json"))).relire(SYSTEME, FICHE)


@pytest.mark.parametrize("statut", [401, 403])
def test_cle_refusee_arrete_tout(statut):
    erreur = Exception("non")
    erreur.status_code = statut
    with pytest.raises(RelectureImpossible) as exc:
        RelecteurClaude(client=FauxClient(erreur)).relire(SYSTEME, FICHE)
    assert exc.value.fatale


def test_autre_erreur_n_arrete_que_ce_bulletin():
    erreur = Exception("surcharge")
    erreur.status_code = 529
    with pytest.raises(RelectureImpossible) as exc:
        RelecteurClaude(client=FauxClient(erreur)).relire(SYSTEME, FICHE)
    assert not exc.value.fatale


def test_blocs_avec_regles():
    blocs = blocs_systeme("Prime X versée en décembre.")
    assert blocs[0]["text"].startswith(CONSIGNES)
    assert "Prime X" in blocs[0]["text"]


def test_creer_client_import_paresseux_et_espace_de_travail(monkeypatch):
    vu = {}

    def anthropic_factice(**kwargs):
        vu.update(kwargs)
        return "client"

    faux = ModuleType("anthropic")
    faux.Anthropic = anthropic_factice
    monkeypatch.setitem(sys.modules, "anthropic", faux)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "cle")
    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", "espace-1")
    assert creer_client() == "client"
    assert vu["api_key"] == "cle"
    assert vu["default_headers"] == {"anthropic-workspace-id": "espace-1"}


def test_creer_client_sans_espace_de_travail(monkeypatch):
    vu = {}
    faux = ModuleType("anthropic")
    faux.Anthropic = lambda **kwargs: vu.update(kwargs) or "client"
    monkeypatch.setitem(sys.modules, "anthropic", faux)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "cle")
    monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)
    creer_client()
    assert "default_headers" not in vu


def test_sans_cle_relecture_impossible_et_le_dit(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RelectureImpossible) as exc:
        creer_client()
    assert exc.value.fatale
    assert "clé" in exc.value.message
