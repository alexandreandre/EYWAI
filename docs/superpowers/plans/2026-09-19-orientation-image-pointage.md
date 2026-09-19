# Sens de l'image avant lecture — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** qu'une feuille de pointage photographiée ou scannée de travers arrive droite au modèle de vision et à l'OCR.

**Architecture:** trois étages dans `app/shared/infrastructure/documents/text_extraction.py` — redressement EXIF à l'ouverture (`_ouvrir_image`), recherche par OCR inchangée (`_ocr_image_adaptive`), et en dernier ressort une question au modèle de vision (`_demander_orientation_au_modele`) orchestrée par `_orienter`. `render_document_pages` prend un `orientation_model` optionnel ; l'appelant du module pointages le fournit.

**Tech Stack:** Pillow (`ImageOps.exif_transpose`), Tesseract via pytesseract (existant), `extract_structured_json_from_image` (OpenRouter, sortie JSON schématisée).

## Global Constraints

- Spec : `docs/superpowers/specs/2026-09-19-orientation-image-pointage-design.md`.
- Jamais d'échec de lecture à cause de l'orientation : modèle absent, réponse invalide ou exception → image inchangée.
- Une consultation du modèle par document au plus (page 1) ; les pages suivantes d'un PDF suivent l'angle de la page 1.
- Tests unitaires hermétiques : pas de Tesseract ni de réseau (l'OCR et le modèle sont doublés) ; Pillow réel pour le test EXIF (`pytest.importorskip`).
- Commits : uniquement à la demande d'Alexandre (règle du dépôt).

---

### Task 1: Redressement EXIF à l'ouverture

**Files:**
- Modify: `backend/app/shared/infrastructure/documents/text_extraction.py` (import `ImageOps` ; nouvelle `_ouvrir_image` ; `render_document_pages` et `_extract_image` l'utilisent)
- Test: `backend/tests/unit/schedules/test_orientation_image.py` (créer)

**Interfaces:**
- Produces: `_ouvrir_image(file_content: bytes) -> tuple[Image.Image, bool]` — l'image redressée selon son EXIF, et vrai si l'EXIF demandait un redressement.

- [ ] **Step 1: Write the failing test**

```python
"""Le sens de l'image avant lecture : EXIF à l'ouverture, OCR, puis le modèle de vision."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest

from app.shared.infrastructure.documents import text_extraction as te

pytestmark = pytest.mark.unit
pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

_MODULE = "app.shared.infrastructure.documents.text_extraction"


def _jpeg_avec_exif(orientation: int) -> bytes:
    image = Image.new("RGB", (100, 50), "white")
    exif = image.getexif()
    exif[0x0112] = orientation
    buf = io.BytesIO()
    image.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


@patch(f"{_MODULE}._OCR_AVAILABLE", True)
def test_une_photo_couchee_par_son_exif_est_redressee_a_l_ouverture():
    # 6 = « tourner de 90° horaire pour lire » : une photo prise en portrait.
    image, redressee = te._ouvrir_image(_jpeg_avec_exif(6))

    assert image.size == (50, 100)
    assert redressee is True


@patch(f"{_MODULE}._OCR_AVAILABLE", True)
def test_une_image_sans_consigne_exif_est_ouverte_telle_quelle():
    image, redressee = te._ouvrir_image(_jpeg_avec_exif(1))

    assert image.size == (100, 50)
    assert redressee is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest -q tests/unit/schedules/test_orientation_image.py`
Expected: FAIL — `AttributeError: module ... has no attribute '_ouvrir_image'`

- [ ] **Step 3: Write minimal implementation**

Dans l'import optionnel :
```python
    from PIL import Image, ImageEnhance, ImageOps
```
Après `_preprocess_image` :
```python
def _ouvrir_image(file_content: bytes) -> tuple["Image.Image", bool]:
    """Ouvre une image en la redressant selon son EXIF.

    Une photo de téléphone prise en portrait est stockée couchée avec un tag
    « orientation » que `Image.open` ignore : sans ce redressement, seul l'OCR
    pouvait la remettre droite, et il n'y arrive pas sur une feuille manuscrite.
    Rend aussi vrai si l'EXIF demandait un redressement.
    """
    image = Image.open(io.BytesIO(file_content))
    orientation = image.getexif().get(0x0112, 1)
    redressee = ImageOps.exif_transpose(image)
    return (redressee if redressee is not None else image), orientation not in (None, 1)
```
Dans `render_document_pages`, branche image : `image = Image.open(io.BytesIO(file_content))` → `image, _ = _ouvrir_image(file_content)`. Dans `_extract_image` : idem.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest -q tests/unit/schedules/test_orientation_image.py tests/unit/schedules/test_render_document_pages.py tests/unit/shared/test_text_extraction.py`
Expected: PASS

---

### Task 2: Le modèle de vision donne l'angle en dernier ressort

**Files:**
- Modify: `backend/app/shared/infrastructure/documents/text_extraction.py` (constantes `_ROTATIONS_HORAIRES`, `_ORIENTATION_SCHEMA`, `_ORIENTATION_SYSTEM_PROMPT` ; nouvelle `_demander_orientation_au_modele`)
- Test: `backend/tests/unit/schedules/test_orientation_image.py`

**Interfaces:**
- Consumes: `extract_structured_json_from_image(system_prompt, user_prompt, image_bytes, mime_type, json_schema, schema_name, model, max_tokens) -> StructuredExtractionResult | None` (`.data: dict`), `_image_to_vision_bytes(image) -> (bytes, mime)`.
- Produces: `_demander_orientation_au_modele(image, model: str) -> int | None` — angle **horaire** 0/90/180/270, None si indisponible ou invalide.

- [ ] **Step 1: Write the failing tests**

```python
@patch(f"{_MODULE}._image_to_vision_bytes", return_value=(b"jpg", "image/jpeg"))
@patch("app.shared.infrastructure.ai.structured_vision.extract_structured_json_from_image")
def test_le_modele_repond_un_angle_horaire(mock_extract, _bytes):
    mock_extract.return_value = MagicMock(data={"rotation_horaire": 90})

    assert te._demander_orientation_au_modele(MagicMock(), "vision-x") == 90
    appel = mock_extract.call_args.kwargs
    assert appel["model"] == "vision-x"
    assert appel["json_schema"]["properties"]["rotation_horaire"]["enum"] == [0, 90, 180, 270]


@patch(f"{_MODULE}._image_to_vision_bytes", return_value=(b"jpg", "image/jpeg"))
@patch("app.shared.infrastructure.ai.structured_vision.extract_structured_json_from_image")
def test_une_reponse_hors_des_quatre_angles_est_ignoree(mock_extract, _bytes):
    mock_extract.return_value = MagicMock(data={"rotation_horaire": 45})

    assert te._demander_orientation_au_modele(MagicMock(), "vision-x") is None


@patch(f"{_MODULE}._image_to_vision_bytes", return_value=(b"jpg", "image/jpeg"))
@patch("app.shared.infrastructure.ai.structured_vision.extract_structured_json_from_image")
def test_un_modele_indisponible_ne_fait_pas_echouer_la_lecture(mock_extract, _bytes):
    mock_extract.side_effect = RuntimeError("clé API absente")

    assert te._demander_orientation_au_modele(MagicMock(), "vision-x") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest -q tests/unit/schedules/test_orientation_image.py -k modele`
Expected: FAIL — `AttributeError: ... '_demander_orientation_au_modele'`

- [ ] **Step 3: Write minimal implementation**

Constantes à côté de `_OCR_RELIABILITY_MIN_SCORE` :
```python
#: Angles que le modèle de vision peut proposer, en degrés dans le sens horaire.
_ROTATIONS_HORAIRES = (0, 90, 180, 270)
_ORIENTATION_SCHEMA = {
    "type": "object",
    "properties": {"rotation_horaire": {"type": "integer", "enum": [0, 90, 180, 270]}},
    "required": ["rotation_horaire"],
    "additionalProperties": False,
}
_ORIENTATION_SYSTEM_PROMPT = (
    "Tu redresses des documents scannés ou photographiés (feuilles de pointage, "
    "relevés d'heures). Réponds uniquement par l'angle, en degrés dans le sens "
    "horaire, dont il faut tourner l'image pour que son texte se lise normalement ; "
    "0 si elle est déjà droite."
)
```
Fonction, après `_ocr_image_adaptive` :
```python
def _demander_orientation_au_modele(image: "Image.Image", model: str) -> int | None:
    """Angle horaire (0/90/180/270) proposé par le modèle de vision, None sinon.

    Dernier ressort quand l'OCR n'a rien départagé (feuille manuscrite floue ou
    de biais). Modèle non configuré, réponse hors des quatre angles ou erreur :
    None — l'orientation ne fait jamais échouer une lecture.
    """
    try:
        from app.shared.infrastructure.ai.structured_vision import (
            extract_structured_json_from_image,
        )

        octets, mime = _image_to_vision_bytes(image)
        resultat = extract_structured_json_from_image(
            system_prompt=_ORIENTATION_SYSTEM_PROMPT,
            user_prompt=(
                "De combien de degrés, dans le sens horaire, faut-il tourner cette "
                "image pour la lire ?"
            ),
            image_bytes=octets,
            mime_type=mime,
            json_schema=_ORIENTATION_SCHEMA,
            schema_name="orientation_document",
            model=model,
            max_tokens=20,
        )
    except Exception as exc:
        logger.warning("Orientation par le modèle de vision indisponible : %s", exc)
        return None
    if not resultat:
        return None
    angle = resultat.data.get("rotation_horaire")
    return int(angle) if angle in _ROTATIONS_HORAIRES else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest -q tests/unit/schedules/test_orientation_image.py`
Expected: PASS

---

### Task 3: `_orienter` enchaîne les trois étages ; `render_document_pages` les porte

**Files:**
- Modify: `backend/app/shared/infrastructure/documents/text_extraction.py` (`RenderedPage.orientation_angle/orientation_source` ; dataclass `ImageOrientee` ; `_orienter` ; `render_document_pages(..., *, orientation_model=None)`)
- Modify: `backend/app/modules/schedules/application/timesheet_hybrid_extract.py:262` (passe `orientation_model=timesheet_vision_model()`)
- Test: `backend/tests/unit/schedules/test_orientation_image.py`

**Interfaces:**
- Consumes: `_ocr_image_adaptive(image) -> (texte, psm, image_orientee, angle)` ; `_ocr_image_for_orientation(image) -> (texte, psm, score)` ; `_orientation_quality_score(texte) -> int` ; Task 2.
- Produces: `_orienter(image, *, orientation_model: str | None) -> ImageOrientee(texte, psm, image, angle, source)` avec `source ∈ {"ocr", "vision", "aucune"}` et `angle` la rotation PIL (anti-horaire) appliquée ; `RenderedPage.orientation_angle: int`, `RenderedPage.orientation_source: str ∈ {"exif", "ocr", "vision", "aucune"}`.

- [ ] **Step 1: Write the failing tests**

```python
@patch(f"{_MODULE}._OCR_AVAILABLE", True)
@patch(f"{_MODULE}._ocr_image_for_orientation", return_value=("LUNDI MARDI DEBUT FIN", 6, 20))
@patch(f"{_MODULE}._demander_orientation_au_modele", return_value=180)
@patch(f"{_MODULE}._ocr_image_adaptive")
def test_ocr_indecis_le_modele_de_vision_tranche(mock_adaptive, mock_modele, _ocr):
    image, tournee = MagicMock(name="image"), MagicMock(name="tournee")
    image.rotate.return_value = tournee
    mock_adaptive.return_value = ("", 6, image, 0)

    o = te._orienter(image, orientation_model="vision-x")

    mock_modele.assert_called_once_with(image, "vision-x")
    image.rotate.assert_called_once_with(180, expand=True)
    assert (o.image, o.angle, o.source) == (tournee, 180, "vision")
    assert o.texte == "LUNDI MARDI DEBUT FIN", "l'OCR est refait sur l'image redressée"


@patch(f"{_MODULE}._OCR_AVAILABLE", True)
@patch(f"{_MODULE}._ocr_image_for_orientation", return_value=("S18 LUNDI", 6, 13))
@patch(f"{_MODULE}._demander_orientation_au_modele", return_value=90)
@patch(f"{_MODULE}._ocr_image_adaptive")
def test_un_angle_horaire_devient_une_rotation_pil_anti_horaire(mock_adaptive, _modele, _ocr):
    image = MagicMock()
    mock_adaptive.return_value = ("", 6, image, 0)

    o = te._orienter(image, orientation_model="vision-x")

    image.rotate.assert_called_once_with(270, expand=True)
    assert o.angle == 270


@patch(f"{_MODULE}._OCR_AVAILABLE", True)
@patch(f"{_MODULE}._demander_orientation_au_modele")
@patch(f"{_MODULE}._ocr_image_adaptive")
def test_ocr_fiable_le_modele_n_est_pas_consulte(mock_adaptive, mock_modele):
    image = MagicMock()
    mock_adaptive.return_value = (
        "Total pour la semaine 12/05/2026 13/05/2026 14/05/2026", 6, image, 0
    )

    o = te._orienter(image, orientation_model="vision-x")

    mock_modele.assert_not_called()
    assert (o.image, o.angle, o.source) == (image, 0, "aucune")


@patch(f"{_MODULE}._OCR_AVAILABLE", True)
@patch(f"{_MODULE}._demander_orientation_au_modele")
@patch(f"{_MODULE}._ocr_image_adaptive")
def test_rotation_trouvee_par_l_ocr_le_modele_n_est_pas_consulte(mock_adaptive, mock_modele):
    image, tournee = MagicMock(), MagicMock()
    mock_adaptive.return_value = ("S18 LUNDI", 6, tournee, 90)

    o = te._orienter(image, orientation_model="vision-x")

    mock_modele.assert_not_called()
    assert (o.image, o.angle, o.source) == (tournee, 90, "ocr")


@patch(f"{_MODULE}._OCR_AVAILABLE", True)
@patch(f"{_MODULE}._demander_orientation_au_modele", return_value=None)
@patch(f"{_MODULE}._ocr_image_adaptive")
def test_sans_reponse_du_modele_l_image_reste_telle_quelle(mock_adaptive, _modele):
    image = MagicMock()
    mock_adaptive.return_value = ("", 6, image, 0)

    o = te._orienter(image, orientation_model="vision-x")

    image.rotate.assert_not_called()
    assert (o.image, o.angle, o.source) == (image, 0, "aucune")


@patch(f"{_MODULE}._OCR_AVAILABLE", True)
@patch(f"{_MODULE}._demander_orientation_au_modele")
@patch(f"{_MODULE}._ocr_image_adaptive")
def test_sans_modele_configure_le_dernier_ressort_est_muet(mock_adaptive, mock_modele):
    image = MagicMock()
    mock_adaptive.return_value = ("", 6, image, 0)

    te._orienter(image, orientation_model=None)

    mock_modele.assert_not_called()


@patch(f"{_MODULE}._OCR_AVAILABLE", True)
@patch(f"{_MODULE}._image_to_vision_bytes", return_value=(b"jpeg", "image/jpeg"))
@patch(f"{_MODULE}._orienter")
@patch(f"{_MODULE}._ouvrir_image")
def test_la_page_rendue_dit_d_ou_vient_son_orientation(mock_ouvrir, mock_orienter, _bytes):
    image = MagicMock()
    mock_ouvrir.return_value = (image, True)
    mock_orienter.return_value = te.ImageOrientee("", 6, image, 0, "aucune")

    doc = te.render_document_pages(b"photo", "feuille.jpg", orientation_model="vision-x")

    mock_orienter.assert_called_once_with(image, orientation_model="vision-x")
    assert doc.pages[0].orientation_source == "exif"
    assert doc.pages[0].orientation_angle == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest -q tests/unit/schedules/test_orientation_image.py`
Expected: FAIL — `AttributeError: ... '_orienter'` / `'ImageOrientee'` ; `TypeError: render_document_pages() got an unexpected keyword argument 'orientation_model'`

- [ ] **Step 3: Write minimal implementation**

`RenderedPage` :
```python
    vision_mime_type: str = "image/jpeg"
    #: Rotation PIL appliquée à l'image reçue (degrés, sens anti-horaire).
    orientation_angle: int = 0
    #: Qui a décidé du sens : exif | ocr | vision | aucune.
    orientation_source: str = "aucune"
```
Après `_demander_orientation_au_modele` :
```python
@dataclass
class ImageOrientee:
    texte: str
    psm: int
    image: "Image.Image"
    angle: int
    source: str


def _orienter(image: "Image.Image", *, orientation_model: str | None) -> ImageOrientee:
    """OCR avec auto-rotation ; le modèle de vision tranche si l'OCR n'a rien départagé."""
    texte, psm, orientee, angle = _ocr_image_adaptive(image)
    if angle or orientee is not image:
        return ImageOrientee(texte, psm, orientee, angle, "ocr")
    if orientation_model and _orientation_quality_score(texte) < _OCR_RELIABILITY_MIN_SCORE:
        horaire = _demander_orientation_au_modele(image, orientation_model)
        if horaire:
            angle = (360 - horaire) % 360
            orientee = image.rotate(angle, expand=True)
            texte, psm, _ = _ocr_image_for_orientation(orientee)
            return ImageOrientee(texte, psm, orientee, angle, "vision")
    return ImageOrientee(texte, psm, image, 0, "aucune")
```
`render_document_pages(file_content, filename, *, orientation_model: str | None = None)` — branche image :
```python
        image, exif = _ouvrir_image(file_content)
        o = _orienter(image, orientation_model=orientation_model)
        text = _post_process_ocr_text(o.texte)
        vision_bytes, vision_mime = _image_to_vision_bytes(o.image)
        return RenderedDocument(
            pages=[
                RenderedPage(
                    page_index=1, png_bytes=vision_bytes, ocr_text=text, ocr_psm=o.psm,
                    vision_mime_type=vision_mime, orientation_angle=o.angle,
                    orientation_source="exif" if exif and o.source == "aucune" else o.source,
                )
            ],
            pages_total=1, pages_processed=1,
        )
```
Branche PDF, page 1 : `o = _orienter(img, orientation_model=orientation_model)` ; `text, psm, oriented, page_rotation, page_source = o.texte, o.psm, o.image, o.angle, o.source` ; pages suivantes inchangées (rotation de la page 1) ; chaque `RenderedPage` reçoit `orientation_angle=page_rotation, orientation_source=page_source`.

`timesheet_hybrid_extract.py:262` :
```python
    rendered: RenderedDocument = render_document_pages(
        file_content, filename, orientation_model=timesheet_vision_model()
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest -q tests/unit/schedules tests/unit/shared/test_text_extraction.py`
Expected: PASS (les tests existants de `render_document_pages` continuent de doubler `_ocr_image_adaptive`).

---

### Task 4: Lint, suite, et vérification sur une vraie feuille

- [ ] **Step 1:** `cd backend && .venv/bin/python -m ruff check app/shared/infrastructure/documents/text_extraction.py app/modules/schedules/application/timesheet_hybrid_extract.py tests/unit/schedules/test_orientation_image.py` → `All checks passed!`
- [ ] **Step 2:** `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key .venv/bin/python -m pytest -q tests/unit` → tout vert.
- [ ] **Step 3:** vérification manuelle locale, hors tests : une photo d'une feuille Colorplast (`data/colorplast/pointages/…`) tournée de 90° et enregistrée avec EXIF passe par `render_document_pages` et ressort droite (`orientation_source == "exif"`) ; la même sans EXIF ressort `ocr` ou `vision`.
- [ ] **Step 4:** commit à la demande d'Alexandre : `fix(pointages): le sens de l'image est redressé avant lecture (EXIF, OCR, modèle de vision)`.

---

## Révision en cours d'exécution (19/09)

Deux mesures sur de vraies feuilles Colorplast ont changé la tâche 3 :

- **La course aux scores OCR ne décide plus de l'orientation.** À 200 dpi,
  l'image droite scorait 0 et sa variante à 90° scorait 22 : Tesseract lit
  lui-même le texte couché, le score dit s'il s'en est sorti, pas si l'image est
  droite. Il re-tournait de travers une photo redressée par son EXIF.
- **L'OSD de Tesseract remet de côté (90/270)**, juste 24/24 en brut et 8/8 en
  JPEG à des confiances de 0,1 à 2,1 — sous le seuil de 5 qu'exigeait l'ancien
  code. Il n'est pas cru sur 0/180, qu'il confond à ces confiances.

`_orienter` final : EXIF → OSD pour le côté → texte OCR fiable = droite → sinon
le modèle de vision sur l'image obtenue → sinon telle quelle. Nouvelle
`_angle_osd(image) -> int | None` (rotation PIL). Tests dans
`tests/unit/schedules/test_orientation_image.py` (19), `test_render_single_image`
adapté (il doublait `_ocr_image_adaptive`, que `_orienter` n'appelle plus).
Vérifié pixel par pixel sur `semaine-07-pointages.pdf` à 200 et 300 dpi : EXIF 3/6/8,
côté 90/270 et droite sortent droites ; l'envers sans EXIF attend le modèle
(absent en local).
