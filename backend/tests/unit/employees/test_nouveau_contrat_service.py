"""« Nouveau contrat » côté serveur : ce qui est lu, ce qui est écrit, dans quel ordre.

Rien ne doit rester à moitié écrit : la fiche bascule d'abord, sous condition
(elle n'a pas changé depuis la lecture), puis le contrat précédent est rangé ;
si le rangement échoue, la fiche revient à son état d'avant. Le salaire passe
par l'historique, comme l'onglet Augmentations ; s'il échoue, le contrat reste
enregistré et la réponse dit où saisir le salaire.
"""

from __future__ import annotations

import copy
from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.employees.application import nouveau_contrat as service

pytestmark = pytest.mark.unit

EMP, SOC = "emp-1", "soc-1"
FICHE = {
    "id": EMP,
    "company_id": SOC,
    "employment_status": "parti",
    "hire_date": "2026-01-19",
    "date_debut_execution": None,
    "date_conclusion_contrat": None,
    "is_temps_partiel": False,
    "current_exit_id": None,
    "contract_type": "CDD",
    "contract_end_date": "2026-05-31",
    "seniority_reference_date": "2026-01-19",
    "duree_hebdomadaire": "39.00",
    "job_title": "Opératrice polyvalente",
    "salaire_de_base": {"type": "mensuel", "valeur": 1964.73},
}
DEPART = {"id": "depart-1", "last_working_day": "2026-05-31", "status": "archivee"}


class _Requete:
    def __init__(self, base, table):
        self.base, self.table, self.op, self.filtres, self.valeurs = base, table, "select", {}, None

    def select(self, *_a, **_k):
        return self

    def update(self, valeurs):
        self.op, self.valeurs = "update", valeurs
        return self

    def eq(self, colonne, valeur):
        self.filtres[colonne] = valeur
        return self

    def neq(self, *_a):
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a):
        return self

    def execute(self):
        return SimpleNamespace(data=self.base.executer(self))


class _Base:
    def __init__(self, fiche=None, depart=DEPART, bulletins=(), bascule=None):
        self.fiche = copy.deepcopy(fiche or FICHE)
        self.depart = depart
        self.bulletins = set(bulletins)
        self.journal: list[tuple] = []
        self.refuser_mise_a_jour = False

    def table(self, nom):
        return _Requete(self, nom)

    def executer(self, r: _Requete):
        if r.table == "employees" and r.op == "select":
            return [copy.deepcopy(self.fiche)]
        if r.table == "employees" and r.op == "update":
            self.journal.append(("update", dict(r.filtres), dict(r.valeurs)))
            if self.refuser_mise_a_jour:
                return []
            if any(self.fiche.get(c) != v for c, v in r.filtres.items() if c not in ("id", "company_id")):
                return []
            self.fiche.update(r.valeurs)
            return [copy.deepcopy(self.fiche)]
        if r.table == "employee_exits":
            return [self.depart] if self.depart else []
        if r.table == "payslips":
            cle = (r.filtres.get("year"), r.filtres.get("month"))
            return [{"id": "b"}] if cle in self.bulletins else []
        raise AssertionError(f"lecture inattendue : {r.table} {r.op}")


@pytest.fixture
def base(monkeypatch):
    b = _Base(bulletins={(2026, 5)})
    monkeypatch.setattr(service, "supabase", b)
    monkeypatch.setattr(service, "lire_bascule", lambda _c: None)
    b.periodes = []
    b.salaires = []

    def ranger(employee_id, company_id, payload):
        b.journal.append(("periode", payload.contract_type, payload.date_debut.isoformat(), payload.date_fin.isoformat()))
        ligne = {"id": "periode-1", "contract_type": payload.contract_type,
                 "date_debut": payload.date_debut.isoformat(), "date_fin": payload.date_fin.isoformat()}
        b.periodes.append(ligne)
        return ligne

    def historiser(employee_id, company_id, ancien_salaire, nouveau_salaire, motif, effective_date, created_by):
        b.journal.append(("salaire", nouveau_salaire["valeur"], effective_date))
        b.salaires.append(nouveau_salaire)
        return {"id": "salaire-1"}

    monkeypatch.setattr(service, "add_contract_period", ranger)
    monkeypatch.setattr(service, "apply_salary_update", historiser)
    monkeypatch.setattr(service, "get_employee_by_id", lambda e, c: {"id": e, **b.fiche})
    return b


def _payload(**champs):
    base = {
        "date_debut": "2026-09-01",
        "contract_type": "CDD",
        "date_fin": "2026-12-18",
        "duree_hebdomadaire": 39,
        "salaire_mensuel": 2017.22,
        "job_title": "Opératrice polyvalente",
        "reprendre_anciennete": False,
    }
    base.update(champs)
    return service.NouveauContratIn(**base)


class TestApercu:
    def test_un_salarie_parti(self, base):
        apercu = service.apercu(EMP, SOC)
        assert apercu["possible"] is True
        assert apercu["raison"] is None
        assert apercu["contrat_precedent"] == {
            "contract_type": "CDD", "date_debut": "2026-01-19", "date_fin": "2026-05-31"
        }
        assert apercu["premier_jour_possible"] == "2026-06-01"
        assert apercu["date_anciennete"] == "2026-01-19"
        assert apercu["prerempli"] == {
            "contract_type": "CDD",
            "duree_hebdomadaire": 39.0,
            "salaire_mensuel": 1964.73,
            "job_title": "Opératrice polyvalente",
        }
        assert apercu["types"] == ["CDI", "CDD", "Apprentissage", "Contrat de professionnalisation"]

    def test_un_salarie_actif(self, base):
        base.fiche["employment_status"] = "actif"
        apercu = service.apercu(EMP, SOC)
        assert apercu["possible"] is False
        assert apercu["raison"] == "Un nouveau contrat se crée sur la fiche d'un salarié parti."

    def test_type_hors_liste_preremplit_un_cdd(self, base):
        base.fiche["contract_type"] = "Stage"
        assert service.apercu(EMP, SOC)["prerempli"]["contract_type"] == "CDD"


class TestCreer:
    def test_ordre_des_ecritures(self, base):
        resultat = service.creer(EMP, SOC, _payload(), "rh-1")

        assert [e[0] for e in base.journal] == ["update", "periode", "salaire"]
        _, filtres, valeurs = base.journal[0]
        # Bascule conditionnelle : la fiche n'a pas changé depuis la lecture.
        assert filtres == {"id": EMP, "company_id": SOC, "employment_status": "parti", "hire_date": "2026-01-19"}
        assert valeurs["hire_date"] == "2026-09-01"
        assert valeurs["employment_status"] == "actif"
        assert base.journal[1] == ("periode", "CDD", "2026-01-19", "2026-05-31")
        assert base.journal[2] == ("salaire", 2017.22, "2026-09-01")
        assert resultat["message"].startswith("Nouveau contrat enregistré : CDD du 01/09/2026 au 18/12/2026.")
        assert resultat["avertissements"] == []
        assert resultat["employee"]["employment_status"] == "actif"
        assert resultat["date_anciennete"] == "2026-09-01"

    def test_la_case_cochee_garde_la_date_d_anciennete(self, base):
        resultat = service.creer(EMP, SOC, _payload(reprendre_anciennete=True), "rh-1")
        assert base.fiche["seniority_reference_date"] == "2026-01-19"
        assert resultat["date_anciennete"] == "2026-01-19"

    def test_un_refus_n_ecrit_rien(self, base):
        with pytest.raises(service.NouveauContratRefuse, match="Indiquez la date de fin du CDD"):
            service.creer(EMP, SOC, _payload(date_fin=None), "rh-1")
        assert base.journal == []

    def test_le_dernier_bulletin_du_precedent_est_exige(self, base):
        base.bulletins.clear()
        with pytest.raises(service.NouveauContratRefuse, match="Générez d'abord le bulletin de 05/2026"):
            service.creer(EMP, SOC, _payload(), "rh-1")
        assert base.journal == []

    def test_avant_la_bascule_le_dernier_mois_appartient_a_l_ancien_logiciel(self, base, monkeypatch):
        base.bulletins.clear()
        monkeypatch.setattr(service, "lire_bascule", lambda _c: SimpleNamespace(rang=2026 * 12 + 8))
        service.creer(EMP, SOC, _payload(), "rh-1")
        assert base.fiche["employment_status"] == "actif"

    def test_une_fiche_modifiee_entre_temps(self, base):
        base.refuser_mise_a_jour = True
        with pytest.raises(service.FicheModifiee, match="Rechargez la page"):
            service.creer(EMP, SOC, _payload(), "rh-1")
        assert [e[0] for e in base.journal] == ["update"]

    def test_le_rangement_echoue_la_fiche_revient(self, base, monkeypatch):
        def en_panne(*_a, **_k):
            raise RuntimeError("base injoignable")

        monkeypatch.setattr(service, "add_contract_period", en_panne)
        with pytest.raises(service.NonEnregistre, match="rien n'a changé"):
            service.creer(EMP, SOC, _payload(), "rh-1")
        assert base.fiche == {**FICHE}
        assert [e[0] for e in base.journal] == ["update", "update"]

    def test_le_rangement_et_le_retour_echouent(self, base, monkeypatch):
        def en_panne(*_a, **_k):
            base.refuser_mise_a_jour = True
            raise RuntimeError("base injoignable")

        monkeypatch.setattr(service, "add_contract_period", en_panne)
        with pytest.raises(service.NonEnregistre) as erreur:
            service.creer(EMP, SOC, _payload(), "rh-1")
        assert "ajoutez-le dans les contrats passés : CDD du 19/01/2026 au 31/05/2026" in str(erreur.value)

    def test_le_salaire_echoue_le_contrat_reste_et_la_reponse_le_dit(self, base, monkeypatch):
        def en_panne(*_a, **_k):
            raise RuntimeError("base injoignable")

        monkeypatch.setattr(service, "apply_salary_update", en_panne)
        resultat = service.creer(EMP, SOC, _payload(), "rh-1")
        assert base.fiche["employment_status"] == "actif"
        assert resultat["avertissements"] == [
            (
                "Le salaire n'a pas été mis à jour : saisissez 2 017,22 € dans l'onglet "
                "Augmentations, date d'effet le 01/09/2026."
            )
        ]

    def test_meme_salaire_pas_d_historique(self, base):
        service.creer(EMP, SOC, _payload(salaire_mensuel=1964.73), "rh-1")
        assert [e[0] for e in base.journal] == ["update", "periode"]


def test_le_corps_de_requete_valide_les_dates():
    with pytest.raises(ValueError):
        service.NouveauContratIn(
            date_debut="pas une date", contract_type="CDD", duree_hebdomadaire=39, salaire_mensuel=1
        )
    corps = _payload(contract_type=" CDI ", date_fin=None)
    assert corps.contract_type == "CDI"
    assert corps.date_debut == date(2026, 9, 1)
