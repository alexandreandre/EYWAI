"""État des bulletins lus par un export : brouillons et bulletins à recalculer.

Aucun export ne filtre sur le statut du bulletin : le journal, les écritures, le
virement, la DSN lisent les brouillons comme les bulletins validés. L'aperçu le
dit au lieu de laisser croire que seul le validé sort. Ce qui est exporté ne
change pas.
"""

from __future__ import annotations

from app.shared.domain.pluriel import accord, pluriel

#: Dit la vérité : l'export lit aussi les brouillons, il n'y a pas de filtre « validé ».
MESSAGE_AUCUN_BULLETIN = "Aucun bulletin de paie pour cette période"

#: Exports dont les montants viennent des bulletins du mois.
EXPORTS_LUS_SUR_BULLETINS = frozenset(
    {
        "journal_paie",
        "virement_salaires",
        "od_salaires",
        "od_charges_sociales",
        "od_pas",
        "od_globale",
        "export_cabinet_generique",
        "export_cabinet_quadra",
        "export_cabinet_sage",
        "dsn_mensuelle",
        "charges_sociales",
        "fec",
        "paiement_organismes",
        "recapitulatif_montants",
    }
)


def avertissements_etat_bulletins(
    non_valides: int, a_recalculer: int, non_verifies: int = 0
) -> list[str]:
    """Les phrases de l'aperçu ; rien quand tout est validé et à jour."""
    phrases: list[str] = []
    if non_valides:
        phrases.append(
            f"{pluriel(non_valides, 'bulletin')} {accord(non_valides, 'non validé')} : "
            "l'export reprend aussi les brouillons."
        )
    if a_recalculer:
        phrases.append(
            f"{pluriel(a_recalculer, 'bulletin')} à recalculer : leurs données ont changé "
            "depuis le calcul, l'export reprend le dernier calcul."
        )
    if non_verifies:
        phrases.append(
            f"L'état « à recalculer » de {pluriel(non_verifies, 'bulletin')} "
            "n'a pas pu être vérifié."
        )
    return phrases
