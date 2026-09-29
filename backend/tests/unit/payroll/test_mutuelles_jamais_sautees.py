"""Un bulletin ne sort jamais sans ses mutuelles.

29/09/2026 : sur un délai réseau, la lecture des types de mutuelle échouait, le
moteur notait un repli et continuait — septembre à blanc d'un salarié de Comitech
sans ses 127 € de mutuelle, net trop haut de 130 €. Désormais : deux relectures,
puis la génération s'arrête avec un message ; et une mutuelle de la fiche
introuvable ou désactivée arrête aussi le calcul au lieu de disparaître.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.modules.payroll.engine import mutuelles as M

pytestmark = pytest.mark.unit


def _client(*reponses):
    """Un client dont chaque `execute()` rend la réponse suivante (ou lève)."""
    client = MagicMock()
    requete = client.table.return_value.select.return_value.in_.return_value.eq.return_value
    requete.execute.side_effect = list(reponses)
    return client


def test_la_lecture_reessaie_puis_rend_les_mutuelles():
    ctx = SimpleNamespace()
    client = _client(TimeoutError("The read operation timed out"), SimpleNamespace(data=[{"id": "a", "libelle": "GAN"}]))
    with patch.object(M.database, "get_supabase_admin_client", return_value=client), patch.object(M.time, "sleep"):
        assert M.mutuelles_du_salarie(ctx, ["a"]) == [{"id": "a", "libelle": "GAN"}]


def test_trois_echecs_arretent_le_calcul():
    ctx = SimpleNamespace()
    client = _client(*[TimeoutError("The read operation timed out")] * 3)
    with patch.object(M.database, "get_supabase_admin_client", return_value=client), patch.object(M.time, "sleep"):
        with pytest.raises(M.MutuelleIllisible, match="n'a pas été calculé"):
            M.mutuelles_du_salarie(ctx, ["a"])


def test_une_mutuelle_de_la_fiche_introuvable_ou_desactivee_arrete_le_calcul():
    ctx = SimpleNamespace()
    client = _client(SimpleNamespace(data=[{"id": "a"}]))
    with patch.object(M.database, "get_supabase_admin_client", return_value=client):
        with pytest.raises(M.MutuelleIllisible, match="introuvable ou désactivée"):
            M.mutuelles_du_salarie(ctx, ["a", "b"])


def test_une_seule_lecture_par_bulletin():
    ctx = SimpleNamespace()
    client = _client(SimpleNamespace(data=[{"id": "a"}]))
    with patch.object(M.database, "get_supabase_admin_client", return_value=client):
        M.mutuelles_du_salarie(ctx, ["a"])
        M.mutuelles_du_salarie(ctx, ["a"])
    assert client.table.call_count == 1


def test_sans_mutuelle_rien_n_est_lu():
    with patch.object(M.database, "get_supabase_admin_client") as client:
        assert M.mutuelles_du_salarie(SimpleNamespace(), []) == []
    client.assert_not_called()


def test_le_calcul_des_cotisations_ne_continue_pas_sans_mutuelle():
    """Bout en bout : la lecture échoue, le calcul des cotisations s'arrête."""
    from app.modules.payroll.engine import calcul_cotisations
    from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations

    from .helpers import build_test_contexte

    ctx = build_test_contexte()
    ctx.contrat.setdefault("specificites_paie", {})["mutuelle"] = {"adhesion": True, "mutuelle_type_ids": ["a"]}
    with patch.object(calcul_cotisations, "mutuelles_du_salarie", side_effect=M.MutuelleIllisible("illisible")):
        with pytest.raises(M.MutuelleIllisible):
            calculer_cotisations(ctx, 2500.0, 0.0, 0.0)
