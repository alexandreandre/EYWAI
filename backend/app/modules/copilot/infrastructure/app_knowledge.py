"""
Base de connaissances produit EYWAI exposée à l'assistant IA.

Sert à répondre aux questions d'aide à l'utilisation du logiciel :
« comment faire X ? », « où trouver Y ? », « à quoi sert tel module ? ».

Source de vérité maintenue à la main à partir de la navigation réelle du
frontend (barres latérales RH et collaborateur, routes React Router). À mettre
à jour lorsque la navigation ou les fonctionnalités évoluent.
"""

APP_FEATURE_GUIDE = """\
EYWAI est un logiciel SaaS de gestion RH et de paie pour les entreprises françaises.
Il comporte deux grands espaces selon le profil connecté :
- l'espace RH / administrateur (gestionnaires RH, admins d'entreprise) ;
- l'espace collaborateur (les salariés).

La navigation se fait via la barre latérale gauche. Quand tu indiques un chemin,
utilise des libellés clairs (ex. « Menu latéral → EYWAI Paie → Congés & Absences »).

================================================================================
ESPACE RH / ADMINISTRATEUR (barre latérale en 3 sections + Tableau de bord)
================================================================================

— Tableau de bord (menu « Tableau de bord ») :
  Vue d'ensemble des tâches prioritaires : paie à lancer, signatures en attente,
  recrutement, onboarding, titres de séjour à renouveler, suivi médical, alertes
  RIB. Contient aussi l'assistant IA (« Demander à l'IA ») et des analytics
  d'équipe repliables.

--- Section « EYWAI Team » (gestion des effectifs et du suivi documentaire) ---

— Analytics Team (« Analytics Team ») : KPIs effectifs, turnover, absentéisme,
  masse salariale, journal d'audit.

— Collaborateurs (« Collaborateurs ») : liste de tous les salariés, recherche,
  création d'un collaborateur. En cliquant sur un collaborateur on ouvre sa
  fiche, avec les onglets : Documents, Augmentations et Promotions,
  Primes et autres (primes mensuelles, médailles du travail, prêts employeur,
  taux de PAS), Entretiens, Suivi médical, Calendrier, Badgeuse. C'est aussi là
  qu'on affecte la convention collective d'un salarié. Les identifiants de connexion d'un
  salarié (nom d'utilisateur + mot de passe temporaire) se trouvent dans
  l'onglet Documents → dossier « Autres » → fichier « Identifiants de connexion »
  (PDF téléchargeable). Si le PDF n'existe pas encore, il est généré automatiquement
  à l'ouverture (le salarié doit avoir une adresse e-mail renseignée).

— Recrutement (« Recrutement ») : pipeline de candidatures en Kanban + vue liste,
  fiches candidats, création d'offres de poste, scoring IA des candidats,
  analytics de recrutement. Lors de l'embauche d'un candidat, un compte
  collaborateur est créé automatiquement : une fenêtre affiche le nom d'utilisateur,
  l'e-mail et le mot de passe temporaire (à transmettre une seule fois). Le PDF
  « Identifiants de connexion » est ensuite disponible dans Documents → Autres.

— Onboarding (« Onboarding ») : hub des intégrations en cours. La checklist
  détaillée d'un nouvel arrivant (administratif, matériel, accès, formation)
  s'ouvre en cliquant sur un collaborateur.

— Départs (« Départs ») : gestion des sorties (démission, rupture
  conventionnelle, licenciement, fin de période d'essai, retraite), génération
  des documents de fin de contrat (solde de tout compte, attestations).

— Équipes (« Équipes ») : création et gestion des équipes, désignation des
  managers, affectation des collaborateurs.

— Documents (« Documents ») : explorateur des documents de l'entreprise
  (contrats, avenants, pièces justificatives, bulletins, identifiants de connexion),
  génération de documents. Pour retrouver les identifiants d'un salarié : ouvrir
  le dossier « Autres », sélectionner le collaborateur, puis télécharger le PDF
  « Identifiants de connexion ».

— Titres de séjour (« Titres de séjour ») : suivi des échéances et statuts des
  titres de séjour des collaborateurs étrangers.

--- Section « EYWAI Gestion » (pilotage RH au quotidien) ---

— Analytics Gestion (« Analytics Gestion ») : indicateurs RH opérationnels.

— Badgeuse (« Badgeuse ») : pointages des salariés (onglets Vue d'ensemble,
  Corrections, Paramètres).

— Calendriers (« Calendriers ») : saisie et validation des heures travaillées,
  modèles d'horaires, remplissage assisté par IA, import de pointages, vue par
  équipe. (Même page que l'étape ① du parcours paie.)

— Entretiens (« Entretiens ») : campagnes et comptes rendus d'entretiens annuels
  / professionnels (onglet Entretiens de Formation & talents).

— Suivi médical (« Suivi médical ») : planification des visites médicales,
  alertes et conformité (onglets Pilotage, Conformité).

— Formation & talents (« Formation & talents ») : plan de formation, conformité,
  entretiens, développement des compétences, paramètres (onglets Pilotage,
  Formations, Conformité, Entretiens, Développement, Paramètres).

— Augmentations & Promotions (« Augmentations & Promotions ») : campagnes
  d'augmentation, promotions individuelles, avenants au contrat.

— CSE & Dialogue Social (« CSE & Dialogue Social ») : réunions, élus, heures de
  délégation, BDES, élections, exports.

— Gestion des Utilisateurs (« Gestion des Utilisateurs ») : comptes applicatifs
  des gestionnaires RH et administrateurs (pas les comptes collaborateurs/salariés).
  Permet de créer des comptes RH, attribuer des rôles et gérer les accès aux
  entreprises. Les identifiants des salariés se gèrent via la fiche Collaborateur
  (onglet Documents) ou lors de la création / embauche, pas via ce module.

— Mon Entreprise (« Mon Entreprise ») : paramétrage de l'entreprise (onglets
  Pilotage, Identité, Paie, Mutuelle, Bibliothèque). L'onglet Paie permet de
  configurer les médailles du travail (activation, paliers, scan des éligibles)
  et de valider les dossiers en attente RH.

--- Section « EYWAI Paie » (parcours de production de la paie) ---

Le parcours est numéroté et doit être suivi dans l'ordre avant de lancer la paie :
  ① Calendrier → valider les heures / calendriers du mois (même écran que
    « Calendriers » en EYWAI Gestion, mais accessible ici dans le workflow paie).
  ② Congés & Absences → valider / refuser les demandes de congés et absences.
  ③ Notes de frais → valider les notes de frais.
  ④ Primes → saisir les primes, la participation et l'intéressement.
  ⑤ Saisies sur salaire → saisies-arrêts, pensions alimentaires, ATD.
  ⑥ Avances & acomptes → valider et verser avances sur salaire, acomptes sur
    salaire et acomptes sur prime (réconciliation possible au moment de la paie).
  ⑦ Prêts employeur → gérer les prêts en cours, échéanciers et remboursements
    sur bulletin.
Une fois les étapes à jour, le bouton « Lancer la paie » génère les bulletins du
mois.

— Prêts employeur (« Prêts employeur », étape ⑦ du workflow) : création et suivi
  des prêts accordés aux salariés (montant, taux, échéancier, remboursements
  déduits en paie). Le collaborateur peut consulter ses prêts dans son espace
  (« Prêts employeur »). La fiche collaborateur (onglet « Primes et autres »)
  permet aussi de voir les prêts d'un salarié.

Autres outils de la section paie :
— Analytics Paie (« Analytics Paie ») : indicateurs de paie.
— Simulation Paie (« Simulation Paie ») : calcul inverse (brut↔net), simulation,
  arrêt maladie.
— Suivi des taux (« Suivi des taux ») : cotisations, barèmes, synchronisation
  réglementaire.
— Exports (« Exports ») : exports paie & comptabilité, déclarations, paiements,
  exports RH, exports planifiés, historique.
— Paie (« Paie ») : consultation des bulletins (par collaborateur ou par mois) ;
  l'édition d'un bulletin donne accès aux onglets Édition, Aperçu, Historique,
  Comparaison N-1, Tendance.

--- Pied de barre latérale RH ---
— Support (« Support ») : assistant de création de ticket en plusieurs étapes et
  historique des tickets.
— Compte : modification du mot de passe, déconnexion.
— (Pour les admins plateforme EYWAI uniquement) « Plateforme Admin » : back-office
  EYWAI, dont le catalogue des conventions collectives (KALI), la veille
  réglementaire et les télétransmissions DSN.

================================================================================
ESPACE COLLABORATEUR (barre latérale du salarié)
================================================================================

— Tableau de bord : soldes de congés, prochaine absence, dernier bulletin, notes
  de frais en cours, badgeuse, signatures en attente, accès rapide aux modules.
— Calendrier et planning (« Calendrier et planning ») : vue mensuelle de son
  planning, semaine détaillée, export PDF.
— Ma badgeuse (« Ma badgeuse ») : pointage des entrées / sorties.
— Congés & absences (« Congés & absences ») : consulter ses soldes, faire une
  nouvelle demande, voir le calendrier du mois.
— Notes de frais (« Notes de frais ») : déclarer et suivre ses notes de frais.
— Avances & acomptes (« Avances & acomptes ») : demander et suivre une avance
  sur salaire, un acompte sur salaire (droit du salarié) ou un acompte sur prime.
— Prêts employeur (« Prêts employeur ») : consulter les prêts accordés par
  l'entreprise et leur échéancier de remboursement.
— Mes documents (« Mes documents ») : consulter ses documents RH. Le PDF
  « Identifiants de connexion » (nom d'utilisateur et mot de passe temporaire)
  est dans le dossier « Autres ».
— Ma formation (« Ma formation ») : ses entretiens, objectifs, compétences,
  formations, habilitations, obligations légales et son onboarding.
— Mon suivi médical (« Mon suivi médical », si le module est activé) : prochaines
  visites, obligations, historique (en lecture seule).
— Mon CSE (« Mon CSE », pour les élus) : réunions, délégation, documents.
— Mes bulletins : historique et téléchargement des bulletins de paie (accessible
  depuis le tableau de bord).
— Support (« Support ») et Mon profil (« Mon profil »).

================================================================================
IDENTIFIANTS DE CONNEXION DES COLLABORATEURS (salariés)
================================================================================

Chaque salarié dispose d'un compte pour accéder à son espace collaborateur.
Le compte est créé automatiquement lors de :
  1. La création manuelle d'un collaborateur (menu Collaborateurs → créer) — un
     message affiche le nom d'utilisateur, l'e-mail et le mot de passe temporaire.
  2. L'embauche d'un candidat via Recrutement — une fenêtre de confirmation affiche
     les identifiants (à transmettre une seule fois au salarié).
  3. La première consultation du PDF identifiants si le salarié a un e-mail mais
     pas encore de compte (génération automatique).

Où retrouver les identifiants (côté RH) :
  Chemin principal :
    Menu latéral → EYWAI Team → Collaborateurs → cliquer sur le salarié
    → onglet « Documents » → dossier « Autres » → « Identifiants de connexion »
    → bouton Télécharger (PDF).
  Chemin alternatif (vue globale) :
    Menu latéral → EYWAI Team → Documents → dossier « Autres » → sélectionner
    le collaborateur → « Identifiants de connexion ».

Contenu du PDF : nom d'utilisateur (identifiant de connexion), mot de passe
temporaire. Le salarié doit modifier ce mot de passe dès sa première connexion.
Connexion : page de connexion EYWAI avec le nom d'utilisateur ou l'e-mail +
mot de passe. En cas d'oubli : « Mot de passe oublié » sur la page de connexion.

Côté collaborateur (salarié) : Menu latéral → Mes documents → dossier « Autres »
→ « Identifiants de connexion ».

Prérequis : le salarié doit avoir une adresse e-mail renseignée dans sa fiche.
Sans e-mail, le compte ne peut pas être créé.

================================================================================
FAQ RH TRANSVERSES
================================================================================

— Lancer la paie : suivre le parcours numéroté ① à ⑦ dans EYWAI Paie, puis
  cliquer sur « Lancer la paie » (disponible une fois les étapes à jour).
— Avance vs acompte : une avance sur salaire est versée avant le travail ;
  un acompte sur salaire concerne le salaire déjà gagné ; un acompte sur prime
  anticipe une prime. Tout se gère dans « Avances & acomptes » (RH et collaborateur).
— Prêts employeur : module dédié dans le workflow paie (étape ⑦) et espace
  collaborateur ; paramétrage et validation des médailles du travail dans
  Mon Entreprise → onglet Paie.
— Convention collective : affectée par salarié dans sa fiche (Collaborateurs)
  ou consultée via l'assistant IA pour les questions réglementaires.
— Multi-entreprises : un gestionnaire RH peut basculer d'entreprise via le
  sélecteur en haut de l'écran ; les données affichées concernent l'entreprise active.
— Identifiants collaborateur : voir section dédiée ci-dessus (Documents → Autres).

================================================================================
RÈGLES DE RÉPONSE POUR L'AIDE À L'UTILISATION
================================================================================
- Donne le chemin de navigation exact (libellés de menus / onglets).
- Si la fonctionnalité dépend du profil (RH vs collaborateur), précise-le.
- Reste concis : indique où aller et les étapes clés, sans inventer d'écrans ou
  de boutons qui ne figurent pas dans ce guide.
- Si une fonctionnalité demandée n'existe manifestement pas dans le guide,
  dis-le honnêtement et propose l'option la plus proche ou le module Support.
"""
