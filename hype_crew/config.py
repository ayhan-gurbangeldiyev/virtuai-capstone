"""Hype Crew runtime configuration.

Loads .env once, exposes typed settings via `settings` singleton.
Import: `from hype_crew.config import settings`
"""
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Load .env from hype_crew/ dir (next to this file)
ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")


def _required(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        raise RuntimeError(f"Missing required env var: {key} (set in hype_crew/.env)")
    return val


def _optional(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _bool(key: str, default: bool = False) -> bool:
    return _optional(key, str(default)).lower() in ("1", "true", "yes", "on")


def _float(key: str, default: float = 0.0) -> float:
    try:
        return float(_optional(key, str(default)))
    except ValueError:
        return default


def _int(key: str, default: int = 0) -> int:
    try:
        return int(_optional(key, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # Supabase
    supabase_url: str
    supabase_service_key: str

    # LLM
    openrouter_api_key: str
    openai_api_key: str            # TTS kalite kapısı (OpenAI Whisper); boşsa fal-whisper
    cansu_tts_gate_mode: str       # balanced | strict
    model_fast: str
    model_smart: str
    # 2026-06-08 — writer model override (Sonnet 4.6 by default for the
    # writer step ONLY; gate/editor/dedup stay on model_smart Gemini Flash).
    # Set to empty string in env to disable override (cron falls back to
    # is_ultra=False → Flash for the writer too).
    writer_model: str

    # Postiz
    postiz_api_key: str
    postiz_base_url: str

    # Runtime
    dry_run: bool
    log_level: str
    daily_cost_cap_usd: float
    default_schedule_delay_hours: int

    # Memory
    memory_backend: str

    # Wiro AI (Phase 21 — visual pipeline)
    wiro_api_key: str
    wiro_api_secret: str
    wiro_base_url: str
    wiro_image_default_slug: str

    # Persona asset storage (Phase 21)
    supabase_reference_bucket: str
    supabase_generated_bucket: str

    # Compliance thresholds (Phase 21)
    clip_similarity_threshold: float
    aesthetic_threshold: float

    # Phase 23 — Video pipeline
    supabase_videos_bucket: str
    ffmpeg_path: str
    ffmpeg_preset: str
    video_bitrate_kbps: int
    video_max_file_size_mb: int

    # Phase 23 — HeyGen avatar (was never wired into config; .env had the key
    # but settings.heygen_api_key stayed empty → avatar step failed once a
    # script finally passed the pre-spend guard).
    heygen_api_key: str

    # Phase 23 — MiniMax TTS (Türkçe Cansu voice clone)
    minimax_api_key: str
    minimax_group_id: str
    minimax_voice_id_cansu: str
    minimax_api_base: str
    minimax_model: str

    # Phase 42.B-07 — brand-brief-builder (default OFF, byte-for-byte
    # identical Phase 34 fallback when disabled). flow.py:2344/2420/2458
    # gate behavior on this flag — Settings without the attribute raises
    # AttributeError and crashes _run_visual_branch, killing every image.
    brand_brief_builder_enabled: bool

    # Cansu frame i2i pipeline — single Wiro Nano Banana Pro call composites the
    # news hero into a fixed framed template (4:5, 4K) and writes the headline.
    # cansu_frame_template_url: the persistent CDN/Wiro URL of the approved frame
    #   (Gen-Z purple minimal template) — passed as input_image for img2img.
    # cansu_frame_i2i_enabled: default OFF. When ON, generate_visual() routes the
    #   still/photo path through framed_news_image instead of the brand/face path.
    # cansu_style_board_url: optional second reference (Cansu aesthetic anchor).
    #   Empty until the style-board asset is produced (Section 8 TODO).
    cansu_frame_template_url: str
    cansu_frame_i2i_enabled: bool
    cansu_style_board_url: str
    # SÖZLÜK/SENCE? yardımcı kartları Postiz'e CANLI yayınlasın mı? Default OFF →
    # kartlar pending_review draft olarak düşer (Berkay onaylayınca flag açılır).
    cards_publish_enabled: bool

    # Cansu video v2 — complete-news narration pipeline (Berkay 10 Haz 2026).
    # When ON, generate_video() routes through the dedicated complete-news
    # writer + autonomous script_lint gate + tts_normalize, and skips video
    # for weak-source trends. Default OFF → byte-for-byte legacy behavior
    # (platform-draft script via _resolve_video_script, no new gate).
    # cansu_video_min_source_chars: full_source_text shorter than this → NO
    #   video (image-only). Weak source + "give the whole news" = hallucination
    #   (a 149-char source invented company names); measured natural gap ~500.
    cansu_video_v2_enabled: bool
    cansu_video_min_source_chars: int

    # LangGraph durability migration (durability/resume önceliği). Default OFF →
    # CrewAI Flow yolu byte-for-byte korunur (anında rollback = flag kapat).
    # langgraph_enabled: per-account override hype_account_config.langgraph_enabled
    #   ile DB-wins (dry_run_mode deseni); bu env genel fallback.
    # checkpoint_db_url: PostgresSaver için direct Postgres conn string
    #   (Supabase `langgraph` şeması). BOŞSA → lokal SQLite checkpointer (dev/spike,
    #   secret gerektirmez). Mekanizma aynı; sadece backend farklı.
    langgraph_enabled: bool
    checkpoint_db_url: str

    # LiteLLM Router (kırılganlık kök-neden: direct LLM çağrılarına uniform
    # timeout+retry+fallback+devre-kesici+gerçek cost/latency). Default OFF →
    # mevcut httpx/SDK yolları aynen çalışır. İlk hedef: card_gates.chat_json.
    litellm_router_enabled: bool


settings = Settings(
    supabase_url=_required("SUPABASE_URL"),
    supabase_service_key=_required("SUPABASE_SERVICE_KEY"),
    openrouter_api_key=_required("OPENROUTER_API_KEY"),
    openai_api_key=_optional("OPENAI_API_KEY", ""),
    cansu_tts_gate_mode=_optional("CANSU_TTS_GATE_MODE", "balanced"),
    # Phase 18.9 — defaults moved to Gemini 3 Flash for ~30x cost reduction
    # and more natural Turkish output. Override via env vars if needed.
    model_fast=_optional("HYPE_MODEL_FAST", "openrouter/google/gemini-3-flash-preview"),
    model_smart=_optional("HYPE_MODEL_SMART", "openrouter/google/gemini-3-flash-preview"),
    # 2026-06-08 — writer ONLY runs on Sonnet 4.6 by default; gate/editor
    # stay on model_smart. Set HYPE_WRITER_MODEL=  (empty) to disable.
    writer_model=_optional("HYPE_WRITER_MODEL", "anthropic/claude-sonnet-4.6"),
    postiz_api_key=_optional("POSTIZ_API_KEY"),  # may be empty during dry-run dev
    postiz_base_url=_optional("POSTIZ_BASE_URL", "https://api.postiz.com/public/v1"),
    dry_run=_bool("HYPE_DRY_RUN", default=True),
    log_level=_optional("HYPE_LOG_LEVEL", "INFO"),
    daily_cost_cap_usd=_float("HYPE_DAILY_COST_CAP_USD", 2.00),
    default_schedule_delay_hours=_int("HYPE_DEFAULT_SCHEDULE_DELAY_HOURS", 2),
    memory_backend=_optional("HYPE_MEMORY_BACKEND", "supabase"),
    # Phase 21 — Wiro AI
    wiro_api_key=_optional("WIRO_API_KEY"),
    wiro_api_secret=_optional("WIRO_API_SECRET"),
    wiro_base_url=_optional("WIRO_BASE_URL", "https://api.wiro.ai/v1"),
    wiro_image_default_slug=_optional("WIRO_IMAGE_DEFAULT_SLUG", "google/nano-banana-pro"),
    # Phase 21 — Storage buckets
    supabase_reference_bucket=_optional("SUPABASE_REFERENCE_BUCKET", "persona-anchors"),
    supabase_generated_bucket=_optional("SUPABASE_GENERATED_BUCKET", "persona-generated"),
    # Phase 21 — Compliance thresholds
    clip_similarity_threshold=_float("CLIP_SIMILARITY_THRESHOLD", 0.85),
    aesthetic_threshold=_float("AESTHETIC_THRESHOLD", 0.65),
    # Phase 23 — Video pipeline
    supabase_videos_bucket=_optional("SUPABASE_VIDEOS_BUCKET", "persona-videos"),
    ffmpeg_path=_optional("FFMPEG_PATH", "ffmpeg"),
    ffmpeg_preset=_optional("FFMPEG_PRESET", "medium"),
    video_bitrate_kbps=_int("VIDEO_ENCODING_BITRATE_KBPS", 6500),
    video_max_file_size_mb=_int("VIDEO_ENCODING_MAX_FILE_SIZE_MB", 30),
    # Phase 23 — HeyGen avatar
    heygen_api_key=_optional("HEYGEN_API_KEY"),
    # Phase 23 — MiniMax TTS
    minimax_api_key=_optional("MINIMAX_API_KEY"),
    minimax_group_id=_optional("MINIMAX_GROUP_ID"),
    minimax_voice_id_cansu=_optional("MINIMAX_VOICE_ID_CANSU"),
    minimax_api_base=_optional("MINIMAX_API_BASE", "https://api.minimax.io/v1"),
    minimax_model=_optional("MINIMAX_MODEL", "speech-02-hd"),
    # Phase 42.B-07 — default OFF; flow.py falls back to Phase 34 brand
    # extractor (byte-for-byte). Flip via BRAND_BRIEF_BUILDER_ENABLED=true.
    brand_brief_builder_enabled=_bool("BRAND_BRIEF_BUILDER_ENABLED", default=False),
    # Cansu frame i2i pipeline — default OFF (no regression). Set the frame URL
    # + flip CANSU_FRAME_I2I_ENABLED=true to route stills through the framed i2i.
    cansu_frame_template_url=_optional("CANSU_FRAME_TEMPLATE_URL"),
    cansu_frame_i2i_enabled=_bool("CANSU_FRAME_I2I_ENABLED", default=False),
    cards_publish_enabled=_bool("CANSU_CARDS_PUBLISH_ENABLED", default=False),
    cansu_style_board_url=_optional("CANSU_STYLE_BOARD_URL"),
    # Cansu video v2 — default OFF (legacy path preserved). Flip
    # CANSU_VIDEO_V2_ENABLED=true to route through complete-news writer + gate.
    cansu_video_v2_enabled=_bool("CANSU_VIDEO_V2_ENABLED", default=False),
    cansu_video_min_source_chars=_int("CANSU_VIDEO_MIN_SOURCE_CHARS", 500),
    # LangGraph durability — default OFF (CrewAI yolu korunur). checkpoint_db_url
    # boşsa lokal SQLite checkpointer kullanılır (dev/spike).
    langgraph_enabled=_bool("HYPE_LANGGRAPH_ENABLED", default=False),
    checkpoint_db_url=_optional("HYPE_CHECKPOINT_DB_URL", ""),
    # LiteLLM Router — default OFF (mevcut httpx/SDK yolları korunur).
    litellm_router_enabled=_bool("HYPE_LITELLM_ROUTER_ENABLED", default=False),
)


# Convenience for CrewAI LiteLLM — set OPENROUTER_API_KEY in process env
# (CrewAI's LiteLLM picks it up from env when model string starts with "openrouter/")
os.environ.setdefault("OPENROUTER_API_KEY", settings.openrouter_api_key)

# Disable CrewAI anonymous telemetry (we have our own observability via Supabase)
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")


def effective_langgraph_enabled(account_id: str) -> bool:
    """Per-account LangGraph anahtarı — DB-wins (dry_run_mode deseni), env fallback.

    hype_account_config.langgraph_enabled NOT NULL ise onu kullanır; NULL/kolon yok/
    sorgu hatası → settings.langgraph_enabled (env HYPE_LANGGRAPH_ENABLED).

    İKİ YERDE de (runner.run_for_account branch kararı + flow publish'teki
    _lg_resume_safety write-ahead) AYNI değeri okur → tutarlı: per-account ON ise hem
    LangGraph yolu hem write-ahead aktif; OFF ise hem CrewAI hem write-ahead kapalı
    (resume-safety kuplajı korunur, çift-post riski yok).

    NOT: env ON + tüm DB değerleri NULL → herkes ON → mevcut davranışla BİREBİR aynı
    (bu fonksiyon eklenince davranış DEĞİŞMEZ). Per-account override yalnız DB'ye
    açık değer yazılınca devreye girer.
    """
    try:
        from tools.supabase_client import make_supabase
        r = (
            make_supabase().table("hype_account_config")
            .select("langgraph_enabled").eq("account_id", account_id).limit(1).execute()
        )
        if r.data and r.data[0].get("langgraph_enabled") is not None:
            return bool(r.data[0]["langgraph_enabled"])
    except Exception:  # noqa: BLE001 — kolon yoksa / sorgu düşerse env fallback
        pass
    return bool(getattr(settings, "langgraph_enabled", False))
