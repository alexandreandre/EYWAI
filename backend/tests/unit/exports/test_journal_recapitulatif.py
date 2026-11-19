"""Journal de paie au format de Quadra : le mois cumulé par rubrique (Elsa, 17/11)."""

import pytest

from app.modules.exports.infrastructure.journal_recapitulatif import journal_recapitulatif

pytestmark = pytest.mark.unit


def _bulletin(base: float, absence: float, retraite: float, pas: float):
    return {
        "salaire_brut": base - absence,
        "net_a_payer": round(base - absence - retraite - 10 - pas - 50, 2),
        "calcul_du_brut": [{"libelle": "Salaire de base", "gain": base}],
        "details_absences": [{"libelle": "Absence maladie du 12/10/26", "perte": absence, "quantite": 1}] if absence else [],
        "cotisations_officielles": [
            {
                "code": "retraite",
                "lignes": [
                    {"coti_id": "rc_t1", "libelle": "Retraite T1", "base": base - absence, "montant_salarial": retraite, "montant_patronal": retraite * 1.5},
                    {"coti_id": "ags", "libelle": "AGS", "base": base - absence, "montant_salarial": 0.0, "montant_patronal": 5.0},
                ],
            },
            {
                "code": "csg_non_deductible",
                "lignes": [{"libelle": "CSG/CRDS non déductible", "base": base * 0.9825, "montant_salarial": 10.0}],
            },
        ],
        "synthese_net": {"net_imposable": base - absence - retraite, "impot_prelevement_a_la_source": {"base": 1000, "montant": pas}},
        "retenues_saisies": {"total_preleve": 50.0, "saisies": [{"type": "atd", "creditor_name": "SIP AMIENS", "montant": 50.0}]},
    }


def test_le_mois_cumule_par_rubrique_dans_l_ordre_de_quadra():
    lignes = journal_recapitulatif([_bulletin(3000, 100, 90, 120), _bulletin(2000, 0, 60, 40)], 2)
    par_libelle = {l["Libellé"]: l for l in lignes}
    libelles = [l["Libellé"] for l in lignes]

    assert par_libelle["Salaire de base"]["Montant salarial"] == 5000
    # Les dates sortent du libellé : une rubrique, tous salariés confondus.
    assert par_libelle["Absence maladie"]["Montant salarial"] == -100
    assert par_libelle["SALAIRE BRUT"]["Montant salarial"] == 4900
    assert par_libelle["Retraite T1"] == {
        "Libellé": "Retraite T1", "Montant salarial": 150.0, "Base": 4900.0, "Charges patronales": 225.0,
    }
    assert par_libelle["AGS"]["Charges patronales"] == 10
    assert par_libelle["TOTAL DES RETENUES"]["Montant salarial"] == 150
    assert par_libelle["TOTAL DES RETENUES"]["Charges patronales"] == 235
    assert par_libelle["NET IMPOSABLE"]["Montant salarial"] == 4750
    # Après le net imposable, ce qui se retire est négatif, comme chez Quadra.
    assert par_libelle["CSG/CRDS non déductible"]["Montant salarial"] == -20
    assert par_libelle["Prélèvement à la source"]["Montant salarial"] == -160
    assert par_libelle["ATD SIP AMIENS"]["Montant salarial"] == -100
    assert par_libelle["NET A PAYER"]["Montant salarial"] == 4470
    assert libelles.index("SALAIRE BRUT") < libelles.index("Retraite T1") < libelles.index("TOTAL DES RETENUES")
    assert libelles.index("NET IMPOSABLE") < libelles.index("CSG/CRDS non déductible") < libelles.index("NET A PAYER")
    assert libelles[-1] == "Salariés payés sur la période : 2"


def test_le_net_se_retrouve_a_partir_des_lignes():
    lignes = journal_recapitulatif([_bulletin(3000, 100, 90, 120), _bulletin(2000, 0, 60, 40)], 2)
    par_libelle = {l["Libellé"]: l for l in lignes}
    i = [l["Libellé"] for l in lignes].index("NET IMPOSABLE")
    apres = sum(l["Montant salarial"] or 0 for l in lignes[i + 1 : -2])
    brut = par_libelle["SALAIRE BRUT"]["Montant salarial"]
    retenues = par_libelle["TOTAL DES RETENUES"]["Montant salarial"]
    assert round(brut - retenues + apres, 2) == par_libelle["NET A PAYER"]["Montant salarial"]
