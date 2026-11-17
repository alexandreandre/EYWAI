"""Activité partielle : les vraies dates des jours chômés au bloc 65 (602).

Retour de la RH cliente (Lyon, 17/11/2026) : la DSN déclarait les heures
d'activité partielle sans les dates des jours chômés (un bloc 602 sur toute la
période). Les dates viennent maintenant du calendrier, mêmes jours que ceux
que le bulletin paie.

Sources ouvertes :
- fiche net-entreprises n° 2309 « L'activité partielle » (modifiée le
  27/06/2025) : « S'il y a différentes périodes dans le mois, il y a autant de
  bloc S21.G00.65 que de périodes » ; arrêt les 3 premiers jours de chaque
  semaine → « 4 blocs de suspension chacun de 3 jours avec comme date de
  début le lundi et date de fin le mercredi » ;
- cahier technique NEODeS CT2026.1.2, S21.G00.65.003 : pour le motif 602, la
  date de fin réelle de la suspension ; 65.002 CCH-13 : pas après la fin du
  contrat ; 65.001 SIG-11 : le 602 va avec un 51 de type 019.

Données inventées.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Tuple

import pytest

from app.modules.activite_partielle.application import service as ap_service
from app.modules.dsn_export.application.builder import build_parsed_dsn_from_payroll
from app.modules.dsn_export.domain.deux_contrats import evenements_du_contrat
from app.modules.dsn_export.domain.evenements import plages_consecutives
from app.modules.dsn_export.domain.writer import encode_dsn_bytes

pytestmark = pytest.mark.unit

SOCIETE = {
    "siret": "12345678900011",
    "name": "Société d'essai",
    "address": {"rue": "1 rue de l'Essai", "code_postal": "01000", "ville": "BOURG EN BRESSE"},
    "code_naf": "2229A",
    "taux_at_mp": 3.15,
}

SALARIE = {
    "id": "e1",
    "first_name": "Paul",
    "last_name": "ESSAI",
    "nir": "177017512345678",
    "sexe": "M",
    "date_naissance": "1977-01-01",
    "lieu_naissance": "PARIS (75)",
    "adresse": {"rue": "1 rue du Test", "code_postal": "01000", "ville": "BOURG EN BRESSE"},
    "hire_date": "2021-09-13",
    "contract_type": "CDI",
    "statut": "Non-Cadre",
    "duree_hebdomadaire": 35.0,
    "classification_conventionnelle": {
        "pcs": "674a",
        "idcc": "0292",
        "position": "200",
        "niveau_dsn": "710",
        "classification_dsn": "252HK",
        "taux_at_individuel_dsn": "3.15",
        "code_statut_dsn": "06",
        "numero_contrat_dsn": "00000",
    },
}

CADRE_AU_FORFAIT = {
    **SALARIE,
    "id": "e2",
    "nir": "180017512345612",
    "statut": "Cadre",
    "is_forfait_jour": True,
    "duree_hebdomadaire": None,
    "classification_conventionnelle": {
        **SALARIE["classification_conventionnelle"],
        "pcs": "372c",
        "code_statut_dsn": "02",
    },
}


def _bulletin(heures: float, indemnite: float, *, taux: float = 14.5) -> Dict:
    bulletin = {
        "salaire_brut": 2400.0,
        "synthese_net": {"net_imposable": 1900.0, "montant_net_social": 1900.0},
        "calcul_du_brut": [{"libelle": "Salaire de base", "quantite": 151.67, "gain": 2400.0}],
    }
    if heures:
        bulletin["calcul_du_brut"].append(
            {
                "libelle": "Heures chômées (act. part.)",
                "quantite": heures,
                "taux": taux,
                "gain": -round(heures * taux, 2),
            }
        )
        bulletin["revenus_hors_brut_imposables"] = [
            {
                "libelle": "Indemnité activité partielle",
                "montant": indemnite,
                "prime_id": "indemnite_activite_partielle",
            }
        ]
    return bulletin


def _jours(*jours: Tuple[str, float]) -> List[Dict]:
    return [{"date": quand, "heures": heures} for quand, heures in jours]


def _dsn(salarie: Dict, bulletin: Dict, periode: str = "2026-09"):
    fichier, avertissements = build_parsed_dsn_from_payroll(
        SOCIETE, [{"employee": salarie, "payslip_data": bulletin}], periode
    )
    texte = encode_dsn_bytes(fichier).decode("iso-8859-15")
    lignes = [(l.split(",", 1)[0], l.split(",", 1)[1].strip("'")) for l in texte.splitlines()]
    return lignes, avertissements


def _blocs(lignes, bloc: str) -> List[Dict[str, str]]:
    sortie: List[Dict[str, str]] = []
    for rubrique, valeur in lignes:
        if not rubrique.startswith(bloc + "."):
            continue
        suffixe = rubrique.rsplit(".", 1)[1]
        if suffixe == "001" or not sortie:
            sortie.append({})
        sortie[-1][suffixe] = valeur
    return sortie


def _hors_bloc_65(lignes):
    """Tout sauf les blocs 65 et le nombre de rubriques du fichier (S90)."""
    return [
        (r, v) for r, v in lignes if not r.startswith("S21.G00.65.") and r != "S90.G00.90.001"
    ]


def _nombre_de_rubriques(lignes) -> int:
    return int(dict(lignes)["S90.G00.90.001"])


# --------------------------------------------------------------------------
# Plages de jours consécutifs
# --------------------------------------------------------------------------


def test_les_jours_qui_se_suivent_font_une_plage():
    assert plages_consecutives(
        [date(2026, 9, 14), date(2026, 9, 8), date(2026, 9, 9), date(2026, 9, 11), date(2026, 9, 9)]
    ) == [
        (date(2026, 9, 8), date(2026, 9, 9)),
        (date(2026, 9, 11), date(2026, 9, 11)),
        (date(2026, 9, 14), date(2026, 9, 14)),
    ]


def test_une_plage_passe_d_un_mois_a_l_autre():
    assert plages_consecutives([date(2026, 8, 31), date(2026, 9, 1)]) == [
        (date(2026, 8, 31), date(2026, 9, 1))
    ]


# --------------------------------------------------------------------------
# Bloc 65 (602) daté par le calendrier
# --------------------------------------------------------------------------


def test_salarie_en_heures_un_bloc_par_plage_de_jours_chomes():
    """Mardi 8 et mercredi 9 (une plage), vendredi 11, lundi 14 : trois blocs."""
    salarie = {
        **SALARIE,
        "activite_partielle_dsn": _jours(
            ("2026-09-08", 7.0), ("2026-09-09", 7.0), ("2026-09-11", 3.0), ("2026-09-14", 7.0)
        ),
    }
    lignes, avertissements = _dsn(salarie, _bulletin(24.0, 210.0))
    assert _blocs(lignes, "S21.G00.65") == [
        {"001": "602", "002": "08092026", "003": "09092026"},
        {"001": "602", "002": "11092026", "003": "11092026"},
        {"001": "602", "002": "14092026", "003": "14092026"},
    ]
    types = {b["011"]: b for b in _blocs(lignes, "S21.G00.51")}
    assert (types["019"]["012"], types["019"]["013"]) == ("24.00", "210.00")
    assert not [a for a in avertissements if "ctivité partielle" in a]


def test_cadre_au_forfait_jours_un_bloc_par_jour_chome_isole():
    """Jeudi 3 et jeudi 10 chômés (7 h chacun au forfait) : deux blocs."""
    salarie = {
        **CADRE_AU_FORFAIT,
        "activite_partielle_dsn": _jours(("2026-09-03", 7.0), ("2026-09-10", 7.0)),
    }
    lignes, avertissements = _dsn(salarie, _bulletin(14.0, 260.0, taux=26.0))
    assert _blocs(lignes, "S21.G00.65") == [
        {"001": "602", "002": "03092026", "003": "03092026"},
        {"001": "602", "002": "10092026", "003": "10092026"},
    ]
    types = {b["011"]: b for b in _blocs(lignes, "S21.G00.51")}
    assert types["019"]["012"] == "14.00"
    assert not [a for a in avertissements if "ctivité partielle" in a]


@pytest.mark.parametrize("salarie", [SALARIE, CADRE_AU_FORFAIT], ids=["heures", "forfait"])
def test_seules_les_dates_du_602_changent(salarie):
    """Le reste de la DSN est celui d'avant (bloc 602 sur toute la période)."""
    bulletin = _bulletin(14.0, 120.0)
    avant, avertissements_avant = _dsn(salarie, bulletin)
    apres, avertissements_apres = _dsn(
        {**salarie, "activite_partielle_dsn": _jours(("2026-09-03", 7.0), ("2026-09-10", 7.0))},
        bulletin,
    )
    assert _blocs(avant, "S21.G00.65") == [{"001": "602", "002": "01092026", "003": "30092026"}]
    assert _hors_bloc_65(apres) == _hors_bloc_65(avant)
    # Un bloc 65 de plus (trois rubriques) : deux jours isolés au lieu d'une période.
    assert _nombre_de_rubriques(apres) == _nombre_de_rubriques(avant) + 3
    assert any("sans dates de chômage" in a for a in avertissements_avant)
    assert not any("sans dates de chômage" in a for a in avertissements_apres)


@pytest.mark.parametrize("salarie", [SALARIE, CADRE_AU_FORFAIT], ids=["heures", "forfait"])
def test_un_mois_sans_activite_partielle_ne_change_pas(salarie):
    bulletin = _bulletin(0, 0)
    avant, avertissements_avant = _dsn(salarie, bulletin)
    apres, avertissements_apres = _dsn({**salarie, "activite_partielle_dsn": []}, bulletin)
    assert apres == avant
    assert avertissements_apres == avertissements_avant
    assert _blocs(apres, "S21.G00.65") == []


def test_des_jours_au_calendrier_sans_ligne_au_bulletin_ne_declarent_rien():
    """Le 602 exige le 019 (65.001 SIG-11) : le bulletin fait foi des heures."""
    salarie = {**SALARIE, "activite_partielle_dsn": _jours(("2026-09-03", 7.0))}
    lignes, _ = _dsn(salarie, _bulletin(0, 0))
    assert _blocs(lignes, "S21.G00.65") == []


def test_calendrier_change_depuis_le_bulletin_se_dit():
    salarie = {**SALARIE, "activite_partielle_dsn": _jours(("2026-09-03", 7.0))}
    lignes, avertissements = _dsn(salarie, _bulletin(14.0, 120.0))
    assert _blocs(lignes, "S21.G00.65") == [{"001": "602", "002": "03092026", "003": "03092026"}]
    assert any("7 h chômées au calendrier, 14 h au bulletin" in a for a in avertissements)


def test_pas_de_jour_chome_apres_la_fin_du_contrat():
    """65.002 CCH-13 : la suspension ne commence pas après la fin du contrat."""
    salarie = {
        **SALARIE,
        "contract_type": "CDD",
        "contract_end_date": "2026-09-15",
        "activite_partielle_dsn": _jours(("2026-09-14", 7.0), ("2026-09-15", 7.0), ("2026-09-16", 7.0)),
    }
    lignes, _ = _dsn(salarie, _bulletin(14.0, 120.0))
    assert _blocs(lignes, "S21.G00.65") == [{"001": "602", "002": "14092026", "003": "15092026"}]


def test_une_ligne_reprise_garde_les_dates_de_son_libelle():
    bulletin = _bulletin(0, 0)
    bulletin["calcul_du_brut"].append(
        {"libelle": "Act. partiel. 170926-180926", "quantite": 14.0, "taux": 14.74, "perte": 206.4}
    )
    bulletin["primes_non_soumises"] = [{"libelle": "Indemn. activité partielle", "montant": 120.0}]
    salarie = {**SALARIE, "activite_partielle_dsn": _jours(("2026-09-03", 7.0))}
    lignes, _ = _dsn(salarie, bulletin)
    assert _blocs(lignes, "S21.G00.65") == [{"001": "602", "002": "17092026", "003": "18092026"}]


def test_deux_contrats_chacun_ses_jours_chomes():
    evenements = {"activite_partielle_dsn": _jours(("2026-11-05", 7.0), ("2026-11-20", 7.0))}
    ancien = evenements_du_contrat(evenements, date(2026, 1, 1), date(2026, 11, 10))
    nouveau = evenements_du_contrat(evenements, date(2026, 11, 17), None)
    assert ancien["activite_partielle_dsn"] == _jours(("2026-11-05", 7.0))
    assert nouveau["activite_partielle_dsn"] == _jours(("2026-11-20", 7.0))


# --------------------------------------------------------------------------
# Jours lus au calendrier, période du bulletin
# --------------------------------------------------------------------------


def _ligne_calendrier(eid, annee, mois, prevu, reel=()):
    return {
        "employee_id": eid,
        "year": annee,
        "month": mois,
        "planned_calendar": {"calendrier_prevu": list(prevu)},
        "actual_hours": {"calendrier_reel": list(reel)},
    }


def _ap(jour, heures=7.0):
    return {"jour": jour, "type": "activite_partielle", "heures_prevues": heures}


def _travail(jour, heures=7.0):
    return {"jour": jour, "type": "travail", "heures_prevues": heures}


@pytest.fixture
def periode_du_bulletin(monkeypatch):
    """Heures : fenêtre des variables 21/08–20/09 ; forfait : mois civil."""
    bornes = {
        False: (date(2026, 8, 21), date(2026, 9, 20)),
        True: (date(2026, 9, 1), date(2026, 9, 30)),
    }
    monkeypatch.setattr(
        ap_service,
        "bornes_du_bulletin",
        lambda company_id, year, month, *, forfait_jours: bornes[forfait_jours],
    )
    monkeypatch.setattr(ap_service, "_apres_la_reprise", lambda c, y, m, debut: debut)
    monkeypatch.setattr(ap_service, "lire_reglage", lambda c: {"heures_par_jour": None})


def test_jours_lus_dans_la_periode_du_bulletin(periode_du_bulletin):
    lignes = [
        _ligne_calendrier("e1", 2026, 8, [_ap(25), _ap(26), _travail(27)]),
        _ligne_calendrier(
            "e1", 2026, 9, [_ap(3), _ap(4, 7.0), _travail(5), _ap(22)], [{"jour": 4, "heures_faites": 3.5}]
        ),
        _ligne_calendrier("e2", 2026, 9, [_ap(3, 1), _ap(22, 1), _travail(23, 1)]),
        _ligne_calendrier("e3", 2026, 9, [_travail(3)]),
    ]
    jours = ap_service.jours_chomes_des_bulletins(
        "societe",
        2026,
        9,
        [
            {"id": "e1", "duree_hebdomadaire": 35},
            {"id": "e2", "is_forfait_jour": True},
            {"id": "e3", "duree_hebdomadaire": 35},
        ],
        ap_service.calendriers_des_lignes(lignes, 2026, 9),
    )
    # En heures : 25 et 26/08 sont payés en septembre, le 22/09 ira en
    # octobre ; le 4/09 n'a chômé que la demi-journée non faite.
    assert jours["e1"] == [
        (date(2026, 8, 25), 7.0),
        (date(2026, 8, 26), 7.0),
        (date(2026, 9, 3), 7.0),
        (date(2026, 9, 4), 3.5),
    ]
    # Au forfait : période civile, 7 h le jour chômé.
    assert jours["e2"] == [(date(2026, 9, 3), 7.0), (date(2026, 9, 22), 7.0)]
    assert "e3" not in jours


def test_le_chargeur_de_la_dsn_joint_les_jours_chomes(monkeypatch, periode_du_bulletin):
    from app.modules.exports.infrastructure import export_dsn
    from tests.unit.base_en_memoire import BaseEnMemoire

    BaseEnMemoire(
        {"employee_schedules": [_ligne_calendrier("e1", 2026, 9, [_ap(8), _ap(9), _travail(10)])]}
    ).brancher(monkeypatch)
    evenements = export_dsn._evenements_dsn(
        "societe", "2026-09", ["e1", "e2"], {"e1": {"id": "e1", "duree_hebdomadaire": 35}}
    )
    assert evenements["e1"]["activite_partielle_dsn"] == _jours(
        ("2026-09-08", 7.0), ("2026-09-09", 7.0)
    )
    assert "activite_partielle_dsn" not in evenements["e2"]
