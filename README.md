# AITAG — AI Authorship Tagger

A lightweight proof-of-concept for AI content detection and steganographic watermarking, inspired by Google SynthID.

## Architecture

```
aitag/
├── core/
│   ├── classifier.py      # DistilBERT inference wrapper
│   ├── watermark.py       # Steganographic embed/extract
│   └── integrity.py       # Cryptographic hash binding
├── api/
│   └── server.py          # FastAPI endpoints
├── cli.py                 # CLI entry point
├── config.py              # Centralised config
└── tests/
    └── test_roundtrip.py  # Smoke tests
```

## Setup

```bash
pip install -r requirements.txt
```

Set your model path in `.env` or as an environment variable:
```
MODEL_PATH=./model/distilbert_model
```

## Usage

### CLI
```bash
# Classify only
python cli.py input.txt

# Classify + embed watermark
python cli.py input.txt --tag

# Verify a previously tagged file
python cli.py tagged.txt --verify
```

### API
```bash
uvicorn api.server:app --reload --port 8000
```

Endpoints:
- `POST /classify` — confidence score only
- `POST /tag`      — classify + embed watermark
- `POST /verify`   — extract + validate watermark

## Hardware Requirements
- RAM: ~1.5 GB at inference
- VRAM: ~250 MB (CPU fallback automatic)
- No training required
