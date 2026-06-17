"""Blog içerik üretim route'ları v2.
POST /api/generate/blog/outline - Blog taslak üretimi
POST /api/generate/blog/full - Tam blog yazısı üretimi
POST /api/generate/blog/seo-optimize - SEO analiz ve optimizasyon
POST /api/generate/blog/cover-image - Cover + makale içi görsel promptları
POST /api/generate/blog/repurpose - Blog'u diğer platformlara dönüştürme
GET /api/meta/blog/styles - Blog stilleri
GET /api/meta/blog/frameworks - Yazı framework'leri
GET /api/meta/blog/levels - İçerik seviyeleri
"""
from fastapi import APIRouter, HTTPException, Depends
from middleware.auth import require_auth
from middleware.rate_limit import rate_limit
from pydantic import BaseModel
from typing import Optional, List
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["blog"])


# ==================== MODELS ====================

class BlogOutlineRequest(BaseModel):
    topic: str
    style: str = "informative"
    framework: str = "answer_first"
    target_keyword: Optional[str] = None
    language: str = "auto"
    additional_context: Optional[str] = None
    trend_context: Optional[str] = None  # Trend'den gelen ek bağlam


class BlogFullRequest(BaseModel):
    topic: str
    outline: Optional[str] = None  # Outline'dan gelen taslak
    style: str = "informative"
    framework: str = "answer_first"
    level: str = "standard"  # quick, standard, deep_dive, ultimate
    target_keyword: Optional[str] = None
    language: str = "auto"
    additional_context: Optional[str] = None
    trend_context: Optional[str] = None


class BlogSEORequest(BaseModel):
    content: str  # Mevcut blog yazısı
    target_keyword: Optional[str] = None
    language: str = "auto"


class BlogCoverImageRequest(BaseModel):
    topic: str
    content: Optional[str] = None  # Blog içeriği varsa daha iyi prompt üretir
    style: str = "editorial"  # photorealistic, editorial, illustration, 3d
    section_count: int = 3  # Kaç makale içi görsel promptu üretilsin


class BlogRepurposeRequest(BaseModel):
    blog_content: str
    target_platform: str = "twitter"  # twitter, linkedin, instagram_carousel
    language: str = "auto"


class GeneratedContent(BaseModel):
    content: str
    variant_index: int = 0
    character_count: int = 0


class GenerationResponse(BaseModel):
    success: bool
    variants: List[GeneratedContent]
    error: Optional[str] = None
    metadata: Optional[dict] = None  # SEO skoru, readability vb.


# ==================== HELPERS ====================

def _get_word_range(level: str) -> str:
    from prompts.blog import CONTENT_LEVELS
    lvl = CONTENT_LEVELS.get(level, CONTENT_LEVELS["standard"])
    return lvl["word_range"]


def _get_framework_instruction(framework: str) -> str:
    from prompts.blog import BLOG_FRAMEWORKS
    fw = BLOG_FRAMEWORKS.get(framework, BLOG_FRAMEWORKS["answer_first"])
    return f"Framework: {fw['label']}\nYapı: {fw['structure']}\nEn iyi: {fw['best_for']}"


def _calculate_readability(text: str) -> dict:
    """Basit okunabilirlik metrikleri hesapla."""
    words = text.split()
    sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    h2_count = text.count("## ") + text.count("\n## ")

    word_count = len(words)
    sentence_count = max(len(sentences), 1)
    avg_sentence_length = round(word_count / sentence_count, 1)
    read_time = round(word_count / 200, 1)  # 200 kelime/dk ortalama

    return {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "avg_sentence_length": avg_sentence_length,
        "paragraph_count": len(paragraphs),
        "h2_count": h2_count,
        "estimated_read_time_min": read_time,
    }


# ==================== ROUTES ====================

@router.post("/generate/blog/outline", response_model=GenerationResponse)
async def generate_blog_outline(request: BlogOutlineRequest, _=Depends(rate_limit), user=Depends(require_auth)):
    """Blog taslağı üret"""
    try:
        from server import generate_with_openai
        from prompts.blog import BLOG_FORMAT_PROMPTS, BLOG_SYSTEM_PROMPT

        format_prompt = BLOG_FORMAT_PROMPTS["outline"]
        fw_instruction = _get_framework_instruction(request.framework)
        lang = "Türkçe yaz." if request.language == "tr" else "İngilizce yaz." if request.language == "en" else "Konunun diline göre otomatik yaz."
        keyword_ctx = f"\nHedef anahtar kelime: {request.target_keyword}" if request.target_keyword else ""
        trend_ctx = f"\n\n## TREND BAĞLAMI\n{request.trend_context}" if request.trend_context else ""

        system_prompt = (
            f"{BLOG_SYSTEM_PROMPT}\n\n"
            f"{format_prompt}\n\n"
            f"## AYARLAR\n"
            f"Stil: {request.style}\n"
            f"{fw_instruction}\n"
            f"{keyword_ctx}\n\n"
            f"## DİL\n{lang}"
            f"{trend_ctx}"
        )
        if request.additional_context:
            system_prompt += f"\n\n## EK BAĞLAM\n{request.additional_context}"

        user_prompt = f"Konu: {request.topic}\n\nBlog taslağını oluştur."

        contents = await generate_with_openai(system_prompt, user_prompt, 1)
        variants = [GeneratedContent(content=contents[0], variant_index=0, character_count=len(contents[0]))]
        return GenerationResponse(success=True, variants=variants)
    except Exception as e:
        logger.error(f"Blog outline error: {e}")
        return GenerationResponse(success=False, variants=[], error="Bir hata oluştu. Lütfen tekrar deneyin.")


@router.post("/generate/blog/full", response_model=GenerationResponse)
async def generate_blog_full(request: BlogFullRequest, _=Depends(rate_limit), user=Depends(require_auth)):
    """Tam blog yazısı üret"""
    try:
        from server import generate_with_openai
        from prompts.blog import BLOG_FORMAT_PROMPTS, BLOG_SYSTEM_PROMPT

        format_prompt = BLOG_FORMAT_PROMPTS["full"]
        fw_instruction = _get_framework_instruction(request.framework)
        word_range = _get_word_range(request.level)
        lang = "Türkçe yaz." if request.language == "tr" else "İngilizce yaz." if request.language == "en" else "Konunun diline göre otomatik yaz."
        keyword_ctx = f"\nHedef anahtar kelime: {request.target_keyword}" if request.target_keyword else ""
        outline_ctx = f"\n\n## TASLAK (Bunu Takip Et)\n{request.outline}" if request.outline else ""
        trend_ctx = f"\n\n## TREND BAĞLAMI\n{request.trend_context}" if request.trend_context else ""

        system_prompt = (
            f"{BLOG_SYSTEM_PROMPT}\n\n"
            f"{format_prompt}\n\n"
            f"## AYARLAR\n"
            f"Stil: {request.style}\n"
            f"{fw_instruction}\n"
            f"Hedef kelime sayısı: ~{word_range} kelime\n"
            f"{keyword_ctx}\n\n"
            f"## DİL\n{lang}"
            f"{outline_ctx}"
            f"{trend_ctx}"
        )
        if request.additional_context:
            system_prompt += f"\n\n## EK BAĞLAM\n{request.additional_context}"

        user_prompt = f"Konu: {request.topic}\n\nBlog yazısını yaz."

        contents = await generate_with_openai(system_prompt, user_prompt, 1)

        # Readability metrikleri hesapla
        readability = _calculate_readability(contents[0])

        variants = [GeneratedContent(content=contents[0], variant_index=0, character_count=len(contents[0]))]
        return GenerationResponse(success=True, variants=variants, metadata={"readability": readability})
    except Exception as e:
        logger.error(f"Blog full error: {e}")
        return GenerationResponse(success=False, variants=[], error="Bir hata oluştu. Lütfen tekrar deneyin.")


@router.post("/generate/blog/seo-optimize", response_model=GenerationResponse)
async def generate_blog_seo(request: BlogSEORequest, _=Depends(rate_limit), user=Depends(require_auth)):
    """Mevcut blog yazısını SEO analiz et"""
    try:
        from server import generate_with_openai
        from prompts.blog import BLOG_FORMAT_PROMPTS, BLOG_SYSTEM_PROMPT

        format_prompt = BLOG_FORMAT_PROMPTS["seo_optimize"]
        keyword_ctx = f"\nHedef anahtar kelime: {request.target_keyword}" if request.target_keyword else ""
        lang = "Türkçe analiz yap." if request.language == "tr" else "İngilizce analiz yap." if request.language == "en" else "Otomatik dil."

        system_prompt = f"{format_prompt}\n{keyword_ctx}\n{lang}"
        user_prompt = f"Bu blog yazısını SEO açısından analiz et:\n\n{request.content}"

        contents = await generate_with_openai(system_prompt, user_prompt, 1)

        # Readability metrikleri
        readability = _calculate_readability(request.content)

        # Parse JSON response
        raw = contents[0].replace("```json", "").replace("```", "").strip()
        try:
            seo_data = json.loads(raw)
        except json.JSONDecodeError:
            seo_data = {"raw_analysis": raw}

        variants = [GeneratedContent(content=contents[0], variant_index=0, character_count=len(contents[0]))]
        return GenerationResponse(success=True, variants=variants, metadata={
            "readability": readability,
            "seo_analysis": seo_data
        })
    except Exception as e:
        logger.error(f"Blog SEO error: {e}")
        return GenerationResponse(success=False, variants=[], error="Bir hata oluştu. Lütfen tekrar deneyin.")


@router.post("/generate/blog/cover-image", response_model=GenerationResponse)
async def generate_blog_cover_image(request: BlogCoverImageRequest, _=Depends(rate_limit), user=Depends(require_auth)):
    """Blog cover image + makale içi görsel promptları üret"""
    try:
        from server import generate_with_openai
        from prompts.blog import BLOG_FORMAT_PROMPTS

        format_prompt = BLOG_FORMAT_PROMPTS["cover_image"]

        content_ctx = f"\n\nBlog içeriği (kısa özet):\n{request.content[:1000]}" if request.content else ""

        system_prompt = format_prompt
        user_prompt = (
            f"Blog konusu: {request.topic}\n"
            f"Stil: {request.style}\n"
            f"Makale içi görsel sayısı: {request.section_count}\n"
            f"{content_ctx}\n\n"
            f"Cover image ve makale içi görsel promptlarını üret."
        )

        contents = await generate_with_openai(system_prompt, user_prompt, 1)

        # Parse JSON
        raw = contents[0].replace("```json", "").replace("```", "").strip()
        try:
            image_data = json.loads(raw)
        except json.JSONDecodeError:
            image_data = {"raw": raw}

        variants = [GeneratedContent(content=contents[0], variant_index=0, character_count=len(contents[0]))]
        return GenerationResponse(success=True, variants=variants, metadata={"image_prompts": image_data})
    except Exception as e:
        logger.error(f"Blog cover image error: {e}")
        return GenerationResponse(success=False, variants=[], error="Bir hata oluştu. Lütfen tekrar deneyin.")


@router.post("/generate/blog/repurpose", response_model=GenerationResponse)
async def generate_blog_repurpose(request: BlogRepurposeRequest, _=Depends(rate_limit), user=Depends(require_auth)):
    """Blog'u başka platforma dönüştür"""
    try:
        from server import generate_with_openai
        from prompts.blog import BLOG_FORMAT_PROMPTS

        format_prompt = BLOG_FORMAT_PROMPTS["repurpose"]
        lang = "Türkçe yaz." if request.language == "tr" else "İngilizce yaz." if request.language == "en" else "Konunun diline göre otomatik yaz."

        system_prompt = f"{format_prompt}\n\nHedef platform: {request.target_platform}\n\n## DİL\n{lang}"
        user_prompt = f"Bu blog yazısını {request.target_platform} formatına dönüştür:\n\n{request.blog_content}"

        contents = await generate_with_openai(system_prompt, user_prompt, 1)
        variants = [GeneratedContent(content=contents[0], variant_index=0, character_count=len(contents[0]))]
        return GenerationResponse(success=True, variants=variants)
    except Exception as e:
        logger.error(f"Blog repurpose error: {e}")
        return GenerationResponse(success=False, variants=[], error="Bir hata oluştu. Lütfen tekrar deneyin.")


# ==================== META ROUTES ====================

@router.get("/meta/blog/styles")
async def get_blog_styles():
    from prompts.blog import BLOG_STYLES
    return [{"id": k, **v} for k, v in BLOG_STYLES.items()]


@router.get("/meta/blog/frameworks")
async def get_blog_frameworks():
    from prompts.blog import BLOG_FRAMEWORKS
    return [{"id": k, **v} for k, v in BLOG_FRAMEWORKS.items()]


@router.get("/meta/blog/levels")
async def get_blog_levels():
    from prompts.blog import CONTENT_LEVELS
    return [{"id": k, **v} for k, v in CONTENT_LEVELS.items()]
