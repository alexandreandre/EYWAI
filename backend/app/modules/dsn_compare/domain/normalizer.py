"""Normalisation d'une DSN parsée vers un snapshot comparable."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.modules.dsn_import.application.cumuls import extract_monthly_totals
from app.modules.dsn_import.domain.model import (
    ContratBlock,
    EtablissementBlock,
    IndividuBlock,
    ParsedDsnSet,
    VersementBlock,
)
from app.modules.dsn_import.domain.parser import parse_dsn_files


def _norm_nir(value: str) -> str:
    return (value or "").replace(" ", "").replace(".", "")[:15]


def _norm_code(value: str) -> str:
    text = (value or "").strip()
    if " - " in text:
        text = text.split(" - ", 1)[0].strip()
    return text


@dataclass
class RemunerationSnap:
    type_code: str
    montant: float
    heures: float


@dataclass
class CotisationSnap:
    code: str
    montant: float
    assiette: float


@dataclass
class EmployeeSnap:
    key: str
    nir: str
    nom: str
    prenom: str
    matricule: str
    ntt: str
    nature_contrat: str
    date_debut_contrat: str
    numero_contrat: str
    brut: float
    net_imposable: float
    net_verse: float
    pas: float
    heures: float
    remunerations: List[RemunerationSnap] = field(default_factory=list)
    cotisations: List[CotisationSnap] = field(default_factory=list)
    bases: Dict[str, float] = field(default_factory=dict)
    events: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class EstablishmentSnap:
    siret: str
    period: str
    norme: str
    headcount: int
    brut: float
    net_imposable: float
    pas: float
    employees: Dict[str, EmployeeSnap] = field(default_factory=dict)
    source_file: str = ""


@dataclass
class DsnNormalizedSnapshot:
    establishments: Dict[str, EstablishmentSnap] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


def _employee_key(ind: IndividuBlock) -> str:
    nir = _norm_nir(ind.nir)
    if nir:
        return f"nir:{nir}"
    if ind.ntt:
        return f"ntt:{ind.ntt.strip()}"
    if ind.matricule:
        return f"mat:{ind.matricule.strip().upper()}"
    return f"name:{(ind.nom or '').upper()}|{(ind.prenom or '').upper()}"


def _contrat_primary(ind: IndividuBlock) -> Optional[ContratBlock]:
    if not ind.contrats:
        return None
    # Préférer le contrat avec versement
    for ctr in ind.contrats:
        if ctr.versements:
            return ctr
    return ind.contrats[0]


def _versement_primary(ctr: ContratBlock) -> Optional[VersementBlock]:
    return ctr.versements[0] if ctr.versements else None


def normalize_individu(ind: IndividuBlock) -> EmployeeSnap:
    totals = extract_monthly_totals(ind)
    ctr = _contrat_primary(ind)
    ver = _versement_primary(ctr) if ctr else None
    remunerations: List[RemunerationSnap] = []
    cotisations: List[CotisationSnap] = []
    bases: Dict[str, float] = {}
    events: List[Dict[str, str]] = []

    if ver:
        for rem in ver.remunerations:
            remunerations.append(
                RemunerationSnap(
                    type_code=_norm_code(rem.type_code),
                    montant=float(rem.montant or 0),
                    heures=float(rem.heures or 0),
                )
            )
        for cot in ver.cotisations_individuelles:
            montant = float(cot.montant_patronal or cot.montant_salarial or 0)
            cotisations.append(
                CotisationSnap(
                    code=_norm_code(cot.code).zfill(3),
                    montant=montant,
                    assiette=float(cot.montant_assiette or 0),
                )
            )
        for base in ver.bases_assujetties:
            bases[_norm_code(base.code).zfill(2)] = float(base.montant or 0)

    if ctr:
        for arret in ctr.arrets:
            events.append(
                {
                    "type": "arret",
                    "debut": arret.date_debut,
                    "fin": arret.date_fin,
                    "motif": arret.motif,
                }
            )
        for susp in ctr.suspensions:
            events.append(
                {
                    "type": "suspension",
                    "debut": susp.date_debut,
                    "fin": susp.date_fin,
                    "motif": susp.motif or susp.type_suspension,
                }
            )
        if ctr.fin_contrat:
            events.append(
                {
                    "type": "fin_contrat",
                    "debut": ctr.fin_contrat.date_fin,
                    "fin": ctr.fin_contrat.date_fin,
                    "motif": ctr.fin_contrat.motif,
                }
            )

    return EmployeeSnap(
        key=_employee_key(ind),
        nir=_norm_nir(ind.nir),
        nom=(ind.nom or "").upper(),
        prenom=(ind.prenom or "").upper(),
        matricule=(ind.matricule or "").upper(),
        ntt=(ind.ntt or "").strip(),
        nature_contrat=_norm_code(ctr.nature) if ctr else "",
        date_debut_contrat=ctr.date_debut if ctr else "",
        numero_contrat=ctr.numero_contrat if ctr else "",
        brut=float(totals.get("brut") or 0),
        net_imposable=float(totals.get("net_imposable") or 0),
        net_verse=float(ver.net_verse if ver else 0),
        pas=float(totals.get("pas") or 0),
        heures=float(totals.get("heures") or 0),
        remunerations=remunerations,
        cotisations=cotisations,
        bases=bases,
        events=events,
    )


def normalize_etablissement(
    etab: EtablissementBlock,
    *,
    period: str,
    norme: str,
    source_file: str = "",
) -> EstablishmentSnap:
    employees: Dict[str, EmployeeSnap] = {}
    brut = net = pas = 0.0
    for ind in etab.individus:
        snap = normalize_individu(ind)
        employees[snap.key] = snap
        brut += snap.brut
        net += snap.net_imposable
        pas += snap.pas
    return EstablishmentSnap(
        siret=(etab.siret or "").replace(" ", ""),
        period=period,
        norme=norme,
        headcount=len(employees),
        brut=round(brut, 2),
        net_imposable=round(net, 2),
        pas=round(pas, 2),
        employees=employees,
        source_file=source_file,
    )


def normalize_parsed_dsn(parsed: ParsedDsnSet) -> DsnNormalizedSnapshot:
    snaps: Dict[str, EstablishmentSnap] = {}
    warnings = list(parsed.warnings or [])
    etabs = parsed.etablissements_by_siret()
    # période / norme depuis le premier fichier
    period = parsed.period_min or ""
    norme = ""
    source = ""
    if parsed.files:
        norme = parsed.files[0].envoi.norme or ""
        source = parsed.files[0].file_name
        warnings.extend(parsed.files[0].parse_warnings or [])
    for siret, etab in etabs.items():
        snaps[siret] = normalize_etablissement(
            etab, period=period, norme=norme, source_file=source
        )
    return DsnNormalizedSnapshot(establishments=snaps, warnings=warnings)


def normalize_dsn_bytes(
    content: bytes,
    *,
    file_name: str = "dsn.dsn",
) -> DsnNormalizedSnapshot:
    parsed = parse_dsn_files([(file_name, content)])
    return normalize_parsed_dsn(parsed)
