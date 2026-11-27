"""Heures retenues par le client dans son fichier de pointage (lot L16, 27/11).

Certains relevés Excel portent, après le total pointé (« Tot H Poin »), une
colonne d'heures décidées par le client : sans en-tête, ou titrée « Total
heures ». C'est elle qui fait foi. Le lecteur la retrouve par sa place (après
les heures pointées, avant les commentaires) et la confirme par les lignes de
total de chaque salarié ; le calcul des badges ne réécrit pas ces jours.

Classeurs synthétiques, salariés pseudonymes.
"""

from datetime import datetime
from io import BytesIO
from unittest.mock import patch

from openpyxl import Workbook

from app.modules.schedules.application.timesheet_import.structured_parser import (
    detect_column_mapping,
    parse_tabular_file,
)

BADGES = ("Entrée 1.", "Sortie 1.", "Entrée 2.", "Sortie 2.", "Entrée 3.", "Sortie 3.")

# Trois mises en page vues chez le même client.
AVEC_SECTION = [  # semaine 39 : une colonne de section décale tout
    "Jour", "Nom", "Cod Sectio", "Entrée 1.", "Sortie 1.", None, "Entrée 2.",
    "Sortie 2.", None, "Entrée 3.", "Sortie 3.", None, "Tot H Poin",
    "Hr Théoriq", None, "Commentaires", "Retour",
]
SANS_TITRE = [  # semaines 40-41 : la colonne retenue n'a pas d'en-tête
    "Jour", "Nom", "Entrée 1.", "Sortie 1.", None, "Entrée 2.", "Sortie 2.",
    None, "Entrée 3.", "Sortie 3.", None, "Tot H Poin", None, "Commentaires",
    "Retour",
]
TITREE = [  # semaines 42-43 : « Total heures »
    "Jour", "Nom", "Entrée 1.", "Sortie 1.", None, "Entrée 2.", "Sortie 2.",
    None, "Entrée 3.", "Sortie 3.", None, "Tot H Poin", "Total heures",
    "Commentaires", "Retour",
]


def _jour(j, badges, pointe, retenue, commentaire=None):
    return {"date": datetime(2026, 10, j), "badges": badges, "pointe": pointe,
            "retenue": retenue, "commentaire": commentaire}


SALARIES = [
    ("Salarié Un", [
        # Retenue sous le pointé, dans la tolérance : 6,75 et non 7.
        _jour(1, (815, 1000, 1015, 1230, 1300, 1547), 6.78, 6.75),
        # Retenue sous le pointé : 5,5 et non 6,28.
        _jour(2, (744, 1000, 1015, 1416, 0, 0), 6.28, 5.5),
        # Au-delà du théorique : 9,75 sans revue « heures en plus ».
        _jour(5, (800, 1000, 1015, 1230, 1300, 1834), 9.82, 9.75, "1 h sup accordée"),
    ]),
    ("Salarié Deux", [
        _jour(1, (800, 1000, 1015, 1230, 1300, 1545), 7.0, 7),
        # Badge incomplet : le client a retenu 7 h.
        _jour(2, (800, 0, 0, 0, 0, 0), 0, 7, "badge oublié"),
        # Retenue vide sur un jour badgé : repli sur le calcul des badges.
        _jour(5, (800, 1000, 1015, 1230, 1300, 1545), 7.0, None),
    ]),
    ("Salarié Trois", [
        _jour(1, (800, 1000, 1015, 1230, 1300, 1545), 7.0, 7),
        _jour(2, (800, 1000, 1015, 1230, 1300, 1546), 7.02, 7),
        _jour(5, (800, 1000, 1015, 1230, 1300, 1544), 6.98, 7),
    ]),
]


def _colonne_retenue(entete):
    i_pointe = entete.index("Tot H Poin")
    if "Total heures" in entete:
        return entete.index("Total heures")
    return next(i for i in range(i_pointe + 1, len(entete)) if entete[i] is None)


def _classeur(entete, salaries=SALARIES, *, total=None) -> bytes:
    """Une ligne par jour, puis une ligne de total (sans date ni nom) portant
    la somme de la colonne retenue — ou `total` pour la fausser."""
    wb = Workbook()
    ws = wb.active
    ws.append(entete)
    i_ret = _colonne_retenue(entete)
    for nom, jours in salaries:
        for j in jours:
            ligne = [None] * len(entete)
            for i, titre in enumerate(entete):
                if titre == "Jour":
                    ligne[i] = j["date"]
                elif titre == "Nom":
                    ligne[i] = nom
                elif titre == "Cod Sectio":
                    ligne[i] = "MONT"
                elif titre in BADGES:
                    ligne[i] = j["badges"][BADGES.index(titre)]
                elif titre == "Tot H Poin":
                    ligne[i] = j["pointe"]
                elif titre == "Hr Théoriq":
                    ligne[i] = 7.75
                elif titre == "Commentaires":
                    ligne[i] = j["commentaire"]
                elif titre is None and i < entete.index("Tot H Poin"):
                    # Colonnes sans titre entre les badges : heure arrondie,
                    # numérique elle aussi (le piège à ne pas prendre).
                    ligne[i] = round(j["badges"][0] / 100, 2)
            ligne[i_ret] = j["retenue"]
            ws.append(ligne)
        ligne_total = [None] * len(entete)
        ligne_total[i_ret] = (
            total if total is not None else sum(j["retenue"] or 0 for j in jours)
        )
        ws.append(ligne_total)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _lire(contenu: bytes):
    return parse_tabular_file(
        contenu, "pointage.xlsx", target_year=2026, target_month=10,
        options={"skip_period_filter": True},
    )


def _par_jour(res):
    return {(r.raw_name, r.jour): r for r in res.rows}


# --- Lecture ---------------------------------------------------------------


def test_les_trois_mises_en_page_lisent_les_heures_retenues():
    for entete in (AVEC_SECTION, SANS_TITRE, TITREE):
        res = _lire(_classeur(entete))
        jours = _par_jour(res)
        assert jours[("Salarié Un", 1)].heures == 6.75, entete
        assert jours[("Salarié Un", 1)].heures_retenues == 6.75
        assert jours[("Salarié Un", 2)].heures == 5.5
        assert jours[("Salarié Un", 5)].heures == 9.75
        assert jours[("Salarié Deux", 2)].heures == 7
        assert jours[("Salarié Trois", 2)].heures == 7


def test_les_badges_restent_lus():
    jours = _par_jour(_lire(_classeur(SANS_TITRE)))
    un = jours[("Salarié Un", 1)]
    assert (str(un.entry_raw), str(un.exit_raw)) == ("815", "1547")
    assert un.punched_break_minutes == 45


def test_les_lignes_de_total_ne_sont_pas_des_jours():
    for entete in (AVEC_SECTION, SANS_TITRE, TITREE):
        res = _lire(_classeur(entete))
        assert len(res.rows) == 9, entete
        assert not any("date illisible" in w for w in res.warnings)


def test_retenue_vide_sur_un_jour_badge_repli_et_avertissement():
    for entete in (AVEC_SECTION, SANS_TITRE, TITREE):
        jour = _par_jour(_lire(_classeur(entete)))[("Salarié Deux", 5)]
        assert jour.heures_retenues is None
        assert jour.heures == 7.0  # le total pointé, recalculé ensuite par les badges
        assert any("heures retenues" in n.lower() for n in jour.notes), entete


def test_colonne_sans_titre_non_confirmee_par_les_totaux_repli_et_avertissement():
    res = _lire(_classeur(SANS_TITRE, total=99))
    jours = _par_jour(res)
    assert jours[("Salarié Un", 1)].heures == 6.78
    assert all(r.heures_retenues is None for r in res.rows)
    assert any("heures retenues" in w.lower() for w in res.warnings)
    assert len(res.rows) == 9


def test_la_colonne_retenue_ne_se_devine_pas_par_sa_lettre():
    """Avec la colonne de section, la retenue est deux colonnes plus loin que
    dans la mise en page sans section : seule la structure la trouve."""
    res = _lire(_classeur(AVEC_SECTION))
    assert res.column_mapping.get("hours_retained")
    assert res.column_mapping["hours"] == "Tot H Poin"


def test_mapping_total_heures_a_cote_du_pointe():
    mapping = detect_column_mapping([h or "" for h in TITREE])
    assert mapping["hours"] == "Tot H Poin"
    assert mapping["hours_retained"] == "Total heures"


def test_total_heures_seul_reste_la_colonne_des_heures():
    """Un relevé dont la seule colonne d'heures s'appelle « Total heures »."""
    mapping = detect_column_mapping(["Date", "Nom", "Total heures"])
    assert mapping["hours"] == "Total heures"
    assert "hours_retained" not in mapping


def test_un_releve_sans_colonne_retenue_ne_change_pas():
    entete = "Matricule;Jour;Nom;Entrée 1.;Sortie 1.;Entrée 2.;Sortie 2.;Entrée 3.;Sortie 3.;Tot H Poin;Hr Théoriq"
    contenu = "\n".join([
        entete,
        "000001;01/10/2026;Salarié Un;815;1000;1015;1230;1300;1547;6,78;7,75",
    ]).encode("utf-8")
    res = parse_tabular_file(contenu, "releve.csv", target_year=2026, target_month=10,
                             options={"skip_period_filter": True})
    assert res.rows[0].heures == 6.78
    assert res.rows[0].heures_retenues is None
    assert res.warnings == []


# --- Proposition ----------------------------------------------------------


def test_la_proposition_drapeaute_les_jours_fixes_par_le_fichier():
    from app.modules.schedules.application.timesheet_import.proposal_builder import (
        build_proposal_from_tabular,
    )

    prop = build_proposal_from_tabular(_lire(_classeur(SANS_TITRE)), year=2026, month=10, roster=[])
    jours = {(e.raw_name, d.jour): d for e in prop.employees for d in e.days}
    assert jours[("Salarié Un", 1)].heures_fixees_par_fichier is True
    assert jours[("Salarié Un", 1)].punch_entry_raw == "815"
    assert jours[("Salarié Deux", 5)].heures_fixees_par_fichier is False
    deux = next(e for e in prop.employees if e.raw_name == "Salarié Deux")
    assert any(w.startswith("Jour 5 :") and "heures retenues" in w.lower() for w in deux.warnings)


def test_les_groupes_multi_mois_drapeautent_aussi():
    from app.modules.schedules.application.timesheet_import.multi_month import (
        build_month_groups_from_rows,
    )

    groupes = build_month_groups_from_rows(_lire(_classeur(TITREE)).rows, [])
    jours = [d for g in groupes for e in g["employees"] for d in e["days"]]
    assert any(d["heures_fixees_par_fichier"] and d["heures"] == 6.75 for d in jours)


# --- Calcul des badges ----------------------------------------------------


def _reglages():
    from app.modules.schedules.domain.punch_accounting_entities import PunchAccountingSettings

    return PunchAccountingSettings(
        enabled=True, tolerance_minutes=30, default_break_deduct_minutes=45,
        break_threshold_minutes=0, use_last_nonzero_exit=True,
        slot_detection="nearest_entry", within_tolerance_pay_theoretical=True,
        require_manager_validation_for_overtime=True,
    )


def _creneau():
    from app.modules.schedules.domain.punch_accounting_rules import slot_from_row

    return [slot_from_row({
        "id": "A", "code": "A", "entry_time": "08:00", "exit_time": "15:45",
        "theoretical_gross_minutes": 465, "break_deduct_minutes": 45,
    })]


@patch("app.modules.schedules.application.punch_accounting_service.repo.get_overtime_review")
@patch("app.modules.schedules.application.punch_accounting_service.repo.list_slots")
@patch("app.modules.schedules.application.punch_accounting_service.repo.get_settings")
def test_un_jour_fixe_par_le_fichier_garde_ses_heures(mock_settings, mock_slots, mock_revue):
    from app.modules.schedules.application.punch_accounting_service import (
        apply_punch_accounting_to_proposal,
    )
    from app.modules.schedules.schemas.ai import (
        AiCalendarProposalResponse,
        AiDayEntry,
        AiEmployeeProposal,
    )

    mock_settings.return_value = _reglages()
    mock_slots.return_value = _creneau()
    mock_revue.return_value = None
    prop = AiCalendarProposalResponse(
        year=2026, month=10, source="relevé",
        employees=[AiEmployeeProposal(raw_name="Salarié Un", employee_id="e1", days=[
            AiDayEntry(jour=1, heures=6.75, punch_entry_raw="815", punch_exit_raw="1547",
                       punch_break_minutes=45, heures_fixees_par_fichier=True),
            AiDayEntry(jour=5, heures=9.75, punch_entry_raw="800", punch_exit_raw="1834",
                       punch_break_minutes=45, heures_fixees_par_fichier=True),
            AiDayEntry(jour=6, heures=7.0, punch_entry_raw="800", punch_exit_raw=None,
                       heures_fixees_par_fichier=True),
            # Témoin non drapeauté : recalculé (dans la tolérance → théorique).
            AiDayEntry(jour=7, heures=6.78, punch_entry_raw="815", punch_exit_raw="1547",
                       punch_break_minutes=45),
        ])],
    )

    res = apply_punch_accounting_to_proposal(prop, "co-1")
    jours = {d.jour: d for d in res.employees[0].days}

    assert jours[1].heures == 6.75
    assert jours[5].heures == 9.75
    assert jours[5].heures_en_plus_a_valider is None
    assert jours[6].heures == 7.0
    assert jours[1].punch_entry_raw == "815" and jours[1].punch_exit_raw == "1547"
    assert jours[7].heures == 7.0
    assert not any(w.startswith(("Jour 1 :", "Jour 5 :", "Jour 6 :")) for w in res.employees[0].warnings)
    assert not any(q.code in ("punch_overtime_review", "punch_incomplete") for q in res.quality_checks)


# --- Plusieurs relevés fusionnés à l'écran --------------------------------


@patch("app.modules.schedules.application.timesheet_import.commit_service.timesheet_import_repository")
def test_un_jour_d_un_autre_mois_relu_dans_le_lot_s_ecrit_a_sa_date(mock_repo):
    """La fusion à l'écran envoie les jours de septembre avec leur mois, dans
    le lot d'octobre (le dernier fichier) : ils s'écrivent en septembre, pas
    sous leur numéro en octobre."""
    from app.modules.schedules.application.timesheet_import.commit_service import (
        _employes_par_mois,
        appliquer_revue_au_lot,
    )
    from app.modules.schedules.schemas.ai import (
        AiCalendarProposalResponse,
        AiDayEntry,
        AiEmployeeProposal,
    )
    from app.modules.schedules.schemas.persist import PersistTimesheetEmployee

    mock_repo.get_batch.return_value = {
        "id": "b43", "company_id": "c1", "status": "previewed", "summary_json": {},
        "preview_json": AiCalendarProposalResponse(
            year=2026, month=10, source="test",
            employees=[AiEmployeeProposal(
                raw_name="Salarié Un", employee_id="e1", review_status="ok",
                match_confidence="high",
                days=[AiDayEntry(jour=21, heures=7.0)],
            )],
        ).model_dump(mode="json"),
    }
    relus = [PersistTimesheetEmployee(employee_id="e1", days=[
        AiDayEntry(jour=21, heures=7.25, year=2026, month=9),
        AiDayEntry(jour=25, heures=6.75, year=2026, month=9),
        AiDayEntry(jour=21, heures=7.0),
    ])]

    appliquer_revue_au_lot("b43", company_id="c1", employees=relus)

    (_, payload), _ = mock_repo.update_batch.call_args
    jours = [AiDayEntry(**d) for d in payload["preview_json"]["employees"][0]["days"]]
    par_mois = _employes_par_mois(
        [PersistTimesheetEmployee(employee_id="e1", days=jours)], 2026, 10
    )
    assert sorted((d.jour, d.heures) for d in par_mois[(2026, 9)][0].days) == [(21, 7.25), (25, 6.75)]
    assert [(d.jour, d.heures) for d in par_mois[(2026, 10)][0].days] == [(21, 7.0)]
