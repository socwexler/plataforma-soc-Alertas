"""Importación de bitácoras Excel desde la interfaz web (con simulación previa e historial)."""
import json
import logging
import re
import shutil
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..importacion import MODOS, ErrorImportacion, describir_archivo, importar
from ..models import Importacion, Usuario
from ..security import requiere

router = APIRouter(prefix="/api/importaciones", tags=["importaciones"])
log = logging.getLogger("uvicorn.error")

CARPETA = Path("/tmp/importaciones")
MAX_BYTES = 50 * 1024 * 1024
VIGENCIA_SEG = 24 * 3600
LOCK_ID = 7_240_001  # candado para que no corran dos importaciones a la vez


def _limpiar_viejos():
    CARPETA.mkdir(parents=True, exist_ok=True)
    limite = time.time() - VIGENCIA_SEG
    for f in CARPETA.iterdir():
        if f.stat().st_mtime < limite:
            f.unlink(missing_ok=True)


def _ruta(archivo_id: str) -> tuple[Path, dict]:
    if not re.fullmatch(r"[0-9a-f]{32}", archivo_id):
        raise HTTPException(400, "Identificador de archivo no válido")
    ruta = CARPETA / f"{archivo_id}.xlsx"
    meta = CARPETA / f"{archivo_id}.json"
    if not ruta.exists():
        raise HTTPException(410, "El archivo ya no está disponible; vuelva a cargarlo")
    return ruta, json.loads(meta.read_text(encoding="utf-8"))


@router.post("/archivo")
def subir(archivo: UploadFile, _=Depends(requiere("importar"))):
    """Recibe el Excel, lo guarda temporalmente y devuelve sus hojas."""
    nombre = Path(archivo.filename or "bitacora.xlsx").name
    if not nombre.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(415, "Solo se aceptan archivos Excel .xlsx o .xlsm")
    _limpiar_viejos()
    aid = uuid.uuid4().hex
    ruta = CARPETA / f"{aid}.xlsx"
    with ruta.open("wb") as destino:
        shutil.copyfileobj(archivo.file, destino, length=1024 * 1024)
    if ruta.stat().st_size > MAX_BYTES:
        ruta.unlink(missing_ok=True)
        raise HTTPException(413, "El archivo supera 50 MB")
    try:
        hojas = describir_archivo(str(ruta))
    except Exception:
        ruta.unlink(missing_ok=True)
        raise HTTPException(422, "No se pudo leer el archivo. Verifique que sea un Excel válido y que no tenga contraseña.")
    (CARPETA / f"{aid}.json").write_text(json.dumps({"nombre": nombre}), encoding="utf-8")
    return {"archivo_id": aid, "nombre": nombre, "tamano": ruta.stat().st_size, "hojas": hojas}


class SolicitudImportacion(BaseModel):
    archivo_id: str
    hoja: str
    modo: str = "solo_nuevos"
    servicio: str | None = None
    simular: bool = True
    cargar_catalogos: bool = True


def _registrar(db: Session, s: SolicitudImportacion, nombre: str, yo: Usuario, exito: bool, mensaje: str | None,
               resultado: dict | None) -> int:
    reg = Importacion(archivo=nombre, hoja=s.hoja, modo=s.modo, simulacion=s.simular, exito=exito, mensaje=mensaje,
                      resultado=resultado, usuario_id=yo.id, usuario_nombre=yo.nombre)
    db.add(reg)
    db.commit()
    return reg.id


@router.post("")
def ejecutar(s: SolicitudImportacion, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("importar"))):
    if s.modo not in MODOS:
        raise HTTPException(422, f"Modo no válido. Opciones: {', '.join(MODOS)}")
    if s.servicio not in (None, "SOC", "NOC"):
        raise HTTPException(422, "Servicio no válido")
    ruta, meta = _ruta(s.archivo_id)

    if not db.scalar(select(func.pg_try_advisory_xact_lock(LOCK_ID))):
        raise HTTPException(409, "Ya hay una importación en curso; intente en unos minutos")
    try:
        resultado = importar(db, str(ruta), s.hoja, s.servicio, s.modo, s.cargar_catalogos)
    except ErrorImportacion as e:
        db.rollback()
        _registrar(db, s, meta["nombre"], yo, False, str(e), None)
        raise HTTPException(422, str(e))
    except Exception as e:  # error inesperado: no dejar nada a medias
        db.rollback()
        log.exception("Error importando %s", meta["nombre"])
        _registrar(db, s, meta["nombre"], yo, False, f"Error inesperado: {e}", None)
        raise HTTPException(500, "Error inesperado durante la importación; no se guardó ningún cambio")

    if s.simular:
        db.rollback()
    else:
        db.commit()
        log.info("Importación de %s por %s: %s", meta["nombre"], yo.usuario, resultado["resumen"])
    resultado["id"] = _registrar(db, s, meta["nombre"], yo, True, None, resultado)
    resultado["simulacion"] = s.simular
    resultado["archivo"] = meta["nombre"]
    return resultado


@router.get("")
def historial(db: Session = Depends(get_db), _=Depends(requiere("importar"))):
    regs = db.scalars(select(Importacion).order_by(Importacion.creado_en.desc()).limit(50)).all()
    return [{
        "id": r.id, "archivo": r.archivo, "hoja": r.hoja, "modo": r.modo, "simulacion": r.simulacion,
        "exito": r.exito, "mensaje": r.mensaje, "usuario": r.usuario_nombre, "creado_en": r.creado_en,
        "resumen": (r.resultado or {}).get("resumen"),
    } for r in regs]


@router.get("/{iid}")
def detalle(iid: int, db: Session = Depends(get_db), _=Depends(requiere("importar"))):
    r = db.get(Importacion, iid)
    if not r:
        raise HTTPException(404, "Importación no encontrada")
    return {**(r.resultado or {}), "id": r.id, "archivo": r.archivo, "simulacion": r.simulacion, "exito": r.exito,
            "mensaje": r.mensaje, "usuario": r.usuario_nombre, "creado_en": r.creado_en}
