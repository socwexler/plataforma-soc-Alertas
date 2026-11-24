import { useEffect, useMemo, useRef, useState } from "react";
import { clave, ESTADOS, REVISIONES } from "../util";

export const Crit = ({ v }) => (v ? <span className={`badge crit-${v}`}>{v}</span> : <span className="tenue">—</span>);
export const Estado = ({ v }) => <span className={`badge est-${v}`}>{ESTADOS[v] || v}</span>;

export const Revision = ({ v }) => (v ? <span className={`badge rev-${v}`}>{REVISIONES[v]}</span> : <span className="tenue">No requiere</span>);

export function Campo({ etiqueta, ayuda, className = "", children }) {
  return (
    <label className={`campo ${className}`}>
      <span>{etiqueta}{ayuda && <span className="ayuda"> · {ayuda}</span>}</span>
      {children}
    </label>
  );
}

export function MsgError({ e }) {
  if (!e) return null;
  return <div className="alerta error">{e.message || String(e)}</div>;
}

export function Paginador({ total, pagina, tamano, onCambio }) {
  const paginas = Math.max(1, Math.ceil(total / tamano));
  const desde = total ? (pagina - 1) * tamano + 1 : 0;
  const hasta = Math.min(total, pagina * tamano);
  return (
    <div className="paginador">
      <span>{desde}–{hasta} de {total.toLocaleString("es-CO")}</span>
      <div className="btns">
        <button className="btn chico" disabled={pagina <= 1} onClick={() => onCambio(pagina - 1)}>Anterior</button>
        <span style={{ alignSelf: "center" }}>Página {pagina} de {paginas}</span>
        <button className="btn chico" disabled={pagina >= paginas} onClick={() => onCambio(pagina + 1)}>Siguiente</button>
      </div>
    </div>
  );
}

export function Modal({ titulo, onCerrar, children, pie }) {
  useEffect(() => {
    const esc = (e) => e.key === "Escape" && onCerrar();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onCerrar]);
  return (
    <div className="modal-fondo" onMouseDown={(e) => e.target === e.currentTarget && onCerrar()}>
      <div className="modal" role="dialog" aria-label={titulo}>
        <h2>{titulo}</h2>
        {children}
        {pie && <div className="pie">{pie}</div>}
      </div>
    </div>
  );
}

/** Pide confirmación y ejecuta. Si falla, muestra el motivo sin cerrar. */
export function Confirmar({ titulo, boton, peligro, listo = true, onAceptar, onCerrar, children }) {
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const aceptar = async () => {
    setOcupado(true); setError(null);
    try { await onAceptar(); } catch (e) { setError(e); setOcupado(false); }
  };
  return (
    <Modal titulo={titulo} onCerrar={onCerrar} pie={<>
      <button className="btn" onClick={onCerrar}>Cancelar</button>
      <button className={`btn ${peligro ? "peligro" : "primario"}`} disabled={ocupado || !listo} onClick={aceptar}>{boton}</button>
    </>}>
      <MsgError e={error} />
      {children}
    </Modal>
  );
}

/** Botones Editar / Deshabilitar / Eliminar de una fila. uso: historial que impide eliminar. */
export function AccionesFila({ activo, uso, onEditar, onEstado, onEliminar }) {
  const alto = (fn) => (e) => { e.stopPropagation(); fn(); };
  return (
    <div className="acciones fila">
      <button className="btn chico" onClick={alto(onEditar)}>Editar</button>
      {onEstado && <button className="btn chico" onClick={alto(onEstado)}>{activo ? "Deshabilitar" : "Habilitar"}</button>}
      {onEliminar && <button className="btn chico peligro" disabled={!!uso} title={uso ? `No se puede eliminar: tiene ${uso}. Deshabilítelo.` : undefined} onClick={alto(onEliminar)}>Eliminar</button>}
    </div>
  );
}

/** Selector con búsqueda. opciones: [{id, nombre, ...}] */
export function Combo({ opciones, valor, onCambio, placeholder, render, max = 40 }) {
  const [abierto, setAbierto] = useState(false);
  const [texto, setTexto] = useState("");
  const [activo, setActivo] = useState(0);
  const caja = useRef(null);
  const sel = opciones.find((o) => o.id === valor);

  useEffect(() => {
    const fuera = (e) => caja.current && !caja.current.contains(e.target) && setAbierto(false);
    document.addEventListener("mousedown", fuera);
    return () => document.removeEventListener("mousedown", fuera);
  }, []);

  const filtradas = useMemo(() => {
    const palabras = clave(texto).split(/\s+/).filter(Boolean);
    const r = palabras.length ? opciones.filter((o) => { const k = clave(o.nombre); return palabras.every((p) => k.includes(p)); }) : opciones;
    return r.slice(0, max);
  }, [texto, opciones, max]);

  const elegir = (o) => { onCambio(o); setAbierto(false); setTexto(""); };

  return (
    <div className="combo" ref={caja}>
      <input
        value={abierto ? texto : sel?.nombre || ""}
        placeholder={placeholder}
        onFocus={() => { setAbierto(true); setActivo(0); }}
        onChange={(e) => { setTexto(e.target.value); setAbierto(true); setActivo(0); }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setActivo((a) => Math.min(a + 1, filtradas.length - 1)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setActivo((a) => Math.max(a - 1, 0)); }
          if (e.key === "Enter" && abierto && filtradas[activo]) { e.preventDefault(); elegir(filtradas[activo]); }
          if (e.key === "Escape") setAbierto(false);
        }}
      />
      {abierto && (
        <div className="combo-lista">
          {filtradas.length === 0 && <div className="combo-op tenue">Sin resultados</div>}
          {filtradas.map((o, i) => (
            <div key={o.id} className={`combo-op ${i === activo ? "activo" : ""}`}
                 onMouseDown={(e) => { e.preventDefault(); elegir(o); }} onMouseEnter={() => setActivo(i)}>
              {render ? render(o) : o.nombre}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function Dato({ t, children, className = "" }) {
  return (
    <div className={`dato ${className}`}>
      <h3>{t}</h3>
      <div className="v">{children ?? <span className="tenue">—</span>}</div>
    </div>
  );
}
