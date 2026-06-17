# Phase 26 — hype-exec Hetzner deployment guide

One-time setup (run as root via `ssh root@46.225.27.85`):

## 1. System user + directories

```bash
useradd -r -s /usr/sbin/nologin -d /opt/hype-exec hype || true
mkdir -p /opt/hype-exec/{logs,state}
chown -R hype:hype /opt/hype-exec
```

## 2. Code rsync (from local laptop)

```bash
rsync -avz --delete \
  --exclude='.venv/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='.env' \
  --exclude='scripts/smoke_*' \
  hype_exec/ root@46.225.27.85:/opt/hype-exec/

ssh root@46.225.27.85 'chown -R hype:hype /opt/hype-exec'
```

## 3. Python venv + deps

```bash
ssh root@46.225.27.85 'cd /opt/hype-exec && \
  sudo -u hype python3.12 -m venv .venv && \
  sudo -u hype .venv/bin/pip install --upgrade pip && \
  sudo -u hype .venv/bin/pip install -r requirements.txt'
```

## 4. `.env`

Copy `.env.example` to `/opt/hype-exec/.env` and fill in:
- `SUPABASE_DB_URL` — Postgres URI on port **5432** (session pooler), NOT 6543.
- `SUPABASE_SERVICE_ROLE_KEY` — same as Hype Crew uses.
- `GOOGLE_API_KEY` — Gemini direct API (https://aistudio.google.com/apikey).
- `HYPE_ACCOUNT_ID` — Cansu's connected_accounts.id.

```bash
ssh root@46.225.27.85 'chmod 0600 /opt/hype-exec/.env && chown hype:hype /opt/hype-exec/.env'
```

## 5. systemd

```bash
scp deploy/hype-exec.service              root@46.225.27.85:/etc/systemd/system/
scp deploy/hype-exec-cleanup.service      root@46.225.27.85:/etc/systemd/system/
scp deploy/hype-exec-cleanup.timer        root@46.225.27.85:/etc/systemd/system/

ssh root@46.225.27.85 'systemctl daemon-reload && \
  systemctl enable --now hype-exec.service && \
  systemctl enable --now hype-exec-cleanup.timer'
```

## 6. Smoke

```bash
ssh root@46.225.27.85 'systemctl status hype-exec.service --no-pager | head -15'
ssh root@46.225.27.85 'journalctl -u hype-exec -n 80 --no-pager'
ssh root@46.225.27.85 'curl -s http://127.0.0.1:8090/health'
```

Expected:
- service: `Active: active (running)`
- journal: `psycopg pool opened`, `LangGraph AsyncPostgresSaver setup complete`, `[health] listening on http://127.0.0.1:8090`
- health: `ok`

## 7. Backend reload

`backend/server.py` now registers `exec_router`. To pick it up on Hetzner:

```bash
rsync -avz backend/routes/exec.py    root@46.225.27.85:/opt/contentfactory/backend/routes/
rsync -avz backend/server.py         root@46.225.27.85:/opt/contentfactory/backend/server.py
ssh root@46.225.27.85 'systemctl restart contentfactory.service'
```

## 8. Hype Crew reload (Phase 26.H hooks)

```bash
rsync -avz hype_crew/runner.py hype_crew/flow.py root@46.225.27.85:/opt/hype-crew/
ssh root@46.225.27.85 'find /opt/hype-crew -name __pycache__ -not -path "*/venv/*" -exec rm -rf {} +'
```

(Timer is hourly; next tick picks up changes automatically.)

## 9. Manual trigger to verify wiring

```bash
# Force a daily_standup meeting bypass scheduler:
ssh root@46.225.27.85 'cd /opt/hype-exec && sudo -u hype .venv/bin/python -m hype_exec.scripts.smoke_graph'
```

Then in Supabase:
```sql
SELECT id, kind, started_at, ended_at FROM executive_meetings ORDER BY started_at DESC LIMIT 3;
SELECT role_responsible, decision_type, status FROM executive_decisions ORDER BY created_at DESC LIMIT 10;
SELECT author_role, kind, left(content,80) FROM executive_memos ORDER BY created_at DESC LIMIT 10;
```

## Rollback

```bash
ssh root@46.225.27.85 'systemctl disable --now hype-exec.service hype-exec-cleanup.timer'
# Optionally remove dirs / DB rows if you want to fully revert.
```

`hype_account_config.executive_freeze=true` (manual SQL) acts as kill-switch
without stopping the daemon.
