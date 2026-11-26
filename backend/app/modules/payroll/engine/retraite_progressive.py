"""Retraite progressive et cotisations d'assurance vieillesse sur un temps plein.

Le réglage vit sur la fiche, `specificites_paie.retraite_progressive` (colonne
JSON existante, sans migration) :

    {
      "actif": true,
      "quotite": 0.5,                    # part du temps plein travaillée (40 à 80 %)
      "date_debut": "2026-10-01",
      "date_fin": null,
      "vieillesse_temps_plein": true,    # CSS L241-3-1 : base vieillesse à temps plein
      "complementaire_temps_plein": false,   # ANI Agirc-Arrco du 17/11/2017, art. 75
      "prise_en_charge_part_salariale": false,
      "salaire_temps_plein": null        # facultatif : montant fixé par l'accord
    }

Textes ouverts le 26/11/2026 :

- CSS L241-3-1 : « en cas d'emploi exercé à temps partiel […] ou, dans des
  conditions fixées par décret, en cas d'emploi dont la rémunération ne peut être
  déterminée selon un nombre d'heures travaillées, l'assiette des cotisations
  destinées à financer l'assurance vieillesse peut être maintenue à la hauteur du
  salaire correspondant à son activité exercée à temps plein. Lorsqu'elle est
  prise en charge par l'employeur, la part salariale est exclue de l'assiette de
  la contribution prévue à l'article L. 136-1. »
- CSS R241-0-2, I : salaire temps plein = rémunération du mois × (durée du
  travail à temps plein / heures rémunérées du mois ou « nombre d'heures
  considéré comme correspondant à la rémunération mensuelle versée ») ; III :
  taux de droit commun de la vieillesse plafonnée et déplafonnée ; V : pas de
  plafond réduit du temps partiel (L242-8) quand l'option est prise.
- CSS R241-0-3, II : l'employeur « peut prendre en charge la différence » de
  cotisation salariale ; l'accord en fixe la proportion.
- Forfait jours (régime de base) : le nombre d'heures « considéré » est la
  rémunération divisée par 1,7 SMIC horaire, et l'option n'est ouverte que sous
  ce seuil (Lamy, d'après le décret 2005-1352 et la lettre-circulaire Acoss
  2005-176 ; circulaire Agirc-Arrco 2025-6 : « le code de la sécurité sociale
  limite l'accès au dispositif du régime de base à ceux dont la rémunération
  n'excède pas 1,7 SMIC »). Le salaire temps plein vaut alors 1,7 SMIC mensuel.
- Agirc-Arrco, avenant 23 (circulaire 2025-6) : au forfait jours réduit, assiette
  = rémunération × 218 / jours du forfait, dans la limite de huit plafonds, même
  au-delà de 1,7 SMIC.
- DSN (fiche net-entreprises v2.1) : base 22 = différentiel déplafonné, base 24 =
  différentiel plafonné (plafond entier − base 02), CTP 288 ; S21.G00.40.044.

Le supplément ne touche ni le brut ni la CSG : ce sont des lignes de cotisation
en plus, « Surcotisation retraite progressive », part patronale à l'employeur,
part salariale au salarié sauf prise en charge (alors versée par l'employeur).
Un salarié sans réglage ne voit rien changer : la fonction rend une liste vide.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import legal_constants as lc

CLE_REGLAGE = "retraite_progressive"
#: Quotité de travail permise (CSS R161-19-6 : « ne peut être inférieure à 40 %
#: ou supérieure à 80 % de la durée de travail à temps complet »).
QUOTITE_MIN, QUOTITE_MAX = 0.40, 0.80
#: Seuil du forfait jours pour la vieillesse de base, en SMIC.
COEFFICIENT_SMIC_FORFAIT = 1.7
#: Limite de l'assiette Agirc-Arrco (ANI du 17/11/2017, art. 32 : huit plafonds).
FACTEUR_PLAFOND_COMPLEMENTAIRE = 8

#: Cotisations du barème suivies, et la ligne de surcotisation qu'elles donnent.
#: (identifiant du barème, identifiant de la surcotisation, assiette « p » ou « d »).
VIEILLESSE_DE_BASE: Tuple[Tuple[str, str, str], ...] = (
    ("vieillesse_plafonnee", "surcotisation_vieillesse_plafonnee", "plafonnee"),
    ("retraite_secu_plafond", "surcotisation_vieillesse_plafonnee", "plafonnee"),
    ("vieillesse_deplafonnee", "surcotisation_vieillesse_deplafonnee", "deplafonnee"),
    ("retraite_secu_deplafond", "surcotisation_vieillesse_deplafonnee", "deplafonnee"),
)
COMPLEMENTAIRE: Tuple[Tuple[str, str, str], ...] = (
    ("retraite_comp_t1", "surcotisation_retraite_comp_t1", "t1"),
    ("ceg_t1", "surcotisation_ceg_t1", "t1"),
    ("retraite_comp_t2", "surcotisation_retraite_comp_t2", "t2"),
    ("ceg_t2", "surcotisation_ceg_t2", "t2"),
    ("cet", "surcotisation_cet", "cet"),
)
#: Toutes les lignes que ce module peut poser (rubrique « Retraite », DSN).
COTI_IDS_SURCOTISATION = frozenset(s for _, s, _ in VIEILLESSE_DE_BASE + COMPLEMENTAIRE)
LIBELLE = "Surcotisation retraite progressive"


@dataclass(frozen=True)
class ReglageRetraiteProgressive:
    actif: bool
    quotite: Optional[float]
    date_debut: Optional[date]
    date_fin: Optional[date]
    vieillesse_temps_plein: bool
    complementaire_temps_plein: bool
    prise_en_charge_part_salariale: bool
    salaire_temps_plein: Optional[float]

    def couvre(self, annee: int, mois: int) -> bool:
        """Le réglage vaut-il pour au moins un jour du mois ?"""
        if not self.actif:
            return False
        premier = date(annee, mois, 1)
        mois_suivant = date(annee + mois // 12, mois % 12 + 1, 1)
        if self.date_debut and self.date_debut >= mois_suivant:
            return False
        if self.date_fin and self.date_fin < premier:
            return False
        return True


def _date(valeur: Any) -> Optional[date]:
    if not valeur:
        return None
    try:
        return date.fromisoformat(str(valeur)[:10])
    except ValueError:
        raise ValueError(f"Retraite progressive : date illisible « {valeur} » (attendu AAAA-MM-JJ).") from None


def _nombre(valeur: Any, nom: str) -> Optional[float]:
    if valeur is None or (isinstance(valeur, str) and not valeur.strip()):
        return None
    try:
        if isinstance(valeur, bool):
            raise ValueError
        return float(str(valeur).replace(",", ".").replace("%", "").strip())
    except (TypeError, ValueError):
        raise ValueError(f"Retraite progressive : {nom} illisible « {valeur} ».") from None


def lire_reglage(specificites_paie: Any) -> Optional[ReglageRetraiteProgressive]:
    """Le réglage de la fiche, ou None s'il n'y en a pas.

    Une quotité saisie en pourcentage (50) est ramenée à une fraction (0,5). Une
    valeur illisible arrête le calcul : se taire donnerait un bulletin faux.
    """
    if not isinstance(specificites_paie, dict):
        return None
    brut = specificites_paie.get(CLE_REGLAGE)
    if not isinstance(brut, dict) or not brut.get("actif"):
        return None
    quotite = _nombre(brut.get("quotite"), "quotité")
    if quotite is not None and quotite > 1:
        quotite = quotite / 100.0
    if quotite is not None and not 0 < quotite < 1:
        raise ValueError(f"Retraite progressive : quotité impossible « {brut.get('quotite')} » (entre 40 et 80 %).")
    salaire = _nombre(brut.get("salaire_temps_plein"), "salaire temps plein")
    return ReglageRetraiteProgressive(
        actif=True,
        quotite=quotite,
        date_debut=_date(brut.get("date_debut")),
        date_fin=_date(brut.get("date_fin")),
        vieillesse_temps_plein=bool(brut.get("vieillesse_temps_plein")),
        complementaire_temps_plein=bool(brut.get("complementaire_temps_plein")),
        prise_en_charge_part_salariale=bool(brut.get("prise_en_charge_part_salariale")),
        salaire_temps_plein=salaire if salaire and salaire > 0 else None,
    )


def _alerte(code: str, message: str) -> Dict[str, Any]:
    return {
        "code": code,
        "critique": False,
        "severity": "warning",
        "message": message,
        "donnee_non_officielle": False,
    }


def _euros(valeur: float) -> str:
    entier, _, decimales = f"{valeur:.2f}".partition(".")
    return f"{int(entier):,}".replace(",", " ") + "," + decimales + " €"


@dataclass(frozen=True)
class SalairesTempsPlein:
    """Salaires reconstitués du mois ; None quand l'option ne s'applique pas."""

    base: Optional[float]
    complementaire: Optional[float]
    quotite: Optional[float]
    alertes: Tuple[Dict[str, Any], ...] = ()


def salaires_temps_plein(
    reglage: ReglageRetraiteProgressive,
    *,
    brut: float,
    au_forfait_jours: bool,
    jours_forfait: Optional[float],
    heures_contrat_mois: float,
    heures_complementaires_mois: float,
    smic_horaire: float,
) -> SalairesTempsPlein:
    """Salaire temps plein de la vieillesse de base et de la complémentaire."""
    alertes: List[Dict[str, Any]] = []
    heures_temps_plein = lc.DUREE_LEGALE_HEBDO * 52 / 12
    if au_forfait_jours:
        quotite_fiche = (jours_forfait / lc.JOURS_FORFAIT_LEGAL) if jours_forfait else None
    else:
        quotite_fiche = (heures_contrat_mois / heures_temps_plein) if heures_contrat_mois else None
        if quotite_fiche is not None and quotite_fiche >= 0.9999:
            quotite_fiche = None
    quotite = reglage.quotite if reglage.quotite is not None else quotite_fiche
    if quotite is not None and not QUOTITE_MIN - 1e-9 <= quotite <= QUOTITE_MAX + 1e-9:
        alertes.append(_alerte(
            "retraite_progressive_quotite_hors_bornes",
            f"Retraite progressive à {quotite * 100:.0f} % : la loi la permet entre 40 et 80 % "
            "du temps plein (CSS R161-19-6). Vérifiez la quotité de la fiche.",
        ))
    if reglage.quotite is not None and (
        quotite_fiche is None or abs(quotite_fiche - reglage.quotite) > 0.01
    ):
        if au_forfait_jours:
            jours = jours_forfait or lc.JOURS_FORFAIT_LEGAL
            detail = f"le forfait de la fiche est de {jours:g} jours ({jours / lc.JOURS_FORFAIT_LEGAL * 100:.0f} % de 218)"
            attendu = f"{round(reglage.quotite * lc.JOURS_FORFAIT_LEGAL):d} jours"
        else:
            detail = f"le contrat de la fiche est de {heures_contrat_mois:.2f} h par mois"
            attendu = f"{reglage.quotite * heures_temps_plein:.2f} h par mois"
        alertes.append(_alerte(
            "retraite_progressive_quotite_fiche",
            f"Retraite progressive à {reglage.quotite * 100:.0f} %, mais {detail}. "
            f"Le salaire et les jours du bulletin suivent la fiche : passez-la à {attendu} "
            "si le temps de travail a bien changé.",
        ))

    base: Optional[float] = None
    complementaire: Optional[float] = None
    if brut <= 0:
        return SalairesTempsPlein(None, None, quotite, tuple(alertes))

    if reglage.salaire_temps_plein is not None:
        if reglage.vieillesse_temps_plein:
            base = reglage.salaire_temps_plein
        if reglage.complementaire_temps_plein:
            complementaire = reglage.salaire_temps_plein
    elif au_forfait_jours:
        if reglage.vieillesse_temps_plein:
            seuil = COEFFICIENT_SMIC_FORFAIT * smic_horaire
            heures_considerees = brut / seuil if seuil > 0 else 0.0
            if seuil <= 0 or heures_considerees >= heures_temps_plein:
                alertes.append(_alerte(
                    "retraite_progressive_forfait_au_dela_1_7_smic",
                    f"Forfait jours : la vieillesse de base sur un temps plein n'est ouverte que sous "
                    f"1,7 SMIC ({_euros(seuil * heures_temps_plein)} ce mois) ; le brut est de "
                    f"{_euros(brut)}. Aucune surcotisation de base n'est posée. La retraite "
                    "complémentaire reste possible (Agirc-Arrco, avenant 23).",
                ))
            else:
                base = brut * heures_temps_plein / heures_considerees
        if reglage.complementaire_temps_plein:
            jours = jours_forfait or (quotite * lc.JOURS_FORFAIT_LEGAL if quotite else None)
            if jours:
                complementaire = brut * lc.JOURS_FORFAIT_LEGAL / jours
    else:
        heures_remunerees = heures_contrat_mois + max(0.0, heures_complementaires_mois)
        if 0 < heures_remunerees < heures_temps_plein:
            temps_plein = brut * heures_temps_plein / heures_remunerees
        elif quotite:
            temps_plein = brut / quotite
        else:
            temps_plein = None
        if reglage.vieillesse_temps_plein:
            base = temps_plein
        if reglage.complementaire_temps_plein:
            complementaire = temps_plein

    if reglage.complementaire_temps_plein and not reglage.vieillesse_temps_plein and not au_forfait_jours:
        alertes.append(_alerte(
            "retraite_progressive_complementaire_seule",
            "Complémentaire sur un temps plein sans la vieillesse de base : l'Agirc-Arrco ne "
            "l'ouvre qu'avec la base, sauf au forfait jours (ANI du 17/11/2017, art. 75).",
        ))
        complementaire = None

    arrondi = lambda v: round(v, 2) if v is not None and v > brut else None  # noqa: E731
    return SalairesTempsPlein(arrondi(base), arrondi(complementaire), quotite, tuple(alertes))


def _lignes_du_bareme(cotisations: List[Dict[str, Any]], identifiant: str) -> List[Dict[str, Any]]:
    return [c for c in cotisations if isinstance(c, dict) and c.get("id") == identifiant]


def lignes_de_surcotisation(
    reglage: ReglageRetraiteProgressive,
    salaires: SalairesTempsPlein,
    *,
    cotisations_du_bareme: List[Dict[str, Any]],
    brut: float,
    plafond: float,
    assiette_plafonnee: float,
    assiette_tranche_2: float,
    assiette_cet: float,
    calculer_ligne: Callable[..., Optional[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Les lignes « Surcotisation retraite progressive » du bulletin.

    ``plafond`` : le plafond du mois sans la réduction du temps partiel (R241-0-2,
    V), mais réduit d'une entrée, d'une sortie ou d'une absence non payée.
    ``calculer_ligne`` : `_calculer_une_ligne` du moteur des cotisations.
    """
    differentiels: Dict[str, float] = {}
    #: Montant de la base DSN de chaque ligne : 24 (plafonnée) ou 22 (déplafonnée).
    bases_dsn: Dict[str, float] = {}
    if salaires.base is not None:
        differentiels["plafonnee"] = max(0.0, min(salaires.base, plafond) - assiette_plafonnee)
        differentiels["deplafonnee"] = max(0.0, salaires.base - brut)
        bases_dsn["plafonnee"] = differentiels["plafonnee"]
        bases_dsn["deplafonnee"] = differentiels["deplafonnee"]
    if salaires.complementaire is not None:
        tp = min(salaires.complementaire, FACTEUR_PLAFOND_COMPLEMENTAIRE * plafond)
        differentiels["t1"] = max(0.0, min(tp, plafond) - assiette_plafonnee)
        differentiels["t2"] = max(0.0, max(0.0, tp - plafond) - max(0.0, assiette_tranche_2))
        # CET : due sur toute la rémunération quand elle dépasse le plafond ;
        # la part réelle n'en payait pas si le brut restait dessous.
        differentiels["cet"] = max(0.0, tp - assiette_cet) if tp > plafond else 0.0
        bases_dsn["t1"] = differentiels["t1"]
        bases_dsn["t2"] = bases_dsn["cet"] = max(0.0, tp - brut)

    lignes: List[Dict[str, Any]] = []
    suivies = (VIEILLESSE_DE_BASE if salaires.base is not None else ()) + (
        COMPLEMENTAIRE if salaires.complementaire is not None else ()
    )
    for id_bareme, id_ligne, assiette_cle in suivies:
        assiette = round(differentiels.get(assiette_cle, 0.0), 2)
        if assiette <= 0:
            continue
        for cotisation in _lignes_du_bareme(cotisations_du_bareme, id_bareme):
            taux_sal = cotisation.get("salarial")
            taux_pat = cotisation.get("patronal")
            taux_sal = float(taux_sal) if isinstance(taux_sal, (int, float)) else None
            taux_pat = float(taux_pat) if isinstance(taux_pat, (int, float)) else None
            ligne = calculer_ligne(
                f"{LIBELLE} – {cotisation.get('libelle') or id_bareme}",
                assiette,
                taux_sal,
                taux_pat,
                coti_id=id_ligne,
            )
            if not ligne:
                continue
            ligne["retraite_progressive"] = True
            ligne["assiette_base_dsn"] = round(bases_dsn.get(assiette_cle, assiette), 2)
            if reglage.prise_en_charge_part_salariale and ligne.get("montant_salarial"):
                # R241-0-3, II : la part salariale du supplément est payée par
                # l'employeur ; elle ne passe ni par le brut ni par la CSG (L241-3-1).
                prise = float(ligne["montant_salarial"])
                ligne["montant_patronal"] = round(float(ligne.get("montant_patronal") or 0.0) + prise, 2)
                ligne["taux_patronal"] = round((taux_pat or 0.0) + (taux_sal or 0.0), 6)
                ligne["montant_salarial"] = 0.0
                ligne["taux_salarial"] = None
                ligne["prise_en_charge_part_salariale"] = round(prise, 2)
            lignes.append(ligne)
    return lignes


def assiettes_dsn(lignes: List[Dict[str, Any]]) -> Dict[str, float]:
    """Montants des bases 22 (différentiel déplafonné) et 24 (plafonné) d'un bulletin."""
    bases: Dict[str, float] = {}
    for ligne in lignes:
        coti_id = str(ligne.get("coti_id") or "")
        montant = float(ligne.get("assiette_base_dsn") or ligne.get("base") or 0.0)
        if coti_id == "surcotisation_vieillesse_deplafonnee":
            bases["22"] = max(bases.get("22", 0.0), montant)
        elif coti_id == "surcotisation_vieillesse_plafonnee":
            bases["24"] = max(bases.get("24", 0.0), montant)
    return bases
