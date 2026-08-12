---
name: qa-session
description: Session QA exploratoire d'EYWAI pilotée par Playwright MCP sur l'environnement de test — explore les modules comme un utilisateur, relève bugs fonctionnels, erreurs console/réseau et problèmes UX, produit un rapport de constats et propose les specs E2E à ajouter. À utiliser quand l'utilisateur tape /qa-session ou demande une session de QA / chasse aux bugs UI.
---

# Session QA exploratoire

## Préconditions (vérifier AVANT d'explorer)

1. **Cible = environnement de test uniquement** :
   `https://sirh-frontend-test-505040845625.europe-west1.run.app`.
   Au premier écran, vérifier le bandeau « ENVIRONNEMENT DE TEST ». Pas de
   bandeau = production → STOP immédiat.
2. Le serveur MCP `playwright` doit être disponible (déclaré dans `.mcp.json`).
   S'il ne l'est pas, demander de relancer la session ou `claude mcp list`.
3. Identifiants : compte QA de `frontend/.env.e2e` (E2E_QA_EMAIL /
   E2E_QA_PASSWORD). S'il ne se connecte pas, faire rejouer
   `scripts/qa/seed_qa_user.sql` (la resynchro l'efface).
4. Lire le dernier rapport dans `data/qa/constats/` pour ne pas re-signaler
   des constats connus.
5. **Lire `data/qa/personas.md` (obligatoire)** : la session s'explore EN
   INCARNANT le persona — Elsa côté RH, un ouvrier d'usine côté salarié —
   avec sa grille de lecture (les 6 réflexes de détection).
6. **Lire la section du `data/qa/registre-elsa.md`** correspondant aux
   modules visés : chaque signalement ⚪/🔴 du module doit être REJOUÉ
   pendant la session (numéro cité dans le rapport s'il se reproduit) ;
   un 🟢 rejoué sans problème est annoté « re-testé OK <date> » dans le
   registre.

## Interdits absolus

- Le bouton « Resynchroniser depuis la prod » du bandeau : ne JAMAIS cliquer.
- Tout dépôt/envoi vers l'extérieur : dépôt DSN, signature électronique,
  envoi d'e-mails en masse (verrouillés côté test, mais ne pas s'y frotter).
- Les suppressions en masse. Les créations/modifications unitaires sont
  permises (c'est un environnement d'essai) mais notées dans le rapport,
  section « Traces laissées », pour prévenir les autres testeurs.

## Déroulé

1. **Cadrage** : choisir 2-4 modules (avec l'utilisateur s'il a précisé, sinon
   prioriser : paie > absences > collaborateurs > exports > badgeuse), en
   s'appuyant sur la carte des routes dans `docs/qa/strategie-qa.md`.
2. **Exploration par module**, en incarnant le persona : dérouler ses vraies
   tâches dans son vrai ordre (côté RH : le cycle de paie de personas.md —
   pointages → calendriers → variables → anomalies → génération → bulletins
   → exports ; côté salarié : login → bulletin → congés → acompte), sur des
   sociétés contrastées (Cartol, Colorplast, MAJI). Formulaires : soumettre
   vide, valeurs limites, caractères spéciaux. À chaque page, appliquer les
   6 réflexes d'Elsa : blocage muet, clic sans effet, état affiché faux,
   blocage/alerte inversés, document non professionnel, écran non rafraîchi
   — plus erreurs console, 4xx inattendus, 5xx, chargements infinis,
   placeholders. Tout libellé qu'Elsa devrait demander « c'est-à-dire ? »
   est un constat.
3. **Reproduction** : tout constat doit être reproduit une seconde fois avant
   d'être consigné, avec le chemin exact.
4. **Rapport** : écrire `data/qa/constats/AAAA-MM-JJ.md` — sous `data/`
   (gitignoré) et JAMAIS sous `docs/` : le dépôt est public et les constats
   contiennent des noms réels et des captures de données de paie. Si un
   constat doit être cité dans un fichier versionné (doc, commit, spec),
   l'anonymiser (« un salarié de <société> », jamais le nom) :
   - un tableau par sévérité : bloquant / majeur / mineur / cosmétique ;
   - pour chaque constat : module, étapes de reproduction, attendu vs obtenu,
     capture (chemin du screenshot), erreur console/réseau associée ;
   - section « Traces laissées » (données créées/modifiées pendant la session).
5. **Conversion en tests** : proposer pour chaque constat majeur+ une spec
   Playwright dans `frontend/e2e/`, afin que le bug corrigé ne revienne pas.
   Ne les écrire qu'après accord.

## Restitution

Réponse courte : nombre de constats par sévérité, les 3 plus importants en
une ligne chacun, lien vers le rapport. Le détail vit dans le fichier.
