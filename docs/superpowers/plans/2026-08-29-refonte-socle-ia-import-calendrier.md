# Refonte socle IA + import calendrier — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extraction native (sans OCR local) des relevés de pointeuse via Gemini, socle IA async avec timeouts/retries/journalisation, et watchdog des jobs — spec `docs/superpowers/specs/2026-08-28-refonte-socle-ia-import-calendrier-design.md`.

**Architecture:** Un client OpenRouter async s'ajoute au socle (`app/shared/infrastructure/ai/`) avec une entrée PDF native. Un extracteur `timesheet_native_extract` produit le même `HybridExtractResult` que l'hybride pour se brancher sans toucher au merge/consensus existants, derrière `TIMESHEET_EXTRACT_MODE=native`. Le watchdog marque `failed` tout job « extracting » sans heartbeat > 5 min.

**Tech Stack:** Python 3.14 (backend/venv), FastAPI, openai SDK (AsyncOpenAI → OpenRouter), PyPDF2, pytest, Supabase.

## Global Constraints

- Aucune nouvelle dépendance npm/pip (openai, httpx, PyPDF2, pdfplumber déjà présents).
- Textes utilisateur en français ; messages d'erreur explicites.
- `ruff check` propre sur tout fichier touché ; tests via `cd backend && ./venv/bin/python -m pytest <chemin> -q`.
- Ne PAS modifier `timesheet_hybrid_extract.py` (chemin de repli conservé tel quel), sauf import de ses symboles.
- Un commit par tâche, style Conventional Commits en français, sur la branche courante (`feat/mode-paie-navigation`), fin de message : `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Le rollback fonctionnel = variable d'env `TIMESHEET_EXTRACT_MODE=hybrid`, sans redéploiement de code.

---

### Task 1: Client OpenRouter async (socle)

**Files:**
- Create: `backend/app/shared/infrastructure/ai/client_async.py`
- Create: `backend/tests/unit/shared_ai/__init__.py` (vide)
- Test: `backend/tests/unit/shared_ai/test_client_async.py`

**Interfaces:**
- Consumes: `resolve_model`, `require_llm_api_key`, `OPENROUTER_BASE_URL` de `app.shared.infrastructure.ai.client`.
- Produces: `get_async_chat_client() -> AsyncOpenAI` et `async chat_completions_create_async(*, model: str, **kwargs) -> Any` (kwargs transmis à `chat.completions.create`, `timeout` inclus). Journalise chaque appel (modèle, durée ms, tokens, succès/échec) sur le logger `app.ai`.

- [ ] **Step 1: Écrire le test qui échoue**

```python
# backend/tests/unit/shared_ai/test_client_async.py
"""Client OpenRouter async : résolution de modèle, transmission kwargs, journalisation."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


def _fake_response(total_tokens: int = 42):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))],
        usage=SimpleNamespace(total_tokens=total_tokens),
    )


def test_create_async_resolves_alias_and_forwards_kwargs(monkeypatch):
    from app.shared.infrastructure.ai import client_async

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=_fake_response())
    monkeypatch.setattr(client_async, "get_async_chat_client", lambda: fake_client)

    result = asyncio.run(
        client_async.chat_completions_create_async(
            model="gpt-4o-mini", temperature=0.0, timeout=60.0
        )
    )

    assert result.usage.total_tokens == 42
    kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "openai/gpt-4o-mini"
    assert kwargs["timeout"] == 60.0
    assert kwargs["temperature"] == 0.0


def test_create_async_logs_and_reraises_on_failure(monkeypatch, caplog):
    from app.shared.infrastructure.ai import client_async

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(client_async, "get_async_chat_client", lambda: fake_client)

    with caplog.at_level("WARNING", logger="app.ai"):
        with pytest.raises(RuntimeError):
            asyncio.run(
                client_async.chat_completions_create_async(model="google/gemini-2.5-flash")
            )
    assert any("gemini-2.5-flash" in r.message for r in caplog.records)
```

- [ ] **Step 2: Vérifier l'échec**

Run: `cd backend && ./venv/bin/python -m pytest tests/unit/shared_ai/test_client_async.py -q`
Expected: FAIL — `ModuleNotFoundError: app.shared.infrastructure.ai.client_async`

- [ ] **Step 3: Implémentation minimale**

```python
# backend/app/shared/infrastructure/ai/client_async.py
"""Client OpenRouter async : timeouts explicites, retries SDK, journalisation par appel."""

from __future__ import annotations

import logging
import time
from functools import lru_cache
from typing import Any

import httpx
from openai import AsyncOpenAI

from app.shared.infrastructure.ai.client import (
    OPENROUTER_BASE_URL,
    require_llm_api_key,
    resolve_model,
)

logger = logging.getLogger("app.ai")

# Lecture longue (PDF multi-pages) mais bornée — le défaut SDK est de 600 s.
_DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)


@lru_cache(maxsize=1)
def get_async_chat_client() -> AsyncOpenAI:
    import os

    return AsyncOpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=require_llm_api_key(),
        timeout=_DEFAULT_TIMEOUT,
        max_retries=2,  # backoff SDK sur 429/5xx
        default_headers={
            "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "https://eywai.app"),
            "X-Title": os.getenv("OPENROUTER_APP_TITLE", "EYWAI"),
        },
    )


async def chat_completions_create_async(*, model: str, **kwargs: Any) -> Any:
    """chat.completions.create async via OpenRouter, avec trace durée/tokens."""
    resolved = resolve_model(model)
    started = time.monotonic()
    try:
        response = await get_async_chat_client().chat.completions.create(
            model=resolved, **kwargs
        )
    except Exception as exc:
        logger.warning(
            "Appel IA échoué model=%s durée=%dms erreur=%s",
            resolved,
            int((time.monotonic() - started) * 1000),
            exc,
        )
        raise
    usage = getattr(response, "usage", None)
    logger.info(
        "Appel IA model=%s durée=%dms tokens=%s",
        resolved,
        int((time.monotonic() - started) * 1000),
        getattr(usage, "total_tokens", None),
    )
    return response
```

- [ ] **Step 4: Vérifier le vert**

Run: `cd backend && ./venv/bin/python -m pytest tests/unit/shared_ai/test_client_async.py -q`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/shared/infrastructure/ai/client_async.py backend/tests/unit/shared_ai/
git commit -m "feat(ai): client OpenRouter async avec timeouts et journalisation

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Extraction JSON structurée depuis un PDF natif

**Files:**
- Create: `backend/app/shared/infrastructure/ai/structured_document.py`
- Test: `backend/tests/unit/shared_ai/test_structured_document.py`

**Interfaces:**
- Consumes: `chat_completions_create_async` (Task 1), `StructuredExtractionResult` de `structured_extractor`.
- Produces: `async extract_structured_json_from_pdf(*, system_prompt: str, user_prompt: str, pdf_bytes: bytes, filename: str = "document.pdf", json_schema: dict, schema_name: str = "pdf_extraction", model: str, temperature: float = 0.0, max_tokens: int | None = None) -> StructuredExtractionResult | None`. Le PDF part en file part OpenRouter (`{"type": "file", "file": {"filename", "file_data": "data:application/pdf;base64,…"}}`). Retry une fois sur échec de parsing, `None` après deux échecs.

- [ ] **Step 1: Écrire le test qui échoue**

```python
# backend/tests/unit/shared_ai/test_structured_document.py
"""Entrée PDF native : file part OpenRouter, parsing JSON, retry."""

import asyncio
import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.unit

_PDF = b"%PDF-1.4 fake"
_SCHEMA = {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"], "additionalProperties": False}


def _resp(content: str, tokens: int = 10):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(total_tokens=tokens),
    )


def test_pdf_sent_as_file_part_and_parsed(monkeypatch):
    from app.shared.infrastructure.ai import structured_document as sd

    mock_create = AsyncMock(return_value=_resp('{"x": 7}'))
    monkeypatch.setattr(sd, "chat_completions_create_async", mock_create)

    result = asyncio.run(
        sd.extract_structured_json_from_pdf(
            system_prompt="sys",
            user_prompt="user",
            pdf_bytes=_PDF,
            filename="releve.pdf",
            json_schema=_SCHEMA,
            model="google/gemini-2.5-flash",
        )
    )

    assert result is not None and result.data == {"x": 7} and result.tokens_used == 10
    kwargs = mock_create.call_args.kwargs
    parts = kwargs["messages"][1]["content"]
    file_part = next(p for p in parts if p["type"] == "file")
    assert file_part["file"]["filename"] == "releve.pdf"
    expected_prefix = "data:application/pdf;base64," + base64.b64encode(_PDF).decode()[:8]
    assert file_part["file"]["file_data"].startswith(expected_prefix)
    assert kwargs["response_format"]["json_schema"]["strict"] is True


def test_retry_once_then_none(monkeypatch):
    from app.shared.infrastructure.ai import structured_document as sd

    mock_create = AsyncMock(side_effect=[_resp("pas du json"), _resp("toujours pas")])
    monkeypatch.setattr(sd, "chat_completions_create_async", mock_create)

    result = asyncio.run(
        sd.extract_structured_json_from_pdf(
            system_prompt="s", user_prompt="u", pdf_bytes=_PDF,
            json_schema=_SCHEMA, model="google/gemini-2.5-flash",
        )
    )
    assert result is None
    assert mock_create.call_count == 2
```

- [ ] **Step 2: Vérifier l'échec**

Run: `cd backend && ./venv/bin/python -m pytest tests/unit/shared_ai/test_structured_document.py -q`
Expected: FAIL — module `structured_document` inexistant

- [ ] **Step 3: Implémentation minimale**

```python
# backend/app/shared/infrastructure/ai/structured_document.py
"""Extraction JSON structurée depuis un PDF envoyé nativement au modèle (sans OCR local)."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

from app.shared.infrastructure.ai.client import require_llm_api_key
from app.shared.infrastructure.ai.client_async import chat_completions_create_async
from app.shared.infrastructure.ai.structured_extractor import StructuredExtractionResult

logger = logging.getLogger(__name__)


async def extract_structured_json_from_pdf(
    *,
    system_prompt: str,
    user_prompt: str,
    pdf_bytes: bytes,
    filename: str = "document.pdf",
    json_schema: dict[str, Any],
    schema_name: str = "pdf_extraction",
    model: str,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> StructuredExtractionResult | None:
    """PDF en file part OpenRouter + sortie JSON schématisée. Retry une fois."""
    require_llm_api_key()
    encoded = base64.b64encode(pdf_bytes).decode("ascii")
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {
                    "type": "file",
                    "file": {
                        "filename": filename,
                        "file_data": f"data:application/pdf;base64,{encoded}",
                    },
                },
            ],
        },
    ]
    request_kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": json_schema},
        },
    }
    if max_tokens is not None:
        request_kwargs["max_tokens"] = max_tokens

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            resp = await chat_completions_create_async(**request_kwargs)
            raw = (resp.choices[0].message.content or "").strip()
            data = json.loads(raw)
            if not isinstance(data, dict):
                return None
            usage = getattr(resp, "usage", None)
            tokens = int(getattr(usage, "total_tokens", 0) or 0) if usage else 0
            return StructuredExtractionResult(data=data, tokens_used=tokens)
        except Exception as exc:
            last_error = exc
            logger.warning(
                "extract_structured_json_from_pdf tentative %s échouée: %s",
                attempt + 1,
                exc,
            )
    logger.error("extract_structured_json_from_pdf échouée après retry: %s", last_error)
    return None


__all__ = ["extract_structured_json_from_pdf"]
```

> **Note routage OpenRouter** : par défaut OpenRouter peut router un PDF vers
> son propre parseur (`mistral-ocr`, facturé par page) plutôt que vers la
> lecture native de Gemini. Si l'éval (Task 9) montre un surcoût ou une
> qualité dégradée, ajouter à `request_kwargs` :
> `"extra_body": {"plugins": [{"id": "file-parser", "pdf": {"engine": "native"}}]}`.

- [ ] **Step 4: Vérifier le vert**

Run: `cd backend && ./venv/bin/python -m pytest tests/unit/shared_ai/test_structured_document.py -q`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/shared/infrastructure/ai/structured_document.py backend/tests/unit/shared_ai/test_structured_document.py
git commit -m "feat(ai): extraction JSON structurée depuis un PDF natif OpenRouter

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Découpage d'un PDF en lots de pages

**Files:**
- Create: `backend/app/shared/infrastructure/documents/pdf_batches.py`
- Create: `backend/tests/unit/shared_documents/__init__.py` (vide)
- Test: `backend/tests/unit/shared_documents/test_pdf_batches.py`

**Interfaces:**
- Consumes: `PyPDF2` (déjà dépendance), `DocumentExtractionError` de `text_extraction`.
- Produces: `@dataclass PdfBatch(content: bytes, page_start: int, page_end: int)` (1-based inclus) et `split_pdf_into_batches(file_content: bytes, *, batch_size: int, max_pages: int = 120) -> list[PdfBatch]`. Lève `DocumentExtractionError` si le PDF est illisible ou vide.

- [ ] **Step 1: Écrire le test qui échoue**

```python
# backend/tests/unit/shared_documents/test_pdf_batches.py
"""Découpage PDF en lots : bornes 1-based, plafond de pages, PDF illisible."""

import io

import pytest
from PyPDF2 import PdfReader, PdfWriter

pytestmark = pytest.mark.unit


def _blank_pdf(pages: int) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_split_five_pages_in_batches_of_two():
    from app.shared.infrastructure.documents.pdf_batches import split_pdf_into_batches

    batches = split_pdf_into_batches(_blank_pdf(5), batch_size=2)

    assert [(b.page_start, b.page_end) for b in batches] == [(1, 2), (3, 4), (5, 5)]
    assert len(PdfReader(io.BytesIO(batches[0].content)).pages) == 2
    assert len(PdfReader(io.BytesIO(batches[2].content)).pages) == 1


def test_max_pages_caps_output():
    from app.shared.infrastructure.documents.pdf_batches import split_pdf_into_batches

    batches = split_pdf_into_batches(_blank_pdf(6), batch_size=4, max_pages=5)
    assert batches[-1].page_end == 5


def test_unreadable_pdf_raises():
    from app.shared.infrastructure.documents.pdf_batches import split_pdf_into_batches
    from app.shared.infrastructure.documents.text_extraction import DocumentExtractionError

    with pytest.raises(DocumentExtractionError):
        split_pdf_into_batches(b"pas un pdf", batch_size=2)
```

- [ ] **Step 2: Vérifier l'échec**

Run: `cd backend && ./venv/bin/python -m pytest tests/unit/shared_documents/test_pdf_batches.py -q`
Expected: FAIL — module `pdf_batches` inexistant

- [ ] **Step 3: Implémentation minimale**

```python
# backend/app/shared/infrastructure/documents/pdf_batches.py
"""Découpage d'un PDF en lots de pages pour envoi natif au modèle."""

from __future__ import annotations

import io
from dataclasses import dataclass

from PyPDF2 import PdfReader, PdfWriter

from app.shared.infrastructure.documents.text_extraction import DocumentExtractionError


@dataclass
class PdfBatch:
    content: bytes
    page_start: int  # 1-based, inclus
    page_end: int  # 1-based, inclus


def split_pdf_into_batches(
    file_content: bytes, *, batch_size: int, max_pages: int = 120
) -> list[PdfBatch]:
    try:
        reader = PdfReader(io.BytesIO(file_content))
        total = len(reader.pages)
    except Exception as exc:
        raise DocumentExtractionError("Impossible de lire le PDF.") from exc
    if total == 0:
        raise DocumentExtractionError("Le PDF ne contient aucune page.")

    total = min(total, max_pages)
    batch_size = max(1, batch_size)
    batches: list[PdfBatch] = []
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        writer = PdfWriter()
        for idx in range(start, end):
            writer.add_page(reader.pages[idx])
        buf = io.BytesIO()
        writer.write(buf)
        batches.append(
            PdfBatch(content=buf.getvalue(), page_start=start + 1, page_end=end)
        )
    return batches


__all__ = ["PdfBatch", "split_pdf_into_batches"]
```

- [ ] **Step 4: Vérifier le vert**

Run: `cd backend && ./venv/bin/python -m pytest tests/unit/shared_documents/test_pdf_batches.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/shared/infrastructure/documents/pdf_batches.py backend/tests/unit/shared_documents/
git commit -m "feat(documents): découpage d'un PDF en lots de pages

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Schéma de lot + texte de couche PDF public

**Files:**
- Modify: `backend/app/modules/schedules/application/timesheet_page_schema.py` (ajouts en fin de fichier)
- Modify: `backend/app/shared/infrastructure/documents/text_extraction.py` (ajout d'un wrapper public en fin de fichier)
- Test: `backend/tests/unit/schedules/test_timesheet_batch_schema.py`

**Interfaces:**
- Consumes: `PAGE_EXTRACTION_JSON_SCHEMA` existant ; `_extract_pdf_native` (privé, même fichier).
- Produces:
  - `BATCH_EXTRACTION_JSON_SCHEMA: dict` — objet `{"pages": [<page + page_index>]}` strict.
  - `build_batch_user_prompt_native(*, page_start: int, page_end: int, pages_total: int, matricule_hint: str) -> str`.
  - `extract_pdf_text_layer(file_content: bytes) -> str` dans `text_extraction` (texte pdfplumber seul, jamais d'OCR ; chaîne vide si absent/illisible).

- [ ] **Step 1: Écrire le test qui échoue**

```python
# backend/tests/unit/schedules/test_timesheet_batch_schema.py
"""Schéma de lot natif et wrapper texte de couche PDF."""

import pytest

pytestmark = pytest.mark.unit


def test_batch_schema_wraps_page_schema_with_page_index():
    from app.modules.schedules.application.timesheet_page_schema import (
        BATCH_EXTRACTION_JSON_SCHEMA,
        PAGE_EXTRACTION_JSON_SCHEMA,
    )

    items = BATCH_EXTRACTION_JSON_SCHEMA["properties"]["pages"]["items"]
    assert "page_index" in items["properties"]
    assert "page_index" in items["required"]
    for key in PAGE_EXTRACTION_JSON_SCHEMA["properties"]:
        assert key in items["properties"]
    assert BATCH_EXTRACTION_JSON_SCHEMA["required"] == ["pages"]


def test_batch_prompt_mentions_page_range():
    from app.modules.schedules.application.timesheet_page_schema import (
        build_batch_user_prompt_native,
    )

    prompt = build_batch_user_prompt_native(
        page_start=3, page_end=4, pages_total=9, matricule_hint="Matricules GTA connus : 007."
    )
    assert "3" in prompt and "4" in prompt and "9" in prompt
    assert "007" in prompt


def test_extract_pdf_text_layer_returns_empty_for_non_pdf():
    from app.shared.infrastructure.documents.text_extraction import extract_pdf_text_layer

    assert extract_pdf_text_layer(b"pas un pdf") == ""
```

- [ ] **Step 2: Vérifier l'échec**

Run: `cd backend && ./venv/bin/python -m pytest tests/unit/schedules/test_timesheet_batch_schema.py -q`
Expected: FAIL — `ImportError` sur les nouveaux symboles

- [ ] **Step 3: Implémentation minimale**

Dans `timesheet_page_schema.py`, ajouter en fin de fichier :

```python
# --- Extraction native par lot (mode TIMESHEET_EXTRACT_MODE=native) ---

_BATCH_PAGE_ITEM_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        **PAGE_EXTRACTION_JSON_SCHEMA["properties"],
        "page_index": {"type": "integer"},
    },
    "required": [*PAGE_EXTRACTION_JSON_SCHEMA["required"], "page_index"],
}

BATCH_EXTRACTION_JSON_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"pages": {"type": "array", "items": _BATCH_PAGE_ITEM_SCHEMA}},
    "required": ["pages"],
}


def build_batch_user_prompt_native(
    *, page_start: int, page_end: int, pages_total: int, matricule_hint: str
) -> str:
    """Consigne utilisateur pour un lot de pages PDF envoyé nativement."""
    return (
        f"Le document PDF joint contient les pages {page_start} à {page_end} "
        f"d'un relevé de pointeuse qui en compte {pages_total}.\n"
        "Renvoie un élément par page dans `pages`, avec `page_index` égal au "
        "numéro de page dans le document COMPLET (pas dans le lot).\n"
        f"{matricule_hint}".strip()
    )
```

Dans `text_extraction.py`, ajouter en fin de fichier :

```python
def extract_pdf_text_layer(file_content: bytes) -> str:
    """Texte de la couche PDF seul (pdfplumber), sans jamais déclencher l'OCR.

    Chaîne vide pour un scan, une image ou un PDF illisible : l'appelant du
    mode natif saute alors la détection de période plutôt que payer un OCR.
    """
    if not file_content or not file_content[:4] == b"%PDF":
        return ""
    try:
        return _extract_pdf_native(file_content) or ""
    except Exception:  # pragma: no cover - repli défensif
        return ""
```

- [ ] **Step 4: Vérifier le vert**

Run: `cd backend && ./venv/bin/python -m pytest tests/unit/schedules/test_timesheet_batch_schema.py tests/unit/schedules -q`
Expected: nouveau fichier `3 passed`, aucun autre test cassé

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/schedules/application/timesheet_page_schema.py backend/app/shared/infrastructure/documents/text_extraction.py backend/tests/unit/schedules/test_timesheet_batch_schema.py
git commit -m "feat(schedules): schéma de lot natif et texte de couche PDF sans OCR

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Extracteur natif de relevés

**Files:**
- Create: `backend/app/modules/schedules/application/timesheet_native_extract.py`
- Modify: `backend/app/modules/schedules/application/timesheet_extract_config.py` (mode `native` + taille de lot)
- Test: `backend/tests/unit/schedules/test_timesheet_native_extract.py`

**Interfaces:**
- Consumes: `extract_structured_json_from_pdf` (Task 2), `split_pdf_into_batches`/`PdfBatch` (Task 3), `BATCH_EXTRACTION_JSON_SCHEMA`, `build_batch_user_prompt_native`, `extract_pdf_text_layer` (Task 4), `build_page_consensus`, `merge_page_results`, `HybridExtractResult`, `_merged_to_cegid_result`, `_CEGID_FALLBACK_THRESHOLD`, `_matricule_hint` (import depuis `timesheet_hybrid_extract`), `build_page_system_prompt`, `build_page_user_prompt_vision`, `extract_structured_json_from_image`, `best_deterministic_parse`, `timesheet_vision_model`, `timesheet_page_concurrency`.
- Produces:
  - `timesheet_extract_config.timesheet_extract_mode()` accepte `"native"` (défaut inchangé `"hybrid"`).
  - `timesheet_extract_config.timesheet_native_batch_size() -> int` (env `TIMESHEET_NATIVE_BATCH_PAGES`, défaut 4, borné 1–10).
  - `extract_timesheet_native(*, file_content: bytes, filename: str, year: int, month: int, known_matricules: list[str] | None = None, on_progress: Callable[[dict], None] | None = None, week_anchor_context: str = "", week_anchor_date: date | None = None, punch_settings: PunchAccountingSettings | None = None) -> HybridExtractResult` — façade sync (`asyncio.run`), `extraction_method` = `"native_pdf"` ou `"native_image"`.

- [ ] **Step 1: Modifier la config (test d'abord)**

Ajouter à `backend/tests/unit/schedules/test_timesheet_native_extract.py` :

```python
# backend/tests/unit/schedules/test_timesheet_native_extract.py
"""Extracteur natif : config, lots parallèles, heartbeats, repli déterministe."""

import io

import pytest
from PyPDF2 import PdfWriter

pytestmark = pytest.mark.unit


def _blank_pdf(pages: int) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_mode_native_is_accepted(monkeypatch):
    from app.modules.schedules.application import timesheet_extract_config as cfg

    monkeypatch.setenv("TIMESHEET_EXTRACT_MODE", "native")
    assert cfg.timesheet_extract_mode() == "native"


def test_batch_size_default_and_clamp(monkeypatch):
    from app.modules.schedules.application import timesheet_extract_config as cfg

    monkeypatch.delenv("TIMESHEET_NATIVE_BATCH_PAGES", raising=False)
    assert cfg.timesheet_native_batch_size() == 4
    monkeypatch.setenv("TIMESHEET_NATIVE_BATCH_PAGES", "99")
    assert cfg.timesheet_native_batch_size() == 10
    monkeypatch.setenv("TIMESHEET_NATIVE_BATCH_PAGES", "0")
    assert cfg.timesheet_native_batch_size() == 1
```

- [ ] **Step 2: Vérifier l'échec, implémenter la config, vérifier le vert**

Run: `cd backend && ./venv/bin/python -m pytest tests/unit/schedules/test_timesheet_native_extract.py -q`
Expected: FAIL (`native` refusé, fonction absente). Puis dans `timesheet_extract_config.py` :

```python
def timesheet_extract_mode() -> str:
    raw = os.getenv("TIMESHEET_EXTRACT_MODE", "hybrid").strip().lower()
    if raw in ("deterministic", "hybrid", "llm_document", "native"):
        return raw
    return "hybrid"


def timesheet_native_batch_size() -> int:
    raw = os.getenv("TIMESHEET_NATIVE_BATCH_PAGES", "4").strip()
    try:
        return max(1, min(10, int(raw)))
    except ValueError:
        return 4
```

Re-run: Expected `2 passed`.

- [ ] **Step 3: Test de l'orchestration native (échec attendu)**

Ajouter au même fichier de test :

```python
def _canned_batch_payload(page_indices):
    from app.shared.infrastructure.ai.structured_extractor import StructuredExtractionResult

    return StructuredExtractionResult(
        data={
            "pages": [
                {
                    "page_index": idx,
                    "employees": [
                        {
                            "raw_name": f"Emp Page{idx}",
                            "matricule": str(idx).zfill(3),
                            "days": [{"jour": 2, "heures": 7.0}],
                            "weekly_total_pdf": None,
                            "warnings": [],
                        }
                    ],
                    "page_period_hint": None,
                    "confidence": 0.9,
                    "warnings": [],
                }
                for idx in page_indices
            ]
        },
        tokens_used=100,
    )


def test_native_pdf_extraction_merges_batches_and_heartbeats(monkeypatch):
    from app.modules.schedules.application import timesheet_native_extract as native

    async def fake_pdf_extract(**kwargs):
        prompt = kwargs["user_prompt"]
        # Le prompt contient « pages X à Y » — retrouver le lot par ses bornes.
        import re

        start, end = map(int, re.search(r"pages (\d+) à (\d+)", prompt).groups())
        return _canned_batch_payload(list(range(start, end + 1)))

    monkeypatch.setattr(native, "extract_structured_json_from_pdf", fake_pdf_extract)
    monkeypatch.setenv("TIMESHEET_NATIVE_BATCH_PAGES", "2")
    events = []

    result = native.extract_timesheet_native(
        file_content=_blank_pdf(3),
        filename="releve.pdf",
        year=2026,
        month=6,
        on_progress=events.append,
    )

    assert result.extraction_method == "native_pdf"
    assert result.pages_total == 3 and result.pages_processed == 3
    assert len(result.parse_result.employees) == 3
    assert result.tokens_used == 200  # 2 lots × 100
    phases = [e["phase"] for e in events]
    assert phases[0] == "extracting" and phases[-1] == "merging"
    assert events[-2]["pages_done"] == 3


def test_native_batch_failure_yields_page_warnings(monkeypatch):
    from app.modules.schedules.application import timesheet_native_extract as native

    async def failing_extract(**kwargs):
        return None

    monkeypatch.setattr(native, "extract_structured_json_from_pdf", failing_extract)
    monkeypatch.setenv("TIMESHEET_NATIVE_BATCH_PAGES", "4")

    result = native.extract_timesheet_native(
        file_content=_blank_pdf(2), filename="r.pdf", year=2026, month=6
    )

    assert result.parse_result.employees == []
    joined = " ".join(w for p in result.page_results for w in p.warnings)
    assert "échouée" in joined


def test_deterministic_text_layer_short_circuits_llm(monkeypatch):
    """Couche texte Cegid confiante → aucun appel IA (fast path de la spec)."""
    from unittest.mock import AsyncMock

    from app.modules.schedules.application import timesheet_native_extract as native
    from app.modules.schedules.application.parsers.cegid_weekly import (
        CegidDayEntry,
        CegidEmployeeBlock,
        CegidParseResult,
    )
    from types import SimpleNamespace

    block = CegidEmployeeBlock(
        matricule="001",
        raw_name="Emp Direct",
        days=[CegidDayEntry(jour=2, month=6, year=2026, heures=7.0)],
        week_days=[],
        weekly_total_hours=None,
        days_expected_count=1,
        days_parsed_count=1,
        parse_warnings=[],
    )
    det = SimpleNamespace(
        parse_result=CegidParseResult(
            format_detected=True, confidence=0.9, employees=[block]
        ),
        parser_key="cegid_weekly",
    )
    monkeypatch.setattr(native, "extract_pdf_text_layer", lambda _: "SEMAINE 22 ...")
    monkeypatch.setattr(native, "best_deterministic_parse", lambda *a, **k: det)
    mock_llm = AsyncMock()
    monkeypatch.setattr(native, "extract_structured_json_from_pdf", mock_llm)

    result = native.extract_timesheet_native(
        file_content=_blank_pdf(1), filename="cegid.pdf", year=2026, month=6
    )

    mock_llm.assert_not_called()
    assert result.extraction_method == "native_text_layer"
    assert len(result.parse_result.employees) == 1
```

Run: `cd backend && ./venv/bin/python -m pytest tests/unit/schedules/test_timesheet_native_extract.py -q`
Expected: FAIL — module `timesheet_native_extract` inexistant

- [ ] **Step 4: Implémentation**

```python
# backend/app/modules/schedules/application/timesheet_native_extract.py
"""Extraction native des relevés : PDF envoyé au modèle par lots, sans OCR local."""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any, Callable

from app.modules.schedules.application.timesheet_extract_config import (
    timesheet_native_batch_size,
    timesheet_page_concurrency,
    timesheet_vision_model,
)
from app.modules.schedules.application.timesheet_hybrid_extract import (
    _CEGID_FALLBACK_THRESHOLD,
    _matricule_hint,
    _merged_to_cegid_result,
    HybridExtractResult,
)
from app.modules.schedules.application.timesheet_import.registry import (
    best_deterministic_parse,
)
from app.modules.schedules.application.timesheet_page_consensus import (
    PageExtractionResult,
    build_page_consensus,
)
from app.modules.schedules.application.timesheet_page_merge import merge_page_results
from app.modules.schedules.application.timesheet_page_schema import (
    BATCH_EXTRACTION_JSON_SCHEMA,
    PAGE_EXTRACTION_JSON_SCHEMA,
    build_batch_user_prompt_native,
    build_page_system_prompt,
    build_page_user_prompt_vision,
)
from app.modules.schedules.domain.punch_accounting_entities import (
    PunchAccountingSettings,
)
from app.shared.infrastructure.ai import is_llm_configured
from app.shared.infrastructure.ai.structured_document import (
    extract_structured_json_from_pdf,
)
from app.shared.infrastructure.ai.structured_vision import (
    extract_structured_json_from_image,
)
from app.shared.infrastructure.documents.pdf_batches import (
    PdfBatch,
    split_pdf_into_batches,
)
from app.shared.infrastructure.documents.text_extraction import (
    DocumentExtractionError,
    extract_pdf_text_layer,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[dict[str, Any]], None]

# Aligné sur _CEGID_CONFIDENCE_THRESHOLD d'ai_fill : au-delà, le parseur
# déterministe suffit et aucun appel IA n'est nécessaire (spec §3.2-1).
_DETERMINISTIC_SHORTCIRCUIT_CONFIDENCE = 0.75

_IMAGE_MIMES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".heic": "image/heic",
}


def _is_pdf(file_content: bytes, filename: str) -> bool:
    return file_content[:4] == b"%PDF" or (filename or "").lower().endswith(".pdf")


def _image_mime(filename: str) -> str:
    from pathlib import Path

    return _IMAGE_MIMES.get(Path((filename or "")).suffix.lower(), "image/png")


def _consensus_from_page_data(
    page_data: dict[str, Any],
    *,
    fallback_index: int,
    tokens: int,
    year: int,
    month: int,
    punch_settings: PunchAccountingSettings | None,
) -> PageExtractionResult:
    idx = page_data.get("page_index")
    page_index = int(idx) if isinstance(idx, int) and idx > 0 else fallback_index
    return build_page_consensus(
        page_index=page_index,
        vision_data=page_data,
        text_data=None,
        tokens_used=tokens,
        year=year,
        month=month,
        format_hint=None,
        punch_settings=punch_settings,
    )


async def _extract_pdf_batches_async(
    *,
    file_content: bytes,
    year: int,
    month: int,
    mat_hint: str,
    week_anchor_context: str,
    punch_settings: PunchAccountingSettings | None,
    on_progress: ProgressCallback | None,
) -> tuple[list[PageExtractionResult], int, int]:
    batches = split_pdf_into_batches(
        file_content, batch_size=timesheet_native_batch_size()
    )
    pages_total = batches[-1].page_end if batches else 0
    semaphore = asyncio.Semaphore(timesheet_page_concurrency())
    page_results: list[PageExtractionResult] = []
    tokens_total = 0
    done_pages = 0

    def _heartbeat(current_page: int) -> None:
        if on_progress:
            on_progress(
                {
                    "phase": "extracting",
                    "pages_total": pages_total,
                    "pages_done": done_pages,
                    "current_page": current_page,
                }
            )

    async def _run_batch(batch: PdfBatch):
        async with semaphore:
            _heartbeat(batch.page_start)
            payload = await extract_structured_json_from_pdf(
                system_prompt=build_page_system_prompt(
                    year=year,
                    month=month,
                    channel="vision",
                    week_anchor_context=week_anchor_context,
                ),
                user_prompt=build_batch_user_prompt_native(
                    page_start=batch.page_start,
                    page_end=batch.page_end,
                    pages_total=pages_total,
                    matricule_hint=mat_hint,
                ),
                pdf_bytes=batch.content,
                filename=f"pages-{batch.page_start}-{batch.page_end}.pdf",
                json_schema=BATCH_EXTRACTION_JSON_SCHEMA,
                schema_name="timesheet_batch_native",
                model=timesheet_vision_model(),
                max_tokens=8192,
            )
            return batch, payload

    _heartbeat(0)
    for coro in asyncio.as_completed([_run_batch(b) for b in batches]):
        batch, payload = await coro
        batch_pages = list(range(batch.page_start, batch.page_end + 1))
        if payload is None:
            for idx in batch_pages:
                page_results.append(
                    PageExtractionResult(
                        page_index=idx,
                        warnings=[f"Page {idx} : extraction native échouée."],
                    )
                )
        else:
            pages = payload.data.get("pages") or []
            per_page_tokens = payload.tokens_used // max(1, len(pages))
            for offset, page_data in enumerate(pages):
                page_results.append(
                    _consensus_from_page_data(
                        page_data,
                        fallback_index=batch_pages[min(offset, len(batch_pages) - 1)],
                        tokens=per_page_tokens,
                        year=year,
                        month=month,
                        punch_settings=punch_settings,
                    )
                )
            tokens_total += payload.tokens_used
        done_pages += len(batch_pages)
        _heartbeat(batch.page_end)

    return page_results, tokens_total, pages_total


def extract_timesheet_native(
    *,
    file_content: bytes,
    filename: str,
    year: int,
    month: int,
    known_matricules: list[str] | None = None,
    on_progress: ProgressCallback | None = None,
    week_anchor_context: str = "",
    week_anchor_date: date | None = None,
    punch_settings: PunchAccountingSettings | None = None,
) -> HybridExtractResult:
    """Même contrat de sortie que l'hybride, sans OCR local ni rendu 300 DPI."""
    if not is_llm_configured():
        raise DocumentExtractionError(
            "L'extraction native nécessite OPENROUTER_API_KEY."
        )
    mat_hint = _matricule_hint(known_matricules or [])

    if _is_pdf(file_content, filename):
        # Fast path spec §3.2-1 : couche texte Cegid confiante → zéro appel IA.
        text_layer = extract_pdf_text_layer(file_content)
        if text_layer:
            det = best_deterministic_parse(text_layer, year=year, month=month)
            if (
                det.parse_result
                and det.parse_result.format_detected
                and det.parse_result.confidence >= _DETERMINISTIC_SHORTCIRCUIT_CONFIDENCE
                and det.parse_result.employees
            ):
                from app.modules.schedules.application.timesheet_page_merge import (
                    MergedExtractionResult,
                )

                pages = 1
                if on_progress:
                    on_progress(
                        {
                            "phase": "merging",
                            "pages_total": pages,
                            "pages_done": pages,
                            "current_page": pages,
                        }
                    )
                return HybridExtractResult(
                    parse_result=det.parse_result,
                    full_ocr_text=text_layer,
                    extraction_method="native_text_layer",
                    pages_total=pages,
                    pages_processed=pages,
                    truncated=False,
                    merged=MergedExtractionResult(
                        confidence=det.parse_result.confidence
                    ),
                    used_cegid_fallback=True,
                    fallback_parser_key=det.parser_key,
                )

        page_results, tokens_total, pages_total = asyncio.run(
            _extract_pdf_batches_async(
                file_content=file_content,
                year=year,
                month=month,
                mat_hint=mat_hint,
                week_anchor_context=week_anchor_context,
                punch_settings=punch_settings,
                on_progress=on_progress,
            )
        )
        # text_layer déjà calculé avant le fast path déterministe.
        method = "native_pdf"
    else:
        vision = extract_structured_json_from_image(
            system_prompt=build_page_system_prompt(
                year=year,
                month=month,
                channel="vision",
                week_anchor_context=week_anchor_context,
            ),
            user_prompt=build_page_user_prompt_vision(
                page_index=1, pages_total=1, matricule_hint=mat_hint
            ),
            image_bytes=file_content,
            mime_type=_image_mime(filename),
            json_schema=PAGE_EXTRACTION_JSON_SCHEMA,
            schema_name="timesheet_page_vision",
            model=timesheet_vision_model(),
            max_tokens=4096,
        )
        if vision is None:
            page_results = [
                PageExtractionResult(
                    page_index=1, warnings=["Page 1 : extraction native échouée."]
                )
            ]
            tokens_total = 0
        else:
            page_results = [
                build_page_consensus(
                    page_index=1,
                    vision_data=vision.data,
                    text_data=None,
                    tokens_used=vision.tokens_used,
                    year=year,
                    month=month,
                    format_hint=None,
                    punch_settings=punch_settings,
                )
            ]
            tokens_total = vision.tokens_used
        pages_total = 1
        text_layer = ""
        method = "native_image"

    page_results.sort(key=lambda p: p.page_index)
    merged = merge_page_results(page_results, format_hint=None)

    from app.modules.schedules.application.parsers.cegid_weekly import CegidParseResult

    fallback_attempt = best_deterministic_parse(text_layer, year=year, month=month)
    cegid_fallback = fallback_attempt.parse_result or CegidParseResult(
        format_detected=False, confidence=0.0
    )

    used_fallback = False
    if merged.confidence < _CEGID_FALLBACK_THRESHOLD and cegid_fallback.employees:
        if cegid_fallback.confidence > merged.confidence or len(
            cegid_fallback.employees
        ) > len(merged.employees):
            parse_result = cegid_fallback
            used_fallback = True
        else:
            parse_result = _merged_to_cegid_result(
                merged,
                target_year=year,
                target_month=month,
                cegid_fallback=cegid_fallback,
                week_anchor_date=week_anchor_date,
            )
    else:
        parse_result = _merged_to_cegid_result(
            merged,
            target_year=year,
            target_month=month,
            cegid_fallback=cegid_fallback,
            week_anchor_date=week_anchor_date,
        )

    warnings: list[str] = []
    if used_fallback:
        warnings.append("Repli parseur Cegid utilisé (confiance native insuffisante).")

    if on_progress:
        on_progress(
            {
                "phase": "merging",
                "pages_total": pages_total,
                "pages_done": pages_total,
                "current_page": pages_total,
            }
        )

    return HybridExtractResult(
        parse_result=parse_result,
        full_ocr_text=text_layer,
        extraction_method=method,
        pages_total=pages_total,
        pages_processed=pages_total,
        truncated=False,
        warnings=warnings,
        page_results=page_results,
        merged=merged,
        tokens_used=tokens_total,
        consensus_conflicts=merged.conflicts_count,
        used_cegid_fallback=used_fallback,
        fallback_parser_key=fallback_attempt.parser_key if used_fallback else None,
    )


__all__ = ["extract_timesheet_native"]
```

- [ ] **Step 5: Vérifier le vert**

Run: `cd backend && ./venv/bin/python -m pytest tests/unit/schedules/test_timesheet_native_extract.py -q`
Expected: `5 passed`

- [ ] **Step 6: Non-régression module schedules**

Run: `cd backend && ./venv/bin/python -m pytest tests/unit/schedules -q`
Expected: tout vert

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/schedules/application/timesheet_native_extract.py backend/app/modules/schedules/application/timesheet_extract_config.py backend/tests/unit/schedules/test_timesheet_native_extract.py
git commit -m "feat(schedules): extracteur natif de relevés par lots PDF parallèles

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Dispatch du mode natif dans ai_fill

**Files:**
- Modify: `backend/app/modules/schedules/application/ai_fill.py` (fonction `extract_timesheet` ~l.1152 et `_extract_timesheet_hybrid_path` ~l.923)
- Test: `backend/tests/unit/schedules/test_ai_fill_native_dispatch.py`

**Interfaces:**
- Consumes: `extract_timesheet_native` (Task 5), `extract_pdf_text_layer` (Task 4).
- Produces: `ai_fill.extract_timesheet(...)` route le mode `native` vers le même chemin que `hybrid` avec `mode="native"` ; `_extract_timesheet_hybrid_path(..., mode: str = "hybrid")` choisit l'extracteur et, en natif, remplace le pré-scan OCR par `extract_pdf_text_layer` (pré-scan sauté si texte vide).

- [ ] **Step 1: Écrire le test qui échoue**

```python
# backend/tests/unit/schedules/test_ai_fill_native_dispatch.py
"""Le mode TIMESHEET_EXTRACT_MODE=native route vers l'extracteur natif sans OCR."""

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


def _canned_hybrid_result():
    from app.modules.schedules.application.parsers.cegid_weekly import (
        CegidDayEntry,
        CegidEmployeeBlock,
        CegidParseResult,
    )
    from app.modules.schedules.application.timesheet_hybrid_extract import (
        HybridExtractResult,
    )
    from app.modules.schedules.application.timesheet_page_merge import (
        MergedExtractionResult,
    )

    block = CegidEmployeeBlock(
        matricule="001",
        raw_name="Test Emp",
        days=[CegidDayEntry(jour=2, month=6, year=2026, heures=7.0)],
        week_days=[],
        weekly_total_hours=None,
        days_expected_count=1,
        days_parsed_count=1,
        parse_warnings=[],
    )
    return HybridExtractResult(
        parse_result=CegidParseResult(
            format_detected=True, confidence=0.9, employees=[block]
        ),
        full_ocr_text="",
        extraction_method="native_pdf",
        pages_total=1,
        pages_processed=1,
        truncated=False,
        merged=MergedExtractionResult(employees=[], confidence=0.9),
    )


def test_native_mode_calls_native_extractor_not_ocr(monkeypatch):
    from app.modules.schedules.application import ai_fill

    monkeypatch.setenv("TIMESHEET_EXTRACT_MODE", "native")

    with (
        patch.object(
            ai_fill, "_native_extractor", return_value=_canned_hybrid_result()
        ) as mock_native,
        patch(
            "app.modules.schedules.application.ai_fill.extract_document_text"
        ) as mock_ocr_prescan,
    ):
        response = ai_fill.extract_timesheet(
            year=2026,
            month=6,
            file_content=b"%PDF-1.4 fake",
            filename="releve.pdf",
            roster=[],
            skip_audit=True,
        )

    mock_native.assert_called_once()
    mock_ocr_prescan.assert_not_called()
    assert response.extraction_method == "native_pdf"
```

Note : le test référence `ai_fill._native_extractor`, un alias module-level introduit au Step 3 pour rendre l'extracteur patchable.

- [ ] **Step 2: Vérifier l'échec**

Run: `cd backend && ./venv/bin/python -m pytest tests/unit/schedules/test_ai_fill_native_dispatch.py -q`
Expected: FAIL — `AttributeError: _native_extractor` (ou mode natif non routé)

- [ ] **Step 3: Implémentation**

Dans `ai_fill.py` :

1. Ajouter près des imports du module (niveau module, après les imports existants) :

```python
from app.modules.schedules.application.timesheet_native_extract import (
    extract_timesheet_native as _native_extractor,
)
from app.shared.infrastructure.documents.text_extraction import (  # noqa: F811 - complète l'import existant
    extract_pdf_text_layer,
)
```

2. Signature de `_extract_timesheet_hybrid_path` : ajouter le paramètre `mode: str = "hybrid"`.

3. Dans `_extract_timesheet_hybrid_path`, remplacer le bloc pré-scan actuel :

```python
    try:
        preview_text, _, _ = extract_document_text(file_content, filename)
    except DocumentExtractionError as e:
        raise ScheduleAppError("validation", str(e), status_code=400) from e

    period_detection = detect_timesheet_period(
```

par :

```python
    if mode == "native":
        # Jamais d'OCR en natif : couche texte PDF seule, pré-scan sauté sinon.
        preview_text = extract_pdf_text_layer(file_content)
    else:
        try:
            preview_text, _, _ = extract_document_text(file_content, filename)
        except DocumentExtractionError as e:
            raise ScheduleAppError("validation", str(e), status_code=400) from e

    period_detection = detect_timesheet_period(
```

et garder `detect_timesheet_period(preview_text or "", ...)` inchangé pour le reste.

4. Toujours dans `_extract_timesheet_hybrid_path`, remplacer l'appel :

```python
        hybrid = extract_timesheet_hybrid(
```

par :

```python
        extractor = _native_extractor if mode == "native" else extract_timesheet_hybrid
        hybrid = extractor(
```

(les kwargs existants sont identiques dans les deux signatures).

5. Dans `extract_timesheet`, remplacer :

```python
    if extract_mode == "hybrid":
        return _extract_timesheet_hybrid_path(
```

par :

```python
    if extract_mode in ("hybrid", "native"):
        return _extract_timesheet_hybrid_path(
            mode=extract_mode,
```

(en conservant tous les kwargs existants à la suite).

- [ ] **Step 4: Vérifier le vert + non-régression**

Run: `cd backend && ./venv/bin/python -m pytest tests/unit/schedules/test_ai_fill_native_dispatch.py tests/unit/schedules tests/integration/participation -q`
Expected: tout vert

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/schedules/application/ai_fill.py backend/tests/unit/schedules/test_ai_fill_native_dispatch.py
git commit -m "feat(schedules): mode natif routé dans extract_timesheet sans pré-scan OCR

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Watchdog des jobs zombies

**Files:**
- Modify: `backend/app/modules/schedules/application/timesheet_import_service.py` (fonction `get_import_job`, ~l.125)
- Test: `backend/tests/unit/schedules/test_timesheet_import_watchdog.py`

**Interfaces:**
- Consumes: `_update_job` (stampe déjà `updated_at` à chaque heartbeat `on_progress`).
- Produces: `get_import_job` marque `failed` (colonnes `status`, `error_message`, `completed_at`) tout job `extracting` dont `updated_at` date de plus de `_STALE_EXTRACTING_SECONDS = 300` secondes, et renvoie le job mis à jour. Le front existant affiche déjà `error_message` et permet de relancer (les fichiers restent dans le dialogue).

- [ ] **Step 1: Écrire le test qui échoue**

```python
# backend/tests/unit/schedules/test_timesheet_import_watchdog.py
"""Un job « extracting » sans heartbeat depuis > 5 min est marqué failed."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _job_row(status: str, updated_minutes_ago: float) -> dict:
    return {
        "id": "job-1",
        "status": status,
        "updated_at": (
            datetime.now(timezone.utc) - timedelta(minutes=updated_minutes_ago)
        ).isoformat(),
    }


def _db_returning(row: dict) -> MagicMock:
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = row
    return db


def test_stale_extracting_job_marked_failed():
    from app.modules.schedules.application import timesheet_import_service as svc

    with (
        patch.object(svc, "_db", return_value=_db_returning(_job_row("extracting", 6))),
        patch.object(svc, "_update_job") as mock_update,
    ):
        job = svc.get_import_job("job-1")

    assert job["status"] == "failed"
    assert "interrompue" in job["error_message"]
    payload = mock_update.call_args.args[1]
    assert payload["status"] == "failed"


def test_fresh_extracting_job_untouched():
    from app.modules.schedules.application import timesheet_import_service as svc

    with (
        patch.object(svc, "_db", return_value=_db_returning(_job_row("extracting", 1))),
        patch.object(svc, "_update_job") as mock_update,
    ):
        job = svc.get_import_job("job-1")

    assert job["status"] == "extracting"
    mock_update.assert_not_called()


def test_completed_job_untouched():
    from app.modules.schedules.application import timesheet_import_service as svc

    with (
        patch.object(svc, "_db", return_value=_db_returning(_job_row("completed", 60))),
        patch.object(svc, "_update_job") as mock_update,
    ):
        job = svc.get_import_job("job-1")

    assert job["status"] == "completed"
    mock_update.assert_not_called()
```

- [ ] **Step 2: Vérifier l'échec**

Run: `cd backend && ./venv/bin/python -m pytest tests/unit/schedules/test_timesheet_import_watchdog.py -q`
Expected: FAIL — le job périmé reste `extracting`

- [ ] **Step 3: Implémentation**

Dans `timesheet_import_service.py`, au-dessus de `get_import_job` :

```python
# > 2 × le pire cas d'un lot natif (lecture 120 s × 2 tentatives) : au-delà,
# l'instance qui portait le job est morte (OOM/redémarrage) et personne ne
# marquera jamais l'échec — c'est le bug de l'attente infinie du 29/08.
_STALE_EXTRACTING_SECONDS = 300


def _parse_iso_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
```

et remplacer le corps de `get_import_job` :

```python
def get_import_job(job_id: str, *, company_id: str | None = None) -> dict[str, Any] | None:
    query = _db().table("schedule_import_jobs").select("*").eq("id", job_id)
    if company_id:
        query = query.eq("company_id", company_id)
    result = query.maybe_single().execute()
    job = result.data
    if job and job.get("status") == "extracting":
        heartbeat = _parse_iso_datetime(job.get("updated_at"))
        stale = (
            heartbeat is None
            or (datetime.now(timezone.utc) - heartbeat).total_seconds()
            > _STALE_EXTRACTING_SECONDS
        )
        if stale:
            message = (
                "L'analyse a été interrompue (instance redémarrée). "
                "Relancez l'import."
            )
            _update_job(
                job_id,
                {
                    "status": "failed",
                    "error_message": message,
                    "completed_at": _now_iso(),
                },
            )
            job = {**job, "status": "failed", "error_message": message}
    return job
```

- [ ] **Step 4: Vérifier le vert + non-régression**

Run: `cd backend && ./venv/bin/python -m pytest tests/unit/schedules/test_timesheet_import_watchdog.py tests/unit/schedules -q`
Expected: tout vert

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/schedules/application/timesheet_import_service.py backend/tests/unit/schedules/test_timesheet_import_watchdog.py
git commit -m "fix(schedules): watchdog des jobs d'import sans heartbeat

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: P2 — timeout du remplissage NL et endpoint non bloquant

**Files:**
- Modify: `backend/app/shared/infrastructure/ai/structured_extractor.py` (paramètre `timeout`)
- Modify: `backend/app/modules/schedules/application/ai_fill.py` (appel `extract_structured_json` du remplissage NL, ~l.876)
- Modify: `backend/app/modules/schedules/api/router.py` (route `assisted_fill_extract_timesheet`, ~l.400)
- Test: `backend/tests/unit/shared_ai/test_structured_extractor_timeout.py`

**Interfaces:**
- Consumes: `chat_completions_create` (client sync existant — accepte `timeout` par requête via le SDK openai).
- Produces: `extract_structured_json(..., timeout: float | None = None)` ; le remplissage NL passe `timeout=60.0` ; la route sync d'extraction est exécutée via `run_in_threadpool` pour ne plus geler l'event loop (la route `parse-text` est un `def` : FastAPI la met déjà en threadpool, ne pas la changer).

- [ ] **Step 1: Écrire le test qui échoue**

```python
# backend/tests/unit/shared_ai/test_structured_extractor_timeout.py
"""extract_structured_json transmet le timeout par requête au client."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def test_timeout_forwarded_to_client():
    from app.shared.infrastructure.ai import structured_extractor as se

    fake_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": 1}'))],
        usage=SimpleNamespace(total_tokens=5),
    )
    with (
        patch.object(se, "require_llm_api_key"),
        patch.object(se, "chat_completions_create", MagicMock(return_value=fake_resp)) as mock_create,
    ):
        result = se.extract_structured_json(
            system_prompt="s",
            user_prompt="u",
            json_schema={"type": "object", "properties": {}, "additionalProperties": False},
            model="google/gemini-2.5-flash",
            timeout=60.0,
        )

    assert result is not None
    assert mock_create.call_args.kwargs["timeout"] == 60.0
```

- [ ] **Step 2: Vérifier l'échec**

Run: `cd backend && ./venv/bin/python -m pytest tests/unit/shared_ai/test_structured_extractor_timeout.py -q`
Expected: FAIL — `TypeError: unexpected keyword argument 'timeout'`

- [ ] **Step 3: Implémentation**

Dans `structured_extractor.py`, signature et kwargs :

```python
def extract_structured_json(
    *,
    system_prompt: str,
    user_prompt: str,
    json_schema: dict[str, Any],
    schema_name: str = "extraction",
    model: str,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    timeout: float | None = None,
) -> StructuredExtractionResult | None:
```

et après la construction de `request_kwargs` existante :

```python
    if timeout is not None:
        request_kwargs["timeout"] = timeout
```

Dans `ai_fill.py`, l'appel du remplissage NL (~l.876) gagne :

```python
        model=MODEL_SCHEDULE_NL_FILL,
        max_tokens=4096,
        timeout=60.0,
```

Dans `router.py`, la route sync d'extraction (~l.446) :

```python
    from starlette.concurrency import run_in_threadpool

    try:
        return await run_in_threadpool(
            lambda: ai_fill.extract_timesheet(
                year=year,
                month=month,
                file_content=content,
                filename=file.filename or "",
                roster=roster,
                single_employee=single_employee,
                document_scope=scope,
                week_anchor_date=parsed_anchor,
                company_id=current_user.active_company_id,
                user_id=current_user.id,
            )
        )
    except ScheduleAppError as e:
        _handle_schedule_error(e)
```

- [ ] **Step 4: Vérifier le vert + non-régression**

Run: `cd backend && ./venv/bin/python -m pytest tests/unit/shared_ai tests/unit/schedules tests/integration -q`
Expected: tout vert (xfail connus inchangés)

- [ ] **Step 5: Commit**

```bash
git add backend/app/shared/infrastructure/ai/structured_extractor.py backend/app/modules/schedules/application/ai_fill.py backend/app/modules/schedules/api/router.py backend/tests/unit/shared_ai/test_structured_extractor_timeout.py
git commit -m "feat(ai): timeout du remplissage NL et extraction hors event loop

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: Éval comparative et activation sur l'environnement de test

**Files:**
- Create: `backend/scripts/eval_timesheet_native_vs_hybrid.py`
- Modify: `.github/workflows/deploy-test-env.yml` (ajout `TIMESHEET_EXTRACT_MODE` dans `--set-env-vars`)
- Modify: `.github/workflows/deploy.yml` (même variable dans le bloc `env_vars` de l'étape test uniquement — PAS l'étape production)

**Interfaces:**
- Consumes: `ai_fill.extract_timesheet` (les deux modes via env), `backend/.env` (clé OpenRouter).
- Produces: script CLI `./venv/bin/python scripts/eval_timesheet_native_vs_hybrid.py <dossier_de_pdfs>` qui imprime, par fichier et par mode : durée, salariés détectés, jours remplis, confiance, tokens. La bascule prod du défaut reste MANUELLE, après revue de l'éval par Alexandre.

- [ ] **Step 1: Écrire le script**

```python
# backend/scripts/eval_timesheet_native_vs_hybrid.py
"""Compare hybrid vs native sur un dossier de relevés réels.

Usage : cd backend && ./venv/bin/python scripts/eval_timesheet_native_vs_hybrid.py <dossier>
Nécessite OPENROUTER_API_KEY (backend/.env). N'écrit rien en base (skip_audit).
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.modules.schedules.application import ai_fill  # noqa: E402


def _run(mode: str, path: Path, year: int, month: int):
    os.environ["TIMESHEET_EXTRACT_MODE"] = mode
    started = time.monotonic()
    try:
        resp = ai_fill.extract_timesheet(
            year=year,
            month=month,
            file_content=path.read_bytes(),
            filename=path.name,
            roster=[],
            skip_audit=True,
        )
        days = sum(len(e.days) for e in resp.employees)
        return {
            "durée_s": round(time.monotonic() - started, 1),
            "salariés": len(resp.employees),
            "jours": days,
            "méthode": resp.extraction_method,
            "avertissements": len(resp.warnings or []),
        }
    except Exception as exc:  # noqa: BLE001 - rapport d'éval
        return {"durée_s": round(time.monotonic() - started, 1), "erreur": str(exc)[:120]}


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    folder = Path(sys.argv[1])
    year = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
    month = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    files = sorted(
        p for p in folder.iterdir()
        if p.suffix.lower() in (".pdf", ".png", ".jpg", ".jpeg")
    )
    for path in files:
        print(f"\n=== {path.name} ===")
        for mode in ("hybrid", "native"):
            print(f"  {mode:8s} {_run(mode, path, year, month)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Vérifier le script à vide**

Run: `cd backend && ./venv/bin/python scripts/eval_timesheet_native_vs_hybrid.py`
Expected: affiche l'usage et sort en code 1 (pas de crash d'import)

- [ ] **Step 3: Activer le natif sur l'env de test**

Dans `.github/workflows/deploy-test-env.yml`, dans la chaîne `--set-env-vars`, ajouter `##TIMESHEET_EXTRACT_MODE=native` juste avant `##COPILOT_RH_DATA_ENABLED=true`.
Dans `.github/workflows/deploy.yml`, bloc `env_vars` de l'étape **test** (celle avec `APP_ENV=test`), ajouter la ligne `TIMESHEET_EXTRACT_MODE=native`. Ne PAS toucher l'étape production.

- [ ] **Step 4: Vérifier les gardes de workflow**

Run: `cd backend && ./venv/bin/python -m pytest tests/unit/copilot/test_deploy_workflow.py -q`
Expected: tout vert

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/eval_timesheet_native_vs_hybrid.py .github/workflows/deploy-test-env.yml .github/workflows/deploy.yml
git commit -m "feat(schedules): éval hybrid vs native et activation du natif sur le test

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Après le plan

1. Déployer l'env de test (`gh workflow run deploy-test-env.yml --ref <branche>`), rejouer l'import Colorplast réel.
2. Lancer l'éval comparative sur un panier de relevés réels (Colorplast, Cegid, manuscrits) et la faire relire à Alexandre.
3. Si l'éval est concluante : ajouter `TIMESHEET_EXTRACT_MODE=native` à l'étape production de `deploy.yml` (décision explicite d'Alexandre).
4. Chantier séparé (hors plan) : migration des autres modules IA sur le socle async et nettoyage de `models.py`.
