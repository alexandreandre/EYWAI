"""Bulletin d'un stagiaire (contrat « Stage ») : cotisations, net imposable, impôt, mentions.

Sources :
- BOSS, exonération stagiaires, § 70 et 80
  (https://boss.gouv.fr/portail/accueil/exonerations/exoneration-stagiaires.html) :
  la gratification est exclue de l'assiette dans la limite de 15 % du plafond
  horaire de la Sécurité sociale par heure de stage (4,50 €/h en 2026) ; « quel
  que soit son montant », elle n'est assujettie ni à la retraite complémentaire,
  ni à l'assurance chômage, ni à la contribution au dialogue social. Au-delà de
  la franchise, maladie, vieillesse, allocations familiales, CSG/CRDS, CSA,
  FNAL et versement mobilité restent dus sur la part qui dépasse.
- CGI art. 81 bis (https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000029236245) :
  la gratification est exonérée d'impôt sur le revenu dans la limite du montant
  annuel du SMIC, comme le salaire d'un apprenti.
- net-entreprises, fiche 1891 : la rémunération nette fiscale déclarée reste la
  gratification nette ; seule la part soumise au prélèvement est réduite (la
  part exonérée est déclarée à part). Le net imposable du bulletin reste donc
  la gratification, et c'est la base du prélèvement qui tombe à zéro.

Stage à 35 h : 151,67 h × 4,50 € = 682,50 € de franchise.
"""

from __future__ import annotations

import copy

import pytest

from app.modules.payroll.documents.bulletin_view import construire_vue_bulletin
from app.modules.payroll.engine.bulletin import creer_bulletin_final
from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from app.modules.payroll.engine.calcul_net import _base_pas_du_mois, calculer_net_et_impot

from .fixtures.baremes_snapshot import baremes_snapshot
from .helpers import build_test_contexte
from .test_bulletin_view import _rendre

pytestmark = pytest.mark.unit

FRANCHISE = 682.50
MUTUELLE_FICHE = {"adhesion": True, "montant_salarial": 17.62, "montant_patronal": 17.62}
#: Cotisations que la gratification ne supporte jamais (BOSS § 70) ; l'AGS et
#: l'APEC suivent l'assurance chômage et la retraite complémentaire des cadres.
JAMAIS_DUES = {
    "retraite_comp_t1",
    "retraite_comp_t2",
    "ceg_t1",
    "ceg_t2",
    "cet",
    "apec",
    "assurance_chomage",
    "ags",
    "dialogue_social",
}
MENTION_STAGIAIRE = (
    "Stagiaire : gratification exonérée d'impôt sur le revenu dans la limite du SMIC annuel."
)


#: Les lignes du barème de production (identifiants et taux 2026), pour que
#: chaque cotisation visée existe et puisse être écartée.
COTISATIONS_2026 = [
    {"id": "ags", "libelle": "Cotisation AGS", "base": "brut", "salarial": None, "patronal": 0.0025},
    {"id": "retraite_comp_t1", "libelle": "Retraite Complémentaire Tranche 1 (AGIRC-ARRCO)",
     "base": "brut_plafonne", "salarial": 0.0315, "patronal": 0.0472},
    {"id": "retraite_comp_t2", "libelle": "Retraite Complémentaire Tranche 2 (AGIRC-ARRCO)",
     "base": "tranche_2", "salarial": 0.0864, "patronal": 0.1295},
    {"id": "ceg_t1", "libelle": "Contribution d'Équilibre Général (CEG) T1",
     "base": "brut_plafonne", "salarial": 0.0086, "patronal": 0.0129},
    {"id": "ceg_t2", "libelle": "Contribution d'Équilibre Général (CEG) T2",
     "base": "tranche_2", "salarial": 0.0108, "patronal": 0.0162},
    {"id": "cet", "libelle": "Contribution d'Équilibre Technique (CET)",
     "base": "assiette_cet", "salarial": 0.0014, "patronal": 0.0021},
    {"id": "apec", "libelle": "Cotisation APEC (Cadres)",
     "base": "brut_cadre_4_plafonds", "salarial": 0.00024, "patronal": 0.00036},
    {"id": "allocations_familiales", "libelle": "Allocations familiales", "base": "brut",
     "salarial": None, "patronal": None, "patronal_plein": 0.0525, "patronal_reduit": 0.0325},
    {"id": "assurance_chomage", "libelle": "Assurance Chômage", "base": "brut",
     "salarial": None, "patronal": 0.04},
    {"id": "csa", "libelle": "Contribution Solidarité Autonomie (CSA)", "base": "brut",
     "salarial": None, "patronal": 0.003},
    {"id": "csg", "libelle": "CSG/CRDS", "base": "brut",
     "salarial": {"deductible": 0.068, "non_deductible": 0.029}, "patronal": None},
    {"id": "dialogue_social", "libelle": "Contribution au dialogue social", "base": None,
     "salarial": None, "patronal": 0.00016},
    {"id": "fnal", "libelle": "Fonds National d'Aide au Logement (FNAL)", "base": "brut",
     "salarial": None, "patronal": {"taux_moins_50": 0.001, "taux_50_et_plus": 0.005}},
    {"id": "securite_sociale_maladie", "libelle": "Sécurité sociale - Maladie, Maternité, Invalidité, Décès",
     "base": "brut", "salarial": None, "patronal": None, "patronal_plein": 0.13, "patronal_reduit": 0.07},
    {"id": "retraite_secu_plafond", "libelle": "Sécurité sociale Vieillesse plafonnée",
     "base": "brut_plafonne", "salarial": 0.069, "patronal": 0.0855},
    {"id": "retraite_secu_deplafond", "libelle": "Sécurité sociale Vieillesse déplafonnée",
     "base": "brut", "salarial": 0.004, "patronal": 0.0211},
]


def _baremes_2026() -> dict:
    baremes = copy.deepcopy(baremes_snapshot())
    baremes["stage"]["plafond_horaire_ss"] = 30.0
    baremes["cotisations"] = {"cotisations": copy.deepcopy(COTISATIONS_2026)}
    return baremes


def _stagiaire(gratification: float, *, mutuelle: dict | None = None, taux_pas: float = 0.0):
    ctx = build_test_contexte(
        salaire_base=gratification,
        type_contrat="Stage",
        taux_pas=taux_pas,
        baremes=_baremes_2026(),
        specificites_extra={"mutuelle": mutuelle} if mutuelle else None,
    )
    ctx.year = 2026
    ctx.cumuls = {"cumuls": {"net_imposable": 0.0}}
    return ctx


def _bulletin(ctx, brut: float) -> dict:
    lignes, total_sal = calculer_cotisations(ctx, brut)
    nets = calculer_net_et_impot(ctx, brut, lignes, total_sal, [], 0.0)
    return creer_bulletin_final(ctx, brut, [], lignes, nets, [], 2026, 4)


class TestSousLaFranchise:
    def test_aucune_cotisation(self):
        lignes, total = calculer_cotisations(_stagiaire(600.0, mutuelle=MUTUELLE_FICHE), 600.0)
        assert total == 0.0
        assert [l["coti_id"] for l in lignes] == ["exoneration_stage"]

    def test_net_imposable_sans_part_patronale_de_mutuelle_non_calculee(self):
        """La fiche porte une mutuelle, le bulletin n'en calcule aucune ligne :
        rien à réintégrer (617,62 auparavant, 600 + 17,62 lus sur la fiche)."""
        ctx = _stagiaire(600.0, mutuelle=MUTUELLE_FICHE)
        lignes, total_sal = calculer_cotisations(ctx, 600.0)
        nets = calculer_net_et_impot(ctx, 600.0, lignes, total_sal, [], 0.0)
        assert nets["net_imposable"] == pytest.approx(600.0, abs=0.001)

    def test_gratification_exoneree_d_impot_dans_la_limite_du_smic_annuel(self):
        ctx = _stagiaire(600.0, mutuelle=MUTUELLE_FICHE, taux_pas=5.0)
        lignes, total_sal = calculer_cotisations(ctx, 600.0)
        nets = calculer_net_et_impot(ctx, 600.0, lignes, total_sal, [], 0.0)
        assert nets["base_pas"] == pytest.approx(0.0, abs=0.001)
        assert nets["montant_impot_pas"] == pytest.approx(0.0, abs=0.001)

    def test_au_dela_du_smic_annuel_la_gratification_redevient_imposable(self):
        ctx = _stagiaire(600.0)
        plafond_annuel = ctx.smic_mensuel * 12
        ctx.cumuls = {"cumuls": {"net_imposable": plafond_annuel - 100.0}}
        assert _base_pas_du_mois(ctx, 600.0) == pytest.approx(500.0, abs=0.05)

    def test_mention_d_exoneration_d_impot_du_stagiaire(self):
        bulletin = _bulletin(_stagiaire(600.0, mutuelle=MUTUELLE_FICHE), 600.0)
        assert bulletin["synthese_net"]["exoneration_ir_stagiaire"] is True
        impot = construire_vue_bulletin(bulletin)["pied"]["impot"]
        assert impot["exoneration_stagiaire"] is True
        assert impot["exoneration_apprenti"] is False
        html = _rendre(bulletin)
        assert MENTION_STAGIAIRE in html
        assert "Apprenti : rémunération exonérée" not in html

    def test_evolution_de_la_remuneration_nulle(self):
        """Aucune cotisation salariale chômage ni maladie, ni avant ni après 2018 :
        la mention « dont évolution… » vaut 0 (8,70 auparavant, repli sur le brut)."""
        bulletin = _bulletin(_stagiaire(600.0, mutuelle=MUTUELLE_FICHE), 600.0)
        pied = construire_vue_bulletin(bulletin)["pied"]
        assert pied["evolution_remuneration"] == 0.0
        assert pied["mention_evolution"] not in _rendre(bulletin)


class TestAuDelaDeLaFranchise:
    def test_ni_retraite_complementaire_ni_chomage_ni_ags_ni_dialogue_social(self):
        lignes, _ = calculer_cotisations(_stagiaire(900.0), 900.0)
        presentes = {l.get("coti_id") for l in lignes}
        assert presentes.isdisjoint(JAMAIS_DUES), presentes & JAMAIS_DUES

    def test_les_autres_cotisations_seulement_sur_la_part_au_dela_de_la_franchise(self):
        lignes, total = calculer_cotisations(_stagiaire(900.0), 900.0)
        exoneree = next(l for l in lignes if l["coti_id"] == "exoneration_stage")
        assert exoneree["base"] == FRANCHISE
        maladie = next(l for l in lignes if l.get("coti_id") == "securite_sociale_maladie")
        assert maladie["base"] == pytest.approx(217.50, abs=0.001)
        vieillesse = next(l for l in lignes if l.get("coti_id") == "retraite_secu_plafond")
        assert vieillesse["base"] == pytest.approx(217.50, abs=0.001)
        for ligne in lignes:
            if ligne["coti_id"] == "exoneration_stage" or ligne.get("base") is None:
                continue
            assert ligne["base"] <= 217.50 + 0.001, ligne
        assert total > 0

    def test_evolution_de_la_remuneration_nulle(self):
        bulletin = _bulletin(_stagiaire(900.0), 900.0)
        assert construire_vue_bulletin(bulletin)["pied"]["evolution_remuneration"] == 0.0


class TestSalarieOrdinaire:
    def test_pas_de_drapeau_stagiaire_sur_le_bulletin_d_un_salarie(self):
        ctx = build_test_contexte(salaire_base=2000.0, type_contrat="CDI", baremes=_baremes_2026())
        ctx.year = 2026
        bulletin = _bulletin(ctx, 2000.0)
        assert "exoneration_ir_stagiaire" not in bulletin["synthese_net"]
        assert construire_vue_bulletin(bulletin)["pied"]["impot"]["exoneration_stagiaire"] is False

    def test_la_part_patronale_calculee_reste_au_net_imposable(self):
        """Garde : un salarié dont le bulletin porte la mutuelle garde sa part
        patronale réintégrée au net imposable."""
        mutuelle = {"adhesion": True, "montant_salarial": 20.0, "montant_patronal": 30.0}
        avec = build_test_contexte(
            salaire_base=2000.0,
            type_contrat="CDI",
            baremes=_baremes_2026(),
            specificites_extra={"mutuelle": mutuelle},
        )
        lignes, total_sal = calculer_cotisations(avec, 2000.0)
        assert any(l.get("coti_id") == "mutuelle" for l in lignes)
        csg_nd = sum(
            l.get("montant_salarial") or 0.0
            for l in lignes
            if "csg/crds non déductible" in (l.get("libelle") or "").lower()
        )
        nets = calculer_net_et_impot(avec, 2000.0, lignes, total_sal, [], 0.0)
        assert nets["net_imposable"] == pytest.approx(
            2000.0 - total_sal + csg_nd + 30.0, abs=0.01
        )
