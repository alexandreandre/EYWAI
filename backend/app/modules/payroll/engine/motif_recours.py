"""Motif de recours d'un CDD : ce qu'il dit de l'indemnité de fin de contrat.

Le motif est saisi sur la fiche (« Motif de recours du CDD »), sous
`specificites_paie.dsn_reprise.motif_recours`, ou posé dans la classification
par la reprise DSN. Ce sont les codes de la rubrique DSN S21.G00.40.021 (cahier
technique DSN, P26), les mêmes que `frontend/src/constants/dsnFiche.ts`
(MOTIFS_RECOURS_CDD) et que l'export DSN lit (`dsn_export/application/builder.py`).

Code du travail, art. L1243-10 : l'indemnité de fin de contrat (prime de
précarité, art. L1243-8) n'est pas due
  1° lorsque le contrat est conclu au titre du 3° de l'article L1242-2 (emplois
     à caractère saisonnier, contrats d'usage) ou de l'article L1242-3
     (recrutement de personnes sans emploi, complément de formation
     professionnelle), sauf dispositions conventionnelles plus favorables ;
  2° pour un jeune pendant ses vacances scolaires ou universitaires ;
  3° quand le salarié refuse un CDI pour le même emploi ou un emploi similaire ;
  4° en cas de rupture anticipée à l'initiative du salarié, faute grave ou force
     majeure.
Seul le 1° a un code de motif ; les autres cas restent aux drapeaux de la fiche
(`exclure_prime_precarite`, `cdd_sans_precarite`), qui gardent la priorité. Le
contrat vendanges est un contrat saisonnier (Code rural, art. L718-4 à L718-6).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

#: Codes S21.G00.40.021 pour lesquels l'indemnité de fin de contrat n'est pas
#: due (Code du travail, art. L1243-10, 1°).
MOTIFS_SANS_INDEMNITE_FIN_CONTRAT: dict[str, str] = {
    "03": "emploi à caractère saisonnier (L1242-2, 3°)",
    "04": "contrat vendanges, contrat saisonnier (L1242-2, 3° ; Code rural, L718-4)",
    "05": "contrat d'usage (L1242-2, 3°)",
    "09": "recrutement de personnes sans emploi en difficulté (L1242-3, 1°)",
    "10": "complément de formation professionnelle (L1242-3, 2°)",
}


def _code(valeur: Any) -> str:
    texte = str(valeur or "").strip()
    if texte.isdigit() and len(texte) < 2:
        return texte.zfill(2)
    return texte


def motif_recours_cdd(classification: Any, specificites: Any) -> str:
    """Le code du motif de recours, dans l'ordre de l'export DSN : la
    classification d'abord, la saisie de la fiche (`dsn_reprise`) ensuite."""
    if isinstance(classification, Mapping) and classification.get("motif_recours"):
        return _code(classification.get("motif_recours"))
    reprise = specificites.get("dsn_reprise") if isinstance(specificites, Mapping) else None
    if isinstance(reprise, Mapping):
        return _code(reprise.get("motif_recours"))
    return ""


def prime_precarite_exclue_par_motif(classification: Any, specificites: Any) -> bool:
    """Vrai quand le motif de recours exclut l'indemnité de fin de contrat (L1243-10, 1°)."""
    return motif_recours_cdd(classification, specificites) in MOTIFS_SANS_INDEMNITE_FIN_CONTRAT
