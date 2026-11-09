"""Événements du contrat : arrêts (60), fin du contrat (62), autres suspensions
(65), indemnités de rupture (52) et jours du plafond (53 unité 40).

Données inventées ; chaque attendu a été lu dans une DSN 2026 de l'ancien
logiciel ou dans le cahier technique NEODeS 2026, cité au cas par cas.
"""

from __future__ import annotations

import copy
import pytest
from datetime import date
from typing import Dict, List, Tuple

from app.modules.dsn_export.application.builder import build_parsed_dsn_from_payroll
from app.modules.dsn_export.domain.evenements import (
    blocs_arret,
    bloc_fin_contrat,
    blocs_suspension,
    indemnites_de_rupture,
    jours_hors_plafond,
    suspensions_du_bulletin,
)
from app.modules.dsn_export.domain.writer import encode_dsn_bytes

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
    "duree_hebdomadaire": 39.0,
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

BULLETIN = {
    "salaire_brut": 2400.0,
    "synthese_net": {"net_imposable": 1900.0, "montant_net_social": 1900.0},
    "calcul_du_brut": [
        {"libelle": "Salaire de base", "quantite": 151.67, "gain": 2100.0},
        {"libelle": "Heures suppl. structurelles majorées à 25%", "quantite": 17.33, "gain": 300.0},
    ],
}


def _lignes(salarie: Dict = None, bulletin: Dict = None, periode: str = "2026-09") -> List[Tuple[str, str]]:
    fichier, _ = build_parsed_dsn_from_payroll(
        SOCIETE,
        [{"employee": salarie or SALARIE, "payslip_data": bulletin or BULLETIN}],
        periode,
    )
    texte = encode_dsn_bytes(fichier).decode("iso-8859-15")
    return [(l.split(",", 1)[0], l.split(",", 1)[1].strip("'")) for l in texte.splitlines()]


def _blocs(lignes, bloc: str) -> List[Dict[str, str]]:
    sortie: List[Dict[str, str]] = []
    precedent = None
    for rubrique, valeur in lignes:
        if not rubrique.startswith(bloc + "."):
            precedent = None
            continue
        numero = rubrique.rsplit(".", 1)[1]
        if precedent is None or numero <= precedent:
            sortie.append({})
        sortie[-1][numero] = valeur
        precedent = numero
    return sortie


def _ordre_des_blocs(lignes) -> List[str]:
    ordre: List[str] = []
    for rubrique, _ in lignes:
        bloc = rubrique.rsplit(".", 1)[0]
        if not ordre or ordre[-1] != bloc:
            ordre.append(bloc)
    return ordre


def _arret(type_absence: str, debut: str, fin: str, **extra) -> Dict:
    jours = []
    courant = date.fromisoformat(debut)
    while courant <= date.fromisoformat(fin):
        jours.append(courant.isoformat())
        courant = date.fromordinal(courant.toordinal() + 1)
    return {"type": type_absence, "selected_days": jours, **extra}


# --------------------------------------------------------------------------
# Arrêts de travail (60)
# --------------------------------------------------------------------------


def test_arret_maladie_veille_de_l_arret_fin_previsionnelle_reprise():
    """Maladie du 16 au 28/03 : dernier jour travaillé 15/03, reprise le 29."""
    blocs = blocs_arret(
        [_arret("arret_maladie", "2026-03-16", "2026-03-28")],
        date(2026, 3, 1),
        date(2026, 3, 31),
    )
    assert blocs == [
        {
            "S21.G00.60.001": "01",
            "S21.G00.60.002": "15032026",
            "S21.G00.60.003": "28032026",
            "S21.G00.60.004": "02",
            "S21.G00.60.010": "29032026",
            "S21.G00.60.011": "01",
        }
    ]


def test_la_prolongation_continue_l_arret_initial():
    """Arrêt du 18/03 prolongé jusqu'au 12/04 : en avril, un seul arrêt qui
    garde son dernier jour travaillé du 17/03 (ancien logiciel, avril)."""
    blocs = blocs_arret(
        [
            _arret("arret_maladie", "2026-03-18", "2026-03-31"),
            _arret("arret_maladie", "2026-04-01", "2026-04-12"),
        ],
        date(2026, 4, 1),
        date(2026, 4, 30),
    )
    assert len(blocs) == 1
    assert blocs[0]["S21.G00.60.002"] == "17032026"
    assert blocs[0]["S21.G00.60.003"] == "12042026"
    assert blocs[0]["S21.G00.60.010"] == "13042026"


def test_adoption_declaree_en_motif_09_quel_que_soit_le_conge_saisi():
    """Cahier technique DSN 2026.1, S21.G00.60.001 : « 09 - adoption ». Un
    congé d'adoption saisi sous la nature maternité ou paternité garde ce motif."""
    for type_absence in ("arret_maternite", "arret_paternite"):
        blocs = blocs_arret(
            [_arret(type_absence, "2026-10-05", "2026-10-30", arret_type="adoption")],
            date(2026, 10, 1),
            date(2026, 10, 31),
        )
        assert [b["S21.G00.60.001"] for b in blocs] == ["09"], type_absence
    blocs = blocs_arret(
        [_arret("arret_paternite", "2026-10-05", "2026-10-30")],
        date(2026, 10, 1),
        date(2026, 10, 31),
    )
    assert [b["S21.G00.60.001"] for b in blocs] == ["03"]


def test_accident_du_travail_jour_travaille_sans_date_de_l_accident():
    """CT 60.002 : le jour de l'accident est travaillé. La date de l'accident
    (60.012) est interdite en DSN mensuelle (DSN-VAL, CST-04) : elle ne se
    déclare qu'au signalement d'arrêt — l'ancien logiciel l'omet aussi."""
    blocs = blocs_arret(
        [_arret("arret_at", "2026-05-23", "2026-05-29", arret_type="accident_travail")],
        date(2026, 5, 1),
        date(2026, 5, 31),
    )
    assert blocs[0]["S21.G00.60.001"] == "06"
    assert blocs[0]["S21.G00.60.002"] == "23052026"
    assert "S21.G00.60.012" not in blocs[0]


def test_accident_anterieur_a_l_arret_le_dernier_jour_est_la_veille():
    """CT 60.002 : la veille de l'arrêt, sauf arrêt prescrit le jour travaillé."""
    blocs = blocs_arret(
        [_arret("arret_maladie_pro", "2026-05-23", "2026-05-29",
                demi_journees={"date_accident": "2026-05-02"})],
        date(2026, 5, 1),
        date(2026, 5, 31),
    )
    assert blocs[0]["S21.G00.60.002"] == "22052026"
    assert "S21.G00.60.012" not in blocs[0]


def test_subrogation_declare_ses_dates_et_l_arret_sans_reprise_n_en_a_pas():
    blocs = blocs_arret(
        [_arret("arret_maladie", "2026-08-17", "2026-09-30", subrogation_active=True)],
        date(2026, 9, 1),
        date(2026, 9, 30),
    )
    assert blocs[0]["S21.G00.60.004"] == "01"
    assert blocs[0]["S21.G00.60.005"] == "17082026"
    assert blocs[0]["S21.G00.60.006"] == "30092026"
    assert "S21.G00.60.010" not in blocs[0]


def test_subrogation_porte_le_compte_de_l_employeur():
    """CT 60.007 / 60.008 : IBAN et BIC de l'employeur obligatoires en subrogation."""
    blocs = blocs_arret(
        [_arret("arret_maladie", "2026-08-17", "2026-09-30", subrogation_active=True)],
        date(2026, 9, 1),
        date(2026, 9, 30),
        compte_employeur=("FR7600000000000000000000000", "CEPAFRPP000"),
    )
    assert blocs[0]["S21.G00.60.007"] == "FR7600000000000000000000000"
    assert blocs[0]["S21.G00.60.008"] == "CEPAFRPP000"


def test_la_paie_dit_si_l_employeur_est_subroge():
    """La demande d'arrêt cochait la subrogation, la paie n'en a rien fait
    (indemnités versées directement au salarié) : on déclare la paie."""
    salarie = {
        **SALARIE,
        "absences_dsn": [_arret("arret_maladie", "2026-08-17", "2026-09-30", subrogation_active=True)],
    }
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["synthese_net"]["subrogation_active"] = False
    arret = _blocs(_lignes(salarie, bulletin), "S21.G00.60")[0]
    assert arret["004"] == "02"
    assert "005" not in arret


# --------------------------------------------------------------------------
# Autres suspensions (65), lues sur les lignes du bulletin
# --------------------------------------------------------------------------


def test_absences_non_payees_et_evenement_familial_lus_sur_le_bulletin():
    bulletin = {
        "calcul_du_brut": [
            {"libelle": "Abs. Abs aut nonpayé 080626", "quantite": 7.63, "perte": 93.93},
            {"libelle": "Abs. Congés s.so 170826-180826", "quantite": 14.0, "perte": 172.34},
            {"libelle": "Abs. Evt familli 250226-270226", "quantite": 21.0, "perte": 271.93},
            {"libelle": "Réduction HS structurelles (jours d'absence)", "quantite": 0.87, "perte": 13.39},
            {"libelle": "Absence maladie 160326-280326", "quantite": 70.0, "perte": 906.44},
        ],
        "details_absences": [
            {"libelle": "Absence injustifiée du 14/09/26 (base)", "quantite": 5.83, "perte": 71.77},
        ],
    }
    assert suspensions_du_bulletin(bulletin) == [
        ("637", date(2026, 2, 25), date(2026, 2, 27)),
        ("501", date(2026, 6, 8), date(2026, 6, 8)),
        ("501", date(2026, 8, 17), date(2026, 8, 18)),
        ("501", date(2026, 9, 14), date(2026, 9, 14)),
    ]


# --------------------------------------------------------------------------
# Fin du contrat (62) et indemnités de rupture (52)
# --------------------------------------------------------------------------


def test_fin_de_cdd_sans_dossier_de_sortie():
    salarie = {**SALARIE, "contract_type": "CDD", "contract_end_date": "2026-09-15"}
    bloc, _ = bloc_fin_contrat(salarie, date(2026, 9, 1), date(2026, 9, 30))
    assert bloc == {
        "S21.G00.62.001": "15092026",
        "S21.G00.62.002": "031",
        "S21.G00.62.006": "15092026",
    }


def test_la_sortie_reprise_garde_son_motif_d_origine():
    """L'import a rangé un départ à la retraite (039) en « démission »."""
    salarie = {
        **SALARIE,
        "sortie_dsn": {
            "exit_type": "demission",
            "last_working_day": "2026-06-30",
            "exit_request_date": "2026-06-30",
            "exit_reason": "Import DSN (039)",
        },
    }
    bloc, _ = bloc_fin_contrat(salarie, date(2026, 6, 1), date(2026, 6, 30))
    assert bloc["S21.G00.62.002"] == "039"


def test_demission_porte_sa_date_de_notification():
    """CCH-12 : 62.003 obligatoire pour une démission (059)."""
    salarie = {
        **SALARIE,
        "sortie_dsn": {
            "exit_type": "demission",
            "last_working_day": "2026-09-29",
            "exit_request_date": "2026-09-01",
        },
    }
    bloc, _ = bloc_fin_contrat(salarie, date(2026, 9, 1), date(2026, 9, 30))
    assert bloc["S21.G00.62.002"] == "059"
    assert bloc["S21.G00.62.003"] == "01092026"


def test_indemnites_de_rupture_reconnues_dans_les_deux_formats():
    bulletin = {
        "calcul_du_brut": [
            {"libelle": "Ind.de précarité des CDD", "gain": 797.04},
            {"libelle": "Ind.de CP des CDD", "gain": 940.23},
            {"libelle": "Prime de précarité (CDD)", "gain": 1069.75},
            {"libelle": "Indemnités de CP", "gain": 104.53},
        ]
    }
    assert indemnites_de_rupture(bulletin) == [("011", 1866.79, True), ("020", 940.23, True)]


def test_fin_de_cdd_dans_la_dsn_du_mois():
    """15/09 : bloc 62, prime de précarité en 52.011 exclue du salaire chômage
    (CT 51.011), périodes de paie bornées à la fin du contrat (CCH-13)."""
    salarie = {**SALARIE, "contract_type": "CDD", "hire_date": "2026-04-07", "contract_end_date": "2026-09-15"}
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["salaire_brut"] = 2152.0
    bulletin["calcul_du_brut"] = [
        {"libelle": "Salaire de base", "quantite": 77.0, "gain": 947.87},
        {"libelle": "Heures suppl. structurelles majorées à 25%", "quantite": 8.8, "gain": 135.41},
        {"libelle": "Prime de précarité (CDD)", "gain": 1069.75},
    ]
    lignes = _lignes(salarie, bulletin)
    assert _blocs(lignes, "S21.G00.62") == [{"001": "15092026", "002": "031", "006": "15092026"}]
    primes = _blocs(lignes, "S21.G00.52")
    assert [(p["001"], p["002"], p.get("006")) for p in primes] == [("011", "1069.75", "00000")]
    remunerations = {b["011"]: b for b in _blocs(lignes, "S21.G00.51")}
    assert remunerations["001"]["013"] == "2152.00"
    assert remunerations["002"]["013"] == "1082.25"
    assert remunerations["001"]["002"] == "15092026"


def test_arret_dans_la_dsn_avant_les_affiliations():
    """Ordre de la norme : 40, 60, 62, 65, 70, 71, puis le versement."""
    salarie = {
        **SALARIE,
        "absences_dsn": [_arret("arret_maladie", "2026-09-01", "2026-09-30")],
        "affiliations_psc": [{"option": "OPT1", "population": "02", "id_affiliation": "1", "id_contrat": "1"}],
    }
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["calcul_du_brut"].append(
        {"libelle": "Absence injustifiée du 14/09/26 (base)", "quantite": 5.83, "perte": 71.77}
    )
    lignes = _lignes(salarie, bulletin)
    ordre = _ordre_des_blocs(lignes)
    assert ordre.index("S21.G00.40") < ordre.index("S21.G00.60") < ordre.index("S21.G00.65")
    assert ordre.index("S21.G00.65") < ordre.index("S21.G00.70") < ordre.index("S21.G00.71")
    assert ordre.index("S21.G00.71") < ordre.index("S21.G00.50")
    assert _blocs(lignes, "S21.G00.60")[0]["002"] == "31082026"
    assert _blocs(lignes, "S21.G00.65") == [{"001": "501", "002": "14092026", "003": "14092026"}]


def test_jours_du_plafond_suivent_le_plafond_retenu_par_la_paie():
    """La paie réduit le plafond au prorata des jours : 3 871,50 sur 4 005,00
    en juin, c'est 29 jours sur 30 (un jour d'absence non payée)."""
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["parametres"] = {"pss_mensuel": 3871.5, "pss_mensuel_plein": 4005.0}
    lignes = _lignes(bulletin=bulletin, periode="2026-06")
    activite = next(
        v for (r, v), (r2, v2) in zip(lignes, lignes[1:] + [("", "")])
        if r == "S21.G00.53.002" and r2 == "S21.G00.53.003" and v2 == "40"
    )
    assert activite == "29.00"


def test_jours_du_plafond_retirent_arrets_et_absences_non_payees_a_defaut():
    """Sans plafond sur le bulletin : 31 jours en mai, moins deux jours non
    payés et sept jours d'accident du travail, font 22 (ancien logiciel)."""
    salarie = {
        **SALARIE,
        "absences_dsn": [_arret("arret_at", "2026-05-23", "2026-05-29", arret_type="accident_travail")],
    }
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["calcul_du_brut"] += [
        {"libelle": "Abs. JF non payé 080526", "quantite": 7.0, "perte": 85.4},
        {"libelle": "Abs. JF non payé 140526", "quantite": 7.0, "perte": 85.4},
    ]
    lignes = _lignes(salarie, bulletin, periode="2026-05")
    activite = next(
        v for (r, v), (r2, v2) in zip(lignes, lignes[1:] + [("", "")])
        if r == "S21.G00.53.002" and r2 == "S21.G00.53.003" and v2 == "40"
    )
    assert activite == "22.00"


# --------------------------------------------------------------------------
# Activité partielle (65 motif 602, 51 type 019)
# --------------------------------------------------------------------------
# Cahier technique 2026.1.2 : 65.001 SIG-11 (602 exige un 51 type 019), 51.012
# SIG-11 (heures obligatoires sur 019). DSN de l'ancien logiciel, sept. 2026 :
# 019 = heures chômées et montant de l'indemnité du bulletin.


def _bulletin_activite_partielle() -> Dict:
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["calcul_du_brut"].append(
        {"libelle": "Heures chômées (act. part.)", "quantite": 20.0, "taux": 14.5, "gain": -290.0}
    )
    bulletin["revenus_hors_brut_imposables"] = [
        {"libelle": "Indemnité activité partielle", "montant": 190.4, "prime_id": "indemnite_activite_partielle"}
    ]
    return bulletin


def test_activite_partielle_saisie_emet_602_et_019():
    lignes = _lignes(bulletin=_bulletin_activite_partielle())
    assert _blocs(lignes, "S21.G00.65") == [{"001": "602", "002": "01092026", "003": "30092026"}]
    types = {b["011"]: b for b in _blocs(lignes, "S21.G00.51")}
    assert types["019"]["012"] == "20.00"
    assert types["019"]["013"] == "190.40"


def test_activite_partielle_lue_sur_un_bulletin_repris_suit_ses_dates():
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["calcul_du_brut"] += [
        {"libelle": "Act. partiel. 040926", "quantite": 7.0, "taux": 14.74, "perte": 103.2},
        {"libelle": "Act. partiel. 170926-180926", "quantite": 14.0, "taux": 14.74, "perte": 206.4},
    ]
    bulletin["primes_non_soumises"] = [{"libelle": "Indemn. activité partielle", "montant": 199.92}]
    lignes = _lignes(bulletin=bulletin)
    assert _blocs(lignes, "S21.G00.65") == [
        {"001": "602", "002": "04092026", "003": "04092026"},
        {"001": "602", "002": "17092026", "003": "18092026"},
    ]
    types = {b["011"]: b for b in _blocs(lignes, "S21.G00.51")}
    assert (types["019"]["012"], types["019"]["013"]) == ("21.00", "199.92")


def test_activite_partielle_en_jours_ne_se_declare_pas_en_heures():
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["calcul_du_brut"].append(
        {"libelle": "Act. partiel. 030626", "quantite": 1, "taux": 140.9091, "perte": 140.91}
    )
    lignes = _lignes(bulletin=bulletin)
    assert _blocs(lignes, "S21.G00.65") == []
    assert "019" not in {b["011"] for b in _blocs(lignes, "S21.G00.51")}


def test_sans_activite_partielle_rien_ne_change():
    lignes = _lignes()
    assert _blocs(lignes, "S21.G00.65") == []
    assert "019" not in {b["011"] for b in _blocs(lignes, "S21.G00.51")}


# --------------------------------------------------------------------------
# Temps partiel thérapeutique (60 motifs 15 à 18, 66)
# --------------------------------------------------------------------------
# Cahier technique 2026.1.2 : 60.001 (valeurs 15 à 18, SIG-13 : bloc 66
# obligatoire), 60.011 (« 02 - reprise temps partiel thérapeutique »), bloc 66.
# Ancien logiciel, 2026 : motif 15 ; dernier jour = veille ; 60.011 = 01 à la
# fin du temps partiel ; 66 borné au mois.


def _tpt(nature: str, debut: str, fin: str) -> Dict:
    return _arret(nature, debut, fin, arret_type="mi_temps_therapeutique")


@pytest.mark.parametrize(
    "nature, motif", [("arret_maladie", "15"), ("arret_at", "16"), ("arret_maladie_pro", "18")]
)
def test_temps_partiel_therapeutique_declare_selon_son_origine(nature, motif):
    blocs = blocs_arret([_tpt(nature, "2026-09-07", "2026-09-25")], date(2026, 9, 1), date(2026, 9, 30))
    assert blocs[0]["S21.G00.60.001"] == motif
    # La veille, même sous la nature accident : ce n'est pas le jour de l'accident.
    assert blocs[0]["S21.G00.60.002"] == "06092026"
    assert blocs[0]["S21.G00.60.011"] == "01"


def test_temps_partiel_apres_un_accident_de_trajet_motif_17():
    absences = [
        _arret("arret_at", "2026-08-03", "2026-08-30", arret_type="accident_trajet"),
        _tpt("arret_at", "2026-09-07", "2026-09-25"),
    ]
    blocs = blocs_arret(absences, date(2026, 9, 1), date(2026, 9, 30))
    assert [b["S21.G00.60.001"] for b in blocs] == ["17"]


def test_reprise_en_temps_partiel_therapeutique_motif_de_reprise_02():
    absences = [
        _arret("arret_maladie", "2026-09-01", "2026-09-11", arret_type="maladie_simple"),
        _tpt("arret_maladie", "2026-09-14", "2026-09-30"),
    ]
    blocs = blocs_arret(absences, date(2026, 9, 1), date(2026, 9, 30))
    assert blocs[0]["S21.G00.60.001"] == "01"
    assert blocs[0]["S21.G00.60.011"] == "02"


def test_reprise_normale_quand_un_autre_arret_suit_de_loin():
    absences = [
        _arret("arret_maladie", "2026-09-01", "2026-09-04", arret_type="maladie_simple"),
        _tpt("arret_maladie", "2026-09-21", "2026-09-30"),
    ]
    blocs = blocs_arret(absences, date(2026, 9, 1), date(2026, 9, 30))
    assert blocs[0]["S21.G00.60.011"] == "01"


def test_bloc_66_borne_au_mois_et_perte_du_bulletin_repris():
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["calcul_du_brut"].append(
        {"libelle": "Tps.part.théra.070926-300926", "quantite": 60.08, "taux": 15.5, "perte": 932.0}
    )
    salarie = {**SALARIE, "absences_dsn": [_tpt("arret_maladie", "2026-09-07", "2026-10-09")]}
    lignes = _lignes(salarie=salarie, bulletin=bulletin)
    assert _blocs(lignes, "S21.G00.66") == [{"001": "07092026", "002": "30092026", "003": "932.00"}]
    ordre = _ordre_des_blocs(lignes)
    assert ordre.index("S21.G00.60") < ordre.index("S21.G00.66") < ordre.index("S21.G00.50")


def test_bloc_66_perte_de_la_ligne_d_arret_du_bulletin_calcule():
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["calcul_du_brut"] += [
        {"libelle": "Absence maladie du 01/09 au 04/09", "perte": 200.0, "is_arret_maladie": True},
        {"libelle": "Absence maladie du 07/09 au 25/09", "perte": 412.5, "is_arret_maladie": True},
    ]
    salarie = {**SALARIE, "absences_dsn": [_tpt("arret_maladie", "2026-09-07", "2026-09-25")]}
    assert _blocs(_lignes(salarie=salarie, bulletin=bulletin), "S21.G00.66")[0]["003"] == "412.50"


def test_pas_de_bloc_66_pour_un_arret_ordinaire():
    salarie = {**SALARIE, "absences_dsn": [_arret("arret_maladie", "2026-09-07", "2026-09-11")]}
    assert _blocs(_lignes(salarie=salarie), "S21.G00.66") == []


def test_absence_du_mois_d_avant_portee_par_la_fenetre_garde_sa_vraie_date():
    """R-469 : fenêtre décalée (Colorplast, avant-dernier vendredi) : une journée d'absence du
    29/09 passe sur le bulletin d'octobre. La DSN lit la date du libellé, jamais le mois du
    bulletin ; 65.002 reste ≤ fin du mois principal (CT § 4.4.12) et rien ne sort du plafond
    d'octobre (53 unité 40), puisque le jour n'est pas dans le mois civil déclaré."""
    bulletin = {
        "details_absences": [
            {"libelle": "Absence non rémunérée du 29/09/26", "quantite": 7.0, "perte": 90.0},
            {"libelle": "Absence injustifiée du 05/10/26 (base)", "quantite": 7.0, "perte": 90.0},
        ],
    }
    assert blocs_suspension(bulletin) == [
        {"S21.G00.65.001": "501", "S21.G00.65.002": "29092026", "S21.G00.65.003": "29092026"},
        {"S21.G00.65.001": "501", "S21.G00.65.002": "05102026", "S21.G00.65.003": "05102026"},
    ]
    assert jours_hors_plafond([], bulletin, date(2026, 10, 1), date(2026, 10, 31)) == 1
