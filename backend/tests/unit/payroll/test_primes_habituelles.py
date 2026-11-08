"""Les primes que l'ancien logiciel versait chaque mois et que Martine ne calcule pas."""

from __future__ import annotations

from app.modules.payroll.domain.primes_habituelles import (
    deja_saisie,
    message_prime,
    primes_habituelles,
)


def _bulletin(*lignes):
    return {"calcul_du_brut": [{"libelle": l, "gain": g} for l, g in lignes]}


class TestHabituelles:
    def test_versee_les_deux_mois(self):
        primes = primes_habituelles(
            _bulletin(("Prime de présence", 25)), _bulletin(("Prime de présence", 50))
        )
        assert [(p.libelle, p.montant) for p in primes] == [("Prime de présence", 25.0)]

    def test_versee_un_seul_mois_ignoree(self):
        assert primes_habituelles(_bulletin(("Prime cooptation", 500)), _bulletin()) == []

    def test_anciennete_calculee_par_martine(self):
        assert (
            primes_habituelles(
                _bulletin(("PRIME ANCIENNETE", 100)), _bulletin(("Prime ancienneté", 100))
            )
            == []
        )

    def test_salaire_de_base_ignore(self):
        assert (
            primes_habituelles(_bulletin(("SALAIRE DE BASE", 1)), _bulletin(("SALAIRE DE BASE", 1)))
            == []
        )

    def test_astreinte_comptee(self):
        primes = primes_habituelles(
            _bulletin(("PRIME ASTREINTE", 200)), _bulletin(("Prime astreinte", 250))
        )
        assert [p.libelle for p in primes] == ["PRIME ASTREINTE"]

    def test_gain_nul_ignore(self):
        assert primes_habituelles(_bulletin(("Prime X", 0)), _bulletin(("Prime X", 10))) == []

    def test_bulletin_vide(self):
        assert primes_habituelles(None, {}) == []


class TestDejaSaisie:
    def test_meme_nom(self):
        assert deja_saisie("Prime de présence", ["Prime de presence"])

    def test_nom_proche(self):
        assert deja_saisie("Prime Assiduité Atelier", ["Assiduité"])

    def test_autre_prime(self):
        assert not deja_saisie("Prime de présence", ["Prime de poste"])

    def test_rien_de_saisi(self):
        assert not deja_saisie("Prime de présence", [])


def test_message_dit_quoi_faire():
    from app.modules.payroll.domain.primes_habituelles import PrimeHabituelle

    message = message_prime(PrimeHabituelle("Prime de présence", 25.0), "septembre 2026")
    assert "Prime de présence" in message
    assert "25,00 €" in message
    assert "Saisissez-la" in message
