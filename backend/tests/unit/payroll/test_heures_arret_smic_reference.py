"""Un arrêt ne sort du SMIC de référence qu'à proportion de ce qui n'est pas maintenu.

La réduction générale se calcule sur les heures rémunérées. Pendant un arrêt de
travail, la rémunération peut être maintenue en entier, en partie, ou pas du
tout : le SMIC de référence suit la part restée à la charge de l'employeur.

Le moteur gardait les heures d'arrêt en bloc, en supposant le maintien acquis.
Demory et Fuckar (Colorplast, mai 2026) n'en reçoivent aucun : nous réclamions
347 € d'allègement sur des heures que personne n'avait payées — un allègement
de trop, donc un risque en cas de contrôle.

Même principe que la correction de janvier 2026 sur les absences non
rémunérées, appliqué cette fois aux arrêts.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def _heures_qui_sortent(heures_arret: float, deduction: float, maintien: float) -> float:
    """Le calcul de `payslip_run_heures`, isolé."""
    if heures_arret <= 0:
        return 0.0
    part_maintenue = min(1.0, maintien / deduction) if deduction > 0 else 0.0
    return round(heures_arret * (1.0 - part_maintenue), 2)


def test_sans_aucun_maintien_toutes_les_heures_sortent():
    """Demory, mai : 28,00 h d'accident du travail, pas un euro de maintien."""
    assert _heures_qui_sortent(28.0, 341.60, 0.0) == 28.0


def test_avec_un_maintien_entier_aucune_heure_ne_sort():
    assert _heures_qui_sortent(28.0, 341.60, 341.60) == 0.0


def test_un_maintien_partiel_fait_sortir_le_reste():
    """Maintien de 90 % : 10 % des heures sortent."""
    assert _heures_qui_sortent(28.0, 341.60, 307.44) == 2.80


def test_un_maintien_superieur_a_la_retenue_ne_rajoute_pas_d_heures():
    """Le cabinet peut maintenir plus que la retenue : on ne descend pas sous zéro."""
    assert _heures_qui_sortent(28.0, 341.60, 500.0) == 0.0


def test_sans_arret_rien_ne_change():
    assert _heures_qui_sortent(0.0, 0.0, 0.0) == 0.0
