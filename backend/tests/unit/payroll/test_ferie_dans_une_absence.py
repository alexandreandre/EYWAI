"""Un férié compris dans un arrêt ou un congé sans solde suit l'absence.

Il n'est pas payé comme férié : il est retenu avec l'absence, et seul le
maintien le couvre, s'il est indemnisé. Sources :
- convention de la plasturgie, avenant Collaborateurs, art. 11 (Légifrance
  KALITEXT000005682080) : l'indemnité est due au collaborateur « subissant une
  perte de salaire du fait du chômage d'un jour férié légal » ; pendant un
  arrêt, la perte vient de l'arrêt. Le maintien (avenant du 15/05/1991 art. 13,
  accord cadres art. 5 c) se calcule sur la rémunération qu'il « aurait perçue
  s'il avait normalement travaillé pendant la période indemnisée », en jours
  calendaires ;
- C. trav. D1226-1 (« la rémunération brute que le salarié aurait perçue s'il
  avait continué à travailler ») ; suspension du contrat : Cass. soc.
  24/06/1998 n° 96-44.234 et 14/04/1999 n° 97-42.064 (« peu important
  qu'elle comprenne un ou plusieurs jours fériés ») ; arrêt maladie : CA Douai
  30/05/2025 n° 24/00480 (« l'indemnité n'est due que si le salarié bénéficie
  du maintien de salaire »).

Comitech, S.G., arrêt du 05/05 au 20/05/2026 (8 et 14 mai fériés), mois avec
des jours travaillés : la retenue comptait 10 journées (1 029,91), le maintien
12 (1 235,91). Les deux fériés étaient payés deux fois.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.calcul_brut_forfait import calculer_salaire_brut_forfait

from .helpers import build_test_contexte
from .test_absence_mois_ferie import FERIES_MAI, MAI, _ctx, _jours, _libelles, _pertes

pytestmark = pytest.mark.unit

BORNES = "date_debut_arret_reel", "date_fin_arret_reel"


def _mois(arret=None, sans_solde=None, injustifiee=(), forfait=False) -> list[dict]:
    """Mai 2026 : les fériés, une absence, et des jours travaillés ailleurs."""
    heures_jour = 1.0 if forfait else 7.8
    travail = "travail_base" if forfait else "travail"
    cal = []
    for jour in _jours(MAI):
        iso = jour.isoformat()
        dans_arret = arret is not None and arret[0] <= jour <= arret[1]
        dans_sans_solde = sans_solde is not None and sans_solde[0] <= jour <= sans_solde[1]
        if jour in FERIES_MAI:
            ev = {"date_complete": iso, "type": "ferie", "heures": 0.0}
            if dans_arret:
                ev.update({"arret_type": "maladie_simple", BORNES[0]: arret[0].isoformat(),
                           BORNES[1]: arret[1].isoformat()})
            if dans_sans_solde:
                ev["source_absence"] = "sans_solde"
            cal.append(ev)
        elif jour.weekday() >= 5:
            continue
        elif dans_arret:
            cal.append({"date_complete": iso, "type": "arret_maladie", "heures": 0,
                        "arret_type": "maladie_simple", BORNES[0]: arret[0].isoformat(),
                        BORNES[1]: arret[1].isoformat()})
        elif dans_sans_solde:
            cal.append({"date_complete": iso, "type": "absence_non_remuneree", "heures": 0})
        elif jour in injustifiee:
            cal.append({"date_complete": iso, "type": "absence_injustifiee", "heures": 0})
        else:
            cal.append({"date_complete": iso, "type": travail, "heures": heures_jour})
    return cal


def _brut(cal):
    return calculer_salaire_brut(_ctx(), cal, *MAI, nb_jours_travail_planifies=10)


# --- Moteur des heures, mois avec des jours travaillés ------------------------


def test_les_feries_d_un_arret_sont_retenus_avec_lui_comme_le_maintien_les_compte():
    result = _brut(_mois(arret=(date(2026, 5, 5), date(2026, 5, 20))))
    # 12 journées du 05 au 20/05, fériés compris : 84 h à 12,8740 et 9,60 h
    # structurelles à 16,0925, la valeur que le maintien leur donne (1 235,91).
    assert _pertes(result, "Absence arrêt maladie") == 1081.42
    assert _pertes(result, "Réduction HS structurelles") == 154.49
    assert "Absence arrêt maladie du 05/05 au 20/05" in _libelles(result)


def test_un_ferie_hors_de_l_arret_reste_paye():
    # Arrêt du 11 au 13/05 : le jeudi 14 mai est après l'arrêt.
    result = _brut(_mois(arret=(date(2026, 5, 11), date(2026, 5, 13))))
    assert _pertes(result, "Absence arrêt maladie") == round(3 * 7 * 12.8740, 2)


def test_les_feries_d_un_conge_sans_solde_sont_retenus_avec_lui():
    # Sans solde du 01/05 au 15/05 : 1er, 8 et 14 mai compris, 11 journées.
    result = _brut(_mois(sans_solde=(date(2026, 5, 1), date(2026, 5, 15))))
    assert _pertes(result, "Absence non rémunérée") == round(11 * 90.12, 2)


def test_un_ferie_entre_deux_absences_injustifiees_reste_paye():
    # L3133-3 ne pose plus qu'une condition d'ancienneté : le 8 mai, entre deux
    # absences injustifiées, reste payé.
    result = _brut(_mois(injustifiee=(date(2026, 5, 7), date(2026, 5, 11))))
    assert not any("08/05" in l for l in _libelles(result))


# --- Forfait jours ------------------------------------------------------------


def _forfait():
    return build_test_contexte(
        statut="Cadre", salaire_base=3608.0, specificites_extra={"is_forfait_jour": True}
    )


def test_forfait_mois_sans_travail_les_feries_de_l_arret_sont_retenus_comme_aux_heures():
    # Arrêt du 04/05 au 31/05, le 1er mai hors de l'arrêt : 20 journées retenues
    # (fériés de l'arrêt compris), le 1er mai payé. Avant : 17, et 777,50 €.
    from .test_absence_mois_ferie import _arret

    cal = _arret(date(2026, 5, 4), date(2026, 5, 31), MAI, FERIES_MAI)
    result = calculer_salaire_brut_forfait(_forfait(), cal, *MAI, [])
    assert sum(1 for l in _libelles(result) if l.startswith("Absence maladie")) == 20
    assert result["salaire_brut_total"] == round(3608.0 - 20 * 166.50, 2)


def test_forfait_mois_travaille_les_feries_d_un_arret_sont_retenus():
    cal = _mois(arret=(date(2026, 5, 5), date(2026, 5, 20)), forfait=True)
    result = calculer_salaire_brut_forfait(_forfait(), cal, *MAI, [])
    assert sum(1 for l in _libelles(result) if l.startswith("Absence maladie")) == 12


def test_forfait_les_feries_d_un_conge_sans_solde_sont_retenus():
    cal = _mois(sans_solde=(date(2026, 5, 1), date(2026, 5, 15)), forfait=True)
    result = calculer_salaire_brut_forfait(_forfait(), cal, *MAI, [])
    assert sum(1 for l in _libelles(result) if l.startswith("Absence non rémunérée")) == 11
