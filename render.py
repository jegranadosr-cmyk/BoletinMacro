import os
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")


def fmt_price(v):
    if v is None:
        return "-"
    return f"{v:,.2f}"


def fmt_big(nombre, v):
    if v is None:
        return "-"
    if nombre == "BITCOIN":
        return f"${v:,.2f}"
    return f"{v:,.2f}"


def pct_plain(v):
    if v is None:
        return "-"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"


def level_pct(v):
    """For level values (inflación, desempleo), not variations -- no forced '+'."""
    if v is None:
        return "-"
    return f"{v:.2f}%"


def fmt_fx(v):
    """4 decimals for FX pairs quoted close to 1 (EUR/USD etc.)."""
    if v is None:
        return "-"
    return f"{v:,.4f}"


def pct_span(v):
    if v is None:
        return '<span class="na">-</span>'
    cls = "up" if v >= 0 else "down"
    sign = "+" if v >= 0 else ""
    return f'<span class="pct {cls}"><span class="dot {cls}"></span>{sign}{v:.2f}%</span>'


def pct_span_compact(v):
    if v is None:
        return '<span class="na">-</span>'
    cls = "up" if v >= 0 else "down"
    sign = "+" if v >= 0 else ""
    return f'<span class="pct {cls}">{sign}{v:.2f}%</span>'


def arrow(v):
    if v is None:
        return ""
    return "▲" if v >= 0 else "▼"


def fmt_usd_billions(v):
    if v is None:
        return "-"
    sign = "+" if v >= 0 else "-"
    return f"{sign}${abs(v) / 1e9:,.1f}B"


def fmt_usd_billions_plain(v):
    if v is None:
        return "-"
    return f"${v / 1e9:,.1f}B"


def fmt_gdp_scaled(v):
    """Trillions if large enough, billions otherwise -- GDP ranges from
    ~$290B (Nigeria) to ~$30T (USA) in this bulletin's country set."""
    if v is None:
        return "-"
    if abs(v) >= 1e12:
        return f"${v / 1e12:,.2f}T"
    return f"${v / 1e9:,.1f}B"


def fmt_population(v):
    if v is None:
        return "-"
    return f"{v / 1e6:,.1f}M"


def fmt_usd_plain(v):
    """Plain dollar amount with thousands separators, no scaling (GDP per capita)."""
    if v is None:
        return "-"
    return f"${v:,.0f}"


def fmt_int_commas(v):
    if v is None:
        return "-"
    return f"{v:,.0f}"


def bar_height(v, all_items):
    vals = [abs(i["pct_day"]) for i in all_items if i["pct_day"] is not None]
    max_val = max(vals) if vals else 1
    if v is None:
        return 4
    h = max(4, int(abs(v) / max_val * 140)) if max_val else 4
    return h


def _env():
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=False)
    env.filters["pct_span"] = pct_span
    env.globals.update(
        fmt_price=fmt_price,
        fmt_big=fmt_big,
        fmt_usd_billions=fmt_usd_billions,
        fmt_usd_billions_plain=fmt_usd_billions_plain,
        fmt_gdp_scaled=fmt_gdp_scaled,
        fmt_population=fmt_population,
        fmt_usd_plain=fmt_usd_plain,
        fmt_int_commas=fmt_int_commas,
        pct_plain=pct_plain,
        level_pct=level_pct,
        fmt_fx=fmt_fx,
        pct_span=lambda v: _markup(pct_span(v)),
        pct_span_compact=lambda v: _markup(pct_span_compact(v)),
        arrow=arrow,
        bar_height=bar_height,
    )
    return env


def _markup(html_str):
    from markupsafe import Markup
    return Markup(html_str)


def render_html(data, template_name):
    env = _env()
    tpl = env.get_template(template_name)
    assets_uri = "file:///" + ASSETS_DIR.replace("\\", "/")
    templates_uri = "file:///" + TEMPLATES_DIR.replace("\\", "/")
    return tpl.render(
        assets=assets_uri,
        templates=templates_uri,
        time_label="11:30",
        **data,
    )


PAGE_WIDTH_PX = 2000
PAGE_HEIGHT_PX = 3086
DEVICE_SCALE = 2
VIEWPORT = {"width": PAGE_WIDTH_PX // DEVICE_SCALE, "height": PAGE_HEIGHT_PX // DEVICE_SCALE}

# Paginas 1 y 2 fueron creciendo mas alla del presupuesto estandar de
# VIEWPORT a medida que se les agregaron paises -- por pedido explicito del
# usuario (2026-10-30, originalmente sobre pagina 2) no se achica la letra
# para que quepa; en su lugar cada pagina usa el lienzo mas alto que
# necesite. El ancho y el resto del layout (header, tablas, footer) son
# identicos entre paginas, solo cambia cuanto alto captura el screenshot.
PAGE1_HEIGHT_PX = 3820
PAGE1_VIEWPORT = {"width": PAGE_WIDTH_PX // DEVICE_SCALE, "height": PAGE1_HEIGHT_PX // DEVICE_SCALE}
PAGE2_HEIGHT_PX = 3220
PAGE2_VIEWPORT = {"width": PAGE_WIDTH_PX // DEVICE_SCALE, "height": PAGE2_HEIGHT_PX // DEVICE_SCALE}

_VIEWPORT_BY_TEMPLATE = {"page1.html": PAGE1_VIEWPORT, "page2.html": PAGE2_VIEWPORT}


def render_bulletin(data, out_dir, pages=("page1.html", "page2.html")):
    """Render each page at a fixed pixel output, every time, so the images
    sent to Telegram are consistent regardless of content length (shorter
    content leaves white space at the bottom; content taller than the
    viewport is cropped rather than resized). Page 2 uses a taller canvas
    than the rest (see PAGE2_VIEWPORT) since it keeps growing with more
    countries and the font isn't meant to shrink to compensate.
    """
    os.makedirs(out_dir, exist_ok=True)

    tmp_paths = []
    for i, template_name in enumerate(pages, start=1):
        html_str = render_html(data, template_name)
        tmp_path = os.path.abspath(os.path.join(out_dir, f"_tmp_page{i}.html"))
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(html_str)
        tmp_paths.append((tmp_path, template_name))

    out_paths = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for i, (tmp_path, template_name) in enumerate(tmp_paths, start=1):
                viewport = _VIEWPORT_BY_TEMPLATE.get(template_name, VIEWPORT)
                bpage = browser.new_page(viewport=viewport, device_scale_factor=DEVICE_SCALE)
                bpage.goto("file:///" + tmp_path.replace("\\", "/"))
                bpage.evaluate(f"document.querySelector('.page').style.minHeight = '{viewport['height']}px'")
                bpage.wait_for_timeout(400)
                out_path = os.path.join(out_dir, f"page{i}.png")
                bpage.screenshot(path=out_path)
                out_paths.append(out_path)
                bpage.close()
            browser.close()
    finally:
        for tmp_path, _ in tmp_paths:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    return out_paths


def render_pdf(data, out_dir, template_name="pdf.html", filename="boletin.pdf"):
    """Single multi-page PDF (vector text, not a rasterized screenshot) --
    sent alongside the images so recipients have a print-quality copy too.
    Each page break is forced by the .pdf-sheet CSS rule in pdf.html rather
    than relying on content height matching the page size exactly. Uses the
    tallest per-template viewport height uniformly for every page since
    Playwright's page.pdf() sets one page size per document -- a shorter page
    ends up with a bit of blank space at the bottom, same as it would if it
    were simply shorter content on a fixed-size page (already normal
    elsewhere in this bulletin)."""
    os.makedirs(out_dir, exist_ok=True)
    html_str = render_html(data, template_name)
    tmp_path = os.path.abspath(os.path.join(out_dir, "_tmp_pdf.html"))
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(html_str)

    pdf_height = max(v["height"] for v in _VIEWPORT_BY_TEMPLATE.values())
    out_path = os.path.join(out_dir, filename)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            bpage = browser.new_page(viewport={"width": VIEWPORT["width"], "height": pdf_height})
            bpage.goto("file:///" + tmp_path.replace("\\", "/"))
            bpage.wait_for_timeout(400)
            bpage.pdf(
                path=out_path,
                width=f"{VIEWPORT['width']}px",
                height=f"{pdf_height}px",
                print_background=True,
                margin={"top": "0px", "bottom": "0px", "left": "0px", "right": "0px"},
            )
            browser.close()
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return out_path
