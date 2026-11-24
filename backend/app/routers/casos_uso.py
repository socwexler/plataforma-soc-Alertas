"""Base de conocimiento de casos de uso."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..auditoria import aplicar, eliminar, registrar
from ..db import get_db
from ..models import Caso, CasoUso, Tactica, Usuario
from ..schemas import CasoUsoIn, CasoUsoMini, CasoUsoOut, EstadoIn, PaginaCasosUso, TacticaOut
from ..security import requiere, usuario_actual

router = APIRouter(prefix="/api", tags=["base de conocimiento"])


@router.get("/tacticas", response_model=list[TacticaOut])
def tacticas(db: Session = Depends(get_db), _=Depends(usuario_actual)):
    return db.scalars(select(Tactica).order_by(Tactica.orden)).all()


@router.get("/casos-uso/opciones", response_model=list[CasoUsoMini])
def opciones(servicio: str = "SOC", db: Session = Depends(get_db), _=Depends(usuario_actual)):
    """Lista liviana para el selector del formulario; los más usados primero."""
    uso = (select(Caso.caso_uso_id, func.count().label("n")).group_by(Caso.caso_uso_id).subquery())
    filas = db.execute(
        select(CasoUso, func.coalesce(uso.c.n, 0))
        .outerjoin(uso, uso.c.caso_uso_id == CasoUso.id)
        .where(CasoUso.activo, CasoUso.servicio == servicio)
        .order_by(func.coalesce(uso.c.n, 0).desc(), CasoUso.nombre)
    ).all()
    return [
        CasoUsoMini.model_validate(cu).model_copy(update={"tiene_plantilla": bool(cu.resumen_ejecutivo)})
        for cu, _n in filas
    ]


@router.get("/casos-uso", response_model=PaginaCasosUso)
def listar(
    q: str | None = None,
    servicio: str | None = None,
    tactica_id: str | None = None,
    criticidad: str | None = None,
    con_plantilla: bool | None = None,
    incluir_inactivos: bool = False,
    pagina: int = 1,
    tamano: int = 50,
    db: Session = Depends(get_db),
    _=Depends(requiere("kb.ver")),
):
    filtros = []
    if not incluir_inactivos:
        filtros.append(CasoUso.activo)
    if q:
        patron = f"%{q.strip()}%"
        filtros.append(or_(CasoUso.nombre.ilike(patron), CasoUso.tecnica.ilike(patron),
                           CasoUso.tecnologia.ilike(patron), CasoUso.resumen_ejecutivo.ilike(patron)))
    if servicio:
        filtros.append(CasoUso.servicio == servicio)
    if tactica_id:
        filtros.append(CasoUso.tactica_id == tactica_id)
    if criticidad:
        filtros.append(CasoUso.criticidad == criticidad)
    if con_plantilla is True:
        filtros.append(CasoUso.resumen_ejecutivo.is_not(None))
    elif con_plantilla is False:
        filtros.append(CasoUso.resumen_ejecutivo.is_(None))

    total = db.scalar(select(func.count()).select_from(CasoUso).where(*filtros))
    uso = select(Caso.caso_uso_id, func.count().label("n")).group_by(Caso.caso_uso_id).subquery()
    filas = db.execute(
        select(CasoUso, func.coalesce(uso.c.n, 0).label("n"))
        .outerjoin(uso, uso.c.caso_uso_id == CasoUso.id)
        .where(*filtros)
        .order_by(func.coalesce(uso.c.n, 0).desc(), CasoUso.nombre)
        .offset((max(pagina, 1) - 1) * tamano).limit(min(tamano, 200))
    ).all()
    items = [CasoUsoOut.model_validate(cu).model_copy(update={"total_casos": n}) for cu, n in filas]
    return {"total": total, "items": items}


@router.get("/casos-uso/{cid}", response_model=CasoUsoOut)
def obtener(cid: int, db: Session = Depends(get_db), _=Depends(requiere("kb.ver"))):
    cu = db.get(CasoUso, cid)
    if not cu:
        raise HTTPException(404, "Caso de uso no encontrado")
    n = db.scalar(select(func.count()).select_from(Caso).where(Caso.caso_uso_id == cid))
    return CasoUsoOut.model_validate(cu).model_copy(update={"total_casos": n})


def _validar_nombre(db: Session, datos: CasoUsoIn, excluir: int | None = None):
    q = select(CasoUso).where(func.lower(CasoUso.nombre) == datos.nombre.strip().lower(),
                              CasoUso.servicio == datos.servicio)
    if excluir:
        q = q.where(CasoUso.id != excluir)
    if db.scalar(q):
        raise HTTPException(409, "Ya existe un caso de uso con ese nombre")


@router.post("/casos-uso", response_model=CasoUsoOut, status_code=201)
def crear(datos: CasoUsoIn, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("kb.editar"))):
    _validar_nombre(db, datos)
    cu = CasoUso(**datos.model_dump(), origen="manual")
    cu.nombre = cu.nombre.strip()
    db.add(cu)
    registrar(db, yo, "crear", f"el caso de uso {cu.nombre}")
    db.commit()
    db.refresh(cu)
    return CasoUsoOut.model_validate(cu)


@router.put("/casos-uso/{cid}", response_model=CasoUsoOut)
def editar(cid: int, datos: CasoUsoIn, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("kb.editar"))):
    cu = db.get(CasoUso, cid)
    if not cu:
        raise HTTPException(404, "Caso de uso no encontrado")
    _validar_nombre(db, datos, excluir=cid)
    cambios = aplicar(cu, datos.model_dump())
    if cambios:
        registrar(db, yo, "editar", f"el caso de uso {cu.nombre}", cambios)
    db.commit()
    db.refresh(cu)
    return obtener(cid, db)


@router.patch("/casos-uso/{cid}/estado", response_model=CasoUsoOut)
def cambiar_estado(cid: int, datos: EstadoIn, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("kb.editar"))):
    """Deshabilitado no aparece al registrar casos; los casos que lo usan no cambian."""
    cu = db.get(CasoUso, cid)
    if not cu:
        raise HTTPException(404, "Caso de uso no encontrado")
    if cu.activo != datos.activo:
        cu.activo = datos.activo
        registrar(db, yo, "habilitar" if cu.activo else "deshabilitar", f"el caso de uso {cu.nombre}")
        db.commit()
        db.refresh(cu)
    return obtener(cid, db)


@router.delete("/casos-uso/{cid}", status_code=204)
def borrar(cid: int, db: Session = Depends(get_db), yo: Usuario = Depends(requiere("kb.eliminar"))):
    cu = db.get(CasoUso, cid)
    if not cu:
        raise HTTPException(404, "Caso de uso no encontrado")
    n = db.scalar(select(func.count()).select_from(Caso).where(Caso.caso_uso_id == cid))
    eliminar(db, yo, cu, f"el caso de uso {cu.nombre}", f"{n} caso{'s' * (n > 1)}" if n else None)
