# Relevé hebdomadaire — en-tête « semaine du … au … » avec dates explicites
WEEKLY_HEADER = """
RELEVÉ DE POINTAGE — Semaine du 03/06/2025 au 09/06/2025
Entreprise ACME

Martin Paul
Lun 03/06  8.00
Mar 04/06  7.50
Mer 05/06  8.00
Jeu 06/06  8.00
Ven 07/06  6.00
Total semaine : 37.50 h
"""

# Relevé mensuel partiel — plage de dates étendue
MONTHLY_PARTIAL = """
POINTAGES JUIN 2025
Durand Sophie
01/06 0  02/06 8  03/06 8  04/06 8  05/06 8  06/06 0
09/06 8  10/06 8  11/06 8  12/06 8  13/06 8
16/06 8  17/06 8  18/06 8  19/06 8  20/06 8
23/06 8  24/06 8  25/06 8  26/06 8  27/06 8
30/06 8
"""

# Colonnes jours de la semaine sans dates ni période
WEEKDAYS_ONLY = """
BADGEUSE FILIALE X
Employé : INCONNU Jean

Lun    Mar    Mer    Jeu    Ven
 8h     8h     7h     8h     6h
"""

# Semaine à cheval sur deux mois
CROSS_MONTH = """
Semaine du 27/05/2025 au 02/06/2025
Martin Paul — Lun 27/05 8h Mar 28/05 8h Mer 29/05 8h Jeu 30/05 8h Ven 31/05 4h
Sam 01/06 0h Dim 02/06 0h
"""

# Numéro de semaine sans dates
WEEK_NUMBER_ONLY = """
Rapport S24 — Exercice 2025
Heures équipe production
"""

# Relevé Cegid hebdomadaire (format Colorplast — anonymisé)
CEGID_WEEK_22 = """
Pointages "retenu" + commentaires
Du 25/05/2026 au 31/05/2026
Entreprise DEMO

196 ADAM YOUSSEF
Lundi 25/05/26
8:00 12:00 13:00 17:30
# 7:30
Mardi 26/05/26
8:00 12:00 13:00 17:29
# 7:29
Mercredi 27/05/26
8:00 12:00 13:00 17:30
# 7:30
Jeudi 28/05/26
8:00 12:00 13:00 17:30
# 7:30
Vendredi 29/05/26
8:00 12:00 13:00 17:30
# 7:30
Total pour la semaine 22/2026: 37:29

270 DURAND Sophie
Lundi 25/05/26
# 0:00
Mardi 26/05/26
8:00 12:00 13:00 17:00
# 7:00
Mercredi 27/05/26
8:00 12:00 13:00 17:00
# 7:00
Jeudi 28/05/26
8:00 12:00 13:00 17:00
# 7:00
Vendredi 29/05/26
8:00 12:00 13:00 17:00
# 7:00
Total pour la semaine 22/2026: 28:00

95 LIKA Rina
Lundi 25/05/26
# 0:00
Mardi 26/05/26
# 0:00
Mercredi 27/05/26
# 0:00
Jeudi 28/05/26
# 0:00
Vendredi 29/05/26
# 0:00
Total pour la semaine 22/2026: 0:00
"""

_CEGID_EMP_BLOCK = """
{mat} {name}
Lundi 25/05/26
8:00 12:00 13:00 17:30
# 7:30
Mardi 26/05/26
8:00 12:00 13:00 17:29
# 7:29
Mercredi 27/05/26
8:00 12:00 13:00 17:30
# 7:30
Jeudi 28/05/26
8:00 12:00 13:00 17:30
# 7:30
Vendredi 29/05/26
8:00 12:00 13:00 17:30
# 7:30
Total pour la semaine 22/2026: 37:29
"""

_CEGID_EMP_NAMES = [
    "ALPHA", "BRAVO", "CHARLIE", "DELTA", "ECHO", "FOXTROT", "GOLF", "HOTEL",
]

CEGID_LONG_TEXT = (
    'Pointages "retenu" + commentaires\n'
    "Du 25/05/2026 au 31/05/2026\n"
    "Entreprise DEMO\n"
    + "".join(
        _CEGID_EMP_BLOCK.format(
            mat=100 + i,
            name=f"EMPLOYE {_CEGID_EMP_NAMES[i % len(_CEGID_EMP_NAMES)]}",
        )
        for i in range(90)
    )
)

# Variante OCR bruitée (symptômes terrain : # manquant, séparateurs altérés, totaux coupés)
CEGID_WEEK_22_OCR_NOISY = """
Pointages "retenu" + commentaires
Du 25/05/2026 au 31/05/2026
Entreprise DEMO

196 ADAM YOUSSEF
Lundi 25/05/26
8:00 12:00 13:00 17:30
§ 7;30
Mardi 26/05/26
8:00 12.00 13:00 17:29
n 7:29
Mercredi 27/05/26
8:00 12:00 13:00 17:30
7:30
Jeudi 28/05/26
8:00 12:00 13:00 17:30
# 7:30
Vendredi 29/05/26
8:00 12:00 13:00 17:30
# 7:30
Total pour la semaine
22/2026: 37:29

270 DURAND Sophie
Lundi 25/05/26
§ 0:00
Mardi 26/05/26
8:00 12:00 13:00 17:00
# 7:00
Mercredi 27/05/26
8:00 12:00 13:00 17:00
# 7:00
Jeudi 28/05/26
8:00 12:00 13:00 17:00
# 7:00
Vendredi 29/05/26
8:00 12:00 13:00 17:00
# 7:00
Total pour la semaine 22/2026: 28:00

95 LIKA Rina
Lundi 25/05/26
# 0:00
Mardi 26/05/26
# 0:00
Mercredi 27/05/26
# 0:00
Jeudi 28/05/26
# 0:00
Vendredi 29/05/26
# 0:00
Total pour la semaine 22/2026: 0:00
"""
