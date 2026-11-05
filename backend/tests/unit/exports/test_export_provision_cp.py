"""Tests de l'export provision congés payés (infrastructure) : la règle légale du 05/11/2026."""

from unittest.mock import patch

import pytest

from app.modules.exports.domain.provision_cp import PeriodeProvision
from app.modules.exports.infrastructure import export_provision_cp as module
from app.modules.exports.infrastructure.export_provision_cp import BulletinDuMois

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def sans_base(monkeypatch):
    """Les lectures en base : ici, une société sans reprise, sans repos, sans cumuls, période
    de congés au 1er juin."""
    monkeypatch.setattr(module, "_lire_bascule", lambda company_id: None)
    monkeypatch.setattr(module, "_lire_repos", lambda *a, **k: {})
    monkeypatch.setattr(module, "_lire_cumuls", lambda *a, **k: {})
    monkeypatch.setattr(module, "_mois_debut_periode", lambda company_id: 6)


SALARIES = [
    {
        "id": "emp-1",
        "matricule": "BARUMET",
        "first_name": "Dalande",
        "last_name": "BARUMET",
        "hire_date": "2010-03-01",
        "employment_status": "actif",
        "salaire_de_base": {"type": "mensuel", "valeur": 2600.0},
        "duree_hebdomadaire": 35.0,
    },
    {
        "id": "emp-2",
        "matricule": "NEUF",
        "first_name": "Maëlle",
        "last_name": "SEGUIN",
        "hire_date": "2026-05-01",
        "employment_status": "actif",
        "salaire_de_base": {"type": "mensuel", "valeur": 1900.0},
        "duree_hebdomadaire": 35.0,
    },
]

BULLETINS = {
    "emp-1": {(2026, m): (2640.86, 679.76) for m in range(1, 8)},
    "emp-2": {},
}

#: Bulletins de BARUMET : janvier à juillet 2026, une prime d'ancienneté chaque mois, un arrêt
#: maladie en mars.
DETAILS = {
    "emp-1": {
        (2026, m): BulletinDuMois(
            2640.86,
            [{"libelle": "Salaire de base", "gain": 2600.0}, {"libelle": "Prime ancienneté", "gain": 40.86}]
            + ([{"libelle": "Absence maladie 020326-060326", "perte": 500.0}] if m == 3 else []),
        )
        for m in range(1, 8)
    },
}

CONGES = {
    "emp-1": (PeriodeProvision(28.00, 25.0, None), PeriodeProvision(4.16, 4.16, None)),
    "emp-2": (PeriodeProvision(0.00, 0.0, None), PeriodeProvision(2.08, 2.08, None)),
}


def _patch_all(conges=None, salaries=None, details=None):
    conges = conges or CONGES
    return (
        patch.object(module, "_lire_salaries", return_value=salaries or SALARIES),
        patch.object(module, "_lire_bulletins", return_value=BULLETINS),
        patch.object(module, "_lire_conges_ouvres", side_effect=lambda eid, *a, **k: conges[eid]),
        patch.object(module, "_lire_details_bulletins", return_value=DETAILS if details is None else details),
    )


class TestCollecterLignes:
    def test_les_deux_salaries_sont_presents(self):
        p1, p2, p3, p4 = _patch_all()
        with p1, p2, p3, p4:
            lignes, _ = module.collecter_lignes("company-1", "2026-07")

        assert [l.matricule for l in lignes] == ["BARUMET", "NEUF"]

    def test_la_valeur_du_jour_est_le_contrat_plus_les_primes_recurrentes(self):
        p1, p2, p3, p4 = _patch_all()
        with p1, p2, p3, p4:
            lignes, _ = module.collecter_lignes("company-1", "2026-07")

        barumet = lignes[0]
        assert barumet.primes_recurrentes == 40.86
        attendu = round(module._valeur_jour_du_contrat(SALARIES[0]) + 40.86 / (260 / 12), 2)
        assert barumet.valeur_jour == attendu

    def test_chaque_periode_au_plus_eleve_du_maintien_et_du_dixieme(self):
        p1, p2, p3, p4 = _patch_all()
        with p1, p2, p3, p4:
            lignes, _ = module.collecter_lignes("company-1", "2026-07")

        barumet = lignes[0]
        # N-1 (juin 2025 - mai 2026) : bulletins de janvier à mai, l'arrêt de mars à 80 %.
        assert barumet.base_n1 == round(5 * 2640.86 + 400.0, 2)
        assert barumet.reconstitution == 400.0
        # N (juin - juillet 2026) : deux bulletins.
        assert barumet.base_n == round(2 * 2640.86, 2)
        dixieme_n1 = round(barumet.base_n1 * 0.10 * 28.0 / 25.0, 2)
        maintien_n1 = round(28.0 * barumet.valeur_jour, 2)
        assert barumet.provision_n1 == max(dixieme_n1, maintien_n1)
        dixieme_n = round(barumet.base_n * 0.10, 2)
        maintien_n = round(4.16 * barumet.valeur_jour, 2)
        assert barumet.provision_n == max(dixieme_n, maintien_n)
        assert barumet.provision == round(barumet.provision_n1 + barumet.provision_n, 2)
        assert barumet.mois_retenus == "7/12"

    def test_un_mois_d_absence_ne_fait_plus_baisser_la_valeur_du_jour(self):
        """L'écart signalé par Elsa : chez Quadra, un mois d'absence baissait la moyenne."""
        avec_arret = {"emp-1": dict(DETAILS["emp-1"])}
        avec_arret["emp-1"][(2026, 7)] = BulletinDuMois(
            0.0, [{"libelle": "Absence maladie 010726-310726", "perte": 2600.0}]
        )
        p1, p2, p3, p4 = _patch_all(details=avec_arret)
        with p1, p2, p3, p4:
            lignes, _ = module.collecter_lignes("company-1", "2026-07")
        p1, p2, p3, p4 = _patch_all()
        with p1, p2, p3, p4:
            sans, _ = module.collecter_lignes("company-1", "2026-07")

        assert lignes[0].valeur_jour == sans[0].valeur_jour

    def test_sans_remuneration_de_la_periode_le_maintien_seul_est_signale(self):
        p1, p2, p3, p4 = _patch_all(details={})
        with p1, p2, p3, p4:
            lignes, avertissements = module.collecter_lignes("company-1", "2026-07")

        assert "rémunération de la période N-1 inconnue : maintien seul" in lignes[0].anomalie
        assert any("maintien seul" in a for a in avertissements)

    def test_salarie_sans_bulletin_signale(self):
        p1, p2, p3, p4 = _patch_all()
        with p1, p2, p3, p4:
            lignes, _ = module.collecter_lignes("company-1", "2026-07")

        neuf = lignes[1]
        assert neuf.mois_retenus == "0/12"
        assert "aucun bulletin" in neuf.anomalie
        assert neuf.provision == round(2.08 * neuf.valeur_jour, 2)

    def test_sans_salaire_contractuel_le_jour_vient_de_la_moyenne_des_bulletins(self):
        muet = [{**SALARIES[0], "salaire_de_base": None}]
        p1, p2, p3, p4 = _patch_all(salaries=muet)
        with p1, p2, p3, p4:
            lignes, _ = module.collecter_lignes("company-1", "2026-07")

        assert lignes[0].valeur_jour == round(2640.86 / (260 / 12), 2)
        assert "moyenne des bulletins" in lignes[0].anomalie

    def test_avertissement_quand_les_bulletins_de_la_periode_precedente_manquent(self):
        p1, p2, p3, p4 = _patch_all()
        with p1, p2, p3, p4:
            _, avertissements = module.collecter_lignes("company-1", "2026-07")

        assert any("pas tous les bulletins de la période précédente" in a for a in avertissements)

    def test_avertissement_sur_les_reports_non_repris(self):
        p1, p2, p3, p4 = _patch_all()
        with p1, p2, p3, p4:
            _, avertissements = module.collecter_lignes("company-1", "2026-07")

        assert any("période précédente recalculé" in a for a in avertissements)

    def test_aucun_avertissement_sans_ligne(self):
        p1, p2, p3, p4 = _patch_all(salaries=[{**SALARIES[0], "id": "x"}],
                                    conges={"x": (PeriodeProvision(0, 0, None), PeriodeProvision(0, 0, None))})
        with p1, p2, p3, p4:
            lignes, avertissements = module.collecter_lignes("company-1", "2026-07")

        assert lignes == [] and avertissements == []

    def test_solde_nul_hors_perimetre(self):
        conges = {**CONGES, "emp-2": (PeriodeProvision(0, 0, None), PeriodeProvision(0, 0, None))}
        p1, p2, p3, p4 = _patch_all(conges=conges)
        with p1, p2, p3, p4:
            lignes, _ = module.collecter_lignes("company-1", "2026-07")

        assert [l.matricule for l in lignes] == ["BARUMET"]

    def test_salarie_sans_date_d_embauche_exclu_et_signale(self):
        sans_date = [dict(SALARIES[0]), {**SALARIES[1], "hire_date": None}]
        p1, p2, p3, p4 = _patch_all(salaries=sans_date)
        with p1, p2, p3, p4:
            lignes, avertissements = module.collecter_lignes("company-1", "2026-07")

        assert [l.matricule for l in lignes] == ["BARUMET"]
        assert any("date d'entrée" in a for a in avertissements)


class TestBasesDuDixieme:
    PERIODES = ((module.date(2025, 6, 1), module.date(2026, 5, 31)), (module.date(2026, 6, 1), module.date(2026, 9, 30)))

    def test_le_cumul_de_la_periode_fait_foi(self):
        bulletins = {(2026, 9): BulletinDuMois(3000.0, [])}
        cumuls_n = {"brut_reference_n_1": 11800.0, "brut_reference_period_start": "2026-06-01"}
        cumuls_n1 = {"brut_reference_n_1": 35000.0, "brut_reference_period_start": "2025-06-01"}
        assert module.bases_du_dixieme(bulletins, cumuls_n1, cumuls_n, self.PERIODES) == (35000.0, 11800.0, 0.0)

    def test_un_dernier_mois_paye_par_l_ancien_logiciel_fait_foi(self):
        """Comitech (05/11) : un cumul de 1 205,37 € contre 5 382,70 € aux bulletins de Quadra."""
        bulletins = {(2026, m): BulletinDuMois(1345.68, [], importe=True) for m in (6, 7, 8, 9)}
        cumuls_n = {"brut_reference_n_1": 1205.37, "brut_reference_period_start": "2026-06-01"}
        assert module.bases_du_dixieme(bulletins, None, cumuls_n, self.PERIODES)[1] == 5382.72

    def test_un_cumul_d_une_autre_periode_ne_compte_pas(self):
        bulletins = {(2026, 9): BulletinDuMois(3000.0, [])}
        cumuls_n = {"brut_reference_n_1": 99999.0, "brut_reference_period_start": "2025-06-01"}
        assert module.bases_du_dixieme(bulletins, None, cumuls_n, self.PERIODES)[1] == 3000.0

    def test_sans_cumul_ni_bulletin_la_base_est_inconnue(self):
        assert module.bases_du_dixieme({}, None, None, self.PERIODES) == (None, None, 0.0)

    def test_la_reconstitution_s_ajoute_a_sa_periode(self):
        bulletins = {
            (2026, 5): BulletinDuMois(1500.0, [{"libelle": "Absence maladie 010526-150526", "perte": 1000.0}]),
            (2026, 9): BulletinDuMois(2000.0, [{"libelle": "Absence accident du travail du 01/09", "perte": 500.0}]),
        }
        base_n1, base_n, reconstitution = module.bases_du_dixieme(bulletins, None, None, self.PERIODES)
        assert (base_n1, base_n, reconstitution) == (2300.0, 2500.0, 1300.0)


class TestValeurJourDuContrat:
    def test_trente_cinq_heures(self):
        assert module._valeur_jour_du_contrat({"salaire_de_base": {"valeur": 2600.0}, "duree_hebdomadaire": 35.0}) == round(2600 / 151.67 * 7, 2)

    def test_les_heures_structurelles_comptent(self):
        a_35 = module._valeur_jour_du_contrat({"salaire_de_base": {"valeur": 2600.0}, "duree_hebdomadaire": 35.0})
        a_39 = module._valeur_jour_du_contrat({"salaire_de_base": {"valeur": 2600.0}, "duree_hebdomadaire": 39.0,
                                               "specificites_paie": {"salaire_hors_hs_structurelles": True}})
        assert a_39 > a_35

    def test_sans_salaire(self):
        assert module._valeur_jour_du_contrat({"salaire_de_base": None}) == 0.0


class TestMontantContractuel:
    def test_forme_reelle_de_la_base(self):
        # En production le champ vaut {"type": "mensuel", "valeur": 2049.76}
        assert module._montant_contractuel(
            {"salaire_de_base": {"type": "mensuel", "valeur": 2049.76}}
        ) == 2049.76

    def test_nombre_nu(self):
        assert module._montant_contractuel({"salaire_de_base": 1800.0}) == 1800.0

    def test_absent(self):
        assert module._montant_contractuel({"salaire_de_base": None}) is None


class TestPreview:
    def test_preview_expose_le_contrat_commun(self):
        p1, p2, p3, p4 = _patch_all()
        with p1, p2, p3, p4:
            preview = module.preview_provision_cp("company-1", "2026-07")

        assert preview["employees_count"] == 2
        assert preview["can_generate"] is True
        assert preview["totals"]["total_amount"] == preview["details"]["total"]
        assert preview["anomalies"] == [] or all(
            a["severity"] != "blocking" for a in preview["anomalies"]
        )

    def test_preview_bloquant_quand_rien_ne_peut_etre_valorise(self):
        # Aucun bulletin et aucun salaire contractuel : des soldes, mais 0 EUR.
        muets = [{**s, "salaire_de_base": None} for s in SALARIES]
        with patch.object(module, "_lire_salaries", return_value=muets), \
             patch.object(module, "_lire_bulletins", return_value={"emp-1": {}, "emp-2": {}}), \
             patch.object(module, "_lire_details_bulletins", return_value={}), \
             patch.object(module, "_lire_conges_ouvres", side_effect=lambda eid, *a, **k: CONGES[eid]):
            preview = module.preview_provision_cp("company-1", "2026-07")

        assert preview["details"]["total"] == 0.0
        assert preview["can_generate"] is False
        assert any(a["severity"] == "blocking" for a in preview["anomalies"])

    def test_preview_bloquant_quand_aucune_ligne(self):
        with patch.object(module, "_lire_salaries", return_value=[]), \
             patch.object(module, "_lire_bulletins", return_value={}), \
             patch.object(module, "_lire_details_bulletins", return_value={}):
            preview = module.preview_provision_cp("company-1", "2026-07")

        assert preview["can_generate"] is False
        assert any(a["severity"] == "blocking" for a in preview["anomalies"])


class TestGenerate:
    def test_xlsx_commence_par_l_entete_zip(self):
        p1, p2, p3, p4 = _patch_all()
        with p1, p2, p3, p4:
            contenu = module.generate_provision_cp_export("company-1", "2026-07")

        assert contenu[:2] == b"PK"

    def test_csv_contient_la_ligne_total_et_les_colonnes_de_la_regle(self):
        p1, p2, p3, p4 = _patch_all()
        with p1, p2, p3, p4:
            contenu = module.generate_provision_cp_export(
                "company-1", "2026-07", file_format="csv"
            )

        texte = contenu.decode("utf-8-sig")
        assert "Total" in texte
        assert "BARUMET" in texte
        for colonne in ("Valeur d'un jour (maintien)", "Base dixième N-1", "Méthode", "Provision repos"):
            assert colonne in texte.splitlines()[0]


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
