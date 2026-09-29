"""Les replis des calculs profonds remontent au bulletin (audit 25/09, B6).

Les chargeurs de règles, les lectures de bulletins passés et le pied de page
n'ont pas le contexte de paie sous la main : ils notent leur repli dans la
collecte que le générateur ouvre pour la durée d'une génération.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.modules.payroll.engine import replis
from app.modules.payroll.engine.replis import (
    CODE_REPLI_CONVENTION,
    CODE_REPLI_AVANCES,
    CODE_REPLI_SOLDES_CONGES,
    fermer_collecte,
    fusionner_replis,
    noter_repli,
    ouvrir_collecte,
)

PAYROLL = Path(__file__).resolve().parents[3] / "app/modules/payroll"


def test_hors_generation_noter_un_repli_ne_fait_rien():
    noter_repli(CODE_REPLI_SOLDES_CONGES)  # ne lève pas, n'écrit nulle part


def test_pendant_une_generation_le_repli_est_collecte_une_fois():
    alertes: list = []
    jeton = ouvrir_collecte(alertes)
    try:
        noter_repli(CODE_REPLI_SOLDES_CONGES)
        noter_repli(CODE_REPLI_SOLDES_CONGES)
        noter_repli(CODE_REPLI_CONVENTION)
    finally:
        fermer_collecte(jeton)
    assert [a["code"] for a in alertes] == [CODE_REPLI_SOLDES_CONGES, CODE_REPLI_CONVENTION]
    assert all(a["repli"] is True for a in alertes)
    # Collecte fermée : plus rien n'arrive dans la liste.
    noter_repli(CODE_REPLI_AVANCES)
    assert len(alertes) == 2


def test_la_fusion_garde_les_alertes_du_bulletin_sans_doublon():
    existantes = [{"code": "autre", "message": "x"}, replis.alerte_de_repli(CODE_REPLI_CONVENTION)]
    fusion = fusionner_replis(
        existantes,
        [replis.alerte_de_repli(CODE_REPLI_CONVENTION), replis.alerte_de_repli(CODE_REPLI_AVANCES)],
    )
    assert [a["code"] for a in fusion] == ["autre", CODE_REPLI_CONVENTION, CODE_REPLI_AVANCES]
    assert fusionner_replis(None, []) == []


def test_chaque_code_a_son_message():
    codes = [v for k, v in vars(replis).items() if k.startswith("CODE_REPLI_")]
    assert len(codes) == 14
    for code in codes:
        message = replis.alerte_de_repli(code)["message"]
        assert "À vérifier avant de" in message


def test_une_mutuelle_illisible_arrete_le_calcul(monkeypatch):
    """Plus de repli pour la mutuelle : le bulletin n'est pas calculé sans elle."""
    from app.core import database
    from app.modules.payroll.engine import calcul_net, mutuelles

    def base_en_panne():
        raise ConnectionError("base injoignable")

    monkeypatch.setattr(database, "get_supabase_admin_client", base_en_panne)
    monkeypatch.setattr(mutuelles.time, "sleep", lambda _s: None)
    contexte = SimpleNamespace(
        contrat={
            "specificites_paie": {
                "mutuelle": {"adhesion": True, "mutuelle_type_ids": ["m1"]}
            }
        },
        alertes_baremes=[],
    )
    with pytest.raises(mutuelles.MutuelleIllisible):
        calcul_net._get_part_patronale_mutuelle(contexte)
    assert contexte.alertes_baremes == []


def test_des_conventions_illisibles_sont_notees():
    class BaseEnPanne:
        def table(self, _nom):
            raise ConnectionError("base injoignable")

    from app.modules.payroll.engine.baremes_loader import charger_conventions_collectives

    alertes: list = []
    jeton = ouvrir_collecte(alertes)
    try:
        assert charger_conventions_collectives(BaseEnPanne()) == {}
    finally:
        fermer_collecte(jeton)
    assert [a["code"] for a in alertes] == [CODE_REPLI_CONVENTION]


def test_des_soldes_de_conges_illisibles_sont_notes(monkeypatch):
    from app.modules.absences.application import queries
    from app.modules.payroll.engine.bulletin import build_solde_conges_pied_de_page

    def en_panne(*_a, **_k):
        raise ConnectionError("base injoignable")

    monkeypatch.setattr(queries, "get_absence_balances_for_payslip", en_panne)
    alertes: list = []
    jeton = ouvrir_collecte(alertes)
    try:
        assert build_solde_conges_pied_de_page("e1", 2026, 8) is None
    finally:
        fermer_collecte(jeton)
    assert [a["code"] for a in alertes] == [CODE_REPLI_SOLDES_CONGES]


# Les autres replis sont au cœur des générateurs et des runs, que les tests
# unitaires n'exécutent pas en entier : une garde lit leur code source.
SITES = [
    ("engine/baremes_loader.py", "CODE_REPLI_CONVENTION", 2),
    ("engine/reference_remuneration.py", "CODE_REPLI_REFERENCE_CONGES", 2),
    ("engine/bulletin.py", "CODE_REPLI_SOLDES_CONGES", 1),
    ("documents/payslip_generator.py", "CODE_REPLI_SORTIE", 1),
    ("documents/payslip_generator.py", "CODE_REPLI_VARIABLES_AUTO", 1),
    ("documents/payslip_generator.py", "CODE_REPLI_MODULATION", 1),
    ("documents/payslip_generator.py", "CODE_REPLI_PRIMES_POSTES", 1),
    ("documents/payslip_generator.py", "CODE_REPLI_EVOLUTION_SALAIRE", 1),
    ("documents/payslip_generator_forfait.py", "CODE_REPLI_EVOLUTION_SALAIRE", 1),
    ("documents/payslip_run_heures.py", "CODE_REPLI_CONGES_FIN_CONTRAT", 2),
    ("documents/payslip_run_common.py", "CODE_REPLI_REGLAGES_CONGES", 1),
    ("documents/payslip_run_common.py", "CODE_REPLI_PRORATA_ANCIENNETE", 1),
    ("documents/payslip_run_forfait.py", "CODE_REPLI_FORFAIT_ANCIENNETE", 1),
]


@pytest.mark.parametrize("fichier,code,nombre", SITES)
def test_chaque_repli_est_signale(fichier, code, nombre):
    source = (PAYROLL / fichier).read_text(encoding="utf-8")
    appels = source.count(f"noter_repli({code})") + source.count(
        f"signaler_repli(contexte, {code})"
    )
    assert appels == nombre


@pytest.mark.parametrize(
    "fichier", ["documents/payslip_generator.py", "documents/payslip_generator_forfait.py"]
)
def test_les_generateurs_ouvrent_et_ferment_la_collecte(fichier):
    source = (PAYROLL / fichier).read_text(encoding="utf-8")
    ouverture = source.index("jeton_replis = ouvrir_collecte(alertes_de_repli_generateur)")
    assert ouverture < source.index("    try:\n", ouverture)
    assert "fermer_collecte(jeton_replis)" in source[source.rindex("    finally:"):]
    assert "fusionner_replis(" in source
