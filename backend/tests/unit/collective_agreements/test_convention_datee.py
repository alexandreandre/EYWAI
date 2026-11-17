"""Convention et classification datées : Zone 404, de « sans convention » à Syntec.

Relevé du 16/11/2026 : `resolve_employee_idcc` lisait la première convention de
la société, sans date, et l'empreinte des bulletins hache la classification de
la fiche. Rattacher Syntec ou changer les classifications aurait appliqué Syntec
aux mois passés et fait passer « à recalculer » les bulletins repris de juillet
à octobre. Avec une date d'effet : avant elle, l'ancienne convention ; après,
Syntec ; sans date en base, rien ne change ; l'empreinte d'un mois passé ne
bouge pas. Chaque cas tourne sur un salarié en heures et un au forfait jours.
"""

from __future__ import annotations

import inspect
import json
from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.collective_agreements.application import idcc_resolution
from app.modules.collective_agreements.application.idcc_resolution import (
    build_convention_collective_payload,
    resolve_employee_idcc,
)
from app.modules.collective_agreements.domain.convention_datee import (
    CLE_CLASSIFICATION_AVANT,
    classification_a_la_date,
    classification_du_mois,
    dater_changement_classification,
    fin_du_mois,
    ligne_en_vigueur,
)
from app.modules.employees.application import contrat_du_mois
from app.modules.payroll.application.empreinte_entrees_service import (
    empreinte_des_lectures,
)
from tests.unit.payroll.test_filet_heures_sur_arret import (
    moteur,  # noqa: F401 — fixture
)

pytestmark = pytest.mark.unit

SOCIETE = "soc-zone"
SYNTEC = "cat-syntec"
PLASTURGIE = "cat-plasturgie"
CATALOGUE = {SYNTEC: "1486", PLASTURGIE: "0292"}
EFFET = date(2026, 11, 1)

SANS_CONVENTION = {
    "idcc": "9999",
    "position": "200",
    "statut_categoriel": "Cadre",
    "code_statut_dsn": "06",
    "classification_dsn": "742CE",
}
SYNTEC_CLASSIFICATION = {
    "idcc": "1486",
    "position": "2.1",
    "coefficient": 115,
    "statut_categoriel": "Cadre",
    "code_statut_dsn": "01",
    "classification_dsn": "742CE",
}

#: Un salarié en heures et un au forfait jours : la même règle pour les deux.
FICHES = {
    "heures": {
        "id": "emp-heures",
        "company_id": SOCIETE,
        "statut": "Non-Cadre",
        "is_forfait_jour": False,
        "duree_hebdomadaire": 35,
        "hire_date": "2026-03-02",
        "salaire_de_base": {"valeur": 2600},
        "contract_type": "CDI",
    },
    "forfait_jours": {
        "id": "emp-forfait",
        "company_id": SOCIETE,
        "statut": "Cadre",
        "is_forfait_jour": True,
        "duree_hebdomadaire": None,
        "hire_date": "2026-03-02",
        "salaire_de_base": {"valeur": 4200},
        "contract_type": "CDI",
    },
}


def _fiche(profil: str, classification) -> dict:
    return {**FICHES[profil], "classification_conventionnelle": classification}


def _apres_changement(profil: str) -> dict:
    """La fiche telle que la mise à jour datée l'enregistre."""
    return _fiche(
        profil,
        dater_changement_classification(SANS_CONVENTION, SYNTEC_CLASSIFICATION, EFFET),
    )


# --- Fausse base : conventions de la société et catalogue ------------------


class _Requete:
    def __init__(self, base: "_Base", table: str):
        self.base, self.table, self.filtres = base, table, {}

    def select(self, *_a, **_k):
        return self

    def eq(self, colonne, valeur):
        self.filtres[colonne] = valeur
        return self

    limit = order = lambda self, *_a, **_k: self  # noqa: E731

    def maybe_single(self):
        self.unique = True
        return self

    def execute(self):
        if self.table == "company_collective_agreements":
            return SimpleNamespace(
                data=[r for r in self.base.lignes if r["company_id"] == self.filtres.get("company_id")]
            )
        if self.table == "collective_agreements_catalog":
            idcc = CATALOGUE.get(self.filtres.get("id"))
            if idcc is None and self.filtres.get("idcc"):
                return SimpleNamespace(data=[{"name": "Syntec"}])
            return SimpleNamespace(data={"idcc": idcc} if idcc else None)
        raise AssertionError(f"lecture inattendue : {self.table}")


class _Base:
    def __init__(self, lignes: list[dict]):
        self.lignes = lignes

    def table(self, nom: str) -> _Requete:
        return _Requete(self, nom)


def _ligne(agreement: str, debut: str | None = None, fin: str | None = None) -> dict:
    ligne = {"company_id": SOCIETE, "collective_agreement_id": agreement}
    if debut is not None:
        ligne["date_debut"] = debut
    if fin is not None:
        ligne["date_fin"] = fin
    return ligne


# --- La convention de la société à une date --------------------------------


@pytest.mark.parametrize("profil", list(FICHES))
class TestConventionDeLaSociete:
    def test_avant_la_date_l_ancienne_convention(self, profil):
        """Zone 404 : aucune convention avant le 01/11, companies.idcc vide."""
        base = _Base([_ligne(SYNTEC, "2026-11-01")])
        idcc = resolve_employee_idcc(
            FICHES[profil], {"id": SOCIETE}, supabase_client=base, a_la_date=fin_du_mois(2026, 10)
        )
        assert idcc is None

    def test_avant_la_date_la_convention_de_la_societe_reste(self, profil):
        base = _Base([_ligne(SYNTEC, "2026-11-01")])
        idcc = resolve_employee_idcc(
            FICHES[profil],
            {"id": SOCIETE, "idcc": "9999"},
            supabase_client=base,
            a_la_date=fin_du_mois(2026, 9),
        )
        assert idcc == "9999"

    def test_a_partir_de_la_date_syntec(self, profil):
        base = _Base([_ligne(SYNTEC, "2026-11-01")])
        for mois in (11, 12):
            idcc = resolve_employee_idcc(
                FICHES[profil], {"id": SOCIETE}, supabase_client=base, a_la_date=fin_du_mois(2026, mois)
            )
            assert idcc == "1486"

    def test_une_ligne_datee_prend_la_suite_d_une_ligne_sans_date(self, profil):
        base = _Base([_ligne(PLASTURGIE), _ligne(SYNTEC, "2026-11-01")])
        avant = resolve_employee_idcc(
            FICHES[profil], {"id": SOCIETE}, supabase_client=base, a_la_date=date(2026, 10, 31)
        )
        apres = resolve_employee_idcc(
            FICHES[profil], {"id": SOCIETE}, supabase_client=base, a_la_date=date(2026, 11, 30)
        )
        assert (avant, apres) == ("0292", "1486")

    def test_sans_date_en_base_rien_ne_change(self, profil):
        """Les 7 sociétés d'aujourd'hui : une ligne sans date vaut tous les mois."""
        base = _Base([_ligne(PLASTURGIE)])
        for a_la_date in (None, date(2020, 1, 31), date(2026, 7, 31), date(2030, 12, 31)):
            idcc = resolve_employee_idcc(
                FICHES[profil], {"id": SOCIETE, "idcc": "0292"}, supabase_client=base, a_la_date=a_la_date
            )
            assert idcc == "0292"

    def test_le_bloc_du_bulletin_suit_la_date(self, profil):
        base = _Base([_ligne(SYNTEC, "2026-11-01")])
        octobre = build_convention_collective_payload(
            FICHES[profil], {"id": SOCIETE}, supabase_client=base, a_la_date=fin_du_mois(2026, 10)
        )
        novembre = build_convention_collective_payload(
            FICHES[profil], {"id": SOCIETE}, supabase_client=base, a_la_date=fin_du_mois(2026, 11)
        )
        assert octobre == {}
        assert novembre["idcc"] == "1486"


def test_une_ligne_terminee_ne_vaut_plus():
    lignes = [_ligne(PLASTURGIE, None, "2026-10-31"), _ligne(SYNTEC, "2026-11-01")]
    assert ligne_en_vigueur(lignes, date(2026, 10, 31))["collective_agreement_id"] == PLASTURGIE
    assert ligne_en_vigueur(lignes, date(2026, 11, 1))["collective_agreement_id"] == SYNTEC


def test_sans_ligne_datee_la_premiere_comme_avant():
    lignes = [_ligne(PLASTURGIE), _ligne(SYNTEC)]
    assert ligne_en_vigueur(lignes, date(2026, 11, 30))["collective_agreement_id"] == PLASTURGIE


# --- La classification de la fiche à une date ------------------------------


class TestClassificationDatee:
    def test_avant_la_date_l_ancienne_classification_telle_qu_enregistree(self):
        datee = dater_changement_classification(SANS_CONVENTION, SYNTEC_CLASSIFICATION, EFFET)
        assert classification_du_mois(datee, 2026, 10) == SANS_CONVENTION
        assert classification_du_mois(datee, 2026, 7) == SANS_CONVENTION

    def test_a_partir_de_la_date_syntec_sans_la_note(self):
        datee = dater_changement_classification(SANS_CONVENTION, SYNTEC_CLASSIFICATION, EFFET)
        assert classification_du_mois(datee, 2026, 11) == SYNTEC_CLASSIFICATION

    def test_sans_note_la_classification_est_rendue_telle_quelle(self):
        assert classification_du_mois(SANS_CONVENTION, 2026, 10) is SANS_CONVENTION
        assert classification_du_mois(None, 2026, 10) is None

    def test_sans_date_la_note_enregistree_reste_et_celle_du_client_est_ignoree(self):
        enregistree = dater_changement_classification(SANS_CONVENTION, SYNTEC_CLASSIFICATION, EFFET)
        renvoyee = {
            **SYNTEC_CLASSIFICATION,
            "coefficient": 130,
            CLE_CLASSIFICATION_AVANT: {"a_partir_du": "2020-01-01", "classification": {}},
        }
        ecrite = dater_changement_classification(enregistree, renvoyee, None)
        assert ecrite[CLE_CLASSIFICATION_AVANT] == enregistree[CLE_CLASSIFICATION_AVANT]
        assert classification_du_mois(ecrite, 2026, 10) == SANS_CONVENTION
        assert classification_du_mois(ecrite, 2026, 11)["coefficient"] == 130

    def test_une_nouvelle_date_au_meme_jour_remplace_la_precedente(self):
        une = dater_changement_classification(SANS_CONVENTION, SYNTEC_CLASSIFICATION, EFFET)
        corrigee = {**SYNTEC_CLASSIFICATION, "coefficient": 130}
        deux = dater_changement_classification(une, corrigee, EFFET)
        assert deux[CLE_CLASSIFICATION_AVANT]["classification"] == SANS_CONVENTION
        assert classification_du_mois(deux, 2026, 10) == SANS_CONVENTION

    def test_deux_changements_successifs(self):
        une = dater_changement_classification(SANS_CONVENTION, SYNTEC_CLASSIFICATION, EFFET)
        promue = {**SYNTEC_CLASSIFICATION, "position": "2.2"}
        deux = dater_changement_classification(une, promue, date(2027, 3, 1))
        assert classification_du_mois(deux, 2026, 10) == SANS_CONVENTION
        assert classification_du_mois(deux, 2027, 2) == SYNTEC_CLASSIFICATION
        assert classification_du_mois(deux, 2027, 3) == promue

    def test_une_classification_en_texte_json(self):
        datee = dater_changement_classification(SANS_CONVENTION, SYNTEC_CLASSIFICATION, EFFET)
        assert classification_a_la_date(json.dumps(datee), date(2026, 10, 31)) == SANS_CONVENTION


# --- La fiche du mois (les deux générateurs, la DSN, les alertes) ----------


@pytest.mark.parametrize("profil", list(FICHES))
class TestFicheDuMois:
    def test_la_fiche_d_octobre_porte_l_ancienne_classification(self, profil):
        fiche = contrat_du_mois.fiche_du_mois(_apres_changement(profil), 2026, 10)
        assert fiche["classification_conventionnelle"] == SANS_CONVENTION
        assert fiche["is_forfait_jour"] is FICHES[profil]["is_forfait_jour"]

    def test_la_fiche_de_novembre_porte_syntec(self, profil):
        fiche = contrat_du_mois.fiche_du_mois(_apres_changement(profil), 2026, 11)
        assert fiche["classification_conventionnelle"] == SYNTEC_CLASSIFICATION

    def test_sans_changement_date_la_fiche_est_inchangee(self, profil):
        employee = _fiche(profil, SANS_CONVENTION)
        assert contrat_du_mois.fiche_du_mois(employee, 2026, 10) == employee


# --- L'empreinte : aucun bulletin passé « à recalculer » --------------------


def _empreinte(employee: dict, annee: int, mois: int) -> str:
    return empreinte_des_lectures(
        year=annee,
        month=mois,
        calendriers={},
        absences=[],
        saisies=[],
        employee=employee,
        company={"id": SOCIETE, "idcc": None, "settings": {}},
        fenetre_variables={"debut": f"{annee}-{mois:02d}-01", "fin": f"{annee}-{mois:02d}-28"},
    )


@pytest.mark.parametrize("profil", list(FICHES))
class TestEmpreinte:
    @pytest.mark.parametrize("mois", [7, 8, 9, 10])
    def test_l_empreinte_d_un_mois_passe_ne_bouge_pas(self, profil, mois):
        avant = _empreinte(_fiche(profil, SANS_CONVENTION), 2026, mois)
        apres = _empreinte(_apres_changement(profil), 2026, mois)
        assert apres == avant

    def test_le_mois_de_la_date_d_effet_change(self, profil):
        avant = _empreinte(_fiche(profil, SANS_CONVENTION), 2026, 11)
        apres = _empreinte(_apres_changement(profil), 2026, 11)
        assert apres != avant

    def test_la_fiche_du_generateur_et_celle_de_la_liste_ont_la_meme_empreinte(self, profil):
        """Le générateur hache la fiche du mois (déjà datée), la liste la fiche
        brute : même empreinte, sinon un bulletin tout juste fait serait périmé."""
        brute = _apres_changement(profil)
        for mois in (10, 11):
            du_mois = contrat_du_mois.fiche_du_mois(brute, 2026, mois)
            assert _empreinte(du_mois, 2026, mois) == _empreinte(brute, 2026, mois)

    def test_rattacher_syntec_a_la_societe_ne_touche_aucune_empreinte(self, profil):
        """La convention de la société n'est pas dans l'empreinte : la ligne
        datée de `company_collective_agreements` ne périme aucun bulletin."""
        employee = _fiche(profil, SANS_CONVENTION)
        assert _empreinte(employee, 2026, 10) == _empreinte(dict(employee), 2026, 10)


# --- Les deux générateurs passent la date du mois --------------------------


def test_les_deux_generateurs_lisent_la_convention_a_la_fin_du_mois():
    from app.modules.payroll.documents import (
        payslip_generator,
        payslip_generator_forfait,
    )

    for generer in (
        payslip_generator.process_payslip_generation,
        payslip_generator_forfait.process_payslip_generation_forfait,
    ):
        source = inspect.getsource(generer)
        assert "fiche_du_mois(employee_data, year, month, contract_period_id)" in source
        assert "a_la_date=fin_du_mois(year, month)" in source


def test_le_generateur_en_heures_ecrit_l_ancienne_classification_et_date_la_convention(
    monkeypatch, moteur  # noqa: F811
):
    """Calcul de septembre (avant le 01/11) d'un salarié en heures dont la fiche
    porte déjà Syntec datée : contrat.json garde l'ancienne classification, la
    convention se lit au 30/09."""
    from app.modules.payroll.documents import payslip_generator as pg
    from app.modules.payroll.documents import payslip_run_heures
    from app.modules.payroll.documents.bac_a_sable import BacASable
    from app.modules.schedules.infrastructure.arrets_valides import (
        arrets_valides_reader,
    )
    from tests.unit.payroll.test_filet_heures_sur_arret import EMP
    from tests.unit.payroll.test_filet_heures_sur_arret import _Base as _BaseFilet

    class _BaseDatee(_BaseFilet):
        def lire(self, table, colonnes):
            ligne = super().lire(table, colonnes)
            if table == "employees":
                return {
                    **ligne,
                    "classification_conventionnelle": dater_changement_classification(
                        SANS_CONVENTION, SYNTEC_CLASSIFICATION, EFFET
                    ),
                }
            return ligne

    vu: dict = {}

    def convention_espion(employee_row, company_row, **kwargs):
        vu["a_la_date"] = kwargs.get("a_la_date")
        return {}

    def run_espion(employee_path, *_a, **_k):
        vu["contrat"] = json.loads((employee_path / "contrat.json").read_text(encoding="utf-8"))
        return {"alertes_baremes": [], "salaire_brut": 0.0, "net_a_payer": 0.0}

    monkeypatch.setattr(pg, "build_convention_collective_payload", convention_espion)
    monkeypatch.setattr(payslip_run_heures, "run_payslip_generation_heures", run_espion)
    monkeypatch.setattr(pg, "supabase", _BaseDatee([], compensation=False))
    monkeypatch.setattr(arrets_valides_reader, "par_salarie", lambda *_a, **_k: {EMP: []})
    try:
        pg.process_payslip_generation(EMP, 2026, 9, bac_a_sable=BacASable())
    except Exception:  # noqa: BLE001 — seul ce que le calcul a lu compte ici
        pass

    assert vu["a_la_date"] == date(2026, 9, 30)
    classification = vu["contrat"]["remuneration"]["classification_conventionnelle"]
    assert classification["idcc"] == "9999"
    assert CLE_CLASSIFICATION_AVANT not in classification


# --- La mise à jour de la fiche pose la note -------------------------------


def test_la_mise_a_jour_datee_garde_l_ancienne_classification(monkeypatch):
    from app.modules.employees.application import commands

    monkeypatch.setattr(
        commands._employee_repository,
        "get_by_id_only",
        lambda _id: {"id": "emp-forfait", "company_id": SOCIETE, "classification_conventionnelle": SANS_CONVENTION},
    )
    update = {"classification_conventionnelle": dict(SYNTEC_CLASSIFICATION)}
    commands._avec_classification_datee("emp-forfait", update, EFFET)
    ecrite = update["classification_conventionnelle"]
    assert classification_du_mois(ecrite, 2026, 10) == SANS_CONVENTION
    assert classification_du_mois(ecrite, 2026, 11) == SYNTEC_CLASSIFICATION


def test_la_resolution_lit_toutes_les_lignes_sans_colonne_nommee():
    """`select *` : sans la migration des dates, la lecture ne casse pas."""
    source = inspect.getsource(idcc_resolution.company_agreement_id_a_la_date)
    assert '.select("*")' in source
