#!/usr/bin/env python3
import json
import logging
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen

from feed_pipeline import load_sources, parse_feed, translate_items
from translation_chain import TranslationChain
HOST = "127.0.0.1"
PORT = 8787
TIMEOUT_SECONDS = 20
# Optional: basic SSRF guard
ALLOWED_SCHEMES = {"http", "https"}


def fetch_url(target: str):
    req = Request(
        target,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RSSProxy/1.0",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        },
    )
    with urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        body = resp.read()
        ctype = resp.headers.get("Content-Type", "") or ""
        return body, ctype


class ProxyHandler(BaseHTTPRequestHandler):
    server_version = "RSSProxy/1.0"
    def _set_cors(self, status=200, content_type="text/plain; charset=utf-8"):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Type", content_type)
    def do_OPTIONS(self):
        self._set_cors(204)
        self.end_headers()
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._set_cors(200, "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return
        if parsed.path == "/sources":
            self._handle_sources()
            return
        if parsed.path == "/translated":
            self._handle_translated_feed(parsed.query)
            return
        if parsed.path not in ("/raw", "/"):
            self._set_cors(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return
        self._handle_raw(parsed.query)

    def _handle_sources(self):
        try:
            sources = load_sources()
            payload = {"sources": [s.__dict__ for s in sources]}
            self._set_cors(200, "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))
        except Exception as e:
            self._set_cors(500)
            self.end_headers()
            self.wfile.write(f"Failed loading sources: {e}".encode("utf-8"))

    def _handle_translated_feed(self, query_string: str):
        qs = parse_qs(query_string)
        source_id = qs.get("source_id", [""])[0].strip()
        if not source_id:
            self._set_cors(400)
            self.end_headers()
            self.wfile.write(b"Missing ?source_id=")
            return

        try:
            target_lang = qs.get("target_lang", ["en"])[0].strip() or "en"
            sources = [s for s in load_sources() if s.enabled]
            source = next((s for s in sources if s.id == source_id), None)
            if source is None:
                self._set_cors(404)
                self.end_headers()
                self.wfile.write(b"Unknown source_id")
                return

            body, _ = fetch_url(source.url)
            items = parse_feed(body)
            translator = TranslationChain()
            translated_items = translate_items(items, source.language, translator, target_lang=target_lang)
            payload = {
                "source": source.__dict__,
                "target_lang": target_lang,
                "item_count": len(translated_items),
                "items": translated_items,
            }
            self._set_cors(200, "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        except HTTPError as e:
            self._set_cors(e.code)
            self.end_headers()
            self.wfile.write(f"Upstream HTTP error: {e.code}".encode("utf-8"))
        except URLError as e:
            self._set_cors(502)
            self.end_headers()
            self.wfile.write(f"Upstream URL error: {e.reason}".encode("utf-8"))
        except Exception as e:
            self._set_cors(500)
            self.end_headers()
            self.wfile.write(f"Translated feed error: {e}".encode("utf-8"))

    def _handle_raw(self, query_string: str):
        qs = parse_qs(query_string)
        target = qs.get("url", [""])[0].strip()
        target = unquote(target)
        if not target:
            self._set_cors(400)
            self.end_headers()
            self.wfile.write(b"Missing ?url=")
            return
        u = urlparse(target)
        if u.scheme not in ALLOWED_SCHEMES:
            self._set_cors(400)
            self.end_headers()
            self.wfile.write(b"Only http/https URLs are allowed")
            return
        try:
            body, ctype = fetch_url(target)
            # RSS/Atom often comes as xml/text; normalize to XML-ish content type
            out_type = "application/xml; charset=utf-8"
            if "json" in ctype.lower():
                out_type = "application/json; charset=utf-8"
            self._set_cors(200, out_type)
            self.end_headers()
            self.wfile.write(body)
        except HTTPError as e:
            self._set_cors(e.code)
            self.end_headers()
            msg = f"Upstream HTTP error: {e.code}".encode("utf-8")
            self.wfile.write(msg)
        except URLError as e:
            self._set_cors(502)
            self.end_headers()
            msg = f"Upstream URL error: {e.reason}".encode("utf-8")
            self.wfile.write(msg)
        except Exception as e:
            self._set_cors(500)
            self.end_headers()
            msg = f"Proxy error: {e}".encode("utf-8")
            self.wfile.write(msg)
    def log_message(self, fmt, *args):
        sys.stdout.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), fmt % args))
def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    server = ThreadingHTTPServer((HOST, PORT), ProxyHandler)
    print(f"RSS proxy listening on http://{HOST}:{PORT}")
    print(f"Health check: http://{HOST}:{PORT}/health")
    print(f"Use in app:   http://{HOST}:{PORT}/raw?url=")
    print(f"Sources list: http://{HOST}:{PORT}/sources")
    print(f"Translated:   http://{HOST}:{PORT}/translated?source_id=<id>&target_lang=en")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping proxy...")
    finally:
        server.server_close()
if __name__ == "__main__":
    main()