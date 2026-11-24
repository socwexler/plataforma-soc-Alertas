import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { BarraCelda, BarrasH, COLOR_CRIT, Columnas, Leyenda, SERIE } from "../components/Graficos";
import { Campo, Crit, MsgError } from "../components/Ui";
import { duracion, ESTADOS, ESTADOS_GLPI, fechaHora, infoGlpi, num } from "../util";

const SERIES_CRIT = ["Baja", "Media", "Alta", "Crítica"].map((c) => ({ clave: c, nombre: c, color: COLOR_CRIT[c] }));
const iso = (d) => d.toISOString().slice(0, 10);
const pct = (a, b) => (b ? `${Math.round((a / b) * 100)}%` : "—");

function rangos() {
  const hoy = new Date();
  const menos = (n) => { const d = new Date(hoy); d.setDate(d.getDate() - n); return iso(d); };
  const ini = new Date(hoy.getFullYear(), hoy.getMonth(), 1);
  const iniAnt = new Date(hoy.getFullYear(), hoy.getMonth() - 1, 1);
  const finAnt = new Date(hoy.getFullYear(), hoy.getMonth(), 0);
  return {
    "Hoy": [iso(hoy), iso(hoy)],
    "7 días": [menos(6), iso(hoy)],
    "30 días": [menos(29), iso(hoy)],
    "Este mes": [iso(ini), iso(hoy)],
    "Mes anterior": [iso(iniAnt), iso(finAnt)],
    "90 días": [menos(89), iso(hoy)],
  };
}

function Kpi({ etiqueta, valor, sub }) {
  return <div className="kpi"><div className="etiqueta">{etiqueta}</div><div className="valor">{valor}</div>{sub && <div className="sub">{sub}</div>}</div>;
}

export default function Tablero() {
  const nav = useNavigate();
  const R = useMemo(rangos, []);
  const [f, setF] = useState({ desde: R["30 días"][0], hasta: R["30 días"][1], cliente_id: "", servicio: "", analista_id: "" });
  const [d, setD] = useState(null);
  const [cat, setCat] = useState({ clientes: [], analistas: [] });
  const [glpi, setGlpi] = useState({ activo: false });
  const [verTabla, setVerTabla] = useState(false);
  const [error, setError] = useState(null);
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    Promise.all([api("/clientes"), api("/usuarios/analistas")]).then(([clientes, analistas]) => setCat({ clientes, analistas })).catch(setError);
    infoGlpi(api).then(setGlpi);
  }, []);
  useEffect(() => {
    setCargando(true);
    api("/tablero", { params: f }).then((r) => { setD(r); setError(null); }).catch(setError).finally(() => setCargando(false));
  }, [f]);

  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }));
  const irCasos = (extra) => {
    const p = new URLSearchParams({ desde: f.desde, hasta: f.hasta });
    ["cliente_id", "servicio", "analista_id"].forEach((k) => f[k] && p.set(k, f[k]));
    Object.entries(extra).forEach(([k, v]) => p.set(k, v));
    nav(`/casos?${p}`);
  };
  const rangoActivo = Object.entries(R).find(([, [a, b]]) => a === f.desde && b === f.hasta)?.[0];

  const k = d?.indicadores;
  const variacion = k && k.total_periodo_anterior ? Math.round(((k.total - k.total_periodo_anterior) / k.total_periodo_anterior) * 100) : null;
  const diasFmt = (s) => { const [, m, dd] = s.split("-"); return `${dd}/${m}`; };
  const maxAnalista = Math.max(1, ...(d?.por_analista || []).map((a) => a.total));

  return (
    <>
      <div className="cabecera">
        <div><h1>Tablero</h1><p>Casos reportados por analista, estados, tiempos de reporte y tickets GLPI.</p></div>
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
          <div className="kpis" style={{ marginTop: 16 }}>
            <Kpi etiqueta="Casos reportados" valor={num(k.total)}
                 sub={variacion === null ? "sin datos del periodo anterior" : `${variacion > 0 ? "+" : ""}${variacion}% vs. ${num(k.total_periodo_anterior)} del periodo anterior`} />
            <Kpi etiqueta="Criticidad alta o crítica" valor={num(k.alta_critica)} sub={`${pct(k.alta_critica, k.total)} del total`} />
            <Kpi etiqueta="Con retroalimentación" valor={pct(k.con_retro, k.total)} sub={`${num(k.con_retro)} de ${num(k.total)} casos`} />
            <Kpi etiqueta="Tiempo mediano de reporte" valor={duracion(k.mediana_minutos)} sub="alerta SIEM → reporte al cliente" />
            <Kpi etiqueta="Dentro del SLA" valor={pct(k.dentro_sla, k.con_tiempo)} sub={`${num(k.con_tiempo - k.dentro_sla)} casos fuera`} />
            {glpi.activo && <Kpi etiqueta="Tickets GLPI abiertos" valor={num(k.tickets_abiertos)} sub={`${num(k.con_ticket)} casos con ticket`} />}
          </div>

          <div className="panel">
            <div className="cabecera" style={{ marginBottom: 8 }}>
              <h2 style={{ margin: 0 }}>Casos por día y criticidad</h2>
              <button className="btn chico" onClick={() => setVerTabla(!verTabla)}>{verTabla ? "Ver gráfico" : "Ver tabla"}</button>
            </div>
            {!verTabla ? (
              <>
                <Leyenda series={[...SERIES_CRIT].reverse()} />
                <Columnas
                  series={SERIES_CRIT}
                  etiquetaCada={Math.ceil(d.por_dia.length / 12)}
                  datos={d.por_dia.map((x) => ({ etiqueta: diasFmt(x.dia), titulo: new Date(`${x.dia}T12:00`).toLocaleDateString("es-CO", { weekday: "long", day: "numeric", month: "long" }), valores: x }))}
                />
              </>
            ) : (
              <div className="tabla-scroll" style={{ maxHeight: 320 }}>
                <table className="tabla">
                  <thead><tr><th>Día</th>{SERIES_CRIT.map((s) => <th key={s.clave} className="num">{s.nombre}</th>)}<th className="num">Total</th></tr></thead>
                  <tbody>{d.por_dia.map((x) => (
                    <tr key={x.dia}><td className="num">{x.dia}</td>{SERIES_CRIT.map((s) => <td key={s.clave} className="num">{num(x[s.clave])}</td>)}
                      <td className="num"><b>{num(SERIES_CRIT.reduce((a, s) => a + x[s.clave], 0) + x.Sin)}</b></td></tr>
                  ))}</tbody>
                </table>
              </div>
            )}
          </div>

          <div className="panel">
            <h2>Cumplimiento del SLA por criticidad</h2>
            <div className="tabla-scroll">
              <table className="tabla">
                <thead><tr><th>Criticidad</th><th className="num">Objetivo</th><th className="num">Casos</th><th className="num">Dentro</th><th className="num">Fuera</th>
                  <th className="num">Cumplimiento</th><th style={{ width: "25%" }}></th><th className="num">Tiempo mediano</th></tr></thead>
                <tbody>{d.por_sla.map((x) => (
                  <tr key={x.criticidad} className="click" onClick={() => irCasos({ criticidad: x.criticidad })}>
                    <td><Crit v={x.criticidad} /></td><td className="num">≤ {duracion(x.objetivo)}</td><td className="num"><b>{num(x.con_tiempo)}</b></td>
                    <td className="num">{num(x.dentro)}</td><td className="num">{num(x.con_tiempo - x.dentro)}</td>
                    <td className="num">{x.con_tiempo ? pct(x.dentro, x.con_tiempo) : "—"}</td>
                    <td style={{ verticalAlign: "middle" }}><BarraCelda valor={x.dentro} max={x.con_tiempo || 1} /></td>
                    <td className="num">{duracion(x.mediana_minutos)}</td></tr>
                ))}</tbody>
              </table>
            </div>
            <p className="tenue" style={{ marginBottom: 0 }}>Tiempo entre la alerta del SIEM y el reporte al cliente. Cuenta solo los casos con las dos fechas.</p>
          </div>

          <div className="panel">
            <h2>Casos por analista</h2>
            <div className="tabla-scroll">
              <table className="tabla">
                <thead><tr>
                  <th>Analista</th><th className="num">Casos</th><th style={{ width: "18%" }}></th><th className="num">Alta / crítica</th>
                  <th className="num">Con retro.</th><th className="num">Sin retro.</th><th className="num">Tiempo mediano</th><th className="num">Dentro SLA</th>
                  {glpi.activo && <th className="num">Con ticket</th>}<th>Último caso</th>
                </tr></thead>
                <tbody>
                  {d.por_analista.map((a) => (
                    <tr key={a.id} className="click" onClick={() => irCasos({ analista_id: a.id })}>
                      <td style={{ minWidth: 190 }}>{a.nombre}</td>
                      <td className="num"><b>{num(a.total)}</b></td>
                      <td style={{ verticalAlign: "middle" }}><BarraCelda valor={a.total} max={maxAnalista} /></td>
                      <td className="num">{num(a.alta_critica)}</td>
                      <td className="num">{pct(a.con_retro, a.total)}</td>
                      <td className="num">{num(a.total - a.con_retro)}</td>
                      <td className="num">{duracion(a.mediana_minutos)}</td>
                      <td className="num">{pct(a.dentro_sla, a.con_tiempo)}</td>
                      {glpi.activo && <td className="num">{num(a.con_ticket)}</td>}
                      <td className="num">{fechaHora(a.ultimo)}</td>
                    </tr>
                  ))}
                  {!d.por_analista.length && <tr><td colSpan={10} className="vacio">Sin casos en el periodo.</td></tr>}
                </tbody>
              </table>
            </div>
            {d.sin_analista > 0 && <p className="tenue" style={{ marginBottom: 0 }}>{num(d.sin_analista)} casos sin analista asignado.</p>}
          </div>

          <div className="grid g2" style={{ marginTop: 16 }}>
            <div className="panel" style={{ margin: 0 }}>
              <h2>Estado de los casos</h2>
              <BarrasH datos={Object.entries(ESTADOS).map(([kk, n]) => ({ etiqueta: n, valor: d.por_estado[kk] || 0, clave: kk }))}
                       onClick={(x) => irCasos({ estado: x.clave })} />
              {glpi.activo && Object.keys(d.glpi_estados).length > 0 && (
                <>
                  <h3 style={{ marginTop: 18 }}>Tickets GLPI por estado</h3>
                  <BarrasH datos={Object.entries(d.glpi_estados).map(([e, n]) => ({ etiqueta: ESTADOS_GLPI[e] || "Sin sincronizar", valor: n }))} />
                </>
              )}
            </div>
            <div className="panel" style={{ margin: 0 }}>
              <h2>Tiempo entre la alerta y el reporte</h2>
              <Columnas alto={200} series={[{ clave: "total", nombre: "Casos", color: SERIE }]}
                        datos={d.tiempos.map((t) => ({ etiqueta: t.tramo, valores: { total: t.total } }))} />
            </div>
          </div>

          <div className="grid g2" style={{ marginTop: 16 }}>
            <div className="panel" style={{ margin: 0 }}>
              <h2>Casos por hora del día</h2>
              <Columnas alto={200} etiquetaCada={3} series={[{ clave: "total", nombre: "Casos", color: SERIE }]}
                        datos={d.por_hora.map((h) => ({ etiqueta: `${h.hora}h`, titulo: `${String(h.hora).padStart(2, "0")}:00 – ${String(h.hora).padStart(2, "0")}:59`, valores: { total: h.total } }))} />
            </div>
            <div className="panel" style={{ margin: 0 }}>
              <h2>Top 10 alertas</h2>
              <BarrasH datos={d.top_alertas.map((a) => ({ etiqueta: a.alerta, valor: a.total }))} onClick={(x) => irCasos({ q: x.etiqueta })} />
            </div>
          </div>

          <div className="panel" style={{ marginTop: 16 }}>
            <h2>Por cliente</h2>
            <div className="tabla-scroll">
              <table className="tabla">
                <thead><tr><th>Cliente</th><th className="num">Casos</th><th className="num">Alta / crítica</th><th className="num">Con retro.</th>
                  <th className="num">Tiempo mediano</th>{glpi.activo && <th className="num">Tickets abiertos</th>}</tr></thead>
                <tbody>
                  {d.por_cliente.map((c) => (
                    <tr key={c.id} className="click" onClick={() => irCasos({ cliente_id: c.id })}>
                      <td><b>{c.codigo}</b> <span className="tenue">{c.nombre}</span></td>
                      <td className="num">{num(c.total)}</td><td className="num">{num(c.alta_critica)}</td>
                      <td className="num">{pct(c.con_retro, c.total)}</td><td className="num">{duracion(c.mediana_minutos)}</td>
                      {glpi.activo && <td className="num">{num(c.tickets_abiertos)}</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
