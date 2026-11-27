"""Primes liées aux pointages des usines (retour d'Elsa du 17/11/2026).

- Panier ou prime de présence seulement si le poste commence dans une plage
  (Mont Blanc et LEWIS : 4 h ou 12 h) ;
- pause payée de N h par poste au taux horaire (Cartol) ;
- prime d'assiduité perdue par un arrêt ou une absence injustifiée relevés au
  calendrier : au mois (Mont Blanc 50 €, 25 € à mi-temps), à la semaine
  (LEWIS 6 €) ;
- heures de nuit lues sur l'heure de début et de fin, majorées d'un % du taux
  horaire (Cartol 50 %) ;
- périmètre : hors forfait jours, cadres et alternants.
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from app.modules.payroll_variables.application import generate_monthly as gm
from app.modules.payroll_variables.domain.assiduite import (
    evaluer_assiduite_des_semaines,
    evaluer_assiduite_du_mois,
    lundis_de_la_fenetre,
    motif_de_perte,
)
from app.modules.payroll_variables.domain.jours_travailles import detail_jours_travailles
from app.modules.payroll_variables.domain.rules import employee_matches_conditions

pytestmark = pytest.mark.unit

DEBUT, FIN = date(2026, 10, 1), date(2026, 10, 31)
PLAGES_4H_12H = [{"de": "03:30", "a": "04:30"}, {"de": "11:30", "a": "12:30"}]


def _ouvres(debut: date, fin: date):
    j = debut
    while j <= fin:
        if j.weekday() < 5:
            yield j
        j += timedelta(days=1)


def _calendrier(debuts: dict[date, str] | None = None, types: dict[date, str] | None = None, heures=7.0):
    """Prévu « travail » 7 h les jours ouvrés ; réel pointé avec les débuts donnés."""
    prevu, reel = {}, {}
    for j in _ouvres(DEBUT, FIN):
        prevu[j] = {"jour": j.day, "type": "travail", "heures_prevues": heures}
        t = (types or {}).get(j)
        if t:
            prevu[j] = {"jour": j.day, "type": t, "heures_prevues": 0}
            reel[j] = {"jour": j.day, "type": t, "heures_faites": 0}
            continue
        entree = {"jour": j.day, "type": "travail", "heures_faites": heures}
        if debuts is not None and j in debuts:
            entree["debut"] = debuts[j]
            entree["fin"] = "12:00"
        reel[j] = entree
    return prevu, reel


class TestJoursSelonLHeureDeDebut:
    def test_seuls_les_postes_de_4_h_et_12_h_comptent(self):
        jours = list(_ouvres(DEBUT, FIN))
        debuts = {j: ("03:50" if i % 3 == 0 else "11:55" if i % 3 == 1 else "05:43") for i, j in enumerate(jours)}
        prevu, reel = _calendrier(debuts)
        d = detail_jours_travailles(prevu, reel, set(), DEBUT, FIN, plages_debut=PLAGES_4H_12H)
        attendu = sum(1 for i in range(len(jours)) if i % 3 != 2)
        assert d["jours"] == attendu
        assert d["sans_heure_de_debut"] == 0

    def test_un_jour_sans_heure_de_debut_ne_compte_pas_et_se_voit(self):
        prevu, reel = _calendrier({})
        d = detail_jours_travailles(prevu, reel, set(), DEBUT, FIN, plages_debut=PLAGES_4H_12H)
        assert d["jours"] == 0
        assert d["sans_heure_de_debut"] == len(list(_ouvres(DEBUT, FIN)))
        assert d["aucun_badge"] is True

    def test_un_badge_oublie_prend_le_poste_de_sa_semaine(self):
        # Semaine du 5 au 9/10 au poste de 4 h, badge oublié le mercredi 7.
        debuts = {j: "03:50" for j in _ouvres(date(2026, 10, 5), date(2026, 10, 9)) if j.day != 7}
        prevu, reel = _calendrier(debuts)
        d = detail_jours_travailles(prevu, reel, set(), date(2026, 10, 5), date(2026, 10, 9), plages_debut=PLAGES_4H_12H)
        assert d["jours"] == 5
        assert d["sans_heure_de_debut"] == 0
        assert d["repris_de_la_semaine"] == ["2026-10-07"]

    def test_une_semaine_hors_plage_ne_donne_rien_au_jour_oublie(self):
        debuts = {j: "08:00" for j in _ouvres(date(2026, 10, 5), date(2026, 10, 9)) if j.day != 7}
        prevu, reel = _calendrier(debuts)
        d = detail_jours_travailles(prevu, reel, set(), date(2026, 10, 5), date(2026, 10, 9), plages_debut=PLAGES_4H_12H)
        assert d["jours"] == 0
        assert d["sans_heure_de_debut"] == 0
        assert d["repris_de_la_semaine"] == ["2026-10-07"]

    def test_une_semaine_a_postes_melanges_reste_a_verifier(self):
        debuts = {date(2026, 10, 5): "03:50", date(2026, 10, 6): "11:55", date(2026, 10, 8): "03:50", date(2026, 10, 9): "03:50"}
        prevu, reel = _calendrier(debuts)
        d = detail_jours_travailles(prevu, reel, set(), date(2026, 10, 5), date(2026, 10, 9), plages_debut=PLAGES_4H_12H)
        assert d["jours"] == 4
        assert d["sans_heure_de_debut"] == 1
        assert d["repris_de_la_semaine"] == []

    def test_un_seul_badge_ne_tranche_pas_la_semaine(self):
        # Seul le vendredi badgé, à 8 h (formation) : les postes de 4 h oubliés restent à voir.
        prevu, reel = _calendrier({date(2026, 10, 9): "08:00"})
        d = detail_jours_travailles(prevu, reel, set(), date(2026, 10, 5), date(2026, 10, 9), plages_debut=PLAGES_4H_12H)
        assert d["jours"] == 0
        assert d["sans_heure_de_debut"] == 4
        assert d["repris_de_la_semaine"] == []

    def test_les_badges_hors_fenetre_ne_tranchent_rien(self):
        # Nouveau contrat le mercredi 7 : les badges du lundi et du mardi sont à l'ancien.
        prevu, reel = _calendrier({date(2026, 10, 5): "03:50", date(2026, 10, 6): "03:50"})
        d = detail_jours_travailles(prevu, reel, set(), date(2026, 10, 7), date(2026, 10, 9), plages_debut=PLAGES_4H_12H)
        assert d["jours"] == 0
        assert d["sans_heure_de_debut"] == 3
        assert d["aucun_badge"] is True

    def test_un_jour_sous_le_seuil_ne_sert_pas_de_modele(self):
        prevu, reel = _calendrier({date(2026, 10, 5): "03:50", date(2026, 10, 6): "03:50"})
        reel[date(2026, 10, 5)]["heures_faites"] = 3.0
        reel[date(2026, 10, 6)]["heures_faites"] = 3.0
        d = detail_jours_travailles(
            prevu, reel, set(), date(2026, 10, 5), date(2026, 10, 9), min_heures=6, plages_debut=PLAGES_4H_12H
        )
        assert d["jours"] == 0
        assert d["sans_heure_de_debut"] == 3

    def test_une_semaine_sans_aucun_badge_reste_a_verifier(self):
        debuts = {j: "03:50" for j in _ouvres(date(2026, 10, 5), date(2026, 10, 9))}
        prevu, reel = _calendrier(debuts)
        d = detail_jours_travailles(prevu, reel, set(), date(2026, 10, 5), date(2026, 10, 16), plages_debut=PLAGES_4H_12H)
        assert d["jours"] == 5
        assert d["sans_heure_de_debut"] == 5
        assert d["aucun_badge"] is False

    def test_sans_plage_rien_ne_change(self):
        prevu, reel = _calendrier({})
        assert detail_jours_travailles(prevu, reel, set(), DEBUT, FIN)["jours"] == 22


class TestAssiduite:
    def test_un_arret_fait_perdre_la_prime_du_mois(self):
        prevu, reel = _calendrier(types={date(2026, 10, 14): "arret_maladie"})
        r = evaluer_assiduite_du_mois(prevu, reel, set(), DEBUT, FIN, montant=50)
        assert r["amount"] == 0
        assert r["details"]["perdue"] == [{"jour": "2026-10-14", "motif": "arret_maladie"}]

    def test_conges_et_recup_ne_font_rien_perdre(self):
        prevu, reel = _calendrier(
            types={date(2026, 10, 14): "conges_payes", date(2026, 10, 15): "rtt", date(2026, 10, 16): "repos"}
        )
        assert evaluer_assiduite_du_mois(prevu, reel, set(), DEBUT, FIN, montant=50)["amount"] == 50

    def test_une_journee_prevue_non_faite_fait_perdre(self):
        prevu, reel = _calendrier()
        reel[date(2026, 10, 20)] = {"jour": 20, "type": "travail", "heures_faites": 0}
        r = evaluer_assiduite_du_mois(prevu, reel, set(), DEBUT, FIN, montant=50)
        assert r["amount"] == 0
        assert r["details"]["perdue"][0]["motif"] == "journee_non_faite"

    def test_mi_temps_moitie(self):
        prevu, reel = _calendrier(heures=3.5)
        assert evaluer_assiduite_du_mois(prevu, reel, set(), DEBUT, FIN, montant=50, duree_hebdomadaire=17.5)["amount"] == 25

    def test_rien_travaille_pas_de_prime(self):
        prevu, reel = {}, {}
        assert evaluer_assiduite_du_mois(prevu, reel, set(), DEBUT, FIN, montant=50)["amount"] == 0

    def test_semaines_lewis(self):
        prevu, reel = _calendrier(types={date(2026, 10, 14): "absent_a_typer"})
        r = evaluer_assiduite_des_semaines(prevu, reel, set(), DEBUT, FIN, montant_par_semaine=6)
        lundis = lundis_de_la_fenetre(DEBUT, FIN)
        # Les semaines qui finissent en octobre (dimanches 4, 11, 18, 25).
        assert [l.isoformat() for l in lundis] == ["2026-09-28", "2026-10-05", "2026-10-12", "2026-10-19"]
        # La semaine du 12/10 est perdue.
        assert r["quantity"] == 3
        assert r["amount"] == 18

    def test_une_semaine_a_cheval_se_paie_dans_le_mois_de_son_dimanche(self):
        # La semaine du 26/10 au 01/11 se paie en novembre, une fois vécue.
        assert date(2026, 10, 26) not in lundis_de_la_fenetre(DEBUT, FIN)
        assert date(2026, 10, 26) in lundis_de_la_fenetre(date(2026, 11, 1), date(2026, 11, 30))

    def test_un_arret_en_debut_de_semaine_du_mois_d_avant_se_voit(self):
        prevu, reel = _calendrier()
        prevu[date(2026, 9, 29)] = {"jour": 29, "type": "arret_maladie"}
        r = evaluer_assiduite_des_semaines(prevu, reel, set(), DEBUT, FIN, montant_par_semaine=6)
        assert r["details"]["weeks"][0] == {
            "monday": "2026-09-28",
            "eligible": False,
            "reason": "absence",
            "jours": ["2026-09-29"],
        }

    def test_types_choisis_par_la_regle(self):
        assert motif_de_perte({"type": "conges_payes"}, None) is None
        assert motif_de_perte({"type": "absence_non_remuneree"}, None) == "absence_non_remuneree"
        assert motif_de_perte({"type": "absence_non_remuneree"}, None, ["arret"]) is None
        assert motif_de_perte({"type": "arret_at"}, None, ["arret"]) == "arret_at"

    def test_absence_non_remuneree_typee_a_l_ecran_fait_perdre(self):
        prevu, reel = _calendrier(types={date(2026, 10, 14): "absence_non_remuneree"})
        assert evaluer_assiduite_du_mois(prevu, reel, set(), DEBUT, FIN, montant=50)["amount"] == 0

    def test_conge_maternite_ne_fait_jamais_perdre(self):
        prevu, reel = _calendrier()
        prevu[date(2026, 10, 14)] = {"jour": 14, "type": "arret_maladie", "arret_type": "maternite"}
        reel[date(2026, 10, 14)] = {"jour": 14, "type": "arret_maladie", "heures_faites": 0}
        assert evaluer_assiduite_du_mois(prevu, reel, set(), DEBUT, FIN, montant=50)["amount"] == 50

    def test_un_jtc_valide_a_0_h_n_est_pas_une_journee_non_faite(self):
        prevu, reel = _calendrier()
        reel[date(2026, 10, 20)] = {"jour": 20, "type": "travail", "heures_faites": 0}
        r = evaluer_assiduite_du_mois(prevu, reel, {date(2026, 10, 20)}, DEBUT, FIN, montant=50)
        assert r["amount"] == 50

    def test_un_mois_tout_en_conges_payes_garde_la_prime(self):
        prevu, reel = _calendrier(types={j: "conges_payes" for j in _ouvres(DEBUT, FIN)})
        assert evaluer_assiduite_du_mois(prevu, reel, set(), DEBUT, FIN, montant=50)["amount"] == 50

    def test_au_mois_les_demandes_cochees_font_perdre(self):
        prevu, reel = _calendrier()
        r = evaluer_assiduite_du_mois(
            prevu, reel, set(), DEBUT, FIN, montant=50, jours_demandes_qui_font_perdre={date(2026, 10, 9)}
        )
        assert r["amount"] == 0
        assert r["details"]["perdue"] == [{"jour": "2026-10-09", "motif": "demande_d_absence"}]


class TestPerimetre:
    @pytest.mark.parametrize(
        "fiche,attendu",
        [
            ({"id": "1", "statut": "Non-Cadre", "is_forfait_jour": False, "contract_type": "CDI"}, True),
            ({"id": "2", "statut": "Non-Cadre", "is_forfait_jour": True, "contract_type": "CDI"}, False),
            ({"id": "3", "statut": "Cadre", "is_forfait_jour": False, "contract_type": "CDI"}, False),
            ({"id": "4", "statut": "Non-Cadre", "is_forfait_jour": False, "contract_type": "Apprentissage"}, False),
            ({"id": "5", "statut": "Non-Cadre", "is_forfait_jour": False, "contract_type": "CDD"}, True),
        ],
    )
    def test_hors_forfait_cadres_alternants(self, fiche, attendu):
        conditions = {"exclure_forfait_jours": True, "exclure_cadres": True, "exclure_alternants": True}
        assert employee_matches_conditions(fiche, conditions) is attendu


# ---------------------------------------------------------------- génération


def _brancher(monkeypatch, regle, fiche, prevu, reel):
    monkeypatch.setattr(gm, "_bornes_variables", lambda cid, a, m: (DEBUT, FIN))
    repo = MagicMock()
    repo.list_rules.return_value = [{"enabled": True, "generation_mode": "auto", "code": "r", **regle}]
    repo.list_special_days.return_value = []
    monkeypatch.setattr(gm, "repo", repo)
    chaine = MagicMock()
    chaine.select.return_value = chaine
    chaine.eq.return_value = chaine
    chaine.in_.return_value = chaine
    chaine.execute.return_value = MagicMock(data=[fiche])
    sb = MagicMock()
    sb.table.return_value = chaine
    monkeypatch.setattr(gm, "supabase", sb)
    monkeypatch.setattr(gm, "list_validated_absences_for_employees_in_range", lambda *a, **k: [])
    monkeypatch.setattr(gm, "_calendriers_de_la_fenetre", lambda eid, d, f: (prevu, reel))
    return repo


FICHE = {
    "id": "e1",
    "first_name": "A",
    "last_name": "B",
    "statut": "Non-Cadre",
    "is_forfait_jour": False,
    "contract_type": "CDI",
    "salaire_de_base": 1823.03,
    "duree_hebdomadaire": 35,
}


class TestGeneration:
    def test_panier_mont_blanc_aux_postes_de_4_h(self, monkeypatch):
        jours = list(_ouvres(DEBUT, FIN))
        debuts = {j: ("03:50" if j.day % 2 else "05:43") for j in jours}
        prevu, reel = _calendrier(debuts)
        _brancher(
            monkeypatch,
            {
                "rule_type": "per_worked_day",
                "label": "Panier",
                "amount": 10,
                "conditions": {"plages_debut": PLAGES_4H_12H, "situation_repas": "sur_lieu_travail"},
            },
            FICHE,
            prevu,
            reel,
        )
        res = gm.generate_monthly_variables("c", 2026, 10, dry_run=True)
        n = sum(1 for j in jours if j.day % 2)
        assert res["preview"][0]["quantity"] == n
        assert res["preview"][0]["amount"] == 10 * n

    def test_sans_heure_de_debut_l_apercu_le_dit(self, monkeypatch):
        prevu, reel = _calendrier({})
        _brancher(
            monkeypatch,
            {"rule_type": "per_worked_day", "label": "Panier", "amount": 10, "conditions": {"plages_debut": PLAGES_4H_12H}},
            FICHE,
            prevu,
            reel,
        )
        res = gm.generate_monthly_variables("c", 2026, 10, dry_run=True)
        assert res["preview"][0]["amount"] == 0
        assert res["preview"][0]["details"]["jours_sans_heure_de_debut"] == 22

    def test_pause_payee_cartol_au_taux_horaire(self, monkeypatch):
        prevu, reel = _calendrier({j: "05:00" for j in _ouvres(DEBUT, FIN)})
        _brancher(
            monkeypatch,
            {
                "rule_type": "per_worked_day",
                "label": "Pause payée",
                "amount": None,
                "conditions": {"plages_debut": [{"de": "04:30", "a": "05:30"}], "heures_par_jour": 0.5},
            },
            FICHE,
            prevu,
            reel,
        )
        res = gm.generate_monthly_variables("c", 2026, 10, dry_run=True)
        taux = 1823.03 / (35 * 52 / 12)
        assert res["preview"][0]["amount"] == pytest.approx(round(22 * round(0.5 * round(taux, 4), 4), 2))

    def test_assiduite_mensuelle_perdue_par_un_arret(self, monkeypatch):
        prevu, reel = _calendrier(types={date(2026, 10, 7): "arret_maladie"})
        repo = _brancher(
            monkeypatch,
            {
                "rule_type": "per_week_without_absence",
                "label": "Prime d'assiduité",
                "amount": 50,
                "conditions": {"periode_assiduite": "mois"},
            },
            FICHE,
            prevu,
            reel,
        )
        res = gm.generate_monthly_variables("c", 2026, 10, dry_run=True)
        assert res["preview"][0]["amount"] == 0
        assert res["preview"][0]["details"]["perdue"][0]["motif"] == "arret_maladie"
        repo.upsert_monthly_input.assert_not_called()

    def test_assiduite_mensuelle_ecrite(self, monkeypatch):
        prevu, reel = _calendrier()
        repo = _brancher(
            monkeypatch,
            {
                "rule_type": "per_week_without_absence",
                "label": "Prime d'assiduité",
                "amount": 50,
                "conditions": {"periode_assiduite": "mois"},
            },
            FICHE,
            prevu,
            reel,
        )
        res = gm.generate_monthly_variables("c", 2026, 10)
        assert res["written_count"] == 1
        payload = repo.upsert_monthly_input.call_args[0][0]
        assert payload["amount"] == 50 and payload["is_socially_taxed"] is True

    def test_forfait_jours_exclu(self, monkeypatch):
        prevu, reel = _calendrier()
        _brancher(
            monkeypatch,
            {
                "rule_type": "per_week_without_absence",
                "label": "Prime d'assiduité",
                "amount": 50,
                "conditions": {"periode_assiduite": "mois", "exclure_forfait_jours": True},
            },
            {**FICHE, "is_forfait_jour": True},
            prevu,
            reel,
        )
        assert gm.generate_monthly_variables("c", 2026, 10, dry_run=True)["preview"] == []

    def test_nuit_cartol_depuis_le_calendrier(self, monkeypatch):
        prevu, reel = _calendrier()
        for j in _ouvres(DEBUT, FIN):
            reel[j] = {**reel[j], "debut": "05:00", "fin": "13:15"}
        _brancher(
            monkeypatch,
            {
                "rule_type": "per_night_hour",
                "label": "Heures de nuit",
                "amount": None,
                "rate": None,
                "conditions": {"majoration_pct": 50, "depuis_les_pointages": True},
            },
            FICHE,
            prevu,
            reel,
        )
        monkeypatch.setattr(gm, "_shift_payroll_summary", lambda *a, **k: {})
        import app.modules.planning.application.shift_payroll_aggregation as agg

        monkeypatch.setattr(agg, "aggregate_shift_payroll_metrics", lambda *a, **k: {})
        res = gm.generate_monthly_variables("c", 2026, 10, dry_run=True)
        taux = round(round(1823.03 / (35 * 52 / 12), 4) * 0.5, 4)
        assert res["preview"][0]["quantity"] == 22.0
        assert res["preview"][0]["amount"] == pytest.approx(round(taux * 22, 2))


class TestRetombeAZero:
    def test_la_prime_perdue_retire_la_saisie_deja_ecrite(self, monkeypatch):
        prevu, reel = _calendrier(types={date(2026, 10, 7): "arret_maladie"})
        repo = _brancher(
            monkeypatch,
            {
                "rule_type": "per_week_without_absence",
                "label": "Prime d'assiduité",
                "amount": 50,
                "conditions": {"periode_assiduite": "mois"},
            },
            FICHE,
            prevu,
            reel,
        )
        gm.generate_monthly_variables("c", 2026, 10)
        repo.retirer_saisie_generee.assert_called_once_with("e1", 2026, 10, "Prime d'assiduité")
        repo.upsert_monthly_input.assert_not_called()

    def test_une_regle_de_nuit_ancienne_ne_lit_pas_les_pointages(self, monkeypatch):
        prevu, reel = _calendrier()
        for j in _ouvres(DEBUT, FIN):
            reel[j] = {**reel[j], "debut": "05:00", "fin": "13:15"}
        _brancher(
            monkeypatch,
            {"rule_type": "per_night_hour", "label": "Nuit", "amount": 2, "rate": None, "conditions": {}},
            FICHE,
            prevu,
            reel,
        )
        monkeypatch.setattr(gm, "_shift_payroll_summary", lambda *a, **k: {})
        import app.modules.planning.application.shift_payroll_aggregation as agg

        monkeypatch.setattr(agg, "aggregate_shift_payroll_metrics", lambda *a, **k: {})
        assert gm.generate_monthly_variables("c", 2026, 10, dry_run=True)["preview"] == []



class TestJoursSansHeureDArriveeDits:
    """L19 (26-27/11) : les jours travaillés sans heure d'arrivée dont le panier
    n'est pas compté étaient calculés mais dits nulle part quand le panier du
    mois restait positif. Ils se recalculent au calendrier, par la même règle,
    au bulletin et pour « Primes du mois » ; rien n'est stocké (relecture du
    27/11 : une remarque dans la description pouvait faire payer la saisie en
    heures sup)."""

    REGLE = {
        "rule_type": "per_worked_day",
        "label": "Panier",
        "amount": 10,
        "conditions": {"plages_debut": PLAGES_4H_12H},
    }

    def _calendrier_avec_deux_oublis(self):
        # Postes de 4 h badgés, sauf le lundi 5 et le mardi 6 : semaine mêlée
        # (un seul autre badge au poste de 12 h) qui ne tranche pas.
        debuts = {j: "03:50" for j in _ouvres(DEBUT, FIN)}
        debuts.pop(date(2026, 10, 5))
        debuts.pop(date(2026, 10, 6))
        debuts[date(2026, 10, 7)] = "11:55"
        return _calendrier(debuts)

    def test_l_apercu_donne_les_dates(self, monkeypatch):
        prevu, reel = self._calendrier_avec_deux_oublis()
        _brancher(monkeypatch, self.REGLE, FICHE, prevu, reel)
        res = gm.generate_monthly_variables("c", 2026, 10, dry_run=True)
        details = res["preview"][0]["details"]
        assert res["preview"][0]["amount"] > 0
        assert details["jours_sans_heure_de_debut"] == 2
        assert details["dates_sans_heure_de_debut"] == ["2026-10-05", "2026-10-06"]

    def test_la_saisie_ecrite_garde_sa_description(self, monkeypatch):
        prevu, reel = self._calendrier_avec_deux_oublis()
        repo = _brancher(monkeypatch, self.REGLE, FICHE, prevu, reel)
        monkeypatch.setattr(gm, "_bonus_type_meta", lambda r: ("Panier", False, False, None, None, None))
        gm.generate_monthly_variables("c", 2026, 10, dry_run=False)
        assert repo.upsert_monthly_input.call_args.args[0]["description"] == "Auto: r"

    def test_le_bulletin_le_dit_recalcule_au_calendrier(self, monkeypatch):
        from app.modules.payroll_variables.application.alertes_paniers import alertes_des_paniers_du_mois

        prevu, reel = self._calendrier_avec_deux_oublis()
        _brancher(monkeypatch, self.REGLE, FICHE, prevu, reel)
        alertes = alertes_des_paniers_du_mois("c", "e1", 2026, 10, [])
        assert [a["message"] for a in alertes] == [
            "Panier : 2 jours travaillés sans heure d'arrivée, non comptés (05/10, 06/10) : "
            "heure d'arrivée à saisir au calendrier, ou absence à poser."
        ]
        assert alertes[0]["code"] == "jours_sans_heure_d_arrivee"
        assert alertes[0]["critique"] is False

    def test_l_arrivee_corrigee_eteint_l_alerte(self, monkeypatch):
        from app.modules.payroll_variables.application.alertes_paniers import alertes_des_paniers_du_mois

        prevu, reel = _calendrier({j: "03:50" for j in _ouvres(DEBUT, FIN)})
        _brancher(monkeypatch, self.REGLE, FICHE, prevu, reel)
        assert alertes_des_paniers_du_mois("c", "e1", 2026, 10, []) == []

    def test_panier_du_mois_a_zero_l_alerte_reste(self, monkeypatch):
        from app.modules.payroll_variables.application.alertes_paniers import alertes_des_paniers_du_mois

        prevu, reel = _calendrier({})
        _brancher(monkeypatch, self.REGLE, FICHE, prevu, reel)
        alertes = alertes_des_paniers_du_mois("c", "e1", 2026, 10, [])
        assert len(alertes) == 1 and "22 jours travaillés sans heure d'arrivée" in alertes[0]["message"]

    def test_l_ecran_primes_du_mois_les_lit_sans_rien_ecrire(self, monkeypatch):
        from app.modules.payroll_variables.application.alertes_paniers import jours_sans_heure_d_arrivee

        prevu, reel = self._calendrier_avec_deux_oublis()
        repo = _brancher(monkeypatch, self.REGLE, FICHE, prevu, reel)
        jours = jours_sans_heure_d_arrivee("c", 2026, 10)
        assert jours == [
            {
                "employee_id": "e1",
                "first_name": "A",
                "last_name": "B",
                "rule_label": "Panier",
                "dates": ["2026-10-05", "2026-10-06"],
            }
        ]
        repo.upsert_monthly_input.assert_not_called()
        repo.retirer_saisie_generee.assert_not_called()


class TestMontantModifieSansLeNombre:
    """L19, relecture point B : un panier dont le montant est changé à la main
    sans changer le nombre garde la réintégration calculée sur ce nombre ; le
    bulletin le dit."""

    REGLE = {"rule_type": "per_worked_day", "label": "Panier", "amount": 7.6, "conditions": {}}

    def _saisie(self, montant):
        return {"name": "Panier", "description": "Auto: r", "amount": montant, "payroll_quantity": 15,
                "manual_override": True}

    def test_montant_different_du_nombre_fois_le_taux(self, monkeypatch):
        from app.modules.payroll_variables.application.alertes_paniers import alertes_des_paniers_du_mois

        _brancher(monkeypatch, self.REGLE, FICHE, {}, {})
        alertes = alertes_des_paniers_du_mois("c", "e1", 2026, 10, [self._saisie(121.6)])
        assert [a["message"] for a in alertes] == [
            "Panier : montant modifié à la main (121,60 €) sans changer le nombre de paniers (15) : "
            "la part réintégrée est calculée sur 15 paniers ; corrigez le nombre dans Primes du mois"
        ]
        assert alertes[0]["critique"] is False

    def test_montant_egal_au_nombre_fois_le_taux(self, monkeypatch):
        from app.modules.payroll_variables.application.alertes_paniers import alertes_des_paniers_du_mois

        _brancher(monkeypatch, self.REGLE, FICHE, {}, {})
        assert alertes_des_paniers_du_mois("c", "e1", 2026, 10, [self._saisie(114.0)]) == []

    def test_une_saisie_a_la_main_ou_retiree_ne_dit_rien(self, monkeypatch):
        from app.modules.payroll_variables.application.alertes_paniers import alertes_des_paniers_du_mois

        _brancher(monkeypatch, self.REGLE, FICHE, {}, {})
        a_la_main = {**self._saisie(121.6), "description": "Saisie RH"}
        retiree = {**self._saisie(0), "amount": 0}
        assert alertes_des_paniers_du_mois("c", "e1", 2026, 10, [a_la_main, retiree]) == []


@pytest.mark.parametrize("module", ["payslip_generator", "payslip_generator_forfait"])
def test_les_deux_generateurs_disent_les_paniers_du_mois(module):
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[3] / f"app/modules/payroll/documents/{module}.py"
    ).read_text(encoding="utf-8")
    assert "alertes_des_paniers_du_mois(" in source
