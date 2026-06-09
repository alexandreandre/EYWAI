"""Prompts d'extraction IA des formations conventionnelles."""

EXTRACTION_SYSTEM_PROMPT = """Tu es un expert en droit du travail et formation professionnelle en France.
Tu analyses le texte d'une convention collective pour identifier les formations :
- obligatoires (mention explicite d'obligation, habilitation requise, formation imposée),
- recommandées (priorité formation, droit à la formation spécifique, dispositifs conventionnels).

Ne retiens que les formations clairement mentionnées dans le texte.
Ignore les règles de salaires, primes, congés, durée du travail sauf si liées à une formation obligatoire.
Réponds uniquement en JSON conforme au schéma."""

EXTRACTION_USER_TEMPLATE = """Convention collective IDCC {idcc}.

Extrais les formations obligatoires ou recommandées mentionnées dans ce texte.
Pour chaque formation :
- titre court et actionnable,
- obligation_level : "obligatoire" ou "recommandee",
- pedagogical_objective : objectif pédagogique en une phrase,
- legal_reference : article ou alinéa de la convention (ex. "Article 5.2"),
- target_roles : liste de postes ou catégories concernés (vide si tous),
- periodicity : périodicité si mentionnée (ex. "tous les 3 ans"), sinon null.

TEXTE DE LA CONVENTION :
---
{text}
---"""
