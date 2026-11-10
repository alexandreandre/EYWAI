"""La fiche d'un bulletin telle que l'IA la reçoit. Fonctions pures, sans base.

Deux barrières : la fiche ne reprend que des parties utiles du bulletin (liste
ci-dessous), puis un filtre récursif retire toute clé personnelle et masque ce
qui ressemblerait à un NIR, un IBAN, un courriel ou au nom du salarié dans un
texte. Le salarié n'y est qu'un code stable.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable
from typing import Any

# Les parties du bulletin que la relecture regarde.
_SECTIONS_DU_MOIS = (
    "calcul_du_brut",
    "salaire_brut",
    "structure_cotisations",
    "synthese_net",
    "net_a_payer",
    "primes_non_soumises",
    "retenues_sur_net",
    "revenus_hors_brut_imposables",
    "participations",
    "details_absences",
    "details_conges",
    "details_maintien",
    "cumuls",
    "reprise",
    "parametres",
    "alertes_baremes",
)
_SECTIONS_DU_MOIS_PRECEDENT = tuple(
    s for s in _SECTIONS_DU_MOIS if s not in ("cumuls", "reprise", "parametres")
)
_EN_TETE = ("periode", "annee", "mois", "date_debut_periode", "date_fin_periode")
_EN_TETE_SALARIE = (
    "emploi",
    "statut",
    "type_contrat",
    "is_alternant",
    "date_entree",
    "date_anciennete",
    "classification",
    "convention_collective",
)
_CHAMPS_ECARTS = ("salaire_brut", "net_a_payer")

MASQUE = "[masqué]"

_CLES_ENTIERES = {
    "ssn",
    "codepostal",
    "employeeid",
    "userid",
    "salarieid",
}
_MORCEAUX_DE_CLE = (
    "iban",
    "email",
    "courriel",
    "adresse",
    "address",
    "naissance",
    "birth",
    "prenom",
    "firstname",
    "lastname",
    "fullname",
    "securitesociale",
    "socialsecurity",
    "residencepermit",
    "telephone",
    "phone",
    "coordonneesbancaires",
)
_MOTS_DE_CLE = {"nir", "bic", "rib", "nom", "name", "mail", "matricule", "rue", "ville", "sejour"}

_RE_COURRIEL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_RE_IBAN = re.compile(r"\b[A-Za-z]{2}\d{2}(?:[  ]?[A-Za-z0-9]{4}){3,7}(?:[  ]?[A-Za-z0-9]{1,4})?\b")
_RE_NIR = re.compile(
    r"\b[12](?:[  ]?\d{2}){2}[  ]?(?:\d{2}|2[AaBb])(?:[  ]?\d{3}){2}(?:[  ]?\d{2})?\b"
)

_ACCENTS = {
    "a": "aàâä",
    "c": "cç",
    "e": "eéèêë",
    "i": "iîï",
    "o": "oôö",
    "u": "uùûü",
    "y": "yÿ",
}
_NOM_MINIMUM = 3
_LETTRES_CODE = "ABCDEFGHJKLMNPQRSTUVWXYZ"


def _sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c))


def _cle_interdite(cle: str) -> bool:
    separee = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", _sans_accents(str(cle))).lower()
    compacte = re.sub(r"[^a-z0-9]", "", separee)
    if compacte in _CLES_ENTIERES:
        return True
    if any(morceau in compacte for morceau in _MORCEAUX_DE_CLE):
        return True
    return bool(_MOTS_DE_CLE & set(re.split(r"[^a-z0-9]+", separee)))


def _motif_du_nom(nom: str) -> str:
    morceaux = []
    for lettre in _sans_accents(nom).lower():
        if lettre in _ACCENTS:
            morceaux.append(f"[{_ACCENTS[lettre]}]")
        elif re.fullmatch(r"[\s\-'’]", lettre):
            morceaux.append(r"[\s\-'’]+")
        else:
            morceaux.append(re.escape(lettre))
    return "".join(morceaux)


def _regex_des_noms(noms: Iterable[str]) -> re.Pattern[str] | None:
    mots: set[str] = set()
    for nom in noms:
        # Le nom entier d'abord (« Le Goff »), puis ses mots assez longs pour ne
        # pas emporter une particule du texte (« de », « le »).
        for mot in [str(nom or "").strip(), *re.split(r"[\s\-'’]+", str(nom or ""))]:
            if len(mot) >= _NOM_MINIMUM:
                mots.add(mot)
    if not mots:
        return None
    # Les plus longs d'abord : « Martineau » ne doit pas être coupé par « Martin ».
    alternatives = "|".join(_motif_du_nom(m) for m in sorted(mots, key=len, reverse=True))
    return re.compile(rf"(?<![^\W\d_])(?:{alternatives})(?![^\W\d_])", re.IGNORECASE)


def filtrer_donnees_personnelles(
    valeur: Any, *, noms: Iterable[str] = (), code: str = MASQUE
) -> Any:
    """Copie de `valeur` sans clé personnelle, à toute profondeur.

    `noms` : prénom et nom du salarié, remplacés par `code` dans les textes.
    """
    regex_noms = _regex_des_noms(noms)

    def nettoyer_texte(texte: str) -> str:
        texte = _RE_COURRIEL.sub(MASQUE, texte)
        texte = _RE_IBAN.sub(MASQUE, texte)
        texte = _RE_NIR.sub(MASQUE, texte)
        return regex_noms.sub(code, texte) if regex_noms else texte

    def parcourir(element: Any) -> Any:
        if isinstance(element, dict):
            return {
                cle: parcourir(contenu)
                for cle, contenu in element.items()
                if not _cle_interdite(cle)
            }
        if isinstance(element, (list, tuple)):
            return [parcourir(contenu) for contenu in element]
        if isinstance(element, str):
            return nettoyer_texte(element)
        if isinstance(element, int) and not isinstance(element, bool) and abs(element) >= 10**12:
            return None
        return element

    return parcourir(valeur)


def code_salarie(employee_id: str) -> str:
    """Code stable d'un salarié, sans chiffre : il ne se confond jamais avec un montant."""
    empreinte = hashlib.sha256(str(employee_id).encode("utf-8")).digest()
    return "SAL-" + "".join(_LETTRES_CODE[o % len(_LETTRES_CODE)] for o in empreinte[:8])


def _noms_du_bulletin(*bulletins: dict[str, Any] | None) -> list[str]:
    noms: list[str] = []
    for bulletin in bulletins:
        salarie = ((bulletin or {}).get("en_tete") or {}).get("salarie") or {}
        noms.extend(str(salarie[c]) for c in ("nom", "prenom", "nom_complet") if salarie.get(c))
    return noms


def _partie_du_bulletin(bulletin: dict[str, Any], sections: tuple[str, ...]) -> dict[str, Any]:
    extrait = {s: bulletin[s] for s in sections if s in bulletin}
    en_tete = bulletin.get("en_tete") or {}
    salarie = en_tete.get("salarie") or {}
    extrait["en_tete"] = {
        **{c: en_tete[c] for c in _EN_TETE if c in en_tete},
        "salarie": {c: salarie[c] for c in _EN_TETE_SALARIE if c in salarie},
    }
    pied = bulletin.get("pied_de_page") or {}
    if "solde_conges" in pied:
        extrait["pied_de_page"] = {"solde_conges": pied["solde_conges"]}
    return extrait


def _ecarts(bulletin: dict[str, Any], precedent: dict[str, Any] | None) -> dict[str, float]:
    """Écarts calculés ici : l'IA peut les citer sans avoir à les refaire."""
    if not precedent:
        return {}
    ecarts: dict[str, float] = {}
    for champ in _CHAMPS_ECARTS:
        ce_mois, avant = bulletin.get(champ), precedent.get(champ)
        if isinstance(ce_mois, (int, float)) and isinstance(avant, (int, float)):
            ecarts[champ] = round(float(ce_mois) - float(avant), 2)
    return ecarts


def construire_fiche(
    bulletin: dict[str, Any],
    *,
    precedent: dict[str, Any] | None,
    contrat: dict[str, Any],
    code: str,
    noms_connus: Iterable[str] = (),
) -> dict[str, Any]:
    """La fiche filtrée d'un bulletin : à envoyer telle quelle.

    `noms_connus` : les noms de la fiche salarié. Un libellé peut porter le nom
    d'usage alors que l'en-tête du bulletin porte l'autre.
    """
    fiche = {
        "salarie": code,
        "contrat": contrat,
        "mois": _partie_du_bulletin(bulletin, _SECTIONS_DU_MOIS),
        "mois_precedent": (
            _partie_du_bulletin(precedent, _SECTIONS_DU_MOIS_PRECEDENT) if precedent else None
        ),
        "ecarts_avec_mois_precedent": _ecarts(bulletin, precedent),
    }
    return filtrer_donnees_personnelles(
        fiche, noms=[*_noms_du_bulletin(bulletin, precedent), *noms_connus], code=code
    )
