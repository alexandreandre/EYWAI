"""La ligne de retenue d'un arrêt dit sa nature [F16].

Tous les arrêts arrivent au calendrier en `arret_maladie` (la validation d'une
demande d'arrêt ne pose que ce type de jour, avec son `arret_type`) : le
dictionnaire des libellés du moteur (« accident du travail », « congé
maternité »…) n'était jamais atteint, et le bulletin d'un accident du travail
imprimait « Absence arrêt maladie du … ».

La nature vient, dans l'ordre : du type de jour quand il la porte déjà
(`arret_at`, repris de Quadra) ; de la demande validée d'origine
(`source_absence`, posé par le générateur depuis `absence_requests`), seule à
distinguer la maternité et la paternité, qui n'ont pas de type d'arrêt
propre ; à défaut, du type d'arrêt (accident du travail, de trajet, rechute,
maladie professionnelle). Le montant de la retenue ne change pas.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.payroll.documents import payslip_generator
from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

JOURS_OUVRES = (26, 27, 28, 29)


def _pertes(calendrier):
    contexte = build_test_contexte(
        salaire_base=1850.37, duree_hebdo=39.0, date_entree="2026-03-23",
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )
    resultat = calculer_salaire_brut(
        contexte, calendrier, date(2026, 5, 1), date(2026, 5, 31), [],
        date_debut_variables=date(2026, 4, 20), date_fin_variables=date(2026, 5, 24),
    )
    return [(l["libelle"], l["quantite"], l["perte"])
            for l in resultat["lignes_composants_brut"]
            if l.get("perte") and l["libelle"].startswith("Absence")]


def _jours(jours=JOURS_OUVRES, **meta):
    return [
        {"date_complete": f"2026-05-{j:02d}", "type": "arret_maladie", "heures": 8.5, **meta}
        for j in jours
    ]


@pytest.mark.parametrize("meta, libelle", [
    ({"arret_type": "accident_travail"}, "Absence accident du travail du 26/05 au 29/05"),
    ({"arret_type": "accident_trajet"}, "Absence accident du travail du 26/05 au 29/05"),
    ({"arret_type": "rechute_at"}, "Absence accident du travail du 26/05 au 29/05"),
    ({"arret_type": "maladie_professionnelle"}, "Absence maladie professionnelle du 26/05 au 29/05"),
    ({"arret_type": "rechute_at", "source_absence": "arret_maladie_pro"},
     "Absence maladie professionnelle du 26/05 au 29/05"),
    ({"arret_type": "maladie_simple", "source_absence": "arret_maternite"},
     "Absence congé maternité du 26/05 au 29/05"),
    ({"source_absence": "arret_paternite"}, "Absence congé paternité du 26/05 au 29/05"),
    ({"arret_type": "accident_travail", "source_absence": "arret_at"},
     "Absence accident du travail du 26/05 au 29/05"),
])
def test_le_libelle_suit_la_nature_de_l_arret(meta, libelle):
    # Montant inchangé : 4 jours × 7 h = 28,00 h à 12,20 (341,60 €).
    assert _pertes(_jours(**meta)) == [(libelle, 28.0, 341.60)]


@pytest.mark.parametrize("meta", [
    {"arret_type": "maladie_simple"},
    {"arret_type": "maladie_simple", "source_absence": "arret_maladie"},
    {},
])
def test_la_maladie_garde_son_libelle(meta):
    assert _pertes(_jours(**meta)) == [("Absence arrêt maladie du 26/05 au 29/05", 28.0, 341.60)]


def test_deux_natures_qui_se_suivent_font_deux_lignes():
    calendrier = _jours((26, 27), arret_type="maladie_simple") + _jours(
        (28, 29), arret_type="accident_travail"
    )
    assert _pertes(calendrier) == [
        ("Absence arrêt maladie du 26/05 au 27/05", 14.0, 170.80),
        ("Absence accident du travail du 28/05 au 29/05", 14.0, 170.80),
    ]


class _Requete:
    def __init__(self, lignes):
        self._lignes = lignes

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a):
        return self

    def execute(self):
        return SimpleNamespace(data=self._lignes)


class _Client:
    def __init__(self, lignes):
        self._lignes = lignes

    def table(self, _nom):
        return _Requete(self._lignes)


def _jour(jour, type_jour, **meta):
    return {"annee": 2026, "mois": 5, "jour": jour, "type": type_jour,
            "heures_prevues": 0.0, **meta}


def test_le_generateur_pose_la_nature_de_la_demande_sur_les_jours_d_arret(monkeypatch):
    demandes = [
        {"type": "arret_paternite", "selected_days": ["2026-05-04", "2026-05-05"]},
        {"type": "arret_at", "selected_days": ["2026-05-11"]},
        {"type": "conge_paye", "selected_days": ["2026-05-18"]},
    ]
    monkeypatch.setattr(payslip_generator, "supabase", _Client(demandes))
    jours = [
        _jour(4, "arret_maladie"),
        _jour(5, "arret_maladie"),
        _jour(11, "arret_maladie", arret_type="accident_travail"),
        _jour(12, "arret_maladie", arret_type="maladie_simple"),
        _jour(18, "conges_payes"),
        _jour(19, "travail", heures_prevues=7.0),
    ]
    rows = payslip_generator._stamp_source_absence_conges(jours, "emp-1")

    assert rows == demandes
    assert [j.get("source_absence") for j in jours] == [
        "arret_paternite", "arret_paternite", "arret_at", None, "conge_paye", None,
    ]


def test_le_generateur_marque_les_feries_d_un_conge_sans_solde(monkeypatch):
    # Défaut du 24/10 : un sans solde du 1er au 31 mai couvre le 1er mai, que la
    # validation laisse « férié » sans borne. Les fériés d'une demande de congé
    # payé ne sont pas marqués : le congé ne retient pas la journée.
    demandes = [
        {"type": "sans_solde", "selected_days": ["2026-05-01", "2026-05-02", "2026-05-04"]},
        {"type": "conge_paye", "selected_days": ["2026-05-14"]},
    ]
    monkeypatch.setattr(payslip_generator, "supabase", _Client(demandes))
    jours = [
        _jour(1, "ferie"),
        _jour(4, "absence_non_remuneree"),
        _jour(8, "ferie"),
        _jour(14, "ferie"),
    ]
    payslip_generator._stamp_source_absence_conges(jours, "emp-1")
    assert [j.get("source_absence") for j in jours] == ["sans_solde", None, None, None]
