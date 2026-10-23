"""Lire les corrections faites à la main sur un bulletin enregistré.

La route « lignes corrigeables », la carte de l'écran, la restauration d'une
version, la liste de contrôle, le PDF, l'info-bulle et le test du théorème
lisent ici les mêmes codes que le moteur (`codes_des_lignes`), numérotés de la
même façon.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from app.modules.payroll.engine.codes_des_lignes import (
    BLOC_BRUT,
    BLOC_COTISATIONS,
    BLOC_IMPOT,
    CODE_IMPOT,
    MODE_TAUX,
    champ_du_montant,
    code_de_ligne,
    famille_du_code,
    mode_de_correction,
    numeroter,
)
from app.modules.payroll.engine.corrections_manuelles import (
    CLE_CORRECTIONS_EN_ATTENTE,
    CorrectionDeLigne,
    CorrectionInvalide,
)

#: Les blocs imprimés d'un bulletin qui portent ses lignes de gain. Les lignes
#: d'arrêt de `details_maintien` sont celles de `details_absences`.
BLOCS_DE_GAINS = ("calcul_du_brut", "details_conges", "details_absences")
LIBELLE_IMPOT = "Impôt sur le revenu prélevé à la source"


@dataclass(frozen=True)
class LigneCorrigeable:
    code: str | None
    bloc: str
    libelle: str
    mode: str | None
    raison: str | None = None
    retenue: bool = False
    base: float | None = None
    taux: float | None = None
    montant: float | None = None
    taux_salarial: float | None = None
    taux_patronal: float | None = None
    montant_salarial: float | None = None
    montant_patronal: float | None = None
    correction: dict[str, Any] | None = None
    valeur_calculee: dict[str, Any] | None = None

    def en_dict(self) -> dict[str, Any]:
        return asdict(self)


def _nombre(valeur: Any) -> float | None:
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _dict(valeur: Any) -> dict[str, Any] | None:
    return dict(valeur) if isinstance(valeur, Mapping) else None


def _donnees(payslip_data: Any) -> Mapping[str, Any]:
    return payslip_data if isinstance(payslip_data, Mapping) else {}


def _lignes_de_gain(data: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [l for bloc in BLOCS_DE_GAINS for l in data.get(bloc) or [] if isinstance(l, Mapping)]


def _lignes_de_cotisation(data: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        l
        for rubrique in data.get("cotisations_officielles") or []
        if isinstance(rubrique, Mapping)
        for l in rubrique.get("lignes") or []
        if isinstance(l, Mapping)
    ]


def _impot(data: Mapping[str, Any]) -> Mapping[str, Any] | None:
    synthese = data.get("synthese_net")
    impot = synthese.get("impot_prelevement_a_la_source") if isinstance(synthese, Mapping) else None
    return impot if isinstance(impot, Mapping) else None


def lignes_corrigeables(payslip_data: Any) -> list[LigneCorrigeable]:
    """Chaque ligne du bulletin, son code, par quoi elle se corrige, et sa correction."""
    data = _donnees(payslip_data)
    sortie: list[LigneCorrigeable] = []
    gains = _lignes_de_gain(data)
    for ligne, code in zip(gains, numeroter(code_de_ligne(BLOC_BRUT, l) for l in gains)):
        mode, raison = mode_de_correction(BLOC_BRUT, ligne, code)
        champ = champ_du_montant(ligne)
        sortie.append(
            LigneCorrigeable(
                code=code,
                bloc=BLOC_BRUT,
                libelle=str(ligne.get("libelle") or ""),
                mode=mode,
                raison=raison,
                retenue=champ == "perte",
                base=_nombre(ligne.get("quantite")),
                taux=_nombre(ligne.get("taux")),
                montant=_nombre(ligne.get(champ)),
                correction=_dict(ligne.get("correction")),
                valeur_calculee=_dict(ligne.get("valeur_calculee")),
            )
        )
    cotisations = _lignes_de_cotisation(data)
    for ligne, code in zip(cotisations, numeroter(code_de_ligne(BLOC_COTISATIONS, l) for l in cotisations)):
        mode, raison = mode_de_correction(BLOC_COTISATIONS, ligne, code)
        sortie.append(
            LigneCorrigeable(
                code=code,
                bloc=BLOC_COTISATIONS,
                libelle=str(ligne.get("libelle") or ""),
                mode=mode,
                raison=raison,
                base=_nombre(ligne.get("base")),
                taux_salarial=_nombre(ligne.get("taux_salarial")),
                taux_patronal=_nombre(ligne.get("taux_patronal")),
                montant_salarial=_nombre(ligne.get("montant_salarial")),
                montant_patronal=_nombre(ligne.get("montant_patronal")),
                correction=_dict(ligne.get("correction")),
                valeur_calculee=_dict(ligne.get("valeur_calculee")),
            )
        )
    impot = _impot(data)
    if impot is not None:
        sortie.append(
            LigneCorrigeable(
                code=CODE_IMPOT,
                bloc=BLOC_IMPOT,
                libelle=LIBELLE_IMPOT,
                mode=MODE_TAUX,
                base=_nombre(impot.get("base")),
                taux=_nombre(impot.get("taux")),
                montant=_nombre(impot.get("montant")),
                correction=_dict(impot.get("correction")),
                valeur_calculee=_dict(impot.get("valeur_calculee")),
            )
        )
    return sortie


def corrections_en_attente_du_bulletin(payslip_data: Any) -> list[dict[str, Any]]:
    entrees = _donnees(payslip_data).get(CLE_CORRECTIONS_EN_ATTENTE) or []
    return [dict(e) for e in entrees if isinstance(e, Mapping)]


def corrections_du_bulletin(payslip_data: Any) -> dict[str, CorrectionDeLigne]:
    """Les corrections du bulletin par identifiant de saisie : posées ou en attente."""
    trouvees: dict[str, CorrectionDeLigne] = {}
    traces = [l.correction for l in lignes_corrigeables(payslip_data) if l.correction]
    for trace in [*traces, *corrections_en_attente_du_bulletin(payslip_data)]:
        identifiant = trace.get("saisie_id")
        if not identifiant or str(identifiant) in trouvees:
            continue
        try:
            trouvees[str(identifiant)] = CorrectionDeLigne.depuis(trace)
        except CorrectionInvalide:
            continue
    return trouvees


def lignes_corrigees_du_bulletin(payslip_data: Any) -> list[dict[str, str]]:
    """Une entrée par famille de ligne corrigée : le capteur compare les familles d'un mois à l'autre."""
    vues: dict[str, str] = {}
    for ligne in lignes_corrigeables(payslip_data):
        if ligne.correction and ligne.code:
            vues.setdefault(famille_du_code(ligne.code), ligne.libelle)
    return [{"famille": famille, "libelle": libelle} for famille, libelle in vues.items()]


def _euros(valeur: Any) -> str:
    montant = float(valeur or 0.0)
    texte = f"{abs(montant):,.2f}".replace(",", " ").replace(".", ",")
    return f"{'−' if montant < 0 else ''}{texte} €"


def valeur_calculee_fr(bloc: str, valeur_calculee: Any) -> str:
    valeur = valeur_calculee if isinstance(valeur_calculee, Mapping) else {}
    if bloc == BLOC_IMPOT:
        return "un taux de " + f"{float(valeur.get('taux') or 0.0):.2f}".replace(".", ",") + " %"
    if bloc == BLOC_BRUT:
        montant = valeur.get("gain") if valeur.get("gain") is not None else valeur.get("perte")
        return _euros(montant)
    parts = []
    if valeur.get("montant_salarial"):
        parts.append(f"{_euros(valeur['montant_salarial'])} salarial")
    if valeur.get("montant_patronal"):
        parts.append(f"{_euros(valeur['montant_patronal'])} patronal")
    return " et ".join(parts) or _euros(0.0)


def explication_de_correction(ligne: Mapping[str, Any], bloc: str) -> str | None:
    correction = ligne.get("correction")
    if not isinstance(correction, Mapping):
        return None
    return (
        f"Corrigée à la main : {correction.get('motif') or ''}. "
        f"Martine avait calculé {valeur_calculee_fr(bloc, ligne.get('valeur_calculee'))}."
    )


def mentions_des_corrections(payslip_data: Any) -> list[str]:
    """Les notes du PDF : chaque ligne corrigée, son motif et la valeur de Martine."""
    mentions = []
    for ligne in lignes_corrigeables(payslip_data):
        if not ligne.correction:
            continue
        motif = ligne.correction.get("motif") or ""
        if ligne.bloc == BLOC_IMPOT:
            mentions.append(
                f"* Taux d'impôt corrigé à la main : {motif} "
                f"(Martine avait appliqué {valeur_calculee_fr(BLOC_IMPOT, ligne.valeur_calculee)})."
            )
        else:
            mentions.append(
                f"* Ligne corrigée à la main — {ligne.libelle} : {motif} "
                f"(Martine avait calculé {valeur_calculee_fr(ligne.bloc, ligne.valeur_calculee)})."
            )
    return mentions
