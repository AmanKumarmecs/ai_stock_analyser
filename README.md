# AI NSE Stock Analyzer v9

Free-stack deployment-ready demo for NSE-listed stock analysis.

## What this version is designed for

- **Frontend:** Netlify Free
- **Backend:** Koyeb Free
- **Database:** Neon Free Postgres
- **Daily retraining:** GitHub Actions scheduled workflow in a public repo
- **Heavy/manual training:** Kaggle Notebook
- **Model file:** `backend/models/model_pack.joblib`, kept under 100 MB

## Features

- Automatic NSE-listed symbol data fetching through free public data source
- Bullish / Bearish / Neutral prediction
- Next trading day and next 5 trading day trend
- Confidence filter
- DMI / ADX, RSI, MACD, SMA, volatility, volume, and NIFTY 50 context
- Prediction storage and evaluation in Neon
- Automatic data pruning to stay within free database limits
- GitHub Actions model retraining after market close
- Koyeb-safe runtime: inference/evaluation only by default

## Important disclaimer

This is a demo/educational analytics project. It is not financial advice and does not guarantee profit or accuracy. It uses free public data for demonstration, not an official NSE licensed real-time feed.

## Local backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Local frontend

```powershell
cd frontend
npm install
npm run dev
```

## Deployment guide

Read:

```text
DEPLOYMENT_FREE_STACK.md
```

## Training

GitHub Actions workflow:

```text
.github/workflows/daily-retrain.yml
```

Kaggle guide:

```text
training/KAGGLE_TRAINING_GUIDE.md
```
