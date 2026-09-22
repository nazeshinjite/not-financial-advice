"""Market data tools. Each one reads the on-disk cache first and calls Yahoo only on a miss."""

import json
from pathlib import Path

import yfinance as yf

# Cached responses live here and are committed, so calls whose exact arguments are
# cached replay offline and every teammate works from identical data. Anchored to the
# repo root (two levels up from this file) so a notebook in dev/ hits the same files as
# one at the root.
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
# Units live in the key names so a prompt can never misread them: money is in billions
# (_b) and ratios are percentages (_pct). Yahoo gives money as raw integers such as
# 302970011648 and growth as fractions such as 1.059; a model reading those in a prompt
# misplaced the magnitude once in three test runs, so the scaling is done here, once.
FUNDAMENTAL_FIELDS = {
    "longName": "name",
    "sector": "sector",
    "industry": "industry",
    "financialCurrency": "currency",  # the unit of the money fields; Yahoo reports foreign listings in local currency
    "marketCap": "market_cap_b",
    "trailingPE": "trailing_pe",
    "forwardPE": "forward_pe",
    "totalRevenue": "revenue_b",
    "revenueGrowth": "revenue_growth_pct",
    "profitMargins": "profit_margin_pct",
    "earningsGrowth": "earnings_growth_pct",
    "dividendYield": "dividend_yield_pct",  # already a percent in yfinance 1.7 (AAPL 0.32 means 0.32%); not rescaled
    "fiftyTwoWeekHigh": "week52_high",
    "fiftyTwoWeekLow": "week52_low",
}
BILLIONS = {"market_cap_b", "revenue_b"}
FRACTION_TO_PCT = {"revenue_growth_pct", "profit_margin_pct", "earnings_growth_pct"}


# A flat dict of the selected fundamentals, scaled to the units in the key names.
# A field Yahoo omits comes back as None.
def get_fundamentals(symbol, refresh=False):
    return cache_or_fetch(f"get_fundamentals_{symbol}", lambda: _fetch_fundamentals(symbol), refresh)


def _fetch_fundamentals(symbol):
    info = yf.Ticker(symbol).info
    result = {"symbol": symbol}
    for yahoo_key, our_key in FUNDAMENTAL_FIELDS.items():
        value = info.get(yahoo_key)
        if value is not None and our_key in BILLIONS:
            value = round(value / 1e9, 2)
        elif value is not None and our_key in FRACTION_TO_PCT:
            value = round(value * 100, 1)
        result[our_key] = value
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
