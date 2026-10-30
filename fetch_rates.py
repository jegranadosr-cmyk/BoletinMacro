"""Fetch central bank policy interest rates from multiple verified sources.

Each source was cross-checked against independent news reporting (Oct 2026):
- Fed: FRED official series (DFEDTARL/DFEDTARU) -> target range, most authoritative.
- ECB: FRED official series (ECBDFR, deposit facility rate -- the ECB's actual
  operative policy rate since the 2022 framework change). NOTE: countryeconomy.com
  and some aggregators report the MRO/refinancing rate instead (0.15pp higher,
  e.g. 2.65% vs 2.50%) -- that is a different, less-cited rate, not an error,
  but we standardize on the deposit facility rate here.
- BOJ: countryeconomy.com's figure for Japan was confirmed stale (stuck at the
  2024 value), so Japan is sourced from global-rates.com instead, which matched
  independent news reporting.
- PBOC / BanRep: countryeconomy.com verified correct against independent sources.
"""
import re
import socket
import urllib.request

# Force IPv4-only resolution -- see fetch_market.py for why (broken/slow IPv6
# route in this environment turns every first connection attempt into a ~15-30s
# stall before falling back to IPv4). Applied here too since this module may be
# imported standalone, without fetch_market having run first.
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only_getaddrinfo

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
# FRED's graph.csv endpoint rejects browser-style User-Agents (connection reset)
# but allows curl's -- harmless quirk of their edge/WAF, not auth-related.
FRED_HEADERS = {"User-Agent": "curl/8.0"}

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
COUNTRYECONOMY_URL = "https://countryeconomy.com/key-rates"
BOJ_URL = "https://www.global-rates.com/en/interest-rates/central-banks/9/japanese-boj-overnight-call-rate/"


def _fetch_text(url, timeout=20, headers=None):
    req = urllib.request.Request(url, headers=headers or HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _fred_series(series_id):
    """Returns list of (date_str, value_float) for a FRED series, oldest first."""
    csv_text = _fetch_text(FRED_CSV.format(series=series_id), headers=FRED_HEADERS)
    rows = []
    for line in csv_text.strip().splitlines()[1:]:
        parts = line.split(",")
        if len(parts) != 2:
            continue
        date_str, val_str = parts
        try:
            rows.append((date_str, float(val_str)))
        except ValueError:
            continue
    return rows


def _fred_current_and_change_date(series_id):
    rows = _fred_series(series_id)
    if not rows:
        return None, None
    current = rows[-1][1]
    change_date = rows[-1][0]
    for date_str, val in reversed(rows):
        if val == current:
            change_date = date_str
        else:
            break
    return current, change_date


def fetch_fed():
    upper, date_u = _fred_current_and_change_date("DFEDTARU")
    lower, date_l = _fred_current_and_change_date("DFEDTARL")
    if upper is None or lower is None:
        return {"pais": "EE.UU.", "banco": "Fed", "tasa": None, "tasa_label": None, "fecha": None}
    return {
        "pais": "EE.UU.", "banco": "Fed",
        "tasa": upper,
        "tasa_label": f"{lower:.2f}%-{upper:.2f}%",
        "fecha": date_u,
    }


def fetch_ecb():
    val, date = _fred_current_and_change_date("ECBDFR")
    if val is None:
        return {"pais": "Eurozona", "banco": "BCE", "tasa": None, "tasa_label": None, "fecha": None}
    return {"pais": "Eurozona", "banco": "BCE", "tasa": val, "tasa_label": f"{val:.2f}%", "fecha": date}


def fetch_boj():
    html = _fetch_text(BOJ_URL)
    tbody_idx = html.find("<tbody>")
    search_region = html[tbody_idx:] if tbody_idx != -1 else html
    m = re.search(
        r'table-normal text-start">([^<]+)</div>.*?table-bold text-end">([\d.]+)\s*%</div>',
        search_region, re.S,
    )
    if not m:
        return {"pais": "Japón", "banco": "BOJ", "tasa": None, "tasa_label": None, "fecha": None}
    date_str, rate_str = m.group(1).strip(), m.group(2).strip()
    mm, dd, yyyy = date_str.split("-")
    iso_date = f"{yyyy}-{mm}-{dd}"
    val = float(rate_str)
    return {"pais": "Japón", "banco": "BOJ", "tasa": val, "tasa_label": f"{val:.2f}%", "fecha": iso_date}


def _countryeconomy_rate(slug):
    html = _fetch_text(COUNTRYECONOMY_URL)
    pattern = re.compile(
        r'href="/key-rates/' + re.escape(slug) + r'"[^>]*>.*?</a></td>'
        r'<td class="fecha" data-value="([^"]+)">[^<]+</td>'
        r'<td class="numero" data-value="([^"]+)">([^<]+)</td>',
        re.S,
    )
    m = pattern.search(html)
    if not m:
        return None, None
    fecha, valor_str, _ = m.groups()
    return float(valor_str), fecha


def fetch_china():
    val, fecha = _countryeconomy_rate("china")
    if val is None:
        return {"pais": "China", "banco": "PBOC", "tasa": None, "tasa_label": None, "fecha": None}
    return {"pais": "China", "banco": "PBOC", "tasa": val, "tasa_label": f"{val:.2f}%", "fecha": fecha}


def fetch_colombia():
    val, fecha = _countryeconomy_rate("colombia")
    if val is None:
        return {"pais": "Colombia", "banco": "BanRep", "tasa": None, "tasa_label": None, "fecha": None}
    return {"pais": "Colombia", "banco": "BanRep", "tasa": val, "tasa_label": f"{val:.2f}%", "fecha": fecha}


def _simple_rate(pais, slug, banco):
    val, fecha = _countryeconomy_rate(slug)
    if val is None:
        return {"pais": pais, "banco": banco, "tasa": None, "tasa_label": None, "fecha": None}
    return {"pais": pais, "banco": banco, "tasa": val, "tasa_label": f"{val:.2f}%", "fecha": fecha}


def fetch_india():
    return _simple_rate("India", "india", "RBI")


def fetch_south_korea():
    return _simple_rate("Corea del Sur", "south-korea", "BOK")


def fetch_policy_rates():
    fetchers = [fetch_ecb, fetch_fed, fetch_china, fetch_boj, fetch_colombia,
                fetch_india, fetch_south_korea]
    out = []
    for fn in fetchers:
        try:
            out.append(fn())
        except Exception:
            out.append({"pais": "?", "banco": fn.__name__, "tasa": None, "tasa_label": None, "fecha": None})
    return out
