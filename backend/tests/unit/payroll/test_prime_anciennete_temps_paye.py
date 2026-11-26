"""Prime d'ancienneté de la métallurgie : elle suit le temps payé du mois, aux deux générateurs.

CCN de la métallurgie du 7 février 2022, art. 142 : « Le montant de la prime d'ancienneté varie
avec l'horaire de travail. Il supporte donc, le cas échéant, les majorations pour heures
supplémentaires ou au titre des conventions de forfait en jours ». Enquête du 26/11/2026 : au
générateur des heures, le prorata valait toujours 1 sauf arrêt (les pointages étaient lus sous une
clé absente) ; au forfait jours, les congés, RTT, formation et activité partielle comptaient comme
des absences (5 CP sur 19 jours : 0,7368).

Règle : ratio = 1 − temps non payé ÷ référence, plus les heures sup × (1 + majoration) ÷ référence
au générateur des heures. Seuls font baisser la prime : absence injustifiée, non rémunérée ou sans
solde, heures chômées d'activité partielle, arrêt non maintenu, jours hors contrat. Congés payés
(L. 3141-24 II), fériés chômés (L. 3133-3), arrêt maintenu (art. 91.1.2) et mois court (L. 3242-1)
restent payés.

Chaque cas passe par le vrai calcul du brut (`calculer_salaire_brut`, `calculer_salaire_brut_forfait`)
et lit la ligne de prime qu'il pose. Salariés fictifs : classe 8 (2,9 %), point des Deux-Sèvres 2026
(5,80 €), 5 ans d'ancienneté : 84,10 € par mois aux heures, 109,33 € au forfait (majoration de 30 %).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.calcul_brut_forfait import calculer_salaire_brut_forfait
from app.modules.payroll.engine.contexte import ChargerContexte
from tests.unit.payroll.test_prime_anciennete_metallurgie import _metallurgie_baremes

pytestmark = pytest.mark.unit

PLEIN_HEURES = 84.10
PLEIN_FORFAIT = 109.33
NOVEMBRE = (date(2026, 11, 1), date(2026, 11, 30))
#: Période de société au forfait : 20 jours du lundi au vendredi, dont le 11/11 férié : 19 jours.
PERIODE_19_JOURS = (date(2026, 11, 2), date(2026, 11, 27))
LIBELLE_AP = "Heures chômées (act. part.)"


def _contexte(
    *,
    forfait: bool = False,
    date_sortie: str | None = None,
    duree: float = 35,
    classe: int = 8,
    date_entree: str = "2021-06-14",
    jours_forfait: float | None = None,
):
    employee = {
        "date_entree": date_entree,
        "statut": "Non-cadre",
        "duree_hebdomadaire": duree,
        "salaire_base": 2400.0,
        "is_forfait_jour": forfait,
        "type_contrat": "CDI",
        "convention_collective": {"idcc": "3248", "libelle": "Métallurgie"},
        "classification_conventionnelle": {"classe_emploi": classe, "coefficient": classe},
    }
    company = {
        "adresse_code_postal": "79140",
        "identification": {"adresse": {"code_postal": "79140"}},
        "parametres_paie": {"effectif": 70},
    }
    ctx = ChargerContexte(employee, company, _metallurgie_baremes())
    ctx.year = 2026
    if date_sortie:
        ctx.contrat["contrat"]["date_sortie"] = date_sortie
    if jours_forfait is not None:
        ctx.contrat.setdefault("specificites_paie", {})["forfait_annual_days"] = jours_forfait
    return ctx


def _jours(debut: date, fin: date) -> list[date]:
    return [debut + timedelta(days=k) for k in range((fin - debut).days + 1)]


def _calendrier_heures(debut: date, fin: date, autres: dict[int, dict] | None = None) -> list[dict]:
    """Un mois pointé : 7 h par jour du lundi au vendredi, sauf les jours donnés."""
    autres = autres or {}
    cal = []
    for jour in _jours(debut, fin):
        if jour.day in autres:
            cal.append({"date_complete": jour.isoformat(), **autres[jour.day]})
        elif jour.weekday() < 5:
            cal.append({"date_complete": jour.isoformat(), "type": "travail_base", "heures": 7.0})
    return cal


def _calendrier_forfait(debut: date, fin: date, autres: dict[int, dict] | None = None) -> list[dict]:
    autres = autres or {}
    cal = []
    for jour in _jours(debut, fin):
        if jour.day in autres:
            cal.append({"date_complete": jour.isoformat(), **autres[jour.day]})
        elif jour.weekday() < 5:
            cal.append({"date_complete": jour.isoformat(), "type": "travail_base", "heures": 1.0})
        else:
            cal.append({"date_complete": jour.isoformat(), "type": "weekend", "heures": 0.0})
    return cal


def _prime(resultat: dict) -> float | None:
    for ligne in resultat["lignes_composants_brut"]:
        if "anciennet" in str(ligne.get("libelle") or "").lower():
            return ligne.get("gain")
    return None


def _heures(cal, *, periode=NOVEMBRE, primes=None, jours_maintien=None, ctx=None):
    return _prime(
        calculer_salaire_brut(
            ctx or _contexte(), cal, *periode, primes or [], jours_maintien=jours_maintien or set()
        )
    )


def _forfait(cal, *, periode=PERIODE_19_JOURS, primes=None, jours_maintien=None, ctx=None):
    return _prime(
        calculer_salaire_brut_forfait(
            ctx or _contexte(forfait=True), cal, *periode, primes or [],
            jours_maintien=jours_maintien or set(),
        )
    )


CP = {"type": "conges_payes", "heures": 0.0}
FERIE = {"type": "ferie", "heures": 0.0}
ARRET = {"type": "arret_maladie", "heures": 0.0}


# 1) Cinq jours de congés payés : la prime reste pleine.
def test_heures_cinq_conges_payes_prime_pleine():
    cal = _calendrier_heures(*NOVEMBRE, {d: CP for d in (16, 17, 18, 19, 20)})
    assert _heures(cal) == PLEIN_HEURES


def test_forfait_cinq_conges_payes_sur_19_jours_prime_pleine():
    """Le cas du 26/11 : 14 jours travaillés et 5 CP sur 19 donnaient 0,7368."""
    cal = _calendrier_forfait(*PERIODE_19_JOURS, {11: FERIE, **{d: CP for d in (16, 17, 18, 19, 20)}})
    assert _forfait(cal) == PLEIN_FORFAIT


# 2) Férié chômé : payé (L. 3133-3), la prime reste pleine.
def test_heures_ferie_chome_prime_pleine():
    assert _heures(_calendrier_heures(*NOVEMBRE, {11: FERIE})) == PLEIN_HEURES


def test_forfait_ferie_chome_prime_pleine():
    assert _forfait(_calendrier_forfait(*PERIODE_19_JOURS, {11: FERIE})) == PLEIN_FORFAIT


# 3) Mois de 20 jours ouvrés, pointé ou sans pointage : la prime ne dépend pas des pointages.
FEVRIER = (date(2026, 2, 1), date(2026, 2, 28))
#: Février 2026 : 4 ans d'ancienneté, point de 5,70 € (celui de 5,80 € vaut depuis le 06/03/2026).
PLEIN_FEVRIER_HEURES = round(5.70 * 2.9 * 4, 2)
PLEIN_FEVRIER_FORFAIT = round(PLEIN_FEVRIER_HEURES * 1.3, 2)


def test_heures_mois_de_20_jours_pointe_prime_pleine():
    assert _heures(_calendrier_heures(*FEVRIER), periode=FEVRIER) == PLEIN_FEVRIER_HEURES == 66.12


def test_heures_mois_de_20_jours_sans_pointage_prime_pleine():
    assert _heures([], periode=FEVRIER) == PLEIN_FEVRIER_HEURES


def test_forfait_mois_de_20_jours_prime_pleine():
    assert _forfait(_calendrier_forfait(*FEVRIER), periode=FEVRIER) == PLEIN_FEVRIER_FORFAIT == 85.96


# 4) 28 h d'activité partielle saisies : (151,67 − 28) ÷ 151,67.
def test_heures_activite_partielle_saisie():
    primes = [{"prime_id": "heures_chomees", "libelle": LIBELLE_AP, "montant": -400.0, "quantite": 28.0}]
    attendu = round(PLEIN_HEURES * round((151.67 - 28) / 151.67, 6), 2)
    assert _heures(_calendrier_heures(*NOVEMBRE), primes=primes) == attendu == 68.57


# 5) 22,92 h d'absence injustifiée : ratio 0,8489.
def test_heures_absence_injustifiee():
    # Trois journées de 7 h et une de 1,92 h retenues.
    absences = {d: {"type": "absence_injustifiee_base", "heures": 7.0} for d in (2, 3, 4)}
    absences[5] = {"type": "absence_injustifiee_base", "heures": 1.92}
    ratio = round((151.67 - 22.92) / 151.67, 6)
    assert round(ratio, 4) == 0.8489
    assert _heures(_calendrier_heures(*NOVEMBRE, absences)) == round(PLEIN_HEURES * ratio, 2)


def test_heures_absence_non_remuneree_sans_solde():
    cal = _calendrier_heures(*NOVEMBRE, {d: {"type": "absence_non_remuneree", "heures": 7.0} for d in (2, 3)})
    assert _heures(cal) == round(PLEIN_HEURES * round((151.67 - 14) / 151.67, 6), 2)


# 6) 5,25 h d'heures sup à 25 % : prime × (1 + 5,25 × 1,25 ÷ 151,67).
def test_heures_heures_sup_majorees():
    cal = _calendrier_heures(*NOVEMBRE, {6: {"type": "travail_hs25", "heures": 5.25}})
    # Le vendredi 6 porte ses 5,25 h sup ; sa base reste payée (mensualisation).
    attendu = round(PLEIN_HEURES * round(1 + 5.25 * 1.25 / 151.67, 6), 2)
    assert _heures(cal) == attendu == 87.74


# 7) Arrêt maintenu, puis non maintenu.
def test_heures_arret_maintenu_prime_pleine():
    cal = _calendrier_heures(*NOVEMBRE, {d: ARRET for d in (16, 17, 18)})
    assert _heures(cal, jours_maintien={16, 17, 18}) == PLEIN_HEURES


def test_heures_arret_en_partie_non_maintenu():
    """Trois jours d'arrêt, le premier en carence : 7 h retirées."""
    cal = _calendrier_heures(*NOVEMBRE, {d: ARRET for d in (16, 17, 18)})
    assert _heures(cal, jours_maintien={17, 18}) == round(PLEIN_HEURES * round(144.67 / 151.67, 6), 2)


def test_forfait_arret_maintenu_puis_non_maintenu():
    cal = _calendrier_forfait(*PERIODE_19_JOURS, {11: FERIE, **{d: ARRET for d in (16, 17, 18)}})
    assert _forfait(cal, jours_maintien={16, 17, 18}) == PLEIN_FORFAIT
    assert _forfait(cal, jours_maintien={17, 18}) == round(PLEIN_FORFAIT * round(18 / 19, 6), 2)


# 8) Mois de sortie : la prime suit les jours sous contrat, dans la même proportion que le salaire.
def test_heures_mois_de_sortie():
    """Sortie le vendredi 13/11 : 10 jours ouvrés sous contrat sur 21."""
    ctx = _contexte(date_sortie="2026-11-13")
    cal = _calendrier_heures(date(2026, 11, 1), date(2026, 11, 13), {11: FERIE})
    attendu = round(PLEIN_HEURES * round(10 / 21, 6), 2)
    assert _heures(cal, ctx=ctx) == attendu == 40.05


def test_forfait_mois_de_sortie_suit_le_salaire():
    """Sortie le vendredi 13/11, mois civil : le salaire du forfait paie 10 jours ouvrés sur 21
    (fériés compris des deux côtés) ; la prime aussi, comme aux heures, et non 9 sur 20."""
    ctx = _contexte(forfait=True, date_sortie="2026-11-13")
    cal = _calendrier_forfait(date(2026, 11, 1), date(2026, 11, 30), {11: FERIE})
    resultat = calculer_salaire_brut_forfait(ctx, cal, *NOVEMBRE, [], jours_maintien=set())
    retenue = next(l for l in resultat["lignes_composants_brut"] if l.get("is_entree_sortie"))
    assert retenue["quantite"] == 11.0  # 11 jours ouvrés sur 21 retirés du salaire
    assert _prime(resultat) == round(PLEIN_FORFAIT * round(10 / 21, 6), 2) == 52.06


# 9) Forfait : 2 jours d'activité partielle sur 19 → 17/19.
def test_forfait_deux_jours_d_activite_partielle():
    # Les jours chômés sortent du calendrier du forfait (`analyser_jours_forfait`) ; les heures
    # chômées arrivent par la saisie, 7 h par journée.
    cal = [
        j for j in _calendrier_forfait(*PERIODE_19_JOURS, {11: FERIE})
        if j["date_complete"] not in ("2026-11-23", "2026-11-24")
    ]
    primes = [{"prime_id": "heures_chomees", "libelle": LIBELLE_AP, "montant": -300.0, "quantite": 14.0}]
    assert _forfait(cal, primes=primes) == round(PLEIN_FORFAIT * round(17 / 19, 6), 2)


def test_forfait_rtt_formation_ecole_restent_payes():
    cal = _calendrier_forfait(
        *PERIODE_19_JOURS,
        {11: FERIE, 16: {"type": "rtt", "heures": 0.0}, 17: {"type": "formation", "heures": 0.0},
         18: {"type": "ecole", "heures": 0.0}},
    )
    assert _forfait(cal) == PLEIN_FORFAIT


def test_forfait_absence_injustifiee_un_jour():
    cal = _calendrier_forfait(*PERIODE_19_JOURS, {11: FERIE, 16: {"type": "absence_injustifiee_base", "heures": 1.0}})
    assert _forfait(cal) == round(PLEIN_FORFAIT * round(18 / 19, 6), 2)


# Férié compris dans un arrêt non maintenu : retenu avec l'arrêt, au salaire comme à la prime.
def test_heures_ferie_dans_un_arret_non_maintenu():
    """Arrêt du lundi 9 au vendredi 13/11, le 11 férié, rien de maintenu : 5 × 7 h."""
    cal = _calendrier_heures(*NOVEMBRE, {**{d: ARRET for d in (9, 10, 12, 13)}, 11: FERIE})
    assert _heures(cal, jours_maintien=set()) == round(PLEIN_HEURES * round((151.67 - 35) / 151.67, 6), 2)


def test_forfait_ferie_dans_un_arret_non_maintenu():
    """Même arrêt au forfait : le salaire retient 5 journées, la prime aussi (14/19, pas 15/19)."""
    cal = _calendrier_forfait(*PERIODE_19_JOURS, {**{d: ARRET for d in (9, 10, 12, 13)}, 11: FERIE})
    resultat = calculer_salaire_brut_forfait(_contexte(forfait=True), cal, *PERIODE_19_JOURS, [], jours_maintien=set())
    retenus = [l for l in resultat["lignes_composants_brut"] if str(l.get("libelle")).startswith("Absence maladie")]
    assert len(retenus) == 5
    assert _prime(resultat) == round(PLEIN_FORFAIT * round(14 / 19, 6), 2)


# Temps partiel et forfait réduit : la prime suit la durée du contrat rapportée à la durée pleine.
def test_heures_temps_partiel_28_h_comme_le_cabinet():
    """28 h, classe 4, 11 ans, point de 5,70 € (février 2026) : le cabinet a versé
    5,70 × 1,95 % × 100 × 11 × 0,8 = 97,81 € ; la durée du contrat seule donnait 122,27 €.
    Martine arrondit le plein mois avant le prorata (122,27 × 0,8 = 97,82) : un centime d'écart,
    connu, hors de ce lot."""
    ctx = _contexte(duree=28, classe=4, date_entree="2015-01-05")
    assert _heures(_calendrier_heures(*FEVRIER), periode=FEVRIER, ctx=ctx) == round(122.27 * 0.8, 2) == 97.82


def test_heures_temps_partiel_avec_une_absence():
    """28 h : une journée d'absence injustifiée de 5,6 h sur les 121,33 h du contrat."""
    ctx = _contexte(duree=28)
    cal = _calendrier_heures(*NOVEMBRE, {16: {"type": "absence_injustifiee_base", "heures": 5.6}})
    attendu = round(PLEIN_HEURES * round(0.8 * (121.33 - 5.6) / 121.33, 6), 2)
    assert _heures(cal, ctx=ctx) == attendu


def test_heures_au_dela_de_35_h_prime_pleine_sans_majorer_les_heures_structurelles():
    """37,5 h, classe 6, 3 ans, février 2026 : le cabinet verse 5,70 × 2,45 % × 100 × 3 = 41,90 €.
    Question ouverte : l'art. 142 dit que la prime « supporte » les majorations d'heures sup."""
    # Martine : 41,89 (5,70 × 2,45 × 3 = 41,895, arrondi du plein mois en flottant) ; un centime
    # d'écart avec le cabinet, connu, hors de ce lot. La prime n'est pas majorée par les 2,5 h.
    ctx = _contexte(duree=37.5, classe=6, date_entree="2022-06-13")
    assert _heures(_calendrier_heures(*FEVRIER), periode=FEVRIER, ctx=ctx) == 41.89


def test_heures_au_dela_de_35_h_les_heures_sup_du_mois_se_rapportent_a_151_67():
    ctx = _contexte(duree=37.5, classe=6, date_entree="2022-06-13")
    cal = _calendrier_heures(*FEVRIER, {6: {"type": "travail_hs25", "heures": 6.93}})
    assert _heures(cal, periode=FEVRIER, ctx=ctx) == round(41.89 * round(1 + 6.93 * 1.25 / 151.67, 6), 2)


def test_forfait_reduit_au_prorata_de_ses_jours():
    """Forfait de 109 jours : la moitié de 218, la moitié de la prime."""
    ctx = _contexte(forfait=True, jours_forfait=109)
    assert _forfait(_calendrier_forfait(*PERIODE_19_JOURS, {11: FERIE}), ctx=ctx) == round(PLEIN_FORFAIT * 0.5, 2)


def test_forfait_plein_sur_la_fiche_prime_pleine():
    ctx = _contexte(forfait=True, jours_forfait=218)
    assert _forfait(_calendrier_forfait(*PERIODE_19_JOURS, {11: FERIE}), ctx=ctx) == PLEIN_FORFAIT
