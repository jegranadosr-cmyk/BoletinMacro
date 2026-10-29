"""Fetch Eurozone aggregate macro indicators from Eurostat's public JSON API
(no key required). countryeconomy.com doesn't track the Eurozone as a block,
so this is a separate source from fetch_countryeconomy.py.

Verified live (Oct 2026):
- GDP growth YoY: namq_10_gdp, na_item=B1GQ, unit=CLV_PCH_SM (seasonally
  adjusted real GDP, % change on same quarter of previous year).
- Inflation YoY: prc_hicp_manr, coicop=CP00 (HICP all-items, annual rate).
- Unemployment: une_rt_m, seasonally adjusted, total, both sexes.
- Trade balance: not reliably available under a short Eurostat code within
  reasonable effort -- left as None; the bulletin shows "-" for this cell.
- Fiscal deficit % GDP: gov_10dd_edpt1, na_item=B9 (net lending/borrowing),
  sector=S13 (general government), unit=PC_GDP.

Eurostat uses different aggregate geo codes per dataset vintage (EA20 vs
EA21 vs EA19), so each fetch tries a short list of candidates.
"""
import json
import socket
import urllib.request

_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only_getaddrinfo

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}?format=JSON&{params}&lang=en"

EUROZONE_GEOS = ["EA21", "EA20", "EA19", "EA"]


def _fetch_json(url, timeout=20):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _latest_value(data):
    time_dim = data["dimension"]["time"]["category"]["index"]
    idx_to_time = {v: k for k, v in time_dim.items()}
    value = data["value"]
    if not value:
        return None, None
    max_idx = max(int(k) for k in value.keys())
    return value[str(max_idx)], idx_to_time.get(max_idx)


def _try_geos(dataset, params):
    for geo in EUROZONE_GEOS:
        url = BASE.format(dataset=dataset, params=f"{params}&geo={geo}")
        try:
            data = _fetch_json(url)
            val, fecha = _latest_value(data)
            if val is not None:
                return val, fecha
        except Exception:
            continue
    return None, None


def fetch_gdp_growth():
    val, fecha = _try_geos("namq_10_gdp", "s_adj=SCA&na_item=B1GQ&unit=CLV_PCH_SM")
    return val, fecha


def fetch_cpi_yoy():
    val, fecha = _try_geos("prc_hicp_manr", "coicop=CP00")
    return val, fecha


def fetch_unemployment():
    val, fecha = _try_geos("une_rt_m", "s_adj=SA&age=TOTAL&unit=PC_ACT&sex=T")
    return val, fecha


def fetch_deficit_pct_gdp():
    val, fecha = _try_geos("gov_10dd_edpt1", "na_item=B9&sector=S13&unit=PC_GDP")
    return val, fecha


def fetch_macro_indicators():
    pib, _ = fetch_gdp_growth()
    ipc, _ = fetch_cpi_yoy()
    desempleo, _ = fetch_unemployment()
    deficit, _ = fetch_deficit_pct_gdp()
    return {
        "pais": "Eurozona",
        "pib_crecimiento": pib,
        "inflacion": ipc,
        "desempleo": desempleo,
        "balanza_comercial_pib": None,
        "deficit_fiscal_pib": deficit,
    }
