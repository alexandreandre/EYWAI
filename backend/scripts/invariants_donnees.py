"""
Contrôles d'intégrité des données (LECTURE SEULE).

Axe D du programme d'audit. Chaque contrôle exprime un invariant que les
données devraient respecter ; le script les compte, en montre quelques
exemples anonymisés, et sort en code 1 si un contrôle de gravité « haute »
est en défaut — de quoi le brancher en tâche planifiée.

    python -m scripts.invariants_donnees            # rapport lisible
    python -m scripts.invariants_donnees --json     # sortie machine

N'ÉCRIT JAMAIS RIEN. Aucun nom, e-mail, NIR ni salaire n'est affiché :
les exemples sont réduits à des identifiants tronqués.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

from app.core.database import supabase


@dataclass
class Constat:
    code: str
    libelle: str
    gravite: str  # haute | moyenne | basse
    nombre: int
    exemples: List[str] = field(default_factory=list)
    commentaire: str = ""


def _lignes(table: str, select: str, **filtres) -> List[Dict[str, Any]]:
    """Toutes les lignes, par pages.

    PostgREST plafonne une réponse à 1000 lignes : sans pagination, un
    contrôle d'intégrité sous-compte EN SILENCE, ce qui est pire que pas de
    contrôle du tout (première version de ce script : 1000 bulletins vus
    sur 1308, 598 jours d'absence sur 2455).
    """
    taille_page = 1000
    debut = 0
    tout: List[Dict[str, Any]] = []
    while True:
        requete = supabase.table(table).select(select)
        for colonne, valeur in filtres.items():
            if valeur is None:
                requete = requete.is_(colonne, "null")
            else:
                requete = requete.eq(colonne, valeur)
        reponse = requete.range(debut, debut + taille_page - 1).execute()
        page = list(getattr(reponse, "data", None) or [])
        tout.extend(page)
        if len(page) < taille_page:
            return tout
        debut += taille_page


def _court(identifiant: Any) -> str:
    texte = str(identifiant or "")
    return texte[:8] if texte else "?"


# ----- Contrôles -----


def controle_emails_fabriques() -> Constat:
    """Règle projet : employees.email est réel ou vide, jamais fabriqué."""
    suffixes = (".dsn-import.local", "@dsn-import.eywai.fr", "@eywai.access.local", "@users.eywai")
    fautifs = [
        ligne
        for ligne in _lignes("employees", "id, email, employment_status")
        if any((ligne.get("email") or "").lower().endswith(s) for s in suffixes)
    ]
    actifs = [
        f
        for f in fautifs
        if (f.get("employment_status") or "actif").lower()
        in ("actif", "active", "en_onboarding")
    ]
    return Constat(
        code="emails_fabriques",
        libelle="Fiches portant une adresse fabriquée dans employees.email",
        gravite="moyenne",
        nombre=len(fautifs),
        exemples=[_court(f["id"]) for f in fautifs[:5]],
        commentaire=(
            f"{len(actifs)} sur des salariés ACTIFS — ils ne sont pas "
            "invitables tant que l'adresse réelle n'est pas saisie."
        ),
    )


def controle_nir_doublons() -> Constat:
    """Un NIR ne doit pas désigner deux salariés dans la même société."""
    vus: Dict[str, List[str]] = {}
    for ligne in _lignes("employees", "id, nir, company_id"):
        nir = (ligne.get("nir") or "").strip()
        if not nir:
            continue
        cle = f"{ligne.get('company_id')}|{nir}"
        vus.setdefault(cle, []).append(str(ligne["id"]))
    doublons = {c: ids for c, ids in vus.items() if len(ids) > 1}
    return Constat(
        code="nir_doublons",
        libelle="NIR partagé par plusieurs fiches d'une même société",
        gravite="haute",
        nombre=len(doublons),
        exemples=[" + ".join(_court(i) for i in ids) for ids in list(doublons.values())[:5]],
        commentaire="Un doublon fausse le rapprochement DSN et les IJSS.",
    )


def controle_emails_partages() -> Constat:
    """Deux salariés ne doivent pas partager une adresse réelle : le lien
    d'activation donnerait à l'un l'accès au compte de l'autre."""
    suffixes = (".dsn-import.local", "@dsn-import.eywai.fr", "@eywai.access.local", "@users.eywai")
    vus: Dict[str, List[str]] = {}
    for ligne in _lignes("employees", "id, email"):
        adresse = (ligne.get("email") or "").strip().lower()
        if not adresse or any(adresse.endswith(s) for s in suffixes):
            continue
        vus.setdefault(adresse, []).append(str(ligne["id"]))
    partages = {a: ids for a, ids in vus.items() if len(ids) > 1}
    return Constat(
        code="emails_partages",
        libelle="Adresse e-mail réelle partagée par plusieurs fiches",
        gravite="haute",
        nombre=len(partages),
        exemples=[" + ".join(_court(i) for i in ids) for ids in list(partages.values())[:5]],
        commentaire="Chemin d'accès croisé aux données RH via le lien d'activation.",
    )


def controle_comptes_orphelins() -> Constat:
    """Un compte auth sans fiche salariée est un accès sans porteur."""
    lies = {
        str(ligne["user_id"])
        for ligne in _lignes("employees", "user_id")
        if ligne.get("user_id")
    }
    return Constat(
        code="comptes_lies",
        libelle="Comptes auth rattachés à une fiche salariée",
        gravite="basse",
        nombre=len(lies),
        commentaire="Repère de volumétrie ; les orphelins se comptent côté auth.users.",
    )


def controle_absences_sans_marqueur() -> Constat:
    """Les jours d'absence du planning doivent porter origine:'absence',
    sinon la garde de préservation ne les voit pas (audit axe C)."""
    types_absence = {
        "arret_maladie", "conge", "conges_payes", "rtt", "arret_at",
        "absence_non_remuneree", "absence_justifiee",
    }
    total = marques = 0
    exemples: List[str] = []
    for ligne in _lignes("employee_schedules", "employee_id, planned_calendar"):
        calendrier = ligne.get("planned_calendar") or {}
        jours = calendrier.get("calendrier_prevu") or []
        if not isinstance(jours, list):
            continue
        for jour in jours:
            if not isinstance(jour, dict) or jour.get("type") not in types_absence:
                continue
            total += 1
            if jour.get("origine") == "absence":
                marques += 1
            elif len(exemples) < 5:
                exemples.append(f"{_court(ligne.get('employee_id'))}/j{jour.get('jour')}")
    non_marques = total - marques
    return Constat(
        code="absences_sans_marqueur",
        libelle="Jours d'absence du planning sans marqueur de protection",
        gravite="haute" if non_marques else "basse",
        nombre=non_marques,
        exemples=exemples,
        commentaire=(
            f"{marques} marqués sur {total} jours d'absence — les non marqués "
            "sont effacés sans avertissement par une régénération."
        ),
    )


def controle_bulletins_statuts() -> Constat:
    """Un salarié ne voit que des bulletins validés : s'il n'y en a aucun,
    son espace est vide, ce qu'il faut savoir avant de l'inviter."""
    par_statut: Dict[str, int] = {}
    for ligne in _lignes("payslips", "id, status"):
        par_statut[str(ligne.get("status") or "?")] = (
            par_statut.get(str(ligne.get("status") or "?"), 0) + 1
        )
    valides = par_statut.get("valide", 0)
    total = sum(par_statut.values())
    return Constat(
        code="bulletins_valides",
        libelle="Bulletins au statut « validé » (seuls visibles par le salarié)",
        gravite="moyenne" if valides == 0 else "basse",
        nombre=valides,
        exemples=[f"{statut}={nombre}" for statut, nombre in sorted(par_statut.items())],
        commentaire=(
            f"{total} bulletins au total. Aucun validé ⇒ espace salarié vide."
            if valides == 0
            else ""
        ),
    )


CONTROLES: List[Callable[[], Constat]] = [
    controle_emails_fabriques,
    controle_nir_doublons,
    controle_emails_partages,
    controle_absences_sans_marqueur,
    controle_bulletins_statuts,
    controle_comptes_orphelins,
]


def executer() -> List[Constat]:
    resultats: List[Constat] = []
    for controle in CONTROLES:
        try:
            resultats.append(controle())
        except Exception as exc:  # un contrôle en panne ne masque pas les autres
            resultats.append(
                Constat(
                    code=getattr(controle, "__name__", "inconnu"),
                    libelle="Contrôle non exécuté",
                    gravite="moyenne",
                    nombre=-1,
                    commentaire=str(exc)[:200],
                )
            )
    return resultats


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--json", action="store_true", help="sortie machine")
    options = parseur.parse_args()

    constats = executer()

    if options.json:
        print(json.dumps([c.__dict__ for c in constats], ensure_ascii=False, indent=2))
    else:
        print("\nINVARIANTS DE DONNÉES — lecture seule\n" + "=" * 60)
        for c in constats:
            marque = {"haute": "⚠ ", "moyenne": "· ", "basse": "  "}.get(c.gravite, "  ")
            print(f"\n{marque}[{c.gravite.upper():7}] {c.libelle}")
            print(f"    nombre : {c.nombre}")
            if c.exemples:
                print(f"    exemples : {', '.join(c.exemples)}")
            if c.commentaire:
                print(f"    {c.commentaire}")
        print()

    en_defaut = [c for c in constats if c.gravite == "haute" and c.nombre > 0]
    return 1 if en_defaut else 0


if __name__ == "__main__":
    sys.exit(main())
