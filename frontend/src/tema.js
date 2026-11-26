import { useEffect, useState } from "react";

// Modo día/noche. Se guarda solo en este navegador; sin elección se sigue el del sistema.
// index.html lo aplica antes de cargar la página para que no parpadee.
const CLAVE = "soc_tema";
const guardado = () => { try { return localStorage.getItem(CLAVE); } catch { return null; } };
const sistema = () => (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "oscuro" : "claro");
const aplicar = (t) => { document.documentElement.dataset.tema = t; };

export function useTema() {
  const [tema, setTema] = useState(() => guardado() || sistema());
  useEffect(() => { aplicar(tema); }, [tema]);
  useEffect(() => {
    const m = window.matchMedia?.("(prefers-color-scheme: dark)");
    const cambio = () => { if (!guardado()) setTema(sistema()); };
    m?.addEventListener("change", cambio);
    return () => m?.removeEventListener("change", cambio);
  }, []);
  const alternar = () => setTema((t) => {
    const n = t === "oscuro" ? "claro" : "oscuro";
    try { localStorage.setItem(CLAVE, n); } catch { /* sin almacenamiento */ }
    return n;
  });
  return [tema, alternar];
}
