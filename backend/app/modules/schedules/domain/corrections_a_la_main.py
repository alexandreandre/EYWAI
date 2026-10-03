"""Refaire un import : les jours corrigés à la main depuis le premier import.

Un relevé déjà validé peut être relu (lecteur corrigé, salarié sauté) ; ses
jours ne doivent jamais écraser en silence ce que la gestionnaire a corrigé
au calendrier entre-temps. Pour chaque salarié et chaque jour que relit le
fichier, on compare :

- ce qu'avait écrit le lot précédent (son aperçu validé, `preview_json`) ;
- ce qui est au calendrier réel aujourd'hui ;
- ce que relit le fichier.

Le calendrier diffère de ce qu'avait écrit l'import : quelqu'un l'a corrigé.
Un jour que l'import n'avait pas écrit et qui porte des heures au calendrier a
été saisi hors de l'import. Dans les deux cas, si le fichier relu dit autre
chose que le calendrier, c'est une correction à la main : la relecture la
montre, et l'enregistrement garde la valeur du calendrier.

Pourquoi pas seulement « le calendrier diffère du fichier » : après une
correction du lecteur, toutes les heures mal lues par l'ancien diffèrent du
fichier relu ; les garder rendrait la relecture inutile. Sans lot précédent
connu (`ecrits_par_import` vide), la règle devient exactement celle-là : tout
jour non vide du calendrier que le fichier contredit est gardé.

Deux écritures d'une même valeur ne sont pas une correction : l'écran réécrit
« weekend » en « repos » et « conge » en « conges_payes » sans que personne ne
corrige rien (mesuré sur la base de test le 03/10/2026), et un jour sans
heures, travaillé ou de repos, est un jour vide.

Module pur : l'appelant fournit les trois relevés, indexés par
`(employee_id, annee, mois, jour)`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from app.modules.schedules.domain.rules import coerce_jour

Cle = tuple[str, int, int, int]

#: Écritures d'un même type de jour (l'écran et l'import ne nomment pas pareil).
_MEME_TYPE: dict[str, str] = {
    "": "travail",
    "work": "travail",
    "weekend": "repos",
    "conge": "conges_payes",
    "cp": "conges_payes",
}
#: Un jour sans heures de ces types est un jour vide.
_TYPES_VIDES = frozenset({"travail", "repos"})


@dataclass(frozen=True)
class ValeurJour:
    heures: float | None
    type: str | None

    def to_dict(self) -> dict[str, Any]:
        return {"heures": self.heures, "type": self.type}


@dataclass(frozen=True)
class CorrectionALaMain:
    employee_id: str
    annee: int
    mois: int
    jour: int
    #: Ce qu'avait écrit le lot précédent ; None : il n'avait rien écrit ce jour-là.
    import_precedent: ValeurJour | None
    #: Ce qui est au calendrier ; None : le jour est vide.
    calendrier: ValeurJour | None
    #: Ce que relit le fichier.
    fichier: ValeurJour

    @property
    def cle(self) -> Cle:
        return (self.employee_id, self.annee, self.mois, self.jour)

    def to_dict(self) -> dict[str, Any]:
        return {
            "employee_id": self.employee_id,
            "annee": self.annee,
            "mois": self.mois,
            "jour": self.jour,
            "import_precedent": (
                self.import_precedent.to_dict() if self.import_precedent else None
            ),
            "calendrier": self.calendrier.to_dict() if self.calendrier else None,
            "fichier": self.fichier.to_dict(),
        }


def _famille(type_: str | None) -> str:
    t = (type_ or "travail").strip().lower()
    return _MEME_TYPE.get(t, t)


def _signature(valeur: ValeurJour | None) -> tuple[float | None, str] | None:
    """Ce qui compte d'un jour ; None pour un jour vide."""
    if valeur is None:
        return None
    famille = _famille(valeur.type)
    if valeur.heures is None:
        return None if famille in _TYPES_VIDES else (None, famille)
    return (round(float(valeur.heures), 2), famille)


def _calendrier_ou_vide(valeur: ValeurJour | None) -> ValeurJour | None:
    return None if _signature(valeur) is None else valeur


def corrections_a_la_main(
    jours_du_fichier: Mapping[Cle, ValeurJour],
    ecrits_par_import: Mapping[Cle, ValeurJour],
    en_base: Mapping[Cle, ValeurJour],
) -> list[CorrectionALaMain]:
    """Les jours du fichier dont le calendrier a été corrigé depuis l'import et
    qui le contredisent ; rangés par salarié puis par date."""
    corrections: list[CorrectionALaMain] = []
    for cle, fichier in jours_du_fichier.items():
        calendrier = _signature(en_base.get(cle))
        if cle in ecrits_par_import:
            corrige = calendrier != _signature(ecrits_par_import[cle])
        else:
            corrige = calendrier is not None
        if not corrige or calendrier == _signature(fichier):
            continue
        employee_id, annee, mois, jour = cle
        corrections.append(
            CorrectionALaMain(
                employee_id=employee_id,
                annee=annee,
                mois=mois,
                jour=jour,
                import_precedent=ecrits_par_import.get(cle),
                calendrier=_calendrier_ou_vide(en_base.get(cle)),
                fichier=fichier,
            )
        )
    return sorted(corrections, key=lambda c: c.cle)


def jours_du_calendrier_reel(
    employee_id: str, annee: int, mois: int, calendrier_reel: Iterable[Any]
) -> dict[Cle, ValeurJour]:
    """Le réel stocké d'un salarié pour un mois (`actual_hours.calendrier_reel`)."""
    jours: dict[Cle, ValeurJour] = {}
    for entree in calendrier_reel or []:
        if not isinstance(entree, dict):
            continue
        jour = coerce_jour(entree.get("jour"))
        if jour is None:
            continue
        heures = entree.get("heures_faites")
        jours[(employee_id, annee, mois, jour)] = ValeurJour(
            heures=None if heures is None else float(heures),
            type=entree.get("type"),
        )
    return jours


__all__ = [
    "Cle",
    "CorrectionALaMain",
    "ValeurJour",
    "corrections_a_la_main",
    "jours_du_calendrier_reel",
]
