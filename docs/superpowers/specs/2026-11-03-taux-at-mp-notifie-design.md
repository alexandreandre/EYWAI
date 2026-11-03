# Taux AT/MP notifié : import du PDF et taux daté

Date : 03/11/2026. Branche : feat/dsn-octobre. État : spec écrite, construction en attente d'une vraie notification (point 10 du message à Elsa du 03/11).

## Pourquoi

Promis à Elsa dans le message de la vidéo B (02/11) : la RH dépose le PDF de notification du taux AT/MP, Martine lit le taux et sa date d'effet, la RH confirme, et Martine garde le PDF comme preuve. En janvier, Martine prévient si le taux de l'année manque.

Aujourd'hui :
- le taux est **une seule valeur sans date** : la colonne `companies.taux_at_mp`, copiée par les générateurs dans `parametres_paie.taux_specifiques.taux_at_mp` (`payslip_generator.py:1368`, `payslip_generator_forfait.py:571`) ;
- chaque import de DSN **l'écrase** (`dsn_import/domain/establishment_extract.py`, `AUTO_OVERWRITE_FROM_DSN`) : la DSN dit le taux que l'ancien logiciel a appliqué, pas forcément le taux notifié ;
- un changement de taux en cours d'année ou un taux rétroactif ne se voit nulle part.

Comment l'administration transmet le taux (sources dans `data/_sources/parametres-notifies/`) :
- notification dématérialisée obligatoire depuis le 01/01/2022, sur le compte AT/MP de net-entreprises ;
- seule l'entreprise télécharge le PDF officiel, un tiers déclarant ne fait que consulter ;
- mises à jour « majoritairement chaque début d'année mais également en cours d'année » ;
- ni API ni compte rendu lisible par logiciel pour l'instant. Le CRM 118 (NEOReS) les transmettra « à terme », sans calendrier.

## Ce qu'on construit

1. **Un historique des taux par établissement** : table `company_taux_at_mp`.
   - Colonnes : `id`, `company_id` (cascade), `date_effet` (date), `taux` (numeric, en %), `code_risque` (texte, facultatif), `source` (`notification`, `dsn`, `saisie`), `document_path` (le PDF archivé, facultatif), `siret_lu`, `notifie_le` (facultatif), `created_at`, `created_by`.
   - Une ligne par `(company_id, date_effet)`. Une nouvelle notification à la même date remplace l'ancienne et garde son PDF.
   - Droits (RLS) : lecture pour les membres de la société, écriture pour admin, rh et collaborateur_rh, comme les paramètres de paie.
   - Une société = un établissement (un SIRET), comme aujourd'hui.

2. **Un seul juge du taux du mois** : `taux_at_mp_du_mois(company_id, annee, mois)`.
   - Il rend la ligne dont la `date_effet` est la plus récente sans dépasser le 1er du mois, et sinon `companies.taux_at_mp` (le comportement d'aujourd'hui).
   - Le lisent : les deux générateurs, la simulation, l'empreinte des bulletins (`empreinte_entrees_service.py:286`) et la DSN (`dsn_export/application/builder.py:514`).
   - `companies.taux_at_mp` reste en place : c'est le taux du jour, affiché sur la fiche de la société. Une confirmation le met à jour si sa date d'effet est passée.

3. **Le dépôt du PDF**, sur la carte « Taux AT/MP » des paramètres de paie de la société.
   - La RH dépose le PDF. Martine en lit le texte (`pdfplumber`, déjà dans `requirements.txt`) : SIRET, taux net notifié, date d'effet, code risque, date de la notification.
   - Elle montre un aperçu : « Taux notifié : 2,13 % à partir du 01/01/2027 (code risque 252BA). Aujourd'hui : 2,05 %. » Rien n'est écrit avant « Enregistrer ce taux ».
   - **SIRET d'une autre société** : refus, qui nomme la société du SIRET lu si elle est dans le groupe.
   - **PDF illisible** (scanné, mise en page inconnue) : la RH tape le taux et la date d'effet, et le PDF est archivé quand même. Elle n'est jamais bloquée (l'outil reste souple).
   - **Plusieurs codes risque** sur une notification : Martine les montre tous, et la RH choisit celui des salariés de l'établissement. Un taux par salarié n'est pas construit (voir « Hors champ »).
   - Le PDF va dans le stockage de la société. Il s'ouvre depuis la ligne de l'historique.

4. **Les bulletins touchés.**
   - Brouillons : l'empreinte lit le taux du mois. Ceux des mois couverts par le nouveau taux passent « À recalculer », et eux seuls.
   - Bulletins remis : ils restent figés. Si la date d'effet est déjà passée, l'aperçu le dit avant l'enregistrement : « 3 bulletins remis d'octobre et de novembre ont été calculés à 2,05 % : la différence se régularise sur le prochain bulletin. » La régularisation se fait à la main, comme toute correction (théorème : toujours corrigeable à la main).

5. **L'alerte de janvier**, dans la revue d'avant-paie, de sévérité « à vérifier », jamais bloquante.
   - Elle se lève pour tout mois de l'année N quand aucune ligne n'a de date d'effet en N.
   - Texte : « Aucun taux AT/MP notifié pour 2027 : le taux de 2026 (2,05 %) s'applique. Déposez la notification de 2027 dès qu'elle arrive sur net-entreprises. »
   - Elle tombe dès qu'une ligne de N existe, même avec un taux inchangé.

6. **L'import de DSN** n'écrase plus le taux.
   - Il écrit une ligne `source = dsn`, datée du 1er du mois de la DSN, seulement si aucune notification ne couvre ce mois.
   - Si une notification couvre ce mois avec un autre taux, la DSN ne change rien. L'import le signale : « La DSN de septembre applique 2,20 %, le taux notifié est 2,05 %. » C'est aussi un constat d'audit.

## Ce qu'on ne touche pas

- **Le calcul de la cotisation** (`calcul_cotisations.py:863`) : il lit toujours `parametres_paie.taux_specifiques.taux_at_mp`. Seule la valeur qu'on y met change : celle du mois au lieu de celle du jour.
- **La réduction générale** : la part AT/MP du paramètre T vient de la même valeur.
- **Le bonus-malus** : il reste saisi à la main jusqu'à ce que NEOReS le transmette (page 54 du cahier technique 2027.1).

## Hors champ (plus tard)

- **Lecture automatique par NEOReS** (CRM 118, bloc RO.B008) quand les taux AT/MP y arriveront, par l'API DSN (point A4). La table est prête : ce sera une `source` de plus.
- **Un taux par salarié** (plusieurs codes risque dans un établissement, par exemple un taux « bureaux »). On le construira si une des sept sociétés en a besoin.
- **Un seul point d'entrée « Documents de l'administration »** pour la notification AT/MP, le CRM PAS et le CRM 118. La fenêtre de dépôt est écrite pour être réutilisée.

## Ce qui attend la vraie pièce

- Les libellés exacts du PDF (« taux net », « date d'effet », etc.) et leur place. Le lecteur se calibre sur la pièce d'Elsa.
- Le test se fait sur le **texte extrait et pseudonymisé** de la pièce, jamais sur le PDF : le dépôt est public, les données restent hors git (`data/` n'est pas versionné).
- Vérifier sur la pièce : un PDF par établissement, ou plusieurs SIRET dans un même PDF.

## Tests prévus (TDD)

- `taux_at_mp_du_mois` : sans ligne, la colonne ; une ligne au 01/01 ; un changement au 01/07 ; une date d'effet après le mois demandé, ignorée.
- Lecteur du PDF : le texte de la pièce donne SIRET, taux, date ; un texte inconnu ne donne rien, sans erreur.
- Empreinte : un nouveau taux au 01/10 fait passer « À recalculer » les brouillons d'octobre et après, pas ceux de septembre.
- Alerte de janvier : levée sans ligne de l'année, tombée avec une ligne au même taux.
- Import de DSN : n'écrase plus une notification ; écrit une ligne `dsn` sur un mois sans notification.
- Filet avant/après : sans aucune ligne dans la table, zéro écart au centime sur les sept sociétés.
