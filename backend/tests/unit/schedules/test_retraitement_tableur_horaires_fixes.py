"""Retraitement d'un relevé de badgeuse à horaires fixes (règle du 19/06/2026).

Cas tirés du rejeu à blanc des relevés de janvier à juin 2026 d'une société
à trois postes (journée, équipe du matin, équipe de l'après-midi) : le
moteur doit ramener chaque journée à l'horaire, signaler les heures en plus
au-delà de la tolérance, et ne jamais payer plus que le temps pointé.
"""

from app.modules.schedules.domain.punch_accounting_entities import (
    PunchAccountingSettings,
    PunchDayInput,
)
from app.modules.schedules.domain.punch_accounting_rules import (
    compute_from_raw_times,
    compute_punch_day,
    slot_from_row,
)

# Horaires de l'accord (hors activité partielle) : journée 8 h-16 h 30
# (7,75 h, 45 min de pause déduites) ; équipes 4 h-12 h et 12 h-20 h
# (7,75 h payées : 15 min déduites, déjeuner payé).
CRENEAUX_ACCORD = [
    {"id": "journee", "code": "A", "entry_time": "08:00", "exit_time": "16:30",
     "theoretical_gross_minutes": 510, "break_deduct_minutes": 45, "sort_order": 0},
    {"id": "matin", "code": "B", "entry_time": "04:00", "exit_time": "12:00",
     "theoretical_gross_minutes": 480, "break_deduct_minutes": 15,
     "paid_lunch_break": True, "sort_order": 1},
    {"id": "apres_midi", "code": "B", "entry_time": "12:00", "exit_time": "20:00",
     "theoretical_gross_minutes": 480, "break_deduct_minutes": 15,
     "paid_lunch_break": True, "sort_order": 2},
]

REGLAGE = PunchAccountingSettings(
    enabled=True,
    tolerance_minutes=30,
    default_break_deduct_minutes=45,
    slot_detection="nearest_entry",
)


def _creneaux():
    return [slot_from_row(r) for r in CRENEAUX_ACCORD]


def _jour(entree, sortie, code=None, **kw):
    return compute_from_raw_times(
        entry_raw=entree, exit_raw=sortie, shift_code=code,
        settings=REGLAGE, slots=_creneaux(), **kw,
    )


class TestChoixDuCreneauParEntreeEtSortie:
    def test_arrivee_tres_tot_puis_sortie_de_journee_reste_sur_la_journee(self):
        # 5 h 29 → 16 h 30 : une journée commencée 2 h 31 plus tôt, pas une
        # équipe du matin sortie 4 h 30 en retard.
        r = _jour(529, 1630)
        assert r.applied_slot_id == "journee"
        assert r.overtime_reason == "early_entry"
        assert r.overtime_hours == 2.52
        assert r.needs_review

    def test_arrivee_avant_midi_et_sortie_a_20h_est_l_equipe_d_apres_midi(self):
        r = _jour(956, 2000)
        assert r.applied_slot_id == "apres_midi"
        assert r.overtime_reason == "early_entry"

    def test_le_code_horaire_ne_force_pas_le_creneau_en_mode_horaire_le_plus_proche(self):
        # Code « B » (équipe) sur une journée 7 h 54 → 16 h 30 : payée à l'horaire.
        r = _jour(754, 1630, code="B")
        assert r.applied_slot_id == "journee"
        assert r.accounted_hours == 7.75
        assert r.overtime_hours == 0.0


class TestPointageIncomplet:
    def test_un_seul_badge_n_est_pas_une_journee_de_23_heures(self):
        r = _jour(1128, 1128)
        assert r.is_incomplete
        assert r.accounted_hours == 0.0
        assert r.overtime_hours == 0.0
        assert not r.needs_review

    def test_une_entree_sans_sortie_est_incomplete_pas_absente(self):
        r = _jour(800, 0)
        assert r.is_incomplete
        assert not r.is_absent

    def test_une_sortie_sans_entree_est_incomplete(self):
        r = _jour(0, 400)
        assert r.is_incomplete
        assert not r.is_absent

    def test_aucun_badge_reste_une_journee_sans_pointage(self):
        r = _jour(0, 0)
        assert r.is_absent
        assert not r.is_incomplete


class TestHeuresEnPlusJamaisAuDelaDuPointe:
    def test_retard_le_matin_compense_la_sortie_tardive(self):
        # 8 h 40 → 17 h 15 : 45 min de dépassement le soir, mais 40 min de
        # retard le matin ; pointé 7,83 h pour 7,75 h théoriques : rien à valider.
        r = _jour(840, 1715)
        assert r.overtime_hours == 0.0
        assert not r.needs_review
        assert r.accounted_hours == 7.75

    def test_heures_en_plus_ramenees_au_temps_reellement_fait(self):
        # 8 h 40 → 18 h 00 : 1 h 30 de dépassement, 40 min de retard ;
        # fait en plus : 8,58 − 7,75 = 0,83 h.
        r = _jour(840, 1800)
        assert r.overtime_hours == 0.83
        assert r.needs_review
        assert r.accounted_hours == 7.75

    def test_avance_seule_inchangee(self):
        r = _jour(720, 1630)
        assert r.overtime_hours == 0.67
        assert r.overtime_reason == "early_entry"


class TestPausePlafonneeALaPausePointee:
    def test_demi_journee_sans_dejeuner_ne_perd_que_la_pause_pointee(self):
        # 8 h → 10 h, 10 h 15 → 12 h 17 : 15 min de pause pointées, pas 45.
        r = _jour(800, 1217, punched_break_minutes=15)
        assert r.pointed_net_hours == 4.03
        assert r.accounted_hours == 4.03

    def test_pause_pointee_plus_longue_que_le_creneau_garde_la_pause_du_creneau(self):
        # Journée complète, déjeuner d'une heure : payée à l'horaire.
        r = _jour(800, 1630, punched_break_minutes=75)
        assert r.accounted_hours == 7.75

    def test_sans_pause_pointee_la_pause_du_creneau_s_applique(self):
        r = _jour(800, 1217)
        assert r.pointed_net_hours == 3.53

    def test_journee_complete_sans_pause_du_matin_badgee_reste_payee_a_l_horaire(self):
        # 7 h 35 → 16 h 30, seul le déjeuner badgé (30 min) : la règle de la
        # journée (−0,75 h) s'applique, rien « en plus ».
        r = _jour(735, 1630, punched_break_minutes=30)
        assert r.accounted_hours == 7.75
        assert r.overtime_hours == 0.0
        assert not r.needs_review

    def test_pause_pointee_garde_la_detection_avance_et_depassement(self):
        r = compute_punch_day(
            PunchDayInput(entry_minutes=7 * 60 + 20, exit_minutes=16 * 60 + 30,
                          punched_break_minutes=45),
            REGLAGE, _creneaux(),
        )
        assert r.overtime_reason == "early_entry"
        assert r.overtime_hours == 0.67


class TestPauseBadgeeLongue:
    def test_une_longue_pause_badgee_annule_les_heures_en_plus(self):
        # 6 h 59 → 16 h 30 avec 1 h 47 de pauses badgées : 7,73 h faites.
        r = _jour(659, 1630, punched_break_minutes=107)
        assert r.overtime_hours == 0.0
        assert not r.needs_review
        assert r.accounted_hours == 7.75

    def test_le_dejeuner_paye_des_equipes_ne_compte_pas_comme_pause(self):
        # Équipe 4 h → 14 h 02, 45 min badgées dont 30 de déjeuner payé.
        creneaux = [
            slot_from_row({**r, "paid_break_minutes": 30} if r["id"] != "journee" else r)
            for r in CRENEAUX_ACCORD
        ]
        r = compute_from_raw_times(
            entry_raw=400, exit_raw=1402, shift_code=None, settings=REGLAGE,
            slots=creneaux, punched_break_minutes=45,
        )
        assert r.applied_slot_id == "matin"
        assert r.overtime_hours == 2.03
