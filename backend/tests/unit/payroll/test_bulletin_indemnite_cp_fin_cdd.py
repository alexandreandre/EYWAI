"""Le moteur porte le détail de l'indemnité de CP de fin de CDD dans le bulletin."""

from app.modules.payroll.engine.bulletin import detail_indemnite_cp_fin_cdd


class _Contexte:
    pass


def test_le_detail_du_contexte_passe_dans_le_bulletin():
    contexte = _Contexte()
    contexte.detail_iccp_fin_cdd = {"methode": "salaire_retabli_solde_n1", "mention": "…"}
    assert detail_indemnite_cp_fin_cdd(contexte) == contexte.detail_iccp_fin_cdd


def test_sans_detail_rien():
    assert detail_indemnite_cp_fin_cdd(_Contexte()) is None
    contexte = _Contexte()
    contexte.detail_iccp_fin_cdd = "pas un dict"
    assert detail_indemnite_cp_fin_cdd(contexte) is None
