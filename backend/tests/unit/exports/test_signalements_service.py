from datetime import date
from unittest.mock import patch

import pytest

from app.modules.exports.application import signalements as service

MODULE = "app.modules.exports.application.signalements"


def _arret(du, au, saisi):
    jours = [date.fromordinal(o).isoformat() for o in range(du.toordinal(), au.toordinal() + 1)]
    return {"employee_id": "e1", "type": "arret_maladie", "selected_days": jours,
            "subrogation_active": False, "arret_type": None, "created_at": f"{saisi}T09:00:00+00:00"}


@pytest.fixture
def base():
    with patch(f"{MODULE}._arrets", return_value=[_arret(date(2026, 10, 5), date(2026, 10, 9), "2026-10-06")]), \
         patch(f"{MODULE}._envoyes", return_value=[]), \
         patch(f"{MODULE}._depuis", return_value=date(2026, 10, 1)), \
         patch(f"{MODULE}._effectif", return_value=20), \
         patch(f"{MODULE}._noms", return_value={"e1": "A. T."}), \
         patch(f"{MODULE}._sorties", return_value=[]), \
         patch(f"{MODULE}._contrats", return_value=[]), \
         patch(f"{MODULE}._bulletins", return_value=set()):
        yield


def test_la_liste_dit_la_date_limite_et_le_retard(base):
    resultat = service.lister("c1", aujourd_hui=date(2026, 10, 12))
    (ligne,) = resultat["a_faire"]
    assert ligne["nature"] == "04" and ligne["a_deposer_avant"] == "2026-10-11"
    assert ligne["en_retard"] is True and ligne["salarie"] == "A. T."
    assert ligne["a_verifier"] is None


def test_le_fichier_reel_se_genere_et_dit_la_date_limite(base):
    # Décision du 30/10 : DSN-VAL embarque les contrôles du point de dépôt et
    # passe les signalements sans anomalie ; un arrêt n'attend pas.
    with patch(f"{MODULE}._fichier", return_value="S10.G00.00.001,'Martine Paie'\n"), \
         patch(f"{MODULE}.upload_export_file", return_value="exports/c1/x.dsn"), \
         patch(f"{MODULE}.create_signed_url", return_value="https://lien"), \
         patch(f"{MODULE}.commands.record_export_history", return_value="x1") as historique:
        resultat = service.generer("c1", "u1", employee_id="e1", nature="04", debut="2026-10-05", essai=False)
    assert historique.call_args.args[0]["parameters"]["essai"] is False
    assert resultat["message"] == "Déposez-le sur net-entreprises.fr avant le 11/10/2026."


def test_verrou_ferme_le_fichier_reel_est_refuse(base):
    from app.modules.dsn_export.domain import etat_conformite

    with patch.object(etat_conformite, "SIGNALEMENTS_DEPOSABLES", False), pytest.raises(ValueError, match="essai"):
        service.generer("c1", "u1", employee_id="e1", nature="04", debut="2026-10-05", essai=False)


def test_un_signalement_qui_n_est_plus_a_faire_est_refuse(base):
    with pytest.raises(ValueError, match="plus à faire"):
        service.generer("c1", "u1", employee_id="e1", nature="04", debut="2026-10-04", essai=True)


def test_l_essai_se_range_dans_l_historique(base):
    with patch(f"{MODULE}._fichier", return_value="S10.G00.00.001,'Martine Paie'\n"), \
         patch(f"{MODULE}.upload_export_file", return_value="exports/c1/x.dsn"), \
         patch(f"{MODULE}.create_signed_url", return_value="https://lien"), \
         patch(f"{MODULE}.commands.record_export_history", return_value="x1") as historique:
        resultat = service.generer("c1", "u1", employee_id="e1", nature="04", debut="2026-10-05", essai=True)
    enregistre = historique.call_args.args[0]
    assert enregistre["export_type"] == "dsn_signalement_arret" and enregistre["period"] == "2026-10"
    assert enregistre["parameters"] == {"employee_id": "e1", "nature": "04", "motif": "01",
                                        "debut": "2026-10-05", "fin_prevue": "2026-10-09",
                                        "subrogation": False, "date_reprise": None, "essai": True}
    assert resultat["download_url"] == "https://lien" and "mode test" in resultat["message"]


def test_le_type_se_lit_dans_l_historique_et_ne_devient_pas_a_refaire():
    from typing import get_args

    from app.modules.exports.application.scheduled_exports import EXPORT_TYPE_LABELS
    from app.modules.exports.domain.a_refaire import EXPORTS_HORS_BULLETINS
    from app.modules.exports.schemas.requests import ExportType

    assert "dsn_signalement_arret" in get_args(ExportType)
    assert EXPORT_TYPE_LABELS["dsn_signalement_arret"] == "Signalement DSN d'arrêt"
    # Il lit les arrêts et la fiche, aucun bulletin : un recalcul ne le rend pas faux.
    assert "dsn_signalement_arret" in EXPORTS_HORS_BULLETINS


@pytest.fixture
def sortie():
    with patch(f"{MODULE}._arrets", return_value=[]), \
         patch(f"{MODULE}._envoyes", return_value=[]), \
         patch(f"{MODULE}._depuis", return_value=date(2026, 10, 1)), \
         patch(f"{MODULE}._effectif", return_value=20), \
         patch(f"{MODULE}._noms", return_value={"e2": "B. U."}), \
         patch(f"{MODULE}._sorties", return_value=[{"employee_id": "e2", "exit_type": "fin_cdd",
                                                     "last_working_day": "2026-11-06", "status": "validee"}]), \
         patch(f"{MODULE}._contrats", return_value=[]), \
         patch(f"{MODULE}._bulletins", return_value={("e2", 2026, 11)}):
        yield


def test_la_fin_de_contrat_se_liste_avec_sa_date_limite(sortie):
    (ligne,) = service.lister("c1", aujourd_hui=date(2026, 11, 9))["a_faire"]
    assert (ligne["nature"], ligne["debut"], ligne["a_deposer_avant"], ligne["a_verifier"]) == (
        "07", "2026-11-06", "2026-11-13", None)


def test_sans_bulletin_de_sortie_la_fin_de_contrat_attend(sortie):
    with patch(f"{MODULE}._bulletins", return_value=set()):
        (ligne,) = service.lister("c1", aujourd_hui=date(2026, 11, 9))["a_faire"]
        assert "Bulletin du mois de sortie" in ligne["a_verifier"]
        with pytest.raises(ValueError, match="Bulletin"):
            service.generer("c1", "u1", employee_id="e2", nature="07", debut="2026-11-06", essai=True,
                            aujourd_hui=date(2026, 11, 9))


def test_la_fin_de_contrat_se_genere_depuis_la_dsn_du_mois(sortie):
    mensuelle = "\r\n".join([
        "S20.G00.05.001,'01'", "S21.G00.30.001,'1900101234567'", "S21.G00.50.001,'30112026'",
        "S21.G00.62.001,'06112026'", "S21.G00.62.002,'031'", "S90.G00.90.001,'7'", "S90.G00.90.002,'1'",
    ]) + "\r\n"
    with patch(f"{MODULE}.generate_dsn_file", return_value=mensuelle.encode("iso-8859-15")) as mensuelle_du_mois, \
         patch(f"{MODULE}.upload_export_file", return_value="exports/c1/f.dsn") as rangement, \
         patch(f"{MODULE}.create_signed_url", return_value="https://lien"), \
         patch(f"{MODULE}.commands.record_export_history", return_value="x2") as historique:
        resultat = service.generer("c1", "u1", employee_id="e2", nature="07", debut="2026-11-06", essai=False,
                                   aujourd_hui=date(2026, 11, 9))
    assert mensuelle_du_mois.call_args.args[:4] == ("c1", "2026-11", "dsn_mensuelle_normale", ["e2"])
    contenu = rangement.call_args.args[2].decode("iso-8859-15")
    assert "S20.G00.05.001,'07'" in contenu and "S21.G00.63.001,'90'" in contenu
    assert historique.call_args.args[0]["parameters"]["nature"] == "07"
    assert resultat["message"] == "Déposez-le sur net-entreprises.fr avant le 13/11/2026."
