"""
Tests unitaires — document_variables (fusion templates).
"""

from __future__ import annotations

import re

from app.services.document_variables import build_variables, get_unknown_variables

# Clés exactes produites par build_variables (non-régression structurelle)
_BUILD_VARIABLES_KEYS = frozenset(
    {
        "prenom",
        "nom",
        "date_naissance",
        "lieu_naissance",
        "nationalite",
        "adresse_salarie",
        "numero_titre_sejour",
        "titre_sejour_fin",
        "date_fin_contrat",
        "fin_periode_essai",
        "numero_securite_sociale",
        "poste",
        "classification",
        "coefficient",
        "salaire_brut_mensuel",
        "salaire_brut_annuel",
        "date_debut_contrat",
        "type_contrat",
        "duree_hebdomadaire",
        "lieu_travail",
        "periode_essai_duree",
        "service",
        "manager",
        "missions",
        "description_poste",
        "localisation_poste",
        "date_avenant",
        "date_effet",
        "motif_avenant",
        "ancien_salaire",
        "nouveau_salaire",
        "ancien_poste",
        "nouveau_poste",
        "ancienne_duree",
        "nouvelle_duree",
        "ancien_lieu",
        "nouveau_lieu",
        "nom_entreprise",
        "siret",
        "urssaf_number",
        "code_ape",
        "adresse_entreprise",
        "convention_collective",
        "idcc",
        "nom_signataire_rh",
        "qualite_signataire_rh",
        "date_generation",
        "signature_lieu",
        "signature_date",
    }
)

_DATE_FR_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")


def test_t1_build_variables_complete_no_none_french_amounts_and_dates() -> None:
    employee = {
        "first_name": "Marie",
        "last_name": "Martin",
        "date_naissance": "1990-05-10",
        "hire_date": "2020-01-15",
        "contract_type": "CDI",
        "job_title": "Ingénieur",
        "salaire_de_base": {"valeur": 2500.0},
        "duree_hebdomadaire": 39,
        "lieu_travail": "Paris",
        "nir": "1 90 05 10 123 45 67",
        "classification_conventionnelle": {
            "classe_emploi": "Cadre",
            "coefficient": "250",
        },
        "periode_essai_duree": "3 mois",
    }
    company = {
        "company_name": "ACME SAS",
        "siret": "12345678901234",
        "code_ape": "6201Z",
        "address": "10 rue de la Paix, 75002 Paris",
        "convention_collective": "Syntec",
        "idcc": "1486",
        "nom_signataire_rh": "Jean RH",
        "qualite_signataire_rh": "DRH",
        "city": "Lyon",
    }
    context = {
        "date_effet": "2026-04-01",
        "date_avenant": "2026-03-15",
        "motif_avenant": "Évolution salariale",
        "ancien_salaire": 2400,
        "nouveau_salaire": 2500,
        "ancien_poste": "Junior",
        "nouveau_poste": "Confirmé",
        "ancienne_duree": "35 h",
        "nouvelle_duree": "39 h",
        "ancien_lieu": "Paris",
        "nouveau_lieu": "Lyon",
        "nom_signataire_rh": "Signataire Ctx",
        "qualite_signataire_rh": "Responsable RH",
        "signature_lieu": "Lyon",
        "signature_date": "2026-04-10",
    }

    out = build_variables(employee, company, context)

    assert frozenset(out.keys()) == _BUILD_VARIABLES_KEYS
    assert not any(v is None for v in out.values())
    assert all(isinstance(v, str) for v in out.values())

    assert out["prenom"] == "Marie"
    assert out["nom"] == "Martin"
    assert out["salaire_brut_mensuel"] == "2 500,00 €"
    assert out["salaire_brut_annuel"] == "30 000,00 €"
    assert out["nouveau_salaire"] == "2 500,00 €"
    assert out["ancien_salaire"] == "2 400,00 €"
    assert out["ancien_lieu"] == "Paris"
    assert out["nouveau_lieu"] == "Lyon"
    assert out["localisation_poste"] == "Paris"

    assert _DATE_FR_RE.match(out["date_naissance"])
    assert out["date_naissance"] == "10/05/1990"
    assert out["date_debut_contrat"] == "15/01/2020"
    assert _DATE_FR_RE.match(out["date_effet"])
    assert out["date_effet"] == "01/04/2026"
    assert _DATE_FR_RE.match(out["date_generation"])
    assert _DATE_FR_RE.match(out["signature_date"])


def test_t2_build_variables_missing_keys_empty_strings_no_exception() -> None:
    out = build_variables({}, {}, None)

    assert frozenset(out.keys()) == _BUILD_VARIABLES_KEYS
    # Toujours renseignées par le système (date du jour), pas des champs « manquants » métier
    system_keys = {"date_generation", "signature_date"}
    for k, v in out.items():
        if k in system_keys:
            assert _DATE_FR_RE.match(v), f"clé {k!r} attendue en JJ/MM/AAAA, got {v!r}"
        else:
            assert v == "", f"clé {k!r} devrait être '' pour données vides, got {v!r}"


def test_t3_get_unknown_variables_finds_inconnu() -> None:
    tpl = "Bonjour {{prenom}} {{inconnu}}"
    known = {"prenom": "Test"}
    assert get_unknown_variables(tpl, known) == ["inconnu"]


def test_t4_get_unknown_variables_none_when_all_known() -> None:
    tpl = "Bonjour {{prenom}}"
    known = {"prenom": "Test"}
    assert get_unknown_variables(tpl, known) == []
