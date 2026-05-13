"""
tests/test_audio.py
-------------------
Smoke test for audio provenance encode → verify pipeline.

Usage:
    python tests/test_audio.py your_audio.mp3
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.audio_encoder import AudioProvenanceEncoder
from core.audio_verifier import AudioProvenanceVerifier

PRIVATE_KEY = "keys/issuer_private.pem"
ISSUER_NAME = "Provint-TTS-001"

def run(input_audio: str):
    print("\n── Encoding ──────────────────────────────────────")
    encoder = AudioProvenanceEncoder(ISSUER_NAME, PRIVATE_KEY)
    result  = encoder.encode(input_audio, "test_watermarked.wav")

    print(f"  Audio    : {result['audio_path']}")
    print(f"  Issuer   : {result['metadata']['issuer_name']}")
    print(f"  Duration : {result['metadata']['audio_duration_s']}s")

    print("\n── Verifying (clean) ─────────────────────────────")
    verifier = AudioProvenanceVerifier(result["metadata"])
    report   = verifier.verify(result["audio_path"])

    _print_report(report)

    print("\n── Full Report JSON ──────────────────────────────")
    print(json.dumps(report, indent=2))


def _print_report(r: dict):
    status_icon = {
        "Verified":              "✓",
        "Partially Modified":    "~",
        "Integrity Compromised": "✗",
        "Verification Failed":   "✗",
    }.get(r["provenance_status"], "?")

    print(f"  {status_icon} Provenance Status   : {r['provenance_status']}")
    print(f"    Generator/Author  : {r['generator_author']}")
    print(f"    Embedded At       : {r['embedded_timestamp']}")
    print(f"    Integrity         : {r['integrity_status']}")
    print(f"    Watermark Recovery: {r['watermark_recovery']}")
    print(f"    Signature         : {r['signature_validation']}")
    print(f"    Hash Match        : {r['feature_hash_match']}")
    print(f"    Confidence        : {r['confidence']}")
    if r.get("reason"):
        print(f"    Reason            : {r['reason']}")


if __name__ == "__main__":
    audio = sys.argv[1] if len(sys.argv) > 1 else "input.wav"
    run(audio)
