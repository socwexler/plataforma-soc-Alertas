from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auditoria import aplicar, eliminar, registrar
from ..db import get_db
from ..models import Auditoria, Caso, Importacion, Seguimiento, Usuario
from ..schemas import EstadoIn, UsuarioIn, UsuarioMini, UsuarioOut
from ..security import hash_password, requiere, tiene, usuario_actual

router = APIRouter(prefix="/api/usuarios", tags=["usuarios"])


def _usos(db: Session, uid: int | None = None) -> dict[int, str]:
    """Historial de cada usuario: con él no se puede eliminar, solo deshabilitar."""
    partes: dict[int, list[str]] = {}
    for col, uno, varios in ((Caso.analista_id, "caso", "casos"), (Seguimiento.autor_id, "seguimiento", "seguimientos"),
                             (Importacion.usuario_id, "importación", "importaciones")):
        q = select(col, func.count()).where(col.is_not(None)).group_by(col)
        for i, n in db.execute(q.where(col == uid) if uid else q):
            partes.setdefault(i, []).append(f"{n} {uno if n == 1 else varios}")
    return {i: ", ".join(p) for i, p in partes.items()}


def _out(u: Usuario, uso: str | None = None) -> UsuarioOut:
    return UsuarioOut.model_validate(u).model_copy(update={"puede_ingresar": bool(u.password_hash), "uso": uso})


def _objeto(u: Usuario) -> str:
    return f"el usuario {u.nombre} ({u.usuario})"


def _proteger_admin(yo: Usuario, *roles: str):
    """El Líder administra usuarios, pero no crea, modifica ni nombra administradores."""
    if "ADMIN" in roles and not tiene(yo, "sistema.admin"):
        raise HTTPException(403, "Solo un administrador puede gestionar a los administradores")


@router.get("/analistas", response_model=list[UsuarioMini])
def analistas(db: Session = Depends(get_db), _=Depends(usuario_actual)):
    """Lista corta para filtros (incluye analistas históricos sin acceso)."""
    return db.scalars(select(Usuario).order_by(Usuario.nombre)).all()


@router.get("", response_model=list[UsuarioOut])
def listar(db: Session = Depends(get_db), _=Depends(requiere("usuarios.admin"))):
    usos = _usos(db)
    return [_out(u, usos.get(u.id)) for u in db.scalars(select(Usuario).order_by(Usuario.activo.desc(), Usuario.nombre))]


@router.post("", response_model=UsuarioOut, status_code=201)
def crear(datos: UsuarioIn, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("usuarios.admin"))):
    _proteger_admin(yo, datos.rol)
    if db.scalar(select(Usuario).where(func.lower(Usuario.usuario) == datos.usuario.lower())):
        raise HTTPException(409, "Ese nombre de usuario ya existe")
    u = Usuario(**datos.model_dump(exclude={"password"}))
    if datos.password:
        u.password_hash = hash_password(datos.password)
    db.add(u)
    registrar(db, yo, "crear", _objeto(u), f"rol {u.rol}" + ("" if u.password_hash else ", sin contraseña"))
    db.commit()
    return _out(u)


@router.put("/{uid}", response_model=UsuarioOut)
def editar(uid: int, datos: UsuarioIn, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("usuarios.admin"))):
    u = db.get(Usuario, uid) or _404()
    _proteger_admin(yo, u.rol, datos.rol)
    otro = db.scalar(select(Usuario).where(func.lower(Usuario.usuario) == datos.usuario.lower(), Usuario.id != uid))
    if otro:
        raise HTTPException(409, "Ese nombre de usuario ya existe")
    if u.id == yo.id and (datos.rol != u.rol or not datos.activo):
        raise HTTPException(400, "No puede cambiar su propio rol ni desactivarse")
    cambios = aplicar(u, datos.model_dump(exclude={"password"}))
    if datos.password:
        u.password_hash = hash_password(datos.password)
        cambios = "; ".join(x for x in (cambios, "contraseña cambiada") if x)
    if cambios:
        registrar(db, yo, "editar", _objeto(u), cambios)
    db.commit()
    return _out(u, _usos(db, uid).get(uid))


@router.patch("/{uid}/estado", response_model=UsuarioOut)
def cambiar_estado(uid: int, datos: EstadoIn, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("usuarios.admin"))):
    """Deshabilitado no puede ingresar y su sesión abierta deja de funcionar; sus casos no cambian."""
    u = db.get(Usuario, uid) or _404()
    _proteger_admin(yo, u.rol)
    if u.id == yo.id:
        raise HTTPException(400, "No puede deshabilitarse a sí mismo")
    if u.activo != datos.activo:
        u.activo = datos.activo
        registrar(db, yo, "habilitar" if u.activo else "deshabilitar", _objeto(u))
        db.commit()
    return _out(u, _usos(db, uid).get(uid))


@router.delete("/{uid}", status_code=204)
def borrar(uid: int, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("usuarios.admin"))):
    u = db.get(Usuario, uid) or _404()
    _proteger_admin(yo, u.rol)
    if u.id == yo.id:
        raise HTTPException(400, "No puede eliminarse a sí mismo")
    eliminar(db, yo, u, _objeto(u), _usos(db, uid).get(uid))


@router.get("/cambios")
def cambios(pagina: int = 1, q: str | None = None, db: Session = Depends(get_db), _=Depends(requiere("usuarios.admin"))):
    """Registro de cambios administrativos, del más reciente al más antiguo. Solo lectura."""
    f = []
    if q and q.strip():
        p = f"%{q.strip()}%"
        f.append(Auditoria.usuario.ilike(p) | Auditoria.objeto.ilike(p) | Auditoria.detalle.ilike(p))
    filas = db.scalars(select(Auditoria).where(*f).order_by(Auditoria.id.desc()).offset((max(pagina, 1) - 1) * 50).limit(50))
    return {"total": db.scalar(select(func.count()).select_from(Auditoria).where(*f)),
            "items": [{"id": a.id, "usuario": a.usuario, "accion": a.accion, "objeto": a.objeto, "detalle": a.detalle,
                       "creado_en": a.creado_en} for a in filas]}


def _404():
    raise HTTPException(404, "Usuario no encontrado")
