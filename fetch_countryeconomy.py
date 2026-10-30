"""Fetch core macro indicators (CPI inflation, unemployment, trade balance,
fiscal deficit) from countryeconomy.com overview tables, for every country
this bulletin covers except the Euro area aggregate (not tracked on these
pages -- see fetch_eurostat.py for that one). GDP growth itself comes from
fetch_growth.py (World Bank CAGR, consistent across 1/5/20-year horizons and
across the Euro area aggregate too).

Verified against the live tables (Oct 2026):
- CPI: countryeconomy.com/cpi -- first "numero" cell is interannual CPI.
- Unemployment: countryeconomy.com/unemployment -- first "numero" cell is the
  unemployment rate.
- Trade balance: countryeconomy.com/trade/balance -- second plain "numero"
  cell (after the eur/dol export/import/balance triplets and the coverage
  rate) is "Trade balance % GDP".
- Fiscal deficit: countryeconomy.com/deficit -- plain "numero" cell after the
  eur/dol deficit pair is "Deficit % GDP".
"""
import re
import socket
import urllib.request

_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only_getaddrinfo

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

CPI_URL = "https://countryeconomy.com/cpi"
UNEMPLOYMENT_URL = "https://countryeconomy.com/unemployment"
TRADE_BALANCE_URL = "https://countryeconomy.com/trade/balance"
DEFICIT_URL = "https://countryeconomy.com/deficit"

PAISES = [
    ("Colombia", "colombia"),
    ("Brasil", "brazil"),
    ("México", "mexico"),
    ("Chile", "chile"),
    ("Perú", "peru"),
    ("EE.UU.", "usa"),
    ("Francia", "france"),
    ("Alemania", "germany"),
    ("Italia", "italy"),
    ("España", "spain"),
    ("China", "china"),
    ("Japón", "japan"),
]


def _fetch_text(url, timeout=20):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _row_html(html, base_path, slug):
    for quote in ("'", '"'):
        idx = html.find(f"href={quote}{base_path}{slug}{quote}")
        if idx != -1:
            break
    else:
        return None
    end = html.find("</tr>", idx)
    return html[idx:end] if end != -1 else None


def _numeros(row_html):
    """List of (class_suffix, value) for every class="numero..." cell in the row."""
    return [
        (cls.strip(), float(val))
        for cls, val in re.findall(r'class="numero([^"]*)" data-value="(-?[\d.]+)"', row_html)
    ]


def _plain_numeros(row_html):
    return [val for cls, val in _numeros(row_html) if cls == ""]


def fetch_cpi_yoy():
    html = _fetch_text(CPI_URL)
    out = {}
    for _, slug in PAISES:
        row = _row_html(html, "/countries-cpi/", slug)
        plain = _plain_numeros(row) if row else []
        out[slug] = plain[0] if plain else None
    return out


def fetch_unemployment():
    html = _fetch_text(UNEMPLOYMENT_URL)
    out = {}
    for _, slug in PAISES:
        row = _row_html(html, "/unemployment/", slug)
        plain = _plain_numeros(row) if row else []
        out[slug] = plain[0] if plain else None
    return out


def fetch_trade_balance_pct_gdp():
    html = _fetch_text(TRADE_BALANCE_URL)
    out = {}
    for _, slug in PAISES:
        row = _row_html(html, "/trade/balance/", slug)
        plain = _plain_numeros(row) if row else []
        # plain[0] = coverage rate, plain[1] = trade balance % GDP
        out[slug] = plain[1] if len(plain) > 1 else None
    return out


def fetch_deficit_pct_gdp():
    html = _fetch_text(DEFICIT_URL)
    out = {}
    for _, slug in PAISES:
        row = _row_html(html, "/deficit/", slug)
        plain = _plain_numeros(row) if row else []
        out[slug] = plain[0] if plain else None
    return out


def fetch_macro_indicators():
    cpi = fetch_cpi_yoy()
    unemployment = fetch_unemployment()
    trade = fetch_trade_balance_pct_gdp()
    deficit = fetch_deficit_pct_gdp()
    out = []
    for nombre, slug in PAISES:
        out.append({
            "pais": nombre,
            "inflacion": cpi.get(slug),
            "desempleo": unemployment.get(slug),
            "balanza_comercial_pib": trade.get(slug),
            "deficit_fiscal_pib": deficit.get(slug),
        })
    return out
