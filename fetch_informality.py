"""Fetch the informal employment rate (% of total employment) from Our World
in Data's public CSV export (no key required) -- itself a republication of
UN SDG indicator 8.3.1 ("Proportion of informal employment, by sector and
sex", 13th ICLS standard), the official standardized cross-country measure
(ILO's own term: jobs lacking basic social/legal protection and employment
benefits).

Switched from ILOSTAT's raw DF_EMP_PIFL_SEX_RT dataflow (2026-11-01) after
finding that dataflow gave a UK figure (~20%) wildly inconsistent with
independent verification (~6.5%, Euronews Aug 2024 citing ILO) -- traced to
the UK's entry there being sourced from EU-SILC's narrower "no written
contract" proxy instead of the standard definition. This OWID/SDG-8.3.1
series gives 6.51% for the UK's latest reported year (2018), matching that
external figure closely. Spot-checked the same way against Italy, France,
Germany and Spain and found much closer agreement across the board than the
old source, not just for the UK -- this is simply the better, more current,
single consistent series (one CSV, ~1.5s to fetch, vs. the old ~1.5MB
ILOSTAT bulk dump).

NOT covered for the USA, China or Japan -- confirmed via multiple ILO-
adjacent sources (this one, ILOSTAT's raw series, academic estimates) that
none of the three publish a comparable harmonized figure; this is a
genuine, structural reporting gap (these countries don't run the household
surveys this indicator needs), not a scraping failure.
"""
import socket
import urllib.request

_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only_getaddrinfo

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
OWID_URL = "https://ourworldindata.org/grapher/share-in-informal-employment.csv?v=1"

PAISES = [
    ("Colombia", "COL"),
    ("EE.UU.", "USA"),
    ("Inglaterra", "GBR"),
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


def fetch_informalidad():
    csv_text = _fetch_text(OWID_URL)
    lines = csv_text.splitlines()
    latest_by_code = {}
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) < 4:
            continue
        code, year, value = parts[1], parts[2], parts[3]
        if not value:
            continue
        try:
            year_int = int(year)
            val = float(value)
        except ValueError:
            continue
        if code not in latest_by_code or year_int > latest_by_code[code][0]:
            latest_by_code[code] = (year_int, val)

    out = []
    for nombre, code in PAISES:
        entry = latest_by_code.get(code)
        out.append({"pais": nombre, "informalidad_pct": entry[1] if entry else None})
    return out
