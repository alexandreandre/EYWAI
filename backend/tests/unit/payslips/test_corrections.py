"""Corriger un bulletin = écrire ses variables du mois, puis le recalculer.

Audit du 28/09 : l'écran enregistrait le bulletin retouché tel quel. Un montant
retouché laissait cotisations, net et cumuls faux ; ramener les heures sup à
zéro ne recalculait rien ; un échec du recalcul passait inaperçu.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from app.modules.payslips.application import corrections as mod
from app.modules.payslips.application.dto import (
    CorrigerBulletinInput,
    PayslipBadRequestError,
    PayslipConflictError,
)
from app.modules.payslips.domain.corrections import CorrectionsBulletin
from app.modules.payslips.domain.heures_sup import (
    LIBELLE_HS_DECLAREES,
    LIBELLE_HS_DECLAREES_50,
)
from app.modules.payslips.domain.primes_editees import DiffPrimes
from app.modules.payslips.schemas.requests import PayslipEditRequest

pytestmark = pytest.mark.unit

MAJ = "2026-09-28T09:00:00.123456+00:00"
BULLETIN = {
    "id": "ps-1",
    "employee_id": "emp-1",
    "company_id": "comp-1",
    "year": 2026,
    "month": 8,
    "status": "brouillon",
    "updated_at": MAJ,
    "url": "https://pdf/ancien",
    "payslip_data": {"salaire_brut": 2000.0},
    "pdf_notes": None,
    "internal_notes": [],
    "edit_history": [{"version": 3}],
}


class FauxClient:
    """Enregistre chaque écriture : (table, opération, valeur, filtres)."""

    def __init__(self) -> None:
        self.ecritures: list[tuple] = []

    def table(self, nom: str) -> "_Requete":
        return _Requete(self, nom)

    def de(self, table: str, operation: str) -> list[tuple]:
        return [e for e in self.ecritures if e[0] == table and e[1] == operation]


class _Requete:
    def __init__(self, client: FauxClient, table: str) -> None:
        self.client, self.nom, self.op, self.valeur, self.filtres = client, table, None, None, []

    def insert(self, valeur):
        self.op, self.valeur = "insert", valeur
        return self

    def update(self, valeur):
        self.op, self.valeur = "update", valeur
        return self

    def delete(self):
        self.op = "delete"
        return self

    def eq(self, cle, valeur):
        self.filtres.append((cle, valeur))
        return self

    def match(self, valeurs):
        self.filtres.extend(sorted(valeurs.items()))
        return self

    def in_(self, cle, valeurs):
        self.filtres.append((cle, tuple(valeurs)))
        return self

    def execute(self):
        self.client.ecritures.append((self.nom, self.op, self.valeur, tuple(self.filtres)))
        return MagicMock(data=[])


@pytest.fixture
def base():
    client = FauxClient()
    etat = {"bulletin": dict(BULLETIN)}
    with (
        patch.object(mod, "supabase", client),
        patch.object(mod, "_lire_bulletin", side_effect=lambda _id: dict(etat["bulletin"])),
        patch.object(mod, "_relire_en_entier", side_effect=lambda _id: dict(etat["bulletin"])),
        patch.object(mod, "_refuser_si_importe"),
        patch.object(mod, "verifier_appartenance"),
        patch.object(mod, "reimprimer_bulletin") as reimprimer,
        patch.object(mod, "generate_payslip") as generer,
    ):
        generer.return_value = MagicMock(status="success")
        client.generer, client.reimprimer, client.etat = generer, reimprimer, etat
        yield client


def _corriger(corrections=CorrectionsBulletin(), **kwargs):
    return mod.corriger_bulletin(
        CorrigerBulletinInput(
            payslip_id="ps-1",
            corrections=corrections,
            current_user_id="rh-1",
            current_user_name="RH",
            **kwargs,
        )
    )


# --- La requête : des corrections, jamais un bulletin ---


def test_un_bulletin_retouche_n_est_plus_accepte():
    with pytest.raises(ValidationError):
        PayslipEditRequest(payslip_data={"salaire_brut": 1}, changes_summary="x")


def test_declarer_et_revenir_au_planning_se_contredisent():
    with pytest.raises(ValidationError):
        PayslipEditRequest(
            corrections={"heures_sup": {"hs25": 4, "hs50": 0}, "revenir_au_planning": True}
        )


def test_une_prime_ajoutee_n_accepte_aucun_champ_de_rattachement():
    with pytest.raises(ValidationError):
        PayslipEditRequest(
            corrections={"primes_ajoutees": [{"name": "Prime", "amount": 10, "employee_id": "x"}]}
        )


def test_la_requete_se_traduit_en_corrections_du_domaine():
    requete = PayslipEditRequest(
        corrections={
            "heures_sup": {"hs25": 4, "hs50": 1.5},
            "primes_ajoutees": [{"name": "Prime", "amount": 10.005}],
            "primes_corrigees": [{"saisie_id": "s-1", "amount": 150}],
            "primes_retirees": ["s-2", "s-2"],
        }
    )
    c = requete.corrections.vers_domaine()
    assert c.heures_sup == (4.0, 1.5)
    assert c.primes.ajoutees[0]["name"] == "Prime"
    assert c.primes.modifiees == (("s-1", 150.0),)
    assert c.primes.retirees == ("s-2",)


# --- Heures sup ---


def test_declarer_les_heures_sup_les_ecrit_puis_regenere_une_fois(base):
    resultat = _corriger(CorrectionsBulletin(heures_sup=(4.0, 0.0)))

    supprimees = base.de("monthly_inputs", "delete")
    assert supprimees and ("name", (LIBELLE_HS_DECLAREES, LIBELLE_HS_DECLAREES_50)) in supprimees[0][3]
    (inserees,) = base.de("monthly_inputs", "insert")
    lignes = {l["name"]: l for l in inserees[2]}
    assert lignes[LIBELLE_HS_DECLAREES]["payroll_quantity"] == 4.0
    assert lignes[LIBELLE_HS_DECLAREES_50]["payroll_quantity"] == 0.0
    assert all(l["manual_override"] and l["employee_id"] == "emp-1" and l["month"] == 8 for l in lignes.values())

    base.generer.assert_called_once()
    entree = base.generer.call_args.args[0]
    assert (entree.employee_id, entree.year, entree.month) == ("emp-1", 2026, 8)
    assert entree.force_calendrier_incomplet and entree.regenerer_bulletin_valide
    assert entree.motif == "Heures sup 4 h à 25 % et 0 h à 50 %"
    assert resultat["recalcule"] is True and resultat["recalcul_erreur"] is None


def test_ramener_les_heures_a_zero_est_une_vraie_declaration(base):
    _corriger(CorrectionsBulletin(heures_sup=(0.0, 0.0)))
    (inserees,) = base.de("monthly_inputs", "insert")
    assert [l["payroll_quantity"] for l in inserees[2]] == [0.0, 0.0]
    base.generer.assert_called_once()


def test_revenir_au_planning_retire_les_seules_declarations_du_bulletin(base):
    _corriger(CorrectionsBulletin(revenir_au_planning=True))
    (supprimee,) = base.de("monthly_inputs", "delete")
    assert ("name", (LIBELLE_HS_DECLAREES, LIBELLE_HS_DECLAREES_50)) in supprimee[3]
    assert not base.de("monthly_inputs", "insert")
    base.generer.assert_called_once()


def test_la_regeneration_se_fait_sous_le_verrou_du_mois(base, verrous_de_generation):
    vus = []
    base.generer.side_effect = lambda *_: vus.append(set(verrous_de_generation.tenus)) or MagicMock(status="success")
    _corriger(CorrectionsBulletin(heures_sup=(4.0, 0.0)))
    assert vus == [{("emp-1", 2026, 8)}]
    assert not verrous_de_generation.tenus


# --- Primes ---


def test_les_primes_passent_par_les_variables_du_mois(base):
    primes = DiffPrimes(
        ajoutees=({"name": "Prime", "amount": 50.0},),
        modifiees=(("s-1", 150.0),),
        retirees=("s-2",),
    )
    with patch.object(mod, "appliquer_primes_editees") as appliquer:
        _corriger(CorrectionsBulletin(primes=primes))
    appliquer.assert_called_once_with(
        primes, employee_id="emp-1", company_id="comp-1", year=2026, month=8
    )
    mod.verifier_appartenance.assert_called_once_with(
        {"s-1", "s-2"}, employee_id="emp-1", company_id="comp-1", year=2026, month=8
    )
    base.generer.assert_called_once()


def test_une_prime_d_une_autre_fiche_ne_laisse_aucune_trace(base):
    mod.verifier_appartenance.side_effect = PayslipBadRequestError("inconnue")
    with pytest.raises(PayslipBadRequestError):
        _corriger(CorrectionsBulletin(primes=DiffPrimes(retirees=("s-9",))))
    assert base.ecritures == []
    base.generer.assert_not_called()


# --- Gardes ---


def test_un_bulletin_modifie_depuis_son_ouverture_est_refuse(base):
    with pytest.raises(PayslipConflictError):
        _corriger(
            CorrectionsBulletin(heures_sup=(4.0, 0.0)),
            base_updated_at="2026-09-28T08:00:00+00:00",
        )
    assert base.ecritures == []


def test_le_meme_instant_ecrit_autrement_n_est_pas_un_conflit(base):
    base.etat["bulletin"]["updated_at"] = "2026-09-28T09:00:00+00:00"
    _corriger(CorrectionsBulletin(heures_sup=(4.0, 0.0)), base_updated_at="2026-09-28T09:00:00Z")
    base.generer.assert_called_once()


def test_rien_a_enregistrer_est_refuse(base):
    with pytest.raises(PayslipBadRequestError):
        _corriger(pdf_notes="")
    assert base.ecritures == []


def test_un_bulletin_importe_est_refuse_avant_toute_ecriture(base):
    mod._refuser_si_importe.side_effect = PayslipBadRequestError("repris")
    with pytest.raises(PayslipBadRequestError):
        _corriger(CorrectionsBulletin(heures_sup=(4.0, 0.0)))
    assert base.ecritures == []


def test_un_bulletin_valide_repasse_en_brouillon_avant_les_variables(base):
    base.etat["bulletin"]["status"] = "valide"
    ordre = []
    with patch.object(
        mod, "_set_payslip_status_brouillon", side_effect=lambda _id: ordre.append("brouillon")
    ):
        base.generer.side_effect = lambda *_: ordre.append("recalcul") or MagicMock(status="success")
        _corriger(CorrectionsBulletin(heures_sup=(4.0, 0.0)))
    assert ordre == ["brouillon", "recalcul"]


# --- Échec du recalcul ---


def test_un_recalcul_en_echec_est_dit_et_marque_sur_le_bulletin(base):
    base.generer.side_effect = RuntimeError("Barème introuvable")
    resultat = _corriger(CorrectionsBulletin(heures_sup=(4.0, 0.0)))

    assert resultat["recalcule"] is False
    assert resultat["recalcul_erreur"] == "Barème introuvable"
    # Les variables restent écrites : elles sont la vérité.
    assert base.de("monthly_inputs", "insert")
    (marque,) = [
        e for e in base.de("payslips", "update") if "payslip_data" in (e[2] or {})
    ]
    assert marque[2]["payslip_data"]["recalcul_en_attente"]["erreur"] == "Barème introuvable"
    assert marque[2]["payslip_data"]["salaire_brut"] == 2000.0


def test_un_resultat_en_erreur_compte_comme_un_echec(base):
    base.generer.return_value = MagicMock(status="error", message="Calendrier illisible")
    resultat = _corriger(CorrectionsBulletin(heures_sup=(4.0, 0.0)))
    assert resultat["recalcul_erreur"] == "Calendrier illisible"


# --- Notes ---


def test_seule_la_note_change_le_pdf_est_reimprime_sans_recalcul(base):
    ordre = []
    base.reimprimer.side_effect = lambda _id: ordre.append("reimprime")
    with patch.object(mod, "archiver_version", side_effect=lambda *a, **k: ordre.append("archive")) as archiver:
        resultat = _corriger(pdf_notes="Prime versée en septembre")

    base.generer.assert_not_called()
    base.reimprimer.assert_called_once_with("ps-1")
    assert ordre == ["archive", "reimprime"]
    assert archiver.call_args.kwargs == {
        "edited_by": "rh-1",
        "edited_by_name": "RH",
        "changes_summary": "Notes modifiées",
        "action": "notes",
    }
    mises_a_jour = [e[2] for e in base.de("payslips", "update")]
    assert {"pdf_notes": "Prime versée en septembre"} in mises_a_jour
    assert resultat["recalcule"] is False and resultat["recalcul_erreur"] is None


def test_une_note_interne_seule_ne_touche_pas_au_pdf(base):
    _corriger(internal_note="Vu avec la salariée")
    base.generer.assert_not_called()
    base.reimprimer.assert_not_called()
    (maj,) = base.de("payslips", "update")
    (note,) = maj[2]["internal_notes"]
    assert note["content"] == "Vu avec la salariée" and note["author_id"] == "rh-1"


def test_le_resume_ecrit_par_la_rh_part_dans_l_historique(base):
    _corriger(CorrectionsBulletin(heures_sup=(4.0, 0.0)), changes_summary="Heures du 12 non faites")
    assert base.generer.call_args.args[0].motif == "Heures du 12 non faites"
