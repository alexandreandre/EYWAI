# Période à saisir pour la paie — pas 2, l'écran : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Montrer à la personne qui génère ce qui manque exactement (dates, fenêtre), lui montrer la fenêtre des variables partout où elle génère, et signaler les bulletins calculés sur une fenêtre qui a changé depuis.

**Architecture:** Le backend expose déjà `fenetre`, `jours_manquants`, `jours_informatifs` sur le 422 et l'anomalie pré-paie (pas 1). Ce pas ajoute côté backend le repérage des bulletins calculés sur une autre fenêtre (dans `apercu_fenetre` et comme anomalie pré-paie `fenetre_modifiee`), et côté front : l'extraction tolérante des détails du refus, une lib pure qui regroupe des dates ISO par semaine, un composant de liste réutilisé par les deux dialogues de refus, le bloc fenêtre en lecture dans la régénération unitaire, et les libellés/types pré-paie.

**Tech Stack:** Python 3.12 / FastAPI / pytest (backend, `backend/.venv/bin/python`) ; React + TypeScript + vitest + eslint (frontend, pas de testing-library : la logique va dans des libs pures testées, les composants restent minces).

Spec : `docs/superpowers/specs/2026-09-20-periode-a-saisir-pour-la-paie-design.md` (§ 4 et 5). Pas 1 : `2026-09-20-periode-a-saisir-socle-backend.md`.

## Global Constraints

- Champs d'API additifs uniquement ; un front ancien continue de marcher.
- La fenêtre reste un réglage société-mois : aucun champ de fenêtre dans la requête de génération.
- Aucun commit sans demande explicite d'Alexandre.
- Front : `cd frontend && npx vitest run <fichier>` ; `npx eslint <fichiers>` ; `npx tsc --noEmit -p .` (trois erreurs préexistantes hors périmètre : `SalaryAdvances.tsx`, `SuiviIJSS.tsx`, `YearCalendarView.tsx`).
- Backend : `cd backend && .venv/bin/python -m pytest tests/unit -q -p no:warnings` ; deux rouges d'environnement connus.

---

### Task 1: Backend — les bulletins calculés sur une autre fenêtre

**Files:**
- Modify: `backend/app/modules/payroll/application/periode_variables_service.py`
- Modify: `backend/app/modules/payroll_variables/schemas/requests.py:69-77` (`PeriodeVariablesSchema`)
- Test: `backend/tests/unit/payroll/test_bulletins_sur_une_autre_fenetre.py`

**Interfaces:**
- Produces: `bulletin_hors_fenetre(ligne: dict, fenetre: FenetreVariables) -> bool` (pur) ; `bulletins_sur_une_autre_fenetre(company_id, annee, mois, fenetre) -> list[dict]` (lignes `{employee_id, status, debut, fin}`) ; `apercu_fenetre(...)` gagne `bulletins_a_regenerer: int` et `employes_a_regenerer: list[str]`.

- [ ] **Step 1: Tests rouges**

```python
"""Un bulletin garde la fenêtre sur laquelle il a été calculé (en-tête). Quand la
fenêtre du mois change, ces bulletins sont à régénérer — on les nomme."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.shared.domain.periode_variables import FenetreVariables

pytestmark = pytest.mark.unit

MODULE = "app.modules.payroll.application.periode_variables_service"
FENETRE = FenetreVariables(debut=date(2026, 6, 22), fin=date(2026, 7, 26), origine="regle")


def test_un_bulletin_calcule_sur_la_meme_fenetre_n_est_pas_a_regenerer():
    from app.modules.payroll.application.periode_variables_service import bulletin_hors_fenetre

    assert bulletin_hors_fenetre({"debut": "2026-06-22", "fin": "2026-07-26"}, FENETRE) is False


def test_un_bulletin_calcule_sur_une_autre_fin_est_a_regenerer():
    from app.modules.payroll.application.periode_variables_service import bulletin_hors_fenetre

    assert bulletin_hors_fenetre({"debut": "2026-06-22", "fin": "2026-07-19"}, FENETRE) is True


def test_un_bulletin_sans_fenetre_en_en_tete_ou_importe_est_ignore():
    from app.modules.payroll.application.periode_variables_service import bulletin_hors_fenetre

    assert bulletin_hors_fenetre({"debut": None, "fin": None}, FENETRE) is False
    assert bulletin_hors_fenetre({"debut": "2026-06-01", "fin": "2026-06-30", "origine": "importe"}, FENETRE) is False


@patch(f"{MODULE}.supabase")
def test_le_service_lit_les_bulletins_du_mois_et_rend_ceux_a_regenerer(mock_supabase):
    from app.modules.payroll.application.periode_variables_service import (
        bulletins_sur_une_autre_fenetre,
    )

    chaine = mock_supabase.table.return_value.select.return_value.match.return_value
    chaine.execute.return_value = MagicMock(
        data=[
            {"employee_id": "e1", "status": "brouillon", "origine": "calcule", "debut": "2026-06-22", "fin": "2026-07-19"},
            {"employee_id": "e2", "status": "valide", "origine": "calcule", "debut": "2026-06-22", "fin": "2026-07-26"},
            {"employee_id": "e3", "status": "valide", "origine": "importe", "debut": None, "fin": None},
        ]
    )

    lignes = bulletins_sur_une_autre_fenetre("c1", 2026, 7, FENETRE)

    assert [l["employee_id"] for l in lignes] == ["e1"]
    select = mock_supabase.table.return_value.select.call_args.args[0]
    assert "payslip_data->en_tete->>date_debut_variables" in select


@patch(f"{MODULE}.bulletins_sur_une_autre_fenetre")
@patch(f"{MODULE}.resoudre_fenetre_variables", return_value=FENETRE)
def test_l_apercu_compte_les_bulletins_a_regenerer(mock_fenetre, mock_bulletins):
    from app.modules.payroll.application.periode_variables_service import apercu_fenetre

    mock_bulletins.return_value = [{"employee_id": "e1"}, {"employee_id": "e4"}]

    apercu = apercu_fenetre("c1", 2026, 7)

    assert apercu["bulletins_a_regenerer"] == 2
    assert apercu["employes_a_regenerer"] == ["e1", "e4"]
```

- [ ] **Step 2: Vérifier le rouge**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/payroll/test_bulletins_sur_une_autre_fenetre.py -q -p no:warnings`
Expected: `ImportError: cannot import name 'bulletin_hors_fenetre'`.

- [ ] **Step 3: Implémenter**

Dans `periode_variables_service.py`, après `enregistrer_fenetre_variables` :

```python
#: Colonnes du bulletin utiles ici : la fenêtre sur laquelle il a été calculé
#: est dans son en-tête (`bulletin.py`), en ISO.
_SELECT_BULLETINS = (
    "employee_id, status, origine, "
    "debut:payslip_data->en_tete->>date_debut_variables, "
    "fin:payslip_data->en_tete->>date_fin_variables"
)


def bulletin_hors_fenetre(ligne: dict[str, Any], fenetre: FenetreVariables) -> bool:
    """Vrai si ce bulletin a été calculé sur une autre fenêtre que celle du mois.

    Un bulletin importé (reprise de paie) ou sans fenêtre en en-tête (ancien
    moteur) n'est pas concerné : il n'a pas été calculé par nous sur une fenêtre.
    """
    if (ligne.get("origine") or "calcule") == "importe":
        return False
    debut, fin = ligne.get("debut"), ligne.get("fin")
    if not debut or not fin:
        return False
    return (str(debut)[:10], str(fin)[:10]) != (fenetre.debut.isoformat(), fenetre.fin.isoformat())


def bulletins_sur_une_autre_fenetre(
    company_id: str, annee: int, mois: int, fenetre: FenetreVariables
) -> list[dict[str, Any]]:
    """Les bulletins du mois à régénérer parce que la fenêtre a changé depuis."""
    resp = (
        supabase.table("payslips")
        .select(_SELECT_BULLETINS)
        .match({"company_id": str(company_id), "year": int(annee), "month": int(mois)})
        .execute()
    )
    return [ligne for ligne in (resp.data if resp else None) or [] if bulletin_hors_fenetre(ligne, fenetre)]
```

et `apercu_fenetre` :

```python
def apercu_fenetre(company_id: str, annee: int, mois: int) -> dict[str, Any]:
    """Charge utile de l'API : la fenêtre plus de quoi l'afficher sans recalcul."""
    fenetre = resoudre_fenetre_variables(str(company_id), annee, mois)
    debut_mois, fin_mois = bornes_mois_civil(annee, mois)
    a_regenerer = bulletins_sur_une_autre_fenetre(str(company_id), annee, mois, fenetre)
    return {
        "debut": fenetre.debut.isoformat(),
        "fin": fenetre.fin.isoformat(),
        "origine": fenetre.origine,
        "semaines": semaines_iso(fenetre.debut, fenetre.fin),
        "mois_civil": [debut_mois.isoformat(), fin_mois.isoformat()],
        "report_debut": (fenetre.fin + timedelta(days=1)).isoformat(),
        # Bulletins du mois calculés sur une autre fenêtre : à régénérer.
        "bulletins_a_regenerer": len(a_regenerer),
        "employes_a_regenerer": [str(ligne["employee_id"]) for ligne in a_regenerer],
    }
```

`__all__` : ajouter `"bulletin_hors_fenetre"`, `"bulletins_sur_une_autre_fenetre"`.

`PeriodeVariablesSchema` :

```python
class PeriodeVariablesSchema(BaseModel):
    """Fenêtre des variables d'un mois, telle qu'affichée au lancement de paie."""

    debut: str
    fin: str
    origine: str
    semaines: list[int]
    mois_civil: list[str]
    report_debut: str
    #: Bulletins du mois calculés sur une autre fenêtre (à régénérer).
    bulletins_a_regenerer: int = 0
    employes_a_regenerer: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Vérifier le vert**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/payroll/test_bulletins_sur_une_autre_fenetre.py tests/unit/payroll -q -p no:warnings -k "fenetre or periode or preflight" && .venv/bin/ruff check app/modules/payroll/application/periode_variables_service.py app/modules/payroll_variables/schemas/requests.py`
Expected: verts. Vérifier aussi qu'aucun test existant ne moque `apercu_fenetre` en supposant six clés exactes (`grep -rn "apercu_fenetre" backend/tests`).

---

### Task 2: Backend — l'anomalie pré-paie `fenetre_modifiee`

**Files:**
- Modify: `backend/app/modules/payroll/schemas/preflight_responses.py:10-17, 71-80`
- Modify: `backend/app/modules/payroll/application/preflight_anomalies.py` (`_build_counts`, `build_preflight_anomalies`)
- Test: `backend/tests/unit/payroll/test_preflight_anomalies.py`

**Interfaces:**
- Consumes: `resoudre_fenetre_variables`, `bulletins_sur_une_autre_fenetre` (module `periode_variables_service`).
- Produces: anomalie `type="fenetre_modifiee"`, `severity="a_verifier"`, `fenetre` = fenêtre du mois, `message` = « Bulletin calculé sur la fenêtre 22/06 → 19/07 ; celle du mois est 22/06 → 26/07 : à régénérer. » ; `counts.fenetre_modifiee`.

- [ ] **Step 1: Test rouge** (classe `TestPeriodeASaisir`, même jeu de doublures que les tests du pas 1)

```python
    @patch("app.modules.payroll.application.preflight_anomalies.bulletins_sur_une_autre_fenetre")
    @patch(
        "app.modules.schedules.infrastructure.punch_accounting_repository.list_overtime_reviews",
        return_value=[],
    )
    @patch("app.modules.modulation.infrastructure.repository.get_modulation_settings")
    @patch("app.modules.payroll.application.preflight_anomalies.badgeuse_service.get_company_period_summary")
    @patch("app.modules.payroll.application.preflight_anomalies.preflight_repository.list_resolutions")
    @patch("app.modules.payroll.application.preflight_anomalies.supabase")
    def test_un_bulletin_calcule_sur_une_autre_fenetre_est_a_regenerer(
        self, mock_supabase, mock_resolutions, mock_badgeuse, mock_mod_settings, _mock_punch, mock_bulletins
    ):
        mock_mod_settings.return_value = _default_mod_settings()
        mock_resolutions.return_value = []
        mock_badgeuse.return_value = {}
        _configure_supabase(
            mock_supabase,
            schedules=[
                {
                    "employee_id": EMP_ID,
                    "planned_calendar": {"calendrier_prevu": _full_june_2026_planned()},
                    "actual_hours": {"calendrier_reel": _full_june_2026_actual()},
                }
            ],
        )
        mock_bulletins.return_value = [
            {"employee_id": EMP_ID, "status": "brouillon", "debut": "2026-06-01", "fin": "2026-06-21"}
        ]

        with patch(
            "app.modules.absences.infrastructure.repository.absence_repository.list_validated_for_employees",
            return_value=[],
        ):
            result = preflight_anomalies.build_preflight_anomalies(COMPANY_ID, 2026, 6)

        anomalie = next(a for a in result.anomalies if a.type == "fenetre_modifiee")
        assert anomalie.severity == "a_verifier"
        assert "01/06 → 21/06" in anomalie.message and "01/06 → 30/06" in anomalie.message
        assert anomalie.fenetre["fin"] == "2026-06-30"
        assert result.counts.fenetre_modifiee == 1
```

- [ ] **Step 2: Vérifier le rouge**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/payroll/test_preflight_anomalies.py -q -p no:warnings -k autre_fenetre`
Expected: `AttributeError: ... does not have the attribute 'bulletins_sur_une_autre_fenetre'`.

- [ ] **Step 3: Implémenter**

`preflight_responses.py` :

```python
PreflightAnomalyType = Literal[
    "ecart_heures",
    "heures_non_saisies",
    "pointage",
    "conflit_absence",
    "hs_routing_pending",
    "hs_pointage_a_valider",
    "fenetre_modifiee",
]
```

et dans `PreflightAnomalyCounts` : `fenetre_modifiee: int = 0`.

`preflight_anomalies.py` — imports :

```python
from app.modules.payroll.application.periode_variables_service import (
    bulletins_sur_une_autre_fenetre,
    resoudre_fenetre_variables,
)
from app.shared.domain.periode_variables import semaines_iso
```

`_build_counts` : ajouter `elif a.type == "fenetre_modifiee": counts.fenetre_modifiee += 1`.

Dans `build_preflight_anomalies`, après la boucle des salariés et avant l'assemblage des compteurs :

```python
    # Bulletins du mois calculés sur une fenêtre qui a changé depuis : la paie
    # n'est plus celle que la gestionnaire croit avoir lancée.
    fenetre = resoudre_fenetre_variables(company_id, year, month)
    for ligne in bulletins_sur_une_autre_fenetre(company_id, year, month, fenetre):
        eid = str(ligne.get("employee_id") or "")
        emp = emp_by_id.get(eid)
        if not emp:
            continue
        ancienne = f"{str(ligne.get('debut'))[8:10]}/{str(ligne.get('debut'))[5:7]} → {str(ligne.get('fin'))[8:10]}/{str(ligne.get('fin'))[5:7]}"
        anomalies.append(
            PreflightAnomaly(
                id=_anomaly_id(eid, "fenetre_modifiee"),
                employee_id=eid,
                employee_name=_employee_name(emp.get("first_name"), emp.get("last_name")),
                team_id=str(emp["team_id"]) if emp.get("team_id") else None,
                type="fenetre_modifiee",
                severity="a_verifier",
                status="a_traiter",
                is_forfait_jour=is_forfait_jour(emp.get("statut"), emp.get("is_forfait_jour")),
                fenetre={
                    "debut": fenetre.debut.isoformat(),
                    "fin": fenetre.fin.isoformat(),
                    "semaines": semaines_iso(fenetre.debut, fenetre.fin),
                    "origine": fenetre.origine,
                },
                message=(
                    f"Bulletin calculé sur la fenêtre {ancienne} ; celle du mois est "
                    f"{fenetre.debut:%d/%m} → {fenetre.fin:%d/%m} : à régénérer."
                ),
            )
        )
```

Les résolutions (`_merge_resolution`) s'appliquent comme aux autres types : une justification possible, pas obligatoire.

- [ ] **Step 4: Vérifier le vert**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/payroll/test_preflight_anomalies.py -q -p no:warnings && .venv/bin/ruff check app/modules/payroll`
Expected: verts. Les tests existants de la classe doivent aussi moquer `bulletins_sur_une_autre_fenetre` (retour `[]`) : l'ajouter au `autouse` du pas 1 (`patch("app.modules.payroll.application.preflight_anomalies.bulletins_sur_une_autre_fenetre", return_value=[])`) pour ne pas toucher chaque test.

---

### Task 3: Front — extraction des détails du refus et regroupement des jours par semaine

**Files:**
- Modify: `frontend/src/features/payroll/utils/generationGuards.ts`
- Create: `frontend/src/features/payroll/lib/joursASaisir.ts`
- Test: `frontend/src/features/payroll/utils/generationGuards.test.ts`, `frontend/src/features/payroll/lib/joursASaisir.test.ts`

**Interfaces:**
- Produces: `RefusalFenetre = { debut: string; fin: string; semaines: number[]; origine: string }` ; `RefusalDetails = { fenetre: RefusalFenetre | null; joursManquants: string[]; joursInformatifs: string[] }` ; `GenerationRefusal.details?: RefusalDetails` ; `regrouperParSemaine(iso: string[]) -> { semaine: number; annee: number; libelle: string }[]` (« S26 : 22/06–26/06 »), `libellePlages(iso: string[]) -> string` (« 22/06–26/06, 29/06–30/06 »).

- [ ] **Step 1: Tests rouges**

`generationGuards.test.ts`, dans `describe('extractGenerationRefusal')` :

```ts
  it('porte les détails de la période à saisir quand le backend les donne', () => {
    const error = httpError(422, {
      code: 'calendrier_incomplet',
      message: '07/2026 — 7 jour(s) à saisir dans la fenêtre des variables (22/06 → 26/07) : 22/06–26/06, 29/06–30/06.',
      fenetre: { debut: '2026-06-22', fin: '2026-07-26', semaines: [26, 27, 28, 29, 30], origine: 'regle' },
      jours_manquants: ['2026-06-22', '2026-06-23'],
      jours_informatifs: ['2026-07-27'],
    });
    expect(extractGenerationRefusal(error)?.details).toEqual({
      fenetre: { debut: '2026-06-22', fin: '2026-07-26', semaines: [26, 27, 28, 29, 30], origine: 'regle' },
      joursManquants: ['2026-06-22', '2026-06-23'],
      joursInformatifs: ['2026-07-27'],
    });
  });

  it('reste compatible avec un 422 sans détails (backend ancien)', () => {
    const error = httpError(422, { code: 'calendrier_incomplet', message: 'incomplet' });
    expect(extractGenerationRefusal(error)?.details).toBeUndefined();
  });
```

`joursASaisir.test.ts` :

```ts
import { describe, expect, it } from 'vitest';
import { libellePlages, regrouperParSemaine } from './joursASaisir';

describe('regrouperParSemaine', () => {
  it('regroupe des dates ISO par semaine ISO, avec des plages lisibles', () => {
    expect(
      regrouperParSemaine(['2026-06-22', '2026-06-23', '2026-06-24', '2026-06-25', '2026-06-26', '2026-06-29', '2026-06-30', '2026-07-02']),
    ).toEqual([
      { semaine: 26, annee: 2026, libelle: 'S26 : 22/06–26/06' },
      { semaine: 27, annee: 2026, libelle: 'S27 : 29/06–30/06, 02/07' },
    ]);
  });

  it('rend une liste vide sans dates', () => {
    expect(regrouperParSemaine([])).toEqual([]);
  });
});

describe('libellePlages', () => {
  it('écrit les plages comme le serveur', () => {
    expect(libellePlages(['2026-07-27', '2026-07-28', '2026-07-29', '2026-07-30', '2026-07-31'])).toBe('27/07–31/07');
    expect(libellePlages(['2026-07-10'])).toBe('10/07');
  });
});
```

- [ ] **Step 2: Vérifier le rouge**

Run: `cd frontend && npx vitest run src/features/payroll/utils/generationGuards.test.ts src/features/payroll/lib/joursASaisir.test.ts`
Expected: le premier échoue sur `details` (`undefined`), le second sur le module absent.

- [ ] **Step 3: Implémenter**

`joursASaisir.ts` :

```ts
/**
 * Les jours à saisir, lus par la gestionnaire de paie : en semaines et en
 * plages (« S26 : 22/06–26/06 »), comme le serveur les nomme dans son 422.
 */

import { getISOWeek, getISOWeekYear, parseISO } from 'date-fns';

const jjmm = (iso: string): string => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;

const lendemain = (iso: string): string => {
  const d = parseISO(iso);
  d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0, 10);
};

/** Plages de jours consécutifs : `[[debut, fin], ...]`, dates ISO triées. */
export function plages(iso: string[]): [string, string][] {
  const out: [string, string][] = [];
  for (const jour of [...iso].sort()) {
    const derniere = out[out.length - 1];
    if (derniere && lendemain(derniere[1]) === jour) derniere[1] = jour;
    else out.push([jour, jour]);
  }
  return out;
}

/** « 22/06–26/06, 29/06–30/06 » — la même écriture que le message du serveur. */
export function libellePlages(iso: string[]): string {
  return plages(iso)
    .map(([a, b]) => (a === b ? jjmm(a) : `${jjmm(a)}–${jjmm(b)}`))
    .join(', ');
}

export interface SemaineASaisir {
  semaine: number;
  annee: number;
  libelle: string;
}

/** Une ligne par semaine ISO : « S26 : 22/06–26/06 ». */
export function regrouperParSemaine(iso: string[]): SemaineASaisir[] {
  const parSemaine = new Map<string, { semaine: number; annee: number; jours: string[] }>();
  for (const jour of [...iso].sort()) {
    const d = parseISO(jour);
    const semaine = getISOWeek(d);
    const annee = getISOWeekYear(d);
    const cle = `${annee}-${semaine}`;
    const entree = parSemaine.get(cle) ?? { semaine, annee, jours: [] };
    entree.jours.push(jour);
    parSemaine.set(cle, entree);
  }
  return [...parSemaine.values()].map(({ semaine, annee, jours }) => ({
    semaine,
    annee,
    libelle: `S${semaine} : ${libellePlages(jours)}`,
  }));
}
```

`generationGuards.ts` — types et extraction :

```ts
export type RefusalFenetre = {
  debut: string;
  fin: string;
  semaines: number[];
  origine: string;
};

/** Détails de la période à saisir joints au 422 `calendrier_incomplet` (backend ≥ 20/09/2026). */
export type RefusalDetails = {
  fenetre: RefusalFenetre | null;
  joursManquants: string[];
  joursInformatifs: string[];
};

export type GenerationRefusal = {
  code: GenerationRefusalCode;
  message: string;
  details?: RefusalDetails;
};

const isoDates = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : [];

function extractRefusalDetails(detail: Record<string, unknown>): RefusalDetails | undefined {
  const brut = detail as {
    fenetre?: unknown;
    jours_manquants?: unknown;
    jours_informatifs?: unknown;
  };
  if (!('jours_manquants' in brut) && !('fenetre' in brut)) return undefined;
  let fenetre: RefusalFenetre | null = null;
  if (brut.fenetre && typeof brut.fenetre === 'object') {
    const f = brut.fenetre as Partial<RefusalFenetre>;
    if (typeof f.debut === 'string' && typeof f.fin === 'string') {
      fenetre = {
        debut: f.debut,
        fin: f.fin,
        semaines: Array.isArray(f.semaines) ? f.semaines.filter((s): s is number => typeof s === 'number') : [],
        origine: typeof f.origine === 'string' ? f.origine : 'regle',
      };
    }
  }
  return {
    fenetre,
    joursManquants: isoDates(brut.jours_manquants),
    joursInformatifs: isoDates(brut.jours_informatifs),
  };
}
```

et dans `extractGenerationRefusal`, remplacer le `return` final par :

```ts
  const cleaned =
    typeof message === 'string' ? sanitizeBackendMessage(message) : null;
  const refusal: GenerationRefusal = {
    code: refusalCode,
    message: cleaned ?? REFUSAL_FALLBACK_MESSAGES[refusalCode],
  };
  if (refusalCode === 'calendrier_incomplet') {
    const details = extractRefusalDetails(detail as Record<string, unknown>);
    if (details) refusal.details = details;
  }
  return refusal;
```

Le test existant `toEqual({ code, message })` reste vrai : sans détails, la clé `details` n'existe pas.

- [ ] **Step 4: Vérifier le vert**

Run: `cd frontend && npx vitest run src/features/payroll/utils/generationGuards.test.ts src/features/payroll/lib/joursASaisir.test.ts && npx eslint src/features/payroll/utils/generationGuards.ts src/features/payroll/lib/joursASaisir.ts`
Expected: verts, lint propre.

---

### Task 4: Front — la liste des jours dans les deux dialogues de refus, la fenêtre dans la régénération unitaire

**Files:**
- Create: `frontend/src/features/payroll/components/JoursASaisirListe.tsx`
- Modify: `frontend/src/features/payroll/components/PayrollGenerationRefusalDialog.tsx`
- Modify: `frontend/src/components/payslip-edit/RegeneratePayslipButton.tsx`
- Modify: `frontend/src/features/payroll/components/BlocPeriodeVariables.tsx`
- Modify: `frontend/src/api/periodeVariables.ts` (`PeriodeVariables` : `bulletins_a_regenerer?: number`, `employes_a_regenerer?: string[]`)

**Interfaces:**
- Consumes: `GenerationRefusal.details`, `regrouperParSemaine`, `libellePlages`, `formatFr`, `libelleSemaines`, `usePeriodeVariables`.
- Produces: `<JoursASaisirListe details={RefusalDetails} lienPlanning?: string />` ; `BlocPeriodeVariables` prop `lectureSeule?: boolean` (bornes + semaines + « Modifier la fenêtre » qui déplie le formulaire existant) et mention « N bulletin(s) déjà généré(s) gardent l'ancienne fenêtre » quand `bulletins_a_regenerer > 0`.

- [ ] **Step 1: `JoursASaisirListe.tsx`**

```tsx
import { Link } from 'react-router-dom';

import { formatFr, libelleSemaines } from '@/features/payroll/lib/fenetreVariables';
import { libellePlages, regrouperParSemaine } from '@/features/payroll/lib/joursASaisir';
import type { RefusalDetails } from '@/features/payroll/utils/generationGuards';

interface Props {
  details: RefusalDetails;
  /** Lien « Compléter le planning » ; absent dans la génération groupée. */
  lienPlanning?: string;
}

/**
 * Ce qui manque pour générer, tel que le serveur l'a jugé : la fenêtre des
 * variables, les jours à saisir par semaine, et ceux qui attendront le mois
 * suivant. Rien n'est recalculé ici — on montre ce que le 422 a dit.
 */
export function JoursASaisirListe({ details, lienPlanning }: Props) {
  const semaines = regrouperParSemaine(details.joursManquants);
  return (
    <div className="space-y-2 text-sm">
      {details.fenetre && (
        <p className="text-muted-foreground">
          Fenêtre des variables : du {formatFr(details.fenetre.debut)} au{' '}
          {formatFr(details.fenetre.fin)}
          {details.fenetre.semaines.length > 0
            ? ` (${libelleSemaines(details.fenetre.semaines)})`
            : ''}
          .
        </p>
      )}
      {semaines.length > 0 && (
        <ul className="list-disc space-y-0.5 pl-5">
          {semaines.map((s) => (
            <li key={`${s.annee}-${s.semaine}`}>{s.libelle}</li>
          ))}
        </ul>
      )}
      {details.joursInformatifs.length > 0 && (
        <p className="text-xs text-muted-foreground">
          Hors fenêtre, à saisir pour le mois suivant : {libellePlages(details.joursInformatifs)}.
        </p>
      )}
      {lienPlanning && semaines.length > 0 && (
        <Link to={lienPlanning} className="text-xs underline underline-offset-2">
          Compléter le planning
        </Link>
      )}
    </div>
  );
}
```

- [ ] **Step 2: `PayrollGenerationRefusalDialog.tsx`** — dans la branche `single`, après `{single.message}` :

```tsx
              {single.code === 'calendrier_incomplet' && single.details && (
                <div className="mt-2">
                  <JoursASaisirListe details={single.details} />
                </div>
              )}
```

(import `JoursASaisirListe` ; `AlertDialogDescription` rend un `<p>` : remplacer le `AlertDialogDescription` de la branche `single` par un `<div className="text-sm text-muted-foreground">` pour ne pas imbriquer de bloc dans un paragraphe, en gardant le contenu.)

- [ ] **Step 3: `RegeneratePayslipButton.tsx`**

Dialogue de refus : sous `{refus?.message}`, dans un `<div>` plutôt qu'un `<p>` :

```tsx
              {refus?.code === 'calendrier_incomplet' && refus.details && (
                <div className="mt-2">
                  <JoursASaisirListe
                    details={refus.details}
                    lienPlanning={`/schedules?employee=${encodeURIComponent(employeeId)}`}
                  />
                </div>
              )}
```

Dialogue de confirmation « Régénérer ce bulletin ? » : après la description, le bloc fenêtre en lecture :

```tsx
          <div className="pt-1">
            <BlocPeriodeVariables year={year} month={month} lectureSeule />
          </div>
```

(import `BlocPeriodeVariables` depuis `@/features/payroll/components/BlocPeriodeVariables`.)

- [ ] **Step 4: `BlocPeriodeVariables.tsx`** — prop `lectureSeule` et mention des bulletins :

```tsx
interface Props {
  year: number;
  month: number;
  /** Bornes et semaines seulement ; « Modifier la fenêtre » déplie le réglage. */
  lectureSeule?: boolean;
}

export function BlocPeriodeVariables({ year, month, lectureSeule = false }: Props) {
  const { data: fenetre, isLoading } = usePeriodeVariables(year, month);
  const enregistrer = useEnregistrerPeriodeVariables(year, month);
  const [finSaisie, setFinSaisie] = useState<string>('');
  const [modification, setModification] = useState(false);

  if (isLoading || !fenetre) return null;
  const aRegenerer = fenetre.bulletins_a_regenerer ?? 0;
  const mentionBulletins =
    aRegenerer > 0 ? (
      <p className="text-xs text-amber-700 dark:text-amber-500">
        {aRegenerer} bulletin{aRegenerer > 1 ? 's' : ''} déjà généré{aRegenerer > 1 ? 's' : ''} pour
        ce mois garde{aRegenerer > 1 ? 'nt' : ''} l'ancienne fenêtre : à régénérer.
      </p>
    ) : null;
```

Branche mois civil : inchangée, plus `{mentionBulletins}` en fin de bloc. Branche fenêtre décalée : si `lectureSeule && !modification`, rendre seulement le titre, la ligne « Du … au … — semaines … », `mentionBulletins` et un bouton lien :

```tsx
        <Button type="button" variant="link" className="h-auto p-0 text-xs" onClick={() => setModification(true)}>
          Modifier la fenêtre de {libelleMois(month, year)} (pour toute la société)
        </Button>
```

avec `libelleMois` = `monthYearLabel` de `@/features/payroll/utils/payrollMonth`. Sinon, le formulaire existant, complété de `{mentionBulletins}` à la place du paragraphe ambre statique quand `aRegenerer > 0` (le paragraphe statique reste quand `aRegenerer === 0`).

- [ ] **Step 5: Vérifier**

Run: `cd frontend && npx eslint src/features/payroll/components/JoursASaisirListe.tsx src/features/payroll/components/PayrollGenerationRefusalDialog.tsx src/components/payslip-edit/RegeneratePayslipButton.tsx src/features/payroll/components/BlocPeriodeVariables.tsx src/api/periodeVariables.ts && npx tsc --noEmit -p . 2>&1 | grep -v "SalaryAdvances\|SuiviIJSS\|YearCalendarView" | grep -c "error TS"`
Expected: lint propre, `0` erreur de type hors préexistantes.

---

### Task 5: Front — types et libellés pré-paie

**Files:**
- Modify: `frontend/src/api/payrollPreflight.ts` (type union + `PreflightAnomaly.jours_manquants?`, `fenetre?` + `PreflightAnomalyCounts.fenetre_modifiee`)
- Modify: `frontend/src/features/payroll/components/preflightLabels.ts`
- Test: `frontend/src/features/payroll/components/preflightLabels.test.ts` (nouveau)

- [ ] **Step 1: Test rouge**

```ts
import { describe, expect, it } from 'vitest';
import type { PreflightAnomaly } from '@/api/payrollPreflight';
import {
  PREFLIGHT_ANOMALY_TYPE_LABELS,
  PREFLIGHT_ANOMALY_TYPE_ORDER,
  verifyPathForAnomaly,
} from './preflightLabels';

const anomalie = (type: PreflightAnomaly['type']): PreflightAnomaly => ({
  id: 'e1:' + type,
  employee_id: 'e1',
  employee_name: 'Michel BUGNY',
  type,
  severity: 'a_verifier',
  status: 'a_traiter',
  is_forfait_jour: false,
  detail_jours: [],
  conflict_days: [],
});

describe('fenetre_modifiee', () => {
  it('a un libellé, une place dans l’ordre et renvoie au lancement de paie', () => {
    expect(PREFLIGHT_ANOMALY_TYPE_LABELS.fenetre_modifiee).toBe('Fenêtre modifiée');
    expect(PREFLIGHT_ANOMALY_TYPE_ORDER).toContain('fenetre_modifiee');
    expect(verifyPathForAnomaly(anomalie('fenetre_modifiee'))).toBe('/payroll');
  });
});
```

- [ ] **Step 2: Vérifier le rouge**

Run: `cd frontend && npx vitest run src/features/payroll/components/preflightLabels.test.ts`
Expected: erreur de type / `undefined`.

- [ ] **Step 3: Implémenter**

`payrollPreflight.ts` : ajouter `| 'fenetre_modifiee'` au type, `jours_manquants?: string[]; fenetre?: { debut: string; fin: string; semaines: number[]; origine: string } | null;` à `PreflightAnomaly`, `fenetre_modifiee: number;` à `PreflightAnomalyCounts`.

`preflightLabels.ts` : `fenetre_modifiee: 'Fenêtre modifiée'` dans les libellés ; `'fenetre_modifiee'` après `'heures_non_saisies'` dans l'ordre ; dans `verifyPathForAnomaly`, avant le `return '/schedules'` final : `if (anomaly.type === 'fenetre_modifiee') return '/payroll';`.

Chercher les autres `Record<PreflightAnomalyType, …>` du front (`grep -rn "Record<PreflightAnomalyType" frontend/src`) et compléter chacun, sinon `tsc` refuse.

- [ ] **Step 4: Vérifier le vert**

Run: `cd frontend && npx vitest run src/features/payroll && npx eslint src/api/payrollPreflight.ts src/features/payroll/components/preflightLabels.ts && npx tsc --noEmit -p . 2>&1 | grep -v "SalaryAdvances\|SuiviIJSS\|YearCalendarView" | grep -c "error TS"`
Expected: verts, `0`.

---

### Task 6: Suites complètes, documentation, présentation

- [ ] **Step 1: Backend** — `cd backend && .venv/bin/python -m pytest tests/unit -q -p no:warnings | tail -2` (deux rouges d'environnement seulement) ; `ruff check app/modules/payroll app/modules/payroll_variables`.
- [ ] **Step 2: Frontend** — `cd frontend && npx vitest run` ; `npx eslint src/features/payroll src/components/payslip-edit src/api/periodeVariables.ts src/api/payrollPreflight.ts` ; `tsc` comme ci-dessus.
- [ ] **Step 3: Documentation** — passation §6 : pas 2 livré (ce que voit l'écran : liste datée, fenêtre en lecture, « à régénérer ») ; mémoire `periode-a-saisir-fenetre.md` : pas 2 fait, pas 3 restant.
- [ ] **Step 4: Présenter à Alexandre** — commit et déploiement uniquement sur sa demande.
