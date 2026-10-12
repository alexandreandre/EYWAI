"""Le calcul inverse (net → brut) compte comme le bulletin. [rejeu G.9]

Relevé (rejeu du 11/10/2026, page « Simulation de Paie », onglet « Calcul
Inverse ») : pour un net de 1 800 € et un prélèvement de 2,1 %, sans salarié,
le résultat donnait un brut de 2 343,05 € et un coût employeur de 3 145,45 €,
rejoué au centime sous piège à écritures. Trois anomalies, confirmées dans le
code :

- la réponse portait « janvier 2025 » : l'écran envoie le mois et l'année
  (octobre 2026), la route ne les transmettait pas et le moteur du calcul
  inverse forçait `month=1, year=2025` ;
- le détail comptait la « Contribution CPF des titulaires de CDD » (1 %) sans
  contrat précisé : le calcul inverse passait par un bulletin simplifié qui
  parcourt tout le barème des cotisations, sans le filtre `est_cdd` du moteur ;
- aucune ligne de réduction générale : ce bulletin simplifié n'en calcule pas,
  quand le bulletin d'essai (moteur complet) en porte une.

Attendu : le calcul inverse fait tourner le moteur du bulletin d'essai
(`run_simulation_bulletin_pipeline`), sur la période choisie à l'écran, avec
les barèmes chargés (refus s'ils sont d'une année passée, comme un bulletin) ;
sans type de contrat, un CDI, et la réponse le dit.
"""

from __future__ import annotations

import copy

import pytest

from app.modules.payroll.application import simulation_queries as sq
from app.modules.payroll.engine.baremes_loader import BaremesDUneAnneePassee
from app.modules.payroll.engine.calcul_inverse import calculer_brut_depuis_net
from app.modules.payroll.engine.contexte import ChargerContexte
from app.modules.payroll.engine.simulation_pipeline import run_simulation_bulletin_pipeline
from tests.unit.payroll.fixtures.baremes_snapshot import (
    baremes_snapshot,
    entreprise_snapshot,
)

pytestmark = pytest.mark.unit

CPF_CDD = {
    "id": "cpf_cdd",
    "libelle": "Contribution CPF des titulaires de CDD",
    "base": "brut",
    "salarial": None,
    "patronal": 0.01,
}


def _baremes() -> dict:
    baremes = copy.deepcopy(baremes_snapshot())
    baremes["cotisations"]["cotisations"].append(dict(CPF_CDD))
    baremes["smic"]["annee"] = 2026
    return baremes


def _salarie(**extra) -> dict:
    # Ce que `manual_employee_payload` construit pour l'écran : non-cadre, 35 h,
    # prélèvement de 2,1 %, aucun type de contrat.
    return {
        "id": "manual",
        "first_name": "Simulation",
        "last_name": "Manuelle",
        "statut": "Non-cadre",
        "duree_hebdomadaire": 35.0,
        "salaire_base": 0.0,
        "taux_prelevement_source": 2.1,
        "type_contrat": "",
        "date_entree": "",
        **extra,
    }


def _inverse(salarie=None, *, baremes=None, month=10, year=2026) -> dict:
    return calculer_brut_depuis_net(
        net_cible=1800.0,
        type_net="net_a_payer",
        employee_data=salarie or _salarie(),
        company_data={"entreprise": entreprise_snapshot(effectif=10)},
        baremes=baremes or _baremes(),
        calendrier={},
        saisies={},
        options={},
        month=month,
        year=year,
    )


def _lignes(bulletin: dict) -> list[dict]:
    s = bulletin["structure_cotisations"]
    return (
        list(s.get("bloc_principales") or [])
        + list(s.get("bloc_allegements") or [])
        + list((s.get("bloc_autres_contributions") or {}).get("lignes") or [])
        + list(s.get("bloc_csg_non_deductible") or [])
    )


def _cpf(bulletin: dict) -> list[dict]:
    return [
        l
        for l in _lignes(bulletin)
        if "CPF" in (l.get("libelle") or "") and abs(l.get("montant_patronal") or 0) > 0
    ]


def _reduction(bulletin: dict) -> list[dict]:
    return [
        l for l in _lignes(bulletin) if "réduction générale" in (l.get("libelle") or "").lower()
    ]


def test_le_calcul_inverse_compte_sur_la_periode_choisie_a_l_ecran():
    resultat = _inverse(month=10, year=2026)

    assert resultat["bulletin_complet"]["en_tete"]["periode"] == "Octobre 2026"
    assert (resultat["month"], resultat["year"]) == (10, 2026)


def test_sans_type_de_contrat_un_cdi_sans_contribution_cpf_des_cdd():
    resultat = _inverse()

    assert _cpf(resultat["bulletin_complet"]) == []
    assert resultat["type_contrat"] == "CDI"
    assert resultat["type_contrat_par_defaut"] is True


def test_un_cdd_paie_la_contribution_cpf_des_cdd():
    resultat = _inverse(_salarie(type_contrat="CDD"))

    (ligne,) = _cpf(resultat["bulletin_complet"])
    assert ligne["montant_patronal"] == pytest.approx(round(resultat["brut_calcule"] * 0.01, 2))
    assert resultat["type_contrat"] == "CDD"
    assert resultat["type_contrat_par_defaut"] is False


def test_la_reduction_generale_est_celle_du_moteur_du_bulletin():
    resultat = _inverse()
    bulletin = resultat["bulletin_complet"]

    (ligne,) = _reduction(bulletin)
    assert ligne["montant_patronal"] < 0

    # Le même salarié, au brut trouvé, dans le moteur du bulletin d'essai.
    contexte = ChargerContexte(
        _salarie(type_contrat="CDI", salaire_base=resultat["brut_calcule"]),
        {"entreprise": entreprise_snapshot(effectif=10)},
        _baremes(),
    )
    attendu = run_simulation_bulletin_pipeline(contexte, month=10, year=2026)
    (ligne_attendue,) = _reduction(attendu)
    assert ligne["montant_patronal"] == pytest.approx(ligne_attendue["montant_patronal"])
    assert resultat["cout_employeur"] == pytest.approx(
        attendu["pied_de_page"]["cout_total_employeur"]
    )
    assert resultat["brut_calcule"] == pytest.approx(attendu["salaire_brut"])


def test_le_net_obtenu_est_le_net_cible_a_l_euro_pres():
    resultat = _inverse()

    assert resultat["convergence"] is True
    assert abs(resultat["net_obtenu"] - 1800.0) < 1.0
    assert resultat["net_obtenu"] == pytest.approx(resultat["bulletin_complet"]["net_a_payer"])


def test_des_baremes_d_une_annee_passee_sont_refuses_comme_pour_un_bulletin():
    with pytest.raises(BaremesDUneAnneePassee):
        _inverse(year=2027)


def test_la_route_transmet_le_mois_et_l_annee_de_l_ecran(monkeypatch):
    recu: dict = {}
    monkeypatch.setattr(sq, "load_company", lambda _cid: {"id": "soc", "name": "Société"})
    monkeypatch.setattr(sq, "load_baremes", lambda: {})
    monkeypatch.setattr(sq, "company_to_payroll_payload", lambda *_a, **_k: {})

    def commande(**kwargs):
        recu.update(kwargs)
        return {}

    monkeypatch.setattr(sq.simulation_commands, "run_reverse_calculation", commande)
    sq.run_reverse_calculation_for_company(
        company_id="soc",
        employee_id=None,
        net_target=1800.0,
        net_type="net_a_payer",
        options={"manual_params": {"statut": "Non-cadre"}},
        month=10,
        year=2026,
    )

    assert (recu["month"], recu["year"]) == (10, 2026)


def test_le_routeur_passe_la_periode_de_la_requete(monkeypatch):
    from app.modules.payroll.api import router as routeur

    recu: dict = {}
    monkeypatch.setattr(routeur, "_require_rh_or_admin", lambda _u: "soc")
    monkeypatch.setattr(
        routeur.simulation_queries,
        "run_reverse_calculation_for_company",
        lambda **kwargs: recu.update(kwargs) or {},
    )
    corps = routeur.ReverseCalculationRequest(
        employee_id=None, net_target=1800, net_type="net_a_payer", month=10, year=2026
    )
    routeur.reverse_calculation(corps, current_user=object())

    assert (recu["month"], recu["year"]) == (10, 2026)
