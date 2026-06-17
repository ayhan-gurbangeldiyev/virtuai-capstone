"""Autonomous content gate for Cansu video narration scripts.

Berkay 10 Haz 2026 — when the crew runs autonomously (cron), a bad
narration must be DETECTED and BLOCKED before it is rendered/posted, with
no human in the loop. We saw the writer leak artifacts the prompt bans
(e.g. "— Cansu ile —": persona self-reference + em-dash) on the robot-taxi
draft. The prompt alone is not a guarantee; this gate is the deterministic
backstop.

Scope — DETERMINISTIC, high-precision style/format checks only (no false
blocks on legitimate news):

  - self_reference   persona name ("Cansu") or presenter first-person voice
  - cta_in_body      subscribe/follow CTA anywhere OTHER than the appended outro
  - banned_char      em/en dash, ellipsis, "!", "?", markdown (* # ` _ >)
  - too_long         expected TTS duration over the hard ≤30s ceiling
  - empty            blank after strip

NOT here (handled by other layers, on purpose — a deterministic regex would
false-block real Turkish and trigger needless image-only fallbacks):
  - invented_channel / off-topic / source-muddle / fabricated stats
                               -> faithfulness_gate (LLM, Tier 0+1): an
       invented outlet or unsupported number is not in the source text.
  - duplicate trend            -> flow-level dedup query
The persona's own name IS blocked here (covers the "— Cansu ile —" leak).

Usage by the autonomous flow:
  res = lint_video_script(narration, outro=outro_text)
  if not res.ok:
      # 1 retry: regenerate the script once
      # if it still fails -> skip video, fall back to image-only post
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Completeness-first length policy (Berkay 10 Haz 2026): target ~30s, but a
# dense news may run up to ~40s — the viewer must LEARN the whole story. So the
# gate ceiling is 40s, not 30s. Effective VIDEO rate at the locked prosody
# (speed=1.1 + light 0.15/0.2 pauses) measured ≈ 17 chars/s (669c → 39.0s
# render). We use 17.0 here; pre_spend_guard's 665-char MAX is the harder gate,
# so this stays a slightly-looser soft signal (40s × 17 = 680 chars).
MAX_DURATION_S = 40.0
LINT_TTS_CHARS_PER_SECOND = 17.0

# --- high-precision patterns ------------------------------------------------

# Persona's own name — never appears in a clean third-person news narration.
_PERSONA_NAME = re.compile(r"\bcansu\b", re.IGNORECASE)

# First-person PRESENTER voice. Deliberately narrow to avoid false positives
# on generic Turkish: we do NOT match bare "biz"/"kanal"/"abone" which occur
# in real news ("Süveyş Kanalı", "Netflix abone sayısı", "biz insanlar").
# Only unambiguous first-person presenter tokens + possessive "kanalımız".
_PRESENTER_VOICE = re.compile(
    r"\b(ben|bana|benim|bize|bizim|bizler|"
    r"kanalımız|kanalıma|kanalımda)\b",
    re.IGNORECASE,
)

# NOTE: invented-channel detection is intentionally NOT done by regex here.
# Outlet-ish nouns ("Kanalı", "Gündemi") false-positive on real names
# ("Süveyş Kanalı", "yapay zeka gündemi"), and a deterministic false block
# means an unnecessary image-only fallback in autonomous mode. An invented
# outlet name is a SEMANTIC problem — it won't appear in the source text —
# so it is caught by the faithfulness gate. The persona's own name is still
# blocked above (_PERSONA_NAME), which covers the "— Cansu ile —" leak.

# Subscribe / follow CTA — allowed ONLY inside the appended outro line.
_CTA = re.compile(
    r"(abone ol|takip et|takipte kal|kaçırma|kaçırmamak|bizi takip|"
    r"bildirimleri aç|kanala abone|beğenmeyi unutma|yorumlarda)",
    re.IGNORECASE,
)

# Banned characters: long dashes, ellipsis, exclaim/question, markdown.
_BANNED_CHARS = {
    "—": "em_dash",
    "–": "en_dash",
    "―": "horizontal_bar",
    "…": "ellipsis",
    "!": "exclamation",
    "?": "question",
    "*": "markdown_star",
    "#": "markdown_hash",
    "`": "backtick",
    "_": "underscore",
    ">": "blockquote",
}
_TRIPLE_DOT = re.compile(r"\.\.\.")

# 2026-06-10 (Berkay) — ASCII'leşmiş Türkçe dedektörü. Flash, gövde
# metninde ara ara diakritiksiz Türkçe'ye kayıyor (ş→s, ç→c, ı→i...);
# giriş cümlesi şablondan doğru gelince video "ilk cümle düzgün, sonrası
# bozuk" okunuyordu (Fable 5 videosu vakası). Liste: DOĞRU yazımı
# diakritik içeren çok yaygın kelimelerin ASCII-bozuk halleri — İngilizce
# çakışması olmayanlar seçildi. 2+ FARKLI eşleşme = drift (tek eşleşme
# tesadüf/alıntı olabilir).
_ASCIIFIED_TR = re.compile(
    r"\b(icin|cunku|ucretsiz|buyuk|kucuk|gelistir\w*|ozellik\w*|dogru|"
    r"soyle\w*|simdi|dusun\w*|gorus\w*|gorsel\w*|aciklad\w*|kullanima|"
    r"yapiyor|calisiyor|gosteriyor|degisiyor|gunluk|bugun|dunya\w*|"
    r"sirket\w*|musteri\w*|turkce|yuzde|cikti|cikiyor|acti|acik\w*)\b",
    re.IGNORECASE,
)


class ScriptBlocked(Exception):
    """Raised by assert_script_clean when the autonomous gate blocks a script."""

    def __init__(self, violations: list["Violation"]):
        self.violations = violations
        codes = ", ".join(v.code for v in violations)
        super().__init__(f"script blocked: {codes}")


@dataclass
class Violation:
    code: str
    detail: str = ""


@dataclass
class LintResult:
    ok: bool
    violations: list[Violation] = field(default_factory=list)
    chars: int = 0
    expected_duration_s: float = 0.0

    @property
    def codes(self) -> list[str]:
        return [v.code for v in self.violations]


def _strip_outro(script: str, outro: str | None) -> str:
    """Remove the appended outro from the tail so body-only checks ignore it.

    The outro is deterministically appended by the writer; its CTA ("takipte
    kal") is legitimate. We only want to flag CTA / artifacts in the LLM body.
    """
    s = script.strip()
    if not outro:
        return s
    o = outro.strip()
    if s.endswith(o):
        return s[: -len(o)].strip()
    # tolerate trailing whitespace/punctuation differences: if the last
    # sentence equals the outro (whitespace-normalized), drop it.
    sents = re.split(r"(?<=[.!?])\s+", s)
    if len(sents) >= 2:
        last = re.sub(r"\s+", " ", sents[-1].strip())
        if last == re.sub(r"\s+", " ", o):
            return " ".join(sents[:-1]).strip()
    return s


def lint_video_script(
    script: str,
    *,
    outro: str | None = None,
    max_duration_s: float = MAX_DURATION_S,
) -> LintResult:
    """Pure function. Return LintResult.ok=False with violations if the
    narration must NOT be rendered/posted by the autonomous flow.
    """
    violations: list[Violation] = []

    if script is None or not script.strip():
        return LintResult(ok=False, violations=[Violation("empty", "blank script")])

    full = script.strip()
    n = len(full)
    body = _strip_outro(full, outro)

    # 1. persona self-reference (check whole script — name must never appear)
    m = _PERSONA_NAME.search(full)
    if m:
        violations.append(Violation("self_reference", f"persona name '{m.group()}'"))

    # 2. presenter first-person voice
    m = _PRESENTER_VOICE.search(full)
    if m:
        violations.append(Violation("self_reference", f"presenter voice '{m.group()}'"))

    # 3. CTA inside the body (outro excluded)
    m = _CTA.search(body)
    if m:
        violations.append(Violation("cta_in_body", f"'{m.group()}' outside outro"))

    # 4. banned characters
    seen_banned: set[str] = set()
    for ch, name in _BANNED_CHARS.items():
        if ch in full and name not in seen_banned:
            violations.append(Violation("banned_char", f"{name} '{ch}'"))
            seen_banned.add(name)
    if _TRIPLE_DOT.search(full) and "ellipsis" not in seen_banned:
        violations.append(Violation("banned_char", "ellipsis '...'"))

    # 5. duration ceiling
    exp = n / LINT_TTS_CHARS_PER_SECOND
    if exp > max_duration_s:
        violations.append(
            Violation("too_long", f"~{exp:.1f}s > {max_duration_s:.0f}s ({n} chars)")
        )

    # 6. ASCII'leşmiş Türkçe (TTS 's/c/i' okur — yayınlanamaz)
    _ascii_hits = {m.group(1).lower() for m in _ASCIIFIED_TR.finditer(full)}
    if len(_ascii_hits) >= 2:
        violations.append(
            Violation(
                "asciified_turkish",
                "diakritiksiz Türkçe: " + ", ".join(sorted(_ascii_hits)[:5]),
            )
        )

    return LintResult(
        ok=not violations, violations=violations, chars=n, expected_duration_s=exp
    )


def assert_script_clean(
    script: str, *, outro: str | None = None, draft_id: str = "?"
) -> LintResult:
    """Validate, log, raise ScriptBlocked if the gate blocks. Returns LintResult."""
    r = lint_video_script(script, outro=outro)
    if not r.ok:
        logger.error(
            "[script_lint] BLOCKED draft=%s codes=%s | %s",
            draft_id[:8], r.codes,
            " ; ".join(f"{v.code}:{v.detail}" for v in r.violations),
        )
        raise ScriptBlocked(r.violations)
    logger.info(
        "[script_lint] CLEAN draft=%s chars=%d exp=%.1fs", draft_id[:8], r.chars, r.expected_duration_s
    )
    return r
