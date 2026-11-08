"""Motif de rupture du contrat (S21.G00.62.002) : proposé, choisi, refusé.

Cahier technique DSN 2026.1, rubrique S21.G00.62.002 : CCH-11 dit quels motifs
sont autorisés selon la nature du contrat (S21.G00.40.007). Le choix est rangé
dans ``exit_notes.motif_dsn`` ; sans choix, le motif est proposé d'après le type
de sortie et le contrat, et rien ne s'invente quand ils ne suffisent pas.
Fonctions pures.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Tuple

from app.modules.dsn_export.domain.contract_map import map_contract_nature_to_dsn

#: Type de sortie MARTINE → motif de rupture (S21.G00.62.002).
MOTIF_RUPTURE = {
    "fin_cdd": "031",
    "demission": "059",
    "rupture_conventionnelle": "043",
    "licenciement": "020",
    "depart_retraite": "039",
    "mise_retraite": "038",
    "fin_periode_essai": "034",
    "deces": "066",
}
#: Origine de l'inaptitude saisie au dossier → motif de rupture.
MOTIF_INAPTITUDE = {"non_professionnelle": "091", "professionnelle": "092"}

LIBELLES = {
    "011": "Licenciement suite à liquidation ou redressement judiciaire",
    "012": "Licenciement suite à fermeture définitive de l'établissement",
    "014": "Licenciement pour motif économique",
    "015": "Licenciement pour fin de chantier ou d'opération",
    "020": "Licenciement pour autre motif",
    "031": "Fin de CDD à son terme",
    "033": "Rupture anticipée du CDD pour inaptitude constatée par le médecin du travail",
    "034": "Fin de période d'essai à l'initiative de l'employeur",
    "035": "Fin de période d'essai à l'initiative du salarié",
    "036": "Rupture anticipée du CDD à l'initiative de l'employeur",
    "037": "Rupture anticipée du CDD à l'initiative du salarié",
    "038": "Mise à la retraite par l'employeur",
    "039": "Départ à la retraite à l'initiative du salarié",
    "043": "Rupture conventionnelle",
    "058": "Prise d'acte de la rupture",
    "059": "Démission",
    "066": "Décès du salarié",
    "081": "Fin de contrat d'apprentissage",
    "082": "Résiliation judiciaire du contrat",
    "083": "Rupture pour force majeure ou fait du prince",
    "084": "Rupture d'un commun accord du CDD",
    "087": "Licenciement pour faute grave",
    "088": "Licenciement pour faute lourde",
    "089": "Licenciement pour force majeure",
    "091": "Licenciement pour inaptitude d'origine non professionnelle",
    "092": "Licenciement pour inaptitude d'origine professionnelle",
    "095": "Rupture anticipée du CDD pour faute grave",
    "096": "Rupture anticipée du CDD pour faute lourde",
    "097": "Rupture anticipée du CDD suite à fermeture de l'établissement",
}

_CDI_LARGE: FrozenSet[str] = frozenset({"01", "07", "08", "09", "50", "53", "54", "82", "91"})
_ESSAI = frozenset({"01", "02", "03", "07", "08", "09", "10", "50", "53", "54", "82", "91", "92"})
_RUPTURE_CDD = frozenset({"02", "03", "10", "53", "54", "60", "92"})
_FAUTE_CDD = frozenset({"02", "03", "10", "92"})

#: Natures de contrat autorisées (CCH-11). Un motif absent n'y est pas restreint.
_NATURES: Dict[str, FrozenSet[str]] = {
    "011": frozenset({"01", "07", "08", "09", "82", "91"}),
    "012": frozenset({"01", "07", "08", "09", "82", "91"}),
    "014": frozenset({"01", "07", "08", "09", "50", "53", "54", "91"}),
    "015": frozenset({"01", "07", "08", "09", "82"}),
    "020": frozenset({"01", "07", "08", "09", "10", "50", "53", "54", "82", "91"}),
    "031": frozenset({"02", "10", "53", "54", "60", "92"}),
    "033": frozenset({"02", "03", "10", "53", "54", "92"}),
    "034": _ESSAI,
    "035": _ESSAI,
    "036": _RUPTURE_CDD,
    "037": _RUPTURE_CDD,
    "038": frozenset({"01", "07", "08", "09", "50", "82", "91"}),
    "039": _CDI_LARGE,
    "043": _CDI_LARGE,
    "058": frozenset({"01", "07", "08", "09", "82", "91"}),
    "059": frozenset({"01", "03", "07", "08", "09", "50", "53", "54", "82", "91"}),
    "081": frozenset({"53", "54"}),
    "083": frozenset({"01", "02", "03", "09", "10", "91", "92", "53", "54"}),
    "084": _RUPTURE_CDD,
    "087": frozenset({"01", "07", "08", "09", "50", "82", "91"}),
    "088": frozenset({"01", "07", "08", "09", "50", "82", "91"}),
    "089": frozenset({"01", "07", "08", "09", "53", "54", "82", "91"}),
    "091": _CDI_LARGE,
    "092": _CDI_LARGE,
    "095": _FAUTE_CDD,
    "096": _FAUTE_CDD,
    "097": _FAUTE_CDD,
}

#: Motifs ouverts à d'autres natures selon le dispositif (40.008, CCH-11).
_NATURES_PAR_DISPOSITIF: Dict[str, Dict[str, FrozenSet[str]]] = {
    code: {"01": frozenset({"61", "64", "65"}), "91": frozenset({"61", "64", "65"}), "08": frozenset({"64", "65"})}
    for code in ("036", "037", "084")
}
_NATURES_PAR_DISPOSITIF["081"] = {
    nature: frozenset({"64", "65"}) for nature in ("01", "03", "08", "91")
}
_NATURES_PAR_DISPOSITIF["081"].update({nature: frozenset({"64", "65", "81"}) for nature in ("02", "92")})

#: Motifs de CDI et leur équivalent sur un CDD (CCH-11 : ils lui sont interdits).
_EQUIVALENT_CDD = {
    "059": "037",
    "020": "036",
    "043": "084",
    "087": "095",
    "091": "033",
    "092": "033",
}

_MENU_PAR_TYPE: Dict[str, Tuple[str, ...]] = {
    "fin_cdd": ("031", "081", "036", "037", "084", "033", "083", "095", "096", "097"),
    "licenciement": (
        "020", "014", "011", "012", "015", "089", "036", "097",
    ),
    "demission": ("059", "058", "037"),
    "rupture_conventionnelle": ("043", "084"),
    "deces": ("066",),
    "autre_motif": ("058", "082", "083", "089"),
}


def _jour(valeur: Any) -> Optional[date]:
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    try:
        return date.fromisoformat(str(valeur or "")[:10])
    except ValueError:
        return None


def _notes(sortie: Mapping[str, Any]) -> Mapping[str, Any]:
    notes = sortie.get("exit_notes")
    return notes if isinstance(notes, dict) else {}


def _contrat(employee: Mapping[str, Any]) -> Tuple[Optional[str], str, bool]:
    """(nature, dispositif, apprentissage). Nature inconnue sans type de contrat."""
    classification = employee.get("classification_conventionnelle")
    dispositif = str(
        (classification if isinstance(classification, dict) else {}).get("dispositif_politique_publique") or ""
    )
    type_contrat = employee.get("contract_type")
    apprentissage = dispositif in {"64", "65", "66"} or "apprenti" in str(type_contrat or "").lower()
    nature = map_contract_nature_to_dsn(type_contrat) if type_contrat else None
    return nature, dispositif, apprentissage


def _permis_sur_le_contrat(code: str, employee: Mapping[str, Any]) -> bool:
    """CCH-11 : le motif est-il autorisé pour cette nature de contrat ?"""
    nature, dispositif, apprentissage = _contrat(employee)
    natures = _NATURES.get(code)
    if nature is None or natures is None or nature in natures:
        return True
    if code == "081" and apprentissage:
        return True
    conditions = _NATURES_PAR_DISPOSITIF.get(code, {})
    return dispositif in conditions.get(nature, frozenset())


def motifs_possibles(sortie: Mapping[str, Any], employee: Mapping[str, Any]) -> List[str]:
    """Les motifs qui vont avec ce type de sortie, ce dossier et ce contrat."""
    type_sortie = str(sortie.get("exit_type") or "")
    notes = _notes(sortie)
    if type_sortie == "depart_retraite":
        menu: Tuple[str, ...] = (
            ("038",) if notes.get("retirement_initiator") == "employer" else ("039",)
        )
    elif type_sortie == "fin_periode_essai":
        menu = ("035",) if notes.get("probation_ended_by") == "employee" else ("034",)
    elif type_sortie == "licenciement":
        origine = notes.get("inaptitude_origine")
        if origine in MOTIF_INAPTITUDE:
            # CCH-29 : indemnités d'inaptitude et motif vont ensemble.
            menu = (MOTIF_INAPTITUDE[origine], "033")
        elif sortie.get("is_gross_misconduct"):
            menu = ("087", "088", "095", "096")
        else:
            menu = _MENU_PAR_TYPE["licenciement"]
    else:
        menu = _MENU_PAR_TYPE.get(type_sortie, ())
    return [code for code in menu if _permis_sur_le_contrat(code, employee)]


def _motif_de_base(sortie: Mapping[str, Any], apprentissage: bool) -> str:
    type_sortie = str(sortie.get("exit_type") or "")
    notes = _notes(sortie)
    motif = MOTIF_RUPTURE.get(type_sortie, "")
    if type_sortie == "licenciement":
        if sortie.get("is_gross_misconduct"):
            motif = "087"
        elif notes.get("inaptitude_origine") in MOTIF_INAPTITUDE:
            # Licenciement pour inaptitude (cahier technique 2026.1, 091 et 092).
            motif = MOTIF_INAPTITUDE[notes["inaptitude_origine"]]
    elif type_sortie == "depart_retraite" and notes.get("retirement_initiator") == "employer":
        # Mise à la retraite par l'employeur (cahier technique 2026.1, 038).
        motif = MOTIF_RUPTURE["mise_retraite"]
    elif type_sortie == "fin_periode_essai" and notes.get("probation_ended_by") == "employee":
        # Fin de période d'essai à l'initiative du salarié (cahier technique 2026.1, 035).
        motif = "035"
    elif type_sortie == "fin_cdd" and apprentissage:
        motif = "081"
    return motif


def motif_propose(
    sortie: Mapping[str, Any], employee: Mapping[str, Any], *, apprentissage: bool = False
) -> Tuple[str, Optional[str]]:
    """(code proposé, raison). Code vide : le dossier doit le dire, la raison dit quoi faire."""
    type_sortie = str(sortie.get("exit_type") or "")
    apprentissage = apprentissage or _contrat(employee)[2]
    fin = _jour(sortie.get("last_working_day"))
    terme = _jour(employee.get("contract_end_date"))
    if type_sortie == "fin_cdd" and fin and terme and fin < terme:
        return "", (
            f"Ce CDD s'arrête le {fin:%d/%m/%Y}, avant son terme du {terme:%d/%m/%Y} : "
            "choisissez qui rompt et pourquoi dans le motif DSN du dossier de sortie."
        )
    motif = _motif_de_base(sortie, apprentissage)
    if not motif:
        return "", (
            "Ce type de sortie ne donne pas de motif DSN : choisissez-le dans le dossier de sortie."
        )
    if not _permis_sur_le_contrat(motif, employee):
        equivalent = _EQUIVALENT_CDD.get(motif)
        if equivalent and _permis_sur_le_contrat(equivalent, employee):
            return equivalent, None
        return "", (
            f"Le motif {motif} n'est pas autorisé pour ce contrat : choisissez le motif DSN "
            "dans le dossier de sortie."
        )
    return motif, None


def motif_refuse(
    code: str, sortie: Mapping[str, Any], employee: Mapping[str, Any]
) -> Optional[str]:
    """Pourquoi ce motif ne va pas, en français simple ; None s'il convient."""
    possibles = motifs_possibles(sortie, employee)
    if code in possibles:
        return None
    if possibles:
        liste = ", ".join(f"{p} ({LIBELLES[p]})" for p in possibles)
        action = f"Choisissez un motif de la liste : {liste}."
    else:
        action = "Cette sortie n'a pas de motif DSN à choisir."
    libelle = LIBELLES.get(code)
    nom = f"{code} ({libelle})" if libelle else code
    return f"Le motif {nom} ne va pas avec ce contrat ou ce type de sortie. {action}"


def resume_du_dossier(sortie: Mapping[str, Any], employee: Mapping[str, Any]) -> Dict[str, Any]:
    """Ce qu'affiche le dossier de sortie : choix, proposition, motif retenu, liste."""
    choisi = _notes(sortie).get("motif_dsn")
    propose, raison = motif_propose(sortie, employee)
    refus = motif_refuse(str(choisi), sortie, employee) if choisi else None
    retenu = "" if refus else str(choisi or propose)
    alerte = refus or (None if choisi else raison)
    options = motifs_possibles(sortie, employee)
    return {
        "choisi": choisi or None,
        "propose": propose or None,
        "retenu": retenu or None,
        "alerte": alerte,
        "options": [{"code": code, "libelle": LIBELLES[code]} for code in options],
    }
