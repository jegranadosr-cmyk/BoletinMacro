import datetime
import json
import os
import sys
import traceback

import fetch_countryeconomy as fce
import fetch_eurostat as feu
import fetch_rates as fr
import fetch_debt_bonds as fdb
import fetch_market as fmkt
import fetch_worldbank as fwb
import fetch_news as fnews
import resumen as rs
import render as rd
import send_telegram as st

MESES_ES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
            "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def build_data():
    today = datetime.date.today()
    errors = []
    data = {"fecha": today}

    # PIB / inflacion / desempleo / balanza comercial: Colombia, EE.UU., China, Japon
    r, err = safe(fce.fetch_macro_indicators)
    macro_indicadores = r if not err else []
    if err:
        errors.append(f"CountryEconomyMacro: {err}")

    # Eurozona (agregado, via Eurostat)
    r, err = safe(feu.fetch_macro_indicators)
    if err:
        errors.append(f"EurostatMacro: {err}")
        r = {"pais": "Eurozona", "pib_crecimiento": None, "inflacion": None,
             "desempleo": None, "balanza_comercial_pib": None, "deficit_fiscal_pib": None}
    # Insert Eurozona after Colombia and EE.UU., before China/Japon
    macro_indicadores = macro_indicadores[:2] + [r] + macro_indicadores[2:]

    # Balanza de pagos: cuenta corriente, cuenta de capital, reservas internacionales (World Bank)
    r, err = safe(fwb.fetch_balance_of_payments)
    bop_by_country = {d["pais"]: d for d in r} if not err else {}
    if err:
        errors.append(f"WorldBank: {err}")
    for d in macro_indicadores:
        bop = bop_by_country.get(d["pais"], {})
        d["cuenta_corriente_pib"] = bop.get("cuenta_corriente_pib")
        d["cuenta_capital_usd"] = bop.get("cuenta_capital_usd")
        d["reservas_internacionales_usd"] = bop.get("reservas_internacionales_usd")

    data["macro_indicadores"] = macro_indicadores

    # Tasas de politica monetaria (bancos centrales)
    r, err = safe(fr.fetch_policy_rates)
    data["tasas_bancos_centrales"] = r if not err else []
    if err:
        errors.append(f"TasasBC: {err}")

    # Deuda/PIB y bono a 10 anos: Francia, EE.UU., China, Japon, Colombia
    r, err = safe(fdb.fetch_debt_and_bonds)
    data["deuda_bonos"] = r if not err else []
    if err:
        errors.append(f"DeudaBonos: {err}")

    # Resumen coyuntural: una fila por pais con tasa de politica monetaria,
    # deuda/PIB y bono a 10 anos. Francia usa la tasa del BCE (Eurozona).
    rate_by_country = {t["pais"]: t for t in data["tasas_bancos_centrales"]}
    RATE_LOOKUP = {
        "Francia": "Eurozona", "EE.UU.": "EE.UU.", "China": "China",
        "Japón": "Japón", "Colombia": "Colombia",
    }
    resumen_coyuntural = []
    for d in data["deuda_bonos"]:
        rate = rate_by_country.get(RATE_LOOKUP.get(d["pais"]))
        if rate and rate["tasa"] is not None:
            tasa_label = f"{rate['tasa_label']} ({rate['banco']})"
        else:
            tasa_label = "-"
        resumen_coyuntural.append({
            "pais": d["pais"], "tasa_label": tasa_label,
            "deuda_pib": d["deuda_pib"], "bono_10y": d["bono_10y"],
            "riesgo_pais_pb": d.get("riesgo_pais_pb"),
            "rating_moodys": d.get("rating_moodys"),
            "rating_sp": d.get("rating_sp"),
            "rating_fitch": d.get("rating_fitch"),
        })
    data["resumen_coyuntural"] = resumen_coyuntural

    # Mercados clave: dolar (DXY), EUR/USD, USD/COP, oro, petroleo WTI
    r, err = safe(fmkt.fetch_mercados_clave)
    data["mercados_clave"] = r if not err else []
    if err:
        errors.append(f"MercadosClave: {err}")

    # Noticias relevantes de macroeconomia y coyuntura (TradingEconomics)
    r, err = safe(fnews.fetch_relevant_news)
    data["noticias"] = r if not err else []
    if err:
        errors.append(f"Noticias: {err}")

    data["errors"] = errors
    return data


def main():
    data = build_data()

    if data["errors"]:
        print("WARNINGS during fetch:", file=sys.stderr)
        for e in data["errors"]:
            print(" -", e, file=sys.stderr)

    data["bullets"] = rs.generate_bullets(data)

    today = data["fecha"]
    data["fecha_larga"] = f"{DIAS_ES[today.weekday()].capitalize()}, {today.day} de {MESES_ES[today.month]} de {today.year}"

    with open("data_dump.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    print("Data built OK. Dumped to data_dump.json")
    return data


def run(send=True):
    data = main()

    pages = rd.render_bulletin(data, "render_out")
    print(f"Rendered: {', '.join(pages)}")

    if send:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set, skipping send.", file=sys.stderr)
            return data
        result = st.send_media_group(token, chat_id, pages)
        print(json.dumps(result, indent=2))
        if not result.get("ok"):
            raise RuntimeError(f"Telegram send failed: {result}")
    return data


if __name__ == "__main__":
    try:
        send_flag = os.environ.get("SKIP_SEND") != "1"
        run(send=send_flag)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
