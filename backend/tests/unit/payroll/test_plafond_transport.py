"""Plafond annuel d'exonération de la prise en charge des trajets."""

from app.modules.payroll.engine.plafond_transport import (
    depassement_annuel,
    plafond_annuel_transport,
)

BAREME = {
    "FRAIS_PRO": [
        {
            "sections": {
                "mobilite_durable": {
                    "employeurs_prives": {
                        "limite_base": 600.0,
                        "limite_cumul_transport_public": 900.0,
                        "limite_cumul_carburant_total": 600.0,
                        "limite_cumul_carburant_part_carburant": 300.0,
                    }
                }
            }
        }
    ]
}


def test_plafond_de_base():
    assert plafond_annuel_transport(BAREME) == 600.0


def test_plafond_releve_en_cas_de_cumul_avec_abonnement_public():
    assert plafond_annuel_transport(BAREME, avec_abonnement_public=True) == 900.0


def test_bareme_absent_donne_none():
    assert plafond_annuel_transport(None) is None
    assert plafond_annuel_transport({"FRAIS_PRO": []}) is None
    assert plafond_annuel_transport({"FRAIS_PRO": [{"sections": {}}]}) is None


def test_depassement_girerd_3000_euros_par_an():
    """GIRERD Fabrice, Colorplast : 250 €/mois soit 3 000 €/an."""
    assert depassement_annuel(3000.0, 600.0) == 2400.0


def test_depassement_espinosa_1200_euros_par_an():
    """ESPINOSA Anthony, Colorplast : 100 €/mois soit 1 200 €/an."""
    assert depassement_annuel(1200.0, 600.0) == 600.0


def test_pas_de_depassement_sous_le_plafond():
    assert depassement_annuel(500.0, 600.0) == 0.0


def test_pas_de_depassement_au_plafond_exact():
    assert depassement_annuel(600.0, 600.0) == 0.0


def test_plafond_inconnu_ne_signale_aucun_depassement():
    """Sans barème, on ne peut rien affirmer : ne pas alerter à tort."""
    assert depassement_annuel(3000.0, None) == 0.0


# --- Contrôle non bloquant --------------------------------------------------

from app.modules.payroll.engine.controles_convention import (  # noqa: E402
    controle_plafond_transport,
)


def test_aucune_alerte_sous_le_plafond():
    assert controle_plafond_transport(500.0, BAREME, annee=2026) == []


def test_alerte_au_dessus_du_plafond():
    alertes = controle_plafond_transport(3000.0, BAREME, annee=2026)
    assert len(alertes) == 1
    alerte = alertes[0]
    assert alerte["code"] == "transport_plafond_annuel_depasse"
    assert alerte["critique"] is True
    message = alerte["message"].replace(" ", " ").replace("\xa0", " ")
    assert "2 400,00" in message
    assert "600,00" in message
    assert "2026" in message


def test_aucune_alerte_sans_bareme():
    assert controle_plafond_transport(3000.0, None, annee=2026) == []


def test_plafond_releve_evite_l_alerte():
    """Avec abonnement public, le plafond passe à 900 € : 800 € ne dépasse plus."""
    alertes = controle_plafond_transport(
        800.0, BAREME, avec_abonnement_public=True, annee=2026
    )
    assert alertes == []


def test_alerte_ne_modifie_pas_le_bulletin():
    """Le contrôle rend seulement un message : il ne renvoie aucun montant à
    réintégrer. La décision de régulariser appartient à la RH et au cabinet."""
    alerte = controle_plafond_transport(3000.0, BAREME, annee=2026)[0]
    assert set(alerte) == {
        "code",
        "critique",
        "severity",
        "message",
        "donnee_non_officielle",
    }
