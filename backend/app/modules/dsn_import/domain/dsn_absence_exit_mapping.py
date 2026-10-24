"""Mapping motifs DSN → enums MARTINE (absences / sorties)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.modules.dsn_import.domain.normalize import normalize_date_dsn
from app.shared.domain.absence_calendar import daterange_days

# Motifs de rupture DSN (S21.G00.62.002) → type de départ de Martine.
# Source : cahier technique DSN 2026.1 (NEODeS, 24/12/2025), rubrique
# S21.G00.62.002 « Motif de la rupture du contrat », p. 273-274 (copie locale
# docs/audit-maji-2026/sources/dsn-cahier-technique-2026.1.txt). Chaque motif va
# au type le plus proche ; la mise à la retraite (038) n'a pas encore de type
# propre et rejoint les départs à la retraite. Le motif d'origine reste dans
# « Import DSN (0xx) » et c'est lui que la DSN de Martine réémet.
EXIT_MOTIF_MAP: Dict[str, str] = {
    # Licenciements et ruptures à l'initiative de l'employeur
    "011": "licenciement",  # liquidation ou redressement judiciaire
    "012": "licenciement",  # fermeture définitive de l'établissement
    "014": "licenciement",  # motif économique
    "015": "licenciement",  # fin de chantier ou d'opération
    "020": "licenciement",  # autre motif
    "025": "licenciement",  # autre fin de contrat pour motif économique
    "026": "licenciement",  # motif économique après acceptation d'un CSP
    "065": "licenciement",  # décès de l'employeur ou internement
    "082": "licenciement",  # résiliation judiciaire
    "083": "licenciement",  # force majeure ou fait du prince
    "086": "licenciement",  # convention CATS
    "087": "licenciement",  # faute grave
    "088": "licenciement",  # faute lourde
    "089": "licenciement",  # force majeure
    "091": "licenciement",  # inaptitude d'origine non professionnelle
    "092": "licenciement",  # inaptitude d'origine professionnelle
    "093": "licenciement",  # décision d'une autorité administrative
    "112": "licenciement",  # accord de performance collective
    "113": "licenciement",  # motif spécifique (L2254-2)
    "115": "licenciement",  # articles 18 et 19 de la loi 2017-1339
    "117": "licenciement",  # motif économique après refus d'un CSP
    # Fins de CDD, de mission ou d'apprentissage, à terme ou anticipées
    "031": "fin_cdd",  # fin de CDD ou fin d'accueil occasionnel
    "032": "fin_cdd",  # fin de mission d'intérim
    "033": "fin_cdd",  # rupture anticipée pour inaptitude
    "036": "fin_cdd",  # rupture anticipée à l'initiative de l'employeur
    "037": "fin_cdd",  # rupture anticipée à l'initiative du salarié
    "081": "fin_cdd",  # fin de contrat d'apprentissage
    "084": "fin_cdd",  # rupture d'un commun accord du CDD, de l'apprentissage, de la mission
    "094": "fin_cdd",  # rupture anticipée pour arrêt de tournage
    "095": "fin_cdd",  # rupture anticipée pour faute grave
    "096": "fin_cdd",  # rupture anticipée pour faute lourde
    "097": "fin_cdd",  # rupture anticipée suite à fermeture de l'établissement
    # Périodes d'essai
    "034": "fin_periode_essai",  # à l'initiative de l'employeur
    "035": "fin_periode_essai",  # à l'initiative du salarié
    # Retraite
    "038": "depart_retraite",  # mise à la retraite par l'employeur
    "039": "depart_retraite",  # départ à la retraite à l'initiative du salarié
    # Ruptures d'un commun accord
    "043": "rupture_conventionnelle",
    "110": "rupture_conventionnelle",  # rupture conventionnelle collective
    "111": "rupture_conventionnelle",  # congé de mobilité
    "114": "rupture_conventionnelle",  # entrée en PAP
    # À l'initiative du salarié
    "058": "demission",  # prise d'acte de la rupture
    "059": "demission",
    # Sans rupture du contrat
    "100": "transfert",  # mutation au sein du groupe
    "998": "transfert",  # transfert vers un autre établissement
}

# Absences : cahier technique DSN 2026.1 (NEODeS, CT2026.1.2 du 24/12/2025),
# https://www.net-entreprises.fr/media/documentation/dsn-cahier-technique-2026.1.pdf
# Bloc S21.G00.60 « Arrêt de travail », rubrique .001 « Motif de l'arrêt »
# (p. 266) ; bloc S21.G00.65 « Autre suspension de l'exécution du contrat »,
# rubrique .001 « Motif de suspension » (p. 281-283). Le bloc S21.G00.41
# (« Changements Contrat », p. 215) ne porte que les valeurs d'avant une
# modification du contrat : il n'est jamais une absence.

#: Motif d'arrêt (S21.G00.60.001) → (nature, type d'arrêt) de Martine. Les
#: mêmes que l'export (dsn_export/domain/evenements.py), lus à l'envers.
ARRET_MOTIF_MAP: Dict[str, Tuple[str, str]] = {
    "01": ("arret_maladie", "maladie_simple"),
    "02": ("arret_maternite", "maternite"),
    "03": ("arret_paternite", "paternite"),  # paternité / accueil de l'enfant
    "04": ("arret_at", "accident_trajet"),
    "05": ("arret_maladie_pro", "maladie_professionnelle"),
    "06": ("arret_at", "accident_travail"),  # accident de travail ou de service
    "09": ("arret_maternite", "adoption"),
}

#: Accident de trajet, maladie professionnelle, accident du travail : l'arrêt
#: est prescrit le jour de l'accident, qui est travaillé (60.002 : « arrêt
#: prescrit lors d'un jour travaillé : le dernier jour travaillé correspond
#: alors à la date de l'arrêt »). L'arrêt commence ce jour-là : c'est la règle
#: de l'export (dsn_export/domain/evenements.py, MOTIFS_ACCIDENT) et ce
#: qu'imprime Quadra (60.002 = 23/05, « Absence A.T. 230526-290526 »).
#: Pour les autres motifs, .002 est la veille de la prescription.
MOTIFS_ARRET_PRESCRIT_LE_JOUR_TRAVAILLE = frozenset({"04", "05", "06"})

#: Libellés de la norme, pour dire ce qui n'est pas repris.
LIBELLES_MOTIF_ARRET: Dict[str, str] = {
    "01": "maladie",
    "02": "maternité",
    "03": "paternité / accueil de l'enfant",
    "04": "congé suite à un accident de trajet",
    "05": "congé suite à maladie professionnelle",
    "06": "congé suite à accident de travail ou de service",
    "07": "femme enceinte dispensée de travail",
    "09": "adoption",
    "10": "[FP] congé suite à une maladie imputable au service",
    "11": "[FP] congé de maladie des victimes ou réformés de guerre",
    "12": "[FP] congé de longue durée",
    "13": "[FP] congé de longue maladie",
    "14": "[FP] congé pour invalidité temporaire imputable au service",
    "15": "temps partiel thérapeutique (risque maladie)",
    "16": "temps partiel thérapeutique (risque accident de travail)",
    "17": "temps partiel thérapeutique (risque accident de trajet)",
    "18": "temps partiel thérapeutique (risque maladie professionnelle)",
    "19": "deuil d'enfant",
    "20": "congé supplémentaire de naissance",
    "99": "annulation",
}

#: Motif de suspension (S21.G00.65.001) → type d'absence de Martine. Seules
#: les suspensions prises en jours entiers sur toute la période : le congé de
#: proche aidant, de présence parentale ou de solidarité familiale se
#: fractionnent (65.005 en demi-journées), le congé pour enfant malade peut
#: être payé par la convention ; ils restent à saisir.
SUSPENSION_ABSENCE_MAP: Dict[str, str] = {
    "501": "sans_solde",  # congé divers non rémunéré
    "632": "sans_solde",  # congé parental d'éducation
    "635": "sans_solde",  # congé pour création ou reprise d'entreprise
    "639": "sans_solde",  # congé sabbatique
    "680": "sans_solde",  # congé sans solde cotisé
    "637": "evenement_familial",  # congé pour évènement familial
}

LIBELLES_MOTIF_SUSPENSION: Dict[str, str] = {
    "112": "invalidité catégorie 1",
    "114": "invalidité catégorie 2",
    "116": "invalidité catégorie 3",
    "200": "congés payés (caisse de congés)",
    "301": "congé de formation professionnelle",
    "501": "congé divers non rémunéré",
    "507": "chômage intempéries",
    "601": "mobilité",
    "602": "chômage sans rupture de contrat",
    "603": "détention provisoire",
    "607": "congé de présence parentale",
    "609": "congé individuel de formation",
    "610": "projet de transition professionnelle",
    "611": "congé de bilan de compétences",
    "618": "congé de formation économique, sociale et syndicale",
    "627": "congé de solidarité familiale",
    "632": "congé parental d'éducation",
    "635": "congé pour création ou reprise d'entreprise",
    "636": "congé pour enfant malade",
    "637": "congé pour évènement familial",
    "639": "congé sabbatique",
    "650": "congé de proche aidant",
    "652": "inaptitude temporaire liée à la grossesse",
    "680": "congé sans solde cotisé",
    "686": "contrat suspendu pour expatriation",
    "998": "annulation",
}


def map_exit_motif(motif: str) -> str:
    """Le type de départ d'un motif de rupture DSN.

    Un motif renseigné sans équivalent (066, 085, 098, 099…) devient « Autre
    motif » et non une démission : son code reste dans « Import DSN (0xx) ».
    Sans motif du tout, on garde la démission.
    """
    brut = (motif or "").strip()
    if not brut:
        return "demission"
    code = brut.zfill(3)[:3]
    return EXIT_MOTIF_MAP.get(code, "autre_motif")


BLOC_ARRET = "S21.G00.60"
BLOC_SUSPENSION = "S21.G00.65"


def _code(motif: str, longueur: int) -> str:
    brut = (motif or "").strip()
    return brut.zfill(longueur)[:longueur] if brut else ""


def map_arret_motif(motif: str) -> Optional[Tuple[str, str]]:
    """(nature, type d'arrêt) d'un motif d'arrêt, ou None s'il n'a pas d'équivalent."""
    return ARRET_MOTIF_MAP.get(_code(motif, 2))


def map_suspension_to_absence(motif: str) -> Optional[str]:
    """Type d'absence d'un motif de suspension, ou None s'il n'a pas d'équivalent."""
    return SUSPENSION_ABSENCE_MAP.get(_code(motif, 3))


def libelle_motif(bloc: str, motif: str) -> str:
    if bloc == BLOC_ARRET:
        return LIBELLES_MOTIF_ARRET.get(_code(motif, 2), f"motif {motif or 'absent'}")
    return LIBELLES_MOTIF_SUSPENSION.get(_code(motif, 3), f"motif {motif or 'absent'}")


def _jour(valeur: str) -> Optional[date]:
    iso = normalize_date_dsn(valeur or "")
    try:
        return date.fromisoformat(iso) if iso else None
    except ValueError:
        return None


def bornes_arret(arret: Any) -> Optional[Tuple[date, date]]:
    """(premier, dernier) jour d'absence d'un bloc 60.

    Premier : le lendemain du dernier jour travaillé (.002), sauf accident
    (motifs 04, 05, 06) où l'arrêt est prescrit le jour de l'accident, .002
    lui-même. Dernier : la veille de la reprise (.010, « premier jour travaillé
    et payé ») si elle est déclarée, sinon la fin prévisionnelle (.003). None si
    l'arrêt ne couvre aucun jour.
    """
    dernier_travaille = _jour(arret.dernier_jour_travaille)
    if dernier_travaille is None:
        return None
    reprise = _jour(arret.date_reprise)
    fin = reprise - timedelta(days=1) if reprise else _jour(arret.fin_previsionnelle)
    if _code(arret.motif, 2) in MOTIFS_ARRET_PRESCRIT_LE_JOUR_TRAVAILLE:
        debut = dernier_travaille
    else:
        debut = dernier_travaille + timedelta(days=1)
    if fin is None or fin < debut:
        return None
    return debut, fin


def bornes_suspension(suspension: Any) -> Optional[Tuple[date, date]]:
    debut = _jour(suspension.date_debut)
    fin = _jour(suspension.date_fin)
    if debut is None or fin is None or fin < debut:
        return None
    return debut, fin


def derniere_declaration(blocs: Iterable[Any], cle, bornes) -> List[Any]:
    """Un bloc par absence, même déclarée plusieurs fois.

    Un arrêt de plus d'un mois est redéclaré dans chaque DSN, une prolongation
    garde le même dernier jour travaillé, et certains logiciels mettent l'arrêt
    initial et sa prolongation dans la même DSN. Pour une même clé (motif,
    date de départ), la DSN la plus récente l'emporte — elle porte la reprise
    ou la prolongation ; dans une même DSN, la fin la plus tardive.
    """
    retenus: Dict[Any, Tuple[Tuple[str, date], Any]] = {}
    for bloc in blocs:
        b = bornes(bloc)
        if b is None:
            continue
        rang = (bloc.periode_dsn or "", b[1])
        k = cle(bloc)
        if k not in retenus or rang >= retenus[k][0]:
            retenus[k] = (rang, bloc)
    return [bloc for _, bloc in retenus.values()]


def _payload(
    debut: date,
    fin: date,
    absence_type: str,
    arret_type: Optional[str],
    motif: str,
    *,
    siret: str,
    nir: str,
    employee_label: str,
    dsn_block: str,
    suffixe: str = "",
) -> Dict[str, Any]:
    start, end = debut.isoformat(), fin.isoformat()
    return {
        "absence_type": absence_type,
        "arret_type": arret_type,
        "selected_days": [d.isoformat() for d in daterange_days(debut, fin)],
        "date_debut": start,
        "date_fin": end,
        "motif_dsn": motif,
        "siret": siret,
        "nir": nir,
        "employee_label": employee_label,
        "source_key": f"{start}:{end}:{absence_type}{suffixe}",
        "dsn_block": dsn_block,
    }


def build_absence_payload_from_arret(
    arret: Any,
    *,
    siret: str,
    nir: str,
    employee_label: str,
) -> Optional[Dict[str, Any]]:
    """Payload preview absence d'un bloc 60 ; None sans équivalent ou sans jour."""
    nature = map_arret_motif(arret.motif)
    bornes = bornes_arret(arret)
    if nature is None or bornes is None:
        return None
    payload = _payload(
        *bornes,
        *nature,
        _code(arret.motif, 2),
        siret=siret,
        nir=nir,
        employee_label=employee_label,
        dsn_block="G00.60",
    )
    payload["dernier_jour_travaille"] = normalize_date_dsn(arret.dernier_jour_travaille)
    payload["date_reprise"] = normalize_date_dsn(arret.date_reprise)
    payload["subrogation_dsn"] = (arret.subrogation or "").strip() == "01"
    return payload


def build_absence_payload_from_suspension(
    suspension: Any,
    *,
    siret: str,
    nir: str,
    employee_label: str,
) -> Optional[Dict[str, Any]]:
    """Payload preview absence d'un bloc 65 ; None sans équivalent."""
    absence_type = map_suspension_to_absence(suspension.motif)
    bornes = bornes_suspension(suspension)
    if absence_type is None or bornes is None:
        return None
    return _payload(
        *bornes,
        absence_type,
        None,
        _code(suspension.motif, 3),
        siret=siret,
        nir=nir,
        employee_label=employee_label,
        dsn_block="G00.65",
        suffixe=":suspension",
    )


def build_exit_payload_from_fin_contrat(
    fin: Any,
    *,
    siret: str,
    nir: str,
    employee_label: str,
) -> Optional[Dict[str, Any]]:
    lwd = normalize_date_dsn(fin.date_fin)
    if not lwd:
        return None
    motif = fin.motif or ""
    exit_type = map_exit_motif(motif)
    source_key = f"{lwd}:{exit_type}:{motif}"

    return {
        "exit_type": exit_type,
        "last_working_day": lwd,
        "exit_request_date": lwd,
        "motif_dsn": motif,
        "date_notification": normalize_date_dsn(fin.date_notification),
        "siret": siret,
        "nir": nir,
        "employee_label": employee_label,
        "source_key": source_key,
        "dsn_block": "G00.62",
    }
