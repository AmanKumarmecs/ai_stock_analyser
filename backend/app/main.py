from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.services.daily_learning import (
    evaluate_pending_predictions,
    get_learning_status,
    run_daily_learning_cycle,
    prune_learning_data,
    save_prediction_from_analysis,
    start_daily_scheduler,
)
from app.services.indicators import add_indicators, to_chart_rows
from app.services.market_data import DEFAULT_SYMBOLS, MarketDataError, fetch_history, fetch_quote, normalize_symbol
from app.services.predictor import analyze_stock, get_training_status, train_models_for_symbol

app = FastAPI(
    title="AI NSE Stock Analyzer API",
    description="Version 9 free-stack API: Koyeb backend, Neon DB, Netlify frontend, GitHub Actions/Kaggle model training, and automatic data pruning.",
    version="9.0.0",
)

origins_raw = os.getenv("ALLOWED_ORIGINS", "*").strip()
allow_origins = ["*"] if origins_raw == "*" else [item.strip() for item in origins_raw.split(",") if item.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=(allow_origins != ["*"]),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    # Lightweight automatic daily learning. It runs only if the backend is alive.
    start_daily_scheduler()


@app.get("/health")
def health():
    return {"status": "ok", "message": "AI NSE Stock Analyzer API v9 free-stack deployment is running"}


@app.get("/api/default-symbols")
def default_symbols():
    return {"symbols": DEFAULT_SYMBOLS}


@app.get("/api/system/limits")
def system_limits():
    return {
        "version": "v9",
        "backend_target": "Koyeb Free",
        "database_target": "Neon Free",
        "frontend_target": "Netlify Free",
        "training_target": "GitHub Actions public repo + Kaggle Notebook",
        "runtime_training_enabled": os.getenv("ENABLE_RUNTIME_TRAINING", "false").lower() in {"1", "true", "yes"},
        "model_max_mb": float(os.getenv("MODEL_MAX_MB", "95")),
        "db_keep_days": int(os.getenv("DB_KEEP_DAYS", "90")),
        "db_max_rows_per_symbol": int(os.getenv("DB_MAX_ROWS_PER_SYMBOL", "140")),
        "db_max_total_rows": int(os.getenv("DB_MAX_TOTAL_ROWS", "2500")),
        "note": "The free backend is designed for inference/evaluation. Daily model training should run through GitHub Actions or Kaggle and produce backend/models/model_pack.joblib under 100 MB.",
    }


@app.get("/api/quote/{symbol}")
def quote(symbol: str):
    try:
        return fetch_quote(symbol)
    except MarketDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/model-status/{symbol}")
def model_status(symbol: str):
    normalized = normalize_symbol(symbol)
    return get_training_status(normalized)


@app.get("/api/learning/status")
def all_learning_status(limit: int = Query(default=20, ge=1, le=100)):
    return get_learning_status(None, limit=limit)


@app.get("/api/learning/status/{symbol}")
def symbol_learning_status(symbol: str, limit: int = Query(default=20, ge=1, le=100)):
    normalized = normalize_symbol(symbol)
    return get_learning_status(normalized, limit=limit)


@app.post("/api/learning/daily-cycle")
def manual_daily_cycle(symbols: str | None = Query(default=None, description="Optional comma-separated symbols. Blank means default watchlist.")):
    try:
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()] if symbols else None
        return run_daily_learning_cycle(symbol_list, mode="manual")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Daily learning cycle failed: {exc}") from exc


@app.post("/api/learning/prune")
def prune_learning_store():
    try:
        return prune_learning_data()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Prune failed: {exc}") from exc


@app.post("/api/train/{symbol}")
def train_symbol(
    symbol: str,
    period: str = Query(default="5y", description="Training period. Use 2y, 5y or max depending on free data availability."),
    interval: str = Query(default="1d", description="Daily data is recommended for stable training."),
):
    # Runtime training is disabled by default for Koyeb Free because 512 MB / 0.1 vCPU is too small.
    # Use GitHub Actions or Kaggle training instead. Enable only locally with ENABLE_RUNTIME_TRAINING=true.
    if os.getenv("ENABLE_RUNTIME_TRAINING", "false").strip().lower() not in {"1", "true", "yes"}:
        return {
            "trained": False,
            "runtime_training_enabled": False,
            "message": "Runtime training is disabled for the free backend. Use GitHub Actions/Kaggle to create backend/models/model_pack.joblib.",
        }
    try:
        normalized = normalize_symbol(symbol)
        history = fetch_history(normalized, period=period, interval=interval)
        enriched = add_indicators(history)

        market_enriched = None
        try:
            market_history = fetch_history("^NSEI", period=period, interval=interval)
            market_enriched = add_indicators(market_history)
        except Exception:
            market_enriched = None

        evaluate_pending_predictions(normalized, enriched)
        return train_models_for_symbol(enriched, normalized, market_df=market_enriched)
    except (MarketDataError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Unexpected training error: {exc}") from exc


@app.get("/api/analyze/{symbol}")
def analyze(
    symbol: str,
    period: str = Query(default="1y", description="Example: 6mo, 1y, 2y"),
    interval: str = Query(default="1d", description="Example: 1d. Intraday intervals may be limited by free data source."),
):
    try:
        normalized = normalize_symbol(symbol)
        history = fetch_history(normalized, period=period, interval=interval)
        enriched = add_indicators(history)

        market_enriched = None
        market_note = "NIFTY 50 context was not available from the free data source."
        try:
            market_history = fetch_history("^NSEI", period=period, interval=interval)
            market_enriched = add_indicators(market_history)
            market_note = "NIFTY 50 market context included."
        except Exception as exc:  # noqa: BLE001
            market_note = f"NIFTY 50 context unavailable; stock analysis still completed. Reason: {exc}"

        # Each analysis also checks older stored predictions if the actual target close is now known.
        evaluated = evaluate_pending_predictions(normalized, enriched)

        analysis = analyze_stock(enriched, normalized, market_df=market_enriched)
        analysis["version"] = "v9"
        analysis["chart"] = to_chart_rows(enriched, limit=180)

        # Save today's prediction automatically. This becomes tomorrow/five-day training feedback.
        saved = save_prediction_from_analysis(analysis)
        learning = get_learning_status(normalized, limit=10)
        learning["current_analysis_saved"] = saved
        learning["evaluated_on_this_request"] = evaluated
        analysis["learning"] = learning

        analysis["data_source_note"] = (
            "Automatic free public data source for NSE-listed symbols. "
            "Not an official NSE real-time licensed feed. For commercial production, connect a licensed NSE/vendor feed. "
            "Version 9 stores predictions in Neon/PostgreSQL, compares actual future close once available, prunes old rows automatically, and uses GitHub Actions/Kaggle-trained model packs. "
            + market_note
        )
        return analysis
    except (MarketDataError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Unexpected analysis error: {exc}") from exc
