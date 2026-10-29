"""Generate the 'Resumen ejecutivo' bullet points for the macro bulletin."""


def fmt_pct(v, decimals=2):
    if v is None:
        return "-"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.{decimals}f}%"


def generate_bullets(data):
    bullets = []

    pib_validos = [d for d in data.get("macro_indicadores", []) if d["pib_crecimiento"] is not None]
    if pib_validos:
        top_pib = max(pib_validos, key=lambda d: d["pib_crecimiento"])
        bullets.append(f"{top_pib['pais']} lidera el crecimiento del PIB del grupo, {fmt_pct(top_pib['pib_crecimiento'])} interanual.")
        contraccion = [d for d in pib_validos if d["pib_crecimiento"] < 0]
        if contraccion:
            peor_pib = min(contraccion, key=lambda d: d["pib_crecimiento"])
            bullets.append(f"{peor_pib['pais']} es la única economía del grupo en contracción, {fmt_pct(peor_pib['pib_crecimiento'])} interanual.")

    validos = [d for d in data.get("macro_indicadores", []) if d["inflacion"] is not None]
    if validos:
        top_infl = max(validos, key=lambda d: d["inflacion"])
        bullets.append(f"{top_infl['pais']} registra la mayor inflación interanual del grupo, {fmt_pct(top_infl['inflacion'])}.")

    for t in data.get("tasas_bancos_centrales", []):
        if t["tasa"] is None:
            continue
        label = t.get("tasa_label") or f"{t['tasa']:.2f}%"
        bullets.append(f"Tasa {t['banco']} ({t['pais']}): {label} (desde {t['fecha']}).")

    deuda_validos = [d for d in data.get("deuda_bonos", []) if d["deuda_pib"] is not None]
    if deuda_validos:
        top_deuda = max(deuda_validos, key=lambda d: d["deuda_pib"])
        bullets.append(f"{top_deuda['pais']} tiene la mayor deuda pública del grupo, {fmt_pct(top_deuda['deuda_pib'])} del PIB.")

    bono_validos = [d for d in data.get("deuda_bonos", []) if d["bono_10y"] is not None]
    if bono_validos:
        top_bono = max(bono_validos, key=lambda d: d["bono_10y"])
        bullets.append(f"El bono a 10 años de {top_bono['pais']} rinde {fmt_pct(top_bono['bono_10y'])}, el más alto del grupo.")

    riesgo_validos = [d for d in data.get("deuda_bonos", []) if d.get("riesgo_pais_pb") is not None]
    if riesgo_validos:
        top_riesgo = max(riesgo_validos, key=lambda d: d["riesgo_pais_pb"])
        bullets.append(f"{top_riesgo['pais']} tiene el mayor riesgo país del grupo, {top_riesgo['riesgo_pais_pb']:.0f} puntos básicos (S&P: {top_riesgo.get('rating_sp') or '-'}).")

    balanza_validos = [d for d in data.get("macro_indicadores", []) if d["balanza_comercial_pib"] is not None]
    if balanza_validos:
        top_superavit = max(balanza_validos, key=lambda d: d["balanza_comercial_pib"])
        if top_superavit["balanza_comercial_pib"] > 0:
            bullets.append(f"{top_superavit['pais']} muestra el mayor superávit comercial, {fmt_pct(top_superavit['balanza_comercial_pib'])} del PIB.")
        top_deficit = min(balanza_validos, key=lambda d: d["balanza_comercial_pib"])
        if top_deficit["balanza_comercial_pib"] < 0:
            bullets.append(f"{top_deficit['pais']} presenta el mayor déficit comercial, {fmt_pct(top_deficit['balanza_comercial_pib'])} del PIB.")

    desempleo_validos = [d for d in data.get("macro_indicadores", []) if d["desempleo"] is not None]
    if desempleo_validos:
        top_desempleo = max(desempleo_validos, key=lambda d: d["desempleo"])
        bullets.append(f"{top_desempleo['pais']} tiene la mayor tasa de desempleo del grupo, {fmt_pct(top_desempleo['desempleo'])}.")

    deficit_validos = [d for d in data.get("macro_indicadores", []) if d["deficit_fiscal_pib"] is not None]
    if deficit_validos:
        peor_deficit = min(deficit_validos, key=lambda d: d["deficit_fiscal_pib"])
        bullets.append(f"{peor_deficit['pais']} tiene el mayor déficit fiscal del grupo, {fmt_pct(peor_deficit['deficit_fiscal_pib'])} del PIB.")

    dxy = next((m for m in data.get("mercados_clave", []) if m["nombre"].startswith("DXY")), None)
    if dxy and dxy["pct_month"] is not None:
        verbo = "se fortalece" if dxy["pct_month"] >= 0 else "se debilita"
        bullets.append(f"El dólar (DXY) {verbo} {fmt_pct(abs(dxy['pct_month']))} en el mes.")

    oro = next((m for m in data.get("mercados_clave", []) if m["nombre"].startswith("Oro")), None)
    if oro and oro["pct_month"] is not None:
        verbo = "sube" if oro["pct_month"] >= 0 else "cae"
        bullets.append(f"El oro {verbo} {fmt_pct(abs(oro['pct_month']))} en el mes, ${oro['price']:,.0f}/oz.")

    petroleo = next((m for m in data.get("mercados_clave", []) if "WTI" in m["nombre"]), None)
    if petroleo and petroleo["pct_month"] is not None:
        verbo = "sube" if petroleo["pct_month"] >= 0 else "cae"
        bullets.append(f"El petróleo WTI {verbo} {fmt_pct(abs(petroleo['pct_month']))} en el mes, ${petroleo['price']:,.2f}/barril.")

    usdcop = next((m for m in data.get("mercados_clave", []) if m["nombre"] == "USD/COP"), None)
    if usdcop and usdcop["pct_month"] is not None:
        verbo = "se devalúa" if usdcop["pct_month"] >= 0 else "se revalúa"
        bullets.append(f"El peso colombiano {verbo} {fmt_pct(abs(usdcop['pct_month']))} en el mes frente al dólar (${usdcop['price']:,.0f} COP).")

    return bullets
