"""Fetch real 5-year sovereign CDS spreads (basis points) from
worldgovernmentbonds.com using a real headless browser (Playwright).

Investigated twice this session as a plain HTTP scrape and ruled out both
times: the number is filled in by client-side JS after the initial HTML
loads (element with data-async-variable='jsGlobalResult|result.ultimoValore'
starts as '----' and gets replaced), and no JSON endpoint reachable with a
simple GET/POST was found. A real browser renders it correctly, so this
module reuses Playwright (already a hard dependency for the PNG render
step) instead of urllib like the other fetch_*.py modules.

This is the real sovereign CDS, NOT the countryeconomy.com bond-spread-vs-
Bund figure in fetch_debt_bonds.py (riesgo_pais_pb) -- the two measure
different things and can differ a lot (e.g. Colombia: ~960bp bond spread
vs ~150bp CDS, because the bond spread also reflects currency and expected-
inflation differentials that a CDS, quoted in USD, does not).
"""
from playwright.sync_api import sync_playwright

PAISES = [
    ("Francia", "france"),
    ("Alemania", "germany"),
    ("Italia", "italy"),
    ("España", "spain"),
    ("EE.UU.", "united-states"),
    ("China", "china"),
    ("Japón", "japan"),
    ("Colombia", "colombia"),
    ("Brasil", "brazil"),
    ("México", "mexico"),
    ("Chile", "chile"),
    ("Perú", "peru"),
]

URL = "https://www.worldgovernmentbonds.com/cds-historical-data/{slug}/5-years/"
SELECTOR = '[data-async-variable="jsGlobalResult|result.ultimoValore"]'


def fetch_cds_5y():
    out = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for nombre, slug in PAISES:
            page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            try:
                page.goto(URL.format(slug=slug), timeout=20000)
                page.wait_for_timeout(2500)
                text = page.evaluate(f"document.querySelector('{SELECTOR}')?.textContent")
                out[nombre] = float(text) if text and text.strip() not in ("", "----") else None
            except Exception:
                out[nombre] = None
            page.close()
        browser.close()
    return out
