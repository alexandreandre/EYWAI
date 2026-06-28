"""Contrôles non bloquants : convention collective et cohérence paie."""

from __future__ import annotations

from typing import Any, Dict, List

from app.modules.collective_agreements.application.idcc_resolution import (
    resolve_minimum_for_classification,
)
from app.modules.collective_agreements.rules.constants import SMH_NATIONAL_IDCC
from app.modules.collective_agreements.rules.resolver import (
    code_postal_from_entreprise,
    resolve_salaires_minima,
)

NET_SUPERIEUR_BRUT_MESSAGE = "Net > Brut"


def _is_smh_national_idcc(idcc: str) -> bool:
    normalized = idcc.strip()
    if normalized in SMH_NATIONAL_IDCC:
        return True
    stripped = normalized.lstrip("0") or "0"
    return stripped in {x.lstrip("0") for x in SMH_NATIONAL_IDCC}


def _alert(
    *,
    code: str,
    message: str,
    critique: bool = False,
    donnee_non_officielle: bool = False,
) -> Dict[str, Any]:
    return {
        "code": code,
        "critique": critique,
        "severity": "warning" if critique else "info",
        "message": message,
        "donnee_non_officielle": donnee_non_officielle,
    }


def _minimum_conventionnel_ajuste(contexte, minimum: float) -> float:
    """Prorata temps partiel (< 35 h) sur le minimum mensuel SMH."""
    contrat = (contexte.contrat.get("contrat") or {}) if hasattr(contexte, "contrat") else {}
    temps = contrat.get("temps_travail") or {}
    try:
        duree = float(temps.get("duree_hebdomadaire") or 35)
    except (TypeError, ValueError):
        duree = 35.0
    if 0 < duree < 35:
        return round(minimum * duree / 35.0, 2)
    return minimum


def controle_convention_collective(contexte, salaire_brut: float) -> List[Dict[str, Any]]:
    """
    Vérifie la cohérence salaire / convention collective (non bloquant).
    Les alertes sont stockées dans payslip_data.alertes_baremes pour la RH.
    """
    if getattr(contexte, "is_alternant", False):
        return []

    cc = (
        contexte.contrat.get("remuneration", {}).get("convention_collective", {}) or {}
    )
    idcc = str(cc.get("idcc") or "").strip()
    if not idcc:
        return []

    libelle_cc = str(cc.get("libelle") or cc.get("name") or f"IDCC {idcc}").strip()
    regles_cc = contexte.baremes.get("conventions_collectives", {}).get(
        f"idcc_{idcc}", {}
    )
    if not regles_cc and idcc.isdigit():
        for variant in (idcc.zfill(4), idcc.lstrip("0") or "0"):
            regles_cc = contexte.baremes.get("conventions_collectives", {}).get(
                f"idcc_{variant}", {}
            )
            if regles_cc:
                break

    alertes: List[Dict[str, Any]] = []

    if not regles_cc:
        alertes.append(
            _alert(
                code="cc_regles_absentes",
                critique=True,
                message=(
                    f"Aucune règle paie extraite pour {libelle_cc} (IDCC {idcc}). "
                    "Le moteur ne peut pas vérifier les minima conventionnels."
                ),
            )
        )
        return alertes

    classification = (
        contexte.contrat.get("remuneration", {}).get("classification_conventionnelle")
        or {}
    )
    has_lookup_key = any(
        classification.get(field) is not None
        for field in ("coefficient", "classe_emploi", "classe")
    )
    if not has_lookup_key:
        alertes.append(
            _alert(
                code="cc_classification_manquante",
                critique=True,
                message=(
                    f"Classification conventionnelle absente sur la fiche salarié "
                    f"({libelle_cc}). Impossible de contrôler le minimum conventionnel."
                ),
            )
        )
        return alertes

    minima = resolve_salaires_minima(
        regles_cc,
        code_postal=code_postal_from_entreprise(contexte.entreprise),
    )
    if not minima:
        alertes.append(
            _alert(
                code="cc_grille_vide",
                critique=True,
                message=(
                    f"Aucune grille salariale disponible pour {libelle_cc} "
                    f"(IDCC {idcc}). Mettez à jour la convention depuis Légifrance."
                ),
            )
        )
        return alertes

    min_row = resolve_minimum_for_classification(
        minima, classification, idcc=idcc
    )
    if min_row is None:
        coeff = classification.get("coefficient")
        try:
            coeff_num = float(coeff) if coeff is not None else None
        except (TypeError, ValueError):
            coeff_num = None

        if _is_smh_national_idcc(idcc) and coeff_num is not None and coeff_num > 18:
            message = (
                f"Classe d'emploi absente ou invalide pour {libelle_cc} "
                f"(coefficient de position {coeff_num:g} non utilisable pour le "
                f"barème SMH). Renseignez la classe (1-18) sur la fiche salarié."
            )
        elif coeff_num is not None:
            message = (
                f"Coefficient {coeff_num:g} absent de la grille {libelle_cc}. "
                "Vérifiez la classification ou mettez à jour la convention."
            )
        else:
            message = (
                f"Classification absente de la grille {libelle_cc}. "
                "Vérifiez la classification ou mettez à jour la convention."
            )
        alertes.append(
            _alert(
                code="cc_coefficient_hors_grille",
                critique=True,
                message=message,
            )
        )
        return alertes

    minimum_applicable = float(min_row.get("valeur") or 0)
    minimum_applicable = _minimum_conventionnel_ajuste(contexte, minimum_applicable)
    libelle_poste = min_row.get("libelle")
    try:
        coeff_affiche = float(min_row.get("coefficient") or 0)
    except (TypeError, ValueError):
        coeff_affiche = 0.0

    if salaire_brut + 0.01 < minimum_applicable:
        poste = f" ({libelle_poste})" if libelle_poste else ""
        alertes.append(
            _alert(
                code="cc_salaire_sous_minimum",
                critique=True,
                message=(
                    f"Salaire brut ({salaire_brut:.2f} €) inférieur au minimum "
                    f"conventionnel{poste} pour le coefficient {coeff_affiche:g} "
                    f"({minimum_applicable:.2f} € — {libelle_cc})."
                ),
            )
        )

    return alertes


def controle_prime_anciennete(contexte) -> List[Dict[str, Any]]:
    """Alertes non bloquantes liées à la prime d'ancienneté CCN."""
    from app.modules.collective_agreements.rules.prime_calcul import (
        check_eligibilite_prime_anciennete,
        compute_anciennete_annees,
        resolve_prime_anciennete_config,
    )

    cc = (
        contexte.contrat.get("remuneration", {}).get("convention_collective", {}) or {}
    )
    idcc = str(cc.get("idcc") or "").strip()
    if not idcc:
        return []

    regles_cc = contexte.baremes.get("conventions_collectives", {}).get(
        f"idcc_{idcc}", {}
    )
    if not regles_cc and idcc.isdigit():
        for variant in (idcc.zfill(4), idcc.lstrip("0") or "0"):
            regles_cc = contexte.baremes.get("conventions_collectives", {}).get(
                f"idcc_{variant}", {}
            )
            if regles_cc:
                break

    regles_prime = regles_cc.get("prime_anciennete") or {}
    if not regles_prime:
        return []

    date_entree = getattr(contexte, "date_anciennete_prime", None) or contexte.date_entree
    if not date_entree:
        return []

    from datetime import date as date_cls

    ref = getattr(contexte, "date_fin_periode", None) or date_cls.today()
    resolved = resolve_prime_anciennete_config(regles_prime, contexte.entreprise)
    anciennete = compute_anciennete_annees(date_entree, ref, mode="floor")
    from app.modules.collective_agreements.rules.prime_calcul import cap_anciennete_annees

    anciennete = cap_anciennete_annees(anciennete, regles_prime)
    eligible, motif = check_eligibilite_prime_anciennete(
        regles_prime=regles_prime,
        contrat=contexte.contrat,
        anciennete_annees=anciennete,
        statut=contexte.statut_salarie,
        min_annees_override=resolved.get("min_annees_override"),
    )

    alertes: List[Dict[str, Any]] = []
    if not eligible:
        from app.modules.collective_agreements.rules.prime_calcul import (
            _normalize_statut_label,
        )

        statuts_exclus = (regles_prime.get("eligibilite") or {}).get(
            "statuts_exclus"
        ) or []
        statut_n = _normalize_statut_label(contexte.statut_salarie or "")
        for exclu in statuts_exclus:
            exclu_n = _normalize_statut_label(str(exclu))
            if exclu_n == "cadre" and statut_n in ("cadre", "cadres"):
                alertes.append(
                    _alert(
                        code="prime_anciennete_non_applicable_cadre",
                        message=(
                            "Prime d'ancienneté non applicable : statut cadre "
                            "exclu par la convention collective."
                        ),
                    )
                )
                break
        return alertes

    regle_base = regles_prime.get("base_de_calcul") or {}
    methode = regle_base.get("methode")
    taux_par_classe = regles_prime.get("taux_par_classe") or {}
    needs_vp = methode in ("metallurgie_prime_anciennete",) or (
        methode == "valeur_du_point" and taux_par_classe
    )

    if needs_vp and resolved.get("valeur_point") is None:
        cp = resolved.get("code_postal") or code_postal_from_entreprise(
            contexte.entreprise
        )
        alertes.append(
            _alert(
                code="prime_anciennete_vp_zone_introuvable",
                message=(
                    f"Valeur du point prime d'ancienneté introuvable pour le "
                    f"code postal {cp or 'inconnu'}."
                ),
            )
        )

    classification = (
        contexte.contrat.get("remuneration", {}).get("classification_conventionnelle")
        or {}
    )
    has_classe = any(
        classification.get(k) is not None for k in ("classe_emploi", "classe", "coefficient")
    )
    if not has_classe:
        alertes.append(
            _alert(
                code="prime_anciennete_classification_manquante",
                message=(
                    "Prime d'ancienneté : classification conventionnelle "
                    "(classe) manquante sur la fiche salarié."
                ),
            )
        )

    return alertes


def controle_net_superieur_brut(
    salaire_brut: float,
    net_a_payer: float,
) -> List[Dict[str, Any]]:
    """Signale un net à payer supérieur au brut (avertissement non bloquant)."""
    try:
        brut = float(salaire_brut)
        net = float(net_a_payer)
    except (TypeError, ValueError):
        return []
    if brut < 0 or net <= brut + 0.009:
        return []
    return [
        _alert(
            code="net_superieur_brut",
            critique=False,
            message=NET_SUPERIEUR_BRUT_MESSAGE,
        )
    ]


def _rh_alert_message(raw: Dict[str, Any]) -> str:
    code = str(raw.get("code") or "").strip()
    if code == "net_superieur_brut":
        return NET_SUPERIEUR_BRUT_MESSAGE
    return str(raw.get("message") or "").strip()


def _codes_alertes_baremes(payslip_data: Dict[str, Any]) -> set[str]:
    codes: set[str] = set()
    for raw in payslip_data.get("alertes_baremes") or []:
        if isinstance(raw, dict) and raw.get("code"):
            codes.add(str(raw["code"]))
    return codes


def extraire_messages_alertes_rh(payslip_data: Dict[str, Any]) -> List[str]:
    """Messages d'alerte RH pour listes / génération (persistés + détection legacy)."""
    messages: List[str] = []
    seen: set[str] = set()
    for raw in payslip_data.get("alertes_baremes") or []:
        if not isinstance(raw, dict):
            continue
        msg = _rh_alert_message(raw)
        if msg and msg not in seen:
            messages.append(msg)
            seen.add(msg)

    for raw in extraire_alertes_rh_depuis_bulletin(payslip_data):
        if str(raw.get("code") or "") == "net_superieur_brut":
            continue
        msg = str(raw.get("message") or "").strip()
        if msg and msg not in seen:
            messages.append(msg)
            seen.add(msg)

    if "net_superieur_brut" not in _codes_alertes_baremes(payslip_data):
        brut = payslip_data.get("salaire_brut")
        net = payslip_data.get("net_a_payer")
        try:
            brut_f = float(brut) if brut is not None else None
            net_f = float(net) if net is not None else None
        except (TypeError, ValueError):
            brut_f = net_f = None
        if brut_f is not None and net_f is not None:
            for alerte in controle_net_superieur_brut(brut_f, net_f):
                msg = str(alerte.get("message") or "").strip()
                if msg and msg not in seen:
                    messages.append(msg)
                    seen.add(msg)
    return messages


def extraire_alertes_rh_depuis_bulletin(
    payslip_data: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Agrège les alertes moteur paie pour affichage RH (API / anomalies)."""
    out: List[Dict[str, str]] = []

    for raw in payslip_data.get("alertes_baremes") or []:
        if not isinstance(raw, dict):
            continue
        msg = _rh_alert_message(raw)
        if not msg:
            continue
        out.append(
            {
                "source": "moteur_paie",
                "code": str(raw.get("code") or "alerte_paie"),
                "severite": "bloquant" if raw.get("critique") else "avertissement",
                "message": msg,
            }
        )

    synthese = payslip_data.get("synthese_net") or {}
    if isinstance(synthese, dict):
        for msg in synthese.get("alertes_maintien") or []:
            text = str(msg).strip()
            if text:
                out.append(
                    {
                        "source": "maintien_salaire",
                        "code": "maintien_salaire",
                        "severite": "avertissement",
                        "message": text,
                    }
                )

    return out
