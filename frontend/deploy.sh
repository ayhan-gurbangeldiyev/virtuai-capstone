#!/bin/bash
# Type Hype Frontend Deploy Script
# Usage: ./deploy.sh
set -e

echo "🔨 Building..."
npx craco build

echo "📦 Syncing to .vercel/output..."
rm -rf .vercel/output/static/*
cp -r build/* .vercel/output/static/

echo "🚀 Deploying to Vercel..."
npx vercel deploy --prebuilt --prod --yes --force

echo "✅ Verifying..."
LIVE_HASH=$(curl -s https://typehype.io/ 2>&1 | grep -o 'main\.[a-f0-9]*\.js' | head -1)
LOCAL_HASH=$(ls build/static/js/main.*.js | grep -o 'main\.[a-f0-9]*\.js')

if [ "$LIVE_HASH" = "$LOCAL_HASH" ]; then
  echo "✅ Deploy verified: $LIVE_HASH"
else
  echo "⚠️ Hash mismatch! Live: $LIVE_HASH, Local: $LOCAL_HASH"
fi
