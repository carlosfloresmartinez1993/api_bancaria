// Tipos que reflejan los esquemas Pydantic del backend.
// Los montos llegan como texto ("1234.50") para no perder precisión.
//
// Jerarquía: Empresa → Cliente (en la API, "terminal") → Proyecto (con su % de comisión).

export type Rol = "admin" | "contador";

export interface Pagina<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Usuario {
  id: string;
  nombre: string;
  apellidos: string;
  correo: string;
  rol: Rol;
  activo: boolean;
  fecha_creacion: string;
}

export interface Token {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface Empresa {
  id: string;
  usuario_id: string;
  nombre: string;
  csf: string | null;
  banco: string | null;
  numero_cuenta: string | null;
  clabe: string | null;
  fecha_registro: string;
  num_clientes: number;
}

export interface Saldo {
  al_dia: string;
  ingresos_brutos: string;
  comisiones: string;
  ingresos_netos: string;
  salidas: string;
  saldo: string;
}

/** Cliente: en la API se llama "terminal". */
export interface Terminal {
  id: string;
  empresa_id: string;
  identificador_terminal: string;
  activa: boolean;
  fecha_registro: string;
  num_proyectos: number;
}

export interface Proyecto {
  id: string;
  terminal_id: string;
  empresa_id: string;
  nombre: string;
  activo: boolean;
  fecha_registro: string;
  porcentaje_vigente: string | null;
}

export interface HistorialPorcentaje {
  id: string;
  proyecto_id: string;
  porcentaje: string;
  fecha_inicio_vigencia: string;
  fecha_fin_vigencia: string | null;
}

export interface CambioPorcentajeOut {
  historial: HistorialPorcentaje;
  movimientos_recalculados: number;
}

export interface MetodoPago {
  id: string;
  nombre: string;
  activo: boolean;
  fecha_registro: string;
}

export interface Movimiento {
  id: string;
  proyecto_id: string;
  terminal_id: string;
  empresa_id: string;
  usuario_id: string;
  metodo_pago_id: string;
  fecha_movimiento: string;
  monto_bruto: string;
  porcentaje_aplicado: string;
  comision: string;
  monto_neto: string;
  requiere_factura: boolean;
  fecha_captura: string;
  observaciones: string | null;
}

export interface Salida {
  id: string;
  proyecto_id: string;
  terminal_id: string;
  empresa_id: string;
  usuario_id: string;
  metodo_pago_id: string;
  monto: string;
  destino: string;
  fecha: string;
  observaciones: string | null;
  fecha_registro: string;
}

export interface SalidaRegistrada {
  salida: Salida;
  saldo_proyecto: string;
  saldo_empresa: string;
  advertencia: string | null;
}

export interface Reporte {
  titulo: string;
  parametros: Record<string, unknown>;
  columnas: { clave: string; etiqueta: string }[];
  filas: Record<string, unknown>[];
  totales: Record<string, unknown> | null;
  elaborado_por: string | null;
}

export const ACCIONES_BITACORA = [
  "CREAR_USUARIO",
  "EDITAR_USUARIO",
  "CAMBIO_PASSWORD",
  "ACTIVAR",
  "DESACTIVAR",
  "REASIGNAR_EMPRESA",
  "CAMBIO_PORCENTAJE",
  "EDITAR_MOVIMIENTO",
  "ELIMINAR_MOVIMIENTO",
  "EDITAR_SALIDA",
  "ELIMINAR_SALIDA",
  "CIERRE_ENVIADO",
  "CIERRE_ERROR",
] as const;
