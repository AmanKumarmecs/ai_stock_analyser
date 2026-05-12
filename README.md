# AI NSE Stock Analyzer v8 - Deployment Ready

This version adds Neon/PostgreSQL support through `DATABASE_URL`, Oracle VM model storage through `MODEL_DIR`, Netlify frontend environment support, and daily auto-learning support.

# AI NSE Stock Analyzer v8 — Auto Daily Learning Demo

This is a seller-ready demo website for NSE-listed stock analysis. It uses automatic free public market data for demo purposes, calculates technical indicators, predicts **Bullish / Bearish / Neutral**, and explains the reason behind the prediction.

## What is new in v8

Version 8 adds automatic learning:

1. The app saves every next-day and next-5-day prediction in a SQLite database.
2. When new market data becomes available, the app compares old predictions with the actual close.
3. It marks each prediction as Correct / Wrong / Pending.
4. It retrains saved symbol-specific models using updated historical data.
5. It saves the fresh prediction for the next evaluation cycle.
6. A lightweight backend scheduler runs this daily after 16:10 IST **when the backend is alive**.
7. A dashboard panel shows evaluated predictions, pending predictions, learning accuracy, and recent prediction history.

> Important: If the backend is deployed on a free platform that sleeps, background jobs cannot run while it is asleep. Use the **Run auto learning now** button or configure a free cron ping to call `/api/learning/daily-cycle` after market close.

## Project structure

```text
backend/   FastAPI API, prediction engine, auto-learning database
frontend/  React + Vite dashboard
```

## Run backend

```powershell
cd "D:\Projects\NSE Stock Analyser"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
cd backend
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

## Run frontend

Open another PowerShell:

```powershell
cd "D:\Projects\NSE Stock Analyser\frontend"
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

## How daily learning works

### On Analyze

When you analyze a stock, the backend:

- fetches latest available data
- evaluates any old pending prediction if the target close is now available
- generates current prediction
- stores current prediction into `backend/data/daily_learning.db`

### On daily cycle

The daily learning cycle:

- fetches updated data for the stock/watchlist
- evaluates previous predictions
- retrains next-day and next-5-day saved models
- stores today's new prediction

Manual API:

```text
POST http://127.0.0.1:8000/api/learning/daily-cycle
```

For one symbol:

```text
POST http://127.0.0.1:8000/api/learning/daily-cycle?symbols=RELIANCE.NS
```

Learning status:

```text
GET http://127.0.0.1:8000/api/learning/status/RELIANCE.NS
```

## Prediction meaning

- **Next Trading Day** = expected direction of the next trading day close compared with the latest close.
- **Next 5 Trading Days** = expected direction after 5 trading days compared with the latest close.
- **Neutral** means weak or unclear signal. This is intentional to avoid forced predictions.

## Data and disclaimer

This demo uses free public data access through Yahoo/yfinance-style sources for NSE-listed symbols. It is not an official NSE licensed real-time feed. For commercial production, connect a licensed NSE/vendor feed.

This project is for demo and educational analysis only. It is not financial advice and does not guarantee profit or accuracy.
