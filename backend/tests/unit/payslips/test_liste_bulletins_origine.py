"""La liste des bulletins porte l'origine et les points à arbitrer.

Sans eux, l'écran ne peut ni griser les actions d'un bulletin repris, ni
montrer un point à arbitrer. La colonne `origine` n'existe pas encore en
production (migration 20260917090000) : la requête doit y survivre.
"""

from unittest.mock import MagicMock, patch

from app.modules.payslips.infrastructure.queries import get_employee_payslips

LIGNE = {
    "id": "ps-1",
    "month": 3,
    "year": 2026,
    "pdf_storage_path": "c/e/bulletins/Bulletin_COTTE_Leo_03-2026.pdf",
    "payslip_data": {
        "net_a_payer": 1917.90,
        "alertes_baremes": [
            {
                "code": "transport_plafond_annuel_depasse",
                "critique": False,
                "a_arbitrer": True,
                "message": "Indemnité de transport : 700,00 € versés en 2026.",
            }
        ],
    },
    "manually_edited": False,
    "edit_count": 0,
    "edited_at": None,
    "edited_by": None,
}


def _patcher(reponses):
    chaine = MagicMock()
    for m in ("select", "eq", "order"):
        getattr(chaine, m).return_value = chaine
    chaine.execute.side_effect = reponses
    client = MagicMock()
    client.table.return_value = chaine
    urls = {LIGNE["pdf_storage_path"]: "https://exemple/bulletin.pdf"}
    return (
        patch("app.modules.payslips.infrastructure.queries.supabase", client),
        patch(
            "app.modules.payslips.infrastructure.queries.create_payslip_url_maps",
            return_value=(urls, urls),
        ),
        chaine,
    )


def test_l_origine_et_les_points_a_arbitrer_sont_dans_la_liste():
    p_supabase, p_urls, _ = _patcher([MagicMock(data=[{**LIGNE, "origine": "importe"}])])
    with p_supabase, p_urls:
        ligne = get_employee_payslips("e-1")[0]
    assert ligne["origine"] == "importe"
    assert ligne["points_a_arbitrer"] == [
        "Indemnité de transport : 700,00 € versés en 2026."
    ]
    assert ligne["warnings"] == []


def test_sans_la_colonne_origine_la_liste_sort_quand_meme():
    erreur = Exception("column payslips.origine does not exist")
    p_supabase, p_urls, chaine = _patcher([erreur, MagicMock(data=[LIGNE])])
    with p_supabase, p_urls:
        ligne = get_employee_payslips("e-1")[0]
    assert ligne["origine"] == "calcule"
    assert ligne["net_a_payer"] == 1917.90
    assert any("origine" in appel.args[0] for appel in chaine.select.call_args_list)
