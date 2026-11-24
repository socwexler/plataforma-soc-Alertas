"""Texto y HTML de la notificación de un caso al cliente (equivale a la hoja 'Plantilla' del Excel)."""
import html
import re
from zoneinfo import ZoneInfo

from .config import settings
from .models import Caso

TZ = ZoneInfo(settings.zona_horaria)


def construir_notificacion(c: Caso, evidencias: list[tuple[str, int, str]] = ()) -> dict:
    """evidencias: (src de la imagen, ancho en px, nombre), ya listas para el recuadro de la plantilla."""
    fecha = c.fecha_evento.astimezone(TZ).strftime("%d/%m/%Y %H:%M") if c.fecha_evento else ""
    tactica = c.tactica.nombre if c.tactica else (c.tactica_original or "")
    secciones = [
        ("Resumen ejecutivo", c.resumen_ejecutivo),
        ("Análisis de seguridad", c.analisis),
        ("Detalles del evento (LOG)", c.log_evento),
        ("Acciones de seguridad recomendadas", c.acciones_recomendadas),
    ]
    titulo = "Alerta Evento De Seguridad" if c.servicio == "SOC" else "Alerta Evento NOC"
    asunto = f"[{c.numero}] {c.cliente.codigo} - {c.alerta} - Criticidad {c.criticidad or ''}".strip()

    lineas = [titulo, "",
              f"Número de reporte: {c.numero}    Criticidad / Impacto: {c.criticidad or ''}",
              f"Alerta detectada: {c.alerta}",
              f"Técnica: {c.tecnica or ''}    Táctica: {tactica}",
              f"Geolocalización: {c.geolocalizacion or 'N/A'}    Fuente que reporta: {c.reporting_ip or ''}",
              f"Fecha del evento: {fecha}    Cliente: {c.cliente.etiqueta}"]
    if c.glpi_ticket_id:
        lineas.append(f"Ticket GLPI: {c.glpi_ticket_id}")
    for t, v in secciones:
        if v:
            lineas += ["", t.upper(), v]

    asunto_correo = re.sub(r"\s+", " ", f"{c.numero}_{c.cliente.codigo}_{c.alerta}").strip()
    return {"asunto": asunto, "asunto_correo": asunto_correo, "texto": "\n".join(lineas),
            "html": _tabla(c, titulo, tactica, secciones, evidencias)}


# Colores de la hoja "Plantilla" de la bitácora
AZUL, GRIS, CLARO = "#2E4263", "#D9D9D9", "#F2F2F2"
COLOR_CRITICIDAD = {"Crítica": ("#C00000", "#FFFFFF"), "Alta": ("#FF0000", "#FFFFFF"),
                    "Media": ("#FFC000", "#000000"), "Baja": ("#92D050", "#000000")}
ANCHO = 800


def _multilinea(v) -> str:
    """Saltos y sangrías con <br>/&nbsp;: Outlook no respeta white-space."""
    t = html.escape(str(v or "")).replace("\r", "").replace("\t", "    ")
    return re.sub(r"(?m)^ +|  +", lambda m: "&nbsp;" * len(m.group()), t).replace("\n", "<br>")


def _tabla(c: Caso, titulo: str, tactica: str, secciones: list, evidencias=()) -> str:
    def cab(t, span=1):
        return (f'<td colspan="{span}" bgcolor="{AZUL}" align="center" style="background:{AZUL};color:#FFFFFF;font-weight:bold;'
                f'border:1px solid #000000;padding:6px 8px">{html.escape(t)}</td>')

    def dato(v, span=1, fondo=CLARO, extra="", alinear="center"):
        return (f'<td colspan="{span}" bgcolor="{fondo}" align="{alinear}" style="background:{fondo};border:1px solid #000000;'
                f'padding:6px 8px;vertical-align:middle;{extra}">{_multilinea(v) or "&nbsp;"}</td>')

    fondo, tinta = COLOR_CRITICIDAD.get(c.criticidad, (CLARO, "#000000"))
    resumen, analisis, log, acciones = (v for _, v in secciones)
    fecha = c.fecha_bitacora.strftime("%d/%m/%Y") if c.fecha_bitacora else ""
    imagenes = (f'<td colspan="4" bgcolor="{CLARO}" align="center" style="background:{CLARO};border:1px solid #000000;padding:8px">'
                + "<br><br>".join(f'<img src="{html.escape(src)}" width="{w}" alt="{html.escape(nom)}" style="width:{w}px;max-width:100%">'
                                  for src, w, nom in evidencias) + "</td>")
    filas = [
        cab(titulo, 4),
        cab("Numero de reporte") + dato(c.numero, fondo=GRIS, extra="font-size:16px;") + cab("Criticidad / Impacto")
        + dato(c.criticidad, fondo=fondo, extra=f"color:{tinta};"),
        cab("Alerta detectada") + dato(c.alerta, 3, extra="color:#E03C31;font-weight:bold;"),
        cab("Técnica") + dato(c.tecnica) + cab("Táctica") + dato(tactica),
        cab("Resumen ejecutivo", 4), dato(resumen, 4),
        cab("Geolocalización") + cab("Fuente que reporta", 3),
        dato(c.geolocalizacion or "N/A") + dato(c.reporting_ip, 3),
        cab("Análisis de seguridad", 4), dato(analisis, 4, alinear="left"),
        cab("Detalles del evento (LOG)", 4),
        dato(log, 4, alinear="left", extra="font-family:Consolas,'Courier New',monospace;font-size:12px;word-break:break-all;"),
        cab("Evidencias", 4), imagenes if evidencias else dato("", 4, extra="height:60px;"),
        cab("Acciones de seguridad recomendadas", 4), dato(acciones, 4, alinear="left"),
        cab("Fecha", 2) + dato(fecha, 2, fondo="#FFFFFF"),
    ]
    if c.glpi_ticket_id:
        filas.append(cab("Ticket", 2) + dato(c.glpi_ticket_id, 2, fondo="#FFFFFF"))
    return (f'<table width="{ANCHO}" cellspacing="0" cellpadding="0" style="width:{ANCHO}px;border-collapse:collapse;'
            f'table-layout:fixed;font-family:Calibri,Arial,sans-serif;font-size:14px;color:#000000">'
            + '<colgroup><col width="25%"><col width="25%"><col width="25%"><col width="25%"></colgroup>'
            + "".join(f"<tr>{f}</tr>" for f in filas) + "</table>")
