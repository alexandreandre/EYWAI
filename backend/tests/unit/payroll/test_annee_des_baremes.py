"""Un bulletin ne se calcule pas en silence avec les barèmes d'une autre année.

L'année des barèmes ne vit pas dans une colonne de `payroll_config` (aucune
date d'effet : `version`, `is_active`, `created_at`, `last_checked_at`) mais
dans le contenu de deux d'entre eux : `smic.annee` (posée par la synchro du
SMIC à chaque écriture) et `reduction_generale.annee` (posée à la main avec
`smic_reference_horaire`, que la synchro ne met pas à jour). Le PSS et les
cotisations n'en portent pas ; le PAS porte `periode` (« mensuel_2026 »), mais
sa grille peut légitimement rester celle de l'année d'avant (loi de finances
tardive) : il n'est pas contrôlé.

- Barèmes d'une année antérieure au bulletin : refus, message pour la
  gestionnaire (janvier 2027 calculé avec le SMIC, le PASS et la réduction de
  2026, sinon).
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

    def test_janvier_2027_avec_les_baremes_2026_est_refuse(self):
        with pytest.raises(BaremesDUneAnneePassee) as refus:
            controler_annee_des_baremes(_baremes(), 2027)
        message = str(refus.value)
        assert "Les barèmes 2027 ne sont pas encore chargés" in message
        assert "contactez le support" in message
        assert "SMIC 2026" in message and "réduction générale 2026" in message

    def test_une_reduction_generale_restee_en_2026_suffit_a_refuser(self):
        # La synchro met le SMIC à jour, pas le SMIC de référence de la réduction.
        with pytest.raises(BaremesDUneAnneePassee) as refus:
            controler_annee_des_baremes(_baremes(smic=2027), 2027)
        assert "réduction générale 2026" in str(refus.value)
        assert "SMIC 2027" not in str(refus.value)

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


class TestLesDeuxCalculsRefusent:
    def test_le_bulletin_aux_heures(self, tmp_path):
        from app.modules.payroll.documents.payslip_run_heures import (
            run_payslip_generation_heures,
        )

        dossier = _dossier_salarie(tmp_path, 1)
        with pytest.raises(BaremesDUneAnneePassee):
            run_payslip_generation_heures(
                dossier, 2027, 1, tmp_path, baremes_override=_baremes(), persister=False
            )

    def test_le_bulletin_au_forfait_jours(self, tmp_path):
        from app.modules.payroll.documents.payslip_run_forfait import (
            run_payslip_generation_forfait,
        )

        dossier = _dossier_salarie(tmp_path, 1)
        with pytest.raises(BaremesDUneAnneePassee):
            run_payslip_generation_forfait(dossier, 2027, 1, tmp_path, baremes_override=_baremes())
