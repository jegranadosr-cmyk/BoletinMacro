import datetime
import json
import os
import sys
import traceback

import fetch_countryeconomy as fce
import fetch_eurostat as feu
import fetch_growth as fg
import fetch_rates as fr
import fetch_debt_bonds as fdb
import fetch_worldbank as fwb
import fetch_demographics as fdem
import fetch_reserves as fres
import render as rd
import send_telegram as st

MESES_ES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
            "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

# Canonical region order used across every table in the bulletin (same order,
# every table -- a 2026-10-29 review flagged that the country order used to
# vary from one table to the next).
REGIONES = [
    "Colombia", "EE.UU.", "Reino Unido", "Francia", "Alemania", "Italia", "España",
    "India", "Corea del Sur", "China", "Japón", "Vietnam",
]
# Las 12 regiones son paises soberanos (ya no incluye el agregado Eurozona).
REGIONES_SOBERANOS = REGIONES


def safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def build_data():
    today = datetime.date.today()
    errors = []
    data = {"fecha": today}

    # Crecimiento del PIB a 1/5/20 anos (CAGR, Banco Mundial) para las 12 regiones
    r, err = safe(fg.fetch_growth_horizons)
    growth_by_country = {d["pais"]: d for d in r} if not err else {}
    if err:
        errors.append(f"Growth: {err}")

    # Inflacion / desempleo / balanza comercial / deficit fiscal: las 12 regiones
    r, err = safe(fce.fetch_macro_indicators)
    macro_by_country = {d["pais"]: d for d in r} if not err else {}
    if err:
        errors.append(f"CountryEconomyMacro: {err}")

    # Los paises de la Eurozona (Francia, Alemania, Italia, España) usan HICP
    # (Eurostat) en vez del IPC nacional de countryeconomy.com, para ser
    # comparables entre si -- el IPC nacional puede diferir varios puntos del
    # HICP armonizado.
    for pais in feu.EUROZONE_COUNTRY_GEOS:
        hicp = feu.fetch_hicp_country(pais)
        if hicp is not None:
            macro_by_country.setdefault(pais, {})["inflacion"] = hicp
        else:
            errors.append(f"HICP {pais}: sin dato, se mantiene el IPC nacional")

    # Balanza de pagos: cuenta corriente, cuenta de capital, reservas internacionales (World Bank)
    r, err = safe(fwb.fetch_balance_of_payments)
    bop_by_country = {d["pais"]: d for d in r} if not err else {}
    if err:
        errors.append(f"WorldBank: {err}")

    macro_indicadores = []
    for pais in REGIONES:
        growth = growth_by_country.get(pais, {})
        macro = macro_by_country.get(pais, {})
        bop = bop_by_country.get(pais, {})
        macro_indicadores.append({
            "pais": pais,
            "pib_1a": growth.get("pib_1a"),
            "pib_5a": growth.get("pib_5a"),
            "pib_anio": growth.get("anio"),
            "inflacion": macro.get("inflacion"),
            "desempleo": macro.get("desempleo"),
            "balanza_comercial_pib": macro.get("balanza_comercial_pib"),
            "deficit_fiscal_pib": macro.get("deficit_fiscal_pib"),
            "cuenta_corriente_pib": bop.get("cuenta_corriente_pib"),
            "cuenta_capital_usd": bop.get("cuenta_capital_usd"),
            "reservas_internacionales_usd": bop.get("reservas_internacionales_usd"),
        })
    data["macro_indicadores"] = macro_indicadores

    # Tasas de politica monetaria (bancos centrales)
    r, err = safe(fr.fetch_policy_rates)
    data["tasas_bancos_centrales"] = r if not err else []
    if err:
        errors.append(f"TasasBC: {err}")

    # Deuda/PIB, bono a 10 anos y rating: todos los REGIONES_SOBERANOS (12)
    r, err = safe(fdb.fetch_debt_and_bonds)
    deuda_by_country = {d["pais"]: d for d in r} if not err else {}
    if err:
        errors.append(f"DeudaBonos: {err}")

    # Tasa de politica monetaria + tasa real ex-post (tasa - inflacion del mismo
    # pais) para las 12 regiones. Francia/Alemania/Italia/Espana usan la tasa
    # del BCE (todas comparten la Eurozona en este boletin).
    rate_by_country = {t["pais"]: t for t in data["tasas_bancos_centrales"]}
    inflacion_by_country = {d["pais"]: d.get("inflacion") for d in macro_indicadores}
    RATE_LOOKUP = {
        "Francia": "Eurozona", "Alemania": "Eurozona", "Italia": "Eurozona", "España": "Eurozona",
        "EE.UU.": "EE.UU.", "China": "China", "Japón": "Japón", "Colombia": "Colombia",
        "India": "India", "Corea del Sur": "Corea del Sur",
        "Reino Unido": "Reino Unido", "Vietnam": "Vietnam",
    }
    tasas_por_region = {}
    for pais in REGIONES:
        rate = rate_by_country.get(RATE_LOOKUP.get(pais))
        if rate and rate["tasa"] is not None:
            tasa_label = f"{rate['tasa_label']} ({rate['banco']})"
        else:
            tasa_label = "-"
        inflacion_pais = inflacion_by_country.get(pais)
        # Tasa real ex-post = tasa de politica - inflacion interanual del mismo pais
        # (para Eurozona usa la inflacion HICP de cada pais, no la tasa BCE restada
        # de una inflacion distinta -- asi la tasa real sigue siendo comparable).
        tasa_real = (rate["tasa"] - inflacion_pais) if (rate and rate["tasa"] is not None and inflacion_pais is not None) else None
        tasas_por_region[pais] = {"tasa_label": tasa_label, "tasa_real": tasa_real}
    data["resumen_coyuntural_by_pais"] = tasas_por_region

    # Resumen coyuntural: una fila por pais soberano (sin Eurozona, no es un
    # emisor soberano) con deuda/PIB, bono a 10 anos y rating. Mismo orden
    # (REGIONES_SOBERANOS) que las demas tablas.
    resumen_coyuntural = []
    for pais in REGIONES_SOBERANOS:
        d = deuda_by_country.get(pais, {})
        resumen_coyuntural.append({
            "pais": pais, **tasas_por_region[pais],
            "deuda_pib": d.get("deuda_pib"), "bono_10y": d.get("bono_10y"),
            "rating_moodys": d.get("rating_moodys"),
            "rating_sp": d.get("rating_sp"),
            "rating_fitch": d.get("rating_fitch"),
        })
    data["resumen_coyuntural"] = resumen_coyuntural

    # Pagina 2 (independiente): poblacion, PIB nominal/PPA, PIB per capita,
    # area y reservas de petroleo/gas. Roster propio (BASE_ROSTER abajo),
    # independiente de REGIONES/pagina 1 -- a proposito: un pais puede
    # quitarse de una pagina sin afectar a la otra (pedido explicito del
    # usuario 2026-10-30 al quitar Iran/Irak solo de pagina 1).
    r, err = safe(fdem.fetch_demographics)
    demografia_by_pais = {d["pais"]: d for d in r} if not err else {}
    if err:
        errors.append(f"Demografia: {err}")

    r, err = safe(fres.fetch_reserves)
    data["reservas_by_pais"] = {d["pais"]: d for d in r} if not err else {}
    if err:
        errors.append(f"Reservas: {err}")

    # Roster base (17 paises) para ambas tablas de pagina 2.
    BASE_ROSTER = [
        "Colombia", "EE.UU.", "Iran", "Iraq", "Alemania", "India", "Corea del Sur",
        "China", "Japón", "Brasil", "Rusia", "Arabia Saudita", "Qatar", "Indonesia",
        "Canadá", "Australia", "Kuwait",
    ]

    # Tabla "Poblacion, PIB...": el roster base + EAU + Kazajistan (sin
    # quitar a Japon ni a Alemania), orden por poblacion desc (pedido
    # explicito del usuario).
    POBLACION_ROSTER = BASE_ROSTER + ["EAU", "Kazajistán"]
    data["demografia_poblacion"] = sorted(
        (demografia_by_pais[p] for p in POBLACION_ROSTER if p in demografia_by_pais),
        key=lambda d: (d["poblacion"] is None, -(d["poblacion"] or 0)),
    )

    # Tabla "Territorio y reservas": el roster base, pero Corea del Sur
    # reemplazada por Venezuela, Japon reemplazado por EAU y Alemania
    # reemplazada por Kazajistan (pedido explicito del usuario), orden por
    # area desc.
    AREA_SUB = {"Corea del Sur": "Venezuela", "Japón": "EAU", "Alemania": "Kazajistán"}
    AREA_ROSTER = [AREA_SUB.get(p, p) for p in BASE_ROSTER]
    data["demografia_area"] = sorted(
        (demografia_by_pais[p] for p in AREA_ROSTER if p in demografia_by_pais),
        key=lambda d: (d["area_km2"] is None, -(d["area_km2"] or 0)),
    )

    data["errors"] = errors
    return data


def main():
    data = build_data()

    if data["errors"]:
        print("WARNINGS during fetch:", file=sys.stderr)
        for e in data["errors"]:
            print(" -", e, file=sys.stderr)

    today = data["fecha"]
    data["fecha_larga"] = f"{DIAS_ES[today.weekday()].capitalize()}, {today.day} de {MESES_ES[today.month]} de {today.year}"

    # Bogota is UTC-5 year-round (no DST) -- avoids pulling in a tz database dependency.
    bogota_now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)
    data["hora_corte"] = f"{bogota_now.strftime('%H:%M')} COT"

    anios_pib = [d["pib_anio"] for d in data.get("macro_indicadores", []) if d.get("pib_anio")]
    data["pib_anio_ref"] = max(anios_pib) if anios_pib else "n/d"

    with open("data_dump.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    print("Data built OK. Dumped to data_dump.json")
    return data


def run(send=True):
    data = main()

    pages = rd.render_bulletin(data, "render_out")
    pdf_path = rd.render_pdf(data, "render_out")
    print(f"Rendered: {', '.join(pages)}, {pdf_path}")

    if send:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set, skipping send.", file=sys.stderr)
            return data
        result = st.send_bulletin(token, chat_id, pages)
        print(json.dumps(result, indent=2))
        if not result.get("ok"):
            raise RuntimeError(f"Telegram send failed: {result}")

        # PDF por separado (sendDocument) -- preserva texto vectorial en vez
        # de las imagenes rasterizadas, para quien quiera guardar/imprimir.
        pdf_result = st.send_document(token, chat_id, pdf_path)
        print(json.dumps(pdf_result, indent=2))
        if not pdf_result.get("ok"):
            raise RuntimeError(f"Telegram PDF send failed: {pdf_result}")
    return data


if __name__ == "__main__":
    try:
        send_flag = os.environ.get("SKIP_SEND") != "1"
        run(send=send_flag)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
