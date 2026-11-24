import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, token } from "./api";

const Ctx = createContext(null);

export function AuthProvider({ children }) {
  const [usuario, setUsuario] = useState(null);
  const [cargando, setCargando] = useState(true);

  const cargar = useCallback(async () => {
    if (!token.get()) { setUsuario(null); setCargando(false); return; }
    try { setUsuario(await api("/auth/yo")); } catch { setUsuario(null); }
    setCargando(false);
  }, []);

  useEffect(() => {
    cargar();
    const salir = () => setUsuario(null);
    window.addEventListener("sesion-vencida", salir);
    return () => window.removeEventListener("sesion-vencida", salir);
  }, [cargar]);

  const entrar = async (usuario, password) => {
    const r = await api("/auth/login", { metodo: "POST", form: { username: usuario, password } });
    token.set(r.access_token);
    await cargar();
  };
  const salir = () => { token.borrar(); setUsuario(null); };
  // los permisos de cada rol los define el servidor (/auth/yo)
  const puede = (permiso) => !!usuario?.permisos?.includes(permiso);

  return <Ctx.Provider value={{ usuario, cargando, entrar, salir, puede }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
