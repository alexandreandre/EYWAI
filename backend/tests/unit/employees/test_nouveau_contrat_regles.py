"""Nouveau contrat d'un salarié parti : règles pures (refus, ancienneté, écritures).

Cas de référence : une salariée en CDD du 19/01/2026 au 31/05/2026, départ
archivé, revenue le 01/09/2026 en CDD.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.employees.domain.nouveau_contrat import (
    ContratPrecedent,
    Demande,
    contrat_precedent,
    date_anciennete,
    ecritures,
    message_de_succes,
    premier_jour_possible,
    raison_du_refus,
    raison_indisponible,
)

pytestmark = pytest.mark.unit

FICHE = {
    "employment_status": "parti",
    "hire_date": "2026-01-19",
    "date_debut_execution": None,
    "contract_type": "CDD",
    "contract_end_date": "2026-05-31",
    "seniority_reference_date": "2026-01-19",
    "duree_hebdomadaire": "39.00",
    "job_title": "Opératrice polyvalente",
    "salaire_de_base": {"type": "mensuel", "valeur": 1964.73},
}
DEPART = {"id": "depart-1", "last_working_day": "2026-05-31"}
PRECEDENT = ContratPrecedent("CDD", date(2026, 1, 19), date(2026, 5, 31))


def _demande(**champs) -> Demande:
    base = {
        "date_debut": date(2026, 9, 1),
        "contract_type": "CDD",
        "date_fin": date(2026, 12, 18),
        "duree_hebdomadaire": 39.0,
        "salaire_mensuel": 2017.22,
        "job_title": "Opératrice polyvalente",
        "reprendre_anciennete": False,
    }
    base.update(champs)
    return Demande(**base)


def _refus(fiche=FICHE, demande=None, *, bulletin=True, bascule=None):
    fiche = dict(fiche)
    return raison_du_refus(
        fiche,
        contrat_precedent(fiche, DEPART),
        demande or _demande(),
        bulletin_du_dernier_mois=bulletin,
        rang_de_bascule=bascule,
    )


class TestContratPrecedent:
    def test_debut_d_entree_et_fin_du_depart(self):
        assert contrat_precedent(FICHE, DEPART) == PRECEDENT

    def test_sans_depart_la_fin_de_contrat_de_la_fiche(self):
        assert contrat_precedent(FICHE, None).fin == date(2026, 5, 31)

    def test_un_depart_anticipe_l_emporte_sur_la_fin_prevue(self):
        assert contrat_precedent(FICHE, {"last_working_day": "2026-04-30"}).fin == date(2026, 4, 30)

    def test_un_cdi_parti_sans_depart_n_a_pas_de_fin_connue(self):
        fiche = {**FICHE, "contract_type": "CDI", "contract_end_date": None}
        assert contrat_precedent(fiche, None) is None


class TestIndisponible:
    def test_un_salarie_parti(self):
        assert raison_indisponible(FICHE, PRECEDENT) is None

    @pytest.mark.parametrize("statut", ["sorti", "inactif"])
    def test_les_autres_statuts_de_depart(self, statut):
        assert raison_indisponible({**FICHE, "employment_status": statut}, PRECEDENT) is None

    def test_un_depart_pas_cloture(self):
        raison = raison_indisponible({**FICHE, "employment_status": "en_sortie"}, PRECEDENT)
        assert "Clôturez-le dans Départs" in raison

    def test_un_salarie_actif(self):
        raison = raison_indisponible({**FICHE, "employment_status": "actif"}, PRECEDENT)
        assert raison == "Un nouveau contrat se crée sur la fiche d'un salarié parti."

    def test_fin_inconnue(self):
        assert "fin du contrat précédent est inconnue" in raison_indisponible(FICHE, None)


class TestRefus:
    def test_le_cas_de_reference_passe(self):
        assert _refus() is None

    def test_le_premier_jour_possible(self):
        assert premier_jour_possible(PRECEDENT) == date(2026, 6, 1)
        assert premier_jour_possible(ContratPrecedent("CDD", date(2026, 1, 1), date(2026, 12, 15))) == date(2027, 1, 1)

    def test_avant_la_fin_du_precedent(self):
        assert _refus(demande=_demande(date_debut=date(2026, 5, 31))) == (
            "Le nouveau contrat doit commencer après la fin du précédent (31/05/2026)."
        )

    def test_le_meme_mois_que_la_fin_du_precedent(self):
        fiche = {**FICHE, "contract_end_date": "2026-05-15"}
        refus = raison_du_refus(
            fiche,
            contrat_precedent(fiche, {"last_working_day": "2026-05-15"}),
            _demande(date_debut=date(2026, 5, 20)),
            bulletin_du_dernier_mois=True,
            rang_de_bascule=None,
        )
        assert refus == (
            "Le nouveau contrat commencerait en 05/2026, le mois où le précédent se "
            "termine : Martine ne fait qu'un bulletin par mois. Il peut commencer le "
            "01/06/2026 au plus tôt."
        )

    def test_le_lendemain_au_premier_du_mois_passe(self):
        assert _refus(demande=_demande(date_debut=date(2026, 6, 1))) is None

    def test_cdd_sans_fin(self):
        assert _refus(demande=_demande(date_fin=None)) == "Indiquez la date de fin du CDD."

    def test_cdi_avec_fin(self):
        assert _refus(demande=_demande(contract_type="CDI")) == "Un CDI n'a pas de date de fin."

    def test_cdi_sans_fin_passe(self):
        assert _refus(demande=_demande(contract_type="CDI", date_fin=None)) is None

    def test_fin_avant_debut(self):
        assert _refus(demande=_demande(date_fin=date(2026, 8, 31))) == (
            "La date de fin est avant la date de début."
        )

    def test_type_inconnu(self):
        assert _refus(demande=_demande(contract_type="Intérim")) == (
            "Type de contrat inconnu : « Intérim »."
        )

    @pytest.mark.parametrize("duree", [0, -1, 49])
    def test_duree_invalide(self, duree):
        assert "Durée hebdomadaire invalide" in _refus(demande=_demande(duree_hebdomadaire=duree))

    def test_salaire_absent(self):
        assert _refus(demande=_demande(salaire_mensuel=0)) == (
            "Indiquez le salaire de base mensuel du nouveau contrat."
        )

    def test_dernier_bulletin_du_precedent_manquant(self):
        assert _refus(bulletin=False) == (
            "Générez d'abord le bulletin de 05/2026, dernier mois du contrat précédent : "
            "il ne pourra plus l'être ensuite."
        )

    def test_dernier_mois_paye_par_l_ancien_logiciel(self):
        """Mai est antérieur à la bascule de reprise (août) : il appartient à l'ancien logiciel."""
        assert _refus(bulletin=False, bascule=2026 * 12 + 8) is None

    def test_un_salarie_actif_est_refuse(self):
        assert _refus(fiche={**FICHE, "employment_status": "actif"}) == (
            "Un nouveau contrat se crée sur la fiche d'un salarié parti."
        )


class TestAnciennete:
    def test_case_decochee_l_anciennete_part_du_nouveau_contrat(self):
        assert date_anciennete(FICHE, PRECEDENT, _demande()) == date(2026, 9, 1)

    def test_case_cochee_la_date_du_contrat_precedent_est_gardee(self):
        fiche = {**FICHE, "seniority_reference_date": "2025-03-01"}
        assert date_anciennete(fiche, PRECEDENT, _demande(reprendre_anciennete=True)) == date(2025, 3, 1)

    def test_case_cochee_sans_date_d_anciennete_le_debut_du_precedent(self):
        """La date d'entrée change : un champ vide retomberait sur le nouveau début."""
        fiche = {**FICHE, "seniority_reference_date": None}
        assert date_anciennete(fiche, PRECEDENT, _demande(reprendre_anciennete=True)) == date(2026, 1, 19)


class TestEcritures:
    def test_le_contrat_range(self):
        periode, _, _ = ecritures(FICHE, PRECEDENT, _demande())
        assert periode == {"contract_type": "CDD", "date_debut": "2026-01-19", "date_fin": "2026-05-31"}

    def test_la_fiche_porte_le_nouveau_contrat(self):
        _, fiche, _ = ecritures(FICHE, PRECEDENT, _demande())
        assert fiche == {
            "hire_date": "2026-09-01",
            "date_debut_execution": None,
            "date_conclusion_contrat": None,
            "contract_type": "CDD",
            "contract_end_date": "2026-12-18",
            "duree_hebdomadaire": 39.0,
            "is_temps_partiel": False,
            "job_title": "Opératrice polyvalente",
            "employment_status": "actif",
            "current_exit_id": None,
            "seniority_reference_date": "2026-09-01",
        }

    def test_temps_partiel_et_poste_vide(self):
        _, fiche, _ = ecritures(FICHE, PRECEDENT, _demande(duree_hebdomadaire=24, job_title="  "))
        assert fiche["is_temps_partiel"] is True
        assert fiche["job_title"] == "Opératrice polyvalente"

    def test_le_salaire_change_est_historise_au_debut(self):
        _, _, salaire = ecritures(FICHE, PRECEDENT, _demande())
        assert salaire == {
            "ancien_salaire": {"type": "mensuel", "valeur": 1964.73},
            "nouveau_salaire": {"type": "mensuel", "valeur": 2017.22},
            "motif": "Nouveau contrat du 01/09/2026",
            "effective_date": "2026-09-01",
        }

    def test_le_meme_salaire_n_ecrit_pas_d_historique(self):
        _, _, salaire = ecritures(FICHE, PRECEDENT, _demande(salaire_mensuel=1964.73))
        assert salaire is None


def test_message_de_succes():
    assert message_de_succes(PRECEDENT, _demande()) == (
        "Nouveau contrat enregistré : CDD du 01/09/2026 au 18/12/2026. Le contrat "
        "précédent (CDD du 19/01/2026 au 31/05/2026) est dans les contrats passés. Le "
        "bulletin de 09/2026 peut être généré."
    )
    assert message_de_succes(PRECEDENT, _demande(contract_type="CDI", date_fin=None)).startswith(
        "Nouveau contrat enregistré : CDI à partir du 01/09/2026."
    )
