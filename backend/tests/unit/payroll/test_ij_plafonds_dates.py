"""Plafonds d'IJ : un barème daté, lu à la date de l'accident ou du début de l'arrêt.

Le barème `ij_plafonds` (montant maximal de l'indemnité journalière par jour)
n'était pas daté. Le décret n° 2026-909 du 30/09/2026 abaisse le plafond des
IJ d'accident du travail et de maladie professionnelle pour les arrêts qui
surviennent à compter du 01/11/2026 (service-public, actualité A19080 du
08/10/2026, ouverte le 12/10/2026 : « concerne les arrêts qui surviendront à
compter de cette date » ; 0,226 % du PASS au lieu de 0,834 %, soit 65,17 € puis
86,89 € par jour au lieu de 240,49 € puis 320,66 €). Le jour où le relevé
automatique écrirait 65,17 €, un arrêt commencé en octobre aurait été plafonné
à tort.

Le barème porte désormais ses paliers (`historique`, date d'effet). La règle
suit la date de l'accident quand elle est saisie, sinon le début de l'arrêt
(celui de l'arrêt prolongé, pour une prolongation).
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien

pytestmark = pytest.mark.unit

PALIER_2026 = {"maladie": 42.97, "maternite_paternite": 104.02, "at_mp": 240.49, "at_mp_majoree": 320.66}
PALIER_DECRET = {"maladie": 42.97, "maternite_paternite": 104.02, "at_mp": 65.17, "at_mp_majoree": 86.89}

#: Le relevé a déjà écrit les montants du décret ; les paliers gardent l'ancien.
BAREME_DATE = {
    **PALIER_DECRET,
    "historique": [
        {"date_debut": "2026-01-01", **PALIER_2026},
        {"date_debut": "2026-11-01", **PALIER_DECRET},
    ],
}

NOVEMBRE = (date(2026, 11, 1), date(2026, 11, 30))


def _ctx(ij_plafonds) -> SimpleNamespace:
    return SimpleNamespace(
        salaire_base_mensuel=5000.0,
        statut_salarie="Non-Cadre",
        baremes={"pss": {"annuel": 48060.0}, "ij_plafonds": ij_plafonds},
        contrat={"contrat": {"date_entree": "2020-01-06", "statut": "Non-Cadre"}},
    )


def _ij_par_jour(debut, fin="2026-11-20", ij_plafonds=BAREME_DATE, **extra):
    r = calculer_maintien(
        {
            "arret_type": "accident_travail",
            "date_debut": debut,
            "date_fin": fin,
            "subrogation_active": False,
            "nombre_enfants": 0,
            "salaire_periode_reelle": 0.0,
            **extra,
        },
        _ctx(ij_plafonds),
        {"apply_legal_maintenance": True, "min_seniority_months": 12},
        *NOVEMBRE,
    )
    ijss = r["ijss"]
    return round(ijss["ijss_theorique"] / ijss["nb_jours_indemnises"], 2)


SANS_PLAFOND = round(5000.0 / 30.42 * 0.6, 2)  # 98,62 €


# Les jours comparés restent avant le 29e jour de l'arrêt (60 %).


def test_un_arret_d_octobre_garde_l_ancien_plafond_meme_releve_au_nouveau():
    assert _ij_par_jour("2026-10-15", fin="2026-11-10") == SANS_PLAFOND


def test_un_arret_de_novembre_prend_le_plafond_du_decret():
    assert _ij_par_jour("2026-11-05") == 65.17


def test_le_palier_du_decret_s_applique_meme_si_le_releve_n_est_pas_passe():
    bareme = {**PALIER_2026, "historique": BAREME_DATE["historique"]}
    assert _ij_par_jour("2026-11-05", ij_plafonds=bareme) == 65.17


def test_la_date_de_l_accident_saisie_l_emporte_sur_le_debut_de_l_arret():
    # Accident du 20/10, arrêt prescrit à partir du 05/11 : ancien plafond.
    assert _ij_par_jour("2026-11-05", date_accident="2026-10-20") == SANS_PLAFOND


def test_une_prolongation_garde_le_plafond_de_l_arret_prolonge():
    connus = [{"debut": "2026-10-10", "fin": "2026-11-01", "type": "accident_travail"}]
    assert _ij_par_jour("2026-11-02", fin="2026-11-05", arrets_connus=connus) == SANS_PLAFOND


def test_un_bareme_sans_paliers_se_lit_comme_avant():
    assert _ij_par_jour("2026-10-15", fin="2026-11-10", ij_plafonds=dict(PALIER_DECRET)) == 65.17


def test_le_bulletin_lit_la_date_de_l_accident_posee_au_calendrier():
    from app.modules.payroll.documents.payslip_run_heures import _extraire_arret_pour_maintien

    class _Ctx:
        contrat = {"contrat": {"temps_travail": {}}}

    cal = [
        {"date_complete": "2026-11-05", "type": "arret_maladie", "arret_type": "accident_travail",
         "date_debut_arret_reel": "2026-11-05", "date_fin_arret_reel": "2026-11-20",
         "date_accident": "2026-10-20"},
    ]
    arret = _extraire_arret_pour_maintien(cal, _Ctx(), *NOVEMBRE)
    assert arret["date_accident"] == "2026-10-20"


def test_le_releve_automatique_garde_les_paliers():
    import sys
    from pathlib import Path

    racine = Path(__file__).resolve().parents[3] / "scraping"
    if str(racine) not in sys.path:
        sys.path.insert(0, str(racine))
    from core.migrated_specs import SPEC_IJ_MALADIE

    nouveau = SPEC_IJ_MALADIE.build_config_data(dict(PALIER_DECRET), {"config_data": BAREME_DATE})
    assert nouveau["historique"] == BAREME_DATE["historique"]
    assert nouveau["at_mp"] == 65.17
