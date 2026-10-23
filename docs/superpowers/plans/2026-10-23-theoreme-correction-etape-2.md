# Théorème de la correction à la main — étape 2 : plan d'exécution

> **Pour les agents :** sous-compétence requise : superpowers:subagent-driven-development (recommandée) ou superpowers:executing-plans, tâche par tâche. Les étapes se cochent (`- [ ]`). Travail moteur en Opus ; écran et liste de contrôle en Sonnet. Deux agents au plus en même temps, aucun sous-agent lancé par un agent.

**But :** corriger directement n'importe quelle ligne calculée d'un bulletin — gain, cotisation, réduction générale, taux d'impôt du mois — par sa base, son taux ou son montant selon la règle 3. La correction est une variable du mois que le moteur rejoue à chaque calcul, à l'endroit où la ligne naît ; elle se voit (écran, PDF), passe dans le net, les cumuls, la DSN, l'écriture comptable et le mois suivant, et n'est jamais perdue en silence (orpheline, elle bloque la validation).

**Architecture :**
- **Code stable.** Une fonction pure lit le code d'une ligne sur la ligne elle-même (drapeau du moteur, organisme, libellé) : `engine/codes_des_lignes.py`. Le code n'est pas stocké : un bulletin sans correction reste identique clé pour clé, et un bulletin calculé avant cette étape se corrige comme les autres. Deux lignes de même code sont numérotées `#2`, `#3` dans leur ordre.
- **Stockage.** `monthly_inputs.correction_ligne` (colonne de l'étape 1), avec `type: "correction"`. Aucune migration.
- **Application.** `engine/corrections_manuelles.py` : `CorrectionDeLigne`, `JournalDesCorrections` (posé sur le contexte par chaque pipeline), `LignesCorrigees` (une liste qui corrige chaque ligne à son entrée ; les deux calculs du brut et `calculer_cotisations` y posent leurs lignes), deux passes de pipeline pour les lignes nées après (nuit, pause, maintien ; CSG des IJSS, JEI), la réduction générale dans `calcul_reduction_generale.py`, le taux d'impôt dans `calculer_net_et_impot`, les corrections orphelines posées sur le bulletin.
- **Lecture d'un bulletin.** `engine/corrections_du_bulletin.py` : `lignes_corrigeables`, `corrections_du_bulletin`, mentions et explications. La route, la carte, la restauration, la liste de contrôle, le PDF et le test du théorème lisent tous là.

**Technologies :** Python 3.11 (FastAPI, Pydantic v2, client Supabase), pytest ; React + TypeScript, TanStack Query, Vitest.

**Spécification :** `docs/superpowers/specs/2026-10-18-theoreme-correction-a-la-main-design.md` (§ 3 règles 3, 6, 7 ; § 5 ; § 6 ; § 7 ; § 9 ; § 10 étape 2). **Étape 1 :** `docs/superpowers/plans/2026-10-18-theoreme-correction-etape-1.md` et les commits `fix/payslip-edit-state..feat/anomalies-bulletins`.

## Contraintes globales

- Sans correction, chaque bulletin est identique **au centime et clé pour clé** : `comparer5.py` compare toutes les clés de `payslip_data`, de la vue imprimée et des cumuls. Aucun champ nouveau ne s'écrit sur une ligne ou sur un bulletin qui n'a pas de correction (`correction`, `valeur_calculee`, `corrections_en_attente` n'apparaissent qu'avec une correction).
- Règle 3 : une ligne qui porte une base (une quantité pour un gain) et un taux se corrige par sa base ou son taux, et son montant vaut `round(base × taux, 2)` ; une ligne sans base ni taux (forfait, prime, réduction générale, mutuelle) se corrige par son montant ; l'impôt par son taux du mois, en pourcentage. Une correction ne porte jamais à la fois une base ou un taux et un montant.
- Une correction ne change jamais le libellé d'une ligne. Les totaux ne se tapent jamais.
- Le motif est obligatoire : 3 caractères au moins, 300 au plus.
- Une correction ne vaut que pour son mois ; elle est rejouée à chaque recalcul ; orpheline, elle reste enregistrée, le bulletin porte `corrections_en_attente` et ne se valide pas.
- Rien n'est écrit en base par les tests. Le test du théorème et le filet tournent au bac à sable sous le piège à écritures (`backend/scripts/verification_rgdu/piege.py`).
- **Pas de déploiement, pas de push** dans ce plan : ils se font sur accord explicite d'Alexandre. Ne jamais pousser sur `main`. Ne jamais régénérer un bulletin réel.
- Spécificités Colorplast intouchables : le filet doit montrer 0 écart ; tout écart s'explique et se corrige avant la suite.
- Aucun nom de salarié dans le code, les tests, les commits ni les messages (dépôt public). Le produit s'appelle « Martine » dans tout texte visible.
- Interpréteur : `/Users/alex/dev/EYWAI/backend/.venv/bin/python`. Les tests unitaires se lancent depuis `backend/` du worktree avec `APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key` devant (reproduit la CI ; sans ces variables, deux tests sont rouges à cause du `.env` local, pas du code). Chaque agent ne lance que les tests de ce qu'il touche ; la suite complète passe une fois, à la tâche 14.
- Worktree : `/Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2`, branche `feat/theoreme-etape-2` (part de `feat/anomalies-bulletins`, 338215e6). Le dépôt principal `/Users/alex/dev/EYWAI` sert à autre chose : n'y rien modifier.

## Décisions prises là où la spécification laisse ouvert

1. **Le code se lit, il ne s'écrit pas.** La spec dit « un code stable sur chaque ligne ». Un champ écrit sur chaque ligne changerait tous les bulletins au filet et laisserait sans code ceux calculés avant. Le code est donc une fonction pure de la ligne ; le test du théorème vérifie qu'aucune ligne réelle n'en manque.
2. **Doublons numérotés.** Deux lignes de même code (deux mutuelles de même nom, la vieillesse déplafonnée en double du barème de test) deviennent `code` et `code#2`, dans leur ordre ; elles restent dans le même bloc et dans le même ordre au calcul comme une fois enregistrées.
3. **Champs d'une correction.** Gain : `base` (la quantité imprimée), `taux`, `montant`. Cotisation : `base`, `taux_salarial`, `taux_patronal`, `montant_salarial`, `montant_patronal` (les mêmes noms que l'étape 1). Impôt : `taux` en pourcentage.
4. **Ce qui ne se corrige pas sur la carte, et pourquoi (la carte le dit).** Une prime saisie (« Primes du mois » le fait déjà), un sous-total, une ligne d'information, une régularisation de l'étape 1, les cotisations de la participation et de la prime de partage de la valeur (par une régularisation de cotisation : leur net se calcule à part des lignes), les lignes hors brut (frais, IJSS, indemnités exonérées : à leur source ou dans « Primes du mois »). Le théorème tient : chaque ligne se corrige, ici, par une régularisation ou à sa source.
5. **Ce qui suit une ligne corrigée.** Tout ce que le moteur calcule depuis les lignes : brut, précarité, indemnité compensatrice de congés, rémunération et heures des heures sup et complémentaires, sous-total contractuel, heures du SMIC de référence (base, absences non payées, arrêts, heures sup perdues), maintien versé, assiettes et cotisations, plafond de la réduction des heures sup, forfait social, net imposable, impôt, cumuls. Ce qui se calcule depuis le contrat ne suit pas : corriger le taux de « Salaire de base » ne change pas le taux horaire des absences, des congés ni des heures sup, qui gardent le calcul de Martine et se corrigent chacune.
6. **Tranches Agirc-Arrco.** Leurs cumuls de régularisation suivent l'assiette, pas une ligne : une base corrigée sur une ligne de tranche ne les touche pas. Pour changer une tranche, on corrige le brut.
7. **Une correction qui ne convient plus.** Si la ligne visée existe encore mais ne se corrige plus par les mêmes champs (elle a perdu son taux), la correction reste en attente comme une ligne disparue.
8. **Réduction générale.** Corrigée par son montant ; son cumul enregistre la réduction appliquée (déjà appliquée moins le montant corrigé). Une correction qui rendrait la réduction de l'année négative est refusée au recalcul, comme la régularisation de l'étape 1.
9. **« Validé = recalculé ».** La valeur calculée de Martine est imprimée sur le PDF : elle reste dans la comparaison au centime (rien à changer dans `empreinte_entrees`), et un bulletin dont Martine recalcule autrement la ligne corrigée est « À recalculer ».
10. **Restauration.** Elle remet les corrections de la version sans vérifier leurs lignes : une correction dont la ligne n'existe plus revient en attente et bloque la validation.
11. **Une correction par ligne.** Corriger à nouveau une ligne corrigée, c'est retirer sa correction et en ajouter une autre dans le même enregistrement ; la route refuse deux corrections actives sur la même ligne.
12. **Mutuelle.** La part patronale réintégrée au net imposable suit l'écart d'une correction directe comme celui d'une régularisation. La part salariale non déductible de mutuelle reste lue sur la fiche (limite connue, comme à l'étape 1).
13. **Défaut de l'étape 1 trouvé en lisant le code :** `PayslipInfo` (réponse de `/api/employees/{id}/payslips`) ne déclare pas `regularisations` ; Pydantic le retire, et la liste de contrôle ne voit jamais les régularisations du mois. La tâche 12 le corrige avec les nouveaux champs.

## Fichiers

| Fichier | Rôle |
|---|---|
| `backend/app/modules/payroll/engine/codes_des_lignes.py` (créé) | inventaire : code, famille, mode de correction, numérotation |
| `backend/app/modules/payroll/engine/corrections_manuelles.py` | correction de ligne, journal du mois, `LignesCorrigees`, passes de pipeline, réduction générale, taux d'impôt, corrections en attente |
| `backend/app/modules/payroll/engine/corrections_du_bulletin.py` (créé) | lecture d'un bulletin : lignes corrigeables, corrections, mentions, explications |
| `backend/app/modules/payroll/engine/calcul_brut.py`, `calcul_brut_forfait.py` | les lignes de gain naissent corrigées ; heures et montants dérivés suivent |
| `backend/app/modules/payroll/engine/calcul_cotisations.py` | les cotisations naissent corrigées |
| `backend/app/modules/payroll/engine/calcul_reduction_generale.py` | réduction générale corrigée, cumul appliqué |
| `backend/app/modules/payroll/engine/calcul_net.py` | taux d'impôt du mois ; mutuelle réintégrée |
| `backend/app/modules/payroll/engine/bulletin.py` | la correction de l'impôt sur la synthèse |
| `backend/app/modules/payroll/documents/payslip_generator.py`, `payslip_generator_forfait.py` | rangent la correction à part des primes |
| `backend/app/modules/payroll/documents/payslip_run_heures.py`, `payslip_run_forfait.py` | journal, deux passes, corrections en attente |
| `backend/app/modules/payroll/domain/explications_lignes.py` | info-bulle d'une ligne corrigée |
| `backend/app/modules/payroll/documents/bulletin_view.py` | astérisque et note sur le PDF |
| `backend/app/modules/payslips/domain/coherence.py` | une correction en attente bloque la validation |
| `backend/app/modules/payslips/domain/corrections.py`, `application/corrections.py`, `application/dto.py`, `schemas/requests.py` | écrire, vérifier, retirer, restaurer |
| `backend/app/modules/payslips/application/lignes_corrigeables.py` (créé), `api/router.py`, `schemas/responses.py` | route `GET /api/payslips/{id}/lignes-corrigeables` |
| `backend/app/modules/payslips/infrastructure/payslip_list_meta.py`, `infrastructure/queries.py` | lignes corrigées et corrections en attente dans les listes |
| `frontend/src/api/payslips.ts`, `src/lib/queryKeys.ts` | types et lecture |
| `frontend/src/features/payroll/utils/correctionsBulletin.ts` | état, requête, champs, aperçu, résumé |
| `frontend/src/components/payslip-edit/CorrigerUneLigneCard.tsx` (créé), `CorrectionsBulletinPanel.tsx`, `src/pages/rh/PayslipEdit.tsx` | la carte |
| `frontend/src/features/payroll/utils/bulletinARecalculer.ts`, `listeControleMois.ts` | liste de contrôle et capteur |
| `backend/scripts/theoreme_correction_a_la_main.py` | test du théorème étendu |

---

### Tâche 0 : préparer le worktree

**Fichiers :** aucun suivi par git.

- [ ] **Étape 1 : vérifier la branche et la base**

```bash
git -C /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2 status --short --branch | head -3
git -C /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2 merge-base --is-ancestor 338215e6 HEAD && echo base-ok
```

Attendu : `## feat/theoreme-etape-2` et `base-ok`.

- [ ] **Étape 2 : donner au worktree ses fichiers locaux (ignorés par git)**

```bash
ln -sfn /Users/alex/dev/EYWAI/frontend/node_modules /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/frontend/node_modules
cp /Users/alex/dev/EYWAI/backend/.env /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend/.env
git -C /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2 status --short | grep -v '^??' | wc -l
```

Attendu : `0` (les deux fichiers sont ignorés par git ; rien d'autre ne change).

- [ ] **Étape 3 : vérifier que les tests de l'étape 1 passent dans le worktree**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_corrections_manuelles.py tests/unit/payroll/test_regularisations_dans_les_pipelines.py tests/unit/payslips/test_corrections.py -q
```

Attendu : tout passe.

---

### Tâche 1 : l'inventaire — un code stable pour chaque ligne

**Fichiers :**
- Créer : `backend/app/modules/payroll/engine/codes_des_lignes.py`
- Tester : `backend/tests/unit/payroll/test_codes_des_lignes.py` (créé)

**Interfaces :**
- Produit (module `app.modules.payroll.engine.codes_des_lignes`) :
  - constantes `BLOC_BRUT = "brut"`, `BLOC_COTISATIONS = "cotisations"`, `BLOC_IMPOT = "impot"`, `MODE_BASE_OU_TAUX = "base_ou_taux"`, `MODE_MONTANT = "montant"`, `MODE_TAUX = "taux"`, `CODE_IMPOT = "impot"`, `RAISON_SAISIE`, `RAISON_SOUS_TOTAL`, `RAISON_INFORMATION`, `RAISON_REGULARISATION`, `RAISON_HORS_SALAIRE`, `RAISON_INCONNUE`, `COTI_IDS_A_PLUSIEURS_LIGNES`, `COTI_IDS_AU_MONTANT` ;
  - `slug(texte: Any) -> str` ;
  - `famille_du_code(code: str | None) -> str` (`"brut:heures_sup:25#2"` → `"brut:heures_sup"`) ;
  - `code_de_ligne_de_gain(ligne: Mapping) -> str | None`, `code_de_ligne_de_cotisation(ligne: Mapping) -> str | None`, `code_de_ligne(bloc: str, ligne: Mapping) -> str | None` ;
  - `numeroter(codes: Iterable[str | None]) -> list[str | None]` et `class Numerotation` avec `code(bloc, ligne) -> str | None` (même numérotation, ligne par ligne) ;
  - `champ_du_montant(ligne: Mapping) -> str` (`"gain"` ou `"perte"`) ;
  - `mode_de_correction(bloc: str, ligne: Mapping, code: str | None) -> tuple[str | None, str | None]` (mode, raison quand le mode est `None`).

- [ ] **Étape 1 : écrire les tests qui échouent**

Créer `backend/tests/unit/payroll/test_codes_des_lignes.py` :

```python
"""Chaque ligne d'un bulletin a un code stable, lu sur la ligne elle-même.

Une correction vise une ligne par ce code. Il n'est pas stocké : un bulletin
sans correction reste identique, et un bulletin d'avant se corrige aussi. Un
libellé écrit dans un producteur de lignes sans code ferait échouer le test du
théorème : on l'attrape ici d'abord.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from app.modules.payroll.documents import payslip_run_forfait, payslip_run_heures
from app.modules.payroll.engine import (
    calcul_brut,
    calcul_brut_forfait,
    indemnites_sortie_brut,
    regime_indemnites_rupture,
    salary_evolution_brut,
)
from app.modules.payroll.engine.codes_des_lignes import (
    BLOC_BRUT,
    BLOC_COTISATIONS,
    BLOC_IMPOT,
    CODE_IMPOT,
    MODE_BASE_OU_TAUX,
    MODE_MONTANT,
    MODE_TAUX,
    RAISON_HORS_SALAIRE,
    RAISON_INCONNUE,
    RAISON_INFORMATION,
    RAISON_REGULARISATION,
    RAISON_SAISIE,
    RAISON_SOUS_TOTAL,
    Numerotation,
    champ_du_montant,
    code_de_ligne,
    famille_du_code,
    mode_de_correction,
    numeroter,
    slug,
)

pytestmark = pytest.mark.unit


def _gain(libelle, **champs):
    return {"libelle": libelle, "quantite": None, "taux": None, "gain": None, "perte": None, **champs}


@pytest.mark.parametrize(
    "ligne, code",
    [
        (_gain("Salaire de base", quantite=151.67, taux=16.4832, gain=2500.0), "brut:salaire_base"),
        (_gain("Salaire de base (forfait jour)", gain=3608.0), "brut:salaire_base"),
        (_gain("Heures suppl. structurelles majorées à 25%", quantite=17.33, taux=15.31, gain=265.37), "brut:hs_structurelles"),
        (_gain("Heures suppl. majorées à 25%", quantite=4.0, taux=20.6039, gain=82.42), "brut:heures_sup:25"),
        (_gain("Heures suppl. majorées à 50%", quantite=2.0, taux=24.72, gain=49.44), "brut:heures_sup:50"),
        (_gain("Heures complémentaires majorées à 10%", quantite=3.0, taux=18.1, gain=54.3), "brut:heures_complementaires:10"),
        (_gain("SOUS-TOTAL SALAIRE CONTRACTUEL", quantite=169.0, gain=2123.38, is_sous_total=True), "brut:sous_total"),
        (_gain("Absence pour entrée ou sortie", quantite=14.0, taux=16.48, perte=230.72), "brut:absence_entree_sortie"),
        (_gain("Absence injustifiée du 21/01/26 (base)", quantite=3.5, taux=16.4832, perte=57.69), "brut:absence_injustifiee:du-21-01-26-base"),
        (_gain("Absence injustifiée (2 jours)", quantite=2.0, taux=166.5, perte=333.0), "brut:absence_injustifiee:2-jours"),
        (_gain("Absence non rémunérée du 16/03/26 (1 jour)", quantite=1.0, taux=166.4975, perte=166.5), "brut:absence_non_remuneree:16-03-26-1-jour"),
        (_gain("Absence événement familial du 10/03/26", quantite=7.0, taux=16.48, perte=115.36), "brut:absence_evenement_familial:10-03-26"),
        (_gain("Abs. jour férié non payé du 11/11/26", quantite=7.0, taux=16.48, perte=115.36), "brut:absence_ferie_non_paye:11-11-26"),
        (_gain("Absence maladie du 03/09 au 05/09", quantite=21.0, taux=16.48, perte=346.08, is_arret_maladie=True), "brut:arret:absence-maladie-du-03-09-au-05-09"),
        (_gain("Absence maladie du 16/03/26", quantite=1.0, taux=164.0, perte=164.0), "brut:absence_maladie:16-03-26"),
        (_gain("Réduction HS structurelles (jours d'absence)", quantite=0.36, taux=15.31, perte=5.51), "brut:reduction_hs_absence"),
        (_gain("Réduction HS structurelles (événement familial)", quantite=2.4, taux=15.31, perte=36.74), "brut:reduction_hs_evenement_familial"),
        (_gain("Maintien de salaire (événement familial)", gain=151.0), "brut:maintien_evenement_familial"),
        (_gain("Complément retenue absence intégrale du mois (fériés et repos)", perte=80.0), "brut:complement_absence_integrale"),
        (_gain("Retenue absence intégrale du mois limitée au salaire mensuel", gain=-12.0), "brut:retenue_absence_integrale"),
        (_gain("Absence sur tout le mois : retenue ramenée au salaire du mois", perte=10.0), "brut:retenue_absence_mois_complet"),
        (_gain("Lissage modulation", gain=10.0), "brut:lissage_modulation"),
        (_gain("Absence congés payés (3 jours : du 01/09 au 03/09)", quantite=21.0, perte=346.0), "brut:absence_conges_payes"),
        (_gain("Indemnité de congés payés (partie base)", quantite=21.0, taux=16.48, gain=346.08), "brut:indemnite_conges_payes:partie-base"),
        (_gain("Indemnité de congés payés (partie HS 25%)", quantite=2.4, taux=20.6, gain=49.44), "brut:indemnite_conges_payes:partie-hs-25"),
        (_gain("Indemnité de congés payés (règle du 1/10ème)", gain=400.0), "brut:indemnite_conges_payes:regle-du-1-10eme"),
        (_gain("Indemnité compensatrice de congés payés (CDD)", taux=0.1, gain=1210.0), "brut:iccp:cdd"),
        (_gain("Indemnité compensatrice de congés payés", taux=0.1, gain=300.0), "brut:iccp"),
        (_gain("Indemnité compensatrice de préavis", gain=2500.0, is_indemnite_sortie=True), "brut:indemnite_sortie:indemnite-compensatrice-de-preavis"),
        (_gain("Prime de précarité (CDD)", taux=0.1, gain=1100.0), "brut:precarite"),
        (_gain("Indemnité de fin de mission (intérim)", taux=0.1, gain=250.0), "brut:ifm"),
        (_gain("Avantages en nature", gain=120.0), "brut:avantages_en_nature"),
        (_gain("Rappel de salaire (période du 01/09 au 30/09)", gain=50.0), "brut:rappel_salaire:periode-du-01-09-au-30-09"),
        (_gain("Rappel de salaire", gain=50.0), "brut:rappel_salaire"),
        (_gain("Réintégration NDF Repas", gain=3.0), "brut:reintegration:ndf-repas"),
        (_gain("Prime d'ancienneté", quantite=2000.0, taux=0.03, gain=60.0, meta={"plein_mois": 60.0}), "brut:prime_anciennete"),
        (_gain("Prime exceptionnelle", gain=100.0, saisie_id="s-1"), "brut:saisie:s-1"),
        (_gain("Prime de fin d'année", gain=100.0), "brut:prime:prime-de-fin-d-annee"),
        (_gain("Heures de nuit majorées à 50%", quantite=10.0, taux=24.72, gain=82.42), "brut:heures_nuit"),
        (_gain("Pause rémunérée (planning)", quantite=5.0, taux=16.48, gain=82.42), "brut:pause_remuneree"),
        (_gain("Maintien de salaire employeur", gain=300.0, is_maintien_employeur=True), "brut:maintien_employeur"),
        (_gain("HS reportées au compte modulation", quantite=3.0, is_informative=True), "brut:information:hs-reportees-au-compte-modulation"),
    ],
)
def test_chaque_ligne_de_gain_a_son_code(ligne, code):
    assert code_de_ligne(BLOC_BRUT, ligne) == code


@pytest.mark.parametrize(
    "ligne, code",
    [
        ({"coti_id": "securite_sociale_maladie", "libelle": "Maladie, maternité, invalidité, décès"}, "cotisation:securite_sociale_maladie"),
        ({"coti_id": "csg_non_deductible", "libelle": "CSG/CRDS non déductible"}, "cotisation:csg_non_deductible:csg-crds-non-deductible"),
        ({"coti_id": "csg_non_deductible", "libelle": "CSG/CRDS sur HS non déductible"}, "cotisation:csg_non_deductible:csg-crds-sur-hs-non-deductible"),
        ({"coti_id": "forfait_social", "libelle": "Forfait social 8% sur prévoyance"}, "cotisation:forfait_social:forfait-social-8-sur-prevoyance"),
        ({"coti_id": "mutuelle", "libelle": "Mutuelle Frais de Santé"}, "cotisation:mutuelle:mutuelle-frais-de-sante"),
        ({"libelle": "CSG déductible IJSS", "base": 300.0, "taux_salarial": 0.038}, "cotisation:sans_organisme:csg-deductible-ijss"),
        ({"libelle": "CSG déductible — Participation", "is_participation": True}, "cotisation:sans_organisme:csg-deductible-participation"),
        ({"coti_id": "reduction_generale", "libelle": "Réduction générale de cotisations patronales"}, "cotisation:reduction_generale"),
        ({"coti_id": "mutuelle", "libelle": "Régularisation – Mutuelle", "regularisation": {"saisie_id": "s1"}}, "cotisation:regularisation:s1"),
        ({"libelle": ""}, None),
    ],
)
def test_chaque_cotisation_a_son_code(ligne, code):
    assert code_de_ligne(BLOC_COTISATIONS, ligne) == code


def test_l_impot_a_son_code():
    assert code_de_ligne(BLOC_IMPOT, {"base": 2000.0, "taux": 5.2, "montant": 104.0}) == CODE_IMPOT == "impot"


def test_une_ligne_que_l_inventaire_ne_connait_pas_n_a_pas_de_code():
    assert code_de_ligne(BLOC_BRUT, _gain("Ligne inventée", quantite=1.0, taux=2.0, perte=2.0)) is None
    assert mode_de_correction(BLOC_BRUT, {}, None) == (None, RAISON_INCONNUE)


def test_le_slug_et_la_famille():
    assert slug("Absence du 12/09/26 (règle)") == "absence-du-12-09-26-regle"
    assert famille_du_code("brut:heures_sup:25#2") == "brut:heures_sup"
    assert famille_du_code("cotisation:mutuelle:gan-sante") == "cotisation:mutuelle"
    assert famille_du_code("impot") == "impot"
    assert famille_du_code(None) == ""


def test_deux_lignes_de_meme_code_sont_numerotees_dans_leur_ordre():
    assert numeroter(["a", "b", "a", None, "a"]) == ["a", "b", "a#2", None, "a#3"]
    numeros = Numerotation()
    ligne = {"coti_id": "vieillesse_deplafonnee", "libelle": "Vieillesse déplafonnée"}
    assert numeros.code(BLOC_COTISATIONS, ligne) == "cotisation:vieillesse_deplafonnee"
    assert numeros.code(BLOC_COTISATIONS, dict(ligne)) == "cotisation:vieillesse_deplafonnee#2"


def test_le_montant_d_une_retenue_est_sa_perte():
    assert champ_du_montant(_gain("Absence", quantite=1.0, taux=2.0, perte=2.0)) == "perte"
    assert champ_du_montant(_gain("Prime", gain=2.0)) == "gain"


@pytest.mark.parametrize(
    "bloc, ligne, attendu",
    [
        (BLOC_BRUT, _gain("Salaire de base", quantite=151.67, taux=16.48, gain=2500.0), (MODE_BASE_OU_TAUX, None)),
        (BLOC_BRUT, _gain("Absence non rémunérée du 16/03/26", quantite=7.0, taux=16.48, perte=115.36), (MODE_BASE_OU_TAUX, None)),
        # Un taux sans quantité (précarité) : le montant seul.
        (BLOC_BRUT, _gain("Prime de précarité (CDD)", taux=0.1, gain=1100.0), (MODE_MONTANT, None)),
        (BLOC_BRUT, _gain("Prime exceptionnelle", gain=100.0, saisie_id="s-1"), (None, RAISON_SAISIE)),
        (BLOC_BRUT, _gain("SOUS-TOTAL SALAIRE CONTRACTUEL", gain=1.0, is_sous_total=True), (None, RAISON_SOUS_TOTAL)),
        (BLOC_BRUT, _gain("HS reportées au compte modulation", is_informative=True), (None, RAISON_INFORMATION)),
        (BLOC_COTISATIONS, {"coti_id": "securite_sociale_maladie", "libelle": "Maladie", "base": 2000.0, "taux_salarial": 0.0, "taux_patronal": 0.07}, (MODE_BASE_OU_TAUX, None)),
        (BLOC_COTISATIONS, {"coti_id": "allocations_familiales", "libelle": "AF", "base": 2000.0, "taux_salarial": None, "taux_patronal": 0.0525}, (MODE_BASE_OU_TAUX, None)),
        # La réduction générale porte un coefficient cumulé, pas un taux du mois.
        (BLOC_COTISATIONS, {"coti_id": "reduction_generale", "libelle": "Réduction générale de cotisations patronales", "base": 2500.0, "taux_patronal": 0.1978}, (MODE_MONTANT, None)),
        (BLOC_COTISATIONS, {"coti_id": "mutuelle", "libelle": "Mutuelle", "base": None}, (MODE_MONTANT, None)),
        (BLOC_COTISATIONS, {"coti_id": "mutuelle", "libelle": "Régularisation – Mutuelle", "regularisation": {"saisie_id": "s1"}}, (None, RAISON_REGULARISATION)),
        (BLOC_COTISATIONS, {"libelle": "CSG déductible — Participation", "base": 100.0, "taux_salarial": 0.068, "is_participation": True}, (None, RAISON_HORS_SALAIRE)),
        (BLOC_IMPOT, {"base": 2000.0, "taux": 5.2}, (MODE_TAUX, None)),
    ],
)
def test_la_regle_3_dit_par_quoi_chaque_ligne_se_corrige(bloc, ligne, attendu):
    assert mode_de_correction(bloc, ligne, code_de_ligne(bloc, ligne)) == attendu


def _lignes_ecrites(module) -> list[dict]:
    """Les lignes de gain écrites en dur dans un producteur : libellé (parties
    variables remplacées par « 25 »), et drapeaux posés à True."""
    lignes = []
    for noeud in ast.walk(ast.parse(inspect.getsource(module))):
        if not isinstance(noeud, ast.Dict):
            continue
        cles = {c.value: v for c, v in zip(noeud.keys, noeud.values) if isinstance(c, ast.Constant)}
        if "libelle" not in cles or not ({"gain", "perte"} & cles.keys()):
            continue
        valeur = cles["libelle"]
        if isinstance(valeur, ast.Constant) and isinstance(valeur.value, str):
            libelle = valeur.value
        elif isinstance(valeur, ast.JoinedStr):
            libelle = "".join(p.value if isinstance(p, ast.Constant) else "25" for p in valeur.values)
        else:
            continue  # libellé calculé : couvert par le test paramétré et le test du théorème
        drapeaux = {
            cle: True
            for cle, v in cles.items()
            if str(cle).startswith("is_") and isinstance(v, ast.Constant) and v.value is True
        }
        lignes.append({"libelle": libelle, "quantite": 1.0, "taux": 1.0, "perte": 1.0, **drapeaux})
    return lignes


PRODUCTEURS_DE_GAINS = [
    calcul_brut,
    calcul_brut_forfait,
    indemnites_sortie_brut,
    regime_indemnites_rupture,
    salary_evolution_brut,
    payslip_run_heures,
    payslip_run_forfait,
]


@pytest.mark.parametrize("module", PRODUCTEURS_DE_GAINS, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_chaque_libelle_ecrit_dans_un_producteur_de_gains_a_un_code(module):
    """Un nouveau type de ligne n'entre pas sans sa correction (spec § 9)."""
    inconnues = [l["libelle"] for l in _lignes_ecrites(module) if code_de_ligne(BLOC_BRUT, l) is None]
    assert inconnues == []
```

- [ ] **Étape 2 : lancer les tests pour les voir échouer**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_codes_des_lignes.py -q
```

Attendu : erreur de collecte, `ModuleNotFoundError: No module named 'app.modules.payroll.engine.codes_des_lignes'`.

- [ ] **Étape 3 : écrire le module**

Créer `backend/app/modules/payroll/engine/codes_des_lignes.py` :

```python
"""Le code stable de chaque ligne d'un bulletin, et ce qui s'y corrige.

Théorème de la correction à la main, étape 2 (spec 2026-10-18, règle 3 et
§ 10). Une correction vise une ligne par son code. Le code se lit sur la ligne
elle-même, au calcul comme sur un bulletin enregistré : il n'est jamais
stocké. Un bulletin sans correction reste donc identique, clé pour clé, et un
bulletin calculé avant cette étape se corrige comme les autres.

- Gain : « brut:<famille>[:<discriminant>] ». La famille vient d'un drapeau
  posé par le moteur ou du libellé, qu'une correction ne change jamais ; le
  discriminant (une date, un palier) distingue les lignes d'une même famille.
- Cotisation : « cotisation:<coti_id>[:<libellé>] ». Le libellé n'entre que
  pour les organismes qui portent plusieurs lignes.
- Impôt : « impot ».

Deux lignes de même code sont numérotées dans leur ordre (« #2 », « #3 ») :
elles restent dans le même bloc et dans le même ordre, au calcul comme une
fois enregistrées.

Une ligne que l'inventaire ne connaît pas n'a pas de code : le test du
théorème échoue sur elle. Un nouveau type de ligne n'entre pas sans sa
correction.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Any, Iterable, Mapping

BLOC_BRUT = "brut"
BLOC_COTISATIONS = "cotisations"
BLOC_IMPOT = "impot"

MODE_BASE_OU_TAUX = "base_ou_taux"
MODE_MONTANT = "montant"
MODE_TAUX = "taux"

CODE_IMPOT = "impot"

RAISON_SAISIE = "Une prime saisie se corrige dans « Primes du mois »."
RAISON_SOUS_TOTAL = "Un sous-total ne se corrige pas : corrigez les lignes qui le composent."
RAISON_INFORMATION = "Ligne d'information : elle ne compte pas dans le brut."
RAISON_REGULARISATION = (
    "Une régularisation se retire ou se refait dans « Régularisations de cotisation »."
)
RAISON_HORS_SALAIRE = (
    "Cotisation de la participation ou de la prime de partage de la valeur : "
    "corrigez-la par une régularisation de cotisation."
)
RAISON_INCONNUE = (
    "Martine ne connaît pas cette ligne : corrigez-la à sa source ou par une régularisation."
)

#: Organismes qui portent plusieurs lignes sur un même bulletin : CSG sur le
#: salaire et sur les heures sup, forfait social sur prévoyance et sur retraite
#: supplémentaire, une ligne par mutuelle et par tranche de prévoyance.
COTI_IDS_A_PLUSIEURS_LIGNES = frozenset(
    {
        "csg_deductible",
        "csg_non_deductible",
        "crds",
        "forfait_social",
        "mutuelle",
        "prevoyance_cadre",
        "prevoyance_non_cadre",
        "retraite_sup",
    }
)

#: Cotisations dont le montant n'est pas base × taux : elles se corrigent par
#: leur montant (règle 3). La réduction générale porte un coefficient cumulé.
COTI_IDS_AU_MONTANT = frozenset(
    {
        "reduction_generale",
        "mutuelle",
        "reduction_hs_salariale",
        "deduction_hs_patronale",
        "exoneration_apprenti_salariale",
        "exoneration_stage",
    }
)

#: (famille, motif du libellé). Le premier motif qui reconnaît le libellé donne
#: la famille ; le groupe « d », s'il existe, le discriminant.
_MOTIFS_DE_GAIN: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (famille, re.compile(motif))
    for famille, motif in (
        ("salaire_base", r"^Salaire de base( \(forfait jour\))?$"),
        ("hs_structurelles", r"^Heures suppl\. structurelles majorées à .+%$"),
        ("heures_sup", r"^Heures suppl\. majorées à (?P<d>.+)%$"),
        ("heures_complementaires", r"^Heures complémentaires majorées à (?P<d>.+)%$"),
        ("absence_entree_sortie", r"^Absence pour entrée ou sortie$"),
        ("absence_injustifiee", r"^Absence injustifiée (?P<d>.+)$"),
        ("absence_non_remuneree", r"^Absence non rémunérée du (?P<d>.+)$"),
        ("absence_evenement_familial", r"^Absence événement familial du (?P<d>.+)$"),
        ("absence_ferie_non_paye", r"^Abs\. jour férié non payé du (?P<d>.+)$"),
        ("absence_maladie", r"^Absence maladie du (?P<d>.+)$"),
        ("reduction_hs_absence", r"^Réduction HS structurelles \(jours d'absence\)$"),
        ("reduction_hs_evenement_familial", r"^Réduction HS structurelles \(événement familial\)$"),
        ("maintien_evenement_familial", r"^Maintien de salaire \(événement familial\)$"),
        ("maintien_employeur", r"^Maintien de salaire employeur$"),
        ("complement_absence_integrale", r"^Complément retenue absence intégrale du mois"),
        ("retenue_absence_integrale", r"^Retenue absence intégrale du mois limitée au salaire mensuel$"),
        ("retenue_absence_mois_complet", r"^Absence sur tout le mois : retenue ramenée au salaire du mois$"),
        ("lissage_modulation", r"^Lissage modulation$"),
        ("absence_conges_payes", r"^Absence congés payés"),
        ("indemnite_conges_payes", r"^Indemnité de congés payés \((?P<d>.+)\)$"),
        ("iccp", r"^Indemnité compensatrice de congés payés(?P<d>.*)$"),
        ("precarite", r"^Prime de précarité \(CDD\)$"),
        ("ifm", r"^Indemnité de fin de mission \(intérim\)$"),
        ("avantages_en_nature", r"^Avantages en nature$"),
        ("rappel_salaire", r"^Rappel de salaire(?P<d>.*)$"),
        ("reintegration", r"^Réintégration (?P<d>.+)$"),
        ("heures_nuit", r"^Heures de nuit majorées à .+%$"),
        ("pause_remuneree", r"^Pause rémunérée \(planning\)$"),
    )
)


def slug(texte: Any) -> str:
    """« Absence du 12/09/26 (règle) » → « absence-du-12-09-26-regle »."""
    ascii_ = unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-")


def famille_du_code(code: str | None) -> str:
    """« brut:heures_sup:25#2 » → « brut:heures_sup » ; « impot » → « impot »."""
    if not code:
        return ""
    return ":".join(code.split("#", 1)[0].split(":")[:2])


def _avec_discriminant(prefixe: str, discriminant: Any) -> str:
    morceau = slug(discriminant)
    return f"{prefixe}:{morceau}" if morceau else prefixe


def _montant_seul(ligne: Mapping[str, Any]) -> bool:
    return (
        ligne.get("quantite") is None
        and ligne.get("taux") is None
        and ligne.get("gain") is not None
        and ligne.get("perte") is None
    )


def code_de_ligne_de_gain(ligne: Mapping[str, Any]) -> str | None:
    libelle = str(ligne.get("libelle") or "")
    if ligne.get("is_sous_total"):
        return "brut:sous_total"
    if ligne.get("is_informative"):
        return _avec_discriminant("brut:information", libelle)
    if ligne.get("saisie_id"):
        return f"brut:saisie:{ligne['saisie_id']}"
    if ligne.get("is_arret_maladie"):
        return _avec_discriminant("brut:arret", libelle)
    if ligne.get("is_maintien_employeur"):
        return "brut:maintien_employeur"
    if ligne.get("is_indemnite_sortie"):
        return _avec_discriminant("brut:indemnite_sortie", libelle)
    meta = ligne.get("meta")
    if isinstance(meta, Mapping) and "plein_mois" in meta:
        return "brut:prime_anciennete"
    for famille, motif in _MOTIFS_DE_GAIN:
        trouve = motif.match(libelle)
        if trouve:
            return _avec_discriminant(f"brut:{famille}", trouve.groupdict().get("d"))
    # Un gain au forfait, sans quantité ni taux (prime d'une règle, rappel
    # d'IJSS…) : il se corrige toujours par son montant.
    if libelle and _montant_seul(ligne):
        return _avec_discriminant("brut:prime", libelle)
    return None


def code_de_ligne_de_cotisation(ligne: Mapping[str, Any]) -> str | None:
    regularisation = ligne.get("regularisation")
    if isinstance(regularisation, Mapping):
        return f"cotisation:regularisation:{regularisation.get('saisie_id') or slug(ligne.get('libelle'))}"
    coti_id = str(ligne.get("coti_id") or "")
    libelle = ligne.get("libelle")
    if not coti_id:
        return _avec_discriminant("cotisation:sans_organisme", libelle) if slug(libelle) else None
    if coti_id in COTI_IDS_A_PLUSIEURS_LIGNES or ligne.get("is_participation") or ligne.get("is_ppv"):
        return _avec_discriminant(f"cotisation:{coti_id}", libelle)
    return f"cotisation:{coti_id}"


def code_de_ligne(bloc: str, ligne: Mapping[str, Any]) -> str | None:
    if bloc == BLOC_BRUT:
        return code_de_ligne_de_gain(ligne)
    if bloc == BLOC_COTISATIONS:
        return code_de_ligne_de_cotisation(ligne)
    if bloc == BLOC_IMPOT:
        return CODE_IMPOT
    return None


def numeroter(codes: Iterable[str | None]) -> list[str | None]:
    """Le deuxième code identique devient « code#2 », le troisième « code#3 »."""
    vus: Counter[str] = Counter()
    sortie: list[str | None] = []
    for code in codes:
        if code is None:
            sortie.append(None)
            continue
        vus[code] += 1
        sortie.append(code if vus[code] == 1 else f"{code}#{vus[code]}")
    return sortie


class Numerotation:
    """La même numérotation que `numeroter`, quand les lignes arrivent une à une."""

    def __init__(self) -> None:
        self._vus: Counter[str] = Counter()

    def code(self, bloc: str, ligne: Mapping[str, Any]) -> str | None:
        code = code_de_ligne(bloc, ligne)
        if code is None:
            return None
        self._vus[code] += 1
        rang = self._vus[code]
        return code if rang == 1 else f"{code}#{rang}"


def champ_du_montant(ligne: Mapping[str, Any]) -> str:
    """Le champ qui porte le montant d'un gain : « gain », ou « perte » pour une retenue."""
    return "perte" if ligne.get("gain") is None and ligne.get("perte") is not None else "gain"


def mode_de_correction(
    bloc: str, ligne: Mapping[str, Any], code: str | None
) -> tuple[str | None, str | None]:
    """Par quoi la ligne se corrige (règle 3), ou pourquoi elle ne se corrige pas ici."""
    if code is None:
        return None, RAISON_INCONNUE
    if bloc == BLOC_IMPOT:
        return MODE_TAUX, None
    famille = famille_du_code(code)
    if bloc == BLOC_BRUT:
        if famille == "brut:sous_total":
            return None, RAISON_SOUS_TOTAL
        if famille == "brut:information":
            return None, RAISON_INFORMATION
        if famille == "brut:saisie":
            return None, RAISON_SAISIE
        if ligne.get("quantite") is not None and ligne.get("taux") is not None:
            return MODE_BASE_OU_TAUX, None
        return MODE_MONTANT, None
    if famille == "cotisation:regularisation":
        return None, RAISON_REGULARISATION
    if ligne.get("is_participation") or ligne.get("is_ppv"):
        return None, RAISON_HORS_SALAIRE
    if str(ligne.get("coti_id") or "") in COTI_IDS_AU_MONTANT:
        return MODE_MONTANT, None
    if ligne.get("base") is not None and (
        ligne.get("taux_salarial") is not None or ligne.get("taux_patronal") is not None
    ):
        return MODE_BASE_OU_TAUX, None
    return MODE_MONTANT, None
```

- [ ] **Étape 4 : relancer les tests**

Même commande qu'à l'étape 2. Attendu : tout passe. Si le test des libellés écrits trouve un libellé inconnu (un producteur que l'inventaire a manqué), ajouter son motif à `_MOTIFS_DE_GAIN` **et** une ligne au test paramétré, puis relancer.

- [ ] **Étape 5 : commiter**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2 && git add backend/app/modules/payroll/engine/codes_des_lignes.py backend/tests/unit/payroll/test_codes_des_lignes.py && git commit -m "feat(paie): chaque ligne d'un bulletin a un code stable, lu sur la ligne

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 2 : la correction d'une ligne, le journal du mois, les lignes corrigées à leur entrée

**Fichiers :**
- Modifier : `backend/app/modules/payroll/engine/corrections_manuelles.py` (ajouts en fin de fichier, et l'import de `dataclass` devient `dataclass, field`)
- Tester : `backend/tests/unit/payroll/test_corrections_de_ligne.py` (créé)

**Interfaces :**
- Consomme : tout `codes_des_lignes` (tâche 1).
- Produit (module `app.modules.payroll.engine.corrections_manuelles`) :
  - `TYPE_CORRECTION = "correction"`, `CLE_CORRECTIONS_LIGNE = "corrections_ligne"` (clé des saisies du mois), `CLE_CORRECTIONS_EN_ATTENTE = "corrections_en_attente"` (clé de `payslip_data`), `PREFIXE_SAISIE_CORRECTION = "Correction – "`, `RAISON_LIGNE_ABSENTE`, `PAR_MODE: dict[str, str]` ;
  - `class CorrectionInvalide(ValueError)` ;
  - `bloc_du_code(code: str) -> str | None` ;
  - `@dataclass(frozen=True) CorrectionDeLigne(ligne, libelle, motif, base=None, taux=None, montant=None, taux_salarial=None, taux_patronal=None, montant_salarial=None, montant_patronal=None, saisie_id=None)` avec `.bloc`, `.champs: frozenset[str]`, `.par_montant`, `.convient(mode) -> bool`, `.charge_utile() -> dict`, `.trace() -> dict` (charge utile + `saisie_id`), `.saisie_du_mois(periode) -> dict`, `CorrectionDeLigne.depuis(donnees, saisie_id=None)` ;
  - `est_correction_de_ligne(saisie) -> bool`, `ranger_correction_manuelle(saisie, saisies_data) -> bool` (range aussi les régularisations de l'étape 1) ;
  - `@dataclass(frozen=True) EffetUnitaire(famille, quantite=0.0, brut=0.0, salarial=0.0, patronal=0.0)` ;
  - `@dataclass EffetDesCorrections` avec `corrigees: int`, `salarial: float`, `patronal: float`, `ajouter(effet)`, `quantite(*familles) -> float`, `sur_le_brut(*familles) -> float` (effet sur le brut : un gain qui monte compte en plus, une retenue qui monte en moins) ;
  - `class JournalDesCorrections` avec `JournalDesCorrections.depuis(saisie_du_mois) -> JournalDesCorrections | None` (None sans correction), `prendre(code)`, `refuser(correction, raison)`, `corriger(ligne, bloc, code) -> EffetUnitaire | None`, `en_attente() -> list[dict]` (trace + `raison`) ;
  - `journal_du_contexte(contexte) -> JournalDesCorrections | None` (lit `contexte.corrections_du_mois`) ;
  - `class LignesCorrigees(list)` : `LignesCorrigees(journal, bloc, lignes=())`, attribut `.effet` ;
  - `corriger_les_lignes_de_gain(lignes, journal) -> EffetDesCorrections`, `corriger_les_lignes_de_cotisation(lignes, journal) -> EffetDesCorrections` ;
  - `recaler_le_sous_total(lignes) -> None`, `synchroniser_le_maintien(resultats_maintien, lignes) -> None` ;
  - `corriger_la_reduction_generale(ligne, journal, reduction_deja: float) -> dict | None` ;
  - `corriger_le_taux_d_impot(taux_calcule, base_pas, journal) -> tuple[float, dict | None]` (le dict : `{"correction": trace, "valeur_calculee": {"taux", "montant"}}`) ;
  - `poser_les_corrections_en_attente(bulletin, journal) -> None`.
- Une ligne corrigée porte `correction` (la trace) et `valeur_calculee` : pour un gain `{"quantite", "taux", "gain", "perte"}`, pour une cotisation `{"base", "taux_salarial", "taux_patronal", "montant_salarial", "montant_patronal"}` — les mêmes noms que les champs de la ligne.

- [ ] **Étape 1 : écrire les tests qui échouent**

Créer `backend/tests/unit/payroll/test_corrections_de_ligne.py` :

```python
"""Corriger une ligne : par sa base, son taux ou son montant, au centime comme le moteur."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.codes_des_lignes import BLOC_BRUT, BLOC_COTISATIONS
from app.modules.payroll.engine.corrections_manuelles import (
    CLE_CORRECTIONS_EN_ATTENTE,
    CLE_CORRECTIONS_LIGNE,
    CLE_REGULARISATIONS_COTISATION,
    RAISON_LIGNE_ABSENTE,
    CorrectionDeLigne,
    CorrectionInvalide,
    JournalDesCorrections,
    LignesCorrigees,
    RegularisationCotisation,
    corriger_la_reduction_generale,
    corriger_le_taux_d_impot,
    corriger_les_lignes_de_gain,
    poser_les_corrections_en_attente,
    ranger_correction_manuelle,
    recaler_le_sous_total,
    synchroniser_le_maintien,
)

pytestmark = pytest.mark.unit

PERIODE = {"employee_id": "e", "company_id": "c", "year": 2026, "month": 10}


def _salaire_de_base():
    return {"libelle": "Salaire de base", "quantite": 151.67, "taux": 16.4832, "gain": 2500.0, "perte": None}


def _c(**champs):
    donnees = dict(ligne="brut:salaire_base", libelle="Salaire de base", motif="Avenant", saisie_id="s1")
    donnees.update(champs)
    return CorrectionDeLigne(**donnees)


def test_une_correction_porte_une_base_ou_un_taux_ou_un_montant_jamais_les_deux():
    with pytest.raises(CorrectionInvalide):
        _c(base=160.0, montant=2600.0)
    with pytest.raises(CorrectionInvalide):
        _c(ligne="cotisation:mutuelle:x", base=10.0, montant_patronal=5.0)


@pytest.mark.parametrize(
    "champs",
    [
        {"motif": "  ", "base": 160.0},
        {"ligne": "", "base": 160.0},
        {"ligne": "ailleurs:x", "base": 160.0},
        {},
        {"taux_salarial": 0.01},
        {"ligne": "impot", "libelle": "Impôt", "taux": 120.0},
    ],
)
def test_une_correction_incomplete_ou_hors_de_sa_ligne_est_refusee(champs):
    with pytest.raises(CorrectionInvalide):
        _c(**champs)


def test_la_charge_utile_ne_porte_que_les_champs_remplis():
    assert _c(base=160.0).charge_utile() == {
        "type": "correction",
        "ligne": "brut:salaire_base",
        "libelle": "Salaire de base",
        "motif": "Avenant",
        "base": 160.0,
    }
    assert _c(base=160.0).trace()["saisie_id"] == "s1"


def test_la_saisie_du_mois_porte_la_correction_sans_montant():
    saisie = _c(base=160.0).saisie_du_mois(PERIODE)
    assert saisie["name"] == "Correction – Salaire de base"
    assert saisie["amount"] == 0 and saisie["description"] == "Avenant"
    assert saisie["correction_ligne"]["type"] == "correction"
    assert saisie["employee_id"] == "e" and saisie["month"] == 10


def test_ranger_une_correction_la_met_a_part_des_primes():
    saisies: dict = {}
    charge = _c(base=160.0).charge_utile()
    assert ranger_correction_manuelle({"id": "s1", "correction_ligne": charge}, saisies)
    assert saisies[CLE_CORRECTIONS_LIGNE] == [{**charge, "saisie_id": "s1"}]
    assert not ranger_correction_manuelle({"id": "s2", "name": "Prime", "correction_ligne": None}, saisies)


def test_ranger_une_regularisation_la_range_comme_a_l_etape_1():
    regul = RegularisationCotisation(coti_id="mutuelle", libelle="Mutuelle", motif="Tarif", montant_patronal=8.3)
    saisies: dict = {}
    assert ranger_correction_manuelle({"id": "r1", "correction_ligne": regul.charge_utile()}, saisies)
    assert saisies[CLE_REGULARISATIONS_COTISATION][0]["saisie_id"] == "r1"
    assert CLE_CORRECTIONS_LIGNE not in saisies


def test_le_journal_ne_se_pose_que_s_il_y_a_des_corrections():
    assert JournalDesCorrections.depuis({}) is None
    assert JournalDesCorrections.depuis({CLE_CORRECTIONS_LIGNE: []}) is None
    journal = JournalDesCorrections.depuis({CLE_CORRECTIONS_LIGNE: [_c(base=160.0).trace()]})
    assert journal is not None and [e["saisie_id"] for e in journal.en_attente()] == ["s1"]


def test_la_base_corrigee_fait_suivre_le_montant_au_centime():
    journal = JournalDesCorrections([_c(base=160.0)])
    ligne = _salaire_de_base()
    effet = journal.corriger(ligne, BLOC_BRUT, "brut:salaire_base")
    assert ligne["quantite"] == 160.0
    assert ligne["gain"] == round(160.0 * 16.4832, 2)
    assert ligne["libelle"] == "Salaire de base"
    assert ligne["valeur_calculee"] == {"quantite": 151.67, "taux": 16.4832, "gain": 2500.0, "perte": None}
    assert ligne["correction"]["motif"] == "Avenant" and ligne["correction"]["saisie_id"] == "s1"
    assert effet.famille == "brut:salaire_base"
    assert effet.quantite == pytest.approx(8.33)
    assert effet.brut == pytest.approx(round(160.0 * 16.4832, 2) - 2500.0)
    assert journal.en_attente() == []


def test_une_retenue_corrigee_par_son_taux_baisse_le_brut():
    ligne = {"libelle": "Absence non rémunérée du 16/03/26", "quantite": 7.0, "taux": 16.0, "gain": None, "perte": 112.0}
    journal = JournalDesCorrections([_c(ligne="brut:absence_non_remuneree:16-03-26", libelle=ligne["libelle"], taux=17.0)])
    effet = journal.corriger(ligne, BLOC_BRUT, "brut:absence_non_remuneree:16-03-26")
    assert ligne["perte"] == 119.0 and ligne["gain"] is None
    assert effet.brut == -7.0 and effet.quantite == 0.0


def test_une_ligne_au_forfait_se_corrige_par_son_montant():
    ligne = {"libelle": "Prime de précarité (CDD)", "quantite": None, "taux": 0.1, "gain": 1100.0, "perte": None}
    journal = JournalDesCorrections([_c(ligne="brut:precarite", libelle=ligne["libelle"], montant=1000.0)])
    journal.corriger(ligne, BLOC_BRUT, "brut:precarite")
    assert ligne["gain"] == 1000.0 and ligne["taux"] == 0.1


def test_une_correction_qui_ne_convient_plus_a_sa_ligne_reste_en_attente():
    ligne = {"libelle": "Prime de précarité (CDD)", "quantite": None, "taux": 0.1, "gain": 1100.0, "perte": None}
    journal = JournalDesCorrections([_c(ligne="brut:precarite", libelle=ligne["libelle"], base=10.0)])
    assert journal.corriger(ligne, BLOC_BRUT, "brut:precarite") is None
    assert ligne["gain"] == 1100.0 and "correction" not in ligne
    attente = journal.en_attente()
    assert attente[0]["saisie_id"] == "s1" and "son montant" in attente[0]["raison"]


def test_une_correction_dont_la_ligne_n_existe_plus_reste_en_attente():
    journal = JournalDesCorrections([_c(base=160.0)])
    journal.corriger({"libelle": "Avantages en nature", "gain": 1.0}, BLOC_BRUT, "brut:avantages_en_nature")
    assert journal.en_attente() == [{**_c(base=160.0).trace(), "raison": RAISON_LIGNE_ABSENTE}]


def test_une_ligne_deja_corrigee_ne_l_est_pas_deux_fois():
    journal = JournalDesCorrections([_c(base=160.0), _c(base=170.0, saisie_id="s2")])
    ligne = _salaire_de_base()
    journal.corriger(ligne, BLOC_BRUT, "brut:salaire_base")
    assert journal.corriger(ligne, BLOC_BRUT, "brut:salaire_base") is None
    assert ligne["quantite"] == 160.0
    assert [e["saisie_id"] for e in journal.en_attente()] == ["s2"]


def test_une_cotisation_corrigee_par_sa_base_garde_son_taux():
    ligne = {"coti_id": "securite_sociale_maladie", "libelle": "Maladie", "base": 2000.0,
             "taux_salarial": 0.0, "taux_patronal": 0.07, "montant_salarial": 0.0, "montant_patronal": 140.0}
    journal = JournalDesCorrections([_c(ligne="cotisation:securite_sociale_maladie", libelle="Maladie", base=2100.0)])
    effet = journal.corriger(ligne, BLOC_COTISATIONS, "cotisation:securite_sociale_maladie")
    assert ligne["montant_patronal"] == 147.0 and ligne["montant_salarial"] == 0.0 and ligne["base"] == 2100.0
    assert ligne["valeur_calculee"]["montant_patronal"] == 140.0
    assert (effet.salarial, effet.patronal) == (0.0, 7.0)


def test_une_mutuelle_se_corrige_par_son_montant():
    ligne = {"coti_id": "mutuelle", "libelle": "Mutuelle", "base": None, "taux_salarial": None,
             "taux_patronal": None, "montant_salarial": 20.0, "montant_patronal": 30.0}
    code = "cotisation:mutuelle:mutuelle"
    journal = JournalDesCorrections([_c(ligne=code, libelle="Mutuelle", montant_salarial=22.5)])
    effet = journal.corriger(ligne, BLOC_COTISATIONS, code)
    assert ligne["montant_salarial"] == 22.5 and ligne["montant_patronal"] == 30.0
    assert effet.salarial == 2.5


def test_les_lignes_corrigees_corrigent_chaque_ligne_a_son_entree():
    lignes = LignesCorrigees(JournalDesCorrections([_c(base=160.0)]), BLOC_BRUT)
    lignes.append(_salaire_de_base())
    lignes.extend([{"libelle": "Avantages en nature", "quantite": None, "taux": None, "gain": 120.0, "perte": None}])
    assert lignes[0]["quantite"] == 160.0 and "correction" not in lignes[1]
    assert lignes.effet.corrigees == 1
    assert lignes.effet.quantite("brut:salaire_base") == pytest.approx(8.33)
    assert lignes.effet.quantite("brut:heures_sup") == 0.0


def test_sans_journal_les_lignes_corrigees_sont_une_liste_ordinaire():
    ligne = _salaire_de_base()
    lignes = LignesCorrigees(None, BLOC_BRUT)
    lignes.append(ligne)
    lignes += [dict(ligne)]
    assert list(lignes) == [_salaire_de_base(), _salaire_de_base()]
    assert lignes.effet.corrigees == 0


def test_deux_lignes_de_meme_code_se_corrigent_chacune_par_son_numero():
    vd = {"coti_id": "vieillesse_deplafonnee", "libelle": "Vieillesse déplafonnée", "base": 2500.0,
          "taux_salarial": 0.004, "taux_patronal": 0.0202, "montant_salarial": 10.0, "montant_patronal": 50.5}
    code = "cotisation:vieillesse_deplafonnee#2"
    lignes = LignesCorrigees(
        JournalDesCorrections([_c(ligne=code, libelle="Vieillesse déplafonnée", base=2600.0)]), BLOC_COTISATIONS
    )
    lignes.extend([dict(vd), dict(vd)])
    assert lignes[0]["base"] == 2500.0 and lignes[1]["base"] == 2600.0


def test_une_passe_de_pipeline_corrige_les_lignes_nees_apres_et_laisse_les_autres():
    deja = _salaire_de_base()
    JournalDesCorrections([_c(base=160.0)]).corriger(deja, BLOC_BRUT, "brut:salaire_base")
    maintien = {"libelle": "Maintien de salaire employeur", "quantite": None, "taux": None, "gain": 300.0,
                "perte": None, "is_maintien_employeur": True}
    journal = JournalDesCorrections(
        [_c(ligne="brut:maintien_employeur", libelle="Maintien de salaire employeur", montant=250.0, saisie_id="s2")]
    )
    effet = corriger_les_lignes_de_gain([deja, maintien], journal)
    assert maintien["gain"] == 250.0 and effet.corrigees == 1 and effet.sur_le_brut("brut:maintien_employeur") == -50.0
    resultats = {"maintien": {"maintien_verse": 300.0}}
    synchroniser_le_maintien(resultats, [deja, maintien])
    assert resultats["maintien"]["maintien_verse"] == 250.0


def test_le_sous_total_suit_le_salaire_de_base_corrige():
    base = {"libelle": "Salaire de base", "quantite": 151.67, "taux": 12.2503, "gain": 1858.01, "perte": None}
    hs = {"libelle": "Heures suppl. structurelles majorées à 25%", "quantite": 17.33, "taux": 15.3129, "gain": 265.37, "perte": None}
    sous_total = {"libelle": "SOUS-TOTAL SALAIRE CONTRACTUEL", "quantite": 169.0, "taux": None, "gain": 2123.38,
                  "perte": None, "is_sous_total": True}
    lignes = [base, hs, sous_total]
    recaler_le_sous_total(lignes)
    assert sous_total["gain"] == 2123.38  # rien de corrigé : intact
    JournalDesCorrections([_c(base=160.0)]).corriger(base, BLOC_BRUT, "brut:salaire_base")
    recaler_le_sous_total(lignes)
    assert sous_total["gain"] == round(base["gain"] + 265.37, 2)
    assert sous_total["quantite"] == round(160.0 + 17.33, 2)


def _rg(montant=-300.0):
    return {"coti_id": "reduction_generale", "libelle": "Réduction générale de cotisations patronales",
            "base": 2000.0, "taux_salarial": None, "taux_patronal": 0.15, "montant_salarial": 0.0,
            "montant_patronal": montant, "valeur_cumulative_a_enregistrer": 2700.0}


def test_la_reduction_generale_corrigee_enregistre_ce_qui_est_applique():
    journal = JournalDesCorrections(
        [_c(ligne="cotisation:reduction_generale", libelle="Réduction générale de cotisations patronales",
            montant_patronal=-250.0)]
    )
    ligne = corriger_la_reduction_generale(_rg(), journal, reduction_deja=2400.0)
    assert ligne["montant_patronal"] == -250.0
    assert ligne["valeur_cumulative_a_enregistrer"] == 2650.0
    assert ligne["valeur_calculee"]["montant_patronal"] == -300.0


def test_une_reduction_de_l_annee_negative_est_refusee():
    journal = JournalDesCorrections(
        [_c(ligne="cotisation:reduction_generale", libelle="Réduction générale de cotisations patronales",
            montant_patronal=150.0)]
    )
    with pytest.raises(CorrectionInvalide):
        corriger_la_reduction_generale(_rg(), journal, reduction_deja=100.0)


def test_sans_correction_la_reduction_est_intacte():
    assert corriger_la_reduction_generale(_rg(), None, 2400.0) == _rg()
    assert corriger_la_reduction_generale(None, JournalDesCorrections([]), 0.0) is None


def test_le_taux_d_impot_du_mois_se_corrige():
    journal = JournalDesCorrections(
        [_c(ligne="impot", libelle="Impôt sur le revenu prélevé à la source", motif="Taux DGFiP du mois", taux=7.5)]
    )
    taux, trace = corriger_le_taux_d_impot(5.2, 2000.0, journal)
    assert taux == 7.5
    assert trace["valeur_calculee"] == {"taux": 5.2, "montant": 104.0}
    assert trace["correction"]["taux"] == 7.5 and trace["correction"]["saisie_id"] == "s1"
    assert journal.en_attente() == []


def test_sans_correction_le_taux_d_impot_est_celui_de_martine():
    assert corriger_le_taux_d_impot(5.2, 2000.0, None) == (5.2, None)
    assert corriger_le_taux_d_impot(5.2, 2000.0, JournalDesCorrections([_c(base=160.0)])) == (5.2, None)


def test_les_corrections_en_attente_vont_sur_le_bulletin_et_seulement_elles():
    bulletin: dict = {}
    poser_les_corrections_en_attente(bulletin, None)
    poser_les_corrections_en_attente(bulletin, JournalDesCorrections([]))
    assert CLE_CORRECTIONS_EN_ATTENTE not in bulletin
    poser_les_corrections_en_attente(bulletin, JournalDesCorrections([_c(base=160.0)]))
    assert bulletin[CLE_CORRECTIONS_EN_ATTENTE][0]["saisie_id"] == "s1"
```

- [ ] **Étape 2 : lancer les tests pour les voir échouer**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_corrections_de_ligne.py -q
```

Attendu : `ImportError: cannot import name 'CLE_CORRECTIONS_EN_ATTENTE'`.

- [ ] **Étape 3 : écrire l'implémentation**

Dans `backend/app/modules/payroll/engine/corrections_manuelles.py`, remplacer `from dataclasses import dataclass` par `from dataclasses import dataclass, field`, compléter la docstring du module par le paragraphe :

```python
"""…

Étape 2 : la correction directe d'une ligne. Elle vise une ligne par son code
(`codes_des_lignes`) et porte sa base, son taux ou son montant selon la règle
3. Le moteur la pose là où la ligne naît (`LignesCorrigees`), avant tout ce qui
en dérive ; la ligne garde son libellé, porte la trace de la correction et la
valeur que Martine avait calculée. Une correction qui ne trouve pas sa ligne
reste en attente sur le bulletin.
"""
```

puis ajouter l'import suivant en tête du fichier, avec les autres (sans le `# noqa: E402`), et tout le reste du bloc en fin de fichier :

```python
# --- Étape 2 : la correction directe d'une ligne ----------------------------

from app.modules.payroll.engine.codes_des_lignes import (  # noqa: E402
    BLOC_BRUT,
    BLOC_COTISATIONS,
    BLOC_IMPOT,
    CODE_IMPOT,
    MODE_BASE_OU_TAUX,
    MODE_MONTANT,
    MODE_TAUX,
    Numerotation,
    champ_du_montant,
    code_de_ligne_de_cotisation,
    code_de_ligne_de_gain,
    famille_du_code,
    mode_de_correction,
)

TYPE_CORRECTION = "correction"
CLE_CORRECTIONS_LIGNE = "corrections_ligne"
CLE_CORRECTIONS_EN_ATTENTE = "corrections_en_attente"
PREFIXE_SAISIE_CORRECTION = "Correction – "

RAISON_LIGNE_ABSENTE = (
    "La ligne visée n'est plus sur le bulletin : sa source a changé. Retirez la "
    "correction ou reportez-la sur une autre ligne."
)

#: Comment la ligne se corrige, pour les messages.
PAR_MODE = {
    MODE_BASE_OU_TAUX: "sa base ou son taux",
    MODE_MONTANT: "son montant",
    MODE_TAUX: "son taux",
}

_VALEURS = (
    "base",
    "taux",
    "montant",
    "taux_salarial",
    "taux_patronal",
    "montant_salarial",
    "montant_patronal",
)
_CHAMPS_DE_MONTANT = frozenset({"montant", "montant_salarial", "montant_patronal"})
_CHAMPS_PAR_BLOC = {
    BLOC_BRUT: frozenset({"base", "taux", "montant"}),
    BLOC_COTISATIONS: frozenset(
        {"base", "taux_salarial", "taux_patronal", "montant_salarial", "montant_patronal"}
    ),
    BLOC_IMPOT: frozenset({"taux"}),
}
_CHAMPS_PERMIS = {
    (BLOC_BRUT, MODE_BASE_OU_TAUX): frozenset({"base", "taux"}),
    (BLOC_BRUT, MODE_MONTANT): frozenset({"montant"}),
    (BLOC_COTISATIONS, MODE_BASE_OU_TAUX): frozenset({"base", "taux_salarial", "taux_patronal"}),
    (BLOC_COTISATIONS, MODE_MONTANT): frozenset({"montant_salarial", "montant_patronal"}),
    (BLOC_IMPOT, MODE_TAUX): frozenset({"taux"}),
}


class CorrectionInvalide(ValueError):
    """Une correction qu'on ne peut ni enregistrer ni appliquer telle quelle."""


def bloc_du_code(code: str) -> str | None:
    if code == CODE_IMPOT:
        return BLOC_IMPOT
    if code.startswith("brut:"):
        return BLOC_BRUT
    if code.startswith("cotisation:"):
        return BLOC_COTISATIONS
    return None


def _zero_si_vide(valeur: Any) -> float:
    nombre = _nombre(valeur)
    return 0.0 if nombre is None else nombre


@dataclass(frozen=True)
class CorrectionDeLigne:
    ligne: str
    libelle: str
    motif: str
    base: float | None = None
    taux: float | None = None
    montant: float | None = None
    taux_salarial: float | None = None
    taux_patronal: float | None = None
    montant_salarial: float | None = None
    montant_patronal: float | None = None
    saisie_id: str | None = None

    def __post_init__(self) -> None:
        if not self.ligne.strip():
            raise CorrectionInvalide("Choisissez la ligne à corriger.")
        if not self.libelle.strip():
            raise CorrectionInvalide("La ligne à corriger n'a pas de libellé.")
        if len(self.motif.strip()) < 3:
            raise CorrectionInvalide("Écrivez le motif de la correction.")
        bloc = bloc_du_code(self.ligne)
        if bloc is None:
            raise CorrectionInvalide("Martine ne connaît pas cette ligne.")
        champs = self.champs
        if not champs:
            raise CorrectionInvalide("Tapez la valeur voulue.")
        if not champs <= _CHAMPS_PAR_BLOC[bloc]:
            raise CorrectionInvalide("Ces valeurs ne se corrigent pas sur cette ligne.")
        if champs & _CHAMPS_DE_MONTANT and champs - _CHAMPS_DE_MONTANT:
            raise CorrectionInvalide(
                "Une correction porte une base ou un taux, ou bien un montant, jamais les deux."
            )
        if bloc == BLOC_IMPOT and not 0.0 <= float(self.taux or 0.0) <= 100.0:
            raise CorrectionInvalide("Le taux d'impôt se tape en pourcentage, entre 0 et 100.")

    @property
    def bloc(self) -> str:
        return bloc_du_code(self.ligne) or ""

    @property
    def champs(self) -> frozenset[str]:
        return frozenset(nom for nom in _VALEURS if getattr(self, nom) is not None)

    @property
    def par_montant(self) -> bool:
        return bool(self.champs & _CHAMPS_DE_MONTANT)

    def convient(self, mode: str | None) -> bool:
        permis = _CHAMPS_PERMIS.get((self.bloc, mode))
        return permis is not None and self.champs <= permis

    def charge_utile(self) -> dict[str, Any]:
        """Ce qui s'enregistre dans monthly_inputs.correction_ligne."""
        charge: dict[str, Any] = {
            "type": TYPE_CORRECTION,
            "ligne": self.ligne,
            "libelle": self.libelle,
            "motif": self.motif.strip(),
        }
        charge.update({nom: getattr(self, nom) for nom in _VALEURS if getattr(self, nom) is not None})
        return charge

    def trace(self) -> dict[str, Any]:
        """Ce que porte la ligne corrigée : la correction et la saisie qui la porte."""
        return {**self.charge_utile(), "saisie_id": self.saisie_id}

    @classmethod
    def depuis(cls, donnees: Mapping[str, Any], saisie_id: str | None = None) -> CorrectionDeLigne:
        identifiant = saisie_id or donnees.get("saisie_id")
        return cls(
            ligne=str(donnees.get("ligne") or ""),
            libelle=str(donnees.get("libelle") or ""),
            motif=str(donnees.get("motif") or ""),
            **{nom: _nombre(donnees.get(nom)) for nom in _VALEURS},
            saisie_id=str(identifiant) if identifiant else None,
        )

    def saisie_du_mois(self, periode: Mapping[str, Any]) -> dict[str, Any]:
        """La ligne monthly_inputs qui porte la correction."""
        return {
            **periode,
            "name": f"{PREFIXE_SAISIE_CORRECTION}{self.libelle}"[:120],
            "description": self.motif.strip(),
            "amount": 0,
            "is_socially_taxed": False,
            "is_taxable": False,
            "correction_ligne": self.charge_utile(),
        }


def est_correction_de_ligne(saisie: Mapping[str, Any]) -> bool:
    correction = saisie.get("correction_ligne")
    return isinstance(correction, Mapping) and correction.get("type") == TYPE_CORRECTION


def ranger_correction_manuelle(saisie: Mapping[str, Any], saisies_data: dict[str, Any]) -> bool:
    """Range une régularisation ou une correction de ligne à part des primes.

    Dit si la saisie en était une : elle n'est alors pas une prime du bulletin.
    """
    if ranger_regularisation(saisie, saisies_data):
        return True
    if not est_correction_de_ligne(saisie):
        return False
    entree = dict(saisie["correction_ligne"])
    if saisie.get("id"):
        entree["saisie_id"] = str(saisie["id"])
    saisies_data.setdefault(CLE_CORRECTIONS_LIGNE, []).append(entree)
    return True


@dataclass(frozen=True)
class EffetUnitaire:
    famille: str
    quantite: float = 0.0
    brut: float = 0.0
    salarial: float = 0.0
    patronal: float = 0.0


@dataclass
class EffetDesCorrections:
    """Ce que les corrections d'un lot de lignes ont changé, par famille de ligne."""

    corrigees: int = 0
    salarial: float = 0.0
    patronal: float = 0.0
    _quantites: dict[str, float] = field(default_factory=dict)
    _brut: dict[str, float] = field(default_factory=dict)

    def ajouter(self, effet: EffetUnitaire | None) -> None:
        if effet is None:
            return
        self.corrigees += 1
        self.salarial = round(self.salarial + effet.salarial, 2)
        self.patronal = round(self.patronal + effet.patronal, 2)
        self._quantites[effet.famille] = self._quantites.get(effet.famille, 0.0) + effet.quantite
        self._brut[effet.famille] = round(self._brut.get(effet.famille, 0.0) + effet.brut, 2)

    def quantite(self, *familles: str) -> float:
        return round(sum((self._quantites.get(f, 0.0) for f in familles), 0.0), 4)

    def sur_le_brut(self, *familles: str) -> float:
        return round(sum((self._brut.get(f, 0.0) for f in familles), 0.0), 2)


def _corriger_un_gain(ligne: dict[str, Any], correction: CorrectionDeLigne) -> EffetUnitaire:
    champ = champ_du_montant(ligne)
    avant = {cle: ligne.get(cle) for cle in ("quantite", "taux", "gain", "perte")}
    if correction.montant is not None:
        ligne[champ] = round(float(correction.montant), 2)
    else:
        quantite = correction.base if correction.base is not None else _zero_si_vide(ligne.get("quantite"))
        taux = correction.taux if correction.taux is not None else _zero_si_vide(ligne.get("taux"))
        ligne["quantite"] = quantite
        ligne["taux"] = taux
        ligne[champ] = round(float(quantite) * float(taux), 2)
    ligne["valeur_calculee"] = avant
    ligne["correction"] = correction.trace()
    signe = 1.0 if champ == "gain" else -1.0
    return EffetUnitaire(
        famille=famille_du_code(correction.ligne),
        quantite=_zero_si_vide(ligne.get("quantite")) - _zero_si_vide(avant["quantite"]),
        brut=round(signe * (_zero_si_vide(ligne[champ]) - _zero_si_vide(avant[champ])), 2),
    )


def _corriger_une_cotisation(ligne: dict[str, Any], correction: CorrectionDeLigne) -> EffetUnitaire:
    cles = ("base", "taux_salarial", "taux_patronal", "montant_salarial", "montant_patronal")
    avant = {cle: ligne.get(cle) for cle in cles}
    if correction.par_montant:
        if correction.montant_salarial is not None:
            ligne["montant_salarial"] = round(float(correction.montant_salarial), 2)
        if correction.montant_patronal is not None:
            ligne["montant_patronal"] = round(float(correction.montant_patronal), 2)
    else:
        base = correction.base if correction.base is not None else _zero_si_vide(ligne.get("base"))
        if correction.taux_salarial is not None:
            ligne["taux_salarial"] = correction.taux_salarial
        if correction.taux_patronal is not None:
            ligne["taux_patronal"] = correction.taux_patronal
        ligne["base"] = base
        # Le même arrondi que `calcul_cotisations._calculer_une_ligne`.
        if ligne.get("taux_salarial") is not None:
            ligne["montant_salarial"] = round(float(base) * float(ligne["taux_salarial"]), 2)
        if ligne.get("taux_patronal") is not None:
            ligne["montant_patronal"] = round(float(base) * float(ligne["taux_patronal"]), 2)
    ligne["valeur_calculee"] = avant
    ligne["correction"] = correction.trace()
    return EffetUnitaire(
        famille=famille_du_code(correction.ligne),
        salarial=round(_zero_si_vide(ligne.get("montant_salarial")) - _zero_si_vide(avant["montant_salarial"]), 2),
        patronal=round(_zero_si_vide(ligne.get("montant_patronal")) - _zero_si_vide(avant["montant_patronal"]), 2),
    )


class JournalDesCorrections:
    """Les corrections du mois, et ce que le calcul en a fait."""

    def __init__(self, corrections: Iterable[CorrectionDeLigne]) -> None:
        self._a_poser: dict[str, list[CorrectionDeLigne]] = {}
        for correction in corrections:
            self._a_poser.setdefault(correction.ligne, []).append(correction)
        self._refusees: list[tuple[CorrectionDeLigne, str]] = []

    @classmethod
    def depuis(cls, saisie_du_mois: Mapping[str, Any]) -> JournalDesCorrections | None:
        entrees = saisie_du_mois.get(CLE_CORRECTIONS_LIGNE) or []
        if not entrees:
            return None
        return cls(CorrectionDeLigne.depuis(entree) for entree in entrees)

    def prendre(self, code: str | None) -> CorrectionDeLigne | None:
        if not code:
            return None
        file = self._a_poser.get(code)
        if not file:
            return None
        correction = file.pop(0)
        if not file:
            del self._a_poser[code]
        return correction

    def refuser(self, correction: CorrectionDeLigne, raison: str) -> None:
        self._refusees.append((correction, raison))

    def corriger(self, ligne: Any, bloc: str, code: str | None) -> EffetUnitaire | None:
        """Pose sur la ligne la correction qui la vise, s'il y en a une."""
        if not isinstance(ligne, dict) or ligne.get("correction") is not None:
            return None
        correction = self.prendre(code)
        if correction is None:
            return None
        mode, raison = mode_de_correction(bloc, ligne, code)
        if mode is None:
            self.refuser(correction, raison or RAISON_LIGNE_ABSENTE)
            return None
        if not correction.convient(mode):
            self.refuser(correction, f"La ligne se corrige par {PAR_MODE[mode]} : refaites la correction.")
            return None
        if bloc == BLOC_BRUT:
            return _corriger_un_gain(ligne, correction)
        return _corriger_une_cotisation(ligne, correction)

    def en_attente(self) -> list[dict[str, Any]]:
        """Les corrections qui n'ont pas trouvé leur ligne, avec la raison."""
        restantes = [(c, RAISON_LIGNE_ABSENTE) for file in self._a_poser.values() for c in file]
        return [{**c.trace(), "raison": raison} for c, raison in [*self._refusees, *restantes]]


def journal_du_contexte(contexte: Any) -> JournalDesCorrections | None:
    journal = getattr(contexte, "corrections_du_mois", None)
    return journal if isinstance(journal, JournalDesCorrections) else None


class LignesCorrigees(list):
    """Les lignes d'un calcul, chacune corrigée à son entrée si une correction la vise.

    Les deux calculs du brut et celui des cotisations y posent leurs lignes : la
    correction s'applique là où la ligne naît, avant tout ce qui en dérive
    (précarité, indemnité compensatrice, heures sup, plafond de la réduction
    des heures sup, forfait social). Sans journal, c'est une liste ordinaire.
    """

    def __init__(self, journal: JournalDesCorrections | None, bloc: str, lignes: Iterable[Any] = ()) -> None:
        super().__init__()
        self.journal = journal
        self.bloc = bloc
        self.effet = EffetDesCorrections()
        self._numeros = Numerotation()
        for ligne in lignes:
            self.append(ligne)

    def _poser(self, ligne: Any) -> Any:
        if self.journal is not None and isinstance(ligne, dict):
            self.effet.ajouter(self.journal.corriger(ligne, self.bloc, self._numeros.code(self.bloc, ligne)))
        return ligne

    def append(self, ligne: Any) -> None:
        super().append(self._poser(ligne))

    def extend(self, lignes: Iterable[Any]) -> None:
        for ligne in lignes:
            self.append(ligne)

    def insert(self, index: Any, ligne: Any) -> None:
        super().insert(index, self._poser(ligne))

    def __iadd__(self, lignes: Iterable[Any]) -> LignesCorrigees:
        self.extend(lignes)
        return self


def _corriger_les_lignes(lignes: Iterable[Any], journal: JournalDesCorrections | None, bloc: str) -> EffetDesCorrections:
    effet = EffetDesCorrections()
    if journal is None:
        return effet
    numeros = Numerotation()
    for ligne in lignes:
        if isinstance(ligne, dict):
            effet.ajouter(journal.corriger(ligne, bloc, numeros.code(bloc, ligne)))
    return effet


def corriger_les_lignes_de_gain(lignes: Iterable[Any], journal: JournalDesCorrections | None) -> EffetDesCorrections:
    """Les lignes de gain posées après le calcul du brut (nuit, pause, maintien)."""
    return _corriger_les_lignes(lignes, journal, BLOC_BRUT)


def corriger_les_lignes_de_cotisation(
    lignes: Iterable[Any], journal: JournalDesCorrections | None
) -> EffetDesCorrections:
    """Les cotisations posées après `calculer_cotisations` (CSG des IJSS, JEI)."""
    return _corriger_les_lignes(lignes, journal, BLOC_COTISATIONS)


def recaler_le_sous_total(lignes: Iterable[Any]) -> None:
    """Le sous-total contractuel suit un salaire de base ou des heures structurelles corrigés."""
    lignes = [ligne for ligne in lignes if isinstance(ligne, dict)]
    composantes = [
        ligne
        for ligne in lignes
        if famille_du_code(code_de_ligne_de_gain(ligne)) in ("brut:salaire_base", "brut:hs_structurelles")
    ]
    if not any(ligne.get("correction") for ligne in composantes):
        return
    for ligne in lignes:
        if ligne.get("is_sous_total"):
            ligne["gain"] = round(sum(_zero_si_vide(c.get("gain")) for c in composantes), 2)
            ligne["quantite"] = round(sum(_zero_si_vide(c.get("quantite")) for c in composantes), 2)


def synchroniser_le_maintien(resultats_maintien: Any, lignes: Iterable[Any]) -> None:
    """Un maintien employeur corrigé devient le maintien versé (part des heures maintenues, détail du bulletin)."""
    if not isinstance(resultats_maintien, dict):
        return
    for ligne in lignes:
        if isinstance(ligne, dict) and ligne.get("is_maintien_employeur") and ligne.get("correction"):
            bloc = resultats_maintien.get("maintien")
            if not isinstance(bloc, dict):
                bloc = resultats_maintien["maintien"] = {}
            bloc["maintien_verse"] = _zero_si_vide(ligne.get("gain"))


def corriger_la_reduction_generale(
    ligne: dict[str, Any] | None, journal: JournalDesCorrections | None, reduction_deja: float
) -> dict[str, Any] | None:
    """La réduction générale du mois, corrigée par son montant.

    Son cumul enregistre ce qui est réellement appliqué (spec § 6) : le mois
    suivant régularise depuis là, comme le veut la loi.
    """
    if ligne is None or journal is None:
        return ligne
    if journal.corriger(ligne, BLOC_COTISATIONS, code_de_ligne_de_cotisation(ligne)) is None:
        return ligne
    appliquee = round(float(reduction_deja) - _zero_si_vide(ligne.get("montant_patronal")), 2)
    if appliquee < 0:
        raise CorrectionInvalide(
            "La réduction générale corrigée dépasse la réduction appliquée depuis janvier : "
            "la réduction de l'année deviendrait négative. Corrigez son montant."
        )
    ligne["valeur_cumulative_a_enregistrer"] = appliquee
    return ligne


def corriger_le_taux_d_impot(
    taux_calcule: float, base_pas: float, journal: JournalDesCorrections | None
) -> tuple[float, dict[str, Any] | None]:
    """Le taux d'impôt du mois, corrigé ; le montant suit (base × taux, au centime)."""
    if journal is None:
        return taux_calcule, None
    correction = journal.prendre(CODE_IMPOT)
    if correction is None:
        return taux_calcule, None
    if not correction.convient(MODE_TAUX):
        journal.refuser(correction, f"La ligne se corrige par {PAR_MODE[MODE_TAUX]} : refaites la correction.")
        return taux_calcule, None
    trace = {
        "correction": correction.trace(),
        "valeur_calculee": {
            "taux": taux_calcule,
            "montant": round(base_pas * (taux_calcule / 100.0), 2),
        },
    }
    return float(correction.taux), trace


def poser_les_corrections_en_attente(bulletin: dict[str, Any], journal: JournalDesCorrections | None) -> None:
    """Règle 7 : une correction sans ligne n'est jamais perdue en silence."""
    if journal is None:
        return
    attente = journal.en_attente()
    if attente:
        bulletin[CLE_CORRECTIONS_EN_ATTENTE] = attente
```

- [ ] **Étape 4 : relancer les tests de la tâche et ceux de l'étape 1**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_corrections_de_ligne.py tests/unit/payroll/test_corrections_manuelles.py tests/unit/payroll/test_codes_des_lignes.py -q
```

Attendu : tout passe.

- [ ] **Étape 5 : commiter**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2 && git add backend/app/modules/payroll/engine/corrections_manuelles.py backend/tests/unit/payroll/test_corrections_de_ligne.py && git commit -m "feat(paie): une ligne se corrige par sa base, son taux ou son montant, et le journal du mois garde celles qui n'ont pas trouvé leur ligne

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 3 : les gains au mensuel — corrigés à leur naissance, et ce qui en dérive suit

**Fichiers :**
- Modifier : `backend/app/modules/payroll/engine/calcul_brut.py` (import ; `lignes_composants_brut = []` dans `calculer_salaire_brut` ; bloc avant `# Le calcul du brut total reste inchangé` ; heures sup, heures complémentaires, retour)
- Tester : `backend/tests/unit/payroll/test_corrections_gains_mensuel.py` (créé)

**Interfaces :**
- Consomme : `LignesCorrigees`, `journal_du_contexte`, `recaler_le_sous_total`, `JournalDesCorrections`, `CorrectionDeLigne` (tâche 2) ; `BLOC_BRUT`, `code_de_ligne` (tâche 1).
- Produit : `calculer_salaire_brut` lit `contexte.corrections_du_mois` (absent = aucun changement). Ses sorties `salaire_brut_total`, `lignes_composants_brut` (une liste ordinaire), `remuneration_brute_heures_supp`, `total_heures_supp`, `heures_base_remunerees`, `heures_absence_non_payees`, `heures_sup_perdues_absence`, `deduction_arret_maladie`, `heures_arret_deduites`, `heures_complementaires` suivent les lignes corrigées. Le pipeline les passe déjà à la réduction générale et aux cumuls (`heures_remunerees`, `heures_supplementaires_remunerees`, `montant_hs_remunerees`) : spec § 6, « quantités ».

- [ ] **Étape 1 : écrire les tests qui échouent**

Créer `backend/tests/unit/payroll/test_corrections_gains_mensuel.py` :

```python
"""Une ligne de gain corrigée au mensuel : ce qui en dérive suit (spec § 5 et § 6).

Le brut, la précarité, l'indemnité compensatrice, la rémunération et les heures
des heures sup, le sous-total contractuel et les heures du SMIC de référence
partent des lignes corrigées. Sans correction, rien ne bouge.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.codes_des_lignes import BLOC_BRUT, code_de_ligne
from app.modules.payroll.engine.corrections_manuelles import CorrectionDeLigne, JournalDesCorrections

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

JANVIER = (date(2026, 1, 1), date(2026, 1, 31))


def _calendrier(hs=None, absences=None, heures_jour=7.0):
    cal = []
    jour = date(2026, 1, 1)
    while jour.month == 1:
        if jour.weekday() < 5:
            cal.append({"date_complete": jour.isoformat(), "type": "travail_base", "heures": heures_jour})
        jour = date.fromordinal(jour.toordinal() + 1)
    for iso, (type_ev, heures) in (hs or {}).items():
        cal.append({"date_complete": iso, "type": type_ev, "heures": heures})
    for iso, heures in (absences or {}).items():
        cal.append({"date_complete": iso, "type": "absence_injustifiee_base", "heures": heures})
    return cal


def _contexte(*corrections, **options):
    contexte = build_test_contexte(**options)
    contexte.year = 2026
    if corrections:
        contexte.corrections_du_mois = JournalDesCorrections(list(corrections))
    return contexte


def _ligne(resultat, code):
    return next(l for l in resultat["lignes_composants_brut"] if code_de_ligne(BLOC_BRUT, l) == code)


def _c(code, libelle, **champs):
    return CorrectionDeLigne(ligne=code, libelle=libelle, motif="Test", saisie_id="s1", **champs)


def test_sans_correction_le_brut_est_identique():
    cal = _calendrier(hs={"2026-01-15": ("travail_hs25", 4.0)}, absences={"2026-01-21": 3.5})
    reference = calculer_salaire_brut(_contexte(), cal, *JANVIER, [])
    avec_journal_vide = _contexte()
    avec_journal_vide.corrections_du_mois = JournalDesCorrections([])
    assert calculer_salaire_brut(avec_journal_vide, cal, *JANVIER, []) == reference
    assert type(reference["lignes_composants_brut"]) is list


def test_la_base_du_salaire_de_base_corrigee_suit_dans_le_brut_et_les_heures():
    reference = calculer_salaire_brut(_contexte(), _calendrier(), *JANVIER, [])
    base0 = _ligne(reference, "brut:salaire_base")
    corrige = calculer_salaire_brut(
        _contexte(_c("brut:salaire_base", "Salaire de base", base=160.0)), _calendrier(), *JANVIER, []
    )
    base1 = _ligne(corrige, "brut:salaire_base")
    attendu = round(160.0 * base0["taux"], 2)
    assert base1["gain"] == attendu and base1["valeur_calculee"]["gain"] == base0["gain"]
    assert corrige["salaire_brut_total"] == pytest.approx(reference["salaire_brut_total"] + attendu - base0["gain"], abs=0.005)
    assert corrige["heures_base_remunerees"] == pytest.approx(160.0)


def test_des_heures_sup_corrigees_suivent_dans_leurs_heures_et_leur_remuneration():
    cal = _calendrier(hs={"2026-01-15": ("travail_hs25", 4.0)})
    reference = calculer_salaire_brut(_contexte(), cal, *JANVIER, [])
    hs0 = _ligne(reference, "brut:heures_sup:25")
    corrige = calculer_salaire_brut(
        _contexte(_c("brut:heures_sup:25", hs0["libelle"], base=6.0)), cal, *JANVIER, []
    )
    hs1 = _ligne(corrige, "brut:heures_sup:25")
    assert hs1["gain"] == round(6.0 * hs0["taux"], 2)
    assert corrige["total_heures_supp"] == pytest.approx(reference["total_heures_supp"] + 2.0)
    assert corrige["remuneration_brute_heures_supp"] == pytest.approx(
        reference["remuneration_brute_heures_supp"] + hs1["gain"] - hs0["gain"], abs=0.005
    )


def test_une_absence_corrigee_suit_dans_les_heures_non_payees():
    cal = _calendrier(absences={"2026-01-21": 3.5})
    reference = calculer_salaire_brut(_contexte(), cal, *JANVIER, [])
    code = "brut:absence_injustifiee:du-21-01-26-base"
    abs0 = _ligne(reference, code)
    corrige = calculer_salaire_brut(_contexte(_c(code, abs0["libelle"], base=7.0)), cal, *JANVIER, [])
    abs1 = _ligne(corrige, code)
    assert abs1["perte"] == round(7.0 * abs0["taux"], 2)
    assert corrige["heures_absence_non_payees"] == pytest.approx(reference["heures_absence_non_payees"] + 3.5)
    assert corrige["salaire_brut_total"] == pytest.approx(
        reference["salaire_brut_total"] - (abs1["perte"] - abs0["perte"]), abs=0.005
    )


def test_le_sous_total_et_les_heures_structurelles_suivent():
    options = dict(salaire_base=2123.38, duree_hebdo=39.0)
    # Les heures structurelles viennent du contrat, pas du planning : le
    # calendrier ordinaire suffit (sonde du 23/10 : base, structurelles, sous-total).
    reference = calculer_salaire_brut(_contexte(**options), _calendrier(), *JANVIER, [])
    hs0 = _ligne(reference, "brut:hs_structurelles")
    corrige = calculer_salaire_brut(
        _contexte(_c("brut:hs_structurelles", hs0["libelle"], base=20.0), **options),
        _calendrier(),
        *JANVIER,
        [],
    )
    hs1 = _ligne(corrige, "brut:hs_structurelles")
    sous_total = _ligne(corrige, "brut:sous_total")
    assert sous_total["gain"] == round(_ligne(corrige, "brut:salaire_base")["gain"] + hs1["gain"], 2)
    assert corrige["total_heures_supp"] == pytest.approx(reference["total_heures_supp"] + 20.0 - hs0["quantite"])
    assert corrige["remuneration_brute_heures_supp"] == pytest.approx(
        reference["remuneration_brute_heures_supp"] + hs1["gain"] - hs0["gain"], abs=0.005
    )


def _cdd(*corrections):
    contexte = _contexte(
        *corrections,
        salaire_base=2200.0,
        type_contrat="CDD",
        date_entree="2025-10-01",
        date_fin_contrat="2026-04-30",
        cumuls={"brut_total": 8800.0},
        specificites_extra={"dsn_reprise": {"motif_recours": "02"}},
    )
    return calculer_salaire_brut(contexte, [], date(2026, 4, 1), date(2026, 4, 30), [])


def test_la_precarite_et_l_indemnite_compensatrice_suivent_le_salaire_corrige():
    reference = _cdd()
    assert _ligne(reference, "brut:precarite")["gain"] == pytest.approx(1100.0)
    corrige = _cdd(_c("brut:salaire_base", "Salaire de base", base=160.0))
    gain = _ligne(corrige, "brut:salaire_base")["gain"]
    precarite = _ligne(corrige, "brut:precarite")["gain"]
    assert precarite == pytest.approx(round((8800.0 + gain) * 0.1, 2), abs=0.01)
    assert _ligne(corrige, "brut:iccp:cdd")["gain"] == pytest.approx(round((8800.0 + gain + precarite) * 0.1, 2), abs=0.01)


def test_l_indemnite_compensatrice_suit_la_precarite_corrigee():
    corrige = _cdd(_c("brut:precarite", "Prime de précarité (CDD)", montant=1000.0))
    assert _ligne(corrige, "brut:precarite")["gain"] == 1000.0
    assert _ligne(corrige, "brut:iccp:cdd")["gain"] == pytest.approx(1200.0, abs=0.01)
```

Note : les chiffres du CDD viennent d'une sonde du 23/10 sur ces mêmes entrées (base 2 200 €, précarité 1 100 €, indemnité compensatrice 1 210 €, soit le dixième de 8 800 + 2 200 + 1 100).

- [ ] **Étape 2 : lancer les tests pour les voir échouer**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_corrections_gains_mensuel.py -q
```

Attendu : `test_sans_correction_le_brut_est_identique` passe déjà ; les autres échouent (`AssertionError`, la ligne n'est pas corrigée).

- [ ] **Étape 3 : poser les lignes dans `LignesCorrigees`**

Dans `backend/app/modules/payroll/engine/calcul_brut.py`, ajouter aux imports :

```python
from app.modules.payroll.engine.codes_des_lignes import BLOC_BRUT
from app.modules.payroll.engine.corrections_manuelles import (
    LignesCorrigees,
    journal_du_contexte,
    recaler_le_sous_total,
)
```

Dans `calculer_salaire_brut`, remplacer `lignes_composants_brut = []` par :

```python
    # Chaque ligne naît corrigée si une correction faite à la main la vise
    # (théorème de la correction à la main, étape 2) : tout ce qui se calcule
    # ensuite depuis les lignes (précarité, indemnité compensatrice, heures sup)
    # part de la valeur voulue.
    lignes_composants_brut = LignesCorrigees(journal_du_contexte(contexte), BLOC_BRUT)
```

- [ ] **Étape 4 : faire suivre ce que le calcul tient à part des lignes**

Juste avant la ligne `    # Le calcul du brut total reste inchangé`, insérer :

```python
    # Les heures et montants que le calcul tient à part des lignes suivent les
    # lignes corrigées (spec § 6, quantités) : heures payées, heures sup
    # structurelles, absences non payées, arrêts, heures sup perdues.
    effet = lignes_composants_brut.effet
    if effet.corrigees:
        heures_base_remunerees = round(heures_base_remunerees + effet.quantite("brut:salaire_base"), 2)
        heures_sup_structurelles_mensuelles = round(
            heures_sup_structurelles_mensuelles + effet.quantite("brut:hs_structurelles"), 2
        )
        remuneration_hs_structurelles = round(
            remuneration_hs_structurelles + effet.sur_le_brut("brut:hs_structurelles"), 2
        )
        heures_absence_non_payees += effet.quantite(
            "brut:absence_injustifiee", "brut:absence_non_remuneree", "brut:absence_ferie_non_paye"
        )
        heures_arret_deduites += effet.quantite("brut:arret")
        deduction_arret_maladie_total -= effet.sur_le_brut("brut:arret")
        heures_hs_perdues = round(heures_hs_perdues + effet.quantite("brut:reduction_hs_absence"), 2)
        recaler_le_sous_total(lignes_composants_brut)
```

Puis, plus bas dans la même fonction :

```python
    # avant
    heures_sup_conjoncturelles = heures_travail_hs25_total + heures_travail_hs50_total
    # après
    heures_sup_conjoncturelles = (
        heures_travail_hs25_total + heures_travail_hs50_total + effet.quantite("brut:heures_sup")
    )
```

```python
    # avant
    if heures_hs_exonerees is not None:
        total_heures_supp_mois = heures_hs_exonerees
    if montant_hs_exonerees is not None:
        remuneration_hs_totale = montant_hs_exonerees
    # après
    if heures_hs_exonerees is not None:
        total_heures_supp_mois = heures_hs_exonerees + effet.quantite(
            "brut:heures_sup", "brut:hs_structurelles"
        )
    if montant_hs_exonerees is not None:
        remuneration_hs_totale = montant_hs_exonerees + effet.sur_le_brut(
            "brut:heures_sup", "brut:hs_structurelles", "brut:heures_complementaires"
        )
```

Dans les deux expressions des heures complémentaires (`contexte.heures_complementaires_mois = round(...)` et la clé `"heures_complementaires"` du retour), remplacer `heures_travail_hc1_total + heures_travail_hc2_total` par `heures_travail_hc1_total + heures_travail_hc2_total + effet.quantite("brut:heures_complementaires")`. Enfin, dans le `return`, remplacer `"lignes_composants_brut": lignes_composants_brut,` par `"lignes_composants_brut": list(lignes_composants_brut),`.

`effet.quantite(...)` et `effet.sur_le_brut(...)` valent `0.0` sans correction : ajouter `0.0` ne change aucun flottant.

- [ ] **Étape 5 : relancer les tests de la tâche et les tests du brut**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_corrections_gains_mensuel.py tests/unit/payroll/test_compteurs_heures_bulletin.py tests/unit/payroll/test_lien_saisie.py tests/unit/payroll/test_absence_mois_complet.py tests/unit/payroll/test_arret_maladie_deduction.py tests/unit/payroll/test_golden_bulletins.py tests/unit/employee_exits/test_precarite_non_due.py -q
```

Attendu : tout passe.

- [ ] **Étape 6 : commiter**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2 && git add backend/app/modules/payroll/engine/calcul_brut.py backend/tests/unit/payroll/test_corrections_gains_mensuel.py && git commit -m "feat(paie): une ligne de gain corrigée au mensuel fait suivre la précarité, l'indemnité compensatrice, les heures sup et les heures payées

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 4 : les gains au forfait jours

**Fichiers :**
- Modifier : `backend/app/modules/payroll/engine/calcul_brut_forfait.py` (import, constante, `lignes_composants_brut = []` dans `calculer_salaire_brut_forfait`, bloc avant `total_gains = sum(`, `salaire_base_seul`, retour)
- Tester : `backend/tests/unit/payroll/test_corrections_gains_forfait.py` (créé)

**Interfaces :**
- Consomme : comme la tâche 3.
- Produit : `FAMILLES_RETENUES_FORFAIT: tuple[str, ...]` dans `calcul_brut_forfait` ; `calculer_salaire_brut_forfait` rend `salaire_forfait_mois` et `retenues_absence_mois` (le rapport des salaires de la réduction générale au forfait, `rapport_salaires_forfait_jours`) qui suivent les lignes corrigées.

- [ ] **Étape 1 : écrire les tests qui échouent**

Créer `backend/tests/unit/payroll/test_corrections_gains_forfait.py` :

```python
"""Au forfait jours, une ligne corrigée fait suivre le brut et le rapport des
salaires de la réduction générale (salaire du forfait, retenues d'absence)."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut_forfait import calculer_salaire_brut_forfait
from app.modules.payroll.engine.codes_des_lignes import BLOC_BRUT, code_de_ligne
from app.modules.payroll.engine.corrections_manuelles import CorrectionDeLigne, JournalDesCorrections

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

MARS = (date(2026, 3, 1), date(2026, 3, 31))
ABSENCE = [{"date_complete": "2026-03-16", "type": "absence_non_remuneree", "heures": 7.8}]
CODE_ABSENCE = "brut:absence_non_remuneree:16-03-26-1-jour"


def _brut(*corrections):
    contexte = build_test_contexte(statut="Cadre", salaire_base=3608.0, specificites_extra={"is_forfait_jour": True})
    contexte.year = 2026
    if corrections:
        contexte.corrections_du_mois = JournalDesCorrections(list(corrections))
    return calculer_salaire_brut_forfait(contexte, ABSENCE, *MARS, [])


def _ligne(resultat, code):
    return next(l for l in resultat["lignes_composants_brut"] if code_de_ligne(BLOC_BRUT, l) == code)


def _c(code, libelle, **champs):
    return CorrectionDeLigne(ligne=code, libelle=libelle, motif="Test", saisie_id="s1", **champs)


def test_sans_correction_le_forfait_est_identique():
    reference = _brut()
    assert reference["salaire_forfait_mois"] == 3608.0
    assert type(reference["lignes_composants_brut"]) is list
    assert _brut() == reference


def test_le_salaire_du_forfait_corrige_suit_dans_le_brut_et_le_rapport_des_salaires():
    reference = _brut()
    corrige = _brut(_c("brut:salaire_base", "Salaire de base (forfait jour)", montant=3700.0))
    assert _ligne(corrige, "brut:salaire_base")["gain"] == 3700.0
    assert corrige["salaire_brut_total"] == pytest.approx(reference["salaire_brut_total"] + 92.0)
    assert corrige["salaire_forfait_mois"] == 3700.0


def test_une_absence_corrigee_suit_dans_les_retenues_du_mois():
    reference = _brut()
    absence0 = _ligne(reference, CODE_ABSENCE)
    corrige = _brut(_c(CODE_ABSENCE, absence0["libelle"], base=2.0))
    absence1 = _ligne(corrige, CODE_ABSENCE)
    assert absence1["perte"] == round(2.0 * absence0["taux"], 2)
    assert corrige["retenues_absence_mois"] == pytest.approx(
        reference["retenues_absence_mois"] + absence1["perte"] - absence0["perte"], abs=0.005
    )
    assert corrige["salaire_brut_total"] == pytest.approx(
        reference["salaire_brut_total"] - (absence1["perte"] - absence0["perte"]), abs=0.005
    )
```

- [ ] **Étape 2 : lancer les tests pour les voir échouer**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_corrections_gains_forfait.py -q
```

Attendu : le premier test passe, les deux autres échouent.

- [ ] **Étape 3 : écrire l'implémentation**

Dans `backend/app/modules/payroll/engine/calcul_brut_forfait.py`, ajouter aux imports :

```python
from app.modules.payroll.engine.codes_des_lignes import BLOC_BRUT
from app.modules.payroll.engine.corrections_manuelles import LignesCorrigees, journal_du_contexte
```

et, après les imports :

```python
#: Les retenues d'absence qui entrent dans le rapport des salaires de la
#: réduction générale au forfait jours (`retenues_absence_mois`).
FAMILLES_RETENUES_FORFAIT = (
    "brut:absence_entree_sortie",
    "brut:absence_injustifiee",
    "brut:absence_non_remuneree",
    "brut:absence_ferie_non_paye",
    "brut:absence_maladie",
    "brut:arret",
    "brut:retenue_absence_mois_complet",
)
```

Dans `calculer_salaire_brut_forfait`, remplacer `lignes_composants_brut = []` par :

```python
    # Chaque ligne naît corrigée si une correction faite à la main la vise.
    lignes_composants_brut = LignesCorrigees(journal_du_contexte(contexte), BLOC_BRUT)
```

Juste avant `    total_gains = sum(` (après l'appel à `_ajouter_lignes_de_fin_de_contrat(...)`), insérer :

```python
    # Le salaire du forfait et les retenues d'absence que lit la réduction
    # générale suivent les lignes corrigées.
    effet = lignes_composants_brut.effet
    salaire_forfait_mois = salaire_contractuel + effet.sur_le_brut("brut:salaire_base")
    if effet.corrigees:
        retenues_absence_mois -= effet.sur_le_brut(*FAMILLES_RETENUES_FORFAIT)
```

Remplacer `    salaire_base_seul = salaire_contractuel` par `    salaire_base_seul = salaire_forfait_mois`, et dans le `return` : `"lignes_composants_brut": list(lignes_composants_brut),` et `"salaire_forfait_mois": round(salaire_forfait_mois, 2),`.

- [ ] **Étape 4 : relancer les tests de la tâche et ceux du forfait**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_corrections_gains_forfait.py tests/unit/payroll/test_forfait_absences.py tests/unit/payroll/test_reduction_generale_forfait_jours.py -q
```

Attendu : tout passe.

- [ ] **Étape 5 : commiter**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2 && git add backend/app/modules/payroll/engine/calcul_brut_forfait.py backend/tests/unit/payroll/test_corrections_gains_forfait.py && git commit -m "feat(paie): au forfait jours, une ligne corrigée fait suivre le brut et le rapport des salaires de la réduction

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 5 : les cotisations naissent corrigées, et le net imposable de la mutuelle suit

**Fichiers :**
- Modifier : `backend/app/modules/payroll/engine/calcul_cotisations.py` (import ; retour anticipé du stagiaire ; `bulletin_cotisations = []`)
- Modifier : `backend/app/modules/payroll/engine/calcul_net.py` (`_part_patronale_mutuelle_du_bulletin`)
- Tester : `backend/tests/unit/payroll/test_corrections_cotisations.py` (créé)

**Interfaces :**
- Consomme : `LignesCorrigees`, `journal_du_contexte`, `JournalDesCorrections`, `CorrectionDeLigne` ; `BLOC_COTISATIONS`, `code_de_ligne`, `Numerotation`.
- Produit : `calculer_cotisations` lit `contexte.corrections_du_mois` ; son total salarial, le plafond de la réduction des heures sup et l'assiette du forfait social partent des lignes corrigées. `_part_patronale_mutuelle_du_bulletin` ajoute l'écart d'une mutuelle corrigée (montant de la ligne moins `valeur_calculee.montant_patronal`) comme celui d'une régularisation.

- [ ] **Étape 1 : écrire les tests qui échouent**

Créer `backend/tests/unit/payroll/test_corrections_cotisations.py` :

```python
"""Une cotisation corrigée à la naissance de sa ligne : la ligne, le total salarial
et ce qui se calcule ensuite sur les lignes restent d'accord (spec § 5)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.payroll.engine import calcul_net
from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from app.modules.payroll.engine.codes_des_lignes import BLOC_COTISATIONS, Numerotation
from app.modules.payroll.engine.corrections_manuelles import CorrectionDeLigne, JournalDesCorrections

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _cotisations(*corrections, brut=2500.0, hs=82.42, heures_hs=4.0, taux_reduction_hs=None):
    contexte = build_test_contexte()
    contexte.year, contexte.month = 2026, 4
    if taux_reduction_hs is not None:
        # Le barème de test porte une réduction salariale des heures sup nulle.
        contexte.baremes.setdefault("heures_supp", {})["reduction_salariale"] = {
            "taux_reduction": {"plafond_legal": taux_reduction_hs}
        }
    if corrections:
        contexte.corrections_du_mois = JournalDesCorrections(list(corrections))
    return calculer_cotisations(contexte, brut, hs, heures_hs)


def _par_code(lignes):
    numeros = Numerotation()
    return {numeros.code(BLOC_COTISATIONS, l): l for l in lignes}


def _c(code, libelle, saisie_id="s1", **champs):
    return CorrectionDeLigne(ligne=code, libelle=libelle, motif="Test", saisie_id=saisie_id, **champs)


def test_sans_correction_les_cotisations_sont_identiques():
    lignes, total = _cotisations()
    contexte = build_test_contexte()
    contexte.year, contexte.month = 2026, 4
    contexte.corrections_du_mois = JournalDesCorrections([])
    assert calculer_cotisations(contexte, 2500.0, 82.42, 4.0) == (lignes, total)
    assert type(lignes) is list


def test_une_cotisation_corrigee_par_sa_base_fait_suivre_le_total_salarial():
    reference, total0 = _cotisations()
    vp0 = _par_code(reference)["cotisation:vieillesse_plafonnee"]
    lignes, total = _cotisations(_c("cotisation:vieillesse_plafonnee", vp0["libelle"], base=2600.0))
    vp = _par_code(lignes)["cotisation:vieillesse_plafonnee"]
    assert vp["montant_salarial"] == round(2600.0 * vp0["taux_salarial"], 2)
    assert vp["montant_patronal"] == round(2600.0 * vp0["taux_patronal"], 2)
    assert vp["valeur_calculee"]["montant_salarial"] == vp0["montant_salarial"]
    assert total == pytest.approx(total0 + vp["montant_salarial"] - vp0["montant_salarial"], abs=0.005)
    assert total == pytest.approx(sum(l.get("montant_salarial") or 0.0 for l in lignes), abs=0.005)


def test_une_ligne_en_double_se_corrige_par_son_numero():
    reference, _ = _cotisations()
    codes = list(_par_code(reference))
    assert "cotisation:vieillesse_deplafonnee#2" in codes  # le barème de test la porte deux fois
    lignes, _ = _cotisations(_c("cotisation:vieillesse_deplafonnee#2", "Vieillesse déplafonnée", base=2600.0))
    doublons = [l for l in lignes if l.get("coti_id") == "vieillesse_deplafonnee"]
    assert [l["base"] for l in doublons] == [2500.0, 2600.0]


def test_le_plafond_de_la_reduction_des_heures_sup_lit_les_lignes_corrigees():
    """Le plafond (les cotisations salariales dues) se lit sur les lignes corrigées."""
    lignes, _ = _cotisations(
        _c("cotisation:csg_deductible:csg-deductible", "CSG déductible", base=0.0),
        _c("cotisation:vieillesse_plafonnee", "Vieillesse plafonnée", base=0.0, saisie_id="s2"),
        hs=2000.0,
        heures_hs=100.0,
        # Un taux fort : le plafond joue à coup sûr, et seulement s'il lit les lignes corrigées.
        taux_reduction_hs=0.5,
    )
    par_code = _par_code(lignes)
    assert par_code["cotisation:csg_deductible:csg-deductible"]["montant_salarial"] == 0.0
    dues = round(
        sum(l.get("montant_salarial") or 0.0 for l in lignes if l.get("coti_id") != "reduction_hs_salariale"), 2
    )
    assert dues < round(2000.0 * 0.5, 2)  # le plafond joue
    assert par_code["cotisation:reduction_hs_salariale"]["montant_salarial"] == pytest.approx(-dues, abs=0.005)


def _mutuelle(patronal, **extra):
    return {"coti_id": "mutuelle", "libelle": "Mutuelle", "montant_salarial": 20.0, "montant_patronal": patronal, **extra}


def test_sans_correction_la_mutuelle_reintegree_est_inchangee():
    with patch.object(calcul_net, "_get_part_patronale_mutuelle", return_value=30.0):
        assert calcul_net._part_patronale_mutuelle_du_bulletin(None, [_mutuelle(30.0)]) == 30.0


def test_une_mutuelle_corrigee_reintegre_son_ecart_au_net_imposable():
    corrigee = _mutuelle(36.0, valeur_calculee={"montant_patronal": 30.0}, correction={"saisie_id": "s1"})
    with patch.object(calcul_net, "_get_part_patronale_mutuelle", return_value=30.0):
        assert calcul_net._part_patronale_mutuelle_du_bulletin(None, [corrigee]) == 36.0
    baissee = _mutuelle(25.0, valeur_calculee={"montant_patronal": 30.0}, correction={"saisie_id": "s1"})
    with patch.object(calcul_net, "_get_part_patronale_mutuelle", return_value=30.0):
        assert calcul_net._part_patronale_mutuelle_du_bulletin(None, [baissee]) == 25.0
```

- [ ] **Étape 2 : lancer les tests pour les voir échouer**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_corrections_cotisations.py -q
```

Attendu : les deux tests « sans correction » passent, les quatre autres échouent.

- [ ] **Étape 3 : poser les cotisations dans `LignesCorrigees`**

Dans `backend/app/modules/payroll/engine/calcul_cotisations.py`, ajouter aux imports :

```python
from app.modules.payroll.engine.codes_des_lignes import BLOC_COTISATIONS
from app.modules.payroll.engine.corrections_manuelles import LignesCorrigees, journal_du_contexte
```

Remplacer le retour anticipé du stagiaire :

```python
        if salaire_brut <= plafond_stage + 0.01:
            return [
                enrichir_ligne_cotisation(
                    { ... "libelle": "Gratification de stage exonérée", ... },
                    coti_id="exoneration_stage",
                )
            ], 0.0
```

par (le dictionnaire de la ligne est inchangé) :

```python
        if salaire_brut <= plafond_stage + 0.01:
            lignes_stage = LignesCorrigees(
                journal_du_contexte(contexte),
                BLOC_COTISATIONS,
                [
                    enrichir_ligne_cotisation(
                        {
                            "libelle": "Gratification de stage exonérée",
                            "base": round(salaire_brut, 2),
                            "taux_salarial": None,
                            "montant_salarial": 0.0,
                            "taux_patronal": None,
                            "montant_patronal": 0.0,
                        },
                        coti_id="exoneration_stage",
                    )
                ],
            )
            return list(lignes_stage), round(
                sum(float(ligne.get("montant_salarial") or 0.0) for ligne in lignes_stage), 2
            )
```

Remplacer `    bulletin_cotisations = []` par :

```python
    # Chaque cotisation naît corrigée si une correction faite à la main la vise :
    # le total salarial, le plafond de la réduction des heures sup et l'assiette
    # du forfait social lisent la ligne corrigée.
    bulletin_cotisations = LignesCorrigees(journal_du_contexte(contexte), BLOC_COTISATIONS)
```

La compréhension de fin (`bulletin_cotisations = [enrichir_ligne_cotisation(ligne) for ligne in bulletin_cotisations]`) rend déjà une liste ordinaire : la laisser.

- [ ] **Étape 4 : la mutuelle réintégrée suit l'écart corrigé**

Dans `backend/app/modules/payroll/engine/calcul_net.py`, remplacer le corps de `_part_patronale_mutuelle_du_bulletin` (après sa docstring, qu'on complète d'une phrase : « Une ligne corrigée à la main réintègre son écart de la même façon. ») par :

```python
    mutuelle = [ligne for ligne in lignes_cotisations if ligne.get("coti_id") == "mutuelle"]

    def _calculee(ligne: Dict[str, Any]) -> float:
        valeur = ligne.get("valeur_calculee")
        if isinstance(valeur, dict):
            return _get_safe_float(valeur.get("montant_patronal"))
        return _get_safe_float(ligne.get("montant_patronal"))

    calculee = round(sum(_calculee(ligne) for ligne in mutuelle if not ligne.get("regularisation")), 2)
    regularisee = round(
        sum(_get_safe_float(ligne.get("montant_patronal")) for ligne in mutuelle if ligne.get("regularisation")),
        2,
    )
    corrigee = round(
        sum(
            _get_safe_float(ligne.get("montant_patronal")) - _calculee(ligne)
            for ligne in mutuelle
            if isinstance(ligne.get("valeur_calculee"), dict)
        ),
        2,
    )
    fiche = _get_part_patronale_mutuelle(contexte)
    reintegree = min(fiche, calculee) if calculee > 0 else 0.0
    if (regularisee or corrigee) and fiche > 0:
        reintegree += regularisee + corrigee
    return round(max(0.0, reintegree), 2)
```

Sans correction, `corrigee` vaut 0 et le calcul est celui de l'étape 1.

- [ ] **Étape 5 : relancer les tests de la tâche et ceux des cotisations et du net**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_corrections_cotisations.py tests/unit/payroll/test_net_imposable_regularisations.py tests/unit/payroll/test_mutuelles_jamais_sautees.py tests/unit/payroll/test_compteurs_heures_bulletin.py tests/unit/payroll/test_professionnalisation.py tests/unit/payroll/test_golden_bulletins.py -q
```

Attendu : tout passe.

- [ ] **Étape 6 : commiter**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2 && git add backend/app/modules/payroll/engine/calcul_cotisations.py backend/app/modules/payroll/engine/calcul_net.py backend/tests/unit/payroll/test_corrections_cotisations.py && git commit -m "feat(paie): une cotisation naît corrigée, et le total salarial, le plafond des heures sup et la mutuelle imposable la suivent

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 6 : la réduction générale et le taux d'impôt du mois

**Fichiers :**
- Modifier : `backend/app/modules/payroll/engine/calcul_reduction_generale.py` (`calculer_reduction_generale`)
- Modifier : `backend/app/modules/payroll/engine/calcul_net.py` (`calculer_net_et_impot`)
- Modifier : `backend/app/modules/payroll/engine/bulletin.py` (bloc `impot_prelevement_a_la_source` de `synthese_net`)
- Tester : `backend/tests/unit/payroll/test_corrections_reduction_et_impot.py` (créé)

**Interfaces :**
- Consomme : `corriger_la_reduction_generale`, `corriger_le_taux_d_impot`, `journal_du_contexte` (tâche 2).
- Produit : `calculer_reduction_generale` rend la ligne corrigée et sa `valeur_cumulative_a_enregistrer` appliquée ; `calculer_net_et_impot` rend `taux_pas_applique` et `montant_impot_pas` corrigés et, seulement s'il y a correction, `correction_impot = {"correction", "valeur_calculee"}` ; `synthese_net.impot_prelevement_a_la_source` porte alors `correction` et `valeur_calculee`. Les cumuls `reduction_generale_patronale` et `impot_preleve_a_la_source` (`mettre_a_jour_cumuls`, inchangé) enregistrent ce qui est appliqué et prélevé.

- [ ] **Étape 1 : écrire les tests qui échouent**

Créer `backend/tests/unit/payroll/test_corrections_reduction_et_impot.py` :

```python
"""Réduction générale corrigée par son montant, impôt par le taux du mois ; leurs
cumuls enregistrent ce qui a été appliqué et prélevé (spec § 5 et § 6)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.modules.payroll.documents.payslip_run_common import mettre_a_jour_cumuls
from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from app.modules.payroll.engine.calcul_net import calculer_net_et_impot
from app.modules.payroll.engine.calcul_reduction_generale import calculer_reduction_generale
from app.modules.payroll.engine.corrections_manuelles import CorrectionDeLigne, JournalDesCorrections

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

RG = "Réduction générale de cotisations patronales"


def _contexte(*corrections, cumuls=None):
    contexte = build_test_contexte(taux_pas=5.2, cumuls=cumuls)
    contexte.year, contexte.month = 2026, 4
    if corrections:
        contexte.corrections_du_mois = JournalDesCorrections(list(corrections))
    return contexte


def _c(code, libelle, **champs):
    return CorrectionDeLigne(ligne=code, libelle=libelle, motif="Test", saisie_id="s1", **champs)


def test_sans_correction_la_reduction_est_identique():
    assert calculer_reduction_generale(_contexte(), 2500.0, 155.67) == calculer_reduction_generale(
        _contexte(_c("brut:salaire_base", "Salaire de base", base=1.0)), 2500.0, 155.67
    )


def test_la_reduction_corrigee_enregistre_ce_qui_est_applique():
    reference = calculer_reduction_generale(_contexte(cumuls={"reduction_generale_patronale": -1000.0}), 2500.0, 155.67)
    contexte = _contexte(
        _c("cotisation:reduction_generale", RG, montant_patronal=-300.0),
        cumuls={"reduction_generale_patronale": -1000.0},
    )
    ligne = calculer_reduction_generale(contexte, 2500.0, 155.67)
    assert ligne["montant_patronal"] == -300.0
    assert ligne["valeur_calculee"]["montant_patronal"] == reference["montant_patronal"]
    assert ligne["valeur_cumulative_a_enregistrer"] == 1300.0
    assert ligne["smic_reference_mois"] == reference["smic_reference_mois"]


def test_le_cumul_de_la_reduction_et_de_l_impot_suit_la_correction(tmp_path):
    contexte = SimpleNamespace(
        cumuls={"cumuls": {"reduction_generale_patronale": -1000.0, "brut_total": 7500.0,
                           "impot_preleve_a_la_source": 300.0}, "periode": {}},
        company_id=None,
        year=2026,
    )
    ligne_rg = {"coti_id": "reduction_generale", "montant_patronal": -300.0, "valeur_cumulative_a_enregistrer": 1300.0}
    mettre_a_jour_cumuls(
        contexte, 2500.0, 0.0, {"net_imposable": 2000.0, "montant_impot_pas": 150.0}, ligne_rg, 4, 0.0, 0.0, tmp_path
    )
    cumuls = json.loads((tmp_path / "cumuls" / "04.json").read_text(encoding="utf-8"))["cumuls"]
    assert cumuls["reduction_generale_patronale"] == -1300.0
    assert cumuls["impot_preleve_a_la_source"] == 450.0


def _nets(contexte):
    lignes, total = calculer_cotisations(contexte, 2500.0, 82.42, 4.0)
    return calculer_net_et_impot(contexte, 2500.0, lignes, total, [], 82.42, 0.0, [])


def test_sans_correction_l_impot_est_identique_et_ne_dit_rien_de_plus():
    reference = _nets(_contexte())
    assert "correction_impot" not in reference
    assert _nets(_contexte(_c("brut:salaire_base", "Salaire de base", base=1.0))) == reference


def test_le_taux_d_impot_du_mois_corrige_fait_suivre_le_montant_et_le_net():
    reference = _nets(_contexte())
    nets = _nets(_contexte(_c("impot", "Impôt sur le revenu prélevé à la source", taux=7.5)))
    attendu = round(reference["base_pas"] * (7.5 / 100.0), 2)
    assert nets["taux_pas_applique"] == 7.5
    assert nets["montant_impot_pas"] == attendu
    assert nets["net_a_payer"] == pytest.approx(reference["net_a_payer"] - (attendu - reference["montant_impot_pas"]), abs=0.005)
    assert nets["correction_impot"]["valeur_calculee"] == {
        "taux": reference["taux_pas_applique"],
        "montant": reference["montant_impot_pas"],
    }
```

- [ ] **Étape 2 : lancer les tests pour les voir échouer**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_corrections_reduction_et_impot.py -q
```

Attendu : les tests « sans correction » et celui des cumuls passent ; les deux autres échouent.

- [ ] **Étape 3 : la réduction générale**

Dans `backend/app/modules/payroll/engine/calcul_reduction_generale.py`, ajouter `from app.modules.payroll.engine.corrections_manuelles import corriger_la_reduction_generale, journal_du_contexte`, et remplacer la fin de `calculer_reduction_generale` :

```python
    # avant
    if annee < lc.ANNEE_BASCULE_RGDU:
        return _calculer_reduction_fillon(
            contexte, salaire_brut_mois, heures_remunerees_mois
        )
    return _calculer_reduction_rgdu(
        contexte, salaire_brut_mois, heures_remunerees_mois
    )
    # après
    if annee < lc.ANNEE_BASCULE_RGDU:
        ligne = _calculer_reduction_fillon(contexte, salaire_brut_mois, heures_remunerees_mois)
    else:
        ligne = _calculer_reduction_rgdu(contexte, salaire_brut_mois, heures_remunerees_mois)
    # Corrigée à la main par son montant : son cumul enregistre la réduction
    # réellement appliquée, et le mois suivant régularise depuis là (spec § 6).
    journal = journal_du_contexte(contexte)
    if journal is None or ligne is None:
        return ligne
    return corriger_la_reduction_generale(ligne, journal, _lire_cumuls_precedents(contexte)[2])
```

- [ ] **Étape 4 : le taux d'impôt du mois**

Dans `backend/app/modules/payroll/engine/calcul_net.py`, ajouter `from app.modules.payroll.engine.corrections_manuelles import corriger_le_taux_d_impot, journal_du_contexte`, et dans `calculer_net_et_impot` remplacer :

```python
    montant_impot = _calculer_prelevement_a_la_source(contexte, net_imposable)
    base_pas = _base_pas_du_mois(contexte, net_imposable)
    taux_pas_applique = taux_pas_du_mois(contexte, base_pas)
```

par :

```python
    base_pas = _base_pas_du_mois(contexte, net_imposable)
    # Le taux du mois peut être corrigé à la main ; le montant suit, avec la
    # même formule que `_calculer_prelevement_a_la_source`.
    taux_pas_applique, correction_impot = corriger_le_taux_d_impot(
        taux_pas_du_mois(contexte, base_pas), base_pas, journal_du_contexte(contexte)
    )
    montant_impot = round(base_pas * (taux_pas_applique / 100.0), 2)
```

Garder `_calculer_prelevement_a_la_source` (d'autres tests l'appellent). Puis, à la fin de la fonction, remplacer `    return {` par `    resultats = {` (le dictionnaire reste le même, clé pour clé), et après son accolade fermante ajouter :

```python
    # La clé n'existe qu'avec une correction : un bulletin sans correction ne change pas.
    if correction_impot is not None:
        resultats["correction_impot"] = correction_impot
    return resultats
```

- [ ] **Étape 5 : la synthèse du bulletin porte la correction de l'impôt**

Dans `backend/app/modules/payroll/engine/bulletin.py`, dans `creer_bulletin_final`, compléter le bloc `"impot_prelevement_a_la_source"` de `synthese_net` :

```python
        "impot_prelevement_a_la_source": {
            "base": base_pas,
            # Le taux appliqué par le moteur, pas celui de la fiche : quand aucun
            # taux personnalisé n'est connu, c'est la grille du mois qui a servi,
            # et le bulletin doit afficher le taux dont vient le montant.
            "taux": resultats_nets.get("taux_pas_applique", 0.0),
            "montant": resultats_nets.get("montant_impot_pas"),
            # Corrigé à la main : la correction et le taux que Martine avait appliqué.
            **(resultats_nets.get("correction_impot") or {}),
        },
```

Vérifier que `creer_bulletin_sortie` reprend ce bloc de `creer_bulletin_final` sans le reconstruire (`grep -n "impot_prelevement_a_la_source" backend/app/modules/payroll/engine/bulletin.py` : une seule écriture du bloc).

- [ ] **Étape 6 : relancer les tests de la tâche, de l'impôt et de la réduction**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_corrections_reduction_et_impot.py tests/unit/payroll/test_pas_bareme_defaut.py tests/unit/payroll/test_pas_apprenti.py tests/unit/payroll/test_pas_taux_pose_par_l_ecran.py tests/unit/payroll/test_cumul_reduction_regularisee.py tests/unit/payroll/test_reduction_generale_forfait_jours.py tests/unit/payroll/test_bulletin_officiel.py tests/unit/payroll/test_golden_bulletins.py -q
```

Attendu : tout passe.

- [ ] **Étape 7 : commiter**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2 && git add backend/app/modules/payroll/engine/calcul_reduction_generale.py backend/app/modules/payroll/engine/calcul_net.py backend/app/modules/payroll/engine/bulletin.py backend/tests/unit/payroll/test_corrections_reduction_et_impot.py && git commit -m "feat(paie): la réduction générale se corrige par son montant et l'impôt par son taux du mois ; leurs cumuls enregistrent ce qui est appliqué

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 7 : les deux générateurs et les deux pipelines, aux mêmes étapes

**Fichiers :**
- Modifier : `backend/app/modules/payroll/documents/payslip_generator.py` et `payslip_generator_forfait.py` (import ; `ranger_regularisation(row, saisies_data)` devient `ranger_correction_manuelle(row, saisies_data)`)
- Modifier : `backend/app/modules/payroll/documents/payslip_run_heures.py` et `payslip_run_forfait.py`
- Modifier (test de contrat) : `backend/tests/unit/payroll/test_regularisations_dans_les_pipelines.py`

**Interfaces :**
- Consomme : `JournalDesCorrections.depuis`, `ranger_correction_manuelle`, `corriger_les_lignes_de_gain`, `corriger_les_lignes_de_cotisation`, `synchroniser_le_maintien`, `poser_les_corrections_en_attente` (tâche 2).
- Produit : chaque pipeline pose `contexte.corrections_du_mois` (lu par les tâches 3 à 6), corrige les lignes nées après le brut et après `calculer_cotisations`, et pose `payslip_data["corrections_en_attente"]` quand une correction n'a pas trouvé sa ligne. Le bulletin de sortie (`creer_bulletin_sortie`) et le bac à sable passent par ces pipelines.

- [ ] **Étape 1 : écrire le test de contrat qui échoue**

Dans `backend/tests/unit/payroll/test_regularisations_dans_les_pipelines.py`, remplacer le premier test et ajouter les suivants :

```python
@pytest.mark.parametrize("module", [payslip_generator, payslip_generator_forfait])
def test_chaque_generateur_range_les_corrections_avant_les_primes(module):
    source = inspect.getsource(module)
    assert "ranger_correction_manuelle(row, saisies_data)" in source
    assert "ranger_regularisation(row, saisies_data)" not in source
    assert source.index("ranger_correction_manuelle(row, saisies_data)") < source.index("est_saisie_ijss_validees(row)")


@pytest.mark.parametrize(
    "module, calcul_du_brut",
    [(payslip_run_heures, "calculer_salaire_brut("), (payslip_run_forfait, "calculer_salaire_brut_forfait(")],
)
def test_chaque_pipeline_pose_les_corrections_aux_memes_etapes(module, calcul_du_brut):
    """Spec § 5 : le module des corrections est appelé aux mêmes étapes des deux copies."""
    source = inspect.getsource(module)
    journal = source.index("contexte.corrections_du_mois = JournalDesCorrections.depuis(saisie_du_mois)")
    brut = source.index(f"resultat_brut = {calcul_du_brut}")
    maintien = source.index("lignes_csg_ijss, ijss_imposables, brut_modifie = _appliquer_maintien_arret_maladie(")
    gains = source.index("effet_gains = corriger_les_lignes_de_gain(details_brut, contexte.corrections_du_mois)")
    cotisations = source.index("lignes_cotisations, total_salarial = calculer_cotisations(")
    reduction = source.index("calculer_reduction_generale(")
    passe_cotisations = source.index(
        "effet_cotisations = corriger_les_lignes_de_cotisation(lignes_cotisations, contexte.corrections_du_mois)"
    )
    regul = source.index("ajouter_regularisations(")
    net = source.index("resultats_nets = calculer_net_et_impot(")
    assemblage = source.rindex("bulletin_final = creer_bulletin_final(")
    attente = source.index("poser_les_corrections_en_attente(bulletin_final, contexte.corrections_du_mois)")
    cumuls = source.index("mettre_a_jour_cumuls(")
    assert journal < brut < maintien < gains < cotisations
    assert reduction < passe_cotisations < regul < net
    assert assemblage < attente < cumuls
    assert "synchroniser_le_maintien(resultats_maintien, details_brut)" in source


@pytest.mark.parametrize(
    "module, fonction",
    [
        (calcul_brut, "calculer_salaire_brut"),
        (calcul_brut_forfait, "calculer_salaire_brut_forfait"),
        (calcul_cotisations, "calculer_cotisations"),
    ],
)
def test_chaque_producteur_de_lignes_les_pose_dans_des_lignes_corrigees(module, fonction):
    """Une ligne ne peut pas naître sans passer par sa correction."""
    source = inspect.getsource(getattr(module, fonction))
    assert "LignesCorrigees(journal_du_contexte(contexte)" in source
    assert "lignes_composants_brut = []" not in source and "bulletin_cotisations = []" not in source


def test_la_reduction_et_l_impot_lisent_leur_correction():
    assert "corriger_la_reduction_generale(" in inspect.getsource(calcul_reduction_generale.calculer_reduction_generale)
    assert "corriger_le_taux_d_impot(" in inspect.getsource(calcul_net.calculer_net_et_impot)
```

et compléter les imports du fichier :

```python
from app.modules.payroll.engine import (
    calcul_brut,
    calcul_brut_forfait,
    calcul_cotisations,
    calcul_net,
    calcul_reduction_generale,
)
```

Le test existant `test_chaque_pipeline_pose_les_regularisations_entre_la_reduction_et_le_net` reste tel quel.

- [ ] **Étape 2 : lancer le test pour le voir échouer**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_regularisations_dans_les_pipelines.py -q
```

Attendu : les tests des générateurs et des pipelines échouent ; ceux des producteurs, de la réduction et de l'impôt passent (tâches 3 à 6).

- [ ] **Étape 3 : les générateurs rangent la correction à part des primes**

Dans `payslip_generator.py` et `payslip_generator_forfait.py`, remplacer l'import `ranger_regularisation` par `ranger_correction_manuelle`, et dans la boucle des saisies :

```python
            if ranger_correction_manuelle(row, saisies_data):
                # Régularisation de cotisation ou correction de ligne saisie depuis
                # le bulletin : ce n'est pas une prime, le moteur la rejoue.
                continue
```

- [ ] **Étape 4 : le pipeline mensuel**

Dans `payslip_run_heures.py`, remplacer l'import de l'étape 1 par :

```python
from app.modules.payroll.engine.corrections_manuelles import (
    JournalDesCorrections,
    ajouter_regularisations,
    corriger_les_lignes_de_cotisation,
    corriger_les_lignes_de_gain,
    poser_les_corrections_en_attente,
    synchroniser_le_maintien,
)
```

Après `    contexte.month = month` :

```python
    # Corrections faites à la main depuis le bulletin (théorème, étape 2) : le
    # moteur les pose ligne par ligne, là où chaque ligne naît.
    contexte.corrections_du_mois = JournalDesCorrections.depuis(saisie_du_mois)
```

Juste après l'appel `lignes_csg_ijss, ijss_imposables, brut_modifie = _appliquer_maintien_arret_maladie(...)` et avant `    if indemnites_remplacement:` :

```python
    # Lignes de gain posées après le calcul du brut (nuit, pause, maintien) :
    # corrigées ici, puis le brut se refait sur les lignes.
    effet_gains = corriger_les_lignes_de_gain(details_brut, contexte.corrections_du_mois)
    if effet_gains.corrigees:
        brut_modifie = True
        synchroniser_le_maintien(resultats_maintien, details_brut)
```

Juste avant le commentaire `    # Régularisations de cotisation saisies à la main : après la réduction` :

```python
    # Cotisations posées après `calculer_cotisations` (CSG des IJSS, JEI) :
    # corrigées ici ; la réduction générale l'a été à son calcul.
    effet_cotisations = corriger_les_lignes_de_cotisation(lignes_cotisations, contexte.corrections_du_mois)
    if effet_cotisations.salarial:
        total_salarial = round(total_salarial + effet_cotisations.salarial, 2)
```

Juste après le bloc `if contexte.exit_indemnities: bulletin_final = creer_bulletin_sortie(...) else: bulletin_final = creer_bulletin_final(...)` et avant `    smic_calcule_mois = (` :

```python
    # Règle 7 : une correction qui n'a pas trouvé sa ligne reste sur le bulletin.
    poser_les_corrections_en_attente(bulletin_final, contexte.corrections_du_mois)
```

- [ ] **Étape 5 : le pipeline forfait, aux mêmes étapes**

Dans `payslip_run_forfait.py`, les mêmes quatre ajouts, aux mêmes places : l'import identique ; le journal après `    contexte.month = month` ; la passe des gains après `lignes_csg_ijss, ijss_imposables, brut_modifie = _appliquer_maintien_arret_maladie(...)` et avant `    if brut_modifie:` ; la passe des cotisations juste avant le commentaire des régularisations ; `poser_les_corrections_en_attente(bulletin_final, contexte.corrections_du_mois)` après le bloc `creer_bulletin_sortie` / `creer_bulletin_final` et avant `    smic_calcule_mois = (`. Le code des quatre blocs est celui de l'étape 4, mot pour mot.

- [ ] **Étape 6 : relancer le test de contrat et les tests des pipelines**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_regularisations_dans_les_pipelines.py tests/unit/payroll/test_bulletin_parametres_dsn.py tests/unit/payroll/test_comitech_benefits.py tests/unit/payroll -q -x -k "pipeline or generat or bac_a_sable or regularis or correction"
```

Attendu : tout passe.

- [ ] **Étape 7 : commiter**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2 && git add backend/app/modules/payroll/documents/payslip_generator.py backend/app/modules/payroll/documents/payslip_generator_forfait.py backend/app/modules/payroll/documents/payslip_run_heures.py backend/app/modules/payroll/documents/payslip_run_forfait.py backend/tests/unit/payroll/test_regularisations_dans_les_pipelines.py && git commit -m "feat(paie): les deux pipelines rejouent les corrections de ligne aux mêmes étapes et gardent celles qui n'ont pas trouvé leur ligne

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 8 : ce qui se voit — lecture d'un bulletin, info-bulle, PDF ; la validation bloquée ; l'empreinte

**Fichiers :**
- Créer : `backend/app/modules/payroll/engine/corrections_du_bulletin.py`
- Modifier : `backend/app/modules/payroll/domain/explications_lignes.py` (`poser_explications` et une fonction ajoutée)
- Modifier : `backend/app/modules/payroll/documents/bulletin_view.py` (`_ligne_brut`, `_ligne_cotisation`, `construire_lignes`)
- Modifier : `backend/app/modules/payslips/domain/coherence.py`
- Tester : `backend/tests/unit/payroll/test_corrections_du_bulletin.py` (créé), `backend/tests/unit/payslips/test_coherence_corrections_en_attente.py` (créé), `backend/tests/unit/payroll/test_empreinte_entrees.py` (ajouts)

**Interfaces :**
- Consomme : `codes_des_lignes` (tâche 1) ; `CLE_CORRECTIONS_EN_ATTENTE`, `CorrectionDeLigne`, `CorrectionInvalide`, `JournalDesCorrections` (tâche 2).
- Produit (module `app.modules.payroll.engine.corrections_du_bulletin`) :
  - `BLOCS_DE_GAINS = ("calcul_du_brut", "details_conges", "details_absences")`, `LIBELLE_IMPOT` ;
  - `@dataclass(frozen=True) LigneCorrigeable(code, bloc, libelle, mode, raison=None, retenue=False, base=None, taux=None, montant=None, taux_salarial=None, taux_patronal=None, montant_salarial=None, montant_patronal=None, correction=None, valeur_calculee=None)` et `.en_dict()` ;
  - `lignes_corrigeables(payslip_data) -> list[LigneCorrigeable]` (gains, cotisations numérotées comme au calcul, puis l'impôt ; `base` d'un gain = sa quantité) ;
  - `corrections_en_attente_du_bulletin(payslip_data) -> list[dict]` ;
  - `corrections_du_bulletin(payslip_data) -> dict[str, CorrectionDeLigne]` (par identifiant de saisie : lignes corrigées et corrections en attente) ;
  - `lignes_corrigees_du_bulletin(payslip_data) -> list[dict]` (`{"famille", "libelle"}`, une par famille) ;
  - `valeur_calculee_fr(bloc, valeur_calculee) -> str`, `explication_de_correction(ligne, bloc) -> str | None`, `mentions_des_corrections(payslip_data) -> list[str]`.
- `app.modules.payslips.domain.coherence.MESSAGE_CORRECTION_EN_ATTENTE`, et `raisons_de_ne_pas_valider` le rend quand `payslip_data["corrections_en_attente"]` n'est pas vide.

- [ ] **Étape 1 : écrire les tests qui échouent**

Créer `backend/tests/unit/payroll/test_corrections_du_bulletin.py` :

```python
"""Un bulletin enregistré dit ses lignes, ce qui s'y corrige et ce qui a été corrigé."""

from __future__ import annotations

import pytest

from app.modules.payroll.documents.bulletin_view import construire_lignes
from app.modules.payroll.domain.explications_lignes import poser_explications
from app.modules.payroll.engine.codes_des_lignes import (
    BLOC_BRUT,
    BLOC_COTISATIONS,
    MODE_BASE_OU_TAUX,
    MODE_MONTANT,
    MODE_TAUX,
    RAISON_SAISIE,
)
from app.modules.payroll.engine.corrections_du_bulletin import (
    corrections_du_bulletin,
    corrections_en_attente_du_bulletin,
    explication_de_correction,
    lignes_corrigeables,
    lignes_corrigees_du_bulletin,
    mentions_des_corrections,
)
from app.modules.payroll.engine.corrections_manuelles import CorrectionDeLigne, JournalDesCorrections

pytestmark = pytest.mark.unit


def _bulletin():
    return {
        "en_tete": {"annee": 2026, "mois": 10},
        "calcul_du_brut": [
            {"libelle": "Salaire de base", "quantite": 151.67, "taux": 16.4832, "gain": 2500.0, "perte": None},
            {"libelle": "Prime exceptionnelle", "quantite": None, "taux": None, "gain": 100.0, "perte": None, "saisie_id": "p1"},
        ],
        "details_absences": [
            {"libelle": "Absence non rémunérée du 16/10/26", "quantite": 7.0, "taux": 16.4832, "gain": None, "perte": 115.38},
        ],
        "cotisations_officielles": [
            {"code": "sante", "lignes": [
                {"coti_id": "securite_sociale_maladie", "libelle": "Maladie", "base": 2600.0, "taux_salarial": 0.0,
                 "taux_patronal": 0.07, "montant_salarial": 0.0, "montant_patronal": 182.0},
                {"coti_id": "mutuelle", "libelle": "Mutuelle", "base": None, "taux_salarial": None, "taux_patronal": None,
                 "montant_salarial": 20.0, "montant_patronal": 30.0},
            ]},
        ],
        "synthese_net": {"net_imposable": 2000.0, "impot_prelevement_a_la_source": {"base": 2000.0, "taux": 5.2, "montant": 104.0}},
    }


def _corrige():
    """Le même bulletin, salaire de base et impôt corrigés comme le moteur les pose."""
    bulletin = _bulletin()
    journal = JournalDesCorrections(
        [CorrectionDeLigne(ligne="brut:salaire_base", libelle="Salaire de base", motif="Avenant du 01/10", base=160.0, saisie_id="c1")]
    )
    journal.corriger(bulletin["calcul_du_brut"][0], BLOC_BRUT, "brut:salaire_base")
    bulletin["synthese_net"]["impot_prelevement_a_la_source"].update(
        {"taux": 7.5, "montant": 150.0,
         "correction": {"type": "correction", "ligne": "impot", "libelle": "Impôt", "motif": "Taux DGFiP du mois", "taux": 7.5, "saisie_id": "c2"},
         "valeur_calculee": {"taux": 5.2, "montant": 104.0}}
    )
    return bulletin


def test_le_bulletin_dit_chaque_ligne_et_par_quoi_elle_se_corrige():
    lignes = {l.code: l for l in lignes_corrigeables(_bulletin())}
    assert lignes["brut:salaire_base"].mode == MODE_BASE_OU_TAUX and lignes["brut:salaire_base"].base == 151.67
    assert lignes["brut:saisie:p1"].mode is None and lignes["brut:saisie:p1"].raison == RAISON_SAISIE
    absence = lignes["brut:absence_non_remuneree:16-10-26"]
    assert absence.retenue and absence.montant == 115.38
    assert lignes["cotisation:securite_sociale_maladie"].taux_patronal == 0.07
    assert lignes["cotisation:mutuelle:mutuelle"].mode == MODE_MONTANT
    assert lignes["impot"].mode == MODE_TAUX and lignes["impot"].taux == 5.2
    assert all(l.correction is None for l in lignes.values())


def test_une_ligne_corrigee_dit_sa_correction_et_ce_que_martine_avait_calcule():
    lignes = {l.code: l for l in lignes_corrigeables(_corrige())}
    base = lignes["brut:salaire_base"]
    assert base.correction["saisie_id"] == "c1" and base.valeur_calculee["gain"] == 2500.0
    assert lignes["impot"].correction["saisie_id"] == "c2"
    assert set(corrections_du_bulletin(_corrige())) == {"c1", "c2"}
    assert lignes_corrigees_du_bulletin(_corrige()) == [
        {"famille": "brut:salaire_base", "libelle": "Salaire de base"},
        {"famille": "impot", "libelle": "Impôt sur le revenu prélevé à la source"},
    ]


def test_une_correction_en_attente_se_lit_et_se_restaure():
    bulletin = {**_bulletin(), "corrections_en_attente": [
        {"type": "correction", "ligne": "brut:precarite", "libelle": "Prime de précarité (CDD)", "motif": "CDD prolongé",
         "montant": 0.0, "saisie_id": "c3", "raison": "La ligne visée n'est plus sur le bulletin."},
    ]}
    assert corrections_en_attente_du_bulletin(bulletin)[0]["saisie_id"] == "c3"
    assert corrections_du_bulletin(bulletin)["c3"].ligne == "brut:precarite"
    assert corrections_en_attente_du_bulletin(_bulletin()) == []


def test_l_info_bulle_d_une_ligne_corrigee_remplace_celle_du_calcul():
    bulletin = _corrige()
    ligne = bulletin["calcul_du_brut"][0]
    assert explication_de_correction(ligne, BLOC_BRUT) == (
        "Corrigée à la main : Avenant du 01/10. Martine avait calculé 2 500,00 €."
    )
    assert explication_de_correction(_bulletin()["calcul_du_brut"][0], BLOC_BRUT) is None
    poser_explications(bulletin)
    assert bulletin["calcul_du_brut"][0]["explication"].startswith("Corrigée à la main")
    assert "explication" not in bulletin["calcul_du_brut"][1]


def test_le_pdf_marque_la_ligne_corrigee_et_dit_pourquoi():
    lignes = construire_lignes(_corrige())
    libelles = [l["libelle"] for l in lignes]
    assert "Salaire de base *" in libelles
    notes = [l["libelle"] for l in lignes if l["type"] == "note"]
    assert "* Ligne corrigée à la main — Salaire de base : Avenant du 01/10 (Martine avait calculé 2 500,00 €)." in notes
    assert "* Taux d'impôt corrigé à la main : Taux DGFiP du mois (Martine avait appliqué un taux de 5,20 %)." in notes
    assert mentions_des_corrections(_bulletin()) == []


def test_sans_correction_le_pdf_est_celui_d_avant():
    lignes = construire_lignes(_bulletin())
    assert not any(l["libelle"].endswith(" *") for l in lignes)
    assert not any("corrigée à la main" in l["libelle"] for l in lignes if l["type"] == "note")


def test_la_valeur_calculee_d_une_cotisation_se_dit_par_part():
    from app.modules.payroll.engine.corrections_du_bulletin import valeur_calculee_fr

    assert valeur_calculee_fr(BLOC_COTISATIONS, {"montant_salarial": 12.4, "montant_patronal": 25.0}) == (
        "12,40 € salarial et 25,00 € patronal"
    )
```

Créer `backend/tests/unit/payslips/test_coherence_corrections_en_attente.py` :

```python
"""Une correction en attente bloque la validation (règle 7)."""

from __future__ import annotations

import pytest

from app.modules.payslips.domain.coherence import MESSAGE_CORRECTION_EN_ATTENTE, raisons_de_ne_pas_valider

pytestmark = pytest.mark.unit


def test_une_correction_en_attente_empeche_de_valider():
    data = {"corrections_en_attente": [{"saisie_id": "c3", "ligne": "brut:precarite"}]}
    assert raisons_de_ne_pas_valider(data) == [MESSAGE_CORRECTION_EN_ATTENTE]


def test_sans_correction_en_attente_rien_ne_change():
    assert raisons_de_ne_pas_valider({}) == []
    assert raisons_de_ne_pas_valider({"corrections_en_attente": []}) == []
```

Dans `backend/tests/unit/payroll/test_empreinte_entrees.py`, ajouter :

```python
def test_une_correction_de_ligne_change_l_empreinte():
    ordinaire = {"year": 2026, "month": 10, "name": "Correction – Salaire de base", "amount": 0}
    corrigee = {**ordinaire, "correction_ligne": {"type": "correction", "ligne": "brut:salaire_base", "base": 160.0}}
    assert empreinte(construire_entrees({"saisies": [saisie_pour_empreinte(ordinaire)]})) != empreinte(
        construire_entrees({"saisies": [saisie_pour_empreinte(corrigee)]})
    )


def test_la_valeur_calculee_d_une_ligne_corrigee_compte_au_centime():
    """Le PDF l'imprime : si Martine recalcule autrement la ligne corrigée, le bulletin est à recalculer."""
    from app.modules.payroll.domain.empreinte_entrees import ecart_au_centime

    def _bulletin(valeur):
        return {
            "salaire_brut": 2637.31,
            "net_a_payer": 2000.0,
            "calcul_du_brut": [{"libelle": "Salaire de base", "quantite": 160.0, "taux": 16.4832, "gain": 2637.31,
                                "correction": {"saisie_id": "c1"}, "valeur_calculee": {"gain": valeur}}],
        }

    assert ecart_au_centime(_bulletin(2500.0), _bulletin(2500.0)) is None
    assert ecart_au_centime(_bulletin(2500.0), _bulletin(2510.0)) is not None
```

(`empreinte`, `construire_entrees`, `saisie_pour_empreinte` sont déjà importés en tête de ce fichier depuis l'étape 1.)

- [ ] **Étape 2 : lancer les tests pour les voir échouer**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_corrections_du_bulletin.py tests/unit/payslips/test_coherence_corrections_en_attente.py tests/unit/payroll/test_empreinte_entrees.py -q
```

Attendu : `ModuleNotFoundError` pour `corrections_du_bulletin`, `ImportError` pour `MESSAGE_CORRECTION_EN_ATTENTE` ; les deux tests d'empreinte passent déjà (rien à changer dans l'empreinte : décision 9).

- [ ] **Étape 3 : écrire `corrections_du_bulletin.py`**

```python
"""Lire les corrections faites à la main sur un bulletin enregistré.

La route « lignes corrigeables », la carte de l'écran, la restauration d'une
version, la liste de contrôle, le PDF, l'info-bulle et le test du théorème
lisent ici les mêmes codes que le moteur (`codes_des_lignes`), numérotés de la
même façon.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from app.modules.payroll.engine.codes_des_lignes import (
    BLOC_BRUT,
    BLOC_COTISATIONS,
    BLOC_IMPOT,
    CODE_IMPOT,
    MODE_TAUX,
    champ_du_montant,
    code_de_ligne,
    famille_du_code,
    mode_de_correction,
    numeroter,
)
from app.modules.payroll.engine.corrections_manuelles import (
    CLE_CORRECTIONS_EN_ATTENTE,
    CorrectionDeLigne,
    CorrectionInvalide,
)

#: Les blocs imprimés d'un bulletin qui portent ses lignes de gain. Les lignes
#: d'arrêt de `details_maintien` sont celles de `details_absences`.
BLOCS_DE_GAINS = ("calcul_du_brut", "details_conges", "details_absences")
LIBELLE_IMPOT = "Impôt sur le revenu prélevé à la source"


@dataclass(frozen=True)
class LigneCorrigeable:
    code: str | None
    bloc: str
    libelle: str
    mode: str | None
    raison: str | None = None
    retenue: bool = False
    base: float | None = None
    taux: float | None = None
    montant: float | None = None
    taux_salarial: float | None = None
    taux_patronal: float | None = None
    montant_salarial: float | None = None
    montant_patronal: float | None = None
    correction: dict[str, Any] | None = None
    valeur_calculee: dict[str, Any] | None = None

    def en_dict(self) -> dict[str, Any]:
        return asdict(self)


def _nombre(valeur: Any) -> float | None:
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _dict(valeur: Any) -> dict[str, Any] | None:
    return dict(valeur) if isinstance(valeur, Mapping) else None


def _donnees(payslip_data: Any) -> Mapping[str, Any]:
    return payslip_data if isinstance(payslip_data, Mapping) else {}


def _lignes_de_gain(data: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [l for bloc in BLOCS_DE_GAINS for l in data.get(bloc) or [] if isinstance(l, Mapping)]


def _lignes_de_cotisation(data: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        l
        for rubrique in data.get("cotisations_officielles") or []
        if isinstance(rubrique, Mapping)
        for l in rubrique.get("lignes") or []
        if isinstance(l, Mapping)
    ]


def _impot(data: Mapping[str, Any]) -> Mapping[str, Any] | None:
    synthese = data.get("synthese_net")
    impot = synthese.get("impot_prelevement_a_la_source") if isinstance(synthese, Mapping) else None
    return impot if isinstance(impot, Mapping) else None


def lignes_corrigeables(payslip_data: Any) -> list[LigneCorrigeable]:
    """Chaque ligne du bulletin, son code, par quoi elle se corrige, et sa correction."""
    data = _donnees(payslip_data)
    sortie: list[LigneCorrigeable] = []
    gains = _lignes_de_gain(data)
    for ligne, code in zip(gains, numeroter(code_de_ligne(BLOC_BRUT, l) for l in gains)):
        mode, raison = mode_de_correction(BLOC_BRUT, ligne, code)
        champ = champ_du_montant(ligne)
        sortie.append(
            LigneCorrigeable(
                code=code,
                bloc=BLOC_BRUT,
                libelle=str(ligne.get("libelle") or ""),
                mode=mode,
                raison=raison,
                retenue=champ == "perte",
                base=_nombre(ligne.get("quantite")),
                taux=_nombre(ligne.get("taux")),
                montant=_nombre(ligne.get(champ)),
                correction=_dict(ligne.get("correction")),
                valeur_calculee=_dict(ligne.get("valeur_calculee")),
            )
        )
    cotisations = _lignes_de_cotisation(data)
    for ligne, code in zip(cotisations, numeroter(code_de_ligne(BLOC_COTISATIONS, l) for l in cotisations)):
        mode, raison = mode_de_correction(BLOC_COTISATIONS, ligne, code)
        sortie.append(
            LigneCorrigeable(
                code=code,
                bloc=BLOC_COTISATIONS,
                libelle=str(ligne.get("libelle") or ""),
                mode=mode,
                raison=raison,
                base=_nombre(ligne.get("base")),
                taux_salarial=_nombre(ligne.get("taux_salarial")),
                taux_patronal=_nombre(ligne.get("taux_patronal")),
                montant_salarial=_nombre(ligne.get("montant_salarial")),
                montant_patronal=_nombre(ligne.get("montant_patronal")),
                correction=_dict(ligne.get("correction")),
                valeur_calculee=_dict(ligne.get("valeur_calculee")),
            )
        )
    impot = _impot(data)
    if impot is not None:
        sortie.append(
            LigneCorrigeable(
                code=CODE_IMPOT,
                bloc=BLOC_IMPOT,
                libelle=LIBELLE_IMPOT,
                mode=MODE_TAUX,
                base=_nombre(impot.get("base")),
                taux=_nombre(impot.get("taux")),
                montant=_nombre(impot.get("montant")),
                correction=_dict(impot.get("correction")),
                valeur_calculee=_dict(impot.get("valeur_calculee")),
            )
        )
    return sortie


def corrections_en_attente_du_bulletin(payslip_data: Any) -> list[dict[str, Any]]:
    entrees = _donnees(payslip_data).get(CLE_CORRECTIONS_EN_ATTENTE) or []
    return [dict(e) for e in entrees if isinstance(e, Mapping)]


def corrections_du_bulletin(payslip_data: Any) -> dict[str, CorrectionDeLigne]:
    """Les corrections du bulletin par identifiant de saisie : posées ou en attente."""
    trouvees: dict[str, CorrectionDeLigne] = {}
    traces = [l.correction for l in lignes_corrigeables(payslip_data) if l.correction]
    for trace in [*traces, *corrections_en_attente_du_bulletin(payslip_data)]:
        identifiant = trace.get("saisie_id")
        if not identifiant or str(identifiant) in trouvees:
            continue
        try:
            trouvees[str(identifiant)] = CorrectionDeLigne.depuis(trace)
        except CorrectionInvalide:
            continue
    return trouvees


def lignes_corrigees_du_bulletin(payslip_data: Any) -> list[dict[str, str]]:
    """Une entrée par famille de ligne corrigée : le capteur compare les familles d'un mois à l'autre."""
    vues: dict[str, str] = {}
    for ligne in lignes_corrigeables(payslip_data):
        if ligne.correction and ligne.code:
            vues.setdefault(famille_du_code(ligne.code), ligne.libelle)
    return [{"famille": famille, "libelle": libelle} for famille, libelle in vues.items()]


def _euros(valeur: Any) -> str:
    montant = float(valeur or 0.0)
    texte = f"{abs(montant):,.2f}".replace(",", " ").replace(".", ",")
    return f"{'−' if montant < 0 else ''}{texte} €"


def valeur_calculee_fr(bloc: str, valeur_calculee: Any) -> str:
    valeur = valeur_calculee if isinstance(valeur_calculee, Mapping) else {}
    if bloc == BLOC_IMPOT:
        return "un taux de " + f"{float(valeur.get('taux') or 0.0):.2f}".replace(".", ",") + " %"
    if bloc == BLOC_BRUT:
        montant = valeur.get("gain") if valeur.get("gain") is not None else valeur.get("perte")
        return _euros(montant)
    parts = []
    if valeur.get("montant_salarial"):
        parts.append(f"{_euros(valeur['montant_salarial'])} salarial")
    if valeur.get("montant_patronal"):
        parts.append(f"{_euros(valeur['montant_patronal'])} patronal")
    return " et ".join(parts) or _euros(0.0)


def explication_de_correction(ligne: Mapping[str, Any], bloc: str) -> str | None:
    correction = ligne.get("correction")
    if not isinstance(correction, Mapping):
        return None
    return (
        f"Corrigée à la main : {correction.get('motif') or ''}. "
        f"Martine avait calculé {valeur_calculee_fr(bloc, ligne.get('valeur_calculee'))}."
    )


def mentions_des_corrections(payslip_data: Any) -> list[str]:
    """Les notes du PDF : chaque ligne corrigée, son motif et la valeur de Martine."""
    mentions = []
    for ligne in lignes_corrigeables(payslip_data):
        if not ligne.correction:
            continue
        motif = ligne.correction.get("motif") or ""
        if ligne.bloc == BLOC_IMPOT:
            mentions.append(
                f"* Taux d'impôt corrigé à la main : {motif} "
                f"(Martine avait appliqué {valeur_calculee_fr(BLOC_IMPOT, ligne.valeur_calculee)})."
            )
        else:
            mentions.append(
                f"* Ligne corrigée à la main — {ligne.libelle} : {motif} "
                f"(Martine avait calculé {valeur_calculee_fr(ligne.bloc, ligne.valeur_calculee)})."
            )
    return mentions
```

Le texte attendu par le test du PDF pour l'impôt est « (Martine avait appliqué un taux de 5,20 %) » : `valeur_calculee_fr` rend « un taux de 5,20 % ».

- [ ] **Étape 4 : l'info-bulle, le PDF, la validation**

Dans `backend/app/modules/payroll/domain/explications_lignes.py`, ajouter les imports :

```python
from app.modules.payroll.engine.codes_des_lignes import BLOC_BRUT, BLOC_COTISATIONS
from app.modules.payroll.engine.corrections_du_bulletin import BLOCS_DE_GAINS, explication_de_correction
```

ajouter, avant `def _lignes_de(` :

```python
def _expliquer_corrections(bulletin: dict[str, Any]) -> None:
    """Une ligne corrigée à la main le dit au survol, avec ce que Martine avait
    calculé. Posée en dernier : elle remplace l'explication du calcul (celle de
    la réduction générale ne dit plus « régularisation depuis janvier »)."""
    for bloc in (*BLOCS_DE_GAINS, "details_maintien"):
        for ligne in _lignes_de(bulletin, bloc):
            _poser(ligne, explication_de_correction(ligne, BLOC_BRUT))
    structure = bulletin.get("structure_cotisations")
    if isinstance(structure, dict):
        for cle, valeur in structure.items():
            if isinstance(valeur, list):
                for ligne in _lignes_de(structure, cle):
                    _poser(ligne, explication_de_correction(ligne, BLOC_COTISATIONS))
    for rubrique in bulletin.get("cotisations_officielles") or []:
        if isinstance(rubrique, dict):
            for ligne in _lignes_de(rubrique, "lignes"):
                _poser(ligne, explication_de_correction(ligne, BLOC_COTISATIONS))
```

et, dans `poser_explications`, juste avant `return bulletin` : `    _expliquer_corrections(bulletin)`.

Dans `backend/app/modules/payroll/documents/bulletin_view.py`, ajouter `from app.modules.payroll.engine.corrections_du_bulletin import mentions_des_corrections`, puis :

```python
def _libelle_marque(source: Dict[str, Any]) -> str:
    """Une ligne corrigée à la main porte un astérisque ; sa note suit les cotisations."""
    libelle = source.get("libelle") or ""
    return f"{libelle} *" if isinstance(source.get("correction"), dict) else libelle
```

remplacer `source.get("libelle") or ""` par `_libelle_marque(source)` dans `_ligne_brut` et dans `_ligne_cotisation`, et dans `construire_lignes`, juste après la boucle des mentions de régularisations :

```python
    for mention in mentions_des_corrections(bulletin):
        lignes.append(_ligne("note", mention))
```

Dans `backend/app/modules/payslips/domain/coherence.py`, ajouter `from app.modules.payroll.engine.corrections_manuelles import CLE_CORRECTIONS_EN_ATTENTE`, la constante :

```python
MESSAGE_CORRECTION_EN_ATTENTE = (
    "Une correction faite à la main ne trouve plus sa ligne : retirez-la ou "
    "reportez-la sur une autre ligne (onglet « Corriger ») avant de valider."
)
```

et, dans `raisons_de_ne_pas_valider`, après le test de `recalcul_en_attente` :

```python
    if isinstance(payslip_data, dict) and payslip_data.get(CLE_CORRECTIONS_EN_ATTENTE):
        raisons.append(MESSAGE_CORRECTION_EN_ATTENTE)
```

- [ ] **Étape 5 : relancer les tests de la tâche, de la vue et des explications**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payroll/test_corrections_du_bulletin.py tests/unit/payslips/test_coherence_corrections_en_attente.py tests/unit/payroll/test_empreinte_entrees.py tests/unit/payroll/test_bulletin_view_regularisations.py tests/unit/payroll -q -k "bulletin_view or explication or coherence or empreinte or correction"
```

Attendu : tout passe.

- [ ] **Étape 6 : commiter**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2 && git add backend/app/modules/payroll/engine/corrections_du_bulletin.py backend/app/modules/payroll/domain/explications_lignes.py backend/app/modules/payroll/documents/bulletin_view.py backend/app/modules/payslips/domain/coherence.py backend/tests/unit/payroll/test_corrections_du_bulletin.py backend/tests/unit/payslips/test_coherence_corrections_en_attente.py backend/tests/unit/payroll/test_empreinte_entrees.py && git commit -m "feat(paie): une ligne corrigée à la main le dit à l'écran et sur le PDF, et une correction en attente bloque la validation

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 9 : la DSN suit une ligne corrigée

**Fichiers :**
- Tester : `backend/tests/unit/dsn_export/test_corrections_de_ligne_dsn.py` (créé)
- Modifier : rien, sauf si un test échoue (alors corriger `dsn_export/domain/cotisation_mapping.py` avec un test qui reproduit le cas).

**Interfaces :**
- Consomme : `build_bases_and_cotisations` (existant) ; une ligne corrigée est une ligne ordinaire (pas de drapeau `regularisation`) : elle se fond par la règle normale de `_cumuler`.
- Produit : la preuve, par famille, que la DSN recalcule juste ce que la règle 3 a posé. L'écriture comptable se vérifie au test du théorème (résidu nul, tâche 13) : elle lit `cotisations_detail`, le brut, le net et l'impôt du bulletin, qui portent déjà les valeurs corrigées.

- [ ] **Étape 1 : écrire les tests**

```python
"""La DSN recalcule base × taux sur plusieurs familles : une ligne corrigée par la
règle 3 y passe au centime (spec § 7). Chiffres sondés le 23/10."""

from __future__ import annotations

import pytest

from app.modules.dsn_export.domain.cotisation_mapping import build_bases_and_cotisations

pytestmark = pytest.mark.unit


def _dsn(lignes, brut=2000.0):
    _, cotisations, avertissements = build_bases_and_cotisations(
        lignes, brut=brut, period_start="2026-10-01", period_end="2026-10-31"
    )
    assert avertissements == []
    return {c.code: round(float(c.montant_patronal or 0.0), 2) for c in cotisations}


def test_une_maladie_corrigee_par_son_taux_se_scinde_en_socle_et_complement():
    ligne = {"coti_id": "securite_sociale_maladie", "libelle": "Maladie, maternité, invalidité, décès",
             "base": 2000.0, "taux_salarial": 0.0, "taux_patronal": 0.073, "montant_salarial": 0.0,
             "montant_patronal": 146.0, "correction": {"saisie_id": "c1"}, "valeur_calculee": {"montant_patronal": 140.0}}
    assert _dsn([ligne]) == {"075": 140.0, "907": 6.0}


def test_une_csg_corrigee_par_sa_base_se_recalcule_au_centime():
    lignes = [
        {"coti_id": "csg_deductible", "libelle": "CSG déductible", "base": 2100.0, "taux_salarial": 0.068,
         "taux_patronal": None, "montant_salarial": 142.8, "montant_patronal": 0.0, "correction": {"saisie_id": "c1"}},
        {"coti_id": "csg_non_deductible", "libelle": "CSG/CRDS non déductible", "base": 2000.0, "taux_salarial": 0.029,
         "taux_patronal": None, "montant_salarial": 58.0, "montant_patronal": 0.0},
    ]
    dsn = _dsn(lignes)
    assert round(dsn["072"] + dsn["079"], 2) == round(142.8 + 58.0, 2)


def test_une_reduction_generale_corrigee_se_declare_pour_son_montant():
    lignes = [
        {"coti_id": "vieillesse_plafonnee", "libelle": "Vieillesse plafonnée", "base": 2000.0, "taux_salarial": 0.069,
         "taux_patronal": 0.0855, "montant_salarial": 138.0, "montant_patronal": 171.0},
        {"coti_id": "reduction_generale", "libelle": "Réduction générale de cotisations patronales", "base": 2000.0,
         "taux_salarial": None, "taux_patronal": 0.1978, "montant_salarial": 0.0, "montant_patronal": -250.0,
         "smic_reference_mois": 1823.03, "correction": {"saisie_id": "c1"}},
    ]
    dsn = _dsn(lignes)
    assert round(dsn["018"] + dsn["106"], 2) == -250.0
```

- [ ] **Étape 2 : lancer les tests**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/dsn_export/test_corrections_de_ligne_dsn.py tests/unit/dsn_export/test_regularisations_dsn.py -q
```

Attendu : tout passe sans toucher au code (sonde du 23/10 : 075 = 140,00 et 907 = 6,00 ; 072 + 079 = 200,80 ; 018 + 106 = −250,00). Si un test échoue, c'est un défaut de la DSN : le reproduire, le corriger dans `cotisation_mapping.py`, relancer aussi `tests/unit/dsn_export`.

Limite connue, à vérifier au premier dépôt réel (spec § 7) : une base de CSG corrigée sur une seule des deux lignes de CSG fait compter deux assiettes dans la base 04 (bloc 78) ; les montants (bloc 81) restent justes.

- [ ] **Étape 3 : commiter**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2 && git add backend/tests/unit/dsn_export/test_corrections_de_ligne_dsn.py && git commit -m "test(dsn): une ligne corrigée par sa base, son taux ou son montant se déclare au centime

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 10 : la route — écrire, vérifier, retirer, restaurer ; lire les lignes corrigeables

**Fichiers :**
- Modifier : `backend/app/modules/payslips/schemas/requests.py` (classe `CorrectionLigneAjoutee`, deux champs de `CorrectionsBulletinRequest`)
- Modifier : `backend/app/modules/payslips/domain/corrections.py` (`CorrectionsBulletin`, `resume_des_corrections`, `refus_des_corrections`, `corrections_pour_revenir`)
- Modifier : `backend/app/modules/payslips/application/dto.py` (`CorrigerBulletinInput.verifier_les_lignes`)
- Modifier : `backend/app/modules/payslips/application/corrections.py`
- Créer : `backend/app/modules/payslips/application/lignes_corrigeables.py`
- Modifier : `backend/app/modules/payslips/schemas/responses.py`, `backend/app/modules/payslips/api/router.py`
- Tester : `backend/tests/unit/payslips/test_corrections_de_ligne_route.py` (créé), `backend/tests/unit/payslips/test_corrections_restauration_regularisations.py` (ajouts)

**Interfaces :**
- Consomme : `CorrectionDeLigne`, `CorrectionInvalide`, `PAR_MODE` (tâche 2) ; `lignes_corrigeables`, `corrections_du_bulletin`, `corrections_en_attente_du_bulletin` (tâche 8).
- Produit :
  - requête : `corrections.corrections_ajoutees: list[CorrectionLigneAjoutee]` (champs `ligne`, `libelle`, `motif`, `base`, `taux`, `montant`, `taux_salarial`, `taux_patronal`, `montant_salarial`, `montant_patronal`) et `corrections.corrections_retirees: list[str]` (identifiants de saisie) ;
  - domaine : `CorrectionsBulletin.corrections_ajoutees: tuple[CorrectionDeLigne, ...]`, `.corrections_retirees: tuple[str, ...]` ; `refus_des_corrections(corrections, payslip_data) -> str | None` ;
  - `CorrigerBulletinInput.verifier_les_lignes: bool = True` (la restauration passe `False`) ;
  - `lire_lignes_corrigeables(payslip_id) -> {"lignes": [...], "en_attente": [...]}` et la route `GET /api/payslips/{payslip_id}/lignes-corrigeables` (permission `payslips.edit`) qui rend `LignesCorrigeablesResponse`.

- [ ] **Étape 1 : écrire les tests qui échouent**

Créer `backend/tests/unit/payslips/test_corrections_de_ligne_route.py` :

```python
"""Corriger une ligne depuis le bulletin : la requête, la vérification, l'écriture, la lecture."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from app.modules.payroll.engine.corrections_manuelles import CorrectionDeLigne
from app.modules.payslips.application import corrections as mod
from app.modules.payslips.application import lignes_corrigeables as lecture
from app.modules.payslips.application.dto import CorrigerBulletinInput, PayslipBadRequestError
from app.modules.payslips.domain.corrections import CorrectionsBulletin, refus_des_corrections, resume_des_corrections
from app.modules.payslips.schemas.requests import PayslipEditRequest
from app.modules.payslips.schemas.responses import LignesCorrigeablesResponse
from tests.unit.payslips.test_corrections import BULLETIN, FauxClient

pytestmark = pytest.mark.unit

SALAIRE = {"libelle": "Salaire de base", "quantite": 151.67, "taux": 16.4832, "gain": 2500.0, "perte": None}
DONNEES = {
    "salaire_brut": 2500.0,
    "calcul_du_brut": [SALAIRE],
    "cotisations_officielles": [{"code": "sante", "lignes": [
        {"coti_id": "allocations_familiales", "libelle": "Allocations familiales", "base": 2500.0,
         "taux_salarial": None, "taux_patronal": 0.0525, "montant_salarial": 0.0, "montant_patronal": 131.25},
    ]}],
}
AJOUT = {"ligne": "brut:salaire_base", "libelle": "Salaire de base", "motif": "Avenant", "base": 160.0}


def _c(**champs):
    return CorrectionDeLigne(**{**AJOUT, **champs})


def test_la_requete_refuse_une_correction_sans_motif_ou_ambigue():
    with pytest.raises(ValidationError):
        PayslipEditRequest(corrections={"corrections_ajoutees": [{**AJOUT, "motif": ""}]})
    with pytest.raises(ValidationError):
        PayslipEditRequest(corrections={"corrections_ajoutees": [{**AJOUT, "montant": 2600.0}]})


def test_la_requete_donne_les_corrections_au_domaine():
    requete = PayslipEditRequest(corrections={"corrections_ajoutees": [AJOUT], "corrections_retirees": ["c9", "c9"]})
    domaine = requete.corrections.vers_domaine()
    assert domaine.corrections_ajoutees == (_c(),)
    assert domaine.corrections_retirees == ("c9",)
    assert domaine.change_des_variables


@pytest.mark.parametrize(
    "correction, retirees, donnees, morceau",
    [
        (_c(ligne="brut:precarite", libelle="Prime de précarité (CDD)", base=None, montant=1.0), (), DONNEES, "n'est plus sur le bulletin"),
        (_c(base=None, montant=2600.0), (), DONNEES, "se corrige par sa base ou son taux"),
        (_c(ligne="cotisation:allocations_familiales", libelle="Allocations familiales", base=None, taux_salarial=0.01), (), DONNEES, "n'a pas de taux salarial"),
        (_c(), (), {**DONNEES, "calcul_du_brut": [{**SALAIRE, "correction": {"saisie_id": "c1"}}]}, "déjà corrigée"),
    ],
)
def test_une_correction_qui_ne_tient_pas_sur_le_bulletin_est_refusee(correction, retirees, donnees, morceau):
    refus = refus_des_corrections(CorrectionsBulletin(corrections_ajoutees=(correction,), corrections_retirees=retirees), donnees)
    assert refus is not None and morceau in refus


def test_corriger_a_nouveau_une_ligne_retire_l_ancienne_correction_dans_le_meme_enregistrement():
    donnees = {**DONNEES, "calcul_du_brut": [{**SALAIRE, "correction": {"saisie_id": "c1"}}]}
    corrections = CorrectionsBulletin(corrections_ajoutees=(_c(),), corrections_retirees=("c1",))
    assert refus_des_corrections(corrections, donnees) is None
    assert refus_des_corrections(CorrectionsBulletin(corrections_ajoutees=(_c(), _c(base=170.0))), DONNEES) is not None


def test_le_resume_nomme_la_ligne_corrigee():
    texte = resume_des_corrections(CorrectionsBulletin(corrections_ajoutees=(_c(),), corrections_retirees=("c9",)))
    assert "ligne « salaire de base » corrigée : avenant" in texte.lower()
    assert "1 correction retirée" in texte


@pytest.fixture
def base():
    client = FauxClient()
    etat = {"bulletin": {**BULLETIN, "payslip_data": DONNEES}}
    with (
        patch.object(mod, "supabase", client),
        patch.object(mod, "_lire_bulletin", side_effect=lambda _id: dict(etat["bulletin"])),
        patch.object(mod, "_relire_en_entier", side_effect=lambda _id: dict(etat["bulletin"])),
        patch.object(mod, "_refuser_si_importe"),
        patch.object(mod, "verifier_appartenance"),
        patch.object(mod, "salarie_generable"),
        patch.object(mod, "reimprimer_bulletin"),
        patch.object(mod, "generate_payslip") as generer,
    ):
        generer.return_value = MagicMock(status="success")
        client.generer = generer
        yield client


def _corriger(corrections, **kwargs):
    return mod.corriger_bulletin(
        CorrigerBulletinInput(payslip_id="ps-1", corrections=corrections, current_user_id="rh-1", current_user_name="RH", **kwargs)
    )


def test_corriger_une_ligne_ecrit_une_saisie_du_mois_puis_recalcule(base):
    _corriger(CorrectionsBulletin(corrections_ajoutees=(_c(),)))
    saisie = base.de("monthly_inputs", "insert")[0][2][0]
    assert saisie["correction_ligne"] == {**_c().charge_utile()}
    assert saisie["employee_id"] == "emp-1" and saisie["month"] == 8
    assert base.generer.called


def test_une_correction_refusee_n_ecrit_rien(base):
    with pytest.raises(PayslipBadRequestError):
        _corriger(CorrectionsBulletin(corrections_ajoutees=(_c(base=None, montant=2600.0),)))
    assert base.ecritures == [] and not base.generer.called


def test_retirer_une_correction_supprime_la_seule_saisie_du_bulletin(base):
    _corriger(CorrectionsBulletin(corrections_retirees=("c9",)))
    filtres = dict(base.de("monthly_inputs", "delete")[0][3])
    assert filtres["id"] == ("c9",) and filtres["employee_id"] == "emp-1" and filtres["month"] == 8


def test_la_restauration_ne_verifie_pas_les_lignes(base):
    _corriger(CorrectionsBulletin(corrections_ajoutees=(_c(ligne="brut:precarite", libelle="Prime de précarité (CDD)", base=None, montant=1.0),)), verifier_les_lignes=False)
    assert base.de("monthly_inputs", "insert")


def test_la_lecture_rend_les_lignes_et_les_corrections_en_attente():
    reponse = MagicMock(data={"payslip_data": {**DONNEES, "corrections_en_attente": [
        {**_c(ligne="brut:precarite", libelle="Prime de précarité (CDD)", base=None, montant=1.0).trace(), "saisie_id": "c3", "raison": "Ligne disparue."}
    ]}})
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = reponse
    with patch.object(lecture, "supabase", client):
        lu = lecture.lire_lignes_corrigeables("ps-1")
    modele = LignesCorrigeablesResponse(**lu)
    assert [l.code for l in modele.lignes] == ["brut:salaire_base", "cotisation:allocations_familiales"]
    assert modele.lignes[0].mode == "base_ou_taux"
    assert modele.en_attente[0].saisie_id == "c3" and modele.en_attente[0].raison == "Ligne disparue."
```

Dans `backend/tests/unit/payslips/test_corrections_restauration_regularisations.py`, ajouter :

```python
from app.modules.payroll.engine.codes_des_lignes import BLOC_BRUT
from app.modules.payroll.engine.corrections_manuelles import CorrectionDeLigne, JournalDesCorrections


def _avec_correction(saisie_id, base):
    ligne = {"libelle": "Salaire de base", "quantite": 151.67, "taux": 16.4832, "gain": 2500.0, "perte": None}
    correction = CorrectionDeLigne(ligne="brut:salaire_base", libelle="Salaire de base", motif="Avenant", base=base, saisie_id=saisie_id)
    JournalDesCorrections([correction]).corriger(ligne, BLOC_BRUT, "brut:salaire_base")
    return {"calcul_du_brut": [ligne]}


def test_une_correction_de_ligne_ajoutee_depuis_la_version_est_retiree():
    c = corrections_pour_revenir(_avec_correction("c2", 170.0), {"calcul_du_brut": []})
    assert c.corrections_retirees == ("c2",) and c.corrections_ajoutees == ()


def test_une_correction_de_ligne_disparue_depuis_la_version_est_recreee():
    c = corrections_pour_revenir({"calcul_du_brut": []}, _avec_correction("c1", 160.0))
    assert [x.base for x in c.corrections_ajoutees] == [160.0]
    assert c.corrections_ajoutees[0].saisie_id is None


def test_une_correction_en_attente_de_la_version_revient_aussi():
    cible = {"corrections_en_attente": [{"type": "correction", "ligne": "brut:precarite", "libelle": "Prime de précarité (CDD)",
                                         "motif": "CDD prolongé", "montant": 0.0, "saisie_id": "c3", "raison": "…"}]}
    c = corrections_pour_revenir({}, cible)
    assert [x.ligne for x in c.corrections_ajoutees] == ["brut:precarite"]
```

- [ ] **Étape 2 : lancer les tests pour les voir échouer**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payslips/test_corrections_de_ligne_route.py tests/unit/payslips/test_corrections_restauration_regularisations.py -q
```

Attendu : erreurs d'import (`refus_des_corrections`, `lignes_corrigeables`, `LignesCorrigeablesResponse`).

- [ ] **Étape 3 : la requête**

Dans `backend/app/modules/payslips/schemas/requests.py`, compléter l'import des corrections manuelles avec `CorrectionDeLigne, CorrectionInvalide`, ajouter après `RegularisationAjoutee` :

```python
class CorrectionLigneAjoutee(BaseModel):
    """Une ligne corrigée depuis le bulletin : sa base, son taux ou son montant,
    selon ce que la ligne porte (règle 3). Le serveur calcule le montant."""

    model_config = ConfigDict(extra="forbid")

    ligne: str = Field(..., min_length=1, max_length=200)
    libelle: str = Field(..., min_length=1, max_length=160)
    motif: str = Field(..., min_length=3, max_length=300)
    base: float | None = Field(None, ge=-1_000_000, le=1_000_000)
    taux: float | None = Field(None, ge=-1_000, le=1_000)
    montant: float | None = Field(None, ge=-1_000_000, le=1_000_000)
    taux_salarial: float | None = Field(None, ge=-1, le=1)
    taux_patronal: float | None = Field(None, ge=-1, le=1)
    montant_salarial: float | None = Field(None, ge=-100_000, le=100_000)
    montant_patronal: float | None = Field(None, ge=-100_000, le=100_000)

    @model_validator(mode="after")
    def _correction_coherente(self) -> "CorrectionLigneAjoutee":
        try:
            self.vers_domaine()
        except CorrectionInvalide as exc:
            raise ValueError(str(exc)) from exc
        return self

    def vers_domaine(self) -> CorrectionDeLigne:
        return CorrectionDeLigne(**self.model_dump())
```

et dans `CorrectionsBulletinRequest` :

```python
    corrections_ajoutees: list[CorrectionLigneAjoutee] = Field(default_factory=list, max_length=20)
    corrections_retirees: list[str] = Field(default_factory=list, max_length=50)
```

puis, dans son `vers_domaine`, passer à `CorrectionsBulletin(...)` :

```python
            corrections_ajoutees=tuple(c.vers_domaine() for c in self.corrections_ajoutees),
            corrections_retirees=tuple(dict.fromkeys(self.corrections_retirees)),
```

- [ ] **Étape 4 : le domaine**

Dans `backend/app/modules/payslips/domain/corrections.py`, compléter les imports :

```python
from app.modules.payroll.engine.corrections_du_bulletin import corrections_du_bulletin, lignes_corrigeables
from app.modules.payroll.engine.corrections_manuelles import (
    PAR_MODE,
    CorrectionDeLigne,
    RegularisationCotisation,
    regularisations_du_bulletin,
)
```

ajouter à `CorrectionsBulletin` :

```python
    #: Corrections de ligne à ajouter, puis identifiants de saisie à retirer.
    corrections_ajoutees: tuple[CorrectionDeLigne, ...] = ()
    corrections_retirees: tuple[str, ...] = ()
```

et à `change_des_variables` : `or bool(self.corrections_ajoutees) or bool(self.corrections_retirees)`.

Dans `resume_des_corrections`, avant `if not parties:` :

```python
    for correction in corrections.corrections_ajoutees:
        parties.append(f"ligne « {correction.libelle} » corrigée : {correction.motif}")
    if corrections.corrections_retirees:
        n = len(corrections.corrections_retirees)
        parties.append(f"{n} correction{'s' if n > 1 else ''} retirée{'s' if n > 1 else ''}")
```

Ajouter :

```python
_NOMS_DES_TAUX = {"taux": "taux", "taux_salarial": "taux salarial", "taux_patronal": "taux patronal"}


def refus_des_corrections(corrections: CorrectionsBulletin, payslip_data: dict[str, Any] | None) -> str | None:
    """Pourquoi une correction ajoutée ne tient pas sur ce bulletin, ou None.

    La ligne doit exister, se corriger par les champs reçus (règle 3), porter le
    taux corrigé, et ne pas être déjà corrigée — sauf si sa correction est
    retirée dans le même enregistrement.
    """
    if not corrections.corrections_ajoutees:
        return None
    par_code = {ligne.code: ligne for ligne in lignes_corrigeables(payslip_data) if ligne.code}
    retirees = set(corrections.corrections_retirees)
    visees: set[str] = set()
    for correction in corrections.corrections_ajoutees:
        ligne = par_code.get(correction.ligne)
        if ligne is None:
            return f"La ligne « {correction.libelle} » n'est plus sur le bulletin : rechargez-le."
        if ligne.mode is None:
            return f"« {ligne.libelle} » : {ligne.raison}"
        if not correction.convient(ligne.mode):
            return f"« {ligne.libelle} » se corrige par {PAR_MODE[ligne.mode]}."
        for champ, nom in _NOMS_DES_TAUX.items():
            if getattr(correction, champ) is not None and getattr(ligne, champ) is None:
                return f"« {ligne.libelle} » n'a pas de {nom} : corrigez ce qu'elle porte."
        deja = (ligne.correction or {}).get("saisie_id")
        if deja and str(deja) not in retirees:
            return f"« {ligne.libelle} » est déjà corrigée : retirez d'abord sa correction."
        if correction.ligne in visees:
            return f"« {ligne.libelle} » est corrigée deux fois : gardez une seule correction."
        visees.add(correction.ligne)
    return None
```

Dans `corrections_pour_revenir`, avant le `return`, ajouter :

```python
    corrections_courant = corrections_du_bulletin(courant)
    corrections_cible = corrections_du_bulletin(cible)
    corrections_retirees = tuple(sid for sid in corrections_courant if sid not in corrections_cible)
    corrections_ajoutees = tuple(
        CorrectionDeLigne.depuis(correction.charge_utile())
        for sid, correction in corrections_cible.items()
        if sid not in corrections_courant and sid not in saisies_existantes
    )
```

et passer `corrections_ajoutees=corrections_ajoutees, corrections_retirees=corrections_retirees` au `CorrectionsBulletin(...)` rendu. Compléter sa docstring : « Les corrections de ligne reviennent de même ; une correction dont la ligne n'existe plus revient en attente. »

- [ ] **Étape 5 : l'application**

Dans `backend/app/modules/payslips/application/dto.py`, ajouter à `CorrigerBulletinInput` :

```python
    #: Vérifier que chaque correction ajoutée tient sur le bulletin. La
    #: restauration d'une version ne le fait pas : une correction dont la ligne
    #: n'existe plus revient en attente et bloque la validation (règle 7).
    verifier_les_lignes: bool = True
```

Dans `backend/app/modules/payslips/application/corrections.py` :
- importer `refus_des_corrections` depuis `domain.corrections`, `corrections_du_bulletin` depuis `app.modules.payroll.engine.corrections_du_bulletin`, `regularisations_du_bulletin` depuis `app.modules.payroll.engine.corrections_manuelles` ;
- ajouter, après `_ecrire_regularisations` :

```python
def _ecrire_corrections_de_ligne(corrections: CorrectionsBulletin, periode: dict[str, Any]) -> None:
    """Ajoute et retire les corrections de ligne du mois, pour ce seul salarié et ce seul mois."""
    if corrections.corrections_retirees:
        (
            supabase.table("monthly_inputs")
            .delete()
            .match(periode)
            .in_("id", list(corrections.corrections_retirees))
            .execute()
        )
    if corrections.corrections_ajoutees:
        supabase.table("monthly_inputs").insert(
            [correction.saisie_du_mois(periode) for correction in corrections.corrections_ajoutees]
        ).execute()
```

- dans `_ecrire_variables`, après `_ecrire_regularisations(corrections, periode)` : `    _ecrire_corrections_de_ligne(corrections, periode)` ;
- dans `corriger_bulletin`, juste après `_refuser_si_modifie_depuis(bulletin, cmd.base_updated_at)` et `corrections = cmd.corrections` :

```python
    if cmd.verifier_les_lignes:
        refus = refus_des_corrections(corrections, bulletin.get("payslip_data"))
        if refus:
            raise PayslipBadRequestError(refus)
```

- dans `restaurer_version`, remplacer le calcul de `saisies_existantes` par :

```python
    identifiants = (
        set(primes_saisies_du_bulletin(cible))
        | set(regularisations_du_bulletin(cible))
        | set(corrections_du_bulletin(cible))
    )
    corrections = corrections_pour_revenir(
        bulletin.get("payslip_data"),
        cible,
        saisies_existantes=_saisies_existantes(identifiants, periode),
    )
```

  et passer `verifier_les_lignes=False` au `CorrigerBulletinInput(...)` qu'elle construit ;
- remplacer `MESSAGE_RIEN_A_RESTAURER` par :

```python
MESSAGE_RIEN_A_RESTAURER = (
    "Cette version a déjà les mêmes heures sup, primes, régularisations et "
    "corrections que le bulletin : rien à restaurer. Le reste (planning, "
    "absences, salaire) se corrige à sa source."
)
```

Créer `backend/app/modules/payslips/application/lignes_corrigeables.py` :

```python
"""Les lignes d'un bulletin et ce qui s'y corrige, pour la carte « Corriger une ligne »."""

from __future__ import annotations

from typing import Any

from app.core.database import supabase
from app.modules.payroll.engine.corrections_du_bulletin import (
    corrections_en_attente_du_bulletin,
    lignes_corrigeables,
)
from app.modules.payslips.application.dto import PayslipNotFoundError

_CHAMPS_EN_ATTENTE = ("saisie_id", "ligne", "libelle", "motif", "raison")


def lire_lignes_corrigeables(payslip_id: str) -> dict[str, Any]:
    reponse = (
        supabase.table("payslips").select("payslip_data").eq("id", payslip_id).maybe_single().execute()
    )
    if not reponse or not reponse.data:
        raise PayslipNotFoundError("Bulletin non trouvé")
    donnees = reponse.data.get("payslip_data") or {}
    return {
        "lignes": [ligne.en_dict() for ligne in lignes_corrigeables(donnees)],
        "en_attente": [
            {cle: entree.get(cle) for cle in _CHAMPS_EN_ATTENTE}
            for entree in corrections_en_attente_du_bulletin(donnees)
        ],
    }
```

Dans `backend/app/modules/payslips/schemas/responses.py` (ajouter `Literal` à l'import de `typing` s'il n'y est pas) :

```python
class LigneCorrigeableResponse(BaseModel):
    """Une ligne du bulletin, son code et par quoi elle se corrige (règle 3)."""

    code: str | None = None
    bloc: Literal["brut", "cotisations", "impot"]
    libelle: str
    mode: Literal["base_ou_taux", "montant", "taux"] | None = None
    raison: str | None = None
    retenue: bool = False
    base: float | None = None
    taux: float | None = None
    montant: float | None = None
    taux_salarial: float | None = None
    taux_patronal: float | None = None
    montant_salarial: float | None = None
    montant_patronal: float | None = None
    correction: dict[str, Any] | None = None
    valeur_calculee: dict[str, Any] | None = None


class CorrectionEnAttenteResponse(BaseModel):
    """Une correction qui ne trouve plus sa ligne : à retirer ou à reporter."""

    saisie_id: str | None = None
    ligne: str
    libelle: str
    motif: str
    raison: str


class LignesCorrigeablesResponse(BaseModel):
    lignes: list[LigneCorrigeableResponse]
    en_attente: list[CorrectionEnAttenteResponse]
```

Dans `backend/app/modules/payslips/api/router.py`, importer `lire_lignes_corrigeables` et `LignesCorrigeablesResponse`, et ajouter, avant la route `GET /api/payslips/{payslip_id}/history` :

```python
# --- Lignes corrigeables (carte « Corriger une ligne ») ---
@router.get("/api/payslips/{payslip_id}/lignes-corrigeables", response_model=LignesCorrigeablesResponse)
def get_lignes_corrigeables_route(
    payslip_id: str,
    current_user: User = Depends(get_current_user),
):
    """Les lignes du bulletin, leur code et ce qui s'y corrige ; les corrections en attente."""
    try:
        _require_payslip_scope(current_user, payslip_id, "payslips.edit")
        return LignesCorrigeablesResponse(**lire_lignes_corrigeables(payslip_id))
    except _PAYSLIP_APP_ERRORS as e:
        _map_app_errors(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Échec de get_lignes_corrigeables_route")
        raise HTTPException(status_code=500, detail=MESSAGE_ERREUR_INTERNE)
```

- [ ] **Étape 6 : relancer les tests de la tâche et ceux des bulletins**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payslips -q
```

Attendu : tout passe (un test qui affirmait l'ancien texte de `MESSAGE_RIEN_A_RESTAURER` se met à jour avec le nouveau, en important la constante).

- [ ] **Étape 7 : commiter**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2 && git add backend/app/modules/payslips && git add backend/tests/unit/payslips && git commit -m "feat(paie): corriger un bulletin ajoute, vérifie, retire et restaure les corrections de ligne, et la route dit ce qui se corrige

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 11 : l'écran — la carte « Corriger une ligne »

**Fichiers :**
- Modifier : `frontend/src/api/payslips.ts` (types, `CorrectionsBulletin`, `getLignesCorrigeables`)
- Modifier : `frontend/src/lib/queryKeys.ts` (`lignesCorrigeables`)
- Modifier : `frontend/src/features/payroll/utils/correctionsBulletin.ts` (état, requête, champs, aperçu, résumé)
- Créer : `frontend/src/components/payslip-edit/CorrigerUneLigneCard.tsx`
- Modifier : `frontend/src/components/payslip-edit/CorrectionsBulletinPanel.tsx`, `frontend/src/pages/rh/PayslipEdit.tsx`
- Tester : `frontend/src/features/payroll/utils/corrigerUneLigne.test.ts` (créé)

**Interfaces :**
- Consomme : la route de la tâche 10 (`GET /api/payslips/{id}/lignes-corrigeables` → `{ lignes, en_attente }`) et les champs `corrections.corrections_ajoutees` / `corrections.corrections_retirees` de `POST /api/payslips/{id}/edit`.
- Produit : `EtatCorrections.correctionsAjoutees: CorrectionLigneAjoutee[]` et `.correctionsRetirees: string[]` ; `champsDeLaLigne`, `correctionDeLigne`, `apercuDuMontant`, `eurosFr`, `resumeDeLaCorrection` ; la carte, branchée après « Régularisations de cotisation ». Les codes et la règle 3 viennent du serveur : l'écran ne les recalcule pas.

- [ ] **Étape 1 : écrire les tests qui échouent**

Créer `frontend/src/features/payroll/utils/corrigerUneLigne.test.ts` :

```ts
import { describe, expect, it } from 'vitest';

import type { LigneCorrigeable } from '@/api/payslips';
import {
  apercuDuMontant,
  champsDeLaLigne,
  correctionDeLigne,
  etatInitial,
  eurosFr,
  recalculAttendu,
  requeteDeCorrection,
  resumeDeLaCorrection,
} from './correctionsBulletin';

const SALAIRE: LigneCorrigeable = {
  code: 'brut:salaire_base',
  bloc: 'brut',
  libelle: 'Salaire de base',
  mode: 'base_ou_taux',
  base: 151.67,
  taux: 16.4832,
  montant: 2500,
};
const MALADIE: LigneCorrigeable = {
  code: 'cotisation:securite_sociale_maladie',
  bloc: 'cotisations',
  libelle: 'Maladie',
  mode: 'base_ou_taux',
  base: 2000,
  taux_salarial: 0,
  taux_patronal: 0.07,
  montant_salarial: 0,
  montant_patronal: 140,
};
const IMPOT: LigneCorrigeable = {
  code: 'impot',
  bloc: 'impot',
  libelle: 'Impôt sur le revenu prélevé à la source',
  mode: 'taux',
  base: 2063.56,
  taux: 5.2,
  montant: 107.31,
};

describe('corriger une ligne', () => {
  it('une ligne en heures se corrige par sa base ou son taux', () => {
    expect(champsDeLaLigne(SALAIRE).map((c) => c.cle)).toEqual(['base', 'taux']);
  });

  it('une ligne au forfait se corrige par son montant, et une retenue le dit', () => {
    expect(champsDeLaLigne({ ...SALAIRE, mode: 'montant', retenue: true })).toEqual([
      { cle: 'montant', libelle: 'Retenue (€)', valeur: 2500 },
    ]);
  });

  it('une ligne qui ne se corrige pas ici ne propose rien', () => {
    expect(champsDeLaLigne({ ...SALAIRE, mode: null, raison: 'Une prime saisie se corrige dans « Primes du mois ».' })).toEqual([]);
  });

  it('une cotisation montre ses taux en pourcentage et la correction les envoie en fraction', () => {
    const champs = champsDeLaLigne(MALADIE);
    expect(champs.map((c) => c.cle)).toEqual(['base', 'taux_salarial', 'taux_patronal']);
    expect(champs[2].valeur).toBeCloseTo(7);
    expect(correctionDeLigne(MALADIE, 'taux_patronal', 7.3, ' Taux AT 2026 ')).toEqual({
      ligne: 'cotisation:securite_sociale_maladie',
      libelle: 'Maladie',
      motif: 'Taux AT 2026',
      taux_patronal: 0.073,
    });
  });

  it('l’aperçu suit base × taux au centime', () => {
    expect(apercuDuMontant(SALAIRE, 'base', 160)).toBe(2637.31);
    expect(apercuDuMontant(MALADIE, 'base', 2100)).toBe(147);
    expect(apercuDuMontant(IMPOT, 'taux', 7.5)).toBe(154.77);
    expect(apercuDuMontant(SALAIRE, 'base', Number.NaN)).toBeNull();
  });

  it('le résumé dit ce que Martine avait calculé et ce qui est imposé', () => {
    const corrigee: LigneCorrigeable = {
      ...SALAIRE,
      base: 160,
      montant: 2637.31,
      correction: { ligne: 'brut:salaire_base', libelle: 'Salaire de base', motif: 'Avenant', base: 160, saisie_id: 'c1' },
      valeur_calculee: { quantite: 151.67, taux: 16.4832, gain: 2500, perte: null },
    };
    expect(resumeDeLaCorrection(corrigee)).toBe('Martine : 2 500,00 € → corrigé : 2 637,31 €');
    expect(eurosFr(-1234.5)).toBe('−1 234,50 €');
  });

  it('la requête porte les corrections ajoutées et retirées, et le bulletin sera recalculé', () => {
    const initial = etatInitial({}, null);
    expect(initial.correctionsAjoutees).toEqual([]);
    const courant = {
      ...initial,
      correctionsAjoutees: [correctionDeLigne(SALAIRE, 'base', 160, 'Avenant')],
      correctionsRetirees: ['c9'],
    };
    const requete = requeteDeCorrection(initial, courant, null);
    expect(requete.corrections.corrections_ajoutees).toEqual([
      { ligne: 'brut:salaire_base', libelle: 'Salaire de base', motif: 'Avenant', base: 160 },
    ]);
    expect(requete.corrections.corrections_retirees).toEqual(['c9']);
    expect(recalculAttendu(initial, courant)).toBe(true);
  });
});
```

- [ ] **Étape 2 : lancer les tests pour les voir échouer**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/frontend && npx vitest run src/features/payroll/utils/corrigerUneLigne.test.ts
```

Attendu : échec à l'import (`champsDeLaLigne` n'existe pas).

- [ ] **Étape 3 : les types et la lecture**

Dans `frontend/src/api/payslips.ts`, après `RegularisationAjoutee` :

```ts
/** Une ligne corrigée depuis le bulletin : sa base, son taux ou son montant, selon la règle 3. */
export interface CorrectionLigneAjoutee {
  /** Le code de la ligne, donné par le serveur. */
  ligne: string;
  libelle: string;
  motif: string;
  base?: number | null;
  taux?: number | null;
  montant?: number | null;
  taux_salarial?: number | null;
  taux_patronal?: number | null;
  montant_salarial?: number | null;
  montant_patronal?: number | null;
}

export type ModeDeCorrection = 'base_ou_taux' | 'montant' | 'taux';

/** Une ligne du bulletin et ce qui s'y corrige (`GET /api/payslips/{id}/lignes-corrigeables`). */
export interface LigneCorrigeable {
  code: string | null;
  bloc: 'brut' | 'cotisations' | 'impot';
  libelle: string;
  /** null : la ligne ne se corrige pas ici, `raison` dit où. */
  mode: ModeDeCorrection | null;
  raison?: string | null;
  /** Une retenue (absence…) : son montant est ce qui est retiré. */
  retenue?: boolean;
  base?: number | null;
  taux?: number | null;
  montant?: number | null;
  taux_salarial?: number | null;
  taux_patronal?: number | null;
  montant_salarial?: number | null;
  montant_patronal?: number | null;
  correction?: (CorrectionLigneAjoutee & { saisie_id?: string | null }) | null;
  valeur_calculee?: Record<string, number | null> | null;
}

/** Une correction qui ne trouve plus sa ligne : elle bloque la validation. */
export interface CorrectionEnAttente {
  saisie_id: string | null;
  ligne: string;
  libelle: string;
  motif: string;
  raison: string;
}

export interface LignesCorrigeables {
  lignes: LigneCorrigeable[];
  en_attente: CorrectionEnAttente[];
}
```

ajouter à `CorrectionsBulletin` :

```ts
  corrections_ajoutees?: CorrectionLigneAjoutee[];
  corrections_retirees?: string[];
```

et, à côté de `getRevueDuMois` :

```ts
export async function getLignesCorrigeables(
  payslipId: string,
  companyId?: string | null,
): Promise<LignesCorrigeables> {
  const response = await apiClient.get<LignesCorrigeables>(
    `/api/payslips/${encodeURIComponent(payslipId)}/lignes-corrigeables`,
    { ...enTeteSociete(companyId) },
  );
  return response.data;
}
```

Dans `frontend/src/lib/queryKeys.ts`, à côté de `revueDuMois` :

```ts
  lignesCorrigeables: (companyId: string | undefined, payslipId: string, version: string | null | undefined) =>
    companyQueryKey(companyId, 'payslips', 'lignes-corrigeables', payslipId, version ?? ''),
```

(si le type du paramètre `companyId` de `revueDuMois` diffère, reprendre exactement le sien).

- [ ] **Étape 4 : l'état, la requête, les champs, l'aperçu, le résumé**

Dans `frontend/src/features/payroll/utils/correctionsBulletin.ts` : importer `CorrectionLigneAjoutee` et `LigneCorrigeable` depuis `@/api/payslips` ; ajouter à `EtatCorrections` :

```ts
  correctionsAjoutees: CorrectionLigneAjoutee[];
  correctionsRetirees: string[];
```

à `etatInitial` : `correctionsAjoutees: [], correctionsRetirees: [],` ; dans `requeteDeCorrection`, après les régularisations :

```ts
  if (courant.correctionsAjoutees.length) corrections.corrections_ajoutees = courant.correctionsAjoutees;
  if (courant.correctionsRetirees.length) corrections.corrections_retirees = courant.correctionsRetirees;
```

puis ajouter en fin de fichier :

```ts
/** Ce qui se tape pour corriger une ligne, selon la règle 3. */
export type ChampCorrigeable =
  | 'base'
  | 'taux'
  | 'montant'
  | 'taux_salarial'
  | 'taux_patronal'
  | 'montant_salarial'
  | 'montant_patronal';

export interface ChampDeLigne {
  cle: ChampCorrigeable;
  libelle: string;
  /** La valeur de Martine, dans l'unité tapée (un taux de cotisation en %). */
  valeur: number | null;
}

const TAUX_EN_POURCENT: ReadonlySet<ChampCorrigeable> = new Set<ChampCorrigeable>(['taux_salarial', 'taux_patronal']);

function pourcent(fraction: number | null | undefined): number | null {
  return typeof fraction === 'number' ? Math.round(fraction * 1e6) / 1e4 : null;
}

/** Les champs que la ligne laisse corriger. Rien pour une ligne qui ne se corrige pas ici. */
export function champsDeLaLigne(ligne: LigneCorrigeable): ChampDeLigne[] {
  if (!ligne.mode) return [];
  if (ligne.bloc === 'impot') {
    return [{ cle: 'taux', libelle: 'Taux d’impôt du mois (%)', valeur: ligne.taux ?? null }];
  }
  if (ligne.bloc === 'brut') {
    if (ligne.mode === 'base_ou_taux') {
      return [
        { cle: 'base', libelle: 'Base (heures, jours ou quantité)', valeur: ligne.base ?? null },
        { cle: 'taux', libelle: 'Taux', valeur: ligne.taux ?? null },
      ];
    }
    return [{ cle: 'montant', libelle: ligne.retenue ? 'Retenue (€)' : 'Montant (€)', valeur: ligne.montant ?? null }];
  }
  if (ligne.mode === 'base_ou_taux') {
    const champs: ChampDeLigne[] = [{ cle: 'base', libelle: 'Base (€)', valeur: ligne.base ?? null }];
    if (ligne.taux_salarial != null) {
      champs.push({ cle: 'taux_salarial', libelle: 'Taux salarial (%)', valeur: pourcent(ligne.taux_salarial) });
    }
    if (ligne.taux_patronal != null) {
      champs.push({ cle: 'taux_patronal', libelle: 'Taux patronal (%)', valeur: pourcent(ligne.taux_patronal) });
    }
    return champs;
  }
  return [
    { cle: 'montant_salarial', libelle: 'Part salariale (€)', valeur: ligne.montant_salarial ?? null },
    { cle: 'montant_patronal', libelle: 'Part patronale (€)', valeur: ligne.montant_patronal ?? null },
  ];
}

/** La correction à envoyer : un seul champ, un taux de cotisation repassé en fraction. */
export function correctionDeLigne(
  ligne: LigneCorrigeable,
  cle: ChampCorrigeable,
  saisie: number,
  motif: string
): CorrectionLigneAjoutee {
  const correction: CorrectionLigneAjoutee = { ligne: String(ligne.code), libelle: ligne.libelle, motif: motif.trim() };
  correction[cle] = TAUX_EN_POURCENT.has(cle) ? Math.round(saisie * 1e4) / 1e6 : saisie;
  return correction;
}

/** Le montant qu'aura la ligne, pour l'aperçu. Le serveur le recalcule. */
export function apercuDuMontant(ligne: LigneCorrigeable, cle: ChampCorrigeable, saisie: number): number | null {
  if (!Number.isFinite(saisie)) return null;
  if (ligne.bloc === 'impot') return ligne.base != null ? arrondi((ligne.base * saisie) / 100) : null;
  if (cle === 'montant' || cle === 'montant_salarial' || cle === 'montant_patronal') return arrondi(saisie);
  const base = cle === 'base' ? saisie : ligne.base ?? 0;
  if (ligne.bloc === 'brut') return arrondi(base * (cle === 'taux' ? saisie : ligne.taux ?? 0));
  const salarial = cle === 'taux_salarial' ? saisie / 100 : ligne.taux_salarial ?? 0;
  const patronal = cle === 'taux_patronal' ? saisie / 100 : ligne.taux_patronal ?? 0;
  return arrondi(arrondi(base * salarial) + arrondi(base * patronal));
}

/** « 1 234,50 € », avec des espaces ordinaires (les espaces insécables du navigateur varient). */
export function eurosFr(valeur: number): string {
  const [entier, decimales] = Math.abs(valeur).toFixed(2).split('.');
  return `${valeur < 0 ? '−' : ''}${entier.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')},${decimales} €`;
}

function tauxFr(valeur: number): string {
  return `${valeur.toFixed(2).replace('.', ',')} %`;
}

/** « Martine : 2 500,00 € → corrigé : 2 637,31 € ». */
export function resumeDeLaCorrection(ligne: LigneCorrigeable): string {
  const calcule = (ligne.valeur_calculee ?? {}) as Record<string, number | null | undefined>;
  if (ligne.bloc === 'impot') {
    return `Martine : ${tauxFr(calcule.taux ?? 0)} → corrigé : ${tauxFr(ligne.taux ?? 0)}`;
  }
  if (ligne.bloc === 'brut') {
    return `Martine : ${eurosFr(calcule.gain ?? calcule.perte ?? 0)} → corrigé : ${eurosFr(ligne.montant ?? 0)}`;
  }
  const avant = arrondi((calcule.montant_salarial ?? 0) + (calcule.montant_patronal ?? 0));
  const apres = arrondi((ligne.montant_salarial ?? 0) + (ligne.montant_patronal ?? 0));
  return `Martine : ${eurosFr(avant)} → corrigé : ${eurosFr(apres)}`;
}
```

Compléter ensuite chaque objet `EtatCorrections` écrit à la main ailleurs (tests compris) avec `correctionsAjoutees: [], correctionsRetirees: []` : les trouver par `grep -rn "regularisationsRetirees:" /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/frontend/src`.

- [ ] **Étape 5 : la carte**

Créer `frontend/src/components/payslip-edit/CorrigerUneLigneCard.tsx` :

```tsx
/**
 * Corriger une ligne du bulletin (théorème de la correction à la main, étape 2).
 *
 * Toute ligne calculée par Martine se corrige ici, par ce que la règle 3
 * permet : sa base ou son taux quand elle en porte (le montant suit au centime,
 * le serveur le recalcule), son montant sinon, le taux du mois pour l'impôt. La
 * correction est une variable du mois : à l'enregistrement, le bulletin est
 * recalculé en entier, et elle passe dans le net, les cumuls, la DSN et les
 * exports. Les codes et la règle viennent du serveur, jamais d'un calcul ici.
 */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PencilLine, Trash2, TriangleAlert, Undo2 } from 'lucide-react';

import { getLignesCorrigeables, type LigneCorrigeable } from '@/api/payslips';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  apercuDuMontant,
  champsDeLaLigne,
  correctionDeLigne,
  type ChampCorrigeable,
  type EtatCorrections,
  eurosFr,
  resumeDeLaCorrection,
} from '@/features/payroll/utils/correctionsBulletin';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { queryKeys } from '@/lib/queryKeys';

const BLOCS: Array<{ bloc: LigneCorrigeable['bloc']; titre: string }> = [
  { bloc: 'brut', titre: 'Rémunération' },
  { bloc: 'cotisations', titre: 'Cotisations' },
  { bloc: 'impot', titre: 'Impôt' },
];

interface Props {
  payslipId: string;
  /** `updated_at` du bulletin : la carte relit ses lignes après chaque enregistrement. */
  version: string | null;
  etat: EtatCorrections;
  onChange: (etat: EtatCorrections) => void;
  disabled?: boolean;
}

export default function CorrigerUneLigneCard({ payslipId, version, etat, onChange, disabled }: Props) {
  const companyId = useActiveCompanyId();
  const query = useQuery({
    queryKey: queryKeys.lignesCorrigeables(companyId, payslipId, version),
    queryFn: () => getLignesCorrigeables(payslipId, companyId),
    enabled: Boolean(companyId && payslipId),
    staleTime: 30_000,
  });
  const [code, setCode] = useState('');
  const [cle, setCle] = useState<ChampCorrigeable | ''>('');
  const [valeur, setValeur] = useState('');
  const [motif, setMotif] = useState('');
  const [reporterDe, setReporterDe] = useState<string | null>(null);

  const lignes = query.data?.lignes ?? [];
  const enAttente = query.data?.en_attente ?? [];
  const corrigees = lignes.filter((l) => l.correction?.saisie_id);
  const retirees = new Set(etat.correctionsRetirees);
  const ligne = lignes.find((l) => l.code === code && l.mode);
  const champs = ligne ? champsDeLaLigne(ligne) : [];
  const champ = champs.find((c) => c.cle === cle) ?? champs[0];
  const nombre = Number.parseFloat(valeur.replace(',', '.'));
  const apercu = ligne && champ ? apercuDuMontant(ligne, champ.cle, nombre) : null;
  const saisieDeLaLigne = ligne?.correction?.saisie_id ? String(ligne.correction.saisie_id) : null;
  const dejaCorrigee = saisieDeLaLigne !== null && !retirees.has(saisieDeLaLigne);
  const pret = !!ligne && !!champ && Number.isFinite(nombre) && motif.trim().length >= 3 && !dejaCorrigee;

  const basculer = (saisieId: string) =>
    onChange({
      ...etat,
      correctionsRetirees: retirees.has(saisieId)
        ? etat.correctionsRetirees.filter((id) => id !== saisieId)
        : [...etat.correctionsRetirees, saisieId],
    });

  const ajouter = () => {
    if (!pret || !ligne || !champ) return;
    const aRetirer = reporterDe && !retirees.has(reporterDe) ? [reporterDe] : [];
    onChange({
      ...etat,
      correctionsAjoutees: [...etat.correctionsAjoutees, correctionDeLigne(ligne, champ.cle, nombre, motif)],
      correctionsRetirees: [...etat.correctionsRetirees, ...aRetirer],
    });
    setValeur('');
    setMotif('');
    setReporterDe(null);
  };

  return (
    <Card data-testid="corriger-une-ligne">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <PencilLine className="h-5 w-5" />
          Corriger une ligne
        </CardTitle>
        <CardDescription>
          Une ligne fausse ? Choisissez-la, corrigez sa base ou son taux (son montant si elle n’en a pas) et écrivez le
          motif. Le montant suit au centime. À l’enregistrement, le bulletin est recalculé en entier : net, cumuls, DSN
          et exports suivent.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {query.isLoading ? <p className="text-sm text-muted-foreground">Lecture des lignes du bulletin…</p> : null}
        {query.isError ? (
          <p className="text-sm text-destructive">Les lignes du bulletin n’ont pas pu être lues. Rechargez la page.</p>
        ) : null}

        {enAttente.length > 0 ? (
          <Alert variant="destructive" data-testid="corrections-en-attente">
            <TriangleAlert className="h-4 w-4" />
            <AlertDescription className="space-y-2">
              <p>
                Ces corrections ne trouvent plus leur ligne. Le bulletin ne peut pas être validé tant qu’elles ne sont
                pas retirées ou reportées sur une autre ligne.
              </p>
              {enAttente.map((attente) => {
                const id = String(attente.saisie_id ?? '');
                return (
                  <div key={id || attente.ligne} className="flex flex-wrap items-center justify-between gap-2">
                    <span className={retirees.has(id) ? 'line-through' : ''}>
                      {attente.libelle} — {attente.motif} ({attente.raison})
                    </span>
                    {id && !disabled ? (
                      <span className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={() => basculer(id)}>
                          {retirees.has(id) ? 'Garder' : 'Retirer'}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setReporterDe(id);
                            setMotif(attente.motif);
                            setCode('');
                          }}
                        >
                          Reporter sur une autre ligne
                        </Button>
                      </span>
                    ) : null}
                  </div>
                );
              })}
            </AlertDescription>
          </Alert>
        ) : null}

        {corrigees.map((l) => {
          const id = String(l.correction?.saisie_id);
          return (
            <div key={id} className="flex items-center justify-between rounded-md border p-3 text-sm">
              <div className={retirees.has(id) ? 'line-through text-muted-foreground' : ''}>
                <div className="font-medium">{l.libelle}</div>
                <div className="text-xs text-muted-foreground">
                  {resumeDeLaCorrection(l)} — {l.correction?.motif}
                </div>
              </div>
              {disabled ? null : (
                <Button variant="ghost" size="sm" onClick={() => basculer(id)}>
                  {retirees.has(id) ? (
                    <>
                      <Undo2 className="h-4 w-4 mr-1" /> Garder
                    </>
                  ) : (
                    <>
                      <Trash2 className="h-4 w-4 mr-1" /> Retirer
                    </>
                  )}
                </Button>
              )}
            </div>
          );
        })}

        {etat.correctionsAjoutees.map((c, index) => (
          <div
            key={`correction-${index}`}
            className="flex items-center justify-between rounded-md border border-dashed p-3 text-sm"
          >
            <div>
              <div className="font-medium">{c.libelle} (à enregistrer)</div>
              <div className="text-xs text-muted-foreground">{c.motif}</div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              disabled={disabled}
              onClick={() =>
                onChange({ ...etat, correctionsAjoutees: etat.correctionsAjoutees.filter((_, i) => i !== index) })
              }
            >
              <Trash2 className="h-4 w-4 mr-1" /> Annuler
            </Button>
          </div>
        ))}

        {!disabled && lignes.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1 sm:col-span-2">
              <Label htmlFor="ligne-a-corriger">
                Ligne{reporterDe ? ' (report de la correction en attente)' : ''}
              </Label>
              <select
                id="ligne-a-corriger"
                className="w-full rounded-md border px-2 py-2 text-sm"
                value={code}
                onChange={(e) => {
                  setCode(e.target.value);
                  setCle('');
                  setValeur('');
                }}
              >
                <option value="">Choisissez une ligne…</option>
                {BLOCS.map(({ bloc, titre }) => (
                  <optgroup key={bloc} label={titre}>
                    {lignes
                      .filter((l) => l.bloc === bloc && l.code)
                      .map((l) => (
                        <option key={String(l.code)} value={String(l.code)} disabled={!l.mode} title={l.raison ?? undefined}>
                          {l.libelle}
                          {l.mode ? '' : ' — se corrige ailleurs'}
                        </option>
                      ))}
                  </optgroup>
                ))}
              </select>
              {dejaCorrigee ? (
                <p className="text-xs text-destructive">
                  Cette ligne est déjà corrigée : retirez sa correction ci-dessus pour la refaire.
                </p>
              ) : null}
            </div>
            {ligne && champ ? (
              <>
                <div className="space-y-1">
                  <Label htmlFor="champ-a-corriger">Ce que vous corrigez</Label>
                  <select
                    id="champ-a-corriger"
                    className="w-full rounded-md border px-2 py-2 text-sm"
                    value={champ.cle}
                    onChange={(e) => setCle(e.target.value as ChampCorrigeable)}
                  >
                    {champs.map((c) => (
                      <option key={c.cle} value={c.cle}>
                        {c.libelle}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="valeur-corrigee">
                    Valeur voulue{champ.valeur !== null ? ` (Martine : ${String(champ.valeur).replace('.', ',')})` : ''}
                  </Label>
                  <Input id="valeur-corrigee" inputMode="decimal" value={valeur} onChange={(e) => setValeur(e.target.value)} />
                </div>
                <div className="space-y-1 sm:col-span-2">
                  <Label htmlFor="motif-correction">Motif (obligatoire)</Label>
                  <Input id="motif-correction" maxLength={300} value={motif} onChange={(e) => setMotif(e.target.value)} />
                </div>
                <div className="flex items-center gap-3 sm:col-span-2">
                  <Button variant="outline" disabled={!pret} onClick={ajouter} data-testid="ajouter-correction-ligne">
                    Ajouter la correction
                  </Button>
                  {apercu !== null ? (
                    <span className="text-sm text-muted-foreground">Montant après correction : {eurosFr(apercu)}</span>
                  ) : null}
                </div>
              </>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Étape 6 : brancher la carte**

Dans `CorrectionsBulletinPanel.tsx` : importer `CorrigerUneLigneCard` ; ajouter aux `Props` `payslipId: string;` et `version?: string | null;` et à la déstructuration `payslipId, version = null,` ; juste après `<RegularisationsCotisationCard … />` :

```tsx
      <CorrigerUneLigneCard payslipId={payslipId} version={version} etat={etat} onChange={onChange} disabled={disabled} />
```

Mettre à jour la docstring du panneau : « … ses régularisations de cotisation et toute ligne calculée. » Dans `PayslipEdit.tsx`, passer au panneau `payslipId={payslip.id}` et `version={payslip.updated_at ?? null}`.

- [ ] **Étape 7 : lancer les tests et le contrôle des types**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/frontend && npx vitest run src/features/payroll/utils/corrigerUneLigne.test.ts src/features/payroll/utils/correctionsBulletin.test.ts && npx tsc --noEmit -p .
```

Attendu : tout passe, aucune erreur de type.

- [ ] **Étape 8 : commiter**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2 && git add frontend/src/api/payslips.ts frontend/src/lib/queryKeys.ts frontend/src/features/payroll/utils/correctionsBulletin.ts frontend/src/features/payroll/utils/corrigerUneLigne.test.ts frontend/src/components/payslip-edit/CorrigerUneLigneCard.tsx frontend/src/components/payslip-edit/CorrectionsBulletinPanel.tsx frontend/src/pages/rh/PayslipEdit.tsx && git add -u frontend/src && git commit -m "feat(paie): l'onglet Corriger corrige toute ligne par sa base, son taux ou son montant, et montre les corrections en attente

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 12 : la liste de contrôle et le capteur (et la liste qui perdait les régularisations)

**Fichiers :**
- Modifier : `backend/app/modules/payslips/infrastructure/payslip_list_meta.py`, `backend/app/modules/payslips/infrastructure/queries.py` (`get_employee_payslips`), `backend/app/modules/payslips/schemas/responses.py` (`LigneCorrigeeInfo`, `PayslipInfo`)
- Modifier : `frontend/src/features/payroll/utils/bulletinARecalculer.ts` (`LigneBulletinPaie`), `frontend/src/features/payroll/utils/listeControleMois.ts` (`etapeRegularisations`, `etapeValides`, libellé de l'étape)
- Tester : `backend/tests/unit/payslips/test_payslip_list_meta_corrections.py` (créé), `frontend/src/features/payroll/utils/listeControleMois.test.ts` (ajouts et une attente modifiée)

**Interfaces :**
- Consomme : `lignes_corrigees_du_bulletin`, `corrections_en_attente_du_bulletin` (tâche 8).
- Produit : chaque ligne de `/api/employees/{id}/payslips` porte `regularisations: string[]` (étape 1 ; la réponse le retirait jusqu'ici), `lignes_corrigees: {famille, libelle}[]` et `corrections_en_attente: number`. L'étape « Corrections à la main » (id `regularisations`, inchangé) compte régularisations et lignes corrigées et signale celles qui reviennent deux mois de suite ; l'étape « Bulletins validés » est à faire tant qu'un bulletin du mois a une correction en attente.

- [ ] **Étape 1 : écrire les tests qui échouent**

Créer `backend/tests/unit/payslips/test_payslip_list_meta_corrections.py` :

```python
"""La liste des bulletins dit les lignes corrigées et les corrections en attente,
et sa réponse garde ce que l'étape 1 y mettait déjà."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.codes_des_lignes import BLOC_BRUT
from app.modules.payroll.engine.corrections_manuelles import CorrectionDeLigne, JournalDesCorrections
from app.modules.payslips.infrastructure.payslip_list_meta import payslip_list_meta
from app.modules.payslips.schemas.responses import PayslipInfo

pytestmark = pytest.mark.unit


def _bulletin_corrige():
    ligne = {"libelle": "Salaire de base", "quantite": 151.67, "taux": 16.4832, "gain": 2500.0, "perte": None}
    correction = CorrectionDeLigne(ligne="brut:salaire_base", libelle="Salaire de base", motif="Avenant", base=160.0, saisie_id="c1")
    JournalDesCorrections([correction]).corriger(ligne, BLOC_BRUT, "brut:salaire_base")
    return {
        "calcul_du_brut": [ligne],
        "corrections_en_attente": [{"saisie_id": "c3", "ligne": "brut:precarite", "libelle": "Prime de précarité (CDD)",
                                    "motif": "CDD prolongé", "raison": "…"}],
    }


def test_la_liste_dit_les_lignes_corrigees_et_les_corrections_en_attente():
    meta = payslip_list_meta(_bulletin_corrige())
    assert meta["lignes_corrigees"] == [{"famille": "brut:salaire_base", "libelle": "Salaire de base"}]
    assert meta["corrections_en_attente"] == 1


def test_sans_correction_la_liste_n_en_dit_rien():
    for donnees in ({}, None):
        meta = payslip_list_meta(donnees)
        assert meta["lignes_corrigees"] == [] and meta["corrections_en_attente"] == 0


def test_la_reponse_de_liste_garde_regularisations_lignes_corrigees_et_attente():
    info = PayslipInfo(
        id="p", name="n", month=10, year=2026, url="u",
        regularisations=["Mutuelle"],
        lignes_corrigees=[{"famille": "brut:salaire_base", "libelle": "Salaire de base"}],
        corrections_en_attente=1,
    )
    sortie = info.model_dump()
    assert sortie["regularisations"] == ["Mutuelle"]
    assert sortie["lignes_corrigees"] == [{"famille": "brut:salaire_base", "libelle": "Salaire de base"}]
    assert sortie["corrections_en_attente"] == 1
```

Dans `frontend/src/features/payroll/utils/listeControleMois.test.ts`, dans le bloc `describe('régularisations à la main', …)`, remplacer l'attente `'Aucune régularisation saisie à la main ce mois.'` par `'Aucune correction à la main ce mois.'`, et ajouter :

```ts
  it('compte les lignes corrigées et signale une ligne corrigée deux mois de suite', () => {
    const e = entree({
      year: 2026,
      month: 10,
      bulletinsParSalarie: {
        statut: 'ok',
        valeur: {
          s1: [
            { year: 2026, month: 10, regularisations: [], lignes_corrigees: [{ famille: 'brut:salaire_base', libelle: 'Salaire de base' }] },
            { year: 2026, month: 9, lignes_corrigees: [{ famille: 'brut:salaire_base', libelle: 'Salaire de base' }] },
          ],
        },
      },
    });
    const etapeCorr = listeControleDuMois(e).etapes.find((x) => x.id === 'regularisations');
    expect(etapeCorr?.libelle).toBe('Corrections à la main');
    expect(etapeCorr?.detail).toBe(
      '1 ligne corrigée à la main ce mois. « Salaire de base » est corrigée deux mois de suite : signalez-le, Martine se trompe peut-être.'
    );
  });

  it('une correction en attente bloque l’étape de validation', () => {
    const resultat = listeControleDuMois(
      entree({
        bulletinsParSalarie: OK({
          'e-1': [{ year: 2026, month: 9, a_recalculer: false, origine: 'calcule', status: 'brouillon', corrections_en_attente: 1 }],
          'e-2': [{ year: 2026, month: 9, a_recalculer: false, origine: 'calcule', status: 'valide' }],
        }),
      })
    );
    const valides = etape(resultat, ETAPE_VALIDES);
    expect(valides.etat).toBe('a_faire');
    expect(valides.detail).toBe(
      '1 bulletin a une correction en attente : réglez-la dans l’onglet « Corriger » avant de valider.'
    );
  });
```

- [ ] **Étape 2 : lancer les tests pour les voir échouer**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payslips/test_payslip_list_meta_corrections.py -q
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/frontend && npx vitest run src/features/payroll/utils/listeControleMois.test.ts
```

Attendu : `KeyError: 'lignes_corrigees'` et `PayslipInfo` sans les champs côté serveur ; trois tests rouges côté écran.

- [ ] **Étape 3 : le serveur**

Dans `payslip_list_meta.py`, importer `corrections_en_attente_du_bulletin, lignes_corrigees_du_bulletin` depuis `app.modules.payroll.engine.corrections_du_bulletin` ; ajouter à `vide` : `"lignes_corrigees": [], "corrections_en_attente": 0,` ; et au retour :

```python
        "lignes_corrigees": lignes_corrigees_du_bulletin(payslip_data),
        "corrections_en_attente": len(corrections_en_attente_du_bulletin(payslip_data)),
```

Dans `queries.py`, `get_employee_payslips`, à côté de `"regularisations": meta.get("regularisations", []),` :

```python
                "lignes_corrigees": meta.get("lignes_corrigees", []),
                "corrections_en_attente": meta.get("corrections_en_attente", 0),
```

Dans `responses.py`, avant `PayslipInfo` :

```python
class LigneCorrigeeInfo(BaseModel):
    """Une famille de ligne corrigée à la main sur le bulletin (capteur du mois)."""

    famille: str
    libelle: str
```

et dans `PayslipInfo`, après `edited_by` :

```python
    #: Cotisations régularisées à la main (libellés). Sans ce champ déclaré, la
    #: réponse le retirait et la liste de contrôle ne le voyait jamais.
    regularisations: list[str] = []
    #: Lignes corrigées à la main, une par famille de code.
    lignes_corrigees: list[LigneCorrigeeInfo] = []
    #: Corrections qui ne trouvent plus leur ligne : le bulletin ne se valide pas.
    corrections_en_attente: int = 0
```

- [ ] **Étape 4 : l'écran**

Dans `bulletinARecalculer.ts`, ajouter à `LigneBulletinPaie` :

```ts
  /** Lignes corrigées à la main sur ce bulletin (famille du code et libellé). */
  lignes_corrigees?: Array<{ famille: string; libelle: string }> | null;
  /** Corrections qui ne trouvent plus leur ligne : le bulletin ne peut pas être validé. */
  corrections_en_attente?: number | null;
```

Dans `listeControleMois.ts`, remplacer le corps de `etapeRegularisations` par :

```ts
  return etatDepuisLecture(lecture, (parSalarie) => {
    const precedent = month === 1 ? { year: year - 1, month: 12 } : { year, month: month - 1 };
    let regularisations = 0;
    let lignes = 0;
    const regulRepetees = new Set<string>();
    const lignesRepetees = new Map<string, string>();
    for (const bulletins of Object.values(parSalarie)) {
      const duMois = bulletins.find((b) => b.year === year && b.month === month);
      const avant = bulletins.find((b) => b.year === precedent.year && b.month === precedent.month);
      const regulDuMois = duMois?.regularisations ?? [];
      const regulAvant = new Set(avant?.regularisations ?? []);
      regularisations += regulDuMois.length;
      regulDuMois.filter((libelle) => regulAvant.has(libelle)).forEach((libelle) => regulRepetees.add(libelle));
      const corrigees = duMois?.lignes_corrigees ?? [];
      const famillesAvant = new Set((avant?.lignes_corrigees ?? []).map((l) => l.famille));
      lignes += corrigees.length;
      corrigees.filter((l) => famillesAvant.has(l.famille)).forEach((l) => lignesRepetees.set(l.famille, l.libelle));
    }
    if (regularisations === 0 && lignes === 0) return { etat: 'fait', detail: 'Aucune correction à la main ce mois.' };
    const phrases: string[] = [];
    if (regularisations > 0) {
      const s = regularisations > 1 ? 's' : '';
      phrases.push(`${regularisations} régularisation${s} saisie${s} à la main ce mois.`);
    }
    if (lignes > 0) {
      const s = lignes > 1 ? 's' : '';
      phrases.push(`${lignes} ligne${s} corrigée${s} à la main ce mois.`);
    }
    for (const libelle of [...regulRepetees].sort()) {
      phrases.push(`« ${libelle} » est régularisée deux mois de suite : signalez-le, Martine se trompe peut-être.`);
    }
    for (const libelle of [...lignesRepetees.values()].sort()) {
      phrases.push(`« ${libelle} » est corrigée deux mois de suite : signalez-le, Martine se trompe peut-être.`);
    }
    return { etat: 'fait', detail: phrases.join(' ') };
  });
```

Changer le libellé de l'étape : `libelle: 'Corrections à la main',`. Dans `etapeValides`, compter les corrections en attente et les faire passer avant tout :

```ts
    let aValider = 0;
    let enAttente = 0;
    for (const salarie of salaries) {
      if (payrollEmploymentBlockReason(salarie, year, month)) continue;
      const ligne = (parSalarie[salarie.id] ?? []).find((p) => p.year === year && p.month === month);
      if ((ligne?.corrections_en_attente ?? 0) > 0) enAttente += 1;
      // Un bulletin repris de l'ancien logiciel a été payé : rien à valider.
      if (ligne && (ligne.status === 'valide' || estBulletinImporte(ligne))) continue;
      aValider += 1;
    }
    if (enAttente > 0) {
      return {
        etat: 'a_faire',
        detail: pluriel(
          enAttente,
          '1 bulletin a une correction en attente : réglez-la dans l’onglet « Corriger » avant de valider.',
          `${enAttente} bulletins ont une correction en attente : réglez-les dans l’onglet « Corriger » avant de valider.`
        ),
      };
    }
```

(le reste de `etapeValides` est inchangé).

- [ ] **Étape 5 : relancer les tests**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit/payslips/test_payslip_list_meta_corrections.py tests/unit/payslips/test_payslip_list_meta_regularisations.py -q
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/frontend && npx vitest run src/features/payroll/utils/listeControleMois.test.ts && npx tsc --noEmit -p .
```

Attendu : tout passe.

- [ ] **Étape 6 : commiter**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2 && git add backend/app/modules/payslips/infrastructure/payslip_list_meta.py backend/app/modules/payslips/infrastructure/queries.py backend/app/modules/payslips/schemas/responses.py backend/tests/unit/payslips/test_payslip_list_meta_corrections.py frontend/src/features/payroll/utils/bulletinARecalculer.ts frontend/src/features/payroll/utils/listeControleMois.ts frontend/src/features/payroll/utils/listeControleMois.test.ts && git commit -m "feat(paie): la liste de contrôle compte les lignes corrigées, signale celles qui reviennent et bloque la validation d'une correction en attente

La réponse de liste retirait les régularisations de l'étape 1 : elle les déclare désormais.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 13 : le test du théorème étendu à la correction directe

**Fichiers :**
- Modifier : `backend/scripts/theoreme_correction_a_la_main.py` (docstring, imports, `_noter`, fonctions ajoutées, `main`)

**Interfaces :**
- Consomme : `lignes_corrigeables`, `LigneCorrigeable` (tâche 8) ; `CorrectionDeLigne` (tâche 2) ; `codes_des_lignes` (tâche 1) ; `raisons_de_ne_pas_valider`, `MESSAGE_CORRECTION_EN_ATTENTE` (tâche 8) ; `_pas_details` (`dsn_export/application/builder.py`) ; les fonctions de l'étape 1 du script (`_cumuls_precedents`, `_lignes`, `_montants_dsn`, `_dsn_a_bouge`, `_residu`, `_generer`, `_un_salarie`).
- Produit : `PYTHONPATH=. python scripts/theoreme_correction_a_la_main.py "<Société>" <année> <mois> <sortie.json> [tout|regularisations|directes]`. Pour chaque bulletin : chaque ligne a un code ; une correction par famille de ligne vérifie les garanties 2 à 7 et 10 (la ligne porte la valeur voulue et garde celle de Martine ; brut = somme des lignes ; copies des cotisations d'accord ; résidu comptable nul ; cumuls du mois = cumuls d'avant + ce mois, heures comprises ; réduction générale ; DSN de la cotisation ou de l'impôt) ; le mois suivant part des cumuls corrigés ; une correction orpheline reste en attente et bloque la validation.

- [ ] **Étape 1 : écrire l'extension**

Dans la docstring du script, ajouter le paragraphe :

```python
"""…
Étape 2 (correction directe) : chaque ligne du bulletin doit avoir un code ;
pour chaque famille de ligne, une correction permise par la règle 3 (base + 1
ou + 10, montant + 10 ou ± 1, taux d'impôt + 1 point) est injectée en mémoire,
et l'on vérifie la ligne, les totaux, les copies, le net, les cumuls, la DSN et
le mois suivant. Puis une correction sans ligne : elle reste en attente et
bloque la validation. Le dernier argument choisit la partie : tout (défaut),
regularisations, directes.
"""
```

Ajouter aux imports (après ceux de l'étape 1, avec `# noqa: E402`) :

```python
from app.modules.dsn_export.application.builder import _pas_details  # noqa: E402
from app.modules.payroll.engine.codes_des_lignes import (  # noqa: E402
    BLOC_BRUT,
    BLOC_COTISATIONS,
    BLOC_IMPOT,
    MODE_BASE_OU_TAUX,
    MODE_TAUX,
    code_de_ligne,
    famille_du_code,
    numeroter,
)
from app.modules.payroll.engine.corrections_du_bulletin import (  # noqa: E402
    BLOCS_DE_GAINS,
    LigneCorrigeable,
    lignes_corrigeables,
)
from app.modules.payroll.engine.corrections_manuelles import CorrectionDeLigne  # noqa: E402
from app.modules.payslips.domain.coherence import (  # noqa: E402
    MESSAGE_CORRECTION_EN_ATTENTE,
    raisons_de_ne_pas_valider,
)
```

Remplacer la ligne `print(...)` de `_noter` par :

```python
    nom = constats.get("coti_id") or constats.get("code") or constats.get("cas")
    print(("OK  " if ok else "ECHEC"), employee_id[:8], nom, constats if not ok else "", flush=True)
```

Ajouter, avant `main` :

```python
#: Les cumuls d'heures qu'une base corrigée d'une heure doit faire monter d'une heure (spec § 6).
HEURES_SUIVIES = {
    "brut:heures_sup": ("heures_supplementaires_remunerees", "heures_remunerees"),
    "brut:salaire_base": ("heures_remunerees",),
}


def _ecart(avant: object, apres: object) -> float:
    return round(float(apres or 0.0) - float(avant or 0.0), 2)


def _cumul(resultat: dict, cle: str) -> float:
    return float(((resultat.get("cumuls") or {}).get("cumuls") or {}).get(cle) or 0.0)


def _synthese(data: dict, cle: str) -> float:
    return float((data.get("synthese_net") or {}).get(cle) or 0.0)


def _impot(data: dict) -> dict:
    return (data.get("synthese_net") or {}).get("impot_prelevement_a_la_source") or {}


def _somme_du_brut(data: dict) -> float:
    total = 0.0
    for bloc in BLOCS_DE_GAINS:
        for ligne in data.get(bloc) or []:
            if isinstance(ligne, dict) and not ligne.get("is_sous_total") and not ligne.get("is_informative"):
                total += float(ligne.get("gain") or 0.0) - float(ligne.get("perte") or 0.0)
    return round(total, 2)


def _totaux(data: dict) -> dict[str, float]:
    structure = data.get("structure_cotisations") or {}
    officielles = [r for r in data.get("cotisations_officielles") or [] if isinstance(r, dict)]
    lignes = _lignes(data)
    return {
        "brut": float(data.get("salaire_brut") or 0.0),
        "somme_du_brut": _somme_du_brut(data),
        "salarial": float(structure.get("total_salarial") or 0.0),
        "patronal": float(structure.get("total_patronal") or 0.0),
        "salarial_officiel": round(sum(float(r.get("total_salarial") or 0.0) for r in officielles), 2),
        "patronal_officiel": round(sum(float(r.get("total_patronal") or 0.0) for r in officielles), 2),
        "lignes_salariales": round(sum(float(l.get("montant_salarial") or 0.0) for l in lignes), 2),
        "lignes_patronales": round(sum(float(l.get("montant_patronal") or 0.0) for l in lignes), 2),
    }


def _lignes_par_code(data: dict) -> dict[str, dict]:
    lignes = _lignes(data)
    return {code: ligne for code, ligne in zip(numeroter(code_de_ligne(BLOC_COTISATIONS, l) for l in lignes), lignes) if code}


def _correction_pour(ligne: LigneCorrigeable) -> CorrectionDeLigne:
    """Une correction permise par la règle 3, assez petite pour ne rien faire basculer."""
    commun = dict(ligne=ligne.code, libelle=ligne.libelle, motif="Test du théorème")
    if ligne.mode == MODE_TAUX:
        return CorrectionDeLigne(**commun, taux=round(float(ligne.taux or 0.0) + 1.0, 2))
    if ligne.bloc == BLOC_BRUT:
        if ligne.mode == MODE_BASE_OU_TAUX:
            return CorrectionDeLigne(**commun, base=round(float(ligne.base or 0.0) + 1.0, 2))
        return CorrectionDeLigne(**commun, montant=round(float(ligne.montant or 0.0) + 10.0, 2))
    if ligne.mode == MODE_BASE_OU_TAUX:
        return CorrectionDeLigne(**commun, base=round(float(ligne.base or 0.0) + 10.0, 2))
    if famille_du_code(ligne.code) == "cotisation:reduction_generale":
        # Un euro de réduction en plus : la réduction de l'année ne peut pas devenir négative.
        return CorrectionDeLigne(**commun, montant_patronal=round(float(ligne.montant_patronal or 0.0) - 1.0, 2))
    if ligne.montant_patronal:
        return CorrectionDeLigne(**commun, montant_patronal=round(float(ligne.montant_patronal) + 1.0, 2))
    return CorrectionDeLigne(**commun, montant_salarial=round(float(ligne.montant_salarial or 0.0) + 1.0, 2))


def _attendu(ligne: LigneCorrigeable, correction: CorrectionDeLigne) -> dict[str, float]:
    """Ce que la ligne doit porter après la correction, au centime comme le moteur."""
    if ligne.bloc == BLOC_IMPOT:
        taux = float(correction.taux)
        return {"taux": taux, "montant": round(float(ligne.base or 0.0) * (taux / 100.0), 2)}
    if ligne.bloc == BLOC_BRUT:
        if correction.montant is not None:
            return {"montant": round(correction.montant, 2)}
        return {"base": float(correction.base), "montant": round(float(correction.base) * float(ligne.taux or 0.0), 2)}
    if correction.par_montant:
        return {
            cle: round(float(getattr(correction, cle)), 2)
            for cle in ("montant_salarial", "montant_patronal")
            if getattr(correction, cle) is not None
        }
    base = float(correction.base)
    attendu = {"base": base}
    if ligne.taux_salarial is not None:
        attendu["montant_salarial"] = round(base * ligne.taux_salarial, 2)
    if ligne.taux_patronal is not None:
        attendu["montant_patronal"] = round(base * ligne.taux_patronal, 2)
    return attendu


def _porte(ligne: LigneCorrigeable | None, attendu: dict[str, float]) -> bool:
    return (
        ligne is not None
        and ligne.correction is not None
        and all(abs(float(getattr(ligne, cle) or 0.0) - valeur) < 0.005 for cle, valeur in attendu.items())
    )


def _garde_la_valeur_de_martine(avant: LigneCorrigeable, apres: LigneCorrigeable | None) -> bool:
    if apres is None or not apres.valeur_calculee:
        return False
    calcule = apres.valeur_calculee
    if avant.bloc == BLOC_IMPOT:
        return abs(float(calcule.get("taux") or 0.0) - float(avant.taux or 0.0)) < 1e-6
    if avant.bloc == BLOC_BRUT:
        montant = calcule.get("gain") if calcule.get("gain") is not None else calcule.get("perte")
        return abs(float(montant or 0.0) - float(avant.montant or 0.0)) < 0.005
    return all(
        abs(float(calcule.get(cle) or 0.0) - float(getattr(avant, cle) or 0.0)) < 0.005
        for cle in ("montant_salarial", "montant_patronal")
    )


def _cumuls_suivent(base: dict, res: dict, ligne: LigneCorrigeable, apres: LigneCorrigeable | None) -> dict[str, bool]:
    data0, data1 = base["payslip_data"], res["payslip_data"]

    def mouvement(cle: str) -> float:
        return _ecart(_cumul(base, cle), _cumul(res, cle))

    constats = {
        "cumul_brut": abs(mouvement("brut_total") - _ecart(data0.get("salaire_brut"), data1.get("salaire_brut"))) < 0.011,
        "cumul_net_imposable": abs(
            mouvement("net_imposable") - _ecart(_synthese(data0, "net_imposable"), _synthese(data1, "net_imposable"))
        ) < 0.011,
        "cumul_impot": abs(
            mouvement("impot_preleve_a_la_source") - _ecart(_impot(data0).get("montant"), _impot(data1).get("montant"))
        ) < 0.011,
    }
    famille = famille_du_code(ligne.code)
    if famille == "cotisation:reduction_generale" and apres is not None:
        constats["cumul_reduction"] = abs(
            mouvement("reduction_generale_patronale") - _ecart(ligne.montant_patronal, apres.montant_patronal)
        ) < 0.011
    if ligne.mode == MODE_BASE_OU_TAUX and famille in HEURES_SUIVIES and "forfait" not in ligne.libelle.lower():
        for cle in HEURES_SUIVIES[famille]:
            constats[f"cumul_{cle}"] = abs(mouvement(cle) - 1.0) < 0.011
    return constats


def _le_mois_suivant_part_des_cumuls(employee_id: str, year: int, month: int, res: dict) -> bool | None:
    """Le mois suivant, recalculé sur les cumuls corrigés, en repart. None s'il n'est pas calculable."""
    annee, mois = (year, month + 1) if month < 12 else (year + 1, 1)
    try:
        suivant = _generer(employee_id, annee, mois, res.get("cumuls"))
    except HTTPException as exc:
        if exc.status_code in (400, 422):
            return None
        raise
    brut = float(suivant["payslip_data"].get("salaire_brut") or 0.0)
    return abs((_cumul(suivant, "brut_total") - brut) - _cumul(res, "brut_total")) < 0.011


def _corrections_directes(company_id: str, employee_id: str, year: int, month: int, rapport: list[dict]) -> None:
    """Étape 2 : chaque famille de ligne du bulletin, corrigée directement."""
    employee = supabase.table("employees").select("*").eq("id", employee_id).single().execute().data
    cumuls = _cumuls_precedents(employee_id, year, month)
    try:
        base = _generer(employee_id, year, month, cumuls)
    except HTTPException as exc:
        if exc.status_code not in (400, 422):
            raise
        rapport.append({"salarie": employee_id, "ok": True, "cas": "bulletin de départ refusé", "saute": True})
        return
    data0 = base["payslip_data"]
    lignes0 = lignes_corrigeables(data0)
    for ligne in lignes0:
        if ligne.code is None:
            _noter(rapport, employee_id, False, cas="type de ligne non couvert", libelle=ligne.libelle)
    periode = {"employee_id": employee_id, "company_id": company_id, "year": year, "month": month}
    dsn0, residu0, totaux0, cotisations0 = _montants_dsn(data0), _residu(data0, employee), _totaux(data0), _lignes_par_code(data0)
    familles: set[str] = set()
    mois_suivant_verifie = False
    for ligne in lignes0:
        if not ligne.code or not ligne.mode or famille_du_code(ligne.code) in familles:
            continue
        familles.add(famille_du_code(ligne.code))
        correction = _correction_pour(ligne)
        saisie = {**correction.saisie_du_mois(periode), "id": "theoreme-ligne"}
        try:
            res = _generer(employee_id, year, month, cumuls, (saisie,))
        except HTTPException as exc:
            _noter(rapport, employee_id, False, code=ligne.code, refus=str(exc.detail)[:300])
            continue
        data1 = res["payslip_data"]
        apres = {l.code: l for l in lignes_corrigeables(data1)}.get(ligne.code)
        attendu = _attendu(ligne, correction)
        totaux1 = _totaux(data1)
        constats = {
            "valeur_posee": _porte(apres, attendu),
            "valeur_de_martine": _garde_la_valeur_de_martine(ligne, apres),
            "brut_somme_des_lignes": abs(
                _ecart(totaux0["brut"], totaux1["brut"]) - _ecart(totaux0["somme_du_brut"], totaux1["somme_du_brut"])
            ) < 0.011,
            "copies": all(
                abs(_ecart(totaux0[a], totaux1[a]) - _ecart(totaux0[b], totaux1[b])) < 0.011
                for a, b in (
                    ("salarial", "salarial_officiel"),
                    ("salarial", "lignes_salariales"),
                    ("patronal", "patronal_officiel"),
                    ("patronal", "lignes_patronales"),
                )
            ),
            "residu": abs(_residu(data1, employee) - residu0) < 0.005,
            "rien_en_attente": not data1.get("corrections_en_attente"),
            **_cumuls_suivent(base, res, ligne, apres),
        }
        if ligne.bloc == BLOC_COTISATIONS and ligne.code in cotisations0 and apres is not None:
            constats["dsn"] = _dsn_a_bouge(
                dsn0,
                _montants_dsn(data1),
                cotisations0[ligne.code],
                _ecart(ligne.montant_salarial, apres.montant_salarial),
                _ecart(ligne.montant_patronal, apres.montant_patronal),
            )
        if ligne.bloc == BLOC_IMPOT:
            montant, taux, _assiette = _pas_details(data1)
            constats["dsn_impot"] = abs(montant - attendu["montant"]) < 0.005 and abs(taux - attendu["taux"]) < 1e-6
        if ligne.bloc == BLOC_BRUT and not mois_suivant_verifie:
            mois_suivant_verifie = True
            suivant = _le_mois_suivant_part_des_cumuls(employee_id, year, month, res)
            if suivant is not None:
                constats["mois_suivant"] = suivant
        _noter(rapport, employee_id, all(constats.values()), code=ligne.code, **constats)
    orpheline = CorrectionDeLigne(
        ligne="brut:ligne_disparue", libelle="Ligne disparue", motif="Test du théorème", montant=1.0
    )
    res = _generer(employee_id, year, month, cumuls, ({**orpheline.saisie_du_mois(periode), "id": "theoreme-orpheline"},))
    data1 = res["payslip_data"]
    constats = {
        "en_attente": [e.get("saisie_id") for e in data1.get("corrections_en_attente") or []] == ["theoreme-orpheline"],
        "validation_bloquee": MESSAGE_CORRECTION_EN_ATTENTE in raisons_de_ne_pas_valider(data1),
        "brut_inchange": abs(_ecart(data0.get("salaire_brut"), data1.get("salaire_brut"))) < 0.005,
    }
    _noter(rapport, employee_id, all(constats.values()), cas="correction orpheline", **constats)
```

Remplacer `main` par :

```python
def main(societe: str, year: int, month: int, sortie: str, partie: str = "tout") -> int:
    if partie not in ("tout", "regularisations", "directes"):
        raise SystemExit("partie : tout, regularisations ou directes")
    company = supabase.table("companies").select("id").eq("company_name", societe).single().execute().data
    bulletins = (
        supabase.table("payslips")
        .select("employee_id")
        .match({"company_id": company["id"], "year": year, "month": month})
        .execute()
        .data
    )
    rapport: list[dict] = []
    for bulletin in bulletins:
        employee_id = bulletin["employee_id"]
        print(f"salarie {employee_id[:8]}", flush=True)
        with lecture_seule():
            if partie in ("tout", "regularisations"):
                _un_salarie(company["id"], employee_id, year, month, rapport)
            if partie in ("tout", "directes"):
                _corrections_directes(company["id"], employee_id, year, month, rapport)
    echecs = sum(1 for cas in rapport if not cas["ok"])
    with open(sortie, "w", encoding="utf-8") as fichier:
        json.dump(rapport, fichier, ensure_ascii=False, indent=1)
    print(f"{len(rapport)} cas, {echecs} échec(s)", flush=True)
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], *(sys.argv[5:6])))
```

- [ ] **Étape 2 : vérifier que le script se charge**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && PYTHONPATH=. /Users/alex/dev/EYWAI/backend/.venv/bin/python -c "import ast,sys; ast.parse(open('scripts/theoreme_correction_a_la_main.py').read()); print('syntaxe ok')"
```

Attendu : `syntaxe ok`.

- [ ] **Étape 3 : faire tourner le test du théorème sur les quatre sociétés (en arrière-plan, sous `caffeinate -i`, plusieurs heures)**

À lancer avec `run_in_background` : chaque bulletin demande une génération par famille de ligne.

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && for s in "Colorplast" "Comitech Composite" "MAJI" "Zone 404 Mars"; do PYTHONPATH=. caffeinate -i /Users/alex/dev/EYWAI/backend/.venv/bin/python scripts/theoreme_correction_a_la_main.py "$s" 2026 9 "/Users/alex/dev/eywai-filet/theoreme2-${s// /_}.json" tout > "/Users/alex/dev/eywai-filet/theoreme2-${s// /_}.log" 2>&1; done; echo fini > /Users/alex/dev/eywai-filet/theoreme2-fini.txt
```

Attendu : pour chaque société, la dernière ligne du journal dit `N cas, 0 échec(s)`, et aucune `EcritureInterdite`. Zone 404 Mars porte des salariés au forfait jours (garantie 10). Pour chaque échec : ouvrir le cas dans le JSON, trouver la cause, la reproduire par un test unitaire dans la tâche qu'elle concerne, la corriger, relancer la société. Un « type de ligne non couvert » s'ajoute à l'inventaire (tâche 1, motif et test). Ne jamais assouplir un contrôle pour le faire passer.

- [ ] **Étape 4 : commiter le script (les rapports restent hors du dépôt)**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2 && git add backend/scripts/theoreme_correction_a_la_main.py && git commit -m "test(paie): le test du théorème corrige chaque famille de ligne au bac à sable et vérifie ligne, totaux, net, cumuls, DSN, mois suivant et corrections orphelines

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 14 : filet avant/après au centime, suite complète, compte rendu (sans déploiement)

**Fichiers :** aucun dans le dépôt. Les relevés vont dans `/Users/alex/dev/eywai-filet/` (hors dépôt, survit à la session).

- [ ] **Étape 1 : filet « avant » sur la base de l'étape 2 (environ 20 min, en arrière-plan)**

```bash
caffeinate -i /Users/alex/dev/eywai-filet/lancer.sh /Users/alex/dev/eywai-filet/theoreme2-avant 338215e6
```

Le dossier se passe en **chemin absolu**. `lancer.sh` lit le commit dans `/Users/alex/dev/EYWAI` : passer toujours un commit ou une branche explicite, jamais `HEAD` (le `HEAD` du dépôt principal n'est pas cette branche). Attendu : `/Users/alex/dev/eywai-filet/theoreme2-avant/fini.txt` existe, les quatre `apres_*.json` sont non vides.

- [ ] **Étape 2 : filet « après » sur la branche, aussitôt après (environ 20 min, en arrière-plan)**

Tous les commits des tâches 1 à 13 doivent être faits.

```bash
caffeinate -i /Users/alex/dev/eywai-filet/lancer.sh /Users/alex/dev/eywai-filet/theoreme2-apres feat/theoreme-etape-2
```

Les deux relevés se font l'un après l'autre, sans attendre entre eux : la base de test porte la vraie paie, et des données qui bougent entre les deux feraient des écarts qui ne viennent pas du code.

- [ ] **Étape 3 : comparer au centime**

```bash
cd /Users/alex/dev/eywai-filet && /Users/alex/dev/EYWAI/backend/.venv/bin/python comparer5.py "/Users/alex/dev/eywai-filet/theoreme2-avant/apres_*.json" "/Users/alex/dev/eywai-filet/theoreme2-apres/apres_*.json"
```

Attendu : `Bulletins avec écart : 0`, `Cumuls avec écart : 0`, et les mêmes erreurs connues des deux côtés. Aucun bulletin réel n'a encore de correction de ligne (l'étape 2 n'est pas déployée) : tout écart est une régression, clé nouvelle comprise. Il bloque la suite : l'expliquer, le corriger, refaire l'étape 2 puis l'étape 3.

- [ ] **Étape 4 : suite complète, une seule fois**

```bash
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest tests/unit -q
cd /Users/alex/dev/EYWAI/.claude/worktrees/theoreme-etape-2/frontend && npx vitest run && npx tsc --noEmit -p .
```

Attendu : tout passe.

- [ ] **Étape 5 : compte rendu à Alexandre, sans rien pousser ni déployer**

Lui donner : le résultat du filet (bulletins comparés par société et par mois, 0 écart), le test du théorème (cas et échecs par société, familles de lignes couvertes, cas « mois suivant non calculable »), les décisions de ce plan, et le geste à faire après déploiement : les vidéos A.1 s9-s10, C.13 et J.1 disent « une cotisation se régularise depuis le bulletin, le reste à la source », à mettre à jour puisque toute ligne se corrige. Lui demander son accord pour pousser la branche (CI) et la déployer sur le site de test (`gh workflow run deploy-test-env.yml --ref feat/theoreme-etape-2`). Aucune migration n'est à appliquer. Après déploiement, sur son accord : rejouer le parcours sur un salarié de MAJI créé pour l'occasion puis supprimé (corriger une ligne de gain, une cotisation et le taux d'impôt ; enregistrer ; vérifier la ligne, la note du PDF, le net et la liste de contrôle ; supprimer une absence pour rendre une correction orpheline et vérifier que la validation est refusée ; retirer les corrections).

---

## Couverture de la spécification

| Exigence (spec) | Tâche |
|---|---|
| Code stable sur chaque ligne, discriminants des `coti_id` non uniques, participation, PPV, IJSS (§ 10) | 1 |
| Correction par base, taux ou montant selon la règle 3, arrondi du moteur, quantités liées (§ 3) | 1, 2, 3, 4, 5 |
| Correction aux points du § 5 : gain à sa naissance, lignes d'après le brut, cotisation dans son calcul, réduction générale, impôt | 3, 4, 5, 6, 7 |
| Les deux pipelines aux mêmes étapes, test de contrat (§ 5) | 7 |
| Taux d'impôt du mois | 6 |
| Cumuls : réduction appliquée, impôt prélevé, heures (§ 6) | 3, 6, 13 |
| `valeur_calculee`, mention à l'écran et sur le PDF ; info-bulle de la réduction (règle 6, § 7) | 2, 8 |
| Correction orpheline « en attente » qui bloque la validation (règle 7) | 2, 7, 8, 11, 12 |
| DSN au centime ; écriture comptable équilibrée (§ 7) | 9, 13 |
| Empreinte « À recalculer » sans périmer les bulletins existants (§ 4, § 7) | 1 (code non stocké), 8 |
| Historique et restauration d'une version (règle 6) | 10 |
| Carte « Corriger une ligne » (§ 8) | 10, 11 |
| Liste de contrôle et capteur (règle 8, § 8) | 12 |
| Test du théorème étendu (§ 9) | 13 |
| Garantie 1 : filet au centime | 14 |
| Bornes de la règle 9 (mois repris verrouillé, validé repassé en brouillon) | inchangées : `corriger_bulletin` les applique déjà |

---

## Écarts à l'exécution

Notés par l'agent qui a exécuté les tâches 0 à 10 (23/10).

- **Tâche 0.** Le contrôle des noms du crochet `pre-commit` ne voit pas la table des pseudonymes dans le worktree (`data/_outils/` est hors git) : il passe sans rien vérifier. Avant chaque commit, il a été rejoué sur le diff indexé du worktree avec la table du dépôt principal (lecture seule). Le contrôle `ruff` du crochet est aussi sauté (pas de `backend/.venv` dans le worktree) : rejoué à la main avec l'interpréteur du dépôt principal (`--select E9,F63,F7,F82`).
- **Tâche 3.** `test_la_precarite_et_l_indemnite_compensatrice_suivent_le_salaire_corrige` passe aussi avant l'implémentation (la correction n'étant pas posée, la précarité vaut le dixième du brut non corrigé, ce que le test vérifie). Il ne devient discriminant qu'une fois la correction posée ; laissé tel quel.
- **Tâche 8.** L'import en tête de `explications_lignes.py` (`codes_des_lignes`, `corrections_du_bulletin`) créait un cycle quand ce module est chargé le premier (`engine/__init__` → `bulletin` → `explications_lignes` à moitié chargé). Les tests ne le voyaient pas (autre ordre d'import). Corrigé par un import local dans `_expliquer_corrections` ; chaque module touché a été vérifié importable seul, et `app.main` aussi.
