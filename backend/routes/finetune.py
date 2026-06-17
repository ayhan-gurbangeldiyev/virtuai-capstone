# @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import/cagri yok; aktif akisin parcasi DEGIL.
# Referans icin tutuluyor. Bkz: docs/DEPRECATED_MODULES.md
"""
Fine-tuning route'ları - Together AI entegrasyonu
POST /api/finetune/upload   - JSONL dataset yükle
POST /api/finetune/start    - Fine-tune job başlat
GET  /api/finetune/status/{job_id} - Job durumu
GET  /api/finetune/models   - Fine-tuned modeller
POST /api/finetune/generate - Fine-tuned model ile üret
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from middleware.auth import require_auth
from pydantic import BaseModel, Field
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/finetune", tags=["finetune"])


# ── Pydantic Models ─────────────────────────────────────────

class StartFineTuneRequest(BaseModel):
    training_file_id: str
    model: str = "meta-llama/Llama-3.3-70B-Instruct"
    n_epochs: int = Field(default=3, ge=1, le=10)
    learning_rate: float = Field(default=1e-5, gt=0)
    batch_size: int = Field(default=4, ge=1, le=128)
    suffix: Optional[str] = None
    wandb_api_key: Optional[str] = None


class GenerateRequest(BaseModel):
    model: str
    prompt: str
    system_prompt: str = "Sen bir sosyal medya içerik uzmanısın. Verilen konuda etkili tweet'ler üretiyorsun."
    max_tokens: int = Field(default=280, ge=1, le=2048)
    temperature: float = Field(default=0.7, ge=0, le=2)
    n: int = Field(default=1, ge=1, le=5)


def _get_service():
    from services.together_finetune import together_service
    return together_service


# ── Routes ───────────────────────────────────────────────────

@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    user=Depends(require_auth),
):
    """JSONL dataset dosyasını Together AI'ye yükle."""
    if not file.filename or not file.filename.endswith(".jsonl"):
        raise HTTPException(400, "Sadece .jsonl dosyalar kabul edilir.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(400, "Dosya boş.")
    if len(content) > 500 * 1024 * 1024:  # 500MB
        raise HTTPException(400, "Dosya çok büyük (max 500MB).")

    try:
        svc = _get_service()
        result = await svc.upload_file(content, file.filename)
        return {"ok": True, "file": result}
    except Exception as e:
        logger.error(f"Dosya yükleme hatası: {e}")
        raise HTTPException(500, str(e))


@router.post("/start")
async def start_finetune(
    req: StartFineTuneRequest,
    user=Depends(require_auth),
):
    """Fine-tune job başlat."""
    try:
        svc = _get_service()
        result = await svc.create_finetune(
            training_file=req.training_file_id,
            model=req.model,
            n_epochs=req.n_epochs,
            learning_rate=req.learning_rate,
            batch_size=req.batch_size,
            suffix=req.suffix,
            wandb_api_key=req.wandb_api_key,
        )
        return {"ok": True, "job": result}
    except Exception as e:
        logger.error(f"Fine-tune başlatma hatası: {e}")
        raise HTTPException(500, str(e))


@router.get("/status/{job_id}")
async def get_status(job_id: str, user=Depends(require_auth)):
    """Fine-tune job durumunu sorgula."""
    try:
        svc = _get_service()
        result = await svc.get_finetune_status(job_id)
        return {"ok": True, "job": result}
    except Exception as e:
        logger.error(f"Status sorgu hatası: {e}")
        raise HTTPException(500, str(e))


@router.get("/models")
async def list_models(user=Depends(require_auth)):
    """Tamamlanmış fine-tuned modelleri listele."""
    try:
        svc = _get_service()
        models = await svc.list_finetuned_models()
        return {"ok": True, "models": models}
    except Exception as e:
        logger.error(f"Model listeleme hatası: {e}")
        raise HTTPException(500, str(e))


@router.post("/generate")
async def generate(req: GenerateRequest, user=Depends(require_auth)):
    """Fine-tuned model ile içerik üret."""
    try:
        svc = _get_service()
        messages = [
            {"role": "system", "content": req.system_prompt},
            {"role": "user", "content": req.prompt},
        ]
        result = await svc.chat_completion(
            model=req.model,
            messages=messages,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
            n=req.n,
        )
        choices = result.get("choices", [])
        texts = [c.get("message", {}).get("content", "") for c in choices]
        return {
            "ok": True,
            "generations": texts,
            "model": req.model,
            "usage": result.get("usage"),
        }
    except Exception as e:
        logger.error(f"Generate hatası: {e}")
        raise HTTPException(500, str(e))
