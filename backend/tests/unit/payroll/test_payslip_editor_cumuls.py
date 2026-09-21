"""Le PDF rendu après génération doit porter les cumuls du bulletin qu'il imprime.

Constat du 21/09/2026 (Cotte, juillet) : le rendu « enrichi » remplaçait les
cumuls du bulletin par ceux lus dans employee_schedules, encore ceux de la
génération précédente — le corps était à jour, les cumuls avaient une
génération de retard.
"""

from app.modules.payroll.documents.payslip_editor import cumuls_pour_le_rendu


def test_les_cumuls_du_bulletin_priment_sur_la_base():
    bulletin = {"cumuls": {"cumuls": {"brut_total": 17044.47}, "periode": {"dernier_mois_calcule": 7}}}
    en_base = {"cumuls": {"brut_total": 17030.93}}

    assert cumuls_pour_le_rendu(bulletin, en_base) == bulletin["cumuls"]


def test_sans_cumuls_dans_le_bulletin_on_lit_la_base():
    """Bulletins importés (reprise) : payslip_data n'a pas de bloc cumuls."""
    en_base = {"cumuls": {"brut_total": 14468.06}}

    assert cumuls_pour_le_rendu({"cumuls": None}, en_base) == en_base
    assert cumuls_pour_le_rendu({}, en_base) == en_base


def test_un_bloc_cumuls_vide_ne_prime_pas():
    en_base = {"cumuls": {"brut_total": 14468.06}}

    assert cumuls_pour_le_rendu({"cumuls": {}}, en_base) == en_base
    assert cumuls_pour_le_rendu({"cumuls": {"cumuls": {}}}, en_base) == en_base


def test_sans_rien_en_base_les_cumuls_du_bulletin_restent():
    bulletin = {"cumuls": {"cumuls": {"brut_total": 2576.41}}}

    assert cumuls_pour_le_rendu(bulletin, None) == bulletin["cumuls"]
