"""Contenido de la presentación ejecutiva: lo que se calcula además de contenido.armar()."""
from datetime import date

from .textos import pct

DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
RESPONSABLE = {"WX": "Wexler", "CLIENTE": "Cliente", "AMBOS": "Compartida"}
FILAS_ANEXO = 22


def _variacion(antes: int, ahora: int) -> dict | None:
    if not antes:
        return None
    d = ahora - antes
    return {"dif": abs(d), "signo": "▲" if d > 0 else "▼" if d < 0 else "=", "pct": f"{abs(d) / antes * 100:.0f} %"}


def _actividades(lista: list[dict]) -> dict | None:
    if not lista:
        return None
    frentes: dict[str, list] = {}
    for a in lista:
        try:
            c = date.fromisoformat(a.get("compromiso") or "").strftime("%d/%m/%Y")
        except ValueError:
            c = None
        frentes.setdefault(a["frente"], []).append({**a, "quien": RESPONSABLE.get(a["responsable"], a["responsable"]), "compromiso_txt": c})
    return {
        "frentes": [{"nombre": k, "items": v, "avance": round(sum(x["avance"] for x in v) / len(v)), "listas": sum(x["avance"] >= 100 for x in v)} for k, v in frentes.items()],
        "total": len(lista), "completas": sum(a["avance"] >= 100 for a in lista),
    }


def _repartir(frentes: list[dict], columnas: int = 3) -> dict:
    """Reparte las tarjetas por frente en columnas de alto parecido; con pocas, se ven más grandes."""
    cols: list[list] = [[] for _ in range(columnas)]
    alto = [0] * columnas
    for f in frentes:
        i = alto.index(min(alto))
        cols[i].append(f)
        alto[i] += 2 + len(f["items"])
    cols = [c for c in cols if c]
    return {"columnas": cols, "n": len(cols), "zoom": round(min(1.5, max(1, 15 / max(alto))), 2)}


def _paginas_actividades(act: dict | None, maximo: int = 24) -> list[dict]:
    """Divide en páginas si hay muchas actividades (un frente largo se parte)."""
    if not act:
        return []
    trozos = []
    for f in act["frentes"]:
        for k in range(0, len(f["items"]), 8):
            trozos.append({**f, "items": f["items"][k:k + 8], "sigue": k > 0})
    paginas, actual, filas = [], [], 0
    for t in trozos:
        alto = 2 + len(t["items"])
        if actual and filas + alto > maximo:
            paginas.append(_repartir(actual))
            actual, filas = [], 0
        actual.append(t)
        filas += alto
    if actual:
        paginas.append(_repartir(actual))
    return paginas


def armar(informe, ctx: dict) -> dict:
    servicios = {}
    for s, sv in ctx["serv"].items():
        d = sv["d"].get("detalle") or {}   # los informes finales antiguos no lo tienen
        P = sv["d"]["periodos"]
        casos = d.get("casos") or []
        servicios[s] = {
            "det": d, "var": _variacion(P[-2]["total"], P[-1]["total"]),
            "max_dia": max([x["total"] for x in d.get("por_dia", [])] + [1]), "max_hora": max(d.get("por_hora") or [1]) or 1,
            "max_semana": max(d.get("por_semana") or [1]) or 1,
            "dias": [{**x, "num": int(x["dia"][8:]), "mes": MESES[int(x["dia"][5:7]) - 1], "finde": date.fromisoformat(x["dia"]).weekday() >= 5} for x in d.get("por_dia", [])],
            "anexo": [casos[i:i + FILAS_ANEXO] for i in range(0, len(casos), FILAS_ANEXO)],
            # solo si está activado en Configuración y el informe conserva el texto de tiempos
            "sla": pct(sv["actual"]["dentro_sla"], sv["actual"]["con_tiempo"]) if ctx["mostrar_tiempos"] and sv["actual"]["con_tiempo"] and (ctx["t"].get(f"tiempos_{s}") or "").strip() else None,
            "sla_f": sv["actual"]["dentro_sla"] / sv["actual"]["con_tiempo"] if sv["actual"]["con_tiempo"] else 0,
            # pocos destacados: van en la misma página que los pendientes
            "juntos": 0 < len(sv["d"]["destacados"]) <= 4 and bool(d.get("sin_respuesta")),
            "retro_f": sv["actual"]["con_retro"] / sv["actual"]["total"] if sv["actual"]["total"] else 0,
        }
    act = _actividades(informe.actividades or [])
    return {"ex": servicios, "act": act, "act_paginas": _paginas_actividades(act), "dias_semana": DIAS,
            "estados": {"SIN_RETRO": "Sin retroalimentación", "CON_RETRO": "Con retroalimentación", "CERRADO": "Cerrado"},
            "ips_permitidos": ((informe.anexos or {}).get("ips") or {}).get("permitidos", [])[:8]}
