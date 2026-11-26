"""Integración con GLPI 10 por API REST (apirest.php).

GLPI se usa para que el cliente tenga un número de ticket y para hacerle seguimiento;
el detalle del caso vive en la plataforma.
"""
import logging
import threading
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from . import avisos
from .config import settings
from .db import SessionLocal
from .models import Caso, Seguimiento, Usuario
from .notificacion import construir_notificacion

log = logging.getLogger("uvicorn.error")

ESTADOS_GLPI = {1: "Nuevo", 2: "En curso (asignado)", 3: "En curso (planificado)", 4: "En espera",
                5: "Resuelto", 6: "Cerrado"}
# Criticidad del caso -> urgencia e impacto en GLPI (1 muy baja … 5 muy alta)
URGENCIA = {"Crítica": 5, "Alta": 4, "Media": 3, "Baja": 2}

_estado_sync = {"ultima": None, "resultado": None, "error": None}


class ErrorGLPI(Exception):
    pass


class ClienteGLPI:
    """Sesión de API de GLPI. Uso: `with ClienteGLPI() as g: g.crear_ticket(...)`."""

    def __init__(self):
        if not settings.glpi_activo:
            raise ErrorGLPI("La integración con GLPI no está configurada (Configuración → GLPI)")
        self.http = httpx.Client(base_url=settings.glpi_url.rstrip("/"), verify=settings.glpi_verificar_ssl,
                                 timeout=20, headers={"App-Token": settings.glpi_app_token,
                                                      "Content-Type": "application/json"})

    def __enter__(self):
        r = self._req("GET", "/initSession", headers={"Authorization": f"user_token {settings.glpi_user_token}"})
        self.http.headers["Session-Token"] = r["session_token"]
        return self

    def __exit__(self, *exc):
        try:
            self.http.get("/killSession")
        except httpx.HTTPError:
            pass
        self.http.close()

    def _req(self, metodo: str, ruta: str, **kw):
        try:
            r = self.http.request(metodo, ruta, **kw)
        except httpx.HTTPError as e:
            raise ErrorGLPI(f"No se pudo conectar con GLPI: {e}") from e
        if r.status_code >= 400:
            try:
                cuerpo = r.json()
                detalle = " - ".join(str(x) for x in cuerpo) if isinstance(cuerpo, list) else str(cuerpo)
            except ValueError:
                detalle = r.text[:300]
            raise ErrorGLPI(f"GLPI respondió {r.status_code}: {detalle}")
        return r.json() if r.content else None

    # ------------------------------------------------------------ operaciones
    def sesion(self) -> dict:
        s = self._req("GET", "/getFullSession")["session"]
        return {"usuario": s.get("glpiname"), "entidad_activa": s.get("glpiactive_entity_name")}

    def crear_ticket(self, nombre: str, contenido: str, entidad_id: int, criticidad: str | None) -> int:
        entrada = {
            "name": nombre[:250],
            "content": contenido,
            "entities_id": entidad_id,
            "type": settings.glpi_tipo_ticket,
            "urgency": URGENCIA.get(criticidad, 3),
            "impact": URGENCIA.get(criticidad, 3),
        }
        if settings.glpi_categoria_id:
            entrada["itilcategories_id"] = settings.glpi_categoria_id
        if settings.glpi_origen_id:
            entrada["requesttypes_id"] = settings.glpi_origen_id
        r = self._req("POST", "/Ticket", json={"input": entrada})
        if not isinstance(r, dict) or not r.get("id"):
            raise ErrorGLPI(f"GLPI no devolvió el número del ticket: {r}")
        return int(r["id"])

    def estado_ticket(self, ticket_id: int) -> int:
        return int(self._req("GET", f"/Ticket/{ticket_id}")["status"])

    def agregar_seguimiento(self, ticket_id: int, texto: str):
        self._req("POST", "/ITILFollowup",
                  json={"input": {"itemtype": "Ticket", "items_id": ticket_id, "content": texto}})

    def resolver_ticket(self, ticket_id: int, texto: str):
        self._req("POST", "/ITILSolution",
                  json={"input": {"itemtype": "Ticket", "items_id": ticket_id, "content": texto}})
        if self.estado_ticket(ticket_id) < 5:  # algunas configuraciones no cambian el estado solas
            self._req("PUT", f"/Ticket/{ticket_id}", json={"input": {"id": ticket_id, "status": 5}})


# ------------------------------------------------------------------ servicio
def _seg(db: Session, caso: Caso, autor: Usuario | None, texto: str):
    db.add(Seguimiento(caso_id=caso.id, autor_id=autor.id if autor else None,
                       autor_nombre=autor.nombre if autor else "GLPI", tipo="glpi", comentario=texto))


def crear_ticket_para_caso(db: Session, caso: Caso, autor: Usuario | None) -> int:
    """Crea el ticket y lo guarda en el caso. Si falla, deja el error en el caso y lanza ErrorGLPI."""
    if caso.glpi_ticket_id:
        raise ErrorGLPI(f"El caso ya tiene el ticket GLPI {caso.glpi_ticket_id}")
    try:
        if not caso.cliente.glpi_entidad_id:
            raise ErrorGLPI(f"El cliente {caso.cliente.codigo} no tiene asignada la entidad de GLPI (menú Clientes)")
        n = construir_notificacion(caso)
        with ClienteGLPI() as g:
            tid = g.crear_ticket(n["asunto"], n["html"], caso.cliente.glpi_entidad_id, caso.criticidad)
    except ErrorGLPI as e:
        caso.glpi_error = str(e)
        avisos.falla_glpi(db, str(e), caso)
        db.commit()
        raise
    from .alertas import limpiar_ticket_propio   # aquí: alertas importa este módulo
    limpiar_ticket_propio(db, tid)
    caso.glpi_ticket_id = tid
    caso.glpi_estado = 1
    caso.glpi_error = None
    caso.glpi_sincronizado_en = datetime.now(timezone.utc)
    _seg(db, caso, autor, f"Ticket GLPI {tid} creado")
    db.commit()
    return tid


def publicar_seguimiento(caso: Caso, texto: str):
    with ClienteGLPI() as g:
        g.agregar_seguimiento(caso.glpi_ticket_id, texto)


def resolver_ticket_de_caso(db: Session, caso: Caso, autor: Usuario | None):
    texto = "Caso cerrado por el SOC de Wexler."
    if caso.acciones_cliente:
        texto += f"\n\nAcciones ejecutadas por el cliente:\n{caso.acciones_cliente}"
    with ClienteGLPI() as g:
        g.resolver_ticket(caso.glpi_ticket_id, texto)
        caso.glpi_estado = g.estado_ticket(caso.glpi_ticket_id)
    caso.glpi_sincronizado_en = datetime.now(timezone.utc)
    _seg(db, caso, autor, f"Ticket GLPI {caso.glpi_ticket_id} marcado como resuelto")


def sincronizar(db: Session, dias: int = 90, maximo: int = 300) -> dict:
    """Actualiza el estado de los tickets no cerrados de los últimos `dias` días."""
    desde = datetime.now(timezone.utc) - timedelta(days=dias)
    casos = db.scalars(
        select(Caso).where(Caso.glpi_ticket_id.is_not(None), Caso.fecha_evento >= desde,
                           or_(Caso.glpi_estado.is_(None), Caso.glpi_estado < 6))
        .order_by(Caso.glpi_sincronizado_en.asc().nulls_first()).limit(maximo)
    ).unique().all()
    cambios = errores = 0
    if casos:
        with ClienteGLPI() as g:
            for c in casos:
                try:
                    nuevo = g.estado_ticket(c.glpi_ticket_id)
                except ErrorGLPI as e:
                    errores += 1
                    c.glpi_error = str(e)
                    continue
                if nuevo != c.glpi_estado:
                    if c.glpi_estado is not None:
                        _seg(db, c, None, f"Estado del ticket {c.glpi_ticket_id} en GLPI: "
                                          f"{ESTADOS_GLPI.get(c.glpi_estado, c.glpi_estado)} → {ESTADOS_GLPI.get(nuevo, nuevo)}")
                    c.glpi_estado = nuevo
                    cambios += 1
                c.glpi_error = None
                c.glpi_sincronizado_en = datetime.now(timezone.utc)
    db.commit()
    return {"revisados": len(casos), "cambios": cambios, "errores": errores}


def estado_integracion() -> dict:
    return {
        "activo": settings.glpi_activo,
        "url_web": settings.glpi_url_web,
        "crear_por_defecto": settings.glpi_crear_por_defecto,
        "resolver_al_cerrar": settings.glpi_resolver_al_cerrar,
        "sync_minutos": settings.glpi_sync_minutos,
        "ultima_sincronizacion": _estado_sync["ultima"],
        "resultado_sincronizacion": _estado_sync["resultado"],
        "error_sincronizacion": _estado_sync["error"],
        "estados": ESTADOS_GLPI,
    }


def ejecutar_sincronizacion():
    with SessionLocal() as db:
        try:
            _estado_sync["resultado"] = sincronizar(db)
            _estado_sync["error"] = None
        except Exception as e:  # noqa: BLE001 - se registra y se reintenta en el próximo ciclo
            db.rollback()
            if not _estado_sync["error"]:   # solo al empezar a fallar, no en cada intento
                avisos.falla_glpi(db, f"Sincronización: {e}")
                db.commit()
            _estado_sync["error"] = str(e)
            log.warning("Sincronización GLPI falló: %s", e)
        _estado_sync["ultima"] = datetime.now(timezone.utc)
    return _estado_sync


def iniciar_sincronizacion_periodica(parar: threading.Event):
    def ciclo():
        ultima = datetime.now(timezone.utc)
        while not parar.wait(30):   # la configuración puede cambiar en cualquier momento
            cada = settings.glpi_sync_minutos or 0
            if settings.glpi_activo and cada > 0 and datetime.now(timezone.utc) - ultima >= timedelta(minutes=cada):
                ultima = datetime.now(timezone.utc)
                ejecutar_sincronizacion()

    hilo = threading.Thread(target=ciclo, name="sync-glpi", daemon=True)
    hilo.start()
    return hilo
