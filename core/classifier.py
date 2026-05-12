"""
core/classifier.py
------------------
Thin inference wrapper around a fine-tuned sequence classifier.

Model: Hello-SimpleAI/chatgpt-detector-roberta
Labels:  0 → AI (ChatGPT)   1 → Human
Output:  ClassifierResult dataclass
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from functools import lru_cache

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from config import settings


@dataclass
class ClassifierResult:
    label: str          # "Human" | "AI" | "Uncertain"
    confidence: float   # 0.0 – 1.0
    phrase: str         # human-readable summary

    @property
    def tag_char(self) -> str:
        return {"Human": "H", "AI": "A", "Uncertain": "U"}[self.label]


def _phrase(label: str, confidence: float) -> str:
    brackets = {
        "AI":    [(0.95, "Highly likely AI-generated"),
                  (0.80, "Likely AI-generated"),
                  (0.00, "Possibly AI-generated")],
        "Human": [(0.95, "Highly likely human-written"),
                  (0.80, "Likely human-written"),
                  (0.00, "Possibly human-written")],
    }
    for threshold, text in brackets.get(label, []):
        if confidence >= threshold:
            return text
    return "Uncertain — low confidence"


def _resolve_device() -> torch.device:
    if settings.device == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(settings.device)


@lru_cache(maxsize=1)
def _load_model():
    """Load tokenizer + model once; cache for lifetime of process."""
    path = Path(settings.model_path)
    if not path.is_dir():
        raise FileNotFoundError(
            f"Model directory not found: {path.resolve()}\n"
            f"Set AITAG_MODEL_PATH in your .env file."
        )
    tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(str(path), local_files_only=True)
    device = _resolve_device()
    model.to(device)
    model.eval()
    return tokenizer, model, device


def classify(text: str) -> ClassifierResult:
    """
    Classify a piece of text.

    Args:
        text: raw input string (any length; will be truncated to max_token_length)

    Returns:
        ClassifierResult with label, confidence, and descriptive phrase
    """
    tokenizer, model, device = _load_model()

    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=settings.max_token_length,
    )
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        logits = model(**inputs).logits
        probs = logits.softmax(dim=1)[0]  # shape [2]

    idx = probs.argmax().item()
    confidence = probs.max().item()
    label_raw = ["Human", "AI"][idx]   # model id2label: 0 = Human, 1 = ChatGPT
    label = label_raw if confidence >= settings.confidence_threshold else "Uncertain"

    return ClassifierResult(
        label=label,
        confidence=float(confidence),
        phrase=_phrase(label, confidence),
    )
