"""Fetch government debt-to-GDP and 10-year bond yields for France, USA, China,
Japan and Colombia. Sources verified against independent reporting (Oct 2026):
- Debt/GDP: countryeconomy.com national-debt overview table (all 5 countries).
- 10Y yield: countryeconomy.com bonds overview table (USA/France/Japan) and its
  individual country page (Colombia); China isn't tracked there, so it's sourced
  from tradingeconomics.com's live quote span instead.
"""
import re
import socket
import urllib.request

_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only_getaddrinfo

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

DEBT_URL = "https://countryeconomy.com/national-debt"
BONDS_URL = "https://countryeconomy.com/bonds"
COLOMBIA_BOND_URL = "https://countryeconomy.com/bonds/colombia"
CHINA_BOND_URL = "https://tradingeconomics.com/china/government-bond-yield"

PAISES = [
    ("Francia", "france"),
    ("EE.UU.", "usa"),
    ("China", "china"),
    ("Japón", "japan"),
    ("Colombia", "colombia"),
]


def _fetch_text(url, timeout=20):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _extract_by_slug(html, base_path, slug):
    pattern = re.compile(
        r"href='" + re.escape(base_path) + re.escape(slug) + r"'.*?"
        r'class="numero" data-value="([\d.]+)">',
        re.S,
    )
    m = pattern.search(html)
    return float(m.group(1)) if m else None


def fetch_debt_to_gdp():
    html = _fetch_text(DEBT_URL)
    return {slug: _extract_by_slug(html, "/national-debt/", slug) for _, slug in PAISES}


def fetch_bond_yields():
    html = _fetch_text(BONDS_URL)
    out = {slug: _extract_by_slug(html, "/bonds/", slug) for _, slug in PAISES}

    # Colombia: not in the overview table, has its own page.
    try:
        col_html = _fetch_text(COLOMBIA_BOND_URL)
        m = re.search(r'class="numero" data-value="([\d.]+)">', col_html)
        out["colombia"] = float(m.group(1)) if m else None
    except Exception:
        out["colombia"] = None

    # China: not tracked by countryeconomy.com at all; use tradingeconomics.com.
    try:
        cn_html = _fetch_text(CHINA_BOND_URL)
        m = re.search(r'id="market_last">([\d.]+)</span>', cn_html)
        out["china"] = float(m.group(1)) if m else None
    except Exception:
        out["china"] = None

    return out


def fetch_debt_and_bonds():
    debt = fetch_debt_to_gdp()
    bonds = fetch_bond_yields()
    out = []
    for nombre, slug in PAISES:
        out.append({
            "pais": nombre,
            "deuda_pib": debt.get(slug),
            "bono_10y": bonds.get(slug),
        })
    return out
