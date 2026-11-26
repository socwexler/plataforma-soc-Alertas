from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Rol = Literal["N1", "N2", "N3", "LIDER", "CISO", "ADMIN"]
Revision = Literal["PENDIENTE", "REVISADO", "OBSERVADO"]
Servicio = Literal["SOC", "NOC"]
Criticidad = Literal["Crítica", "Alta", "Media", "Baja"]
Estado = Literal["SIN_RETRO", "CON_RETRO", "CERRADO"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Usuarios ----------
class UsuarioOut(ORM):
    id: int
    usuario: str
    nombre: str
    email: str | None
    rol: Rol
    activo: bool
    puede_ingresar: bool = False
    permisos: list[str] = []
    uso: str | None = None   # historial que impide eliminarlo


class UsuarioIn(BaseModel):
    usuario: str = Field(min_length=3, max_length=60)
    nombre: str = Field(min_length=3, max_length=120)
    email: str | None = None
    rol: Rol = "N1"
    activo: bool = True
    password: str | None = Field(default=None, min_length=8)


class EstadoIn(BaseModel):
    activo: bool


class CambioClave(BaseModel):
    actual: str
    nueva: str = Field(min_length=8)


# ---------- Clientes ----------
class ClienteIn(BaseModel):
    codigo: str = Field(min_length=2, max_length=20)
    nombre: str = Field(min_length=2, max_length=200)
    servicio_soc: bool = True
    servicio_noc: bool = False
    dia_corte: int = Field(default=1, ge=1, le=28)
    eps_contratados: int | None = None
    fuentes_licencia: int | None = None
    glpi_entidad_id: int | None = None
    activo: bool = True


class ClienteOut(ClienteIn, ORM):
    id: int
    total_correos: int = 0
    tiene_logo: bool = False
    logo_claro: bool | None = None
    uso: str | None = None


class CorreosIn(BaseModel):
    """Texto tal como se pega: separado por ; , o saltos de línea, con o sin nombre."""
    para: str = Field(default="", max_length=20000)
    cc: str = Field(default="", max_length=20000)
    dominios: str = Field(default="", max_length=2000)


class ClienteMini(ORM):
    id: int
    codigo: str
    nombre: str


# ---------- Catálogos ----------
class TacticaOut(ORM):
    id: str
    nombre: str
    nombre_en: str


class CasoUsoIn(BaseModel):
    nombre: str = Field(min_length=3, max_length=300)
    servicio: Servicio = "SOC"
    criticidad: Criticidad | None = None
    es_auditoria: bool = False
    tecnica: str | None = None
    tecnica_id: str | None = None
    tactica_id: str | None = None
    tecnologia: str | None = None
    funcionalidad: str | None = None
    resumen_ejecutivo: str | None = None
    acciones_recomendadas: str | None = None
    guia_analisis: str | None = None
    observaciones: str | None = None
    activo: bool = True


class CasoUsoOut(CasoUsoIn, ORM):
    id: int
    origen: str
    tactica: TacticaOut | None
    actualizado_en: datetime
    total_casos: int = 0


class CasoUsoMini(ORM):
    id: int
    nombre: str
    servicio: Servicio
    criticidad: str | None
    tactica_id: str | None
    tiene_plantilla: bool = False


# ---------- Casos ----------
class CasoIn(BaseModel):
    servicio: Servicio = "SOC"
    cliente_id: int
    caso_uso_id: int | None = None
    alerta: str = Field(min_length=3, max_length=300)
    criticidad: Criticidad
    tecnica: str | None = None
    tactica_id: str | None = None
    resumen_ejecutivo: str | None = None
    analisis: str | None = None
    acciones_recomendadas: str | None = None
    geolocalizacion: str | None = None
    reporting_ip: str | None = None
    log_evento: str | None = None
    fecha_evento: datetime
    fecha_reporte: datetime | None = None  # al crear se ignora (hora del servidor); al editar solo la corrige un revisor
    estado: Estado = "SIN_RETRO"
    acciones_cliente: str | None = None
    glpi_ticket_id: int | None = None


class UsuarioMini(ORM):
    id: int
    nombre: str


class SeguimientoIn(BaseModel):
    comentario: str = Field(min_length=1)
    tipo: Literal["comentario", "cliente"] = "comentario"
    publicar_glpi: bool = False


class RevisionIn(BaseModel):
    resultado: Literal["REVISADO", "OBSERVADO"]
    observacion: str | None = None


class AdjuntoOut(ORM):
    id: int
    nombre: str
    tipo: Literal["EVIDENCIA", "ADJUNTO", "GESTION"]
    mime: str
    tamano: int
    incluir: bool
    seguimiento_id: int | None
    subido_por: str
    creado_en: datetime


class AdjuntoIn(BaseModel):
    incluir: bool


class MotivoIn(BaseModel):
    motivo: str

    @field_validator("motivo")
    @classmethod
    def _limpiar(cls, v: str) -> str:
        v = v.strip()
        if not 10 <= len(v) <= 500:
            raise ValueError("escriba entre 10 y 500 caracteres")
        return v


class SeguimientoOut(ORM):
    id: int
    autor_nombre: str
    tipo: str
    comentario: str
    creado_en: datetime
    glpi_error: str | None = None


class CasoListaOut(ORM):
    id: int
    numero: str
    servicio: Servicio
    cliente: ClienteMini
    analista: UsuarioMini | None
    alerta: str
    criticidad: str | None
    tactica: TacticaOut | None
    fecha_evento: datetime | None
    fecha_reporte: datetime | None
    minutos_respuesta: int | None
    sla_minutos: int
    dentro_sla: bool | None
    estado: Estado
    glpi_ticket_id: int | None
    glpi_estado: int | None = None
    revision: Revision | None = None
    anulado_en: datetime | None = None


class CasoOut(CasoListaOut):
    cliente_id: int   # el formulario de edición lo necesita para mostrar el cliente elegido
    caso_uso_id: int | None
    tecnica: str | None
    tactica_id: str | None
    tactica_original: str | None
    resumen_ejecutivo: str | None
    analisis: str | None
    acciones_recomendadas: str | None
    geolocalizacion: str | None
    reporting_ip: str | None
    log_evento: str | None
    acciones_cliente: str | None
    revisado_por: str | None
    revisado_en: datetime | None
    anulado_por: str | None
    anulado_motivo: str | None
    origen: str
    creado_en: datetime
    glpi_error: str | None
    glpi_sincronizado_en: datetime | None
    actualizado_en: datetime
    seguimientos: list[SeguimientoOut]
    adjuntos: list[AdjuntoOut] = []


class Pagina(BaseModel):
    total: int
    items: list


class PaginaCasos(Pagina):
    items: list[CasoListaOut]


class PaginaCasosUso(Pagina):
    items: list[CasoUsoOut]


# ---------- Alertas por tratar (tickets del SIEM en GLPI) ----------
class AlertaOut(ORM):
    id: int
    glpi_ticket_id: int
    glpi_estado: int | None
    glpi_entidad_id: int | None
    cliente_id: int | None
    cliente: ClienteMini | None
    titulo: str
    criticidad: str | None
    fecha_alerta: datetime
    estado: Literal["POR_REPORTAR", "EN_GESTION", "REPORTADA", "CERRADA_GLPI"]
    analista: UsuarioMini | None
    tomada_en: datetime | None
    caso_id: int | None
    caso_numero: str | None
    reportada_en: datetime | None
    cerrada_en: datetime | None
    sla_minutos: int
    minutos: int | None = None      # en espera (pendientes) o hasta el reporte (reportadas)


class AlertaDetalle(AlertaOut):
    contenido: str | None
