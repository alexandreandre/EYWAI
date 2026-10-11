"""Prime de partage de la valeur (PPV) : où elle va sur le bulletin.

Règles (loi n° 2022-1158 art. 1, modifiée par la loi n° 2023-1107 ; BOSS,
« Mesures exceptionnelles — protection du pouvoir d'achat » ; Urssaf, page
« Prime de partage de la valeur », mise à jour du 07/09/2026) :

- Exonérée de cotisations dans la limite de 3 000 € par an et par salarié
  (6 000 € quand l'employeur a un accord d'intéressement), en deux primes au
  plus par année civile. Au-delà, la part en trop est soumise comme du salaire.
- Du 01/01/2024 au 31/12/2026, elle est aussi exonérée d'impôt, de CSG/CRDS et
  de forfait social dans les entreprises de moins de 50 salariés, pour les
  salariés payés moins de 3 Smic sur les 12 mois précédant le versement.
- Sinon : CSG/CRDS sur la totalité (9,7 %, sans abattement), imposable, et
  forfait social de 20 % dans les entreprises d'au moins 250 salariés.

L'effectif est celui des seuils (`app.shared.domain.effectif_seuils`), jamais
le nombre de comptes de la société.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List

from app.modules.participation.domain.bulletin_rules import compute_participation_csg

PLAFOND_ANNUEL = 3000.0
PLAFOND_ANNUEL_AVEC_INTERESSEMENT = 6000.0
NOMBRE_DE_PRIMES_EXONEREES = 2
SEUIL_EFFECTIF_EXONERATION_TOTALE = 50
SEUIL_SMIC_EXONERATION_TOTALE = 3.0
#: Dernière année de l'exonération d'impôt, de CSG/CRDS et de forfait social
#: (loi n° 2023-1107, art. 9).
DERNIERE_ANNEE_EXONERATION_TOTALE = 2026
SEUIL_EFFECTIF_FORFAIT_SOCIAL = 250
TAUX_FORFAIT_SOCIAL = 0.20

LIBELLE = "Prime de partage de la valeur"


def _sans_accents(texte: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c)
    ).lower()


def est_une_ppv(prime_id: Any, libelle: Any) -> bool:
    """La PPV, qu'elle vienne du catalogue ou qu'elle soit saisie par son nom."""
    if str(prime_id or "") == "prime_partage_valeur":
        return True
    texte = _sans_accents(f"{prime_id or ''} {libelle or ''}").replace("_", " ")
    if "partage de la valeur" in texte or "prime de partage" in texte:
        return True
    return "ppv" in texte.split() or any(mot.startswith("ppv") for mot in texte.split())


@dataclass
class PpvRangee:
    non_soumises: List[Dict[str, Any]] = field(default_factory=list)
    soumises_impot: List[Dict[str, Any]] = field(default_factory=list)
    soumises: List[Dict[str, Any]] = field(default_factory=list)
    lignes_cotisations: List[Dict[str, Any]] = field(default_factory=list)
    alertes: List[Dict[str, Any]] = field(default_factory=list)


def _lignes_csg(libelle: str, montant: float, ded: float, non_ded: float) -> List[Dict[str, Any]]:
    # `is_ppv` : ces lignes ne portent pas sur le salaire ; le net imposable et
    # le net à payer les lisent sur la prime elle-même (cf. calcul_net).
    return [
        {
            "libelle": f"CSG déductible — {libelle}",
            "base": montant,
            "taux_salarial": 0.068,
            "taux_patronal": 0.0,
            "montant_salarial": ded,
            "montant_patronal": 0.0,
            "is_ppv": True,
        },
        {
            "libelle": f"CSG/CRDS non déductible — {libelle}",
            "base": montant,
            "taux_salarial": 0.029,
            "taux_patronal": 0.0,
            "montant_salarial": non_ded,
            "montant_patronal": 0.0,
            "is_ppv": True,
        },
    ]


def classer_ppv(
    prime: Dict[str, Any],
    *,
    effectif: int,
    donnees: Dict[str, Any] | None,
    smic_horaire: float,
    heures_mensuelles: float,
    annee: int,
) -> PpvRangee:
    """Range une PPV non soumise à cotisations selon les règles ci-dessus.

    `donnees` (lues par le générateur) : `deja_versees`, les montants des PPV
    déjà versées dans l'année, que la prime rangée rejoint (une deuxième PPV du
    même mois compte la première) ; `remuneration_mensuelle_moyenne` des 12 mois
    précédents (None : inconnue, le salaire du mois en tient lieu côté appelant) ;
    `accord_interessement`.
    """
    donnees = donnees if donnees is not None else {}
    deja = donnees.setdefault("deja_versees", [])
    montant = round(float(prime.get("montant") or 0.0), 2)
    libelle = str(prime.get("libelle") or LIBELLE)
    rangee = PpvRangee()
    if montant <= 0:
        rangee.non_soumises.append(dict(prime))
        return rangee

    plafond = (
        PLAFOND_ANNUEL_AVEC_INTERESSEMENT
        if donnees.get("accord_interessement")
        else PLAFOND_ANNUEL
    )
    rang = len(deja) + 1
    if rang > NOMBRE_DE_PRIMES_EXONEREES:
        exoneree = 0.0
        rangee.alertes.append(
            {
                "code": "ppv_nombre_de_primes",
                "severity": "warning",
                "message": (
                    f"{libelle} : c'est la {rang}e prime de partage de la valeur de "
                    f"{annee}. Seules deux primes par an sont exonérées : celle-ci "
                    "est soumise comme du salaire."
                ),
            }
        )
    else:
        exoneree = round(max(0.0, min(montant, plafond - sum(deja))), 2)
    soumise = round(montant - exoneree, 2)
    if soumise > 0 and rang <= NOMBRE_DE_PRIMES_EXONEREES:
        rangee.alertes.append(
            {
                "code": "ppv_plafond_annuel",
                "severity": "warning",
                "message": (
                    f"{libelle} : le plafond annuel d'exonération de "
                    f"{plafond:,.0f} €".replace(",", " ")
                    + f" est dépassé ({sum(deja) + montant:.2f} € versés en {annee}). "
                    f"{soumise:.2f} € sont soumis comme du salaire."
                ),
            }
        )
    deja.append(montant)

    if exoneree > 0:
        part = {**prime, "montant": exoneree}
        moyenne = donnees.get("remuneration_mensuelle_moyenne")
        trois_smic = SEUIL_SMIC_EXONERATION_TOTALE * float(smic_horaire or 0) * float(
            heures_mensuelles or 0
        )
        sous_trois_smic = moyenne is None or trois_smic <= 0 or float(moyenne) < trois_smic
        exoneration_totale = (
            annee <= DERNIERE_ANNEE_EXONERATION_TOTALE
            and int(effectif or 0) < SEUIL_EFFECTIF_EXONERATION_TOTALE
            and sous_trois_smic
        )
        if exoneration_totale:
            rangee.non_soumises.append(part)
        else:
            non_ded, ded, _ = compute_participation_csg(exoneree)
            part["csg_deductible"] = float(ded)
            part["csg_non_deductible"] = float(non_ded)
            rangee.soumises_impot.append(part)
            rangee.lignes_cotisations.extend(
                _lignes_csg(libelle, exoneree, float(ded), float(non_ded))
            )
            if int(effectif or 0) >= SEUIL_EFFECTIF_FORFAIT_SOCIAL:
                rangee.lignes_cotisations.append(
                    {
                        "libelle": f"Forfait social — {libelle}",
                        "base": exoneree,
                        "taux_salarial": 0.0,
                        "taux_patronal": TAUX_FORFAIT_SOCIAL,
                        "montant_salarial": 0.0,
                        "montant_patronal": round(exoneree * TAUX_FORFAIT_SOCIAL, 2),
                        "rubrique": "autres_contributions_employeur",
                        "is_ppv": True,
                    }
                )
    if soumise > 0:
        rangee.soumises.append(
            {**prime, "montant": soumise, "libelle": f"{libelle} (part non exonérée)"}
        )
    return rangee
