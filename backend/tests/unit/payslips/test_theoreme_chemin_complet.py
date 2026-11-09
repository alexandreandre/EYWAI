"""Le théorème joué sur le vrai chemin de la correction (R-181, R-183).

Le script du théorème injecte ses corrections en mémoire : il ne passe ni par
`corriger_bulletin`, ni par `monthly_inputs`, ni par l'historique, et il ne lit
de la DSN et de l'OD qu'un mapping et un résidu. Ici, tout est réel sauf la base
et l'imprimeur :

- `corriger_bulletin` et `restaurer_version`, sans doublure ;
- `generate_payslip` et le générateur, qui relisent les saisies dans la base
  en mémoire, et le moteur (`run_payslip_generation_heures`), sur des barèmes
  figés ;
- `build_parsed_dsn_from_payroll` pour la DSN complète, le registre comptable et
  `controler()` pour l'OD complète.

Le faux : la base (`BaseEnMemoire`), le stockage et l'imprimeur PDF (rien n'est
lu de leur contenu), plus les doublures communes de `tests/unit/conftest.py`
(verrou SQL en mémoire, effets du bulletin sur les prêts et avances, arrêts
validés). Chaque valeur attendue est calculée à part, depuis les taux, jamais
en comparant deux calculs du moteur.

Aucun montant de client : deux salariés fictifs, une société fictive.
"""

from __future__ import annotations

import calendar
import copy
from dataclasses import dataclass
from datetime import date
from typing import Any

import pytest

from app.core import database
from app.modules.dsn_export.application.builder import build_parsed_dsn_from_payroll
from app.modules.dsn_export.domain.writer import encode_dsn_bytes
from app.modules.dsn_import.application.cumuls import extract_monthly_totals
from app.modules.dsn_import.domain.parser import parse_dsn_content
from app.modules.exports.domain.accounting_plan import resolve_organisme_from_coti_id
from app.modules.exports.domain.controle_comptable import controler
from app.modules.exports.infrastructure.export_ecritures_comptables import (
    generate_od_globale,
    get_payslip_data_for_od,
)
from app.modules.exports.infrastructure.payroll_ledger import build_payroll_ledger
from app.modules.payroll.documents import payslip_run_heures, pdf_du_bulletin
from app.modules.payroll.documents.verrou_generation import GenerationDejaEnCours
from app.modules.payroll.engine.corrections_du_bulletin import (
    corrections_du_bulletin,
    lignes_corrigeables,
)
from app.modules.payroll.engine.corrections_manuelles import (
    CorrectionDeLigne,
    RegularisationCotisation,
    regularisations_du_bulletin,
)
from app.modules.payslips.application import commands, suite_du_bulletin
from app.modules.payslips.application.corrections import (
    corriger_bulletin,
    restaurer_version,
)
from app.modules.payslips.application.dto import (
    CorrigerBulletinInput,
    GeneratePayslipInput,
    PayslipBadRequestError,
    PayslipConflictError,
    RestorePayslipInput,
    UserContext,
)
from app.modules.payslips.application.service import edit_payslip_for_user
from app.modules.payslips.domain.coherence import raisons_de_ne_pas_valider
from app.modules.payslips.domain.corrections import CorrectionsBulletin
from tests.unit.base_en_memoire import BaseEnMemoire
from tests.unit.payroll.test_annee_des_baremes import _baremes

pytestmark = pytest.mark.unit

ANNEE, MOIS, SUIVANT = 2026, 10, 11
SOCIETE = "societe-fictive"
SALARIE, COLLEGUE = "salarie-a", "salarie-b"
SALAIRE, SALAIRE_COLLEGUE = 2500.0, 2200.0
HEURES = 151.67
TAUX_HORAIRE = 16.4832
TAUX_PAS = 0.05
PLAFOND_SECU = 4005.0

VIEILLESSE_PLAFONNEE = (0.069, 0.0855)
VIEILLESSE_DEPLAFONNEE = (0.004, 0.0202)
MALADIE, ALLOCATIONS, FNAL, CHOMAGE = 0.07, 0.0525, 0.001, 0.0405
CSG_DEDUCTIBLE, CSG_NON_DEDUCTIBLE, CRDS = 0.068, 0.029, 0.005
ABATTEMENT_CSG = 0.9825


SMIC_HORAIRE = 12.31
REDUCTION_TMIN, REDUCTION_TDELTA, REDUCTION_P, REDUCTION_POINT_SORTIE = 0.02, 0.3781, 1.75, 3.0


def _r(valeur: float) -> float:
    return round(valeur + 1e-9, 2)


def _reduction(brut: float, heures: float) -> float:
    """La réduction générale du mois, à part : le coefficient dépend du salaire
    rapporté au SMIC des heures. Corriger les heures au taux horaire le laisse
    donc inchangé ; un autre salaire le change."""
    rapport = REDUCTION_POINT_SORTIE * SMIC_HORAIRE * heures / brut
    coefficient = REDUCTION_TMIN + REDUCTION_TDELTA * (0.5 * (rapport - 1)) ** REDUCTION_P
    return -_r(brut * round(coefficient, 4))


def attendu(
    brut: float = SALAIRE,
    *,
    heures: float = HEURES,
    base_vieillesse: float | None = None,
    regularisation: float = 0.0,
) -> dict[str, Any]:
    """Le bulletin, calculé à part, depuis les seuls taux.

    `base_vieillesse` : l'assiette de la vieillesse plafonnée quand elle est
    corrigée. `regularisation` : la base d'une régularisation de vieillesse
    plafonnée, ligne à part.
    """
    assiette = brut if base_vieillesse is None else base_vieillesse
    vieillesse_sal, vieillesse_pat = _r(assiette * VIEILLESSE_PLAFONNEE[0]), _r(assiette * VIEILLESSE_PLAFONNEE[1])
    regul_sal, regul_pat = _r(regularisation * VIEILLESSE_PLAFONNEE[0]), _r(regularisation * VIEILLESSE_PLAFONNEE[1])
    deplaf_sal, deplaf_pat = _r(brut * VIEILLESSE_DEPLAFONNEE[0]), _r(brut * VIEILLESSE_DEPLAFONNEE[1])
    base_csg = _r(brut * ABATTEMENT_CSG)
    csg_ded, csg_nd = _r(base_csg * CSG_DEDUCTIBLE), _r(base_csg * CSG_NON_DEDUCTIBLE)
    crds = _r(base_csg * CRDS)
    maladie, alloc, fnal, chomage = _r(brut * MALADIE), _r(brut * ALLOCATIONS), _r(brut * FNAL), _r(brut * CHOMAGE)
    reduction = _reduction(brut, heures)

    salarial = _r(vieillesse_sal + regul_sal + deplaf_sal + csg_ded + csg_nd)
    patronal = _r(vieillesse_pat + regul_pat + deplaf_pat + maladie + alloc + fnal + chomage + reduction)
    net_imposable = _r(brut - salarial + csg_nd)
    pas = _r(net_imposable * TAUX_PAS)
    return {
        "brut": brut,
        "heures": heures,
        "salarial": salarial,
        "patronal": patronal,
        "net_imposable": net_imposable,
        "pas": pas,
        "net": _r(brut - salarial - pas),
        "reduction": reduction,
        "bases": {
            "02": _r(assiette + regularisation),
            "03": _r(brut),
            "04": base_csg,
            "07": _r(brut),
        },
        "cotisations": {
            ("076", "02"): (_r(assiette + regularisation), _r(vieillesse_sal + vieillesse_pat + regul_sal + regul_pat)),
            ("049", "02"): (_r(brut), fnal),
            ("076", "03"): (_r(brut), _r(deplaf_sal + deplaf_pat)),
            ("075", "03"): (_r(brut), maladie),
            ("074", "03"): (_r(brut), _r(brut * 0.0345)),
            ("102", "03"): (_r(brut), _r(alloc - _r(brut * 0.0345))),
            # 9,20 % : 6,80 % et 2,40 %, chaque fraction arrondie (`_csg_et_crds`).
            ("072", "04"): (base_csg, _r(csg_ded + _r(base_csg * 0.024))),
            ("079", "04"): (base_csg, crds),
            ("040", "07"): (_r(brut), chomage),
        },
    }


COLLEGUE_ATTENDU = attendu(SALAIRE_COLLEGUE)
DEPART = attendu()
GAIN_CORRIGE_BRUT = _r(160.0 * TAUX_HORAIRE)


@dataclass(frozen=True)
class Cas:
    nom: str
    corrections: CorrectionsBulletin
    apres: dict[str, Any]

    def retrait(self, saisie_id: str) -> CorrectionsBulletin:
        if self.corrections.regularisations_ajoutees:
            return CorrectionsBulletin(regularisations_retirees=(saisie_id,))
        return CorrectionsBulletin(corrections_retirees=(saisie_id,))


CAS = [
    Cas(
        "gain_corrige",
        CorrectionsBulletin(
            corrections_ajoutees=(
                CorrectionDeLigne(ligne="brut:salaire_base", libelle="Salaire de base", motif="Heures réelles", base=160.0),
            )
        ),
        attendu(GAIN_CORRIGE_BRUT, heures=160.0),
    ),
    Cas(
        "cotisation_corrigee",
        CorrectionsBulletin(
            corrections_ajoutees=(
                CorrectionDeLigne(
                    ligne="cotisation:vieillesse_plafonnee",
                    libelle="Vieillesse plafonnée",
                    motif="Assiette du contrat",
                    base=2600.0,
                ),
            )
        ),
        attendu(base_vieillesse=2600.0),
    ),
    Cas(
        "regularisation",
        CorrectionsBulletin(
            regularisations_ajoutees=(
                RegularisationCotisation(
                    coti_id="vieillesse_plafonnee",
                    libelle="Vieillesse plafonnée",
                    motif="Oubli du mois précédent",
                    base=100.0,
                    taux_salarial=VIEILLESSE_PLAFONNEE[0],
                    taux_patronal=VIEILLESSE_PLAFONNEE[1],
                ),
            )
        ),
        attendu(regularisation=100.0),
    ),
]
PARAMETRES = pytest.mark.parametrize("cas", CAS, ids=[c.nom for c in CAS])


# --- Le monde fictif -------------------------------------------------------------


def _calendrier(mois: int) -> tuple[dict, dict]:
    prevu, reel = [], []
    for jour in range(1, calendar.monthrange(ANNEE, mois)[1] + 1):
        travaille = date(ANNEE, mois, jour).weekday() < 5
        prevu.append({"jour": jour, "type": "travail" if travaille else "repos", "heures_prevues": 7.0 if travaille else 0.0})
        reel.append({"jour": jour, "heures_faites": 7.0 if travaille else 0.0})
    return {"calendrier_prevu": prevu}, {"calendrier_reel": reel}


def _fiche(employe: str, salaire: float, nir: str) -> dict[str, Any]:
    return {
        "id": employe,
        "company_id": SOCIETE,
        "first_name": "Prenom",
        "last_name": f"Fictif {employe}",
        "employee_folder_name": f"fictif_{employe}",
        "matricule": employe,
        "nir": nir,
        "sexe": "M",
        "date_naissance": "1985-01-15",
        "lieu_naissance": "PARIS",
        "coordonnees_bancaires": {"iban": "FR7630006000011234567890189", "bic": "FICTFRPP"},
        "hire_date": "2020-01-01",
        "statut": "Non-Cadre",
        "contract_type": "CDI",
        "duree_hebdomadaire": 35,
        "salaire_de_base": {"valeur": salaire},
        "pcs": "389a",
        "idcc": "1486",
        "job_title": "Technicien",
        "specificites_paie": {"prelevement_a_la_source": {"taux": TAUX_PAS * 100, "is_personnalise": True}},
        "adresse": {"rue": "1 RUE FICTIVE", "code_postal": "39100", "ville": "DOLE"},
        "is_forfait_jour": False,
    }


class _Imprimeur:
    def __init__(self, *_a: Any, **_k: Any) -> None:
        pass

    def write_pdf(self, chemin: Any, *_a: Any, **_k: Any) -> None:
        with open(chemin, "wb") as fichier:
            fichier.write(b"%PDF-fictif")


class _Stockage:
    def __init__(self) -> None:
        self.deposes: list[str] = []
        self.copies: list[tuple[str, str]] = []
        self.retires: list[str] = []

    def from_(self, _bucket: str) -> _Stockage:
        return self

    def upload(self, path: str, **_k: Any) -> dict:
        self.deposes.append(path)
        return {}

    def create_signed_url(self, chemin: str, *_a: Any, **_k: Any) -> dict:
        return {"signedURL": f"https://stockage.invalid/{chemin}"}

    def copy(self, source: str, destination: str) -> dict:
        self.copies.append((source, destination))
        return {}

    def remove(self, chemins: list[str]) -> list:
        self.retires.extend(chemins)
        return []


def _baremes_de_paie() -> dict:
    """Les barèmes figés, sans le doublon de vieillesse, au taux légal de CSG/CRDS."""
    baremes = _baremes()
    vues: set[str] = set()
    uniques = []
    for ligne in baremes["cotisations"]["cotisations"]:
        if ligne["id"] in vues:
            continue
        vues.add(ligne["id"])
        uniques.append({**ligne, "salarial": CSG_NON_DEDUCTIBLE} if ligne["id"] == "csg_non_deductible" else ligne)
    uniques.append({"id": "assurance_chomage", "libelle": "Assurance chômage", "base": "brut", "salarial": None, "patronal": CHOMAGE})
    baremes["cotisations"]["cotisations"] = uniques
    return baremes


class Paie:
    """La paie du mois, sur la base en mémoire, par ses vraies portes."""

    def __init__(self, base: BaseEnMemoire, stockage: _Stockage, verrous: Any) -> None:
        self.base, self.stockage, self.verrous = base, stockage, verrous

    def bulletin(self, employe: str = SALARIE, mois: int = MOIS) -> dict[str, Any]:
        return self.base.ligne("payslips", employee_id=employe, year=ANNEE, month=mois)

    def donnees(self, employe: str = SALARIE, mois: int = MOIS) -> dict[str, Any]:
        return self.bulletin(employe, mois)["payslip_data"]

    def saisies(self, employe: str = SALARIE) -> list[dict[str, Any]]:
        return self.base.lignes("monthly_inputs", employee_id=employe)

    def generer(self, employe: str, mois: int = MOIS, **options: Any) -> Any:
        return commands.generate_payslip(
            GeneratePayslipInput(employee_id=employe, year=ANNEE, month=mois, **options)
        )

    def corriger(self, corrections: CorrectionsBulletin, **options: Any) -> dict[str, Any]:
        return corriger_bulletin(
            CorrigerBulletinInput(
                payslip_id=str(self.bulletin()["id"]),
                corrections=corrections,
                current_user_id="rh-fictive",
                current_user_name="RH Fictive",
                **options,
            )
        )

    def restaurer(self, version: int) -> dict[str, Any]:
        return restaurer_version(
            RestorePayslipInput(
                payslip_id=str(self.bulletin()["id"]),
                version=version,
                current_user_id="rh-fictive",
                current_user_name="RH Fictive",
            )
        )

    def corriger_a_l_ecran(self, corrections: CorrectionsBulletin) -> dict[str, Any]:
        """La porte du routeur : droits, verrou de période et bulletin remis, puis la correction."""
        return edit_payslip_for_user(
            str(self.bulletin()["id"]),
            corrections,
            UserContext(
                user_id="rh-fictive",
                is_platform_admin=False,
                has_rh_access_in_company=lambda _societe: True,
                active_company_id=SOCIETE,
                first_name="RH",
                last_name="Fictive",
            ),
        )

    # --- Ce qui sort du bulletin ------------------------------------------------

    def dsn(self) -> tuple[dict[str, dict[str, Any]], Any]:
        """La DSN complète, lue par salarié et par code."""
        lignes = [
            {"employee": self.base.ligne("employees", id=employe), "payslip_data": self.donnees(employe)}
            for employe in (SALARIE, COLLEGUE)
        ]
        fichier, _ = build_parsed_dsn_from_payroll(self.base.ligne("companies", id=SOCIETE), lignes, f"{ANNEE}-{MOIS:02d}")
        lu: dict[str, dict[str, Any]] = {}
        for individu in fichier.etablissement.individus:
            versement = individu.contrats[0].versements[0]
            cotisations: dict[tuple[str, str], tuple[float, float]] = {}
            for cotisation in versement.cotisations_individuelles:
                cle = (cotisation.code, str(cotisation.rubriques.get("_base")))
                assert cle not in cotisations, f"{cle} déclaré deux fois"
                cotisations[cle] = (round(cotisation.montant_assiette, 2), round(cotisation.montant_patronal, 2))
            lu[individu.matricule] = {
                "net_fiscal": round(versement.net_fiscal, 2),
                "net_verse": round(versement.net_verse, 2),
                "pas": round(versement.pas, 2),
                "remunerations": {r.type_code: round(r.montant, 2) for r in versement.remunerations},
                "bases": {b.code: round(b.montant, 2) for b in versement.bases_assujetties},
                "cotisations": cotisations,
            }
        return lu, fichier

    def od(self) -> tuple[dict[str, Any], dict[str, float]]:
        """L'OD complète, lue comme l'export, contrôlée par `controler()`."""
        for ligne in self.base.tables["payslips"]:
            # Ce que rend la jointure `employees!inner(…)` de PostgREST.
            ligne["employees"] = {
                **self.base.ligne("employees", id=ligne["employee_id"]),
                "companies": {"company_name": "Societe Fictive"},
            }
        periode = f"{ANNEE}-{MOIS:02d}"
        lignes, _ = get_payslip_data_for_od(SOCIETE, periode)
        ecritures, totaux, _ = build_payroll_ledger(SOCIETE, periode)
        generate_od_globale(SOCIETE, periode)  # refuse un déséquilibre
        rapport = controler(
            lignes,
            ecritures,
            lambda c: resolve_organisme_from_coti_id(c.get("coti_id"), str(c.get("libelle") or "")),
        )
        return rapport, totaux


@pytest.fixture
def paie(monkeypatch, verrous_de_generation) -> Paie:
    calendriers = [
        {
            "employee_id": employe,
            "company_id": SOCIETE,
            "year": ANNEE,
            "month": mois,
            "planned_calendar": _calendrier(mois)[0],
            "actual_hours": _calendrier(mois)[1],
        }
        for employe in (SALARIE, COLLEGUE)
        for mois in (9, 10, 11, 12)
    ]
    base = BaseEnMemoire(
        {
            "employees": [
                _fiche(SALARIE, SALAIRE, "1850199000000"),
                _fiche(COLLEGUE, SALAIRE_COLLEGUE, "2900199000000"),
            ],
            "companies": [
                {
                    "id": SOCIETE,
                    "raison_sociale": "Societe Fictive",
                    "name": "Societe Fictive",
                    "company_name": "Societe Fictive",
                    "siret": "12345678900015",
                    "code_naf": "2562B",
                    "adresse_code_postal": "39100",
                    "address": {"rue": "1 RUE FICTIVE", "code_postal": "39100", "ville": "DOLE"},
                    "taux_at_mp": 0.01,
                    "taux_vm": 0.0,
                    "settings": {"effectif_seuils": {str(ANNEE): 12}},
                }
            ],
            "employee_schedules": calendriers,
            "payslips": [],
            "monthly_inputs": [],
        }
    )
    base.brancher(monkeypatch)
    stockage = _Stockage()
    monkeypatch.setattr(type(database.supabase), "storage", property(lambda _self: stockage))
    monkeypatch.setattr(pdf_du_bulletin, "HTML", _Imprimeur)
    moteur = payslip_run_heures.run_payslip_generation_heures
    baremes = _baremes_de_paie()
    monkeypatch.setattr(
        payslip_run_heures,
        "run_payslip_generation_heures",
        lambda *a, **k: moteur(*a, **{**k, "baremes_override": copy.deepcopy(baremes)}),
    )
    paie = Paie(base, stockage, verrous_de_generation)
    for employe in (SALARIE, COLLEGUE):
        paie.generer(employe)
    verrous_de_generation.appels.clear()
    stockage.copies.clear()
    return paie


def _photo(paie: Paie) -> dict[str, Any]:
    return copy.deepcopy(
        {"bulletin": paie.bulletin(), "saisies": paie.saisies(), "collegue": paie.bulletin(COLLEGUE)}
    )


def _identiques(a: Any, b: Any, chemin: str = "") -> list[str]:
    """Les chemins où deux bulletins diffèrent ; les empreintes (date du calcul) à part."""
    if isinstance(a, dict) and isinstance(b, dict):
        ecarts = []
        for cle in set(a) | set(b):
            if "empreinte" in str(cle):
                continue
            ecarts.extend(_identiques(a.get(cle), b.get(cle), f"{chemin}/{cle}"))
        return ecarts
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [e for i, (x, y) in enumerate(zip(a, b)) for e in _identiques(x, y, f"{chemin}[{i}]")]
    return [] if a == b else [f"{chemin}: {a!r} != {b!r}"]


def _lignes_de(donnees: dict[str, Any]) -> list[dict[str, Any]]:
    return [l for rubrique in donnees.get("cotisations_officielles") or [] for l in rubrique.get("lignes") or []]


def _verifier_bulletin(donnees: dict[str, Any], vise: dict[str, Any]) -> None:
    synthese = donnees["synthese_net"]
    impot = synthese["impot_prelevement_a_la_source"]
    structure = donnees["structure_cotisations"]
    obtenu = {
        "brut": donnees["salaire_brut"],
        "net": donnees["net_a_payer"],
        "net_imposable": synthese["net_imposable"],
        "pas": impot["montant"],
        "salarial": structure["total_salarial"],
        "patronal": structure["total_patronal"],
    }
    assert obtenu == {k: vise[k] for k in obtenu}
    assert donnees["cumuls"]["cumuls"]["brut_total"] == vise["brut"]
    assert donnees["cumuls"]["cumuls"]["heures_remunerees"] == vise["heures"]
    assert donnees["cumuls"]["cumuls"]["net_imposable"] == vise["net_imposable"]
    assert donnees["cumuls"]["cumuls"]["impot_preleve_a_la_source"] == vise["pas"]
    assert donnees["cumuls"]["cumuls"]["reduction_generale_patronale"] == vise["reduction"]


def _verifier_dsn(lu: dict[str, Any], vise: dict[str, Any]) -> None:
    assert lu["bases"] == vise["bases"]
    assert lu["net_fiscal"] == vise["net_imposable"]
    assert lu["pas"] == vise["pas"]
    # Formule du CT 2026 (`_net_verse`) : chaque fraction non déductible arrondie à part.
    assert lu["net_verse"] == _r(vise["net_imposable"] - _r(vise["bases"]["04"] * 0.024) - _r(vise["bases"]["04"] * CRDS))
    assert lu["remunerations"]["002"] == vise["brut"]
    cotisations = dict(lu["cotisations"])
    reduction = cotisations.pop(("018", "03"))[1] + cotisations.pop(("106", "03"))[1]
    assert _r(reduction) == vise["reduction"]
    assert cotisations == vise["cotisations"]


def _verifier_od(rapport: dict[str, Any], vise: dict[str, Any]) -> None:
    assert rapport["equilibre"] is True
    assert rapport["complet"] is True
    assert rapport["natures_en_ecart"] == []
    assert rapport["bulletins_incoherents"] == []
    export = {n["nature"]: n["export"] for n in rapport["natures"]}
    assert export["brut"] == _r(vise["brut"] + COLLEGUE_ATTENDU["brut"])
    assert export["net_a_payer"] == -_r(vise["net"] + COLLEGUE_ATTENDU["net"])
    assert export["pas"] == -_r(vise["pas"] + COLLEGUE_ATTENDU["pas"])
    charges = sum(v for k, v in export.items() if k.startswith("charges:"))
    dettes = sum(v for k, v in export.items() if k.startswith("dettes:"))
    assert _r(charges) == _r(vise["patronal"] + COLLEGUE_ATTENDU["patronal"])
    assert _r(dettes) == -_r(
        vise["patronal"] + vise["salarial"] + COLLEGUE_ATTENDU["patronal"] + COLLEGUE_ATTENDU["salarial"]
    )


# --- Le point de départ est juste -------------------------------------------------


def test_le_bulletin_de_depart_vaut_le_calcul_a_part(paie):
    _verifier_bulletin(paie.donnees(), DEPART)
    _verifier_bulletin(paie.donnees(COLLEGUE), COLLEGUE_ATTENDU)
    lu, _ = paie.dsn()
    _verifier_dsn(lu[SALARIE], DEPART)
    _verifier_dsn(lu[COLLEGUE], COLLEGUE_ATTENDU)
    _verifier_od(paie.od()[0], DEPART)


# --- R-181 : écriture, relecture, archivage ---------------------------------------


@PARAMETRES
def test_la_correction_s_ecrit_dans_les_variables_du_mois(paie, cas):
    resultat = paie.corriger(cas.corrections)
    assert resultat["recalcule"] is True and resultat["recalcul_erreur"] is None

    saisies = paie.saisies()
    assert len(saisies) == 1
    saisie = saisies[0]
    assert {k: saisie[k] for k in ("employee_id", "company_id", "year", "month")} == {
        "employee_id": SALARIE,
        "company_id": SOCIETE,
        "year": ANNEE,
        "month": MOIS,
    }
    assert saisie["contract_period_id"] is None
    assert saisie["amount"] == 0
    assert saisie["correction_ligne"]["motif"]
    assert paie.saisies(COLLEGUE) == []


@PARAMETRES
def test_le_moteur_relit_la_saisie_et_le_bulletin_suit_au_centime(paie, cas):
    paie.corriger(cas.corrections)
    donnees = paie.donnees()
    _verifier_bulletin(donnees, cas.apres)

    saisie_id = str(paie.saisies()[0]["id"])
    portees = {**corrections_du_bulletin(donnees), **regularisations_du_bulletin(donnees)}
    assert list(portees) == [saisie_id]
    # L'autre bulletin du mois n'a pas bougé.
    assert paie.donnees(COLLEGUE)["net_a_payer"] == COLLEGUE_ATTENDU["net"]


def test_corriger_la_base_a_zero_retire_les_heures_du_smic(paie):
    paie.corriger(
        CorrectionsBulletin(
            corrections_ajoutees=(
                CorrectionDeLigne(ligne="brut:salaire_base", libelle="Salaire de base", motif="Absence non saisie", base=0.0),
            )
        )
    )
    donnees = paie.donnees()
    assert donnees["salaire_brut"] == 0.0
    assert donnees["cumuls"]["cumuls"]["heures_remunerees"] == 0.0


def test_le_gain_corrige_garde_la_valeur_de_martine(paie):
    paie.corriger(CAS[0].corrections)
    ligne = next(l for l in lignes_corrigeables(paie.donnees()) if l.code == "brut:salaire_base")
    assert ligne.base == 160.0
    assert ligne.montant == GAIN_CORRIGE_BRUT
    assert ligne.correction["saisie_id"] == str(paie.saisies()[0]["id"])
    assert ligne.valeur_calculee["gain"] == SALAIRE


def test_la_cotisation_corrigee_garde_la_valeur_de_martine(paie):
    paie.corriger(CAS[1].corrections)
    ligne = next(l for l in lignes_corrigeables(paie.donnees()) if l.code == "cotisation:vieillesse_plafonnee")
    assert (ligne.base, ligne.montant_salarial, ligne.montant_patronal) == (2600.0, 179.4, 222.3)
    assert ligne.valeur_calculee["montant_salarial"] == 172.5


@PARAMETRES
def test_la_version_d_avant_est_archivee_avec_son_pdf(paie, cas):
    avant = _photo(paie)["bulletin"]
    paie.corriger(cas.corrections, changes_summary="Motif de la RH")
    historique = paie.bulletin()["edit_history"]
    assert [v["version"] for v in historique] == [1]
    version = historique[0]
    assert version["action"] == "correction"
    assert version["changes_summary"] == "Motif de la RH"
    assert version["edited_by"] == "rh-fictive"
    assert version["previous_payslip_data"] == avant["payslip_data"]
    assert version["previous_pdf_url"] == avant["url"]
    assert version["pdf_storage_path"].endswith("_v1.pdf")
    assert paie.stockage.copies == [(avant["pdf_storage_path"], version["pdf_storage_path"])]
    # Un nouveau PDF, et l'ancien retiré.
    assert paie.bulletin()["pdf_storage_path"] != avant["pdf_storage_path"]
    assert avant["pdf_storage_path"] in paie.stockage.retires


# --- R-183 : DSN complète et OD complète sur le bulletin corrigé ----------------


@PARAMETRES
def test_la_dsn_complete_suit_la_correction_par_salarie_et_par_code(paie, cas):
    paie.corriger(cas.corrections)
    lu, fichier = paie.dsn()
    _verifier_dsn(lu[SALARIE], cas.apres)
    _verifier_dsn(lu[COLLEGUE], COLLEGUE_ATTENDU)

    # Le fichier écrit se relit : même salarié, même brut.
    relu = parse_dsn_content(encode_dsn_bytes(fichier), file_name="corrigee.dsn")
    totaux = [extract_monthly_totals(i) for i in relu.etablissement.individus]
    assert [round(t["brut"], 2) for t in totaux] == [cas.apres["brut"], COLLEGUE_ATTENDU["brut"]]
    assert [round(t["pas"], 2) for t in totaux] == [cas.apres["pas"], COLLEGUE_ATTENDU["pas"]]


@PARAMETRES
def test_l_od_complete_equilibre_et_range_chaque_nature(paie, cas):
    paie.corriger(cas.corrections)
    rapport, totaux = paie.od()
    _verifier_od(rapport, cas.apres)
    assert totaux["equilibre"] is True
    assert totaux.get("anomalies") in (None, [])


# --- R-181 : retrait et restauration ---------------------------------------------


@PARAMETRES
def test_le_retrait_revient_au_centime_au_bulletin_d_origine(paie, cas):
    origine = _photo(paie)["bulletin"]["payslip_data"]
    paie.corriger(cas.corrections)
    saisie_id = str(paie.saisies()[0]["id"])

    resultat = paie.corriger(cas.retrait(saisie_id))

    assert resultat["recalcule"] is True
    assert paie.saisies() == []
    assert _identiques(paie.donnees(), origine) == []
    _verifier_bulletin(paie.donnees(), DEPART)
    lu, _ = paie.dsn()
    _verifier_dsn(lu[SALARIE], DEPART)
    _verifier_od(paie.od()[0], DEPART)


def test_le_retrait_d_une_saisie_d_un_autre_salarie_ne_supprime_rien(paie):
    paie.corriger(CAS[2].corrections)
    saisie_id = str(paie.saisies()[0]["id"])
    # Le bulletin du collègue ne porte pas cette saisie : son identifiant ne sert à rien.
    corriger_bulletin(
        CorrigerBulletinInput(
            payslip_id=str(paie.bulletin(COLLEGUE)["id"]),
            corrections=CorrectionsBulletin(regularisations_retirees=(saisie_id,)),
            current_user_id="rh-fictive",
            current_user_name="RH Fictive",
        )
    )
    assert [str(s["id"]) for s in paie.saisies()] == [saisie_id]


@PARAMETRES
def test_la_restauration_revient_a_la_version_et_retire_la_saisie(paie, cas):
    origine = _photo(paie)["bulletin"]["payslip_data"]
    paie.corriger(cas.corrections)

    resultat = paie.restaurer(1)

    assert resultat["recalcule"] is True
    assert paie.saisies() == []
    assert _identiques(paie.donnees(), origine) == []
    historique = paie.bulletin()["edit_history"]
    assert [v["version"] for v in historique] == [1, 2]
    assert historique[1]["changes_summary"] == "Retour à la version 1"
    lu, _ = paie.dsn()
    _verifier_dsn(lu[SALARIE], DEPART)
    _verifier_od(paie.od()[0], DEPART)


@PARAMETRES
def test_restaurer_la_version_corrigee_recree_sa_saisie(paie, cas):
    paie.corriger(cas.corrections)
    premiere_saisie = str(paie.saisies()[0]["id"])
    paie.restaurer(1)
    assert paie.saisies() == []

    # La version 2 est le bulletin corrigé, archivé par la restauration.
    resultat = paie.restaurer(2)

    assert resultat["recalcule"] is True
    saisies = paie.saisies()
    assert len(saisies) == 1
    assert str(saisies[0]["id"]) != premiere_saisie
    _verifier_bulletin(paie.donnees(), cas.apres)


# --- R-181 : refus -----------------------------------------------------------------


def _inchange(paie: Paie, photo: dict[str, Any]) -> None:
    apres = _photo(paie)
    assert apres == photo


@pytest.mark.parametrize(
    "correction, phrase",
    [
        (
            CorrectionDeLigne(ligne="brut:prime_inconnue", libelle="Prime inconnue", motif="Essai", montant=10.0),
            "n'est plus sur le bulletin",
        ),
        (
            CorrectionDeLigne(ligne="brut:salaire_base", libelle="Salaire de base", motif="Essai", montant=10.0),
            "se corrige par",
        ),
        (
            CorrectionDeLigne(ligne="cotisation:allocations_familiales", libelle="AF", motif="Essai", taux_salarial=0.01),
            "n'a pas de taux salarial",
        ),
    ],
    ids=["ligne_absente", "mode_interdit", "taux_absent"],
)
def test_une_correction_impossible_est_refusee_sans_rien_ecrire(paie, correction, phrase):
    photo = _photo(paie)
    with pytest.raises(PayslipBadRequestError, match=phrase):
        paie.corriger(CorrectionsBulletin(corrections_ajoutees=(correction,)))
    _inchange(paie, photo)


def test_une_ligne_deja_corrigee_est_refusee_sans_ajouter_de_saisie(paie):
    paie.corriger(CAS[0].corrections)
    photo = _photo(paie)
    with pytest.raises(PayslipBadRequestError, match="déjà corrigée"):
        paie.corriger(CAS[0].corrections)
    _inchange(paie, photo)


def test_la_reduction_generale_qui_deviendrait_negative_est_refusee(paie):
    photo = _photo(paie)
    correction = CorrectionDeLigne(
        ligne="cotisation:reduction_generale",
        libelle="Réduction générale de cotisations patronales",
        motif="Essai",
        montant_patronal=10.0,
    )
    # Depuis janvier, rien d'autre que le mois : la réduction ne peut pas être positive.
    with pytest.raises(PayslipBadRequestError, match="réduction générale"):
        paie.corriger(CorrectionsBulletin(corrections_ajoutees=(correction,)))
    _inchange(paie, photo)


def test_rien_a_corriger_est_refuse_sans_rien_ecrire(paie):
    photo = _photo(paie)
    with pytest.raises(PayslipBadRequestError, match="Aucune modification"):
        paie.corriger(CorrectionsBulletin())
    _inchange(paie, photo)


# --- R-181 : verrous ---------------------------------------------------------------


def test_le_verrou_est_pris_une_fois_et_rendu(paie):
    paie.corriger(CAS[0].corrections)
    assert paie.verrous.appels == ["prendre_verrou_generation_bulletin", "rendre_verrou_generation_bulletin"]
    assert paie.verrous.tenus == {}


def test_une_generation_en_cours_refuse_la_correction_sans_ecrire(paie):
    paie.bulletin()["status"] = "valide"
    paie.verrous.tenus[(SALARIE, ANNEE, MOIS)] = "autre-requete"
    photo = _photo(paie)
    with pytest.raises(GenerationDejaEnCours):
        paie.corriger(CAS[0].corrections)
    _inchange(paie, photo)
    assert paie.bulletin()["status"] == "valide"


def test_un_bulletin_modifie_depuis_son_ouverture_est_refuse(paie):
    paie.bulletin()["updated_at"] = "2026-11-02T10:00:00+00:00"
    photo = _photo(paie)
    with pytest.raises(PayslipConflictError):
        paie.corriger(CAS[0].corrections, base_updated_at="2026-11-02T09:59:00+00:00")
    _inchange(paie, photo)


def test_le_bulletin_ouvert_a_la_bonne_date_passe(paie):
    paie.bulletin()["updated_at"] = "2026-11-02T10:00:00+00:00"
    assert paie.corriger(CAS[0].corrections, base_updated_at="2026-11-02T10:00:00Z")["recalcule"] is True


def test_un_bulletin_repris_de_l_ancien_logiciel_est_refuse(paie):
    paie.bulletin()["origine"] = "importe"
    photo = _photo(paie)
    with pytest.raises(PayslipBadRequestError, match="logiciel précédent"):
        paie.corriger(CAS[0].corrections)
    with pytest.raises(PayslipBadRequestError, match="logiciel précédent"):
        paie.restaurer(1)
    _inchange(paie, photo)


def test_la_porte_de_l_ecran_refuse_un_bulletin_remis_sans_rien_ecrire(paie, monkeypatch):
    from app.modules.payslips.application import period_edit_lock

    # Validé, remis au 1er du mois suivant : le 01/11/2026 est passé.
    monkeypatch.setattr(period_edit_lock, "aujourd_hui_local", lambda: date(2026, 11, 8))
    paie.bulletin()["status"] = "valide"
    photo = _photo(paie)
    with pytest.raises(PayslipBadRequestError, match="il ne se modifie plus"):
        paie.corriger_a_l_ecran(CAS[0].corrections)
    _inchange(paie, photo)


def test_la_porte_de_l_ecran_laisse_corriger_un_brouillon(paie):
    assert paie.corriger_a_l_ecran(CAS[0].corrections)["recalcule"] is True
    _verifier_bulletin(paie.donnees(), CAS[0].apres)


# --- R-181 : validé, brouillon, recalcul en échec -----------------------------------


def test_un_bulletin_valide_corrige_repasse_en_brouillon_et_le_dit(paie):
    paie.bulletin()["status"] = "valide"
    avant = _photo(paie)["bulletin"]

    resultat = paie.corriger(CAS[0].corrections)

    assert paie.bulletin()["status"] == "brouillon"
    assert resultat["recalcule"] is True
    assert paie.bulletin()["edit_history"][0]["previous_payslip_data"] == avant["payslip_data"]
    _verifier_bulletin(paie.donnees(), CAS[0].apres)


def test_une_note_interne_seule_laisse_le_bulletin_valide(paie):
    paie.bulletin()["status"] = "valide"
    donnees = _photo(paie)["bulletin"]["payslip_data"]
    resultat = paie.corriger(CorrectionsBulletin(), internal_note="À revoir avec le service.")
    assert paie.bulletin()["status"] == "valide"
    assert resultat["recalcule"] is False
    assert paie.donnees() == donnees
    assert paie.saisies() == []


def test_si_le_moteur_echoue_la_saisie_reste_et_le_bulletin_le_dit(paie, monkeypatch):
    paie.bulletin()["status"] = "valide"
    moteur = payslip_run_heures.run_payslip_generation_heures

    def en_panne(*_a: Any, **_k: Any) -> dict:
        raise ValueError("Barème illisible.")

    monkeypatch.setattr(payslip_run_heures, "run_payslip_generation_heures", en_panne)
    resultat = paie.corriger(CAS[0].corrections)

    assert resultat["recalcule"] is False
    assert resultat["recalcul_erreur"] == "Barème illisible."
    assert paie.bulletin()["status"] == "brouillon"
    assert len(paie.saisies()) == 1
    assert paie.donnees()["salaire_brut"] == SALAIRE  # l'ancien calcul, marqué
    raisons = raisons_de_ne_pas_valider(paie.donnees())
    assert raisons and "recalcul" in raisons[0].lower()
    assert paie.donnees()["recalcul_en_attente"]["erreur"] == "Barème illisible."

    # La panne levée, retirer la correction refait le bulletin entier et efface la marque.
    monkeypatch.setattr(payslip_run_heures, "run_payslip_generation_heures", moteur)
    resultat = paie.corriger(CAS[0].retrait(str(paie.saisies()[0]["id"])))
    assert resultat["recalcule"] is True
    assert "recalcul_en_attente" not in paie.donnees()
    _verifier_bulletin(paie.donnees(), DEPART)


# --- R-181 : cascade sur le mois suivant ------------------------------------------


@pytest.fixture
def cascade(paie, monkeypatch) -> Paie:
    """La vraie règle de la suite, à la place de la doublure commune des tests."""
    monkeypatch.setattr(commands, "mois_suivant_a_recalculer", suite_du_bulletin.mois_suivant_a_recalculer)
    return paie


def test_le_brouillon_du_mois_suivant_est_rendu_a_l_ecran(cascade):
    cascade.generer(SALARIE, SUIVANT)

    resultat = cascade.corriger(CAS[0].corrections)

    suite = resultat["mois_suivant_a_recalculer"]
    assert (suite["year"], suite["month"]) == (ANNEE, SUIVANT)
    # Le recalcul que l'écran enchaîne : novembre repart des cumuls corrigés d'octobre.
    cascade.generer(SALARIE, SUIVANT)
    cumuls = cascade.donnees(mois=SUIVANT)["cumuls"]["cumuls"]
    assert round(cumuls["brut_total"], 2) == _r(GAIN_CORRIGE_BRUT + SALAIRE)
    assert round(cumuls["heures_remunerees"], 2) == _r(160.0 + HEURES)


def test_le_mois_suivant_valide_est_signale_et_jamais_recalcule(cascade, monkeypatch):
    from app.modules.payroll.application import empreinte_entrees_service as service

    cascade.generer(SALARIE, SUIVANT)
    cascade.bulletin(mois=SUIVANT)["status"] = "valide"
    # Le verdict du bac à sable d'un validé : on le veut « il a changé », sans lancer le moteur.
    monkeypatch.setattr(service, "_verifier_les_valides", lambda _e, _l, etats, *_a, **_k: etats)
    novembre_avant = copy.deepcopy(cascade.donnees(mois=SUIVANT))

    resultat = cascade.corriger(CAS[0].corrections)

    assert resultat["mois_suivant_a_recalculer"] is None
    assert "mois_suivant_valide" in [a.get("code") for a in resultat["warnings"] if isinstance(a, dict)]
    assert cascade.donnees(mois=SUIVANT) == novembre_avant
    assert cascade.bulletin(mois=SUIVANT)["status"] == "valide"


def test_sans_mois_suivant_il_n_y_a_rien_a_recalculer(cascade):
    assert cascade.corriger(CAS[0].corrections)["mois_suivant_a_recalculer"] is None


@PARAMETRES
def test_restaurer_rend_aussi_le_mois_suivant_a_recalculer(cascade, cas):
    cascade.generer(SALARIE, SUIVANT)
    cascade.corriger(cas.corrections)
    cascade.generer(SALARIE, SUIVANT)

    resultat = cascade.restaurer(1)

    assert resultat["mois_suivant_a_recalculer"] is not None
