"""Informe ejecutivo en Word sobre la plantilla corporativa
"Plantilla Informes Técnicos y Ejecutivo 2026 - SOC para cliente".

Se conservan la portada, el encabezado (código, versión, página, TLP), el pie y los estilos;
se reemplazan los textos de la portada y se escribe el contenido con los estilos de la plantilla.
La tabla de contenido y los índices de tablas y gráficas se llenan con los números de página
reales (se calculan convirtiendo una vez a PDF) y quedan marcados para que Word los actualice.
"""
import copy
import io
import re
from pathlib import Path

import pymupdf
from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from . import graficos_png as gp
from .contenido import CRITS
from .convertidor import ErrorConversion, word_a_pdf

PLANTILLA = Path(__file__).parent / "recursos" / "plantilla_informe.docx"
ROJO = RGBColor(0xE1, 0x2C, 0x26)
GRIS = RGBColor(0x5D, 0x6B, 0x7C)
ANCHO = 6.5  # pulgadas útiles (carta con márgenes de 1")
ESTADOS = {"SIN_RETRO": "Sin retroalimentación", "CON_RETRO": "Con retroalimentación", "CERRADO": "Cerrado"}


def _el(tag, **attrs):
    e = OxmlElement(tag)
    for k, v in attrs.items():
        e.set(qn(k), str(v))
    return e


def _run_campo(tipo, **attrs):
    r = OxmlElement("w:r")
    r.append(_el("w:fldChar", **{"w:fldCharType": tipo, **attrs}))
    return r


def _run_instr(texto):
    r = OxmlElement("w:r")
    it = _el("w:instrText", **{"xml:space": "preserve"})
    it.text = texto
    r.append(it)
    return r


def _run_texto(texto):
    r = OxmlElement("w:r")
    if texto == "\t":
        r.append(OxmlElement("w:tab"))
    else:
        t = _el("w:t", **{"xml:space": "preserve"})
        t.text = texto
        r.append(t)
    return r


def _clave(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


class Escritor:
    def __init__(self, paginas: dict | None = None):
        self.doc = Document(PLANTILLA)
        self.body = self.doc.element.body
        self.estilos = {s.style_id: s for s in self.doc.styles}
        self.paginas = paginas or {}
        self.entradas = []            # (tipo, nivel, numero, texto) en orden del documento
        self.num = [0, 0, 0]
        self.n = {"Tabla": 0, "Gráfica": 0}
        self._preparar()

    # ------------------------------------------------------------------ plantilla
    def _preparar(self):
        hijos = list(self.body)
        # 1. Quitar el contenido de muestra ("Titulo", "Título nivel 1"…) que sigue a los índices
        inicio = next(i for i, e in enumerate(hijos)
                      if e.tag == qn("w:p") and e.find(".//" + qn("w:pStyle")) is not None
                      and e.find(".//" + qn("w:pStyle")).get(qn("w:val")) == "TtuloDegradado"
                      and "Titulo" in "".join(t.text or "" for t in e.iter(qn("w:t"))))
        for e in hijos[inicio:]:
            if e.tag != qn("w:sectPr"):
                self.body.remove(e)
        # 2. Estilo de títulos de índice sin numeración (LibreOffice ignora numId=0 en "TOC Heading")
        if "TituloIndice" not in self.estilos:
            st = self.doc.styles.add_style("Título índice", WD_STYLE_TYPE.PARAGRAPH)
            st.element.set(qn("w:styleId"), "TituloIndice")
            st.base_style = self.estilos["Normal"]
            st.font.name = "Montserrat SemiBold"
            st.font.size = Pt(14)
            st.font.color.rgb = ROJO
            st.paragraph_format.space_before = Pt(12)
            st.paragraph_format.space_after = Pt(12)
            st.paragraph_format.keep_with_next = True
            self.estilos["TituloIndice"] = st
        # 3. Sacar la tabla de contenido del control "Table of Contents": LibreOffice toma su primer
        #    párrafo como título del índice y lo numera como un título de nivel 1
        for sdt in list(self.body.iter(qn("w:sdt"))):
            contenido = sdt.find(qn("w:sdtContent"))
            if contenido is not None and sdt.getparent() is self.body:
                for hijo in list(contenido):
                    sdt.addprevious(hijo)
                self.body.remove(sdt)
        # 4. Ubicar tabla de contenido e índices
        self.p_toc = self.p_tablas = self.p_graficas = None
        quitar = []
        en_toc = False
        for p in list(self.body.iter(qn("w:p"))):
            texto = "".join(t.text or "" for t in p.iter(qn("w:t"))).strip()
            estilo = p.find(".//" + qn("w:pStyle"))
            estilo = estilo.get(qn("w:val")) if estilo is not None else ""
            if estilo == "TtuloTDC":
                self._estilo_xml(p, "TituloIndice")
                self.p_toc = p
                en_toc = True
                continue
            if texto.startswith("Índice de tablas"):
                self.p_tablas, en_toc = p, False
            elif texto.startswith("Índice de gráficas"):
                self.p_graficas = p
            elif texto.startswith("Índice de ilustraciones"):
                quitar.append(p)
            elif en_toc:
                quitar.append(p)   # entradas de ejemplo del TOC de la plantilla
        for p in quitar:
            p.getparent().remove(p)
        for p in (self.p_tablas, self.p_graficas):
            if p is not None:
                self._estilo_xml(p, "TituloIndice")
        # Word actualiza los campos al abrir el documento
        ajustes = self.doc.settings.element
        if ajustes.find(qn("w:updateFields")) is None:
            campo = _el("w:updateFields", **{"w:val": "true"})
            # posición exigida por el esquema: antes de hdrShapeDefaults/footnotePr/endnotePr/compat…
            siguiente = next((e for e in ajustes if e.tag in {qn(f"w:{x}") for x in (
                "hdrShapeDefaults", "footnotePr", "endnotePr", "compat", "docVars", "rsids")}
                or e.tag.endswith("}mathPr")), None)
            if siguiente is not None:
                siguiente.addprevious(campo)
            else:
                ajustes.append(campo)

    @staticmethod
    def _estilo_xml(p, estilo_id):
        ppr = p.find(qn("w:pPr"))
        if ppr is None:
            ppr = OxmlElement("w:pPr")
            p.insert(0, ppr)
        for tag in ("w:pStyle", "w:numPr", "w:ind"):
            for x in ppr.findall(qn(tag)):
                ppr.remove(x)
        ppr.insert(0, _el("w:pStyle", **{"w:val": estilo_id}))

    def portada(self, titulo: str, subtitulo: str, fecha: str):
        """Reemplaza textos de la portada aunque Word los haya partido en varios fragmentos (runs)."""
        reemplazos = {"Revisión de actividad de cuenta": subtitulo, "1 de agosto de 2026": fecha,
                      "INFORME DE MONITOREO": titulo}
        for p in self.body.iter(qn("w:p")):
            ts = [t for t in p.iter(qn("w:t")) if t.getparent().getparent() is p]
            texto = "".join(t.text or "" for t in ts).strip()
            if texto not in reemplazos or not ts:
                continue
            ts[0].text = reemplazos[texto]
            for t in ts[1:]:
                t.text = ""
            if texto == "INFORME DE MONITOREO":
                # color de respaldo para visores sin degradado de texto (LibreOffice/PDF)
                rpr = ts[0].getparent().find(qn("w:rPr"))
                if rpr is not None and rpr.find(qn("w:color")) is None:
                    rpr.insert(0, _el("w:color", **{"w:val": "E12C26"}))

    # ------------------------------------------------------------------ bloques
    def p(self, texto="", estilo="Normal", alinear=None, tam=None, negrita=None, color=None, despues=None, cursiva=None):
        par = self.doc.add_paragraph(style=self.estilos.get(estilo))
        if texto:
            r = par.add_run(texto)
            if tam:
                r.font.size = Pt(tam)
            if negrita is not None:
                r.bold = negrita
            if cursiva is not None:
                r.italic = cursiva
            if color:
                r.font.color.rgb = color
        if alinear is not None:
            par.alignment = alinear
        if despues is not None:
            par.paragraph_format.space_after = Pt(despues)
        return par

    def parrafos(self, texto: str):
        for bloque in (texto or "").split("\n\n"):
            if bloque.strip():
                self.p(" ".join(bloque.split("\n")).strip(), alinear=WD_ALIGN_PARAGRAPH.JUSTIFY, despues=6)

    def nota(self, texto: str):
        if texto:
            self.p(texto, tam=9, color=GRIS, cursiva=True, alinear=WD_ALIGN_PARAGRAPH.JUSTIFY, despues=6)

    def titulo(self, nivel: int, texto: str):
        self.num[nivel - 1] += 1
        for i in range(nivel, 3):
            self.num[i] = 0
        numero = ".".join(str(x) for x in self.num[:nivel])
        self.p(texto, estilo=f"Ttulo{nivel}")
        self.entradas.append(("titulo", nivel, numero, texto))

    def subtitulo(self, texto: str):
        self.p(texto, estilo="SubttuloWexler", despues=4)

    def vinetas(self, items: list[str]):
        for item in items:
            par = self.p(item, estilo="Prrafodelista", alinear=WD_ALIGN_PARAGRAPH.JUSTIFY, despues=4)
            ppr = par._p.get_or_add_pPr()
            num = OxmlElement("w:numPr")
            num.append(_el("w:ilvl", **{"w:val": 0}))
            num.append(_el("w:numId", **{"w:val": 1}))   # viñeta de la plantilla
            estilo = ppr.find(qn("w:pStyle"))             # el esquema exige numPr justo después del estilo
            if estilo is not None:
                estilo.addnext(num)
            else:
                ppr.insert(0, num)

    def leyenda(self, tipo: str, texto: str):
        """Leyenda numerada (campo SEQ) para los índices de tablas y gráficas."""
        self.n[tipo] += 1
        par = self.p(alinear=WD_ALIGN_PARAGRAPH.CENTER, despues=10)
        par.paragraph_format.space_before = Pt(3)
        for r in (_run_texto(f"{tipo} "), _run_campo("begin"), _run_instr(f" SEQ {tipo} \\* ARABIC "),
                  _run_campo("separate"), _run_texto(str(self.n[tipo])), _run_campo("end"), _run_texto(f". {texto}")):
            rpr = OxmlElement("w:rPr")
            rpr.append(_el("w:i"))
            rpr.append(_el("w:color", **{"w:val": "5D6B7C"}))
            rpr.append(_el("w:sz", **{"w:val": 17}))
            r.insert(0, rpr)
            par._p.append(r)
        self.entradas.append((tipo, 1, str(self.n[tipo]), f"{tipo} {self.n[tipo]}. {texto}"))

    def imagen(self, png: bytes, ancho: float, leyenda: str):
        par = self.p(alinear=WD_ALIGN_PARAGRAPH.CENTER, despues=0)
        par.paragraph_format.keep_with_next = True
        par.add_run().add_picture(io.BytesIO(png), width=Inches(ancho))
        self.leyenda("Gráfica", leyenda)

    def tabla(self, filas: list[list], anchos: list[float], leyenda: str | None = None, numericas=(), negrita_ultima=False):
        t = self.doc.add_table(rows=len(filas), cols=len(filas[0]))
        t.style = self.estilos.get("Tablaconcuadrcula2-nfasis5")
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        for i, fila in enumerate(filas):
            for j, v in enumerate(fila):
                c = t.cell(i, j)
                c.width = Inches(anchos[j])
                par = c.paragraphs[0]
                par.text = "" if v is None else str(v)
                par.paragraph_format.space_after = Pt(0)
                par.alignment = WD_ALIGN_PARAGRAPH.RIGHT if (j in numericas and i > 0) else \
                    WD_ALIGN_PARAGRAPH.CENTER if i == 0 else WD_ALIGN_PARAGRAPH.LEFT
                for r in par.runs:
                    r.font.size = Pt(9)
                    if negrita_ultima and i == len(filas) - 1:
                        r.bold = True
            if i == 0:  # repetir encabezado si la tabla pasa de página
                trpr = t.rows[0]._tr.get_or_add_trPr()
                trpr.append(_el("w:tblHeader"))
        if leyenda:
            self.leyenda("Tabla", leyenda)
        else:
            self.p(despues=4)
        return t

    def salto(self):
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # ------------------------------------------------------------------ índices
    def _campo_indice(self, despues_de, instr: str, entradas: list[tuple[int, str, str]], estilo_por_nivel):
        """Inserta un campo TOC con sus entradas ya calculadas a continuación del párrafo dado."""
        ancla = despues_de
        pars = []
        if not entradas:
            par = self.doc.add_paragraph()._p
            par.append(_run_campo("begin", **{"w:dirty": "true"}))
            par.append(_run_instr(instr))
            par.append(_run_campo("separate"))
            par.append(_run_texto("No hay entradas en este informe."))
            par.append(_run_campo("end"))
            pars.append(par)
        for k, (nivel, texto, pagina) in enumerate(entradas):
            par = self.doc.add_paragraph(style=self.estilos.get(estilo_por_nivel(nivel)))._p
            ppr = par.get_or_add_pPr()
            tabs = OxmlElement("w:tabs")
            tabs.append(_el("w:tab", **{"w:val": "right", "w:leader": "dot", "w:pos": 9350}))
            ppr.append(tabs)
            if k == 0:
                par.append(_run_campo("begin", **{"w:dirty": "true"}))
                par.append(_run_instr(instr))
                par.append(_run_campo("separate"))
            par.append(_run_texto(texto))
            par.append(_run_texto("\t"))
            par.append(_run_texto(str(pagina or "")))
            if k == len(entradas) - 1:
                par.append(_run_campo("end"))
            pars.append(par)
        for par in pars:  # mover desde el final del documento a su lugar
            ancla.addnext(par)
            ancla = par

    def indices(self):
        pag = lambda tipo, texto: self.paginas.get((tipo, _clave(texto)))  # noqa: E731
        toc = [(nivel, f"{numero}  {texto}", pag("titulo", texto)) for tipo, nivel, numero, texto in self.entradas
               if tipo == "titulo" and nivel <= 3]
        if self.p_toc is not None:
            self._campo_indice(self.p_toc, ' TOC \\o "1-3" \\h \\z \\u ', toc, lambda n: f"TDC{min(n, 3)}")
        for p, tipo in ((self.p_tablas, "Tabla"), (self.p_graficas, "Gráfica")):
            if p is not None:
                ent = [(1, texto, pag(tipo, texto)) for t, _, _, texto in self.entradas if t == tipo]
                self._campo_indice(p, f' TOC \\h \\z \\c "{tipo}" ', ent, lambda n: "Normal")

    def guardar(self) -> bytes:
        self.indices()
        b = io.BytesIO()
        self.doc.save(b)
        return b.getvalue()


# ---------------------------------------------------------------------- contenido
def _escribir(ctx: dict, paginas: dict | None) -> tuple[bytes, list]:
    n, t = ctx["n"], ctx["t"]
    w = Escritor(paginas)
    cl = ctx["cliente"]
    w.portada("INFORME DE MONITOREO", f"Informe mensual {ctx['servicios_txt']} · {cl.codigo} - {cl.nombre}", ctx["periodo"])

    w.p(f"Informe mensual de monitoreo {ctx['servicios_txt']}", estilo="TtuloDegradado")
    w.subtitulo(f"{ctx['nombre_cliente']} · {ctx['periodo']}")
    if ctx["informe"].estado == "BORRADOR":
        w.nota("Documento en borrador.")

    # 1. Resumen ejecutivo
    w.titulo(1, "Resumen ejecutivo")
    w.titulo(2, "Objetivo")
    w.parrafos(t["objetivo"])
    w.titulo(2, "Alcance")
    w.parrafos(t["alcance"])
    w.titulo(2, "Indicadores del periodo")
    k = ctx["kpis"]
    tk = w.tabla([[e for e, _, _ in k], [v for _, v, _ in k], [s for _, _, s in k]], [ANCHO / len(k)] * len(k),
                 "Indicadores del periodo")
    for j in range(len(k)):
        for fila, (tam, color, negrita) in ((1, (16, ROJO, True)), (2, (8, GRIS, False))):
            par = tk.cell(fila, j).paragraphs[0]
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in par.runs:
                r.font.size, r.font.color.rgb, r.bold = Pt(tam), color, negrita
    if t["conclusiones"]:
        w.titulo(2, "Resumen del periodo")
        w.parrafos(t["conclusiones"])

    for s, sv in ctx["serv"].items():
        d = sv["d"]
        w.titulo(1, f"Gestión de eventos de {s} por criticidad")
        w.parrafos(t[f"resumen_{s}"])
        w.imagen(gp.columnas(ctx["cortas"], [(c, gp.COLOR_CRIT[c], [p["criticidad"][c] for p in d["periodos"]]) for c in CRITS]),
                 5.6, f"Eventos de {s} por criticidad en los tres últimos periodos")
        filas = [["Criticidad"] + ctx["cortas"]] + [[c] + [n(p["criticidad"][c]) for p in d["periodos"]] for c in reversed(CRITS)] \
            + [["Total"] + [n(p["total"]) for p in d["periodos"]]]
        w.tabla(filas, [2.0] + [1.5] * 3, f"Eventos de {s} por criticidad", numericas=(1, 2, 3), negrita_ultima=True)
        w.parrafos(t[f"retro_{s}"])
        if ctx["tiempos_word"] and t.get(f"tiempos_{s}"):
            w.parrafos(t[f"tiempos_{s}"])

        w.titulo(2, "Alertas del periodo")
        w.parrafos(t[f"alertas_{s}"])
        if d["top_alertas"]:
            w.imagen(gp.barras_h([(x["alerta"], x["total"]) for x in d["top_alertas"]]), ANCHO,
                     f"Top {len(d['top_alertas'])} de alertas de {s} reportadas en el periodo")
        if d["destacados"]:
            filas = [["Número", "Fecha", "Alerta", "Criticidad", "Estado"]] + \
                    [[e["numero"], e["fecha"], e["alerta"], e["criticidad"], ESTADOS.get(e["estado"], e["estado"])]
                     for e in d["destacados"]]
            w.tabla(filas, [0.8, 1.15, 2.55, 0.8, 1.2], f"Eventos de {s} de criticidad alta o crítica")

        if s == "SOC" and d["tacticas"]:
            w.titulo(2, "Categorías MITRE ATT&CK")
            w.parrafos(t["categorias_SOC"])
            filas = [["Táctica"] + ctx["cortas"]] + [[x["tactica"]] + [n(v) if v else "–" for v in x["valores"]] for x in d["tacticas"][:14]]
            w.tabla(filas, [2.6] + [1.3] * 3, "Eventos por táctica MITRE ATT&CK", numericas=(1, 2, 3))

    if "estado" in ctx["num"]:
        w.titulo(1, "Estado del servicio")
        f = ctx["fuentes"]
        if f or ctx["total_fuentes"]:
            w.titulo(2, "Fuentes integradas")
            w.parrafos(t["fuentes"])
            if f and f.get("por_tipo"):
                w.imagen(gp.barras_h([(x["tipo"], x["total"]) for x in f["por_tipo"][:10]], ancho_pulg=5.5), 5.0,
                         "Fuentes integradas por proveedor")
        if ctx["eps_series"] or ctx["informe"].eps_promedio:
            w.titulo(2, "Promedio de EPS")
            w.parrafos(t["eps"])
            if ctx["eps_series"]:
                w.imagen(gp.columnas([p for p, _ in ctx["eps_series"]], [("EPS", gp.ROJO, [v for _, v in ctx["eps_series"]])],
                                     ancho_pulg=5.0, alto_pulg=2.4), 4.6, "Promedio de eventos por segundo (EPS) por periodo")

    if "interes" in ctx["num"]:
        w.titulo(1, "Eventos de interés")
        for clave_, titulo, sentido in (("paises_entrantes", "Países diferentes a Colombia entrantes permitidos", "entrantes"),
                                        ("paises_salientes", "Países diferentes a Colombia salientes permitidos", "salientes")):
            datos = ctx[clave_]
            if datos:
                w.titulo(2, titulo)
                w.parrafos(t[clave_])
                w.imagen(gp.barras_h([(x["pais"], x["total"]) for x in datos]), ANCHO,
                         f"Top {len(datos)} de países con conexiones {sentido} permitidas")
                w.nota(f"La información complementaria se encuentra en el anexo de países {sentido}.")
        if ctx["puertos_ent"] or ctx["puertos_sal"]:
            w.titulo(2, "Puertos no comunes con conexión aceptada")
            w.parrafos(t["puertos"])
            for titulo, datos in (("entrantes", ctx["puertos_ent"]), ("salientes", ctx["puertos_sal"])):
                if datos:
                    filas = [["Puerto", "Servicio", "Eventos"]] + [[x["puerto"], x["servicio"], n(x["total"])] for x in datos]
                    w.tabla(filas, [1.2, 3.3, 2.0], f"Top {len(datos)} de puertos no comunes {titulo}", numericas=(2,))
            w.nota("La información complementaria se encuentra en el anexo de puertos.")
        if ctx["ips"]:
            w.titulo(2, "Top de ataques detectados por IPS bloqueados")
            w.parrafos(t["ips"])
            w.imagen(gp.barras_h([(x["ataque"], x["total"]) for x in ctx["ips"]]), ANCHO, "Top de ataques bloqueados por el IPS")
            w.nota("La información complementaria se encuentra en el anexo de tipos de ataques IPS.")

    if ctx["boletines"]:
        w.titulo(1, "Boletines de inteligencia de amenazas")
        for b in ctx["boletines"]:
            w.titulo(2, b["nombre"])
            meta = " · ".join(x for x in (b.get("tipo"), b.get("fecha")) if x)
            if meta:
                w.nota(meta)
            w.parrafos(b.get("resumen") or "")

    w.titulo(1, "Recomendaciones y conclusiones")
    w.titulo(2, "Recomendaciones de seguridad")
    w.vinetas(ctx["recomendaciones"])
    if t["conclusiones"]:
        w.titulo(2, "Conclusiones")
        w.parrafos(t["conclusiones"])
    w.nota("La información complementaria de cada punto se envía en los anexos.")
    return w.guardar(), w.entradas


def _paginas_desde_pdf(pdf: bytes, entradas: list) -> dict:
    """Ubica cada título y leyenda en el PDF (después de los índices) para numerar la tabla de contenido."""
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    textos = [_clave(p.get_text()) for p in doc]
    inicio = 0
    for i, tx in enumerate(textos):
        if "Índice de gráficas" in tx or "Índice de tablas" in tx or "Tabla de contenido" in tx:
            inicio = i + 1
    paginas, actual = {}, inicio
    for tipo, _nivel, _numero, texto in entradas:
        buscar = _clave(texto)
        for i in range(actual, len(textos)):
            if buscar in textos[i]:
                paginas[(tipo, buscar)] = i + 1
                actual = i
                break
    return paginas


def generar(ctx: dict) -> tuple[bytes, bytes | None]:
    """Devuelve (docx, pdf). El PDF puede ser None si el convertidor no está disponible."""
    docx, entradas = _escribir(ctx, None)
    try:
        pdf = word_a_pdf(docx)
    except ErrorConversion:
        return docx, None
    paginas = _paginas_desde_pdf(pdf, entradas)
    docx, _ = _escribir(ctx, paginas)
    return docx, word_a_pdf(docx)
