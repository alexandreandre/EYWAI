"""Tests de l'export provision congés payés (infrastructure)."""

from unittest.mock import patch

import pytest

from app.modules.exports.infrastructure import export_provision_cp as module

pytestmark = pytest.mark.unit

SALARIES = [
    {
        "id": "emp-1",
        "matricule": "BERTAUD",
        "first_name": "Sylvain",
        "last_name": "BERTAUD",
        "hire_date": "2010-03-01",
        "employment_status": "actif",
        "salaire_de_base": {"montant": 2600.0},
    },
    {
        "id": "emp-2",
        "matricule": "NEUF",
        "first_name": "Maëlle",
        "last_name": "SEGUIN",
        "hire_date": "2026-05-01",
        "employment_status": "actif",
        "salaire_de_base": {"montant": 1900.0},
    },
]

BULLETINS = {
    "emp-1": {(2026, m): (2640.86, 679.76) for m in range(1, 8)},
    "emp-2": {},
}

SOLDES = {
    "emp-1": (28.00, 4.16),
    "emp-2": (0.00, 2.08),
}


def _patch_all():
    return (
        patch.object(module, "_lire_salaries", return_value=SALARIES),
        patch.object(module, "_lire_bulletins", return_value=BULLETINS),
        patch.object(module, "_lire_soldes_ouvres", side_effect=lambda eid, *a, **k: SOLDES[eid]),
    )


class TestCollecterLignes:
    def test_les_deux_salaries_sont_presents(self):
        p1, p2, p3 = _patch_all()
        with p1, p2, p3:
            lignes, avertissements = module.collecter_lignes("company-1", "2026-07")

        assert [l.matricule for l in lignes] == ["BERTAUD", "NEUF"]

    def test_salarie_avec_bulletins_calcule_sur_ses_bulletins(self):
        p1, p2, p3 = _patch_all()
        with p1, p2, p3:
            lignes, _ = module.collecter_lignes("company-1", "2026-07")

        bertaud = lignes[0]
        assert bertaud.solde_jours == 32.16
        assert bertaud.salaire_reference == 2640.86
        assert bertaud.mois_retenus == "7/12"
        assert bertaud.anomalie == ""
        assert bertaud.provision == 3860.46

    def test_salarie_sans_bulletin_replie_et_signale(self):
        p1, p2, p3 = _patch_all()
        with p1, p2, p3:
            lignes, _ = module.collecter_lignes("company-1", "2026-07")

        neuf = lignes[1]
        assert neuf.salaire_reference == 1900.0
        assert neuf.mois_retenus == "0/12"
        assert "aucun bulletin" in neuf.anomalie

    def test_avertissement_quand_l_historique_est_incomplet(self):
        p1, p2, p3 = _patch_all()
        with p1, p2, p3:
            _, avertissements = module.collecter_lignes("company-1", "2026-07")

        assert any("sur 12" in a for a in avertissements)

    def test_solde_nul_hors_perimetre(self):
        with patch.object(module, "_lire_salaries", return_value=SALARIES), \
             patch.object(module, "_lire_bulletins", return_value=BULLETINS), \
             patch.object(module, "_lire_soldes_ouvres",
                          side_effect=lambda eid, *a, **k: (0.0, 0.0) if eid == "emp-2" else SOLDES[eid]):
            lignes, _ = module.collecter_lignes("company-1", "2026-07")

        assert [l.matricule for l in lignes] == ["BERTAUD"]

    def test_salarie_sans_date_d_embauche_exclu_et_signale(self):
        sans_date = [dict(SALARIES[0]), {**SALARIES[1], "hire_date": None}]
        with patch.object(module, "_lire_salaries", return_value=sans_date), \
             patch.object(module, "_lire_bulletins", return_value=BULLETINS), \
             patch.object(module, "_lire_soldes_ouvres", side_effect=lambda eid, *a, **k: SOLDES[eid]):
            lignes, avertissements = module.collecter_lignes("company-1", "2026-07")

        assert [l.matricule for l in lignes] == ["BERTAUD"]
        assert any("date d'entrée" in a for a in avertissements)


class TestPreview:
    def test_preview_expose_le_contrat_commun(self):
        p1, p2, p3 = _patch_all()
        with p1, p2, p3:
            preview = module.preview_provision_cp("company-1", "2026-07")

        assert preview["employees_count"] == 2
        assert preview["can_generate"] is True
        assert preview["totals"]["total_amount"] == preview["details"]["total"]
        assert preview["anomalies"] == [] or all(
            a["severity"] != "blocking" for a in preview["anomalies"]
        )

    def test_preview_bloquant_quand_aucune_ligne(self):
        with patch.object(module, "_lire_salaries", return_value=[]), \
             patch.object(module, "_lire_bulletins", return_value={}), \
             patch.object(module, "_lire_soldes_ouvres", return_value=(0.0, 0.0)):
            preview = module.preview_provision_cp("company-1", "2026-07")

        assert preview["can_generate"] is False
        assert any(a["severity"] == "blocking" for a in preview["anomalies"])


class TestGenerate:
    def test_xlsx_commence_par_l_entete_zip(self):
        p1, p2, p3 = _patch_all()
        with p1, p2, p3:
            contenu = module.generate_provision_cp_export("company-1", "2026-07")

        assert contenu[:2] == b"PK"

    def test_csv_contient_la_ligne_total(self):
        p1, p2, p3 = _patch_all()
        with p1, p2, p3:
            contenu = module.generate_provision_cp_export(
                "company-1", "2026-07", file_format="csv"
            )

        texte = contenu.decode("utf-8-sig")
        assert "Total" in texte
        assert "BERTAUD" in texte


class TestCablage:
    def test_type_declare_en_preview_et_en_generation(self):
        from app.modules.exports.domain.value_objects import (
            EXPORT_TYPES_GENERATE,
            EXPORT_TYPES_PREVIEW,
        )

        assert "provision_cp" in EXPORT_TYPES_PREVIEW
        assert "provision_cp" in EXPORT_TYPES_GENERATE

    def test_type_accepte_par_le_schema_de_requete(self):
        from app.modules.exports.schemas.requests import ExportPreviewRequest

        requete = ExportPreviewRequest(export_type="provision_cp", period="2026-07")
        assert requete.export_type == "provision_cp"

    def test_providers_expose_les_deux_fonctions(self):
        from app.modules.exports.infrastructure import providers

        assert callable(providers.preview_provision_cp)
        assert callable(providers.generate_provision_cp_export)
