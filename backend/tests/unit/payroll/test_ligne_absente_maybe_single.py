"""Ligne absente : maybe_single().execute() rend None (postgrest 2.31), la lecture le dit sans planter.

Même piège que la publication des documents de départ (tournage H.4 du 20/10/2026) :
`.data` était lu sur None. Quand la ligne existe, rien ne change.
"""

from __future__ import annotations

import logging

import pytest

from tests.unit.sans_ligne import sans_ligne  # noqa: F401 — fixture

pytestmark = pytest.mark.unit


def test_les_evenements_d_un_mois_sans_calendrier_ne_sont_pas_generes(sans_ligne, caplog):
    from app.modules.payroll.application import writer

    sans_ligne(writer, accesseurs=("get_supabase_admin_client",))
    with caplog.at_level(logging.WARNING):
        assert writer.generer_et_enregistrer_evenements("e", "Nom", 35.0, 2026, 10) is None
    messages = [r.getMessage() for r in caplog.records]
    assert any("Aucun calendrier trouvé" in m for m in messages)
    assert not any("Erreur" in m for m in messages)
