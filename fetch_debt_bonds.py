"""Fetch government debt-to-GDP, 10-year bond yields and sovereign credit
ratings for the UK, France, Germany, Italy, Spain, USA, India, South Korea,
China, Japan, Colombia and Vietnam -- the "Fiscal y riesgo soberano" table
on page 1 (Bangladesh was removed from just this table, pedido explicito
del usuario 2026-11-01 -- it still appears in the other two page-1 tables,
via REGIONES in main.py). Sources verified against independent reporting
(Oct 2026):
- Debt/GDP: countryeconomy.com national-debt overview table (all 12).
- 10Y yield: countryeconomy.com bonds overview table (UK/France/Germany/
  Italy/Spain/USA/India); Colombia has its own countryeconomy.com page;
  China, South Korea and Vietnam aren't tracked there at all, so those come
  from tradingeconomics.com's live quote span instead.
- Ratings: countryeconomy.com ratings overview table (all 12) -- except
  Vietnam's Moody's/S&P cells, which are blank there (genuinely missing,
  not just unrated: Vietnam IS rated by both in reality, Ba2/BB+ as of
  2025-2026) -- those two are filled in from tradingeconomics.com/vietnam/
  rating's meta description instead (verified 2026-11-01 against multiple
  independent press sources). Vietnam's Fitch rating, sourced from
  countryeconomy.com like everyone else's, was cross-checked the same way
  and found to lag real-time (shows "BB", current sovereign issuer rating
  is "BB+" per Fitch's own June-2025 affirmation) -- same class of staleness
  previously found for the US's Fitch rating on this site. Per that
  precedent, this is NOT hand-corrected here (a daily automated pipeline
  shouldn't silently override a live-scraped value with a hand-typed one
  that will itself go stale next time Fitch acts) -- documented here and in
  the bulletin's footnote instead.

Sovereign risk is NOT part of this module -- see fetch_cds.py for the real
5-year CDS spread (a review on 2026-10-29 correctly flagged that this
module's earlier "riesgo_pais_pb" field, countryeconomy.com's bond-spread-
vs-Bund figure, doesn't measure the same thing as a CDS/EMBI and was
mislabeled as "riesgo país"; it has been dropped from this module in favor
of the real CDS number).
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
TE_BOND_URL = "https://tradingeconomics.com/{te_slug}/government-bond-yield"
RATINGS_URL = "https://countryeconomy.com/ratings"
TE_RATING_URL = "https://tradingeconomics.com/{te_slug}/rating"

PAISES = [
    ("Inglaterra", "uk"),
    ("Francia", "france"),
    ("Alemania", "germany"),
    ("Italia", "italy"),
    ("España", "spain"),
    ("EE.UU.", "usa"),
    ("China", "china"),
    ("Japón", "japan"),
    ("Colombia", "colombia"),
    ("India", "india"),
    ("Corea del Sur", "south-korea"),
    ("Vietnam", "vietnam"),
]

# Countries whose 10Y yield isn't on countryeconomy.com's overview table or
# its own page -- fetched live from tradingeconomics.com instead. Slug is
# the same as countryeconomy.com's here, conveniently.
TE_BOND_SLUGS = {"china", "south-korea", "vietnam"}

# Countries missing Moody's and/or S&P on countryeconomy.com's ratings table
# (genuinely rated by those agencies in reality, just not shown there) --
# filled in from tradingeconomics.com's ratings page instead.
TE_RATING_FALLBACK_SLUGS = {"vietnam"}


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
    out = {slug: _extract_by_slug(html, "/bonds/", slug) for _, slug in PAISES if slug not in TE_BOND_SLUGS}

    # Colombia: not in the overview table, has its own countryeconomy.com page.
    try:
        col_html = _fetch_text(COLOMBIA_BOND_URL)
        m = re.search(r'class="numero" data-value="([\d.]+)">', col_html)
        out["colombia"] = float(m.group(1)) if m else None
    except Exception:
        out["colombia"] = None

    for slug in TE_BOND_SLUGS:
        try:
            te_html = _fetch_text(TE_BOND_URL.format(te_slug=slug))
            m = re.search(r'id="market_last">([\d.]+)</span>', te_html)
            out[slug] = float(m.group(1)) if m else None
        except Exception:
            out[slug] = None

    return out


def _te_rating(slug):
    """Moody's / S&P from TradingEconomics' ratings page meta description
    (e.g. "Standard & Poor's credit rating for Vietnam stands at BB+ ...
    Moody's credit rating for Vietnam was last set at Ba2 ..."). Fitch isn't
    reliably present in this summary, so it's not parsed here."""
    try:
        html = _fetch_text(TE_RATING_URL.format(te_slug=slug))
    except Exception:
        return None, None
    m = re.search(r'id="metaDesc"[^>]*content="([^"]*)"', html)
    if not m:
        return None, None
    desc = m.group(1)
    sp = re.search(r"Poor\S*\s*credit rating for [^.]*?stands at ([A-Za-z0-9+\-]+)", desc)
    moodys = re.search(r"Moody\S*\s*credit rating for [^.]*?was last set at ([A-Za-z0-9+\-]+)", desc)
    return (moodys.group(1) if moodys else None, sp.group(1) if sp else None)


def fetch_ratings():
    """Moody's / S&P / Fitch sovereign credit ratings from the overview table.

    Each country's row always has exactly 3 rating <td> cells in that order,
    but a given cell can be genuinely empty for a country rated by fewer than
    3 agencies (verified against Iran/Iraq, each only rated by Fitch, while
    this module covered them -- their Moody's/S&P cells were blank <td></td>,
    not missing data). Parsed per-cell rather than requiring all 3 to be
    present, so a partially-rated country still surfaces the rating(s) it
    does have. For slugs in TE_RATING_FALLBACK_SLUGS, a still-missing
    Moody's/S&P after that is filled in from TradingEconomics (see module
    docstring -- Vietnam is rated by both in reality, just not shown here).
    """
    html = _fetch_text(RATINGS_URL)
    out = {}
    for _, slug in PAISES:
        idx = html.find(f'href="/ratings/{slug}"')
        if idx == -1:
            out[slug] = (None, None, None)
            continue
        row_end = html.find("</tr>", idx)
        row = html[idx:row_end]
        tds = re.findall(r"<td>(.*?)</td>", row, re.S)
        vals = []
        for td in tds[:3]:
            m = re.search(r'class="padleft">\s*([^<]+?)\s*</span>', td)
            vals.append(m.group(1) if m else None)
        while len(vals) < 3:
            vals.append(None)
        out[slug] = tuple(vals)

    for slug in TE_RATING_FALLBACK_SLUGS:
        moodys, sp, fitch = out.get(slug, (None, None, None))
        if moodys is None or sp is None:
            te_moodys, te_sp = _te_rating(slug)
            moodys = moodys or te_moodys
            sp = sp or te_sp
            out[slug] = (moodys, sp, fitch)

    return out


def fetch_debt_and_bonds():
    debt = fetch_debt_to_gdp()
    bonds = fetch_bond_yields()
    ratings = fetch_ratings()
    out = []
    for nombre, slug in PAISES:
        moodys, sp, fitch = ratings.get(slug, (None, None, None))
        out.append({
            "pais": nombre,
            "deuda_pib": debt.get(slug),
            "bono_10y": bonds.get(slug),
            "rating_moodys": moodys,
            "rating_sp": sp,
            "rating_fitch": fitch,
        })
    return out
