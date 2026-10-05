"""La RH recale les congés payés N-1 et N d'un salarié à la fin d'un mois.

Le crayon de l'onglet Soldes ne corrigeait que RTT et JTC : un écart de congés
avec l'ancien logiciel ne se corrigeait que par l'import super-administrateur.
Le recalage RH passe par la même mécanique que la reprise (`apply_cp_solde_import`,
solde d'ouverture DATÉ), pour que :

- le pied de bulletin et l'indemnité de départ le relisent (mêmes ajustements) ;
- le roulement du 1er juin le traite comme une reprise (pas de jour perdu de plus) ;
- les RTT, la note « Import CP bulletin » et la bascule restent intacts.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.security import get_current_user
from app.main import app
from app.modules.absences.application import leave_settings_commands as cmd
from app.modules.absences.domain.leave_policy import (
    EmployeeLeaveAdjustment,
    LeavePolicySettings,
)
from app.modules.absences.domain.rules import compute_cp_period_balances
from app.modules.absences.infrastructure import repository as absences_repository
from app.modules.absences.infrastructure.short_cache import ShortLivedCache
from app.modules.absences.schemas.leave_settings import EmployeeCpRecalage
from app.modules.users.schemas.responses import CompanyAccess, User
from app.shared.reprise_paie import Bascule

pytestmark = pytest.mark.unit

SOCIETE = "aaaaaaaa-1111-1111-1111-111111111111"
SALARIE = "bbbbbbbb-2222-2222-2222-222222222222"
FIN_SEPTEMBRE = date(2026, 9, 30)


def _demande(**kw) -> EmployeeCpRecalage:
    valeurs = {"year": 2026, "month": 9, "cp_n1_solde": 27.0, "cp_n_solde": 6.24,
               "note": "Un jour d'écart avec le bulletin de septembre"}
    valeurs.update(kw)
    return EmployeeCpRecalage(**valeurs)


@pytest.fixture
def recalage(monkeypatch):
    """Le recalage sans base : on observe ce qu'il transmet à la reprise datée."""
    appels: list[dict] = []
    monkeypatch.setattr(cmd, "_ensure_employee_in_company", lambda *a: None)
    monkeypatch.setattr(cmd, "lire_bascule", lambda company_id: None)
    monkeypatch.setattr(cmd, "get_cp_opening_reference_dates", lambda ids: {})
    monkeypatch.setattr(cmd, "get_employee_adjustment", lambda e, y: EmployeeLeaveAdjustment.empty())
    monkeypatch.setattr(cmd, "apply_cp_solde_import", lambda *a, **kw: appels.append({"args": a, **kw}))
    monkeypatch.setattr(
        "app.modules.absences.application.queries.get_absence_balances_for_payslip",
        lambda employee_id, year, month, date_fin_prises=None: {
            "conges_payes_periode_precedente": {"solde": 27.0},
            "conges_payes": {"solde": 6.24},
        },
    )
    return appels


# --- Ce que la RH saisit --------------------------------------------------------


def test_le_commentaire_est_obligatoire():
    with pytest.raises(ValidationError):
        _demande(note="   ")
    with pytest.raises(ValidationError):
        _demande(note=None)


def test_le_recalage_est_une_reprise_datee_qui_ne_touche_pas_aux_rtt(recalage):
    cmd.recaler_cp_rh(SOCIETE, SALARIE, _demande())

    (appel,) = recalage
    assert appel["args"] == (SOCIETE, SALARIE, 2026)
    assert appel["month"] == 9
    assert appel["cp_n1_solde"] == 27.0 and appel["cp_n_solde"] == 6.24
    # Sans solde RTT : le compteur RTT du salarié reste celui qu'il était.
    assert appel["rtt_solde"] is None


def test_la_note_dit_quand_quoi_et_pourquoi(recalage):
    cmd.recaler_cp_rh(SOCIETE, SALARIE, _demande())

    note = recalage[0]["note"]
    assert note.startswith("Recalage RH du ")
    assert "au 30/09/2026" in note
    assert "CP N-1 27,00 j" in note and "CP N 6,24 j" in note
    assert "Un jour d'écart avec le bulletin de septembre" in note


def test_la_note_precedente_reste_en_trace(recalage, monkeypatch):
    monkeypatch.setattr(
        cmd, "get_employee_adjustment",
        lambda e, y: replace(EmployeeLeaveAdjustment.empty(), note="Reprise Quadra au 31/08/2026"),
    )
    cmd.recaler_cp_rh(SOCIETE, SALARIE, _demande())

    assert "Précédent : Reprise Quadra au 31/08/2026" in recalage[0]["note"]


def test_le_commentaire_ne_bascule_jamais_en_mode_fidele_au_bulletin(recalage):
    """« Import CP bulletin » dans la note est du code (rules._is_bulletin_cp_import) :
    tapé dans un commentaire, il changerait le mode de calcul du salarié."""
    cmd.recaler_cp_rh(SOCIETE, SALARIE, _demande(note="Import CP bulletin de septembre"))

    assert "Import CP bulletin" not in recalage[0]["note"]


def test_la_reponse_relit_le_solde_que_le_bulletin_imprimera(recalage):
    reponse = cmd.recaler_cp_rh(SOCIETE, SALARIE, _demande())

    assert reponse.date_reference == FIN_SEPTEMBRE
    assert reponse.cp_n1_solde == 27.0
    assert reponse.cp_n_solde == 6.24


# --- Ce qui est refusé, et où corriger ---------------------------------------------


def test_un_mois_qui_n_est_pas_termine_est_refuse(recalage):
    annee = date.today().year + 1
    with pytest.raises(ValueError, match="pas terminé"):
        cmd.recaler_cp_rh(SOCIETE, SALARIE, _demande(year=annee, month=1))
    assert recalage == []


def test_un_mois_avant_la_bascule_est_refuse(recalage, monkeypatch):
    monkeypatch.setattr(
        cmd, "lire_bascule",
        lambda company_id: Bascule(annee=2026, mois=8, logiciel_precedent="Quadra"),
    )
    with pytest.raises(ValueError, match="31/08/2026") as refus:
        cmd.recaler_cp_rh(SOCIETE, SALARIE, _demande(month=7))
    assert "août 2026" in str(refus.value)
    assert recalage == []


def test_le_mois_de_la_bascule_corrige_la_reprise(recalage, monkeypatch):
    monkeypatch.setattr(
        cmd, "lire_bascule",
        lambda company_id: Bascule(annee=2026, mois=8, logiciel_precedent="Quadra"),
    )
    cmd.recaler_cp_rh(SOCIETE, SALARIE, _demande(month=8))
    assert len(recalage) == 1


def test_un_mois_avant_le_dernier_recalage_est_refuse(recalage, monkeypatch):
    """Revenir en arrière remplacerait une reprise plus récente par une plus ancienne."""
    monkeypatch.setattr(cmd, "get_cp_opening_reference_dates", lambda ids: {SALARIE: date(2026, 10, 31)})
    with pytest.raises(ValueError, match="31/10/2026"):
        cmd.recaler_cp_rh(SOCIETE, SALARIE, _demande(month=9))
    assert recalage == []


def test_un_salarie_en_mode_fidele_au_bulletin_est_refuse(recalage, monkeypatch):
    monkeypatch.setattr(
        cmd, "get_employee_adjustment",
        lambda e, y: replace(EmployeeLeaveAdjustment.empty(), note="Import CP bulletin Août 2026 (x.pdf)"),
    )
    with pytest.raises(ValueError, match="administrateur"):
        cmd.recaler_cp_rh(SOCIETE, SALARIE, _demande())
    assert recalage == []


# --- La reprise datée, sans RTT ni cache périmé ----------------------------------


def _importer(monkeypatch, ecrits, *, affiche=None, avant_lecture=None):
    monkeypatch.setattr("app.modules.absences.infrastructure.queries.get_employee_hire_date", lambda e: "2020-01-01")
    monkeypatch.setattr(cmd, "get_leave_policy", lambda c: None)
    monkeypatch.setattr(cmd, "absence_repository", type("R", (), {"list_validated_for_employees": staticmethod(lambda ids: [])}))
    monkeypatch.setattr("app.modules.absences.domain.rules.compute_cp_period_balances",
                        lambda *a, **kw: {"n1_remaining": 25.0, "n_remaining": 6.24})
    monkeypatch.setattr(cmd, "bulletin_reference_date", lambda y, m: FIN_SEPTEMBRE)
    monkeypatch.setattr(cmd, "upsert_employee_adjustment", lambda c, e, y, p: ecrits.append(dict(p)))

    def lire(employee_id, year, month, date_fin_prises=None):
        if avant_lecture:
            avant_lecture()
        return affiche

    monkeypatch.setattr("app.modules.absences.application.queries.get_absence_balances_for_payslip", lire)


def test_sans_solde_rtt_la_reprise_n_ecrit_pas_le_compteur_rtt(monkeypatch):
    ecrits: list[dict] = []
    _importer(monkeypatch, ecrits)
    with patch("app.modules.absences.domain.rules.compute_rtt_balance") as rtt:
        cmd.apply_cp_solde_import(SOCIETE, SALARIE, 2026, cp_n1_solde=27.0, cp_n_solde=6.24,
                                  rtt_solde=None, month=9, note="n")
    rtt.assert_not_called()
    assert ecrits and all("rtt_opening_balance" not in e for e in ecrits)
    assert ecrits[0]["cp_opening_reference_date"] == "2026-09-30"
    assert ecrits[0]["cp_n1_opening_balance"] == 2.0


def test_le_solde_affiche_est_relu_avec_la_nouvelle_date_de_reprise(monkeypatch):
    """Les congés du planning antérieurs à la date de reprise sont absorbés par le
    solde repris. Relus avec la date d'avant (cache de quelques secondes), ils
    étaient encore décomptés et le recalage sur l'affiché ne les voyait pas."""
    cache = ShortLivedCache(ttl_seconds=60, clock=lambda: 1000.0)
    cache.get_or_load((SALARIE,), lambda ids: {SALARIE: date(2026, 8, 31)})
    monkeypatch.setattr(absences_repository, "_cutoff_cache", cache)
    vus: list[int] = []
    ecrits: list[dict] = []
    _importer(monkeypatch, ecrits, avant_lecture=lambda: vus.append(len(cache._entries)),
              affiche={"conges_payes_periode_precedente": {"solde": 27.0}, "conges_payes": {"solde": 6.24}})

    cmd.apply_cp_solde_import(SOCIETE, SALARIE, 2026, cp_n1_solde=27.0, cp_n_solde=6.24,
                              rtt_solde=None, month=9, note="n")

    assert vus == [0]


# --- Le 1er juin ne perd pas un jour de plus --------------------------------------


def test_au_1er_juin_le_n_recale_devient_le_n_1_sans_perte():
    """Recalage au 30/09/2026 : comme toute reprise datée, il roule au 1er juin
    2027 (le N de clôture devient le N-1) ; le double compte connu du modèle ne
    s'y ajoute pas tant que la reprise vaut."""
    politique = LeavePolicySettings(cp_reference_period_start_month=6, cp_carryover_enabled=True)
    entree = date(2020, 1, 1)
    demandes = [{"type": "conge_paye", "status": "validated", "jours_payes": 5.0,
                 "selected_days": [f"2026-08-{d:02d}" for d in (3, 4, 5, 6, 7)]}]
    theorique = compute_cp_period_balances(entree, demandes, FIN_SEPTEMBRE, policy=politique,
                                           adjustment=EmployeeLeaveAdjustment.empty())
    recale = EmployeeLeaveAdjustment(
        cp_n1_opening_balance=round(27.0 - theorique["n1_remaining"], 2),
        cp_n_opening_balance=round(6.24 - theorique["n_remaining_brut"], 2),
        cp_opening_reference_date=FIN_SEPTEMBRE,
    )

    fin_mai = compute_cp_period_balances(entree, demandes, date(2027, 5, 31), policy=politique, adjustment=recale)
    fin_juin = compute_cp_period_balances(entree, demandes, date(2027, 6, 30), policy=politique, adjustment=recale)

    assert compute_cp_period_balances(entree, demandes, FIN_SEPTEMBRE, policy=politique,
                                      adjustment=recale)["n1_remaining"] == 27.0
    assert fin_juin["n1_remaining"] == fin_mai["n_remaining"]


# --- La route RH ------------------------------------------------------------------


def _rh() -> User:
    return User(
        id="dddddddd-4444-4444-4444-444444444444",
        email="rh@societe-a.fr",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(company_id=SOCIETE, company_name="Société A", role="rh", is_primary=True)
        ],
        active_company_id=SOCIETE,
    )


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = _rh
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


URL = f"/api/absences/leave-settings/employees/{SALARIE}/soldes-cp"
CORPS = {"year": 2026, "month": 9, "cp_n1_solde": 27, "cp_n_solde": 6.24, "note": "Écart d'un jour"}


def test_la_route_rh_recale_et_rend_le_solde_relu(client):
    from app.modules.absences.schemas.leave_settings_responses import CpRecalageResponse

    with patch.object(cmd, "recaler_cp_rh", return_value=CpRecalageResponse(
        employee_id=SALARIE, date_reference=FIN_SEPTEMBRE, cp_n1_solde=27.0, cp_n_solde=6.24,
    )) as recaler:
        reponse = client.put(URL, json=CORPS)

    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["date_reference"] == "2026-09-30"
    (company_id, employee_id, corps), _ = recaler.call_args
    assert (company_id, employee_id, corps.month) == (SOCIETE, SALARIE, 9)


def test_un_refus_garde_son_message(client):
    with patch.object(cmd, "recaler_cp_rh", side_effect=ValueError("Le mois choisi n'est pas terminé.")):
        reponse = client.put(URL, json=CORPS)

    assert reponse.status_code == 400
    assert reponse.json()["detail"] == "Le mois choisi n'est pas terminé."


def test_sans_commentaire_la_route_refuse(client):
    reponse = client.put(URL, json={**CORPS, "note": ""})
    assert reponse.status_code == 422
