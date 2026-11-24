"""Modelo de datos de la plataforma SOC/NOC."""
from datetime import date, datetime

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String, Text,
    UniqueConstraint, func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

ROLES = ("N1", "N2", "N3", "LIDER", "CISO", "ADMIN")
REVISIONES = ("PENDIENTE", "REVISADO", "OBSERVADO")
SERVICIOS = ("SOC", "NOC")
CRITICIDADES = ("Crítica", "Alta", "Media", "Baja")
ESTADOS = ("SIN_RETRO", "CON_RETRO", "CERRADO")


def _in(col: str, valores: tuple[str, ...]) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in valores)})"


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (CheckConstraint(_in("rol", ROLES), name="ck_usuario_rol"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario: Mapped[str] = mapped_column(String(60), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(160))
    rol: Mapped[str] = mapped_column(String(20), default="N1")
    # Sin clave = no puede iniciar sesión (p. ej. analistas creados por la migración)
    password_hash: Mapped[str | None] = mapped_column(String(100))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(200))
    servicio_soc: Mapped[bool] = mapped_column(Boolean, default=True)
    servicio_noc: Mapped[bool] = mapped_column(Boolean, default=False)
    # Día del mes en que inicia el periodo del informe (16 = del 16 al 15, 1 = mes calendario)
    dia_corte: Mapped[int] = mapped_column(Integer, default=1)
    eps_contratados: Mapped[int | None] = mapped_column(Integer)
    fuentes_licencia: Mapped[int | None] = mapped_column(Integer)
    glpi_entidad_id: Mapped[int | None] = mapped_column(Integer)
    # Destinatarios del correo de alerta. Solo se aceptan direcciones de los dominios del cliente (o propios).
    correos_para: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    correos_cc: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    correos_dominios: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    correos_por: Mapped[str | None] = mapped_column(String(120))      # quién los modificó por última vez
    correos_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    # Logo para la presentación (PNG o JPG ya recortado). logo_claro: es blanco y va sobre fondo oscuro
    logo: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    logo_mime: Mapped[str | None] = mapped_column(String(20))
    logo_claro: Mapped[bool | None] = mapped_column(Boolean)

    @property
    def tiene_logo(self) -> bool:
        return self.logo_mime is not None

    @property
    def total_correos(self) -> int:
        return len(self.correos_para or [])

    @property
    def etiqueta(self) -> str:
        return f"{self.codigo} - {self.nombre}"


class Tactica(Base):
    """Catálogo de tácticas MITRE ATT&CK (nombres en español)."""
    __tablename__ = "tacticas"

    id: Mapped[str] = mapped_column(String(10), primary_key=True)  # TA0001
    nombre: Mapped[str] = mapped_column(String(80), unique=True)
    nombre_en: Mapped[str] = mapped_column(String(80))
    orden: Mapped[int] = mapped_column(Integer)


class CasoUso(Base):
    """Base de conocimiento: casos de uso / reglas con su plantilla de reporte."""
    __tablename__ = "casos_uso"
    __table_args__ = (
        CheckConstraint(_in("servicio", SERVICIOS), name="ck_casouso_servicio"),
        Index("ix_casos_uso_nombre_servicio", text("lower(nombre)"), "servicio", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(Text)
    servicio: Mapped[str] = mapped_column(String(3), default="SOC")
    criticidad: Mapped[str | None] = mapped_column(String(10))
    es_auditoria: Mapped[bool] = mapped_column(Boolean, default=False)
    tecnica: Mapped[str | None] = mapped_column(Text)
    tecnica_id: Mapped[str | None] = mapped_column(String(20))  # T1110.001
    tactica_id: Mapped[str | None] = mapped_column(ForeignKey("tacticas.id"))
    tecnologia: Mapped[str | None] = mapped_column(Text)
    funcionalidad: Mapped[str | None] = mapped_column(Text)
    resumen_ejecutivo: Mapped[str | None] = mapped_column(Text)
    acciones_recomendadas: Mapped[str | None] = mapped_column(Text)
    guia_analisis: Mapped[str | None] = mapped_column(Text)
    observaciones: Mapped[str | None] = mapped_column(Text)
    origen: Mapped[str] = mapped_column(String(30), default="manual")
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tactica: Mapped[Tactica | None] = relationship(lazy="joined")


class Consecutivo(Base):
    """Último número asignado por servicio (WX#### para SOC, WXNOC### para NOC)."""
    __tablename__ = "consecutivos"

    servicio: Mapped[str] = mapped_column(String(3), primary_key=True)
    ultimo: Mapped[int] = mapped_column(Integer, default=0)


class Caso(Base):
    __tablename__ = "casos"
    __table_args__ = (
        CheckConstraint(_in("servicio", SERVICIOS), name="ck_caso_servicio"),
        CheckConstraint(_in("estado", ESTADOS), name="ck_caso_estado"),
        CheckConstraint(f"revision IS NULL OR {_in('revision', REVISIONES)}", name="ck_caso_revision"),
        CheckConstraint(f"criticidad IS NULL OR {_in('criticidad', CRITICIDADES)}", name="ck_caso_criticidad"),
        Index("ix_casos_cliente_fecha", "cliente_id", "fecha_evento"),
        Index("ix_casos_analista_fecha", "analista_id", "fecha_evento"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True)
    servicio: Mapped[str] = mapped_column(String(3), default="SOC")
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"))
    analista_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    caso_uso_id: Mapped[int | None] = mapped_column(ForeignKey("casos_uso.id"))

    alerta: Mapped[str] = mapped_column(Text)
    criticidad: Mapped[str | None] = mapped_column(String(10), index=True)
    tecnica: Mapped[str | None] = mapped_column(Text)
    tactica_id: Mapped[str | None] = mapped_column(ForeignKey("tacticas.id"))
    tactica_original: Mapped[str | None] = mapped_column(Text)  # texto tal cual venía en el Excel

    resumen_ejecutivo: Mapped[str | None] = mapped_column(Text)
    analisis: Mapped[str | None] = mapped_column(Text)
    acciones_recomendadas: Mapped[str | None] = mapped_column(Text)
    geolocalizacion: Mapped[str | None] = mapped_column(Text)
    reporting_ip: Mapped[str | None] = mapped_column(Text)
    log_evento: Mapped[str | None] = mapped_column(Text)

    # Fecha/hora completas (antes: fecha y horas en columnas separadas)
    fecha_evento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    # Día con el que el caso cuenta en informes, filtros y tablero: la columna "Fecha" de la bitácora
    # (casos importados) o el día del reporte al cliente (casos creados en la plataforma)
    fecha_bitacora: Mapped[date | None] = mapped_column(Date, index=True)
    fecha_reporte: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    estado: Mapped[str] = mapped_column(String(12), default="SIN_RETRO", index=True)
    acciones_cliente: Mapped[str | None] = mapped_column(Text)
    # Revisión posterior de los casos creados por un N1 (NULL = no requiere: N2 o superior, o importado)
    revision: Mapped[str | None] = mapped_column(String(10), index=True)
    revisado_por: Mapped[str | None] = mapped_column(String(120))
    revisado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    glpi_ticket_id: Mapped[int | None] = mapped_column(Integer)
    # Estado del ticket en GLPI: 1 Nuevo, 2 En curso (asignado), 3 En curso (planificado), 4 En espera, 5 Resuelto, 6 Cerrado
    glpi_estado: Mapped[int | None] = mapped_column(Integer)
    glpi_error: Mapped[str | None] = mapped_column(Text)
    glpi_sincronizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    origen: Mapped[str] = mapped_column(String(20), default="app")  # app | migracion
    # Anulado: conserva su número y su historial, pero no cuenta en tablero ni informes (usar VIGENTE en toda cifra)
    anulado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulado_por: Mapped[str | None] = mapped_column(String(120))
    anulado_motivo: Mapped[str | None] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    cliente: Mapped[Cliente] = relationship(lazy="joined")
    analista: Mapped[Usuario | None] = relationship(lazy="joined")
    tactica: Mapped[Tactica | None] = relationship(lazy="joined")
    adjuntos: Mapped[list["Adjunto"]] = relationship(order_by="Adjunto.id", cascade="all, delete-orphan")
    seguimientos: Mapped[list["Seguimiento"]] = relationship(
        back_populates="caso", order_by="Seguimiento.creado_en", cascade="all, delete-orphan"
    )

    @property
    def minutos_respuesta(self) -> int | None:
        if self.fecha_evento and self.fecha_reporte:
            return int((self.fecha_reporte - self.fecha_evento).total_seconds() // 60)
        return None


# Condición que debe llevar toda cifra de casos
VIGENTE = Caso.anulado_en.is_(None)


class Seguimiento(Base):
    """Historial de comentarios del caso (reemplaza columnas Comentario N2…N10)."""
    __tablename__ = "seguimientos"

    id: Mapped[int] = mapped_column(primary_key=True)
    caso_id: Mapped[int] = mapped_column(ForeignKey("casos.id", ondelete="CASCADE"), index=True)
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    autor_nombre: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(String(20), default="comentario")  # comentario | cliente | estado
    comentario: Mapped[str] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    caso: Mapped[Caso] = relationship(back_populates="seguimientos")


class Adjunto(Base):
    """Archivos del caso. EVIDENCIA: imagen que sale en el recuadro del correo; ADJUNTO: archivo pegado al correo."""
    __tablename__ = "adjuntos"
    __table_args__ = (CheckConstraint("tipo IN ('EVIDENCIA', 'ADJUNTO')", name="ck_adjunto_tipo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    caso_id: Mapped[int] = mapped_column(ForeignKey("casos.id", ondelete="CASCADE"), index=True)
    nombre: Mapped[str] = mapped_column(String(160))
    tipo: Mapped[str] = mapped_column(String(10))
    mime: Mapped[str] = mapped_column(String(100))
    tamano: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    ancho: Mapped[int | None] = mapped_column(Integer)
    incluir: Mapped[bool] = mapped_column(Boolean, default=True)     # va en el correo al cliente
    contenido: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)  # no se carga al listar
    subido_por: Mapped[str] = mapped_column(String(120))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Importacion(Base):
    """Historial de importaciones de bitácoras Excel (incluye simulaciones)."""
    __tablename__ = "importaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    archivo: Mapped[str] = mapped_column(Text)
    hoja: Mapped[str] = mapped_column(Text)
    modo: Mapped[str] = mapped_column(String(20))
    simulacion: Mapped[bool] = mapped_column(Boolean, default=True)
    exito: Mapped[bool] = mapped_column(Boolean, default=True)
    mensaje: Mapped[str | None] = mapped_column(Text)
    resultado: Mapped[dict | None] = mapped_column(JSONB)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    usuario_nombre: Mapped[str] = mapped_column(String(120))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImagenInforme(Base):
    """Imágenes de los boletines de un informe (boletines[].imagen_id)."""
    __tablename__ = "informe_imagenes"

    id: Mapped[int] = mapped_column(primary_key=True)
    informe_id: Mapped[int] = mapped_column(ForeignKey("informes.id", ondelete="CASCADE"), index=True)
    mime: Mapped[str] = mapped_column(String(20))
    ancho: Mapped[int] = mapped_column(Integer)
    alto: Mapped[int] = mapped_column(Integer)
    contenido: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)


class Configuracion(Base):
    """Parámetros cambiados desde la pantalla. Los secretos van cifrados (ver configuracion.py)."""
    __tablename__ = "configuracion"

    clave: Mapped[str] = mapped_column(String(60), primary_key=True)
    valor: Mapped[str | None] = mapped_column(Text)
    por: Mapped[str] = mapped_column(String(120))
    en: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Conexion(Base):
    """Otras APIs registradas. La clave va cifrada."""
    __tablename__ = "conexiones"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), unique=True)
    url: Mapped[str] = mapped_column(String(500))
    autenticacion: Mapped[str] = mapped_column(String(10))
    cabecera: Mapped[str | None] = mapped_column(String(60))
    usuario: Mapped[str | None] = mapped_column(String(120))
    clave: Mapped[str | None] = mapped_column(Text)
    notas: Mapped[str | None] = mapped_column(String(500))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    por: Mapped[str] = mapped_column(String(120))
    en: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ClaveApi(Base):
    """Claves de solo lectura para otros sistemas. Solo se guarda la huella."""
    __tablename__ = "claves_api"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80))
    prefijo: Mapped[str] = mapped_column(String(12))
    huella: Mapped[str] = mapped_column(String(64), unique=True)
    permisos: Mapped[list] = mapped_column(JSONB)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))  # NULL = todos
    vence_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revocada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_uso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creada_por: Mapped[str] = mapped_column(String(120))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    cliente: Mapped[Cliente | None] = relationship(lazy="joined")


class Aviso(Base):
    """Cola de avisos internos por correo."""
    __tablename__ = "avisos"
    __table_args__ = (CheckConstraint("estado IN ('PENDIENTE', 'ENVIADO', 'ERROR', 'DESCARTADO')", name="ck_aviso_estado"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(20))
    asunto: Mapped[str] = mapped_column(String(250))
    cuerpo: Mapped[str] = mapped_column(Text)
    para: Mapped[list] = mapped_column(JSONB, default=list)     # vacío = destinatarios configurados
    estado: Mapped[str] = mapped_column(String(12), index=True)
    intentos: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    proximo: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    enviado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Auditoria(Base):
    """Registro de cambios administrativos. Guarda texto y no llaves: sobrevive a lo que se elimina."""
    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario: Mapped[str] = mapped_column(String(200))
    accion: Mapped[str] = mapped_column(String(20))
    objeto: Mapped[str] = mapped_column(String(400))
    detalle: Mapped[str | None] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Informe(Base):
    """Informe mensual de un cliente (un periodo según su día de corte)."""
    __tablename__ = "informes"
    __table_args__ = (
        UniqueConstraint("cliente_id", "periodo_inicio", name="uq_informe_cliente_periodo"),
        CheckConstraint("estado IN ('BORRADOR', 'FINAL')", name="ck_informe_estado"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), index=True)
    periodo_inicio: Mapped[date] = mapped_column(Date)
    periodo_fin: Mapped[date] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String(10), default="BORRADOR")
    eps_promedio: Mapped[float | None] = mapped_column(Float)
    fuentes_integradas: Mapped[int | None] = mapped_column(Integer)
    boletines_enviados: Mapped[int | None] = mapped_column(Integer)
    # Anexos de FortiSIEM ya agregados: países, puertos, ataques IPS, fuentes
    anexos: Mapped[dict] = mapped_column(JSONB, default=dict)
    archivos: Mapped[list] = mapped_column(JSONB, default=list)       # archivos cargados (nombre, tipos, fecha)
    boletines: Mapped[list] = mapped_column(JSONB, default=list)      # boletines de inteligencia del periodo
    textos: Mapped[dict] = mapped_column(JSONB, default=dict)         # textos editables del informe
    metricas: Mapped[dict | None] = mapped_column(JSONB)              # foto de las métricas al marcarlo FINAL
    creado_por: Mapped[str] = mapped_column(String(120))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    cliente: Mapped[Cliente] = relationship(lazy="joined")
    imagenes: Mapped[list["ImagenInforme"]] = relationship(order_by="ImagenInforme.id", cascade="all, delete-orphan")
