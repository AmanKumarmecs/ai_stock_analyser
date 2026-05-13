from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

FEATURES = [
    "Return_1",
    "Return_2",
    "Return_3",
    "Return_5",
    "Return_10",
    "Return_20",
    "MA20_Gap_Pct",
    "MA50_Gap_Pct",
    "MA100_Gap_Pct",
    "SMA20_Slope_5",
    "SMA50_Slope_5",
    "RSI_14",
    "RSI_Change_5",
    "MACD_Hist",
    "MACD_Hist_Slope_3",
    "Volume_Ratio",
    "Volume_Ratio_5",
    "Volume_Change_5",
    "Volatility_20",
    "Daily_Range_Pct",
    "Open_Close_Pct",
    "Gap_Open_Pct",
    "ATR_14_Pct",
    "BB_Position",
    "Close_Position_20",
    "Close_Position_50",
    "Plus_DI_20",
    "Minus_DI_20",
    "ADX_20",
    "DMI20_Spread",
    "DMI20_Spread_Change_3",
    "Plus_DI_50",
    "Minus_DI_50",
    "ADX_50",
    "DMI50_Spread",
]

MODEL_DIR = Path(os.getenv("MODEL_DIR", str(Path(__file__).resolve().parents[2] / "models")))
MODEL_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PACK_PATH = MODEL_DIR / "model_pack.joblib"
MODEL_MANIFEST_PATH = MODEL_DIR / "model_manifest.json"
_MODEL_PACK_CACHE: Dict[str, Any] | None = None
_MODEL_PACK_CACHE_MTIME: float | None = None


def _load_model_pack() -> Dict[str, Any] | None:
    """Load the deployment model pack if it exists. Cached by file mtime for Koyeb memory efficiency."""
    global _MODEL_PACK_CACHE, _MODEL_PACK_CACHE_MTIME
    if not MODEL_PACK_PATH.exists():
        return None
    try:
        mtime = MODEL_PACK_PATH.stat().st_mtime
        if _MODEL_PACK_CACHE is not None and _MODEL_PACK_CACHE_MTIME == mtime:
            return _MODEL_PACK_CACHE
        _MODEL_PACK_CACHE = joblib.load(MODEL_PACK_PATH)
        _MODEL_PACK_CACHE_MTIME = mtime
        return _MODEL_PACK_CACHE
    except Exception:
        return None


def _pack_horizon_package(symbol: str, horizon_key: str) -> Dict[str, Any] | None:
    pack = _load_model_pack()
    if not pack:
        return None
    symbols = pack.get("symbols") or {}
    return (symbols.get(symbol) or {}).get(horizon_key)


MARKET_FEATURES = [
    "NIFTY_Return_1",
    "NIFTY_Return_5",
    "NIFTY_MA20_Gap_Pct",
    "NIFTY_RSI_14",
    "NIFTY_MACD_Hist",
    "NIFTY_DMI20_Spread",
    "NIFTY_ADX_20",
]

LABEL_TO_TREND = {-1: "Bearish", 0: "Neutral", 1: "Bullish"}
TREND_TO_LABEL = {v: k for k, v in LABEL_TO_TREND.items()}


@dataclass
class HorizonConfig:
    key: str
    title: str
    horizon: int
    neutral_threshold: float
    confidence_filter: float = 0.60


HORIZONS = [
    HorizonConfig(
        key="next_day",
        title="Next trading day close direction",
        horizon=1,
        neutral_threshold=0.0015,  # 0.15%; tiny next-day moves are treated as Neutral noise.
    ),
    HorizonConfig(
        key="next_5_day",
        title="Next 5 trading day trend",
        horizon=5,
        neutral_threshold=0.0075,  # 0.75%; filters small 5-day moves.
    ),
]


def analyze_stock(df: pd.DataFrame, symbol: str, market_df: pd.DataFrame | None = None) -> Dict[str, Any]:
    """Create seller-friendly stock analysis with Neutral filtering and NIFTY context."""
    if len(df) < 80:
        raise ValueError("At least 80 data points are required for a meaningful Version 7 trained analysis")

    prepared = _attach_market_features(df, market_df)
    clean = prepared.dropna(subset=["Close"]).reset_index(drop=True)
    latest = clean.iloc[-1]
    previous = clean.iloc[-2]

    market_context = _market_context(market_df)

    predictions: Dict[str, Any] = {}
    for config in HORIZONS:
        predictions[config.key] = _predict_for_horizon(clean, config, market_context, symbol)

    # Use next-day as the primary top-card prediction because that is the question users ask first.
    primary = predictions["next_day"]
    five_day = predictions["next_5_day"]

    risk_score, risk_level, risk_reasons = _risk(latest)
    latest_close = float(latest["Close"])
    prev_close = float(previous["Close"])
    change = latest_close - prev_close
    change_pct = (change / prev_close * 100) if prev_close else 0.0

    support, resistance = _support_resistance(clean)
    indicators = _indicator_snapshot(latest)
    reasons = _build_better_reasons(
        latest=latest,
        previous=previous,
        primary=primary,
        five_day=five_day,
        market_context=market_context,
        risk_reasons=risk_reasons,
    )
    summary = _summary(symbol, primary, five_day, risk_level, market_context, reasons)

    return {
        "symbol": symbol,
        "version": "v9",
        "latest": {
            "date": str(latest.get("Date", ""))[:19],
            "open": _round(latest.get("Open")),
            "high": _round(latest.get("High")),
            "low": _round(latest.get("Low")),
            "close": _round(latest_close),
            "volume": int(latest.get("Volume", 0) or 0),
            "change": _round(change),
            "change_percent": _round(change_pct),
        },
        "prediction": {
            "trend": primary["trend"],
            "probability_up": primary["probability_up"],
            "confidence": primary["confidence"],
            "risk_level": risk_level,
            "risk_score": risk_score,
            "support": support,
            "resistance": resistance,
            "model_note": (
                "Version 9 uses GitHub Actions/Kaggle-trained model packs when available, plus technical indicators, DMI/ADX, Neutral filtering, backtest accuracy, and NIFTY 50 context."
            ),
            "confidence_filter": "Bullish/Bearish is shown only when confidence is strong; otherwise the output becomes Neutral/Avoid.",
            "next_day": primary,
            "next_5_day": five_day,
        },
        "market_context": market_context,
        "indicators": indicators,
        "reasons": reasons,
        "summary": summary,
        "disclaimer": "Demo/educational analysis only. Not financial advice. Free public data can be delayed or incomplete.",
    }


def _attach_market_features(stock_df: pd.DataFrame, market_df: pd.DataFrame | None) -> pd.DataFrame:
    out = stock_df.copy()
    if market_df is None or market_df.empty:
        for col in MARKET_FEATURES:
            out[col] = 0.0 if col != "NIFTY_RSI_14" else 50.0
        return out

    market = market_df.copy()
    market["DateKey"] = pd.to_datetime(market["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    out["DateKey"] = pd.to_datetime(out["Date"], errors="coerce").dt.strftime("%Y-%m-%d")

    keep = [
        "DateKey",
        "Return_1",
        "Return_5",
        "MA20_Gap_Pct",
        "RSI_14",
        "MACD_Hist",
        "DMI20_Spread",
        "ADX_20",
    ]
    market = market[[c for c in keep if c in market.columns]].copy()
    market = market.rename(
        columns={
            "Return_1": "NIFTY_Return_1",
            "Return_5": "NIFTY_Return_5",
            "MA20_Gap_Pct": "NIFTY_MA20_Gap_Pct",
            "RSI_14": "NIFTY_RSI_14",
            "MACD_Hist": "NIFTY_MACD_Hist",
            "DMI20_Spread": "NIFTY_DMI20_Spread",
            "ADX_20": "NIFTY_ADX_20",
        }
    )
    out = out.merge(market, on="DateKey", how="left")
    for col in MARKET_FEATURES:
        if col not in out.columns:
            out[col] = np.nan
        out[col] = out[col].ffill().bfill()
    return out.drop(columns=["DateKey"], errors="ignore")


def _predict_for_horizon(df: pd.DataFrame, config: HorizonConfig, market_context: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    ml_probs, model_note, backtest = _ml_distribution(df, config, symbol)
    rule_probs, rule_reasons = _rule_distribution(df.iloc[-1], df.iloc[-2], config, market_context)

    if ml_probs is None:
        final_probs = rule_probs
        engine = "Rule-based fallback"
    else:
        final_probs = {
            label: (0.68 * ml_probs.get(label, 0.0)) + (0.32 * rule_probs.get(label, 0.0))
            for label in [-1, 0, 1]
        }
        engine = "ML + rules"

    final_probs = _normalise_probs(final_probs)
    raw_label = max(final_probs, key=final_probs.get)
    label, confidence, filter_reason = _apply_confidence_filter(final_probs, config.confidence_filter)

    return {
        "horizon_key": config.key,
        "title": config.title,
        "trend": LABEL_TO_TREND[label],
        "raw_trend": LABEL_TO_TREND[raw_label],
        "confidence": int(round(confidence * 100)),
        "probability_up": _round(final_probs.get(1, 0) * 100),
        "probability_neutral": _round(final_probs.get(0, 0) * 100),
        "probability_down": _round(final_probs.get(-1, 0) * 100),
        "neutral_threshold_percent": _round(config.neutral_threshold * 100, 2),
        "confidence_filter_percent": int(round(config.confidence_filter * 100)),
        "filter_reason": filter_reason,
        "model_engine": engine,
        "model_note": model_note,
        "backtest": backtest,
        "rule_reasons": rule_reasons,
    }




def _safe_model_name(symbol: str, horizon_key: str) -> str:
    cleaned = symbol.upper().replace("^", "INDEX_").replace(".", "_").replace("/", "_").replace("-", "_")
    return f"{cleaned}_{horizon_key}.joblib"


def _model_path(symbol: str, horizon_key: str) -> Path:
    return MODEL_DIR / _safe_model_name(symbol, horizon_key)


def get_training_status(symbol: str) -> Dict[str, Any]:
    status = {"symbol": symbol, "trained": False, "model_pack_available": MODEL_PACK_PATH.exists(), "models": {}}
    pack = _load_model_pack()
    for config in HORIZONS:
        pack_pkg = _pack_horizon_package(symbol, config.key)
        if pack_pkg:
            status["models"][config.key] = {
                "available": True,
                "source": "model_pack.joblib",
                "trained_at": pack_pkg.get("trained_at"),
                "samples": pack_pkg.get("samples"),
                "backtest": pack_pkg.get("backtest"),
                "model_type": pack_pkg.get("model_type"),
            }
            status["trained"] = True
            continue

        path = _model_path(symbol, config.key)
        if path.exists():
            try:
                package = joblib.load(path)
                status["models"][config.key] = {
                    "available": True,
                    "source": str(path.name),
                    "trained_at": package.get("trained_at"),
                    "samples": package.get("samples"),
                    "backtest": package.get("backtest"),
                    "model_type": package.get("model_type"),
                }
                status["trained"] = True
            except Exception as exc:  # noqa: BLE001
                status["models"][config.key] = {"available": False, "error": str(exc)}
        else:
            status["models"][config.key] = {"available": False}
    if pack:
        status["model_pack"] = {
            "version": pack.get("version"),
            "trained_at": pack.get("trained_at"),
            "symbols": sorted(list((pack.get("symbols") or {}).keys())),
            "size_mb": _round(MODEL_PACK_PATH.stat().st_size / (1024 * 1024)) if MODEL_PACK_PATH.exists() else None,
        }
    return status

def train_models_for_symbol(df: pd.DataFrame, symbol: str, market_df: pd.DataFrame | None = None) -> Dict[str, Any]:
    prepared = _attach_market_features(df, market_df)
    results: Dict[str, Any] = {}
    for config in HORIZONS:
        results[config.key] = _train_horizon_model(prepared, symbol, config)
    return {
        "symbol": symbol,
        "version": "v9",
        "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "models": results,
        "message": "Training completed. Version 9 training is designed for Kaggle/GitHub Actions, not the free backend runtime.",
    }


def _train_horizon_model(df: pd.DataFrame, symbol: str, config: HorizonConfig) -> Dict[str, Any]:
    data = df.copy()
    future_return = data["Close"].shift(-config.horizon) / data["Close"] - 1
    data["Target"] = np.select(
        [future_return > config.neutral_threshold, future_return < -config.neutral_threshold],
        [1, -1],
        default=0,
    )
    all_features = FEATURES + [f for f in MARKET_FEATURES if f in data.columns]
    data = data.replace([np.inf, -np.inf], np.nan).dropna(subset=all_features + ["Target"])
    trainable = data.iloc[: -config.horizon].copy() if len(data) > config.horizon else data.iloc[0:0]

    if len(trainable) < 220:
        return {"trained": False, "error": f"Not enough clean rows to train. Need about 220+, got {len(trainable)}."}
    if trainable["Target"].nunique() < 2:
        return {"trained": False, "error": "Only one target class found; training would be unreliable."}

    X = trainable[all_features]
    y = trainable["Target"].astype(int)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.22, shuffle=False)
    if y_train.nunique() < 2:
        return {"trained": False, "error": "Training split had only one target class."}

    models = [
        RandomForestClassifier(
            n_estimators=220,
            max_depth=9,
            min_samples_leaf=3,
            random_state=100 + config.horizon,
            class_weight="balanced_subsample",
            n_jobs=-1,
        ),
        ExtraTreesClassifier(
            n_estimators=220,
            max_depth=9,
            min_samples_leaf=3,
            random_state=200 + config.horizon,
            class_weight="balanced",
            n_jobs=-1,
        ),
        GradientBoostingClassifier(
            n_estimators=110,
            learning_rate=0.055,
            max_depth=3,
            random_state=300 + config.horizon,
        ),
    ]

    fitted = []
    for model in models:
        try:
            model.fit(X_train, y_train)
            fitted.append(model)
        except Exception:
            continue
    if not fitted:
        return {"trained": False, "error": "No model could be trained successfully."}

    test_probs = _ensemble_predict_proba(fitted, X_test)
    test_preds = [_label_from_proba(row, config.confidence_filter)[0] for row in test_probs]
    acc_all = float(accuracy_score(y_test, test_preds)) if len(y_test) else None
    confident_mask = [pred != 0 for pred in test_preds]
    confident_total = int(sum(confident_mask))
    if confident_total:
        y_conf = np.array(y_test)[confident_mask]
        pred_conf = np.array(test_preds)[confident_mask]
        acc_conf = float(accuracy_score(y_conf, pred_conf))
    else:
        acc_conf = None

    # Train final package on all available known history after measuring holdout.
    final_models = []
    for model in models:
        try:
            model.fit(X, y)
            final_models.append(model)
        except Exception:
            continue

    backtest = {
        "accuracy_all_signals": _round(acc_all * 100) if acc_all is not None else None,
        "accuracy_confident_only": _round(acc_conf * 100) if acc_conf is not None else None,
        "confident_signal_coverage": _round((confident_total / len(y_test) * 100) if len(y_test) else 0),
        "test_samples": int(len(y_test)),
        "confident_samples": confident_total,
        "note": "Version 9 trained holdout test. Confident-only accuracy can improve because weak setups are filtered as Neutral/Avoid.",
    }
    package = {
        "symbol": symbol,
        "horizon_key": config.key,
        "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model_type": "RandomForest + ExtraTrees + GradientBoosting ensemble",
        "features": all_features,
        "models": final_models,
        "samples": int(len(X)),
        "backtest": backtest,
        "confidence_filter": config.confidence_filter,
        "neutral_threshold": config.neutral_threshold,
    }
    joblib.dump(package, _model_path(symbol, config.key))
    return {
        "trained": True,
        "model_type": package["model_type"],
        "samples": package["samples"],
        "trained_at": package["trained_at"],
        "backtest": backtest,
    }


def _saved_model_distribution(df: pd.DataFrame, config: HorizonConfig, symbol: str) -> Tuple[Dict[int, float] | None, str, Dict[str, Any]] | None:
    package = _pack_horizon_package(symbol, config.key)
    package_source = "model_pack.joblib"

    if package is None:
        path = _model_path(symbol, config.key)
        if not path.exists():
            return None
        try:
            package = joblib.load(path)
            package_source = path.name
        except Exception:  # noqa: BLE001
            return None

    try:
        features = package.get("features") or []
        data = df.copy().replace([np.inf, -np.inf], np.nan)
        missing = [f for f in features if f not in data.columns]
        if missing:
            return None
        latest_features = data[features].dropna().tail(1)
        if latest_features.empty:
            return None
        probs = _ensemble_predict_proba(package.get("models", []), latest_features)[0]
        note = (
            f"Saved Version 9 symbol-trained model loaded from {package_source}. "
            f"Trained at {package.get('trained_at')} using {package.get('samples')} samples."
        )
        return probs, note, package.get("backtest") or _empty_backtest("Saved model has no backtest metadata.")
    except Exception:  # noqa: BLE001
        return None

def _ensemble_predict_proba(models: List[Any], X: pd.DataFrame) -> List[Dict[int, float]]:
    if not models:
        return [{-1: 0.33, 0: 0.34, 1: 0.33} for _ in range(len(X))]
    rows = []
    accumulator = [ {-1: 0.0, 0: 0.0, 1: 0.0} for _ in range(len(X)) ]
    used = 0
    for model in models:
        if not hasattr(model, "predict_proba"):
            continue
        try:
            probs = model.predict_proba(X)
            classes = getattr(model, "classes_", np.array([-1, 0, 1]))
            for idx, row in enumerate(probs):
                d = _proba_dict(classes, row)
                for label in [-1, 0, 1]:
                    accumulator[idx][label] += d[label]
            used += 1
        except Exception:
            continue
    if used == 0:
        return [{-1: 0.33, 0: 0.34, 1: 0.33} for _ in range(len(X))]
    for idx in range(len(X)):
        rows.append(_normalise_probs({label: accumulator[idx][label] / used for label in [-1, 0, 1]}))
    return rows
def _ml_distribution(df: pd.DataFrame, config: HorizonConfig, symbol: str) -> Tuple[Dict[int, float] | None, str, Dict[str, Any]]:
    saved = _saved_model_distribution(df, config, symbol)
    if saved is not None:
        return saved

    data = df.copy()
    future_return = data["Close"].shift(-config.horizon) / data["Close"] - 1
    data["Target"] = np.select(
        [future_return > config.neutral_threshold, future_return < -config.neutral_threshold],
        [1, -1],
        default=0,
    )
    all_features = FEATURES + [f for f in MARKET_FEATURES if f in data.columns]
    data = data.replace([np.inf, -np.inf], np.nan).dropna(subset=all_features + ["Target"])

    # Remove the last rows whose future target is not known for training, but still use latest features for prediction.
    trainable = data.iloc[: -config.horizon].copy() if len(data) > config.horizon else data.iloc[0:0]
    latest_features = data[all_features].iloc[[-1]] if len(data) else None

    if latest_features is None or len(trainable) < 120 or trainable["Target"].nunique() < 2:
        return (
            None,
            "Not enough clean history/classes for ML; using rule-based technical scoring.",
            _empty_backtest("Not enough history/classes for backtest."),
        )

    X = trainable[all_features]
    y = trainable["Target"].astype(int)

    try:
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, shuffle=False)
        if y_train.nunique() < 2:
            return (
                None,
                "Training split had only one target class; using rule-based technical scoring.",
                _empty_backtest("Training split had only one target class."),
            )
        model = RandomForestClassifier(
            n_estimators=260,
            max_depth=7,
            min_samples_leaf=4,
            random_state=42 + config.horizon,
            class_weight="balanced_subsample",
        )
        model.fit(X_train, y_train)

        probability_rows = model.predict_proba(X_test)
        test_preds = [_label_from_proba(_proba_dict(model.classes_, row), config.confidence_filter)[0] for row in probability_rows]
        acc_all = float(accuracy_score(y_test, test_preds)) if len(y_test) else None
        confident_mask = [pred != 0 for pred in test_preds]
        confident_total = int(sum(confident_mask))
        if confident_total:
            y_conf = np.array(y_test)[confident_mask]
            pred_conf = np.array(test_preds)[confident_mask]
            acc_conf = float(accuracy_score(y_conf, pred_conf))
        else:
            acc_conf = None

        latest_row_probs = model.predict_proba(latest_features)[0]
        probabilities = _proba_dict(model.classes_, latest_row_probs)

        backtest = {
            "accuracy_all_signals": _round(acc_all * 100) if acc_all is not None else None,
            "accuracy_confident_only": _round(acc_conf * 100) if acc_conf is not None else None,
            "confident_signal_coverage": _round((confident_total / len(y_test) * 100) if len(y_test) else 0),
            "test_samples": int(len(y_test)),
            "confident_samples": confident_total,
            "note": "Backtest uses the latest 25% chronological holdout. It is a demo estimate, not a guarantee.",
        }
        note = "On-request fallback Random Forest used. Version 9 fallback model used until the next GitHub Actions/Kaggle training cycle saves a model pack."
        return probabilities, note, backtest
    except Exception as exc:  # noqa: BLE001
        return None, f"ML model could not run cleanly, using rule-based scoring. Reason: {exc}", _empty_backtest(str(exc))


def _rule_distribution(
    latest: pd.Series,
    previous: pd.Series,
    config: HorizonConfig,
    market_context: Dict[str, Any],
) -> Tuple[Dict[int, float], List[str]]:
    score = 0.0
    reasons: List[str] = []

    close = float(latest["Close"])
    prev_close = float(previous["Close"])
    rsi = _float(latest.get("RSI_14"), 50)
    sma20 = _float(latest.get("SMA_20"), close)
    sma50 = _float(latest.get("SMA_50"), close)
    macd_hist = _float(latest.get("MACD_Hist"), 0)
    plus_di20 = _float(latest.get("Plus_DI_20"), 0)
    minus_di20 = _float(latest.get("Minus_DI_20"), 0)
    adx20 = _float(latest.get("ADX_20"), 0)
    dmi20_spread = _float(latest.get("DMI20_Spread"), plus_di20 - minus_di20)
    plus_di50 = _float(latest.get("Plus_DI_50"), 0)
    minus_di50 = _float(latest.get("Minus_DI_50"), 0)
    adx50 = _float(latest.get("ADX_50"), 0)
    dmi50_spread = _float(latest.get("DMI50_Spread"), plus_di50 - minus_di50)
    vol_ratio = _float(latest.get("Volume_Ratio"), 1)
    ret1 = _float(latest.get("Return_1"), 0)
    ret5 = _float(latest.get("Return_5"), 0)
    nifty_score = _float(market_context.get("score"), 0.0)

    day_change_pct = ((close - prev_close) / prev_close * 100) if prev_close else 0

    if close > sma20:
        score += 0.20
        reasons.append("Price is above SMA 20, so short-term structure is supportive.")
    else:
        score -= 0.20
        reasons.append("Price is below SMA 20, so short-term structure is weak.")

    if close > sma50:
        score += 0.16
        reasons.append("Price is above SMA 50, which supports the broader short-term trend.")
    else:
        score -= 0.16
        reasons.append("Price is below SMA 50, which keeps the broader trend under pressure.")

    if macd_hist > 0:
        score += 0.14
        reasons.append("MACD histogram is positive, indicating improving momentum.")
    else:
        score -= 0.14
        reasons.append("MACD histogram is negative, indicating weaker momentum.")

    # DMI / ADX: +DI above -DI supports bullish direction; ADX confirms trend strength.
    if dmi20_spread > 2:
        score += 0.14
        reasons.append("20-period DMI is bullish because +DI is above -DI.")
    elif dmi20_spread < -2:
        score -= 0.14
        reasons.append("20-period DMI is bearish because -DI is above +DI.")
    else:
        reasons.append("20-period DMI is almost balanced, so direction is not strong.")

    if adx20 >= 25 and abs(dmi20_spread) > 2:
        score += 0.08 if dmi20_spread > 0 else -0.08
        reasons.append("ADX 20 is above 25, so the short-term DMI direction has stronger trend confirmation.")
    elif adx20 < 18:
        score *= 0.88
        reasons.append("ADX 20 is low, so the short-term trend is weak and confidence is reduced.")

    if dmi50_spread > 2 and adx50 >= 18:
        score += 0.06
        reasons.append("50-period DMI also supports a broader bullish structure.")
    elif dmi50_spread < -2 and adx50 >= 18:
        score -= 0.06
        reasons.append("50-period DMI also supports a broader bearish structure.")

    if 45 <= rsi <= 62:
        score += 0.08
        reasons.append("RSI is in a healthy zone, so momentum is not overheated.")
    elif 62 < rsi <= 70:
        score += 0.04
        reasons.append("RSI is positive but close to the overbought zone, so upside may need confirmation.")
    elif rsi > 70:
        score -= 0.10
        reasons.append("RSI is overbought, so reversal/profit-booking risk is higher.")
    elif rsi < 32:
        score += 0.04
        reasons.append("RSI is oversold, so a rebound is possible but risk remains high.")
    else:
        score -= 0.06
        reasons.append("RSI is below neutral, so momentum is still weak.")

    if vol_ratio > 1.25 and day_change_pct > 0:
        score += 0.10
        reasons.append("Volume is above average while price is rising, confirming buying interest.")
    elif vol_ratio > 1.25 and day_change_pct < 0:
        score -= 0.10
        reasons.append("Volume is above average while price is falling, confirming selling pressure.")
    elif vol_ratio < 0.75:
        score -= 0.03
        reasons.append("Volume is below average, so the latest move has weak confirmation.")

    if config.horizon == 1:
        if ret1 > 0 and ret5 > 0:
            score += 0.08
            reasons.append("Both 1-day and 5-day momentum are positive.")
        elif ret1 < 0 and ret5 < 0:
            score -= 0.08
            reasons.append("Both 1-day and 5-day momentum are negative.")
    else:
        if ret5 > 0.015:
            score += 0.12
            reasons.append("Recent 5-day return is strong, supporting the 5-day trend view.")
        elif ret5 < -0.015:
            score -= 0.12
            reasons.append("Recent 5-day return is weak, pressuring the 5-day trend view.")

    if nifty_score > 0.25:
        score += 0.09
        reasons.append("NIFTY 50 context is supportive, which improves the stock's bullish probability.")
    elif nifty_score < -0.25:
        score -= 0.09
        reasons.append("NIFTY 50 context is weak, which increases bearish pressure.")
    else:
        reasons.append("NIFTY 50 context is mixed, so confidence is reduced.")

    # Convert score to three-class probabilities.
    abs_score = min(abs(score), 1.0)
    neutral = max(0.12, 0.56 - abs_score * 0.55)
    directional = 1 - neutral
    if score >= 0:
        up = 0.50 + directional * 0.50
        down = 1 - up - neutral
    else:
        down = 0.50 + directional * 0.50
        up = 1 - down - neutral
    probabilities = _normalise_probs({1: max(up, 0.01), 0: max(neutral, 0.01), -1: max(down, 0.01)})
    return probabilities, reasons[:8]


def _apply_confidence_filter(probabilities: Dict[int, float], confidence_filter: float) -> Tuple[int, float, str]:
    label, confidence = _label_from_proba(probabilities, confidence_filter)
    if label == 0:
        if max(probabilities, key=probabilities.get) == 0:
            return label, confidence, "Neutral has the highest probability."
        return label, confidence, "Signal is below the confidence filter, so it is marked Neutral/Avoid."
    return label, confidence, "Signal passed the confidence filter."


def _label_from_proba(probabilities: Dict[int, float], confidence_filter: float) -> Tuple[int, float]:
    probs = _normalise_probs(probabilities)
    sorted_items = sorted(probs.items(), key=lambda item: item[1], reverse=True)
    top_label, top_prob = sorted_items[0]
    second_prob = sorted_items[1][1] if len(sorted_items) > 1 else 0.0

    # Do not force Bullish/Bearish if the model is not decisive.
    if top_label != 0 and (top_prob < confidence_filter or (top_prob - second_prob) < 0.08):
        return 0, top_prob
    return int(top_label), float(top_prob)


def _proba_dict(classes: np.ndarray, row: np.ndarray) -> Dict[int, float]:
    out = {-1: 0.0, 0: 0.0, 1: 0.0}
    for cls, value in zip(classes, row):
        out[int(cls)] = float(value)
    return _normalise_probs(out)


def _normalise_probs(probs: Dict[int, float]) -> Dict[int, float]:
    cleaned = {-1: max(float(probs.get(-1, 0)), 0.0), 0: max(float(probs.get(0, 0)), 0.0), 1: max(float(probs.get(1, 0)), 0.0)}
    total = sum(cleaned.values())
    if total <= 0:
        return {-1: 0.33, 0: 0.34, 1: 0.33}
    return {label: value / total for label, value in cleaned.items()}


def _empty_backtest(note: str) -> Dict[str, Any]:
    return {
        "accuracy_all_signals": None,
        "accuracy_confident_only": None,
        "confident_signal_coverage": None,
        "test_samples": 0,
        "confident_samples": 0,
        "note": note,
    }


def _market_context(market_df: pd.DataFrame | None) -> Dict[str, Any]:
    if market_df is None or market_df.empty or len(market_df.dropna(subset=["Close"])) < 2:
        return {
            "symbol": "^NSEI",
            "name": "NIFTY 50",
            "available": False,
            "trend": "Unavailable",
            "score": 0.0,
            "reasons": ["NIFTY 50 context could not be fetched from the free data source."],
        }

    df = market_df.dropna(subset=["Close"]).reset_index(drop=True)
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    close = float(latest["Close"])
    prev_close = float(prev["Close"])
    change = close - prev_close
    change_pct = change / prev_close * 100 if prev_close else 0
    sma20 = _float(latest.get("SMA_20"), close)
    sma50 = _float(latest.get("SMA_50"), close)
    rsi = _float(latest.get("RSI_14"), 50)
    macd_hist = _float(latest.get("MACD_Hist"), 0)
    nifty_dmi20 = _float(latest.get("DMI20_Spread"), 0)
    nifty_adx20 = _float(latest.get("ADX_20"), 0)

    score = 0.0
    reasons: List[str] = []
    if close > sma20:
        score += 0.22
        reasons.append("NIFTY 50 is above SMA 20, supporting short-term market sentiment.")
    else:
        score -= 0.22
        reasons.append("NIFTY 50 is below SMA 20, showing short-term market weakness.")
    if close > sma50:
        score += 0.16
        reasons.append("NIFTY 50 is above SMA 50, supporting broader market structure.")
    else:
        score -= 0.16
        reasons.append("NIFTY 50 is below SMA 50, weakening broader market structure.")
    if macd_hist > 0:
        score += 0.12
        reasons.append("NIFTY MACD histogram is positive.")
    else:
        score -= 0.12
        reasons.append("NIFTY MACD histogram is negative.")
    if change_pct > 0.25:
        score += 0.10
        reasons.append("Latest NIFTY daily move is positive.")
    elif change_pct < -0.25:
        score -= 0.10
        reasons.append("Latest NIFTY daily move is negative.")
    if nifty_dmi20 > 2 and nifty_adx20 >= 18:
        score += 0.08
        reasons.append("NIFTY DMI/ADX is supportive, showing positive market-direction strength.")
    elif nifty_dmi20 < -2 and nifty_adx20 >= 18:
        score -= 0.08
        reasons.append("NIFTY DMI/ADX is weak, showing negative market-direction strength.")
    if rsi > 70:
        score -= 0.05
        reasons.append("NIFTY RSI is overheated, so broad-market pullback risk exists.")
    elif rsi < 35:
        score -= 0.05
        reasons.append("NIFTY RSI is weak, so broad-market confidence is limited.")

    if score >= 0.25:
        trend = "Supportive"
    elif score <= -0.25:
        trend = "Weak"
    else:
        trend = "Mixed"

    return {
        "symbol": "^NSEI",
        "name": "NIFTY 50",
        "available": True,
        "trend": trend,
        "score": _round(score, 3),
        "date": str(latest.get("Date", ""))[:19],
        "close": _round(close),
        "change": _round(change),
        "change_percent": _round(change_pct),
        "rsi14": _round(rsi),
        "adx20": _round(nifty_adx20),
        "dmi20_spread": _round(nifty_dmi20),
        "sma20": _round(sma20),
        "sma50": _round(sma50),
        "reasons": reasons[:5],
    }


def _risk(latest: pd.Series) -> Tuple[int, str, List[str]]:
    risk = 35
    reasons: List[str] = []
    rsi = _float(latest.get("RSI_14"), 50)
    vol = _float(latest.get("Volatility_20"), 25)
    volume_ratio = _float(latest.get("Volume_Ratio"), 1)
    daily_range = _float(latest.get("Daily_Range_Pct"), 2)
    adx20 = _float(latest.get("ADX_20"), 20)

    if vol > 45:
        risk += 25
        reasons.append("20-day volatility is high, so movement risk is elevated.")
    elif vol > 30:
        risk += 12
        reasons.append("20-day volatility is moderate, so sudden movement is possible.")
    else:
        reasons.append("20-day volatility is relatively controlled.")

    if rsi > 72 or rsi < 28:
        risk += 16
        reasons.append("RSI is in an extreme zone, which can increase reversal risk.")
    if volume_ratio > 1.8:
        risk += 12
        reasons.append("Volume spike detected, so volatility may remain high.")
    if daily_range > 4:
        risk += 12
        reasons.append("Latest daily range is large, showing intraday volatility.")
    if adx20 < 15:
        risk += 6
        reasons.append("ADX 20 is low, so trend strength is weak and false-signal risk increases.")

    risk = int(max(0, min(100, risk)))
    if risk >= 70:
        level = "High"
    elif risk >= 45:
        level = "Medium"
    else:
        level = "Low"
    return risk, level, reasons


def _support_resistance(df: pd.DataFrame) -> Tuple[float | None, float | None]:
    recent = df.tail(30)
    if recent.empty:
        return None, None
    return _round(recent["Low"].min()), _round(recent["High"].max())


def _indicator_snapshot(latest: pd.Series) -> Dict[str, float | None]:
    return {
        "sma20": _round(latest.get("SMA_20")),
        "sma50": _round(latest.get("SMA_50")),
        "rsi14": _round(latest.get("RSI_14")),
        "rsi_change_5": _round(latest.get("RSI_Change_5")),
        "macd": _round(latest.get("MACD")),
        "macd_signal": _round(latest.get("MACD_Signal")),
        "macd_histogram": _round(latest.get("MACD_Hist")),
        "macd_hist_slope_3": _round(latest.get("MACD_Hist_Slope_3")),
        "plus_di_20": _round(latest.get("Plus_DI_20")),
        "minus_di_20": _round(latest.get("Minus_DI_20")),
        "adx_20": _round(latest.get("ADX_20")),
        "dmi20_spread": _round(latest.get("DMI20_Spread")),
        "plus_di_50": _round(latest.get("Plus_DI_50")),
        "minus_di_50": _round(latest.get("Minus_DI_50")),
        "adx_50": _round(latest.get("ADX_50")),
        "dmi50_spread": _round(latest.get("DMI50_Spread")),
        "volume_ratio": _round(latest.get("Volume_Ratio")),
        "volatility20": _round(latest.get("Volatility_20")),
        "atr14_percent": _round(latest.get("ATR_14_Pct")),
        "bb_position": _round(latest.get("BB_Position")),
        "close_position_20": _round(latest.get("Close_Position_20")),
        "close_position_50": _round(latest.get("Close_Position_50")),
        "volume_ratio_5": _round(latest.get("Volume_Ratio_5")),
        "gap_open_percent": _round(latest.get("Gap_Open_Pct")),
        "bollinger_upper": _round(latest.get("BB_Upper")),
        "bollinger_lower": _round(latest.get("BB_Lower")),
        "ma20_gap_percent": _round(latest.get("MA20_Gap_Pct")),
        "ma50_gap_percent": _round(latest.get("MA50_Gap_Pct")),
        "nifty_return_1": _round(latest.get("NIFTY_Return_1", 0) * 100),
        "nifty_return_5": _round(latest.get("NIFTY_Return_5", 0) * 100),
        "nifty_ma20_gap_percent": _round(latest.get("NIFTY_MA20_Gap_Pct", 0)),
        "nifty_adx_20": _round(latest.get("NIFTY_ADX_20", 0)),
        "nifty_dmi20_spread": _round(latest.get("NIFTY_DMI20_Spread", 0)),
    }


def _build_better_reasons(
    latest: pd.Series,
    previous: pd.Series,
    primary: Dict[str, Any],
    five_day: Dict[str, Any],
    market_context: Dict[str, Any],
    risk_reasons: List[str],
) -> List[str]:
    reasons: List[str] = []
    reasons.append(
        f"Next-day output is {primary['trend']} because up/down/neutral probabilities are "
        f"{primary['probability_up']}% / {primary['probability_down']}% / {primary['probability_neutral']}%."
    )
    reasons.append(
        f"Next 5 trading day output is {five_day['trend']} with {five_day['confidence']}% confidence."
    )
    reasons.append(primary.get("filter_reason", "Confidence filter applied."))

    close = float(latest["Close"])
    prev_close = float(previous["Close"])
    sma20 = _float(latest.get("SMA_20"), close)
    sma50 = _float(latest.get("SMA_50"), close)
    rsi = _float(latest.get("RSI_14"), 50)
    macd_hist = _float(latest.get("MACD_Hist"), 0)
    dmi20_spread = _float(latest.get("DMI20_Spread"), 0)
    adx20 = _float(latest.get("ADX_20"), 0)
    dmi50_spread = _float(latest.get("DMI50_Spread"), 0)
    adx50 = _float(latest.get("ADX_50"), 0)
    vol_ratio = _float(latest.get("Volume_Ratio"), 1)
    day_change = (close - prev_close) / prev_close * 100 if prev_close else 0

    if close > sma20 and close > sma50:
        reasons.append("Price is above both SMA 20 and SMA 50, so the trend structure is positive.")
    elif close < sma20 and close < sma50:
        reasons.append("Price is below both SMA 20 and SMA 50, so the trend structure is weak.")
    else:
        reasons.append("Price is between key moving averages, so the setup is mixed.")

    if macd_hist > 0:
        reasons.append("MACD histogram is positive, showing improving momentum.")
    else:
        reasons.append("MACD histogram is negative, showing weak momentum.")

    if dmi20_spread > 2 and adx20 >= 25:
        reasons.append("DMI/ADX confirms bullish strength: +DI is above -DI and ADX 20 shows a strong trend.")
    elif dmi20_spread < -2 and adx20 >= 25:
        reasons.append("DMI/ADX confirms bearish strength: -DI is above +DI and ADX 20 shows a strong trend.")
    elif adx20 < 18:
        reasons.append("ADX 20 is low, so the model reduces confidence because the current trend is weak.")
    else:
        reasons.append("DMI/ADX is mixed, so it is used as a confidence-control filter rather than a strong direction signal.")

    if dmi50_spread > 2 and adx50 >= 18:
        reasons.append("50-period DMI supports the broader bullish side.")
    elif dmi50_spread < -2 and adx50 >= 18:
        reasons.append("50-period DMI supports the broader bearish side.")

    if vol_ratio > 1.25 and day_change > 0:
        reasons.append("Volume is above average with price rise, confirming buying interest.")
    elif vol_ratio > 1.25 and day_change < 0:
        reasons.append("Volume is above average with price fall, confirming selling pressure.")
    else:
        reasons.append("Volume confirmation is not very strong, so prediction confidence is controlled.")

    if rsi > 70:
        reasons.append("RSI is overbought, so upside prediction is treated carefully.")
    elif rsi < 35:
        reasons.append("RSI is weak/oversold, so bearish risk is higher but rebound is possible.")
    else:
        reasons.append("RSI is not in an extreme zone, reducing immediate reversal risk.")

    if market_context.get("available"):
        reasons.append(f"NIFTY 50 market context is {market_context.get('trend')}, so broad-market impact is included.")
    else:
        reasons.append("NIFTY 50 context was unavailable, so the model relied more on stock-level data.")

    reasons.extend(risk_reasons[:2])

    seen = set()
    unique = []
    for reason in reasons:
        if reason not in seen:
            unique.append(reason)
            seen.add(reason)
    return unique[:10]


def _summary(symbol: str, primary: Dict[str, Any], five_day: Dict[str, Any], risk_level: str, market_context: Dict[str, Any], reasons: List[str]) -> str:
    return (
        f"{symbol} Version 7 trained analysis shows next trading day as {primary['trend']} "
        f"and next 5 trading days as {five_day['trend']}. The confidence filter is active, so unclear setups are marked "
        f"Neutral instead of forcing Bullish/Bearish. Current risk is {risk_level.lower()}, and NIFTY 50 context is "
        f"{str(market_context.get('trend', 'unavailable')).lower()}. {reasons[0]} "
        "This is demo/educational analysis, not financial advice."
    )


def _round(value, ndigits: int = 2):
    try:
        if pd.isna(value):
            return None
        return round(float(value), ndigits)
    except Exception:  # noqa: BLE001
        return None


def _float(value, default: float) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:  # noqa: BLE001
        return default
