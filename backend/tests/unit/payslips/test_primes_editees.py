"""Ce qui a changé dans les primes saisies entre deux versions d'un bulletin."""

import pytest

from app.modules.payslips.domain.primes_editees import diff_primes

pytestmark = pytest.mark.unit

BASE = {"libelle": "Salaire de base", "quantite": 151.67, "taux": 14.28, "gain": 2165.85}


def _prime(saisie_id, gain, libelle="Prime exceptionnelle"):
    return {"libelle": libelle, "quantite": None, "taux": None, "gain": gain, "saisie_id": saisie_id}


def _bulletin(*lignes, non_soumises=()):
    return {"calcul_du_brut": [BASE, *lignes], "primes_non_soumises": list(non_soumises)}


NOUVELLE = {
    "libelle": "Prime de fin de chantier",
    "gain": 100.0,
    "nouvelle_saisie": {
        "name": "Prime de fin de chantier",
        "amount": 100.0,
        "is_socially_taxed": True,
        "is_taxable": True,
        "catalog_prime_id": None,
    },
}


def test_rien_ne_change_diff_vide():
    avant = _bulletin(_prime("s-1", 100.0))
    assert diff_primes(avant, _bulletin(_prime("s-1", 100.0))).vide


def test_une_prime_ajoutee_depuis_le_bulletin():
    diff = diff_primes(_bulletin(), _bulletin(NOUVELLE))

    assert diff.ajoutees == (
        {
            "name": "Prime de fin de chantier",
            "amount": 100.0,
            "is_socially_taxed": True,
            "is_taxable": True,
            "catalog_prime_id": None,
        },
    )
    assert not diff.modifiees and not diff.retirees


def test_le_montant_retouche_apres_ajout_fait_foi():
    retouchee = {**NOUVELLE, "gain": 120.0}
    assert diff_primes(_bulletin(), _bulletin(retouchee)).ajoutees[0]["amount"] == 120.0


def test_un_montant_corrige():
    diff = diff_primes(_bulletin(_prime("s-1", 100.0)), _bulletin(_prime("s-1", 150.0)))
    assert diff.modifiees == (("s-1", 150.0),)


def test_une_prime_retiree():
    diff = diff_primes(_bulletin(_prime("s-1", 100.0)), _bulletin())
    assert diff.retirees == ("s-1",)
    assert diff.ids_touches == {"s-1"}


def test_une_prime_non_soumise_se_lit_sur_son_montant():
    avant = _bulletin(non_soumises=[{"libelle": "Panier", "montant": 7.5, "saisie_id": "s-2"}])
    apres = _bulletin(non_soumises=[{"libelle": "Panier", "montant": 15.0, "saisie_id": "s-2"}])
    assert diff_primes(avant, apres).modifiees == (("s-2", 15.0),)


def test_une_ligne_calculee_retouchee_n_est_pas_une_prime():
    retouchee = {**BASE, "gain": 2000.0}
    assert diff_primes(_bulletin(), {"calcul_du_brut": [retouchee]}).vide


def test_un_lien_inconnu_du_bulletin_d_origine_est_ignore():
    """Un saisie_id absent d'avant n'a rien à corriger : on ne l'invente pas."""
    assert diff_primes(_bulletin(), _bulletin(_prime("s-9", 100.0))).vide


def test_ajout_et_retrait_dans_le_meme_enregistrement():
    diff = diff_primes(_bulletin(_prime("s-1", 100.0)), _bulletin(NOUVELLE))
    assert diff.retirees == ("s-1",)
    assert len(diff.ajoutees) == 1


def test_sans_marques_retire_nouvelle_saisie_sans_toucher_au_reste():
    from app.modules.payslips.domain.primes_editees import sans_marques_de_saisie

    avant = _bulletin(_prime("s-1", 100.0), NOUVELLE)
    propre = sans_marques_de_saisie(avant)

    assert "nouvelle_saisie" in avant["calcul_du_brut"][2]  # l'original n'est pas modifié
    assert "nouvelle_saisie" not in propre["calcul_du_brut"][2]
    assert propre["calcul_du_brut"][1]["saisie_id"] == "s-1"


# --- Une prime ajoutée ne porte que ses propres champs (audit du 28/09, K1) ---

def test_une_prime_ajoutee_ne_garde_que_ses_champs():
    forgee = {
        **NOUVELLE["nouvelle_saisie"],
        "employee_id": "autre-salarie",
        "company_id": "autre-societe",
        "year": 2025,
        "month": 1,
        "manual_override": False,
        "payroll_quantity": 12,
    }
    diff = diff_primes(_bulletin(), _bulletin({**NOUVELLE, "nouvelle_saisie": forgee}))

    assert diff.ajoutees == (
        {
            "name": "Prime de fin de chantier",
            "is_socially_taxed": True,
            "is_taxable": True,
            "catalog_prime_id": None,
            "amount": 100.0,
        },
    )


def test_prime_ajoutee_propre_retire_tout_champ_inconnu():
    from app.modules.payslips.domain.primes_editees import prime_ajoutee_propre

    assert prime_ajoutee_propre({"name": "X", "employee_id": "e", "month": 3}) == {"name": "X"}


def test_l_insertion_impose_le_salarie_la_societe_et_la_periode_du_bulletin():
    from unittest.mock import MagicMock, patch

    from app.modules.payslips.application import primes_editees as app_primes
    from app.modules.payslips.domain.primes_editees import DiffPrimes

    client = MagicMock()
    diff = DiffPrimes(ajoutees=({"name": "Prime", "amount": 10.0, "employee_id": "autre"},))
    with patch.object(app_primes, "supabase", client):
        app_primes.appliquer_primes_editees(
            diff, employee_id="e1", company_id="c1", year=2026, month=9
        )

    assert client.table.return_value.insert.call_args.args[0] == [
        {
            "name": "Prime",
            "amount": 10.0,
            "employee_id": "e1",
            "company_id": "c1",
            "year": 2026,
            "month": 9,
            "manual_override": True,
        }
    ]


class _Saisies:
    """`monthly_inputs` en mémoire, pour les retraits depuis le bulletin."""

    def __init__(self, lignes):
        self.lignes = {str(l["id"]): dict(l) for l in lignes}
        self.supprimees: list[str] = []
        self._ids: list[str] = []

    def table(self, nom):
        assert nom == "monthly_inputs"
        self._action, self._ids, self._valeurs = None, [], None
        return self

    def select(self, *_a):
        self._action = "select"
        return self

    def update(self, valeurs):
        self._action, self._valeurs = "update", valeurs
        return self

    def delete(self):
        self._action = "delete"
        return self

    def in_(self, _cle, ids):
        self._ids = [str(i) for i in ids]
        return self

    def eq(self, _cle, valeur):
        self._ids = [str(valeur)]
        return self

    def execute(self):
        from unittest.mock import MagicMock

        if self._action == "select":
            return MagicMock(data=[self.lignes[i] for i in self._ids if i in self.lignes])
        for i in self._ids:
            if self._action == "update":
                self.lignes[i].update(self._valeurs)
            elif self._action == "delete":
                self.supprimees.append(i)
                self.lignes.pop(i, None)
        return MagicMock(data=[])


def test_une_prime_generee_retiree_du_bulletin_passe_a_zero_et_ne_revient_pas():
    """Comitech : la génération des variables tourne avant chaque bulletin. Une
    prime de règle automatique supprimée y était recréée ; retirée, elle passe à
    0 avec manual_override, que la génération respecte."""
    from unittest.mock import patch

    from app.modules.payroll_variables.infrastructure import repository as variables
    from app.modules.payslips.application import primes_editees as app_primes
    from app.modules.payslips.domain.primes_editees import DiffPrimes

    base = _Saisies(
        [
            {"id": "s-auto", "name": "Prime de poste difficile", "description": "Auto: PRIME_POSTE_DIFFICILE", "amount": 80.0},
            {"id": "s-main", "name": "Prime exceptionnelle", "description": None, "amount": 50.0},
        ]
    )
    with patch.object(app_primes, "supabase", base):
        app_primes.appliquer_primes_editees(
            DiffPrimes(retirees=("s-auto", "s-main")),
            employee_id="e1", company_id="c1", year=2026, month=10,
        )

    assert base.supprimees == ["s-main"]
    assert base.lignes["s-auto"]["amount"] == 0
    assert base.lignes["s-auto"]["manual_override"] is True

    # La génération suivante ne repasse pas derrière.
    with (
        patch.object(variables, "find_existing_monthly_input", return_value=base.lignes["s-auto"]),
        patch.object(variables, "supabase") as client,
    ):
        variables.upsert_monthly_input(
            {"employee_id": "e1", "year": 2026, "month": 10, "name": "Prime de poste difficile", "amount": 80.0}
        )
    client.table.assert_not_called()


def test_un_montant_corrige_au_bulletin_n_est_plus_ecrase_par_la_generation():
    from unittest.mock import MagicMock, patch

    from app.modules.payslips.application import primes_editees as app_primes
    from app.modules.payslips.domain.primes_editees import DiffPrimes

    client = MagicMock()
    with patch.object(app_primes, "supabase", client):
        app_primes.appliquer_primes_editees(
            DiffPrimes(modifiees=(("s-1", 150.0),)),
            employee_id="e1", company_id="c1", year=2026, month=9,
        )

    client.table.return_value.update.assert_called_once_with(
        {"amount": 150.0, "manual_override": True}
    )


def test_une_retenue_sur_le_net_ajoutee_depuis_le_bulletin_devient_une_saisie_sur_le_net():
    """Défaut 1 de l'écran du bulletin : la retenue sur le net devenait une prime
    négative non soumise, parce que `sur_le_net` ne traversait pas la requête."""
    from unittest.mock import MagicMock, patch

    from app.modules.payslips.application import primes_editees as app_primes
    from app.modules.payslips.schemas.requests import PayslipEditRequest

    requete = PayslipEditRequest(
        corrections={
            "primes_ajoutees": [
                {
                    "name": "Acompte",
                    "amount": -200,
                    "sur_le_net": True,
                    "is_socially_taxed": False,
                    "is_taxable": False,
                }
            ]
        }
    )
    diff = requete.corrections.vers_domaine().primes
    client = MagicMock()
    with patch.object(app_primes, "supabase", client):
        app_primes.appliquer_primes_editees(
            diff, employee_id="e1", company_id="c1", year=2026, month=9
        )

    insere = client.table.return_value.insert.call_args.args[0][0]
    assert insere["sur_le_net"] is True
    assert insere["amount"] == -200.0
    assert insere["is_socially_taxed"] is False


def test_une_prime_ajoutee_sans_precision_n_est_pas_sur_le_net():
    from unittest.mock import MagicMock, patch

    from app.modules.payslips.application import primes_editees as app_primes
    from app.modules.payslips.schemas.requests import PayslipEditRequest

    requete = PayslipEditRequest(
        corrections={"primes_ajoutees": [{"name": "Prime", "amount": 50}]}
    )
    client = MagicMock()
    with patch.object(app_primes, "supabase", client):
        app_primes.appliquer_primes_editees(
            requete.corrections.vers_domaine().primes,
            employee_id="e1", company_id="c1", year=2026, month=9,
        )
    assert client.table.return_value.insert.call_args.args[0][0].get("sur_le_net") is False


def test_un_montant_corrige_au_bulletin_garde_le_sens_de_la_saisie():
    """Corriger un montant change le montant, jamais le sens : un positif sur
    une retenue serait lu par le moteur comme un versement ajouté au net."""
    from unittest.mock import patch

    from app.modules.payslips.application import primes_editees as app_primes
    from app.modules.payslips.domain.primes_editees import DiffPrimes

    base = _Saisies(
        [
            {"id": "s-ret", "amount": -200.0, "sur_le_net": True},
            {"id": "s-ver", "amount": 150.0, "sur_le_net": True},
            {"id": "s-prime", "amount": 300.0, "sur_le_net": False},
        ]
    )
    with patch.object(app_primes, "supabase", base):
        app_primes.appliquer_primes_editees(
            DiffPrimes(modifiees=(("s-ret", 201.0), ("s-ver", 160.0), ("s-prime", 350.0))),
            employee_id="e1", company_id="c1", year=2026, month=10,
        )

    assert base.lignes["s-ret"]["amount"] == -201.0
    assert base.lignes["s-ver"]["amount"] == 160.0
    assert base.lignes["s-prime"]["amount"] == 350.0
