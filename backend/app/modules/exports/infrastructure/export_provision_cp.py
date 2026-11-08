# Export « État de provision des congés payés » — valorisation en euros de la dette de CP.
# Ce que chaque salarié toucherait s'il partait à la fin du mois demandé : la règle légale,
# décrite dans `exports/domain/provision_cp.py` (retour d'Elsa du 05/11/2026).
from __future__ import annotations

import calendar
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import supabase
from app.modules.absences.application.queries import (
    _hours_per_rest_day,
    _leave_context,
    _parse_hire_date,
)
from app.modules.absences.domain.rules import (
    compute_cp_period_balances,
    heures_repos_prises,
)
from app.modules.absences.infrastructure import fractionnement_repository as frac_repo
from app.modules.absences.infrastructure.repository import absence_repository
from app.modules.exports.domain.provision_cp import (
    JOURS_OUVRES_PAR_MOIS,
    LigneProvision,
    PeriodeProvision,
    bornes_des_periodes,
    calculer_ligne,
    calculer_totaux,
    en_jours_ouvres,
    mois_de_reference,
    patronal_du_bulletin,
    present_a_la_date,
    primes_recurrentes,
    reference_du_salarie,
    repos_en_jours,
)
from app.shared.reprise_paie import lire_bascule as _lire_bascule
from app.shared.reprise_paie import rang_du_mois
from app.shared.utils.export import generate_csv, generate_xlsx
from app.shared.domain.pluriel import accord, pluriel

#: PostgREST tronque une réponse à 1000 lignes sans le dire — on pagine en deçà.
TAILLE_PAGE = 500

EXPORT_HEADERS = [
    "Matricule",
    "Nom de l'employé",
    "Date d'entrée",
    "Solde jrs N-1",
    "Solde jrs N",
    "Solde jrs repos compensateur",
    "Solde jours",
    "Valeur d'un jour (maintien)",
    "Dont primes récurrentes (par mois)",
    "Base dixième N-1",
    "Base dixième N",
    "Dont absences reconstituées",
    "Provision N-1",
    "Provision N",
    "Provision repos",
    "Méthode",
    "Provision",
    "Taux Ch. soc.",
    "Montant charges sociales",
    "Total",
    "Mois retenus",
    "Anomalie",
]

Mois = Tuple[int, int]


def _fin_de_mois(period: str) -> date:
    annee, mois = map(int, period.split("-"))
    return date(annee, mois, calendar.monthrange(annee, mois)[1])


def _montant_contractuel(salarie: Dict[str, Any]) -> Optional[float]:
    brut = salarie.get("salaire_de_base")
    if isinstance(brut, dict):
        # La base stocke {"type": "mensuel", "valeur": 2049.76} : c'est « valeur » qui
        # porte le montant. Les autres clés sont des variantes rencontrées à l'import.
        for cle in ("valeur", "montant", "value", "brut_mensuel", "amount"):
            valeur = brut.get(cle)
            if isinstance(valeur, (int, float)):
                return float(valeur)
        return None
    return float(brut) if isinstance(brut, (int, float)) else None


def _lire_salaries(
    company_id: str,
    employee_ids: Optional[List[str]] = None,
    ref_date: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """Les salariés présents à la fin du mois demandé (`present_a_la_date`), quel que soit leur
    statut d'aujourd'hui : un salarié parti en juin est dans la provision de mai. Sans date
    d'entrée, seul un salarié actif est gardé, pour être signalé."""
    requete = (
        supabase.table("employees")
        .select(
            "id, matricule, first_name, last_name, hire_date, employment_status, "
            "salaire_de_base, duree_hebdomadaire, specificites_paie"
        )
        .eq("company_id", company_id)
    )
    if employee_ids:
        requete = requete.in_("id", employee_ids)
    salaries = requete.execute().data or []
    sorties: Dict[str, List[date]] = {}
    ids = [s["id"] for s in salaries]
    if ids:
        for sortie in (
            supabase.table("employee_exits")
            .select("employee_id, last_working_day, exit_type")
            .in_("employee_id", ids)
            .execute()
            .data
            or []
        ):
            if sortie.get("exit_type") == "transfert" or not sortie.get("last_working_day"):
                continue
            sorties.setdefault(sortie["employee_id"], []).append(
                date.fromisoformat(str(sortie["last_working_day"])[:10])
            )
    ref = ref_date or date.today()
    lignes = [
        s for s in salaries
        if (not s.get("hire_date") and s.get("employment_status") == "actif")
        or (
            s.get("hire_date")
            and present_a_la_date(
                date.fromisoformat(str(s["hire_date"])[:10]), sorties.get(s["id"], []), ref
            )
        )
    ]
    return sorted(lignes, key=lambda e: (e.get("last_name") or "", e.get("first_name") or ""))


def _lire_bulletins(
    company_id: str, mois_cibles: List[Tuple[int, int]]
) -> Dict[str, Dict[Tuple[int, int], Tuple[float, float]]]:
    """Brut et cotisations patronales par salarié et par mois, sur la fenêtre demandée : le
    taux de charges de l'état, et le salaire moyen de repli.

    La lecture est paginée : PostgREST plafonne une réponse à 1000 lignes sans
    le signaler. Une société de 90 salariés dépasse ce seuil dès douze mois
    d'historique, et les bulletins tombés dans la troncature ne sont pas
    « manquants » — ils faussent le taux de charges sans la moindre anomalie affichée.
    """
    annees = sorted({a for a, _ in mois_cibles})
    lignes: List[Dict[str, Any]] = []
    decalage = 0
    while True:
        lot = (
            supabase.table("payslips")
            .select("employee_id, year, month, payslip_data")
            .eq("company_id", company_id)
            .in_("year", annees)
            .range(decalage, decalage + TAILLE_PAGE - 1)
            .execute()
        ).data or []
        lignes.extend(lot)
        if len(lot) < TAILLE_PAGE:
            break
        decalage += TAILLE_PAGE
    attendus = set(mois_cibles)
    resultat: Dict[str, Dict[Tuple[int, int], Tuple[float, float]]] = {}
    for ligne in lignes:
        cle = (ligne["year"], ligne["month"])
        if cle not in attendus:
            continue
        donnees = ligne.get("payslip_data") or {}
        brut = float(donnees.get("salaire_brut") or 0)
        patronal = patronal_du_bulletin(donnees)
        # Un mois à deux contrats a deux bulletins : la provision les somme (D3).
        deja_brut, deja_patronal = resultat.setdefault(ligne["employee_id"], {}).get(cle, (0.0, 0.0))
        resultat[ligne["employee_id"]][cle] = (deja_brut + brut, deja_patronal + patronal)
    return resultat


class BulletinDuMois:
    """Ce que la provision lit d'un bulletin pour le dixième et le maintien."""

    __slots__ = ("brut", "lignes", "importe", "bulletins")

    def __init__(self, brut: float = 0.0, lignes: Optional[List[Dict[str, Any]]] = None, importe: bool = False):
        self.brut = brut
        self.lignes = lignes or []
        self.importe = importe
        self.bulletins: List[Dict[str, Any]] = []


def _lire_details_bulletins(
    company_id: str, annees: List[int]
) -> Dict[str, Dict[Mois, BulletinDuMois]]:
    """Brut, lignes du brut et origine de chaque bulletin des années demandées, par salarié.

    Seuls `salaire_brut`, `calcul_du_brut` et `details_absences` sont lus (chemins JSON), pas
    tout le bulletin. Le moteur porte ses retenues d'absence dans `details_absences` ; un
    bulletin repris les a dans `calcul_du_brut` et `details_absences` vide (la lecture de
    `solde_de_tout_compte/common/bulletin_de_sortie.lignes_du_bulletin`) : les deux se lisent
    ensemble. Sans cela, un arrêt au forfait jours de MAJI (avril 2026) retirait le maintien
    de salaire sans reconstituer l'absence. Paginé comme `_lire_bulletins`. Deux bulletins le
    même mois (deux contrats) s'ajoutent."""
    resultat: Dict[str, Dict[Mois, BulletinDuMois]] = {}
    decalage = 0
    while True:
        lot = (
            supabase.table("payslips")
            .select(
                "employee_id, year, month, origine, brut:payslip_data->salaire_brut, "
                "lignes:payslip_data->calcul_du_brut, absences:payslip_data->details_absences"
            )
            .eq("company_id", company_id)
            .in_("year", annees)
            .order("id")
            .range(decalage, decalage + TAILLE_PAGE - 1)
            .execute()
        ).data or []
        for ligne in lot:
            cle = (int(ligne["year"]), int(ligne["month"]))
            mois = resultat.setdefault(ligne["employee_id"], {}).setdefault(cle, BulletinDuMois())
            try:
                mois.brut = round(mois.brut + float(ligne.get("brut") or 0), 2)
            except (TypeError, ValueError):
                pass
            from app.modules.payroll.infrastructure.reference_dixieme import lignes_pour_dixieme

            lignes_du_bulletin = lignes_pour_dixieme(
                {"calcul_du_brut": ligne.get("lignes"), "details_absences": ligne.get("absences")},
                importe=ligne.get("origine") == "importe",
            )
            mois.lignes += lignes_du_bulletin
            mois.bulletins.append({"annee": cle[0], "mois": cle[1], "brut": ligne.get("brut"), "lignes": lignes_du_bulletin})
            mois.importe = mois.importe or ligne.get("origine") == "importe"
        if len(lot) < TAILLE_PAGE:
            return resultat
        decalage += TAILLE_PAGE


def _lire_cumuls(employee_ids: List[str], annee: int, mois: int) -> Dict[str, Dict[str, Any]]:
    """Les cumuls de paie du mois (`employee_schedules.cumuls.cumuls`) par salarié."""
    if not employee_ids:
        return {}
    lignes = (
        supabase.table("employee_schedules")
        .select("employee_id, cumuls")
        .eq("year", annee)
        .eq("month", mois)
        .in_("employee_id", employee_ids)
        .execute()
        .data
    ) or []
    resultat: Dict[str, Dict[str, Any]] = {}
    for ligne in lignes:
        cumuls = ligne.get("cumuls") or {}
        imbrique = cumuls.get("cumuls", cumuls) if isinstance(cumuls, dict) else {}
        if isinstance(imbrique, dict):
            resultat[ligne["employee_id"]] = imbrique
    return resultat


def _mois_debut_periode(company_id: str) -> int:
    from app.modules.absences.infrastructure.leave_settings_repository import get_leave_policy

    try:
        return int(get_leave_policy(str(company_id)).cp_reference_period_start_month or 6)
    except Exception:
        return 6


def _brut_des_bulletins(bulletins: Dict[Mois, BulletinDuMois], mois: List[Mois]) -> Optional[float]:
    presents = [bulletins[m].brut for m in mois if m in bulletins]
    return round(sum(presents), 2) if presents else None


def _base_dans_les_cumuls(cumuls: Optional[Dict[str, Any]], debut: date, fin: date) -> Optional[float]:
    """`brut_reference_n_1` des cumuls quand ils portent sur la période [debut, fin]."""
    if not cumuls or cumuls.get("brut_reference_n_1") is None:
        return None
    if str(cumuls.get("brut_reference_period_start") or "")[:10] != debut.isoformat():
        return None
    try:
        return round(float(cumuls["brut_reference_n_1"]), 2)
    except (TypeError, ValueError):
        return None


def _bases_detaillees_du_dixieme(
    bulletins: Dict[Mois, BulletinDuMois],
    cumuls_fin_n1: Optional[Dict[str, Any]],
    cumuls_du_mois: Optional[Dict[str, Any]],
    periodes: Tuple[Tuple[date, date], Tuple[date, date]],
    *, entree: Optional[date] = None,
):
    from app.shared.domain.dixieme_conges import BaseDixieme, calculer_base_periode

    resultats = []
    for (debut, fin), cumuls in zip(periodes, (cumuls_fin_n1, cumuls_du_mois)):
        dernier = bulletins.get((fin.year, fin.month))
        brut_repris = None if dernier is not None and dernier.importe else _base_dans_les_cumuls(cumuls, debut, fin)
        debut_effectif = max(debut, entree) if entree else debut
        if debut_effectif > fin:
            resultats.append(BaseDixieme(0.0))
            continue
        resultats.append(calculer_base_periode(
            [detail for (a, m), b in bulletins.items() for detail in (b.bulletins or [{"annee": a, "mois": m, "brut": b.brut, "lignes": b.lignes}])],
            debut=debut_effectif, fin=fin, brut_repris=brut_repris,
        ))
    return resultats


def bases_du_dixieme(
    bulletins: Dict[Mois, BulletinDuMois],
    cumuls_fin_n1: Optional[Dict[str, Any]],
    cumuls_du_mois: Optional[Dict[str, Any]],
    periodes: Tuple[Tuple[date, date], Tuple[date, date]],
) -> Tuple[Optional[float], Optional[float], float]:
    """La base légale unique ; un mois absent sans cumul déclaré reste inconnu."""
    n1, n = _bases_detaillees_du_dixieme(bulletins, cumuls_fin_n1, cumuls_du_mois, periodes)
    return n1.base, n.base, round(n1.reconstitution - n1.complement_remplace + n.reconstitution - n.complement_remplace, 2)


def _lire_conges_ouvres(
    employee_id: str, company_id: str, ref_date: date
) -> Tuple[PeriodeProvision, PeriodeProvision]:
    """Congés N-1 et N à la date, en jours ouvrés : restants (le solde de l'écran) et droits
    légaux acquis (sans les jours d'ancienneté), sans encore de base du dixième."""
    vide = PeriodeProvision(restants=0.0, droits=0.0, base=None)
    hire_date = _parse_hire_date(employee_id)
    if not hire_date:
        return vide, vide
    policy, adjustment, _, cp_seniority = _leave_context(
        employee_id, ref_date.year, company_id
    )
    from app.modules.absences.application.fractionnement_prefill import (
        build_employee_cp_seniority_context_from_db,
    )

    contexte = build_employee_cp_seniority_context_from_db(employee_id)
    validees = absence_repository.list_validated_for_employees([employee_id])
    periodes = compute_cp_period_balances(
        hire_date,
        validees,
        ref_date,
        policy=policy,
        adjustment=adjustment,
        cp_seniority=cp_seniority,
        employee_ctx=contexte,
    )
    reglages = frac_repo.get_fractionnement_settings_row(company_id) or {}
    ratio = float(reglages.get("ouvres_to_ouvrables_ratio") or 1.2)
    # Le solde est dans l'unité de la société : seul un solde en ouvrables se convertit.
    unite = getattr(policy, "cp_counting_unit", None)

    def periode(cle: str, cle_anciennete: str) -> PeriodeProvision:
        p = periodes[cle]
        acquis = float(p.get("acquis") or 0) - float(periodes.get(cle_anciennete) or 0)
        return PeriodeProvision(
            restants=en_jours_ouvres(float(p.get("solde") or 0), unite, ratio),
            droits=en_jours_ouvres(max(acquis, 0.0), unite, ratio),
            base=None,
        )

    return (
        periode("periode_precedente", "cp_seniority_n1"),
        periode("periode_courante", "cp_seniority_n"),
    )


def _valeur_jour_du_contrat(salarie: Dict[str, Any]) -> float:
    """Un jour de congé au maintien d'après la fiche : base et heures sup structurelles
    majorées, la règle du bulletin de sortie (`iccp_fin_contrat.valeur_jour_maintien`)."""
    salaire = _montant_contractuel(salarie)
    if not salaire or salaire <= 0:
        return 0.0
    from app.modules.payroll.engine.calcul_indemnites_sortie import (
        MAJORATION_HS_STRUCTURELLES,
        _salaire_habituel_et_taux_horaire,
    )
    from app.modules.payroll.engine.iccp_fin_contrat import valeur_jour_maintien

    _, taux_horaire, duree = _salaire_habituel_et_taux_horaire(salarie, float(salaire))
    if taux_horaire <= 0:
        return 0.0
    return round(valeur_jour_maintien(taux_horaire, duree, MAJORATION_HS_STRUCTURELLES), 2)


def _lire_credits_repos(company_id: str, annee: int, mois: int) -> Dict[str, float]:
    """Heures de repos compensateur créditées par salarié, de janvier au mois demandé inclus.

    Le compteur est celui de l'écran des soldes (l'année civile), arrêté au mois de la
    provision : un crédit d'octobre n'existe pas encore au 30/09. Lecture paginée, comme
    les bulletins (PostgREST tronque à 1000 lignes sans le dire)."""
    heures: Dict[str, float] = {}
    decalage = 0
    while True:
        lot = (
            supabase.table("repos_compensateur_credits")
            .select("employee_id, heures")
            .eq("company_id", company_id)
            .eq("year", annee)
            .lte("month", mois)
            .order("id")
            .range(decalage, decalage + TAILLE_PAGE - 1)
            .execute()
        ).data or []
        for credit in lot:
            eid = credit.get("employee_id")
            heures[eid] = round(heures.get(eid, 0.0) + float(credit.get("heures") or 0), 2)
        if len(lot) < TAILLE_PAGE:
            return heures
        decalage += TAILLE_PAGE


def _lire_repos(
    company_id: str, ref_date: date, employee_ids: List[str]
) -> Dict[str, Tuple[float, str]]:
    """Solde de repos compensateur en jours à la date, et son anomalie, par salarié.

    Acquis : les crédits de l'année jusqu'au mois demandé. Pris : les repos validés de
    l'année jusqu'à la date, une journée valant le réglage de la société."""
    if not employee_ids:
        return {}
    credits = _lire_credits_repos(company_id, ref_date.year, ref_date.month)
    par_salarie: Dict[str, List[Dict[str, Any]]] = {}
    for demande in absence_repository.list_validated_for_employees(employee_ids):
        if demande.get("type") == "repos_compensateur":
            par_salarie.setdefault(demande.get("employee_id"), []).append(demande)
    heures_par_jour = _hours_per_rest_day(company_id)
    recuperation = _soldes_recuperation(company_id, employee_ids, ref_date.year, ref_date.month)
    resultat: Dict[str, Tuple[float, str]] = {}
    for eid in employee_ids:
        prises = heures_repos_prises(
            par_salarie.get(eid, []),
            ref_date,
            hours_per_rest_day=heures_par_jour,
            period_start=date(ref_date.year, 1, 1),
            period_end=date(ref_date.year, 12, 31),
        )
        acquises = credits.get(eid, 0.0)
        jours, anomalie = (0.0, "")
        if acquises or prises:
            jours, anomalie = repos_en_jours(acquises, prises, heures_par_jour)
        # Heures de récupération (repos compensateur de remplacement) : le solde
        # du compteur à la fin du mois, dû tant qu'il n'est ni pris ni payé (spec
        # 2026-11-05-heures-de-recuperation). À part : un repos pris sans crédit
        # ne vient pas le diminuer, il se signale.
        heures_recup = recuperation.get(eid, 0.0)
        if heures_recup:
            jours = round(jours + repos_en_jours(heures_recup, 0.0, heures_par_jour)[0], 2)
        if acquises or prises or heures_recup:
            resultat[eid] = (jours, anomalie)
    return resultat


def _soldes_recuperation(
    company_id: str, employee_ids: List[str], annee: int, mois: int
) -> Dict[str, float]:
    """Solde du compteur de récupération de chaque salarié à la fin du mois ;
    vide quand la société paie ses heures sup."""
    from app.modules.modulation.domain.hour_account_rules import solde_au
    from app.modules.modulation.infrastructure import repository as modulation_repo

    reglage = modulation_repo.get_modulation_settings(company_id)
    if not reglage.hour_account_enabled:
        return {}
    par_salarie: Dict[str, List[Dict[str, Any]]] = {}
    for mouvement in modulation_repo.list_movements_for_employees(employee_ids):
        par_salarie.setdefault(str(mouvement.get("employee_id")), []).append(mouvement)
    soldes: Dict[str, float] = {}
    for eid, mouvements in par_salarie.items():
        solde = solde_au(mouvements, annee, mois)
        if solde > 0:
            soldes[eid] = solde
    return soldes


def collecter_lignes(
    company_id: str, period: str, employee_ids: Optional[List[str]] = None
) -> Tuple[List[LigneProvision], List[str]]:
    ref_date = _fin_de_mois(period)
    mois_cibles = mois_de_reference(ref_date.year, ref_date.month)
    periodes = bornes_des_periodes(ref_date, _mois_debut_periode(company_id))
    (debut_n1, fin_n1), _ = periodes
    salaries = _lire_salaries(company_id, employee_ids, ref_date=ref_date)
    bascule = _lire_bascule(company_id)
    # À partir du mois de la reprise, les soldes sont ceux du logiciel précédent.
    soldes_repris = bool(bascule) and rang_du_mois(ref_date.year, ref_date.month) >= bascule.rang
    bulletins = _lire_bulletins(company_id, mois_cibles)
    avec_date = [s["id"] for s in salaries if s.get("hire_date")]
    details = _lire_details_bulletins(company_id, list(range(debut_n1.year, ref_date.year + 1)))
    cumuls_fin_n1 = _lire_cumuls(avec_date, fin_n1.year, fin_n1.month)
    cumuls_du_mois = _lire_cumuls(avec_date, ref_date.year, ref_date.month)
    repos = _lire_repos(company_id, ref_date, avec_date)

    lignes: List[LigneProvision] = []
    sans_date = 0
    maintien_seul = 0

    for salarie in salaries:
        if not salarie.get("hire_date"):
            sans_date += 1
            continue
        eid = salarie["id"]
        n1, n = _lire_conges_ouvres(eid, company_id, ref_date)
        jours_repos, anomalie_repos = repos.get(eid, (0.0, ""))
        if round(n1.restants + n.restants + jours_repos, 2) == 0 and not anomalie_repos:
            continue
        reference = reference_du_salarie(
            bulletins.get(eid, {}),
            mois_cibles,
            _montant_contractuel(salarie),
            date.fromisoformat(str(salarie["hire_date"])[:10]),
        )
        anomalies = [reference.anomalie]

        bulletins_du_salarie = details.get(eid, {})
        detail_n1, detail_n = _bases_detaillees_du_dixieme(
            bulletins_du_salarie, cumuls_fin_n1.get(eid), cumuls_du_mois.get(eid), periodes,
            entree=date.fromisoformat(str(salarie["hire_date"])[:10]),
        )
        base_n1, base_n = detail_n1.base, detail_n.base
        reconstitution = round(detail_n1.reconstitution - detail_n1.complement_remplace + detail_n.reconstitution - detail_n.complement_remplace, 2)
        anomalies.extend(detail_n1.alertes)
        anomalies.extend(detail_n.alertes)
        n1 = PeriodeProvision(restants=n1.restants, droits=n1.droits, base=base_n1)
        n = PeriodeProvision(restants=n.restants, droits=n.droits, base=base_n)
        for libelle, p in (("N-1", n1), ("N", n)):
            if p.restants > 0 and (p.base is None or p.droits <= 0):
                maintien_seul += 1
                anomalies.append(f"rémunération de la période {libelle} inconnue : maintien seul")

        # Un mois entier d'absence n'a pas de prime : il ne dit rien de ce qui revient chaque mois.
        derniers = [
            bulletins_du_salarie[m].lignes
            for m in sorted(bulletins_du_salarie)
            if m <= (ref_date.year, ref_date.month) and bulletins_du_salarie[m].brut > 0
        ]
        primes = primes_recurrentes(derniers)
        valeur_contrat = _valeur_jour_du_contrat(salarie)
        if valeur_contrat <= 0:
            valeur_contrat = round(reference.salaire_reference / JOURS_OUVRES_PAR_MOIS, 2)
            anomalies.append("pas de salaire contractuel : jour valorisé sur la moyenne des bulletins")
            primes = 0.0  # la moyenne des bulletins les contient déjà
        valeur_jour = round(valeur_contrat + primes / JOURS_OUVRES_PAR_MOIS, 2)

        if round(n1.restants + n.restants, 2) < 0:
            anomalies.append("solde négatif : congés pris d'avance")
        anomalies.append(anomalie_repos)
        lignes.append(
            calculer_ligne(
                matricule=salarie.get("matricule") or "",
                nom=f"{salarie.get('first_name') or ''} {salarie.get('last_name') or ''}".strip(),
                date_entree=str(salarie["hire_date"])[:10],
                n1=n1,
                n=n,
                valeur_jour=valeur_jour,
                taux_charges=reference.taux_charges,
                mois_retenus=reference.mois_retenus,
                solde_repos=jours_repos,
                primes_recurrentes=primes,
                reconstitution=reconstitution,
                anomalie="; ".join(a for a in anomalies if a),
            )
        )

    avertissements: List[str] = []
    if lignes and not soldes_repris:
        # Les congés antérieurs à janvier 2026 ne sont pas dans MARTINE : le solde de la
        # période précédente est un droit recalculé, pas un report repris du cabinet.
        # Mesuré le 07/08/2026 sur Cartol : 20,8 à 22,5 j chez nous contre 3 à 88 j
        # sur l'état du cabinet. Tant que les reports ne sont pas chargés, la provision
        # est sous-évaluée. Ne jamais laisser sortir ce chiffre sans le dire.
        avertissements.append(
            "Solde de la période précédente recalculé par Martine et non repris de "
            "la paie actuelle : les congés antérieurs à janvier 2026 n'y sont pas. La provision "
            "est indicative tant que les reports n'ont pas été chargés."
        )
    if lignes:
        premiers = [min(mois) for mois in details.values() if mois]
        if not premiers or min(premiers) > (debut_n1.year, debut_n1.month):
            avertissements.append(
                "Martine n'a pas tous les bulletins de la période précédente : les absences des "
                "mois sans bulletin ne sont pas reconstituées dans le dixième."
            )
    if maintien_seul:
        avertissements.append(
            f"{pluriel(maintien_seul, 'période')} au maintien seul : rémunération de la période "
            "inconnue de Martine (colonne Anomalie)."
        )
    if sans_date:
        avertissements.append(
            f"{pluriel(sans_date, 'salarié')} {accord(sans_date, 'exclu')} : aucune date d'entrée renseignée."
        )
    return lignes, avertissements


def preview_provision_cp(
    company_id: str, period: str, employee_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    lignes, avertissements = collecter_lignes(company_id, period, employee_ids)
    totaux = calculer_totaux(lignes)

    anomalies: List[Dict[str, Any]] = []
    bascule = _lire_bascule(company_id)
    annee, mois = map(int, period.split("-"))
    if bascule and rang_du_mois(annee, mois) < bascule.rang:
        # Avant la reprise, Martine n'a pas les soldes du logiciel précédent : elle n'aurait
        # que des droits recalculés depuis l'embauche, sans les congés pris (MAJI mai 2026).
        logiciel = bascule.logiciel_precedent or "le logiciel précédent"
        anomalies.append(
            {
                "type": "error",
                "message": (
                    f"Martine tient les congés de cette société depuis la reprise de "
                    f"{bascule.libelle} : la provision se calcule à partir de ce mois. "
                    f"Avant, les soldes sont dans {logiciel}."
                ),
                "severity": "blocking",
            }
        )
    if not bascule and lignes and all(l.anomalie.startswith("aucun bulletin") for l in lignes):
        # Ni reprise ni bulletin : la paie est encore ailleurs (Cartol, LEWIS, Mont Blanc au
        # 03/11/2026). Les soldes seraient des droits recalculés sans les congés pris, le
        # salaire celui de la fiche et les charges à zéro : un chiffre faux, pas indicatif.
        anomalies.append(
            {
                "type": "error",
                "message": (
                    "Martine n'a aucun bulletin ni reprise des congés pour cette société : "
                    "la paie et les soldes de congés sont encore dans le logiciel précédent. "
                    "La provision se fera dans Martine après la reprise."
                ),
                "severity": "blocking",
            }
        )
    if not lignes:
        anomalies.append(
            {
                "type": "error",
                "message": "Aucun salarié avec un solde de congés à cette date",
                "severity": "blocking",
            }
        )
    elif totaux["provision"] == 0:
        # Des soldes existent (une ligne à solde nul est hors périmètre) mais rien n'a pu
        # être valorisé : ni salaire contractuel, ni bulletin. Un fichier entièrement à
        # zéro se lirait comme « aucune dette », ce qui est faux.
        anomalies.append(
            {
                "type": "error",
                "message": (
                    "Aucune valeur disponible pour les jours : ni salaire contractuel ni "
                    "bulletin pour les salariés concernés"
                ),
                "severity": "blocking",
            }
        )
    nb_anomalies = sum(1 for l in lignes if l.anomalie)
    if nb_anomalies:
        anomalies.append(
            {
                "type": "warning",
                "message": f"{pluriel(nb_anomalies, 'ligne')} {accord(nb_anomalies, 'signalée')} dans la colonne Anomalie",
                "severity": "warning",
            }
        )

    return {
        "employees_count": len(lignes),
        "totals": {
            "employees_count": len(lignes),
            "total_amount": totaux["total"],
        },
        "anomalies": anomalies,
        "warnings": avertissements,
        "can_generate": all(a.get("severity") != "blocking" for a in anomalies),
        "details": {
            "provision": totaux["provision"],
            "montant_charges": totaux["montant_charges"],
            "total": totaux["total"],
            "solde_jours": totaux["solde_jours"],
            "solde_repos": totaux["solde_repos"],
            "taux_charges_moyen": totaux["taux_charges"],
        },
    }


def _cellule(valeur: Optional[float]) -> Any:
    return "" if valeur is None else valeur


def _lignes_export(lignes: List[LigneProvision]) -> List[Dict[str, Any]]:
    donnees = [
        {
            "Matricule": l.matricule,
            "Nom de l'employé": l.nom,
            "Date d'entrée": l.date_entree,
            "Solde jrs N-1": l.solde_n1,
            "Solde jrs N": l.solde_n,
            "Solde jrs repos compensateur": l.solde_repos,
            "Solde jours": l.solde_jours,
            "Valeur d'un jour (maintien)": l.valeur_jour,
            "Dont primes récurrentes (par mois)": l.primes_recurrentes,
            "Base dixième N-1": _cellule(l.base_n1),
            "Base dixième N": _cellule(l.base_n),
            "Dont absences reconstituées": l.reconstitution,
            "Provision N-1": l.provision_n1,
            "Provision N": l.provision_n,
            "Provision repos": l.provision_repos,
            "Méthode": l.methode,
            "Provision": l.provision,
            "Taux Ch. soc.": l.taux_charges,
            "Montant charges sociales": l.montant_charges,
            "Total": l.total,
            "Mois retenus": l.mois_retenus,
            "Anomalie": l.anomalie,
        }
        for l in lignes
    ]
    totaux = calculer_totaux(lignes)
    donnees.append(
        {
            "Matricule": "",
            "Nom de l'employé": "Total",
            "Date d'entrée": "",
            "Solde jrs N-1": totaux["solde_n1"],
            "Solde jrs N": totaux["solde_n"],
            "Solde jrs repos compensateur": totaux["solde_repos"],
            "Solde jours": totaux["solde_jours"],
            "Valeur d'un jour (maintien)": "",
            "Dont primes récurrentes (par mois)": "",
            "Base dixième N-1": "",
            "Base dixième N": "",
            "Dont absences reconstituées": totaux["reconstitution"],
            "Provision N-1": totaux["provision_n1"],
            "Provision N": totaux["provision_n"],
            "Provision repos": totaux["provision_repos"],
            "Méthode": "",
            "Provision": totaux["provision"],
            "Taux Ch. soc.": totaux["taux_charges"],
            "Montant charges sociales": totaux["montant_charges"],
            "Total": totaux["total"],
            "Mois retenus": "",
            "Anomalie": "",
        }
    )
    return donnees


def generate_provision_cp_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    file_format: str = "xlsx",
) -> bytes:
    lignes, _ = collecter_lignes(company_id, period, employee_ids)
    donnees = _lignes_export(lignes)
    if file_format == "xlsx":
        return generate_xlsx(donnees, EXPORT_HEADERS, f"Provision CP {period}")
    return generate_csv(donnees, EXPORT_HEADERS)
