import { useEffect, useState } from "react";
import { api } from "../api";
import { Modal, MsgError } from "./Ui";
import { fechaHora } from "../util";

const peso = (n) => (n == null ? "" : n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1048576).toFixed(1)} MB`);

/** Elegir y cargar los anexos del informe desde SharePoint (solo lectura). */
export default function TraerSharePoint({ id, onCargado, onCerrar }) {
  const [d, setD] = useState(null);
  const [marcados, setMarcados] = useState({});   // "tipo|nombre" -> true
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    api(`/informes/${id}/sharepoint`).then((r) => {
      setD(r);
      const m = {};
      r.tipos.forEach((t) => t.archivos.filter((a) => a.sugerido).forEach((a) => { m[`${t.tipo}|${a.nombre}`] = true; }));
      setMarcados(m);
    }).catch(setError);
  }, [id]);

  const elegidos = Object.keys(marcados).filter((k) => marcados[k]);
  const cargar = async () => {
    setOcupado(true); setError(null);
    try {
      const r = await api(`/informes/${id}/sharepoint`, { metodo: "POST", datos: { archivos: elegidos.map((k) => { const i = k.indexOf("|"); return { tipo: k.slice(0, i), nombre: k.slice(i + 1) }; }) } });
      onCargado(r);
    } catch (e) { setError(e); setOcupado(false); }
  };

  return (
    <Modal titulo="Traer anexos de SharePoint" onCerrar={onCerrar}
           pie={<><button className="btn" onClick={onCerrar}>Cancelar</button>
             <button className="btn primario" disabled={ocupado || !elegidos.length} onClick={cargar}>{ocupado ? "Cargando…" : `Cargar ${elegidos.length || ""} archivo${elegidos.length === 1 ? "" : "s"}`}</button></>}>
      <MsgError e={error} />
      {!d && !error && <div className="vacio">Buscando en SharePoint…</div>}
      {d && (
        <>
          <p className="tenue" style={{ marginTop: 0 }}>Se marcan los archivos del periodo (<b>{d.patron}</b>, con <b>_NOC</b> opcional). Si no siguen ese nombre, elija el que corresponda. Solo se lee: no se cambia nada en SharePoint.</p>
          <div className="sp-lista">
            {d.tipos.map((t) => (
              <div key={t.tipo} className="sp-tipo">
                <div className="sp-cab"><b>{t.nombre}</b> <span className="tenue">{t.carpeta ? `${t.carpeta}${t.carpeta_cliente ? ` / ${t.carpeta_cliente}` : ""}` : ""}</span></div>
                {t.error && <div className="tenue" style={{ color: "var(--aviso-tx)" }}>{t.error}</div>}
                {!t.error && !t.archivos.length && <div className="tenue">La carpeta del cliente no tiene archivos CSV o Excel.</div>}
                {t.archivos.map((a) => {
                  const k = `${t.tipo}|${a.nombre}`;
                  return (
                    <label key={k} className="check sp-archivo">
                      <input type="checkbox" checked={!!marcados[k]} onChange={(e) => setMarcados((m) => ({ ...m, [k]: e.target.checked }))} />
                      <span>{a.nombre}{a.sugerido && <span className="badge al-REPORTADA" style={{ marginLeft: 6 }}>del periodo</span>}</span>
                      <span className="tenue">{fechaHora(a.modificado)} · {peso(a.tamano)}</span>
                    </label>
                  );
                })}
              </div>
            ))}
          </div>
        </>
      )}
    </Modal>
  );
}
