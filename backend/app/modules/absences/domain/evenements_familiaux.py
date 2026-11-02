"""Durée d'un congé pour événement familial : jamais moins que la loi.

Code du travail L3142-4 (mis à jour le 14/06/2026) : la convention fixe la
durée de chaque congé, sans descendre sous les minima ci-dessous (jours
ouvrables). Sans convention configurée, ce sont ces minima qui s'appliquent.
"""

from __future__ import annotations

MINIMA_LEGAUX_JOURS: dict[str, int] = {
    "mariage_salarie": 4,
    "pacs_salarie": 4,
    "mariage_enfant": 1,
    "naissance_adoption": 3,
    # 12 jours, 14 si l'enfant avait moins de 25 ans, était lui-même parent,
    # ou pour une personne de moins de 25 ans à charge. Le compteur ouvre le
    # plus long : la RH pose les jours qui s'appliquent.
    "deces_enfant": 14,
    "deces_conjoint": 3,
    "deces_pere_mere": 3,
    "deces_frere_soeur": 3,
    "deces_beaux_parents": 3,
    "annonce_handicap_enfant": 10,
}


def duree_evenement(
    code: str,
    *,
    duree_convention: int | None,
    duree_reference: int | None,
    avec_convention: bool,
) -> int | None:
    """Jours ouverts pour cet événement, ou None s'il n'est pas proposé.

    - durée saisie pour la convention : elle, sans descendre sous la loi ;
    - événement prévu par la loi, sans durée saisie : le minimum légal ;
    - événement hors loi (grands-parents, déménagement) : seulement avec une
      convention, à la durée de la table de référence comme avant.
    """
    legal = MINIMA_LEGAUX_JOURS.get(code)
    if duree_convention is not None:
        return max(duree_convention, legal or 0)
    if legal is not None:
        return legal
    if avec_convention:
        return duree_reference
    return None
