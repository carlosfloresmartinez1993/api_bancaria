import { useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";

/**
 * Tras cualquier cambio de dinero (movimiento, salida, % de terminal) hay que refrescar
 * saldos y reportes, porque todos se calculan a partir de esos registros.
 */
export function useInvalidarDinero() {
  const qc = useQueryClient();
  return useCallback(() => {
    for (const key of ["movimientos", "salidas", "reporte", "saldo", "terminales", "porcentajes"]) {
      qc.invalidateQueries({ queryKey: [key] });
    }
  }, [qc]);
}
