"""Fetch balance-of-payments indicators (current account, capital account,
international reserves) from the World Bank's public API (no key required).

Verified live (Oct 2026):
- Current account % GDP: BN.CAB.XOKA.GD.ZS (most countries). Not published
  for the Euro area aggregate (EMU), so it's derived there from the raw USD
  current account (BN.CAB.XOKA.CD) divided by GDP in USD (NY.GDP.MKTP.CD).
- Capital account, current US$: BN.TRF.KOGT.CD. This is the BPM6 "capital
  account" proper (capital transfers, debt forgiveness, etc.) -- usually a
  very small number, not to be confused with the much larger "financial
  account". Not reported for Colombia.
- International reserves, current US$: FI.RES.TOTL.CD.

Country codes: COL, USA, EMU (euro area aggregate), FRA, DEU, ITA, ESP, CHN, JPN.

CDS (credit default swaps) were investigated but no free, statically
scrapable source was found: worldgovernmentbonds.com's sovereign-cds pages
load their numbers through a WordPress REST route
(/wp-json/common/v1/historical) that expects a POST payload mirroring a
large inline JS object (country symbol, date range, etc.) that isn't
practical to reverse-engineer reliably for an unattended daily job.
countryeconomy.com and tradingeconomics.com don't carry CDS at all. The
"riesgo_pais_pb" field in fetch_debt_bonds.py (risk premium, bp) is used as
the closest available proxy for sovereign credit risk.
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
BASE = "https://api.worldbank.org/v2/country/{country}/indicator/{indicator}?format=json&per_page=20"

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


def fetch_balance_of_payments():
    out = []
    for nombre, code in PAISES:
        try:
            ca_pct = _latest(code, "BN.CAB.XOKA.GD.ZS")
            if ca_pct is None:
                # Euro area aggregate isn't published as %GDP -- derive it.
                ca_usd = _latest(code, "BN.CAB.XOKA.CD")
                gdp_usd = _latest(code, "NY.GDP.MKTP.CD")
                ca_pct = (ca_usd / gdp_usd * 100) if (ca_usd is not None and gdp_usd) else None
        except Exception:
            ca_pct = None

        try:
            capital_usd = _latest(code, "BN.TRF.KOGT.CD")
        except Exception:
            capital_usd = None

        try:
            reservas_usd = _latest(code, "FI.RES.TOTL.CD")
        except Exception:
            reservas_usd = None

        out.append({
            "pais": nombre,
            "cuenta_corriente_pib": ca_pct,
            "cuenta_capital_usd": capital_usd,
            "reservas_internacionales_usd": reservas_usd,
        })
    return out
