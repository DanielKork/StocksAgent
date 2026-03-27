import time
from datetime import datetime, timezone
import yfinance as yf
import pandas as pd
import ta
from cachetools import TTLCache
from backend.config import (
    CACHE_QUOTE_TTL, CACHE_QUOTE_MAXSIZE,
    CACHE_INFO_TTL, CACHE_INFO_MAXSIZE,
    CACHE_FINANCIALS_TTL, CACHE_FINANCIALS_MAXSIZE,
    YAHOO_MAX_RETRIES, YAHOO_RETRY_DELAY,
    MAX_COMPARE_STOCKS,
)

# Caches with configurable TTL and max size
_quote_cache = TTLCache(maxsize=CACHE_QUOTE_MAXSIZE, ttl=CACHE_QUOTE_TTL)
_info_cache = TTLCache(maxsize=CACHE_INFO_MAXSIZE, ttl=CACHE_INFO_TTL)
_financials_cache = TTLCache(maxsize=CACHE_FINANCIALS_MAXSIZE, ttl=CACHE_FINANCIALS_TTL)

_MAX_RETRIES = YAHOO_MAX_RETRIES
_RETRY_DELAY = YAHOO_RETRY_DELAY


def _get_ticker(symbol: str) -> yf.Ticker:
    return yf.Ticker(symbol.upper().strip())


def _retry(func, *args, **kwargs):
    """Retry a function call with exponential backoff on rate limit errors."""
    delay = YAHOO_RETRY_DELAY
    for attempt in range(YAHOO_MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if "RateLimit" in type(e).__name__ or "Too Many Requests" in str(e):
                if attempt < YAHOO_MAX_RETRIES - 1:
                    time.sleep(delay)
                    delay *= 2
                    continue
            raise
    raise RuntimeError(f"Failed after {YAHOO_MAX_RETRIES} retries")


def get_realtime_quote(ticker: str) -> dict:
    key = ticker.upper()
    if key in _quote_cache:
        return _quote_cache[key]

    t = _get_ticker(ticker)
    info = _retry(lambda: t.info)
    if not info:
        raise ValueError(f"Could not fetch data for ticker '{key}'. It may be invalid or Yahoo Finance is temporarily unavailable.")

    result = {
        "ticker": key,
        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "previous_close": info.get("previousClose") or info.get("regularMarketPreviousClose"),
        "open": info.get("open") or info.get("regularMarketOpen"),
        "day_high": info.get("dayHigh") or info.get("regularMarketDayHigh"),
        "day_low": info.get("dayLow") or info.get("regularMarketDayLow"),
        "volume": info.get("volume") or info.get("regularMarketVolume"),
        "market_cap": info.get("marketCap"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        "currency": info.get("currency", "USD"),
        "exchange": info.get("exchange", ""),
    }

    # Calculate change
    if result["price"] and result["previous_close"]:
        result["change"] = round(result["price"] - result["previous_close"], 4)
        result["change_percent"] = round(
            (result["change"] / result["previous_close"]) * 100, 2
        )
    else:
        result["change"] = None
        result["change_percent"] = None

    _quote_cache[key] = result
    return result


def get_historical_data(ticker: str, period: str = "1mo", interval: str = "1d") -> list[dict]:
    t = _get_ticker(ticker)
    df = _retry(lambda: t.history(period=period, interval=interval))
    if df.empty:
        return []
    df.index = df.index.strftime("%Y-%m-%d %H:%M:%S")
    records = df.reset_index().to_dict(orient="records")
    # Clean NaN values
    for r in records:
        for k, v in r.items():
            if pd.isna(v):
                r[k] = None
    return records


def get_company_info(ticker: str) -> dict:
    key = ticker.upper()
    if key in _info_cache:
        return _info_cache[key]

    t = _get_ticker(ticker)
    info = _retry(lambda: t.info) or {}

    result = {
        "ticker": key,
        "name": info.get("longName") or info.get("shortName", ""),
        "sector": info.get("sector", ""),
        "industry": info.get("industry", ""),
        "country": info.get("country", ""),
        "website": info.get("website", ""),
        "description": info.get("longBusinessSummary", ""),
        "employees": info.get("fullTimeEmployees"),
        "ceo": "",
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "dividend_yield": info.get("dividendYield"),
        "beta": info.get("beta"),
        "eps": info.get("trailingEps"),
    }

    # Get CEO from company officers
    officers = info.get("companyOfficers", [])
    for officer in officers:
        title = officer.get("title", "").lower()
        if "ceo" in title or "chief executive" in title:
            result["ceo"] = officer.get("name", "")
            break

    _info_cache[key] = result
    return result


def get_financials(ticker: str) -> dict:
    key = ticker.upper()
    if key in _financials_cache:
        return _financials_cache[key]

    t = _get_ticker(ticker)

    def df_to_dict(df):
        if df is None or df.empty:
            return {}
        df_copy = df.copy()
        df_copy.columns = [c.strftime("%Y-%m-%d") if hasattr(c, "strftime") else str(c) for c in df_copy.columns]
        data = {}
        for col in df_copy.columns:
            data[col] = {}
            for idx, val in df_copy[col].items():
                data[col][str(idx)] = None if pd.isna(val) else val
        return data

    result = {
        "ticker": key,
        "income_statement": df_to_dict(_retry(lambda: t.financials)),
        "balance_sheet": df_to_dict(_retry(lambda: t.balance_sheet)),
        "cash_flow": df_to_dict(_retry(lambda: t.cashflow)),
        "quarterly_income": df_to_dict(_retry(lambda: t.quarterly_financials)),
        "quarterly_balance": df_to_dict(_retry(lambda: t.quarterly_balance_sheet)),
    }

    _financials_cache[key] = result
    return result


def get_news(ticker: str) -> list[dict]:
    t = _get_ticker(ticker)
    news = _retry(lambda: t.news) or []
    results = []
    for item in news[:10]:
        content = item.get("content", {})
        results.append({
            "title": content.get("title", item.get("title", "")),
            "publisher": content.get("provider", {}).get("displayName", item.get("publisher", "")),
            "link": content.get("canonicalUrl", {}).get("url", item.get("link", "")),
            "published": content.get("pubDate", item.get("providerPublishTime", "")),
        })
    return results


def get_recommendations(ticker: str) -> dict:
    t = _get_ticker(ticker)

    # Analyst recommendations summary
    info = _retry(lambda: t.info) or {}
    result = {
        "ticker": ticker.upper(),
        "target_high": info.get("targetHighPrice"),
        "target_low": info.get("targetLowPrice"),
        "target_mean": info.get("targetMeanPrice"),
        "target_median": info.get("targetMedianPrice"),
        "recommendation": info.get("recommendationKey", ""),
        "number_of_analysts": info.get("numberOfAnalystOpinions"),
        "current_price": info.get("currentPrice"),
    }

    # Recent recommendations
    try:
        recs = t.recommendations
        if recs is not None and not recs.empty:
            recent = recs.tail(10).reset_index()
            recent_list = []
            for _, row in recent.iterrows():
                rec = {}
                for col in recent.columns:
                    val = row[col]
                    if pd.isna(val):
                        rec[col] = None
                    elif hasattr(val, "isoformat"):
                        rec[col] = val.isoformat()
                    else:
                        rec[col] = val
                recent_list.append(rec)
            result["recent_recommendations"] = recent_list
    except Exception:
        result["recent_recommendations"] = []

    return result


def get_technical_indicators(ticker: str, period: str = "6mo") -> dict:
    t = _get_ticker(ticker)
    df = _retry(lambda: t.history(period=period, interval="1d"))

    if df.empty or len(df) < 20:
        return {"ticker": ticker.upper(), "error": "Not enough data for technical analysis"}

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    result = {
        "ticker": ticker.upper(),
        "period": period,
        "data_points": len(df),
        "latest_close": round(float(close.iloc[-1]), 2),
    }

    # RSI (14-period)
    rsi_indicator = ta.momentum.RSIIndicator(close, window=14)
    rsi_val = rsi_indicator.rsi().iloc[-1]
    result["rsi_14"] = round(float(rsi_val), 2) if not pd.isna(rsi_val) else None
    if result["rsi_14"]:
        if result["rsi_14"] > 70:
            result["rsi_signal"] = "Overbought"
        elif result["rsi_14"] < 30:
            result["rsi_signal"] = "Oversold"
        else:
            result["rsi_signal"] = "Neutral"

    # MACD
    macd_indicator = ta.trend.MACD(close)
    macd_val = macd_indicator.macd().iloc[-1]
    macd_signal = macd_indicator.macd_signal().iloc[-1]
    macd_hist = macd_indicator.macd_diff().iloc[-1]
    result["macd"] = round(float(macd_val), 4) if not pd.isna(macd_val) else None
    result["macd_signal"] = round(float(macd_signal), 4) if not pd.isna(macd_signal) else None
    result["macd_histogram"] = round(float(macd_hist), 4) if not pd.isna(macd_hist) else None
    if result["macd"] is not None and result["macd_signal"] is not None:
        result["macd_trend"] = "Bullish" if result["macd"] > result["macd_signal"] else "Bearish"

    # Moving Averages
    for window in [20, 50, 200]:
        if len(close) >= window:
            sma = close.rolling(window=window).mean().iloc[-1]
            ema = close.ewm(span=window, adjust=False).mean().iloc[-1]
            result[f"sma_{window}"] = round(float(sma), 2) if not pd.isna(sma) else None
            result[f"ema_{window}"] = round(float(ema), 2) if not pd.isna(ema) else None

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    result["bb_upper"] = round(float(bb.bollinger_hband().iloc[-1]), 2)
    result["bb_middle"] = round(float(bb.bollinger_mavg().iloc[-1]), 2)
    result["bb_lower"] = round(float(bb.bollinger_lband().iloc[-1]), 2)

    # Average True Range (volatility)
    atr = ta.volatility.AverageTrueRange(high, low, close, window=14)
    atr_val = atr.average_true_range().iloc[-1]
    result["atr_14"] = round(float(atr_val), 2) if not pd.isna(atr_val) else None

    # Volume SMA
    vol_sma = volume.rolling(window=20).mean().iloc[-1]
    result["volume_sma_20"] = int(vol_sma) if not pd.isna(vol_sma) else None
    result["current_volume"] = int(volume.iloc[-1])

    return result


def compare_stocks(tickers: list[str]) -> list[dict]:
    results = []
    for ticker in tickers[:MAX_COMPARE_STOCKS]:  # configurable limit
        try:
            quote = get_realtime_quote(ticker)
            info = get_company_info(ticker)
            results.append({
                "ticker": ticker.upper(),
                "name": info.get("name", ""),
                "price": quote.get("price"),
                "change_percent": quote.get("change_percent"),
                "market_cap": quote.get("market_cap"),
                "pe_ratio": info.get("pe_ratio"),
                "forward_pe": info.get("forward_pe"),
                "eps": info.get("eps"),
                "dividend_yield": info.get("dividend_yield"),
                "beta": info.get("beta"),
                "sector": info.get("sector", ""),
                "52w_high": quote.get("fifty_two_week_high"),
                "52w_low": quote.get("fifty_two_week_low"),
            })
        except Exception as e:
            results.append({"ticker": ticker.upper(), "error": str(e)})
    return results


def get_portfolio_summary(positions: list[dict]) -> list[dict]:
    """Enrich portfolio positions with current market data."""
    enriched = []
    for pos in positions:
        try:
            quote = get_realtime_quote(pos["ticker"])
            current_price = quote.get("price", 0) or 0
            cost_basis = pos["shares"] * pos["avg_price"]
            market_value = pos["shares"] * current_price
            pnl = market_value - cost_basis
            pnl_pct = (pnl / cost_basis * 100) if cost_basis else 0
            enriched.append({
                **pos,
                "current_price": current_price,
                "market_value": round(market_value, 2),
                "cost_basis": round(cost_basis, 2),
                "pnl": round(pnl, 2),
                "pnl_percent": round(pnl_pct, 2),
                "day_change_percent": quote.get("change_percent"),
            })
        except Exception:
            enriched.append({**pos, "current_price": None, "error": "Failed to fetch price"})
    return enriched


def get_market_status() -> dict:
    """Check if major markets are currently open or closed."""
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo

    now_utc = datetime.now(timezone.utc)

    markets = []

    # US Markets (NYSE/NASDAQ) — ET
    et = ZoneInfo("America/New_York")
    now_et = now_utc.astimezone(et)
    weekday_et = now_et.weekday()  # 0=Mon, 6=Sun
    hour_et = now_et.hour
    minute_et = now_et.minute
    us_open = (
        weekday_et < 5
        and (hour_et > 9 or (hour_et == 9 and minute_et >= 30))
        and hour_et < 16
    )
    markets.append({
        "market": "US (NYSE/NASDAQ)",
        "timezone": "America/New_York",
        "local_time": now_et.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "is_open": us_open,
        "trading_hours": "09:30–16:00 ET",
        "status": "Open" if us_open else "Closed",
    })

    # European Markets (LSE) — London
    london = ZoneInfo("Europe/London")
    now_london = now_utc.astimezone(london)
    weekday_london = now_london.weekday()
    hour_london = now_london.hour
    lse_open = weekday_london < 5 and 8 <= hour_london < 16
    markets.append({
        "market": "Europe (LSE)",
        "timezone": "Europe/London",
        "local_time": now_london.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "is_open": lse_open,
        "trading_hours": "08:00–16:30 GMT/BST",
        "status": "Open" if lse_open else "Closed",
    })

    # Asian Markets (Tokyo) — JST
    tokyo = ZoneInfo("Asia/Tokyo")
    now_tokyo = now_utc.astimezone(tokyo)
    weekday_tokyo = now_tokyo.weekday()
    hour_tokyo = now_tokyo.hour
    tse_open = weekday_tokyo < 5 and 9 <= hour_tokyo < 15
    markets.append({
        "market": "Asia (TSE Tokyo)",
        "timezone": "Asia/Tokyo",
        "local_time": now_tokyo.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "is_open": tse_open,
        "trading_hours": "09:00–15:00 JST",
        "status": "Open" if tse_open else "Closed",
    })

    any_open = any(m["is_open"] for m in markets)

    return {
        "utc_time": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "any_market_open": any_open,
        "markets": markets,
    }
