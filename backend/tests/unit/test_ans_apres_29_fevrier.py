"""Une date d'embauche au 29 février ne fait plus planter le calcul des visites."""
from datetime import date

from app.modules.medical_follow_up.infrastructure.obligation_engine import _ans_apres


def test_un_29_fevrier_devient_le_28_hors_annee_bissextile():
    assert _ans_apres(date(2024, 2, 29), 5) == date(2029, 2, 28)


def test_une_date_ordinaire_avance_du_nombre_d_annees():
    assert _ans_apres(date(2024, 3, 15), 2) == date(2026, 3, 15)
