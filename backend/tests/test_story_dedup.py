"""story_dedup deterministik katman testleri (LLM'siz, use_llm=False).

Gerçek Claude Fable 5 duplicate üçlüsüyle kalibre edildi (2026-06-10):
aynı lansmanın 3 farklı tweet'i 3 ayrı trend/run yaratmıştı.
"""
from services.story_dedup import find_same_story, story_tokens


T1 = ("Claude Fable 5 Tanıtıldı",
      "Anthropic just released Claude Fable 5, calling it the company's next generation of intelligence")
T2 = ("Claude Fable 5'in performansı",
      "Fable 5 is state-of-the-art on nearly all tested benchmarks, with exceptional performance in software")
T3 = ("Claude Fable 5 piyasada",
      "Claude Fable 5 is available everywhere today. Claude Mythos 5 is restricted to Glasswing partners")
T_PENTAGON = ("Anthropic Pentagon ile anlaşma imzaladı",
              "Anthropic signed a defense agreement with the Pentagon for secure deployments")
T_OPENAI = ("OpenAI kullanıcı hesapları yanlışlıkla askıya alındı",
            "Some OpenAI user accounts were mistakenly suspended, access being restored")

CANDS = [
    {"id": "1", "topic": T1[0], "raw_content": T1[1]},
    {"id": "5", "topic": T_OPENAI[0], "raw_content": T_OPENAI[1]},
]


def test_same_launch_different_tweets_match():
    for t in (T2, T3):
        m = find_same_story(t[0], t[1], CANDS, use_llm=False)
        assert m and m["id"] == "1", f"{t[0]!r} Fable lansmanına eşleşmeliydi"


def test_same_company_different_story_no_match():
    m = find_same_story(T_PENTAGON[0], T_PENTAGON[1], CANDS, use_llm=False)
    assert m is None, "aynı şirketin FARKLI haberi şüphe bile tetiklememeli"


def test_stopwords_do_not_carry_signature():
    sig = story_tokens("Yeni özellikleri duyuruldu ve geliyor")
    assert sig == set(), f"yalnız stopword'lerden imza çıkmamalı: {sig}"


def test_empty_inputs_safe():
    assert find_same_story("", "", CANDS, use_llm=False) is None
    assert find_same_story("Claude Fable 5", "x", [], use_llm=False) is None
