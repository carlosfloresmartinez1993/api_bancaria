import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { api } from "./api";
import type { Empresa, Pagina, Terminal, Usuario } from "./types";

// Catálogos que se usan en filtros y selectores. El backend permite hasta 500 por página.

export function useEmpresasCatalogo() {
  return useQuery({
    queryKey: ["empresas", "catalogo"],
    queryFn: () => api.get<Pagina<Empresa>>("/empresas", { limit: 500 }),
    select: (p) => p.items,
    staleTime: 60_000,
  });
}

export function useTerminalesCatalogo(empresaId?: string) {
  return useQuery({
    queryKey: ["terminales", "catalogo", empresaId ?? "todas"],
    queryFn: () => api.get<Pagina<Terminal>>("/terminales", { limit: 500, empresa_id: empresaId }),
    select: (p) => p.items,
    staleTime: 60_000,
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

/** Mapa id → nombre de empresa, para mostrar nombres en tablas que solo traen el id. */
export function useNombresEmpresa(): Map<string, string> {
  const { data } = useEmpresasCatalogo();
  return new Map((data ?? []).map((e) => [e.id, e.nombre]));
}

export function useNombresTerminal(): Map<string, string> {
  const { data } = useTerminalesCatalogo();
  return new Map((data ?? []).map((t) => [t.id, t.identificador_terminal]));
}

export function useNombresUsuario(): Map<string, string> {
  const { data } = useUsuariosCatalogo();
  return new Map((data ?? []).map((u) => [u.id, `${u.nombre} ${u.apellidos}`]));
}
