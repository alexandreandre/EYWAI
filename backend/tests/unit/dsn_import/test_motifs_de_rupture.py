"""Import DSN : le motif de rupture (S21.G00.62.002) devient le bon type de départ.

Source : cahier technique DSN 2026.1 (NEODeS, net-entreprises.fr, version du
24/12/2025), rubrique S21.G00.62.002 « Motif de la rupture du contrat », liste
des valeurs p. 273-274 — copie locale
docs/audit-maji-2026/sources/dsn-cahier-technique-2026.1.txt, l. 16183-16251.

La table traduisait 039 (départ à la retraite à l'initiative du salarié) en
démission, 038 (mise à la retraite par l'employeur) en fin de période d'essai,
034 et 035 (fins de période d'essai) en licenciement, 011 et 012 (licenciements)
en démission, 020 (licenciement pour autre motif) en rupture conventionnelle,
025 et 026 (motif économique) en départ à la retraite, et les fins de mission
ou ruptures anticipées de CDD (032, 033, 036, 037) en licenciement : un
recalcul des indemnités de ces dossiers aurait payé une indemnité de
licenciement à une fin de CDD (enquête H, annexe A).

Martine n'a que sept types de départ ; chaque motif va au plus proche. La mise
à la retraite (038) n'a pas encore de type propre : elle est rangée avec les
départs à la retraite, le motif d'origine restant dans « Import DSN (038) ».
"""

from __future__ import annotations

import pytest

from app.modules.dsn_import.domain.dsn_absence_exit_mapping import map_exit_motif

pytestmark = pytest.mark.unit

MOTIFS = [
    # Licenciements et ruptures à l'initiative de l'employeur
    ("011", "licenciement"),  # licenciement suite à liquidation ou redressement judiciaire
    ("012", "licenciement"),  # licenciement suite à fermeture définitive de l'établissement
    ("014", "licenciement"),  # licenciement pour motif économique
    ("015", "licenciement"),  # licenciement pour fin de chantier ou d'opération
    ("020", "licenciement"),  # licenciement pour autre motif
    ("025", "licenciement"),  # autre fin de contrat pour motif économique
    ("026", "licenciement"),  # rupture pour motif économique après acceptation d'un CSP
    ("065", "licenciement"),  # décès de l'employeur ou internement, licenciement autre motif
    ("082", "licenciement"),  # résiliation judiciaire du contrat de travail
    ("083", "licenciement"),  # rupture pour force majeure ou fait du prince
    ("086", "licenciement"),  # licenciement convention CATS
    ("087", "licenciement"),  # licenciement pour faute grave
    ("088", "licenciement"),  # licenciement pour faute lourde
    ("089", "licenciement"),  # licenciement pour force majeure
    ("091", "licenciement"),  # inaptitude d'origine non professionnelle
    ("092", "licenciement"),  # inaptitude d'origine professionnelle
    ("093", "licenciement"),  # licenciement suite à décision d'une autorité administrative
    ("112", "licenciement"),  # rupture dans le cadre d'un accord de performance collective
    ("113", "licenciement"),  # licenciement pour motif spécifique (L2254-2)
    ("115", "licenciement"),  # licenciement, articles 18 et 19 de la loi 2017-1339
    ("117", "licenciement"),  # licenciement économique après refus d'un CSP
    # Fins de CDD, de mission ou d'apprentissage, à terme ou anticipées
    ("031", "fin_cdd"),  # fin de CDD ou fin d'accueil occasionnel
    ("032", "fin_cdd"),  # fin de mission d'intérim
    ("033", "fin_cdd"),  # rupture anticipée d'un CDD ou d'une mission pour inaptitude
    ("036", "fin_cdd"),  # rupture anticipée d'un CDD… à l'initiative de l'employeur
    ("037", "fin_cdd"),  # rupture anticipée d'un CDD… à l'initiative du salarié
    ("081", "fin_cdd"),  # fin de contrat d'apprentissage
    ("084", "fin_cdd"),  # rupture d'un commun accord du CDD, de l'apprentissage ou de la mission
    ("094", "fin_cdd"),  # rupture anticipée pour arrêt de tournage
    ("095", "fin_cdd"),  # rupture anticipée d'un CDD ou d'une mission pour faute grave
    ("096", "fin_cdd"),  # rupture anticipée d'un CDD ou d'une mission pour faute lourde
    ("097", "fin_cdd"),  # rupture anticipée suite à fermeture de l'établissement
    # Périodes d'essai
    ("034", "fin_periode_essai"),  # à l'initiative de l'employeur
    ("035", "fin_periode_essai"),  # à l'initiative du salarié
    # Retraite
    ("038", "depart_retraite"),  # mise à la retraite par l'employeur
    ("039", "depart_retraite"),  # départ à la retraite à l'initiative du salarié
    # Ruptures d'un commun accord
    ("043", "rupture_conventionnelle"),  # rupture conventionnelle
    ("110", "rupture_conventionnelle"),  # rupture conventionnelle collective
    ("111", "rupture_conventionnelle"),  # rupture amiable dans le cadre d'un congé de mobilité
    ("114", "rupture_conventionnelle"),  # rupture d'un commun accord pour entrée en PAP
    # À l'initiative du salarié
    ("058", "demission"),  # prise d'acte de la rupture
    ("059", "demission"),  # démission
    # Sans rupture du contrat
    ("100", "transfert"),  # mutation au sein du même groupe, sans rupture du contrat
    ("998", "transfert"),  # transfert du contrat vers un autre établissement, sans rupture
]


@pytest.mark.parametrize("motif, type_attendu", MOTIFS)
def test_chaque_motif_officiel_devient_le_type_de_depart_le_plus_proche(motif, type_attendu):
    assert map_exit_motif(motif) == type_attendu


@pytest.mark.parametrize("motif", ["39", " 039 ", "0390"])
def test_le_motif_est_lu_sur_trois_chiffres(motif):
    assert map_exit_motif(motif) == "depart_retraite"
