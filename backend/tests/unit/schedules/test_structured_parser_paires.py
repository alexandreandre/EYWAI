"""Relevé de badgeuse à trois paires entrée/sortie par jour (format du 19/06/2026).

Colonnes : Entrée 1, Sortie 1, Entrée 2, Sortie 2, Entrée 3, Sortie 3. Le
lecteur garde la première entrée et la dernière sortie de la journée, mesure
la pause visible entre les paires, et rattache à la veille la sortie d'un
poste de nuit écrite sur la ligne du lendemain.
"""

from app.modules.schedules.application.timesheet_import.structured_parser import (
    detect_column_mapping,
    parse_tabular_file,
)

ENTETE = (
    "Matricule;Jour;Nom;Cod Sectio;Entrée 1.;Sortie 1.;Entrée 2.;Sortie 2.;"
    "Entrée 3.;Sortie 3.;Tot H Poin;Hr Théoriq;Code Horai"
)


def _lire(*lignes: str):
    contenu = "\n".join([ENTETE, *lignes]).encode("utf-8")
    res = parse_tabular_file(
        contenu, "releve.csv", target_year=2026, target_month=2,
        options={"skip_period_filter": True},
    )
    return {r.jour: r for r in res.rows}


def test_les_colonnes_entree_2_et_3_sont_reconnues():
    mapping = detect_column_mapping(ENTETE.split(";"))
    assert mapping["entry_1"] == "Entrée 1."
    assert mapping["entry_2"] == "Entrée 2."
    assert mapping["entry_3"] == "Entrée 3."
    assert mapping["exit_last"] == "Sortie 3."


def test_journee_complete_premiere_entree_derniere_sortie_et_pause_de_45():
    j = _lire("000001;10/02/2026;Salarié Un;MONT;800;1000;1015;1230;1300;1630;7,75;7,75;A")[10]
    assert str(j.entry_raw) == "800"
    assert str(j.exit_raw) == "1630"
    assert j.punched_break_minutes == 45


def test_demi_journee_la_pause_pointee_est_celle_du_matin():
    j = _lire("000001;10/02/2026;Salarié Un;MONT;800;1000;1015;1217;0;0;4,03;7,75;A")[10]
    assert str(j.exit_raw) == "1217"
    assert j.punched_break_minutes == 15


def test_une_seule_paire_ne_dit_rien_de_la_pause():
    j = _lire("000001;10/02/2026;Salarié Un;MONT;800;1630;0;0;0;0;8,5;7,75;A")[10]
    assert str(j.exit_raw) == "1630"
    assert j.punched_break_minutes is None


def test_entree_seule_reste_une_entree_sans_sortie():
    j = _lire("000001;10/02/2026;Salarié Un;MONT;800;0;0;0;0;0;0;7,75;A")[10]
    assert str(j.entry_raw) == "800"
    assert j.exit_raw is None


def test_poste_de_nuit_rattache_la_sortie_du_lendemain_a_la_veille():
    jours = _lire(
        "000002;09/02/2026;Salarié Deux;POIN;2000;0;0;0;0;0;4;7,75;B",
        "000002;10/02/2026;Salarié Deux;POIN;0;400;2000;0;0;0;32;7,75;B",
        "000002;11/02/2026;Salarié Deux;POIN;0;400;0;0;0;0;28;7,75;B",
    )
    lundi, mardi, mercredi = jours[9], jours[10], jours[11]
    assert (str(lundi.entry_raw), str(lundi.exit_raw)) == ("2000", "400")
    assert (str(mardi.entry_raw), str(mardi.exit_raw)) == ("2000", "400")
    assert mercredi.entry_raw is None and mercredi.exit_raw is None
    assert any("poste de nuit" in n for n in mercredi.notes)


def test_une_entree_seule_suivie_d_une_journee_normale_reste_incomplete():
    jours = _lire(
        "000001;10/02/2026;Salarié Un;MONT;800;0;0;0;0;0;0;7,75;A",
        "000001;11/02/2026;Salarié Un;MONT;800;1000;1015;1230;1300;1630;7,75;7,75;A",
    )
    assert str(jours[10].entry_raw) == "800" and jours[10].exit_raw is None
    assert (str(jours[11].entry_raw), str(jours[11].exit_raw)) == ("800", "1630")


def test_sans_colonnes_de_paires_le_comportement_historique_reste():
    contenu = (
        "Matricule;Jour;Nom;Entrée 1.;Sortie 3.;Tot H Poin\n"
        "000001;10/02/2026;Salarié Un;800;1630;7,75\n"
    ).encode("utf-8")
    res = parse_tabular_file(contenu, "r.csv", target_year=2026, target_month=2)
    j = res.rows[0]
    assert (str(j.entry_raw), str(j.exit_raw)) == ("800", "1630")
    assert j.punched_break_minutes is None


def test_un_poste_de_nuit_n_ecrase_pas_le_poste_de_jour_de_la_veille():
    jours = _lire(
        "000003;09/02/2026;Salarié Trois;POIN;800;1630;2000;0;0;0;12;7,75;A",
        "000003;10/02/2026;Salarié Trois;POIN;0;400;0;0;0;0;28;7,75;A",
    )
    lundi = jours[9]
    assert (str(lundi.entry_raw), str(lundi.exit_raw)) == ("800", "1630")
    assert any("non compté" in n for n in lundi.notes)


def test_la_proposition_porte_la_pause_pointee_et_les_notes_du_lecteur():
    from app.modules.schedules.application.timesheet_import.proposal_builder import (
        build_proposal_from_tabular,
    )

    contenu = "\n".join([
        ENTETE,
        "000002;09/02/2026;Salarié Deux;POIN;800;1000;1015;1217;0;0;4;7,75;A",
        "000002;10/02/2026;Salarié Deux;POIN;2000;0;0;0;0;0;4;7,75;B",
        "000002;11/02/2026;Salarié Deux;POIN;0;400;0;0;0;0;28;7,75;B",
    ]).encode("utf-8")
    parsed = parse_tabular_file(contenu, "r.csv", target_year=2026, target_month=2)
    proposal = build_proposal_from_tabular(parsed, year=2026, month=2, roster=[])

    emp = proposal.employees[0]
    jours = {d.jour: d for d in emp.days}
    assert jours[9].punch_break_minutes == 15
    assert (jours[10].punch_entry_raw, jours[10].punch_exit_raw) == ("2000", "400")
    assert any(w.startswith("Jour 11 :") and "poste de nuit" in w for w in emp.warnings)
