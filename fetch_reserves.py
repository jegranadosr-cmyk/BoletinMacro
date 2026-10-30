"""Fetch proven crude oil and natural gas reserves per country.

- Oil: countryeconomy.com's own "Crude Oil Reserves (Million barrels)" page
  per country (/energy-and-environment/crude-oil/reserves/{slug}) -- same
  site/pattern used throughout this bulletin, verified against known real-
  world figures (e.g. Saudi Arabia ~258,600 million barrels, Canada's oil
  sands ~170,300).
- Gas: countryeconomy.com doesn't track this at all (checked). Natural gas
  proved reserves instead come from Wikipedia's "List of countries by
  natural gas proven reserves" wikitable (billions of cubic metres, U.S.
  EIA 2021 column) -- a plain server-rendered table, no JS needed. The CIA
  World Factbook (which has the same data) actively blocks headless
  browsers (returned "Access Denied" to Playwright during testing), so
  Wikipedia was used instead.

The Eurozone isn't a single country and isn't tracked by either source, so
callers should expect no entry for "Eurozona" in either dict.
"""
import re
import socket
import urllib.request

_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only_getaddrinfo

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

OIL_URL = "https://countryeconomy.com/energy-and-environment/crude-oil/reserves/{slug}"
GAS_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_countries_by_natural_gas_proven_reserves"

# (nombre mostrado, slug countryeconomy.com, nombre en ingles en Wikipedia)
PAISES = [
    ("Colombia", "colombia", "Colombia"),
    ("EE.UU.", "usa", "United States"),
    ("Iran", "iran", "Iran"),
    ("Iraq", "iraq", "Iraq"),
    ("Alemania", "germany", "Germany"),
    ("India", "india", "India"),
    ("China", "china", "China"),
    ("Brasil", "brazil", "Brazil"),
    ("Rusia", "russia", "Russia"),
    ("Arabia Saudita", "saudi-arabia", "Saudi Arabia"),
    ("Qatar", "qatar", "Qatar"),
    ("Indonesia", "indonesia", "Indonesia"),
    ("Canadá", "canada", "Canada"),
    ("Australia", "australia", "Australia"),
    ("Kuwait", "kuwait", "Kuwait"),
    # Reemplaza a Corea del Sur en la tabla de territorio/reservas (pedido
    # explicito del usuario) -- Corea del Sur sigue en la tabla de poblacion/PIB.
    ("Venezuela", "venezuela", "Venezuela"),
    # Reemplaza a Japon en la tabla de territorio/reservas (pedido explicito
    # del usuario) -- Japon sigue en la tabla de poblacion/PIB.
    ("EAU", "united-arab-emirates", "United Arab Emirates"),
]


def _fetch_text(url, timeout=20):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def fetch_oil_reserves_mmbbl():
    out = {}
    for _, slug, _ in PAISES:
        try:
            html = _fetch_text(OIL_URL.format(slug=slug))
            m = re.search(r'class="numero" data-value="([\d.]+)"', html)
            out[slug] = float(m.group(1)) if m else None
        except Exception:
            out[slug] = None
    return out


def fetch_gas_reserves_bcm():
    """Billions of cubic metres, U.S. EIA (2021) column of the Wikipedia table."""
    try:
        html = _fetch_text(GAS_WIKI_URL)
    except Exception:
        return {}
    idx = html.find('<table class="wikitable')
    tbl_end = html.find("</table>", idx)
    table_html = html[idx:tbl_end] if idx != -1 and tbl_end != -1 else ""
    out = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.S):
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)
        cleaned = [re.sub("<[^>]+>", "", c).strip() for c in cells]
        if len(cleaned) < 2:
            continue
        name = cleaned[0].replace(" *", "").strip()
        value_str = cleaned[1].replace(",", "")
        try:
            out[name] = float(value_str)
        except ValueError:
            continue
    return out


def fetch_reserves():
    oil = fetch_oil_reserves_mmbbl()
    gas = fetch_gas_reserves_bcm()
    out = []
    for nombre, slug, wiki_name in PAISES:
        out.append({
            "pais": nombre,
            "petroleo_mmbbl": oil.get(slug),
            "gas_bcm": gas.get(wiki_name),
        })
    return out
