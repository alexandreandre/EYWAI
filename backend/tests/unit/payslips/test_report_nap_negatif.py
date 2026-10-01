"""État du report d'un net négatif sur le mois suivant, tel que l'écran le lit."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.payslips.application.report_nap_negatif import (
    ReportNapRefuse,
    construire_etat_du_report,
    decider_ecriture_du_report,
    executer_report,
)

pytestmark = pytest.mark.unit

META_SEPTEMBRE = {"company_id": "co-1", "employee_id": "emp-1", "year": 2026, "month": 9}

REPORT = {
    "id": "s-2",
    "name": "Mon report",
    "amount": -115.43,
    "catalog_prime_id": "report_nap_negatif",
    "sur_le_net": True,
}
ACOMPTE = {
    "id": "s-1",
    "name": "Acompte",
    "amount": -300.0,
    "sur_le_net": True,
}
MESSAGE_ACOMPTE = (
    "Une retenue sur le net de 300,00 € existe déjà en octobre 2026, sous un autre nom. "
    "Ouvrez les saisies avant d’ajouter le report."
)
MESSAGE_DOUBLONS = (
    "Plusieurs reports existent déjà en octobre 2026 : 115,43 € et 100,00 €. "
    "Chacun est déduit du net tant que la ligne existe. "
    "Ouvrez les saisies pour n’en garder qu’un."
)


def _etat(net=-115.43, saisies=(), statut_suivant=None, cloture=False, meta=META_SEPTEMBRE):
    return construire_etat_du_report(
        "ps-1",
        meta,
        net_a_payer=net,
        saisies_mois_suivant=list(saisies),
        statut_bulletin_suivant=statut_suivant,
        mois_suivant_cloture=cloture,
    )


def test_sans_report_l_etat_donne_le_montant_et_le_mois_suivant():
    etat = _etat()
    assert etat["montant_a_reporter"] == 115.43
    assert (etat["annee_suivante"], etat["mois_suivant"]) == (2026, 10)
    assert etat["nom_du_report"] == "Report NAP négatif 09/2026"
    assert etat["saisie"] is None
    assert etat["saisies"] == []
    assert etat["autre_retenue_sur_le_net"] is None
    assert etat["verrou"] is None
    assert etat["company_id"] == "co-1"


def test_le_report_existant_est_retrouve_par_son_marqueur():
    etat = _etat(saisies=[ACOMPTE, REPORT])
    attendu = {"id": "s-2", "name": "Mon report", "amount": -115.43}
    assert etat["saisie"] == attendu
    assert etat["saisies"] == [attendu]
    assert etat["autre_retenue_sur_le_net"] == {
        "id": "s-1",
        "name": "Acompte",
        "amount": -300.0,
    }


def test_le_report_d_un_autre_mois_n_est_pas_celui_de_ce_bulletin():
    etat = _etat(saisies=[{"id": "s-3", "name": "Report NAP négatif 08/2026", "amount": -50.0}])
    assert etat["saisie"] is None
    assert etat["saisies"] == []


def test_plusieurs_reports_reconnus_sont_tous_nommes():
    etat = _etat(
        saisies=[
            {**REPORT, "id": "s-a", "name": "Report NAP négatif 09/2026", "amount": -115.43},
            {**REPORT, "id": "s-b", "name": "Report NAP négatif 09/2026", "amount": -100.0},
        ]
    )
    assert [s["id"] for s in etat["saisies"]] == ["s-a", "s-b"]
    assert etat["saisie"] == etat["saisies"][0]


def test_une_retenue_sous_un_autre_nom_n_est_pas_un_report():
    etat = _etat(saisies=[ACOMPTE])
    assert etat["saisie"] is None
    assert etat["saisies"] == []
    assert etat["autre_retenue_sur_le_net"]["amount"] == -300.0


def test_decembre_reporte_sur_janvier():
    etat = _etat(meta={**META_SEPTEMBRE, "month": 12})
    assert (etat["annee_suivante"], etat["mois_suivant"]) == (2027, 1)
    assert etat["nom_du_report"] == "Report NAP négatif 12/2026"


@pytest.mark.parametrize(
    ("statut", "cloture", "verrou"),
    [("valide", False, "bulletin_valide"), (None, True, "mois_cloture"), ("brouillon", False, None)],
)
def test_le_verrou_dit_pourquoi_on_ne_peut_plus_reporter(statut, cloture, verrou):
    assert _etat(statut_suivant=statut, cloture=cloture)["verrou"] == verrou


def test_un_net_positif_n_a_rien_a_reporter():
    assert _etat(net=12.0)["montant_a_reporter"] == 0.0


def test_la_route_masque_un_bulletin_d_une_autre_societe():
    from app.modules.payslips.api.router import get_report_net_negatif_route

    user = SimpleNamespace(active_company_id="co-1")
    with patch(
        "app.modules.payslips.api.router.get_payslip_meta_for_access",
        return_value={"company_id": "co-2", "employee_id": "emp-2", "year": 2026, "month": 9},
    ):
        with pytest.raises(HTTPException) as exc:
            get_report_net_negatif_route("ps-1", current_user=user)
    assert exc.value.status_code == 404


def test_creer_sans_saisie_prepare_une_insertion():
    d = decider_ecriture_du_report("creer", _etat())
    assert d.refus is None
    assert d.op == "creer"
    assert d.payload["name"] == "Report NAP négatif 09/2026"
    assert d.payload["amount"] == -115.43
    assert d.payload["sur_le_net"] is True
    assert d.payload["catalog_prime_id"] == "report_nap_negatif"


def test_creer_quand_le_report_existe_deja_au_meme_montant_ne_fait_rien():
    d = decider_ecriture_du_report("creer", _etat(saisies=[REPORT]))
    assert d.refus is None
    assert d.op == "noop"
    assert d.saisie_id == "s-2"


def test_creer_quand_le_montant_a_change_met_a_jour_la_meme_saisie():
    d = decider_ecriture_du_report("creer", _etat(saisies=[{**REPORT, "amount": -100.0}]))
    assert d.refus is None
    assert d.op == "mettre_a_jour"
    assert d.saisie_id == "s-2"
    assert d.amount == -115.43


def test_creer_face_a_une_retenue_sous_un_autre_nom_refuse_sans_ecrire():
    d = decider_ecriture_du_report("creer", _etat(saisies=[ACOMPTE]))
    assert d.op is None
    assert d.refus == MESSAGE_ACOMPTE


def test_creer_face_a_plusieurs_reports_refuse_sans_ajouter():
    d = decider_ecriture_du_report(
        "creer",
        _etat(
            saisies=[
                {**REPORT, "id": "s-a", "amount": -115.43},
                {**REPORT, "id": "s-b", "name": "Report NAP négatif 09/2026", "amount": -100.0},
            ]
        ),
    )
    assert d.op is None
    assert d.refus == MESSAGE_DOUBLONS


def test_le_verrou_refuse_creation_mise_a_jour_et_suppression():
    etat = _etat(saisies=[REPORT], statut_suivant="valide")
    for action in ("creer", "mettre_a_jour", "supprimer"):
        d = decider_ecriture_du_report(action, etat)
        assert d.op is None
        assert d.refus == (
            "Le bulletin d’octobre 2026 est déjà validé : "
            + (
                "impossible d’en retirer le report."
                if action == "supprimer"
                else "impossible d’y reporter la somme."
            )
        )


def test_le_verrou_cloture_refuse_aussi():
    d = decider_ecriture_du_report("creer", _etat(cloture=True))
    assert d.refus == "La paie d’octobre 2026 est clôturée : impossible d’y reporter la somme."


def test_un_second_appel_ne_cree_pas_une_seconde_ligne():
    sans = _etat()
    avec = _etat(saisies=[REPORT])
    with patch(
        "app.modules.payslips.application.report_nap_negatif.lire_etat_du_report",
        side_effect=[sans, avec, avec],
    ):
        with patch(
            "app.modules.payslips.application.report_nap_negatif.create_employee_monthly_input"
        ) as creer:
            creer.return_value = SimpleNamespace(inserted_data=REPORT)
            executer_report("creer", "ps-1", META_SEPTEMBRE)
            executer_report("creer", "ps-1", META_SEPTEMBRE)
    assert creer.call_count == 1


def test_une_retenue_etrangere_n_ecrit_rien():
    with patch(
        "app.modules.payslips.application.report_nap_negatif.lire_etat_du_report",
        return_value=_etat(saisies=[ACOMPTE]),
    ):
        with patch(
            "app.modules.payslips.application.report_nap_negatif.create_employee_monthly_input"
        ) as creer:
            with pytest.raises(ReportNapRefuse, match="sous un autre nom"):
                executer_report("creer", "ps-1", META_SEPTEMBRE)
            creer.assert_not_called()


def test_un_ecran_perime_ne_peut_pas_ecrire_si_le_bulletin_suivant_est_valide():
    with patch(
        "app.modules.payslips.application.report_nap_negatif.lire_etat_du_report",
        return_value=_etat(statut_suivant="valide"),
    ):
        with patch(
            "app.modules.payslips.application.report_nap_negatif.create_employee_monthly_input"
        ) as creer:
            with pytest.raises(ReportNapRefuse, match="déjà validé"):
                executer_report("creer", "ps-1", META_SEPTEMBRE)
            creer.assert_not_called()


def test_un_bulletin_valide_a_cote_d_un_brouillon_verrouille():
    from app.modules.payslips.infrastructure.queries import get_payslip_status_for_period

    chaine = MagicMock()
    for m in ("select", "match", "eq", "limit", "execute"):
        getattr(chaine, m).return_value = chaine
    chaine.execute.return_value = MagicMock(
        data=[{"status": "brouillon"}, {"status": "valide"}]
    )
    client = MagicMock()
    client.table.return_value = chaine
    with patch("app.modules.payslips.infrastructure.queries.supabase", client):
        assert get_payslip_status_for_period("emp-1", "co-1", 2026, 10) == "valide"
    chaine.limit.assert_not_called()


def test_la_lecture_du_mois_groupe_les_saisies_par_salarie():
    from app.modules.payslips.application.report_nap_negatif import lire_etats_du_mois

    bulletin = {
        "id": "ps-1",
        "company_id": "co-1",
        "employee_id": "emp-1",
        "year": 2026,
        "month": 9,
        "net_a_payer": -115.43,
    }
    with patch(
        "app.modules.payslips.infrastructure.queries.get_payslips_meta_for_period",
        return_value=[bulletin],
    ), patch(
        "app.modules.payslips.infrastructure.queries.get_report_candidates_for_company_period",
        return_value=[
            {**REPORT, "employee_id": "emp-1"},
            {**ACOMPTE, "employee_id": "emp-autre"},
        ],
    ), patch(
        "app.modules.payslips.infrastructure.queries.get_payslip_statuses_by_employee_for_period",
        return_value={"emp-1": ["brouillon"]},
    ), patch(
        "app.modules.payroll.infrastructure.analytics_repository.payroll_analytics_repository.is_period_closed",
        return_value=False,
    ):
        etats = lire_etats_du_mois("co-1", 2026, 9)
    assert len(etats) == 1
    assert etats[0]["saisie"]["id"] == "s-2"
    assert etats[0]["autre_retenue_sur_le_net"] is None
