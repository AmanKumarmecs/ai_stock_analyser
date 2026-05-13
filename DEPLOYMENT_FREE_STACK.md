# AI NSE Stock Analyzer v9 - Free Stack Deployment

Target stack:

- Frontend: Netlify Free
- Backend API: Koyeb Free
- Database: Neon Free
- Daily retraining: GitHub Actions scheduled workflow in a public repo
- Heavy/manual training: Kaggle Notebook
- Model file: `backend/models/model_pack.joblib`, kept under 100 MB

## 1. Push this repo to GitHub

```powershell
git add .
git commit -m "v9 free-stack deployment ready"
git push
```

## 2. Neon

Create a Neon Postgres database and copy the connection string:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST/neondb?sslmode=require
```

Do not commit this value.

## 3. GitHub Secrets

In GitHub repo:

`Settings -> Secrets and variables -> Actions -> New repository secret`

Add:

```text
DATABASE_URL = your Neon connection string
```

Then open `Actions -> Daily model retraining -> Run workflow` once manually.

The workflow creates/updates:

```text
backend/models/model_pack.joblib
backend/models/model_manifest.json
```

The workflow is scheduled after market close on weekdays.

## 4. Koyeb backend

Create a Koyeb Web Service from GitHub.

Recommended settings:

```text
Service type: Web Service
Repository: your GitHub repo
Root directory: backend
Build method: Dockerfile
Instance: Free
```

Environment variables:

```env
DATABASE_URL=your Neon connection string
ALLOWED_ORIGINS=https://your-netlify-site.netlify.app
MODEL_DIR=/app/models
ENABLE_RUNTIME_TRAINING=false
DB_KEEP_DAYS=90
DB_MAX_ROWS_PER_SYMBOL=140
DB_MAX_TOTAL_ROWS=2500
MODEL_MAX_MB=95
```

Health check URL:

```text
/health
```

## 5. Netlify frontend

Create Netlify site from GitHub.

Build settings:

```text
Base directory: frontend
Build command: npm ci && npm run build
Publish directory: dist
```

Environment variable:

```env
VITE_API_BASE_URL=https://your-koyeb-service-url.koyeb.app
```

Redeploy the site.

## 6. Free limit protection

The backend automatically prunes Neon rows using:

```env
DB_KEEP_DAYS=90
DB_MAX_ROWS_PER_SYMBOL=140
DB_MAX_TOTAL_ROWS=2500
```

The GitHub workflow refuses to keep `model_pack.joblib` above `MODEL_MAX_MB`, default 95 MB, so it stays below the common 100 MB GitHub file limit.

## 7. What does not happen on Koyeb Free

Koyeb Free is small, so runtime training is disabled by default. The backend does:

- inference
- prediction storage
- prediction evaluation
- database pruning

Training happens in:

- GitHub Actions daily workflow
- Kaggle Notebook manually when needed
