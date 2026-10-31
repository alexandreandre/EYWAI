"""Date de remise d'un bulletin au salarié (D5) et message du bulletin figé (D4)."""

from datetime import date

import pytest

from app.modules.payslips.domain.mise_a_disposition import (
    CLE_REGLAGE,
    bulletins_remis,
    jour_de_mise_a_disposition,
    message_bulletin_remis,
    remis_le,
    remis_le_du_bulletin,
)


def _remis(**kwargs):
    base = {
        "year": 2026,
        "month": 10,
        "statut": "valide",
        "valide_le": date(2026, 10, 28),
        "jour": 1,
        "bulletin_de_sortie": False,
    }
    return remis_le(**{**base, **kwargs})


def test_sans_reglage_le_bulletin_est_remis_le_1er_du_mois_suivant():
    assert jour_de_mise_a_disposition({}) == 1
    assert jour_de_mise_a_disposition(None) == 1
    assert _remis() == date(2026, 11, 1)


def test_le_jour_regle_du_mois_suivant():
    assert jour_de_mise_a_disposition({CLE_REGLAGE: 5}) == 5
    assert _remis(jour=5) == date(2026, 11, 5)


def test_zero_veut_dire_des_la_validation():
    assert jour_de_mise_a_disposition({CLE_REGLAGE: 0}) == 0
    assert _remis(jour=0) == date(2026, 10, 28)


def test_valide_apres_la_date_le_bulletin_est_remis_a_sa_validation():
    assert _remis(valide_le=date(2026, 11, 3)) == date(2026, 11, 3)


def test_decembre_est_remis_en_janvier():
    assert _remis(month=12, valide_le=date(2026, 12, 29)) == date(2027, 1, 1)


def test_le_bulletin_de_sortie_est_remis_des_sa_validation():
    assert _remis(bulletin_de_sortie=True, valide_le=date(2026, 10, 18)) == date(2026, 10, 18)


def test_un_brouillon_n_est_jamais_remis():
    assert _remis(statut="brouillon") is None


def test_valide_sans_date_de_validation_vaut_la_date_du_mois():
    assert _remis(valide_le=None) == date(2026, 11, 1)
    assert _remis(valide_le=None, jour=0) == date(2026, 11, 1)


@pytest.mark.parametrize("valeur, attendu", [(40, 28), (-3, 1), ("x", 1), (True, 1), ("7", 7)])
def test_un_reglage_illisible_retombe_dans_les_bornes(valeur, attendu):
    assert jour_de_mise_a_disposition({CLE_REGLAGE: valeur}) == attendu


def test_le_message_dit_la_date_et_le_mois_de_la_correction():
    assert message_bulletin_remis(2026, 10, date(2026, 11, 1)) == (
        "Ce bulletin a été remis au salarié le 01/11/2026 : il ne se modifie plus. "
        "Une erreur se corrige sur le bulletin de novembre 2026, par une régularisation."
    )
    assert "janvier 2027" in message_bulletin_remis(2026, 12, date(2027, 1, 1))


def _ligne(**kwargs):
    base = {
        "year": 2026,
        "month": 10,
        "status": "valide",
        "validated_at": "2026-10-28T16:00:00+00:00",
        "payslip_data": {},
    }
    return {**base, **kwargs}


def test_la_remise_se_lit_sur_la_ligne_du_bulletin():
    assert remis_le_du_bulletin(_ligne(), jour=1) == date(2026, 11, 1)
    assert remis_le_du_bulletin(_ligne(status="brouillon"), jour=1) is None


def test_la_validation_compte_a_l_heure_de_paris():
    # 23 h 30 UTC le 31/10 = 0 h 30 le 01/11 à Paris.
    ligne = _ligne(validated_at="2026-10-31T23:30:00+00:00")
    assert remis_le_du_bulletin(ligne, jour=0) == date(2026, 11, 1)


def test_la_marque_de_sortie_se_lit_dans_les_donnees_du_bulletin():
    ligne = _ligne(validated_at="2026-10-18T09:00:00+00:00", payslip_data={"bulletin_de_sortie": True})
    assert remis_le_du_bulletin(ligne, jour=1) == date(2026, 10, 18)


def test_le_salarie_ne_voit_que_les_bulletins_remis():
    lignes = [
        _ligne(month=9, validated_at="2026-10-03T08:00:00+00:00"),
        _ligne(),
        _ligne(month=8, status="brouillon"),
    ]
    assert bulletins_remis(lignes, jour=1, aujourd_hui=date(2026, 10, 31)) == [lignes[0]]
    assert bulletins_remis(lignes, jour=1, aujourd_hui=date(2026, 11, 1)) == lignes[:2]


def test_a_notifier_les_bulletins_remis_depuis_peu_et_pas_encore_notifies():
    from app.modules.payslips.domain.mise_a_disposition import a_notifier

    du_jour = _ligne()
    deja = _ligne(month=9, validated_at="2026-10-03T08:00:00+00:00",
                  payslip_data={"salarie_notifie_le": "2026-10-03T10:00:00"})
    trop_vieux = _ligne(month=8, validated_at="2026-09-02T08:00:00+00:00")
    pas_encore = _ligne(month=11, validated_at="2026-11-01T08:00:00+00:00")
    lignes = [du_jour, deja, trop_vieux, pas_encore]
    assert a_notifier(lignes, jour=1, aujourd_hui=date(2026, 11, 1)) == [du_jour]
