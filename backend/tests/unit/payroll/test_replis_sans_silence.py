"""Plus d'état silencieux : une lecture ratée garde le calcul, et le bulletin le dit.

Audit du 17/11/2026 : six endroits rendaient une valeur par défaut sans aucun
signal (maintien en jours ouvrés, heures structurelles d'un jour maintenu,
bruts de référence des IJSS, congés posés au planning, règles de convention,
politique de congés au départ). Le comportement ne change pas (sauf le taux
horaire du maintien, qui prenait un montant par jour pour un taux par heure) ;
chacun pose maintenant son alerte de repli.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.payroll.engine import replis
from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _codes(alertes) -> list[str]:
    return [a.get("code") for a in alertes]


def _collecte(fonction):
    """Lance `fonction` dans une collecte de génération, rend les codes notés."""
    alertes: list = []
    jeton = replis.ouvrir_collecte(alertes)
    try:
        fonction()
    finally:
        replis.fermer_collecte(jeton)
    return _codes(alertes)


def _arret_jours_ouvres():
    return {
        "arret_type": "maladie_simple",
        "date_debut": "2026-08-03",
        "date_fin": "2026-08-14",
        "subrogation_active": False,
        "nombre_enfants": 0,
        "salaire_periode_reelle": 0.0,
        "arrets_connus": [{"debut": "2026-08-03", "fin": "2026-08-14", "type": "maladie_simple"}],
        "maintien_base_ouvree": True,
    }


def test_taux_horaire_illisible_en_jours_ouvres_ne_maintient_pas_sept_fois_trop():
    contexte = build_test_contexte(salaire_base=3042.0, duree_hebdo=35.0, date_entree="2010-01-04")
    with patch(
        "app.modules.payroll.engine.calcul_brut._get_salaire_horaire_base",
        side_effect=ValueError("taux illisible"),
    ):
        resultat = calculer_maintien(
            _arret_jours_ouvres(), contexte, {}, date(2026, 8, 1), date(2026, 8, 31)
        )
    assert "repli_taux_horaire_maintien" in _codes(contexte.alertes_baremes)
    # L'ancien repli valait 3 042 ÷ 30,42 = 100 € « de l'heure », × 7 h par jour.
    assert float((resultat.get("maintien") or {}).get("maintien_verse") or 0.0) < 700.0


def test_heures_structurelles_illisibles_se_signalent():
    from app.modules.payroll.engine.maintien_salaire_service import (
        _quote_part_hs_structurelles_journaliere,
    )

    contexte = build_test_contexte(salaire_base=2000.0, duree_hebdo=39.0)
    with patch(
        "app.modules.payroll.engine.calcul_brut.compute_hs_structurelles_mensuelles",
        side_effect=ValueError("illisible"),
    ):
        _quote_part_hs_structurelles_journaliere(contexte, 39.0, 13.0)
    assert "repli_heures_structurelles_maintien" in _codes(contexte.alertes_baremes)


def test_bruts_de_reference_des_ijss_illisibles_se_signalent():
    from app.modules.payroll.infrastructure import salaires_de_reference as module

    arret = {"date_debut": "2026-08-03", "arrets_connus": []}
    with patch.object(module, "salaires_bruts_de_reference", side_effect=ConnectionError("base")):
        codes = _collecte(lambda: module.poser_salaires_de_reference(arret, "salarie-1"))
    assert codes == ["repli_bruts_reference_ijss"]
    assert "salaires_bruts_reference" not in arret


def test_conges_du_planning_illisibles_se_signalent():
    from app.modules.absences.infrastructure import repository as module

    with patch.object(module._planning_cache, "get_or_load", side_effect=ConnectionError("base")):
        codes = _collecte(lambda: module._with_planning_conges_payes([{"id": "a"}], ["salarie-1"]))
    assert codes == ["repli_conges_du_planning"]


def test_regles_de_convention_illisibles_se_signalent():
    from app.modules.collective_agreements.rules.repository import (
        CCRulesRepository,
    )

    class _Panne:
        def table(self, *_a):
            raise ConnectionError("base")

    depot = CCRulesRepository(supabase_client=_Panne())
    codes = _collecte(lambda: depot.get_rules_by_idcc("1486"))
    assert codes == ["repli_convention_collective"]


def test_hors_d_un_bulletin_une_lecture_ratee_ne_pose_rien():
    """`noter_repli` ne fait rien sans génération en cours : l'écran ne change pas."""
    from app.modules.collective_agreements.rules.repository import (
        CCRulesRepository,
    )

    class _Panne:
        def table(self, *_a):
            raise ConnectionError("base")

    assert CCRulesRepository(supabase_client=_Panne()).get_rules_by_idcc("1486") is None


def test_politique_de_conges_illisible_au_depart_se_signale():
    from app.modules.payroll.engine import calcul_indemnites_sortie as module

    with patch(
        "app.modules.absences.infrastructure.leave_settings_repository.get_leave_policy",
        side_effect=ConnectionError("base"),
    ):
        codes = _collecte(lambda: module._rythme_des_conges({"company_id": "societe-1"}))
    assert codes == ["repli_reglages_conges"]
