"""Compute real GDP growth (CAGR) over 1, 5 and 20 years from the World
Bank's annual real-GDP series (constant 2015 US$, NY.GDP.MKTP.KD) -- a
single consistent source and methodology across all regions, including the
Euro area aggregate (which national statistics offices don't publish
directly in a comparable way).

CAGR_n = (GDP_latest / GDP_(latest-n)) ** (1/n) - 1
"""
import socket
import time
import urllib.request
import json

_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only_getaddrinfo

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
URL = "https://api.worldbank.org/v2/country/{country}/indicator/NY.GDP.MKTP.KD?format=json&per_page=30"
HORIZONS = (1, 5, 20)

PAISES = [
    ("Colombia", "COL"),
    ("EE.UU.", "USA"),
    ("Eurozona", "EMU"),
    ("Francia", "FRA"),
    ("Alemania", "DEU"),
    ("Italia", "ITA"),
    ("España", "ESP"),
    ("China", "CHN"),
    ("Japón", "JPN"),
]


def _fetch_json(url, timeout=25, retries=3):
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


def _cagr_horizons(country):
    data = _fetch_json(URL.format(country=country))
    rows = {int(row["date"]): row["value"] for row in data[1] if row["value"] is not None} if len(data) > 1 and data[1] else {}
    if not rows:
        return {n: None for n in HORIZONS}
    latest_year = max(rows.keys())
    latest_val = rows[latest_year]
    out = {}
    for n in HORIZONS:
        base_year = latest_year - n
        base_val = rows.get(base_year)
        out[n] = ((latest_val / base_val) ** (1 / n) - 1) * 100 if base_val else None
    return out


def fetch_growth_horizons():
    out = []
    for nombre, code in PAISES:
        try:
            horizons = _cagr_horizons(code)
        except Exception:
            horizons = {n: None for n in HORIZONS}
        out.append({
            "pais": nombre,
            "pib_1a": horizons[1],
            "pib_5a": horizons[5],
            "pib_20a": horizons[20],
        })
    return out
