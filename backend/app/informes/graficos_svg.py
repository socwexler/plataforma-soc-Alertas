"""Gráficos SVG simples para el PDF (WeasyPrint los dibuja como vectores)."""
from html import escape

# Paleta validada con validate_palette.js (modo claro)
COLOR_CRIT = {"Baja": "#2a78d6", "Media": "#eda100", "Alta": "#e34948", "Crítica": "#9b2f6e"}
SERIE = "#E12C26"  # rojo Wexler (serie única)
TINTA, TENUE, GRILLA = "#1b2533", "#5d6b7c", "#e6eaf0"
FUENTE = "font-family:Lato,'DejaVu Sans',sans-serif"


def _n(v) -> str:
    return f"{int(round(v)):,}".replace(",", ".")


def _corta(s: str, maximo: int) -> str:
    return s if len(s) <= maximo else s[: maximo - 1] + "…"


def _escala(maximo: float) -> tuple[float, list[float]]:
    if maximo <= 0:
        return 4, [0, 1, 2, 3, 4]
    crudo = maximo / 4
    mag = 10 ** (len(str(int(crudo))) - 1)
    paso = next(p * mag for p in (1, 2, 2.5, 5, 10) if p * mag >= crudo)
    return paso * 4, [paso * i for i in range(5)]


def _barra_v(x, y, w, h, r=4):
    if h <= 0:
        return ""
    r = min(r, w / 2, h)
    return f"M{x:.1f},{y + h:.1f}V{y + r:.1f}Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f}H{x + w - r:.1f}" \
           f"Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f}V{y + h:.1f}Z"


def barras_h(items: list[tuple[str, float]], ancho=480, color=SERIE, etiqueta_max=46, alto_barra=14, sep=10, tam=10) -> str:
    """Barras horizontales: etiqueta a la izquierda, valor directo al final de la barra."""
    if not items:
        return ""
    largo = max(len(_corta(e, etiqueta_max)) for e, _ in items)
    izq = min(int(ancho * 0.48), max(90, int(largo * 0.56 * tam) + 12))
    der = int(7 * tam)
    w = ancho - izq - der
    maximo = max(v for _, v in items) or 1
    alto = len(items) * (alto_barra + sep) + 4
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho} {alto}" style="{FUENTE}">']
    for i, (etq, v) in enumerate(items):
        y = i * (alto_barra + sep) + 2
        bw = max(2, w * v / maximo)
        p.append(f'<text x="{izq - 8}" y="{y + alto_barra / 2}" dy="0.35em" text-anchor="end" font-size="{tam}" fill="{TINTA}">{escape(_corta(etq, etiqueta_max))}</text>')
        p.append(f'<rect x="{izq}" y="{y}" width="{w}" height="{alto_barra}" rx="4" fill="#eef2f6"/>')
        p.append(f'<rect x="{izq}" y="{y}" width="{bw:.1f}" height="{alto_barra}" rx="4" fill="{color}"/>')
        p.append(f'<text x="{izq + bw + 6:.1f}" y="{y + alto_barra / 2}" dy="0.35em" font-size="{tam}" font-weight="600" fill="{TINTA}">{_n(v)}</text>')
    p.append("</svg>")
    return "".join(p)


def columnas(categorias: list[str], series: list[tuple[str, str, list[float]]], ancho=480, alto=220,
             leyenda=True, totales=True, formato=_n, tam=10) -> str:
    """Columnas apiladas (series de abajo hacia arriba) con total encima y leyenda."""
    if not categorias:
        return ""
    m_izq, m_der, m_arr, m_aba = int(4.4 * tam), 10, int(2.2 * tam) if totales else 10, int(3 * tam)
    ley_alto = int(2.2 * tam) if leyenda and len(series) > 1 else 0
    w, h = ancho - m_izq - m_der, alto - m_arr - m_aba - ley_alto
    tot = [sum(s[2][i] for s in series) for i in range(len(categorias))]
    tope, pasos = _escala(max(tot))
    banda = w / len(categorias)
    bw = min(70, banda * 0.55)
    y = lambda v: m_arr + ley_alto + h - (v / tope) * h  # noqa: E731
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho} {alto}" style="{FUENTE}">']
    if ley_alto:
        x = m_izq
        for nombre, color, _ in reversed(series):
            p.append(f'<rect x="{x}" y="4" width="{tam}" height="{tam}" rx="3" fill="{color}"/>'
                     f'<text x="{x + 1.5 * tam}" y="{4 + tam / 2}" dy="0.35em" font-size="{tam}" fill="{TENUE}">{escape(nombre)}</text>')
            x += 2.6 * tam + len(nombre) * 0.6 * tam
    for v in pasos:
        p.append(f'<line x1="{m_izq}" x2="{m_izq + w}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="{"#b9c2cd" if v == 0 else GRILLA}"/>'
                 f'<text x="{m_izq - 6}" y="{y(v):.1f}" dy="0.35em" text-anchor="end" font-size="{tam - 1}" fill="{TENUE}">{formato(v)}</text>')
    for i, cat in enumerate(categorias):
        x = m_izq + i * banda + (banda - bw) / 2
        acum = 0
        visibles = [s for s in series if s[2][i] > 0]
        for j, (nombre, color, vals) in enumerate(visibles):
            v = vals[i]
            y0 = y(acum + v)
            hh = y(acum) - y0 - (2 if acum > 0 else 0)
            acum += v
            if j == len(visibles) - 1:
                p.append(f'<path d="{_barra_v(x, y0, bw, hh)}" fill="{color}"/>')
            else:
                p.append(f'<rect x="{x:.1f}" y="{y0:.1f}" width="{bw:.1f}" height="{max(0, hh):.1f}" fill="{color}"/>')
        if totales:
            p.append(f'<text x="{x + bw / 2:.1f}" y="{y(tot[i]) - 6:.1f}" text-anchor="middle" font-size="{tam}" font-weight="600" fill="{TINTA}">{formato(tot[i])}</text>')
        p.append(f'<text x="{m_izq + i * banda + banda / 2:.1f}" y="{alto - tam}" text-anchor="middle" font-size="{tam - 0.5}" fill="{TENUE}">{escape(cat)}</text>')
    p.append("</svg>")
    return "".join(p)
