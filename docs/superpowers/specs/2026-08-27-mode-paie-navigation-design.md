# Mode paie — navigation réduite pour le premier contact

**Date** : 2026-08-27
**Point** : préparation du point paye du 28/08/2026 (`docs/afaire.md` #18)
**Statut** : validé

## Constat

**Aucun utilisateur côté client n'a jamais ouvert l'application.** Les identifiants
provisoires ont été établis le 22/07/2026 (`Vente SIRH Docs/EYWAI_acces_provisoires.xlsx`,
8 comptes) et n'ont jamais été transmis — c'est le point #2, toujours ouvert au 07/08. La
production contient pourtant 246 salariés, des bulletins, 182 taux PAS et sept sociétés
paramétrées : les données sont là, les utilisateurs ne sont jamais venus.

Le premier contact est le **vendredi 28/08/2026** : faire tourner une paie de bout en bout
sur Colorplast (7 salariés) devant Gaëlle Bouali, sur l'environnement de test.

La sidebar RH expose aujourd'hui **48 entrées** réparties en trois sections repliables
(`RH_TEAM_GROUPS`, `RH_GESTION_GROUPS`, `RH_PAIE_GROUPS` dans
`frontend/src/components/ui/app-sidebar.tsx`). Une partie n'est pas alimentée, et pas par
accident — ces écrans attendent des données client qui ne sont pas arrivées :

| Écran | État en base | Point |
|---|---|---|
| CSE & Dialogue social | 0 mandat enregistré | #11 |
| Entretiens | 0 entretien, aucune société réglée | #25 |
| Périodes d'essai | 0 période saisie | #28 |
| Congés (fractionnement) | aucune société paramétrée | #19 |
| Badgeuse / pointages | 5 sociétés sur 7 sans règle de pause | #27 |

Ouvrir ces écrans à quelqu'un qui découvre l'outil ne montre pas un produit riche : ça
montre un produit vide.

## Décision

**Ne laisser accessible que la paie et ce dont la paie a besoin. Le reste est retiré de la
navigation et inaccessible par l'URL.**

Réduire plutôt que griser : griser fonctionne pour trois ou quatre éléments dans une liste
courte, pas pour 29 sur 48. L'œil parcourt quand même la liste, chaque ligne morte est une
question en suspens, et le résultat ressemble à une application cassée. Le contre-argument
habituel — « on a acheté un SIRH complet, où est le reste ? » — ne s'applique pas : on ne
peut pas regretter ce qu'on n'a jamais vu. La feuille de route des modules à venir part
dans le document de suivi, pas dans l'interface.

**Le mode s'applique à tous les comptes client**, administrateurs Vanessa Amate et Gérault
Verny compris. Seuls les comptes EYWAI conservent la navigation complète, pour paramétrer
et vérifier.

## Périmètre : 19 entrées sur 48

Le critère est fonctionnel, pas esthétique : **tout ce sans quoi une paie mensuelle ne peut
pas être produite et sortie reste accessible.** Le périmètre est calé sur une paie
quelconque des sept sociétés, pas sur le seul cas de Colorplast en juillet — sinon le mode
casserait dès la deuxième société.

| Entrée | Route | Pourquoi c'est nécessaire |
|---|---|---|
| Tableau de bord | `/` | point d'entrée |
| Collaborateurs | `/employees` | contrat, taux, éléments permanents du bulletin |
| Calendrier | `/schedules` | **bloque le lancement** tant qu'il reste des éléments |
| Congés & absences | `/leaves` | **bloque le lancement** |
| Suivi IJSS / CPAM | `/suivi-ijss` | subrogation ; 13 arrêts chez Cartol, 7 chez MBC, 6 chez Comitech |
| Temps de travail & HS | `/suivi-temps-travail` | heures à valider |
| Contingent HS | `/suivi-contingent-hs` | plafonne les heures supplémentaires payées |
| Modulation | `/suivi-modulation` | alimente le bulletin |
| Suivi CET | `/suivi-cet` | alimente le bulletin |
| Notes de frais | `/expenses` | **bloque le lancement** |
| Primes | `/saisies` | saisies du mois |
| Saisies sur salaire | `/salary-seizures` | ligne réelle : `42700000` à 1 641,83 € sur l'OD MAJI de juillet |
| Avances & acomptes | `/salary-advances` | ligne réelle : `42500000` à 2 500 € sur l'OD MAJI de juillet |
| Prêts employeur | `/employee-loans` | même nature de retenue |
| Simulation paie | `/simulation` | contrôle avant validation |
| Suivi des taux | `/rates` | barèmes de cotisations ; un taux faux fausse le bulletin |
| Prélèvement à la source | `/taux-pas` | sans taux connu, le salarié reçoit la grille par défaut |
| Exports | `/exports` | OD comptable (#26), DSN (#20), virement (#16) — sans lui rien ne sort |
| Paie | `/payroll` | production des bulletins |

**Vérification du garde-fou** : `useCanLaunchPayroll` conditionne le lancement à zéro
élément en attente sur `/schedules`, `/leaves` et `/expenses`. Les trois sont dans le
périmètre : la checklist de préflight reste entièrement praticable.

### Ce qui est retiré — 29 entrées

| Retiré | Raison |
|---|---|
| Recrutement, Onboarding, Départs, Périodes d'essai, Équipes | hors production de paie |
| Documents, Titres de séjour | hors production de paie |
| Badgeuse, Planning, Calendriers (section Gestion), Entretiens, Formation, Augmentations, Suivi médical, CSE | hors production de paie, et modules non alimentés |
| Analytics Team, Analytics Gestion, Analytics Paie | lecture, pas production |
| Gestion des utilisateurs, Mon entreprise | administration |
| Validations, Congés à valider, CET à valider | retirées du menu RH, mais **routes laissées atteignables** — voir ci-dessous |

La section **Effectifs** disparaît entièrement sauf Collaborateurs, et la section
**Gestion** disparaît entièrement. Il ne reste que Tableau de bord, Collaborateurs et la
section Paie complète.

### Les files de validation manager restent atteignables

`/approvals`, `/leave-requests` et `/cet-requests` ne figurent pas dans le menu RH — elles
vivent dans `menuItems.manager`, que le filtre par section ne touche pas. Mais leurs
**routes** restent ouvertes, car elles sont le transport d'actions qui sont, elles, dans le
périmètre : valider un bulletin, approuver une note de frais ou une avance.

C'est le seul rôle des cinq directeurs (Eric Noble, Damien Faucher, Lucas Chambert, Michael
Francony, Baptiste Droz-Vincent), dont le rôle de base est `custom`. Les couper reviendrait
à les priver de leur seule fonction dans l'outil.

La limite est nette : on ouvre le **transport** d'une action du périmètre, pas un module.
`/planning`, `/formation` et `/analytics` figurent aussi dans les droits des directeurs et
restent bloqués — pour eux comme pour les autres, c'est l'effet voulu de la décision, pas un
défaut.

## Alertes

**Les alertes des écrans retirés sont supprimées, pas rendues cliquables.** Une alerte qui
mène vers une page absente du menu est incohérente, et une alerte sur laquelle on ne peut
pas agir est pire qu'une absence d'alerte.

`lib/rhPendingTasks.ts` construit chaque tâche avec son URL de destination. Le même
filtrage par liste blanche s'y applique. Les tâches restantes pointent toutes vers une page
atteignable : `/leaves`, `/expenses`, `/employees`, `/employees?alert=deadlines`,
`/schedules`, `/suivi-temps-travail`, `/suivi-cet`, `/rates`. Disparaissent :
`/medical-follow-up`, `/residence-permits`, `/annual-reviews`, `/recruitment`,
`/onboarding`, `/company`.

**Conséquence assumée, à énoncer au client.** Des échéances à valeur légale cessent d'être
signalées par EYWAI : 41 titres de séjour avec leur date d'expiration, les visites
médicales de reprise, les entretiens professionnels. Ce n'est pas une régression — personne
côté client n'a jamais ouvert l'application, donc aucune de ces alertes n'a jamais été lue,
et la veille reste là où elle est aujourd'hui. Mais c'est à dire explicitement vendredi :
tant que ces modules ne sont pas ouverts, EYWAI ne surveille pas ces échéances. Les alertes
reviennent avec leur module.

## Version démo — pour le 28/08

Objectif : montrer le menu réduit vendredi, sur l'environnement de test uniquement. Pas de
réglage société, pas d'écran d'administration, pas de migration.

**1. Une source unique de vérité** — `frontend/src/lib/payrollFocus.ts` :

- `PAYROLL_FOCUS_NAV_URLS` : les 19 routes du tableau ci-dessus.
- `PAYROLL_FOCUS_ROUTE_PREFIXES` : la liste précédente **plus les sous-routes** atteintes
  depuis ces écrans — `/employees/:employeeId`, `/payroll/:employeeId`,
  `/payslips/:payslipId/edit`. Distinguer les deux listes est ce qui évite de casser la
  navigation interne : une fiche salarié n'est pas une entrée de menu, mais elle doit rester
  accessible.
- `isPayrollFocusAllowed(path): boolean`, en correspondance de préfixe.
- `restrictToPayrollFocus(groups)` : filtre les `items` de chaque groupe et supprime les
  groupes devenus vides. Fonction pure, testable sans React.

**Piège identifié** : `/schedules` figure **deux fois** dans la sidebar — « Calendriers »
dans `RH_GESTION_SUIVI_RH_ITEMS` et « Calendrier » dans le parcours paie de
`RH_PAIE_GROUPS`, même URL. Un filtre par URL seule garderait les deux et laisserait la
section Gestion vivante avec une entrée orpheline. Le filtre s'applique donc **par
section**, pas globalement :

| Section | Traitement |
|---|---|
| `RH_TEAM_GROUPS` | ne garder que Collaborateurs |
| `RH_GESTION_GROUPS` | supprimée entièrement |
| `RH_PAIE_GROUPS` | tout garder sauf Analytics Paie |

`restrictToPayrollFocus` prend donc la section en paramètre. `PAYROLL_FOCUS_NAV_URLS` reste
la source de vérité pour l'ensemble, et sert d'assertion de test : la navigation produite
doit contenir exactement ces 19 URL, sans doublon.
- `usePayrollFocus(): boolean` : actif **sauf** si `user.is_super_admin === true` ou si
  `user.email` figure dans `PAYROLL_FOCUS_BYPASS_EMAILS` (`alexandreandre2004@gmail.com`).
  La double condition évite de dépendre d'un drapeau dont la valeur en base n'a pas été
  vérifiée.

**2. Navigation** — `components/ui/app-sidebar.tsx` : trois `useMemo` produisant
`teamGroups`, `gestionGroups`, `paieGroups`. `rhGestionGroups` existe déjà sous cette forme
et sert de modèle. Remplacer les références directes aux trois constantes — elles sont
consommées à douze endroits (navigation repliée, pastilles de tâches, détection de section
active, ouverture automatique). Le filtre s'applique une fois et se propage : une section
vidée ne s'affiche plus et ne compte plus de tâches.

**3. Accessibilité réelle** — `App.tsx` : un garde placé sur le seul bloc `<Routes>` de la
zone RH (lignes ~150-260), qui redirige vers `/` quand `isPayrollFocusAllowed` est faux.
Le bloc `employeeCollaboratorRoutes` et les routes manager et admin ne sont pas touchés.

**4. Alertes** — `lib/rhPendingTasks.ts` : filtrer la liste produite sur
`isPayrollFocusAllowed(task.url)`.

### Recette avant vendredi

- Compte `gaelle.bouali` : 19 entrées, sections Team et Gestion absentes, parcours complet
  jusqu'à la validation d'un bulletin Colorplast **et** la sortie de l'OD comptable.
- Compte `alexandreandre2004@gmail.com` : navigation inchangée, 48 entrées.
- Compte `vanessa.amate` : 19 entrées, aucune alerte pointant vers un écran retiré.
- Saisie directe de `/cse` dans la barre d'adresse : redirection vers `/`.
- Saisie directe de `/employees/<id>` : la fiche s'ouvre.
- Espace salarié et espace manager : inchangés.
- Sidebar repliée : mêmes entrées que dépliée.

### Prérequis non technique, bloquant

Gaëlle Bouali est RH sur **MAJI et Zone 404 uniquement**. Sans Colorplast ajoutée à son
compte de test, elle ne peut pas exécuter la séquence, quel que soit le menu. À faire avant
le call.

## Version produit — après le 28/08

Le design durable se conçoit une fois qu'on aura vu où Gaëlle bute réellement. Direction
retenue, à confirmer par l'usage :

- Le périmètre devient un **réglage par société** (liste des modules ouverts), et non plus
  une constante. Une société bascule quand elle bascule.
- Le commutateur vit dans l'**espace admin EYWAI** (`pages/admin/eywai`), pas dans les
  réglages société : le client ne le rouvre pas seul.
- L'ouverture se fait **module par module**, avec sa condition d'ouverture consignée. C'est
  la contrepartie de la promesse faite au client : un onglet s'ouvre le jour où son
  paramétrage est vrai.
- Deuxième vague pressentie, une fois la première paie bouclée : Documents, Départs,
  Périodes d'essai, Analytics paie.

## Hors périmètre

- **Aucune restriction côté serveur.** Le garde est côté client : il retire la navigation et
  bloque l'accès par URL dans l'application, il ne protège pas l'API. Ce lot cadre
  l'attention, il ne remplace pas le système de permissions, qui est déjà en place et
  correct (catégories × actions, périmètre entreprise / équipes / exceptions nominatives).
- Aucune modification de l'espace salarié, de l'espace manager ni de l'espace admin.
- **Aucun changement sur les droits d'action.** Ce que chacun a le droit de faire reste
  exactement ce qu'il a le droit de faire aujourd'hui ; seule la navigation change.
