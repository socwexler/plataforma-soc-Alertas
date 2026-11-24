from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import adjuntos, correo, imagenes
from ..auditoria import aplicar, eliminar, registrar
from ..db import get_db
from ..models import Caso, Cliente, Informe, Usuario
from ..schemas import ClienteIn, ClienteOut, CorreosIn, EstadoIn
from ..security import requiere, usuario_actual

router = APIRouter(prefix="/api/clientes", tags=["clientes"])


@router.get("", response_model=list[ClienteOut])
def listar(solo_activos: bool = False, db: Session = Depends(get_db), _=Depends(usuario_actual)):
    q = select(Cliente).order_by(Cliente.codigo)
    if solo_activos:
        q = q.where(Cliente.activo)
    usos = _usos(db)
    return [ClienteOut.model_validate(c).model_copy(update={"uso": usos.get(c.id)}) for c in db.scalars(q)]


def _usos(db: Session, cid: int | None = None) -> dict[int, str]:
    partes: dict[int, list[str]] = {}
    for col, uno, varios in ((Caso.cliente_id, "caso", "casos"), (Informe.cliente_id, "informe", "informes")):
        q = select(col, func.count()).group_by(col)
        for i, n in db.execute(q.where(col == cid) if cid else q):
            partes.setdefault(i, []).append(f"{n} {uno if n == 1 else varios}")
    return {i: ", ".join(p) for i, p in partes.items()}


@router.post("", response_model=ClienteOut, status_code=201)
def crear(datos: ClienteIn, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("clientes.admin"))):
    if db.scalar(select(Cliente).where(func.lower(Cliente.codigo) == datos.codigo.lower())):
        raise HTTPException(409, "Ya existe un cliente con ese código")
    c = Cliente(**datos.model_dump())
    db.add(c)
    registrar(db, yo, "crear", f"el cliente {c.etiqueta}")
    db.commit()
    return c


@router.put("/{cid}", response_model=ClienteOut)
def editar(cid: int, datos: ClienteIn, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("clientes.admin"))):
    c = db.get(Cliente, cid)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    if db.scalar(select(Cliente).where(func.lower(Cliente.codigo) == datos.codigo.lower(), Cliente.id != cid)):
        raise HTTPException(409, "Ya existe un cliente con ese código")
    cambios = aplicar(c, datos.model_dump(), {"activo": "activo", "dia_corte": "día de corte", "codigo": "código"})
    if cambios:
        registrar(db, yo, "editar", f"el cliente {c.etiqueta}", cambios)
    db.commit()
    return c


@router.patch("/{cid}/estado", response_model=ClienteOut)
def cambiar_estado(cid: int, datos: EstadoIn, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("clientes.admin"))):
    """Deshabilitado no recibe casos, informes ni correos nuevos; lo que ya tiene se conserva."""
    c = db.get(Cliente, cid)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    if c.activo != datos.activo:
        c.activo = datos.activo
        registrar(db, yo, "habilitar" if c.activo else "deshabilitar", f"el cliente {c.etiqueta}")
        db.commit()
    return c


@router.delete("/{cid}", status_code=204)
def borrar(cid: int, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("clientes.admin"))):
    c = db.get(Cliente, cid)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    eliminar(db, yo, c, f"el cliente {c.etiqueta}", _usos(db, cid).get(cid))


# ------------------------------------------------------------------ logo
def _cliente(db: Session, cid: int) -> Cliente:
    c = db.get(Cliente, cid)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    return c


@router.get("/{cid}/logo")
def ver_logo(cid: int, db: Session = Depends(get_db), _=Depends(usuario_actual)):
    c = _cliente(db, cid)
    if not c.tiene_logo:
        raise HTTPException(404, "El cliente no tiene logo")
    return Response(c.logo, media_type=c.logo_mime, headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store",
                                                             "Content-Security-Policy": "default-src 'none'; sandbox"})


@router.put("/{cid}/logo", response_model=ClienteOut)
def guardar_logo(cid: int, archivo: UploadFile, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("clientes.admin"))):
    c = _cliente(db, cid)
    try:
        d = imagenes.preparar(archivo.filename, archivo.file.read(5 * adjuntos.MB + 1), logo=True)
    except adjuntos.ErrorAdjunto as e:
        raise HTTPException(422, str(e))
    registrar(db, yo, "editar", f"el logo del cliente {c.etiqueta}", "logo reemplazado" if c.tiene_logo else "logo cargado")
    c.logo, c.logo_mime, c.logo_claro = d["contenido"], d["mime"], d["claro"]
    db.commit()
    return c


@router.delete("/{cid}/logo", response_model=ClienteOut)
def quitar_logo(cid: int, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("clientes.admin"))):
    c = _cliente(db, cid)
    if c.tiene_logo:
        c.logo = c.logo_mime = c.logo_claro = None
        registrar(db, yo, "editar", f"el logo del cliente {c.etiqueta}", "logo eliminado")
        db.commit()
    return c


def _correos(c: Cliente) -> dict:
    return {"para": c.correos_para or [], "cc": c.correos_cc or [], "dominios": c.correos_dominios or [],
            "por": c.correos_por, "en": c.correos_en, "cc_fijo": correo.settings.correo_cc, "cco_fijo": correo.settings.correo_cco}


@router.get("/{cid}/correos")
def ver_correos(cid: int, db: Session = Depends(get_db), _=Depends(requiere("clientes.admin"))):
    c = db.get(Cliente, cid)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    return _correos(c)


@router.put("/{cid}/correos")
def guardar_correos(cid: int, datos: CorreosIn, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("clientes.admin"))):
    """Destinatarios del correo de alerta. Solo direcciones de los dominios del cliente (o propios)."""
    c = db.get(Cliente, cid)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    try:
        para, cc, dominios = correo.leer_correos(datos.para), correo.leer_correos(datos.cc), correo.leer_dominios(datos.dominios)
        cc = [x for x in cc if x not in para]
        correo.validar_cliente(db, c, para, cc, dominios)
    except correo.ErrorCorreo as e:
        raise HTTPException(422, str(e))
    antes = (c.correos_para or [], c.correos_cc or [], c.correos_dominios or [])
    if antes != (para, cc, dominios):
        detalle = []
        for nombre, a, b in zip(("Para", "CC", "dominios"), antes, (para, cc, dominios)):
            mas, menos = [x for x in b if x not in a], [x for x in a if x not in b]
            detalle += [f"{nombre} agrega {', '.join(mas)}"] * bool(mas) + [f"{nombre} quita {', '.join(menos)}"] * bool(menos)
        registrar(db, yo, "editar", f"los correos del cliente {c.etiqueta}", "; ".join(detalle) or "cambio de orden")
    c.correos_para, c.correos_cc, c.correos_dominios = para, cc, dominios
    c.correos_por, c.correos_en = yo.nombre, datetime.now(timezone.utc)
    db.commit()
    return _correos(c)
