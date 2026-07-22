"""Reconstruction de bulletins d'option participation depuis des saisies existantes.

Fonction pure : classe les `monthly_inputs` déjà en base (issues d'un backtest
ou d'une saisie antérieure au module participation) et reconstitue, par
salarié, le bulletin d'option qu'aurait produit le workflow normal
(create_campaign → réponse salarié), sans jamais modifier les saisies.

Voir docs/superpowers/specs/2026-07-22-import-participations-saisies-existantes-design.md
pour la dérivation complète de la formule (en particulier : le montant d'une
ligne PEE est déjà un brut, pas un net à regonfler — vérifié sur le moteur
réel et sur le cas GIRERD/MBC).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List

from app.modules.participation.domain.bulletin_rules import (
    CSG_DEDUCTIBLE_RATE,
    CSG_NON_DEDUCTIBLE_RATE,
    compute_participation_csg,
)

# Facteur net-de-CSG : ce que le salarié perçoit réellement (numéraire) ou ce
# qui est effectivement placé (PEE) une fois la CSG/CRDS 9,7 % déduite à la
# source du montant brut de la saisie.
_NET_FACTOR = Decimal("1") - CSG_DEDUCTIBLE_RATE - CSG_NON_DEDUCTIBLE_RATE


def _round2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ReconstructedBulletin:
    """Bulletin d'option reconstitué pour un salarié à partir de ses saisies."""

    employee_id: str
    dispositif_type: str
    gross_amount: Decimal
    csg_non_deductible: Decimal
    csg_deductible: Decimal
    advance_amount: Decimal
    advance_label: str
    net_amount: Decimal
    choice_type: str
    cash_amount: Decimal
    pee_amount: Decimal
    source_input_ids: List[str] = field(default_factory=list)


def _classify_input(row: Dict[str, Any]) -> str:
    """Retourne 'numeraire' | 'pee' | 'avance' | 'exclu' selon le libellé et le montant.

    Ordre de détection important : les remboursements de frais/notes de frais
    sont exclus en premier (même si leur libellé contient « participation »),
    puis le PEE, puis l'avance/acompte (dont le libellé contient aussi
    « participation »), puis la ligne numéraire générique.
    """
    name = str(row.get("name") or "").lower()
    amount = float(row.get("amount") or 0)

    if "note de frais" in name or "remboursement" in name:
        return "exclu"
    if "pee" in name or "épargne" in name or "epargne" in name:
        return "pee" if amount > 0 else "exclu"
    if "avance" in name or "acompte" in name:
        return "avance" if amount < 0 else "exclu"
    if "participation" in name or "intéressement" in name or "interessement" in name:
        return "numeraire" if amount > 0 else "exclu"
    return "exclu"


def reconstruct_bulletins_from_inputs(
    monthly_inputs: List[Dict[str, Any]],
) -> List[ReconstructedBulletin]:
    """Reconstitue un bulletin d'option participation par salarié bénéficiaire.

    `monthly_inputs` : lignes brutes de la table `monthly_inputs` (au minimum
    `id`, `employee_id`, `name`, `amount`), pour une société et une période de
    paie données. Les lignes non liées à la participation (autres primes,
    frais, etc.) sont ignorées : cette fonction peut recevoir l'intégralité
    des saisies du mois sans pré-filtrage SQL.

    Un salarié sans ligne numéraire ni PEE positive (ex. avance orpheline) ne
    devient pas bénéficiaire.
    """
    grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(
        lambda: {"numeraire": [], "pee": [], "avance": []}
    )
    for row in monthly_inputs:
        kind = _classify_input(row)
        if kind == "exclu":
            continue
        employee_id = str(row.get("employee_id"))
        grouped[employee_id][kind].append(row)

    results: List[ReconstructedBulletin] = []
    for employee_id, buckets in grouped.items():
        numeraire_rows = buckets["numeraire"]
        pee_rows = buckets["pee"]
        avance_rows = buckets["avance"]
        if not numeraire_rows and not pee_rows:
            continue

        gross_numeraire = sum(
            (Decimal(str(r["amount"])) for r in numeraire_rows), Decimal("0")
        )
        gross_pee = sum((Decimal(str(r["amount"])) for r in pee_rows), Decimal("0"))
        advance_amount = sum(
            (abs(Decimal(str(r["amount"]))) for r in avance_rows), Decimal("0")
        )
        advance_label = str(avance_rows[0]["name"]) if avance_rows else ""

        gross = gross_numeraire + gross_pee
        csg_non_deductible, csg_deductible, _csg_total = compute_participation_csg(
            gross
        )

        cash_amount = _round2(gross_numeraire * _NET_FACTOR) - advance_amount
        pee_amount = _round2(gross_pee * _NET_FACTOR)
        net_amount = cash_amount + pee_amount

        if gross_pee == 0:
            choice_type = "full_cash"
        elif gross_numeraire == 0:
            choice_type = "full_pee"
        else:
            choice_type = "partial_cash"

        source_input_ids = [
            str(r["id"]) for r in (*numeraire_rows, *pee_rows, *avance_rows)
        ]

        results.append(
            ReconstructedBulletin(
                employee_id=employee_id,
                dispositif_type="participation",
                gross_amount=gross,
                csg_non_deductible=csg_non_deductible,
                csg_deductible=csg_deductible,
                advance_amount=advance_amount,
                advance_label=advance_label,
                net_amount=net_amount,
                choice_type=choice_type,
                cash_amount=cash_amount,
                pee_amount=pee_amount,
                source_input_ids=source_input_ids,
            )
        )
    return results
