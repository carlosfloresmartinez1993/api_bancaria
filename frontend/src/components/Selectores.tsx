import { useEffect, type SelectHTMLAttributes } from "react";
import { porcentaje } from "../lib/format";
import {
  useEmpresasCatalogo,
  useMetodosPago,
  useNombresEmpresa,
  useNombresTerminal,
  useProyectosCatalogo,
  useTerminalesCatalogo,
  useUsuariosCatalogo,
} from "../lib/queries";
import type { Rol } from "../lib/types";
import { Select } from "./ui";

type Props = Omit<SelectHTMLAttributes<HTMLSelectElement>, "onChange"> & {
  valor: string;
  onCambiar: (valor: string) => void;
  /** Texto de la opción vacía; si se omite, el selector no permite quedar vacío. */
  vacio?: string;
};

function Opcion0({ vacio, texto }: { vacio?: string; texto: string }) {
  return vacio !== undefined ? <option value="">{vacio}</option> : <option value="" disabled>{texto}</option>;
}

export function SelectorEmpresa({ valor, onCambiar, vacio, ...props }: Props) {
  const { data, isLoading } = useEmpresasCatalogo();
  return (
    <Select value={valor} onChange={(e) => onCambiar(e.target.value)} disabled={isLoading || props.disabled} {...props}>
      <Opcion0 vacio={vacio} texto="Selecciona una empresa" />
      {data?.map((e) => (
        <option key={e.id} value={e.id}>
          {e.nombre}
        </option>
      ))}
    </Select>
  );
}

/** Selector de clientes (terminales), opcionalmente de una empresa. */
export function SelectorCliente({
  valor,
  onCambiar,
  vacio,
  empresaId,
  soloActivos = false,
  ...props
}: Props & { empresaId?: string; soloActivos?: boolean }) {
  const { data, isLoading } = useTerminalesCatalogo(empresaId || undefined);
  const nombres = useNombresEmpresa();
  const clientes = (data ?? []).filter((t) => !soloActivos || t.activa);
  return (
    <Select value={valor} onChange={(e) => onCambiar(e.target.value)} disabled={isLoading || props.disabled} {...props}>
      <Opcion0 vacio={vacio} texto="Selecciona un cliente" />
      {clientes.map((t) => (
        <option key={t.id} value={t.id}>
          {t.identificador_terminal}
          {!empresaId && nombres.get(t.empresa_id) ? ` — ${nombres.get(t.empresa_id)}` : ""}
          {!t.activa ? " (inactivo)" : ""}
        </option>
      ))}
    </Select>
  );
}

/** Selector de proyectos de un cliente o de una empresa; muestra el % vigente. */
export function SelectorProyecto({
  valor,
  onCambiar,
  vacio,
  empresaId,
  terminalId,
  soloActivos = false,
  autoSeleccionar = false,
  ...props
}: Props & { empresaId?: string; terminalId?: string; soloActivos?: boolean; autoSeleccionar?: boolean }) {
  const { data, isLoading } = useProyectosCatalogo({ empresaId, terminalId });
  const nombresCliente = useNombresTerminal();
  const proyectos = (data ?? []).filter((p) => !soloActivos || p.activo);

  // Si solo hay un proyecto posible, se elige solo.
  const unico = proyectos.length === 1 ? proyectos[0].id : null;
  useEffect(() => {
    if (autoSeleccionar && !valor && unico) onCambiar(unico);
  }, [autoSeleccionar, valor, unico, onCambiar]);

  return (
    <Select value={valor} onChange={(e) => onCambiar(e.target.value)} disabled={isLoading || props.disabled} {...props}>
      <Opcion0 vacio={vacio} texto={terminalId || empresaId ? "Selecciona un proyecto" : "Elige primero el cliente"} />
      {proyectos.map((p) => (
        <option key={p.id} value={p.id}>
          {!terminalId && nombresCliente.get(p.terminal_id) ? `${nombresCliente.get(p.terminal_id)} · ` : ""}
          {p.nombre} ({porcentaje(p.porcentaje_vigente)})
          {!p.activo ? " (inactivo)" : ""}
        </option>
      ))}
    </Select>
  );
}

export function SelectorMetodoPago({ valor, onCambiar, vacio, ...props }: Props) {
  const { data, isLoading } = useMetodosPago();
  return (
    <Select value={valor} onChange={(e) => onCambiar(e.target.value)} disabled={isLoading || props.disabled} {...props}>
      <Opcion0 vacio={vacio} texto="Selecciona el método de pago" />
      {data?.map((m) => (
        <option key={m.id} value={m.id}>
          {m.nombre}
        </option>
      ))}
    </Select>
  );
}

export function SelectorUsuario({ valor, onCambiar, vacio, rol, ...props }: Props & { rol?: Rol }) {
  const { data, isLoading } = useUsuariosCatalogo();
  const usuarios = (data ?? []).filter((u) => (!rol || u.rol === rol) && u.activo);
  return (
    <Select value={valor} onChange={(e) => onCambiar(e.target.value)} disabled={isLoading || props.disabled} {...props}>
      <Opcion0 vacio={vacio} texto="Selecciona un usuario" />
      {usuarios.map((u) => (
        <option key={u.id} value={u.id}>
          {u.nombre} {u.apellidos} ({u.correo})
        </option>
      ))}
    </Select>
  );
}
