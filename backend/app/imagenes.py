"""Imágenes de la presentación (logos y boletines): validación, recorte y tamaño."""
import io

from PIL import Image, ImageChops, ImageStat

from .adjuntos import ErrorAdjunto, validar

LOGO_MAX, BOLETIN_MAX = 900, 2000


def _recortar(im: Image.Image) -> Image.Image:
    """Quita el margen transparente o blanco alrededor del logo."""
    if im.mode == "RGBA":
        caja = im.getchannel("A").point(lambda v: 255 if v > 12 else 0).getbbox()
    else:
        dif = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255))).convert("L")
        caja = dif.point(lambda v: 255 if v > 18 else 0).getbbox()
    return im.crop(caja) if caja else im


def preparar(nombre: str | None, datos: bytes, logo: bool = False) -> dict:
    """PNG o JPG verificado, sin metadatos y con tamaño razonable para la presentación."""
    v = validar(nombre, datos, "EVIDENCIA")
    with Image.open(io.BytesIO(v["contenido"])) as im:
        im.load()
        claro = None
        if logo:
            im = _recortar(im)
            if im.width < 40 or im.height < 12:
                raise ErrorAdjunto(f"{v['nombre']}: la imagen es muy pequeña para un logo")
            # Logo blanco sobre transparente: se muestra sobre fondo oscuro para que se vea
            if im.mode == "RGBA":
                alfa = im.getchannel("A").point(lambda x: 255 if x > 60 else 0)
                claro = ImageStat.Stat(im.convert("L"), alfa).mean[0] > 190 if alfa.getbbox() else False
            else:
                claro = False
        maximo = LOGO_MAX if logo else BOLETIN_MAX
        im.thumbnail((maximo, maximo), Image.LANCZOS)
        b = io.BytesIO()
        if v["mime"] == "image/png":
            im.save(b, "PNG", optimize=True)
        else:
            im.save(b, "JPEG", quality=88)
        return {"mime": v["mime"], "contenido": b.getvalue(), "ancho": im.width, "alto": im.height, "claro": claro}
