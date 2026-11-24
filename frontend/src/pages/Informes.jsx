import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Campo, MsgError } from "../components/Ui";
import { fechaHora } from "../util";

const NOMBRE_ANEXO = { paises_entrantes: "Países ent.", paises_salientes: "Países sal.", puertos: "Puertos", ips: "IPS",
  fuentes: "Fuentes", fuentes_noc: "Fuentes NOC", eps_historico: "EPS" };

export default function Informes() {
  const nav = useNavigate();
  const { puede } = useAuth();
  const [clientes, setClientes] = useState([]);
  const [lista, setLista] = useState([]);
  const [filtro, setFiltro] = useState("");
  const [nuevo, setNuevo] = useState({ cliente_id: "", periodo: "" });
  const [periodos, setPeriodos] = useState([]);
  const [error, setError] = useState(null);
  const [creando, setCreando] = useState(false);

  useEffect(() => { api("/clientes").then(setClientes).catch(setError); }, []);
  useEffect(() => { api("/informes", { params: { cliente_id: filtro } }).then(setLista).catch(setError); }, [filtro]);
  useEffect(() => {
    setPeriodos([]);
    if (!nuevo.cliente_id) return;
    api("/informes/periodos", { params: { cliente_id: nuevo.cliente_id } }).then((p) => {
      setPeriodos(p);
      const sugerido = p.find((x) => !x.en_curso) || p[0];
      setNuevo((n) => ({ ...n, periodo: sugerido ? `${sugerido.anio}-${sugerido.mes}` : "" }));
    }).catch(setError);
  }, [nuevo.cliente_id]);

  const sel = periodos.find((p) => `${p.anio}-${p.mes}` === nuevo.periodo);
  const crear = async () => {
    if (sel?.informe_id) { nav(`/informes/${sel.informe_id}`); return; }
    setCreando(true); setError(null);
    try {
      const r = await api("/informes", { metodo: "POST", datos: { cliente_id: Number(nuevo.cliente_id), anio: sel.anio, mes: sel.mes } });
      nav(`/informes/${r.id}`);
    } catch (e) { setError(e); }
    setCreando(false);
  };

  return (
    <>
      <div className="cabecera">
        <div><h1>Informes mensuales</h1><p>Informe ejecutivo en Word y PDF (plantilla corporativa) y presentación web exportable a PDF, calculados desde la bitácora y los anexos de FortiSIEM.</p></div>
      </div>
      <MsgError e={error} />

      {puede("informes.editar") && (
        <div className="panel">
          <h2>Nuevo informe</h2>
          <div className="filtros" style={{ marginBottom: 0 }}>
            <Campo etiqueta="Cliente">
              <select value={nuevo.cliente_id} onChange={(e) => setNuevo({ cliente_id: e.target.value, periodo: "" })}>
                <option value="">Seleccione…</option>
                {clientes.filter((c) => c.activo).map((c) => <option key={c.id} value={c.id}>{c.codigo} - {c.nombre}</option>)}
              </select>
            </Campo>
            <Campo etiqueta="Periodo" className="busqueda">
              <select value={nuevo.periodo} onChange={(e) => setNuevo((n) => ({ ...n, periodo: e.target.value }))} disabled={!periodos.length}>
                {periodos.map((p) => (
                  <option key={`${p.anio}-${p.mes}`} value={`${p.anio}-${p.mes}`}>
                    {p.nombre} · {p.etiqueta}{p.en_curso ? " (en curso)" : ""}{p.informe_id ? " · ya creado" : ""}
                  </option>
                ))}
              </select>
            </Campo>
            <button className="btn primario" style={{ flex: "0 0 auto" }} disabled={!sel || creando} onClick={crear}>
              {sel?.informe_id ? "Abrir informe" : creando ? "Creando…" : "Crear informe"}
            </button>
          </div>
          {sel?.en_curso && <div className="alerta aviso" style={{ margin: "12px 0 0" }}>Este periodo aún no termina: el informe tendrá datos parciales.</div>}
        </div>
      )}

      <div className="panel">
        <div className="filtros">
          <Campo etiqueta="Cliente">
            <select value={filtro} onChange={(e) => setFiltro(e.target.value)}>
              <option value="">Todos</option>
              {clientes.map((c) => <option key={c.id} value={c.id}>{c.codigo}</option>)}
            </select>
          </Campo>
        </div>
        <div className="tabla-scroll">
          <table className="tabla">
            <thead><tr><th>Cliente</th><th>Informe</th><th>Periodo</th><th>Anexos</th><th>Estado</th><th>Actualizado</th></tr></thead>
            <tbody>
              {lista.map((i) => (
                <tr key={i.id} className="click" onClick={() => nav(`/informes/${i.id}`)}>
                  <td><b>{i.cliente.codigo}</b></td>
                  <td>{i.nombre}</td>
                  <td>{i.periodo}</td>
                  <td>{i.anexos.length ? i.anexos.map((a) => <span key={a} className="badge etq" style={{ marginRight: 4 }}>{NOMBRE_ANEXO[a] || a}</span>) : <span className="tenue">sin anexos</span>}</td>
                  <td>{i.estado === "FINAL" ? <span className="badge est-CON_RETRO">Final</span> : <span className="badge etq">Borrador</span>}</td>
                  <td className="num">{fechaHora(i.actualizado_en)}</td>
                </tr>
              ))}
              {!lista.length && <tr><td colSpan={6} className="vacio">Aún no hay informes.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
