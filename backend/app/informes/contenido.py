"""Arma el contenido del informe (secciones, números, gráficos) que comparten el PDF y el PPTX."""
from datetime import date

from . import graficos_svg as g
from .periodos import nombre_informe
from .textos import CLAVES, n, pct

CRITS = ["Baja", "Media", "Alta", "Crítica"]
NOMBRE_SERVICIO = {"SOC": "Monitoreo de eventos de seguridad 7x24 (SOC)", "NOC": "Monitoreo de infraestructura 7x24 (NOC)"}


def armar(informe, metricas: dict, svg: bool = False) -> dict:
    """Devuelve el contexto del informe. Las secciones sin datos se omiten."""
    cl = informe.cliente
    an = informe.anexos or {}
    tx = {k: (informe.textos or {}).get(k, "") for k in CLAVES}
    servicios = metricas["servicios"]
    periodo_actual = metricas["periodos"][-1]
    cortas = [p["corta"] for p in metricas["periodos"]]

    secciones = []          # [(numero, titulo, [subtitulos])]
    def sec(titulo, subs=()):
        secciones.append((str(len(secciones) + 1), titulo, list(subs)))
        return str(len(secciones))

    num = {"resumen": sec("Resumen ejecutivo")}
    serv = {}
    for s, d in servicios.items():
        actual = d["periodos"][-1]
        num[s] = sec(f"Gestión de eventos de {s} por criticidad",
                     ["Alertas del periodo"] + (["Categorías MITRE ATT&CK"] if s == "SOC" else []))
        serv[s] = {
            "d": d, "actual": actual, "nombre": NOMBRE_SERVICIO[s],
            "svg_criticidad": g.columnas(cortas, [(c, g.COLOR_CRIT[c], [p["criticidad"][c] for p in d["periodos"]]) for c in CRITS],
                                         ancho=470, alto=250) if svg else None,
            "svg_alertas": g.barras_h([(x["alerta"], x["total"]) for x in d["top_alertas"]], ancho=900, etiqueta_max=80) if svg else None,
            "retro_pct": pct(actual["con_retro"], actual["total"]),
            "sla_pct": pct(actual["dentro_sla"], actual["con_tiempo"]) if actual["con_tiempo"] else None,
        }

    fuentes = an.get("fuentes")
    eps_hist = an.get("eps_historico") or []
    subs_estado = (["Fuentes integradas"] if fuentes or informe.fuentes_integradas else []) + \
                  (["Promedio de EPS"] if informe.eps_promedio or eps_hist else [])
    if subs_estado:
        num["estado"] = sec("Estado del servicio", subs_estado)

    interes = []
    if an.get("paises_entrantes"):
        interes.append("Eventos de países diferentes a Colombia entrantes permitidos")
    if an.get("paises_salientes"):
        interes.append("Eventos de países diferentes a Colombia salientes permitidos")
    puertos = an.get("puertos") or {}
    if puertos.get("entrantes") or puertos.get("salientes"):
        interes.append("Puertos no comunes con conexión aceptada entrantes/salientes permitidos")
    ips = an.get("ips") or {}
    if ips.get("bloqueados"):
        interes.append("Top de ataques detectados por IPS bloqueados")
    if interes:
        num["interes"] = sec("Eventos de interés", interes)
    if informe.boletines:
        num["boletines"] = sec("Boletines de inteligencia de amenazas")
    num["recomendaciones"] = sec("Recomendaciones y conclusiones")

    # EPS: histórico cargado + valor del periodo
    eps_series = [(x["periodo"], x["valor"]) for x in eps_hist][-3:]
    if informe.eps_promedio and (not eps_series or abs(eps_series[-1][1] - informe.eps_promedio) > 0.01):
        eps_series = (eps_series + [(nombre_informe(informe.periodo_inicio).split()[0], informe.eps_promedio)])[-3:]

    total_eventos = sum(sv["actual"]["total"] for sv in serv.values())
    kpis = [("Eventos reportados", n(total_eventos), " + ".join(f"{n(sv['actual']['total'])} {s}" for s, sv in serv.items()) if len(serv) > 1 else "")]
    if informe.eps_promedio:
        kpis.append(("Promedio de EPS", f"{informe.eps_promedio:,.0f}".replace(",", "."),
                     f"de {n(cl.eps_contratados)} contratados" if cl.eps_contratados else "eventos por segundo"))
    total_fuentes = informe.fuentes_integradas or (fuentes or {}).get("total")
    if total_fuentes:
        kpis.append(("Fuentes integradas", n(total_fuentes), "en FortiSIEM"))
    if informe.boletines_enviados is not None or informe.boletines:
        kpis.append(("Boletines enviados", n(informe.boletines_enviados if informe.boletines_enviados is not None else len(informe.boletines)), "de inteligencia de amenazas"))
    soc = serv.get("SOC") or next(iter(serv.values()), None)
    if soc and soc["actual"]["total"]:
        kpis.append(("Con retroalimentación", soc["retro_pct"], "de los eventos escalados"))

    return {
        "cliente": cl, "nombre_cliente": f"{cl.codigo} - {cl.nombre}", "informe": informe,
        "titulo_mes": nombre_informe(informe.periodo_inicio),
        "periodo": periodo_actual["etiqueta"], "periodos": metricas["periodos"], "cortas": cortas,
        "servicios_txt": " y ".join(servicios.keys()) or "SOC",
        "secciones": secciones, "num": num, "serv": serv, "t": tx, "kpis": kpis,
        "fuentes": fuentes, "total_fuentes": total_fuentes,
        "svg_fuentes": g.barras_h([(x["tipo"], x["total"]) for x in fuentes["por_tipo"][:8]], ancho=460)
        if svg and fuentes and fuentes.get("por_tipo") else None,
        "eps_series": eps_series,
        "svg_eps": g.columnas([p for p, _ in eps_series], [("EPS", g.SERIE, [v for _, v in eps_series])], ancho=420, alto=220,
                              leyenda=False) if svg and eps_series else None,
        "paises_entrantes": (an.get("paises_entrantes") or [])[:15],
        "paises_salientes": (an.get("paises_salientes") or [])[:15],
        "svg_pe": g.barras_h([(x["pais"], x["total"]) for x in (an.get("paises_entrantes") or [])[:15]], ancho=440, alto_barra=12, sep=8) if svg else None,
        "svg_ps": g.barras_h([(x["pais"], x["total"]) for x in (an.get("paises_salientes") or [])[:15]], ancho=440, alto_barra=12, sep=8) if svg else None,
        "puertos_ent": (puertos.get("entrantes") or [])[:10], "puertos_sal": (puertos.get("salientes") or [])[:10],
        "ips": (ips.get("bloqueados") or [])[:10],
        "svg_ips": g.barras_h([(x["ataque"], x["total"]) for x in (ips.get("bloqueados") or [])[:10]], ancho=900, etiqueta_max=80) if svg else None,
        "boletines": informe.boletines or [],
        "recomendaciones": [r.strip(" •-\t") for r in (tx.get("recomendaciones") or "").split("\n") if r.strip()],
        "generado": date.today().strftime("%d/%m/%Y"),
        "n": n, "pct": pct,
    }
