"""L'aperçu du bulletin (onglet « Bulletin ») ne dépend pas du stockage des PDF.

Relevé au tournage B.1-B.4 (19/10/2026) : « Aperçu indisponible pour le
moment » par intermittence, « Rafraîchir l'aperçu » le faisait revenir. La
route de l'aperçu lisait le bulletin par `get_payslip_details`, qui signe les
liens du PDF et de chaque version de l'historique : quatre appels au stockage
dont l'aperçu, rendu depuis les données enregistrées, n'a rien à faire. Un
appel au stockage qui échoue faisait tomber l'aperçu (500).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.payslips.api import router
from app.modules.payslips.infrastructure import queries as lectures

pytestmark = pytest.mark.unit

BULLETIN = {
    "id": "b-1",
    "employee_id": "e-1",
    "company_id": "c-1",
    "year": 2026,
    "month": 10,
    "pdf_storage_path": "c-1/2026/10/bulletin.pdf",
    "edit_history": [{"version": 1, "pdf_storage_path": "c-1/2026/10/v1.pdf"}],
    "payslip_data": {"salaire_brut": 2100.0, "net_a_payer": 1650.0},
}


class _Requete:
    def __init__(self, ligne):
        self._ligne = ligne

    def execute(self, *_a, **_k):
        return SimpleNamespace(data=self._ligne)

    def __call__(self, *_a, **_k):
        return self

    def __getattr__(self, _nom):
        return self


class _Base:
    """Le bulletin et ses cumuls existent ; seul le stockage tombe."""

    lignes = {"payslips": BULLETIN, "employee_schedules": {"cumuls": {"cumuls": {}}}}

    def table(self, nom, *_a, **_k):
        return _Requete(self.lignes[nom])

    @property
    def storage(self):
        raise ConnectionError("stockage injoignable")


@pytest.fixture
def base(monkeypatch):
    client = _Base()
    monkeypatch.setattr(lectures, "supabase", client)
    monkeypatch.setattr(
        "app.modules.payslips.infrastructure.storage_urls.supabase", client
    )
    monkeypatch.setattr(router, "_require_payslip_scope", lambda *_a, **_k: {"company_id": "c-1"})
    monkeypatch.setattr(
        "app.modules.payroll.documents.bulletin_view.construire_vue_bulletin",
        lambda donnees: {"brut": donnees.get("salaire_brut")},
    )
    return client


def test_l_apercu_se_rend_meme_si_le_stockage_ne_repond_pas(base, monkeypatch):
    rendus = []

    class _Gabarit:
        def render(self, vue):
            rendus.append(vue)
            return "<html>bulletin</html>"

    monkeypatch.setattr(
        "jinja2.Environment.get_template", lambda self, nom: _Gabarit()
    )
    reponse = router.preview_payslip_route(
        "b-1",
        router.PayslipPreviewRequest(pdf_notes=None),
        current_user=SimpleNamespace(id="u-1", active_company_id="c-1"),
    )
    assert reponse.html == "<html>bulletin</html>"
    assert rendus == [{"brut": 2100.0}]
