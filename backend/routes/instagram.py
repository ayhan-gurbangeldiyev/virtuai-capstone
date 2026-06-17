"""Instagram içerik üretim route'ları.
POST /api/generate/instagram/caption - Caption üretimi
POST /api/generate/instagram/reel-script - Reel script üretimi
POST /api/generate/instagram/hashtags - Hashtag üretimi
POST /api/generate/instagram/story-ideas - Story fikir üretimi
GET /api/meta/instagram/formats - Mevcut formatlar
"""
from fastapi import APIRouter, HTTPException, Depends
from middleware.auth import require_auth
from middleware.rate_limit import rate_limit
from pydantic import BaseModel
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["instagram"])


class InstagramCaptionRequest(BaseModel):
    topic: str
    format: str = "standard"  # standard, story_caption, educational, promotional
    language: str = "auto"
    additional_context: Optional[str] = None
    variants: int = 1


class InstagramReelRequest(BaseModel):
    topic: str
    duration: int = 30  # 15, 30, 60
    language: str = "auto"
    additional_context: Optional[str] = None


class InstagramHashtagRequest(BaseModel):
    topic: str
    niche: Optional[str] = None
    language: str = "auto"


class InstagramStoryRequest(BaseModel):
    topic: str
    count: int = 5
    language: str = "auto"
    additional_context: Optional[str] = None


class GeneratedContent(BaseModel):
    content: str
    variant_index: int = 0
    character_count: int = 0


class GenerationResponse(BaseModel):
    success: bool
    variants: List[GeneratedContent]
    error: Optional[str] = None


@router.post("/generate/instagram/caption", response_model=GenerationResponse)
async def generate_instagram_caption(request: InstagramCaptionRequest, _=Depends(rate_limit), user=Depends(require_auth)):
    """Instagram caption üret"""
    try:
        from server import generate_with_openai
        from prompts.instagram import INSTAGRAM_FORMAT_PROMPTS, INSTAGRAM_SYSTEM_PROMPT
        from prompts.quality import BANNED_PATTERNS

        format_prompt = INSTAGRAM_FORMAT_PROMPTS.get(request.format, INSTAGRAM_FORMAT_PROMPTS["standard"])
        lang = "Türkçe yaz." if request.language == "tr" else "İngilizce yaz." if request.language == "en" else "Konunun diline göre otomatik yaz."

        system_prompt = f"{INSTAGRAM_SYSTEM_PROMPT}\n\n{BANNED_PATTERNS}\n\n{format_prompt}\n\n## DİL\n{lang}\n\n{'## EK BAĞLAM' + chr(10) + request.additional_context if request.additional_context else ''}\n\n## KONU\n{request.topic}"

        contents = await generate_with_openai(system_prompt, "İçeriği üret.", request.variants)
        variants = [GeneratedContent(content=c, variant_index=i, character_count=len(c)) for i, c in enumerate(contents)]
        return GenerationResponse(success=True, variants=variants)
    except Exception as e:
        logger.error(f"Instagram caption error: {e}")
        return GenerationResponse(success=False, variants=[], error="Bir hata oluştu. Lütfen tekrar deneyin.")


@router.post("/generate/instagram/reel-script", response_model=GenerationResponse)
async def generate_instagram_reel(request: InstagramReelRequest, _=Depends(rate_limit), user=Depends(require_auth)):
    """Instagram reel scripti üret"""
    try:
        from server import generate_with_openai
        from prompts.instagram import INSTAGRAM_FORMAT_PROMPTS, INSTAGRAM_SYSTEM_PROMPT
        from prompts.quality import BANNED_PATTERNS

        format_prompt = INSTAGRAM_FORMAT_PROMPTS["reel_script"]
        lang = "Türkçe yaz." if request.language == "tr" else "İngilizce yaz." if request.language == "en" else "Konunun diline göre otomatik yaz."

        system_prompt = f"{INSTAGRAM_SYSTEM_PROMPT}\n\n{BANNED_PATTERNS}\n\n{format_prompt}\n\nHedef süre: {request.duration} saniye\n\n## DİL\n{lang}\n\n{'## EK BAĞLAM' + chr(10) + request.additional_context if request.additional_context else ''}\n\n## KONU\n{request.topic}"

        contents = await generate_with_openai(system_prompt, "Reel scriptini üret.", 1)
        variants = [GeneratedContent(content=contents[0], variant_index=0, character_count=len(contents[0]))]
        return GenerationResponse(success=True, variants=variants)
    except Exception as e:
        logger.error(f"Instagram reel error: {e}")
        return GenerationResponse(success=False, variants=[], error="Bir hata oluştu. Lütfen tekrar deneyin.")


@router.post("/generate/instagram/hashtags", response_model=GenerationResponse)
async def generate_instagram_hashtags(request: InstagramHashtagRequest, _=Depends(rate_limit), user=Depends(require_auth)):
    """Instagram hashtag seti üret"""
    try:
        from server import generate_with_openai
        from prompts.instagram import INSTAGRAM_HASHTAG_PROMPT

        niche_ctx = f"\nNiş: {request.niche}" if request.niche else ""
        system_prompt = f"{INSTAGRAM_HASHTAG_PROMPT}{niche_ctx}\n\n## KONU\n{request.topic}"

        contents = await generate_with_openai(system_prompt, "Hashtag setini üret.", 1)
        variants = [GeneratedContent(content=contents[0], variant_index=0, character_count=len(contents[0]))]
        return GenerationResponse(success=True, variants=variants)
    except Exception as e:
        logger.error(f"Instagram hashtag error: {e}")
        return GenerationResponse(success=False, variants=[], error="Bir hata oluştu. Lütfen tekrar deneyin.")


@router.post("/generate/instagram/story-ideas", response_model=GenerationResponse)
async def generate_instagram_stories(request: InstagramStoryRequest, _=Depends(rate_limit), user=Depends(require_auth)):
    """Instagram story fikirleri üret"""
    try:
        from server import generate_with_openai
        from prompts.instagram import INSTAGRAM_FORMAT_PROMPTS, INSTAGRAM_SYSTEM_PROMPT

        format_prompt = INSTAGRAM_FORMAT_PROMPTS["story_ideas"]
        lang = "Türkçe yaz." if request.language == "tr" else "İngilizce yaz." if request.language == "en" else "Konunun diline göre otomatik yaz."

        system_prompt = f"{INSTAGRAM_SYSTEM_PROMPT}\n\n{format_prompt}\n\nStory sayısı: {request.count}\n\n## DİL\n{lang}\n\n{'## EK BAĞLAM' + chr(10) + request.additional_context if request.additional_context else ''}\n\n## KONU\n{request.topic}"

        contents = await generate_with_openai(system_prompt, "Story fikirlerini üret.", 1)
        variants = [GeneratedContent(content=contents[0], variant_index=0, character_count=len(contents[0]))]
        return GenerationResponse(success=True, variants=variants)
    except Exception as e:
        logger.error(f"Instagram story error: {e}")
        return GenerationResponse(success=False, variants=[], error="Bir hata oluştu. Lütfen tekrar deneyin.")


@router.get("/meta/instagram/formats")
async def get_instagram_formats():
    """Instagram formatlarını döndür"""
    from prompts.instagram import INSTAGRAM_FORMATS
    return [{"id": k, **v} for k, v in INSTAGRAM_FORMATS.items()]
