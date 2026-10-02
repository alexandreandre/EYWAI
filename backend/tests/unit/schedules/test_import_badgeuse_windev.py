"""Import d'un export de badgeuse WinDev « Pointages "retenu" » (noms inventés).

Défauts constatés le 02/10/2026 sur des pointages de septembre : une fiche badge
sans prénom était jetée par le lecteur, et le salarié n'avait aucune heure.
"""

from app.modules.schedules.application.parsers.cegid_weekly import (
    try_parse_cegid_weekly,
)
from tests.fixtures.timesheets.windev_samples import WINDEV_BADGE_WEEK


def _lecture(texte: str = WINDEV_BADGE_WEEK):
    return try_parse_cegid_weekly(texte, target_year=2026, target_month=9)


class TestFicheBadgeAuNomSeul:
    def test_toutes_les_fiches_du_releve_sont_lues(self):
        assert [e.matricule for e in _lecture().employees] == ["101", "178", "172", "176"]

    def test_la_fiche_au_nom_seul_porte_ses_heures(self):
        fiche = next(e for e in _lecture().employees if e.matricule == "178")
        assert fiche.raw_name == "DUPRAT"
        assert [d.jour for d in fiche.days] == [14, 15, 16, 17, 18]
        assert [d.heures for d in fiche.days] == [9.08, 9.12, 8.43, 8.35, 6.28]
        assert fiche.empty_week is False

    def test_la_fiche_vide_reste_une_semaine_vide(self):
        vide = next(e for e in _lecture().employees if e.matricule == "172")
        assert vide.raw_name == "DUPRAT Claire"
        assert vide.empty_week is True
        assert vide.days == []

    def test_un_jour_de_la_semaine_seul_n_est_pas_un_nom(self):
        texte = WINDEV_BADGE_WEEK.replace("178 DUPRAT\n", "178 Lundi\n", 1)
        assert not any(e.raw_name.lower() == "lundi" for e in _lecture(texte).employees)
