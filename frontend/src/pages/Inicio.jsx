import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Crit, Estado, MsgError } from "../components/Ui";
import { duracion, ESTADOS, fechaHora, num, textoSla } from "../util";

export default function Inicio() {
  const { usuario, puede } = useAuth();
  const [r, setR] = useState(null);
  const [ultimos, setUltimos] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    api("/casos/resumen").then(setR).catch(setError);
    api("/casos", { params: { tamano: 8 } }).then((p) => setUltimos(p.items)).catch(setError);
  }, []);

  const maxCli = Math.max(1, ...(r?.por_cliente_30 || []).map((c) => c.total));
  const totalEst = Object.values(r?.por_estado_30 || {}).reduce((a, b) => a + b, 0) || 1;

  return (
    <>
      <div className="cabecera">
        <div>
          <h1>Hola, {usuario.nombre.split(" ")[0]}</h1>
          <p>Resumen de la operación de los últimos 30 días.</p>
        </div>
        {puede("casos.crear") && <Link className="btn primario" to="/casos/nuevo">+ Registrar caso</Link>}
      </div>
      <MsgError e={error} />
      {r && (
        <div className="kpis">
          <div className="kpi"><div className="etiqueta">Casos hoy</div><div className="valor">{num(r.hoy)}</div>
            {puede("casos.crear") && <div className="sub">{num(r.mios_hoy)} registrados por usted</div>}</div>
          <div className="kpi"><div className="etiqueta">Casos últimos 30 días</div><div className="valor">{num(r.ultimos_30)}</div></div>
          <div className="kpi"><div className="etiqueta">Tiempo mediano de reporte</div><div className="valor">{duracion(r.mediana_minutos_30)}</div>
            <div className="sub">alerta SIEM → reporte al cliente</div></div>
          <div className="kpi"><div className="etiqueta">Fuera de SLA</div><div className="valor">{num(r.fuera_sla_30)}</div>
            <div className="sub">{r.con_tiempo_30 ? Math.round((r.fuera_sla_30 / r.con_tiempo_30) * 100) : 0}% de los casos · {textoSla(r.sla)}</div></div>
        </div>
      )}
      {r && (
        <div className="grid g2">
          <div className="panel">
            <h2>Casos por cliente (30 días)</h2>
            <div className="barras">
              {r.por_cliente_30.map((c) => (
                <div className="barra" key={c.codigo}>
                  <span>{c.codigo}</span>
                  <div className="pista"><div className="relleno" style={{ width: `${(c.total / maxCli) * 100}%` }} /></div>
                  <span className="num">{num(c.total)}</span>
                </div>
              ))}
              {!r.por_cliente_30.length && <div className="tenue">Sin casos en el periodo.</div>}
            </div>
          </div>
          <div className="panel">
            <h2>Retroalimentación del cliente (30 días)</h2>
            <div className="barras">
              {Object.keys(ESTADOS).map((k) => (
                <div className="barra" key={k} style={{ gridTemplateColumns: "150px 1fr 50px" }}>
                  <span>{ESTADOS[k]}</span>
                  <div className="pista"><div className="relleno" style={{ width: `${((r.por_estado_30[k] || 0) / totalEst) * 100}%`, background: k === "CON_RETRO" ? "var(--acento)" : undefined }} /></div>
                  <span className="num">{num(r.por_estado_30[k] || 0)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
      <div className="panel">
        <h2>Últimos casos registrados</h2>
        <div className="tabla-scroll">
          <table className="tabla">
            <thead><tr><th>Número</th><th>Cliente</th><th>Alerta</th><th>Criticidad</th><th>Evento</th><th>Analista</th><th>Estado</th></tr></thead>
            <tbody>
              {ultimos.map((c) => (
                <tr key={c.id}>
                  <td className="num"><Link to={`/casos/${c.id}`}>{c.numero}</Link></td>
                  <td>{c.cliente.codigo}</td>
                  <td>{c.alerta}</td>
                  <td><Crit v={c.criticidad} /></td>
                  <td className="num">{fechaHora(c.fecha_evento)}</td>
                  <td>{c.analista?.nombre || "—"}</td>
                  <td><Estado v={c.estado} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
