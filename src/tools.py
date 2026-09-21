"""Market data tools. Each one reads the on-disk cache first and calls Yahoo only on a miss."""

import json
from pathlib import Path

import yfinance as yf

# Cached responses live here and are committed, so calls whose exact arguments are
# cached replay offline and every teammate works from identical data. Anchored to the repo root (two levels up
# from this file) so a notebook in dev/ hits the same files as one at the root.
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"


# Return the cached result for `name` if it exists; otherwise call fetch(), save it, return it.
def cache_or_fetch(name, fetch, refresh=False):
    path = CACHE_DIR / f"{name}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    result = fetch()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2))
    return result


# Daily closes for the period plus a few summary numbers a prompt can quote directly.
def get_prices(symbol, period="6mo", refresh=False):
    return cache_or_fetch(f"get_prices_{symbol}_{period}", lambda: _fetch_prices(symbol, period), refresh)


def _fetch_prices(symbol, period):
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
        "dates": [str(d.date()) for d in history.index],  # plain strings, so the dict is JSON-safe
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


# A flat dict of the selected fundamentals. A field Yahoo omits comes back as None.
def get_fundamentals(symbol, refresh=False):
    return cache_or_fetch(f"get_fundamentals_{symbol}", lambda: _fetch_fundamentals(symbol), refresh)


def _fetch_fundamentals(symbol):
    info = yf.Ticker(symbol).info
    result = {"symbol": symbol}
    for yahoo_key, our_key in FUNDAMENTAL_FIELDS.items():
        result[our_key] = info.get(yahoo_key)
    return result


# Recent headlines with summaries.
def get_news(symbol, limit=10, refresh=False):
    return cache_or_fetch(f"get_news_{symbol}_{limit}", lambda: _fetch_news(symbol, limit), refresh)


def _fetch_news(symbol, limit):
    articles = []
    for item in yf.Ticker(symbol).news[:limit]:
        content = item["content"]  # yfinance 1.x nests every article field under "content"
        articles.append({
            "title": content.get("title"),
            "summary": content.get("summary", ""),
            "publisher": (content.get("provider") or {}).get("displayName"),
            "published": content.get("pubDate"),
            "url": (content.get("canonicalUrl") or {}).get("url"),
        })
    return articles


# The menu the agent picks from. A plan step names a key here; the executor calls the value.
TOOLS = {
    "get_prices": get_prices,
    "get_fundamentals": get_fundamentals,
    "get_news": get_news,
}
