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
    "name": "Bulletin_FERISSE_Leo_03-2026.pdf",
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


def test_a_recalculer_survit_au_schema():
    rendu = PayslipInfo(**{**LIGNE, "a_recalculer": True, "salaire_brut": 1800.0, "heures_sup": 2.0}).model_dump()
    assert rendu["a_recalculer"] is True
    assert rendu["salaire_brut"] == 1800.0
    assert rendu["heures_sup"] == 2.0
    minimal = {k: v for k, v in LIGNE.items() if k not in ("origine", "points_a_arbitrer")}
    rendu = PayslipInfo(**minimal).model_dump()
    assert rendu["origine"] == "calcule"
    assert rendu["points_a_arbitrer"] == []
    assert rendu["a_recalculer"] is None


def test_le_statut_valide_survit_au_schema():
    """La liste de la paie du mois montre « Validé » et propose de valider le reste
    (revue du 05/10) : le dépôt lit `status`, le schéma doit le garder."""
    assert PayslipInfo(**{**LIGNE, "status": "valide"}).model_dump()["status"] == "valide"
    assert PayslipInfo(**LIGNE).model_dump()["status"] is None
