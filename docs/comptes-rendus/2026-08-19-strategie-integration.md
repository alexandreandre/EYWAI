# Stratégie d'intégration EYWAI — août 2026

> **Remplacé le 19/08** par le design validé en brainstorm :
> `docs/superpowers/specs/2026-08-19-integration-par-vagues-design.md`.

Réponse aux priorités d'Elsa (WhatsApp, 13/08) : « la paie c'est la priorité
numéro 1 … le package paie = bulletin + DSN + provision + banque. Tout le
reste c'est vraiment secondaire : 1) recrutement, 2) visite médicale,
3) CSE, 4) entretiens. »

## Principe

On intègre **société par société**, pas fonctionnalité par fonctionnalité
partout à la fois. Une société pilote valide le package paie de bout en
bout en doublon de Cegid ; tant que les quatre critères ne sont pas verts,
Cegid fait foi. Une fois le pilote validé, on déploie par vagues.

Les accès se font par **lien d'activation** envoyé à chaque salarié (le
tableau d'identifiants est abandonné).

## Étape 0 — Prérequis transverses (en cours)

| Prérequis | Sert à | État |
| --- | --- | --- |
| Adresses e-mail réelles | liens d'activation + envoi des bulletins | 148/246 manquantes — demandé à Elsa (question #1) |
| Accès net-entreprises | dépôt DSN + retours de taux PAS | 3 sociétés sur 7 reçues ; Cartol, LEWIS, MAJI, Zone 404 chez Marie |
| DSN de juillet | backtests + taux PAS à jour | toujours pas déposées sur le Drive |

## Étape 1 — Le package paie (priorité n° 1)

Périmètre : **bulletin + DSN + provision CP + banque** (virements salaires
et acomptes).

**Définition de « intégré »** — les 4 critères, sur un même mois M :

1. **Bulletins** : EYWAI = Cegid au centime pour tous les salariés (backtest).
2. **DSN** : fichier EYWAI à 0 anomalie DSN-VAL et identique à la DSN
   déposée par Cegid.
3. **Provision CP** : au centime contre l'état du cabinet.
4. **Banque** : fichier de virement (salaires + acomptes) accepté par la
   banque.

**Pilote : Colorplast.** C'est la société la plus proche du vert partout :
bulletins au centime sur mai (7/7), DSN à 0 anomalie DSN-VAL, OD comptable
au centime, 5 e-mails réels sur 7 salariés (2 à récupérer seulement), accès
net-entreprises reçu, badgeuse déjà en double run.

Déroulé du pilote : 1 à 2 mois de **double run** (EYWAI en parallèle de
Cegid, comparaison mensuelle sur les 4 critères), puis bascule.

**Vague 2** — dans l'ordre de convergence des backtests : Comitech, puis
Cartol, MBC et LEWIS. **Vague 3** — MAJI et Zone 404 (aucun bulletin en
base à ce jour : reprise d'historique à faire d'abord).

## Étapes suivantes (secondaire, dans l'ordre d'Elsa)

1. **Recrutement** — testé comme un flux de paie : embauche → contrat →
   **DSN d'amorçage** (point ajouté par Elsa le 11/08 : obtenir le taux PAS
   du nouvel entrant) → premier bulletin. C'est la jonction
   recrutement→paie qu'Elsa veut vérifier.
2. **Visite médicale** — fonctionnel livré (suivi, case aménagement de
   poste) ; il ne reste qu'à former et activer.
3. **CSE** — outil de reprise prêt ; bloqué par les PV d'élections
   (dates, suppléants, collèges) côté client.
4. **Entretiens** — campagnes par société prêtes et vérifiées à blanc ;
   bloqué par l'arbitrage du périmètre MBC (58 vs 75).

## Règles du jeu pendant l'intégration

- Aucune bascule sans les 4 critères verts sur le mois précédent.
- Pendant le double run, Cegid reste la référence : aucun document EYWAI
  n'est envoyé aux salariés ni aux organismes.
- Chaque vague démarre seulement quand la précédente est stabilisée.
