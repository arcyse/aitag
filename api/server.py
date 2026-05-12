"""
api/server.py
-------------
FastAPI application exposing classify / tag / verify over HTTP.

Run:
    uvicorn api.server:app --reload --port 8000
"""

from __future__ import annotations
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.classifier import classify
from core.watermark import embed, verify, strip


# ── App setup ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="AITAG — AI Authorship Tagger",
    version="1.0.0",
    description="Lightweight AI content detection + steganographic watermarking API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response schemas ────────────────────────────────────────────

class TextRequest(BaseModel):
    text: str


class ClassifyResponse(BaseModel):
    label: str
    confidence: float
    confidence_pct: str
    phrase: str


class TagResponse(BaseModel):
    label: str
    confidence: float
    confidence_pct: str
    phrase: str
    reference: str
    tagged_text: str


class ParagraphDetail(BaseModel):
    paragraph: int
    text_preview: str
    label: str
    tag_char: str
    modified: bool


class VerifyResponse(BaseModel):
    found: bool
    label: str
    modified: bool
    paragraphs: list[dict]
    clean_text: str


# ── Endpoints ─────────────────────────────────────────────────────────────

@app.post("/classify", response_model=ClassifyResponse, summary="Classify text as Human or AI")
def classify_endpoint(req: TextRequest):
    """
    Returns an authorship confidence estimate.
    No watermark is embedded.
    """
    if not req.text.strip():
        raise HTTPException(status_code=422, detail="Text must not be empty.")
    result = classify(req.text)
    return ClassifyResponse(
        label=result.label,
        confidence=result.confidence,
        confidence_pct=f"{result.confidence * 100:.2f}%",
        phrase=result.phrase,
    )


@app.post("/tag", response_model=TagResponse, summary="Classify and embed steganographic watermark")
def tag_endpoint(req: TextRequest):
    """
    Classifies each paragraph and embeds an invisible watermark + integrity
    digest into the text. Returns the watermarked text and a reference ID.
    """
    if not req.text.strip():
        raise HTTPException(status_code=422, detail="Text must not be empty.")
    result = embed(req.text)
    return TagResponse(
        label=result.label,
        confidence=result.confidence,
        confidence_pct=f"{result.confidence * 100:.2f}%",
        phrase=result.phrase,
        reference=result.reference,
        tagged_text=result.tagged_text,
    )


@app.post("/verify", response_model=VerifyResponse, summary="Extract and validate embedded watermark")
def verify_endpoint(req: TextRequest):
    """
    Attempts to locate and decode the embedded watermark.
    Returns the original authorship label and whether the content has been
    modified since watermarking.
    """
    if not req.text.strip():
        raise HTTPException(status_code=422, detail="Text must not be empty.")
    result = verify(req.text)
    clean  = strip(req.text)
    return VerifyResponse(
        found=result.found,
        label=result.label,
        modified=result.modified,
        paragraphs=result.paragraphs,
        clean_text=clean,
    )


@app.get("/health")
def health():
    return {"status": "ok"}
