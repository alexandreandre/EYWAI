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
    CLE_MARTINE_A_LA_CORRECTION,
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
    #: Martine calcule autre chose qu'à la correction : à relire, rien n'est bloqué.
    alerte: str | None = None

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


def valeur_de_martine(ligne: LigneCorrigeable) -> dict[str, Any]:
    """Ce que Martine a calculé sur cette ligne, dans la forme de `valeur_calculee`."""
    if ligne.valeur_calculee:
        return dict(ligne.valeur_calculee)
    if ligne.bloc == BLOC_BRUT:
        return {
            "quantite": ligne.base,
            "taux": ligne.taux,
            "gain": None if ligne.retenue else ligne.montant,
            "perte": ligne.montant if ligne.retenue else None,
        }
    if ligne.bloc == BLOC_IMPOT:
        return {"taux": ligne.taux, "montant": ligne.montant}
    return {
        "base": ligne.base,
        "taux_salarial": ligne.taux_salarial,
        "taux_patronal": ligne.taux_patronal,
        "montant_salarial": ligne.montant_salarial,
        "montant_patronal": ligne.montant_patronal,
    }


#: Le champ corrigé, et la valeur de Martine à laquelle le comparer, par bloc.
_CHAMPS_COMPARES = {
    BLOC_BRUT: {"base": ("quantite",), "taux": ("taux",), "montant": ("gain", "perte")},
    BLOC_COTISATIONS: {cle: (cle,) for cle in ("base", "taux_salarial", "taux_patronal", "montant_salarial", "montant_patronal")},
    BLOC_IMPOT: {"taux": ("taux",)},
}
_TOLERANCE_MARTINE = 0.005


def alerte_valeur_de_martine(bloc: str, correction: Any, valeur_calculee: Any) -> str | None:
    """Une phrase si Martine calcule autre chose qu'au moment de la correction.

    Seul ce que la correction remplace compte : une correction de taux n'a pas
    à s'alarmer que la quantité ait bougé.
    """
    if not isinstance(correction, Mapping) or not isinstance(valeur_calculee, Mapping):
        return None
    notee = correction.get(CLE_MARTINE_A_LA_CORRECTION)
    if not isinstance(notee, Mapping):
        return None
    for champ, cles in _CHAMPS_COMPARES.get(bloc, {}).items():
        if correction.get(champ) is None:
            continue
        cle = next((c for c in cles if notee.get(c) is not None or valeur_calculee.get(c) is not None), cles[0])
        if abs((_nombre(notee.get(cle)) or 0.0) - (_nombre(valeur_calculee.get(cle)) or 0.0)) > _TOLERANCE_MARTINE:
            return (
                f"Martine calcule maintenant {valeur_calculee_fr(bloc, valeur_calculee)} sur cette ligne, "
                f"contre {valeur_calculee_fr(bloc, notee)} quand elle a été corrigée à la main. "
                "La correction reste appliquée : retirez-la si elle n'a plus lieu d'être."
            )
    return None


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
                alerte=alerte_valeur_de_martine(BLOC_BRUT, ligne.get("correction"), ligne.get("valeur_calculee")),
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
                alerte=alerte_valeur_de_martine(BLOC_COTISATIONS, ligne.get("correction"), ligne.get("valeur_calculee")),
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
                alerte=alerte_valeur_de_martine(BLOC_IMPOT, impot.get("correction"), impot.get("valeur_calculee")),
            )
        )
    return sortie


_SOURCE_PRIMES = "« Primes du mois » (onglet Corriger), ou la fiche du salarié pour une prime fixe"


def _bloc(libelle: str, montant: Any, source: str) -> dict[str, Any] | None:
    valeur = _nombre(montant)
    return {"libelle": libelle, "montant": valeur, "source": source} if valeur else None


def _blocs_listes(lignes: Any, libelle_par_defaut: str, source: str) -> list[dict[str, Any]]:
    if not isinstance(lignes, list):
        return []
    trouves = (
        _bloc(str(l.get("libelle") or libelle_par_defaut), l.get("montant"), source)
        for l in lignes
        if isinstance(l, Mapping)
    )
    return [b for b in trouves if b]


def _total(data: Mapping[str, Any], cle: str, champ: str) -> Any:
    bloc = data.get(cle)
    return bloc.get(champ) if isinstance(bloc, Mapping) else None


def blocs_a_la_source(payslip_data: Any) -> list[dict[str, Any]]:
    """Ce qui porte de l'argent sur le bulletin sans être une ligne de la carte, et où le corriger.

    Ces montants viennent de leur module : les corriger là les corrige partout.
    """
    data = _donnees(payslip_data)
    synthese = data.get("synthese_net") if isinstance(data.get("synthese_net"), Mapping) else {}
    blocs = [
        *_blocs_listes(data.get("primes_non_soumises"), "Prime non soumise", _SOURCE_PRIMES),
        *_blocs_listes(data.get("revenus_hors_brut_imposables"), "Revenu imposable hors brut", _SOURCE_PRIMES),
        *_blocs_listes(data.get("participations"), "Participation", "« Participation »"),
        _bloc("Avances remboursées", _total(data, "remboursements_avances", "total_rembourse"), "« Avances & acomptes »"),
        _bloc("Saisies sur salaire", _total(data, "retenues_saisies", "total_preleve"), "« Saisies & Avances »"),
        _bloc("Prêt employeur", _total(data, "remboursements_prets", "total_rembourse"), "« Prêts employeur »"),
        *_blocs_listes(
            data["indemnites_sortie"].get("lignes_exonerees") if isinstance(data.get("indemnites_sortie"), Mapping) else None,
            "Indemnité de rupture",
            "« Sorties de salarié » (dossier de départ)",
        ),
        _bloc("Indemnités journalières nettes", synthese.get("ijss_net"), "« Absences & Congés » (arrêt)"),
        _bloc("Acomptes du mois", synthese.get("acompte_verse"), "« Avances & acomptes »"),
    ]
    return [b for b in blocs if b]


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
