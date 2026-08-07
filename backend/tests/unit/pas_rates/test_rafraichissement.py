"""Le taux PAS se rafraîchit même quand l'import DSN n'écrit pas la fiche.

Cas réel à l'origine du besoin : ANDRE Elsa, fiche créée en janvier avec 10,50 %,
puis DSN de février à mai portant 13,30 % — quatre imports, quatre « ignorer »,
aucune écriture. Le taux est resté quatre mois sur la valeur de janvier.
"""

from unittest.mock import patch

from app.modules.pas_rates.application import rafraichissement


def _payload(taux, type_taux="01", identifiant="ID-1"):
    return {
        "specificites_paie": {
            "prelevement_a_la_source": {
                "taux": taux,
                "type_taux": type_taux,
                "identifiant_taux": identifiant,
            }
        }
    }


def _salarie(taux, type_taux="01", periode="2026-01"):
    bloc = {"taux": taux, "type_taux": type_taux}
    if periode:
        bloc["periode"] = periode
    return {"id": "emp-1", "specificites_paie": {"prelevement_a_la_source": bloc}}


def _appel(payload, salarie, periode="2026-05"):
    with patch.object(rafraichissement.repo, "enregistrer_taux") as hist, patch.object(
        rafraichissement.repo, "maj_taux_courant"
    ) as maj:
        ecrit = rafraichissement.rafraichir_depuis_import(
            "co-1", salarie, payload, periode, "2026-05.dsn", "user-1"
        )
    return ecrit, hist, maj


def test_taux_different_est_ecrit():
    ecrit, hist, maj = _appel(_payload(13.30), _salarie(10.50))
    assert ecrit is True
    maj.assert_called_once()
    assert maj.call_args[0][1] == 13.30
    entree = hist.call_args[0][0][0]
    assert entree["periode"] == "2026-05"
    assert entree["source"] == "dsn"
    assert entree["source_fichier"] == "2026-05.dsn"


def test_taux_identique_et_deja_date_n_ecrit_rien():
    ecrit, hist, maj = _appel(_payload(13.30), _salarie(13.30, periode="2026-05"))
    assert ecrit is False
    hist.assert_not_called()
    maj.assert_not_called()


def test_taux_identique_mais_non_date_est_ecrit():
    """Un taux sans période doit être daté, même s'il ne change pas de valeur."""
    ecrit, _, maj = _appel(_payload(13.30), _salarie(13.30, periode=None))
    assert ecrit is True
    maj.assert_called_once()


def test_changement_de_type_seul_est_ecrit():
    """Passer du barème au taux DGFiP compte, même à valeur égale."""
    ecrit, _, maj = _appel(
        _payload(5.70, type_taux="01"),
        _salarie(5.70, type_taux="13", periode="2026-01"),
    )
    assert ecrit is True


def test_taux_zero_est_ecrit():
    """Un taux qui retombe à 0 % est un taux, pas une absence."""
    ecrit, _, maj = _appel(_payload(0.0), _salarie(5.40))
    assert ecrit is True
    assert maj.call_args[0][1] == 0.0


def test_dsn_plus_ancienne_ne_fait_pas_reculer_le_taux():
    """Les mois d'un même lot ne sont pas toujours importés dans l'ordre."""
    ecrit, hist, maj = _appel(
        _payload(10.50), _salarie(13.30, periode="2026-05"), periode="2026-02"
    )
    assert ecrit is False
    maj.assert_not_called()


def test_payload_sans_taux_ne_touche_rien():
    ecrit, hist, maj = _appel({"specificites_paie": {}}, _salarie(13.30))
    assert ecrit is False
    maj.assert_not_called()


def test_sans_periode_on_s_abstient():
    ecrit, hist, maj = _appel(_payload(13.30), _salarie(10.50), periode=None)
    assert ecrit is False
    maj.assert_not_called()
