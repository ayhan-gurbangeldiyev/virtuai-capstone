"""SÖZLÜK/SENCE? metin kartı render — aura template + PIL kod-overlay (Wiro YOK).

13 Haz 2026 (Berkay): kuraklık-dolgusu görsel kartları. Önceden üretilmiş aura
template (SÖZLÜK=şeftali, SENCE?=derin teal; 'pill' gömülü) Supabase'de durur;
metin GERÇEK fontla PIL ile basılır. Wiro i2i YOK → ücretsiz, net, %100 tutarlı,
kusursuz Türkçe.

Fontlar (assets/fonts/, repoya gömülü):
- SENCE?  → GoogleSans-Bold.ttf (OFL, lisans-temiz; Berkay'ın seçtiği Google Sans)
- SÖZLÜK  → Baloo2.ttf (OFL, chunky rounded) + harfler arası renkli nokta = Friends
            GÖRÜNÜMÜ. Gerçek Friends fontu Türkçe glyph içermiyor (İ/ş/ğ/ç YOK,
            kanıtlandı) → bu fallback hem Friends-look hem TR-tam hem ticari-güvenli.

Tema metadata (renk/text_color/template_env) tek kaynak: [[card_themes]].
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

import httpx
from PIL import Image, ImageDraw, ImageFont

from .card_themes import CardTheme, get_theme, resolve_frame_url

_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_BALOO = str(_FONT_DIR / "Baloo2.ttf")
_GSANS = str(_FONT_DIR / "GoogleSans-Bold.ttf")

_DARK = (24, 24, 24)
_WHITE = (255, 255, 255)
_FRIENDS_DOTS = [(230, 57, 70), (42, 157, 244), (255, 200, 60)]  # kırmızı, mavi, sarı

_DOTTED_THEMES = {"dictionary"}          # Friends noktalı tema(lar)
_PLAIN_FONT = {"question": _GSANS, "news": _GSANS}

_TEMPLATE_CACHE: dict[str, bytes] = {}


def _fill(theme: CardTheme):
    return _WHITE if theme.text_color == "white" else _DARK


def _load_template(theme: CardTheme, override: Optional[str] = None) -> Image.Image:
    src = (override or resolve_frame_url(theme)).strip()
    if not src:
        raise RuntimeError(
            f"tema '{theme.key}' template URL'si yok — {theme.template_env} set değil"
        )
    if src.startswith("http"):
        if src not in _TEMPLATE_CACHE:
            r = httpx.get(src, timeout=30.0)
            r.raise_for_status()
            _TEMPLATE_CACHE[src] = r.content
        return Image.open(io.BytesIO(_TEMPLATE_CACHE[src])).convert("RGB")
    return Image.open(src).convert("RGB")


def _baloo(size: int, wght: int = 800) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(_BALOO, size)
    f.set_variation_by_axes([wght])
    return f


def _wrap(draw, text: str, font, max_w: float) -> list[str]:
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if not cur or draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _fit_plain(draw, text: str, font_path: str, max_w: float, max_h: float,
               max_lines: int = 3, lo: int = 40, hi: int = 480):
    """En büyük punto: ≤max_lines satır, her satır ≤max_w, blok ≤max_h (binary search)."""
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        f = ImageFont.truetype(font_path, mid)
        lines = _wrap(draw, text, f, max_w)
        asc, desc = f.getmetrics()
        block_h = (asc + desc) * 1.14 * len(lines)
        ok = (len(lines) <= max_lines and block_h <= max_h
              and all(draw.textlength(l, font=f) <= max_w for l in lines))
        if ok:
            best = (mid, lines)
            lo = mid + 1
        else:
            hi = mid - 1
    if best is None:
        f = ImageFont.truetype(font_path, lo)
        best = (lo, _wrap(draw, text, f, max_w))
    return best


def _draw_dotted_term(draw, term: str, img_w: int, cy: int, max_w: float, fill) -> tuple[int, float]:
    """SÖZLÜK terimi: harf harf + araya renkli nokta (Friends). Auto-fit + merkez."""
    def metrics(sz: int):
        f = _baloo(sz, 800)
        widths = [draw.textlength(c, font=f) for c in term]
        dot_gap = sz * 0.34
        total = sum(widths) + dot_gap * max(0, len(term) - 1)
        return f, widths, dot_gap, total

    size = 300
    _, _, _, t0 = metrics(size)
    size = max(60, int(size * max_w / t0)) if t0 else 200
    f, widths, dot_gap, total = metrics(size)
    asc, desc = f.getmetrics()
    term_h = asc + desc
    x = (img_w - total) / 2
    y = cy - term_h / 2
    dot_r = size * 0.055
    di = 0
    for i, c in enumerate(term):
        draw.text((x, y), c, font=f, fill=fill)
        x += widths[i]
        if i < len(term) - 1:
            if c != " " and term[i + 1] != " ":
                dcx = x + dot_gap / 2
                draw.ellipse([dcx - dot_r, cy - dot_r, dcx + dot_r, cy + dot_r],
                             fill=_FRIENDS_DOTS[di % 3])
                di += 1
            x += dot_gap
    return size, term_h


def render_text_card(theme_key: str, main_text: str, sub_text: Optional[str] = None,
                     template_override: Optional[str] = None) -> bytes:
    """Aura template'i alıp metni gerçek fontla bas → JPEG bytes (4:5).

    - dictionary (SÖZLÜK): main_text=terim (Friends noktalı, BÜYÜK harf), sub_text=açıklama.
    - question (SENCE?): main_text=soru (Google Sans, satırlara sarılır).
    Metin rengi temadan (beyaz/koyu). template_override test/PoC içindir.
    """
    theme = get_theme(theme_key)
    img = _load_template(theme, template_override)
    W, H = img.size
    draw = ImageDraw.Draw(img)
    fill = _fill(theme)

    if theme.key in _DOTTED_THEMES:
        cy = int(H * 0.46)
        size, term_h = _draw_dotted_term(draw, main_text.upper(), W, cy, int(W * 0.82), fill)
        if sub_text:
            gf = _baloo(max(28, int(size * 0.30)), 600)
            gy = cy + term_h / 2 + size * 0.14
            for line in _wrap(draw, sub_text, gf, int(W * 0.80)):   # uzunsa sar, taşma yok
                gw = draw.textlength(line, font=gf)
                draw.text(((W - gw) / 2, gy), line, font=gf, fill=fill)
                gy += gf.getmetrics()[0] + gf.getmetrics()[1] + size * 0.04
    else:
        font_path = _PLAIN_FONT.get(theme.key, _GSANS)
        size, lines = _fit_plain(draw, main_text, font_path, int(W * 0.84), int(H * 0.34), max_lines=3)
        f = ImageFont.truetype(font_path, size)
        gap = int(size * 1.14)
        cy = int(H * 0.46)
        start = cy - gap * (len(lines) - 1) / 2
        for i, l in enumerate(lines):
            draw.text((W / 2, start + i * gap), l, font=f, fill=fill, anchor="mm")

    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    return buf.getvalue()


async def render_and_store_text_card(
    *, theme_key: str, main_text: str, sub_text: Optional[str] = None,
    key_prefix: str = "cards", template_override: Optional[str] = None,
) -> dict:
    """Kartı render et + Supabase persona-generated bucket'a yükle → public URL döndür."""
    import hashlib

    from config import settings
    from .supabase_storage import SupabaseStorage

    data = render_text_card(theme_key, main_text, sub_text, template_override)
    digest = hashlib.sha256(data).hexdigest()[:16]
    key = f"{key_prefix}/{theme_key}/{digest}.jpg"
    up = await SupabaseStorage().upload_bytes(
        bucket=settings.supabase_generated_bucket,
        key=key, data=data, content_type="image/jpeg", upsert=True,
    )
    return {"image_url": up.public_url, "storage_key": up.storage_key,
            "size_bytes": up.size_bytes, "theme": theme_key}
