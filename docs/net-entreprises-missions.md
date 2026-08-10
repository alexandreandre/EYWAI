# net-entreprises — ce qui est tranché, ce qui reste, comment le chercher

**Document de travail, pour la session suivante.** Il existe pour éviter deux
gâchis : rouvrir une question déjà tranchée, et relancer Elsa sur ce qu'on peut
obtenir soi-même.

Les identifiants et les relevés nominatifs sont dans `data/_acces/net-entreprises.md`,
gitignoré. Ici, rien que de la méthode et des constats.

---

## Le canal

Aucun lien direct n'existe entre moi et l'agent navigateur. Il n'est pas dans la
liste des agents joignables, il n'y a ni API ni session partagée. La boucle est
donc, à chaque fois :

> j'écris une mission → Alexandre la colle dans Claude dans Chrome → il me colle
> le compte rendu.

C'est lent, et c'est la contrainte qui justifie tout le reste : **une mission
doit revenir avec sa réponse du premier coup**, parce qu'un aller-retour coûte
cher.

---

## Tranché — ne pas rouvrir

### Le portail ne donne pas les comptes rendus DSN

Vérifié le 08/08/2026, deux fois. La seconde inspection a testé **deux
échéances** (juin et juillet 2026), **deux chemins d'accès**, et a lu la
**structure des pages** au lieu de leur rendu visuel.

Sur `dsnrg.net-entreprises.fr/cnxrg/detaildecla`, tous les retours — CRM
identité, contrôle d'identité, contrôles inter-déclarations, URSSAF,
AGIRC-ARRCO, prévoyance, et **DGFiP « Données nominatives »** — sont du texte
statique. Aucun lien, aucun bouton.

Conséquences, définitives :

- **Scripter une connexion ne servirait à rien** : il n'y a aucun fichier à
  récupérer. La question « on ne peut pas juste faire une connexion ? » a été
  posée deux fois ; la réponse est non, et elle est établie.
- Les taux PAS passeront par **Cegid**, qui reçoit les CRM — c'est précisément
  pour ça que le portail ne les expose pas. `pas_rates/application/ingest.py`
  sait déjà lire un CRM. Plan B : l'API DSN de net-entreprises, souscription
  hors portail plus certificat cachet serveur, des semaines.

Trois fausses pistes fermées, pour ne pas les reprendre :

| Piste | Réalité |
|---|---|
| « Télécharger au format PDF » du certificat de conformité | Ouvre une pop-up de texte brut. Libellé trompeur |
| Page « Gestion des retours TPT » | **TPT = Temps Partiel Thérapeutique**, pas tiers prestataire technique. Aucun routage |
| « Autres services → BIS Régime général » | Renvoie au même tableau de bord |

### Rien d'autre à attendre du compte lui-même

- **Aucune gestion d'API ni de certificat** dans le compte (~20 min de parcours
  complet des menus).
- **Aucun écran pour rattacher un nouveau SIREN.** Ajouter Cartol, LEWIS et
  Zone 404 est une démarche qui part de l'entreprise cliente. À faire faire par
  Elsa, pas par nous.
- Le compte tiers-déclarant couvre **4 SIREN sur 7** : MBC, Comitech, MAJI,
  Colorplast.

### Ne pas tester les autres comptes

Les identifiants Comitech et Colorplast reçus séparément portent sur des SIREN
que le compte principal voit déjà. Les essayer, c'est risquer de bloquer le
compte de deux personnes pour une information qu'on possède. Laissés en « non
testés, probablement redondants ».

---

## Reste à chercher — trois missions

Le portail garde trois choses qu'EYWAI n'a pas, et aucune ne concerne le PAS.

### ~~Mission A — DSN-VAL~~ ✅ faite le 10/08/2026

**DSN-VAL n'est pas un service en ligne, c'est une application locale** à
télécharger (110 Mo, Java). Donc aucune donnée ne sort du poste, et l'agent
navigateur n'a servi qu'à trouver le lien : la validation tourne ici.

Résultat dans **`docs/dsn-val-diagnostic.md`**. En bref : les cinq fichiers du
cabinet passent à **0 anomalie**, les nôtres de 628 à 7 250 — mais pour
seulement **34 règles distinctes**, les mêmes partout. La question #17 à Elsa
(la nomenclature des codes de cotisation) devient inutile : le validateur donne
le diagnostic sans elle.

Rejouer : `scripts/dsn_generer_pour_validation.py` puis `scripts/dsn_valider.py`.

<details>
<summary>Énoncé d'origine, conservé</summary>

### Mission A — DSN-VAL, le validateur officiel

Repéré dans le menu **Outils de Contrôle** (avec « DSN contrôle SIRET » et
« DSN-FPOC »).

**Ce que ça débloque : le point #20.** Notre export DSN est marqué « non
déposable », avec 100 à 120 rubriques manquantes selon la société. Le validateur
officiel dit lesquelles, fichier en main.

**Et ça peut supprimer une question à Elsa.** La question #17 lui demande « la
nomenclature officielle des codes de cotisation ». Si le validateur nous donne
le diagnostic, on n'a plus à la demander — même schéma que le fichier BIC et la
provision CP, dont les réponses étaient déjà chez nous.

On sait produire le fichier : `build_parsed_dsn_from_payroll`
(`app/modules/dsn_export/application/builder.py`), déjà utilisé par
`scripts/dsn_conformance_report.py`.

> ⚠️ **Le seul endroit du chantier où un agent peut faire un dégât.** Toutes les
> missions précédentes disaient « ne clique sur rien qui envoie ». Celle-ci
> demande de téléverser. L'interdiction doit être réécrite au scalpel :
>
> *Tu peux déposer un fichier dans l'outil de **contrôle**. Tu ne dois JAMAIS le
> déposer dans le service de **déclaration**. Un contrôle ne déclare rien ; un
> dépôt est une déclaration sociale réelle et irréversible.*
>
> Garde-fou supplémentaire : commencer par une DSN d'un **mois déjà déposé**. Si
> quelque chose partait de travers, ce serait un doublon détectable, pas une
> fausse déclaration.

</details>

### ~~Mission B — Fiches de paramétrage des OC~~ ✅ faite le 10/08/2026

**14 fiches récupérées**, rangées en `data/<societe>/referentiel/fpoc/`.
Résultat dans **`docs/fiches-parametrage-oc.md`**. Les fiches portent les
numéros de rubrique DSN en tête de colonne : la correspondance est donnée. Elles
règlent aussi la question posée à Elsa le 05/08 sur les deux comptes de
prévoyance de Colorplast — **Mutex pour les non-cadres, Alptis pour les cadres**.

<details>
<summary>Énoncé d'origine, conservé</summary>

### Mission B — Fiches de paramétrage des OC

Repérées dans le menu **Outils de Paramétrage**.

**Ce que ça débloque : les codes prévoyance et mutuelle.** C'est une cause
racine identifiée du backtest Comitech (mutuelle et prévoyance non liées), et
l'export DSN a dû corriger trois codes à l'aveugle contre les fichiers du
cabinet. La fiche de paramétrage est la source officielle, par organisme et par
contrat.

À récupérer pour les quatre SIREN accessibles.

</details>

### ~~Mission C — Serveur de nomenclatures DSN~~ — sans objet

**DSN-VAL embarque déjà la nomenclature officielle** : le jar
`n4ds.dsn.p03v01.all` contient les tables NEODeS (IDCC, PCS-ESE, pays, codes
risque AT…) et le validateur nomme lui-même chaque rubrique dans ses rapports.
Aucune raison de retourner sur le portail pour ça.

<details>
<summary>Énoncé d'origine, conservé</summary>

### Mission C — Serveur de nomenclatures DSN

Dans le menu **Référentiels**.

**Ce que ça débloque : une vérification.** On a reconstitué la nomenclature
depuis le cahier technique NEODeS (`data/_dsn_conformance/nomenclature-reconstituee.md`).
Le serveur officiel permet de la confronter au lieu de la croire sur parole.
Mission courte, à faire en dernier.

---

</details>

## Méthode — ce qui fait converger

Tiré de deux échanges, un raté et un réussi.

1. **Une mission par échange.** Le premier compte rendu, trop large, est revenu
   avec des « faute de temps » et une conclusion fausse sur les CRM. Le second,
   ciblé sur cinq questions fermées, a tranché.
2. **Exiger l'URL et la suite exacte des clics.** C'est ce qui rend un résultat
   vérifiable, et réutilisable si on automatise.
3. **Exiger un verdict, et ce qui a été essayé pour l'obtenir.** « Environ
   20 minutes, deux passages dans l'arborescence » vaut infiniment mieux qu'un
   « je n'ai pas trouvé » sec. Demander explicitement de distinguer *je n'ai pas
   trouvé* de *ça n'existe pas*, et de tenter deux chemins avant de répondre non.
4. **Lui donner ce qu'on sait déjà**, pour qu'il ne refasse pas le chemin.

5. **Toujours dire sur quel compte être connecté**, en tête de mission. C'est la
   première chose qu'Alexandre a besoin de savoir pour lancer l'échange, et
   l'oublier lui coûte un aller-retour. Par défaut : le compte tiers-déclarant
   déjà ouvert, ligne `mbc` du coffre, qui couvre les 4 SIREN. Préciser aussi
   « ne change pas de compte, ne te déconnecte pas ».

Et trois consignes permanentes, à recopier dans chaque mission :

- Ne jamais saisir d'identifiant ni de mot de passe ; la session est ouverte.
- S'arrêter net devant une demande de code SMS, de code par mail, de paiement
  ou de changement de mot de passe.
- Ne recopier **aucune donnée nominative** : les comptes rendus contiennent des
  noms, des NIR et des taux d'imposition. Décrire un fichier par son nombre de
  lignes et ses colonnes.

L'agent signale spontanément l'absence d'instruction cachée dans les pages
visitées. C'est une bonne hygiène, continuer à la demander.

---

## Journal

| Date | Mission | Résultat |
|---|---|---|
| 08/08/2026 | Inspection large : SIREN, services, historique DSN, CRM, AT/MP | Le compte couvre 4 SIREN. Taux AT/MP MBC 3,14 %, conforme à EYWAI. DSN juin et juillet déposées. **Conclusion erronée sur les CRM**, faute d'avoir ouvert le détail des déclarations |
| 08/08/2026 | Cinq questions fermées, avec exigence de verdict et de chemin | CRM non récupérables, **confirmé**. TPT élucidé. Ni API ni certificat dans le compte. Pas d'ajout de SIREN possible. MECELEC INDUSTRIES = déclarant administrateur du SIRET de MBC |
| 10/08/2026 | Mission A — DSN-VAL | L'agent s'est arrêté au bon endroit : DSN-VAL est une **application locale**, pas un service web. Il a rapporté le lien et les prérequis, la validation a tourné ici. **Bon exemple** : la mission prévoyait ce cas de figure à l'étape 1, ce qui a évité un aller-retour |

## Deux points ouverts, côté Elsa

- **Rattacher Cartol, LEWIS et Zone 404** au compte tiers-déclarant. La démarche
  part de l'entreprise cliente ; nous ne pouvons pas la lancer.
- **MECELEC INDUSTRIES** est administrateur du SIRET de Mont Blanc Composite et
  voit le même tableau de bord que la titulaire du compte. Cette entité n'est
  aucune des sept sociétés. À confirmer comme voulu — ce sont des droits
  d'administration sur des déclarations sociales.
