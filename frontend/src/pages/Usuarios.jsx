import { useEffect, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Link } from "react-router-dom";
import { AccionesFila, Campo, Confirmar, Modal, MsgError } from "../components/Ui";
import { clave, ROLES } from "../util";

const NUEVO = { usuario: "", nombre: "", email: "", rol: "N1", activo: true, password: "" };

export default function Usuarios() {
  const { usuario, puede } = useAuth();
  const esAdmin = puede("sistema.admin");
  const editable = (u) => esAdmin || u.rol !== "ADMIN";
  const [lista, setLista] = useState([]);
  const [editar, setEditar] = useState(null);
  const [error, setError] = useState(null);
  const [confirmar, setConfirmar] = useState(null);  // { tipo: "estado" | "eliminar", u }
  const [filtro, setFiltro] = useState({ q: "", estado: "" });
  const visibles = lista.filter((u) => (!filtro.estado || u.activo === (filtro.estado === "activos"))
    && clave(`${u.nombre} ${u.usuario} ${u.email || ""} ${ROLES[u.rol]}`).includes(clave(filtro.q)));
  const ejecutar = async () => {
    const { tipo, u } = confirmar;
    if (tipo === "eliminar") await api(`/usuarios/${u.id}`, { metodo: "DELETE" });
    else await api(`/usuarios/${u.id}/estado`, { metodo: "PATCH", datos: { activo: !u.activo } });
    setConfirmar(null);
    cargar();
  };

  const cargar = () => api("/usuarios").then(setLista).catch(setError);
  useEffect(() => { cargar(); }, []);
  const set = (k) => (e) => setEditar((x) => ({ ...x, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  const guardar = async () => {
    setError(null);
    const d = { ...editar, email: editar.email || null, password: editar.password || null };
    try {
      if (d.id) await api(`/usuarios/${d.id}`, { metodo: "PUT", datos: d });
      else await api("/usuarios", { metodo: "POST", datos: d });
      setEditar(null);
      cargar();
    } catch (e) { setError(e); }
  };

  return (
    <>
      <div className="cabecera">
        <div><h1>Usuarios</h1><p>Los analistas importados de la bitácora no pueden ingresar hasta que se les asigne una contraseña.</p></div>
        <div className="acciones">
          <Link className="btn" to="/cambios">Registro de cambios</Link>
          <button className="btn primario" onClick={() => { setError(null); setEditar({ ...NUEVO }); }}>+ Nuevo usuario</button>
        </div>
      </div>
      <MsgError e={!editar && error} />
      <div className="panel">
        <div className="filtros">
          <Campo etiqueta="Buscar" className="busqueda"><input value={filtro.q} onChange={(e) => setFiltro((f) => ({ ...f, q: e.target.value }))} placeholder="Nombre, usuario, correo o rol" /></Campo>
          <Campo etiqueta="Estado"><select value={filtro.estado} onChange={(e) => setFiltro((f) => ({ ...f, estado: e.target.value }))}>
            <option value="">Todos</option><option value="activos">Habilitados</option><option value="inactivos">Deshabilitados</option>
          </select></Campo>
        </div>
        <div className="tabla-scroll">
        <table className="tabla">
          <thead><tr><th>Nombre</th><th>Usuario</th><th>Rol</th><th>Correo</th><th>Acceso</th><th>Acciones</th></tr></thead>
          <tbody>
            {visibles.map((u) => (
              <tr key={u.id} className={u.activo ? "" : "inactiva"}>
                <td>{u.nombre}</td>
                <td className="mono">{u.usuario}</td>
                <td>{ROLES[u.rol]}</td>
                <td>{u.email || "—"}</td>
                <td>{!u.activo ? <span className="badge etq">Deshabilitado</span> : u.puede_ingresar ? "Habilitado" : <span className="badge crit-Media">Sin contraseña</span>}</td>
                <td>{!editable(u) ? <span className="tenue">Solo un administrador</span> : (
                  <AccionesFila activo={u.activo} uso={u.uso}
                    onEditar={() => { setError(null); setEditar({ ...NUEVO, ...u, email: u.email || "", password: "" }); }}
                    onEstado={u.id === usuario.id ? null : () => setConfirmar({ tipo: "estado", u })}
                    onEliminar={u.id === usuario.id ? null : () => setConfirmar({ tipo: "eliminar", u })} />
                )}</td>
              </tr>
            ))}
            {!visibles.length && <tr><td colSpan={6} className="vacio">Sin resultados.</td></tr>}
          </tbody>
        </table>
        </div>
        <p className="tenue" style={{ margin: "10px 0 0" }}>Solo se elimina un usuario sin casos, seguimientos ni importaciones. Los demás se deshabilitan: no pueden ingresar y su historial se conserva.</p>
      </div>
      {confirmar && (
        <Confirmar peligro={confirmar.tipo === "eliminar" || confirmar.u.activo} onCerrar={() => setConfirmar(null)} onAceptar={ejecutar}
                   titulo={`${confirmar.tipo === "eliminar" ? "Eliminar" : confirmar.u.activo ? "Deshabilitar" : "Habilitar"} a ${confirmar.u.nombre}`}
                   boton={confirmar.tipo === "eliminar" ? "Eliminar" : confirmar.u.activo ? "Deshabilitar" : "Habilitar"}>
          <p style={{ margin: 0 }}>{confirmar.tipo === "eliminar" ? "Se borra el usuario y no se puede recuperar."
            : confirmar.u.activo ? "No podrá ingresar y, si tiene una sesión abierta, se le cerrará. Sus casos e historial no cambian y puede habilitarlo de nuevo."
              : confirmar.u.puede_ingresar ? "Podrá ingresar otra vez con su contraseña anterior y el mismo rol." : "Quedará habilitado, pero no podrá ingresar hasta que le asigne una contraseña."}</p>
        </Confirmar>
      )}
      {editar && (
        <Modal titulo={editar.id ? `Editar ${editar.nombre}` : "Nuevo usuario"} onCerrar={() => setEditar(null)} pie={<>
          <button className="btn" onClick={() => setEditar(null)}>Cancelar</button>
          <button className="btn primario" onClick={guardar}>Guardar</button>
        </>}>
          <MsgError e={error} />
          <div className="grid g2">
            <Campo etiqueta="Nombre completo"><input value={editar.nombre} onChange={set("nombre")} /></Campo>
            <Campo etiqueta="Usuario"><input value={editar.usuario} onChange={set("usuario")} autoComplete="off" /></Campo>
            <Campo etiqueta="Correo"><input type="email" value={editar.email} onChange={set("email")} /></Campo>
            <Campo etiqueta="Rol">
              <select value={editar.rol} onChange={set("rol")} disabled={editar.id === usuario.id}>{Object.entries(ROLES).filter(([k]) => esAdmin || k !== "ADMIN").map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
            </Campo>
            <Campo etiqueta={editar.id ? "Nueva contraseña" : "Contraseña"} ayuda={editar.id ? "vacío = no cambiar" : "mínimo 8 caracteres"}>
              <input type="password" value={editar.password} onChange={set("password")} autoComplete="new-password" />
            </Campo>
            <label className="check" style={{ alignSelf: "end" }}><input type="checkbox" checked={editar.activo} onChange={set("activo")} /> Usuario activo</label>
          </div>
        </Modal>
      )}
    </>
  );
}
