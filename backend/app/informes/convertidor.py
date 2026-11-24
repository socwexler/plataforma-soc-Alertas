"""Cliente del servicio Gotenberg (contenedor `convertidor`).

- Word -> PDF con LibreOffice (actualiza la tabla de contenido y los índices).
- HTML -> PDF con Chromium (presentación).
"""
import os

import httpx

URL = os.environ.get("CONVERTIDOR_URL", "http://convertidor:3000")


class ErrorConversion(Exception):
    pass


def _post(ruta: str, files, data: dict) -> bytes:
    try:
        r = httpx.post(f"{URL}{ruta}", files=files, data=data, timeout=180)
    except httpx.HTTPError as e:
        raise ErrorConversion(f"No se pudo contactar el servicio de conversión: {e}") from e
    if r.status_code != 200:
        raise ErrorConversion(f"El servicio de conversión respondió {r.status_code}: {r.text[:300]}")
    return r.content


def word_a_pdf(docx: bytes, nombre: str = "informe.docx") -> bytes:
    return _post("/forms/libreoffice/convert", {"files": (nombre, docx)},
                 {"updateIndexes": "true", "exportBookmarks": "true"})


def html_a_pdf(html: str, ancho_pulg: float = 13.333, alto_pulg: float = 7.5) -> bytes:
    return _post("/forms/chromium/convert/html", {"files": ("index.html", html.encode("utf-8"), "text/html")}, {
        "paperWidth": str(ancho_pulg), "paperHeight": str(alto_pulg),
        "marginTop": "0", "marginBottom": "0", "marginLeft": "0", "marginRight": "0",
        "printBackground": "true", "preferCssPageSize": "true",
        "waitForExpression": "window.__listo === true",  # mapa cargado, o agotado su tiempo de espera (8 s)
    })
