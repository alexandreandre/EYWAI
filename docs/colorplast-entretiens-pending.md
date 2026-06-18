# Entretiens Colorplast — points en attente client

## Guide + passeport (bibliothèque)

Questions à poser à la sœur / au client avant implémentation :

1. **« Guide »** — de quel document s'agit-il ?
   - Guide de préparation pour le salarié avant l'entretien ?
   - Guide RH sur les obligations légales (2 ans / 6 ans) ?
   - Document interne Colorplast (procédure, charte) ?

2. **« Passeport »** — s'agit-il du **passeport de compétences** (suivi formation / évolution lié à l'entretien professionnel) ?

3. **Usage attendu**
   - Simple dépôt en bibliothèque entreprise (consultation RH / salarié) ?
   - Génération ou remplissage automatique par salarié dans l'application ?

4. **Format** — PDF, Word, les deux ? Fichiers à fournir par Colorplast.

## Convocation — modèle définitif

Le PDF de convocation actuel utilise un **format standard EYWAI** (ReportLab).  
Quand le modèle Colorplast sera disponible (texte, mise en page, signature DG), remplacer le contenu dans :

`backend/app/modules/annual_reviews/infrastructure/convocation_pdf.py`

## Configuration entreprise

Sur la fiche Colorplast, renseigner :

- **Nom du signataire** = Directeur Général de l'entreprise (pas du groupe)
- **Qualité du signataire** = « Directeur Général »
