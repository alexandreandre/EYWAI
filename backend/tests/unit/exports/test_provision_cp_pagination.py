"""
La provision de congés payés lit TOUS les bulletins, pas les 1000 premiers.

PostgREST tronque une réponse à 1000 lignes sans le signaler. La provision
valorise chaque solde par un salaire de référence moyenné sur douze mois de
bulletins : un bulletin tombé dans la troncature n'apparaît pas comme
manquant, il abaisse la moyenne. La dette de congés payés déclarée à la
comptabilité serait donc sous-évaluée, silencieusement.

Cartol Industrie compte 486 bulletins sur six mois : la barre des 1000 est
franchie dès que l'historique atteint l'année pleine.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.modules.exports.infrastructure.export_provision_cp import (
    TAILLE_PAGE,
    _lire_bulletins,
)

COMPANY_ID = "11111111-1111-1111-1111-111111111111"


def _bulletin(index: int, annee: int, mois: int) -> dict:
    return {
        "employee_id": f"salarie-{index}",
        "year": annee,
        "month": mois,
        "payslip_data": {
            "salaire_brut": 2000.0,
            "cotisations_officielles": [{"total_patronal": 800.0}],
        },
    }


#: PostgREST refuse de rendre plus que cela en une réponse, sans le signaler.
PLAFOND_SERVEUR = 1000


class _TableFeinte:
    """Rejoue PostgREST : `range` découpe, et le serveur plafonne à 1000 lignes.

    Ce plafond est le cœur du piège. Sans lui, une pagination mal dimensionnée
    (page plus large que le plafond) passerait le test tout en perdant des
    lignes en production.
    """

    def __init__(self, lignes):
        self._lignes = lignes
        self._debut = 0
        self._fin = len(lignes)

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def in_(self, *_args, **_kwargs):
        return self

    def range(self, debut, fin):
        self._debut, self._fin = debut, fin + 1
        return self

    def execute(self):
        fin = min(self._fin, self._debut + PLAFOND_SERVEUR)
        return MagicMock(data=self._lignes[self._debut : fin])


class TestPaginationDesBulletins:
    def test_lit_au_dela_de_mille_bulletins(self):
        """1200 bulletins sur 12 mois : aucun ne doit être perdu."""
        mois_cibles = [(2026, m) for m in range(1, 13)]
        lignes = [
            _bulletin(i, 2026, mois_cibles[i % 12][1]) for i in range(1200)
        ]
        table = _TableFeinte(lignes)

        with patch(
            "app.modules.exports.infrastructure.export_provision_cp.supabase"
        ) as base:
            base.table.return_value = table
            resultat = _lire_bulletins(COMPANY_ID, mois_cibles)

        assert len(resultat) == 1200, (
            f"{len(resultat)} salariés retenus sur 1200 — des bulletins ont été "
            "perdus dans la troncature PostgREST, et la provision serait "
            "sous-évaluée sans aucune anomalie affichée."
        )

    def test_la_derniere_page_incomplete_arrete_la_lecture(self):
        """Un lot plus court que la page signifie la fin : pas de boucle infinie."""
        mois_cibles = [(2026, 1)]
        lignes = [_bulletin(i, 2026, 1) for i in range(TAILLE_PAGE + 3)]
        table = _TableFeinte(lignes)

        with patch(
            "app.modules.exports.infrastructure.export_provision_cp.supabase"
        ) as base:
            base.table.return_value = table
            resultat = _lire_bulletins(COMPANY_ID, mois_cibles)

        assert len(resultat) == TAILLE_PAGE + 3

    def test_la_page_reste_sous_le_plafond_du_serveur(self):
        """Une page plus large que 1000 perdrait des lignes sans rien dire."""
        assert TAILLE_PAGE <= PLAFOND_SERVEUR, (
            f"TAILLE_PAGE={TAILLE_PAGE} dépasse le plafond PostgREST de "
            f"{PLAFOND_SERVEUR} : le serveur rendrait une page courte, la "
            "boucle croirait avoir fini, et des bulletins seraient perdus."
        )

    def test_les_mois_hors_fenetre_sont_ignores(self):
        """La pagination ne doit pas élargir la fenêtre demandée."""
        lignes = [_bulletin(0, 2026, 1), _bulletin(1, 2026, 7)]
        table = _TableFeinte(lignes)

        with patch(
            "app.modules.exports.infrastructure.export_provision_cp.supabase"
        ) as base:
            base.table.return_value = table
            resultat = _lire_bulletins(COMPANY_ID, [(2026, 1)])

        assert set(resultat) == {"salarie-0"}
