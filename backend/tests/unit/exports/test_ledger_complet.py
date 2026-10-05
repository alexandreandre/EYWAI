"""Registre paie : chaque montant de chaque bulletin, une fois, au bon compte.

Bulletins inventés couvrant tout ce qu'un bulletin peut porter : brut,
cotisations par organisme avec réduction générale et forfait social, PAS,
acompte, avance, prêt (capital et intérêts), saisie, PPV, note de frais,
transport, IJSS subrogées, indemnité de licenciement.
"""

from collections import defaultdict
from unittest.mock import patch

import pytest

from app.modules.exports.infrastructure import payroll_ledger as ledger_module
from app.modules.exports.infrastructure.export_ecritures_comptables import (
    ligne_od_du_bulletin,
)

pytestmark = pytest.mark.unit

# Défauts plateforme, tels qu'en base (accounting_mappings, company_id NULL).
MAPPINGS_PLATEFORME = {
    "salaire_brut": {"compte_comptable": "641000", "compte_charge": "641000", "journal": "OD"},
    "net_a_payer": {"compte_comptable": "421000", "compte_tiers": "421000", "journal": "OD"},
    "pas": {"compte_comptable": "442000", "compte_tiers": "442000", "journal": "OD"},
    "acompte_salaire": {"compte_comptable": "425100", "compte_tiers": "425100"},
    "avance_salaire": {"compte_comptable": "425200", "compte_tiers": "425200"},
    "saisie_opposition": {"compte_comptable": "427000", "compte_tiers": "427000"},
    "pret_employeur": {"compte_comptable": "274000", "compte_tiers": "274000"},
    "note_de_frais": {"compte_comptable": "428625", "compte_tiers": "428625"},
    "indemnite_transport": {"compte_comptable": "648000", "compte_charge": "648000"},
}


def _bulletin_complet():
    """Salarié A : tout ce qu'un mois ordinaire peut retenir ou ajouter."""
    return {
        "salaire_brut": 3000.0,
        "net_a_payer": 1926.31,
        "structure_cotisations": {
            "total_salarial": 360.0,
            "total_patronal": 280.8,
            "bloc_principales": [
                {"coti_id": "securite_sociale_maladie", "libelle": "Maladie", "montant_salarial": 0.0, "montant_patronal": 210.0},
                {"coti_id": "retraite_comp_t1", "libelle": "Retraite T1", "montant_salarial": 120.0, "montant_patronal": 180.0},
                {"coti_id": "csg_deductible", "libelle": "CSG déductible", "montant_salarial": 200.0, "montant_patronal": 0.0},
                {"coti_id": "mutuelle", "libelle": "Mutuelle", "montant_salarial": 30.0, "montant_patronal": 30.0},
                {"coti_id": "prevoyance_non_cadre", "libelle": "Prévoyance", "montant_salarial": 10.0, "montant_patronal": 10.0},
            ],
            "bloc_allegements": [
                {"coti_id": "reduction_generale", "libelle": "Réduction générale", "montant_salarial": 0.0, "montant_patronal": -150.0},
            ],
            "bloc_autres_contributions": {
                "lignes": [
                    {"coti_id": "forfait_social", "libelle": "Forfait social 8 %", "montant_salarial": 0.0, "montant_patronal": 0.8},
                ]
            },
        },
        "synthese_net": {
            "acompte_verse": 800.0,
            "impot_prelevement_a_la_source": {"montant": 50.0},
        },
        "primes_non_soumises": [
            {"libelle": "Prime de partage de la valeur (PPV)", "prime_id": "prime_partage_valeur", "montant": 400.0},
            {"libelle": "Indemnité de transport", "montant": 60.0},
            {"prime_id": "remb_restaurant_2026-09-12", "libelle": "remb restaurant 2026-09-12", "montant": 85.3},
        ],
        "retenues_saisies": {
            "total_preleve": 46.49,
            "saisies": [{"type": "saisie_arret", "montant": 46.49, "creditor_name": "Trésor"}],
        },
        "remboursements_prets": {
            "total_rembourse": 212.5,
            "total_capital": 200.0,
            "total_interets": 12.5,
            "avantage_nature_interets": 0.0,
        },
        "remboursements_avances": {
            "total_rembourse": 150.0,
            "avances": [{"montant": 150.0, "type": "avance_salaire", "type_label": "Avance sur salaire", "compte": "4252"}],
        },
    }


def _bulletin_de_sortie():
    """Salarié B : sortie avec indemnité de licenciement, IJSS subrogées."""
    return {
        "salaire_brut": 1200.0,
        "net_a_payer": 3105.23,
        "structure_cotisations": {
            "total_salarial": 115.1,
            "total_patronal": 84.0,
            "bloc_principales": [
                {"coti_id": "securite_sociale_maladie", "libelle": "Maladie", "montant_salarial": 0.0, "montant_patronal": 84.0},
                {"coti_id": "csg_deductible", "libelle": "CSG déductible", "montant_salarial": 81.6, "montant_patronal": 0.0},
                {"libelle": "CSG déductible IJSS", "montant_salarial": 19.0, "montant_patronal": 0.0},
                {"libelle": "CSG/CRDS IJSS non déductible", "montant_salarial": 14.5, "montant_patronal": 0.0},
            ],
        },
        "synthese_net": {"impot_prelevement_a_la_source": {"montant": 0.0}},
        "revenus_hors_brut_imposables": [
            {"prime_id": "ijss_subrogees", "libelle": "IJSS subrogées", "montant": 500.0}
        ],
        "indemnites_sortie": {
            "lignes_exonerees": [{"libelle": "Indemnité légale de licenciement", "montant": 1520.33}],
            "total_exonerees": 1520.33,
        },
    }


SAISIES_DU_MOIS_A = [{"name": "Acompte", "amount": -800.0}]


def _ligne(nom, payslip_data, saisies=()):
    return ligne_od_du_bulletin(
        payslip_id=f"bulletin-{nom}",
        employee={"id": f"salarie-{nom}", "first_name": "Salarié", "last_name": nom},
        payslip_data=payslip_data,
        saisies_du_salarie=list(saisies),
        compte_de_saisie=lambda type_saisie: "4271",
    )


def _construire(lignes, mappings=None, **kwargs):
    totals = {
        "total_brut": sum(ligne["brut"] for ligne in lignes),
        "total_net_a_payer": sum(ligne["net_a_payer"] for ligne in lignes),
        "total_cotisations_salariales": sum(ligne["cotisations_salariales"] for ligne in lignes),
        "total_cotisations_patronales": sum(ligne["cotisations_patronales"] for ligne in lignes),
        "total_pas": sum(ligne["pas"] for ligne in lignes),
        "employees_count": len(lignes),
    }
    with patch.object(
        ledger_module, "get_payslip_data_for_od", return_value=(lignes, totals)
    ), patch.object(
        ledger_module, "get_accounting_mappings", return_value=mappings or MAPPINGS_PLATEFORME
    ):
        return ledger_module.build_payroll_ledger("societe", "2026-09", **kwargs)


def _par_compte(ecritures):
    comptes = defaultdict(lambda: [0.0, 0.0])
    for e in ecritures:
        comptes[e["compte_comptable"]][0] += e["debit"]
        comptes[e["compte_comptable"]][1] += e["credit"]
    return {c: (round(d, 2), round(cr, 2)) for c, (d, cr) in comptes.items()}


class TestOdComplete:
    def test_chaque_montant_au_bon_compte_et_equilibre(self):
        lignes = [
            _ligne("A", _bulletin_complet(), SAISIES_DU_MOIS_A),
            _ligne("B", _bulletin_de_sortie()),
        ]
        ecritures, od_totals, _ = _construire(lignes)

        assert od_totals["anomalies"] == []
        assert od_totals["equilibre"] is True
        assert od_totals["total_debit"] == 7130.43
        assert _par_compte(ecritures) == {
            "641000": (4200.0, 0.0),  # brut
            "421000": (0.0, 5031.54),  # net à payer
            "442000": (0.0, 50.0),  # PAS
            "645100": (144.8, 0.0),  # URSSAF : 210 + 84 − 150 de réduction générale + 0,80 de forfait social
            "431000": (0.0, 426.4),  # URSSAF : part salariale 281,60 + patronale nette 144,80
            "645300": (180.0, 0.0),
            "437200": (0.0, 300.0),
            "645242": (30.0, 0.0),
            "437020": (0.0, 60.0),
            "645241": (10.0, 0.0),
            "437400": (0.0, 20.0),
            "438700": (500.0, 33.5),  # IJSS à recevoir, nettes de leur CSG
            "641300": (400.0, 0.0),  # PPV
            "648000": (60.0, 0.0),  # transport
            "428625": (85.3, 0.0),  # note de frais remboursée sur le bulletin
            "425100": (0.0, 800.0),  # acompte
            "4271": (0.0, 46.49),  # saisie, au compte de son type
            "274000": (0.0, 200.0),  # prêt : capital
            "762400": (0.0, 12.5),  # prêt : intérêts
            "4252": (0.0, 150.0),  # avance, au compte où elle a été versée
            "641400": (1520.33, 0.0),  # indemnité de licenciement exonérée
        }

    def test_les_tables_des_modules_et_les_notes_de_frais_ne_sont_plus_relues(self):
        """Le bulletin fait foi : relire les tables comptait deux fois (ou pas
        du tout) ce que le bulletin retient, et ignorait le filtre de salariés."""
        lignes = [_ligne("A", _bulletin_complet(), SAISIES_DU_MOIS_A)]
        interdit = AssertionError("lecture interdite")
        with patch(
            "app.modules.exports.infrastructure.export_acomptes.get_acomptes_data",
            side_effect=interdit,
        ), patch(
            "app.modules.exports.infrastructure.export_saisies.get_saisies_data",
            side_effect=interdit,
        ), patch.object(
            ledger_module, "list_loan_repayments_by_period", side_effect=interdit
        ), patch(
            "app.modules.exports.infrastructure.export_notes_frais.get_notes_frais_ecritures",
            side_effect=interdit,
        ):
            ecritures, od_totals, _ = _construire(lignes)
        assert od_totals["equilibre"] is True
        net = _par_compte(ecritures)["421000"]
        assert net == (0.0, 1926.31)

    def test_chaque_ligne_porte_l_intitule_de_son_compte(self):
        """Le FEC en a besoin (CompteLib) : le libellé sans la période."""
        ecritures, _, _ = _construire([_ligne("B", _bulletin_de_sortie())])
        intitules = {e["compte_comptable"]: e["compte_lib"] for e in ecritures}
        assert intitules["421000"] == "Net à payer"
        assert intitules["431000"] == "Dette URSSAF"
        assert intitules["641400"] == "Indemnités de rupture"

    def test_un_seul_journal_celui_de_la_societe(self):
        mappings = dict(MAPPINGS_PLATEFORME)
        mappings["salaire_brut"] = {**mappings["salaire_brut"], "journal": "PAI"}
        ecritures, _, _ = _construire([_ligne("B", _bulletin_de_sortie())], mappings)
        assert {e["journal"] for e in ecritures} == {"PAI"}

    def test_le_plan_de_la_societe_prime_sur_le_compte_du_module(self):
        mappings = dict(MAPPINGS_PLATEFORME)
        mappings["saisie_opposition"] = {
            "company_id": "societe",
            "compte_comptable": "42700000",
            "compte_tiers": "42700000",
        }
        ecritures, od_totals, _ = _construire(
            [_ligne("A", _bulletin_complet(), SAISIES_DU_MOIS_A)], mappings
        )
        comptes = _par_compte(ecritures)
        assert comptes["42700000"] == (0.0, 46.49)
        assert "4271" not in comptes
        assert od_totals["equilibre"] is True


class TestControleDuRegistre:
    def test_chaque_nature_de_chaque_bulletin_une_fois_au_centime(self):
        from app.modules.exports.domain.accounting_plan import (
            resolve_organisme_from_coti_id,
        )
        from app.modules.exports.domain.controle_comptable import controler

        lignes = [
            _ligne("A", _bulletin_complet(), SAISIES_DU_MOIS_A),
            _ligne("B", _bulletin_de_sortie()),
        ]
        ecritures, _, _ = _construire(lignes)
        rapport = controler(
            lignes,
            ecritures,
            lambda c: resolve_organisme_from_coti_id(c.get("coti_id"), str(c.get("libelle") or "")),
        )
        assert rapport["equilibre"] is True
        assert rapport["bulletins_incoherents"] == []
        assert rapport["natures_en_ecart"] == []
        assert {n["nature"] for n in rapport["natures"]} >= {
            "brut",
            "net_a_payer",
            "pas",
            "charges:URSSAF",
            "dettes:IJSS",
            "hors_brut:prime_partage_valeur",
            "hors_brut:note_de_frais",
            "hors_brut:acompte_verse",
            "hors_brut:avance_salaire",
            "hors_brut:saisie_opposition",
            "hors_brut:pret_employeur",
            "hors_brut:interets_pret_employeur",
            "hors_brut:ijss",
            "hors_brut:indemnite_rupture",
        }


class TestBulletinIncoherent:
    def test_ecart_nomme_le_salarie_et_bloque_l_export(self):
        """Un net qui ne se retrouve pas à partir du bulletin : l'OD ne peut pas
        s'équilibrer, le message doit dire quel bulletin regarder."""
        bulletin = _bulletin_de_sortie()
        bulletin["net_a_payer"] = 3105.24
        _, od_totals, _ = _construire([_ligne("B", bulletin)])

        assert od_totals["equilibre"] is False
        incoherents = [a for a in od_totals["anomalies"] if a["code"] == "bulletin_incoherent"]
        assert len(incoherents) == 1
        assert "Salarié B" in incoherents[0]["detail"]
        assert incoherents[0]["montant"] == 0.01

        with pytest.raises(ledger_module.LedgerImbalanceError) as exc:
            ledger_module.assert_ledger_balanced(od_totals)
        assert "Salarié B" in str(exc.value)


class TestOdPartielles:
    @pytest.mark.parametrize("scope", ["salaires", "charges_sociales", "pas"])
    def test_chaque_od_partielle_est_equilibree(self, scope):
        lignes = [
            _ligne("A", _bulletin_complet(), SAISIES_DU_MOIS_A),
            _ligne("B", _bulletin_de_sortie()),
        ]
        ecritures, _, _ = _construire(lignes, scope=scope)
        assert ecritures
        assert round(sum(e["debit"] for e in ecritures), 2) == round(
            sum(e["credit"] for e in ecritures), 2
        )

    def test_les_trois_od_partielles_font_l_od_globale(self):
        lignes = [
            _ligne("A", _bulletin_complet(), SAISIES_DU_MOIS_A),
            _ligne("B", _bulletin_de_sortie()),
        ]
        globale, _, _ = _construire(lignes)
        soldes = defaultdict(float)
        for scope in ("salaires", "charges_sociales", "pas"):
            partielle, _, _ = _construire(lignes, scope=scope)
            for e in partielle:
                soldes[e["compte_comptable"]] += e["debit"] - e["credit"]
        attendu = {c: round(d - cr, 2) for c, (d, cr) in _par_compte(globale).items()}
        assert {c: round(v, 2) for c, v in soldes.items() if round(v, 2)} == {
            c: v for c, v in attendu.items() if v
        }


class TestRetenuesReprises:
    def test_report_d_un_net_negatif_au_compte_du_net(self):
        bulletin = {
            "salaire_brut": 2000.0,
            "net_a_payer": 330.25,
            "structure_cotisations": {
                "total_salarial": 450.0,
                "total_patronal": 0.0,
                "bloc_principales": [
                    {"coti_id": "vieillesse_plafonnee", "libelle": "Sécu.Soc Plafonnée", "montant_salarial": 450.0, "montant_patronal": 0.0},
                ],
            },
            "synthese_net": {"acompte_verse": 800.0},
            "retenues_sur_net": [
                {"libelle": "Acompte 08/2026", "montant": 800.0},
                {"libelle": "Report NAP négatif", "montant": 419.75},
            ],
        }
        ecritures, od_totals, _ = _construire([_ligne("C", bulletin)])
        assert od_totals["equilibre"] is True
        comptes = _par_compte(ecritures)
        assert comptes["425100"] == (0.0, 800.0)
        assert comptes["421000"] == (0.0, 750.0)  # net 330,25 + report 419,75
