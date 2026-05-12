"""
core/watermark.py
-----------------
Steganographic watermark for plain text using Unicode covert channels.

Encoding scheme
---------------
Payload  = tag_char (1 byte) + integrity_digest (hash_length bytes)
           → total (1 + hash_length) characters → (1 + hash_length) × 8 bits

Each bit is mapped:
  '0' → ZERO WIDTH SPACE        U+200B  (invisible, zero-width)
  '1' → NO-BREAK SPACE          U+00A0  (visually a normal space, zero-width in most renders)

The bit stream is bracketed by a sentinel sequence so the extractor
can locate it reliably:

  START_SENTINEL = U+200B U+200B U+200B U+00A0 U+00A0  (3× ZWS + 2× NBSP)
  END_SENTINEL   = U+00A0 U+00A0 U+00A0 U+200B U+200B  (3× NBSP + 2× ZWS)

The full hidden tag is appended to the end of the paragraph text.

Robustness note
---------------
Zero-width characters survive most web copy-paste flows and plain-text
transmission (email, SMS). They are stripped by some rich-text editors
(Word, Google Docs). This is a known trade-off for this class of approach.
SynthID's text variant uses logit-bias injection at generation time to
avoid this fragility — that requires access to the generator, which we
don't have here.

Balance strategy
----------------
  Stealth   — characters are invisible; sentinel is not a natural word boundary
  Robustness — sentinel makes partial-strip detection possible
  Integrity  — digest covers text + tag, so any edit breaks verification
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional

from core.integrity import compute_digest, verify_digest, document_reference
from core.classifier import classify, ClassifierResult
from config import settings

# ── Unicode covert channel ──────────────────────────────────────────────────

ZWS  = "\u200B"   # Zero Width Space  → bit 0
NBSP = "\u00A0"   # No-Break Space    → bit 1

START_SENTINEL = ZWS * 3 + NBSP * 2
END_SENTINEL   = NBSP * 3 + ZWS * 2

PATTERN = re.compile(
    r"\u200B{3}\u00A0{2}"   # start sentinel
    r"([\u200B\u00A0]+)"    # payload bits (captured)
    r"\u00A0{3}\u200B{2}"   # end sentinel
)


# ── Low-level encode / decode ───────────────────────────────────────────────

def _str_to_bits(s: str) -> str:
    return "".join(format(ord(c), "08b") for c in s)


def _bits_to_str(bits: str) -> str:
    # Pad to multiple of 8
    bits = bits.ljust((len(bits) + 7) // 8 * 8, "0")
    chars = []
    for i in range(0, len(bits), 8):
        byte = bits[i : i + 8]
        if len(byte) == 8:
            chars.append(chr(int(byte, 2)))
    return "".join(chars)


def _encode_payload(tag_char: str, digest: str) -> str:
    bits = _str_to_bits(tag_char + digest)
    encoded = "".join(ZWS if b == "0" else NBSP for b in bits)
    return START_SENTINEL + encoded + END_SENTINEL


def _decode_payload(raw_bits: str) -> tuple[str, str]:
    """Return (tag_char, digest) or raise ValueError."""
    expected_chars = 1 + settings.hash_length
    expected_bits  = expected_chars * 8

    bits = "".join("0" if c == ZWS else "1" for c in raw_bits)
    bits = bits.ljust(expected_bits, "0")[:expected_bits]

    decoded = _bits_to_str(bits)
    if len(decoded) < 1 + settings.hash_length:
        raise ValueError("Payload too short to decode")

    tag_char = decoded[0]
    digest   = decoded[1 : 1 + settings.hash_length]
    return tag_char, digest


# ── Public API ───────────────────────────────────────────────────────────────

@dataclass
class EmbedResult:
    tagged_text: str
    reference: str          # document-level MD5 ref (display only)
    label: str
    confidence: float
    phrase: str


@dataclass
class VerifyResult:
    found: bool             # watermark present
    label: str              # recovered label ("Human" | "AI" | "Uncertain" | "Unknown")
    tag_char: str           # raw tag character
    modified: bool          # True if content changed after embedding
    # Per-paragraph details
    paragraphs: list[dict]  # [{text, label, modified}]


def embed(text: str) -> EmbedResult:
    """
    Classify every paragraph and embed a watermark into each one.

    Empty lines are preserved but not watermarked (no classifier call).
    """
    lines = text.split("\n")
    tagged_lines: list[str] = []

    # Use whole-document classification as the top-level result
    doc_result: ClassifierResult = classify(text)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            tagged_lines.append(line)
            continue

        para_result: ClassifierResult = classify(stripped)
        digest  = compute_digest(stripped, para_result.tag_char)
        payload = _encode_payload(para_result.tag_char, digest)
        tagged_lines.append(stripped + payload)

    return EmbedResult(
        tagged_text="\n".join(tagged_lines),
        reference=document_reference(text),
        label=doc_result.label,
        confidence=doc_result.confidence,
        phrase=doc_result.phrase,
    )


def verify(tagged_text: str) -> VerifyResult:
    """
    Extract and validate all watermarks in tagged_text.

    Returns a VerifyResult with per-paragraph details and an overall
    `modified` flag that is True if ANY paragraph failed verification.
    """
    lines = tagged_text.split("\n")
    para_details: list[dict] = []
    any_modified = False
    any_found    = False

    overall_label    = "Unknown"
    overall_tag_char = "?"

    for i, line in enumerate(lines):
        match = PATTERN.search(line)
        if not match:
            # No watermark on this line — skip silently
            continue

        any_found = True
        raw_bits  = match.group(1)

        try:
            tag_char, stored_digest = _decode_payload(raw_bits)
        except ValueError:
            para_details.append({
                "paragraph": i,
                "label": "Unknown",
                "modified": True,
                "error": "Malformed payload",
            })
            any_modified = True
            continue

        # Recover original text by stripping the watermark
        clean_text = PATTERN.sub("", line).strip()

        label = {"H": "Human", "A": "AI", "U": "Uncertain"}.get(tag_char, "Unknown")
        modified = not verify_digest(clean_text, tag_char, stored_digest)
        any_modified = any_modified or modified

        para_details.append({
            "paragraph": i,
            "text_preview": clean_text[:60] + ("…" if len(clean_text) > 60 else ""),
            "label": label,
            "tag_char": tag_char,
            "modified": modified,
        })

        # Use first paragraph's label as overall label
        if overall_label == "Unknown":
            overall_label    = label
            overall_tag_char = tag_char

    return VerifyResult(
        found=any_found,
        label=overall_label,
        tag_char=overall_tag_char,
        modified=any_modified,
        paragraphs=para_details,
    )


def strip(tagged_text: str) -> str:
    """Return a clean copy of the text with all watermarks removed."""
    return PATTERN.sub("", tagged_text)
