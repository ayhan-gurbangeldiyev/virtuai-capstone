# Faz 2 (LangGraph durability) — PROD Deploy Runbook

**Amaç:** LangGraph Faz 2 kodunu prod'a (`root@46.225.27.85:/opt/hype-crew`) deploy et.
**Flag durumu:** `HYPE_LANGGRAPH_ENABLED` **OFF kalır** → deploy *inert* (saf CrewAI yolu çalışır).
**Kaynak:** `main` @ `8035493` (PR#62). **Phoenix deploy EDİLMEZ** (o `feat/phoenix-observability`'de, server hazır değil).

> Bu deploy, flag OFF olsa bile canlı CrewAI yolundaki dosyaları (`flow.py`, `runner.py`,
> `config.py`, `supabase_logger.py`) değiştirir. "Always-on" değişikliklerin CrewAI-yolu-güvenli
> olduğu aşağıda KANITLANDI. Yine de prod-drift kontrolü (STEP 0) zorunlu kapıdır.

---

## Deploy edilecek dosyalar (main vs son-LangGraph-öncesi delta)

| Dosya | Tür | Not |
|---|---|---|
| `hype_crew/lg/` (paket: `__init__`,`graph`,`nodes`,`checkpointer`,`card_graph`,`.gitignore`) | YENİ | Flag OFF iken hiç import edilmez (runner.py:97 gate) |
| `hype_crew/flow.py` | DEĞİŞ | +466 satır; Postiz write-ahead flag-gated, idempotency always-on (güvenli, aşağıda) |
| `hype_crew/runner.py` | DEĞİŞ | +124; langgraph branch flag-gated, reaper koordinasyonu always-on |
| `hype_crew/config.py` | DEĞİŞ | +14; saf ekleme (langgraph_enabled, checkpoint_db_url; default OFF/boş) |
| `hype_crew/callbacks/supabase_logger.py` | DEĞİŞ | +67; init_run resume yolu `if run_id:` gate'li, log_stage upsert always-on |
| `hype_crew/requirements.txt` | DEĞİŞ | +10 langgraph deps (psycopg/checkpoint-postgres/sqlite). **Phoenix satırları main'de YOK.** |

Migration `025`/`026`: **prod'a zaten uygulandı** (additive, 6h+ canlı CrewAI'yı bozmadı) → deploy'da tekrar YOK.

---

## Always-on güvenlik denetimi (flag OFF iken canlı CrewAI'da etkisi)

Flag-OFF iken bile yürürlükte olan değişiklikler ve her birinin CrewAI-yolu-güvenli kanıtı:

| Değişiklik | Always-on? | CrewAI yolunda davranış | Kanıt |
|---|---|---|---|
| `init_run(run_id=…)` resume yolu | Hayır (gate'li) | `flow.py:525 preset_run_id = state.run_id or None`. CrewAI runner langgraph branch'ine GİRMEZ (runner.py:97) → `state.run_id` ön-set EDİLMEZ → `run_id=None` → **legacy yol = byte-identical** | flow.py:520-532, runner.py:97 |
| `log_stage` upsert | Evet | `on_conflict=(run_id,stage_order)`. CrewAI'da stage'ler tekil → conflict yok → **insert gibi davranır**. Constraint `uq_hype_stages_run_order` (025) prod'da CANLI | supabase_logger.py:179-194 |
| `_write_daily_draft` idempotency SELECT | Evet | `_run_id_for_idem = state.run_id` (CrewAI'da DB-minted id dolu). Taze run'da SELECT **boş döner** → INSERT'e devam. +1 SELECT/draft (ihmal edilebilir), davranış no-op | flow.py:3683 |
| `_write_daily_draft` 23505 handler | Evet | Yalnız gerçek unique-violation'da tetiklenir; canlı index'in (025/026) companion'ı. Normal akışta hiç çalışmaz | flow.py 23505 bloğu |
| Postiz write-ahead (SCHEDULING sentinel) | **Hayır (gate'li)** | `_lg_resume_safety = bool(settings.langgraph_enabled)` → flag OFF iken **tamamen atlanır** | flow.py:4520 |
| `reap_orphan_drafts` / `_reap_stuck_runs` | Evet | Yalnız >2h takılı 'running' run'ları reap eder; checkpoint'li (<2h) satırı korur. CrewAI stuck-run temizliği zaten vardı, mantık aynı | runner.py:9-90 |

**Sonuç:** Yan-etki üreten her değişiklik (Postiz write-ahead, LangGraph branch) flag-gate'li. Always-on
olanlar (idempotency SELECT, log_stage upsert, init_run legacy) ya byte-identical ya da no-op/insert-eşdeğeri,
ve bağımlı oldukları constraint'ler prod'da zaten canlı + sorunsuz. **Deploy inert.**

---

## ✅ STEP 0 SONUCU (2026-06-14 yürütüldü — KAPI GEÇTİ)
- Prod manifest: `29caad7` (8 Haz) ama **bayat** — sonradan manifest'siz scp-deploy yapılmış.
- **Prod ≠ pristine CrewAI: prod'da Faz1 LangGraph kodu CANLI ama DORMANT** (lg/ paketi var; flow.py/runner.py
  Faz1 state-field'ları + Faz1 langgraph branch). `HYPE_LANGGRAPH_ENABLED` .env'de SET DEĞİL → flag OFF →
  CrewAI çalışıyor (son 24h'de 0 "LangGraph yolu" log'u). `HYPE_CHECKPOINT_DB_URL` ekli.
- **Karşılaştırma:** config.py **prod==main** (identical); supabase_logger.py prod=eski(29caad7); flow.py/runner.py
  prod=Faz1 (dc92d8c base'den 56/32 satır ileri, hepsi LangGraph Faz1 kodu — main'in Faz2'si üst-küme).
- **PROD-ONLY HOTFIX YOK** → backport gerekmez. Deploy = dormant Faz1'i Faz2'ye yükseltmek (flag OFF kalır,
  dormant→dormant). Always-on değişiklikler (supabase_logger upsert, flow idempotency) CrewAI yoluna eklenir
  (yukarıdaki denetim TEMİZ).
- **Rollback yedeği prod'un MEVCUT Faz1 halini yakalamalı** (STEP 2 öncesi tar) → bilinen-iyi dormant-Faz1+CrewAI.

---

## STEP 0 — Prod-drift kapısı (ZORUNLU, read-only) ⚠️ kullanıcı onayı gerekir

> Geçmişte prod scp-deploy ile git'ten İLERİ çıkmıştı (prod-only hotfix). Bu deploy o dosyaları
> ezeceği için, deploy'dan ÖNCE prod-disk vs niyetlenen-kod farkını görmek ŞART.

```bash
# 1) Prod'un deployed-manifest'i + disk md5'leri (baseline = manifest, prod-git DEĞİL)
ssh root@46.225.27.85 'cat /opt/contentfactory/.deployed_manifest.json' | python3 -m json.tool
ssh root@46.225.27.85 'cd /opt/hype-crew && md5sum flow.py runner.py config.py callbacks/supabase_logger.py'

# 2) Lokal (main) karşılığı — karşılaştır
git -C . show main:hype_crew/flow.py | md5; # vb. her dosya için
```
- Manifest commit'i `main`'in nesi? Prod disk md5'leri manifest md5'leriyle eşleşiyor mu (install-vs-restart drift yok)?
- Eğer prod disk md5 ≠ manifest md5 → prod'da deploy-sonrası elle dokunulmuş dosya var → **diff al, prod-only fix'i main'e backport et, SONRA deploy.**
- lg/ paketi prod'da yoksa (beklenen): temiz ekleme.

---

## STEP 1 — Cron'u durdur (kör-run penceresini sıfırla) ⚠️ onay

```bash
ssh root@46.225.27.85 'systemctl stop hype-crew.timer'   # çalışan run varsa bitmesini bekle
ssh root@46.225.27.85 'systemctl is-active hype-crew.service'  # 'inactive' olmalı
```

## STEP 2 — Dosyaları gönder ⚠️ onay
> ÇİFT-PREFIX TUZAĞI (critic): repo kökünden `--relative hype_crew/lg` → `/opt/hype-crew/hype_crew/lg`
> (YANLIŞ). Doğru: ÖNCE `hype_crew/`'e cd, sonra -R ile hype_crew-relative path'ler:
```bash
cd /Users/berkay/.openclaw/workspace/ContentFactory/hype_crew
# 1) kuru-çalıştır (yazmaz) — lg/ ve dosyaların /opt/hype-crew/'in İÇİNE düştüğünü gör:
rsync -aRn --delete-missing-args \
  lg flow.py runner.py config.py callbacks/supabase_logger.py requirements.txt \
  root@46.225.27.85:/opt/hype-crew/ | grep -E "lg/|flow.py|supabase_logger" | head
# 2) gerçek gönderim (-R hype_crew-relative path'leri korur → /opt/hype-crew/{lg,flow.py,callbacks/...}):
rsync -aR --delete lg \
  flow.py runner.py config.py callbacks/supabase_logger.py requirements.txt \
  root@46.225.27.85:/opt/hype-crew/
# NOT: --delete YALNIZ lg/ ağacına etki etsin diye lg ayrı; tek dosyalar zaten üzerine yazılır.
```

### STEP 2-GATE (critic) — rsync sonrası path doğrula (çift-prefix riski)
```bash
ssh root@46.225.27.85 'ls /opt/hype-crew/lg/graph.py /opt/hype-crew/lg/checkpointer.py /opt/hype-crew/lg/nodes.py /opt/hype-crew/callbacks/supabase_logger.py'
# Hepsi GÖRÜNMELİ. /opt/hype-crew/hype_crew/... olursa = çift-prefix → DUR, rsync düzelt.
```

## STEP 3 — Deps kur (ZORUNLU — yoksa ExecStartPre smoke patlar, servis başlamaz) ⚠️ onay
```bash
ssh root@46.225.27.85 'cd /opt/hype-crew && venv/bin/pip install -r requirements.txt 2>&1 | tee /tmp/pip_faz2.log | tail -5'
ssh root@46.225.27.85 'cd /opt/hype-crew && venv/bin/pip check'   # TEMİZ olmalı
```
### STEP 3-GATE (critic, ATLAMA) — flag-bağımsız dep doğrulama
> smoke STEP6 checkpointer probe flag-OFF iken SKIP eder → kırık langgraph/psycopg dep'i smoke'u GEÇER
> ama flag açılınca çöker. Bu kontrol o kör noktayı kapatır (flag bağımsız):
```bash
ssh root@46.225.27.85 'cd /opt/hype-crew && venv/bin/python -c "import psycopg, psycopg_pool, langgraph; from lg.checkpointer import sync_checkpointer; print(\"DEP OK\")"'
# "DEP OK" yazmazsa → DUR (prod Python ≠ yerel 3.13 ise psycopg binary wheel eksik olabilir).
```

## STEP 4 — Manifest yaz (drift baseline güncelle)
```bash
ssh root@46.225.27.85 'cd /opt/contentfactory && python3 -m scripts.write_deploy_manifest'  # path teyit et
```

## STEP 5 — Smoke (deploy gate) + manual dry-run + restart ⚠️ onay
```bash
# 5a) smoke (ExecStartPre ile aynı gate):
ssh root@46.225.27.85 'cd /opt/hype-crew && venv/bin/python -m scripts.smoke_test_flow'  # STEP 1-6 PASS şart
```
### STEP 5-GATE (critic, cron start'tan ÖNCE) — tek manuel CrewAI run, constraint izle
> Always-on değişiklikler (log_stage upsert, idempotency SELECT) CANLI CrewAI'da İLK kez koşar.
> Beklenmedik Supabase constraint/tip hatasını cron başlamadan yakala:
```bash
ssh root@46.225.27.85 'cd /opt/hype-crew && HYPE_DRY_RUN=true timeout 600 venv/bin/python -m runner 2>&1 | tail -30'
ssh root@46.225.27.85 'journalctl -u hype-crew --since "10 min ago" --no-pager | grep -E "ERROR|23505|42703|constraint" || echo "constraint hatası YOK"'
# 23505/42703/constraint görünürse → cron'u KAPALI bırak, düzelt. Temizse devam:
ssh root@46.225.27.85 'systemctl start hype-crew.timer && systemctl status hype-crew.timer --no-pager'
```

## STEP 6 — Inert doğrulama (deploy sonrası ilk CrewAI run'ı izle)
- `.env`'de `HYPE_LANGGRAPH_ENABLED` **set DEĞİL / false** olduğunu teyit et (`grep -i langgraph /opt/hype-crew/.env`).
- İlk cron run'ı: `journalctl -u hype-crew.service -f` → normal CrewAI akışı, `[Runner] LangGraph` log'u **GÖRÜNMEMELİ**.
- Supabase: yeni `hype_runs` satırı normal (DB-minted id), `hype_stages` tek satır/stage, `daily_drafts` unique-violation YOK.

---

## Rollback (deploy ters giderse)
> Flag-OFF rollback'i İŞE YARAMAZ (sorun deploy'un kendisinde, flag zaten OFF).

```bash
# Hızlı: önceki dosyaları geri yükle (deploy öncesi prod kopyalarını /opt/hype-crew/.bak'a al!)
# STEP 2'den ÖNCE: ssh root@46.225.27.85 'cd /opt/hype-crew && tar czf /root/hype-crew-pre-faz2.tgz flow.py runner.py config.py callbacks/supabase_logger.py'
ssh root@46.225.27.85 'systemctl stop hype-crew.timer'
ssh root@46.225.27.85 'cd /opt/hype-crew && tar xzf /root/hype-crew-pre-faz2.tgz'   # geri yükle
ssh root@46.225.27.85 'cd /opt/hype-crew && venv/bin/python -m scripts.smoke_test_flow && systemctl start hype-crew.timer'
```
> **STEP 2'den önce pre-faz2 yedeği almak rollback'in ön-koşuludur.** Runbook'a eklendi.

---

## Sonraki adımlar (deploy SONRASI, ayrı pencere)
1. prod-dry uçtan-uca + prod-dry kill-resume (Faz 2 kodu aktif, gerçek altyapı) — flag yine OFF, manuel tetik.
2. Phoenix server online (gözetimsiz genişlemeden önce; `feat/phoenix-observability` merge + Hetzner collector).
3. Alert→Slack teyidi + reconcile runbook + rollback drill.
4. Per-account flag wire → İLK FLAG-ON (tek manuel, cron durdurulmuş, video OFF, izlenen) → soak → cutover.
