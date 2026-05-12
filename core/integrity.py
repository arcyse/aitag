"""
core/integrity.py
-----------------
Cryptographic binding between content and its authorship tag.

Design
------
  digest = SHA-256( text_bytes + tag_char_bytes )[:hash_length]

The digest is truncated hex (default 8 chars = 32-bit collision space).
This is a PoC — for production, replace with HMAC-SHA256 + a secret key
or an asymmetric signature scheme.
"""

from __future__ import annotations
import hashlib
from config import settings


def compute_digest(text: str, tag_char: str) -> str:
    """
    Compute a short integrity digest for (text, tag_char).

    Returns:
        Lowercase hex string of length settings.hash_length
    """
    payload = text.encode("utf-8") + tag_char.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[: settings.hash_length]


def verify_digest(text: str, tag_char: str, stored_digest: str) -> bool:
    """
    Return True if the stored digest matches a freshly computed one.
    False means the text has been modified after watermarking.
    """
    return compute_digest(text, tag_char) == stored_digest


def document_reference(text: str) -> str:
    """Short MD5 reference ID for the whole document (display only)."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
