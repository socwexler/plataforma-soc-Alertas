"""Lectura de los anexos exportados de FortiSIEM (CSV o Excel).

El tipo de cada tabla se detecta por sus encabezados, así que sirven tanto los CSV crudos
(p. ej. "Paises salientes.csv", "report1794971796.csv") como las hojas de los Excel que hoy
alimentan Power BI (Paises_Entrantes, Puertos_Saliente, IPs, Fuentes…).
Solo se guarda lo agregado (top por país, puerto, ataque), no las filas crudas.
"""
import csv
import io
from collections import Counter, defaultdict
from datetime import date, datetime

from openpyxl import load_workbook

from ..normalizacion import clave
from .paises import es_colombia, pais_es

TOP = 30
# Puertos de uso habitual que no se reportan como "no comunes"
PUERTOS_COMUNES = {20, 21, 22, 23, 25, 53, 67, 68, 80, 88, 110, 123, 135, 137, 138, 139, 143, 161, 162, 389, 443,
                   445, 465, 514, 587, 636, 993, 995, 1433, 1521, 3306, 3389, 5432, 8080, 8081, 8443, 9092}
ACCIONES_BLOQUEO = ("drop", "block", "deny", "reset", "reject", "bloq")


class ErrorAnexo(Exception):
    pass


# ------------------------------------------------------------------ lectura
def _num(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "")
    if not s or s == "\\N":
        return 0.0
    if s.count(",") and s.count("."):          # 1.234,5 o 1,234.5
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif s.count(",") == 1 and len(s.split(",")[1]) != 3:
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _txt(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return None if s in ("", "\\N") else s


def _tablas_csv(contenido: bytes):
    for cod in ("utf-8-sig", "latin-1"):
        try:
            texto = contenido.decode(cod)
            break
        except UnicodeDecodeError:
            continue
    primera = texto.split("\n", 1)[0]
    sep = ";" if primera.count(";") > primera.count(",") else ","
    lector = csv.reader(io.StringIO(texto), delimiter=sep)
    enc = next(lector, None)
    if enc:
        yield "CSV", enc, lector


def _tablas_xlsx(contenido: bytes):
    wb = load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    try:
        for ws in wb.worksheets:
            ws.reset_dimensions()
            filas = ws.iter_rows(values_only=True)
            for _ in range(10):  # el encabezado puede no estar en la primera fila
                enc = next(filas, None)
                if enc is None:
                    break
                celdas = [c for c in enc if c not in (None, "")]
                # un encabezado tiene al menos 2 celdas y ninguna es un párrafo
                if len(celdas) >= 2 and all(len(str(c)) <= 80 for c in celdas) and _detectar([clave(c) for c in enc]):
                    yield ws.title, list(enc), filas
                    break
    finally:
        wb.close()


# ------------------------------------------------------------------ detección
def _col(claves: list[str], *patrones, excluir=()) -> int | None:
    """Patrones: 'x' exacto, 'x*' empieza por, '*x' o '*x*' contiene."""
    for p in patrones:
        for i, k in enumerate(claves):
            if not k or any(x in k for x in excluir):
                continue
            if p.startswith("*"):
                ok = p.strip("*") in k
            elif p.endswith("*"):
                ok = k.startswith(p[:-1])
            else:
                ok = k == p
            if ok:
                return i
    return None


def _col_total(claves):
    return _col(claves, "total", "cantidad eventos", "cantidad", "conteo", "count*", "*count", "*total", "eventos")


def _detectar(claves: list[str]) -> str | None:
    if _col(claves, "*nombre amenaza") is not None:
        return "boletines"
    if _col(claves, "mes periodo", "*periodo") is not None and _col(claves, "cantidad", "*eps") is not None \
            and _col(claves, "*pais") is None:
        return "eps"
    if _col(claves, "*attack name", "*ataque") is not None and _col_total(claves) is not None:
        return "ips"
    if _col(claves, "*puerto*", "*port", excluir=("report",)) is not None and _col_total(claves) is not None \
            and _col(claves, "*attack name") is None:
        return "puertos"
    if _col(claves, "*pais*", "pais*") is not None and _col_total(claves) is not None:
        return "paises"
    if _col(claves, "nombre") is not None and _col(claves, "ip") is not None and _col(claves, "tipo") is not None:
        return "fuentes"
    return None


# ------------------------------------------------------------------ agregados
def _top(c: Counter, n=TOP):
    return c.most_common(n)


def _paises(claves, filas):
    ip = _col(claves, "*pais*", "pais*")
    it = _col_total(claves)
    nombre = claves[ip]
    tipo = "paises_salientes" if "destino" in nombre else "paises_entrantes"
    c, n = Counter(), 0
    for r in filas:
        if ip >= len(r):
            continue
        n += 1
        if es_colombia(_txt(r[ip])):
            continue
        c[pais_es(_txt(r[ip]))] += _num(r[it]) if it < len(r) else 0
    return tipo, [{"pais": p, "total": int(v)} for p, v in _top(c) if v > 0], n


def _puertos(claves, filas):
    ip_ = _col(claves, "*puerto*", "*port", excluir=("report",))
    isv = _col(claves, "*servicio*", "*service*")
    idr = _col(claves, "*direccion*", "entrante saliente", "*direction*")
    it = _col_total(claves)
    ent, sal, n = Counter(), Counter(), 0
    for r in filas:
        if ip_ >= len(r):
            continue
        try:
            puerto = int(_num(r[ip_]))
        except (TypeError, ValueError):
            continue
        n += 1
        if not puerto or puerto in PUERTOS_COMUNES:
            continue
        servicio = _txt(r[isv]) if isv is not None and isv < len(r) else None
        direccion = clave(_txt(r[idr])) if idr is not None and idr < len(r) and _txt(r[idr]) else ""
        destino = ent if direccion.startswith(("in", "entra")) else sal if direccion.startswith(("out", "sal")) else None
        if destino is not None:
            destino[(puerto, servicio or f"{puerto}")] += _num(r[it]) if it < len(r) else 0
    fmt = lambda c: [{"puerto": p, "servicio": s, "total": int(v)} for (p, s), v in _top(c)]  # noqa: E731
    return "puertos", {"entrantes": fmt(ent), "salientes": fmt(sal)}, n


def _ips(claves, filas):
    ia = _col(claves, "*attack name", "*ataque")
    iac = _col(claves, "*firewall action", "*action", "*accion")
    isev = _col(claves, "*severity*", "*severidad*")
    it = _col_total(claves)
    bloq, perm, sev, n = Counter(), Counter(), {}, 0
    for r in filas:
        ataque = _txt(r[ia]) if ia < len(r) else None
        if not ataque:
            continue
        n += 1
        accion = clave(_txt(r[iac])) if iac is not None and iac < len(r) else ""
        (bloq if any(a in accion for a in ACCIONES_BLOQUEO) else perm)[ataque] += _num(r[it]) if it < len(r) else 0
        if isev is not None and isev < len(r) and _txt(r[isev]):
            sev[ataque] = _txt(r[isev])
    fmt = lambda c: [{"ataque": a, "total": int(v), "severidad": sev.get(a)} for a, v in _top(c)]  # noqa: E731
    return "ips", {"bloqueados": fmt(bloq), "permitidos": fmt(perm)}, n


def _fuentes(claves, filas):
    inom, iip, itipo = _col(claves, "nombre"), _col(claves, "ip"), _col(claves, "tipo")
    imod = _col(claves, "modelo")
    ienv = _col(claves, "*envia*")
    iestados = [i for i in (_col(claves, "estado"), _col(claves, "status"), _col(claves, "fecha")) if i is not None]
    por_tipo, por_estado, lista = Counter(), Counter(), []
    envian = no_envian = 0
    hay_envio = False
    for r in filas:
        nombre = _txt(r[inom]) if inom < len(r) else None
        if not nombre:
            continue
        tipo = (_txt(r[itipo]) if itipo < len(r) else None) or "Sin tipo"
        por_tipo[tipo] += 1
        # Estado en FortiSIEM ("Aprobado", "No administrado"): primera columna con un valor que no sea fecha
        estado = next((_txt(r[i]) for i in iestados
                       if i < len(r) and _txt(r[i]) and not isinstance(r[i], (date, datetime))), None)
        if estado:
            por_estado[estado] += 1
        envio = clave(_txt(r[ienv])) if ienv is not None and ienv < len(r) and _txt(r[ienv]) else ""
        if envio:
            hay_envio = True
            if envio.startswith(("si", "s ", "yes", "true", "envia")) or envio == "1":
                envian += 1
            else:
                no_envian += 1
        lista.append({"nombre": nombre, "ip": _txt(r[iip]) if iip < len(r) else None, "tipo": tipo,
                      "modelo": _txt(r[imod]) if imod is not None and imod < len(r) else None, "estado": estado})
    datos = {"total": len(lista), "por_tipo": [{"tipo": t, "total": v} for t, v in por_tipo.most_common()],
             "por_estado": [{"estado": e, "total": v} for e, v in por_estado.most_common()],
             "envian": envian if hay_envio else None, "no_envian": no_envian if hay_envio else None,
             "lista": lista[:2000]}
    return "fuentes", datos, len(lista)


def _eps(claves, filas):
    ip = _col(claves, "mes periodo", "*periodo")
    iv = _col(claves, "cantidad", "*eps")
    salida = []
    for r in filas:
        if ip < len(r) and _txt(r[ip]) and iv < len(r) and _num(r[iv]):
            salida.append({"periodo": _txt(r[ip]), "valor": round(_num(r[iv]), 2)})
    return "eps", salida, len(salida)


def _boletines(claves, filas):
    i = {k: _col(claves, *p) for k, p in {"nombre": ("*nombre amenaza",), "tipo": ("tipo",),
                                           "fecha": ("*fecha*",), "resumen": ("*resumen*", "*impacto*")}.items()}
    salida = []
    for r in filas:
        g = lambda k: r[i[k]] if i[k] is not None and i[k] < len(r) else None  # noqa: E731
        if not _txt(g("nombre")):
            continue
        f = g("fecha")
        salida.append({"nombre": _txt(g("nombre")), "tipo": _txt(g("tipo")),
                       "fecha": f.date().isoformat() if isinstance(f, datetime) else _txt(f),
                       "resumen": (_txt(g("resumen")) or "").replace("\r\r\n", " ").replace("\r\n", " ")})
    return "boletines", salida, len(salida)


PROCESADORES = {"paises": _paises, "puertos": _puertos, "ips": _ips, "fuentes": _fuentes, "eps": _eps,
                "boletines": _boletines}
NOMBRES = {"paises_entrantes": "Países entrantes", "paises_salientes": "Países salientes", "puertos": "Puertos",
           "ips": "Ataques IPS", "fuentes": "Fuentes integradas", "eps": "EPS", "boletines": "Boletines"}


def leer_anexo(nombre: str, contenido: bytes) -> list[dict]:
    """Devuelve [{tipo, origen, filas, datos}] por cada tabla reconocida del archivo."""
    n = nombre.lower()
    if n.endswith((".xlsx", ".xlsm")):
        tablas = _tablas_xlsx(contenido)
    elif n.endswith((".csv", ".txt")):
        tablas = _tablas_csv(contenido)
    else:
        raise ErrorAnexo("Formato no soportado: use CSV o Excel (.xlsx)")
    salida = []
    try:
        for origen, enc, filas in tablas:
            claves = [clave(c) for c in enc]
            tipo = _detectar(claves)
            if not tipo:
                continue
            t, datos, cuenta = PROCESADORES[tipo](claves, filas)
            salida.append({"tipo": t, "origen": origen, "filas": cuenta, "datos": datos})
    except (csv.Error, ValueError) as e:
        raise ErrorAnexo(f"No se pudo leer {nombre}: {e}") from e
    if not salida:
        raise ErrorAnexo(f"No se reconoció el contenido de {nombre}. Se esperan exportes de FortiSIEM de países, "
                         "puertos, ataques IPS o fuentes (o las hojas del Excel del informe).")
    return salida


def aplicar(anexos: dict, leidos: list[dict]) -> tuple[dict, list | None, list | None]:
    """Combina lo leído con los anexos existentes. Devuelve (anexos, historico_eps, boletines).

    Cada tipo reemplaza al anterior, salvo los puertos y ataques IPS, que se reemplazan por lado
    (entrantes/salientes, bloqueados/permitidos) solo si el archivo trae datos de ese lado,
    para poder cargar entrantes y salientes en archivos separados.
    """
    nuevo = dict(anexos or {})
    eps = boletines = None
    for t in leidos:
        tipo, datos = t["tipo"], t["datos"]
        if tipo == "eps":
            eps = datos
        elif tipo == "boletines":
            boletines = datos
        elif tipo in ("puertos", "ips"):
            actual = dict(nuevo.get(tipo) or {})
            for lado, valor in datos.items():
                if valor:
                    actual[lado] = valor
                actual.setdefault(lado, [])
            nuevo[tipo] = actual
        elif tipo == "fuentes":
            nuevo["fuentes_noc" if "noc" in t["origen"].lower() else "fuentes"] = datos
        else:
            nuevo[tipo] = datos
    if eps:
        nuevo["eps_historico"] = eps
    return nuevo, eps, boletines


def resumen(t: dict) -> str:
    d = t["datos"]
    if t["tipo"].startswith("paises"):
        return f"{len(d)} países (sin Colombia)" + (f"; principal: {d[0]['pais']}" if d else "")
    if t["tipo"] == "puertos":
        return f"{len(d['entrantes'])} puertos no comunes entrantes y {len(d['salientes'])} salientes"
    if t["tipo"] == "ips":
        return f"{len(d['bloqueados'])} ataques bloqueados y {len(d['permitidos'])} permitidos/detectados"
    if t["tipo"] == "fuentes":
        return f"{d['total']} fuentes, {len(d['por_tipo'])} tipos"
    if t["tipo"] == "eps":
        return ", ".join(f"{x['periodo']}: {x['valor']}" for x in d)
    if t["tipo"] == "boletines":
        return f"{len(d)} boletines"
    return ""
