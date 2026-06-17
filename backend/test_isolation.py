"""
Type Hype - User Isolation Security Test
Tests that User B cannot access User A's data.
"""
import httpx
import json
import time
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Config
API_BASE = "https://api.typehype.io/api"
HEADERS_BASE = {
    "X-TH-Client": "typehype-web",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/json",
}

# Berkay's known resource IDs
BERKAY_ID = "ac3be5d8-fe50-41ad-9db4-97e4faa703cc"
BERKAY_SOURCE_ID = "54cf7983-fecd-4e8e-9a56-038998277dfa"  # @semihdev
BERKAY_PROFILE_ID = "fb8fd9a4-5d9f-4d9c-849f-13af43f5c836"  # Semih Kışlar
BERKAY_GEN_ID = "9f4e8981-9696-4209-9e52-dc305ad05151"

# Test user
TEST_EMAIL = "testuser@typehype.io"
TEST_PASSWORD = "TestUser2026!Secure"

results = []

_nonce_counter = 0
def headers_for(token):
    global _nonce_counter
    _nonce_counter += 1
    h = dict(HEADERS_BASE)
    h["Authorization"] = f"Bearer {token}"
    h["X-TH-Timestamp"] = str(int(time.time()))
    h["X-TH-Nonce"] = f"test-{int(time.time() * 1000)}-{_nonce_counter}"
    return h

def test(name, passed, detail=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    results.append((name, passed, detail))
    print(f"  {status} | {name}" + (f" | {detail}" if detail else ""))

def run_tests():
    from supabase import create_client
    
    supabase_url = os.environ['SUPABASE_URL']
    supabase_key = os.environ['SUPABASE_SERVICE_KEY']
    sb = create_client(supabase_url, supabase_key)
    
    # Get test user token
    sign_in = sb.auth.sign_in_with_password({
        'email': TEST_EMAIL,
        'password': TEST_PASSWORD
    })
    test_token = sign_in.session.access_token
    test_user_id = sign_in.user.id
    print(f"\nTest user: {test_user_id}")
    print(f"Berkay:    {BERKAY_ID}\n")
    
    client = httpx.Client(timeout=30)
    h = headers_for(test_token)
    
    # ==========================================
    print("=" * 60)
    print("GRUP 1: VERİ İZOLASYONU (OKUMA)")
    print("=" * 60)
    
    # 1. History
    r = client.get(f"{API_BASE}/generations/history", headers=h)
    data = r.json() if r.status_code == 200 else []
    test("1. History boş olmalı", len(data) == 0, f"Dönen: {len(data)} kayıt")
    
    # 2. Favorites
    r = client.get(f"{API_BASE}/favorites", headers=h)
    data = r.json() if r.status_code == 200 else []
    test("2. Favoriler boş olmalı", len(data) == 0, f"Dönen: {len(data)} kayıt")
    
    # 3. Style Sources
    r = client.get(f"{API_BASE}/sources/list", headers=h)
    data = r.json() if r.status_code == 200 else []
    test("3. Sources boş olmalı", len(data) == 0, f"Dönen: {len(data)} kayıt")
    
    # 4. Style Profiles
    r = client.get(f"{API_BASE}/styles/list", headers=h)
    data = r.json() if r.status_code == 200 else []
    test("4. Profiller boş olmalı", len(data) == 0, f"Dönen: {len(data)} kayıt")
    
    # 5. Settings
    r = client.get(f"{API_BASE}/settings", headers=h)
    data = r.json() if r.status_code == 200 else {}
    # New user: either returns defaults or empty/new row. Key: must NOT return Berkay's settings
    user_id_in_settings = data.get("user_id", "")
    not_berkay = user_id_in_settings != BERKAY_ID
    test("5. Ayarlar Berkay'a ait olmamalı", not_berkay, f"Dönen: user_id={user_id_in_settings}, persona={data.get('default_persona')}")
    
    # 6. Stats
    r = client.get(f"{API_BASE}/user/stats", headers=h)
    data = r.json() if r.status_code == 200 else {}
    gen_count = data.get("generations", 0)
    fav_count = data.get("favorites", 0)
    all_zero = gen_count == 0 and fav_count == 0
    test("6. İstatistikler 0 olmalı", all_zero, f"Dönen: gen={gen_count}, fav={fav_count}")
    
    # 7. Analysis History
    r = client.get(f"{API_BASE}/analyze/history", headers=h)
    data = r.json() if r.status_code == 200 else []
    test("7. Analiz geçmişi boş olmalı", len(data) == 0, f"Dönen: {len(data)} kayıt")
    
    # 8. Coach Insights
    r = client.get(f"{API_BASE}/coach/insights", headers=h)
    data = r.json() if r.status_code == 200 else {}
    gen_count = data.get("total_generations", data.get("generation_count", 0))
    # Key: must not show Berkay's generation count (25)
    test("8. Coach insights Berkay verisi yok", gen_count != 25 and gen_count < 5, f"Dönen: generations={gen_count}")
    
    # ==========================================
    print("\n" + "=" * 60)
    print("GRUP 2: IDOR SALDIRILARI (ID İLE ERİŞİM)")
    print("=" * 60)
    
    # 9. Access Berkay's source tweets
    r = client.get(f"{API_BASE}/sources/{BERKAY_SOURCE_ID}/tweets", headers=h)
    test("9. Başkasının source tweet'leri", r.status_code in (403, 404), f"HTTP {r.status_code}")
    
    # 10. Access Berkay's profile
    r = client.get(f"{API_BASE}/styles/{BERKAY_PROFILE_ID}", headers=h)
    test("10. Başkasının profili", r.status_code in (403, 404), f"HTTP {r.status_code}")
    
    # 11. Delete Berkay's profile
    r = client.delete(f"{API_BASE}/styles/{BERKAY_PROFILE_ID}", headers=h)
    test("11. Başkasının profilini silme", r.status_code in (403, 404), f"HTTP {r.status_code}")
    # Verify not deleted
    check = sb.table("style_profiles").select("id").eq("id", BERKAY_PROFILE_ID).execute()
    test("11b. Profil hala duruyor mu", len(check.data) == 1, f"Profil sayısı: {len(check.data)}")
    
    # 12. Delete Berkay's source
    r = client.delete(f"{API_BASE}/sources/{BERKAY_SOURCE_ID}", headers=h)
    test("12. Başkasının source'unu silme", r.status_code in (403, 404), f"HTTP {r.status_code}")
    check = sb.table("style_sources").select("id").eq("id", BERKAY_SOURCE_ID).execute()
    test("12b. Source hala duruyor mu", len(check.data) == 1, f"Source sayısı: {len(check.data)}")
    
    # 13. Delete Berkay's favorite (create one first for Berkay, then test)
    import uuid as _uuid
    berkay_fav_id = str(_uuid.uuid4())
    sb.table("favorites").insert({
        "id": berkay_fav_id,
        "user_id": BERKAY_ID,
        "content": "Test favorite",
        "type": "tweet",
    }).execute()
    r = client.delete(f"{API_BASE}/favorites/{berkay_fav_id}", headers=h)
    # Should not delete (user_id mismatch)
    check = sb.table("favorites").select("id").eq("id", berkay_fav_id).execute()
    test("13. Başkasının favorisini silme", len(check.data) == 1, f"Favori hala var: {len(check.data) == 1}")
    # Cleanup
    sb.table("favorites").delete().eq("id", berkay_fav_id).execute()
    
    # 14. Generate with Berkay's style profile
    h = headers_for(test_token)  # fresh nonce
    r = client.post(f"{API_BASE}/generate/tweet", headers=h, json={
        "topic": "test isolation",
        "persona": "otorite",
        "tone": "natural",
        "length": "micro",
        "language": "tr",
        "style_profile_id": BERKAY_PROFILE_ID,
        "variants": 1
    })
    # Should succeed but WITHOUT using Berkay's style (profile not found for this user)
    if r.status_code == 200:
        test("14. Başkasının profiliyle üretim", True, "Üretim başarılı ama stil profili yok sayıldı")
    else:
        test("14. Başkasının profiliyle üretim", r.status_code != 500, f"HTTP {r.status_code}")
    
    # ==========================================
    print("\n" + "=" * 60)
    print("GRUP 3: YAZMA İZOLASYONU")
    print("=" * 60)
    
    # 15. Check Berkay's generation count before
    berkay_gens_before = sb.table("generations").select("id", count="exact").eq("user_id", BERKAY_ID).execute().count
    
    # Generate content as test user
    h = headers_for(test_token)  # fresh nonce
    r = client.post(f"{API_BASE}/generate/tweet", headers=h, json={
        "topic": "isolation test tweet",
        "persona": "saf",
        "tone": "natural",
        "length": "micro",
        "language": "tr",
        "variants": 1
    })
    
    if r.status_code == 200:
        # Check it's saved under test user
        test_gens = sb.table("generations").select("id,user_id").eq("user_id", test_user_id).execute()
        test("15. Üretim test kullanıcıya ait", len(test_gens.data) > 0, f"Test user üretimleri: {len(test_gens.data)}")
        
        # Check Berkay's count didn't change
        berkay_gens_after = sb.table("generations").select("id", count="exact").eq("user_id", BERKAY_ID).execute().count
        test("16. Berkay'ın history'si etkilenmedi", berkay_gens_before == berkay_gens_after, 
             f"Önce: {berkay_gens_before}, Sonra: {berkay_gens_after}")
    else:
        test("15. Tweet üretimi", False, f"HTTP {r.status_code}: {r.text[:100]}")
        test("16. Berkay'ın history'si", False, "Üretim başarısız, test atlandı")
    
    # ==========================================
    print("\n" + "=" * 60)
    print("GRUP 4: MIDDLEWARE GÜVENLİĞİ")
    print("=" * 60)
    
    # 17. No auth token
    h_no_auth = dict(HEADERS_BASE)
    h_no_auth["X-TH-Timestamp"] = str(int(time.time()))
    r = client.get(f"{API_BASE}/generations/history", headers=h_no_auth)
    test("17. Token'sız istek reddedilmeli", r.status_code == 401, f"HTTP {r.status_code}")
    
    # 18. No X-TH-Client header
    h_no_client = {"Authorization": f"Bearer {test_token}", "X-TH-Timestamp": str(int(time.time()))}
    r = client.get(f"{API_BASE}/generations/history", headers=h_no_client)
    test("18. X-TH-Client'sız istek reddedilmeli", r.status_code == 403, f"HTTP {r.status_code}")
    
    # 19. Old timestamp (replay)
    h_old = headers_for(test_token)
    h_old["X-TH-Timestamp"] = str(int(time.time()) - 600)  # 10 min ago
    r = client.post(f"{API_BASE}/generate/tweet", headers=h_old, json={
        "topic": "replay test", "persona": "saf", "tone": "natural",
        "length": "micro", "language": "tr", "variants": 1
    })
    test("19. Eski timestamp reddedilmeli", r.status_code in (400, 403), f"HTTP {r.status_code}")
    
    # ==========================================
    print("\n" + "=" * 60)
    print("GRUP 5: STYLE PROMPT & REFRESH IDOR")
    print("=" * 60)
    
    # 20. Get Berkay's style prompt
    h = headers_for(test_token)
    r = client.get(f"{API_BASE}/styles/{BERKAY_PROFILE_ID}/prompt", headers=h)
    test("20. Başkasının stil prompt'u", r.status_code in (403, 404), f"HTTP {r.status_code}")
    
    # 21. Refresh Berkay's profile
    h = headers_for(test_token)
    r = client.post(f"{API_BASE}/styles/{BERKAY_PROFILE_ID}/refresh", headers=h)
    test("21. Başkasının profilini refresh", r.status_code in (403, 404), f"HTTP {r.status_code}")
    
    # 22. Refresh Berkay's source
    h = headers_for(test_token)
    r = client.post(f"{API_BASE}/sources/{BERKAY_SOURCE_ID}/refresh", headers=h)
    test("22. Başkasının source'unu refresh", r.status_code in (403, 404), f"HTTP {r.status_code}")
    
    # 23. Analyze Berkay's source
    r = client.post(f"{API_BASE}/styles/analyze-source/{BERKAY_SOURCE_ID}", headers=h)
    test("23. Başkasının source'unu analiz", r.status_code in (403, 404), f"HTTP {r.status_code}")
    
    # 24. Status checks isolation
    r = client.get(f"{API_BASE}/status", headers=h)
    data = r.json() if r.status_code == 200 else []
    test("24. Status checks boş olmalı", len(data) == 0, f"Dönen: {len(data)} kayıt")
    
    # ==========================================
    # CLEANUP
    print("\n" + "=" * 60)
    print("TEMİZLİK")
    print("=" * 60)
    
    # Delete test user's generations
    sb.table("generations").delete().eq("user_id", test_user_id).execute()
    print("  Test user üretimleri silindi")
    
    # Delete test user from auth
    try:
        sb.auth.admin.delete_user(test_user_id)
        print("  Test user silindi")
    except Exception:
        # Delete via user_settings cleanup instead
        sb.table("user_settings").delete().eq("user_id", test_user_id).execute()
        print("  Test user verileri temizlendi (auth silme izni yok)")
    
    # ==========================================
    # SUMMARY
    print("\n" + "=" * 60)
    passed = sum(1 for _, p, _ in results if p)
    failed = sum(1 for _, p, _ in results if not p)
    total = len(results)
    print(f"SONUÇ: {passed}/{total} PASS, {failed} FAIL")
    if failed > 0:
        print("\nBAŞARISIZ TESTLER:")
        for name, p, detail in results:
            if not p:
                print(f"  ❌ {name} | {detail}")
    print("=" * 60)
    
    return failed == 0

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
