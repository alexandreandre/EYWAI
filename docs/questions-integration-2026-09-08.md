# Intégration — ce qui est en suspens au 2026-09-08

Source : groupe WhatsApp « MARTINE - MISE EN PROD », 213 messages du 28/08 au
09/09 (heure de Paris), extrait dans `data/_inbox/whatsapp-martine-mise-en-prod/`.
Croisé avec `docs/afaire.md` et `docs/superpowers/plans/2026-09-08-periode-variables-paie.md`.

Le dépôt est public : ce rapport cite des lignes, jamais le contenu nominatif.
Les noms de salariés sont dans `_chat.txt`, qui reste sous `data/`.

**Compte** : 2 bloquants · 3 engagements non tenus · 4 questions sans réponse ·
3 points à trancher · 1 lot livré non confirmé.

---

## Bloquants

### B1 — Une gestionnaire est à l'arrêt sur deux sociétés

Elle n'a aucun bulletin 2026 sur MAJI ; ceux qu'elle génère elle-même sortent
faux sur toutes les périodes depuis janvier. Elle l'a dit deux fois, puis :
« je ne sais pas si je continue étant donné qu'il n'y a aucun historique ».

- **Source** : `_chat.txt:272`, `:275`
- **Engagement pris** (`_chat.txt:451`) : reprendre les paies passées de MAJI,
  puis regarder ZONE 404, et la prévenir quand elle peut reprendre.
- **État** : non fait. Elle attend depuis le 07/09.

### B2 — Le bulletin porte encore la fenêtre glissante

Annoncé le 08/09 comme un bonus (« la vraie période de paie : juillet = 22/06 →
26/07 »), corrigé par la gestionnaire 26 minutes plus tard : le bulletin doit
porter **le mois civil**, du 1er au 31 ; seuls les heures sup et les paniers
décalent.

- **Source** : `_chat.txt:378` (l'annonce), `_chat.txt:384` (la correction)
- **Couvert par** le plan, tâche 8 (`…periode-variables-paie.md:1439`) — écrit,
  pas implémenté.
- **Portée** : tant que ça tient, l'en-tête est faux *et* congés, arrêts et
  primes se rattachent à la mauvaise période.

---

## Engagements pris, non tenus

### E1 — La période des variables configurable
« Je me mets sur ça » (`_chat.txt:438`). Design et plan écrits le 08/09, aucune
ligne de code. Répartition convenue : les fenêtres de **juillet** sont à saisir
côté EYWAI, celles d'**août** par la gestionnaire (`_chat.txt:434`).

Fenêtres données (`_chat.txt:427-431`) :

| Sociétés | Juillet | Août |
|---|---|---|
| MBC, Comitech, Colorplast | 22/06 → 25/07 | 27/07 → 22/08 |
| Cartol, LEWIS | 22/06 → 18/07 | 20/07 → 22/08 |
| MAJI, ZONE 404 | non concernées (`_chat.txt:408`) | — |

### E2 — Activité partielle
Le type n'existe pas dans l'outil. « On doit d'abord caler son traitement en
paie avant de l'ajouter à la légende — je te donne un délai » (`_chat.txt:178`).
Le délai n'a jamais été donné. **Utilisé en ce moment chez LEWIS**
(`_chat.txt:100`).

### E3 — Cerfa S3201 / S6202 télétransmis
Les 4 Cerfa avec exemples ont été envoyés par mail le 03/09 et accusés réception
(« c'est exactement ce qu'il nous faut, on s'y attaque juste après »,
`_chat.txt:180`). Rien de commencé.

---

## Questions restées sans réponse

| Qui → qui | Quand | Question | Ligne |
|---|---|---|---|
| Elsa → Alexandre | 07/09 12:15 | La partie **JEI** est-elle active sur l'environnement de test pour le lab ? | `_chat.txt:216` |
| Elsa → Vanessa | 31/08 17:05 | Le call **Cegid** pour récupérer la clé API. Réponse « je fais un ticket demain » (01/09), puis plus rien — 8 jours. | `_chat.txt:15` |
| Alexandre → Gaëlle | 08/09 20:44 | Les deux bulletins de juillet (EYWAI + Quadra) pour l'écart d'imposable. Jamais envoyés — l'écart a été résolu depuis (mutuelle), reste à confirmer. | `_chat.txt:392` |
| — | 01/09 | La trame de pointage promise au directeur Colorplast, pour des scans lisibles par l'IA. Aucune suite dans le fil. | `_chat.txt:23` |

---

## Points à trancher

### T1 — Le trou du dimanche ⚠️
Toutes les fenêtres données finissent un **samedi** et la suivante démarre le
**lundi**. Les dimanches 19/07, 26/07 et 23/08 ne tombent donc dans aucune
fenêtre : une heure travaillée ou un panier ce jour-là disparaît, sans alerte.

Ces dimanches ferment pourtant des semaines ISO (S29, S30, S34) que le plan
normalise à la semaine.

**À demander avant d'implémenter** : les fenêtres doivent-elles se fermer le
dimanche (fin de semaine complète) plutôt que le samedi ?

### T2 — Primes de présence et d'assiduité chez MBC
Elles sont attribuées d'après les variables, donc décalées elles aussi. « On en
reparlera » (`_chat.txt:426`). Le plan ne les traite pas.

### T3 — Le récap de réunion Notion
Partagé le 28/08 (`_chat.txt:5`), jamais exploité — hors de nos quatre
sources. Personne ne l'a rouvert depuis.

---

## Livré, non confirmé

Le lot du 09/09 01:20 (`_chat.txt:438-443`) : congés affichés au bulletin avec
leurs dates, net imposable corrigé (le complément mutuelle famille était déduit
à tort), heures sup éditables au bulletin. Aucun retour depuis.

---

## Note d'extraction

Les mentions restent des identifiants bruts dans le fil (`@100085773918263`,
`@117257002860683`) : WhatsApp les stocke non résolues dans le texte du message.
L'auteur, lui, est correctement nommé depuis le correctif du 08/09. Un
rapprochement des mentions serait à faire — voir `whatsapp_base.auteur`.
