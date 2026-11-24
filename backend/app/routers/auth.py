from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Usuario
from ..schemas import CambioClave, UsuarioOut
from ..security import PERMISOS, crear_token, hash_password, usuario_actual, verificar_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    u = db.scalar(select(Usuario).where(func.lower(Usuario.usuario) == form.username.strip().lower()))
    if not u or not u.activo or not verificar_password(form.password, u.password_hash):
        raise HTTPException(401, "Usuario o contraseña incorrectos")
    return {"access_token": crear_token(u), "token_type": "bearer"}


@router.get("/yo", response_model=UsuarioOut)
def yo(u: Usuario = Depends(usuario_actual)):
    return UsuarioOut.model_validate(u).model_copy(update={"puede_ingresar": True, "permisos": sorted(PERMISOS[u.rol])})


@router.post("/cambiar-clave", status_code=204)
def cambiar_clave(datos: CambioClave, u: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    if not verificar_password(datos.actual, u.password_hash):
        raise HTTPException(400, "La contraseña actual no es correcta")
    u.password_hash = hash_password(datos.nueva)
    db.merge(u)
    db.commit()
