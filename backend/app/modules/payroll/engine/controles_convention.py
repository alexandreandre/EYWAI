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
_ALERT_CODES_NON_ACTIONNABLES_LISTE = {
    "prime_anciennete_non_applicable_cadre",
    "prime_anciennete_prorata_zero",
    # Ancienneté insuffisante pour la prime : cas normal d'un salarié récent.
    # Le moteur ne l'émet plus, mais les bulletins générés avant le fix la portent.
    "prime_anciennete_non_eligible",
}
_MAINTIEN_MESSAGES_NON_ACTIONNABLES_LISTE = {
    "Ancienneté insuffisante pour le maintien légal",
    "IJSS versées directement au salarié",
}


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


def _salaire_contractuel_pour_minimum(contexte, salaire_brut: float) -> float:
    """Salaire mensuel avant absences, pertinent pour contrôler le minimum CCN."""
    remuneration = (
        contexte.contrat.get("remuneration", {})
        if hasattr(contexte, "contrat")
        else {}
    )
    salaire_base = remuneration.get("salaire_de_base") or {}
    raw = salaire_base.get("valeur") if isinstance(salaire_base, dict) else salaire_base
    try:
        valeur = float(raw)
    except (TypeError, ValueError):
        valeur = 0.0
    return valeur if valeur > 0 else float(salaire_brut)


def controle_convention_collective(contexte, salaire_brut: float) -> List[Dict[str, Any]]:
    """
    Vérifie la cohérence salaire / convention collective (non bloquant).
    Les alertes sont stockées dans payslip_data.alertes_baremes pour la RH.
    """
    type_contrat = str(getattr(contexte, "type_contrat", "") or "").lower()
    contrat_alternance = any(
        label in type_contrat for label in ("apprentissage", "professionnalisation")
    )
    if getattr(contexte, "is_alternant", False) or contrat_alternance:
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
                # Paramétrage manquant côté outil : le bulletin reste juste,
                # seul le contrôle des minima ne peut pas être joué.
                critique=False,
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
                critique=False,
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
                critique=False,
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
                critique=False,
                message=message,
            )
        )
        return alertes

    if _is_smh_national_idcc(idcc):
        # Le SMH métallurgie est une garantie sur l'année civile complète
        # (articles 138 à 140 IDCC 3248). Son assiette comprend les éléments
        # bruts éligibles versés sur l'année : comparer ici le seul salaire
        # contractuel mensuel à SMH / 12 produit des faux positifs.
        return alertes

    minimum_applicable = float(min_row.get("valeur") or 0)
    minimum_applicable = _minimum_conventionnel_ajuste(contexte, minimum_applicable)
    libelle_poste = min_row.get("libelle")
    try:
        coeff_affiche = float(min_row.get("coefficient") or 0)
    except (TypeError, ValueError):
        coeff_affiche = 0.0

    salaire_controle = _salaire_contractuel_pour_minimum(contexte, salaire_brut)
    if salaire_controle + 0.01 < minimum_applicable:
        poste = f" ({libelle_poste})" if libelle_poste else ""
        alertes.append(
            _alert(
                code="cc_salaire_sous_minimum",
                critique=True,
                message=(
                    f"Salaire contractuel ({salaire_controle:.2f} €) inférieur au minimum "
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
    eligible, motif, _ = check_eligibilite_prime_anciennete(
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


def controle_plafond_transport(
    cumul_annuel: float,
    frais_pro: Dict[str, Any] | None,
    *,
    avec_abonnement_public: bool = False,
    annee: int,
) -> List[Dict[str, Any]]:
    """Signale un dépassement du plafond annuel d'exonération des trajets.

    Contrôle non bloquant : le bulletin n'est PAS modifié. Une réintégration
    automatique changerait des bulletins qui convergent aujourd'hui avec ceux
    du cabinet, sans que la RH l'ait décidé. Le rôle du logiciel est de rendre
    l'écart visible ; la décision de régulariser appartient à la RH.
    """
    from app.modules.payroll.engine.plafond_transport import (
        depassement_annuel,
        plafond_annuel_transport,
    )

    plafond = plafond_annuel_transport(
        frais_pro, avec_abonnement_public=avec_abonnement_public
    )
    exces = depassement_annuel(cumul_annuel, plafond)
    if exces <= 0:
        return []

    def _eur(v: float) -> str:
        return f"{v:,.2f}".replace(",", " ").replace(".", ",")

    return [
        _alert(
            code="transport_plafond_annuel_depasse",
            critique=True,
            message=(
                f"Indemnité trajet domicile-travail : cumul {_eur(cumul_annuel)} € "
                f"versé en {annee}, pour un plafond d'exonération de "
                f"{_eur(plafond)} € — soit {_eur(exces)} € au-delà du plafond. "
                "Cette part excédentaire est normalement soumise à cotisations "
                "et imposable. Le bulletin n'a pas été modifié : à arbitrer "
                "côté paie."
            ),
        )
    ]


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


def _brut_reference_net_depuis_bulletin(payslip_data: Dict[str, Any]) -> Optional[float]:
    """Brut de comparaison incluant la participation numéraire hors salaire brut."""
    brut = payslip_data.get("salaire_brut")
    try:
        total = float(brut) if brut is not None else None
    except (TypeError, ValueError):
        return None
    if total is None:
        return None

    participation_numeraire = 0.0
    for participation in payslip_data.get("participations") or []:
        if not isinstance(participation, dict):
            continue
        try:
            brut_participation = float(participation.get("brut") or 0)
            part_pee = float(participation.get("part_pee") or 0)
        except (TypeError, ValueError):
            continue
        participation_numeraire += max(0.0, brut_participation - part_pee)
    if participation_numeraire:
        total += participation_numeraire

    synthese_net = payslip_data.get("synthese_net") or {}
    try:
        total += max(0.0, -float(synthese_net.get("acompte_verse") or 0))
    except (AttributeError, TypeError, ValueError):
        pass
    for prime in payslip_data.get("primes_non_soumises") or []:
        if not isinstance(prime, dict):
            continue
        try:
            total += max(0.0, float(prime.get("montant") or 0))
        except (TypeError, ValueError):
            continue
    for revenu in payslip_data.get("revenus_hors_brut_imposables") or []:
        if not isinstance(revenu, dict):
            continue
        try:
            total += max(0.0, float(revenu.get("montant") or 0))
        except (TypeError, ValueError):
            continue
    if participation_numeraire or total != float(brut):
        return round(total, 2)

    for ligne in payslip_data.get("calcul_du_brut") or []:
        if not isinstance(ligne, dict):
            continue
        libelle = str(ligne.get("libelle") or "").lower()
        if "participation" not in libelle or "brut" not in libelle:
            continue
        try:
            total += float(ligne.get("gain") or 0)
        except (TypeError, ValueError):
            continue
    return round(total, 2)


def extraire_messages_alertes_rh(payslip_data: Dict[str, Any]) -> List[str]:
    """Messages d'alerte RH pour listes / génération (persistés + détection legacy)."""
    messages: List[str] = []
    seen: set[str] = set()
    for raw in payslip_data.get("alertes_baremes") or []:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("code") or "") in _ALERT_CODES_NON_ACTIONNABLES_LISTE:
            continue
        msg = _rh_alert_message(raw)
        if msg and msg not in seen:
            messages.append(msg)
            seen.add(msg)

    for raw in extraire_alertes_rh_depuis_bulletin(payslip_data):
        code = str(raw.get("code") or "")
        if code == "net_superieur_brut" or code in _ALERT_CODES_NON_ACTIONNABLES_LISTE:
            continue
        msg = str(raw.get("message") or "").strip()
        if msg in _MAINTIEN_MESSAGES_NON_ACTIONNABLES_LISTE:
            continue
        if msg and msg not in seen:
            messages.append(msg)
            seen.add(msg)

    if "net_superieur_brut" not in _codes_alertes_baremes(payslip_data):
        brut_f = _brut_reference_net_depuis_bulletin(payslip_data)
        net = payslip_data.get("net_a_payer")
        try:
            net_f = float(net) if net is not None else None
        except (TypeError, ValueError):
            net_f = None
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
        if str(raw.get("code") or "") in _ALERT_CODES_NON_ACTIONNABLES_LISTE:
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
            if text and text not in _MAINTIEN_MESSAGES_NON_ACTIONNABLES_LISTE:
                out.append(
                    {
                        "source": "maintien_salaire",
                        "code": "maintien_salaire",
                        "severite": "avertissement",
                        "message": text,
                    }
                )

    return out
