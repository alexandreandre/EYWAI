# Taxonomie des questions RH — couverture agent

L'agent doit router et répondre correctement à chaque catégorie.
Utiliser cette liste comme matrice Phase 5 (minimum 1 question par catégorie marquée ★).

## A. Données effectifs (SQL) ★

| ID | Question exemple | Données attendues |
|----|------------------|-------------------|
| A01 | Combien avons-nous de salariés en CDI ? | COUNT employees |
| A02 | Liste des cadres avec leur ancienneté | employees.statut, hire_date |
| A03 | Qui est en période d'essai ce mois-ci ? | periode_essai jsonb |
| A04 | Quel est le salaire de base de [Prénom Nom] ? | salaire_de_base |
| A05 | Employés en temps partiel et leur durée hebdo | is_temps_partiel, duree_hebdomadaire |
| A06 | Effectif par type de contrat | GROUP BY contract_type |
| A07 | Salariés partis cette année | statut = parti / employee_exits |
| A08 | Moyenne d'âge des effectifs | date_naissance |

## B. Paie & masse salariale (SQL) ★

| ID | Question exemple | Données attendues |
|----|------------------|-------------------|
| B01 | Masse salariale brute du mois dernier | payslips payslip_data |
| B02 | Net à payer total en [mois/année] | payslip_data.net_a_payer |
| B03 | Coût total employeur du trimestre | cout_total_employeur |
| B04 | Bulletins générés pour [employé] en 2025 | payslips filter |
| B05 | Primes versées ce mois | monthly_inputs |
| B06 | Évolution du salaire de [employé] | salary_history |
| B07 | Taux de PAS de [employé] | specificites_paie |
| B08 | Avances en attente de validation | salary_advances.status |
| B09 | Prêts employeur en cours | employee_loans |

## C. Absences & congés (SQL) ★

| ID | Question exemple | Données attendues |
|----|------------------|-------------------|
| C01 | Demandes de congés en attente | absence_requests pending |
| C02 | Qui est absent aujourd'hui ? | selected_days + date |
| C03 | Total jours RTT pris ce trimestre | type=rtt, validated |
| C04 | Absences maladie du mois | type=maladie |
| C05 | Taux d'absentéisme sur 12 mois | calcul sur selected_days |

## D. Notes de frais (SQL) ★

| ID | Question exemple | Données attendues |
|----|------------------|-------------------|
| D01 | Notes de frais en attente de validation | status=pending |
| D02 | Total notes de frais validées ce mois | SUM amount |
| D03 | Dépenses transport de [employé] | type=Transport |

## E. Recrutement & onboarding (SQL)

| ID | Question exemple | Données attendues |
|----|------------------|-------------------|
| E01 | Candidats en cours de recrutement | recruitment_candidates |
| E02 | Onboardings non terminés | onboarding_checklists |
| E03 | Candidat avec le meilleur score IA | ai_score |

## F. Formation & entretiens (SQL)

| ID | Question exemple | Données attendues |
|----|------------------|-------------------|
| F01 | Formations en cours | training_enrollments |
| F02 | Entretiens annuels non faits | annual_reviews status |
| F03 | Budget formation consommé | training_budget |

## G. Conformité & documents (SQL)

| ID | Question exemple | Données attendues |
|----|------------------|-------------------|
| G01 | Titres de séjour expirant dans 30 jours | residence_permits |
| G02 | Salariés sans RIB renseigné | coordonnees_bancaires null |
| G03 | Visites médicales en retard | medical_obligations |

## H. Conventions collectives (CC) ★

| ID | Question exemple | Intent |
|----|------------------|--------|
| H01 | Combien de jours de congés payés par an ? | requires_collective_agreement |
| H02 | Durée de la période d'essai cadres ? | CC |
| H03 | Que dit la convention sur les RTT ? | CC + collective_agreement_query |
| H04 | Préavis de démission non-cadre ? | CC |
| H05 | Grille de classification coefficient 240 | CC |
| H06 | Heures supplémentaires majoration | CC |

## I. Aide logiciel — navigation RH (app_help) ★

| ID | Question exemple | Chemin attendu dans le guide |
|----|------------------|------------------------------|
| I01 | Comment lancer la paie ? | Parcours paie ①→⑥ + bouton Lancer |
| I02 | Où valider les congés ? | EYWAI Paie → Congés & Absences |
| I03 | Comment créer un collaborateur ? | EYWAI Team → Collaborateurs |
| I04 | Où sont les identifiants de connexion ? | Fiche → Documents → Autres |
| I05 | Comment faire une augmentation ? | Augmentations & Promotions |
| I06 | Où exporter la paie ? | EYWAI Paie → Exports |
| I07 | Comment gérer les prêts employeur ? | EYWAI Paie → Prêts employeur |
| I08 | Où configurer la mutuelle ? | Mon Entreprise → Mutuelle |
| I09 | Comment planifier une visite médicale ? | Suivi médical |
| I10 | Où voir les analytics effectifs ? | Analytics Team |
| I11 | Comment embaucher un candidat ? | Recrutement → embauche |
| I12 | Gérer un départ en retraite | Départs |
| I13 | Paramétrer les équipes | Équipes |
| I14 | Accéder à la simulation de paie | Simulation Paie |
| I15 | Valider les avances sur salaire | Avances & acomptes |

## J. Aide logiciel — espace collaborateur (app_help)

| ID | Question exemple | Chemin attendu |
|----|------------------|----------------|
| J01 | Comment demander un congé ? | Congés & absences |
| J02 | Où voir mon bulletin ? | Tableau de bord / Mes bulletins |
| J03 | Déclarer une note de frais | Notes de frais |
| J04 | Demander une avance | Avances & acomptes |
| J05 | Consulter mon planning | Calendrier et planning |

## K. Questions mixtes / clarification

| ID | Question exemple | Comportement attendu |
|----|------------------|---------------------|
| K01 | Combien d'employés ? | Clarification : tous ? CDI ? actifs ? |
| K02 | Congés de Martin | Clarification employé si homonymes |
| K03 | Que dit la convention ? (multi-CC) | Clarification quelle CC |
| K04 | Comment faire X (feature inexistante) | Honnêteté + Support |

---

## Grille de scoring Phase 5

| Résultat | Critère |
|----------|---------|
| ✅ | Intent correct + réponse complète et exacte |
| ⚠️ | Intent correct mais données/guide incomplets |
| ❌ | Mauvais intent ou hallucination |

**Objectif release** : 0 ❌, ≤ 2 ⚠️ sur les 20 questions ★.
