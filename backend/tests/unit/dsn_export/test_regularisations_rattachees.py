"""Une régularisation saisie avec sa période se déclare rattachée à ses mois d'origine.

CT DSN 2026.1 (2025-12-24) : § 2.2.2.2 (période d'origine des cotisations
régularisées), § 2.2.2.5 (corrections valorisées mois civil par mois civil,
bloc 78 aux dates du mois corrigé), § 2.1.3.6.2 (rappel qualifié par sa
période de rattachement), S21.G00.51.001/002 (période à laquelle la
rémunération est rattachée).
"""

from __future__ import annotations

import pytest

from app.modules.dsn_export.domain.cotisation_mapping import build_bases_and_cotisations
from app.modules.dsn_export.domain.rattachement import mois_entre, repartir
from app.modules.dsn_export.domain.remuneration_map import (
    build_remunerations_from_payslip,
)
from app.modules.dsn_export.domain.writer import write_versement
from app.modules.dsn_import.domain.model import VersementBlock
from app.modules.payroll.engine.corrections_manuelles import (
    RegularisationCotisation,
    RegularisationHeures,
)

pytestmark = pytest.mark.unit

OCTOBRE = ("01102026", "31102026")


def _maladie(base=2000.0):
    return {
        "coti_id": "securite_sociale_maladie",
        "libelle": "Sécurité sociale - Maladie",
        "base": base,
        "taux_salarial": None,
        "taux_patronal": 0.07,
        "montant_salarial": 0.0,
        "montant_patronal": round(base * 0.07, 2),
    }


def _regul_maladie(base=100.0, **periode):
    return RegularisationCotisation(
        coti_id="securite_sociale_maladie",
        libelle="Sécurité sociale - Maladie",
        motif="Base oubliée",
        base=base,
        taux_patronal=0.07,
        **periode,
    ).ligne_de_cotisation()


def _dsn(lignes, periode="2026-10"):
    return build_bases_and_cotisations(
        lignes, brut=2000.0, period_start=OCTOBRE[0], period_end=OCTOBRE[1], periode=periode
    )


def _blocs_sous(bases, cotisations, debut):
    base_codes = {b.code for b in bases if b.date_debut == debut}
    return [c for c in cotisations if c.rubriques.get("_base") in base_codes]


def test_repartir_garde_le_total_au_centime():
    assert repartir(100.0, 3) == [33.33, 33.33, 33.34]
    assert repartir(-100.0, 3) == [-33.33, -33.33, -33.34]
    assert sum(repartir(7.0, 3)) == pytest.approx(7.0)
    assert mois_entre("2026-11", "2027-01") == ["2026-11", "2026-12", "2027-01"]


def test_sans_periode_rien_ne_change():
    sans = _dsn([_maladie(), _regul_maladie()])
    avant = build_bases_and_cotisations(
        [_maladie(), _regul_maladie()], brut=2000.0, period_start=OCTOBRE[0], period_end=OCTOBRE[1]
    )
    assert sans == avant


def test_une_regularisation_de_septembre_se_declare_aux_dates_de_septembre():
    bases, cotisations, _ = _dsn([_maladie(), _regul_maladie(mois_debut="2026-09")])

    septembre = [b for b in bases if b.date_debut == "01092026"]
    assert len(septembre) == 1
    base = septembre[0]
    assert base.rubriques["S21.G00.78.001"] == "03"
    assert base.rubriques["S21.G00.78.002"] == "01092026"
    assert base.rubriques["S21.G00.78.003"] == "30092026"
    assert base.rubriques["S21.G00.78.004"] == "100.00"
    assert "_composants_79" not in base.rubriques

    (bloc,) = _blocs_sous(bases, cotisations, "01092026")
    assert bloc.rubriques["S21.G00.81.001"] == "075"
    assert bloc.rubriques["S21.G00.81.003"] == "100.00"
    assert bloc.rubriques["S21.G00.81.004"] == "7.00"
    assert bloc.rubriques["S21.G00.81.007"] == "7.000"

    # Le mois courant ne porte plus la régularisation.
    (courante,) = [c for c in _blocs_sous(bases, cotisations, OCTOBRE[0]) if c.code == "075"]
    assert courante.rubriques["S21.G00.81.004"] == "140.00"
    assert courante.rubriques["S21.G00.81.003"] == "2000.00"


def test_une_regularisation_sur_trois_mois_se_declare_mois_par_mois():
    bases, cotisations, _ = _dsn(
        [_maladie(), _regul_maladie(base=300.0, mois_debut="2026-07", mois_fin="2026-09")]
    )
    debuts = sorted(b.date_debut for b in bases if b.date_debut != OCTOBRE[0])
    assert debuts == ["01072026", "01082026", "01092026"]
    montants = [
        float(c.rubriques["S21.G00.81.004"])
        for d in ("01072026", "01082026", "01092026")
        for c in _blocs_sous(bases, cotisations, d)
    ]
    assert montants == [7.0, 7.0, 7.0]
    assert sum(montants) == pytest.approx(21.0)


def test_une_regularisation_negative_garde_son_signe():
    bases, cotisations, _ = _dsn([_maladie(), _regul_maladie(base=-100.0, mois_debut="2026-09")])
    (base,) = [b for b in bases if b.date_debut == "01092026"]
    assert base.rubriques["S21.G00.78.004"] == "-100.00"
    (bloc,) = _blocs_sous(bases, cotisations, "01092026")
    assert bloc.rubriques["S21.G00.81.004"] == "-7.00"
    assert bloc.rubriques["S21.G00.81.007"] == "7.000"


def test_le_mois_du_bulletin_reste_dans_sa_periode():
    avec_octobre = _dsn([_maladie(), _regul_maladie(mois_debut="2026-10")])
    sans_periode = _dsn([_maladie(), _regul_maladie()])
    assert [b.date_debut for b in avec_octobre[0]] == [b.date_debut for b in sans_periode[0]]
    montant = lambda r: [c.rubriques["S21.G00.81.004"] for c in r[1] if c.code == "075"]
    assert montant(avec_octobre) == montant(sans_periode) == ["147.00"]


def test_la_csg_regularisee_se_rattache_sur_la_base_04():
    regul = RegularisationCotisation(
        coti_id="csg_non_deductible",
        libelle="CSG/CRDS non déductible",
        motif="Assiette oubliée",
        base=1000.0,
        taux_salarial=0.029,
        mois_debut="2026-09",
    ).ligne_de_cotisation()
    bases, cotisations, _ = _dsn([_maladie(), regul])
    (base,) = [b for b in bases if b.date_debut == "01092026"]
    assert base.rubriques["S21.G00.78.001"] == "04"
    blocs = {c.code: c.rubriques for c in _blocs_sous(bases, cotisations, "01092026")}
    assert blocs["072"]["S21.G00.81.004"] == "24.00"
    assert blocs["079"]["S21.G00.81.004"] == "5.00"


def test_la_reduction_generale_regularisee_reste_dans_le_mois_courant():
    """CCH-17 de S21.G00.81 : 018/106 exigent le SMIC retenu (79 type 01) sous la
    même base 03, que Martine ne connaît pas pour un mois passé."""
    regul = RegularisationCotisation(
        coti_id="reduction_generale",
        libelle="Réduction générale",
        motif="Erreur",
        montant_patronal=-10.0,
        mois_debut="2026-09",
    ).ligne_de_cotisation()
    bases, _, _ = _dsn([_maladie(), regul])
    assert all(b.date_debut == OCTOBRE[0] for b in bases)


def test_la_prevoyance_regularisee_reste_dans_le_mois_courant():
    regul = RegularisationCotisation(
        coti_id="prevoyance_non_cadre",
        libelle="Prévoyance non cadre",
        motif="Erreur",
        base=100.0,
        taux_patronal=0.01,
        mois_debut="2026-09",
    ).ligne_de_cotisation()
    bases, _, _ = _dsn([_maladie(), regul])
    assert all(b.date_debut == OCTOBRE[0] for b in bases)


def test_le_bloc_rattache_s_ecrit_sous_sa_base():
    bases, cotisations, _ = _dsn([_maladie(), _regul_maladie(mois_debut="2026-09")])
    versement = VersementBlock(bases_assujetties=bases, cotisations_individuelles=cotisations)
    lignes: list[str] = []
    write_versement(versement, lignes)
    texte = "\n".join(lignes)
    attendu = (
        "S21.G00.78.001,'03'\nS21.G00.78.002,'01092026'\nS21.G00.78.003,'30092026'\n"
        "S21.G00.78.004,'100.00'\nS21.G00.81.001,'075'"
    )
    assert attendu in texte


# --- Rémunérations : les heures régularisées -----------------------------------


def _bulletin_avec_heures(regul: RegularisationHeures, gain: float, quantite: float):
    return {
        "calcul_du_brut": [
            {"libelle": "Salaire de base", "quantite": 151.67, "taux": 13.1874, "gain": 2000.0},
            {
                "libelle": regul.libelle(0.25),
                "quantite": quantite,
                "taux": 16.4843,
                "gain": gain,
                "regularisation_heures": {**regul.charge_utile(), "saisie_id": "s1"},
            },
        ]
    }


def _remunerations(bulletin, brut):
    return build_remunerations_from_payslip(
        bulletin, brut=brut, period_start=OCTOBRE[0], period_end=OCTOBRE[1], period="2026-10"
    ).remunerations


def _par_type_et_debut(remus):
    return {(r.rubriques["S21.G00.51.011"], r.rubriques["S21.G00.51.001"]): r.rubriques for r in remus}


def test_des_heures_sup_de_septembre_se_declarent_aux_dates_de_septembre():
    regul = RegularisationHeures(nature="hs1", mois_origine="2026-09", quantite=4.0, motif="Oubli")
    remus = _par_type_et_debut(_remunerations(_bulletin_avec_heures(regul, 65.94, 4.0), 2065.94))

    assert remus[("001", "01092026")]["S21.G00.51.002"] == "30092026"
    assert remus[("001", "01092026")]["S21.G00.51.013"] == "65.94"
    assert remus[("002", "01092026")]["S21.G00.51.013"] == "65.94"
    assert remus[("017", "01092026")]["S21.G00.51.013"] == "65.94"
    assert remus[("017", "01092026")]["S21.G00.51.012"] == "4.00"
    # Le mois courant ne porte que ses propres éléments.
    assert remus[("001", OCTOBRE[0])]["S21.G00.51.013"] == "2000.00"
    assert ("017", OCTOBRE[0]) not in remus


def test_des_heures_normales_de_septembre_n_ont_pas_de_type_017():
    regul = RegularisationHeures(nature="normales", mois_origine="2026-09", quantite=3.0, motif="Oubli")
    remus = _par_type_et_debut(_remunerations(_bulletin_avec_heures(regul, 39.56, 3.0), 2039.56))
    assert remus[("001", "01092026")]["S21.G00.51.013"] == "39.56"
    assert ("017", "01092026") not in remus


def test_des_heures_sur_deux_mois_se_repartissent():
    regul = RegularisationHeures(
        nature="hs1", mois_origine="2026-08", mois_fin="2026-09", quantite=5.0, motif="Oubli"
    )
    remus = _par_type_et_debut(_remunerations(_bulletin_avec_heures(regul, 82.43, 5.0), 2082.43))
    assert remus[("017", "01082026")]["S21.G00.51.013"] == "41.21"
    assert remus[("017", "01092026")]["S21.G00.51.013"] == "41.22"
    assert remus[("017", "01082026")]["S21.G00.51.012"] == "2.50"


def test_des_heures_du_mois_courant_restent_dans_le_mois():
    regul = RegularisationHeures(nature="hs1", mois_origine="2026-10", quantite=4.0, motif="Oubli")
    remus = _par_type_et_debut(_remunerations(_bulletin_avec_heures(regul, 65.94, 4.0), 2065.94))
    assert {debut for _, debut in remus} == {OCTOBRE[0]}
    assert remus[("017", OCTOBRE[0])]["S21.G00.51.013"] == "65.94"


# --- Ce que l'aperçu de la DSN dit ----------------------------------------------


def _bulletin_cotisations(*lignes):
    return {"cotisations_officielles": [{"lignes": list(lignes)}], "calcul_du_brut": []}


def test_l_avis_ne_vise_plus_une_regularisation_rattachee():
    from app.modules.dsn_export.domain.rectification import avis_des_regularisations

    rattachee = RegularisationCotisation(
        coti_id="securite_sociale_maladie",
        libelle="Sécurité sociale - Maladie",
        motif="Base oubliée",
        base=100.0,
        taux_patronal=0.07,
        mois_debut="2026-09",
        saisie_id="a",
    ).ligne_de_cotisation()
    sans_periode = RegularisationCotisation(
        coti_id="assurance_chomage",
        libelle="Assurance chômage",
        motif="Erreur",
        base=100.0,
        taux_patronal=0.04,
        saisie_id="b",
    ).ligne_de_cotisation()
    avis = avis_des_regularisations("A. B.", _bulletin_cotisations(rattachee, sans_periode), "2026-10")
    assert len(avis) == 1
    assert "Assurance chômage" in avis[0]
    assert "mois d'origine" in avis[0]


def test_l_avis_dit_la_repartition_sur_plusieurs_mois():
    from app.modules.dsn_export.domain.rectification import avis_des_regularisations

    ligne = RegularisationCotisation(
        coti_id="securite_sociale_maladie",
        libelle="Sécurité sociale - Maladie",
        motif="Base oubliée",
        base=300.0,
        taux_patronal=0.07,
        mois_debut="2026-07",
        mois_fin="2026-09",
        saisie_id="a",
    ).ligne_de_cotisation()
    (avis,) = avis_des_regularisations("A. B.", _bulletin_cotisations(ligne), "2026-10")
    assert "3 mois" in avis and "parts égales" in avis


def test_l_avis_garde_la_reduction_generale_d_un_mois_passe():
    from app.modules.dsn_export.domain.rectification import avis_des_regularisations

    ligne = RegularisationCotisation(
        coti_id="reduction_generale",
        libelle="Réduction générale",
        motif="Erreur",
        montant_patronal=-10.0,
        mois_debut="2026-09",
        saisie_id="a",
    ).ligne_de_cotisation()
    (avis,) = avis_des_regularisations("A. B.", _bulletin_cotisations(ligne), "2026-10")
    assert "Réduction générale" in avis


def test_des_heures_regularisees_ne_sont_plus_un_rappel_sans_mois():
    from app.modules.dsn_export.domain.rectification import avis_des_regularisations

    regul = RegularisationHeures(nature="hs1", mois_origine="2026-09", quantite=4.0, motif="Oubli")
    bulletin = _bulletin_avec_heures(regul, 65.94, 4.0)
    assert avis_des_regularisations("A. B.", bulletin, "2026-10") == []


# --- Le fichier DSN entier ------------------------------------------------------


def test_le_fichier_porte_la_regularisation_aux_dates_de_septembre():
    from app.modules.dsn_export.application.builder import build_parsed_dsn_from_payroll
    from app.modules.dsn_export.domain.writer import encode_dsn_bytes

    from .test_builder_from_payslip import _sample_company, _sample_employee_row

    ligne = _sample_employee_row()
    regul = RegularisationCotisation(
        coti_id="assurance_chomage",
        libelle="Assurance chômage",
        motif="Taux erroné en septembre",
        base=2500.0,
        taux_patronal=0.001,
        mois_debut="2026-09",
        saisie_id="r1",
    ).ligne_de_cotisation()
    ligne["payslip_data"]["structure_cotisations"]["bloc_principales"].append(regul)
    dsn_file, _ = build_parsed_dsn_from_payroll(_sample_company(), [ligne], "2026-10")
    texte = encode_dsn_bytes(dsn_file).decode("latin-1")

    assert "S21.G00.78.002,'01092026'" in texte
    assert "S21.G00.78.003,'30092026'" in texte
    ver = dsn_file.etablissement.individus[0].contrats[0].versements[0]
    septembre = [b for b in ver.bases_assujetties if b.date_debut == "01092026"]
    assert len(septembre) == 1
    assert "_composants_79" not in septembre[0].rubriques
    sous_septembre = [c for c in ver.cotisations_individuelles if c.rubriques["_base"] == septembre[0].code]
    assert [c.rubriques["S21.G00.81.004"] for c in sous_septembre] == ["2.50"]
