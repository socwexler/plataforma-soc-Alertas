"""Gráficos PNG (matplotlib) para el informe en Word, con la tipografía de la plantilla."""
import glob
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

for f in glob.glob("/usr/local/share/fonts/wexler/*.ttf"):
    font_manager.fontManager.addfont(f)
plt.rcParams.update({
    "font.family": ["Lato", "DejaVu Sans"], "font.size": 9, "axes.edgecolor": "#B9C2CD", "axes.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "xtick.color": "#5D6B7C", "ytick.color": "#5D6B7C", "text.color": "#1B2533",
})

ROJO = "#E12C26"          # rojo de la plantilla Wexler (serie única)
COLOR_CRIT = {"Baja": "#2A78D6", "Media": "#EDA100", "Alta": "#E34948", "Crítica": "#9B2F6E"}
GRILLA = "#E6EAF0"


def _n(v) -> str:
    return f"{int(round(v)):,}".replace(",", ".")


def _png(fig) -> bytes:
    b = io.BytesIO()
    fig.savefig(b, format="png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return b.getvalue()


def barras_h(items: list[tuple[str, float]], color=ROJO, ancho_pulg=6.3, max_etiqueta=60) -> bytes:
    etiquetas = [e if len(e) <= max_etiqueta else e[: max_etiqueta - 1] + "…" for e, _ in items]
    valores = [v for _, v in items]
    alto = 0.32 * len(items) + 0.3
    fig, ax = plt.subplots(figsize=(ancho_pulg, alto))
    y = range(len(items))
    ax.barh(list(y), valores, height=0.62, color=color, zorder=2)
    ax.set_yticks(list(y), etiquetas)
    ax.invert_yaxis()
    ax.tick_params(axis="y", length=0, labelsize=8.5)
    ax.xaxis.set_visible(False)
    ax.spines["bottom"].set_visible(False)
    tope = max(valores or [1])
    for i, v in enumerate(valores):
        ax.text(v + tope * 0.01, i, _n(v), va="center", fontsize=8.5, fontweight="bold", color="#1B2533")
    ax.set_xlim(0, tope * 1.12)
    return _png(fig)


def columnas(categorias: list[str], series: list[tuple[str, str, list[float]]], ancho_pulg=6.3, alto_pulg=2.8,
             totales=True, decimales=0) -> bytes:
    """Columnas (apiladas si hay varias series) con 2 px de separación entre segmentos y total encima."""
    fig, ax = plt.subplots(figsize=(ancho_pulg, alto_pulg))
    x = list(range(len(categorias)))
    base = [0.0] * len(categorias)
    for nombre, color, vals in series:
        ax.bar(x, vals, bottom=base, width=0.5, color=color, label=nombre, zorder=2, edgecolor="white", linewidth=1)
        base = [b + v for b, v in zip(base, vals)]
    ax.set_xticks(x, categorias)
    ax.tick_params(axis="x", length=0)
    ax.tick_params(axis="y", length=0, labelsize=8)
    ax.yaxis.grid(True, color=GRILLA, zorder=0)
    tope = max(base or [1]) or 1
    if totales:
        for i, t in enumerate(base):
            texto = f"{t:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")
            ax.text(i, t + tope * 0.02, texto, ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_ylim(0, tope * 1.15)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: _n(v)))
    if len(series) > 1:
        ax.legend(*[list(reversed(z)) for z in ax.get_legend_handles_labels()], loc="upper left",
                  bbox_to_anchor=(0, 1.18), ncol=len(series), frameon=False, fontsize=8.5, handlelength=1, handleheight=1)
    return _png(fig)
