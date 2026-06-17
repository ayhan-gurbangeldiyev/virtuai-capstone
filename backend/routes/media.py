"""
Media routes - Nano Banana Pro image prompt generation
"""
from fastapi import APIRouter, HTTPException, Depends
from middleware.auth import require_auth
from middleware.rate_limit import rate_limit
from pydantic import BaseModel
from typing import Optional
import logging

router = APIRouter(prefix="/media", tags=["media"])
logger = logging.getLogger(__name__)


class ImagePromptRequest(BaseModel):
    content: str  # Tweet or post content
    platform: str = "twitter"  # twitter, linkedin, instagram, blog
    style: str = "realistic"  # realistic, illustration, 3d, abstract


class ImagePromptResponse(BaseModel):
    success: bool
    prompt: Optional[str] = None
    nano_banana_json: Optional[dict] = None
    error: Optional[str] = None


STYLE_GUIDES = {
    "realistic": "photorealistic, high detail, natural lighting, 8k",
    "illustration": "digital illustration, clean lines, vibrant colors, modern flat design",
    "3d": "3D render, cinema 4D style, soft lighting, glossy materials",
    "abstract": "abstract art, geometric shapes, bold colors, minimalist composition",
}

PLATFORM_SPECS = {
    "twitter": {"aspect": "16:9", "vibe": "attention-grabbing, bold, minimal text"},
    "linkedin": {"aspect": "1.91:1", "vibe": "professional, clean, corporate-friendly"},
    "instagram": {"aspect": "1:1", "vibe": "aesthetic, eye-catching, scroll-stopping"},
    "blog": {"aspect": "16:9", "vibe": "editorial, complementary to article, informative"},
}


@router.post("/generate-image-prompt", response_model=ImagePromptResponse)
async def generate_image_prompt(request: ImagePromptRequest, _=Depends(rate_limit), user=Depends(require_auth)):
    """Generate a Nano Banana Pro compatible image prompt from content."""
    from server import openai_client
    if not openai_client:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    style_guide = STYLE_GUIDES.get(request.style, STYLE_GUIDES["realistic"])
    platform = PLATFORM_SPECS.get(request.platform, PLATFORM_SPECS["twitter"])

    system_prompt = """Sen bir AI görsel prompt mühendisisin. Verilen içeriğe uygun, Nano Banana Pro (veya Midjourney/DALL-E) için detaylı görsel promptu üretiyorsun.

KURALLAR:
- Prompt İngilizce olmalı (görsel AI'lar İngilizce daha iyi anlıyor)
- İçeriğin ana mesajını görselleştir, literal çeviri yapma
- Metin/yazı KOYMA görsele (no text in image)
- Detaylı sahne tarifi ver: kompozisyon, ışık, renk paleti, atmosfer
- Prompt tek paragraf, 50-100 kelime arası

JSON formatında döndür:
{
  "prompt": "detailed english prompt here...",
  "negative_prompt": "things to avoid",
  "style_preset": "one of: photorealistic, digital-art, 3d-model, abstract",
  "aspect_ratio": "16:9 or 1:1 etc"
}

Sadece JSON döndür, başka bir şey yazma."""

    user_prompt = f"""İçerik: {request.content}

Platform: {request.platform} ({platform['vibe']})
En-boy oranı: {platform['aspect']}
Stil: {request.style} ({style_guide})

Bu içeriğe uygun görsel promptu üret."""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8,
            max_tokens=500
        )

        raw = response.choices[0].message.content.strip()

        # Parse JSON
        import json
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        nano_json = json.loads(cleaned)

        return ImagePromptResponse(
            success=True,
            prompt=nano_json.get("prompt", ""),
            nano_banana_json=nano_json
        )
    except json.JSONDecodeError:
        # Fallback: return raw as prompt
        return ImagePromptResponse(
            success=True,
            prompt=raw,
            nano_banana_json={"prompt": raw, "style_preset": request.style, "aspect_ratio": platform["aspect"]}
        )
    except Exception as e:
        logger.error(f"Image prompt generation error: {str(e)}")
        return ImagePromptResponse(success=False, error="Bir hata oluştu. Lütfen tekrar deneyin.")
