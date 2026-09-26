"""
Attestation de salaire d'un arrêt : périmètre société (audit du 25/09/2026, E3).

Téléchargement, informations et génération de l'attestation n'utilisaient pas
`current_user` : tout compte connecté lisait l'attestation d'un arrêt d'une
autre société, et pouvait la régénérer (la génération écrase l'existante).
L'arrêt doit désormais appartenir à la société active, et l'appelant être RH
de cette société ou le titulaire de l'arrêt (l'espace salarié lit et
télécharge sa propre attestation). La génération et le marquage de
transmission CPAM restent réservés aux RH.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.users.schemas.responses import CompanyAccess, User

SOCIETE_A = "aaaaaaaa-1111-1111-1111-111111111111"
SOCIETE_B = "bbbbbbbb-2222-2222-2222-222222222222"
ARRET = "eeeeeeee-5555-5555-5555-555555555555"
COMPTE = "dddddddd-4444-4444-4444-444444444444"
MA_FICHE = "cccccccc-3333-3333-3333-333333333333"
AUTRE_FICHE = "ffffffff-6666-6666-6666-666666666666"


def _user(role: str = "rh") -> User:
    return User(
        id=COMPTE,
        email="compte@societe-a.fr",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=SOCIETE_A,
                company_name="Société A",
                role=role,
                is_primary=True,
            ),
        ],
        active_company_id=SOCIETE_A,
    )


def _arret(company_id: str, employee_id: str = MA_FICHE) -> dict:
    return {
        "id": ARRET,
        "company_id": company_id,
        "employee_id": employee_id,
        "type": "arret_maladie",
        "status": "validated",
    }


class _Contexte:
    """Client HTTP + dépendances de lecture/écriture simulées."""

    def __init__(self, role: str, arret: dict | None):
        self.role = role
        self.arret = arret

    def __enter__(self):
        app.dependency_overrides[get_current_user] = lambda: _user(self.role)
        self._patches = [
            patch(
                "app.modules.absences.api.router.absence_router.get_absence_by_id",
                return_value=self.arret,
            ),
            patch(
                "app.modules.absences.api.router.absence_router."
                "resolve_employee_id_for_user",
                return_value=MA_FICHE,
            ),
            patch("app.modules.absences.api.router.queries"),
            patch("app.modules.absences.api.router.commands"),
        ]
        _, _, self.queries, self.commands = [p.start() for p in self._patches]
        self.queries.download_salary_certificate.return_value = (
            b"%PDF-1.4",
            "attestation.pdf",
        )
        self.queries.get_salary_certificate_info.return_value = {
            "id": "cert-1",
            "filename": "attestation.pdf",
        }
        self.commands.generate_salary_certificate.return_value = "cert-1"
        self.commands.mark_salary_certificate_transmitted.return_value = {
            "absence_id": ARRET,
            "transmitted_to_cpam": True,
            "message": "Transmission CPAM enregistrée.",
        }
        self.client = TestClient(app)
        return self

    def __exit__(self, *exc):
        for p in self._patches:
            p.stop()
        app.dependency_overrides.pop(get_current_user, None)
        return False


def _telecharger(ctx: _Contexte):
    return ctx.client.get(f"/api/absences/{ARRET}/certificate/download")


def _infos(ctx: _Contexte):
    return ctx.client.get(f"/api/absences/{ARRET}/certificate")


def _generer(ctx: _Contexte):
    return ctx.client.post(f"/api/absences/{ARRET}/generate-certificate")


def _transmettre(ctx: _Contexte):
    return ctx.client.patch(
        f"/api/absences/{ARRET}/certificate/transmission",
        json={"transmitted_to_cpam": True},
    )


# ----- autre société : refusé, rien n'est lu ni écrit -----


class TestArretDUneAutreSociete:
    def test_telechargement_refuse(self):
        with _Contexte("rh", _arret(SOCIETE_B)) as ctx:
            reponse = _telecharger(ctx)
            ctx.queries.download_salary_certificate.assert_not_called()
        # 404, libellé du cas « aucune attestation » : l'arrêt n'est pas révélé.
        assert reponse.status_code == 404
        assert reponse.json()["detail"] == "Aucune attestation trouvée pour cet arrêt."

    def test_informations_refusees(self):
        with _Contexte("rh", _arret(SOCIETE_B)) as ctx:
            reponse = _infos(ctx)
            ctx.queries.get_salary_certificate_info.assert_not_called()
        assert reponse.status_code == 404

    def test_generation_refusee_sans_ecraser(self):
        with _Contexte("rh", _arret(SOCIETE_B)) as ctx:
            reponse = _generer(ctx)
            ctx.commands.generate_salary_certificate.assert_not_called()
        assert reponse.status_code == 404
        assert reponse.json()["detail"] == "Arrêt non trouvé."

    def test_transmission_refusee(self):
        with _Contexte("rh", _arret(SOCIETE_B)) as ctx:
            reponse = _transmettre(ctx)
            ctx.commands.mark_salary_certificate_transmitted.assert_not_called()
        assert reponse.status_code == 404

    def test_titulaire_dans_une_autre_societe_refuse(self):
        """Même fiche, mais l'arrêt n'est pas de la société active."""
        with _Contexte("collaborateur", _arret(SOCIETE_B)) as ctx:
            reponse = _telecharger(ctx)
            ctx.queries.download_salary_certificate.assert_not_called()
        assert reponse.status_code == 404


# ----- même société : comme avant -----


class TestArretDeMaSociete:
    def test_rh_telecharge(self):
        with _Contexte("rh", _arret(SOCIETE_A, AUTRE_FICHE)) as ctx:
            reponse = _telecharger(ctx)
            ctx.queries.download_salary_certificate.assert_called_once_with(ARRET)
        assert reponse.status_code == 200
        assert reponse.content == b"%PDF-1.4"
        assert reponse.headers["content-type"] == "application/pdf"

    def test_rh_lit_les_informations(self):
        with _Contexte("rh", _arret(SOCIETE_A, AUTRE_FICHE)) as ctx:
            reponse = _infos(ctx)
        assert reponse.status_code == 200
        assert reponse.json() == {"id": "cert-1", "filename": "attestation.pdf"}

    def test_rh_genere(self):
        with _Contexte("rh", _arret(SOCIETE_A, AUTRE_FICHE)) as ctx:
            reponse = _generer(ctx)
            ctx.commands.generate_salary_certificate.assert_called_once_with(
                ARRET, generated_by=COMPTE
            )
        assert reponse.status_code == 200
        assert reponse.json() == {
            "certificate_id": "cert-1",
            "message": "Attestation générée avec succès",
        }

    def test_rh_marque_la_transmission(self):
        with _Contexte("rh", _arret(SOCIETE_A, AUTRE_FICHE)) as ctx:
            reponse = _transmettre(ctx)
        assert reponse.status_code == 200
        assert reponse.json()["transmitted_to_cpam"] is True

    @pytest.mark.parametrize("appel", [_telecharger, _infos])
    def test_salarie_lit_sa_propre_attestation(self, appel):
        with _Contexte("collaborateur", _arret(SOCIETE_A, MA_FICHE)) as ctx:
            reponse = appel(ctx)
        assert reponse.status_code == 200

    @pytest.mark.parametrize("appel", [_telecharger, _infos])
    def test_salarie_ne_lit_pas_celle_d_un_collegue(self, appel):
        with _Contexte("collaborateur", _arret(SOCIETE_A, AUTRE_FICHE)) as ctx:
            reponse = appel(ctx)
            ctx.queries.download_salary_certificate.assert_not_called()
            ctx.queries.get_salary_certificate_info.assert_not_called()
        assert reponse.status_code == 404

    def test_salarie_ne_regenere_pas_son_attestation(self):
        """La génération est un geste RH (seule la page RH l'appelle)."""
        with _Contexte("collaborateur", _arret(SOCIETE_A, MA_FICHE)) as ctx:
            reponse = _generer(ctx)
            ctx.commands.generate_salary_certificate.assert_not_called()
        assert reponse.status_code == 403
