"""Signalements DSN d'arrêt et de reprise : la liste à faire, et la génération.

Les règles sont dans `dsn_export/domain/signalements.py` ; ici, la lecture de la
base, le rangement du fichier et l'historique des exports.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.database import supabase
from app.modules.dsn_export.application.signalement_builder import construire_signalement
from app.modules.dsn_export.domain import etat_conformite
from app.modules.dsn_export.domain.evenements import MOTIF_ARRET
from app.modules.dsn_export.domain.fctu import (
    FinASignaler,
    bloc_preavis,
    fctu_depuis_mensuelle,
    fins_a_signaler,
)
from app.modules.dsn_export.domain.signalements import (
    SignalementAFaire,
    SignalementEnvoye,
    signalements_a_faire,
)
from app.modules.dsn_export.domain.usages_signalement import NATURE_FCTU
from app.modules.dsn_export.infrastructure import settings_repository
from app.modules.exports.application import commands
from app.modules.exports.infrastructure.export_dsn import generate_dsn_file, get_company_data
from app.modules.exports.infrastructure.storage import create_signed_url, upload_export_file
from app.shared.domain.effectif_seuils import effectif_retenu

EXPORT_TYPE = "dsn_signalement_arret"
BUCKET = "exports"


def _arrets(company_id: str) -> List[Dict[str, Any]]:
    return (
        supabase.table("absence_requests")
        .select("employee_id,type,selected_days,subrogation_active,arret_type,created_at")
        .eq("company_id", company_id)
        .eq("status", "validated")
        .in_("type", sorted(MOTIF_ARRET))
        .execute()
    ).data or []


def _envoyes(company_id: str) -> List[SignalementEnvoye]:
    lignes = (
        supabase.table("exports_history")
        .select("parameters,created_at")
        .eq("company_id", company_id)
        .eq("export_type", EXPORT_TYPE)
        .execute()
    ).data or []
    envoyes = []
    for ligne in lignes:
        p = ligne.get("parameters") or {}
        envoyes.append(SignalementEnvoye(
            str(p.get("employee_id")), str(p.get("nature")), str(p.get("motif")),
            date.fromisoformat(p["debut"]), date.fromisoformat(p["fin_prevue"]),
            bool(p.get("essai")), date.fromisoformat(str(ligne["created_at"])[:10]),
        ))
    return envoyes


def _depuis(company_id: str) -> Optional[date]:
    """Le 1er du mois qui suit le dernier mois de bulletins repris d'un autre logiciel."""
    lignes = (
        supabase.table("payslips")
        .select("year,month")
        .eq("company_id", company_id)
        .eq("origine", "importe")
        .order("year", desc=True)
        .order("month", desc=True)
        .limit(1)
        .execute()
    ).data or []
    if not lignes:
        return None
    annee, mois = int(lignes[0]["year"]), int(lignes[0]["month"])
    return date(annee + 1, 1, 1) if mois == 12 else date(annee, mois + 1, 1)


def _effectif(company_id: str, annee: int) -> int:
    societe = supabase.table("companies").select("*").eq("id", company_id).single().execute().data
    return effectif_retenu(societe, annee).valeur or 0


def _noms(company_id: str) -> Dict[str, str]:
    lignes = (
        supabase.table("employees").select("id,first_name,last_name").eq("company_id", company_id).execute()
    ).data or []
    return {
        str(l["id"]): f"{l.get('first_name') or ''} {l.get('last_name') or ''}".strip()
        for l in lignes
    }


def _sorties(company_id: str) -> List[Dict[str, Any]]:
    return (
        supabase.table("employee_exits")
        .select("*")
        .eq("company_id", company_id)
        .neq("status", "annulee")
        .execute()
    ).data or []


def _contrats(company_id: str) -> List[Dict[str, Any]]:
    return (
        supabase.table("employees")
        .select("id,contract_type,contract_end_date")
        .eq("company_id", company_id)
        .execute()
    ).data or []


def _bulletins(company_id: str, depuis: Optional[date]) -> Set[Tuple[str, int, int]]:
    requete = supabase.table("payslips").select("employee_id,year,month").eq("company_id", company_id)
    if depuis:
        requete = requete.gte("year", depuis.year)
    return {
        (str(l["employee_id"]), int(l["year"]), int(l["month"]))
        for l in (requete.execute().data or [])
    }


def _fins(company_id: str, aujourd_hui: date) -> List[FinASignaler]:
    depuis = _depuis(company_id)
    return fins_a_signaler(
        sorties=_sorties(company_id),
        contrats=_contrats(company_id),
        envoyes=_envoyes(company_id),
        bulletins=_bulletins(company_id, depuis),
        depuis=depuis,
        aujourd_hui=aujourd_hui,
    )


def _attente_fin(f: FinASignaler, aujourd_hui: date) -> Optional[str]:
    """Ce qui manque avant de générer la fin de contrat, ou None si elle est prête."""
    if f.fin > aujourd_hui:
        return (
            f"Fin prévue le {f.fin:%d/%m/%Y} : le fichier se génère après la sortie "
            "et son bulletin."
        )
    if not f.bulletin_pret:
        return (
            "Bulletin du mois de sortie pas encore calculé : calculez-le, la fin de "
            "contrat reprend le solde de tout compte."
        )
    return None


def _ligne_fin(f: FinASignaler, noms: Dict[str, str], aujourd_hui: date) -> Dict[str, Any]:
    return {
        "employee_id": f.employee_id,
        "salarie": noms.get(f.employee_id, ""),
        "nature": NATURE_FCTU,
        "motif": "",
        "debut": f.fin.isoformat(),
        "fin_prevue": f.fin.isoformat(),
        "subrogation": False,
        "connu_le": f.fin.isoformat(),
        "a_deposer_avant": f.a_deposer_avant.isoformat(),
        "date_reprise": None,
        "en_retard": f.a_deposer_avant < aujourd_hui,
        "a_verifier": _attente_fin(f, aujourd_hui),
    }


def _a_faire(company_id: str, aujourd_hui: date) -> List[SignalementAFaire]:
    par_salarie: Dict[str, List[Dict[str, Any]]] = {}
    for arret in _arrets(company_id):
        par_salarie.setdefault(str(arret["employee_id"]), []).append(arret)
    return signalements_a_faire(
        par_salarie,
        _envoyes(company_id),
        depuis=_depuis(company_id),
        effectif=_effectif(company_id, aujourd_hui.year),
    )


def _iso(jour: Optional[date]) -> Optional[str]:
    return jour.isoformat() if jour else None


def _ligne(s: SignalementAFaire, noms: Dict[str, str], aujourd_hui: date) -> Dict[str, Any]:
    return {
        "employee_id": s.employee_id,
        "salarie": noms.get(s.employee_id, ""),
        "nature": s.nature,
        "motif": s.motif,
        "debut": _iso(s.debut),
        "fin_prevue": _iso(s.fin_prevue),
        "subrogation": s.subrogation,
        "connu_le": _iso(s.connu_le),
        "a_deposer_avant": _iso(s.a_deposer_avant),
        "date_reprise": _iso(s.date_reprise),
        "en_retard": s.a_deposer_avant < aujourd_hui,
        "a_verifier": s.a_verifier,
    }


def lister(company_id: str, *, aujourd_hui: Optional[date] = None) -> Dict[str, Any]:
    """Les signalements à faire, du plus pressé au moins pressé, et ceux déjà générés."""
    jour = aujourd_hui or date.today()
    noms = _noms(company_id)
    faits = [
        {
            "employee_id": e.employee_id,
            "salarie": noms.get(e.employee_id, ""),
            "nature": e.nature,
            "motif": e.motif,
            "debut": e.debut.isoformat(),
            "fin_prevue": e.fin_prevue.isoformat(),
            "essai": e.essai,
            "genere_le": e.genere_le.isoformat(),
        }
        for e in sorted(_envoyes(company_id), key=lambda e: e.genere_le, reverse=True)
    ]
    a_faire = [_ligne(s, noms, jour) for s in _a_faire(company_id, jour)]
    a_faire += [_ligne_fin(f, noms, jour) for f in _fins(company_id, jour)]
    a_faire.sort(key=lambda ligne: (ligne["a_deposer_avant"], ligne["employee_id"]))
    return {"a_faire": a_faire, "faits": faits}


def _fichier(company_id: str, s: SignalementAFaire, essai: bool) -> str:
    employee = supabase.table("employees").select("*").eq("id", s.employee_id).single().execute().data
    return construire_signalement(
        get_company_data(company_id),
        employee,
        s,
        settings=settings_repository.charger(company_id),
        essai=essai,
        constitue_le=date.today(),
    )


def generer(
    company_id: str,
    user_id: str,
    *,
    employee_id: str,
    nature: str,
    debut: str,
    essai: bool,
    aujourd_hui: Optional[date] = None,
) -> Dict[str, Any]:
    """Génère, range et historise le fichier d'un signalement encore à faire."""
    jour = aujourd_hui or date.today()
    if not essai and not etat_conformite.SIGNALEMENTS_DEPOSABLES:
        raise ValueError(etat_conformite.RAISON_SIGNALEMENTS)
    if nature == NATURE_FCTU:
        return _generer_fin(company_id, user_id, employee_id=employee_id, fin=debut, essai=essai, jour=jour)
    s = next(
        (
            x for x in _a_faire(company_id, jour)
            if x.employee_id == employee_id and x.nature == nature and x.debut.isoformat() == debut
        ),
        None,
    )
    if s is None:
        raise ValueError("Ce signalement n'est plus à faire : rechargez la liste.")
    return _ranger(
        company_id,
        user_id,
        _fichier(company_id, s, essai).encode("iso-8859-15"),
        essai=essai,
        a_deposer_avant=s.a_deposer_avant,
        parametres={
            "employee_id": s.employee_id,
            "nature": s.nature,
            "motif": s.motif,
            "debut": s.debut.isoformat(),
            "fin_prevue": s.fin_prevue.isoformat(),
            "subrogation": s.subrogation,
            "date_reprise": _iso(s.date_reprise),
            "essai": essai,
        },
    )


def _generer_fin(
    company_id: str, user_id: str, *, employee_id: str, fin: str, essai: bool, jour: date
) -> Dict[str, Any]:
    """La fin de contrat : la DSN du mois de sortie du salarié, passée en nature 07."""
    f = next(
        (x for x in _fins(company_id, jour) if x.employee_id == employee_id and x.fin.isoformat() == fin),
        None,
    )
    if f is None:
        raise ValueError("Ce signalement n'est plus à faire : rechargez la liste.")
    attente = _attente_fin(f, jour)
    if attente:
        raise ValueError(attente)
    sortie = next((s for s in _sorties(company_id) if str(s.get("employee_id")) == employee_id), None)
    mensuelle = generate_dsn_file(
        company_id, f"{f.fin:%Y-%m}", "dsn_mensuelle_normale", [employee_id], essai=essai
    )
    texte = fctu_depuis_mensuelle(
        mensuelle.decode("iso-8859-15"), mois_solde=f.fin, preavis=bloc_preavis(sortie)
    )
    return _ranger(
        company_id,
        user_id,
        texte.encode("iso-8859-15"),
        essai=essai,
        a_deposer_avant=f.a_deposer_avant,
        parametres={
            "employee_id": employee_id,
            "nature": NATURE_FCTU,
            "motif": "",
            "debut": f.fin.isoformat(),
            "fin_prevue": f.fin.isoformat(),
            "subrogation": False,
            "date_reprise": None,
            "essai": essai,
        },
    )


def _ranger(
    company_id: str,
    user_id: str,
    contenu: bytes,
    *,
    essai: bool,
    a_deposer_avant: date,
    parametres: Dict[str, Any],
) -> Dict[str, Any]:
    """Range le fichier, l'inscrit à l'historique et dit quoi en faire."""
    prefixe = "dsn_essai_signalement" if essai else "dsn_signalement"
    filename = (
        f"{prefixe}_{parametres['nature']}_{parametres['debut']}_{datetime.now():%Y%m%d%H%M%S}.dsn"
    )
    chemin = upload_export_file(
        BUCKET,
        f"exports/{company_id}/{EXPORT_TYPE}/{filename}",
        contenu,
        "text/plain; charset=iso-8859-15",
    )
    export_id = commands.record_export_history({
        "company_id": company_id,
        "export_type": EXPORT_TYPE,
        "period": parametres["debut"][:7],
        "parameters": parametres,
        "file_paths": [chemin],
        "report": {},
        "status": "generated",
        "generated_by": user_id,
    })
    message = (
        "Fichier d'essai : déposez-le en mode test sur net-entreprises.fr. "
        "Il ne vaut pas signalement."
        if essai
        else f"Déposez-le sur net-entreprises.fr avant le {a_deposer_avant:%d/%m/%Y}."
    )
    return {
        "export_id": export_id,
        "filename": filename,
        "download_url": create_signed_url(chemin, 3600),
        "message": message,
    }
