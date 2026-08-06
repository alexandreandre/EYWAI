"""
Construction du contexte « convention collective » envoyé au LLM.

Le texte de base d'une convention va de 130 000 à plus de 400 000 caractères. Le
lui envoyer entier coûte cher et dégrade la précision : au-delà de quelques
dizaines de milliers de tokens, le modèle retient mal un article isolé au milieu
d'un document. On sélectionne donc les sections utiles à la question.

Deux garanties tiennent la sélection honnête :
- le **sommaire complet** est toujours joint, pour que le modèle sache ce qui
  existe et puisse dire qu'une section n'a pas été retenue ;
- sous le seuil, le texte est transmis **intégralement** — aucune sélection,
  donc aucun risque d'écarter le bon passage.

Logique purement domaine : aucun accès base, réseau ou LLM.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# En dessous de ce volume, on envoie tout : la sélection n'apporterait rien et
# ne ferait que créer un risque de manquer le bon article.
SEUIL_TEXTE_INTEGRAL = 60_000

# Budget de la sélection (~32 000 tokens), sommaire non compris.
BUDGET_SELECTION = 120_000

_MOTIF_TITRE = re.compile(r"^(#{1,4})\s+(.+?)\s*$", re.MULTILINE)

# Mots trop fréquents pour discriminer une section d'une convention collective.
_MOTS_VIDES = frozenset(
    """
    a ai au aux avec ce ces dans de des du elle en est et eux il ils je la le
    les leur lui ma mais me meme mes moi mon ne nos notre nous on ou par pas
    pour qu que qui sa se ses son sur ta te tes toi ton tu un une vos votre
    vous y quel quelle quels quelles quoi comment combien est-ce c est sont
    ont fait faire dit dire salarie salaries entreprise convention collective
    article articles texte
    """.split()
)


@dataclass(frozen=True)
class ContexteConvention:
    """Contexte prêt à être inséré dans le prompt."""

    texte: str
    sommaire: str
    integral: bool
    caracteres_source: int
    caracteres_retenus: int


@dataclass(frozen=True)
class _Section:
    rang: int
    titre: str
    contenu: str

    @property
    def taille(self) -> int:
        return len(self.contenu)


def _sans_accents(valeur: str) -> str:
    decompose = unicodedata.normalize("NFD", valeur.lower())
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


def _mots_utiles(valeur: str) -> set[str]:
    mots = re.findall(r"[a-z0-9]+", _sans_accents(valeur))
    return {m for m in mots if len(m) > 2 and m not in _MOTS_VIDES}


def decouper_en_sections(texte: str) -> list[_Section]:
    """Découpe le texte sur ses titres Markdown, en conservant l'ordre d'origine."""
    titres = list(_MOTIF_TITRE.finditer(texte))
    if not titres:
        return [_Section(rang=0, titre="", contenu=texte)]

    sections: list[_Section] = []
    entete = texte[: titres[0].start()].strip()
    if entete:
        sections.append(_Section(rang=0, titre="", contenu=entete))

    for index, titre in enumerate(titres):
        fin = titres[index + 1].start() if index + 1 < len(titres) else len(texte)
        contenu = texte[titre.start() : fin].strip()
        if contenu:
            sections.append(
                _Section(rang=len(sections), titre=titre.group(2).strip(), contenu=contenu)
            )
    return sections


def _score(section: _Section, mots_question: set[str]) -> float:
    """Pertinence d'une section : le titre pèse lourd, le corps compte en densité.

    La densité — occurrences par tranche de 10 000 caractères — et non la simple
    présence : dans une convention, une section de 56 000 caractères contient
    presque toujours au moins une fois chacun des mots de la question, et une
    mesure de présence la ferait gagner à tous les coups. C'est exactement ce qui
    faisait remonter « Protection sociale complémentaire » sur une question de
    préavis.
    """
    if not mots_question:
        return 0.0
    mots_titre = _mots_utiles(section.titre)
    couverture_titre = len(mots_question & mots_titre) / len(mots_question)

    corps = _sans_accents(section.contenu)
    occurrences = sum(
        len(re.findall(rf"\b{re.escape(mot)}", corps)) for mot in mots_question
    )
    densite = occurrences / max(1.0, section.taille / 10_000)
    return 3.0 * couverture_titre + min(densite, 3.0)


def construire_sommaire(sections: list[_Section]) -> str:
    """Sommaire numéroté : les numéros sont les rangs, utilisés pour la sélection."""
    lignes = [f"{s.rang}. {s.titre}" for s in sections if s.titre]
    return "\n".join(lignes)


def construire_contexte(
    texte: str,
    question: str,
    *,
    rangs_prioritaires: set[int] | None = None,
    seuil_integral: int = SEUIL_TEXTE_INTEGRAL,
    budget: int = BUDGET_SELECTION,
) -> ContexteConvention:
    """Prépare le texte de convention à envoyer au LLM pour cette question.

    ``rangs_prioritaires`` — les sections désignées à la lecture du sommaire —
    passent devant le classement lexical. C'est ce qui franchit la barrière de
    vocabulaire : une question sur « un mariage ou un décès » ne contient aucun
    des mots du chapitre « Congés payés. Congés exceptionnels ».
    """
    texte = texte or ""
    sections = decouper_en_sections(texte)
    sommaire = construire_sommaire(sections)

    if len(texte) <= seuil_integral:
        return ContexteConvention(
            texte=texte,
            sommaire=sommaire,
            integral=True,
            caracteres_source=len(texte),
            caracteres_retenus=len(texte),
        )

    prioritaires = rangs_prioritaires or set()
    mots_question = _mots_utiles(question)
    # À pertinence égale, la section la plus courte passe devant : on en retient
    # davantage pour le même budget.
    classees = sorted(
        sections,
        key=lambda s: (
            0 if s.rang in prioritaires else 1,
            -_score(s, mots_question),
            s.taille,
            s.rang,
        ),
    )

    retenues: list[_Section] = []
    total = 0
    for section in classees:
        if total + section.taille > budget and retenues:
            continue
        retenues.append(section)
        total += section.taille
        if total >= budget:
            break

    retenues.sort(key=lambda s: s.rang)
    return ContexteConvention(
        texte="\n\n".join(s.contenu for s in retenues),
        sommaire=sommaire,
        integral=False,
        caracteres_source=len(texte),
        caracteres_retenus=total,
    )
