import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, token } from "../api";
import { Campo, MsgError } from "../components/Ui";
import { fechaHora, num } from "../util";

const MODOS = {
  solo_nuevos: {
    titulo: "Solo casos nuevos",
    texto: "Agrega los números de reporte que aún no están en la plataforma. No modifica nada de lo ya cargado.",
  },
  actualizar: {
    titulo: "Nuevos y actualizar importados",
    texto: "Además, actualiza los casos que vinieron del Excel (estado, retroalimentación, acciones del cliente, comentarios N2…). Úselo mientras la bitácora de producción siga en uso.",
  },
  reemplazar: {
    titulo: "Reemplazar todo lo importado",
    texto: "Borra todos los casos que vinieron de Excel y los vuelve a cargar desde este archivo. Los casos creados en la plataforma no se tocan.",
  },
};

async function subirArchivo(archivo) {
  const fd = new FormData();
  fd.append("archivo", archivo);
  const r = await fetch("/api/importaciones/archivo", { method: "POST", headers: { Authorization: `Bearer ${token.get()}` }, body: fd });
  const cuerpo = await r.json().catch(() => null);
  if (!r.ok) throw new Error(cuerpo?.detail || `Error ${r.status} al cargar el archivo`);
  return cuerpo;
}

function Resultado({ r }) {
  const [verTodo, setVerTodo] = useState(false);
  const s = r.resumen;
  const avisos = verTodo ? r.avisos : r.avisos.slice(0, 15);
  return (
    <>
      <div className="kpis">
        <div className="kpi"><div className="etiqueta">Casos nuevos</div><div className="valor">{num(s.insertados)}</div></div>
        <div className="kpi"><div className="etiqueta">Actualizados</div><div className="valor">{num(s.actualizados)}</div></div>
        <div className="kpi"><div className="etiqueta">Sin cambios</div><div className="valor">{num(s.sin_cambios)}</div></div>
        <div className="kpi"><div className="etiqueta">Filas omitidas</div><div className="valor">{num(s.omitidos)}</div>
          <div className="sub">{num(s.filas_vacias)} filas vacías ignoradas</div></div>
      </div>
      <div className="grid g2">
        <div className="panel">
          <h2>Detalle</h2>
          <table className="tabla">
            <tbody>
              {r.detalle.map((d) => <tr key={d.concepto}><td>{d.concepto}</td><td className="num" style={{ textAlign: "right" }}>{num(d.total)}</td></tr>)}
            </tbody>
          </table>
        </div>
        <div className="panel">
          <h2>Catálogos</h2>
          <p><b>Siguiente número:</b> {r.siguiente_numero.SOC} (SOC) · {r.siguiente_numero.NOC} (NOC)</p>
          <p><b>Casos en la plataforma después de importar:</b> {num(r.total_casos)}</p>
          <p><b>Base de conocimiento nueva:</b> {num(r.base_conocimiento_nuevos.con_plantilla)} casos de uso con plantilla,{" "}
            {num(r.base_conocimiento_nuevos.reglas_fortisiem)} reglas FortiSIEM</p>
          <p><b>Clientes nuevos:</b> {r.clientes_nuevos.length ? r.clientes_nuevos.join(", ") : "ninguno"}</p>
          <p><b>Analistas nuevos:</b> {r.analistas_nuevos.length ? r.analistas_nuevos.join(", ") : "ninguno"}
            {r.analistas_nuevos.length > 0 && <span className="tenue"> (quedan sin contraseña; asígnela en Usuarios)</span>}</p>
        </div>
      </div>
      {r.avisos.length > 0 && (
        <div className="panel">
          <h2>Avisos para revisar ({num(s.avisos)})</h2>
          <p className="tenue">El número de fila corresponde al Excel. Corrija en el archivo si es necesario y vuelva a importar.</p>
          <div className="tabla-scroll">
            <table className="tabla">
              <thead><tr><th>Fila</th><th>Número</th><th>Motivo</th></tr></thead>
              <tbody>
                {avisos.map((a, i) => (
                  <tr key={i}><td className="num">{a.fila}</td><td className="num">{a.numero || "—"}</td><td>{a.motivo}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          {r.avisos.length > 15 && (
            <button className="btn chico" style={{ marginTop: 10 }} onClick={() => setVerTodo(!verTodo)}>
              {verTodo ? "Ver menos" : `Ver los ${r.avisos.length} avisos`}
            </button>
          )}
        </div>
      )}
    </>
  );
}

export default function Importar() {
  const [archivo, setArchivo] = useState(null);       // respuesta de /archivo
  const [hoja, setHoja] = useState("");
  const [servicio, setServicio] = useState("SOC");
  const [modo, setModo] = useState("solo_nuevos");
  const [catalogos, setCatalogos] = useState(true);
  const [simulacion, setSimulacion] = useState(null);  // resultado de la simulación vigente
  const [final, setFinal] = useState(null);
  const [historial, setHistorial] = useState([]);
  const [ocupado, setOcupado] = useState(null);
  const [error, setError] = useState(null);
  const input = useRef(null);

  const cargarHistorial = () => api("/importaciones").then(setHistorial).catch(() => {});
  useEffect(() => { cargarHistorial(); }, []);

  // Cualquier cambio de opciones invalida la simulación anterior
  useEffect(() => { setSimulacion(null); setFinal(null); }, [archivo, hoja, servicio, modo, catalogos]);

  const elegirArchivo = async (f) => {
    if (!f) return;
    setError(null); setArchivo(null); setOcupado("Leyendo el archivo…");
    try {
      const r = await subirArchivo(f);
      setArchivo(r);
      const h = r.hojas.find((x) => x.es_bitacora && x.filas > 0) || r.hojas.find((x) => x.es_bitacora);
      setHoja(h?.nombre || "");
      setServicio(h?.servicio_sugerido || "SOC");
    } catch (e) { setError(e); }
    setOcupado(null);
    if (input.current) input.current.value = "";
  };

  const ejecutar = async (simular) => {
    if (!simular && modo === "reemplazar" &&
        !window.confirm("Se borrarán todos los casos importados desde Excel y se cargarán de nuevo desde este archivo. ¿Continuar?")) return;
    setError(null);
    setOcupado(simular ? "Simulando importación…" : "Importando…");
    try {
      const r = await api("/importaciones", { metodo: "POST", datos: {
        archivo_id: archivo.archivo_id, hoja, modo, servicio, simular, cargar_catalogos: catalogos } });
      if (simular) setSimulacion(r); else { setFinal(r); setSimulacion(null); }
      cargarHistorial();
    } catch (e) { setError(e); }
    setOcupado(null);
  };

  const hojaSel = archivo?.hojas.find((h) => h.nombre === hoja);

  return (
    <>
      <div className="cabecera">
        <div>
          <h1>Importar bitácora</h1>
          <p>Carga casos desde la bitácora Excel de producción. Siempre se simula primero; nada se guarda hasta que confirme.</p>
        </div>
      </div>
      <MsgError e={error} />
      {final && (
        <div className="alerta ok">
          Importación completada: {num(final.resumen.insertados)} casos nuevos y {num(final.resumen.actualizados)} actualizados.{" "}
          <Link to="/casos">Ver casos</Link>
        </div>
      )}

      <div className="panel">
        <h2>1. Archivo</h2>
        <div className="acciones">
          <input ref={input} type="file" accept=".xlsx,.xlsm" style={{ display: "none" }} onChange={(e) => elegirArchivo(e.target.files[0])} />
          <button className="btn primario" disabled={!!ocupado} onClick={() => input.current.click()}>
            {archivo ? "Cambiar archivo" : "Seleccionar archivo Excel"}
          </button>
          {archivo && <span><b>{archivo.nombre}</b> <span className="tenue">· {(archivo.tamano / 1048576).toFixed(1)} MB</span></span>}
          {ocupado === "Leyendo el archivo…" && <span className="tenue">{ocupado}</span>}
        </div>
      </div>

      {archivo && (
        <div className="panel">
          <h2>2. Opciones</h2>
          <div className="grid g3">
            <Campo etiqueta="Hoja con los casos">
              <select value={hoja} onChange={(e) => { setHoja(e.target.value); const h = archivo.hojas.find((x) => x.nombre === e.target.value); if (h?.servicio_sugerido) setServicio(h.servicio_sugerido); }}>
                {archivo.hojas.map((h) => (
                  <option key={h.nombre} value={h.nombre} disabled={!h.es_bitacora}>
                    {h.nombre}{h.es_bitacora ? ` (${num(h.filas)} casos)` : " (no es bitácora)"}
                  </option>
                ))}
              </select>
            </Campo>
            <Campo etiqueta="Servicio" ayuda="los números WXNOC siempre se toman como NOC">
              <select value={servicio} onChange={(e) => setServicio(e.target.value)}><option>SOC</option><option>NOC</option></select>
            </Campo>
            <label className="check" style={{ alignSelf: "end", paddingBottom: 8 }}>
              <input type="checkbox" checked={catalogos} onChange={(e) => setCatalogos(e.target.checked)} />
              Cargar también clientes y base de conocimiento nuevos del archivo
            </label>
          </div>
          <h3 style={{ marginTop: 18 }}>Modo</h3>
          <div className="grid g3">
            {Object.entries(MODOS).map(([k, m]) => (
              <label key={k} className="panel" style={{ margin: 0, cursor: "pointer", borderColor: modo === k ? "var(--acento)" : undefined, boxShadow: modo === k ? "0 0 0 3px var(--acento-suave)" : undefined }}>
                <span className="check"><input type="radio" name="modo" checked={modo === k} onChange={() => setModo(k)} /> <b>{m.titulo}</b></span>
                <p className="tenue" style={{ margin: "6px 0 0" }}>{m.texto}</p>
              </label>
            ))}
          </div>
          <div className="acciones" style={{ marginTop: 16 }}>
            <button className="btn primario" disabled={!!ocupado || !hojaSel?.es_bitacora} onClick={() => ejecutar(true)}>Simular importación</button>
            {simulacion && (
              <button className={`btn ${modo === "reemplazar" ? "peligro" : "primario"}`} disabled={!!ocupado} onClick={() => ejecutar(false)}>
                Confirmar e importar
              </button>
            )}
            {ocupado && ocupado !== "Leyendo el archivo…" && <span className="tenue">{ocupado}</span>}
          </div>
        </div>
      )}

      {(simulacion || final) && (
        <>
          <h2 style={{ marginTop: 20 }}>{simulacion ? "3. Resultado de la simulación (no se guardó nada)" : "Resultado de la importación"}</h2>
          <Resultado r={simulacion || final} />
        </>
      )}

      <div className="panel">
        <h2>Historial de importaciones</h2>
        <div className="tabla-scroll">
          <table className="tabla">
            <thead><tr><th>Fecha</th><th>Archivo</th><th>Hoja</th><th>Modo</th><th>Tipo</th><th className="num">Nuevos</th><th className="num">Actualizados</th><th>Usuario</th></tr></thead>
            <tbody>
              {historial.map((h) => (
                <tr key={h.id}>
                  <td className="num">{fechaHora(h.creado_en)}</td>
                  <td>{h.archivo}</td>
                  <td>{h.hoja}</td>
                  <td>{MODOS[h.modo]?.titulo || h.modo}</td>
                  <td>{!h.exito ? <span className="badge crit-Alta" title={h.mensaje}>Error</span> : h.simulacion ? <span className="badge etq">Simulación</span> : <span className="badge est-CON_RETRO">Importado</span>}</td>
                  <td className="num">{h.resumen ? num(h.resumen.insertados) : "—"}</td>
                  <td className="num">{h.resumen ? num(h.resumen.actualizados) : "—"}</td>
                  <td>{h.usuario}</td>
                </tr>
              ))}
              {!historial.length && <tr><td colSpan={8} className="vacio">Aún no hay importaciones.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
