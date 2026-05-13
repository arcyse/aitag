"""
debug_audio.py
--------------
Isolates exactly where the encode→verify pipeline breaks.
Run: python debug_audio.py test.mp3
"""
import sys
import hashlib
import os
import time
import numpy as np
import librosa
import soundfile as sf
from pathlib import Path

sys.path.insert(0, ".")

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

from core.audio_payload import ProvenancePayload, PAYLOAD_SIZE, SIG_SIZE, TOTAL_SIZE
from core.audio_encoder import (
    SAMPLE_RATE, N_FFT, HOP_LENGTH, REDUNDANCY,
    FREQ_LOW_HZ, FREQ_HIGH_HZ,
    _hz_to_bin, _bytes_to_bits, _bits_to_bytes, _extract_features
)

PRIVATE_KEY_PATH = "keys/issuer_private.pem"
audio_path = sys.argv[1] if len(sys.argv) > 1 else "test.mp3"

# ── Load keys ────────────────────────────────────────────────────────────
with open(PRIVATE_KEY_PATH, "rb") as f:
    private_key = serialization.load_pem_private_key(f.read(), password=None)
public_key = private_key.public_key()

pub_raw = public_key.public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw
)
print(f"[keys] Public key (hex): {pub_raw.hex()}")
print(f"[keys] Public key len : {len(pub_raw)} bytes")

# ── Build payload ────────────────────────────────────────────────────────
signal, sr = librosa.load(audio_path, sr=SAMPLE_RATE, mono=True)
features     = _extract_features(signal, sr)
feature_hash = hashlib.sha256(features.tobytes()).digest()

payload = ProvenancePayload(
    feature_hash=feature_hash,
    issuer_id=b"Provint-TTS-001",
    timestamp=int(time.time()),
    nonce=os.urandom(8),
    version=1,
)
payload_bytes = payload.pack()
print(f"\n[payload] Packed size : {len(payload_bytes)} bytes")
print(f"[payload] feature_hash: {payload.feature_hash.hex()}")

# ── Sign ─────────────────────────────────────────────────────────────────
signature = private_key.sign(payload_bytes)
print(f"\n[sign] Signature len  : {len(signature)} bytes")
print(f"[sign] Signature (hex): {signature.hex()[:32]}...")

embed_data = payload_bytes + signature
print(f"\n[embed] Total embed   : {len(embed_data)} bytes ({len(embed_data)*8} bits)")

# ── Verify signature BEFORE embedding (sanity check) ────────────────────
try:
    public_key.verify(signature, payload_bytes)
    print("\n[sanity] ✓ Signature valid BEFORE embedding")
except InvalidSignature:
    print("\n[sanity] ✗ Signature ALREADY INVALID before embedding — key problem!")
    sys.exit(1)

# ── Embed ────────────────────────────────────────────────────────────────
D     = librosa.stft(signal, n_fft=N_FFT, hop_length=HOP_LENGTH)
mag   = np.abs(D).astype(np.float64)
phase = np.angle(D)

bin_lo = _hz_to_bin(FREQ_LOW_HZ,  SAMPLE_RATE, N_FFT)
bin_hi = _hz_to_bin(FREQ_HIGH_HZ, SAMPLE_RATE, N_FFT)
bits   = _bytes_to_bits(embed_data)
n_bits = len(bits)
n_frames = mag.shape[1]

copy_starts = [int(i * n_frames / REDUNDANCY) for i in range(REDUNDANCY)]
for start_frame in copy_starts:
    bit_idx = 0
    for frame in range(start_frame, n_frames):
        if bit_idx >= n_bits: break
        for bin_idx in range(bin_lo, bin_hi):
            if bit_idx >= n_bits: break
            v = mag[bin_idx, frame]
            mag[bin_idx, frame] = float((int(v) & ~1) | bits[bit_idx])
            bit_idx += 1

D_marked    = mag * np.exp(1j * phase)
watermarked = librosa.istft(D_marked, n_fft=N_FFT, hop_length=HOP_LENGTH)
sf.write("debug_watermarked.wav", watermarked, SAMPLE_RATE)
print("\n[embed] Saved: debug_watermarked.wav")

# ── Extract ──────────────────────────────────────────────────────────────
D2   = librosa.stft(watermarked, n_fft=N_FFT, hop_length=HOP_LENGTH)
mag2 = np.abs(D2)

all_copies = []
for start_frame in copy_starts:
    extracted_bits = []
    bit_idx = 0
    for frame in range(start_frame, mag2.shape[1]):
        if bit_idx >= n_bits: break
        for bin_idx in range(bin_lo, bin_hi):
            if bit_idx >= n_bits: break
            extracted_bits.append(int(mag2[bin_idx, frame]) & 1)
            bit_idx += 1
    if len(extracted_bits) >= n_bits:
        all_copies.append(extracted_bits[:n_bits])

print(f"\n[extract] Copies recovered: {len(all_copies)}/{REDUNDANCY}")

if not all_copies:
    print("[extract] ✗ No copies recovered!")
    sys.exit(1)

voted = []
for i in range(n_bits):
    ones = sum(c[i] for c in all_copies)
    voted.append(1 if ones > len(all_copies) / 2 else 0)

recovered = _bits_to_bytes(voted)
print(f"[extract] Recovered bytes : {len(recovered)}")

# Compare original vs recovered
match = sum(a == b for a, b in zip(embed_data, recovered[:len(embed_data)]))
print(f"[extract] Byte match      : {match}/{len(embed_data)} ({match/len(embed_data)*100:.1f}%)")

# ── Verify signature AFTER extraction ────────────────────────────────────
rec_payload_bytes = recovered[:PAYLOAD_SIZE]
rec_signature     = recovered[PAYLOAD_SIZE:PAYLOAD_SIZE + SIG_SIZE]

print(f"\n[verify] Original sig  : {signature.hex()[:32]}...")
print(f"[verify] Recovered sig : {rec_signature.hex()[:32]}...")
print(f"[verify] Sig match     : {signature == rec_signature}")

try:
    public_key.verify(rec_signature, rec_payload_bytes)
    print("[verify] ✓ Signature VALID after extraction")
except InvalidSignature:
    print("[verify] ✗ Signature INVALID after extraction")
    diff_bits = sum(bin(a ^ b).count('1') for a, b in zip(signature, rec_signature))
    print(f"[verify] Bit differences in signature: {diff_bits}/512")
