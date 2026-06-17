"""Layer 2: OCR text scan + forbidden pattern detection.

Uses easyocr (Türkçe + English) to extract any rendered text from the generated
image, then checks against a forbidden patterns list. Flags any of:
- Watermark text ("AI generated", "Stable Diffusion", model brand names)
- Brand logos rendered as text (visible logo text)
- Political/religious tokens

If any forbidden pattern present → FAIL.
Empty OCR result is PASS (most lifestyle images have no text).
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass

import easyocr
import numpy as np
from loguru import logger
from PIL import Image

LANGUAGES = ["tr", "en"]

# Patterns that signal compliance failure if found in OCR output.
FORBIDDEN_TEXT_PATTERNS = [
    r"\bai\s*generated\b",
    r"\bgenerated\s+by\s+ai\b",
    r"\bstable\s*diffusion\b",
    r"\bmidjourney\b",
    r"\bdall[\s-]?e\b",
    r"\bflux\b(?!\s*ai)",  # avoid "flux ai" company name only — we don't want raw "flux" text
    r"\bnano\s*banana\b",
    r"\bseedream\b",
    r"\bbytedance\b",
    r"\bopenai\b",
    r"\bwiro\b",
    # Brand logos often appear as text
    r"\bnike\b", r"\badidas\b", r"\bgucci\b", r"\bprada\b",
    r"\bcoca[\s-]?cola\b", r"\bpepsi\b",
    # Political/religious
    r"\btrump\b", r"\bbiden\b", r"\berdoğan\b",
]

# Compile once
_PATTERNS = [re.compile(p, re.IGNORECASE) for p in FORBIDDEN_TEXT_PATTERNS]
_reader = None


def _get_reader() -> easyocr.Reader:
    global _reader
    if _reader is None:
        logger.info(f"loading easyocr ({LANGUAGES})...")
        _reader = easyocr.Reader(LANGUAGES, gpu=False, verbose=False)
        logger.info("easyocr loaded")
    return _reader


@dataclass(frozen=True)
class OcrResult:
    text: str              # all detected text joined
    detection_count: int
    forbidden_matches: list[str]
    verdict: str           # 'PASS' | 'FAIL'


def check_ocr(generated_image_bytes: bytes) -> OcrResult:
    reader = _get_reader()
    img = Image.open(io.BytesIO(generated_image_bytes)).convert("RGB")
    arr = np.array(img)
    detections = reader.readtext(arr, detail=0)  # detail=0 → just text strings
    text = " | ".join(detections).strip()
    matches: list[str] = []
    for pat, raw in zip(_PATTERNS, FORBIDDEN_TEXT_PATTERNS):
        if pat.search(text):
            matches.append(raw)
    verdict = "FAIL" if matches else "PASS"
    return OcrResult(
        text=text,
        detection_count=len(detections),
        forbidden_matches=matches,
        verdict=verdict,
    )
