"""Régularisation d'heures d'un autre mois (retour d'Elsa, Lyon, 10/11/2026).

Les heures s'ajoutent au planning, sur une ligne à elles qui dit le mois
d'origine. Les heures sup et complémentaires gardent leur réduction salariale et
leur exonération d'impôt (CSS L241-17 ; CGI 81 quater) ; toutes comptent dans le
SMIC de référence de la réduction générale. Sans régularisation, rien ne bouge.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut, taux_majore
from app.modules.payroll.engine.codes_des_lignes import (
    BLOC_BRUT,
    code_de_ligne,
    mode_de_correction,
)
from app.modules.payroll.engine.corrections_manuelles import (
    CLE_REGULARISATIONS_COTISATION,
    CLE_REGULARISATIONS_HEURES,
    RegularisationHeures,
    RegularisationInvalide,
    ranger_correction_manuelle,
    regularisations_heures_du_bulletin,
)

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

JANVIER = (date(2026, 1, 1), date(2026, 1, 31))


def _calendrier(hs=None):
    cal = []
    jour = date(2026, 1, 1)
    while jour.month == 1:
        if jour.weekday() < 5:
            cal.append(
                {
                    "date_complete": jour.isoformat(),
                    "type": "travail_base",
                    "heures": 7.0,
                }
            )
        jour = date.fromordinal(jour.toordinal() + 1)
    for iso, (type_ev, heures) in (hs or {}).items():
        cal.append({"date_complete": iso, "type": type_ev, "heures": heures})
    return cal


def _regul(
    nature="hs1", quantite=4.0, mois="2025-12", taux_horaire=None, saisie_id="s1"
):
    return {
        **RegularisationHeures(
            nature=nature,
            mois_origine=mois,
            quantite=quantite,
            motif="Oubli du planning",
            taux_horaire=taux_horaire,
        ).charge_utile(),
        "saisie_id": saisie_id,
    }


def _calcul(*reguls, cal=None, **options):
    contexte = build_test_contexte(**options)
    contexte.year = 2026
    if reguls:
        contexte.contrat.setdefault("saisie_du_mois", {})[
            CLE_REGULARISATIONS_HEURES
        ] = list(reguls)
    return calculer_salaire_brut(contexte, cal or _calendrier(), *JANVIER, [])


def _lignes_regul(resultat):
    return [
        l for l in resultat["lignes_composants_brut"] if l.get("regularisation_heures")
    ]


def test_sans_regularisation_le_brut_est_identique():
    reference = _calcul(cal=_calendrier(hs={"2026-01-15": ("travail_hs25", 4.0)}))
    assert not _lignes_regul(reference)
    assert reference["heures_normales_regularisees"] == 0.0


def test_des_heures_sup_d_un_autre_mois_s_ajoutent_au_planning_et_gardent_l_exoneration():
    cal = _calendrier(hs={"2026-01-15": ("travail_hs25", 4.0)})
    reference = _calcul(cal=cal)
    resultat = _calcul(_regul("hs1", 3.5), cal=cal)
    (ligne,) = _lignes_regul(resultat)
    hs_planning = next(
        l
        for l in resultat["lignes_composants_brut"]
        if l["libelle"].startswith("Heures suppl.")
    )
    assert hs_planning["quantite"] == 4.0  # le planning n'est pas remplacé
    assert ligne["libelle"] == "Régularisation heures sup 25 % – 12/2025"
    assert ligne["taux"] == hs_planning["taux"]
    assert ligne["gain"] == round(3.5 * hs_planning["taux"], 2)
    assert resultat["salaire_brut_total"] == pytest.approx(
        reference["salaire_brut_total"] + ligne["gain"], abs=0.005
    )
    assert resultat["total_heures_supp"] == pytest.approx(
        reference["total_heures_supp"] + 3.5
    )
    assert resultat["remuneration_brute_heures_supp"] == pytest.approx(
        reference["remuneration_brute_heures_supp"] + ligne["gain"], abs=0.005
    )
    assert resultat["heures_sup_conjoncturelles"] == pytest.approx(
        reference["heures_sup_conjoncturelles"] + 3.5
    )


def test_le_second_palier_prend_la_majoration_de_la_societe():
    resultat = _calcul(_regul("hs2", 2.0))
    (ligne,) = _lignes_regul(resultat)
    assert ligne["libelle"].startswith("Régularisation heures sup 50 %")
    assert ligne["taux"] > 0


def test_des_heures_normales_comptent_au_smic_de_reference_pas_dans_les_heures_sup():
    reference = _calcul()
    resultat = _calcul(_regul("normales", 6.0, mois="2025-11"))
    (ligne,) = _lignes_regul(resultat)
    assert ligne["libelle"] == "Régularisation heures normales – 11/2025"
    assert resultat["heures_normales_regularisees"] == 6.0
    assert resultat["total_heures_supp"] == reference["total_heures_supp"]
    assert (
        resultat["remuneration_brute_heures_supp"]
        == reference["remuneration_brute_heures_supp"]
    )
    assert resultat["salaire_brut_total"] == pytest.approx(
        reference["salaire_brut_total"] + ligne["gain"], abs=0.005
    )


def test_des_heures_complementaires_vont_dans_leur_regime():
    reference = _calcul()
    resultat = _calcul(_regul("hc1", 2.0))
    (ligne,) = _lignes_regul(resultat)
    assert ligne["libelle"].startswith("Régularisation heures complémentaires 10 %")
    assert resultat["heures_complementaires"] == pytest.approx(
        reference["heures_complementaires"] + 2.0
    )
    assert resultat["remuneration_brute_heures_supp"] == pytest.approx(
        reference["remuneration_brute_heures_supp"] + ligne["gain"], abs=0.005
    )
    # La déduction forfaitaire patronale reste réservée aux heures sup.
    assert resultat["total_heures_supp"] == reference["total_heures_supp"]


def test_des_heures_payees_en_trop_se_reprennent():
    reference = _calcul(cal=_calendrier(hs={"2026-01-15": ("travail_hs25", 4.0)}))
    resultat = _calcul(
        _regul("hs1", -1.5), cal=_calendrier(hs={"2026-01-15": ("travail_hs25", 4.0)})
    )
    (ligne,) = _lignes_regul(resultat)
    assert ligne["gain"] < 0
    assert resultat["total_heures_supp"] == pytest.approx(
        reference["total_heures_supp"] - 1.5
    )


def test_le_taux_horaire_du_mois_d_origine_peut_etre_donne():
    (ligne,) = _lignes_regul(_calcul(_regul("hs1", 2.0, taux_horaire=12.0)))
    assert ligne["taux"] == taux_majore(12.0, 0.25)
    assert ligne["gain"] == round(2.0 * taux_majore(12.0, 0.25), 2)


def test_la_ligne_ne_se_corrige_que_dans_sa_carte_et_se_relit_sur_le_bulletin():
    (ligne,) = _lignes_regul(_calcul(_regul("hs1", 2.0, saisie_id="abc")))
    code = code_de_ligne(BLOC_BRUT, ligne)
    assert code == "brut:regularisation_heures:abc"
    mode, raison = mode_de_correction(BLOC_BRUT, ligne, code)
    assert mode is None and "Régularisations d'heures" in raison
    relues = regularisations_heures_du_bulletin({"calcul_du_brut": [ligne]})
    assert list(relues) == ["abc"] and relues["abc"].quantite == 2.0


def test_la_saisie_est_rangee_a_part_des_primes():
    saisies: dict = {}
    regul = RegularisationHeures(
        nature="hs1", mois_origine="2025-12", quantite=4.0, motif="Oubli"
    )
    assert ranger_correction_manuelle({"id": "s9", **regul.saisie_du_mois({})}, saisies)
    assert saisies[CLE_REGULARISATIONS_HEURES][0]["saisie_id"] == "s9"
    assert CLE_REGULARISATIONS_COTISATION not in saisies


@pytest.mark.parametrize(
    "champs",
    [
        {"nature": "hs3"},
        {"mois_origine": "2025-13"},
        {"quantite": 0.0},
        {"quantite": 301.0},
        {"motif": "a"},
        {"taux_horaire": 0.0},
    ],
)
def test_une_regularisation_incoherente_est_refusee(champs):
    base = {
        "nature": "hs1",
        "mois_origine": "2025-12",
        "quantite": 4.0,
        "motif": "Oubli",
    }
    with pytest.raises(RegularisationInvalide):
        RegularisationHeures(**{**base, **champs})


# --- Le serveur : refus, restauration, requête ---------------------------------


def _bulletin_avec(*reguls):
    from app.modules.payroll.engine.calcul_brut import taux_majore as majorer

    lignes = [
        RegularisationHeures.depuis(r).ligne_de_gain(15.0, {"hs1": 0.25}, majorer)
        for r in reguls
    ]
    return {"calcul_du_brut": lignes}


def test_le_refus_au_forfait_jours_et_pour_un_mois_posterieur():
    from app.modules.payslips.domain.corrections import (
        MESSAGE_HEURES_AU_FORFAIT,
        CorrectionsBulletin,
        refus_des_regularisations_heures,
    )

    ok = RegularisationHeures(
        nature="hs1", mois_origine="2026-09", quantite=2.0, motif="Oubli"
    )
    futur = RegularisationHeures(
        nature="hs1", mois_origine="2026-11", quantite=2.0, motif="Oubli"
    )
    meme_mois = RegularisationHeures(
        nature="hs1", mois_origine="2026-10", quantite=2.0, motif="Oubli"
    )
    c = CorrectionsBulletin(regularisations_heures_ajoutees=(ok,))
    assert refus_des_regularisations_heures(c, 2026, 10, forfait_jours=False) is None
    assert (
        refus_des_regularisations_heures(c, 2026, 10, forfait_jours=True)
        == MESSAGE_HEURES_AU_FORFAIT
    )
    assert "postérieures" in refus_des_regularisations_heures(
        CorrectionsBulletin(regularisations_heures_ajoutees=(futur,)),
        2026,
        10,
        forfait_jours=False,
    )
    assert (
        refus_des_regularisations_heures(
            CorrectionsBulletin(regularisations_heures_ajoutees=(meme_mois,)),
            2026,
            10,
            forfait_jours=False,
        )
        is None
    )
    assert c.change_des_variables


def test_restaurer_une_version_rend_et_retire_les_heures_regularisees():
    from app.modules.payslips.domain.corrections import (
        apercu_de_restauration,
        contenu_de_version,
        corrections_pour_revenir,
    )

    avec = _bulletin_avec(_regul("hs1", 3.0, saisie_id="a"))
    sans = {"calcul_du_brut": []}
    retour = corrections_pour_revenir(sans, avec)
    assert [r.quantite for r in retour.regularisations_heures_ajoutees] == [3.0]
    assert corrections_pour_revenir(avec, sans).regularisations_heures_retirees == (
        "a",
    )
    assert any("3 h de 12/2025" in p for p in contenu_de_version(avec))
    assert apercu_de_restauration(avec, sans)["retirees"]


def test_la_requete_de_l_ecran_devient_une_correction():
    from pydantic import ValidationError

    from app.modules.payslips.schemas.requests import CorrectionsBulletinRequest

    requete = CorrectionsBulletinRequest(
        regularisations_heures_ajoutees=[
            {
                "nature": "hs1",
                "mois_origine": "2026-09",
                "quantite": 3.5,
                "motif": "Semaine 38 oubliée",
            }
        ],
        regularisations_heures_retirees=["x", "x"],
    )
    domaine = requete.vers_domaine()
    assert domaine.regularisations_heures_ajoutees[0].mois_affiche == "09/2026"
    assert domaine.regularisations_heures_retirees == ("x",)
    with pytest.raises(ValidationError):
        CorrectionsBulletinRequest(
            regularisations_heures_ajoutees=[
                {
                    "nature": "hs1",
                    "mois_origine": "2026-9",
                    "quantite": 1,
                    "motif": "abc",
                }
            ]
        )


def test_la_liste_de_controle_compte_les_heures_regularisees():
    from app.modules.payslips.infrastructure import payslip_list_meta

    source = payslip_list_meta.__file__
    assert "regularisations_heures_du_bulletin" in Path(source).read_text(
        encoding="utf-8"
    )


def test_le_pipeline_heures_transmet_les_regularisations_au_calcul():
    from app.modules.payroll.documents import payslip_run_heures

    source = Path(payslip_run_heures.__file__).read_text(encoding="utf-8")
    assert (
        'contexte.contrat.setdefault("saisie_du_mois", {})[CLE_REGULARISATIONS_HEURES]'
        in source
    )
    assert 'resultat_brut.get("heures_normales_regularisees"' in source
