#!/bin/bash
# Viral Tweet Collection v4 — 312 hesap, 3 cookie rotation
# TR: min 100 like, EN: min 500 like (collector script dil bazlı otomatik ayarlıyor)
# 8 niche sırayla, 10dk rate limit arası (3 cookie ile daha hızlı)

set -e
cd /opt/contentfactory/backend
source venv/bin/activate
export $(grep -v '^#' .env | xargs)

LOG_DIR="/tmp/viral_collect_v4"
mkdir -p "$LOG_DIR"

PAGES=10
WAIT=600  # 10dk (3 cookie ile 15dk gerekmez)

echo "$(date) - 🚀 Viral Tweet Collection v4"
echo "  312 hesap | 3 cookie rotation | $PAGES sayfa/hesap"
echo "============================================="

NICHES=("tech" "pazarlama" "finans" "kripto" "mizah" "kisisel_gelisim" "icerik_uretici" "haber")

for i in "${!NICHES[@]}"; do
    NICHE="${NICHES[$i]}"
    echo ""
    echo "$(date) - 🔥 [$((i+1))/${#NICHES[@]}] $NICHE niche'i başlıyor..."
    python3 -u scripts/collect_viral_tweets.py \
        --niche "$NICHE" --min-likes 1000 --max-pages "$PAGES" \
        2>&1 | tee "$LOG_DIR/${NICHE}.log"
    echo "$(date) - ✅ $NICHE tamamlandı"
    
    # Son niche değilse bekle
    if [ $i -lt $((${#NICHES[@]}-1)) ]; then
        echo "$(date) - ⏳ ${WAIT}s bekleniyor..."
        sleep $WAIT
    fi
done

echo ""
echo "$(date) - 🎉 TÜM NİCHE'LER TAMAMLANDI"
echo "============================================="

# Supabase özet
python3 -c "
import httpx, os
url = os.environ['SUPABASE_URL'] + '/rest/v1/viral_tweets'
key = os.environ['SUPABASE_SERVICE_KEY']
headers = {'apikey': key, 'Authorization': 'Bearer ' + key}
r = httpx.get(url + '?select=niche,language', params={'limit': 100000}, headers=headers)
data = r.json()
by_niche = {}
for d in data:
    n = d.get('niche', '?')
    l = d.get('language', '?')
    if n not in by_niche:
        by_niche[n] = {'tr': 0, 'en': 0, 'total': 0}
    by_niche[n][l] = by_niche[n].get(l, 0) + 1
    by_niche[n]['total'] += 1
print(f'\nToplam: {len(data)} viral tweet')
for n, c in sorted(by_niche.items(), key=lambda x: -x['total']):
    status = '✅' if c['total'] >= 100 else '⚠️'
    print(f'  {status} {n}: {c[\"total\"]} ({c.get(\"tr\",0)} TR + {c.get(\"en\",0)} EN)')
"
