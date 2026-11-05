# Heures de récupération (repos compensateur de remplacement)

Date : 05/11/2026. Déclencheur : Elsa demande si les heures de récup des non-cadres de MAJI sont prises en compte. Réponse vérifiée le jour même : non. Quadra les écrit en lignes de texte sur ses bulletins (heures acquises, heures prises avec leur date, solde) ; Martine n'en suit aucune.

Pas de brainstorming : chaque décision ci-dessous est tranchée selon notre recommandation et rattachée à son texte. Les citations mot pour mot sont dans `data/_sources/heures-sup/` (hors git) : `recuperation-lu-2026-11-05.md` (relu le 05/11 par curl) et `repos-remplacement-paye-regimes-hs-lu-2026-11-03.md`.

L'inventaire nominatif des compteurs que Quadra affiche, société par société, est dans `data/_rapports/2026-11-05-inventaire-compteurs-repos.md` (hors git, noms de salariés).

## 1. Le droit

| Règle | Texte |
|---|---|
| Une heure sup ouvre droit à une majoration **ou** à un repos compensateur équivalent. | C. trav. L3121-28 |
| Le remplacement porte sur le paiement des heures **et des majorations** : le repos est « équivalent ». Une heure à 25 % donne 1 h 15 de repos ; une heure à 50 % donne 1 h 30. Le Code dit « équivalent » ; le chiffre est écrit dans les fiches officielles (Code du travail numérique : « chaque heure majorée à 25 % ouvre droit à 1h15 de repos » ; ministère : une heure à 150 % « peut être remplacé[e] par un repos d'une durée d'1h30 » ; service-public F2391 : « équivalente à la rémunération majorée »). | L3121-28, L3121-33 II 2°, L3121-37 |
| Taux à défaut d'accord : 25 % pour les 8 premières heures, 50 % au-delà. | L3121-36 |
| Les heures compensées par un repos équivalent ne s'imputent pas sur le contingent annuel. | L3121-30, al. 3 |
| **Sans accord collectif** : dans une entreprise sans délégué syndical, l'employeur peut mettre en place le remplacement, à condition que le CSE, s'il existe, ne s'y oppose pas. Il fixe aussi les modalités d'attribution et de prise, après avis du CSE. | L3121-37 |
| Le salarié est informé des heures de repos compensateur de remplacement portées à son crédit par un document annexé au bulletin ; dès 7 heures, ce document notifie l'ouverture du droit et l'obligation de le prendre dans un délai maximum de deux mois. C'est la seule règle réglementaire du repos de remplacement à défaut d'accord. | D3171-11 (annexe électronique possible : D3171-15) |
| Les règles de prise D3121-17 à D3121-23 (demi-journée au choix, demande une semaine avant, report limité, indemnité de fin de contrat) visent la seule **contrepartie obligatoire en repos**, pas le repos de remplacement. Martine les prend comme réglages par défaut raisonnables, pas comme obligations. | D3121-17 à D3121-23 |
| Les mentions obligatoires du bulletin ne comprennent aucun solde de repos. | R3243-1 |
| Une heure mise en repos (puis payée faute d'être prise) n'a ni la réduction salariale, ni la déduction patronale, ni l'exonération d'impôt ; une heure payée directement les garde. | BOSS, rubrique heures supplémentaires (§ 220-230) ; BOFiP BOI-RSA-CHAMP-20-50-20-40 |

**Relu le 05/11 par curl** sur code.travail.gouv.fr et service-public.fr : texte et date identiques aux copies du 02/11. Deux pages ne se sont pas ouvertes ce jour-là : le BOSS (connexion refusée, la citation est celle lue le 03/11) et Légifrance (page Cloudflare ; L3121-37 lu sur code.travail.gouv.fr).

**Ce que la loi permet aux sept sociétés.** Aucune n'a d'accord sur le temps de travail (Elsa, 02/11). Le repos de remplacement reste possible par décision de l'employeur (L3121-37), à deux conditions que Martine ne peut pas connaître : pas de délégué syndical ; un CSE, s'il existe, qui ne s'y oppose pas. **On ne bloque pas** : le réglage dit ces deux conditions au moment où la RH l'active, et l'activation vaut confirmation (une question, posée une fois). Les modalités de prise (délai, demi-journée) restent celles que l'employeur fixe ; Martine applique la mention légale des deux mois dès 7 heures (D3171-11).

**Sans CSE**, le texte n'impose aucune condition ni aucune forme ; les modalités de prise sont fixées par l'employeur (lecture de L3121-37 al. 2, qui ne prévoit que l'avis du CSE quand il existe).

**Plasturgie (IDCC 292 : Colorplast, Comitech).** La fiche du Code du travail numérique indique que la convention prévoit un repos de remplacement pour les non-cadres et un délai de prise de 2 à 6 mois. Le texte de la convention n'a pas pu être ouvert (Légifrance fermé ce jour-là) : à lire avant d'activer le compteur chez ces deux sociétés. Martine imprime la mention légale des deux mois (D3171-11, « à défaut de précision conventionnelle contraire ») ; si la convention fixe un autre délai, c'est la mention à adapter.

**Forme de l'information.** Le D3171-11 demande un document annexé au bulletin ; R3243-1 ne met aucun solde de repos parmi les mentions du bulletin, et rien n'interdit de l'y imprimer. Martine imprime l'information dans le cadre des compteurs du bulletin lui-même, comme Quadra : le cumul de l'année (acquis, pris) et le solde dans le tableau, et en note le détail du mois (« 9 h acquises, 7 h prises le 13/07 », heures payées) et, dès 7 heures, la mention des deux mois. Le salarié a la même information, sur la même feuille.

## 2. Ce que Martine avait

Le compte d'heures du module `modulation` (`domain/hour_account_rules.py`, `application/payroll_hook.py`, branché dans `payroll/documents/payslip_run_heures.py`), jamais utilisé (aucune ligne en base au 05/11). Il fait l'essentiel : retirer des heures sup du calendrier de paie, les créditer au compte, débiter par une absence « récupération », défaire ses crédits quand le bulletin se recalcule. Il fait l'affaire **une fois corrigé** ; on n'en crée pas un deuxième. Défauts trouvés :

1. **Crédit à 1 pour 1** : une heure sup à 25 % créditait 1 h au lieu de 1 h 15 (L3121-28).
2. **Fenêtre** : il prenait les heures sup du calendrier étendu (mois civil ∪ fenêtre des variables) au lieu de la seule fenêtre des variables, celle où la paie les compte (`TYPES_RATTACHES_AUX_VARIABLES`).
3. **Solde remis à zéro chaque 1er janvier** : le solde ne lisait que les mouvements de l'année. Un repos non pris ne se perd pas ; il se reporte jusqu'à ce qu'il soit pris ou payé.
4. **Bac à sable** : le crédit d'une génération précédente du même mois comptait dans le solde et le plafond.
5. **« Tout au compteur » ignorait le plafond** du solde.
6. **Rien sur le bulletin** : ni solde, ni heures prises.
7. **Récupération seulement à la journée**, et une récupération validée ne pouvait plus être annulée (« le re-crédit n'existe pas »).

## 3. Décisions

### 3.1 Un seul réglage par société

« Heures supplémentaires : **payées** au bulletin, ou **mises au compteur de récupération** », avec un plafond facultatif du solde (en heures de repos). Au-delà du plafond, les heures sont payées. Rien d'autre à régler : la récupération par absence est ouverte d'office, le débit se fait à la validation.

En base : `company_modulation_settings.hour_account_enabled` + `hs_routing_policy` (`account_all` ou `pay_all`) + `max_account_balance_hours`. Aucune migration. Repasser en « payées » garde le compte ouvert : un solde acquis reste dû, visible, à prendre ou à payer. Les réglages de modulation annuelle et de franchise restent pour plus tard, repliés.

### 3.2 Ce que Martine fait seule chaque mois

- Elle prend les heures sup de la fenêtre des variables, les retire du calendrier de paie (en commençant par les derniers jours), et crédite le compteur de leur équivalent majoré, au taux de majoration que la paie leur aurait appliqué (barème de la société ; 25 % et 50 % à défaut). Le plafond se compte en heures de repos.
- Elle n'impute pas ces heures sur le contingent (elles ne sont plus dans les heures sup payées).
- Elle imprime au bulletin le compteur « Récup. (h) » : acquis du mois, pris du mois, solde ; les prises avec leur date (« 7 h le 13/07 ») ; dès 7 h de solde, la mention légale des deux mois.

Des heures sup saisies à la main (variables du mois, ou depuis le bulletin) font foi sur le planning, pour le compteur comme pour la paie : sinon elles seraient payées et mises au compteur.

### 3.3 Le choix du mois, salarié par salarié (demande d'Elsa du 02/11)

Sur le bulletin du mois, la RH voit « X h d'heures sup mises au compteur (= Y h de repos) » et un bouton **« Payer ces heures ce mois-ci »**. Le bouton enregistre la décision (`employee_overtime_routing_decisions`, heures à payer = toutes) et recalcule le bulletin. Elle peut revenir en arrière (« Remettre au compteur »). Dans une société qui paie, c'est l'inverse : « X h d'heures sup payées ce mois-ci » et **« Mettre ces heures au compteur »**. Un bulletin validé, repris de Quadra ou verrouillé refuse ces gestes et dit pourquoi.

La conséquence est écrite à côté du bouton, à partir du BOSS : « Payées ce mois-ci, ces heures gardent l'exonération d'impôt et les réductions des heures sup. Mises au compteur puis payées plus tard (solde de janvier, départ), elles les perdent. » C'est notre conseil du 03/11 à Elsa : payer directement les heures qui ne seront pas prises en repos.

### 3.4 Payer un solde

Sur le bulletin, quand le compteur a un solde : **« Payer le solde »** (en janvier pour Elsa, ou à tout moment). Le crédit du mois n'en fait pas partie : ces heures-là se paient avec « Payer ces heures ce mois-ci » et gardent leurs régimes. Martine pose un débit « paiement » au compteur pour le mois, et le bulletin de ce mois porte la ligne « Paiement solde heures de récupération » = heures × taux horaire de base, **en prime**, sans les régimes des heures sup (tranché le 03/11, spec `2026-11-03-rubrique-paiement-recup-hs-design.md`). Annuler le paiement rend les heures au compteur.

Au départ du salarié, un solde non pris est payé : D3121-23 le dit pour la contrepartie obligatoire ; pour le repos de remplacement, aucun texte lu ne le dit, mais ce repos remplace un salaire déjà gagné (notre lecture). L'alerte du bulletin de sortie le signale, la RH paie le solde du même bouton.

Le solde du compteur entre aussi dans la provision des congés, avec le repos compensateur (demande d'Elsa du 05/11 : « N-1 + N + repos compensateur + ancienneté »).

### 3.5 La récupération prise

Une absence « Récupération » (type `recuperation_modulation`, libellé à l'écran « Récupération (heures sup) »), payée comme un jour travaillé, qui débite le compteur à la validation :
- à la journée : la journée vaut la durée hebdomadaire ÷ 5 ;
- **en heures** (« 3,5 h le 14/08 ») : la journée reste travaillée au calendrier, seul le compteur est débité, comme le repos compensateur ;
- refusée si le solde ne suffit pas (le message dit le solde) ;
- annuler une récupération validée rend ses heures au compteur.

### 3.6 Reprise des soldes de Quadra au 30/09

Un mouvement « solde d'ouverture » daté de septembre 2026 par salarié, au solde que Quadra imprime, négatif compris (on suit Quadra même quand son arithmétique diffère : « les cumuls de reprise suivent le cabinet »). C'est une écriture dans la vraie paie : script simulé d'abord, écriture sur « lance ».

## 4. Ce qui ne change pas

- Une société sans le réglage : rien ne change, au centime (filet avant/après à 0 écart).
- Le repos compensateur « contrepartie obligatoire » (hors contingent, module `repos_compensateur`) reste un compteur distinct : le droit les distingue (L3121-30, L3121-38).
- La DSN : une heure mise au compteur n'est pas payée, donc n'est pas déclarée en heure sup ; une récupération prise est une absence payée sans suspension ; le paiement d'un solde sort comme une prime.

Le bulletin d'un contrat rangé (mois à deux contrats) ne touche pas au compteur : ses heures sup restent payées (cas rare, corrigeable à la main).

## 5. Ce que chaque société fait, mesuré sur ses bulletins

Mettre « au compteur » envoie **toutes** les heures sup de la société au compteur : on ne le décide pas sur la seule présence d'un solde, mais sur ce que Quadra a fait de janvier à septembre (bulletins dont le « montant net des heures compl/suppl exo. » du mois n'est pas nul).

| Société | Bulletins avec heures sup payées | Soldes de récup. au 30/09 | Réglage |
|---|---|---|---|
| MAJI | 6 sur 174 | 2 | **au compteur** |
| Comitech | 138 sur 233 | 1 | payées, soldes suivis |
| Mont-Blanc | 586 sur 1 112 | 14 | payées, soldes suivis |
| Cartol | 372 sur 952 | 1 | payées, soldes suivis |
| Colorplast | 68 sur 109 | 0 | rien ne change (Colorplast est intouchable sans accord) |
| LEWIS | 88 sur 658 | 0 | rien ne change |
| Zone 404 | 0 sur 79 | 0 | rien ne change |

La seule ligne de MAJI sans valeur en septembre reprise quand même est celle demandée par Alexandre (1 h en août, aucune ligne ensuite).

## 6. Les autres compteurs de l'inventaire

- **RTT et repos du forfait** (MAJI, Zone 404, Comitech, Mont-Blanc, Cartol, LEWIS) : Martine les a sous le nom RTT. L'ouverture est calée pour que le solde au 30/09 égale celui de Quadra, vérifié par le calcul de Martine lui-même.
- **JTC** (Mont-Blanc) et **CET** (Mont-Blanc, Cartol) : mécanismes existants, activés, soldes repris.
- **Modulation de Cartol** : pas reprise. L'activer changerait le calcul des heures sup de toute la société, et une vraie modulation suppose un accord collectif qu'aucune société n'a (Elsa, 02/11). À décider à part.
- **« Solde rep.comp. » de Mont-Blanc** (une valeur, −7,50, sans unité) : pas reprise, on ne sait pas ce que c'est.
