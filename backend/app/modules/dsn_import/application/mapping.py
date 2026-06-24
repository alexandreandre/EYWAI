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
    map_sexe,
    map_statut_cadre,
    map_temps_partiel_dsn,
    normalize_date_dsn,
)
from app.modules.dsn_import.application.cumuls import extract_monthly_totals
from app.modules.dsn_import.domain.establishment_extract import enrich_establishment_payload
from app.modules.dsn_import.domain.dsn_absence_exit_mapping import (
    build_absence_payload_from_arret,
    build_absence_payload_from_suspension,
    build_exit_payload_from_fin_contrat,
)
from app.modules.dsn_import.domain.psc import build_specificites_paie_psc
from app.modules.employees.domain.rules import is_temps_travail_incoherent

# Champs modifiables en preview (clé payload -> libellé UI)
EDITABLE_FIELDS: Dict[str, Dict[str, str]] = {
    "group": {
        "group_name": "Raison sociale",
        "siren": "SIREN",
    },
    "establishment": {
        "company_name": "Raison sociale",
        "siret": "SIRET",
        "code_naf": "Code NAF",
        "adresse_rue": "Adresse",
        "adresse_code_postal": "Code postal",
        "adresse_ville": "Ville",
        "taux_at_mp": "Taux AT/MP (%)",
        "paie_jour_de_fin": "Jour fin période paie",
        "paie_occurrence": "Occurrence paie",
    },
    "employee": {
        "last_name": "Nom",
        "first_name": "Prénom",
        "nir": "NIR",
        "email": "Email",
        "job_title": "Poste",
        "hire_date": "Date d'embauche",
        "salaire_brut": "Salaire brut mensuel",
        "is_temps_partiel": "Temps partiel",
        "duree_hebdomadaire": "Durée hebdomadaire (h)",
    },
}


REVIEW_REASON_LABELS: Dict[str, str] = {
    "brut_absent": "Brut non extrait de la DSN",
    "nir_incomplet": "NIR absent (NTT ou matricule utilisé)",
    "temps_partiel_incoherent": "Temps partiel détecté sans durée hebdo (< 35 h)",
}


def compute_review_reasons_from_payload(
    payload: Dict[str, Any],
    *,
    effective_action: str = "create",
    is_existing: bool = False,
) -> List[str]:
    """Motifs nécessitant une relecture RH (non bloquants pour l'import)."""
    reasons: List[str] = []
    brut = float((payload.get("salaire_de_base") or {}).get("valeur") or 0)
    if brut <= 0 and not (is_existing and effective_action == "skip"):
        reasons.append("brut_absent")
    if not payload.get("nir") and (payload.get("ntt") or payload.get("matricule")):
        reasons.append("nir_incomplet")
    if is_temps_travail_incoherent(
        payload.get("is_temps_partiel"),
        payload.get("duree_hebdomadaire"),
    ):
        reasons.append("temps_partiel_incoherent")
    return reasons


def apply_review_flags(item: Dict[str, Any], *, effective_action: Optional[str] = None) -> None:
    """Met à jour needs_review / review_reasons sur un item salarié."""
    if item.get("item_type") != "employee":
        return
    payload = item.get("mapped_payload") or {}
    action = effective_action or item.get("action") or "create"
    reasons = compute_review_reasons_from_payload(
        payload,
        effective_action=action,
        is_existing=bool(item.get("is_existing")),
    )
    item["needs_review"] = bool(reasons)
    item["review_reasons"] = reasons
    cols = dict(item.get("preview_columns") or {})
    cols["brut"] = (payload.get("salaire_de_base") or {}).get("valeur")
    cols["is_temps_partiel"] = payload.get("is_temps_partiel")
    cols["duree_hebdomadaire"] = payload.get("duree_hebdomadaire")
    item["preview_columns"] = cols


def normalize_employee_edits(edits: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise les éditions preview salarié (clé plate salaire_brut -> salaire_de_base)."""
    out = dict(edits)
    if "salaire_brut" in out:
        raw = out.pop("salaire_brut")
        try:
            val = float(str(raw).replace(",", ".").replace(" ", ""))
        except (ValueError, TypeError):
            val = 0.0
        sb = out.get("salaire_de_base")
        if not isinstance(sb, dict):
            sb = {"type": "mensuel"}
        sb = dict(sb)
        sb["valeur"] = round(val, 2)
        sb["a_verifier"] = val <= 0
        out["salaire_de_base"] = sb

    if "is_temps_partiel" in out or "duree_hebdomadaire" in out:
        from app.modules.employees.domain.rules import normalize_temps_travail_fields

        raw_tp = out.get("is_temps_partiel")
        if isinstance(raw_tp, str):
            raw_tp = raw_tp.strip().lower() in ("1", "true", "oui", "yes")
        elif raw_tp is not None:
            raw_tp = bool(raw_tp)

        raw_duree = out.get("duree_hebdomadaire")
        try:
            duree = float(str(raw_duree).replace(",", ".")) if raw_duree not in (None, "") else None
        except (ValueError, TypeError):
            duree = None

        is_tp, heures = normalize_temps_travail_fields(raw_tp, duree)
        out["is_temps_partiel"] = is_tp
        out["duree_hebdomadaire"] = heures

    return out


def build_review_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Agrège les motifs de relecture pour le résumé preview."""
    by_reason: Dict[str, int] = {}
    total = 0
    for it in items:
        if it.get("item_type") != "employee" or not it.get("needs_review"):
            continue
        total += 1
        for reason in it.get("review_reasons") or []:
            by_reason[reason] = by_reason.get(reason, 0) + 1
    return {"total": total, "by_reason": by_reason}


def build_actions_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Agrège les actions create/update/skip par type d'item."""
    totals = {"create": 0, "update": 0, "skip": 0}
    by_type: Dict[str, Dict[str, int]] = {}
    for it in items:
        action = it.get("action", "create")
        if action not in totals:
            action = "create"
        totals[action] = totals.get(action, 0) + 1
        item_type = it.get("item_type", "other")
        bucket = by_type.setdefault(item_type, {"create": 0, "update": 0, "skip": 0})
        bucket[action] = bucket.get(action, 0) + 1
    return {"totals": totals, "by_type": by_type}


def enrich_summary_from_items(
    summary: Dict[str, Any],
    parsed: ParsedDsnSet,
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Complète le résumé avec SIRET, IDCC, agrégats d'actions."""
    etabs = parsed.etablissements_by_siret()
    sirets = list(etabs.keys())
    summary = {**summary}
    summary["siret"] = sirets[0] if len(sirets) == 1 else (sirets[0] if sirets else None)
    summary["sirets"] = sirets

    idcc_map = collect_idcc_by_establishment(parsed)
    primary_idcc = None
    for idccs in idcc_map.values():
        if idccs:
            primary_idcc = idccs[0]
            break
    summary["primary_idcc"] = primary_idcc

    non_cumul = [it for it in items if it.get("item_type") != "cumul"]
    summary["actions_summary"] = build_actions_summary(non_cumul)
    summary["has_existing_dossier"] = any(
        it.get("action") == "update"
        for it in non_cumul
        if it.get("item_type") in ("group", "establishment")
    )
    return summary


def _is_generic_company_name(name: Optional[str]) -> bool:
    """Nom générique généré par l'import (pas une raison sociale DSN)."""
    if not name or not str(name).strip():
        return True
    n = str(name).strip()
    if n.startswith("Établissement "):
        return True
    if n.startswith("Groupe ") and n.replace("Groupe ", "").isdigit():
        return True
    return False


def apply_legal_name_to_preview(
    items: List[Dict[str, Any]],
    legal_name: str,
    *,
    single_establishment: bool = False,
) -> None:
    """
    Applique la raison sociale (DSN / SIRENE) sur l'entreprise, pas sur le groupe EYWAI.
    Le groupe reste un conteneur organisationnel discret.
    """
    clean = legal_name.strip()
    if not clean:
        return
    short = clean.split("(")[0].strip() or clean

    for it in items:
        item_type = it.get("item_type")
        payload = it.get("mapped_payload") or {}

        if item_type == "establishment":
            current = payload.get("company_name") or ""
            if _is_generic_company_name(current):
                payload["company_name"] = clean
                payload["raison_sociale"] = clean
                it["label"] = clean
                it["mapped_payload"] = payload

        elif item_type == "group":
            payload["group_name"] = f"Groupe {short}"
            payload["description"] = "Conteneur EYWAI — créé automatiquement à l'import DSN"
            payload["_scaffold"] = True
            it["label"] = f"Groupe {short}"
            it["mapped_payload"] = payload
            if single_establishment:
                it["is_scaffold"] = True
                it["label"] = f"Conteneur groupe ({short})"


def map_group_payload(parsed: ParsedDsnSet) -> Dict[str, Any]:
    siren = parsed.siren or ""
    raison = _find_raison_sociale(parsed)
    short = raison.split("(")[0].strip() if raison else ""
    return {
        "group_name": f"Groupe {short}" if short else f"Groupe {siren}",
        "siren": siren,
        "description": "Conteneur EYWAI — créé automatiquement à l'import DSN",
        "is_active": True,
    }


def _find_raison_sociale(parsed: ParsedDsnSet) -> str:
    for f in parsed.files:
        if f.entreprise.raison_sociale and not _looks_like_code(f.entreprise.raison_sociale):
            return f.entreprise.raison_sociale
        if f.etablissement_s20.raison_sociale and not _looks_like_code(f.etablissement_s20.raison_sociale):
            return f.etablissement_s20.raison_sociale
        if f.etablissement.raison_sociale and not _looks_like_code(f.etablissement.raison_sociale):
            return f.etablissement.raison_sociale
    return ""


def _default_establishment_name(etab: EtablissementBlock, siret: str) -> str:
    if etab.adresse_ville:
        return f"Établissement {etab.adresse_ville} ({siret[-5:]})"
    return f"Établissement {siret}"


def map_establishment_payload(
    etab: EtablissementBlock, siren: str, parsed: ParsedDsnSet
) -> Dict[str, Any]:
    addr = build_address_dict(etab.adresse_rue, etab.adresse_cp, etab.adresse_ville)
    raison = etab.raison_sociale or ""
    if not raison or _looks_like_code(raison):
        raison = _find_raison_sociale(parsed)
    if not raison or _looks_like_code(raison):
        raison = _default_establishment_name(etab, etab.siret)
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
    return enrich_establishment_payload(payload, etab, parsed)


def _looks_like_code(value: str) -> bool:
    """Évite d'utiliser un NIC/NAF comme raison sociale."""
    clean = value.replace(" ", "")
    if not clean:
        return True
    if clean.isdigit() and len(clean) <= 5:
        return True
    if len(clean) <= 6 and any(c.isdigit() for c in clean) and any(c.isalpha() for c in clean):
        return True
    return False


def _employee_label(ind: IndividuBlock) -> str:
    name = f"{ind.prenom} {ind.nom}".strip()
    if name:
        return name
    if ind.matricule:
        return f"Matricule {ind.matricule}"
    return ind.identifiant or "Salarié"


def _estimate_brut_from_contrat(contrat: ContratBlock) -> float:
    from app.modules.dsn_import.domain.model import IndividuBlock

    stub = IndividuBlock(contrats=[contrat])
    return extract_monthly_totals(stub).get("brut", 0.0)


def _extract_pas(contrat: ContratBlock) -> Dict[str, Any]:
    """Reconstitue le prélèvement à la source depuis le dernier versement DSN.

    On retient le versement le plus récent porteur d'un taux PAS afin d'initialiser
    `specificites_paie.prelevement_a_la_source.taux` (consommé par le moteur de paie).
    """
    candidates = [v for v in contrat.versements if v.pas_taux or v.pas or v.montant_soumis_pas]
    if not candidates:
        return {}

    def _sort_key(ver: Any) -> str:
        d = (ver.date_versement or "").replace("-", "").replace("/", "")
        if len(d) == 8 and d.isdigit():
            return f"{d[4:8]}{d[2:4]}{d[0:2]}"
        return d

    ver = max(candidates, key=_sort_key)
    pas: Dict[str, Any] = {}
    if ver.pas_taux:
        pas["taux"] = round(ver.pas_taux, 4)
    if ver.pas_type:
        pas["type_taux"] = ver.pas_type
    if ver.pas_identifiant:
        pas["identifiant_taux"] = ver.pas_identifiant
    if ver.montant_soumis_pas:
        pas["assiette_dsn"] = round(ver.montant_soumis_pas, 2)
    if ver.pas:
        pas["montant_dsn"] = round(ver.pas, 2)
    return pas


def map_employee_payload(
    ind: IndividuBlock,
    etab: EtablissementBlock,
    siret: str,
) -> Dict[str, Any]:
    contrat = ind.contrats[0] if ind.contrats else ContratBlock()
    is_tp, heures = map_temps_partiel_dsn(
        contrat.modalite_temps,
        contrat.unite_quotite,
        contrat.quotite,
        contrat.quotite_reference,
    )
    brut = _estimate_brut_from_contrat(contrat)
    hire = normalize_date_dsn(contrat.date_debut) or normalize_date_dsn(contrat.rubriques.get("S21.G00.40.001", ""))
    end = normalize_date_dsn(contrat.date_fin)

    email_placeholder = _placeholder_email(ind, siret)
    contract_type = map_contract_type(contrat.nature)
    pas = _extract_pas(contrat)
    sexe = map_sexe(ind.sexe)
    psc_block = build_specificites_paie_psc(contrat, organismes_psc=etab.organismes_psc)
    psc_meta = psc_block.pop("_psc_meta", {})

    anciennete_dates = [
        normalize_date_dsn(a.date_debut)
        for a in contrat.anciennetes
        if normalize_date_dsn(a.date_debut)
    ]
    date_anciennete = min(anciennete_dates) if anciennete_dates else hire

    primes_dsn = [
        {
            "code": p.code,
            "montant": round(p.montant, 2),
            "date_debut": normalize_date_dsn(p.date_debut),
            "date_fin": normalize_date_dsn(p.date_fin),
        }
        for v in contrat.versements
        for p in v.primes
        if p.montant > 0
    ]

    payload: Dict[str, Any] = {
        "first_name": ind.prenom,
        "last_name": ind.nom,
        "email": email_placeholder,
        "nir": ind.nir or None,
        "ntt": ind.ntt or None,
        "matricule": ind.matricule or None,
        "date_naissance": normalize_date_dsn(ind.date_naissance),
        "lieu_naissance": ind.lieu_naissance or "Non renseigné",
        "nationalite": ind.nationalite or "Française",
        "adresse": build_address_dict(ind.adresse_rue, ind.adresse_cp, ind.adresse_ville),
        "coordonnees_bancaires": {"iban": "", "bic": ""},
        "hire_date": hire,
        "contract_type": contract_type,
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
            "libelle_emploi": contrat.libelle_emploi or None,
            "statut_categoriel": map_statut_cadre(contrat.statut),
            "code_statut_dsn": contrat.statut or None,
            "position": contrat.position_conv or None,
            "dispositif_politique_publique": contrat.dispositif or None,
            "numero_contrat_dsn": contrat.numero_contrat or None,
            "classification_dsn": contrat.rubriques.get("S21.G00.40.040"),
            "niveau_dsn": contrat.rubriques.get("S21.G00.40.041"),
            "taux_at_individuel_dsn": contrat.rubriques.get("S21.G00.40.043"),
        },
        "elements_variables": {"primes_dsn": primes_dsn} if primes_dsn else {},
        "specificites_paie": {
            **psc_block,
            "prelevement_a_la_source": pas,
            "dsn_anciennete": {
                "date_anciennete": date_anciennete,
                "segments": len(contrat.anciennetes),
            }
            if contrat.anciennetes
            else None,
        },
        "collective_agreement_idcc": contrat.idcc,
        # Salariés en activité chez l'établisseur externe — pas le flux onboarding EYWAI.
        "employment_status": "actif",
        "import_source": "dsn",
        "_psc_meta": psc_meta,
        "_needs_review": brut <= 0,
    }

    # Champs d'état civil persistés uniquement si la migration correspondante est
    # appliquée (cf. _commit_employee qui filtre selon les colonnes réelles).
    if sexe:
        payload["sexe"] = sexe
    if ind.nom_usage:
        payload["nom_usage"] = ind.nom_usage.strip()

    # Alternance : la date de début d'exécution est le fait générateur du régime
    # apprenti (PAS, cotisations). On l'initialise sur la date de début du contrat.
    if contract_type in ("apprentissage", "professionnalisation") and hire:
        payload["date_debut_execution"] = hire
        payload["date_conclusion_contrat"] = hire

    return payload


def _placeholder_email(ind: IndividuBlock, siret: str) -> str:
    """Email technique pour salarié importé (compte Auth différé)."""
    id_tail = (ind.identifiant or "000")[-6:]
    slug = f"{ind.prenom}.{ind.nom}".lower().replace(" ", "-")
    slug = "".join(c for c in slug if c.isalnum() or c in ".-_") or "salarie"
    return f"import.{slug}.{id_tail}@{siret[:9]}.dsn-import.local"


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


def _build_absence_exit_items(
    etab: EtablissementBlock,
    siret: str,
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for ind in etab.individus:
        ident = ind.identifiant or ind.nom
        label = _employee_label(ind)
        contrat = ind.contrats[0] if ind.contrats else None
        if not contrat:
            continue

        if contrat.fin_contrat and contrat.fin_contrat.date_fin:
            exit_payload = build_exit_payload_from_fin_contrat(
                contrat.fin_contrat,
                siret=siret,
                nir=ind.nir or ident,
                employee_label=label,
            )
            if exit_payload:
                ref = f"exit:{siret}:{ident}:{exit_payload['source_key']}"
                items.append(
                    {
                        "item_type": "exit",
                        "source_ref": ref,
                        "action": "create",
                        "mapped_payload": exit_payload,
                        "label": f"Sortie — {label}",
                        "preview_columns": {
                            "exit_type": exit_payload.get("exit_type"),
                            "last_working_day": exit_payload.get("last_working_day"),
                            "motif_dsn": exit_payload.get("motif_dsn"),
                        },
                    }
                )

        for arret in contrat.arrets:
            abs_payload = build_absence_payload_from_arret(
                arret,
                siret=siret,
                nir=ind.nir or ident,
                employee_label=label,
            )
            if not abs_payload:
                continue
            ref = f"abs:{siret}:{ident}:{abs_payload['source_key']}"
            items.append(
                {
                    "item_type": "absence",
                    "source_ref": ref,
                    "action": "create",
                    "mapped_payload": abs_payload,
                    "label": f"Arrêt — {label}",
                    "preview_columns": {
                        "absence_type": abs_payload.get("absence_type"),
                        "date_debut": abs_payload.get("date_debut"),
                        "date_fin": abs_payload.get("date_fin"),
                    },
                }
            )

        for suspension in contrat.suspensions:
            abs_payload = build_absence_payload_from_suspension(
                suspension,
                siret=siret,
                nir=ind.nir or ident,
                employee_label=label,
            )
            if not abs_payload:
                continue
            ref = f"abs:{siret}:{ident}:{abs_payload['source_key']}"
            items.append(
                {
                    "item_type": "absence",
                    "source_ref": ref,
                    "action": "create",
                    "mapped_payload": abs_payload,
                    "label": f"Suspension — {label}",
                    "preview_columns": {
                        "absence_type": abs_payload.get("absence_type"),
                        "date_debut": abs_payload.get("date_debut"),
                        "date_fin": abs_payload.get("date_fin"),
                    },
                }
            )

    return items


def build_preview_items(parsed: ParsedDsnSet) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Construit les items de preview et le résumé."""
    items: List[Dict[str, Any]] = []
    siren = parsed.siren or ""

    etabs = parsed.etablissements_by_siret()
    single_establishment = len(etabs) == 1
    group_payload = map_group_payload(parsed)
    if single_establishment:
        group_payload["_scaffold"] = True
    items.append(
        {
            "item_type": "group",
            "source_ref": f"group:{siren}",
            "action": "create",
            "mapped_payload": group_payload,
            "label": group_payload.get("group_name"),
            "editable_fields": EDITABLE_FIELDS["group"],
            "is_scaffold": single_establishment,
        }
    )

    idcc_map = collect_idcc_by_establishment(parsed)

    for siret, etab in etabs.items():
        etab_payload = map_establishment_payload(etab, siren, parsed)
        items.append(
            {
                "item_type": "establishment",
                "source_ref": f"etab:{siret}",
                "action": "create",
                "mapped_payload": etab_payload,
                "label": etab_payload.get("company_name") or siret,
                "employee_count": len(etab.individus),
                "editable_fields": EDITABLE_FIELDS["establishment"],
                "payroll_extract": etab_payload.get("_dsn_extracted") or {},
                "payroll_conflicts": etab_payload.get("_payroll_conflicts") or {},
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
            ident = ind.identifiant or ind.nom
            ref = f"emp:{siret}:{ident}"
            emp_item = {
                "item_type": "employee",
                "source_ref": ref,
                "action": "create",
                "mapped_payload": emp_payload,
                "label": _employee_label(ind),
                "preview_columns": {
                    "nir": emp_payload.get("nir") or emp_payload.get("matricule") or "—",
                    "job_title": emp_payload.get("job_title"),
                    "hire_date": emp_payload.get("hire_date"),
                    "brut": emp_payload.get("salaire_de_base", {}).get("valeur"),
                    "is_temps_partiel": emp_payload.get("is_temps_partiel"),
                    "duree_hebdomadaire": emp_payload.get("duree_hebdomadaire"),
                },
                "editable_fields": EDITABLE_FIELDS["employee"],
            }
            apply_review_flags(emp_item)
            items.append(emp_item)

        items.extend(_build_absence_exit_items(etab, siret))

    summary = {
        "siren": siren,
        "period_min": parsed.period_min,
        "period_max": parsed.period_max,
        "establishment_count": len(etabs),
        "employee_count": sum(len(e.individus) for e in etabs.values()),
        "file_count": len(parsed.files),
    }

    raison = _find_raison_sociale(parsed)
    if raison:
        apply_legal_name_to_preview(items, raison, single_establishment=single_establishment)

    return items, summary
