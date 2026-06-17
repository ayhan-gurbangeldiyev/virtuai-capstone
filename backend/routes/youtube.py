"""YouTube içerik üretim route'ları.
POST /api/generate/youtube/idea - Video fikir üretimi
POST /api/generate/youtube/script - Video script üretimi
POST /api/generate/youtube/title - Başlık üretimi
POST /api/generate/youtube/description - Açıklama + tag üretimi
GET /api/meta/youtube/formats - YouTube formatları
"""
from fastapi import APIRouter, Depends
from middleware.auth import require_auth
from middleware.rate_limit import rate_limit
from pydantic import BaseModel
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["youtube"])


class YouTubeIdeaRequest(BaseModel):
    niche: str
    count: int = 5
    language: str = "auto"
    additional_context: Optional[str] = None


class YouTubeScriptRequest(BaseModel):
    topic: str
    duration_minutes: int = 10
    style: str = "educational"
    language: str = "auto"
    additional_context: Optional[str] = None


class YouTubeTitleRequest(BaseModel):
    topic: str
    count: int = 7
    language: str = "auto"


class YouTubeDescriptionRequest(BaseModel):
    topic: str
    video_title: Optional[str] = None
    target_keyword: Optional[str] = None
    language: str = "auto"


class GeneratedContent(BaseModel):
    content: str
    variant_index: int = 0
    character_count: int = 0


class GenerationResponse(BaseModel):
    success: bool
    variants: List[GeneratedContent]
    error: Optional[str] = None


def _lang_instruction(lang: str) -> str:
    if lang == "tr": return "Türkçe yaz."
    if lang == "en": return "İngilizce yaz."
    return "Konunun diline göre otomatik yaz."


@router.post("/generate/youtube/idea", response_model=GenerationResponse)
async def generate_youtube_idea(request: YouTubeIdeaRequest, _=Depends(rate_limit), user=Depends(require_auth)):
    """YouTube video fikirleri üret"""
    try:
        from server import generate_with_openai
        from prompts.youtube import YOUTUBE_FORMAT_PROMPTS, YOUTUBE_SYSTEM_PROMPT

        system_prompt = f"{YOUTUBE_SYSTEM_PROMPT}\n\n{YOUTUBE_FORMAT_PROMPTS['idea']}\n\nFikir sayısı: {request.count}\n\n## DİL\n{_lang_instruction(request.language)}\n\n{'## EK BAĞLAM' + chr(10) + request.additional_context if request.additional_context else ''}\n\n## NİŞ/KONU\n{request.niche}"

        contents = await generate_with_openai(system_prompt, "Video fikirlerini üret.", 1)
        variants = [GeneratedContent(content=contents[0], variant_index=0, character_count=len(contents[0]))]
        return GenerationResponse(success=True, variants=variants)
    except Exception as e:
        logger.error(f"YouTube idea error: {e}")
        return GenerationResponse(success=False, variants=[], error="Bir hata oluştu. Lütfen tekrar deneyin.")


@router.post("/generate/youtube/script", response_model=GenerationResponse)
async def generate_youtube_script(request: YouTubeScriptRequest, _=Depends(rate_limit), user=Depends(require_auth)):
    """YouTube video scripti üret"""
    try:
        from server import generate_with_openai
        from prompts.youtube import YOUTUBE_FORMAT_PROMPTS, YOUTUBE_SYSTEM_PROMPT
        from prompts.quality import BANNED_PATTERNS

        system_prompt = f"{YOUTUBE_SYSTEM_PROMPT}\n\n{BANNED_PATTERNS}\n\n{YOUTUBE_FORMAT_PROMPTS['script']}\n\nHedef süre: ~{request.duration_minutes} dakika\nStil: {request.style}\n\n## DİL\n{_lang_instruction(request.language)}\n\n{'## EK BAĞLAM' + chr(10) + request.additional_context if request.additional_context else ''}\n\n## KONU\n{request.topic}"

        contents = await generate_with_openai(system_prompt, "Video scriptini yaz.", 1)
        variants = [GeneratedContent(content=contents[0], variant_index=0, character_count=len(contents[0]))]
        return GenerationResponse(success=True, variants=variants)
    except Exception as e:
        logger.error(f"YouTube script error: {e}")
        return GenerationResponse(success=False, variants=[], error="Bir hata oluştu. Lütfen tekrar deneyin.")


@router.post("/generate/youtube/title", response_model=GenerationResponse)
async def generate_youtube_title(request: YouTubeTitleRequest, _=Depends(rate_limit), user=Depends(require_auth)):
    """YouTube başlıkları üret"""
    try:
        from server import generate_with_openai
        from prompts.youtube import YOUTUBE_FORMAT_PROMPTS, YOUTUBE_SYSTEM_PROMPT

        system_prompt = f"{YOUTUBE_SYSTEM_PROMPT}\n\n{YOUTUBE_FORMAT_PROMPTS['title']}\n\nBaşlık sayısı: {request.count}\n\n## DİL\n{_lang_instruction(request.language)}\n\n## KONU\n{request.topic}"

        contents = await generate_with_openai(system_prompt, "Başlıkları üret.", 1)
        variants = [GeneratedContent(content=contents[0], variant_index=0, character_count=len(contents[0]))]
        return GenerationResponse(success=True, variants=variants)
    except Exception as e:
        logger.error(f"YouTube title error: {e}")
        return GenerationResponse(success=False, variants=[], error="Bir hata oluştu. Lütfen tekrar deneyin.")


@router.post("/generate/youtube/description", response_model=GenerationResponse)
async def generate_youtube_description(request: YouTubeDescriptionRequest, _=Depends(rate_limit), user=Depends(require_auth)):
    """YouTube açıklama + taglar üret"""
    try:
        from server import generate_with_openai
        from prompts.youtube import YOUTUBE_FORMAT_PROMPTS, YOUTUBE_SYSTEM_PROMPT

        title_ctx = f"\nVideo başlığı: {request.video_title}" if request.video_title else ""
        keyword_ctx = f"\nHedef anahtar kelime: {request.target_keyword}" if request.target_keyword else ""

        system_prompt = f"{YOUTUBE_SYSTEM_PROMPT}\n\n{YOUTUBE_FORMAT_PROMPTS['description']}{title_ctx}{keyword_ctx}\n\n## DİL\n{_lang_instruction(request.language)}\n\n## KONU\n{request.topic}"

        contents = await generate_with_openai(system_prompt, "Açıklama ve tagları üret.", 1)
        variants = [GeneratedContent(content=contents[0], variant_index=0, character_count=len(contents[0]))]
        return GenerationResponse(success=True, variants=variants)
    except Exception as e:
        logger.error(f"YouTube description error: {e}")
        return GenerationResponse(success=False, variants=[], error="Bir hata oluştu. Lütfen tekrar deneyin.")


@router.get("/meta/youtube/formats")
async def get_youtube_formats():
    """YouTube formatlarını döndür"""
    from prompts.youtube import YOUTUBE_FORMATS
    return [{"id": k, **v} for k, v in YOUTUBE_FORMATS.items()]
