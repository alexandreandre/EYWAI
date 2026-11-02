# Formules de prévoyance par société

Date : 02/11/2026. Branche : feat/dsn-octobre.

## Pourquoi

Retour d'Elsa sur la vidéo B (5:45) : « le mieux c'est de le pré-paramétrer au début pour qu'elles n'aient plus qu'à sélectionner un type de prévoyance ». Aujourd'hui, la mutuelle a des formules de société (`company_mutuelle_types`), mais la prévoyance se tape ligne par ligne sur la fiche de chaque salarié (`specificites_paie.prevoyance.lignes_specifiques`). Dans la base de test, chaque société n'a que 2 à 13 jeux de lignes différents pour 6 à 85 adhérents : les formules existent déjà, de fait.

## Ce qu'on construit

1. **Un catalogue par société** : table `company_prevoyance_formules`.
   - Colonnes : `id`, `company_id` (cascade), `libelle`, `statut_categoriel` (`cadre`, `non_cadre`, `tous`), `lignes` (jsonb), `is_active`, `created_at`, `updated_at`, `created_by`.
   - `lignes` a la même forme que les lignes de la fiche : `libelle`, `salarial`, `patronal`, `forfait_social` (fractions) et `base` facultative (`brut_plafonne` par défaut, `tranche_2`, `brut`). Les autres clés d'une ligne sont gardées telles quelles.
   - Les droits (RLS) sont ceux des formules de mutuelle : lecture pour les membres de la société, écriture pour admin, rh et collaborateur_rh.
2. **Le choix sur la fiche** : au-dessus des lignes de prévoyance, une liste « Formule de la société », filtrée par catégorie (cadre ou non-cadre, plus « tous »).
   - Choisir une formule **copie** ses lignes dans `lignes_specifiques` et pose `prevoyance.formule_id`.
   - Les lignes restent modifiables, pour garder l'outil souple. Si elles ne sont plus celles de la formule, la fiche le dit : « Lignes modifiées depuis la formule ».
   - « Aucune (lignes saisies à la main) » garde le fonctionnement d'aujourd'hui.
3. **Une formule modifiée** : l'écran dit combien de fiches la portent avec d'autres lignes, et propose « Mettre à jour les N fiches ».
   - La mise à jour réécrit leurs lignes. Leurs brouillons passent « À recalculer », comme pour toute fiche modifiée.
   - Un bulletin remis reste figé.
   - Rien ne se met à jour sans ce clic.
4. **Retirer une formule** la désactive (`is_active = false`). Les fiches gardent leurs lignes, et la liste affiche « formule retirée ».

## Ce qu'on ne touche pas

- **Le moteur.** Il lit toujours `lignes_specifiques` (`calcul_cotisations.py`, lignes de prévoyance cadre et non-cadre ; `_assiette_pour_base`). Copier une formule donne exactement les lignes qu'on aurait tapées.
- **La DSN.** Les affiliations du bloc 70 viennent de la reprise et des collègues (`dsn_export/domain/affiliations.py`), pas de la fiche.
- **L'empreinte des bulletins.** `prevoyance.formule_id` n'est lu par aucun calcul. Il est retiré de l'empreinte (`empreinte_entrees_service._fiche`) : relier une fiche à sa formule ne fait passer aucun bulletin « À recalculer ». Une fiche sans formule a la même empreinte qu'avant.

## Remplir le catalogue pour les sept sociétés

On ne demande à personne de créer les formules. Le script `backend/scripts/creer_formules_prevoyance.py` les crée depuis les fiches existantes.
- Il prend un jeu de lignes distinct par société et par catégorie, et le nomme d'après ses libellés.
- Il relie à la formule les fiches qui portent exactement ces lignes.
- Il tourne d'abord en simulation, avec le piège à écritures, une empreinte et une sauvegarde. Il n'écrit que sur « lance creer_formules_prevoyance ».
- Aucune ligne ne change, donc aucun bulletin ne bouge.

## Points d'entrée

- API, sur le modèle de `/api/mutuelle-types` (société active de l'utilisateur, droit RH en écriture) :
  - `GET /api/prevoyance-formules` ;
  - `POST /api/prevoyance-formules` ;
  - `PUT /api/prevoyance-formules/{id}`, qui renvoie la formule et `fiches_a_mettre_a_jour` ;
  - `DELETE /api/prevoyance-formules/{id}` ;
  - `POST /api/prevoyance-formules/{id}/appliquer`, qui renvoie le nombre de fiches réécrites.
- Module backend `prevoyance_formules` (api, application, infrastructure), avec une règle pure `appliquer_formule(prevoyance, formule) -> prevoyance`. Elle copie les lignes, pose `formule_id` et laisse le reste (`adhesion`, autres clés) intact.
- Écran société : section « Formules de prévoyance » sous la mutuelle, dans l'onglet « Paramètres paie » (`CompanyPayrollTab.tsx`).
- Écran fiche : `PrevoyanceAffiliationFields.tsx`, utilisé à la création et à la modification.

## Tests

- Backend :
  - `appliquer_formule`, qui copie, garde `adhesion` et les clés inconnues, et remplace les lignes ;
  - l'empreinte, identique avec ou sans `formule_id`, différente si une ligne change ;
  - le compte des fiches à mettre à jour ;
  - la route en écriture, refusée sans droit RH.
- Frontend :
  - le filtre par catégorie ;
  - la copie des lignes au choix d'une formule ;
  - la détection « Lignes modifiées depuis la formule ».
- Suites unitaires complètes avant de pousser. Pas de filet au centime : aucun calcul ne change (le moteur n'est pas touché, et l'empreinte reste identique pour les fiches d'aujourd'hui).

## Vidéo

B.4 scène 2 montre la formule créée sur la société, puis choisie sur la fiche. Le texte de la scène est réécrit au tournage de B.
