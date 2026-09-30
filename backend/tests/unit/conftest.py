"""Réglages communs aux tests unitaires : aucun appel à une vraie base."""

from __future__ import annotations

import pytest

from app.modules.payroll.documents import verrou_generation


class VerrousEnMemoire:
    """Remplace les deux fonctions SQL du verrou de génération."""

    def __init__(self) -> None:
        self.tenus: dict[tuple, str] = {}
        self.appels: list[str] = []

    def __call__(self, nom: str, params: dict):
        self.appels.append(nom)
        cle = (params["p_employee_id"], params["p_year"], params["p_month"])
        if nom == "prendre_verrou_generation_bulletin":
            if cle in self.tenus:
                return False
            self.tenus[cle] = params["p_jeton"]
            return True
        if nom == "rendre_verrou_generation_bulletin":
            if self.tenus.get(cle) == params["p_jeton"]:
                del self.tenus[cle]
            return None
        raise AssertionError(f"fonction inattendue : {nom}")


@pytest.fixture(autouse=True)
def verrous_de_generation(monkeypatch) -> VerrousEnMemoire:
    """Le verrou de génération passe par la base : en test, il reste en mémoire."""
    faux = VerrousEnMemoire()
    monkeypatch.setattr(verrou_generation, "_rpc", faux)
    return faux


@pytest.fixture(autouse=True)
def aucun_arret_valide_lu_en_base(monkeypatch) -> None:
    """Les arrêts validés se lisent en base (`absence_requests`) : en test, aucun,
    sauf doublure explicite (`patch(...arrets_valides_reader)`)."""
    from app.modules.schedules.infrastructure.arrets_valides import arrets_valides_reader

    monkeypatch.setattr(arrets_valides_reader, "par_salarie", lambda *a, **k: {})
