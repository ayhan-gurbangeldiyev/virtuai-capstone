"""LinkedIn içerik üretim route'ları v2.
POST /api/generate/linkedin - Post üretimi (persona entegrasyonlu)
POST /api/generate/linkedin/carousel - Carousel metin üretimi
POST /api/generate/linkedin/hooks - Hook alternatifleri üret
POST /api/generate/linkedin/analyze - Post analizi
POST /api/generate/linkedin/image-prompt - Görsel promptu üret
GET /api/meta/linkedin/formats - Formatlar
GET /api/meta/linkedin/personas - Persona'lar
"""
from fastapi import APIRouter, HTTPException, Depends
from middleware.auth import require_auth
from middleware.rate_limit import rate_limit
from pydantic import BaseModel
from typing import Optional, List
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["linkedin"])


# ==================== MODELS ====================

class LinkedInGenerateRequest(BaseModel):
    topic: str
    format: str = "standard"
    persona: str = "thought_leader"
    language: str = "auto"
    additional_context: Optional[str] = None
    trend_context: Optional[str] = None
    variants: int = 1
    hook: Optional[str] = None  # Hook Lab'dan seçilen hook


class LinkedInCarouselRequest(BaseModel):
    topic: str
    slide_count: int = 8
    persona: str = "thought_leader"
    language: str = "auto"
    additional_context: Optional[str] = None
    trend_context: Optional[str] = None


class LinkedInHooksRequest(BaseModel):
    topic: str
    persona: str = "thought_leader"
    format: str = "standard"
    count: int = 5
    language: str = "auto"


class LinkedInAnalyzeRequest(BaseModel):
    content: str
    language: str = "auto"


class LinkedInImageRequest(BaseModel):
    topic: str
    content: Optional[str] = None
    style: str = "professional"  # professional, creative, minimal, bold


class GeneratedContent(BaseModel):
    content: str
    variant_index: int = 0
    character_count: int = 0


class GenerationResponse(BaseModel):
    success: bool
    variants: List[GeneratedContent]
    error: Optional[str] = None
    metadata: Optional[dict] = None


# ==================== HELPERS ====================

def _build_persona_prompt(persona_id: str) -> str:
    """Persona bilgilerini prompt string'e çevir."""
    from prompts.linkedin import LINKEDIN_PERSONAS
    persona = LINKEDIN_PERSONAS.get(persona_id)
    if not persona:
        return ""

    voice_str = "\n".join(f"- {v}" for v in persona.get("voice", []))
    avoid_str = ", ".join(persona.get("avoid", []))

    return f"""
## SENİN KARAKTERİN: {persona['name']}
{persona['identity']}

### Ses Tonu:
{voice_str}

### Yazım Kuralların:
{persona['writing_rules']}

### KAÇIN:
{avoid_str}
"""


def _get_lang(language: str) -> str:
    if language == "tr":
        return "Türkçe yaz."
    elif language == "en":
        return "İngilizce yaz."
    return "Konunun diline göre otomatik yaz."


# ==================== ROUTES ====================

@router.post("/generate/linkedin", response_model=GenerationResponse)
async def generate_linkedin_post(request: LinkedInGenerateRequest, _=Depends(rate_limit), user=Depends(require_auth)):
    """LinkedIn post üret (persona entegrasyonlu)"""
    try:
        from server import generate_with_openai
        from prompts.linkedin import LINKEDIN_FORMAT_PROMPTS, LINKEDIN_SYSTEM_PROMPT

        format_prompt = LINKEDIN_FORMAT_PROMPTS.get(request.format, LINKEDIN_FORMAT_PROMPTS["standard"])
        persona_prompt = _build_persona_prompt(request.persona)
        lang = _get_lang(request.language)
        trend_ctx = f"\n\n## TREND BAĞLAMI\nBu içerik güncel bir trend hakkında:\n{request.trend_context}" if request.trend_context else ""
        hook_ctx = f"\n\n## HOOK (Bunu kullan veya uyarla)\n{request.hook}" if request.hook else ""

        system_prompt = (
            f"{LINKEDIN_SYSTEM_PROMPT}\n\n"
            f"{persona_prompt}\n\n"
            f"{format_prompt}\n\n"
            f"## DİL\n{lang}"
            f"{trend_ctx}"
            f"{hook_ctx}"
        )
        if request.additional_context:
            system_prompt += f"\n\n## EK BAĞLAM\n{request.additional_context}"

        user_prompt = f"Konu: {request.topic}\n\nLinkedIn {request.format} post üret."

        contents = await generate_with_openai(system_prompt, user_prompt, request.variants)
        variants = [
            GeneratedContent(content=c, variant_index=i, character_count=len(c))
            for i, c in enumerate(contents)
        ]
        return GenerationResponse(success=True, variants=variants)
    except Exception as e:
        logger.error(f"LinkedIn generation error: {e}")
        return GenerationResponse(success=False, variants=[], error="Bir hata oluştu. Lütfen tekrar deneyin.")


@router.post("/generate/linkedin/carousel", response_model=GenerationResponse)
async def generate_linkedin_carousel(request: LinkedInCarouselRequest, _=Depends(rate_limit), user=Depends(require_auth)):
    """LinkedIn carousel metin üret"""
    try:
        from server import generate_with_openai
        from prompts.linkedin import LINKEDIN_FORMAT_PROMPTS, LINKEDIN_SYSTEM_PROMPT

        format_prompt = LINKEDIN_FORMAT_PROMPTS["carousel_text"]
        persona_prompt = _build_persona_prompt(request.persona)
        lang = _get_lang(request.language)
        trend_ctx = f"\n\n## TREND BAĞLAMI\n{request.trend_context}" if request.trend_context else ""

        system_prompt = (
            f"{LINKEDIN_SYSTEM_PROMPT}\n\n"
            f"{persona_prompt}\n\n"
            f"{format_prompt}\n\n"
            f"Slide sayısı: {request.slide_count}\n\n"
            f"## DİL\n{lang}"
            f"{trend_ctx}"
        )
        if request.additional_context:
            system_prompt += f"\n\n## EK BAĞLAM\n{request.additional_context}"

        user_prompt = f"Konu: {request.topic}\n\nLinkedIn carousel metinlerini üret."

        contents = await generate_with_openai(system_prompt, user_prompt, 1)
        variants = [GeneratedContent(content=contents[0], variant_index=0, character_count=len(contents[0]))]
        return GenerationResponse(success=True, variants=variants)
    except Exception as e:
        logger.error(f"LinkedIn carousel error: {e}")
        return GenerationResponse(success=False, variants=[], error="Bir hata oluştu. Lütfen tekrar deneyin.")


@router.post("/generate/linkedin/hooks", response_model=GenerationResponse)
async def generate_linkedin_hooks(request: LinkedInHooksRequest, _=Depends(rate_limit), user=Depends(require_auth)):
    """Hook alternatifleri üret"""
    try:
        from server import generate_with_openai
        from prompts.linkedin import LINKEDIN_SYSTEM_PROMPT

        persona_prompt = _build_persona_prompt(request.persona)
        lang = _get_lang(request.language)

        system_prompt = f"""Sen LinkedIn hook uzmanısın. Verilen konu için {request.count} farklı hook (açılış) üreteceksin.

{persona_prompt}

## HOOK KURALLARI:
- Her hook LinkedIn'de "see more" tıklatmalı (ilk 2-3 satır)
- Her hook FARKLI bir yaklaşım kullanmalı:
  1. Kişisel deneyim ile açılış ("5 yıl önce...")
  2. Şok edici data/istatistik ("Şirketlerin %73'ü...")
  3. Contrarian/provokatif iddia ("Herkes X diyor ama...")
  4. Soru ile merak ("Ya X olmasaydı?")
  5. Sahne kurma/hikaye ("Toplantı odasındaydım. Telefon çaldı.")
- Her hook 2-3 satır, max 150 karakter
- Hook'tan sonra "..." ile bitir (devamını okutmak için)

## DİL
{lang}

## ÇIKTI FORMATI:
Her hook'u numaralı listele:
1. [hook metni]
2. [hook metni]
...

Sadece hook'ları yaz, açıklama ekleme."""

        user_prompt = f"Konu: {request.topic}\nFormat: {request.format}\n\n{request.count} farklı LinkedIn hook üret."

        contents = await generate_with_openai(system_prompt, user_prompt, 1)
        variants = [GeneratedContent(content=contents[0], variant_index=0, character_count=len(contents[0]))]
        return GenerationResponse(success=True, variants=variants)
    except Exception as e:
        logger.error(f"LinkedIn hooks error: {e}")
        return GenerationResponse(success=False, variants=[], error="Bir hata oluştu. Lütfen tekrar deneyin.")


@router.post("/generate/linkedin/analyze", response_model=GenerationResponse)
async def analyze_linkedin_post(request: LinkedInAnalyzeRequest, _=Depends(rate_limit), user=Depends(require_auth)):
    """Mevcut LinkedIn postunu analiz et"""
    try:
        from server import generate_with_openai

        lang = _get_lang(request.language)
        char_count = len(request.content)
        word_count = len(request.content.split())
        line_count = len([l for l in request.content.split("\n") if l.strip()])
        hashtag_count = request.content.count("#")

        system_prompt = f"""Sen LinkedIn içerik analisti sin. Verilen postu analiz edip detaylı feedback ver.

## ANALİZ KRİTERLERİ:

1. **Hook Gücü (1-10)**: İlk 2-3 satır "see more" tıklatır mı?
2. **Yapı Skoru (1-10)**: Paragraf uzunluğu, boş satırlar, akış
3. **Persona Tutarlılığı (1-10)**: Tutarlı bir ses var mı?
4. **Engagement Potansiyeli (1-10)**: Yorum/paylaşım alır mı?
5. **CTA Etkisi (1-10)**: Net bir aksiyon çağrısı var mı?

## ÇIKTI FORMATI (JSON):
```json
{{
  "overall_score": 0-100,
  "hook_score": 0-10,
  "structure_score": 0-10,
  "persona_score": 0-10,
  "engagement_score": 0-10,
  "cta_score": 0-10,
  "strengths": ["güçlü yön 1", "güçlü yön 2"],
  "weaknesses": ["zayıf yön 1"],
  "improvements": [
    {{
      "type": "critical|warning|suggestion",
      "issue": "Sorun",
      "fix": "Düzeltme önerisi"
    }}
  ],
  "suggested_hashtags": ["#hashtag1", "#hashtag2", "#hashtag3"],
  "hook_alternatives": ["Alternatif hook 1", "Alternatif hook 2"]
}}
```

Sadece JSON döndür. {lang}"""

        user_prompt = f"Bu LinkedIn postunu analiz et ({char_count} karakter, {word_count} kelime, {hashtag_count} hashtag):\n\n{request.content}"

        contents = await generate_with_openai(system_prompt, user_prompt, 1)

        # Parse JSON
        raw = contents[0].replace("```json", "").replace("```", "").strip()
        try:
            analysis = json.loads(raw)
        except json.JSONDecodeError:
            analysis = {"raw": raw}

        variants = [GeneratedContent(content=contents[0], variant_index=0, character_count=len(contents[0]))]
        return GenerationResponse(
            success=True, variants=variants,
            metadata={
                "analysis": analysis,
                "stats": {
                    "character_count": char_count,
                    "word_count": word_count,
                    "line_count": line_count,
                    "hashtag_count": hashtag_count
                }
            }
        )
    except Exception as e:
        logger.error(f"LinkedIn analyze error: {e}")
        return GenerationResponse(success=False, variants=[], error="Bir hata oluştu. Lütfen tekrar deneyin.")


@router.post("/generate/linkedin/image-prompt", response_model=GenerationResponse)
async def generate_linkedin_image(request: LinkedInImageRequest, _=Depends(rate_limit), user=Depends(require_auth)):
    """LinkedIn post görseli için prompt üret"""
    try:
        from server import generate_with_openai

        style_guides = {
            "professional": "clean, corporate, modern office environment, soft lighting, blue tones",
            "creative": "vibrant colors, abstract shapes, dynamic composition, bold design",
            "minimal": "minimalist, white space, single focal point, clean lines, muted colors",
            "bold": "high contrast, strong typography area, gradient backgrounds, impactful"
        }
        style = style_guides.get(request.style, style_guides["professional"])
        content_ctx = f"\nPost içeriği: {request.content[:500]}" if request.content else ""

        system_prompt = """Sen LinkedIn görsel prompt uzmanısın. Post konusuna uygun görsel promptu üret.

## KURALLAR:
- Prompt İngilizce
- LinkedIn 1200x627 banner boyutu (1.91:1 aspect ratio)
- Metin/yazı görsele KOYMA
- Profesyonel, corporate-friendly
- Stock fotoğraf hissi verme

## ÇIKTI (JSON):
```json
{
  "prompt": "Detaylı İngilizce prompt (50-100 kelime)",
  "negative_prompt": "Kaçınılacaklar",
  "style_preset": "professional|creative|minimal|bold",
  "aspect_ratio": "1.91:1"
}
```
Sadece JSON döndür."""

        user_prompt = f"LinkedIn post konusu: {request.topic}\nGörsel stili: {request.style} ({style}){content_ctx}\n\nGörsel promptu üret."

        contents = await generate_with_openai(system_prompt, user_prompt, 1)

        raw = contents[0].replace("```json", "").replace("```", "").strip()
        try:
            image_data = json.loads(raw)
        except json.JSONDecodeError:
            image_data = {"prompt": raw, "style_preset": request.style, "aspect_ratio": "1.91:1"}

        variants = [GeneratedContent(content=contents[0], variant_index=0, character_count=len(contents[0]))]
        return GenerationResponse(success=True, variants=variants, metadata={"image_prompt": image_data})
    except Exception as e:
        logger.error(f"LinkedIn image prompt error: {e}")
        return GenerationResponse(success=False, variants=[], error="Bir hata oluştu. Lütfen tekrar deneyin.")


# ==================== META ROUTES ====================

@router.get("/meta/linkedin/formats")
async def get_linkedin_formats():
    from prompts.linkedin import LINKEDIN_FORMATS
    return [{"id": k, **v} for k, v in LINKEDIN_FORMATS.items()]


@router.get("/meta/linkedin/personas")
async def get_linkedin_personas():
    from prompts.linkedin import LINKEDIN_PERSONAS
    return [
        {"id": k, "name": v["name"], "label": v["label"], "description": v["description"]}
        for k, v in LINKEDIN_PERSONAS.items()
    ]
