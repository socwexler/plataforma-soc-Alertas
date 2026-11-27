"""Administración: parámetros, conexiones a otras APIs, claves de acceso y estado del sistema."""
import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .. import avisos, configuracion as cfg, glpi
from ..auditoria import aplicar, registrar
from ..config import settings
from ..db import get_db
from ..models import Adjunto, Aviso, Caso, ClaveApi, Cliente, Conexion, Usuario
from ..security import requiere

router = APIRouter(prefix="/api/config", tags=["administración"])
ADMIN = requiere("config.admin")


# ------------------------------------------------------------------ otras APIs
class ConexionIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    url: str = Field(min_length=8, max_length=500)
    autenticacion: Literal["ninguna", "bearer", "cabecera", "basica"] = "cabecera"
    cabecera: str | None = Field(default=None, max_length=60, pattern=r"^[A-Za-z0-9-]*$")
    usuario: str | None = Field(default=None, max_length=120)
    notas: str | None = Field(default=None, max_length=500)
    activo: bool = True
    clave: str | None = Field(default=None, max_length=1000)


def _cx(c: Conexion) -> dict:
    return {"id": c.id, "nombre": c.nombre, "url": c.url, "autenticacion": c.autenticacion, "cabecera": c.cabecera, "usuario": c.usuario,
            "notas": c.notas, "activo": c.activo, "definida": bool(c.clave), "por": c.por, "en": c.en}


def _datos_cx(d: ConexionIn) -> dict:
    v = d.model_dump(exclude={"clave"})
    v["nombre"] = v["nombre"].strip()
    v["url"] = cfg.validar_url(v["url"])
    cfg.validar_host(cfg.urlsplit(v["url"]).hostname)
    if d.autenticacion == "cabecera" and not v["cabecera"]:
        raise cfg.ErrorConfig("Escriba el nombre de la cabecera, por ejemplo x-apikey")
    if d.autenticacion == "cabecera" and v["cabecera"].lower() in {"host", "content-length", "transfer-encoding", "connection", "cookie"}:
        raise cfg.ErrorConfig("Esa cabecera no se puede usar")
    if d.autenticacion == "basica" and not v["usuario"]:
        raise cfg.ErrorConfig("Escriba el usuario")
    if any(x and any(ord(ch) < 32 for ch in x) for x in (v["nombre"], v["usuario"], d.clave)):
        raise cfg.ErrorConfig("Hay caracteres no permitidos")
    return v


def _conexion(db: Session, i: int) -> Conexion:
    c = db.get(Conexion, i)
    if not c:
        raise HTTPException(404, "Conexión no encontrada")
    return c


@router.get("/conexiones")
def conexiones(db: Session = Depends(get_db), _=Depends(ADMIN)):
    return [_cx(c) for c in db.scalars(select(Conexion).order_by(Conexion.nombre))]


@router.post("/conexiones", status_code=201)
def crear_conexion(d: ConexionIn, db: Session = Depends(get_db), yo: Usuario = Depends(ADMIN)):
    try:
        v = _datos_cx(d)
    except cfg.ErrorConfig as e:
        raise HTTPException(422, str(e))
    if db.scalar(select(Conexion).where(func.lower(Conexion.nombre) == v["nombre"].lower())):
        raise HTTPException(409, "Ya existe una conexión con ese nombre")
    c = Conexion(**v, clave=cfg.cifrar(d.clave) if d.clave else None, por=yo.nombre, en=datetime.now(timezone.utc))
    db.add(c)
    registrar(db, yo, "crear", f"la conexión {c.nombre}", f"dirección: {c.url}")
    db.commit()
    return _cx(c)


@router.put("/conexiones/{i}")
def editar_conexion(i: int, d: ConexionIn, db: Session = Depends(get_db), yo: Usuario = Depends(ADMIN)):
    c = _conexion(db, i)
    try:
        v = _datos_cx(d)
    except cfg.ErrorConfig as e:
        raise HTTPException(422, str(e))
    if db.scalar(select(Conexion).where(func.lower(Conexion.nombre) == v["nombre"].lower(), Conexion.id != i)):
        raise HTTPException(409, "Ya existe una conexión con ese nombre")
    if c.clave and not d.clave and cfg.destino(c.url) != cfg.destino(v["url"]):
        raise HTTPException(422, "Cambió el servidor: por seguridad vuelva a escribir la clave")
    cambios = aplicar(c, v)
    if d.clave:
        c.clave = cfg.cifrar(d.clave)
        cambios = "; ".join(x for x in (cambios, "clave reemplazada") if x)
    if cambios:
        c.por, c.en = yo.nombre, datetime.now(timezone.utc)
        registrar(db, yo, "editar", f"la conexión {c.nombre}", cambios)
    db.commit()
    return _cx(c)


@router.delete("/conexiones/{i}", status_code=204)
def borrar_conexion(i: int, db: Session = Depends(get_db), yo: Usuario = Depends(ADMIN)):
    c = _conexion(db, i)
    registrar(db, yo, "eliminar", f"la conexión {c.nombre}")
    db.delete(c)
    db.commit()


def _get(url: str, verificar: bool = True, **kw) -> dict:
    """Consulta de prueba: devuelve solo el código y el tiempo, nunca el contenido ni las claves."""
    t = time.monotonic()
    try:
        with httpx.Client(verify=verificar, timeout=15, follow_redirects=False) as h, h.stream("GET", url, **kw) as r:
            codigo = r.status_code
    except httpx.HTTPError as e:
        raise HTTPException(502, f"No se pudo conectar: {type(e).__name__}")
    except (ValueError, UnicodeError):
        raise HTTPException(422, "La clave o la dirección tienen caracteres no válidos")
    return {"codigo": codigo, "ms": round((time.monotonic() - t) * 1000)}


@router.post("/conexiones/{i}/probar")
def probar_conexion(i: int, db: Session = Depends(get_db), _=Depends(ADMIN)):
    c = _conexion(db, i)
    try:
        cfg.validar_host(cfg.urlsplit(c.url).hostname)
        clave = cfg.descifrar(c.clave) if c.clave else ""
    except cfg.ErrorConfig as e:
        raise HTTPException(422, str(e))
    except cfg.InvalidToken:
        raise HTTPException(422, "La clave guardada ya no se puede leer; escríbala de nuevo")
    kw: dict[str, Any] = {}
    if c.autenticacion == "bearer":
        kw["headers"] = {"Authorization": f"Bearer {clave}"}
    elif c.autenticacion == "cabecera":
        kw["headers"] = {c.cabecera: clave}
    elif c.autenticacion == "basica":
        kw["auth"] = (c.usuario or "", clave)
    return _get(c.url, **kw)


# ------------------------------------------------------------------ claves de acceso a esta plataforma
class ClaveIn(BaseModel):
    nombre: str = Field(min_length=3, max_length=80)
    permisos: list[Literal["casos", "resumen"]] = Field(min_length=1)
    cliente_id: int | None = None
    dias: int = Field(default=180, ge=1, le=365)


def _ck(k: ClaveApi) -> dict:
    ahora = datetime.now(timezone.utc)
    return {"id": k.id, "nombre": k.nombre, "prefijo": k.prefijo, "permisos": k.permisos, "cliente": k.cliente.codigo if k.cliente else None,
            "vence_en": k.vence_en, "revocada_en": k.revocada_en, "ultimo_uso": k.ultimo_uso, "creada_por": k.creada_por, "creado_en": k.creado_en,
            "estado": "Revocada" if k.revocada_en else "Vencida" if k.vence_en <= ahora else "Activa"}


@router.get("/claves")
def claves(db: Session = Depends(get_db), _=Depends(ADMIN)):
    return [_ck(k) for k in db.scalars(select(ClaveApi).order_by(ClaveApi.id.desc()))]


@router.post("/claves", status_code=201)
def crear_clave(d: ClaveIn, db: Session = Depends(get_db), yo: Usuario = Depends(ADMIN)):
    """La clave completa se entrega solo aquí; se guarda su huella."""
    cl = db.get(Cliente, d.cliente_id) if d.cliente_id else None
    if d.cliente_id and not cl:
        raise HTTPException(422, "Cliente no válido")
    clave = "soc_" + secrets.token_urlsafe(32)
    k = ClaveApi(nombre=d.nombre.strip(), prefijo=clave[:10], huella=hashlib.sha256(clave.encode()).hexdigest(),
                 permisos=sorted(set(d.permisos)), cliente_id=d.cliente_id, creada_por=yo.nombre,
                 vence_en=datetime.now(timezone.utc) + timedelta(days=d.dias))
    db.add(k)
    registrar(db, yo, "crear", f"la clave de acceso {k.nombre} ({k.prefijo}…)",
              f"permisos: {', '.join(k.permisos)}; cliente: {cl.codigo if cl else 'todos'}; vence: {k.vence_en:%d/%m/%Y}")
    db.commit()
    return {**_ck(k), "clave": clave}


@router.post("/claves/{i}/revocar")
def revocar_clave(i: int, db: Session = Depends(get_db), yo: Usuario = Depends(ADMIN)):
    k = db.get(ClaveApi, i)
    if not k:
        raise HTTPException(404, "Clave no encontrada")
    if not k.revocada_en:
        k.revocada_en = datetime.now(timezone.utc)
        registrar(db, yo, "deshabilitar", f"la clave de acceso {k.nombre} ({k.prefijo}…)")
        db.commit()
    return _ck(k)


# ------------------------------------------------------------------ avisos y pruebas
class Prueba(BaseModel):
    para: str = Field(max_length=200)


@router.get("/avisos")
def ver_avisos(db: Session = Depends(get_db), _=Depends(ADMIN)):
    cuenta = dict(db.execute(select(Aviso.estado, func.count()).group_by(Aviso.estado)).all())
    return {"cuenta": cuenta, "items": [{"id": a.id, "tipo": a.tipo, "asunto": a.asunto, "estado": a.estado, "intentos": a.intentos, "error": a.error,
                                         "creado_en": a.creado_en, "enviado_en": a.enviado_en}
                                        for a in db.scalars(select(Aviso).order_by(Aviso.id.desc()).limit(50))]}


@router.post("/avisos/reintentar")
def reintentar(db: Session = Depends(get_db), _=Depends(ADMIN)):
    n = 0
    for a in db.scalars(select(Aviso).where(Aviso.estado.in_(("ERROR", "PENDIENTE")))):
        a.estado, a.intentos, a.proximo = "PENDIENTE", 0, datetime.now(timezone.utc)
        n += 1
    db.commit()
    return {"reintentos": n}


@router.post("/avisos/probar")
def probar_avisos(d: Prueba, _=Depends(ADMIN)):
    try:
        avisos.probar(d.para)
    except (avisos.ErrorAviso, avisos.correo.ErrorCorreo) as e:
        raise HTTPException(502, str(e))
    return {"ok": True}


@router.post("/fortisiem/probar")
def probar_fortisiem(_=Depends(ADMIN)):
    if not (settings.fortisiem_url and settings.fortisiem_usuario and settings.fortisiem_clave):
        raise HTTPException(400, "Guarde primero la dirección, el usuario y la contraseña de FortiSIEM")
    r = _get(settings.fortisiem_url.rstrip("/") + "/phoenix/rest/config/Domain", settings.fortisiem_verificar_ssl,
             auth=(f"{settings.fortisiem_organizacion or 'super'}/{settings.fortisiem_usuario}", settings.fortisiem_clave))
    if r["codigo"] in (401, 403):
        raise HTTPException(502, "FortiSIEM respondió, pero rechazó el usuario, la contraseña o el permiso de consulta")
    if r["codigo"] != 200:
        raise HTTPException(502, f"FortiSIEM respondió {r['codigo']}")
    return r


@router.get("/sharepoint/estado")
def estado_sharepoint(_=Depends(ADMIN)):
    """Avance de la configuración, para la guía de pasos (no se conecta a SharePoint)."""
    from .. import sharepoint
    return sharepoint.estado()


@router.post("/sharepoint/probar")
def probar_sharepoint(db: Session = Depends(get_db), _=Depends(ADMIN)):
    """Revisa la conexión y las carpetas de los anexos (solo lectura)."""
    from .. import sharepoint
    try:
        return sharepoint.probar(db.scalars(select(Cliente).where(Cliente.activo).order_by(Cliente.codigo)).all())
    except sharepoint.ErrorSP as e:
        raise HTTPException(400 if "no está activada" in str(e) else 502, str(e))


@router.get("/sistema")
def sistema(db: Session = Depends(get_db), _=Depends(ADMIN)):
    try:
        with httpx.Client(timeout=5) as h:
            conv = h.get("http://convertidor:3000/health").status_code == 200
    except httpx.HTTPError:
        conv = False
    n = lambda *f: db.scalar(select(func.count()).select_from(Caso).where(*f))  # noqa: E731
    return {
        "esquema": db.scalar(text("select version_num from alembic_version")),
        "base_mb": round(db.scalar(text("select pg_database_size(current_database())")) / 1048576, 1),
        "adjuntos_mb": round((db.scalar(select(func.coalesce(func.sum(Adjunto.tamano), 0))) or 0) / 1048576, 1),
        "casos": n(Caso.anulado_en.is_(None)), "casos_anulados": n(Caso.anulado_en.is_not(None)),
        "usuarios_activos": db.scalar(select(func.count()).select_from(Usuario).where(Usuario.activo, Usuario.password_hash.is_not(None))),
        "clientes_sin_correos": db.scalar(select(func.count()).select_from(Cliente).where(Cliente.activo, func.jsonb_array_length(Cliente.correos_para) == 0)),
        "convertidor": conv, "glpi": {k: glpi.estado_integracion()[k] for k in ("activo", "ultima_sincronizacion", "error_sincronizacion")},
        "avisos_activos": bool(settings.avisos_activo and avisos.configurado()),
        "claves_ilegibles": sorted(cfg.ILEGIBLES), "hora": datetime.now(timezone.utc),
    }


# ------------------------------------------------------------------ parámetros (al final: {grupo} es genérico)
class GrupoIn(BaseModel):
    valores: dict[str, Any] = {}
    borrar: list[str] = []


@router.get("")
def ver(db: Session = Depends(get_db), _=Depends(ADMIN)):
    return cfg.listar(db)


@router.put("/{grupo}")
def guardar(grupo: str, d: GrupoIn, db: Session = Depends(get_db), yo: Usuario = Depends(ADMIN)):
    try:
        cfg.guardar(db, yo, grupo, d.valores, d.borrar)
    except cfg.ErrorConfig as e:
        raise HTTPException(422, str(e))
    return cfg.listar(db)


@router.post("/{grupo}/restablecer")
def restablecer(grupo: str, db: Session = Depends(get_db), yo: Usuario = Depends(ADMIN)):
    try:
        cfg.restablecer(db, yo, grupo)
    except cfg.ErrorConfig as e:
        raise HTTPException(422, str(e))
    return cfg.listar(db)
