# Central Asia Research Tool

This project provides:

- A local RSS proxy with CORS support
- Multilingual source feed config (`kk`, `uz`, `ky`)
- Translation chaining:
  - Primary: LibreTranslate
  - Fallback: Ollama (`mistral` by default)

## Endpoints

- `GET /health` - health check
- `GET /raw?url=<encoded_feed_url>` - proxy raw XML/JSON feed response
- `GET /sources` - list configured feed sources
- `GET /translated?source_id=<id>&target_lang=en` - fetch and translate feed entries

## Free Local Stack Setup

### 1) Start LibreTranslate

Run your own local LibreTranslate service (for example via Docker) and make sure it is reachable at:

- `http://127.0.0.1:5000`

Set a different URL via `LIBRETRANSLATE_URL` if needed.

### 2) Start Ollama and pull Mistral

```bash
ollama pull mistral
ollama serve
```

Ollama default URL is:

- `http://127.0.0.1:11434`

## Configuration

Environment variables:

- `LIBRETRANSLATE_URL` (default: `http://127.0.0.1:5000`)
- `OLLAMA_URL` (default: `http://127.0.0.1:11434`)
- `OLLAMA_MODEL` (default: `mistral`)
- `TRANSLATION_TARGET_LANG` (default: `en`)
- `TRANSLATION_TIMEOUT_SECONDS` (default: `12`)
- `TRANSLATION_RETRIES` (default: `1`)
- `TRANSLATION_PROVIDER_BACKOFF_SECONDS` (default: `45`)

Source config file:

- `sources.json`

## Run

```bash
python rss_proxy.py
```

## Smoke tests

```bash
curl "http://127.0.0.1:8787/health"
curl "http://127.0.0.1:8787/sources"
curl "http://127.0.0.1:8787/translated?source_id=informburo_kz&target_lang=en"
```

## Tests

```bash
python -m unittest discover -s tests -v
```
