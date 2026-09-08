"""Heures supplémentaires conjoncturelles lues sur un bulletin.

Pourquoi ce module : l'écran d'édition d'un bulletin laisse corriger la
quantité d'heures supplémentaires ligne à ligne, mais ne recalcule ni les
cotisations ni le net. La correction n'a de sens que si elle est redonnée au
moteur, qui refait alors tout le bulletin.

Le moteur accepte ces heures en entrée déclarative
(`saisie_du_mois["heures_supplementaires_conjoncturelles"]` et `…_50`). Il les
applique **par paire** : dès qu'un palier est déclaré, l'autre l'est aussi et
prend la valeur transmise, fût-elle nulle
(cf. `calcul_brut`, application des heures supplémentaires déclarées). Ne
redéclarer que le palier corrigé ferait donc disparaître l'autre — 3,5 h à
50 % perdues sans un mot. D'où une lecture qui rend toujours les deux.

Deux lignes sont volontairement écartées :

- les heures supplémentaires **structurelles**, qui viennent de l'horaire
  contractuel (39 h) et non d'une variable du mois ;
- les heures **complémentaires** du temps partiel, qui relèvent d'un autre
  régime.

Le palier se lit sur le **taux**, pas sur le pourcentage écrit dans le
libellé : une société peut majorer à 10 % puis 25 %, auquel cas « 25 % »
désigne le second palier et non le premier.
"""

from __future__ import annotations

from typing import Any

_MOT_HEURES_SUP = "heures suppl"
_MOT_STRUCTURELLES = "structurelle"


def _est_ligne_heures_sup_conjoncturelle(ligne: Any) -> bool:
    if not isinstance(ligne, dict) or ligne.get("is_sous_total"):
        return False
    libelle = str(ligne.get("libelle") or "").lower()
    if _MOT_STRUCTURELLES in libelle:
        return False
    return _MOT_HEURES_SUP in libelle


def _nombre(valeur: Any) -> float | None:
    """Ne convertit que ce qui est déjà numérique.

    Une quantité illisible (`None`, « 3,5 », un texte) n'est pas devinée : la
    déclarer de travers écraserait le calcul du moteur.
    """
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    return float(valeur)


def quantites_heures_sup_conjoncturelles(
    payslip_data: dict[str, Any] | None,
) -> tuple[float, float]:
    """Rend `(heures du premier palier, heures du second palier)`.

    Rend `(0.0, 0.0)` si le bulletin n'en porte pas, ou si une quantité n'est
    pas lisible — mieux vaut ne rien déclarer que déclarer un chiffre inventé.
    """
    if not isinstance(payslip_data, dict):
        return (0.0, 0.0)

    lignes = payslip_data.get("calcul_du_brut")
    if not isinstance(lignes, list):
        return (0.0, 0.0)

    retenues: list[tuple[float, float]] = []  # (taux, quantité)
    for ligne in lignes:
        if not _est_ligne_heures_sup_conjoncturelle(ligne):
            continue
        quantite = _nombre(ligne.get("quantite"))
        if quantite is None:
            return (0.0, 0.0)
        taux = _nombre(ligne.get("taux"))
        retenues.append((taux if taux is not None else 0.0, quantite))

    if not retenues:
        return (0.0, 0.0)

    # Le palier le plus majoré est celui dont l'heure coûte le plus cher.
    retenues.sort(key=lambda couple: couple[0])
    if len(retenues) == 1:
        taux, quantite = retenues[0]
        # Un seul palier : le libellé reste le seul indice disponible, et c'est
        # la convention que le moteur applique déjà aux saisies déclarées.
        libelle_50 = any(
            "50" in str(ligne.get("libelle") or "")
            for ligne in lignes
            if _est_ligne_heures_sup_conjoncturelle(ligne)
        )
        return (0.0, quantite) if libelle_50 else (quantite, 0.0)

    premier = sum(quantite for _, quantite in retenues[:-1])
    second = retenues[-1][1]
    return (premier, second)
