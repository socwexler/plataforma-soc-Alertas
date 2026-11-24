"""Quién creó, modificó, deshabilitó o eliminó usuarios, clientes, casos de uso e informes."""
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Auditoria, Usuario


def registrar(db: Session, yo: Usuario, accion: str, objeto: str, detalle: str | None = None):
    db.add(Auditoria(usuario=f"{yo.nombre} ({yo.usuario})", accion=accion, objeto=objeto[:400], detalle=detalle or None))


def _texto(v) -> str:
    if isinstance(v, bool):
        return "sí" if v else "no"
    t = "vacío" if v in (None, "") else str(v)
    return t if len(t) <= 60 else t[:57] + "…"


def aplicar(obj, datos: dict, etiquetas: dict[str, str] | None = None) -> str:
    """Asigna los campos y devuelve qué cambió, para el registro."""
    cambios = []
    for k, v in datos.items():
        antes = getattr(obj, k)
        if antes != v:
            cambios.append(f"{(etiquetas or {}).get(k, k.replace('_', ' '))}: {_texto(antes)} → {_texto(v)}")
            setattr(obj, k, v)
    return "; ".join(cambios)


def eliminar(db: Session, yo: Usuario, obj, objeto: str, usado: str | None):
    """Solo se elimina lo que no tiene historial; lo demás se deshabilita."""
    if usado:
        raise HTTPException(409, f"No se puede eliminar {objeto}: tiene {usado}. Deshabilítelo para conservar el historial")
    registrar(db, yo, "eliminar", objeto)
    db.delete(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"No se puede eliminar {objeto}: se acaba de usar en otro registro")
