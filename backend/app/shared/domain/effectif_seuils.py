"""Effectif retenu pour les seuils de paie (11, 20 et 50 salariés).

La loi retient pour une année civile la moyenne des effectifs de chaque mois
de l'année précédente (CSS L130-1, R130-1 ; BOSS « Effectif ») ; l'Urssaf la
communique chaque année (compte rendu n° 118 des effectifs annuels). Martine
ne la recalcule pas : la gestionnaire la saisit par année, dans
`companies.settings.effectif_seuils` (`{"2026": 5}`).

`companies.effectif` n'est que le nombre de comptes de la société, tenu par un
déclencheur de la base (admins, RH et salariés partis compris) : il ne sert
plus qu'en dernier recours, et le bulletin le signale. Avant le 11/10/2026, le
moteur le lisait directement (Colorplast vue à 19 pour environ 5 salariés).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

CLE_EFFECTIF_SEUILS = "effectif_seuils"
CODE_ALERTE_EFFECTIF = "effectif_annee_non_saisi"
CODE_ALERTE_FRANCHISSEMENT = "effectif_seuil_franchi_moins_de_cinq_ans"

#: Seuils lus par le moteur : formation, versement mobilité et dispositif
#: d'apprentissage (11), déduction heures sup et repos compensateur (20),
#: FNAL, réduction générale et prime de partage de la valeur (50).
_PALIERS = ((50, "50 et plus"), (20, "de 20 à 49"), (11, "de 11 à 19"))


@dataclass(frozen=True)
class EffectifRetenu:
    valeur: int
    annee: int
    #: Année saisie reprise ; None = nombre de comptes de la société.
    annee_source: int | None

    @property
    def saisi_pour_l_annee(self) -> bool:
        return self.annee_source == self.annee


def _entier(valeur: Any) -> int | None:
    if isinstance(valeur, bool):
        return None
    if isinstance(valeur, int):
        return valeur if valeur >= 0 else None
    if isinstance(valeur, str) and valeur.strip().isdigit():
        return int(valeur.strip())
    return None


def effectifs_saisis(company: Mapping[str, Any] | None) -> dict[int, int]:
    """Les effectifs saisis, par année ; les valeurs illisibles sont ignorées."""
    reglages = (company or {}).get("settings")
    saisis = reglages.get(CLE_EFFECTIF_SEUILS) if isinstance(reglages, Mapping) else None
    if not isinstance(saisis, Mapping):
        return {}
    resultat: dict[int, int] = {}
    for annee, valeur in saisis.items():
        annee_int, valeur_int = _entier(str(annee)), _entier(valeur)
        if annee_int is not None and valeur_int is not None:
            resultat[annee_int] = valeur_int
    return resultat


def effectif_retenu(company: Mapping[str, Any] | None, annee: int) -> EffectifRetenu:
    """L'effectif de l'année ; sinon la dernière année saisie avant, sinon la
    plus proche après ; sans aucune saisie, le nombre de comptes."""
    saisis = effectifs_saisis(company)
    if annee in saisis:
        return EffectifRetenu(saisis[annee], annee, annee)
    avant = [a for a in saisis if a < annee]
    apres = [a for a in saisis if a > annee]
    source = max(avant) if avant else (min(apres) if apres else None)
    if source is not None:
        return EffectifRetenu(saisis[source], annee, source)
    comptes = _entier((company or {}).get("effectif")) or 0
    return EffectifRetenu(comptes, annee, None)


def palier_effectif(valeur: int) -> str:
    for seuil, libelle in _PALIERS:
        if valeur >= seuil:
            return libelle
    return "moins de 11"


def alerte_effectif(retenu: EffectifRetenu) -> dict[str, Any] | None:
    """L'alerte du bulletin quand l'effectif de son année n'est pas saisi."""
    if retenu.saisi_pour_l_annee:
        return None
    a = retenu.annee
    saisir = (
        f"Saisissez l'effectif {a} (moyenne de {a - 1}, communiquée par l'Urssaf) "
        "dans les paramètres de paie de la société, puis recalculez."
    )
    if retenu.annee_source is None:
        message = (
            f"Effectif {a} non saisi : Martine a compté les comptes de la société "
            f"({retenu.valeur}), qui ne sont pas l'effectif légal. {saisir} "
            "À vérifier avant de valider ce bulletin."
        )
    else:
        message = (
            f"Effectif {a} non saisi : Martine reprend celui de "
            f"{retenu.annee_source} ({retenu.valeur}). {saisir}"
        )
    return {"code": CODE_ALERTE_EFFECTIF, "message": message}


def alerte_franchissement_seuil(
    company: Mapping[str, Any] | None, annee: int
) -> dict[str, Any] | None:
    """Alerte quand l'effectif saisi franchit un seuil depuis moins de cinq ans.

    CSS L130-1, II : un seuil atteint ou dépassé n'est pris en compte qu'après
    cinq années civiles consécutives (sources lues : Legisocial, commentaires du
    BOSS ; Légifrance et le BOSS ne s'ouvrent pas d'ici). La clé d'année porte la
    moyenne de l'année précédente : on regarde les quatre saisies d'avant. Martine
    ne neutralise rien d'elle-même, l'historique des années passées n'étant pas
    saisi : elle applique l'effectif saisi et le dit. Saisir l'effectif à retenir
    est la réponse.
    """
    saisis = effectifs_saisis(company)
    effectif = saisis.get(annee)
    if effectif is None:
        return None
    for seuil in (50, 20, 11):
        if effectif < seuil:
            continue
        sous_le_seuil = sorted(
            a for a in range(annee - 4, annee) if a in saisis and saisis[a] < seuil
        )
        if sous_le_seuil:
            derniere = sous_le_seuil[-1]
            return {
                "code": CODE_ALERTE_FRANCHISSEMENT,
                "message": (
                    f"Seuil de {seuil} salariés atteint : effectif {annee} saisi à "
                    f"{effectif}, {saisis[derniere]} en {derniere}. Un seuil ne compte "
                    "qu'après cinq années civiles consécutives (CSS L130-1) : Martine "
                    "applique pourtant l'effectif saisi. Vérifiez l'effectif à retenir "
                    "dans les paramètres de paie avant de valider."
                ),
            }
    return None


def effectifs_avec(
    settings: Mapping[str, Any] | None, annee: int, valeur: int
) -> dict[str, int]:
    """Les effectifs saisis, avec celui de `annee` posé ou remplacé."""
    anciens = settings.get(CLE_EFFECTIF_SEUILS) if isinstance(settings, Mapping) else None
    fusion = dict(anciens) if isinstance(anciens, Mapping) else {}
    fusion[str(annee)] = valeur
    return fusion
