"""Salaire de référence des sommes de départ, tiré des bulletins bruts.

Code du travail, art. R1234-4 (Légifrance, version en vigueur depuis le
27/09/2017, ouvert le 11/10/2026) : « Le salaire à prendre en considération
pour le calcul de l'indemnité de licenciement est, selon la formule la plus
avantageuse pour le salarié : 1° Soit la moyenne mensuelle des douze derniers
mois précédant le licenciement, ou lorsque la durée de service du salarié est
inférieure à douze mois, la moyenne mensuelle de la rémunération de l'ensemble
des mois précédant le licenciement ; 2° Soit le tiers des trois derniers mois.
Dans ce cas, toute prime ou gratification de caractère annuel ou exceptionnel,
versée au salarié pendant cette période, n'est prise en compte que dans la
limite d'un montant calculé à due proportion. »

service-public.gouv.fr F987 (vérifié le 05/06/2026, ouvert le 11/10/2026) :
« L'indemnité légale est calculée à partir des salaires bruts précédant le
licenciement » ; « Si une prime annuelle a été perçue, il faut ajouter 1/12e
du montant de la prime à chacun des 3 derniers mois de référence » ;
« Lorsque le salarié a été en arrêt de travail pour maladie […] le salaire de
référence à prendre en compte est celui des 12 ou des 3 derniers mois
précédant l'arrêt ».

Cour de cassation, chambre sociale, 23 mai 2017, n° 15-22.223, publié au
bulletin (Légifrance JURITEXT000034813531, ouvert le 11/10/2026) : « le
salaire de référence à prendre en considération pour le calcul de l'indemnité
légale ou conventionnelle de licenciement est, selon la formule la plus
avantageuse pour le salarié, celui des douze ou des trois derniers mois
précédant l'arrêt de travail pour maladie ». Quand les mois de référence
contiennent un arrêt, ce sont les mois qui précèdent l'arrêt le plus récent
qui servent, et le détail de l'indemnité le dit (`arret`).

Les primes « de caractère annuel ou exceptionnel » sont reconnues à leur
libellé (13e mois, prime annuelle, exceptionnelle, de bilan, de fin d'année,
de vacances, gratification, bonus) : un libellé inconnu compte comme du salaire.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, List, Optional, Sequence, Tuple

_PRIME_ANNUELLE = re.compile(
    r"13e mois|13eme mois|treizieme|annuel|exceptionnel|bilan|fin d'annee"
    r"|vacances|gratification|bonus"
)
_ARRET = re.compile(r"maladie|maintien de salaire|accident du travail|\bijss\b")


def _normalise(texte: Any) -> str:
    sans_accents = unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore")
    return sans_accents.decode("ascii").lower()


def _nombre(valeur: Any) -> float:
    try:
        return float(valeur or 0)
    except (TypeError, ValueError):
        return 0.0


@dataclass(frozen=True, order=True)
class MoisDeSalaire:
    annee: int
    mois: int
    #: Brut du bulletin, sommes de rupture retirées.
    brut: float
    #: Primes de caractère annuel ou exceptionnel versées ce mois, comprises dans le brut.
    primes_annuelles: float = 0.0
    arret_maladie: bool = False


@dataclass(frozen=True)
class SalaireDeReference:
    retenu: float
    #: « douze_mois », « trois_mois » ou « contrat » (aucun bulletin lu).
    formule: str
    moyenne_douze_mois: Optional[float]
    tiers_trois_mois: Optional[float]
    mois_lus: int
    alertes: Tuple[str, ...] = field(default_factory=tuple)
    #: Arrêt maladie dans les mois de référence : la phrase qui le dit.
    arret: Optional[str] = None

    def phrase(self) -> str:
        if self.formule == "contrat":
            return (
                f"salaire habituel du contrat ({self.retenu:.2f} €), "
                "aucun bulletin dans Martine avant le départ"
            )
        douze = f"moyenne des {self.mois_lus} derniers mois {self.moyenne_douze_mois:.2f} €"
        trois = f"tiers des 3 derniers mois {self.tiers_trois_mois:.2f} €"
        retenue = "moyenne" if self.formule == "douze_mois" else "tiers des 3 derniers mois"
        return f"{douze}, {trois} : {retenue} retenu, le plus favorable (R1234-4)"


_MOIS_FR = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)


def _mois_fr(mois: MoisDeSalaire) -> str:
    return f"{_MOIS_FR[mois.mois - 1]} {mois.annee}"


def _suivant(annee: int, mois: int) -> Tuple[int, int]:
    return (annee, mois + 1) if mois < 12 else (annee + 1, 1)


def _arret_le_plus_recent(derniers: Sequence[MoisDeSalaire]) -> Optional[Tuple[MoisDeSalaire, MoisDeSalaire]]:
    """(premier mois, dernier mois) de l'arrêt le plus récent : les mois d'arrêt
    consécutifs qui finissent au dernier mois d'arrêt des mois de référence."""
    arrets = [m for m in derniers if m.arret_maladie]
    if not arrets:
        return None
    fin = arrets[-1]
    debut = fin
    for precedent in reversed(arrets[:-1]):
        if _suivant(precedent.annee, precedent.mois) != (debut.annee, debut.mois):
            break
        debut = precedent
    return debut, fin


def _repli_contrat(repli_contrat: float, alerte: str) -> SalaireDeReference:
    return SalaireDeReference(
        retenu=round(max(repli_contrat, 0.0), 2),
        formule="contrat",
        moyenne_douze_mois=None,
        tiers_trois_mois=None,
        mois_lus=0,
        alertes=(alerte,),
    )


def calculer_salaire_de_reference(
    mois: Sequence[MoisDeSalaire],
    *,
    repli_contrat: float,
    mois_d_anciennete: Optional[int] = None,
    avant_l_arret: bool = True,
) -> SalaireDeReference:
    """Le plus favorable de la moyenne des douze derniers mois et du tiers des
    trois derniers (primes annuelles à due proportion). Sans bulletin : le
    salaire habituel du contrat, signalé.

    `avant_l_arret` : un arrêt maladie dans les douze mois fait prendre les
    mois qui précèdent l'arrêt le plus récent (Cass. soc., 23 mai 2017,
    n° 15-22.223). False pour la rémunération d'un préavis, qui n'est pas un
    salaire de référence d'indemnité de licenciement : l'arrêt y est signalé."""
    tries = sorted(mois)
    derniers = tries[-12:]
    if not derniers:
        return _repli_contrat(
            repli_contrat,
            "Aucun bulletin dans Martine avant le départ : salaire de référence "
            "pris au salaire habituel du contrat, à vérifier.",
        )
    phrase_arret: Optional[str] = None
    mois_exclus = 0
    arret = _arret_le_plus_recent(derniers) if avant_l_arret else None
    if arret is not None:
        debut, fin = arret
        avant = [m for m in tries if (m.annee, m.mois) < (debut.annee, debut.mois)]
        periode = (
            f"de {_mois_fr(debut)} à {_mois_fr(fin)}" if debut != fin else f"en {_mois_fr(debut)}"
        )
        if not avant:
            return _repli_contrat(
                repli_contrat,
                f"Arrêt maladie {periode} dans les mois de référence et aucun bulletin dans "
                "Martine avant l'arrêt : salaire de référence pris au salaire habituel du "
                "contrat, à vérifier (Cass. soc., 23 mai 2017, n° 15-22.223).",
            )
        mois_exclus = len([m for m in tries if (m.annee, m.mois) >= (debut.annee, debut.mois)])
        derniers = avant[-12:]
        phrase_arret = (
            f"Salaire de référence calculé sur les {len(derniers)} mois qui précèdent l'arrêt "
            f"maladie {periode} (Cass. soc., 23 mai 2017, n° 15-22.223)."
        )
    moyenne = round(sum(m.brut for m in derniers) / len(derniers), 2)
    trois = derniers[-3:]
    total_trois = sum(
        m.brut - m.primes_annuelles + m.primes_annuelles * len(trois) / 12 for m in trois
    )
    tiers = round(total_trois / len(trois), 2)
    alertes: List[str] = []
    anciennete = None if mois_d_anciennete is None else mois_d_anciennete - mois_exclus
    attendus = 12 if anciennete is None else min(12, max(anciennete, 0))
    if len(derniers) < attendus:
        alertes.append(
            f"Salaire de référence lu sur {len(derniers)} bulletins : les mois "
            "précédents ne sont pas dans Martine (ancien logiciel), à vérifier."
        )
    if not avant_l_arret and any(m.arret_maladie for m in derniers):
        alertes.append(
            "Arrêt maladie dans les derniers mois : la rémunération que le salarié aurait "
            "perçue est à vérifier."
        )
    if tiers > moyenne:
        return SalaireDeReference(
            tiers, "trois_mois", moyenne, tiers, len(derniers), tuple(alertes), phrase_arret
        )
    return SalaireDeReference(
        moyenne, "douze_mois", moyenne, tiers, len(derniers), tuple(alertes), phrase_arret
    )


def mois_de_salaire_du_bulletin(annee: int, mois: int, payslip_data: dict) -> MoisDeSalaire:
    from app.modules.payroll.solde_de_tout_compte.common.bulletin_de_sortie import (
        sommes_de_rupture_du_bulletin,
    )

    brut = _nombre(payslip_data.get("salaire_brut"))
    rupture = sum(
        _nombre(s.get("montant"))
        for s in sommes_de_rupture_du_bulletin(payslip_data)
        if s.get("dans_le_brut")
    )
    primes = 0.0
    arret = False
    lignes: Iterable[dict] = list(payslip_data.get("calcul_du_brut") or []) + list(
        payslip_data.get("details_absences") or []
    )
    for ligne in lignes:
        if not isinstance(ligne, dict):
            continue
        libelle = _normalise(ligne.get("libelle"))
        if _ARRET.search(libelle):
            arret = True
        if libelle.startswith("prime") or "gratification" in libelle or "13" in libelle:
            if _PRIME_ANNUELLE.search(libelle):
                primes += _nombre(ligne.get("gain")) - _nombre(ligne.get("perte"))
    return MoisDeSalaire(
        annee=int(annee),
        mois=int(mois),
        brut=round(brut - rupture, 2),
        primes_annuelles=round(max(primes, 0.0), 2),
        arret_maladie=arret,
    )


def lire_mois_de_salaire(
    employee_id: str, avant_le: date, supabase_client: Any, *, nombre: int = 12
) -> List[MoisDeSalaire]:
    """Les bulletins des `nombre` mois qui précèdent le mois de `avant_le`."""
    lignes = (
        supabase_client.table("payslips")
        .select("year, month, payslip_data")
        .eq("employee_id", employee_id)
        .gte("year", avant_le.year - 2)
        .lte("year", avant_le.year)
        .execute()
        .data
    ) or []
    mois: List[MoisDeSalaire] = []
    for ligne in lignes:
        annee, numero = int(ligne.get("year") or 0), int(ligne.get("month") or 0)
        if (annee, numero) >= (avant_le.year, avant_le.month):
            continue
        donnees = ligne.get("payslip_data")
        if not isinstance(donnees, dict):
            continue
        mois.append(mois_de_salaire_du_bulletin(annee, numero, donnees))
    return sorted(mois)[-nombre:]
