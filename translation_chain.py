#!/usr/bin/env python3
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SUPPORTED_LANGS = {"kk", "uz", "ky", "ru", "en"}
LOGGER = logging.getLogger("translation_chain")


@dataclass
class TranslationResult:
    text: str
    provider: str
    status: str
    source_lang: str
    target_lang: str
    cached: bool = False


class TranslationChain:
    def __init__(self) -> None:
        self.target_lang = os.getenv("TRANSLATION_TARGET_LANG", "en").strip().lower() or "en"
        self.libretranslate_url = os.getenv("LIBRETRANSLATE_URL", "http://127.0.0.1:5000").rstrip("/")
        self.ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "mistral").strip() or "mistral"
        self.timeout_seconds = float(os.getenv("TRANSLATION_TIMEOUT_SECONDS", "12"))
        self.retry_count = int(os.getenv("TRANSLATION_RETRIES", "1"))
        self.backoff_seconds = int(os.getenv("TRANSLATION_PROVIDER_BACKOFF_SECONDS", "45"))

        self._cache: Dict[Tuple[str, str, str], TranslationResult] = {}
        self._provider_open_until: Dict[str, float] = {"libretranslate": 0.0, "ollama": 0.0}

    def _normalize_lang(self, lang: str) -> str:
        lang = (lang or "").strip().lower()
        if lang in SUPPORTED_LANGS:
            return lang
        return "auto"

    def _cache_key(self, text: str, source_lang: str, target_lang: str) -> Tuple[str, str, str]:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return (digest, source_lang, target_lang)

    def _is_provider_available(self, provider: str) -> bool:
        return time.time() >= self._provider_open_until.get(provider, 0.0)

    def _trip_provider(self, provider: str) -> None:
        self._provider_open_until[provider] = time.time() + self.backoff_seconds
        LOGGER.warning("provider_backoff provider=%s seconds=%s", provider, self.backoff_seconds)

    def _post_json(self, url: str, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        req = Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=self.timeout_seconds) as resp:
            out = resp.read().decode("utf-8", errors="replace")
        return json.loads(out)

    def _translate_libretranslate(self, text: str, source_lang: str, target_lang: str) -> str:
        payload = {"q": text, "source": source_lang, "target": target_lang, "format": "text"}
        data = self._post_json(f"{self.libretranslate_url}/translate", payload)
        translated = data.get("translatedText", "").strip()
        if not translated:
            raise RuntimeError("LibreTranslate returned empty translation")
        return translated

    def _translate_ollama(self, text: str, source_lang: str, target_lang: str) -> str:
        prompt = (
            "Translate the following text from "
            f"{source_lang} to {target_lang}. Return only the translated text with no commentary:\n\n{text}"
        )
        payload = {"model": self.ollama_model, "prompt": prompt, "stream": False}
        data = self._post_json(f"{self.ollama_url}/api/generate", payload)
        translated = data.get("response", "").strip()
        if not translated:
            raise RuntimeError("Ollama returned empty translation")
        return translated

    def translate(self, text: str, source_lang: str, target_lang: Optional[str] = None) -> TranslationResult:
        source_lang = self._normalize_lang(source_lang)
        target_lang = self._normalize_lang(target_lang or self.target_lang)
        text = (text or "").strip()

        if not text:
            return TranslationResult("", "none", "skipped_empty", source_lang, target_lang)
        if source_lang == target_lang:
            return TranslationResult(text, "none", "skipped_same_language", source_lang, target_lang)
        if source_lang == "en" and target_lang == "en":
            return TranslationResult(text, "none", "skipped_english", source_lang, target_lang)

        key = self._cache_key(text, source_lang, target_lang)
        cached = self._cache.get(key)
        if cached:
            return TranslationResult(
                text=cached.text,
                provider=cached.provider,
                status=cached.status,
                source_lang=source_lang,
                target_lang=target_lang,
                cached=True,
            )

        # Try LibreTranslate first, then Ollama fallback.
        for provider in ("libretranslate", "ollama"):
            if not self._is_provider_available(provider):
                LOGGER.info("provider_skipped provider=%s reason=backoff_open", provider)
                continue

            for _ in range(self.retry_count + 1):
                try:
                    if provider == "libretranslate":
                        translated = self._translate_libretranslate(text, source_lang, target_lang)
                    else:
                        translated = self._translate_ollama(text, source_lang, target_lang)
                    result = TranslationResult(
                        text=translated,
                        provider=provider,
                        status="translated",
                        source_lang=source_lang,
                        target_lang=target_lang,
                    )
                    self._cache[key] = result
                    LOGGER.info("translation_success provider=%s source=%s target=%s", provider, source_lang, target_lang)
                    return result
                except (URLError, HTTPError, TimeoutError, RuntimeError, json.JSONDecodeError):
                    LOGGER.warning("translation_attempt_failed provider=%s source=%s target=%s", provider, source_lang, target_lang)
                    continue

            self._trip_provider(provider)

        return TranslationResult(text, "none", "failed", source_lang, target_lang)
