# AI NSE Stock Analyzer v8 Deployment Notes

Recommended free stack:

- Frontend: Netlify
- Backend API: Oracle Cloud Always Free VM
- Database: Neon Postgres free plan
- Daily automation: Linux cron on Oracle VM
- Model files: Oracle VM `/opt/ai-nse-stock-analyzer/models`

## Backend environment variables

Create `/opt/ai-nse-stock-analyzer/backend/.env` or set variables in the systemd service:

```bash
DATABASE_URL='postgresql://USER:PASSWORD@HOST.neon.tech/DBNAME?sslmode=require'
ALLOWED_ORIGINS='https://your-site.netlify.app'
MODEL_DIR='/opt/ai-nse-stock-analyzer/models'
```

## Start backend manually

```bash
cd /opt/ai-nse-stock-analyzer/backend
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Cron command

```bash
10 16 * * 1-5 curl -s -X POST http://127.0.0.1:8000/api/learning/daily-cycle >> /opt/ai-nse-stock-analyzer/cron.log 2>&1
```
