"""Métricas de casos para el informe: periodo actual y los dos anteriores."""
from collections import Counter, defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import VIGENTE, Caso, Cliente, Tactica
from .periodos import etiqueta, etiqueta_corta, ultimos

TZ = ZoneInfo(settings.zona_horaria)
CRITICIDADES = ["Crítica", "Alta", "Media", "Baja"]
MINUTOS = func.extract("epoch", Caso.fecha_reporte - Caso.fecha_evento) / 60
CON_TIEMPO = Caso.fecha_reporte.is_not(None) & Caso.fecha_evento.is_not(None)


def _rango(ini: date, fin: date):
    return (Caso.fecha_bitacora >= ini, Caso.fecha_bitacora <= fin)


def _periodo(db: Session, base: list, ini: date, fin: date) -> dict:
    F = [*base, *_rango(ini, fin)]
    total, con_retro, mediana, con_tiempo, dentro = db.execute(select(
        func.count(), func.count().filter(Caso.estado != "SIN_RETRO"),
        func.percentile_cont(0.5).within_group(MINUTOS).filter(CON_TIEMPO),
        func.count().filter(CON_TIEMPO), func.count().filter(CON_TIEMPO & (MINUTOS <= settings.sla_minutos)),
    ).where(*F)).one()
    crit = dict(db.execute(select(Caso.criticidad, func.count()).where(*F).group_by(Caso.criticidad)).all())
    tac = {(nombre or "Sin táctica"): cuenta for nombre, cuenta in db.execute(
        select(Tactica.nombre, func.count())
        .select_from(Caso).outerjoin(Tactica, Tactica.id == Caso.tactica_id).where(*F)
        .group_by(Tactica.nombre)).all()}
    return {
        "inicio": ini.isoformat(), "fin": fin.isoformat(), "etiqueta": etiqueta(ini, fin), "corta": etiqueta_corta(ini, fin),
        "total": total, "criticidad": {c: crit.get(c, 0) for c in CRITICIDADES},
        "con_retro": con_retro, "sin_retro": total - con_retro,
        "mediana_minutos": round(mediana) if mediana is not None else None,
        "con_tiempo": con_tiempo, "dentro_sla": dentro, "tacticas": tac,
    }


def calcular(db: Session, cliente: Cliente, inicio: date) -> dict:
    periodos = ultimos(inicio, cliente.dia_corte, 3)
    ini_actual, fin_actual = periodos[-1]
    servicios = {}
    for servicio in ("SOC", "NOC"):
        base = [VIGENTE, Caso.cliente_id == cliente.id, Caso.servicio == servicio]
        contratado = cliente.servicio_soc if servicio == "SOC" else cliente.servicio_noc
        hay = db.scalar(select(func.count()).select_from(Caso).where(*base, *_rango(periodos[0][0], fin_actual)))
        if not contratado and not hay:
            continue
        filas = [_periodo(db, base, i, f) for i, f in periodos]

        F = [*base, *_rango(ini_actual, fin_actual)]
        por_alerta = defaultdict(Counter)
        for alerta, crit, n in db.execute(
                select(Caso.alerta, Caso.criticidad, func.count()).where(*F).group_by(Caso.alerta, Caso.criticidad)):
            por_alerta[alerta][crit or "Sin"] += n
        top = sorted(por_alerta.items(), key=lambda kv: -sum(kv[1].values()))[:10]
        top_alertas = [{"alerta": a, "total": sum(c.values()), "criticidad": c.most_common(1)[0][0],
                        "por_criticidad": dict(c)} for a, c in top]
        destacados = [{
            "numero": c.numero, "fecha": c.fecha_evento.astimezone(TZ).strftime("%d/%m/%Y %H:%M") if c.fecha_evento else "",
            "alerta": c.alerta, "criticidad": c.criticidad, "estado": c.estado, "glpi": c.glpi_ticket_id,
        } for c in db.scalars(select(Caso).where(*F, Caso.criticidad.in_(["Crítica", "Alta"]))
                              .order_by(Caso.fecha_evento).limit(20)).unique()]

        nombres_tac = sorted({t for p in filas for t in p["tacticas"]}, key=lambda t: -filas[-1]["tacticas"].get(t, 0))
        servicios[servicio] = {
            "periodos": filas,
            "top_alertas": top_alertas,
            "destacados": destacados,
            "tacticas": [{"tactica": t, "valores": [p["tacticas"].get(t, 0) for p in filas]} for t in nombres_tac],
        }
    return {
        "periodos": [{"inicio": i.isoformat(), "fin": f.isoformat(), "etiqueta": etiqueta(i, f),
                      "corta": etiqueta_corta(i, f)} for i, f in periodos],
        "sla_minutos": settings.sla_minutos,
        "servicios": servicios,
        "calculado_en": datetime.now(TZ).isoformat(timespec="minutes"),
    }
