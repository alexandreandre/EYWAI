"""Le constructeur déclare les deux bulletins d'un mois à deux contrats (D3.2).

Le CDD (numéro 00000) finit le 10/11 ; le CDI (numéro 00001, posé par
« Nouveau contrat ») commence le 17/11. La ligne du salarié porte le bulletin du
contrat de la fiche, et `contrat_precedent` celui du contrat rangé, sur sa fiche
rangée.
"""

from __future__ import annotations

from app.modules.dsn_export.application.builder import build_parsed_dsn_from_payroll
from app.modules.dsn_export.domain.writer import encode_dsn_bytes
from app.modules.dsn_import.application.cumuls import extract_monthly_totals
from app.modules.dsn_import.domain.parser import parse_dsn_content

SOCIETE = {
    "siret": "12345678900015",
    "name": "ACME INDUSTRIE",
    "code_naf": "2562B",
    "address": {"rue": "1 RUE DE LA PAIX", "code_postal": "75001", "ville": "PARIS"},
}


def _fiche(**contrat) -> dict:
    return {
        "id": "emp-1",
        "first_name": "Jean",
        "last_name": "Dupont",
        "nir": "1850175123456",
        "sexe": "M",
        "date_naissance": "1985-01-15",
        "lieu_naissance": "PARIS",
        "statut": "Non-Cadre",
        "adresse": {"rue": "10 AVENUE TEST", "code_postal": "75010", "ville": "PARIS"},
        "idcc": "1486",
        "pcs": "389a",
        "job_title": "Peintre",
        **contrat,
    }


def _bulletin(brut: float, pas: float) -> dict:
    return {
        "salaire_brut": brut,
        "synthese_net": {
            "net_imposable": round(brut * 0.8, 2),
            "net_a_payer": round(brut * 0.78, 2),
            "impot_prelevement_a_la_source": {"montant": pas, "taux": 2.0, "base": round(brut * 0.8, 2)},
        },
        "structure_cotisations": {
            "bloc_principales": [
                {
                    "coti_id": "securite_sociale_maladie",
                    "libelle": "Sécurité sociale - Maladie",
                    "base": brut,
                    "taux_patronal": 7.0,
                    "montant_patronal": round(brut * 0.07, 2),
                    "montant_salarial": 0,
                },
            ],
        },
    }


ANCIEN = _fiche(
    contract_type="CDD",
    hire_date="2026-07-01",
    contract_end_date="2026-11-10",
    classification_conventionnelle={"numero_contrat_dsn": "00000", "motif_recours": "03"},
)
NOUVEAU = _fiche(
    contract_type="CDI",
    hire_date="2026-11-17",
    classification_conventionnelle={"numero_contrat_dsn": "00001"},
)


def _ligne() -> dict:
    return {
        "employee": dict(NOUVEAU),
        "payslip_data": _bulletin(900.0, 14.4),
        "contrat_precedent": {"employee": dict(ANCIEN), "payslip_data": _bulletin(700.0, 11.2)},
    }


def _individu():
    fichier, avertissements = build_parsed_dsn_from_payroll(SOCIETE, [_ligne()], "2026-11")
    assert len(fichier.etablissement.individus) == 1, avertissements
    return fichier, fichier.etablissement.individus[0]


def test_un_individu_deux_contrats_dans_l_ordre():
    _, individu = _individu()
    assert [(c.rubriques["S21.G00.40.001"], c.rubriques["S21.G00.40.009"]) for c in individu.contrats] == [
        ("01072026", "00000"),
        ("17112026", "00001"),
    ]


def test_chaque_contrat_a_ses_dates_de_remuneration():
    _, individu = _individu()
    ancien, nouveau = individu.contrats
    remuneration_ancien = ancien.versements[0].remunerations[0].rubriques
    remuneration_nouveau = nouveau.versements[0].remunerations[0].rubriques
    assert (remuneration_ancien["S21.G00.51.001"], remuneration_ancien["S21.G00.51.002"]) == ("01112026", "10112026")
    assert remuneration_ancien["S21.G00.51.010"] == "00000"
    assert remuneration_nouveau["S21.G00.51.001"] == "17112026"
    assert remuneration_nouveau["S21.G00.51.010"] == "00001"


def test_la_fin_de_contrat_est_sous_l_ancien_contrat_seul():
    _, individu = _individu()
    ancien, nouveau = individu.contrats
    assert ancien.fin_contrat is not None
    assert ancien.fin_contrat.rubriques["S21.G00.62.001"] == "10112026"
    assert nouveau.fin_contrat is None


def test_le_motif_de_recours_est_celui_de_chaque_contrat():
    _, individu = _individu()
    ancien, nouveau = individu.contrats
    assert ancien.rubriques["S21.G00.40.021"] == "03"
    assert "S21.G00.40.021" not in nouveau.rubriques


def test_les_deux_bulletins_sont_declares_et_se_relisent():
    fichier, individu = _individu()
    totaux = extract_monthly_totals(individu)
    assert abs(totaux["brut"] - 1600.0) < 0.01
    assert abs(totaux["pas"] - 25.6) < 0.01
    relu = parse_dsn_content(encode_dsn_bytes(fichier), file_name="deux_contrats.dsn")
    individu_relu = relu.etablissement.individus[0]
    assert [c.numero_contrat for c in individu_relu.contrats] == ["00000", "00001"]
    assert abs(extract_monthly_totals(individu_relu)["brut"] - 1600.0) < 0.01


def test_une_fin_reprise_avant_le_debut_du_contrat_n_est_pas_declaree():
    """CT 40.010 CCH-11 : la fin prévisionnelle ne précède pas le début. Une
    reprise DSN restée sur la fiche décrit le contrat rangé, pas celui-ci."""
    fiche = _fiche(
        contract_type="CDI",
        hire_date="2026-11-17",
        specificites_paie={"dsn_reprise": {"date_fin_contrat": "10112026"}},
    )
    fichier, _ = build_parsed_dsn_from_payroll(
        SOCIETE, [{"employee": fiche, "payslip_data": _bulletin(900.0, 14.4)}], "2026-11"
    )
    assert "S21.G00.40.010" not in fichier.etablissement.individus[0].contrats[0].rubriques
