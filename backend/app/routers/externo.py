"""Consulta de solo lectura para otros sistemas (Power BI…) con clave de acceso: cabecera X-Api-Key.

Entrega datos operativos del caso, sin análisis, textos ni registros del evento. Los anulados no cuentan.
"""
import hashlib
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import VIGENTE, Caso, ClaveApi, Cliente

router = APIRouter(prefix="/api/externo", tags=["consulta externa"])


def con(permiso: str):
    def _dep(x_api_key: str = Header(""), db: Session = Depends(get_db)) -> ClaveApi:
        k = db.scalar(select(ClaveApi).where(ClaveApi.huella == hashlib.sha256(x_api_key.encode()).hexdigest())) if x_api_key.startswith("soc_") else None
        ahora = datetime.now(timezone.utc)
        if not k or k.revocada_en or k.vence_en <= ahora:
            raise HTTPException(401, "Clave de acceso inválida, vencida o revocada")
        if permiso not in k.permisos:
            raise HTTPException(403, "La clave no tiene permiso para esta consulta")
        if not k.ultimo_uso or k.ultimo_uso < ahora - timedelta(minutes=1):
            k.ultimo_uso = ahora
            db.commit()
        return k
    return _dep


def _filtros(k: ClaveApi, desde: date | None, hasta: date | None, cliente: str | None, servicio: str | None) -> list:
    f = [VIGENTE]
    if k.cliente_id:
        f.append(Caso.cliente_id == k.cliente_id)
    if desde:
        f.append(Caso.fecha_bitacora >= desde)
    if hasta:
        f.append(Caso.fecha_bitacora <= hasta)
    if cliente:
        f.append(Caso.cliente.has(func.lower(Cliente.codigo) == cliente.strip().lower()))
    if servicio:
        f.append(Caso.servicio == servicio.upper())
    return f


@router.get("/casos")
def casos(desde: date | None = None, hasta: date | None = None, cliente: str | None = None, servicio: str | None = None,
          pagina: int = 1, tamano: int = 200, db: Session = Depends(get_db), k: ClaveApi = Depends(con("casos"))):
    f, tamano = _filtros(k, desde, hasta, cliente, servicio), max(1, min(tamano, 500))
    filas = db.scalars(select(Caso).where(*f).order_by(Caso.id).offset((max(pagina, 1) - 1) * tamano).limit(tamano)).unique()
    return {"total": db.scalar(select(func.count()).select_from(Caso).where(*f)), "pagina": max(pagina, 1), "items": [{
        "numero": c.numero, "servicio": c.servicio, "cliente": c.cliente.codigo, "fecha": c.fecha_bitacora, "alerta": c.alerta,
        "criticidad": c.criticidad, "tactica": c.tactica.nombre if c.tactica else None, "tecnica": c.tecnica, "estado": c.estado,
        "fecha_evento": c.fecha_evento, "fecha_reporte": c.fecha_reporte, "minutos_reporte": c.minutos_respuesta,
        "analista": c.analista.nombre if c.analista else None, "ticket_glpi": c.glpi_ticket_id} for c in filas]}


@router.get("/resumen")
def resumen(desde: date, hasta: date, cliente: str | None = None, servicio: str | None = None,
            db: Session = Depends(get_db), k: ClaveApi = Depends(con("resumen"))):
    if hasta < desde or (hasta - desde).days > 400:
        raise HTTPException(422, "El rango debe ser de hasta 400 días")
    f = _filtros(k, desde, hasta, cliente, servicio)
    por = lambda col: {(x or "Sin dato"): n for x, n in db.execute(select(col, func.count()).where(*f).group_by(col))}  # noqa: E731
    return {"desde": desde, "hasta": hasta, "total": db.scalar(select(func.count()).select_from(Caso).where(*f)),
            "por_criticidad": por(Caso.criticidad), "por_estado": por(Caso.estado), "por_servicio": por(Caso.servicio),
            "por_dia": {d.isoformat(): n for d, n in db.execute(select(Caso.fecha_bitacora, func.count()).where(*f).group_by(Caso.fecha_bitacora).order_by(Caso.fecha_bitacora))},
            "por_cliente": {c: n for c, n in db.execute(select(Cliente.codigo, func.count()).join(Caso, Caso.cliente_id == Cliente.id).where(*f).group_by(Cliente.codigo))}}
