"""Market data tools. Each one reads the on-disk cache first and calls Yahoo only on a miss."""

import functools
import inspect
import json
import os
from pathlib import Path

import yfinance as yf

# Cached JSON lives here and is committed, so the notebook reruns offline and
# every teammate works from identical data.
CACHE_DIR = Path(os.getenv("NFA_CACHE_DIR", "data/cache"))


# Decorator: turn a fetch function into a cache-first one. The file name is the
# function name plus every argument (defaults included), so get_prices("AAPL", "6mo")
# and get_prices("AAPL", "1y") are different files. Pass refresh=True to refetch.
def cached(fn):
    signature = inspect.signature(fn)

    @functools.wraps(fn)
    def wrapper(*args, refresh=False, **kwargs):
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        key = "_".join([fn.__name__, *(str(v) for v in bound.arguments.values())])
        path = CACHE_DIR / f"{key}.json"
        if path.exists() and not refresh:
            return json.loads(path.read_text())
        result = fn(*args, **kwargs)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2, default=str))
        return result

    return wrapper


# Daily closes for the period plus a few summary numbers a prompt can quote directly.
@cached
def get_prices(symbol, period="6mo"):
    history = yf.Ticker(symbol).history(period=period)
    if history.empty:
        raise ValueError(f"No price history returned for {symbol!r}")
    close = history["Close"].round(2)
    return {
        "symbol": symbol,
        "period": period,
        "start": str(history.index[0].date()),
        "end": str(history.index[-1].date()),
        "last_close": float(close.iloc[-1]),
        "change_pct": round(float((close.iloc[-1] / close.iloc[0] - 1) * 100), 2),
        "high": float(close.max()),
        "low": float(close.min()),
        "avg_volume": int(history["Volume"].mean()),
        "dates": [str(d.date()) for d in history.index],
        "close": [float(c) for c in close],
    }


# Yahoo's info dict has hundreds of keys; keep the dozen an analyst would actually cite.
FUNDAMENTAL_FIELDS = {
    "longName": "name",
    "sector": "sector",
    "industry": "industry",
    "marketCap": "market_cap",
    "trailingPE": "trailing_pe",
    "forwardPE": "forward_pe",
    "totalRevenue": "revenue",
    "revenueGrowth": "revenue_growth",
    "profitMargins": "profit_margin",
    "earningsGrowth": "earnings_growth",
    "dividendYield": "dividend_yield",
    "fiftyTwoWeekHigh": "week52_high",
    "fiftyTwoWeekLow": "week52_low",
}


# A flat dict of the selected fundamentals. Missing fields come back as None rather than raising.
@cached
def get_fundamentals(symbol):
    info = yf.Ticker(symbol).info
    result = {"symbol": symbol}
    for source_key, our_key in FUNDAMENTAL_FIELDS.items():
        result[our_key] = info.get(source_key)
    return result


# Recent headlines with summaries. yfinance changed its news shape in 2025 (everything
# moved under a "content" key), so this reads both the old and the new layout.
@cached
def get_news(symbol, limit=10):
    items = yf.Ticker(symbol).news[:limit]
    articles = []
    for item in items:
        content = item.get("content", item)
        provider = content.get("provider") or {}
        articles.append({
            "title": content.get("title"),
            "summary": content.get("summary") or content.get("description") or "",
            "publisher": provider.get("displayName") or item.get("publisher"),
            "published": content.get("pubDate") or item.get("providerPublishTime"),
            "url": (content.get("canonicalUrl") or {}).get("url") or item.get("link"),
        })
    return articles


# The menu the agent picks from. A plan step names a key here; the executor calls the value.
TOOLS = {
    "get_prices": get_prices,
    "get_fundamentals": get_fundamentals,
    "get_news": get_news,
}
