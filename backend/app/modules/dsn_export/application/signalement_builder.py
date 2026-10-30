"""Le fichier d'un signalement d'arrêt (04) ou de reprise anticipée (05).

Les données identifiantes sont celles de la DSN mensuelle (cahier technique
2026.1, § 2.5.1 : sinon le signalement n'aboutit pas) : mêmes lectures de la
fiche, puis filtrage par les rubriques permises de la nature.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from app.modules.dsn_export.application.builder import (
    DsnBuildError,
    _classification,
    build_entreprise,
    build_envoi,
    build_etablissement,
)
from app.modules.dsn_export.domain.contract_map import iso_to_dsn_date
from app.modules.dsn_export.domain.evenements import (
    MOTIFS_ACCIDENT,
    dernier_jour_travaille,
    dsn,
)
from app.modules.dsn_export.domain.settings import DsnSettings
from app.modules.dsn_export.domain.signalements import SignalementAFaire
from app.modules.dsn_export.domain.usages_signalement import NATURE_ARRET, filtrer
from app.modules.dsn_export.domain.writer import ecrire_blocs


def _manque(champ: str) -> DsnBuildError:
    return DsnBuildError(f"Signalement impossible : {champ} manquant sur la fiche du salarié.")


def _individu(employee: Dict[str, Any]) -> Dict[str, str]:
    nir = str(employee.get("nir") or "").replace(" ", "")[:13]
    ntt = str(employee.get("ntt") or "")
    if not nir and not ntt:
        raise _manque("numéro de sécurité sociale")
    naissance = iso_to_dsn_date(employee.get("date_naissance") or employee.get("birth_date"))
    nom = str(employee.get("last_name") or "").upper()
    prenom = str(employee.get("first_name") or "").strip()
    for champ, valeur in (("nom", nom), ("prénom", prenom), ("date de naissance", naissance)):
        if not valeur:
            raise _manque(champ)
    rubriques = {
        "S21.G00.30.001": nir,
        "S21.G00.30.002": nom,
        "S21.G00.30.004": prenom,
        "S21.G00.30.006": naissance,
        "S21.G00.30.019": str(employee.get("matricule") or employee.get("time_tracking_id") or ""),
        "S21.G00.30.020": ntt,
    }
    if employee.get("nom_usage"):
        rubriques["S21.G00.30.003"] = str(employee["nom_usage"]).upper()
    return rubriques


def _debut_contrat(employee: Dict[str, Any]) -> date:
    texte = str(employee.get("hire_date") or employee.get("date_entree") or "")[:10]
    try:
        return date.fromisoformat(texte)
    except ValueError:
        raise _manque("date d'embauche") from None


def _contrat(employee: Dict[str, Any], debut: date, siret: str) -> Dict[str, str]:
    classification = _classification(employee)
    numero = str(
        classification.get("numero_contrat_dsn")
        or employee.get("numero_contrat")
        or employee.get("contract_number")
        or "00000"
    )
    return {"S21.G00.40.001": dsn(debut), "S21.G00.40.009": numero, "S21.G00.40.019": siret[:14]}


def _arret(s: SignalementAFaire, debut_contrat: Optional[date], settings: DsnSettings) -> Dict[str, str]:
    rubriques = {
        "S21.G00.60.001": s.motif,
        "S21.G00.60.002": dsn(dernier_jour_travaille(s.motif, s.debut, debut_contrat)),
        "S21.G00.60.003": dsn(s.fin_prevue),
    }
    if s.motif in MOTIFS_ACCIDENT:
        # Martine n'a pas de champ « date de l'accident » : le premier jour de
        # l'arrêt, que la DSN mensuelle tient déjà pour le jour de l'accident,
        # jamais avant le contrat (SIG-14).
        rubriques["S21.G00.60.012"] = dsn(max(s.debut, debut_contrat) if debut_contrat else s.debut)
    if s.nature == NATURE_ARRET:
        rubriques["S21.G00.60.004"] = "01" if s.subrogation else "02"
        if s.subrogation:
            compte = next((v for v in settings.versements if v.get("iban")), None)
            if not compte:
                raise DsnBuildError(
                    "Signalement impossible : subrogation sans IBAN de l'employeur "
                    "(réglages DSN, versements)."
                )
            rubriques.update({
                "S21.G00.60.005": dsn(s.debut),
                "S21.G00.60.006": dsn(s.fin_prevue),
                "S21.G00.60.007": str(compte.get("iban") or ""),
                "S21.G00.60.008": str(compte.get("bic") or ""),
            })
    else:
        rubriques["S21.G00.60.010"] = dsn(s.date_reprise)
        rubriques["S21.G00.60.011"] = "01"
    return rubriques


def construire_signalement(
    company: Dict[str, Any],
    employee: Dict[str, Any],
    signalement: SignalementAFaire,
    *,
    settings: DsnSettings,
    essai: bool,
    constitue_le: date,
) -> str:
    nature = signalement.nature
    individu = _individu(employee)
    debut_contrat = _debut_contrat(employee)
    entreprise = build_entreprise(company, settings=settings)
    etablissement = build_etablissement(company, entreprise, settings=settings)
    declaration = {
        "S20.G00.05.001": nature,
        "S20.G00.05.002": "01",
        "S20.G00.05.003": "11",
        "S20.G00.05.004": "1",
        "S20.G00.05.007": dsn(constitue_le),
    }
    contacts = [
        {
            "S20.G00.07.001": c.nom,
            "S20.G00.07.002": c.telephone,
            "S20.G00.07.003": c.email,
            "S20.G00.07.004": c.code_destinataire,
        }
        for c in settings.contacts_declaration
    ]
    blocs: List[Dict[str, str]] = [
        build_envoi(essai=essai, settings=settings).rubriques,
        declaration,
        *contacts,
        entreprise.rubriques,
        etablissement.rubriques,
        *(org.rubriques for org in etablissement.organismes_psc),
        individu,
        _contrat(employee, debut_contrat, etablissement.siret),
        _arret(signalement, debut_contrat, settings),
    ]
    return ecrire_blocs([filtrer(bloc, nature) for bloc in blocs])
