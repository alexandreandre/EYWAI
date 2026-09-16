# Colorplast, mai 2026 : EYWAI contre Quadra, ligne à ligne

Rejeu du 16/09/2026 (`backend/scripts/colorplast_rejeu_test.py --jusqu-a 5`),
comparé au PDF du cabinet `data/colorplast/bulletins/2026-05/`. Sept salariés.
Fenêtre des variables : **20/04 → 24/05**. Convention : **écart = EYWAI − Quadra**.

Mai est le mois le plus dense de la série : augmentation générale au 01/05,
versement de la participation 2025 avec des acomptes déjà versés à déduire,
journée de solidarité le 25, deux jours fériés non payés pour les derniers
embauchés, un arrêt maladie et un accident du travail.

Deux anciens salariés, Chaleyssin et Da Silva Car, reçoivent un bulletin sans
salaire pour leur seule part de participation (11,04 et 221,81). Ils sont hors
du périmètre du rejeu.

## État

| | Brut | Net à payer | Impôt | Net social | Compteurs | Plafond | Coût patronal | Déduction HS | Allègement |
|---|---|---|---|---|---|---|---|---|---|
| Bugny | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Cotte | ✓ | ✓ | ✓ | ✓ | *écart assumé* | ✓ | ✓ | ✓ | −1,18 |
| Demory | ✓ | ✓ | ✓ | ✓ | *écart assumé* | ✓ | ✓ | ✓ | ✓ |
| Espinosa | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Fuckar | −0,01 | ✓ | ✓ | ✓ | *écart assumé* | ✓ | ✓ | ✓ | ✓ |
| Girerd | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Gautheron | *en attente* | | | | | | | | |

Les sept bruts tombent au centime, y compris les deux bulletins d'arrêt.

## Ce qui a été corrigé dans le moteur

### Seul l'arrêt maladie réduisait le plafond

Le plafond de Sécurité sociale se réduit au prorata des jours de suspension du
contrat. Notre liste des absences qui déclenchent cette réduction ne contenait
que `arret_maladie` : un **accident du travail**, un congé maternité ou
paternité passaient au travers, et le plafond restait entier.

Demory est en accident du travail du 23 au 29/05. Corrigé, avec les trois types
manquants, et couvert par `test_arrets_de_travail_deduits.py`.

### Le plafond ne comptait que les jours ouvrés inscrits au calendrier

Même dossier, deuxième couche. Un arrêt suspend le contrat **du premier au
dernier jour déclaré**, week-end et jours fériés enjambés compris. Nous ne
retirions que les jours ouvrés typés au calendrier.

L'accident de Demory est déclaré du 23 au 29/05 : le 23 et le 24 tombent un
week-end, le 25 est le lundi de Pentecôte. Le cabinet retire les sept jours ;
nous n'en retirions que quatre. Son plafond valait 3 229,84 au lieu des
2 842,26 du cabinet — **387,58 €**, soit très exactement trois jours de plafond
(4 005 / 31 = 129,19).

Le cabinet est dans son droit : c'est bien la durée déclarée qui compte, celle
qui part à la caisse. Corrigé dans `ratio_plafond_periode`, avec un repère de
non-régression sur l'ancien chiffre.

### Les heures d'un arrêt non maintenu restaient dans la base de l'allègement

Le moteur considérait toute heure d'arrêt comme rémunérée, donc conservée dans
le SMIC de référence qui sert de base à l'allègement de cotisations. C'est vrai
quand l'employeur maintient le salaire ; ce n'est pas le cas ici, où la caisse
paie directement.

Le moteur retire désormais ces heures **à proportion de ce que l'employeur ne
maintient pas** : rien si le maintien est complet, tout s'il est nul, la
fraction correspondante entre les deux. Couvert par
`test_heures_arret_smic_reference.py`.

## Ce qui a été corrigé dans les données

### Demory et Fuckar ne sont augmentés qu'en juin

J'avais placé leur augmentation en mai. Leurs bulletins de mai portent encore
12,2000 €/h : ils passent à la nouvelle base le mois suivant. Corrigé.

### `prior_service_months` porte l'ancienneté totale, pas la reprise

Le champ est censé contenir des **mois de service antérieurs** (contrat
précédent, groupe), que le moteur ajoute à l'ancienneté qu'il calcule lui-même.
Chez Colorplast il contient l'ancienneté totale écoulée : Girerd 144, Cotte 67,
Bugny 44. Le moteur la compte donc deux fois.

Sans effet pour les anciens — ils sont au-dessus de tous les seuils dans les
deux cas. Mais il faisait passer Demory et Fuckar au-dessus des trois mois
d'ancienneté, et leur faisait **payer des jours fériés que le cabinet ne paie
pas**. Remis à 0 pour ces deux-là.

**À vérifier sur les six autres sociétés** : le champ y est probablement rempli
de la même façon.

### Mai était déjà entièrement saisi dans la base de test

Une saisie « Saisie backtest paie mai 2026 » portait déjà les primes, la
participation, les acomptes, le report du net négatif, les arrêts et les fériés
au calendrier. J'ai commencé par en ajouter un double — troisième fois de la
session que la base contient déjà ce que j'allais écrire.

La saisie existante était d'ailleurs plus juste que la mienne : la participation
de Girerd y est placée sur un **plan d'épargne entreprise**, pas versée.

Le rejeu de mai pose désormais uniquement ce qui manquait vraiment — les heures
supplémentaires — et il se déroule sans intervention manuelle.

## Ce que nous ne reproduisons pas, et pourquoi

### Les heures d'arrêt restent au compteur imprimé du cabinet

Demory 32,80 h, Fuckar 28,95 h (dont −3,05 h au compteur d'heures sup). Le
cabinet les garde au compteur imprimé du bulletin ; nous les en sortons,
puisqu'elles ne sont pas payées.

C'est la même question que pour Gautheron : **qui verse le complément de salaire
au-delà du 3ᵉ jour d'arrêt ?** Si c'est l'employeur, les heures sont maintenues
et le cabinet a raison de les garder. Si c'est la prévoyance, elles ne le sont
pas. **Question 4** de la page tenue pour Gaëlle.

### Cotte traîne toujours son congé pour événement familial de mars

23,40 h au compteur et 2,40 h au compteur d'heures sup, plus 1,18 € d'allègement.
Voir `docs/colorplast-mars-2026-ligne-a-ligne.md`.

## Ce qui reste ouvert

### Gautheron : ses cumuls dépendent d'avril

Son brut de mai tombe au centime (2 432,78), mais ses cumuls héritent de son
arrêt d'avril, toujours suspendu à la question du maintien. Elle est imprimée au
rejeu sans le faire échouer.

### Fuckar : 0,01 € sur le brut

Un centime sur 1 664,78. Sans conséquence sur le net, l'impôt ni les cotisations.
