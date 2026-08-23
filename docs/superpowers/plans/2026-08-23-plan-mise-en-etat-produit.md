# Plan de mise en état du produit — du 23 août à la bascule paie

Écrit le 23/08/2026, après les audits des axes A (sécurité), C (vérification
des corrections) et D (intégrité des données), et la cartographie de ce qui
est réellement vérifié.

**Ce que « prêt » veut dire ici**, en cinq conditions vérifiables :
1. le moteur produit des bulletins qui collent à ceux du cabinet ;
2. les utilisateurs peuvent entrer sans risque — fait ;
3. la donnée ne se dégrade pas en usage normal ;
4. une panne se voit ;
5. ce qui est annoncé vérifié l'est réellement.

Les conditions 1, 3, 4 et 5 ne sont pas remplies aujourd'hui. Ce plan les
traite dans l'ordre où elles bloquent la suite.

---

## Phase 0 — D'ici mercredi : préparer, ne rien déployer

Rien de cette phase ne touche la production. Le gel des déploiements tient
jusqu'à la réunion : treize failles fermées et deux régressions en 24 h, à
trois jours d'une signature, justifient de stabiliser.

### 0.1 Ranimer les tests de non-régression du brut ⟵ *commencer par là*

**Pourquoi.** Quatre tests vérifiaient des montants de référence sur le
calcul du brut : mois complet, absence non rémunérée, heures
supplémentaires à 25 %, congés payés sur cinq jours. Ils sont gelés dans
`tests/integration/known_failures.txt` depuis le 7 août. Plus aucun montant
n'est vérifié sur le cœur du moteur, et le dernier scénario est justement
l'écart n°1 attendu sur juillet.

**Comment.** Pas en ajoutant les champs manquants un par un — j'ai sondé,
chaque champ ajouté en révèle un autre, et cette dérive recommencera. La
fausse fiche de paie du test doit être construite à partir du **contrat
réel** du moteur, pour qu'un nouveau champ obligatoire casse bruyamment à
la construction au lieu de tuer le test en silence. Même leçon que les
simulacres sans gabarit qui ont laissé deux routes mortes en production.

**Critère de sortie.** Les 4 scénarios passent au vert en comparant des
montants, et ils sortent de la liste des échecs gelés. Un cinquième test
vérifie que la fausse fiche suit le contrat réel.

### 0.2 Réparer le chargeur de bulletins du backtest

**Pourquoi.** `scripts/backtest/pdf_loader.py` cherche les fichiers dans un
dossier `Config/` qui n'existe plus : six sociétés sur sept lèveraient une
erreur. Plus grave, son repli silencieux `pdfs[0]` peut comparer **le
mauvais mois** sans rien dire. Un chargeur qui se trompe de mois est pire
qu'un chargeur qui plante.

**Critère de sortie.** Les 7 sociétés se chargent, et un mois absent lève
une erreur explicite au lieu de prendre le premier fichier venu.

### 0.3 Rassembler les données de juillet

- Descendre du Drive les bulletins de référence de juillet (Cartol, MBC,
  LEWIS, Comitech, Colorplast) — ils y sont depuis le 3 août, rien n'a été
  récupéré en local ; les pointages hebdomadaires S26 à S30 aussi.
- Ingérer les pièces jointes de Gaëlle dès qu'elles sont dans
  `data/_inbox/` : soldes CP au 31/07 des 5 sociétés, adresses Colorplast,
  dossiers CSE de Cartol et LEWIS.
- Acter que **MAJI et Zone 404 sont hors backtest** : ni dossier de juillet
  ni cumuls de juin.

**Critère de sortie.** `data/<societe>/` contient juillet pour les 5
sociétés retenues, et l'inventaire le confirme.

### 0.4 Deux gestes courts de fiabilité

- **Sauvegarde du stockage** : 1384 bulletins de paie et 1961 objets n'ont
  aujourd'hui aucune sauvegarde — la base est protégée, les fichiers non.
- **Une alerte minimale** : un cron est en échec depuis 22 jours sans que
  personne le sache, et il n'existe aucune alerte dans tout le système.
  Commencer par le strict nécessaire — échec de cron et taux d'erreurs 5xx.

---

## Phase 1 — Mercredi 26, 15 h : la séance

Séance de travail, pas démonstration. **Ne pas montrer le badgeage** : il
n'est paramétré nulle part, et chez la seule société qui badge aucun créneau
n'existe, donc aucune heure supplémentaire n'est détectée.

**Trois décisions à obtenir :**
1. **Marquage « atelier » pour les JTC.** Leur tableau des codes horaires
   (reçu le 2 juillet, jamais exploité) distingue déjà Atelier et Bureau,
   service par service. La question devient : « on reprend votre découpage
   existant, vous confirmez ? »
2. **Pauses des trois sociétés qui pointent.** Le même tableau donne les
   horaires réels de Cartol — une base concrète à leur soumettre.
3. **Arbitrage des 16 jours** d'absences validées que le planning ne
   reflète plus.

**Deux choses à annoncer avant qu'elles ne les découvrent :** aucun bulletin
n'est validé, donc l'espace salarié sera vide ; et un salarié ne voit
désormais que ses propres données.

**Une question de données :** deux salariés de MBC partagent la même
adresse personnelle, l'un des deux est faux.

---

## Phase 2 — Du 27 août au 4 septembre : le backtest de juillet

C'est le cœur de la valeur du produit, et la fenêtre est courte : Gaëlle
produit cette paie cette semaine, et la rencontre est calée la semaine du
1er septembre.

### 2.0 ⚠ Constat du 23/08 : juillet est VIDE dans l'outil

Mesuré en base, sur la production :

| Donnée de juillet 2026 | Présent |
| --- | --- |
| Bulletins | **0** |
| Saisies mensuelles (primes, acomptes) | **0** |
| Demandes d'absence | **0** |
| Calendriers avec heures réelles | **0** |
| Calendriers prévisionnels auto-générés | 252 |
| Jours de congé dans les calendriers | 31, pour 224 salariés |

Trente-et-un jours de congé sur un mois de juillet, c'est invraisemblable.
Le mois n'existe dans l'outil que sous forme de calendriers uniformes
générés fin juin : LEWIS a planifié 154 h pour ses 39 salariés, MBC 165 h
pour ses 75, temps partiels compris.

**Conséquence directe** : le backtest comparerait un mois vide à un mois
réel. Le premier essai sur Colorplast le confirme — la chaîne fonctionne
(7 références appariées, écarts systématiques identifiés) mais les écarts
par salarié atteignent 1 900 à 3 900 €.

**Le backtest de juillet n'est donc pas un réglage à ajuster : il demande
une SAISIE de juillet.** Trois sources, trois natures :
- les **heures réelles** — feuilles de pointage S26 à S30, sur le Drive,
  formats hétérogènes (scans pour la plupart, tableur pour LEWIS) ;
- les **congés** — nulle part dans l'outil, Gaëlle les a ;
- les **primes et acomptes** — dans les « TABLEAU RECAP » du Drive.

C'est précisément l'objet de la session avec Gaëlle la semaine du 1er
septembre. À arbitrer : soit on saisit juillet et le backtest est
concluant, soit on l'acte comme théorique et il ne vérifie que la
mécanique.

### 2.1 Traiter d'abord les causes racines — chiffres re-mesurés le 23/08

- **Heures supplémentaires fantômes : alerte mal cadrée.** L'annonce parlait
  de 153 calendriers sur 252 au-dessus du contrat. Mesuré : **23 sur 224**
  dans le périmètre du backtest, dont la plupart sont des cadres et
  forfaits-jours pour qui les heures du calendrier sont une convention. Le
  vrai résidu tient en **5 temps partiels planifiés à temps plein** — dont
  un à 12 h/semaine planifié 154 h.
- **Mutuelles : défaut confirmé et plus grave que prévu.** 159 salariés ont
  la cotisation entière à leur charge, alors que le bulletin réel de Cartol
  (juillet, code EMU1) montre 29,64 € salarié / 29,63 € employeur. Cartol
  80 salariés, LEWIS 37, MBC 24. Cause : les lignes DSN non rapprochées
  d'une formule connue retombent sur « Mutuelle Autre », sans part
  patronale. **Les fiches organisme de Cartol et LEWIS manquent** — à
  demander. Détail dans la mémoire du projet.

### 2.2 Décider du sort des congés payés

Le vocabulaire du lot 2 n'est pas livré : vérifié le 23/08, l'analyseur ne
connaît que `conges_payes` et jamais `conge`, et aucune traduction n'existe
entre les deux — un congé payé validé reste donc invisible pour la paie.
Nuance mesurée : sur juillet le sujet est moins brûlant qu'attendu, faute
de données — 31 jours de congé seulement, et zéro demande d'absence.
Soit on livre le lot 2 avant, soit on le déclare écart connu et on
l'exclut du diagnostic — mais on le décide **avant**, pas en découvrant les
résultats.

### 2.3 Lancer et exploiter

Déclarer d'avance en écarts connus les trois défauts moteur documentés et
non corrigés (diviseur forfait 21,67 contre 22, retenue CP calculée au
maintien, résidu de net imposable d'environ 3,35 € par salarié ayant des CP)
plutôt que de les re-diagnostiquer. Bonne nouvelle : juillet est le premier
mois où le SMIC en base est le bon.

**Critère de sortie.** Un écart chiffré par société, chaque écart rattaché à
une cause, et la liste de ce qui reste inexpliqué pour la séance avec
Gaëlle.

---

## Phase 3 — Avant d'ouvrir aux salariés : que la donnée ne se dégrade plus

### 3.1 Le canal des heures réelles qui efface les absences

**Le défaut le plus coûteux encore ouvert.** Poser des heures réelles sur un
jour d'absence validée — par pointage, import de feuille, badgeuse ou saisie
RH — annule son effet en paie, marqueur compris, sans le moindre
avertissement. C'est exactement la population de la vague 1.

Étendre la garde au canal réel, et faire remonter en anomalie plutôt qu'en
silence.

### 3.2 Élargir la protection des absences

Aujourd'hui **42 jours protégés sur 2455**. Marquer tout jour portant un
type d'absence et une donnée d'arrêt, sans exiger une demande validée en
face — c'est ce qui manque aux 380 jours d'arrêt maladie non marqués, dont
351 portent la nature de l'arrêt. Et couvrir les types absents de la liste
blanche (`arret_at`, `absence_non_remuneree`, `absence_justifiee` : 665
jours).

### 3.3 Paramétrer le badgeage, avec leurs décisions

Créneaux horaires par société — le tableau de Cartol donne la base. Sans
créneau, aucune heure supplémentaire n'est détectée ni retenue.
Traiter aussi les postes de nuit (journée coupée en deux, 0 h comptabilisée)
et rendre l'application des décisions d'heures supplémentaires idempotente :
aujourd'hui, approbation puis nouvel aperçu puis nouvelle approbation
double le paiement.

---

## Phase 4 — Dette structurelle, en continu

### 4.1 Rendre le vert crédible

- **La CI n'exécute que 331 tests sur 6822 avant de déployer** ; trois
  répertoires de tests ne sont lancés par aucun workflow.
- Le fichier de smoke qui semble couvrir 78 routes ne prouve rien : son
  authentification est vide et il accepte le code 401 comme un succès.
- **262 routes ne sont citées par aucun test**, dont la badgeuse en entier.

### 4.2 Traiter le motif d'autorisation comme un motif

Sept endroits colmatés un par un, un huitième trouvé à chaque fois. Il faut
une garde par défaut au niveau de l'architecture — comme celle posée sur le
routeur planning, qui a couvert 26 routes d'un coup.

Deux petites failles restent ouvertes, sans données sensibles derrière
aujourd'hui : historique de handicap (table vide) et fiches candidats.

### 4.3 Vérifier ce qui est utilisé et jamais contrôlé

L'effort de vérification est aujourd'hui **inversement corrélé à l'usage
réel** : des modules à plus de 100 tests n'ont aucune donnée en production,
tandis que d'autres, utilisés quotidiennement, n'en ont aucun. Ordre
proposé : OETH, recrutement, suivi IJSS, import DSN, équipes, documents,
piste d'audit, comptabilité, onboarding, médailles du travail.

---

## Ce qui reste entre tes mains

- Fermer l'inscription publique Supabase.
- Régénérer le secret PISTE/KALI — présent dans l'historique d'un dépôt
  public, à considérer comme compromis.
- Trancher sur le compte orphelin d'Elsa avant de l'inviter.
- Déposer les pièces jointes de Gaëlle dans `data/_inbox/`.

## Régime de travail proposé

Vitesse et vérification adversariale systématique tant qu'on durcit ; puis,
dès que des utilisateurs réels sont dans le système, je prépare et tu valides
avant déploiement. Cette nuit a montré les deux faces : treize failles
fermées, et deux fonctionnalités cassées que seule la seconde passe a
rattrapées.
