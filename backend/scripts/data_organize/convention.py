"""Convention de nommage et de rangement des données de paie locales.

Ce module est la *seule* source de vérité sur « quel document va où ». Il ne lit
ni n'écrit aucun fichier : il ne fait que traduire un chemin source en chemin
cible. Tout le reste (inventaire, migration, ingestion WhatsApp) s'appuie dessus.

Arborescence cible, sous la racine `data/` (gitignorée) :

    data/<societe>/calendriers/            calendrier-2026.xlsx
    data/<societe>/dsn/                    2026-05.dsn
    data/<societe>/bulletins/<AAAA-MM>/    bulletins Cegid + md/<MATRICULE>.md
    data/<societe>/pointages/<AAAA-MM>/    relevés hebdomadaires
    data/<societe>/variables/<AAAA-MM>/    prépa paie, heures sup, primes
    data/<societe>/compteurs/              CP, ancienneté, IJSS, RTT, CET
    data/<societe>/referentiel/            enrichissement salarié, accords, modèles
"""

from __future__ import annotations

import datetime as _dt
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

# --------------------------------------------------------------------------
# Sociétés
# --------------------------------------------------------------------------

#: Slug canonique par société. Toute variante d'écriture converge ici.
SOCIETES = ("cartol", "colorplast", "comitech", "lewis", "maji", "mbc", "zone")

MODELES = "_modeles"
ARCHIVE = "_archive"
INBOX = "_inbox"

#: Motifs reconnus dans un chemin ou un nom de fichier, du plus spécifique au
#: plus générique (l'ordre compte : « comitech » avant « composite »).
_ALIAS_SOCIETE: tuple[tuple[str, str], ...] = (
    ("comitech", "comitech"),
    ("colorplast", "colorplast"),
    ("cartol", "cartol"),
    ("lewis", "lewis"),
    ("maji", "maji"),
    ("zone", "zone"),
    ("mont blanc composite", "mbc"),
    ("mont-blanc-composite", "mbc"),
    ("mbc", "mbc"),
    ("exemple", MODELES),
)


def detecter_societe(texte: str) -> str | None:
    """Renvoie le slug de société contenu dans `texte`, ou None."""
    plat = _sans_accent(texte).lower()
    for motif, slug in _ALIAS_SOCIETE:
        if motif in plat:
            return slug
    return None


# --------------------------------------------------------------------------
# Rubriques
# --------------------------------------------------------------------------

CALENDRIERS = "calendriers"
DSN = "dsn"
BULLETINS = "bulletins"
POINTAGES = "pointages"
VARIABLES = "variables"
COMPTEURS = "compteurs"
REFERENTIEL = "referentiel"

RUBRIQUES = (
    CALENDRIERS,
    DSN,
    BULLETINS,
    POINTAGES,
    VARIABLES,
    COMPTEURS,
    REFERENTIEL,
)

#: Rubriques dont les documents sont rangés dans un sous-dossier `AAAA-MM`.
RUBRIQUES_MENSUELLES = (BULLETINS, POINTAGES, VARIABLES)


# --------------------------------------------------------------------------
# Normalisation des noms
# --------------------------------------------------------------------------

#: Artefacts macOS / Windows à effacer des noms de fichiers.
_ARTEFACTS = (
    "(recuperation automatique)",
    "(copie)",
    "(copy)",
    " ok gb",
    " ok",
    " maj",
)

_RE_SUFFIXE_NUMEROTE = re.compile(r"\s*\(\d+\)$")
_RE_PREFIXE_WHATSAPP = re.compile(r"^-?\d{6,10}-")
_RE_SEPARATEURS = re.compile(r"[^a-z0-9]+")


def _sans_accent(texte: str) -> str:
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


def slugifier(texte: str) -> str:
    """`Prime d'ancienneté (1)` -> `prime-d-anciennete`."""
    plat = _sans_accent(texte).lower()
    return _RE_SEPARATEURS.sub("-", plat).strip("-")


def nettoyer_nom(nom: str) -> str:
    """Nettoie un nom de fichier sans toucher à son extension.

    Retire le préfixe numérique des exports WhatsApp, les suffixes `(1)`, les
    artefacts de récupération automatique, puis slugifie le radical.
    """
    chemin = Path(nom)
    extension = chemin.suffix.lower()
    radical = chemin.stem

    radical = _RE_PREFIXE_WHATSAPP.sub("", radical)
    radical = _RE_SUFFIXE_NUMEROTE.sub("", radical)

    plat = _sans_accent(radical).lower()
    for artefact in _ARTEFACTS:
        plat = plat.replace(artefact, "")
        # Un artefact peut apparaître plusieurs fois de suite.
        while artefact in plat:
            plat = plat.replace(artefact, "")

    slug = slugifier(plat)
    return f"{slug}{extension}" if slug else f"sans-nom{extension}"


# --------------------------------------------------------------------------
# Périodes
# --------------------------------------------------------------------------

ANNEE_PAR_DEFAUT = 2026

_RE_AAAA_MM = re.compile(r"(20\d{2})[-_ ]?(0[1-9]|1[0-2])(?!\d)")
_RE_MM_AAAA = re.compile(r"(?<!\d)(0[1-9]|1[0-2])[-_ ](20\d{2})(?!\d)")
_RE_MM_AA = re.compile(r"(?<!\d)(0[1-9]|1[0-2])[-_](2\d)(?!\d)")
_RE_DSN = re.compile(r"_(\d{2})(\d{2})_\d{6}", re.IGNORECASE)
_RE_SEMAINE = re.compile(r"(?:semaine|^s)\s*(\d{1,2})(?!\d)", re.IGNORECASE)

#: Un nom bâti sur des numéros de semaine : `S18`, `S01 à S04 MAJ`, `S22 à S25`,
#: `S05 pointages 2026`. C'est toujours un relevé de pointage.
_RE_NOM_SEMAINES = re.compile(r"^s\s?\d{1,2}\b", re.IGNORECASE)
_RE_ANNEE = re.compile(r"(?<!\d)(20\d{2})(?!\d)")


def mois_de_la_semaine_iso(semaine: int, annee: int = ANNEE_PAR_DEFAUT) -> int:
    """Mois auquel se rattache une semaine ISO (via son jeudi, jour pivot ISO)."""
    semaine = max(1, min(53, semaine))
    jeudi = _dt.date.fromisocalendar(annee, semaine, 4)
    return jeudi.month


def detecter_periode_explicite(texte: str) -> str | None:
    """Extrait un mois explicitement écrit (`AAAA-MM`, `MM-AAAA`, `MM-AA`, DSN).

    C'est le signal le plus fiable : il ne dépend d'aucune convention de
    rangement. Ne devine rien à partir d'un numéro de semaine.
    """
    if m := _RE_DSN.search(texte):
        mois, annee = int(m.group(1)), 2000 + int(m.group(2))
        if 1 <= mois <= 12:
            return f"{annee}-{mois:02d}"

    if m := _RE_AAAA_MM.search(texte):
        return f"{int(m.group(1))}-{int(m.group(2)):02d}"

    if m := _RE_MM_AAAA.search(texte):
        return f"{int(m.group(2))}-{int(m.group(1)):02d}"

    if m := _RE_MM_AA.search(texte):
        return f"{2000 + int(m.group(2))}-{int(m.group(1)):02d}"

    return None


def detecter_periode_semaine(texte: str) -> str | None:
    """Déduit un mois d'un numéro de semaine ISO (`SEMAINE 18`, `S18 à S21`).

    Signal faible : une semaine à cheval sur deux mois est rattachée à celui de
    son jeudi, qui n'est pas toujours le mois de paie concerné. À n'utiliser
    qu'en dernier recours, après le dossier de rangement.
    """
    if m := _RE_SEMAINE.search(texte):
        semaine = int(m.group(1))
        if 1 <= semaine <= 53:
            return f"{ANNEE_PAR_DEFAUT}-{mois_de_la_semaine_iso(semaine):02d}"
    return None


def detecter_annee(texte: str) -> str | None:
    if m := _RE_ANNEE.search(texte):
        return m.group(1)
    return None


def detecter_periode(texte: str) -> str | None:
    """Meilleure période déductible de `texte`, du signal fort au signal faible."""
    return (
        detecter_periode_explicite(texte)
        or detecter_periode_semaine(texte)
        or detecter_annee(texte)
    )


def est_periode_mensuelle(periode: str | None) -> bool:
    return bool(periode) and len(periode) == 7


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------

#: Mots-clés du nom de fichier ou du dossier parent -> rubrique.
#: L'ordre compte : la première correspondance gagne.
_INDICES_RUBRIQUE: tuple[tuple[tuple[str, ...], str], ...] = (
    (("calendrier", "jour repos", "jours repos", "jour de repos", "jtc"), CALENDRIERS),
    ((".dsn",), DSN),
    (("bulletin", "compteur cp"), BULLETINS),
    (("pointage", "semaine", "presence", "badge"), POINTAGES),
    (
        ("prepa paie", "heures sup", "heure sup", "variable", "prime", "acompte"),
        VARIABLES,
    ),
    (
        (
            "anciennete",
            "ijss",
            "cp ",
            "10e",
            "10eme",
            "fractionnement",
            "cet",
            "rtt",
            "solidarite",
            "contingent",
            "conges",
        ),
        COMPTEURS,
    ),
    (
        ("enrichissement", "paie ", "accord", "contrat", "avenant", "modele"),
        REFERENTIEL,
    ),
)


def detecter_rubrique(nom: str, dossier_parent: str = "") -> str | None:
    """Déduit la rubrique d'un document depuis son nom et son dossier parent."""
    nom_plat = _sans_accent(nom).lower()
    parent_plat = _sans_accent(dossier_parent).lower()

    extension = Path(nom).suffix.lower()
    if extension == ".dsn":
        return DSN

    # `S18.pdf`, `S01 à S04 MAJ.pdf` : un nom bâti sur des numéros de semaine est
    # toujours un pointage, aucun autre document n'est nommé ainsi.
    if _RE_NOM_SEMAINES.match(_sans_accent(Path(nom).stem)):
        return POINTAGES

    # Le nom du fichier prime sur celui du dossier : un calendrier rangé dans un
    # dossier « Bulletins » reste un calendrier.
    for mots, rubrique in _INDICES_RUBRIQUE:
        if any(mot in nom_plat for mot in mots):
            return rubrique

    for mots, rubrique in _INDICES_RUBRIQUE:
        if any(mot in parent_plat for mot in mots):
            return rubrique

    # `05-26 CARTOL.pdf`, `05-2026 COMITECH.pdf`, `05-2026.pdf` : un nom qui se
    # réduit à un mois et éventuellement une société désigne le lot de bulletins
    # du mois. C'est la façon dont Cegid nomme ses exports.
    if extension == ".pdf" and _se_reduit_a_periode_et_societe(nom):
        return BULLETINS

    return None


def _se_reduit_a_periode_et_societe(nom: str) -> bool:
    """Le nom ne contient-il qu'un mois, et au plus un nom de société ?"""
    radical = _sans_accent(Path(nom).stem).lower()
    if not detecter_periode_explicite(radical):
        return False

    residu = _RE_SUFFIXE_NUMEROTE.sub("", radical)
    residu = _RE_AAAA_MM.sub(" ", residu)
    residu = _RE_MM_AAAA.sub(" ", residu)
    residu = _RE_MM_AA.sub(" ", residu)
    for motif, _ in _ALIAS_SOCIETE:
        residu = residu.replace(motif, " ")
    return not _RE_SEPARATEURS.sub("", residu)


_RE_SEMAINE_LONGUE = re.compile(r"\bsemaines?-?(\d{1,2})\b")
_RE_SEMAINE_COURTE = re.compile(r"\bs-?(\d{1,2})\b")
_RE_PLAGE_SEMAINES = re.compile(r"\bs-?(\d{1,2})-a-s-?(\d{1,2})\b")


def _normaliser_semaines(nom: str) -> str:
    """Uniformise la désignation des semaines dans un nom de pointage.

    `s18.pdf`, `semaine-18.pdf` et `s-18.pdf` désignent le même document ; sans
    normalisation ils occuperaient trois emplacements différents. Formes
    retenues : `semaine-18`, et `semaines-22-a-25` pour une plage. La
    substitution se fait sur place, pour ne pas désorganiser un nom qui contient
    autre chose (`pointage-s24-extrait-pmi`).
    """
    chemin = Path(nom)
    # Tout ramener à la forme courte, pour n'avoir qu'un motif à traiter.
    radical = _RE_SEMAINE_LONGUE.sub(r"s\1", chemin.stem)

    radical = _RE_PLAGE_SEMAINES.sub(
        lambda m: f"semaines-{int(m.group(1)):02d}-a-{int(m.group(2)):02d}", radical
    )
    radical = _RE_SEMAINE_COURTE.sub(lambda m: f"semaine-{int(m.group(1)):02d}", radical)

    radical = _RE_SEPARATEURS.sub("-", radical).strip("-")
    return f"{radical}{chemin.suffix}"


@dataclass(frozen=True)
class Destination:
    """Emplacement canonique d'un document."""

    societe: str
    rubrique: str
    periode: str | None
    nom: str

    def chemin_relatif(self) -> Path:
        """Chemin sous la racine `data/`."""
        base = Path(self.societe) / self.rubrique
        if self.rubrique in RUBRIQUES_MENSUELLES and est_periode_mensuelle(self.periode):
            base = base / str(self.periode)
        return base / self.nom

    def __str__(self) -> str:  # pragma: no cover - confort de lecture
        return str(self.chemin_relatif())


def nom_canonique(rubrique: str, periode: str | None, nom_origine: str) -> str:
    """Nom de fichier canonique pour une rubrique donnée.

    Les DSN sont entièrement renommées d'après leur période (`2026-05.dsn`), car
    leur nom d'origine (`000001_0526_000001 (1).dsn`) n'est pas lisible. Les
    autres documents conservent un nom nettoyé, la période servant déjà de
    dossier pour les rubriques mensuelles.
    """
    extension = Path(nom_origine).suffix.lower()

    if rubrique == DSN and periode:
        return f"{periode}{extension}"

    propre = nettoyer_nom(nom_origine)

    if rubrique == POINTAGES:
        propre = _normaliser_semaines(propre)

    if rubrique == CALENDRIERS and periode:
        # `calendrier 2026 CARTOL(Récupération automatique).xlsx` -> `calendrier-2026.xlsx`
        # Un calendrier est annuel : on ne retient que l'année, même si le
        # document a été rangé dans un dossier mensuel.
        annee = periode[:4]
        radical = Path(propre).stem
        for slug in SOCIETES:
            radical = radical.replace(f"-{slug}", "").replace(f"{slug}-", "")
        radical = radical.replace(annee, "").strip("-") or "calendrier"
        return f"{radical}-{annee}{extension}"

    return propre
