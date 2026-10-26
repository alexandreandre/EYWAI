"""Import DSN : chaque bloc d'absence est lu selon la norme.

Source : cahier technique DSN 2026.1 (NEODeS, CT2026.1.2 du 24/12/2025),
https://www.net-entreprises.fr/media/documentation/dsn-cahier-technique-2026.1.pdf
- S21.G00.41 « Changements Contrat » (p. 215) : les valeurs d'avant une
  modification du contrat. Jamais un arrêt ;
- S21.G00.60 « Arrêt de travail » (p. 265-269) : .001 motif (01 maladie,
  02 maternité, 03 paternité / accueil de l'enfant, 04 accident de trajet,
  05 maladie professionnelle, 06 accident du travail, 09 adoption, 15 à 18
  temps partiel thérapeutique…), .002 date du dernier jour travaillé, .003 date
  de fin prévisionnelle, .010 date de la reprise (« premier jour travaillé et
  payé suite à l'arrêt ») ;
- S21.G00.65 « Autre suspension de l'exécution du contrat » (p. 280-283) :
  .001 motif (501 congé divers non rémunéré, 632 congé parental d'éducation,
  637 congé pour évènement familial, 602 chômage sans rupture…), .002 premier
  jour, .003 fin de la suspension.

L'import lisait le 41 comme un arrêt, le 60 comme une suspension (tout arrêt
devenait « sans solde », un jour trop tôt) et le 65 comme une ancienneté.
Extraits fabriqués : aucune donnée réelle.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.modules.dsn_import.application.mapping import build_preview_items, map_employee_payload
from app.modules.dsn_import.domain.parser import parse_dsn_content, parse_dsn_files

pytestmark = pytest.mark.unit

NIR = "1800175000001"


def _dsn(mois: str, blocs: str, *, avant_versement: str = "") -> bytes:
    """Une DSN mensuelle d'un salarié ; `mois` au format MMAAAA."""
    entete = f"""S10.G00.00.001,'LOGICIEL'
S10.G00.00.006,'P26V01'
S20.G00.05.001,'01'
S20.G00.05.005,'01{mois}'
S21.G00.06.001,'123456789'
S21.G00.11.001,'00011'
S21.G00.30.001,'{NIR}'
S21.G00.30.002,'TEST'
S21.G00.30.004,'Salarie'
S21.G00.40.001,'01012020'
S21.G00.40.002,'07'
S21.G00.40.007,'01'
S21.G00.40.017,'0292'
"""
    versement = f"""S21.G00.50.001,'28{mois}'
S21.G00.50.002,'1800.00'
S21.G00.51.001,'01{mois}'
S21.G00.51.002,'28{mois}'
S21.G00.51.011,'001'
S21.G00.51.013,'2000.00'
"""
    return (entete + avant_versement + versement + blocs).encode("latin-1")


def _arret(motif: str, dernier_jour: str, fin: str, reprise: str = "") -> str:
    bloc = (
        f"S21.G00.60.001,'{motif}'\n"
        f"S21.G00.60.002,'{dernier_jour}'\n"
        f"S21.G00.60.003,'{fin}'\n"
        "S21.G00.60.004,'02'\n"
    )
    if reprise:
        bloc += f"S21.G00.60.010,'{reprise}'\nS21.G00.60.011,'01'\n"
    return bloc


def _suspension(motif: str, debut: str, fin: str) -> str:
    return (
        f"S21.G00.65.001,'{motif}'\n"
        f"S21.G00.65.002,'{debut}'\n"
        f"S21.G00.65.003,'{fin}'\n"
    )


def _absences(*fichiers: tuple[str, bytes]) -> list[dict]:
    items, _ = build_preview_items(parse_dsn_files(list(fichiers)))
    return [it["mapped_payload"] for it in items if it["item_type"] == "absence"]


def _une_absence(*fichiers: tuple[str, bytes]) -> dict:
    (absence,) = _absences(*fichiers)
    return absence


def _jours(debut: str, fin: str) -> list[str]:
    d, f = date.fromisoformat(debut), date.fromisoformat(fin)
    return [(d + timedelta(days=n)).isoformat() for n in range((f - d).days + 1)]


# --- Bloc 60 : arrêt de travail ---------------------------------------------


def test_un_arret_maladie_repris_commence_le_lendemain_du_dernier_jour_travaille():
    """Dernier jour travaillé le 15, reprise le 29 : arrêt du 16 au 28."""
    absence = _une_absence(
        ("2026-03.dsn", _dsn("032026", _arret("01", "15032026", "28032026", "29032026")))
    )
    assert absence["absence_type"] == "arret_maladie"
    assert absence["arret_type"] == "maladie_simple"
    assert (absence["date_debut"], absence["date_fin"]) == ("2026-03-16", "2026-03-28")
    assert absence["selected_days"] == _jours("2026-03-16", "2026-03-28")
    assert absence["dsn_block"] == "G00.60"
    assert absence["motif_dsn"] == "01"


def test_sans_reprise_l_arret_va_jusqu_a_la_fin_previsionnelle():
    absence = _une_absence(("2026-05.dsn", _dsn("052026", _arret("01", "03052026", "31052026"))))
    assert (absence["date_debut"], absence["date_fin"]) == ("2026-05-04", "2026-05-31")


def test_la_reprise_avant_la_fin_previsionnelle_raccourcit_l_arret():
    absence = _une_absence(
        ("2026-05.dsn", _dsn("052026", _arret("01", "03052026", "31052026", "20052026")))
    )
    assert absence["date_fin"] == "2026-05-19"


@pytest.mark.parametrize(
    ("motif", "nature", "type_arret", "premier_jour"),
    [
        ("01", "arret_maladie", "maladie_simple", "2026-05-06"),
        ("02", "arret_maternite", "maternite", "2026-05-06"),
        ("03", "arret_paternite", "paternite", "2026-05-06"),
        # Accident : prescrit le jour de l'accident, qui est le dernier jour travaillé.
        ("04", "arret_at", "accident_trajet", "2026-05-05"),
        ("05", "arret_maladie_pro", "maladie_professionnelle", "2026-05-05"),
        ("06", "arret_at", "accident_travail", "2026-05-05"),
        ("09", "arret_maternite", "adoption", "2026-05-06"),
    ],
)
def test_le_motif_de_l_arret_donne_la_nature_et_le_type_d_arret(motif, nature, type_arret, premier_jour):
    absence = _une_absence(
        ("2026-05.dsn", _dsn("052026", _arret(motif, "05052026", "14052026", "15052026")))
    )
    assert (absence["absence_type"], absence["arret_type"]) == (nature, type_arret)
    assert (absence["date_debut"], absence["date_fin"]) == (premier_jour, "2026-05-14")


def test_un_accident_du_travail_commence_le_jour_de_l_accident():
    """60.002 : « arrêt prescrit lors d'un jour travaillé : le dernier jour
    travaillé correspond alors à la date de l'arrêt ». C'est ce que l'export de
    Martine écrit pour un accident, et ce qu'imprime l'ancien logiciel
    (dernier jour travaillé le 23, « Absence A.T. du 23 au 29 »)."""
    absence = _une_absence(
        ("2026-05.dsn", _dsn("052026", _arret("06", "23052026", "29052026", "30052026")))
    )
    assert (absence["date_debut"], absence["date_fin"]) == ("2026-05-23", "2026-05-29")


def test_un_arret_n_est_jamais_un_sans_solde():
    absences = _absences(
        ("2026-05.dsn", _dsn("052026", _arret("01", "03052026", "31052026") + _arret("06", "05052026", "14052026")))
    )
    assert absences and all(a["absence_type"] != "sans_solde" for a in absences)


def test_une_prolongation_declaree_le_mois_suivant_ne_fait_qu_un_arret():
    """Avril déclare l'arrêt jusqu'au 30/04 ; mai le prolonge jusqu'au 30/05."""
    absence = _une_absence(
        ("2026-04.dsn", _dsn("042026", _arret("01", "26042026", "30042026"))),
        ("2026-05.dsn", _dsn("052026", _arret("01", "26042026", "30052026", "31052026"))),
    )
    assert (absence["date_debut"], absence["date_fin"]) == ("2026-04-27", "2026-05-30")


def test_l_arret_initial_et_sa_prolongation_dans_la_meme_dsn_ne_font_qu_un_arret():
    absence = _une_absence(
        (
            "2026-05.dsn",
            _dsn(
                "052026",
                _arret("01", "26042026", "30042026", "01052026")
                + _arret("01", "26042026", "30052026", "31052026"),
            ),
        )
    )
    assert (absence["date_debut"], absence["date_fin"]) == ("2026-04-27", "2026-05-30")


def test_la_reprise_declaree_le_mois_suivant_l_emporte_sur_la_fin_previsionnelle():
    """Mars prévoit l'arrêt jusqu'au 15/04 ; avril déclare la reprise le 10/04."""
    absence = _une_absence(
        ("2026-04.dsn", _dsn("042026", _arret("01", "20032026", "15042026", "10042026"))),
        ("2026-03.dsn", _dsn("032026", _arret("01", "20032026", "15042026"))),
    )
    assert (absence["date_debut"], absence["date_fin"]) == ("2026-03-21", "2026-04-09")


def test_une_reprise_le_lendemain_du_dernier_jour_travaille_ne_cree_pas_d_absence():
    assert _absences(("2026-05.dsn", _dsn("052026", _arret("01", "05052026", "05052026", "06052026")))) == []


@pytest.mark.parametrize("motif", ["07", "15", "16", "19", "20", "99"])
def test_un_motif_d_arret_sans_equivalent_n_est_pas_repris_en_silence(motif):
    """Temps partiel thérapeutique, deuil d'enfant, annulation… : à saisir à la main."""
    parsed = parse_dsn_files(
        [("2026-05.dsn", _dsn("052026", _arret(motif, "05052026", "14052026")))]
    )
    items, summary = build_preview_items(parsed)
    assert not [it for it in items if it["item_type"] == "absence"]
    (non_repris,) = summary["absences_non_reprises"]
    assert (non_repris["bloc"], non_repris["motif"], non_repris["nombre"]) == ("S21.G00.60", motif, 1)
    assert non_repris["libelle"]


# --- Bloc 65 : autre suspension du contrat ----------------------------------


def test_un_conge_non_remunere_501_est_un_sans_solde_aux_dates_du_bloc():
    absence = _une_absence(("2026-05.dsn", _dsn("052026", _suspension("501", "05052026", "06052026"))))
    assert absence["absence_type"] == "sans_solde"
    assert absence["arret_type"] is None
    assert (absence["date_debut"], absence["date_fin"]) == ("2026-05-05", "2026-05-06")
    assert absence["dsn_block"] == "G00.65"


def test_un_conge_parental_d_education_632_est_un_sans_solde():
    """La norme code le congé parental d'éducation 632 (il n'existe pas de 504)."""
    absence = _une_absence(("2026-05.dsn", _dsn("052026", _suspension("632", "01052026", "31052026"))))
    assert absence["absence_type"] == "sans_solde"
    assert (absence["date_debut"], absence["date_fin"]) == ("2026-05-01", "2026-05-31")


def test_le_code_504_absent_de_la_norme_n_est_pas_range_en_sans_solde():
    _, summary = build_preview_items(
        parse_dsn_files([("2026-05.dsn", _dsn("052026", _suspension("504", "01052026", "31052026")))])
    )
    assert [n["motif"] for n in summary["absences_non_reprises"]] == ["504"]


def test_un_conge_pour_evenement_familial_637_est_un_evenement_familial():
    absence = _une_absence(("2026-05.dsn", _dsn("052026", _suspension("637", "04052026", "04052026"))))
    assert absence["absence_type"] == "evenement_familial"
    assert absence["selected_days"] == ["2026-05-04"]


def test_le_chomage_sans_rupture_602_n_est_pas_une_absence_mais_est_signale():
    _, summary = build_preview_items(
        parse_dsn_files(
            [
                (
                    "2026-05.dsn",
                    _dsn(
                        "052026",
                        _suspension("602", "04052026", "04052026") + _suspension("602", "11052026", "12052026"),
                    ),
                )
            ]
        )
    )
    (non_repris,) = summary["absences_non_reprises"]
    assert (non_repris["bloc"], non_repris["motif"], non_repris["nombre"]) == ("S21.G00.65", "602", 2)


def test_une_suspension_supra_mensuelle_declaree_deux_mois_ne_fait_qu_une_absence():
    absence = _une_absence(
        ("2026-04.dsn", _dsn("042026", _suspension("632", "15042026", "30062026"))),
        ("2026-05.dsn", _dsn("052026", _suspension("632", "15042026", "30062026"))),
    )
    assert (absence["date_debut"], absence["date_fin"]) == ("2026-04-15", "2026-06-30")


def test_une_suspension_n_est_plus_lue_comme_une_anciennete():
    contenu = _dsn("052026", _suspension("501", "05052026", "06052026"))
    dsn = parse_dsn_content(contenu, file_name="2026-05.dsn")
    etab = dsn.etablissement
    (individu,) = etab.individus
    payload = map_employee_payload(individu, etab, "12345678900011")
    assert payload["specificites_paie"].get("dsn_anciennete") is None


# --- Bloc 41 : changements contrat ------------------------------------------


def test_un_changement_de_contrat_ne_cree_aucune_absence():
    changement = (
        "S21.G00.41.001,'14042026'\n"
        "S21.G00.41.004,'02'\n"
        "S21.G00.41.012,'12345678900029'\n"
    )
    contenu = _dsn("042026", "", avant_versement=changement)
    items, summary = build_preview_items(parse_dsn_files([("2026-04.dsn", contenu)]))
    assert not [it for it in items if it["item_type"] == "absence"]
    assert summary["absences_non_reprises"] == []

    (contrat,) = parse_dsn_content(contenu, file_name="2026-04.dsn").etablissement.individus[0].contrats
    (lu,) = contrat.changements
    assert lu.date_modification == "14042026"
    assert lu.rubriques["S21.G00.41.004"] == "02"
    assert contrat.arrets == []


def test_l_apercu_dit_ce_qui_n_est_pas_importe():
    from app.modules.dsn_import.domain.user_messages import absence_non_reprise_anomaly

    anomalie = absence_non_reprise_anomaly(
        {"bloc": "S21.G00.65", "motif": "602", "libelle": "chômage sans rupture de contrat", "nombre": 2}
    )
    assert anomalie["severity"] == "warning"
    assert anomalie["message"].startswith(
        "2 suspensions « chômage sans rupture de contrat » (motif 602, bloc S21.G00.65) non importées"
    )


# --- Motifs traduits le 25/10/2026 (reprise Mont Blanc) ----------------------


def test_un_conge_pour_enfant_malade_636_est_un_sans_solde():
    """Code du travail L1225-61 : congé non rémunéré, sauf convention plus favorable.
    Mont Blanc (Quadra, janvier 2026) retient bien la journée (« Abs. Enfant malade »)."""
    absence = _une_absence(("2026-01.dsn", _dsn("012026", _suspension("636", "21012026", "21012026"))))
    assert absence["absence_type"] == "sans_solde"
    assert absence["selected_days"] == ["2026-01-21"]


@pytest.mark.parametrize("motif", ["15", "16", "17", "18"])
def test_le_temps_partiel_therapeutique_dit_ou_le_saisir(motif):
    """La DSN donne la période du temps partiel thérapeutique, pas les heures non
    travaillées : pas d'absence créée (elle retiendrait des jours pleins), mais l'aperçu
    dit de le saisir jour par jour, en arrêt de type « Mi-temps thérapeutique »."""
    from app.modules.dsn_import.domain.user_messages import absence_non_reprise_anomaly

    parsed = parse_dsn_files([("2026-06.dsn", _dsn("062026", _arret(motif, "14062026", "30062026")))])
    items, summary = build_preview_items(parsed)
    assert not [it for it in items if it["item_type"] == "absence"]
    (non_repris,) = summary["absences_non_reprises"]
    anomalie = absence_non_reprise_anomaly(non_repris)
    assert "Mi-temps thérapeutique" in anomalie["hint"] and "jour par jour" in anomalie["hint"]
    assert "pas de type d'absence" not in anomalie["message"]


def test_le_chomage_sans_rupture_602_dit_de_le_saisir_dans_les_variables():
    """Activité partielle (L5122-1) : des heures chômées et une indemnité, pas une absence."""
    from app.modules.dsn_import.domain.user_messages import absence_non_reprise_anomaly

    _, summary = build_preview_items(
        parse_dsn_files([("2026-05.dsn", _dsn("052026", _suspension("602", "04052026", "04052026")))])
    )
    (non_repris,) = summary["absences_non_reprises"]
    anomalie = absence_non_reprise_anomaly(non_repris)
    assert "activité partielle" in anomalie["hint"].lower() and "variables du mois" in anomalie["hint"]
    assert "pas de type d'absence" not in anomalie["message"]
