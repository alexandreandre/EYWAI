"""Tests compression images pour l'API vision."""

import os
from io import BytesIO
from unittest.mock import patch

import pytest
from PIL import Image

from app.shared.infrastructure.documents.text_extraction import (
    _image_to_vision_bytes,
    ensure_vision_image_under_limit,
)


def _large_rgb_image(width: int, height: int) -> Image.Image:
    return Image.new("RGB", (width, height), color=(128, 64, 32))


def _noisy_rgb_image(width: int, height: int) -> Image.Image:
    return Image.frombytes("RGB", (width, height), os.urandom(width * height * 3))


def test_image_to_vision_bytes_resizes_and_jpeg():
    image = _large_rgb_image(7457, 10276)
    payload, mime = _image_to_vision_bytes(image)
    assert mime == "image/jpeg"
    assert len(payload) <= 8 * 1024 * 1024
    decoded = Image.open(BytesIO(payload))
    assert max(decoded.size) <= 2400


@patch(
    "app.shared.infrastructure.documents.text_extraction._vision_max_bytes",
    return_value=100_000,
)
def test_ensure_vision_image_under_limit_recompresses_large_payload(_mock_cap):
    image = _noisy_rgb_image(1200, 900)
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=95)
    raw = buf.getvalue()
    assert len(raw) > 100_000

    payload, mime = ensure_vision_image_under_limit(raw, "image/jpeg")
    assert mime == "image/jpeg"
    assert len(payload) <= 100_000


@pytest.mark.parametrize("size", [(800, 600), (1200, 900)])
def test_small_image_stays_under_limit(size):
    image = _large_rgb_image(*size)
    payload, mime = _image_to_vision_bytes(image)
    assert mime == "image/jpeg"
    assert len(payload) <= 8 * 1024 * 1024
