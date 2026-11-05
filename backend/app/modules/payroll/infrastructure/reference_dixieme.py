"""Lectures du dixième ; les montants se calculent dans le seul domaine pur.

L'historique destiné au moteur est injecté à ses deux entrées de cumuls,
jamais relu par calcul_conges. Aucun cumul repris n'est réécrit.
"""
from __future__ import annotations

import copy
import logging
from collections.abc import Mapping
from dataclasses import asdict
from datetime import date, timedelta
from typing import Any

from app.shared.domain.dixieme_conges import (
    BaseDixieme,
    calculer_base_periode,
    est_libelle_absence,
    part_reconstituee,
    texte_normalise,
)

CLE_REFERENCE_DIXIEME = "reference_dixieme_conges"
logger = logging.getLogger(__name__)


def lignes_pour_dixieme(donnees: Mapping[str, Any], *, importe: bool = False) -> list[dict]:
    """Les deux blocs, codés par l'inventaire stable pour un bulletin Martine."""
    from app.modules.payroll.engine.codes_des_lignes import code_de_ligne_de_gain

    lignes = []
    for bloc in ("calcul_du_brut", "details_absences"):
        lignes_codees = []
        for ligne in donnees.get(bloc) or []:
            if isinstance(ligne, Mapping):
                code = str(ligne.get("code_dixieme") or ligne.get("code") or "")
                if not code.startswith("brut:"):
                    code = code_de_ligne_de_gain(ligne) or ""
                lignes_codees.append((ligne, code))
        nombre_hs = sum(code.startswith("brut:reduction_hs_absence") for _, code in lignes_codees)
        nombre_absences = sum(bool(ligne.get("perte")) and est_libelle_absence(ligne.get("libelle")) for ligne, _ in lignes_codees)
        affectation_individuelle = nombre_hs == nombre_absences
        part_de_la_ligne_precedente = None
        for ligne, code in lignes_codees:
            copie = dict(ligne)
            famille = code.split(":")[1] if code.startswith("brut:") else ""
            if not importe:
                copie["code_dixieme"] = code or None
                if famille in {"retenue_absence_integrale", "retenue_absence_mois_complet", "complement_absence_integrale", "reduction_hs_absence"}:
                    # Dans calcul_brut, les CP sont retenus ensuite, avec
                    # leurs propres HS. Cette retenue concerne les autres absences.
                    copie["dixieme_hors_conges_payes"] = True
            elif famille == "reduction_hs_absence" and affectation_individuelle and part_de_la_ligne_precedente is not None:
                # Le bulletin repris détaille chaque retenue puis sa ligne
                # d'HS immédiatement suivante (PDF vérifiés). Aucune affectation
                # à distance, ni déduction de nature depuis le seul montant.
                copie["dixieme_part_reconstituee"] = part_de_la_ligne_precedente
            texte = texte_normalise(ligne.get("libelle"))
            if ligne.get("perte") and est_libelle_absence(texte):
                part_de_la_ligne_precedente = part_reconstituee(texte)
            else:
                part_de_la_ligne_precedente = None
            lignes.append(copie)
    return lignes


def lire_bulletins_reference(
    client: Any, employee_id: str, debut: date, fin: date, *, contract_period_id: str | None = None,
) -> list[dict]:
    if fin < debut:
        return []
    resultat = []
    decalage = 0
    while True:
        requete = (client.table("payslips").select("year, month, origine, payslip_data")
                   .eq("employee_id", employee_id).gte("year", debut.year).lte("year", fin.year))
        requete = requete.eq("contract_period_id", contract_period_id) if contract_period_id else requete.is_("contract_period_id", "null")
        lot = requete.order("id").range(decalage, decalage + 499).execute().data or []
        for ligne in lot:
            cle = (int(ligne["year"]), int(ligne["month"]))
            if not (debut.year, debut.month) <= cle <= (fin.year, fin.month):
                continue
            data = ligne.get("payslip_data") or {}
            resultat.append({"annee": cle[0], "mois": cle[1], "brut": data.get("salaire_brut"),
                             "importe": ligne.get("origine") == "importe",
                             "lignes": lignes_pour_dixieme(data, importe=ligne.get("origine") == "importe")})
        if len(lot) < 500:
            return resultat
        decalage += 500


def _imbrique(cumuls: dict | None) -> dict:
    return (cumuls.get("cumuls", cumuls) or {}) if isinstance(cumuls, dict) else {}


def base_de_reference(
    client: Any, employee_id: str, debut: date, fin: date, *,
    cumuls: dict | None = None, lire_cumul: bool = True,
    entree: date | None = None, contract_period_id: str | None = None,
) -> BaseDixieme:
    debut_effectif = max(debut, entree) if entree else debut
    if fin < debut_effectif:
        return BaseDixieme(0.0)
    bulletins = lire_bulletins_reference(client, employee_id, debut_effectif, fin, contract_period_id=contract_period_id)
    dernier_repris = any(b["importe"] and (b["annee"], b["mois"]) == (fin.year, fin.month) for b in bulletins)
    if lire_cumul and cumuls is None and not contract_period_id and not dernier_repris:
        lignes = (client.table("employee_schedules").select("cumuls").eq("employee_id", employee_id)
                  .eq("year", fin.year).eq("month", fin.month).execute().data or [])
        cumuls = lignes[0].get("cumuls") if lignes else None
    c = _imbrique(cumuls)
    brut = None
    debut_cumul = str(c.get("brut_reference_period_start") or "")[:10]
    fin_cumul = str(c.get("brut_reference_period_end") or "")[:10]
    periode_identifiee = debut_cumul == debut.isoformat() or (
        not debut_cumul and fin_cumul == fin.isoformat()
    )
    if not contract_period_id and not dernier_repris and periode_identifiee:
        valeur = c.get("brut_reference_n_1")
        if isinstance(valeur, (int, float)):
            brut = float(valeur)
    return calculer_base_periode(bulletins, debut=debut_effectif, fin=fin, brut_repris=brut)


def _jour(valeur: Any) -> date | None:
    try:
        return date.fromisoformat(str(valeur or "")[:10])
    except ValueError:
        return None


def preparer_cumuls_dixieme(
    client: Any, employee_data: dict, company_id: str, year: int, month: int, cumuls: dict,
    *, contract_period_id: str | None = None,
) -> dict:
    """Une photographie séparée des cumuls déclarés, sans modifier l'entrée.

    Les bases passent dans le JSON des cumuls déjà intercepté par le bac à
    sable. Cette photographie de lecture est retirée des cumuls produits.
    """
    sortie = copy.deepcopy(cumuls)
    try:
        from app.modules.absences.application.queries import (
            get_absence_balances_for_payslip,
        )
        from app.modules.absences.infrastructure.leave_settings_repository import (
            get_leave_policy,
        )

        policy = get_leave_policy(company_id)
        mois_debut = int(policy.cp_reference_period_start_month or 6)
        annee = year if month >= mois_debut else year - 1
        debut_n = date(annee, mois_debut, 1)
        debut_n1 = date(annee - 1, mois_debut, 1)
        avant = date(year, month, 1) - timedelta(days=1)
        entree = _jour(employee_data.get("hire_date"))
        eid = str(employee_data["id"])
        # Acquis au mois de paie, prises arrêtées AVANT le mois : le stock
        # disponible n'a pas encore consommé le congé à indemniser.
        compteurs = get_absence_balances_for_payslip(eid, year, month, date_fin_prises=avant) or {}
        precedent = base_de_reference(client, eid, debut_n1, debut_n - timedelta(days=1), entree=entree, contract_period_id=contract_period_id)
        courant = base_de_reference(client, eid, debut_n, avant, cumuls=cumuls, lire_cumul=False, entree=entree, contract_period_id=contract_period_id)
        unite = getattr(policy, "cp_counting_unit", "ouvrable")
        reference = {"coefficient_jours_evenements": 1.0 if unite == "ouvre" else 1.2,
                     "periode_precedente": {**asdict(precedent), "debut": debut_n1.isoformat()},
                     "periode_en_cours": {**asdict(courant), "debut": debut_n.isoformat()},
                     "alertes": []}
        if entree and any(mot in str(employee_data.get("contract_type") or "").lower() for mot in ("cdd", "interim", "intérim")):
            reference["contrat"] = asdict(base_de_reference(
                client, eid, entree, avant, entree=entree, lire_cumul=False,
                contract_period_id=contract_period_id,
            ))
        for cle, compteur in (("periode_precedente", "conges_payes_periode_precedente"), ("periode_en_cours", "conges_payes")):
            p = compteurs.get(compteur) or {}
            reference[cle]["droits"] = max(0.0, float(p.get("acquis") or 0.0))
            reference[cle]["restants"] = max(0.0, float(p.get("solde") or 0.0))
        # La période en cours n'est pas encore clôturée : ne pas comparer ses
        # seuls salaires passés à des droits incluant le mois encore impayé.
        reference["periode_en_cours"]["base_avant_mois"] = courant.base
        reference["periode_en_cours"]["base"] = None
        reference["periode_en_cours"]["alertes"] = ["Congés pris sur la période en cours : rémunération non clôturée, maintien seul à vérifier à la clôture."]
        sortie[CLE_REFERENCE_DIXIEME] = reference
    except Exception as exc:  # noqa: BLE001 — maintien seul explicite, jamais de base inventée
        logger.warning("Référence du dixième indisponible : %s", exc)
        sortie[CLE_REFERENCE_DIXIEME] = {"alertes": ["Rémunération de la période d'acquisition inconnue : maintien seul, vérifier le dixième."], "contrat": {"base": None}}
    return sortie
