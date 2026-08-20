"""La trace de campagne participation ne doit toucher que les lignes créées (jamais de filtre global)."""
from unittest.mock import MagicMock, patch


def test_trace_campagne_ciblee_par_ids():
    from app.modules.participation.application import campaign_service as cs

    fake_table = MagicMock()
    fake_supabase = MagicMock()
    fake_supabase.table.return_value = fake_table
    fake_table.update.return_value = fake_table
    fake_table.in_.return_value = fake_table

    with patch.object(cs, "supabase", fake_supabase):
        cs._tag_campaign_inputs("camp-1", ["id-a", "id-b"])

    fake_table.update.assert_called_once_with({"participation_campaign_id": "camp-1"})
    fake_table.in_.assert_called_once_with("id", ["id-a", "id-b"])
    assert not fake_table.eq.called   # plus de filtre year/month
    assert not fake_table.is_.called  # plus de filtre "null" global


def test_trace_campagne_decoupe_les_grandes_listes():
    """Le filtre in_ voyage dans l'URL : une campagne de 180 lignes doit être découpée."""
    from app.modules.participation.application import campaign_service as cs

    fake_table = MagicMock()
    fake_supabase = MagicMock()
    fake_supabase.table.return_value = fake_table
    fake_table.update.return_value = fake_table
    fake_table.in_.return_value = fake_table

    ids = [f"id-{n}" for n in range(180)]
    with patch.object(cs, "supabase", fake_supabase):
        cs._tag_campaign_inputs("camp-1", ids)

    # 180 ids / 50 par lot => 4 appels, et chaque lot reste sous la limite
    assert fake_table.in_.call_count == 4
    envoyes = [appel.args[1] for appel in fake_table.in_.call_args_list]
    assert [len(lot) for lot in envoyes] == [50, 50, 50, 30]
    assert [i for lot in envoyes for i in lot] == ids


def test_trace_campagne_sans_ids_ne_touche_pas_la_base():
    from app.modules.participation.application import campaign_service as cs

    fake_supabase = MagicMock()
    with patch.object(cs, "supabase", fake_supabase):
        cs._tag_campaign_inputs("camp-1", [])

    assert not fake_supabase.table.called
