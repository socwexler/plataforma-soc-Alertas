from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_ignore_empty=True)

    database_url: str
    jwt_secret: str
    jwt_horas: int = 10
    admin_usuario: str = "admin"
    admin_password: str | None = None
    # SLA de notificación por criticidad: minutos entre la alerta del SIEM y el reporte al cliente
    sla_critica: int = 35
    sla_alta: int = 45
    sla_media: int = 120
    sla_baja: int = 240
    zona_horaria: str = "America/Bogota"

    # GLPI 10 (API REST). Si glpi_url está vacío la integración queda desactivada.
    glpi_url: str | None = None              # p. ej. https://glpi.wexler.com.co/apirest.php
    glpi_app_token: str | None = None
    glpi_user_token: str | None = None       # token de API del usuario de servicio
    glpi_verificar_ssl: bool = True
    glpi_tipo_ticket: int = 1                # 1 = Incidente, 2 = Solicitud
    glpi_categoria_id: int | None = None     # categoría ITIL para los tickets del SOC
    glpi_origen_id: int | None = None        # origen de la solicitud (requesttypes_id)
    glpi_crear_por_defecto: bool = True      # casilla "crear ticket" marcada en el formulario
    glpi_resolver_al_cerrar: bool = True     # al cerrar el caso, se registra la solución en GLPI
    glpi_sync_minutos: int = 10              # cada cuánto se consulta el estado de los tickets abiertos
    glpi_url_tickets: str | None = None      # URL web para abrir un ticket; por defecto se deriva de glpi_url
    # Alertas por tratar: tickets que el SIEM crea en GLPI por correo. Se reconocen por al menos uno de los criterios.
    glpi_alertas_activo: bool = False
    glpi_alertas_origen_id: int | None = None      # origen de la solicitud de esos tickets (p. ej. Correo electrónico)
    glpi_alertas_categoria_id: int | None = None   # categoría ITIL de esos tickets
    glpi_alertas_texto: str | None = None          # texto que lleva el título de esos tickets
    glpi_alertas_minutos: int = 2                  # cada cuánto se buscan tickets nuevos
    glpi_alertas_dias: int = 3                     # antigüedad máxima de los tickets que se traen

    # Correo de notificación al cliente
    correo_cc: str = "soc@wexler.com.co"                 # copia fija en todos los correos
    correo_cco: str = "alertassoc@wexler.com.co"         # copia oculta fija
    correo_dominio_propio: str = "wexler.com.co"         # siempre permitido
    correo_plazo_horas: int = 48
    correo_tlp: str = "TLP:RED"
    # Mapa de la presentación: teselas {z}/{y}/{x} que carga el navegador. "no" = sin mapa de fondo, solo ubicaciones
    mapa_base: str = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/OSM_Land_Water_Map/default/GoogleMapsCompatible_Level9/{z}/{y}/{x}.png"
    mapa_lineas: str = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/Reference_Features/default/GoogleMapsCompatible_Level9/{z}/{y}/{x}.png"
    mapa_atribucion: str = "Mapa: NASA GIBS · © OpenStreetMap"
    correo_max_mb: int = 15                              # total de archivos en un correo
    adjunto_max_mb: int = 15                             # por archivo
    adjuntos_caso_max_mb: int = 60                       # por caso
    mapa_activo: bool = True
    mostrar_tiempos: bool = False                        # tiempos de notificación y SLA en la ejecutiva, el Word y su PDF
    url_plataforma: str | None = None                    # para los enlaces de los avisos

    # Avisos internos por correo (se administran en Configuración)
    avisos_activo: bool = False
    smtp_servidor: str | None = None
    smtp_puerto: int = 587
    smtp_seguridad: str = "STARTTLS"                     # STARTTLS | SSL | NINGUNA
    smtp_verificar_ssl: bool = True
    smtp_usuario: str | None = None
    smtp_clave: str | None = None
    smtp_remitente: str | None = None
    avisos_destino: str | None = None
    aviso_por_revisar: bool = True
    avisos_agrupar_min: int = 15
    aviso_devuelto: bool = True
    aviso_glpi: bool = True
    aviso_alerta_sin_tomar: bool = True       # una alerta de GLPI supera su SLA sin que nadie la tome

    # FortiSIEM (por ahora solo se prueba la conexión; los anexos se cargan por archivo)
    fortisiem_url: str | None = None
    fortisiem_organizacion: str = "super"
    fortisiem_usuario: str | None = None
    fortisiem_clave: str | None = None
    fortisiem_verificar_ssl: bool = True

    # SharePoint: anexos del informe (solo lectura). no | carpeta (sincronizada y montada en /sharepoint) | graph
    sharepoint_modo: str = "no"
    sharepoint_ruta: str | None = None             # carpeta base dentro de la montada o de la biblioteca
    sharepoint_sitio: str | None = None            # https://empresa.sharepoint.com/sites/SOC
    sharepoint_biblioteca: str | None = None       # vacío = la biblioteca de documentos del sitio
    sharepoint_tenant: str | None = None
    sharepoint_cliente_id: str | None = None
    sharepoint_secreto: str | None = None
    sharepoint_login_url: str = "https://login.microsoftonline.com"
    sharepoint_graph_url: str = "https://graph.microsoft.com/v1.0"
    # Carpeta de cada anexo: su nombre o el número con que empieza («04» = «04 WX - Promedio Mensual EPS»)
    sharepoint_carpeta_eps: str = "04"
    sharepoint_carpeta_fuentes: str = "07"
    sharepoint_carpeta_paises_entrantes: str = "10"
    sharepoint_carpeta_paises_salientes: str = "12"
    sharepoint_carpeta_puertos: str = "14"
    sharepoint_carpeta_ips: str = "15"

    @property
    def sla_objetivos(self) -> dict[str, int]:
        return {"Crítica": self.sla_critica, "Alta": self.sla_alta, "Media": self.sla_media, "Baja": self.sla_baja}

    @property
    def glpi_activo(self) -> bool:
        return bool(self.glpi_url and self.glpi_app_token and self.glpi_user_token)

    @property
    def glpi_url_web(self) -> str | None:
        if self.glpi_url_tickets:
            return self.glpi_url_tickets
        if self.glpi_url:
            return self.glpi_url.rsplit("/apirest.php", 1)[0] + "/front/ticket.form.php?id="
        return None


settings = Settings()
