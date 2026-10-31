# Prêt de l'employeur : le plafond légal de la retenue (D7)

Date : 31/10/2026. Feuille de route du 30/10, chantier 4, D7 : « prêt au départ : garder le plafond légal, l'expliquer à Elsa ».

## Ce que disent les sources (ouvertes le 31/10)

- Code du travail, L3251-1 à L3251-3 (Légifrance) : pas de compensation pour fournitures diverses ; une avance en espèces se retient par retenues successives d'au plus un dixième des salaires exigibles, et « la retenue opérée à ce titre ne se confond pas avec la partie saisissable ».
- Cass. soc., 15 janvier 2014, n° 12-19.739 (Légifrance, JURITEXT000028489016) : « toutes les créances de l'employeur à l'égard d'un salarié, autres que celles visées aux articles L. 3251-1 et L. 3251-3, peuvent donner lieu à compensation dans la limite de la fraction saisissable du salaire » ; « la créance de l'employeur résultant d'un prêt consenti à un salarié dans le cadre d'une convention distincte du contrat de travail pour une durée spécifique ne constitue pas une avance sur salaire ». La cour d'appel qui appliquait le dixième est cassée.
- Cass. soc., 4 avril 2006 (texte reproduit par imavocats.fr) : la compensation du prêt avec le salaire « ne peut s'appliquer que sur la fraction saisissable » ; une retenue qui absorbe tout le salaire du mois est abusive.
- L3252-1 à L3252-3 (Légifrance) : la quotité vise « les sommes dues à titre de rémunération » ; la base est la rémunération et ses accessoires, après cotisations et prélèvement à la source, sans « les indemnités insaisissables » ni les remboursements de frais. L'indemnité de licenciement « n'a pas le caractère de salaire » (manuel, Cairn 2023 ; Lefebvre-Dalloz la range parmi les indemnités insaisissables).

## Ce qui existe

- Depuis le 05/10 (3aec9ecb), la retenue d'un prêt est plafonnée au dixième du salaire exigible, le prêt étant « assimilé » à une avance. C'est la lecture que l'arrêt de 2014 casse : les prêts de Martine ont leur contrat et leur échéancier (`template_contrat_pret.html`). Le dixième retient moins que la loi le permet sur un salaire moyen, et plus sur un petit salaire : 80 € sur 800 € de net, quand la quotité est de 68,59 €.
- Les intérêts s'ajoutent au capital plafonné : le total peut dépasser le plafond.
- Au départ, Martine retient l'échéance du mois ; le reste dû s'affiche au dossier de sortie. Le contrat ne prévoit rien pour le départ.
- La base saisissable des saisies compte les indemnités de rupture du bulletin de sortie (`indemnites_sortie.total_exonerees`, ajoutées au net).
- En base au 31/10 : aucun prêt, aucun bulletin avec une indemnité de rupture, une seule saisie. Rien ne change sur un bulletin existant.

## La règle

- **Plafond du prêt** : la quotité saisissable du mois (barème légal de l'année, lu en base) moins ce que les saisies sur salaire en ont déjà pris ; jamais plus que le net encore disponible. Plusieurs prêts se partagent ce qui reste, dans l'ordre.
- **Base** : celle des saisies (`base_saisissable`), prise avant les retenues : les saisies et les avances déjà retirées du net y reviennent.
- **Personnes à charge** : celles déclarées pour la saisie en cours du mois (le module des saisies les écrit au bulletin), sinon aucune.
- **Capital et intérêts tiennent ensemble** sous le plafond ; les intérêts restent au prorata du capital retenu.
- **Indemnités de rupture** (licenciement, rupture conventionnelle, mise à la retraite) hors de la base saisissable, pour les saisies comme pour les prêts.
- **Sans barème** : rien n'est retenu et le bulletin le dit.
- **Le bulletin** dit, quand l'échéance n'est pas retenue en entier : combien, sur combien, la quotité du mois et ce que les saisies ou un autre prêt en ont pris, le reliquat.
- **Contrat de prêt** : « dans la limite de la fraction saisissable du salaire », avec l'arrêt.
- **Hors lot** : retenir tout le reste dû au départ (exigibilité anticipée). La loi le borne à la même quotité ; sans prêt en base, c'est un cas de niche : la RH ajoute la retenue à la main sur le solde de tout compte, ou le salarié rembourse directement. La pratique de Vanessa et Gaëlle (« tout le reste dû au solde de tout compte ») dépasse la loi dès que ce reste dépasse la quotité ; c'est ce qu'on explique à Elsa.

## Tests

- Domaine : plafond = quotité − saisies, borné au net ; base sans les indemnités de rupture, nommées dans la composition.
- Enrichissement : rejeu G.3 retenu en entier (quotité 274,63 € sur 1 619,54 €) ; saisie qui prend presque tout ; un second prêt sans reste ; personnes à charge de la saisie ; net qui limite ; barème absent ; bulletin de sortie avec indemnité de licenciement ; la quotité se calcule sur le net avant l'avance.
