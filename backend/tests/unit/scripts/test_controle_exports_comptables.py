"""Contrôle des exports comptables : relire les fichiers produits, au centime."""

import pytest

from app.modules.exports.infrastructure.export_formats_cabinet import (
    _format_quadra_line,
)
from scripts.controle_exports_comptables import (
    _identite_brute,
    ecart_de_soldes,
    lignes_du_plan,
    relire_fec,
    relire_quadra,
    relire_sage,
)

pytestmark = pytest.mark.unit

ECRITURE = {
    "date_ecriture": "2026-09-30",
    "journal": "PAI",
    "compte_comptable": "641000",
    "libelle": "Salaires Septembre 2026",
    "debit": 15944.12,
    "credit": 0.0,
    "periode_paie": "2026-09",
}


def test_relire_quadra_redonne_les_montants():
    lignes = [
        _format_quadra_line(ECRITURE),
        _format_quadra_line({**ECRITURE, "compte_comptable": "42100000", "debit": 0.0, "credit": 15944.12}),
    ]
    contenu = ("\r\n".join(lignes) + "\r\n").encode("latin-1")
    assert relire_quadra(contenu) == {"64100000": (15944.12, 0.0), "42100000": (0.0, 15944.12)}


def test_relire_quadra_refuse_un_enregistrement_mal_forme():
    with pytest.raises(ValueError):
        relire_quadra(b"M641000  OD\r\n")


def test_relire_fec_a_la_virgule():
    contenu = (
        b"JournalCode\tCompteNum\tDebit\tCredit\n"
        b"PAI\t641000\t100,50\t0,00\n"
        b"PAI\t421000\t0,00\t100,50\n"
    )
    assert relire_fec(contenu) == {"641000": (100.5, 0.0), "421000": (0.0, 100.5)}


def test_relire_sage():
    contenu = (
        "Date|Journal|Compte|Libelle|Debit|Credit|Analytique|Reference\r\n"
        "20260930|OD|641000|Salaires|100.50|0.00||OD_PAIE_2026-09\r\n"
    ).encode("utf-8-sig")
    assert relire_sage(contenu) == {"641000": (100.5, 0.0)}


def test_ecart_de_soldes_au_centime():
    assert ecart_de_soldes({"641000": (100.5, 0.0)}, {"641000": (100.5, 0.0)}) == 0.0
    assert ecart_de_soldes({"641000": (100.5, 0.0)}, {"641000": (100.49, 0.0)}) == 0.01
    assert ecart_de_soldes({}, {"421000": (0.0, 3.0)}) == 3.0


def test_plan_applique_comme_plan_de_la_societe():
    plan = {
        "journal": "PAI",
        "organismes": {"URSSAF": {"compte_charge": "64510000", "compte_tiers": "43100000"}},
        "elements": {"net_a_payer": {"compte_charge": "", "compte_tiers": "42100000"}},
    }
    lignes = lignes_du_plan("societe", plan)
    assert lignes["organisme_urssaf"]["compte_tiers"] == "43100000"
    assert lignes["organisme_urssaf"]["company_id"] == "societe"
    assert lignes["net_a_payer"]["compte_comptable"] == "42100000"
    assert lignes["net_a_payer"]["journal"] == "PAI"


def test_identite_brute_d_un_bulletin_complet():
    bulletin = {
        "salaire_brut": 3000.0,
        "net_a_payer": 2050.0,
        "structure_cotisations": {"total_salarial": 600.0},
        "synthese_net": {"acompte_verse": 300.0, "impot_prelevement_a_la_source": {"montant": 100.0}},
        "primes_non_soumises": [{"montant": 50.0}],
    }
    assert _identite_brute(bulletin) == 0.0
    assert _identite_brute({**bulletin, "net_a_payer": 2050.01}) == -0.01
