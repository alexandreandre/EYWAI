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


def pytest_configure(config) -> None:
    config.addinivalue_line(
        "markers",
        "effets_en_base: les effets d'un bulletin (prêts, avances, CET, modulation) "
        "sont lus et défaits pour de bon, sur une base en mémoire",
    )


@pytest.fixture(autouse=True)
def aucun_effet_de_bulletin_en_base(request, monkeypatch) -> None:
    """Défaire les effets d'un bulletin lit et écrit en base : en test, rien à
    défaire ni à refuser, sauf pour les tests qui portent `effets_en_base`."""
    if request.node.get_closest_marker("effets_en_base"):
        return
    from app.modules.payslips.application import effets_du_bulletin as effets

    for nom in (
        "refuser_si_effets_non_defaisables",
        "defaire_effets_du_bulletin",
        "defaire_avant_suppression",
    ):
        monkeypatch.setattr(effets, nom, lambda *a, **k: None)


@pytest.fixture(autouse=True)
def aucun_arret_valide_lu_en_base(monkeypatch) -> None:
    """Les arrêts validés se lisent en base (`absence_requests`) : en test, aucun,
    sauf doublure explicite (`patch(...arrets_valides_reader)`)."""
    from app.modules.schedules.infrastructure.arrets_valides import arrets_valides_reader

    monkeypatch.setattr(arrets_valides_reader, "par_salarie", lambda *a, **k: {})
