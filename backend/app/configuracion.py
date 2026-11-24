"""Configuración administrable desde la pantalla.

Los valores guardados en la base reemplazan a los del .env (en memoria, sobre `settings`). Las claves se guardan
cifradas con una llave derivada de JWT_SECRET y nunca se devuelven por la API ni se escriben en la auditoría.
"""
import base64
import hashlib
import ipaddress
import logging
import socket
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auditoria import registrar
from .config import settings
from .models import Cliente, Configuracion, Usuario

log = logging.getLogger("uvicorn.error")
BASE = settings.model_copy()          # lo que vino del .env o por defecto
ILEGIBLES: set[str] = set()           # claves que no se pudieron descifrar (cambió JWT_SECRET)


class ErrorConfig(ValueError):
    pass


def C(clave, etiqueta, tipo="texto", **kw):
    return {"clave": clave, "etiqueta": etiqueta, "tipo": tipo, **kw}


# tipo: texto | entero | si_no | secreto | opcion | url | host | correos
GRUPOS: dict[str, dict] = {
    "general": {"titulo": "General", "campos": [
        C("sla_minutos", "SLA de reporte (minutos)", "entero", min=1, max=1440,
          ayuda="Cambia el cumplimiento en inicio, tablero e informes en borrador; los finales no cambian"),
        C("jwt_horas", "Duración de la sesión (horas)", "entero", min=1, max=24, ayuda="Aplica a los próximos ingresos"),
        C("url_plataforma", "Dirección de la plataforma", "url", opcional=True, ayuda="Para los enlaces de los avisos, por ejemplo http://10.0.0.1:8080"),
        C("adjunto_max_mb", "Máximo por archivo (MB)", "entero", min=1, max=60),
        C("adjuntos_caso_max_mb", "Máximo de archivos por caso (MB)", "entero", min=1, max=500),
        C("mostrar_tiempos", "Mostrar tiempos de notificación y SLA en los informes", "si_no", ayuda="Presentación ejecutiva, Word y PDF. Los informes finales conservan lo que tenían"),
        C("mapa_activo", "Fondo del mapa en la presentación (requiere Internet)", "si_no"),
    ]},
    "correo_cliente": {"titulo": "Correo al cliente", "campos": [
        C("correo_cc", "Copia fija (CC)", "correos", ayuda="Solo direcciones del dominio propio"),
        C("correo_cco", "Copia oculta fija (CCO)", "correos", ayuda="Solo direcciones del dominio propio"),
        C("correo_dominio_propio", "Dominio propio", "texto", ayuda="Siempre permitido como destinatario; no puede ser de un cliente"),
        C("correo_plazo_horas", "Plazo de respuesta (horas)", "entero", min=1, max=720),
        C("correo_tlp", "Marca TLP", "opcion", opciones=["TLP:RED", "TLP:AMBER+STRICT", "TLP:AMBER", "TLP:GREEN", "TLP:CLEAR"]),
        C("correo_max_mb", "Máximo de archivos en un correo (MB)", "entero", min=1, max=40),
    ]},
    "avisos": {"titulo": "Avisos internos", "url": ("smtp_servidor", "smtp_puerto"), "campos": [
        C("avisos_activo", "Enviar avisos internos por correo", "si_no"),
        C("smtp_servidor", "Servidor SMTP", "host", opcional=True, ayuda="por ejemplo smtp.office365.com"),
        C("smtp_puerto", "Puerto", "entero", min=1, max=65535),
        C("smtp_seguridad", "Seguridad", "opcion", opciones=["STARTTLS", "SSL", "NINGUNA"], ayuda="NINGUNA solo sin usuario"),
        C("smtp_verificar_ssl", "Verificar el certificado", "si_no"),
        C("smtp_usuario", "Usuario", "texto", opcional=True),
        C("smtp_clave", "Contraseña", "secreto"),
        C("smtp_remitente", "Remitente", "correos", opcional=True, uno=True, ayuda="Del dominio propio"),
        C("avisos_destino", "Destinatarios", "correos", opcional=True, ayuda="Solo del dominio propio; uno por línea o separados por ;"),
        C("aviso_por_revisar", "Avisar cuando un caso queda por revisar", "si_no"),
        C("avisos_agrupar_min", "Agrupar los casos por revisar cada (minutos)", "entero", min=0, max=240),
        C("aviso_devuelto", "Avisar al analista cuando le devuelven un caso", "si_no", ayuda="Al correo del usuario; si no tiene, a los destinatarios"),
        C("aviso_glpi", "Avisar si falla GLPI", "si_no"),
    ]},
    "glpi": {"titulo": "GLPI", "url": ("glpi_url",), "campos": [
        C("glpi_url", "URL de la API", "url", opcional=True, ayuda="termina en /apirest.php; vacío desactiva la integración"),
        C("glpi_app_token", "App-Token", "secreto"),
        C("glpi_user_token", "Token del usuario de servicio", "secreto"),
        C("glpi_verificar_ssl", "Verificar el certificado", "si_no"),
        C("glpi_tipo_ticket", "Tipo de ticket", "opcion", opciones=[1, 2], nombres={1: "Incidente", 2: "Solicitud"}),
        C("glpi_categoria_id", "ID de la categoría ITIL", "entero", opcional=True, min=1, max=10**9),
        C("glpi_origen_id", "ID del origen de la solicitud", "entero", opcional=True, min=1, max=10**9),
        C("glpi_crear_por_defecto", "Marcar «Crear ticket» por defecto", "si_no"),
        C("glpi_resolver_al_cerrar", "Resolver el ticket al cerrar el caso", "si_no"),
        C("glpi_sync_minutos", "Sincronizar cada (minutos)", "entero", min=0, max=1440, ayuda="0 = solo manual"),
        C("glpi_url_tickets", "URL web para abrir un ticket", "url", opcional=True, ayuda="vacío = se deduce de la API"),
    ]},
    "fortisiem": {"titulo": "FortiSIEM", "url": ("fortisiem_url",), "campos": [
        C("fortisiem_url", "URL del supervisor", "url", opcional=True, ayuda="por ejemplo https://fortisiem.empresa.com"),
        C("fortisiem_organizacion", "Organización", "texto", ayuda="super, o el nombre de la organización"),
        C("fortisiem_usuario", "Usuario de consulta", "texto", opcional=True),
        C("fortisiem_clave", "Contraseña", "secreto"),
        C("fortisiem_verificar_ssl", "Verificar el certificado", "si_no"),
    ]},
}
_CAMPOS = {c["clave"]: (g, c) for g, d in GRUPOS.items() for c in d["campos"]}


# ------------------------------------------------------------------ cifrado
def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"soc-configuracion:" + settings.jwt_secret.encode()).digest()))


def cifrar(v: str) -> str:
    return _fernet().encrypt(v.encode()).decode()


def descifrar(v: str) -> str:
    return _fernet().decrypt(v.encode()).decode()


# ------------------------------------------------------------------ destinos permitidos
def validar_host(host: str):
    """Impide apuntar a la propia máquina o a los servicios internos de la plataforma."""
    h = (host or "").strip().strip("[]").lower()
    if not h or h in {"localhost", "db", "api", "web", "convertidor"} or h.endswith(".localhost"):
        raise ErrorConfig(f"Dirección no permitida: {host or 'vacía'}")
    try:
        ips = {ipaddress.ip_address(x[4][0].split("%")[0]) for x in socket.getaddrinfo(h, None)}
    except (OSError, UnicodeError):
        return  # aún no resuelve: fallará al conectar
    propias = set()
    for s in ("db", "api", "web", "convertidor"):
        try:
            propias |= {ipaddress.ip_address(x[4][0]) for x in socket.getaddrinfo(s, None)}
        except OSError:
            pass
    for ip in ips:
        ip = getattr(ip, "ipv4_mapped", None) or ip
        if ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast or ip in propias:
            raise ErrorConfig(f"Dirección no permitida: {host}")


def validar_url(v: str) -> str:
    v = v.strip().rstrip("/")
    try:
        u = urlsplit(v)
        u.port  # noqa: B018 - lanza ValueError si el puerto no es válido
    except ValueError as e:
        raise ErrorConfig("La dirección no es válida") from e
    if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password or any(c.isspace() for c in v):
        raise ErrorConfig("La dirección debe empezar por http:// o https:// y no llevar usuario ni clave")
    return v


def destino(url: str | None) -> str:
    """Servidor al que se envían las credenciales."""
    u = urlsplit(url or "")
    return f"{u.scheme}://{u.hostname}:{u.port or ''}" if u.hostname else ""


# ------------------------------------------------------------------ carga
def _leer(c: dict, v: str):
    if c["tipo"] == "si_no":
        return v == "true"
    if c["tipo"] == "entero" or (c["tipo"] == "opcion" and isinstance(c["opciones"][0], int)):
        return int(v) if v else None
    if not v:
        return "" if not c.get("opcional") and c["tipo"] != "secreto" else None
    return v


def cargar(db: Session):
    """Deja en `settings` el valor guardado o, si no hay, el del .env."""
    filas = {f.clave: f for f in db.scalars(select(Configuracion))}
    ILEGIBLES.clear()
    for clave, (_g, c) in _CAMPOS.items():
        valor = getattr(BASE, clave)
        f = filas.get(clave)
        if f is not None:
            try:
                valor = _leer(c, (descifrar(f.valor) if f.valor else "") if c["tipo"] == "secreto" else f.valor or "")
            except (InvalidToken, ValueError):
                ILEGIBLES.add(clave)
                valor = None if c["tipo"] == "secreto" else valor
                log.warning("No se pudo leer la configuración '%s'; vuelva a escribirla", clave)
        setattr(settings, clave, valor)


def listar(db: Session) -> list[dict]:
    filas = {f.clave: f for f in db.scalars(select(Configuracion))}
    salida = []
    for g, d in GRUPOS.items():
        campos = []
        for c in d["campos"]:
            f, v = filas.get(c["clave"]), getattr(settings, c["clave"])
            defecto = type(BASE).model_fields[c["clave"]].default
            campos.append({**c, "valor": None if c["tipo"] == "secreto" else v, "definida": bool(v) if c["tipo"] == "secreto" else None,
                           "ilegible": c["clave"] in ILEGIBLES,
                           "origen": "pantalla" if f else ".env" if getattr(BASE, c["clave"]) != defecto else "predeterminado",
                           "por": f.por if f else None, "en": f.en if f else None})
        salida.append({"grupo": g, "titulo": d["titulo"], "campos": campos})
    return salida


# ------------------------------------------------------------------ guardar
def _convertir(c: dict, v, dominio: str):
    """Valida y devuelve el texto que se guarda."""
    from . import correo
    t, et = c["tipo"], c["etiqueta"]
    if t == "si_no":
        if not isinstance(v, bool):
            raise ErrorConfig(f"{et}: debe ser sí o no")
        return "true" if v else "false"
    vacio = v is None or (isinstance(v, str) and not v.strip())
    if vacio:
        if c.get("opcional") or t == "correos":
            return ""
        raise ErrorConfig(f"{et}: es obligatorio")
    if t == "entero":
        try:
            n = int(v)
        except (TypeError, ValueError) as e:
            raise ErrorConfig(f"{et}: debe ser un número entero") from e
        if isinstance(v, bool) or isinstance(v, float) and v != n or not c["min"] <= n <= c["max"]:
            raise ErrorConfig(f"{et}: debe estar entre {c['min']} y {c['max']}")
        return str(n)
    if t == "opcion":
        if v not in c["opciones"] and str(v) not in map(str, c["opciones"]):
            raise ErrorConfig(f"{et}: opción no válida")
        return str(v)
    if not isinstance(v, str) or len(v) > 2000:
        raise ErrorConfig(f"{et}: no es válido")
    if t == "url":
        v = validar_url(v)
        if c["clave"] not in ("url_plataforma", "glpi_url_tickets"):   # las demás las llama el servidor
            validar_host(urlsplit(v).hostname)
        return v
    if t == "host":
        v = v.strip().lower()
        if any(ch in v for ch in "/@: ") or len(v) > 253:
            raise ErrorConfig(f"{et}: escriba solo el nombre o la IP del servidor")
        validar_host(v)
        return v
    if t == "correos":
        try:
            lista = correo.leer_correos(v)
        except correo.ErrorCorreo as e:
            raise ErrorConfig(f"{et}: {e}") from e
        if c.get("uno") and len(lista) != 1:
            raise ErrorConfig(f"{et}: escriba una sola dirección")
        ajenos = [x for x in lista if not correo._en(x, [dominio])]
        if ajenos:
            raise ErrorConfig(f"{et}: solo se aceptan direcciones de {dominio}: {', '.join(ajenos[:3])}")
        return "; ".join(lista)
    v = v.strip()
    if any(ord(ch) < 32 for ch in v) or len(v) > 300:
        raise ErrorConfig(f"{et}: no es válido")
    return v


def _validar_dominio(db: Session, d: str) -> str:
    from . import correo
    d = d.strip().lstrip("@").lower()
    if not correo._DOMINIO.fullmatch(d) or d in correo.PUBLICOS:
        raise ErrorConfig("Dominio propio: no es un dominio válido de la empresa")
    for cl in db.scalars(select(Cliente)):
        if any(d == o or d.endswith("." + o) or o.endswith("." + d) for o in cl.correos_dominios or []):
            raise ErrorConfig(f"Dominio propio: {d} pertenece a {cl.codigo}")
    return d


def guardar(db: Session, yo: Usuario, grupo: str, datos: dict, borrar: list[str]):
    if grupo not in GRUPOS:
        raise ErrorConfig("Grupo no válido")
    d = GRUPOS[grupo]
    campos = {c["clave"]: c for c in d["campos"]}
    ajenas = [k for k in [*datos, *borrar] if k not in campos or (k in borrar and campos[k]["tipo"] != "secreto")]
    if ajenas:
        raise ErrorConfig(f"Campo no válido: {ajenas[0]}")
    if grupo == "correo_cliente" and "correo_dominio_propio" in datos:
        datos["correo_dominio_propio"] = _validar_dominio(db, str(datos["correo_dominio_propio"] or ""))
    dominio = datos.get("correo_dominio_propio") or settings.correo_dominio_propio

    nuevos, secretos = {}, {}
    for k, v in datos.items():
        c = campos[k]
        if c["tipo"] == "secreto":
            if v not in (None, ""):
                if not isinstance(v, str) or len(v) > 500 or any(ord(ch) < 32 for ch in v):
                    raise ErrorConfig(f"{c['etiqueta']}: no es válida")
                secretos[k] = v.strip()
        else:
            nuevos[k] = _convertir(c, v, dominio)
    if grupo == "correo_cliente":  # las copias deben seguir siendo del dominio propio aunque solo cambie el dominio
        for k in ("correo_cc", "correo_cco"):
            _convertir(campos[k], nuevos.get(k, getattr(settings, k)), dominio)

    actual = lambda k: nuevos.get(k) if k in nuevos else getattr(settings, k)  # noqa: E731
    # Si cambia el servidor, la clave guardada no se le envía: hay que escribirla otra vez
    if d.get("url"):
        fijas = d["url"]
        antes = tuple(destino(getattr(settings, k)) if campos[k]["tipo"] == "url" else str(getattr(settings, k) or "") for k in fijas)
        ahora = tuple(destino(actual(k)) if campos[k]["tipo"] == "url" else str(actual(k) or "") for k in fijas)
        faltan = [c["etiqueta"] for c in d["campos"] if c["tipo"] == "secreto" and getattr(settings, c["clave"])
                  and c["clave"] not in secretos and c["clave"] not in borrar]
        if antes != ahora and ahora[0] and faltan:
            raise ErrorConfig(f"Cambió el servidor: por seguridad vuelva a escribir {', '.join(faltan)}")
    if grupo == "avisos":
        clave = secretos.get("smtp_clave") or (settings.smtp_clave if "smtp_clave" not in borrar else None)
        if actual("smtp_seguridad") == "NINGUNA" and (actual("smtp_usuario") or clave):
            raise ErrorConfig("Con usuario o contraseña la conexión debe ser STARTTLS o SSL")
        if actual("smtp_usuario") and not clave:
            raise ErrorConfig("Escriba la contraseña del usuario SMTP")
        if actual("avisos_activo") in (True, "true") and not (actual("smtp_servidor") and actual("smtp_remitente") and actual("avisos_destino")):
            raise ErrorConfig("Para activar los avisos faltan el servidor, el remitente o los destinatarios")

    filas = {f.clave: f for f in db.scalars(select(Configuracion))}
    cambios = []
    for k, v in nuevos.items():
        antes = getattr(settings, k)
        if _leer(campos[k], v) == antes or (not v and antes in (None, "")):
            continue
        cambios.append(f"{campos[k]['etiqueta']}: {_mostrar(antes)} → {_mostrar(_leer(campos[k], v))}")
        _fila(db, filas, k, v, yo)
    for k, v in secretos.items():
        cambios.append(f"{campos[k]['etiqueta']}: {'reemplazada' if getattr(settings, k) else 'guardada'}")
        _fila(db, filas, k, cifrar(v), yo)
    for k in borrar:
        if getattr(settings, k) or k in filas:
            cambios.append(f"{campos[k]['etiqueta']}: borrada")
            _fila(db, filas, k, "", yo)
    if cambios:
        registrar(db, yo, "editar", f"la configuración de {d['titulo']}", "; ".join(cambios))
    db.commit()
    cargar(db)


def restablecer(db: Session, yo: Usuario, grupo: str):
    """Vuelve a los valores del .env o predeterminados."""
    if grupo not in GRUPOS:
        raise ErrorConfig("Grupo no válido")
    n = 0
    for f in db.scalars(select(Configuracion).where(Configuracion.clave.in_([c["clave"] for c in GRUPOS[grupo]["campos"]]))):
        db.delete(f)
        n += 1
    if n:
        registrar(db, yo, "editar", f"la configuración de {GRUPOS[grupo]['titulo']}", "valores restablecidos a los de la instalación")
    db.commit()
    cargar(db)


def _fila(db: Session, filas: dict, clave: str, valor: str, yo: Usuario):
    from datetime import datetime, timezone
    f = filas.get(clave)
    if f is None:
        f = filas[clave] = Configuracion(clave=clave)
        db.add(f)
    f.valor, f.por, f.en = valor, yo.nombre, datetime.now(timezone.utc)


def _mostrar(v) -> str:
    return ("sí" if v else "no") if isinstance(v, bool) else "vacío" if v in (None, "") else str(v)[:120]
