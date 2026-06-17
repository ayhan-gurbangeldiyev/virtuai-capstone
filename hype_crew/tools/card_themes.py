"""Glow kart renk-kod temaları — içerik tipi → renk + pill + template (tek tanım).

2026-06-13 (Berkay kararı): akışa format çeşitliliği. Haber = Mor Glow (mevcut,
LOCKED). Yeni formatlar AYNI i2i tasarımında farklı renk + farklı pill etiketiyle
üretilip haberlerin arasına serpiştirilir. Renk = içerik tipi.

TEK DOĞRU TANIM burada: renk kelimeleri, pill etiketi, hangi template env'i
taşıdığı, başlık metni rengi ve (kontrast denetimi için) aurayı temsil eden koyu
hex. `framed_news_image.build_frame_i2i_prompt` artık bu temadan beslenir;
default=news → mor prompt'u BYTE-FOR-BYTE eskisiyle aynı kalır (regresyon testi).

KONTRAST GATE (Critic'in en büyük korkusu — okunmaz kart otonom yayını):
her tema, başlık metni rengiyle WCAG AA (4.5:1) kontrastını GEÇMELİ. Parlak
amber/sarı + beyaz metin geçmez → o temalar `text_color="dark"` kullanır.
`audit_themes()` tasarım anında hangi temanın geçtiğini/kaldığını raporlar.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

# WCAG AA gövde-metni eşiği. Glow zaten kontrast-zorlu zemin; altına düşen
# hiçbir tema canlıya çıkmamalı.
WCAG_AA_MIN = 4.5


@dataclass(frozen=True)
class CardTheme:
    key: str
    pill_label: str        # prompt'taki pill metni — "HABER" / "SÖZLÜK" / "SENCE?"
    aura_atmosphere: str   # "purple-aura" — prompt: "the provided {x} news poster"
    aura_words: str        # "violet-to-magenta" — prompt: "{x} radial AURA"
    glow_word: str         # "purple" — prompt: "lit by the {x} glow"
    text_color: str        # "white" | "dark" — başlık metni rengi
    pill_style: str        # "white-outline" | "dark-outline" — pill çerçevesi (zemine göre)
    hero_style: str        # "branded" (logo arketipleri) | "symbolic" (logosuz)
    template_env: str      # bu temanın frame URL'sini taşıyan env değişkeni
    aura_hex: str          # aurayı temsil eden zemin rengi (kontrast denetimi)
    # recolor=True → ayrı template YOK; mor canonical'ı input alıp prompt'ta
    # "moru bu renge ÇEVİR" denir (haberle aynı tek-geçiş Wiro yolu). Dedike
    # template env'i set edilirse o kullanılır; edilmezse mor'dan çevrilir.
    recolor: bool = False

    @property
    def text_hex(self) -> str:
        return "#FFFFFF" if self.text_color == "white" else "#111111"

    def text_contrast(self) -> float:
        """Başlık metni ile aura zemini arası WCAG kontrast oranı."""
        return wcag_contrast(self.aura_hex, self.text_hex)

    def passes_contrast(self) -> bool:
        return self.text_contrast() >= WCAG_AA_MIN


# Haber teması mor değerleri build_frame_i2i_prompt'un ESKİ sabit string'ini
# birebir üretmeli (regresyon testi bunu kilitler). text_color="white",
# glow_word="purple", aura_atmosphere="purple-aura", aura_words="violet-to-magenta".
_THEMES: dict[str, CardTheme] = {
    "news": CardTheme(
        key="news", pill_label="HABER",
        aura_atmosphere="purple-aura", aura_words="violet-to-magenta",
        glow_word="purple", text_color="white", pill_style="white-outline",
        hero_style="branded",
        template_env="CANSU_FRAME_TEMPLATE_URL", aura_hex="#3A0A63",
    ),
    # --- Faz 1+ (template asset üretilince CANSU_FRAME_TEMPLATE_URL_* set edilir;
    #     o zamana kadar tetiklenmez, edilirse news template'e düşer) ---
    # Berkay paleti (2026-06-13): SÖZLÜK = kırık beyaz/ivory. AÇIK zemin →
    # beyaz metin OKUNMAZ, bu yüzden text_color="dark" + pill_style="dark-outline".
    "dictionary": CardTheme(
        key="dictionary", pill_label="SÖZLÜK",
        aura_atmosphere="warm off-white cream-ivory", aura_words="soft warm-ivory",
        glow_word="ivory", text_color="dark", pill_style="dark-outline",
        hero_style="symbolic",
        template_env="CANSU_FRAME_TEMPLATE_URL_DICTIONARY", aura_hex="#F1ECDE",
        recolor=True,
    ),
    # SENCE? = DERİN teal (Berkay onaylı base 2210497). Koyu zemin → BEYAZ metin
    # (~10:1) + beyaz pill (template'e gömülü). Font: Google Sans.
    "question": CardTheme(
        key="question", pill_label="SENCE?",
        aura_atmosphere="deep-teal-aura", aura_words="deep turquoise-teal",
        glow_word="turquoise", text_color="white", pill_style="white-outline",
        hero_style="symbolic",
        template_env="CANSU_FRAME_TEMPLATE_URL_QUESTION", aura_hex="#0B3D3B",
        recolor=False,
    ),
}


def get_theme(key: Optional[str]) -> CardTheme:
    """Temayı döndür; bilinmeyen/None → news (mor). Asla KeyError atmaz."""
    return _THEMES.get((key or "news"), _THEMES["news"])


def resolve_frame_url(theme: CardTheme, fallback: str = "") -> str:
    """Temanın template URL'sini env'den çöz; yoksa fallback (news template)."""
    return (os.environ.get(theme.template_env) or fallback or "").strip()


# --- WCAG kontrast (deterministik, runtime'a bağlı değil) ---

def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _srgb_to_linear(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    r, g, b = _hex_to_rgb(hex_color)
    return (
        0.2126 * _srgb_to_linear(r)
        + 0.7152 * _srgb_to_linear(g)
        + 0.0722 * _srgb_to_linear(b)
    )


def wcag_contrast(hex_a: str, hex_b: str) -> float:
    """İki renk arası WCAG kontrast oranı (1.0–21.0)."""
    la, lb = relative_luminance(hex_a), relative_luminance(hex_b)
    hi, lo = max(la, lb), min(la, lb)
    return round((hi + 0.05) / (lo + 0.05), 2)


def audit_themes() -> list[dict]:
    """Her temanın kontrast durumunu raporla (tasarım anı gate)."""
    out = []
    for t in _THEMES.values():
        out.append({
            "theme": t.key,
            "pill": t.pill_label,
            "text": t.text_color,
            "contrast": t.text_contrast(),
            "passes_AA": t.passes_contrast(),
            "template_set": bool(resolve_frame_url(t)),
        })
    return out


if __name__ == "__main__":  # python -m tools.card_themes → kontrast tablosu
    print(f"WCAG AA min = {WCAG_AA_MIN}:1\n")
    for row in audit_themes():
        mark = "✓" if row["passes_AA"] else "✗ KALDI"
        print(
            f"  {mark}  {row['theme']:<11} pill={row['pill']:<8} "
            f"text={row['text']:<5} kontrast={row['contrast']:>5}:1 "
            f"template={'set' if row['template_set'] else 'YOK (news fallback)'}"
        )
