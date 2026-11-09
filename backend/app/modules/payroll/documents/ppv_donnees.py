"""Ce que le générateur lit pour ranger une prime de partage de la valeur.

Les règles sont dans `engine.ppv` ; ici, seulement les lectures :
- les PPV déjà versées dans l'année civile (variables des mois d'avant,
  reconnues par leur nature) : deux primes et 3 000 € par an au plus ;
- la rémunération moyenne des 12 mois précédant le versement (bulletins
  enregistrés) : la condition des 3 Smic ;
- l'accord d'intéressement de la société (`settings.ppv_accord_interessement`) :
  plafond porté à 6 000 €.

Rien n'est lu quand le mois n'a pas de PPV : les autres bulletins ne font pas
une lecture de plus.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from app.modules.monthly_inputs.domain.rules import est_saisie_retiree
from app.modules.payroll.engine.ppv import est_une_ppv

CLE_SAISIES = "ppv"
CLE_ACCORD_INTERESSEMENT = "ppv_accord_interessement"


def _est_une_ppv_saisie(row: Dict[str, Any]) -> bool:
    if row.get("sur_le_net") or est_saisie_retiree(row):
        return False
    return est_une_ppv(row.get("catalog_prime_id") or "", row.get("name"))


def _ppv_du_bulletin(bulletin: Dict[str, Any]) -> float:
    """Ce qu'un bulletin porte de PPV : montants et gains des lignes reconnues à leur nature."""
    total = 0.0
    for cle, champ in (
        ("primes_non_soumises", "montant"),
        ("revenus_hors_brut_imposables", "montant"),
        ("calcul_du_brut", "gain"),
    ):
        lignes = bulletin.get(cle)
        for ligne in lignes if isinstance(lignes, list) else []:
            if isinstance(ligne, dict) and est_une_ppv(ligne.get("prime_id"), ligne.get("libelle")):
                total += _montant(ligne.get(champ))
    return round(total, 2)


def _montant(valeur: Any) -> float:
    try:
        return float(valeur or 0.0)
    except (TypeError, ValueError):
        return 0.0


def donnees_ppv_du_mois(
    supabase: Any,
    employee_id: str,
    year: int,
    month: int,
    company_data: Optional[Dict[str, Any]],
    saisies_du_mois: Iterable[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Les données de `engine.ppv.classer_ppv`, ou None sans PPV dans le mois."""
    if not any(_est_une_ppv_saisie(row) for row in saisies_du_mois or []):
        return None

    variables = (
        supabase.table("monthly_inputs")
        .select("year, month, name, amount, catalog_prime_id, sur_le_net, description")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .lt("month", month)
        .execute()
        .data
        or []
    )
    saisies_ppv = [
        row
        for row in sorted(variables, key=lambda r: int(r.get("month") or 0))
        if _est_une_ppv_saisie(row) and _montant(row.get("amount")) > 0
    ]
    deja_versees: List[float] = [round(_montant(row.get("amount")), 2) for row in saisies_ppv]
    mois_saisis = {int(row.get("month") or 0) for row in saisies_ppv}

    rang = year * 12 + month
    bulletins = (
        supabase.table("payslips")
        .select(
            "year, month, salaire_brut:payslip_data->salaire_brut, "
            "primes_non_soumises:payslip_data->primes_non_soumises, "
            "revenus_hors_brut_imposables:payslip_data->revenus_hors_brut_imposables, "
            "calcul_du_brut:payslip_data->calcul_du_brut"
        )
        .eq("employee_id", employee_id)
        .in_("year", [year - 1, year])
        .execute()
        .data
        or []
    )
    bruts = [
        _montant(b.get("salaire_brut"))
        for b in bulletins
        if rang - 12 <= int(b.get("year") or 0) * 12 + int(b.get("month") or 0) < rang
    ]
    moyenne = round(sum(bruts) / len(bruts), 2) if bruts else None

    # Une PPV sur un bulletin sans variable du mois : bulletin repris d'un
    # logiciel antérieur (R-036, l'acompte de juillet de MAJI). Elle compte
    # comme une variable : deux primes et le plafond annuel. Par mois, une seule
    # prime, même en plusieurs lignes (part exonérée et part soumise).
    deja_par_mois: Dict[int, float] = {}
    for bulletin in bulletins:
        mois_bulletin = int(bulletin.get("month") or 0)
        if int(bulletin.get("year") or 0) != year or mois_bulletin >= month or mois_bulletin in mois_saisis:
            continue
        montant = _ppv_du_bulletin(bulletin)
        if montant > 0:
            deja_par_mois[mois_bulletin] = round(deja_par_mois.get(mois_bulletin, 0.0) + montant, 2)
    deja_versees.extend(deja_par_mois[mois] for mois in sorted(deja_par_mois))

    reglages = (company_data or {}).get("settings")
    accord = bool(
        isinstance(reglages, dict) and reglages.get(CLE_ACCORD_INTERESSEMENT)
    )
    return {
        "deja_versees": deja_versees,
        "remuneration_mensuelle_moyenne": moyenne,
        "mois_de_remuneration": len(bruts),
        "accord_interessement": accord,
    }
