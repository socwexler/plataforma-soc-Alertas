"""Tablero de la operación: casos por analista, estados, tiempos de reporte y tickets GLPI."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Integer, case, cast, func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import VIGENTE, Caso, Cliente, Usuario
from ..security import requiere
from ..sla import CON_TIEMPO, MINUTOS, dentro, objetivo

router = APIRouter(prefix="/api/tablero", tags=["tablero"])
TZ = ZoneInfo(settings.zona_horaria)

MEDIANA = func.percentile_cont(0.5).within_group(MINUTOS).filter(CON_TIEMPO)
LOCAL = func.timezone(settings.zona_horaria, Caso.fecha_evento)
CRITICIDADES = ["Crítica", "Alta", "Media", "Baja"]
TRAMOS = [(0, 15, "< 15 min"), (15, 30, "15–30 min"), (30, 60, "30–60 min"), (60, 120, "1–2 h"),
          (120, 720, "2–12 h"), (720, None, "> 12 h")]


def _contar(cond):
    return func.count().filter(cond)


def _redondear(v):
    return None if v is None else round(float(v))


@router.get("")
def tablero(
    desde: date | None = None,
    hasta: date | None = None,
    cliente_id: int | None = None,
    servicio: str | None = None,
    analista_id: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(requiere("tablero.ver")),
):
    hoy = datetime.now(TZ).date()
    hasta = hasta or hoy
    desde = desde or (hasta - timedelta(days=29))
    if desde > hasta:
        raise HTTPException(422, "La fecha inicial es posterior a la final")
    if (hasta - desde).days > 400:
        raise HTTPException(422, "El rango máximo es de 400 días")
    dias = (hasta - desde).days + 1

    def filtros(i, f):
        r = [VIGENTE, Caso.fecha_bitacora >= i, Caso.fecha_bitacora <= f]
        if cliente_id:
            r.append(Caso.cliente_id == cliente_id)
        if servicio:
            r.append(Caso.servicio == servicio)
        if analista_id:
            r.append(Caso.analista_id == analista_id)
        return r

    F = filtros(desde, hasta)
    sla = dentro()

    # ---------- indicadores
    k = db.execute(select(
        func.count(),
        _contar(Caso.estado != "SIN_RETRO"),
        MEDIANA,
        _contar(CON_TIEMPO),
        _contar(sla),
        _contar(Caso.criticidad.in_(["Crítica", "Alta"])),
        _contar(Caso.glpi_ticket_id.is_not(None)),
        _contar(Caso.glpi_ticket_id.is_not(None) & (func.coalesce(Caso.glpi_estado, 0) < 5)),
    ).where(*F)).one()
    anterior = db.scalar(select(func.count()).select_from(Caso).where(*filtros(desde - timedelta(days=dias), desde - timedelta(days=1))))
    indicadores = {
        "total": k[0], "con_retro": k[1], "mediana_minutos": _redondear(k[2]), "con_tiempo": k[3],
        "dentro_sla": k[4], "alta_critica": k[5], "con_ticket": k[6], "tickets_abiertos": k[7],
        "total_periodo_anterior": anterior,
    }

    # ---------- cumplimiento del SLA por criticidad
    pc = {r[0]: r for r in db.execute(select(Caso.criticidad, func.count(), _contar(CON_TIEMPO), _contar(sla), MEDIANA).where(*F).group_by(Caso.criticidad))}
    por_sla = [{"criticidad": c, "objetivo": m, "total": pc[c][1] if c in pc else 0, "con_tiempo": pc[c][2] if c in pc else 0,
                "dentro": pc[c][3] if c in pc else 0, "mediana_minutos": _redondear(pc[c][4]) if c in pc else None}
               for c, m in settings.sla_objetivos.items()]

    # ---------- por día y criticidad (hora de Colombia)
    dia = Caso.fecha_bitacora
    filas = db.execute(select(dia, Caso.criticidad, func.count()).where(*F).group_by(dia, Caso.criticidad)).all()
    por_dia = {(desde + timedelta(days=i)).isoformat(): {c: 0 for c in CRITICIDADES + ["Sin"]} for i in range(dias)}
    for d, crit, n in filas:
        por_dia.setdefault(d.isoformat(), {c: 0 for c in CRITICIDADES + ["Sin"]})[crit or "Sin"] += n
    por_dia = [{"dia": d, **v} for d, v in sorted(por_dia.items())]

    # ---------- por analista
    pa = db.execute(
        select(Usuario.id, Usuario.nombre, func.count(), _contar(Caso.criticidad.in_(["Crítica", "Alta"])),
               _contar(Caso.estado != "SIN_RETRO"), MEDIANA, _contar(CON_TIEMPO),
               _contar(sla), _contar(Caso.glpi_ticket_id.is_not(None)),
               func.max(Caso.fecha_evento))
        .join(Caso.analista).where(*F).group_by(Usuario.id, Usuario.nombre).order_by(func.count().desc())
    ).all()
    por_analista = [{
        "id": r[0], "nombre": r[1], "total": r[2], "alta_critica": r[3], "con_retro": r[4],
        "mediana_minutos": _redondear(r[5]), "con_tiempo": r[6], "dentro_sla": r[7], "con_ticket": r[8],
        "ultimo": r[9],
    } for r in pa]
    sin_analista = db.scalar(select(func.count()).select_from(Caso).where(*F, Caso.analista_id.is_(None)))

    # ---------- distribución por estado, hora, tiempo de reporte
    por_estado = dict(db.execute(select(Caso.estado, func.count()).where(*F).group_by(Caso.estado)).all())
    hora = cast(func.extract("hour", LOCAL), Integer)
    horas = dict(db.execute(select(hora, func.count()).where(*F).group_by(hora)).all())
    por_hora = [{"hora": h, "total": horas.get(h, 0)} for h in range(24)]

    tramo = case(*[((MINUTOS >= a) & (MINUTOS < b), et) if b else (MINUTOS >= a, et) for a, b, et in TRAMOS],
                 else_="< 15 min")
    t = dict(db.execute(select(tramo, func.count()).where(*F, CON_TIEMPO).group_by(tramo)).all())
    tiempos = [{"tramo": et, "total": t.get(et, 0)} for _a, _b, et in TRAMOS]

    # ---------- alertas y clientes
    top_alertas = [{"alerta": a, "total": n} for a, n in db.execute(
        select(Caso.alerta, func.count()).where(*F).group_by(Caso.alerta).order_by(func.count().desc()).limit(10))]
    por_cliente = [{
        "id": r[0], "codigo": r[1], "nombre": r[2], "total": r[3], "con_retro": r[4],
        "mediana_minutos": _redondear(r[5]), "alta_critica": r[6], "tickets_abiertos": r[7],
    } for r in db.execute(
        select(Cliente.id, Cliente.codigo, Cliente.nombre, func.count(), _contar(Caso.estado != "SIN_RETRO"), MEDIANA,
               _contar(Caso.criticidad.in_(["Crítica", "Alta"])),
               _contar(Caso.glpi_ticket_id.is_not(None) & (func.coalesce(Caso.glpi_estado, 0) < 5)))
        .join(Caso.cliente).where(*F).group_by(Cliente.id).order_by(func.count().desc()))]

    glpi_estados = {str(e or 0): n for e, n in db.execute(
        select(Caso.glpi_estado, func.count()).where(*F, Caso.glpi_ticket_id.is_not(None)).group_by(Caso.glpi_estado))}

    return {
        "desde": desde, "hasta": hasta, "dias": dias,
        "indicadores": indicadores, "por_sla": por_sla, "por_dia": por_dia, "por_analista": por_analista, "sin_analista": sin_analista,
        "por_estado": por_estado, "por_hora": por_hora, "tiempos": tiempos, "top_alertas": top_alertas,
        "por_cliente": por_cliente, "glpi_estados": glpi_estados,
    }


# ---------------------------------------------------------------- SLA por analista
P90 = func.percentile_cont(0.9).within_group(MINUTOS).filter(CON_TIEMPO)


def _rango(desde: date | None, hasta: date | None) -> tuple[date, date]:
    hasta = hasta or datetime.now(TZ).date()
    desde = desde or (hasta - timedelta(days=29))
    if desde > hasta:
        raise HTTPException(422, "La fecha inicial es posterior a la final")
    if (hasta - desde).days > 400:
        raise HTTPException(422, "El rango máximo es de 400 días")
    return desde, hasta


@router.get("/sla")
def sla(
    desde: date | None = None,
    hasta: date | None = None,
    cliente_id: int | None = None,
    servicio: str | None = None,
    analista_id: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(requiere("tablero.ver")),
):
    """Cumplimiento del SLA de notificación por analista y criticidad, su evolución y los casos fuera del objetivo."""
    desde, hasta = _rango(desde, hasta)
    F = [VIGENTE, Caso.fecha_bitacora >= desde, Caso.fecha_bitacora <= hasta]
    if cliente_id:
        F.append(Caso.cliente_id == cliente_id)
    if servicio:
        F.append(Caso.servicio == servicio)
    G = [*F, Caso.analista_id == analista_id] if analista_id else F   # el detalle; la tabla de analistas usa F
    ok, objetivos = dentro(), settings.sla_objetivos
    crit = func.coalesce(Caso.criticidad, "Media")   # sin criticidad cuenta como Media, igual que su objetivo
    medidas = (func.count(), _contar(CON_TIEMPO), _contar(ok), MEDIANA, P90, func.max(MINUTOS).filter(CON_TIEMPO))

    def fila(r, i=0):
        return {"total": r[i], "con_tiempo": r[i + 1], "dentro": r[i + 2], "mediana_minutos": _redondear(r[i + 3]),
                "p90_minutos": _redondear(r[i + 4]), "max_minutos": _redondear(r[i + 5])}

    resumen = fila(db.execute(select(*medidas).where(*G)).one())

    # analistas × criticidad
    analistas: dict[int, dict] = {}
    for r in db.execute(select(Usuario.id, Usuario.nombre, crit, *medidas)
                        .join(Caso.analista).where(*F).group_by(Usuario.id, Usuario.nombre, crit)):
        a = analistas.setdefault(r[0], {"id": r[0], "nombre": r[1], "por_criticidad": {}})
        a["por_criticidad"][r[2]] = fila(r, 3)
    for r in db.execute(select(Usuario.id, *medidas).join(Caso.analista).where(*F).group_by(Usuario.id)):
        analistas[r[0]].update(fila(r, 1))
    por_analista = sorted(analistas.values(), key=lambda a: (-(a["con_tiempo"] - a["dentro"]), -a["con_tiempo"]))

    por_criticidad = [{"criticidad": c, "objetivo": m, **fila(r)} for c, m in objetivos.items()
                      for r in [db.execute(select(*medidas).where(*G, crit == c)).one()]]

    # evolución: por día hasta 5 semanas, si no por semana (lunes)
    dias = (hasta - desde).days + 1
    unidad = "dia" if dias <= 35 else "semana"
    clave = Caso.fecha_bitacora if unidad == "dia" else func.date_trunc("week", Caso.fecha_bitacora)
    evol = {r[0].date() if isinstance(r[0], datetime) else r[0]: r for r in
            db.execute(select(clave, _contar(CON_TIEMPO), _contar(ok)).where(*G).group_by(clave))}
    inicio = desde if unidad == "dia" else desde - timedelta(days=desde.weekday())
    paso = timedelta(days=1 if unidad == "dia" else 7)
    evolucion, d = [], inicio
    while d <= hasta:
        r = evol.get(d)
        evolucion.append({"desde": d.isoformat(), "con_tiempo": r[1] if r else 0, "dentro": r[2] if r else 0})
        d += paso

    # casos fuera del objetivo, primero los que más se pasaron
    exceso = MINUTOS - objetivo()
    fuera = [{"id": c.id, "numero": c.numero, "cliente": c.cliente.codigo, "analista": c.analista.nombre if c.analista else None,
              "criticidad": c.criticidad, "alerta": c.alerta, "fecha_evento": c.fecha_evento, "fecha_reporte": c.fecha_reporte,
              "minutos": round(m, 2), "objetivo": c.sla_minutos, "exceso_minutos": round(x, 2)}
             for c, m, x in db.execute(select(Caso, MINUTOS, exceso).where(*G, CON_TIEMPO, exceso > 0)
                                       .order_by(exceso.desc()).limit(100)).unique()]
    return {"desde": desde, "hasta": hasta, "objetivos": objetivos, "resumen": resumen, "por_criticidad": por_criticidad,
            "por_analista": por_analista, "unidad": unidad, "evolucion": evolucion, "fuera": fuera,
            "total_fuera": resumen["con_tiempo"] - resumen["dentro"]}
