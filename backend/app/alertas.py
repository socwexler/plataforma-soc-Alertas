"""Alertas por tratar: tickets que el SIEM crea en GLPI (por correo) y que se deben reportar al cliente.

La plataforma busca en GLPI los tickets abiertos que cumplen los criterios de Configuración → GLPI, los muestra en
la bandeja y, al reportarlos, crea el caso WX con el mismo ticket. El flujo manual (el N1 crea el caso y el ticket)
sigue igual: sirve para los clientes que aún no están afinados en el SIEM.
"""
import html
import logging
import re
import threading
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import avisos
from .config import settings
from .db import SessionLocal
from .glpi import ClienteGLPI, ErrorGLPI
from .models import Alerta, Caso, Cliente, Seguimiento, Usuario

log = logging.getLogger("uvicorn.error")

PENDIENTES = ("POR_REPORTAR", "EN_GESTION")
# Urgencia del ticket en GLPI (1 muy baja … 5 muy alta) -> criticidad propuesta; el analista la puede cambiar
CRITICIDAD = {5: "Crítica", 4: "Alta", 3: "Media", 2: "Baja", 1: "Baja"}
MAX_POR_VEZ = 100          # tickets nuevos que se leen en cada búsqueda
MAX_TEXTO = 20000

_estado = {"ultima": None, "resultado": None, "error": None}
_candado = threading.Lock()


# ------------------------------------------------------------------ lectura del ticket
class _Texto(HTMLParser):
    SALTO = {"br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4", "table"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self.oculto = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.oculto += 1
        elif tag in self.SALTO:
            self.partes.append("\n")
        elif tag in ("td", "th"):
            self.partes.append("\t")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.oculto = max(0, self.oculto - 1)
        elif tag in self.SALTO:
            self.partes.append("\n")

    def handle_data(self, data):
        if not self.oculto:
            self.partes.append(data)


def texto_plano(contenido: str | None) -> str:
    """El contenido del ticket llega en HTML (GLPI 10 lo guarda escapado): se deja solo el texto."""
    if not contenido:
        return ""
    s = contenido
    for _ in range(2):   # &lt;p&gt; -> <p>
        if "&lt;" not in s and "&amp;" not in s:
            break
        s = html.unescape(s)
    p = _Texto()
    p.feed(s)
    p.close()
    # espacios repetidos a uno; las celdas de una tabla quedan separadas por tabulador
    lineas = [re.sub(r"\s*\t\s*", "\t", re.sub(r"[^\S\t]+", " ", x)).strip()
              for x in "".join(p.partes).replace("\r", "").split("\n")]
    t = re.sub(r"\n{3,}", "\n\n", "\n".join(lineas)).strip()
    return t[:MAX_TEXTO]


def _entero(v, defecto):
    try:
        return int(v)
    except (TypeError, ValueError):
        return defecto


def _fecha(v) -> datetime:
    """Fecha del ticket («2026-11-26 10:15:00», hora del servidor de GLPI: la de Colombia)."""
    try:
        d = datetime.fromisoformat(str(v))
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)
    if d.tzinfo is None:
        d = d.replace(tzinfo=ZoneInfo(settings.zona_horaria))
    return min(d.astimezone(timezone.utc), datetime.now(timezone.utc))


def criterios(desde: datetime) -> dict:
    """Búsqueda de GLPI (search/Ticket): abiertos, recientes y con los criterios configurados.
    Campos de GLPI: 1 título, 2 id, 7 categoría, 9 origen, 12 estado, 15 fecha de apertura."""
    c = [(12, "equals", "notold"), (15, "morethan", desde.astimezone(ZoneInfo(settings.zona_horaria)).strftime("%Y-%m-%d %H:%M:%S"))]
    if settings.glpi_alertas_origen_id:
        c.append((9, "equals", settings.glpi_alertas_origen_id))
    if settings.glpi_alertas_categoria_id:
        c.append((7, "equals", settings.glpi_alertas_categoria_id))
    if settings.glpi_alertas_texto:
        c.append((1, "contains", settings.glpi_alertas_texto))
    p: dict = {}
    for i, (campo, tipo, valor) in enumerate(c):
        if i:
            p[f"criteria[{i}][link]"] = "AND"
        p[f"criteria[{i}][field]"] = campo
        p[f"criteria[{i}][searchtype]"] = tipo
        p[f"criteria[{i}][value]"] = valor
    p["forcedisplay[0]"] = 2
    p["sort"] = 15
    p["order"] = "ASC"
    return p


def _buscar(g: ClienteGLPI, desde: datetime) -> list[int]:
    ids: list[int] = []
    for inicio in range(0, 1000, 200):
        r = g._req("GET", "/search/Ticket", params={**criterios(desde), "range": f"{inicio}-{inicio + 199}"}) or {}
        filas = r.get("data") or []
        ids += [int(x["2"]) for x in filas if str(x.get("2", "")).isdigit()]
        if len(filas) < 200 or len(ids) >= int(r.get("totalcount") or 0):
            break
    return ids


def _clientes(db: Session) -> dict[int, int]:
    """Entidad de GLPI -> cliente (solo si una sola ficha activa tiene esa entidad)."""
    cuenta: dict[int, list[int]] = {}
    for c in db.scalars(select(Cliente).where(Cliente.activo, Cliente.glpi_entidad_id.is_not(None))):
        cuenta.setdefault(c.glpi_entidad_id, []).append(c.id)
    return {e: ids[0] for e, ids in cuenta.items() if len(ids) == 1}


# ------------------------------------------------------------------ búsqueda periódica
def traer(db: Session) -> dict:
    """Trae los tickets nuevos, asigna el cliente y saca de la bandeja los que se cerraron en GLPI."""
    if not settings.glpi_activo:
        raise ErrorGLPI("La integración con GLPI no está configurada (Configuración → GLPI)")
    if not settings.glpi_alertas_activo:
        raise ErrorGLPI("La bandeja de alertas no está activada (Configuración → GLPI)")
    if not _candado.acquire(timeout=60):
        raise ErrorGLPI("Ya hay una búsqueda de alertas en curso")
    try:
        return _traer(db)
    finally:
        _candado.release()


def _traer(db: Session) -> dict:
    ahora = datetime.now(timezone.utc)
    mapa = _clientes(db)
    nuevas = cerradas = 0
    with ClienteGLPI() as g:
        ids = _buscar(g, ahora - timedelta(days=settings.glpi_alertas_dias))
        abiertos = set(ids)
        conocidos = set(db.scalars(select(Alerta.glpi_ticket_id).where(Alerta.glpi_ticket_id.in_(ids)))) if ids else set()
        # los tickets que ya tienen caso (creados por la plataforma o digitados) no son alertas por tratar
        con_caso = set(db.scalars(select(Caso.glpi_ticket_id).where(Caso.glpi_ticket_id.in_(ids)))) if ids else set()
        for tid in [x for x in ids if x not in conocidos and x not in con_caso][:MAX_POR_VEZ]:
            t = g._req("GET", f"/Ticket/{tid}") or {}
            estado = _entero(t.get("status"), 1)
            if estado >= 5:
                continue
            entidad = _entero(t.get("entities_id"), None)
            titulo = " ".join(str(t.get("name") or f"Ticket {tid}").split())[:300]
            try:
                with db.begin_nested():
                    db.add(Alerta(glpi_ticket_id=tid, glpi_entidad_id=entidad, glpi_estado=estado, cliente_id=mapa.get(entidad),
                                  titulo=titulo, contenido=texto_plano(t.get("content")), estado="POR_REPORTAR",
                                  criticidad=CRITICIDAD.get(_entero(t.get("urgency"), 3)), fecha_alerta=_fecha(t.get("date"))))
                nuevas += 1
            except IntegrityError:   # otro proceso la trajo al mismo tiempo
                pass
        # las pendientes: cliente asignado después y tickets que ya no están abiertos en GLPI
        for a in db.scalars(select(Alerta).where(Alerta.estado.in_(PENDIENTES))).unique().all():
            if a.cliente_id is None and a.glpi_entidad_id in mapa:
                a.cliente_id = mapa[a.glpi_entidad_id]
            if a.glpi_ticket_id in abiertos:
                continue
            try:
                a.glpi_estado = g.estado_ticket(a.glpi_ticket_id)
            except ErrorGLPI:
                continue
            if a.glpi_estado >= 5:
                a.estado, a.cerrada_en = "CERRADA_GLPI", ahora
                cerradas += 1
    # aviso interno: superó su SLA sin que nadie la tome (una vez)
    for a in db.scalars(select(Alerta).where(Alerta.estado == "POR_REPORTAR", Alerta.avisada_en.is_(None))).unique().all():
        espera = int((ahora - a.fecha_alerta).total_seconds() // 60)
        if espera > a.sla_minutos:
            avisos.alerta_sin_tomar(db, a, espera)
            a.avisada_en = ahora
    db.commit()
    return {"revisados": len(ids), "nuevas": nuevas, "cerradas": cerradas}


def ejecutar() -> dict:
    with SessionLocal() as db:
        try:
            _estado["resultado"] = traer(db)
            _estado["error"] = None
        except Exception as e:  # noqa: BLE001 - se registra y se reintenta en el próximo ciclo
            db.rollback()
            if not _estado["error"]:   # solo al empezar a fallar
                avisos.falla_glpi(db, f"Alertas por tratar: {e}")
                db.commit()
            _estado["error"] = str(e)
            log.warning("Búsqueda de alertas en GLPI falló: %s", e)
        _estado["ultima"] = datetime.now(timezone.utc)
    return _estado


def estado() -> dict:
    return {"activo": bool(settings.glpi_activo and settings.glpi_alertas_activo), "minutos": settings.glpi_alertas_minutos,
            "ultima": _estado["ultima"], "resultado": _estado["resultado"], "error": _estado["error"]}


def toca(ultima: datetime | None) -> bool:
    return (settings.glpi_activo and settings.glpi_alertas_activo
            and (ultima is None or datetime.now(timezone.utc) - ultima >= timedelta(minutes=settings.glpi_alertas_minutos)))


# ------------------------------------------------------------------ con los casos
def reportar(db: Session, a: Alerta, c: Caso, yo: Usuario):
    """La alerta queda reportada con su caso (el caso ya tiene el número de ticket)."""
    ahora = datetime.now(timezone.utc)
    a.estado, a.caso_id, a.reportada_en = "REPORTADA", c.id, ahora
    if a.analista_id is None:
        a.analista_id, a.tomada_en = yo.id, ahora
    llego = a.fecha_alerta.astimezone(ZoneInfo(settings.zona_horaria)).strftime("%d/%m/%Y %H:%M")
    db.add(Seguimiento(caso_id=c.id, autor_id=yo.id, autor_nombre=yo.nombre, tipo="glpi",
                       comentario=f"Caso creado desde «Alertas por tratar»: ticket GLPI {a.glpi_ticket_id} (llegó a GLPI el {llego})"))


def vincular_ticket(db: Session, c: Caso, yo: Usuario):
    """Si a un caso se le pone (a mano o al crear el ticket) el número de una alerta pendiente, la alerta queda reportada."""
    if not c.glpi_ticket_id:
        return
    a = db.scalar(select(Alerta).where(Alerta.glpi_ticket_id == c.glpi_ticket_id, Alerta.estado.in_(PENDIENTES)))
    if a and not db.scalar(select(Alerta.id).where(Alerta.caso_id == c.id)):
        reportar(db, a, c, yo)


def limpiar_ticket_propio(db: Session, tid: int):
    """Un ticket que acaba de crear la plataforma no es una alerta (por si la búsqueda lo alcanzó a traer)."""
    db.execute(delete(Alerta).where(Alerta.glpi_ticket_id == tid, Alerta.caso_id.is_(None), Alerta.analista_id.is_(None)))


def iniciar(parar: threading.Event):
    """Busca alertas cada `glpi_alertas_minutos` (la configuración puede cambiar en cualquier momento)."""
    def ciclo():
        ultima = datetime.now(timezone.utc)   # la primera, pasado el intervalo desde el arranque
        while not parar.wait(20):
            if toca(ultima):
                ultima = datetime.now(timezone.utc)
                ejecutar()

    hilo = threading.Thread(target=ciclo, name="alertas-glpi", daemon=True)
    hilo.start()
    return hilo
