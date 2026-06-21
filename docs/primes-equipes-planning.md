# Primes équipes et planning — guide RH

Guide produit **généraliste** pour configurer et contrôler les indemnités et majorations liées au planning équipes (panier repas, majoration nuit, pause payée, prime de présence).

## Prérequis

1. **Planning équipes** activé pour l’entreprise.
2. **Convention collective planning** renseignée (Entreprise → Paie → Planning équipes).
3. **Types de poste** configurés (codes, horaires par défaut, pause, plages nuit).
4. **Semaines du mois verrouillées** avant génération paie — seuls les postes verrouillés comptent.

## Séparation métier (important)

| Règle | Canal | Bulletin |
|-------|-------|----------|
| **Panier repas** (montant versé / poste) | Règle variable `per_shift_type` → saisies mensuelles | Prime exonérée (plafond URSSAF appliqué automatiquement) |
| **Majoration nuit** (ex. +25 % 20h–4h) | Métriques planning → **brut** | Ligne « heures nuit majorées » |
| **Pause payée** (ex. 30 min) | Métriques planning → **brut** | Ligne « pause rémunérée » |
| **Prime présence hebdo** | Règle `per_week_without_absence` | Prime en saisies mensuelles |

Ne pas saisir manuellement nuit ou pause dans les variables récurrentes : elles sont calculées depuis le planning. Ne pas cumuler `per_night_hour` avec les plages nuit des postes.

---

## Modèles rapides (presets RH)

| Action (Entreprise → Paie) | Effet |
|----------------------------|--------|
| Planning équipes → **Modèle 3×8 industriel** | MATIN 4–12, APREM 12–20, NUIT 20–4, pause 30 min, nuit 25 % |
| Planning équipes → **Modèle 3×8 standard** | Horaires 5–13 / 13–21 / 22–6 (autres clients) |
| Pointage → **Preset équipes pause payée** | Créneaux B avec pause déjeuner payée |
| Variables paie → **Modèle équipes** | Règles panier jour/nuit + prime nuit (montants à compléter) |
| Variables paie → **Modèle astreinte** | (existant) astreintes |

Les presets sont **idempotents** : ils ne remplacent pas une config existante (codes déjà présents ignorés).

---

## 1. Types de poste

**Entreprise → Paie → Planning équipes**

- CC planning + types MATIN / APREM / NUIT
- Pause payée (minutes), plages nuit (`night_windows`), éligibilité panier
- Poste de nuit : autoriser fin &lt; début

---

## 2. Pointage (pause payée)

**Entreprise → Paie → Comptabilisation des pointages**

- Activer le moteur
- Appliquer le preset **équipes pause payée** ou configurer `paid_lunch_break` sur les créneaux
- La pause planifiée (30 min sur le poste) réduit la déduction pause au pointage

---

## 3. Variables récurrentes (paniers, prime nuit, présence)

**Entreprise → Paie → Variables de paie récurrentes**

### Panier par poste (`per_shift_type`)

| Champ | Exemple |
|-------|---------|
| Montant unitaire | 7,40 € (montant versé au salarié) |
| Code export | SPEQ (optionnel) |
| Types de poste | MATIN, APREM ou NUIT |

### Prime équipe de nuit

- Type `per_shift_type`, poste **NUIT** seul, montant unitaire (ex. 6,95 €).

### Prime de présence (`per_week_without_absence`)

- Montant **hebdomadaire** (ex. 6 €)
- **Cocher explicitement** les types d’absence qui annulent la prime pour la semaine ISO
- Option : minimum de postes verrouillés / semaine (équipes)

Sans type d’absence coché, la règle ne génère rien.

### Codes export paie

Champ **Code export** sur la règle (ex. SPEQ, B_P4) — repris sur les saisies mensuelles et le bulletin.

---

## 4. Prime d’ancienneté, CP anc., IJSS

- **Prime d’ancienneté** : carte dédiée + CCN de l’entreprise (aligner avec une filiale référence si besoin).
- **CP ancienneté** : preset métallurgie / LEWIS / custom sur la carte CP.
- **IJSS** : profils import (mapping JSON) + opérations sur **Suivi IJSS**.

---

## 5. Workflow de clôture paie

1. Planning verrouillé (toutes les semaines du mois)
2. Variables → **Simuler** puis **Générer les saisies**
3. Bulletins → contrôler panier, nuit, pause, présence

---

## 6. Checklist recette (exemple équipes industrielles)

- [ ] Presets appliqués puis montants complétés (panier 7,40 €, prime nuit 6,95 €, export SPEQ)
- [ ] Majoration nuit via postes (25 %), pas règle `per_night_hour`
- [ ] Pause 30 min sur chaque poste verrouillé
- [ ] Prime présence : types d’absence cochés, test avec absence mid-week
- [ ] Panier = nb postes × montant unitaire
- [ ] Alignement prime anc. / CP / IJSS avec filiale référence (paramétrage manuel)

Les paramètres restent **par entreprise** ; aucune règle n’est codée en dur pour une filiale.
