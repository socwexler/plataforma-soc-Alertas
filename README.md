# Plataforma SOC/NOC – Wexler

Reemplaza la bitácora en Excel por una aplicación web con base de datos.

**Fase 1:**
- Registro de casos por los analistas N1, con numeración automática WX/WXNOC.
- Base de conocimiento de casos de uso.
- Notificación al cliente lista para copiar en el correo.
- Seguimiento de cada caso con historial.
- Administración de clientes y usuarios.
- Importación de la bitácora Excel desde la aplicación.

**Fase 2:**
- Tickets en GLPI 10: se crean al registrar el caso, con reintento, seguimientos, solución al cerrar y sincronización del estado.
- Tablero: casos por analista, criticidad por día, estados, tiempos de reporte y SLA, carga por hora, alertas y clientes.
- Migraciones de esquema con Alembic: las actualizaciones no borran datos.

**Fase 3 (esta versión):**
- Informe mensual por cliente, calculado desde la bitácora y los anexos de FortiSIEM.
- **Informe ejecutivo en Word** sobre la plantilla corporativa *Plantilla Informes Técnicos y Ejecutivo 2026 - SOC para cliente*.
- **El mismo informe en PDF**, con idéntico formato.
- **Presentación en HTML/CSS** con la identidad Wexler: modo presentación y exportación a PDF.

| Fase | Contenido |
|------|-----------|
| 4 | API de FortiSIEM (anexos automáticos), Directorio Activo (LDAP), envío del informe por correo |

## Arquitectura

```
navegador ──► web (nginx + React) ──/api──► api (FastAPI, Python) ──► db (PostgreSQL 16)
                                               └──► convertidor (Gotenberg: LibreOffice + Chromium)
```

El `convertidor` es [Gotenberg](https://gotenberg.dev) con las fuentes de la plantilla (Lato y Montserrat, licencia OFL, en `convertidor/fuentes`). Convierte el Word a PDF y la presentación HTML a PDF. Solo es accesible desde la red interna de Docker.

Todo corre con Docker Compose. Solo se publica el puerto de `web` (8080 por defecto); la base de datos y la API quedan en la red interna de Docker.

## Instalación en el servidor Linux

1. Instale Docker Engine y el plugin de Compose.
2. Copie la carpeta `plataforma-soc` al servidor.
3. Cree la configuración a partir del ejemplo y edítela. Use claves largas y aleatorias para `POSTGRES_PASSWORD`, `JWT_SECRET` y `ADMIN_PASSWORD`; para generar una puede usar `openssl rand -base64 32`.
   ```bash
   cp .env.example .env
   nano .env
   ```
4. Levante los servicios:
   ```bash
   docker compose up -d --build
   ```
5. Entre a `http://<servidor>:8080` con el usuario `ADMIN_USUARIO` y la clave `ADMIN_PASSWORD`. Para publicar la aplicación con HTTPS, póngala detrás del proxy inverso corporativo.

## Correo de alerta al cliente

Nadie escribe destinatarios al enviar: salen del cliente del caso.

- **Configuración:** *Clientes → Correos* (Líder SOC y Administrador). Se definen los dominios del cliente y las listas Para y CC; se puede pegar la lista de Outlook. Queda quién y cuándo las modificó.
- **Validaciones al guardar y al generar:** solo direcciones de los dominios del cliente o del dominio propio; un dominio no puede pertenecer a dos clientes; no se aceptan dominios públicos (gmail.com…).
- **Uso:** en el caso, pestaña *Correo al cliente* → *Generar borrador de Outlook*. Descarga un `.eml` con destinatarios, asunto `WX…_CLIENTE_Alerta` y la plantilla. **No envía nada:** el analista lo abre en Outlook, revisa destinatarios y archivos, y lo envía. El borrador queda en el seguimiento del caso.
- **Bloquea** si el cliente no tiene destinatarios, está inactivo o hay direcciones fuera de sus dominios. **Pide confirmar** si el contenido menciona el dominio de otro cliente, faltan textos, el caso está devuelto o ya se generó un borrador.
- Copia fija, copia oculta, plazo y marca TLP: variables `CORREO_*` del `.env`.
- Imágenes: `backend/app/recursos_correo` (`banner.png`, `logo.png`).

## Evidencias y adjuntos

- **Evidencia:** imagen PNG o JPG; sale dentro del recuadro *Evidencias* de la plantilla: en la pestaña *Notificación* (y al copiarla) y en el borrador de Outlook. Se puede pegar un recorte con Ctrl+V. Se guarda sin metadatos (autor, equipo, ubicación).
- **Cambio de estado:** al marcar un estado (o con *Agregar evidencia*) se puede escribir un detalle y cargar el soporte: correo (`.msg`, `.eml`), imagen o documento. Lo hacen todos los roles menos el CISO, en cualquier caso vigente aunque no sea propio. Queda en el seguimiento con el nombre de quien lo hizo; es interno: no va en la plantilla ni en el correo, y no devuelve el caso a revisión. Los correos que traen ejecutables, HTML o macros se rechazan. Para guardar un correo en Outlook: *Archivo → Guardar como*.
- **Adjunto:** pdf, docx, xlsx, pptx, csv, txt, log, json, zip, png, jpg; va pegado al correo.
- *En el correo* decide si el archivo se envía al cliente; desmarcado queda solo en el caso.
- **Quién:** los ven y descargan todos los roles; los agrega o quita quien puede editar el caso (los del cambio de estado los agrega cualquier analista). Todo queda en el seguimiento. Si un N1 cambia archivos de un caso revisado, vuelve a *Por revisar*.
- **Se rechazan** ejecutables, macros, HTML, SVG, zip con ejecutables y archivos cuyo contenido no corresponde a su extensión. **No hay antivirus:** no suba muestras de malware.
- **Límites** (`.env`): `ADJUNTO_MAX_MB` por archivo (15), `CORREO_MAX_MB` por correo (15; lo bloquea), `ADJUNTOS_CASO_MAX_MB` por caso (60).
- **Avisa** si el nombre o el texto de un archivo menciona a otro cliente. Solo lee el texto de csv, txt, log y json; no revisa PDF, Word, Excel, zip ni imágenes.
- Se guardan en la base de datos: entran en el respaldo y lo hacen crecer. No se suben a GLPI.
- La importación *Reemplazar* se bloquea si hay casos importados con archivos.

## Integración con GLPI 10

GLPI se usa para que el cliente tenga un número de ticket y para hacerle seguimiento; el detalle del caso vive en la plataforma.

### Configuración

1. **En GLPI:**
   - En *Configuración → General → API*, habilite la API REST y el inicio de sesión con token externo.
   - Cree un *cliente de API*; ese es el `GLPI_APP_TOKEN`.
   - Cree un usuario de servicio con permiso para crear tickets en las entidades de los clientes.
   - En su ficha, genere el *Token de API*; ese es el `GLPI_USER_TOKEN`.
2. **En `.env`:**
   - Complete `GLPI_URL` (termina en `/apirest.php`), `GLPI_APP_TOKEN` y `GLPI_USER_TOKEN`.
   - Opcional: `GLPI_CATEGORIA_ID` y `GLPI_ORIGEN_ID`.
   - Reinicie con `docker compose up -d`.
3. **En la plataforma:**
   - En **Clientes**, asigne a cada cliente su **ID de entidad en GLPI**.
   - En el panel *Integración con GLPI* de esa misma página, use **Probar conexión**.

### Funcionamiento

| Momento | Qué pasa en GLPI |
|---|---|
| Al guardar un caso nuevo (casilla *Crear ticket en GLPI*) | Se crea el ticket en la entidad del cliente. El título es `[WX…] CLIENTE - Alerta - Criticidad` y el contenido es la notificación del caso. La urgencia y el impacto salen de la criticidad (Crítica 5, Alta 4, Media 3, Baja 2). |
| Si GLPI falla o el cliente no tiene entidad | El caso **se guarda igual**. El error se muestra en el detalle con el botón **Reintentar crear ticket**. |
| Comentario con *Publicar en GLPI* | Se agrega como seguimiento del ticket. |
| El caso pasa a **Cerrado** | Se registra la solución en el ticket, con las acciones del cliente (`GLPI_RESOLVER_AL_CERRAR`). |
| Cada `GLPI_SYNC_MINUTOS` | Se consulta el estado de los tickets abiertos de los últimos 90 días. Los cambios quedan en el historial del caso, y el estado se ve en la lista, el detalle y el tablero. |

### Pruebas sin GLPI real

`backend/scripts/glpi_simulado.py` imita la API de GLPI 10. Arranque el simulador dentro del contenedor de la API:

```bash
docker compose exec -d -e SIM_APP_TOKEN=app -e SIM_USER_TOKEN=user api uvicorn scripts.glpi_simulado:app --port 8099
```

En `.env`, apunte la integración al simulador:

```
GLPI_URL=http://127.0.0.1:8099/apirest.php
GLPI_APP_TOKEN=app
GLPI_USER_TOKEN=user
```

La entidad 999 simula un error de permisos.

## Tablero

En el menú **Tablero** hay filtros de periodo (con accesos rápidos: hoy, 7 días, 30 días, este mes, mes anterior, 90 días), cliente, servicio y analista. Muestra:

- **Indicadores:**
  - Casos y su variación frente al periodo anterior.
  - Casos de criticidad alta o crítica.
  - Porcentaje con retroalimentación.
  - Tiempo mediano entre la alerta y el reporte.
  - Porcentaje dentro del SLA (`SLA_MINUTOS`).
  - Tickets GLPI abiertos.
- **Casos por día y criticidad:** gráfico con detalle al pasar el mouse y vista de tabla.
- **Tabla por analista:** casos, alta o crítica, con y sin retroalimentación, tiempo mediano, % SLA, tickets y último caso.
- **Distribuciones:**
  - Estado de los casos y de los tickets GLPI.
  - Tramos de tiempo de reporte.
  - Casos por hora del día, útil para dimensionar turnos 7x24.
  - Top 10 de alertas.
- **Tabla por cliente.**

Al hacer clic en un analista, estado, alerta o cliente se abre la lista de casos ya filtrada.

## Informes mensuales

En el menú **Informes**: elija el cliente y el periodo, y pulse **Crear informe**. Los periodos salen del *día de corte* del cliente; por ejemplo, del 16 al 15 o del 25 al 24.

### Qué se calcula solo, desde la bitácora

- Eventos de los tres últimos periodos por criticidad (SOC y NOC por separado).
- Retroalimentación del cliente y tiempos de notificación.
- Top 10 de alertas, eventos de criticidad alta o crítica y tácticas MITRE ATT&CK.

### Qué se carga en el editor del informe

1. **Anexos de FortiSIEM** (botón *Cargar archivos*). El tipo se reconoce por los encabezados y solo se guarda el resultado agregado. Sirven:

   | Anexo | Archivo |
   |---|---|
   | Países entrantes / salientes | CSV de FortiSIEM (`Pais de Origen` / `Pais de Destino` + `Total`). Se excluye Colombia y los nombres se traducen al español. |
   | Puertos no comunes | CSV con `Puertos Asociados`, `Servicios Asociados`, `Entrante/Saliente`, `Total`. Se descartan los puertos habituales: 80, 443, 22, 3389, 1433, 514… |
   | Ataques IPS | Exporte con `Attack Name`, `Firewall Action`, `COUNT(...)`. Bloqueados = dropped, blocked, reset o deny. |
   | Fuentes integradas | Listado con `Nombre`, `IP`, `TIPO` y estado. |
   | Todo junto | El Excel que hoy alimenta Power BI (uno por cliente), con sus hojas Paises_*, Puertos_*, IPs, Fuentes*, EPS y Boletines_Inteligencia. |

2. **Datos del servicio:** promedio de EPS, fuentes integradas y boletines enviados. Las fuentes y el histórico de EPS se heredan del informe anterior.
3. **Boletines de inteligencia** del periodo.
4. **Textos:** se redactan solos con los datos (resumen del trimestre, alertas, categorías, fuentes, países, IPS, recomendaciones y conclusiones). Se pueden editar, y **Regenerar** vuelve a redactarlos con los datos actuales.

Las secciones sin datos (por ejemplo, sin anexo de IPS) se omiten del informe, y la numeración se ajusta sola.

### Descargas y estados

| Botón | Resultado |
|---|---|
| **Descargar Word** | `.docx` sobre la plantilla corporativa. Detalle abajo. |
| **Descargar PDF** | El mismo Word convertido con LibreOffice, con las fuentes corporativas. |
| **Ver presentación** | Diapositivas 16:9 en HTML/CSS con el logo, la foto de portada y los colores de la plantilla. **Presentar** pasa a pantalla completa (← → para avanzar, Esc para salir) y **Exportar a PDF** la descarga con Chromium. |
| **Presentación PDF** | La misma presentación descargada directo en PDF. |

En el Word:
- Se conservan la portada, el encabezado (código SN-FR-01, versión, página X de Y, TLP) y el pie.
- En la portada se completan el cliente y el periodo.
- El contenido usa los estilos de la plantilla (títulos numerados en rojo y tabla con encabezado rojo).
- La tabla de contenido y los índices de tablas y gráficas llevan los números de página reales, y Word ofrece actualizarlos al abrir el archivo.

Los cuatro botones usan siempre los datos actuales del informe.

La plantilla está en `backend/app/informes/recursos/plantilla_informe.docx`. Para cambiar el diseño, reemplace ese archivo por una nueva versión, conservando los textos "INFORME DE MONITOREO", "Revisión de actividad de cuenta", "1 de agosto de 2026", "Tabla de contenido", "Índice de tablas", "Índice de gráficas" y el título de ejemplo "Titulo", que es donde empieza el contenido.
- **Marcar como final** (Líder SOC o Administrador) congela las cifras: aunque después se editen casos, el informe enviado no cambia. **Volver a borrador** lo desbloquea.

### Presentación ejecutiva

Para enviar al cliente: fondo claro, con más detalle, en PDF o HTML (panel *Presentaciones* del informe).

- **Contenido:** resumen con anillo de retroalimentación y alertas principales, comparativo de tres periodos, comportamiento por día, hora y día de la semana, alertas y técnicas, MITRE, origen y dispositivos, destacados y pendientes de respuesta, fuentes y EPS, mapas, puertos, IPS, boletines, actividades, recomendaciones y anexo con todos los eventos (hasta 400).
- **Actividades y pendientes:** se registran en el informe (frente, responsable, avance, compromiso). Las que no estén al 100 % pasan al informe siguiente.
- No lleva paneles laterales de texto: las gráficas y tablas ocupan toda la hoja. Los textos de resumen y MITRE se siguen usando en el Word y en la presentación interactiva.
- Los **tiempos de notificación y el SLA** no se muestran, salvo que se active *Configuración → General → Mostrar tiempos…* (y el informe conserve el texto *Tiempos de notificación*). Aplica a la presentación ejecutiva, al Word y a su PDF, y queda fijado al marcar el informe como final.
- Las secciones sin datos se omiten. Un informe final congelado antes de la versión 0012 no tiene comportamiento, origen, pendientes ni anexo; vuelva a borrador para incluirlos.

### Presentación interactiva

- Para exponer en reunión: fondo oscuro y animada. *Ver* la abre en el navegador; *Descargar HTML* entrega un solo archivo que se abre con doble clic; *Descargar PDF* la exporta con cada diapositiva en su estado final.
- **Teclas:** ← → avanzar, `I` índice, `N` notas del presentador (los textos del informe), `F` pantalla completa.
- **Interacción:** clic en una criticidad para resaltarla, clic en la agenda para ir a una sección, clic en un boletín para ampliarlo, ayuda al pasar el cursor.
- **Mapa:** ubica los países del anexo (`informes/mapa.py`), con pestañas Entrantes/Salientes, zoom y arrastre. El PDF trae un mapa por sentido. Un país sin ubicación conocida se lista al lado.
- **El fondo del mapa se carga de Internet** (NASA GIBS y OpenStreetMap, sin clave) desde el navegador de quien presenta, y desde el servidor para el PDF. Solo se piden imágenes del mundo; no se envían datos del cliente. Sin conexión quedan las ubicaciones sobre una cuadrícula. Se cambia o desactiva con `MAPA_BASE`, `MAPA_LINEAS`, `MAPA_ATRIBUCION`.
- **Logo del cliente:** *Clientes → Logo* (Líder y Administrador). PNG o JPG hasta 5 MB; se recorta el margen y, si es blanco, se muestra sobre fondo oscuro.
- **Imagen del boletín:** en el editor del informe; también con Ctrl+V. Se ajusta a 2000 px. Al guardar se borran las que ningún boletín usa.
- El logo y las imágenes no salen en el Word ni en el PDF del informe ejecutivo.
- Recursos gráficos: `backend/app/informes/recursos/presentacion` (fotos, logo Wexler, fuentes Sora y Aspekta).

## Importar la bitácora Excel

### Desde la aplicación (recomendado)

Menú **Administración → Importar bitácora** (roles Líder SOC y Administrador):

1. Seleccione el Excel (.xlsx o .xlsm, hasta 50 MB). La aplicación muestra las hojas y cuántos casos tiene cada una.
2. Elija la hoja, el servicio y el modo:

   | Modo | Qué hace | Cuándo usarlo |
   |------|----------|---------------|
   | **Solo casos nuevos** | Agrega los números de reporte que no existen. | Cargas periódicas |
   | **Nuevos y actualizar importados** | Además, actualiza los casos que vinieron del Excel: estado, retroalimentación, acciones del cliente, comentarios N2… | Mientras la bitácora de producción siga en uso en paralelo |
   | **Reemplazar todo lo importado** | Borra los casos que vinieron de Excel y los vuelve a cargar. | Cuando se corrigieron muchos datos en el Excel |

3. Pulse **Simular importación**. Verá los casos nuevos, actualizados, sin cambios y omitidos, más los avisos con el número de fila del Excel. Hasta este paso no se guarda nada.
4. Si todo está bien, pulse **Confirmar e importar**. Cada simulación e importación queda en el historial con el usuario y la fecha.

Garantías:
- Los casos creados en la plataforma nunca se modifican ni se borran por una importación.
- Si un número del Excel ya lo usa un caso de la plataforma, la fila se omite y aparece como aviso.
- Una importación con error no deja cambios a medias.
- No pueden correr dos importaciones al mismo tiempo.

### Desde la línea de comandos

Copie el Excel a la carpeta indicada en `DATOS_DIR` (por defecto `./datos`) y ejecute:

```bash
# Simulación: muestra lo que haría, sin guardar nada
docker compose exec api python -m scripts.migrar_bitacora "/datos/BITACORA.xlsx" --simular

# Carga real (modos: solo_nuevos | actualizar | reemplazar)
docker compose exec api python -m scripts.migrar_bitacora "/datos/BITACORA.xlsx" --modo actualizar

# Bitácora NOC (misma estructura de columnas que la hoja NOC)
docker compose exec api python -m scripts.migrar_bitacora "/datos/BITACORA_NOC.xlsx" --hoja NOC --solo-casos
```

### Cómo se transforman los datos
- **Clientes:** los toma de la hoja `INFORMACION` y de los casos. El día de corte, los EPS contratados y otros datos iniciales se pueden precargar con `datos/clientes.json` (por código de cliente); el resto se ajusta luego en **Clientes**.
- **Analistas:** crea un usuario N1 por cada nombre. Quedan **sin contraseña**, así que el administrador debe asignarla en **Usuarios** antes de que puedan ingresar.
- **Base de conocimiento:** carga la hoja `Linea Base forti` (casos de uso con plantilla de comunicación) y la hoja `Line Base Secu` (reglas de FortiSIEM sin plantilla).
- **Casos:**
  - Normaliza la criticidad ("media" → Media).
  - Normaliza la táctica a MITRE ATT&CK; las variantes en español e inglés se unifican. El texto original se guarda en `tactica_original`.
  - Une la fecha con las horas del SIEM y del reporte. Cuando el caso cruza la medianoche, decide por los casos vecinos si la "Fecha" era la del reporte (lo habitual: el evento queda el día anterior) o la del evento (el reporte queda al día siguiente). Si la diferencia supera 12 h no se considera un cruce: se deja como aviso para revisar.
  - Guarda la columna "Fecha" en `fecha_bitacora`. Los informes, el tablero, los filtros de Casos y la página de inicio cuentan por ese día; en los casos creados en la plataforma es el día del reporte al cliente.
  - Convierte los "Comentario N2…N10" en historial de seguimiento.
- **Versiones anteriores:** si la base se cargó antes de la migración 0004, vuelva a importar el mismo Excel en modo *Nuevos y actualizar importados* para corregir el día de los casos de medianoche. Ese modo también reemplaza con el Excel lo editado en la plataforma sobre casos importados; revise la simulación primero.
- **Es idempotente:** un número de reporte ya cargado no se duplica.
- **Avisos:** marca las filas sin fecha o sin criticidad, los números repetidos dentro del archivo y los casos con más de 12 h entre el evento y el reporte.
- **Consecutivo:** queda en el mayor número usado, y la plataforma continúa desde ahí.

## Roles

| | N1 | N2 | N3 | Líder SOC | CISO | Administrador |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Ver todos los casos | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Crear casos; editar y comentar los propios | ✓ | ✓ | ✓ | ✓ | – | ✓ |
| Consultar la base de conocimiento | ✓ | ✓ | ✓ | ✓ | – | ✓ |
| Revisar casos de N1; editar, comentar y anular cualquiera | – | ✓ | ✓ | ✓ | – | ✓ |
| Tablero e inicio; ver y descargar informes | – | ✓ | ✓ | ✓ | ✓ | ✓ |
| Preparar informes; editar la base de conocimiento | – | ✓ | ✓ | ✓ | – | ✓ |
| Cerrar o eliminar informes; eliminar casos de uso; clientes; importar; usuarios; configuración | – | – | – | ✓ | – | ✓ |
| Administrar administradores | – | – | – | – | – | ✓ |

- Los permisos se definen en `backend/app/security.py` (`PERMISOS`) y se validan en el servidor; el menú solo los refleja.
- N2 y N3 tienen hoy los mismos permisos.
- El Líder administra usuarios, pero no puede crear, modificar ni nombrar administradores. Nadie cambia su propio rol.

### Revisión de los casos de N1

El N1 reporta de inmediato al cliente y el caso queda **Por revisar**. Un N2 o superior lo marca **Revisado** o lo **devuelve** con una observación. Si el N1 corrige el contenido, vuelve a quedar por revisar. La revisión no cambia la hora de reporte ni el SLA, y queda en el seguimiento del caso. Los casos importados y los creados por N2 o superior no la requieren.

## Configuración

Menú *Configuración* (Líder SOC y Administrador). Lo guardado allí reemplaza al `.env` de inmediato, sin reiniciar; *Restablecer* vuelve a los valores de la instalación.

- **General:** SLA, duración de la sesión, límites de archivos, fondo del mapa, dirección de la plataforma.
- **Correo al cliente:** copias fijas, dominio propio, plazo, marca TLP. La alerta sigue siendo un borrador: no se envía.
- **Avisos internos:** correo SMTP **solo al dominio propio** para casos por revisar (agrupados), devueltos (al analista) y fallas de GLPI. Llevan número, cliente, alerta y criticidad. Si el correo falla, el caso se guarda igual y se reintenta hasta 6 veces; a las 24 horas se descarta.
- **GLPI** y **FortiSIEM:** conexión y prueba. De FortiSIEM solo se prueba; los anexos se cargan por archivo.
- **Otras APIs:** registro y prueba de conexiones; usarlas requiere desarrollo.
- **Claves de acceso:** para que otro sistema consulte `GET /api/externo/casos` y `/api/externo/resumen` con la cabecera `X-Api-Key`. Solo lectura, con vencimiento, por cliente si se quiere y revocables. No entregan análisis ni registros.

Seguridad:
- Las claves se guardan **cifradas** con una llave derivada de `JWT_SECRET` y no se vuelven a mostrar. Si cambia `JWT_SECRET` hay que escribirlas de nuevo (*Estado* lo avisa). Un respaldo de la base sin el `.env` no permite leerlas.
- Si cambia el servidor de una conexión, se exige escribir otra vez la clave.
- No se puede apuntar a la propia máquina ni a los servicios internos de la plataforma.
- Con usuario SMTP la conexión debe ser STARTTLS o SSL.
- Todo queda en el registro de cambios, sin las claves.

## Editar, deshabilitar y eliminar

| | Editar y deshabilitar | Eliminar | No se elimina si tiene |
|---|---|---|---|
| Usuarios | Líder, Administrador | Líder, Administrador | casos, seguimientos o importaciones |
| Clientes | Líder, Administrador | Líder, Administrador | casos o informes |
| Casos de uso | N2 o superior | Líder, Administrador | casos |
| Informes | N2 o superior (editar) | Líder, Administrador | estado Final |

- **Deshabilitar** conserva el historial: el usuario no ingresa y pierde la sesión abierta; el cliente no recibe casos, informes ni correos nuevos; el caso de uso no aparece al registrar. Los casos existentes se siguen gestionando.
- Nadie se deshabilita ni se elimina a sí mismo, y el Líder no toca administradores: siempre queda al menos un administrador.
- El administrador del `.env` solo se crea si no existe ninguno.
- **Ingreso:** no hay registro ni recuperación por correo; quien olvida la contraseña la pide al Líder o al Administrador. *Recordar mi usuario* guarda solo el nombre de usuario en ese navegador.
- **Registro de cambios** (*Usuarios → Registro de cambios*): quién, cuándo y qué. No se puede modificar desde la aplicación. Nunca guarda contraseñas.
- Los casos no se eliminan: se anulan.

### Anular casos

- N2 o superior, con motivo obligatorio (*detalle del caso → Anular*). Se puede **restaurar**, también con motivo. Ambas quedan en el seguimiento y en el registro de cambios.
- El caso conserva número, historial y archivos, pero no cuenta en inicio, tablero ni informes, no sale en *Por revisar* y solo admite comentarios.
- En *Casos* quedan ocultos; el filtro *Anulados* los muestra. Buscar el número exacto siempre lo encuentra.
- Los informes **finales** no cambian. Los textos de un **borrador** se deben regenerar; el seguimiento del caso indica cuáles.
- No retira correos enviados ni modifica el ticket de GLPI.
- Importar: *Actualizar* mantiene la anulación; *Reemplazar* se bloquea si hay casos importados anulados.
- Desarrollo: toda cifra de casos debe filtrar por `VIGENTE` (`models.py`).

## Respaldo

```bash
# respaldo diario recomendado (cron)
docker compose exec -T db pg_dump -U soc -Fc soc > respaldo_soc_$(date +%F).dump
# restaurar
docker compose exec -T db pg_restore -U soc -d soc --clean < respaldo_soc_AAAA-MM-DD.dump
```

## Pruebas

`bash pruebas/correr.sh` instala una copia limpia en un proyecto Docker aparte (puerto 8099), corre todo y la elimina; con `--dejar` queda encendida. Necesita Docker, Node y, **fuera del repositorio** (carpeta superior o `SOC_INSUMOS`), la bitácora Excel, los CSV de FortiSIEM y `control.json` con las cifras esperadas.

## Actualizar un servidor

`sudo bash actualizar.sh <paquete.tar.gz> <sha256>`: verifica el paquete, respalda la base, conserva `.env` y `datos`, guarda la carpeta anterior e instala.

## Qué no va en el repositorio

`.env`, claves, bitácoras, anexos, respaldos, `datos/` y cifras o datos de clientes.

## Desarrollo

- Documentación de la API: `http://<servidor>:8080/api/docs`
- Backend: `backend/app` (modelos en `models.py`, normalización en `normalizacion.py`, endpoints en `routers/`).
- Frontend: `frontend/src` (páginas en `pages/`).
- **Esquema de base de datos:** se versiona con Alembic (`backend/migraciones`). Al iniciar, la API aplica sola las migraciones pendientes.
- **Para crear una migración** después de cambiar `models.py`:
  ```bash
  docker compose run --rm -v "$PWD/backend:/srv" api alembic revision --autogenerate -m "descripcion"
  ```
