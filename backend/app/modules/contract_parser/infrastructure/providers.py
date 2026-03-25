"""
Providers (services externes) du module contract_parser.

- PdfTextExtractor : extraction de texte PDF (pdfplumber / PyPDF2 / OCR).
- ExtractionLLMProvider : appels OpenAI (prompts contrat, RIB, questionnaire).
Comportement strictement identique à l'ancien router.
"""

from __future__ import annotations

import io
import json
import os
import traceback
from typing import Any, Dict, Tuple

from app.modules.contract_parser.domain.interfaces import (
    IExtractionLLM,
    IPdfTextExtractor,
)
from app.modules.contract_parser.domain.rules import is_scanned_pdf

# Import des bibliothèques pour la lecture de PDF
try:
    import pdfplumber

    _PDFPLUMBER_AVAILABLE = True
except ImportError:
    _PDFPLUMBER_AVAILABLE = False
    print("WARNING: pdfplumber non disponible")

try:
    import PyPDF2

    _PYPDF2_AVAILABLE = True
except ImportError:
    _PYPDF2_AVAILABLE = False
    print("WARNING: PyPDF2 non disponible")

try:
    from pdf2image import convert_from_bytes
    import pytesseract
    from PIL import Image
    from PIL import ImageEnhance

    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False
    print("WARNING: OCR libraries non disponibles (pdf2image, pytesseract, pillow)")


# ---------------------------------------------------------------------------
# PdfTextExtractor
# ---------------------------------------------------------------------------


class PdfTextExtractor(IPdfTextExtractor):
    """
    Extraction de texte depuis un PDF (pdfplumber → PyPDF2 → OCR).
    Utilise la règle domaine is_scanned_pdf pour la stratégie.
    """

    def _extract_with_pdfplumber(self, file_content: bytes) -> str:
        if not _PDFPLUMBER_AVAILABLE:
            return ""
        try:
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                return text.strip()
        except Exception as e:
            print(f"ERROR: Impossible d'extraire le texte avec pdfplumber : {e}")
            return ""

    def _extract_with_pypdf2(self, file_content: bytes) -> str:
        if not _PYPDF2_AVAILABLE:
            return ""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            print(f"ERROR: Impossible d'extraire le texte avec PyPDF2 : {e}")
            return ""

    def _preprocess_image_for_ocr(self, image: "Image.Image") -> "Image.Image":
        image = image.convert("L")
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.5)
        return image

    def _extract_with_ocr(self, file_content: bytes, max_pages: int = 5) -> str:
        if not _OCR_AVAILABLE:
            return ""
        try:
            print("INFO: Conversion du PDF en images pour OCR...")
            images = convert_from_bytes(
                file_content, dpi=300, first_page=1, last_page=max_pages
            )
            text = ""
            for i, img in enumerate(images):
                print(f"INFO: OCR de la page {i + 1}/{len(images)}...")
                processed_img = self._preprocess_image_for_ocr(img)
                custom_config = r"--oem 3 --psm 6"
                page_text = pytesseract.image_to_string(
                    processed_img, lang="fra", config=custom_config
                )
                text += page_text + "\n"
            return text.strip()
        except Exception as e:
            print(f"ERROR: Impossible d'extraire le texte avec OCR : {e}")
            traceback.print_exc()
            return ""

    def extract_text(self, file_content: bytes) -> Tuple[str, str]:
        text = ""
        method = ""

        if _PDFPLUMBER_AVAILABLE:
            print("INFO: Tentative d'extraction avec pdfplumber...")
            text = self._extract_with_pdfplumber(file_content)
            if text and len(text) > 100 and not is_scanned_pdf(text):
                method = "pdfplumber"
                print(
                    f"INFO: Extraction réussie avec pdfplumber ({len(text)} caractères)"
                )
                return text, method
            elif text:
                print(
                    f"WARNING: pdfplumber a extrait du texte ({len(text)} caractères) mais il semble être un PDF scanné"
                )

        if not text and _PYPDF2_AVAILABLE:
            print("INFO: Tentative d'extraction avec PyPDF2...")
            text = self._extract_with_pypdf2(file_content)
            if text and len(text) > 100 and not is_scanned_pdf(text):
                method = "PyPDF2"
                print(f"INFO: Extraction réussie avec PyPDF2 ({len(text)} caractères)")
                return text, method
            elif text:
                print(
                    f"WARNING: PyPDF2 a extrait du texte ({len(text)} caractères) mais il semble être un PDF scanné"
                )

        if _OCR_AVAILABLE:
            print(
                "INFO: Le PDF semble être scanné ou l'extraction a échoué. Tentative d'OCR..."
            )
            ocr_text = self._extract_with_ocr(file_content, max_pages=5)
            if ocr_text and len(ocr_text) > 50:
                method = "OCR (Tesseract)"
                print(f"INFO: Extraction réussie avec OCR ({len(ocr_text)} caractères)")
                return ocr_text, method

        if text and len(text) > 20:
            method = "Extraction de base (qualité limitée)"
            print(
                f"WARNING: OCR non disponible. Utilisation du texte extrait avec qualité limitée ({len(text)} caractères)"
            )
            return text, method

        if not text or len(text) < 20:
            raise Exception(
                "Impossible d'extraire le texte du PDF avec les méthodes disponibles"
            )

        return text, method


# ---------------------------------------------------------------------------
# ExtractionLLMProvider (prompts + appel OpenAI)
# ---------------------------------------------------------------------------

_CONTRACT_PROMPT = """Tu es un assistant spécialisé dans l'extraction d'informations à partir de contrats de travail français.

Je vais te fournir le texte extrait d'un document de contrat de travail. Ta tâche est d'extraire TOUTES les informations pertinentes suivantes, si elles sont présentes dans le document :

**INFORMATIONS DU SALARIÉ :**
- Prénom (first_name)
- Nom (last_name) (Ne pas écrire le Nom de Famille tout en majuscule dans les champs)
- Email (email) - si disponible
- Numéro de sécurité sociale / NIR (nir) - format : 15 chiffres
- Date de naissance (date_naissance) - format : YYYY-MM-DD
- Lieu de naissance (lieu_naissance)
- Nationalité (nationalite)
- Adresse complète :
  - Rue (adresse.rue)
  - Code postal (adresse.code_postal)
  - Ville (adresse.ville)
- Coordonnées bancaires :
  - IBAN (coordonnees_bancaires.iban)
  - BIC (coordonnees_bancaires.bic)

**INFORMATIONS DU CONTRAT :**
- Date de début / Date d'embauche (hire_date) - format : YYYY-MM-DD
- Intitulé du poste / Job title (job_title)
- Type de contrat (contract_type) - ex : CDI, CDD, etc.
- Statut (statut) - ex : Cadre, Non-Cadre, Agent de maîtrise
- Durée hebdomadaire de travail en heures (duree_hebdomadaire) - nombre décimal
- Temps partiel ? (is_temps_partiel) - boolean (true/false)

**RÉMUNÉRATION ET CLASSIFICATION :**
- Salaire de base mensuel brut (salaire_de_base.valeur) - nombre décimal
- Classification conventionnelle :
  - Groupe d'emploi (classification_conventionnelle.groupe_emploi) - ex : A, B, C, etc.
  - Classe d'emploi (classification_conventionnelle.classe_emploi) - nombre entier
  - Coefficient (classification_conventionnelle.coefficient) - nombre entier

**AVANTAGES EN NATURE :**
- Repas fournis par mois (avantages_en_nature.repas.nombre_par_mois) - nombre entier
- Bénéficie d'un logement ? (avantages_en_nature.logement.beneficie) - boolean
- Bénéficie d'un véhicule ? (avantages_en_nature.vehicule.beneficie) - boolean

**SPÉCIFICITÉS DE PAIE :**
- Prélèvement à la source personnalisé ? (specificites_paie.prelevement_a_la_source.is_personnalise) - boolean
- Taux de prélèvement (specificites_paie.prelevement_a_la_source.taux) - nombre décimal (en %)
- Abonnement de transport mensuel total (specificites_paie.transport.abonnement_mensuel_total) - nombre décimal
- Nombre de titres restaurant par mois (specificites_paie.titres_restaurant.nombre_par_mois) - nombre entier

**MUTUELLE (tableau de lignes) :**
- Liste de lignes de mutuelle (specificites_paie.mutuelle.lignes_specifiques[]) :
  - Libellé (libelle)
  - Montant salarial (montant_salarial) - nombre décimal
  - Montant patronal (montant_patronal) - nombre décimal
  - Part patronale soumise à CSG ? (part_patronale_soumise_a_csg) - boolean
  - Pour la mutuelle, si tu vois cette ligne : AG2R, 154 Rue Anatole France, 92599 LEVALLOIS PERRET Cedex. Comprend "Mutuelle Salarié Seul, avec taux salarial = 31.58€ et taux patronal = 31.57€

**PRÉVOYANCE (pour les cadres uniquement, tableau de lignes) :**
- Adhésion prévoyance ? (specificites_paie.prevoyance.adhesion) - boolean
- Liste de lignes de prévoyance (specificites_paie.prevoyance.lignes_specifiques[]) :
  - Libellé (libelle)
  - Taux salarial en % (salarial) - nombre décimal
  - Taux patronal en % (patronal) - nombre décimal
  - Forfait social en % (forfait_social) - nombre décimal

**INSTRUCTIONS IMPORTANTES :**
1. Si une information n'est PAS présente dans le document, ne l'inclus PAS dans ta réponse JSON.
2. Ne jamais inventer ou deviner une information qui n'est pas explicitement mentionnée.
3. Respecte scrupuleusement les formats demandés (dates en YYYY-MM-DD, nombres décimaux, booleans).
4. Pour les dates, convertis les formats français (ex: "01/03/2024" ou "1er mars 2024") au format ISO (ex: "2024-03-01").
5. Pour les montants, extrait uniquement le nombre (retire les symboles €, les espaces, etc.).
6. Si plusieurs valeurs semblent contradictoires, choisis la plus récente ou la plus fiable.
7. Sois attentif aux variations d'orthographe et de formulation (ex: "N° Sécu", "NIR", "Numéro de Sécurité Sociale").

**FORMAT DE SORTIE :**
Réponds UNIQUEMENT avec un objet JSON valide suivant cette structure :

{
  "extracted_data": {
    "first_name": "...",
    "last_name": "...",
    ...
  },
  "confidence": "high|medium|low",
  "warnings": ["liste des avertissements ou ambiguïtés rencontrées"]
}

N'ajoute AUCUN texte explicatif avant ou après le JSON. Uniquement le JSON pur."""

_RIB_PROMPT = """Tu es un assistant IA spécialisé dans l'extraction de données bancaires depuis des RIB (Relevé d'Identité Bancaire) français.

Ton rôle est d'extraire les informations bancaires suivantes depuis le texte d'un RIB fourni :

**CHAMPS À EXTRAIRE :**

1. **IBAN** (obligatoire) : Format international (FR76... 27 caractères pour la France)
2. **BIC** (obligatoire) : Code d'identification de la banque (8 ou 11 caractères)
3. **Titulaire** (optionnel) : Nom du titulaire du compte
4. **Domiciliation bancaire** (optionnel) : Nom et adresse de l'agence bancaire
5. **Code banque** (optionnel) : 5 chiffres
6. **Code guichet** (optionnel) : 5 chiffres
7. **Numéro de compte** (optionnel) : 11 caractères
8. **Clé RIB** (optionnel) : 2 chiffres

**RÈGLES D'EXTRACTION :**

- Nettoie les espaces dans l'IBAN et le BIC (exemple : "FR76 1234 5678..." → "FR7612345678...")
- Si l'IBAN n'est pas trouvé, cherche les composants séparés (code banque, guichet, numéro de compte, clé)
- Formate toujours l'IBAN en majuscules sans espaces
- Formate toujours le BIC en majuscules sans espaces
- Si une information n'est pas trouvée ou est incertaine, retourne `null` pour ce champ

**FORMAT DE RÉPONSE :**

Tu dois retourner UNIQUEMENT un JSON valide avec cette structure exacte :

{
  "extracted_data": {
    "iban": "string ou null",
    "bic": "string ou null",
    "titulaire": "string ou null",
    "domiciliation": "string ou null",
    "code_banque": "string ou null",
    "code_guichet": "string ou null",
    "numero_compte": "string ou null",
    "cle_rib": "string ou null"
  },
  "confidence": "high" | "medium" | "low",
  "warnings": ["liste de chaînes de caractères avec les avertissements éventuels"]
}

**EXEMPLES DE WARNINGS :**

- "IBAN incomplet ou invalide détecté"
- "BIC non trouvé dans le document"
- "Format de RIB non standard"
- "Qualité du scan faible, vérification manuelle recommandée"

N'ajoute AUCUN texte explicatif avant ou après le JSON. Uniquement le JSON pur."""

_QUESTIONNAIRE_PROMPT = """Tu es un assistant IA spécialisé dans l'extraction de données depuis des questionnaires d'embauche français.

Ton rôle est d'extraire les informations suivantes depuis le texte d'un questionnaire d'embauche fourni :

**INFORMATIONS DU CANDIDAT/SALARIÉ :**
- Prénom (first_name)
- Nom (last_name) - Ne pas écrire le nom de famille tout en majuscules dans les champs
- Email (email) - si disponible
- Numéro de sécurité sociale / NIR (nir) - format : 15 chiffres
- Date de naissance (date_naissance) - format : YYYY-MM-DD
- Lieu de naissance (lieu_naissance)
- Nationalité (nationalite)
- Adresse complète :
  - Rue (adresse.rue)
  - Code postal (adresse.code_postal)
  - Ville (adresse.ville)
- Coordonnées bancaires :
  - IBAN (coordonnees_bancaires.iban)
  - BIC (coordonnees_bancaires.bic)

**INFORMATIONS DU POSTE/CONTRAT :**
- Date de début / Date d'embauche prévue (hire_date) - format : YYYY-MM-DD
- Intitulé du poste / Poste souhaité (job_title)
- Type de contrat souhaité (contract_type) - ex : CDI, CDD, etc.
- Statut (statut) - ex : Cadre, Non-Cadre, Agent de maîtrise
- Durée hebdomadaire de travail en heures (duree_hebdomadaire) - nombre décimal
- Temps partiel ? (is_temps_partiel) - boolean (true/false)

**RÉMUNÉRATION ET CLASSIFICATION :**
- Salaire souhaité / Salaire de base mensuel brut (salaire_de_base.valeur) - nombre décimal
- Classification conventionnelle :
  - Groupe d'emploi (classification_conventionnelle.groupe_emploi) - ex : A, B, C, etc.
  - Classe d'emploi (classification_conventionnelle.classe_emploi) - nombre entier
  - Coefficient (classification_conventionnelle.coefficient) - nombre entier

**AVANTAGES EN NATURE :**
- Repas fournis par mois (avantages_en_nature.repas.nombre_par_mois) - nombre entier
- Bénéficie d'un logement ? (avantages_en_nature.logement.beneficie) - boolean
- Bénéficie d'un véhicule ? (avantages_en_nature.vehicule.beneficie) - boolean

**SPÉCIFICITÉS DE PAIE :**
- Prélèvement à la source personnalisé ? (specificites_paie.prelevement_a_la_source.is_personnalise) - boolean
- Taux de prélèvement (specificites_paie.prelevement_a_la_source.taux) - nombre décimal (en %)
- Abonnement de transport mensuel total (specificites_paie.transport.abonnement_mensuel_total) - nombre décimal
- Nombre de titres restaurant par mois (specificites_paie.titres_restaurant.nombre_par_mois) - nombre entier

**MUTUELLE (tableau de lignes) :**
- Liste de lignes de mutuelle (specificites_paie.mutuelle.lignes_specifiques[]) :
  - Libellé (libelle)
  - Montant salarial (montant_salarial) - nombre décimal
  - Montant patronal (montant_patronal) - nombre décimal
  - Part patronale soumise à CSG ? (part_patronale_soumise_a_csg) - boolean

**PRÉVOYANCE (pour les cadres uniquement, tableau de lignes) :**
- Adhésion prévoyance ? (specificites_paie.prevoyance.adhesion) - boolean
- Liste de lignes de prévoyance (specificites_paie.prevoyance.lignes_specifiques[]) :
  - Libellé (libelle)
  - Taux salarial en % (salarial) - nombre décimal
  - Taux patronal en % (patronal) - nombre décimal
  - Forfait social en % (forfait_social) - nombre décimal

**INSTRUCTIONS IMPORTANTES :**
1. Si une information n'est PAS présente dans le document, ne l'inclus PAS dans ta réponse JSON.
2. Ne jamais inventer ou deviner une information qui n'est pas explicitement mentionnée.
3. Respecte scrupuleusement les formats demandés (dates en YYYY-MM-DD, nombres décimaux, booleans).
4. Pour les dates, convertis les formats français (ex: "01/03/2024" ou "1er mars 2024") au format ISO (ex: "2024-03-01").
5. Pour les montants, extrait uniquement le nombre (retire les symboles €, les espaces, etc.).
6. Si plusieurs valeurs semblent contradictoires, choisis la plus récente ou la plus fiable.
7. Sois attentif aux variations d'orthographe et de formulation (ex: "N° Sécu", "NIR", "Numéro de Sécurité Sociale").
8. Un questionnaire d'embauche peut contenir des informations moins formelles qu'un contrat, sois flexible dans l'interprétation.

**FORMAT DE SORTIE :**
Réponds UNIQUEMENT avec un objet JSON valide suivant cette structure :

{
  "extracted_data": {
    "first_name": "...",
    "last_name": "...",
    ...
  },
  "confidence": "high|medium|low",
  "warnings": ["liste des avertissements ou ambiguïtés rencontrées"]
}

N'ajoute AUCUN texte explicatif avant ou après le JSON. Uniquement le JSON pur."""


class ExtractionLLMProvider(IExtractionLLM):
    """Appels OpenAI (gpt-4o-mini) pour extraction contrat / RIB / questionnaire."""

    def __init__(self) -> None:
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return self._client

    def _call_llm(
        self,
        prompt: str,
        user_content: str,
        max_tokens: int,
        log_prefix: str = "",
    ) -> Dict[str, Any]:
        client = self._get_client()
        full_content = f"{prompt}\n\n{user_content}"
        print(
            f"INFO: Appel de l'API OpenAI (gpt-4o-mini){' ' + log_prefix if log_prefix else ''}..."
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": full_content}],
            max_tokens=max_tokens,
            temperature=0.1,
        )
        raw_response = response.choices[0].message.content or ""
        print(
            f"DEBUG: Réponse brute de GPT-4o-mini{log_prefix}: {raw_response[:500]}..."
        )
        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError as e:
            print(f"ERROR: Impossible de parser la réponse JSON : {e}")
            print(f"DEBUG: Réponse complète : {raw_response}")
            raise ValueError(
                "Le modèle AI n'a pas retourné un JSON valide. Veuillez réessayer."
            ) from e
        if "extracted_data" not in parsed:
            parsed = {
                "extracted_data": parsed,
                "confidence": "medium",
                "warnings": [],
            }
        return parsed

    def extract_contract(self, extracted_text: str) -> Dict[str, Any]:
        user_content = f"--- CONTENU DU CONTRAT PDF ---\n\n{extracted_text}"
        return self._call_llm(
            _CONTRACT_PROMPT,
            user_content,
            max_tokens=4096,
            log_prefix="pour l'analyse du texte",
        )

    def extract_rib(self, extracted_text: str) -> Dict[str, Any]:
        user_content = f"--- CONTENU DU RIB PDF ---\n\n{extracted_text}"
        return self._call_llm(
            _RIB_PROMPT,
            user_content,
            max_tokens=2048,
            log_prefix="pour l'analyse du RIB",
        )

    def extract_questionnaire(self, extracted_text: str) -> Dict[str, Any]:
        user_content = (
            f"--- CONTENU DU QUESTIONNAIRE D'EMBAUCHE PDF ---\n\n{extracted_text}"
        )
        return self._call_llm(
            _QUESTIONNAIRE_PROMPT,
            user_content,
            max_tokens=4096,
            log_prefix="pour l'analyse du questionnaire",
        )


# Instances singleton pour l'application
pdf_text_extractor = PdfTextExtractor()
extraction_llm_provider = ExtractionLLMProvider()
