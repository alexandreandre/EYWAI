"""La fin connue d'un contrat (05/11/2026) : ce qui décide si une lettre peut dire « fait partie des effectifs »."""
from __future__ import annotations

from datetime import date

import pytest

from app.modules.documents.domain.fin_de_contrat import fin_de_contrat, terme_du_contrat

pytestmark = pytest.mark.unit

ENTREE = "2024-01-15"


def test_le_dernier_jour_d_un_depart_fait_foi():
    fiche = {"contract_type": "CDI", "hire_date": ENTREE}
    assert fin_de_contrat(fiche, date(2026, 10, 31)) == date(2026, 10, 31)


def test_un_ancien_depart_ne_compte_pas_pour_un_salarie_revenu():
    fiche = {"contract_type": "CDI", "hire_date": ENTREE}
    assert fin_de_contrat(fiche, date(2023, 6, 30)) is None


def test_le_terme_d_un_cdd():
    fiche = {"contract_type": "CDD", "hire_date": ENTREE, "contract_end_date": "2026-06-30"}
    assert fin_de_contrat(fiche, None) == date(2026, 6, 30)
    assert terme_du_contrat(fiche) == date(2026, 6, 30)


def test_un_terme_anterieur_a_l_entree_est_perime():
    fiche = {"contract_type": "CDD", "hire_date": ENTREE, "contract_end_date": "2023-06-30"}
    assert fin_de_contrat(fiche, None) is None


def test_un_cdi_n_a_pas_de_terme():
    """L'écran ne montre pas ce champ pour un CDI, et le vide à l'enregistrement."""
    fiche = {"contract_type": "CDI", "hire_date": ENTREE, "contract_end_date": "2026-06-30"}
    assert terme_du_contrat(fiche) is None
    assert fin_de_contrat(fiche, None) is None


def test_le_terme_d_un_apprenti():
    fiche = {
        "contract_type": "apprentissage",
        "hire_date": ENTREE,
        "contract_end_date": None,
        "specificites_paie": {"dsn_reprise": {"date_fin_contrat": "2026-08-31"}},
    }
    assert terme_du_contrat(fiche) == date(2026, 8, 31)


def test_sans_date():
    assert fin_de_contrat({"contract_type": "CDD", "hire_date": ENTREE}, None) is None
