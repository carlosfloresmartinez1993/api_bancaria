import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { api } from "./api";
import type { Empresa, MetodoPago, Pagina, Proyecto, Terminal, Usuario } from "./types";

// Catálogos que se usan en filtros y selectores. El backend permite hasta 500 por página.

export function useEmpresasCatalogo() {
  return useQuery({
    queryKey: ["empresas", "catalogo"],
    queryFn: () => api.get<Pagina<Empresa>>("/empresas", { limit: 500 }),
    select: (p) => p.items,
    staleTime: 60_000,
  });
}

/** Clientes (terminales), opcionalmente de una sola empresa. */
export function useTerminalesCatalogo(empresaId?: string) {
  return useQuery({
    queryKey: ["terminales", "catalogo", empresaId ?? "todas"],
    queryFn: () => api.get<Pagina<Terminal>>("/terminales", { limit: 500, empresa_id: empresaId }),
    select: (p) => p.items,
    staleTime: 60_000,
  });
}

/** Proyectos, opcionalmente de una empresa o de un cliente. */
export function useProyectosCatalogo(filtro: { empresaId?: string; terminalId?: string } = {}) {
  return useQuery({
    queryKey: ["proyectos", "catalogo", filtro.empresaId ?? "", filtro.terminalId ?? ""],
    queryFn: () =>
      api.get<Pagina<Proyecto>>("/proyectos", {
        limit: 500,
        empresa_id: filtro.empresaId || undefined,
        terminal_id: filtro.terminalId || undefined,
      }),
    select: (p) => p.items,
    staleTime: 60_000,
  });
}

export function useMetodosPago(incluirInactivos = false) {
  return useQuery({
    queryKey: ["metodos-pago", incluirInactivos],
    queryFn: () => api.get<MetodoPago[]>("/metodos-pago", { incluir_inactivos: incluirInactivos || undefined }),
    staleTime: 5 * 60_000,
  });
}

/** Solo admin: la ruta /usuarios es exclusiva de administradores. */
export function useUsuariosCatalogo() {
  const { esAdmin } = useAuth();
  return useQuery({
    queryKey: ["usuarios", "catalogo"],
    queryFn: () => api.get<Pagina<Usuario>>("/usuarios", { limit: 500 }),
    select: (p) => p.items,
    enabled: esAdmin,
    staleTime: 60_000,
  });
}

// Mapas id → nombre, para mostrar nombres en tablas que solo traen el id.

export function useNombresEmpresa(): Map<string, string> {
  const { data } = useEmpresasCatalogo();
  return new Map((data ?? []).map((e) => [e.id, e.nombre]));
}

export function useNombresTerminal(): Map<string, string> {
  const { data } = useTerminalesCatalogo();
  return new Map((data ?? []).map((t) => [t.id, t.identificador_terminal]));
}

export function useNombresProyecto(): Map<string, string> {
  const { data } = useProyectosCatalogo();
  return new Map((data ?? []).map((p) => [p.id, p.nombre]));
}

export function useNombresMetodoPago(): Map<string, string> {
  const { data } = useMetodosPago(true);
  return new Map((data ?? []).map((m) => [m.id, m.nombre]));
}

export function useNombresUsuario(): Map<string, string> {
  const { data } = useUsuariosCatalogo();
  return new Map((data ?? []).map((u) => [u.id, `${u.nombre} ${u.apellidos}`]));
}
