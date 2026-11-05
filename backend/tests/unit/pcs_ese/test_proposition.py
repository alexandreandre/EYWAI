"""Martine propose un code PCS-ESE : collègues de la société, du groupe, puis métiers Insee."""

from app.modules.pcs_ese.domain.normalisation import est_cadre, normaliser_poste
from app.modules.pcs_ese.domain.proposition import FicheCollegue, collegues_de, proposer


def f(code, poste="Agent de production", statut="Non-Cadre", cid="c1", soc="Soc A", eid="x"):
    return FicheCollegue(eid, cid, soc, poste, statut, code)


def p_metier(poste, statut="Non-Cadre"):
    return proposer(poste=poste, statut=statut, collegues_societe=[], collegues_groupe=[])


# --- a) collègues de la société -------------------------------------------------------


def test_a_tous_le_meme_code_sur():
    p = proposer(
        poste="agent de production",
        statut="Non-Cadre",
        collegues_societe=[f("674a"), f("674a"), f("674a")],
        collegues_groupe=[],
    )
    assert (p.code, p.sur, p.regle, p.nb_collegues) == ("674a", True, "a", 3)
    assert p.raison == "Même poste et même statut que 3 collègues de Soc A, tous en 674a."


def test_un_seul_collegue_suffit():
    p = proposer(poste="x", statut="Non-Cadre", collegues_societe=[f("674a")], collegues_groupe=[])
    assert p.sur
    assert p.raison == "Même poste et même statut qu'1 collègue de Soc A, en 674a."


def test_desaccord_pas_sur_et_codes_les_plus_frequents():
    p = proposer(
        poste="x",
        statut="Non-Cadre",
        collegues_societe=[f("674a"), f("625h"), f("674a")],
        collegues_groupe=[f("623e", cid="c2")],
    )
    assert not p.sur and p.code is None and p.regle == "a"
    assert [c.code for c in p.candidats][:2] == ["674a", "625h"]
    assert p.candidats[0].raison == "2 collègues sur 3 de Soc A, au même poste, en 674a."
    assert p.raison == "Les collègues de Soc A au même poste n'ont pas tous le même code."


# --- b) collègues du groupe -----------------------------------------------------------


def test_b_groupe_quand_personne_dans_la_societe():
    p = proposer(
        poste="x",
        statut="Non-Cadre",
        collegues_societe=[],
        collegues_groupe=[f("674a", cid="c2", soc="Comitech")],
    )
    assert (p.code, p.regle) == ("674a", "b")
    assert p.raison == "Même poste et même statut qu'1 collègue du groupe (Comitech), en 674a."


def test_9999_et_vide_ne_comptent_pas():
    p = proposer(
        poste="contrôleur de gestion",
        statut="Non-Cadre",
        collegues_societe=[f("9999"), f("")],
        collegues_groupe=[f("9999", cid="c2")],
    )
    assert p.regle == "c"


# --- seuil ECAP ----------------------------------------------------------------------


def test_ecap_un_seul_collegue_propose_pas_pose():
    p = proposer(poste="x", statut="Non-Cadre", collegues_societe=[f("624d")], collegues_groupe=[])
    assert not p.sur and p.code is None
    assert p.candidats[0].code == "624d" and p.candidats[0].ecap
    assert "Code ECAP" in p.candidats[0].raison


def test_ecap_deux_collegues_pose():
    p = proposer(
        poste="x", statut="Non-Cadre", collegues_societe=[f("624d"), f("624d")], collegues_groupe=[]
    )
    assert p.sur and p.ecap and p.code == "624d"


# --- c) métiers Insee ----------------------------------------------------------------


def test_c_metier_exact_sans_secteur():
    p = p_metier("Contrôleur de gestion")
    assert (p.code, p.sur, p.regle) == ("461d", True, "c")
    assert p.raison == "Métier Insee : « Contrôleur de gestion, non cadre » (rubrique 461d)."


def test_c_un_apprenti_n_est_jamais_sur():
    # L'Insee code l'apprenti à part (« Apprenti charpentier » en 681a, non qualifié) :
    # l'intitulé seul ne dit pas où le ranger.
    p = p_metier("Contrôleur de gestion - apprenti")
    assert not p.sur and "461d" in [c.code for c in p.candidats]


def test_c_le_metier_apprenti_ne_vaut_pas_pour_le_metier():
    # « Apprenti charpentier » (681a) ne rend pas Martine sûre pour un charpentier.
    p = p_metier("Charpentier")
    assert not (p.sur and p.code == "681a")


def test_c_niveau_de_qualification_inconnu_jamais_sur():
    # « Maçon, ouvrier qualifié », « …, ouvrier non qualifié » : le niveau ne se lit pas
    # dans l'intitulé du poste.
    for poste in ("Maçon", "Mécanicien auto", "Peintre en bâtiment"):
        assert not p_metier(poste).sur, poste


def test_c_un_code_ecap_n_est_jamais_pose_par_l_insee():
    for poste in ("Agent de sécurité", "Grutier", "Cariste"):
        p = p_metier(poste)
        assert not (p.sur and p.ecap), poste


def test_c_cadre_ecarte_les_non_cadres():
    p = p_metier("Responsable méthode", statut="Cadre")
    assert (p.code, p.sur) == ("387c", True)


def test_c_metier_a_secteur_jamais_sur():
    p = p_metier("Soudeur")
    assert not p.sur
    assert 1 <= len(p.candidats) <= 3


def test_c_plusieurs_codes_trois_propositions():
    p = p_metier("Agent d'entretien")
    assert not p.sur and len(p.candidats) == 3
    assert all(c.code[0] in "456" for c in p.candidats)
    assert p.candidats[0].raison.startswith("Métier Insee")


def test_c_cadre_ne_recoit_que_le_groupe_3():
    p = p_metier("Directeur commercial", statut="Cadre")
    assert p.candidats and all(c.code[0] == "3" for c in p.candidats)


def test_jamais_groupes_1_2_ni_public():
    from app.modules.pcs_ese.domain.referentiel import charger_referentiel

    ref = charger_referentiel()
    for poste in ("Peintre", "Agent de bureau", "Comptable", "Infirmier"):
        for c in p_metier(poste).candidats:
            assert c.code[0] not in "12" and not ref[c.code].public


def test_intitule_coupe_a_30_caracteres():
    p = p_metier("technicien de maintenance indu")
    assert "477b" in [c.code for c in p.candidats]


def test_rien_trouve():
    p = p_metier("Pilote IA / robotique")
    assert p.code is None and p.regle is None and p.candidats == ()
    assert p.raison.startswith("Aucun collègue au même poste")


def test_9999_jamais_propose():
    p = p_metier("Profession non connue")
    assert "9999" not in [c.code for c in p.candidats]


# --- comparaison des postes -----------------------------------------------------------


def test_normaliser_poste():
    assert normaliser_poste("  Agent de Prod. Qualifié ") == "agent de prod qualifie"
    assert normaliser_poste("Opérateur/peinture") == "operateur peinture"


def test_est_cadre():
    assert est_cadre("Cadre") and not est_cadre("Non-Cadre") and not est_cadre("")


def test_collegues_de_meme_poste_meme_statut_sans_soi():
    fiches = [
        f("674a", poste="Agent de Production", eid="1"),
        f("674a", eid="moi"),
        f("625h", statut="Cadre", eid="2"),
        f("623e", cid="c2", soc="B", eid="3"),
        f("623e", cid="c2", soc="B", poste="Soudeur", eid="4"),
    ]
    soc, grp = collegues_de(
        fiches, company_id="c1", poste="agent de production ", statut="Non-Cadre", exclure_id="moi"
    )
    assert [x.employee_id for x in soc] == ["1"]
    assert [x.employee_id for x in grp] == ["3"]


# --- qualité des propositions proches -------------------------------------------------


def test_un_mot_generique_seul_ne_suffit_pas():
    for poste in ("Opérateur de production", "Agent de production", "Responsable maintenance"):
        for c in p_metier(poste).candidats:
            assert "informatique" not in c.raison and "de bureau" not in c.raison, (poste, c)
            assert "flotte" not in c.raison, (poste, c)


def test_le_metier_le_plus_complet_en_premier():
    p = p_metier("Peintre industriel qualifié")
    assert p.candidats[0].code == "624f"


def test_un_mot_precis_seul_suffit():
    p = p_metier("Magasinier / cariste")
    assert {"652a", "653a"} <= {c.code for c in p.candidats}


def test_a_un_code_incompatible_avec_le_statut_ne_compte_pas():
    # Un non-cadre ne prend pas un code de cadre (groupe 3), même chez un collègue.
    p = proposer(
        poste="x", statut="Non-Cadre", collegues_societe=[f("387c")], collegues_groupe=[f("674a", cid="c2")]
    )
    assert (p.code, p.regle) == ("674a", "b")
    p = proposer(poste="x", statut="Cadre", collegues_societe=[f("674a", statut="Cadre")], collegues_groupe=[])
    assert p.regle != "a"
