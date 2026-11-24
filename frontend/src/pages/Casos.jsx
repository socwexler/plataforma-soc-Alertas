import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Campo, Crit, Estado, MsgError, Paginador, Revision } from "../components/Ui";
import { CRITICIDADES, duracion, ESTADOS, ESTADOS_GLPI, fechaHora, REVISIONES } from "../util";

const FILTROS = ["q", "cliente_id", "analista_id", "servicio", "estado", "criticidad", "tactica_id", "revision", "anulados", "desde", "hasta"];
const TAMANO = 50;

export default function Casos() {
  const [sp, setSp] = useSearchParams();
  const nav = useNavigate();
  const { puede } = useAuth();
  const [datos, setDatos] = useState({ total: 0, items: [] });
  const [cat, setCat] = useState({ clientes: [], analistas: [], tacticas: [] });
  const [error, setError] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [q, setQ] = useState(sp.get("q") || "");
  const pagina = Number(sp.get("pagina") || 1);

  useEffect(() => {
    Promise.all([api("/clientes"), api("/usuarios/analistas"), api("/tacticas")])
      .then(([clientes, analistas, tacticas]) => setCat({ clientes, analistas, tacticas }))
      .catch(setError);
  }, []);

  useEffect(() => {
    const params = { pagina, tamano: TAMANO };
    FILTROS.forEach((k) => { if (sp.get(k)) params[k] = sp.get(k); });
    setCargando(true);
    api("/casos", { params }).then(setDatos).catch(setError).finally(() => setCargando(false));
  }, [sp, pagina]);

  const fijar = (k, v) => {
    const n = new URLSearchParams(sp);
    if (v) n.set(k, v); else n.delete(k);
    n.delete("pagina");
    setSp(n);
  };

  // búsqueda con espera para no consultar por cada tecla
  useEffect(() => {
    const t = setTimeout(() => { if ((sp.get("q") || "") !== q) fijar("q", q); }, 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const sel = (k, opciones, todas = "Todos") => (
    <select value={sp.get(k) || ""} onChange={(e) => fijar(k, e.target.value)}>
      <option value="">{todas}</option>
      {opciones}
    </select>
  );

  return (
    <>
      <div className="cabecera">
        <div><h1>Casos</h1><p>Bitácora de eventos escalados a los clientes.</p></div>
        {puede("casos.crear") && <Link className="btn primario" to="/casos/nuevo">+ Registrar caso</Link>}
      </div>
      <MsgError e={error} />
      <div className="panel">
        <div className="filtros">
          <Campo etiqueta="Buscar" className="busqueda">
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Número, alerta, IP, texto del análisis o log" />
          </Campo>
          <Campo etiqueta="Cliente">{sel("cliente_id", cat.clientes.map((c) => <option key={c.id} value={c.id}>{c.codigo}</option>))}</Campo>
          <Campo etiqueta="Servicio">{sel("servicio", ["SOC", "NOC"].map((s) => <option key={s}>{s}</option>))}</Campo>
          <Campo etiqueta="Criticidad">{sel("criticidad", CRITICIDADES.map((c) => <option key={c}>{c}</option>), "Todas")}</Campo>
          <Campo etiqueta="Estado">{sel("estado", Object.entries(ESTADOS).map(([k, v]) => <option key={k} value={k}>{v}</option>))}</Campo>
          <Campo etiqueta="Analista">{sel("analista_id", cat.analistas.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>))}</Campo>
          <Campo etiqueta="Táctica">{sel("tactica_id", cat.tacticas.map((t) => <option key={t.id} value={t.id}>{t.nombre}</option>), "Todas")}</Campo>
          <Campo etiqueta="Revisión">{sel("revision", Object.entries(REVISIONES).map(([k, v]) => <option key={k} value={k}>{v}</option>), "Todas")}</Campo>
          <Campo etiqueta="Anulados">{sel("anulados", [<option key="i" value="incluir">Incluir</option>, <option key="s" value="solo">Solo anulados</option>], "Ocultos")}</Campo>
          <Campo etiqueta="Desde"><input type="date" value={sp.get("desde") || ""} onChange={(e) => fijar("desde", e.target.value)} /></Campo>
          <Campo etiqueta="Hasta"><input type="date" value={sp.get("hasta") || ""} onChange={(e) => fijar("hasta", e.target.value)} /></Campo>
          {[...sp.keys()].some((k) => FILTROS.includes(k)) && (
            <button className="btn fantasma" style={{ flex: "0 0 auto" }} onClick={() => { setQ(""); setSp({}); }}>Limpiar filtros</button>
          )}
        </div>
        <div className="tabla-scroll" style={{ opacity: cargando ? 0.6 : 1 }}>
          <table className="tabla">
            <thead>
              <tr><th>Número</th><th>Cliente</th><th>Alerta</th><th>Crit.</th><th>Táctica</th><th>Evento SIEM</th><th>Tiempo reporte</th><th>Analista</th><th>Estado</th><th>GLPI</th></tr>
            </thead>
            <tbody>
              {datos.items.map((c) => (
                <tr key={c.id} className={c.anulado_en ? "click anulado" : "click"} onClick={() => nav(`/casos/${c.id}`)}>
                  <td className="num"><b>{c.numero}</b></td>
                  <td title={c.cliente.nombre}>{c.cliente.codigo}</td>
                  <td style={{ minWidth: 240 }}>{c.alerta}</td>
                  <td><Crit v={c.criticidad} /></td>
                  <td>{c.tactica?.nombre || "—"}</td>
                  <td className="num">{fechaHora(c.fecha_evento)}</td>
                  <td className="num">{duracion(c.minutos_respuesta)}</td>
                  <td>{c.analista?.nombre || "—"}</td>
                  <td>{c.anulado_en ? <span className="badge est-anulado">Anulado</span> : <Estado v={c.estado} />}{!c.anulado_en && c.revision && c.revision !== "REVISADO" && <div style={{ marginTop: 4 }}><Revision v={c.revision} /></div>}</td>
                  <td className="num">{c.glpi_ticket_id || "—"}{c.glpi_estado && <div className="tenue" style={{ fontSize: 12 }}>{ESTADOS_GLPI[c.glpi_estado]}</div>}</td>
                </tr>
              ))}
              {!cargando && !datos.items.length && <tr><td colSpan={10} className="vacio">No hay casos con esos filtros.</td></tr>}
            </tbody>
          </table>
        </div>
        <Paginador total={datos.total} pagina={pagina} tamano={TAMANO}
                   onCambio={(p) => { const n = new URLSearchParams(sp); n.set("pagina", p); setSp(n); }} />
      </div>
    </>
  );
}
