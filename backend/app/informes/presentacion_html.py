"""Presentación interactiva del informe: un único HTML 16:9 con tipografías, fotos e imágenes incrustadas.

La misma página se usa en el navegador (navegación, índice, notas, mapa y gráficas animadas) y, con pdf=True,
para exportarla con Chromium (servicio `convertidor`) con cada diapositiva en su estado final.
Lo único que se consulta en línea son las teselas del mapa (config `MAPA_*`); sin conexión quedan las ubicaciones.
"""
import base64
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from ..config import settings
from . import ejecutivo
from .contenido import CRITS, armar
from .convertidor import html_a_pdf
from .mapa import ORIGEN, ubicar

_DIR = Path(__file__).parent
_REC = _DIR / "recursos" / "presentacion"
_env = Environment(loader=FileSystemLoader(_DIR / "plantillas"), autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
_FOTOS = {"portada": "securing-digital-data-conceptualizing-cybersecurity.jpg", "d1": "future-technology.jpg",
          "d3": "man-taps-blue-sensor-monitors-dark-lab.jpg", "d4": "network-engineer.jpg", "cierre": "businessman-man.jpg"}
_FUENTES = [("Sora", "Sora-Regular.ttf", 400), ("Sora", "Sora-Medium.ttf", 500), ("Sora", "Sora-SemiBold.ttf", 600), ("Sora", "Sora-Bold.ttf", 700),
            ("Aspekta", "Aspekta-300.otf", 300), ("Aspekta", "Aspekta-400.otf", 400), ("Aspekta", "Aspekta-500.otf", 500), ("Aspekta", "Aspekta-600.otf", 600)]


def _uri(datos: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(datos).decode()}"


@lru_cache
def recursos() -> dict:
    fuentes = "\n".join(
        f"@font-face{{font-family:{fam};src:url({_uri((_REC / 'fonts' / f).read_bytes(), 'font/ttf' if f.endswith('ttf') else 'font/otf')});"
        f"font-weight:{peso};font-display:swap}}" for fam, f, peso in _FUENTES)
    return {
        "fuentes": Markup(fuentes),
        "fotos": {k: Markup(_uri((_REC / "img" / f).read_bytes(), "image/jpeg")) for k, f in _FOTOS.items()},
        "logo": _uri((_REC / "logo/wexler-horizontal.svg").read_bytes(), "image/svg+xml"),
        "iso": Markup(_uri((_REC / "logo/wexler-isotipo.svg").read_bytes(), "image/svg+xml")),
        "css": Markup((_DIR / "plantillas/presentacion.css").read_text(encoding="utf-8")),
        "css_ejec": Markup((_DIR / "plantillas/ejecutiva.css").read_text(encoding="utf-8")),
        "isotipo": Markup(re.sub(r"<\?xml.*?\?>", "", (_REC / "logo/wexler-isotipo.svg").read_text(encoding="utf-8"))),
        "logo_oscuro": _uri((_REC / "logo/wexler-horizontal.svg").read_text(encoding="utf-8").replace("#fafafa", "#17181c").encode(), "image/svg+xml"),
        "js": Markup((_DIR / "plantillas/presentacion.js").read_text(encoding="utf-8")),
    }


def _fecha(v: str | None) -> str | None:
    try:
        return date.fromisoformat(v).strftime("%d/%m/%Y") if v else None
    except ValueError:
        return v


def _mapa(informe) -> dict:
    an = informe.anexos or {}
    m = {"origen": ORIGEN, "sin": {}, "total": {}, "base": settings.mapa_base if settings.mapa_activo and settings.mapa_base != "no" else "", "lineas": settings.mapa_lineas, "atribucion": settings.mapa_atribucion}
    for modo in ("entrantes", "salientes"):
        lista = (an.get(f"paises_{modo}") or [])[:15]
        m[modo], m["sin"][modo] = ubicar(lista)
        m["total"][modo] = sum(p["total"] for p in lista) or 1
    return m


def html(informe, metricas: dict, informe_id: int | None = None, pdf: bool = False, estilo: str = "interactiva") -> str:
    ctx = armar(informe, metricas, svg=False)
    cl = informe.cliente
    imagenes = {x.id: x for x in informe.imagenes}
    ctx["boletines"] = [{**b, "fecha_txt": _fecha(b.get("fecha")),
                         "vertical": b.get("imagen_id") in imagenes and imagenes[b["imagen_id"]].alto > imagenes[b["imagen_id"]].ancho,
                         "imagen": _uri(imagenes[b["imagen_id"]].contenido, imagenes[b["imagen_id"]].mime) if b.get("imagen_id") in imagenes else None}
                        for b in ctx["boletines"]]
    mapa = _mapa(informe)
    con = [m for m in ("entrantes", "salientes") if mapa[m]]
    ejec = estilo == "ejecutiva"
    datos = {
        "mapa": mapa, "informe_id": informe_id, "estilo": estilo, "archivo": f"{'Informe_ejecutivo' if ejec else 'Presentacion'}_{cl.codigo}_{ctx['titulo_mes'].replace(' ', '_')}.pdf",
        "pie": f"INFORME {ctx['servicios_txt']} · {cl.codigo} · {ctx['periodo']}".upper(),
    }
    extra = ejecutivo.armar(informe, ctx) if ejec else {}
    return _env.get_template("ejecutiva.html" if ejec else "presentacion.html").render(
        **ctx, **extra, rec=recursos(), mapa=mapa, datos=datos, informe_id=informe_id, pdf=pdf,
        # En el PDF no hay pestañas: un mapa por sentido
        modos_mapa=con if pdf else (["ambos"] if len(con) == 2 else con),
        crits=list(reversed(CRITS)), crits_sin=[*reversed(CRITS), "Sin"],
        logo=Markup(_uri(cl.logo, cl.logo_mime)) if cl.tiene_logo else None, logo_claro=cl.logo_claro)


def pdf(informe, metricas: dict, estilo: str = "interactiva") -> bytes:
    return html_a_pdf(html(informe, metricas, pdf=True, estilo=estilo), 20, 11.25)
