"""Un calcul qui n'a pas pu se faire se voit sur le bulletin (audit 25/09, B3 à B5).

Première étape, non bloquante : l'alerte est ajoutée aux alertes du bulletin,
que les RH voient à la génération. Les blocs concernés sont au cœur des
générateurs, que les tests unitaires n'exécutent pas en entier : une garde lit
donc aussi leur code source pour empêcher un retour au silence.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.modules.payroll.documents import (
    payslip_generator,
    payslip_generator_forfait,
    payslip_run_common,
    payslip_run_forfait,
    payslip_run_heures,
)
from app.modules.payroll.engine.controles_convention import avertissements_de_generation
from app.modules.payroll.engine.replis import (
    CODE_REPLI_AVANCES,
    CODE_REPLI_MAINTIEN,
    CODE_REPLI_SORTIE,
    ajouter_repli,
    alerte_de_repli,
    signaler_repli,
)


def test_un_repli_ajoute_une_seule_alerte_lisible():
    contexte = SimpleNamespace(alertes_baremes=[])
    signaler_repli(contexte, CODE_REPLI_MAINTIEN)
    signaler_repli(contexte, CODE_REPLI_MAINTIEN)
    assert [a["code"] for a in contexte.alertes_baremes] == [CODE_REPLI_MAINTIEN]
    assert "Maintien de salaire non calculé" in contexte.alertes_baremes[0]["message"]


def test_un_contexte_sans_liste_d_alertes_en_recoit_une():
    contexte = SimpleNamespace()
    signaler_repli(contexte, CODE_REPLI_SORTIE)
    assert contexte.alertes_baremes == [alerte_de_repli(CODE_REPLI_SORTIE)]


def test_les_rh_voient_les_trois_replis_a_la_generation():
    alertes: list = []
    for code in (CODE_REPLI_MAINTIEN, CODE_REPLI_AVANCES, CODE_REPLI_SORTIE):
        ajouter_repli(alertes, code)
    messages = avertissements_de_generation({"alertes_baremes": alertes})
    assert len(messages) == 3
    assert all("vérifier" in m for m in messages)


def test_une_sortie_illisible_ajoute_l_alerte_au_bulletin():
    sb = MagicMock()
    sb.table.side_effect = RuntimeError("base injoignable")
    alertes: list = []
    indemnites, blocage = payslip_run_common.resolve_exit_state_for_payslip(
        "emp-1", 2026, 8, sb, alertes=alertes
    )
    assert (indemnites, blocage) == (None, False)
    assert [a["code"] for a in alertes] == [CODE_REPLI_SORTIE]


def test_sans_liste_d_alertes_le_comportement_est_inchange():
    sb = MagicMock()
    sb.table.side_effect = RuntimeError("base injoignable")
    assert payslip_run_common.resolve_exit_state_for_payslip("emp-1", 2026, 8, sb) == (None, False)


def _bloc_except_apres(source: str, repere: str) -> str:
    debut = source.index(repere)
    fin = source.index("except", debut)
    return source[fin : fin + 900]


def test_le_maintien_avale_se_signale_heures_et_forfait():
    for module in (payslip_run_heures, payslip_run_forfait):
        bloc = _bloc_except_apres(inspect.getsource(module), "resultats_maintien = calculer_maintien(")
        assert "signaler_repli(contexte, CODE_REPLI_MAINTIEN)" in bloc, module.__name__
        assert "logging.exception" in bloc, module.__name__


def test_la_sortie_illisible_est_signalee_par_les_deux_calculs():
    for module in (payslip_run_heures, payslip_run_forfait):
        source = inspect.getsource(module)
        appel = source.index("= resolve_exit_state_for_payslip(")
        assert "alertes=contexte.alertes_baremes" in source[appel : appel + 400], module.__name__


def test_les_avances_avalees_se_signalent_sans_perdre_les_acomptes():
    source = inspect.getsource(payslip_generator)
    bloc = _bloc_except_apres(source, "get_advances_to_repay(employee_id, year, month)")
    assert 'saisies_data["acompte"] = net_a_payer_only_correction_total' in bloc
    assert 'saisies_data["acompte"] = 0.0' not in bloc
    assert "ajouter_repli(alertes_de_repli_generateur, CODE_REPLI_AVANCES)" in bloc
    source_forfait = inspect.getsource(payslip_generator_forfait)
    assert "ajouter_repli(alertes_de_repli_generateur, CODE_REPLI_AVANCES)" in source_forfait
    for s in (source, source_forfait):
        # Les replis du générateur rejoignent les alertes du bulletin, sans doublon.
        assert 'fusionner_replis(\n                payslip_json_data.get("alertes_baremes"), alertes_de_repli_generateur\n            )' in s
