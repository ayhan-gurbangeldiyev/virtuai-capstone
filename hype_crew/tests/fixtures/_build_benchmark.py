"""Build the faithfulness benchmark JSONL.

Two parts:
  • 25 gold-seed cases — encoded directly from the Phase 0 audit (the
    real fabrications + overreaches + grounded passes Berkay flagged
    on the X/Cansu DUT account on 2026-06-03/04/05). Sources are the
    actual `trends.raw_content` rows queried from Supabase, IDs are
    cross-referenced in the `audit_trend_id` field.
  • 125 synthetic cases — programmatically derived from real grounded
    sources to stress the gate:
      - hard_negative (≥40): grounded source + ONE injected fabrication
      - hard_positive (≥85): grounded source + paraphrase / suffix /
        alias / strong opinion (most valuable — the false-positive
        stress test the gate must NOT block)

Total: ≥150 cases, ≥50 grounded labels (gold 7 + ~50 hard_positive).

Run:   python3 hype_crew/tests/fixtures/_build_benchmark.py
Output: hype_crew/tests/fixtures/faithfulness_benchmark.jsonl
"""
from __future__ import annotations
import json
import os
import random
from pathlib import Path

random.seed(20260606)

HERE = Path(__file__).resolve().parent
OUT = HERE / "faithfulness_benchmark.jsonl"


# ──────────────────────────────────────────────────────────────────────
# 25 GOLD SEED — Phase 0 audit, verbatim categories
# ──────────────────────────────────────────────────────────────────────

GOLD: list[dict] = []


def gold(case_id, label, src, draft, *, ungrounded=None, category, trend_id=None,
         url=None, note="", regression_known_gap=False):
    GOLD.append({
        "id": case_id, "label": label, "category": category,
        "source_raw_content": src.strip(),
        "source_url": url,
        "draft_text": draft.strip(),
        "ungrounded_spans": ungrounded or [],
        "gold": True, "phase0_audit": True,
        "audit_trend_id": trend_id,
        "regression_known_gap": bool(regression_known_gap),
        "note": note,
    })


# ── FABRICATIONS (12) — concrete entity / number / event invented ──────

gold(
    "gold-01-starlink-fabrication", "fabrication",
    "Google, artan yapay zeka talebini karşılamak için SpaceX ile aylık 920 milyon dolarlık işlem gücü anlaşması imzaladı.",
    "Google'ın SpaceX ile $920M aylık anlaşması — asıl hikaye Starlink üzerinden veri merkezlerine fiziksel uplink kurmak. Bu sadece compute alımı değil, jeo-stratejik bir hamle.",
    ungrounded=["Starlink", "fiziksel uplink"],
    category="entity_fabrication", trend_id="4c5e5458-8c31-440a-9b1e-3e285ce805e1",
    note="Phase 0: Starlink kaynakta YOK; Google–SpaceX compute deal'i Starlink ağıyla karıştırıldı.",
)
gold(
    "gold-02-recursive-self-improvement-contradiction", "fabrication",
    "None of this guarantees recursive self-improvement is on the horizon. It's not yet clear that Claude is capable of research judgment—of choosing the right problems to work on.",
    "Anthropic'in son Opus güncellemesi recursive self-improvement eşiğini geçti — artık model kendi araştırma problemlerini seçebiliyor. Eşik aşıldı.",
    ungrounded=["recursive self-improvement eşiğini geçti", "kendi araştırma problemlerini seçebiliyor"],
    category="source_contradiction", trend_id="47a8798f-828d-42e2-b7b4-1760839b48a9",
    url="https://x.com/AnthropicAI/status/2062568873321513443",
    note="Phase 0: kaynak AÇIKÇA 'is NOT on the horizon' diyor — draft tersini iddia ediyor.",
)
gold(
    "gold-03-cve-fabrication", "fabrication",
    "Meta AI'daki bir açık, kötü niyetli kişilerin bazı Instagram hesaplarını devralmasına yol açtı. Saldırganlar, destek botundan hedef hesaba yeni bir e-posta eklemesini istedi.",
    "Meta AI Instagram açığı CVE-2026-48095 olarak kaydedildi. Yapay zekâ destek botu üzerinden hesap ele geçirme — kritik güvenlik açığı.",
    ungrounded=["CVE-2026-48095"],
    category="specific_id_fabrication", trend_id="2dd07abb-e4ed-4e94-8e4d-15f2adecb84b",
    note="Phase 0: kaynakta CVE numarası YOK. Llm uydurdu.",
)
gold(
    "gold-04-llama3-injection", "fabrication",
    "Yapay zekâ botu, Instagram hesaplarının çalınmasına yardım etti! Meta AI'daki bir açık, kötü niyetli kişilerin bazı Instagram hesaplarını devralmasına yol açtı.",
    "Meta'nın Llama 3 tabanlı destek asistanı Instagram hesap devralma saldırısının kaynağı oldu. Llama 3'ün destek otomasyonu prompt injection açığı verdi.",
    ungrounded=["Llama 3", "Llama 3 tabanlı"],
    category="entity_fabrication", trend_id="2dd07abb-e4ed-4e94-8e4d-15f2adecb84b",
    note="Phase 0: kaynakta Llama 3 YOK. 'Meta AI' soyutlaması Llama 3 olarak somutlaştırıldı.",
)
gold(
    "gold-05-iphone-battery-number", "fabrication",
    "Apple, iPhone 18 Pro modelinde bölgesel batarya stratejisi uyguluyor.",
    "iPhone 18 Pro %23 daha büyük batarya ile geliyor — Çin modeli 5400 mAh, ABD modeli 4800 mAh. Apple'ın bölgesel strateji rekabette ezber bozuyor.",
    ungrounded=["%23 daha büyük", "5400 mAh", "4800 mAh"],
    category="numeric_fabrication", trend_id="9170e2ff-bf9c-43b0-b090-3e1065d508a7",
    note="Phase 0: kaynak sadece 'bölgesel batarya stratejisi' diyor. Sayılar uyduruldu.",
)
gold(
    "gold-06-spacex-ipo-overstate", "fabrication",
    "12 Haziran'da tüm zamanların en büyük halka arzını gerçekleştirecek SpaceX'in hisse fiyatı açıklandı. SpaceX'in hisse fiyatının 135 dolar olacağı açıklandı.",
    "SpaceX 12 Haziran'da $135'tan IPO. Şirket değerlemesi $850 milyar, Tesla'yı geçti.",
    ungrounded=["$850 milyar", "Tesla'yı geçti"],
    category="numeric_fabrication", trend_id="f9537323-788f-40bc-ae79-b03fddbe80fb",
    note="Phase 0: kaynakta değerleme YOK, sadece hisse fiyatı.",
)
gold(
    "gold-07-mythos-benchmark-fabrication", "fabrication",
    "Anthropic, Claude Mythos Preview modeli ile bir ayda 10 binden fazla kritik güvenlik açığı tespit ettiğini duyurdu.",
    "Claude Mythos SWE-Bench Verified'de %78.3 skor ile yeni SOTA. Ayrıca MMLU'da Opus 4.8'i geçti.",
    ungrounded=["SWE-Bench Verified", "%78.3", "MMLU", "Opus 4.8'i geçti"],
    category="benchmark_fabrication", trend_id="f530cc49-fc2c-4f43-9a4a-342cb24cb431",
    note="Phase 0: benchmark adı + skor uyduruldu.",
)
gold(
    "gold-08-google-deepmind-substitution", "fabrication",
    "Google, doğaya 32 milyon 'özel' erkek sivrisinek salmaya hazırlanıyor. Süreç onaylanırsa ABD'de Kaliforniya ve Florida'da milyonlarca laboratuvar üretimi erkek sivrisinek doğaya bırakılacak.",
    "Google DeepMind, AlphaFold sayesinde 32 milyon CRISPR sivrisinek üretti. Bu, sentetik biyolojinin Google'ın AI altyapısıyla buluştuğu ilk vaka.",
    ungrounded=["DeepMind", "AlphaFold", "CRISPR"],
    category="entity_fabrication", trend_id="28f9cb58-eca5-4455-aefb-37875c9d612c",
    note="Phase 0: kaynakta DeepMind/AlphaFold/CRISPR YOK; Google Verily projesinin AI projesi olarak yeniden çerçevelenmesi.",
)
gold(
    "gold-09-meta-limitless-acquisition-date", "fabrication",
    "Meta, 2025 sonunda satın aldığı Limitless teknolojisiyle yeni bir yapay zeka destekli kolye ve giyilebilir cihazlar üzerinde çalışıyor.",
    "Meta, 2024 başında satın aldığı Limitless'i $1.2 milyara aldı ve bu yıl 100 milyon kullanıcı hedefliyor.",
    ungrounded=["2024 başında", "$1.2 milyara", "100 milyon kullanıcı"],
    category="date_and_numeric_fabrication", trend_id="2b9d6412-b91c-48f8-9adf-07c3f85c5926",
    note="Phase 0: tarih ve sayılar uydurma.",
)
gold(
    "gold-10-gemini-quota-numeric", "fabrication",
    "Google, gelen şikayetler üzerine Gemini uygulamasındaki kullanım limitlerini güncelledi. Yeni kota sistemi, ücretsiz model seçenekleri ve Omni güncellemelerinin tüm detayları haberimizde.",
    "Gemini ücretsiz kotası 50'den 200 mesaj/güne çıktı. Omni model artık 1M token context destekliyor.",
    ungrounded=["50'den 200 mesaj/güne", "1M token context"],
    category="numeric_fabrication", trend_id="21246c84-6eb0-41be-b55f-686be71ab61c",
)
gold(
    "gold-11-starship-orbit-fabrication", "fabrication",
    "SpaceX, üçüncü nesil Starship V3 roketini ilk kez test uçuşuna çıkardı. Uzaya ulaşan roketin detayları ve testin sonuçları haberimizde.",
    "Starship V3 ilk yörünge testini başardı — 250 km yörüngede Starlink uydularını bıraktı. Tam re-use başarısı.",
    ungrounded=["250 km yörüngede", "Starlink uydularını bıraktı", "Tam re-use"],
    category="event_fabrication", trend_id="78b72d20-485b-40ff-9c9e-47697f744a83",
)
gold(
    "gold-12-claude-opus-speedup-attribution", "fabrication",
    "Correction: Claude Opus 4's ~3x average speedup dates to May 2025, not May 2024.",
    "Claude Opus 4.8, GPU başına 8x throughput iyileşmesi getirdi. NVIDIA H200'lerde tam optimizasyon.",
    ungrounded=["GPU başına 8x throughput", "NVIDIA H200"],
    category="numeric_fabrication", trend_id="27e5f5cd-0e45-459a-80ed-1dd7559f3697",
)
# Added 2026-06-06 from shadow_backfill audit (FN-16). A real-world recall
# gap surfaced by Phase-6 shadow logging: source attributes the assistant
# to "Google Gemini destekli yeni Siri", draft silently substitutes "Apple
# Intelligence" — a different AI brand. Pre-fix gate passed this.
# Added 2026-06-06 from real-world approve_thread failure on the 3 Meta-AI
# video drafts. The Instagram caption ended in "#MetaAI #YapayZeka …"; GLiNER
# extracted the hashtag "MetaAI" as a distinct entity. The source had
# "Meta'nın yeni yapay zeka asistanı" but not the concatenated form "MetaAI",
# so T0 over-blocked a clearly-grounded caption. Fix: added the concatenated
# "metaai" / "meta-ai" / "meta ai" forms to meta's alias-set. This case
# locks the fix in so a future alias-map regression resurfaces immediately.
gold(
    "gold-27-meta-ai-hashtag-concat", "grounded",
    "Meta'nın yeni yapay zeka asistanı, karmaşık analiz ekranlarını sohbet ekranına taşıyor. İçerik üreticileri artık performans verilerini grafiklerde boğulmadan inceleyebilecek.",
    "Meta'nın yeni yapay zeka asistanı analiz ekranlarını sohbete taşıyor. Grafik yerine soru soruyorsun, içgörü geliyor.\n\n#MetaAI #YapayZeka #IcerikUretici #SosyalMedya #Analiz #Meta",
    category="grounded_hashtag_concat",
    url="https://x.com/webtekno/status/2062957751056158735",
    note="Surfaced from the 2026-06-06 approve_thread failure on Meta-AI video Instagram caption (a7b3234b). Concatenated brand+AI form ('MetaAI') in a hashtag should not register as a novel entity.",
)
gold(
    "gold-26-apple-intelligence-vs-gemini-substitution", "fabrication",
    "Apple'ın yeni Apple TV ve HomePod Mini modellerini Eylül ayında çıkaracağı iddia ediliyor. Cihazların Google Gemini destekli yeni Siri ile gelmesi bekleniyor.",
    "Herkes Apple yeni HomePod ve Apple TV ile donanım satacak sanıyor ama olay bambaşka. Apple Intelligence için her odaya fiziksel bir kulak yerleştiriyorlar. Bu bir cihaz güncellemesi değil resmen evdeki agent arayüzü alanını kapatma savaşı.",
    ungrounded=["Apple Intelligence"],
    category="entity_substitution_fabrication",
    trend_id="(shadow_backfill_audit)",
    url="https://x.com/shiftdeletenet/status/2061357078967681412",
    regression_known_gap=True,
    note="Source attributes the new Siri to Google Gemini; draft substitutes Apple Intelligence. Different AI brands. Surfaced in 2026-06-06 shadow backfill as FN-16. KNOWN RECALL GAP — current gate passes this; tracked separately so CI's 'calibrated recall' stays valid until the gate is updated to catch entity-substitution.",
)


# ── OVERREACH (6) — source-supported core but draft extrapolates beyond ─

gold(
    "gold-13-meta-ai-asistan-overreach", "overreach",
    "Meta'nın yeni yapay zeka asistanı, karmaşık analiz ekranlarını sohbet ekranına taşıyor. İçerik üreticileri artık performans verilerini grafiklerde boğulmadan inceleyebilecek ve doğal dilde sorular sorarak anında içgörü alabilecek.",
    "Meta'nın yeni AI asistanı creator ekonomisinin son halkasını da kapadı. Artık dashboard yok, sohbet var — bu, BÜTÜN performance marketing endüstrisi için exit signal.",
    ungrounded=["creator ekonomisinin son halkası", "bütün performance marketing endüstrisi için exit signal"],
    category="generalization_overreach", trend_id="5635ee82-ff8c-4784-a1b5-0cc0fadbbfed",
)
gold(
    "gold-14-reels-series-overreach", "overreach",
    "Meta, Instagram ve Facebook Reels için 'Series' adlı yeni bir özelliği test ediyor. Bu özellik, içerik üreticilerinin aynı konu etrafındaki Reels videolarını bölümler hâlinde bir araya getirmesini sağlayacak.",
    "Meta Series ile YouTube'a doğrudan saldırı başlattı — uzun-form video savaşının ikinci raundu.",
    ungrounded=["YouTube'a doğrudan saldırı", "uzun-form video savaşının ikinci raundu"],
    category="framing_overreach", trend_id="f6e451d4-b601-43f7-acd0-2c7daac0be12",
)
gold(
    "gold-15-mythos-overreach", "overreach",
    "Anthropic, Claude Mythos Preview modeli ile bir ayda 10 binden fazla kritik güvenlik açığı tespit ettiğini duyurdu.",
    "Claude Mythos güvenlik araştırmacılarının %40'ını işsiz bıraktı. Bug bounty programları artık AI'a karşı.",
    ungrounded=["güvenlik araştırmacılarının %40'ını işsiz bıraktı", "bug bounty programları artık AI'a karşı"],
    category="market_impact_overreach", trend_id="f530cc49-fc2c-4f43-9a4a-342cb24cb431",
)
gold(
    "gold-16-singapore-overreach", "overreach",
    "We're expanding our partnership with Singapore to help safely deploy AI at scale. Together with country experts, our new programs will focus on accelerating scientific discovery, advancing pandemic preparedness, and improving healthcare.",
    "Google'ın Singapur ortaklığı aslında ASEAN'ın AI başkenti seçiminin habercisi. Bu, Çin'in bölgedeki AI etkisine karşı doğrudan bir blok kurma hamlesi.",
    ungrounded=["ASEAN'ın AI başkenti seçimi", "Çin'in bölgedeki AI etkisine karşı blok kurma"],
    category="geopolitical_overreach", trend_id="43aa4fba-fe4b-4554-83c0-23e7ddc942c0",
    url="https://x.com/GoogleDeepMind/status/2057985225100235022",
)
gold(
    "gold-17-synthid-overreach", "overreach",
    "SynthID, our imperceptible watermark for AI-generated content, is expanding to more partners. We're also adding new ways to find out if content was generated using AI - just ask in the GeminiApp or in Google Search.",
    "SynthID artık deepfake savaşının kazananı — Google bu watermark'la sektörün de-facto standardını kurdu.",
    ungrounded=["deepfake savaşının kazananı", "sektörün de-facto standardını"],
    category="market_impact_overreach", trend_id="91df7584-9451-46d6-8e7b-10edeeba7c99",
    url="https://x.com/GoogleDeepMind/status/2057898089621459434",
)
gold(
    "gold-18-ad-formats-overreach", "overreach",
    "We're testing new ad formats in Search and expanding our Direct Offers pilot.",
    "Google'ın yeni reklam formatları, AI Overview'ın monetizasyon başarısızlığına son verme hamlesi. Search Ads $200B pazarı krize girdi.",
    ungrounded=["AI Overview'ın monetizasyon başarısızlığı", "Search Ads $200B pazarı krize girdi"],
    category="market_impact_overreach", trend_id="f569e3de-dca6-40e0-b36f-9aa2b7bc3042",
)


# ── GROUNDED (7) — should PASS ─────────────────────────────────────────

gold(
    "gold-19-opus48-grounded", "grounded",
    "Introducing Claude Opus 4.8: it builds on Opus 4.7 with sharper judgment, more honesty about its own progress, and the ability to work independently for longer than its predecessors. Available today at the same price.",
    "Anthropic Claude Opus 4.8'i duyurdu: Opus 4.7'nin üzerine inşa edilmiş, daha keskin yargı + kendi ilerlemesi konusunda daha dürüst + daha uzun süre bağımsız çalışabilen bir model. Aynı fiyat seviyesi.",
    category="grounded_factual", trend_id="17271453-22bc-420c-bd8f-3e63bc0eb9b4",
    url="https://x.com/claudeai/status/2060042702150930686",
)
gold(
    "gold-20-google-spacex-grounded", "grounded",
    "Google, artan yapay zeka talebini karşılamak için SpaceX ile aylık 920 milyon dolarlık işlem gücü anlaşması imzaladı.",
    "Google, AI talebinin altında ezilmeye başladı: SpaceX ile aylık $920M'lık compute anlaşması imzaladı. Yani devlerin bile içeride yetmiyor.",
    category="grounded_with_strong_opinion", trend_id="4c5e5458-8c31-440a-9b1e-3e285ce805e1",
    url="https://x.com/shiftdeletenet/status/2063167115973005809",
    note="Opinion ('devlerin bile içeride yetmiyor') somut iddia değil; ground edilmesi gereken tek factual claim doğru.",
)
gold(
    "gold-21-meta-ai-bot-grounded", "grounded",
    "Yapay zekâ botu, Instagram hesaplarının çalınmasına yardım etti! Meta AI'daki bir açık, kötü niyetli kişilerin bazı Instagram hesaplarını devralmasına yol açtı. Saldırganlar, destek botundan hedef hesaba yeni bir e-posta eklemesini istedi. Bot doğrulama kodunu asıl hesap sahibine değil saldırganın e-postasına gönderince, şifre sıfırlama bağlantısıyla hesaplar ele geçirilebildi.",
    "Meta AI destek botu, Instagram hesaplarının ele geçirilmesine yol açtı: saldırgan e-postası ekleten flow, doğrulama kodunu yanlış adrese gönderiyor. Klasik 'AI'ın yetkisi insandan fazla' tuzağı.",
    category="grounded_factual", trend_id="2dd07abb-e4ed-4e94-8e4d-15f2adecb84b",
    url="https://x.com/webtekno/status/2061805243000180995",
)
gold(
    "gold-22-iphone-battery-grounded", "grounded",
    "Apple, iPhone 18 Pro modelinde bölgesel batarya stratejisi uyguluyor.",
    "Apple iPhone 18 Pro'da bölgesel batarya stratejisine geçiyor. Tek SKU dünyası bitiyor olabilir.",
    category="grounded_with_soft_inference", trend_id="9170e2ff-bf9c-43b0-b090-3e1065d508a7",
    url="https://x.com/shiftdeletenet/status/2061701520572166583",
)
gold(
    "gold-23-spacex-ipo-grounded", "grounded",
    "12 Haziran'da tüm zamanların en büyük halka arzını gerçekleştirecek SpaceX'in hisse fiyatı açıklandı. SpaceX'in hisse fiyatının 135 dolar olacağı açıklandı.",
    "SpaceX 12 Haziran'da $135 hisse fiyatıyla halka açılıyor — tüm zamanların en büyük IPO'su.",
    category="grounded_factual", trend_id="f9537323-788f-40bc-ae79-b03fddbe80fb",
    url="https://x.com/webtekno/status/2062526408367235370",
)
gold(
    "gold-24-recursive-self-improvement-grounded", "grounded",
    "None of this guarantees recursive self-improvement is on the horizon. It's not yet clear that Claude is capable of research judgment—of choosing the right problems to work on.",
    "Anthropic'in dürüst kabulü: recursive self-improvement HENÜZ ufukta değil. Claude, doğru problemi seçme yargısına sahip mi belli değil. Hype değil, gerçekçilik.",
    category="grounded_with_strong_opinion", trend_id="47a8798f-828d-42e2-b7b4-1760839b48a9",
    url="https://x.com/AnthropicAI/status/2062568873321513443",
    note="Source-faithful: kaynağın aynısını söylüyor + 'hype değil, gerçekçilik' = opinion (faithful framing).",
)
gold(
    "gold-25-singapore-grounded", "grounded",
    "We're expanding our partnership with Singapore to help safely deploy AI at scale. Together with country experts, our new programs will focus on accelerating scientific discovery, advancing pandemic preparedness, and improving healthcare.",
    "Google DeepMind, Singapur ortaklığını genişletiyor: bilimsel keşif, pandemi hazırlığı ve sağlık üç başlık. Devlet + AI lab ortaklığı pattern'i yayılıyor.",
    category="grounded_factual", trend_id="43aa4fba-fe4b-4554-83c0-23e7ddc942c0",
    url="https://x.com/GoogleDeepMind/status/2057985225100235022",
)


# ──────────────────────────────────────────────────────────────────────
# SYNTHETIC EXPANSION (≥125)
# ──────────────────────────────────────────────────────────────────────

# Real grounded sources we'll perturb. Each is a (id, src, base_grounded_draft) tuple.
# All sources are pulled from the trends table (verified 2026-06-06).
REAL_SOURCES = [
    ("src-opus48",
     "Introducing Claude Opus 4.8: it builds on Opus 4.7 with sharper judgment, more honesty about its own progress, and the ability to work independently for longer than its predecessors. Available today at the same price.",
     "Anthropic Claude Opus 4.8'i duyurdu — Opus 4.7'nin üzerine inşa edilmiş, daha keskin yargı ve daha uzun bağımsız çalışma. Aynı fiyat.",
     "https://x.com/claudeai/status/2060042702150930686"),
    ("src-google-spacex",
     "Google, artan yapay zeka talebini karşılamak için SpaceX ile aylık 920 milyon dolarlık işlem gücü anlaşması imzaladı.",
     "Google, AI talebi için SpaceX ile aylık $920M compute anlaşması imzaladı.",
     "https://x.com/shiftdeletenet/status/2063167115973005809"),
    ("src-meta-ai-bot",
     "Yapay zekâ botu, Instagram hesaplarının çalınmasına yardım etti! Meta AI'daki bir açık, kötü niyetli kişilerin bazı Instagram hesaplarını devralmasına yol açtı. Saldırganlar, destek botundan hedef hesaba yeni bir e-posta eklemesini istedi.",
     "Meta AI destek botu, Instagram hesaplarının ele geçirilmesinde araç oldu — saldırgan e-postası flow'u.",
     None),
    ("src-iphone-battery",
     "Apple, iPhone 18 Pro modelinde bölgesel batarya stratejisi uyguluyor.",
     "Apple iPhone 18 Pro'da bölgesel batarya stratejisine geçiyor.",
     None),
    ("src-spacex-ipo",
     "12 Haziran'da tüm zamanların en büyük halka arzını gerçekleştirecek SpaceX'in hisse fiyatı açıklandı. SpaceX'in hisse fiyatının 135 dolar olacağı açıklandı.",
     "SpaceX 12 Haziran'da $135 hisse fiyatıyla halka açılıyor.",
     None),
    ("src-rsi-not-horizon",
     "None of this guarantees recursive self-improvement is on the horizon. It's not yet clear that Claude is capable of research judgment—of choosing the right problems to work on.",
     "Anthropic recursive self-improvement'in HENÜZ ufukta olmadığını söyledi.",
     "https://x.com/AnthropicAI/status/2062568873321513443"),
    ("src-singapore",
     "We're expanding our partnership with Singapore to help safely deploy AI at scale. Together with country experts, our new programs will focus on accelerating scientific discovery, advancing pandemic preparedness, and improving healthcare.",
     "Google DeepMind, Singapur ortaklığını genişletiyor: bilimsel keşif, pandemi hazırlığı, sağlık.",
     "https://x.com/GoogleDeepMind/status/2057985225100235022"),
    ("src-meta-asistan",
     "Meta'nın yeni yapay zeka asistanı, karmaşık analiz ekranlarını sohbet ekranına taşıyor. İçerik üreticileri artık performans verilerini grafiklerde boğulmadan inceleyebilecek.",
     "Meta'nın yeni AI asistanı, analiz dashboard'unu sohbet ekranına taşıyor.",
     None),
    ("src-reels-series",
     "Meta, Instagram ve Facebook Reels için 'Series' adlı yeni bir özelliği test ediyor. Bu özellik, içerik üreticilerinin aynı konu etrafındaki Reels videolarını bölümler hâlinde bir araya getirmesini sağlayacak.",
     "Meta Reels için Series özelliği test ediyor — Reels'leri bölümler hâlinde gruplama.",
     None),
    ("src-mythos",
     "Anthropic, Claude Mythos Preview modeli ile bir ayda 10 binden fazla kritik güvenlik açığı tespit ettiğini duyurdu.",
     "Anthropic, Claude Mythos Preview ile bir ayda 10.000+ kritik güvenlik açığı tespit ettiğini açıkladı.",
     None),
    ("src-mosquito",
     "Google, doğaya 32 milyon 'özel' erkek sivrisinek salmaya hazırlanıyor. Süreç onaylanırsa ABD'de Kaliforniya ve Florida'da milyonlarca laboratuvar üretimi erkek sivrisinek doğaya bırakılacak.",
     "Google, doğaya 32 milyon laboratuvar-üretimi erkek sivrisinek salacak.",
     None),
    ("src-starship-v3",
     "SpaceX, üçüncü nesil Starship V3 roketini ilk kez test uçuşuna çıkardı. Uzaya ulaşan roketin detayları ve testin sonuçları haberimizde.",
     "SpaceX, Starship V3'ün ilk test uçuşunu gerçekleştirdi.",
     None),
    ("src-meta-limitless",
     "Meta, 2025 sonunda satın aldığı Limitless teknolojisiyle yeni bir yapay zeka destekli kolye ve giyilebilir cihazlar üzerinde çalışıyor.",
     "Meta, 2025 sonunda aldığı Limitless ile AI destekli giyilebilirler üzerinde çalışıyor.",
     None),
    ("src-ai-studio",
     "Google AI Studio, kodlama gerektirmeden sadece yazılı talimatlarla Android uygulamaları geliştirme özelliği kazandı.",
     "Google AI Studio, yazılı talimatla Android uygulaması geliştirme özelliği kazandı.",
     None),
    ("src-synthid",
     "SynthID, our imperceptible watermark for AI-generated content, is expanding to more partners. We're also adding new ways to find out if content was generated using AI - just ask in the GeminiApp or in Google Search.",
     "Google DeepMind, SynthID watermark'ını daha fazla ortağa açıyor — Gemini App ve Search'te AI-üretimi sorgulama.",
     "https://x.com/GoogleDeepMind/status/2057898089621459434"),
]


cases: list[dict] = list(GOLD)


# ── Hard negatives — inject exactly ONE fabrication into a grounded draft ──

INJECTIONS = [
    # (label of injection, text to append/insert, ungrounded_spans)
    ("fake_cve", " CVE-2026-99999 olarak takip ediliyor.", ["CVE-2026-99999"]),
    ("novel_entity_starlink", " Asıl iş Starlink üzerinden yapılacak.", ["Starlink"]),
    ("novel_entity_palantir", " Palantir devrede.", ["Palantir"]),
    ("novel_entity_deepseek", " DeepSeek bu hamlede dolaylı kazanan.", ["DeepSeek"]),
    ("novel_entity_huawei", " Huawei'nin çip envanteri devrede.", ["Huawei"]),
    ("wrong_number_billion", " Toplam $42 milyar değerindeki anlaşma kapsamında.", ["$42 milyar"]),
    ("wrong_number_percent", " Bu, pazarın %67'sini doğrudan etkileyecek.", ["%67"]),
    ("benchmark_invented", " MMLU'da %94.2 skor aldı.", ["MMLU", "%94.2"]),
    ("benchmark_invented_swe", " SWE-Bench Verified'de SOTA.", ["SWE-Bench Verified"]),
    ("wrong_speedup", " Önceki sürüme göre 7x hızlı.", ["7x"]),
    ("invented_gpu", " NVIDIA H200 kümeleri üzerinde çalışıyor.", ["NVIDIA H200"]),
    ("source_contradiction_yes",
     " Bu, recursive self-improvement eşiğinin geçildiği anlamına geliyor.",
     ["recursive self-improvement eşiği"]),
    ("invented_person_demis", " Demis Hassabis açıklamayı X'te paylaştı.", ["Demis Hassabis"]),
    ("invented_person_altman", " Sam Altman tweet'iyle teyit etti.", ["Sam Altman tweet'iyle teyit"]),
    ("fake_acquisition_amount", " Limitless'i $1.2 milyara aldılar.", ["$1.2 milyara"]),
    ("fake_revenue", " Yıllık $4.8 milyar gelir bekleniyor.", ["$4.8 milyar"]),
    ("fake_user_count", " 240 milyon aktif kullanıcıya ulaştı.", ["240 milyon aktif kullanıcı"]),
]

hn_idx = 0
for inj_label, inj_text, inj_spans in INJECTIONS:
    for src_id, src, base, url in REAL_SOURCES:
        hn_idx += 1
        if hn_idx > 45:  # cap hard_negative around 45 to leave room for positives
            break
        cases.append({
            "id": f"hn-{hn_idx:03d}-{inj_label}-{src_id}",
            "label": "fabrication",
            "category": f"synthetic_injection_{inj_label}",
            "source_raw_content": src,
            "draft_text": base + inj_text,
            "ungrounded_spans": inj_spans,
            "gold": False,
            "phase0_audit": False,
            "synthetic_kind": "hard_negative",
            "source_url": url,
        })
    if hn_idx > 45:
        break


# ── Hard positives — paraphrase / suffix / alias / strong opinion ──────

# Turkish agglutinative suffix variants of canonical entities
SUFFIX_VARIANTS = [
    ("OpenAI", ["OpenAI'ın", "OpenAI'a", "OpenAI'dan", "OpenAI'la", "OpenAI'ı"]),
    ("SpaceX", ["SpaceX'in", "SpaceX'le", "SpaceX'i", "SpaceX'ten"]),
    ("Google", ["Google'ın", "Google'a", "Google'dan"]),
    ("Anthropic", ["Anthropic'in", "Anthropic'i", "Anthropic'ten"]),
    ("Apple", ["Apple'ın", "Apple'a", "Apple'dan"]),
    ("Meta", ["Meta'nın", "Meta'ya", "Meta'dan"]),
    ("Microsoft", ["Microsoft'un", "Microsoft'a"]),
    ("Claude", ["Claude'un", "Claude'a"]),
]

# Aliases that should NOT trigger a block when the canonical entity is in source
ALIAS_VARIANTS = [
    ("Meta", "Facebook"),
    ("Meta", "Instagram"),
    ("Google", "DeepMind"),
    ("Google", "Google DeepMind"),
    ("Amazon", "AWS"),
    ("Amazon", "Bedrock"),
    ("OpenAI", "ChatGPT"),
    ("OpenAI", "GPT"),
]

# Strong opinion templates — built ONLY on source-grounded facts
OPINION_PREFIXES = [
    "asıl iş şu: ",
    "bence buradaki perde-arkası: ",
    "burada görünmeyen şey: ",
    "kimse söylemiyor ama: ",
    "bu kararın bir yan etkisi: ",
    "ben bu hamleyi şöyle okuyorum: ",
    "esas mesele net: ",
    "şu açıdan bakınca: ",
]
OPINION_SUFFIXES_SAFE = [
    "demek ki rakipler düşünmek zorunda.",
    "demek ki sektör için bir sinyal.",
    "yani basit bir güncelleme değil.",
    "ekosistemde tartışma başlatır.",
    "operatörler için anlamlı.",
    "yatırımcılar için yeni bilgi.",
    "geliştirici tarafında pratik etki var.",
    "bunu hafife almak yanlış olur.",
]

PARAPHRASE_TEMPLATES = [
    "Yeni gelişme — {fact}. İlginç bir hamle.",
    "{fact} Bu, ürün ekibinin son aylardır işaret ettiği yöne uyuyor.",
    "{fact} — basit bir başlık, etkisi katmanlı.",
    "Bir cümle: {fact}. Detayı haberde.",
    "Bugünün haberi: {fact}. Yorum yarın.",
    "{fact} Bunu duyurduklarında, ekibin disiplini hissediliyor.",
    "Sade haliyle: {fact}.",
    "Resmi açıklama geldi: {fact}.",
]


hp_idx = 0


def add_positive(case_id, src_id, src, draft, kind, url=None, note=""):
    global hp_idx
    hp_idx += 1
    cases.append({
        "id": f"hp-{hp_idx:03d}-{kind}-{src_id}",
        "label": "grounded",
        "category": f"synthetic_positive_{kind}",
        "source_raw_content": src,
        "draft_text": draft,
        "ungrounded_spans": [],
        "gold": False,
        "phase0_audit": False,
        "synthetic_kind": "hard_positive",
        "source_url": url,
        "note": note,
    })


# 1) Paraphrases of grounded drafts
for src_id, src, base, url in REAL_SOURCES:
    for tpl in PARAPHRASE_TEMPLATES[:3]:
        fact = base
        if fact.endswith("."):
            fact = fact[:-1]
        add_positive(f"para", src_id, src, tpl.format(fact=fact), "paraphrase", url=url)

# 2) Turkish-suffix variants — pick a base sentence containing entity, swap to suffixed form
SUFFIX_TEMPLATES = [
    ("OpenAI", "src-opus48",  # not literally in src, but a test of suffix matching on a non-source entity? skip
    ),
]
# Apply suffix variants where canonical entity IS in source
for canonical, suffix_forms in SUFFIX_VARIANTS:
    for src_id, src, base, url in REAL_SOURCES:
        if canonical.lower() not in src.lower():
            continue
        for sfx in suffix_forms[:2]:  # 2 suffix variants per (canonical, source) pair
            # Make a paraphrase referencing the entity in suffixed form
            draft = f"{sfx} bu hamlesi, kaynakta belirtildiği gibi {base[:80].rstrip('.')}."
            add_positive("sfx", src_id, src, draft, f"suffix_{canonical.lower()}", url=url)

# 3) Alias variants — refer to entity by an alias that should map to same canonical
for canonical, alias in ALIAS_VARIANTS:
    for src_id, src, base, url in REAL_SOURCES:
        if canonical.lower() not in src.lower():
            continue
        draft = f"{alias} tarafı için anlamlı bir gelişme: {base}"
        add_positive("alias", src_id, src, draft, f"alias_{alias.lower().replace(' ', '_')}", url=url)

# 4) Strong opinions on grounded facts (the most valuable: gate must NOT block these)
for src_id, src, base, url in REAL_SOURCES:
    for pfx in OPINION_PREFIXES[:3]:
        sfx = random.choice(OPINION_SUFFIXES_SAFE)
        draft = f"{base} {pfx}{sfx}"
        add_positive("opinion", src_id, src, draft, "strong_opinion_on_grounded", url=url)

# 5) Direct restatements (the simplest grounded case — must pass)
for src_id, src, base, url in REAL_SOURCES:
    add_positive("restate", src_id, src, base, "direct_restatement", url=url)


# ──────────────────────────────────────────────────────────────────────
# Sanity counts + write
# ──────────────────────────────────────────────────────────────────────

from collections import Counter
labels = Counter(c["label"] for c in cases)
synth = Counter(c.get("synthetic_kind") for c in cases if not c.get("gold"))
print(f"Total cases : {len(cases)}")
print(f"By label    : {dict(labels)}")
print(f"By synth    : {dict(synth)}")
print(f"Grounded total: {labels['grounded']}  (must be ≥50)")

assert len(cases) >= 150, f"need ≥150, got {len(cases)}"
assert labels["grounded"] >= 50, f"need ≥50 grounded, got {labels['grounded']}"
assert labels["fabrication"] >= 40, f"need ≥40 fabrication, got {labels['fabrication']}"

with open(OUT, "w", encoding="utf-8") as f:
    for c in cases:
        f.write(json.dumps(c, ensure_ascii=False) + "\n")

print(f"\nWrote {len(cases)} cases → {OUT}")
