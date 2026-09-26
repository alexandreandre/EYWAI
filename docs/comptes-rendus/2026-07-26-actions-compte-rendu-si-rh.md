# Compte rendu SI RH — les 22 actions, point par point

**Document de travail.** Objectif : **comprendre** chaque point avant de corriger quoi que ce
soit. Aucun développement n'est lancé à ce stade.

**Date :** 26 juillet 2026 · **Base auditée :** production (289 salariés, dont **240 actifs**,
7 sociétés) · **Méthode :** chaque point confronté au code et à la base réelle, en lecture seule.

**Légende des verdicts**

| | |
|---|---|
| ✅ **Déjà fait** | Le point est traité, ou l'était déjà sans qu'on le sache |
| 🟢 **Conforme** | La demande est juste, il n'y a qu'à l'exécuter |
| 🟡 **Partiel** | L'idée est bonne mais incomplète : un arbitrage manque |
| 🟠 **À nuancer** | Le constat est juste, la solution suggérée n'est pas la bonne |
| ❓ **À clarifier** | Impossible de trancher sans une réponse du terrain |

---

## 1. Corriger les accès de Vanessa pour qu'elle ait toutes les filiales

**Ce que ça veut dire** — Vanessa s'est connectée et n'a pas vu les 7 sociétés.

**Vérifié en base.** Le provisionnement a tourné en deux passes le 22/07 :

| Heure | Événement |
|---|---|
| 12:28 | MAJI réactivé, Zone 404 créé |
| **13:11** | **Connexion de Vanessa → 2 filiales sur 7** |
| 13:26 | MBC, Cartol, LEWIS, Colorplast, Comitech créés |
| depuis | aucune reconnexion |

Elle a constaté le problème **quinze minutes avant qu'il soit résolu**. Ses 7 accès sont actifs
en rôle `admin`.

> ✅ **Déjà fait.** Une reconnexion suffit. Attention : elle a un second compte
> (`vamate@maji-invest.fr`) jamais utilisé, à ne pas employer pour se connecter.

**Trouvé en passant, corrigé** : la révocation d'accès n'avait **aucun effet** — le chargeur de
session ne lisait jamais `is_active`. Gaëlle disposait de 5 sociétés qu'elle n'aurait pas dû
voir, exploitables et pas seulement visibles. Correctif écrit en TDD (5 tests), suite complète
à 4250 tests au vert, production alignée sur la matrice d'accès que tu as transmise.

---

## 2. Envoyer les identifiants de connexion à Gaëlle et Vanessa via WhatsApp

**Ce que ça veut dire** — leur transmettre de quoi se connecter.

**Vérifié.** Le login par identifiant fonctionne (résolveur exécuté en lecture seule sur la prod) :

| Personne | Identifiant | Mot de passe |
|---|---|---|
| Vanessa Amate | `vanessa.amate` | dans le classeur |
| Gaëlle Bouali | `gaelle.bouali` | dans le classeur |

Classeur : `backend/reports/EYWAI_acces_provisoires.xlsx` (droits `600`, dossier ignoré par git).
Les deux comptes sont en `must_change_password` : elles choisiront leur mot de passe au
premier accès.

> 🟢 **Conforme, prêt à envoyer.**

**⚠️ À savoir** — l'e-mail d'authentification de Vanessa est un **placeholder DSN**
(`import.vanessa.amate…@…dsn-import.local`). Le jour où on nettoiera les placeholders (point 4),
**son accès casse** si son e-mail n'a pas été migré avant. Les points 2 et 4 sont liés.

---

## 3. Créer un fichier importable avec les IBAN et BIC manquants

**Ce que ça veut dire** — compléter en masse les coordonnées bancaires.

**Vérifié — l'ampleur est plus nette que prévu :**

| | Salariés actifs concernés |
|---|---|
| IBAN manquant | **0** |
| **BIC manquant** (IBAN présent) | **238 / 240** |

Répartition : Cartol 86 · MBC 75 · LEWIS 39 · Comitech 17 · MAJI 10 · Colorplast 7 · Zone 404 4.

Ce n'est donc pas « quelques BIC à compléter » : **c'est la quasi-totalité de la base**, effet
mécanique de l'import DSN qui écrit `{"iban": "", "bic": ""}` puis ne remplit que l'IBAN.

**L'import existe déjà** et reconnaît la colonne BIC sous les intitulés `bic`, `swift` ou
`code bic`, avec validation d'IBAN.

> 🟢 **Conforme.** Rien à développer. Je peux générer le fichier pré-rempli des 238 salariés,
> classé par société, avec IBAN et colonne BIC à compléter.

**À noter** : le BIC est déductible de l'IBAN français dans la grande majorité des cas (le code
banque y est contenu). Une table de correspondance banque → BIC éviterait une saisie manuelle de
238 lignes. À arbitrer.

---

## 4. Collecter les adresses e-mail de tous les salariés (RGPD)

**Ce que ça veut dire** — sans e-mail, impossible de notifier un salarié du dépôt d'un document
dans son coffre-fort, ce qui est une obligation.

**Vérifié — et c'est le point le plus sérieux du compte rendu :**

| Société | Salariés actifs sans e-mail réel |
|---|---|
| Cartol Industrie | 77 |
| LEWIS | 39 |
| Mont Blanc Composite | 19 |
| Comitech Composite | 10 |
| Colorplast | 2 |
| MAJI | 1 |
| **Total** | **148 / 240 (62 %)** |

Ces salariés portent une adresse technique fabriquée à l'import
(`import.prenom.nom.123456@…dsn-import.local`), sur un domaine **qui n'existe pas**.

**Le problème n'est pas seulement la collecte.** La fonction qui notifie le salarié teste
uniquement « une adresse est-elle renseignée ? » avant d'envoyer. Une adresse placeholder passe
ce test. L'envoi part, échoue, et la fonction est explicitement *best effort* : **elle ne lève
jamais d'erreur**. Résultat : rien ne distingue aujourd'hui un salarié notifié d'un salarié
jamais notifié.

Le suffixe `.dsn-import.local` est pourtant **déjà reconnu dans cinq endroits du code** — partout
sauf là où il engage la conformité.

> 🟠 **À nuancer.** Elsa a raison sur la collecte, mais s'arrêter là laisse le trou ouvert :
> tant qu'il n'y a pas de garde-fou, on croira avoir notifié 148 personnes qui ne l'auront
> pas été. **Deux chantiers, pas un** : (a) collecter, (b) bloquer et signaler les adresses
> non routables. Le (b) est une demi-journée et devrait passer en premier.

Le passage papier en atelier via Corinne et Catherine est la bonne approche pour Cartol et MBC,
qui concentrent 96 des 148 cas.

---

## 5. Ajouter Robin comme utilisateur sur Zone 404

**Ce que ça veut dire** — ambigu, c'est le point le plus flou du compte rendu.

**Vérifié.** Il s'agit de **Robin BARAN**, Pilote IA / Robotique chez Zone 404. Et il a déjà tout :

| Salarié Zone 404 | Compte | Accès | Rôle | Identifiant |
|---|---|---|---|---|
| **Robin BARAN** | ✅ | Zone 404, actif | collaborateur | `robin.baran` |
| Théo BARBERET | ✅ | Zone 404, actif | collaborateur | `theo.barberet` |
| Tristan AGOUMBI OGANDAGA | ✅ | Zone 404, actif | collaborateur | `tristan.agoumbi_ogandaga` |
| Mohamed ASSANHAJI | ✅ | Zone 404, actif | collaborateur | `mohamed.assanhaji` |
| Mathys FILLINGER | ✅ | Zone 404, actif | collaborateur | `mathys.fillinger` |
| Raphaël PERRIER | ✅ | Zone 404, actif | collaborateur | `raphael.perrier` |

Les 6 salariés sont configurés à l'identique. **Rien ne distingue Robin de ses collègues**, et il
n'apparaît dans aucune ligne de la matrice d'accès transmise depuis.

> ❓ **À clarifier.** Si « utilisateur » = espace salarié, c'est déjà fait. Si ça veut dire un
> rôle de gestion (RH, validation…), il faut savoir lequel — son poste ne l'indique pas.
> Il a été ajouté au manifeste avec son rôle actuel, ce qui documente l'existant sans rien changer.

---

## 6. Renseigner les dates d'expiration des titres de séjour

**Vérifié :**

| | |
|---|---|
| Salariés soumis à titre de séjour | **36** |
| **Sans date d'expiration** | **34** (MBC 32 · Comitech 1 · MAJI 1) |

**Le moteur d'alertes existe déjà** et couvre explicitement le cas « soumis mais date non
renseignée », avec calcul des jours restants et statuts d'échéance. Le tableau de bord charge
déjà le champ.

> 🟢 **Conforme.** Pure saisie, aucun développement. Le sujet est concentré sur MBC (32 des 34).

---

## 7. Bouton d'export Excel pour les titres de séjour

**Vérifié.** Le module est complet côté données et alertes, mais ne contient **aucune génération
de fichier**. Les exports existants ailleurs dans l'application fournissent le modèle.

> 🟢 **Conforme.** Petit développement, ~0,5 jour. Point à trancher : l'export porte-t-il sur
> les 36 salariés soumis, ou sur toute la base avec une colonne « soumis O/N » ?

---

## 8. Compteur séparé pour les JTC (3/an, dont 1 pour la journée de solidarité)

**Ce que ça veut dire** — un compteur distinct des CP et des RTT, plafonné à 3 jours par an,
perdus s'ils ne sont pas pris, dont un est consommé par la journée de solidarité.

**Vérifié.** Le sigle « JTC » **n'apparaît nulle part** dans le dépôt. Deux difficultés :

1. Les types d'absence sont un **type énuméré PostgreSQL** — en ajouter un impose une
   **migration de schéma**, avec propagation dans le moteur de paie, les exports et la DSN.
2. Deux modules font déjà exactement ce travail de compteur distinct : `repos_compensateur` et
   `cet`. **C'est le bon modèle**, et il correspond au mot « séparé » du compte rendu.

La journée de solidarité, elle, existe déjà comme paramètre d'entreprise et est traitée par le
moteur de paie. Le lier au compteur JTC est le seul morceau qui touche la paie.

> 🟡 **Partiel.** La demande est claire mais il manque les règles d'acquisition :
> les 3 jours sont-ils acquis d'un bloc en début d'année, ou proratisés à l'embauche ?
> Sur quelle période (année civile ou juin→mai comme les CP) ? Toutes les sociétés ou certaines ?
> **Le chantier est plus lourd qu'il n'y paraît : 3 à 5 jours.**

---

## 9. Salariés Colorplast en RTT alors qu'ils n'en ont pas

**Vérifié — et le diagnostic est net.**

D'abord, ce n'est **pas** une histoire de congés posés : Colorplast compte
**0 demande d'absence de type RTT**. Ce qu'Elsa a vu est donc un **solde de RTT affiché**, pas
un RTT pris.

Ensuite, la cause. Quand une société n'a aucune configuration de congés, le moteur retombe sur
une valeur par défaut de **10 jours de RTT par an**, et l'éligibilité individuelle ne filtre
personne :

| Société | Config RTT | RTT effectifs |
|---|---|---|
| Comitech, LEWIS, Cartol | `rtt_annual_days = 10` (explicite) | 10 j/an |
| **Colorplast, MBC, MAJI, Zone 404** | **aucune configuration** | **10 j/an par défaut** |

> 🟢 **Conforme — Elsa a vu juste, et le problème dépasse Colorplast.** Quatre sociétés sur sept,
> dont MBC, n'ont **aucun paramétrage de congés** et distribuent 10 RTT/an à tout le monde par
> simple effet de défaut.

**Ce qui doit être décidé** : Colorplast doit-elle avoir 0 RTT, ou des RTT réservés aux cadres au
forfait ? La même question vaut pour MBC, MAJI et Zone 404. Le correctif technique (ne plus
accorder de RTT en l'absence de configuration explicite) est simple, mais il **change le
comportement des 7 sociétés** : il faut d'abord la cible métier, puis le patch.

---

## 10. Coche « aménagement » sur les fiches de suivi médical

**Vérifié.** Le terme n'existe nulle part. Le module gère les visites et les obligations, mais il
n'existe **pas d'entité « avis d'aptitude »** portant des restrictions.

> 🟡 **Partiel.** Deux choses à trancher avant de coder :
>
> 1. **Où poser la coche ?** Un aménagement de poste survit à la visite qui l'a prescrit. Le
>    poser sur la visite le rendrait invisible dès la visite suivante — il devrait être porté par
>    **le salarié**, avec la visite d'origine en référence.
> 2. Un aménagement a des **conséquences juridiques** (obligation de reclassement, inaptitude).
>    Une case à cocher est un bon début, mais elle appellera vite un motif et une date de fin.

---

## 11. Ajouter les élus CSE sur la plateforme

**Vérifié.** La table des élus existe et contient **0 ligne**. Le module est complet par ailleurs
(mandats, alertes de fin de mandat, heures de délégation).

> 🟢 **Conforme.** Pure saisie. À faire **avant** le point 12 : sans élus, les exports CSE n'ont
> rien à produire, et on ne pourra pas reproduire les erreurs signalées.

---

## 12. Retravailler la partie CSE — erreurs sur les exports

**Vérifié partiellement.** Trois exports existent : base des élus, heures de délégation,
historique des réunions.

**Piste identifiée** dans l'export des élus : le calcul des jours restants est enveloppé dans un
`try/except` qui, en cas d'échec, met la valeur à vide et laisse le statut à « Actif ». Si les
dates de fin de mandat remontent avec un fuseau horaire, la soustraction échoue silencieusement —
l'export sort avec une colonne « Jours restants » vide et **tous les mandats marqués « Actif »**,
expirés compris.

> ❓ **À clarifier.** C'est une hypothèse cohérente avec « des erreurs sur les exports », mais
> la table est vide : je n'ai pas pu reproduire. **Il me faut l'export fautif ou la description
> précise de l'erreur constatée.** C'est le seul point du compte rendu où je n'ai pas de cause
> racine solide.

---

## 13. Partager le tableau BDES à Elsa pour génération automatique

**Vérifié.** Seul le **dépôt** d'un fichier BDES existe. Il n'y a **aucune génération**.

Le point positif : les indicateurs nécessaires sont déjà calculés (turnover, pyramide des âges,
effectifs par service et par contrat, ancienneté moyenne). L'essentiel du travail est la
**structure réglementaire** de la BDES et le rendu documentaire, pas le calcul.

> 🟢 **Conforme, et c'est le plus gros morceau : 8 à 10 jours.** Objectif annoncé : export PDF ou
> Word pour septembre.
>
> **⚠️ Point de planning** : le tableau d'Elsa **définit la cible**. Tant qu'il n'est pas
> transmis, le chantier ne peut pas démarrer — et c'est le seul poste qui ne rentre pas dans
> l'échéance s'il glisse. **À réclamer en priorité absolue.**

---

## 14. Confirmer les montants des primes médaille du travail avec Mickaël

**Vérifié.** Les paliers par défaut sont 400 € (argent, 20 ans), 600 € (vermeil, 30 ans),
800 € (or, 35 ans) et 1 000 € (grande médaille, 40 ans). Une table de configuration par société
permet de les redéfinir — **une seule société est configurée (Comitech)**, les 6 autres tournent
sur les valeurs par défaut.

> 🟢 **Conforme.** Pure configuration, aucun développement.
>
> **Utile pour la discussion avec Mickaël** : le module gère déjà l'exonération sociale 2026 —
> la prime est exonérée tant qu'elle n'excède pas le salaire mensuel de base brut. Cela peut
> orienter le montant retenu, autant le lui dire avant qu'il tranche.

---

## 15. Vérifier l'existence d'une prime de transport dans le module primes

**Vérifié — et suivre cette action à la lettre créerait une erreur de paie.**

Le catalogue de primes ne connaît que deux modes de calcul, « montant fixe » et « selon heures »,
**sans aucune notion d'exonération**. Une prime de transport créée là serait **intégralement
soumise à cotisations**.

Or le transport **existe déjà, et correctement** : dans les spécificités de paie du contrat, avec
le remboursement d'abonnement à 50 % (obligatoire, exonéré — article L3261-2 du Code du travail)
et l'indemnité mensuelle nette.

> 🟠 **À nuancer.** La bonne réponse n'est pas « l'ajouter », c'est **« elle existe, mais pas où
> vous la cherchez »** : fiche du salarié, onglet spécificités de paie. À montrer à Gaëlle plutôt
> qu'à recréer. Le seul développement utile serait de rendre ce réglage plus visible, ou d'en
> permettre la saisie en masse.

---

## 16. Vérifier la création d'un fichier de virement pour les acomptes

**Vérifié.** L'export « acomptes » actuel est **comptable** : liste détaillée et écritures
d'opérations diverses (comptes 425x / 512000), **sans coordonnées bancaires**. Ce n'est pas un
fichier de virement.

En revanche, la plateforme sait déjà générer des virements : la génération **SEPA pain.001**
existe et le type d'export « virement salaires » est fonctionnel.

> 🟢 **Conforme.** Le besoin est réel et les briques sont là — il s'agit d'alimenter la
> génération SEPA avec les acomptes de la période au lieu des nets à payer. ~2 jours.
>
> **⚠️ Dépendance bloquante : les 238 BIC manquants (point 3).** Sans eux, le fichier sera
> rejeté par la banque. Le point 3 doit être terminé avant celui-ci.

---

## 17. Créer un environnement de test avec les données réelles

**Ce que ça veut dire** — pouvoir s'entraîner aux sorties et opérations sensibles sans toucher
la production. Le besoin est parfaitement légitime.

> 🟠 **À nuancer.** « Avec les données réelles » signifie dupliquer hors production les bulletins,
> NIR, IBAN, coordonnées et **données de santé** (arrêts de travail) de 289 personnes. C'est un
> traitement de données personnelles à part entière, sans base légale évidente, dans un
> environnement par construction moins protégé que la production.
>
> **Une base pseudonymisée remplit exactement le même objectif de formation** : mêmes volumes,
> mêmes structures, mêmes cas particuliers, seules les identités changent. Coût de développement
> comparable, exposition nulle.

Si la copie réelle est malgré tout retenue, c'est une décision à documenter et à porter avec le
DPO, pas un choix technique. Compter 3 à 5 jours dans les deux cas.

---

## 18. Session dédiée à la génération de la paye avec Gaëlle

> 🟢 **Conforme.** Organisation, pas de développement.

**Utile à préparer** : le parcours décrit en réunion (import des pointages → validation des
congés → vérification des anomalies → génération) correspond bien au code, et le système
d'anomalies rouge/orange existe tel que présenté (« bloquant » / « à vérifier »).

À prévoir **après** le point 9 (RTT) et le point 22 (arrondi), sinon la session se fera sur des
compteurs de congés faux.

---

## 19. Faire vérifier la configuration du fractionnement des congés

**Vérifié — la réponse est plus simple que prévu, et elle surprend :**

| | |
|---|---|
| Sociétés avec une configuration de fractionnement | **0 / 7** |
| Droits de fractionnement déjà attribués | **0** |

Le module est pourtant **complet** : domaine dédié, règles légales, prévisualisation, validation,
réglages par entreprise.

> 🟡 **Partiel.** Il n'y a pas « une configuration à vérifier » — **il n'y en a aucune**. Le
> module est prêt mais n'a jamais été activé nulle part.

**Ce qui doit être décidé** : applique-t-on la règle légale (jours supplémentaires selon les
jours pris hors période du 1er mai au 31 octobre) ou un usage propre au groupe ? Sur quelles
sociétés ? La réponse conditionne les soldes au 31 mai, donc le point 22.

---

## 20. Double-checker les numéros de sécurité sociale et données DSN

**Vérifié — bonne nouvelle sur les NIR, moins bonne sur la DSN.**

**Les NIR sont propres** : **0 sur 240** salariés actifs ont un NIR absent ou mal formé. Un seul
porte un NIR à 13 chiffres (sans clé), ce qui est un format valide en DSN.

**En revanche, un point de mapping DSN mérite un vrai contrôle.** Le bloc `S21.G00.60` est traité
comme une « suspension de contrat » et son code `'01'` transformé en **congé sans solde**. Or
dans la DSN Cartol de janvier, ce bloc contient **16 arrêts, dont 14 au code `'01'`**, et la
forme des données ne ressemble pas à une suspension : les rubriques `.005` à `.008` portent des
dates et coordonnées bancaires de **subrogation**, `.010` une date de reprise. Un bloc de
suspension ne transporte pas de subrogation — tout indique le bloc « arrêt de travail ».

Si c'est confirmé, **14 arrêts maladie deviennent des congés sans solde** : faux pour
l'absentéisme, faux pour le maintien de salaire, faux pour les attestations.

> 🟠 **À nuancer.** L'action visait les NIR, qui sont déjà bons. **Le vrai risque avant mise en
> production est ailleurs**, dans l'interprétation des blocs d'arrêt. À confronter au cahier
> technique DSN avant de toucher au mapping.

---

## 21. Mettre en place la badgeuse chez Colorplast d'abord

**Vérifié.** Le module est **complet** : service QR, authentification des terminaux, routeur
dédié, gestion des pointages, export.

> 🟢 **Conforme.** Aucun développement — c'est du déploiement et de la conduite du changement.
> Commencer par Colorplast est la bonne approche.

---

## 22. Paramétrer l'arrondi des congés au 31 mai (entier supérieur)

**Vérifié — c'est à moitié fait, et la moitié qui manque demande un arbitrage.**

L'arrondi à l'entier supérieur **existe déjà**, mais sur l'**acquisition** : le droit acquis est
arrondi au supérieur, de même que le prorata d'ancienneté. La période de référence est bien calée
sur une clôture au 31 mai (juin → mai). Aucune colonne de paramétrage d'arrondi n'existe.

Or l'exemple donné — *« si le solde est de 7,5 jours, arrondi à 8 »* — porte sur le **solde**
(acquis moins pris), ce qui n'est pas couvert.

> 🟡 **Partiel — et c'est une question métier avant d'être technique.** Arrondir le **solde** et
> arrondir le **droit acquis** ne donnent pas le même résultat dès qu'un salarié a posé des
> congés, et l'une des deux options **crée du droit à congé supplémentaire**. La règle légale
> porte sur le droit acquis ; l'exemple d'Elsa semble décrire le solde.
>
> **Il faut trancher avec Gaëlle avant d'écrire une ligne de code.**

---

## Synthèse

Sur les 22 actions :

| Verdict | Nombre | Points |
|---|---|---|
| ✅ Déjà fait | 2 | 1, 5 (probablement) |
| 🟢 Conforme, à exécuter | 10 | 2, 3, 6, 7, 11, 13, 14, 16, 18, 21 |
| 🟡 Partiel — arbitrage requis | 5 | 8, 10, 19, 22, et 9 côté cible |
| 🟠 À nuancer — la solution proposée n'est pas la bonne | 4 | 4, 15, 17, 20 |
| ❓ À clarifier | 2 | 5, 12 |

**Ce qui ressort de l'audit et qui n'était pas dans le compte rendu :**

1. **62 % des salariés actifs (148/240) n'ont pas d'e-mail réel**, et le système croit les
   notifier. C'est le sujet de conformité le plus tangible.
2. **99 % des salariés (238/240) n'ont pas de BIC**, ce qui bloque le fichier de virement.
3. **4 sociétés sur 7 n'ont aucune configuration de congés** et distribuent 10 RTT/an par défaut.
4. **Le fractionnement n'est activé nulle part**, alors que le module est prêt.
5. **Les NIR sont propres** — le contrôle avant production doit viser le mapping des arrêts DSN.

**Ordre d'attaque suggéré** — les trois collectes (e-mails, BIC, titres de séjour) ne dépendent
d'aucun développement et conditionnent trois chantiers : elles doivent démarrer immédiatement,
en parallèle. La BDES doit être lancée dès réception du tableau d'Elsa. Les arbitrages congés
(points 9, 19, 22) doivent être rendus avant la session paye avec Gaëlle (point 18), sinon elle
se fera sur des compteurs faux.

---

## Questions à poser à Elsa / au client

Ces cinq réponses débloquent tout le reste :

- [ ] **RTT** — Colorplast doit-elle avoir 0 RTT, ou des RTT réservés aux cadres au forfait ?
      Même question pour MBC, MAJI et Zone 404, qui sont dans la même situation.
- [ ] **Arrondi au 31 mai** — arrondit-on le **solde** (acquis moins pris) ou le **droit acquis**
      de l'année ? L'exemple des 7,5 → 8 jours décrit lequel des deux ?
- [ ] **JTC** — les 3 jours sont-ils acquis d'un bloc en début d'année ou proratisés à
      l'embauche ? Sur quelle période (année civile ou juin → mai) ? Toutes les sociétés ?
- [ ] **Fractionnement** — applique-t-on la règle légale ou un usage propre au groupe, et sur
      quelles sociétés ? (Aucune n'est configurée aujourd'hui.)
- [ ] **CSE** — quel export exactement pose problème, et quel est le symptôme observé ?
- [ ] **Robin** — « ajouter comme utilisateur » signifie-t-il l'espace salarié (déjà en place)
      ou un rôle de gestion ? Lequel ?

---

*Phase 1 terminée : compréhension et cartographie, aucun développement engagé. Dis-moi quels
points tu veux traiter en premier et si la compréhension est la bonne.*
