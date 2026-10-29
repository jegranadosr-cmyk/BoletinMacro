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
        pct_plain=pct_plain,
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


def html_to_png(html_str, out_path):
    tmp_html = os.path.abspath(out_path.replace(".png", ".tmp.html"))
    with open(tmp_html, "w", encoding="utf-8") as f:
        f.write(html_str)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1000, "height": 400}, device_scale_factor=2)
        page.goto("file:///" + tmp_html.replace("\\", "/"))
        page.wait_for_timeout(400)
        page.screenshot(path=out_path, full_page=True)
        browser.close()
    os.remove(tmp_html)


def render_bulletin(data, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    page1_html = render_html(data, "page1.html")
    page2_html = render_html(data, "page2.html")
    p1_path = os.path.join(out_dir, "page1.png")
    p2_path = os.path.join(out_dir, "page2.png")
    html_to_png(page1_html, p1_path)
    html_to_png(page2_html, p2_path)
    return p1_path, p2_path
