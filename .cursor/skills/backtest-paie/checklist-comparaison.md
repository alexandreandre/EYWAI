# Checklist comparaison bulletin EYWAI vs réel

Référence pour la phase 2 du backtest. Tolérance : **0,01 €** par montant.

## En-tête bulletin

- [ ] Entreprise (raison sociale, SIRET)
- [ ] Salarié (nom, matricule, emploi, classification)
- [ ] Période (mai AAAA)
- [ ] Ancienneté / date entrée

## Base de calcul

### Contrat heures
- [ ] Heures travaillées / heures payées
- [ ] Heures supplémentaires (25 %, 50 %)
- [ ] Heures complémentaires (10 %, 25 %)
- [ ] Absences (CP, maladie, sans solde…) — jours et retenues
- [ ] RTT

### Forfait jours
- [ ] Jours travaillés / jours ouvrés
- [ ] Absences en jours
- [ ] Pas de lignes heures incohérentes

## Éléments de brut

- [ ] Salaire de base (montant et base)
- [ ] Primes (ancienneté, exceptionnelles, 13e…)
- [ ] Indemnités (transport, panier, etc.)
- [ ] Avantages en nature
- [ ] IJSS / maintien maladie
- [ ] Retenues sur brut
- [ ] **Total brut**

## Cotisations salariales

Pour chaque ligne :
- [ ] Libellé présent des deux côtés
- [ ] Base identique (ou expliquée)
- [ ] Taux identique
- [ ] Montant salarial identique

Zones fréquentes d'écart :
- Vieillesse plafonnée / déplafonnée
- Retraite complémentaire (Tranche 1 / 2)
- CSG / CRDS (base déductible vs non)
- Mutuelle / prévoyance
- Chômage (AT/MP, AGS si visible salarié)

## Cotisations patronales

Même logique que salariales. Écarts patronaux n'impactent pas le net salarié mais signalent un bug moteur ou barème.

## Net et fiscalité

- [ ] Total cotisations salariales
- [ ] Net imposable
- [ ] Montant net social (si affiché)
- [ ] Net à payer avant PAS
- [ ] PAS — base, taux, montant
- [ ] **Net à payer final**
- [ ] Éléments non soumis (titres-restaurant, remboursements…)

## Coût employeur

- [ ] Total cotisations patronales
- [ ] Réduction Fillon / RGDU (montant ou coef)
- [ ] **Coût total employeur**

## Cumuls annuels (depuis janvier)

- [ ] Brut
- [ ] Plafond SS
- [ ] Net imposable
- [ ] PAS prélevé
- [ ] Heures / jours (selon contrat)
- [ ] Coût employeur cumulé

Un écart sur cumul avec net du mois OK → souvent cumul N-1 (`cumuls/04.json`) ou mois antérieur non rejoué.

## Affichage (🟢 si seul écart)

- [ ] Ordre des lignes
- [ ] Libellés (mutuelle, primes…)
- [ ] Lignes manquantes ou en trop
- [ ] Arrondis visibles (> 0,01 € → remonter en 🟡)

## Mapping JSON EYWAI (si disponible)

| Bulletin réel (concept) | Clé EYWAI typique |
|-------------------------|-------------------|
| Salaire brut | `salaire_brut` |
| Net à payer | `net_a_payer` |
| Net imposable | `synthese_net.net_imposable` |
| Cotisations | `cotisations[]` ou lignes détaillées |
| Cumuls | section cumuls du `payslip_data` |

Utiliser `comparer_simulation_reel(bulletin_simule, bulletin_reel)` pour le rapprochement automatique des totaux.
