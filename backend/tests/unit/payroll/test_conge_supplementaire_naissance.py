"""Congé supplémentaire de naissance (R-231) : saisi, retenu, déclaré en motif 20.

Sources ouvertes le 08/11/2026 :
- Code du travail L1225-46-2 (suspension du contrat, 1 ou 2 mois) et L1225-46-3
  (assimilé au travail effectif pour l'ancienneté), code.travail.gouv.fr ;
- service-public F39685 (vérifiée le 03/06/2026) : « ne perçoit pas de salaire »,
  indemnité de la CPAM à 70 % puis 60 % du salaire net ;
- entreprendre.service-public F39687 (vérifiée le 02/11/2026) : déclaration en DSN
  dans les 5 jours, formulaire PDF sur le compte employeur le même jour ;
- cahier technique DSN 2026.1, S21.G00.60.001 : « 20 - Congé supplémentaire de
  naissance ».
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.absences.domain.nature_arret import incoherence_nature_type_d_arret
from app.modules.absences.schemas.requests import AbsenceRequestCreate
from app.modules.dsn_export.domain.evenements import blocs_arret, periodes_d_arret
from app.modules.dsn_export.domain.signalements import signalements_a_faire
from app.modules.payroll.engine.calcul_brut import LIBELLES_ARRET, _nature_de_l_arret
from app.modules.payroll.engine.maintien_salaire_service import (
    _qualifier_arret,
    calculer_maintien,
    compute_jours_avec_maintien_mois,
    resolve_subrogation_active,
)
from app.shared.domain.dixieme_conges import part_reconstituee

pytestmark = pytest.mark.unit

CSN = "conge_supplementaire_naissance"
JANVIER = (date(2027, 1, 1), date(2027, 1, 31))


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(
        salaire_base_mensuel=2400.0,
        statut_salarie="Non-Cadre",
        baremes={
            "pss": {"annuel": 48060.0},
            "ij_plafonds": {
                "maladie": 42.97,
                "maternite_paternite": 104.02,
                "at_mp": 240.49,
                "at_mp_majoree": 320.66,
            },
        },
        contrat={"contrat": {"date_entree": "2021-08-01", "statut": "Non-Cadre"}},
    )


def _settings(**extra):
    from app.modules.maintenance_settings.application.queries import _defaults

    return {**_defaults("soc").model_dump(mode="json"), **extra}


def _conge(settings, *, ctx=None):
    return calculer_maintien(
        {
            "arret_type": CSN,
            "date_debut": "2027-01-04",
            "date_fin": "2027-01-31",
            "subrogation_active": True,
            "nombre_enfants": 0,
            "salaire_periode_reelle": 0.0,
        },
        ctx or _ctx(),
        settings,
        *JANVIER,
    )


def _absence(nature="arret_paternite", du="2027-01-04", au="2027-01-08", **extra):
    jours = [date.fromisoformat(du).toordinal() + k for k in range(
        date.fromisoformat(au).toordinal() - date.fromisoformat(du).toordinal() + 1
    )]
    return {
        "id": "a1",
        "type": nature,
        "arret_type": CSN,
        "selected_days": [date.fromordinal(j).isoformat() for j in jours],
        "created_at": "2027-01-04T08:00:00",
        "subrogation_active": False,
        **extra,
    }


@pytest.mark.parametrize("nature", ["arret_maternite", "arret_paternite"])
def test_saisissable_sous_maternite_et_paternite(nature):
    demande = AbsenceRequestCreate(
        employee_id="e1",
        type=nature,
        arret_type=CSN,
        date_debut=date(2027, 1, 4),
        date_fin=date(2027, 1, 31),
    )
    assert demande.arret_type == CSN
    assert incoherence_nature_type_d_arret(nature, CSN) is None


def test_refuse_sous_un_arret_maladie():
    assert "Congé supplémentaire de naissance" in incoherence_nature_type_d_arret(
        "arret_maladie", CSN
    )


def test_pas_de_carence_comme_les_conges_de_parentalite():
    qualification = _qualifier_arret(CSN)
    assert qualification["carence_ss_jours"] == 0
    assert qualification["est_maternite"] is True


def test_aucun_maintien_par_defaut_et_subrogation_eteinte():
    r = _conge(_settings(subrogation_mode="when_maintien"))
    assert r["maintien"]["maintien_verse"] == 0
    assert r["maintien"]["maintien_applicable"] is False
    assert "congé supplémentaire de naissance" in r["maintien"]["motif_non_maintien"]
    assert r["subrogation_active"] is False


def test_le_reglage_de_maintien_des_conges_de_parentalite_ne_s_y_applique_pas():
    """Le réglage parle de maternité, de paternité et d'adoption ; F39685 dit
    que le salarié ne perçoit pas de salaire."""
    r = _conge(_settings(maintain_parental_leave=True))
    assert r["maintien"]["maintien_verse"] == 0
    assert r["subrogation_active"] is False


def test_aucun_jour_maintenu_meme_reglage_allume():
    jours = compute_jours_avec_maintien_mois(
        {"arret_type": CSN, "date_debut": "2027-01-04", "date_fin": "2027-01-31"},
        _ctx(),
        _settings(maintain_parental_leave=True),
        *JANVIER,
    )
    assert jours == set()


def test_l_indemnite_de_la_cpam_n_est_pas_estimee():
    """Ni l'IJ de maternité ni l'IJ de maladie : 70 % puis 60 % du net, à part."""
    r = _conge(_settings())
    assert r["ijss"]["ijss_theorique"] == 0
    assert r["ijss"]["nb_jours_indemnises"] == 0


def test_la_rh_est_prevenue_de_l_indemnite_et_des_conges_payes():
    alertes = " ".join(_conge(_settings())["alertes"])
    assert "versée par la CPAM" in alertes
    assert "L3141-5" in alertes


def test_le_motif_dit_le_conge_meme_sans_anciennete():
    ctx = _ctx()
    ctx.contrat = {"contrat": {"date_entree": "2026-12-01", "statut": "Non-Cadre"}}
    alertes = _conge(_settings(), ctx=ctx)["alertes"]
    assert not any("Ancienneté insuffisante" in a for a in alertes)


def test_la_subrogation_reste_eteinte_meme_demandee():
    assert resolve_subrogation_active({"subrogation_mode": "when_maintien"}, CSN, True, True) is False
    assert resolve_subrogation_active({"subrogation_mode": "when_maintien"}, "paternite", True, True) is True


def test_le_bulletin_dit_le_conge():
    nature = _nature_de_l_arret(
        {"type": "arret_maladie", "source_absence": "arret_paternite", "arret_type": CSN}
    )
    assert LIBELLES_ARRET[nature] == "congé supplémentaire de naissance"


def test_le_dixieme_ne_retient_pas_le_taux_de_la_maladie():
    assert part_reconstituee(CSN) == 1.0
    assert part_reconstituee("Absence congé supplémentaire de naissance du 04/01/27") == 1.0


@pytest.mark.parametrize("nature", ["arret_maternite", "arret_paternite"])
def test_dsn_motif_20(nature):
    blocs = blocs_arret([_absence(nature)], *JANVIER)
    assert [b["S21.G00.60.001"] for b in blocs] == ["20"]
    assert blocs[0]["S21.G00.60.004"] == "02"
    assert blocs[0]["S21.G00.60.002"] == "03012027"


def test_deux_fractions_font_deux_periodes():
    periodes = periodes_d_arret(
        [
            _absence(du="2027-01-04", au="2027-01-29"),
            {**_absence(du="2027-03-01", au="2027-03-26"), "id": "a2"},
        ]
    )
    assert [(p.motif, p.debut) for p in periodes] == [
        ("20", date(2027, 1, 4)),
        ("20", date(2027, 3, 1)),
    ]


def test_le_signalement_rappelle_le_formulaire():
    [ligne] = signalements_a_faire({"e1": [_absence()]}, [], depuis=None, effectif=10)
    assert ligne.motif == "20"
    assert ligne.a_deposer_avant == date(2027, 1, 9)
    assert "formulaire" in ligne.a_verifier


def test_le_signalement_fait_verifier_le_dernier_jour_apres_un_autre_arret():
    paternite = {
        "id": "p1",
        "type": "arret_paternite",
        "arret_type": "paternite",
        "selected_days": ["2027-01-01", "2027-01-02", "2027-01-03"],
        "created_at": "2027-01-01T08:00:00",
    }
    lignes = signalements_a_faire({"e1": [paternite, _absence()]}, [], depuis=None, effectif=10)
    [csn] = [l for l in lignes if l.motif == "20"]
    assert "dernier jour travaillé" in csn.a_verifier
