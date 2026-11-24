import { useRef, useState } from "react";
import { ESTADOS } from "../util";
import { imagenesPegadas, peso, TIPOS_GESTION } from "./Adjuntos";
import { Campo, Confirmar } from "./Ui";

/** Cambia el estado del caso con su soporte. Si el estado es el actual, solo agrega archivos. */
export default function CambioEstado({ caso, estado, onAceptar, onCerrar }) {
  const [comentario, setComentario] = useState("");
  const [archivos, setArchivos] = useState([]);
  const [encima, setEncima] = useState(false);
  const entrada = useRef(null);
  const mismo = estado === caso.estado;
  const agregar = (lista) => { const n = [...lista]; if (n.length) setArchivos((l) => [...l, ...n]); };   // copiar antes: al limpiar la entrada la lista queda vacía

  return (
    <Confirmar titulo={mismo ? `Agregar evidencia · ${caso.numero}` : `${caso.numero}: ${ESTADOS[caso.estado]} → ${ESTADOS[estado]}`}
               boton={mismo ? "Agregar evidencia" : "Cambiar estado"} listo={!mismo || archivos.length > 0}
               onCerrar={onCerrar} onAceptar={() => onAceptar(comentario, archivos)}>
      <div onPaste={(e) => { const i = imagenesPegadas(e); if (i.length) { e.preventDefault(); agregar(i); } }}>
        <Campo etiqueta="Detalle" ayuda="opcional">
          <textarea rows={3} maxLength={4000} autoFocus value={comentario} onChange={(e) => setComentario(e.target.value)}
                    placeholder="Ej.: el cliente confirma que es una actividad autorizada" />
        </Campo>
        <input ref={entrada} type="file" multiple accept={TIPOS_GESTION} hidden onChange={(e) => { agregar(e.target.files); e.target.value = ""; }} />
        <div className={`soltar ${encima ? "encima" : ""}`} onDragOver={(e) => { e.preventDefault(); setEncima(true); }} onDragLeave={() => setEncima(false)}
             onDrop={(e) => { e.preventDefault(); setEncima(false); agregar(e.dataTransfer.files); }}>
          <button type="button" className="btn chico primario" onClick={() => entrada.current.click()}>+ Evidencias</button>
          <span className="tenue">Correo (.msg o .eml), imagen o documento{mismo ? "" : " · opcional"}. También puede arrastrarlos aquí o pegar un recorte con Ctrl+V.</span>
        </div>
        {archivos.map((a, i) => (
          <div key={i} className="adjunto">
            <span className="mini ext">{a.name.split(".").pop().toUpperCase()}</span>
            <div style={{ flex: 1, minWidth: 0, overflowWrap: "anywhere" }}>{a.name}<div className="tenue" style={{ fontSize: 12 }}>{peso(a.size)}</div></div>
            <button type="button" className="btn chico peligro" onClick={() => setArchivos((l) => l.filter((_, k) => k !== i))}>Quitar</button>
          </div>
        ))}
        <p className="tenue" style={{ margin: "10px 0 0", fontSize: 13 }}>Queda en el seguimiento del caso con su nombre. Los archivos son internos: no van en la plantilla ni en el correo al cliente.</p>
      </div>
    </Confirmar>
  );
}
