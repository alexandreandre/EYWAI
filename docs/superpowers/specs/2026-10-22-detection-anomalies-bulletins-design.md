# Détection d'anomalies sur les bulletins générés

Plan de technologie. Rien n'est à construire tant que le PDF du mois n'est pas en place, et tant que ce plan n'a pas été repris comme chantier.

Date : 22 octobre 2026.

## But

Sur la vision « tous les bulletins du mois », la personne qui prépare la paie voit ce que les règles ont trouvé, salarié par salarié, et peut demander une explication en français. L'explication ne crée aucun chiffre. Elle reformule des constats déjà calculés.

Le détecteur regarde les bulletins que Martine a générés (`payslip_data`). Il ne lit pas les PDF Quadra historiques, et il ne relit pas les pixels du PDF affiché.

## Ce qui existe déjà

Trois couches tournent sans modèle. Elles restent la source des anomalies. Le modèle vient après, et seulement pour écrire.

### 1. Avant la génération — la revue pré-paie

`backend/app/modules/payroll/application/preflight_anomalies.py`, exposée par `GET /preflight-anomalies`.

Elle regarde le mois avant le calcul : calendrier incomplet, heures à saisir, écart pointage / prévu, heures posées sur un arrêt, revues d'heures supplémentaires en attente. Chaque anomalie a un type, une sévérité (`bloquant` ou non), un statut, et peut être justifiée ou acquittée. Ce n'est pas un contrôle de bulletin : le bulletin n'existe pas encore.

### 2. Pendant le calcul — les contrôles du moteur

`backend/app/modules/payroll/engine/bulletin.py` appelle `controles_convention.py` et range le résultat dans `payslip_data.alertes_baremes`. Le maintien range ses messages dans `payslip_data.synthese_net.alertes_maintien`.

Déjà couvert, entre autres : minimum conventionnel, salaire d'apprenti, heures complémentaires, prime d'ancienneté, net supérieur au brut, net négatif. L'écran du bulletin les affiche (`PayslipAlertsBanner`). Certaines alertes sont marquées non actionnables (prime d'ancienneté non applicable, IJSS versées directement).

Ces alertes sont un résultat du calcul. Elles disent « le moteur a vu ceci en calculant ». Elles ne redisent pas « le bulletin écrit est cohérent avec ses propres lignes ».

### 3. Après le calcul — la comparaison N / N-1

`backend/app/modules/payslips/domain/comparison_engine.py`. Fonction pure, sans base, sur deux `payslip_data`.

| Règle | Seuil | Niveau |
|---|---|---|
| R01 | Brut total varie de plus de 5 % (sans changement de contrat) | Avertissement |
| R02 | Brut varie de 1 à 5 % | Avertissement |
| R03 | Net à payer varie de plus de 10 % | Critique |
| R04 | Net varie de 5 à 10 % | Avertissement |
| R05 | Cotisations salariales varient de plus de 8 % | Avertissement |
| R06 | Une ligne de brut du bulletin de référence a disparu | Avertissement |
| R07 | Une ligne de brut est nouvelle | Info |
| R08 | Heures travaillées sous 50 % du volume contractuel (hors forfait jour) | Critique |
| R09 | Plus de 20 h supplémentaires | Info |
| R10 | Net en baisse sur trois mois consécutifs | Avertissement |
| R12 | Pas de bulletin N-1 validé | Info |

R11 est retirée. Seules ces règles s'acquittent ou s'ignorent (`POST /api/payslips/{id}/alerts/{rule_id}/acquit` et `/ignore`), avec une trace d'audit. Le statut vit dans `payslip_data.alerts_status`.

La liste « Par mois » (`frontend/src/features/payroll/utils/revueDuMois.ts`) reprend une partie de ces seuils sans rappeler le moteur : net au-delà de 10 % (R03), plus de 20 h sup (R09), net négatif, bulletin périmé, bulletin encore au bac à sable. Une alerte acquittée ne met plus la ligne en orange.

### 4. L'assistant déjà en place — il ne contrôle pas les bulletins

Le copilot (`backend/app/modules/copilot`) interroge les données RH par un catalogue fermé d'outils (`domain/tools.py`) : effectif, recherche, synthèse de paie, absences, planning, indicateurs, et trois outils nominatifs bornés par les droits. Le modèle ne choisit pas l'entreprise, n'envoie pas de SQL, ne passe pas d'identifiants internes. Au plus cinq outils par tour. Les identifiants sont retirés avant l'envoi (`_sanitize_for_llm`). Chaque tour est journalisé dans `copilot_interactions`.

Les modèles sont dans `backend/app/shared/infrastructure/ai/models.py`, via OpenRouter : Gemini Flash Lite pour le routage, Gemini 3 Flash pour la synthèse et les conventions. Le banc d'essai est `backend/scripts/eval_assistant_rh.py`.

Cet assistant répond à des questions. Il ne parcourt pas les lignes d'un bulletin, et il ne doit pas le faire en l'état : un outil de plus du type « lis ce bulletin et dis-moi ce qui cloche » reproduirait l'erreur de la page déjà envoyée sur les bulletins Quadra, où un seul des deux effets avait été additionné et le sens du montant inversé.

## Principe

Une anomalie de bulletin est un écart entre deux calculs, les deux faits par notre code.

1. Le bulletin généré porte des lignes et des totaux dans `payslip_data`.
2. La même fonction que le moteur (taux, réduction générale, net imposable, somme des lignes) est rejouée sur ces lignes.
3. L'écart au centime, dans un sens explicite, est l'anomalie.
4. Le modèle reçoit la liste déjà chiffrée. Il écrit le français. S'il introduit un nombre qui n'est pas dans la liste, la phrase est jetée et on affiche le message de la règle.

Le PDF du mois sert à l'œil humain. Le détecteur ne l'ouvre pas.

## Ce que les règles actuelles ne voient pas

La comparaison N / N-1 voit un changement. Elle ne voit pas un mois faux qui ressemble au mois d'avant. Les contrôles du moteur voient ce qu'ils ont décidé pendant le calcul. Ils ne rejouent pas le bulletin comme une pièce à vérifier.

Les familles à ajouter, toutes déterministes, toutes rejouées sur `payslip_data` :

**Cohérence interne.** Chaque ligne de cotisation : montant = base × taux, au centime. Somme des lignes de brut = salaire brut. Somme des retenues et des parts patronales = les totaux imprimés. Net à payer = brut − retenues salariales − acompte + rappels prévus par la formule du moteur. Net imposable = la formule du moteur, part patronale de frais de santé comprise. Prélèvement à la source = net imposable × taux, au centime.

**Taux du millésime.** Maladie et famille patronales sont celles de l'année en cours pour le profil du salarié (taux pleins, ou l'exonération que sa fiche porte vraiment). Un bulletin qui garderait les taux réduits de l'année précédente, sans code d'exonération, est une anomalie. La réduction générale, quand le coefficient de `calcul_reduction_generale.py` est positif, doit être présente et égale au centime à ce coefficient appliqué au brut, avec le SMIC que le moteur a retenu (SMIC du 1er janvier, heures supplémentaires à 12,02 €, prorata). Un SMIC horaire différent est une anomalie, même si le mois d'après « a l'air » juste.

**Le salarié seul dans le mois.** On groupe les bulletins du mois par profil comparable (CDD ou non, temps partiel ou non, même société). Si un seul bulletin n'a pas la réduction ou garde d'anciens taux alors que les autres du même profil les ont, c'est lui qu'on signale. C'est le cas d'une fiche de cotisations restée sur l'ancien paramétrage.

**Le mois suivant ne répare pas tout seul.** Pour une anomalie de janvier encore ouverte, on regarde si un mois ultérieur porte une ligne de rappel ou un cumul qui reprend le mois fautif. Sans cette ligne, l'anomalie reste ouverte. On ne conclut pas « ça se rattrape dans l'année » sans la ligne.

Ces règles appellent les fonctions du moteur. Elles n'en recopient pas les formules. Un changement de taux se fait une fois, dans le barème, et les deux chemins suivent.

## Forme d'une anomalie

Même objet que `PayslipAlert`, pour réutiliser l'acquittement.

- `rule_id` : nouvelle série `B01`, `B02`, … (B pour bulletin). On ne réutilise pas R01–R12, qui comparent au mois précédent.
- `level` : `CRITIQUE` si l'écart change le net ou les cotisations dues ; `AVERTISSEMENT` si c'est une cohérence de ligne sans effet de net ; `INFO` si c'est le salarié seul dans le mois et que l'écart est nul au centime près mais le profil diverge.
- `message` : une phrase avec les deux montants et le sens (trop payé, trop bas, ligne absente).
- `field` : la clé de `payslip_data` ou le libellé de ligne.
- `value_n`, `value_n1` : le montant du bulletin et le montant rejoué. `delta_pct` ou, mieux, un `delta_eur` au centime. Le sens est le signe : positif = le bulletin est au-dessus du rejeu.
- `status` : `active`, `acquittee`, `ignoree`, mêmes routes que les règles R, étendues à la série B dans `REGLES_CONNUES`.

L'acquittement est une décision de la personne, datée, commentée, auditée. Il ne modifie pas le bulletin.

## Où le modèle intervient

Un seul appel, au clic « Expliquer le mois ». Pas à l'ouverture de la page, pas bulletin par bulletin.

Entrée, après `_sanitize_for_llm` : le mois, la société sous son nom, et la liste des anomalies actives (règle, niveau, message, montants). Pas de NIR, pas d'IBAN, pas d'adresse, pas de `company_id`, pas le PDF.

Modèle : une constante nouvelle dans `models.py`, `MODEL_REVUE_BULLETINS`, sur la même famille que `MODEL_COPILOT_SYNTHESIS` (Gemini 3 Flash via OpenRouter, `chat_completions_create`). Température 0. Un schéma de sortie imposé : un résumé du mois, puis une phrase par salarié qui a au moins une anomalie.

Garde : chaque nombre présent dans la réponse doit déjà figurer dans l'entrée. Sinon la phrase est écartée et l'écran montre le `message` de la règle. Le modèle n'a pas le droit d'ajouter une anomalie, d'en fusionner deux, ni de dire qu'un mois suivant rattrape si aucune règle ne l'a écrit.

Journal : même table que le copilot, ou une table sœur `revue_bulletin_explications` (société, mois, utilisateur, nombre d'anomalies envoyées, latence, modèle). On ne stocke pas le `payslip_data`.

Droits : la route relit les bulletins avec le `company_id` du serveur et le périmètre de l'utilisateur, comme les outils nominatifs du copilot. Un RH d'équipe ne reçoit que les salariés de son périmètre.

## L'écran, sur le PDF du mois

Le PDF du mois (bouton sur Gestion de la paie, onglet Par mois) reste le document. À côté, un rail « À regarder » :

- construit sans modèle, dès l'ouverture, en rejouant les règles B et en relisant les alertes moteur et les règles R encore actives ;
- groupé par salarié, dans le même ordre alphabétique que le PDF ;
- un clic sur le nom va au signet du PDF ;
- les critiques d'abord ;
- le bouton « Expliquer le mois » n'apparaît que s'il y a au moins une anomalie active. Il remplit le résumé et les phrases. Tant qu'on n'a pas cliqué, on ne paie pas d'appel.

Une anomalie acquittée sort du rail. Elle reste consultable dans le filtre « y compris acquittées ».

## Comment on sait que c'est juste

Des `payslip_data` anonymisés, en fixtures, jamais de bulletin réel dans `tests/`.

Pour chaque règle B : un bulletin qui doit la lever, un bulletin juste qui ne doit pas la lever, et le cas limite au centime (1 centime d'écart ne lève pas, 2 centimes lèvent si la règle est au centime).

Trois formes, inspirées de constats déjà faits sur d'anciens bulletins, réécrites en JSON anonyme :

- taux de l'année précédente encore appliqués, réduction générale absente, alors que le rejeu donne une réduction plus grande que le complément de taux : le sens au net est « trop payé », pas « cotisations manquantes » ;
- un seul contrat du mois sans la réduction, les autres du même profil l'ayant ;
- part patronale de frais de santé présente en ligne et absente du net imposable, puis un mois suivant qui réintègre le mois courant sans reprendre les mois d'avant.

Le banc d'essai du modèle est séparé, sur le modèle de `eval_assistant_rh.py`. On lui donne des listes d'anomalies figées. On vérifie qu'il ne change aucun montant, qu'il ne conclut pas un rattrapage non fourni, et qu'il nomme le bon salarié. Un échec de banc ne bloque pas l'affichage des règles : les règles s'affichent même si l'explication est refusée par la garde.

## Ordre, le jour où on le construit

1. Règles B pures, à côté de `comparison_engine.py`, avec les fixtures. Aucune route, aucun modèle.
2. Route de lecture du mois : règles B + alertes moteur + règles R actives, filtrées par société et périmètre. Le rail s'en sert. Le PDF du mois doit déjà exister.
3. Acquittement de la série B sur les routes d'alerte existantes.
4. Bouton « Expliquer le mois », garde sur les nombres, journal.
5. Banc d'essai du modèle.

Chaque étape s'arrête sur des tests verts. On ne commence pas par l'appel au modèle.

## Hors de ce plan

- Lire un PDF, Quadra ou Martine, pour y chercher des anomalies.
- Laisser le modèle recalculer un taux, une réduction, un net.
- Corriger le bulletin tout seul. La correction reste le chemin déjà prévu : variables du mois, ou la correction à la main quand elle existera.
- Étendre le copilot avec un outil « audite ce bulletin ».
- Mélanger la revue pré-paie (avant le calcul) et cette revue (après le calcul). Les deux restent deux moments.
