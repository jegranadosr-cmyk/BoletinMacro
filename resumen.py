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

    return bullets
