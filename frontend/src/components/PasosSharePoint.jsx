import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { copiarTexto } from "../util";

const LINEA_ENV = 'SHAREPOINT_CARPETA_LOCAL="C:\\Users\\<usuario>\\OneDrive - <empresa>\\<carpeta de SharePoint>"';
const COMANDO = "docker compose up -d";
const SOLICITUD_TI = `Solicitud para TI: acceso de solo lectura de la Plataforma SOC a SharePoint

1. Registrar una aplicación en Microsoft Entra ID (p. ej. «Plataforma SOC - lectura SharePoint»).
2. Darle el permiso de aplicación de Microsoft Graph «Sites.Selected» y el consentimiento de administrador.
3. Conceder a esa aplicación el rol «read» solo sobre el sitio de SharePoint del SOC (no sobre todos los sitios).
4. Crear un secreto de cliente y entregar por un canal seguro: ID del inquilino (tenant), ID de la aplicación (client ID) y el secreto, con su fecha de vencimiento.
5. Permitir que el servidor de la plataforma salga por HTTPS a login.microsoftonline.com, graph.microsoft.com y *.sharepoint.com.

La plataforma solo lee los archivos; no escribe ni borra nada en SharePoint.`;

function Paso({ ok, children }) {
  return (
    <li className={`paso ${ok === true ? "hecho" : ok === false ? "falta" : ""}`}>
      <span className="marca-paso" aria-hidden="true">{ok === true ? "✓" : ok === false ? "!" : "·"}</span>
      <div>{children}</div>
    </li>
  );
}

function Copiar({ texto, etiqueta = "Copiar" }) {
  const [hecho, setHecho] = useState(false);
  return <button type="button" className="btn chico" onClick={async () => { setHecho(await copiarTexto(texto)); setTimeout(() => setHecho(false), 1500); }}>{hecho ? "Copiado" : etiqueta}</button>;
}

/** Guía de pasos para activar los anexos desde SharePoint, con lo que ya está listo. */
export default function PasosSharePoint({ version }) {
  const [e, setE] = useState(null);
  useEffect(() => { api("/config/sharepoint/estado").then(setE).catch(() => setE(null)); }, [version]);
  if (!e) return null;
  const g = e.graph, graphListo = g.sitio && g.tenant && g.cliente_id && g.secreto;
  const enUso = (m) => e.modo === m && <span className="badge al-REPORTADA" style={{ marginLeft: 8 }}>en uso</span>;
  return (
    <div className="panel pasos-sp">
      <h2>Cómo activarlo</h2>
      <p className="tenue" style={{ marginTop: -4 }}>Elija uno de los dos orígenes. Los pasos marcados con ✓ ya están listos.</p>

      <details open={e.modo !== "graph"}>
        <summary><b>Opción A · Carpeta sincronizada</b>{enUso("carpeta")} <span className="tenue">en el equipo que tiene OneDrive</span></summary>
        <ol className="pasos">
          <Paso>Sincronice con OneDrive la carpeta de SharePoint del SOC en este equipo (en SharePoint: «Agregar acceso directo a Mis archivos» o «Sincronizar»).</Paso>
          <Paso ok={e.carpeta_montada}>
            Agregue al archivo <code>.env</code> de la plataforma la ruta de esa carpeta y reinicie:
            <div className="codigo-paso"><code>{LINEA_ENV}</code><Copiar texto={LINEA_ENV} /></div>
            <div className="codigo-paso"><code>{COMANDO}</code><Copiar texto={COMANDO} /></div>
            <span className="tenue">{e.carpeta_montada ? "La carpeta ya está montada." : "Todavía no hay ninguna carpeta montada."}</span>
          </Paso>
          <Paso ok={e.modo === "carpeta" ? e.carpeta_base_existe !== false : undefined}>
            Abajo, en <b>Origen</b>, elija «Carpeta sincronizada». Si la carpeta montada contiene la de los anexos, escriba su nombre en <b>Carpeta base</b>. Guarde.
            {e.modo === "carpeta" && e.carpeta_base_existe === false && <div style={{ color: "var(--aviso-tx)" }}>No existe la carpeta base «{e.carpeta_base}» dentro de la carpeta montada.</div>}
          </Paso>
          <Paso>Pulse <b>Probar SharePoint</b> (al final de esta página): muestra las 6 carpetas y qué clientes no tienen subcarpeta. Si en SharePoint un cliente se llama distinto, escríbalo en <Link to="/clientes">Clientes</Link> → «Carpeta en SharePoint».</Paso>
        </ol>
      </details>

      <details open={e.modo === "graph"}>
        <summary><b>Opción B · Microsoft Graph</b>{enUso("graph")} <span className="tenue">para el servidor</span></summary>
        <ol className="pasos">
          <Paso ok={graphListo || undefined}>
            TI registra una aplicación en Entra ID con permiso <b>Sites.Selected</b> de solo lectura sobre el sitio del SOC y entrega el tenant, el client ID y el secreto.
            <div className="acciones" style={{ marginTop: 6 }}><Copiar texto={SOLICITUD_TI} etiqueta="Copiar la solicitud para TI" /></div>
          </Paso>
          <Paso>El servidor debe poder salir por HTTPS a <code>login.microsoftonline.com</code>, <code>graph.microsoft.com</code> y <code>*.sharepoint.com</code>.</Paso>
          <Paso ok={graphListo}>
            Abajo escriba el <b>sitio</b>, el <b>tenant</b>, el <b>client ID</b> y el <b>secreto</b>{!graphListo && (
              <span className="tenue"> (falta: {[!g.sitio && "sitio", !g.tenant && "tenant", !g.cliente_id && "client ID", !g.secreto && "secreto"].filter(Boolean).join(", ")})</span>)}.
          </Paso>
          <Paso ok={e.modo === "graph" || undefined}>En <b>Origen</b> elija «Microsoft Graph», guarde y pulse <b>Probar SharePoint</b>.</Paso>
        </ol>
      </details>

      <details open>
        <summary><b>Cada mes</b> <span className="tenue">equipo del SOC</span></summary>
        <ol className="pasos">
          <Paso>Exporte de FortiSIEM los 6 anexos <b>con el periodo de corte de cada cliente</b> (no el mes calendario si su corte es otro).</Paso>
          <Paso>
            Guarde cada uno en la subcarpeta del cliente dentro de su carpeta:
            <ul className="carpetas-paso">{Object.entries(e.carpetas).map(([t, c]) => <li key={t}><b>{e.nombres[t]}:</b> carpeta «{c}…»</li>)}</ul>
          </Paso>
          <Paso>Nombre: <code>CODIGO_AAAA-MM.csv</code> con el mes en que <b>empieza</b> el periodo; las fuentes NOC, <code>CODIGO_AAAA-MM_NOC.csv</code>. Ej.: del 16 de octubre al 15 de noviembre de 2026 → <code>CODIGO_2026-10.csv</code>.</Paso>
          <Paso>En el informe, sección 2 (Anexos de FortiSIEM): <b>Traer de SharePoint</b>, revise lo marcado y cargue.</Paso>
        </ol>
      </details>
    </div>
  );
}
