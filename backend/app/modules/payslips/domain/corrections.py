"""Ce qui se corrige sur un bulletin : ses heures sup, ses primes du mois et ses régularisations de cotisation.

Un bulletin ne se corrige plus en retouchant ses lignes. Les montants retouchés
à la main laissaient les bases, les cotisations, le net et les cumuls de
l'ancien calcul (audit du 28/09). On corrige ses variables du mois, puis le
moteur recalcule le bulletin en entier. Le reste (planning, absences, salaire,
primes fixes) se corrige à sa source, sur son propre écran.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from app.modules.payroll.engine.corrections_du_bulletin import (
    corrections_du_bulletin,
    lignes_corrigeables,
    valeur_de_martine,
)
from app.modules.payroll.engine.corrections_manuelles import (
    COTI_ID_REDUCTION_GENERALE,
    PAR_MODE,
    CorrectionDeLigne,
    RegularisationCotisation,
    RegularisationHeures,
    regularisations_du_bulletin,
    regularisations_heures_du_bulletin,
)
from app.modules.payslips.domain.heures_sup import quantites_heures_sup_calculees
from app.modules.payslips.domain.primes_editees import (
    DiffPrimes,
    primes_saisies_du_bulletin,
)

_TOLERANCE = 0.005

CODE_REDUCTION_GENERALE = "cotisation:reduction_generale"
MESSAGE_REDUCTION_CORRIGEE_TROP_HAUT = (
    "La réduction générale corrigée dépasse la réduction appliquée depuis janvier : "
    "la réduction de l'année deviendrait négative. Corrigez son montant."
)
MESSAGE_REDUCTION_REGULARISEE_TROP_HAUT = (
    "La régularisation de la réduction générale dépasse la réduction appliquée depuis "
    "janvier : la réduction de l'année deviendrait négative. Corrigez son montant."
)


@dataclass(frozen=True)
class CorrectionsBulletin:
    #: (heures au premier palier, heures au second palier) déclarées depuis le
    #: bulletin ; elles priment sur le planning, même nulles.
    heures_sup: tuple[float, float] | None = None
    #: Retirer les heures sup déclarées depuis le bulletin : le planning refait foi.
    revenir_au_planning: bool = False
    primes: DiffPrimes = DiffPrimes()
    #: Régularisations de cotisation à ajouter, puis identifiants de saisie à retirer.
    regularisations_ajoutees: tuple[RegularisationCotisation, ...] = ()
    regularisations_retirees: tuple[str, ...] = ()
    #: Heures d'un autre mois à ajouter à ce bulletin, puis identifiants de saisie à retirer.
    regularisations_heures_ajoutees: tuple[RegularisationHeures, ...] = ()
    regularisations_heures_retirees: tuple[str, ...] = ()
    #: Corrections de ligne à ajouter, puis identifiants de saisie à retirer.
    corrections_ajoutees: tuple[CorrectionDeLigne, ...] = ()
    corrections_retirees: tuple[str, ...] = ()

    @property
    def change_des_variables(self) -> bool:
        return (
            self.heures_sup is not None
            or self.revenir_au_planning
            or not self.primes.vide
            or bool(self.regularisations_ajoutees)
            or bool(self.regularisations_retirees)
            or bool(self.regularisations_heures_ajoutees)
            or bool(self.regularisations_heures_retirees)
            or bool(self.corrections_ajoutees)
            or bool(self.corrections_retirees)
        )


def _heures(valeur: float) -> str:
    texte = f"{round(float(valeur), 2):.2f}".rstrip("0").rstrip(".")
    return texte.replace(".", ",")


def _euros(valeur: float) -> str:
    return f"{float(valeur):.2f}".replace(".", ",") + " €"


def resume_des_corrections(corrections: CorrectionsBulletin) -> str:
    """Une phrase pour l'historique quand la RH n'en a pas écrit."""
    parties: list[str] = []
    if corrections.revenir_au_planning:
        parties.append("heures sup du planning")
    if corrections.heures_sup is not None:
        hs25, hs50 = corrections.heures_sup
        parties.append(f"heures sup {_heures(hs25)} h à 25 % et {_heures(hs50)} h à 50 %")
    for prime in corrections.primes.ajoutees:
        parties.append(f"prime ajoutée « {prime.get('name')} » {_euros(prime.get('amount') or 0)}")
    if corrections.primes.modifiees:
        n = len(corrections.primes.modifiees)
        parties.append(f"{n} prime{'s' if n > 1 else ''} corrigée{'s' if n > 1 else ''}")
    if corrections.primes.retirees:
        n = len(corrections.primes.retirees)
        parties.append(f"{n} prime{'s' if n > 1 else ''} retirée{'s' if n > 1 else ''}")
    for regul in corrections.regularisations_ajoutees:
        parties.append(f"régularisation « {regul.libelle} » : {regul.motif}")
    if corrections.regularisations_retirees:
        n = len(corrections.regularisations_retirees)
        parties.append(f"{n} régularisation{'s' if n > 1 else ''} retirée{'s' if n > 1 else ''}")
    for regul in corrections.regularisations_heures_ajoutees:
        parties.append(f"régularisation de {_heures(regul.quantite)} h de {regul.mois_affiche} : {regul.motif}")
    if corrections.regularisations_heures_retirees:
        n = len(corrections.regularisations_heures_retirees)
        parties.append(f"{n} régularisation{'s' if n > 1 else ''} d'heures retirée{'s' if n > 1 else ''}")
    for correction in corrections.corrections_ajoutees:
        parties.append(f"ligne « {correction.libelle} » corrigée : {correction.motif}")
    if corrections.corrections_retirees:
        n = len(corrections.corrections_retirees)
        parties.append(f"{n} correction{'s' if n > 1 else ''} retirée{'s' if n > 1 else ''}")
    if not parties:
        return "Notes modifiées"
    texte = ", ".join(parties)
    return texte[0].upper() + texte[1:]


_NOMS_DES_TAUX = {"taux": "taux", "taux_salarial": "taux salarial", "taux_patronal": "taux patronal"}


def refus_des_corrections(corrections: CorrectionsBulletin, payslip_data: dict[str, Any] | None) -> str | None:
    """Pourquoi une correction ajoutée ne tient pas sur ce bulletin, ou None.

    La ligne doit exister, se corriger par les champs reçus (règle 3), porter le
    taux corrigé, et ne pas être déjà corrigée — sauf si sa correction est
    retirée dans le même enregistrement.
    """
    if not corrections.corrections_ajoutees:
        return None
    par_code = {ligne.code: ligne for ligne in lignes_corrigeables(payslip_data) if ligne.code}
    retirees = set(corrections.corrections_retirees)
    visees: set[str] = set()
    for correction in corrections.corrections_ajoutees:
        ligne = par_code.get(correction.ligne)
        if ligne is None:
            return f"La ligne « {correction.libelle} » n'est plus sur le bulletin : rechargez-le."
        if ligne.mode is None:
            return f"« {ligne.libelle} » : {ligne.raison}"
        if not correction.convient(ligne.mode):
            return f"« {ligne.libelle} » se corrige par {PAR_MODE[ligne.mode]}."
        for champ, nom in _NOMS_DES_TAUX.items():
            if getattr(correction, champ) is not None and getattr(ligne, champ) is None:
                return f"« {ligne.libelle} » n'a pas de {nom} : corrigez ce qu'elle porte."
        deja = (ligne.correction or {}).get("saisie_id")
        if deja and str(deja) not in retirees:
            return f"« {ligne.libelle} » est déjà corrigée : retirez d'abord sa correction."
        if correction.ligne in visees:
            return f"« {ligne.libelle} » est corrigée deux fois : gardez une seule correction."
        visees.add(correction.ligne)
    return None


MESSAGE_HEURES_AU_FORFAIT = (
    "Ce salarié est au forfait jours : son temps se compte en jours, "
    "il n'a pas d'heures à régulariser."
)


def refus_des_regularisations_heures(
    corrections: CorrectionsBulletin, year: int, month: int, *, forfait_jours: bool
) -> str | None:
    """Pourquoi une régularisation d'heures ajoutée ne tient pas sur ce bulletin, ou None."""
    if not corrections.regularisations_heures_ajoutees:
        return None
    if forfait_jours:
        return MESSAGE_HEURES_AU_FORFAIT
    for regul in corrections.regularisations_heures_ajoutees:
        if regul.dernier_mois > f"{year:04d}-{month:02d}":
            return (
                f"Les heures de {regul.mois_affiche} sont postérieures à ce bulletin : "
                "choisissez un mois d'origine antérieur ou égal."
            )
    return None


def refus_des_periodes_de_regularisation(
    corrections: CorrectionsBulletin, year: int, month: int
) -> str | None:
    """Une régularisation de cotisation ne corrige pas un mois postérieur au bulletin."""
    mois_du_bulletin = f"{year:04d}-{month:02d}"
    for regul in corrections.regularisations_ajoutees:
        if regul.mois_fin and regul.mois_fin > mois_du_bulletin:
            return (
                f"La période de « {regul.libelle} » ({regul.periode}) est postérieure à ce "
                "bulletin : choisissez des mois antérieurs ou égaux."
            )
    return None


def _cumul_de_reduction(payslip_data: dict[str, Any] | None) -> float | None:
    """La réduction appliquée depuis janvier, fin de mois, imprimée sur le bulletin."""
    bloc = (payslip_data or {}).get("cumuls")
    if not isinstance(bloc, dict):
        return None
    source = bloc.get("cumuls") if isinstance(bloc.get("cumuls"), dict) else bloc
    valeur = source.get("reduction_generale_patronale")
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return abs(float(valeur))
    except (TypeError, ValueError):
        return None


def refus_de_la_reduction_generale(
    corrections: CorrectionsBulletin, payslip_data: dict[str, Any] | None
) -> str | None:
    """Le refus du moteur, opposé avant d'écrire.

    Sans lui la saisie reste enregistrée, le moteur la refuse à chaque recalcul
    et le bulletin reste bloqué. Le moteur reste seul juge quand le bulletin ne
    dit pas son cumul.
    """
    ajoutee = next(
        (c for c in corrections.corrections_ajoutees if c.ligne == CODE_REDUCTION_GENERALE), None
    )
    nouvelles = [
        r for r in corrections.regularisations_ajoutees if r.coti_id == COTI_ID_REDUCTION_GENERALE
    ]
    if ajoutee is None and not nouvelles:
        return None
    cumul = _cumul_de_reduction(payslip_data)
    ligne = next(
        (l for l in lignes_corrigeables(payslip_data) if l.code == CODE_REDUCTION_GENERALE), None
    )
    if cumul is None or ligne is None or ligne.montant_patronal is None:
        return None

    posees = {
        sid: r.montants()[1]
        for sid, r in regularisations_du_bulletin(payslip_data).items()
        if r.coti_id == COTI_ID_REDUCTION_GENERALE
    }
    # Ce qui était appliqué avant ce mois, tel que le moteur le relit.
    deja = round(cumul + ligne.montant_patronal + sum(posees.values()), 2)

    montant = ligne.montant_patronal
    saisie = str((ligne.correction or {}).get("saisie_id") or "")
    if saisie and saisie in corrections.corrections_retirees:
        montant = float((ligne.valeur_calculee or {}).get("montant_patronal") or 0.0)
    if ajoutee is not None and ajoutee.montant_patronal is not None:
        montant = round(float(ajoutee.montant_patronal), 2)
        if round(deja - montant, 2) < 0:
            return MESSAGE_REDUCTION_CORRIGEE_TROP_HAUT

    gardees = [m for sid, m in posees.items() if sid not in corrections.regularisations_retirees]
    regularisation = sum(gardees) + sum(r.montants()[1] for r in nouvelles)
    if round(regularisation - (deja - montant), 2) > 0:
        return MESSAGE_REDUCTION_REGULARISEE_TROP_HAUT
    return None


def avec_la_valeur_de_martine(
    corrections: CorrectionsBulletin, payslip_data: dict[str, Any] | None
) -> CorrectionsBulletin:
    """Note, sur chaque correction ajoutée, ce que Martine calcule à cet instant (R-185)."""
    if not corrections.corrections_ajoutees:
        return corrections
    par_code = {ligne.code: ligne for ligne in lignes_corrigeables(payslip_data) if ligne.code}
    return replace(
        corrections,
        corrections_ajoutees=tuple(
            replace(c, martine_a_la_correction=valeur_de_martine(par_code[c.ligne]))
            if c.ligne in par_code and c.martine_a_la_correction is None
            else c
            for c in corrections.corrections_ajoutees
        ),
    )


def _declarees(payslip_data: dict[str, Any] | None) -> tuple[float, float] | None:
    declarees = (payslip_data or {}).get("heures_sup_declarees")
    if not isinstance(declarees, dict):
        return None
    return (
        round(float(declarees.get("hs25") or 0.0), 2),
        round(float(declarees.get("hs50") or 0.0), 2),
    )


def _proches(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return all(abs(x - y) <= _TOLERANCE for x, y in zip(a, b))


def _heures_pour_revenir(
    courant: dict[str, Any] | None, cible: dict[str, Any] | None
) -> tuple[float, float] | None:
    """Les heures sup à déclarer pour retrouver celles de la version cible.

    Une version récente dit si ses heures ont été déclarées au bulletin ; une
    plus ancienne ne le dit pas, et on reprend alors les quantités qu'elle
    imprimait, telles que Martine les avait calculées : une ligne d'heures
    corrigée à la main revient comme correction, jamais comme heures
    déclarées. Le bulletin du moment se lit de même. Rien à déclarer quand
    elles sont déjà celles du bulletin.
    """
    cible_declarees = _declarees(cible)
    if cible_declarees is not None:
        courant_declarees = _declarees(courant)
        if courant_declarees is not None and _proches(cible_declarees, courant_declarees):
            return None
        return cible_declarees
    heures_cible = quantites_heures_sup_calculees(cible)
    heures_courant = quantites_heures_sup_calculees(courant)
    if _proches(heures_cible, heures_courant):
        return None
    return (round(heures_cible[0], 2), round(heures_cible[1], 2))


def corrections_pour_revenir(
    courant: dict[str, Any] | None,
    cible: dict[str, Any] | None,
    *,
    saisies_existantes: set[str] | frozenset[str] = frozenset(),
) -> CorrectionsBulletin:
    """Ce qu'il faut corriger pour que le bulletin retrouve les heures sup et
    les primes saisies d'une version antérieure.

    Restaurer ne recopie plus l'ancien bulletin (ses cotisations et son net
    n'auraient pas suivi) : on revient à ses variables, et le moteur recalcule.
    Une prime de la version dont la saisie a disparu est recréée, avec le régime
    de la section où elle était imprimée ; `saisies_existantes` évite de recréer
    une saisie encore présente dans le mois. Les corrections de ligne reviennent
    de même ; une correction dont la ligne n'existe plus revient en attente.
    """
    primes_courant = primes_saisies_du_bulletin(courant)
    primes_cible = primes_saisies_du_bulletin(cible)

    retirees = tuple(sid for sid in primes_courant if sid not in primes_cible)
    modifiees: list[tuple[str, float]] = []
    ajoutees: list[dict[str, Any]] = []
    for sid, prime in primes_cible.items():
        if sid in primes_courant:
            if abs(prime.montant - primes_courant[sid].montant) > _TOLERANCE:
                modifiees.append((sid, prime.montant))
        elif sid in saisies_existantes:
            modifiees.append((sid, prime.montant))
        else:
            ajoutees.append(
                {
                    "name": prime.libelle,
                    "amount": prime.montant,
                    "is_socially_taxed": prime.soumise,
                    "is_taxable": prime.soumise,
                    "catalog_prime_id": None,
                }
            )
    regul_courant = regularisations_du_bulletin(courant)
    regul_cible = regularisations_du_bulletin(cible)
    regularisations_retirees = tuple(sid for sid in regul_courant if sid not in regul_cible)
    regularisations_ajoutees = tuple(
        RegularisationCotisation.depuis({**regul.charge_utile()})
        for sid, regul in regul_cible.items()
        if sid not in regul_courant and sid not in saisies_existantes
    )
    heures_courant = regularisations_heures_du_bulletin(courant)
    heures_cible = regularisations_heures_du_bulletin(cible)
    regularisations_heures_retirees = tuple(sid for sid in heures_courant if sid not in heures_cible)
    regularisations_heures_ajoutees = tuple(
        RegularisationHeures.depuis(regul.charge_utile())
        for sid, regul in heures_cible.items()
        if sid not in heures_courant and sid not in saisies_existantes
    )
    corrections_courant = corrections_du_bulletin(courant)
    corrections_cible = corrections_du_bulletin(cible)
    corrections_retirees = tuple(sid for sid in corrections_courant if sid not in corrections_cible)
    corrections_ajoutees = tuple(
        CorrectionDeLigne.depuis(correction.charge_utile())
        for sid, correction in corrections_cible.items()
        if sid not in corrections_courant and sid not in saisies_existantes
    )
    return CorrectionsBulletin(
        heures_sup=_heures_pour_revenir(courant, cible),
        primes=DiffPrimes(tuple(ajoutees), tuple(modifiees), retirees),
        regularisations_ajoutees=regularisations_ajoutees,
        regularisations_retirees=regularisations_retirees,
        regularisations_heures_ajoutees=regularisations_heures_ajoutees,
        regularisations_heures_retirees=regularisations_heures_retirees,
        corrections_ajoutees=corrections_ajoutees,
        corrections_retirees=corrections_retirees,
    )


# --- Ce que l'historique dit d'une version (jeu du 23/10) ---


def _heures_de(payslip_data: dict[str, Any] | None) -> tuple[float, float]:
    """Les heures sup déclarées au bulletin, sinon celles que Martine avait calculées (comme la restauration)."""
    declarees = _declarees(payslip_data)
    if declarees is not None:
        return declarees
    hs25, hs50 = quantites_heures_sup_calculees(payslip_data)
    return (round(hs25, 2), round(hs50, 2))


def _phrase_heures(heures: tuple[float, float]) -> str:
    return f"Heures sup {_heures(heures[0])} h à 25 % et {_heures(heures[1])} h à 50 %"


def contenu_de_version(cible: dict[str, Any] | None) -> list[str]:
    """Ce que la version porte de ce qu'une restauration rétablit : son intitulé.

    L'historique affichait le résumé du changement qui avait remplacé la
    version : « 1 prime retirée » sur une version qui avait la prime.
    """
    parties = [_phrase_heures(_heures_de(cible))]
    primes = primes_saisies_du_bulletin(cible)
    parties.extend(f"{prime.libelle} {_euros(prime.montant)}" for prime in primes.values())
    if not primes:
        parties.append("aucune prime saisie")
    corrections = corrections_du_bulletin(cible)
    if corrections:
        libelles = ", ".join(correction.libelle for correction in corrections.values())
        parties.append(f"{'Lignes corrigées' if len(corrections) > 1 else 'Ligne corrigée'} : {libelles}")
    else:
        parties.append("aucune ligne corrigée")
    regularisations = regularisations_du_bulletin(cible)
    if regularisations:
        libelles = ", ".join(regul.libelle for regul in regularisations.values())
        parties.append(f"{'Régularisations' if len(regularisations) > 1 else 'Régularisation'} : {libelles}")
    heures_regularisees = regularisations_heures_du_bulletin(cible)
    if heures_regularisees:
        libelles = ", ".join(
            f"{_heures(regul.quantite)} h de {regul.mois_affiche}" for regul in heures_regularisees.values()
        )
        parties.append(f"Heures régularisées : {libelles}")
    return parties


def apercu_de_restauration(
    courant: dict[str, Any] | None, cible: dict[str, Any] | None
) -> dict[str, list[str]]:
    """Ce que restaurer `cible` ferait au bulletin `courant`, d'après le calcul de la restauration.

    `reviennent` : ce que la version rétablit ; `remplacees` : les corrections
    du moment dont la ligne reprend celle de la version ; `retirees` : ce que
    la version n'avait pas et qui part. Rien ne disparaît sans être nommé.
    """
    corrections = corrections_pour_revenir(courant, cible)
    reviennent: list[str] = []
    remplacees: list[str] = []
    retirees: list[str] = []

    if corrections.heures_sup is not None:
        avant = _heures_de(courant)
        reviennent.append(
            f"{_phrase_heures(corrections.heures_sup)} (au lieu de {_heures(avant[0])} h et {_heures(avant[1])} h)"
        )

    primes_courant = primes_saisies_du_bulletin(courant)
    primes_cible = primes_saisies_du_bulletin(cible)
    for prime in corrections.primes.ajoutees:
        reviennent.append(f"Prime « {prime.get('name')} » : {_euros(prime.get('amount') or 0)}")
    for sid, montant in corrections.primes.modifiees:
        libelle = primes_cible[sid].libelle if sid in primes_cible else "Prime"
        phrase = f"Prime « {libelle} » : {_euros(montant)}"
        if sid in primes_courant:
            phrase += f" (au lieu de {_euros(primes_courant[sid].montant)})"
        reviennent.append(phrase)
    for sid in corrections.primes.retirees:
        prime = primes_courant[sid]
        retirees.append(f"Prime « {prime.libelle} » : {_euros(prime.montant)}")

    regul_courant = regularisations_du_bulletin(courant)
    for regul in corrections.regularisations_ajoutees:
        reviennent.append(f"Régularisation « {regul.libelle} » : {regul.motif}")
    for sid in corrections.regularisations_retirees:
        regul = regul_courant[sid]
        retirees.append(f"Régularisation « {regul.libelle} » : {regul.motif}")

    heures_courant = regularisations_heures_du_bulletin(courant)
    for regul in corrections.regularisations_heures_ajoutees:
        reviennent.append(f"Régularisation de {_heures(regul.quantite)} h de {regul.mois_affiche} : {regul.motif}")
    for sid in corrections.regularisations_heures_retirees:
        regul = heures_courant[sid]
        retirees.append(f"Régularisation de {_heures(regul.quantite)} h de {regul.mois_affiche} : {regul.motif}")

    corrections_courant = corrections_du_bulletin(courant)
    par_ligne = {correction.ligne: correction for correction in corrections.corrections_ajoutees}
    for correction in corrections.corrections_ajoutees:
        reviennent.append(f"Correction de la ligne « {correction.libelle} » : {correction.motif}")
    for sid in corrections.corrections_retirees:
        actuelle = corrections_courant[sid]
        nouvelle = par_ligne.get(actuelle.ligne)
        if nouvelle is not None:
            remplacees.append(
                f"Correction de la ligne « {actuelle.libelle} » : {actuelle.motif} "
                f"(remplacée par celle de la version : {nouvelle.motif})"
            )
        else:
            retirees.append(f"Correction de la ligne « {actuelle.libelle} » : {actuelle.motif}")

    return {"reviennent": reviennent, "remplacees": remplacees, "retirees": retirees}
