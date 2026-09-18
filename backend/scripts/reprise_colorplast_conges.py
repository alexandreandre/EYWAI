"""Reprise Colorplast : les compteurs de congés partent du bulletin Quadra de juin.

La société bascule au 30 juin 2026 (`company_payroll_takeover`). Les cumuls de
paie partent du solde d'ouverture de juin ; les compteurs de congés doivent en
faire autant. Or une reprise datée du 31/08 (recalage du 12/09, feuille
« compteurs fin août ») avait été posée entre-temps : notre juillet n'imprimait
alors aucun compteur, et les écarts stockés absorbaient des saisies en double de
l'été. Ce script remet les compteurs à la doctrine : une ouverture à la date de
bascule, lue sur le bulletin Quadra de juin, et tout ce qui suit calculé depuis
nos absences.

Il faut d'abord que nos absences disent la vérité :
- trois demandes validées en double sur les mêmes jours sont annulées par la
  commande applicative, qui ne restaure au calendrier que les jours qu'aucune
  autre demande validée ne couvre — ici aucun ;
- `jours_payes`, plafonné à la validation sous un solde alors faux, est réaligné
  sur ce que le bulletin a réellement payé : le moteur paie les jours du
  calendrier, seul le compteur lit `jours_payes`.

Simulation par défaut : elle rejoue le nettoyage en mémoire et montre les
compteurs d'août attendus face au bulletin Quadra d'août. `--apply` écrit, dans
l'ordre : nettoyage, reprise au 30/06 pour les sept salariés (écart au théorique,
via `apply_cp_solde_import`), régénération de juillet à septembre dans l'ordre —
le générateur n'écrit que le cumul du mois demandé —, puis contrôle que brut, net
et cumuls n'ont pas bougé et que les compteurs d'août égalent ceux de Quadra.

Le script est rejouable : une demande déjà annulée, un `jours_payes` déjà
réaligné ou une reprise déjà écrite au 30/06 avec les mêmes écarts sont sautés.

Usage :
    python -m scripts.reprise_colorplast_conges            # simulation
    python -m scripts.reprise_colorplast_conges --apply    # écrit
"""

from __future__ import annotations

import dataclasses
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402
from app.modules.absences.application.commands import (  # noqa: E402
    update_absence_request_status,
)
from app.modules.absences.application.leave_settings_commands import (  # noqa: E402
    apply_cp_solde_import,
)
from app.modules.absences.application.queries import (  # noqa: E402
    _leave_context,
    _parse_hire_date,
)
from app.modules.absences.domain.leave_policy import EmployeeLeaveAdjustment  # noqa: E402
from app.modules.absences.domain.planning_cp import merge_planning_cp_days  # noqa: E402
from app.modules.absences.domain.rules import compute_cp_period_balances  # noqa: E402
from app.modules.absences.infrastructure import (  # noqa: E402
    planning_cp_repository,
    repository as absences_repository_module,
)
from app.modules.absences.infrastructure.leave_settings_repository import (  # noqa: E402
    get_employee_adjustment,
)
from app.modules.absences.infrastructure.repository import absence_repository  # noqa: E402
from app.modules.payslips.application.commands import generate_payslip  # noqa: E402
from app.modules.payslips.application.dto import (  # noqa: E402
    GeneratePayslipInput,
    PayslipBadRequestError,
    PayslipCalendarIncompleteError,
)
from scripts.backtest.colorplast_lignes_quadra import lire_bulletins  # noqa: E402

COMPANY_ID = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"
ANNEE = 2026
MOIS_BASCULE = 6
BASCULE = date(ANNEE, MOIS_BASCULE, 30)
MOIS_A_REGENERER = (7, 8, 9)
#: Anciens salariés partis avant 2026, payés d'une seule participation en mai.
HORS_REPRISE = ("CHALEYSSIN", "DA SILVA CARDOSO")

#: Demandes validées en double sur les mêmes jours. On garde celle dont les jours
#: sont ceux que le bulletin a payés, on annule l'autre.
DOUBLONS_A_ANNULER = {
    "c3b2f7bf-9134-4633-8766-75a3f61e21fa": (
        "BUGNY 03→12/08 (10 j) : doublon de f0a97857 (03→18/08, 12 j payés au "
        "bulletin d'août, 12 chez Quadra)"
    ),
    "615679fa-777f-425a-9279-88281fede297": (
        "ESPINOSA 13/07 : doublon de dd8abc67 (même jour)"
    ),
    "71a8d563-df87-4002-9821-18bca69c616d": (
        "GAUTHERON 03→14/08 (4 j payés) : doublon de 1faae243 (10 j payés au "
        "bulletin d'août, 10 chez Quadra)"
    ),
}

#: `jours_payes` plafonné à la validation sous un solde alors faux ; le bulletin
#: a payé les jours du calendrier. On réaligne sur le bulletin.
JOURS_PAYES_DU_BULLETIN = {
    "c5987827-c00e-411d-b716-18d764ff542b": (
        15.0, "ESPINOSA août : 15 j payés (bulletin et Quadra), plafonné à 12"
    ),
    "d7ea0527-bbc3-4e06-a04a-daa9515cd257": (
        1.0, "GAUTHERON 13/07 : 1 j payé (bulletin et Quadra), plafonné à 0,5"
    ),
    "02816a33-af5c-465f-8da6-0cd41763139d": (
        1.0, "GAUTHERON 21/07 : 1 j payé (bulletin et Quadra), plafonné à 0"
    ),
    "d8d4f06a-a888-404a-99db-2453c2853c9b": (
        12.0,
        "FUCKAR août : 12 j payés par notre bulletin, plafonné à 3. Quadra a payé "
        "10 j de CP et mis 17-18/08 en congés sans solde : écart de paie d'août, "
        "à traiter à part",
    ),
}

#: Bulletins marqués « modifiés à la main » que l'on régénère quand même, avec
#: la raison. Sans entrée ici, la retouche prime et le bulletin est laissé tel quel.
REGENERER_MALGRE_RETOUCHE = {
    "ESPINOSA": (
        "juillet : l'historique ne contient que des régénérations (dont une par "
        "Gaëlle depuis l'écran le 15/09), brut et net identiques dans toutes les "
        "versions depuis le 14/09 ; le drapeau est périmé, rien à préserver"
    ),
}


def appliquer_nettoyage(
    demandes: list[dict], doublons: set[str], jours_payes: dict[str, float]
) -> list[dict]:
    """Le nettoyage rejoué en mémoire : ce que la base contiendra après --apply."""
    restantes = []
    for demande in demandes:
        if demande.get("id") in doublons:
            continue
        copie = dict(demande)
        if copie.get("id") in jours_payes:
            copie["jours_payes"] = jours_payes[copie["id"]]
        restantes.append(copie)
    return restantes


def _salaries() -> dict[str, dict]:
    lignes = (
        supabase.table("employees")
        .select("id, last_name, first_name, employment_status")
        .eq("company_id", COMPANY_ID)
        .execute()
        .data
    )
    return {
        str(e["last_name"]).upper(): e
        for e in lignes
        if str(e["last_name"]).upper() not in HORS_REPRISE
    }


def _demandes_validees(employee_id: str) -> list[dict]:
    """Comme `list_validated_for_employees`, mais avec l'identifiant, pour rejouer
    le nettoyage en mémoire ; le planning est fusionné avec la bascule comme
    date de reprise, ce que la base fera après --apply."""
    demandes = (
        supabase.table("absence_requests")
        .select(
            "id, employee_id, type, selected_days, jours_payes, demi_journees, "
            "heures_par_jour, arret_type"
        )
        .eq("employee_id", employee_id)
        .eq("status", "validated")
        .execute()
        .data
        or []
    )
    for demande in demandes:
        # La fusion avec le planning ne dédoublonne que les demandes validées.
        demande.setdefault("status", "validated")
    return demandes


def _avec_planning(demandes: list[dict], employee_id: str) -> list[dict]:
    planning = planning_cp_repository.list_planning_cp_days([employee_id])
    return merge_planning_cp_days(demandes, planning, {employee_id: BASCULE})


def _solde(cp: dict, indice: int) -> float:
    """Quadra n'imprime pas un solde négatif de façon lisible : on le recompose."""
    if "Solde" in cp:
        return float(cp["Solde"][indice])
    return round(float(cp["Acquis"][indice]) - float(cp["Total pris"][indice]), 2)


def _plan(salaries: dict[str, dict]) -> list[dict]:
    """Une ligne par salarié : cible de juin, écart à écrire, août prévu et Quadra."""
    quadra_juin = lire_bulletins(ANNEE, MOIS_BASCULE)
    quadra_aout = lire_bulletins(ANNEE, 8)
    vide = EmployeeLeaveAdjustment.empty()
    fin_aout = date(ANNEE, 8, 31)
    lignes = []
    for nom, salarie in sorted(salaries.items()):
        if nom not in quadra_juin:
            print(f"  {nom:10s} !! absent du bulletin Quadra de juin, ignoré")
            continue
        eid = salarie["id"]
        hire = _parse_hire_date(eid)
        policy, _, _, cp_seniority = _leave_context(eid, ANNEE, COMPANY_ID)
        demandes = appliquer_nettoyage(
            _demandes_validees(eid),
            set(DOUBLONS_A_ANNULER),
            {k: v[0] for k, v in JOURS_PAYES_DU_BULLETIN.items()},
        )
        demandes = _avec_planning(demandes, eid)
        cible_n1 = _solde(quadra_juin[nom].cp, 0)
        cible_n = _solde(quadra_juin[nom].cp, 1)
        theorique = compute_cp_period_balances(
            hire, demandes, BASCULE, policy=policy, adjustment=vide,
            cp_seniority=cp_seniority,
        )
        ecart_n1 = round(cible_n1 - max(0.0, theorique["n1_remaining"]), 2)
        ecart_n = round(cible_n - max(0.0, theorique["n_remaining"]), 2)
        ajustement = dataclasses.replace(
            vide, cp_n1_opening_balance=ecart_n1, cp_n_opening_balance=ecart_n
        )
        aout = compute_cp_period_balances(
            hire, demandes, fin_aout, policy=policy, adjustment=ajustement,
            cp_seniority=cp_seniority,
        )
        quadra = quadra_aout.get(nom)
        lignes.append(
            {
                "nom": nom,
                "employee_id": eid,
                "cible_n1": cible_n1,
                "cible_n": cible_n,
                "theorique_n1": theorique["n1_remaining"],
                "theorique_n": theorique["n_remaining"],
                "ecart_n1": ecart_n1,
                "ecart_n": ecart_n,
                "aout_n1": aout["n1_remaining"],
                "aout_n": round(
                    float(aout["periode_courante"]["acquis"])
                    + ecart_n
                    - float(aout["periode_courante"]["pris"]),
                    2,
                ),
                "aout_pris": round(
                    float(aout["periode_precedente"]["pris"])
                    + float(aout["periode_courante"]["pris"]),
                    2,
                ),
                "quadra_n1": _solde(quadra.cp, 0) if quadra else None,
                "quadra_n": _solde(quadra.cp, 1) if quadra else None,
                "quadra_pris": (
                    round(float(quadra.cp["Total pris"][0]) + float(quadra.cp["Total pris"][1]), 2)
                    if quadra else None
                ),
            }
        )
    return lignes


def _afficher_plan(lignes: list[dict]) -> None:
    print(
        f"\n{'Salarié':10s} {'Quadra 30/06':>13s} {'théorique':>13s} {'écart écrit':>13s} "
        f"| {'août prévu':>13s} {'pris':>5s} {'Quadra 31/08':>13s} {'pris':>5s} {'diff':>13s}"
    )
    print("-" * 118)
    for ligne in lignes:
        if ligne["quadra_n1"] is None:
            quadra, diff, qpris = "sorti", "", ""
        else:
            quadra = f"{ligne['quadra_n1']:6.2f}/{ligne['quadra_n']:6.2f}"
            diff = f"{ligne['aout_n1'] - ligne['quadra_n1']:+6.2f}/{ligne['aout_n'] - ligne['quadra_n']:+6.2f}"
            qpris = f"{ligne['quadra_pris']:5.2f}"
        print(
            f"{ligne['nom']:10s} {ligne['cible_n1']:6.2f}/{ligne['cible_n']:6.2f} "
            f"{ligne['theorique_n1']:6.2f}/{ligne['theorique_n']:6.2f} "
            f"{ligne['ecart_n1']:+6.2f}/{ligne['ecart_n']:+6.2f} | "
            f"{ligne['aout_n1']:6.2f}/{ligne['aout_n']:6.2f} {ligne['aout_pris']:5.2f} "
            f"{quadra:>13s} {qpris:>5s} {diff:>13s}"
        )


def _bulletins_a_regenerer() -> list[dict]:
    return sorted(
        (
            supabase.table("payslips")
            .select("id, employee_id, month, manually_edited, payslip_data")
            .eq("company_id", COMPANY_ID)
            .eq("year", ANNEE)
            .in_("month", list(MOIS_A_REGENERER))
            .eq("origine", "calcule")
            .execute()
            .data
            or []
        ),
        key=lambda b: (b["month"], b["employee_id"]),
    )


def _empreinte(bulletin: dict) -> dict:
    donnees = bulletin.get("payslip_data") or {}
    return {
        "salaire_brut": donnees.get("salaire_brut"),
        "net_a_payer": donnees.get("net_a_payer"),
        "cumuls": donnees.get("cumuls"),
    }


def _compteurs(bulletin: dict) -> str:
    solde = ((bulletin.get("payslip_data") or {}).get("pied_de_page") or {}).get(
        "solde_conges"
    )
    if not solde:
        return "aucun compteur"
    n1 = solde.get("conges_payes_periode_precedente") or {}
    n = solde.get("conges_payes") or {}
    return (
        f"N-1 {float(n1.get('solde') or 0):6.2f} (pris {float(n1.get('pris') or 0):5.2f})  "
        f"N {float(n.get('solde') or 0):5.2f} (pris {float(n.get('pris') or 0):5.2f})"
    )


def _nettoyer() -> None:
    print("\n--- 1. Nettoyage des demandes")
    for rid, raison in DOUBLONS_A_ANNULER.items():
        avant = absence_repository.get_by_id(rid) or {}
        if avant.get("status") == "cancelled":
            print(f"  déjà annulée  {rid[:8]}")
            continue
        update_absence_request_status(rid, "cancelled")
        commentaire = f"Annulée le {date.today():%d/%m/%Y} — {raison}"
        if avant.get("comment"):
            commentaire = f"{avant['comment']} — {commentaire}"
        absence_repository.update(rid, {"comment": commentaire})
        print(f"  annulée  {rid[:8]}  {raison}")
    for rid, (valeur, raison) in JOURS_PAYES_DU_BULLETIN.items():
        avant = absence_repository.get_by_id(rid) or {}
        if float(avant.get("jours_payes") or 0) == valeur:
            print(f"  déjà réaligné {rid[:8]}")
            continue
        commentaire = f"jours_payes {avant.get('jours_payes')} → {valeur} le {date.today():%d/%m/%Y} — {raison}"
        if avant.get("comment"):
            commentaire = f"{avant['comment']} — {commentaire}"
        absence_repository.update(rid, {"jours_payes": valeur, "comment": commentaire})
        print(f"  réaligné {rid[:8]}  {raison}")


def _ajustement_en_base(employee_id: str) -> dict | None:
    lignes = (
        supabase.table("employee_leave_adjustments")
        .select(
            "cp_opening_reference_date, cp_n1_opening_balance, cp_n_opening_balance, "
            "rtt_opening_balance"
        )
        .eq("employee_id", employee_id)
        .eq("year", ANNEE)
        .limit(1)
        .execute()
        .data
    )
    return lignes[0] if lignes else None


def _reprendre(lignes: list[dict]) -> None:
    print("\n--- 2. Reprise au 30/06/2026")
    for ligne in lignes:
        en_base = _ajustement_en_base(ligne["employee_id"])
        if (
            en_base
            and str(en_base["cp_opening_reference_date"])[:10] == BASCULE.isoformat()
            and float(en_base["cp_n1_opening_balance"]) == ligne["ecart_n1"]
            and float(en_base["cp_n_opening_balance"]) == ligne["ecart_n"]
        ):
            print(f"  {ligne['nom']:10s} déjà reprise au 30/06 avec les mêmes écarts")
            continue
        precedent = get_employee_adjustment(ligne["employee_id"], ANNEE)
        note = (
            f"Reprise Quadra au {BASCULE:%d/%m/%Y} (bascule de la société) : soldes du "
            f"bulletin de juin, N-1 {ligne['cible_n1']:.2f} / N {ligne['cible_n']:.2f}"
        )
        if precedent.note:
            note = f"{note} — remplace : {precedent.note}"
        apply_cp_solde_import(
            COMPANY_ID,
            ligne["employee_id"],
            ANNEE,
            cp_n1_solde=ligne["cible_n1"],
            cp_n_solde=ligne["cible_n"],
            rtt_solde=0.0,
            month=MOIS_BASCULE,
            note=note,
        )
        ecrit = _ajustement_en_base(ligne["employee_id"])
        print(
            f"  {ligne['nom']:10s} réf {ecrit['cp_opening_reference_date']}  "
            f"N-1 {float(ecrit['cp_n1_opening_balance']):+6.2f}  N {float(ecrit['cp_n_opening_balance']):+5.2f}  "
            f"RTT {float(ecrit['rtt_opening_balance']):+5.2f}"
            + ("" if float(ecrit["cp_n1_opening_balance"]) == ligne["ecart_n1"] else "  !! différent de la simulation")
        )
    # Les caches de quelques secondes du calcul des soldes serviraient encore
    # l'ancienne date de reprise à la régénération qui suit.
    absences_repository_module._planning_cache.clear()
    absences_repository_module._cutoff_cache.clear()


def _regenerer(bulletins: list[dict], noms: dict[str, str]) -> list[str]:
    print("\n--- 3. Régénération de juillet à septembre, dans l'ordre")
    echecs: set[str] = set()
    for b in bulletins:
        nom = noms.get(b["employee_id"], b["employee_id"][:8])
        if b.get("manually_edited") and nom not in REGENERER_MALGRE_RETOUCHE:
            print(f"  {b['month']:02d} {nom:10s} !! modifié à la main, non régénéré")
            echecs.add(b["employee_id"])
            continue
        if b["employee_id"] in echecs:
            print(f"  {b['month']:02d} {nom:10s} sauté : un mois précédent a échoué")
            continue
        try:
            resultat = generate_payslip(
                GeneratePayslipInput(
                    employee_id=b["employee_id"],
                    year=ANNEE,
                    month=b["month"],
                    force_calendrier_incomplet=True,
                    regenerer_bulletin_valide=True,
                    requested_by_name="script reprise_colorplast_conges",
                )
            )
            print(f"  {b['month']:02d} {nom:10s} {resultat.status}")
        except (PayslipBadRequestError, PayslipCalendarIncompleteError) as exc:
            print(f"  {b['month']:02d} {nom:10s} !! refusé : {exc}")
            echecs.add(b["employee_id"])
    return sorted(noms.get(e, e) for e in echecs)


def _controler(avant: dict[str, dict], noms: dict[str, str]) -> int:
    print("\n--- 4. Contrôle")
    quadra = {m: lire_bulletins(ANNEE, m) for m in (7, 8)}
    apres = {b["id"]: b for b in _bulletins_a_regenerer()}
    anomalies = 0
    for bid, b in sorted(apres.items(), key=lambda kv: (kv[1]["month"], noms.get(kv[1]["employee_id"], ""))):
        nom = noms.get(b["employee_id"], b["employee_id"][:8])
        if _empreinte(b) != avant.get(bid):
            anomalies += 1
            print(f"  {b['month']:02d} {nom:10s} !! brut, net ou cumuls ont changé")
        q = quadra.get(b["month"], {}).get(nom)
        reference = (
            f"Quadra N-1 {_solde(q.cp, 0):6.2f} (pris {float(q.cp['Total pris'][0]):5.2f})  "
            f"N {_solde(q.cp, 1):5.2f} (pris {float(q.cp['Total pris'][1]):5.2f})"
            if q and q.cp else "Quadra : —"
        )
        print(f"  {b['month']:02d} {nom:10s} nous {_compteurs(b)}   {reference}")
    return anomalies


def main(appliquer: bool) -> int:
    salaries = _salaries()
    noms = {s["id"]: nom for nom, s in salaries.items()}
    print("Demandes à annuler :")
    for rid, raison in DOUBLONS_A_ANNULER.items():
        print(f"  {rid[:8]}  {raison}")
    print("jours_payes à réaligner :")
    for rid, (valeur, raison) in JOURS_PAYES_DU_BULLETIN.items():
        print(f"  {rid[:8]}  → {valeur:g}  {raison}")

    lignes = _plan(salaries)
    _afficher_plan(lignes)

    bulletins = _bulletins_a_regenerer()
    print(f"\n{len(bulletins)} bulletins calculés à régénérer dans l'ordre : "
          + ", ".join(f"{b['month']:02d} {noms.get(b['employee_id'], '?')}" for b in bulletins))

    if not appliquer:
        print("\nSimulation : rien n'a été écrit. Relancer avec --apply.")
        return 0

    avant = {b["id"]: _empreinte(b) for b in bulletins}
    _nettoyer()
    _reprendre(lignes)
    echecs = _regenerer(bulletins, noms)
    anomalies = _controler(avant, noms)
    if echecs or anomalies:
        print(f"\n!! {len(echecs)} salarié(s) non régénéré(s) : {', '.join(echecs)} ; "
              f"{anomalies} bulletin(s) dont brut, net ou cumuls ont changé.")
        return 1
    print("\nTerminé : brut, net et cumuls inchangés sur tous les bulletins régénérés.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--apply" in sys.argv))
