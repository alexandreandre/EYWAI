"""Le run met en forme les compteurs de congés et les rémunérations de période
pour l'indemnité de fin de contrat (fonction pure, sans base)."""

from app.modules.payroll.documents.payslip_run_heures import periodes_depuis_compteurs

COMPTEURS = {
    "conges_payes": {"acquis": 4.16, "pris": 0.0, "solde": 4.16, "periode": "01/06/2026 – 31/05/2027"},
    "conges_payes_periode_precedente": {"acquis": 7.0, "pris": 1.0, "solde": 2.78, "periode": "01/06/2025 – 31/05/2026"},
}


def test_demory():
    p = periodes_depuis_compteurs(COMPTEURS, brut_periode_precedente=4171.35, brut_en_cours_avant_mois=2026.41)
    assert p["periode_precedente"] == {"libelle": "2025-2026", "brut": 4171.35, "droits": 3.78, "restants": 2.78}
    assert p["periode_en_cours"] == {"libelle": "2026-2027", "brut_avant_mois": 2026.41, "droits": 4.16, "restants": 4.16}


def test_les_droits_sont_pris_plus_solde_pas_le_champ_acquis():
    """`acquis` (7,0 chez Demory) ne suit pas la reprise ; pris + solde, oui."""
    p = periodes_depuis_compteurs(COMPTEURS, brut_periode_precedente=None, brut_en_cours_avant_mois=0.0)
    assert p["periode_precedente"]["droits"] == 3.78 and p["periode_precedente"]["brut"] is None


def test_sans_compteurs_rien():
    assert periodes_depuis_compteurs(None, brut_periode_precedente=1.0, brut_en_cours_avant_mois=1.0) is None
    assert periodes_depuis_compteurs({}, brut_periode_precedente=1.0, brut_en_cours_avant_mois=1.0) is None


def test_le_libelle_vient_de_la_periode_affichee():
    compteurs = {"conges_payes": {"pris": 0, "solde": 1.0, "periode": "01/06/2026 – 31/05/2027"}}
    p = periodes_depuis_compteurs(compteurs, brut_periode_precedente=None, brut_en_cours_avant_mois=10.0)
    assert p["periode_en_cours"]["libelle"] == "2026-2027" and "periode_precedente" not in p
