"""Rapprochement fichier ↔ base et nature des changements proposés."""

from app.modules.pas_rates.domain.extraction import TauxFichier
from app.modules.pas_rates.domain.rapprochement import (
    cle_nir,
    cle_nom,
    construire_apercu,
    lignes_a_ecrire,
)


def _salarie(**kw):
    base = {
        "id": "emp-1",
        "last_name": "NOBLE",
        "first_name": "Eric",
        "nir": "1690199404042",
        "employment_status": "actif",
        "specificites_paie": {"prelevement_a_la_source": {"taux": 3.5, "type_taux": "13"}},
    }
    base.update(kw)
    return base


def _ligne(**kw):
    base = {
        "nir": "1690199404042",
        "nom": "NOBLE",
        "prenom": "Eric",
        "matricule": "0001",
        "taux": 26.8,
        "type_taux": "01",
        "identifiant_taux": "ABC",
    }
    base.update(kw)
    return TauxFichier(**base)


def _apercu(lignes, salaries):
    return construire_apercu(
        lignes,
        salaries,
        periode="2026-05",
        siren="991177304",
        fichier="2026-05.dsn",
        source="dsn",
    )


def test_taux_different_est_une_modification():
    apercu = _apercu([_ligne()], [_salarie()])
    assert apercu.lignes[0].nature == "modifie"
    assert apercu.lignes[0].taux_actuel == 3.5
    assert apercu.lignes[0].taux_fichier == 26.8


def test_changement_de_type_seul_est_une_modification():
    """Le passage du barème au taux DGFiP compte, même à taux identique."""
    salarie = _salarie(
        specificites_paie={"prelevement_a_la_source": {"taux": 26.8, "type_taux": "13"}}
    )
    apercu = _apercu([_ligne()], [salarie])
    assert apercu.lignes[0].nature == "modifie"


def test_taux_et_type_identiques_ne_changent_rien():
    salarie = _salarie(
        specificites_paie={"prelevement_a_la_source": {"taux": 26.8, "type_taux": "01"}}
    )
    apercu = _apercu([_ligne()], [salarie])
    assert apercu.lignes[0].nature == "inchange"
    assert lignes_a_ecrire(apercu) == []


def test_salarie_sans_taux_recoit_un_nouveau_taux():
    salarie = _salarie(specificites_paie={"prelevement_a_la_source": {"type_taux": "13"}})
    apercu = _apercu([_ligne(taux=5.3, type_taux="13")], [salarie])
    assert apercu.lignes[0].nature == "nouveau"
    assert len(lignes_a_ecrire(apercu)) == 1


def test_taux_absent_du_fichier_ne_remet_pas_a_zero():
    apercu = _apercu([_ligne(taux=None)], [_salarie()])
    assert apercu.lignes[0].nature == "inchange"
    assert lignes_a_ecrire(apercu) == []


def test_individu_non_rapproche_est_signale_jamais_cree():
    apercu = _apercu([_ligne(nir="9999999999999", nom="INCONNU", prenom="Jean")], [])
    assert apercu.lignes[0].nature == "non_rapproche"
    assert apercu.lignes[0].employee_id is None
    assert lignes_a_ecrire(apercu) == []


def test_salarie_parti_est_reconnu_mais_pas_modifie():
    """Le fichier du mois travaillé contient encore les sortants."""
    salarie = _salarie(employment_status="parti")
    apercu = _apercu([_ligne()], [salarie])
    assert apercu.lignes[0].nature == "hors_effectif"
    assert apercu.lignes[0].employee_id == "emp-1"
    assert lignes_a_ecrire(apercu) == []


def test_salarie_en_sortie_reste_dans_l_effectif():
    """Un préavis en cours a encore des bulletins à produire."""
    apercu = _apercu([_ligne()], [_salarie(employment_status="en_sortie")])
    assert apercu.lignes[0].nature == "modifie"


def test_avertissement_ignore_les_partis_absents_du_fichier():
    parti = _salarie(id="emp-2", last_name="PARTI", first_name="Paul", nir="2800199404042")
    parti["employment_status"] = "parti"
    apercu = _apercu([_ligne()], [_salarie(), parti])
    assert apercu.avertissements == []


def test_rapprochement_par_nom_quand_le_nir_manque():
    salarie = _salarie(nir="")
    apercu = _apercu([_ligne(nir="")], [salarie])
    assert apercu.lignes[0].employee_id == "emp-1"


def test_rapprochement_tolere_accents_et_second_prenom():
    salarie = _salarie(last_name="LEITES", first_name="Maria Héléna", nir="")
    ligne = _ligne(nir="", nom="LEITES", prenom="MARIA HELENA")
    apercu = _apercu([ligne], [salarie])
    assert apercu.lignes[0].employee_id == "emp-1"


def test_nir_rapproche_sur_treize_chiffres():
    """La base garde treize chiffres, un export peut en porter quinze."""
    assert cle_nir("169019940404212") == "1690199404042"
    assert cle_nir("1 69 01 99 404 042") == "1690199404042"


def test_cle_nom_ignore_la_casse_et_la_ponctuation():
    assert cle_nom("de Sá", "Anthony") == cle_nom("DE SA", "ANTHONY")


def test_second_contrat_du_meme_salarie_est_ignore():
    apercu = _apercu([_ligne(), _ligne(taux=9.9)], [_salarie()])
    lignes_salarie = [l for l in apercu.lignes if l.employee_id == "emp-1"]
    assert len(lignes_salarie) == 1
    assert lignes_salarie[0].taux_fichier == 26.8


def test_salaries_absents_du_fichier_sont_signales():
    autre = _salarie(id="emp-2", last_name="ABSENT", first_name="Paul", nir="2800199404042")
    apercu = _apercu([_ligne()], [_salarie(), autre])
    assert apercu.avertissements
    assert "1 salarié(s)" in apercu.avertissements[0]


def test_compteurs_resument_l_apercu():
    autre = _salarie(id="emp-2", last_name="AUTRE", first_name="Paul", nir="2800199404042")
    apercu = _apercu(
        [_ligne(), _ligne(nir="9999999999999", nom="INCONNU", prenom="Jean")],
        [_salarie(), autre],
    )
    compteurs = apercu.compteurs()
    assert compteurs["modifie"] == 1
    assert compteurs["non_rapproche"] == 1
