# Interfaçage comptable — conception

**Point afaire :** #26. Interfaçage compta
**Date :** 4 août 2026
**Statut :** conception validée, implémentation à planifier

---

## 1. Constat

L'interfaçage comptable existe dans le code depuis juin 2026 : un moteur d'écritures
(`payroll_ledger`), trois formats de sortie (OD globale, journal de paie, FEC), un
panneau de mappings comptables et un connecteur API Cegid Loop. Rien de tout cela ne
produit un fichier qu'un cabinet puisse importer.

### 1.1 L'OD n'est jamais équilibrée

Moteur exécuté sur Colorplast, données de production :

| Période | Lignes générées | Total débit | Total crédit | Écart |
|---|---|---|---|---|
| Juin 2026 | 137 | 28 387,98 € | 28 825,51 € | **437,53 €** |
| Mai 2026 | 139 | — | — | **10 571,53 €** |

Un fichier d'écritures déséquilibré est rejeté par tout logiciel comptable. L'export
sort quand même : `equilibre: False` est calculé et ignoré.

### 1.2 Cause racine : les éléments hors brut n'ont pas de contrepartie

Le moteur ne pose au débit que le salaire brut (641000) et les charges patronales
(645000). Tout ce qui arrive au net à payer sans transiter par le brut est crédité
sans contrepartie de charge.

Vérification arithmétique sur juin 2026 :

```
brut                    19 445,81   (seul débit hors charges patronales)
net à payer             15 611,06
cotisations salariales   4 028,22
PAS                        244,06
                        ----------
crédit correspondant    19 883,34
écart                      437,53   = indemnité de transport, non débitée
```

L'écart est exactement le montant des éléments non soumis. En mai 2026, le net à payer
(22 894,47 €) dépasse le brut (18 458,05 €) de 4 436 € à cause de la participation :
même mécanisme, amplifié.

Éléments concernés, tous présents dans `payslip_data` avec un identifiant stable :

| Bloc | Identifiant | Compte attendu (plan Colorplast) |
|---|---|---|
| `primes_non_soumises[].prime_id` | `indemnite_de_transport` | 67181500 |
| `synthese_net.acompte_verse` | — | 425100 |
| `retenues_saisies.saisies[]` | — | 42700000 |
| `remboursements_prets` | — | 274000 |
| `remboursements_avances` | — | 425200 |
| notes de frais | — | 42862500 |
| `participations` | — | à confirmer |

L'OD de référence (10/25) ne contient aucune participation ; les comptes correspondants
ne peuvent donc pas en être déduits. Ils seront demandés à Elsa avec l'OD d'un mois qui
en comporte, plutôt que devinés.

### 1.3 Les organismes ne sont pas reconnus

`resolve_organisme` (`app/modules/exports/domain/charges_organisme.py`) cherche des
mots-clés dans le **libellé** de la cotisation : « URSSAF », « RETRAITE », « AGIRC »,
« PREVOYANCE », « MUTUELLE ». Conséquence : « Sécurité sociale - Maladie, Maternité,
Invalidité, Décès », « Allocations familiales », « Cotisation AGS », « Assurance
Chômage », « Accidents du travail » retournent toutes `AUTRE`.

Toutes les charges atterrissent donc sur un unique 645000 et toutes les dettes sur un
unique 431000.

### 1.4 Les comptes ne sont pas ceux du client

L'OD de paie réelle du cabinet (Colorplast, période 10/25, transmise par Elsa le
2 août 2026 — `data/_inbox/whatsapp-elsa-2026-08-02/`) utilise le plan Cegid à
8 chiffres, ventilé **par organisme** :

| Compte | Intitulé | Nature |
|---|---|---|
| 42100000 | Personnel — rémunérations dues | tiers |
| 42700000 | Saisies-arrêts | tiers |
| 42862500 | Notes de frais | tiers |
| 43100000 | URSSAF | tiers |
| 43702000 | Mutuelle (AG2R) | tiers |
| 43720000 | Caisse de retraite | tiers |
| 43740000 | Prévoyance (Mutex) | tiers |
| 43741000 | Prévoyance (Alptis) | tiers |
| 43780000 | Retraite supplémentaire (La Mondiale) | tiers |
| 44210000 | Prélèvement à la source | tiers |
| 64110000 | Salaires et appointements | charge |
| 64111300 | Primes diverses | charge |
| 64510000 | Cotisations à l'URSSAF | charge |
| 64524100 | Prévoyance (Mutex) | charge |
| 64524200 | Mutuelle (AG2R) | charge |
| 64524300 | Prévoyance (Alptis) | charge |
| 64530000 | Retraite complémentaire (Klésia) | charge |
| 64530100 | Retraite supplémentaire (La Mondiale) | charge |
| 67181500 | Remboursement transport | charge |

Journal `PAI`, référence de pièce `PAIE1025`, date au dernier jour du mois, **19 lignes
agrégées** pour 7 salariés — là où nous en produisons 137.

### 1.5 Rien n'est configuré

- `company_accounting_config` : **0 ligne**. Aucune société n'a de connexion comptable.
- `accounting_mappings` : 11 lignes, toutes `company_id = NULL` (défauts plateforme).
- `accounting_transmissions` : 2 lignes, mode manuel, Colorplast, juin 2026.
- Dernière génération d'export comptable : 12 juin 2026.

### 1.6 Deux copies du même module

`app/modules/payroll/exports/ecritures_comptables.py` (597 lignes) est une copie
obsolète de `app/modules/exports/infrastructure/export_ecritures_comptables.py`. Elle
lit `structure_cotisations.cotisations`, une clé qui n'existe plus dans les bulletins
(les cotisations sont réparties en `bloc_principales`, `bloc_allegements`,
`bloc_csg_non_deductible`, `bloc_autres_contributions`) et retourne donc zéro
cotisation. Elle reste appelée par `exports/application/service.py` via
`providers.generate_od_salaires`.

---

## 2. Objectif

Produire, pour chacune des 7 sociétés, une OD de paie mensuelle **équilibrée**, aux
**comptes du client**, dans le **format de son cabinet**, transmissible de trois
façons : téléchargement manuel, fichier FEC, et dépôt automatique par l'API Cegid Loop.

Priorité retenue : reproduire ce qui se fait déjà chez le cabinet, et respecter les
obligations légales de forme (FEC, arrêté du 29 juillet 2013). Pas d'invention.

---

## 3. Architecture

Cinq briques, dans cet ordre de dépendance :

```
A. Plan comptable par société  ──┐
                                 ├──> B. Moteur d'OD ──> C. Formats ──> D. Transmission
   (référentiel de comptes)      │        (équilibre)      (fichiers)      (manuel/API)
                                 │
                                 └──> E. Validation contre les OD réelles du cabinet
```

### A. Plan comptable par société

**Unité de mapping : le `coti_id`.** Chaque ligne de cotisation d'un bulletin porte
déjà un identifiant stable, indépendant du libellé (qui, lui, varie d'une société à
l'autre : « GAN Isolé 2026 (EMU3) » chez l'une, « AG2R Mutuelle » chez l'autre). Le
recensement sur les bulletins de juin 2026 donne **31 identifiants distincts** :

- Blocs principaux et CSG : `ags`, `allocations_familiales`, `apec`,
  `assurance_chomage`, `at_mp`, `ceg_t1`, `ceg_t2`, `cet`, `csg_deductible`,
  `csg_non_deductible`, `mutuelle`, `prevoyance_cadre`, `prevoyance_non_cadre`,
  `retraite_comp_t1`, `retraite_comp_t2`, `retraite_secu_deplafond`,
  `retraite_secu_plafond`, `retraite_sup`, `securite_sociale_maladie`, `forfait_social`
- Allègements : `reduction_generale`, `deduction_hs_patronale`,
  `reduction_hs_salariale`, `exoneration_apprenti_salariale`
- Autres contributions : `CFP`, `csa`, `dialogue_social`, `fnal`,
  `taxe_apprentissage`, `taxe_apprentissage_solde`, `versement_mobilite`

Un cas à traiter : la CSG sur participation apparaît **sans `coti_id`** (2 bulletins en
juin 2026). Le moteur doit la rattacher explicitement, pas la laisser tomber dans un
fourre-tout silencieux.

**Évolution de `accounting_mappings`.** La table porte aujourd'hui un seul
`compte_comptable` et un `sens`. Une cotisation en demande deux : un compte de charge
(part patronale) et un compte de tiers (dette envers l'organisme). Colonnes ajoutées :

| Colonne | Type | Rôle |
|---|---|---|
| `coti_id` | text | identifiant de cotisation ou d'élément (clé de rattachement) |
| `compte_charge` | text | compte de classe 6 débité (part patronale) |
| `compte_tiers` | text | compte de classe 4 crédité (dette organisme ou salarié) |
| `organisme` | text | nom affiché de l'organisme (AG2R, Alptis, Klésia…) |

`compte_comptable` et `sens` sont conservés pour les rubriques qui n'ont qu'un seul
compte (net à payer, PAS) et pour ne pas casser l'existant.

**Résolution en cascade** (déjà en place dans `get_accounting_mappings`, à conserver) :
mapping société → mapping plateforme (`company_id = NULL`) → défaut codé. Une clé sans
mapping est **signalée**, jamais absorbée silencieusement.

**Écran.** `frontend/src/components/exports/AccountingMappingsPanel.tsx` existe et est
étendu : une ligne par `coti_id`, deux colonnes de comptes, le nom de l'organisme,
et un indicateur visuel pour les clés non mappées.

### B. Moteur d'OD réécrit

Remplace la logique de `payroll_ledger.build_payroll_ledger`.

**Règle d'équilibre : par construction.** Chaque montant lu dans le bulletin est posé
des deux côtés au moment où il est lu, jamais après coup. Un élément sans compte de
contrepartie ne produit aucune écriture et remonte une anomalie.

Écritures produites pour une période :

| Élément du bulletin | Débit | Crédit |
|---|---|---|
| Salaire brut | compte de charge « salaires » | — |
| Primes soumises | compte de charge « primes » | — |
| Cotisations salariales | — | compte de tiers de l'organisme |
| Cotisations patronales | compte de charge de l'organisme | compte de tiers de l'organisme |
| Allègements patronaux | compte de tiers de l'organisme (dette réduite) | compte de charge de l'organisme (charge annulée) |
| PAS | — | compte PAS |
| Éléments non soumis (transport, participation…) | compte de charge dédié | — |
| Saisies-arrêts | — | compte saisies |
| Acomptes déjà versés | compte acomptes | — |
| Net à payer | — | compte personnel |

**Agrégation par compte**, comme le cabinet : une ligne par compte pour la société
entière, pas une ligne par salarié. C'est ce qui ramène 137 lignes à une vingtaine.

**Refus d'exporter si l'écart dépasse 0,01 €.** Message explicite listant les éléments
sans compte, au lieu d'un fichier faux. C'est le changement de comportement le plus
important du chantier.

Le module obsolète `payroll/exports/ecritures_comptables.py` est supprimé et ses
appelants (`exports/application/service.py`) redirigés vers le moteur unique.

### C. Formats de sortie

- **OD globale** CSV et Excel — existe, à revalider une fois le moteur corrigé.
- **FEC** — les 18 colonnes de l'arrêté du 29 juillet 2013 sont présentes
  (`export_fec.py`). À vérifier une fois les écritures justes : `EcritureNum`,
  `PieceRef`, `CompteLib` doivent porter les valeurs du cabinet (`PAIE<AAAAMM>`).
- **Format cabinet** — `export_formats_cabinet.py` existe ; à aligner sur le gabarit
  observé (journal `PAI`, date au dernier jour du mois, libellé « Salaire de MM/AAAA »).

### D. Transmission

- **Manuel** : téléchargement des fichiers depuis l'écran Exports. Fonctionne.
- **API Cegid Loop** : le connecteur (`cegid_quadra_connector.py`, 485 lignes) suit la
  documentation officielle — dépôt de fichier, `importFEC`, suivi de statut. Il n'a
  jamais été exercé contre le vrai service. Il manque, par société : le code dossier
  (Colorplast = `000005`, lisible sur l'OD du cabinet), la clé API et la clé
  d'abonnement. Un test de connexion sans envoi doit précéder toute transmission réelle.

### E. Validation

Un test de non-régression par société : l'OD générée est comparée à l'OD réelle du
cabinet, ligne à ligne, sur les comptes et les montants. Les fichiers de référence
vivent dans `data/<societe>/comptabilite/` (jamais dans le dépôt — le dépôt est public).

Critère de réussite : mêmes comptes, mêmes montants au centime, écart d'équilibre nul.

---

## 4. Dépendances externes

Trois éléments manquent et conditionnent la couverture des 7 sociétés. Le choix retenu
est de traiter les 7 d'emblée ; les briques A à C se construisent sans attendre, et
Colorplast se paramètre dès maintenant à partir de l'OD 10/25 déjà reçue.

| Ce qu'il faut | Pour quoi | Sans quoi |
|---|---|---|
| Une OD de paie pour Cartol, Comitech, LEWIS, MAJI, Mont Blanc, Zone 404 (un mois suffit) | construire les 6 plans comptables | seule Colorplast est paramétrable |
| Une OD de mai ou juin 2026 | comparer les montants au centime | validation de structure seulement |
| Identifiants Cegid Loop (clé API, clé d'abonnement, code dossier par société) | brique D | transmission manuelle uniquement |

---

## 5. Hors périmètre

- **Ventilation analytique.** La colonne `analytique` existe dans
  `accounting_mappings` mais aucune société n'a de section analytique renseignée. Le
  cabinet n'en utilise pas dans l'OD observée.
- **Lettrage.** L'OD du cabinet porte des codes de lettrage (`AF`, `AB`). Ils sont
  posés par la comptabilité, pas par la paie.
- **Écritures hors paie.** L'OD du cabinet contient une ligne annotée « cette écriture
  est saisie par nous, elle ne vient pas de la paie ». Nous ne la produisons pas.
- **Provision de congés payés.** C'est le point #23, distinct.
- **Reprise des périodes antérieures.** Aucune régénération rétroactive des exports
  déjà produits.

---

## 6. Risques

| Risque | Portée | Traitement |
|---|---|---|
| Le refus d'export sur déséquilibre bloque un export qui « passait » avant | tous les utilisateurs de l'écran Exports | le fichier produit avant était faux ; le message doit dire quoi corriger |
| Les libellés d'organisme varient par société (GAN, AG2R, Alptis…) | mapping | le rattachement se fait sur `coti_id`, jamais sur le libellé |
| Suppression du module dupliqué | `exports/application/service.py` | redirection vers le moteur unique, tests unitaires existants à faire passer |
| Envoi réel vers Cegid depuis l'environnement de test | production comptable du client | la transmission suit la même règle que la DSN : refusée hors production |
