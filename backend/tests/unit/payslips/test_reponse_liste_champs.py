"""La ligne de liste d'un bulletin garde les champs que le service construit.

FastAPI retire de la réponse tout champ absent du `response_model`. Le service
`payslip_list_meta` produit `warnings` et `points_a_arbitrer`, le dépôt ajoute
`origine` : sans déclaration, l'écran ne voit rien — les boutons des bulletins
importés restaient cliquables et le point à arbitrer n'apparaissait pas
(constat d'Alexandre, 21/09/2026).
"""

from app.modules.payslips.schemas.responses import PayslipInfo

LIGNE = {
    "id": "ps-1",
    "name": "Bulletin_COTTE_Leo_03-2026.pdf",
    "month": 3,
    "year": 2026,
    "url": "https://exemple/bulletin.pdf",
    "net_a_payer": 1917.90,
    "warnings": ["Classification manquante."],
    "points_a_arbitrer": ["Indemnité de transport : 700,00 € versés en 2026."],
    "origine": "importe",
    "manually_edited": False,
    "edit_count": 0,
}


def test_l_origine_survit_au_schema():
    assert PayslipInfo(**LIGNE).model_dump()["origine"] == "importe"


def test_les_points_a_arbitrer_survivent_au_schema():
    rendu = PayslipInfo(**LIGNE).model_dump()
    assert rendu["points_a_arbitrer"] == [
        "Indemnité de transport : 700,00 € versés en 2026."
    ]
    assert rendu["warnings"] == ["Classification manquante."]


def test_un_bulletin_calcule_sans_point_a_arbitrer_reste_valide():
    minimal = {k: v for k, v in LIGNE.items() if k not in ("origine", "points_a_arbitrer")}
    rendu = PayslipInfo(**minimal).model_dump()
    assert rendu["origine"] == "calcule"
    assert rendu["points_a_arbitrer"] == []
