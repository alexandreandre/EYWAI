"""Mapping DSN -> payloads entreprise / salarié / CC."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.modules.dsn_import.domain.model import (
    ContratBlock,
    EtablissementBlock,
    IndividuBlock,
    ParsedDsnSet,
)
from app.modules.dsn_import.domain.normalize import (
    build_address_dict,
    flatten_company_address,
    map_contract_type,
    map_statut_cadre,
    map_temps_partiel,
    normalize_date_dsn,
)
from app.modules.dsn_import.domain.rubriques import REMUNERATION_BRUT_TYPES


def map_group_payload(parsed: ParsedDsnSet) -> Dict[str, Any]:
    siren = parsed.siren or ""
    raison = ""
    for f in parsed.files:
        if f.entreprise.raison_sociale:
            raison = f.entreprise.raison_sociale
            break
        if f.etablissement.raison_sociale:
            raison = f.etablissement.raison_sociale
            break
    return {
        "group_name": raison or f"Groupe {siren}",
        "siren": siren,
        "description": "Importé depuis DSN",
        "is_active": True,
    }


def map_establishment_payload(
    etab: EtablissementBlock, siren: str, parsed: ParsedDsnSet
) -> Dict[str, Any]:
    addr = build_address_dict(etab.adresse_rue, etab.adresse_cp, etab.adresse_ville)
    raison = etab.raison_sociale or ""
    if not raison:
        for f in parsed.files:
            if f.entreprise.raison_sociale:
                raison = f.entreprise.raison_sociale
                break
    payload = {
        "company_name": raison,
        "raison_sociale": raison,
        "siret": etab.siret,
        "siren": siren or etab.siret[:9],
        "code_naf": etab.code_naf,
        "naf_ape": etab.code_naf,
        "effectif": etab.effectif or None,
        "is_active": True,
        **flatten_company_address(addr),
    }
    return payload


def _estimate_brut_from_contrat(contrat: ContratBlock) -> float:
    total = 0.0
    for ver in contrat.versements:
        for rem in ver.remunerations:
            if rem.type_code in REMUNERATION_BRUT_TYPES or not rem.type_code:
                total += rem.montant
    return round(total, 2)


def map_employee_payload(
    ind: IndividuBlock,
    etab: EtablissementBlock,
    siret: str,
) -> Dict[str, Any]:
    contrat = ind.contrats[0] if ind.contrats else ContratBlock()
    is_tp, heures = map_temps_partiel(contrat.modalite_temps, contrat.quotite)
    brut = _estimate_brut_from_contrat(contrat)
    hire = normalize_date_dsn(contrat.date_debut) or normalize_date_dsn(contrat.rubriques.get("S21.G00.40.001", ""))
    end = normalize_date_dsn(contrat.date_fin)

    email_placeholder = _placeholder_email(ind, siret)

    return {
        "first_name": ind.prenom,
        "last_name": ind.nom,
        "email": email_placeholder,
        "nir": ind.nir,
        "date_naissance": normalize_date_dsn(ind.date_naissance),
        "lieu_naissance": ind.lieu_naissance or "Non renseigné",
        "nationalite": ind.nationalite or "Française",
        "adresse": build_address_dict(ind.adresse_rue, ind.adresse_cp, ind.adresse_ville),
        "coordonnees_bancaires": {"iban": "", "bic": ""},
        "hire_date": hire,
        "contract_type": map_contract_type(contrat.nature),
        "contract_end_date": end,
        "statut": map_statut_cadre(contrat.statut),
        "job_title": contrat.libelle_emploi or contrat.pcs or "Salarié",
        "is_temps_partiel": is_tp,
        "duree_hebdomadaire": heures,
        "salaire_de_base": {
            "valeur": brut,
            "type": "mensuel",
            "a_verifier": brut <= 0,
        },
        "classification_conventionnelle": {
            "idcc": contrat.idcc,
            "pcs": contrat.pcs,
        },
        "elements_variables": {},
        "specificites_paie": {
            "prevoyance": {"adhesion": False},
            "mutuelle": {"adhesion": False},
            "prelevement_a_la_source": {},
        },
        "collective_agreement_idcc": contrat.idcc,
        "employment_status": "en_onboarding",
        "import_source": "dsn",
        "_needs_review": brut <= 0 or not ind.adresse_rue,
    }


def _placeholder_email(ind: IndividuBlock, siret: str) -> str:
    """Email technique pour salarié importé (compte Auth différé)."""
    nir_tail = (ind.nir or "000")[-6:]
    slug = f"{ind.prenom}.{ind.nom}".lower().replace(" ", "-")
    slug = "".join(c for c in slug if c.isalnum() or c in ".-_") or "salarie"
    return f"import.{slug}.{nir_tail}@{siret[:9]}.dsn-import.local"


def collect_idcc_by_establishment(parsed: ParsedDsnSet) -> Dict[str, List[str]]:
    """Retourne {siret: [idcc, ...]} uniques."""
    out: Dict[str, set] = {}
    for siret, etab in parsed.etablissements_by_siret().items():
        idccs: set = set()
        for ind in etab.individus:
            for ctr in ind.contrats:
                if ctr.idcc:
                    idccs.add(ctr.idcc.strip())
        if idccs:
            out[siret] = sorted(idccs)
    return {k: list(v) for k, v in out.items()}


def build_preview_items(parsed: ParsedDsnSet) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Construit les items de preview et le résumé."""
    items: List[Dict[str, Any]] = []
    siren = parsed.siren or ""

    group_payload = map_group_payload(parsed)
    items.append(
        {
            "item_type": "group",
            "source_ref": f"group:{siren}",
            "action": "create",
            "mapped_payload": group_payload,
            "label": group_payload.get("group_name"),
        }
    )

    idcc_map = collect_idcc_by_establishment(parsed)
    etabs = parsed.etablissements_by_siret()

    for siret, etab in etabs.items():
        etab_payload = map_establishment_payload(etab, siren, parsed)
        items.append(
            {
                "item_type": "establishment",
                "source_ref": f"etab:{siret}",
                "action": "create",
                "mapped_payload": etab_payload,
                "label": etab_payload.get("company_name"),
                "employee_count": len(etab.individus),
            }
        )
        for idcc in idcc_map.get(siret, []):
            items.append(
                {
                    "item_type": "collective_agreement",
                    "source_ref": f"cc:{siret}:{idcc}",
                    "action": "create",
                    "mapped_payload": {"siret": siret, "idcc": idcc},
                    "label": f"IDCC {idcc}",
                }
            )
        for ind in etab.individus:
            emp_payload = map_employee_payload(ind, etab, siret)
            ref = f"emp:{siret}:{ind.nir or ind.nom}"
            items.append(
                {
                    "item_type": "employee",
                    "source_ref": ref,
                    "action": "create",
                    "mapped_payload": emp_payload,
                    "label": f"{ind.prenom} {ind.nom}".strip(),
                    "needs_review": emp_payload.get("_needs_review", False),
                }
            )

    summary = {
        "siren": siren,
        "period_min": parsed.period_min,
        "period_max": parsed.period_max,
        "establishment_count": len(etabs),
        "employee_count": sum(len(e.individus) for e in etabs.values()),
        "file_count": len(parsed.files),
    }
    return items, summary
