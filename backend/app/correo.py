"""Correo de alerta al cliente: destinatarios controlados y borrador de Outlook (.eml).

Nadie escribe destinatarios al enviar: salen del cliente del caso. Se validan al guardarlos y otra vez al
generar cada correo, y solo se aceptan direcciones de los dominios del cliente o del dominio propio.
"""
import base64
import html
import re
from email.message import EmailMessage
from email.policy import SMTP
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .adjuntos import MB, texto_de
from .config import settings
from .models import Caso, Cliente, Seguimiento
from .notificacion import ANCHO, construir_notificacion

RECURSOS = Path(__file__).parent / "recursos_correo"
_CORREO = re.compile(r"[a-z0-9][a-z0-9._%+'-]*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}")
_DOMINIO = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}")
# Dominios que no identifican a un cliente
PUBLICOS = {"gmail.com", "hotmail.com", "outlook.com", "outlook.es", "live.com", "yahoo.com", "yahoo.es", "icloud.com",
            "msn.com", "proton.me", "protonmail.com", "aol.com", "com.co", "gov.co", "edu.co", "org.co", "net.co"}


class ErrorCorreo(ValueError):
    pass


def leer_correos(texto: str) -> list[str]:
    """Acepta 'a@x.co; Nombre Apellido <b@x.co>' separados por ; , o líneas. Falla si algo no es un correo."""
    salida, malos = [], []
    for trozo in re.split(r"[;\n\r]+", texto or ""):
        entre = re.findall(r"<([^<>]*)>", trozo)
        # con "Nombre <correo>" se ignora el nombre, pero ninguna otra dirección de la línea se pierde en silencio
        sueltos = re.split(r"[,\s]+", re.sub(r"<[^<>]*>", " ", trozo))
        partes = entre + [x for x in sueltos if "@" in x] if entre else sueltos
        for x in partes:
            x = x.strip().strip("\"'").lower()
            if not x:
                continue
            (salida if _CORREO.fullmatch(x) else malos).append(x)
    if malos:
        raise ErrorCorreo("No son correos válidos: " + ", ".join(malos[:5]))
    return list(dict.fromkeys(salida))


def leer_dominios(texto: str) -> list[str]:
    ds = list(dict.fromkeys(d.strip().lstrip("@").lower() for d in re.split(r"[;,\s]+", texto or "") if d.strip()))
    malos = [d for d in ds if not _DOMINIO.fullmatch(d)]
    if malos:
        raise ErrorCorreo("No son dominios válidos: " + ", ".join(malos[:5]))
    generales = [d for d in ds if d in PUBLICOS]
    if generales:
        raise ErrorCorreo("No identifican a un solo cliente: " + ", ".join(generales))
    return [d for d in ds if d != settings.correo_dominio_propio]


def _en(correo: str, dominios) -> bool:
    d = correo.rsplit("@", 1)[-1]
    return any(d == x or d.endswith("." + x) for x in dominios)


def fuera_de_dominio(correos: list[str], dominios: list[str]) -> list[str]:
    return [c for c in correos if not _en(c, [*dominios, settings.correo_dominio_propio])]


def validar_cliente(db: Session, cliente: Cliente, para: list[str], cc: list[str], dominios: list[str]):
    ajenos = fuera_de_dominio([*para, *cc], dominios)
    if ajenos:
        raise ErrorCorreo("Estas direcciones no pertenecen a los dominios del cliente: " + ", ".join(ajenos[:5]))
    for otro in db.scalars(select(Cliente).where(Cliente.id != cliente.id)):
        choque = [d for d in dominios for o in (otro.correos_dominios or [])
                  if d == o or d.endswith("." + o) or o.endswith("." + d)]
        if choque:
            raise ErrorCorreo(f"El dominio {choque[0]} ya es de {otro.codigo}")


# ------------------------------------------------------------------ contenido
@lru_cache
def _imagen(nombre: str) -> bytes:
    return (RECURSOS / nombre).read_bytes()


def _uri(nombre: str) -> str:
    return "data:image/png;base64," + base64.b64encode(_imagen(nombre)).decode()


def _cuerpo(tabla: str, banner: str, logo: str) -> str:
    tlp = html.escape(settings.correo_tlp)
    marca = f'<p style="margin:0 0 16px"><span style="background:#000000;color:#FF2B2B">{tlp}</span></p>'
    return f'''<div style="font-family:Arial,sans-serif;font-size:15px;color:#000000">
{marca}<p style="margin:0 0 16px">Cordial saludo,</p>
<p style="margin:0 0 16px">Se envía evento para su gestión.</p>
<p style="margin:0 0 16px"><img src="{banner}" width="785" height="137" alt="Ciberseguridad - Wexler"></p>
{tabla}
<p style="margin:20px 0 16px;color:#333333">Nota: De no recibir retroalimentación en un plazo de {settings.correo_plazo_horas} horas después del escalamiento del evento, se procederá con el cierre del mismo.</p>
<p style="margin:0 0 16px;max-width:{ANCHO}px"><b>IMPORTANTE:</b> Este mensaje contiene información clasificada como {tlp}, de acuerdo con el protocolo FIRST. La información es altamente sensible y está destinada únicamente a las personas autorizadas. No debe compartirse ni redistribuirse sin consentimiento explícito.</p>
{marca}<p style="margin:0 0 8px;color:#333333">Cordialmente,</p>
<table cellspacing="0" cellpadding="0"><tr><td style="padding-right:36px;vertical-align:middle"><img src="{logo}" width="121" height="23" alt="Wexler"></td>
<td style="font-size:13px;line-height:20px"><b style="font-size:18px">SOC WEXLER</b><br><b style="color:#FF5A4F">Centro de operaciones</b><br>+57 321 453 7127<br>soc@wexler.com.co<br><a href="https://www.wexler.com.co">www.wexler.com.co</a></td></tr></table>
</div>'''


def _menciona(texto: str, dominio: str) -> bool:
    t = texto.replace("[.]", ".").replace("(.)", ".").lower()
    return re.search(r"(?<![a-z0-9-])" + re.escape(dominio) + r"(?![a-z0-9-])", t) is not None


def _evidencias(c: Caso, src) -> list[tuple[str, int, str]]:
    return [(src(a), min(a.ancho or ANCHO, ANCHO - 30), a.nombre) for a in c.adjuntos if a.incluir and a.tipo == "EVIDENCIA"]


def _codigo_en(nombre: str, codigo: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(codigo.lower()) + r"(?![a-z0-9])", nombre.lower()) is not None


def preparar(db: Session, c: Caso) -> dict:
    """Destinatarios, asunto y comprobaciones. `bloqueos` impide generar; `advertencias` exige confirmar."""
    cl = c.cliente
    n = construir_notificacion(c, _evidencias(c, lambda a: f"data:{a.mime};base64,{base64.b64encode(a.contenido).decode()}"))
    incluidos = [a for a in c.adjuntos if a.incluir]
    para, cc = list(cl.correos_para or []), list(cl.correos_cc or [])
    cc += [x for x in leer_correos(settings.correo_cc) if x not in cc and x not in para]
    cco = [x for x in leer_correos(settings.correo_cco) if x not in para and x not in cc]
    bloqueos, advertencias = [], []
    if not cl.activo:
        bloqueos.append(f"{cl.codigo} está inactivo")
    if not para:
        bloqueos.append(f"{cl.codigo} no tiene destinatarios. Pida al Líder SOC que los configure en Clientes")
    ajenos = fuera_de_dominio([*para, *(cl.correos_cc or [])], cl.correos_dominios or [])
    if ajenos:
        bloqueos.append("Hay destinatarios fuera de los dominios del cliente: " + ", ".join(ajenos))
    total = sum(a.tamano for a in incluidos)
    if total > settings.correo_max_mb * MB:
        bloqueos.append(f"Los archivos del correo suman {total / MB:.1f} MB y el máximo es {settings.correo_max_mb} MB. Quite alguno del correo")
    texto = " ".join(x or "" for x in (c.alerta, c.resumen_ejecutivo, c.analisis, c.acciones_recomendadas, c.log_evento,
                                       c.reporting_ip, c.geolocalizacion))
    for otro in db.scalars(select(Cliente).where(Cliente.id != cl.id)):
        for d in otro.correos_dominios or []:
            if _menciona(texto, d):
                advertencias.append(f"El contenido menciona {d}, que es de {otro.codigo}. Revise que no sea información de otro cliente")
            for a in incluidos:
                if _menciona(a.nombre, d) or _menciona(texto_de(a), d):
                    advertencias.append(f"El archivo {a.nombre} menciona {d}, que es de {otro.codigo}")
        for a in incluidos:
            if _codigo_en(a.nombre, otro.codigo) and not _codigo_en(a.nombre, cl.codigo):
                advertencias.append(f"El nombre del archivo {a.nombre} contiene {otro.codigo}, que es otro cliente")
    for nombre, v in (("el resumen ejecutivo", c.resumen_ejecutivo), ("el análisis", c.analisis),
                      ("las acciones recomendadas", c.acciones_recomendadas)):
        if not (v or "").strip():
            advertencias.append(f"Falta {nombre}")
    if c.revision == "OBSERVADO":
        advertencias.append("El caso fue devuelto con observaciones y no se ha corregido")
    previo = db.scalar(select(Seguimiento).where(Seguimiento.caso_id == c.id, Seguimiento.tipo == "correo")
                       .order_by(Seguimiento.creado_en.desc()).limit(1))
    if previo:
        advertencias.append(f"Ya se generó un borrador de este caso ({previo.autor_nombre})")
    return {"cliente": cl.etiqueta, "asunto": n["asunto_correo"], "para": para, "cc": cc, "cco": cco,
            "bloqueos": bloqueos, "advertencias": list(dict.fromkeys(advertencias)),
            "archivos": [{"nombre": a.nombre, "tipo": a.tipo, "tamano": a.tamano} for a in incluidos], "html": _cuerpo(n["html"], _uri("banner.png"), _uri("logo.png"))}


def borrador(c: Caso, d: dict) -> bytes:
    """Borrador .eml: X-Unsent hace que Outlook de escritorio lo abra listo para editar y enviar."""
    n = construir_notificacion(c, _evidencias(c, lambda a: f"cid:ev{a.id}@soc"))
    m = EmailMessage(policy=SMTP)
    m["Subject"], m["To"], m["X-Unsent"] = d["asunto"], ", ".join(d["para"]), "1"
    if d["cc"]:
        m["Cc"] = ", ".join(d["cc"])
    if d["cco"]:
        m["Bcc"] = ", ".join(d["cco"])
    m.set_content(n["texto"])
    m.add_alternative("<html><body>" + _cuerpo(n["html"], "cid:banner@soc", "cid:logo@soc") + "</body></html>", subtype="html")
    cuerpo = m.get_payload()[1]
    for nombre in ("banner", "logo"):
        cuerpo.add_related(_imagen(f"{nombre}.png"), "image", "png", cid=f"<{nombre}@soc>", filename=f"{nombre}.png", disposition="inline")
    for a in c.adjuntos:
        if not a.incluir:
            continue
        principal, sub = a.mime.split("/", 1)
        if a.tipo == "EVIDENCIA":
            cuerpo.add_related(a.contenido, principal, sub, cid=f"<ev{a.id}@soc>", filename=a.nombre, disposition="inline")
        else:
            m.add_attachment(a.contenido, principal, sub, filename=a.nombre)
    return m.as_bytes()
