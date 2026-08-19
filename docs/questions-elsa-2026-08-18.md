# Questions en suspens — 18 août 2026

Balayage après les messages d'Elsa du 18/08 (67 messages nouveaux depuis le
11/08, conversation ré-extraite le 18/08). Référentiel : la liste épurée de
13 questions envoyée le 11/08 à 18 h 48 (`_chat.txt:9377`), issue de la liste
de 16 d'`afaire.md`. Marie est rentrée de congés : c'est elle qui a fourni les
réponses du jour, via Elsa.

## Réponses trouvées

### #13 — OD de paie des six sociétés *(partiel : 5 sur 6 attendues)*
- **Attendu** : une OD de paie récente par société, pour y lire les comptes
  manquants de l'interfaçage comptable (paniers, cantine, IJSS).
- **Trouvé** : les OD Cegid Quadra de **juillet 2026** pour Cartol, LEWIS,
  Comitech, MBC — plus Colorplast (déjà couverte par l'OD d'octobre 2025).
  Toutes équilibrées, avec le journal PAI complet. Envoyées par Elsa après
  « un retour de Marie ».
- **Source** : `_chat.txt:9454-9465` ; fichiers rangés le 18/08 sous
  `data/<societe>/referentiel/<societe>-paie-07-2026.xlsx` (cartol,
  colorplast, comitech, lewis, mbc).
- **Ce qu'on y lit** :
  - **Paniers** : Cartol `64130300` ; LEWIS et MBC `64130400` + `64140100`
    (deux comptes, vraisemblablement part exonérée / part soumise, à
    confirmer au branchement).
  - **IJSS** : `43874000` (« organismes sociaux — produits à recevoir »),
    présent chez Cartol et LEWIS en juillet.
  - **Cantine** : aucun libellé explicite dans ces OD. Candidats : les
    sous-comptes `425900xx` (LEWIS, MBC, un par salarié ?). **Toujours
    ouvert**, voir Pistes.
  - Bonus : activité partielle LEWIS `64131100`, 13e mois LEWIS `64114000`,
    PPV `64130100`/`64130200` selon la société.
- **Suite** : brancher ces comptes dans l'interfaçage compta (#26) et
  vérifier que LEWIS et MBC tombent au centime sur juillet. **Manquent MAJI
  et Zone 404** — relancer Marie (rentrée), d'autant qu'elle doit aussi les
  accès net-entreprises (#6).

### Prévoyance Colorplast — question du 05/08, hors liste numérotée
- **Attendu** : quelle cotisation va sur `43740000` (Mutex) et `43741000`
  (Alptis) dans l'OD Colorplast (question posée le 05/08,
  `_chat.txt:9085`).
- **Trouvé** : « La prévoyance MUTEX (437400) s'est terminée en 12/2025,
  donc compte à ne plus utiliser, le **437 411** est le bon compte à partir
  de 01/2026, c'est **GAN prévoyance** ». Cohérent avec l'OD Colorplast de
  juillet, qui porte bien `43741100` et plus aucun `437400xx`.
- **Source** : `_chat.txt:9453`
- **Suite** : mettre à jour le mapping compta Colorplast (l'OD de référence
  d'octobre 2025 est antérieure au changement). ⚠ Vérifier l'impact sur les
  fiches de paramétrage OC (`data/colorplast/referentiel/fpoc/`) qui datent
  Mutex = non-cadres : si le contrat prévoyance a changé d'assureur au
  01/01/2026, la FPOC Mutex est peut-être périmée aussi côté DSN.

### Priorités d'intégration — question du 13/08, hors liste numérotée
- **Attendu** : l'ordre de priorité des fonctionnalités pour l'intégration
  progressive (demandé le 13/08 après l'abandon du tableau d'identifiants au
  profit de liens d'activation).
- **Trouvé** : « La paie c'est la priorité numéro 1 … le package paie » =
  **bulletin + DSN + provision + banque**. Ensuite, « vraiment secondaire » :
  1) recrutement (pour voir s'il s'intègre bien dans la paie),
  2) visite médicale, 3) CSE, 4) entretiens.
- **Source** : `_chat.txt:9413-9418`
- **Suite** : écrire la stratégie d'intégration promise à Elsa et la lui
  envoyer.

## Pistes (sujet évoqué, donnée manquante)

### #13 (reliquat) — comptes cantine
- **Trouvé** : les OD de juillet ne portent aucun libellé « cantine » ;
  seuls candidats les sous-comptes `425900xx` chez LEWIS et MBC — **manque**
  la confirmation de ce qu'ils contiennent.
- **À demander à Elsa** : « Dans les OD de juillet, la cantine passe par
  quels comptes ? Je vois des 425900xx chez LEWIS et MBC sans libellé. »

### #6 — Accès net-entreprises de Cartol, LEWIS, MAJI et Zone 404
- **Trouvé** : Marie est rentrée (elle a fourni les OD du jour) — **manque**
  les identifiants eux-mêmes, toujours aucune trace.
- **À demander à Elsa** : « Marie étant rentrée, peux-tu lui redemander les
  accès net-entreprises de Cartol, LEWIS, MAJI et Zone 404 ? Et au passage
  les OD de paie de MAJI et Zone 404, les seules manquantes. »

## Sans trace (rien dans les 67 messages)

- #1 — Adresses e-mail des salariés, six sociétés — **toujours le plus urgent**
- #2 — Les 16 salariés MBC absents du tableau JTC
- #3 — PV des élections CSE de Cartol et LEWIS
- #4 — CSE MBC : fin de mandat, secrétaire/trésorier
- #5 — CSE ou PV de carence chez Colorplast, MAJI et Zone 404
- #7 — Provision CP des six autres sociétés
- #8 — État Cartol à 71 salariés au lieu de 86
- #10 — Périmètre entretiens MBC (attente Gaëlle, rentrée en principe)
- #14 — Clé de licence Cegid (attente Vanessa)
- #15 — DSN de juillet (les fichiers du 18/08 sont des OD, pas des DSN)
- #16 — Créneaux pour le point paye avec Gaëlle

## Questions d'Elsa restées sans réponse

- [11/08 19:55] « Les erreurs au niveau de la paie tu as pu voir ? » —
  `_chat.txt:9384`. À traiter : demander de quelles erreurs elle parle si
  ce n'est pas évident, ou répondre sur l'état des backtests.
- [11/08 19:55] « Et les taux personnalisés de la DGFIP ? » —
  `_chat.txt:9385`. Répondre avec l'état du #31 (écran PAS livré, 182 taux
  en prod, DSN de juin appliquées ; bloqué ensuite par l'accès
  net-entreprises et les DSN de juillet).
- [11/08 19:55] **Nouveau point ajouté par Elsa** : la **DSN d'amorçage**
  (DSN à produire à l'embauche pour obtenir le taux PAS du nouveau salarié).
  Vanessa devait la lui envoyer ; à intégrer au chantier PAS/DSN comme
  fonctionnalité attendue. — `_chat.txt:9385`

## Ingestion et conflits

- 5 fichiers OD rangés automatiquement le 18/08 sous
  `data/<societe>/referentiel/` (le doublon Colorplast est identique).
- **1 divergent à arbitrer, non écrasé** : `semaine 21 (1).pdf` (22/06) vs
  `data/comitech/pointages/2026-05/semaine-21.pdf` — même emplacement,
  contenu différent.

## Contexte

Marie : rentrée (retour confirmé le 18/08). Gaëlle : rentrée en principe
depuis le 17/08, rien reçu d'elle — les #10 et #16 sont relançables dès
maintenant. Vanessa : encore en congés (3 semaines depuis ~le 08/08), les
#14 et la DSN d'amorçage attendront son retour.

---

## Addendum du 19/08

### #7 — Provision CP : RÉPONDU (5 sociétés sur 6 attendues)
- **Trouvé** : les « États de provision des congés payés » du cabinet,
  exercice 01/01→30/06/2026, pour Cartol (rafraîchi), LEWIS, Colorplast,
  MBC et Comitech. Manquent MAJI et Zone 404 (comme pour les OD).
- **Source** : `_chat.txt` du 19/08 vers 17h01-17h05 ; rangés sous
  `data/<societe>/compteurs/provision-cp-2026-06.pdf`.
- **Suite** : charger les soldes N-1 dans EYWAI société par société (même
  méthode que Cartol en juillet) — c'est ce qui active le drapeau « soldes
  repris » du design d'intégration et fait apparaître les compteurs de
  congés.

### #8 — État Cartol à 71 salariés : probablement caduque
Le nouvel état Cartol compte ~88 lignes (contre 71 dans celui du 21/07,
pour 86 payés en juin) : l'ancien fichier était simplement une extraction
antérieure aux embauches. À confirmer au chargement, plus rien à demander.

### Groupe d'intégration : les premiers utilisateurs sont connus
Elsa a donné la composition (message du 19/08 vers 9h29) : d'abord
**Gaëlle (RH usines), Vanessa (MAJI/Zone 404) et Elsa**, ensuite les
directeurs de site (MBC, LEWIS, Comitech/Colorplast, Cartol, MAJI/Zone
404 — noms dans le fil). Pas de Teams : groupe WhatsApp. Les numéros de
Gaëlle et Vanessa sont dans le fil (ne pas les recopier ici, dépôt
public). Impact design : la vague 1 commence par ce trio RH + directeurs,
avant les salariés.
