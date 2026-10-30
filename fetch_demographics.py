"""Fetch population, GDP (nominal and PPP), GDP per capita (nominal and PPP)
and land area from the World Bank's public API (no key required) -- same
source and retry pattern as fetch_worldbank.py and fetch_growth.py.

"PIB real" here means PPP-adjusted GDP (constant international $), which is
what's commonly meant by "real" size when comparing economies across
countries (it strips out exchange-rate and cost-of-living distortions that
nominal, market-FX GDP carries) -- a different concept from "real GDP" in
the single-country, inflation-adjusted-over-time sense used elsewhere in
this bulletin (fetch_growth.py).
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
BASE = "https://api.worldbank.org/v2/country/{country}/indicator/{indicator}?format=json&per_page=5"

# (nombre mostrado, codigo Banco Mundial, nombre en ingles para cruzar con Wikipedia)
PAISES = [
    ("Colombia", "COL", "Colombia"),
    ("EE.UU.", "USA", "United States"),
    ("Iran", "IRN", "Iran"),
    ("Iraq", "IRQ", "Iraq"),
    ("Alemania", "DEU", "Germany"),
    ("India", "IND", "India"),
    ("Corea del Sur", "KOR", "South Korea"),
    ("China", "CHN", "China"),
    ("Japón", "JPN", "Japan"),
    ("Brasil", "BRA", "Brazil"),
    ("Rusia", "RUS", "Russia"),
    ("Arabia Saudita", "SAU", "Saudi Arabia"),
    ("Qatar", "QAT", "Qatar"),
    ("Indonesia", "IDN", "Indonesia"),
    ("Canadá", "CAN", "Canada"),
    ("Australia", "AUS", "Australia"),
    ("Kuwait", "KWT", "Kuwait"),
]


def _latest(country, indicator, timeout=25, retries=3):
    url = BASE.format(country=country, indicator=indicator)
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
            break
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    else:
        raise last_err
    if len(data) < 2 or not data[1]:
        return None
    for row in data[1]:
        if row["value"] is not None:
            return row["value"]
    return None


def fetch_demographics():
    out = []
    for nombre, code, _ in PAISES:
        try:
            poblacion = _latest(code, "SP.POP.TOTL")
        except Exception:
            poblacion = None
        try:
            pib_nominal = _latest(code, "NY.GDP.MKTP.CD")
        except Exception:
            pib_nominal = None
        try:
            pib_ppa = _latest(code, "NY.GDP.MKTP.PP.CD")
        except Exception:
            pib_ppa = None
        try:
            pib_pc_nominal = _latest(code, "NY.GDP.PCAP.CD")
        except Exception:
            pib_pc_nominal = None
        try:
            pib_pc_ppa = _latest(code, "NY.GDP.PCAP.PP.CD")
        except Exception:
            pib_pc_ppa = None
        try:
            area_km2 = _latest(code, "AG.SRF.TOTL.K2")
        except Exception:
            area_km2 = None
        out.append({
            "pais": nombre,
            "poblacion": poblacion,
            "pib_nominal_usd": pib_nominal,
            "pib_ppa_usd": pib_ppa,
            "pib_pc_nominal_usd": pib_pc_nominal,
            "pib_pc_ppa_usd": pib_pc_ppa,
            "area_km2": area_km2,
        })
    return out
