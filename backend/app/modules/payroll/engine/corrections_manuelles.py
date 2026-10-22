"""Les corrections faites à la main sur un bulletin.

Étape 1 : la régularisation de cotisation. Elle ne retouche pas une ligne
calculée. Elle s'ajoute au bloc des cotisations, rattachée à l'organisme de la
ligne qu'elle régularise (son coti_id), avec sa base et son taux, au centime
comme le moteur. Une cotisation sans taux (forfait, réduction générale) se
régularise par son montant. Elle vit comme une saisie du mois : le moteur la
rejoue à chaque calcul, et elle passe dans le net, les cumuls, la DSN et les
exports comme toute ligne.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from app.modules.payroll.engine.cotisations_rubriques import enrichir_ligne_cotisation

TYPE_REGULARISATION_COTISATION = "regularisation_cotisation"
CLE_REGULARISATIONS_COTISATION = "regularisations_cotisation"
PREFIXE_LIBELLE = "Régularisation – "
COTI_ID_REDUCTION_GENERALE = "reduction_generale"


class RegularisationInvalide(ValueError):
    """Une régularisation qu'on ne peut pas appliquer telle quelle."""


def _nombre(valeur: Any) -> float | None:
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class RegularisationCotisation:
    coti_id: str
    libelle: str
    motif: str
    base: float | None = None
    taux_salarial: float | None = None
    taux_patronal: float | None = None
    montant_salarial: float | None = None
    montant_patronal: float | None = None
    saisie_id: str | None = None

    def __post_init__(self) -> None:
        if not self.coti_id.strip():
            raise RegularisationInvalide("Choisissez la cotisation à régulariser.")
        if not self.libelle.strip():
            raise RegularisationInvalide("La cotisation à régulariser n'a pas de libellé.")
        if len(self.motif.strip()) < 3:
            raise RegularisationInvalide("Écrivez le motif de la régularisation.")
        par_taux = self.base is not None
        au_montant = self.montant_salarial is not None or self.montant_patronal is not None
        if par_taux == au_montant:
            raise RegularisationInvalide(
                "Une régularisation porte soit une base avec le taux de la cotisation, "
                "soit un montant pour une cotisation sans taux, jamais les deux."
            )
        if par_taux and not (self.taux_salarial or self.taux_patronal):
            raise RegularisationInvalide(
                "Une régularisation par la base porte le taux de la cotisation."
            )

    @property
    def par_taux(self) -> bool:
        return self.base is not None

    def montants(self) -> tuple[float, float]:
        """(salarial, patronal), arrondis au centime comme le moteur."""
        if self.par_taux:
            base = float(self.base or 0.0)
            return (
                round(base * float(self.taux_salarial or 0.0), 2),
                round(base * float(self.taux_patronal or 0.0), 2),
            )
        return (
            round(float(self.montant_salarial or 0.0), 2),
            round(float(self.montant_patronal or 0.0), 2),
        )

    def charge_utile(self) -> dict[str, Any]:
        """Ce qui s'enregistre dans monthly_inputs.correction_ligne."""
        return {
            "type": TYPE_REGULARISATION_COTISATION,
            "coti_id": self.coti_id,
            "libelle": self.libelle,
            "motif": self.motif.strip(),
            "base": self.base,
            "taux_salarial": self.taux_salarial,
            "taux_patronal": self.taux_patronal,
            "montant_salarial": self.montant_salarial,
            "montant_patronal": self.montant_patronal,
        }

    @classmethod
    def depuis(
        cls, donnees: Mapping[str, Any], saisie_id: str | None = None
    ) -> RegularisationCotisation:
        identifiant = saisie_id or donnees.get("saisie_id")
        return cls(
            coti_id=str(donnees.get("coti_id") or ""),
            libelle=str(donnees.get("libelle") or ""),
            motif=str(donnees.get("motif") or ""),
            base=_nombre(donnees.get("base")),
            taux_salarial=_nombre(donnees.get("taux_salarial")),
            taux_patronal=_nombre(donnees.get("taux_patronal")),
            montant_salarial=_nombre(donnees.get("montant_salarial")),
            montant_patronal=_nombre(donnees.get("montant_patronal")),
            saisie_id=str(identifiant) if identifiant else None,
        )

    def saisie_du_mois(self, periode: Mapping[str, Any]) -> dict[str, Any]:
        """La ligne monthly_inputs qui porte la régularisation."""
        return {
            **periode,
            "name": f"{PREFIXE_LIBELLE}{self.libelle}"[:120],
            "description": self.motif.strip(),
            "amount": 0,
            "is_socially_taxed": False,
            "is_taxable": False,
            "correction_ligne": self.charge_utile(),
        }

    def ligne_de_cotisation(self) -> dict[str, Any]:
        salarial, patronal = self.montants()
        ligne = {
            "libelle": f"{PREFIXE_LIBELLE}{self.libelle}",
            "base": self.base,
            "taux_salarial": self.taux_salarial if self.par_taux else None,
            "montant_salarial": salarial,
            "taux_patronal": self.taux_patronal if self.par_taux else None,
            "montant_patronal": patronal,
            "explication": f"Régularisation saisie à la main : {self.motif.strip()}",
            "regularisation": {**self.charge_utile(), "saisie_id": self.saisie_id},
        }
        return enrichir_ligne_cotisation(ligne, coti_id=self.coti_id)


def est_regularisation_cotisation(saisie: Mapping[str, Any]) -> bool:
    correction = saisie.get("correction_ligne")
    return isinstance(correction, Mapping) and correction.get("type") == TYPE_REGULARISATION_COTISATION


def ranger_regularisation(saisie: Mapping[str, Any], saisies_data: dict[str, Any]) -> bool:
    """Range une régularisation à part des primes. Dit si la saisie en était une."""
    if not est_regularisation_cotisation(saisie):
        return False
    entree = dict(saisie["correction_ligne"])
    if saisie.get("id"):
        entree["saisie_id"] = str(saisie["id"])
    saisies_data.setdefault(CLE_REGULARISATIONS_COTISATION, []).append(entree)
    return True


def lignes_de_regularisation(entrees: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    return [RegularisationCotisation.depuis(e).ligne_de_cotisation() for e in entrees or []]


@dataclass(frozen=True)
class EffetDesRegularisations:
    total_salarial: float
    reduction_generale: float


def ajouter_regularisations(
    lignes_cotisations: list[dict[str, Any]],
    total_salarial: float,
    saisie_du_mois: Mapping[str, Any],
) -> EffetDesRegularisations:
    """Pose les régularisations du mois dans le bloc des cotisations, en place."""
    lignes = lignes_de_regularisation(saisie_du_mois.get(CLE_REGULARISATIONS_COTISATION))
    lignes_cotisations.extend(lignes)
    return EffetDesRegularisations(
        total_salarial=round(
            float(total_salarial or 0.0) + sum(ligne["montant_salarial"] for ligne in lignes),
            2,
        ),
        reduction_generale=round(
            sum(
                ligne["montant_patronal"]
                for ligne in lignes
                if ligne.get("coti_id") == COTI_ID_REDUCTION_GENERALE
            ),
            2,
        ),
    )


def regularisations_du_bulletin(
    payslip_data: Mapping[str, Any] | None,
) -> dict[str, RegularisationCotisation]:
    """Les régularisations imprimées sur un bulletin, par identifiant de saisie."""
    trouvees: dict[str, RegularisationCotisation] = {}
    for rubrique in (payslip_data or {}).get("cotisations_officielles") or []:
        if not isinstance(rubrique, Mapping):
            continue
        for ligne in rubrique.get("lignes") or []:
            regul = ligne.get("regularisation") if isinstance(ligne, Mapping) else None
            if isinstance(regul, Mapping) and regul.get("saisie_id"):
                trouvees[str(regul["saisie_id"])] = RegularisationCotisation.depuis(regul)
    return trouvees


def mentions_des_regularisations(payslip_data: Mapping[str, Any] | None) -> list[str]:
    return [
        f"Régularisation saisie à la main — {regul.libelle} : {regul.motif}"
        for regul in regularisations_du_bulletin(payslip_data).values()
    ]
