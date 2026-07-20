---
name: backtest-paie
description: >-
  Backtest paie EYWAI contre bulletins réels : comparaison ligne par ligne entre
  bulletin généré (Ayway/EYWAI) et bulletin réel, diagnostic des écarts, corrections
  moteur/paramètres/données. Mode entreprise par entreprise, employé par employé.
  À utiliser lorsque l'utilisateur tape /backtest-paie, lance une recette paie sur
  un mois (ex. mai), ou envoie un bulletin simulé + bulletin réel à rapprocher.
---

# Backtest paie (`/backtest-paie`)

## Contexte

On va tester la paie sur le mois de mai. On va procéder entreprise par entreprise, employé par employé, en mode backtest.

Je vais t'envoyer le bulletin généré par Ayway et le contenu du bulletin réel. Et tu vas faire les améliorations et les changements nécessaires pour détecter les problèmes et proposer des choses pour que notre bulletin colle avec le bulletin réel.

**Référence produit** : EYWAI = logiciel ; « Ayway » = bulletin généré par notre moteur. Le bulletin **réel** (Silae, ancien logiciel, PDF client) est la **cible de vérité terrain** pour ce backtest — pas une règle légale abstraite.

## Quand utiliser ce skill

- L'utilisateur tape **`/backtest-paie`** ou attache ce skill.
- Il démarre une session de recette paie sur **mai** (ou un autre mois explicite).
- Il envoie **deux bulletins** (EYWAI + réel) pour un salarié donné.

## Rôle de l'agent

| Phase | Action |
|-------|--------|
| **1 — Cadrer** | Confirmer entreprise, employé, mois ; lister ce qui manque |
| **2 — Comparer** | Écarts ligne par ligne (montants, libellés, bases, cumuls) |
| **3 — Diagnostiquer** | Cause racine : moteur, paramètre, donnée, affichage, cumul N-1 |
| **4 — Corriger** | Implémenter le plus petit diff pertinent ; re-vérifier |
| **5 — Avancer** | Marquer le salarié OK / écart restant ; proposer le suivant |

**Priorité** : faire coller le bulletin EYWAI au bulletin réel. Ne pas contredire le réel sans preuve forte (erreur évidente de saisie côté client, doublon, mauvais mois).

## Principes

- **Ordre de passage** : une **entreprise** à la fois, un **employé** à la fois — ne pas mélanger les contextes.
- **Produit généraliste** : pas de hardcode filiale ; paramètres (`company_*`, CCN, `leave_settings`, etc.) — voir `.cursor/rules/product-context.mdc`.
- **Tolérance** : écart ≤ 0,01 € = OK ; au-delà, investiguer.
- **Régressions** : signaler si la correction risque d'impacter d'autres filiales ou contrats (forfait jours vs heures, CCN, stage, CDD…).
- **Données runtime** : cumuls et saisies sous `backend/app/runtime/payroll/data/employes/<NOM>/`.

---

## Phase 1 — Cadrer (chaque salarié)

Demander ou inférer :

| Élément | Exemple |
|---------|---------|
| Entreprise / filiale | CARTOL, LEWIS… |
| Employé | Nom, matricule si dispo |
| Période | Mai 2026 (défaut si non précisé) |
| Type contrat | CDI heures, forfait jours, CDD, alternance… |
| CCN | Si connue |

Si des éléments manquent : **une salve** de questions courtes (max 3–5), puis continuer avec hypothèses explicites.

Produire le cadrage :

```markdown
## Backtest — [Entreprise] / [Employé] / [Mois AAAA]

- Contrat : [type]
- CCN : [IDCC ou inconnu]
- Bulletin EYWAI : [collé / fichier / capture]
- Bulletin réel : [collé / fichier / capture]
```

---

## Phase 2 — Comparer (obligatoire)

Comparer **dans cet ordre** (du haut vers le bas du bulletin) :

1. **Heures / jours** — base, HS, absences, RTT
2. **Éléments de brut** — salaire base, primes, avantages, retenues
3. **Brut total**
4. **Cotisations** — ligne par ligne (base, taux, part salariale, part patronale)
5. **Net imposable / net social / net à payer**
6. **PAS** — base, taux, montant
7. **Cumuls** — brut, plafond SS, net imposable, PAS, coût employeur
8. **Affichage** — libellés, ordre des lignes, lignes manquantes ou en trop

Format de sortie :

```markdown
## Écarts détectés

| Zone | Ligne / champ | EYWAI | Réel | Écart | Gravité |
|------|---------------|-------|------|-------|---------|
| … | … | … | … | … | 🔴 / 🟡 / 🟢 |

### Synthèse chiffrée
- Brut : [EYWAI] vs [réel] → écart [X]
- Cotisations sal. : …
- Net à payer : …

### Lignes OK (sans écart significatif)
- …
```

**Gravité** : 🔴 bloquant (net/brut/cotisation majeure) · 🟡 écart secondaire ou cumul · 🟢 affichage / libellé seul.

Pour le détail des champs à vérifier, voir [checklist-comparaison.md](checklist-comparaison.md).

**Code existant** : `comparer_simulation_reel()` dans `backend/app/modules/payroll/engine/simulation.py` si les deux bulletins sont en JSON structuré.

---

## Phase 3 — Diagnostiquer

Pour chaque écart 🔴 ou 🟡, identifier la cause :

| Cause probable | Où regarder |
|----------------|-------------|
| Calcul moteur | `backend/app/modules/payroll/engine/` (`calcul_brut.py`, `calcul_net.py`, `calcul_reduction_generale.py`, `simulation_pipeline.py`) |
| Cotisations / barèmes | Supabase `payroll_config`, `convention_collective_rules` |
| Bulletin / PDF | `backend/app/modules/payroll/documents/` |
| Saisies du mois | `runtime/payroll/data/employes/<NOM>/saisies/05.json` |
| Cumuls N-1 | `runtime/payroll/data/employes/<NOM>/cumuls/04.json` |
| Absences / congés | `backend/app/modules/absences/` |
| Paramètres société | `maintenance_settings`, `leave_settings`, `prime_anciennete_settings` |
| Contrat / sortie | `employees`, `employee_exits` |

Produire :

```markdown
## Diagnostic

### Écart 1 — [libellé]
- **Constat** : …
- **Cause probable** : [moteur | paramètre | donnée | cumul | affichage]
- **Fichier / zone** : …
- **Correction proposée** : …

## Verdict global
- [ ] Bulletin OK (écarts ≤ 0,01 € ou acceptables documentés)
- [ ] Corrections nécessaires (liste ci-dessus)
```

---

## Phase 4 — Corriger

1. **Diff minimal** — une correction ciblée par cause racine, pas de refactor opportuniste.
2. **Re-vérifier** — relancer la génération ou raisonner sur l'impact chiffré si pas de run local.
3. **Tests** — pytest ciblé dans `backend/tests/unit/payroll/` si le cas est reproductible.
4. **Migrations** — workflow `.cursor/rules/database.mdc` si paramétrage DB requis.

Répondre en français :

```markdown
## Corrections appliquées
- [fichier] : [ce qui change et pourquoi]

## Impact attendu sur [Employé]
- Brut : … → …
- Net : … → …

## À valider
- [ ] Regénérer le bulletin mai et comparer à nouveau
```

Si l'écart vient clairement d'une **erreur côté bulletin réel** (mauvaise saisie, mauvais mois), le signaler explicitement — ne pas « forcer » EYWAI à reproduire une erreur.

---

## Phase 5 — Avancer dans le backtest

Tenir un **suivi de session** (mettre à jour à chaque salarié) :

```markdown
## Suivi backtest mai — [Entreprise en cours]

| Employé | Statut | Écarts principaux | Action |
|---------|--------|-------------------|--------|
| … | ✅ OK / 🔧 corrigé / ⏳ en cours / ❌ bloqué | … | … |

**Prochain salarié** : [nom] — envoie les deux bulletins quand tu es prêt.
```

Quand une entreprise est terminée : récap entreprise, puis demander quelle entreprise attaquer ensuite.

---

## Entrée attendue (par salarié)

Idéalement fournir :

1. **Bulletin EYWAI** — PDF, capture, JSON `payslip_data`, ou copier-coller des lignes
2. **Bulletin réel** — même format
3. **Contexte** — entreprise, nom employé, mai (ou mois), type contrat

Formats acceptés : texte collé, capture, export JSON, tableau Excel. Si une seule source est partielle, extraire ce qui est disponible et lister les zones non comparables.

---

## Anti-patterns

- Comparer deux salariés ou deux entreprises dans le même diagnostic.
- Coder sans avoir produit le tableau d'écarts (phase 2).
- Hardcoder une exception « pour CARTOL » ou une filiale.
- Ignorer les cumuls quand le net du mois semble proche mais le cumul diverge.
- Confondre `/backtest-paie` (bulletin vs bulletin) avec `/elsa` (retour métier formulé par Elsa).

## Ressources

- Checklist détaillée : [checklist-comparaison.md](checklist-comparaison.md)
- Retours métier client (hors comparaison bulletin) : skill `/elsa`
- Audit moteur : `AUDIT_PAIE.md`
