# Intégration EYWAI par vagues — design validé

Issu du brainstorm avec Alexandre du 18-19/08/2026, sur les priorités
d'Elsa (13/08 : « la paie c'est la priorité numéro 1 … le package paie =
bulletin + DSN + provision + banque, tout le reste est secondaire »).
Remplace `docs/strategie-integration-2026-08.md` (première version, avant
brainstorm).

## Principe retenu : deux rails en parallèle

Les utilisateurs montent à bord par vagues pendant que la paie converge
en interne. Personne n'attend personne : la paie « rejoint » chaque
société dès qu'elle tombe au centime. Elsa n'est jamais bloquante — ses
réponses élargissent le déploiement, elles ne conditionnent pas le départ.

### Rail utilisateurs

| Vague | Qui | Quoi |
| --- | --- | --- |
| **0** | Gaëlle (RH usines), Vanessa (MAJI/Zone 404), Elsa, puis les 5 directeurs de site | Activation de leurs comptes + tour des modules RH — composition donnée par Elsa le 19/08 |
| **1** | Salariés Colorplast + Comitech **à e-mail réel** (5/7 et 8/18, s'élargit au fil des réponses d'Elsa) | 🔑 Activation + ⏱ badgeage/pointages + demandes de congés (compteur masqué, voir plus bas) |
| **2** | Cartol, MBC, LEWIS | 🔑 + ⏱, plus 🗂 RH interne partout (visites médicales, titres de séjour, périodes d'essai) |
| **3** | Boîte par boîte, quand sa paie a basculé | 📄 Espace salarié (bulletins, soldes, acomptes) |

### Rail paie (interne, invisible des utilisateurs)

Double run vs Cegid : Colorplast + Comitech d'abord, puis Cartol / MBC /
LEWIS au fil de la convergence moteur, MAJI / Zone 404 en dernier (reprise
d'historique préalable — aucun bulletin en base).

## Critères de validation

- **Une vague utilisateurs est validée** quand ≥ 80 % des invités ont
  activé leur compte, un mois de badgeage concorde avec le papier, et
  Elsa donne son feu vert.
- **La paie d'une société bascule** quand, sur un même mois, les **5
  critères** sont verts :
  1. bulletins = Cegid au centime ;
  2. DSN identique à la DSN déposée (et 0 anomalie DSN-VAL) ;
  3. provision CP au centime vs l'état du cabinet ;
  4. fichier de virement (salaires + acomptes) accepté par la banque ;
  5. OD comptable au centime vs l'OD du cabinet (références de juillet
     2026 reçues le 18/08 dans `data/*/referentiel/`).

## Composants à développer

### 1. Lien d'activation (nouveau)

- Bouton « Inviter » côté RH (fiche salarié / liste), e-mail envoyé **par
  EYWAI** (jamais par Supabase) avec un lien `https://<eywai>/activation?token=…`.
- Côté serveur : `generate_link` Supabase (admin) → on garde le token, on
  envoie nous-mêmes. La page `/activation` (frontend, aux couleurs EYWAI)
  vérifie le token et fait choisir le mot de passe. Supabase invisible de
  bout en bout.
- Lien à usage unique, expiration 7 jours, ré-envoyable par la RH.
- **E-mail uniquement** : jamais d'adresse inventée (règle existante) ;
  sans e-mail réel, pas d'invitation.
- Le compte naît avec le rôle salarié scopé à sa société, via la matrice
  d'accès existante (`access_manifest`) — « bien respecter les accès ».

### 2. Interrupteurs de modules par société (nouveau)

- Généralisation du pattern du module Recrutement
  (`_ensure_module_enabled`) : un registre « modules actifs » par société.
- Backend : garde générique sur les routers concernés ; API de lecture
  pour le frontend ; menus/navigation filtrés.
- Écran d'admin (plateforme) pour allumer/éteindre par société.
- **Lancer une vague = allumer des interrupteurs**, aucune mise en prod.
- Défaut : tout éteint pour les salariés ; les écrans RH restent pilotés
  par le RBAC existant.

### 3. Congés sans compteur (nouveau, léger)

- Le salarié peut poser ses congés dès la vague 1 ; le compteur affiché
  est masqué (« solde en cours de reprise ») tant que la société n'a pas
  le drapeau **« soldes repris »**.
- Drapeau par société, activé après chargement de l'état de provision du
  cabinet.

### 4. Chargement des soldes N-1 (données, pas du dev)

Les états « provision CP » du cabinet (exercice 01→06/2026) sont arrivés
le 19/08 pour Cartol, LEWIS, Colorplast, MBC, Comitech
(`data/<societe>/compteurs/provision-cp-2026-06.pdf`). Même méthode que la
reprise Cartol de juillet : extraire les soldes N-1, charger, vérifier
nom par nom. Manquent MAJI et Zone 404.

## Dépendances côté client (élargissent, ne bloquent pas)

- E-mails réels (#1) → élargit les vagues salariés, boîte par boîte.
- Provisions MAJI/Zone 404 (#7 reliquat) → leur drapeau « soldes repris ».
- DSN de juillet + accès net-entreprises manquants (#6/#15) → rail paie.

## Hors périmètre de ce design

- La **DSN d'amorçage** (demande d'Elsa du 11/08) : chantier PAS/DSN du
  rail paie, spécifié à part.
- La reprise d'historique MAJI/Zone 404.
- Le contenu détaillé du pack 📄 Espace salarié (vague 3, à affiner quand
  la première paie bascule).
