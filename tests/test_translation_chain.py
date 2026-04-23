import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from feed_pipeline import load_sources
from translation_chain import TranslationChain


class FeedConfigTests(unittest.TestCase):
    def test_load_sources_reads_expected_fields(self):
        payload = {
            "sources": [
                {
                    "id": "test_source",
                    "name": "Test Source",
                    "url": "https://example.com/rss",
                    "language": "kk",
                    "category": "general",
                    "enabled": True,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "sources.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            sources = load_sources(path)
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0].id, "test_source")
            self.assertEqual(sources[0].language, "kk")


class TranslationChainTests(unittest.TestCase):
    def test_fallback_to_ollama_when_libretranslate_fails(self):
        chain = TranslationChain()
        with patch.object(chain, "_translate_libretranslate", side_effect=RuntimeError("down")), patch.object(
            chain, "_translate_ollama", return_value="hello world"
        ):
            result = chain.translate("salem alem", "kk", "en")
            self.assertEqual(result.status, "translated")
            self.assertEqual(result.provider, "ollama")
            self.assertEqual(result.text, "hello world")

    def test_return_original_when_all_providers_fail(self):
        chain = TranslationChain()
        with patch.object(chain, "_translate_libretranslate", side_effect=RuntimeError("down")), patch.object(
            chain, "_translate_ollama", side_effect=RuntimeError("down")
        ):
            result = chain.translate("salem alem", "kk", "en")
            self.assertEqual(result.status, "failed")
            self.assertEqual(result.provider, "none")
            self.assertEqual(result.text, "salem alem")

    def test_skip_for_empty_text(self):
        chain = TranslationChain()
        result = chain.translate("", "kk", "en")
        self.assertEqual(result.status, "skipped_empty")
        self.assertEqual(result.provider, "none")

    def test_cache_hit_returns_cached_flag(self):
        chain = TranslationChain()
        with patch.object(chain, "_translate_libretranslate", return_value="first result"):
            first = chain.translate("test", "uz", "en")
            second = chain.translate("test", "uz", "en")
            self.assertEqual(first.status, "translated")
            self.assertTrue(second.cached)
            self.assertEqual(second.text, "first result")


if __name__ == "__main__":
    unittest.main()
