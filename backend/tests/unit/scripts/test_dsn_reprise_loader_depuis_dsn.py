"""La reprise se lit directement dans une DSN du cabinet (MAJI et Zone 404 n'ont pas de jeu)."""
from pathlib import Path

from scripts.dsn_reprise_loader import (
    SOCIETES,
    organismes_de_la_dsn,
    planifier,
    reprise_depuis_dsn,
)

NIR_A = "1800101000001"
NIR_B = "2800101000002"

DSN = f"""S21.G00.15.001,'CTR1'
S21.G00.15.002,'ORGA'
S21.G00.15.004,'01'
S21.G00.15.005,'1'
S21.G00.30.001,'{NIR_A}'
S21.G00.40.001,'01092026'
S21.G00.40.010,'30092026'
S21.G00.40.021,'01'
S21.G00.50.007,'01'
S21.G00.70.004,'A'
S21.G00.70.005,'B'
S21.G00.70.012,'1'
S21.G00.70.013,'1'
S21.G00.30.001,'{NIR_B}'
S21.G00.40.001,'01012026'
S21.G00.40.010,'31082026'
S21.G00.40.021,'02'
S21.G00.40.001,'01092026'
S21.G00.50.007,'13'
"""


def _dsn(tmp_path: Path) -> Path:
    chemin = tmp_path / "2026-09.dsn"
    chemin.write_text(DSN, encoding="latin-1")
    return chemin


def test_maji_et_zone_sont_connues_du_loader():
    assert "maji" in SOCIETES and "zone" in SOCIETES


def test_bloc_15_et_affiliations_viennent_de_la_meme_dsn(tmp_path):
    chemin = _dsn(tmp_path)

    assert organismes_de_la_dsn(chemin) == [
        {"reference": "CTR1", "organisme": "ORGA", "nature": "01", "ordre": "1"}
    ]
    reprises = dict(reprise_depuis_dsn(chemin))
    assert reprises[NIR_A]["affiliations_psc"] == [
        {"option": "A", "population": "B", "id_affiliation": "1", "id_contrat": "1"}
    ]
    assert reprises[NIR_A]["dsn_reprise"]["date_fin_contrat"] == "30092026"


def test_deux_contrats_le_meme_mois_ni_date_de_fin_ni_motif(tmp_path):
    reprises = dict(reprise_depuis_dsn(_dsn(tmp_path)))

    assert reprises[NIR_B]["dsn_reprise"] == {"pas_type": "13"}


def test_le_reste_de_la_fiche_est_conserve():
    plan = planifier(
        [{"id": "e1", "nir": NIR_A + "12", "specificites_paie": {"mutuelle": {"x": 1}}}],
        [(NIR_A, {"affiliations_psc": [{"id_affiliation": "1"}]})],
    )

    fiche, nouvelles, _ = plan["ecritures"][0]
    assert fiche["id"] == "e1"
    assert nouvelles == {"mutuelle": {"x": 1}, "affiliations_psc": [{"id_affiliation": "1"}]}


def test_nir_sur_deux_fiches_rien_n_est_ecrit():
    fiches = [{"id": i, "nir": NIR_A, "specificites_paie": {}} for i in ("e1", "e2")]

    plan = planifier(fiches, [(NIR_A, {"dsn_reprise": {"pas_type": "13"}})])

    assert plan["ecritures"] == [] and plan["ambigus"] == 1


def test_fiche_deja_a_jour_et_salarie_sans_fiche():
    charge = {"dsn_reprise": {"pas_type": "13"}}
    plan = planifier(
        [{"id": "e1", "nir": NIR_A, "specificites_paie": dict(charge)}],
        [(NIR_A, charge), (NIR_B, charge)],
    )

    assert plan["ecritures"] == [] and plan["a_jour"] == 1 and plan["absents"] == 1
