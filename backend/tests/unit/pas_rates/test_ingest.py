"""Dépôt d'un fichier : garde-fous du refus, puis écriture effective."""

import pytest

from app.modules.pas_rates.application import ingest
from app.modules.pas_rates.domain.model import Apercu, LigneApercu

ENTETE = (
    "S10.G00.00.006,'P26V01'\n"
    "S20.G00.05.005,'01052026'\n"
    "S21.G00.06.001,'991177304'\n"
    "S21.G00.11.001,'00029'\n"
)

INDIVIDU = (
    "S21.G00.30.001,'1660606088067'\n"
    "S21.G00.30.002,'NOBLE'\n"
    "S21.G00.30.004,'Eric'\n"
    "S21.G00.40.001,'01012024'\n"
    "S21.G00.50.001,'31052026'\n"
    "S21.G00.50.006,'26.80'\n"
    "S21.G00.50.007,'01'\n"
)

FICHIER = (ENTETE + INDIVIDU).encode("latin-1")


@pytest.fixture
def base(monkeypatch):
    """Une base en mémoire : un salarié, aucun historique."""
    etat = {
        "salaries": [
            {
                "id": "emp-1",
                "last_name": "NOBLE",
                "first_name": "Eric",
                "nir": "1660606088067",
                "employment_status": "actif",
                "company_id": "cid",
                "specificites_paie": {
                    "prelevement_a_la_source": {"taux": 3.5, "type_taux": "13"}
                },
            }
        ],
        "historique": [],
        "maj": [],
    }
    monkeypatch.setattr(ingest, "_siren_societe", lambda cid: "991177304")
    monkeypatch.setattr(
        ingest.repo, "lister_salaries", lambda cid, inclure_partis=False: etat["salaries"]
    )
    monkeypatch.setattr(
        ingest.repo,
        "enregistrer_taux",
        lambda entries: etat["historique"].extend(entries) or len(entries),
    )
    monkeypatch.setattr(
        ingest.repo,
        "maj_taux_courant",
        lambda *args: etat["maj"].append(args),
    )
    return etat


def test_apercu_ne_touche_pas_la_base(base):
    apercu = ingest.preparer_apercu("cid", FICHIER, "2026-05.dsn", "dsn")
    assert apercu.periode == "2026-05"
    assert apercu.compteurs()["modifie"] == 1
    assert base["historique"] == []
    assert base["maj"] == []


def test_application_ecrit_historique_et_taux_courant(base):
    apercu = ingest.preparer_apercu("cid", FICHIER, "2026-05.dsn", "dsn")
    resultat = ingest.appliquer("cid", apercu, "user-1")

    assert resultat == {"appliques": 1, "echecs": [], "historique": 1}
    entree = base["historique"][0]
    assert entree["employee_id"] == "emp-1"
    assert entree["periode"] == "2026-05"
    assert entree["taux"] == 26.8
    assert entree["type_taux"] == "01"
    assert entree["source"] == "dsn"
    assert entree["source_fichier"] == "2026-05.dsn"
    assert entree["applied_by"] == "user-1"
    assert base["maj"] == [("emp-1", 26.8, "01", None, "2026-05")]


def test_un_echec_n_annule_pas_les_autres(base, monkeypatch):
    apercu = Apercu(periode="2026-05", siren="991177304", fichier="f.dsn", source="dsn")
    apercu.lignes = [
        LigneApercu("emp-1", "A", "Un", None, 1.0, None, "01", nature="nouveau"),
        LigneApercu("emp-2", "B", "Deux", None, 2.0, None, "01", nature="nouveau"),
    ]

    def maj(employee_id, *args):
        if employee_id == "emp-1":
            raise RuntimeError("colonne verrouillée")
        base["maj"].append(employee_id)

    monkeypatch.setattr(ingest.repo, "maj_taux_courant", maj)
    resultat = ingest.appliquer("cid", apercu, None)

    assert resultat["appliques"] == 1
    assert len(resultat["echecs"]) == 1
    assert resultat["echecs"][0]["employee_id"] == "emp-1"
    assert base["maj"] == ["emp-2"]


def test_fichier_d_un_autre_siren_est_refuse(base, monkeypatch):
    monkeypatch.setattr(ingest, "_siren_societe", lambda cid: "751168337")
    with pytest.raises(ingest.FichierInvalide, match="991177304"):
        ingest.preparer_apercu("cid", FICHIER, "2026-05.dsn", "dsn")
    assert base["historique"] == []


def test_fichier_sans_taux_est_refuse(base):
    sans_pas = (
        ENTETE
        + "S21.G00.30.001,'1660606088067'\n"
        "S21.G00.30.002,'NOBLE'\n"
        "S21.G00.30.004,'Eric'\n"
        "S21.G00.40.001,'01012024'\n"
    ).encode("latin-1")
    with pytest.raises(ingest.FichierInvalide, match="Aucun taux"):
        ingest.preparer_apercu("cid", sans_pas, "2026-05.dsn", "dsn")


def test_fichier_non_datable_est_refuse(base):
    sans_periode = (
        "S10.G00.00.006,'P26V01'\n"
        "S21.G00.06.001,'991177304'\n"
        "S21.G00.11.001,'00029'\n"
        "S21.G00.30.001,'1660606088067'\n"
        "S21.G00.30.002,'NOBLE'\n"
        "S21.G00.30.004,'Eric'\n"
        "S21.G00.40.001,'01012024'\n"
        "S21.G00.50.006,'26.80'\n"
        "S21.G00.50.007,'01'\n"
    ).encode("latin-1")
    with pytest.raises(ingest.FichierInvalide, match="dater"):
        ingest.preparer_apercu("cid", sans_periode, "sans-date.dsn", "dsn")


def test_fichier_vide_est_refuse(base):
    with pytest.raises(ingest.FichierInvalide, match="vide"):
        ingest.preparer_apercu("cid", b"", "vide.dsn", "dsn")


def test_source_inconnue_est_refusee(base):
    with pytest.raises(ingest.FichierInvalide, match="Source inconnue"):
        ingest.preparer_apercu("cid", FICHIER, "2026-05.dsn", "bulletin")


def test_rejouer_le_meme_fichier_ne_change_plus_rien(base):
    apercu = ingest.preparer_apercu("cid", FICHIER, "2026-05.dsn", "dsn")
    ingest.appliquer("cid", apercu, "user-1")
    # Le taux courant est désormais celui du fichier.
    base["salaries"][0]["specificites_paie"]["prelevement_a_la_source"] = {
        "taux": 26.8,
        "type_taux": "01",
    }
    second = ingest.preparer_apercu("cid", FICHIER, "2026-05.dsn", "dsn")
    assert second.a_appliquer() == []
    assert ingest.appliquer("cid", second, "user-1")["appliques"] == 0
