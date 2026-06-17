"""Raster image watermarking for AI disclosure."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Literal

from PIL import Image, ImageDraw, ImageFont

WatermarkPosition = Literal["bottom_right", "bottom_left", "top_right", "top_left"]


@dataclass(frozen=True)
class WatermarkedImage:
    data: bytes
    content_type: str
    width: int
    height: int
    text: str
    position: WatermarkPosition


def apply_ai_watermark(
    data: bytes,
    content_type: str,
    *,
    text: str = "AI generated",
    position: WatermarkPosition = "bottom_right",
) -> WatermarkedImage:
    """Draw a small AI disclosure label onto a raster image."""
    if not content_type.startswith("image/"):
        raise ValueError(f"Expected image content type, got {content_type}")
    if not data:
        raise ValueError("Cannot watermark an empty image")

    with Image.open(BytesIO(data)) as source:
        image = source.convert("RGBA")
        width, height = image.size
        overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)

        font_size = max(11, min(24, round(min(width, height) * 0.035)))
        font = _load_font(font_size)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        pad_x = max(8, round(font_size * 0.7))
        pad_y = max(5, round(font_size * 0.42))
        margin = max(8, round(min(width, height) * 0.025))
        box_width = text_width + pad_x * 2
        box_height = text_height + pad_y * 2
        x, y = _position_box(width, height, box_width, box_height, margin, position)

        draw.rounded_rectangle(
            (x, y, x + box_width, y + box_height),
            radius=max(6, round(box_height * 0.35)),
            fill=(10, 10, 10, 172),
        )
        draw.text(
            (x + pad_x, y + pad_y - max(1, round(font_size * 0.08))),
            text,
            font=font,
            fill=(255, 255, 255, 235),
        )

        composited = Image.alpha_composite(image, overlay)
        output = BytesIO()
        output_format = _pil_format_for_content_type(content_type)
        if output_format == "JPEG":
            composited = composited.convert("RGB")
        composited.save(output, format=output_format, quality=94)
        return WatermarkedImage(
            data=output.getvalue(),
            content_type=_content_type_for_pil_format(output_format),
            width=width,
            height=height,
            text=text,
            position=position,
        )


def _load_font(font_size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("Arial.ttf", font_size)
    except OSError:
        return ImageFont.load_default(size=font_size)


def _position_box(
    image_width: int,
    image_height: int,
    box_width: int,
    box_height: int,
    margin: int,
    position: WatermarkPosition,
) -> tuple[int, int]:
    x_left = margin
    x_right = max(margin, image_width - box_width - margin)
    y_top = margin
    y_bottom = max(margin, image_height - box_height - margin)
    return {
        "bottom_right": (x_right, y_bottom),
        "bottom_left": (x_left, y_bottom),
        "top_right": (x_right, y_top),
        "top_left": (x_left, y_top),
    }[position]


def _pil_format_for_content_type(content_type: str) -> str:
    return {
        "image/jpeg": "JPEG",
        "image/jpg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP",
    }.get(content_type, "PNG")


def _content_type_for_pil_format(format_name: str) -> str:
    return {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
    }[format_name]
