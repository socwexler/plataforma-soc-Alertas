import { useEffect, useRef, useState } from "react";
import { num } from "../util";

// Paleta validada (validate_palette.js, modo claro): orden de severidad Baja → Crítica
export const COLOR_CRIT = { Baja: "#2a78d6", Media: "#eda100", Alta: "#e34948", Crítica: "#9b2f6e", Sin: "#a3a8b0" };
export const SERIE = "#2a78d6";

function useAncho() {
  const ref = useRef(null);
  const [ancho, setAncho] = useState(600);
  useEffect(() => {
    if (!ref.current) return undefined;
    const ro = new ResizeObserver(([e]) => setAncho(Math.max(240, Math.floor(e.contentRect.width))));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, ancho];
}

function escala(max) {
  if (max <= 0) return { tope: 4, pasos: [0, 1, 2, 3, 4] };
  const crudo = max / 4;
  const mag = 10 ** Math.floor(Math.log10(crudo));
  const paso = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((p) => p >= crudo);
  return { tope: paso * 4, pasos: [0, 1, 2, 3, 4].map((i) => i * paso) };
}

/** Camino de una barra vertical con las esquinas superiores redondeadas (4px). */
function barra(x, y, w, h, r = 4) {
  if (h <= 0) return "";
  const rr = Math.min(r, w / 2, h);
  return `M${x},${y + h}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h}Z`;
}

function Tooltip({ t }) {
  if (!t) return null;
  return (
    <div className="viz-tooltip" style={{ left: t.x, top: t.y }}>
      <b>{t.titulo}</b>
      {t.filas.map(([color, etq, v]) => (
        <div key={etq} className="viz-tt-fila">
          {color && <span className="viz-punto" style={{ background: color }} />}<span>{etq}</span><b>{v}</b>
        </div>
      ))}
    </div>
  );
}

/**
 * Columnas (opcionalmente apiladas).
 * datos: [{etiqueta, titulo?, valores: {serie: n}}]; series: [{clave, nombre, color}] de abajo hacia arriba.
 */
export function Columnas({ datos, series, alto = 220, etiquetaCada = 1, formatoEje = (v) => num(v) }) {
  const [ref, ancho] = useAncho();
  const [tt, setTt] = useState(null);
  const m = { izq: 40, der: 8, arr: 10, aba: 26 };
  const w = ancho - m.izq - m.der;
  const h = alto - m.arr - m.aba;
  const totales = datos.map((d) => series.reduce((a, s) => a + (d.valores[s.clave] || 0), 0));
  const { tope, pasos } = escala(Math.max(0, ...totales));
  const banda = w / Math.max(datos.length, 1);
  const bw = Math.max(2, Math.min(36, banda * 0.68));
  const y = (v) => h - (v / tope) * h;

  return (
    <div className="viz" ref={ref} onMouseLeave={() => setTt(null)}>
      <svg width={ancho} height={alto} role="img">
        <g transform={`translate(${m.izq},${m.arr})`}>
          {pasos.map((p) => (
            <g key={p}>
              <line x1={0} x2={w} y1={y(p)} y2={y(p)} className={p === 0 ? "viz-base" : "viz-grid"} />
              <text x={-8} y={y(p)} dy="0.32em" textAnchor="end" className="viz-eje">{formatoEje(p)}</text>
            </g>
          ))}
          {datos.map((d, i) => {
            const x = i * banda + (banda - bw) / 2;
            let acum = 0;
            const visibles = series.filter((s) => (d.valores[s.clave] || 0) > 0);
            const ultima = visibles[visibles.length - 1]?.clave;
            return (
              <g key={d.etiqueta + i}>
                {visibles.map((s) => {
                  const v = d.valores[s.clave];
                  const y0 = y(acum + v);
                  const alto_ = y(acum) - y0 - (acum > 0 ? 2 : 0); // 2px de separación entre segmentos
                  acum += v;
                  return s.clave === ultima
                    ? <path key={s.clave} d={barra(x, y0, bw, alto_)} fill={s.color} />
                    : <rect key={s.clave} x={x} y={y0} width={bw} height={Math.max(0, alto_)} fill={s.color} />;
                })}
                <rect x={i * banda} y={0} width={banda} height={h} fill="transparent"
                  onMouseMove={(e) => {
                    const caja = ref.current.getBoundingClientRect();
                    setTt({
                      x: Math.min(e.clientX - caja.left + 12, ancho - 190), y: e.clientY - caja.top + 12,
                      titulo: d.titulo || d.etiqueta,
                      filas: [...series].reverse().map((s) => [series.length > 1 ? s.color : null, s.nombre, num(d.valores[s.clave] || 0)])
                        .concat(series.length > 1 ? [[null, "Total", num(totales[i])]] : []),
                    });
                  }} />
                {i % etiquetaCada === 0 && (
                  <text x={i * banda + banda / 2} y={h + 16} textAnchor="middle" className="viz-eje">{d.etiqueta}</text>
                )}
              </g>
            );
          })}
        </g>
      </svg>
      <Tooltip t={tt} />
    </div>
  );
}

export function Leyenda({ series }) {
  return (
    <div className="viz-leyenda">
      {series.map((s) => <span key={s.clave}><span className="viz-punto" style={{ background: s.color }} />{s.nombre}</span>)}
    </div>
  );
}

/** Barras horizontales con etiqueta arriba y valor directo al final. */
export function BarrasH({ datos, color = SERIE, formato = num, onClick }) {
  const max = Math.max(1, ...datos.map((d) => d.valor));
  return (
    <div className="viz-barras">
      {datos.map((d) => (
        <div key={d.etiqueta} className={`viz-bh ${onClick ? "click" : ""}`} onClick={onClick ? () => onClick(d) : undefined}
             title={`${d.etiqueta}: ${formato(d.valor)}`}>
          <div className="viz-bh-etq"><span>{d.etiqueta}</span><b>{formato(d.valor)}</b></div>
          <div className="viz-bh-pista"><div style={{ width: `${(d.valor / max) * 100}%`, background: d.color || color }} /></div>
        </div>
      ))}
    </div>
  );
}

/** Barra fina dentro de una celda de tabla. */
export function BarraCelda({ valor, max, color = SERIE }) {
  return (
    <div className="viz-celda"><div style={{ width: `${max ? (valor / max) * 100 : 0}%`, background: color }} /></div>
  );
}
