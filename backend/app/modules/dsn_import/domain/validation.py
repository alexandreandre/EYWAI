"""Validation du modèle DSN importé."""

from __future__ import annotations

from typing import Any, Dict, List, Set

from app.modules.dsn_import.domain.model import EtablissementBlock, IndividuBlock, ParsedDsnSet
from app.shared.dsn_validation import validate_nir, validate_siren, validate_siret


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


def validate_parsed_dsn(parsed: ParsedDsnSet) -> List[Dict[str, Any]]:
    """Valide l'ensemble parsé et retourne la liste d'anomalies."""
    anomalies: List[Dict[str, Any]] = []

    siren = parsed.siren
    if siren:
        ok, err = validate_siren(siren)
        if not ok:
            anomalies.append(_anomaly(f"SIREN : {err}", severity="blocking", source_ref=f"group:{siren}"))

    etabs = parsed.etablissements_by_siret()
    if not etabs:
        anomalies.append(
            _anomaly("Aucun établissement identifié dans les DSN", severity="blocking")
        )

    seen_nirs: Set[str] = set()
    for siret, etab in etabs.items():
        ok, err = validate_siret(siret)
        if not ok:
            anomalies.append(
                _anomaly(f"Établissement {siret} : {err}", severity="blocking", source_ref=f"etab:{siret}")
            )
        if siren and siret[:9] != siren[:9]:
            anomalies.append(
                _anomaly(
                    f"SIRET {siret} incohérent avec SIREN {siren}",
                    severity="blocking",
                    source_ref=f"etab:{siret}",
                )
            )
        for ind in etab.individus:
            anomalies.extend(_validate_individu(ind, siret, seen_nirs))

    if not parsed.period_min:
        anomalies.append(
            _anomaly("Période DSN non identifiée (S10.G00.00.005)", severity="warning")
        )

    return anomalies


def _validate_individu(
    ind: IndividuBlock, siret: str, seen_nirs: Set[str]
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    name = f"{ind.prenom} {ind.nom}".strip() or "Salarié"
    ref = f"emp:{siret}:{ind.nir or name}"

    if not ind.nom or not ind.prenom:
        out.append(_anomaly(f"{name} : nom ou prénom manquant", source_ref=ref))

    if ind.nir:
        ok, err = validate_nir(ind.nir)
        if not ok:
            out.append(_anomaly(f"{name} : {err}", severity="blocking", source_ref=ref))
        elif ind.nir in seen_nirs:
            out.append(
                _anomaly(f"{name} : NIR en doublon dans l'import", severity="blocking", source_ref=ref)
            )
        else:
            seen_nirs.add(ind.nir)
    else:
        out.append(_anomaly(f"{name} : NIR manquant", severity="blocking", source_ref=ref))

    if not ind.contrats:
        out.append(_anomaly(f"{name} : aucun contrat trouvé", source_ref=ref))
    else:
        ctr = ind.contrats[0]
        if not ctr.date_debut:
            out.append(_anomaly(f"{name} : date de début de contrat manquante", source_ref=ref))
        if not ctr.nature:
            out.append(_anomaly(f"{name} : nature de contrat manquante", source_ref=ref))

    return out
