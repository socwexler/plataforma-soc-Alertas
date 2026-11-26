"""Avisos internos del SOC por correo (SMTP). Nunca se envía nada a clientes.

Se encolan en la base y un hilo los envía: si el servidor de correo falla, se reintenta sin afectar el registro de casos.
Solo llevan número, cliente, alerta y criticidad; el detalle se consulta en la plataforma.
"""
import logging
import smtplib
import ssl
import threading
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import correo
from .config import settings
from .db import SessionLocal
from .models import Aviso, Caso, Usuario

log = logging.getLogger("uvicorn.error")
MAX_INTENTOS = 6


class ErrorAviso(Exception):
    pass


def _propios(texto: str | None) -> list[str]:
    return [x for x in correo.leer_correos(texto or "") if correo._en(x, [settings.correo_dominio_propio])]


def configurado() -> bool:
    return bool(settings.smtp_servidor and settings.smtp_remitente)


# ------------------------------------------------------------------ encolar
def _encolar(db: Session, tipo: str, asunto: str, cuerpo: str, para: list[str] | None = None):
    if settings.avisos_activo and configurado():
        db.add(Aviso(tipo=tipo, asunto=" ".join(asunto.split())[:250], cuerpo=cuerpo, para=para or [], estado="PENDIENTE", intentos=0,
                     proximo=datetime.now(timezone.utc)))


def _linea(c: Caso) -> str:
    enlace = f"\n  {settings.url_plataforma}/casos/{c.id}" if settings.url_plataforma else ""
    return f"{c.numero} · {c.cliente.codigo} · {c.criticidad or 'sin criticidad'} · {' '.join(c.alerta.split())[:160]}{enlace}"


def por_revisar(db: Session, c: Caso):
    if settings.aviso_por_revisar:
        _encolar(db, "por_revisar", f"Caso por revisar: {c.numero}", _linea(c))


def devuelto(db: Session, c: Caso, revisor: Usuario, nota: str):
    if settings.aviso_devuelto:
        try:
            para = _propios(c.analista.email if c.analista else None)
        except correo.ErrorCorreo:
            para = []
        _encolar(db, "devuelto", f"Caso devuelto para corregir: {c.numero}", f"{_linea(c)}\n\n{revisor.nombre} lo devolvió: {nota}", para)


def falla_glpi(db: Session, texto: str, c: Caso | None = None):
    if settings.aviso_glpi:
        _encolar(db, "glpi", f"Falla de GLPI{': ' + c.numero if c else ''}", (_linea(c) + "\n\n" if c else "") + f"Error: {texto[:400]}")


def alerta_sin_tomar(db: Session, a, minutos: int):
    """Alerta de GLPI que superó su SLA sin que nadie la tome (una sola vez por alerta)."""
    if settings.aviso_alerta_sin_tomar:
        enlace = f"\n  {settings.url_plataforma}/alertas" if settings.url_plataforma else ""
        cliente = a.cliente.codigo if a.cliente else "sin cliente asignado"
        _encolar(db, "alerta", f"Alerta sin tomar: ticket GLPI {a.glpi_ticket_id}",
                 f"Ticket GLPI {a.glpi_ticket_id} · {cliente} · {a.criticidad or 'sin criticidad'} · {' '.join(a.titulo.split())[:160]}"
                 f"\nLleva {minutos} minutos en «Alertas por tratar» sin que nadie la tome (SLA: {a.sla_minutos} minutos).{enlace}")


# ------------------------------------------------------------------ enviar
def _conexion() -> smtplib.SMTP:
    ctx = ssl.create_default_context()
    if not settings.smtp_verificar_ssl:
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
    try:
        if settings.smtp_seguridad == "SSL":
            s = smtplib.SMTP_SSL(settings.smtp_servidor, settings.smtp_puerto, timeout=20, context=ctx)
        else:
            s = smtplib.SMTP(settings.smtp_servidor, settings.smtp_puerto, timeout=20)
            if settings.smtp_seguridad == "STARTTLS":
                s.starttls(context=ctx)
        if settings.smtp_usuario:
            s.login(settings.smtp_usuario, settings.smtp_clave or "")
        return s
    except smtplib.SMTPAuthenticationError as e:
        raise ErrorAviso("El servidor de correo rechazó el usuario o la contraseña") from e
    except (smtplib.SMTPException, OSError, ssl.SSLError) as e:
        raise ErrorAviso(f"No se pudo conectar con el servidor de correo: {e}"[:300]) from e


def _enviar(s: smtplib.SMTP, para: list[str], asunto: str, cuerpo: str):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = f"Plataforma SOC <{settings.smtp_remitente}>", ", ".join(para), f"[SOC] {asunto}"
    m["Date"], m["Message-ID"] = formatdate(localtime=True), make_msgid(domain=settings.correo_dominio_propio)
    m["Auto-Submitted"] = "auto-generated"
    m.set_content(cuerpo + "\n\n--\nAviso automático de la Plataforma SOC. No responda a este correo.")
    try:
        s.send_message(m)
    except (smtplib.SMTPException, OSError) as e:
        raise ErrorAviso(f"El servidor de correo no aceptó el mensaje: {e}"[:300]) from e


def probar(para: str):
    """Correo de prueba inmediato, solo al dominio propio."""
    lista = _propios(para)
    if len(lista) != 1:
        raise ErrorAviso(f"Escriba una dirección de {settings.correo_dominio_propio}")
    if not configurado():
        raise ErrorAviso("Guarde primero el servidor y el remitente")
    s = _conexion()
    try:
        _enviar(s, lista, "Prueba de avisos", "La configuración de avisos funciona.")
    finally:
        _cerrar(s)


def _cerrar(s: smtplib.SMTP):
    try:
        s.quit()
    except (smtplib.SMTPException, OSError):
        pass


def procesar(db: Session) -> int:
    """Envía lo pendiente. Los casos por revisar se agrupan en un solo correo."""
    ahora = datetime.now(timezone.utc)
    db.execute(delete(Aviso).where(Aviso.creado_en < ahora - timedelta(days=90)))
    pendientes = db.scalars(select(Aviso).where(Aviso.estado == "PENDIENTE").order_by(Aviso.id)).all()
    for a in [x for x in pendientes if x.creado_en < ahora - timedelta(hours=24)]:
        a.estado, a.error = "DESCARTADO", a.error or "No se envió en 24 horas"
    pendientes = [x for x in pendientes if x.estado == "PENDIENTE" and x.proximo <= ahora]
    db.commit()
    if not pendientes or not (settings.avisos_activo and configurado()):
        return 0
    grupos = [[a] for a in pendientes if a.tipo != "por_revisar"]
    rev = [a for a in pendientes if a.tipo == "por_revisar"]
    if rev and rev[0].creado_en <= ahora - timedelta(minutes=settings.avisos_agrupar_min or 0):
        grupos.append(rev)
    if not grupos:
        return 0
    enviados, s, fallo = 0, None, None
    for g in grupos:
        try:
            if fallo:
                raise fallo
            if s is None:
                try:
                    s = _conexion()
                except ErrorAviso as e:
                    fallo = e
                    raise
            para = [x for x in g[0].para if correo._en(x, [settings.correo_dominio_propio])] or _propios(settings.avisos_destino)
            if not para:
                raise ErrorAviso("No hay destinatarios configurados")
            asunto = g[0].asunto if len(g) == 1 else f"{len(g)} casos por revisar"
            _enviar(s, para, asunto, "\n".join(a.cuerpo for a in g))
            for a in g:
                a.estado, a.enviado_en, a.error = "ENVIADO", datetime.now(timezone.utc), None
            enviados += 1
        except ErrorAviso as e:
            for a in g:
                a.intentos += 1
                a.error, a.proximo = str(e), ahora + timedelta(minutes=2 ** a.intentos)
                if a.intentos >= MAX_INTENTOS:
                    a.estado = "ERROR"
        db.commit()
    if s is not None:
        _cerrar(s)
    return enviados


def iniciar(parar: threading.Event):
    def ciclo():
        while not parar.wait(20):
            with SessionLocal() as db:
                try:
                    procesar(db)
                except Exception as e:  # noqa: BLE001 - se reintenta en el próximo ciclo
                    db.rollback()
                    log.warning("Avisos internos: %s", e)
    threading.Thread(target=ciclo, name="avisos", daemon=True).start()
