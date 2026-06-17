"""TikTok içerik üretim route'ları.
POST /api/generate/tiktok/script - TikTok script üretimi
POST /api/generate/tiktok/caption - Caption + hashtag üretimi
GET /api/meta/tiktok/formats - TikTok formatları
"""
from fastapi import APIRouter, Depends
from middleware.auth import require_auth
from middleware.rate_limit import rate_limit
from pydantic import BaseModel
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["tiktok"])


class TikTokScriptRequest(BaseModel):
    topic: str
    duration: int = 30  # 15, 30, 60
    language: str = "auto"
    additional_context: Optional[str] = None


class TikTokCaptionRequest(BaseModel):
    topic: str
    video_description: Optional[str] = None
    language: str = "auto"


class GeneratedContent(BaseModel):
    content: str
    variant_index: int = 0
    character_count: int = 0


class GenerationResponse(BaseModel):
    success: bool
    variants: List[GeneratedContent]
    error: Optional[str] = None


def _lang(lang: str) -> str:
    if lang == "tr": return "Türkçe yaz."
    if lang == "en": return "İngilizce yaz."
    return "Konunun diline göre otomatik yaz."


@router.post("/generate/tiktok/script", response_model=GenerationResponse)
async def generate_tiktok_script(request: TikTokScriptRequest, _=Depends(rate_limit), user=Depends(require_auth)):
    """TikTok video scripti üret"""
    try:
        from server import generate_with_openai
        from prompts.tiktok import TIKTOK_FORMAT_PROMPTS, TIKTOK_SYSTEM_PROMPT
        from prompts.quality import BANNED_PATTERNS

        duration_key = f"script_{request.duration}"
        format_prompt = TIKTOK_FORMAT_PROMPTS.get(duration_key, TIKTOK_FORMAT_PROMPTS["script_30"])

        system_prompt = f"{TIKTOK_SYSTEM_PROMPT}\n\n{BANNED_PATTERNS}\n\n{format_prompt}\n\n## DİL\n{_lang(request.language)}\n\n{'## EK BAĞLAM' + chr(10) + request.additional_context if request.additional_context else ''}\n\n## KONU\n{request.topic}"

        contents = await generate_with_openai(system_prompt, "TikTok scriptini üret.", 1)
        variants = [GeneratedContent(content=contents[0], variant_index=0, character_count=len(contents[0]))]
        return GenerationResponse(success=True, variants=variants)
    except Exception as e:
        logger.error(f"TikTok script error: {e}")
        return GenerationResponse(success=False, variants=[], error="Bir hata oluştu. Lütfen tekrar deneyin.")


@router.post("/generate/tiktok/caption", response_model=GenerationResponse)
async def generate_tiktok_caption(request: TikTokCaptionRequest, _=Depends(rate_limit), user=Depends(require_auth)):
    """TikTok caption + hashtag üret"""
    try:
        from server import generate_with_openai
        from prompts.tiktok import TIKTOK_FORMAT_PROMPTS, TIKTOK_SYSTEM_PROMPT

        format_prompt = TIKTOK_FORMAT_PROMPTS["caption"]
        video_ctx = f"\nVideo açıklaması: {request.video_description}" if request.video_description else ""

        system_prompt = f"{TIKTOK_SYSTEM_PROMPT}\n\n{format_prompt}{video_ctx}\n\n## DİL\n{_lang(request.language)}\n\n## KONU\n{request.topic}"

        contents = await generate_with_openai(system_prompt, "Caption ve hashtag'leri üret.", 1)
        variants = [GeneratedContent(content=contents[0], variant_index=0, character_count=len(contents[0]))]
        return GenerationResponse(success=True, variants=variants)
    except Exception as e:
        logger.error(f"TikTok caption error: {e}")
        return GenerationResponse(success=False, variants=[], error="Bir hata oluştu. Lütfen tekrar deneyin.")


@router.get("/meta/tiktok/formats")
async def get_tiktok_formats():
    """TikTok formatlarını döndür"""
    from prompts.tiktok import TIKTOK_FORMATS
    return [{"id": k, **v} for k, v in TIKTOK_FORMATS.items()]
