"""Informes mensuales por cliente: datos, anexos de FortiSIEM, textos y descarga en PDF/PPTX."""
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from .. import adjuntos, imagenes
from ..auditoria import registrar
from ..config import settings
from ..db import get_db
from ..informes import anexos as ax
from ..informes import metricas as mt
from ..informes import presentacion_html, word
from ..informes.contenido import armar
from ..informes.convertidor import ErrorConversion
from ..informes.periodos import etiqueta, nombre_informe, periodo
from ..informes.textos import CLAVES, generar
from ..models import Cliente, ImagenInforme, Informe, Usuario
from ..security import requiere

router = APIRouter(prefix="/api/informes", tags=["informes"])
TZ = ZoneInfo(settings.zona_horaria)
MAX_ANEXO = 60 * 1024 * 1024


def _obtener(db: Session, iid: int) -> Informe:
    inf = db.get(Informe, iid)
    if not inf:
        raise HTTPException(404, "Informe no encontrado")
    return inf


def _editable(inf: Informe):
    if inf.estado == "FINAL":
        raise HTTPException(409, "El informe está marcado como final; vuelva a borrador para modificarlo")


def _metricas(db: Session, inf: Informe) -> dict:
    return inf.metricas if inf.estado == "FINAL" and inf.metricas else mt.calcular(db, inf.cliente, inf.periodo_inicio)


def _resumen(inf: Informe) -> dict:
    return {"id": inf.id, "cliente": {"id": inf.cliente.id, "codigo": inf.cliente.codigo, "nombre": inf.cliente.nombre},
            "periodo_inicio": inf.periodo_inicio, "periodo_fin": inf.periodo_fin,
            "periodo": etiqueta(inf.periodo_inicio, inf.periodo_fin), "nombre": nombre_informe(inf.periodo_inicio),
            "estado": inf.estado, "creado_por": inf.creado_por, "actualizado_en": inf.actualizado_en,
            "anexos": sorted(k for k, v in (inf.anexos or {}).items() if v)}


def _detalle(db: Session, inf: Informe) -> dict:
    an = inf.anexos or {}
    return {
        **_resumen(inf),
        "eps_promedio": inf.eps_promedio, "fuentes_integradas": inf.fuentes_integradas,
        "boletines_enviados": inf.boletines_enviados, "boletines": inf.boletines or [],
        "textos": inf.textos or {}, "claves_textos": CLAVES, "archivos": inf.archivos or [],
        "anexos_resumen": {k: ax.resumen({"tipo": k, "datos": v}) for k, v in an.items()
                           if v and k in ("paises_entrantes", "paises_salientes", "puertos", "ips", "fuentes", "fuentes_noc", "eps")},
        "eps_historico": an.get("eps_historico") or [],
        "eps_contratados": inf.cliente.eps_contratados,
        "metricas": _metricas(db, inf),
    }


def _nombre_archivo(inf: Informe, ext: str) -> str:
    base = f"Informe {inf.cliente.codigo} {nombre_informe(inf.periodo_inicio)}"
    return re.sub(r"[^\w\- ]", "", base).replace(" ", "_") + f".{ext}"


# ------------------------------------------------------------------ listado y creación
@router.get("")
def listar(cliente_id: int | None = None, db: Session = Depends(get_db), _=Depends(requiere("informes.ver"))):
    q = select(Informe).order_by(Informe.periodo_inicio.desc(), Informe.id.desc()).limit(300)
    if cliente_id:
        q = q.where(Informe.cliente_id == cliente_id)
    return [_resumen(i) for i in db.scalars(q).unique()]


@router.get("/periodos")
def periodos_disponibles(cliente_id: int, db: Session = Depends(get_db), _=Depends(requiere("informes.ver"))):
    """Últimos 12 periodos del cliente según su día de corte (el más reciente primero)."""
    cl = db.get(Cliente, cliente_id)
    if not cl:
        raise HTTPException(404, "Cliente no encontrado")
    hoy = datetime.now(TZ).date()
    existentes = {i.periodo_inicio: i.id for i in db.scalars(select(Informe).where(Informe.cliente_id == cliente_id))}
    salida, anio, mes = [], hoy.year, hoy.month
    while len(salida) < 12:
        ini, fin = periodo(anio, mes, cl.dia_corte)
        if ini <= hoy:
            salida.append({"anio": anio, "mes": mes, "inicio": ini, "fin": fin, "etiqueta": etiqueta(ini, fin),
                           "nombre": nombre_informe(ini), "en_curso": fin >= hoy, "informe_id": existentes.get(ini)})
        anio, mes = (anio - 1, 12) if mes == 1 else (anio, mes - 1)
    return salida


class NuevoInforme(BaseModel):
    cliente_id: int
    anio: int = Field(ge=2020, le=2100)
    mes: int = Field(ge=1, le=12)


@router.post("", status_code=201)
def crear(datos: NuevoInforme, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("informes.editar"))):
    cl = db.get(Cliente, datos.cliente_id)
    if not cl:
        raise HTTPException(404, "Cliente no encontrado")
    if not cl.activo:
        raise HTTPException(422, f"{cl.codigo} está deshabilitado; habilítelo para crear informes")
    ini, fin = periodo(datos.anio, datos.mes, cl.dia_corte)
    if db.scalar(select(Informe).where(Informe.cliente_id == cl.id, Informe.periodo_inicio == ini)):
        raise HTTPException(409, "Ya existe un informe para ese cliente y periodo")
    # Se heredan del informe anterior los datos que suelen repetirse (fuentes, histórico de EPS)
    anterior = db.scalar(select(Informe).where(Informe.cliente_id == cl.id, Informe.periodo_inicio < ini)
                         .order_by(Informe.periodo_inicio.desc()).limit(1))
    anexos = {}
    if anterior:
        an = anterior.anexos or {}
        anexos = {k: an[k] for k in ("fuentes", "fuentes_noc") if an.get(k)}
        hist = list(an.get("eps_historico") or [])
        if anterior.eps_promedio:
            hist.append({"periodo": nombre_informe(anterior.periodo_inicio).split()[0], "valor": anterior.eps_promedio})
        if hist:
            anexos["eps_historico"] = hist[-3:]
    inf = Informe(cliente_id=cl.id, periodo_inicio=ini, periodo_fin=fin, anexos=anexos, archivos=[], boletines=[],
                  textos={}, creado_por=yo.nombre,
                  fuentes_integradas=anterior.fuentes_integradas if anterior else None)
    db.add(inf)
    db.flush()
    db.refresh(inf)
    inf.textos = generar(cl, inf, mt.calcular(db, cl, ini))
    db.commit()
    return _detalle(db, inf)


# ------------------------------------------------------------------ edición
@router.get("/{iid}")
def obtener(iid: int, db: Session = Depends(get_db), _=Depends(requiere("informes.ver"))):
    return _detalle(db, _obtener(db, iid))


class Boletin(BaseModel):
    nombre: str = Field(min_length=3)
    tipo: str | None = None
    fecha: str | None = None
    resumen: str | None = None
    imagen_id: int | None = None


class EdicionInforme(BaseModel):
    eps_promedio: float | None = Field(default=None, ge=0)
    fuentes_integradas: int | None = Field(default=None, ge=0)
    boletines_enviados: int | None = Field(default=None, ge=0)
    boletines: list[Boletin] = []
    textos: dict[str, str] = {}


@router.put("/{iid}")
def editar(iid: int, datos: EdicionInforme, db: Session = Depends(get_db), _=Depends(requiere("informes.editar"))):
    inf = _obtener(db, iid)
    _editable(inf)
    inf.eps_promedio = datos.eps_promedio
    inf.fuentes_integradas = datos.fuentes_integradas
    inf.boletines_enviados = datos.boletines_enviados
    propias = {x.id for x in inf.imagenes}
    usadas = {b.imagen_id for b in datos.boletines if b.imagen_id}
    if usadas - propias:
        raise HTTPException(422, "La imagen de un boletín ya no existe; cárguela de nuevo")
    inf.boletines = [b.model_dump() for b in datos.boletines]
    inf.imagenes = [x for x in inf.imagenes if x.id in usadas]  # se borran las que ya no usa ningún boletín
    inf.textos = {**(inf.textos or {}), **{k: v for k, v in datos.textos.items() if k in CLAVES}}
    db.commit()
    return _detalle(db, inf)


@router.post("/{iid}/imagenes", status_code=201)
def cargar_imagen(iid: int, archivo: UploadFile, db: Session = Depends(get_db), _=Depends(requiere("informes.editar"))):
    """Imagen de un boletín. Queda asociada al guardar el informe con su imagen_id."""
    inf = _obtener(db, iid)
    _editable(inf)
    if len(inf.imagenes) >= 60:
        raise HTTPException(422, "El informe ya tiene demasiadas imágenes; guarde los cambios para descartar las que no se usan")
    try:
        d = imagenes.preparar(archivo.filename, archivo.file.read(settings.adjunto_max_mb * adjuntos.MB + 1))
    except adjuntos.ErrorAdjunto as e:
        raise HTTPException(422, str(e))
    d.pop("claro")
    x = ImagenInforme(informe_id=iid, **d)
    db.add(x)
    db.commit()
    return {"id": x.id}


@router.get("/{iid}/imagenes/{img}")
def ver_imagen(iid: int, img: int, db: Session = Depends(get_db), _=Depends(requiere("informes.ver"))):
    x = db.get(ImagenInforme, img)
    if not x or x.informe_id != iid:
        raise HTTPException(404, "Imagen no encontrada")
    return Response(x.contenido, media_type=x.mime, headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=300",
                                                             "Content-Security-Policy": "default-src 'none'; sandbox"})


@router.post("/{iid}/anexos")
async def cargar_anexos(iid: int, archivos: list[UploadFile], db: Session = Depends(get_db),
                        yo: Usuario = Depends(requiere("informes.editar"))):
    inf = _obtener(db, iid)
    _editable(inf)
    resultados, errores = [], []
    anexos = dict(inf.anexos or {})
    for a in archivos:
        contenido = await a.read()
        if len(contenido) > MAX_ANEXO:
            errores.append(f"{a.filename}: supera 60 MB")
            continue
        try:
            leidos = ax.leer_anexo(a.filename or "anexo.csv", contenido)
        except ax.ErrorAnexo as e:
            errores.append(str(e))
            continue
        anexos, eps, boletines = ax.aplicar(anexos, leidos)
        if eps and inf.eps_promedio is None:
            inf.eps_promedio = eps[-1]["valor"]
        if boletines and not inf.boletines:
            inf.boletines = boletines
            inf.boletines_enviados = inf.boletines_enviados or len(boletines)
        if anexos.get("fuentes") and not inf.fuentes_integradas:
            inf.fuentes_integradas = anexos["fuentes"]["total"]
        detalle = [{"tipo": t["tipo"], "nombre": ax.NOMBRES.get(t["tipo"], t["tipo"]), "origen": t["origen"],
                    "filas": t["filas"], "resumen": ax.resumen(t)} for t in leidos]
        resultados.append({"archivo": a.filename, "tablas": detalle})
        inf.archivos = [*(inf.archivos or []), {"archivo": a.filename, "tablas": detalle, "por": yo.nombre,
                                                "fecha": datetime.now(TZ).isoformat(timespec="minutes")}]
    inf.anexos = anexos
    flag_modified(inf, "anexos")
    db.commit()
    return {"resultados": resultados, "errores": errores, "informe": _detalle(db, inf)}


@router.delete("/{iid}/anexos/{tipo}")
def quitar_anexo(iid: int, tipo: str, db: Session = Depends(get_db), _=Depends(requiere("informes.editar"))):
    inf = _obtener(db, iid)
    _editable(inf)
    anexos = dict(inf.anexos or {})
    anexos.pop(tipo, None)
    inf.anexos = anexos
    db.commit()
    return _detalle(db, inf)


class Regenerar(BaseModel):
    claves: list[str] | None = None  # None = todos


@router.post("/{iid}/textos/regenerar")
def regenerar(iid: int, datos: Regenerar, db: Session = Depends(get_db), _=Depends(requiere("informes.editar"))):
    inf = _obtener(db, iid)
    _editable(inf)
    nuevos = generar(inf.cliente, inf, mt.calcular(db, inf.cliente, inf.periodo_inicio))
    claves = datos.claves or list(CLAVES)
    inf.textos = {**(inf.textos or {}), **{k: nuevos.get(k, "") for k in claves}}
    db.commit()
    return _detalle(db, inf)


class CambioEstado(BaseModel):
    estado: str


@router.post("/{iid}/estado")
def cambiar_estado(iid: int, datos: CambioEstado, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("informes.cerrar"))):
    inf = _obtener(db, iid)
    if datos.estado not in ("BORRADOR", "FINAL"):
        raise HTTPException(422, "Estado no válido")
    if datos.estado == "FINAL":
        # Se congela la foto de las métricas: el informe enviado no cambia si luego se editan casos
        inf.metricas = mt.calcular(db, inf.cliente, inf.periodo_inicio)
    else:
        inf.metricas = None
    if inf.estado != datos.estado:
        registrar(db, yo, "editar", f"el informe de {inf.cliente.codigo} del {inf.periodo_inicio} al {inf.periodo_fin}",
                  f"estado: {inf.estado.lower()} → {datos.estado.lower()}")
    inf.estado = datos.estado
    db.commit()
    return _detalle(db, inf)


@router.delete("/{iid}", status_code=204)
def eliminar(iid: int, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("informes.cerrar"))):
    inf = _obtener(db, iid)
    _editable(inf)
    registrar(db, yo, "eliminar", f"el informe de {inf.cliente.codigo} del {inf.periodo_inicio} al {inf.periodo_fin}")
    db.delete(inf)
    db.commit()


# ------------------------------------------------------------------ salidas
def _archivo(contenido: bytes, tipo: str, nombre: str) -> Response:
    return Response(contenido, media_type=tipo, headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@router.get("/{iid}/docx")
def descargar_word(iid: int, db: Session = Depends(get_db), _=Depends(requiere("informes.ver"))):
    """Informe ejecutivo en Word sobre la plantilla corporativa (tabla de contenido con páginas)."""
    inf = _obtener(db, iid)
    docx, _pdf = word.generar(armar(inf, _metricas(db, inf)))
    return _archivo(docx, DOCX, _nombre_archivo(inf, "docx"))


@router.get("/{iid}/pdf")
def descargar_pdf(iid: int, db: Session = Depends(get_db), _=Depends(requiere("informes.ver"))):
    """El mismo Word convertido a PDF (LibreOffice), con las fuentes de la plantilla."""
    inf = _obtener(db, iid)
    _docx, pdf = word.generar(armar(inf, _metricas(db, inf)))
    if pdf is None:
        raise HTTPException(503, "El servicio de conversión a PDF no está disponible; intente de nuevo o descargue el Word")
    return _archivo(pdf, "application/pdf", _nombre_archivo(inf, "pdf"))


@router.get("/{iid}/presentacion", response_class=HTMLResponse)
def ver_presentacion(iid: int, descargar: bool = False, db: Session = Depends(get_db), _=Depends(requiere("informes.ver"))):
    """Con descargar=true entrega un único archivo .html que se abre con doble clic."""
    inf = _obtener(db, iid)
    h = presentacion_html.html(inf, _metricas(db, inf), informe_id=None if descargar else inf.id)
    nombre = _nombre_archivo(inf, "html").replace("Informe_", "Presentacion_")
    return HTMLResponse(h, headers={"Content-Disposition": f'attachment; filename="{nombre}"'} if descargar else None)


@router.get("/{iid}/presentacion.pdf")
def presentacion_pdf(iid: int, db: Session = Depends(get_db), _=Depends(requiere("informes.ver"))):
    inf = _obtener(db, iid)
    try:
        pdf = presentacion_html.pdf(inf, _metricas(db, inf))
    except ErrorConversion as e:
        raise HTTPException(503, str(e))
    nombre = _nombre_archivo(inf, "pdf").replace("Informe_", "Presentacion_")
    return _archivo(pdf, "application/pdf", nombre)
