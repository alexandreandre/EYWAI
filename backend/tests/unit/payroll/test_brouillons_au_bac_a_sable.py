"""Un brouillon dont seul le planning d'à côté a changé est d'abord recalculé au bac à sable.

Rejeu final C3 (13/10/2026) : poser ou changer le calendrier d'octobre faisait
passer « À recalculer » le bulletin de septembre, et la fenêtre « Valider les
bulletins prêts » ajoutait « Septembre 2026 est à recalculer… ». Le calcul de
septembre ne changeait pas : l'empreinte hache tout le planning de M-1, M et
M+1, le calcul n'en lit qu'une petite partie (les jours de la semaine à cheval,
et presque toujours sans effet). Le lot 42 réglait le cas d'un validé ; un
brouillon restait « À recalculer » à tort.

Choix du lot 43 : étendre aux brouillons la vérification au bac à sable, mais
seulement quand le changement est hors du mois. Le bulletin garde une partie de
plus, `planning_du_mois` : le prévu du mois civil et de la fenêtre des
variables, le réel de la fenêtre, les absences qui y touchent — ce que le calcul
lit à coup sûr. Si elle a changé, le brouillon est « À recalculer » tout de suite,
comme avant (le cas courant : la gestionnaire corrige son mois). Si seuls le
planning ou les absences d'à côté ont changé, il est recalculé au bac à sable :
identique au centime, il reste à jour ; sinon « À recalculer » en disant ce qui
change. Resserrer l'empreinte aux jours lus aurait été plus léger, mais un oubli
aurait laissé un bulletin faux « à jour » sans un mot (le repli sur le planning
d'un mois sans pointage, par exemple, fait dépendre la semaine à cheval de tout
le mois suivant) : le bac à sable, lui, calcule exactement.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.payroll.application import empreinte_entrees_service as service
from app.modules.payroll.application.empreinte_entrees_service import (
    EtatDuBulletin,
    VerdictBacASable,
)
from tests.unit.payroll.test_valides_au_bac_a_sable import (  # noqa: F401 — fixtures
    CALENDRIERS,
    JUIN_POSE,
    _lectures,
    _lire,
    _lire_puis_verifier,
    _mai,
    _verdicts_oublies,
    arriere_plan,
)

pytestmark = pytest.mark.unit

#: Fenêtre des variables de mai pour la société des tests (règle par défaut) :
#: du 20 avril au 24 mai.


def _avec(mois: tuple[int, int], *, prevu=None, reel=None):
    """Les calendriers de mai, un mois changé (prévu ou réel ajoutés)."""
    ligne = CALENDRIERS.get(mois) or {
        "planned_calendar": {"calendrier_prevu": []},
        "actual_hours": {"calendrier_reel": []},
    }
    nouvelle = {
        **ligne,
        "planned_calendar": {
            "calendrier_prevu": list(ligne["planned_calendar"]["calendrier_prevu"]) + list(prevu or [])
        },
        "actual_hours": {
            "calendrier_reel": list(ligne["actual_hours"]["calendrier_reel"]) + list(reel or [])
        },
    }
    return {**CALENDRIERS, mois: nouvelle}


def _brouillon():
    return _mai(status="brouillon")


# --- Le cas du rejeu : le mois suivant posé, le brouillon reste juste ------------


def test_un_brouillon_dont_seul_le_mois_suivant_change_est_verifie_au_bac_a_sable(arriere_plan):
    avant, apres, verifier, poser = _lire_puis_verifier(
        arriere_plan,
        _lectures(calendriers=JUIN_POSE),
        _brouillon(),
        verdict=VerdictBacASable(identique=True),
    )
    # Le temps du calcul : ni « À recalculer » ni à jour.
    assert avant["a_verifier"] is True
    assert avant["a_recalculer"] is None
    # Identique au centime : à jour, ses empreintes reposées sans changer son statut.
    assert apres["a_verifier"] is False
    assert apres["a_recalculer"] is False
    assert apres["raison_a_recalculer"] is None
    assert verifier.call_args.args[:3] == ("e1", 2026, 5)
    poser.assert_called_once()
    assert poser.call_args.args[0] == "b-mai"
    assert poser.call_args.kwargs["statut"] == "brouillon"


def test_un_brouillon_que_le_mois_suivant_change_vraiment_dit_ce_qui_change(arriere_plan):
    ecart = "Martine l'a recalculé sans rien enregistrer : le net à payer passerait de 1 500,00 € à 1 512,00 €."
    _, apres, _, poser = _lire_puis_verifier(
        arriere_plan,
        _lectures(calendriers=JUIN_POSE),
        _brouillon(),
        verdict=VerdictBacASable(identique=False, ecart=ecart),
    )
    assert apres["a_recalculer"] is True
    assert apres["raison_a_recalculer"] == (
        "Le planning a changé depuis le calcul : recalculez avant de valider. " + ecart
    )
    poser.assert_not_called()


def test_sans_verdict_le_brouillon_est_a_recalculer_comme_avant(arriere_plan):
    _, apres, _, _ = _lire_puis_verifier(
        arriere_plan, _lectures(calendriers=JUIN_POSE), _brouillon(), verdict=None
    )
    assert apres["a_recalculer"] is True
    assert apres["raison_a_recalculer"].startswith("Le planning a changé")


def test_un_jour_d_avril_hors_de_la_fenetre_est_verifie_au_bac_a_sable(arriere_plan):
    lectures = _lectures(calendriers=_avec((2026, 4), prevu=[{"jour": 6, "type": "conges_payes"}]))
    ligne, _, _ = _lire(lectures, _brouillon(), verdict=None)
    assert ligne["a_verifier"] is True
    assert len(arriere_plan.taches) == 1


def test_des_pointages_du_mois_apres_la_fenetre_sont_verifies_au_bac_a_sable(arriere_plan):
    """Société à fenêtre décalée : les heures du 28 mai comptent pour juin."""
    lectures = _lectures(
        calendriers=_avec((2026, 5), reel=[{"jour": 28, "type": "travail", "heures_faites": 9}])
    )
    ligne, _, _ = _lire(lectures, _brouillon(), verdict=None)
    assert ligne["a_verifier"] is True
    assert len(arriere_plan.taches) == 1


def test_une_absence_du_mois_suivant_est_verifiee_au_bac_a_sable(arriere_plan):
    absences = [{"type": "conge_paye", "selected_days": ["2026-06-02"]}]
    ligne, _, _ = _lire(_lectures(absences=absences), _brouillon(), verdict=None)
    assert ligne["a_verifier"] is True
    assert len(arriere_plan.taches) == 1


# --- Ce qui reste « À recalculer » tout de suite -----------------------------------


@pytest.mark.parametrize(
    "calendriers",
    [
        # Le réel du mois change (la gestionnaire corrige son mois).
        _avec((2026, 5), reel=[{"jour": 13, "type": "travail", "heures_faites": 8}]),
        # Un congé posé au prévu du mois, même après la fenêtre (mois civil).
        _avec((2026, 5), prevu=[{"jour": 28, "type": "conges_payes"}]),
        # Un jour d'avril dans la fenêtre des variables de mai.
        _avec((2026, 4), reel=[{"jour": 27, "type": "travail", "heures_faites": 9}]),
    ],
    ids=["reel-du-mois", "prevu-du-mois", "fenetre-en-avril"],
)
def test_un_brouillon_dont_le_mois_ou_sa_fenetre_change_est_a_recalculer_tout_de_suite(
    arriere_plan, calendriers
):
    ligne, verifier, _ = _lire(_lectures(calendriers=calendriers), _brouillon(), verdict=None)
    assert arriere_plan.taches == []
    verifier.assert_not_called()
    assert ligne["a_verifier"] is False
    assert ligne["a_recalculer"] is True
    assert ligne["raison_a_recalculer"].startswith("Le planning a changé")


def test_une_absence_du_mois_rend_le_brouillon_a_recalculer_tout_de_suite(arriere_plan):
    absences = [{"type": "conge_paye", "selected_days": ["2026-05-05"]}]
    ligne, _, _ = _lire(_lectures(absences=absences), _brouillon(), verdict=None)
    assert arriere_plan.taches == []
    assert ligne["a_recalculer"] is True


def test_le_mois_suivant_et_le_mois_change_ensemble_le_brouillon_est_a_recalculer(arriere_plan):
    calendriers = {
        **JUIN_POSE,
        (2026, 5): _avec((2026, 5), reel=[{"jour": 13, "type": "travail", "heures_faites": 8}])[(2026, 5)],
    }
    ligne, _, _ = _lire(_lectures(calendriers=calendriers), _brouillon(), verdict=None)
    assert arriere_plan.taches == []
    assert ligne["a_recalculer"] is True


def test_un_brouillon_calcule_avant_cette_partie_reste_a_recalculer_comme_avant(arriere_plan):
    """Sans `planning_du_mois` (calculé avant le lot 43), on ne sait pas où est le
    changement : la règle d'avant, « À recalculer » tout de suite."""
    ancien = _brouillon()
    ancien["empreinte_complementaire"] = {
        nom: valeur
        for nom, valeur in ancien["empreinte_complementaire"].items()
        if nom != "planning_du_mois"
    }
    ligne, _, _ = _lire(_lectures(calendriers=JUIN_POSE), ancien, verdict=None)
    assert arriere_plan.taches == []
    assert ligne["a_recalculer"] is True


def test_la_generation_pose_la_partie_du_planning_du_mois():
    assert "planning_du_mois" in _brouillon()["empreinte_complementaire"]


# --- Valider un brouillon en cours de vérification ---------------------------------


def test_un_brouillon_en_verification_ne_se_valide_pas_encore():
    """Le verdict arrive en quelques secondes : la validation attend, et le dit."""
    from app.modules.payslips.application import comparison_service as svc

    detail = {
        "id": "p-1",
        "employee_id": "emp-1",
        "company_id": "comp-1",
        "year": 2026,
        "month": 9,
        "status": "brouillon",
        "payslip_data": {"net_a_payer": 100},
    }
    with (
        patch.object(svc, "payslip_meta_reader") as meta,
        patch.object(svc, "_ensure_edit_meta"),
        patch.object(svc, "get_payslip_details", return_value=detail),
        patch.object(
            svc,
            "_etat_actuel_du_bulletin",
            return_value=EtatDuBulletin(entrees_changees=None, verification_en_cours=True),
        ),
        patch.object(svc, "mark_payslip_validated") as marquer,
        pytest.raises(svc.PayslipBadRequestError) as exc,
    ):
        meta.get_payslip_meta.return_value = {"id": "p-1"}
        svc.validate_payslip_for_user("p-1", MagicMock())
    marquer.assert_not_called()
    assert str(exc.value) == (
        "Martine vérifie encore ce bulletin : le planning a changé depuis son calcul, et "
        "elle le recalcule sans rien enregistrer pour savoir si un montant change. "
        "Réessayez dans quelques secondes."
    )


# --- Reposer les empreintes d'un brouillon ------------------------------------------


class _Payslips:
    """La table `payslips` d'un seul bulletin, qui note les filtres de l'écriture."""

    def __init__(self, ligne):
        self.ligne = ligne
        self.ecrit = None
        self.filtres_ecriture: list = []
        self._maj = None

    def table(self, nom):
        assert nom == "payslips"
        return self

    def select(self, *_a, **_k):
        self._maj = None
        return self

    def update(self, valeurs):
        self._maj = valeurs
        return self

    def eq(self, colonne, valeur):
        if self._maj is not None:
            self.filtres_ecriture.append((colonne, valeur))
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        from types import SimpleNamespace

        if self._maj is not None:
            self.ecrit = self._maj
            return SimpleNamespace(data=[{**self.ligne, **self._maj, "updated_at": "T2"}])
        return SimpleNamespace(data=[self.ligne])


def test_les_empreintes_d_un_brouillon_se_reposent_s_il_n_a_pas_bouge():
    from app.modules.payroll.infrastructure import empreinte_entrees_queries as q

    ligne = {
        "status": "brouillon",
        "updated_at": "2026-10-13T10:00:00.123456+00:00",
        "payslip_data": {"net_a_payer": 1500.0, "parametres": {"empreinte_entrees": "a"}},
    }
    base = _Payslips(ligne)
    with patch.object(q, "supabase", base):
        rendu = q.poser_empreintes_verifiees("b-1", {"empreinte_entrees": "b"}, "a", statut="brouillon")
    assert rendu == "T2"
    assert base.ecrit == {"payslip_data": {"net_a_payer": 1500.0, "parametres": {"empreinte_entrees": "b"}}}
    # Recalculé ou validé entre la lecture et l'écriture : rien n'est écrasé.
    assert ("status", "brouillon") in base.filtres_ecriture
    assert ("updated_at", "2026-10-13T10:00:00.123456+00:00") in base.filtres_ecriture


def test_un_brouillon_valide_entre_temps_n_est_pas_touche():
    from app.modules.payroll.infrastructure import empreinte_entrees_queries as q

    ligne = {"status": "valide", "payslip_data": {"parametres": {"empreinte_entrees": "a"}}}
    base = _Payslips(ligne)
    with patch.object(q, "supabase", base):
        assert q.poser_empreintes_verifiees("b-1", {}, "a", statut="brouillon") is None
    assert base.ecrit is None


def test_un_brouillon_n_est_jamais_verifie_pour_sa_fiche():
    """La fiche d'un brouillon le périme tout de suite : c'est elle qu'il imprime."""
    etat = service._etats_par_mois(
        _lectures(employee={**_lectures().employee, "salaire_de_base": {"valeur": 2100}}),
        [_brouillon()],
    )[(2026, 5)]
    assert etat.a_recalculer is True
    assert etat.seulement_hors_du_mois is False
