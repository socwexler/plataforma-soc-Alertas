import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { AccionesFila, Campo, Confirmar, Crit, Dato, Modal, MsgError, Paginador } from "../components/Ui";
import { CRITICIDADES, fecha, num } from "../util";

const TAMANO = 50;
const NUEVO = {
  nombre: "", servicio: "SOC", criticidad: "Media", es_auditoria: false, tecnica: "", tecnica_id: "", tactica_id: "",
  tecnologia: "", funcionalidad: "", resumen_ejecutivo: "", acciones_recomendadas: "", guia_analisis: "", observaciones: "", activo: true,
};

export default function BaseConocimiento() {
  const { puede } = useAuth();
  const esN2 = puede("kb.editar");
  const [sp, setSp] = useSearchParams();
  const [filtro, setFiltro] = useState({ q: "", servicio: "", tactica_id: "", criticidad: "", con_plantilla: "" });
  const [pagina, setPagina] = useState(1);
  const [datos, setDatos] = useState({ total: 0, items: [] });
  const [tacticas, setTacticas] = useState([]);
  const [ver, setVer] = useState(null);
  const [editar, setEditar] = useState(null);
  const [error, setError] = useState(null);
  const [recarga, setRecarga] = useState(0);
  const [confirmar, setConfirmar] = useState(null);  // { tipo, cu }
  const ejecutar = async () => {
    const { tipo, cu } = confirmar;
    if (tipo === "eliminar") await api(`/casos-uso/${cu.id}`, { metodo: "DELETE" });
    else await api(`/casos-uso/${cu.id}/estado`, { metodo: "PATCH", datos: { activo: !cu.activo } });
    setConfirmar(null);
    setRecarga((x) => x + 1);
  };

  useEffect(() => { api("/tacticas").then(setTacticas).catch(setError); }, []);
  useEffect(() => {
    const idx = sp.get("id");
    if (idx) api(`/casos-uso/${idx}`).then(setVer).catch(setError);
  }, [sp]);
  useEffect(() => {
    const t = setTimeout(() => {
      api("/casos-uso", { params: { ...filtro, pagina, tamano: TAMANO, incluir_inactivos: esN2 } })
        .then(setDatos).catch(setError);
    }, 250);
    return () => clearTimeout(t);
  }, [filtro, pagina, recarga, esN2]);

  const fijar = (k) => (e) => { setFiltro((f) => ({ ...f, [k]: e.target.value })); setPagina(1); };
  const cerrarVer = () => { setVer(null); if (sp.get("id")) setSp({}); };

  const guardar = async () => {
    setError(null);
    const d = { ...editar };
    ["tactica_id", "criticidad", "tecnica_id"].forEach((k) => { if (!d[k]) d[k] = null; });
    try {
      if (d.id) await api(`/casos-uso/${d.id}`, { metodo: "PUT", datos: d });
      else await api("/casos-uso", { metodo: "POST", datos: d });
      setEditar(null);
      setRecarga((x) => x + 1);
    } catch (e) { setError(e); }
  };
  const setE = (k) => (e) => setEditar((x) => ({ ...x, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  return (
    <>
      <div className="cabecera">
        <div>
          <h1>Base de conocimiento</h1>
          <p>Casos de uso del SIEM con criticidad, MITRE ATT&CK y plantilla de comunicación al cliente.</p>
        </div>
        {puede("kb.editar") && <button className="btn primario" onClick={() => setEditar({ ...NUEVO })}>+ Nuevo caso de uso</button>}
      </div>
      <MsgError e={error} />
      <div className="panel">
        <div className="filtros">
          <Campo etiqueta="Buscar" className="busqueda"><input value={filtro.q} onChange={fijar("q")} placeholder="Nombre, técnica, tecnología o texto" /></Campo>
          <Campo etiqueta="Servicio"><select value={filtro.servicio} onChange={fijar("servicio")}><option value="">Todos</option><option>SOC</option><option>NOC</option></select></Campo>
          <Campo etiqueta="Táctica">
            <select value={filtro.tactica_id} onChange={fijar("tactica_id")}>
              <option value="">Todas</option>
              {tacticas.map((t) => <option key={t.id} value={t.id}>{t.nombre}</option>)}
            </select>
          </Campo>
          <Campo etiqueta="Criticidad">
            <select value={filtro.criticidad} onChange={fijar("criticidad")}><option value="">Todas</option>{CRITICIDADES.map((c) => <option key={c}>{c}</option>)}</select>
          </Campo>
          <Campo etiqueta="Plantilla">
            <select value={filtro.con_plantilla} onChange={fijar("con_plantilla")}>
              <option value="">Todos</option><option value="true">Con plantilla</option><option value="false">Sin plantilla</option>
            </select>
          </Campo>
        </div>
        <div className="tabla-scroll">
          <table className="tabla">
            <thead><tr><th>Caso de uso</th><th>Crit.</th><th>Táctica</th><th>Técnica</th><th>Tecnología</th><th>Plantilla</th><th className="num">Casos</th>{esN2 && <th>Acciones</th>}</tr></thead>
            <tbody>
              {datos.items.map((cu) => (
                <tr key={cu.id} className={cu.activo ? "click" : "click inactiva"} onClick={() => setVer(cu)}>
                  <td style={{ minWidth: 260 }}>{cu.nombre}{cu.es_auditoria && <> <span className="badge etq">auditoría</span></>}{!cu.activo && <> <span className="badge etq">deshabilitado</span></>}</td>
                  <td><Crit v={cu.criticidad} /></td>
                  <td>{cu.tactica?.nombre || "—"}</td>
                  <td>{cu.tecnica || "—"}{cu.tecnica_id && <span className="tenue"> · {cu.tecnica_id}</span>}</td>
                  <td>{cu.tecnologia || "—"}</td>
                  <td>{cu.resumen_ejecutivo ? "Sí" : <span className="tenue">No</span>}</td>
                  <td className="num">{num(cu.total_casos)}</td>
                  {esN2 && <td><AccionesFila activo={cu.activo} uso={cu.total_casos ? `${num(cu.total_casos)} caso${cu.total_casos > 1 ? "s" : ""}` : null}
                    onEditar={() => { setError(null); setEditar({ ...NUEVO, ...cu, tactica_id: cu.tactica_id || "" }); }}
                    onEstado={() => setConfirmar({ tipo: "estado", cu })}
                    onEliminar={puede("kb.eliminar") ? () => setConfirmar({ tipo: "eliminar", cu }) : null} /></td>}
                </tr>
              ))}
              {!datos.items.length && <tr><td colSpan={esN2 ? 8 : 7} className="vacio">Sin resultados.</td></tr>}
            </tbody>
          </table>
        </div>
        <Paginador total={datos.total} pagina={pagina} tamano={TAMANO} onCambio={setPagina} />
      </div>

      {confirmar && (
        <Confirmar peligro={confirmar.tipo === "eliminar" || confirmar.cu.activo} onCerrar={() => setConfirmar(null)} onAceptar={ejecutar}
                   titulo={`${confirmar.tipo === "eliminar" ? "Eliminar" : confirmar.cu.activo ? "Deshabilitar" : "Habilitar"} caso de uso`}
                   boton={confirmar.tipo === "eliminar" ? "Eliminar" : confirmar.cu.activo ? "Deshabilitar" : "Habilitar"}>
          <p style={{ margin: 0 }}><b>{confirmar.cu.nombre}</b><br />{confirmar.tipo === "eliminar" ? "Se borra con su plantilla y no se puede recuperar. Si sigue en el Excel, importar los catálogos lo vuelve a crear."
            : confirmar.cu.activo ? "Dejará de aparecer al registrar casos. Los casos que ya lo usan no cambian." : "Volverá a aparecer al registrar casos."}</p>
        </Confirmar>
      )}

      {ver && (
        <Modal titulo={ver.nombre} onCerrar={cerrarVer} pie={<>
          <Link className="btn" to={`/casos?q=${encodeURIComponent(ver.nombre)}`}>Ver casos ({num(ver.total_casos)})</Link>
          {puede("kb.editar") && <button className="btn" onClick={() => { setEditar({ ...NUEVO, ...ver, tactica_id: ver.tactica_id || "" }); setVer(null); }}>Editar</button>}
          <button className="btn primario" onClick={cerrarVer}>Cerrar</button>
        </>}>
          <div className="grid g4">
            <Dato t="Criticidad"><Crit v={ver.criticidad} /></Dato>
            <Dato t="Táctica">{ver.tactica ? `${ver.tactica.nombre} (${ver.tactica.id})` : null}</Dato>
            <Dato t="Técnica">{ver.tecnica}{ver.tecnica_id && ` · ${ver.tecnica_id}`}</Dato>
            <Dato t="Tecnología">{[ver.tecnologia, ver.funcionalidad].filter(Boolean).join(" · ") || null}</Dato>
          </div>
          <Dato t="Resumen ejecutivo (plantilla)"><div className="pre">{ver.resumen_ejecutivo}</div></Dato>
          <Dato t="Acciones de seguridad recomendadas"><div className="pre">{ver.acciones_recomendadas}</div></Dato>
          {ver.guia_analisis && <Dato t="Guía de análisis para el analista"><div className="pre">{ver.guia_analisis}</div></Dato>}
          {ver.observaciones && <Dato t="Observaciones"><div className="pre">{ver.observaciones}</div></Dato>}
          <p className="tenue">Origen: {ver.origen.replaceAll("_", " ")} · actualizado {fecha(ver.actualizado_en)}</p>
        </Modal>
      )}

      {editar && (
        <Modal titulo={editar.id ? "Editar caso de uso" : "Nuevo caso de uso"} onCerrar={() => setEditar(null)} pie={<>
          <button className="btn" onClick={() => setEditar(null)}>Cancelar</button>
          <button className="btn primario" onClick={guardar}>Guardar</button>
        </>}>
          <MsgError e={error} />
          <div className="grid g4">
            <Campo etiqueta="Nombre" className="span-todo"><input value={editar.nombre} onChange={setE("nombre")} /></Campo>
            <Campo etiqueta="Servicio"><select value={editar.servicio} onChange={setE("servicio")}><option>SOC</option><option>NOC</option></select></Campo>
            <Campo etiqueta="Criticidad"><select value={editar.criticidad || ""} onChange={setE("criticidad")}><option value="">—</option>{CRITICIDADES.map((c) => <option key={c}>{c}</option>)}</select></Campo>
            <Campo etiqueta="Táctica" className="span2">
              <select value={editar.tactica_id || ""} onChange={setE("tactica_id")}>
                <option value="">Sin táctica</option>
                {tacticas.map((t) => <option key={t.id} value={t.id}>{t.nombre} ({t.id})</option>)}
              </select>
            </Campo>
            <Campo etiqueta="Técnica" className="span2"><input value={editar.tecnica || ""} onChange={setE("tecnica")} /></Campo>
            <Campo etiqueta="ID técnica" ayuda="T1110.001"><input value={editar.tecnica_id || ""} onChange={setE("tecnica_id")} /></Campo>
            <Campo etiqueta="Tecnología"><input value={editar.tecnologia || ""} onChange={setE("tecnologia")} /></Campo>
            <Campo etiqueta="Resumen ejecutivo (plantilla)" className="span-todo"><textarea rows={6} value={editar.resumen_ejecutivo || ""} onChange={setE("resumen_ejecutivo")} /></Campo>
            <Campo etiqueta="Acciones de seguridad recomendadas" className="span-todo"><textarea rows={6} value={editar.acciones_recomendadas || ""} onChange={setE("acciones_recomendadas")} /></Campo>
            <Campo etiqueta="Guía de análisis" ayuda="estructura sugerida del análisis; se precarga en el formulario" className="span-todo">
              <textarea rows={5} value={editar.guia_analisis || ""} onChange={setE("guia_analisis")} />
            </Campo>
            <Campo etiqueta="Observaciones" className="span-todo"><textarea rows={3} value={editar.observaciones || ""} onChange={setE("observaciones")} /></Campo>
            <label className="check span2"><input type="checkbox" checked={editar.es_auditoria} onChange={setE("es_auditoria")} /> Caso de uso de auditoría</label>
            <label className="check span2"><input type="checkbox" checked={editar.activo} onChange={setE("activo")} /> Activo (aparece en el formulario)</label>
          </div>
        </Modal>
      )}
    </>
  );
}
