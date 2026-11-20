"""R01 ne bloque plus la validation.

R01 compare le brut TOTAL au dernier bulletin validé, heures sup, primes et
absences comprises, et le contexte dit toujours « pas de changement de
contrat » (`has_contract_change: False`, comparison_service). Un mois avec
quelques heures sup dépasse 5 % de brut : la règle demandait un acquittement
pour presque chaque bulletin variable, dès qu'un mois précédent est validé.
Calculer un changement de contrat n'y changerait rien : ce sont les variables
du mois qui font bouger le brut. R01 devient un avertissement ; R03 (net à plus
de 10 %) reste critique et garde le filet.
"""

from __future__ import annotations

from app.modules.payslips.domain.comparison_engine import compute_comparison


def _ctx() -> dict:
    return {
        "bulletin_n_id": "n",
        "month_n": 10,
        "year_n": 2026,
        "bulletin_n1_id": "n1",
        "month_n1": 9,
        "year_n1": 2026,
        "is_forfait_jour": False,
        "has_contract_change": False,
        "has_declared_advance": None,
        "recent_nets_asc": [],
    }


def _bulletin(brut: float, net: float) -> dict:
    return {
        "salaire_brut": brut,
        "net_a_payer": net,
        "structure_cotisations": {"total_salarial": 400.0},
        "synthese_net": {},
        "calcul_du_brut": [{"type": "travail_base", "libelle": "Salaire de base", "quantite": 151.67}],
        "total_heures_supp": 0.0,
    }


def test_un_mois_d_heures_sup_ne_bloque_pas_la_validation():
    # Brut +8 % (heures sup), net +8 % : sous le seuil critique du net.
    resultat = compute_comparison(_bulletin(1944.0, 1512.0), _bulletin(1800.0, 1400.0), _ctx())
    r01 = [a for a in resultat.alerts if a.rule_id == "R01"]
    assert len(r01) == 1
    assert r01[0].level == "AVERTISSEMENT"
    assert resultat.has_critical is False


def test_r01_ne_pretend_plus_avoir_cherche_un_changement_de_contrat():
    resultat = compute_comparison(_bulletin(1944.0, 1512.0), _bulletin(1800.0, 1400.0), _ctx())
    r01 = next(a for a in resultat.alerts if a.rule_id == "R01")
    assert "contrat" not in r01.message


def test_le_net_a_plus_de_10_pourcent_reste_critique():
    resultat = compute_comparison(_bulletin(2100.0, 1600.0), _bulletin(1800.0, 1400.0), _ctx())
    r03 = [a for a in resultat.alerts if a.rule_id == "R03"]
    assert len(r03) == 1
    assert r03[0].level == "CRITIQUE"
    assert resultat.has_critical is True


def _net(net: float, brut: float = 2000.0) -> dict:
    return {"salaire_brut": brut, "net_a_payer": net, "total_cotisations_salariales": brut - net}


def test_mois_d_avant_incomplet_le_net_ne_se_compare_pas():
    """Entré le 28/09 : 3 jours en septembre, un mois plein en octobre (« +508 % »)."""
    contexte = {**_ctx(), "mois_precedent_incomplet": True}
    resultat = compute_comparison(_net(1567.04), _net(257.74, 330.0), contexte)
    assert not [a for a in resultat.alerts if a.rule_id in ("R01", "R02", "R03", "R04")]


def test_mois_d_avant_complet_le_net_reste_critique():
    resultat = compute_comparison(_net(1567.04), _net(257.74, 330.0), _ctx())
    assert [a.level for a in resultat.alerts if a.rule_id == "R03"] == ["CRITIQUE"]



def test_r03_face_a_un_mois_repris_n_est_qu_un_avertissement():
    """Zone 404, 17/11 : le premier mois calculé par Martine se comparait à
    septembre repris de Quadra ; un net à +60 % bloquait la validation."""
    ctx = {
        **_ctx(),
        "month_n": 10,
        "year_n": 2026,
        "month_n1": 8,
        "year_n1": 2026,
        "mois_precedent_repris": True,
        "month_repris": 9,
        "year_repris": 2026,
    }
    resultat = compute_comparison(_bulletin(3000.0, 2400.0), _bulletin(1800.0, 1500.0), ctx)
    r03 = [a for a in resultat.alerts if a.rule_id == "R03"]
    assert len(r03) == 1 and r03[0].level == "AVERTISSEMENT"
    # Le texte nomme le vrai mois comparé (août) et le mois repris (septembre).
    assert r03[0].message.endswith(
        "par rapport à août, dernier mois calculé par Martine "
        "(septembre vient de l'ancien logiciel)."
    )
    assert "par rapport au mois repris" not in r03[0].message
    assert resultat.has_critical is False


def test_r12_mois_precedent_repris_le_dit_au_lieu_d_aucun_bulletin():
    """Zone 404, 20/11 : premier mois calculé, septembre repris de Quadra ; le
    serveur disait « Aucun bulletin N-1 validé trouvé »."""
    ctx = {
        **_ctx(),
        "month_n": 10,
        "year_n": 2026,
        "mois_precedent_repris": True,
        "month_repris": 9,
        "year_repris": 2026,
    }
    resultat = compute_comparison(_bulletin(3000.0, 2400.0), None, ctx)
    r12 = [a.message for a in resultat.alerts if a.rule_id == "R12"]
    assert r12 == ["Septembre vient de l'ancien logiciel : pas de comparaison du net."]


def test_r12_mois_repris_d_une_autre_annee_porte_l_annee():
    ctx = {
        **_ctx(),
        "month_n": 1,
        "year_n": 2027,
        "mois_precedent_repris": True,
        "month_repris": 12,
        "year_repris": 2026,
    }
    resultat = compute_comparison(_bulletin(3000.0, 2400.0), None, ctx)
    r12 = [a.message for a in resultat.alerts if a.rule_id == "R12"]
    assert r12 == ["Décembre 2026 vient de l'ancien logiciel : pas de comparaison du net."]


def test_r12_sans_mois_repris_garde_son_texte():
    resultat = compute_comparison(_bulletin(3000.0, 2400.0), None, _ctx())
    r12 = [a.message for a in resultat.alerts if a.rule_id == "R12"]
    assert r12 == ["Aucun bulletin N-1 validé trouvé pour la comparaison."]


def test_r03_entre_deux_mois_de_martine_reste_critique():
    resultat = compute_comparison(_bulletin(3000.0, 2400.0), _bulletin(1800.0, 1500.0), _ctx())
    assert [a.level for a in resultat.alerts if a.rule_id == "R03"] == ["CRITIQUE"]


def test_mois_repris_entre_le_bulletin_de_comparaison_et_n(monkeypatch):
    """Le serveur exclut les bulletins repris de la comparaison (R-085) : il faut
    savoir si un mois repris tombe entre le bulletin comparé et N."""
    from unittest.mock import MagicMock

    from app.modules.payslips.infrastructure import comparison_queries as q

    chaine = MagicMock()
    for m in ("select", "eq", "or_"):
        getattr(chaine, m).return_value = chaine
    chaine.execute.return_value = MagicMock(data=[{"year": 2026, "month": 9}])
    sb = MagicMock()
    sb.table.return_value = chaine
    monkeypatch.setattr(q, "supabase", sb)
    # Septembre repris, aucun mois Martine avant : repris.
    assert q.mois_repris_entre("e", "c", None, 2026, 10) is True
    # Août calculé par Martine, septembre repris : repris.
    assert q.mois_repris_entre("e", "c", {"year": 2026, "month": 8}, 2026, 10) is True
    # Le bulletin comparé est postérieur au mois repris : non.
    assert q.mois_repris_entre("e", "c", {"year": 2026, "month": 9}, 2026, 11) is False
    # Le mois repris est nommé à l'écran : on le rend.
    assert q.dernier_mois_repris_entre("e", "c", None, 2026, 10) == (2026, 9)
    assert q.dernier_mois_repris_entre("e", "c", {"year": 2026, "month": 9}, 2026, 11) is None
