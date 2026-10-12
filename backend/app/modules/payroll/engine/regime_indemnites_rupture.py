"""Régime social des indemnités de rupture : licenciement, rupture conventionnelle,
mise à la retraite par l'employeur.

Sources ouvertes le 11/10/2026 :
- BOSS, « Indemnités de rupture » (mis à jour le 26/06/2026) : § 50 et 60
  (exclusion de l'assiette des cotisations pour la fraction non imposable au
  sens de l'article 80 duodecies du CGI, dans la limite de 2 PASS), § 70
  (au-delà de 10 PASS, soumises dès le premier euro), § 80 (CSG et CRDS non dues
  dans la limite du plus faible du montant légal ou conventionnel et du montant
  exclu des cotisations ; pas d'abattement pour frais professionnels), § 300
  (licenciement : fraction non imposable = le plus élevé du double de la
  rémunération annuelle brute de l'année civile précédente, de la moitié de
  l'indemnité — ces deux limites dans la limite de 6 PASS — et du montant légal
  ou conventionnel), § 380 (forfait social : licenciement exclu), § 940 à 1000
  (rupture conventionnelle : mêmes limites, contribution patronale de 40 % sur
  la part exclue des cotisations, pas de forfait social), § 1640 à 1660 (mise à
  la retraite : limites de 5 PASS pour les deux premiers critères, contribution
  de 40 %, pas de forfait social), § 130 (sans rémunération l'année précédente,
  les deux autres limites seules).
- Code de la sécurité sociale, art. L137-12 (Légifrance, version en vigueur
  depuis le 31/12/2025, loi n° 2025-1403 du 30 décembre 2025, art. 15) :
  contribution patronale « assise sur les indemnités versées à l'occasion de :
  1° La mise à la retraite […] 2° La rupture conventionnelle […] pour leur part
  exclue de l'assiette des cotisations de sécurité sociale […] Le taux de cette
  contribution est fixé à 40 %. »
- Cahier technique DSN 2026.1 (docs/audit-maji-2026/sources/
  dsn-cahier-technique-2026.1.txt, S21.G00.81.001, l. 18278) : « 093 -
  Contribution sur indemnités de mise à la retraite ou de rupture
  conventionnelle individuelle ».

Ce que le moteur en fait :
- la part soumise aux cotisations entre au brut (engine/indemnites_sortie_brut) ;
  sa CSG/CRDS est calculée sans abattement ;
- la part exclue des cotisations mais soumise à la CSG/CRDS (au-delà du minimum
  légal ou conventionnel) porte une CSG/CRDS sans abattement, entièrement non
  déductible (elle est hors du revenu imposable) ;
- la contribution patronale de 40 % est une ligne patronale (DSN 093, base 03) ;
- la part exclue des cotisations est ajoutée au net après cotisations et au
  montant net social (BOSS, Montant net social, II, A, 1) ;
- le net imposable prend la part imposable, pas la part soumise aux
  cotisations (`ecart_imposable_et_soumis`) ; la CSG de la part imposable ou
  soumise aux cotisations est déductible (BOFIP BOI-RSA-BASE-30-30, § 100).

Rupture conventionnelle d'un salarié en droit de bénéficier d'une pension de
retraite d'un régime légalement obligatoire (case du dossier) : imposable dès
le premier euro (BOSS § 940) ; cotisations, CSG/CRDS et contribution de 40 %
inchangées, la limite sociale restant celle des a) et b) du 6° de l'article
80 duodecies du CGI (§ 60 : « y compris lorsqu'elles sont soumises à l'impôt
sur le revenu » ; § 890 : distinction du régime social supprimée en 2023).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

LICENCIEMENT = "licenciement"
RUPTURE_CONVENTIONNELLE = "rupture_conventionnelle"
MISE_A_LA_RETRAITE = "mise_retraite"

TAUX_CONTRIBUTION_PATRONALE = 0.40
COTI_ID_CONTRIBUTION = "contribution_indemnite_rupture"

#: Clé du dossier de départ → nature de l'indemnité, et le montant versé.
INDEMNITES_DU_DOSSIER = (
    ("indemnite_licenciement", "montant"),
    ("indemnite_rupture_conventionnelle", "montant_negocie"),
    ("indemnite_mise_retraite", "montant"),
)

_LIBELLES = {
    LICENCIEMENT: "Indemnité de licenciement",
    RUPTURE_CONVENTIONNELLE: "Indemnité de rupture conventionnelle",
    MISE_A_LA_RETRAITE: "Indemnité de mise à la retraite",
}
#: Quand l'indemnité conventionnelle saisie est versée (DSN 021 et 004).
_LIBELLES_CONVENTIONNELS = {
    LICENCIEMENT: "Indemnité conventionnelle de licenciement",
    MISE_A_LA_RETRAITE: "Indemnité conventionnelle de mise à la retraite",
}


def _euros(valeur: float) -> str:
    return f"{valeur:,.2f} €".replace(",", " ").replace(".", ",")


@dataclass(frozen=True)
class RegimeIndemniteRupture:
    nature: str
    montant: float
    minimum: float
    remuneration_annuelle_n_1: Optional[float]
    pass_annuel: float
    exoneree_impot: float
    exoneree_cotisations: float
    soumise_cotisations: float
    exoneree_csg: float
    #: Part exclue des cotisations mais soumise à la CSG/CRDS.
    assiette_csg_seule: float
    contribution_patronale: float
    taux_contribution_patronale: float
    imposable: float
    #: Rupture conventionnelle d'un salarié qui peut liquider sa retraite.
    pension_de_retraite: bool = False

    def mention(self) -> str:
        morceaux = []
        if self.exoneree_cotisations > 0:
            morceaux.append(
                f"Exonérée de cotisations dans la limite de {_euros(self.exoneree_cotisations)}"
            )
        if self.soumise_cotisations > 0:
            morceaux.append(f"soumise aux cotisations pour {_euros(self.soumise_cotisations)}")
        if self.assiette_csg_seule > 0:
            morceaux.append(
                f"CSG/CRDS sur {_euros(self.assiette_csg_seule)} au-delà du minimum légal "
                f"ou conventionnel ({_euros(self.exoneree_csg)})"
            )
        if self.contribution_patronale > 0:
            morceaux.append(
                f"contribution patronale de 40 % : {_euros(self.contribution_patronale)}"
            )
        if self.pension_de_retraite:
            morceaux.append(
                "imposable dès le premier euro, le salarié pouvant bénéficier d'une pension "
                "de retraite"
            )
        return " ; ".join(morceaux) + " (BOSS, Indemnités de rupture)."

    def en_dict(self) -> Dict[str, Any]:
        donnees = asdict(self)
        donnees["mention"] = self.mention()
        return donnees


def ventiler_indemnite_de_rupture(
    nature: str,
    montant: float,
    *,
    minimum: float,
    remuneration_annuelle_n_1: Optional[float],
    pass_annuel: float,
    pension_de_retraite: bool = False,
) -> RegimeIndemniteRupture:
    """Parts exonérées et soumises d'une indemnité de rupture (fonction pure).

    `pension_de_retraite` (rupture conventionnelle seulement) : imposable dès
    le premier euro ; la limite sociale reste calculée sur les a) et b) du 6°
    de l'article 80 duodecies (BOSS § 60, 890, 940)."""
    montant = round(max(float(montant or 0.0), 0.0), 2)
    minimum = round(max(float(minimum or 0.0), 0.0), 2)
    pass_annuel = float(pass_annuel or 0.0)

    candidats = [montant / 2]
    if remuneration_annuelle_n_1 is not None:
        candidats.append(2 * float(remuneration_annuelle_n_1))
    plafond_fiscal = (5 if nature == MISE_A_LA_RETRAITE else 6) * pass_annuel
    exoneree_impot = round(min(montant, max(minimum, min(max(candidats), plafond_fiscal))), 2)

    if montant > 10 * pass_annuel:
        exoneree_cotisations = 0.0
    else:
        exoneree_cotisations = round(min(exoneree_impot, 2 * pass_annuel), 2)
    exoneree_csg = round(min(minimum, exoneree_cotisations), 2)
    pension = bool(pension_de_retraite) and nature == RUPTURE_CONVENTIONNELLE
    if pension:
        exoneree_impot = 0.0
    taux = (
        TAUX_CONTRIBUTION_PATRONALE
        if nature in (RUPTURE_CONVENTIONNELLE, MISE_A_LA_RETRAITE)
        else 0.0
    )
    return RegimeIndemniteRupture(
        nature=nature,
        montant=montant,
        minimum=minimum,
        remuneration_annuelle_n_1=(
            None if remuneration_annuelle_n_1 is None else round(float(remuneration_annuelle_n_1), 2)
        ),
        pass_annuel=pass_annuel,
        exoneree_impot=exoneree_impot,
        exoneree_cotisations=exoneree_cotisations,
        soumise_cotisations=round(montant - exoneree_cotisations, 2),
        exoneree_csg=exoneree_csg,
        assiette_csg_seule=round(exoneree_cotisations - exoneree_csg, 2),
        contribution_patronale=round(exoneree_cotisations * taux, 2),
        taux_contribution_patronale=taux,
        imposable=round(montant - exoneree_impot, 2),
        pension_de_retraite=pension,
    )


# ---------------------------------------------------------------------------
# Lecture dans le dossier de départ que porte le contexte de paie
# ---------------------------------------------------------------------------


def regimes_du_dossier(dossier: Any) -> List[Dict[str, Any]]:
    """Les régimes calculés par le dossier de départ (un par indemnité versée)."""
    if not isinstance(dossier, dict):
        return []
    regimes = []
    for cle, _champ in INDEMNITES_DU_DOSSIER:
        bloc = dossier.get(cle)
        regime = bloc.get("regime_social") if isinstance(bloc, dict) else None
        if isinstance(regime, dict) and float(regime.get("montant") or 0) > 0:
            regimes.append(regime)
    return regimes


def part_soumise_aux_cotisations(dossier: Any) -> float:
    return round(sum(float(r.get("soumise_cotisations") or 0) for r in regimes_du_dossier(dossier)), 2)


def ecart_imposable_et_soumis(dossier: Any) -> float:
    """Ce que le net imposable doit ajouter (ou retirer) au brut pour les
    indemnités de rupture : le brut porte la part soumise aux cotisations, le
    net imposable la part imposable (CGI 80 duodecies). Positif pour une
    rupture conventionnelle d'un salarié qui peut liquider sa retraite,
    négatif au-delà de 2 PASS (part soumise mais exonérée d'impôt)."""
    return round(
        sum(
            float(r.get("imposable") or 0) - float(r.get("soumise_cotisations") or 0)
            for r in regimes_du_dossier(dossier)
        ),
        2,
    )


def _assiette_csg_deductible(regime: Dict[str, Any]) -> float:
    """La part soumise à la CSG/CRDS dont la CSG est déductible : la part
    imposable et la part exonérée d'impôt mais soumise aux cotisations (BOFIP
    BOI-RSA-BASE-30-30, § 100). Seule la CSG de la part exonérée d'impôt et de
    cotisations ne se déduit pas."""
    soumise = float(regime.get("soumise_cotisations") or 0)
    assiette_csg = soumise + float(regime.get("assiette_csg_seule") or 0)
    return round(min(assiette_csg, max(float(regime.get("imposable") or 0), soumise)), 2)


def lignes_brut_parts_soumises(dossier: Any) -> List[Dict[str, Any]]:
    """Lignes du brut : la part de chaque indemnité qui dépasse les limites."""
    lignes = []
    for regime in regimes_du_dossier(dossier):
        soumise = round(float(regime.get("soumise_cotisations") or 0), 2)
        if soumise <= 0:
            continue
        nature = str(regime.get("nature"))
        libelle = (
            _LIBELLES_CONVENTIONNELS.get(nature)
            if regime.get("conventionnelle")
            else None
        ) or _LIBELLES.get(nature, "Indemnité de rupture")
        lignes.append(
            {
                "libelle": f"{libelle} (part soumise à cotisations)",
                "quantite": None,
                "taux": None,
                "gain": soumise,
                "perte": None,
                "is_indemnite_sortie": True,
            }
        )
    return lignes


def _taux_csg(contexte: Any) -> tuple[float, float]:
    """(CSG déductible, CSG non déductible et CRDS) du barème du mois : une
    entrée « csg » à deux taux (barème de la base), sinon des entrées séparées."""
    lire = getattr(contexte, "get_cotisation_by_id", None)
    if lire is None:
        return 0.0, 0.0
    csg = lire("csg") or {}
    salarial = csg.get("salarial")
    if isinstance(salarial, dict):
        return float(salarial.get("deductible") or 0.0), float(salarial.get("non_deductible") or 0.0)

    def taux(coti_id: str) -> float:
        valeur = (lire(coti_id) or {}).get("salarial")
        return float(valeur) if isinstance(valeur, (int, float)) else 0.0

    return taux("csg_deductible"), taux("csg_non_deductible") + taux("crds")


def lignes_cotisations_indemnites_rupture(contexte: Any) -> List[Dict[str, Any]]:
    """CSG/CRDS sans abattement et contribution patronale des indemnités de rupture."""
    from app.modules.payroll.engine.cotisations_rubriques import enrichir_ligne_cotisation

    regimes = regimes_du_dossier(getattr(contexte, "exit_indemnities", None))
    if not regimes:
        return []
    deductible, non_deductible = _taux_csg(contexte)
    # CSG déductible : part imposable ou soumise aux cotisations ; le reste de
    # l'assiette (exonéré d'impôt et de cotisations) en entier non déductible.
    assiette_deductible = round(sum(_assiette_csg_deductible(r) for r in regimes), 2)
    assiette_csg = round(
        sum(
            float(r.get("soumise_cotisations") or 0) + float(r.get("assiette_csg_seule") or 0)
            for r in regimes
        ),
        2,
    )
    csg_seule = round(assiette_csg - assiette_deductible, 2)
    lignes: List[Dict[str, Any]] = []

    def salariale(libelle: str, base: float, taux: float, coti_id: str) -> None:
        if base > 0 and taux > 0:
            lignes.append(
                enrichir_ligne_cotisation(
                    {
                        "libelle": libelle,
                        "base": base,
                        "taux_salarial": round(taux, 6),
                        "montant_salarial": round(base * taux, 2),
                        "taux_patronal": None,
                        "montant_patronal": 0.0,
                        "is_indemnite_rupture": True,
                    },
                    coti_id=coti_id,
                )
            )

    salariale("CSG déductible sur indemnité de rupture", assiette_deductible, deductible, "csg_deductible")
    salariale(
        "CSG/CRDS non déductible sur indemnité de rupture",
        assiette_deductible,
        non_deductible,
        "csg_non_deductible",
    )
    salariale(
        "CSG/CRDS non déductible sur indemnité de rupture non imposable",
        csg_seule,
        deductible + non_deductible,
        "csg_non_deductible",
    )
    for regime in regimes:
        contribution = round(float(regime.get("contribution_patronale") or 0), 2)
        if contribution <= 0:
            continue
        objet = (
            "mise à la retraite"
            if regime.get("nature") == MISE_A_LA_RETRAITE
            else "rupture conventionnelle"
        )
        lignes.append(
            enrichir_ligne_cotisation(
                {
                    "libelle": f"Contribution patronale sur indemnité de {objet} (40 %)",
                    "base": round(float(regime.get("exoneree_cotisations") or 0), 2),
                    "taux_salarial": None,
                    "montant_salarial": 0.0,
                    "taux_patronal": float(regime.get("taux_contribution_patronale") or 0.0),
                    "montant_patronal": contribution,
                    "is_indemnite_rupture": True,
                },
                coti_id=COTI_ID_CONTRIBUTION,
            )
        )
    return lignes
