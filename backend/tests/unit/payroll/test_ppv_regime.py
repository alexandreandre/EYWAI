"""Prime de partage de la valeur : nature, CSG/CRDS, plafonds et nombre de primes. [G3]

Le moteur ne reconnaissait la PPV que par l'identifiant du catalogue
(`prime_partage_valeur`) : une PPV saisie par son nom suivait le chemin
générique. Il ne regardait que l'effectif, ne contrôlait ni la rémunération
(3 Smic), ni le plafond, ni le nombre de primes, et n'appliquait jamais la
CSG/CRDS : à 50 salariés et plus, la PPV entrait au net imposable sans un
centime de CSG.

Règles (BOSS, « Mesures exceptionnelles — protection du pouvoir d'achat » ;
Urssaf, « Prime de partage de la valeur », mise à jour du 07/09/2026) :
- du 01/01/2024 au 31/12/2026, exonération d'impôt, de CSG/CRDS et de forfait
  social pour les entreprises de moins de 50 salariés et les salariés payés
  moins de 3 Smic sur les 12 mois précédant le versement ;
- sinon : exonérée de cotisations, soumise à CSG/CRDS (9,7 %, sans abattement),
  imposable, et forfait social de 20 % dès 250 salariés ;
- jusqu'à deux primes par an, 3 000 € au total (6 000 € avec un accord
  d'intéressement) : au-delà, la part en trop est soumise comme du salaire.

L'effectif est celui des seuils (`effectif_retenu`), jamais `companies.effectif`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.payroll.engine import ppv

pytestmark = pytest.mark.unit

SMIC = 12.31
HEURES = 151.67  # 3 Smic mensuels : 5 601,17 €


def _ranger(montant=100.0, *, effectif=5, remuneration=2500.0, deja=None, accord=False, libelle="Prime de partage de la valeur"):
    prime = {"prime_id": "prime_partage_valeur", "libelle": libelle, "montant": montant}
    donnees = {
        "deja_versees": list(deja or []),
        "remuneration_mensuelle_moyenne": remuneration,
        "accord_interessement": accord,
    }
    return ppv.classer_ppv(
        prime,
        effectif=effectif,
        donnees=donnees,
        smic_horaire=SMIC,
        heures_mensuelles=HEURES,
        annee=2026,
    )


class TestNature:
    @pytest.mark.parametrize(
        "prime_id, libelle",
        [
            ("prime_partage_valeur", "Prime"),
            ("ppv_juillet", "PPV juillet"),
            ("prime_de_partage", "Prime de partage de la valeur"),
            ("prime_ppv", "Prime PPV 2026"),
        ],
    )
    def test_reconnue_par_l_identifiant_ou_le_libelle(self, prime_id, libelle):
        assert ppv.est_une_ppv(prime_id, libelle)

    @pytest.mark.parametrize("libelle", ["Prime exceptionnelle", "Prime d'objectifs", "Rappel"])
    def test_une_autre_prime_n_en_est_pas_une(self, libelle):
        assert not ppv.est_une_ppv(libelle.replace(" ", "_").lower(), libelle)


class TestRegime:
    def test_moins_de_50_et_moins_de_3_smic_exoneree_de_tout(self):
        r = _ranger()
        assert [p["montant"] for p in r.non_soumises] == [100.0]
        assert r.soumises_impot == [] and r.soumises == [] and r.lignes_cotisations == []

    def test_50_salaries_et_plus_csg_crds_et_impot(self):
        r = _ranger(effectif=60)
        (prime,) = r.soumises_impot
        assert prime["montant"] == 100.0
        assert prime["csg_deductible"] == pytest.approx(6.80)
        assert prime["csg_non_deductible"] == pytest.approx(2.90)
        assert sum(l["montant_salarial"] for l in r.lignes_cotisations) == pytest.approx(9.70)
        assert r.non_soumises == []

    def test_au_moins_3_smic_sur_12_mois_csg_crds_aussi(self):
        r = _ranger(remuneration=5700.0)
        assert [p["montant"] for p in r.soumises_impot] == [100.0]

    def test_forfait_social_des_250_salaries(self):
        r = _ranger(effectif=300)
        forfait = [l for l in r.lignes_cotisations if "forfait social" in l["libelle"].lower()]
        assert len(forfait) == 1
        assert forfait[0]["montant_patronal"] == pytest.approx(20.0)
        assert forfait[0]["montant_salarial"] == 0.0

    def test_pas_de_forfait_social_sous_250(self):
        r = _ranger(effectif=60)
        assert not [l for l in r.lignes_cotisations if "forfait social" in l["libelle"].lower()]


class TestPlafondsEtNombre:
    def test_au_dela_de_3000_la_part_en_trop_est_soumise(self):
        r = _ranger(500.0, deja=[2800.0])
        assert [p["montant"] for p in r.non_soumises] == [200.0]
        assert [p["montant"] for p in r.soumises] == [300.0]
        assert r.alertes and "3 000" in r.alertes[0]["message"]

    def test_6000_avec_un_accord_d_interessement(self):
        r = _ranger(500.0, deja=[2800.0], accord=True)
        assert [p["montant"] for p in r.non_soumises] == [500.0]
        assert r.soumises == []

    def test_une_troisieme_prime_n_est_plus_exoneree(self):
        r = _ranger(100.0, deja=[100.0, 100.0])
        assert [p["montant"] for p in r.soumises] == [100.0]
        assert r.non_soumises == []
        assert r.alertes and "deux" in r.alertes[0]["message"]

    def test_la_prime_rangee_compte_pour_la_suivante_du_meme_mois(self):
        donnees = {"deja_versees": [], "remuneration_mensuelle_moyenne": 2500.0}
        for _ in range(3):
            r = ppv.classer_ppv(
                {"prime_id": "prime_partage_valeur", "libelle": "PPV", "montant": 100.0},
                effectif=5,
                donnees=donnees,
                smic_horaire=SMIC,
                heures_mensuelles=HEURES,
                annee=2026,
            )
        assert [p["montant"] for p in r.soumises] == [100.0]


class TestAuNet:
    def test_la_csg_de_la_ppv_sort_du_net_et_la_deductible_de_l_imposable(self):
        from .helpers import build_test_contexte
        from app.modules.payroll.engine.calcul_net import calculer_net_et_impot

        ctx = build_test_contexte(salaire_base=2000.0)
        sans = calculer_net_et_impot(ctx, 2000.0, [], 400.0, [], 0.0, 0.0, [])
        ppv_csg = {
            "prime_id": "prime_partage_valeur",
            "libelle": "Prime de partage de la valeur",
            "montant": 100.0,
            "csg_deductible": 6.80,
            "csg_non_deductible": 2.90,
        }
        avec = calculer_net_et_impot(ctx, 2000.0, [], 400.0, [], 0.0, 0.0, [ppv_csg])

        assert avec["net_imposable"] == pytest.approx(sans["net_imposable"] + 100.0 - 6.80)
        assert avec["net_a_payer"] == pytest.approx(sans["net_a_payer"] + 100.0 - 9.70)
        assert avec["montant_net_social"] == pytest.approx(
            sans["montant_net_social"] + 100.0 - 9.70
        )


def test_les_deux_generateurs_rangent_la_ppv_par_sa_nature():
    racine = Path(__file__).resolve().parents[3] / "app" / "modules" / "payroll" / "documents"
    for nom in ("payslip_run_heures.py", "payslip_run_forfait.py"):
        source = (racine / nom).read_text(encoding="utf-8")
        assert "classer_ppv(" in source, nom
        assert 'prime_id == "prime_partage_valeur"' not in source, nom
