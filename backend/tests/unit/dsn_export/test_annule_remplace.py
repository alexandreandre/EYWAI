"""DSN mensuelle déjà déposée, bulletin changé (R-174).

CT 2026.1 § 1.4.3.3 : l'annule et remplace intégral se dépose au plus tard la
veille à minuit de l'échéance ; au-delà, la correction va sur une paie suivante.
Le numéro d'ordre (05.004) repère la déclaration remplacée, un rang inférieur n'est
pas intégré. La rubrique 05.006 ne vaut que pour les signalements : DSN-VAL la
refuse sur une mensuelle (CST-04).
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.dsn_export.application.builder import (
    build_declaration,
    build_parsed_dsn_from_payroll,
)
from app.modules.dsn_export.domain.rectification import (
    DeclarationRemplacee,
    avis_mois_deja_declare,
    lire_numero_ordre,
    refus_annule_remplace,
)
from app.modules.dsn_export.domain.writer import encode_dsn_bytes
from app.modules.dsn_import.domain.parser import parse_dsn_content
from app.modules.exports.infrastructure import export_dsn
from tests.unit.dsn_export.test_builder_versement import BULLETIN, SALARIE, SOCIETE

pytestmark = pytest.mark.unit

REMPLACEE = DeclarationRemplacee(ordre=1)


def _fichier(**options) -> bytes:
    fichier, _ = build_parsed_dsn_from_payroll(
        SOCIETE, [{"employee": SALARIE, "payslip_data": BULLETIN}], "2026-10", **options
    )
    return encode_dsn_bytes(fichier)


def _rubriques_05(contenu: bytes) -> dict:
    return {
        ligne.split(",")[0]: ligne.split(",", 1)[1].strip("'")
        for ligne in contenu.decode("iso-8859-15").splitlines()
        if ligne.startswith("S20.G00.05.")
    }


@pytest.mark.parametrize("valeur,ordre", [("1", 1), (3, 3), ("0", 0)])
def test_numero_d_ordre_lu(valeur, ordre):
    assert lire_numero_ordre(valeur) == DeclarationRemplacee(ordre=ordre)


@pytest.mark.parametrize("mauvais", ["", "abc", "01", "-1", "1234567890123456", None])
def test_numero_d_ordre_mal_forme_refuse(mauvais):
    with pytest.raises(ValueError, match="numéro d'ordre"):
        lire_numero_ordre(mauvais)


def test_par_defaut_la_declaration_reste_normale():
    bloc = build_declaration("2026-10")
    assert bloc.type_declaration == "01"
    assert bloc.rubriques["S20.G00.05.002"] == "01"
    assert bloc.rubriques["S20.G00.05.004"] == "1"
    assert "S20.G00.05.006" not in bloc.rubriques


def test_annule_et_remplace_porte_le_type_et_un_rang_superieur_sans_05_006():
    bloc = build_declaration("2026-10", remplace=REMPLACEE)
    assert bloc.type_declaration == "03"
    assert bloc.rubriques["S20.G00.05.002"] == "03"
    assert bloc.rubriques["S20.G00.05.004"] == "2"
    assert "S20.G00.05.006" not in bloc.rubriques


def test_le_fichier_complet_sans_demande_reste_de_type_01():
    rubriques = _rubriques_05(_fichier())
    assert rubriques["S20.G00.05.002"] == "01"
    assert "S20.G00.05.006" not in rubriques


def test_le_fichier_annule_et_remplace_se_relit_et_garde_tout_le_mois():
    normal = _fichier()
    remplacant = _fichier(remplace=REMPLACEE)
    rubriques = _rubriques_05(remplacant)
    assert rubriques["S20.G00.05.002"] == "03"
    assert "S20.G00.05.006" not in rubriques
    relu = parse_dsn_content(remplacant, file_name="essai.dsn")
    assert relu.declaration.type_declaration == "03"
    # Intégral : hors bloc 05, rien ne change.
    sans_05 = lambda octets: [
        l for l in octets.decode("iso-8859-15").splitlines()
        if not l.startswith(("S20.G00.05.", "S90."))
    ]
    assert sans_05(normal) == sans_05(remplacant)


@pytest.mark.parametrize(
    "effectif,aujourd_hui,admis",
    [
        (18, date(2026, 11, 14), True),
        (18, date(2026, 11, 15), False),
        (60, date(2026, 11, 4), True),
        (60, date(2026, 11, 5), False),
    ],
)
def test_date_limite_veille_de_l_echeance(effectif, aujourd_hui, admis):
    refus = refus_annule_remplace("2026-10", effectif, aujourd_hui)
    assert (refus is None) is admis
    if not admis:
        assert "paie d'un mois suivant" in refus


def test_decembre_echeance_en_janvier():
    assert refus_annule_remplace("2026-12", 18, date(2027, 1, 14)) is None
    assert refus_annule_remplace("2026-12", 18, date(2027, 1, 15)) is not None


def test_avis_avant_la_date_limite_nomme_le_mois_et_la_date():
    avis = avis_mois_deja_declare("2026-10", 18, date(2026, 11, 8))
    assert "octobre 2026" in avis
    assert "14/11/2026" in avis
    assert "annule et remplace" in avis


def test_avis_apres_la_date_limite_dit_ce_qui_reste():
    avis = avis_mois_deja_declare("2026-10", 18, date(2026, 11, 20))
    assert "octobre 2026" in avis
    assert "paie d'un mois suivant" in avis
    assert "ticket" in avis


def _apercu(deja_declarees):
    with patch.object(export_dsn, "get_company_data", return_value={"siret": "1", "settings": {}}), patch.object(
        export_dsn,
        "get_dsn_employees_data",
        return_value=([], {
            "nombre_salaries": 0, "nombre_contrats": 0, "masse_salariale_brute": 0,
            "total_charges": 0, "total_net_imposable": 0, "total_pas": 0,
        }),
    ), patch.object(export_dsn, "check_dsn_data", return_value=([], [])), patch.object(
        export_dsn, "raison_de_refus_dsn_mois_repris", return_value=None
    ), patch.object(export_dsn, "periodes_deposees", return_value=frozenset(deja_declarees)):
        return export_dsn.preview_dsn("co", "2026-10", "dsn_mensuelle_normale")


def test_l_apercu_previent_quand_le_mois_a_deja_une_dsn():
    assert any("annule et remplace" in a or "paie d'un mois suivant" in a for a in _apercu({"2026-10"})["warnings"])


def test_l_apercu_ne_dit_rien_pour_un_mois_sans_dsn():
    assert _apercu({"2026-09"})["warnings"] == []


def test_generation_refusee_apres_la_date_limite():
    with patch.object(export_dsn, "raison_de_refus_dsn_mois_repris", return_value=None), patch.object(
        export_dsn, "get_company_data", return_value={"settings": {"effectif_seuils": {"2026": 18}}}
    ), patch.object(export_dsn, "_aujourd_hui_a_paris", return_value=date(2026, 11, 20)), patch.object(
        export_dsn, "get_dsn_employees_data"
    ) as lecture:
        with pytest.raises(ValueError, match="paie d'un mois suivant"):
            export_dsn.generate_dsn_file("co", "2026-10", "dsn_mensuelle_normale", remplace=REMPLACEE)
    lecture.assert_not_called()
