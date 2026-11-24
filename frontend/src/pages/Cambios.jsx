import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Campo, MsgError, Paginador } from "../components/Ui";
import { fechaHora } from "../util";

const ACCION = { crear: "Creó", editar: "Modificó", deshabilitar: "Deshabilitó", habilitar: "Habilitó", eliminar: "Eliminó", anular: "Anuló", restaurar: "Restauró" };

export default function Cambios() {
  const [q, setQ] = useState("");
  const [pagina, setPagina] = useState(1);
  const [datos, setDatos] = useState({ total: 0, items: [] });
  const [error, setError] = useState(null);
  useEffect(() => {
    const t = setTimeout(() => api("/usuarios/cambios", { params: { q, pagina } }).then(setDatos).catch(setError), 250);
    return () => clearTimeout(t);
  }, [q, pagina]);
  return (
    <>
      <div className="cabecera">
        <div><h1>Registro de cambios</h1><p>Quién creó, modificó, deshabilitó o eliminó usuarios, clientes, casos de uso e informes, y quién anuló casos. Solo lectura.</p></div>
        <Link className="btn" to="/usuarios">Volver a usuarios</Link>
      </div>
      <MsgError e={error} />
      <div className="panel">
        <div className="filtros"><Campo etiqueta="Buscar" className="busqueda"><input value={q} onChange={(e) => { setQ(e.target.value); setPagina(1); }} placeholder="Persona, usuario, cliente, caso de uso…" /></Campo></div>
        <div className="tabla-scroll">
          <table className="tabla">
            <thead><tr><th>Fecha</th><th>Quién</th><th>Acción</th><th>Detalle</th></tr></thead>
            <tbody>
              {datos.items.map((a) => (
                <tr key={a.id}>
                  <td style={{ whiteSpace: "nowrap" }}>{fechaHora(a.creado_en)}</td>
                  <td>{a.usuario}</td>
                  <td>{ACCION[a.accion] || a.accion} {a.objeto}</td>
                  <td style={{ overflowWrap: "anywhere" }}>{a.detalle || "—"}</td>
                </tr>
              ))}
              {!datos.items.length && <tr><td colSpan={4} className="vacio">Sin cambios registrados.</td></tr>}
            </tbody>
          </table>
        </div>
        <Paginador total={datos.total} pagina={pagina} tamano={50} onCambio={setPagina} />
      </div>
    </>
  );
}
