"""Validation du modèle DSN importé."""

from __future__ import annotations

from typing import Any, Dict, List, Set

from app.modules.dsn_import.domain.model import EtablissementBlock, IndividuBlock, ParsedDsnSet
from app.shared.dsn_validation import (
    build_siret_from_siren_nic,
    validate_nir_dsn,
    validate_siren,
    validate_siret,
)


def _anomaly(
    message: str,
    *,
    severity: str = "warning",
    source_ref: str = "",
) -> Dict[str, Any]:
    return {
        "type": "error" if severity == "blocking" else "warning",
        "message": message,
        "severity": severity,
        "source_ref": source_ref,
    }


def _resolve_siret(etab: EtablissementBlock, siren: str) -> str:
    if etab.siret and len(etab.siret.replace(" ", "")) == 14:
        return etab.siret.replace(" ", "")
    if etab.nic and siren:
        return build_siret_from_siren_nic(siren, etab.nic)
    return etab.siret.replace(" ", "") if etab.siret else ""


def validate_parsed_dsn(parsed: ParsedDsnSet) -> List[Dict[str, Any]]:
    """Valide l'ensemble parsé et retourne la liste d'anomalies."""
    anomalies: List[Dict[str, Any]] = []

    siren = parsed.siren or ""
    if siren:
        ok, err = validate_siren(siren)
        if not ok:
            anomalies.append(_anomaly(f"SIREN : {err}", severity="blocking", source_ref=f"group:{siren}"))

    etabs = parsed.etablissements_by_siret()
    if not etabs:
        anomalies.append(
            _anomaly("Aucun établissement identifié dans les DSN", severity="blocking")
        )

    seen_ids: Set[str] = set()
    for siret, etab in etabs.items():
        ok, err = validate_siret(siret)
        if not ok:
            anomalies.append(
                _anomaly(f"Établissement {siret} : {err}", severity="blocking", source_ref=f"etab:{siret}")
            )
        if siren and len(siret) >= 9 and siret[:9] != siren[:9]:
            anomalies.append(
                _anomaly(
                    f"SIRET {siret} incohérent avec SIREN {siren}",
                    severity="blocking",
                    source_ref=f"etab:{siret}",
                )
            )
        for ind in etab.individus:
            anomalies.extend(_validate_individu(ind, siret, seen_ids))

    if not parsed.period_min:
        anomalies.append(
            _anomaly("Période DSN non identifiée (S20.G00.05.005)", severity="warning")
        )

    return anomalies


def _validate_individu(
    ind: IndividuBlock, siret: str, seen_ids: Set[str]
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    name = f"{ind.prenom} {ind.nom}".strip() or "Salarié"
    ident = ind.identifiant or name
    ref = f"emp:{siret}:{ident}"

    if not ind.nom:
        out.append(_anomaly(f"{name} : nom manquant", source_ref=ref))
    if not ind.prenom:
        out.append(_anomaly(f"{name} : prénom manquant", source_ref=ref))

    if ind.nir:
        ok, err = validate_nir_dsn(ind.nir)
        if not ok:
            out.append(_anomaly(f"{name} : {err}", severity="blocking", source_ref=ref))
        elif ind.nir in seen_ids:
            out.append(
                _anomaly(f"{name} : NIR en doublon dans l'import", severity="blocking", source_ref=ref)
            )
        else:
            seen_ids.add(ind.nir)
    elif ind.ntt:
        if ind.ntt in seen_ids:
            out.append(
                _anomaly(f"{name} : NTT en doublon dans l'import", severity="blocking", source_ref=ref)
            )
        else:
            seen_ids.add(ind.ntt)
        out.append(
            _anomaly(
                f"{name} : NIR absent — identifié par NTT (compte à compléter)",
                severity="warning",
                source_ref=ref,
            )
        )
    elif ind.matricule:
        if ind.matricule in seen_ids:
            out.append(
                _anomaly(
                    f"{name} : matricule en doublon dans l'import",
                    severity="blocking",
                    source_ref=ref,
                )
            )
        else:
            seen_ids.add(ind.matricule)
        out.append(
            _anomaly(
                f"{name} : NIR absent — identifié par matricule {ind.matricule}",
                severity="warning",
                source_ref=ref,
            )
        )
    else:
        out.append(_anomaly(f"{name} : NIR / NTT / matricule manquant", severity="blocking", source_ref=ref))

    if not ind.contrats:
        out.append(_anomaly(f"{name} : aucun contrat trouvé", source_ref=ref))
    else:
        ctr = ind.contrats[0]
        if not ctr.date_debut:
            out.append(_anomaly(f"{name} : date de début de contrat manquante", source_ref=ref))
        if not ctr.nature:
            out.append(_anomaly(f"{name} : nature de contrat manquante", source_ref=ref))

    return out
