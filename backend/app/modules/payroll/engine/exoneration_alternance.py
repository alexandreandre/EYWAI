"""Règles pures d'exonération pour les alternants (apprentis / pro).

Aucune valeur en dur : tous les seuils proviennent du contexte de paie et des
barèmes dynamiques (payroll_config, clé 'alternance'). Le module ne calcule
jamais le SMIC lui-même : il consomme `ContextePaie.smic_mensuel_proratise()`.

Fait générateur du régime apprenti = 1er jour d'EXÉCUTION du contrat (BOSS).
Option de maintien de l'ancien régime (contrat conclu avant la bascule mais
débutant après) : flag `specificites_paie.maintien_regime_apprenti`.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger

logger = get_logger("modules.payroll.engine.exoneration_alternance")


def _parse_date(value: Any) -> Optional[date]:
    """Parse une date ISO (YYYY-MM-DD) ou FR (DD/MM/YYYY) en `date`, sinon None."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def _config_apprenti(contexte) -> Dict[str, Any]:
    alternance = contexte.baremes.get("alternance", {}) or {}
    return alternance.get("apprenti", {}) or {}


def _maintien_ancien_regime(contexte) -> bool:
    spec = contexte.contrat.get("specificites_paie", {}) or {}
    return bool(spec.get("maintien_regime_apprenti", False))


def _regime_plus_recent(regimes: List[Dict[str, Any]]) -> Dict[str, Any]:
    def _key(r: Dict[str, Any]) -> date:
        return _parse_date(r.get("date_execution_min")) or date.min

    return sorted(regimes, key=_key)[-1]


def selectionner_regime_apprenti(contexte) -> Optional[Dict[str, Any]]:
    """Régime apprenti applicable selon la fenêtre de date d'exécution.

    Si l'option de maintien est active, la sélection se fait sur la date de
    conclusion du contrat. Sans date fiable, on retient le régime le plus
    récent (comportement prudent).
    """
    cfg = _config_apprenti(contexte)
    regimes = cfg.get("regimes") or []
    if not regimes:
        return None

    if _maintien_ancien_regime(contexte):
        date_ref = _parse_date(contexte.date_conclusion_contrat) or _parse_date(
            contexte.date_debut_execution
        )
    else:
        date_ref = _parse_date(contexte.date_debut_execution)

    if date_ref is None:
        return _regime_plus_recent(regimes)

    for regime in regimes:
        d_min = _parse_date(regime.get("date_execution_min"))
        d_max = _parse_date(regime.get("date_execution_max"))
        if (d_min is None or date_ref >= d_min) and (
            d_max is None or date_ref <= d_max
        ):
            return regime
    return _regime_plus_recent(regimes)


def plafond_exoneration_apprenti(contexte, regime: Dict[str, Any]) -> float:
    """Plafond mensuel d'exonération = pct × SMIC mensuel proratisé (durée)."""
    pct = float(regime.get("plafond_exoneration_pct_smic") or 0.0)
    return round(contexte.smic_mensuel_proratise() * pct, 2)


def assiette_residuelle(brut: float, plafond: float) -> float:
    """Part de rémunération soumise après exonération = max(0, brut - plafond)."""
    return round(max(0.0, float(brut) - float(plafond)), 2)


def _config_professionnalisation(contexte) -> Dict[str, Any]:
    alternance = contexte.baremes.get("alternance", {}) or {}
    return alternance.get("professionnalisation", {}) or {}


def age_a_date(date_naissance: Any, date_ref: Optional[date] = None) -> Optional[int]:
    """Âge révolu à une date de référence (aujourd'hui par défaut)."""
    dn = _parse_date(date_naissance)
    if dn is None:
        return None
    ref = date_ref or date.today()
    return (
        ref.year
        - dn.year
        - ((ref.month, ref.day) < (dn.month, dn.day))
    )


def public_professionnalisation(contexte) -> Dict[str, Any]:
    """Caractéristiques du salarié en contrat de professionnalisation.

    `demandeur_emploi` provient d'un flag explicite dans specificites_paie.
    """
    spec = contexte.contrat.get("specificites_paie", {}) or {}
    return {
        "age": age_a_date(contexte.date_naissance),
        "demandeur_emploi": bool(spec.get("demandeur_emploi", False)),
    }


def _public_correspond(criteres: Dict[str, Any], public: Dict[str, Any]) -> bool:
    age_min = criteres.get("age_min")
    if age_min is not None:
        age = public.get("age")
        if age is None or age < age_min:
            return False
    if criteres.get("demandeur_emploi") and not public.get("demandeur_emploi"):
        return False
    return True


def exonerations_patronales_professionnalisation(
    contexte, salaire_brut: float
) -> List[Dict[str, Any]]:
    """Lignes d'exonération patronale pour un contrat de professionnalisation.

    IMPORTANT (anti-double-comptage) : les anciennes exonérations patronales
    (publics >= 45 ans / demandeurs d'emploi) ont été absorbées par la
    réduction générale, qui s'applique déjà. Cette liste est donc VIDE par
    défaut dans payroll_config ; le mécanisme reste piloté par la config pour
    rester dynamique si un dispositif spécifique réapparaissait.
    """
    if not getattr(contexte, "is_professionnalisation", False):
        return []
    cfg = _config_professionnalisation(contexte)
    regles = cfg.get("exonerations_patronales") or []
    if not regles:
        return []

    public = public_professionnalisation(contexte)
    lignes: List[Dict[str, Any]] = []
    for regle in regles:
        criteres = regle.get("criteres", {}) or {}
        if not _public_correspond(criteres, public):
            continue
        for coti in regle.get("cotisations", []) or []:
            taux = float(coti.get("taux_patronal") or 0.0)
            if taux <= 0:
                continue
            montant = round(-float(salaire_brut) * taux, 2)
            lignes.append(
                {
                    "libelle": coti.get(
                        "libelle", "Exonération patronale professionnalisation"
                    ),
                    "base": round(float(salaire_brut), 2),
                    "taux_salarial": None,
                    "montant_salarial": 0.0,
                    "taux_patronal": -taux,
                    "montant_patronal": montant,
                }
            )
    return lignes


def controle_salaire_minimum_alternant(
    contexte, salaire_brut: float
) -> Optional[Dict[str, Any]]:
    """Alerte non bloquante si le brut est sous le minimum conventionnel.

    Le minimum est piloté par une grille dans payroll_config
    (`alternance.<type>.grille_remuneration`) exprimée en % du SMIC selon
    l'âge. Absente (cas par défaut) : aucun contrôle, aucun faux positif.
    """
    if not getattr(contexte, "is_alternant", False):
        return None
    alternance = contexte.baremes.get("alternance", {}) or {}
    cle = "apprenti" if contexte.is_apprenti else "professionnalisation"
    grille = (alternance.get(cle, {}) or {}).get("grille_remuneration") or []
    if not grille:
        return None

    age = age_a_date(contexte.date_naissance)
    pct = None
    for tranche in grille:
        age_min = tranche.get("age_min")
        age_max = tranche.get("age_max")
        if age is None:
            continue
        if (age_min is None or age >= age_min) and (
            age_max is None or age <= age_max
        ):
            pct = tranche.get("pct_smic")
            break
    if pct is None:
        return None

    minimum = round(contexte.smic_mensuel_proratise() * float(pct), 2)
    if salaire_brut + 0.01 < minimum:
        return {
            "code": "salaire_minimum_alternant",
            "config_key": "alternance",
            "critique": False,
            "severity": "warning",
            "message": (
                f"Salaire brut ({salaire_brut:.2f} €) sous le minimum "
                f"conventionnel alternant estimé ({minimum:.2f} €)."
            ),
            "donnee_non_officielle": False,
        }
    return None


def contexte_exoneration_apprenti(contexte) -> Optional[Dict[str, Any]]:
    """Paramètres d'exonération d'un apprenti, ou None si non applicable.

    Renvoie un dict :
      - plafond : plafond mensuel d'exonération (€)
      - csg_crds_assujettie : la CSG/CRDS s'applique-t-elle au-delà du plafond ?
      - abattement_csg : abattement frais pro pour la base CSG/CRDS
      - cotisations_exclues : ids de cotisations toujours dues (mutuelle, etc.)
      - exoneration_ir : config d'exonération d'impôt (annuelle)
    """
    if not getattr(contexte, "is_apprenti", False):
        return None
    regime = selectionner_regime_apprenti(contexte)
    if not regime:
        logger.warning(
            "WARN: contrat apprenti mais aucun régime 'alternance' dans payroll_config."
        )
        return None
    cfg = _config_apprenti(contexte)
    return {
        "regime": regime,
        "plafond": plafond_exoneration_apprenti(contexte, regime),
        "csg_crds_assujettie": bool(
            regime.get("csg_crds_assujettie_au_dela_plafond")
        ),
        "abattement_csg": float(cfg.get("abattement_csg_frais_pro") or 0.0),
        "cotisations_exclues": [
            str(c).lower()
            for c in (cfg.get("cotisations_exclues_exoneration") or [])
        ],
        "exoneration_ir": cfg.get("exoneration_ir", {}) or {},
    }
