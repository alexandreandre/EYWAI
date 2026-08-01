"""Tests d'extraction enrichie (norme P26 / Cegid) vers la fiche collaborateur.

Couvre les points révélés par un vrai fichier Cegid Quadra Paie :
- quotité/modalité de temps de travail sur les rubriques .013/.014 (et non .011/.012) ;
- prélèvement à la source (taux/type/identifiant) issu du bloc S21.G00.50 ;
- sexe (S21.G00.30.005) mappé en M/F ;
- dispositif, numéro de contrat et position conventionnelle.
"""

from app.modules.dsn_import.application.mapping import map_employee_payload
from app.modules.dsn_import.domain.normalize import (
    map_sexe,
    map_temps_partiel_dsn,
)
from app.modules.dsn_import.domain.parser import parse_dsn_content


def _individu_from(lines: str):
    content = (
        "S10.G00.00.006,'P26V01'\n"
        "S20.G00.05.005,'01012026'\n"
        "S21.G00.06.001,'951474782'\n"
        "S21.G00.11.001,'00020'\n"
        + lines
    ).encode("latin-1")
    dsn = parse_dsn_content(content)
    return dsn.etablissement.individus[0], dsn.etablissement


def test_temps_plein_quotite_mensuelle_donne_35h():
    """151,67 h mensuelles en .013 => 35 h hebdo, temps plein (modalité 10)."""
    is_tp, heures = map_temps_partiel_dsn("10", "10", "151.67", "151.67")
    assert is_tp is False
    assert heures == 35.0


def test_temps_partiel_par_comparaison_quotite():
    is_tp, heures = map_temps_partiel_dsn("20", "10", "75.83", "151.67")
    assert is_tp is True
    assert heures == round(75.83 * 12 / 52, 2)


def test_temps_partiel_defaut_sans_info():
    is_tp, heures = map_temps_partiel_dsn("", "", "", "")
    assert is_tp is False
    assert heures == 35.0


def test_temps_partiel_modalite_sans_quotite_reste_flag_pour_relecture():
    is_tp, heures = map_temps_partiel_dsn("20", "10", "", "151.67")
    assert is_tp is True
    assert heures == 35.0


def test_review_temps_partiel_incoherent():
    from app.modules.dsn_import.application.mapping import compute_review_reasons_from_payload

    reasons = compute_review_reasons_from_payload(
        {"is_temps_partiel": True, "duree_hebdomadaire": 35.0, "salaire_de_base": {"valeur": 1800}}
    )
    assert "temps_partiel_incoherent" in reasons


def test_map_sexe():
    assert map_sexe("01") == "M"
    assert map_sexe("02") == "F"
    assert map_sexe("") is None


def test_payload_extrait_pas_sexe_et_classification():
    lines = (
        "S21.G00.30.001,'180032710123448'\n"
        "S21.G00.30.002,'LEMAIRE'\n"
        "S21.G00.30.004,'Sophie'\n"
        "S21.G00.30.005,'02'\n"
        "S21.G00.30.006,'15031985'\n"
        "S21.G00.40.001,'01012020'\n"
        "S21.G00.40.002,'04'\n"
        "S21.G00.40.007,'01'\n"
        "S21.G00.40.008,'99'\n"
        "S21.G00.40.009,'C-2020-017'\n"
        "S21.G00.40.011,'10'\n"
        "S21.G00.40.012,'151.67'\n"
        "S21.G00.40.013,'151.67'\n"
        "S21.G00.40.014,'10'\n"
        "S21.G00.40.017,'3248'\n"
        "S21.G00.40.018,'Niveau III - Coef 240'\n"
        "S21.G00.40.006,'Technicienne'\n"
        "S21.G00.50.001,'31012026'\n"
        "S21.G00.50.002,'1880.00'\n"
        "S21.G00.50.004,'1838.00'\n"
        "S21.G00.50.006,'2.30'\n"
        "S21.G00.50.007,'01'\n"
        "S21.G00.50.008,'ABC123'\n"
        "S21.G00.50.009,'43.24'\n"
        "S21.G00.50.013,'1880.00'\n"
        "S21.G00.51.001,'01012026'\n"
        "S21.G00.51.002,'31012026'\n"
        "S21.G00.51.011,'001'\n"
        "S21.G00.51.013,'1880.00'\n"
    )
    ind, etab = _individu_from(lines)
    payload = map_employee_payload(ind, etab, "95147478200020")

    assert payload["sexe"] == "F"
    assert payload["is_temps_partiel"] is False
    assert payload["duree_hebdomadaire"] == 35.0

    pas = payload["specificites_paie"]["prelevement_a_la_source"]
    assert pas["taux"] == 2.30
    assert pas["type_taux"] == "01"
    assert pas["identifiant_taux"] == "ABC123"
    assert pas["assiette_dsn"] == 1880.0
    assert pas["montant_dsn"] == 43.24

    classif = payload["classification_conventionnelle"]
    assert classif["dispositif_politique_publique"] == "99"
    assert classif["numero_contrat_dsn"] == "C-2020-017"
    assert classif["position"] == "Niveau III - Coef 240"
    assert classif["statut_categoriel"] == "Cadre"


def test_payload_sans_pas_reste_vide():
    lines = (
        "S21.G00.30.001,'180032710123448'\n"
        "S21.G00.30.002,'DURAND'\n"
        "S21.G00.30.004,'Marc'\n"
        "S21.G00.30.005,'01'\n"
        "S21.G00.40.001,'01012020'\n"
        "S21.G00.40.007,'01'\n"
        "S21.G00.51.011,'001'\n"
        "S21.G00.51.013,'2000.00'\n"
    )
    ind, etab = _individu_from(lines)
    payload = map_employee_payload(ind, etab, "95147478200020")
    assert payload["sexe"] == "M"
    assert payload["specificites_paie"]["prelevement_a_la_source"] == {}


def test_pas_taux_zero_personnalise_est_enregistre():
    """Un taux personnalisé de 0,00 % (type 01) doit être enregistré explicitement.

    0,00 % (taux personnalisé nul) n'est pas l'absence de taux : sans cet
    enregistrement, un import mensuel ne peut pas ramener à 0 un taux devenu nul
    (le merge conserverait l'ancien taux). Régression corrigée sur le PAS.
    """
    lines = (
        "S21.G00.30.001,'180032710123448'\n"
        "S21.G00.30.002,'MARTIN'\n"
        "S21.G00.30.004,'Jean'\n"
        "S21.G00.30.005,'01'\n"
        "S21.G00.40.001,'01012020'\n"
        "S21.G00.40.007,'01'\n"
        "S21.G00.50.001,'31052026'\n"
        "S21.G00.50.002,'2000.00'\n"
        "S21.G00.50.004,'1950.00'\n"
        "S21.G00.50.006,'0.00'\n"
        "S21.G00.50.007,'01'\n"
        "S21.G00.50.008,'ZERO01'\n"
        "S21.G00.50.009,'0.00'\n"
        "S21.G00.50.013,'2000.00'\n"
    )
    ind, etab = _individu_from(lines)
    payload = map_employee_payload(ind, etab, "95147478200020")
    pas = payload["specificites_paie"]["prelevement_a_la_source"]
    assert pas["taux"] == 0.0
    assert pas["type_taux"] == "01"
    assert pas["identifiant_taux"] == "ZERO01"


def test_payload_plasturgie_mappe_niveau_dsn_en_coefficient():
    lines = (
        "S21.G00.30.001,'180032710123448'\n"
        "S21.G00.30.002,'ARAB'\n"
        "S21.G00.30.004,'Sadiqullah'\n"
        "S21.G00.40.001,'20012025'\n"
        "S21.G00.40.002,'01'\n"
        "S21.G00.40.017,'0292'\n"
        "S21.G00.40.041,'700'\n"
        "S21.G00.40.013,'162.50'\n"
        "S21.G00.40.014,'162.50'\n"
        "S21.G00.51.001,'01012026'\n"
        "S21.G00.51.002,'31012026'\n"
        "S21.G00.51.011,'001'\n"
        "S21.G00.51.013,'1868.57'\n"
    )
    ind, etab = _individu_from(lines)

    payload = map_employee_payload(ind, etab, "95147478200020")

    assert payload["classification_conventionnelle"]["coefficient"] == 700
