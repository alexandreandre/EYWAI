"""Ligne « Montant net des heures compl/suppl exo. » du bulletin.

Le modèle de bulletin clarifié impose, sous le bloc impôt, le montant net des
heures supplémentaires exonérées d'impôt. C'est ce montant que le salarié
retrouve sur sa déclaration : il entre dans son revenu fiscal de référence.
Notre bulletin ne l'imprimait pas du tout.

Sa valeur, relevée sur les bulletins du cabinet de Colorplast — 27 bulletins de
janvier à juillet 2026, dont 22 avec des heures supplémentaires — est toujours :

    rémunération brute des HS − 6,8 % de la base CSG des HS

soit la CSG déductible afférente, et elle seule. La formule tombe juste 27 fois
sur 27 ; retrancher les 9,7 % de CSG/CRDS entière ne tombe jamais. C'est
cohérent avec la nature de la ligne : un montant *imposable* ne se diminue pas
d'une CSG non déductible ni de la CRDS, qui par construction ne réduisent pas
le revenu imposable.

C'est aussi la part exonérée que retranche le net imposable et que compte le
plafond de 7 500 € (R-361). Sous le plafond, le net imposable est le même qu'avec
les 9,7 % : seuls le compteur et le mois d'atteinte du plafond changent.

Chiffres repris des bulletins de janvier 2026 (env. de test).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.payroll.engine import calcul_net

pytestmark = pytest.mark.unit

#: Dumarel, janvier : 691,78 € d'heures sup, base CSG 679,67.
BRUT_HS_DUMAREL = 691.78
BASE_CSG_HS_DUMAREL = 679.67
ATTENDU_DUMAREL = 645.56

#: Moroche, janvier : 442,90 / 435,15 → 413,31.
BRUT_HS_MOROCHE = 442.91
BASE_CSG_HS_MOROCHE = 435.16
ATTENDU_MOROCHE = 413.32


#: Forme réelle du catalogue 2026 : une entrée `csg` unique dont la part
#: salariale se décompose. La première version de ce test utilisait une forme
#: qui n'existe pas (`csg_deductible` avec un taux nombre), et laissait donc
#: passer un moteur qui ne trouvait aucun taux et rendait le brut.
CATALOGUE_2026 = {"csg": {"id": "csg", "libelle": "CSG/CRDS", "salarial": {"deductible": 0.068, "non_deductible": 0.029}}}
#: Forme historique, encore présente dans les snapshots de test.
CATALOGUE_HISTORIQUE = {"csg_deductible": {"id": "csg_deductible", "salarial": 0.068}}


def _contexte(catalogue=None):
    cat = CATALOGUE_2026 if catalogue is None else catalogue
    return SimpleNamespace(
        month=1,
        cumuls={},
        contrat={"specificites_paie": {}},
        get_cotisation_by_id=lambda _id: cat.get(_id),
    )


def _lignes(base_csg_hs, taux=0.097, taux_csg_deductible=0.068):
    return [
        {
            "libelle": "CSG déductible",
            "base": 2334.11,
            "taux_salarial": taux_csg_deductible,
            "montant_salarial": 158.72,
        },
        {
            "libelle": "CSG/CRDS non déductible",
            "base": 2334.11,
            "montant_salarial": 67.69,
        },
        {
            "libelle": "CSG/CRDS sur HS non déductible",
            "base": base_csg_hs,
            "taux_salarial": taux,
            "montant_salarial": round(base_csg_hs * taux, 2),
        },
    ]


class TestMontantNetHeuresSupExonerees:
    def test_dumarel(self):
        montant = calcul_net.montant_net_hs_exonerees(
            _contexte(), _lignes(BASE_CSG_HS_DUMAREL), BRUT_HS_DUMAREL
        )
        assert montant == pytest.approx(ATTENDU_DUMAREL, abs=0.01)

    def test_moroche(self):
        montant = calcul_net.montant_net_hs_exonerees(
            _contexte(), _lignes(BASE_CSG_HS_MOROCHE), BRUT_HS_MOROCHE
        )
        assert montant == pytest.approx(ATTENDU_MOROCHE, abs=0.01)

    def test_sans_heures_sup_le_montant_est_nul(self):
        assert calcul_net.montant_net_hs_exonerees(_contexte(), _lignes(0.0), 0.0) == 0.0

    def test_sans_ligne_csg_sur_hs_on_retranche_la_csg_du_brut_hs(self):
        """Heures sup saisies à la main, sans ligne de CSG dédiée : on applique
        le taux à la rémunération des HS abattue, plutôt que de rendre le brut."""
        lignes = [l for l in _lignes(0.0) if "sur HS" not in l["libelle"]]
        montant = calcul_net.montant_net_hs_exonerees(
            _contexte(), lignes, BRUT_HS_DUMAREL
        )
        assert montant < BRUT_HS_DUMAREL
        assert montant == pytest.approx(BRUT_HS_DUMAREL * (1 - 0.068 * 0.9825), abs=0.5)

    def test_le_taux_vient_de_la_ligne_du_bulletin(self):
        """Le taux appliqué est celui que le bulletin a réellement utilisé."""
        montant = calcul_net.montant_net_hs_exonerees(
            _contexte(), _lignes(BASE_CSG_HS_DUMAREL, taux_csg_deductible=0.05),
            BRUT_HS_DUMAREL,
        )
        assert montant == pytest.approx(BRUT_HS_DUMAREL - 0.05 * BASE_CSG_HS_DUMAREL, abs=0.01)

    def test_repli_sur_le_catalogue_forme_2026(self):
        """Sans taux sur la ligne, le catalogue prend le relais — forme réelle,
        une entrée `csg` dont la part salariale se décompose."""
        lignes = _lignes(BASE_CSG_HS_DUMAREL)
        lignes[0].pop("taux_salarial")
        montant = calcul_net.montant_net_hs_exonerees(
            _contexte(CATALOGUE_2026), lignes, BRUT_HS_DUMAREL
        )
        assert montant == pytest.approx(ATTENDU_DUMAREL, abs=0.01)

    def test_repli_sur_le_catalogue_forme_historique(self):
        lignes = _lignes(BASE_CSG_HS_DUMAREL)
        lignes[0].pop("taux_salarial")
        montant = calcul_net.montant_net_hs_exonerees(
            _contexte(CATALOGUE_HISTORIQUE), lignes, BRUT_HS_DUMAREL
        )
        assert montant == pytest.approx(ATTENDU_DUMAREL, abs=0.01)

    def test_sans_aucun_taux_connu_on_ne_declare_rien(self):
        """Plutôt rendre zéro que le brut : un montant faux au revenu fiscal de
        référence est pire qu'une ligne absente."""
        lignes = _lignes(BASE_CSG_HS_DUMAREL)
        lignes[0].pop("taux_salarial")
        assert calcul_net.montant_net_hs_exonerees(
            _contexte({}), lignes, BRUT_HS_DUMAREL
        ) == 0.0


class TestPartExonereeDuNetImposable:
    """R-361 : brut des HS moins la seule CSG déductible (net-entreprises 2066, via Legisocial)."""

    BRUT = 2884.0
    COTISATIONS = 500.0 + round(BASE_CSG_HS_DUMAREL * 0.097, 2)

    def _net_imposable(self, cumuls=None, mois=6):
        contexte = _contexte()
        contexte.month = mois
        contexte.cumuls = {"cumuls": cumuls or {}}
        lignes = [l for l in _lignes(BASE_CSG_HS_DUMAREL) if "non déductible" not in l["libelle"] or "sur HS" in l["libelle"]]
        return calcul_net._calculer_net_imposable(
            contexte, self.BRUT, self.COTISATIONS, lignes, BRUT_HS_DUMAREL
        )

    def test_la_part_comptee_au_plafond_est_a_6_8(self, monkeypatch):
        monkeypatch.setattr(calcul_net, "_part_patronale_mutuelle_du_bulletin", lambda *a: 0.0)
        monkeypatch.setattr(calcul_net, "_get_part_salariale_mutuelle_non_deductible", lambda *a: 0.0)
        _, exonere = self._net_imposable()
        assert exonere == pytest.approx(ATTENDU_DUMAREL, abs=0.01)

    def test_sous_le_plafond_le_net_imposable_ne_change_pas(self, monkeypatch):
        monkeypatch.setattr(calcul_net, "_part_patronale_mutuelle_du_bulletin", lambda *a: 0.0)
        monkeypatch.setattr(calcul_net, "_get_part_salariale_mutuelle_non_deductible", lambda *a: 0.0)
        net, _ = self._net_imposable()
        csg_hs = round(BASE_CSG_HS_DUMAREL * 0.097, 2)
        attendu_a_9_7 = (self.BRUT - self.COTISATIONS) - (BRUT_HS_DUMAREL - csg_hs)
        assert net == pytest.approx(attendu_a_9_7, abs=0.01)

    def test_au_dela_du_plafond_le_surplus_redevient_imposable(self, monkeypatch):
        monkeypatch.setattr(calcul_net, "_part_patronale_mutuelle_du_bulletin", lambda *a: 0.0)
        monkeypatch.setattr(calcul_net, "_get_part_salariale_mutuelle_non_deductible", lambda *a: 0.0)
        net_sans, _ = self._net_imposable()
        net_avec, exonere = self._net_imposable({"hs_exonerees_ir_cumul": 7400.0})
        assert exonere == pytest.approx(100.0, abs=0.01)
        assert net_avec - net_sans == pytest.approx(ATTENDU_DUMAREL - 100.0, abs=0.01)

    def test_le_compteur_lit_le_cumul_deja_a_6_8(self):
        contexte = _contexte()
        contexte.month = 6
        contexte.cumuls = {"cumuls": {"hs_exonerees_ir_cumul": 970.0, "montant_net_hs_exonerees_cumul": 1000.0}}
        assert calcul_net._cumul_hs_exonerees_ir_debut_mois(contexte) == 1000.0
