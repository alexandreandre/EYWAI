"""« Prime de précarité non due », saisie au départ « Fin de CDD ».

Les cas de la fiche service-public F40 « Fin d'un contrat à durée déterminée
(CDD) » (vérifiée le 22/01/2024, ouverte le 12/10/2026), et la rupture anticipée
à l'initiative du salarié (Code du travail, L1243-10, 4°). L'embauche en CDI à
l'issue du CDD relève de L1243-8 (l'indemnité n'est due que si les relations ne
se poursuivent pas par un CDI), les autres cas de L1243-10.

Le motif est rangé dans `exit_notes.precarite_non_due`. Le dossier de départ le
recopie dans `indemnite_precarite` (`non_due`, `motif`) : le bulletin de sortie
lit le dossier et ne verse pas la prime ; le reçu pour solde de tout compte et
l'attestation France Travail disent pourquoi. Les drapeaux de la fiche
(`exclure_prime_precarite`, `cdd_sans_precarite`) et le motif de recours
(engine/motif_recours.py) l'écartent toujours de leur côté.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

MotifPrecariteNonDue = Literal[
    "embauche_cdi",
    "refus_cdi",
    "rupture_anticipee_salarie",
    "faute_grave",
    "force_majeure",
    "cdd_usage",
    "contrat_aide",
    "complement_formation",
    "jeune_vacances",
    "saisonnier",
]

#: Code du motif → ce que disent le dossier, le reçu et l'attestation.
MOTIFS_PRECARITE_NON_DUE: dict[str, str] = {
    "embauche_cdi": "embauche en CDI à l'issue du CDD",
    "refus_cdi": (
        "refus d'un CDI proposé pour le même emploi ou un emploi similaire, "
        "avec une rémunération au moins équivalente"
    ),
    "rupture_anticipee_salarie": "rupture anticipée du CDD à l'initiative du salarié",
    "faute_grave": "faute grave",
    "force_majeure": "force majeure",
    "cdd_usage": "CDD d'usage",
    "contrat_aide": "contrat aidé (CUI-PEC, contrat de professionnalisation, contrat d'apprentissage)",
    "complement_formation": (
        "contrat avec un complément de formation professionnelle assuré par l'employeur"
    ),
    "jeune_vacances": "contrat conclu avec un jeune pendant ses vacances scolaires ou universitaires",
    "saisonnier": "contrat saisonnier",
}

_ARTICLES = {"embauche_cdi": "L1243-8"}


def motif_precarite_non_due(exit_notes: Any) -> str | None:
    """Le motif saisi au départ, s'il est l'un des cas connus."""
    if not isinstance(exit_notes, Mapping):
        return None
    motif = exit_notes.get("precarite_non_due")
    return motif if motif in MOTIFS_PRECARITE_NON_DUE else None


def mention_precarite_non_due(motif: str) -> str:
    """La phrase du dossier, du reçu et de l'attestation France Travail."""
    article = _ARTICLES.get(motif, "L1243-10")
    return (
        "Indemnité de fin de contrat (prime de précarité) non due : "
        f"{MOTIFS_PRECARITE_NON_DUE[motif]} (Code du travail, art. {article})."
    )


def mention_du_depart(exit_data: Any) -> str | None:
    """La mention d'une fin de CDD dont la prime n'est pas due, sinon None."""
    if not isinstance(exit_data, Mapping) or exit_data.get("exit_type") != "fin_cdd":
        return None
    motif = motif_precarite_non_due(exit_data.get("exit_notes"))
    return mention_precarite_non_due(motif) if motif else None


def precarite_non_due_au_dossier(indemnites: Any) -> bool:
    """Vrai quand le dossier de départ du bulletin dit la prime non due."""
    if not isinstance(indemnites, Mapping):
        return False
    bloc = indemnites.get("indemnite_precarite")
    return isinstance(bloc, Mapping) and bloc.get("non_due") is True
