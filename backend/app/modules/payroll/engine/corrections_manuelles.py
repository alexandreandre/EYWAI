"""Les corrections faites à la main sur un bulletin.

Étape 1 : la régularisation de cotisation. Elle ne retouche pas une ligne
calculée. Elle s'ajoute au bloc des cotisations, rattachée à l'organisme de la
ligne qu'elle régularise (son coti_id), avec sa base et son taux, au centime
comme le moteur. Une cotisation sans taux (forfait, réduction générale) se
régularise par son montant. Elle vit comme une saisie du mois : le moteur la
rejoue à chaque calcul, et elle passe dans le net, les cumuls, la DSN et les
exports comme toute ligne.

Étape 2 : la correction directe d'une ligne. Elle vise une ligne par son code
(`codes_des_lignes`) et porte sa base, son taux ou son montant selon la règle
3. Le moteur la pose là où la ligne naît (`LignesCorrigees`), avant tout ce qui
en dérive ; la ligne garde son libellé, porte la trace de la correction et la
valeur que Martine avait calculée. Une correction qui ne trouve pas sa ligne
reste en attente sur le bulletin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, Iterable, Mapping

from app.modules.payroll.engine.codes_des_lignes import (
    BLOC_BRUT,
    BLOC_COTISATIONS,
    BLOC_IMPOT,
    CODE_IMPOT,
    MODE_BASE_OU_TAUX,
    MODE_MONTANT,
    MODE_TAUX,
    Numerotation,
    champ_du_montant,
    code_de_ligne_de_cotisation,
    code_de_ligne_de_gain,
    famille_du_code,
    mode_de_correction,
)
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


# --- Étape 2 : la correction directe d'une ligne ----------------------------

TYPE_CORRECTION = "correction"
CLE_CORRECTIONS_LIGNE = "corrections_ligne"
CLE_CORRECTIONS_EN_ATTENTE = "corrections_en_attente"
PREFIXE_SAISIE_CORRECTION = "Correction – "

RAISON_LIGNE_ABSENTE = (
    "La ligne visée n'est plus sur le bulletin : sa source a changé. Retirez la "
    "correction ou reportez-la sur une autre ligne."
)

RAISON_DEUX_CORRECTIONS = (
    "Une autre correction vise déjà cette ligne : retirez l'une des deux."
)
RAISON_LIGNE_DEPLACEE = (
    "La correction s'est posée sur une autre ligne de même libellé : vérifiez la "
    "ligne, retirez la correction et refaites-la."
)

#: Comment la ligne se corrige, pour les messages.
PAR_MODE = {
    MODE_BASE_OU_TAUX: "sa base ou son taux",
    MODE_MONTANT: "son montant",
    MODE_TAUX: "son taux",
}

_VALEURS = (
    "base",
    "taux",
    "montant",
    "taux_salarial",
    "taux_patronal",
    "montant_salarial",
    "montant_patronal",
)
_CHAMPS_DE_MONTANT = frozenset({"montant", "montant_salarial", "montant_patronal"})
_CHAMPS_PAR_BLOC = {
    BLOC_BRUT: frozenset({"base", "taux", "montant"}),
    BLOC_COTISATIONS: frozenset(
        {"base", "taux_salarial", "taux_patronal", "montant_salarial", "montant_patronal"}
    ),
    BLOC_IMPOT: frozenset({"taux"}),
}
_CHAMPS_PERMIS = {
    (BLOC_BRUT, MODE_BASE_OU_TAUX): frozenset({"base", "taux"}),
    (BLOC_BRUT, MODE_MONTANT): frozenset({"montant"}),
    (BLOC_COTISATIONS, MODE_BASE_OU_TAUX): frozenset({"base", "taux_salarial", "taux_patronal"}),
    (BLOC_COTISATIONS, MODE_MONTANT): frozenset({"montant_salarial", "montant_patronal"}),
    (BLOC_IMPOT, MODE_TAUX): frozenset({"taux"}),
}


class CorrectionInvalide(ValueError):
    """Une correction qu'on ne peut ni enregistrer ni appliquer telle quelle."""


def bloc_du_code(code: str) -> str | None:
    if code == CODE_IMPOT:
        return BLOC_IMPOT
    if code.startswith("brut:"):
        return BLOC_BRUT
    if code.startswith("cotisation:"):
        return BLOC_COTISATIONS
    return None


def _zero_si_vide(valeur: Any) -> float:
    nombre = _nombre(valeur)
    return 0.0 if nombre is None else nombre


@dataclass(frozen=True)
class CorrectionDeLigne:
    ligne: str
    libelle: str
    motif: str
    base: float | None = None
    taux: float | None = None
    montant: float | None = None
    taux_salarial: float | None = None
    taux_patronal: float | None = None
    montant_salarial: float | None = None
    montant_patronal: float | None = None
    saisie_id: str | None = None

    def __post_init__(self) -> None:
        if not self.ligne.strip():
            raise CorrectionInvalide("Choisissez la ligne à corriger.")
        if not self.libelle.strip():
            raise CorrectionInvalide("La ligne à corriger n'a pas de libellé.")
        if len(self.motif.strip()) < 3:
            raise CorrectionInvalide("Écrivez le motif de la correction.")
        bloc = bloc_du_code(self.ligne)
        if bloc is None:
            raise CorrectionInvalide("Martine ne connaît pas cette ligne.")
        champs = self.champs
        if not champs:
            raise CorrectionInvalide("Tapez la valeur voulue.")
        if not champs <= _CHAMPS_PAR_BLOC[bloc]:
            raise CorrectionInvalide("Ces valeurs ne se corrigent pas sur cette ligne.")
        if champs & _CHAMPS_DE_MONTANT and champs - _CHAMPS_DE_MONTANT:
            raise CorrectionInvalide(
                "Une correction porte une base ou un taux, ou bien un montant, jamais les deux."
            )
        if bloc == BLOC_IMPOT and not 0.0 <= float(self.taux or 0.0) <= 100.0:
            raise CorrectionInvalide("Le taux d'impôt se tape en pourcentage, entre 0 et 100.")

    @property
    def bloc(self) -> str:
        return bloc_du_code(self.ligne) or ""

    @property
    def cle(self) -> tuple[str, str]:
        """La saisie qui porte la correction et la ligne qu'elle vise."""
        return cle_de_correction(self.trace())

    @property
    def champs(self) -> frozenset[str]:
        return frozenset(nom for nom in _VALEURS if getattr(self, nom) is not None)

    @property
    def par_montant(self) -> bool:
        return bool(self.champs & _CHAMPS_DE_MONTANT)

    def convient(self, mode: str | None) -> bool:
        permis = _CHAMPS_PERMIS.get((self.bloc, mode))
        return permis is not None and self.champs <= permis

    def charge_utile(self) -> dict[str, Any]:
        """Ce qui s'enregistre dans monthly_inputs.correction_ligne."""
        charge: dict[str, Any] = {
            "type": TYPE_CORRECTION,
            "ligne": self.ligne,
            "libelle": self.libelle,
            "motif": self.motif.strip(),
        }
        charge.update({nom: getattr(self, nom) for nom in _VALEURS if getattr(self, nom) is not None})
        return charge

    def trace(self) -> dict[str, Any]:
        """Ce que porte la ligne corrigée : la correction et la saisie qui la porte."""
        return {**self.charge_utile(), "saisie_id": self.saisie_id}

    @classmethod
    def depuis(cls, donnees: Mapping[str, Any], saisie_id: str | None = None) -> CorrectionDeLigne:
        identifiant = saisie_id or donnees.get("saisie_id")
        return cls(
            ligne=str(donnees.get("ligne") or ""),
            libelle=str(donnees.get("libelle") or ""),
            motif=str(donnees.get("motif") or ""),
            **{nom: _nombre(donnees.get(nom)) for nom in _VALEURS},
            saisie_id=str(identifiant) if identifiant else None,
        )

    def saisie_du_mois(self, periode: Mapping[str, Any]) -> dict[str, Any]:
        """La ligne monthly_inputs qui porte la correction."""
        return {
            **periode,
            "name": f"{PREFIXE_SAISIE_CORRECTION}{self.libelle}"[:120],
            "description": self.motif.strip(),
            "amount": 0,
            "is_socially_taxed": False,
            "is_taxable": False,
            "correction_ligne": self.charge_utile(),
        }


def cle_de_correction(trace: Mapping[str, Any]) -> tuple[str, str]:
    """La clé d'une correction, lue sur sa trace : la saisie qui la porte et la ligne qu'elle vise."""
    return (str(trace.get("saisie_id") or ""), str(trace.get("ligne") or ""))


def est_correction_de_ligne(saisie: Mapping[str, Any]) -> bool:
    correction = saisie.get("correction_ligne")
    return isinstance(correction, Mapping) and correction.get("type") == TYPE_CORRECTION


def ranger_correction_manuelle(saisie: Mapping[str, Any], saisies_data: dict[str, Any]) -> bool:
    """Range une régularisation ou une correction de ligne à part des primes.

    Dit si la saisie en était une : elle n'est alors pas une prime du bulletin.
    """
    if ranger_regularisation(saisie, saisies_data):
        return True
    if not est_correction_de_ligne(saisie):
        return False
    entree = dict(saisie["correction_ligne"])
    if saisie.get("id"):
        entree["saisie_id"] = str(saisie["id"])
    saisies_data.setdefault(CLE_CORRECTIONS_LIGNE, []).append(entree)
    return True


@dataclass(frozen=True)
class EffetUnitaire:
    famille: str
    quantite: float = 0.0
    brut: float = 0.0
    salarial: float = 0.0
    patronal: float = 0.0


@dataclass
class EffetDesCorrections:
    """Ce que les corrections d'un lot de lignes ont changé, par famille de ligne."""

    corrigees: int = 0
    salarial: float = 0.0
    patronal: float = 0.0
    _quantites: dict[str, float] = field(default_factory=dict)
    _brut: dict[str, float] = field(default_factory=dict)

    def ajouter(self, effet: EffetUnitaire | None) -> None:
        if effet is None:
            return
        self.corrigees += 1
        self.salarial = round(self.salarial + effet.salarial, 2)
        self.patronal = round(self.patronal + effet.patronal, 2)
        self._quantites[effet.famille] = self._quantites.get(effet.famille, 0.0) + effet.quantite
        self._brut[effet.famille] = round(self._brut.get(effet.famille, 0.0) + effet.brut, 2)

    def quantite(self, *familles: str) -> float:
        return round(sum((self._quantites.get(f, 0.0) for f in familles), 0.0), 4)

    def sur_le_brut(self, *familles: str) -> float:
        return round(sum((self._brut.get(f, 0.0) for f in familles), 0.0), 2)


#: Les valeurs d'une ligne qu'une correction peut changer ; `valeur_calculee` les garde.
_VALEURS_DE_LIGNE = {
    BLOC_BRUT: ("quantite", "taux", "gain", "perte"),
    BLOC_COTISATIONS: ("base", "taux_salarial", "taux_patronal", "montant_salarial", "montant_patronal"),
}


def _corriger_un_gain(ligne: dict[str, Any], correction: CorrectionDeLigne) -> None:
    champ = champ_du_montant(ligne)
    if correction.montant is not None:
        ligne[champ] = round(float(correction.montant), 2)
    else:
        quantite = correction.base if correction.base is not None else _zero_si_vide(ligne.get("quantite"))
        taux = correction.taux if correction.taux is not None else _zero_si_vide(ligne.get("taux"))
        ligne["quantite"] = quantite
        ligne["taux"] = taux
        ligne[champ] = round(float(quantite) * float(taux), 2)


def _corriger_une_cotisation(ligne: dict[str, Any], correction: CorrectionDeLigne) -> None:
    if correction.par_montant:
        if correction.montant_salarial is not None:
            ligne["montant_salarial"] = round(float(correction.montant_salarial), 2)
        if correction.montant_patronal is not None:
            ligne["montant_patronal"] = round(float(correction.montant_patronal), 2)
        return
    base = correction.base if correction.base is not None else _zero_si_vide(ligne.get("base"))
    if correction.taux_salarial is not None:
        ligne["taux_salarial"] = correction.taux_salarial
    if correction.taux_patronal is not None:
        ligne["taux_patronal"] = correction.taux_patronal
    ligne["base"] = base
    # Le même arrondi que `calcul_cotisations._calculer_une_ligne`.
    if ligne.get("taux_salarial") is not None:
        ligne["montant_salarial"] = round(float(base) * float(ligne["taux_salarial"]), 2)
    if ligne.get("taux_patronal") is not None:
        ligne["montant_patronal"] = round(float(base) * float(ligne["taux_patronal"]), 2)


def _effet(
    bloc: str, correction: CorrectionDeLigne, avant: Mapping[str, Any], ligne: Mapping[str, Any]
) -> EffetUnitaire:
    """Ce que la ligne a changé depuis `avant` : quantité et brut d'un gain, parts d'une cotisation."""

    def ecart(cle: str) -> float:
        return _zero_si_vide(ligne.get(cle)) - _zero_si_vide(avant.get(cle))

    famille = famille_du_code(correction.ligne)
    if bloc == BLOC_BRUT:
        return EffetUnitaire(famille=famille, quantite=ecart("quantite"), brut=round(ecart("gain") - ecart("perte"), 2))
    return EffetUnitaire(
        famille=famille, salarial=round(ecart("montant_salarial"), 2), patronal=round(ecart("montant_patronal"), 2)
    )


def _appliquer(ligne: dict[str, Any], bloc: str, correction: CorrectionDeLigne) -> EffetUnitaire:
    """Pose la correction ; la ligne garde la valeur que Martine avait calculée."""
    avant = {cle: ligne.get(cle) for cle in _VALEURS_DE_LIGNE[bloc]}
    if bloc == BLOC_BRUT:
        _corriger_un_gain(ligne, correction)
    else:
        _corriger_une_cotisation(ligne, correction)
    ligne["valeur_calculee"] = avant
    ligne["correction"] = correction.trace()
    return _effet(bloc, correction, avant, ligne)


def _cle_portee(ligne: Mapping[str, Any]) -> tuple[str, str] | None:
    portee = ligne.get("correction")
    return cle_de_correction(portee) if isinstance(portee, Mapping) else None


class JournalDesCorrections:
    """Les corrections du mois, et ce que le calcul en a fait.

    Le journal ne se consomme pas. Chaque calcul qui pose ses lignes y retrouve
    les mêmes corrections : un second calcul avec le même contexte les rejoue à
    l'identique. Une ligne qui porte déjà sa correction ne la prend jamais deux
    fois ; retouchée par le calcul après son entrée, elle la retrouve. Une
    correction qu'aucune ligne du bulletin ne porte finit en attente (règle 7).
    """

    def __init__(self, corrections: Iterable[CorrectionDeLigne]) -> None:
        self._corrections: list[CorrectionDeLigne] = []
        self._par_cle: dict[tuple[str, str], CorrectionDeLigne] = {}
        self._par_code: dict[str, CorrectionDeLigne] = {}
        self._raisons: dict[tuple[str, str], str] = {}
        self._posees: set[tuple[str, str]] = set()
        for correction in corrections:
            if correction.cle in self._par_cle:
                continue  # la même saisie, lue deux fois
            self._corrections.append(correction)
            self._par_cle[correction.cle] = correction
            if correction.ligne in self._par_code:
                # Une correction par ligne (décision 11) : la seconde attend qu'on en retire une.
                self._raisons[correction.cle] = RAISON_DEUX_CORRECTIONS
            else:
                self._par_code[correction.ligne] = correction

    @classmethod
    def depuis(cls, saisie_du_mois: Mapping[str, Any]) -> JournalDesCorrections | None:
        entrees = saisie_du_mois.get(CLE_CORRECTIONS_LIGNE) or []
        if not entrees:
            return None
        return cls(CorrectionDeLigne.depuis(entree) for entree in entrees)

    def prendre(self, code: str | None) -> CorrectionDeLigne | None:
        """La correction qui vise ce code. Elle reste au journal : un autre calcul la retrouve."""
        return self._par_code.get(code) if code else None

    def refuser(self, correction: CorrectionDeLigne, raison: str) -> None:
        self._raisons[correction.cle] = raison

    def noter_posee(self, correction: CorrectionDeLigne) -> None:
        self._posees.add(correction.cle)

    def corriger(
        self, ligne: Any, bloc: str, code: str | None, deja: Collection[tuple[str, str]] = ()
    ) -> EffetUnitaire | None:
        """Pose sur la ligne la correction qui la vise, s'il y en a une.

        `deja` : les corrections que d'autres lignes du même lot portent déjà ;
        elles ne se posent pas une seconde fois.
        """
        if not isinstance(ligne, dict):
            return None
        if ligne.get("correction") is not None:
            cle = _cle_portee(ligne)
            correction = self._par_cle.get(cle) if cle else None
            return None if correction is None else self._reaffirmer(ligne, bloc, correction)
        correction = self.prendre(code)
        if correction is None or correction.cle in deja:
            return None
        mode, raison = mode_de_correction(bloc, ligne, code)
        if mode is None:
            self.refuser(correction, raison or RAISON_LIGNE_ABSENTE)
            return None
        if not correction.convient(mode):
            self.refuser(correction, f"La ligne se corrige par {PAR_MODE[mode]} : refaites la correction.")
            return None
        self.noter_posee(correction)
        return _appliquer(ligne, bloc, correction)

    def _reaffirmer(self, ligne: dict[str, Any], bloc: str, correction: CorrectionDeLigne) -> EffetUnitaire | None:
        """Une ligne qui porte déjà sa correction ne la prend pas deux fois.

        Si le calcul l'a retouchée après son entrée, ce qu'il a retouché devient
        la valeur de Martine, et la correction se pose à nouveau par-dessus.
        """
        self.noter_posee(correction)
        cles = _VALEURS_DE_LIGNE.get(bloc)
        if cles is None:
            return None
        martine = dict(ligne.get("valeur_calculee") or {})
        posee = {**ligne, **martine}
        _appliquer(posee, bloc, correction)
        retouchees = {cle: ligne.get(cle) for cle in cles if ligne.get(cle) != posee.get(cle)}
        if not retouchees:
            return None
        avant = {cle: ligne.get(cle) for cle in cles}
        ligne.update({**martine, **retouchees})
        _appliquer(ligne, bloc, correction)
        return _effet(bloc, correction, avant, ligne)

    def en_attente(self, portees: Mapping[tuple[str, str], Collection[str]] | None = None) -> list[dict[str, Any]]:
        """Les corrections qui n'ont pas trouvé leur ligne, avec la raison.

        Sans `portees`, celles que le calcul n'a posées sur aucune ligne. Avec
        les codes des lignes du bulletin qui portent chaque correction, celles
        que le bulletin ne porte pas sous leur code : c'est lui qui fait foi.
        """
        sortie = []
        for correction in self._corrections:
            cle = correction.cle
            raison = self._raisons.get(cle)
            if raison != RAISON_DEUX_CORRECTIONS:
                if portees is None:
                    if cle in self._posees:
                        continue
                    raison = raison or RAISON_LIGNE_ABSENTE
                else:
                    codes = portees.get(cle) or ()
                    if correction.ligne in codes:
                        continue
                    raison = RAISON_LIGNE_DEPLACEE if codes else (raison or RAISON_LIGNE_ABSENTE)
            sortie.append({**correction.trace(), "raison": raison})
        return sortie


def journal_du_contexte(contexte: Any) -> JournalDesCorrections | None:
    journal = getattr(contexte, "corrections_du_mois", None)
    return journal if isinstance(journal, JournalDesCorrections) else None


class LignesCorrigees(list):
    """Les lignes d'un calcul, chacune corrigée à son entrée si une correction la vise.

    Les deux calculs du brut et celui des cotisations y posent leurs lignes : la
    correction s'applique là où la ligne naît, avant tout ce qui en dérive
    (précarité, indemnité compensatrice, heures sup, plafond de la réduction
    des heures sup, forfait social). Sans journal, c'est une liste ordinaire.
    """

    def __init__(self, journal: JournalDesCorrections | None, bloc: str, lignes: Iterable[Any] = ()) -> None:
        super().__init__()
        self.journal = journal
        self.bloc = bloc
        self.effet = EffetDesCorrections()
        self._numeros = Numerotation()
        self._portees: set[tuple[str, str]] = set()
        for ligne in lignes:
            self.append(ligne)

    def _poser(self, ligne: Any) -> Any:
        if self.journal is not None and isinstance(ligne, dict):
            code = self._numeros.code(self.bloc, ligne)
            self.effet.ajouter(self.journal.corriger(ligne, self.bloc, code, self._portees))
            cle = _cle_portee(ligne)
            if cle:
                self._portees.add(cle)
        return ligne

    def append(self, ligne: Any) -> None:
        super().append(self._poser(ligne))

    def extend(self, lignes: Iterable[Any]) -> None:
        for ligne in lignes:
            self.append(ligne)

    def insert(self, index: Any, ligne: Any) -> None:
        super().insert(index, self._poser(ligne))

    def __iadd__(self, lignes: Iterable[Any]) -> LignesCorrigees:
        self.extend(lignes)
        return self


def _corriger_les_lignes(lignes: Iterable[Any], journal: JournalDesCorrections | None, bloc: str) -> EffetDesCorrections:
    effet = EffetDesCorrections()
    if journal is None:
        return effet
    lignes = [ligne for ligne in lignes if isinstance(ligne, dict)]
    # Une correction qu'une ligne du lot porte déjà ne se pose pas sur une autre.
    portees = {cle for cle in map(_cle_portee, lignes) if cle}
    numeros = Numerotation()
    for ligne in lignes:
        effet.ajouter(journal.corriger(ligne, bloc, numeros.code(bloc, ligne), portees))
        cle = _cle_portee(ligne)
        if cle:
            portees.add(cle)
    return effet


def corriger_les_lignes_de_gain(lignes: Iterable[Any], journal: JournalDesCorrections | None) -> EffetDesCorrections:
    """Les lignes de gain posées après le calcul du brut (nuit, pause, maintien)."""
    return _corriger_les_lignes(lignes, journal, BLOC_BRUT)


def corriger_les_lignes_de_cotisation(
    lignes: Iterable[Any], journal: JournalDesCorrections | None
) -> EffetDesCorrections:
    """Les cotisations posées après `calculer_cotisations` (CSG des IJSS, JEI)."""
    return _corriger_les_lignes(lignes, journal, BLOC_COTISATIONS)


def recaler_le_sous_total(lignes: Iterable[Any]) -> None:
    """Le sous-total contractuel suit un salaire de base ou des heures structurelles corrigés."""
    lignes = [ligne for ligne in lignes if isinstance(ligne, dict)]
    composantes = [
        ligne
        for ligne in lignes
        if famille_du_code(code_de_ligne_de_gain(ligne)) in ("brut:salaire_base", "brut:hs_structurelles")
    ]
    if not any(ligne.get("correction") for ligne in composantes):
        return
    for ligne in lignes:
        if ligne.get("is_sous_total"):
            ligne["gain"] = round(sum(_zero_si_vide(c.get("gain")) for c in composantes), 2)
            ligne["quantite"] = round(sum(_zero_si_vide(c.get("quantite")) for c in composantes), 2)


def synchroniser_le_maintien(resultats_maintien: Any, lignes: Iterable[Any]) -> None:
    """Un maintien employeur corrigé devient le maintien versé (part des heures maintenues, détail du bulletin)."""
    if not isinstance(resultats_maintien, dict):
        return
    for ligne in lignes:
        if isinstance(ligne, dict) and ligne.get("is_maintien_employeur") and ligne.get("correction"):
            bloc = resultats_maintien.get("maintien")
            if not isinstance(bloc, dict):
                bloc = resultats_maintien["maintien"] = {}
            bloc["maintien_verse"] = _zero_si_vide(ligne.get("gain"))


def corriger_la_reduction_generale(
    ligne: dict[str, Any] | None, journal: JournalDesCorrections | None, reduction_deja: float
) -> dict[str, Any] | None:
    """La réduction générale du mois, corrigée par son montant.

    Son cumul enregistre ce qui est réellement appliqué (spec § 6) : le mois
    suivant régularise depuis là, comme le veut la loi.
    """
    if ligne is None or journal is None:
        return ligne
    if journal.corriger(ligne, BLOC_COTISATIONS, code_de_ligne_de_cotisation(ligne)) is None:
        return ligne
    appliquee = round(float(reduction_deja) - _zero_si_vide(ligne.get("montant_patronal")), 2)
    if appliquee < 0:
        raise CorrectionInvalide(
            "La réduction générale corrigée dépasse la réduction appliquée depuis janvier : "
            "la réduction de l'année deviendrait négative. Corrigez son montant."
        )
    ligne["valeur_cumulative_a_enregistrer"] = appliquee
    return ligne


def corriger_le_taux_d_impot(
    taux_calcule: float, base_pas: float, journal: JournalDesCorrections | None
) -> tuple[float, dict[str, Any] | None]:
    """Le taux d'impôt du mois, corrigé ; le montant suit (base × taux, au centime)."""
    if journal is None:
        return taux_calcule, None
    correction = journal.prendre(CODE_IMPOT)
    if correction is None:
        return taux_calcule, None
    if not correction.convient(MODE_TAUX):
        journal.refuser(correction, f"La ligne se corrige par {PAR_MODE[MODE_TAUX]} : refaites la correction.")
        return taux_calcule, None
    journal.noter_posee(correction)
    trace = {
        "correction": correction.trace(),
        "valeur_calculee": {
            "taux": taux_calcule,
            "montant": round(base_pas * (taux_calcule / 100.0), 2),
        },
    }
    return float(correction.taux), trace


def poser_les_corrections_en_attente(bulletin: dict[str, Any], journal: JournalDesCorrections | None) -> None:
    """Règle 7 : une correction sans ligne n'est jamais perdue en silence.

    Le bulletin fait foi : une correction est posée si une de ses lignes, lue
    comme l'écran et le PDF la lisent, la porte sous son code. Posée par un
    calcul que le bulletin n'a pas gardé, ou sur un autre doublon que le sien,
    elle reste en attente.
    """
    if journal is None:
        return
    # Import local : la lecture d'un bulletin importe ce module.
    from app.modules.payroll.engine.corrections_du_bulletin import lignes_corrigeables

    portees: dict[tuple[str, str], set[str]] = {}
    for ligne in lignes_corrigeables(bulletin):
        if ligne.correction and ligne.code:
            portees.setdefault(cle_de_correction(ligne.correction), set()).add(ligne.code)
    attente = journal.en_attente(portees)
    if attente:
        bulletin[CLE_CORRECTIONS_EN_ATTENTE] = attente
