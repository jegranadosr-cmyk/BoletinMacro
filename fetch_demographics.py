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
    # Solo para la tabla de territorio/reservas (reemplaza a Corea del Sur
    # ahi, pedido explicito del usuario) -- no aparece en la tabla de
    # poblacion/PIB, que conserva a Corea del Sur.
    ("Venezuela", "VEN", "Venezuela"),
    # EAU: se agrega a la tabla de poblacion/PIB (sin quitar a Japon) y
    # tambien reemplaza a Japon en la tabla de territorio/reservas.
    ("EAU", "ARE", "United Arab Emirates"),
    # Kazajistan: se agrega a la tabla de poblacion/PIB (sin quitar a
    # Alemania) y tambien reemplaza a Alemania en la tabla de
    # territorio/reservas.
    ("Kazajistán", "KAZ", "Kazakhstan"),
]

# El indicador AG.SRF.TOTL.K2 del Banco Mundial trae un dato de Canada
# consistentemente erroneo (15,634,410-15,640,500 km2 en toda la serie
# historica, verificado 2026-10-30) -- un 56% mas grande que el area real de
# Canada (9,984,670 km2, segun Wikipedia/UN Statistics Division y el
# consenso de otras fuentes como CIA World Factbook). El resto de paises
# grandes de este boletin (Rusia, EE.UU., China, Brasil, Australia, India)
# coinciden con Wikipedia dentro de un margen normal (0-3%, o diferencias de
# definicion conocidas como la de India con Cachemira) -- Canada es el unico
# caso con un error real, no una diferencia de convencion. Se sobreescribe
# con el valor correcto en vez de usar el dato crudo de la API.
AREA_OVERRIDE_KM2 = {
    "Canadá": 9984670,
}


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
        if nombre in AREA_OVERRIDE_KM2:
            area_km2 = AREA_OVERRIDE_KM2[nombre]
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
