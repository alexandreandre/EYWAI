"""Corriger une DSN mensuelle déjà déposée (registre R-174 et R-175).

Sources ouvertes le 08/11/2026, cahier technique 2026.1 (2025-12-24) :
- § 1.4.3.2 : un second fichier « normal » du même mois n'est pas accepté ;
- § 1.4.3.3 : l'annule et remplace intégral se dépose au plus tard la veille à
  minuit (heure de Paris) de la date d'exigibilité ; au-delà, les rectifications
  vont dans les paies et les DSN suivantes ; le numéro d'ordre (05.004) repère la
  déclaration remplacée et ne peut pas baisser ;
- § 2.2.2.2 et 2.2.2.5 : une régularisation de cotisation se rattache à sa
  période d'origine, mois civil par mois civil.

La rubrique 05.006 (identifiant de la déclaration remplacée) vaut pour les
signalements (§ 1.4.3.4) : DSN-VAL 2026.1.0.18 la refuse sur une mensuelle de type
03 (CST-04, 08/11/2026). L'annule et remplace mensuel ne la porte pas.

Seul le déclarant connaît la déclaration validée par le point de dépôt : Martine
enregistre chaque génération sans savoir laquelle est partie. Le numéro d'ordre
est donc toujours fourni, jamais déduit, et un annule et remplace n'est jamais
produit sans cette demande.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Optional

from app.modules.dsn_export.domain.signalements import echeance_mensuelle
from app.modules.payroll.domain.report_nap_negatif import mois_en_lettres

#: CSL 00 de S20.G00.05.004, sur 15 chiffres au plus.
_NUMERO_ORDRE = re.compile(r"0|[1-9][0-9]{0,13}")

_SUPPORT = "ouvrez un ticket (menu Support, module « Paie & Bulletins »)"

#: « régulier » n'est pas une régularisation.
_LIBELLE_DE_RAPPEL = re.compile(r"\brappels?\b|\bregul(?:arisation)?\b")


def _sans_accents(texte: str) -> str:
    return unicodedata.normalize("NFD", texte.lower()).encode("ascii", "ignore").decode("ascii")


@dataclass(frozen=True)
class DeclarationRemplacee:
    """La dernière DSN du mois validée par le point de dépôt."""

    ordre: int

    @property
    def ordre_suivant(self) -> int:
        return self.ordre + 1


def lire_numero_ordre(valeur: object) -> DeclarationRemplacee:
    """Le numéro d'ordre (S20.G00.05.004) du fichier déposé qu'on remplace."""
    texte = str(valeur if valeur is not None else "").strip()
    if _NUMERO_ORDRE.fullmatch(texte) is None:
        raise ValueError(
            "Le numéro d'ordre de la DSN à remplacer est illisible : indiquez le numéro "
            "d'ordre (nombre entier) du fichier déposé."
        )
    return DeclarationRemplacee(ordre=int(texte))


def _mois(period: str) -> tuple[int, int]:
    annee, mois = period.split("-")
    return int(annee), int(mois)


def date_limite_annule_remplace(period: str, effectif: int) -> date:
    """La veille de l'échéance du mois déclaré (le 5 ou le 15 du mois suivant)."""
    annee, mois = _mois(period)
    return echeance_mensuelle(date(annee, mois, 1), effectif) - timedelta(days=1)


def refus_annule_remplace(period: str, effectif: int, aujourd_hui: date) -> Optional[str]:
    limite = date_limite_annule_remplace(period, effectif)
    if aujourd_hui <= limite:
        return None
    return (
        f"La DSN de {mois_en_lettres(*_mois(period))} ne peut plus être remplacée : la date "
        f"limite était le {limite:%d/%m/%Y}. La correction se porte sur la paie d'un mois suivant."
    )


def avis_mois_deja_declare(period: str, effectif: int, aujourd_hui: date) -> str:
    """Ce que la gestionnaire doit savoir avant de refaire un mois déjà généré."""
    libelle = mois_en_lettres(*_mois(period))
    limite = date_limite_annule_remplace(period, effectif)
    if aujourd_hui <= limite:
        return (
            f"Une DSN de {libelle} a déjà été générée. Si elle a été déposée, net-entreprises "
            "refusera un deuxième fichier normal. Pour corriger un bulletin, il faut une DSN "
            f"« annule et remplace » de tout le mois, au plus tard le {limite:%d/%m/%Y} ; "
            f"elle n'est pas encore proposée à l'écran : {_SUPPORT}. Après cette date, la "
            "correction se portera sur la paie d'un mois suivant."
        )
    return (
        f"Une DSN de {libelle} a déjà été générée et la date limite de son remplacement "
        f"({limite:%d/%m/%Y}) est passée. Si elle a été déposée, un bulletin corrigé se déclare "
        f"sur la paie d'un mois suivant. Martine ne sait pas encore le rattacher à {libelle} : "
        f"{_SUPPORT}."
    )


def libelles_de_rappel_du_bulletin(payslip_data: Mapping[str, Any] | None) -> list[str]:
    """Les rappels saisis en prime sur ce bulletin, catalogue ou libellé libre, sans doublon.

    Seules les lignes liées à une saisie comptent : c'est là que Gaëlle pose un rappel.
    Une régularisation d'heures n'en est pas : la DSN la rattache à son mois
    d'origine (`rattachement.py`).
    """
    libelles: dict[str, None] = {}
    for ligne in (payslip_data or {}).get("calcul_du_brut") or []:
        if not isinstance(ligne, Mapping):
            continue
        if not ligne.get("saisie_id") or isinstance(ligne.get("regularisation_heures"), Mapping):
            continue
        libelle = str(ligne.get("libelle") or "")
        if _LIBELLE_DE_RAPPEL.search(_sans_accents(libelle)):
            libelles[libelle] = None
    return list(libelles)


def avis_rappel_sans_mois_origine(salarie: str, libelle: str, period: str) -> str:
    """CT 2026.1 § 2.1.3.6 : un rappel se déclare rattaché à sa période. Martine ne le fait pas."""
    return (
        f"Salarié {salarie} : le rappel « {libelle} » est déclaré dans le mois de "
        f"{mois_en_lettres(*_mois(period))}, sans rattachement. S'il concerne un mois passé, la "
        f"DSN devrait le rattacher à son mois d'origine, ce que Martine ne sait pas encore "
        f"faire : {_SUPPORT}."
    )


def avis_regularisation_sans_mois_origine(salarie: str, libelle: str, period: str) -> str:
    return (
        f"Salarié {salarie} : la régularisation « {libelle} » est déclarée avec les dates de "
        f"{mois_en_lettres(*_mois(period))}. Si elle corrige un mois passé, la DSN doit la "
        f"rattacher à son mois d'origine, ce que Martine ne sait pas encore faire : {_SUPPORT}."
    )


def avis_des_regularisations(
    salarie: str, payslip_data: Mapping[str, Any] | None, period: str
) -> list[str]:
    """Ce que l'aperçu de la DSN dit des régularisations et rappels d'un bulletin.

    Une régularisation saisie avec sa période se déclare à ses mois d'origine :
    rien à dire, sauf la répartition à parts égales sur plusieurs mois. Sans
    période, ou pour ce que Martine ne rattache pas (réduction générale,
    prévoyance), l'avis d'hier reste.
    """
    # Import local : le mapping importe ce module par la chaîne du builder.
    from app.modules.dsn_export.domain.cotisation_mapping import regularisation_rattachable
    from app.modules.dsn_export.domain.rattachement import (
        avis_repartition,
        mois_passes,
        periode_d_heures_regularisees,
        periode_d_une_cotisation,
    )
    from app.modules.payroll.engine.corrections_manuelles import regularisations_du_bulletin

    avis: list[str] = []
    for regul in regularisations_du_bulletin(payslip_data).values():
        ligne = regul.ligne_de_cotisation()
        origine = periode_d_une_cotisation(ligne)
        passes = mois_passes(origine, period)[0] if origine else []
        if passes and regularisation_rattachable(ligne):
            if len(passes) > 1:
                avis.append(avis_repartition(salarie, regul.libelle, passes))
            continue
        avis.append(avis_regularisation_sans_mois_origine(salarie, regul.libelle, period))
    for ligne in (payslip_data or {}).get("calcul_du_brut") or []:
        if not isinstance(ligne, Mapping):
            continue
        origine = periode_d_heures_regularisees(ligne)
        if origine is None:
            continue
        passes = mois_passes(origine, period)[0]
        if len(passes) > 1:
            avis.append(avis_repartition(salarie, str(ligne.get("libelle") or ""), passes))
    for libelle in libelles_de_rappel_du_bulletin(payslip_data):
        avis.append(avis_rappel_sans_mois_origine(salarie, libelle, period))
    return avis
