"""
yasinai_adapter.py
Adapter from YasinRelay ContentProcessor domain interface to Yasin-AI
public capability contracts (v1).

Consumes ONLY:
  - yasinai.contracts (GenerationRequest, GenerationResult, ...)
  - yasinai.services (GenerationService)

Must NOT import knowledge_platform, security_platform, developer_platform,
or other private Yasin-AI modules.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from .ai_processor import AIProcessor, ProcessedContent
from .fetch_engine import Post

logger = logging.getLogger(__name__)

# Domain-specific system prompt stays in Relay (not moved into Yasin-AI).
DEFAULT_SYSTEM_PROMPT = (
    "You are a professional content editor for Iranian social media channels "
    "(specifically Eitaa). Your task is to rewrite, translate (if in another "
    "language), or improve the following Telegram post to make it engaging, "
    "polished, and suitable for Iranian audiences. Keep emojis, layout, and "
    "meaning intact. Output ONLY the final processed text, with no introductory "
    "or concluding remarks."
)


def is_yasinai_available() -> bool:
    """Return True if public Yasin-AI packages can be imported."""
    try:
        import yasinai  # noqa: F401
        from yasinai.contracts import GenerationRequest  # noqa: F401
        from yasinai.services import GenerationService  # noqa: F401

        return True
    except ImportError:
        return False


def _ensure_openai_env_from_relay(api_key: str) -> None:
    """
    Map Relay AI_API_KEY onto OPENAI_API_KEY when the latter is unset.

    Yasin-AI OpenAIProvider reads OPENAI_API_KEY only. This preserves
    existing Relay operator env without putting secrets in source.
    """
    if api_key and not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = api_key


class YasinAIContentProcessor(AIProcessor):
    """
    ContentProcessor backed by Yasin-AI GenerationService public API.

    Failure semantics match legacy PassthroughProcessor:
    on missing capability or generation failure, return original post text.
    """

    def __init__(
        self,
        *,
        generation_service: Any = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_prompt: Optional[str] = None,
        api_key: str = "",
    ) -> None:
        _ensure_openai_env_from_relay(api_key)
        self._model = model
        self._provider = provider
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

        if generation_service is not None:
            self._service = generation_service
        else:
            from yasinai.services import GenerationService

            self._service = GenerationService()

    def process(self, post: Post) -> ProcessedContent:
        text = post.text or ""
        if not text.strip():
            return ProcessedContent(source_post=post, text=text)

        try:
            from yasinai.contracts import GenerationRequest

            request = GenerationRequest(
                prompt=text,
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                system_prompt=self._system_prompt,
                provider=self._provider,
                metadata={
                    "source": "yasinrelay",
                    "channel": post.channel,
                    "message_id": post.message_id,
                },
            )
            result = self._service.generate(request)
        except Exception as exc:
            logger.error("Yasin-AI generation failed: %s", exc, exc_info=True)
            return ProcessedContent(source_post=post, text=text)

        if not getattr(result, "success", False):
            logger.error(
                "Yasin-AI generation unsuccessful: %s",
                getattr(result, "error", "unknown"),
            )
            return ProcessedContent(source_post=post, text=text)

        out = (getattr(result, "text", None) or "").strip()
        if not out:
            return ProcessedContent(source_post=post, text=text)
        return ProcessedContent(source_post=post, text=out)

    def summarize(self, text: str) -> str:
        return self._simple_generate(
            text,
            system_prompt="Summarize the following text concisely. Output only the summary.",
        )

    def rewrite(self, text: str) -> str:
        return self._simple_generate(
            text,
            system_prompt=self._system_prompt,
        )

    def translate(self, text: str, target_lang: str = "persian") -> str:
        return self._simple_generate(
            text,
            system_prompt=(
                f"Translate the following text to {target_lang}. "
                "Output only the translation."
            ),
        )

    def generate_title(self, text: str) -> str:
        titled = self._simple_generate(
            text,
            system_prompt="Generate a short title for the following text. Output only the title.",
            max_tokens=64,
        )
        if titled == text:
            words = text.split()
            return " ".join(words[:5]) + ("..." if len(words) > 5 else "")
        return titled

    def _simple_generate(
        self,
        text: str,
        *,
        system_prompt: str,
        max_tokens: Optional[int] = None,
    ) -> str:
        if not (text or "").strip():
            return text
        try:
            from yasinai.contracts import GenerationRequest

            request = GenerationRequest(
                prompt=text,
                model=self._model,
                max_tokens=max_tokens or self._max_tokens,
                temperature=self._temperature,
                system_prompt=system_prompt,
                provider=self._provider,
            )
            result = self._service.generate(request)
            if getattr(result, "success", False) and (result.text or "").strip():
                return result.text.strip()
        except Exception as exc:
            logger.error("Yasin-AI helper generation failed: %s", exp if False else exc)
        return text


def build_content_processor(
    *,
    ai_provider: str = "yasinai",
    api_key: str = "",
    base_url: str = "https://api.openai.com/v1",
    model: str = "gpt-4o-mini",
    generation_service: Any = None,
):
    """
    Factory selecting the AI ContentProcessor implementation.

    - yasinai / default: YasinAIContentProcessor when yasinai is installed
    - passthrough / legacy: direct HTTP PassthroughProcessor (pre-migration)

    Falls back to PassthroughProcessor if yasinai is unavailable.
    """
    from .ai_processor import PassthroughProcessor

    provider = (ai_provider or "yasinai").strip().lower()

    if provider in ("passthrough", "legacy", "direct"):
        return PassthroughProcessor(api_key=api_key, base_url=base_url, model=model)

    if provider in ("yasinai", "yasin-ai", "canonical", ""):
        if generation_service is not None or is_yasinai_available():
            try:
                return YasinAIContentProcessor(
                    generation_service=generation_service,
                    model=model or None,
                    api_key=api_key,
                )
            except ImportError:
                logger.warning(
                    "Yasin-AI requested but not importable; falling back to legacy PassthroughProcessor"
                )
        else:
            logger.warning(
                "Yasin-AI package not installed; falling back to legacy PassthroughProcessor. "
                "Install Yasin-AI v1.1.4+ for canonical contracts."
            )

    return PassthroughProcessor(api_key=api_key, base_url=base_url, model=model)
