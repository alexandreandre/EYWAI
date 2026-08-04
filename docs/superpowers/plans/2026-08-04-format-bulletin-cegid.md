# Bulletin de paie au format Cegid — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faire sortir le bulletin de paie PDF au gabarit du cabinet (Cegid) — une page A4 dense à colonne latérale — sans toucher au moteur de calcul, et brancher l'aperçu de la page RH d'édition sur ce même rendu.

**Architecture:** Un module de présentation pur, `bulletin_view.py`, transforme le `bulletin_final` du moteur en boîtes prêtes à afficher (bandeau, compteurs, identité, lignes, colonne latérale, pied). Le template Jinja devient bête : il parcourt ces boîtes. Un endpoint d'aperçu rend le même template à partir des données éditées, ce qui permet de supprimer la réimplémentation React de la mise en page.

**Tech Stack:** Python 3.12 / FastAPI, Jinja2, WeasyPrint, pytest ; React 19 / TypeScript / Vite, vitest.

**Spec :** [docs/superpowers/specs/2026-08-04-format-bulletin-cegid-design.md](../specs/2026-08-04-format-bulletin-cegid-design.md)

## Global Constraints

- **Aucune modification du moteur de calcul.** Les seuls changements côté moteur sont additifs : exposer dans le bulletin des données déjà connues (matricule, civilité, mode de paiement, SMIC, plafond). Aucun montant ne change. Si un test de calcul existant casse, c'est une erreur, pas un ajustement à faire.
- `bulletin_view.py` est **pur** : pas d'accès base, pas de fichier, pas d'horloge. Tout vient du dictionnaire reçu. C'est ce qui le rend testable sans rendre un PDF.
- Le français est la langue du code métier de ce dépôt : noms de fonctions, de clés et commentaires en français, comme dans `bulletin.py` et `cotisations_rubriques.py`.
- Un bulletin doit rester lisible même avec des données partielles : toute donnée absente se replie ou disparaît, jamais de `None` affiché ni de section vide.
- Les tests unitaires tournent avec `cd backend && python -m pytest`. La CI ne bloque que sur `tests/unit` ; 51 échecs pré-existants dans `tests/integration` (schedules, saisies_avances) ne sont pas de votre fait.
- Commits en français, format conventionnel (`feat(paie): …`), avec `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
- La branche est partagée avec d'autres sessions : stager **des chemins explicites**, jamais `git add -A`.

## Structure des fichiers

| Fichier | Responsabilité |
|---|---|
| `backend/app/modules/payroll/documents/bulletin_view.py` *(créé)* | Fonction pure `bulletin_final → boîtes du gabarit`. Replis, agrégations, formatage, codes de rubriques. |
| `backend/app/runtime/payroll/templates/template_bulletin.html` *(réécrit)* | Gabarit A4 sans logique : parcourt les boîtes de la vue. |
| `backend/app/modules/payroll/engine/bulletin.py` *(modifié)* | Ajouts additifs à `en_tete` (année, mois, matricule, civilité, adresse, mode de paiement, classification brute) et nouveau bloc `parametres`. |
| `backend/app/modules/payroll/documents/payslip_generator.py`, `payslip_generator_forfait.py` *(modifiés)* | Font remonter les colonnes `employees` manquantes dans le contrat. |
| `backend/app/modules/payroll/documents/payslip_run_heures.py`, `payslip_run_forfait.py`, `payslip_editor.py`, `simulated_payslip_generator.py` *(modifiés)* | Passent par la vue avant de rendre le template. |
| `backend/app/modules/payslips/api/router.py`, `schemas/requests.py`, `schemas/responses.py` *(modifiés)* | Endpoint `POST /api/payslips/{id}/preview`. |
| `frontend/src/components/payslip-edit/PayslipPreviewFrame.tsx` *(créé)* | Affiche le rendu serveur dans une iframe isolée. |
| `frontend/src/components/payslip-edit/PreviewPanel.tsx` *(supprimé)* | Réimplémentation React de la mise en page — remplacée par le rendu réel. |
| `backend/tests/unit/payroll/test_bulletin_view.py` *(créé)* | Le gros de la couverture : la vue, testée sans rendu. |

---

### Task 1 : Faire remonter les données manquantes dans le bulletin

Tout ce que Cegid imprime existe en base mais n'arrive pas jusqu'au bulletin. Cette tâche est purement additive : on ajoute des clés, on n'en modifie aucune.

**Files:**
- Modify: `backend/app/modules/payroll/documents/payslip_generator.py:797-806` (bloc `salarie` du contrat)
- Modify: `backend/app/modules/payroll/documents/payslip_generator_forfait.py:371-377` (bloc `salarie` du contrat)
- Modify: `backend/app/modules/payroll/engine/bulletin.py:459-484` (`en_tete` de `creer_bulletin_final`)
- Test: `backend/tests/unit/payroll/test_bulletin_officiel.py`

**Interfaces:**
- Consumes: rien.
- Produces: `bulletin["en_tete"]["annee"]: int`, `["mois"]: int` ; `bulletin["en_tete"]["salarie"]["matricule"|"sexe"|"adresse"|"mode_paiement"|"classification_brute"]` ; `bulletin["parametres"]: {"smic_horaire": float, "pss_mensuel": float}`.

- [ ] **Step 1 : Écrire le test qui échoue**

Dans `backend/tests/unit/payroll/test_bulletin_officiel.py`, ajouter à la fin du fichier :

```python
class TestDonneesEnTeteGabarit:
    """Données que le gabarit Cegid imprime et que le bulletin doit porter."""

    def _bulletin(self):
        ctx = build_test_contexte(salaire_base=2000.0)
        ctx.year = 2026
        ctx.contrat["salarie"]["matricule"] = "ALVES"
        ctx.contrat["salarie"]["sexe"] = "M"
        ctx.contrat["salarie"]["mode_paiement"] = "virement"
        ctx.contrat["salarie"]["adresse"] = {
            "rue": "32 rue de la Fabrique",
            "code_postal": "79250",
            "ville": "NUEIL LES AUBIERS",
        }
        lignes, total_sal = calculer_cotisations(ctx, 2000.0)
        nets = calculer_net_et_impot(ctx, 2000.0, lignes, total_sal, [], 0.0)
        return creer_bulletin_final(ctx, 2000.0, [], lignes, nets, [], 2026, 6)

    def test_en_tete_porte_annee_et_mois(self):
        en_tete = self._bulletin()["en_tete"]
        assert en_tete["annee"] == 2026
        assert en_tete["mois"] == 6

    def test_en_tete_porte_les_donnees_salarie_du_gabarit(self):
        salarie = self._bulletin()["en_tete"]["salarie"]
        assert salarie["matricule"] == "ALVES"
        assert salarie["sexe"] == "M"
        assert salarie["mode_paiement"] == "virement"
        assert salarie["adresse"]["ville"] == "NUEIL LES AUBIERS"

    def test_bulletin_porte_smic_et_plafond(self):
        parametres = self._bulletin()["parametres"]
        assert parametres["smic_horaire"] > 0
        assert parametres["pss_mensuel"] > 0
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

Run: `cd backend && python -m pytest tests/unit/payroll/test_bulletin_officiel.py::TestDonneesEnTeteGabarit -v`
Expected: FAIL, `KeyError: 'annee'` sur le premier test.

- [ ] **Step 3 : Enrichir l'en-tête du bulletin**

Dans `backend/app/modules/payroll/engine/bulletin.py`, remplacer le bloc `"salarie": {…}` de `creer_bulletin_final` (autour de la ligne 467) par :

```python
            "salarie": {
                "nom_complet": f"{contexte.contrat.get('salarie', {}).get('prenom')} {contexte.contrat.get('salarie', {}).get('nom')}",
                "nom": contexte.contrat.get("salarie", {}).get("nom"),
                "prenom": contexte.contrat.get("salarie", {}).get("prenom"),
                "sexe": contexte.contrat.get("salarie", {}).get("sexe"),
                "matricule": contexte.contrat.get("salarie", {}).get("matricule"),
                "adresse": contexte.contrat.get("salarie", {}).get("adresse"),
                "mode_paiement": contexte.contrat.get("salarie", {}).get(
                    "mode_paiement"
                ),
                "nir": contexte.contrat.get("salarie", {}).get("nir"),
                "emploi": contexte.contrat.get("contrat", {}).get("emploi"),
                "statut": contexte.statut_salarie,
                "type_contrat": contexte.type_contrat,
                "is_alternant": contexte.is_alternant,
                "date_entree": contexte.contrat.get("contrat", {}).get("date_entree"),
                "date_anciennete": contexte.contrat.get("contrat", {}).get(
                    "seniority_reference_date"
                )
                or contexte.contrat.get("contrat", {}).get("date_entree"),
                "classification": _formater_classification(contexte.contrat),
                "classification_brute": contexte.contrat.get("contrat", {}).get(
                    "classification_conventionnelle"
                ),
                "convention_collective": _formater_convention_collective(
                    contexte.contrat
                ),
            },
```

Puis, dans le même dictionnaire `"en_tete"`, ajouter juste après `"periode": periode_formatee,` :

```python
            "annee": annee,
            "mois": mois,
```

Enfin, ajouter une clé de premier niveau dans le dictionnaire `bulletin`, juste après `"salaire_brut": salaire_brut,` :

```python
        "parametres": {
            "smic_horaire": contexte.smic_horaire,
            "pss_mensuel": (contexte.baremes.get("pss", {}) or {}).get("mensuel", 0.0)
            or 0.0,
        },
```

- [ ] **Step 4 : Faire remonter les colonnes `employees` dans les deux générateurs**

Dans `backend/app/modules/payroll/documents/payslip_generator.py`, dans `contrat_json_content["salarie"]`, ajouter après la ligne `"nationalite": employee_data.get("nationalite"),` :

```python
                "sexe": employee_data.get("sexe"),
                "matricule": employee_data.get("matricule"),
                "mode_paiement": employee_data.get("salary_payment_method"),
```

et dans `contrat_json_content["contrat"]`, après `"emploi": employee_data.get("job_title"),` :

```python
                "classification_conventionnelle": _parse_if_json_string(
                    employee_data.get("classification_conventionnelle")
                ),
```

Dans `backend/app/modules/payroll/documents/payslip_generator_forfait.py`, le bloc `salarie` est plus pauvre (pas d'adresse). Le compléter :

```python
            "salarie": {
                "nom": employee_data.get("last_name"),
                "prenom": employee_data.get("first_name"),
                "nir": employee_data.get("nir"),
                "date_naissance": employee_data.get("date_naissance"),
                "sexe": employee_data.get("sexe"),
                "matricule": employee_data.get("matricule"),
                "mode_paiement": employee_data.get("salary_payment_method"),
                "adresse": _parse_if_json_string(employee_data.get("adresse")),
            },
```

`_parse_if_json_string` y est déjà importé depuis `payslip_generator` — vérifier l'import en tête de fichier et l'ajouter s'il manque.

Ajouter également, dans le `contrat` du générateur forfait, après `"emploi"` s'il existe (sinon à la suite de `"statut"`) :

```python
                "emploi": employee_data.get("job_title"),
                "classification_conventionnelle": _parse_if_json_string(
                    employee_data.get("classification_conventionnelle")
                ),
```

- [ ] **Step 5 : Lancer les tests**

Run: `cd backend && python -m pytest tests/unit/payroll/ -v`
Expected: PASS, y compris les tests pré-existants de `test_bulletin_officiel.py` (aucun montant n'a changé).

- [ ] **Step 6 : Commit**

```bash
git add backend/app/modules/payroll/engine/bulletin.py \
        backend/app/modules/payroll/documents/payslip_generator.py \
        backend/app/modules/payroll/documents/payslip_generator_forfait.py \
        backend/tests/unit/payroll/test_bulletin_officiel.py
git commit -m "feat(paie): exposer les données d'en-tête du gabarit dans le bulletin"
```

---

### Task 2 : Module de vue — bandeau, salarié, identité

**Files:**
- Create: `backend/app/modules/payroll/documents/bulletin_view.py`
- Test: `backend/tests/unit/payroll/test_bulletin_view.py`

**Interfaces:**
- Consumes: `bulletin["en_tete"]` enrichi par la Task 1.
- Produces: `construire_vue_bulletin(bulletin: dict) -> dict` avec les clés `bandeau`, `salarie`, `identite` ; helpers `_formater_nir(valeur) -> str`, `_civilite(sexe) -> str | None`, `_date_fr(valeur) -> str`.

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer `backend/tests/unit/payroll/test_bulletin_view.py` :

```python
"""Vue de présentation du bulletin — gabarit Cegid."""

from __future__ import annotations

import pytest

from app.modules.payroll.documents.bulletin_view import (
    _civilite,
    _date_fr,
    _formater_nir,
    construire_vue_bulletin,
)


def bulletin_minimal() -> dict:
    """Bulletin réduit aux clés que la vue consomme, calqué sur CARTOL juin 2026."""
    return {
        "en_tete": {
            "periode": "Juin 2026",
            "annee": 2026,
            "mois": 6,
            "date_paiement": "30/06/2026",
            "entreprise": {
                "raison_sociale": "Société CARTOL",
                "siret": "95147478200020",
                "naf_ape": "2562B",
                "adresse": {
                    "rue": "10 BOULEVARD GEORGES POMPIDOU",
                    "code_postal": "79140",
                    "ville": "CERIZAY",
                },
            },
            "salarie": {
                "nom": "ALVES",
                "prenom": "Lucas",
                "nom_complet": "Lucas ALVES",
                "sexe": "M",
                "matricule": "ALVES",
                "nir": "102098519123974",
                "adresse": {
                    "rue": "32 rue de la Fabrique",
                    "code_postal": "79250",
                    "ville": "NUEIL LES AUBIERS",
                },
                "mode_paiement": "virement",
                "emploi": "Opérateur polyvalent",
                "date_entree": "2026-04-08",
                "date_anciennete": "2026-04-08",
                "classification_brute": {"coefficient": "A"},
                "convention_collective": "Convention collective nationale de la métallurgie",
            },
        },
        "calcul_du_brut": [],
        "details_conges": [],
        "details_absences": [],
        "salaire_brut": 1436.21,
        "cotisations_officielles": [],
        "structure_cotisations": {"total_salarial": 0.0, "total_patronal": 0.0},
        "synthese_net": {},
        "primes_non_soumises": [],
        "net_a_payer": 910.64,
        "pied_de_page": {},
        "parametres": {"smic_horaire": 12.31, "pss_mensuel": 3337.50},
    }


class TestHelpers:
    def test_nir_groupe_comme_cegid(self):
        assert _formater_nir("102098519123974") == "1 02 09 85 191 239 74"

    def test_nir_non_standard_rendu_tel_quel(self):
        assert _formater_nir("12345") == "12345"

    def test_nir_absent_donne_chaine_vide(self):
        assert _formater_nir(None) == ""

    @pytest.mark.parametrize("valeur", ["M", "m", "H", "1"])
    def test_civilite_masculine(self, valeur):
        assert _civilite(valeur) == "MR"

    @pytest.mark.parametrize("valeur", ["F", "f", "2"])
    def test_civilite_feminine(self, valeur):
        assert _civilite(valeur) == "MME"

    def test_civilite_inconnue_absente(self):
        assert _civilite(None) is None
        assert _civilite("X") is None

    def test_date_iso_vers_francais(self):
        assert _date_fr("2026-04-08") == "08/04/2026"

    def test_date_absente_donne_chaine_vide(self):
        assert _date_fr(None) == ""


class TestBandeau:
    def test_bandeau_reprend_identification_entreprise(self):
        bandeau = construire_vue_bulletin(bulletin_minimal())["bandeau"]
        assert bandeau["raison_sociale"] == "Société CARTOL"
        assert bandeau["siret"] == "95147478200020"
        assert bandeau["naf_ape"] == "2562B"
        assert bandeau["adresse"] == [
            "10 BOULEVARD GEORGES POMPIDOU",
            "79140 CERIZAY",
        ]

    def test_bandeau_calcule_les_bornes_de_periode(self):
        bandeau = construire_vue_bulletin(bulletin_minimal())["bandeau"]
        assert bandeau["periode"] == "Juin 2026"
        assert bandeau["du"] == "01/06/2026"
        assert bandeau["au"] == "30/06/2026"

    def test_bandeau_sans_mois_n_invente_pas_de_bornes(self):
        bulletin = bulletin_minimal()
        del bulletin["en_tete"]["mois"]
        bandeau = construire_vue_bulletin(bulletin)["bandeau"]
        assert bandeau["du"] == ""
        assert bandeau["au"] == ""


class TestSalarieEtIdentite:
    def test_nom_precede_de_la_civilite_nom_en_premier(self):
        salarie = construire_vue_bulletin(bulletin_minimal())["salarie"]
        assert salarie["civilite"] == "MR"
        assert salarie["nom_ligne"] == "ALVES Lucas"

    def test_adresse_postale_sur_deux_lignes(self):
        salarie = construire_vue_bulletin(bulletin_minimal())["salarie"]
        assert salarie["adresse"] == ["32 rue de la Fabrique", "79250 NUEIL LES AUBIERS"]

    def test_identite_reprend_matricule_nir_et_emploi(self):
        identite = construire_vue_bulletin(bulletin_minimal())["identite"]
        assert identite["matricule"] == "ALVES"
        assert identite["nir"] == "1 02 09 85 191 239 74"
        assert identite["emploi"] == "Opérateur polyvalent"
        assert identite["date_entree"] == "08/04/2026"
        assert identite["coefficient"] == "A"

    def test_anciennete_se_replie_sur_la_date_d_entree(self):
        bulletin = bulletin_minimal()
        bulletin["en_tete"]["salarie"]["date_anciennete"] = None
        identite = construire_vue_bulletin(bulletin)["identite"]
        assert identite["anciennete"] == "08/04/2026"
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && python -m pytest tests/unit/payroll/test_bulletin_view.py -v`
Expected: FAIL à la collecte, `ModuleNotFoundError: app.modules.payroll.documents.bulletin_view`.

- [ ] **Step 3 : Écrire le module**

Créer `backend/app/modules/payroll/documents/bulletin_view.py` :

```python
"""Vue de présentation du bulletin de paie — gabarit Cegid.

Transforme le `bulletin_final` produit par le moteur en boîtes prêtes à
afficher. Fonction pure : aucun accès base, fichier ou horloge, tout vient du
dictionnaire reçu. C'est le seul endroit où vivent les replis, les agrégations
et le formatage — le template ne fait que parcourir le résultat.
"""

from __future__ import annotations

import calendar
from typing import Any, Dict, List, Optional

CIVILITES_MASCULINES = {"M", "H", "MR", "MASCULIN", "1"}
CIVILITES_FEMININES = {"F", "MME", "FEMININ", "FÉMININ", "2"}

# Découpage du NIR tel que Cegid l'imprime : 1 02 09 85 191 239 74
GROUPES_NIR = (1, 2, 2, 2, 3, 3, 2)


def _civilite(sexe: Any) -> Optional[str]:
    valeur = str(sexe or "").strip().upper()
    if valeur in CIVILITES_MASCULINES:
        return "MR"
    if valeur in CIVILITES_FEMININES:
        return "MME"
    return None


def _formater_nir(valeur: Any) -> str:
    brut = "".join(c for c in str(valeur or "") if c.isalnum()).upper()
    if len(brut) != 15:
        return brut
    morceaux: List[str] = []
    position = 0
    for taille in GROUPES_NIR:
        morceaux.append(brut[position : position + taille])
        position += taille
    return " ".join(morceaux)


def _date_fr(valeur: Any) -> str:
    if not valeur:
        return ""
    texte = str(valeur)[:10]
    if len(texte) == 10 and texte[4] == "-" and texte[7] == "-":
        return f"{texte[8:10]}/{texte[5:7]}/{texte[0:4]}"
    return texte


def _lignes_adresse(adresse: Any) -> List[str]:
    """Adresse postale sur deux lignes : rue, puis code postal + ville."""
    if not isinstance(adresse, dict):
        return []
    lignes = []
    rue = (adresse.get("rue") or "").strip()
    if rue:
        lignes.append(rue)
    localite = f"{adresse.get('code_postal') or ''} {adresse.get('ville') or ''}".strip()
    if localite:
        lignes.append(localite)
    return lignes


def construire_bandeau(bulletin: Dict[str, Any]) -> Dict[str, Any]:
    en_tete = bulletin.get("en_tete") or {}
    entreprise = en_tete.get("entreprise") or {}
    annee = en_tete.get("annee")
    mois = en_tete.get("mois")
    du = au = ""
    if annee and mois:
        dernier_jour = calendar.monthrange(int(annee), int(mois))[1]
        du = f"01/{int(mois):02d}/{int(annee)}"
        au = f"{dernier_jour:02d}/{int(mois):02d}/{int(annee)}"
    return {
        "raison_sociale": entreprise.get("raison_sociale") or "",
        "adresse": _lignes_adresse(entreprise.get("adresse")),
        "siret": entreprise.get("siret") or "",
        "naf_ape": entreprise.get("naf_ape") or "",
        "periode": en_tete.get("periode") or "",
        "date_paiement": en_tete.get("date_paiement") or "",
        "du": du,
        "au": au,
    }


def construire_salarie(bulletin: Dict[str, Any]) -> Dict[str, Any]:
    salarie = ((bulletin.get("en_tete") or {}).get("salarie")) or {}
    nom = (salarie.get("nom") or "").strip()
    prenom = (salarie.get("prenom") or "").strip()
    nom_ligne = f"{nom.upper()} {prenom}".strip() if nom else (
        salarie.get("nom_complet") or ""
    )
    return {
        "civilite": _civilite(salarie.get("sexe")),
        "nom_ligne": nom_ligne,
        "adresse": _lignes_adresse(salarie.get("adresse")),
    }


def construire_identite(bulletin: Dict[str, Any]) -> Dict[str, Any]:
    salarie = ((bulletin.get("en_tete") or {}).get("salarie")) or {}
    classification = salarie.get("classification_brute")
    if not isinstance(classification, dict):
        classification = {}
    date_entree = _date_fr(salarie.get("date_entree"))
    return {
        "matricule": salarie.get("matricule") or "",
        "nir": _formater_nir(salarie.get("nir")),
        "date_entree": date_entree,
        "emploi": salarie.get("emploi") or "",
        # Repli documenté : 81 actifs sur 241 n'ont pas de date de reprise
        # d'ancienneté, leur ancienneté part de la date d'entrée.
        "anciennete": _date_fr(salarie.get("date_anciennete")) or date_entree,
        "qualification": classification.get("qualification") or "",
        "classification": classification.get("niveau")
        or classification.get("classification")
        or "",
        "coefficient": classification.get("coefficient") or "",
        "convention_collective": salarie.get("convention_collective") or "",
    }


def construire_vue_bulletin(bulletin: Dict[str, Any]) -> Dict[str, Any]:
    """Point d'entrée unique : le bulletin du moteur, vu par le gabarit."""
    return {
        "bandeau": construire_bandeau(bulletin),
        "salarie": construire_salarie(bulletin),
        "identite": construire_identite(bulletin),
    }
```

- [ ] **Step 4 : Lancer les tests**

Run: `cd backend && python -m pytest tests/unit/payroll/test_bulletin_view.py -v`
Expected: PASS, 15 tests.

- [ ] **Step 5 : Commit**

```bash
git add backend/app/modules/payroll/documents/bulletin_view.py \
        backend/tests/unit/payroll/test_bulletin_view.py
git commit -m "feat(paie): vue du bulletin — bandeau, salarié, identité"
```

---

### Task 3 : Bloc compteurs de congés

Le bloc en haut à gauche du gabarit : `Acquis / Total pris / Solde` en lignes, une colonne par compteur. C'est ici que se fond la section `#solde-conges` du template actuel, RTT et repos compensateur compris.

**Files:**
- Modify: `backend/app/modules/payroll/documents/bulletin_view.py`
- Test: `backend/tests/unit/payroll/test_bulletin_view.py`

**Interfaces:**
- Consumes: `construire_vue_bulletin` de la Task 2 ; `bulletin["pied_de_page"]["solde_conges"]` produit par `build_solde_conges_pied_de_page`.
- Produces: clé `compteurs` de la vue : `None`, ou `{"date_reference": str, "colonnes": [{"titre", "acquis", "pris", "solde"}], "notes": [str]}`.

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à `backend/tests/unit/payroll/test_bulletin_view.py` :

```python
def solde_conges_complet() -> dict:
    return {
        "date_reference": "30/06/2026",
        "conges_payes": {"periode": "2026-2027", "acquis": 2.08, "pris": 0.0, "solde": 2.08},
        "conges_payes_periode_precedente": {
            "periode": "2025-2026",
            "acquis": 4.0,
            "pris": 0.0,
            "solde": 4.0,
        },
        "rtt": {"acquis": 0.0, "pris": 0.0, "solde": 0.0},
        "repos_compensateur": {"acquis": 0.0, "pris": 0.0, "solde": 0.0},
        "cp_seniority_days": 0,
    }


class TestCompteurs:
    def test_colonnes_cp_dans_l_ordre_cegid(self):
        bulletin = bulletin_minimal()
        bulletin["pied_de_page"]["solde_conges"] = solde_conges_complet()
        compteurs = construire_vue_bulletin(bulletin)["compteurs"]
        assert [c["titre"] for c in compteurs["colonnes"]] == ["CP N-1", "CP N"]
        assert compteurs["colonnes"][0]["solde"] == 4.0
        assert compteurs["date_reference"] == "30/06/2026"

    def test_rtt_et_repos_ajoutes_seulement_s_ils_existent(self):
        bulletin = bulletin_minimal()
        solde = solde_conges_complet()
        solde["rtt"] = {"acquis": 10.0, "pris": 2.0, "solde": 8.0}
        solde["repos_compensateur"] = {"acquis": 3.0, "pris": 0.0, "solde": 3.0}
        bulletin["pied_de_page"]["solde_conges"] = solde
        compteurs = construire_vue_bulletin(bulletin)["compteurs"]
        assert [c["titre"] for c in compteurs["colonnes"]] == [
            "CP N-1",
            "CP N",
            "RTT",
            "Repos comp.",
        ]

    def test_cp_periode_precedente_vide_masquee(self):
        bulletin = bulletin_minimal()
        solde = solde_conges_complet()
        solde["conges_payes_periode_precedente"] = {"acquis": 0.0, "pris": 0.0, "solde": 0.0}
        bulletin["pied_de_page"]["solde_conges"] = solde
        compteurs = construire_vue_bulletin(bulletin)["compteurs"]
        assert [c["titre"] for c in compteurs["colonnes"]] == ["CP N"]

    def test_notes_annexes_reprises_en_bas_du_bloc(self):
        bulletin = bulletin_minimal()
        solde = solde_conges_complet()
        solde["cp_seniority_days"] = 2
        solde["fractionnement"] = {
            "jours_acquis": 1,
            "libelle": "1 jour de fractionnement",
            "reference_date": "31/05/2026",
        }
        bulletin["pied_de_page"]["solde_conges"] = solde
        compteurs = construire_vue_bulletin(bulletin)["compteurs"]
        assert any("fractionnement" in note for note in compteurs["notes"])
        assert any("ancienneté" in note for note in compteurs["notes"])

    def test_sans_solde_de_conges_pas_de_bloc(self):
        assert construire_vue_bulletin(bulletin_minimal())["compteurs"] is None
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && python -m pytest tests/unit/payroll/test_bulletin_view.py::TestCompteurs -v`
Expected: FAIL, `KeyError: 'compteurs'`.

- [ ] **Step 3 : Implémenter le bloc**

Ajouter dans `bulletin_view.py`, avant `construire_vue_bulletin` :

```python
def _colonne_compteur(titre: str, compteur: Any) -> Dict[str, Any]:
    donnees = compteur if isinstance(compteur, dict) else {}
    return {
        "titre": titre,
        "acquis": float(donnees.get("acquis") or 0.0),
        "pris": float(donnees.get("pris") or 0.0),
        "solde": float(donnees.get("solde") or 0.0),
    }


def _compteur_alimente(compteur: Any) -> bool:
    donnees = compteur if isinstance(compteur, dict) else {}
    return any(
        float(donnees.get(cle) or 0.0) for cle in ("acquis", "pris", "solde")
    )


def construire_compteurs(bulletin: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    solde = ((bulletin.get("pied_de_page") or {}).get("solde_conges")) or {}
    if not solde:
        return None

    colonnes: List[Dict[str, Any]] = []
    precedente = solde.get("conges_payes_periode_precedente")
    if _compteur_alimente(precedente):
        colonnes.append(_colonne_compteur("CP N-1", precedente))
    colonnes.append(_colonne_compteur("CP N", solde.get("conges_payes")))
    if _compteur_alimente(solde.get("rtt")):
        colonnes.append(_colonne_compteur("RTT", solde.get("rtt")))
    if _compteur_alimente(solde.get("repos_compensateur")):
        colonnes.append(_colonne_compteur("Repos comp.", solde.get("repos_compensateur")))

    notes: List[str] = []
    fractionnement = solde.get("fractionnement") or {}
    if float(fractionnement.get("jours_acquis") or 0) > 0:
        libelle = fractionnement.get("libelle") or "Jours de fractionnement"
        reference = fractionnement.get("reference_date")
        notes.append(f"{libelle} (réf. {reference})" if reference else libelle)
    jours_anciennete = float(solde.get("cp_seniority_days") or 0)
    if jours_anciennete > 0:
        notes.append(
            f"Dont {jours_anciennete:.0f} j CP ancienneté conventionnels"
        )
    if solde.get("cp_seniority_forfait_note"):
        notes.append(str(solde["cp_seniority_forfait_note"]))

    return {
        "date_reference": solde.get("date_reference") or "",
        "colonnes": colonnes,
        "notes": notes,
    }
```

Puis ajouter `"compteurs": construire_compteurs(bulletin),` dans le dictionnaire retourné par `construire_vue_bulletin`.

- [ ] **Step 4 : Lancer les tests**

Run: `cd backend && python -m pytest tests/unit/payroll/test_bulletin_view.py -v`
Expected: PASS, 20 tests.

- [ ] **Step 5 : Commit**

```bash
git add backend/app/modules/payroll/documents/bulletin_view.py \
        backend/tests/unit/payroll/test_bulletin_view.py
git commit -m "feat(paie): vue du bulletin — bloc compteurs de congés"
```

---

### Task 4 : Corps du bulletin

Le tableau central, à plat : brut, rubriques de cotisations préfixées des codes Cegid, total des retenues, net imposable, puis les lignes hors brut.

Deux points de vigilance, tous deux vérifiés sur le bulletin CARTOL de juin 2026 :

1. **`TOTAL DES RETENUES` exclut la CSG/CRDS non déductible.** Sur ALVES : salarial `99,10 + 5,74 + 57,59 + 99,12 + 16,95 + 29,64 = 308,14` — la CSG non déductible (42,27) n'y est pas. Ne pas réutiliser `structure_cotisations.total_salarial`, qui inclut tout, ni `total_avant_csg_crds`, qui exclut aussi les autres contributions employeur alors que Cegid les compte (le patronal `193,77` les inclut). Le total se calcule dans la vue, en sommant toutes les rubriques sauf `csg_non_deductible`.
2. **La rubrique `Q801` s'affiche après le net imposable**, pas dans le bloc principal.

**Files:**
- Modify: `backend/app/modules/payroll/documents/bulletin_view.py`
- Test: `backend/tests/unit/payroll/test_bulletin_view.py`

**Interfaces:**
- Consumes: `bulletin["cotisations_officielles"]` (liste de `{"code", "libelle", "lignes", "total_salarial", "total_patronal"}`, produite par `construire_cotisations_officielles`).
- Produces: clé `lignes` de la vue : liste plate de dicts `{"type": "detail"|"rubrique"|"total"|"hors_brut", "code": str|None, "libelle": str, "base": float|None, "taux": float|None, "montant_salarial": float|None, "montant_patronal": float|None}`.

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à `backend/tests/unit/payroll/test_bulletin_view.py` :

```python
def bulletin_avec_cotisations() -> dict:
    bulletin = bulletin_minimal()
    bulletin["calcul_du_brut"] = [
        {
            "libelle": "SALAIRE DE BASE",
            "quantite": 151.67,
            "taux": 12.31,
            "gain": 1867.06,
            "perte": None,
        }
    ]
    bulletin["cotisations_officielles"] = [
        {
            "code": "sante",
            "libelle": "Santé",
            "lignes": [
                {
                    "libelle": "Sécu.Soc-Mal.Mater.Inval.Déc.",
                    "base": 1436.21,
                    "taux_salarial": None,
                    "montant_salarial": 0.0,
                    "taux_patronal": 0.07,
                    "montant_patronal": 100.53,
                }
            ],
            "total_salarial": 0.0,
            "total_patronal": 100.53,
        },
        {
            "code": "retraite",
            "libelle": "Retraite",
            "lignes": [
                {
                    "libelle": "Sécu.Soc Plafonnée",
                    "base": 1436.21,
                    "taux_salarial": 0.069,
                    "montant_salarial": 99.10,
                    "taux_patronal": 0.0855,
                    "montant_patronal": 122.80,
                }
            ],
            "total_salarial": 99.10,
            "total_patronal": 122.80,
        },
        {
            "code": "csg_non_deductible",
            "libelle": "CSG/CRDS non déductible",
            "lignes": [
                {
                    "libelle": "CSG/CRDS non déductible à l'IR",
                    "base": 1457.66,
                    "taux_salarial": 0.029,
                    "montant_salarial": 42.27,
                    "taux_patronal": None,
                    "montant_patronal": 0.0,
                }
            ],
            "total_salarial": 42.27,
            "total_patronal": 0.0,
        },
    ]
    bulletin["synthese_net"] = {"net_imposable": 1128.07}
    return bulletin


def _libelles(lignes, type_ligne=None):
    return [
        ligne["libelle"]
        for ligne in lignes
        if type_ligne is None or ligne["type"] == type_ligne
    ]


class TestCorps:
    def test_ordre_general_du_corps(self):
        lignes = construire_vue_bulletin(bulletin_avec_cotisations())["lignes"]
        libelles = _libelles(lignes)
        assert libelles.index("SALAIRE DE BASE") < libelles.index("SALAIRE BRUT")
        assert libelles.index("SALAIRE BRUT") < libelles.index("SANTÉ")
        assert libelles.index("SANTÉ") < libelles.index("TOTAL DES RETENUES")
        assert libelles.index("TOTAL DES RETENUES") < libelles.index("NET IMPOSABLE")

    def test_codes_cegid_sur_les_rubriques(self):
        lignes = construire_vue_bulletin(bulletin_avec_cotisations())["lignes"]
        rubriques = {
            ligne["libelle"]: ligne["code"]
            for ligne in lignes
            if ligne["type"] == "rubrique"
        }
        assert rubriques["SANTÉ"] == "Q100"
        assert rubriques["RETRAITE"] == "Q300"
        assert rubriques["CSG/CRDS NON DÉDUCTIBLE À L'IR"] == "Q801"

    def test_csg_non_deductible_apres_le_net_imposable(self):
        lignes = construire_vue_bulletin(bulletin_avec_cotisations())["lignes"]
        libelles = _libelles(lignes)
        assert libelles.index("NET IMPOSABLE") < libelles.index(
            "CSG/CRDS NON DÉDUCTIBLE À L'IR"
        )

    def test_total_des_retenues_exclut_la_csg_non_deductible(self):
        lignes = construire_vue_bulletin(bulletin_avec_cotisations())["lignes"]
        total = next(l for l in lignes if l["libelle"] == "TOTAL DES RETENUES")
        assert total["montant_salarial"] == pytest.approx(99.10)
        assert total["montant_patronal"] == pytest.approx(223.33)

    def test_prevoyance_sans_code_cegid(self):
        bulletin = bulletin_avec_cotisations()
        bulletin["cotisations_officielles"].append(
            {
                "code": "cotisations_statutaires",
                "libelle": "Cotisations statutaires et conventionnelles",
                "lignes": [
                    {
                        "libelle": "PRÉVOYANCE",
                        "base": 1436.21,
                        "taux_salarial": 0.0118,
                        "montant_salarial": 16.95,
                        "taux_patronal": 0.0118,
                        "montant_patronal": 16.95,
                    }
                ],
                "total_salarial": 16.95,
                "total_patronal": 16.95,
            }
        )
        lignes = construire_vue_bulletin(bulletin)["lignes"]
        rubrique = next(
            l for l in lignes if l["libelle"].startswith("COTISATIONS STATUTAIRES")
        )
        assert rubrique["code"] is None

    def test_notes_de_frais_agregees_en_une_ligne(self):
        bulletin = bulletin_avec_cotisations()
        bulletin["notes_de_frais"] = [
            {"libelle": "Péage", "montant": 12.40},
            {"libelle": "Repas", "montant": 18.00},
        ]
        lignes = construire_vue_bulletin(bulletin)["lignes"]
        frais = [l for l in lignes if "frais professionnels" in l["libelle"].lower()]
        assert len(frais) == 1
        assert frais[0]["montant_salarial"] == pytest.approx(30.40)
        assert "Péage" not in _libelles(lignes)

    def test_primes_non_soumises_apres_le_net_imposable(self):
        bulletin = bulletin_avec_cotisations()
        bulletin["primes_non_soumises"] = [
            {"libelle": "INDEMNITÉ DE PANIER", "montant": 20.0}
        ]
        libelles = _libelles(construire_vue_bulletin(bulletin)["lignes"])
        assert libelles.index("NET IMPOSABLE") < libelles.index("INDEMNITÉ DE PANIER")

    def test_retenues_sur_le_net_reprises_en_lignes(self):
        bulletin = bulletin_avec_cotisations()
        bulletin["remboursements_avances"] = {"total_rembourse": 150.0}
        bulletin["retenues_saisies"] = {"total_preleve": 40.0}
        bulletin["remboursements_prets"] = {"total_rembourse": 60.0}
        lignes = construire_vue_bulletin(bulletin)["lignes"]
        montants = {l["libelle"]: l["montant_salarial"] for l in lignes}
        assert montants["Acomptes et avances"] == pytest.approx(150.0)
        assert montants["Retenues sur salaire"] == pytest.approx(40.0)
        assert montants["Remboursement prêt employeur"] == pytest.approx(60.0)
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && python -m pytest tests/unit/payroll/test_bulletin_view.py::TestCorps -v`
Expected: FAIL, `KeyError: 'lignes'`.

- [ ] **Step 3 : Implémenter le corps**

Ajouter dans `bulletin_view.py`, sous les constantes de tête :

```python
# Codes de rubriques du bulletin Cegid. Vérifiés sur les bulletins de juin 2026
# des sept sociétés : ce sont les seuls utilisés, il n'existe pas de Q700.
# La prévoyance et la mutuelle n'ont pas de code chez Cegid (références de
# contrat internes à son paramétrage) : elles restent sans code chez nous.
CODES_CEGID: Dict[str, str] = {
    "sante": "Q100",
    "at_mp": "Q200",
    "retraite": "Q300",
    "famille": "Q400",
    "chomage": "Q500",
    "autres_contributions_employeur": "Q600",
    "csg_deductible": "Q800",
    "csg_non_deductible": "Q801",
    "exonerations": "Q802",
}

LIBELLES_CEGID: Dict[str, str] = {
    "sante": "SANTÉ",
    "at_mp": "AT-MP",
    "retraite": "RETRAITE",
    "famille": "FAMILLE",
    "chomage": "ASSURANCE CHÔMAGE",
    "autres_contributions_employeur": "AUTRES CONTRIB. DUES PAR EMPL.",
    "cotisations_statutaires": "COTISATIONS STATUTAIRES ET CONVENTIONNELLES",
    "csg_deductible": "CSG DÉDUCTIBLE À L'IR",
    "csg_non_deductible": "CSG/CRDS NON DÉDUCTIBLE À L'IR",
    "exonerations": "EXO., ÉCRÊT. ET ALLÈG. COTIS",
}

# La CSG/CRDS non déductible est imprimée après le net imposable et n'entre pas
# dans le total des retenues (vérifié sur CARTOL juin 2026).
RUBRIQUE_APRES_NET_IMPOSABLE = "csg_non_deductible"
```

Puis les constructeurs :

```python
def _ligne(
    type_ligne: str,
    libelle: str,
    *,
    code: Optional[str] = None,
    base: Optional[float] = None,
    taux: Optional[float] = None,
    montant_salarial: Optional[float] = None,
    montant_patronal: Optional[float] = None,
) -> Dict[str, Any]:
    return {
        "type": type_ligne,
        "code": code,
        "libelle": libelle,
        "base": base,
        "taux": taux,
        "montant_salarial": montant_salarial,
        "montant_patronal": montant_patronal,
    }


def _ligne_brut(source: Dict[str, Any]) -> Dict[str, Any]:
    """Une ligne de rémunération : le gain va au salarial, la perte le diminue."""
    gain = source.get("gain")
    perte = source.get("perte")
    montant = None
    if gain is not None:
        montant = float(gain)
    elif perte is not None:
        montant = -float(perte)
    return _ligne(
        "detail",
        source.get("libelle") or "",
        base=source.get("quantite"),
        taux=source.get("taux"),
        montant_salarial=montant,
    )


def _ligne_cotisation(source: Dict[str, Any]) -> Dict[str, Any]:
    taux = source.get("taux_salarial")
    if taux is None:
        taux = source.get("taux_patronal")
    return _ligne(
        "detail",
        source.get("libelle") or "",
        base=source.get("base"),
        taux=float(taux) * 100 if taux is not None else None,
        montant_salarial=source.get("montant_salarial"),
        montant_patronal=source.get("montant_patronal"),
    )


def _lignes_hors_brut(bulletin: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Ce qui s'ajoute ou se retient après le net imposable."""
    lignes: List[Dict[str, Any]] = []

    for prime in bulletin.get("primes_non_soumises") or []:
        if not isinstance(prime, dict):
            continue
        lignes.append(
            _ligne(
                "hors_brut",
                prime.get("libelle") or "Prime non soumise",
                montant_salarial=prime.get("montant"),
            )
        )

    # Volontairement agrégé : le détail des notes de frais reste dans l'appli.
    notes_de_frais = [
        note for note in bulletin.get("notes_de_frais") or [] if isinstance(note, dict)
    ]
    if notes_de_frais:
        total = round(sum(float(note.get("montant") or 0.0) for note in notes_de_frais), 2)
        lignes.append(
            _ligne(
                "hors_brut",
                "Remboursement de frais professionnels",
                montant_salarial=total,
            )
        )

    synthese = bulletin.get("synthese_net") or {}
    for cle, libelle in (
        ("remboursement_transport", "Indemnité de transport"),
        ("indemnite_transport_fixe", "Indemnité transport contractuelle"),
    ):
        montant = float(synthese.get(cle) or 0.0)
        if montant > 0:
            lignes.append(_ligne("hors_brut", libelle, montant_salarial=montant))

    retenues = (
        (bulletin.get("remboursements_avances") or {}).get("total_rembourse"),
        "Acomptes et avances",
    ), (
        (bulletin.get("retenues_saisies") or {}).get("total_preleve"),
        "Retenues sur salaire",
    ), (
        (bulletin.get("remboursements_prets") or {}).get("total_rembourse"),
        "Remboursement prêt employeur",
    )
    for montant, libelle in retenues:
        valeur = float(montant or 0.0)
        if valeur > 0:
            lignes.append(_ligne("hors_brut", libelle, montant_salarial=valeur))

    return lignes


def construire_lignes(bulletin: Dict[str, Any]) -> List[Dict[str, Any]]:
    lignes: List[Dict[str, Any]] = []

    for source in ("calcul_du_brut", "details_conges", "details_absences", "details_maintien"):
        for detail in bulletin.get(source) or []:
            if isinstance(detail, dict):
                lignes.append(_ligne_brut(detail))

    lignes.append(
        _ligne("total", "SALAIRE BRUT", montant_salarial=bulletin.get("salaire_brut"))
    )

    rubriques = [
        rubrique
        for rubrique in bulletin.get("cotisations_officielles") or []
        if isinstance(rubrique, dict)
    ]
    rubriques_principales = [
        r for r in rubriques if r.get("code") != RUBRIQUE_APRES_NET_IMPOSABLE
    ]
    rubriques_apres = [
        r for r in rubriques if r.get("code") == RUBRIQUE_APRES_NET_IMPOSABLE
    ]

    for rubrique in rubriques_principales:
        lignes.extend(_lignes_rubrique(rubrique))

    total_salarial = round(
        sum(float(r.get("total_salarial") or 0.0) for r in rubriques_principales), 2
    )
    total_patronal = round(
        sum(float(r.get("total_patronal") or 0.0) for r in rubriques_principales), 2
    )
    lignes.append(
        _ligne(
            "total",
            "TOTAL DES RETENUES",
            montant_salarial=total_salarial,
            montant_patronal=total_patronal,
        )
    )
    lignes.append(
        _ligne(
            "total",
            "NET IMPOSABLE",
            montant_salarial=(bulletin.get("synthese_net") or {}).get("net_imposable"),
        )
    )

    lignes.extend(_lignes_hors_brut(bulletin))
    for rubrique in rubriques_apres:
        lignes.extend(_lignes_rubrique(rubrique))

    return lignes


def _lignes_rubrique(rubrique: Dict[str, Any]) -> List[Dict[str, Any]]:
    code = rubrique.get("code") or ""
    entete = _ligne(
        "rubrique",
        LIBELLES_CEGID.get(code, (rubrique.get("libelle") or "").upper()),
        code=CODES_CEGID.get(code),
    )
    details = [
        _ligne_cotisation(ligne)
        for ligne in rubrique.get("lignes") or []
        if isinstance(ligne, dict)
    ]
    return [entete, *details]
```

Ajouter `"lignes": construire_lignes(bulletin),` au dictionnaire retourné par `construire_vue_bulletin`.

- [ ] **Step 4 : Lancer les tests**

Run: `cd backend && python -m pytest tests/unit/payroll/test_bulletin_view.py -v`
Expected: PASS, 29 tests.

- [ ] **Step 5 : Commit**

```bash
git add backend/app/modules/payroll/documents/bulletin_view.py \
        backend/tests/unit/payroll/test_bulletin_view.py
git commit -m "feat(paie): vue du bulletin — corps et codes de rubriques Cegid"
```

---

### Task 5 : Colonne latérale

L'encadré étroit de droite. C'est là que se fondent les cartes `#cumuls-annuels` du template actuel.

**Files:**
- Modify: `backend/app/modules/payroll/documents/bulletin_view.py`
- Test: `backend/tests/unit/payroll/test_bulletin_view.py`

**Interfaces:**
- Consumes: `bulletin["parametres"]` (Task 1), `bulletin["cumuls"]["cumuls"]`, `bulletin["pied_de_page"]`.
- Produces: clé `lateral` de la vue : `[{"titre": str, "valeurs": [{"libelle": str, "valeur": str}]}]`.

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à `backend/tests/unit/payroll/test_bulletin_view.py` :

```python
class TestColonneLaterale:
    def _vue(self):
        bulletin = bulletin_minimal()
        bulletin["cumuls"] = {
            "periode": {"annee_en_cours": 2026},
            "cumuls": {
                "brut_total": 4788.07,
                "net_imposable": 3621.64,
                "impot_preleve_a_la_source": 420.57,
                "heures_remunerees": 392.49,
                "heures_supplementaires_remunerees": 12.15,
            },
        }
        bulletin["pied_de_page"] = {
            "cout_total_employeur": 1649.98,
            "total_exonerations": 544.13,
        }
        return construire_vue_bulletin(bulletin)["lateral"]

    def _bloc(self, titre):
        return next(bloc for bloc in self._vue() if bloc["titre"] == titre)

    def test_smic_et_plafond_affiches(self):
        valeurs = {v["libelle"]: v["valeur"] for v in self._bloc("BARÈMES")["valeurs"]}
        assert valeurs["SMIC horaire"] == "12,31"
        assert valeurs["Plafond Sécu"] == "3 337,50"

    def test_bloc_heures(self):
        valeurs = {v["libelle"]: v["valeur"] for v in self._bloc("HEURES")["valeurs"]}
        assert valeurs["Cumul heures"] == "392,49"
        assert valeurs["Cumul h. sup"] == "12,15"

    def test_bloc_cumuls_et_cout_employeur(self):
        valeurs = {v["libelle"]: v["valeur"] for v in self._bloc("CUMULS")["valeurs"]}
        assert valeurs["Bruts"] == "4 788,07"
        assert valeurs["Allègement cotis. employeur"] == "544,13"
        assert valeurs["Total versé employeur"] == "1 649,98"

    def test_mode_de_paiement(self):
        valeurs = {v["libelle"]: v["valeur"] for v in self._bloc("PAIEMENT")["valeurs"]}
        assert valeurs["Mode"] == "par Virement"

    def test_blocs_vides_absents(self):
        titres = [bloc["titre"] for bloc in construire_vue_bulletin(bulletin_minimal())["lateral"]]
        assert "HEURES" not in titres
        assert "CUMULS" not in titres
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && python -m pytest tests/unit/payroll/test_bulletin_view.py::TestColonneLaterale -v`
Expected: FAIL, `KeyError: 'lateral'`.

- [ ] **Step 3 : Implémenter la colonne**

Ajouter dans `bulletin_view.py` :

```python
MODES_PAIEMENT = {
    "virement": "par Virement",
    "cheque": "par Chèque",
    "chèque": "par Chèque",
    "especes": "en Espèces",
    "espèces": "en Espèces",
}


def _montant_fr(valeur: Any) -> str:
    """Format français : espace fine insécable pour les milliers, virgule décimale."""
    nombre = float(valeur or 0.0)
    return f"{nombre:,.2f}".replace(",", " ").replace(".", ",")


def _bloc_lateral(titre: str, valeurs: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    valeurs_utiles = [valeur for valeur in valeurs if valeur["valeur"]]
    if not valeurs_utiles:
        return None
    return {"titre": titre, "valeurs": valeurs_utiles}


def construire_lateral(bulletin: Dict[str, Any]) -> List[Dict[str, Any]]:
    parametres = bulletin.get("parametres") or {}
    cumuls = ((bulletin.get("cumuls") or {}).get("cumuls")) or {}
    pied = bulletin.get("pied_de_page") or {}
    salarie = ((bulletin.get("en_tete") or {}).get("salarie")) or {}

    def valeur(libelle: str, montant: Any) -> Dict[str, str]:
        return {
            "libelle": libelle,
            "valeur": _montant_fr(montant) if montant else "",
        }

    blocs = [
        _bloc_lateral(
            "BARÈMES",
            [
                valeur("SMIC horaire", parametres.get("smic_horaire")),
                valeur("Plafond Sécu", parametres.get("pss_mensuel")),
            ],
        ),
        _bloc_lateral(
            "HEURES",
            [
                valeur("Cumul heures", cumuls.get("heures_remunerees")),
                valeur(
                    "Cumul h. sup", cumuls.get("heures_supplementaires_remunerees")
                ),
            ],
        ),
        _bloc_lateral(
            "CUMULS",
            [
                valeur("Bruts", cumuls.get("brut_total")),
                valeur("Net imposable", cumuls.get("net_imposable")),
                valeur("Allègement cotis. employeur", pied.get("total_exonerations")),
                valeur("Total versé employeur", pied.get("cout_total_employeur")),
            ],
        ),
        _bloc_lateral(
            "PAIEMENT",
            [
                {
                    "libelle": "Mode",
                    "valeur": MODES_PAIEMENT.get(
                        str(salarie.get("mode_paiement") or "").strip().lower(), ""
                    ),
                }
            ],
        ),
    ]
    return [bloc for bloc in blocs if bloc]
```

Ajouter `"lateral": construire_lateral(bulletin),` au dictionnaire retourné par `construire_vue_bulletin`.

- [ ] **Step 4 : Lancer les tests**

Run: `cd backend && python -m pytest tests/unit/payroll/test_bulletin_view.py -v`
Expected: PASS, 34 tests.

- [ ] **Step 5 : Commit**

```bash
git add backend/app/modules/payroll/documents/bulletin_view.py \
        backend/tests/unit/payroll/test_bulletin_view.py
git commit -m "feat(paie): vue du bulletin — colonne latérale"
```

---

### Task 6 : Pied du bulletin et mention légale manquante

Le bas du gabarit, et l'ajout de la mention obligatoire de l'article R3243-1 que notre bulletin n'a jamais portée.

**Files:**
- Modify: `backend/app/modules/payroll/documents/bulletin_view.py`
- Test: `backend/tests/unit/payroll/test_bulletin_view.py`

**Interfaces:**
- Consumes: `bulletin["synthese_net"]`, `bulletin["cumuls"]`, `bulletin["net_a_payer"]`, `bulletin["pied_de_page"]["mentions_legales"]`.
- Produces: clé `pied` de la vue ; fonction publique `calculer_evolution_remuneration(salaire_brut: float, base_csg: float) -> float`.

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à `backend/tests/unit/payroll/test_bulletin_view.py` :

```python
from app.modules.payroll.documents.bulletin_view import calculer_evolution_remuneration


class TestEvolutionRemuneration:
    """Mention obligatoire art. R3243-1, absente de notre bulletin jusqu'ici."""

    def test_valeur_du_bulletin_cartol_alves_juin_2026(self):
        # 1436,21 x 3,15 % - 1457,66 x 1,7 % = 45,24 - 24,78 = 20,46
        assert calculer_evolution_remuneration(1436.21, 1457.66) == pytest.approx(20.46)

    def test_jamais_negative(self):
        assert calculer_evolution_remuneration(100.0, 10000.0) == 0.0

    def test_sans_base_csg_repli_sur_le_brut(self):
        assert calculer_evolution_remuneration(1000.0, 0.0) == pytest.approx(14.5)


class TestPied:
    def _bulletin(self):
        bulletin = bulletin_avec_cotisations()
        bulletin["synthese_net"] = {
            "net_imposable": 1128.07,
            "montant_net_social": 1105.80,
            "net_social_avant_impot": 1105.80,
            "impot_prelevement_a_la_source": {
                "base": 1128.07,
                "taux": 17.30,
                "montant": 195.16,
            },
        }
        bulletin["cumuls"] = {
            "periode": {"annee_en_cours": 2026},
            "cumuls": {
                "net_imposable": 3621.64,
                "impot_preleve_a_la_source": 420.57,
            },
        }
        bulletin["net_a_payer"] = 910.64
        bulletin["pied_de_page"]["mentions_legales"] = {
            "conservation": "Conservez ce bulletin sans limitation de durée.",
            "information": "Pour en savoir plus : www.service-public.fr",
        }
        return bulletin

    def test_nets_et_net_a_payer(self):
        pied = construire_vue_bulletin(self._bulletin())["pied"]
        assert pied["montant_net_social"] == pytest.approx(1105.80)
        assert pied["net_avant_impot"] == pytest.approx(1105.80)
        assert pied["net_a_payer"] == pytest.approx(910.64)

    def test_mention_evolution_remuneration_presente(self):
        pied = construire_vue_bulletin(self._bulletin())["pied"]
        assert pied["evolution_remuneration"] == pytest.approx(20.46)

    def test_tableau_impot_avec_cumuls(self):
        impot = construire_vue_bulletin(self._bulletin())["pied"]["impot"]
        assert impot["taux"] == pytest.approx(17.30)
        assert impot["montant"] == pytest.approx(195.16)
        assert impot["cumul_net_imposable"] == pytest.approx(3621.64)
        assert impot["cumul_impot"] == pytest.approx(420.57)

    def test_mentions_legales_et_convention(self):
        pied = construire_vue_bulletin(self._bulletin())["pied"]
        assert any("service-public.fr" in m for m in pied["mentions_legales"])
        assert "métallurgie" in pied["convention_collective"]

    def test_rectification_signalee_discretement(self):
        bulletin = self._bulletin()
        bulletin["manually_edited"] = True
        bulletin["edited_at"] = "02/08/2026 à 14:30"
        pied = construire_vue_bulletin(bulletin)["pied"]
        assert pied["rectification"] == "Bulletin rectifié le 02/08/2026 à 14:30"

    def test_sans_rectification_pas_de_mention(self):
        assert construire_vue_bulletin(self._bulletin())["pied"]["rectification"] == ""
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && python -m pytest tests/unit/payroll/test_bulletin_view.py::TestPied tests/unit/payroll/test_bulletin_view.py::TestEvolutionRemuneration -v`
Expected: FAIL, `ImportError: cannot import name 'calculer_evolution_remuneration'`.

- [ ] **Step 3 : Implémenter le pied**

Ajouter dans `bulletin_view.py` :

```python
# Cotisations salariales supprimées en 2018 (maladie 0,75 % + chômage 2,40 %)
# et hausse de CSG qui les a compensées (1,7 %). Formule retrouvée sur le
# bulletin CARTOL de juin 2026, exacte au centime.
TAUX_COTISATIONS_SUPPRIMEES = 0.0315
TAUX_HAUSSE_CSG = 0.017

MENTION_EVOLUTION_REMUNERATION = (
    "dont évolution de la rémunération liée à la suppression des cotisations "
    "salariales chômage et maladie"
)


def calculer_evolution_remuneration(salaire_brut: float, base_csg: float) -> float:
    """Mention obligatoire de l'article R3243-1 du Code du travail."""
    brut = float(salaire_brut or 0.0)
    base = float(base_csg or 0.0) or brut
    montant = brut * TAUX_COTISATIONS_SUPPRIMEES - base * TAUX_HAUSSE_CSG
    return round(max(0.0, montant), 2)


def _base_csg(bulletin: Dict[str, Any]) -> float:
    """Base de la CSG, prise sur la première ligne de la rubrique dédiée."""
    for rubrique in bulletin.get("cotisations_officielles") or []:
        if not isinstance(rubrique, dict):
            continue
        if rubrique.get("code") not in {"csg_deductible", "csg_non_deductible"}:
            continue
        for ligne in rubrique.get("lignes") or []:
            if isinstance(ligne, dict) and ligne.get("base"):
                return float(ligne["base"])
    return 0.0


def construire_pied(bulletin: Dict[str, Any]) -> Dict[str, Any]:
    synthese = bulletin.get("synthese_net") or {}
    pas = synthese.get("impot_prelevement_a_la_source") or {}
    cumuls = ((bulletin.get("cumuls") or {}).get("cumuls")) or {}
    salarie = ((bulletin.get("en_tete") or {}).get("salarie")) or {}
    mentions = ((bulletin.get("pied_de_page") or {}).get("mentions_legales")) or {}

    rectification = ""
    if bulletin.get("manually_edited"):
        edite_le = bulletin.get("edited_at")
        rectification = (
            f"Bulletin rectifié le {edite_le}" if edite_le else "Bulletin rectifié"
        )

    return {
        "montant_net_social": synthese.get("montant_net_social"),
        "net_avant_impot": synthese.get("net_social_avant_impot"),
        "evolution_remuneration": calculer_evolution_remuneration(
            float(bulletin.get("salaire_brut") or 0.0), _base_csg(bulletin)
        ),
        "mention_evolution": MENTION_EVOLUTION_REMUNERATION,
        "impot": {
            "net_imposable": synthese.get("net_imposable"),
            "base": pas.get("base"),
            "taux": pas.get("taux"),
            "montant": pas.get("montant"),
            "cumul_net_imposable": cumuls.get("net_imposable"),
            "cumul_impot": cumuls.get("impot_preleve_a_la_source"),
            "exoneration_apprenti": bool(synthese.get("exoneration_ir_apprenti")),
        },
        "net_a_payer": bulletin.get("net_a_payer"),
        "convention_collective": salarie.get("convention_collective") or "",
        "mentions_legales": [
            texte
            for texte in (
                mentions.get("conservation"),
                mentions.get("information"),
            )
            if texte
        ],
        "note": bulletin.get("pdf_notes") or "",
        "rectification": rectification,
    }
```

Ajouter `"pied": construire_pied(bulletin),` au dictionnaire retourné par `construire_vue_bulletin`.

- [ ] **Step 4 : Lancer les tests**

Run: `cd backend && python -m pytest tests/unit/payroll/test_bulletin_view.py -v`
Expected: PASS, 43 tests.

- [ ] **Step 5 : Commit**

```bash
git add backend/app/modules/payroll/documents/bulletin_view.py \
        backend/tests/unit/payroll/test_bulletin_view.py
git commit -m "feat(paie): vue du bulletin — pied et mention art. R3243-1"
```

---

### Task 7 : Réécrire le template et brancher les générateurs

Le template devient bête. Les quatre appelants passent par la vue.

**Files:**
- Modify: `backend/app/runtime/payroll/templates/template_bulletin.html` (réécriture complète)
- Modify: `backend/app/modules/payroll/documents/payslip_run_heures.py:891-902`
- Modify: `backend/app/modules/payroll/documents/payslip_run_forfait.py:573-580`
- Modify: `backend/app/modules/payroll/documents/payslip_editor.py:50-92`
- Modify: `backend/app/modules/payroll/documents/simulated_payslip_generator.py:110-120`
- Modify: `backend/tests/unit/payroll/test_bulletin_officiel.py` (assertions de rendu)

**Interfaces:**
- Consumes: `construire_vue_bulletin(bulletin) -> dict` avec les clés `bandeau`, `compteurs`, `salarie`, `identite`, `lignes`, `lateral`, `pied`.
- Produces: le template attend une variable racine `vue`. Tout appelant doit rendre avec `template.render(vue=construire_vue_bulletin(bulletin))`.

- [ ] **Step 1 : Écrire le test de rendu qui échoue**

Ajouter à `backend/tests/unit/payroll/test_bulletin_view.py` :

```python
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def _rendre(bulletin: dict) -> str:
    template_dir = (
        Path(__file__).resolve().parents[3]
        / "app"
        / "runtime"
        / "payroll"
        / "templates"
    )
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    return env.get_template("template_bulletin.html").render(
        vue=construire_vue_bulletin(bulletin)
    )


class TestRendu:
    def test_le_gabarit_affiche_les_zones_attendues(self):
        html = _rendre(bulletin_avec_cotisations())
        for attendu in (
            "BULLETIN DE SALAIRE",
            "Société CARTOL",
            "ALVES Lucas",
            "Matricule",
            "1 02 09 85 191 239 74",
            "Q100",
            "SANTÉ",
            "TOTAL DES RETENUES",
            "NET IMPOSABLE",
            "Net à payer au salarié",
        ):
            assert attendu in html, f"{attendu} absent du rendu"

    def test_ordre_des_zones(self):
        html = _rendre(bulletin_avec_cotisations())
        assert html.index("BULLETIN DE SALAIRE") < html.index("Matricule")
        assert html.index("Matricule") < html.index("TOTAL DES RETENUES")
        assert html.index("TOTAL DES RETENUES") < html.index("Net à payer au salarié")

    def test_aucune_section_vide_sans_donnees(self):
        html = _rendre(bulletin_minimal())
        assert "CUMULS" not in html
        assert "Solde de congés" not in html
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

Run: `cd backend && python -m pytest tests/unit/payroll/test_bulletin_view.py::TestRendu -v`
Expected: FAIL — le template actuel ignore `vue` et rend un document vide de ces marqueurs.

- [ ] **Step 3 : Réécrire le template**

Remplacer intégralement `backend/app/runtime/payroll/templates/template_bulletin.html` :

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Bulletin de paie</title>
    <style>
        @page { size: A4 portrait; margin: 10mm 8mm; }
        * { box-sizing: border-box; }
        body { font-family: Arial, Helvetica, sans-serif; font-size: 7.5pt; color: #000; line-height: 1.25; }
        table { width: 100%; border-collapse: collapse; }
        .num { text-align: right; white-space: nowrap; }

        /* Bandeau */
        .bandeau { width: 100%; margin-bottom: 4mm; }
        .bandeau td { vertical-align: top; }
        .bandeau .titre { text-align: right; font-weight: bold; font-size: 10pt; }
        .bandeau .periode { text-align: right; }

        /* Identité */
        .identite { margin-bottom: 3mm; }
        .identite td { vertical-align: top; padding: 0; }
        .nom { font-weight: bold; font-size: 9pt; }
        .compteurs { border-collapse: collapse; font-size: 6.5pt; }
        .compteurs th, .compteurs td { border: 1px solid #000; padding: 1px 4px; text-align: right; }
        .compteurs th:first-child, .compteurs td:first-child { text-align: left; }
        .notes-compteurs { font-size: 6pt; margin-top: 1mm; }
        .contrat td { padding: 0 6px 0 0; }

        /* Corps + colonne latérale */
        .corps { width: 100%; }
        .corps > tbody > tr > td { vertical-align: top; padding: 0; }
        .colonne-lateral { width: 26mm; padding-left: 3mm !important; }

        .rubriques { border-top: 1px solid #000; border-bottom: 1px solid #000; }
        .rubriques th { border-bottom: 1px solid #000; padding: 1px 3px; font-size: 6.5pt; text-align: right; }
        .rubriques th:first-child { text-align: left; }
        .rubriques td { padding: 0.6px 3px; }
        .rubriques tr.rubrique td { font-weight: bold; padding-top: 1.5mm; }
        .rubriques tr.total td { font-weight: bold; border-top: 1px solid #000; }
        .rubriques tr.detail td:first-child { padding-left: 4mm; }

        .bloc-lateral { border: 1px solid #000; margin-bottom: 2mm; padding: 1mm; }
        .bloc-lateral .titre { font-weight: bold; font-size: 6pt; text-align: center; border-bottom: 1px solid #000; margin-bottom: 1mm; }
        .bloc-lateral .valeur { font-size: 6pt; }
        .bloc-lateral .valeur .montant { display: block; text-align: right; font-weight: bold; font-size: 7pt; }

        /* Pied */
        .nets { margin-top: 3mm; border-top: 1px solid #000; }
        .nets td { padding: 1px 3px; font-weight: bold; }
        .mention-evolution { font-size: 6pt; font-weight: normal; }
        .impot { margin-top: 2mm; }
        .impot th, .impot td { padding: 1px 3px; text-align: right; border-bottom: 1px solid #ddd; }
        .impot th:first-child, .impot td:first-child { text-align: left; }
        .net-a-payer { margin-top: 3mm; text-align: right; }
        .net-a-payer .libelle { font-size: 7pt; }
        .net-a-payer .montant { font-size: 13pt; font-weight: bold; }
        .mentions { margin-top: 3mm; font-size: 6pt; text-align: center; }

        thead { display: table-header-group; }
        .identite, .bloc-lateral, .net-a-payer { page-break-inside: avoid; }
    </style>
</head>
<body>
    <table class="bandeau">
        <tr>
            <td>
                <div class="nom">{{ vue.bandeau.raison_sociale }}</div>
                {% for ligne in vue.bandeau.adresse %}<div>{{ ligne }}</div>{% endfor %}
                <div>Siret : {{ vue.bandeau.siret }}{% if vue.bandeau.naf_ape %} &nbsp; Code NAF : {{ vue.bandeau.naf_ape }}{% endif %}</div>
            </td>
            <td>
                <div class="titre">BULLETIN DE SALAIRE</div>
                <div class="periode">Période : {{ vue.bandeau.periode }}</div>
                {% if vue.bandeau.date_paiement %}<div class="periode">Paiement le : {{ vue.bandeau.date_paiement }}</div>{% endif %}
                {% if vue.bandeau.du %}<div class="periode">Du : {{ vue.bandeau.du }} &nbsp; Au : {{ vue.bandeau.au }}</div>{% endif %}
            </td>
        </tr>
    </table>

    <table class="identite">
        <tr>
            <td>
                {% if vue.compteurs %}
                <table class="compteurs">
                    <tr>
                        <th></th>
                        {% for colonne in vue.compteurs.colonnes %}<th>{{ colonne.titre }}</th>{% endfor %}
                    </tr>
                    <tr>
                        <td>Acquis</td>
                        {% for colonne in vue.compteurs.colonnes %}<td>{{ "%.2f"|format(colonne.acquis) }}</td>{% endfor %}
                    </tr>
                    <tr>
                        <td>Total pris</td>
                        {% for colonne in vue.compteurs.colonnes %}<td>{{ "%.2f"|format(colonne.pris) }}</td>{% endfor %}
                    </tr>
                    <tr>
                        <td>Solde</td>
                        {% for colonne in vue.compteurs.colonnes %}<td>{{ "%.2f"|format(colonne.solde) }}</td>{% endfor %}
                    </tr>
                </table>
                {% for note in vue.compteurs.notes %}<div class="notes-compteurs">{{ note }}</div>{% endfor %}
                {% endif %}
            </td>
            <td>
                <div class="nom">{% if vue.salarie.civilite %}{{ vue.salarie.civilite }} {% endif %}{{ vue.salarie.nom_ligne }}</div>
                {% for ligne in vue.salarie.adresse %}<div>{{ ligne }}</div>{% endfor %}
            </td>
        </tr>
    </table>

    <table class="contrat">
        <tr>
            <td>Matricule : {{ vue.identite.matricule }}</td>
            <td>NoSécu. : {{ vue.identite.nir }}</td>
        </tr>
        <tr>
            <td>Entré(e) le : {{ vue.identite.date_entree }}</td>
            <td>Ancienneté : {{ vue.identite.anciennete }}</td>
        </tr>
        <tr>
            <td colspan="2">Emploi : {{ vue.identite.emploi }}</td>
        </tr>
        <tr>
            <td>Qualif : {{ vue.identite.qualification }}</td>
            <td>Classif : {{ vue.identite.classification }} &nbsp; Coeff : {{ vue.identite.coefficient }}</td>
        </tr>
    </table>

    <table class="corps">
        <tr>
            <td>
                <table class="rubriques">
                    <thead>
                        <tr>
                            <th>Rubriques</th>
                            <th>Base</th>
                            <th>Taux salarial</th>
                            <th>Montant salarial</th>
                            <th>Mt patronal</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for ligne in vue.lignes %}
                        <tr class="{{ ligne.type }}">
                            <td>{% if ligne.code %}{{ ligne.code }} {% endif %}{{ ligne.libelle }}</td>
                            <td class="num">{% if ligne.base is not none %}{{ "%.2f"|format(ligne.base) }}{% endif %}</td>
                            <td class="num">{% if ligne.taux is not none %}{{ "%.4f"|format(ligne.taux) }}{% endif %}</td>
                            <td class="num">{% if ligne.montant_salarial is not none %}{{ "%.2f"|format(ligne.montant_salarial) }}{% endif %}</td>
                            <td class="num">{% if ligne.montant_patronal is not none %}{{ "%.2f"|format(ligne.montant_patronal) }}{% endif %}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </td>
            <td class="colonne-lateral">
                {% for bloc in vue.lateral %}
                <div class="bloc-lateral">
                    <div class="titre">{{ bloc.titre }}</div>
                    {% for valeur in bloc.valeurs %}
                    <div class="valeur">{{ valeur.libelle }}<span class="montant">{{ valeur.valeur }}</span></div>
                    {% endfor %}
                </div>
                {% endfor %}
            </td>
        </tr>
    </table>

    <table class="nets">
        {% if vue.pied.montant_net_social is not none %}
        <tr>
            <td>MONTANT NET SOCIAL</td>
            <td class="num">{{ "%.2f"|format(vue.pied.montant_net_social) }}</td>
        </tr>
        {% endif %}
        {% if vue.pied.net_avant_impot is not none %}
        <tr>
            <td>NET À PAYER AVANT IMPÔT SUR LE REVENU</td>
            <td class="num">{{ "%.2f"|format(vue.pied.net_avant_impot) }}</td>
        </tr>
        {% endif %}
        {% if vue.pied.evolution_remuneration %}
        <tr>
            <td class="mention-evolution">{{ vue.pied.mention_evolution }}</td>
            <td class="num mention-evolution">{{ "%.2f"|format(vue.pied.evolution_remuneration) }}</td>
        </tr>
        {% endif %}
    </table>

    <table class="impot">
        <thead>
            <tr>
                <th>Impôt sur le revenu</th>
                <th>Base</th>
                <th>Taux</th>
                <th>Montant</th>
                <th>Cumul annuel</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Montant net imposable</td>
                <td></td>
                <td></td>
                <td>{% if vue.pied.impot.net_imposable is not none %}{{ "%.2f"|format(vue.pied.impot.net_imposable) }}{% endif %}</td>
                <td>{% if vue.pied.impot.cumul_net_imposable %}{{ "%.2f"|format(vue.pied.impot.cumul_net_imposable) }}{% endif %}</td>
            </tr>
            <tr>
                <td>Impôt sur le revenu prélevé à la source</td>
                <td>{% if vue.pied.impot.base is not none %}{{ "%.2f"|format(vue.pied.impot.base) }}{% endif %}</td>
                <td>{% if vue.pied.impot.taux is not none %}{{ "%.2f"|format(vue.pied.impot.taux) }}{% endif %}</td>
                <td>{% if vue.pied.impot.montant is not none %}{{ "%.2f"|format(vue.pied.impot.montant) }}{% endif %}</td>
                <td>{% if vue.pied.impot.cumul_impot %}{{ "%.2f"|format(vue.pied.impot.cumul_impot) }}{% endif %}</td>
            </tr>
            {% if vue.pied.impot.exoneration_apprenti %}
            <tr>
                <td colspan="5">Apprenti : rémunération exonérée d'impôt sur le revenu dans la limite du SMIC annuel.</td>
            </tr>
            {% endif %}
        </tbody>
    </table>

    <div class="net-a-payer">
        <div class="libelle">Net à payer au salarié (en euros)</div>
        <div class="montant">{% if vue.pied.net_a_payer is not none %}{{ "%.2f"|format(vue.pied.net_a_payer) }}{% endif %}</div>
    </div>

    <div class="mentions">
        {% if vue.pied.convention_collective %}<div>{{ vue.pied.convention_collective }}</div>{% endif %}
        {% if vue.pied.note %}<div>{{ vue.pied.note }}</div>{% endif %}
        {% if vue.pied.rectification %}<div>{{ vue.pied.rectification }}</div>{% endif %}
        {% for mention in vue.pied.mentions_legales %}<div>{{ mention }}</div>{% endfor %}
    </div>
</body>
</html>
```

- [ ] **Step 4 : Brancher les quatre appelants**

Dans `backend/app/modules/payroll/documents/payslip_run_heures.py`, remplacer :

```python
    template = env.get_template("template_bulletin.html")
    html_genere = template.render(bulletin_final)
```

par :

```python
    from app.modules.payroll.documents.bulletin_view import construire_vue_bulletin

    template = env.get_template("template_bulletin.html")
    html_genere = template.render(vue=construire_vue_bulletin(bulletin_final))
```

Faire le même remplacement dans `payslip_run_forfait.py` (ligne ~575).

Dans `simulated_payslip_generator.py`, méthode `generate_html`, remplacer :

```python
        template_data = self.prepare_simulation_data_for_template(simulation_data)
        template_data_objects = DictToObject(template_data)
        template = self.env.get_template("template_bulletin.html")
        html_content = template.render(template_data_objects.__dict__)
```

par :

```python
        from app.modules.payroll.documents.bulletin_view import construire_vue_bulletin

        template_data = self.prepare_simulation_data_for_template(simulation_data)
        template = self.env.get_template("template_bulletin.html")
        html_content = template.render(vue=construire_vue_bulletin(template_data))
```

Le passage par `DictToObject` n'a plus lieu d'être : la vue consomme un dictionnaire. Si `DictToObject` n'est plus utilisé ailleurs dans le fichier, retirer sa définition et son import.

Dans `payslip_editor.py`, remplacer `html_content = template.render(**template_data)` par :

```python
        from app.modules.payroll.documents.bulletin_view import construire_vue_bulletin

        html_content = template.render(vue=construire_vue_bulletin(template_data))
```

`template_data` porte déjà `pdf_notes`, `manually_edited`, `edited_at` et `cumuls` : la vue les consomme (`construire_pied` lit `manually_edited`, `edited_at`, `pdf_notes` ; `construire_lateral` lit `cumuls`).

- [ ] **Step 5 : Mettre à jour les assertions de rendu existantes**

Dans `backend/tests/unit/payroll/test_bulletin_officiel.py`, deux tests rendent le template et vérifient l'ancienne mise en page : `test_rendu_template_contient_solde_conges_en_bas` et `test_rendu_template_contient_montant_net_social`. Le contenu reste présent, sa forme change. Remplacer dans les deux le rendu :

```python
        html = env.get_template("template_bulletin.html").render(bulletin)
```

par :

```python
        from app.modules.payroll.documents.bulletin_view import construire_vue_bulletin

        html = env.get_template("template_bulletin.html").render(
            vue=construire_vue_bulletin(bulletin)
        )
```

Puis adapter les assertions :

- dans `test_rendu_template_contient_solde_conges_en_bas`, remplacer les assertions `"Solde de congés au 30/04/2026"`, `"11.00 j"` et `"CP période en cours"` par `assert "Acquis" in html` et `assert "CP N" in html`, et remplacer la comparaison d'index `idx_solde < idx_mentions` par `assert html.index("Acquis") < html.index("service-public.fr")` — les compteurs sont désormais en haut, avant les mentions. Renommer le test en `test_rendu_template_contient_les_compteurs_de_conges` ;
- dans `test_rendu_template_contient_montant_net_social`, remplacer `assert "Montant net social" in html or "MONTANT NET SOCIAL" in html` par `assert "MONTANT NET SOCIAL" in html`, et la boucle sur `RUBRIQUES_ORDRE[:3]` par une vérification des codes : `assert "Q100" in html`.

- [ ] **Step 6 : Lancer les tests**

Run: `cd backend && python -m pytest tests/unit/payroll/ -v`
Expected: PASS.

- [ ] **Step 7 : Vérifier le rendu PDF réel**

Générer un PDF depuis un bulletin de test et l'ouvrir, pour contrôler qu'il tient sur une page et que rien ne déborde :

```bash
cd backend && python - <<'PY'
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import sys
sys.path.insert(0, ".")
from tests.unit.payroll.test_bulletin_view import bulletin_avec_cotisations
from app.modules.payroll.documents.bulletin_view import construire_vue_bulletin

env = Environment(loader=FileSystemLoader("app/runtime/payroll/templates"))
html = env.get_template("template_bulletin.html").render(
    vue=construire_vue_bulletin(bulletin_avec_cotisations())
)
HTML(string=html).write_pdf("/tmp/bulletin_cegid.pdf")
print("écrit dans /tmp/bulletin_cegid.pdf")
PY
pdftotext -layout /tmp/bulletin_cegid.pdf - | head -40
```

Expected: une page, bandeau en haut, colonne latérale à droite, net à payer en bas à droite. Comparer visuellement avec `data/cartol/bulletins/2026-06/06-2026-cartol-bulletin-de-salaire.pdf`.

- [ ] **Step 8 : Commit**

```bash
git add backend/app/runtime/payroll/templates/template_bulletin.html \
        backend/app/modules/payroll/documents/payslip_run_heures.py \
        backend/app/modules/payroll/documents/payslip_run_forfait.py \
        backend/app/modules/payroll/documents/payslip_editor.py \
        backend/app/modules/payroll/documents/simulated_payslip_generator.py \
        backend/tests/unit/payroll/test_bulletin_view.py \
        backend/tests/unit/payroll/test_bulletin_officiel.py
git commit -m "feat(paie): bulletin PDF au gabarit Cegid"
```

---

### Task 8 : Endpoint d'aperçu

**Files:**
- Modify: `backend/app/modules/payslips/schemas/requests.py`
- Modify: `backend/app/modules/payslips/schemas/responses.py`
- Modify: `backend/app/modules/payslips/schemas/__init__.py`
- Modify: `backend/app/modules/payslips/api/router.py`
- Test: `backend/tests/integration/payslips/test_api.py`

**Interfaces:**
- Consumes: `construire_vue_bulletin` (Task 2-6), le template (Task 7), `_require_payslip_scope(current_user, payslip_id, permission_code) -> dict`.
- Produces: `POST /api/payslips/{payslip_id}/preview`, corps `{"payslip_data": dict, "pdf_notes": str | None}`, réponse `{"html": str}`.

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter à `backend/tests/integration/payslips/test_api.py` :

```python
class TestPayslipPreview:
    """POST /api/payslips/{payslip_id}/preview — rendu serveur de l'aperçu."""

    def test_apercu_rend_le_gabarit(self, client):
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.payslips.api.router.get_payslip_meta_for_access",
                return_value={
                    "company_id": TEST_COMPANY_ID,
                    "employee_id": TEST_EMPLOYEE_ID,
                },
            ), patch(
                "app.modules.payslips.api.router.access_control_service.require_employee_access",
                return_value=None,
            ):
                response = client.post(
                    "/api/payslips/ps-1/preview",
                    json={
                        "payslip_data": {
                            "en_tete": {
                                "periode": "Juin 2026",
                                "annee": 2026,
                                "mois": 6,
                                "entreprise": {"raison_sociale": "Société CARTOL"},
                                "salarie": {"nom": "ALVES", "prenom": "Lucas"},
                            },
                            "salaire_brut": 1436.21,
                            "net_a_payer": 910.64,
                        },
                        "pdf_notes": None,
                    },
                )
            assert response.status_code == 200
            html = response.json()["html"]
            assert "BULLETIN DE SALAIRE" in html
            assert "ALVES Lucas" in html
        finally:
            app.dependency_overrides.clear()

    def test_apercu_refuse_un_bulletin_hors_perimetre(self, client):
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.payslips.api.router.get_payslip_meta_for_access",
                return_value={
                    "company_id": "autre-societe",
                    "employee_id": TEST_EMPLOYEE_ID,
                },
            ):
                response = client.post(
                    "/api/payslips/ps-1/preview",
                    json={"payslip_data": {}, "pdf_notes": None},
                )
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()
```

Si la fixture `client` n'existe pas dans ce fichier, la créer en tête du fichier :

```python
@pytest.fixture
def client():
    return TestClient(app)
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

Run: `cd backend && python -m pytest tests/integration/payslips/test_api.py::TestPayslipPreview -v`
Expected: FAIL avec 404 sur la première assertion (la route n'existe pas).

- [ ] **Step 3 : Ajouter les schémas**

Dans `backend/app/modules/payslips/schemas/requests.py` :

```python
class PayslipPreviewRequest(BaseModel):
    """Rendu d'aperçu d'un bulletin à partir de données éditées, sans persistance."""

    payslip_data: dict[str, Any]
    pdf_notes: str | None = Field(
        None, max_length=2000, description="Notes visibles sur le bulletin"
    )
```

Dans `backend/app/modules/payslips/schemas/responses.py` :

```python
class PayslipPreviewResponse(BaseModel):
    """Bulletin rendu, prêt à être affiché tel quel."""

    html: str
```

Exporter les deux depuis `backend/app/modules/payslips/schemas/__init__.py`, dans les blocs d'import existants.

- [ ] **Step 4 : Ajouter la route**

Dans `backend/app/modules/payslips/api/router.py`, après `edit_payslip_route`, ajouter :

```python
@router.post(
    "/api/payslips/{payslip_id}/preview", response_model=PayslipPreviewResponse
)
def preview_payslip_route(
    payslip_id: str,
    preview_request: PayslipPreviewRequest,
    current_user: User = Depends(get_current_user),
):
    """Rend le bulletin tel qu'il sortira, sans rien enregistrer."""
    try:
        _require_payslip_scope(current_user, payslip_id, "payslips.edit")

        from jinja2 import Environment, FileSystemLoader

        from app.core.paths import payroll_engine_templates
        from app.modules.payroll.documents.bulletin_view import construire_vue_bulletin

        donnees = dict(preview_request.payslip_data or {})
        donnees["pdf_notes"] = preview_request.pdf_notes

        env = Environment(loader=FileSystemLoader(str(payroll_engine_templates())))
        template = env.get_template("template_bulletin.html")
        return PayslipPreviewResponse(
            html=template.render(vue=construire_vue_bulletin(donnees))
        )
    except _PAYSLIP_APP_ERRORS as e:
        _map_app_errors(e)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
```

Ajouter `PayslipPreviewRequest` et `PayslipPreviewResponse` aux imports de schémas en tête du routeur.

- [ ] **Step 5 : Lancer les tests**

Run: `cd backend && python -m pytest tests/integration/payslips/test_api.py -v`
Expected: PASS (les échecs pré-existants d'autres modules ne concernent pas ce fichier).

- [ ] **Step 6 : Commit**

```bash
git add backend/app/modules/payslips/api/router.py \
        backend/app/modules/payslips/schemas/requests.py \
        backend/app/modules/payslips/schemas/responses.py \
        backend/app/modules/payslips/schemas/__init__.py \
        backend/tests/integration/payslips/test_api.py
git commit -m "feat(paie): endpoint d'aperçu du bulletin"
```

---

### Task 9 : Aperçu RH sur le rendu réel

**Files:**
- Modify: `frontend/src/api/payslips.ts`
- Create: `frontend/src/components/payslip-edit/PayslipPreviewFrame.tsx`
- Delete: `frontend/src/components/payslip-edit/PreviewPanel.tsx`
- Modify: `frontend/src/pages/rh/PayslipEdit.tsx:37` (import) et `:432` (usage)
- Test: `frontend/src/components/payslip-edit/__tests__/PayslipPreviewFrame.test.tsx`

**Interfaces:**
- Consumes: `POST /api/payslips/{id}/preview` (Task 8), réponse `{ html: string }`.
- Produces: `previewPayslip(payslipId: string, payslipData: unknown, pdfNotes?: string): Promise<string>` ; composant `<PayslipPreviewFrame payslipId={string} data={unknown} pdfNotes={string | undefined} />`.

- [ ] **Step 1 : Écrire le test qui échoue**

Créer `frontend/src/components/payslip-edit/__tests__/PayslipPreviewFrame.test.tsx` :

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import PayslipPreviewFrame from '../PayslipPreviewFrame';
import { previewPayslip } from '@/api/payslips';

vi.mock('@/api/payslips', () => ({
  previewPayslip: vi.fn(),
}));

describe('PayslipPreviewFrame', () => {
  beforeEach(() => {
    vi.mocked(previewPayslip).mockReset();
  });

  it('affiche le bulletin rendu par le serveur', async () => {
    vi.mocked(previewPayslip).mockResolvedValue('<p>BULLETIN DE SALAIRE</p>');
    render(<PayslipPreviewFrame payslipId="ps-1" data={{}} />);

    await waitFor(() => {
      const frame = screen.getByTitle('Aperçu du bulletin') as HTMLIFrameElement;
      expect(frame.getAttribute('srcdoc')).toContain('BULLETIN DE SALAIRE');
    });
  });

  it('signale une erreur de rendu sans casser la page', async () => {
    vi.mocked(previewPayslip).mockRejectedValue(new Error('boom'));
    render(<PayslipPreviewFrame payslipId="ps-1" data={{}} />);

    await waitFor(() => {
      expect(screen.getByText(/aperçu indisponible/i)).toBeTruthy();
    });
  });
});
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

Run: `cd frontend && npx vitest run src/components/payslip-edit/__tests__/PayslipPreviewFrame.test.tsx`
Expected: FAIL, module `../PayslipPreviewFrame` introuvable.

- [ ] **Step 3 : Ajouter l'appel API**

Dans `frontend/src/api/payslips.ts`, à la suite de `editPayslip` :

```ts
export const previewPayslip = async (
  payslipId: string,
  payslipData: unknown,
  pdfNotes?: string
): Promise<string> => {
  const response = await apiClient.post<{ html: string }>(
    `/api/payslips/${payslipId}/preview`,
    { payslip_data: payslipData, pdf_notes: pdfNotes ?? null }
  );
  return response.data.html;
};
```

`apiClient` est déjà importé en tête du fichier (`import apiClient from './apiClient';`), comme pour `editPayslip`.

- [ ] **Step 4 : Écrire le composant**

Créer `frontend/src/components/payslip-edit/PayslipPreviewFrame.tsx` :

```tsx
// frontend/src/components/payslip-edit/PayslipPreviewFrame.tsx

import { useCallback, useEffect, useState } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { AlertCircle, RefreshCw } from 'lucide-react';

import { previewPayslip } from '@/api/payslips';

interface PayslipPreviewFrameProps {
  payslipId: string;
  data: unknown;
  pdfNotes?: string;
}

export default function PayslipPreviewFrame({
  payslipId,
  data,
  pdfNotes,
}: PayslipPreviewFrameProps) {
  const [html, setHtml] = useState<string>('');
  const [erreur, setErreur] = useState<string>('');
  const [chargement, setChargement] = useState<boolean>(false);

  const rafraichir = useCallback(async () => {
    setChargement(true);
    setErreur('');
    try {
      setHtml(await previewPayslip(payslipId, data, pdfNotes));
    } catch {
      setErreur("Aperçu indisponible pour le moment.");
    } finally {
      setChargement(false);
    }
  }, [payslipId, data, pdfNotes]);

  useEffect(() => {
    void rafraichir();
    // Rendu à l'ouverture de l'onglet ; les modifications suivantes passent
    // par le bouton, pour ne pas appeler le serveur à chaque frappe.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Aperçu du bulletin tel qu'il sera généré.
        </p>
        <Button variant="outline" size="sm" onClick={rafraichir} disabled={chargement}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Rafraîchir l'aperçu
        </Button>
      </div>

      {erreur && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{erreur}</AlertDescription>
        </Alert>
      )}

      <iframe
        title="Aperçu du bulletin"
        srcDoc={html}
        sandbox=""
        className="h-[1200px] w-full rounded-md border bg-white"
      />
    </div>
  );
}
```

- [ ] **Step 5 : Brancher la page et supprimer l'ancien panneau**

Dans `frontend/src/pages/rh/PayslipEdit.tsx`, remplacer l'import ligne 37 :

```tsx
import PayslipPreviewFrame from '@/components/payslip-edit/PayslipPreviewFrame';
```

et l'usage ligne 432 :

```tsx
          <PayslipPreviewFrame payslipId={payslipId!} data={editedData} pdfNotes={pdfNotes} />
```

La prop `cumuls` n'est plus nécessaire : les cumuls arrivent par `editedData` côté serveur. Si `cumuls` n'est plus utilisé ailleurs dans la page, laisser l'état en place — il alimente d'autres onglets ; vérifier avec `grep -n "cumuls" frontend/src/pages/rh/PayslipEdit.tsx` avant de retirer quoi que ce soit.

Puis supprimer le fichier devenu mort :

```bash
git rm frontend/src/components/payslip-edit/PreviewPanel.tsx
```

- [ ] **Step 6 : Lancer les tests et la compilation**

```bash
cd frontend && npx vitest run src/components/payslip-edit/ && npx tsc --noEmit
```
Expected: tests PASS, aucune erreur TypeScript (notamment aucun import résiduel de `PreviewPanel`).

- [ ] **Step 7 : Commit**

```bash
git add frontend/src/api/payslips.ts \
        frontend/src/components/payslip-edit/PayslipPreviewFrame.tsx \
        frontend/src/components/payslip-edit/__tests__/PayslipPreviewFrame.test.tsx \
        frontend/src/pages/rh/PayslipEdit.tsx
git commit -m "feat(paie): aperçu RH branché sur le rendu réel du bulletin"
```

---

## Vérification finale

- [ ] `cd backend && python -m pytest tests/unit -q` → aucun échec.
- [ ] `cd frontend && npx tsc --noEmit && npx vitest run` → aucun échec.
- [ ] Générer un bulletin réel sur l'environnement de test et le comparer côte à côte avec le bulletin Cegid du même salarié (`data/<societe>/bulletins/<AAAA-MM>/`). Contrôler : une page, montants identiques à ceux d'avant le chantier, colonne latérale alignée, mention « évolution de la rémunération » présente.
- [ ] Vérifier qu'un bulletin sans compteurs de congés, sans cumuls et sans primes reste propre : aucune section vide, aucun `None` affiché.

## Écart connu, hors périmètre

Cegid imprime une ligne `Montant net des heures compl/suppl exo.` avec son cumul annuel. Le montant **net** des heures supplémentaires exonérées n'est pas produit par notre moteur aujourd'hui (`calcul_brut.py` connaît `montant_hs_exonerees` mais seulement comme entrée de mois partiel, pas comme sortie du bulletin). La ligne est donc absente du gabarit. La produire demande un changement de moteur, que la spec exclut explicitement — à traiter séparément si Elsa le réclame.
