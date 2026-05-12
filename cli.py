"""
cli.py
------
Command-line interface for AITAG.

Usage
-----
  python cli.py input.txt                  # classify only
  python cli.py input.txt --tag            # classify + embed watermark
  python cli.py tagged.txt --verify        # extract + validate watermark
  python cli.py tagged.txt --tag --verify  # tag then immediately verify (smoke test)
"""

import argparse
import sys
from pathlib import Path

from core.classifier import classify
from core.watermark import embed, verify, strip


def _fmt_label(label: str) -> str:
    colors = {"AI": "\033[91m", "Human": "\033[92m", "Uncertain": "\033[93m"}
    reset = "\033[0m"
    return f"{colors.get(label, '')}{label}{reset}"


def main():
    parser = argparse.ArgumentParser(
        description="AITAG — AI Authorship Tagger",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input_file", help="Path to a .txt file")
    parser.add_argument("--tag",    action="store_true", help="Embed watermark")
    parser.add_argument("--verify", action="store_true", help="Verify watermark")
    parser.add_argument("--output", help="Save tagged text to this file")
    args = parser.parse_args()

    path = Path(args.input_file)
    if not path.exists():
        print(f"Error: file not found — {path}", file=sys.stderr)
        sys.exit(1)

    text = path.read_text(encoding="utf-8")

    # ── Classify ──────────────────────────────────────────────────────────
    result = classify(text)
    print("\n── Classification ────────────────────────────────")
    print(f"  Label      : {_fmt_label(result.label)}")
    print(f"  Confidence : {result.confidence * 100:.2f}%")
    print(f"  Summary    : {result.phrase}")

    # ── Tag ───────────────────────────────────────────────────────────────
    tagged_text = text
    if args.tag:
        embed_result = embed(text)
        tagged_text  = embed_result.tagged_text
        print("\n── Watermark Embedded ────────────────────────────")
        print(f"  Reference  : {embed_result.reference}")
        print(f"  Paragraphs : {tagged_text.count(chr(0x200B) * 3)} marked")

        out_path = Path(args.output) if args.output else path.with_suffix(".tagged.txt")
        out_path.write_text(tagged_text, encoding="utf-8")
        print(f"  Saved to   : {out_path}")

    # ── Verify ────────────────────────────────────────────────────────────
    if args.verify:
        verify_result = verify(tagged_text)
        print("\n── Verification ──────────────────────────────────")
        if not verify_result.found:
            print("  ⚠  No watermark found in this text.")
        else:
            status = "\033[91mMODIFIED\033[0m" if verify_result.modified else "\033[92mINTACT\033[0m"
            print(f"  Status     : {status}")
            print(f"  Label      : {_fmt_label(verify_result.label)}")
            print(f"\n  Paragraph breakdown:")
            for p in verify_result.paragraphs:
                mod_flag = "✗ MODIFIED" if p["modified"] else "✓ intact"
                print(f"    [{p['paragraph']}] {_fmt_label(p['label'])}  {mod_flag}")
                print(f"        \"{p['text_preview']}\"")

    print()


if __name__ == "__main__":
    main()
