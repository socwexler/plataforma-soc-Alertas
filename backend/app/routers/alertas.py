"""Bandeja «Alertas por tratar»: tickets que el SIEM crea en GLPI y que se deben reportar al cliente."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import alertas
from ..db import get_db
from ..glpi import ErrorGLPI
from ..models import Alerta, Usuario
from ..schemas import AlertaDetalle, AlertaOut
from ..security import requiere, tiene, usuario_actual

router = APIRouter(prefix="/api/alertas", tags=["alertas"])

VISTAS = {"pendientes": alertas.PENDIENTES, "reportadas": ("REPORTADA",), "cerradas": ("CERRADA_GLPI",)}


def _salida(a: Alerta, modelo=AlertaOut, ahora: datetime | None = None):
    ahora = ahora or datetime.now(timezone.utc)
    fin = a.reportada_en or a.cerrada_en or (ahora if a.estado in alertas.PENDIENTES else None)
    minutos = int((fin - a.fecha_alerta).total_seconds() // 60) if fin else None
    return modelo.model_validate(a).model_copy(update={"minutos": max(minutos, 0) if minutos is not None else None})


@router.get("")
def listar(vista: Literal["pendientes", "reportadas", "cerradas", "todas"] = "pendientes", cliente_id: int | None = None,
           q: str | None = None, pagina: int = 1, tamano: int = 50, db: Session = Depends(get_db), _=Depends(usuario_actual)):
    f = []
    if vista in VISTAS:
        f.append(Alerta.estado.in_(VISTAS[vista]))
    if cliente_id:
        f.append(Alerta.cliente_id == cliente_id)
    if q and q.strip():
        t = q.strip()
        f.append(or_(Alerta.titulo.ilike(f"%{t}%"), *([Alerta.glpi_ticket_id == int(t)] if t.isdigit() and len(t) < 10 else [])))
    orden = Alerta.fecha_alerta.asc() if vista == "pendientes" else Alerta.fecha_alerta.desc()
    total = db.scalar(select(func.count()).select_from(Alerta).where(*f))
    filas = db.scalars(select(Alerta).where(*f).order_by(orden, Alerta.id)
                       .offset((max(pagina, 1) - 1) * tamano).limit(min(max(tamano, 1), 200))).unique().all()
    ahora = datetime.now(timezone.utc)
    pend = db.scalars(select(Alerta).where(Alerta.estado.in_(alertas.PENDIENTES))).unique().all()
    return {
        "total": total,
        "items": [_salida(a, ahora=ahora) for a in filas],
        "resumen": {
            "por_reportar": sum(a.estado == "POR_REPORTAR" for a in pend),
            "en_gestion": sum(a.estado == "EN_GESTION" for a in pend),
            "vencidas": sum((ahora - a.fecha_alerta).total_seconds() > a.sla_minutos * 60 for a in pend),
            "sin_cliente": sum(a.cliente_id is None for a in pend),
        },
        "integracion": alertas.estado(),
    }


@router.get("/estado")
def estado(_=Depends(usuario_actual)):
    return alertas.estado()


@router.post("/traer")
def traer(db: Session = Depends(get_db), _=Depends(requiere("casos.crear"))):
    """Busca ahora en GLPI (además de la búsqueda periódica)."""
    try:
        r = alertas.traer(db)
    except ErrorGLPI as e:
        db.rollback()
        raise HTTPException(400 if "no está" in str(e) else 502, str(e))
    alertas._estado.update(ultima=datetime.now(timezone.utc), resultado=r, error=None)
    return r


def _alerta(db: Session, aid: int, bloquear: bool = False) -> Alerta:
    a = db.get(Alerta, aid, with_for_update={"of": Alerta} if bloquear else None)
    if not a:
        raise HTTPException(404, "Alerta no encontrada")
    return a


@router.get("/{aid}", response_model=AlertaDetalle)
def obtener(aid: int, db: Session = Depends(get_db), _=Depends(usuario_actual)):
    return _salida(_alerta(db, aid), AlertaDetalle)


@router.post("/{aid}/tomar", response_model=AlertaOut)
def tomar(aid: int, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("casos.crear"))):
    """El analista la toma: los demás ven quién la está reportando."""
    a = _alerta(db, aid, True)
    if a.estado == "EN_GESTION" and a.analista_id == yo.id:
        return _salida(a)
    if a.estado == "EN_GESTION":
        raise HTTPException(409, f"La está gestionando {a.analista.nombre if a.analista else 'otro analista'}")
    if a.estado != "POR_REPORTAR":
        raise HTTPException(409, "Esta alerta ya no está por reportar")
    a.estado, a.analista_id, a.tomada_en = "EN_GESTION", yo.id, datetime.now(timezone.utc)
    db.commit()
    db.expire_all()
    return _salida(_alerta(db, aid))


@router.post("/{aid}/liberar", response_model=AlertaOut)
def liberar(aid: int, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("casos.crear"))):
    """La devuelve a «Por reportar» (quien la tomó o un revisor, p. ej. al cambiar de turno)."""
    a = _alerta(db, aid, True)
    if a.estado != "EN_GESTION":
        raise HTTPException(409, "La alerta no está en gestión")
    if a.analista_id != yo.id and not tiene(yo, "casos.revisar"):
        raise HTTPException(403, "Solo quien la tomó o un revisor (N2 o superior) pueden liberarla")
    a.estado, a.analista_id, a.tomada_en = "POR_REPORTAR", None, None
    db.commit()
    db.expire_all()
    return _salida(_alerta(db, aid))
