"""Congé parental d'éducation : défauts de la relecture du 26/11 (L11b).

1. Mois civil entièrement en congé parental après un sans solde que la fenêtre
   des variables a repoussé du mois précédent : ces jours ne sont plus absorbés
   en silence par la retenue du mois entier (ligne et alerte).
2. Premier mois au mois civil : les jours de congé parental entre la fin de la
   fenêtre du bulletin précédent et la fin de son mois ne sont retenus nulle
   part : alerte.
3. Import DSN d'un 632 : requalification des sans solde non typés, idempotence
   d'un réimport, alerte de fin anticipée.
4. Ancienneté : seuls les jours de congé postérieurs au départ de l'ancienneté.
5. Tranche 1 : un cumul appliqué négatif n'est rattrapé ni sur un mois sans
   salaire ni sur le petit mois qui suit.
Plus : préavis par l'aperçu réel, indemnité de rupture, plafond d'un jour
repassé en travail.
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest

from app.shared.domain.conge_parental import SOUS_TYPE_CONGE_PARENTAL, jours_d_anciennete_neutralises
from tests.unit.base_en_memoire import BaseEnMemoire

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _jours(d0: date, d1: date, **meta) -> list[dict]:
    out, d = [], d0
    while d <= d1:
        if d.weekday() < 5:
            out.append({"date_complete": d.isoformat(), "type": "absence_non_remuneree", "heures": 0.0, **meta})
        d += timedelta(days=1)
    return out


def _conge(debut: str, fin: str, **k) -> dict:
    d0, d1 = date.fromisoformat(debut), date.fromisoformat(fin)
    return {"type": "sans_solde", "event_subtype": SOUS_TYPE_CONGE_PARENTAL, "status": "validated",
            "selected_days": [(d0 + timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)], **k}


# --- 1 -----------------------------------------------------------------------

def _prevus_d_un_mois(annee: int, mois: int, type_ouvre: str) -> list[dict]:
    import calendar as _cal

    return [
        {"annee": annee, "mois": mois, "jour": j,
         "type": type_ouvre if date(annee, mois, j).weekday() < 5 else "weekend"}
        for j in range(1, _cal.monthrange(annee, mois)[1] + 1)
    ]


_NOVEMBRE_MARTINE = {"existe": True, "fin_variables": "2026-11-22", "mois_entier": False}


def _decembre(
    monkeypatch, novembre_au_planning: str | None, duree=35.0, salaire=1870.83,
    bulletin_novembre: dict | None = _NOVEMBRE_MARTINE,
):
    from app.modules.payroll.engine import calcul_brut as cb

    monkeypatch.setattr(cb, "coefficient_horaire_reel", lambda *_: 1.0)
    periode = {"debut": "2026-12-01", "fin": "2027-03-31"}
    calendrier = _jours(date(2026, 11, 23), date(2026, 11, 30)) + _jours(
        date(2026, 12, 1), date(2026, 12, 31), motif_absence=SOUS_TYPE_CONGE_PARENTAL, periode_absence=periode
    )
    extra = {"specificites_extra": {"salaire_hors_hs_structurelles": True}} if duree > 35 else {}
    contexte = build_test_contexte(salaire_base=salaire, duree_hebdo=duree, date_entree="2020-01-06", **extra)
    contexte.alertes_baremes = []
    contexte.bulletin_precedent = bulletin_novembre
    prevus = (
        _prevus_d_un_mois(2026, 11, novembre_au_planning) if novembre_au_planning else None
    )
    r = cb.calculer_salaire_brut(
        contexte, calendrier, date(2026, 12, 1), date(2026, 12, 31), [],
        nb_jours_travail_planifies=0,
        date_debut_variables=date(2026, 11, 23), date_fin_variables=date(2026, 12, 22),
        jours_prevus=prevus,
    )
    return r, contexte


def test_novembre_paye_les_jours_repousses_non_retenus_sont_rendus_et_signales(monkeypatch):
    r, contexte = _decembre(monkeypatch, "travail")
    lignes = {l["libelle"]: l for l in r["lignes_composants_brut"]}
    ligne = lignes["Absences du mois précédent non retenues (salaire du mois suspendu)"]
    retenue_novembre = sum(
        l["perte"] for l in r["lignes_composants_brut"] if l["libelle"].startswith("Absence non rémunérée du")
    )
    assert ligne["gain"] == pytest.approx(retenue_novembre, abs=0.01)
    assert r["salaire_brut_total"] == pytest.approx(0.0, abs=0.01)
    alerte = next(a for a in contexte.alertes_baremes if a["code"] == "absences_mois_precedent_non_retenues")
    assert "6 jours" in alerte["message"] and "23/11/2026" in alerte["message"]


def test_novembre_deja_entierement_absent_l_absorption_est_juste(monkeypatch):
    """Sans solde continu : le bulletin de novembre retenait déjà le mois entier,
    jours de fin de mois compris. Ni ligne ni alerte (elle ferait retenir deux fois).
    Sans bulletin de novembre, le planning tranche (mois entièrement absent)."""
    entier = {"existe": True, "fin_variables": "2026-11-22", "mois_entier": True}
    sans_bulletin = {"existe": False, "fin_variables": None, "mois_entier": False}
    for planning, bulletin in (
        ("travail", entier), ("absence_non_remuneree", sans_bulletin), (None, sans_bulletin), ("travail", None),
    ):
        r, contexte = _decembre(monkeypatch, planning, bulletin_novembre=bulletin)
        assert r["salaire_brut_total"] == pytest.approx(0.0, abs=0.01)
        assert not any("non retenues" in l["libelle"] for l in r["lignes_composants_brut"])
        assert contexte.alertes_baremes == []


def test_bulletin_precedent_repris_qui_couvrait_son_mois_ni_ligne_ni_alerte(monkeypatch):
    """Novembre payé mais son bulletin vient de l'ancien logiciel (pas de fenêtre :
    il couvrait le mois entier, jours de fin de mois compris), ou sa fenêtre
    allait au-delà de ces jours : rien n'est à porter (Mont Blanc, avril 2026)."""
    for fin in (None, "2026-11-30"):
        r, contexte = _decembre(
            monkeypatch, "travail", bulletin_novembre={"existe": True, "fin_variables": fin, "mois_entier": False}
        )
        assert not any("non retenues" in l["libelle"] for l in r["lignes_composants_brut"])
        assert contexte.alertes_baremes == []
        assert r["salaire_brut_total"] == pytest.approx(0.0, abs=0.01)


def test_trente_neuf_heures_la_part_d_heures_sup_suit_les_jours_repousses(monkeypatch):
    r, contexte = _decembre(monkeypatch, "travail", duree=39.0, salaire=2100.0)
    ligne = next(l for l in r["lignes_composants_brut"] if "non retenues" in l["libelle"])
    base = sum(l["perte"] for l in r["lignes_composants_brut"] if l["libelle"].startswith("Absence non rémunérée du"))
    assert ligne["gain"] > base  # la part d'heures sup structurelles des 6 jours s'y ajoute
    assert r["salaire_brut_total"] == pytest.approx(0.0, abs=0.01)


@pytest.mark.parametrize("duree,salaire", [(35.0, 1870.83), (39.0, 2100.0)])
def test_jamais_de_brut_negatif_avec_un_ferie_paye_hors_absence(monkeypatch, duree, salaire):
    """Mai 2026 : 1er mai férié payé hors absence (le mois n'est pas « entièrement
    absent »), congé parental du 04/05, jours repoussés du 27 au 30/04 d'un
    avril payé : ils ne se retiennent que sur ce qui reste à payer."""
    from app.modules.payroll.engine import calcul_brut as cb

    monkeypatch.setattr(cb, "coefficient_horaire_reel", lambda *_: 1.0)
    periode = {"debut": "2026-05-04", "fin": "2026-09-30"}
    cal = _jours(date(2026, 4, 27), date(2026, 4, 30))
    cal.append({"date_complete": "2026-05-01", "type": "ferie", "heures": 7.0})
    cal += _jours(date(2026, 5, 4), date(2026, 5, 29), motif_absence=SOUS_TYPE_CONGE_PARENTAL, periode_absence=periode)
    extra = {"specificites_extra": {"salaire_hors_hs_structurelles": True}} if duree > 35 else {}
    ctx = build_test_contexte(salaire_base=salaire, duree_hebdo=duree, date_entree="2020-01-06", **extra)
    ctx.alertes_baremes = []
    ctx.bulletin_precedent = {"existe": True, "fin_variables": "2026-04-26", "mois_entier": False}
    r = cb.calculer_salaire_brut(
        ctx, cal, date(2026, 5, 1), date(2026, 5, 31), [], nb_jours_travail_planifies=0,
        date_debut_variables=date(2026, 4, 27), date_fin_variables=date(2026, 5, 22),
        jours_prevus=_prevus_d_un_mois(2026, 4, "travail"),
    )
    assert r["salaire_brut_total"] >= -0.005


# --- 2 -----------------------------------------------------------------------

def _planning(annee, mois, jours, type_jour="absence_non_remuneree"):
    return [{"annee": annee, "mois": mois, "jour": j, "type": type_jour} for j in jours]


def test_jours_entre_la_fenetre_precedente_et_le_mois_civil():
    from app.modules.payroll.documents.payslip_generator import jours_de_conge_parental_entre_deux_bulletins

    demandes = [_conge("2026-11-01", "2027-03-31")]
    precedent = {"en_tete": {"date_fin_variables": "2026-11-22"},
                 "details_absences": [{"libelle": "Absence non rémunérée du 02/11/26"}]}
    planning = _planning(2026, 11, range(2, 31))
    jours = jours_de_conge_parental_entre_deux_bulletins(precedent, 2026, 12, demandes, planning)
    assert jours == [date(2026, 11, d) for d in (23, 24, 25, 26, 27, 30)]


def test_rien_quand_le_bulletin_precedent_les_porte_ou_retenait_le_mois_entier():
    from app.modules.payroll.documents.payslip_generator import jours_de_conge_parental_entre_deux_bulletins

    demandes = [_conge("2026-11-01", "2027-03-31")]
    planning = _planning(2026, 11, range(2, 31))
    au_mois_civil = {"en_tete": {"date_fin_variables": "2026-11-22"},
                     "calcul_du_brut": [{"libelle": "Absence congé parental du 01/11/26 au 30/11/26"}]}
    mois_entier = {"en_tete": {"date_fin_variables": "2026-11-22"},
                   "details_absences": [{"libelle": "Complément retenue absence intégrale du mois (jours fériés/repos inclus)"}]}
    plafonne = {"en_tete": {"date_fin_variables": "2026-11-22"},
                "details_absences": [{"libelle": "Retenue absence intégrale du mois limitée au salaire mensuel"}]}
    au_bout = {"en_tete": {"date_fin_variables": "2026-11-30"}}
    for precedent in (au_mois_civil, mois_entier, plafonne, au_bout, None):
        assert jours_de_conge_parental_entre_deux_bulletins(precedent, 2026, 12, demandes, planning) == []
    assert jours_de_conge_parental_entre_deux_bulletins(
        {"en_tete": {"date_fin_variables": "2026-11-22"}}, 2026, 12, [], planning
    ) == []


def test_jours_deja_retenus_au_bulletin_suivant():
    from app.modules.payroll.documents.payslip_generator import (
        jours_de_conge_parental_deja_retenus_au_bulletin_suivant,
    )

    demandes = [_conge("2026-11-23", "2027-03-31")]
    decembre = {"details_absences": [
        {"libelle": "Absence non rémunérée du 23/11/26"}, {"libelle": "Absence non rémunérée du 24/11/26"},
        {"libelle": "Absence non rémunérée du 20/11/26"}, {"libelle": "Absence non rémunérée du 02/12/26"},
    ]}
    assert jours_de_conge_parental_deja_retenus_au_bulletin_suivant(decembre, 2026, 11, demandes) == [
        date(2026, 11, 23), date(2026, 11, 24)
    ]
    assert jours_de_conge_parental_deja_retenus_au_bulletin_suivant(None, 2026, 11, demandes) == []


def test_les_alertes_ne_lisent_rien_sans_conge_parental_proche(monkeypatch):
    from app.modules.payroll.documents import payslip_generator as pg

    lus = []
    monkeypatch.setattr(pg, "_bulletin_du_mois", lambda *a: lus.append(a) or None)
    assert pg.alertes_conge_parental_entre_bulletins("e-1", 2026, 12, [_conge("2026-03-01", "2026-05-31")], []) == []
    assert pg.alertes_conge_parental_entre_bulletins("e-1", 2026, 12, [_conge("2026-11-23", "2027-03-31")], [], "contrat-range") == []
    assert lus == []
    pg.alertes_conge_parental_entre_bulletins("e-1", 2026, 12, [_conge("2026-11-23", "2027-03-31")], [])
    assert lus == [("e-1", 2026, 11), ("e-1", 2027, 1)]


# --- 3 -----------------------------------------------------------------------

def _reprise(base, jours, event_subtype=SOUS_TYPE_CONGE_PARENTAL):
    from app.modules.absences.application import commands

    with (
        patch.object(commands, "absence_repository") as repo,
        patch.object(commands, "calendar_update_provider") as cal,
    ):
        repo.create.side_effect = lambda d: {**d, "id": f"cree-{len(base.tables['absence_requests'])}"}
        cree = commands.create_reconciliation_absence(
            "e-1", "c-1", "u-1", absence_type="sans_solde", selected_days=jours,
            supabase_client=base, event_subtype=event_subtype,
        )
    return cree, repo, cal


def _base(*demandes):
    return BaseEnMemoire(
        {
            "employees": [{"id": "e-1", "company_id": "c-1", "employment_status": "actif"}],
            "absence_requests": [
                {"employee_id": "e-1", "company_id": "c-1", "type": "sans_solde", "status": "validated", **d}
                for d in demandes
            ],
        }
    )


def test_le_632_requalifie_le_sans_solde_qui_le_recouvre():
    base = _base({"id": "ss-1", "selected_days": ["2026-09-01", "2026-09-02"]})
    cree, repo, cal = _reprise(base, ["2026-09-01", "2026-09-02"])
    assert base.tables["absence_requests"][0]["event_subtype"] == SOUS_TYPE_CONGE_PARENTAL
    cal.poser_le_motif_du_conge_parental.assert_called_once()
    repo.create.assert_not_called()  # mêmes jours : rien de plus à créer
    assert cree["id"] == "ss-1"


def test_un_reimport_ne_cree_rien_de_plus():
    jours = ["2026-09-01", "2026-09-02"]
    base = _base({"id": "cp-1", "event_subtype": SOUS_TYPE_CONGE_PARENTAL, "selected_days": jours})
    cree, repo, cal = _reprise(base, jours)
    repo.create.assert_not_called()
    cal.poser_le_motif_du_conge_parental.assert_not_called()
    assert cree["id"] == "cp-1" and "alertes" not in cree


def test_une_fin_anticipee_est_signalee_sauf_en_fin_de_mois():
    conge = _conge("2026-09-01", "2027-06-30")
    base = _base({"id": "cp-1", "event_subtype": SOUS_TYPE_CONGE_PARENTAL, "selected_days": conge["selected_days"]})
    cree, _, _ = _reprise(base, ["2026-09-01", "2026-09-15"])
    assert any("Fin anticipée" in a for a in cree.get("alertes", []))
    cree, _, _ = _reprise(base, ["2026-09-01", "2026-09-30"])
    assert not cree.get("alertes")


def test_un_sans_solde_qui_deborde_du_632_n_est_pas_requalifie():
    """Congé parental fini le 15/09, sans solde RH du 16 au 30/09, DSN 632 bornée au 30/09."""
    base = _base({"id": "ss-1", "selected_days": [f"2026-09-{d:02d}" for d in range(16, 31)]},
                 {"id": "ss-2", "selected_days": ["2026-08-31", "2026-09-01"]})
    cree, _, cal = _reprise(base, [f"2026-09-{d:02d}" for d in range(1, 31)])
    lignes = {r["id"]: r for r in base.tables["absence_requests"]}
    assert lignes["ss-1"].get("event_subtype") == SOUS_TYPE_CONGE_PARENTAL  # entièrement dedans
    assert not lignes["ss-2"].get("event_subtype")  # déborde au 31/08
    assert any("en déborde et reste un sans solde" in a for a in cree.get("alertes", []))


def test_la_requalification_signale_les_bulletins_deja_calcules():
    base = _base({"id": "ss-1", "selected_days": ["2026-09-28", "2026-09-29"]})
    base.tables["payslips"] = [{"employee_id": "e-1", "year": 2026, "month": 10, "payslip_data": {
        "details_absences": [{"libelle": "Absence non rémunérée du 28/09/26"}]}}]
    cree, _, _ = _reprise(base, [f"2026-09-{d:02d}" for d in range(1, 31)])
    assert any("10/2026" in a and "Recalculez" in a for a in cree.get("alertes", []))


def test_l_import_remonte_la_fin_anticipee_dans_ses_avertissements():
    from app.modules.absences.application import commands
    from app.modules.dsn_import.application.commit import commit_batch

    conge = _conge("2026-09-01", "2027-06-30")
    base = _base({"id": "cp-1", "event_subtype": SOUS_TYPE_CONGE_PARENTAL, "selected_days": conge["selected_days"]})
    items = [{
        "id": "item-cp", "item_type": "absence", "action": "create",
        "source_ref": "abs:1:2:2026-09-01:2026-09-15:sans_solde:suspension",
        "mapped_payload": {"siret": "1", "nir": "2", "absence_type": "sans_solde",
                           "event_subtype": SOUS_TYPE_CONGE_PARENTAL,
                           "selected_days": [f"2026-09-{d:02d}" for d in range(1, 16)]},
    }]
    with (
        patch("app.modules.dsn_import.application.commit.repo") as repo,
        patch("app.modules.dsn_import.application.commit._resolve_employee_for_dsn_item", return_value=("e-1", "c-1")),
        patch("app.modules.dsn_import.application.commit.resolve_dsn_workflow_user_id", return_value="u-1"),
        patch.object(commands, "supabase", base),
        patch.object(commands, "absence_repository"),
        patch.object(commands, "calendar_update_provider"),
    ):
        repo.get_batch.return_value = {"id": "b-1", "status": "previewed", "summary": {"target_company_id": "c-1"}}
        repo.list_items.return_value = items
        repo.find_company_by_id.return_value = {"id": "c-1", "group_id": "g-1"}
        rapport = commit_batch("b-1")
    assert any("Fin anticipée" in w["message"] for w in rapport["warnings"])


# --- 4 -----------------------------------------------------------------------

def test_l_anciennete_ne_retire_que_les_jours_d_apres_son_depart():
    ancien = _conge("2023-01-01", "2023-12-31")  # contrat antérieur, réembauche sans reprise
    assert jours_d_anciennete_neutralises([ancien], date(2026, 12, 31)) == 182
    assert jours_d_anciennete_neutralises([ancien], date(2026, 12, 31), date(2025, 9, 23)) == 0


# --- 5 -----------------------------------------------------------------------

def _assiette_t1(brut: float, pss_ratio: float | None):
    from app.modules.payroll.engine.calcul_cotisations import _calculer_assiettes

    ctx = build_test_contexte(cumuls={
        "cumul_brut_agirc_arrco": -375.58, "cumul_pss_agirc_arrco": 0.0,
        "cumul_tranche_1_appliquee": -375.58, "cumul_tranche_2_appliquee": 0.0,
    })
    ctx.month = 11
    if pss_ratio is not None:
        ctx.ratio_plafond_ss = pss_ratio
    return _calculer_assiettes(ctx, brut, 0.0)["brut_plafonne"]


def test_le_negatif_n_est_rattrape_ni_sur_un_mois_vide_ni_sur_un_petit_mois():
    assert _assiette_t1(0.0, 0.0) == pytest.approx(0.0, abs=0.01)
    assert _assiette_t1(100.0, 0.1) == pytest.approx(100.0, abs=0.01)
    assert _assiette_t1(1870.83, None) == pytest.approx(1870.83, abs=0.01)


def test_tranche_1_sur_trois_mois_apres_un_rappel_d_ijss_negatif():
    """Cumuls portés d'un mois à l'autre : congé (brut 0, plafond 0), petit mois
    de reprise (300 €, plafond partiel), mois plein. Jamais de rattrapage du
    négatif repris, et la tranche 1 de chaque mois vaut son brut."""
    from app.modules.payroll.engine.calcul_cotisations import _calculer_assiettes

    cumuls = {"cumul_brut_agirc_arrco": -375.58, "cumul_pss_agirc_arrco": 9 * 4005.0,
              "cumul_tranche_1_appliquee": -375.58, "cumul_tranche_2_appliquee": 0.0}
    for mois, brut, ratio, attendu in ((10, 0.0, 0.0, 0.0), (11, 300.0, 0.2, 300.0), (12, 1870.83, None, 1870.83)):
        ctx = build_test_contexte(cumuls=dict(cumuls))
        ctx.month = mois
        if ratio is not None:
            ctx.ratio_plafond_ss = ratio
        assert _calculer_assiettes(ctx, brut, 0.0)["brut_plafonne"] == pytest.approx(attendu, abs=0.01)
        suite = ctx.agirc_arrco_cumuls_mois_courant
        cumuls = {k: suite[k] for k in cumuls}


# --- préavis, indemnité, plafond --------------------------------------------

def test_le_preavis_de_l_apercu_compte_le_conge_pour_moitie(monkeypatch):
    from app.modules.employee_exits.application import queries

    salarie = {"id": "e-1", "company_id": "c-1", "hire_date": "2025-01-06", "statut": "Non-cadre"}
    monkeypatch.setattr(queries, "get_employee_full", lambda *_a, **_k: dict(salarie))
    monkeypatch.setattr(queries, "_resolve_employee_collective_agreement", lambda *_a, **_k: (None, None, None))
    sans = queries.get_notice_period_preview(
        "e-1", "c-1", "demission", date(2027, 1, 6), supabase_client=BaseEnMemoire({"absence_requests": []})
    )
    avec = queries.get_notice_period_preview(
        "e-1", "c-1", "demission", date(2027, 1, 6),
        supabase_client=BaseEnMemoire({"absence_requests": [{"employee_id": "e-1", **_conge("2025-07-01", "2026-06-30")}]}),
    )
    assert sans["seniority_months"] == 24
    assert avec["seniority_months"] == 17  # 182 jours repoussés : départ au 07/07/2025


@patch(
    "app.modules.payroll.engine.calcul_indemnites_sortie.calculer_indemnite_conges_restants",
    return_value={"montant": 0.0, "description": "ICCP", "details": {}},
)
def test_l_indemnite_de_rupture_compte_le_conge_pour_moitie(_iccp):
    from app.modules.payroll.engine.calcul_indemnites_sortie import calculer_indemnites_sortie

    salarie = {"id": "emp-1", "hire_date": "2020-01-01", "contract_type": "CDI",
               "salaire_de_base": {"valeur": 2400.0}, "baremes": {"pss": {"annuel": 48060.0, "mensuel": 4005.0}}}
    rupture = {"id": "exit-1", "exit_type": "rupture_conventionnelle", "exit_request_date": "2026-09-15",
               "last_working_day": "2026-10-31", "notice_period_days": 0,
               "notice_indemnity_type": "not_applicable", "montant_negocie": 15000.0}

    def base(*demandes):
        return BaseEnMemoire({
            "employee_schedules": [{"employee_id": "emp-1", "year": 2025, "month": 12,
                                    "cumuls": {"cumuls": {"brut_annee_civile": 30000.0}}}],
            "absence_requests": [{"employee_id": "emp-1", **d} for d in demandes],
        })

    sans = calculer_indemnites_sortie(salarie, rupture, base())["indemnite_rupture_conventionnelle"]
    avec = calculer_indemnites_sortie(salarie, rupture, base(_conge("2022-01-01", "2023-12-31")))[
        "indemnite_rupture_conventionnelle"
    ]
    assert avec["montant_minimum"] < sans["montant_minimum"]


def test_un_jour_repasse_en_travail_garde_son_plafond():
    from app.modules.payroll.engine.calcul_cotisations import ratio_plafond_periode

    periode = {"debut": "2026-11-01", "fin": "2026-11-30"}
    cal = _jours(date(2026, 11, 1), date(2026, 11, 30), motif_absence=SOUS_TYPE_CONGE_PARENTAL, periode_absence=periode)
    cal = [e for e in cal if e["date_complete"] != "2026-11-18"]
    prevus = [{"annee": 2026, "mois": 11, "jour": 18, "type": "travail", "heures_prevues": 7.0}]
    ratio = ratio_plafond_periode(cal, date(2026, 11, 1), date(2026, 11, 30), build_test_contexte(), jours_prevus=prevus)
    assert ratio == pytest.approx(1 / 30, abs=1e-6)


def test_ce_que_le_moteur_sait_du_bulletin_precedent(monkeypatch):
    from app.modules.payroll.documents import payslip_generator as pg

    def bulletin(lignes, fin="2026-11-22"):
        return {"employee_id": "e-1", "year": 2026, "month": 11, "contract_period_id": None,
                "payslip_data": {"en_tete": {"date_fin_variables": fin}, "details_absences": lignes}}

    monkeypatch.setattr(pg, "supabase", BaseEnMemoire({"payslips": [bulletin([])]}))
    assert pg.bulletin_precedent_pour_le_moteur("e-1", 2026, 12) == {
        "existe": True, "fin_variables": "2026-11-22", "mois_entier": False}
    monkeypatch.setattr(pg, "supabase", BaseEnMemoire({"payslips": [bulletin(
        [{"libelle": "Retenue absence intégrale du mois limitée au salaire mensuel"}])]}))
    assert pg.bulletin_precedent_pour_le_moteur("e-1", 2026, 12)["mois_entier"] is True
    monkeypatch.setattr(pg, "supabase", BaseEnMemoire({"payslips": [bulletin([], fin=None)]}))
    assert pg.bulletin_precedent_pour_le_moteur("e-1", 2026, 12)["fin_variables"] is None
    monkeypatch.setattr(pg, "supabase", BaseEnMemoire({"payslips": []}))
    assert pg.bulletin_precedent_pour_le_moteur("e-1", 2026, 12)["existe"] is False


@pytest.mark.parametrize("juin", ["absence_non_remuneree", "arret_maladie"])
def test_mai_avec_ferie_paye_puis_juin_entier_les_jours_de_fin_mai_ne_se_perdent_pas(monkeypatch, juin):
    """Troisième relecture : 35 h, 2 000 €, fenêtre du 26 au 25. Mai : 1er mai férié
    payé, sans solde du 4 au 29 : son bulletin (pas « mois entier ») s'arrête au 25
    et ne retient pas les 26-29/05. Juin entièrement absent : ces jours, qui ne
    tiennent plus sur rien, sont rendus en clair et signalés — jamais retenus nulle part
    en silence. Le planning de mai (aucun jour travaillé) n'y change rien : c'est le
    bulletin de mai qui décide."""
    from app.modules.payroll.engine import calcul_brut as cb

    monkeypatch.setattr(cb, "coefficient_horaire_reel", lambda *_: 1.0)
    cal = _jours(date(2026, 5, 26), date(2026, 5, 29))
    cal += [{**j, "type": juin} for j in _jours(date(2026, 6, 1), date(2026, 6, 30))]
    prevus = [{"annee": 2026, "mois": 5, "jour": 1, "type": "ferie", "heures_prevues": 7.0}] + [
        {"annee": 2026, "mois": 5, "jour": d, "type": "absence_non_remuneree", "heures_prevues": 7.0}
        for d in range(4, 30)
    ]
    ctx = build_test_contexte(salaire_base=2000.0, duree_hebdo=35.0, date_entree="2020-01-06")
    ctx.alertes_baremes = []
    ctx.bulletin_precedent = {"existe": True, "fin_variables": "2026-05-25", "mois_entier": False}
    r = cb.calculer_salaire_brut(
        ctx, cal, date(2026, 6, 1), date(2026, 6, 30), [], nb_jours_travail_planifies=0,
        date_debut_variables=date(2026, 5, 26), date_fin_variables=date(2026, 6, 25), jours_prevus=prevus,
    )
    assert r["salaire_brut_total"] >= -0.005
    if juin == "absence_non_remuneree":
        ligne = next(l for l in r["lignes_composants_brut"] if "non retenues" in l["libelle"])
        assert ligne["gain"] > 0
        assert any(a["code"] == "absences_mois_precedent_non_retenues" for a in ctx.alertes_baremes)


def test_le_bulletin_precedent_n_est_relu_qu_avec_des_jours_repousses():
    from app.modules.payroll.documents.payslip_generator import absence_non_remuneree_avant_le_mois

    novembre = _planning(2026, 11, [23, 24]) + _planning(2026, 11, [20], "travail")
    assert absence_non_remuneree_avant_le_mois(novembre, date(2026, 11, 23), 2026, 12)
    assert not absence_non_remuneree_avant_le_mois(novembre, date(2026, 12, 1), 2026, 12)
    assert not absence_non_remuneree_avant_le_mois(_planning(2026, 11, [20], "travail"), date(2026, 11, 23), 2026, 12)
