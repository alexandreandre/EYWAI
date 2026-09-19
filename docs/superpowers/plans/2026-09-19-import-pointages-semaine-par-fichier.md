# Import de pointages : une semaine par fichier — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** déposer plusieurs feuilles de pointage, donner à chaque fichier sa semaine (le sélecteur « Semaine (optionnel) » existant, répété par ligne), et que chaque fichier soit extrait avec sa semaine.

**Architecture:** l'endpoint groupé `start-batch` reçoit une liste de semaines alignée sur les fichiers ; le job groupé passe à chaque fichier sa `week_anchor_date` au parseur, qui l'accepte déjà ; la fusion par salarié et par jour ne change pas, un avertissement signale deux fichiers sur la même semaine. Le dialogue porte l'état `weekByFile` et un sélecteur par ligne ; les helpers purs sont testés en vitest.

**Tech Stack:** FastAPI (multipart `Form`), Pydantic, pytest ; React + shadcn `Select`, vitest.

## Global Constraints

- Spec : `docs/superpowers/specs/2026-09-19-import-pointages-semaine-par-fichier-design.md`.
- Aucun pré-remplissage des semaines ; « Non précisée » par défaut ; mêmes options qu'aujourd'hui (`monthIsoWeekOptions`).
- Pas de nouvel écran, job ni table ; revue et persistance inchangées.
- Tests hermétiques (Supabase et parseur doublés).
- Commits : uniquement à la demande d'Alexandre.

---

### Task 1: Semaines alignées sur les fichiers (back, parties pures)

**Files:**
- Modify: `backend/app/modules/schedules/application/timesheet_import_service.py`
- Test: `backend/tests/unit/schedules/test_import_multi_semaine_par_fichier.py` (créer)

**Interfaces (Produces):**
- `@dataclass(frozen=True) FichierAImporter(filename: str, content: bytes, week_anchor_date: date | None = None)`
- `semaines_alignees(brut: str | None, nb_fichiers: int) -> list[date | None]` — parse le JSON `week_anchor_dates` ; `ValueError` si la longueur diffère ou si une entrée n'est ni `null` ni une date ISO.
- `libelle_fichier(fichier: FichierAImporter) -> str` — `"S28 · nom.pdf"` ou `"nom.pdf"`.
- `avertissement_semaines_en_double(fichiers: list[FichierAImporter]) -> list[str]`.

- [ ] **Step 1: Write the failing tests**

```python
"""Import groupé de pointages : chaque fichier porte sa semaine."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.schedules.application import timesheet_import_service as svc

pytestmark = pytest.mark.unit


def test_les_semaines_sont_lues_dans_l_ordre_des_fichiers():
    assert svc.semaines_alignees('["2026-07-06", null, "2026-07-20"]', 3) == [
        date(2026, 7, 6), None, date(2026, 7, 20)
    ]


def test_sans_liste_aucune_semaine():
    assert svc.semaines_alignees(None, 2) == [None, None]
    assert svc.semaines_alignees("", 2) == [None, None]


def test_une_liste_desalignee_est_refusee():
    with pytest.raises(ValueError, match="une entrée par fichier"):
        svc.semaines_alignees('["2026-07-06"]', 2)


def test_une_date_illisible_est_refusee():
    with pytest.raises(ValueError, match="AAAA-MM-JJ"):
        svc.semaines_alignees('["06/07/2026"]', 1)


def test_le_libelle_nomme_la_semaine():
    f = svc.FichierAImporter("s28.pdf", b"x", date(2026, 7, 6))
    assert svc.libelle_fichier(f) == "S28 · s28.pdf"
    assert svc.libelle_fichier(svc.FichierAImporter("libre.pdf", b"x")) == "libre.pdf"


def test_deux_fichiers_sur_la_meme_semaine_sont_signales():
    fichiers = [
        svc.FichierAImporter("a.pdf", b"x", date(2026, 7, 6)),
        svc.FichierAImporter("b.pdf", b"x", date(2026, 7, 6)),
        svc.FichierAImporter("c.pdf", b"x", date(2026, 7, 13)),
    ]
    avertissements = svc.avertissement_semaines_en_double(fichiers)
    assert avertissements == [
        "S28 : deux fichiers (a.pdf, b.pdf) — le dernier écrase le premier sur les jours communs."
    ]
    assert svc.avertissement_semaines_en_double(fichiers[1:]) == []
```

- [ ] **Step 2: Run to verify RED** — `cd backend && .venv/bin/python -m pytest -q tests/unit/schedules/test_import_multi_semaine_par_fichier.py` → `AttributeError: ... 'semaines_alignees'`

- [ ] **Step 3: Implement** (dans `timesheet_import_service.py`, après les imports ; `json` et `dataclass` importés)

```python
@dataclass(frozen=True)
class FichierAImporter:
    """Un fichier du lot et la semaine que l'utilisateur lui a donnée (lundi ISO)."""

    filename: str
    content: bytes
    week_anchor_date: date_type | None = None


def semaines_alignees(brut: str | None, nb_fichiers: int) -> list[date_type | None]:
    """`week_anchor_dates` du formulaire : une entrée par fichier, date ISO ou null."""
    if not brut or not brut.strip():
        return [None] * nb_fichiers
    try:
        valeurs = json.loads(brut)
    except json.JSONDecodeError as exc:
        raise ValueError("week_anchor_dates doit être une liste JSON.") from exc
    if not isinstance(valeurs, list) or len(valeurs) != nb_fichiers:
        raise ValueError("week_anchor_dates doit avoir une entrée par fichier, dans le même ordre.")
    semaines: list[date_type | None] = []
    for valeur in valeurs:
        if valeur in (None, ""):
            semaines.append(None)
            continue
        try:
            semaines.append(date_type.fromisoformat(str(valeur)))
        except ValueError as exc:
            raise ValueError(f"Semaine illisible : {valeur!r} (format attendu AAAA-MM-JJ).") from exc
    return semaines


def libelle_fichier(fichier: FichierAImporter) -> str:
    if fichier.week_anchor_date is None:
        return fichier.filename
    return f"S{fichier.week_anchor_date.isocalendar()[1]} · {fichier.filename}"


def avertissement_semaines_en_double(fichiers: list[FichierAImporter]) -> list[str]:
    """Deux fichiers sur la même semaine : la fusion garde le dernier sur les jours communs, il faut le dire."""
    par_semaine: dict[date_type, list[str]] = {}
    for f in fichiers:
        if f.week_anchor_date is not None:
            par_semaine.setdefault(f.week_anchor_date, []).append(f.filename)
    return [
        f"S{lundi.isocalendar()[1]} : deux fichiers ({', '.join(noms)}) — le dernier écrase le premier sur les jours communs."
        for lundi, noms in sorted(par_semaine.items())
        if len(noms) > 1
    ]
```

- [ ] **Step 4: GREEN** — même commande, 6 passent.

---

### Task 2: Le job groupé passe sa semaine à chaque fichier

**Files:**
- Modify: `backend/app/modules/schedules/application/timesheet_import_service.py` (`run_multi_timesheet_extraction_job`)
- Modify: `backend/app/modules/schedules/schemas/ai.py` (`TimesheetExtractProgress.current_file`)
- Modify: `backend/app/modules/schedules/api/router.py` (`start-batch` et `/jobs/{id}`)
- Test: `backend/tests/unit/schedules/test_import_multi_semaine_par_fichier.py`

**Interfaces:**
- Consumes: Task 1 ; `parse_with_llm_fallback(..., week_anchor_date=...)` ; `create_batch_from_proposal(...)`.
- Produces: `run_multi_timesheet_extraction_job(job_id: str, files: list[FichierAImporter]) -> None` ; progression `{"phase": "extracting", "files_total", "files_done", "current_file": libelle}` ; `TimesheetExtractProgress.current_file: Optional[str]`.

- [ ] **Step 1: Write the failing test**

```python
def _proposition(nom: str):
    p = MagicMock()
    p.employees = []
    p.warnings = []
    p.model_copy.return_value = p
    p.model_dump.return_value = {"source": nom}
    return p


@patch(f"{svc.__name__}._job_is_terminal", return_value=False)
@patch(f"{svc.__name__}._raise_if_job_cancelled")
@patch(f"{svc.__name__}.create_batch_from_proposal", return_value={"id": "batch-maitre"})
@patch(f"{svc.__name__}.parse_with_llm_fallback")
@patch(f"{svc.__name__}._update_job")
@patch(f"{svc.__name__}.get_import_job")
def test_chaque_fichier_est_extrait_avec_sa_semaine(mock_job, mock_update, mock_parse, *_):
    mock_job.return_value = {
        "id": "job-1", "status": "extracting", "company_id": "co", "user_id": "u",
        "request_json": {"year": 2026, "month": 7, "employees": [], "single_employee": False, "document_scope": "weekly"},
    }
    mock_parse.side_effect = [(_proposition("a"), "b1"), (_proposition("b"), "b2")]
    fichiers = [
        svc.FichierAImporter("s28.pdf", b"1", date(2026, 7, 6)),
        svc.FichierAImporter("s29.pdf", b"2", date(2026, 7, 13)),
    ]

    svc.run_multi_timesheet_extraction_job("job-1", fichiers)

    semaines = [appel.kwargs["week_anchor_date"] for appel in mock_parse.call_args_list]
    assert semaines == [date(2026, 7, 6), date(2026, 7, 13)]
    libelles = [
        appel.args[1]["progress_json"]["current_file"]
        for appel in mock_update.call_args_list
        if "current_file" in appel.args[1].get("progress_json", {})
    ]
    assert libelles == ["S28 · s28.pdf", "S29 · s29.pdf"]


@patch(f"{svc.__name__}._job_is_terminal", return_value=False)
@patch(f"{svc.__name__}._raise_if_job_cancelled")
@patch(f"{svc.__name__}.create_batch_from_proposal", return_value={"id": "batch-maitre"})
@patch(f"{svc.__name__}.parse_with_llm_fallback")
@patch(f"{svc.__name__}._update_job")
@patch(f"{svc.__name__}.get_import_job")
def test_la_meme_semaine_deux_fois_est_signalee_dans_la_proposition(mock_job, mock_update, mock_parse, mock_batch, *_):
    mock_job.return_value = {
        "id": "job-1", "status": "extracting", "company_id": "co", "user_id": "u",
        "request_json": {"year": 2026, "month": 7, "employees": []},
    }
    mock_parse.side_effect = [(_proposition("a"), "b1"), (_proposition("b"), "b2")]
    fichiers = [svc.FichierAImporter(n, b"x", date(2026, 7, 6)) for n in ("a.pdf", "b.pdf")]

    svc.run_multi_timesheet_extraction_job("job-1", fichiers)

    fusion = mock_batch.call_args.kwargs["proposal"]
    assert any("S28 : deux fichiers" in w for w in fusion.warnings)
```

- [ ] **Step 2: RED** — `TypeError`/`AttributeError` sur `week_anchor_date` / `current_file`.

- [ ] **Step 3: Implement**

`run_multi_timesheet_extraction_job(job_id, files: List[FichierAImporter])` : dans la boucle, `for i, fichier in enumerate(files)` ; progression `"current_file": libelle_fichier(fichier)` ; `parse_with_llm_fallback(..., content=fichier.content, filename=fichier.filename, ..., week_anchor_date=fichier.week_anchor_date, ...)` ; après `merged = _merge_proposals(proposals)` :
```python
        doublons = avertissement_semaines_en_double(files)
        if doublons:
            merged = merged.model_copy(update={"warnings": list(merged.warnings) + doublons})
```
`filename=f"{len(files)} fichiers"` inchangé.

`schemas/ai.py` : `current_file: Optional[str] = None` dans `TimesheetExtractProgress`.

`router.py`, `/jobs/{job_id}` : après le bloc `files_total`, `if progress_raw.get("current_file"): progress = progress.model_copy(update={"current_file": str(progress_raw["current_file"])})`.

`router.py`, `start-batch` : nouveau `week_anchor_dates: str = Form("[]")` ;
```python
    contenus = [(f.filename or "document.pdf", data) for f in files if (data := await f.read())]
    try:
        semaines = semaines_alignees(week_anchor_dates, len(contenus))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    fichiers = [FichierAImporter(nom, data, semaine) for (nom, data), semaine in zip(contenus, semaines)]
    request_json = {..., "files": [{"filename": f.filename, "week_anchor_date": f.week_anchor_date.isoformat() if f.week_anchor_date else None} for f in fichiers]}
    ... create_import_job(file_content=fichiers[0].content, ...)
    runner.enqueue(run_multi_timesheet_extraction_job, job_id, fichiers)
```
(`await` dans une compréhension : écrire la boucle explicitement.)

- [ ] **Step 4: GREEN** — `cd backend && .venv/bin/python -m pytest -q tests/unit/schedules` ; ruff sur les trois fichiers.

---

### Task 3: Front — helpers purs de l'attribution des semaines

**Files:**
- Create: `frontend/src/components/schedules/assisted-fill/importWeekAssignments.ts`
- Test: `frontend/src/components/schedules/assisted-fill/importWeekAssignments.test.ts`

**Interfaces (Produces):**
- `type WeekByFile = Record<string, string>` (clé : `file.name`, valeur : lundi ISO ou absent)
- `weeksAlignedWithFiles(files: { name: string }[], weekByFile: WeekByFile): (string | null)[]`
- `filesMissingWeek(files, weekByFile): string[]`
- `duplicateWeekLabels(files, weekByFile, options: { value: string; week: number }[]): string[]` → `["S28"]`

- [ ] **Step 1: Write the failing tests**

```ts
import { describe, expect, it } from 'vitest';

import {
  duplicateWeekLabels,
  filesMissingWeek,
  weeksAlignedWithFiles,
} from './importWeekAssignments';

const files = [{ name: 'a.pdf' }, { name: 'b.pdf' }, { name: 'c.pdf' }];
const options = [
  { value: '2026-07-06', week: 28 },
  { value: '2026-07-13', week: 29 },
];

describe('importWeekAssignments', () => {
  it('aligne les semaines sur les fichiers, null quand non précisée', () => {
    expect(weeksAlignedWithFiles(files, { 'a.pdf': '2026-07-06', 'c.pdf': '2026-07-13' })).toEqual([
      '2026-07-06',
      null,
      '2026-07-13',
    ]);
  });

  it('liste les fichiers sans semaine', () => {
    expect(filesMissingWeek(files, { 'a.pdf': '2026-07-06' })).toEqual(['b.pdf', 'c.pdf']);
  });

  it('signale une semaine donnée à deux fichiers', () => {
    expect(
      duplicateWeekLabels(files, { 'a.pdf': '2026-07-06', 'b.pdf': '2026-07-06' }, options),
    ).toEqual(['S28']);
    expect(duplicateWeekLabels(files, { 'a.pdf': '2026-07-06' }, options)).toEqual([]);
  });
});
```

- [ ] **Step 2: RED** — `cd frontend && npx vitest run src/components/schedules/assisted-fill/importWeekAssignments.test.ts`

- [ ] **Step 3: Implement**

```ts
export type WeekByFile = Record<string, string>;

export function weeksAlignedWithFiles(
  files: { name: string }[],
  weekByFile: WeekByFile,
): (string | null)[] {
  return files.map((f) => weekByFile[f.name] || null);
}

export function filesMissingWeek(files: { name: string }[], weekByFile: WeekByFile): string[] {
  return files.filter((f) => !weekByFile[f.name]).map((f) => f.name);
}

export function duplicateWeekLabels(
  files: { name: string }[],
  weekByFile: WeekByFile,
  options: { value: string; week: number }[],
): string[] {
  const count = new Map<string, number>();
  for (const f of files) {
    const value = weekByFile[f.name];
    if (value) count.set(value, (count.get(value) ?? 0) + 1);
  }
  return options.filter((o) => (count.get(o.value) ?? 0) > 1).map((o) => `S${o.week}`);
}
```

- [ ] **Step 4: GREEN.**

---

### Task 4: Front — un sélecteur par fichier, et les deux chemins passent la semaine

**Files:**
- Modify: `frontend/src/api/calendar.ts` (`ExtractTimesheetOptions.weekAnchorDates?: (string | null)[]` ; `startTimesheetExtractBatch` ajoute `week_anchor_dates` ; `TimesheetExtractProgress.current_file?: string`)
- Modify: `frontend/src/components/schedules/assisted-fill/PointageImportDialog.tsx`
- Modify: `frontend/src/hooks/pointageImportJobStore.ts` (`progressLabel`)

- [ ] **Step 1:** `calendar.ts` — dans `startTimesheetExtractBatch`, après `document_scope` :
```ts
  if (options.weekAnchorDates) {
    formData.append('week_anchor_dates', JSON.stringify(options.weekAnchorDates));
  }
```
- [ ] **Step 2:** `PointageImportDialog.tsx` — remplacer `const [weekAnchorDate, setWeekAnchorDate] = useState('')` par `const [weekByFile, setWeekByFile] = useState<WeekByFile>({})` ; `reset()` remet `{}` ; supprimer le bloc `<div className="space-y-1.5"><Label htmlFor="week-anchor">Semaine…` de l'en-tête ; la liste des fichiers devient :
```tsx
{files.length > 0 && (
  <ul className="max-h-40 overflow-y-auto rounded border text-xs divide-y">
    {files.map((f) => (
      <li key={f.name} className="flex items-center gap-2 px-2 py-1">
        <span className="min-w-0 flex-1 truncate">{f.name}</span>
        {(documentScope === 'weekly' || documentScope === 'auto') && (
          <Select
            value={weekByFile[f.name] || NO_WEEK}
            onValueChange={(v) =>
              setWeekByFile((prev) => {
                const next = { ...prev };
                if (v === NO_WEEK) delete next[f.name];
                else next[f.name] = v;
                return next;
              })
            }
          >
            <SelectTrigger className="h-7 w-56" aria-label={`Semaine de ${f.name}`}>
              <SelectValue placeholder={documentScope === 'weekly' ? 'Semaine *' : 'Semaine (optionnel)'} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NO_WEEK}>Non précisée</SelectItem>
              {weekOptions.map((w) => (
                <SelectItem key={w.value} value={w.value}>{w.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        <button type="button" onClick={() => removeFile(f.name)} className="text-muted-foreground hover:text-foreground" aria-label={`Retirer ${f.name}`}>
          <X className="h-3.5 w-3.5" />
        </button>
      </li>
    ))}
  </ul>
)}
{duplicates.length > 0 && (
  <p className="text-[11px] text-amber-700">
    {duplicates.join(', ')} attribuée{duplicates.length > 1 ? 's' : ''} à plusieurs fichiers : le dernier écrasera le premier sur les jours communs.
  </p>
)}
```
avec `const duplicates = useMemo(() => duplicateWeekLabels(files, weekByFile, weekOptions), [files, weekByFile, weekOptions])` et
```ts
const removeFile = (name: string) => {
  setFiles((prev) => prev.filter((f) => f.name !== name));
  setWeekByFile((prev) => { const next = { ...prev }; delete next[name]; return next; });
};
```
Validation dans `analyzeFiles` :
```ts
if (documentScope === 'weekly') {
  const manquants = filesMissingWeek(files, weekByFile);
  if (manquants.length > 0) {
    toast({ title: 'Semaine à préciser', description: `Relevé hebdomadaire sans dates explicites : choisissez la semaine (S27, S28…) pour ${manquants.join(', ')}.`, variant: 'destructive' });
    return;
  }
}
```
Chemin groupé : `startTimesheetExtractBatch(files, year, month, roster, { singleEmployee, documentScope, weekAnchorDates: weeksAlignedWithFiles(files, weekByFile) })`.
Chemin fichier par fichier : `weekAnchorDate: weekByFile[file.name] || null`.
Import de `X` depuis `lucide-react` (déjà utilisé ailleurs dans le dossier) et des helpers de Task 3.

- [ ] **Step 3:** `pointageImportJobStore.ts` — dans `progressLabel`, quand `total > 0` :
```ts
    const unit = progress.files_total ? 'fichier' : 'page';
    const courant = progress.current_file ? ` — ${progress.current_file}` : '';
    return `${done}/${total} ${unit}${total > 1 ? 's' : ''}${courant} — analyse IA…`;
```
- [ ] **Step 4:** `cd frontend && npx vitest run src/components/schedules/assisted-fill && npx tsc --noEmit -p tsconfig.json && npm run lint -- --max-warnings=0 src/components/schedules/assisted-fill src/api/calendar.ts src/hooks/pointageImportJobStore.ts` (adapter aux scripts du dépôt).

---

### Task 5: Vérification bout en bout et remise

- [ ] Backend : `APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key .venv/bin/python -m pytest -q tests/unit` vert ; ruff propre.
- [ ] Frontend : `npm test` vert, build (`npm run build`) vert.
- [ ] Sur l'environnement de test (après déploiement à la demande d'Alexandre) : déposer trois PDF de pointage Colorplast, attribuer S27/S28/S29, lancer ; la progression nomme « S28 · … » ; la revue montre un seul lot ; la persistance range les jours de juin de S27 dans juin.
- [ ] Commit à la demande d'Alexandre : `feat(pointages): import en masse, une semaine par fichier`.
