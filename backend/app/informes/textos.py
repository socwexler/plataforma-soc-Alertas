"""Redacción automática de los textos del informe a partir de los datos.

Los textos quedan como borrador editable: el analista los ajusta antes de generar el PDF/PPTX.
"""

CLAVES = {
    "objetivo": "Objetivo",
    "alcance": "Alcance",
    "resumen_SOC": "SOC · Resumen del trimestre",
    "retro_SOC": "SOC · Retroalimentación",
    "alertas_SOC": "SOC · Alertas del periodo",
    "categorias_SOC": "SOC · Categorías MITRE",
    "tiempos_SOC": "SOC · Tiempos de notificación",
    "resumen_NOC": "NOC · Resumen del trimestre",
    "retro_NOC": "NOC · Retroalimentación",
    "alertas_NOC": "NOC · Alertas del periodo",
    "tiempos_NOC": "NOC · Tiempos de notificación",
    "fuentes": "Fuentes integradas",
    "eps": "Promedio de EPS",
    "paises_entrantes": "Países entrantes",
    "paises_salientes": "Países salientes",
    "puertos": "Puertos no comunes",
    "ips": "Ataques IPS",
    "recomendaciones": "Recomendaciones (una por línea)",
    "conclusiones": "Conclusiones",
}

RECOMENDACIONES_BASE = [
    "Validar si los países involucrados en el tráfico entrante y saliente, especialmente aquellos con alta cantidad de "
    "eventos, están alineados con las políticas de la organización. Si no se requiere conectividad con dichos países "
    "para el funcionamiento normal de la entidad, se sugiere bloquearlos como medida preventiva.",
    "Verificar las aplicaciones o servicios asociados a los puertos entrantes y salientes permitidos. Si alguno de "
    "estos puertos no está asociado a un uso autorizado, debe bloquearse a nivel de firewall.",
    "Mantener el bloqueo de los ataques identificados por el sistema de prevención de intrusos (IPS) y conservar "
    "actualizados los dispositivos de seguridad perimetral con las últimas firmas y definiciones.",
    "Enviar retroalimentación de los eventos reportados para identificar comportamientos, eventos controlados o "
    "lecciones aprendidas que permitan la mejora continua de la herramienta y del servicio SIEM.",
    "Revisar constantemente los boletines de seguridad sobre amenazas y vulnerabilidades que puedan afectar a la "
    "organización, bloqueando los indicadores de compromiso (IOC) en los dispositivos de seguridad.",
    "Mantener la capacitación y concientización continua de los colaboradores en seguridad de la información.",
]


def n(x) -> str:
    return f"{int(round(x or 0)):,}".replace(",", ".")


def pct(a, b) -> str:
    if not b:
        return "0 %"
    v = f"{a / b * 100:.1f}".replace(".", ",")
    return (v[:-2] if v.endswith(",0") else v) + " %"


def lista(items: list[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " y " + items[-1]


def _variacion(antes: int, ahora: int) -> str:
    if not antes:
        return ""
    v = (ahora - antes) / antes * 100
    if abs(v) < 3:
        return "se mantuvo estable frente al periodo anterior"
    return f"{'aumentó' if v > 0 else 'disminuyó'} un {abs(v):.0f} % frente al periodo anterior"


def _crit_desc(crit: dict) -> str:
    activos = [(c, v) for c, v in crit.items() if v]
    if not activos:
        return ""
    if len(activos) == 1:
        return f", todos de criticidad {activos[0][0].lower()}"
    return ": " + lista([f"{n(v)} de criticidad {c.lower()}" for c, v in activos])


def _servicio(s: str, d: dict, sla: int) -> dict:
    P = d["periodos"]
    a, b, c = (p["total"] for p in P)
    act = P[-1]
    t = {}
    tot = a + b + c
    var = _variacion(b, c)
    frase = f"Durante el trimestre evaluado, desde el {s} se gestionaron {n(tot)} eventos, pasando de {n(a)} registros " \
            f"en el primer periodo a {n(b)} en el segundo y {n(c)} en el último."
    if var:
        frase += f" El volumen del último periodo {var}"
        if a:
            frase += f" y {'es mayor' if c > a else 'es menor' if c < a else 'es igual'} al del inicio del trimestre"
        frase += "."
    crit_tri = {k: sum(p["criticidad"][k] for p in P) for k in P[0]["criticidad"]}
    if tot:
        dom = max(crit_tri, key=crit_tri.get)
        frase += f"\n\nEn cuanto a la distribución por criticidad, predominaron los eventos de severidad {dom.lower()}, " \
                 f"con {n(crit_tri[dom])} registros ({pct(crit_tri[dom], tot)} del total trimestral)."
        otros = [f"{n(v)} de criticidad {k.lower()}" for k, v in crit_tri.items() if v and k != dom]
        if otros:
            frase += f" Se registraron además {lista(otros)}."
        if not crit_tri.get("Crítica"):
            frase += " No se presentaron eventos de criticidad crítica."
    t[f"resumen_{s}"] = frase

    t[f"retro_{s}"] = (f"Al momento de realizar el informe, de los {n(c)} eventos escalados en el periodo, "
                       f"{n(act['con_retro'])} obtuvieron retroalimentación del cliente y {n(act['sin_retro'])} no la "
                       f"obtuvieron.") if c else "No se escalaron eventos durante el periodo."

    top = d["top_alertas"]
    if top:
        txt = f"Durante el periodo analizado se escalaron {n(c)} eventos{_crit_desc(act['criticidad'])}. " \
              f"Las alertas más recurrentes correspondieron a " + lista([f"{x['alerta']} ({n(x['total'])})" for x in top[:3]]) + "."
        if len(top) > 3:
            txt += " Les siguieron " + lista([f"{x['alerta']} ({n(x['total'])})" for x in top[3:6]]) + "."
        k = len(d["destacados"])
        if k == 1:
            txt += "\n\nSe reportó 1 evento de criticidad alta o crítica, que se detalla en la sección de eventos " \
                   "destacados y requiere especial atención."
        elif k:
            txt += f"\n\nSe reportaron {n(k)} eventos de criticidad alta o crítica, que se detallan en la sección de " \
                   f"eventos destacados y requieren especial atención."
        t[f"alertas_{s}"] = txt
    else:
        t[f"alertas_{s}"] = "No se escalaron eventos durante el periodo."

    if s == "SOC":
        tacs = [x for x in d["tacticas"] if x["tactica"] != "Sin táctica" and x["valores"][-1]]
        if tacs and c:
            top3 = tacs[:3]
            suma = sum(x["valores"][-1] for x in top3)
            txt = "Durante el periodo, las categorías (tácticas MITRE ATT&CK) con mayor número de eventos fueron " + \
                  lista([f"{x['tactica']} ({n(x['valores'][-1])})" for x in top3]) + \
                  f", que concentran el {pct(suma, c)} de los eventos escalados."
            suben = [x for x in d["tacticas"] if x["valores"][0] and x["valores"][-1] > x["valores"][0] * 1.2]
            bajan = [x for x in d["tacticas"] if x["valores"][0] and x["valores"][-1] < x["valores"][0] * 0.8]
            partes = []
            if suben:
                partes.append("aumentaron " + lista([f"{x['tactica']} (de {n(x['valores'][0])} a {n(x['valores'][-1])})" for x in suben[:3]]))
            if bajan:
                partes.append("disminuyeron " + lista([f"{x['tactica']} (de {n(x['valores'][0])} a {n(x['valores'][-1])})" for x in bajan[:3]]))
            if partes:
                txt += "\n\nFrente al inicio del trimestre " + "; y ".join(partes) + "."
            t["categorias_SOC"] = txt
        else:
            t["categorias_SOC"] = "No hay categorías para reportar en el periodo."

    if act["con_tiempo"]:
        t[f"tiempos_{s}"] = (f"El tiempo mediano entre la detección de la alerta en el SIEM y su notificación al cliente "
                             f"fue de {n(act['mediana_minutos'])} minutos. El {pct(act['dentro_sla'], act['con_tiempo'])} "
                             f"de los eventos se notificó dentro del objetivo de {sla} minutos.")
    return t


def generar(cliente, informe, m: dict) -> dict[str, str]:
    an = informe.anexos or {}
    nombre = f"{cliente.codigo} - {cliente.nombre}"
    t = {
        "objetivo": "Presentar un resumen ejecutivo del estado de la seguridad informática a partir del análisis de las "
                    "alertas generadas por la herramienta de monitoreo, con el fin de apoyar la toma de decisiones "
                    "orientadas a mitigar riesgos y fortalecer la protección de la infraestructura tecnológica.",
        "alcance": f"Se efectuó el monitoreo establecido y definido para {nombre}, acorde con el alcance del contrato "
                   f"celebrado, con el propósito de detectar y tomar acciones oportunas ante incidentes que puedan "
                   f"afectar la información o la infraestructura tecnológica de la entidad.",
    }
    for s, d in m["servicios"].items():
        t.update(_servicio(s, d, m["sla_minutos"]))

    f = an.get("fuentes")
    total_f = informe.fuentes_integradas or (f or {}).get("total")
    if total_f:
        txt = f"Actualmente se tienen {n(total_f)} fuentes integradas en la herramienta FortiSIEM, provenientes de " \
              f"diferentes plataformas, tecnologías y fabricantes."
        if f and f.get("por_tipo"):
            pt = f["por_tipo"]
            txt += f" {pt[0]['tipo']} es el proveedor con mayor cantidad de fuentes integradas ({n(pt[0]['total'])})"
            txt += f", seguido por {pt[1]['tipo']} ({n(pt[1]['total'])})." if len(pt) > 1 else "."
        if f and f.get("envian") is not None:
            txt += f"\n\nDel total de {n(f['total'])} fuentes, {n(f['envian'])} se encuentran en estado Envía Logs y " \
                   f"{n(f['no_envian'])} en estado No Envía Logs."
        elif f and f.get("por_estado"):
            txt += "\n\nSegún su estado en FortiSIEM: " + lista([f"{n(e['total'])} {e['estado']}" for e in f["por_estado"]]) + "."
        t["fuentes"] = txt

    if informe.eps_promedio:
        txt = f"Durante el periodo se utilizó un promedio de {informe.eps_promedio:,.0f} eventos por segundo (EPS)".replace(",", ".")
        if cliente.eps_contratados:
            txt += f", frente a {n(cliente.eps_contratados)} EPS contratados ({pct(informe.eps_promedio, cliente.eps_contratados)} de uso)"
        t["eps"] = txt + ". La gráfica muestra la tendencia de uso de los últimos periodos."

    for clave_, sentido, verbo in (("paises_entrantes", "entrantes desde", "orígenes"),
                                   ("paises_salientes", "salientes hacia", "destinos")):
        p = an.get(clave_)
        if p:
            t[clave_] = (f"Se identificaron conexiones {sentido} países diferentes a Colombia que fueron permitidas por la "
                         f"red. Los principales {verbo} fueron " + lista([f"{x['pais']} ({n(x['total'])} eventos)" for x in p[:3]])
                         + ". Se recomienda revisar este tráfico en los dispositivos de seguridad perimetral y bloquear "
                           "los países sin relación con la entidad, para reducir la superficie de ataque.")
    if an.get("puertos"):
        t["puertos"] = ("Se presentan los puertos no comunes con tráfico aceptado, tanto de entrada como de salida, que "
                        "pueden representar información relevante para su gestión. Se consideran puertos no comunes "
                        "aquellos que no son utilizados habitualmente por aplicaciones o servicios conocidos (por ejemplo "
                        "80, 443, 8080, 22, 3389, 1433 o 514).")
    ips = (an.get("ips") or {}).get("bloqueados")
    if ips:
        t["ips"] = (f"Se presenta el top de ataques detectados y bloqueados por el IPS, que resalta los intentos de "
                    f"intrusión más frecuentes contra la red. El más frecuente fue {ips[0]['ataque']} con "
                    f"{n(ips[0]['total'])} eventos. Esta información permite identificar los vectores de ataque más "
                    f"utilizados, evaluar la efectividad de las políticas de seguridad y reforzar la protección de los "
                    f"servicios más expuestos.")

    recs = list(RECOMENDACIONES_BASE)
    if f and f.get("no_envian"):
        recs.insert(0, f"Revisar las {n(f['no_envian'])} fuentes que no están enviando logs al SIEM, ya que afectan la "
                       f"visibilidad del monitoreo.")
    t["recomendaciones"] = "\n".join(recs)

    soc = m["servicios"].get("SOC") or next(iter(m["servicios"].values()), None)
    if soc:
        act, ant = soc["periodos"][-1], soc["periodos"][-2]
        conc = f"En el periodo {m['periodos'][-1]['etiqueta']} se escalaron {n(act['total'])} eventos"
        var = _variacion(ant["total"], act["total"])
        conc += f"; el volumen {var}." if var else "."
        if soc["top_alertas"]:
            conc += f" La alerta más recurrente fue {soc['top_alertas'][0]['alerta']} ({n(soc['top_alertas'][0]['total'])} eventos)."
        k = len(soc["destacados"])
        if k == 1:
            conc += " Se reportó 1 evento de criticidad alta o crítica."
        elif k:
            conc += f" Se reportaron {n(k)} eventos de criticidad alta o crítica."
        if act["total"]:
            conc += f" El {pct(act['con_retro'], act['total'])} de los eventos obtuvo retroalimentación del cliente; " \
                    f"se recomienda fortalecer este canal para mejorar la afinación de los casos de uso."
        t["conclusiones"] = conc
    return t
