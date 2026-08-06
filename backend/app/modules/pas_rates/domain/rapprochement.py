"""Rapprochement des taux lus dans un fichier avec les salariés de la base.

Le NIR est la clé sûre, mais il n'est pas toujours saisi des deux côtés et un
export peut le porter sur quinze chiffres là où la base en garde treize. On
retombe alors sur le nom et le prénom normalisés. Un individu non rapproché est
signalé, jamais créé : la création de fiche a ses propres règles ailleurs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from app.modules.pas_rates.domain.extraction import TauxFichier, normaliser_nom
from app.modules.pas_rates.domain.model import Apercu, LigneApercu

TOLERANCE_TAUX = 0.005


def cle_nir(nir: str) -> str:
    """Treize premiers chiffres : dénominateur commun entre base et exports."""
    compact = "".join(c for c in (nir or "") if not c.isspace())
    return compact[:13] if len(compact) >= 13 else compact


def cle_nom(nom: str, prenom: str) -> str:
    """Nom complet normalisé, prénom réduit au premier vocable."""
    premier_prenom = normaliser_nom(prenom).split(" ")[0] if prenom else ""
    return f"{normaliser_nom(nom)}|{premier_prenom}"


def _index_salaries(salaries: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    for salarie in salaries:
        nir = cle_nir(str(salarie.get("nir") or ""))
        if nir:
            index.setdefault(f"nir:{nir}", salarie)
        index.setdefault(
            "nom:" + cle_nom(str(salarie.get("last_name") or ""), str(salarie.get("first_name") or "")),
            salarie,
        )
    return index


def trouver_salarie(
    ligne: TauxFichier, index: Dict[str, Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    nir = cle_nir(ligne.nir)
    if nir:
        trouve = index.get(f"nir:{nir}")
        if trouve:
            return trouve
    return index.get("nom:" + cle_nom(ligne.nom, ligne.prenom))


def taux_courant(salarie: Dict[str, Any]) -> Dict[str, Any]:
    specificites = salarie.get("specificites_paie") or {}
    if not isinstance(specificites, dict):
        return {}
    bloc = specificites.get("prelevement_a_la_source") or {}
    return bloc if isinstance(bloc, dict) else {}


def est_dans_l_effectif(salarie: Dict[str, Any]) -> bool:
    return str(salarie.get("employment_status") or "").lower() in ("actif", "en_sortie")


def _nature(actuel: Dict[str, Any], ligne: TauxFichier) -> str:
    taux_avant = actuel.get("taux")
    if taux_avant is None:
        return "nouveau"
    if ligne.taux is None:
        return "inchange"
    if abs(float(taux_avant) - ligne.taux) > TOLERANCE_TAUX:
        return "modifie"
    if (actuel.get("type_taux") or None) != (ligne.type_taux or None):
        return "modifie"
    return "inchange"


def construire_apercu(
    lignes_fichier: Sequence[TauxFichier],
    salaries: Sequence[Dict[str, Any]],
    *,
    periode: str,
    siren: str,
    fichier: str,
    source: str,
) -> Apercu:
    index = _index_salaries(salaries)
    apercu = Apercu(periode=periode, siren=siren, fichier=fichier, source=source)
    vus: set[str] = set()

    for ligne in lignes_fichier:
        salarie = trouver_salarie(ligne, index)
        if salarie is None:
            apercu.lignes.append(
                LigneApercu(
                    employee_id=None,
                    nom=ligne.nom,
                    prenom=ligne.prenom,
                    taux_actuel=None,
                    taux_fichier=ligne.taux,
                    type_actuel=None,
                    type_fichier=ligne.type_taux,
                    identifiant_fichier=ligne.identifiant_taux,
                    nature="non_rapproche",
                )
            )
            continue

        employee_id = str(salarie.get("id"))
        if employee_id in vus:
            # Un même salarié apparaît deux fois dans le fichier (deux contrats) :
            # le premier versement retenu fait foi, le second est ignoré.
            continue
        vus.add(employee_id)

        actuel = taux_courant(salarie)
        taux_avant = actuel.get("taux")
        # Un fichier couvre le mois qu'il déclare : il contient donc encore les
        # salariés partis depuis. Leur taux n'a plus d'usage, on ne le touche pas.
        nature = (
            _nature(actuel, ligne)
            if est_dans_l_effectif(salarie)
            else "hors_effectif"
        )
        apercu.lignes.append(
            LigneApercu(
                employee_id=employee_id,
                nom=str(salarie.get("last_name") or ligne.nom),
                prenom=str(salarie.get("first_name") or ligne.prenom),
                taux_actuel=None if taux_avant is None else float(taux_avant),
                taux_fichier=ligne.taux,
                type_actuel=actuel.get("type_taux") or None,
                type_fichier=ligne.type_taux,
                identifiant_fichier=ligne.identifiant_taux,
                nature=nature,
            )
        )

    manquants = [
        s
        for s in salaries
        if str(s.get("id")) not in vus and est_dans_l_effectif(s)
    ]
    if manquants:
        apercu.avertissements.append(
            f"{len(manquants)} salarié(s) de la société ne figurent pas dans le fichier : "
            "leur taux est laissé tel quel."
        )
    return apercu


def lignes_a_ecrire(apercu: Apercu) -> List[LigneApercu]:
    """Les seules lignes qui donnent lieu à une écriture."""
    return [
        ligne
        for ligne in apercu.a_appliquer()
        if ligne.employee_id and ligne.taux_fichier is not None
    ]
