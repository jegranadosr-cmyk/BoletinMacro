"""Fetch a handful of macro-relevant market indicators (dollar index, EUR/USD,
USD/COP, gold, oil) from Yahoo Finance's public chart API, to give the macro
bulletin a quick market-pulse reading alongside the official statistics.
"""
import datetime
import socket
import time
import urllib.request
import json

_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only_getaddrinfo

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def _get_json(url, retries=3, timeout=15):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise last_err


def fetch_chart(symbol, range_="2y", interval="1d"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={range_}&interval={interval}"
    data = _get_json(url)
    result = data["chart"]["result"]
    if not result:
        raise ValueError(f"No data for {symbol}")
    r = result[0]
    meta = r["meta"]
    timestamps = r.get("timestamp", [])
    closes = r["indicators"]["quote"][0].get("close", [])
    series = {}
    for ts, c in zip(timestamps, closes):
        if c is None:
            continue
        d = datetime.datetime.utcfromtimestamp(ts).date()
        series[d] = c
    return meta, series


def _baseline_before(series, cutoff_date):
    candidates = [d for d in series if d < cutoff_date]
    if not candidates:
        return None
    return series[max(candidates)]


def pct_changes_for_symbol(symbol, today=None):
    today = today or datetime.datetime.utcnow().date()
    meta, series = fetch_chart(symbol)
    price = meta.get("regularMarketPrice")
    pct_day = meta.get("regularMarketChangePercent")

    month_start = today.replace(day=1)
    month_base = _baseline_before(series, month_start)
    pct_month = ((price - month_base) / month_base * 100) if month_base else None

    return {"price": price, "pct_day": pct_day, "pct_month": pct_month}


MERCADOS_CLAVE = [
    ("DXY (índice dólar)", "DX-Y.NYB"),
    ("EUR/USD", "EURUSD=X"),
    ("USD/COP", "COP=X"),
    ("Oro (oz troy)", "GC=F"),
    ("Petróleo WTI", "CL=F"),
]


def fetch_mercados_clave():
    out = []
    for nombre, symbol in MERCADOS_CLAVE:
        try:
            r = pct_changes_for_symbol(symbol)
            out.append({"nombre": nombre, **r})
        except Exception:
            out.append({"nombre": nombre, "price": None, "pct_day": None, "pct_month": None})
    return out
