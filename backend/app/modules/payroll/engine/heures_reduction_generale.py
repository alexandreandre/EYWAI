"""Heures rémunérées du mois pour le SMIC de référence de la réduction générale (générateur des heures).

Le salaire minimum de la formule se proratise sur la rémunération que l'absence laisse : en cas de
suspension sans maintien intégral, le rapport entre la rémunération versée et celle que le salarié
aurait perçue s'il avait été présent (BOSS, allègements généraux, § 770 à 790 ; CSS D. 241-7, IV).
Maintien intégral : le salaire minimum de la présence (§ 750). Les IJSS subrogées n'entrent pas dans
le rapport (§ 790) : le maintien versé est le complément de l'employeur.

Deux cas :
- mois au salaire retenu en entier (aucun jour prévu travaillé) : les heures du contrat, heures sup
  structurelles comprises, valent au prorata du maintien sur le salaire du mois complet. La retenue
  jour par jour n'y fait pas foi : elle ne couvre pas toujours les heures du contrat (20 jours × 7 h
  = 140 h sur 151,67 h en février ; vendredis de 5 h à 39 h) et peut les dépasser (22 jours × 7 h =
  154 h) ; le « Complément retenue absence intégrale » ou la « Retenue limitée au salaire » ramène
  l'argent au salaire du mois, pas les heures ;
- mois en partie travaillé : un arrêt sort ses heures à proportion de ce que l'employeur ne maintient
  pas. La retenue de l'arrêt comprend sa part d'heures sup structurelles (ligne « Heures sup. du
  contrat non faites »), comme ses heures : le maintien se rapporte aux deux.
"""

from __future__ import annotations


def heures_remunerees_pour_la_reduction(
    *,
    heures_base_mois: float,
    heures_activite_partielle: float,
    heures_absence_non_payees: float,
    heures_arret: float,
    retenue_arret_base: float,
    retenue_arret_heures_sup: float,
    maintien_verse: float,
    total_heures_supp: float,
    heures_sup_conjoncturelles: float,
    heures_complementaires: float,
    heures_normales_regularisees: float,
    heures_retablies_par_rappels: float,
    salaire_retenu_en_entier: bool,
    salaire_du_mois_complet: float,
) -> float:
    """Les heures du mois qui entrent dans le SMIC de référence (non arrondies)."""
    heures_base_payees = max(0.0, heures_base_mois - heures_activite_partielle)
    en_plus = (
        heures_retablies_par_rappels
        + heures_normales_regularisees
        + heures_complementaires
    )
    if salaire_retenu_en_entier and salaire_du_mois_complet > 0:
        heures_sup_structurelles = max(0.0, total_heures_supp - heures_sup_conjoncturelles)
        part_payee = min(1.0, max(0.0, maintien_verse) / salaire_du_mois_complet)
        return max(
            0.0,
            (heures_base_payees + heures_sup_structurelles) * part_payee
            + heures_sup_conjoncturelles
            + en_plus,
        )
    heures_arret_non_maintenues = 0.0
    if heures_arret > 0:
        retenue = retenue_arret_base + retenue_arret_heures_sup
        part_maintenue = min(1.0, maintien_verse / retenue) if retenue > 0 else 0.0
        heures_arret_non_maintenues = round(heures_arret * (1.0 - part_maintenue), 2)
    return max(
        0.0,
        heures_base_payees
        - heures_arret_non_maintenues
        + total_heures_supp
        - heures_absence_non_payees
        + en_plus,
    )
