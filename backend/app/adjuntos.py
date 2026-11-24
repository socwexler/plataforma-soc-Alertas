"""Validación de los archivos que se suben a un caso.

Se comprueba el contenido y no solo la extensión. No se aceptan ejecutables, macros ni HTML/SVG.
No es un antivirus: los archivos sospechosos (muestras de malware) no deben subirse aquí.
"""
import hashlib
import io
import re
import zipfile

from PIL import Image, ImageOps

from .config import settings

MB = 1024 * 1024
Image.MAX_IMAGE_PIXELS = 40_000_000
IMAGENES = {"png": ("PNG", "image/png"), "jpg": ("JPEG", "image/jpeg"), "jpeg": ("JPEG", "image/jpeg")}
OFFICE = {"docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}
TEXTO = {"txt": "text/plain", "log": "text/plain", "csv": "text/csv", "json": "application/json"}
PELIGROSAS = re.compile(r"\.(exe|dll|scr|com|bat|cmd|ps1|psm1|vbs|vbe|js|jse|wsf|wsh|hta|msi|msp|lnk|jar|iso|img|vhdx?|reg|cpl|"
                        r"html?|svg|xll|chm|one|docm|xlsm|pptm|dotm|xlam|py|sh)$", re.I)
PERMITIDAS = sorted([*IMAGENES, *OFFICE, *TEXTO, "pdf", "zip"])


class ErrorAdjunto(ValueError):
    pass


def limpiar_nombre(nombre: str | None) -> str:
    n = re.split(r"[\\/]", nombre or "")[-1]
    n = re.sub(r"[\x00-\x1f\x7f<>:\"|?*\u202a-\u202e\u2066-\u2069]", "", n).strip(" .")
    base, punto, ext = n.rpartition(".")
    return f"{base[:120]}.{ext[:10]}" if punto and base else ""


def validar(nombre: str | None, datos: bytes, tipo: str) -> dict:
    """Devuelve los campos del adjunto (nombre, mime, contenido…) o lanza ErrorAdjunto."""
    n = limpiar_nombre(nombre)
    ext = n.rpartition(".")[2].lower()
    if not n or ext not in PERMITIDAS:
        raise ErrorAdjunto(f"{n or 'Archivo sin nombre'}: tipo no permitido. Se aceptan: {', '.join(PERMITIDAS)}")
    if not datos:
        raise ErrorAdjunto(f"{n}: el archivo está vacío")
    if len(datos) > settings.adjunto_max_mb * MB:
        raise ErrorAdjunto(f"{n}: supera {settings.adjunto_max_mb} MB")
    ancho = None
    if ext in IMAGENES:
        formato, mime = IMAGENES[ext]
        try:
            with Image.open(io.BytesIO(datos)) as im:
                if im.format != formato:
                    raise ErrorAdjunto(f"{n}: el contenido no es {formato}")
                im.load()
                ancho = im.width
                if tipo == "EVIDENCIA":   # se vuelve a guardar sin metadatos (ubicación, equipo, autor, comentarios)
                    limpia = ImageOps.exif_transpose(im).convert("RGB" if formato == "JPEG" else "RGBA")
                    if formato == "PNG" and limpia.getextrema()[3][0] == 255:
                        limpia = limpia.convert("RGB")
                    limpia.info = {}
                    ancho, b = limpia.width, io.BytesIO()
                    limpia.save(b, formato, **({"quality": 92} if formato == "JPEG" else {"optimize": True}))
                    datos = b.getvalue()
        except ErrorAdjunto:
            raise
        except Exception as e:
            raise ErrorAdjunto(f"{n}: no es una imagen válida") from e
    elif tipo == "EVIDENCIA":
        raise ErrorAdjunto(f"{n}: las evidencias deben ser imágenes PNG o JPG; súbalo como adjunto")
    elif ext == "pdf":
        mime = "application/pdf"
        if not datos[:1024].lstrip().startswith(b"%PDF-"):
            raise ErrorAdjunto(f"{n}: el contenido no es un PDF")
    elif ext in OFFICE or ext == "zip":
        mime = OFFICE.get(ext, "application/zip")
        try:
            with zipfile.ZipFile(io.BytesIO(datos)) as z:
                nombres = z.namelist()
        except zipfile.BadZipFile as e:
            raise ErrorAdjunto(f"{n}: el archivo está dañado o no es {ext}") from e
        if ext in OFFICE and ("[Content_Types].xml" not in nombres or any("vbaproject" in x.lower() for x in nombres)):
            raise ErrorAdjunto(f"{n}: no es un documento válido o contiene macros")
        malo = next((x for x in nombres if PELIGROSAS.search(x)), None) if ext == "zip" else None
        if malo:
            raise ErrorAdjunto(f"{n}: contiene un archivo no permitido ({malo[:60]})")
    else:
        mime = TEXTO[ext]
        if b"\x00" in datos[:65536] and not datos.startswith((b"\xff\xfe", b"\xfe\xff")):
            raise ErrorAdjunto(f"{n}: no es un archivo de texto")
    return {"nombre": n, "tipo": tipo, "mime": mime, "tamano": len(datos), "ancho": ancho, "contenido": datos,
            "sha256": hashlib.sha256(datos).hexdigest()}


def texto_de(a) -> str:
    """Texto de los adjuntos de texto, para buscar menciones a otros clientes."""
    if a.mime not in TEXTO.values():
        return ""
    d = a.contenido[: 5 * MB]
    return d.decode("utf-16" if d.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8", errors="replace")
