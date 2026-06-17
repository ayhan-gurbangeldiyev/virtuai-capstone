"""TTS text normalization for Turkish narration — defense-in-depth.

Berkay 10 Haz 2026 — the complete-news writer already spells numbers in
Turkish words ("iki bin yirmi altı"), but autonomous runs cannot rely on the
LLM being perfect. This layer is the deterministic safety net applied right
before MiniMax synthesis: it cleans markup and converts any LEAKED digits /
symbols to spoken Turkish so the voice never reads a raw "27", "%87" or "$65".

Order matters and version tokens are protected:
  - GPT-4, GPT-5.5, iOS27, o3 etc. are version/model names whose digits are
    handled by pronunciation_resolver (the dict). We MUST NOT convert the
    digit there ("GPT-dört"), so digits adjacent to a letter are left alone.
  - Only FREE-STANDING numbers (preceded/followed by space or punctuation,
    not a letter) are converted.

Idempotent enough for repeated calls; safe on already-clean text.
"""

from __future__ import annotations

import re
import unicodedata

from num2words import num2words


def _tr_number(n: int) -> str:
    # num2words tr is space-less ("yirmiyedi"); MiniMax reads it fine, but we
    # keep it as-is (a naive space-inserter would mangle "ikiyüz" → "iki yüz"
    # which is actually fine, but compound teens like "onbir" must stay glued).
    return num2words(n, lang="tr")


def _convert_int(token: str) -> str:
    try:
        return _tr_number(int(token))
    except (ValueError, OverflowError):
        return token


# free-standing integer: not touching a letter, digit, dot, comma OR hyphen on
# the left (the hyphen guard protects version/model names — GPT-4, Claude-3 —
# whose digit must stay for the pronunciation dict), and not glued to a letter
# or digit on the right (protects iOS27, o3).
_FREE_INT = re.compile(r"(?<![A-Za-zÇĞİÖŞÜçğıöşü0-9.,\-])\d{1,12}(?![A-Za-zÇĞİÖŞÜçğıöşü0-9])")
# decimal like 1,5 or 3.2 (Turkish reads comma as "virgül"). Hyphen guard keeps
# GPT-5.5 intact.
_DECIMAL = re.compile(r"(?<![A-Za-z0-9.\-])(\d+)[.,](\d+)(?![A-Za-z0-9])")
# percent: "%87" or "87%"
_PCT_PRE = re.compile(r"%\s?(\d+)")
_PCT_POST = re.compile(r"(\d+)\s?%")
# money: "$65 milyar" / "$65" → "altmışbeş dolar"
_MONEY = re.compile(r"\$\s?(\d+)")


def normalize_for_tts(text: str) -> str:
    """Clean markup + convert leaked numbers/symbols to spoken Turkish."""
    if not text:
        return text

    t = unicodedata.normalize("NFC", text)
    # Cyrillic look-alikes that sneak in from copy-paste sources → Latin
    for a, b in (("е", "e"), ("а", "a"), ("о", "o"), ("с", "s"), ("р", "p"), ("х", "x")):
        t = t.replace(a, b)
    # long dashes → space (banned by gate, but strip here too for safety)
    t = t.replace("—", " ").replace("–", " ").replace("―", " ")
    # markdown / emphasis / structural chars
    t = re.sub(r"[#*_`>]", "", t)
    # ellipsis / multidot / terminal !? → plain period
    t = t.replace("…", ".")
    t = re.sub(r"\.{2,}", ".", t)
    t = t.replace("!", ".").replace("?", ".")

    # numbers & symbols (decimal BEFORE free-int so "3,2" isn't split)
    t = _DECIMAL.sub(lambda m: f"{_convert_int(m.group(1))} virgül {_convert_int(m.group(2))}", t)
    t = _PCT_PRE.sub(lambda m: f"yüzde {_convert_int(m.group(1))}", t)
    t = _PCT_POST.sub(lambda m: f"yüzde {_convert_int(m.group(1))}", t)
    t = _MONEY.sub(lambda m: f"{_convert_int(m.group(1))} dolar", t)
    t = _FREE_INT.sub(lambda m: _convert_int(m.group(0)), t)

    # whitespace + space-before-punct cleanup
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+([.,])", r"\1", t)
    return t
