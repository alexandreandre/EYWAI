# Sens de l'image avant lecture d'un relevé de pointage

Question d'Alexandre du 19/09/2026 : le lecteur de pointages met-il l'image
dans le bon sens avant de la lire ? Réponse : indirectement, et avec un angle
mort. La chaîne (`app/shared/infrastructure/documents/text_extraction.py`,
`render_document_pages` puis `_ocr_image_adaptive`) lit l'image par l'OCR telle
quelle ; si le texte n'est pas jugé fiable, elle essaie l'angle proposé par
Tesseract (OSD) puis 90°, 180° et 270°, et garde l'orientation dont le texte
score le mieux. C'est cette image réorientée qui part au modèle de vision.

Angles morts constatés :

- l'orientation **EXIF** n'est pas lue : une photo de téléphone prise en
  portrait est stockée couchée avec un tag « tourner de 90° » que `Image.open`
  ignore ; on ne compte que sur l'OCR pour la redresser ;
- le choix repose sur l'OCR : sur une feuille manuscrite floue ou de biais, les
  quatre orientations peuvent scorer zéro ; l'égalité se résout en faveur de
  l'original, et le modèle de vision reçoit une image couchée ou à l'envers ;
- rien côté front, le navigateur envoie le fichier tel quel.

## Conception

Quatre étages, dans l'ordre où l'image passe :

1. **À l'ouverture** — `ImageOps.exif_transpose` quand le tag EXIF (2 à 8) le
   demande (image seule ; les pages PDF n'ont pas d'EXIF). Déterministe, couvre
   le cas le plus fréquent. **L'EXIF tranche** : l'OCR lit ensuite l'image mais
   ne cherche plus de rotation — sur une vraie feuille Colorplast, la course OCR
   (scores de bruit, 1 contre 0) re-tournait de travers une photo déjà redressée.
2. **L'OSD de Tesseract pour le côté (90/270).** Mesuré sur trois feuilles
   manuscrites Colorplast tournées dans les quatre sens, à 200 et 300 dpi : juste
   24 fois sur 24 en brut, 8 fois sur 8 pour les images de côté en JPEG, à des
   confiances de 0,1 à 2,1 — l'ancien code exigeait 5 et ne l'écoutait donc
   jamais. Mais à ces confiances il confond droite et à l'envers (image droite en
   JPEG → « 180 », à l'envers → « 0 ») : on ne le croit que pour 90/270.
3. **Le texte OCR de l'image obtenue** — s'il atteint le seuil de fiabilité,
   l'image est droite, on s'arrête là. La course aux scores (0/90/180/270)
   **ne décide plus** : à 200 dpi, l'image droite scorait 0 et sa variante à
   90° scorait 22, Tesseract lisant lui-même le texte couché ; le score dit si
   Tesseract s'en est sorti, pas si l'image est droite.
4. **Dernier ressort, le modèle de vision** — texte pauvre (feuille manuscrite) :
   on lui montre l'image obtenue et on lui demande l'angle de redressement,
   réponse structurée `{"rotation_horaire": 0 | 90 | 180 | 270}` sur l'image
   réduite ; c'est lui qui tranche droite ou à l'envers. Une fois par document,
   sur la page 1 ; les pages suivantes d'un PDF suivent l'angle de la page 1.
   Modèle non configuré, réponse hors des quatre valeurs ou erreur : l'image
   reste telle quelle — jamais d'échec de lecture pour ça.

Le résultat rendu (`RenderedPage`) porte l'angle finalement appliqué et la
source de la décision (`exif`, `osd`, `ocr`, `vision`, `aucune`) pour le
diagnostic.

## Tests

- image avec tag EXIF « 90° » → redressée à l'ouverture, aucune autre décision ;
- OSD « Rotate: 90 » → rotation PIL 270 ; OSD muet → None ;
- de côté selon l'OSD → redressée ; texte fiable → fin, sans modèle ;
- OSD « 180 » et texte fiable → image gardée telle quelle (OSD non cru sur 0/180) ;
- texte pauvre et modèle répondant 180 → l'image envoyée à la vision est
  retournée ; les rotations OSD et modèle s'additionnent ;
- texte pauvre, modèle absent ou sans avis → image telle quelle, pas d'erreur ;
- la course aux scores n'est jamais appelée pour l'orientation.

## Hors périmètre

Rotation page par page d'un PDF mélangé ; correction côté navigateur.
