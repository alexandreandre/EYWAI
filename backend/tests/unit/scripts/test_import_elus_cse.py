"""Rapprochement des élus du classeur d'Elsa avec les salariés en base.

Cas à couvrir : un élu figure au classeur sous son nom d'usage, alors qu'en base c'est
son nom de naissance qui est enregistré comme last_name (les noms utilisés ici sont
fictifs, sans rapport avec de vraies personnes).
"""

from datetime import date, timedelta

import pytest

from scripts.import_elus_cse import (
    PROJECT_REF_PRODUCTION,
    ROLES,
    LigneElu,
    analyser_arguments,
    cle_nom,
    dates_mandat_par_societe,
    decider_refus_ecriture,
    motif_blocage_statut,
    planifier,
    rapprocher,
    verifier_pas_de_troncature,
)


def test_cle_nom_ignore_accents_tirets_espaces_et_casse():
    assert cle_nom("De Barros") == cle_nom("DE BARROS")
    assert cle_nom("Hervé") == cle_nom("HERVE")
    assert cle_nom("Marie-Noelle") == cle_nom("MARIE NOELLE")


def test_roles_connus():
    assert ROLES["Membre titulaire"] == "titulaire"
    assert ROLES["Membre suppléant"] == "suppleant"


def test_rapprochement_sur_le_nom_de_naissance():
    salaries = [
        {"id": "emp-1", "last_name": "FONTVEILLE", "nom_usage": None, "first_name": "OSCAR"}
    ]
    ligne = LigneElu("CARTOL", "FONTVEILLE", "Oscar", "Membre titulaire", None, None, None)
    assert rapprocher(ligne, salaries) == salaries[0]


def test_rapprochement_sur_le_nom_dusage():
    salaries = [
        {
            "id": "emp-2",
            "last_name": "VERNOUX",
            "nom_usage": "GRANDCHAMP",
            "first_name": "ALIZEE",
        }
    ]
    ligne = LigneElu("CARTOL", "GRANDCHAMP", "Alizee", "Membre titulaire", None, None, None)
    assert rapprocher(ligne, salaries) == salaries[0]


def test_homonymes_departages_par_le_prenom():
    salaries = [
        {"id": "a", "last_name": "MARTIN", "nom_usage": None, "first_name": "PAUL"},
        {"id": "b", "last_name": "MARTIN", "nom_usage": None, "first_name": "JEANNE"},
    ]
    ligne = LigneElu("LEWIS", "MARTIN", "Jeanne", "Membre titulaire", None, None, None)
    assert rapprocher(ligne, salaries)["id"] == "b"


def test_aucun_rapprochement_renvoie_none():
    ligne = LigneElu("LEWIS", "INCONNU", "Zoe", "Membre titulaire", None, None, None)
    assert rapprocher(ligne, []) is None


def test_dates_de_mandat_en_ligne_de_commande():
    resultat = dates_mandat_par_societe(["CARTOL=2023-06-15:2027-06-14"])
    assert resultat["CARTOL"] == (date(2023, 6, 15), date(2027, 6, 14))


# --- I3 : statut salarié éligible / bloqué ----------------------------------------

def test_salarie_actif_nest_pas_bloque():
    salarie = {"id": "emp-1", "employment_status": "actif"}
    assert motif_blocage_statut(salarie) is None


def test_salarie_active_nest_pas_bloque():
    salarie = {"id": "emp-1", "employment_status": "active"}
    assert motif_blocage_statut(salarie) is None


def test_salarie_en_sortie_reste_eligible():
    """Un élu en préavis reste un élu : ne pas le bloquer."""
    salarie = {"id": "emp-1", "employment_status": "en_sortie"}
    assert motif_blocage_statut(salarie) is None


def test_salarie_en_onboarding_reste_eligible():
    salarie = {"id": "emp-1", "employment_status": "en_onboarding"}
    assert motif_blocage_statut(salarie) is None


def test_statut_normalise_espaces_et_casse():
    salarie = {"id": "emp-1", "employment_status": " Actif "}
    assert motif_blocage_statut(salarie) is None


def test_salarie_parti_est_bloque_avec_motif_explicite():
    salarie = {"id": "emp-1", "employment_status": "parti"}
    motif = motif_blocage_statut(salarie)
    assert motif is not None
    assert "parti" in motif
    assert "non actif" in motif


def test_salarie_inactif_est_bloque():
    salarie = {"id": "emp-1", "employment_status": "inactif"}
    motif = motif_blocage_statut(salarie)
    assert motif is not None
    assert "inactif" in motif


def test_salarie_sans_statut_connu_est_bloque():
    salarie = {"id": "emp-1", "employment_status": None}
    assert motif_blocage_statut(salarie) is not None


def test_salarie_statut_totalement_inconnu_est_bloque():
    salarie = {"id": "emp-1", "employment_status": "sabbatique"}
    assert motif_blocage_statut(salarie) is not None


# --- m1 : --dry-run / --apply -------------------------------------------------------

def test_sans_argument_le_mode_est_une_simulation():
    options = analyser_arguments(["--fichier", "classeur.xlsx"])
    assert options.apply is False


def test_apply_active_le_mode_ecriture():
    options = analyser_arguments(["--fichier", "classeur.xlsx", "--apply"])
    assert options.apply is True


def test_dry_run_explicite_reste_une_simulation():
    options = analyser_arguments(["--fichier", "classeur.xlsx", "--dry-run"])
    assert options.apply is False


def test_dry_run_et_apply_ensemble_sont_refuses():
    with pytest.raises(SystemExit):
        analyser_arguments(["--fichier", "classeur.xlsx", "--dry-run", "--apply"])


# --- I5 : garde-fou production -------------------------------------------------------

URL_PRODUCTION = f"https://{PROJECT_REF_PRODUCTION}.supabase.co"
URL_TEST = "https://autre-projet-de-test.supabase.co"


def test_apply_sur_production_sans_confirmation_est_refuse():
    refus = decider_refus_ecriture(URL_PRODUCTION, apply=True, confirmation_production=False)
    assert refus is not None
    assert PROJECT_REF_PRODUCTION in refus
    assert "--confirmer-production" in refus


def test_apply_sur_production_avec_confirmation_est_autorise():
    assert decider_refus_ecriture(URL_PRODUCTION, apply=True, confirmation_production=True) is None


def test_apply_sur_base_non_production_ne_necessite_pas_de_confirmation():
    assert decider_refus_ecriture(URL_TEST, apply=True, confirmation_production=False) is None


def test_dry_run_ne_declenche_jamais_le_refus_meme_sur_production():
    assert decider_refus_ecriture(URL_PRODUCTION, apply=False, confirmation_production=False) is None


def test_apply_sur_production_est_refuse_meme_avec_un_objet_url_non_str():
    """Régression : client.supabase_url (supabase-py) n'est pas une str mais un objet
    yarl.URL — `PROJECT_REF_PRODUCTION in url_base` levait TypeError avant que
    `decider_refus_ecriture` ne convertisse explicitement en chaîne, ce qui cassait
    --apply sur toute base, y compris la production (garde-fou totalement inopérant).
    """
    try:
        from yarl import URL

        url_non_str = URL(URL_PRODUCTION + "/")
    except ImportError:

        class UrlFactice:
            def __init__(self, valeur: str) -> None:
                self._valeur = valeur

            def __str__(self) -> str:
                return self._valeur

        url_non_str = UrlFactice(URL_PRODUCTION + "/")

    assert not isinstance(url_non_str, str)
    refus = decider_refus_ecriture(url_non_str, apply=True, confirmation_production=False)
    assert refus is not None
    assert PROJECT_REF_PRODUCTION in refus


# --- m6 : garde contre la troncature PostgREST --------------------------------------

def test_lecture_sous_la_limite_ne_bloque_pas():
    verifier_pas_de_troncature([{"employee_id": "1"}] * 500)


def test_lecture_a_la_limite_arrete_le_script():
    with pytest.raises(SystemExit):
        verifier_pas_de_troncature([{"employee_id": str(i)} for i in range(1000)])


# --- C1 + m2 : planification (is_active, doublon intra-run) ------------------------

def _ligne_valide(nom="FONTVEILLE", prenom="Oscar", fin=None) -> LigneElu:
    fin = fin or (date.today() + timedelta(days=365))
    return LigneElu(
        "CARTOL", nom, prenom, "Membre titulaire", None, date(2023, 1, 1), fin
    )


def _salarie(nom="FONTVEILLE", prenom="OSCAR", employee_id="emp-1") -> dict:
    return {
        "id": employee_id,
        "company_id": "co-1",
        "last_name": nom,
        "nom_usage": None,
        "first_name": prenom,
        "employment_status": "actif",
    }


def test_mandat_en_cours_est_cree_actif():
    ligne = _ligne_valide(fin=date.today() + timedelta(days=30))
    a_creer, bloques = planifier(
        [ligne], {"Cartol Industrie": "co-1"}, [_salarie()], set(), {}
    )
    assert bloques == []
    assert a_creer[0]["is_active"] is True


def test_mandat_deja_termine_est_cree_inactif():
    """C1 : un mandat historique ne doit jamais être créé is_active=True."""
    ligne = _ligne_valide(fin=date.today() - timedelta(days=10))
    a_creer, bloques = planifier(
        [ligne], {"Cartol Industrie": "co-1"}, [_salarie()], set(), {}
    )
    assert bloques == []
    assert a_creer[0]["is_active"] is False


def test_deux_lignes_identiques_ne_creent_quun_seul_mandat():
    """m2 : sans mise à jour d'`existants` au fil de la boucle, deux lignes identiques
    créeraient deux mandats dans le même run."""
    ligne = _ligne_valide()
    a_creer, bloques = planifier(
        [ligne, ligne], {"Cartol Industrie": "co-1"}, [_salarie()], set(), {}
    )
    assert len(a_creer) == 1
    assert bloques == []


def test_mandat_deja_en_base_nest_pas_recree():
    ligne = _ligne_valide()
    existants = {("emp-1", "2023-01-01")}
    a_creer, bloques = planifier(
        [ligne], {"Cartol Industrie": "co-1"}, [_salarie()], existants, {}
    )
    assert a_creer == []
    assert bloques == []
