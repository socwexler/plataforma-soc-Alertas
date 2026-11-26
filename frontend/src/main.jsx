import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Inicio from "./pages/Inicio";
import Casos from "./pages/Casos";
import CasoForm from "./pages/CasoForm";
import CasoDetalle from "./pages/CasoDetalle";
import BaseConocimiento from "./pages/BaseConocimiento";
import Clientes from "./pages/Clientes";
import Usuarios from "./pages/Usuarios";
import Cambios from "./pages/Cambios";
import Configuracion from "./pages/Configuracion";
import Importar from "./pages/Importar";
import Tablero from "./pages/Tablero";
import Sla from "./pages/Sla";
import Alertas from "./pages/Alertas";
import Informes from "./pages/Informes";
import InformeEditor from "./pages/InformeEditor";
import Presentacion from "./pages/Presentacion";
import "./styles.css";

function Rutas() {
  const { usuario, cargando, puede } = useAuth();
  if (cargando) return <div className="vacio">Cargando…</div>;
  if (!usuario) return <Login />;
  return (
    <Routes>
      {puede("informes.ver") && <Route path="informes/:id/presentacion" element={<Presentacion />} />}
      <Route element={<Layout />}>
        <Route index element={puede("tablero.ver") ? <Inicio /> : <Navigate to={puede("casos.crear") ? "/casos/nuevo" : "/casos"} replace />} />
        {puede("tablero.ver") && <Route path="tablero" element={<Tablero />} />}
        {puede("tablero.ver") && <Route path="sla" element={<Sla />} />}
        <Route path="alertas" element={<Alertas />} />
        <Route path="casos" element={<Casos />} />
        {puede("casos.crear") && <Route path="casos/nuevo" element={<CasoForm />} />}
        <Route path="casos/:id" element={<CasoDetalle />} />
        {puede("casos.crear") && <Route path="casos/:id/editar" element={<CasoForm />} />}
        {puede("kb.ver") && <Route path="conocimiento" element={<BaseConocimiento />} />}
        {puede("informes.ver") && <Route path="informes" element={<Informes />} />}
        {puede("informes.ver") && <Route path="informes/:id" element={<InformeEditor />} />}
        {puede("clientes.admin") && <Route path="clientes" element={<Clientes />} />}
        {puede("importar") && <Route path="importar" element={<Importar />} />}
        {puede("usuarios.admin") && <Route path="usuarios" element={<Usuarios />} />}
        {puede("usuarios.admin") && <Route path="cambios" element={<Cambios />} />}
        {puede("config.admin") && <Route path="configuracion" element={<Configuracion />} />}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider><Rutas /></AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);
