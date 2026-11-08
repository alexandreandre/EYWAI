"""Un avantage en nature corrigé à la main : le net retire ce que la ligne porte.

La valeur entre au brut, puis le net à payer la retire : elle n'est pas versée
en argent. Si le net relit le contrat au lieu de la ligne corrigée, la
différence part en argent.
"""

from types import SimpleNamespace

from app.modules.payroll.engine.calcul_brut import montant_avantages_en_nature
from app.modules.payroll.engine.corrections_manuelles import (
    CorrectionDeLigne,
    JournalDesCorrections,
)

CODE_AVANTAGE = "brut:avantages_en_nature"


def _contexte(journal=None):
    return SimpleNamespace(
        entreprise={"parametres_paie": {"avantages_en_nature": {}}},
        contrat={
            "remuneration": {"avantages_en_nature": {"pret_employeur": {"montant_mensuel": 100}}}
        },
        salaire_base_mensuel=2000.0,
        corrections_du_mois=journal,
    )


def _journal(**valeurs):
    return JournalDesCorrections(
        [
            CorrectionDeLigne(
                ligne=CODE_AVANTAGE,
                libelle="Avantages en nature",
                motif="Valeur réelle",
                saisie_id="s-1",
                **valeurs,
            )
        ]
    )


def test_sans_correction_le_net_retire_la_valeur_du_contrat():
    assert montant_avantages_en_nature(_contexte()) == 100.0


def test_ligne_corrigee_le_net_retire_le_montant_corrige():
    assert montant_avantages_en_nature(_contexte(_journal(montant=150.0))) == 150.0


def test_ligne_corrigee_a_zero_le_net_ne_retire_plus_rien():
    assert montant_avantages_en_nature(_contexte(_journal(montant=0.0))) == 0.0


def test_lire_le_montant_ne_consomme_pas_la_correction():
    contexte = _contexte(_journal(montant=150.0))
    montant_avantages_en_nature(contexte)
    assert montant_avantages_en_nature(contexte) == 150.0
