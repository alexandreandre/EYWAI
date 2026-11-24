"""Saisie sur salaire : montant total de la dette, reste dû, arrêt à zéro.

Demande d'Elsa (Zone 404, 24/11/2026) : la saisie ne connaissait que la
mensualité. On saisit désormais le montant total de la dette ; le reste dû est
ce total moins ce qui a déjà été retenu (historique `salary_seizure_deductions`).
La retenue du mois est plafonnée au reste dû, et la saisie se termine quand il
atteint zéro : plus rien n'est retenu ensuite.

La quotité saisissable (barème légal, L3252-2) reste le plafond : celui du reste
dû s'y ajoute, il ne la remplace pas. Sans montant total, rien ne change.
Données fictives.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.modules.saisies_avances.application import service
from app.modules.saisies_avances.domain import rules
from app.modules.saisies_avances.infrastructure import queries as infra_queries
from app.modules.saisies_avances.schemas.requests import SalarySeizureUpdate
from app.modules.saisies_avances.schemas.responses import SalarySeizure

from .test_quotite_saisissable_legale import BAREME

pytestmark = pytest.mark.unit

PLAFONNEE = "saisie_sur_salaire_plafonnee"
SOLDEE = "saisie_soldee"


def _saisie(**champs) -> dict:
    saisie = {
        "id": "saisie-1",
        "type": "saisie_arret",
        "calculation_mode": "fixe",
        "amount": 300.0,
        "priority": 4,
        "start_date": "2026-07-01",
        "creditor_name": "Créancier fictif SARL",
        "reference_legale": None,
        "status": "active",
    }
    saisie.update(champs)
    return saisie


def _enrichir(net: float, saisies: list, deja_retenu: dict | None = None, payslip_id="bulletin-1"):
    ecritures = MagicMock()
    totaux = MagicMock(
        return_value={k: Decimal(str(v)) for k, v in (deja_retenu or {}).items()}
    )
    with (
        patch.object(service, "get_seizures_for_period", return_value=[dict(s) for s in saisies]),
        patch.object(service, "get_bareme_quotite_saisissable", return_value=BAREME),
        patch.object(service, "get_advances_to_repay", return_value=[]),
        patch.object(service, "get_retenues_sur_le_net_du_mois", return_value=[]),
        patch.object(service, "supprimer_deductions_du_bulletin"),
        patch.object(service, "insert_seizure_deduction", ecritures.saisie),
        patch.object(service, "seizure_repository", ecritures.depot),
        patch.object(service, "total_retenu_par_saisie", totaux),
    ):
        bulletin = service.enrich_payslip(
            {"net_a_payer": net, "salaire_brut": 3000.0}, "e1", 2026, 10, payslip_id=payslip_id
        )
    return bulletin, ecritures, totaux


def _codes(bulletin: dict) -> list[str]:
    return [a.get("code") for a in bulletin.get("alertes_baremes") or []]


# ----- Règle pure -----


def test_reste_du_sans_montant_total_est_none():
    assert rules.reste_du_de_la_saisie(None, Decimal("400")) is None


def test_reste_du_est_le_total_moins_le_deja_retenu():
    assert rules.reste_du_de_la_saisie(Decimal("1000"), Decimal("400")) == Decimal("600.00")


def test_reste_du_ne_descend_pas_sous_zero():
    assert rules.reste_du_de_la_saisie(Decimal("1000"), Decimal("1200")) == Decimal("0.00")


# ----- Bulletin -----


def test_la_retenue_est_plafonnee_au_reste_du_et_la_saisie_se_termine():
    bulletin, ecritures, totaux = _enrichir(
        2500.0, [_saisie(montant_total=1000)], deja_retenu={"saisie-1": 950}
    )
    assert bulletin["retenues_saisies"]["total_preleve"] == 50.0
    assert bulletin["net_a_payer"] == pytest.approx(2450.0)
    # Le déjà retenu se lit sans le bulletin recalculé.
    assert totaux.call_args.kwargs.get("sauf_bulletin") == "bulletin-1"
    assert ecritures.saisie.call_args.args[-1] == 50.0
    # Dernière retenue dite, sans la fausse alerte « quotité ».
    assert SOLDEE in _codes(bulletin)
    assert PLAFONNEE not in _codes(bulletin)
    ecritures.depot.update.assert_called_once_with("saisie-1", {"status": "closed"})


def test_rien_n_est_retenu_quand_le_reste_du_est_nul():
    bulletin, ecritures, _ = _enrichir(
        2500.0, [_saisie(montant_total=1000)], deja_retenu={"saisie-1": 1000}
    )
    assert bulletin["retenues_saisies"]["total_preleve"] == 0
    assert bulletin["net_a_payer"] == 2500.0
    ecritures.saisie.assert_not_called()
    assert PLAFONNEE not in _codes(bulletin)
    # Total ramené au déjà retenu à l'écran : la saisie se termine aussi.
    ecritures.depot.update.assert_called_once_with("saisie-1", {"status": "closed"})


def test_une_retenue_qui_ne_solde_pas_laisse_la_saisie_active():
    bulletin, ecritures, _ = _enrichir(
        2500.0, [_saisie(montant_total=1000)], deja_retenu={"saisie-1": 300}
    )
    assert bulletin["retenues_saisies"]["total_preleve"] == 300.0
    assert SOLDEE not in _codes(bulletin)
    ecritures.depot.update.assert_not_called()


def test_sans_montant_total_rien_ne_change():
    bulletin, ecritures, totaux = _enrichir(2500.0, [_saisie()])
    assert bulletin["retenues_saisies"]["total_preleve"] == 300.0
    assert bulletin["net_a_payer"] == pytest.approx(2200.0)
    totaux.assert_not_called()
    ecritures.depot.update.assert_not_called()
    assert SOLDEE not in _codes(bulletin)


def test_la_quotite_saisissable_reste_le_plafond():
    """Reste dû large : la retenue est celle de la quotité, comme sans total."""
    sans_total, _, _ = _enrichir(1383.52, [_saisie(amount=900.0)])
    avec_total, ecritures, _ = _enrichir(
        1383.52, [_saisie(amount=900.0, montant_total=5000)], deja_retenu={"saisie-1": 0}
    )
    quotite = sans_total["retenues_saisies"]["total_preleve"]
    assert quotite < 900
    assert avec_total["retenues_saisies"]["total_preleve"] == quotite
    assert PLAFONNEE in _codes(avec_total)
    ecritures.depot.update.assert_not_called()


def test_le_reste_du_plus_bas_que_la_quotite_prend_le_pas():
    bulletin, _, _ = _enrichir(
        1383.52, [_saisie(amount=900.0, montant_total=5000)], deja_retenu={"saisie-1": 4980}
    )
    assert bulletin["retenues_saisies"]["total_preleve"] == 20.0
    assert PLAFONNEE not in _codes(bulletin)
    assert SOLDEE in _codes(bulletin)


def test_le_recalcul_qui_ne_solde_plus_rouvre_la_saisie():
    """La saisie terminée par ce bulletin revient au recalcul ; si le nouveau
    net ne permet plus de solder, elle reprend le mois suivant."""
    bulletin, ecritures, _ = _enrichir(
        2500.0,
        [_saisie(montant_total=1000, status="closed")],
        deja_retenu={"saisie-1": 900},
    )
    assert bulletin["retenues_saisies"]["total_preleve"] == 100.0
    ecritures.depot.update.assert_not_called()

    bulletin, ecritures, _ = _enrichir(
        700.0,
        [_saisie(montant_total=1000, status="closed")],
        deja_retenu={"saisie-1": 900},
    )
    assert bulletin["retenues_saisies"]["total_preleve"] < 100.0
    ecritures.depot.update.assert_called_once_with("saisie-1", {"status": "active"})


def test_un_apercu_n_ecrit_pas_le_statut():
    _, ecritures, _ = _enrichir(
        2500.0, [_saisie(montant_total=1000)], deja_retenu={"saisie-1": 950}, payslip_id=None
    )
    ecritures.depot.update.assert_not_called()


# ----- Lecture des saisies du bulletin -----


class _Table:
    def __init__(self, lignes):
        self.lignes = lignes
        self.filtres = []

    def __getattr__(self, nom):
        def _filtre(*args, **kwargs):
            self.filtres.append((nom, args))
            return self

        return _filtre

    def execute(self):
        return MagicMock(data=self.lignes)


def test_le_bulletin_qui_a_solde_la_saisie_la_retrouve_au_recalcul():
    """Terminée par ce bulletin : sans elle, recalculer le bulletin perdait la
    dernière retenue (la saisie n'est plus « active »)."""
    tables = {
        "salary_seizures": [
            _Table([_saisie(id="active-1")]),
            _Table(
                [
                    _saisie(id="soldee-1", status="closed", montant_total=1000),
                    # Terminée à la main avant d'être soldée : reste dehors.
                    _saisie(id="arretee-1", status="closed", montant_total=1000),
                    # Terminée sans montant total : comportement d'avant.
                    _saisie(id="sans-total", status="closed", montant_total=None),
                ]
            ),
        ],
        "salary_seizure_deductions": [
            _Table(
                [
                    {"seizure_id": "soldee-1"},
                    {"seizure_id": "arretee-1"},
                    {"seizure_id": "sans-total"},
                ]
            ),
        ],
    }
    fake = MagicMock()
    fake.table.side_effect = lambda nom: tables[nom].pop(0)
    with (
        patch.object(infra_queries, "supabase", fake),
        patch.object(
            infra_queries,
            "total_retenu_par_saisie",
            return_value={"soldee-1": Decimal("1000"), "arretee-1": Decimal("400")},
        ),
    ):
        saisies = infra_queries.get_seizures_for_period("e1", 2026, 10, payslip_id="bulletin-1")
    assert [s["id"] for s in saisies] == ["active-1", "soldee-1"]


def test_sans_bulletin_seules_les_saisies_actives():
    fake = MagicMock()
    fake.table.return_value = _Table([_saisie(id="active-1")])
    with patch.object(infra_queries, "supabase", fake):
        saisies = infra_queries.get_seizures_for_period("e1", 2026, 10)
    assert [s["id"] for s in saisies] == ["active-1"]
    assert fake.table.call_count == 1


# ----- Réponse API et commandes -----


def _ligne(**champs) -> dict:
    ligne = {
        "id": "saisie-1",
        "company_id": "co",
        "employee_id": "e1",
        "type": "saisie_arret",
        "creditor_name": "Créancier fictif SARL",
        "amount": Decimal("300"),
        "calculation_mode": "fixe",
        "start_date": "2026-07-01",
        "status": "active",
        "priority": 4,
        "created_at": "2026-10-01T08:00:00",
        "updated_at": "2026-10-01T08:00:00",
    }
    ligne.update(champs)
    return ligne


def test_le_detail_expose_le_reste_du():
    with (
        patch.object(service, "seizure_repository") as depot,
        patch.object(
            service, "total_retenu_par_saisie", return_value={"saisie-1": Decimal("400")}
        ),
    ):
        depot.get_by_id.return_value = _ligne(montant_total=Decimal("1000"))
        detail = service.get_salary_seizure("saisie-1")
    rendu = SalarySeizure(**detail).model_dump(mode="json")
    assert rendu["montant_total"] == 1000.0
    assert rendu["total_retenu"] == 400.0
    assert rendu["reste_du"] == 600.0


def test_la_liste_expose_le_reste_du_en_une_lecture():
    with (
        patch.object(service, "list_seizures_with_employee") as lister,
        patch.object(
            service, "total_retenu_par_saisie", return_value={"s-total": Decimal("250")}
        ) as totaux,
    ):
        lister.return_value = [
            _ligne(id="s-total", montant_total=Decimal("1000")),
            _ligne(id="s-sans"),
        ]
        lignes = service.get_salary_seizures()
    totaux.assert_called_once_with(["s-total"])
    assert lignes[0]["reste_du"] == Decimal("750.00")
    assert lignes[1].get("reste_du") is None
    assert SalarySeizure(**lignes[1]).model_dump(mode="json")["reste_du"] is None


def test_sans_montant_total_aucune_lecture_de_l_historique():
    with (
        patch.object(service, "seizure_repository") as depot,
        patch.object(service, "total_retenu_par_saisie") as totaux,
    ):
        depot.get_by_id.return_value = _ligne()
        service.get_salary_seizure("saisie-1")
    totaux.assert_not_called()


def test_la_creation_enregistre_le_montant_total():
    from app.modules.saisies_avances.schemas.requests import SalarySeizureCreate

    donnees = SalarySeizureCreate(
        employee_id="e1",
        type="saisie_arret",
        creditor_name="Créancier fictif SARL",
        amount=Decimal("300"),
        calculation_mode="fixe",
        start_date="2026-07-01",
        montant_total=Decimal("1200.50"),
    )
    with (
        patch.object(service, "employee_company_provider") as societe,
        patch.object(service, "seizure_repository") as depot,
        patch.object(service, "total_retenu_par_saisie", return_value={}),
    ):
        societe.get_company_id.return_value = "co"
        depot.create.side_effect = lambda d: _ligne(**{k: v for k, v in d.items() if k in ("montant_total",)})
        service.create_salary_seizure(donnees, "u1")
    assert depot.create.call_args.args[0]["montant_total"] == 1200.5


def test_la_creation_sans_montant_total_n_ecrit_pas_la_colonne():
    from app.modules.saisies_avances.schemas.requests import SalarySeizureCreate

    donnees = SalarySeizureCreate(
        employee_id="e1",
        type="saisie_arret",
        creditor_name="Créancier fictif SARL",
        start_date="2026-07-01",
    )
    with (
        patch.object(service, "employee_company_provider") as societe,
        patch.object(service, "seizure_repository") as depot,
    ):
        societe.get_company_id.return_value = "co"
        depot.create.return_value = _ligne()
        service.create_salary_seizure(donnees, "u1")
    assert "montant_total" not in depot.create.call_args.args[0]


def test_la_mensualite_et_le_total_se_modifient():
    with (
        patch.object(service, "seizure_repository") as depot,
        patch.object(service, "total_retenu_par_saisie", return_value={}),
    ):
        depot.update.return_value = _ligne(amount=Decimal("250"), montant_total=Decimal("900"))
        service.update_salary_seizure(
            "saisie-1", SalarySeizureUpdate(amount=Decimal("250"), montant_total=Decimal("900"))
        )
    assert depot.update.call_args.args[1] == {"amount": 250.0, "montant_total": 900.0}


def test_le_montant_total_s_efface_explicitement():
    with patch.object(service, "seizure_repository") as depot:
        depot.update.return_value = _ligne()
        service.update_salary_seizure("saisie-1", SalarySeizureUpdate(montant_total=None))
    assert depot.update.call_args.args[1] == {"montant_total": None}


def test_un_montant_total_negatif_est_refuse():
    with pytest.raises(Exception):
        SalarySeizureUpdate(montant_total=Decimal("-1"))
