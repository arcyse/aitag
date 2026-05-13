"""
core/audio_verifier.py
----------------------
Extracts and validates the provenance watermark embedded by AudioProvenanceEncoder.

Usage:
    verifier = AudioProvenanceVerifier(metadata)
    report   = verifier.verify("audio_watermarked.wav")
    print(report)
"""

from __future__ import annotations
import hashlib
import time
from datetime import datetime, timezone

import numpy as np
import librosa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

from core.audio_payload import ProvenancePayload, PAYLOAD_SIZE, SIG_SIZE, TOTAL_SIZE
from core.audio_encoder import (
    SAMPLE_RATE, FREQ_LOW_HZ, FREQ_HIGH_HZ,
    N_FFT, HOP_LENGTH, REDUNDANCY, MEL_BINS, MEL_FRAMES,
    _hz_to_bin, _bits_to_bytes, _extract_features,
)


# ── Thresholds ────────────────────────────────────────────────────────────

VERIFIED_THRESHOLD  = 95.0
PARTIAL_THRESHOLD   = 70.0


# ── Verifier ─────────────────────────────────────────────────────────────

class AudioProvenanceVerifier:
    def __init__(self, metadata: dict):
        self.metadata = metadata
        pub_hex = metadata.get("issuer_public_key", "")
        if pub_hex:
            self.public_key: Ed25519PublicKey = ed25519.Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(pub_hex)
            )
        else:
            self.public_key = None

    def verify(self, audio_path: str) -> dict:
        print(f"[verifier] Loading: {audio_path}")
        signal, sr = librosa.load(audio_path, sr=SAMPLE_RATE, mono=True)

        # ── Stage 1: Watermark extraction ─────────────────────────────
        raw = self._extract_stft(signal)
        if raw is None:
            return self._report("Verification Failed",
                                reason="Could not recover watermark from audio.")

        payload_bytes = raw[:PAYLOAD_SIZE]
        signature     = raw[PAYLOAD_SIZE:PAYLOAD_SIZE + SIG_SIZE]

        # ── Stage 2: Payload decode ────────────────────────────────────
        try:
            payload = ProvenancePayload.unpack(payload_bytes)
        except Exception as e:
            return self._report("Verification Failed",
                                reason=f"Payload decode error: {e}")

        # ── Stage 3: Signature validation ─────────────────────────────
        sig_valid = False
        if self.public_key:
            try:
                self.public_key.verify(signature, payload_bytes)
                sig_valid = True
            except InvalidSignature:
                sig_valid = False
        else:
            return self._report("Verification Failed",
                                reason="No issuer public key in metadata.")

        if not sig_valid:
            return self._report("Verification Failed",
                                reason="Signature invalid — payload may be forged or corrupted.")

        # ── Stage 4: Integrity check ───────────────────────────────────
        features     = _extract_features(signal, SAMPLE_RATE)
        current_hash = hashlib.sha256(features.tobytes()).digest()

        # Bit-level similarity between embedded and current hash
        matching = sum(
            bin(a ^ b).count("0")
            for a, b in zip(payload.feature_hash, current_hash)
        )
        match_pct = (matching / (len(payload.feature_hash) * 8)) * 100

        if match_pct >= VERIFIED_THRESHOLD:
            status = "Verified"
        elif match_pct >= PARTIAL_THRESHOLD:
            status = "Partially Modified"
        else:
            status = "Integrity Compromised"

        ts = datetime.fromtimestamp(payload.timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        return self._report(
            status,
            issuer       = payload.issuer_name or self.metadata.get("issuer_name", "Unknown"),
            timestamp    = ts,
            match_pct    = match_pct,
            sig_valid    = sig_valid,
            recovered    = True,
        )

    def _extract_stft(self, signal: np.ndarray) -> bytes | None:
        D      = librosa.stft(signal, n_fft=N_FFT, hop_length=HOP_LENGTH)
        mag    = np.abs(D)

        bin_lo   = _hz_to_bin(FREQ_LOW_HZ,  SAMPLE_RATE, N_FFT)
        bin_hi   = _hz_to_bin(FREQ_HIGH_HZ, SAMPLE_RATE, N_FFT)
        n_frames = mag.shape[1]
        n_bits   = TOTAL_SIZE * 8  # 1032 bits

        # Collect bits from each redundant copy
        all_copies: list[list[int]] = []
        copy_starts = [int(i * n_frames / REDUNDANCY) for i in range(REDUNDANCY)]

        for start_frame in copy_starts:
            bits    = []
            bit_idx = 0
            for frame in range(start_frame, n_frames):
                if bit_idx >= n_bits:
                    break
                for bin_idx in range(bin_lo, bin_hi):
                    if bit_idx >= n_bits:
                        break
                    bits.append(int(mag[bin_idx, frame]) & 1)
                    bit_idx += 1
            if len(bits) >= n_bits:
                all_copies.append(bits[:n_bits])

        if not all_copies:
            return None

        # Majority vote across copies
        voted = []
        for i in range(n_bits):
            ones = sum(c[i] for c in all_copies)
            voted.append(1 if ones > len(all_copies) / 2 else 0)

        recovered = _bits_to_bytes(voted)
        if len(recovered) < TOTAL_SIZE:
            return None
        return recovered

    def _report(self, status: str, **kw) -> dict:
        recovered = kw.get("recovered", False)
        sig_valid = kw.get("sig_valid", False)
        match_pct = kw.get("match_pct", 0.0)

        if status == "Verified":
            confidence = "High"
        elif status == "Partially Modified":
            confidence = "Medium"
        else:
            confidence = "Low"

        return {
            "provenance_status":    status,
            "generator_author":     kw.get("issuer", "Unknown"),
            "embedded_timestamp":   kw.get("timestamp", "N/A"),
            "integrity_status":     status,
            "watermark_recovery":   "Successful" if recovered else "Failed",
            "signature_validation": "Passed" if sig_valid else "Failed",
            "feature_hash_match":   f"{match_pct:.1f}%",
            "confidence":           confidence,
            "reason":               kw.get("reason", ""),
        }
