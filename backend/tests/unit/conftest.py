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
    # Prolongé en base pendant une longue génération : en test, rien ne part.
    monkeypatch.setattr(verrou_generation, "_prolonger", lambda params: None, raising=False)
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


@pytest.fixture(autouse=True)
def aucun_depart_ni_contrat_passe_lu_en_base(monkeypatch) -> None:
    """La sortie d'un salarié parti se lit sur son départ (`employee_exits`) : en
    test, aucune, sauf doublure explicite (`patch(...lecteur_contrats...)`) ou
    instance neuve de `LecteurContrats` sur une base en mémoire."""
    from app.modules.employees.application.contrat_du_mois import lecteur_contrats

    monkeypatch.setattr(lecteur_contrats, "sortie_du_contrat", lambda *a, **k: None)
    monkeypatch.setattr(lecteur_contrats, "contrat_passe_du_mois", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def aucun_mois_suivant_lu_en_base(monkeypatch) -> None:
    """Après une génération, le mois suivant se lit en base (`suite_du_bulletin`) :
    en test, aucun, sauf doublure explicite."""
    from app.modules.payslips.application import commands

    monkeypatch.setattr(commands, "mois_suivant_a_recalculer", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def aucun_bac_a_sable_a_la_lecture(monkeypatch) -> None:
    """Un validé dont l'empreinte change est recalculé au bac à sable à la lecture :
    en test, ni bulletin relu, ni moteur lancé, ni empreinte écrite. Les tests de
    cette règle remplacent ces fonctions eux-mêmes."""
    from app.modules.payroll.application import empreinte_entrees_service as service

    def _jamais(*_a, **_k):
        raise RuntimeError("bac à sable non lancé en test unitaire")

    monkeypatch.setattr(service, "lire_bulletin_enregistre", lambda *_a, **_k: None)
    monkeypatch.setattr(service, "_calculer_au_bac_a_sable", _jamais)
    monkeypatch.setattr(service, "poser_empreintes_verifiees", lambda *_a, **_k: None)
    # Hors de la requête en vrai ; en test, jouée sur place, sans fil.
    monkeypatch.setattr(service, "_lancer_en_arriere_plan", lambda tache: tache())
    service.oublier_les_verdicts()
