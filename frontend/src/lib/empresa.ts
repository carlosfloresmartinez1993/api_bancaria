/**
 * Valor especial para elegir "Sin empresa" en los selectores de empresa.
 * La API lo recibe como sin_empresa=true (los ids de empresa son UUID).
 */
export const SIN_EMPRESA = "sin";
export const TEXTO_SIN_EMPRESA = "Sin empresa";

/** Traduce el valor de un selector de empresa a los parámetros de la API. */
export function filtroEmpresa(valor: string | undefined | null): { empresa_id?: string; sin_empresa?: boolean } {
  if (!valor) return {};
  if (valor === SIN_EMPRESA) return { sin_empresa: true };
  return { empresa_id: valor };
}

/** Nombre a mostrar para el empresa_id de un registro (null = sin empresa). */
export function nombreEmpresa(nombres: Map<string, string>, empresaId: string | null | undefined): string {
  if (!empresaId) return TEXTO_SIN_EMPRESA;
  return nombres.get(empresaId) ?? "—";
}
