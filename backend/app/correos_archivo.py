"""Lectura mínima de correos guardados (.eml y .msg) para validarlos antes de aceptarlos como evidencia.

Solo se comprueba que sean correos y los nombres de sus adjuntos; no se abre ni se muestra su contenido.
"""
import struct
from email import message_from_bytes
from email.policy import default


class ErrorCorreoArchivo(ValueError):
    pass


# Un borrador sin enviar (como el que genera la plataforma) no trae remitente ni fecha
CABECERAS = ("From", "To", "Cc", "Bcc", "Subject", "Date", "Message-ID", "Received", "MIME-Version", "X-Unsent")


def adjuntos_eml(datos: bytes) -> list[str]:
    """Nombres de los archivos que trae un .eml (incluye los de correos anidados)."""
    try:
        m = message_from_bytes(datos.removeprefix(b"\xef\xbb\xbf").lstrip(), policy=default)
        if b"\x00" in datos[:65536] or not (m["From"] or m["To"] or m["Subject"]) or sum(1 for k in CABECERAS if m[k]) < 2:
            raise ErrorCorreoArchivo("el contenido no es un correo")
        # un correo anidado se llama como su asunto, que puede terminar en «.com»
        return [n for p in m.walk() if p.get_content_type() != "message/rfc822" and (n := p.get_filename())]
    except ErrorCorreoArchivo:
        raise
    except Exception as e:
        raise ErrorCorreoArchivo("no se pudo leer como correo") from e


NO_OUTLOOK, DANADO = "el contenido no es un mensaje de Outlook", "el archivo está dañado o incompleto"
LIBRE = 0xFFFFFFFA   # desde aquí son marcas (fin de cadena, libre…), no sectores


class _Ole:
    """Contenedor OLE (formato del .msg): lista de entradas y lectura de una entrada."""

    def __init__(self, d: bytes):
        if d[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            raise ErrorCorreoArchivo(NO_OUTLOOK)
        self.d = d
        desp, desp_mini = struct.unpack_from("<HH", d, 30)
        if desp not in (9, 12) or desp_mini != 6:
            raise ErrorCorreoArchivo(NO_OUTLOOK)
        self.tam = 1 << desp
        directorio, _, self.corte, mini, _, difat, _ = struct.unpack_from("<7I", d, 48)
        sectores = list(struct.unpack_from("<109I", d, 76))
        vistos = set()
        while difat < LIBRE:
            if difat in vistos:
                raise ErrorCorreoArchivo(DANADO)
            vistos.add(difat)
            v = self._enteros(self._sector(difat))
            sectores += v[:-1]
            difat = v[-1]
        sectores = [s for s in sectores if s < LIBRE]
        if len(set(sectores)) != len(sectores):
            raise ErrorCorreoArchivo(DANADO)
        self.fat = [x for s in sectores for x in self._enteros(self._sector(s))]
        self.minifat = self._enteros(self._cadena(mini))
        dirs = self._cadena(directorio)
        self.entradas = []
        for i in range(0, len(dirs) - 127, 128):
            largo, tipo = struct.unpack_from("<HB", dirs, i + 64)
            if tipo in (1, 2, 5) and 2 <= largo <= 64:
                inicio, tamano = struct.unpack_from("<II", dirs, i + 116)
                self.entradas.append((dirs[i:i + largo - 2].decode("utf-16-le", "replace"), tipo, inicio, tamano))
        raiz = next((e for e in self.entradas if e[1] == 5), None)
        if not raiz:
            raise ErrorCorreoArchivo(NO_OUTLOOK)
        self.mini = self._cadena(raiz[2]) if raiz[3] else b""

    @staticmethod
    def _enteros(b: bytes) -> list[int]:
        return list(struct.unpack(f"<{len(b) // 4}I", b[:len(b) // 4 * 4]))

    def _sector(self, n: int) -> bytes:
        s = self.d[(n + 1) * self.tam:(n + 2) * self.tam]
        if not s:
            raise ErrorCorreoArchivo(DANADO)
        return s

    def _cadena(self, n: int) -> bytes:
        partes, vistos = [], set()
        while n < LIBRE:
            if n in vistos or n >= len(self.fat):
                raise ErrorCorreoArchivo(DANADO)
            vistos.add(n)
            partes.append(self._sector(n))
            n = self.fat[n]
        return b"".join(partes)

    def leer(self, inicio: int, tamano: int) -> bytes:
        if tamano >= self.corte:
            return self._cadena(inicio)[:tamano]
        partes, n = [], inicio
        while n < LIBRE and len(partes) * 64 < tamano:
            if n >= len(self.minifat):
                raise ErrorCorreoArchivo(DANADO)
            partes.append(self.mini[n * 64:n * 64 + 64])
            n = self.minifat[n]
        return b"".join(partes)[:tamano]


# Propiedades con el nombre largo y corto del adjunto; 001F es Unicode y 001E es ANSI
_NOMBRES = {f"__substg1.0_{p}{t}": c for p in ("3707", "3704") for t, c in (("001F", "utf-16-le"), ("001E", "cp1252"))}


def adjuntos_msg(datos: bytes) -> list[str]:
    """Nombres de los archivos que trae un .msg de Outlook (incluye los de mensajes anidados)."""
    try:
        o = _Ole(datos)
        if not any(e[0] == "__properties_version1.0" for e in o.entradas):
            raise ErrorCorreoArchivo(NO_OUTLOOK)
        return [o.leer(i, t).decode(_NOMBRES[n], "replace").strip("\x00 ")
                for n, tipo, i, t in o.entradas if tipo == 2 and n in _NOMBRES and t <= 4096]
    except struct.error as e:
        raise ErrorCorreoArchivo(DANADO) from e
