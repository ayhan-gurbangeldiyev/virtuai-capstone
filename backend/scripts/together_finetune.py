#!/usr/bin/env python3
"""
Type Hype - Together AI Fine-tuning Pipeline
Llama 4 Maverick 17B-128E-Instruct üzerinde LoRA fine-tuning.

Together AI Docs: https://docs.together.ai/docs/fine-tuning-quickstart
Model: meta-llama/Llama-4-Maverick-17B-128E-Instruct
  - LoRA SFT context: 16384 token
  - Batch size: min 16, max 16
  - Maliyet: $8/1M token (min $16 charge)
  - Serverless LoRA inference: ✅ (FP8, anında kullanılabilir)

Kullanım:
    # 1. Dosya yükle
    python together_finetune.py upload --train backend/data/finetune_train.jsonl --val backend/data/finetune_val.jsonl

    # 2. Fine-tune başlat
    python together_finetune.py train --train-file-id file-xxx --val-file-id file-yyy

    # 3. Job durumunu kontrol et
    python together_finetune.py status --job-id ft-xxx

    # 4. Model test et
    python together_finetune.py test --model your-account/model-name

    # 5. Tüm adımları tek seferde
    python together_finetune.py full --train backend/data/finetune_train.jsonl --val backend/data/finetune_val.jsonl
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    from together import Together
except ImportError:
    sys.exit("❌ together kütüphanesi gerekli: pip install together")


# ============================================================
# Config
# ============================================================
MODEL = "meta-llama/Llama-4-Maverick-17B-128E-Instruct"
SUFFIX = "typehype-viral-tweets"

# Hyperparameters (Together AI defaults + tweaks)
DEFAULT_EPOCHS = 3
DEFAULT_LR = 1e-5        # LoRA için iyi başlangıç
DEFAULT_BATCH_SIZE = 16   # Maverick min=max=16
DEFAULT_WARMUP_RATIO = 0.1
DEFAULT_LORA_RANK = 16    # Default 16, 8-64 arası dene
DEFAULT_LORA_ALPHA = 32   # Genelde rank * 2
DEFAULT_LORA_DROPOUT = 0.05
N_EVALS = 10              # Validation evaluation sayısı
N_CHECKPOINTS = 3         # Checkpoint sayısı


# ============================================================
# .env loader
# ============================================================
def load_env():
    for candidate in [
        Path(__file__).resolve().parents[1] / ".env",
        Path.cwd() / ".env",
        Path.cwd() / "backend" / ".env",
    ]:
        if candidate.is_file():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))
            return


# ============================================================
# File operations
# ============================================================
def check_file_local(filepath: str) -> bool:
    """Lokal JSONL format kontrolü."""
    print(f"🔍 Dosya kontrol ediliyor: {filepath}")
    p = Path(filepath)
    if not p.exists():
        print(f"   ❌ Dosya bulunamadı: {filepath}")
        return False
    
    errors = 0
    total = 0
    with open(p) as f:
        for i, line in enumerate(f, 1):
            total += 1
            try:
                obj = json.loads(line)
                msgs = obj.get("messages", [])
                if not msgs or not isinstance(msgs, list):
                    print(f"   ⚠️  Satır {i}: 'messages' alanı eksik veya hatalı")
                    errors += 1
                    continue
                roles = [m.get("role") for m in msgs]
                if "assistant" not in roles:
                    print(f"   ⚠️  Satır {i}: 'assistant' rolü eksik")
                    errors += 1
            except json.JSONDecodeError:
                print(f"   ⚠️  Satır {i}: JSON parse hatası")
                errors += 1
    
    print(f"   ✅ {total} satır kontrol edildi, {errors} hata")
    return errors == 0


def upload_file(client: Together, filepath: str) -> str:
    """Dosya yükle, file ID döndür."""
    print(f"📤 Yükleniyor: {filepath}")
    resp = client.files.upload(file=filepath, purpose="fine-tune")
    file_id = resp.id
    print(f"   ✅ Yüklendi: {file_id}")
    print(f"   Dosya adı: {resp.filename}")
    return file_id


# ============================================================
# Fine-tuning
# ============================================================
def create_finetune(
    client: Together,
    train_file_id: str,
    val_file_id: str | None = None,
    epochs: int = DEFAULT_EPOCHS,
    lr: float = DEFAULT_LR,
    batch_size: int = DEFAULT_BATCH_SIZE,
    suffix: str = SUFFIX,
) -> str:
    """LoRA fine-tune job başlat."""
    print(f"\n🚀 Fine-tune job başlatılıyor:")
    print(f"   Model: {MODEL}")
    print(f"   Suffix: {suffix}")
    print(f"   Epochs: {epochs}")
    print(f"   Learning rate: {lr}")
    print(f"   Batch size: {batch_size}")
    print(f"   LoRA rank: {DEFAULT_LORA_RANK}")
    print(f"   Train file: {train_file_id}")
    if val_file_id:
        print(f"   Val file: {val_file_id}")

    kwargs = {
        "model": MODEL,
        "training_file": train_file_id,
        "suffix": suffix,
        "n_epochs": epochs,
        "learning_rate": lr,
        "batch_size": batch_size,
        "warmup_ratio": DEFAULT_WARMUP_RATIO,
        "lora": True,
        "lora_r": DEFAULT_LORA_RANK,
        "lora_alpha": DEFAULT_LORA_ALPHA,
        "lora_dropout": DEFAULT_LORA_DROPOUT,
        "n_checkpoints": N_CHECKPOINTS,
        "train_on_inputs": False,  # Sadece assistant (tweet) üzerinde train
    }

    if val_file_id:
        kwargs["validation_file"] = val_file_id
        kwargs["n_evals"] = N_EVALS

    resp = client.fine_tuning.create(**kwargs)
    job_id = resp.id
    output_name = getattr(resp, "output_name", "TBD")

    print(f"\n   ✅ Job oluşturuldu!")
    print(f"   Job ID: {job_id}")
    print(f"   Output model: {output_name}")
    print(f"   Status: {resp.status}")
    print(f"\n   Dashboard: https://api.together.xyz/jobs")

    return job_id


def check_status(client: Together, job_id: str) -> dict:
    """Job durumunu kontrol et."""
    resp = client.fine_tuning.retrieve(id=job_id)

    status = resp.status
    print(f"\n📊 Job Status: {job_id}")
    print(f"   Status: {status}")
    print(f"   Model: {resp.model}")

    if hasattr(resp, "output_name") and resp.output_name:
        print(f"   Output: {resp.output_name}")

    if hasattr(resp, "token_count") and resp.token_count:
        cost = (resp.token_count * 8.0) / 1_000_000
        print(f"   Tokens: {resp.token_count:,}")
        print(f"   Tahmini maliyet: ${max(cost, 16.0):.2f}")

    if hasattr(resp, "events") and resp.events:
        print(f"\n   📝 Son olaylar:")
        for event in resp.events[-5:]:
            msg = getattr(event, "message", str(event))
            print(f"      {msg}")

    return resp


def wait_for_completion(client: Together, job_id: str, poll_interval: int = 30) -> dict:
    """Job bitene kadar bekle."""
    print(f"\n⏳ Job tamamlanması bekleniyor: {job_id}")
    print(f"   Poll interval: {poll_interval}s")

    while True:
        resp = client.fine_tuning.retrieve(id=job_id)
        status = resp.status

        if status in ("completed", "failed", "cancelled"):
            print(f"\n   🏁 Job tamamlandı: {status}")
            if status == "completed":
                print(f"   ✅ Model hazır: {resp.output_name}")
                print(f"   Serverless LoRA inference ile anında kullanılabilir!")
            elif status == "failed":
                print(f"   ❌ Job başarısız!")
                if hasattr(resp, "events") and resp.events:
                    for event in resp.events[-3:]:
                        print(f"      {getattr(event, 'message', str(event))}")
            return resp

        print(f"   [{time.strftime('%H:%M:%S')}] Status: {status}...")
        time.sleep(poll_interval)


# ============================================================
# Test inference
# ============================================================
def test_model(client: Together, model_name: str):
    """Fine-tuned modeli test et."""
    test_prompts = [
        {
            "system": "Sen X (Twitter) platformunda viral içerik üreten bir uzmansın. "
                      "Yüksek etkileşim alan, dikkat çekici ve paylaşılabilir Türkçe tweetler yazıyorsun.",
            "user": "Platform: X (Twitter)\nNiche: tech\nDil: Türkçe\nTon: informative\n"
                    "Hook tipi: bold_claim\nYapı: multi_line\nKonu: yapay zeka gelecegi",
        },
        {
            "system": "You are an expert at creating viral content on X (Twitter). "
                      "You write highly engaging, attention-grabbing, and shareable tweets in English.",
            "user": "Platform: X (Twitter)\nNiche: tech\nLanguage: English\nTone: conversational\n"
                    "Hook type: question\nStructure: short_punch\nTopic: AI startups",
        },
        {
            "system": "Sen X (Twitter) platformunda viral içerik üreten bir uzmansın.",
            "user": "Platform: X (Twitter)\nNiche: pazarlama\nDil: Türkçe\nTon: motivational\n"
                    "Hook tipi: story\nYapı: standard\nKonu: girişimcilik dersleri",
        },
    ]

    print(f"\n🧪 Model Test: {model_name}")
    print("=" * 60)

    for i, prompt in enumerate(test_prompts, 1):
        print(f"\n--- Test {i} ---")
        print(f"User: {prompt['user'][:100]}...")

        try:
            resp = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": prompt["system"]},
                    {"role": "user", "content": prompt["user"]},
                ],
                max_tokens=512,
                temperature=0.8,
                top_p=0.9,
            )
            content = resp.choices[0].message.content
            print(f"Assistant:\n{content}")
            print(f"Tokens: {resp.usage.total_tokens}")
        except Exception as e:
            print(f"❌ Hata: {e}")

        print()


# ============================================================
# Full pipeline
# ============================================================
def full_pipeline(
    client: Together,
    train_path: str,
    val_path: str | None = None,
    epochs: int = DEFAULT_EPOCHS,
    lr: float = DEFAULT_LR,
    batch_size: int = DEFAULT_BATCH_SIZE,
    suffix: str = SUFFIX,
    wait: bool = True,
):
    """Tüm adımları tek seferde çalıştır."""
    print("🚀 Type Hype Fine-tuning Full Pipeline")
    print("=" * 60)

    # 1. Check files
    print("\n📋 Adım 1: Dosya kontrolü")
    if not check_file_local(train_path):
        sys.exit("❌ Train dosyası format kontrolünden geçemedi!")

    # 2. Upload files
    print("\n📋 Adım 2: Dosya yükleme")
    train_file_id = upload_file(client, train_path)

    val_file_id = None
    if val_path and Path(val_path).exists():
        val_file_id = upload_file(client, val_path)

    # 3. Create fine-tune job
    print("\n📋 Adım 3: Fine-tune job oluşturma")
    job_id = create_finetune(
        client,
        train_file_id,
        val_file_id,
        epochs=epochs,
        lr=lr,
        batch_size=batch_size,
        suffix=suffix,
    )

    # 4. Wait & test
    if wait:
        print("\n📋 Adım 4: Tamamlanma bekleniyor")
        result = wait_for_completion(client, job_id)

        if result.status == "completed" and hasattr(result, "output_name"):
            print("\n📋 Adım 5: Model testi")
            test_model(client, result.output_name)
    else:
        print(f"\n📋 Job arka planda çalışıyor: {job_id}")
        print(f"   Kontrol: python together_finetune.py status --job-id {job_id}")

    # Save job info
    info = {
        "job_id": job_id,
        "model": MODEL,
        "train_file_id": train_file_id,
        "val_file_id": val_file_id,
        "epochs": epochs,
        "lr": lr,
        "batch_size": batch_size,
        "suffix": suffix,
        "lora_rank": DEFAULT_LORA_RANK,
    }
    info_path = Path(train_path).parent / "finetune_job_info.json"
    with open(info_path, "w") as f:
        json.dump(info, f, indent=2)
    print(f"\n📄 Job bilgileri: {info_path}")


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Type Hype Together AI Fine-tuning")
    sub = parser.add_subparsers(dest="command", required=True)

    # upload
    p_upload = sub.add_parser("upload", help="Dosyaları yükle")
    p_upload.add_argument("--train", required=True, help="Train JSONL dosyası")
    p_upload.add_argument("--val", help="Validation JSONL dosyası")

    # train
    p_train = sub.add_parser("train", help="Fine-tune job başlat")
    p_train.add_argument("--train-file-id", required=True)
    p_train.add_argument("--val-file-id")
    p_train.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    p_train.add_argument("--lr", type=float, default=DEFAULT_LR)
    p_train.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    p_train.add_argument("--suffix", default=SUFFIX)

    # status
    p_status = sub.add_parser("status", help="Job durumu")
    p_status.add_argument("--job-id", required=True)
    p_status.add_argument("--wait", action="store_true", help="Bitene kadar bekle")

    # test
    p_test = sub.add_parser("test", help="Model test")
    p_test.add_argument("--model", required=True, help="Fine-tuned model adı")

    # full
    p_full = sub.add_parser("full", help="Tüm pipeline (upload → train → wait → test)")
    p_full.add_argument("--train", required=True)
    p_full.add_argument("--val")
    p_full.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    p_full.add_argument("--lr", type=float, default=DEFAULT_LR)
    p_full.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    p_full.add_argument("--suffix", default=SUFFIX)
    p_full.add_argument("--no-wait", action="store_true")

    # list
    sub.add_parser("list", help="Tüm fine-tune job'ları listele")

    args = parser.parse_args()
    load_env()

    api_key = os.environ.get("TOGETHER_API_KEY", "")
    if not api_key:
        sys.exit("❌ TOGETHER_API_KEY gerekli. .env'e veya ortam değişkenine ekle.")

    client = Together(api_key=api_key)

    if args.command == "upload":
        check_file_local(args.train)
        train_id = upload_file(client, args.train)
        print(f"\n   Train file ID: {train_id}")
        if args.val:
            check_file_local(args.val)
            val_id = upload_file(client, args.val)
            print(f"   Val file ID: {val_id}")

    elif args.command == "train":
        create_finetune(
            client,
            args.train_file_id,
            args.val_file_id,
            epochs=args.epochs,
            lr=args.lr,
            batch_size=args.batch_size,
            suffix=args.suffix,
        )

    elif args.command == "status":
        if args.wait:
            wait_for_completion(client, args.job_id)
        else:
            check_status(client, args.job_id)

    elif args.command == "test":
        test_model(client, args.model)

    elif args.command == "full":
        full_pipeline(
            client,
            args.train,
            args.val,
            epochs=args.epochs,
            lr=args.lr,
            batch_size=args.batch_size,
            suffix=args.suffix,
            wait=not args.no_wait,
        )

    elif args.command == "list":
        jobs = client.fine_tuning.list()
        if not jobs.data:
            print("Henüz job yok.")
        else:
            for job in jobs.data:
                print(f"  {job.id} | {job.status} | {job.model} | {getattr(job, 'output_name', 'N/A')}")


if __name__ == "__main__":
    main()
