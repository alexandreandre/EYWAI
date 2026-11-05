"""Provision des congés : le repos compensateur entre dans la dette (retour d'Elsa du 05/11/2026).

« Soldes congés : N-1 + N + repos compensateur + ancienneté, hors RTT. » Un repos acquis et pas
pris est payé au départ du salarié (C. trav. D3121-23), comme un congé : c'est une dette.

Le compteur est en heures (crédit COR) ; une journée de repos vaut le réglage de la société
`hours_per_rest_day` (7 h par défaut), comme à l'écran des soldes.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.exports.domain import provision_cp as domaine
from app.modules.exports.infrastructure import export_provision_cp as module

pytestmark = pytest.mark.unit


# --- domaine : conversion du compteur ---------------------------------------------------------

def test_le_compteur_en_heures_se_convertit_en_jours_au_reglage_societe():
    assert domaine.repos_en_jours(21.0, 7.0, 7.0) == (2.0, "")


def test_une_journee_a_huit_heures_divise_par_huit():
    assert domaine.repos_en_jours(16.0, 0.0, 8.0) == (2.0, "")


def test_un_reglage_absent_replie_sur_sept_heures():
    assert domaine.repos_en_jours(14.0, 0.0, 0.0) == (2.0, "")


def test_un_repos_pris_sans_credit_ne_diminue_pas_la_dette_et_se_signale():
    jours, anomalie = domaine.repos_en_jours(0.0, 7.0, 7.0)
    assert jours == 0.0
    assert anomalie == "repos compensateur pris sans crédit : 7 h"


def test_un_compteur_vide_ne_dit_rien():
    assert domaine.repos_en_jours(0.0, 0.0, 7.0) == (0.0, "")


# --- domaine : la ligne et le total ------------------------------------------------------------

def test_le_repos_s_ajoute_aux_jours_provisionnes():
    ligne = domaine.calculer_ligne(
        matricule="M", nom="A B", date_entree="2020-01-01",
        solde_n1=10.0, solde_n=2.0, solde_repos=2.0,
        salaire_reference=2200.0, taux_charges=25.0, mois_retenus="9/12",
    )
    assert ligne.solde_repos == 2.0
    assert ligne.solde_jours == 14.0
    assert ligne.provision == 1400.0
    assert ligne.total == 1750.0


def test_sans_repos_la_ligne_ne_change_pas():
    ligne = domaine.calculer_ligne(
        matricule="M", nom="A B", date_entree="2020-01-01",
        solde_n1=10.0, solde_n=2.0,
        salaire_reference=2200.0, taux_charges=25.0, mois_retenus="9/12",
    )
    assert ligne.solde_repos == 0.0
    assert ligne.solde_jours == 12.0


def test_le_total_somme_le_repos():
    lignes = [
        domaine.calculer_ligne(
            matricule=m, nom=m, date_entree="2020-01-01", solde_n1=1.0, solde_n=1.0,
            solde_repos=r, salaire_reference=2200.0, taux_charges=0.0, mois_retenus="1/12",
        )
        for m, r in (("A", 1.5), ("B", 0.5))
    ]
    assert domaine.calculer_totaux(lignes)["solde_repos"] == 2.0


# --- lecture : crédits jusqu'au mois demandé, prises jusqu'à la date ---------------------------

class _TableFeinte:
    """Enregistre les filtres, rejoue la pagination."""

    def __init__(self, lignes):
        self._lignes = lignes
        self.filtres: list[tuple] = []
        self._debut, self._fin = 0, len(lignes)

    def select(self, *a, **k):
        return self

    def eq(self, colonne, valeur):
        self.filtres.append(("eq", colonne, valeur))
        return self

    def lte(self, colonne, valeur):
        self.filtres.append(("lte", colonne, valeur))
        return self

    def order(self, *a, **k):
        return self

    def range(self, debut, fin):
        self._debut, self._fin = debut, fin + 1
        return self

    def execute(self):
        return MagicMock(data=self._lignes[self._debut : self._fin])


def test_les_credits_sont_ceux_de_l_annee_jusqu_au_mois_demande():
    table = _TableFeinte([
        {"employee_id": "e1", "heures": 10.5},
        {"employee_id": "e1", "heures": 3.5},
        {"employee_id": "e2", "heures": 7},
    ])
    with patch.object(module.supabase, "table", return_value=table):
        heures = module._lire_credits_repos("c", 2026, 9)
    assert heures == {"e1": 14.0, "e2": 7.0}
    assert ("eq", "company_id", "c") in table.filtres
    assert ("eq", "year", 2026) in table.filtres
    assert ("lte", "month", 9) in table.filtres


def test_les_credits_se_lisent_au_dela_d_une_page():
    lignes = [{"employee_id": "e1", "heures": 1} for _ in range(module.TAILLE_PAGE + 3)]
    with patch.object(module.supabase, "table", return_value=_TableFeinte(lignes)):
        heures = module._lire_credits_repos("c", 2026, 9)
    assert heures == {"e1": float(module.TAILLE_PAGE + 3)}


def test_le_solde_de_repos_par_salarie_a_la_fin_du_mois():
    prises = [
        {"employee_id": "e1", "type": "repos_compensateur", "selected_days": ["2026-09-10"],
         "heures_par_jour": {}},
        # Après la fin du mois demandé : pas encore pris au 30/09.
        {"employee_id": "e1", "type": "repos_compensateur", "selected_days": ["2026-10-05"],
         "heures_par_jour": {}},
        # L'an dernier : hors du compteur de l'année, comme à l'écran.
        {"employee_id": "e1", "type": "repos_compensateur", "selected_days": ["2025-12-15"],
         "heures_par_jour": {}},
        # Une demi-journée en heures.
        {"employee_id": "e2", "type": "repos_compensateur", "selected_days": ["2026-09-11"],
         "heures_par_jour": {"2026-09-11": 3.5}},
        {"employee_id": "e2", "type": "conge_paye", "selected_days": ["2026-09-12"]},
    ]
    with patch.object(module, "_lire_credits_repos", return_value={"e1": 21.0, "e2": 7.0}), \
         patch.object(module.absence_repository, "list_validated_for_employees", return_value=prises), \
         patch.object(module, "_hours_per_rest_day", return_value=7.0):
        repos = module._lire_repos("c", date(2026, 9, 30), ["e1", "e2", "e3"])
    assert repos["e1"] == (2.0, "")
    assert repos["e2"] == (0.5, "")
    assert repos.get("e3", (0.0, "")) == (0.0, "")


# --- l'état ------------------------------------------------------------------------------------

SALARIE = {"id": "e1", "matricule": "M", "first_name": "A", "last_name": "B", "hire_date": "2020-01-01",
           "employment_status": "actif", "salaire_de_base": {"valeur": 2200.0}}


def _etat(soldes_cp, repos):
    return (
        patch.object(module, "_lire_salaries", return_value=[SALARIE]),
        patch.object(module, "_lire_bulletins", return_value={"e1": {(2026, 9): (2200.0, 550.0)}}),
        patch.object(module, "_lire_soldes_ouvres", return_value=soldes_cp),
        patch.object(module, "_lire_bascule", return_value=None),
        patch.object(module, "_lire_repos", return_value=repos),
    )


def test_le_repos_entre_dans_la_ligne_de_l_etat():
    a, b, c, d, e = _etat((10.0, 2.0), {"e1": (2.0, "")})
    with a, b, c, d, e:
        lignes, _ = module.collecter_lignes("c", "2026-09")
    assert lignes[0].solde_repos == 2.0
    assert lignes[0].solde_jours == 14.0


def test_un_salarie_sans_conges_mais_avec_du_repos_est_provisionne():
    a, b, c, d, e = _etat((0.0, 0.0), {"e1": (1.0, "")})
    with a, b, c, d, e:
        lignes, _ = module.collecter_lignes("c", "2026-09")
    assert len(lignes) == 1
    assert lignes[0].provision == 100.0


def test_l_anomalie_du_repos_va_dans_la_colonne_anomalie():
    a, b, c, d, e = _etat((10.0, 2.0), {"e1": (0.0, "repos compensateur pris sans crédit : 7 h")})
    with a, b, c, d, e:
        lignes, _ = module.collecter_lignes("c", "2026-09")
    assert "repos compensateur pris sans crédit : 7 h" in lignes[0].anomalie


def test_le_fichier_porte_la_colonne_du_repos_et_son_total():
    a, b, c, d, e = _etat((10.0, 2.0), {"e1": (2.0, "")})
    with a, b, c, d, e:
        contenu = module.generate_provision_cp_export("c", "2026-09", file_format="csv")
    entete, *lignes = list(csv.reader(io.StringIO(contenu.decode("utf-8-sig"))))
    rang = entete.index("Solde jrs repos compensateur")
    assert rang == entete.index("Solde jrs N") + 1
    assert lignes[0][rang] == "2.0"
    total = next(l for l in lignes if l[1] == "Total")
    assert total[rang] == "2.0"
