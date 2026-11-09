"""Tests unitaires — socle commun solde de tout compte."""

from __future__ import annotations

from app.modules.payroll.solde_de_tout_compte.common import socle_commun


class _FakeQuery:
    def __init__(self, data):
        self._data = data

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, colonne, valeur):
        if isinstance(self._data, dict) and colonne in self._data and self._data[colonne] != valeur:
            self._data = None
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        return type("R", (), {"data": self._data})()


class _FakeClient:
    def __init__(self, payslip_row):
        self._row = payslip_row

    def table(self, _name):
        return _FakeQuery(self._row)


def test_compute_remunerations_section_uses_neant_without_payslip() -> None:
    section, total_brut, _, _ = socle_commun.compute_remunerations_section(
        {"salaire_de_base": {"valeur": 0}},
        {"last_working_day": "2025-06-15"},
        employee_id="emp-1",
        supabase_client=_FakeClient(None),
    )
    assert total_brut == 0.0
    assert section["type"] == "amounts"
    assert section["rows"]
    # Sans bulletin, le salaire prorata est à 0 → détail « Néant ».
    assert section["rows"][0]["detail"] == "Néant"


def test_compute_remunerations_section_reads_last_payslip() -> None:
    payslip = {
        "year": 2025,
        "month": 6,
        "payslip_data": {
            "remuneration_brute_heures_supp": 320.0,
            "total_heures_supp": 8.0,
            "calcul_du_brut": [
                {"libelle": "Salaire de base", "gain": 2500.0},
                {"libelle": "Prime d'assiduité", "gain": 150.0},
                {"libelle": "Sous-total primes", "gain": 150.0, "is_sous_total": True},
            ],
        },
    }
    section, total_brut, _, _ = socle_commun.compute_remunerations_section(
        {"salaire_de_base": {"valeur": 2500}, "id": "emp-1"},
        {"last_working_day": "2025-06-30"},
        employee_id="emp-1",
        supabase_client=_FakeClient(payslip),
    )
    assert total_brut > 2500
    assert section["rows"]
    primes = [r for r in section["rows"] if r["label"].startswith("Primes")]
    assert primes and primes[0]["montant"] == 150.0


def test_un_bulletin_d_un_mois_precedent_n_entre_pas_dans_le_recu() -> None:
    """R-389 : sans bulletin du mois de sortie, le reçu estime ; les heures et les
    primes déjà payées le mois d'avant ne sont pas des sommes versées à la rupture
    (L1234-20)."""
    payslip = {
        "year": 2026,
        "month": 8,
        "payslip_data": {
            "remuneration_brute_heures_supp": 320.0,
            "total_heures_supp": 8.0,
            "calcul_du_brut": [{"libelle": "Prime d'assiduité", "gain": 150.0}],
        },
    }
    section, total_brut, _, _ = socle_commun.compute_remunerations_section(
        {"salaire_de_base": {"valeur": 2500}, "id": "emp-1"},
        {"last_working_day": "2026-09-06"},
        employee_id="emp-1",
        supabase_client=_FakeClient(payslip),
    )
    assert total_brut < 2500
    lignes = {r["label"][:6]: r for r in section["rows"]}
    assert lignes["Heures"]["montant"] == 0.0 and lignes["Heures"]["detail"] == "Néant"
    assert lignes["Primes"]["montant"] == 0.0 and lignes["Primes"]["detail"] == "Néant"

