# Plataforma SOC/NOC de Wexler: guía de desarrollo

Reemplaza la bitácora Excel del SOC/NOC: casos de los N1, base de conocimiento, correo al cliente, tablero e informes mensuales. Uso y operación: `README.md`. Todo en **español** (interfaz, código, comentarios, mensajes).

## Stack
Docker Compose: `db` (PostgreSQL 16), `api` (FastAPI, SQLAlchemy 2, Alembic, Python 3.12), `web` (React 18 + Vite + nginx), `convertidor` (Gotenberg 8: Word→PDF y HTML→PDF). Sin más dependencias si se puede evitar.

## Dónde está cada cosa
- `backend/app/models.py`, `schemas.py`, `security.py` (permisos por rol: `PERMISOS`, `tiene`, `requiere`), `config.py` (variables del `.env`).
- `routers/`: `casos`, `casos_uso` (base de conocimiento), `clientes`, `usuarios`, `informes`, `tablero`, `importaciones`, `glpi_api`, `auth`.
- `importacion.py` (bitácora Excel; `Cronologia` deduce fechas que cruzan la medianoche), `correo.py` + `notificacion.py` (borrador `.eml` y plantilla de alerta), `adjuntos.py` e `imagenes.py` (validación de archivos), `auditoria.py` (registro de cambios), `glpi.py`, `configuracion.py` (parámetros de pantalla sobre `settings`, cifrado y destinos permitidos), `avisos.py` (cola y envío SMTP interno). `routers/externo.py`: consulta de solo lectura con clave.
- `informes/`: `anexos` (CSV/Excel de FortiSIEM), `metricas`, `textos`, `contenido`, `word` (python-docx sobre la plantilla corporativa), `presentacion_html` + `plantillas/presentacion.{html,css,js}`, `mapa` (coordenadas de países), `convertidor`.
- `frontend/src`: `pages/`, `components/` (`Ui`, `Adjuntos`, `Imagen`, `Layout`), `auth.jsx` (`puede("permiso")`), `util.js`.
- Esquema: `backend/migraciones/versions` (última **0011**). La API aplica sola las migraciones al iniciar. Al crear una, subir también el número que espera `instalar.sh`.

## Reglas que no se deben romper
- **Toda cifra de casos filtra por `VIGENTE`** (`models.py`): los anulados no cuentan en inicio, tablero ni informes.
- **Todo se cuenta por `fecha_bitacora`** (columna «Fecha» de la bitácora o día del reporte), no por `fecha_evento`.
- **Totales de control** con la bitácora real: `control.json` (local). Informe, lista de casos y tablero deben coincidir.
- El día de corte varía por cliente (`dia_corte`; 1 = mes calendario).
- **Los casos no se eliminan: se anulan** (N2 o superior, con motivo, restaurables) y el número WX no se reutiliza. Usuarios, clientes y casos de uso solo se eliminan si no tienen historial; si lo tienen, se deshabilitan.
- **Los informes FINAL están congelados** (`metricas`): nada los debe cambiar.
- **El correo de alerta nunca se envía**: se descarga un `.eml` (`X-Unsent: 1`). El envío del informe por correo (Fase 4) sería una excepción que el usuario aún no ha definido: preguntar antes de implementarlo. Los destinatarios salen solo del cliente y de sus dominios; es el control para no equivocarse de cliente.
- La importación «Reemplazar» se bloquea si hay casos importados con archivos o anulados.
- Los permisos se validan en el servidor; el menú solo los refleja. Siempre queda un administrador; el del `.env` solo se crea si no existe ninguno.
- Los archivos se validan por contenido, no por extensión. Sin HTML, SVG, macros ni ejecutables. No hay antivirus.
- Nunca escribir claves en el código, los registros ni la auditoría. Las de la pantalla van cifradas y la API nunca las devuelve; al cambiar el servidor de una conexión se exige escribirlas otra vez.
- **Los avisos internos (`avisos.py`) solo van al dominio propio** y sin el detalle del caso; nunca a clientes.
- `PUBLICOS` en `correo.py` prohíbe dominios generales (`gov.co`, `com.co`…): no quitarlos, es parte del control para no equivocarse de cliente (confirmado por el usuario el 2026-11-24).
- Leer siempre `settings.x` al usarlo, no guardarlo en variables de módulo: puede cambiar desde la pantalla.

## Roles
N1 crea y ve todos los casos (edita los suyos). N2 y N3 revisan después (no bloquea ni cambia el SLA), hoy con permisos idénticos por decisión del usuario. Líder SOC administra, sin tocar administradores. CISO solo consulta (sin base de conocimiento). Admin todo.

## Presentación
HTML único de 1920×1080 con fuentes, fotos e imágenes incrustadas, mismo estilo que la presentación de vulnerabilidades de Wexler. `pdf=True` pone la clase `pdf` (todo en estado final) y `window.__listo` avisa que se puede imprimir. El fondo del mapa se carga de Internet (NASA GIBS); **debe funcionar sin conexión**, también el PDF. El logo y las imágenes de boletines no salen en el Word.

## Detalles que ya costaron tiempo
- `deferred` en columnas: usar `mapped_column(..., deferred=True)`; si no, se pierde el NOT NULL. Comprobar siempre `alembic check`.
- Al limpiar un `<input type=file>` la lista de archivos queda vacía: copiarla antes.
- Las rutas fijas de un router van antes de `/{id}` si comparten método.
- `.env` con un valor vacío se ignora: para desactivar el mapa es `MAPA_BASE=no`.
- Medir textos con las animaciones desactivadas (`#stage.midiendo`), porque el desplazamiento altera el alto.

## Repositorio
- Nada de datos de clientes, cifras reales, direcciones internas ni claves en el código, la documentación o las pruebas: van en archivos locales (`control.json`, `clientes.json` en `/datos`, el `CLAUDE.md` de la carpeta superior).
- Pruebas: `bash pruebas/correr.sh` antes de cada commit con cambios de código. FortiSIEM, SMTP y GLPI solo se han probado con simuladores (`pruebas/simuladores.py`).
- El estado, los pendientes y los entornos están en el `CLAUDE.md` local de la carpeta superior.
