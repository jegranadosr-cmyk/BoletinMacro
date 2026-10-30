"""Fetch upcoming macro calendar events from TradingEconomics using a real
headless browser (Playwright).

Investigated and ruled out earlier this session as a plain HTTP scrape: the
table is server-rendered in the initial HTML (so a plain GET does return
rows), but the date-range controls (which filter to "this week" / "next
week" etc.) are purely client-side (a cookie + page reload triggered by
setCalendarRange(n), defined in an inline <script>) and the default,
cookie-less load already returns roughly the next 7 days of events, which
is enough for this bulletin's "next 5 business days" ask -- so a real
browser isn't strictly required for the date range, but IS required to read
the Actual/Previous/Consensus/Forecast values, which live in
<span id="actual">/<span id="previous">/<a id="consensus">/<a id="forecast">
inside each row and are present in the static HTML already (no JS needed
there, this module just uses Playwright for consistency with fetch_cds.py
and because the default page load itself benefits from JS-driven relative
styling we don't otherwise depend on).
"""
from playwright.sync_api import sync_playwright

CALENDAR_URL = "https://tradingeconomics.com/calendar"

RELEVANT_COUNTRIES = {
    "united states", "euro area", "france", "germany", "italy", "spain",
    "china", "japan", "colombia",
}

# Keyword fragments matched against the TE `data-category` slug (lowercase).
RELEVANT_CATEGORY_KEYWORDS = (
    "gdp", "inflation rate", "interest rate", "unemployment", "retail sales",
    "trade balance", "balance of trade", "government budget", "manufacturing pmi",
    "services pmi", "composite pmi", "business confidence", "consumer confidence",
    "industrial production", "producer price",
)

PAIS_ES = {
    "united states": "EE.UU.", "euro area": "Eurozona", "france": "Francia",
    "germany": "Alemania", "italy": "Italia", "spain": "España",
    "china": "China", "japan": "Japón", "colombia": "Colombia",
}


def _is_relevant_category(category):
    return any(kw in category for kw in RELEVANT_CATEGORY_KEYWORDS)


def fetch_upcoming_events(max_items=8):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        page.goto(CALENDAR_URL, timeout=30000)
        page.wait_for_timeout(3000)
        rows = page.evaluate("""
        () => {
          const trs = document.querySelectorAll('tr[data-url]');
          const out = [];
          for (const tr of trs) {
            const country = tr.getAttribute('data-country');
            const category = tr.getAttribute('data-category');
            if (!country || !category) continue;
            const dateCell = tr.querySelector('td[class*="-"]');
            let date = null, time = null;
            if (dateCell) {
              const m = dateCell.className.match(/(\\d{4}-\\d{2}-\\d{2})/);
              if (m) date = m[1];
              const span = dateCell.querySelector('span');
              if (span) time = span.textContent.trim();
            }
            const eventLink = tr.querySelector('a.calendar-event');
            const refSpan = tr.querySelector('span.calendar-reference');
            const actual = tr.querySelector('#actual');
            const previous = tr.querySelector('#previous');
            const consensus = tr.querySelector('#consensus');
            const forecast = tr.querySelector('#forecast');
            out.push({
              country, category, date, time,
              event: eventLink ? eventLink.textContent.trim() : null,
              periodo: refSpan ? refSpan.textContent.trim() : null,
              actual: actual ? actual.textContent.trim() : '',
              previous: previous ? previous.textContent.trim() : '',
              consensus: consensus ? consensus.textContent.trim() : '',
              forecast: forecast ? forecast.textContent.trim() : '',
            });
          }
          return out;
        }
        """)
        browser.close()

    out = []
    for r in rows:
        if r["country"] not in RELEVANT_COUNTRIES:
            continue
        if not _is_relevant_category(r["category"]):
            continue
        if not r["date"] or not r["event"]:
            continue
        if r["actual"]:
            continue  # already released -- this is an upcoming-events list
        out.append({
            "pais": PAIS_ES.get(r["country"], r["country"]),
            "evento": r["event"],
            "periodo": r["periodo"] or "",
            "fecha": r["date"],
            "hora": r["time"] or "",
            "previo": r["previous"] or "-",
            "consenso": r["consensus"] or r["forecast"] or "-",
        })

    out.sort(key=lambda e: (e["fecha"], e["hora"]))

    # Dedupe (e.g. "X Final" repeats the flash estimate's category) and cap.
    seen = set()
    deduped = []
    for e in out:
        key = (e["pais"], e["evento"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)

    return deduped[:max_items]
