"""
core/audio_payload.py
---------------------
Provenance payload dataclass — packs/unpacks to bytes for embedding.

Layout (65 bytes total):
  [0:32]  feature_hash   — SHA-256 of audio features
  [32:48] issuer_id      — first 16 bytes of issuer name (UTF-8, zero-padded)
  [48:56] timestamp      — Unix timestamp (8 bytes, big-endian)
  [56:64] nonce          — 8 random bytes
  [64]    version        — 1 byte
"""

from __future__ import annotations
import struct
import os


PAYLOAD_SIZE = 65   # bytes
SIG_SIZE     = 64   # Ed25519 signature bytes
TOTAL_SIZE   = PAYLOAD_SIZE + SIG_SIZE  # 129 bytes → 1032 bits


class ProvenancePayload:
    def __init__(
        self,
        feature_hash: bytes,
        issuer_id: bytes,
        timestamp: int,
        nonce: bytes,
        version: int = 1,
    ):
        self.feature_hash = feature_hash[:32].ljust(32, b"\x00")
        self.issuer_id    = issuer_id[:16].ljust(16, b"\x00")
        self.timestamp    = timestamp
        self.nonce        = nonce[:8].ljust(8, b"\x00")
        self.version      = version

    def pack(self) -> bytes:
        return (
            self.feature_hash
            + self.issuer_id
            + struct.pack(">Q", self.timestamp)
            + self.nonce
            + struct.pack("B", self.version)
        )

    @classmethod
    def unpack(cls, data: bytes) -> "ProvenancePayload":
        if len(data) < PAYLOAD_SIZE:
            raise ValueError(f"Payload too short: {len(data)} < {PAYLOAD_SIZE}")
        return cls(
            feature_hash = data[0:32],
            issuer_id    = data[32:48],
            timestamp    = struct.unpack(">Q", data[48:56])[0],
            nonce        = data[56:64],
            version      = struct.unpack("B", data[64:65])[0],
        )

    @property
    def issuer_name(self) -> str:
        return self.issuer_id.rstrip(b"\x00").decode("utf-8", errors="replace")
