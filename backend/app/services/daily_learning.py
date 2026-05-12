from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.services.indicators import add_indicators
from app.services.market_data import DEFAULT_SYMBOLS, fetch_history, normalize_symbol
from app.services.predictor import analyze_stock, train_models_for_symbol

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_DB_PATH = DATA_DIR / "daily_learning.db"

_scheduler_started = False
_scheduler_lock = threading.Lock()
_last_scheduler_run_date: str | None = None
_engine: Engine | None = None
_db_initialized = False


def _now_ist() -> datetime:
    # Avoid tzdata dependency on Windows/Oracle VM. IST = UTC+05:30.
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


def _database_url() -> str:
    """Use Neon/PostgreSQL when DATABASE_URL is set; otherwise use local SQLite."""
    raw = os.getenv("DATABASE_URL", "").strip()
    if raw:
        # Neon usually gives postgresql://...; SQLAlchemy needs a driver name for psycopg2.
        if raw.startswith("postgresql://"):
            raw = raw.replace("postgresql://", "postgresql+psycopg2://", 1)
        return raw
    return f"sqlite:///{LOCAL_DB_PATH.as_posix()}"


def _engine_instance() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(_database_url(), pool_pre_ping=True, future=True)
    _init_db(_engine)
    return _engine


def _db_label() -> str:
    url = _database_url()
    if url.startswith("postgresql"):
        return "Neon/PostgreSQL via DATABASE_URL"
    return f"Local SQLite fallback: {LOCAL_DB_PATH}"


def _init_db(engine: Engine) -> None:
    global _db_initialized
    if _db_initialized:
        return

    dialect = engine.dialect.name
    if dialect == "postgresql":
        predictions_id = "id SERIAL PRIMARY KEY"
        runs_id = "id SERIAL PRIMARY KEY"
    else:
        predictions_id = "id INTEGER PRIMARY KEY AUTOINCREMENT"
        runs_id = "id INTEGER PRIMARY KEY AUTOINCREMENT"

    with engine.begin() as conn:
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS predictions (
                    {predictions_id},
                    symbol TEXT NOT NULL,
                    horizon_key TEXT NOT NULL,
                    horizon_days INTEGER NOT NULL,
                    predicted_on_date TEXT NOT NULL,
                    predicted_at TEXT NOT NULL,
                    latest_close REAL NOT NULL,
                    predicted_trend TEXT NOT NULL,
                    raw_trend TEXT,
                    confidence INTEGER,
                    probability_up REAL,
                    probability_neutral REAL,
                    probability_down REAL,
                    neutral_threshold_percent REAL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    actual_date TEXT,
                    actual_close REAL,
                    actual_return_percent REAL,
                    actual_trend TEXT,
                    is_correct INTEGER,
                    evaluated_at TEXT,
                    UNIQUE(symbol, horizon_key, predicted_on_date)
                )
                """
            )
        )
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS learning_runs (
                    {runs_id},
                    run_at TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    symbols_processed INTEGER NOT NULL DEFAULT 0,
                    predictions_saved INTEGER NOT NULL DEFAULT 0,
                    predictions_evaluated INTEGER NOT NULL DEFAULT 0,
                    models_trained INTEGER NOT NULL DEFAULT 0,
                    errors TEXT
                )
                """
            )
        )
    _db_initialized = True


def save_prediction_from_analysis(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Store the current prediction so it can be checked after the target trading day arrives."""
    symbol = analysis.get("symbol")
    latest = analysis.get("latest") or {}
    prediction = analysis.get("prediction") or {}
    if not symbol or not latest.get("date") or latest.get("close") is None:
        return {"saved": 0, "reason": "Missing symbol/latest data"}

    predicted_on_date = str(latest["date"])[:10]
    latest_close = float(latest["close"])
    now = _now_ist().strftime("%Y-%m-%d %H:%M:%S")
    saved = 0

    engine = _engine_instance()
    with engine.begin() as conn:
        for key in ["next_day", "next_5_day"]:
            pred = prediction.get(key) or {}
            if not pred:
                continue
            horizon_days = 1 if key == "next_day" else 5
            conn.execute(
                text(
                    """
                    INSERT INTO predictions (
                        symbol, horizon_key, horizon_days, predicted_on_date, predicted_at,
                        latest_close, predicted_trend, raw_trend, confidence, probability_up,
                        probability_neutral, probability_down, neutral_threshold_percent, status
                    ) VALUES (
                        :symbol, :horizon_key, :horizon_days, :predicted_on_date, :predicted_at,
                        :latest_close, :predicted_trend, :raw_trend, :confidence, :probability_up,
                        :probability_neutral, :probability_down, :neutral_threshold_percent, 'pending'
                    )
                    ON CONFLICT(symbol, horizon_key, predicted_on_date) DO UPDATE SET
                        predicted_at=excluded.predicted_at,
                        latest_close=excluded.latest_close,
                        predicted_trend=excluded.predicted_trend,
                        raw_trend=excluded.raw_trend,
                        confidence=excluded.confidence,
                        probability_up=excluded.probability_up,
                        probability_neutral=excluded.probability_neutral,
                        probability_down=excluded.probability_down,
                        neutral_threshold_percent=excluded.neutral_threshold_percent,
                        status=CASE WHEN predictions.status='evaluated' THEN predictions.status ELSE 'pending' END
                    """
                ),
                {
                    "symbol": symbol,
                    "horizon_key": key,
                    "horizon_days": horizon_days,
                    "predicted_on_date": predicted_on_date,
                    "predicted_at": now,
                    "latest_close": latest_close,
                    "predicted_trend": pred.get("trend"),
                    "raw_trend": pred.get("raw_trend"),
                    "confidence": pred.get("confidence"),
                    "probability_up": pred.get("probability_up"),
                    "probability_neutral": pred.get("probability_neutral"),
                    "probability_down": pred.get("probability_down"),
                    "neutral_threshold_percent": pred.get("neutral_threshold_percent"),
                },
            )
            saved += 1
    return {"saved": saved, "predicted_on_date": predicted_on_date, "database": _db_label()}


def evaluate_pending_predictions(symbol: str, history_df: pd.DataFrame) -> Dict[str, Any]:
    """Compare stored predictions with actual close when the next/5th trading day is available."""
    normalized = normalize_symbol(symbol)
    if history_df is None or history_df.empty:
        return {"evaluated": 0, "pending": 0}

    df = history_df.copy()
    df["DateKey"] = pd.to_datetime(df["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df = df.dropna(subset=["DateKey", "Close"]).reset_index(drop=True)
    date_to_index = {row["DateKey"]: idx for idx, row in df.iterrows()}

    evaluated = 0
    still_pending = 0
    now = _now_ist().strftime("%Y-%m-%d %H:%M:%S")

    engine = _engine_instance()
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT * FROM predictions WHERE symbol=:symbol AND status='pending' ORDER BY predicted_on_date ASC"),
            {"symbol": normalized},
        ).mappings().all()

        for row in rows:
            predicted_date = row["predicted_on_date"]
            if predicted_date not in date_to_index:
                still_pending += 1
                continue
            base_idx = date_to_index[predicted_date]
            target_idx = base_idx + int(row["horizon_days"])
            if target_idx >= len(df):
                still_pending += 1
                continue

            base_close = float(row["latest_close"])
            actual_row = df.iloc[target_idx]
            actual_close = float(actual_row["Close"])
            actual_return = (actual_close / base_close - 1.0) if base_close else 0.0
            threshold = float(row["neutral_threshold_percent"] or 0.0) / 100.0
            if actual_return > threshold:
                actual_trend = "Bullish"
            elif actual_return < -threshold:
                actual_trend = "Bearish"
            else:
                actual_trend = "Neutral"

            is_correct = 1 if str(row["predicted_trend"]) == actual_trend else 0
            conn.execute(
                text(
                    """
                    UPDATE predictions
                    SET status='evaluated', actual_date=:actual_date, actual_close=:actual_close,
                        actual_return_percent=:actual_return_percent, actual_trend=:actual_trend,
                        is_correct=:is_correct, evaluated_at=:evaluated_at
                    WHERE id=:id
                    """
                ),
                {
                    "actual_date": str(actual_row["DateKey"]),
                    "actual_close": actual_close,
                    "actual_return_percent": round(actual_return * 100, 4),
                    "actual_trend": actual_trend,
                    "is_correct": is_correct,
                    "evaluated_at": now,
                    "id": int(row["id"]),
                },
            )
            evaluated += 1

    return {"evaluated": evaluated, "pending": still_pending}


def _fetch_stock_and_market(symbol: str, period: str = "5y") -> tuple[pd.DataFrame, pd.DataFrame | None]:
    normalized = normalize_symbol(symbol)
    history = fetch_history(normalized, period=period, interval="1d")
    enriched = add_indicators(history)
    market_enriched = None
    try:
        market_history = fetch_history("^NSEI", period=period, interval="1d")
        market_enriched = add_indicators(market_history)
    except Exception:
        market_enriched = None
    return enriched, market_enriched


def run_daily_learning_cycle(symbols: List[str] | None = None, mode: str = "manual") -> Dict[str, Any]:
    """
    Daily workflow:
    1) fetch updated data,
    2) evaluate old predictions whose result is now known,
    3) retrain saved models with newest history,
    4) create/store today's fresh predictions.
    """
    target_symbols = symbols or [item["symbol"] for item in DEFAULT_SYMBOLS]
    started = _now_ist().strftime("%Y-%m-%d %H:%M:%S")
    summary: Dict[str, Any] = {
        "version": "v8-deploy-neon-auto-learning",
        "run_at_ist": started,
        "mode": mode,
        "database": _db_label(),
        "symbols": {},
        "symbols_processed": 0,
        "predictions_saved": 0,
        "predictions_evaluated": 0,
        "models_trained": 0,
        "errors": [],
    }

    for symbol in target_symbols:
        normalized = normalize_symbol(symbol)
        item: Dict[str, Any] = {"symbol": normalized}
        try:
            enriched, market = _fetch_stock_and_market(normalized, period="5y")
            eval_result = evaluate_pending_predictions(normalized, enriched)
            train_result = train_models_for_symbol(enriched, normalized, market_df=market)
            analysis = analyze_stock(enriched, normalized, market_df=market)
            save_result = save_prediction_from_analysis(analysis)

            trained_count = sum(1 for model in (train_result.get("models") or {}).values() if model.get("trained"))
            item.update(
                {
                    "evaluated": eval_result.get("evaluated", 0),
                    "still_pending": eval_result.get("pending", 0),
                    "trained_models": trained_count,
                    "saved_predictions": save_result.get("saved", 0),
                    "latest_date": analysis.get("latest", {}).get("date"),
                    "next_day_prediction": analysis.get("prediction", {}).get("next_day", {}).get("trend"),
                    "next_5_day_prediction": analysis.get("prediction", {}).get("next_5_day", {}).get("trend"),
                }
            )
            summary["symbols_processed"] += 1
            summary["predictions_evaluated"] += int(eval_result.get("evaluated", 0))
            summary["models_trained"] += trained_count
            summary["predictions_saved"] += int(save_result.get("saved", 0))
        except Exception as exc:  # noqa: BLE001
            message = f"{normalized}: {exc}"
            item["error"] = str(exc)
            summary["errors"].append(message)
        summary["symbols"][normalized] = item

    engine = _engine_instance()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO learning_runs (
                    run_at, mode, symbols_processed, predictions_saved,
                    predictions_evaluated, models_trained, errors
                ) VALUES (
                    :run_at, :mode, :symbols_processed, :predictions_saved,
                    :predictions_evaluated, :models_trained, :errors
                )
                """
            ),
            {
                "run_at": started,
                "mode": mode,
                "symbols_processed": summary["symbols_processed"],
                "predictions_saved": summary["predictions_saved"],
                "predictions_evaluated": summary["predictions_evaluated"],
                "models_trained": summary["models_trained"],
                "errors": "\n".join(summary["errors"]),
            },
        )
    return summary


def get_learning_status(symbol: str | None = None, limit: int = 20) -> Dict[str, Any]:
    normalized = normalize_symbol(symbol) if symbol else None
    engine = _engine_instance()
    with engine.begin() as conn:
        if normalized:
            stats = conn.execute(
                text(
                    """
                    SELECT
                        COUNT(*) AS total,
                        SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending,
                        SUM(CASE WHEN status='evaluated' THEN 1 ELSE 0 END) AS evaluated,
                        SUM(CASE WHEN status='evaluated' AND is_correct=1 THEN 1 ELSE 0 END) AS correct
                    FROM predictions WHERE symbol=:symbol
                    """
                ),
                {"symbol": normalized},
            ).mappings().first()
            rows = conn.execute(
                text(
                    """
                    SELECT * FROM predictions WHERE symbol=:symbol
                    ORDER BY predicted_on_date DESC, horizon_key ASC LIMIT :limit
                    """
                ),
                {"symbol": normalized, "limit": limit},
            ).mappings().all()
        else:
            stats = conn.execute(
                text(
                    """
                    SELECT
                        COUNT(*) AS total,
                        SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending,
                        SUM(CASE WHEN status='evaluated' THEN 1 ELSE 0 END) AS evaluated,
                        SUM(CASE WHEN status='evaluated' AND is_correct=1 THEN 1 ELSE 0 END) AS correct
                    FROM predictions
                    """
                )
            ).mappings().first()
            rows = conn.execute(
                text("SELECT * FROM predictions ORDER BY predicted_on_date DESC, horizon_key ASC LIMIT :limit"),
                {"limit": limit},
            ).mappings().all()

        last_run = conn.execute(text("SELECT * FROM learning_runs ORDER BY id DESC LIMIT 1")).mappings().first()

    total = int((stats or {}).get("total") or 0)
    pending = int((stats or {}).get("pending") or 0)
    evaluated = int((stats or {}).get("evaluated") or 0)
    correct = int((stats or {}).get("correct") or 0)
    accuracy = round((correct / evaluated * 100), 2) if evaluated else None
    history = [dict(row) for row in rows]
    return {
        "symbol": normalized or "ALL",
        "database": _db_label(),
        "total_predictions": total,
        "pending_predictions": pending,
        "evaluated_predictions": evaluated,
        "correct_predictions": correct,
        "learning_accuracy": accuracy,
        "recent_predictions": history,
        "last_run": dict(last_run) if last_run else None,
        "note": "Auto-learning evaluates stored predictions only after the target trading day data becomes available, then retrains saved models with updated history.",
    }


def start_daily_scheduler() -> Dict[str, Any]:
    """Start a lightweight background scheduler. It runs once per IST day after 16:10."""
    global _scheduler_started
    with _scheduler_lock:
        if _scheduler_started:
            return {"started": False, "message": "Scheduler already running"}
        _scheduler_started = True

    def _loop() -> None:
        global _last_scheduler_run_date
        while True:
            try:
                now = _now_ist()
                today = now.strftime("%Y-%m-%d")
                # NSE regular close is around 15:30 IST. Run after 16:10 IST to allow public data to update.
                if now.hour > 16 or (now.hour == 16 and now.minute >= 10):
                    if _last_scheduler_run_date != today:
                        run_daily_learning_cycle(mode="scheduled")
                        _last_scheduler_run_date = today
            except Exception:
                # Keep scheduler alive even if one data run fails.
                pass
            time.sleep(30 * 60)

    thread = threading.Thread(target=_loop, daemon=True, name="daily-learning-scheduler")
    thread.start()
    return {"started": True, "message": "Daily auto-learning scheduler started. It runs after 16:10 IST when the backend is alive."}
