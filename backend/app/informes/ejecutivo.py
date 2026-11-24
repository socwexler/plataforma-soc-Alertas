"""Contenido de la presentación ejecutiva: lo que se calcula además de contenido.armar()."""
from datetime import date

from ..config import settings
from .textos import _gestion, lista, n, pct

DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
RESPONSABLE = {"WX": "Wexler", "CLIENTE": "Cliente", "AMBOS": "Compartida"}
FILAS_ANEXO = 22


def _variacion(antes: int, ahora: int) -> dict | None:
    if not antes:
        return None
    d = ahora - antes
    return {"dif": abs(d), "signo": "▲" if d > 0 else "▼" if d < 0 else "=", "pct": f"{abs(d) / antes * 100:.0f} %"}


def _pico(por_dia: list[dict]) -> str:
    """Día o días con más eventos (puede haber empate)."""
    mx = max((d["total"] for d in por_dia), default=0)
    if not mx:
        return ""
    dias = [date.fromisoformat(d["dia"]) for d in por_dia if d["total"] == mx]
    txt = [f"{f.day} de {MESES[f.month - 1]}" for f in dias]
    if len(dias) == 1:
        return f"El día con más eventos fue el {txt[0]} ({n(mx)})."
    if len(dias) <= 3:
        return f"Los días con más eventos fueron {lista(txt)} ({n(mx)} cada uno)."
    return f"{len(dias)} días tuvieron el máximo de {n(mx)} eventos." if mx > 1 else "Ningún día tuvo más de un evento."


def _lectura(d: dict) -> list[str]:
    """Frases de comportamiento, solo con lo que los datos permiten afirmar."""
    total = sum(d["por_hora"])
    if not total:
        return []
    f = []
    pico = _pico(d["por_dia"])
    if pico:
        f.append(pico)
    sin = sum(1 for x in d["por_dia"] if not x["total"])
    if sin:
        f.append(f"{n(sin)} de {n(len(d['por_dia']))} días no tuvieron eventos escalados." if sin > 1 else f"1 de {n(len(d['por_dia']))} días no tuvo eventos escalados.")
    habil = sum(v for h, v in enumerate(d["por_hora"]) if 7 <= h < 18)
    f.append(f"El {pct(total - habil, total)} de los eventos ocurrió fuera del horario de 7:00 a 18:00.")
    fin = sum(d["por_semana"][5:])
    if sum(d["por_semana"]):
        f.append(f"El {pct(fin, sum(d['por_semana']))} se presentó en sábado o domingo.")
    return f


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
    total = len(lista)
    return {
        "frentes": [{"nombre": k, "items": v, "avance": round(sum(x["avance"] for x in v) / len(v)), "listas": sum(x["avance"] >= 100 for x in v)} for k, v in frentes.items()],
        "total": total, "completas": sum(a["avance"] >= 100 for a in lista), "curso": sum(0 < a["avance"] < 100 for a in lista),
        "pendientes": sum(a["avance"] == 0 for a in lista), "avance": round(sum(a["avance"] for a in lista) / total),
        "por_responsable": [(RESPONSABLE[k], sum(a["responsable"] == k for a in lista)) for k in ("WX", "CLIENTE", "AMBOS")],
    }


def _repartir(frentes: list[dict], columnas: int = 3) -> list[list[dict]]:
    """Reparte las tarjetas por frente en columnas de alto parecido."""
    cols: list[list] = [[] for _ in range(columnas)]
    alto = [0] * columnas
    for f in frentes:
        i = alto.index(min(alto))
        cols[i].append(f)
        alto[i] += 2 + len(f["items"])
    return cols


def _paginas_actividades(act: dict | None, maximo: int = 24) -> list[list[list[dict]]]:
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
            "det": d, "var": _variacion(P[-2]["total"], P[-1]["total"]), "lectura": _lectura(d) if d else [],
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
    gestion = [x.strip(" •-\t") for x in (ctx["t"].get("gestion") or "").split("\n") if x.strip()]
    if "gestion" not in (informe.textos or {}):   # informe creado antes de que existiera este texto
        gestion = _gestion(informe, {"servicios": {s: sv["d"] for s, sv in ctx["serv"].items()}, "mostrar_tiempos": ctx["mostrar_tiempos"]})
    if not ctx["mostrar_tiempos"]:   # textos generados cuando estaba activado
        gestion = [x for x in gestion if not x.startswith(("Notificación SOC:", "Notificación NOC:"))]
    return {"ex": servicios, "act": act, "act_paginas": _paginas_actividades(act), "gestion": gestion, "dias_semana": DIAS, "sla_minutos": settings.sla_minutos,
            "estados": {"SIN_RETRO": "Sin retroalimentación", "CON_RETRO": "Con retroalimentación", "CERRADO": "Cerrado"},
            "ips_permitidos": ((informe.anexos or {}).get("ips") or {}).get("permitidos", [])[:8]}
