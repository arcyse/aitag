"""
tests/test_roundtrip.py
-----------------------
Smoke tests for the full embed → verify pipeline.
These test the watermark/integrity logic WITHOUT loading the model,
so they run fast even on low-spec hardware.

Run:
    python -m pytest tests/ -v
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock

from core.integrity import compute_digest, verify_digest
from core.watermark import _encode_payload, _decode_payload, PATTERN, strip


# ── Integrity tests ────────────────────────────────────────────────────────

def test_digest_stable():
    d1 = compute_digest("hello world", "A")
    d2 = compute_digest("hello world", "A")
    assert d1 == d2

def test_digest_sensitive_to_text():
    assert compute_digest("hello", "A") != compute_digest("helo", "A")

def test_digest_sensitive_to_tag():
    assert compute_digest("hello", "A") != compute_digest("hello", "H")

def test_verify_passes():
    d = compute_digest("some text", "H")
    assert verify_digest("some text", "H", d) is True

def test_verify_fails_on_edit():
    d = compute_digest("original", "A")
    assert verify_digest("modified", "A", d) is False


# ── Watermark encode / decode tests ──────────────────────────────────────

@pytest.mark.parametrize("tag_char,digest", [
    ("A", "abcd1234"),
    ("H", "00000000"),
    ("U", "ffffffff"),
])
def test_roundtrip_payload(tag_char, digest):
    payload = _encode_payload(tag_char, digest)
    match = PATTERN.search(payload)
    assert match, "Sentinel pattern not found in encoded payload"
    recovered_tag, recovered_digest = _decode_payload(match.group(1))
    assert recovered_tag == tag_char
    assert recovered_digest == digest

def test_strip_removes_watermark():
    payload  = _encode_payload("A", "deadbeef")
    original = "Some paragraph text."
    tagged   = original + payload
    cleaned  = strip(tagged)
    assert cleaned == original
    assert PATTERN.search(cleaned) is None

def test_no_false_positive_on_plain_text():
    plain = "This is a completely normal sentence with no hidden data."
    result = PATTERN.search(plain)
    assert result is None


# ── Mock-based embed/verify integration test ──────────────────────────────

def _mock_classify(text):
    """Return a deterministic mock ClassifierResult."""
    from core.classifier import ClassifierResult
    return ClassifierResult(label="AI", confidence=0.92, phrase="Likely AI-generated")


def test_embed_verify_intact():
    with patch("core.watermark.classify", side_effect=_mock_classify):
        from core.watermark import embed, verify
        result = embed("This is a single paragraph test.")
        v = verify(result.tagged_text)
        assert v.found is True
        assert v.modified is False
        assert v.label == "AI"


def test_embed_verify_detects_modification():
    with patch("core.watermark.classify", side_effect=_mock_classify):
        from core.watermark import embed, verify
        result = embed("Original paragraph content here.")
        tampered = result.tagged_text.replace("Original", "Tampered")
        v = verify(tampered)
        assert v.found is True
        assert v.modified is True


def test_embed_multiline():
    with patch("core.watermark.classify", side_effect=_mock_classify):
        from core.watermark import embed, verify
        text = "First paragraph.\n\nSecond paragraph.\nThird paragraph."
        result = embed(text)
        v = verify(result.tagged_text)
        assert v.found is True
        assert len(v.paragraphs) >= 2
        assert v.modified is False
