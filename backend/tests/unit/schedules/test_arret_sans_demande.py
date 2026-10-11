"""« Arrêt maladie » posé au calendrier sans demande d'arrêt : le bulletin le dit.

Un jour typé « Arrêt maladie » directement au calendrier n'a pas de type
d'arrêt (clé posée par la seule validation d'une demande) : le moteur le
retient comme un arrêt, mais sans maintien de salaire, sans carence payée ni
IJSS, et l'arrêt manque à l'attestation et à la DSN — en silence. Le bulletin
porte désormais une alerte qui dit ce qui manque et où le saisir. Aucune
demande n'est créée à la place de la gestionnaire.
"""

from datetime import date

from app.modules.schedules.domain.conflits_arret import alerte_arret_sans_demande

SEPT = (date(2026, 9, 1), date(2026, 9, 30))


def _jour(jour: int, type_jour: str = "arret_maladie", mois: int = 9, **extra) -> dict:
    return {"annee": 2026, "mois": mois, "jour": jour, "type": type_jour, "heures_prevues": 0, **extra}


def test_un_arret_pose_au_calendrier_sans_demande_alerte():
    calendrier = [_jour(14, "travail", heures_prevues=7.8), _jour(15), _jour(16)]
    alerte = alerte_arret_sans_demande(calendrier, [], *SEPT)
    assert alerte["code"] == "arret_sans_demande"
    assert alerte["critique"] is False
    assert [j["jour"] for j in alerte["jours"]] == [15, 16]
    assert alerte["message"] == (
        "Arrêt maladie posé au calendrier sans demande d'arrêt les 15 et 16 septembre : "
        "ces journées sont retenues sans maintien de salaire ni IJSS, et l'arrêt manque "
        "à l'attestation de salaire et à la DSN. Enregistrez l'arrêt dans Congés & "
        "absences (« + Enregistrer un arrêt », avec son type d'arrêt), puis recalculez "
        "ce bulletin."
    )


def test_une_seule_journee():
    alerte = alerte_arret_sans_demande([_jour(15)], [], *SEPT)
    assert alerte["message"].startswith(
        "Arrêt maladie posé au calendrier sans demande d'arrêt le 15 septembre : "
        "cette journée est retenue sans maintien de salaire ni IJSS"
    )


def test_un_arret_issu_d_une_demande_ne_dit_rien():
    # La validation d'une demande pose le type d'arrêt sur chaque jour.
    calendrier = [_jour(15, arret_type="maladie_simple"), _jour(16, arret_type="maladie_simple")]
    assert alerte_arret_sans_demande(calendrier, [], *SEPT) is None


def test_un_jour_couvert_par_une_demande_validee_ne_dit_rien():
    demande = {"type": "arret_maternite", "status": "validated", "selected_days": ["2026-09-15"]}
    assert alerte_arret_sans_demande([_jour(15)], [demande], *SEPT) is None


def test_un_week_end_sans_heures_n_est_pas_retenu_et_ne_dit_rien():
    # 19 et 20/09/2026 : samedi et dimanche, que le moteur ne retient pas.
    assert alerte_arret_sans_demande([_jour(19), _jour(20)], [], *SEPT) is None


def test_hors_du_mois_du_bulletin_rien():
    assert alerte_arret_sans_demande([_jour(31, mois=8)], [], *SEPT) is None
