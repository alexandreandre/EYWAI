# Attestations à la demande du salarié — conception (05/11/2026)

## Origine

Retour d'Elsa du 05/11. Elle a ouvert Exports > Déclarations > « Attestations & annexes ».
Elle y a trouvé un tableau Excel du mois (Employé, Matricule, Type attestation, Période,
Brut, Net imposable, Net à payer, Statut). Elle demande de pouvoir choisir le type
d'attestation, et si ce format est légal.

Établi le 05/11, non rediscuté :

- ce fichier n'est pas une attestation (`backend/app/modules/exports/infrastructure/export_attestations.py`) ;
- la colonne « Matricule » y contient le début de l'identifiant interne, « Statut » vaut « Généré » partout, et l'écran le présente comme un justificatif pour une mutuelle ou une banque ;
- les attestations obligatoires existent déjà : la DSN remplace l'attestation de salaire pour les IJ et l'attestation employeur France Travail (cahier technique 2026.1, S21.G00.40.025, copie dans `docs/audit-maji-2026/sources/dsn-cahier-technique-2026.1.txt`, lignes 11170 à 11175). Le certificat de travail, le solde de tout compte et l'attestation France Travail sortent avec les documents de sortie.

## Ce que le code contient déjà (trouvé le 05/11)

- Un menu « Ajouter > Générer une attestation » existe, avec 9 types. Il est sur la page RH « Documents » (`frontend/src/components/documents/useCompanyDocumentGeneration.tsx`) et dans l'onglet Documents de la fiche salarié (`frontend/src/components/employee-detail/EmployeeDetailDocumentsRhSection.tsx`). Les deux fenêtres sont des copies l'une de l'autre.
- Le générateur PDF est `backend/app/services/common_attestation_generator.py`. Il est appelé par `document_service.generate_document`, et le document est rangé dans `generated_documents`.
- Le signataire (nom et fonction) se règle dans Entreprise > Fiche (`nom_signataire_rh`, `qualite_signataire_rh`). Un rôle RH peut le modifier. Les 7 sociétés du test l'ont rempli.
- **Gaëlle ne voit ce menu nulle part.** En mode paie, la page Documents est interdite (`frontend/src/lib/payrollFocus.ts`), et l'onglet Documents de la fiche n'affiche que les bulletins (`bulletinsSeulement`, `EmployeeDetailDocumentsTab.tsx`).
- Défauts des lettres actuelles :
  - l'« attestation de salaire » reprend le salaire de base de la fiche, pas les bulletins ;
  - les « revenus annuels » valent le salaire de base × 12 ;
  - l'« attestation retraite » écrit que le salarié « a acquis les droits », ce qui n'a pas de sens ;
  - emploi, présence, ancienneté et poste disent la même chose.

## Ce que disent les sources (ouvertes le 05/11)

1. **Aucun modèle officiel n'est imposé** pour un salarié en poste, et aucun Cerfa n'existe. Le ministère du Travail publie un « Modèle de lettre - Attestation d'emploi », mis à jour le 05/06/2023. Il contient : la société, son représentant et sa fonction, l'adresse du siège, le numéro d'immatriculation (SIRET), le salarié (nom, date et lieu de naissance, adresse), son poste, son contrat (CDI, CDD et son terme), sa date d'entrée et son ancienneté, le lieu et la date, la signature. Il ne parle pas du salaire. Il précise aussi : « un accord ou une convention collective peut prévoir le contenu d'une telle attestation ». Source : https://code.travail.gouv.fr/modeles-de-courriers/attestation-de-travail
2. **Aucune obligation légale de délivrer** cette attestation n'a été trouvée. Le certificat de travail se remet « à l'expiration du contrat » (article L1234-19 du Code du travail ; service-public F87 : « remis à la fin du contrat de travail »).
3. **Bailleur** : la liste des pièces est fermée, « le propriétaire a interdiction d'en exiger d'autres », sous peine d'une amende jusqu'à 3 000 € (15 000 € pour une personne morale). Pour la situation professionnelle, il peut demander le « contrat de travail ou de stage, ou, si nécessaire, attestation de l'employeur précisant l'emploi et la rémunération proposée, la date d'entrée en fonctions envisagée et, si nécessaire, la durée de la période d'essai ». Pour les ressources, il peut demander les « 3 derniers bulletins de salaires ». Source : service-public F1169, qui reprend le décret n° 2015-1437 (Légifrance a refusé le téléchargement par curl, erreur 403).
4. **Banque** : aucune règle officielle ne fixe les pièces. Le prêteur vérifie les revenus « en se référant notamment à des documents vérifiables » (articles L313-16 et suivants du Code de la consommation ; service-public F16123).
5. **net-entreprises** : rien d'autre que l'attestation de salaire pour les IJ.

## Décisions

Alexandre a choisi le 05/11 : deux types (travail et salaire), et 3 mois par défaut, modifiables de 1 à 12. Il a ensuite demandé que je tranche le reste en suivant mes recommandations. Ces points sont marqués « (choix) » : ce sont des choix, pas des règles.

### 1. Deux types, rien d'autre

| Clé (inchangée) | Libellé |
|---|---|
| `attestation_emploi` | Attestation de travail |
| `attestation_salaire` | Attestation de salaire |

- Les clés restent les mêmes, pour que les documents déjà générés gardent leur type.
- Les 7 autres types (`attestation_presence`, `_anciennete`, `_poste`, `_revenus`, `_location`, `_pret`, `_retraite`) quittent le menu et le générateur. Leur libellé reste, pour afficher les documents déjà générés (32 sur le test). Une demande de génération pour l'un d'eux est refusée par le message : « Ce type d'attestation n'existe plus : choisissez l'attestation de travail ou l'attestation de salaire. »
- Ils ne sont plus proposés à l'import de modèle dans la bibliothèque. Aucun modèle client n'existe pour ces types sur le test.

### 2. Attestation de travail

Elle suit le modèle du ministère (source 1). On y ajoute la rémunération et la période d'essai, que le décret demande pour un bailleur (source 3) :

- l'en-tête de la société : logo, raison sociale, adresse, SIRET (`build_branding_header_reportlab`, déjà utilisé) ;
- « Je soussigné(e), {signataire}, {fonction}, agissant pour le compte de la société {raison sociale}, dont le siège est situé {adresse}, immatriculée sous le numéro SIRET {siret}, atteste que : » ;
- un tableau :
  - nom et prénom ;
  - date et lieu de naissance ;
  - adresse ;
  - emploi occupé ;
  - nature du contrat : « CDI » ; « CDD jusqu'au {contract_end_date} » ; « Contrat d'apprentissage jusqu'au {contract_end_date} » ; pour un CDD sans date de fin, « CDD » seul ;
  - date d'entrée ;
  - ancienneté (« x ans et y mois », comptée depuis `hire_date`) ;
  - temps de travail ;
  - rémunération brute mensuelle (`salaire_de_base`) ;
  - la ligne « Période d'essai : en cours jusqu'au {end_date} », seulement si `trial_periods` a une période `en_cours` (lue par `get_active_trial_period`) ;
- « L'intéressé(e) fait toujours partie de nos effectifs à la date du {jour}. » ;
- « La présente attestation est délivrée à la demande de l'intéressé(e) pour servir et valoir ce que de droit. » ;
- « Fait à {ville}, le {jour}. », puis le nom et la fonction du signataire, puis « Signature et cachet de l'employeur ».

Donnée absente : la ligne garde des pointillés « ………… », à compléter à la main. Martine n'invente jamais une valeur et ne laisse jamais une ligne vide sans le montrer. Sans signataire réglé, on lit « Nom et fonction du signataire : ………… ».

Salarié parti (`employment_status = 'parti'`) : refus, avec le message « {Prénom Nom} a quitté l'entreprise : c'est le certificat de travail qui atteste de son emploi (Départs). » Source : L1234-19.

### 3. Attestation de salaire

- Le même en-tête et le même bloc de signature que l'attestation de travail.
- « … atteste que {salarié}, employé(e) en qualité de {poste} depuis le {date d'entrée}, a perçu les rémunérations suivantes au cours des {n} derniers mois de paie : »
- Un tableau Mois | Salaire brut | Net à payer avant impôt sur le revenu, puis une ligne Total.
- « Montants repris des bulletins de paie remis au salarié. »

Règles :

- **Seuls les bulletins remis comptent** : validés, et arrivés à la date de mise à disposition de la société. C'est la règle de l'espace salarié (`bulletins_remis`, `jour_de_la_societe`). Ainsi la lettre dit la même chose que les bulletins du salarié, et Martine n'atteste jamais un brouillon. (choix)
- Les **n** mois les plus récents qui ont un bulletin remis, avec n de 1 à 12, 3 par défaut (décision d'Alexandre). Si le salarié en a moins, la lettre liste ceux qui existent, et la phrase dit leur nombre réel.
- Deux bulletins le même mois (un par contrat, D3) : une seule ligne, qui fait leur somme.
- Montants : le brut vient de `payslip_data.salaire_brut`, le net avant impôt de `payslip_data.synthese_net.net_social_avant_impot`. C'est la ligne du bulletin « Net à payer avant impôt sur le revenu » (`bulletin_view.py`). Le net imposable sert à l'impôt et n'intéresse ni la banque ni le bailleur. Le net payé dépend du taux de prélèvement et des retenues (acompte, titres-restaurant) : on ne le met pas. (choix)
- Aucun bulletin remis : refus, avec le message « Aucun bulletin remis à {Prénom Nom} : Martine n'atteste que des salaires de bulletins validés et remis. » **Au 05/11, tous les bulletins du test sont en brouillon** (Quadra fait encore la paie). Ce message s'affichera donc pour tout le monde tant que la paie n'est pas validée dans Martine.
- Salarié parti : permis. Ses salaires passés restent vrais.

### 4. Une seule fenêtre, partout où il faut

Une fenêtre commune `AttestationDialog` remplace les deux copies. On y choisit :

- le salarié, quand on n'est pas déjà sur sa fiche ;
- le type (2 choix) ;
- le nombre de mois, de 1 à 12, 3 par défaut, pour l'attestation de salaire seulement ;
- le modèle (« Standard Martine » ou un modèle client, comme aujourd'hui).

La fenêtre porte aussi une ligne fixe : « Signée au nom du signataire réglé dans Entreprise > Fiche. »

Elle s'ouvre à trois endroits :

1. **Fiche salarié > Documents**, y compris en mode paie : un bouton « Générer une attestation » au-dessus des bulletins, puis la liste des attestations déjà générées pour ce salarié (pour les rouvrir). Le contrat et les pièces d'identité restent masqués en mode paie.
2. **Page RH Documents**, comme aujourd'hui, hors mode paie.
3. **Exports > Déclarations** : une carte « Attestation pour un salarié », qui ouvre la fenêtre avec le choix du salarié. C'est là qu'Elsa a cherché. (choix)

Après la génération, le PDF s'ouvre dans l'aperçu de Martine (`openDocumentPreview`), avec le message « Attestation de travail de {Prénom Nom} prête ». Un refus s'affiche dans la fenêtre, qui reste ouverte, et dans le message d'erreur.

Côté serveur : `GenerateDocumentRequest` gagne `nombre_mois` (entier de 1 à 12, facultatif). La commande `generate_document` (`backend/app/modules/documents/application/commands.py`) :

- refuse les types retirés et le salarié parti avant toute écriture ;
- lit la période d'essai et les bulletins remis, puis les passe au générateur dans le contexte.

Le générateur reste pur : il ne lit pas la base.

### 5. Le tableau du mois dans Exports

- Le nom devient « Récapitulatif des salaires du mois ».
- La description devient : « Brut, net imposable et net à payer de chaque salarié pour le mois. Ce n'est pas une attestation : pour en remettre une à un salarié, utilisez « Attestation pour un salarié » ci-dessous. »
- Les colonnes deviennent : Matricule (`employees.matricule`), Employé, Période, Brut, Net imposable, Net à payer. « Type attestation » et « Statut » disparaissent.
- L'onglet s'appelle « Récapitulatif », le fichier `recapitulatif_salaires_{periode}`.
- La clé interne `attestations_annexes` reste, pour l'historique et les exports programmés. Seuls les libellés changent : DeclarationsTab, ExportHistory, ExportCommonModel, scheduled_exports.

## Tests

- **Backend, unitaires** :
  - le texte de chaque PDF : mentions du modèle, pointillés quand une donnée manque, période d'essai seulement si elle est en cours, CDD et son terme ;
  - le choix des mois : bulletins remis seulement, les n plus récents, deux bulletins le même mois sommés, moins de n mois ;
  - les refus : type retiré, salarié parti, aucun bulletin remis ;
  - le récapitulatif : vrai matricule, plus de « Statut ».
- **Frontend, Vitest** : `AttestationDialog` propose 2 types ; le nombre de mois n'apparaît que pour le salaire ; le bouton est présent en mode paie.
- **Bout en bout, sur le site de test, un seul parcours en mode paie** (méthode de `08-mode-paie`) :
  - fiche d'un salarié > Documents > Générer une attestation > travail : le PDF s'ouvre ;
  - salaire : le refus « Aucun bulletin remis » s'affiche ;
  - Exports > Déclarations : la carte ouvre la même fenêtre.

  Les attestations générées par le test sont supprimées à la fin, pour que tout soit remis en état sur le test.

## Hors périmètre, signalé

- Le même faux matricule (début de l'identifiant interne) se trouve dans le journal de paie, le virement des acomptes et le paiement des salaires (`export_journal_paie.py:106`, `export_virement_acomptes.py:336`, `export_paiement_salaires.py:183`).
- On ne reconstruit pas les attestations retraite et revenus annuels. Les droits à la retraite relèvent des caisses ; les revenus annuels figurent sur les bulletins de décembre.
