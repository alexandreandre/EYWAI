"""Activité partielle : la pose des heures chômées du mois (base en mémoire)."""

from __future__ import annotations

import pytest

import app.modules.activite_partielle.application.service as svc


class _Requete:
    def __init__(self, base, table):
        self.base, self.table, self.filtres, self.op, self.donnees = (
            base,
            table,
            [],
            "select",
            None,
        )

    def select(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self.filtres.append(lambda r: str(r.get(col)) == str(val))
        return self

    def in_(self, col, vals):
        vals = {str(v) for v in vals}
        self.filtres.append(lambda r: str(r.get(col)) in vals)
        return self

    def insert(self, rows):
        self.op, self.donnees = "insert", rows if isinstance(rows, list) else [rows]
        return self

    def upsert(self, row, on_conflict=None):
        self.op, self.donnees = "upsert", row
        return self

    def delete(self):
        self.op = "delete"
        return self

    def execute(self):
        rows = self.base.setdefault(self.table, [])
        ok = [r for r in rows if all(f(r) for f in self.filtres)]
        if self.op == "insert":
            for r in self.donnees:
                rows.append({**r, "id": f"{self.table}-{len(rows)}"})
            return type("R", (), {"data": self.donnees})
        if self.op == "upsert":
            rows[:] = [
                r for r in rows if r.get("company_id") != self.donnees["company_id"]
            ]
            rows.append(dict(self.donnees))
            return type("R", (), {"data": [self.donnees]})
        if self.op == "delete":
            rows[:] = [r for r in rows if r not in ok]
            return type("R", (), {"data": ok})
        return type("R", (), {"data": [dict(r) for r in ok]})


class _Base:
    def __init__(self):
        self.tables: dict[str, list] = {}

    def table(self, nom):
        return _Requete(self.tables, nom)


@pytest.fixture
def base(monkeypatch):
    import calendar as _cal
    from datetime import date as _date

    import app.shared.reprise_paie as reprise

    # Ni bascule de reprise, ni fenêtre de société : le mois civil.
    monkeypatch.setattr(reprise, "fin_de_la_reprise_au_premier_mois", lambda *a, **k: None)
    monkeypatch.setattr(
        svc,
        "bornes_du_bulletin",
        lambda co, an, mois, forfait_jours: (_date(an, mois, 1), _date(an, mois, _cal.monthrange(an, mois)[1])),
    )
    b = _Base()
    b.tables["employees"] = [
        {
            "id": "e1",
            "company_id": "co",
            "first_name": "A",
            "last_name": "B",
            "salaire_de_base": {"type": "mensuel", "valeur": 2166.67},
            "duree_hebdomadaire": "35.00",
            "hire_date": "2020-01-01",
            "employment_status": "actif",
        }
    ]
    b.tables["company_activite_partielle"] = [
        {
            "company_id": "co",
            "active": True,
            "date_debut": "2026-06-01",
            "date_fin": None,
            "taux_indemnite": "60",
            "plancher_horaire": "9.74",
            "plafond_horaire": "33.24",
            "heures_par_jour": None,
        }
    ]
    monkeypatch.setattr(svc, "_db", lambda: b)
    monkeypatch.setattr(svc, "_bulletin_remis", lambda eid, y, m: False)
    import app.modules.monthly_inputs.application.queries as q

    monkeypatch.setattr(q, "bulletins_a_recalculer", lambda cid, cibles: [])
    return b


def test_pose_les_deux_lignes_et_les_remplace(base):
    res = svc.poser_heures_du_mois(
        "co", 2026, 11, [{"employee_id": "e1", "heures": 56}], "u"
    )
    (r,) = res["resultats"]
    assert r["statut"] == "pose"
    assert r["indemnite"] == 545.44
    lignes = base.tables["monthly_inputs"]
    assert {ligne["name"] for ligne in lignes} == {
        "Heures chômées (act. part.)",
        "Indemnité activité partielle",
    }
    retenue = next(ligne for ligne in lignes if ligne["amount"] < 0)
    assert retenue["payroll_quantity"] == 56
    assert retenue["amount"] == pytest.approx(-800.0, abs=0.01)

    svc.poser_heures_du_mois("co", 2026, 11, [{"employee_id": "e1", "heures": 7}], "u")
    assert len(base.tables["monthly_inputs"]) == 2
    vue = svc.lister_mois("co", 2026, 11)
    assert vue["salaries"][0]["deja"]["heures"] == 7
    assert vue["refus"] is None


def test_zero_heure_retire(base):
    svc.poser_heures_du_mois("co", 2026, 11, [{"employee_id": "e1", "heures": 7}], "u")
    res = svc.poser_heures_du_mois(
        "co", 2026, 11, [{"employee_id": "e1", "heures": 0}], "u"
    )
    assert res["resultats"][0]["statut"] == "retire"
    assert base.tables["monthly_inputs"] == []


def test_hors_periode_refuse(base):
    with pytest.raises(ValueError, match="avant le début"):
        svc.poser_heures_du_mois(
            "co", 2026, 5, [{"employee_id": "e1", "heures": 7}], "u"
        )


def test_bulletin_remis_intouche(base, monkeypatch):
    monkeypatch.setattr(svc, "_bulletin_remis", lambda eid, y, m: True)
    res = svc.poser_heures_du_mois(
        "co", 2026, 11, [{"employee_id": "e1", "heures": 7}], "u"
    )
    assert res["resultats"][0]["statut"] == "bulletin_remis"
    assert "monthly_inputs" not in base.tables or base.tables["monthly_inputs"] == []


# --- Activité partielle posée au calendrier ------------------------------------

AP = "activite_partielle"


def _jour(j, type_, h):
    return {"jour": j, "type": type_, "heures_prevues": h}


def test_calendrier_remplace_la_saisie_a_la_main(base):
    employe = base.tables["employees"][0]
    prevu = [_jour(2, AP, 7.0), _jour(3, AP, 7.0), _jour(4, "travail", 7.0)]
    reel = [{"jour": 3, "heures_faites": 3.0}, {"jour": 4, "heures_faites": 7.0}]
    manuelle = {"name": "Heures chômées (act. part.)", "amount": -100.0, "payroll_quantity": 7}
    prime = {"name": "Prime", "amount": 50.0}
    saisies, alerte = svc.lignes_du_calendrier(
        "co", employe, 2026, 11, prevu, reel, [manuelle, prime]
    )
    assert alerte is None
    assert prime in saisies and manuelle not in saisies
    retenue = next(s for s in saisies if s["name"] == "Heures chômées (act. part.)")
    indemnite = next(s for s in saisies if s["name"] == "Indemnité activité partielle")
    # 7 h le 2, 7 − 3 = 4 h le 3.
    assert retenue["payroll_quantity"] == 11
    assert retenue["amount"] == pytest.approx(-11 * 2166.67 / (35 * 52 / 12), abs=0.01)
    assert indemnite["amount"] > 0 and indemnite["is_socially_taxed"] is False


def test_sans_jour_au_calendrier_la_saisie_a_la_main_reste(base):
    employe = base.tables["employees"][0]
    manuelle = {"name": "Heures chômées (act. part.)", "amount": -100.0}
    saisies, alerte = svc.lignes_du_calendrier(
        "co", employe, 2026, 11, [_jour(2, "travail", 7.0)], [], [manuelle]
    )
    assert saisies == [manuelle] and alerte is None


def test_jour_pose_sans_heures_vaut_une_journee(base):
    employe = base.tables["employees"][0]
    saisies, _ = svc.lignes_du_calendrier(
        "co", employe, 2026, 11, [_jour(2, AP, None)], [], []
    )
    assert saisies[0]["payroll_quantity"] == 7.0


def test_hors_reglage_paye_et_alerte(base):
    employe = base.tables["employees"][0]
    saisies, alerte = svc.lignes_du_calendrier(
        "co", employe, 2026, 3, [_jour(2, AP, 7.0)], [], []
    )
    assert len(saisies) == 2
    assert alerte["code"] == "activite_partielle_hors_reglage"


def test_au_dela_de_35_h_le_bulletin_le_dit(base):
    """A4 (18/11) : à 39 h, la loi paie l'heure sur 151,67 h et n'indemnise
    les heures au-delà de 35 h que sur accord ; Martine calcule au taux du
    contrat et le dit, plutôt que de se taire."""
    employe = {**base.tables["employees"][0], "duree_hebdomadaire": 39}
    saisies, alerte = svc.lignes_du_calendrier(
        "co", employe, 2026, 11, [_jour(2, AP, 7.8)], [], []
    )
    assert len(saisies) == 2
    assert alerte["code"] == "activite_partielle_au_dela_de_35_h"
    assert "151,67 h" in alerte["message"] and alerte["critique"] is False


def test_au_dela_de_35_h_et_hors_reglage_une_seule_alerte_qui_dit_les_deux(base):
    employe = {**base.tables["employees"][0], "duree_hebdomadaire": 39}
    _, alerte = svc.lignes_du_calendrier("co", employe, 2026, 3, [_jour(2, AP, 7.8)], [], [])
    assert alerte["code"] == "activite_partielle_hors_reglage"
    assert "151,67 h" in alerte["message"]


def test_a_35_h_ou_au_forfait_pas_d_alerte(base):
    employe = base.tables["employees"][0]
    _, alerte = svc.lignes_du_calendrier("co", employe, 2026, 11, [_jour(2, AP, 7.0)], [], [])
    assert alerte is None
    assert svc._au_dela_de_la_duree_legale({"duree_hebdomadaire": 39, "is_forfait_jour": True}) is None


def test_sans_salaire_alerte_critique(base):
    employe = {**base.tables["employees"][0], "salaire_de_base": None}
    saisies, alerte = svc.lignes_du_calendrier(
        "co", employe, 2026, 11, [_jour(2, AP, 7.0)], [], []
    )
    assert saisies == [] and alerte["critique"] is True


def test_recap_du_mois_lit_le_calendrier(base):
    base.tables["employee_schedules"] = [
        {
            "employee_id": "e1",
            "year": 2026,
            "month": 11,
            "planned_calendar": {"calendrier_prevu": [_jour(2, AP, 7.0), _jour(3, AP, 7.0)]},
            "actual_hours": {"calendrier_reel": []},
        }
    ]
    vue = svc.lister_mois("co", 2026, 11)
    cal = vue["salaries"][0]["calendrier"]
    assert cal["jours"] == [2, 3] and cal["heures"] == 14.0 and cal["retenue"] > 0


def test_forfait_jours_un_jour_vaut_7_h():
    from app.modules.activite_partielle.domain.calendrier import heures_chomees, jours_chomes

    prevu = [_jour(2, AP, 1), _jour(3, AP, 1)]
    reel = [{"jour": 3, "heures_faites": 0.5}]
    jours = jours_chomes(prevu, reel, forfait_jours=True, heures_par_jour=7)
    assert heures_chomees(jours) == 10.5


# --- Lyon, 17/11 : un jour chômé compte dans le bulletin qui retient les
# absences de ce même jour, ni deux fois, ni jamais. ------------------------

from datetime import date  # noqa: E402


def _jour_de(an, mois, j, type_=AP, h=7.0):
    return {"annee": an, "mois": mois, "jour": j, "type": type_, "heures_prevues": h}


def test_les_jours_suivent_la_periode_du_bulletin(base):
    """Fenêtre d'octobre du 21/09 au 25/10 : le 28/09 et le 2/10 y sont, le
    28/10 part au bulletin de novembre."""
    employe = base.tables["employees"][0]
    prevu = [_jour_de(2026, 9, 28), _jour_de(2026, 10, 2), _jour_de(2026, 10, 28)]
    saisies, _ = svc.lignes_du_calendrier(
        "co", employe, 2026, 10, prevu, [], [], bornes=(date(2026, 9, 21), date(2026, 10, 25))
    )
    assert saisies[0]["payroll_quantity"] == 14.0
    novembre, _ = svc.lignes_du_calendrier(
        "co", employe, 2026, 11, prevu, [], [], bornes=(date(2026, 10, 26), date(2026, 11, 22))
    )
    assert novembre[0]["payroll_quantity"] == 7.0


def test_le_premier_mois_apres_la_reprise_ne_repaie_pas_l_ancien_logiciel(base, monkeypatch):
    """LEWIS : bascule au 30/09, Quadra a payé l'activité partielle de septembre."""
    import app.shared.reprise_paie as reprise

    monkeypatch.setattr(
        reprise, "fin_de_la_reprise_au_premier_mois", lambda *a, **k: date(2026, 9, 30)
    )
    employe = base.tables["employees"][0]
    prevu = [_jour_de(2026, 9, 28), _jour_de(2026, 10, 2)]
    saisies, _ = svc.lignes_du_calendrier(
        "co", employe, 2026, 10, prevu, [], [], bornes=(date(2026, 9, 21), date(2026, 10, 25))
    )
    assert saisies[0]["payroll_quantity"] == 7.0


def test_une_demi_journee_se_lit_sur_le_bon_mois(base):
    """Le 2/09 et le 2/10 ont le même numéro de jour : les heures faites du 2/10
    ne réduisent pas le 2/09."""
    employe = base.tables["employees"][0]
    prevu = [_jour_de(2026, 9, 2), _jour_de(2026, 10, 2)]
    reel = [{"annee": 2026, "mois": 10, "jour": 2, "heures_faites": 3.5}]
    saisies, _ = svc.lignes_du_calendrier(
        "co", employe, 2026, 10, prevu, reel, [], bornes=(date(2026, 9, 1), date(2026, 10, 31))
    )
    assert saisies[0]["payroll_quantity"] == 10.5


# --- Mois entier chômé (R5122-19, al. 2) : la durée d'un mois entier est la
# durée mensuelle du contrat, pas 22 × 7 h ; la retenue ne dépasse jamais le
# salaire du mois. Un profil en heures, un temps partiel, un forfait jours. ---


def _tout_le_mois(nb_jours=23, h=7.0):
    return [_jour(j, AP, h) for j in range(1, nb_jours + 1)]


def _deux(saisies):
    retenue = next(s for s in saisies if s["name"] == "Heures chômées (act. part.)")
    indemnite = next(s for s in saisies if s["name"] == "Indemnité activité partielle")
    return retenue, indemnite


def test_mois_entier_chome_en_heures_retient_le_salaire_et_pas_plus(base):
    employe = base.tables["employees"][0]
    saisies, _ = svc.lignes_du_calendrier("co", employe, 2026, 11, _tout_le_mois(), [], [])
    retenue, indemnite = _deux(saisies)
    assert retenue["payroll_quantity"] == 151.67
    assert retenue["amount"] == -2166.67
    assert indemnite["payroll_quantity"] == 151.67


def test_mois_entier_chome_a_temps_partiel_vaut_la_duree_du_contrat(base):
    employe = {
        **base.tables["employees"][0],
        "duree_hebdomadaire": "24",
        "salaire_de_base": {"valeur": 1300.0},
    }
    saisies, _ = svc.lignes_du_calendrier(
        "co", employe, 2026, 11, _tout_le_mois(h=4.8), [], []
    )
    retenue, _ = _deux(saisies)
    assert retenue["payroll_quantity"] == 104.0
    assert retenue["amount"] == -1300.0


def test_mois_entier_chome_au_forfait_jours_retient_le_salaire(base):
    employe = {
        **base.tables["employees"][0],
        "is_forfait_jour": True,
        "specificites_paie": {"forfait_annual_days": 218},
        "salaire_de_base": {"valeur": 3500.0},
    }
    saisies, _ = svc.lignes_du_calendrier(
        "co", employe, 2026, 11, _tout_le_mois(h=1), [], []
    )
    retenue, _ = _deux(saisies)
    assert retenue["payroll_quantity"] == 154.0
    assert retenue["amount"] == -3500.0


def test_mois_partiel_inchange_par_le_plafond(base):
    employe = base.tables["employees"][0]
    saisies, _ = svc.lignes_du_calendrier("co", employe, 2026, 11, _tout_le_mois(10), [], [])
    retenue, _ = _deux(saisies)
    assert retenue["payroll_quantity"] == 70.0
    assert retenue["amount"] == pytest.approx(-70 * 2166.67 / (35 * 52 / 12), abs=0.01)


# --- Sortie en cours de période : l'écran et la DSN lisent la sortie comme les
# deux générateurs (jours d'après écartés ; en heures, fenêtre jusqu'à la sortie). ---


def _jours_ap(employe, jours, mois=11):
    prevu = [_jour_de(2026, mois, j) for j in jours]
    res = svc.jours_chomes_des_bulletins(
        "co", 2026, mois, [employe], {employe["id"]: (prevu, [])}
    )
    return [d.day for d, _ in res.get(employe["id"], [])]


def test_sortie_en_heures_ecarte_les_jours_d_apres(base):
    employe = {**base.tables["employees"][0], "contract_end_date": "2026-11-12"}
    assert _jours_ap(employe, [10, 11, 13, 16]) == [10, 11]


def test_sortie_apres_la_fenetre_paie_jusqu_a_la_sortie(base, monkeypatch):
    monkeypatch.setattr(
        svc, "bornes_du_bulletin", lambda *a, **k: (date(2026, 10, 23), date(2026, 11, 19))
    )
    employe = {**base.tables["employees"][0], "contract_end_date": "2026-11-26"}
    assert _jours_ap(employe, [18, 20, 25, 27]) == [18, 20, 25]


def test_sortie_au_forfait_jours_ecarte_les_jours_d_apres(base):
    employe = {
        **base.tables["employees"][0],
        "is_forfait_jour": True,
        "specificites_paie": {"forfait_annual_days": 218},
        "contract_end_date": "2026-11-12",
    }
    assert _jours_ap(employe, [10, 13]) == [10]


def test_sortie_au_forfait_apres_la_periode_decalee_jusqu_a_la_sortie(base, monkeypatch):
    """A9 (18/11) : période du forfait au 25/11, sortie le 27/11 ; le bulletin
    paie jusqu'au 27, l'écran et la DSN aussi."""
    monkeypatch.setattr(
        svc, "bornes_du_bulletin", lambda *a, **k: (date(2026, 10, 26), date(2026, 11, 25))
    )
    employe = {
        **base.tables["employees"][0],
        "is_forfait_jour": True,
        "specificites_paie": {"forfait_annual_days": 218},
        "contract_end_date": "2026-11-27",
    }
    assert _jours_ap(employe, [24, 26, 27, 30]) == [24, 26, 27]


def test_un_nouveau_contrat_ne_compte_pas_les_jours_d_avant_son_entree(base, monkeypatch):
    """Relecture A9 (18/11) : période du 26/10 au 25/11, CDI au 02/11 ; les jours
    chômés d'avant l'entrée sont ceux de l'ancien contrat."""
    monkeypatch.setattr(
        svc, "bornes_du_bulletin", lambda *a, **k: (date(2026, 10, 26), date(2026, 11, 25))
    )
    employe = {**base.tables["employees"][0], "hire_date": "2026-11-02"}
    prevu = [_jour_de(2026, 10, 27), _jour_de(2026, 10, 30), _jour_de(2026, 11, 2), _jour_de(2026, 11, 3)]
    res = svc.jours_chomes_des_bulletins("co", 2026, 11, [employe], {employe["id"]: (prevu, [])})
    assert [(d.month, d.day) for d, _ in res[employe["id"]]] == [(11, 2), (11, 3)]
    saisies, _ = svc.lignes_du_calendrier(
        "co", employe, 2026, 11, prevu, [], [], bornes=(date(2026, 10, 26), date(2026, 11, 25))
    )
    assert saisies[0]["payroll_quantity"] == 14.0


def test_sans_sortie_rien_ne_change(base):
    assert _jours_ap(base.tables["employees"][0], [10, 13]) == [10, 13]


# --- Relecture du 17/11 au soir : le plafond retire les heures non chômées du
# mois, et ne joue que sur un mois civil entier sous contrat. ---


def test_un_jour_travaille_sort_du_plafond(base):
    employe = base.tables["employees"][0]
    prevu = _tout_le_mois(22) + [_jour(24, "travail", 7.0)]
    reel = [{"jour": 24, "heures_faites": 7.0}]
    saisies, _ = svc.lignes_du_calendrier("co", employe, 2026, 11, prevu, reel, [])
    retenue, indemnite = _deux(saisies)
    # 151,67 h − 7 h travaillées : 144,67 h chômées, pas 154 h ni 151,67 h.
    assert retenue["payroll_quantity"] == 144.67
    assert retenue["amount"] == pytest.approx(-144.67 * 2166.67 / (35 * 52 / 12), abs=0.01)
    assert indemnite["payroll_quantity"] == 144.67


def test_un_jour_de_conge_sort_aussi_du_plafond(base):
    employe = base.tables["employees"][0]
    # Le 30/11/2026 est un lundi : un congé posé à 0 h vaut une journée.
    prevu = _tout_le_mois(22) + [_jour(30, "conges_payes", 0.0)]
    saisies, _ = svc.lignes_du_calendrier("co", employe, 2026, 11, prevu, [], [])
    retenue, _ = _deux(saisies)
    assert retenue["payroll_quantity"] == 144.67


def test_mois_d_entree_sans_plafond(base):
    employe = {**base.tables["employees"][0], "hire_date": "2026-11-02"}
    saisies, _ = svc.lignes_du_calendrier("co", employe, 2026, 11, _tout_le_mois(22), [], [])
    retenue, _ = _deux(saisies)
    # Le 01/11, d'avant l'entrée, ne compte pas (relecture A9, 18/11) : 21 jours.
    assert retenue["payroll_quantity"] == 147.0


def test_periode_decalee_sans_plafond(base):
    employe = base.tables["employees"][0]
    prevu = [_jour_de(2026, 10, j) for j in (26, 27, 28, 29, 30)] + [
        _jour_de(2026, 11, j) for j in range(1, 21)
    ]
    saisies, _ = svc.lignes_du_calendrier(
        "co", employe, 2026, 11, prevu, [], [], bornes=(date(2026, 10, 23), date(2026, 11, 19))
    )
    retenue, _ = _deux(saisies)
    # Semaines entières, pas un mois (R5122-19) : les jours comptent.
    assert retenue["payroll_quantity"] == 7.0 * 24


def test_la_dsn_et_l_ecran_comptent_les_heures_du_bulletin(base):
    employe = base.tables["employees"][0]
    prevu = [_jour_de(2026, 11, j) for j in range(1, 24)]
    jours = svc.jours_chomes_des_bulletins("co", 2026, 11, [employe], {"e1": (prevu, [])})["e1"]
    assert len(jours) == 23
    assert round(sum(h for _, h in jours), 2) == 151.67


def test_saisie_a_la_main_au_dela_du_mois_le_dit(base):
    res = svc.poser_heures_du_mois("co", 2026, 11, [{"employee_id": "e1", "heures": 160}], "u")
    (r,) = res["resultats"]
    assert r["heures"] == 151.67
    assert r["message"].startswith("160 h saisies, ramenées à 151,67 h")


# --- Deuxième relecture du 17/11 : période décalée, février, heures sup,
# temps partiel, forfait en heures, saisie à la main d'un mois d'entrée. ---


def _calendrier(an, mois, debut, fin, type_ouvre=AP, h=7.0, autres=None):
    """Un jour par date, du lundi au vendredi `type_ouvre`, le week-end « weekend »."""
    from datetime import timedelta

    autres = autres or {}
    jours, jour = [], debut
    while jour <= fin:
        if jour in autres:
            type_, heures = autres[jour]
        elif jour.weekday() < 5:
            type_, heures = type_ouvre, h
        else:
            type_, heures = "weekend", 0.0
        jours.append({"annee": jour.year, "mois": jour.month, "jour": jour.day, "type": type_, "heures_prevues": heures})
        jour += timedelta(days=1)
    return jours


def test_fevrier_entierement_chome_retient_le_mois(base):
    employe = base.tables["employees"][0]
    prevu = _calendrier(2026, 2, date(2026, 2, 1), date(2026, 2, 28))
    saisies, _ = svc.lignes_du_calendrier("co", employe, 2026, 2, prevu, [], [])
    retenue, indemnite = _deux(saisies)
    # 20 jours ouvrés (140 h), mais un mois entier vaut 151,67 h (R5122-19).
    assert retenue["payroll_quantity"] == 151.67 and indemnite["payroll_quantity"] == 151.67
    assert retenue["amount"] == -2166.67


@pytest.mark.parametrize(
    "debut, fin, heures",
    [(date(2026, 9, 19), date(2026, 10, 23), 175.0), (date(2026, 10, 24), date(2026, 11, 20), 140.0)],
)
def test_periode_decalee_entierement_chomee_retient_le_salaire(base, debut, fin, heures):
    employe = base.tables["employees"][0]
    prevu = _calendrier(fin.year, fin.month, debut, fin)
    saisies, _ = svc.lignes_du_calendrier(
        "co", employe, fin.year, fin.month, prevu, [], [], bornes=(debut, fin)
    )
    retenue, indemnite = _deux(saisies)
    # Semaines entières : les jours comptent ; la retenue est le salaire, ni plus ni moins.
    assert indemnite["payroll_quantity"] == heures
    assert retenue["amount"] == -2166.67


def test_periode_decalee_en_partie_chomee_ne_retient_pas_plus_que_le_salaire(base):
    employe = base.tables["employees"][0]
    debut, fin = date(2026, 9, 19), date(2026, 10, 23)
    prevu = _calendrier(2026, 10, debut, fin, autres={date(2026, 10, 23): ("travail", 7.0)})
    saisies, _ = svc.lignes_du_calendrier("co", employe, 2026, 10, prevu, [], [], bornes=(debut, fin))
    retenue, _ = _deux(saisies)
    assert retenue["payroll_quantity"] == 168.0
    assert retenue["amount"] == -2166.67
    assert "ramenée au salaire du mois" in retenue["description"]


def test_les_heures_sup_ne_mangent_pas_le_jour_chome(base):
    employe = base.tables["employees"][0]
    debut, fin = date(2026, 11, 1), date(2026, 11, 30)
    autres = {date(2026, 11, 2): (AP, 7.0), date(2026, 11, 11): ("ferie", None)}
    prevu = _calendrier(2026, 11, debut, fin, type_ouvre="travail", autres=autres)
    reel = [{"annee": 2026, "mois": 11, "jour": j["jour"], "heures_faites": 8.0} for j in prevu if j["type"] == "travail"]
    saisies, alerte = svc.lignes_du_calendrier("co", employe, 2026, 11, prevu, reel, [])
    retenue, _ = _deux(saisies)
    assert retenue["payroll_quantity"] == 7.0 and alerte is None


def test_plafond_a_zero_le_dit(base):
    employe = base.tables["employees"][0]
    debut, fin = date(2026, 11, 1), date(2026, 11, 30)
    # 21 jours ouvrés : 20 travaillés à 7 h (140 h) + 1 férié (7 h) dépassent 151,67 h − 7.
    autres = {date(2026, 11, 2): (AP, 7.0), date(2026, 11, 11): ("ferie", None), date(2026, 11, 28): ("travail", 7.0)}
    prevu = _calendrier(2026, 11, debut, fin, type_ouvre="travail", autres=autres)
    prevu += [{"annee": 2026, "mois": 11, "jour": 29, "type": "travail", "heures_prevues": 7.0}]
    saisies, alerte = svc.lignes_du_calendrier("co", employe, 2026, 11, prevu, [], [])
    assert not [s for s in saisies if s.get("name", "").startswith(("Heures chômées", "Indemnité activité"))]
    assert alerte["code"] == "activite_partielle_sans_heure"


def test_temps_partiel_un_ferie_non_travaille_ne_compte_pas(base):
    employe = {**base.tables["employees"][0], "duree_hebdomadaire": "24", "salaire_de_base": {"valeur": 1300.0}}
    debut, fin = date(2026, 12, 1), date(2026, 12, 31)
    prevu = [
        j if date(2026, 12, j["jour"]).weekday() < 3 else {**j, "type": "", "heures_prevues": 0.0}
        for j in _calendrier(2026, 12, debut, fin, h=8.0)
    ]
    prevu = [{**j, "type": "ferie", "heures_prevues": None} if j["jour"] == 25 else j for j in prevu]
    saisies, _ = svc.lignes_du_calendrier("co", employe, 2026, 12, prevu, [], [])
    retenue, _ = _deux(saisies)
    assert retenue["payroll_quantity"] == 104.0
    assert retenue["amount"] == -1300.0


def test_forfait_un_jour_de_travail_prevu_en_heures_compte(base):
    employe = {
        **base.tables["employees"][0],
        "is_forfait_jour": True,
        "specificites_paie": {"forfait_annual_days": 218},
        "salaire_de_base": {"valeur": 4200.0},
    }
    debut, fin = date(2026, 11, 1), date(2026, 11, 30)
    autres = {date(2026, 11, 30): ("travail", 7.0)}
    prevu = _calendrier(2026, 11, debut, fin, h=1, autres=autres)
    saisies, _ = svc.lignes_du_calendrier("co", employe, 2026, 11, prevu, [], [])
    retenue, _ = _deux(saisies)
    # 20 jours chômés (140 h) sous le plafond 154 − 7 : les jours comptent.
    assert retenue["payroll_quantity"] == 140.0


def test_saisie_a_la_main_un_mois_d_entree_n_est_pas_bornee_au_mois(base):
    base.tables["employees"][0]["hire_date"] = "2026-11-16"
    res = svc.poser_heures_du_mois("co", 2026, 11, [{"employee_id": "e1", "heures": 151.67}], "u")
    (r,) = res["resultats"]
    assert "message" not in r


def test_la_dsn_porte_les_heures_du_bulletin_en_fevrier(base):
    employe = base.tables["employees"][0]
    prevu = _calendrier(2026, 2, date(2026, 2, 1), date(2026, 2, 28))
    jours = svc.jours_chomes_des_bulletins("co", 2026, 2, [employe], {"e1": (prevu, [])})["e1"]
    assert round(sum(h for _, h in jours), 2) == 151.67


# --- Troisième relecture du 17/11 : férié ou congé dans un mois chômé, sortie
# après une fenêtre décalée, mention d'arrondi, heures faites un jour de repos. ---

TAUX_2166 = 2166.67 / (35 * 52 / 12)


def test_mois_chome_avec_un_ferie_retient_le_mois_moins_le_ferie(base):
    employe = base.tables["employees"][0]
    prevu = _calendrier(
        2026, 11, date(2026, 11, 1), date(2026, 11, 30), autres={date(2026, 11, 11): ("ferie", None)}
    )
    saisies, _ = svc.lignes_du_calendrier("co", employe, 2026, 11, prevu, [], [])
    retenue, indemnite = _deux(saisies)
    # 151,67 h − 7 h fériées, pas les 20 jours chômés (140 h).
    assert retenue["payroll_quantity"] == 144.67 and indemnite["payroll_quantity"] == 144.67
    assert retenue["amount"] == pytest.approx(-144.67 * TAUX_2166, abs=0.01)
    jours = svc.jours_chomes_des_bulletins("co", 2026, 11, [employe], {"e1": (prevu, [])})["e1"]
    assert round(sum(h for _, h in jours), 2) == 144.67


def test_fevrier_chome_avec_un_conge_retient_le_mois_moins_le_conge(base):
    employe = base.tables["employees"][0]
    prevu = _calendrier(
        2026, 2, date(2026, 2, 1), date(2026, 2, 28), autres={date(2026, 2, 2): ("conges_payes", 7.0)}
    )
    saisies, _ = svc.lignes_du_calendrier("co", employe, 2026, 2, prevu, [], [])
    retenue, _ = _deux(saisies)
    assert retenue["payroll_quantity"] == 144.67


def test_sortie_apres_une_fenetre_decalee_ne_retient_pas_le_salaire_entier(base):
    # Fenêtre arrêtée au 21/11, repoussée jusqu'à la sortie du 25/11 (fin_au_depart) :
    # le bulletin est proratisé, la retenue n'est pas ramenée au salaire de la fiche.
    employe = {**base.tables["employees"][0], "contract_end_date": "2026-11-25"}
    debut, fin = date(2026, 10, 22), date(2026, 11, 25)
    prevu = _calendrier(2026, 11, debut, fin)
    saisies, _ = svc.lignes_du_calendrier("co", employe, 2026, 11, prevu, [], [], bornes=(debut, fin))
    retenue, _ = _deux(saisies)
    assert retenue["payroll_quantity"] == 175.0
    assert retenue["amount"] == pytest.approx(-175 * TAUX_2166, abs=0.01)


def test_mois_entier_chome_sans_mention_d_arrondi(base):
    employe = {**base.tables["employees"][0], "salaire_de_base": {"valeur": 2000.0}}
    prevu = _calendrier(2026, 2, date(2026, 2, 1), date(2026, 2, 28))
    saisies, _ = svc.lignes_du_calendrier("co", employe, 2026, 2, prevu, [], [])
    retenue, _ = _deux(saisies)
    assert retenue["amount"] == -2000.0
    assert "ramenée" not in retenue["description"]


def test_heures_faites_un_jour_de_repos_ne_sont_pas_chomees(base):
    employe = base.tables["employees"][0]
    prevu = _calendrier(
        2026, 11, date(2026, 11, 1), date(2026, 11, 30), autres={date(2026, 11, 30): ("repos", 0.0)}
    )
    reel = [{"annee": 2026, "mois": 11, "jour": 30, "heures_faites": 7.0}]
    saisies, _ = svc.lignes_du_calendrier("co", employe, 2026, 11, prevu, reel, [])
    retenue, _ = _deux(saisies)
    # 20 jours chômés (140 h) : le jour de repos travaillé n'est ni chômé ni
    # « rien de travaillé » ; le mois n'est pas retenu en entier (151,67 h avant).
    assert retenue["payroll_quantity"] == 140.0
    assert retenue["amount"] == pytest.approx(-140 * TAUX_2166, abs=0.01)


def test_sortie_le_dernier_jour_apres_une_fenetre_decalee_compte_les_jours(base):
    # Quatrième relecture : sortie le 30/11, fenêtre 23/10–19/11 repoussée au 30/11 :
    # 27 jours ouvrés rattrapés, comptés un par un (pas ramenés au salaire).
    employe = {**base.tables["employees"][0], "contract_end_date": "2026-11-30"}
    debut, fin = date(2026, 10, 23), date(2026, 11, 30)
    prevu = _calendrier(2026, 11, debut, fin)
    saisies, _ = svc.lignes_du_calendrier("co", employe, 2026, 11, prevu, [], [], bornes=(debut, fin))
    retenue, _ = _deux(saisies)
    assert retenue["payroll_quantity"] == 7.0 * 27
    assert retenue["amount"] == pytest.approx(-189 * TAUX_2166, abs=0.01)


def test_sortie_le_dernier_jour_d_un_mois_civil_reste_un_mois_entier(base):
    employe = {**base.tables["employees"][0], "contract_end_date": "2026-11-30"}
    prevu = _calendrier(2026, 11, date(2026, 11, 1), date(2026, 11, 30))
    saisies, _ = svc.lignes_du_calendrier("co", employe, 2026, 11, prevu, [], [])
    retenue, _ = _deux(saisies)
    assert retenue["payroll_quantity"] == 151.67 and retenue["amount"] == -2166.67
