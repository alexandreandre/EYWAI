"""Étiquetage `source_absence` des congés — le maillon qui décide si un congé
posé depuis le module Absences atteint le bulletin.

Un congé validé par la RH projette le jour de planning à **0 h**. Un événement
à 0 h est supprimé par l'agrégation du moteur : sans marqueur, ni retenue, ni
indemnité, ni arbitrage 1/10e. `_stamp_source_absence_conges` pose ce marqueur
depuis la demande d'origine ; c'est lui qui fait exister le congé en paie.

Livré le 07/09/2026, ce maillon n'a jamais tourné une seule fois. Sa requête
filtrait sur `recuperation_modulation`, valeur absente de l'enum PostgreSQL
`absence_type` : PostgREST répondait 22P02 à CHAQUE génération et un
`except Exception: return` avalait l'échec. Mesuré le 08/09/2026 sur l'env de
test : 67 jours de congés d'août absents des bulletins Colorplast, sans le
moindre signal.

Les tests unitaires existants (`test_demi_journee_cp.py`) injectaient le
marqueur à la main : ils couvraient l'aval, jamais le maillon qui le pose.
D'où ce fichier, qui exerce la vraie requête contre un client qui se comporte
comme PostgREST sur une colonne enum.
"""

from types import SimpleNamespace

import pytest

from app.modules.payroll.documents import payslip_generator

pytestmark = pytest.mark.unit


#: Valeurs réellement présentes dans l'enum PostgreSQL `absence_type`, prod ET
#: test (relevées le 08/09/2026). `recuperation_modulation` n'y est PAS, alors
#: que le code l'emploie : c'est cette divergence qui a tué l'étiquetage.
#: La paie ne doit pas dépendre du vocabulaire de la base — d'où ces tests.
#: `tests/integration/test_absence_type_enum.py` surveille la divergence.
TYPES_ABSENCE_EN_BASE = frozenset(
    {
        "conge_paye",
        "rtt",
        "sans_solde",
        "repos_compensateur",
        "evenement_familial",
        "arret_maladie",
        "arret_at",
        "arret_paternite",
        "arret_maternite",
        "arret_maladie_pro",
        "jtc",
    }
)


class _ErreurEnumFactice(Exception):
    """Imite l'APIError 22P02 renvoyée par PostgREST sur une valeur d'enum inconnue."""

    def __init__(self, valeur: str) -> None:
        super().__init__(
            f'invalid input value for enum absence_type: "{valeur}" (22P02)'
        )


class _RequeteFactice:
    """Client PostgREST minimal : refuse toute valeur hors enum, à l'exécution."""

    def __init__(self, lignes, types_en_base):
        self._lignes = lignes
        self._types_en_base = types_en_base
        self._types_filtres: list[str] = []

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, _colonne, _valeur):
        return self

    def in_(self, colonne, valeurs):
        if colonne == "type":
            self._types_filtres = list(valeurs)
        return self

    def execute(self):
        for valeur in self._types_filtres:
            if valeur not in self._types_en_base:
                raise _ErreurEnumFactice(valeur)
        return SimpleNamespace(data=self._lignes)


class _ClientFactice:
    def __init__(self, lignes, types_en_base=TYPES_ABSENCE_EN_BASE):
        self._lignes = lignes
        self._types_en_base = types_en_base

    def table(self, _nom):
        return _RequeteFactice(self._lignes, self._types_en_base)


def _jour_cp(annee=2026, mois=7, jour=13):
    """Jour tel que la validation d'absence le projette : congé payé à 0 h."""
    return {
        "annee": annee,
        "mois": mois,
        "jour": jour,
        "type": "conges_payes",
        "heures_prevues": 0.0,
        "origine": "absence",
    }


class TestEtiquetageDepuisLaDemande:
    def test_un_conge_paye_valide_recoit_le_marqueur(self, monkeypatch):
        """Le maillon doit poser `source_absence` sur le jour projeté — sans
        quoi le congé disparaît du bulletin."""
        client = _ClientFactice(
            [{"type": "conge_paye", "selected_days": ["2026-07-13"]}]
        )
        monkeypatch.setattr(payslip_generator, "supabase", client)

        jours = [_jour_cp()]
        payslip_generator._stamp_source_absence_conges(jours, "emp-1")

        assert jours[0]["source_absence"] == "conge_paye"

    def test_une_recup_modulation_reste_distinguee_du_conge(self, monkeypatch):
        """Récup modulation et congé payé partagent le même type calendrier :
        seul le marqueur les sépare, et lui seul décide des lignes CP."""
        client = _ClientFactice(
            [{"type": "recuperation_modulation", "selected_days": ["2026-07-13"]}]
        )
        monkeypatch.setattr(payslip_generator, "supabase", client)

        jours = [_jour_cp()]
        payslip_generator._stamp_source_absence_conges(jours, "emp-1")

        assert jours[0]["source_absence"] == "recuperation_modulation"


class TestEchecDeLecture:
    def test_un_echec_de_lecture_interrompt_la_generation(self, monkeypatch):
        """Une paie muette est pire qu'une paie absente : si les demandes ne
        peuvent pas être lues, le bulletin serait produit sans ses congés. Il
        ne doit pas être produit du tout."""

        class _ClientEnPanne:
            def table(self, _nom):
                raise RuntimeError("base injoignable")

        monkeypatch.setattr(payslip_generator, "supabase", _ClientEnPanne())

        with pytest.raises(RuntimeError):
            payslip_generator._stamp_source_absence_conges([_jour_cp()], "emp-1")

    def test_aucun_jour_de_conge_ne_declenche_aucune_lecture(self, monkeypatch):
        """Cas passant : sans jour de congé, on ne lit rien (et on ne casse rien)."""

        class _ClientInterdit:
            def table(self, _nom):
                raise AssertionError("aucune lecture attendue")

        monkeypatch.setattr(payslip_generator, "supabase", _ClientInterdit())

        jours = [{"annee": 2026, "mois": 7, "jour": 14, "type": "travail",
                  "heures_prevues": 7.0}]
        payslip_generator._stamp_source_absence_conges(jours, "emp-1")

        assert "source_absence" not in jours[0]
