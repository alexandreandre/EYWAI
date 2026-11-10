"""Relecture IA de la paie d'un mois : préparer, lancer, avancer, lire, marquer vu.

Rien ici ne touche à un bulletin : l'IA dit quoi regarder, c'est tout.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.modules.relecture_ia.domain.consignes import blocs_systeme
from app.modules.relecture_ia.domain.cout import (
    cout_unitaire_eur,
    cout_usd,
    phrase_cout_reel,
)
from app.modules.relecture_ia.domain.droits import compte_autorise
from app.modules.relecture_ia.domain.fiche import code_salarie, construire_fiche
from app.modules.relecture_ia.domain.garde import (
    appliquer_plafond,
    garder_signalements,
    normaliser_ligne,
)
from app.modules.relecture_ia.domain.selection import bulletins_a_relire, meme_version
from app.modules.relecture_ia.infrastructure.client_claude import (
    MODELE,
    RelecteurClaude,
    RelectureImpossible,
    cle_presente,
)
from app.modules.relecture_ia.infrastructure.repository import DepotRelecture
from app.shared.domain.pluriel import pluriel

logger = logging.getLogger(__name__)

_DELAI_REPRISE = timedelta(minutes=2)
_EN_PARALLELE = 4
_TAILLE_PAQUET = 20
_BATTEMENT_SECONDES = 30.0

MESSAGE_SANS_CLE = (
    "La relecture n'est pas encore branchée : la clé d'accès à l'IA n'est pas posée sur le "
    "serveur. Demandez à l'équipe Martine de la poser."
)
_MESSAGE_RIEN_A_RELIRE = (
    "Rien à relire : tous les bulletins de ce mois ont déjà été relus depuis leur "
    "dernière modification."
)
_MESSAGE_DEJA_EN_COURS = "Une relecture est déjà en cours : elle continue, inutile d'en relancer une."
_MESSAGE_INTERROMPUE = (
    "La relecture s'est interrompue à cause d'une erreur de Martine. Relancez-la : "
    "les bulletins déjà relus ne seront pas repris."
)
_MESSAGE_BULLETIN_DISPARU = (
    "Ce bulletin a été supprimé ou remplacé pendant la relecture. Relancez-la pour relire le nouveau."
)


class SocieteRefusee(Exception):
    """Le compte n'a pas accès RH à une société demandée."""


class SansSocieteCochee(Exception):
    """Aucune société demandée."""


class PointIntrouvable(Exception):
    """Le point marqué n'existe pas dans cette société."""


def peut_lancer(email: str | None) -> bool:
    return compte_autorise(email, os.environ.get("RELECTURE_IA_COMPTES"))


def societes_du_compte(user: Any) -> list[dict[str, str]]:
    """Les sociétés où ce compte a un accès RH."""
    return [
        {"company_id": str(a.company_id), "nom": a.company_name}
        for a in user.accessible_companies
        if user.has_rh_access_in_company(a.company_id)
    ]


def _repere_des_relus(versions: list[dict[str, Any]]) -> dict[str, Any]:
    """Pour chaque bulletin, la version relue la plus récente."""
    repere: dict[str, dict[str, Any]] = {}
    for ligne in versions:
        pid = str(ligne["payslip_id"])
        if pid not in repere or str(ligne.get("termine_at") or "") > str(
            repere[pid].get("termine_at") or ""
        ):
            repere[pid] = ligne
    return {pid: l.get("payslip_updated_at") for pid, l in repere.items()}


def _vue_relecture(relecture: dict[str, Any] | None) -> dict[str, Any] | None:
    if relecture is None:
        return None
    return {
        "id": relecture["id"],
        "statut": relecture["statut"],
        "year": relecture["year"],
        "month": relecture["month"],
        "total": relecture.get("total") or 0,
        "traites": relecture.get("traites") or 0,
        "echecs": relecture.get("echecs") or 0,
        "points": relecture.get("points") or 0,
        "message": relecture.get("message"),
        "termine_at": relecture.get("termine_at"),
    }


def _blocage() -> str | None:
    return None if cle_presente() else MESSAGE_SANS_CLE


def _est_bloquee(relecture: dict[str, Any]) -> bool:
    try:
        battement = datetime.fromisoformat(str(relecture["battement_at"]).replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return True
    return datetime.now(UTC) - battement > _DELAI_REPRISE


def _reprendre_si_bloquee(depot: DepotRelecture, relecture: dict[str, Any]) -> bool:
    if not _est_bloquee(relecture):
        return False
    seuil = (datetime.now(UTC) - _DELAI_REPRISE).isoformat()
    return depot.reprendre_si_bloquee(relecture["id"], seuil)


def preparer(
    societes: list[dict[str, str]], year: int, month: int, depot: DepotRelecture | None = None
) -> dict[str, Any]:
    """Ce que la fenêtre de confirmation montre. Ne lit aucun contenu de bulletin."""
    depot = depot or DepotRelecture()
    noms = {s["company_id"]: s["nom"] for s in societes}
    ids = list(noms)
    bulletins = depot.bulletins_du_mois(ids, year, month)
    deja_relus = _repere_des_relus(depot.versions_relues(ids, year, month))
    a_relire = bulletins_a_relire(bulletins, deja_relus)
    avec_regles = depot.societes_avec_regles(ids)

    def compter(lignes: list[dict[str, Any]], company_id: str) -> int:
        return sum(1 for l in lignes if str(l.get("company_id")) == company_id)

    lignes_societes = [
        {
            "company_id": company_id,
            "nom": noms[company_id],
            "bulletins_generes": compter(bulletins, company_id),
            "a_relire": compter(a_relire, company_id),
            "sans_regles": company_id not in avec_regles,
        }
        for company_id in ids
        if compter(bulletins, company_id) > 0
    ]
    derniere = depot.derniere_relecture_terminee(year, month)
    unitaire = cout_unitaire_eur(depot.couts_recents())
    return {
        "year": year,
        "month": month,
        "societes": sorted(lignes_societes, key=lambda s: s["nom"].lower()),
        "total_a_relire": len(a_relire),
        "cout_unitaire_eur": unitaire,
        "cout_estime_eur": round(unitaire * len(a_relire), 2),
        "derniere_relecture": derniere.get("termine_at") if derniere else None,
        "relecture_en_cours": _vue_relecture(depot.relecture_en_cours()),
        "blocage": _blocage(),
    }


def lancer(
    user_id: str,
    societes: list[dict[str, str]],
    year: int,
    month: int,
    company_ids: list[str],
    depot: DepotRelecture | None = None,
) -> dict[str, Any]:
    """Crée la relecture, ou dit pourquoi non. `a_executer` : tâche de fond à poser."""
    depot = depot or DepotRelecture()
    autorisees = {s["company_id"] for s in societes}
    demandees = list(dict.fromkeys(str(c) for c in company_ids))
    if not demandees:
        raise SansSocieteCochee
    if not set(demandees) <= autorisees:
        raise SocieteRefusee

    if (blocage := _blocage()) is not None:
        return {"statut": "bloquee", "message": blocage, "relecture_id": None, "a_executer": False}

    en_cours = depot.relecture_en_cours()
    if en_cours is not None:
        return {
            "statut": "deja_en_cours",
            "message": _MESSAGE_DEJA_EN_COURS,
            "relecture_id": en_cours["id"],
            "a_executer": _reprendre_si_bloquee(depot, en_cours),
        }

    a_relire = bulletins_a_relire(
        depot.bulletins_du_mois(demandees, year, month),
        _repere_des_relus(depot.versions_relues(demandees, year, month)),
    )
    if not a_relire:
        return {
            "statut": "rien_a_relire",
            "message": _MESSAGE_RIEN_A_RELIRE,
            "relecture_id": None,
            "a_executer": False,
        }

    relecture = depot.creer_relecture(
        {
            "year": year,
            "month": month,
            "company_ids": demandees,
            "statut": "en_cours",
            "total": len(a_relire),
            "lance_par": user_id,
            "cout_estime_eur": round(cout_unitaire_eur(depot.couts_recents()) * len(a_relire), 2),
        },
        [
            {
                "payslip_id": b["id"],
                "company_id": b["company_id"],
                "employee_id": b["employee_id"],
                "contract_period_id": b.get("contract_period_id"),
                "year": year,
                "month": month,
                "payslip_updated_at": b.get("updated_at"),
                "statut": "a_faire",
            }
            for b in a_relire
        ],
    )
    if relecture is None:
        return {
            "statut": "deja_en_cours",
            "message": _MESSAGE_DEJA_EN_COURS,
            "relecture_id": None,
            "a_executer": False,
        }
    return {
        "statut": "lancee",
        "message": None,
        "relecture_id": relecture["id"],
        "a_executer": True,
    }


def lire_etat(depot: DepotRelecture | None = None) -> dict[str, Any]:
    """Où en est la relecture ; reprend celle qu'un redémarrage a arrêtée."""
    depot = depot or DepotRelecture()
    relecture = depot.relecture_en_cours()
    if relecture is None:
        return {"relecture": _vue_relecture(depot.derniere_relecture()), "a_executer": False}
    return {
        "relecture": _vue_relecture(relecture),
        "a_executer": _reprendre_si_bloquee(depot, relecture),
    }


@dataclass
class _Avancement:
    traites: int = 0
    echecs: int = 0


def _mois_precedent(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _precedent_du_bulletin(
    precedents: list[dict[str, Any]], employee_id: str, contract_period_id: Any
) -> dict[str, Any] | None:
    """Le bulletin du même contrat au mois d'avant, à défaut celui du salarié."""
    du_salarie = [p for p in precedents if str(p.get("employee_id")) == str(employee_id)]
    for candidat in du_salarie:
        if candidat.get("contract_period_id") == contract_period_id:
            return candidat.get("payslip_data")
    return du_salarie[0].get("payslip_data") if du_salarie else None


_COLONNES_NOM = ("first_name", "last_name", "nom_usage")


def _contrat_de_la_fiche(contrat: dict[str, Any] | None) -> dict[str, Any]:
    return {k: v for k, v in (contrat or {}).items() if k != "id" and k not in _COLONNES_NOM}


def _noms_du_salarie(contrat: dict[str, Any] | None) -> list[str]:
    return [str(contrat[c]) for c in _COLONNES_NOM if contrat and contrat.get(c)]


def _relire_un_bulletin(
    relecteur: RelecteurClaude,
    systeme: list[dict[str, Any]],
    contenu: dict[str, Any],
    precedent: dict[str, Any] | None,
    contrat: dict[str, Any] | None,
    vus: set[str],
) -> dict[str, Any]:
    code = code_salarie(contenu["employee_id"])
    fiche = construire_fiche(
        contenu.get("payslip_data") or {},
        precedent=precedent,
        contrat=_contrat_de_la_fiche(contrat),
        code=code,
        noms_connus=_noms_du_salarie(contrat),
    )
    reponse = relecteur.relire(systeme, fiche)
    garde = garder_signalements(reponse.signalements, fiche, code=code, vus=vus)
    return {
        "statut": "fait",
        "payslip_updated_at": contenu.get("updated_at"),
        "signalements": garde.retenus,
        "ecartes": garde.ecartes,
        "cout_usd": round(cout_usd(reponse.usage), 6),
    }


def _vus_par_salarie(lignes: list[dict[str, Any]]) -> dict[str, set[str]]:
    par_salarie: dict[str, set[str]] = {}
    for ligne in lignes:
        par_salarie.setdefault(str(ligne["employee_id"]), set()).add(str(ligne["ligne_normalisee"]))
    return par_salarie


def _traiter_societe(
    depot: DepotRelecture,
    relecteur: RelecteurClaude,
    relecture_id: str,
    company_id: str,
    lignes: list[dict[str, Any]],
    avancement: _Avancement,
    amorcer: bool = False,
) -> None:
    """Relit les bulletins d'un paquet d'une même société. Lectures groupées, une par nature.

    `amorcer` : le premier bulletin passe seul. Il écrit les règles de la société dans le
    cache ; lancés ensemble, quatre bulletins paieraient chacun cette écriture.
    """
    annee, mois = lignes[0]["year"], lignes[0]["month"]
    annee_avant, mois_avant = _mois_precedent(annee, mois)
    salaries = [str(l["employee_id"]) for l in lignes]
    contenus = {str(c["id"]): c for c in depot.contenus_des_bulletins([l["payslip_id"] for l in lignes])}
    precedents = depot.bulletins_du_mois_precedent(company_id, salaries, annee_avant, mois_avant)
    contrats = {str(c["id"]): c for c in depot.contrats(salaries)}
    vus = _vus_par_salarie(depot.vus_de_la_societe(company_id))
    systeme = blocs_systeme(depot.regles(company_id))

    def enregistrer(ligne: dict[str, Any], champs: dict[str, Any]) -> None:
        depot.enregistrer_resultat(ligne["id"], **champs)
        avancement.traites += 1
        if champs["statut"] == "echec":
            avancement.echecs += 1
        depot.modifier_relecture(relecture_id, traites=avancement.traites, echecs=avancement.echecs)

    def echouer(ligne: dict[str, Any], message: str) -> None:
        enregistrer(ligne, {"statut": "echec", "message": message})

    arret: RelectureImpossible | None = None
    with ThreadPoolExecutor(max_workers=_EN_PARALLELE) as pool:
        taches: dict[Any, dict[str, Any]] = {}
        for ligne in lignes:
            contenu = contenus.get(str(ligne["payslip_id"]))
            if contenu is None:
                echouer(ligne, _MESSAGE_BULLETIN_DISPARU)
                continue
            tache = pool.submit(
                _relire_un_bulletin,
                relecteur,
                systeme,
                contenu,
                _precedent_du_bulletin(precedents, ligne["employee_id"], ligne.get("contract_period_id")),
                contrats.get(str(ligne["employee_id"])),
                vus.get(str(ligne["employee_id"]), set()),
            )
            taches[tache] = ligne
            if amorcer:
                amorcer = False
                while not wait([tache], timeout=_BATTEMENT_SECONDES).done:
                    depot.modifier_relecture(relecture_id)

        restantes = set(taches)
        while restantes:
            finies, restantes = wait(restantes, timeout=_BATTEMENT_SECONDES, return_when=FIRST_COMPLETED)
            if not finies:
                depot.modifier_relecture(relecture_id)
                continue
            for tache in finies:
                ligne = taches[tache]
                try:
                    enregistrer(ligne, tache.result())
                except RelectureImpossible as exc:
                    if exc.fatale:
                        arret = arret or exc
                        for reste in restantes:
                            reste.cancel()
                    else:
                        echouer(ligne, exc.message)
                except Exception:
                    logger.exception("Relecture IA : échec sur un bulletin")
                    echouer(ligne, "Ce bulletin n'a pas pu être relu. Relancez la relecture pour le reprendre.")
    if arret is not None:
        raise arret


def _message_de_fin(fait: int, echecs: int, points: int, cout: float) -> str:
    bilan = f"{pluriel(fait, 'bulletin relu', 'bulletins relus')}, {pluriel(points, 'point')} à regarder."
    if echecs == 1:
        bilan += " 1 bulletin n'a pas pu être relu : relancez pour le reprendre."
    elif echecs > 1:
        bilan += f" {echecs} bulletins n'ont pas pu être relus : relancez pour les reprendre."
    return f"{bilan} {phrase_cout_reel(cout)}"


def _clore(depot: DepotRelecture, relecture_id: str) -> None:
    resultats = depot.resultats_de_la_relecture(relecture_id)
    fait = sum(1 for r in resultats if r.get("statut") == "fait")
    echecs = sum(1 for r in resultats if r.get("statut") == "echec")
    points = sum(len(r.get("signalements") or []) for r in resultats if r.get("statut") == "fait")
    cout = sum(float(r.get("cout_usd") or 0) for r in resultats)
    depot.modifier_relecture(
        relecture_id,
        statut="terminee" if fait > 0 or echecs == 0 else "echec",
        traites=fait + echecs,
        echecs=echecs,
        points=points,
        cout_reel_usd=round(cout, 4),
        message=_message_de_fin(fait, echecs, points, cout),
        termine_at=datetime.now(UTC).isoformat(),
    )
    logger.info(
        "Relecture IA %s terminée : %s relus, %s échecs, %s points, %.4f $ (%s).",
        relecture_id, fait, echecs, points, cout, MODELE,
    )


def _arreter(depot: DepotRelecture, relecture_id: str, message: str) -> None:
    cout = sum(float(r.get("cout_usd") or 0) for r in depot.resultats_de_la_relecture(relecture_id))
    depot.modifier_relecture(
        relecture_id,
        statut="echec",
        cout_reel_usd=round(cout, 4),
        message=f"{message} {phrase_cout_reel(cout)}" if cout > 0 else message,
        termine_at=datetime.now(UTC).isoformat(),
    )


def executer(
    relecture_id: str,
    depot: DepotRelecture | None = None,
    relecteur: RelecteurClaude | None = None,
) -> None:
    """Tâche de fond. Reprend là où la base en est : les lignes encore à faire."""
    depot = depot or DepotRelecture()
    relecteur = relecteur or RelecteurClaude()
    relecture = depot.relecture(relecture_id)
    if relecture is None or relecture.get("statut") != "en_cours":
        return
    try:
        deja = depot.resultats_de_la_relecture(relecture_id)
        avancement = _Avancement(
            traites=sum(1 for r in deja if r.get("statut") in ("fait", "echec")),
            echecs=sum(1 for r in deja if r.get("statut") == "echec"),
        )
        amorcees: set[str] = set()
        while True:
            paquet = depot.bulletins_a_traiter(relecture_id, _TAILLE_PAQUET)
            if not paquet:
                break
            par_societe: dict[str, list[dict[str, Any]]] = {}
            for ligne in paquet:
                par_societe.setdefault(str(ligne["company_id"]), []).append(ligne)
            for company_id, lignes in par_societe.items():
                _traiter_societe(
                    depot, relecteur, relecture_id, company_id, lignes, avancement,
                    amorcer=company_id not in amorcees,
                )
                amorcees.add(company_id)
        _clore(depot, relecture_id)
    except RelectureImpossible as exc:
        _arreter(depot, relecture_id, exc.message)
    except Exception:
        logger.exception("Relecture IA %s interrompue", relecture_id)
        _arreter(depot, relecture_id, _MESSAGE_INTERROMPUE)


def relire_en_lecture_seule(
    payslip_ids: list[str],
    depot: DepotRelecture | None = None,
    relecteur: RelecteurClaude | None = None,
) -> list[dict[str, Any]]:
    """Pour le banc d'essai : relit sans rien écrire, bulletin après bulletin."""
    depot = depot or DepotRelecture()
    relecteur = relecteur or RelecteurClaude()
    resultats: list[dict[str, Any]] = []
    for contenu in depot.contenus_des_bulletins(payslip_ids):
        employe = str(contenu["employee_id"])
        company_id = str(contenu["company_id"])
        annee, mois = _mois_precedent(contenu["year"], contenu["month"])
        precedents = depot.bulletins_du_mois_precedent(company_id, [employe], annee, mois)
        contrat = next(iter(depot.contrats([employe])), None)
        vus = _vus_par_salarie(depot.vus_de_la_societe(company_id)).get(employe, set())
        try:
            resultat = _relire_un_bulletin(
                relecteur,
                blocs_systeme(depot.regles(company_id)),
                contenu,
                _precedent_du_bulletin(precedents, employe, contenu.get("contract_period_id")),
                contrat,
                vus,
            )
        except RelectureImpossible as exc:
            resultat = {"statut": "echec", "message": exc.message, "signalements": [], "cout_usd": 0.0}
        resultats.append({"payslip_id": str(contenu["id"]), **resultat})
    return resultats


def _derniere_par_bulletin(resultats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    derniers: dict[str, dict[str, Any]] = {}
    for ligne in resultats:
        pid = str(ligne["payslip_id"])
        if pid not in derniers or str(ligne.get("termine_at") or "") > str(
            derniers[pid].get("termine_at") or ""
        ):
            derniers[pid] = ligne
    return list(derniers.values())


def _nom_affiche(employe: dict[str, Any] | None) -> str:
    if not employe:
        return "Salarié"
    nom = employe.get("nom_usage") or employe.get("last_name") or ""
    return f"{employe.get('first_name') or ''} {nom}".strip() or "Salarié"


def lire_a_regarder(
    company_id: str, year: int, month: int, depot: DepotRelecture | None = None
) -> dict[str, Any]:
    """Les points de la société active, plafonnés, avec le nom des salariés."""
    depot = depot or DepotRelecture()
    resultats = _derniere_par_bulletin(depot.resultats_du_mois(company_id, year, month))
    versions = {str(b["id"]): b.get("updated_at") for b in depot.bulletins_du_mois([company_id], year, month)}
    relus = [r for r in resultats if str(r["payslip_id"]) in versions]
    vus = _vus_par_salarie(depot.vus_de_la_societe(company_id))

    points: list[dict[str, Any]] = []
    for ligne in relus:
        employe = str(ligne["employee_id"])
        for signalement in ligne.get("signalements") or []:
            if normaliser_ligne(signalement.get("ligne", "")) in vus.get(employe, set()):
                continue
            points.append(
                {
                    "bulletin_relu_id": ligne["id"],
                    "payslip_id": ligne["payslip_id"],
                    "employee_id": employe,
                    "gravite": signalement.get("gravite"),
                    "ligne": signalement.get("ligne"),
                    "raison": signalement.get("raison"),
                    "bulletin_modifie_depuis": not meme_version(
                        versions.get(str(ligne["payslip_id"])), ligne.get("payslip_updated_at")
                    ),
                }
            )

    gardes, autres = appliquer_plafond(points, len(relus))
    noms = {str(e["id"]): e for e in depot.noms_des_salaries([p["employee_id"] for p in gardes])}
    for point in gardes:
        point["nom"] = _nom_affiche(noms.get(point["employee_id"]))
    return {
        "relecture_faite": bool(relus),
        "relu_le": max((str(r.get("termine_at") or "") for r in relus), default=None) or None,
        "points": gardes,
        "autres_points": autres,
    }


def marquer_vu(
    company_id: str,
    user_id: str,
    bulletin_relu_id: str,
    ligne: str,
    depot: DepotRelecture | None = None,
) -> None:
    depot = depot or DepotRelecture()
    relu = depot.bulletin_relu(bulletin_relu_id, company_id)
    if relu is None:
        raise PointIntrouvable
    cle = normaliser_ligne(ligne)
    signalement = next(
        (s for s in relu.get("signalements") or [] if normaliser_ligne(s.get("ligne", "")) == cle),
        None,
    )
    if signalement is None:
        raise PointIntrouvable
    depot.enregistrer_vu(
        {
            "company_id": company_id,
            "employee_id": relu["employee_id"],
            "ligne_normalisee": cle,
            "ligne": signalement.get("ligne"),
            "raison": signalement.get("raison"),
            "year": relu.get("year"),
            "month": relu.get("month"),
            "vu_par": user_id,
        }
    )
