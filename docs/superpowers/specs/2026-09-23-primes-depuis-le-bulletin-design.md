# Primes saisies depuis le bulletin : une seule vérité, les variables du mois

Décidé le 23/09/2026 avec Alexandre, sur un retour de Gaëlle (paie d'août
Colorplast). Premier temps d'un chantier en deux : ici les primes ; le second
temps traitera les absences et le forçage explicite d'un montant calculé.

## Le problème

Gaëlle, 23/09 : « quand on ajoute une prime en manuel dans modification du
bulletin, on retrouve cette prime dans le salaire brut mensuel, mais elle n'est
pas reprise dans le cumul brut et dans la base de toutes les cotisations. Quand
on l'enregistre dans l'onglet Primes, pas de souci. »

C'est exact, et c'est structurel. L'écran « Modifier le bulletin » ne relance pas
le moteur : « Ajouter une ligne » crée une ligne libre, l'écran additionne les
gains pour le brut (`CalculBrutSection.recalculateBrut`), et le serveur enregistre
le document tel quel puis refait le PDF (`payslip_editor.save_edited_payslip`).
Bases, cotisations, net, **cumuls** — et donc le mois suivant et la DSN — restent
ceux du calcul d'origine. L'avertissement rouge de l'écran le dit pour les
cotisations et le net, pas pour les cumuls.

L'onglet Primes, lui, écrit une variable du mois (`monthly_inputs`) que le moteur
lit : tout suit.

Il y a donc deux vérités, les variables du mois et le document retouché, et rien
ne les empêche de diverger.

## La décision

**Les variables du mois sont la seule vérité pour les primes.** Le bulletin reste
un endroit où l'on peut ajouter, corriger ou retirer une prime — c'est l'habitude
de Gaëlle, venue de Quadra, où ajouter une rubrique recalcule tout — mais chaque
geste y est traduit en variable du mois, puis le moteur recalcule le bulletin.

Le précédent existe : corriger les heures supplémentaires depuis le bulletin
écrit déjà une saisie déclarée et régénère
(`commands._recalculer_apres_correction_heures_sup`). On suit ce chemin.

## Ce que voit Gaëlle

Dans la section **Calcul du brut** de l'écran de modification :

- « Ajouter une ligne » devient **« Ajouter une prime »** et ouvre le même
  sélecteur que l'onglet Primes (`SaisieModal`) : une prime du catalogue, ou une
  **prime libre** avec son libellé et ses deux cases *soumise à cotisations* et
  *imposable*. Le catalogue porte les traitements particuliers (exonération PPV,
  panier) ; la prime libre couvre les cas ponctuels.
- Une ligne de prime venue d'une variable du mois se **corrige** (montant) et se
  **supprime** depuis le bulletin.
- Une bannière bleue, dès qu'une prime est ajoutée, corrigée ou retirée :
  « Le bulletin sera recalculé à l'enregistrement : bases, cotisations, net et
  cumuls suivront. »
- À l'enregistrement, le bulletin rechargé est celui du moteur. La prime figure
  aussi dans l'onglet Primes.

Une prime non soumise choisie ici atterrit, comme depuis l'onglet Primes, dans la
section des primes non soumises : c'est le moteur qui range. Les lignes de prime
de cette section se corrigent et se suppriment de la même façon.

## Ce qui ne change pas dans ce premier temps

- Retoucher une **ligne calculée** (salaire de base, absence, heures structurelles,
  indemnité de congés) ne fait toujours bouger que le brut. L'avertissement rouge
  est complété : « Les cotisations, le net imposable, le net à payer **et les
  cumuls** restent ceux du calcul d'origine. » Le second temps remplacera ces
  retouches par un forçage explicite.
- Les heures supplémentaires gardent leur mécanisme actuel.
- Un bulletin **importé** de Quadra reste non modifiable (`_refuser_si_importe`).
- Modifier un bulletin **validé** le repasse en brouillon (inchangé).

## Architecture

### 1. Le lien ligne ↔ saisie (moteur)

Aujourd'hui une ligne de prime du bulletin ne dit pas de quelle saisie elle vient.
Sans ce lien, on ne peut qu'ajouter.

`payslip_generator` pose `saisie_id` (l'`id` de la ligne `monthly_inputs`) sur
chaque `prime_entry` qu'il construit à partir d'une saisie, et le moteur le
recopie sur la ligne qu'il imprime dans `calcul_du_brut` ou
`primes_non_soumises`. Les primes qui ne viennent pas d'une saisie (prime
d'ancienneté calculée, primes de convention, remboursements) n'en portent pas :
elles restent des lignes calculées.

### 2. Le diff à l'enregistrement (serveur)

Nouvelle fonction pure `diff_primes(avant, apres) -> DiffPrimes` dans
`app/modules/payslips/domain/primes_editees.py`, sur le modèle de
`domain.heures_sup` :

- **ajoutées** : lignes d'`apres` portant `nouvelle_saisie` (voir 3) ;
- **modifiées** : lignes à `saisie_id` présentes des deux côtés dont le montant
  (ou la quantité) a changé ;
- **retirées** : `saisie_id` présents dans `avant`, absents d'`apres`.

Rien d'autre n'entre dans le diff : une ligne sans `saisie_id` ni
`nouvelle_saisie` n'est pas une prime saisie.

### 3. Ce que l'écran envoie

Une prime ajoutée depuis le bulletin est posée dans `calcul_du_brut` avec un bloc
`nouvelle_saisie` : `{name, amount, is_socially_taxed, is_taxable,
catalog_prime_id}` — exactement le corps de `MonthlyInputCreate`, produit par le
même sélecteur que l'onglet Primes.

### 4. L'application (serveur)

Dans `commands.edit_payslip`, après l'enregistrement (l'historique garde ainsi la
version saisie), `_appliquer_primes_editees(cmd, avant)` :

1. calcule le diff ; s'il est vide, rien ;
2. insère les ajoutées, met à jour les modifiées, supprime les retirées dans
   `monthly_inputs` — en vérifiant que chaque `saisie_id` appartient bien au
   salarié, à la société et au mois du bulletin ;
3. régénère le bulletin par `generate_payslip` avec les mêmes options que les
   heures sup (`force_calendrier_incomplet=True`, `regenerer_bulletin_valide=True`).

Si les heures sup et les primes changent dans le même enregistrement, **une seule
régénération** : les deux écritures de saisies d'abord, puis un appel au moteur.

### 5. Ce que la régénération écrase

La régénération reconstruit tout le bulletin. Une retouche manuelle d'une ligne
calculée faite **dans le même enregistrement** qu'un changement de prime est donc
perdue — l'historique la conserve. L'écran le dit quand les deux coexistent :
« Cette retouche sera remplacée par le recalcul ; enregistrez-la séparément. »

## Erreurs

- `saisie_id` inconnu ou d'un autre salarié/mois : refus 422, rien n'est écrit.
- Échec du moteur à la régénération : les saisies restent écrites (elles sont la
  vérité), le bulletin enregistré reste la version saisie, et la réponse porte
  l'erreur pour que l'écran propose « Régénérer ».

## Tests

**Domaine, `diff_primes`** (pur) : ajout seul ; modification de montant ;
suppression ; ligne sans lien ignorée ; ligne retouchée sans changement de
montant ignorée ; ajout et suppression dans le même diff.

**Commande, `edit_payslip`** (Supabase simulé) : un ajout crée la saisie et
régénère une fois ; une suppression retire la bonne saisie ; un `saisie_id` d'un
autre salarié est refusé sans écriture ; heures sup et prime ensemble → une seule
régénération ; bulletin importé → refus inchangé.

**Moteur** : une saisie produit une ligne portant son `saisie_id`, dans le brut
ou dans les primes non soumises selon ses cases.

**Écran** (vitest) : « Ajouter une prime » ouvre le sélecteur ; la bannière de
recalcul apparaît ; l'avertissement rouge mentionne les cumuls.

**De bout en bout, sur le test** : sur un bulletin d'août Colorplast en
brouillon, ajouter une prime soumise de 100 € depuis le bulletin donne le même
bulletin — brut, bases, cotisations, net, cumul brut — que la même prime saisie
dans l'onglet Primes puis régénérée.

## Critère de réussite

Le test de bout en bout ci-dessus, au centime. C'est exactement le constat de
Gaëlle retourné : les deux portes d'entrée donnent le même bulletin.
