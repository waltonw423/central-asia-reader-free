#!/usr/bin/env python3
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from translation_chain import TranslationChain


SOURCE_CONFIG_PATH = Path(__file__).with_name("sources.json")


@dataclass
class FeedSource:
    id: str
    name: str
    url: str
    language: str
    category: str
    enabled: bool


def load_sources(path: Path = SOURCE_CONFIG_PATH) -> List[FeedSource]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    sources = []
    for item in raw.get("sources", []):
        sources.append(
            FeedSource(
                id=item["id"],
                name=item["name"],
                url=item["url"],
                language=item["language"],
                category=item.get("category", "general"),
                enabled=bool(item.get("enabled", True)),
            )
        )
    return sources


def _text(node, tag_names: List[str]) -> str:
    for tag in tag_names:
        value = node.findtext(tag)
        if value and value.strip():
            return value.strip()
    return ""


def parse_feed(xml_bytes: bytes) -> List[Dict[str, str]]:
    root = ET.fromstring(xml_bytes)
    items: List[Dict[str, str]] = []

    # RSS
    for item in root.findall(".//channel/item"):
        items.append(
            {
                "title": _text(item, ["title"]),
                "summary": _text(item, ["description", "summary", "{http://purl.org/rss/1.0/modules/content/}encoded"]),
                "link": _text(item, ["link"]),
                "published": _text(item, ["pubDate"]),
            }
        )

    # Atom fallback
    if not items:
        atom_ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall(".//atom:entry", namespaces=atom_ns):
            link_node = entry.find("atom:link", namespaces=atom_ns)
            link_value = ""
            if link_node is not None:
                link_value = (link_node.attrib.get("href") or "").strip()
            items.append(
                {
                    "title": _text(entry, ["{http://www.w3.org/2005/Atom}title"]),
                    "summary": _text(
                        entry,
                        [
                            "{http://www.w3.org/2005/Atom}summary",
                            "{http://www.w3.org/2005/Atom}content",
                        ],
                    ),
                    "link": link_value,
                    "published": _text(entry, ["{http://www.w3.org/2005/Atom}updated"]),
                }
            )

    return items


def translate_items(
    items: List[Dict[str, str]],
    source_lang: str,
    translator: TranslationChain,
    target_lang: str = "en",
) -> List[Dict[str, str]]:
    output: List[Dict[str, str]] = []
    for item in items:
        title_result = translator.translate(item.get("title", ""), source_lang, target_lang=target_lang)
        summary_result = translator.translate(item.get("summary", ""), source_lang, target_lang=target_lang)

        output.append(
            {
                "title_original": item.get("title", ""),
                "title_translated": title_result.text,
                "summary_original": item.get("summary", ""),
                "summary_translated": summary_result.text,
                "translation_status": (
                    "failed"
                    if title_result.status == "failed" or summary_result.status == "failed"
                    else "ok"
                ),
                "translation_provider": (
                    "mixed"
                    if title_result.provider != summary_result.provider
                    else title_result.provider
                ),
                "link": item.get("link", ""),
                "published": item.get("published", ""),
            }
        )

    return output
