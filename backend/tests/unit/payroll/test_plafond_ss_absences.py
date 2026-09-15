"""Plafond de la Sécurité sociale et absences non rémunérées.

Le plafond mensuel est réduit prorata temporis en jours calendaires quand le
contrat est suspendu sans rémunération (BOSS, assiette générale). Le cabinet
l'applique bien : Colorplast janvier 2026, Cotte 3 875,81 € (30/31, son absence
du 21) et Gautheron 3 746,61 € (29/31, ses absences des 13 et 14) ; juin,
Gautheron 3 871,50 € (29/30).

Deux défauts se compensaient chez nous :

* l'ensemble des types qui déclenchent la réduction se comparait par égalité
  stricte, alors que l'analyseur produit `absence_injustifiee_base` et
  `absence_injustifiee_hs25`. Aucune absence issue d'un pointage ne réduisait
  donc le plafond ;
* le ratio se calculait sur tout le calendrier étendu, y compris les jours de
  la semaine rattachée au mois suivant. Gautheron tombait sur 29/31 en janvier,
  mais à cause de deux jours du 29 et 30 janvier — qui appartiennent aux
  variables de février — et non de ses vraies absences.

Enfin, le plafond imprimé sur le bulletin restait le plafond plein, sans jamais
suivre la proratisation appliquée au calcul.

Chiffres repris des bulletins de janvier 2026 (env. de test).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_cotisations import ratio_plafond_periode

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

JANVIER = (date(2026, 1, 1), date(2026, 1, 31))
PSS = 4005.00
#: Semaine du 26 au 30 janvier : elle relève des variables de février.
FENETRE_JANVIER = (date(2025, 12, 22), date(2026, 1, 25))


def _calendrier(absences: dict[str, float], type_absence="absence_injustifiee_base"):
    out = []
    jour = date(2026, 1, 1)
    while jour.month == 1:
        if jour.weekday() < 5:
            iso = jour.isoformat()
            if iso in absences:
                out.append({"date_complete": iso, "type": type_absence,
                            "heures": absences[iso]})
            else:
                out.append({"date_complete": iso, "type": "travail_base", "heures": 8.5})
        jour = date.fromordinal(jour.toordinal() + 1)
    return out


def _pss(calendrier, contexte=None):
    ctx = contexte or build_test_contexte(salaire_base=1964.0, duree_hebdo=39.0)
    return round(PSS * ratio_plafond_periode(calendrier, *JANVIER, ctx), 2)


class TestTypesDAbsence:
    def test_cotte_une_journee_entamee_retire_un_jour(self):
        assert _pss(_calendrier({"2026-01-21": 3.5})) == pytest.approx(3875.81, abs=0.01)

    def test_gautheron_deux_journees(self):
        cal = _calendrier({"2026-01-13": 2.5, "2026-01-14": 8.5})
        assert _pss(cal) == pytest.approx(3746.61, abs=0.01)

    def test_la_part_heures_sup_de_l_absence_compte_aussi(self):
        cal = _calendrier({"2026-01-21": 3.5}, type_absence="absence_injustifiee_hs25")
        assert _pss(cal) == pytest.approx(3875.81, abs=0.01)

    def test_absence_non_remuneree_inchangee(self):
        """Garde anti-régression : ce type marchait déjà."""
        cal = _calendrier({"2026-01-21": 8.5}, type_absence="absence_non_remuneree")
        assert _pss(cal) == pytest.approx(3875.81, abs=0.01)

    def test_sans_absence_le_plafond_est_plein(self):
        assert _pss(_calendrier({})) == pytest.approx(PSS, abs=0.01)

    def test_un_conge_paye_ne_reduit_pas_le_plafond(self):
        cal = _calendrier({"2026-01-21": 8.5}, type_absence="conges_payes")
        assert _pss(cal) == pytest.approx(PSS, abs=0.01)


class TestFenetreDesVariables:
    """Les absences de la semaine rattachée au mois suivant n'entrent pas."""

    def test_une_absence_du_30_janvier_ne_reduit_pas_janvier(self):
        from app.modules.payroll.engine.calcul_brut import evenements_de_la_periode

        cal = _calendrier({"2026-01-29": 8.5, "2026-01-30": 8.5})
        retenus = evenements_de_la_periode(cal, JANVIER, FENETRE_JANVIER)
        assert _pss(retenus) == pytest.approx(PSS, abs=0.01)

    def test_les_absences_dans_la_fenetre_comptent(self):
        from app.modules.payroll.engine.calcul_brut import evenements_de_la_periode

        cal = _calendrier({"2026-01-13": 2.5, "2026-01-14": 8.5})
        retenus = evenements_de_la_periode(cal, JANVIER, FENETRE_JANVIER)
        assert _pss(retenus) == pytest.approx(3746.61, abs=0.01)
