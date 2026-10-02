"""Exports de badgeuse WinDev « Pointages "retenu" + commentaires » (noms inventés).

Couche texte telle que pdfplumber la restitue : la date est sous le jour, le
total du jour termine la ligne des badgeages. Ce que la gestionnaire a tapé sur
le PDF en rouge ou en bleu (« + 1 », « - 0 . 5 », « ABSENCE JUSTIFIE -8.5 »,
« ? ? ? », « CP ») est resté dans le texte : sur la ligne du jour, après la date,
ou sur une ligne isolée — avant le jour suivant, ou entre un jour et sa date.
Une fiche badge peut ne porter que le nom (178), et une ancienne fiche
« NOM Prénom » sans aucun badgeage coexister avec elle (172).
"""

WINDEV_BADGE_WEEK = """Pointages "retenu" + commentaires, semaine à semaine Du 14/09/2026 au 20/09/2026 21/09/2026
101 ROUSSET Lina
Lundi 5:50 9:10 9:24 12:54 13:20 16:00 + 1 9:30
14/09/26
Mardi 5:51 8:13 8:28 8:51 9:00 12:53 13:17 16:00 9:21
15/09/26
Mercredi 4:53 8:35 8:50 13:00 7:52
16/09/26
Jeudi 5:49 8:55 9:09 13:03 13:29 16:00 - 0 . 5 9:31
17/09/26
Vendredi 5:21 8:10 8:30 9:13 12:00 + 1 3:32
18/09/26
Samedi
19/09/26
Dimanche
20/09/26
Total pour la semaine 38/2026: 39:46
101 ROUSSET Lina 39:46
178 DUPRAT
Édition en heures et minutes 1/2
Lundi 6:36 9:08 9:17 13:01 13:11 16:00 9:05
14/09/26
Mardi 6:34 9:06 9:12 12:54 13:07 16:00 9:07
15/09/26
Mercredi 4:34 13:00 8:26
16/09/26
Jeudi 4:34 8:59 9:04 13:00 8:21
17/09/26
+ 0.5
Vendredi 5:37 8:52 8:58 12:00 6:17
18/09/26
Samedi
19/09/26
Dimanche
20/09/26
Total pour la semaine 38/2026: 41:16
178 DUPRAT 41:16
172 DUPRAT Claire
Lundi
14/09/26
Mardi
15/09/26
Mercredi
16/09/26
Jeudi
17/09/26
Vendredi
18/09/26
Samedi
19/09/26
Dimanche
20/09/26
Total pour la semaine 38/2026: 0:00
172 DUPRAT Claire 0:00
176 BERTIN Paul
Lundi 6:25 9:10 9:24 12:53 13:31 ? ? ? 6:14
14/09/26
Mardi ABSENCE JUSTIFIE -8.5
15/09/26
Mercredi 4:53 8:57 9:18 13:00 7:46
16/09/26
Jeudi 6:50 9:01 9:23 13:20 13:52 16:00 8:16
17/09/26
Vendredi
18/09/26 CP
Samedi
19/09/26
Dimanche
20/09/26
Total pour la semaine 38/2026: 22:16
176 BERTIN Paul 22:16
"""
