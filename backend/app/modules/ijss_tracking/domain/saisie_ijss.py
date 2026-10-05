"""La saisie du mois qui porte le montant d'IJSS validé au suivi IJSS.

« Appliquer au bulletin » l'écrit ; le générateur la relit à chaque calcul
comme montant des IJSS subrogées du mois. Elle n'est ni une prime, ni la
saisie « IJSS override », qui bascule aussi le maintien en jours ouvrés.
Le libellé ne commence pas par « IJSS » : l'OD ne la prend pas pour une
somme à reverser.
"""

from __future__ import annotations

from typing import Any, Mapping

LIBELLE_IJSS_VALIDEES = "Montant validé des IJSS (suivi IJSS)"


def est_saisie_ijss_validees(saisie: Mapping[str, Any]) -> bool:
    return str(saisie.get("name") or "") == LIBELLE_IJSS_VALIDEES
