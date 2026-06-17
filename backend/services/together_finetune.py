# @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import/cagri yok; aktif akisin parcasi DEGIL.
# Referans icin tutuluyor. Bkz: docs/DEPRECATED_MODULES.md
"""
Together AI Fine-tuning Servisi
- JSONL dataset upload
- Fine-tune job yönetimi
- Fine-tuned model ile inference
"""
import os
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

TOGETHER_BASE_URL = "https://api.together.xyz/v1"
DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct"


class TogetherFineTuneService:
    def __init__(self):
        self.api_key = os.environ.get("TOGETHER_API_KEY", "")
        if not self.api_key:
            logger.warning("TOGETHER_API_KEY tanımlı değil!")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
        }

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """Together AI API'ye istek at."""
        url = f"{TOGETHER_BASE_URL}{path}"
        async with httpx.AsyncClient(timeout=120) as client:
            try:
                resp = await client.request(method, url, headers=self._headers(), **kwargs)
                if resp.status_code == 429:
                    raise Exception("Together AI rate limit aşıldı, biraz bekleyin.")
                if resp.status_code == 401:
                    raise Exception("Together AI API key geçersiz.")
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                body = e.response.text
                logger.error(f"Together AI hata: {e.response.status_code} - {body}")
                raise Exception(f"Together AI API hatası ({e.response.status_code}): {body}")

    # ── File Upload ──────────────────────────────────────────────

    async def upload_file(self, file_content: bytes, filename: str = "training.jsonl") -> dict:
        """JSONL dosyasını Together AI'ye yükle."""
        logger.info(f"Dosya yükleniyor: {filename} ({len(file_content)} bytes)")
        url = f"{TOGETHER_BASE_URL}/files"
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                url,
                headers=self._headers(),
                files={"file": (filename, file_content, "application/jsonl")},
                data={"purpose": "fine-tune"},
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"Dosya yüklendi: file_id={data.get('id')}")
            return data

    # ── Fine-tune Job ────────────────────────────────────────────

    async def create_finetune(
        self,
        training_file: str,
        model: str = DEFAULT_MODEL,
        n_epochs: int = 3,
        learning_rate: float = 1e-5,
        batch_size: int = 4,
        suffix: Optional[str] = None,
        wandb_api_key: Optional[str] = None,
    ) -> dict:
        """Fine-tune job başlat."""
        payload: dict = {
            "training_file": training_file,
            "model": model,
            "n_epochs": n_epochs,
            "learning_rate": learning_rate,
            "batch_size": batch_size,
        }
        if suffix:
            payload["suffix"] = suffix
        if wandb_api_key:
            payload["wandb"] = {"api_key": wandb_api_key}

        logger.info(f"Fine-tune başlatılıyor: model={model}, epochs={n_epochs}")
        return await self._request("POST", "/fine-tunes", json=payload)

    async def get_finetune_status(self, job_id: str) -> dict:
        """Fine-tune job durumunu sorgula."""
        return await self._request("GET", f"/fine-tunes/{job_id}")

    async def list_finetunes(self) -> dict:
        """Tüm fine-tune job'ları listele."""
        return await self._request("GET", "/fine-tunes")

    async def cancel_finetune(self, job_id: str) -> dict:
        """Fine-tune job iptal et."""
        logger.info(f"Fine-tune iptal ediliyor: {job_id}")
        return await self._request("POST", f"/fine-tunes/{job_id}/cancel")

    # ── Inference ────────────────────────────────────────────────

    async def chat_completion(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = 512,
        temperature: float = 0.7,
        n: int = 1,
    ) -> dict:
        """Fine-tuned model ile chat completion."""
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "n": n,
        }
        return await self._request("POST", "/chat/completions", json=payload)

    # ── Models ───────────────────────────────────────────────────

    async def list_finetuned_models(self) -> list[dict]:
        """Tamamlanmış fine-tune job'lardan model listesi çıkar."""
        result = await self.list_finetunes()
        jobs = result.get("data", result) if isinstance(result, dict) else result
        if not isinstance(jobs, list):
            jobs = []
        return [
            {
                "job_id": j.get("id"),
                "model": j.get("output_name") or j.get("fine_tuned_model"),
                "base_model": j.get("model"),
                "status": j.get("status"),
                "created_at": j.get("created_at"),
            }
            for j in jobs
            if j.get("status") == "completed"
        ]


# Singleton
together_service = TogetherFineTuneService()
