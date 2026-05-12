from __future__ import annotations

import numpy as np
import pandas as pd


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add technical indicators without paid libraries."""
    out = df.copy()
    close = out["Close"].astype(float)
    high = out["High"].astype(float)
    low = out["Low"].astype(float)
    open_ = out.get("Open", close).astype(float)
    volume = out["Volume"].astype(float).replace(0, np.nan)

    out["Return_1"] = close.pct_change()
    out["Return_2"] = close.pct_change(2)
    out["Return_3"] = close.pct_change(3)
    out["Return_5"] = close.pct_change(5)
    out["Return_10"] = close.pct_change(10)
    out["Return_20"] = close.pct_change(20)

    out["SMA_10"] = close.rolling(10).mean()
    out["SMA_20"] = close.rolling(20).mean()
    out["SMA_50"] = close.rolling(50).mean()
    out["SMA_100"] = close.rolling(100).mean()
    out["SMA20_Slope_5"] = out["SMA_20"].pct_change(5) * 100
    out["SMA50_Slope_5"] = out["SMA_50"].pct_change(5) * 100

    out["EMA_12"] = close.ewm(span=12, adjust=False).mean()
    out["EMA_26"] = close.ewm(span=26, adjust=False).mean()
    out["MACD"] = out["EMA_12"] - out["EMA_26"]
    out["MACD_Signal"] = out["MACD"].ewm(span=9, adjust=False).mean()
    out["MACD_Hist"] = out["MACD"] - out["MACD_Signal"]
    out["MACD_Hist_Slope_3"] = out["MACD_Hist"].diff(3)

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out["RSI_14"] = 100 - (100 / (1 + rs))
    out["RSI_14"] = out["RSI_14"].fillna(50)
    out["RSI_Change_5"] = out["RSI_14"].diff(5)

    rolling_std = close.rolling(20).std()
    out["BB_Mid"] = out["SMA_20"]
    out["BB_Upper"] = out["SMA_20"] + (2 * rolling_std)
    out["BB_Lower"] = out["SMA_20"] - (2 * rolling_std)
    bb_range = (out["BB_Upper"] - out["BB_Lower"]).replace(0, np.nan)
    out["BB_Position"] = (close - out["BB_Lower"]) / bb_range

    out["Volume_Avg_5"] = volume.rolling(5).mean()
    out["Volume_Avg_20"] = volume.rolling(20).mean()
    out["Volume_Ratio"] = volume / out["Volume_Avg_20"]
    out["Volume_Ratio_5"] = volume / out["Volume_Avg_5"]
    out["Volume_Change_5"] = volume.pct_change(5)

    out["Volatility_20"] = out["Return_1"].rolling(20).std() * np.sqrt(252) * 100
    out["Daily_Range_Pct"] = ((high - low) / close.replace(0, np.nan)) * 100
    out["Open_Close_Pct"] = ((close - open_) / open_.replace(0, np.nan)) * 100

    prev_close = close.shift(1)
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr_components = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    )
    true_range = tr_components.max(axis=1)
    out["ATR_14"] = true_range.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    out["ATR_14_Pct"] = (out["ATR_14"] / close.replace(0, np.nan)) * 100

    def _dmi_adx(period: int):
        atr = true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        plus_di = 100 * pd.Series(plus_dm, index=out.index).ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr.replace(0, np.nan)
        minus_di = 100 * pd.Series(minus_dm, index=out.index).ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr.replace(0, np.nan)
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
        adx = dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        return plus_di, minus_di, adx

    out["Plus_DI_20"], out["Minus_DI_20"], out["ADX_20"] = _dmi_adx(20)
    out["Plus_DI_50"], out["Minus_DI_50"], out["ADX_50"] = _dmi_adx(50)
    out["DMI20_Spread"] = out["Plus_DI_20"] - out["Minus_DI_20"]
    out["DMI50_Spread"] = out["Plus_DI_50"] - out["Minus_DI_50"]
    out["DMI20_Spread_Change_3"] = out["DMI20_Spread"].diff(3)

    out["MA20_Gap_Pct"] = ((close - out["SMA_20"]) / out["SMA_20"].replace(0, np.nan)) * 100
    out["MA50_Gap_Pct"] = ((close - out["SMA_50"]) / out["SMA_50"].replace(0, np.nan)) * 100
    out["MA100_Gap_Pct"] = ((close - out["SMA_100"]) / out["SMA_100"].replace(0, np.nan)) * 100

    high20 = high.rolling(20).max()
    low20 = low.rolling(20).min()
    high50 = high.rolling(50).max()
    low50 = low.rolling(50).min()
    out["Close_Position_20"] = (close - low20) / (high20 - low20).replace(0, np.nan)
    out["Close_Position_50"] = (close - low50) / (high50 - low50).replace(0, np.nan)

    out["Gap_Open_Pct"] = ((open_ - prev_close) / prev_close.replace(0, np.nan)) * 100

    return out


def to_chart_rows(df: pd.DataFrame, limit: int = 160) -> list[dict]:
    rows = []
    show = df.tail(limit)
    for _, r in show.iterrows():
        rows.append(
            {
                "date": str(r.get("Date", ""))[:10],
                "open": _round(r.get("Open")),
                "high": _round(r.get("High")),
                "low": _round(r.get("Low")),
                "close": _round(r.get("Close")),
                "volume": int(r.get("Volume", 0) or 0),
                "sma20": _round(r.get("SMA_20")),
                "sma50": _round(r.get("SMA_50")),
            }
        )
    return rows


def _round(value, ndigits: int = 2):
    try:
        if pd.isna(value):
            return None
        return round(float(value), ndigits)
    except Exception:  # noqa: BLE001
        return None
