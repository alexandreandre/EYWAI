# Primes Colorplast — guide RH et validation paie

Document opérationnel pour la gestion des trois types de rémunération variables chez Colorplast.

## 1. Prime exceptionnelle (brute, variable)

**Parcours RH** : Menu **Saisies** → onglet **Primes** → **Nouvelle saisie**.

- Choisir « Prime exceptionnelle » (catalogue global ou entreprise).
- Saisir le montant décidé avec le directeur de site.
- Vérifier : **soumise aux cotisations = Oui**, **soumise à l'impôt = Oui**.
- Fréquence : **ponctuelle**, mois par mois (pas de récurrence automatique).

**Catalogue entreprise** (optionnel) : créer une entrée `company_bonus_types` « Prime exceptionnelle » pour pré-remplir les flags fiscaux.

## 2. IND transport (nette, au contrat)

**Parcours RH** : Fiche salarié → **Modifier** → section transport.

| Champ | Usage Colorplast |
|-------|------------------|
| Abonnement transport (€/mois) | Remboursement URSSAF 50 % — si utilisé |
| **Indemnité transport contractuelle (€ net/mois)** | Montant fixe écrit au contrat, versé en net chaque mois |

Le montant est ajouté au **net à payer** (hors brut, hors cotisations), automatiquement à chaque bulletin.

**Migration données** : pour chaque salarié concerné, renseigner `indemnite_mensuelle_nette` sur la fiche (valeur du contrat).

## 3. Prime d'ancienneté (CC plasturgie)

Calcul **automatique** par le moteur de paie si :

- Convention collective **plasturgie** assignée à l'entreprise (IDCC **0292** ou **1297** selon référentiel).
- `date_entree` et salaire de base corrects sur la fiche salarié.
- Règles CC extraites dans Super Admin → **Conventions collectives**.

Barème (accord 28/06/2011) : 2,4 % / 4,8 % / 7,2 % / 9,6 % / 12 % du salaire de base selon paliers 3, 6, 9, 12, 15 ans.

**Hors cadres** : la prime conventionnelle ne s'applique pas au personnel cadre.

### Checklist validation avant bascule prod

- [ ] Récupérer 2 bulletins Colorplast de référence (1 avec ancienneté, 1 avec IND transport).
- [ ] Vérifier import/extraction IDCC plasturgie en Super Admin.
- [ ] Assigner la CC à l'entreprise Colorplast.
- [ ] Générer un bulletin test EYWAI pour le même salarié / même mois.
- [ ] Comparer : prime d'ancienneté, IND transport, net à payer.
- [ ] Écart > 0,50 € → remonter avant clôture paie.

## Configuration Super Admin (prime d'ancienneté)

1. **Conventions collectives** → rechercher « plasturgie » ou IDCC 0292.
2. Importer depuis KALI si absent.
3. Lancer l'extraction des règles ; vérifier `prime_anciennete.bareme` présent.
4. Assigner la convention à Colorplast (fiche entreprise).

Un seed déterministe (`plasturgie_0292`) complète l'extraction IA si le barème est incomplet.
