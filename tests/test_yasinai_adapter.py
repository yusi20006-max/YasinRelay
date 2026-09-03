"""
Contract/integration tests for Yasin-AI public-contract adapter (#43).

These tests never import Yasin-AI private modules. GenerationService is
injected as a mock so CI does not require a live Yasin-AI install or network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from yasinrelay.ai_processor import PassthroughProcessor
from yasinrelay.fetch_engine import Post
from yasinrelay.yasinai_adapter import (
    YasinAIContentProcessor,
    build_content_processor,
    is_yasinai_available,
)


@dataclass
class _FakeResult:
    success: bool
    text: str = ""
    error: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None


def test_adapter_success_rewrites_text():
    service = MagicMock()
    service.generate.return_value = _FakeResult(success=True, text="متن بهبودیافته")

    processor = YasinAIContentProcessor(generation_service=service, model="gpt-4o-mini")
    post = Post(channel="@news", message_id="1", text="raw telegram post")
    out = processor.process(post)

    assert out.text == "متن بهبودیافته"
    assert out.source_post is post
    assert service.generate.called
    req = service.generate.call_args[0][0]
    assert req.prompt == "raw telegram post"
    assert req.model == "gpt-4o-mini"
    assert req.system_prompt  # domain prompt retained in Relay


def test_adapter_failure_falls_back_to_original():
    service = MagicMock()
    service.generate.return_value = _FakeResult(success=False, error="provider down")

    processor = YasinAIContentProcessor(generation_service=service)
    post = Post(channel="@news", message_id="2", text="keep me")
    out = processor.process(post)

    assert out.text == "keep me"


def test_adapter_exception_falls_back_to_original():
    service = MagicMock()
    service.generate.side_effect = RuntimeError("boom")

    processor = YasinAIContentProcessor(generation_service=service)
    post = Post(channel="@news", message_id="3", text="original")
    out = processor.process(post)

    assert out.text == "original"


def test_adapter_empty_text_short_circuits():
    service = MagicMock()
    processor = YasinAIContentProcessor(generation_service=service)
    post = Post(channel="@news", message_id="4", text="   ")
    out = processor.process(post)
    assert out.text == "   "
    assert not service.generate.called


def test_factory_legacy_provider_returns_passthrough():
    proc = build_content_processor(ai_provider="passthrough", api_key="", model="gpt-4o-mini")
    assert isinstance(proc, PassthroughProcessor)


def test_factory_yasinai_with_injected_service():
    service = MagicMock()
    service.generate.return_value = _FakeResult(success=True, text="ok")
    proc = build_content_processor(
        ai_provider="yasinai",
        generation_service=service,
        model="gpt-4o-mini",
    )
    assert isinstance(proc, YasinAIContentProcessor)
    post = Post(channel="@c", message_id="9", text="hello")
    assert proc.process(post).text == "ok"


def test_factory_yasinai_raises_when_unavailable():
    with patch("yasinrelay.yasinai_adapter.is_yasinai_available", return_value=False):
        with pytest.raises(RuntimeError, match="Canonical Yasin-AI requested"):
            build_content_processor(ai_provider="yasinai", api_key="")


def test_factory_raises_on_unsupported_provider():
    with pytest.raises(ValueError, match="Unsupported or invalid AI_PROVIDER"):
        build_content_processor(ai_provider="unsupported_vendor")


def test_top_level_yasinai_contract_imports():
    from yasinai import GenerationRequest, GenerationService

    assert GenerationRequest is not None
    assert GenerationService is not None


def test_no_private_yasinai_imports_in_adapter_source():
    """Static guard: adapter module must not import private packages."""
    import pathlib

    source = pathlib.Path(__file__).resolve().parents[1] / "yasinrelay" / "yasinai_adapter.py"
    lines = source.read_text(encoding="utf-8").splitlines()
    import_lines = [
        ln for ln in lines
        if ln.lstrip().startswith("import ") or ln.lstrip().startswith("from ")
    ]
    joined = "\n".join(import_lines)
    for forbidden in (
        "knowledge_platform",
        "security_platform",
        "developer_platform",
        "yasinai.providers.openai_provider",
        "yasinai.private",
    ):
        assert forbidden not in joined, f"forbidden import: {forbidden}"


def test_pipeline_stage_with_adapter():
    """AIProcessorStage accepts the adapter and preserves pipeline behavior."""
    from yasinrelay.pipeline_engine import AIProcessorStage, PipelineContext

    service = MagicMock()
    service.generate.return_value = _FakeResult(success=True, text="rewritten")
    processor = YasinAIContentProcessor(generation_service=service)
    stage = AIProcessorStage(processor)

    post = Post(channel="@news", message_id="10", text="input")
    ctx = PipelineContext(post=post)
    result = stage.process(ctx)

    assert result.processed_text == "rewritten"
    assert result.is_valid is True


def test_canonical_yasinai_public_imports_and_processor_type():
    """Verify canonical public contracts and that factory produces YasinAIContentProcessor."""
    from yasinai.contracts import GenerationRequest
    from yasinai.services import GenerationService

    assert GenerationRequest is not None
    assert GenerationService is not None

    proc = build_content_processor(ai_provider="yasinai")
    assert isinstance(proc, YasinAIContentProcessor)
    assert not isinstance(proc, PassthroughProcessor)
