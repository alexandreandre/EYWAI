"""[H7] « Prime de précarité non due », saisie au départ « Fin de CDD ».

Fiche service-public F40 « Fin d'un contrat à durée déterminée (CDD) »
(https://www.service-public.gouv.fr/particuliers/vosdroits/F40, vérifiée le
22/01/2024, ouverte le 12/10/2026) : « vous ne percevez pas d'indemnité de fin
de contrat dans les cas suivants : Embauche en CDI à l'issue du CDD (y compris
lorsque le CDD a été renouvelé) ; Refus d'un CDI proposé au salarié pour occuper
le même emploi ou un emploi similaire, avec une rémunération au moins
équivalente ; Faute grave ; Force majeure ; CDD d'usage ; Contrat aidé (contrat
unique d'insertion (CUI) - Parcours emploi compétences (PEC), contrat de
professionnalisation, contrat d'apprentissage) [...] ; Contrat pour lequel
l'employeur s'est engagé à assurer un complément de formation professionnelle
au salarié ; Contrat conclu avec un jeune pendant ses vacances scolaires ou
universitaires ; Contrat saisonnier ».

Code du travail (Code du travail numérique, code.travail.gouv.fr, ouvert le
12/10/2026) : L1243-8, l'indemnité est due « lorsque, à l'issue d'un contrat de
travail à durée déterminée, les relations contractuelles de travail ne se
poursuivent pas par un contrat à durée indéterminée » ; L1243-10, 4°, elle n'est
pas due « en cas de rupture anticipée du contrat due à l'initiative du salarié,
à sa faute grave ou à un cas de force majeure ».

Rien ne se saisissait à l'écran : seuls deux drapeaux de la fiche, posés en
base, écartaient la prime ; sinon elle restait au bulletin de sortie.
"""

from __future__ import annotations

import io
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError
from PyPDF2 import PdfReader

from app.modules.employee_exits.application import commands
from app.modules.employee_exits.application.dto import EmployeeExitApplicationError
from app.modules.employee_exits.schemas.requests import EmployeeExitCreate, EmployeeExitUpdate
from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.calcul_indemnites_sortie import calculer_indemnites_sortie
from app.modules.payroll.engine.precarite_non_due import (
    MOTIFS_PRECARITE_NON_DUE,
    mention_precarite_non_due,
)
from app.modules.payroll.solde_de_tout_compte import EmployeeExitDocumentGenerator
from app.modules.payroll.solde_de_tout_compte.cases import fin_cdd as recu_fin_cdd
from app.modules.payroll.solde_de_tout_compte.common import bulletin_de_sortie
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit

PRIME = "Prime de précarité (CDD)"


def test_les_motifs_sont_ceux_de_la_fiche_f40_et_la_rupture_anticipee_par_le_salarie():
    assert MOTIFS_PRECARITE_NON_DUE == {
        "embauche_cdi": "embauche en CDI à l'issue du CDD",
        "refus_cdi": (
            "refus d'un CDI proposé pour le même emploi ou un emploi similaire, "
            "avec une rémunération au moins équivalente"
        ),
        "rupture_anticipee_salarie": "rupture anticipée du CDD à l'initiative du salarié",
        "faute_grave": "faute grave",
        "force_majeure": "force majeure",
        "cdd_usage": "CDD d'usage",
        "contrat_aide": (
            "contrat aidé (CUI-PEC, contrat de professionnalisation, contrat d'apprentissage)"
        ),
        "complement_formation": (
            "contrat avec un complément de formation professionnelle assuré par l'employeur"
        ),
        "jeune_vacances": (
            "contrat conclu avec un jeune pendant ses vacances scolaires ou universitaires"
        ),
        "saisonnier": "contrat saisonnier",
    }


def test_la_mention_dit_le_motif_et_l_article():
    assert mention_precarite_non_due("refus_cdi") == (
        "Indemnité de fin de contrat (prime de précarité) non due : refus d'un CDI proposé "
        "pour le même emploi ou un emploi similaire, avec une rémunération au moins "
        "équivalente (Code du travail, art. L1243-10)."
    )
    assert mention_precarite_non_due("embauche_cdi").endswith(
        "embauche en CDI à l'issue du CDD (Code du travail, art. L1243-8)."
    )


def test_le_choix_se_saisit_a_la_creation_d_une_fin_de_cdd():
    depart = EmployeeExitCreate(
        employee_id="emp-1",
        exit_type="fin_cdd",
        exit_request_date="2026-10-01",
        last_working_day="2026-10-15",
        precarite_non_due="refus_cdi",
    )
    assert depart.precarite_non_due == "refus_cdi"
    assert commands.notes_du_dossier_a_la_creation("fin_cdd", depart.model_dump()) == {
        "precarite_non_due": "refus_cdi"
    }
    assert commands.notes_du_dossier_a_la_creation("demission", {"precarite_non_due": "refus_cdi"}) is None
    with pytest.raises(ValidationError):
        EmployeeExitCreate(
            employee_id="emp-1",
            exit_type="fin_cdd",
            exit_request_date="2026-10-01",
            last_working_day="2026-10-15",
            precarite_non_due="parce_que",
        )


def _mettre_a_jour(existant: dict, saisie: dict) -> tuple[dict, MagicMock]:
    with patch.object(commands, "EmployeeExitRepository") as depot, patch.object(
        commands, "get_employee_full", return_value={"id": "emp-1"}
    ), patch.object(commands, "get_indemnity_calculator") as calculateur:
        depot.return_value.get_by_id.return_value = existant
        depot.return_value.update.side_effect = lambda _id, _co, maj: {**existant, **maj}
        calculateur.return_value.calculate.return_value = {"indemnite_conges": {"jours_restants": 0}}
        maj = commands.update_employee_exit("exit-1", "co", saisie, supabase_client=MagicMock())
    return maj, calculateur


def test_le_choix_se_modifie_dans_l_onglet_indemnites_et_le_dossier_est_recalcule():
    existant = {
        "id": "exit-1",
        "employee_id": "emp-1",
        "exit_type": "fin_cdd",
        "status": "demission_recue",
        "exit_notes": {"autre": 1},
    }
    assert EmployeeExitUpdate(precarite_non_due="faute_grave").precarite_non_due == "faute_grave"

    maj, calculateur = _mettre_a_jour(existant, {"precarite_non_due": "faute_grave"})
    assert maj["exit_notes"] == {"autre": 1, "precarite_non_due": "faute_grave"}
    assert "precarite_non_due" not in {k for k in maj if k != "exit_notes"}
    assert "calculated_indemnities" in maj
    dossier_demande = calculateur.return_value.calculate.call_args[0][1]
    assert dossier_demande["exit_notes"]["precarite_non_due"] == "faute_grave"

    existant["exit_notes"] = {"autre": 1, "precarite_non_due": "faute_grave"}
    maj, _ = _mettre_a_jour(existant, {"precarite_non_due": None})
    assert maj["exit_notes"] == {"autre": 1}


def test_hors_fin_de_cdd_le_choix_est_refuse():
    existant = {"id": "exit-1", "employee_id": "emp-1", "exit_type": "demission", "exit_notes": {}}
    with pytest.raises(EmployeeExitApplicationError) as erreur:
        _mettre_a_jour(existant, {"precarite_non_due": "refus_cdi"})
    assert erreur.value.status_code == 400
    assert "fin de CDD" in erreur.value.detail


_ICCP = "app.modules.payroll.engine.calcul_indemnites_sortie.calculer_indemnite_conges_restants"


def _cdd() -> dict:
    return {
        "id": "emp-1",
        "hire_date": "2026-04-01",
        "contract_type": "CDD",
        "salaire_de_base": {"valeur": 2000.0},
        "specificites_paie": {"autre": True},
    }


def _fin_cdd(notes: dict | None = None) -> dict:
    return {
        "id": "exit-1",
        "exit_type": "fin_cdd",
        "exit_request_date": "2026-10-01",
        "last_working_day": "2026-10-15",
        "notice_period_days": 0,
        "notice_indemnity_type": "not_applicable",
        "exit_notes": notes or {},
    }


@patch(_ICCP, return_value={"montant": 300.0, "description": "ICCP", "details": {}})
def test_le_dossier_ecarte_la_prime_et_dit_pourquoi(iccp):
    dossier = calculer_indemnites_sortie(
        _cdd(), _fin_cdd({"precarite_non_due": "refus_cdi"}), MagicMock()
    )

    precarite = dossier["indemnite_precarite"]
    assert precarite["montant"] == 0.0
    assert precarite["non_due"] is True
    assert precarite["motif"] == "refus_cdi"
    assert precarite["versee_au_bulletin"] is False
    assert precarite["calcul"] == mention_precarite_non_due("refus_cdi")
    # L'indemnité de congés s'estime sans la prime (pas d'assiette gonflée).
    salarie_du_calcul = iccp.call_args[0][0]
    assert salarie_du_calcul["specificites_paie"] == {"autre": True, "exclure_prime_precarite": True}
    assert dossier["total_gross_indemnities"] == 300.0


@patch(_ICCP, return_value={"montant": 300.0, "description": "ICCP", "details": {"prime_precarite_incluse": 600.0}})
def test_sans_choix_le_dossier_ne_change_pas(_iccp):
    precarite = calculer_indemnites_sortie(_cdd(), _fin_cdd(), MagicMock())["indemnite_precarite"]
    assert precarite["montant"] == 600.0
    assert precarite["versee_au_bulletin"] is True
    assert "non_due" not in precarite


def _gains_du_bulletin_de_sortie(dossier: dict | None) -> dict:
    ctx = build_test_contexte(
        salaire_base=2200.0,
        type_contrat="CDD",
        date_entree="2025-10-01",
        date_fin_contrat="2026-04-30",
        cumuls={"brut_total": 8800.0},
        specificites_extra={"dsn_reprise": {"motif_recours": "02"}},
    )
    ctx.exit_indemnities = dossier
    res = calculer_salaire_brut(ctx, [], date(2026, 4, 1), date(2026, 4, 30), [])
    return {l["libelle"]: l["gain"] for l in res["lignes_composants_brut"] if l.get("gain")}


def test_le_bulletin_de_sortie_ne_verse_pas_la_prime_non_due():
    assert _gains_du_bulletin_de_sortie(None)[PRIME] == pytest.approx(1100.0, abs=0.01)

    gains = _gains_du_bulletin_de_sortie(
        {"indemnite_precarite": {"montant": 0.0, "non_due": True, "motif": "refus_cdi"}}
    )
    assert PRIME not in gains
    # L'indemnité de congés reste due, sur un brut sans précarité.
    iccp = next(v for k, v in gains.items() if "compensatrice de congés" in k)
    assert iccp == pytest.approx(1100.0, abs=0.05)


def _bulletin_de_sortie() -> dict:
    return {
        "salaire_brut": 1000.0,
        "net_a_payer": 780.0,
        "calcul_du_brut": [{"libelle": "Salaire de base", "gain": 1000.0}],
    }


def test_le_recu_tire_du_bulletin_le_dit():
    with patch.object(bulletin_de_sortie, "render_solde_tout_compte_html", return_value=b"pdf") as rendu:
        bulletin_de_sortie.generate_solde_depuis_bulletin(
            {}, {}, _fin_cdd({"precarite_non_due": "faute_grave"}), _bulletin_de_sortie()
        )
    mention = rendu.call_args.kwargs["specific_mention"]
    assert mention.startswith("Sommes versées avec le bulletin de paie de 10/2026.")
    assert mention_precarite_non_due("faute_grave") in mention

    with patch.object(bulletin_de_sortie, "render_solde_tout_compte_html", return_value=b"pdf") as rendu:
        bulletin_de_sortie.generate_solde_depuis_bulletin({}, {}, _fin_cdd(), _bulletin_de_sortie())
    assert rendu.call_args.kwargs["specific_mention"] == "Sommes versées avec le bulletin de paie de 10/2026."


def test_le_recu_estime_sans_bulletin_le_dit():
    section_vide = {"type": "amounts", "title": "", "rows": []}
    with patch.object(
        recu_fin_cdd.socle_commun, "compute_remunerations_section", return_value=(section_vide, 0.0, 0.0, 0.0)
    ), patch.object(
        recu_fin_cdd.socle_commun, "compute_conges_section", return_value=(section_vide, 0.0)
    ), patch.object(recu_fin_cdd, "render_solde_tout_compte_html", return_value=b"pdf") as rendu:
        recu_fin_cdd.generate_fin_cdd_solde(
            {},
            {},
            {},
            _fin_cdd({"precarite_non_due": "embauche_cdi"}),
            {"indemnite_precarite": {"montant": 0.0, "non_due": True, "motif": "embauche_cdi"}},
        )
    kwargs = rendu.call_args.kwargs
    ligne = kwargs["sections"][1]["rows"][0]
    assert ligne["montant"] is None
    assert ligne["detail"] == mention_precarite_non_due("embauche_cdi")
    assert mention_precarite_non_due("embauche_cdi") in kwargs["specific_mention"]


def test_l_attestation_france_travail_le_dit():
    historique = {"month_count": 12, "months": [], "primes_lines": [], "sommes_de_rupture": []}
    with patch(
        "app.modules.payroll.documents.attestation_employeur_generator.get_salary_history",
        return_value=historique,
    ):
        pdf = EmployeeExitDocumentGenerator().generate_attestation_pole_emploi(
            {"id": "emp-1", "first_name": "Jeanne", "last_name": "Essai"},
            {"company_name": "Société QA"},
            _fin_cdd({"precarite_non_due": "refus_cdi"}),
            indemnities={},
        )
    texte = " ".join(" ".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages).split())
    assert "prime de précarité) non due : refus d'un CDI proposé" in texte
    assert "art. L1243-10" in texte
