"""Part salariale de mutuelle et net imposable.

Une cotisation de mutuelle prélevée au salarié vient aujourd'hui en déduction
du net imposable, comme toute cotisation salariale. C'est juste pour les
formules où l'employeur participe (Isolé Colorplast : 29,24 € / 29,23 €) — la
convergence de mai 2026 avec les bulletins du cabinet l'a validée au centime
sur les 7 salariés.

Ça ne l'est pas pour un complément entièrement à la charge du salarié. Cas
constaté sur GIRERD, juillet 2026 : le complément « GAN Famille » (98,13 €,
aucune part patronale) était déduit de l'imposable chez nous et pas chez le
cabinet — 2 570,73 € contre 2 668,88 €, et un PAS inférieur de 4,22 €. Le
cabinet le retient APRÈS l'imposable, ce qui est le traitement des cotisations
finançant les frais de santé (art. 83, 1° quater du CGI, exclusion introduite
par la loi de finances 2014).

Ces tests posent le levier : un type de mutuelle peut déclarer sa part
salariale non déductible, et le net imposable la réintègre. Le défaut reste
« déductible », donc aucun bulletin existant ne bouge.

Chiffres repris du bulletin réel de GIRERD, juillet 2026 (env de test).
"""

from types import SimpleNamespace

import pytest

from app.modules.payroll.engine import calcul_net

pytestmark = pytest.mark.unit

BRUT = 3855.98
#: Total des cotisations salariales, CSG/CRDS non déductible comprise.
TOTAL_COTISATIONS_SALARIALES = 1010.52
REMUNERATION_HS = 449.54

LIGNES_COTISATIONS = [
    {"libelle": "CSG/CRDS non déductible", "montant_salarial": 102.74},
    {"libelle": "CSG/CRDS sur HS non déductible", "montant_salarial": 42.84},
]

ISOLE = {
    "id": "isole",
    "montant_salarial": 29.24,
    "montant_patronal": 29.23,
    "part_patronale_soumise_a_csg": True,
}
FAMILLE = {
    "id": "famille",
    "montant_salarial": 98.13,
    "montant_patronal": 0.0,
    "part_patronale_soumise_a_csg": True,
}

#: Imposable actuel de GIRERD : la part salariale Famille est déduite.
IMPOSABLE_AVEC_FAMILLE_DEDUITE = 2570.73
#: Imposable du cabinet, à 2 centimes près (écart de base CSG, hors sujet ici).
IMPOSABLE_ATTENDU = 2668.86


def _contexte(mutuelle_type_ids):
    return SimpleNamespace(
        month=7,
        cumuls={},
        contrat={
            "specificites_paie": {
                "mutuelle": {
                    "adhesion": True,
                    "mutuelle_type_ids": mutuelle_type_ids,
                    "lignes_specifiques": [],
                    "part_patronale_reintegree_impot": True,
                }
            }
        },
    )


def _client_factice(lignes):
    """Imite le client admin qui lit `company_mutuelle_types`."""

    class _Requete:
        def select(self, *_a, **_k):
            return self

        def in_(self, _colonne, ids):
            self._ids = ids
            return self

        def eq(self, *_a, **_k):
            return self

        def execute(self):
            return SimpleNamespace(
                data=[l for l in lignes if l["id"] in getattr(self, "_ids", [])]
            )

    class _Client:
        def table(self, _nom):
            return _Requete()

    return _Client()


def _imposable(monkeypatch, lignes_mutuelle):
    import app.core.database as database

    monkeypatch.setattr(
        database, "get_supabase_admin_client", lambda: _client_factice(lignes_mutuelle)
    )
    net_imposable, _ = calcul_net._calculer_net_imposable(
        _contexte([l["id"] for l in lignes_mutuelle]),
        BRUT,
        TOTAL_COTISATIONS_SALARIALES,
        LIGNES_COTISATIONS,
        REMUNERATION_HS,
    )
    return net_imposable


class TestPartSalarialeMutuelle:
    def test_une_part_salariale_non_deductible_est_reintegree(self, monkeypatch):
        """Le complément Famille, entièrement à la charge du salarié, ne doit
        pas réduire le revenu imposable."""
        famille = {**FAMILLE, "part_salariale_deductible_impot": False}

        assert _imposable(monkeypatch, [ISOLE, famille]) == IMPOSABLE_ATTENDU

    def test_une_mutuelle_deductible_ne_change_rien(self, monkeypatch):
        """Garde anti-régression : sans le drapeau, le comportement d'aujourd'hui
        est conservé — c'est celui qui converge avec le cabinet sur l'Isolé."""
        assert (
            _imposable(monkeypatch, [ISOLE, FAMILLE])
            == IMPOSABLE_AVEC_FAMILLE_DEDUITE
        )

    def test_le_drapeau_ne_touche_pas_la_part_patronale(self, monkeypatch):
        """La part patronale reste réintégrée : seules 29,23 € (Isolé) le sont,
        le complément Famille n'ayant aucune part employeur."""
        famille = {**FAMILLE, "part_salariale_deductible_impot": False}
        contexte = _contexte(["isole", "famille"])
        import app.core.database as database

        monkeypatch.setattr(
            database,
            "get_supabase_admin_client",
            lambda: _client_factice([ISOLE, famille]),
        )

        assert calcul_net._get_part_patronale_mutuelle(contexte) == 29.23
