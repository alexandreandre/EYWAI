# Checklist UI manuelle — Promotions (F1–F8)

À valider sur l’app en dev (`npm run dev`), compte **RH** + compte **admin**.

| ID | Action | Résultat attendu | Validé |
|----|--------|------------------|--------|
| F1 | Créer promotion type poste sans titre | Toast erreur poste requis | Code OK (`PromotionModal`) |
| F1 | Créer type salaire sans montant | Toast erreur salaire | Code OK |
| F1 | Créer type statut sans statut | Toast erreur statut | Code OK |
| F1 | Créer type classification sans champ | Toast classification | Code OK |
| F2 | Date effet = aujourd’hui | Toast « appliquée » + statut effective | Code OK |
| F3 | Date effet future | Toast « brouillon » + statut draft | Code OK |
| F4 | Liste : actions edit/delete/mark sur draft uniquement | `PromotionsActions` draft only | Code OK |
| F5 | Détail pending : admin approuve/rejette | Boutons approve/reject | Code OK |
| F5 | Détail draft : bouton « Soumettre pour validation » | `submitPromotion` branché | Code OK |
| F6 | Détail approved : « Marquer comme effective » | API 200 après correctif C5 | Code OK |
| F6 | Détail draft : « Marquer comme effective » | API 200 | Code OK |
| F7 | Filtres année/statut/type page Augmentations | `CareerFiltersBar` | À tester en UI |
| F8 | Lien entretien si `performance_review_id` | Navigation détail | À tester en UI |

Parcours complet recommandé (employé Non-Cadre) :
1. Promotion statut → Cadre, date aujourd’hui → vérifier fiche employé.
2. Promotion salaire brouillon → mark-effective depuis liste.
3. Brouillon → Soumettre → Admin approuve → Marquer effective.
