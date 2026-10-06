import { useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";

/**
 * Tras cualquier cambio de dinero (entrada, salida, % de proyecto) o de estructura
 * (cliente, proyecto) hay que refrescar saldos, catálogos y reportes, porque todos
 * se calculan a partir de esos registros.
 */
export function useInvalidarDinero() {
  const qc = useQueryClient();
  return useCallback(() => {
    for (const key of ["movimientos", "salidas", "reporte", "saldo", "terminales", "proyectos", "porcentajes", "empresas"]) {
      qc.invalidateQueries({ queryKey: [key] });
    }
  }, [qc]);
}
