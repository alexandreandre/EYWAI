"""Versement trimestriel aux organismes de prévoyance et de mutuelle (blocs 20 et 55).

FAQ DSN Organismes complémentaires (net-entreprises, V4 2023-10, p. 47-48) :
la DSN du dernier mois du trimestre porte un bloc 20 et ses blocs 55 pour les
cotisations dues du trimestre, 55.004 au format AAAATnn, somme des 55 = 20.005.
Pour un organisme complémentaire, 20.006 et 20.007 valent 01012000.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.dsn_export.domain.versements_complementaires import (
    bloc_versement_complementaire,
    cotisations_par_contrat,
    date_de_paiement,
    est_fin_de_trimestre,
    mois_precedents_du_trimestre,
    periode_d_affectation,
)
from app.modules.dsn_import.domain.model import (
    AffiliationBlock,
    ContratBlock,
    CotisationIndividuelleBlock,
    EtablissementBlock,
    IndividuBlock,
    VersementBlock,
)

pytestmark = pytest.mark.unit

CONTRATS = [
    {"reference": "20000802485169", "organisme": "AGGEEV", "delegataire": "DBALO1", "ordre": "1",
     "type_population": "NON CADRE"},
    {"reference": "10000802485169", "organisme": "AGGEEV", "delegataire": "DBALO1", "ordre": "2",
     "type_population": "00"},
    {"reference": "30000802485169", "organisme": "AGGEEV", "delegataire": "DBALO1", "ordre": "3",
     "type_population": "CADRE"},
    {"reference": "RG153609782", "organisme": "ALMRS1", "ordre": "4"},
]
AGGEEV = {"organisme": "AGGEEV", "bic": "CEPAFRPP382", "iban": "FR7600000000000000000000000",
          "delegataire": "DBALO1", "mode": "05", "jour_paiement": "25"}


def _cotisation(affiliation: str, montant: str, base: str = "31") -> CotisationIndividuelleBlock:
    return CotisationIndividuelleBlock(
        code="059",
        identifiant_affiliation=affiliation,
        rubriques={"S21.G00.81.001": "059", "S21.G00.81.004": montant, "_base": f"{base}#0"},
    )


def _salarie(affiliations: dict[str, str], cotisations: list) -> IndividuBlock:
    return IndividuBlock(
        contrats=[
            ContratBlock(
                affiliations=[
                    AffiliationBlock(
                        identifiant_affiliation=ident,
                        rubriques={"S21.G00.70.012": ident, "S21.G00.70.013": ordre},
                    )
                    for ident, ordre in affiliations.items()
                ],
                versements=[VersementBlock(cotisations_individuelles=cotisations)],
            )
        ]
    )


def test_seul_le_dernier_mois_du_trimestre_porte_le_versement():
    assert [m for m in range(1, 13) if est_fin_de_trimestre(f"2026-{m:02d}")] == [3, 6, 9, 12]


def test_la_periode_d_affectation_est_le_trimestre():
    assert periode_d_affectation("2026-12") == "2026T04"
    assert periode_d_affectation("2026-03") == "2026T01"


def test_les_deux_mois_d_avant_sont_ceux_du_trimestre():
    assert mois_precedents_du_trimestre("2026-12") == ["2026-10", "2026-11"]
    assert mois_precedents_du_trimestre("2027-03") == ["2027-01", "2027-02"]


def test_la_date_de_paiement_est_le_jour_du_cabinet_le_mois_suivant():
    assert date_de_paiement("2026-12", "25") == "25012027"
    assert date_de_paiement("2026-06", "25") == "25072026"
    # Un jour au-delà du mois tombe sur son dernier jour.
    assert date_de_paiement("2027-01", "31") == "28022027"
    assert date_de_paiement("2026-12", None) is None


def test_la_somme_par_contrat_ne_prend_que_les_bases_31_de_ses_affiliations():
    etab = EtablissementBlock(
        individus=[
            _salarie({"1": "2", "2": "4"}, [_cotisation("1", "528.24"), _cotisation("2", "189.96")]),
            _salarie({"1": "1"}, [_cotisation("1", "150.60"), _cotisation("1", "99.00", base="03")]),
        ]
    )
    assert cotisations_par_contrat(etab) == {
        "2": Decimal("528.24"),
        "4": Decimal("189.96"),
        "1": Decimal("150.60"),
    }


def test_le_bloc_20_porte_la_somme_de_ses_55_un_par_contrat_meme_a_zero():
    montants = {"1": Decimal("497.62"), "2": Decimal("1584.72")}
    bloc = bloc_versement_complementaire(AGGEEV, CONTRATS, montants, "2026-06")

    assert bloc.identifiant == "AGGEEV"
    assert bloc.montant == pytest.approx(2082.34)
    r = bloc.rubriques
    assert r["S21.G00.20.001"] == "AGGEEV"
    assert r["S21.G00.20.003"] == "CEPAFRPP382"
    assert r["S21.G00.20.005"] == "2082.34"
    assert r["S21.G00.20.006"] == "01012000"
    assert r["S21.G00.20.007"] == "01012000"
    assert r["S21.G00.20.008"] == "DBALO1"
    assert r["S21.G00.20.010"] == "05"
    assert r["S21.G00.20.011"] == "25072026"
    assert r["_composants_55"] == [
        {"S21.G00.55.001": "497.62", "S21.G00.55.002": "NON CADRE",
         "S21.G00.55.003": "20000802485169", "S21.G00.55.004": "2026T02"},
        {"S21.G00.55.001": "1584.72", "S21.G00.55.002": "00",
         "S21.G00.55.003": "10000802485169", "S21.G00.55.004": "2026T02"},
        {"S21.G00.55.001": "0.00", "S21.G00.55.002": "CADRE",
         "S21.G00.55.003": "30000802485169", "S21.G00.55.004": "2026T02"},
    ]


def test_sans_type_de_population_ni_jour_de_paiement_les_rubriques_sont_absentes():
    versement = {"organisme": "ALMRS1", "bic": "B", "iban": "I", "mode": "05"}
    bloc = bloc_versement_complementaire(versement, CONTRATS, {"4": Decimal("575.56")}, "2026-06")
    assert "S21.G00.20.011" not in bloc.rubriques
    assert "S21.G00.20.008" not in bloc.rubriques
    assert bloc.rubriques["_composants_55"] == [
        {"S21.G00.55.001": "575.56", "S21.G00.55.003": "RG153609782", "S21.G00.55.004": "2026T02"}
    ]


def test_les_55_suivent_leur_bloc_20_dans_le_fichier():
    from app.modules.dsn_export.domain.writer import write_versement_organisme

    bloc = bloc_versement_complementaire(AGGEEV, CONTRATS, {"2": Decimal("10.00")}, "2026-12")
    lignes: list[str] = []
    write_versement_organisme(bloc, lignes)
    codes = [ligne.split(",")[0] for ligne in lignes]
    assert codes == [
        "S21.G00.20.001", "S21.G00.20.003", "S21.G00.20.004", "S21.G00.20.005",
        "S21.G00.20.006", "S21.G00.20.007", "S21.G00.20.008", "S21.G00.20.010",
        "S21.G00.20.011",
        "S21.G00.55.001", "S21.G00.55.002", "S21.G00.55.003", "S21.G00.55.004",
        "S21.G00.55.001", "S21.G00.55.002", "S21.G00.55.003", "S21.G00.55.004",
        "S21.G00.55.001", "S21.G00.55.002", "S21.G00.55.003", "S21.G00.55.004",
    ]
    assert lignes[9] == "S21.G00.55.001,'0.00'"
    assert lignes[13] == "S21.G00.55.001,'10.00'"


def _parametres():
    from app.modules.dsn_export.domain.settings import DsnSettings

    return DsnSettings(
        versements=[
            {"organisme": "79484650100011", "bic": "B", "iban": "I", "mode": "05"},
            AGGEEV,
            {"organisme": "DGFIP", "entite": "DGFIP_PAS", "bic": "B", "iban": "I", "mode": "05"},
        ],
        organismes_complementaires=CONTRATS,
    )


def _etablissement():
    return EtablissementBlock(
        individus=[_salarie({"1": "2"}, [_cotisation("1", "528.24")])]
    )


def test_en_decembre_le_versement_du_trimestre_prend_sa_place():
    from app.modules.dsn_export.application.builder import _paiements

    etab = _etablissement()
    avertissements = _paiements(
        etab, "2026-12", "79484650100011", _parametres(),
        cotisations_complementaires_avant={"2": Decimal("1056.48")},
    )
    assert [v.identifiant for v in etab.versements_organismes] == [
        "79484650100011", "AGGEEV", "DGFIP",
    ]
    aggeev = etab.versements_organismes[1]
    assert aggeev.rubriques["S21.G00.20.005"] == "1584.72"
    assert aggeev.rubriques["S21.G00.20.011"] == "25012027"
    assert [c["S21.G00.55.001"] for c in aggeev.rubriques["_composants_55"]] == [
        "0.00", "1584.72", "0.00",
    ]
    assert not [a for a in avertissements if "complémentaires" in a]


def test_hors_fin_de_trimestre_ni_versement_ni_avertissement():
    from app.modules.dsn_export.application.builder import _paiements

    etab = _etablissement()
    avertissements = _paiements(etab, "2026-11", "79484650100011", _parametres())
    assert "AGGEEV" not in [v.identifiant for v in etab.versements_organismes]
    assert not [a for a in avertissements if "complémentaires" in a]


def test_un_trimestre_aux_mois_inconnus_n_est_pas_verse_et_l_export_le_dit():
    from app.modules.dsn_export.application.builder import _paiements

    etab = _etablissement()
    avertissements = _paiements(etab, "2026-12", "79484650100011", _parametres())
    assert "AGGEEV" not in [v.identifiant for v in etab.versements_organismes]
    assert any("AGGEEV" in a and "à déclarer à la main" in a for a in avertissements)


def test_l_export_recalcule_les_deux_mois_d_avant_du_trimestre(monkeypatch):
    from types import SimpleNamespace

    from app.modules.exports.infrastructure import export_dsn

    lus = []

    def donnees(company_id, mois, employee_ids=None):
        lus.append(mois)
        return [{"mois": mois}], {}

    def construire(company, donnees_du_mois, mois, **_k):
        montant = {"2026-10": "528.24", "2026-11": "528.24"}[mois]
        etab = EtablissementBlock(individus=[_salarie({"1": "2"}, [_cotisation("1", montant)])])
        return SimpleNamespace(etablissement=etab), []

    monkeypatch.setattr(export_dsn, "get_dsn_employees_data", donnees)
    monkeypatch.setattr(export_dsn, "build_parsed_dsn_from_payroll", construire)
    monkeypatch.setattr(export_dsn, "lire_bascule", lambda _cid: None)

    avant = export_dsn.cotisations_complementaires_avant("soc", {}, "2026-12", _parametres())
    assert lus == ["2026-10", "2026-11"]
    assert avant == {"2": Decimal("1056.48")}


def test_un_trimestre_qui_touche_la_bascule_n_est_pas_recalcule(monkeypatch):
    from app.modules.exports.infrastructure import export_dsn
    from app.shared.reprise_paie import Bascule

    monkeypatch.setattr(export_dsn, "lire_bascule", lambda _cid: Bascule(annee=2026, mois=9))
    assert export_dsn.cotisations_complementaires_avant("soc", {}, "2026-09", _parametres()) is None
    assert export_dsn.cotisations_complementaires_avant("soc", {}, "2026-11", _parametres()) is None


DSN_DU_CABINET = (
    "S21.G00.20.001,'AGGEEV'\r\nS21.G00.20.003,'CEPAFRPP382'\r\nS21.G00.20.005,'2082.34'\r\n"
    "S21.G00.20.008,'DBALO1'\r\nS21.G00.20.010,'05'\r\nS21.G00.20.011,'25072026'\r\n"
    "S21.G00.55.001,'497.62'\r\nS21.G00.55.002,'NON CADRE'\r\nS21.G00.55.003,'20000802485169'\r\n"
    "S21.G00.55.004,'2026T02'\r\nS21.G00.55.001,'0.00'\r\nS21.G00.55.003,'30000802485169'\r\n"
    "S21.G00.55.004,'2026T02'\r\nS21.G00.20.001,'DGFIP'\r\nS21.G00.20.005,'244.00'\r\n"
).encode("latin-1")


def test_la_reprise_lit_le_jour_de_paiement_du_cabinet():
    from app.modules.dsn_export.domain.settings import _versements

    aggeev, dgfip = _versements(DSN_DU_CABINET)
    assert aggeev["jour_paiement"] == "25"
    assert "jour_paiement" not in dgfip


def test_la_reprise_lit_le_type_de_population_de_chaque_contrat():
    from app.modules.dsn_export.domain.settings import types_de_population

    assert types_de_population(DSN_DU_CABINET) == {"20000802485169": "NON CADRE"}
