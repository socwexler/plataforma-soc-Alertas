import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { token } from "../api";

/** Presentación HTML del informe a pantalla completa (la genera el servidor con la identidad Wexler). */
export default function Presentacion() {
  const { id } = useParams();
  const [sp] = useSearchParams();
  const estilo = sp.get("estilo") === "ejecutiva" ? "ejecutiva" : "interactiva";
  const [html, setHtml] = useState(null);
  const [error, setError] = useState(null);
  const marco = useRef(null);

  useEffect(() => {
    fetch(`/api/informes/${id}/presentacion?estilo=${estilo}`, { headers: { Authorization: `Bearer ${token.get()}` } })
      .then(async (r) => { if (!r.ok) throw new Error(`Error ${r.status}`); setHtml(await r.text()); })
      .catch(setError);
  }, [id, estilo]);

  return (
    <div style={{ position: "fixed", inset: 0, background: "#05070f" }}>
      {error && <div className="alerta error" style={{ margin: 20 }}>No se pudo cargar la presentación: {error.message}</div>}
      {!html && !error && <div className="vacio" style={{ color: "#ccc" }}>Generando presentación…</div>}
      {html && <iframe ref={marco} onLoad={() => marco.current?.contentWindow?.focus()} title="Presentación" srcDoc={html} allow="fullscreen" style={{ border: 0, width: "100%", height: "100%" }} />}
      <Link to={`/informes/${id}`} className="volver-pres">← Volver al informe</Link>
    </div>
  );
}
