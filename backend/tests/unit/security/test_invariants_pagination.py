"""
Le lecteur du script d'invariants pagine réellement.

PostgREST plafonne une réponse à 1000 lignes. La première version du
script lisait donc 1000 bulletins sur 1308 et 598 jours d'absence sur
2 455 — en annonçant des chiffres d'apparence normale. Un contrôle
d'intégrité qui sous-compte en silence est pire que pas de contrôle : il
rassure à tort.
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import patch


class _Reponse:
    def __init__(self, data: List[Dict[str, Any]]):
        self.data = data


class _Requete:
    """Imite le chaînage supabase et respecte la borne `range`."""

    def __init__(self, lignes: List[Dict[str, Any]], plafond: int):
        self._lignes = lignes
        self._plafond = plafond
        self._debut = 0
        self._fin = plafond - 1

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def is_(self, *_args, **_kwargs):
        return self

    def range(self, debut: int, fin: int):
        self._debut, self._fin = debut, fin
        return self

    def execute(self):
        tranche = self._lignes[self._debut : self._fin + 1]
        # Le serveur ne rend jamais plus que son plafond, quoi qu'on demande.
        return _Reponse(tranche[: self._plafond])


class TestPaginationInvariants:
    def _lire(self, nombre_de_lignes: int, plafond: int = 1000) -> int:
        from scripts import invariants_donnees

        lignes = [{"id": f"l{i}"} for i in range(nombre_de_lignes)]

        class _Client:
            def table(self, _nom):
                return _Requete(lignes, plafond)

        with patch.object(invariants_donnees, "supabase", _Client()):
            return len(invariants_donnees._lignes("peu_importe", "id"))

    def test_lit_au_dela_du_plafond_du_serveur(self):
        assert self._lire(1308) == 1308

    def test_lit_plusieurs_pages_pleines(self):
        assert self._lire(2455) == 2455

    def test_cas_limite_pile_une_page(self):
        assert self._lire(1000) == 1000

    def test_table_vide(self):
        assert self._lire(0) == 0
