from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Usuario

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Qué puede hacer cada rol. Todos los usuarios activos pueden ver los casos.
_ANALISTA = {"casos.crear", "kb.ver"}
_REVISOR = _ANALISTA | {"casos.revisar", "tablero.ver", "informes.ver", "informes.editar", "kb.editar", "casos.anular"}
_LIDER = _REVISOR | {"informes.cerrar", "clientes.admin", "importar", "usuarios.admin", "kb.eliminar", "config.admin"}
PERMISOS: dict[str, frozenset[str]] = {
    "N1": frozenset(_ANALISTA),
    "N2": frozenset(_REVISOR),
    "N3": frozenset(_REVISOR),
    "LIDER": frozenset(_LIDER),
    "CISO": frozenset({"tablero.ver", "informes.ver"}),
    "ADMIN": frozenset(_LIDER | {"sistema.admin"}),
}


def tiene(u: Usuario, permiso: str) -> bool:
    return permiso in PERMISOS.get(u.rol, frozenset())


def hash_password(clave: str) -> str:
    return bcrypt.hashpw(clave.encode(), bcrypt.gensalt()).decode()


def verificar_password(clave: str, hash_: str | None) -> bool:
    if not hash_:
        return False
    return bcrypt.checkpw(clave.encode(), hash_.encode())


def crear_token(usuario: Usuario) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_horas)
    return jwt.encode({"sub": str(usuario.id), "rol": usuario.rol, "exp": exp}, settings.jwt_secret, "HS256")


def usuario_actual(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> Usuario:
    error = HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida o vencida",
                          headers={"WWW-Authenticate": "Bearer"})
    try:
        datos = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise error
    u = db.get(Usuario, int(datos["sub"]))
    if not u or not u.activo:
        raise error
    return u


def requiere(permiso: str):
    """Dependencia: exige que el rol del usuario tenga el permiso."""
    def _dep(u: Usuario = Depends(usuario_actual)) -> Usuario:
        if not tiene(u, permiso):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No tiene permisos para esta acción")
        return u
    return _dep
