import logging
import threading
from pathlib import Path

from fastapi import FastAPI
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select

from .config import settings
from .db import SessionLocal, engine
from .models import Consecutivo, Tactica, Usuario
from .normalizacion import TACTICAS
from . import alertas, avisos, configuracion as cfg, glpi
from .routers import alertas as alertas_api, auth, casos, casos_uso, clientes, configuracion, externo, glpi_api, importaciones, informes, tablero, usuarios
from .security import hash_password

log = logging.getLogger("uvicorn.error")

app = FastAPI(title="Plataforma SOC/NOC Wexler", docs_url="/api/docs", openapi_url="/api/openapi.json")
for r in (alertas_api, auth, usuarios, clientes, casos_uso, casos, importaciones, glpi_api, tablero, informes, configuracion, externo):
    app.include_router(r.router)


def migrar_esquema():
    raiz = Path(__file__).resolve().parent.parent
    cfg = Config(str(raiz / "alembic.ini"))
    cfg.set_main_option("script_location", str(raiz / "migraciones"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        insp = inspect(conn)
        if insp.has_table("casos") and not insp.has_table("alembic_version"):
            # Base creada en la fase 1 sin Alembic: se marca como versión inicial
            command.stamp(cfg, "0001")
            log.info("Esquema existente marcado como versión 0001")
        command.upgrade(cfg, "head")


def inicializar():
    """Aplica migraciones pendientes y crea los datos base. Es idempotente."""
    migrar_esquema()
    with SessionLocal() as db:
        for orden, (tid, es, en) in enumerate(TACTICAS):
            t = db.get(Tactica, tid) or Tactica(id=tid)
            t.nombre, t.nombre_en, t.orden = es, en, orden
            db.merge(t)
        for s in ("SOC", "NOC"):
            if not db.get(Consecutivo, s):
                db.add(Consecutivo(servicio=s, ultimo=0))
        # Solo en la instalación: si ya hay un administrador no se vuelve a crear (pudo renombrarse o eliminarse a propósito)
        if settings.admin_password and not db.scalar(select(Usuario).where(Usuario.rol == "ADMIN").limit(1)):
            db.add(Usuario(usuario=settings.admin_usuario, nombre="Administrador", rol="ADMIN",
                           password_hash=hash_password(settings.admin_password)))
            log.info("Usuario administrador '%s' creado", settings.admin_usuario)
        db.commit()


_parar = threading.Event()


@app.on_event("startup")
def _startup():
    inicializar()
    with SessionLocal() as db:
        cfg.cargar(db)
    glpi.iniciar_sincronizacion_periodica(_parar)
    alertas.iniciar(_parar)
    avisos.iniciar(_parar)


@app.on_event("shutdown")
def _shutdown():
    _parar.set()


@app.get("/api/salud")
def salud():
    return {"ok": True}
