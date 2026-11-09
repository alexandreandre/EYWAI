"""Mapping contrat / identité MARTINE → codes DSN P26."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional

from app.modules.dsn_import.domain.rubriques import CONTRACT_NATURE_MAP, STATUT_CADRE_CODES
from app.modules.employees.domain.rules import (
    DUREE_LEGALE_HEBDO,
    normalize_temps_travail_fields,
)

#: Numéro d'un contrat sans numéro repris : le premier de Quadra.
NUMERO_PREMIER_CONTRAT = "00000"


def numero_du_contrat(employee: Dict[str, Any]) -> str:
    """Numéro du contrat (S21.G00.40.009) : celui de la classification de la
    fiche — repris du cabinet, ou posé par « Nouveau contrat » (00000, 00001…,
    comme Quadra) —, « 00000 » sinon."""
    classification = employee.get("classification_conventionnelle")
    if not isinstance(classification, dict):
        classification = {}
    return str(
        classification.get("numero_contrat_dsn")
        or employee.get("numero_contrat")
        or employee.get("contract_number")
        or NUMERO_PREMIER_CONTRAT
    )


def debut_du_contrat(employee: Dict[str, Any]) -> str:
    """Début du contrat (S21.G00.40.001), AAAA-MM-JJ : celui repris du cabinet
    (`dsn_reprise.date_debut_contrat`) quand le contrat en cours y a commencé
    après l'embauche de la fiche — un CDD suivi d'un apprentissage, sur une
    seule fiche —, l'embauche sinon. Le cahier technique 2026.1 (§ 2.1.2.3.2)
    identifie un contrat par sa date de début et son numéro : les changer sans
    bloc 41 ouvre un second contrat chez les organismes. Une reprise d'avant
    l'embauche (la fiche a changé de contrat depuis) ou illisible est écartée."""
    embauche = str(employee.get("hire_date") or employee.get("date_entree") or "")[:10]
    specificites = employee.get("specificites_paie")
    reprise = employee.get("dsn_reprise") or (
        specificites.get("dsn_reprise") if isinstance(specificites, dict) else None
    )
    repris = str((reprise or {}).get("date_debut_contrat") or "")[:10]
    try:
        if date.fromisoformat(repris) > date.fromisoformat(embauche):
            return repris
    except ValueError:
        pass
    return embauche


def numero_suivant(numero: str) -> str:
    """Le numéro du contrat suivant d'un salarié : 00000 → 00001, comme Quadra ;
    00001 après un numéro qui n'est pas un nombre."""
    if numero.isdigit():
        return str(int(numero) + 1).zfill(max(len(numero), len(NUMERO_PREMIER_CONTRAT)))
    return str(1).zfill(len(NUMERO_PREMIER_CONTRAT))


# Inverse nature contrat
_NATURE_FROM_MARTINE: Dict[str, str] = {}
for code, label in CONTRACT_NATURE_MAP.items():
    _NATURE_FROM_MARTINE.setdefault(label.lower(), code)
# L'apprentissage et la professionnalisation restent des CDD (nature 02) : ce
# qui les distingue est porté par le dispositif de politique publique
# (S21.G00.40.008 = 65), pas par la nature du contrat. C'est ainsi que les
# déclare le cabinet dans les fichiers acceptés.
_NATURE_FROM_MARTINE.update(
    {
        "cdi": "01",
        "cdd": "02",
        "apprentissage": "02",
        "professionnalisation": "02",
        "contrat de professionnalisation": "02",
        "stage": "50",
        "alternance": "02",
    }
)


def iso_to_dsn_date(value: Any) -> str:
    """Convertit YYYY-MM-DD / date / datetime → JJMMAAAA."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d%m%Y")
    if isinstance(value, date):
        return value.strftime("%d%m%Y")
    text = str(value).strip()
    if not text:
        return ""
    clean = text.replace("/", "-")
    if len(clean) == 8 and clean.isdigit():
        # déjà JJMMAAAA ou AAAAMMJJ
        if int(clean[4:8]) > 1900:
            return clean  # JJMMAAAA
        return f"{clean[6:8]}{clean[4:6]}{clean[0:4]}"
    if len(clean) >= 10 and clean[4] == "-" and clean[7] == "-":
        y, m, d = clean[:10].split("-")
        return f"{d}{m}{y}"
    return ""


def period_to_mois_principal(period: str) -> str:
    """YYYY-MM → 01mmaaaa."""
    year, month = period.split("-")
    return f"01{month}{year}"


def period_bounds(period: str) -> tuple[str, str]:
    """Retourne (début, fin) JJMMAAAA du mois civil."""
    year_s, month_s = period.split("-")
    year, month = int(year_s), int(month_s)
    start = f"01{month:02d}{year}"
    if month == 12:
        next_y, next_m = year + 1, 1
    else:
        next_y, next_m = year, month + 1
    # dernier jour = jour 0 du mois suivant
    last = date(next_y, next_m, 1).fromordinal(
        date(next_y, next_m, 1).toordinal() - 1
    )
    end = last.strftime("%d%m%Y")
    return start, end


def map_contract_nature_to_dsn(contract_type: Optional[str]) -> str:
    if not contract_type:
        return "01"
    key = str(contract_type).strip().lower()
    if key.isdigit():
        return key.zfill(2)
    return _NATURE_FROM_MARTINE.get(key, "01")


def map_statut_to_dsn(statut: Optional[str], *, is_cadre: Optional[bool] = None) -> str:
    """Code statut conventionnel DSN (S21.G00.40.002)."""
    if is_cadre is True:
        return "04"
    if is_cadre is False:
        return "06"
    text = (statut or "").strip().lower()
    if text in {"cadre", "cadres"}:
        return "04"
    if any(c in text for c in STATUT_CADRE_CODES):
        return text.zfill(2) if text.isdigit() else "04"
    return "06"


def map_statut_categoriel_rc(statut_conventionnel: str, *, fiche_cadre: bool = False) -> str:
    """Code statut catégoriel Retraite Complémentaire (S21.G00.40.003).

    Rubrique obligatoire, que nous n'émettions pas : 225 anomalies bloquantes
    relevées par DSN-VAL. La correspondance est lue dans les DSN acceptées du
    cabinet, où elle ne souffre aucune exception sur les statuts que nous
    produisons : statut conventionnel « 04 - cadre » → « 01 », « 06 - non
    cadre » → « 04 » (219 contrats sur 219). Le statut « 05 » existe en « 02 »
    (extension cadre) et en « 04 » dans ces DSN : la fiche Cadre les distingue (R-019).
    """
    if statut_conventionnel == "04":
        return "01"
    return "02" if statut_conventionnel == "05" and fiche_cadre else "04"


#: Nationalités de l'Union européenne, hors France. Formes masculine et
#: féminine confondues, sans accent ni casse (voir `map_codification_ue`).
_NATIONALITES_UE = {
    "allemand", "allemande", "autrichien", "autrichienne", "belge",
    "bulgare", "chypriote", "croate", "danois", "danoise", "espagnol",
    "espagnole", "estonien", "estonienne", "finlandais", "finlandaise",
    "grec", "grecque", "hongrois", "hongroise", "irlandais", "irlandaise",
    "italien", "italienne", "letton", "lettonne", "lituanien", "lituanienne",
    "luxembourgeois", "luxembourgeoise", "maltais", "maltaise",
    "neerlandais", "neerlandaise", "hollandais", "hollandaise",
    "polonais", "polonaise", "portugais", "portugaise", "roumain",
    "roumaine", "slovaque", "slovene", "suedois", "suedoise", "tcheque",
}

#: Espace économique européen hors UE, plus la Suisse.
_NATIONALITES_EEE_SUISSE = {
    "islandais", "islandaise", "liechtensteinois", "liechtensteinoise",
    "norvegien", "norvegienne", "suisse", "suissesse",
}

_NATIONALITES_FRANCE = {"francais", "francaise", "france"}


def map_codification_ue(nationalite: Optional[str]) -> str:
    """Codification UE de l'individu (S21.G00.30.013).

    Rubrique obligatoire, absente de nos fichiers : 349 anomalies bloquantes.
    Quatre valeurs, vérifiées sur les DSN du cabinet : « 01 » France, « 02 »
    Union européenne hors France, « 03 » Espace économique européen et Suisse,
    « 04 » tout le reste.

    Le champ `nationality` est saisi en clair et sans discipline
    (`Française`, `FRANCE`, `Francaise`) : on compare sans accent ni casse. Une
    nationalité inconnue ou vide tombe en « 04 », qui n'ouvre aucun droit
    particulier — l'inverse serait de déclarer à tort un ressortissant
    européen.
    """
    texte = _sans_accent(str(nationalite or "")).strip().lower()
    if not texte:
        return "04"
    if texte in _NATIONALITES_FRANCE:
        return "01"
    if texte in _NATIONALITES_UE:
        return "02"
    if texte in _NATIONALITES_EEE_SUISSE:
        return "03"
    return "04"


def _sans_accent(texte: str) -> str:
    import unicodedata

    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


def map_sexe_to_dsn(sexe: Optional[str]) -> str:
    text = (sexe or "").strip().lower()
    if text in {"1", "01", "m", "h", "homme", "masculin"}:
        return "01"
    if text in {"2", "02", "f", "femme", "feminin", "féminin"}:
        return "02"
    return "01"


# Forfait annuel en jours : le cabinet déclare 21,27 jours par mois, soit
# 218 jours ramenés au mois (218 / 10,25 mois travaillés).
QUOTITE_MENSUELLE_FORFAIT_JOURS = "21.27"
#: Forfait jours réduit (fiche net-entreprises n° 3369) : 100 jours → 9,94, soit
#: 21,67 jours par mois pour un forfait complet de 218 jours.
JOURS_MENSUELS_FORFAIT_COMPLET = 21.67
JOURS_ANNUELS_FORFAIT_COMPLET = 218.0


def map_modalite_temps(
    *,
    is_temps_partiel: bool = False,
    duree_hebdo: Optional[float] = None,
    is_forfait_jour: bool = False,
    quotite_forfait_jours: str = "",
    jours_forfait_salarie: Optional[float] = None,
) -> tuple[str, str, str, str]:
    """Retourne (unité, quotité_ref, quotité, modalité).

    La quotité de référence de l'établissement reste la durée légale ; la
    quotité du contrat suit la durée réellement contractée. Une société à 39 h
    déclare 169,00 et non 151,67 — l'écart se voyait sur tous les bulletins
    Colorplast.

    Un salarié au forfait annuel en jours se compte en jours (unité 20), pas en
    heures : le déclarer à 151,67 heures le ferait passer pour un horaire.

    Un forfait réduit (``jours_forfait_salarie``, porté par la fiche) abaisse la
    seule quotité du contrat. La modalité reste « 10 - temps plein » : un forfait
    jours n'est jamais un temps partiel (fiche net-entreprises n° 3369 ; Cass.
    soc., 12 mars 2014, n° 12-29.141), même si la fiche coche le temps partiel.
    """
    if is_forfait_jour:
        reference = quotite_forfait_jours or QUOTITE_MENSUELLE_FORFAIT_JOURS
        quotite = reference
        if jours_forfait_salarie is not None and jours_forfait_salarie < JOURS_ANNUELS_FORFAIT_COMPLET:
            reduite = jours_forfait_salarie * JOURS_MENSUELS_FORFAIT_COMPLET / JOURS_ANNUELS_FORFAIT_COMPLET
            quotite = f"{min(round(reduite, 2), float(reference)):.2f}"
        return "20", reference, quotite, "10"
    # Unité 10 = heures ; quotité mensuelle 151.67 ≈ 35 h
    ref = "151.67"
    if not duree_hebdo or duree_hebdo <= 0:
        return "10", ref, ref, "20" if is_temps_partiel else "10"
    quotite = f"{round(duree_hebdo * 52 / 12, 2):.2f}"
    return "10", ref, quotite, "20" if is_temps_partiel else "10"


#: S21.G00.40.084 (cahier technique 2027.1) : le plafond suit-il la quotité ?
PLAFOND_PRORATISE = "01"
PLAFOND_NON_PRORATISE = "02"


def proratisation_du_plafond(
    *,
    is_temps_partiel: Optional[bool],
    duree_hebdo: Optional[float],
    is_forfait_jour: bool = False,
    jours_forfait_salarie: Optional[float] = None,
) -> Optional[str]:
    """Ce que le bulletin a fait du plafond, pour S21.G00.40.084 ; None hors champ.

    La rubrique ne concerne que le temps partiel et le forfait jours réduit. Elle
    répète la règle de la paie (`_calculer_assiettes`) : un temps partiel de moins
    de 35 h voit son plafond réduit, le calcul au forfait ne le réduit jamais.
    """
    if is_forfait_jour:
        if jours_forfait_salarie is None or jours_forfait_salarie >= JOURS_ANNUELS_FORFAIT_COMPLET:
            return None
        return PLAFOND_NON_PRORATISE
    temps_partiel, duree = normalize_temps_travail_fields(
        is_temps_partiel, float(duree_hebdo) if duree_hebdo is not None else None
    )
    if not temps_partiel:
        return None
    return PLAFOND_PRORATISE if duree < DUREE_LEGALE_HEBDO else PLAFOND_NON_PRORATISE
