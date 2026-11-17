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
        "à la DSN. Enregistrez l'arrêt dans Congés & "
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
    demande = {
        "type": "arret_maternite", "arret_type": "maternite",
        "status": "validated", "selected_days": ["2026-09-15"],
    }
    assert alerte_arret_sans_demande([_jour(15)], [demande], *SEPT) is None


def test_un_week_end_sans_heures_n_est_pas_retenu_et_ne_dit_rien():
    # 19 et 20/09/2026 : samedi et dimanche, que le moteur ne retient pas.
    assert alerte_arret_sans_demande([_jour(19), _jour(20)], [], *SEPT) is None


def test_hors_du_mois_du_bulletin_rien():
    assert alerte_arret_sans_demande([_jour(31, mois=8)], [], *SEPT) is None


def test_un_arret_valide_sans_type_d_arret_est_dit_aussi():
    """17/11 : une demande validée sans type d'arrêt couvre le jour, qui n'en
    reçoit pas non plus ; le maintien l'écarte. Ce n'était dit nulle part."""
    demande = {"type": "arret_paternite", "status": "validated", "selected_days": ["2026-09-15"]}
    alerte = alerte_arret_sans_demande([_jour(15)], [demande], *SEPT)
    assert alerte["code"] == "arret_sans_type"
    assert [j["jour"] for j in alerte["jours"]] == [15]
    assert alerte["message"] == (
        "Arrêt enregistré sans type d'arrêt le 15 septembre : cette journée est retenue "
        "sans maintien de salaire ni IJSS. Indiquez le type de l'arrêt dans Congés & "
        "absences, puis recalculez ce bulletin."
    )


def test_un_arret_valide_avec_son_type_ne_dit_rien():
    demande = {
        "type": "arret_maladie", "arret_type": "maladie_simple",
        "status": "validated", "selected_days": ["2026-09-15"],
    }
    assert alerte_arret_sans_demande([_jour(15)], [demande], *SEPT) is None


class _BaseQuiProjette:
    """Rend seulement les colonnes demandées par `select`, comme PostgREST."""

    def __init__(self, lignes):
        self._lignes = lignes
        self._colonnes: list[str] = []

    def table(self, _nom):
        return self

    def select(self, colonnes, *_a, **_k):
        self._colonnes = [c.strip() for c in colonnes.split(",")]
        return self

    def eq(self, *_a):
        return self

    def execute(self):
        from types import SimpleNamespace

        return SimpleNamespace(
            data=[{c: ligne.get(c) for c in self._colonnes} for ligne in self._lignes]
        )


def test_la_demande_lue_en_base_porte_son_type_d_arret(monkeypatch):
    """Relecture du 17/11 : la lecture des demandes ne prenait pas `arret_type`,
    donc toute demande validée passait pour « sans type ». Un jour du calendrier
    sans type, couvert par une demande qui en a un, ne dit rien."""
    from app.modules.payroll.documents import payslip_generator

    demande = {
        "type": "arret_maladie",
        "arret_type": "maladie",
        "status": "validated",
        "selected_days": ["2026-09-15"],
        "subrogation_active": False,
    }
    monkeypatch.setattr(payslip_generator, "supabase", _BaseQuiProjette([demande]))
    calendrier = [_jour(15)]
    demandes = payslip_generator._stamp_source_absence_conges(calendrier, "e1")
    assert alerte_arret_sans_demande(calendrier, demandes, *SEPT) is None
