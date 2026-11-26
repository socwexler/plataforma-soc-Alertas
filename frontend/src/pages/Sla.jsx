import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { BarraCelda, Columnas, Leyenda, SERIE } from "../components/Graficos";
import { Campo, Crit, MsgError } from "../components/Ui";
import { CRITICIDADES, duracion, fechaHora, isoCol, num, textoSla } from "../util";

const iso = isoCol;   // fecha de Colombia: después de las 7 p. m. la de UTC ya es mañana
const pct = (a, b) => (b ? `${Math.round((a / b) * 100)}%` : "—");
const FUERA = "#e34948";
const SERIES = [{ clave: "dentro", nombre: "Dentro del SLA", color: SERIE }, { clave: "fuera", nombre: "Fuera del SLA", color: FUERA }];
const exceso = (m) => (m < 1 ? `${Math.max(1, Math.round(m * 60))} s` : duracion(Math.round(m)));

function rangos() {
  const hoy = new Date();
  const menos = (n) => { const d = new Date(hoy); d.setDate(d.getDate() - n); return iso(d); };
  return {
    "7 días": [menos(6), iso(hoy)],
    "30 días": [menos(29), iso(hoy)],
    "Este mes": [iso(new Date(hoy.getFullYear(), hoy.getMonth(), 1)), iso(hoy)],
    "Mes anterior": [iso(new Date(hoy.getFullYear(), hoy.getMonth() - 1, 1)), iso(new Date(hoy.getFullYear(), hoy.getMonth(), 0))],
    "90 días": [menos(89), iso(hoy)],
  };
}

function Kpi({ etiqueta, valor, sub }) {
  return <div className="kpi"><div className="etiqueta">{etiqueta}</div><div className="valor">{valor}</div>{sub && <div className="sub">{sub}</div>}</div>;
}

/** Celda «porcentaje · dentro de total» de una criticidad. */
function Celda({ x }) {
  if (!x || !x.con_tiempo) return <td className="num tenue">—</td>;
  const malo = x.dentro / x.con_tiempo < 0.9;   // en rojo por debajo del 90 %
  return <td className="num" title={`${x.dentro} de ${x.con_tiempo} dentro · mediana ${duracion(x.mediana_minutos)}`}>
    <b style={{ color: malo ? "var(--alta-tx)" : undefined }}>{pct(x.dentro, x.con_tiempo)}</b> <span className="tenue">{x.dentro}/{x.con_tiempo}</span></td>;
}

/** SLA de notificación por analista: cumplimiento por criticidad, evolución y casos fuera del objetivo. */
export default function Sla() {
  const R = useMemo(rangos, []);
  const [sp, setSp] = useSearchParams();
  const [f, setF] = useState(() => ({ desde: sp.get("desde") || R["30 días"][0], hasta: sp.get("hasta") || R["30 días"][1],
    cliente_id: sp.get("cliente_id") || "", servicio: sp.get("servicio") || "", analista_id: sp.get("analista_id") || "" }));
  const [d, setD] = useState(null);
  const [cat, setCat] = useState({ clientes: [], analistas: [] });
  const [error, setError] = useState(null);
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    Promise.all([api("/clientes"), api("/usuarios/analistas")]).then(([clientes, analistas]) => setCat({ clientes, analistas })).catch(setError);
  }, []);
  useEffect(() => {
    setSp(Object.fromEntries(Object.entries(f).filter(([, v]) => v)), { replace: true });
    setCargando(true);
    api("/tablero/sla", { params: f }).then((r) => { setD(r); setError(null); }).catch(setError).finally(() => setCargando(false));
  }, [f, setSp]);

  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }));
  const elegir = (id) => { setF((x) => ({ ...x, analista_id: String(id) === x.analista_id ? "" : String(id) })); window.scrollTo({ top: 0, behavior: "smooth" }); };
  const rangoActivo = Object.entries(R).find(([, [a, b]]) => a === f.desde && b === f.hasta)?.[0];
  const elegido = cat.analistas.find((a) => String(a.id) === f.analista_id) || d?.por_analista.find((a) => String(a.id) === f.analista_id);
  const k = d?.resumen;
  const etiquetaEvol = (s) => { const [, m, dd] = s.split("-"); return `${dd}/${m}`; };

  return (
    <>
      <div className="cabecera">
        <div><h1>SLA de notificación</h1>
          <p>Tiempo entre la alerta del SIEM y el reporte al cliente{d ? `: ${textoSla(d.objetivos)}` : ""}. Se cuenta por la fecha de bitácora.</p></div>
        <Link className="btn" to="/tablero">Volver al tablero</Link>
      </div>

      <div className="panel">
        <div className="filtros" style={{ marginBottom: 8 }}>
          <Campo etiqueta="Desde"><input type="date" value={f.desde} max={f.hasta} onChange={set("desde")} /></Campo>
          <Campo etiqueta="Hasta"><input type="date" value={f.hasta} min={f.desde} onChange={set("hasta")} /></Campo>
          <Campo etiqueta="Cliente">
            <select value={f.cliente_id} onChange={set("cliente_id")}><option value="">Todos</option>{cat.clientes.map((c) => <option key={c.id} value={c.id}>{c.codigo}</option>)}</select>
          </Campo>
          <Campo etiqueta="Servicio"><select value={f.servicio} onChange={set("servicio")}><option value="">Todos</option><option>SOC</option><option>NOC</option></select></Campo>
          <Campo etiqueta="Analista">
            <select value={f.analista_id} onChange={set("analista_id")}><option value="">Todos</option>{cat.analistas.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}</select>
          </Campo>
        </div>
        <div className="acciones">
          {Object.entries(R).map(([n, [a, b]]) => (
            <button key={n} className={`btn chico ${rangoActivo === n ? "primario" : ""}`} onClick={() => setF((x) => ({ ...x, desde: a, hasta: b }))}>{n}</button>
          ))}
          {cargando && <span className="tenue">Actualizando…</span>}
        </div>
      </div>
      <MsgError e={error} />

      {d && (
        <div style={{ opacity: cargando ? 0.6 : 1, transition: "opacity .15s" }}>
          {elegido && (
            <div className="alerta aviso acciones" style={{ marginTop: 16, justifyContent: "space-between" }}>
              <span>Detalle de <b>{elegido.nombre}</b>: indicadores, evolución y casos fuera del SLA son solo suyos.</span>
              <button className="btn chico" onClick={() => setF((x) => ({ ...x, analista_id: "" }))}>Ver todos</button>
            </div>
          )}
          <div className="kpis" style={{ marginTop: 16 }}>
            <Kpi etiqueta="Cumplimiento" valor={pct(k.dentro, k.con_tiempo)} sub={`${num(k.dentro)} de ${num(k.con_tiempo)} casos dentro`} />
            <Kpi etiqueta="Fuera del SLA" valor={num(d.total_fuera)} sub={`${pct(d.total_fuera, k.con_tiempo)} de los casos medidos`} />
            <Kpi etiqueta="Tiempo mediano" valor={duracion(k.mediana_minutos)} sub={`el 90% en ${duracion(k.p90_minutos)} o menos`} />
            <Kpi etiqueta="Casos medidos" valor={num(k.con_tiempo)} sub={k.total > k.con_tiempo ? `${num(k.total - k.con_tiempo)} sin las dos fechas` : "todos tienen las dos fechas"} />
          </div>

          <div className="panel">
            <h2>Por criticidad</h2>
            <div className="tabla-scroll">
              <table className="tabla">
                <thead><tr><th>Criticidad</th><th className="num">Objetivo</th><th className="num">Casos</th><th className="num">Dentro</th><th className="num">Fuera</th>
                  <th className="num">Cumplimiento</th><th style={{ width: "22%" }}></th><th className="num">Mediana</th><th className="num">90% en</th><th className="num">Máximo</th></tr></thead>
                <tbody>{d.por_criticidad.map((x) => (
                  <tr key={x.criticidad}>
                    <td><Crit v={x.criticidad} /></td><td className="num">≤ {duracion(x.objetivo)}</td><td className="num"><b>{num(x.con_tiempo)}</b></td>
                    <td className="num">{num(x.dentro)}</td><td className="num">{num(x.con_tiempo - x.dentro)}</td>
                    <td className="num">{pct(x.dentro, x.con_tiempo)}</td>
                    <td style={{ verticalAlign: "middle" }}><BarraCelda valor={x.dentro} max={x.con_tiempo || 1} /></td>
                    <td className="num">{duracion(x.mediana_minutos)}</td><td className="num">{duracion(x.p90_minutos)}</td><td className="num">{duracion(x.max_minutos)}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </div>

          <div className="panel">
            <h2>Por analista</h2>
            <p className="tenue" style={{ marginTop: -6 }}>Primero quien tiene más casos fuera del SLA. Haga clic en un analista para ver su detalle.</p>
            <div className="tabla-scroll">
              <table className="tabla">
                <thead><tr><th>Analista</th><th className="num">Casos</th><th className="num">Cumplimiento</th><th style={{ width: "14%" }}></th><th className="num">Fuera</th>
                  {CRITICIDADES.map((c) => <th key={c} className="num">{c}</th>)}<th className="num">Mediana</th><th className="num">90% en</th></tr></thead>
                <tbody>
                  {d.por_analista.map((a) => (
                    <tr key={a.id} className="click" onClick={() => elegir(a.id)} style={String(a.id) === f.analista_id ? { background: "var(--acento-suave)" } : undefined}>
                      <td style={{ minWidth: 190 }}><b>{a.nombre}</b></td>
                      <td className="num">{num(a.con_tiempo)}</td>
                      <td className="num"><b>{pct(a.dentro, a.con_tiempo)}</b></td>
                      <td style={{ verticalAlign: "middle" }}><BarraCelda valor={a.dentro} max={a.con_tiempo || 1} /></td>
                      <td className="num" style={{ color: a.con_tiempo > a.dentro ? "var(--alta-tx)" : undefined }}>{num(a.con_tiempo - a.dentro)}</td>
                      {CRITICIDADES.map((c) => <Celda key={c} x={a.por_criticidad[c]} />)}
                      <td className="num">{duracion(a.mediana_minutos)}</td><td className="num">{duracion(a.p90_minutos)}</td>
                    </tr>
                  ))}
                  {!d.por_analista.length && <tr><td colSpan={11} className="vacio">Sin casos con analista en el periodo.</td></tr>}
                </tbody>
              </table>
            </div>
          </div>

          <div className="panel">
            <h2>Evolución {d.unidad === "dia" ? "por día" : "por semana"}{elegido ? ` · ${elegido.nombre}` : ""}</h2>
            <Leyenda series={[...SERIES].reverse()} />
            <Columnas alto={220} series={SERIES} etiquetaCada={Math.ceil(d.evolucion.length / 14)}
                      datos={d.evolucion.map((x) => ({ etiqueta: etiquetaEvol(x.desde), titulo: `${d.unidad === "dia" ? "" : "Semana del "}${etiquetaEvol(x.desde)} · ${pct(x.dentro, x.con_tiempo)} dentro`,
                                                       valores: { dentro: x.dentro, fuera: x.con_tiempo - x.dentro } }))} />
          </div>

          <div className="panel">
            <h2>Casos fuera del SLA{elegido ? ` · ${elegido.nombre}` : ""}</h2>
            <p className="tenue" style={{ marginTop: -6 }}>Primero los que más se pasaron del objetivo{d.total_fuera > d.fuera.length ? `; se muestran ${d.fuera.length} de ${num(d.total_fuera)}` : ""}.</p>
            <div className="tabla-scroll">
              <table className="tabla">
                <thead><tr><th>Número</th><th>Cliente</th><th>Alerta</th><th>Crit.</th><th>Analista</th><th>Evento SIEM</th><th className="num">Tiempo</th><th className="num">Objetivo</th><th className="num">Se pasó</th></tr></thead>
                <tbody>
                  {d.fuera.map((c) => (
                    <tr key={c.id}>
                      <td><Link to={`/casos/${c.id}`}>{c.numero}</Link></td><td>{c.cliente}</td><td style={{ maxWidth: 320 }}>{c.alerta}</td>
                      <td><Crit v={c.criticidad} /></td><td>{c.analista || "—"}</td><td className="num">{fechaHora(c.fecha_evento)}</td>
                      <td className="num">{exceso(c.minutos)}</td><td className="num">{duracion(c.objetivo)}</td>
                      <td className="num" style={{ color: "var(--alta-tx)" }}><b>+{exceso(c.exceso_minutos)}</b></td>
                    </tr>
                  ))}
                  {!d.fuera.length && <tr><td colSpan={9} className="vacio">Ningún caso fuera del SLA en el periodo.</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
