"""Profils de salariés pour les tests du bulletin : une règle, plusieurs profils.

Le 17/11/2026, l'activité partielle n'était branchée que dans le générateur des
heures ; les tests étaient verts parce qu'ils ne prenaient qu'un salarié en
heures. Ce module fait tourner le vrai chemin d'un bulletin (aiguillage du bac à
sable, générateur heures ou forfait jours, vrai moteur sur des barèmes figés),
sur une base en mémoire, pour cinq profils :

- `heures` : non-cadre, 35 h, CDI ;
- `forfait_jours` : cadre au forfait jours (case de la fiche) ;
- `apprenti` : contrat d'apprentissage, 35 h ;
- `temps_partiel` : 24 h par semaine ;
- `sortie_en_cours_de_mois` : CDD qui finit le 15 du mois du bulletin.

Usage, une ligne par test multi-profils :

    from tests.unit.payroll.profils_salaries import PROFILS, banc  # noqa: F401

    @pytest.mark.parametrize("profil", PROFILS)
    def test_ma_regle(banc, profil):
        donnees = banc.generer(profil, jours={5: "activite_partielle"})
        ...

Rien n'est écrit : le bulletin passe par `generate_en_bac_a_sable`, comme le
filet et la relecture. Aucun nom réel : salariés et société fictifs.
"""

from __future__ import annotations

import calendar
import copy
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pytest

ANNEE, MOIS = 2026, 10
SOCIETE = "societe-profils"

PROFILS = ("heures", "forfait_jours", "apprenti", "temps_partiel", "sortie_en_cours_de_mois")
#: Le minimum d'une règle qui touche le bulletin : un salarié de chaque générateur.
DEUX_GENERATEURS = ("heures", "forfait_jours")

_COMMUN: dict[str, Any] = {
    "company_id": SOCIETE,
    "first_name": "Prenom",
    "sexe": "F",
    "date_naissance": "1990-03-15",
    "nir": "2900375000000",
    "hire_date": "2020-01-06",
    "statut": "Non-Cadre",
    "contract_type": "CDI",
    "duree_hebdomadaire": 35,
    "salaire_de_base": {"valeur": 2500.0},
    "idcc": "1486",
    "job_title": "Technicien",
    "is_forfait_jour": False,
    "specificites_paie": {"prelevement_a_la_source": {"taux": 0.0, "is_personnalise": True}},
}

_PROFILS: dict[str, dict[str, Any]] = {
    "heures": {},
    "forfait_jours": {
        "statut": "Cadre",
        "is_forfait_jour": True,
        "salaire_de_base": {"valeur": 4200.0},
        "job_title": "Ingénieur",
    },
    "apprenti": {
        "contract_type": "Contrat d'apprentissage",
        "date_naissance": "2006-05-02",
        "hire_date": "2025-09-01",
        "date_debut_execution": "2025-09-01",
        "contract_end_date": "2027-08-31",
        "salaire_de_base": {"valeur": 1200.0},
        "job_title": "Apprentie",
    },
    "temps_partiel": {
        "duree_hebdomadaire": 24,
        "is_temps_partiel": True,
        "salaire_de_base": {"valeur": 1714.29},
    },
    "sortie_en_cours_de_mois": {
        "contract_type": "CDD",
        "hire_date": "2026-04-01",
        "contract_end_date": f"{ANNEE}-{MOIS:02d}-15",
    },
}


def fiche(profil: str, **surcharges: Any) -> dict[str, Any]:
    """La fiche `employees` d'un profil, avec ses surcharges."""
    if profil not in _PROFILS:
        raise KeyError(f"profil inconnu : {profil} (connus : {', '.join(PROFILS)})")
    ligne = {**copy.deepcopy(_COMMUN), **copy.deepcopy(_PROFILS[profil]), **surcharges}
    ligne.setdefault("id", f"salarie-{profil}")
    ligne.setdefault("last_name", f"Fictif {profil}")
    ligne.setdefault("employee_folder_name", f"fictif_{profil}")
    ligne.setdefault("matricule", profil[:10])
    return ligne


def _heures_du_jour(fiche_salarie: dict[str, Any]) -> float:
    if fiche_salarie.get("is_forfait_jour"):
        return 7.0
    return round(float(fiche_salarie.get("duree_hebdomadaire") or 35) / 5, 2)


def calendrier(
    fiche_salarie: dict[str, Any], annee: int, mois: int, jours: dict[int, Any] | None = None
) -> tuple[dict, dict]:
    """Prévu et réel d'un mois : du lundi au vendredi travaillés ; `jours` retype
    des jours (`{5: "activite_partielle"}`), à 0 h faites. Un jour peut aussi
    porter ses métadonnées d'arrêt (`{5: {"type": "arret_maladie", "arret_type": …}}`)."""
    jours = jours or {}
    heures = _heures_du_jour(fiche_salarie)
    prevu, reel = [], []
    for jour in range(1, calendar.monthrange(annee, mois)[1] + 1):
        ouvre = date(annee, mois, jour).weekday() < 5
        # Un jour peut porter ses métadonnées d'arrêt : {"type": …, "arret_type": …}.
        valeur = jours.get(jour)
        extra = dict(valeur) if isinstance(valeur, dict) else {"type": valeur}
        type_jour = extra.pop("type", None) or ("travail" if ouvre else "weekend")
        prevu.append({"jour": jour, "type": type_jour, "heures_prevues": heures if ouvre else 0.0, **extra})
        travaille = type_jour == "travail"
        reel.append({"jour": jour, "type": type_jour, "heures_faites": heures if travaille else 0.0})
    return {"calendrier_prevu": prevu}, {"calendrier_reel": reel}


@dataclass
class Banc:
    """La paie d'un mois sur une base en mémoire, par le vrai aiguillage."""

    base: Any
    lus: dict[str, list[str]] = field(default_factory=dict)

    def generer(
        self,
        profil: str,
        *,
        jours: dict[int, Any] | None = None,
        jours_des_mois_voisins: dict[tuple[int, int], dict[int, Any]] | None = None,
        saisies: list[dict[str, Any]] | None = None,
        absences: list[dict[str, Any]] | None = None,
        fiche_en_plus: dict[str, Any] | None = None,
        annee: int = ANNEE,
        mois: int = MOIS,
    ) -> dict[str, Any]:
        """Calcule le bulletin du profil au bac à sable et rend `payslip_data`."""
        from app.modules.payslips.infrastructure.providers import payslip_generator_provider

        salarie = fiche(profil, **(fiche_en_plus or {}))
        self.base.tables["employees"] = [salarie]
        self.base.tables["employee_schedules"] = []
        for decalage in (-1, 0, 1):
            m = mois + decalage
            a = annee + (m - 1) // 12
            m = (m - 1) % 12 + 1
            # Période décalée (forfait : 21 du mois d'avant au 25) : les jours
            # des mois voisins se typent par `jours_des_mois_voisins[(a, m)]`.
            voisins = (jours_des_mois_voisins or {}).get((a, m))
            prevu, reel = calendrier(salarie, a, m, jours if (a, m) == (annee, mois) else voisins)
            self.base.tables["employee_schedules"].append(
                {
                    "employee_id": salarie["id"],
                    "company_id": SOCIETE,
                    "year": a,
                    "month": m,
                    "planned_calendar": prevu,
                    "actual_hours": reel,
                    "payroll_events": None,
                    "cumuls": None,
                }
            )
        self.base.tables["monthly_inputs"] = [
            {
                "id": f"saisie-{i}",
                "employee_id": salarie["id"],
                "company_id": SOCIETE,
                "year": annee,
                "month": mois,
                "is_socially_taxed": True,
                "is_taxable": True,
                **s,
            }
            for i, s in enumerate(saisies or [])
        ]
        self.base.tables["absence_requests"] = [
            {"employee_id": salarie["id"], "company_id": SOCIETE, **a} for a in (absences or [])
        ]
        resultat = payslip_generator_provider.generate_en_bac_a_sable(salarie["id"], annee, mois)
        return resultat["payslip_data"]


def alertes(donnees: dict[str, Any]) -> list[str]:
    """Les codes des alertes d'un bulletin."""
    return [str(a.get("code")) for a in donnees.get("alertes_baremes") or [] if isinstance(a, dict)]


def lignes_de_gain(donnees: dict[str, Any]) -> list[str]:
    """Les libellés des lignes du brut et des primes d'un bulletin."""
    libelles = [str(l.get("libelle")) for l in donnees.get("salaire_de_base", {}).get("lignes", []) or []]
    for cle in ("lignes_composants_brut", "details_brut"):
        libelles += [str(l.get("libelle")) for l in donnees.get(cle) or [] if isinstance(l, dict)]
    for cle in ("primes", "primes_non_soumises", "autres_elements"):
        valeur = donnees.get(cle)
        if isinstance(valeur, list):
            libelles += [str(l.get("libelle")) for l in valeur if isinstance(l, dict)]
    return libelles


@pytest.fixture
def banc(monkeypatch) -> Banc:
    """Base en mémoire, barèmes figés, vrai moteur heures et forfait jours."""
    from app.core import database
    from app.modules.payroll.application import periode_variables_service
    from app.modules.payroll.documents import payslip_run_forfait, payslip_run_heures
    from app.modules.payroll.documents import payslip_generator as pg
    from app.modules.payroll.documents import payslip_generator_forfait as pgf
    from app.shared.domain.periode_variables import FenetreVariables
    from tests.unit.base_en_memoire import BaseEnMemoire
    from tests.unit.payslips.test_theoreme_chemin_complet import _baremes_de_paie

    base = BaseEnMemoire(
        {
            "companies": [
                {
                    "id": SOCIETE,
                    "raison_sociale": "Societe Profils",
                    "company_name": "Societe Profils",
                    "siret": "12345678900015",
                    "code_naf": "2562B",
                    "adresse_code_postal": "39100",
                    "taux_at_mp": 0.01,
                    "taux_vm": 0.0,
                    "settings": {"effectif_seuils": {str(ANNEE): 12}},
                }
            ],
            "payslips": [],
        }
    )
    base.brancher(monkeypatch)
    monkeypatch.setattr(type(database.supabase), "storage", property(lambda _s: None))

    def fenetre(_societe, annee, mois, **_k):
        debut, fin = date(annee, mois, 1), date(annee, mois, calendar.monthrange(annee, mois)[1])
        return FenetreVariables(debut=debut, fin=fin, origine="mois civil")

    monkeypatch.setattr(periode_variables_service, "resoudre_fenetre_variables", fenetre)
    monkeypatch.setattr(pg, "build_convention_collective_payload", lambda *_a, **_k: {})
    monkeypatch.setattr(pgf, "build_convention_collective_payload", lambda *_a, **_k: {})

    from app.modules.activite_partielle.application import service as activite_partielle

    # Le réglage d'activité partielle se lit par le client d'administration.
    monkeypatch.setattr(activite_partielle, "_db", lambda: base)

    baremes = _baremes_de_paie()
    # Plafonds repas Urssaf 2026 par situation (le panier plafonné en dépend).
    baremes["frais_pro"]["sections"]["repas"].update(
        {"sur_lieu_travail": 7.5, "hors_locaux_sans_restaurant": 10.4, "hors_locaux_avec_restaurant": 21.4}
    )
    for module, nom in (
        (payslip_run_heures, "run_payslip_generation_heures"),
        (payslip_run_forfait, "run_payslip_generation_forfait"),
    ):
        vrai = getattr(module, nom)
        monkeypatch.setattr(
            module,
            nom,
            lambda *a, _vrai=vrai, **k: _vrai(*a, **{**k, "baremes_override": copy.deepcopy(baremes)}),
        )
    return Banc(base)
