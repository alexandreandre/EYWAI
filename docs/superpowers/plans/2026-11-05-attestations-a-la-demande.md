# Attestations à la demande — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**But :** le menu « Générer une attestation » produit deux lettres sourcées (travail, salaire), visibles en mode paie et depuis Exports ; le tableau du mois devient « Récapitulatif des salaires du mois ».

**Architecture :** la commande `generate_document` refuse avant toute écriture et prépare le contexte (période d'essai, bulletins remis regroupés par mois) ; le générateur ReportLab reste pur ; une fenêtre React commune `AttestationDialog` remplace les deux copies et sert trois écrans.

**Pile :** FastAPI + Pydantic, ReportLab, PyPDF2 pour lire les PDF en test, pytest ; React + TanStack Query, Vitest, Playwright.

Spécification : `docs/superpowers/specs/2026-11-05-attestations-a-la-demande-design.md`.

## Contraintes globales

- Tout texte visible dit « Martine », jamais « EYWAI » (`backend/tests/unit/architecture/test_nom_produit.py`).
- Pas de pluriel ni d'accord entre parenthèses (« (s) », « (e) ») : le nombre ou le sexe décide (`test_pas_de_pluriel_entre_parentheses.py`).
- Aucun nom de salarié réel dans un commit, un test ou un message : pseudonymes seulement (« Jeanne Essai »).
- Clés de type inchangées : `attestation_emploi` (« Attestation de travail »), `attestation_salaire` (« Attestation de salaire »).
- Donnée absente = pointillés `A_COMPLETER = "…………………………"`, jamais une valeur inventée.
- Python : `/Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest` depuis `backend/`, avec `APP_ENV=test`.
- Frontend : `npx vitest run <fichier>` depuis `frontend/`.

---

### Tâche 1 : types et requête

**Fichiers :**
- Modifier : `backend/app/modules/document_library/schemas/requests.py`
- Modifier : `backend/app/modules/documents/schemas/requests.py`
- Modifier : `backend/app/modules/documents/application/commands.py` (`generate_document`)
- Test : `backend/tests/unit/documents/test_attestations_commande.py`

**Produit :** `ATTESTATIONS_RETIREES: frozenset[str]` ; `KNOWN_DOCUMENT_TYPES` sans elles ; `GenerateDocumentRequest.nombre_mois: Optional[int]` (1 à 12).

- [ ] Test : une demande `attestation_location` lève `ValueError("Ce type d'attestation n'existe plus : choisissez l'attestation de travail ou l'attestation de salaire.")` ; `nombre_mois=13` est refusé par Pydantic ; le libellé de `attestation_emploi` est « Attestation de travail » ; les types retirés ne sont plus dans `KNOWN_DOCUMENT_TYPES` mais gardent leur libellé.
- [ ] Le lancer : échec attendu.
- [ ] Implémenter :

```python
# document_library/schemas/requests.py
    "attestation_emploi": "Attestation de travail",
# …
# Retirées le 05/11/2026 : elles disaient la même chose que l'attestation de
# travail, ou reprenaient le salaire de la fiche au lieu des bulletins. Leur
# libellé reste, pour afficher les documents déjà générés.
ATTESTATIONS_RETIREES: frozenset[str] = frozenset({
    "attestation_presence", "attestation_anciennete", "attestation_poste",
    "attestation_revenus", "attestation_location", "attestation_pret",
    "attestation_retraite",
})
KNOWN_DOCUMENT_TYPES: frozenset[str] = frozenset(DOCUMENT_TYPE_LABELS) - ATTESTATIONS_RETIREES

# documents/schemas/requests.py, dans GenerateDocumentRequest
    nombre_mois: Optional[int] = Field(
        default=None, ge=1, le=12,
        description="Attestation de salaire : nombre de mois de paie repris (3 par défaut).",
    )

# documents/application/commands.py, en tête de generate_document
    if request.document_type in ATTESTATIONS_RETIREES:
        raise ValueError(
            "Ce type d'attestation n'existe plus : choisissez l'attestation "
            "de travail ou l'attestation de salaire."
        )
```

- [ ] Relancer : vert. Commit `feat(attestations): deux types, les sept autres retirés`.

### Tâche 2 : les mois d'une attestation de salaire

**Fichiers :**
- Créer : `backend/app/modules/documents/domain/__init__.py`, `backend/app/modules/documents/domain/attestation_salaire.py`
- Test : `backend/tests/unit/documents/test_attestation_salaire_mois.py`

**Produit :** `NOMBRE_DE_MOIS_PAR_DEFAUT = 3` ; `mois_a_attester(bulletins, nombre) -> list[dict]` (clés `year`, `month`, `brut`, `net_avant_impot`, du plus ancien au plus récent) ; `total(lignes, cle) -> float | None`.

- [ ] Tests :
  - 5 mois remis, `nombre=3` : les 3 plus récents, dans l'ordre chronologique ;
  - deux bulletins le même mois : une ligne, montants sommés ;
  - 1 mois remis, `nombre=3` : une seule ligne ;
  - un net manquant (`synthese_net` absent) : `net_avant_impot` vaut None pour ce mois, et `total` vaut None ;
  - aucun bulletin : liste vide.
- [ ] Échec attendu, puis implémentation (code dans la tâche, montants arrondis à 2 décimales), puis vert. Commit `feat(attestations): les mois repris des bulletins remis`.

### Tâche 3 : les deux lettres

**Fichiers :**
- Réécrire : `backend/app/services/common_attestation_generator.py`
- Supprimer : `backend/tests/integration/legacy/test_common_attestation_generator.py` (il teste les 7 types retirés)
- Test : `backend/tests/unit/documents/test_attestations_lettres.py`

**Consomme :** le contexte `periode_essai_fin` (date ISO ou None), `mois_de_paie` (sortie de `mois_a_attester`), `nombre_mois_demande`, `date_generation` (facultatif, pour les tests).
**Produit :** `CommonAttestationGenerator.ATTESTATION_TYPES == ["attestation_emploi", "attestation_salaire"]` ; `generate(type, employee, company, context) -> bytes`.

- [ ] Tests, sur le texte lu avec PyPDF2 :
  - **travail** : titre « Attestation de travail », « agissant pour le compte de la société », SIRET, « Madame Jeanne Essai » quand `sexe="F"`, « 1 an et 3 mois » d'ancienneté, « Contrat à durée déterminée (CDD) jusqu'au 31 décembre 2026 », « 2 200,00 € », « fait toujours partie de nos effectifs », « Signature et cachet de l'employeur » ;
  - **période d'essai** : la ligne n'apparaît que si `periode_essai_fin` est donnée ;
  - **donnée absente** : sans adresse ni signataire, « Adresse » est suivie de pointillés, et on lit « Nom et fonction du signataire » ;
  - **pas de genre inventé** : sans `sexe`, ni « Madame » ni « Monsieur » ;
  - **salaire** : « ses 3 derniers mois de paie », « Août 2026 », la ligne « Total », « Net à payer avant impôt sur le revenu » ;
  - « son dernier mois de paie » quand il n'y a qu'un mois ;
  - `mois_de_paie` vide : `ValueError` ;
  - type retiré : `ValueError`.
- [ ] Échec attendu, réécriture, vert. Commit `feat(attestations): lettres de travail et de salaire selon le modèle du ministère`.

### Tâche 4 : la commande prépare et refuse

**Fichiers :**
- Créer : `backend/app/modules/documents/infrastructure/attestation_queries.py` (`bulletins_remis_du_salarie(employee_id, company_id)`, `fin_de_periode_d_essai_en_cours(employee_id, company_id)`)
- Modifier : `backend/app/modules/documents/application/commands.py` (`_contexte_attestation`, appelée dans `generate_document`)
- Test : `backend/tests/unit/documents/test_attestations_commande.py` (suite)

- [ ] Tests (lecteurs remplacés par monkeypatch, `document_service.generate_document` intercepté) :
  - salarié `parti` + travail : `ValueError` contenant « a quitté l'entreprise », rien n'est généré ;
  - salaire sans bulletin remis : `ValueError` « Aucun bulletin remis à Jeanne Essai » ;
  - salaire avec `nombre_mois=2` : le contexte passé au service contient 2 `mois_de_paie` et `nombre_mois_demande == 2` ;
  - travail : `periode_essai_fin` est passée au service.
- [ ] Échec, implémentation, vert. Commit `feat(attestations): la commande lit la période d'essai et les bulletins remis`.

### Tâche 5 : le récapitulatif des salaires du mois

**Fichiers :**
- Modifier : `backend/app/modules/exports/infrastructure/export_attestations.py`, `backend/app/modules/exports/application/service.py` (nom de fichier), `backend/app/modules/exports/application/scheduled_exports.py` (libellé)
- Test : `backend/tests/unit/exports/test_export_recapitulatif_salaires.py`

- [ ] Tests :
  - les colonnes sont exactement `["Matricule", "Employé", "Période", "Brut", "Net imposable", "Net à payer"]` ;
  - le matricule vient de `employees.matricule`, pas de l'identifiant interne ;
  - aucune colonne « Statut ».
- [ ] Échec, implémentation, vert. Commit `fix(exports): récapitulatif des salaires du mois, vrai matricule`.

### Tâche 6 : configuration de l'écran (fonctions pures)

**Fichiers :**
- Modifier : `frontend/src/lib/documentGenerationConfig.ts`, `frontend/src/api/documentLibrary.ts`, `frontend/src/api/documents.ts`
- Test : `frontend/src/lib/documentGenerationConfig.test.ts`

**Produit :**
- `ATTESTATION_COURANTE_TYPES = ['attestation_emploi', 'attestation_salaire']` ;
- `NOMBRE_MOIS_PAR_DEFAUT = 3`, `NOMBRE_MOIS_MAX = 12` ;
- `payloadAttestation({ employeeId, documentType, nombreMois, templateId }): GenerateDocumentPayload` : `nombre_mois` seulement pour le salaire, borné de 1 à 12 ;
- `attestationsDuSalarie(rows: GeneratedDocument[])` : les deux types, la plus récente en premier ;
- `ATTESTATIONS_RETIREES: ReadonlySet<string>` ;
- `GenerateDocumentPayload.nombre_mois?: number | null`.

- [ ] Tests Vitest de chacune de ces fonctions, échec, implémentation, vert. Commit `feat(attestations): configuration de la fenêtre`.

### Tâche 7 : la fenêtre et ses trois portes

**Fichiers :**
- Créer : `frontend/src/components/documents/AttestationDialog.tsx`
- Modifier :
  - `frontend/src/components/employee-detail/EmployeeDetailDocumentsRhSection.tsx` (la copie de la fenêtre est retirée) ;
  - `frontend/src/components/documents/useCompanyDocumentGeneration.tsx` (idem) ;
  - `frontend/src/components/employee-detail/EmployeeDetailDocumentsTab.tsx` (bloc « Attestations » en mode paie) ;
  - `frontend/src/components/exports/DeclarationsTab.tsx` (carte « Attestation pour un salarié », carte renommée) ;
  - `frontend/src/components/exports/ExportHistory.tsx`, `ExportCommonModel.tsx` (libellés) ;
  - `frontend/src/features/company/components/DocumentLibraryTab.tsx` (types retirés filtrés) ;
  - `frontend/src/test/fenetresExportTitres.test.ts`.

**Comportement de `AttestationDialog`** (props `open`, `onOpenChange`, `employee?`, `onGenerated?`) :
- sans `employee`, une liste des salariés non partis ;
- le type (2 choix) ;
- le nombre de mois (saisie numérique de 1 à 12) pour le salaire seulement ;
- le modèle ;
- une ligne fixe sur le signataire ;
- en cas de refus, un encadré rouge dans la fenêtre, qui reste ouverte, plus un message d'erreur ;
- en cas de succès, le message « {libellé} de {Prénom Nom} prête », puis l'aperçu (`openDocumentPreview`), puis `onGenerated`.

- [ ] `npx tsc --noEmit -p tsconfig.app.json` et `npx vitest run` verts. Commit `feat(attestations): une fenêtre commune, en mode paie et dans Exports`.

### Tâche 8 : vérification de bout en bout et déploiement

**Fichiers :**
- Créer : `frontend/e2e/connecte/11-attestations.spec.ts`

Un seul parcours, en mode paie (réécriture de `/api/auth/me` comme dans `08-mode-paie`) :
- fiche d'un salarié actif > Documents > « Générer une attestation » > travail > Générer : l'aperçu s'ouvre, et on note l'identifiant du document ;
- salaire : l'encadré « Aucun bulletin remis » s'affiche ;
- Exports > Déclarations > « Attestation pour un salarié » : la fenêtre propose la liste des salariés ;
- à la fin, suppression des documents générés (`DELETE /api/documents/{id}`).

- [ ] Suite backend et frontend verte, push, puis `gh workflow run deploy-test-env.yml --ref feat/attestations-a-la-demande`. Suivre le run, vérifier `/health`, puis lancer le parcours contre le site de test.
