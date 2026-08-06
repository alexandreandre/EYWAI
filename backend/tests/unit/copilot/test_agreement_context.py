"""Tests du contexte convention collective (sélection de sections)."""

from app.modules.copilot.domain.agreement_context import (
    construire_contexte,
    construire_sommaire,
    decouper_en_sections,
)


def _convention(nb_sections: int, taille: int = 5_000) -> str:
    """Convention synthétique : une section par thème, de taille contrôlée."""
    themes = [
        "Période d'essai",
        "Préavis de licenciement",
        "Congés payés",
        "Prime d'ancienneté",
        "Hygiène et sécurité",
        "Classifications",
        "Maladie et prévoyance",
        "Durée du travail",
    ]
    blocs = []
    for i in range(nb_sections):
        theme = themes[i % len(themes)]
        blocs.append(f"## {theme} {i}\n\n{theme} : " + ("texte " * (taille // 6)))
    return "\n\n".join(blocs)


class TestDecoupage:
    def test_decoupe_sur_les_titres(self):
        sections = decouper_en_sections("## A\n\ncorps a\n\n## B\n\ncorps b")
        assert [s.titre for s in sections] == ["A", "B"]

    def test_conserve_l_entete_avant_le_premier_titre(self):
        sections = decouper_en_sections("préambule\n\n## A\n\ncorps")
        assert sections[0].titre == ""
        assert "préambule" in sections[0].contenu

    def test_texte_sans_titre_reste_une_section(self):
        sections = decouper_en_sections("un texte plat sans titre")
        assert len(sections) == 1
        assert sections[0].contenu == "un texte plat sans titre"

    def test_sommaire_numerote_les_titres(self):
        """Les numéros sont les rangs : ils servent à désigner les sections."""
        sommaire = construire_sommaire(decouper_en_sections("## A\n\nx\n\n### B\n\ny"))
        assert sommaire == "0. A\n1. B"


class TestContexte:
    def test_petit_texte_transmis_integralement(self):
        texte = "## Période d'essai\n\nla période d'essai est de deux mois"
        contexte = construire_contexte(texte, "quelle période d'essai ?")
        assert contexte.integral is True
        assert contexte.texte == texte

    def test_gros_texte_selectionne_la_section_pertinente(self):
        texte = _convention(40)
        contexte = construire_contexte(texte, "quelle est la durée de la période d'essai ?")
        assert contexte.integral is False
        assert "Période d'essai" in contexte.texte
        assert contexte.caracteres_retenus < contexte.caracteres_source

    def test_selection_respecte_le_budget(self):
        texte = _convention(60)
        contexte = construire_contexte(texte, "préavis", budget=30_000)
        assert contexte.caracteres_retenus <= 30_000 + 6_000  # une section de marge

    def test_sommaire_complet_meme_quand_on_selectionne(self):
        texte = _convention(40)
        contexte = construire_contexte(texte, "congés payés")
        # Toutes les sections figurent au sommaire, y compris celles écartées.
        assert contexte.sommaire.count("\n") + 1 == 40

    def test_sections_restituees_dans_l_ordre_du_document(self):
        texte = _convention(40)
        contexte = construire_contexte(texte, "prime d'ancienneté et congés payés")
        positions = [
            contexte.texte.index(ligne)
            for ligne in contexte.texte.split("\n\n## ")[:3]
            if ligne in contexte.texte
        ]
        assert positions == sorted(positions)

    def test_une_grosse_section_hors_sujet_ne_mange_pas_le_budget(self):
        """Régression : la présence brute favorisait les sections géantes.

        Une section de 60 000 caractères contient presque toujours chaque mot de
        la question au moins une fois ; sans mesure de densité, elle remontait
        avant la petite section qui traite réellement du sujet.
        """
        bruit = (
            "## Protection sociale complémentaire\n\n"
            + "garantie prévoyance préavis licenciement ancienneté cotisation "
            * 900
        )
        pertinent = (
            "## Préavis de licenciement\n\n"
            "Le préavis de licenciement est de deux mois au-delà de deux ans "
            "d'ancienneté. Préavis, préavis, préavis."
        )
        contexte = construire_contexte(
            bruit + "\n\n" + pertinent,
            "quel préavis de licenciement ?",
            budget=20_000,
        )
        assert "## Préavis de licenciement" in contexte.texte

    def test_rangs_prioritaires_passent_devant_le_lexical(self):
        """La section désignée est retenue même sans mot commun avec la question."""
        texte = _convention(40)
        sections = decouper_en_sections(texte)
        cible = next(s for s in sections if s.titre.startswith("Hygiène"))
        contexte = construire_contexte(
            texte,
            "combien de jours pour un mariage ?",
            rangs_prioritaires={cible.rang},
            budget=12_000,
        )
        assert cible.titre in contexte.texte

    def test_question_vide_ne_plante_pas(self):
        contexte = construire_contexte(_convention(40), "")
        assert contexte.texte
        assert contexte.caracteres_retenus > 0

    def test_texte_absent(self):
        contexte = construire_contexte("", "peu importe")
        assert contexte.texte == ""
        assert contexte.integral is True
