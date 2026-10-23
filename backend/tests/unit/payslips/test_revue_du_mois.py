"""La revue du mois range les salariés comme le PDF et met les critiques d'abord."""

from __future__ import annotations

import pytest

from app.modules.payslips.domain.anomalies_bulletin import regles_acquittables
from app.modules.payslips.domain.revue_du_mois import personnes_a_relire, revue_du_mois

pytestmark = pytest.mark.unit


def _personne(identifiant: str, prenom: str, nom: str, **payslip_data) -> dict:
    return {
        "identifiant": identifiant,
        "prenom": prenom,
        "nom": nom,
        "payslip_data": {"salaire_brut": 1000.0, "calcul_du_brut": [{"libelle": "Salaire", "gain": 1000.0}], **payslip_data},
    }


def test_un_mois_juste_ne_donne_personne():
    assert revue_du_mois([_personne("a", "Ada", "Bernard")]) == []


def test_l_ordre_est_celui_du_pdf_et_les_critiques_passent_devant():
    avertie = _personne(
        "a",
        "Ada",
        "Martin",
        alertes_baremes=[{"code": "note_de_taux", "critique": False, "message": "Un taux est à relire."}],
    )
    decale = _personne(
        "b",
        "Léo",
        "Bernard",
        salaire_brut=1000.02,
        alertes_baremes=[
            {"code": "note_de_taux", "critique": False, "message": "Un taux est à relire."}
        ],
    )
    revues = revue_du_mois([avertie, decale])
    assert [revue.nom for revue in revues] == ["Bernard", "Martin"]
    niveaux = [alerte.level for alerte in revues[0].alertes]
    assert niveaux == ["CRITIQUE", "AVERTISSEMENT"]
    assert revues[0].alertes[0].rule_id == "B02"
    assert revues[0].alertes[1].rule_id == "note_de_taux"


def test_le_bulletin_le_plus_recent_est_relu_et_un_inconnu_est_laisse():
    salaries = [{"id": "e1", "first_name": "Ada", "last_name": "Bernard"}]
    bulletins = [
        {
            "id": "ancien",
            "employee_id": "e1",
            "updated_at": "2026-08-01",
            "payslip_data": {"salaire_brut": 1.0},
        },
        {
            "id": "recent",
            "employee_id": "e1",
            "updated_at": "2026-08-02",
            "payslip_data": {"salaire_brut": 2.0},
        },
        {"id": "hors", "employee_id": "e9", "payslip_data": {"salaire_brut": 9.0}},
    ]
    personnes = personnes_a_relire(salaries, bulletins)
    assert len(personnes) == 1
    assert personnes[0]["bulletin_id"] == "recent"
    assert personnes[0]["prenom"] == "Ada"
    assert personnes[0]["payslip_data"]["salaire_brut"] == 2.0


def test_les_regles_du_bulletin_s_acquittent_avec_celles_de_la_comparaison():
    regles = regles_acquittables()
    assert {"B01", "B02", "B03", "B04", "R01", "R12"} <= regles
    assert "R11" not in regles
    assert "B99" not in regles


def test_une_alerte_acquittee_sort_de_la_revue():
    personne = _personne(
        "b",
        "Léo",
        "Bernard",
        salaire_brut=1000.02,
        alerts_status={"B02": {"status": "acquittee", "comment": "Vu"}},
    )
    assert revue_du_mois([personne]) == []


def test_une_correction_en_attente_est_a_regarder():
    """Jeu du 23/10 : la liste de contrôle disait « 1 bulletin a une correction en
    attente », la revue « Rien à regarder ce mois-ci »."""
    en_attente = {
        "type": "correction",
        "ligne": "brut:hs25",
        "libelle": "Heures suppl. majorées à 25%",
        "motif": "Heures confirmées",
        "base": 8.0,
        "saisie_id": "c9",
        "raison": "La ligne visée n'est plus sur le bulletin.",
    }
    revues = revue_du_mois([_personne("a", "Ada", "Bernard", corrections_en_attente=[en_attente])])
    assert [r.identifiant for r in revues] == ["a"]
    alerte = revues[0].alertes[0]
    assert alerte.level == "CRITIQUE"
    assert alerte.rule_id not in regles_acquittables()
    assert "Heures suppl. majorées à 25%" in alerte.message
    assert "« Corriger »" in alerte.message
