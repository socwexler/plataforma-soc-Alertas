"""Anexos del informe desde SharePoint (solo lectura: nunca escribe ni borra).

Estructura esperada: <carpeta base>/<carpeta del anexo>/<carpeta del cliente>/<archivos>. La carpeta del anexo se
reconoce por su nombre o por el número con que empieza («04» = «04 WX - Promedio Mensual EPS»); la del cliente es su
código o la «Carpeta en SharePoint» de su ficha. Se propone el archivo CODIGO_AAAA-MM (mes en que empieza el periodo).

Dos orígenes con la misma interfaz:
- carpeta: la carpeta de SharePoint sincronizada con OneDrive y montada en /sharepoint (solo lectura).
- graph: Microsoft Graph con una aplicación de Entra ID (Sites.Selected, solo lectura).
"""
import re
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx

from .config import settings
from .models import Cliente

MONTADA = Path("/sharepoint")
EXTENSIONES = (".csv", ".txt", ".xlsx", ".xlsm")
MAX_BYTES = 60 * 1024 * 1024
MAX_LISTA = 200
# tipo de anexo -> (nombre, tipos que puede reconocer el lector en esa carpeta)
TIPOS: dict[str, tuple[str, set[str]]] = {
    "eps": ("EPS", {"eps"}),
    "fuentes": ("Fuentes integradas", {"fuentes"}),
    "paises_entrantes": ("Países entrantes", {"paises_entrantes"}),
    "paises_salientes": ("Países salientes", {"paises_salientes"}),
    "puertos": ("Puertos", {"puertos"}),
    "ips": ("Ataques IPS", {"ips"}),
}


class ErrorSP(Exception):
    pass


@dataclass
class Item:
    nombre: str
    carpeta: bool
    tamano: int | None = None
    modificado: datetime | None = None
    ref: str | None = None


def activo() -> bool:
    return settings.sharepoint_modo in ("carpeta", "graph")


def _partes(ruta: str | None) -> list[str]:
    partes = [p.strip() for p in re.split(r"[\\/]+", ruta or "") if p.strip()]
    if any(p in (".", "..") for p in partes):
        raise ErrorSP("La carpeta base no es válida")
    return partes


# ------------------------------------------------------------------ carpeta sincronizada
class Carpeta:
    def __init__(self):
        self.raiz = MONTADA.joinpath(*_partes(settings.sharepoint_ruta)).resolve()
        if not self.raiz.is_dir() or not self.raiz.is_relative_to(MONTADA.resolve()):
            raise ErrorSP("No se encuentra la carpeta sincronizada: revise que esté montada en /sharepoint "
                          "(SHAREPOINT_CARPETA_LOCAL en el .env) y la carpeta base en Configuración → SharePoint")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def _ruta(self, partes: list[str]) -> Path:
        p = self.raiz.joinpath(*partes).resolve()
        if not p.is_relative_to(self.raiz):
            raise ErrorSP("Ruta no válida")
        return p

    def hijos(self, partes: list[str]) -> list[Item]:
        p = self._ruta(partes)
        if not p.is_dir():
            return []
        salida = []
        for x in p.iterdir():
            try:
                st = x.stat()
            except OSError:
                continue
            salida.append(Item(x.name, x.is_dir(), None if x.is_dir() else st.st_size,
                               datetime.fromtimestamp(int(st.st_mtime), timezone.utc), "/".join([*partes, x.name])))
        return salida

    def leer(self, item: Item) -> bytes:
        p = self._ruta(_partes(item.ref))
        if p.stat().st_size > MAX_BYTES:
            raise ErrorSP(f"{item.nombre}: supera 60 MB")
        return p.read_bytes()


# ------------------------------------------------------------------ Microsoft Graph
_tokens: dict[tuple, tuple[str, float]] = {}
_candado = threading.Lock()


class Graph:
    def __init__(self):
        if not (settings.sharepoint_sitio and settings.sharepoint_tenant and settings.sharepoint_cliente_id and settings.sharepoint_secreto):
            raise ErrorSP("Faltan datos de Microsoft Graph en Configuración → SharePoint")
        self.base = settings.sharepoint_graph_url.rstrip("/")
        self.http = httpx.Client(timeout=30, follow_redirects=False)

    def __enter__(self):
        try:
            self.http.headers["Authorization"] = f"Bearer {self._token()}"
            s = urlsplit(settings.sharepoint_sitio)
            sitio = self._json(f"{self.base}/sites/{s.hostname}:{quote(s.path.rstrip('/') or '/')}")["id"]
            if settings.sharepoint_biblioteca:
                drives = self._json(f"{self.base}/sites/{sitio}/drives").get("value", [])
                d = next((x for x in drives if x.get("name", "").lower() == settings.sharepoint_biblioteca.strip().lower()), None)
                if not d:
                    raise ErrorSP(f"No existe la biblioteca «{settings.sharepoint_biblioteca}» en el sitio")
                self.drive = d["id"]
            else:
                self.drive = self._json(f"{self.base}/sites/{sitio}/drive")["id"]
        except Exception:
            self.http.close()
            raise
        return self

    def __exit__(self, *exc):
        self.http.close()
        return False

    def _token(self) -> str:
        clave = (settings.sharepoint_login_url, settings.sharepoint_tenant, settings.sharepoint_cliente_id, settings.sharepoint_secreto)
        with _candado:
            t = _tokens.get(clave)
            if t and t[1] > time.time() + 60:
                return t[0]
            url = f"{settings.sharepoint_login_url.rstrip('/')}/{quote(settings.sharepoint_tenant.strip(), safe='')}/oauth2/v2.0/token"
            try:
                r = httpx.post(url, timeout=20, data={"grant_type": "client_credentials", "client_id": settings.sharepoint_cliente_id.strip(),
                                                       "client_secret": settings.sharepoint_secreto, "scope": "https://graph.microsoft.com/.default"})
            except httpx.HTTPError as e:
                raise ErrorSP(f"No se pudo conectar con el inicio de sesión de Microsoft: {e}") from e
            if r.status_code != 200:
                raise ErrorSP(f"Microsoft rechazó la aplicación ({r.status_code}): revise el tenant, el client ID y el secreto")
            j = r.json()
            _tokens.clear()
            _tokens[clave] = (j["access_token"], time.time() + int(j.get("expires_in", 3600)))
            return j["access_token"]

    def _json(self, url: str, **kw) -> dict:
        if not url.startswith(self.base + "/"):   # p. ej. un @odata.nextLink a otro servidor
            raise ErrorSP("Respuesta no válida de Microsoft Graph")
        try:
            r = self.http.get(url, **kw)
        except httpx.HTTPError as e:
            raise ErrorSP(f"No se pudo conectar con Microsoft Graph: {e}") from e
        if r.status_code == 404:
            return {}
        if r.status_code in (401, 403):
            raise ErrorSP("Microsoft Graph negó el acceso: la aplicación necesita permiso de lectura sobre el sitio (Sites.Selected)")
        if r.status_code >= 400:
            raise ErrorSP(f"Microsoft Graph respondió {r.status_code}")
        return r.json()

    def hijos(self, partes: list[str]) -> list[Item]:
        ruta = "/".join([*_partes(settings.sharepoint_ruta), *partes])
        url = f"{self.base}/drives/{self.drive}/root:/{quote(ruta)}:/children" if ruta else f"{self.base}/drives/{self.drive}/root/children"
        salida: list[Item] = []
        for _ in range(20):
            j = self._json(url)
            for x in j.get("value", []):
                mod = x.get("lastModifiedDateTime")
                salida.append(Item(x.get("name", ""), "folder" in x, x.get("size"),
                                   datetime.fromisoformat(mod.replace("Z", "+00:00")) if mod else None, x.get("id")))
            url = j.get("@odata.nextLink")
            if not url:
                break
        return salida

    def leer(self, item: Item) -> bytes:
        if (item.tamano or 0) > MAX_BYTES:
            raise ErrorSP(f"{item.nombre}: supera 60 MB")
        url = f"{self.base}/drives/{self.drive}/items/{quote(item.ref, safe='')}/content"
        try:
            r = self.http.get(url)
            if r.status_code in (301, 302, 303, 307, 308):
                # La descarga es un enlace firmado en SharePoint: se pide sin el token
                destino = r.headers.get("location", "")
                u = urlsplit(destino)
                if u.scheme != "https" and not (u.scheme == "http" and u.hostname == urlsplit(self.base).hostname):
                    raise ErrorSP("Enlace de descarga no válido")
                from .configuracion import ErrorConfig, validar_host
                try:
                    validar_host(u.hostname or "")
                except ErrorConfig as e:
                    raise ErrorSP("Enlace de descarga no válido") from e
                with httpx.stream("GET", destino, timeout=60, follow_redirects=False) as d:
                    if d.status_code != 200:
                        raise ErrorSP(f"La descarga de {item.nombre} respondió {d.status_code}")
                    datos = b""
                    for trozo in d.iter_bytes():
                        datos += trozo
                        if len(datos) > MAX_BYTES:
                            raise ErrorSP(f"{item.nombre}: supera 60 MB")
                    return datos
            if r.status_code != 200:
                raise ErrorSP(f"La descarga de {item.nombre} respondió {r.status_code}")
            return r.content
        except httpx.HTTPError as e:
            raise ErrorSP(f"No se pudo descargar {item.nombre}: {e}") from e


def abrir():
    if settings.sharepoint_modo == "carpeta":
        return Carpeta()
    if settings.sharepoint_modo == "graph":
        return Graph()
    raise ErrorSP("La integración con SharePoint no está activada (Configuración → SharePoint)")


# ------------------------------------------------------------------ búsqueda
def _coincide(nombre: str, buscado: str) -> bool:
    """«04» coincide con «04 WX - Promedio…» pero no con «040…»; un nombre completo coincide igual."""
    n, b = nombre.strip().lower(), (buscado or "").strip().lower()
    return bool(b) and (n == b or (n.startswith(b) and not n[len(b)].isalnum()))


def _carpeta_tipo(raiz: list[Item], tipo: str) -> Item:
    buscado = getattr(settings, f"sharepoint_carpeta_{tipo}")
    hallados = [x for x in raiz if x.carpeta and _coincide(x.nombre, buscado)]
    if not hallados:
        raise ErrorSP(f"No hay una carpeta «{buscado}…»")
    if len(hallados) > 1:
        raise ErrorSP(f"Hay {len(hallados)} carpetas que empiezan por «{buscado}»: escriba el nombre completo en Configuración")
    return hallados[0]


def nombres_cliente(c: Cliente) -> list[str]:
    return [x for x in dict.fromkeys([c.sharepoint_carpeta, c.codigo]) if x]


def sugerido(nombre: str, codigos: list[str], inicio: date) -> bool:
    """CODIGO_AAAA-MM (también CODIGO AAAA_MM, CODIGO-AAAAMM…) con sufijo _NOC opcional."""
    base, _, ext = nombre.rpartition(".")
    if f".{ext.lower()}" not in EXTENSIONES:
        return False
    pat = rf"^(?:{'|'.join(re.escape(c) for c in codigos)})[ _-]+{inicio.year}[ _-]?{inicio.month:02d}(?:[ _-]+noc)?$"
    return re.match(pat, base.strip(), re.IGNORECASE) is not None


def _archivos(fuente, carpeta_tipo: Item, cliente: Cliente) -> tuple[str | None, list[Item]]:
    sub = next((x for x in fuente.hijos([carpeta_tipo.nombre]) if x.carpeta
                and any(x.nombre.strip().lower() == n.lower() for n in nombres_cliente(cliente))), None)
    if not sub:
        return None, []
    # sin carpetas, ocultos ni temporales de Office (~$…)
    return sub.nombre, [x for x in fuente.hijos([carpeta_tipo.nombre, sub.nombre])
                        if not x.carpeta and not x.nombre.startswith((".", "~$")) and x.nombre.lower().endswith(EXTENSIONES)]


def buscar(cliente: Cliente, inicio: date) -> list[dict]:
    """Por cada anexo: carpeta, archivos del cliente y cuáles corresponden al periodo."""
    codigos = nombres_cliente(cliente)
    salida = []
    with abrir() as f:
        raiz = f.hijos([])
        for tipo, (nombre, _) in TIPOS.items():
            t = {"tipo": tipo, "nombre": nombre, "carpeta": None, "carpeta_cliente": None, "archivos": [], "error": None}
            try:
                ct = _carpeta_tipo(raiz, tipo)
                t["carpeta"] = ct.nombre
                t["carpeta_cliente"], archivos = _archivos(f, ct, cliente)
                if t["carpeta_cliente"] is None:
                    t["error"] = f"No hay una subcarpeta {' o '.join(codigos)}"
                lista = [{"nombre": x.nombre, "tamano": x.tamano, "modificado": x.modificado, "sugerido": sugerido(x.nombre, codigos, inicio)}
                         for x in archivos]
                lista.sort(key=lambda x: (not x["sugerido"], -(x["modificado"].timestamp() if x["modificado"] else 0), x["nombre"]))
                t["archivos"] = lista[:MAX_LISTA]
            except ErrorSP as e:
                t["error"] = str(e)
            salida.append(t)
    return salida


def traer(cliente: Cliente, pedidos: list[tuple[str, str]]) -> list[dict]:
    """Descarga los archivos elegidos ([(tipo, nombre)]). Solo acepta nombres que estén en la carpeta del cliente."""
    salida = []
    with abrir() as f:
        raiz = f.hijos([])
        cache: dict[str, tuple[Item, str | None, list[Item]]] = {}
        for tipo, nombre in pedidos:
            r = {"tipo": tipo, "archivo": nombre, "ruta": None, "modificado": None, "contenido": None, "error": None}
            try:
                if tipo not in TIPOS:
                    raise ErrorSP("Tipo de anexo no válido")
                if tipo not in cache:
                    ct = _carpeta_tipo(raiz, tipo)
                    cache[tipo] = (ct, *_archivos(f, ct, cliente))
                ct, sub, archivos = cache[tipo]
                item = next((x for x in archivos if x.nombre == nombre), None)
                if not item:
                    raise ErrorSP(f"{nombre} ya no está en la carpeta {ct.nombre}/{sub or cliente.codigo}")
                r["ruta"] = f"{ct.nombre}/{sub}/{item.nombre}"
                r["modificado"] = item.modificado
                r["contenido"] = f.leer(item)
            except ErrorSP as e:
                r["error"] = str(e)
            salida.append(r)
    return salida


def probar(clientes: list[Cliente]) -> dict:
    """Conecta y revisa las carpetas de los anexos y qué clientes tienen subcarpeta en cada una."""
    with abrir() as f:
        raiz = f.hijos([])
        tipos = []
        for tipo, (nombre, _) in TIPOS.items():
            t = {"tipo": tipo, "nombre": nombre, "carpeta": None, "error": None, "sin_carpeta": []}
            try:
                ct = _carpeta_tipo(raiz, tipo)
                t["carpeta"] = ct.nombre
                subs = {x.nombre.strip().lower() for x in f.hijos([ct.nombre]) if x.carpeta}
                t["sin_carpeta"] = [c.codigo for c in clientes if not any(n.lower() in subs for n in nombres_cliente(c))]
            except ErrorSP as e:
                t["error"] = str(e)
            tipos.append(t)
    return {"modo": settings.sharepoint_modo, "carpetas_base": len([x for x in raiz if x.carpeta]), "tipos": tipos}


def estado() -> dict:
    """Cómo va la configuración (sin conectarse a nada): para la guía de pasos de Configuración → SharePoint."""
    try:
        montada = MONTADA.is_dir() and any(MONTADA.iterdir())
    except OSError:
        montada = False
    base = None
    if montada:
        try:
            base = MONTADA.joinpath(*_partes(settings.sharepoint_ruta)).is_dir()
        except (ErrorSP, OSError):
            base = False
    return {
        "modo": settings.sharepoint_modo,
        "carpeta_montada": montada,
        "carpeta_base": settings.sharepoint_ruta or "",
        "carpeta_base_existe": base,
        "graph": {"sitio": bool(settings.sharepoint_sitio), "tenant": bool(settings.sharepoint_tenant),
                  "cliente_id": bool(settings.sharepoint_cliente_id), "secreto": bool(settings.sharepoint_secreto)},
        "carpetas": {t: getattr(settings, f"sharepoint_carpeta_{t}") for t in TIPOS},
        "nombres": {t: n for t, (n, _) in TIPOS.items()},
    }
