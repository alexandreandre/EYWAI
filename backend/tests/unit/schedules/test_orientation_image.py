"""Le sens de l'image avant lecture : EXIF à l'ouverture, OCR, puis le modèle de vision.

Une feuille de pointage photographiée en portrait est stockée couchée avec un tag
EXIF ; un scan peut être à l'envers ; une feuille manuscrite floue laisse l'OCR
indécis dans les quatre sens. Trois étages, et jamais d'échec de lecture pour ça.
"""

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


# --- 1. EXIF à l'ouverture -------------------------------------------------


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


# --- 2. Le modèle de vision, en dernier ressort ----------------------------


def test_la_mosaique_montre_les_quatre_sens_etiquetes():
    """Mesuré sur S28 (photo) et S29 (scan) : à la question « de combien tourner ? »
    gemini-2.5-flash répond 270 à tout ; devant les quatre vignettes, il désigne
    la bonne 16 fois sur 16."""
    image = Image.new("RGB", (100, 50), "white")

    mosaique = te._mosaique_des_quatre_sens(image, cote=100)

    assert mosaique.width > 2 * image.width
    assert mosaique.height > 2 * image.height


@pytest.mark.parametrize(
    ("vignette", "rotation_pil"), [("A", 0), ("B", 90), ("C", 180), ("D", 270), ("E", None), (None, None)]
)
def test_la_vignette_designee_donne_la_rotation_pil(vignette, rotation_pil):
    assert te._rotation_pil_depuis_vignette(vignette) == rotation_pil


@patch(f"{_MODULE}._image_to_vision_bytes", return_value=(b"jpg", "image/jpeg"))
@patch("app.shared.infrastructure.ai.structured_vision.extract_structured_json_from_image")
def test_le_modele_designe_la_vignette_droite_et_on_en_deduit_l_angle_horaire(mock_extract, mock_bytes):
    # Vignette D = image tournée de 270° PIL (anti-horaire) → 90° horaire pour la lire.
    mock_extract.return_value = MagicMock(data={"vignette_droite": "D"})
    image = Image.new("RGB", (100, 50), "white")

    assert te._demander_orientation_au_modele(image, "vision-x") == 90
    appel = mock_extract.call_args.kwargs
    assert appel["model"] == "vision-x"
    assert appel["json_schema"]["properties"]["vignette_droite"]["enum"] == ["A", "B", "C", "D"]
    envoyee = mock_bytes.call_args.args[0]
    assert envoyee.width > 2 * image.width, "c'est la mosaïque qui part au modèle, pas l'image seule"


@pytest.mark.parametrize(("vignette", "horaire"), [("A", 0), ("B", 270), ("C", 180), ("D", 90)])
@patch(f"{_MODULE}._image_to_vision_bytes", return_value=(b"jpg", "image/jpeg"))
@patch("app.shared.infrastructure.ai.structured_vision.extract_structured_json_from_image")
def test_chaque_vignette_correspond_a_un_angle_horaire(mock_extract, _bytes, vignette, horaire):
    mock_extract.return_value = MagicMock(data={"vignette_droite": vignette})

    assert te._demander_orientation_au_modele(Image.new("RGB", (40, 20)), "vision-x") == horaire


@patch(f"{_MODULE}._image_to_vision_bytes", return_value=(b"jpg", "image/jpeg"))
@patch("app.shared.infrastructure.ai.structured_vision.extract_structured_json_from_image")
def test_une_reponse_hors_des_quatre_vignettes_est_ignoree(mock_extract, _bytes):
    mock_extract.return_value = MagicMock(data={"vignette_droite": "E"})

    assert te._demander_orientation_au_modele(Image.new("RGB", (40, 20)), "vision-x") is None


@patch(f"{_MODULE}._image_to_vision_bytes", return_value=(b"jpg", "image/jpeg"))
@patch("app.shared.infrastructure.ai.structured_vision.extract_structured_json_from_image")
def test_un_modele_indisponible_ne_fait_pas_echouer_la_lecture(mock_extract, _bytes):
    mock_extract.side_effect = RuntimeError("clé API absente")

    assert te._demander_orientation_au_modele(Image.new("RGB", (40, 20)), "vision-x") is None


# --- 3. L'OSD de Tesseract, autoritaire dès qu'il répond ------------------


@patch(f"{_MODULE}._OCR_AVAILABLE", True)
@patch(f"{_MODULE}._preprocess_image", side_effect=lambda img: img)
@patch(f"{_MODULE}.pytesseract")
def test_l_osd_donne_la_rotation_pil_qui_redresse(mock_tess, _pre):
    # « Rotate: 90 » = tourner de 90° horaire pour lire → rotation PIL de 270°.
    mock_tess.image_to_osd.return_value = "Rotate: 90\nOrientation confidence: 0.6\n"

    assert te._angle_osd(MagicMock()) == 270


@patch(f"{_MODULE}._OCR_AVAILABLE", True)
@patch(f"{_MODULE}._preprocess_image", side_effect=lambda img: img)
@patch(f"{_MODULE}.pytesseract")
def test_une_image_droite_pour_l_osd_ne_tourne_pas(mock_tess, _pre):
    mock_tess.image_to_osd.return_value = "Rotate: 0\nOrientation confidence: 1.4\n"

    assert te._angle_osd(MagicMock()) == 0


@patch(f"{_MODULE}._OCR_AVAILABLE", True)
@patch(f"{_MODULE}._preprocess_image", side_effect=lambda img: img)
@patch(f"{_MODULE}.pytesseract")
def test_un_osd_muet_rend_none(mock_tess, _pre):
    mock_tess.image_to_osd.side_effect = RuntimeError("Too few characters")

    assert te._angle_osd(MagicMock()) is None


# --- 4. L'enchaînement -----------------------------------------------------

FIABLE = "Total pour la semaine 12/05/2026 13/05/2026 14/05/2026"
PAUVRE = "AH 9"


def _orienter_avec(image, *, osd, texte, modele, model="vision-x"):
    """Lance `_orienter` avec l'OSD, l'OCR et le modèle doublés ; rend (résultat, doublures)."""
    with patch(f"{_MODULE}._OCR_AVAILABLE", True), \
         patch(f"{_MODULE}._angle_osd", return_value=osd) as mock_osd, \
         patch(f"{_MODULE}._ocr_image_for_orientation", return_value=(texte, 6, 0)) as mock_ocr, \
         patch(f"{_MODULE}._ocr_image_adaptive") as mock_course, \
         patch(f"{_MODULE}._demander_orientation_au_modele", return_value=modele) as mock_modele:
        resultat = te._orienter(image, orientation_model=model)
    return resultat, {"osd": mock_osd, "ocr": mock_ocr, "course": mock_course, "modele": mock_modele}


def _orienter_apres_exif(image, *, osd, texte, modele):
    with patch(f"{_MODULE}._OCR_AVAILABLE", True), \
         patch(f"{_MODULE}._angle_osd", return_value=osd), \
         patch(f"{_MODULE}._ocr_image_for_orientation", return_value=(texte, 6, 0)), \
         patch(f"{_MODULE}._demander_orientation_au_modele", return_value=modele) as mock_modele:
        o = te._orienter(image, orientation_model="vision-x", exif_redressee=True)
    return o, mock_modele


def test_l_exif_redresse_la_photo_et_un_texte_fiable_confirme():
    image = MagicMock()

    o, mock_modele = _orienter_apres_exif(image, osd=None, texte=FIABLE, modele=180)

    image.rotate.assert_not_called()
    mock_modele.assert_not_called()
    assert (o.image, o.angle, o.source, o.texte) == (image, 0, "exif", FIABLE)


def test_l_exif_n_est_qu_un_point_de_depart_la_feuille_peut_etre_couchee_dans_la_photo():
    """S28 Colorplast : la photo portrait est redressée par son EXIF, mais la
    feuille y est posée de côté. Le court-circuit EXIF l'envoyait couchée au
    modèle de lecture ; l'OSD voit le côté et la remet droite."""
    image, redressee = MagicMock(), MagicMock()
    image.rotate.return_value = redressee

    o, _ = _orienter_apres_exif(image, osd=90, texte=FIABLE, modele=0)

    image.rotate.assert_called_once_with(90, expand=True)
    assert (o.image, o.angle, o.source) == (redressee, 90, "osd")


def test_apres_l_exif_texte_pauvre_le_modele_tranche_encore():
    image, tournee = MagicMock(), MagicMock()
    image.rotate.return_value = tournee

    o, mock_modele = _orienter_apres_exif(image, osd=None, texte=PAUVRE, modele=180)

    mock_modele.assert_called_once_with(image, "vision-x")
    assert (o.image, o.angle, o.source) == (tournee, 180, "vision")


def test_de_cote_selon_l_osd_on_redresse_et_un_texte_fiable_suffit():
    image, redressee = MagicMock(), MagicMock()
    image.rotate.return_value = redressee

    o, d = _orienter_avec(image, osd=270, texte=FIABLE, modele=180)

    image.rotate.assert_called_once_with(270, expand=True)
    d["ocr"].assert_called_once_with(redressee)
    d["modele"].assert_not_called()
    assert (o.image, o.angle, o.source) == (redressee, 270, "osd")


def test_de_cote_selon_l_osd_texte_pauvre_le_modele_confirme_sur_l_image_redressee():
    """Feuille manuscrite de côté : l'OSD la remet droite, l'OCR ne lit presque
    rien, le modèle regarde l'image redressée et dit 0 — on garde l'OSD."""
    image, redressee = MagicMock(), MagicMock()
    image.rotate.return_value = redressee

    o, d = _orienter_avec(image, osd=270, texte=PAUVRE, modele=0)

    d["modele"].assert_called_once_with(redressee, "vision-x")
    assert (o.image, o.angle, o.source) == (redressee, 270, "osd")


def test_de_cote_selon_l_osd_mais_a_l_envers_pour_le_modele_les_deux_s_ajoutent():
    image, redressee, finale = MagicMock(), MagicMock(), MagicMock()
    image.rotate.return_value = redressee
    redressee.rotate.return_value = finale

    o, d = _orienter_avec(image, osd=270, texte=PAUVRE, modele=180)

    redressee.rotate.assert_called_once_with(180, expand=True)
    assert (o.image, o.angle, o.source) == (finale, 90, "vision")


def test_l_osd_qui_dit_180_n_est_pas_cru_un_texte_fiable_garde_l_image_droite():
    """À faible confiance, l'OSD confond droite et à l'envers (image droite en
    JPEG → « 180 ») ; de côté, il ne se trompe pas. On ne l'écoute que pour 90/270."""
    image = MagicMock()

    o, d = _orienter_avec(image, osd=180, texte=FIABLE, modele=180)

    image.rotate.assert_not_called()
    d["modele"].assert_not_called()
    assert (o.image, o.angle, o.source) == (image, 0, "aucune")


def test_l_osd_dit_droite_texte_pauvre_le_modele_voit_l_envers():
    image, tournee = MagicMock(), MagicMock()
    image.rotate.return_value = tournee

    o, d = _orienter_avec(image, osd=0, texte=PAUVRE, modele=180)

    d["modele"].assert_called_once_with(image, "vision-x")
    image.rotate.assert_called_once_with(180, expand=True)
    assert (o.image, o.angle, o.source) == (tournee, 180, "vision")
    d["ocr"].assert_called_with(tournee)


def test_un_angle_horaire_du_modele_devient_une_rotation_pil_anti_horaire():
    image = MagicMock()

    o, _ = _orienter_avec(image, osd=None, texte=PAUVRE, modele=90)

    image.rotate.assert_called_once_with(270, expand=True)
    assert o.angle == 270


def test_osd_muet_texte_pauvre_et_modele_sans_avis_l_image_reste_telle_quelle():
    image = MagicMock()

    o, _ = _orienter_avec(image, osd=None, texte=PAUVRE, modele=None)

    image.rotate.assert_not_called()
    assert (o.image, o.angle, o.source) == (image, 0, "aucune")


def test_sans_modele_configure_le_dernier_ressort_est_muet():
    image = MagicMock()

    _, d = _orienter_avec(image, osd=None, texte=PAUVRE, modele=180, model=None)

    d["modele"].assert_not_called()


def test_la_course_aux_scores_ne_decide_plus_de_l_orientation():
    """À 200 dpi, l'image droite scorait 0 et sa variante à 90° scorait 22 :
    Tesseract lit lui-même le texte couché, le score ne dit pas si l'image est droite."""
    _, d = _orienter_avec(MagicMock(), osd=None, texte=PAUVRE, modele=None)

    d["course"].assert_not_called()


@patch(f"{_MODULE}._OCR_AVAILABLE", True)
@patch(f"{_MODULE}._image_to_vision_bytes", return_value=(b"jpeg", "image/jpeg"))
@patch(f"{_MODULE}._orienter")
@patch(f"{_MODULE}._ouvrir_image")
def test_la_page_rendue_dit_d_ou_vient_son_orientation(mock_ouvrir, mock_orienter, _bytes):
    image = MagicMock()
    mock_ouvrir.return_value = (image, True)
    mock_orienter.return_value = te.ImageOrientee("", 6, image, 0, "exif")

    doc = te.render_document_pages(b"photo", "feuille.jpg", orientation_model="vision-x")

    mock_orienter.assert_called_once_with(image, orientation_model="vision-x", exif_redressee=True)
    assert doc.pages[0].orientation_source == "exif"
    assert doc.pages[0].orientation_angle == 0
