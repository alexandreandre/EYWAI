"""Mapping contrat / identité EYWAI → codes DSN P26."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional

from app.modules.dsn_import.domain.rubriques import CONTRACT_NATURE_MAP, STATUT_CADRE_CODES

# Inverse nature contrat
_NATURE_FROM_EYWAI: Dict[str, str] = {}
for code, label in CONTRACT_NATURE_MAP.items():
    _NATURE_FROM_EYWAI.setdefault(label.lower(), code)
# L'apprentissage et la professionnalisation restent des CDD (nature 02) : ce
# qui les distingue est porté par le dispositif de politique publique
# (S21.G00.40.008 = 65), pas par la nature du contrat. C'est ainsi que les
# déclare le cabinet dans les fichiers acceptés.
_NATURE_FROM_EYWAI.update(
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
    return _NATURE_FROM_EYWAI.get(key, "01")


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


def map_statut_categoriel_rc(statut_conventionnel: str) -> str:
    """Code statut catégoriel Retraite Complémentaire (S21.G00.40.003).

    Rubrique obligatoire, que nous n'émettions pas : 225 anomalies bloquantes
    relevées par DSN-VAL. La correspondance est lue dans les DSN acceptées du
    cabinet, où elle ne souffre aucune exception sur les statuts que nous
    produisons : statut conventionnel « 04 - cadre » → « 01 », « 06 - non
    cadre » → « 04 » (219 contrats sur 219).
    """
    return "01" if statut_conventionnel == "04" else "04"


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


def map_modalite_temps(
    *,
    is_temps_partiel: bool = False,
    duree_hebdo: Optional[float] = None,
    is_forfait_jour: bool = False,
    quotite_forfait_jours: str = "",
) -> tuple[str, str, str, str]:
    """Retourne (unité, quotité_ref, quotité, modalité).

    La quotité de référence de l'établissement reste la durée légale ; la
    quotité du contrat suit la durée réellement contractée. Une société à 39 h
    déclare 169,00 et non 151,67 — l'écart se voyait sur tous les bulletins
    Colorplast.

    Un salarié au forfait annuel en jours se compte en jours (unité 20), pas en
    heures : le déclarer à 151,67 heures le ferait passer pour un horaire.
    """
    if is_forfait_jour:
        quotite = quotite_forfait_jours or QUOTITE_MENSUELLE_FORFAIT_JOURS
        return "20", quotite, quotite, "10"
    # Unité 10 = heures ; quotité mensuelle 151.67 ≈ 35 h
    ref = "151.67"
    if not duree_hebdo or duree_hebdo <= 0:
        return "10", ref, ref, "20" if is_temps_partiel else "10"
    quotite = f"{round(duree_hebdo * 52 / 12, 2):.2f}"
    return "10", ref, quotite, "20" if is_temps_partiel else "10"
