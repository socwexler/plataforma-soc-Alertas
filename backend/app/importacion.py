"""Importación de bitácoras Excel (casos, clientes, analistas y base de conocimiento).

La usan la página "Importar bitácora" y el script scripts/migrar_bitacora.py.
Reglas:
- Los casos creados en la plataforma (origen='app') nunca se modifican.
- Un número de reporte que ya existe se omite (modo solo_nuevos) o se actualiza
  con los datos del Excel (modo actualizar, solo casos importados).
- El modo reemplazar borra los casos importados y los vuelve a cargar.
"""
import json
import re
from collections import Counter
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from openpyxl import load_workbook
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from .models import Adjunto, Caso, CasoUso, Cliente, Consecutivo, Seguimiento, Usuario
from .normalizacion import clave, criticidad, estado, tactica_id, texto

MODOS = ("solo_nuevos", "actualizar", "reemplazar")
MAX_AVISOS = 300


class ErrorImportacion(Exception):
    pass


TZ = ZoneInfo("America/Bogota")

# Datos iniciales por código de cliente (día de corte, EPS…), opcionales: /datos/clientes.json. No van en el código.
ARCHIVO_CLIENTES = Path("/datos/clientes.json")
_PERMITIDOS = {"dia_corte", "eps_contratados", "fuentes_licencia", "servicio_soc", "servicio_noc", "glpi_entidad_id"}


def config_clientes() -> dict[str, dict]:
    if not ARCHIVO_CLIENTES.is_file():
        return {}
    try:
        datos = json.loads(ARCHIVO_CLIENTES.read_text(encoding="utf-8"))
        return {str(c).upper(): {k: v for k, v in d.items() if k in _PERMITIDOS} for c, d in datos.items()}
    except (OSError, ValueError, AttributeError) as e:
        raise ErrorImportacion(f"{ARCHIVO_CLIENTES.name} no se puede leer: {e}") from e


COLUMNAS = {
    "numero": ["numero de reporte"],
    "cliente": ["cliente"],
    "fecha": ["fecha"],
    "analista": ["analista"],
    "alerta": ["alerta detectada"],
    "criticidad": ["criticidad"],
    "tecnica": ["tecnica"],
    "tactica": ["tactica"],
    "resumen": ["resumen ejecutivo"],
    "analisis": ["analisis de seguridad"],
    "acciones": ["acciones de seguridad recomendadas"],
    "geo": ["geolocalizacion"],
    "reporting_ip": ["reporting ip", "fuente que reporta"],
    "log": ["log del evento"],
    "hora_evento": ["hora evento en siem", "hora evento"],
    "hora_reporte": ["hora reporte evento a cliente", "hora reporte"],
    "estado": ["estado"],
    "acciones_cliente": ["acciones ejecutadas por cliente"],
}


# ---------------------------------------------------------------- utilidades
def hoja(wb, nombre):
    ws = wb[nombre]
    ws.reset_dimensions()  # en modo solo-lectura la dimensión guardada en el archivo puede estar mal
    return ws


def filas(ws):
    for r in ws.iter_rows(values_only=True):
        yield list(r)


def buscar_encabezado(ws, primera: str, max_filas: int = 15):
    """Devuelve (índice de fila, {clave_columna: índice}) buscando la fila que contiene `primera`."""
    for i, r in enumerate(ws.iter_rows(values_only=True, max_row=max_filas)):
        claves = [clave(c) for c in r]
        if primera in claves:
            return i, {k: j for j, k in enumerate(claves) if k}
    raise ErrorImportacion(f"No se encontró el encabezado '{primera}' en la hoja {ws.title}")


def mapear(enc: dict[str, int]) -> dict[str, int | list[int]]:
    m: dict = {}
    for campo, alias in COLUMNAS.items():
        for a in alias:
            if a in enc:
                m[campo] = enc[a]
                break
    m["comentarios"] = sorted(j for k, j in enc.items() if k.startswith("comentario"))
    return m


def a_fecha(v) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, (int, float)) and v > 1000:
        return (datetime(1899, 12, 30) + timedelta(days=float(v))).date()
    if isinstance(v, str):
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(v.strip(), fmt).date()
            except ValueError:
                pass
    return None


def a_hora(v) -> time | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.time().replace(microsecond=0)
    if isinstance(v, time):
        return v.replace(microsecond=0)
    if isinstance(v, (int, float)):
        seg = round((float(v) % 1) * 86400) % 86400
        return time(seg // 3600, (seg % 3600) // 60, seg % 60)
    m = re.match(r"^\s*(\d{1,2})[:.](\d{2})(?:[:.](\d{2}))?\s*([ap])?", str(v).lower())
    if m:
        h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
        if m.group(4) == "p" and h < 12:
            h += 12
        if m.group(4) == "a" and h == 12:
            h = 0
        if h < 24 and mi < 60:
            return time(h, mi, s)
    return None


def nombre_propio(s: str) -> str:
    return " ".join(p.capitalize() for p in s.split())


def usuario_de(nombre: str, usados: set[str]) -> str:
    partes = [clave(p).replace(" ", "") for p in nombre.split() if p]
    if not partes:
        base = "analista"
    else:
        apellido = partes[-2] if len(partes) >= 4 else partes[-1]
        base = partes[0][0] + apellido
    u, i = base, 2
    while u in usados:
        u, i = f"{base}{i}", i + 1
    usados.add(u)
    return u


def separar_cliente(s: str) -> tuple[str, str]:
    s = " ".join(str(s).split())
    if " - " in s:
        cod, nom = s.split(" - ", 1)
        return cod.strip().upper(), nom.strip()
    return s.strip().upper(), s.strip()


# ---------------------------------------------------------------- cargas
def cargar_clientes(db, wb, nombres_en_casos: set[str]) -> tuple[dict[str, Cliente], list[str]]:
    textos = set(nombres_en_casos)
    if wb is not None and "INFORMACION" in wb.sheetnames:
        ws = hoja(wb, "INFORMACION")
        h, enc = buscar_encabezado(ws, "cliente")
        col = enc["cliente"]
        for i, r in enumerate(filas(ws)):
            if i > h and col < len(r) and r[col]:
                textos.add(str(r[col]))
    existentes = {c.codigo.upper(): c for c in db.scalars(select(Cliente))}
    iniciales = config_clientes()
    nuevos = []
    for t in sorted(textos):
        cod, nom = separar_cliente(t)
        if not cod:
            continue
        if cod not in existentes:
            c = Cliente(codigo=cod, nombre=nom, **iniciales.get(cod, {}))
            db.add(c)
            existentes[cod] = c
            nuevos.append(f"{cod} - {nom}")
    db.flush()
    return existentes, nuevos


def cargar_analistas(db, nombres: set[str]) -> tuple[dict[str, Usuario], list[str]]:
    por_nombre = {clave(u.nombre): u for u in db.scalars(select(Usuario))}
    usados = {u.usuario for u in por_nombre.values()}
    nuevos = []
    for n in sorted(nombres):
        if clave(n) not in por_nombre:
            u = Usuario(usuario=usuario_de(n, usados), nombre=nombre_propio(n), rol="N1")
            db.add(u)
            por_nombre[clave(n)] = u
            nuevos.append(u.nombre)
    db.flush()
    return por_nombre, nuevos


def cargar_base_conocimiento(db, wb) -> tuple[int, int]:
    existentes = {(clave(c.nombre), c.servicio) for c in db.scalars(select(CasoUso))}
    nuevos_forti = nuevos_secu = 0

    def agregar(**kw):
        k = (clave(kw["nombre"]), "SOC")
        if not kw["nombre"] or k in existentes:
            return False
        crit, aud = criticidad(kw.pop("crit"))
        aud = aud or kw["nombre"].upper().startswith("AUDITORIA")
        tac = kw.pop("tac")
        db.add(CasoUso(servicio="SOC", criticidad=crit, es_auditoria=aud, tactica_id=tactica_id(tac), **kw))
        existentes.add(k)
        return True

    if "Linea Base forti" in wb.sheetnames:
        ws = hoja(wb, "Linea Base forti")
        h, e = buscar_encabezado(ws, "nombre cdu")
        g = lambda r, k: texto(r[e[k]]) if k in e and e[k] < len(r) else None  # noqa: E731
        for i, r in enumerate(filas(ws)):
            if i <= h:
                continue
            tecnica_num = g(r, "numero tecnica")
            nuevos_forti += agregar(
                nombre=g(r, "nombre cdu"), crit=g(r, "criticdad") or g(r, "criticidad"),
                tecnica=g(r, "tecnica"), tac=g(r, "tactica"),
                tecnica_id=tecnica_num if tecnica_num and re.match(r"^T\d{4}", tecnica_num) else None,
                resumen_ejecutivo=g(r, "resumen ejecutivo"),
                acciones_recomendadas=g(r, "acciones de seguridad recomendadas"),
                tecnologia=g(r, "tecnologia"), funcionalidad=g(r, "acronimo tecnologia"),
                observaciones=g(r, "observaciones"), origen="linea_base_forti",
            )
    if "Line Base Secu" in wb.sheetnames:
        ws = hoja(wb, "Line Base Secu")
        h, e = buscar_encabezado(ws, "nombre del caso de uso")
        g = lambda r, k: texto(r[e[k]]) if k in e and e[k] < len(r) else None  # noqa: E731
        for i, r in enumerate(filas(ws)):
            if i <= h:
                continue
            nuevos_secu += agregar(
                nombre=g(r, "nombre del caso de uso"), crit=g(r, "criticidad"), tecnica=g(r, "tecnica"),
                tac=g(r, "tactica"), tecnologia=g(r, "tipo de fuente"), funcionalidad=g(r, "funcionalidad"),
                origen="linea_base_secu",
            )
    db.flush()
    return nuevos_forti, nuevos_secu


# ---------------------------------------------------------------- casos
CAMPOS_CASO = ("servicio", "cliente_id", "analista_id", "caso_uso_id", "alerta", "criticidad", "tecnica", "tactica_id",
               "tactica_original", "resumen_ejecutivo", "analisis", "acciones_recomendadas", "geolocalizacion",
               "reporting_ip", "log_evento", "fecha_evento", "fecha_reporte", "fecha_bitacora", "estado", "acciones_cliente")


class _Resultado:
    def __init__(self):
        self.st = Counter()
        self.avisos: list[dict] = []
        self.tacticas_sin_mapear = Counter()

    def aviso(self, fila: int, numero: str | None, motivo: str):
        self.st[f"aviso: {motivo}"] += 1
        if len(self.avisos) < MAX_AVISOS:
            self.avisos.append({"fila": fila, "numero": numero, "motivo": motivo})


def _consecutivo(numero: str | None) -> tuple[str, int] | None:
    """'WX6076' -> ('WX', 6076)."""
    x = re.fullmatch(r"([A-Z]+)(\d+)", (numero or "").upper().replace(" ", ""))
    return (x.group(1), int(x.group(2))) if x else None


class Cronologia:
    """Horas de reporte de los casos que no cruzan la medianoche, por número consecutivo.

    La "Fecha" de la bitácora casi siempre es la del reporte al cliente, pero algunas filas traen la del
    evento. Solo importa cuando el caso cruza la medianoche, y se decide por los casos vecinos.
    """
    VECINOS = 6

    def __init__(self):
        self.ref: dict[tuple[str, int], datetime] = {}

    def agregar(self, numero, dia, h_ev, h_rep):
        k = _consecutivo(numero)
        if k and dia and h_ev and h_rep and h_rep >= h_ev:
            self.ref[k] = datetime.combine(dia, h_rep)

    def vecino(self, numero) -> datetime | None:
        k = _consecutivo(numero)
        if not k:
            return None
        cercanos = sorted(self.ref[(k[0], n)] for n in range(k[1] - self.VECINOS, k[1] + self.VECINOS + 1)
                          if (k[0], n) in self.ref)
        return cercanos[len(cercanos) // 2] if cercanos else None

    def fechar(self, numero, dia, h_ev, h_rep) -> tuple[datetime | None, datetime | None, str | None]:
        """(evento, reporte, caso) en hora local; caso: None | 'fecha_reporte' | 'fecha_evento' | 'dudoso'."""
        if not dia:
            return None, None, None
        ev = datetime.combine(dia, h_ev or time(0))
        if not h_rep:
            return ev, None, None
        rp = datetime.combine(dia, h_rep)
        if rp >= ev:
            return ev, rp, None
        un_dia = timedelta(days=1)
        if rp + un_dia - ev > timedelta(hours=12):      # no es un cruce de medianoche creíble
            return ev, rp + un_dia, "dudoso"
        ref = self.vecino(numero)
        if ref is not None and abs(rp + un_dia - ref) < abs(rp - ref):
            return ev, rp + un_dia, "fecha_evento"      # la Fecha era la del evento
        return ev - un_dia, rp, "fecha_reporte"         # la Fecha era la del reporte (lo habitual)


CRUCES = {"fecha_reporte": "cruce de medianoche: la Fecha es la del reporte (evento el día anterior)",
          "fecha_evento": "cruce de medianoche: la Fecha es la del evento (reporte al día siguiente)"}


def _leer_fila(r, g, m, servicio_defecto, clientes, analistas, kb, res: _Resultado, fila: int, crono: Cronologia):
    """Convierte una fila del Excel en (numero, valores del caso, comentarios) o None si se omite."""
    cli_txt = texto(g(r, "cliente"))
    if not cli_txt:
        res.st["filas vacías (sin cliente)"] += 1
        return None
    numero = texto(g(r, "numero"))
    if not numero:
        res.aviso(fila, None, "fila sin número de reporte (omitida)")
        return None
    numero = numero.upper().replace(" ", "")
    servicio = "NOC" if numero.startswith("WXNOC") else servicio_defecto

    cod, _ = separar_cliente(cli_txt)
    cliente = clientes[cod]
    if servicio == "NOC":
        cliente.servicio_noc = True
    analista_txt = texto(g(r, "analista"))
    analista = analistas.get(clave(analista_txt)) if analista_txt else None

    crit, _aud = criticidad(texto(g(r, "criticidad")))
    tac_txt = texto(g(r, "tactica"))
    tid = tactica_id(tac_txt)
    if tac_txt and not tid:
        res.tacticas_sin_mapear[tac_txt] += 1
    alerta = re.sub(r"\s+", " ", texto(g(r, "alerta")) or "Sin alerta registrada")
    cu = kb.get(clave(alerta)) or kb.get(clave(re.sub(r"^WX-", "", alerta)))

    dia = a_fecha(g(r, "fecha"))
    h_ev, h_rep = a_hora(g(r, "hora_evento")), a_hora(g(r, "hora_reporte"))
    f_ev, f_rep, cruce = crono.fechar(numero, dia, h_ev, h_rep)
    f_ev = f_ev.replace(tzinfo=TZ) if f_ev else None
    f_rep = f_rep.replace(tzinfo=TZ) if f_rep else None
    if cruce in CRUCES:
        res.st[CRUCES[cruce]] += 1
    if not dia:
        res.aviso(fila, numero, "sin fecha")
    if not crit:
        res.aviso(fila, numero, "sin criticidad")
    if f_ev and f_rep and (f_rep - f_ev) > timedelta(hours=12):
        res.aviso(fila, numero, "más de 12 h entre el evento y el reporte (revisar horas)")
    if not cu:
        res.st["sin caso de uso en la base de conocimiento"] += 1

    valores = dict(
        servicio=servicio, cliente_id=cliente.id, analista_id=analista.id if analista else None,
        caso_uso_id=cu.id if cu else None, alerta=alerta, criticidad=crit, tecnica=texto(g(r, "tecnica")),
        tactica_id=tid, tactica_original=tac_txt, resumen_ejecutivo=texto(g(r, "resumen")),
        analisis=texto(g(r, "analisis")), acciones_recomendadas=texto(g(r, "acciones")),
        geolocalizacion=texto(g(r, "geo")), reporting_ip=texto(g(r, "reporting_ip")), log_evento=texto(g(r, "log")),
        fecha_evento=f_ev, fecha_reporte=f_rep, fecha_bitacora=dia, estado=estado(texto(g(r, "estado"))),
        acciones_cliente=texto(g(r, "acciones_cliente")),
    )
    comentarios = []
    for n_col, j in enumerate(m["comentarios"], start=2):
        com = texto(r[j]) if j < len(r) else None
        if com:
            comentarios.append((f"N{n_col} (bitácora)", com))
    return numero, valores, comentarios


def cargar_casos(db: Session, ws, servicio_defecto: str, clientes, analistas, modo: str) -> _Resultado:
    if modo not in MODOS:
        raise ErrorImportacion(f"Modo no válido: {modo}")
    h, enc = buscar_encabezado(ws, "numero de reporte")
    m = mapear(enc)
    faltan = [c for c in ("numero", "cliente", "fecha", "alerta") if c not in m]
    if faltan:
        raise ErrorImportacion(f"Faltan columnas en la hoja {ws.title}: {', '.join(faltan)}")
    g = lambda r, k: (r[m[k]] if k in m and m[k] < len(r) else None)  # noqa: E731

    kb = {clave(c.nombre): c for c in db.scalars(select(CasoUso).where(CasoUso.servicio == "SOC"))}
    res = _Resultado()
    if modo == "reemplazar":
        con_archivos = db.scalar(select(func.count(func.distinct(Adjunto.caso_id))).join(Caso, Caso.id == Adjunto.caso_id)
                                 .where(Caso.origen == "migracion"))
        if con_archivos:
            raise ErrorImportacion(f"No se puede reemplazar: {con_archivos} caso(s) importados tienen evidencias o adjuntos y se "
                                   "perderían. Use el modo 'Nuevos y actualizar importados'")
        anulados = db.scalar(select(func.count()).select_from(Caso).where(Caso.origen == "migracion", Caso.anulado_en.is_not(None)))
        if anulados:
            raise ErrorImportacion(f"No se puede reemplazar: {anulados} caso(s) importados están anulados y volverían a contar. "
                                   "Use el modo 'Nuevos y actualizar importados'")
        borrados = db.execute(delete(Caso).where(Caso.origen == "migracion")).rowcount
        res.st["casos importados borrados antes de cargar"] = borrados
        db.flush()

    # número -> origen de lo que ya está en la base
    origen_de = dict(db.execute(select(Caso.numero, Caso.origen)).all())
    importados = {}
    if modo == "actualizar":
        importados = {c.numero: c for c in db.scalars(
            select(Caso).where(Caso.origen == "migracion").options(selectinload(Caso.seguimientos))).unique()}

    # Primer recorrido: cronología de reportes, para fechar los casos que cruzan la medianoche
    crono = Cronologia()
    for i, r in enumerate(filas(ws)):
        if i > h:
            crono.agregar(texto(g(r, "numero")), a_fecha(g(r, "fecha")), a_hora(g(r, "hora_evento")),
                          a_hora(g(r, "hora_reporte")))

    vistos: set[str] = set()
    lote: list[Caso] = []
    for i, r in enumerate(filas(ws)):
        if i <= h:
            continue
        fila = i + 1  # número de fila tal como se ve en Excel
        leido = _leer_fila(r, g, m, servicio_defecto, clientes, analistas, kb, res, fila, crono)
        if not leido:
            continue
        numero, valores, comentarios = leido
        if numero in vistos:
            res.aviso(fila, numero, "número repetido dentro del archivo (se usa la primera fila)")
            continue
        vistos.add(numero)

        origen = origen_de.get(numero)
        if origen == "app":
            res.aviso(fila, numero, "el número ya lo usa un caso creado en la plataforma (fila omitida)")
            continue
        if origen == "migracion":
            if modo != "actualizar":
                res.st["ya existían (sin cambios)"] += 1
                continue
            caso = importados[numero]
            cambios = [k for k in CAMPOS_CASO if getattr(caso, k) != valores[k]]
            for k in cambios:
                setattr(caso, k, valores[k])
            ya = {s.comentario for s in caso.seguimientos}
            nuevos_com = [(a, c) for a, c in comentarios if c not in ya]
            for autor, com in nuevos_com:
                caso.seguimientos.append(Seguimiento(autor_nombre=autor, tipo="comentario", comentario=com))
            res.st["actualizados" if cambios or nuevos_com else "ya existían (sin cambios)"] += 1
            continue

        caso = Caso(numero=numero, origen="migracion", **valores)
        caso.seguimientos = [Seguimiento(autor_nombre=a, tipo="comentario", comentario=c) for a, c in comentarios]
        lote.append(caso)
        res.st[f"insertados {valores['servicio']}"] += 1
        if len(lote) >= 500:
            db.add_all(lote)
            db.flush()
            lote.clear()
    db.add_all(lote)
    db.flush()
    return res


def ajustar_consecutivos(db: Session) -> dict[str, str]:
    siguiente = {}
    for servicio, prefijo in (("SOC", "WX"), ("NOC", "WXNOC")):
        nums = db.scalars(select(Caso.numero).where(Caso.servicio == servicio))
        maximo = max((int(n[len(prefijo):]) for n in nums if n[len(prefijo):].isdigit()), default=0)
        c = db.get(Consecutivo, servicio, with_for_update=True)
        c.ultimo = max(c.ultimo, maximo)
        siguiente[servicio] = f"{prefijo}{c.ultimo + 1}"
    return siguiente


# ---------------------------------------------------------------- API pública
def describir_archivo(ruta: str) -> list[dict]:
    """Hojas del archivo, indicando cuáles tienen estructura de bitácora y cuántas filas con cliente."""
    wb = load_workbook(ruta, read_only=True, data_only=True)
    try:
        hojas = []
        for nombre in wb.sheetnames:
            ws = hoja(wb, nombre)
            try:
                h, enc = buscar_encabezado(ws, "numero de reporte")
            except ErrorImportacion:
                hojas.append({"nombre": nombre, "es_bitacora": False, "filas": 0, "servicio_sugerido": None})
                continue
            m = mapear(enc)
            if not all(k in m for k in ("cliente", "fecha", "alerta")):  # p. ej. la hoja "Plantilla"
                hojas.append({"nombre": nombre, "es_bitacora": False, "filas": 0, "servicio_sugerido": None})
                continue
            col = m["cliente"]
            n = sum(1 for i, r in enumerate(filas(ws))
                    if i > h and col is not None and col < len(r) and texto(r[col]))
            hojas.append({"nombre": nombre, "es_bitacora": True, "filas": n,
                          "servicio_sugerido": "NOC" if "noc" in nombre.lower() else "SOC"})
        return hojas
    finally:
        wb.close()


def importar(db: Session, ruta: str, hoja_casos: str = "BITACORA", servicio: str | None = None,
             modo: str = "solo_nuevos", cargar_catalogos: bool = True) -> dict:
    """Importa la hoja de casos del archivo. No hace commit: el llamador decide (simulación = rollback)."""
    servicio = servicio or ("NOC" if "noc" in hoja_casos.lower() else "SOC")
    wb = load_workbook(ruta, read_only=True, data_only=True)
    try:
        if hoja_casos not in wb.sheetnames:
            raise ErrorImportacion(f"La hoja '{hoja_casos}' no existe. Hojas: {', '.join(wb.sheetnames)}")
        ws = hoja(wb, hoja_casos)

        # Primer recorrido: clientes y analistas presentes en los casos
        h, enc = buscar_encabezado(ws, "numero de reporte")
        m = mapear(enc)
        if "cliente" not in m:
            raise ErrorImportacion("La hoja no tiene la columna Cliente")
        cli, ana = set(), set()
        for i, r in enumerate(filas(ws)):
            if i > h and m["cliente"] < len(r) and texto(r[m["cliente"]]):
                cli.add(texto(r[m["cliente"]]))
                if "analista" in m and m["analista"] < len(r) and texto(r[m["analista"]]):
                    ana.add(" ".join(texto(r[m["analista"]]).split()))

        clientes, clientes_nuevos = cargar_clientes(db, wb if cargar_catalogos else None, cli)
        analistas, analistas_nuevos = cargar_analistas(db, ana)
        kb_forti = kb_secu = 0
        if cargar_catalogos:
            kb_forti, kb_secu = cargar_base_conocimiento(db, wb)
        res = cargar_casos(db, ws, servicio, clientes, analistas, modo)
        siguiente = ajustar_consecutivos(db)
    finally:
        wb.close()

    st = res.st
    resumen = {
        "insertados": st["insertados SOC"] + st["insertados NOC"],
        "actualizados": st["actualizados"],
        "sin_cambios": st["ya existían (sin cambios)"],
        "omitidos": sum(v for k, v in st.items() if k.startswith("aviso:") and "omitid" in k),
        "filas_vacias": st["filas vacías (sin cliente)"],
        "avisos": sum(v for k, v in st.items() if k.startswith("aviso:")),
    }
    detalle = [{"concepto": k, "total": v} for k, v in st.most_common()]
    detalle += [{"concepto": f"táctica no reconocida: {k}", "total": v}
                for k, v in res.tacticas_sin_mapear.most_common()]
    return {
        "hoja": hoja_casos, "servicio": servicio, "modo": modo,
        "resumen": resumen, "detalle": detalle, "avisos": res.avisos,
        "clientes_nuevos": clientes_nuevos, "analistas_nuevos": analistas_nuevos,
        "base_conocimiento_nuevos": {"con_plantilla": kb_forti, "reglas_fortisiem": kb_secu},
        "siguiente_numero": siguiente,
        "total_casos": db.scalar(select(func.count()).select_from(Caso)),
    }
