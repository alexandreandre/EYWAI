"""Prime de précarité et motif de recours du CDD.

Code du travail, art. L1243-10, 1° : l'indemnité de fin de contrat n'est pas
due pour un contrat conclu au titre du 3° de l'article L1242-2 (saisonnier,
usage ; le contrat vendanges est saisonnier) ou de l'article L1242-3
(personnes sans emploi en difficulté, complément de formation
professionnelle). Codes du motif : rubrique DSN S21.G00.40.021, ceux de la
fiche (« Motif de recours du CDD »).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.reference_remuneration import estimer_extras_fin_contrat

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

PRIME = "Prime de précarité (CDD)"


def _gains(*, motif: str | None = None, classification_motif: str | None = None, **spec) -> dict:
    specificites = dict(spec)
    if motif is not None:
        specificites["dsn_reprise"] = {"motif_recours": motif}
    ctx = build_test_contexte(
        salaire_base=2200.0,
        type_contrat="CDD",
        date_entree="2025-10-01",
        date_fin_contrat="2026-04-30",
        cumuls={"brut_total": 8800.0},
        specificites_extra=specificites,
    )
    if classification_motif is not None:
        ctx.contrat["remuneration"]["classification_conventionnelle"] = {
            "motif_recours": classification_motif
        }
    res = calculer_salaire_brut(ctx, [], date(2026, 4, 1), date(2026, 4, 30), [])
    return {l["libelle"]: l["gain"] for l in res["lignes_composants_brut"] if l.get("gain")}


def test_accroissement_temporaire_d_activite_la_prime_est_due():
    gains = _gains(motif="02")
    assert gains[PRIME] == pytest.approx(1100.0, abs=0.01)


def test_cdd_saisonnier_pas_de_prime():
    gains = _gains(motif="03")
    assert PRIME not in gains
    # L'indemnité de congés reste due, sur un brut sans précarité.
    iccp = next(v for k, v in gains.items() if "compensatrice de congés" in k)
    assert iccp == pytest.approx(1100.0, abs=0.05)


def test_motif_vide_la_prime_reste_due():
    assert _gains(motif="")[PRIME] == pytest.approx(1100.0, abs=0.01)
    assert _gains()[PRIME] == pytest.approx(1100.0, abs=0.01)


@pytest.mark.parametrize("motif", ["03", "04", "05", "09", "10", "3"])
def test_motifs_qui_excluent_la_prime(motif):
    assert PRIME not in _gains(motif=motif)


@pytest.mark.parametrize("motif", ["01", "02", "06", "07", "08", "12", "13"])
def test_motifs_qui_ne_l_excluent_pas(motif):
    assert PRIME in _gains(motif=motif)


def test_le_motif_de_la_classification_est_lu_comme_par_la_dsn():
    assert PRIME not in _gains(classification_motif="05")


def test_les_drapeaux_de_la_fiche_restent_prioritaires():
    assert PRIME not in _gains(motif="02", exclure_prime_precarite=True)
    assert PRIME not in _gains(motif="02", cdd_sans_precarite=True)


def test_l_estimation_de_sortie_suit_la_meme_regle():
    saisonnier, _ = estimer_extras_fin_contrat(
        11000.0, {}, is_cdd=True, specificites={"dsn_reprise": {"motif_recours": "03"}}
    )
    accroissement, _ = estimer_extras_fin_contrat(
        11000.0, {}, is_cdd=True, specificites={"dsn_reprise": {"motif_recours": "02"}}
    )
    assert saisonnier == 0.0
    assert accroissement == pytest.approx(1100.0)
