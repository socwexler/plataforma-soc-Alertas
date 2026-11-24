"""Registro y consulta de casos escalados (reemplaza la hoja BITACORA)."""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from .. import adjuntos, avisos, correo, glpi
from ..notificacion import construir_notificacion
from ..auditoria import registrar
from ..informes.periodos import etiqueta, ultimos
from ..models import VIGENTE, Adjunto, Caso, CasoUso, Cliente, Consecutivo, Informe, Seguimiento, Usuario
from ..schemas import AdjuntoIn, CasoIn, CasoListaOut, CasoOut, MotivoIn, PaginaCasos, RevisionIn, SeguimientoIn, SeguimientoOut
from ..security import requiere, tiene, usuario_actual

router = APIRouter(prefix="/api/casos", tags=["casos"])
TZ = ZoneInfo(settings.zona_horaria)
ETIQUETA_ESTADO = {"SIN_RETRO": "SIN RETROALIMENTACIÓN", "CON_RETRO": "CON RETROALIMENTACIÓN", "CERRADO": "CERRADO"}


def siguiente_numero(db: Session, servicio: str) -> str:
    c = db.get(Consecutivo, servicio, with_for_update=True)
    if c is None:
        c = Consecutivo(servicio=servicio, ultimo=0)
        db.add(c)
        db.flush()
    c.ultimo += 1
    return f"WX{c.ultimo}" if servicio == "SOC" else f"WXNOC{c.ultimo}"


def _filtros(cliente_id, analista_id, servicio, estado, criticidad, tactica_id, caso_uso_id, desde, hasta, q, revision=None, anulados=None):
    f = []
    if anulados == "solo":
        f.append(Caso.anulado_en.is_not(None))
    elif anulados != "incluir":
        # Ocultos, salvo que se busque su número exacto: así no parece que falta un consecutivo
        f.append(or_(VIGENTE, func.lower(Caso.numero) == q.strip().lower()) if q else VIGENTE)
    if revision:
        f.append(Caso.revision == revision)
    if cliente_id:
        f.append(Caso.cliente_id == cliente_id)
    if analista_id:
        f.append(Caso.analista_id == analista_id)
    if servicio:
        f.append(Caso.servicio == servicio)
    if estado:
        f.append(Caso.estado == estado)
    if criticidad:
        f.append(Caso.criticidad == criticidad)
    if tactica_id:
        f.append(Caso.tactica_id == tactica_id)
    if caso_uso_id:
        f.append(Caso.caso_uso_id == caso_uso_id)
    if desde:
        f.append(Caso.fecha_bitacora >= desde)
    if hasta:
        f.append(Caso.fecha_bitacora <= hasta)
    if q:
        p = f"%{q.strip()}%"
        f.append(or_(Caso.numero.ilike(p), Caso.alerta.ilike(p), Caso.reporting_ip.ilike(p),
                     Caso.analisis.ilike(p), Caso.log_evento.ilike(p)))
    return f


@router.get("", response_model=PaginaCasos)
def listar(
    cliente_id: int | None = None,
    analista_id: int | None = None,
    servicio: str | None = None,
    estado: str | None = None,
    criticidad: str | None = None,
    tactica_id: str | None = None,
    caso_uso_id: int | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    q: str | None = None,
    revision: str | None = None,
    anulados: str | None = None,
    pagina: int = 1,
    tamano: int = 50,
    db: Session = Depends(get_db),
    _=Depends(usuario_actual),
):
    f = _filtros(cliente_id, analista_id, servicio, estado, criticidad, tactica_id, caso_uso_id, desde, hasta, q, revision, anulados)
    total = db.scalar(select(func.count()).select_from(Caso).where(*f))
    items = db.scalars(
        select(Caso).where(*f).order_by(Caso.fecha_evento.desc().nulls_last(), Caso.id.desc())
        .offset((max(pagina, 1) - 1) * tamano).limit(min(tamano, 200))
    ).unique().all()
    return {"total": total, "items": items}


@router.get("/resumen")
def resumen(db: Session = Depends(get_db), yo: Usuario = Depends(requiere("tablero.ver"))):
    """Indicadores rápidos para la página de inicio."""
    ahora = datetime.now(TZ)
    hoy = ahora.date()
    hace30 = hoy - timedelta(days=30)

    def contar(*f):
        return db.scalar(select(func.count()).select_from(Caso).where(VIGENTE, *f))

    minutos = (func.extract("epoch", Caso.fecha_reporte - Caso.fecha_evento) / 60)
    mediana = db.scalar(
        select(func.percentile_cont(0.5).within_group(minutos))
        .where(VIGENTE, Caso.fecha_bitacora >= hace30, Caso.fecha_reporte.is_not(None), Caso.fecha_evento.is_not(None))
    )
    fuera_sla = contar(Caso.fecha_bitacora >= hace30, minutos > settings.sla_minutos)
    por_estado = dict(db.execute(
        select(Caso.estado, func.count()).where(VIGENTE, Caso.fecha_bitacora >= hace30).group_by(Caso.estado)
    ).all())
    por_cliente = db.execute(
        select(Cliente.codigo, func.count()).join(Caso.cliente)
        .where(VIGENTE, Caso.fecha_bitacora >= hace30).group_by(Cliente.codigo).order_by(func.count().desc()).limit(8)
    ).all()
    return {
        "hoy": contar(Caso.fecha_bitacora >= hoy),
        "mios_hoy": contar(Caso.fecha_bitacora >= hoy, Caso.analista_id == yo.id),
        "ultimos_30": contar(Caso.fecha_bitacora >= hace30),
        "mediana_minutos_30": round(mediana) if mediana is not None else None,
        "fuera_sla_30": fuera_sla,
        "sla_minutos": settings.sla_minutos,
        "por_estado_30": por_estado,
        "por_cliente_30": [{"codigo": c, "total": n} for c, n in por_cliente],
    }


@router.get("/pendientes")
def pendientes(db: Session = Depends(get_db), yo: Usuario = Depends(usuario_actual)):
    """Contadores del menú: casos por revisar (revisores) y casos propios devueltos (analista)."""
    contar = lambda *f: db.scalar(select(func.count()).select_from(Caso).where(VIGENTE, *f))  # noqa: E731
    return {
        "por_revisar": contar(Caso.revision == "PENDIENTE") if tiene(yo, "casos.revisar") else 0,
        "mis_observados": contar(Caso.revision == "OBSERVADO", Caso.analista_id == yo.id),
    }


@router.get("/similares", response_model=list[CasoListaOut])
def similares(cliente_id: int, alerta: str, horas: int = 24, db: Session = Depends(get_db), _=Depends(usuario_actual)):
    """Casos del mismo cliente y alerta en las últimas N horas (para evitar duplicados)."""
    desde = datetime.now(timezone.utc) - timedelta(hours=horas)
    return db.scalars(
        select(Caso).where(VIGENTE, Caso.cliente_id == cliente_id, func.lower(Caso.alerta) == alerta.strip().lower(),
                           Caso.fecha_evento >= desde)
        .order_by(Caso.fecha_evento.desc()).limit(10)
    ).unique().all()


@router.get("/{cid}", response_model=CasoOut)
def obtener(cid: int, db: Session = Depends(get_db), _=Depends(usuario_actual)):
    c = db.get(Caso, cid)
    if not c:
        raise HTTPException(404, "Caso no encontrado")
    return c


def _validar(db: Session, datos: CasoIn, c: Caso | None = None):
    """Un cliente o caso de uso deshabilitado no se puede elegir, pero los casos que ya lo tienen se pueden seguir gestionando."""
    cliente = db.get(Cliente, datos.cliente_id)
    if not cliente or not (cliente.activo or (c and c.cliente_id == cliente.id)):
        raise HTTPException(422, "Cliente no válido o inactivo")
    if datos.servicio == "NOC" and not cliente.servicio_noc:
        raise HTTPException(422, f"{cliente.codigo} no tiene servicio NOC contratado")
    if datos.servicio == "SOC" and not cliente.servicio_soc:
        raise HTTPException(422, f"{cliente.codigo} no tiene servicio SOC contratado")
    if datos.caso_uso_id:
        cu = db.get(CasoUso, datos.caso_uso_id)
        if not cu:
            raise HTTPException(422, "Caso de uso no encontrado")
        if not cu.activo and not (c and c.caso_uso_id == cu.id):
            raise HTTPException(422, "El caso de uso está deshabilitado")
    if datos.fecha_reporte and datos.fecha_reporte < datos.fecha_evento:
        raise HTTPException(422, "La hora de reporte no puede ser anterior a la hora del evento en el SIEM")
    if datos.fecha_evento > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise HTTPException(422, "La hora del evento no puede estar en el futuro")


def _revisar_de_nuevo(db: Session, c: Caso, yo: Usuario):
    """Un cambio de contenido hecho por un N1 devuelve el caso a la lista del revisor."""
    if c.revision in ("REVISADO", "OBSERVADO") and not tiene(yo, "casos.revisar"):
        c.revision, c.revisado_por, c.revisado_en = "PENDIENTE", None, None
        db.add(Seguimiento(caso_id=c.id, autor_id=yo.id, autor_nombre=yo.nombre, tipo="revision",
                           comentario="Caso corregido: vuelve a quedar por revisar"))
        avisos.por_revisar(db, c)


def _puede_editar(c: Caso, yo: Usuario, anulado_ok: bool = False):
    if c.anulado_en and not anulado_ok:
        raise HTTPException(409, f"{c.numero} está anulado; restáurelo para modificarlo")
    if c.analista_id != yo.id and not tiene(yo, "casos.revisar"):
        raise HTTPException(403, "Solo el analista que registró el caso o un revisor (N2 o superior) pueden modificarlo")


# Campos cuyo cambio obliga a revisar de nuevo (no el estado, la respuesta del cliente ni el ticket)
CONTENIDO = ("cliente_id", "caso_uso_id", "alerta", "criticidad", "tecnica", "tactica_id", "resumen_ejecutivo",
             "analisis", "acciones_recomendadas", "geolocalizacion", "reporting_ip", "log_evento", "fecha_evento",
             "fecha_reporte")


@router.post("", response_model=CasoOut, status_code=201)
def crear(datos: CasoIn, crear_ticket: bool = False, db: Session = Depends(get_db),
          yo: Usuario = Depends(requiere("casos.crear"))):
    """Registra el caso. Con crear_ticket=true también crea el ticket en GLPI; si GLPI falla,
    el caso queda guardado igual y el error se devuelve en glpi_error para reintentar."""
    _validar(db, datos)
    c = Caso(**datos.model_dump())
    c.fecha_reporte = c.fecha_reporte or datetime.now(timezone.utc)
    c.fecha_bitacora = c.fecha_reporte.astimezone(TZ).date()
    c.analista_id = yo.id
    c.numero = siguiente_numero(db, datos.servicio)
    c.origen = "app"
    c.revision = None if tiene(yo, "casos.revisar") else "PENDIENTE"
    db.add(c)
    db.flush()
    db.add(Seguimiento(caso_id=c.id, autor_id=yo.id, autor_nombre=yo.nombre, tipo="estado",
                       comentario=f"Caso registrado con estado {ETIQUETA_ESTADO[c.estado]}"))
    if c.revision == "PENDIENTE":
        avisos.por_revisar(db, c)
    db.commit()
    if crear_ticket and settings.glpi_activo and not c.glpi_ticket_id:
        try:
            glpi.crear_ticket_para_caso(db, db.get(Caso, c.id), yo)
        except glpi.ErrorGLPI:
            pass  # el error queda en caso.glpi_error
    db.expire_all()
    return db.get(Caso, c.id)


@router.put("/{cid}", response_model=CasoOut)
def editar(cid: int, datos: CasoIn, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("casos.crear"))):
    c = db.get(Caso, cid)
    if not c:
        raise HTTPException(404, "Caso no encontrado")
    _puede_editar(c, yo)
    if datos.servicio != c.servicio:
        raise HTTPException(422, "No se puede cambiar el servicio de un caso ya numerado")
    _validar(db, datos, c)
    estado_anterior, ticket_anterior = c.estado, c.glpi_ticket_id
    contenido_anterior = {k: getattr(c, k) for k in CONTENIDO}
    for k, v in datos.model_dump(exclude={"fecha_reporte"}).items():
        setattr(c, k, v)
    if datos.fecha_reporte:
        c.fecha_reporte = datos.fecha_reporte
        if c.origen == "app":  # los importados conservan la Fecha de la bitácora
            c.fecha_bitacora = c.fecha_reporte.astimezone(TZ).date()
    # Si el N1 corrige el contenido, el caso vuelve a la lista del revisor
    if any(getattr(c, k) != v for k, v in contenido_anterior.items()):
        _revisar_de_nuevo(db, c, yo)
    if c.glpi_ticket_id != ticket_anterior:  # ticket digitado a mano: se vuelve a sincronizar
        c.glpi_estado = c.glpi_error = c.glpi_sincronizado_en = None
    if c.estado != estado_anterior:
        db.add(Seguimiento(caso_id=c.id, autor_id=yo.id, autor_nombre=yo.nombre, tipo="estado",
                           comentario=f"Estado: {ETIQUETA_ESTADO[estado_anterior]} → {ETIQUETA_ESTADO[c.estado]}"))
    db.commit()
    if (c.estado == "CERRADO" and estado_anterior != "CERRADO" and c.glpi_ticket_id
            and settings.glpi_activo and settings.glpi_resolver_al_cerrar and (c.glpi_estado or 0) < 5):
        try:
            glpi.resolver_ticket_de_caso(db, c, yo)
            c.glpi_error = None
        except glpi.ErrorGLPI as e:
            c.glpi_error = f"No se pudo resolver el ticket en GLPI: {e}"
        db.commit()
    db.expire_all()
    return db.get(Caso, cid)


@router.post("/{cid}/seguimientos", response_model=SeguimientoOut, status_code=201)
def comentar(cid: int, datos: SeguimientoIn, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("casos.crear"))):
    c = db.get(Caso, cid)
    if not c:
        raise HTTPException(404, "Caso no encontrado")
    _puede_editar(c, yo, anulado_ok=not datos.publicar_glpi)  # en un anulado solo se admiten comentarios
    s = Seguimiento(caso_id=cid, autor_id=yo.id, autor_nombre=yo.nombre, tipo=datos.tipo,
                    comentario=datos.comentario.strip())
    db.add(s)
    db.commit()
    error = None
    if datos.publicar_glpi:
        if not c.glpi_ticket_id:
            error = "El caso no tiene ticket en GLPI"
        else:
            try:
                glpi.publicar_seguimiento(c, f"{yo.nombre}: {s.comentario}")
                s.comentario += "\n(publicado en GLPI)"
                db.commit()
            except glpi.ErrorGLPI as e:
                error = str(e)
    return SeguimientoOut.model_validate(s).model_copy(update={"glpi_error": error})


@router.post("/{cid}/revision", response_model=CasoOut)
def revisar(cid: int, datos: RevisionIn, db: Session = Depends(get_db),
            yo: Usuario = Depends(requiere("casos.revisar"))):
    """Revisión posterior de un caso creado por un N1: lo marca revisado o lo devuelve con observaciones."""
    c = db.get(Caso, cid, with_for_update={"of": Caso})
    if not c:
        raise HTTPException(404, "Caso no encontrado")
    if c.anulado_en:
        raise HTTPException(409, f"{c.numero} está anulado")
    if c.revision is None:
        raise HTTPException(409, "Este caso no requiere revisión")
    if c.analista_id == yo.id:
        raise HTTPException(403, "No puede revisar un caso propio")
    nota = (datos.observacion or "").strip()
    if datos.resultado == "OBSERVADO" and len(nota) < 5:
        raise HTTPException(422, "Escriba qué debe corregir el analista")
    c.revision, c.revisado_por, c.revisado_en = datos.resultado, yo.nombre, datetime.now(timezone.utc)
    titulo = "Caso revisado" if datos.resultado == "REVISADO" else "Caso devuelto con observaciones"
    db.add(Seguimiento(caso_id=c.id, autor_id=yo.id, autor_nombre=yo.nombre, tipo="revision",
                       comentario=f"{titulo}{': ' + nota if nota else ''}"))
    if datos.resultado == "OBSERVADO":
        avisos.devuelto(db, c, yo, nota)
    db.commit()
    db.expire_all()
    return db.get(Caso, cid)


def _informes_de(db: Session, c: Caso) -> str:
    """Informes que cuentan el caso: los finales no cambian y los borradores conservan sus textos hasta regenerarlos."""
    if not c.fecha_bitacora:
        return ""
    nombres: dict[str, list[str]] = {"FINAL": [], "BORRADOR": []}
    for inf in db.scalars(select(Informe).where(Informe.cliente_id == c.cliente_id, Informe.periodo_fin >= c.fecha_bitacora)
                          .order_by(Informe.periodo_inicio)):
        if ultimos(inf.periodo_inicio, c.cliente.dia_corte, 3)[0][0] <= c.fecha_bitacora:  # el informe muestra 3 periodos
            nombres[inf.estado].append(etiqueta(inf.periodo_inicio, inf.periodo_fin))
    notas = []
    if nombres["FINAL"]:
        notas.append(f"No cambia el informe final: {', '.join(nombres['FINAL'])}")
    if nombres["BORRADOR"]:
        notas.append(f"Regenere los textos del informe en borrador: {', '.join(nombres['BORRADOR'])}")
    return "".join(f"\n{n}." for n in notas)


def _anulacion(db: Session, cid: int, yo: Usuario, anular: bool, motivo: str) -> Caso:
    c = db.get(Caso, cid, with_for_update={"of": Caso})
    if not c:
        raise HTTPException(404, "Caso no encontrado")
    if bool(c.anulado_en) == anular:
        raise HTTPException(409, f"{c.numero} {'ya está' if anular else 'no está'} anulado")
    c.anulado_en, c.anulado_por, c.anulado_motivo = (datetime.now(timezone.utc), yo.nombre, motivo) if anular else (None, None, None)
    texto = f"Caso {'anulado' if anular else 'restaurado'}. Motivo: {motivo}{_informes_de(db, c)}"
    if anular and c.glpi_ticket_id:
        texto += f"\nEl ticket GLPI {c.glpi_ticket_id} no se modifica: ciérrelo en GLPI si corresponde."
    db.add(Seguimiento(caso_id=c.id, autor_id=yo.id, autor_nombre=yo.nombre, tipo="anulacion", comentario=texto))
    registrar(db, yo, "anular" if anular else "restaurar", f"el caso {c.numero} de {c.cliente.codigo}", f"motivo: {motivo}")
    db.commit()
    db.expire_all()
    return db.get(Caso, cid)


@router.post("/{cid}/anular", response_model=CasoOut)
def anular(cid: int, datos: MotivoIn, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("casos.anular"))):
    """El caso conserva número e historial, pero deja de contar en tablero e informes y no se puede modificar."""
    return _anulacion(db, cid, yo, True, datos.motivo)


@router.post("/{cid}/restaurar", response_model=CasoOut)
def restaurar(cid: int, datos: MotivoIn, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("casos.anular"))):
    return _anulacion(db, cid, yo, False, datos.motivo)


@router.post("/{cid}/glpi", response_model=CasoOut)
def crear_ticket(cid: int, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("casos.crear"))):
    """Crea (o reintenta crear) el ticket GLPI del caso."""
    c = db.get(Caso, cid)
    if not c:
        raise HTTPException(404, "Caso no encontrado")
    _puede_editar(c, yo)
    try:
        glpi.crear_ticket_para_caso(db, c, yo)
    except glpi.ErrorGLPI as e:
        raise HTTPException(502, str(e))
    db.expire_all()
    return db.get(Caso, cid)


@router.post("/{cid}/glpi/sincronizar", response_model=CasoOut)
def sincronizar_ticket(cid: int, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("casos.crear"))):
    c = db.get(Caso, cid)
    if not c or not c.glpi_ticket_id:
        raise HTTPException(404, "El caso no tiene ticket GLPI")
    _puede_editar(c, yo)
    try:
        with glpi.ClienteGLPI() as g:
            nuevo = g.estado_ticket(c.glpi_ticket_id)
    except glpi.ErrorGLPI as e:
        raise HTTPException(502, str(e))
    c.glpi_estado, c.glpi_error, c.glpi_sincronizado_en = nuevo, None, datetime.now(timezone.utc)
    db.commit()
    db.expire_all()
    return db.get(Caso, cid)


def _para_correo(db: Session, cid: int, yo: Usuario) -> Caso:
    c = db.get(Caso, cid)
    if not c:
        raise HTTPException(404, "Caso no encontrado")
    _puede_editar(c, yo)
    return c


@router.get("/{cid}/correo")
def ver_correo(cid: int, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("casos.crear"))):
    """Vista previa del correo: destinatarios (salen del cliente), asunto, contenido y comprobaciones."""
    return correo.preparar(db, _para_correo(db, cid, yo))


@router.post("/{cid}/correo.eml")
def generar_correo(cid: int, confirmar: bool = False, db: Session = Depends(get_db),
                   yo: Usuario = Depends(requiere("casos.crear"))):
    """Borrador para Outlook. No envía nada; queda registrado quién lo generó y para quién."""
    c = _para_correo(db, cid, yo)
    d = correo.preparar(db, c)
    if d["bloqueos"]:
        raise HTTPException(422, ". ".join(d["bloqueos"]))
    if d["advertencias"] and not confirmar:
        raise HTTPException(409, "Confirme las advertencias: " + ". ".join(d["advertencias"]))
    contenido = correo.borrador(c, d)
    nota = f"Borrador de correo generado. Para: {', '.join(d['para'])}. CC: {', '.join(d['cc']) or 'ninguno'}"
    if d["archivos"]:
        nota += "\nArchivos: " + ", ".join(x["nombre"] for x in d["archivos"])
    if d["advertencias"]:
        nota += "\nAdvertencias aceptadas: " + "; ".join(d["advertencias"])
    db.add(Seguimiento(caso_id=c.id, autor_id=yo.id, autor_nombre=yo.nombre, tipo="correo", comentario=nota))
    db.commit()
    return Response(contenido, media_type="message/rfc822",
                    headers={"Content-Disposition": f'attachment; filename="{c.numero}_{c.cliente.codigo}.eml"'})


# ------------------------------------------------------------------ evidencias y adjuntos
def _adjunto(db: Session, cid: int, aid: int) -> Adjunto:
    a = db.get(Adjunto, aid)
    if not a or a.caso_id != cid:
        raise HTTPException(404, "Archivo no encontrado")
    return a


def _nota(db: Session, c: Caso, yo: Usuario, texto: str):
    db.add(Seguimiento(caso_id=c.id, autor_id=yo.id, autor_nombre=yo.nombre, tipo="adjunto", comentario=texto))


@router.post("/{cid}/adjuntos", response_model=CasoOut, status_code=201)
def subir_adjuntos(cid: int, archivos: list[UploadFile], tipo: str = Form("ADJUNTO"), db: Session = Depends(get_db),
                   yo: Usuario = Depends(requiere("casos.crear"))):
    """Todo o nada: si un archivo no es válido, no se guarda ninguno."""
    c = _para_correo(db, cid, yo)
    if tipo not in ("EVIDENCIA", "ADJUNTO"):
        raise HTTPException(422, "Tipo no válido")
    limite, usado = settings.adjuntos_caso_max_mb * adjuntos.MB, sum(a.tamano for a in c.adjuntos)
    huellas = {(a.sha256, a.tipo) for a in c.adjuntos}
    nuevos = []
    try:
        for f in archivos[:20]:
            d = adjuntos.validar(f.filename, f.file.read(settings.adjunto_max_mb * adjuntos.MB + 1), tipo)
            if (d["sha256"], tipo) in huellas:
                raise adjuntos.ErrorAdjunto(f"{d['nombre']}: ese archivo ya está en el caso")
            usado += d["tamano"]
            if usado > limite:
                raise adjuntos.ErrorAdjunto(f"El caso superaría {settings.adjuntos_caso_max_mb} MB en archivos")
            huellas.add((d["sha256"], tipo))
            nuevos.append(Adjunto(caso_id=cid, incluir=True, subido_por=yo.nombre, **d))
    except adjuntos.ErrorAdjunto as e:
        raise HTTPException(422, str(e))
    db.add_all(nuevos)
    _nota(db, c, yo, f"{'Evidencia' if tipo == 'EVIDENCIA' else 'Adjunto'}: " + ", ".join(a.nombre for a in nuevos))
    _revisar_de_nuevo(db, c, yo)
    db.commit()
    db.expire_all()
    return db.get(Caso, cid)


@router.get("/{cid}/adjuntos/{aid}")
def descargar_adjunto(cid: int, aid: int, db: Session = Depends(get_db), _=Depends(usuario_actual)):
    a = _adjunto(db, cid, aid)
    return Response(a.contenido, media_type=a.mime, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(a.nombre)}",
        "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'; sandbox", "Cache-Control": "private, no-store"})


@router.patch("/{cid}/adjuntos/{aid}", response_model=CasoOut)
def marcar_adjunto(cid: int, aid: int, datos: AdjuntoIn, db: Session = Depends(get_db),
                   yo: Usuario = Depends(requiere("casos.crear"))):
    c, a = _para_correo(db, cid, yo), _adjunto(db, cid, aid)
    if a.incluir != datos.incluir:
        a.incluir = datos.incluir
        _nota(db, c, yo, f"{a.nombre}: {'se incluye en' if a.incluir else 'no va en'} el correo")
        _revisar_de_nuevo(db, c, yo)
        db.commit()
    db.expire_all()
    return db.get(Caso, cid)


@router.delete("/{cid}/adjuntos/{aid}", response_model=CasoOut)
def quitar_adjunto(cid: int, aid: int, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("casos.crear"))):
    c, a = _para_correo(db, cid, yo), _adjunto(db, cid, aid)
    _nota(db, c, yo, f"Archivo eliminado: {a.nombre} (SHA-256 {a.sha256[:16]}…)")
    _revisar_de_nuevo(db, c, yo)
    db.delete(a)
    db.commit()
    db.expire_all()
    return db.get(Caso, cid)


@router.get("/{cid}/notificacion")
def notificacion(cid: int, db: Session = Depends(get_db), _=Depends(usuario_actual)):
    """Texto y HTML de la notificación al cliente (equivale a la hoja 'Plantilla')."""
    c = db.get(Caso, cid)
    if not c:
        raise HTTPException(404, "Caso no encontrado")
    return construir_notificacion(c)
