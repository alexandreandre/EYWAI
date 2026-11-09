"""Paramétrage DSN d'une société : tout ce qui ne vient pas de la paie.

L'émetteur, les contacts, l'IDCC, le code NAF déclaré, les organismes et le
versement ne se déduisent d'aucun bulletin. Ils sont repris de la dernière DSN
du cabinet puis corrigés à la main si besoin, chaque valeur gardant sa source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

SOURCE_REPRISE = "reprise_dsn"
SOURCE_SAISIE = "saisie"

# Codes destinataires vus dans les DSN du cabinet, dans leur ordre d'émission.
CODES_DESTINATAIRES_PAR_DEFAUT = ["01", "02", "03", "04", "05", "06", "07", "08", "09"]


def normaliser_naf(valeur: Optional[str]) -> str:
    """La DSN attend le NAF sans séparateur : ``25.61Z`` devient ``2561Z``."""
    texte = (valeur or "").strip().upper()
    return re.sub(r"[^0-9A-Z]", "", texte)


def normaliser_idcc(valeur: Optional[str]) -> str:
    """L'IDCC est déclaré sur 4 chiffres : ``292`` devient ``0292``."""
    chiffres = re.sub(r"\D", "", str(valeur or ""))
    return chiffres.zfill(4)[:4] if chiffres else ""


def normaliser_telephone(valeur: Optional[str]) -> str:
    return re.sub(r"[^0-9+]", "", str(valeur or ""))


@dataclass
class ContactDeclaration:
    """Contact déclaré pour un organisme destinataire (bloc S20.G00.07)."""

    nom: str = ""
    telephone: str = ""
    email: str = ""
    code_destinataire: str = "01"


@dataclass
class DsnSettings:
    """Paramètres DSN d'une société."""

    emetteur_siren: str = ""
    emetteur_nic: str = ""
    emetteur_raison_sociale: str = ""
    emetteur_rue: str = ""
    emetteur_code_postal: str = ""
    emetteur_ville: str = ""

    contact_emetteur_type: str = "02"
    contact_emetteur_nom: str = ""
    contact_emetteur_email: str = ""
    contact_emetteur_telephone: str = ""

    contacts_declaration: List[ContactDeclaration] = field(default_factory=list)

    naf: str = ""
    idcc: str = ""
    complement_adresse: str = ""
    commune_implantation: str = ""
    # Quotité mensuelle déclarée pour les forfaits annuels en jours : 21,67
    # chez certaines sociétés, 21,27 chez d'autres selon le nombre de jours du
    # forfait. Reprise du cabinet faute de la porter nous-mêmes.
    quotite_forfait_jours: str = ""

    # Rubriques du bloc établissement que le builder ne dérive pas et qu'on
    # reprend telles quelles du cabinet plutôt que de leur inventer un sens.
    rubriques_etablissement: Dict[str, str] = field(default_factory=dict)

    # Contrats collectifs prévoyance / santé / retraite supplémentaire de
    # l'établissement (bloc S21.G00.15), repris des fiches de paramétrage OC
    # (data/<societe>/referentiel/fpoc/) et des DSN du cabinet. Chaque entrée :
    # reference, organisme, delegataire (optionnel), nature, ordre. L'ordre est
    # l'identifiant technique que les blocs 70 des salariés référencent — il ne
    # doit plus bouger une fois émis.
    organismes_complementaires: List[Dict[str, str]] = field(default_factory=list)

    # Versements aux organismes (bloc S21.G00.20) : organisme (20.001),
    # entité d'affectation (20.002), BIC / IBAN, mode de paiement (20.010),
    # délégataire (20.008). Repris du cabinet ; les montants, eux, se
    # calculent chaque mois.
    versements: List[Dict[str, str]] = field(default_factory=list)
    # Assujettissements fiscaux déclarés chaque mois (bloc S21.G00.44) :
    # taxe d'apprentissage (001), contribution supplémentaire (003),
    # formation professionnelle (007), CPF-CDD (013)…
    assujettissements_fiscaux: List[str] = field(default_factory=list)

    source: str = SOURCE_SAISIE
    source_fichier: str = ""
    source_date: str = ""

    def est_complet(self) -> bool:
        """Vrai si les rubriques obligatoires de l'en-tête sont renseignées."""
        return bool(
            self.emetteur_siren
            and self.emetteur_raison_sociale
            and self.contact_emetteur_nom
            and self.contact_emetteur_email
            and self.contacts_declaration
        )

    def manques(self) -> List[str]:
        attendus = {
            "SIREN de l'émetteur": self.emetteur_siren,
            "raison sociale de l'émetteur": self.emetteur_raison_sociale,
            "nom du contact émetteur": self.contact_emetteur_nom,
            "adresse électronique du contact émetteur": self.contact_emetteur_email,
        }
        absents = [libelle for libelle, valeur in attendus.items() if not valeur]
        if not self.contacts_declaration:
            absents.append("contacts de la déclaration")
        return absents


def _premiere(rubriques: Dict[str, List[str]], code: str) -> str:
    valeurs = rubriques.get(code) or []
    return valeurs[0] if valeurs else ""


def extraire_depuis_dsn(contenu: bytes, *, fichier: str = "") -> DsnSettings:
    """Reprend le paramétrage d'une DSN déjà déposée par le cabinet.

    Ne lit que l'en-tête : émetteur, contacts, entreprise. Rien de nominatif
    salarié n'est extrait.
    """
    from app.modules.dsn_export.domain.conformance import lire_rubriques

    rubriques: Dict[str, List[str]] = {}
    for code, valeur in lire_rubriques(contenu):
        rubriques.setdefault(code, []).append(valeur)

    contacts: List[ContactDeclaration] = []
    noms = rubriques.get("S20.G00.07.001") or []
    tels = rubriques.get("S20.G00.07.002") or []
    mails = rubriques.get("S20.G00.07.003") or []
    codes = rubriques.get("S20.G00.07.004") or []
    for index, code in enumerate(codes):
        contacts.append(
            ContactDeclaration(
                nom=noms[index] if index < len(noms) else "",
                telephone=normaliser_telephone(
                    tels[index] if index < len(tels) else ""
                ),
                email=mails[index] if index < len(mails) else "",
                code_destinataire=code,
            )
        )

    # Rubriques du bloc établissement hors de celles que le builder construit.
    construites = {
        "S21.G00.11.001",
        "S21.G00.11.002",
        "S21.G00.11.003",
        "S21.G00.11.004",
        "S21.G00.11.005",
        "S21.G00.11.006",
        "S21.G00.11.007",
        "S21.G00.11.022",
    }
    complementaires = {
        code: valeurs[0]
        for code, valeurs in rubriques.items()
        if code.startswith("S21.G00.11.") and code not in construites and valeurs
    }

    quotite_forfait_jours = _quotite_forfait_jours(contenu)
    versements = _versements(contenu)
    assujettissements: List[str] = []
    for code in rubriques.get("S21.G00.44.001") or []:
        if code not in assujettissements:
            assujettissements.append(code)

    return DsnSettings(
        emetteur_siren=_premiere(rubriques, "S10.G00.01.001"),
        emetteur_nic=_premiere(rubriques, "S10.G00.01.002"),
        emetteur_raison_sociale=_premiere(rubriques, "S10.G00.01.003"),
        emetteur_rue=_premiere(rubriques, "S10.G00.01.004"),
        emetteur_code_postal=_premiere(rubriques, "S10.G00.01.005"),
        emetteur_ville=_premiere(rubriques, "S10.G00.01.006"),
        contact_emetteur_type=_premiere(rubriques, "S10.G00.02.001") or "02",
        contact_emetteur_nom=_premiere(rubriques, "S10.G00.02.002"),
        contact_emetteur_email=_premiere(rubriques, "S10.G00.02.004"),
        contact_emetteur_telephone=normaliser_telephone(
            _premiere(rubriques, "S10.G00.02.005")
        ),
        contacts_declaration=contacts,
        naf=normaliser_naf(_premiere(rubriques, "S21.G00.06.003")),
        idcc=normaliser_idcc(_premiere(rubriques, "S21.G00.06.015")),
        complement_adresse=_premiere(rubriques, "S21.G00.06.007"),
        commune_implantation=_premiere(rubriques, "S21.G00.06.008")
        or _premiere(rubriques, "S21.G00.11.007"),
        rubriques_etablissement=complementaires,
        quotite_forfait_jours=quotite_forfait_jours,
        versements=versements,
        assujettissements_fiscaux=assujettissements,
        source=SOURCE_REPRISE,
        source_fichier=fichier,
    )


#: Rubriques du bloc 20 qui décrivent l'organisme et le paiement, pas le montant.
_VERSEMENT_CLES = {
    "S21.G00.20.001": "organisme",
    "S21.G00.20.002": "entite",
    "S21.G00.20.003": "bic",
    "S21.G00.20.004": "iban",
    "S21.G00.20.008": "delegataire",
    "S21.G00.20.010": "mode",
}


def _versements(contenu: bytes) -> List[Dict[str, str]]:
    """Organismes payés par la DSN du cabinet, avec leurs coordonnées bancaires."""
    from app.modules.dsn_export.domain.conformance import lire_rubriques

    versements: List[Dict[str, str]] = []
    for code, valeur in lire_rubriques(contenu):
        if code == "S21.G00.20.001":
            versements.append({"organisme": valeur})
        elif code in _VERSEMENT_CLES and versements:
            versements[-1][_VERSEMENT_CLES[code]] = valeur
        elif code == "S21.G00.20.011" and versements and len(valeur) == 8:
            # Date de paiement JJMMAAAA : le jour du contrat, repris chaque trimestre.
            versements[-1]["jour_paiement"] = str(int(valeur[:2]))
    vus = set()
    uniques = []
    rubriques = list(lire_rubriques(contenu))
    urssaf = next((v for c, v in rubriques if c == "S21.G00.22.001"), "")
    # Code INSEE du versement mobilité (23.006 du CTP 900 ou assimilés) du bordereau repris.
    commune_vm = ""
    ctp = ""
    for code, valeur in rubriques:
        if code == "S21.G00.23.001":
            ctp = valeur
        elif code == "S21.G00.23.006" and ctp in ("900", "901", "911", "917", "921", "927") and not commune_vm:
            commune_vm = valeur
    for versement in versements:
        if versement["organisme"] in vus:
            continue
        vus.add(versement["organisme"])
        if urssaf and versement["organisme"] == urssaf:
            versement["urssaf"] = "1"
            if commune_vm:
                versement["commune_vm"] = commune_vm
        uniques.append(versement)
    return uniques


def commune_versement_mobilite(parametres: "DsnSettings") -> str:
    """Code INSEE de la commune du versement mobilité, repris du bordereau du cabinet."""
    for versement in parametres.versements:
        if versement.get("commune_vm"):
            return str(versement["commune_vm"])
    return ""


def identifiant_urssaf(societe: Dict[str, Any], parametres: "DsnSettings") -> str:
    """SIRET de l'Urssaf destinataire (S21.G00.22.001, S21.G00.81.002 : 14 chiffres).

    Le versement marqué à la reprise de la DSN du cabinet (organisme de son bordereau)
    d'abord, puis un « N° URSSAF » de fiche société s'il compte 14 chiffres. Un numéro
    de compte cotisant à 18 chiffres n'est pas cet identifiant : DSN-VAL le refuse.
    """
    for versement in parametres.versements:
        organisme = str(versement.get("organisme") or "")
        if versement.get("urssaf") and organisme.isdigit() and len(organisme) == 14:
            return organisme
    for cle in ("urssaf_number", "urssaf_siret", "ops_urssaf"):
        valeur = str(societe.get(cle) or "").replace(" ", "")
        if valeur.isdigit() and len(valeur) == 14:
            return valeur
    return ""


def types_de_population(contenu: bytes) -> Dict[str, str]:
    """Type de population (55.002) de chaque contrat (55.003) dans les composants
    de versement du cabinet : un code de la fiche de l'organisme, déclaré sur sa
    demande (FAQ DSN OC, net-entreprises)."""
    from app.modules.dsn_export.domain.conformance import lire_rubriques

    types: Dict[str, str] = {}
    courant: Dict[str, str] = {}
    for code, valeur in lire_rubriques(contenu):
        if code == "S21.G00.55.001":
            courant = {}
        elif code in ("S21.G00.55.002", "S21.G00.55.003"):
            courant[code] = valeur
            if courant.get("S21.G00.55.003") and courant.get("S21.G00.55.002"):
                types[courant["S21.G00.55.003"]] = courant["S21.G00.55.002"]
    return types


def _quotite_forfait_jours(contenu: bytes) -> str:
    """Quotité que le cabinet déclare pour les contrats comptés en jours."""
    from app.modules.dsn_export.domain.conformance import lire_rubriques

    unite_courante = ""
    quotites: Dict[str, int] = {}
    for code, valeur in lire_rubriques(contenu):
        if code == "S21.G00.40.011":
            unite_courante = valeur
        elif code == "S21.G00.40.012" and unite_courante == "20":
            quotites[valeur] = quotites.get(valeur, 0) + 1
    if not quotites:
        return ""
    return max(quotites.items(), key=lambda paire: paire[1])[0]


def depuis_dict(donnees: Optional[Dict[str, Any]]) -> DsnSettings:
    """Reconstruit le paramétrage depuis la ligne stockée en base."""
    if not donnees:
        return DsnSettings()
    contacts = []
    for brut in donnees.get("contacts_declaration") or []:
        if isinstance(brut, dict):
            contacts.append(
                ContactDeclaration(
                    nom=brut.get("nom") or "",
                    telephone=normaliser_telephone(brut.get("telephone")),
                    email=brut.get("email") or "",
                    code_destinataire=brut.get("code_destinataire") or "01",
                )
            )
    return DsnSettings(
        emetteur_siren=donnees.get("emetteur_siren") or "",
        emetteur_nic=donnees.get("emetteur_nic") or "",
        emetteur_raison_sociale=donnees.get("emetteur_raison_sociale") or "",
        emetteur_rue=donnees.get("emetteur_rue") or "",
        emetteur_code_postal=donnees.get("emetteur_code_postal") or "",
        emetteur_ville=donnees.get("emetteur_ville") or "",
        contact_emetteur_type=donnees.get("contact_emetteur_type") or "02",
        contact_emetteur_nom=donnees.get("contact_emetteur_nom") or "",
        contact_emetteur_email=donnees.get("contact_emetteur_email") or "",
        contact_emetteur_telephone=normaliser_telephone(
            donnees.get("contact_emetteur_telephone")
        ),
        contacts_declaration=contacts,
        naf=normaliser_naf(donnees.get("naf")),
        idcc=normaliser_idcc(donnees.get("idcc")),
        complement_adresse=donnees.get("complement_adresse") or "",
        commune_implantation=donnees.get("commune_implantation") or "",
        quotite_forfait_jours=donnees.get("quotite_forfait_jours") or "",
        rubriques_etablissement=dict(donnees.get("rubriques_etablissement") or {}),
        organismes_complementaires=[
            dict(entree)
            for entree in donnees.get("organismes_complementaires") or []
            if isinstance(entree, dict) and entree.get("reference")
        ],
        versements=[
            dict(entree)
            for entree in donnees.get("versements") or []
            if isinstance(entree, dict) and entree.get("organisme")
        ],
        assujettissements_fiscaux=[
            str(code) for code in donnees.get("assujettissements_fiscaux") or [] if code
        ],
        source=donnees.get("source") or SOURCE_SAISIE,
        source_fichier=donnees.get("source_fichier") or "",
        source_date=str(donnees.get("source_date") or ""),
    )


def vers_dict(settings: DsnSettings) -> Dict[str, Any]:
    """Sérialise pour stockage."""
    return {
        "emetteur_siren": settings.emetteur_siren,
        "emetteur_nic": settings.emetteur_nic,
        "emetteur_raison_sociale": settings.emetteur_raison_sociale,
        "emetteur_rue": settings.emetteur_rue,
        "emetteur_code_postal": settings.emetteur_code_postal,
        "emetteur_ville": settings.emetteur_ville,
        "contact_emetteur_type": settings.contact_emetteur_type,
        "contact_emetteur_nom": settings.contact_emetteur_nom,
        "contact_emetteur_email": settings.contact_emetteur_email,
        "contact_emetteur_telephone": settings.contact_emetteur_telephone,
        "contacts_declaration": [
            {
                "nom": c.nom,
                "telephone": c.telephone,
                "email": c.email,
                "code_destinataire": c.code_destinataire,
            }
            for c in settings.contacts_declaration
        ],
        "naf": settings.naf,
        "idcc": settings.idcc,
        "complement_adresse": settings.complement_adresse,
        "commune_implantation": settings.commune_implantation,
        "quotite_forfait_jours": settings.quotite_forfait_jours,
        "rubriques_etablissement": settings.rubriques_etablissement,
        "organismes_complementaires": settings.organismes_complementaires,
        "versements": settings.versements,
        "assujettissements_fiscaux": settings.assujettissements_fiscaux,
        "source": settings.source,
        "source_fichier": settings.source_fichier,
    }
