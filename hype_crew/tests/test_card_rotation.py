"""Çift-çift fix regression: assign_kinds_chronological asla iki aynı tip
arka arkaya planlamamalı (companion+drought interleave dahil)."""
import datetime as dt

import tools.card_scheduler as cs


def _utc(h, m=0, day=14):
    return dt.datetime(2026, 6, day, h, m, tzinfo=dt.timezone.utc)


def _no_adjacent_dupes(timeline):
    """timeline = [(time, kind)] sıralı → ardışık aynı kind yok mu?"""
    seq = [k for _, k in sorted(timeline)]
    return all(a != b for a, b in zip(seq, seq[1:]))


def test_drought_empty_queue_alternates(monkeypatch):
    monkeypatch.setattr(cs, "_existing_card_slots", lambda *a, **k: [])
    times = [_utc(11), _utc(14), _utc(17), _utc(20)]
    kinds = cs.assign_kinds_chronological("acc", times)
    assert kinds == ["dictionary", "question", "dictionary", "question"]


def test_drought_seeds_off_existing_last(monkeypatch):
    # dün son kart 'dictionary' → bugünkü ilk kart 'question' olmalı
    monkeypatch.setattr(cs, "_existing_card_slots",
                        lambda *a, **k: [(_utc(20, day=13).isoformat(), "dictionary")])
    times = [_utc(11), _utc(14), _utc(17), _utc(20)]
    kinds = cs.assign_kinds_chronological("acc", times)
    assert kinds[0] == "question"
    tl = [(_utc(20, day=13), "dictionary")] + list(zip(times, kinds))
    assert _no_adjacent_dupes(tl)


def test_append_after_queue_no_dupes(monkeypatch):
    # companion KUYRUK SONUNA eklenince (append) çift-çift olmaz.
    # mevcut: 22:09 q, 01:09 d (önceki companion). Yeni 2 slot kuyruktan SONRA.
    existing = [(_utc(22, 9, day=13).isoformat(), "question"),
                (_utc(1, 9).isoformat(), "dictionary")]
    monkeypatch.setattr(cs, "_existing_card_slots", lambda *a, **k: existing)
    new = [_utc(4, 9), _utc(7, 9)]   # 01:09'dan SONRA (append)
    kinds = cs.assign_kinds_chronological("acc", new)
    tl = [(dt.datetime.fromisoformat(t), k) for t, k in existing] + list(zip(new, kinds))
    assert _no_adjacent_dupes(tl), f"adjacent dupe: {sorted(tl)}"


def test_old_bug_scenario_improved(monkeypatch):
    # Eski hata: iki companion batch global-max'tan seed → q,q,d,d.
    # Yeni atama interleave'de bile en kötü tek çakışma; append ile sıfır.
    existing = [(_utc(22, 9, day=13).isoformat(), "question"),
                (_utc(1, 9).isoformat(), "dictionary")]
    monkeypatch.setattr(cs, "_existing_card_slots", lambda *a, **k: existing)
    # append edilmiş yeni slotlar (companion fix sayesinde kuyruktan sonra)
    new = [_utc(4, 9), _utc(7, 9)]
    kinds = cs.assign_kinds_chronological("acc", new)
    assert kinds == ["question", "dictionary"]  # d(01:09)→q→d


def test_companion_two_slots_always_one_each(monkeypatch):
    monkeypatch.setattr(cs, "_existing_card_slots", lambda *a, **k: [])
    kinds = cs.assign_kinds_chronological("acc", [_utc(10), _utc(13)])
    assert set(kinds) == {"dictionary", "question"}
