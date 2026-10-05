"""Valider les bulletins prêts du mois en une fois (revue du 05/10).

Chaque bulletin passe par la règle de validation existante
(`validate_payslip_for_user`) : un bulletin à recalculer ou en alerte critique
n'est jamais validé. Un refus n'arrête pas le lot ; il revient avec sa raison,
dite pour la gestionnaire.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.modules.payslips.application.comparison_service import (
    REFUS_INATTENDU,
    REFUS_INTROUVABLE,
    valider_plusieurs_bulletins,
)
from app.modules.payslips.application.dto import (
    PayslipBadRequestError,
    PayslipCriticalActiveError,
    PayslipNotFoundError,
)


def _valideur(echecs: dict[str, Exception]):
    appels: list[str] = []

    def valider_un(payslip_id: str) -> None:
        appels.append(payslip_id)
        if payslip_id in echecs:
            raise echecs[payslip_id]

    return valider_un, appels


def test_tous_valides_sans_refus():
    valider_un, appels = _valideur({})
    resultat = valider_plusieurs_bulletins(["a", "b"], valider_un)
    assert resultat == {"valides": ["a", "b"], "refus": []}
    assert appels == ["a", "b"]


def test_une_alerte_critique_refuse_ce_bulletin_et_le_lot_continue():
    alerte = PayslipCriticalActiveError(
        [{"rule_id": "R03", "message": "Le net à payer a varié de 14.0% (seuil critique > 10 %).", "field": "net_a_payer"}]
    )
    valider_un, appels = _valideur({"a": alerte})
    resultat = valider_plusieurs_bulletins(["a", "b"], valider_un)
    assert resultat["valides"] == ["b"]
    assert appels == ["a", "b"]
    (refus,) = resultat["refus"]
    assert refus["payslip_id"] == "a"
    assert "Le net à payer a varié de 14.0%" in refus["raison"]
    assert "acquitt" in refus["raison"]


def test_un_bulletin_a_recalculer_est_refuse_avec_ce_qui_a_change():
    valider_un, _ = _valideur({"a": PayslipBadRequestError("La mutuelle a changé depuis le calcul.")})
    resultat = valider_plusieurs_bulletins(["a"], valider_un)
    assert resultat == {
        "valides": [],
        "refus": [{"payslip_id": "a", "raison": "La mutuelle a changé depuis le calcul."}],
    }


def test_un_bulletin_disparu_est_dit_introuvable():
    valider_un, _ = _valideur({"a": PayslipNotFoundError("Bulletin non trouvé")})
    resultat = valider_plusieurs_bulletins(["a"], valider_un)
    assert resultat["refus"] == [{"payslip_id": "a", "raison": REFUS_INTROUVABLE}]


def test_une_erreur_inattendue_ne_valide_pas_et_n_arrete_pas_le_lot():
    valider_un, _ = _valideur({"a": RuntimeError("base injoignable")})
    resultat = valider_plusieurs_bulletins(["a", "b"], valider_un)
    assert resultat["valides"] == ["b"]
    assert resultat["refus"] == [{"payslip_id": "a", "raison": REFUS_INATTENDU}]


def test_un_meme_bulletin_n_est_valide_qu_une_fois():
    valider_un, appels = _valideur({})
    resultat = valider_plusieurs_bulletins(["a", "a", "b"], valider_un)
    assert resultat["valides"] == ["a", "b"]
    assert appels == ["a", "b"]


# --- La route ----------------------------------------------------------------


def _appeler_la_route(ids, *, perimetre, valider):
    from app.modules.payslips.api import router as module
    from app.modules.payslips.schemas import ValidationGroupeeRequest

    utilisateur = SimpleNamespace(id="u-1", email="rh@exemple.fr", active_company_id="c-1")
    requete = SimpleNamespace(client=None)
    with patch.object(module, "_to_user_context", return_value=SimpleNamespace()), patch.object(
        module, "_require_payslip_scope", side_effect=perimetre
    ), patch.object(module, "validate_payslip_for_user", side_effect=valider) as validation, patch.object(
        module, "log_audit_event"
    ) as audit, patch.object(module, "trigger_webhook_event") as webhook:
        reponse = module.validate_payslips_batch_route(
            ValidationGroupeeRequest(payslip_ids=ids), requete, utilisateur
        )
    return reponse, validation, audit, webhook


def test_la_route_valide_trace_et_previent_comme_la_validation_d_un_bulletin():
    reponse, validation, audit, webhook = _appeler_la_route(
        ["a", "b"],
        perimetre=lambda user, pid, perm: {"company_id": "c-1", "employee_id": f"e-{pid}"},
        valider=lambda pid, ctx: None,
    )
    assert reponse == {"valides": ["a", "b"], "refus": []}
    assert [c.args[0] for c in validation.call_args_list] == ["a", "b"]
    assert [c.kwargs["action"] for c in audit.call_args_list] == ["payslip.validate"] * 2
    assert [c.args[1] for c in webhook.call_args_list] == ["payslip.validated"] * 2


def test_la_route_refuse_un_bulletin_hors_perimetre_sans_le_valider():
    def perimetre(user, pid, perm):
        if pid == "a":
            raise HTTPException(status_code=404, detail="Bulletin introuvable")
        return {"company_id": "c-1", "employee_id": "e-b"}

    reponse, validation, audit, _ = _appeler_la_route(
        ["a", "b"], perimetre=perimetre, valider=lambda pid, ctx: None
    )
    assert reponse["valides"] == ["b"]
    assert reponse["refus"] == [{"payslip_id": "a", "raison": REFUS_INTROUVABLE}]
    assert [c.args[0] for c in validation.call_args_list] == ["b"]
    assert len(audit.call_args_list) == 1


def test_la_route_ne_trace_pas_un_bulletin_refuse():
    def valider(pid, ctx):
        raise PayslipBadRequestError("Le planning a changé depuis le calcul.")

    reponse, _, audit, webhook = _appeler_la_route(
        ["a"],
        perimetre=lambda user, pid, perm: {"company_id": "c-1", "employee_id": "e-a"},
        valider=valider,
    )
    assert reponse["refus"] == [{"payslip_id": "a", "raison": "Le planning a changé depuis le calcul."}]
    audit.assert_not_called()
    webhook.assert_not_called()
