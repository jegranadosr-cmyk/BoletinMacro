"""Fetch the informal employment rate (% of total employment) from ILOSTAT's
public bulk CSV API (no key required) -- dataflow DF_EMP_PIFL_SEX_RT, measure
EMP_PIFL_RT, sex SEX_T (total both sexes). This is the standard ILO
"informal employment" indicator (ICLS 2018 definition: informal jobs,
whether in the formal or informal sector) -- broader than, and usually
cited over, "employment in the informal sector" alone.

Verified live (Oct/Nov 2026) against known figures: Colombia ~45-46%
(monthly LFS, the freshest series of the bunch), India ~80%, Bangladesh
~70%, Vietnam ~62%, Italy ~8-10% (notably higher than its EU peers, a well
known fact about the Italian labor market), France/Germany/Spain in the
low single digits.

NOT covered for the USA, China or Japan -- none of the three report this
indicator to ILOSTAT in a comparable harmonized series (shown as "-"; this
is a genuine reporting gap, not a scraping failure).

Reporting frequency varies by country (monthly/quarterly/annual, mixed
within the same dataset) -- _parse_period() orders periods chronologically
regardless of granularity so "latest" is always correct.
"""
import socket
import urllib.request

_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only_getaddrinfo

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
ILOSTAT_URL = "https://sdmx.ilo.org/rest/data/ILO,DF_EMP_PIFL_SEX_RT,1.0/all?format=csv&startPeriod=2018"

PAISES = [
    ("Colombia", "COL"),
    ("EE.UU.", "USA"),
    ("Reino Unido", "GBR"),
    ("Francia", "FRA"),
    ("Alemania", "DEU"),
    ("Italia", "ITA"),
    ("España", "ESP"),
    ("India", "IND"),
    ("Corea del Sur", "KOR"),
    ("China", "CHN"),
    ("Japón", "JPN"),
    ("Vietnam", "VNM"),
    ("Bangladesh", "BGD"),
]


def _fetch_text(url, timeout=30):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _parse_period(period):
    """Sortable (year, sub-period) tuple for annual/quarterly/monthly periods."""
    if "-M" in period:
        y, m = period.split("-M")
        return (int(y), int(m))
    if "-Q" in period:
        y, q = period.split("-Q")
        return (int(y), int(q) * 3)
    return (int(period), 0)


def fetch_informalidad():
    csv_text = _fetch_text(ILOSTAT_URL)
    lines = csv_text.splitlines()
    latest_by_code = {}
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) < 7:
            continue
        ref_area, sex, period, value = parts[1], parts[4], parts[5], parts[6]
        if sex != "SEX_T" or not value:
            continue
        try:
            key = _parse_period(period)
            val = float(value)
        except ValueError:
            continue
        if ref_area not in latest_by_code or key > latest_by_code[ref_area][0]:
            latest_by_code[ref_area] = (key, val)

    out = []
    for nombre, code in PAISES:
        entry = latest_by_code.get(code)
        out.append({"pais": nombre, "informalidad_pct": entry[1] if entry else None})
    return out
