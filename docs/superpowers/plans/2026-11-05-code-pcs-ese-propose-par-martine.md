# Code PCS-ESE trouvé par Martine — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** la RH ne cherche plus le code PCS-ESE : liste des 430 codes avec recherche, proposition
par les collègues puis par les métiers Insee, bloc S21.G00.41 quand le code change, script des 198
fiches à « 9999 ».

**Architecture:** un module serveur `pcs_ese` (référentiel JSON + fonctions pures de proposition et
de changement, testées à part) exposé par deux routes ; l'écran ne fait qu'afficher. Le bloc 41 est
calculé par une fonction pure du domaine DSN, branchée dans le constructeur ; la date de la dernière
DSN déposée vient de `dsn_transmissions`.

**Tech Stack:** FastAPI, Supabase (Python), pytest ; React, react-hook-form, zod, react-query,
cmdk (`@/components/ui/command`), vitest.

Spécification : `docs/superpowers/specs/2026-11-05-code-pcs-ese-propose-par-martine-design.md`.

## Global Constraints

- Liste officielle : 430 codes de la table DSN PCSESE P26V01 (429 PCS-ESE 2017 + « 9999 »).
- Un cadre ne reçoit que des codes du groupe 3 ; un non-cadre que des groupes 4, 5, 6 (proposition seulement).
- Jamais proposés d'office : groupes 1 et 2, codes publics (« * »), métiers « (Etat) », « (coll. loc.) », « (fonction publique) ».
- Sûr par les collègues : tous le même code ; **code ECAP : au moins 2 collègues d'accord**.
- Sûr par l'Insee : intitulé égal à un métier sans secteur entre parenthèses, un seul code.
- Un vrai code n'est jamais remplacé par une proposition ; un import DSN ne remet jamais « 9999 » sur un vrai code.
- Bloc 41 : .001 = date du changement (JJMMAAAA), .019 = ancien code, .028 = 1er du mois de la date.
- « Déjà déclaré » : DSN mensuelle de la société pour ce mois ou après, statut `sent`, `acknowledged` ou `manual`.
- Aucun nom de salarié dans un commit ; écriture des 198 seulement après « lance <script> ».
- Tests serveur : depuis `backend/`, `APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key .venv/bin/python -m pytest <chemin> -q`.
- Tests écran : depuis `frontend/`, `npx vitest run <chemin>` ; `npm run typecheck`.

---

## Lot 1 — Référentiel et proposition (serveur)

### Task 1: le fichier de référence

**Files:**
- Create: `backend/scripts/pcs_ese/construire_referentiel.py`
- Create: `backend/app/modules/pcs_ese/__init__.py`, `backend/app/modules/pcs_ese/data/pcs_ese_2017.json` (généré)
- Create: `backend/app/modules/pcs_ese/domain/__init__.py`, `backend/app/modules/pcs_ese/domain/referentiel.py`
- Test: `backend/tests/unit/pcs_ese/__init__.py`, `backend/tests/unit/pcs_ese/test_referentiel.py`

**Interfaces — Produces:**
- `Exclusion(libelle: str, voir: tuple[str, ...])`
- `Rubrique(code, libelle, typiques: tuple[str,...], assimilees: tuple[str,...], exclues: tuple[Exclusion,...], public: bool, ecap: bool)`, propriété `groupe -> str` (premier caractère)
- `CODES_ECAP: frozenset[str]` (36 codes, guide OETH Urssaf v2.5 p. 22-23)
- `charger_referentiel() -> dict[str, Rubrique]` (mis en cache), `code_valide(code: str) -> bool`

- [ ] **Step 1: tests du référentiel**

```python
from app.modules.pcs_ese.domain.referentiel import CODES_ECAP, charger_referentiel, code_valide

def test_430_codes_dont_9999():
    ref = charger_referentiel()
    assert len(ref) == 430
    assert "9999" in ref and ref["9999"].typiques == ()

def test_metiers_insee_lus():
    r = charger_referentiel()["543g"]
    assert r.libelle == "Employés administratifs qualifiés des autres services des entreprises"
    assert "Employé de bureau (sauf Etat, coll. loc., banque, assurances, transports), employé qualifié" in r.typiques
    assert any(e.voir == ("524b",) for e in r.exclues)

def test_codes_publics_et_ecap():
    ref = charger_referentiel()
    assert sum(r.public for r in ref.values()) == 17
    assert ref["624d"].ecap and ref["643a"].ecap and not ref["674a"].ecap
    assert len(CODES_ECAP) == 36

def test_code_valide_casse_comprise():
    assert code_valide("674a") and code_valide("9999")
    assert not code_valide("674A") and not code_valide("999a") and not code_valide("")
```

- [ ] **Step 2: lancer, constater l'échec** (module absent).
- [ ] **Step 3: script de construction** — lit les 429 pages de
  `data/_sources/insee/pcs-ese-2017-pages-2026-11-05/` et la table
  `data/_sources/net-entreprises/NEODESP26-PCSESE-P26V01.csv` (latin-1), écrit le JSON :
  `{"sources": {...urls, dates...}, "rubriques": [{"code","libelle","public","mise_a_jour","typiques","assimilees","exclues":[{"libelle","voir":[...]}]}]}`.
  Le libellé et le caractère public viennent de la table (fait foi pour la liste), les métiers des pages.
  Lecture des pages : celle du prototype `proto/parse_insee.py` (titre « Rubrique <code> : », sections
  « Professions les plus typiques » / « assimilées » / « exclues » jusqu'à « Nos sites partenaires »,
  « (voir …) » en fin de ligne → codes `\d{3}[a-z]`).
- [ ] **Step 4: `referentiel.py`** — dataclasses gelées, `CODES_ECAP` (liste p. 22-23 recopiée),
  `charger_referentiel()` (`functools.lru_cache`, `Path(__file__).parents[1] / "data" / "pcs_ese_2017.json"`),
  `code_valide = lambda c: c in charger_referentiel()`.
- [ ] **Step 5: tests verts.**
- [ ] **Step 6: commit** `feat(pcs-ese): référentiel des 430 codes et métiers Insee`.

### Task 2: la proposition (fonction pure)

**Files:**
- Create: `backend/app/modules/pcs_ese/domain/normalisation.py`, `backend/app/modules/pcs_ese/domain/proposition.py`
- Test: `backend/tests/unit/pcs_ese/test_proposition.py`

**Interfaces:**
- Consumes: `Rubrique`, `charger_referentiel()`
- Produces:
  - `normaliser_poste(texte: str) -> str` (minuscules, sans accents ni ponctuation, espaces simples)
  - `est_cadre(statut: str) -> bool` (« cadre » sans « non »)
  - `FicheCollegue(employee_id: str, company_id: str, societe: str, poste: str, statut: str, code: str)`
  - `collegues_de(fiches, *, company_id, poste, statut, exclure_id) -> tuple[list[FicheCollegue], list[FicheCollegue]]` (société, autres sociétés)
  - `Candidat(code: str, libelle: str, raison: str, ecap: bool)`
  - `Proposition(code: str|None, sur: bool, raison: str, regle: str|None, nb_collegues: int, candidats: tuple[Candidat,...], ecap: bool)`
  - `proposer(*, poste: str, statut: str, collegues_societe, collegues_groupe, referentiel=None) -> Proposition`

- [ ] **Step 1: tests**

```python
from app.modules.pcs_ese.domain.proposition import FicheCollegue, collegues_de, proposer

def f(code, poste="Agent de production", statut="Non-Cadre", cid="c1", soc="Soc A", eid="x"):
    return FicheCollegue(eid, cid, soc, poste, statut, code)

def test_a_tous_le_meme_code_sur():
    p = proposer(poste="agent de production", statut="Non-Cadre",
                 collegues_societe=[f("674a"), f("674a"), f("674a")], collegues_groupe=[])
    assert (p.code, p.sur, p.regle, p.nb_collegues) == ("674a", True, "a", 3)
    assert p.raison == "Même poste et même statut que 3 collègues de Soc A, tous en 674a."

def test_un_seul_collegue_suffit():
    p = proposer(poste="x", statut="Non-Cadre", collegues_societe=[f("674a")], collegues_groupe=[])
    assert p.sur and p.raison == "Même poste et même statut qu'1 collègue de Soc A, en 674a."

def test_desaccord_pas_sur_et_codes_les_plus_frequents():
    p = proposer(poste="x", statut="Non-Cadre",
                 collegues_societe=[f("674a"), f("625h"), f("674a")], collegues_groupe=[f("623e", cid="c2")])
    assert not p.sur and p.code is None and p.regle == "a"
    assert [c.code for c in p.candidats][:2] == ["674a", "625h"]

def test_b_groupe_quand_personne_dans_la_societe():
    p = proposer(poste="x", statut="Non-Cadre", collegues_societe=[],
                 collegues_groupe=[f("674a", cid="c2", soc="Comitech")])
    assert (p.code, p.regle) == ("674a", "b")
    assert p.raison == "Même poste et même statut qu'1 collègue du groupe (Comitech), en 674a."

def test_9999_et_vide_ne_comptent_pas():
    p = proposer(poste="contrôleur de gestion", statut="Non-Cadre",
                 collegues_societe=[f("9999"), f("")], collegues_groupe=[])
    assert p.regle == "c"

def test_ecap_un_seul_collegue_propose_pas_pose():
    p = proposer(poste="x", statut="Non-Cadre", collegues_societe=[f("624d")], collegues_groupe=[])
    assert not p.sur and p.candidats[0].code == "624d" and p.candidats[0].ecap
    assert "Code ECAP" in p.candidats[0].raison

def test_ecap_deux_collegues_pose():
    p = proposer(poste="x", statut="Non-Cadre", collegues_societe=[f("624d"), f("624d")], collegues_groupe=[])
    assert p.sur and p.ecap

def test_c_metier_exact_sans_secteur():
    p = proposer(poste="Contrôleur de gestion - apprenti", statut="Non-Cadre",
                 collegues_societe=[], collegues_groupe=[])
    assert (p.code, p.sur, p.regle) == ("461d", True, "c")
    assert p.raison == "Métier Insee : « Contrôleur de gestion, non cadre » (rubrique 461d)."

def test_c_cadre_ecarte_les_non_cadres():
    p = proposer(poste="Responsable méthode", statut="Cadre", collegues_societe=[], collegues_groupe=[])
    assert (p.code, p.sur) == ("387c", True)

def test_c_metier_a_secteur_jamais_sur():
    p = proposer(poste="Soudeur", statut="Non-Cadre", collegues_societe=[], collegues_groupe=[])
    assert not p.sur and len(p.candidats) <= 3

def test_c_plusieurs_codes_trois_propositions():
    p = proposer(poste="Agent d'entretien", statut="Non-Cadre", collegues_societe=[], collegues_groupe=[])
    assert not p.sur and len(p.candidats) == 3
    assert all(c.code[0] in "456" for c in p.candidats)

def test_jamais_groupes_1_2_ni_public():
    p = proposer(poste="Peintre", statut="Non-Cadre", collegues_societe=[], collegues_groupe=[])
    assert all(c.code[0] not in "12" and not c.code.endswith("*") for c in p.candidats)

def test_rien_trouve():
    p = proposer(poste="Pilote IA / robotique", statut="Non-Cadre", collegues_societe=[], collegues_groupe=[])
    assert p.code is None and p.regle is None
    assert p.raison.startswith("Aucun collègue au même poste")

def test_collegues_de_meme_poste_meme_statut_sans_soi():
    fiches = [f("674a", poste="Agent de Production", eid="1"), f("674a", eid="moi"),
              f("625h", statut="Cadre", eid="2"), f("623e", cid="c2", soc="B", eid="3")]
    soc, grp = collegues_de(fiches, company_id="c1", poste="agent de production ",
                            statut="Non-Cadre", exclure_id="moi")
    assert [x.employee_id for x in soc] == ["1"] and [x.employee_id for x in grp] == ["3"]
```

- [ ] **Step 2: échec constaté.**
- [ ] **Step 3: `normalisation.py`** — `normaliser_poste` ; `mots_metier(texte) -> list[str]` (règle c) :
  minuscules sans accents, ponctuation → espace, mots vides retirés (`de du des d la le les l et en a au aux h f dont pour sur par`),
  abréviations (`agt→agent, prod→production, qualif→qualifie, resp→responsable, ass/assist/assit→assistant,
  techni→technicien, app→apprenti, adj→adjoint, chaufeur→chauffeur`), féminin → masculin (`trice→teur, euse→eur,
  iere→ier, ienne→ien`), pluriel `s` final retiré (mot > 4 lettres). `tete(metier)` = avant la première virgule ou parenthèse.
- [ ] **Step 4: `proposition.py`** — `proposer` : a) codes vrais (dans le référentiel, ≠ « 9999 ») de la société ; sinon b) du groupe ;
  sinon c). Collègues unanimes → sûr sauf ECAP avec moins de 2 collègues. Désaccord → candidats par fréquence, complétés
  par les métiers, 3 au plus, sans doublon. c) : index des têtes de métiers (typiques=0, assimilées=1, exclues→codes « voir »=2),
  filtres (groupe 3 si cadre, 4-6 sinon ; jamais public ni groupe 1-2 ; métier public sauté sauf « sauf ») ;
  exact = tête normalisée égale à l'intitulé normalisé (sans « apprenti ») ; proche = l'un contient tous les mots de l'autre
  (dernier mot pris en préfixe si l'intitulé fait 30 caractères ou plus) ; sûr si un seul code exact et métier sans
  « ( » autre que « (sauf ». Raisons exactement comme dans les tests.
- [ ] **Step 5: tests verts.**
- [ ] **Step 6: commit** `feat(pcs-ese): Martine propose le code (collègues, groupe, métiers Insee)`.

### Task 3: lecture des collègues et routes

**Files:**
- Create: `backend/app/modules/pcs_ese/infrastructure/__init__.py`, `.../infrastructure/fiches.py`
- Create: `backend/app/modules/pcs_ese/application/__init__.py`, `.../application/queries.py`
- Create: `backend/app/modules/pcs_ese/api/__init__.py`, `.../api/router.py`
- Modify: `backend/app/api/router.py` (import + `router.include_router(pcs_ese_router)`)
- Test: `backend/tests/unit/pcs_ese/test_queries.py`

**Interfaces:**
- Produces: `fiches_du_groupe(company_id: str) -> list[FicheCollegue]` (sociétés du même `group_id`, ou la société seule) ;
  `proposition_pour(company_id, poste, statut, employee_id=None, fiches=None) -> Proposition` ;
  `referentiel_pour_ecran() -> list[dict]` (`code, libelle, metiers, ecap, public`) ;
  routes `GET /api/pcs-ese/referentiel`, `GET /api/pcs-ese/proposition?poste=&statut=&employee_id=` (RH ou admin de la société active ;
  un `employee_id` d'une autre société → 404 via `access_control_service.assert_employee_in_company`).

- [ ] **Step 1: test** — `proposition_pour` avec `fiches=[...]` fournies (pas de base) rend la proposition attendue et exclut `employee_id` ;
  `referentiel_pour_ecran()` a 430 lignes et « 9999 » en dernier.
- [ ] **Step 2-4: échec, code, vert.** `fiches.py` lit `companies(id, company_name, group_id)` puis `employees(id, company_id, job_title, statut, classification_conventionnelle)`.
- [ ] **Step 5: commit** `feat(pcs-ese): routes du référentiel et de la proposition`.

### Task 4: contrôle « dans la liste » à l'aperçu DSN

**Files:** Modify `backend/app/modules/dsn_export/domain/fiche_a_completer.py:15-57` ; Test `backend/tests/unit/exports/test_dsn_fiche_a_completer.py`

- [ ] **Step 1: test** — `"674A"` et `"999a"` → manque « code PCS-ESE « 674A » hors liste », message
  « Code PCS-ESE (S21.G00.40.004) « 674A » absent de la liste officielle (table DSN PCSESE, contrôle CRE-11) : à choisir dans la liste sur la fiche » ;
  `"674a"` et `"9999"` → aucun manque.
- [ ] **Step 2-4:** remplacer `_PCS_ESE.match` par `code_valide`. Adapter les tests existants qui attendaient « hors format ».
- [ ] **Step 5: commit** `fix(dsn): le code PCS-ESE doit être dans la liste officielle`.

## Lot 2 — L'écran

### Task 5: appels et fonctions d'écran

**Files:** Create `frontend/src/api/pcsEse.ts`, `frontend/src/features/pcs-ese/pcsEse.ts`, Test `frontend/src/features/pcs-ese/pcsEse.test.ts`

**Interfaces — Produces:**
- types `RubriquePcs {code, libelle, metiers: string[], ecap, public}`, `CandidatPcs {code, libelle, raison, ecap}`,
  `PropositionPcs {code: string|null, sur, raison, regle, nb_collegues, candidats: CandidatPcs[], ecap}`
- `getReferentielPcsEse(): Promise<RubriquePcs[]>`, `getPropositionPcsEse(p: {poste, statut, employee_id?}): Promise<PropositionPcs>`
- `filtrerRubriques(rubriques, recherche, max = 50): RubriquePcs[]` (code en tête, puis libellé, puis métier ; sans accents ni casse)
- `doitPreRemplir(codeActuel: string, p: PropositionPcs | undefined): boolean` (vrai si `p.sur`, `p.code`, et code actuel vide ou « 9999 »)
- `texteChangement(changement?: {ancien: string; date: string}): string | null` → « Code changé le 06/11/2026 (avant : 9999). Martine déclare ce changement dans la DSN. »

- [ ] **Steps:** tests vitest de ces trois fonctions (recherche « soud » trouve un métier « Soudeur », « 674 » met 674a en tête ;
  pré-remplissage refusé sur « 674a », accepté sur « » et « 9999 », refusé si `sur=false`) ; échec ; code ; vert ; commit
  `feat(ecran): référentiel PCS-ESE et règles de proposition`.

### Task 6: le champ `PcsEseField` et la fiche

**Files:** Create `frontend/src/features/pcs-ese/PcsEseField.tsx` ; Modify
`frontend/src/features/employee-detail/components/EmployeeProfileEditForm.tsx:420-431` ;
Test `frontend/src/features/pcs-ese/PcsEseField.test.tsx`

- Props : `value, onChange, poste, statut, employeeId?, changement?`.
- Popover + Command (modèle `features/admin-import/components/CompanyCombobox.tsx`), recherche via `filtrerRubriques`.
- Proposition : `useQuery(['pcs-ese-proposition', poste, statut, employeeId], …, {enabled: poste.length >= 2})`.
  Si `doitPreRemplir` → `onChange(code)` une seule fois par proposition, et sous le champ « Proposé par Martine : <raison> ».
  Sinon, si candidats → « Codes probables : » + un bouton par candidat (`code — libellé`, raison en dessous, « Code ECAP : il réduit la contribution OETH » si `ecap`).
- [ ] **Steps:** test (rendu avec un client react-query et des réponses simulées : pré-remplissage + raison visibles ; 3 boutons ; clic → `onChange`) ;
  échec ; code ; brancher dans la fiche (`poste = watch('job_title')`, `statut = watch('statut')`, `changement = classification.pcs_changement`) ; vert ;
  `npm run typecheck` ; commit `feat(fiche): le code PCS-ESE se choisit dans la liste, Martine propose`.

### Task 7: la création

**Files:** Modify `createEmployeeFormSchema.ts` (`code_pcs: z.string().optional().default('')`), `CreateEmployeeForm.tsx`
(défaut `code_pcs: ''`, champ après le poste, envoi `classification_conventionnelle: {...classificationPourEnvoi(c), ...(values.code_pcs ? {pcs: values.code_pcs} : {})}`) ;
Test `createEmployeeFormSchema.test.ts` (le code passe), test de l'envoi si une fonction pure existe, sinon extraire `classificationAvecPcs(c, pcs)` dans `classificationConventionnelle.ts` et la tester.
- [ ] **Steps:** test ; échec ; code ; vert ; typecheck ; commit `feat(creation): code PCS-ESE proposé à la création`.

## Lot 3 — Le bloc 41

### Task 8: noter le changement de code (fonction pure + `update_employee`)

**Files:** Create `backend/app/modules/pcs_ese/domain/changement.py`, `backend/app/modules/pcs_ese/infrastructure/transmissions.py` ;
Modify `backend/app/modules/employees/application/commands.py:754` (`update_employee(..., *, depuis_import: bool = False)`),
`backend/app/modules/dsn_import/application/commit.py:945` (`update_employee(employee_id, clean_payload, depuis_import=True)`) ;
Test `backend/tests/unit/pcs_ese/test_changement.py`, `backend/tests/unit/employees/test_update_pcs.py`

**Interfaces — Produces:**
- `appliquer_changement_pcs(avant: dict|None, apres: dict|None, *, aujourd_hui: date, depuis_import: bool, derniere_periode_deposee: str|None) -> dict|None`
  (la classification à écrire, avec `pcs_changement = {"ancien": str, "date": "AAAA-MM-JJ"}` posé, gardé ou retiré)
- `en_attente(changement: dict|None, derniere_periode_deposee: str|None) -> bool` (mois du changement > dernière période déposée, ou aucune)
- `derniere_periode_deposee(company_id: str) -> str|None` (max `period` de `dsn_transmissions`, statut `sent|acknowledged|manual`, type mensuel)

- [ ] **Step 1: tests**

```python
from datetime import date
from app.modules.pcs_ese.domain.changement import appliquer_changement_pcs as ap

J = date(2026, 11, 6)

def test_9999_vers_vrai_code_note_l_ancien():
    r = ap({"pcs": "9999"}, {"pcs": "674a"}, aujourd_hui=J, depuis_import=False, derniere_periode_deposee=None)
    assert r["pcs_changement"] == {"ancien": "9999", "date": "2026-11-06"}

def test_premier_code_rien_a_declarer():
    r = ap({}, {"pcs": "674a"}, aujourd_hui=J, depuis_import=False, derniere_periode_deposee=None)
    assert "pcs_changement" not in r

def test_deux_changements_avant_depot_garde_le_premier_ancien():
    avant = {"pcs": "674a", "pcs_changement": {"ancien": "9999", "date": "2026-11-02"}}
    r = ap(avant, {"pcs": "625h"}, aujourd_hui=J, depuis_import=False, derniere_periode_deposee=None)
    assert r["pcs_changement"] == {"ancien": "9999", "date": "2026-11-06"}

def test_retour_a_l_ancien_rien_a_declarer():
    avant = {"pcs": "674a", "pcs_changement": {"ancien": "9999", "date": "2026-11-02"}}
    r = ap(avant, {"pcs": "9999"}, aujourd_hui=J, depuis_import=False, derniere_periode_deposee=None)
    assert "pcs_changement" not in r

def test_changement_deja_declare_remplace():
    avant = {"pcs": "674a", "pcs_changement": {"ancien": "9999", "date": "2026-09-10"}}
    r = ap(avant, {"pcs": "625h"}, aujourd_hui=J, depuis_import=False, derniere_periode_deposee="2026-09")
    assert r["pcs_changement"] == {"ancien": "674a", "date": "2026-11-06"}

def test_le_client_ne_fabrique_pas_de_changement():
    r = ap({"pcs": "674a"}, {"pcs": "674a", "pcs_changement": {"ancien": "1", "date": "2020-01-01"}},
           aujourd_hui=J, depuis_import=False, derniere_periode_deposee=None)
    assert "pcs_changement" not in r

def test_import_ne_remet_pas_9999_ni_ne_note():
    avant = {"pcs": "674a", "pcs_changement": {"ancien": "9999", "date": "2026-11-02"}}
    r = ap(avant, {"pcs": "9999", "idcc": "0292"}, aujourd_hui=J, depuis_import=True, derniere_periode_deposee=None)
    assert r["pcs"] == "674a" and r["idcc"] == "0292"
    assert r["pcs_changement"] == {"ancien": "9999", "date": "2026-11-02"}

def test_import_vrai_code_different_pas_de_changement_a_declarer():
    r = ap({"pcs": "674a"}, {"pcs": "625h"}, aujourd_hui=J, depuis_import=True, derniere_periode_deposee=None)
    assert r["pcs"] == "625h" and "pcs_changement" not in r
```

  Et dans `test_update_pcs.py` (modèle `tests/unit/employees/test_auth_email_sync.py`, `patch.object(commands, "_employee_repository")`) :
  `update_employee` avec `{"classification_conventionnelle": {"pcs": "674a"}}` sur une fiche à « 9999 » envoie au dépôt
  `pcs_changement` ; avec `depuis_import=True` et « 9999 » sur une fiche à « 674a », le dépôt reçoit « 674a ».
- [ ] **Step 2-4:** échec ; code ; vert. Dans `update_employee`, seulement si `"classification_conventionnelle" in update_data` :
  lire la fiche courante, `derniere_periode_deposee(company_id)` seulement si le code change, appliquer.
- [ ] **Step 5: commit** `feat(pcs-ese): Martine note l'ancien code quand il change ; l'import ne remet pas 9999`.

### Task 9: écrire le bloc S21.G00.41 dans la DSN

**Files:** Create `backend/app/modules/dsn_export/domain/changement_pcs.py` ; Modify
`backend/app/modules/dsn_export/domain/writer.py:623-668` (émettre `ctr.changements` juste après les rubriques du bloc 40,
dans les deux branches), `backend/app/modules/dsn_export/application/builder.py` (`build_individu_from_payroll(..., derniere_periode_deposee=None)`,
`build_parsed_dsn_from_payroll(..., derniere_periode_deposee=None)` qui le transmet ; après la création de `ctr`,
`bloc = bloc_changement_pcs(classification, pcs, period, derniere_periode_deposee)` → `ctr.changements = [bloc]`),
`backend/app/modules/exports/infrastructure/export_dsn.py` (aperçu, génération, cotisations du mois : `derniere_periode_deposee(company_id)`) ;
Test `backend/tests/unit/dsn_export/test_changement_pcs.py`

**Interfaces — Produces:** `bloc_changement_pcs(classification: dict, pcs_actuel: str, period: str, derniere_periode_deposee: str|None) -> ChangementContratBlock|None`

- [ ] **Step 1: tests**

```python
from app.modules.dsn_export.domain.changement_pcs import bloc_changement_pcs as b

C = {"pcs": "674a", "pcs_changement": {"ancien": "9999", "date": "2026-11-06"}}

def test_bloc_du_mois():
    bloc = b(C, "674a", "2026-11", None)
    assert bloc.rubriques == {"S21.G00.41.001": "06112026", "S21.G00.41.019": "9999", "S21.G00.41.028": "01112026"}

def test_mois_suivant_tant_que_rien_n_est_depose():
    assert b(C, "674a", "2026-12", "2026-10") is not None

def test_deja_declare():
    assert b(C, "674a", "2026-12", "2026-11") is None

def test_changement_apres_le_mois_declare():
    assert b(C, "674a", "2026-10", None) is None

def test_ancien_egal_actuel_ou_absent():
    assert b({"pcs": "9999", "pcs_changement": {"ancien": "9999", "date": "2026-11-06"}}, "9999", "2026-11", None) is None
    assert b({"pcs": "674a"}, "674a", "2026-11", None) is None
```

  Plus un test d'écriture (`test_writer_structure.py`) : un contrat construit avec un changement sort
  `S21.G00.40.*` puis `S21.G00.41.001`, `.019`, `.028`, puis `S21.G00.60`/`70`/`71`.
- [ ] **Step 2-4:** échec ; code ; vert ; toute la suite `tests/unit/dsn_export tests/unit/exports tests/unit/dsn_import` verte.
- [ ] **Step 5: commit** `feat(dsn): le changement de code PCS-ESE est déclaré (bloc S21.G00.41)`.

### Task 10: le changement affiché sur la fiche

Couvert par `texteChangement` (Task 5) et `PcsEseField` (prop `changement`) : vérifier à l'écran.

## Lot 4 — Les 198 fiches

### Task 11: script simulé puis appliqué (hors dépôt)

**Files:** Create `~/dev/eywai-filet/pcs-ese/remplacer_9999.py`, `simuler.sh`, `appliquer.sh`.

- `remplacer_9999.py` : charge une fois les fiches du groupe (`fiches_du_groupe`), prend les fiches à « 9999 »,
  calcule `proposition_pour(..., fiches=...)`, ne retient que `sur=True`.
  Sans `--ecrire` : piège `supabase.table(...).update/insert/upsert/delete` (exception), écrit
  `data/_rapports/pcs-ese/<AAAA-MM-JJ>-simulation.md` (initiales, société, poste, statut, actif/parti, code, règle, raison,
  collègues, ECAP) et `plan.json` (id, ancien, nouveau) ; totaux par règle et par société ; codes ECAP posés.
  Avec `--ecrire --plan plan.json` : vérifie que chaque fiche est encore à « 9999 », sauvegarde la classification en JSON,
  écrit par `update_employee(id, {"classification_conventionnelle": {...classif, "pcs": nouveau}})`, s'arrête à la première
  erreur, journal par initiales, relit à la fin (compte des « 9999 » restants).
- [ ] **Steps:** simuler ; relire la liste ; vérifier qu'aucune écriture n'est partie ; montrer à Alexandre ; attendre
  « lance ~/dev/eywai-filet/pcs-ese/appliquer.sh » ; lancer ; relire.

## Déploiement

- Lots 1 à 3 verts (pytest ciblé + suites DSN, vitest, typecheck) → fusion dans `feat/dsn-octobre`,
  `gh workflow run deploy-test-env.yml --ref feat/dsn-octobre`, e2e fiche puis création sur le site de test.
- Lot 4 après le déploiement du lot 3.
