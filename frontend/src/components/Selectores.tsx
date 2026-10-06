import type { SelectHTMLAttributes } from "react";
import { useEmpresasCatalogo, useNombresEmpresa, useTerminalesCatalogo, useUsuariosCatalogo } from "../lib/queries";
import type { Rol } from "../lib/types";
import { Select } from "./ui";

type Props = Omit<SelectHTMLAttributes<HTMLSelectElement>, "onChange"> & {
  valor: string;
  onCambiar: (valor: string) => void;
  /** Texto de la opción vacía; si se omite, el selector no permite quedar vacío. */
  vacio?: string;
};

export function SelectorEmpresa({ valor, onCambiar, vacio, ...props }: Props) {
  const { data, isLoading } = useEmpresasCatalogo();
  return (
    <Select value={valor} onChange={(e) => onCambiar(e.target.value)} disabled={isLoading || props.disabled} {...props}>
      {vacio !== undefined ? <option value="">{vacio}</option> : <option value="" disabled>Selecciona una empresa</option>}
      {data?.map((e) => (
        <option key={e.id} value={e.id}>
          {e.nombre}
        </option>
      ))}
    </Select>
  );
}

export function SelectorTerminal({
  valor,
  onCambiar,
  vacio,
  empresaId,
  soloActivas = false,
  ...props
}: Props & { empresaId?: string; soloActivas?: boolean }) {
  const { data, isLoading } = useTerminalesCatalogo(empresaId || undefined);
  const nombres = useNombresEmpresa();
  const terminales = (data ?? []).filter((t) => !soloActivas || t.activa);
  return (
    <Select value={valor} onChange={(e) => onCambiar(e.target.value)} disabled={isLoading || props.disabled} {...props}>
      {vacio !== undefined ? <option value="">{vacio}</option> : <option value="" disabled>Selecciona una terminal</option>}
      {terminales.map((t) => (
        <option key={t.id} value={t.id}>
          {t.identificador_terminal}
          {!empresaId && nombres.get(t.empresa_id) ? ` — ${nombres.get(t.empresa_id)}` : ""}
          {!t.activa ? " (inactiva)" : ""}
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
      {vacio !== undefined ? <option value="">{vacio}</option> : <option value="" disabled>Selecciona un usuario</option>}
      {usuarios.map((u) => (
        <option key={u.id} value={u.id}>
          {u.nombre} {u.apellidos} ({u.correo})
        </option>
      ))}
    </Select>
  );
}
