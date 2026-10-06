import type { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router";
import { useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { Cargando } from "./components/ui";
import Login from "./pages/Login";
import Inicio from "./pages/Inicio";
import Empresas from "./pages/Empresas";
import EmpresaDetalle from "./pages/EmpresaDetalle";
import Clientes from "./pages/Clientes";
import ClienteDetalle from "./pages/ClienteDetalle";
import MetodosPago from "./pages/MetodosPago";
import Movimientos from "./pages/Movimientos";
import Salidas from "./pages/Salidas";
import Reportes from "./pages/Reportes";
import Usuarios from "./pages/Usuarios";
import Perfil from "./pages/Perfil";

function Protegida({ children, soloAdmin = false }: { children: ReactNode; soloAdmin?: boolean }) {
  const { usuario, cargando, esAdmin } = useAuth();
  const location = useLocation();
  if (cargando) return <div className="min-h-dvh"><Cargando texto="Verificando sesión…" /></div>;
  if (!usuario) return <Navigate to="/login" replace state={{ desde: location.pathname }} />;
  if (soloAdmin && !esAdmin) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <Protegida>
            <Layout />
          </Protegida>
        }
      >
        <Route index element={<Inicio />} />
        <Route path="empresas" element={<Empresas />} />
        <Route path="empresas/:id" element={<EmpresaDetalle />} />
        <Route path="clientes" element={<Clientes />} />
        <Route path="clientes/:id" element={<ClienteDetalle />} />
        <Route path="terminales" element={<Navigate to="/clientes" replace />} />
        <Route path="movimientos" element={<Movimientos />} />
        <Route path="salidas" element={<Salidas />} />
        <Route path="reportes" element={<Reportes />} />
        <Route path="usuarios" element={<Protegida soloAdmin><Usuarios /></Protegida>} />
        <Route path="metodos-pago" element={<Protegida soloAdmin><MetodosPago /></Protegida>} />
        <Route path="perfil" element={<Perfil />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
