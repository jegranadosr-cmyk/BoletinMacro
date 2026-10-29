"""Fetch recent macro/coyuntura news headlines from TradingEconomics' public
news stream endpoint (no key, no auth -- it's the same JSON the site's own
JS pulls to render tradingeconomics.com/stream).

Verified live (Oct 2026): https://tradingeconomics.com/ws/stream.ashx?start=0&size=100
returns a JSON array of recent items (title, description, country, category,
importance 1-3, date, url). The feed mixes everything (stock markets, crypto,
commodities, macro releases) so we filter down to the countries/blocs this
bulletin covers and to macro-relevant categories.
"""
import json
import socket
import urllib.request

_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only_getaddrinfo

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://tradingeconomics.com/stream",
}
STREAM_URL = "https://tradingeconomics.com/ws/stream.ashx?start={start}&size={size}"

RELEVANT_COUNTRIES = {
    "United States", "Euro Area", "France", "Germany", "Italy", "Spain",
    "China", "Japan", "Colombia",
}

MACRO_CATEGORIES = {
    "Full Year GDP Growth", "GDP Growth Rate", "GDP Annual Growth Rate",
    "Inflation Rate", "Interest Rate", "Unemployment Rate", "Unemployed Persons",
    "Goods Trade Balance", "Trade Balance", "Balance of Trade", "Government Budget",
    "Business Confidence", "Consumer Confidence", "Industrial Production",
    "Retail Sales YoY", "Retail Sales MoM", "Government Bond 10Y",
    "Manufacturing PMI", "Services PMI", "Composite PMI",
    "Producer Prices Change", "Producer Price Inflation MoM",
}

PAIS_ES = {
    "United States": "EE.UU.", "Euro Area": "Eurozona", "France": "Francia",
    "Germany": "Alemania", "Italy": "Italia", "Spain": "España",
    "China": "China", "Japan": "Japón", "Colombia": "Colombia",
}


def _fetch_page(start, size=100, timeout=20):
    req = urllib.request.Request(STREAM_URL.format(start=start, size=size), headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def fetch_relevant_news(max_items=8, pages=3, page_size=100):
    items = []
    for i in range(pages):
        try:
            items.extend(_fetch_page(i * page_size, page_size))
        except Exception:
            continue

    seen_combo = set()
    out = []
    for it in items:
        if it["country"] not in RELEVANT_COUNTRIES:
            continue
        if it["category"] not in MACRO_CATEGORIES:
            continue
        # Items arrive newest-first; keep only the latest headline per
        # (country, category) so a preview + its result don't both show up.
        combo = (it["country"], it["category"])
        if combo in seen_combo:
            continue
        seen_combo.add(combo)
        title = it["title"]
        desc = (it.get("description") or "").strip()
        if len(desc) > 220:
            desc = desc[:217].rsplit(" ", 1)[0] + "..."
        out.append({
            "titulo": title,
            "resumen": desc,
            "pais": PAIS_ES.get(it["country"], it["country"]),
            "categoria": it["category"],
            "importancia": it["importance"],
            "fecha": it["date"][:10],
        })

    out.sort(key=lambda d: (d["importancia"], d["fecha"]), reverse=True)
    return out[:max_items]
