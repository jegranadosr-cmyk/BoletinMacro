"""Compute real GDP growth (CAGR) over 1 and 5 years from the World Bank's
annual real-GDP series (constant 2015 US$, NY.GDP.MKTP.KD) -- a single
consistent source and methodology across all 7 regions.

CAGR_n = (GDP_latest / GDP_(latest-n)) ** (1/n) - 1

Caveat (flagged in a 2026-10-29 review): this is ANNUAL data, typically one
full calendar year behind -- e.g. "PIB 1A" for 2026 actually reflects the
last closed year (2025), not the latest quarterly print a news wire would
cite (which runs ~1 quarter behind, not ~1 year). The bulletin surfaces the
actual reference year (fetch_growth_horizons()[...]["anio"]) next to the
number so readers aren't misled into comparing it to a quarterly figure.
Building a true quarterly, YoY, 9-region series is a separate, larger task
(FRED covers the US; Eurostat covers the Eurozone and its members; China,
Japan and Colombia would each need their own source) -- not done here.
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
HORIZONS = (1, 5)

PAISES = [
    ("Colombia", "COL"),
    ("EE.UU.", "USA"),
    ("Alemania", "DEU"),
    ("India", "IND"),
    ("Corea del Sur", "KOR"),
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
        return {n: None for n in HORIZONS}, None
    latest_year = max(rows.keys())
    latest_val = rows[latest_year]
    out = {}
    for n in HORIZONS:
        base_year = latest_year - n
        base_val = rows.get(base_year)
        out[n] = ((latest_val / base_val) ** (1 / n) - 1) * 100 if base_val else None
    return out, latest_year


def fetch_growth_horizons():
    out = []
    for nombre, code in PAISES:
        try:
            horizons, anio = _cagr_horizons(code)
        except Exception:
            horizons, anio = {n: None for n in HORIZONS}, None
        out.append({
            "pais": nombre,
            "pib_1a": horizons[1],
            "pib_5a": horizons[5],
            "anio": anio,
        })
    return out
