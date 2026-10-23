"""L'historique dit ce que chaque version contient, et ce qu'une restauration remplace ou retire.

Jeu du 23/10 : « Version 7 — 1 prime retirée » rétablissait l'état AVEC la
prime (l'intitulé disait le changement qui avait remplacé la version, pas son
contenu), et la restauration de la version 1 avait effacé deux corrections de
ligne sans un mot. L'intitulé dit désormais ce qui revient ; la fenêtre dit ce
qui revient, ce qui est remplacé et ce qui est retiré, d'après le même calcul
que la restauration (`corrections_pour_revenir`).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.payroll.engine.codes_des_lignes import BLOC_BRUT
from app.modules.payroll.engine.corrections_manuelles import (
    CorrectionDeLigne,
    JournalDesCorrections,
    RegularisationCotisation,
)
from app.modules.payslips.domain.corrections import (
    apercu_de_restauration,
    contenu_de_version,
)

pytestmark = pytest.mark.unit


def _salaire(saisie_id: str | None = None, motif: str = "Avenant", taux: float = 15.0) -> dict:
    ligne = {"libelle": "Salaire de base", "quantite": 151.67, "taux": 14.1347, "gain": 2143.81, "perte": None}
    if saisie_id:
        correction = CorrectionDeLigne(
            ligne="brut:salaire_base", libelle="Salaire de base", motif=motif, taux=taux, saisie_id=saisie_id
        )
        JournalDesCorrections([correction]).corriger(ligne, BLOC_BRUT, "brut:salaire_base")
    return ligne


def _bulletin(*, salaire=None, primes=(), declarees=None, regs=(), en_attente=()):
    data: dict = {"calcul_du_brut": [salaire or _salaire()]}
    for sid, libelle, montant in primes:
        data["calcul_du_brut"].append({"libelle": libelle, "gain": montant, "saisie_id": sid})
    if declarees is not None:
        data["heures_sup_declarees"] = {"hs25": declarees[0], "hs50": declarees[1], "planning": 0.0}
    if regs:
        data["cotisations_officielles"] = [{"code": "sante", "lignes": [r.ligne_de_cotisation() for r in regs]}]
    if en_attente:
        data["corrections_en_attente"] = list(en_attente)
    return data


MUTUELLE = RegularisationCotisation(
    coti_id="mutuelle", libelle="Mutuelle", motif="Tarif erroné", montant_salarial=2.38, saisie_id="r1"
)
ORPHELINE = {
    "type": "correction",
    "ligne": "brut:hs25",
    "libelle": "Heures suppl. majorées à 25%",
    "motif": "Heures confirmées",
    "base": 8.0,
    "saisie_id": "c9",
    "raison": "La ligne visée n'est plus sur le bulletin.",
}


class TestContenuDeVersion:
    def test_dit_ses_heures_ses_primes_et_ses_lignes_corrigees(self):
        version = _bulletin(salaire=_salaire("c1"), primes=[("p1", "Prime de jeu", 300.0)], declarees=(5.0, 0.0))
        texte = " · ".join(contenu_de_version(version))
        assert "5 h à 25 % et 0 h à 50 %" in texte
        assert "Prime de jeu 300,00 €" in texte
        assert "Salaire de base" in texte

    def test_une_version_sans_correction_le_dit(self):
        texte = " · ".join(contenu_de_version(_bulletin()))
        assert "aucune prime" in texte.lower()
        assert "aucune ligne corrigée" in texte.lower()

    def test_nomme_ses_regularisations(self):
        assert any("Mutuelle" in partie for partie in contenu_de_version(_bulletin(regs=(MUTUELLE,))))


class TestApercuDeRestauration:
    def test_ce_qui_revient_cite_la_prime_la_correction_et_la_regularisation(self):
        courant = _bulletin()
        version = _bulletin(salaire=_salaire("c1"), primes=[("p1", "Prime de jeu", 300.0)], regs=(MUTUELLE,))
        apercu = apercu_de_restauration(courant, version)
        reviennent = " | ".join(apercu["reviennent"])
        assert "Prime de jeu" in reviennent and "300,00 €" in reviennent
        assert "Salaire de base" in reviennent and "Avenant" in reviennent
        assert "Mutuelle" in reviennent and "Tarif erroné" in reviennent
        assert apercu["retirees"] == [] and apercu["remplacees"] == []

    def test_les_corrections_du_moment_absentes_de_la_version_sont_dites_retirees(self):
        courant = _bulletin(salaire=_salaire("c1"), regs=(MUTUELLE,), primes=[("p1", "Prime de jeu", 300.0)])
        apercu = apercu_de_restauration(courant, _bulletin())
        retirees = " | ".join(apercu["retirees"])
        assert "Salaire de base" in retirees and "Avenant" in retirees
        assert "Mutuelle" in retirees
        assert "Prime de jeu" in retirees
        assert apercu["reviennent"] == []

    def test_une_correction_de_la_meme_ligne_est_dite_remplacee(self):
        courant = _bulletin(salaire=_salaire("c2", motif="Taux du jour", taux=16.0))
        version = _bulletin(salaire=_salaire("c1", motif="Avenant", taux=15.0))
        apercu = apercu_de_restauration(courant, version)
        assert len(apercu["remplacees"]) == 1
        assert "Taux du jour" in apercu["remplacees"][0] and "Avenant" in apercu["remplacees"][0]
        assert apercu["retirees"] == []

    def test_une_correction_en_attente_du_moment_est_dite_retiree(self):
        apercu = apercu_de_restauration(_bulletin(en_attente=[ORPHELINE]), _bulletin())
        assert any("Heures confirmées" in r for r in apercu["retirees"])

    def test_les_heures_qui_reviennent_disent_celles_qu_elles_remplacent(self):
        apercu = apercu_de_restauration(_bulletin(declarees=(5.0, 0.0)), _bulletin(declarees=(0.0, 0.0)))
        assert apercu["reviennent"] == ["Heures sup 0 h à 25 % et 0 h à 50 % (au lieu de 5 h et 0 h)"]

    def test_une_prime_corrigee_depuis_dit_son_montant_d_avant(self):
        apercu = apercu_de_restauration(
            _bulletin(primes=[("p1", "Prime de jeu", 250.0)]), _bulletin(primes=[("p1", "Prime de jeu", 300.0)])
        )
        assert apercu["reviennent"] == ["Prime « Prime de jeu » : 300,00 € (au lieu de 250,00 €)"]

    def test_une_version_identique_ne_change_rien(self):
        meme = _bulletin(salaire=_salaire("c1"), declarees=(5.0, 0.0))
        assert apercu_de_restauration(meme, meme) == {"reviennent": [], "remplacees": [], "retirees": []}


class TestHistoriqueServi:
    def test_chaque_version_porte_son_contenu_et_l_apercu_de_sa_restauration(self):
        from app.modules.payslips.infrastructure import queries

        courant = _bulletin(salaire=_salaire("c1"))
        historique = [
            {"version": 1, "changes_summary": "Ligne « Salaire de base » corrigée : Avenant",
             "previous_payslip_data": _bulletin()},
        ]
        lu = MagicMock()
        lu.data = {"edit_history": historique, "payslip_data": courant}
        table = MagicMock()
        table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = lu
        with patch.object(queries, "supabase") as base:
            base.table.return_value = table
            servi = queries.get_payslip_history("ps-1")
        assert "payslip_data" in table.select.call_args.args[0]
        assert servi[0]["changes_summary"] == "Ligne « Salaire de base » corrigée : Avenant"
        assert any("aucune ligne corrigée" in p.lower() for p in servi[0]["contenu"])
        assert any("Avenant" in r for r in servi[0]["restauration"]["retirees"])

    def test_une_version_illisible_reste_servie_sans_apercu(self):
        from app.modules.payslips.infrastructure import queries

        lu = MagicMock()
        lu.data = {"edit_history": [{"version": 1, "changes_summary": "x", "previous_payslip_data": {}}],
                   "payslip_data": {}}
        table = MagicMock()
        table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = lu
        with patch.object(queries, "supabase") as base:
            base.table.return_value = table
            servi = queries.get_payslip_history("ps-1")
        assert servi[0]["version"] == 1
        assert servi[0].get("restauration") is None
