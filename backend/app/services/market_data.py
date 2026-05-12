from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd
import requests
import yfinance as yf


class MarketDataError(Exception):
    """Raised when market data cannot be fetched or parsed."""


DEFAULT_SYMBOLS: List[Dict[str, str]] = [
    {"symbol": "RELIANCE.NS", "name": "Reliance Industries"},
    {"symbol": "TCS.NS", "name": "Tata Consultancy Services"},
    {"symbol": "INFY.NS", "name": "Infosys"},
    {"symbol": "HDFCBANK.NS", "name": "HDFC Bank"},
    {"symbol": "TATAMOTORS.NS", "name": "Tata Motors"},
    {"symbol": "ICICIBANK.NS", "name": "ICICI Bank"},
    {"symbol": "SBIN.NS", "name": "State Bank of India"},
    {"symbol": "ITC.NS", "name": "ITC"},
    {"symbol": "LT.NS", "name": "Larsen & Toubro"},
    {"symbol": "MARUTI.NS", "name": "Maruti Suzuki"},
]


YAHOO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}


def normalize_symbol(symbol: str) -> str:
    """Normalize user input into a Yahoo Finance NSE symbol."""
    cleaned = symbol.strip().upper().replace(" ", "")
    if not cleaned:
        raise MarketDataError("Symbol is required")
    if cleaned.startswith("^"):
        return cleaned
    if cleaned.endswith(".NS") or cleaned.endswith(".BO"):
        return cleaned
    return f"{cleaned}.NS"


def _flatten_yfinance_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Handle yfinance MultiIndex output from yf.download."""
    if isinstance(df.columns, pd.MultiIndex):
        # yfinance can return either (Price, Ticker) or (Ticker, Price).
        if "Close" in df.columns.get_level_values(0):
            df.columns = df.columns.get_level_values(0)
        elif "Close" in df.columns.get_level_values(-1):
            df.columns = df.columns.get_level_values(-1)
        else:
            df.columns = [str(c[-1] if isinstance(c, tuple) else c) for c in df.columns]
    return df


def _clean_history(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        raise MarketDataError("No market data found for this symbol")

    df = _flatten_yfinance_columns(df.copy())
    df = df.reset_index()

    if "Date" not in df.columns and "Datetime" in df.columns:
        df = df.rename(columns={"Datetime": "Date"})
    if "Date" not in df.columns and "index" in df.columns:
        df = df.rename(columns={"index": "Date"})

    keep_cols = [c for c in ["Date", "Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    df = df[keep_cols].copy()

    if "Close" not in df.columns:
        raise MarketDataError("Close price column missing from market data")

    df = df.dropna(subset=["Close"])
    if df.empty:
        raise MarketDataError("Market data response was empty after cleanup")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    df = df.dropna(subset=["Date"])

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["Close"]).reset_index(drop=True)
    if df.empty:
        raise MarketDataError("No valid close prices found for this symbol")
    return df


def _fetch_with_ticker_history(symbol: str, period: str, interval: str) -> pd.DataFrame:
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval, auto_adjust=False, raise_errors=False)
    return _clean_history(df)


def _fetch_with_yfinance_download(symbol: str, period: str, interval: str) -> pd.DataFrame:
    df = yf.download(
        tickers=symbol,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    return _clean_history(df)


def _period_to_range(period: str) -> str:
    allowed = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}
    return period if period in allowed else "1y"


def _fetch_with_yahoo_chart(symbol: str, period: str, interval: str) -> pd.DataFrame:
    """Direct Yahoo chart fallback used when yfinance wrapper returns empty."""
    chart_range = _period_to_range(period)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {
        "range": chart_range,
        "interval": interval,
        "includePrePost": "false",
        "events": "div,splits",
    }
    response = requests.get(url, params=params, headers=YAHOO_HEADERS, timeout=20)
    response.raise_for_status()
    payload = response.json()

    chart = payload.get("chart", {})
    error = chart.get("error")
    if error:
        raise MarketDataError(str(error))

    results = chart.get("result") or []
    if not results:
        raise MarketDataError("Yahoo chart API returned no result")

    result = results[0]
    timestamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    if not timestamps or not quote:
        raise MarketDataError("Yahoo chart API returned empty candles")

    df = pd.DataFrame(
        {
            "Date": pd.to_datetime(timestamps, unit="s", utc=True).tz_convert("Asia/Kolkata").tz_localize(None),
            "Open": quote.get("open"),
            "High": quote.get("high"),
            "Low": quote.get("low"),
            "Close": quote.get("close"),
            "Volume": quote.get("volume"),
        }
    )
    return _clean_history(df)


def _try_sources(symbol: str, period: str, interval: str) -> Tuple[pd.DataFrame, str]:
    errors: List[str] = []
    sources = [
        ("yfinance Ticker.history", _fetch_with_ticker_history),
        ("yfinance download", _fetch_with_yfinance_download),
        ("Yahoo chart fallback", _fetch_with_yahoo_chart),
    ]

    for source_name, fn in sources:
        try:
            df = fn(symbol, period, interval)
            if df is not None and not df.empty:
                return df, source_name
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{source_name}: {exc}")

    details = " | ".join(errors[-3:]) if errors else "No source returned data"
    raise MarketDataError(
        f"No market data found for {symbol}. Free public data may be temporarily blocked, delayed, "
        f"or unavailable. Details: {details}"
    )


def fetch_history(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    normalized = normalize_symbol(symbol)
    try:
        df, _source = _try_sources(normalized, period, interval)
        return df
    except MarketDataError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise MarketDataError(f"Could not fetch data for {normalized}: {exc}") from exc


def fetch_quote(symbol: str) -> Dict[str, object]:
    """Fetch latest available quote-like data.

    Free public data can be delayed or unavailable outside market hours.
    This method tries 1-minute candles first, then falls back to daily candles.
    """
    normalized = normalize_symbol(symbol)
    source_used = "unknown"

    try:
        try:
            intraday, source_used = _try_sources(normalized, "1d", "1m")
        except MarketDataError:
            intraday, source_used = _try_sources(normalized, "5d", "1d")

        df = _clean_history(intraday)
        last = df.iloc[-1]
        previous_close = float(df.iloc[-2]["Close"]) if len(df) > 1 else float(last["Close"])
        latest_close = float(last["Close"])
        change = latest_close - previous_close
        change_pct = (change / previous_close * 100) if previous_close else 0.0

        return {
            "symbol": normalized,
            "date": str(last["Date"]),
            "open": _safe_float(last.get("Open")),
            "high": _safe_float(last.get("High")),
            "low": _safe_float(last.get("Low")),
            "close": round(latest_close, 2),
            "volume": int(last.get("Volume", 0) or 0),
            "change": round(change, 2),
            "change_percent": round(change_pct, 2),
            "data_source": source_used,
            "data_note": (
                "Automatic free public data for NSE-listed symbols via Yahoo/yfinance-style endpoints. "
                "It may be delayed, incomplete, rate-limited, or unavailable sometimes. "
                "For a commercial product, replace this adapter with an official licensed NSE/vendor feed."
            ),
        }
    except MarketDataError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise MarketDataError(f"Could not fetch quote for {normalized}: {exc}") from exc


def _safe_float(value) -> float | None:
    try:
        if pd.isna(value):
            return None
        return round(float(value), 2)
    except Exception:  # noqa: BLE001
        return None
