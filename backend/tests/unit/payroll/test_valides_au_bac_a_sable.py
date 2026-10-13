"""Un bulletin validé dont l'empreinte change est d'abord recalculé au bac à sable.

Rejeu final du 12/10 (A, C2) : poser le calendrier d'octobre faisait passer
« À recalculer » le bulletin validé de septembre, alors que son calcul ne
change pas (l'empreinte hache M-1, M et M+1 entiers). Choix du 12/10 : Martine
le recalcule d'abord au bac à sable, sans rien écrire. Identique au centime :
l'empreinte est remise à jour sans rien dire. Sinon : « À recalculer », en
disant ce qui change.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.payroll.application import empreinte_entrees_service as service
from app.modules.payroll.application.empreinte_entrees_service import (
    VerdictBacASable,
    annoter_a_recalculer,
    empreinte_des_lectures,
    poser_empreinte_complementaire_depuis_lectures,
)
from app.modules.payroll.domain.empreinte_entrees import (
    ecart_au_centime,
    empreinte_complementaire_stockee,
    empreinte_cumuls,
)
from app.modules.payroll.infrastructure.empreinte_entrees_queries import (
    Complements,
    LecturesEmpreinte,
)

pytestmark = pytest.mark.unit

SERVICE = "app.modules.payroll.application.empreinte_entrees_service"

EMPLOYEE = {
    "id": "e1",
    "company_id": "c1",
    "salaire_de_base": {"valeur": 2000},
    "duree_hebdomadaire": 35,
    "statut": "Non-Cadre",
    "is_forfait_jour": False,
    "hire_date": "2024-01-15",
}
COMPANY = {"id": "c1", "idcc": "292", "settings": {}}
CUMULS_AVRIL = {"cumuls": {"brut_total": 8000.0}}
CUMULS_MAI = {"cumuls": {"brut_total": 10000.0}}
CALENDRIERS = {
    (2026, 4): {
        "planned_calendar": {"calendrier_prevu": []},
        "actual_hours": {"calendrier_reel": []},
        "cumuls": CUMULS_AVRIL,
    },
    (2026, 5): {
        "planned_calendar": {"calendrier_prevu": [{"jour": 12, "type": "travail", "heures_prevues": 7}]},
        "actual_hours": {"calendrier_reel": [{"jour": 12, "type": "travail", "heures_faites": 7}]},
        "cumuls": CUMULS_MAI,
    },
    (2026, 6): {"planned_calendar": {"calendrier_prevu": []}, "actual_hours": {"calendrier_reel": []}},
}
#: Le calendrier de juin posé après la validation de mai.
JUIN_POSE = {
    **CALENDRIERS,
    (2026, 6): {
        "planned_calendar": {"calendrier_prevu": [{"jour": 1, "type": "travail", "heures_prevues": 7}]},
        "actual_hours": {"calendrier_reel": []},
    },
}
COMPLEMENTS = Complements(
    mutuelles=[],
    sorties=[],
    ajustements_conges=[],
    reglages_conges=None,
    conges_anciennete=None,
    historique_salaire=[],
    maintien=None,
    jei=None,
)


def _kwargs(**surcharges):
    base = dict(
        year=2026,
        month=5,
        calendriers=CALENDRIERS,
        absences=[],
        saisies=[],
        employee=EMPLOYEE,
        company=COMPANY,
        notes_de_frais=[],
    )
    base.update(surcharges)
    return base


def _lectures(**surcharges) -> LecturesEmpreinte:
    valeurs = dict(
        employee=EMPLOYEE,
        company=COMPANY,
        calendriers=CALENDRIERS,
        absences=[],
        saisies_par_mois={},
        notes_de_frais=[],
        complements=COMPLEMENTS,
    )
    valeurs.update(surcharges)
    return LecturesEmpreinte(**valeurs)


def _mai(status="valide"):
    """Le bulletin de mai tel que la génération le pose, puis validé."""
    with patch(f"{SERVICE}.lire_complements", return_value=COMPLEMENTS):
        data = poser_empreinte_complementaire_depuis_lectures({}, **_kwargs())
    return {
        "id": "b-mai",
        "year": 2026,
        "month": 5,
        "origine": "calcule",
        "status": status,
        "empreinte_entrees": empreinte_des_lectures(**_kwargs()),
        "empreinte_cumuls_precedents": empreinte_cumuls(CUMULS_AVRIL),
        "empreinte_complementaire": empreinte_complementaire_stockee(data),
    }


@pytest.fixture(autouse=True)
def _verdicts_oublies():
    service.oublier_les_verdicts()
    yield
    service.oublier_les_verdicts()


def _annoter(lectures, ligne, *, verdict, ecrit="2026-10-13T08:00:00+00:00"):
    with (
        patch(f"{SERVICE}.lire_lectures_salarie", return_value=lectures),
        patch(f"{SERVICE}.verifier_valide_au_bac_a_sable", return_value=verdict) as verifier,
        patch(f"{SERVICE}.poser_empreintes_verifiees", return_value=ecrit) as poser,
    ):
        annotee = annoter_a_recalculer("e1", [dict(ligne)])[0]
    return annotee, verifier, poser


# --- Le cas du rejeu : le mois suivant posé après la validation -----------------


def test_sans_le_bac_a_sable_le_valide_passerait_a_recalculer():
    """La règle d'avant, gardée quand Martine ne peut pas savoir (bac à sable en échec)."""
    ligne, verifier, poser = _annoter(_lectures(calendriers=JUIN_POSE), _mai(), verdict=None)
    verifier.assert_called_once()
    assert ligne["a_recalculer"] is True
    assert ligne["raison_a_recalculer"].startswith("Le planning a changé")
    poser.assert_not_called()


def test_identique_au_centime_l_empreinte_est_remise_a_jour_sans_rien_dire():
    ligne, verifier, poser = _annoter(
        _lectures(calendriers=JUIN_POSE), _mai(), verdict=VerdictBacASable(identique=True)
    )
    assert ligne["a_recalculer"] is False
    assert ligne["raison_a_recalculer"] is None
    # Le bac à sable part des cumuls d'avril, ceux que mai a lus.
    _, kwargs = verifier.call_args
    assert verifier.call_args.args[:3] == ("e1", 2026, 5)
    assert kwargs["cumuls_precedents"] == CUMULS_AVRIL
    assert kwargs["cumuls_du_mois"] == CUMULS_MAI
    # Les empreintes posées sont celles d'aujourd'hui.
    poser.assert_called_once()
    payslip_id, parametres, empreinte_lue = poser.call_args.args
    assert payslip_id == "b-mai"
    assert empreinte_lue == _mai()["empreinte_entrees"]
    assert parametres["empreinte_entrees"] == empreinte_des_lectures(**_kwargs(calendriers=JUIN_POSE))
    assert parametres["empreinte_complementaire"]["calendriers"] != _mai()["empreinte_complementaire"]["calendriers"]


def test_different_au_centime_il_reste_a_recalculer_en_disant_ce_qui_change():
    ecart = "Martine l'a recalculé sans rien enregistrer : le net à payer passerait de 1 500,00 € à 1 510,00 €."
    ligne, _, poser = _annoter(
        _lectures(calendriers=JUIN_POSE),
        _mai(),
        verdict=VerdictBacASable(identique=False, ecart=ecart),
    )
    assert ligne["a_recalculer"] is True
    assert ligne["raison_a_recalculer"].startswith("Le planning a changé")
    assert ligne["raison_a_recalculer"].endswith(ecart)
    poser.assert_not_called()


def test_un_meme_etat_n_est_recalcule_qu_une_fois():
    lectures = _lectures(calendriers=JUIN_POSE)
    verdict = VerdictBacASable(identique=False, ecart="Martine l'a recalculé : le brut change.")
    with (
        patch(f"{SERVICE}.lire_lectures_salarie", return_value=lectures),
        patch(f"{SERVICE}.verifier_valide_au_bac_a_sable", return_value=verdict) as verifier,
        patch(f"{SERVICE}.poser_empreintes_verifiees"),
    ):
        premiere = annoter_a_recalculer("e1", [_mai()])[0]
        seconde = annoter_a_recalculer("e1", [_mai()])[0]
    verifier.assert_called_once()
    assert premiere["raison_a_recalculer"] == seconde["raison_a_recalculer"]


# --- Ce qui n'est pas recalculé au bac à sable ----------------------------------


def test_un_brouillon_n_est_pas_recalcule_au_bac_a_sable():
    ligne, verifier, _ = _annoter(
        _lectures(calendriers=JUIN_POSE), _mai(status="brouillon"), verdict=VerdictBacASable(True)
    )
    verifier.assert_not_called()
    assert ligne["a_recalculer"] is True


def test_un_valide_a_jour_n_est_pas_recalcule():
    ligne, verifier, _ = _annoter(_lectures(), _mai(), verdict=VerdictBacASable(True))
    verifier.assert_not_called()
    assert ligne["a_recalculer"] is False


def test_un_valide_dont_le_mois_d_avant_a_ete_recalcule_reste_a_recalculer():
    """Ses cumuls de départ ont changé : c'est la chaîne, pas une entrée du mois."""
    avril_recalcule = {
        **JUIN_POSE,
        (2026, 4): {**CALENDRIERS[(2026, 4)], "cumuls": {"cumuls": {"brut_total": 8100.0}}},
    }
    ligne, verifier, _ = _annoter(
        _lectures(calendriers=avril_recalcule), _mai(), verdict=VerdictBacASable(True)
    )
    verifier.assert_not_called()
    assert ligne["a_recalculer"] is True


def test_l_etat_dans_la_chaine_suit_la_meme_regle():
    lignes = [_mai()]
    with (
        patch.object(service, "lire_empreintes_des_bulletins", return_value=lignes),
        patch.object(service, "lire_lectures_salarie", return_value=_lectures(calendriers=JUIN_POSE)),
        patch.object(service, "verifier_valide_au_bac_a_sable", return_value=VerdictBacASable(True)),
        patch.object(service, "poser_empreintes_verifiees", return_value="2026-10-13T08:00:00+00:00"),
    ):
        etat = service.etat_dans_la_chaine("e1", 2026, 5)
    assert etat.a_recalculer is False
    # L'écran du bulletin garde la date de la dernière écriture (pas de faux conflit).
    assert etat.bulletin_mis_a_jour_le == "2026-10-13T08:00:00+00:00"


# --- Le recalcul au bac à sable : rien n'est écrit ---------------------------------


def test_le_bac_a_sable_tourne_en_lecture_seule_et_compare_au_centime():
    from app.core.lecture_seule import ecritures_permises

    enregistre = {"salaire_brut": 2000.0, "net_a_payer": 1500.0}
    vus: list[bool] = []

    def bac_a_sable(employee_id, year, month, cumuls_precedents):
        vus.append(ecritures_permises())
        assert (employee_id, year, month, cumuls_precedents) == ("e1", 2026, 5, CUMULS_AVRIL)
        return {"payslip_data": dict(enregistre), "cumuls": CUMULS_MAI}

    with (
        patch(f"{SERVICE}.lire_bulletin_enregistre", return_value={"payslip_data": enregistre}),
        patch(f"{SERVICE}._calculer_au_bac_a_sable", side_effect=bac_a_sable),
    ):
        verdict = service.verifier_valide_au_bac_a_sable(
            "e1", 2026, 5, cumuls_precedents=CUMULS_AVRIL, cumuls_du_mois=CUMULS_MAI
        )
    assert vus == [False]
    assert verdict == VerdictBacASable(identique=True)


def test_un_bac_a_sable_en_echec_ne_dit_rien():
    with (
        patch(f"{SERVICE}.lire_bulletin_enregistre", return_value={"payslip_data": {"net_a_payer": 1}}),
        patch(f"{SERVICE}._calculer_au_bac_a_sable", side_effect=RuntimeError("refus")),
    ):
        assert (
            service.verifier_valide_au_bac_a_sable(
                "e1", 2026, 5, cumuls_precedents=None, cumuls_du_mois=None
            )
            is None
        )


# --- Identique au centime ------------------------------------------------------------

BULLETIN = {
    "salaire_brut": 2000.0,
    "net_a_payer": 1500.0,
    "calcul_du_brut": [
        {"libelle": "Salaire de base", "gain": 2000.0, "quantite": 151.67, "taux": 13.1866},
    ],
    "structure_cotisations": {
        "bloc_principales": [
            {"libelle": "Maladie", "montant_salarial": 0.0, "montant_patronal": 140.0},
            {"libelle": "Vieillesse", "montant_salarial": 138.0, "montant_patronal": 171.0},
        ],
        "total_salarial": 438.0,
    },
    "synthese_net": {"net_imposable": 1600.0, "impot_prelevement_a_la_source": {"montant": 100.0}},
    "pied_de_page": {"cout_total_employeur": 2900.0, "solde_conges": {"cp_n": 12.5}},
    "parametres": {"empreinte_entrees": "a"},
    "en_tete": {"date_generation": "2026-06-01"},
}


def test_le_meme_bulletin_est_identique_au_centime():
    recalcule = {
        **BULLETIN,
        # Un dixième de centime d'arrondi, l'ordre des lignes, un texte, une
        # empreinte, une date et un solde de congés ne sont pas des montants.
        "salaire_brut": 2000.0004,
        "structure_cotisations": {
            **BULLETIN["structure_cotisations"],
            "bloc_principales": list(reversed(BULLETIN["structure_cotisations"]["bloc_principales"])),
        },
        "calcul_du_brut": [{**BULLETIN["calcul_du_brut"][0], "explication": "nouveau texte"}],
        "pied_de_page": {"cout_total_employeur": 2900.0, "solde_conges": {"cp_n": 14.0}},
        "parametres": {"empreinte_entrees": "b"},
        "en_tete": {"date_generation": "2026-10-13"},
    }
    assert ecart_au_centime(BULLETIN, recalcule) is None
    assert ecart_au_centime(BULLETIN, recalcule, cumuls_stockes=CUMULS_MAI, cumuls_recalcules=CUMULS_MAI) is None


def test_les_retenues_d_apres_le_calcul_ne_comptent_pas():
    """Avances et saisies sont retenues après le moteur : le bac à sable ne les a pas."""
    enregistre = {
        **BULLETIN,
        "net_a_payer": 1400.0,
        "remboursements_avances": {"total_rembourse": 100.0},
    }
    assert ecart_au_centime(enregistre, BULLETIN) is None


def test_un_net_qui_change_est_dit_en_euros():
    recalcule = {**BULLETIN, "net_a_payer": 1510.0}
    assert ecart_au_centime(BULLETIN, recalcule) == (
        "Martine l'a recalculé sans rien enregistrer : le net à payer passerait "
        "de 1 500,00 € à 1 510,00 €."
    )


def test_un_brut_qui_change_est_dit_d_abord():
    recalcule = {**BULLETIN, "salaire_brut": 2050.5, "net_a_payer": 1540.0}
    assert ecart_au_centime(BULLETIN, recalcule) == (
        "Martine l'a recalculé sans rien enregistrer : le brut passerait "
        "de 2 000,00 € à 2 050,50 €."
    )


def test_une_cotisation_ou_un_cumul_qui_change_est_dit_aussi():
    recalcule = {
        **BULLETIN,
        "structure_cotisations": {**BULLETIN["structure_cotisations"], "total_salarial": 438.01},
    }
    attendu = (
        "Martine l'a recalculé sans rien enregistrer : des cotisations ou des cumuls "
        "changent, le brut et le net restent les mêmes."
    )
    assert ecart_au_centime(BULLETIN, recalcule) == attendu
    assert (
        ecart_au_centime(
            BULLETIN,
            BULLETIN,
            cumuls_stockes=CUMULS_MAI,
            cumuls_recalcules={"cumuls": {"brut_total": 10000.01}},
        )
        == attendu
    )


# --- L'écriture des empreintes : rien d'autre, et seulement sur le bulletin lu -------


class _Payslips:
    """La table `payslips` d'un seul bulletin, en mémoire."""

    def __init__(self, ligne):
        self.ligne = ligne
        self.ecrit = None
        self._maj = None

    def table(self, nom):
        assert nom == "payslips"
        return self

    def select(self, *_a, **_k):
        self._maj = None
        return self

    def update(self, valeurs):
        self._maj = valeurs
        return self

    def eq(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        from types import SimpleNamespace

        if self._maj is not None:
            self.ecrit = self._maj
            return SimpleNamespace(data=[{**self.ligne, **self._maj, "updated_at": "T1"}])
        return SimpleNamespace(data=[self.ligne])


def _poser(ligne, empreinte_lue="a"):
    from app.modules.payroll.infrastructure import empreinte_entrees_queries as q

    base = _Payslips(ligne)
    with patch.object(q, "supabase", base):
        rendu = q.poser_empreintes_verifiees("b-1", {"empreinte_entrees": "b"}, empreinte_lue)
    return rendu, base.ecrit


def test_poser_les_empreintes_ne_touche_que_les_parametres():
    ligne = {
        "status": "valide",
        "payslip_data": {"net_a_payer": 1500.0, "parametres": {"empreinte_entrees": "a", "smic_horaire": 12.02}},
    }
    rendu, ecrit = _poser(ligne)
    assert rendu == "T1"
    assert ecrit == {
        "payslip_data": {
            "net_a_payer": 1500.0,
            "parametres": {"empreinte_entrees": "b", "smic_horaire": 12.02},
        }
    }


def test_un_bulletin_recalcule_ou_plus_valide_entre_temps_n_est_pas_touche():
    recalcule = {"status": "valide", "payslip_data": {"parametres": {"empreinte_entrees": "z"}}}
    assert _poser(recalcule) == (None, None)
    brouillon = {"status": "brouillon", "payslip_data": {"parametres": {"empreinte_entrees": "a"}}}
    assert _poser(brouillon) == (None, None)


def test_une_lecture_ne_lance_que_quelques_bacs_a_sable_les_plus_recents_d_abord():
    """Une mutuelle modifiée change l'empreinte de tous les validés de l'année :
    une lecture en vérifie quelques-uns, les autres restent « À recalculer »."""
    lignes = []
    for mois in range(1, 7):
        lignes.append({**_mai(), "id": f"b-{mois}", "month": mois})
    lectures = _lectures(calendriers=JUIN_POSE)
    with (
        patch(f"{SERVICE}.lire_lectures_salarie", return_value=lectures),
        patch(f"{SERVICE}._a_verifier", return_value=True),
        patch(f"{SERVICE}.verifier_valide_au_bac_a_sable", return_value=None) as verifier,
    ):
        annoter_a_recalculer("e1", lignes)
    mois_verifies = [appel.args[2] for appel in verifier.call_args_list]
    assert mois_verifies == [6, 5, 4][: service.BAC_A_SABLE_PAR_LECTURE]
