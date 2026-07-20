"""
Constantes structurelles légales (règles de droit stables, non scrapées).
"""

from __future__ import annotations

# Temps de travail
DUREE_LEGALE_HEBDO = 35.0
DIVISEUR_JOURS_CALENDAIRES = 30.42

# Seuils d'effectif
SEUIL_EFFECTIF_FNAL = 50
SEUIL_EFFECTIF_CFP = 11

# Bascule réduction générale : Fillon (RGCP) jusqu'en 2025, RGDU à partir de 2026
# (réforme des allègements généraux, LFSS 2025 art. 18 / décret n°2025-887).
ANNEE_BASCULE_RGDU = 2026

# Plafonds SS / assiettes
COEFF_PLAFOND_IJ_PSS = 1.8
FACTEUR_PLAFOND_TRANCHE_2 = 8

# Seuils SMIC (maintien / allocations)
SEUIL_SMIC_MALADIE = 2.5
SEUIL_SMIC_ALLOC = 3.5

# Taux IJSS légaux (structure de calcul, non scrapés)
TAUX_IJSS_MALADIE = 0.50
TAUX_IJSS_MALADIE_3_ENFANTS = 0.66
TAUX_IJSS_AT_MP_J1_28 = 0.60
TAUX_IJSS_AT_MP_J29 = 0.80
TAUX_IJSS_MI_TEMPS = 0.50

# Maintien employeur (tranches courantes)
TRANCHE_MAINTIEN_90 = 0.90
TRANCHE_MAINTIEN_66 = 2.0 / 3.0

# Transport
TAUX_REMBOURSEMENT_TRANSPORT = 0.50

# Exonération IR heures supplémentaires/complémentaires (art. 81 quater CGI,
# loi pouvoir d'achat n°2022-1158 du 16 août 2022, applicable aux
# rémunérations versées à compter du 1ᵉʳ janvier 2022) : plafond ANNUEL,
# exprimé en montant NET imposable des HS/HC (i.e. rémunération brute des
# HS/HC diminuée de la CSG/CRDS qui reste due dessus), apprécié par salarié
# tous employeurs confondus, sur l'année CIVILE. Au-delà, le surplus
# redevient imposable au barème progressif (reste exonéré de cotisations
# sociales salariales à 11,31 %, mécanisme distinct — cf.
# `calcul_cotisations.py`). Source : BOI-RSA-CHAMP-20-50-20-40, BOSS
# Exo-HS-30, service-public.gouv.fr.
PLAFOND_EXONERATION_IR_HS_ANNUEL_NET = 7500.0
