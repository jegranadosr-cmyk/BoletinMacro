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


def render_bulletin(data, out_dir, pages=("page1.html", "page2.html")):
    """Render each page at a fixed 2000x3086px output, every time, so the
    images sent to Telegram are all the same size regardless of content
    length (shorter content leaves white space at the bottom; content taller
    than the viewport is cropped rather than resized).
    """
    os.makedirs(out_dir, exist_ok=True)

    tmp_paths = []
    for i, template_name in enumerate(pages, start=1):
        html_str = render_html(data, template_name)
        tmp_path = os.path.abspath(os.path.join(out_dir, f"_tmp_page{i}.html"))
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(html_str)
        tmp_paths.append(tmp_path)

    out_paths = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for i, tmp_path in enumerate(tmp_paths, start=1):
                bpage = browser.new_page(viewport=VIEWPORT, device_scale_factor=DEVICE_SCALE)
                bpage.goto("file:///" + tmp_path.replace("\\", "/"))
                bpage.evaluate(f"document.querySelector('.page').style.minHeight = '{VIEWPORT['height']}px'")
                bpage.wait_for_timeout(400)
                out_path = os.path.join(out_dir, f"page{i}.png")
                bpage.screenshot(path=out_path)
                out_paths.append(out_path)
                bpage.close()
            browser.close()
    finally:
        for tmp_path in tmp_paths:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    return out_paths
