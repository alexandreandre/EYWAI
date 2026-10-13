"""
Le reçu pour solde de tout compte tiré du bulletin du mois de sortie.

Le reçu récapitule les sommes versées au départ : ce sont celles du dernier
bulletin. On les recalculait à part — salaire contractuel proratisé, cotisations
à zéro, indemnités du dossier de départ — et le reçu contredisait le bulletin
réellement payé (fin de CDD de juillet 2026 : 2 584,10 € au reçu, 2 785,59 € au
bulletin repris de l'ancien logiciel ; précarité et indemnité de congés d'un
autre calcul).

Quand le bulletin du mois de sortie existe, calculé ou repris, le reçu reprend
ses lignes et ses totaux : brut, sommes versées après cotisations, net à payer.
Sans bulletin, le reçu reste une estimation (cas par type de rupture).
"""

from __future__ import annotations

import unicodedata
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from .html_renderer import amount_row, amounts_section, render_solde_tout_compte_html
from .pdf_helpers import safe_float

#: Motif en clair, repris des cas par type de rupture.
MOTIFS = {
    "demission": "démission",
    "rupture_conventionnelle": "rupture conventionnelle",
    "licenciement": "licenciement",
    "depart_retraite": "départ à la retraite",
    "fin_periode_essai": "fin / rupture de période d'essai",
    "fin_cdd": "fin de contrat à durée déterminée",
}

# Libellés des sommes dues au titre de la rupture, quel que soit le logiciel qui
# a fait le bulletin (« Ind.de précarité des CDD », « Indemnité compensatrice de
# congés payés », « Ind.de CP des CDD »…). L'arbitrage des congés payés du mois
# n'en est pas : c'est du salaire.
_MARQUES_DE_RUPTURE = (
    "precarite",
    "fin de contrat",
    "compensatrice",
    "preavis",
    "licenciement",
    "rupture",
    "retraite",
    "ind.de cp",
    "ind. de cp",
    "indemnite de cp",
    "indemnite cp",
)


def _normalise(texte: Any) -> str:
    sans_accents = unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore")
    return " ".join(sans_accents.decode().lower().split())


def est_une_somme_de_rupture(libelle: Any) -> bool:
    n = _normalise(libelle)
    return any(marque in n for marque in _MARQUES_DE_RUPTURE)


def _date(valeur: Any) -> Optional[date]:
    if isinstance(valeur, date):
        return valeur
    try:
        return datetime.fromisoformat(str(valeur)[:10]).date()
    except (TypeError, ValueError):
        return None


def bulletin_du_mois_de_sortie(
    employee_id: Optional[str], exit_data: Dict[str, Any], supabase_client: Any
) -> Optional[Dict[str, Any]]:
    """Le bulletin du mois du dernier jour travaillé, s'il existe."""
    sortie = _date(exit_data.get("last_working_day"))
    if not employee_id or not sortie or supabase_client is None:
        return None
    resp = (
        supabase_client.table("payslips")
        .select("year, month, payslip_data")
        .eq("employee_id", employee_id)
        .eq("year", sortie.year)
        .eq("month", sortie.month)
        .limit(1)
        .execute()
    )
    lignes = getattr(resp, "data", None) or []
    if not lignes:
        return None
    donnees = lignes[0].get("payslip_data") or {}
    return donnees if donnees.get("salaire_brut") is not None else None


#: Alertes du bulletin de sortie que la génération du reçu redit à la gestionnaire.
CODES_ALERTES_DU_RECU = ("rtt_jtc_non_payes_au_depart",)


def alertes_du_recu(payslip_data: Optional[Dict[str, Any]]) -> List[str]:
    """Les alertes du bulletin de sortie qui valent pour le reçu (RTT et JTC
    non pris, « Néant » : à vérifier selon l'accord, décision du 12/10/2026)."""
    if not isinstance(payslip_data, dict):
        return []
    return [
        str(a.get("message"))
        for a in payslip_data.get("alertes_baremes") or []
        if isinstance(a, dict) and a.get("code") in CODES_ALERTES_DU_RECU and a.get("message")
    ]


def indemnites_compensatrices_de_conges(payslip_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Les lignes « Indemnité compensatrice de congés payés … » du bulletin.

    Le moteur les range avec les congés (`details_conges`), pas dans
    `calcul_du_brut` : sans cette lecture, l'indemnité versée manquait au reçu,
    à l'attestation France Travail et à la DSN. Les congés du mois (absence et
    indemnité de congés pris) restent du salaire."""
    return [
        ligne
        for ligne in payslip_data.get("details_conges") or []
        if isinstance(ligne, dict) and "compensatrice" in _normalise(ligne.get("libelle"))
    ]


def _detail(ligne: Dict[str, Any]) -> str:
    quantite, taux = ligne.get("quantite"), ligne.get("taux")
    if quantite in (None, "") or taux in (None, "", 100):
        return ""
    return f"{safe_float(quantite):g} × {safe_float(taux):.4f}".rstrip("0").rstrip(".")


def lignes_du_bulletin(
    payslip_data: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """(rémunération, sommes de rupture soumises, sommes versées après cotisations)."""
    remuneration: List[Dict[str, Any]] = []
    rupture: List[Dict[str, Any]] = []
    # Le moteur porte les retenues d'absence (dont l'entrée ou la sortie en
    # cours de mois) dans details_absences ; un bulletin repris les a dans
    # calcul_du_brut et details_absences vide.
    lignes = (
        list(payslip_data.get("calcul_du_brut") or [])
        + list(payslip_data.get("details_absences") or [])
        + indemnites_compensatrices_de_conges(payslip_data)
    )
    for ligne in lignes:
        libelle = str(ligne.get("libelle") or "").strip()
        if ligne.get("is_sous_total") or _normalise(libelle).startswith(("sous-total", "total")):
            continue
        montant = round(safe_float(ligne.get("gain")) - safe_float(ligne.get("perte")), 2)
        if not montant:
            continue
        cible = rupture if est_une_somme_de_rupture(libelle) else remuneration
        cible.append(amount_row(libelle, _detail(ligne), montant))

    apres_cotisations: List[Dict[str, Any]] = []
    for ligne in payslip_data.get("primes_non_soumises") or []:
        montant = round(safe_float(ligne.get("montant")), 2)
        if montant:
            apres_cotisations.append(amount_row(str(ligne.get("libelle") or "Somme non soumise"), "", montant))
    for ligne in (payslip_data.get("indemnites_sortie") or {}).get("lignes_exonerees") or []:
        montant = round(safe_float(ligne.get("montant")), 2)
        if montant:
            apres_cotisations.append(
                amount_row(
                    str(ligne.get("libelle") or "Indemnité de rupture"),
                    # Le régime calculé par le bulletin (limites, CSG/CRDS) : la
                    # « limite légale » n'est écrite que si elle a été calculée.
                    str(ligne.get("note") or "Versée après cotisations"),
                    montant,
                )
            )
    return remuneration, rupture, apres_cotisations


def sommes_de_rupture_du_bulletin(payslip_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Les sommes dues au titre de la rupture, soumises ou non : {libelle, montant, dans_le_brut}."""
    sommes: List[Dict[str, Any]] = []
    lignes_du_brut = list(payslip_data.get("calcul_du_brut") or []) + indemnites_compensatrices_de_conges(
        payslip_data
    )
    for ligne in lignes_du_brut:
        libelle = str(ligne.get("libelle") or "").strip()
        if ligne.get("is_sous_total") or not est_une_somme_de_rupture(libelle):
            continue
        montant = round(safe_float(ligne.get("gain")) - safe_float(ligne.get("perte")), 2)
        if montant:
            sommes.append({"libelle": libelle, "montant": montant, "dans_le_brut": True})
    apres = list(payslip_data.get("primes_non_soumises") or [])
    exonerees = (payslip_data.get("indemnites_sortie") or {}).get("lignes_exonerees") or []
    for ligne in apres + list(exonerees):
        libelle = str(ligne.get("libelle") or "").strip()
        montant = round(safe_float(ligne.get("montant")), 2)
        if montant and (ligne in exonerees or est_une_somme_de_rupture(libelle)):
            sommes.append({"libelle": libelle, "montant": montant, "dans_le_brut": False})
    return sommes


#: Libellés d'indemnité compensatrice de congés payés, moteur ou ancien logiciel.
_MARQUES_ICCP = (
    "compensatrice de conges",
    "cp des cdd",
    "ind.de cp",
    "ind. de cp",
    "indemnite de cp",
    "indemnite cp",
)


def indemnite_de_conges_du_bulletin(payslip_data: Dict[str, Any]) -> float:
    """L'indemnité compensatrice de congés versée par le bulletin de sortie
    (0 s'il n'en verse aucune) : c'est elle que l'onglet « Indemnités » montre,
    pas l'estimation du dossier."""
    return round(
        sum(
            s["montant"]
            for s in sommes_de_rupture_du_bulletin(payslip_data)
            if any(marque in _normalise(s["libelle"]) for marque in _MARQUES_ICCP)
        ),
        2,
    )


def generate_solde_depuis_bulletin(
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    exit_data: Dict[str, Any],
    payslip_data: Dict[str, Any],
) -> bytes:
    remuneration, rupture, apres_cotisations = lignes_du_bulletin(payslip_data)
    brut = round(safe_float(payslip_data.get("salaire_brut")), 2)
    net = round(safe_float(payslip_data.get("net_a_payer")), 2)
    verse_apres = round(sum(l["montant"] for l in apres_cotisations), 2)

    # Les sections somment toujours au brut du bulletin : un élément que l'on
    # n'a pas su lire reste visible, sous son propre libellé.
    ecart = round(brut - sum(l["montant"] for l in remuneration + rupture), 2)
    if abs(ecart) >= 0.01:
        remuneration.append(amount_row("Autres éléments du bulletin", "", ecart))

    sections = [amounts_section("RÉMUNÉRATION DU DERNIER MOIS", remuneration)]
    if rupture:
        sections.append(amounts_section("INDEMNITÉS DE FIN DE CONTRAT SOUMISES À COTISATIONS", rupture))
    if apres_cotisations:
        sections.append(amounts_section("SOMMES VERSÉES APRÈS COTISATIONS", apres_cotisations))

    exit_type = str(exit_data.get("exit_type") or "")
    sortie = _date(exit_data.get("last_working_day"))
    mois = f"{sortie.month:02d}/{sortie.year}" if sortie else ""
    return render_solde_tout_compte_html(
        employee_data,
        company_data,
        exit_data,
        motif_label=MOTIFS.get(exit_type, "rupture du contrat de travail"),
        sections=sections,
        total_brut=brut,
        # Cotisations et retenues du bulletin : brut + sommes versées après
        # cotisations − net payé (impôt à la source et retenues compris).
        total_cotisations=round(brut + verse_apres - net, 2),
        total_net=net,
        specific_mention=f"Sommes versées avec le bulletin de paie de {mois}.",
        sommes_apres_cotisations=verse_apres or None,
    )
