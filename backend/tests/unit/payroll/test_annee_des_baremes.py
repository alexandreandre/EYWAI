"""Un bulletin ne se calcule pas en silence avec les barèmes d'une autre année.

L'année des barèmes ne vit pas dans une colonne de `payroll_config` (aucune
date d'effet : `version`, `is_active`, `created_at`, `last_checked_at`) mais
dans le contenu de deux d'entre eux : `smic.annee` (posée par la synchro du
SMIC à chaque écriture) et `reduction_generale.annee` (posée à la main avec
`smic_reference_horaire`, que la synchro ne met pas à jour). Le PSS et les
cotisations n'en portent pas ; le PAS porte `periode` (« mensuel_2026 »), mais
sa grille peut légitimement rester celle de l'année d'avant (loi de finances
tardive) : il n'est pas contrôlé.

- Barèmes d'une année antérieure au bulletin : le bulletin se calcule avec le
  dernier barème connu, et une alerte le dit au bulletin et dans la liste du
  mois (12/10/2026, cap « alerte avec sortie manuelle ») : janvier 2027 ne
  doit pas se bloquer parce que le barème de la réduction générale, saisi à la
  main, n'a pas encore été remis à jour. Le calcul inverse (simulation, sans
  alerte à l'écran) garde le refus : son chiffre serait faux en silence.
- Barèmes d'une année postérieure : alerte sur le bulletin, sans le bloquer
  (décembre se corrige souvent en janvier).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.modules.payroll.engine.baremes_loader import (
    BaremesDUneAnneePassee,
    controler_annee_des_baremes,
)
from tests.unit.payroll.fixtures.baremes_snapshot import (
    baremes_snapshot,
    entreprise_snapshot,
)

pytestmark = pytest.mark.unit


def _baremes(*, smic: int | None = 2026, reduction: int | None = 2026) -> dict:
    baremes = copy.deepcopy(baremes_snapshot())
    if smic is not None:
        baremes["smic"]["annee"] = smic
    baremes["reduction_generale"] = {
        "actif": True,
        "tmin": 0.02,
        "p": 1.75,
        "point_sortie_smic": 3.0,
        "tdelta": {"fnal_moins_50": 0.3781, "fnal_50_et_plus": 0.3821},
        "smic_reference_horaire": 12.02,
    }
    if reduction is not None:
        baremes["reduction_generale"]["annee"] = reduction
    return baremes


class TestAnneeDesBaremes:
    def test_un_bulletin_2026_avec_les_baremes_2026_ne_dit_rien(self):
        assert controler_annee_des_baremes(_baremes(), 2026) == []

    def test_janvier_2027_avec_les_baremes_2026_se_calcule_avec_une_alerte(self):
        alertes = controler_annee_des_baremes(_baremes(), 2027)
        assert [a["message"] for a in alertes] == [
            "Barème 2026 du SMIC appliqué en 2027 : à régulariser dès la parution "
            "du nouveau.",
            "Barème 2026 de la réduction générale appliqué en 2027 : à régulariser "
            "dès la parution du nouveau.",
        ]
        for alerte in alertes:
            # Visible, mais ne bloque ni le calcul ni la validation.
            assert alerte["severity"] == "warning"
            assert alerte["critique"] is False

    def test_une_reduction_generale_restee_en_2026_n_alerte_que_sur_elle(self):
        # La synchro met le SMIC à jour, pas le barème de la réduction.
        alertes = controler_annee_des_baremes(_baremes(smic=2027), 2027)
        assert len(alertes) == 1
        assert alertes[0]["message"] == (
            "Barème 2026 de la réduction générale appliqué en 2027 : à régulariser "
            "dès la parution du nouveau."
        )

    def test_l_alerte_se_voit_dans_la_liste_du_mois(self):
        from app.modules.payslips.infrastructure.payslip_list_meta import (
            payslip_list_meta,
        )

        alertes = controler_annee_des_baremes(_baremes(smic=2027), 2027)
        ligne = payslip_list_meta({"alertes_baremes": alertes})
        assert alertes[0]["message"] in ligne["warnings"]

    def test_le_calcul_inverse_garde_le_refus(self):
        from app.modules.payroll.engine.baremes_loader import (
            refuser_baremes_d_une_annee_passee,
        )

        with pytest.raises(BaremesDUneAnneePassee) as refus:
            refuser_baremes_d_une_annee_passee(_baremes(smic=2027), 2027)
        assert "réduction générale 2026" in str(refus.value)
        assert "SMIC 2027" not in str(refus.value)
        refuser_baremes_d_une_annee_passee(_baremes(smic=2027, reduction=2027), 2027)

    def test_le_refus_s_affiche_comme_les_autres_refus_de_generation(self):
        # Les générateurs rendent une ValueError telle quelle à l'écran (400).
        assert issubclass(BaremesDUneAnneePassee, ValueError)

    def test_des_baremes_sans_annee_ne_sont_pas_controles(self):
        assert controler_annee_des_baremes(_baremes(smic=None, reduction=None), 2027) == []

    def test_un_bulletin_2026_regenere_avec_les_baremes_2027_porte_une_alerte(self):
        alertes = controler_annee_des_baremes(_baremes(smic=2027, reduction=2027), 2026)
        assert len(alertes) == 1
        alerte = alertes[0]
        assert alerte["code"] == "baremes_d_une_annee_suivante"
        # Visible, mais ne bloque pas la validation.
        assert alerte["severity"] == "warning"
        assert alerte["critique"] is False
        assert "2027" in alerte["message"] and "2026" in alerte["message"]


def _dossier_salarie(tmp_path: Path, mois: int) -> Path:
    dossier = tmp_path / "salarie"
    (dossier / "saisies").mkdir(parents=True)
    (dossier / "cumuls").mkdir()
    (dossier / "saisies" / f"{mois:02d}.json").write_text("{}", encoding="utf-8")
    contrat = {
        "salarie": {"nom": "Test", "prenom": "Jean"},
        "contrat": {
            "date_entree": "2020-01-01",
            "statut": "Non-Cadre",
            "temps_travail": {"duree_hebdomadaire": 35},
        },
        "remuneration": {"salaire_de_base": {"valeur": 2500}},
        "specificites_paie": {},
    }
    (dossier / "contrat.json").write_text(json.dumps(contrat), encoding="utf-8")
    (dossier / "entreprise.json").write_text(
        json.dumps({"entreprise": entreprise_snapshot()}), encoding="utf-8"
    )
    return dossier


def _alertes_annee_passee(bulletin: dict) -> list[str]:
    return [
        a["message"]
        for a in bulletin.get("alertes_baremes") or []
        if "appliqué en 2027" in str(a.get("message"))
    ]


def _dossier_calculable(tmp_path: Path, *, forfait: bool) -> Path:
    dossier = _dossier_salarie(tmp_path, 1)
    contrat = json.loads((dossier / "contrat.json").read_text(encoding="utf-8"))
    contrat["salarie"]["adresse"] = {"code_postal": "39100"}
    if forfait:
        contrat["contrat"].update({"is_forfait_jour": True, "statut": "Cadre"})
    (dossier / "contrat.json").write_text(json.dumps(contrat), encoding="utf-8")
    entreprise = json.loads((dossier / "entreprise.json").read_text(encoding="utf-8"))
    entreprise["entreprise"].setdefault("identification", {})["adresse"] = {"code_postal": "39100"}
    (dossier / "entreprise.json").write_text(json.dumps(entreprise), encoding="utf-8")
    return dossier


class TestLesDeuxCalculsSeFontAvecUneAlerte:
    @pytest.fixture(autouse=True)
    def _hors_ligne(self, monkeypatch):
        import httpx

        def reseau_interdit(*_a, **_k):
            raise AssertionError("appel réseau pendant un test unitaire")

        monkeypatch.setattr(httpx.Client, "send", reseau_interdit)

    @pytest.mark.parametrize("forfait", [False, True], ids=["aux_heures", "au_forfait_jours"])
    def test_janvier_2027_aux_baremes_2026(self, tmp_path, forfait):
        from app.core.paths import payroll_engine_root
        from app.modules.payroll.documents import payslip_run_forfait, payslip_run_heures

        calculer = (
            payslip_run_forfait.run_payslip_generation_forfait
            if forfait
            else payslip_run_heures.run_payslip_generation_heures
        )
        bulletin = calculer(
            _dossier_calculable(tmp_path, forfait=forfait), 2027, 1, payroll_engine_root(),
            baremes_override=_baremes(), persister=False,
        )
        assert bulletin["salaire_brut"] > 0
        assert len(_alertes_annee_passee(bulletin)) == 2
