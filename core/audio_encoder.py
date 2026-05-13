"""
core/audio_encoder.py
---------------------
Embeds a cryptographic provenance watermark into a WAV/MP3 audio file
using STFT-based spectral embedding with robust magnitude quantization.

Usage:
    encoder = AudioProvenanceEncoder("Provint-TTS-001", "keys/issuer_private.pem")
    result  = encoder.encode("input.wav", "output_watermarked.wav")
"""

from __future__ import annotations
import hashlib
import os
import time
from pathlib import Path

import numpy as np
import librosa
import soundfile as sf
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.audio_payload import ProvenancePayload, PAYLOAD_SIZE, SIG_SIZE, TOTAL_SIZE


# ── Config ────────────────────────────────────────────────────────────────

SAMPLE_RATE    = 22050
FREQ_LOW_HZ    = 1000
FREQ_HIGH_HZ   = 4000
N_FFT          = 2048
HOP_LENGTH     = 512
REDUNDANCY     = 4
MEL_BINS       = 64
MEL_FRAMES     = 300

# Quantization step size for embedding.
# Bit 0 → even multiple of STEP, Bit 1 → odd multiple of STEP.
# Must be large enough to survive ISTFT reconstruction (0.05 works well).
STEP = 0.05


# ── Helpers ───────────────────────────────────────────────────────────────

def _load_private_key(path: str) -> Ed25519PrivateKey:
    with open(path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def _extract_features(signal: np.ndarray, sr: int) -> np.ndarray:
    mel = librosa.feature.melspectrogram(y=signal, sr=sr, n_mels=MEL_BINS)
    mel_db = librosa.power_to_db(mel)
    if mel_db.shape[1] < MEL_FRAMES:
        mel_db = np.pad(mel_db, ((0, 0), (0, MEL_FRAMES - mel_db.shape[1])))
    return mel_db[:, :MEL_FRAMES]


def _hz_to_bin(hz: float, sr: int, n_fft: int) -> int:
    return int(hz * n_fft / sr)


def _bytes_to_bits(data: bytes) -> list[int]:
    return [int(b) for byte in data for b in format(byte, "08b")]


def _bits_to_bytes(bits: list[int]) -> bytes:
    out = []
    for i in range(0, len(bits) - 7, 8):
        out.append(int("".join(str(b) for b in bits[i:i + 8]), 2))
    return bytes(out)


def _embed_bit(mag: float, bit: int) -> float:
    """Quantization index modulation — survives ISTFT float reconstruction."""
    q = round(mag / STEP)
    if (q % 2) != bit:
        q += 1
    return max(q, 1) * STEP  # never zero


def _extract_bit(mag: float) -> int:
    q = round(mag / STEP)
    return int(q % 2)


# ── Encoder ───────────────────────────────────────────────────────────────

class AudioProvenanceEncoder:
    def __init__(self, issuer_name: str, private_key_path: str):
        self.issuer_name = issuer_name
        self.private_key = _load_private_key(private_key_path)
        self.public_key  = self.private_key.public_key()

    def encode(self, input_path: str, output_path: str) -> dict:
        print(f"[encoder] Loading: {input_path}")
        signal, sr = librosa.load(input_path, sr=SAMPLE_RATE, mono=True)

        features     = _extract_features(signal, sr)
        feature_hash = hashlib.sha256(features.tobytes()).digest()

        payload = ProvenancePayload(
            feature_hash = feature_hash,
            issuer_id    = self.issuer_name.encode("utf-8"),
            timestamp    = int(time.time()),
            nonce        = os.urandom(8),
            version      = 1,
        )
        payload_bytes = payload.pack()
        signature     = self.private_key.sign(payload_bytes)
        embed_data    = payload_bytes + signature

        print(f"[encoder] Payload: {len(embed_data)} bytes ({len(embed_data) * 8} bits)")

        watermarked = self._embed_stft(signal, embed_data)

        out = Path(output_path).with_suffix(".wav")
        sf.write(str(out), watermarked, SAMPLE_RATE)
        print(f"[encoder] Saved: {out}")

        pub_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        metadata = {
            "watermark_version":  1,
            "issuer_name":        self.issuer_name,
            "issuer_public_key":  pub_bytes.hex(),
            "embedded_timestamp": payload.timestamp,
            "audio_duration_s":   round(len(signal) / SAMPLE_RATE, 2),
            "sample_rate":        SAMPLE_RATE,
        }
        return {"audio_path": str(out), "metadata": metadata}

    def _embed_stft(self, signal: np.ndarray, embed_data: bytes) -> np.ndarray:
        D     = librosa.stft(signal, n_fft=N_FFT, hop_length=HOP_LENGTH)
        mag   = np.abs(D).astype(np.float64)
        phase = np.angle(D)

        bin_lo   = _hz_to_bin(FREQ_LOW_HZ,  SAMPLE_RATE, N_FFT)
        bin_hi   = _hz_to_bin(FREQ_HIGH_HZ, SAMPLE_RATE, N_FFT)
        bits     = _bytes_to_bits(embed_data)
        n_bits   = len(bits)
        n_frames = mag.shape[1]

        copy_starts = [int(i * n_frames / REDUNDANCY) for i in range(REDUNDANCY)]

        for start_frame in copy_starts:
            bit_idx = 0
            for frame in range(start_frame, n_frames):
                if bit_idx >= n_bits:
                    break
                for bin_idx in range(bin_lo, bin_hi):
                    if bit_idx >= n_bits:
                        break
                    mag[bin_idx, frame] = _embed_bit(mag[bin_idx, frame], bits[bit_idx])
                    bit_idx += 1

        D_marked = mag * np.exp(1j * phase)
        return librosa.istft(D_marked, n_fft=N_FFT, hop_length=HOP_LENGTH)
